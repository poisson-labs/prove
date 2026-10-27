"""Compare two runs cell by cell with multiple-comparison correction and an MDE.

Reads censored frames from ``poisson_prove.survival.censor`` (six columns are used: ``config_hash``,
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
from functools import cached_property
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy import stats
from scipy.optimize import brentq

from poisson_prove import _limits, _verdict
from poisson_prove.store import RunManifest
from poisson_prove.survival import aalen_johansen, competing_set

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
    # The way the test read the row, why a log-rank row's way is not its
    # horizon difference's, the matched pairs under the paired test with the discordant ones
    # (``n01`` only after had the event, ``n10`` only before), and why a limit is null.
    "direction",
    "direction_note",
    "pairs",
    "n01",
    "n10",
    "mde_note",
    # Holm's adjusted p and whether the row counts for the verdict, both
    # directions' limits with what they were computed for, the competing outcomes that shifted
    # under log-rank, and the interval on the change.
    "q_holm",
    "holm",
    "mde_rise",
    "mde_fall",
    "mde_rise_note",
    "mde_fall_note",
    "mde_test",
    "mde_basis",
    "mde_level",
    "mde_family",
    "mde_power",
    "mde_anchor",
    "mde_hr",
    "p_min",
    "flaggable",
    "mde_moves_with",
    "mde_rise_verdict",
    "mde_fall_verdict",
    "competing_shift",
    "ci_lo",
    "ci_hi",
    "ci_level",
    "ci_method",
)
# The columns that hold None, a string, a list or a bool: kept as objects, so an absent value
# reads ``None`` and never the NaN a float column would put there.
_OBJECT_COLUMNS = (
    "config", "verdict", "direction", "direction_note", "pairs", "n01", "n10", "mde_note",
    "mde_rise_note",
    "mde_fall_note", "mde_test", "mde_basis", "mde_anchor", "mde_moves_with", "competing_shift",
    "ci_lo", "ci_hi", "ci_method", "mde_rise", "mde_fall", "mde_hr", "mde_rise_verdict",
    "mde_fall_verdict", "holm", "flaggable",
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

# Which interval is built follows the requested ``method`` and never
# ``seed_identity_match``. Two runs that happen to share their seeds must not get a different
# number from two that do not, or the statistic becomes a property of run provenance rather than
# of the request.
_BASIS_BY_METHOD: Mapping[str, str] = {
    "fisher_bh": _SCORE_RD,
    "logrank_bh": _SCORE_RD,
    "mcnemar_bh": _SCORE_RD_PAIRED,
}

# Checked per cell per arm. The score statistic is binomial, so an interval is constructed
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
# beside it in the same row for the rest. Written once here; the report adds the two grid-only
# causes.
_CAUSES = ("only_a", "only_b", "no_outcome_both", "no_outcome_a", "no_outcome_b")
_ONLY_A, _ONLY_B, _NO_OUTCOME_BOTH, _NO_OUTCOME_A, _NO_OUTCOME_B = _CAUSES

SUMMARY_FIELDS = (
    "method",
    "seed_identity_match",
    "unpaired_analysis",
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


class DeclaredSetMismatch(DiffError):
    """Two runs declare different, non-empty outcome vocabularies.

    Raised in ``diff`` and ``multi_diff`` just before ``_pairing``, after the frames are
    validated and whatever the method: two competing sets are two quantities wearing one name,
    and a CIF is defined by its competing set. A run declaring outcomes against one declaring
    none is not refused, and neither are two runs whose observed sets differ while their
    declared sets agree -- refusing on the observed set fires on provider noise. Not in
    ``_pairing``: this is a refusal, not a pairing predicate.
    """


class NotPairable(DiffError):
    """A paired method was requested but the runs are not pairable."""


class UnpairedAnalysis(UserWarning):
    """The two runs are pairable and the requested method compares them as independent
    samples. A warning and never a refusal: which test to run is the caller's decision, and
    the correspondence is discarded, not misused. A ``UserWarning`` subclass so a CI that
    wants a gate can spell it ``-W error::poisson_prove.diff.UnpairedAnalysis`` without turning
    every other warning in the process into an error."""


class MixedCases(DiffError):
    """A compared condition's episodes, both runs together, report more than one case id:
    the condition ran several cases, so its rows mix what they compare."""


class KindConflict(DiffError):
    """Two sources disagree on whether an event is a failure or a success: the command line and
    a run's declaration, or the two runs' declarations."""


#: An event's kind, which decides whether a rise of it is worse or safer.
KINDS = ("failure", "success")
#: The accepted change when neither run recorded one: the default ``--max-mde``.
DEFAULT_THRESHOLD = 0.20


class UnknownEvent(DiffError):
    """An event name that appears in none of the frames a command loaded.

    Raised by the CLI's validation, not by the library: ``multi_diff`` stays permissive, so
    a caller may legitimately report on an event that did not occur.
    """


# ---------- multiple comparisons ----------


def holm(p: NDArray[Any], q: float = 0.05) -> NDArray[np.float64]:
    """Holm's step-down adjusted p-values, the same shape as ``p``: in ascending order of ``p``
    (ties in their own order), each is the largest so far of ``min(1, (M - j + 1) * p_(j))``. A
    row holds at the family-wise level ``q`` when its value is below ``q``; ``q`` is taken, as
    ``bh`` takes it, and not used."""
    arr = np.asarray(p, dtype=np.float64)
    flat = arr.reshape(-1)
    m = flat.size
    order = np.argsort(flat, kind="stable")
    stepped = np.minimum(1.0, (m - np.arange(m)) * flat[order])
    out = np.empty(m, dtype=np.float64)
    out[order] = np.maximum.accumulate(stepped) if m else stepped
    return out.reshape(arr.shape)


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

    Pooled SE under the null, separate SEs under the alternative; the changed arm B, at
    ``p_a + delta``, is paired with ``n_b`` and the baseline with ``n_a``, matching
    statsmodels' ``power_proportions_2indep`` read the way its documentation says.
    """
    p_alt = p_a + delta
    pooled = (p_a * n_a + p_alt * n_b) / (n_a + n_b)
    se_null = math.sqrt(pooled * (1.0 - pooled) * (1.0 / n_a + 1.0 / n_b))
    se_alt = math.sqrt(p_a * (1.0 - p_a) / n_a + p_alt * (1.0 - p_alt) / n_b)
    z = float(stats.norm.isf(alpha / 2.0))
    if se_alt == 0.0:
        return 1.0 if delta > z * se_null else 0.0
    upper = float(stats.norm.sf((z * se_null - delta) / se_alt))
    lower = float(stats.norm.cdf((-z * se_null - delta) / se_alt))
    return upper + lower


def mde_two_proportion(
    p_a: float, n_a: int, n_b: int, *, alpha: float = 0.05, power: float = 0.8
) -> float:
    """The smallest rise from the share ``p_a`` a two-sided test at ``alpha`` would catch with
    ``power``, between samples of ``n_a`` and ``n_b``, by the normal approximation, solved by
    bisection. A share of exactly 0 uses a ``0.5 / n_a`` guard; at a share of 1 no rise is
    possible and the result is NaN; if even the largest possible rise would not be caught, that
    largest rise is returned. Not the limit a comparison prints, which is computed for the test
    it ran."""
    if n_a <= 0 or n_b <= 0:
        raise DiffError(f"mde needs positive sample sizes, got n_a={n_a}, n_b={n_b}")
    if not 0.0 <= p_a <= 1.0:
        raise DiffError(f"p_a must be in [0, 1], got {p_a}")
    if p_a >= 1.0:
        return math.nan
    guarded = 0.5 / n_a if p_a <= 0.0 else p_a
    cap = 1.0 - guarded
    if _power_two_proportion(cap, guarded, n_a, n_b, alpha) < power:
        return 1.0 - p_a
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


#: The single-event ``diff``'s two reasons a cell prints no limit, each beginning with the word
#: printed for it.
_AT_CEILING = "no room (at ceiling: the baseline had the event in every run)"
_NO_RISE_DETECTABLE = "none detectable (not even the largest possible rise would be caught)"


def _single_event_limit(
    events_a: int, n_a: int, n_b: int, alpha: float, power: float
) -> tuple[float, str | None]:
    """The single-event ``diff``'s limit for a cell and why it has none: a baseline that had the
    event in every run, decided from the counts and never from a floating rate, has no limit
    (NaN); one whose whole headroom is not detectable keeps the headroom with a note."""
    if events_a == n_a:
        return math.nan, _AT_CEILING
    rate_a = events_a / n_a
    mde = mde_two_proportion(rate_a, n_a, n_b, alpha=alpha, power=power)
    guarded = 0.5 / n_a if rate_a <= 0.0 else rate_a
    if _power_two_proportion(1.0 - guarded, guarded, n_a, n_b, alpha) < power:
        return mde, _NO_RISE_DETECTABLE
    return mde, None


# ---------- directions and verdict words ----------


def _logrank_signed(
    t_a: NDArray[np.float64],
    o_a: NDArray[np.bool_],
    t_b: NDArray[np.float64],
    o_b: NDArray[np.bool_],
) -> float:
    """B's observed minus expected events over the pooled event times: the sign a log-rank
    row's direction is read from (positive, B had the event sooner or more often: a rise)."""
    total = 0.0
    for x in np.unique(np.concatenate([t_a[o_a], t_b[o_b]])):
        at_risk_a = int(np.sum(t_a >= x))
        at_risk_b = int(np.sum(t_b >= x))
        events = int(np.sum((t_a == x) & o_a)) + int(np.sum((t_b == x) & o_b))
        total += int(np.sum((t_b == x) & o_b)) - at_risk_b * events / (at_risk_a + at_risk_b)
    return float(total)


def _direction(flagged: bool, signed: float) -> str:
    """A row's direction: ``higher`` or ``lower`` when it is flagged and moved, else
    ``unchanged``."""
    way = _verdict.direction_of(signed) if flagged else None
    return _verdict.UNCHANGED if way is None else way


def _verdict_word(direction: str, kind: str | None) -> str:
    """A row's ``verdict``: ``worse`` or ``safer`` for an event whose kind is known, the direction
    word otherwise, on the result object as on every surface."""
    if direction == _verdict.UNCHANGED or kind is None:
        return direction
    return _verdict.judged(direction, kind)


def _direction_of_record(record: Mapping[str, Any], kind: str | None) -> str:
    """A cell's direction, read back from its verdict when a frame built by hand carries none (an
    event of unknown kind is read as a failure there, as the comparison first recorded it)."""
    direction = record.get("direction")
    if isinstance(direction, str):
        return direction
    verdict = str(record.get("verdict"))
    if verdict in (_verdict.UNCHANGED, _verdict.HIGHER, _verdict.LOWER):
        return verdict
    rise = "safer" if kind == "success" else "worse"
    return _verdict.HIGHER if verdict == rise else _verdict.LOWER


def _objects(cells: pd.DataFrame, records: Sequence[Mapping[str, Any]]) -> None:
    """Set the object columns from the records, so an absent value stays None."""
    for col in _OBJECT_COLUMNS:
        values = [_none_if_nan(r.get(col)) for r in records]
        cells[col] = pd.Series(values, index=cells.index, dtype=object)


def _none_if_nan(value: Any) -> Any:
    return None if isinstance(value, float) and math.isnan(value) else value


#: A log-rank row whose way is not its horizon difference's says the test read when the
#: events happened, which way that went, and the difference it did not follow.
_TIMING_NOTE = (
    "the log-rank test read when the events happened: B's events came {way} than expected, "
    "while the rates at the horizon differ by {delta:.3f}"
)


def _correct(rows: list[dict[str, Any]], q: float, method: str, kinds: Mapping[str, str]) -> None:
    """The one pass over every row: Benjamini-Hochberg's ``q`` (the flag), Holm's ``q_holm`` and
    whether the row counts for the verdict, its direction, its verdict word, and the
    log-rank timing note on a flagged row whose horizon difference is 0 or the other way."""
    if not rows:
        return
    p = np.array([r["p"] for r in rows], dtype=np.float64)
    for r, flag_q, verdict_q in zip(rows, bh(p, q), holm(p, q), strict=True):
        r["q"], r["q_holm"], r["holm"] = float(flag_q), float(verdict_q), bool(verdict_q < q)
        r["direction"] = _direction(flag_q < q, r["_signed"])
        r["verdict"] = _verdict_word(r["direction"], kinds.get(r["event"]))
        timing = method == "logrank_bh" and r["direction"] != _verdict.UNCHANGED
        if timing and (r["delta"] == 0 or (r["delta"] > 0) != (r["_signed"] > 0)):
            way = "sooner" if r["_signed"] > 0 else "later"
            r["direction_note"] = _TIMING_NOTE.format(way=way, delta=r["delta"])


def _cells_frame(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    cells = pd.DataFrame.from_records(
        [{c: r.get(c) for c in CELLS_COLUMNS} for r in records], columns=list(CELLS_COLUMNS)
    )
    _objects(cells, records)
    return cells


# ---------- per-cell tests ----------


def _fisher(ea: int, na: int, eb: int, nb: int) -> tuple[float, float]:
    res = stats.fisher_exact([[ea, na - ea], [eb, nb - eb]], alternative="two-sided")
    return float(res[0]), float(res[1])


def _discordant(
    cell_a: pd.DataFrame, cell_b: pd.DataFrame, config_hash: str
) -> tuple[int, int, int]:
    """``(b, c, pairs)``: ``b`` observed in a only, ``c`` in b only, over the joined pairs.

    Split out of ``_mcnemar`` so the paired interval on the delta can reach the same three
    numbers the test was computed from. An unmatched replicate is dropped by the inner join rather
    than mispaired, and the duplicate guard is here because it is a fact about pairing, not about
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
    #: The two runs' seed identity: same ``run_salt`` and the same stored ``seed`` on every row
    #: this comparison matched (``_seed_identity``). A fact about the runs, never about the test.
    seed_identity_match: bool
    #: The identity held and the requested method discarded it. Not defaulted: a hand-built
    #: result that could omit it could claim no unpaired analysis in silence.
    unpaired_analysis: bool
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
        from poisson_prove import _look

        look = _look.active()
        mde = _look.fmt_rate if look else (lambda x: f"{x:.4f}")
        count = _look.fmt_count if look else str
        shown = _look.fmt_hash if look else str
        num = _look.fmt_num if look else str
        cols = list(CELLS_COLUMNS)
        lines = [
            f"Diff of `{self.event}` by {self.method} at q={self.q}: "
            f"n_safer={count(self.n_safer)}, n_worse={count(self.n_worse)}, "
            f"n_unchanged={count(self.n_unchanged)}, "
            f"n_not_comparable={count(self.n_not_comparable)}, max_mde={mde(self.max_mde)}, "
            f"method={self.method}, seed_identity_match={self.seed_identity_match}, "
            f"unpaired_analysis={self.unpaired_analysis}, t_unit={self.t_unit}, "
            f"horizon={num(self.horizon)}, truncated={count(self.truncated)}, "
            f"dropped_a={count(self.dropped_a)}, dropped_b={count(self.dropped_b)}, "
            f"max_mde_unchanged={mde(self.max_mde_unchanged)}, "
            f"max_mde_unchanged_cell={shown(self.max_mde_unchanged_cell)}",
            "",
            "| " + " | ".join(cols) + " |",
            "|" + "|".join("---" for _ in cols) + "|",
        ]
        for row in self.cells.itertuples(index=False):
            values = [_md_cell(getattr(row, col), col) for col in cols]
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


def _md_cell(value: Any, column: str | None = None) -> str:
    """A table cell. With ``column`` named and the command line's look active, the cell takes
    the look's forms for that column; otherwise the library's own."""
    if isinstance(value, Mapping):
        return json.dumps(_native(value), sort_keys=True, separators=(",", ":"))
    if column is not None:
        from poisson_prove import _look

        if _look.active():
            native = _native(value)
            if column in ("config_hash", "max_mde_unchanged_cell"):
                return _look.fmt_hash(native)
            if isinstance(native, bool) or native is None or isinstance(native, str):
                return str(native)
            if column in ("p", "q"):
                return _look.fmt_p(native)
            if column in ("rate_a", "rate_b", "delta", "mde", "ci_lo", "ci_hi", "stat"):
                return _look.fmt_rate(native)
            if isinstance(native, int):
                return _look.fmt_count(native)
            if isinstance(native, float):
                return _look.fmt_num(native)
            return str(native)
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

    a, b are censored frames from poisson_prove.survival.censor(). Manifests are required for
    pairing and unit checks; if omitted, unpaired and unchecked.
    """
    if method not in _METHODS:
        raise DiffError(f"method must be one of {_METHODS}, got {method!r}")
    if not 0.0 < q < 1.0:
        raise DiffError(f"q must be in (0, 1), got {q}")
    _validate_frame(a, "a")
    _validate_frame(b, "b")

    if (
        manifest_a is not None
        and manifest_b is not None
        and manifest_a.declared is not None
        and manifest_b.declared is not None
        and manifest_a.declared.outcomes
        and manifest_b.declared.outcomes
        and manifest_a.declared.outcomes != manifest_b.declared.outcomes
    ):
        raise DeclaredSetMismatch(
            "the runs declare different outcome sets: a declares "
            f"{', '.join(manifest_a.declared.outcomes)}; b declares "
            f"{', '.join(manifest_b.declared.outcomes)}"
        )
    pairable, t_unit = _pairing(method, manifest_a, manifest_b)

    horizon = min(_frame_horizon(a, "a"), _frame_horizon(b, "b"))
    a_t, truncated_a = _truncate(a, horizon)
    b_t, truncated_b = _truncate(b, horizon)

    hashes_a = set(a_t["config_hash"].astype(str))
    hashes_b = set(b_t["config_hash"].astype(str))
    common = sorted(hashes_a & hashes_b)
    dropped_a = len(hashes_a - hashes_b)
    dropped_b = len(hashes_b - hashes_a)

    # After ``common`` and before the first test: the seed check needs the matched rows, and the
    # warning it raises names their count.
    seed_identity_match, unpaired_analysis = _seed_identity(
        method, pairable, a_t, b_t, common,
        manifest_a.run_salt if manifest_a is not None else None,
    )

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
        delta, signed, pairs = rate_b - rate_a, rate_b - rate_a, None
        only_a = only_b = None
        if method == "fisher_bh":
            statistic, p = _fisher(events_a, n_a, events_b, n_b)
        elif method == "mcnemar_bh":
            statistic, p = _mcnemar(cell_a, cell_b, h)
            # The paired test's change is the matched pairs' difference.
            only_a, only_b, pairs = _discordant(cell_a, cell_b, h)
            delta = signed = (only_b - only_a) / pairs if pairs else 0.0
        else:
            t_a = cell_a["t"].to_numpy(dtype=np.float64)
            t_b = cell_b["t"].to_numpy(dtype=np.float64)
            statistic, p = _logrank(t_a, o_a, t_b, o_b)
            signed = _logrank_signed(t_a, o_a, t_b, o_b)
        mde, mde_note = _single_event_limit(events_a, n_a, n_b, q, power)
        rows.append(
            {
                "event": event,
                "config_hash": h,
                "config": cell_a["config"].iloc[0],
                "n_a": n_a,
                "n_b": n_b,
                "events_a": events_a,
                "events_b": events_b,
                "rate_a": float(rate_a),
                "rate_b": float(rate_b),
                "delta": float(delta) + 0.0,
                "stat": float(statistic),
                "p": float(p),
                "verdict": "unchanged",
                "mde": mde,
                "pairs": pairs,
                "n01": only_b,
                "n10": only_a,
                "mde_note": mde_note,
                "_signed": signed,
            }
        )

    # The single-event result keeps its first record, its event read as a failure (a
    # rise worse, a fall safer); no verb prints it.
    _correct(rows, q, method, {event: "failure"})
    cells = _cells_frame(rows)

    n_safer = int((cells["verdict"] == "safer").sum())
    n_worse = int((cells["verdict"] == "worse").sum())
    n_unchanged = int(len(cells)) - n_safer - n_worse
    max_mde = float(cells["mde"].max()) if rows else 0.0
    max_mde_unchanged, max_mde_unchanged_cell = _unchanged_mde(cells)

    return DiffResult(
        cells=cells,
        method=method,
        seed_identity_match=seed_identity_match,
        unpaired_analysis=unpaired_analysis,
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
    if math.isnan(top):
        return math.nan, None
    hits = unchanged.loc[unchanged["mde"] == top, "config_hash"]
    return top, str(hits.iloc[0])


# ---------- multi-event ----------

_RAW_REQUIRED = ("config_hash", "config", "replicate_index", "outcome", "t", "horizon")
_MAX_EVENTS = 6
_TRADES_COLUMNS = ("config_hash", "config", "safer_events", "worse_events")
_MULTI_SUMMARY_FIELDS = (
    "method",
    "seed_identity_match",
    "unpaired_analysis",
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
    ``rate_a`` / ``rate_b`` are Aalen-Johansen cumulative incidence at the horizon.

    ``kind`` is the event's kind when the command line or the runs gave one; ``n_safer``
    and ``n_worse`` are counts then and None otherwise, while ``n_higher`` and ``n_lower`` count
    the flagged rows either way. ``n_holm_higher`` and ``n_holm_lower`` count the rows that count
    for the verdict; the last three are the design facts when a condition cannot be flagged
    alone."""

    event: str
    cells: pd.DataFrame
    n_safer: int | None
    n_worse: int | None
    n_unchanged: int
    max_mde: float
    max_mde_unchanged: float
    max_mde_unchanged_cell: str | None
    cause_specific: bool
    kind: str | None = None
    n_higher: int | None = None
    n_lower: int | None = None
    n_holm_higher: int = 0
    n_holm_lower: int = 0
    n_unflaggable: int = 0
    together_needed: int | None = None
    replicates_for_lone_flag: int | None = None

    def __post_init__(self) -> None:
        # A result built by hand carries no direction counts; they are read from its cells.
        if self.n_higher is None or self.n_lower is None:
            records = self.cells.to_dict(orient="records")
            directions = [_direction_of_record(r, self.kind) for r in records]
            object.__setattr__(self, "n_higher", directions.count(_verdict.HIGHER))
            object.__setattr__(self, "n_lower", directions.count(_verdict.LOWER))

    def words(self) -> tuple[str, str]:
        """The event's two words for a significant change, the one for a rise first:
        ``worse``/``safer`` for a failure, ``safer``/``worse`` for a success, ``higher``/``lower``
        when the kind is not known."""
        if self.kind is None:
            return _verdict.HIGHER, _verdict.LOWER
        return (_verdict.judged(_verdict.HIGHER, self.kind),
                _verdict.judged(_verdict.LOWER, self.kind))

    def counts(self) -> tuple[tuple[str, int], tuple[str, int]]:
        """The event's flagged rows in its own words, the change for the worse first:
        ``(("worse", n), ("safer", n))`` with a kind, ``(("higher", n), ("lower", n))`` without."""
        if self.kind is None:
            higher, lower = int(self.n_higher or 0), int(self.n_lower or 0)
            return (_verdict.HIGHER, higher), (_verdict.LOWER, lower)
        return ("worse", int(self.n_worse or 0)), ("safer", int(self.n_safer or 0))

    def records(self) -> list[dict[str, Any]]:
        """The cells as JSON-ready records: every number native, every NaN None, the direction
        filled in, each arm's share with its Wilson interval at its level, and whether a
        share differs from its rate, which no store 0.1.0 writes can make true."""
        cached: list[dict[str, Any]] | None = self.__dict__.get("_records")
        if cached is None:
            cached = self._build_records()
            # Every surface reads the same records several times over; they are built once, and
            # each caller gets its own copy, down to the share and config mappings in a cell.
            object.__setattr__(self, "_records", cached)
        return [
            {key: dict(value) if isinstance(value, dict) else value for key, value in cell.items()}
            for cell in cached
        ]

    def _build_records(self) -> list[dict[str, Any]]:
        from poisson_prove.stats import share

        out = []
        for record in self.cells.to_dict(orient="records"):
            cell = {col: _none_if_nan(_native(value)) for col, value in record.items()}
            cell["direction"] = _direction_of_record(cell, self.kind)
            cell["verdict"] = _verdict_word(cell["direction"], self.kind)
            for arm in ("a", "b"):
                # An arm with no run (only a frame built by hand has one) has no share.
                events, n = int(cell[f"events_{arm}"]), int(cell[f"n_{arm}"])
                cell[f"share_{arm}"] = share(events, n) if n else None
                gap = abs(events / n - float(cell[f"rate_{arm}"])) if n else 0.0
                cell[f"share_{arm}_differs"] = gap > _CIF_EQUALITY_TOLERANCE
            out.append(cell)
        return out

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {name: _native(getattr(self, name)) for name in _EVENT_SUMMARY_FIELDS}
        out["max_mde"] = _nan_to_none(self.max_mde)
        out["max_mde_unchanged"] = _nan_to_none(self.max_mde_unchanged)
        out["kind"] = self.kind
        out["n_higher"], out["n_lower"] = int(self.n_higher or 0), int(self.n_lower or 0)
        out["n_holm_higher"], out["n_holm_lower"] = int(self.n_holm_higher), int(self.n_holm_lower)
        if self.kind is None:
            out["n_safer"] = out["n_worse"] = out["n_holm_safer"] = out["n_holm_worse"] = None
        else:
            judged = {_verdict.judged(way, self.kind): n for way, n in
                      ((_verdict.HIGHER, self.n_holm_higher), (_verdict.LOWER, self.n_holm_lower))}
            out["n_holm_safer"], out["n_holm_worse"] = int(judged["safer"]), int(judged["worse"])
        out["n_unflaggable"] = int(self.n_unflaggable)
        out["together_needed"] = self.together_needed
        out["replicates_for_lone_flag"] = self.replicates_for_lone_flag
        out["cells"] = self.records()
        return out


@dataclass(frozen=True, eq=False)
class MultiDiffResult:
    events: tuple[str, ...]
    by_event: Mapping[str, EventDiff]
    method: Method
    #: As ``DiffResult``'s, over the same predicate and the same two entry points.
    seed_identity_match: bool
    unpaired_analysis: bool
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
    # The interval on the delta. All six defaulted: the report's tests build this result by
    # hand from keywords, and an
    # undefaulted field breaks every one of them. ``n_rejected`` is the family's BH rejection
    # count -- the single derivation of R -- and ``alpha_star`` is q * R / n_tests;
    # both are carried so ``cli.py`` can print the arithmetic without doing any of it.
    intervals: pd.DataFrame | None = None
    interval_level: float | None = None
    alpha_star: float | None = None
    n_rejected: int = 0
    n_interval_only: int = 0
    n_verdict_only: int = 0
    # The verdict's facts, defaulted for the same reason. The accepted change the nothing-moved
    # words are asked against and where it came from; the word as ``multi_diff`` decided it over
    # the rows that count (None on a result built by hand, which ``comparison_verdict`` decides
    # from its counts); the verdict limit; the rows flagged that do not count; the runs whose
    # tests' error rates do not hold; the conditions whose errored episodes differ.
    threshold: float = DEFAULT_THRESHOLD
    threshold_source: str = "default"
    word: str | None = None
    verdict_limit: float | None = None
    n_flagged_only: int = 0
    peeking: tuple[Mapping[str, Any], ...] = ()
    errors_differ: tuple[Mapping[str, Any], ...] = ()
    #: The fragility search, run the first time the fragility is read, so a caller that
    #: reads only the word never pays for it.
    fragility_search: Callable[[], _verdict.Fragility] | None = field(default=None, repr=False)

    def __getstate__(self) -> dict[str, Any]:
        """The state a pickle keeps: the fragility searched first, so the copy carries the
        answer and not the search."""
        state = dict(self.__dict__)
        state["_fragility"] = self._fragility
        state["fragility_search"] = None
        return state

    @cached_property
    def _fragility(self) -> _verdict.Fragility:
        if self.fragility_search is None:
            return _verdict.Fragility(None, (), "not searched", False)
        return self.fragility_search()

    @property
    def fragility(self) -> int | None:
        """The fewest stored outcomes whose flipping would change the word; None with a note
        when no set of flips does."""
        return self._fragility.value

    @property
    def fragility_flips(self) -> tuple[Mapping[str, Any], ...]:
        return self._fragility.flips

    @property
    def fragility_note(self) -> str | None:
        return self._fragility.note

    @property
    def fragility_exact(self) -> bool:
        """True with one event under Fisher or the paired test: the search within each
        row is then exhaustive, and across rows it covers four ways the word can change (a
        direction appears, the step-down goes further, a direction disappears, the nothing-moved
        question switches). Not a proof that no smaller set exists outside those four."""
        return self._fragility.exact

    @property
    def agreement(self) -> str:
        """The digest a tree grown beside this comparison carries: what a renderer holds the
        tree it is given against."""
        from poisson_prove.tree import agreement_digest

        return agreement_digest(self)

    def all_kinds_known(self) -> bool:
        return all(self.by_event[e].kind is not None for e in self.events)

    def comparison_verdict(self) -> str:
        """The comparison's word: ``worse``/``safer`` words when every event's kind is known,
        direction words when one is not, read over the rows that count."""
        if self.word is not None:
            return self.word
        # A result built by hand: its flagged rows, and its largest limit among the conditions
        # that did not move, a condition with none counting above every threshold.
        known = self.all_kinds_known()
        ways: list[str] = []
        for ev in self.by_event.values():
            if known:
                ways += [way for way, n in ev.counts() if n]
            else:
                moved = ((_verdict.HIGHER, ev.n_higher), (_verdict.LOWER, ev.n_lower))
                ways += [way for way, n in moved if n]
        unread = any(
            ev.n_unchanged and math.isnan(ev.max_mde_unchanged) for ev in self.by_event.values()
        )
        tops = [ev.max_mde_unchanged for ev in self.by_event.values()]
        limits = [top for top in tops if not math.isnan(top)]
        could = not unread and (not limits or max(limits) <= self.threshold)
        return _verdict.word_of(ways, known, could)

    def _ordered_events(self) -> list[str]:
        """Worst first: by the count of the change for the worse (a rise, without a kind), then
        the other way's, then the name."""
        def key(e: str) -> tuple[int, int, str]:
            (_, up), (_, down) = self.by_event[e].counts()
            return -up, -down, e

        return sorted(self.events, key=key)

    def _method_label(self) -> str:
        # Log-rank tests the cause-specific hazard, and says so wherever it is named.
        if self.method == "logrank_bh":
            return f"{self.method} (cause-specific hazard)"
        return self.method

    def headline(self) -> str:
        """Every event, worst first, then the method line. Never a causal claim."""
        parts = []
        for e in self._ordered_events():
            (up, n_up), (down, n_down) = self.by_event[e].counts()
            parts.append(f"{e}: {n_down} {down}, {n_up} {up}")
        # The headline states the *requested method's* pairing and never the runs'
        # provenance. A reader reading about the analysis reads a fact about the analysis; the
        # runs' seed identity is its own field, and ``unpaired_analysis`` beside it says the
        # identity was there and the request discarded it.
        pairing = "paired" if self.method in _PAIRED_METHODS else "unpaired"
        return (
            " · ".join(parts)
            + f"\n(aalen_johansen + {self._method_label()}, BH q<{self.q} over "
            f"{self.n_tests} tests, {pairing})"
        )

    def complementary_events(self) -> tuple[str, ...] | None:
        """The two events' names, in ``events`` order, when they are exact complements: two events,
        the same cells in both frames, the same ``n_a`` and ``n_b`` per cell, and in every cell and
        both arms ``events(e1) + events(e2) == n``. Integers throughout; no rate, no tolerance."""
        if len(self.events) != 2:
            return None
        first, second = (self.by_event[e].cells for e in self.events)
        hashes = [str(h) for h in first["config_hash"]]
        if sorted(hashes) != sorted(str(h) for h in second["config_hash"]):
            return None
        a = first.set_index(first["config_hash"].astype(str))
        b = second.set_index(second["config_hash"].astype(str))
        for h in hashes:
            n_a, n_b = int(a.at[h, "n_a"]), int(a.at[h, "n_b"])
            if n_a != int(b.at[h, "n_a"]) or n_b != int(b.at[h, "n_b"]):
                return None
            if int(a.at[h, "events_a"]) + int(b.at[h, "events_a"]) != n_a:
                return None
            if int(a.at[h, "events_b"]) + int(b.at[h, "events_b"]) != n_b:
                return None
        return tuple(self.events)

    def trade_line(self) -> str | None:
        """None when ``trades`` is empty; otherwise a count of co-occurrence, not a cause. When the
        two events are exact complements the trade is guaranteed and the line says so instead.
        ``trades`` keeps an event that fell in its first slot and one that rose in its second
        whatever the kinds; a success's slots are the other way about, and the line says which
        way each moved."""
        if len(self.trades) == 0:
            return None
        pairs: dict[tuple[str, str], int] = {}
        for row in self.trades.itertuples(index=False):
            for safer in row.safer_events:
                for worse in row.worse_events:
                    pairs[(safer, worse)] = pairs.get((safer, worse), 0) + 1
        (safer, worse), _ = min(pairs.items(), key=lambda kv: (-kv[1], kv[0]))
        n = len(self.trades)
        fell = "rose" if self.by_event[safer].kind == "success" else "fell"
        rose = "fell" if self.by_event[worse].kind == "success" else "rose"
        complement = self.complementary_events()
        if complement is not None:
            e1, e2 = complement
            cells = int(len(self.by_event[e1].cells))
            return (
                f"{e1} and {e2} are complements here: in all {cells} conditions every trial "
                "recorded exactly one of the two, so each rate is one minus the other and each "
                f"change is the other's with its sign flipped. The {n} conditions where {worse} "
                f"rose are the {n} where {safer} fell: one finding, reported twice. Naming one of "
                "the two shows it once."
            )
        return f"Trade: {safer} {fell} in {n} {'cell' if n == 1 else 'cells'} where {worse} {rose}."

    def to_markdown(self) -> str:
        from poisson_prove import _facts, _look
        from poisson_prove.stats import WILSON_LEVEL, level_label, wilson

        look = _look.active()
        mde = _look.fmt_rate if look else (lambda x: f"{x:.4f}")
        count = _look.fmt_count if look else str
        shown = _look.fmt_hash if look else str
        num = _look.fmt_num if look else str
        lines: list[str] = []
        if self.inferred and self.non_event is None:
            lines.append(
                f"inferred: no event was given, so the event set is {', '.join(self.events)}, "
                "the failures and successes the runs declared"
            )
        elif self.inferred:
            lines.append(
                f"inferred: no event was given, so the event set is {', '.join(self.events)}; "
                f"the non-event is {self.non_event}, the most frequent outcome"
            )
        lines.extend(self.headline().splitlines())
        trade = self.trade_line()
        if trade is not None:
            lines.append(trade)
        lines.append(
            f"method={self._method_label()}, "
            f"seed_identity_match={self.seed_identity_match}, "
            f"unpaired_analysis={self.unpaired_analysis}, q={self.q}, "
            f"t_unit={self.t_unit}, horizon={num(self.horizon)}, n_tests={count(self.n_tests)}, "
            f"n_not_comparable={count(self.n_not_comparable)}, dropped_a={count(self.dropped_a)}, "
            f"dropped_b={count(self.dropped_b)}, truncated={count(self.truncated)}"
        )
        # The cell table: each arm's share with its Wilson interval beside the rates, and
        # the interval on the change beside the change, each labelled with its level.
        share_label = level_label(WILSON_LEVEL)
        change = "change"
        if self.interval_level is not None:
            level = level_label(self.interval_level)
            change = f"change [{level}, {_facts.interval_method(self.method)}]"
        head = [
            "config_hash", "config", "n_a", "n_b", "events_a", "events_b", "rate_a", "rate_b",
            f"share_a [{share_label}]", f"share_b [{share_label}]", "delta", change, "stat", "p",
            "q", "verdict", "mde",
        ]
        for e in self._ordered_events():
            ev = self.by_event[e]
            counts = ", ".join(f"n_{word}={count(n)}" for word, n in reversed(ev.counts()))
            lines.extend(
                [
                    "",
                    f"## {e}: {counts}, "
                    f"n_unchanged={count(ev.n_unchanged)}, max_mde={mde(ev.max_mde)}, "
                    f"max_mde_unchanged={mde(ev.max_mde_unchanged)}, "
                    f"max_mde_unchanged_cell={shown(ev.max_mde_unchanged_cell)}",
                    "",
                    "| " + " | ".join(head) + " |",
                    "|" + "|".join("---" for _ in head) + "|",
                ]
            )
            for record in ev.records():
                values = [_md_cell(record[col], col) for col in head[:8]]
                for arm in ("a", "b"):
                    k, n = int(record[f"events_{arm}"]), int(record[f"n_{arm}"])
                    if not n:
                        values.append("none")
                        continue
                    interval = wilson(k, n)
                    mark = " *" if record[f"share_{arm}_differs"] else ""
                    values.append(f"{k / n:.3f} [{interval.lo:.3f}, {interval.hi:.3f}]{mark}")
                values.append(_md_cell(record["delta"], "delta"))
                lo, hi = record.get("ci_lo"), record.get("ci_hi")
                interval_text = "censored" if lo is None or hi is None else f"[{lo:.3f}, {hi:.3f}]"
                values.append(interval_text)
                values += [_md_cell(record[col], col) for col in ("stat", "p", "q")]
                values.append(str(record["verdict"]))
                limit = _facts.limit_text(record)
                values.append(f"{limit} (timing)" if record.get("direction_note") else limit)
                lines.append("| " + " | ".join(values) + " |")
            lines.append("")
            lines.append(_facts.shares_caption(e, WILSON_LEVEL))
            lines.append(_facts.limits_caption(_facts.power_of(self)))
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
                    f"| {shown(row.config_hash)} | {_md_cell(row.config)} | "
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
        out["interval_rule"] = self.interval_rule()
        out["alpha_star"] = self.alpha_star
        out["n_rejected"] = self.n_rejected
        out["n_interval_only"] = self.n_interval_only
        out["n_verdict_only"] = self.n_verdict_only
        out["threshold"] = self.threshold
        out["threshold_source"] = self.threshold_source
        out["comparison_verdict"] = self.comparison_verdict()
        out["flag_rule"] = "benjamini-hochberg"
        out["verdict_rule"] = "holm"
        out["n_flagged_only"] = int(self.n_flagged_only)
        out["verdict_limit"] = self.verdict_limit
        out["fragility"] = self.fragility
        out["fragility_flips"] = [dict(flip) for flip in self.fragility_flips]
        out["fragility_note"] = self.fragility_note
        out["fragility_exact"] = self.fragility_exact
        out["peeking"] = [dict(entry) for entry in self.peeking]
        out["errors_differ"] = [
            {k: _native(v) for k, v in entry.items()} for entry in self.errors_differ
        ]
        out["headline"] = self.headline()
        out["trade_line"] = self.trade_line()
        return out

    def interval_rule(self) -> str | None:
        """The interval's level is the false-coverage level (Benjamini-Yekutieli) when
        anything is flagged and the simultaneous level (Bonferroni) when nothing is."""
        if self.interval_level is None:
            return None
        return "benjamini-yekutieli" if self.n_rejected else "bonferroni"

    def check(self, fail_on: str = "worse") -> bool:
        """True if the diff passes, read over the rows that count for the verdict.
        'worse': no condition worse in any event, which needs every event's kind (refused with
        ``DiffError`` otherwise, as the command line refuses it); 'any': nothing either way;
        'higher' / 'lower': no event's rate rose / fell."""
        if fail_on not in ("worse", "any", "higher", "lower"):
            raise DiffError(f"fail_on must be 'worse', 'any', 'higher' or 'lower', got {fail_on!r}")
        unknown = [e for e in self.events if self.by_event[e].kind is None]
        if fail_on == "worse" and unknown:
            raise DiffError(
                f"cannot gate on worse: no kind is known for {', '.join(unknown)}; gate on "
                "'higher', 'lower' or 'any', or give each event its kind"
            )
        for ev in self.by_event.values():
            for record in ev.cells.to_dict(orient="records"):
                direction = _direction_of_record(record, ev.kind)
                counted = record.get("holm")
                # A frame built by hand carries no Holm column; its flagged rows count.
                if direction == _verdict.UNCHANGED or (counted is not None and not counted):
                    continue
                if fail_on == "any" or fail_on == direction:
                    return False
                if fail_on == "worse" and _verdict.judged(direction, ev.kind) == "worse":
                    return False
        return True


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
    """(manifests_pairable, t_unit) with the manifest guards, raised before any frame work.

    The manifest half of seed identity: both manifests present and carrying the same
    ``run_salt``. If ``seed_derivation`` and ``treatment_axes`` are added to ``RunManifest``
    they join this clause and nowhere else; the key name does not move then and the predicate
    gains two comparisons.

    The rest of the predicate -- the stored seed on every matched row -- is ``_seed_identity``'s,
    because it cannot be answered before the frames are filtered and matched. So this function
    raises the two manifest-level refusals and no longer raises the unpaired-analysis warning:
    the warning now states a matched-row count, which does not exist here.
    """
    if manifest_a is not None and manifest_b is not None:
        if manifest_a.t_unit != manifest_b.t_unit:
            raise UnitMismatch(
                f"t_unit differs: {manifest_a.t_unit!r} (a) vs {manifest_b.t_unit!r} (b)"
            )
        pairable = manifest_a.run_salt == manifest_b.run_salt
    else:
        pairable = False
    if method in _PAIRED_METHODS and not pairable:
        if manifest_a is None or manifest_b is None:
            raise NotPairable("mcnemar_bh needs both manifests to establish pairing")
        raise NotPairable(
            f"mcnemar_bh needs matching run_salt; got {manifest_a.run_salt!r} vs "
            f"{manifest_b.run_salt!r}"
        )
    if manifest_a is not None:
        return pairable, manifest_a.t_unit
    if manifest_b is not None:
        return pairable, manifest_b.t_unit
    return pairable, "unknown"


def _seed_identity(
    method: str,
    pairable: bool,
    a: pd.DataFrame,
    b: pd.DataFrame,
    common: Sequence[str],
    salt: str | None,
) -> tuple[bool, bool]:
    """(seed_identity_match, unpaired_analysis) over the rows the tests read.

    Matching salts once claimed a counterpart at the same ``(config_hash,
    replicate_index)``; nothing checked whether the two arms stored the same seed there, so a pair
    whose arms consumed different seeds reported ``paired`` and ran ``mcnemar_bh`` on rows that
    were not counterparts. The claim is now measured: the analysed frames are joined on
    ``(config_hash, replicate_index)`` within ``common`` and every matched pair's stored ``seed``
    is compared.

    **A missing ``seed`` column is a declined claim, never a skipped check**: the
    predicate is false, ``mcnemar_bh`` -- the one method that needs the claim -- refuses, and the
    two unpaired methods still run, which covers every hand-built fixture in the comparison and
    report tests.

    **The statistic never follows the answer**. For ``fisher_bh`` and
    ``logrank_bh`` a false predicate is neither a refusal nor a warning: the numbers do not depend
    on it and the fact reaches every artifact as ``seed_identity_match``. The warning is raised
    only when the identity holds and the requested method discards it, which is
    ``unpaired_analysis``.

    A key stored twice in one arm is matched twice. A stored run cannot produce one -- resume is
    presence-keyed -- and a hand-built frame can; it is counted, not refused.
    """
    if not pairable:
        return False, False
    for frame, label in ((a, "a"), (b, "b")):
        if "seed" not in frame.columns:
            if method in _PAIRED_METHODS:
                raise NotPairable(
                    "mcnemar_bh needs the stored seed to establish pairing; "
                    f"frame {label} has no seed column"
                )
            return False, False
    keys = {str(h) for h in common}
    columns = ["config_hash", "replicate_index", "seed"]
    left = a.loc[a["config_hash"].astype(str).isin(keys), columns].copy()
    right = b.loc[b["config_hash"].astype(str).isin(keys), columns].copy()
    left["config_hash"] = left["config_hash"].astype(str)
    right["config_hash"] = right["config_hash"].astype(str)
    matched = left.merge(right, on=["config_hash", "replicate_index"], suffixes=("_a", "_b"))
    n_matched = int(len(matched))
    if n_matched == 0:
        if method in _PAIRED_METHODS:
            raise NotPairable(
                "mcnemar_bh needs matched rows; no (config_hash, replicate_index) is present "
                "in both runs"
            )
        return False, False
    differ = int((matched["seed_a"] != matched["seed_b"]).sum())
    if differ:
        if method in _PAIRED_METHODS:
            raise NotPairable(
                f"mcnemar_bh needs matched rows to share their seed; {differ} of {n_matched} "
                "rows matched at the same (config_hash, replicate_index) carry different seeds"
            )
        return False, False
    if method in _PAIRED_METHODS:
        return True, False
    # Never a switch here. A method the caller named is the method that runs; the one default
    # that follows how the runs were produced is chosen before any frame is read, from the
    # manifests alone (``method=None``), and every surface names the test it ran. This says
    # what the named method discarded and what the alternative is spelled; the choice stays the
    # caller's. No claim about power: that depends on how far the two arms agree episode by
    # episode, which is a fact about the data and not about the salt.
    #
    # The earlier warning could not carry a count -- it was raised before any cell existed -- and
    # said instead that which cells were matched "is not settled here". Now they are: this runs
    # after matching, so the count is the subject of the claim and ``coverage`` carries the rest.
    warnings.warn(
        f"{method} compares two runs that share their seeds as independent samples: both "
        f"manifests carry run_salt {salt!r}, and each of the {n_matched} rows this comparison "
        "matched across its cells stores the same seed in both arms at the same (config_hash, "
        "replicate_index); the cells one arm ran and the other did not are in coverage. Pass "
        "method='mcnemar_bh' to test that correspondence; whether it buys power depends on how "
        "far the two arms agree episode by episode.",
        UnpairedAnalysis,
        # 3, not survival.py's 2: this is one frame deeper than the public function, so 3 lands
        # on the caller of diff/multi_diff -- the line the reader has to change. Unchanged from
        # ``_pairing``, which sat at the same depth.
        stacklevel=3,
    )
    return True, True


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
    """The five rules, in order. Presence is decided before errors: a cell A ran and
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
        frame[col] = pd.Series([r[col] for r in records], index=frame.index, dtype=object)
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

    Called after the BH pass, because the level cannot be known before ``R``. ``n_rejected`` is
    that ``R``: the count of hypotheses BH rejected over the **flat family** ``multi_diff`` runs,
    one pass across every cell and every event. It arrives as an argument rather than being
    recounted here, so it has exactly one derivation.

    Every row has an interval, at ``1 - q max(R, 1) / M``: the
    false-coverage level when anything is flagged, the simultaneous (Bonferroni) level when
    nothing is. Only a comparison of no rows has none.
    """
    if n_tests == 0:
        return None, None, None, 0, 0
    alpha_star = q * max(n_rejected, 1) / n_tests
    interval_level = 1.0 - alpha_star
    wanted = _BASIS_BY_METHOD[method]
    records: list[dict[str, Any]] = []
    n_interval_only = 0
    n_verdict_only = 0
    for row in rows:
        # Checked in both arms. A cell that passes in one arm and fails in the other is censored.
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
            # the interval and the test are expected to disagree in known directions, none of them
            # a bug, and log-rank is expected to produce both.
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


# ---------- what a comparison carries beyond its tests ----------

#: The interval each test's rows carry on their change.
_CI_METHODS: Mapping[str, str] = {
    "fisher_bh": "miettinen-nurminen",
    "logrank_bh": "miettinen-nurminen",
    "mcnemar_bh": "tango",
}


@dataclass(frozen=True)
class _Arms:
    """What a row's tests read beyond its counts, per arm: each run's time and outcome at the
    common horizon, whether it had the row's event, and its replicate index."""

    t: tuple[NDArray[np.float64], NDArray[np.float64]]
    outcomes: tuple[NDArray[Any], NDArray[Any]]
    had: tuple[NDArray[np.bool_], NDArray[np.bool_]]
    reps: tuple[NDArray[Any], NDArray[Any]]

    def pairs(self) -> dict[str, list[int]]:
        """The matched pairs by replicate index: only A had the event, only B, both, neither."""
        had_a = dict(zip(self.reps[0].tolist(), self.had[0].tolist(), strict=True))
        had_b = dict(zip(self.reps[1].tolist(), self.had[1].tolist(), strict=True))
        out: dict[str, list[int]] = {"only_a": [], "only_b": [], "both": [], "neither": []}
        for rep in sorted(set(had_a) & set(had_b)):
            in_a, in_b = had_a[rep], had_b[rep]
            kind = "only_a" if in_a else "only_b" if in_b else "neither"
            out["both" if in_a and in_b else kind].append(int(rep))
        return out

    def outside(self, compared: Sequence[str]) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
        """The runs of each arm that ended in an outcome outside the compared events: the only
        runs a flip may make end in the event."""
        def of(outcomes: NDArray[Any]) -> NDArray[np.bool_]:
            ended = [o is not None and str(o) not in compared for o in outcomes]
            return np.array(ended, dtype=bool)

        return of(self.outcomes[0]), of(self.outcomes[1])


def _require_one_case(a: pd.DataFrame, b: pd.DataFrame, common: Sequence[str]) -> None:
    """Refuse a compared condition whose episodes, both runs together, report more than
    one case id. The id is read from the store's ``case_id`` column and never from ``meta``;
    an episode that reports none is not counted."""
    seen: dict[str, set[str]] = {}
    configs: dict[str, Any] = {}
    wanted = set(common)
    for frame in (a, b):
        if "case_id" not in frame.columns:
            continue
        columns = (frame["config_hash"].astype(str), frame["config"], frame["case_id"])
        for h, config, case in zip(*columns, strict=True):
            if h in wanted and isinstance(case, str) and case:
                seen.setdefault(h, set()).add(case)
                configs.setdefault(h, config)
    for h in sorted(seen):
        if len(seen[h]) > 1:
            cases = sorted(seen[h])
            shown = ", ".join(cases[:3]) + (", ..." if len(cases) > 3 else "")
            condition = ", ".join(f"{k} {v}" for k, v in sorted(dict(configs[h]).items()))
            raise MixedCases(
                f"condition {condition} ran {len(cases)} cases ({shown}); each case must be its "
                "own sweep axis"
            )


def _errors_differ(coverage: pd.DataFrame, q: float) -> list[dict[str, Any]]:
    """The compared conditions whose share of errored episodes differs
    between the runs by Fisher's two-sided exact test at ``p < q``, unadjusted, with each run's
    errored and total counts."""
    out = []
    for record in coverage.to_dict(orient="records"):
        if not record["comparable"]:
            continue
        errored_a, rows_a = int(record["no_outcome_a"]), int(record["rows_a"])
        errored_b, rows_b = int(record["no_outcome_b"]), int(record["rows_b"])
        if errored_a == errored_b == 0:
            continue
        p = _fisher(errored_a, rows_a, errored_b, rows_b)[1]
        if p < q:
            out.append({"config_hash": str(record["config_hash"]), "config": record["config"],
                        "errored_a": errored_a, "rows_a": rows_a, "errored_b": errored_b,
                        "rows_b": rows_b, "p": p})
    return out


def _peeking(
    manifest_a: RunManifest | None, manifest_b: RunManifest | None
) -> list[dict[str, Any]]:
    """The runs whose tests' error rates do not hold, because a resume added
    to them after a comparison of them was read, or because they are partial."""
    out = []
    for manifest in (manifest_a, manifest_b):
        if manifest is None:
            continue
        resumes = manifest.environment.get("resumes") or ()
        if any(isinstance(r, Mapping) and r.get("after_comparison") for r in resumes):
            reason = "resumed after a comparison"
        elif manifest.status == "partial":
            reason = "partial"
        else:
            continue
        out.append({"run_id": manifest.run_id, "run_name": manifest.name, "reason": reason})
    return out


def _complements(rows: Sequence[Mapping[str, Any]], method: str) -> dict[tuple[str, str], str]:
    """Under Fisher and the paired test, each row whose condition's runs, in
    both runs, all ended in its event or one other compared event: the two rows' p-values are
    identical, so a lone change moves both. Maps the row to the other event."""
    if method not in ("fisher_bh", "mcnemar_bh"):
        return {}
    by_condition: dict[str, list[str]] = {}
    arms: dict[str, _Arms] = {}
    for r in rows:
        by_condition.setdefault(r["config_hash"], []).append(r["event"])
        arms[r["config_hash"]] = r["_arms"]
    out: dict[tuple[str, str], str] = {}
    for h, events in by_condition.items():
        ended = {o for outcomes in arms[h].outcomes for o in outcomes.tolist()}
        for i, first in enumerate(events):
            for second in events[i + 1 :]:
                if ended <= {first, second}:
                    out[(h, first)], out[(h, second)] = second, first
    return out


def _limits_of(
    r: Mapping[str, Any], method: str, level: float, power: float, horizon: float
) -> _limits.Limits:
    """One row's limits at one level, by its test."""
    arms: _Arms = r["_arms"]
    if method == "fisher_bh":
        return _limits.fisher_limits(int(r["events_a"]), int(r["n_a"]), int(r["n_b"]), level, power)
    if method == "mcnemar_bh":
        pairs = arms.pairs()
        matched = sum(len(v) for v in pairs.values())
        events_a = len(pairs["only_a"]) + len(pairs["both"])
        return _limits.paired_limits(events_a, matched, level, power)
    return _limits.logrank_limits(arms.t[0], arms.had[0], int(r["n_b"]), horizon, level, power)


def _set_limits(rows: list[dict[str, Any]], event_set: Sequence[str], *, method: str, q: float,
                power: float, horizon: float) -> list[_limits.Limits]:
    """Every row's limits, written into the row; returns each row's
    limits at the verdict's level ``q / M``, which the nothing-moved question reads."""
    m = len(rows)
    moves_with = _complements(rows, method)
    verdict_level = q / m if m else q
    out = []
    for r in rows:
        partner = moves_with.get((r["config_hash"], r["event"]))
        level = verdict_level * (2.0 if partner is not None else 1.0)
        limits = _limits_of(r, method, level, power, horizon)
        at_verdict = (
            limits if partner is None else _limits_of(r, method, verdict_level, power, horizon)
        )
        mde, note = limits.one_number()
        r.update({
            "mde": math.nan if mde is None else mde,
            "mde_note": note,
            "mde_rise": limits.rise.value,
            "mde_fall": limits.fall.value,
            "mde_rise_note": limits.rise.note,
            "mde_fall_note": limits.fall.note,
            "mde_test": limits.test,
            "mde_basis": limits.basis,
            "mde_level": level,
            "mde_family": m,
            "mde_power": power,
            "mde_anchor": "observed baseline",
            "mde_hr": limits.rise.hazard_ratio,
            "p_min": float(limits.p_min),
            "flaggable": bool(limits.p_min < level),
            "mde_moves_with": partner,
            "mde_rise_verdict": at_verdict.rise.value,
            "mde_fall_verdict": at_verdict.fall.value,
            "competing_shift": None,
        })
        out.append(at_verdict)
    return out


def _set_competing_shift(rows: list[dict[str, Any]], q: float) -> None:
    """Under log-rank, each row's other outcomes that ended runs in its
    condition (the non-event included) whose share differs between the runs by Fisher's
    two-sided exact test at ``p < q``, unadjusted, sorted by name."""
    for r in rows:
        arms: _Arms = r["_arms"]
        ended = {str(o) for outcomes in arms.outcomes for o in outcomes.tolist() if o is not None}
        shifted = []
        for other in sorted(ended - {r["event"]}):
            count_a = int(np.sum(arms.outcomes[0] == other))
            count_b = int(np.sum(arms.outcomes[1] == other))
            if _fisher(count_a, int(r["n_a"]), count_b, int(r["n_b"]))[1] < q:
                shifted.append(other)
        r["competing_shift"] = shifted


def _event_diff(event: str, rows: Sequence[dict[str, Any]], kind: str | None, method: str, q: float,
                family: int) -> EventDiff:
    """One event's rows as an ``EventDiff``: the cells, the counts each way, the largest limits,
    and the design facts when a condition of it cannot be flagged alone."""
    cells = _cells_frame(rows)
    directions = [r["direction"] for r in rows]
    unchanged = [r for r in rows if r["direction"] == _verdict.UNCHANGED]
    limits = [r["mde"] for r in rows if not math.isnan(r["mde"])]
    quiet = [r for r in unchanged if not math.isnan(r["mde"])]
    max_unchanged = max((r["mde"] for r in quiet), default=math.nan)
    where = next((r["config_hash"] for r in quiet if r["mde"] == max_unchanged), None)
    unflaggable = [r for r in rows if not r["flaggable"]]
    n_higher, n_lower = directions.count(_verdict.HIGHER), directions.count(_verdict.LOWER)
    judged = {
        _verdict.judged(_verdict.HIGHER, kind): n_higher,
        _verdict.judged(_verdict.LOWER, kind): n_lower,
    }
    return EventDiff(
        event=event,
        cells=cells,
        n_safer=None if kind is None else judged["safer"],
        n_worse=None if kind is None else judged["worse"],
        n_unchanged=len(unchanged),
        max_mde=max(limits, default=math.nan),
        max_mde_unchanged=max_unchanged,
        max_mde_unchanged_cell=where,
        cause_specific=method == "logrank_bh",
        kind=kind,
        n_higher=n_higher,
        n_lower=n_lower,
        n_holm_higher=sum(1 for r in rows if r["holm"] and r["direction"] == _verdict.HIGHER),
        n_holm_lower=sum(1 for r in rows if r["holm"] and r["direction"] == _verdict.LOWER),
        n_unflaggable=len(unflaggable),
        together_needed=(_limits.together_needed([r["p_min"] for r in rows], q, family)
                         if unflaggable else None),
        replicates_for_lone_flag=(_limits.replicates_for_lone_flag(rows[0]["mde_test"], q / family)
                                  if unflaggable else None),
    )


def _trades(by_event: Mapping[str, EventDiff], event_set: Sequence[str], common: Sequence[str],
            groups_a: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    """The conditions where one event's flagged row went one way and another's the other: a fall
    (or, with kinds, a change for the better) in the first slot, a rise (for the worse) in the
    second. With no kind such a condition is still recorded, and the comparison reads it as
    ``mixed``, not a trade."""
    verdicts = {
        k: dict(zip(by_event[k].cells["config_hash"], by_event[k].cells["verdict"], strict=True))
        for k in event_set
    }
    records = []
    for h in common:
        better = tuple(k for k in event_set if verdicts[k].get(h) in ("safer", _verdict.LOWER))
        worse = tuple(k for k in event_set if verdicts[k].get(h) in ("worse", _verdict.HIGHER))
        if better and worse:
            records.append({"config_hash": h, "config": groups_a[h]["config"].iloc[0],
                            "safer_events": better, "worse_events": worse})
    trades = pd.DataFrame.from_records(records, columns=list(_TRADES_COLUMNS))
    for col in ("config", "safer_events", "worse_events"):
        trades[col] = trades[col].astype(object)
    return trades


def _fragile_row(
    r: Mapping[str, Any],
    facts: _verdict.RowFacts,
    *,
    method: str,
    events: Sequence[str],
    level: float,
    power: float,
    horizon: float,
) -> _verdict.Row:
    """One row as the fragility search reads it."""
    arms: _Arms = r["_arms"]
    outside = arms.outside(events)
    common = {"facts": facts, "event": r["event"], "config_hash": r["config_hash"]}
    if method == "fisher_bh":
        def reps(arm: int, chosen: NDArray[np.bool_]) -> tuple[int, ...]:
            return tuple(int(x) for x in arms.reps[arm][chosen])

        return _verdict.FisherRow(
            **common, n=(int(r["n_a"]), int(r["n_b"])),
            had=(reps(0, arms.had[0]), reps(1, arms.had[1])),
            spare=(reps(0, outside[0]), reps(1, outside[1])),
            level=level, power=power,
        )
    if method == "mcnemar_bh":
        pairs = arms.pairs()
        spare_a = frozenset(int(x) for x in arms.reps[0][outside[0]])
        spare_b = frozenset(int(x) for x in arms.reps[1][outside[1]])
        return _verdict.PairedRow(
            **common, only_a=tuple(pairs["only_a"]), only_b=tuple(pairs["only_b"]),
            both=tuple(pairs["both"]), neither=tuple(pairs["neither"]),
            spare_a=spare_a, spare_b=spare_b, level=level, power=power,
        )
    return _verdict.LogrankRow(
        facts, event=r["event"], config_hash=r["config_hash"], t=arms.t, had=arms.had,
        spare=outside, reps=(np.asarray(arms.reps[0]), np.asarray(arms.reps[1])),
        horizon=horizon, level=level, power=power,
    )


def multi_diff(
    a: pd.DataFrame,
    b: pd.DataFrame,
    *,
    events: Sequence[str] | None = None,
    method: Method | None = "fisher_bh",
    q: float = 0.05,
    power: float = 0.8,
    manifest_a: RunManifest | None = None,
    manifest_b: RunManifest | None = None,
    kinds: Mapping[str, str] | None = None,
) -> MultiDiffResult:
    """Diff two RAW store frames across several competing events at once.

    ``method=None`` asks for the default test, chosen from the two manifests and never from the
    outcomes: ``mcnemar_bh`` when both carry one ``run_salt`` (the runs were paired at
    sweep time), else ``fisher_bh``. The result's ``method`` names the test that ran.

    a, b are Store.read() frames (not censored); censoring is applied per event internally.
    events=None infers the set with infer_events. Per cell and event the compared quantity
    is the Aalen-Johansen cumulative incidence at the horizon, estimated once per cell over
    every terminal outcome present (the requested events and the non-event alike compete);
    the per-event test statistic treats every other outcome as censoring. One BH family
    covers every (cell, event) pair. Errored rows (null outcome) are excluded from every
    numerator and denominator.

    ``kinds`` gives events' kinds (``failure`` or ``success``) as the command line names them; a
    kind the runs declare is used too, and the two disagreeing is refused (``KindConflict``).
    ``power`` is the power every detection limit is stated at. A condition whose episodes report
    more than one case id is refused (``MixedCases``). Each row's flag is
    Benjamini-Hochberg's, and the comparison's word counts Holm's rows; every row
    carries its limits, its interval on the change and, under log-rank,
    the competing outcomes that shifted; the fragility is searched when first read.
    """
    if method is None:
        paired = (
            manifest_a is not None
            and manifest_b is not None
            and manifest_a.run_salt == manifest_b.run_salt
        )
        method = "mcnemar_bh" if paired else "fisher_bh"
    if method not in _METHODS:
        raise DiffError(f"method must be one of {_METHODS}, got {method!r}")
    if not 0.0 < q < 1.0:
        raise DiffError(f"q must be in (0, 1), got {q}")
    _validate_raw(a, "a")
    _validate_raw(b, "b")
    if (
        manifest_a is not None
        and manifest_b is not None
        and manifest_a.declared is not None
        and manifest_b.declared is not None
        and manifest_a.declared.outcomes
        and manifest_b.declared.outcomes
        and manifest_a.declared.outcomes != manifest_b.declared.outcomes
    ):
        raise DeclaredSetMismatch(
            "the runs declare different outcome sets: a declares "
            f"{', '.join(manifest_a.declared.outcomes)}; b declares "
            f"{', '.join(manifest_b.declared.outcomes)}"
        )
    pairable, t_unit = _pairing(method, manifest_a, manifest_b)

    inferred = events is None
    non_event: str | None = None
    if events is None:
        # The failures and successes the runs declare, when they declare any; otherwise every
        # outcome present but the most frequent.
        event_set = declared_events(manifest_a, manifest_b)
        if not event_set:
            event_set, non_event = infer_events(a, b)
    else:
        event_set = tuple(dict.fromkeys(str(e) for e in events))
        if not event_set:
            raise DiffError("events must name at least one outcome")

    event_kinds = _resolve_kinds(event_set, kinds, manifest_a, manifest_b)
    threshold, threshold_source = _threshold(manifest_a, manifest_b)

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

    # After ``common`` and before the first test, over the analysed frames: truncation rewrites
    # ``t`` and ``outcome`` and never ``seed``, so the check is the same before and after it.
    seed_identity_match, unpaired_analysis = _seed_identity(
        method, pairable, a_t, b_t, common,
        manifest_a.run_salt if manifest_a is not None else None,
    )

    # Coverage is grouped from the RAW frames, not from a_t / b_t: a cell whose every row
    # errored is absent from both valid hash sets, so grouping the filtered frames would lose
    # exactly the holes this answers for.
    coverage = _coverage(a, b, common)
    _require_one_case(a, b, common)
    errors_differ = _errors_differ(coverage, q)

    # The competing set for Aalen-Johansen is every terminal outcome present in either run,
    # not just the events asked for: a row that ended in the non-event is absorbed, not
    # censored, so it must stay out of the risk set for the events being compared. Only
    # rows re-censored by horizon truncation (null outcome) are censored. A requested event
    # outside this set did not occur; its incidence is zero rather than an error.
    competing = competing_set(a_t, b_t)
    if not competing:
        raise DiffError(
            f"every row of both runs lies past the common horizon {horizon:g}; nothing ended "
            "by then, so there is nothing to compare"
        )

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
            delta = signed = float(rate_b - rate_a)
            pairs: int | None = None
            only_a = only_b = None
            if method == "fisher_bh":
                statistic, p = _fisher(events_a, n_a, events_b, n_b)
            elif method == "mcnemar_bh":
                ind_a, ind_b = _indicator_frame(cell_a, o_a), _indicator_frame(cell_b, o_b)
                statistic, p = _mcnemar(ind_a, ind_b, h)
                # The paired test's change is the matched pairs' difference.
                only_a, only_b, pairs = _discordant(ind_a, ind_b, h)
                delta = signed = (only_b - only_a) / pairs if pairs else 0.0
            else:
                statistic, p = _logrank(t_a, o_a, t_b, o_b)
                signed = _logrank_signed(t_a, o_a, t_b, o_b)
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
                    "delta": float(delta) + 0.0,
                    "stat": float(statistic),
                    "p": float(p),
                    "verdict": "unchanged",
                    "pairs": pairs,
                    "n01": only_b,
                    "n10": only_a,
                    "_signed": signed,
                    "_arms": _Arms(
                        t=(t_a, t_b),
                        outcomes=(out_a, out_b),
                        had=(o_a, o_b),
                        reps=(
                            cell_a["replicate_index"].to_numpy(),
                            cell_b["replicate_index"].to_numpy(),
                        ),
                    ),
                }
            )

    m = len(rows)
    _correct(rows, q, method, event_kinds)
    verdict_limits = _set_limits(rows, event_set, method=method, q=q, power=power, horizon=horizon)
    if method == "logrank_bh":
        _set_competing_shift(rows, q)
    facts = [
        _verdict.RowFacts(r["p"], r["_signed"], event_kinds.get(r["event"]), limits)
        for r, limits in zip(rows, verdict_limits, strict=True)
    ]
    decided = _verdict.decide(facts, q, threshold)

    # After the BH pass: the level cannot be known before R. R is read from the rows the BH
    # pass flagged -- the count of hypotheses it rejected, not the safer/worse sum, which drops a
    # rejected cell whose delta is exactly zero. On one real sweep under log-rank those two
    # differed by 196 to 88. Every row carries its interval, flagged or not.
    n_rejected = sum(1 for r in rows if r["q"] < q)
    intervals, interval_level, alpha_star, n_interval_only, n_verdict_only = _build_intervals(
        rows, groups_a, groups_b, method=method, q=q, n_rejected=n_rejected, n_tests=m
    )
    if intervals is not None:
        bounds = {
            (rec["event"], rec["config_hash"]): rec for rec in intervals.to_dict(orient="records")
        }
        for r in rows:
            interval = bounds[(r["event"], r["config_hash"])]
            r["ci_lo"], r["ci_hi"] = interval["ci_lo"], interval["ci_hi"]
            r["ci_level"] = interval_level
            r["ci_method"] = None if interval["ci_lo"] is None else _CI_METHODS[method]

    by_event = {
        k: _event_diff(k, [r for r in rows if r["event"] == k], event_kinds.get(k), method, q, m)
        for k in event_set
    }
    trades = _trades(by_event, event_set, common, groups_a)

    def search() -> _verdict.Fragility:
        candidates = [_fragile_row(r, f, method=method, events=event_set, level=q / m, power=power,
                                   horizon=horizon) for r, f in zip(rows, facts, strict=True)]
        return _verdict.fragility(candidates, q=q, threshold=threshold, events=len(event_set))

    return MultiDiffResult(
        events=event_set,
        by_event=by_event,
        method=method,
        seed_identity_match=seed_identity_match,
        unpaired_analysis=unpaired_analysis,
        q=float(q),
        t_unit=t_unit,
        horizon=float(horizon),
        n_tests=m,
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
        threshold=threshold,
        threshold_source=threshold_source,
        word=decided.word,
        verdict_limit=decided.verdict_limit,
        n_flagged_only=sum(1 for r in rows if r["q"] < q and not r["holm"]),
        peeking=tuple(_peeking(manifest_a, manifest_b)),
        errors_differ=tuple(errors_differ),
        fragility_search=search,
    )


def declared_events(*manifests: RunManifest | None) -> tuple[str, ...]:
    """The events a comparison or report of these runs defaults to: the failures, then the
    successes, each run's ``[declare]`` table names, in that order, each once. Empty when no run
    declares a kind."""
    names: list[str] = []
    for manifest in manifests:
        if manifest is not None and manifest.declared is not None:
            names += [*manifest.declared.failures, *manifest.declared.successes]
    return tuple(dict.fromkeys(names))


def _declared_kinds(manifest: RunManifest | None) -> dict[str, str]:
    """The kinds a run's ``[declare]`` table gave its outcomes."""
    if manifest is None or manifest.declared is None:
        return {}
    kinds = {name: "failure" for name in manifest.declared.failures}
    kinds.update({name: "success" for name in manifest.declared.successes})
    return kinds


def _resolve_kinds(
    events: Sequence[str],
    given: Mapping[str, str] | None,
    manifest_a: RunManifest | None,
    manifest_b: RunManifest | None,
) -> dict[str, str]:
    """Each compared event's kind, the one given (the command line's) else the one either
    run declares; two runs declaring opposite kinds, or a given kind a run contradicts, are
    refused. An event no source names has no kind and reads in direction words."""
    declared_a, declared_b = _declared_kinds(manifest_a), _declared_kinds(manifest_b)
    out: dict[str, str] = {}
    for event in events:
        kind_a, kind_b = declared_a.get(event), declared_b.get(event)
        if kind_a is not None and kind_b is not None and kind_a != kind_b:
            raise KindConflict(
                f'the runs declare "{event}" differently: a as a {kind_a}, b as a {kind_b}'
            )
        declared = kind_a or kind_b
        typed = None if given is None else given.get(event)
        if typed is not None and declared is not None and typed != declared:
            raise KindConflict(
                f'"{event}" was given as a {typed}, and a run declares it a {declared}'
            )
        kind = typed or declared
        if kind is not None:
            out[event] = kind
    return out


def _threshold(manifest_a: RunManifest | None, manifest_b: RunManifest | None) -> tuple[float, str]:
    """The verdict's detection threshold and its source: the ``max_mde_accepted`` both runs recorded
    (``recorded``), the smaller of two different ones (``smaller``), or the default when neither
    recorded one (``default``)."""
    recorded = [
        float(m.environment["max_mde_accepted"])
        for m in (manifest_a, manifest_b)
        if m is not None and m.environment.get("max_mde_accepted") is not None
    ]
    if not recorded:
        return DEFAULT_THRESHOLD, "default"
    return min(recorded), "smaller" if len(set(recorded)) > 1 else "recorded"


# ---------- the interval on the delta ----------


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

    The constrained MLE can be found by a Farrington-Manning cubic or by a one-dimensional
    maximisation along the constrained line. This is the maximisation, because a mistranscribed
    cubic is a silent statistical bug no reviewer catches by reading. Every
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
