"""M6: compare two runs cell by cell with multiple-comparison correction and an MDE.

Reads censored frames from ``momus.survival.censor`` (six columns are used: ``config_hash``,
``config``, ``replicate_index``, ``t``, ``observed``, ``horizon``) and returns a
``DiffResult``. ``delta = rate_b - rate_a``: negative is *safer* only when ``event`` names a
failure. If ``event`` names a success, safer and worse invert; nothing here is clever
about that.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy import stats

from momus.store import RunManifest

Method = Literal["fisher_bh", "mcnemar_bh", "logrank_bh"]

_METHODS: tuple[str, ...] = ("fisher_bh", "mcnemar_bh", "logrank_bh")
_REQUIRED = ("config_hash", "config", "replicate_index", "t", "observed", "horizon")

CELLS_COLUMNS = (
    "config_hash",
    "config",
    "n_a",
    "n_b",
    "events_a",
    "events_b",
    "rate_a",
    "rate_b",
    "delta",
    "stat",
    "p",
    "q",
    "verdict",
    "mde",
)
SUMMARY_FIELDS = (
    "method",
    "paired",
    "q",
    "event",
    "t_unit",
    "horizon",
    "n_safer",
    "n_worse",
    "n_unchanged",
    "n_not_comparable",
    "max_mde",
    "dropped_a",
    "dropped_b",
    "truncated",
)


class DiffError(Exception):
    """A diff cannot be computed as requested."""


class UnitMismatch(DiffError):
    """The two runs measure ``t`` in different units."""


class NotPairable(DiffError):
    """A paired method was requested but the runs are not pairable."""


# ---------- multiple comparisons ----------


def bh(p: NDArray[Any], q: float = 0.05) -> NDArray[np.float64]:
    """Benjamini-Hochberg adjusted q-values, same shape as p."""
    arr = np.asarray(p, dtype=np.float64)
    m = arr.size
    if m == 0:
        return np.empty(0, dtype=np.float64)
    flat = arr.reshape(-1)
    order = np.argsort(flat, kind="stable")
    ranked = flat[order]
    raw = ranked * m / np.arange(1, m + 1, dtype=np.float64)
    adjusted = np.minimum.accumulate(raw[::-1])[::-1]
    adjusted = np.minimum(adjusted, 1.0)
    out = np.empty(m, dtype=np.float64)
    out[order] = adjusted
    return out.reshape(arr.shape)


# ---------- minimum detectable effect ----------


def _power_two_proportion(delta: float, p_a: float, n_a: int, n_b: int, alpha: float) -> float:
    """Two-sided normal-approximation power to detect p_a + delta vs p_a.

    Pooled SE under the null, separate SEs under the alternative; the increased arm is
    paired with n_a, matching statsmodels' ``power_proportions_2indep`` convention.
    """
    p_alt = p_a + delta
    pooled = (p_alt * n_a + p_a * n_b) / (n_a + n_b)
    se_null = math.sqrt(pooled * (1.0 - pooled) * (1.0 / n_a + 1.0 / n_b))
    se_alt = math.sqrt(p_alt * (1.0 - p_alt) / n_a + p_a * (1.0 - p_a) / n_b)
    z = float(stats.norm.isf(alpha / 2.0))
    if se_alt == 0.0:
        return 1.0 if delta > z * se_null else 0.0
    upper = float(stats.norm.sf((z * se_null - delta) / se_alt))
    lower = float(stats.norm.cdf((-z * se_null - delta) / se_alt))
    return upper + lower


def mde_two_proportion(
    p_a: float, n_a: int, n_b: int, *, alpha: float = 0.05, power: float = 0.8
) -> float:
    """Smallest increase in event rate from p_a detectable at alpha (two-sided) and power.

    Normal approximation, solved by bisection on (0, 1 - p_a]. Rates of exactly 0 or 1
    use a 0.5/n continuity guard. If even the largest possible increase is not detectable
    the largest possible increase is returned.
    """
    if n_a <= 0 or n_b <= 0:
        raise DiffError(f"mde needs positive sample sizes, got n_a={n_a}, n_b={n_b}")
    if not 0.0 <= p_a <= 1.0:
        raise DiffError(f"p_a must be in [0, 1], got {p_a}")
    guarded = p_a
    if p_a <= 0.0:
        guarded = 0.5 / n_a
    elif p_a >= 1.0:
        guarded = 1.0 - 0.5 / n_a
    cap = 1.0 - guarded
    if _power_two_proportion(cap, guarded, n_a, n_b, alpha) < power:
        return (1.0 - p_a) if p_a < 1.0 else cap
    lo, hi = 0.0, cap
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _power_two_proportion(mid, guarded, n_a, n_b, alpha) >= power:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-12:
            break
    return hi


# ---------- per-cell tests ----------


def _fisher(ea: int, na: int, eb: int, nb: int) -> tuple[float, float]:
    res = stats.fisher_exact([[ea, na - ea], [eb, nb - eb]], alternative="two-sided")
    return float(res[0]), float(res[1])


def _mcnemar(cell_a: pd.DataFrame, cell_b: pd.DataFrame, config_hash: str) -> tuple[float, float]:
    for label, cell in (("a", cell_a), ("b", cell_b)):
        if cell["replicate_index"].duplicated().any():
            raise NotPairable(
                f"cell {config_hash}: duplicate replicate_index in run {label}; cannot pair"
            )
    joined = pd.merge(
        cell_a[["replicate_index", "observed"]],
        cell_b[["replicate_index", "observed"]],
        on="replicate_index",
        how="inner",
        suffixes=("_a", "_b"),
    )
    oa = joined["observed_a"].to_numpy(dtype=bool)
    ob = joined["observed_b"].to_numpy(dtype=bool)
    b = int(np.sum(oa & ~ob))
    c = int(np.sum(~oa & ob))
    if b + c == 0:
        return float(b - c), 1.0
    p = float(stats.binomtest(min(b, c), b + c, 0.5).pvalue)
    return float(b - c), p


def _logrank(
    t_a: NDArray[np.float64],
    o_a: NDArray[np.bool_],
    t_b: NDArray[np.float64],
    o_b: NDArray[np.bool_],
) -> tuple[float, float]:
    """Two-sample log-rank: (chi-square statistic with 1 df, p-value)."""
    times = np.unique(np.concatenate([t_a[o_a], t_b[o_b]]))
    observed = 0.0
    expected = 0.0
    variance = 0.0
    for x in times:
        n_a = int(np.sum(t_a >= x))
        n_b = int(np.sum(t_b >= x))
        n = n_a + n_b
        d_a = int(np.sum((t_a == x) & o_a))
        d_b = int(np.sum((t_b == x) & o_b))
        d = d_a + d_b
        if n == 0 or d == 0:
            continue
        observed += d_a
        expected += n_a * d / n
        if n > 1:
            variance += n_a * n_b * d * (n - d) / (n * n * (n - 1))
    if variance <= 0.0:
        return 0.0, 1.0
    statistic = (observed - expected) ** 2 / variance
    return float(statistic), float(stats.chi2.sf(statistic, 1))


# ---------- result ----------


@dataclass(frozen=True, eq=False)
class DiffResult:
    cells: pd.DataFrame
    method: Method
    paired: bool
    q: float
    event: str
    t_unit: str
    horizon: float
    n_safer: int
    n_worse: int
    n_unchanged: int
    n_not_comparable: int
    max_mde: float
    dropped_a: int
    dropped_b: int
    truncated: int

    def to_markdown(self) -> str:
        cols = list(CELLS_COLUMNS)
        lines = [
            f"Diff of `{self.event}` by {self.method} at q={self.q}: "
            f"n_safer={self.n_safer}, n_worse={self.n_worse}, n_unchanged={self.n_unchanged}, "
            f"n_not_comparable={self.n_not_comparable}, max_mde={self.max_mde:.4f}, "
            f"method={self.method}, paired={self.paired}, t_unit={self.t_unit}, "
            f"horizon={self.horizon}, truncated={self.truncated}, "
            f"dropped_a={self.dropped_a}, dropped_b={self.dropped_b}",
            "",
            "| " + " | ".join(cols) + " |",
            "|" + "|".join("---" for _ in cols) + "|",
        ]
        for row in self.cells.itertuples(index=False):
            values = [_md_cell(getattr(row, col)) for col in cols]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines) + "\n"

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {field: _native(getattr(self, field)) for field in SUMMARY_FIELDS}
        out["cells"] = [
            {col: _native(value) for col, value in record.items()}
            for record in self.cells.to_dict(orient="records")
        ]
        return out

    def check(self, fail_on: Literal["worse", "any"] = "worse") -> bool:
        """True if the diff passes.

        'worse': no cell significantly worse. 'any': nothing significant either way.
        """
        if fail_on == "worse":
            return self.n_worse == 0
        if fail_on == "any":
            return self.n_worse == 0 and self.n_safer == 0
        raise DiffError(f"fail_on must be 'worse' or 'any', got {fail_on!r}")


def _native(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_native(v) for v in value]
    return value


def _md_cell(value: Any) -> str:
    if isinstance(value, Mapping):
        return json.dumps(_native(value), sort_keys=True, separators=(",", ":"))
    if isinstance(value, float) or isinstance(value, np.floating):
        return f"{float(value):.6g}"
    return str(_native(value))


# ---------- diff ----------


def _validate_frame(df: pd.DataFrame, label: str) -> None:
    missing = [c for c in _REQUIRED if c not in df.columns]
    if missing:
        raise DiffError(f"frame {label} lacks columns {missing}; pass censor() output")
    if len(df) == 0:
        raise DiffError(f"frame {label} is empty")


def _frame_horizon(df: pd.DataFrame, label: str) -> float:
    present = df["horizon"].dropna().unique()
    if len(present) == 0:
        raise DiffError(f"frame {label} has no horizon")
    return float(np.max(present))


def _truncate(df: pd.DataFrame, h: float) -> tuple[pd.DataFrame, int]:
    out = df.copy()
    over = out["t"].to_numpy(dtype=np.float64) > h
    count = int(np.sum(over))
    if count:
        out.loc[over, "observed"] = False
        out.loc[over, "t"] = h
    out["observed"] = out["observed"].astype(bool)
    return out, count


def diff(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    event: str,
    method: Method = "fisher_bh",
    q: float = 0.05,
    power: float = 0.8,
    manifest_a: RunManifest | None = None,
    manifest_b: RunManifest | None = None,
) -> DiffResult:
    """Diff two censored frames cell by cell.

    a, b are censored frames from momus.survival.censor(). Manifests are required for
    pairing and unit checks; if omitted, unpaired and unchecked.
    """
    if method not in _METHODS:
        raise DiffError(f"method must be one of {_METHODS}, got {method!r}")
    if not 0.0 < q < 1.0:
        raise DiffError(f"q must be in (0, 1), got {q}")
    _validate_frame(a, "a")
    _validate_frame(b, "b")

    if manifest_a is not None and manifest_b is not None:
        if manifest_a.t_unit != manifest_b.t_unit:
            raise UnitMismatch(
                f"t_unit differs: {manifest_a.t_unit!r} (a) vs {manifest_b.t_unit!r} (b)"
            )
        paired = manifest_a.run_salt == manifest_b.run_salt
    else:
        paired = False
    if method == "mcnemar_bh" and not paired:
        if manifest_a is None or manifest_b is None:
            raise NotPairable("mcnemar_bh needs both manifests to establish pairing")
        raise NotPairable(
            f"mcnemar_bh needs matching run_salt; got {manifest_a.run_salt!r} vs "
            f"{manifest_b.run_salt!r}"
        )
    if manifest_a is not None:
        t_unit = manifest_a.t_unit
    elif manifest_b is not None:
        t_unit = manifest_b.t_unit
    else:
        t_unit = "unknown"

    horizon = min(_frame_horizon(a, "a"), _frame_horizon(b, "b"))
    a_t, truncated_a = _truncate(a, horizon)
    b_t, truncated_b = _truncate(b, horizon)

    hashes_a = set(a_t["config_hash"].astype(str))
    hashes_b = set(b_t["config_hash"].astype(str))
    common = sorted(hashes_a & hashes_b)
    dropped_a = len(hashes_a - hashes_b)
    dropped_b = len(hashes_b - hashes_a)

    groups_a = {str(k): g for k, g in a_t.groupby("config_hash", sort=False)}
    groups_b = {str(k): g for k, g in b_t.groupby("config_hash", sort=False)}

    rows: list[dict[str, Any]] = []
    for h in common:
        cell_a, cell_b = groups_a[h], groups_b[h]
        n_a, n_b = int(len(cell_a)), int(len(cell_b))
        o_a = cell_a["observed"].to_numpy(dtype=bool)
        o_b = cell_b["observed"].to_numpy(dtype=bool)
        events_a, events_b = int(o_a.sum()), int(o_b.sum())
        rate_a, rate_b = events_a / n_a, events_b / n_b
        if method == "fisher_bh":
            statistic, p = _fisher(events_a, n_a, events_b, n_b)
        elif method == "mcnemar_bh":
            statistic, p = _mcnemar(cell_a, cell_b, h)
        else:
            statistic, p = _logrank(
                cell_a["t"].to_numpy(dtype=np.float64),
                o_a,
                cell_b["t"].to_numpy(dtype=np.float64),
                o_b,
            )
        rows.append(
            {
                "config_hash": h,
                "config": cell_a["config"].iloc[0],
                "n_a": n_a,
                "n_b": n_b,
                "events_a": events_a,
                "events_b": events_b,
                "rate_a": float(rate_a),
                "rate_b": float(rate_b),
                "delta": float(rate_b - rate_a),
                "stat": float(statistic),
                "p": float(p),
                "q": float("nan"),
                "verdict": "unchanged",
                "mde": mde_two_proportion(rate_a, n_a, n_b, alpha=q, power=power),
            }
        )

    cells = pd.DataFrame.from_records(rows, columns=list(CELLS_COLUMNS))
    if rows:
        adjusted = bh(cells["p"].to_numpy(dtype=np.float64), q)
        deltas = cells["delta"].to_numpy(dtype=np.float64)
        verdicts = np.where(
            (adjusted < q) & (deltas < 0),
            "safer",
            np.where((adjusted < q) & (deltas > 0), "worse", "unchanged"),
        )
        cells["q"] = adjusted
        cells["verdict"] = verdicts
    cells["config"] = cells["config"].astype(object)
    cells["verdict"] = cells["verdict"].astype(object)

    n_safer = int((cells["verdict"] == "safer").sum())
    n_worse = int((cells["verdict"] == "worse").sum())
    n_unchanged = int(len(cells)) - n_safer - n_worse
    max_mde = float(cells["mde"].max()) if rows else 0.0

    return DiffResult(
        cells=cells,
        method=method,
        paired=paired,
        q=float(q),
        event=event,
        t_unit=t_unit,
        horizon=float(horizon),
        n_safer=n_safer,
        n_worse=n_worse,
        n_unchanged=n_unchanged,
        n_not_comparable=dropped_a + dropped_b,
        max_mde=max_mde,
        dropped_a=dropped_a,
        dropped_b=dropped_b,
        truncated=truncated_a + truncated_b,
    )
