"""M6: compare two runs cell by cell with multiple-comparison correction and an MDE.

Reads censored frames from ``proofload.survival.censor`` (six columns are used: ``config_hash``,
``config``, ``replicate_index``, ``t``, ``observed``, ``horizon``) and returns a
``DiffResult``. ``delta = rate_b - rate_a``: negative is *safer* only when ``event`` names a
failure. If ``event`` names a success, safer and worse invert; nothing here is clever
about that.
"""

from __future__ import annotations

import json
import math
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy import stats
from scipy.optimize import brentq

from proofload.store import RunManifest
from proofload.survival import aalen_johansen, competing_set

Method = Literal["fisher_bh", "mcnemar_bh", "logrank_bh"]

_METHODS: tuple[str, ...] = ("fisher_bh", "mcnemar_bh", "logrank_bh")
# The methods that read the correspondence between the two arms. Written once because the
# refusal and the warning are the same predicate seen from its two sides: a method in here
# needs pairing and refuses without it, a method outside it discards pairing and warns when
# there was pairing to discard.
_PAIRED_METHODS: tuple[str, ...] = ("mcnemar_bh",)
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
COVERAGE_COLUMNS = (
    "config_hash",
    "config",
    "rows_a",
    "rows_b",
    "no_outcome_a",
    "no_outcome_b",
    "comparable",
    "cause",
)

INTERVAL_COLUMNS = (
    "event",
    "config_hash",
    "config",
    "ci_lo",
    "ci_hi",
    "basis",
)

# The three bases an interval row may carry, written once here the way ``_CAUSES`` is.
# ``censored`` is a forward guard and not a live branch: ``_truncate_raw`` censors at the
# horizon, the horizon is >= every retained event time, and Aalen-Johansen there collapses to
# the naive proportion, so nothing ``multi_diff`` can be handed reaches it today. It stays
# because a later change to truncation or to the estimator would otherwise put a binomial
# interval on censored data silently, which is the class of number this tool exists to find.
INTERVAL_BASES = ("score_rd", "score_rd_paired", "censored")
_SCORE_RD, _SCORE_RD_PAIRED, _CENSORED = INTERVAL_BASES

# ADR-052: which interval is built follows the requested ``method`` and never ``paired``. Two
# runs that happen to share a run salt must not get a different number from two that do not, or
# the statistic becomes a property of run provenance rather than of the request.
_BASIS_BY_METHOD: Mapping[str, str] = {
    "fisher_bh": _SCORE_RD,
    "logrank_bh": _SCORE_RD,
    "mcnemar_bh": _SCORE_RD_PAIRED,
}

# ADR-050, per cell per arm. The score statistic is binomial, so an interval is constructed
# only where the Aalen-Johansen incidence equals the naive proportion.
_CIF_EQUALITY_TOLERANCE = 1e-12

# Bisection steps per endpoint. The bracket starts at most 2 wide, so 64 halvings put it at
# 1e-19 -- past double precision, which is the point: the loop stops because the bracket has
# collapsed to adjacent floats, not because a tolerance was guessed.
_INVERSION_STEPS = 64

# scipy refuses an rtol below 4 * eps.
_ROOT_RTOL = 4.0 * float(np.finfo(np.float64).eps)

# Why a non-comparable cell is a hole. The order is the precedence the cause is decided by:
# presence before errors, so a cell A ran and wholly errored that B never ran is ``only_a`` --
# the first thing a reader needs is that one arm has no rows at all, and ``no_outcome_a`` sits
# beside it in the same row for the rest. Written once here; M7 adds the two grid-only causes.
_CAUSES = ("only_a", "only_b", "no_outcome_both", "no_outcome_a", "no_outcome_b")
_ONLY_A, _ONLY_B, _NO_OUTCOME_BOTH, _NO_OUTCOME_A, _NO_OUTCOME_B = _CAUSES

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
    "max_mde_unchanged",
    "max_mde_unchanged_cell",
)


class DiffError(Exception):
    """A diff cannot be computed as requested."""


class UnitMismatch(DiffError):
    """The two runs measure ``t`` in different units."""


class NotPairable(DiffError):
    """A paired method was requested but the runs are not pairable."""


class UnpairedAnalysis(UserWarning):
    """The two runs are pairable and the requested method compares them as independent
    samples. A warning and never a refusal: which test to run is the caller's decision, and
    the correspondence is discarded, not misused. A ``UserWarning`` subclass so a CI that
    wants a gate can spell it ``-W error::proofload.diff.UnpairedAnalysis`` without turning
    every other warning in the process into an error."""


class UnknownEvent(DiffError):
    """An event name that appears in none of the frames a command loaded.

    Raised by the CLI's validation, not by the library: ``multi_diff`` stays permissive, so
    a caller may legitimately report on an event that did not occur.
    """


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


def _discordant(
    cell_a: pd.DataFrame, cell_b: pd.DataFrame, config_hash: str
) -> tuple[int, int, int]:
    """``(b, c, pairs)``: ``b`` observed in a only, ``c`` in b only, over the joined pairs.

    Split out of ``_mcnemar`` so S24's paired interval can reach the same three numbers the
    test was computed from. An unmatched replicate is dropped by the inner join rather than
    mispaired, and the duplicate guard is here because it is a fact about pairing, not about
    the binomial that follows.
    """
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
    return int(np.sum(oa & ~ob)), int(np.sum(~oa & ob)), int(len(joined))


def _mcnemar(cell_a: pd.DataFrame, cell_b: pd.DataFrame, config_hash: str) -> tuple[float, float]:
    b, c, _ = _discordant(cell_a, cell_b, config_hash)
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
    max_mde_unchanged: float = field(default=math.nan)  # max mde over verdict == 'unchanged'
    max_mde_unchanged_cell: str | None = None  # config_hash attaining it; None if none unchanged

    def to_markdown(self) -> str:
        cols = list(CELLS_COLUMNS)
        lines = [
            f"Diff of `{self.event}` by {self.method} at q={self.q}: "
            f"n_safer={self.n_safer}, n_worse={self.n_worse}, n_unchanged={self.n_unchanged}, "
            f"n_not_comparable={self.n_not_comparable}, max_mde={self.max_mde:.4f}, "
            f"method={self.method}, paired={self.paired}, t_unit={self.t_unit}, "
            f"horizon={self.horizon}, truncated={self.truncated}, "
            f"dropped_a={self.dropped_a}, dropped_b={self.dropped_b}, "
            f"max_mde_unchanged={self.max_mde_unchanged:.4f}, "
            f"max_mde_unchanged_cell={self.max_mde_unchanged_cell}",
            "",
            "| " + " | ".join(cols) + " |",
            "|" + "|".join("---" for _ in cols) + "|",
        ]
        for row in self.cells.itertuples(index=False):
            values = [_md_cell(getattr(row, col)) for col in cols]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines) + "\n"

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {name: _native(getattr(self, name)) for name in SUMMARY_FIELDS}
        out["max_mde_unchanged"] = _nan_to_none(self.max_mde_unchanged)
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

    a, b are censored frames from proofload.survival.censor(). Manifests are required for
    pairing and unit checks; if omitted, unpaired and unchecked.
    """
    if method not in _METHODS:
        raise DiffError(f"method must be one of {_METHODS}, got {method!r}")
    if not 0.0 < q < 1.0:
        raise DiffError(f"q must be in (0, 1), got {q}")
    _validate_frame(a, "a")
    _validate_frame(b, "b")

    paired, t_unit = _pairing(method, manifest_a, manifest_b)

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
    max_mde_unchanged, max_mde_unchanged_cell = _unchanged_mde(cells)

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
        max_mde_unchanged=max_mde_unchanged,
        max_mde_unchanged_cell=max_mde_unchanged_cell,
    )


def _nan_to_none(value: float) -> float | None:
    return None if math.isnan(value) else float(value)


def _unchanged_mde(cells: pd.DataFrame) -> tuple[float, str | None]:
    """(max mde over verdict == 'unchanged', first config_hash attaining it), or (nan, None)."""
    unchanged = cells[cells["verdict"] == "unchanged"]
    if len(unchanged) == 0:
        return math.nan, None
    top = float(unchanged["mde"].max())
    hits = unchanged.loc[unchanged["mde"] == top, "config_hash"]
    return top, str(hits.iloc[0])


# ---------- multi-event ----------

_RAW_REQUIRED = ("config_hash", "config", "replicate_index", "outcome", "t", "horizon")
_MAX_EVENTS = 6
_TRADES_COLUMNS = ("config_hash", "config", "safer_events", "worse_events")
_MULTI_SUMMARY_FIELDS = (
    "method",
    "paired",
    "q",
    "t_unit",
    "horizon",
    "n_tests",
    "n_not_comparable",
    "dropped_a",
    "dropped_b",
    "truncated",
    "inferred",
    "non_event",
)
_EVENT_SUMMARY_FIELDS = (
    "event",
    "n_safer",
    "n_worse",
    "n_unchanged",
    "max_mde",
    "max_mde_unchanged",
    "max_mde_unchanged_cell",
    "cause_specific",
)


class EventInferenceError(DiffError):
    """The event set could not be inferred from the outcomes present."""


@dataclass(frozen=True, eq=False)
class EventDiff:
    """One event's view of a multi-event diff. ``cells`` has the ``DiffResult.cells`` columns;
    ``rate_a`` / ``rate_b`` are Aalen-Johansen cumulative incidence at the horizon."""

    event: str
    cells: pd.DataFrame
    n_safer: int
    n_worse: int
    n_unchanged: int
    max_mde: float
    max_mde_unchanged: float
    max_mde_unchanged_cell: str | None
    cause_specific: bool

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {name: _native(getattr(self, name)) for name in _EVENT_SUMMARY_FIELDS}
        out["max_mde_unchanged"] = _nan_to_none(self.max_mde_unchanged)
        out["cells"] = [
            {col: _native(value) for col, value in record.items()}
            for record in self.cells.to_dict(orient="records")
        ]
        return out


@dataclass(frozen=True, eq=False)
class MultiDiffResult:
    events: tuple[str, ...]
    by_event: Mapping[str, EventDiff]
    method: Method
    paired: bool
    q: float
    t_unit: str
    horizon: float
    n_tests: int
    n_not_comparable: int
    dropped_a: int
    dropped_b: int
    truncated: int
    trades: pd.DataFrame
    inferred: bool
    non_event: str | None
    coverage: pd.DataFrame | None = None
    # S24. All six defaulted: M7's oracles build this result by hand from keywords, and an
    # undefaulted field breaks every one of them. ``n_rejected`` is the family's BH rejection
    # count -- the single derivation of ADR-049's R -- and ``alpha_star`` is q * R / n_tests;
    # both are carried so ``cli.py`` can print the arithmetic without doing any of it.
    intervals: pd.DataFrame | None = None
    interval_level: float | None = None
    alpha_star: float | None = None
    n_rejected: int = 0
    n_interval_only: int = 0
    n_verdict_only: int = 0

    def _ordered_events(self) -> list[str]:
        return sorted(
            self.events,
            key=lambda e: (-self.by_event[e].n_worse, -self.by_event[e].n_safer, e),
        )

    def _method_label(self) -> str:
        return f"{self.method} (cause-specific)" if self.method == "logrank_bh" else self.method

    def headline(self) -> str:
        """Every event, worst first, then the method line. Never a causal claim."""
        parts = [
            f"{e}: {self.by_event[e].n_safer} safer, {self.by_event[e].n_worse} worse"
            for e in self._ordered_events()
        ]
        pairing = "paired" if self.paired else "unpaired"
        return (
            " · ".join(parts)
            + f"\n(aalen_johansen + {self._method_label()}, BH q<{self.q} over "
            f"{self.n_tests} tests, {pairing})"
        )

    def trade_line(self) -> str | None:
        """None when ``trades`` is empty; otherwise a count of co-occurrence, not a cause."""
        if len(self.trades) == 0:
            return None
        pairs: dict[tuple[str, str], int] = {}
        for row in self.trades.itertuples(index=False):
            for safer in row.safer_events:
                for worse in row.worse_events:
                    pairs[(safer, worse)] = pairs.get((safer, worse), 0) + 1
        (safer, worse), _ = min(pairs.items(), key=lambda kv: (-kv[1], kv[0]))
        n = len(self.trades)
        return (
            f"Trade: {safer} fell in {n} {'cell' if n == 1 else 'cells'} where {worse} rose. "
            "The patch moved failures, it did not remove them."
        )

    def to_markdown(self) -> str:
        lines: list[str] = []
        if self.inferred:
            lines.append(
                f"events: {', '.join(self.events)} "
                f"(inferred; {self.non_event} treated as non-event)"
            )
        lines.extend(self.headline().splitlines())
        trade = self.trade_line()
        if trade is not None:
            lines.append(trade)
        lines.append(
            f"method={self._method_label()}, paired={self.paired}, q={self.q}, "
            f"t_unit={self.t_unit}, horizon={self.horizon}, n_tests={self.n_tests}, "
            f"n_not_comparable={self.n_not_comparable}, dropped_a={self.dropped_a}, "
            f"dropped_b={self.dropped_b}, truncated={self.truncated}"
        )
        cols = list(CELLS_COLUMNS)
        for e in self._ordered_events():
            ev = self.by_event[e]
            lines.extend(
                [
                    "",
                    f"## {e}: n_safer={ev.n_safer}, n_worse={ev.n_worse}, "
                    f"n_unchanged={ev.n_unchanged}, max_mde={ev.max_mde:.4f}, "
                    f"max_mde_unchanged={ev.max_mde_unchanged:.4f}, "
                    f"max_mde_unchanged_cell={ev.max_mde_unchanged_cell}",
                    "",
                    "| " + " | ".join(cols) + " |",
                    "|" + "|".join("---" for _ in cols) + "|",
                ]
            )
            for row in ev.cells.itertuples(index=False):
                lines.append("| " + " | ".join(_md_cell(getattr(row, col)) for col in cols) + " |")
        if len(self.trades):
            tcols = list(_TRADES_COLUMNS)
            lines.extend(
                [
                    "",
                    "## trades",
                    "",
                    "| " + " | ".join(tcols) + " |",
                    "|" + "|".join("---" for _ in tcols) + "|",
                ]
            )
            for row in self.trades.itertuples(index=False):
                lines.append(
                    f"| {row.config_hash} | {_md_cell(row.config)} | "
                    f"{', '.join(row.safer_events)} | {', '.join(row.worse_events)} |"
                )
        return "\n".join(lines) + "\n"

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {name: _native(getattr(self, name)) for name in _MULTI_SUMMARY_FIELDS}
        out["events"] = list(self.events)
        out["by_event"] = {e: self.by_event[e].to_json() for e in self.events}
        out["trades"] = [
            {col: _native(value) for col, value in record.items()}
            for record in self.trades.to_dict(orient="records")
        ]
        out["coverage"] = (
            None
            if self.coverage is None
            else [
                {col: _native(value) for col, value in record.items()}
                for record in self.coverage.to_dict(orient="records")
            ]
        )
        out["intervals"] = (
            None
            if self.intervals is None
            else [
                {col: _native(value) for col, value in record.items()}
                for record in self.intervals.to_dict(orient="records")
            ]
        )
        out["interval_level"] = self.interval_level
        out["alpha_star"] = self.alpha_star
        out["n_rejected"] = self.n_rejected
        out["n_interval_only"] = self.n_interval_only
        out["n_verdict_only"] = self.n_verdict_only
        out["headline"] = self.headline()
        out["trade_line"] = self.trade_line()
        return out

    def check(self, fail_on: Literal["worse", "any"] = "worse") -> bool:
        """True if the diff passes. 'worse': no cell significantly worse in any event.
        'any': nothing significant either way in any event."""
        if fail_on == "worse":
            return all(ev.n_worse == 0 for ev in self.by_event.values())
        if fail_on == "any":
            return all(ev.n_worse == 0 and ev.n_safer == 0 for ev in self.by_event.values())
        raise DiffError(f"fail_on must be 'worse' or 'any', got {fail_on!r}")


def _outcome_counts(a: pd.DataFrame, b: pd.DataFrame) -> dict[str, int]:
    pooled = pd.concat([a["outcome"], b["outcome"]], ignore_index=True).dropna()
    return {str(k): int(v) for k, v in pooled.astype(str).value_counts().items()}


def infer_events(a: pd.DataFrame, b: pd.DataFrame) -> tuple[tuple[str, ...], str]:
    """Returns (events, non_event). Distinct non-null outcomes across both runs pooled,
    minus the single most frequent. Raises EventInferenceError on 0 events or more than 6."""
    for label, df in (("a", a), ("b", b)):
        if "outcome" not in df.columns:
            raise DiffError(f"frame {label} lacks an outcome column; pass raw store frames")
    counts = _outcome_counts(a, b)
    if not counts:
        raise EventInferenceError("no non-null outcomes in either run; nothing to infer")
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ordered[0][1]
    tied = [name for name, n in ordered if n == top]
    if len(tied) > 1:
        raise EventInferenceError(
            f"most frequent outcome is tied between {tied} at {top} rows each; "
            f"outcome counts: {dict(ordered)}; pass events= explicitly"
        )
    non_event = ordered[0][0]
    events = tuple(name for name, _ in ordered[1:])
    if not events:
        raise EventInferenceError(
            f"only one outcome present ({non_event!r}, {top} rows); no events to infer"
        )
    if len(events) > _MAX_EVENTS:
        raise EventInferenceError(
            f"{len(events)} events after dropping {non_event!r}, more than {_MAX_EVENTS}; "
            f"outcome counts: {dict(ordered)}; pass events= explicitly"
        )
    return events, non_event


def _validate_raw(df: pd.DataFrame, label: str) -> None:
    missing = [c for c in _RAW_REQUIRED if c not in df.columns]
    if missing:
        raise DiffError(f"frame {label} lacks columns {missing}; pass raw store frames")
    if len(df) == 0:
        raise DiffError(f"frame {label} is empty")


def _pairing(
    method: str, manifest_a: RunManifest | None, manifest_b: RunManifest | None
) -> tuple[bool, str]:
    """(paired, t_unit) with the S5 guards, raised before any event is tested.

    The one place ``paired`` is decided, for both entry points. It is also the only place
    that sees ``paired`` and ``method`` together before any cell exists, which is why the
    unpaired-analysis warning is raised here and not per cell.
    """
    if manifest_a is not None and manifest_b is not None:
        if manifest_a.t_unit != manifest_b.t_unit:
            raise UnitMismatch(
                f"t_unit differs: {manifest_a.t_unit!r} (a) vs {manifest_b.t_unit!r} (b)"
            )
        paired = manifest_a.run_salt == manifest_b.run_salt
    else:
        paired = False
    if method in _PAIRED_METHODS and not paired:
        if manifest_a is None or manifest_b is None:
            raise NotPairable("mcnemar_bh needs both manifests to establish pairing")
        raise NotPairable(
            f"mcnemar_bh needs matching run_salt; got {manifest_a.run_salt!r} vs "
            f"{manifest_b.run_salt!r}"
        )
    if paired and method not in _PAIRED_METHODS:
        # Never a switch. The same command running a different test depending on whether two
        # runs happen to share a salt would make the statistic a property of run provenance
        # rather than of the request, and a reader of the output could not tell which was
        # run without going back to the manifests. It says what was discarded and what the
        # alternative is spelled; the choice stays the caller's. No claim about power: that
        # depends on how far the two arms agree episode by episode, which is a fact about
        # the data and not about the salt.
        #
        # C18's message half, A27. The sentence used to promise a counterpart for every
        # episode, which the page it is printed beside can contradict: ``coverage`` lists
        # the cells one arm ran and the other did not, and a pair with two of those still
        # reports ``paired``. The correspondence the salt supports is the one over the cells
        # the comparison matched, so that is what this says, and it points at ``coverage``
        # for the rest rather than carrying a count -- there is none to carry here, which is
        # the whole reason the warning is raised before any cell exists. Whether the matched
        # rows are counterparts at all is a separate question and still unchecked; C18 keeps
        # it, and this restatement narrows the claim rather than answering it.
        assert manifest_a is not None  # implied by paired; narrows the type for run_salt
        warnings.warn(
            f"{method} compares two pairable runs as independent samples: both manifests "
            f"carry run_salt {manifest_a.run_salt!r}, which claims a counterpart at the "
            "same (config_hash, replicate_index) across the cells this comparison matched. "
            "Which cells those are is not settled here -- see coverage for the cells one "
            "arm ran and the other did not. Pass method='mcnemar_bh' to test that "
            "correspondence; whether it buys power depends on how far the two arms agree "
            "episode by episode.",
            UnpairedAnalysis,
            # 3, not survival.py's 2: this is one frame deeper than the public function, so
            # 3 lands on the caller of diff/multi_diff -- the line the reader has to change.
            stacklevel=3,
        )
    if manifest_a is not None:
        return paired, manifest_a.t_unit
    if manifest_b is not None:
        return paired, manifest_b.t_unit
    return paired, "unknown"


def _truncate_raw(df: pd.DataFrame, h: float) -> tuple[pd.DataFrame, int]:
    """Rows with t > h are re-censored at h: outcome becomes null so they are an event of
    no kind and count as censored at h for every CIF."""
    out = df.copy()
    over = out["t"].to_numpy(dtype=np.float64) > h
    count = int(np.sum(over))
    if count:
        out.loc[over, "t"] = h
        out.loc[over, "outcome"] = None
    out["outcome"] = out["outcome"].astype(object)
    return out, count


def _cause(rows_a: int, rows_b: int, no_outcome_a: int, no_outcome_b: int) -> str:
    """Section 0.3's five rules, in order. Presence is decided before errors: a cell A ran and
    wholly errored that B never ran is ``only_a``, with ``no_outcome_a == rows_a`` beside it in
    the same row. The counts are always carried; the cause names the first reason, not the
    only one."""
    if rows_a == 0:
        return _ONLY_B
    if rows_b == 0:
        return _ONLY_A
    with_a = rows_a - no_outcome_a
    with_b = rows_b - no_outcome_b
    if with_a == 0 and with_b == 0:
        return _NO_OUTCOME_BOTH
    if with_a == 0:
        return _NO_OUTCOME_A
    return _NO_OUTCOME_B


def _coverage(a: pd.DataFrame, b: pd.DataFrame, common: Sequence[str]) -> pd.DataFrame:
    """One row per ``config_hash`` in a union b, over the RAW frames, sorted by hash.

    Built before the null-outcome filter and before truncation, or a cell wholly errored in
    both arms -- which is in neither valid hash set and therefore in neither ``dropped_a`` nor
    ``dropped_b`` -- would appear nowhere, which is the defect this frame exists to fix.

    ``comparable`` is membership in the same ``common`` the cells are built from, never
    ``rows_a > 0 and rows_b > 0``: a wholly-errored cell has rows in both arms and is not
    comparable. ``config`` comes from A when A has a row for the hash, else from B.
    """
    groups_a = {str(k): g for k, g in a.groupby("config_hash", sort=False)}
    groups_b = {str(k): g for k, g in b.groupby("config_hash", sort=False)}
    comparable = set(common)
    records: list[dict[str, Any]] = []
    for h in sorted(set(groups_a) | set(groups_b)):
        in_a, in_b = h in groups_a, h in groups_b
        rows_a = int(len(groups_a[h])) if in_a else 0
        rows_b = int(len(groups_b[h])) if in_b else 0
        no_a = int(groups_a[h]["outcome"].isna().sum()) if in_a else 0
        no_b = int(groups_b[h]["outcome"].isna().sum()) if in_b else 0
        source = groups_a[h] if in_a else groups_b[h]
        seen = h in comparable
        records.append(
            {
                "config_hash": h,
                "config": source["config"].iloc[0],
                "rows_a": rows_a,
                "rows_b": rows_b,
                "no_outcome_a": no_a,
                "no_outcome_b": no_b,
                "comparable": seen,
                "cause": None if seen else _cause(rows_a, rows_b, no_a, no_b),
            }
        )
    frame = pd.DataFrame.from_records(records, columns=list(COVERAGE_COLUMNS))
    for col in ("config", "cause"):
        frame[col] = frame[col].astype(object)
    return frame


def _indicator_frame(cell: pd.DataFrame, observed: NDArray[np.bool_]) -> pd.DataFrame:
    return pd.DataFrame(
        {"replicate_index": cell["replicate_index"].to_numpy(), "observed": observed}
    )


def _build_intervals(
    rows: Sequence[Mapping[str, Any]],
    groups_a: Mapping[str, pd.DataFrame],
    groups_b: Mapping[str, pd.DataFrame],
    *,
    method: str,
    q: float,
    n_rejected: int,
    n_tests: int,
) -> tuple[pd.DataFrame | None, float | None, float | None, int, int]:
    """``(intervals, interval_level, alpha_star, n_interval_only, n_verdict_only)``.

    Called after the BH pass and after ``by_event``, because the level cannot be known before
    ``R``. ``n_rejected`` is that ``R``: the count of hypotheses BH rejected over the **flat
    family** ``multi_diff`` runs, one pass across every cell and every event. It arrives as an
    argument rather than being recounted here, so it has exactly one derivation.

    ``R == 0`` returns early rather than falling through with ``alpha_star == 0.0``: a
    bisection at zero would run to its step count and hand back ``(-1, 1)`` on every cell,
    which is true, worthless, and the output section 0.3 exists to prevent. The MDE lines are
    already the right object for that run.
    """
    if n_rejected == 0:
        return None, None, None, 0, 0
    alpha_star = q * n_rejected / n_tests
    interval_level = 1.0 - q * n_rejected / n_tests
    wanted = _BASIS_BY_METHOD[method]
    records: list[dict[str, Any]] = []
    n_interval_only = 0
    n_verdict_only = 0
    for row in rows:
        # ADR-050, both arms. A cell that passes in one arm and fails in the other is censored.
        comparable = (
            abs(row["rate_a"] - row["events_a"] / row["n_a"]) <= _CIF_EQUALITY_TOLERANCE
            and abs(row["rate_b"] - row["events_b"] / row["n_b"]) <= _CIF_EQUALITY_TOLERANCE
        )
        ci_lo: float | None
        ci_hi: float | None
        if not comparable:
            ci_lo, ci_hi, basis = None, None, _CENSORED
        elif wanted == _SCORE_RD_PAIRED:
            cell_a, cell_b = groups_a[row["config_hash"]], groups_b[row["config_hash"]]
            hit_a = np.asarray(cell_a["outcome"].to_numpy(dtype=object) == row["event"], dtype=bool)
            hit_b = np.asarray(cell_b["outcome"].to_numpy(dtype=object) == row["event"], dtype=bool)
            pair_b, pair_c, pairs = _discordant(
                _indicator_frame(cell_a, hit_a), _indicator_frame(cell_b, hit_b), row["config_hash"]
            )
            if pairs == 0:
                # No replicate index is shared, so the paired test saw nothing and rejects no
                # delta at any alpha. The inversion of a test with no information is the whole
                # parameter space, and that is what is reported -- not ``censored``, which
                # means the incidence is not a proportion, and not a refusal, because
                # ``_mcnemar`` already scored this cell p=1.0 rather than raising.
                ci_lo, ci_hi, basis = -1.0, 1.0, _SCORE_RD_PAIRED
            else:
                ci_lo, ci_hi = interval_rd_paired(pair_b, pair_c, pairs, alpha=alpha_star)
                basis = _SCORE_RD_PAIRED
        else:
            ci_lo, ci_hi = interval_rd(
                row["events_a"], row["n_a"], row["events_b"], row["n_b"], alpha=alpha_star
            )
            basis = _SCORE_RD
        if ci_lo is not None and ci_hi is not None:
            # Counted, never reconciled. Neither number changes a verdict, a q or a check();
            # section 0.6 has the direction of every expected disagreement and why none of them
            # is a bug, and log-rank is expected to produce both.
            excludes_zero = ci_lo > 0.0 or ci_hi < 0.0
            if row["verdict"] == "unchanged" and excludes_zero:
                n_interval_only += 1
            elif row["verdict"] != "unchanged" and not excludes_zero:
                n_verdict_only += 1
        records.append(
            {
                "event": row["event"],
                "config_hash": row["config_hash"],
                "config": row["config"],
                "ci_lo": ci_lo,
                "ci_hi": ci_hi,
                "basis": basis,
            }
        )
    frame = pd.DataFrame.from_records(records, columns=list(INTERVAL_COLUMNS))
    # object, not float: ``None`` on a censored row must stay ``None`` and not become NaN,
    # because ``ci_lo is None`` is the contract for that state.
    for col in ("config", "ci_lo", "ci_hi", "basis"):
        frame[col] = frame[col].astype(object)
    return frame, interval_level, alpha_star, n_interval_only, n_verdict_only


def multi_diff(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    events: Sequence[str] | None = None,
    method: Method = "fisher_bh",
    q: float = 0.05,
    power: float = 0.8,
    manifest_a: RunManifest | None = None,
    manifest_b: RunManifest | None = None,
) -> MultiDiffResult:
    """Diff two RAW store frames across several competing events at once.

    a, b are Store.read() frames (not censored); censoring is applied per event internally.
    events=None infers the set with infer_events. Per cell and event the compared quantity
    is the Aalen-Johansen cumulative incidence at the horizon, estimated once per cell over
    every terminal outcome present (the requested events and the non-event alike compete);
    the per-event test statistic treats every other outcome as censoring. One BH family
    covers every (cell, event) pair. Errored rows (null outcome) are excluded from every
    numerator and denominator.
    """
    if method not in _METHODS:
        raise DiffError(f"method must be one of {_METHODS}, got {method!r}")
    if not 0.0 < q < 1.0:
        raise DiffError(f"q must be in (0, 1), got {q}")
    _validate_raw(a, "a")
    _validate_raw(b, "b")
    paired, t_unit = _pairing(method, manifest_a, manifest_b)

    inferred = events is None
    non_event: str | None = None
    if events is None:
        event_set, non_event = infer_events(a, b)
    else:
        event_set = tuple(dict.fromkeys(str(e) for e in events))
        if not event_set:
            raise DiffError("events must name at least one outcome")

    a_valid = a.loc[a["outcome"].notna()].reset_index(drop=True)
    b_valid = b.loc[b["outcome"].notna()].reset_index(drop=True)
    if len(a_valid) == 0 or len(b_valid) == 0:
        raise DiffError("a run has no rows with a non-null outcome")
    horizon = min(_frame_horizon(a_valid, "a"), _frame_horizon(b_valid, "b"))
    a_t, truncated_a = _truncate_raw(a_valid, horizon)
    b_t, truncated_b = _truncate_raw(b_valid, horizon)

    hashes_a = set(a_t["config_hash"].astype(str))
    hashes_b = set(b_t["config_hash"].astype(str))
    common = sorted(hashes_a & hashes_b)
    dropped_a = len(hashes_a - hashes_b)
    dropped_b = len(hashes_b - hashes_a)
    groups_a = {str(k): g for k, g in a_t.groupby("config_hash", sort=False)}
    groups_b = {str(k): g for k, g in b_t.groupby("config_hash", sort=False)}

    # Coverage is grouped from the RAW frames, not from a_t / b_t: a cell whose every row
    # errored is absent from both valid hash sets, so grouping the filtered frames would lose
    # exactly the holes this answers for.
    coverage = _coverage(a, b, common)

    # The competing set for Aalen-Johansen is every terminal outcome present in either run,
    # not just the events asked for: a row that ended in the non-event is absorbed, not
    # censored, so it must stay out of the risk set for the events being compared. Only
    # rows re-censored by horizon truncation (null outcome) are censored. A requested event
    # outside this set did not occur; its incidence is zero rather than an error.
    competing = competing_set(a_t, b_t)

    # Gather every (cell, event) row first; one BH pass afterwards.
    rows: list[dict[str, Any]] = []
    for h in common:
        cell_a, cell_b = groups_a[h], groups_b[h]
        n_a, n_b = int(len(cell_a)), int(len(cell_b))
        t_a = cell_a["t"].to_numpy(dtype=np.float64)
        t_b = cell_b["t"].to_numpy(dtype=np.float64)
        out_a = cell_a["outcome"].to_numpy(dtype=object)
        out_b = cell_b["outcome"].to_numpy(dtype=object)
        cif_a = aalen_johansen(t_a, out_a, competing)
        cif_b = aalen_johansen(t_b, out_b, competing)
        for k in event_set:
            o_a = np.asarray(out_a == k, dtype=bool)
            o_b = np.asarray(out_b == k, dtype=bool)
            events_a, events_b = int(o_a.sum()), int(o_b.sum())
            rate_a = min(max(cif_a.at(k, horizon), 0.0), 1.0) if k in competing else 0.0
            rate_b = min(max(cif_b.at(k, horizon), 0.0), 1.0) if k in competing else 0.0
            if method == "fisher_bh":
                statistic, p = _fisher(events_a, n_a, events_b, n_b)
            elif method == "mcnemar_bh":
                statistic, p = _mcnemar(
                    _indicator_frame(cell_a, o_a), _indicator_frame(cell_b, o_b), h
                )
            else:
                statistic, p = _logrank(t_a, o_a, t_b, o_b)
            rows.append(
                {
                    "event": k,
                    "config_hash": h,
                    "config": cell_a["config"].iloc[0],
                    "n_a": n_a,
                    "n_b": n_b,
                    "events_a": events_a,
                    "events_b": events_b,
                    "rate_a": float(rate_a),
                    "rate_b": float(rate_b),
                    "delta": float(rate_b - rate_a) + 0.0,
                    "stat": float(statistic),
                    "p": float(p),
                    "q": math.nan,
                    "verdict": "unchanged",
                    "mde": mde_two_proportion(rate_a, n_a, n_b, alpha=q, power=power),
                }
            )

    if rows:
        adjusted = bh(np.array([r["p"] for r in rows], dtype=np.float64), q)
        for r, q_adj in zip(rows, adjusted, strict=True):
            r["q"] = float(q_adj)
            if q_adj < q and r["delta"] < 0:
                r["verdict"] = "safer"
            elif q_adj < q and r["delta"] > 0:
                r["verdict"] = "worse"

    by_event: dict[str, EventDiff] = {}
    verdicts: dict[str, dict[str, str]] = {}
    for k in event_set:
        records = [{c: r[c] for c in CELLS_COLUMNS} for r in rows if r["event"] == k]
        cells = pd.DataFrame.from_records(records, columns=list(CELLS_COLUMNS))
        cells["config"] = cells["config"].astype(object)
        cells["verdict"] = cells["verdict"].astype(object)
        n_safer = int((cells["verdict"] == "safer").sum())
        n_worse = int((cells["verdict"] == "worse").sum())
        max_mde_unchanged, max_mde_unchanged_cell = _unchanged_mde(cells)
        by_event[k] = EventDiff(
            event=k,
            cells=cells,
            n_safer=n_safer,
            n_worse=n_worse,
            n_unchanged=int(len(cells)) - n_safer - n_worse,
            max_mde=float(cells["mde"].max()) if records else 0.0,
            max_mde_unchanged=max_mde_unchanged,
            max_mde_unchanged_cell=max_mde_unchanged_cell,
            cause_specific=method == "logrank_bh",
        )
        verdicts[k] = dict(zip(cells["config_hash"], cells["verdict"], strict=True))

    # S24, after the BH pass and after ``by_event``: the level cannot be known before R.
    # R is read from the rows the BH pass wrote -- the count of hypotheses it rejected, not the
    # safer/worse sum, which drops a rejected cell whose delta is exactly zero. On Go1 under
    # log-rank those two differ by 196 to 88.
    n_tests = len(common) * len(event_set)
    n_rejected = sum(1 for r in rows if r["q"] < q)
    intervals, interval_level, alpha_star, n_interval_only, n_verdict_only = _build_intervals(
        rows, groups_a, groups_b, method=method, q=q, n_rejected=n_rejected, n_tests=n_tests
    )

    trade_rows: list[dict[str, Any]] = []
    for h in common:
        safer = tuple(k for k in event_set if verdicts[k][h] == "safer")
        worse = tuple(k for k in event_set if verdicts[k][h] == "worse")
        if safer and worse:
            trade_rows.append(
                {
                    "config_hash": h,
                    "config": groups_a[h]["config"].iloc[0],
                    "safer_events": safer,
                    "worse_events": worse,
                }
            )
    trades = pd.DataFrame.from_records(trade_rows, columns=list(_TRADES_COLUMNS))
    for col in ("config", "safer_events", "worse_events"):
        trades[col] = trades[col].astype(object)

    return MultiDiffResult(
        events=event_set,
        by_event=by_event,
        method=method,
        paired=paired,
        q=float(q),
        t_unit=t_unit,
        horizon=float(horizon),
        n_tests=n_tests,
        n_not_comparable=dropped_a + dropped_b,
        dropped_a=dropped_a,
        dropped_b=dropped_b,
        truncated=truncated_a + truncated_b,
        trades=trades,
        inferred=inferred,
        non_event=non_event,
        coverage=coverage,
        intervals=intervals,
        interval_level=interval_level,
        alpha_star=alpha_star,
        n_rejected=n_rejected,
        n_interval_only=n_interval_only,
        n_verdict_only=n_verdict_only,
    )


# ---------- S24: the interval on the delta ----------


def _require_arm(events: int, n: int, label: str) -> None:
    if n <= 0:
        raise DiffError(f"n_{label} must be positive, got {n}")
    if not 0 <= events <= n:
        raise DiffError(f"events_{label} must be in [0, {n}], got {events}")


def _require_pairs(b: int, c: int, n: int) -> None:
    if n <= 0:
        raise DiffError(f"n must be positive, got {n}")
    if b < 0 or c < 0 or b + c > n:
        raise DiffError(f"discordant counts must satisfy 0 <= b + c <= n, got b={b}, c={c}, n={n}")


def _require_alpha(alpha: float) -> None:
    if not 0.0 < alpha < 1.0:
        raise DiffError(f"alpha must be in (0, 1), got {alpha}")


def _maximise(slope: Callable[[float], float], lo: float, hi: float) -> float:
    """The stationary point of a concave log-likelihood on ``[lo, hi]``, from its derivative.

    Section 0.1 leaves the constrained MLE's route open between a Farrington-Manning cubic and
    a one-dimensional maximisation along the constrained line, because a mistranscribed cubic
    is a silent statistical bug no reviewer catches by reading. This is the maximisation. Every
    term of both log-likelihoods below is concave, so ``slope`` is strictly decreasing and the
    root is unique -- which is what makes a bracketed root find correct here rather than merely
    convergent, and why no cubic needs transcribing.
    """
    if hi - lo <= 1e-15:
        return lo
    inset = min(1e-12, (hi - lo) / 4.0)
    left, right = lo + inset, hi - inset
    if slope(left) <= 0.0:
        return lo
    if slope(right) >= 0.0:
        return hi
    return float(brentq(slope, left, right, xtol=1e-15, rtol=_ROOT_RTOL))


def score_p_rd(
    events_a: int, n_a: int, events_b: int, n_b: int, *, delta: float = 0.0
) -> float:
    """Two-sided p-value of the Miettinen-Nurminen score test of ``H0: p_b - p_a == delta``.

    The variance is evaluated at the constrained MLEs under the null and carries the
    ``N / (N - 1)`` factor that distinguishes Miettinen-Nurminen from Mee. Exactly ``1.0`` at
    ``delta == p_b_hat - p_a_hat``, where the constrained MLEs coincide with the unconstrained
    ones and the numerator is zero.
    """
    _require_arm(events_a, n_a, "a")
    _require_arm(events_b, n_b, "b")
    rate_a = _maximise(
        lambda rate: (
            (events_a / rate if events_a else 0.0)
            - ((n_a - events_a) / (1.0 - rate) if n_a - events_a else 0.0)
            + (events_b / (rate + delta) if events_b else 0.0)
            - ((n_b - events_b) / (1.0 - rate - delta) if n_b - events_b else 0.0)
        ),
        max(0.0, -delta),
        min(1.0, 1.0 - delta),
    )
    rate_b = rate_a + delta
    excess = events_b / n_b - events_a / n_a - delta
    pooled = n_a + n_b
    variance = (rate_a * (1.0 - rate_a) / n_a + rate_b * (1.0 - rate_b) / n_b) * (
        pooled / (pooled - 1.0)
    )
    if variance <= 0.0:
        # Both constrained rates are on a boundary, so the null pins the data exactly. The
        # delta is either the only one consistent with it or impossible under it; there is no
        # scale left to measure a departure against.
        return 1.0 if excess == 0.0 else 0.0
    return float(2.0 * stats.norm.sf(abs(excess) / math.sqrt(variance)))


def score_p_rd_paired(b: int, c: int, n: int, *, delta: float = 0.0) -> float:
    """Two-sided p-value of Tango's score test of ``H0: p_b - p_a == delta`` over ``n`` pairs
    with ``b`` discordant one way and ``c`` the other. Exactly ``1.0`` at
    ``delta == (c - b) / n``.

    The discordant counts and the concordant remainder are a trinomial; the constrained MLE
    maximises its log-likelihood along ``p_01 - p_10 == delta``.
    """
    _require_pairs(b, c, n)
    concordant = n - b - c
    discordance = _maximise(
        lambda psi: (
            (b / psi if b else 0.0)
            + (c / (psi + delta) if c else 0.0)
            - (2.0 * concordant / (1.0 - 2.0 * psi - delta) if concordant else 0.0)
        ),
        max(0.0, -delta),
        (1.0 - delta) / 2.0,
    )
    excess = (c - b) - n * delta
    variance = n * (2.0 * discordance + delta * (1.0 - delta))
    if variance <= 0.0:
        return 1.0 if excess == 0.0 else 0.0
    return float(2.0 * stats.norm.sf(abs(excess) / math.sqrt(variance)))


def _endpoint(p_at: Callable[[float], float], point: float, limit: float, alpha: float) -> float:
    """One end of the acceptance region, between the point estimate and the parameter space's
    edge. ``p_at`` is 1.0 at ``point`` and falls away from it, so the two bracket a root.

    An endpoint at the limit is **attained, not solved for**: the parameter space ran out
    before the test started rejecting, which happens exactly when the point estimate is itself
    at the limit. It is never a bisection that gave up -- the loop below has no early exit.
    """
    if p_at(limit) > alpha:
        return limit
    inside, outside = point, limit
    for _ in range(_INVERSION_STEPS):
        middle = 0.5 * (inside + outside)
        if p_at(middle) > alpha:
            inside = middle
        else:
            outside = middle
    return 0.5 * (inside + outside)


def interval_rd(
    events_a: int, n_a: int, events_b: int, n_b: int, *, alpha: float
) -> tuple[float, float]:
    """The set of ``delta`` that ``score_p_rd`` does not reject at ``alpha``, by bisection.

    Always contains ``p_b_hat - p_a_hat`` and always lies inside ``[-1.0, 1.0]``. The endpoints
    solve ``p(delta) == alpha`` and not ``alpha / 2``: ``score_p_rd`` already returns a
    two-sided p-value.
    """
    _require_arm(events_a, n_a, "a")
    _require_arm(events_b, n_b, "b")
    _require_alpha(alpha)

    def p_at(delta: float) -> float:
        return score_p_rd(events_a, n_a, events_b, n_b, delta=delta)

    point = events_b / n_b - events_a / n_a
    return (_endpoint(p_at, point, -1.0, alpha), _endpoint(p_at, point, 1.0, alpha))


def interval_rd_paired(b: int, c: int, n: int, *, alpha: float) -> tuple[float, float]:
    """``interval_rd``'s paired twin, inverting ``score_p_rd_paired``."""
    _require_pairs(b, c, n)
    _require_alpha(alpha)

    def p_at(delta: float) -> float:
        return score_p_rd_paired(b, c, n, delta=delta)

    return (_endpoint(p_at, (c - b) / n, -1.0, alpha), _endpoint(p_at, (c - b) / n, 1.0, alpha))
