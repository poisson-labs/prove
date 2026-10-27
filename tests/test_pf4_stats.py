"""PF4, the statistics: the frozen tests at the library's level (the math suite).

Written from the invariants PF4.1 to PF4.51.
``tests/test_pf4_surfaces.py`` holds what a user reads on a screen or in a file and the contract
tests on the result objects (the code suite); ``tests/test_pf4_calibration.py`` simulates every
claim Prove prints. This file holds the numbers underneath them.

**How each statistic is checked.** Every number is recomputed by code written in this file from
the statistic's own definition, never from Prove's, with an outside library (scipy, statsmodels or
lifelines) wherever one computes the quantity, its arguments taken from that library's
documentation. Where an outside library was found not to compute the quantity as defined, the
test says so and maximises the paper's restricted likelihood here instead (statsmodels 0.15's score
test of a nonzero difference does not match the Miettinen-Nurminen restricted maximum likelihood; the
restricted rates below come from scipy's bounded minimiser, which agrees with Farrington and Manning's
closed form to 1e-7). Property-based tests (Hypothesis) carry the generated
inputs, with the edge cases as explicit examples: empty arms, 0% and 100%, uneven arms both
ways, one condition, ties.

**Readings, named here.**

- ``poisson_prove.stats`` holds ``wilson``, ``WilsonInterval`` and ``WILSON_LEVEL`` (the module's
  other names are PF5's). A refused level raises ``ValueError``.
- The library's cell frames (``EventDiff.cells``) carry every per-condition field as
  columns: ``direction``, ``direction_note``, ``pairs``, ``q_holm``, ``holm``, the limit keys of
  PF4.32 with ``mde_hr``, ``mde_moves_with``, ``mde_rise_verdict`` and ``mde_fall_verdict``,
  ``competing_shift``, and the interval's ``ci_lo``, ``ci_hi``, ``ci_level`` and ``ci_method``.
- The comparison's word is ``MultiDiffResult.comparison_verdict()``; the facts a reader sees are
  read from ``MultiDiffResult.to_json()``, the object ``diff --json`` prints inside its envelope: ``comparison_verdict``, ``verdict_rule``,
  ``flag_rule``, ``n_flagged_only``, ``verdict_limit``, ``fragility``, ``fragility_flips``,
  ``fragility_note``, ``fragility_exact``, ``errors_differ``, ``peeking``, ``intervals``,
  ``interval_level`` and ``interval_rule`` (``benjamini-yekutieli`` or ``bonferroni``).
- ``diff.bh`` and ``diff.holm`` are the two corrections, each returning adjusted p-values in the
  input's order.
- A family of ``M`` rows at level ``q`` is checked through ``multi_diff``'s own ``q`` where only
  the level ``q / M`` matters: one row at ``q / M`` gives the level of ``M`` rows at ``q``. The
  count of rows is checked on real families of 18 (9 conditions by 2 events) and of 328.
- The Westfall-Young tests call ``tree._min_p(observed, permuted)``: it holds the calibration and
  no public path exposes the permutation draws.
- A rollout's case id is ``Episode.meta["case_id"]``; the store copies it into its own ``case_id``
  column when the episode is appended, and a store frame carries it there (null for older parts),
  which is how ``multi_diff`` sees it without decoding ``meta``.
- ``mde_hr`` is the rise's hazard ratio under log-rank (null when the rise is null); the fall's is the
  grid point of ``log θ`` whose incidence change is the printed fall, recovered here from the template.
- ``fragility_flips`` holds one entry per flipped run: ``config_hash``, ``event``, ``run`` (``"a"`` or
  ``"b"``), ``replicate_index`` and ``to`` (``"event"`` or ``"not event"``), so its length is the
  fragility. A flip moves one row: a run is made to end in the event only from an
  outcome outside the compared events, and a run that ended in it is made to end outside them.

**Suite.** The math suite (marker ``math``). Most tests here run in seconds; the exhaustive fragility
searches make a few thousand ``multi_diff`` calls and take longer. The simulations are in ``tests/test_pf4_calibration.py``.
"""

from __future__ import annotations

import itertools
import math
import warnings
from collections.abc import Callable, Sequence
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st
from scipy import stats as sps

from poisson_prove import survival
from poisson_prove.diff import DiffError, bh, holm, interval_rd, interval_rd_paired, multi_diff
from poisson_prove.store import RunManifest

pytestmark = pytest.mark.math

Q = 0.05
POWER = 0.8
GRID = 1e-4
NOTES = {"no room", "none detectable", "cannot be flagged", "no matched pairs"}
LIMIT_KEYS = (
    "mde_rise", "mde_fall", "mde", "mde_rise_note", "mde_fall_note", "mde_note", "mde_test", "mde_basis",
    "mde_level", "mde_family", "mde_power", "mde_anchor", "p_min", "flaggable",
)


# ---------- frames and manifests, built by hand ----------


def _frame(cells: dict[str, list[tuple[int, str | None, float]]], horizon: float, meta: dict[str, Any] | None = None) -> pd.DataFrame:
    """A raw store frame: one row per ``(replicate_index, outcome, t)`` in each named cell. The seed
    is the replicate index plus 1000 in both arms, so a pair of frames is a paired design. ``meta``
    maps a cell to the ``meta`` its rollouts returned, when given; its case id lands in the frame's
    ``case_id`` column, as the store puts it."""
    rows = []
    for name, entries in cells.items():
        for rep, outcome, t in entries:
            row = {
                "config_hash": name,
                "config": {"cell": name},
                "replicate_index": rep,
                "seed": 1000 + rep,
                "outcome": outcome,
                "t": t,
                "horizon": horizon,
            }
            if meta is not None:
                case = dict(meta.get(name, {})).get("case_id")
                row["case_id"] = case if isinstance(case, str) and case else None
            rows.append(row)
    return pd.DataFrame(rows)


def _manifest(run_id: str, salt: str = "shared-salt", environment: dict[str, Any] | None = None) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        target_id="pf4",
        t_unit="steps",
        run_salt=salt,
        axis_types={"cell": "categorical"},
        backend="local",
        environment={} if environment is None else dict(environment),
    )


def _counts(k: int, n: int, *, event: str = "fell", other: str = "ok", t_event: float = 1.0, horizon: float = 10.0,
            start: int = 0) -> list[tuple[int, str, float]]:
    """``n`` runs, the first ``k`` ending in ``event`` at ``t_event``, the rest in ``other`` at the horizon."""
    return [(start + i, event, t_event) if i < k else (start + i, other, horizon) for i in range(n)]


def _compare(a: dict[str, Any], b: dict[str, Any], *, method: str = "fisher_bh", events: Sequence[str] = ("fell",),
             q: float = Q, power: float = POWER, kinds: dict[str, str] | None = None, horizon: float = 10.0,
             salt_b: str = "shared-salt", env: dict[str, Any] | None = None, meta_a: dict[str, Any] | None = None,
             meta_b: dict[str, Any] | None = None, horizon_b: float | None = None) -> Any:
    fa = _frame(a, horizon, meta_a)
    fb = _frame(b, horizon if horizon_b is None else horizon_b, meta_b)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return multi_diff(fa, fb, events=list(events), method=method, q=q, power=power, kinds=kinds,
                          manifest_a=_manifest("A", environment=env), manifest_b=_manifest("B", salt=salt_b, environment=env))


def _cell(result: Any, event: str, name: str) -> dict[str, Any]:
    cells = result.by_event[event].cells
    rows = cells[cells["config_hash"] == name]
    assert len(rows) == 1, (name, list(cells["config_hash"]))
    return dict(rows.iloc[0].to_dict())


def _none(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


# ---------- the references: the definitions, written here ----------


@lru_cache(maxsize=256)
def _fisher_p(n_a: int, n_b: int) -> np.ndarray:
    """scipy's ``fisher_exact`` on the 2x2 table of the event and the non-event in A, then in B. Its
    two-sided p does not depend on which row is which, so it checks no orientation; the directions
    in these tests come from counts the tests make themselves."""
    out = np.empty((n_a + 1, n_b + 1))
    for xa in range(n_a + 1):
        for xb in range(n_b + 1):
            out[xa, xb] = sps.fisher_exact([[xa, n_a - xa], [xb, n_b - xb]])[1]
    return out


def _ref_fisher_power(p_a: float, n_a: int, n_b: int, level: float, deltas: np.ndarray, rise: bool) -> np.ndarray:
    """The power model: A ~ Binomial(n_a, p_a), B ~ Binomial(n_b, p_a +- delta); a table counts when
    its Fisher p is below the level and B's share moved the way the change does."""
    xa, xb = np.arange(n_a + 1), np.arange(n_b + 1)
    moved = (xb[None, :] * n_a > xa[:, None] * n_b) if rise else (xb[None, :] * n_a < xa[:, None] * n_b)
    region = ((_fisher_p(n_a, n_b) < level) & moved).astype(float)
    weight = sps.binom.pmf(xa, n_a, p_a) @ region
    target = np.clip(p_a + deltas if rise else p_a - deltas, 0.0, 1.0)
    return sps.binom.pmf(xb[None, :], n_b, target[:, None]) @ weight


@lru_cache(maxsize=256)
def _paired_region(pairs: int, level: float) -> tuple[np.ndarray, np.ndarray]:
    """Every (n01, n10) with n01 + n10 <= pairs whose exact paired p (scipy's ``binomtest`` of the
    smaller count of the discordant pairs at one half, two-sided) is below the level: rise cells
    (n01 larger) and fall cells (n10 larger)."""
    rise, fall = [], []
    for n01 in range(pairs + 1):
        for n10 in range(pairs + 1 - n01):
            d = n01 + n10
            if d == 0 or n01 == n10:
                continue
            p = sps.binomtest(min(n01, n10), d, 0.5).pvalue
            if p < level:
                (rise if n01 > n10 else fall).append((n01, n10))
    return np.array(rise, dtype=int).reshape(-1, 2), np.array(fall, dtype=int).reshape(-1, 2)


def _ref_paired_power(p_a: float, pairs: int, level: float, deltas: np.ndarray, rise: bool) -> np.ndarray:
    """The paired power model: the two arms independent within a pair at A's share; the multinomial over
    (n01, n10, concordant) enumerated cell by cell, in chunks of the grid."""
    from scipy.special import gammaln

    cells = _paired_region(pairs, level)[0 if rise else 1]
    deltas = np.asarray(deltas, dtype=float)
    if len(cells) == 0:
        return np.zeros(len(deltas))
    n01, n10 = cells[:, 0].astype(float), cells[:, 1].astype(float)
    n00 = pairs - n01 - n10
    log_coef = gammaln(pairs + 1) - gammaln(n01 + 1) - gammaln(n10 + 1) - gammaln(n00 + 1)
    out = np.empty(len(deltas))
    for start in range(0, len(deltas), 400):
        d = deltas[start:start + 400][:, None]
        if rise:
            p01, p10 = (1 - p_a) * (p_a + d), p_a * (1 - p_a - d)
        else:
            p01, p10 = (1 - p_a) * (p_a - d), p_a * (1 - p_a + d)
        p00 = 1.0 - p01 - p10
        with np.errstate(divide="ignore", invalid="ignore"):
            terms = (log_coef[None, :]
                     + np.where(n01 > 0, n01 * np.log(np.maximum(p01, 1e-300)), 0.0)
                     + np.where(n10 > 0, n10 * np.log(np.maximum(p10, 1e-300)), 0.0)
                     + np.where(n00 > 0, n00 * np.log(np.maximum(p00, 1e-300)), 0.0))
        out[start:start + 400] = np.exp(terms).sum(axis=1)
    return out


def _grid_within(room: float) -> np.ndarray:
    """PF4.48: multiples of 0.0001 up to the room and never past it."""
    k = int(math.floor(room / GRID + 1e-9))
    grid = np.arange(1, k + 1) * GRID
    return grid[grid <= room + 1e-15]


def _ref_limit(power: Callable[[np.ndarray], np.ndarray], room: float) -> float | None:
    """PF4.22: the smallest grid value whose power reaches the target and stays at or above it at every
    larger grid value within the room; None when there is none."""
    grid = _grid_within(room)
    if grid.size == 0:
        return None
    values = power(grid)
    staying = np.minimum.accumulate(values[::-1])[::-1] >= POWER
    hits = np.nonzero(staying)[0]
    return float(grid[hits[0]]) if hits.size else None


def _ref_fisher_limits(events_a: int, n_a: int, n_b: int, level: float) -> tuple[float | None, float | None]:
    p_a = events_a / n_a
    rise = _ref_limit(lambda g: _ref_fisher_power(p_a, n_a, n_b, level, g, True), 1.0 - p_a)
    fall = _ref_limit(lambda g: _ref_fisher_power(p_a, n_a, n_b, level, g, False), p_a)
    return rise, fall


def _assert_limit(got: Any, want: float | None, what: Any) -> None:
    """The limit to the grid step: floating-point order
    can move a power that sits on the target by one ulp."""
    if want is None:
        assert _none(got), (what, got)
    else:
        assert not _none(got) and abs(float(got) - want) <= GRID + 1e-12, (what, got, want)


# ---------- PF4.1: the public Wilson interval states its level ----------


@pytest.mark.parametrize("level,k,n", [(None, 10, 32), (0.90, 7, 20), (0.975, 7, 20), (0.5, 7, 20)],
                         ids=["default", "0.90", "0.975", "0.5"])
def test_pf4_1_wilson_returns_its_bounds_level_z_and_method_at_each_level(level: float | None, k: int, n: int) -> None:
    """The default level and other levels in one
    test. scipy documents ``norm.isf(q)`` as the inverse survival function: the two-sided quantile at
    level L leaves (1 - L) / 2 in the upper tail. statsmodels documents
    ``proportion_confint(count, nobs, alpha, method="wilson")``; ``alpha`` is 1 - L."""
    from scipy.stats import norm
    from statsmodels.stats.proportion import proportion_confint

    from poisson_prove.stats import WILSON_LEVEL, WilsonInterval, wilson

    w = wilson(k, n) if level is None else wilson(k, n, level=level)
    want = WILSON_LEVEL if level is None else level
    if level is None:
        assert WILSON_LEVEL == 0.95
    assert isinstance(w, WilsonInterval) and w.method == "wilson"
    assert w.level == want
    assert abs(w.z - float(norm.isf((1.0 - want) / 2.0))) <= 1e-12
    lo, hi = proportion_confint(k, n, alpha=1.0 - want, method="wilson")
    assert abs(w.lo - float(lo)) <= 1e-12 and abs(w.hi - float(hi)) <= 1e-12


def test_pf4_1_wilson_bounds_are_statsmodels_at_each_level_over_the_existing_grid() -> None:
    """The grid of ``test_m5_survival``'s Wilson tests (n up to 500, k from 0 to n), sampled on a
    fixed lattice so the comparison is the same on every run, at the levels 0.95, 0.90, 0.975 and
    0.5 against statsmodels' ``proportion_confint(k, n, alpha=1 - level, method="wilson")``."""
    from statsmodels.stats.proportion import proportion_confint

    from poisson_prove.stats import wilson

    for n in (1, 2, 3, 5, 10, 32, 99, 100, 257, 500):
        for k in sorted({0, 1, n // 3, n // 2, n - 1, n} - {-1}):
            if not 0 <= k <= n:
                continue
            for level in (0.95, 0.90, 0.975, 0.5):
                w = wilson(k, n, level=level)
                lo, hi = proportion_confint(k, n, alpha=1.0 - level, method="wilson")
                assert abs(w.lo - float(lo)) <= 1e-12, (k, n, level)
                assert abs(w.hi - float(hi)) <= 1e-12, (k, n, level)


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.5])
def test_pf4_1_a_level_outside_zero_and_one_is_refused(level: float) -> None:
    from poisson_prove.stats import wilson

    with pytest.raises(ValueError):
        wilson(3, 10, level=level)


# ---------- PF4.1b: the cell table records the level beside the interval ----------


def test_pf4_1b_the_cell_table_records_the_level_beside_its_wilson_bounds() -> None:
    from poisson_prove.stats import WILSON_LEVEL, wilson

    df = _frame(
        {
            "low": [(i, "fell" if i < 5 else "survived", 1.0 + i if i < 5 else 5.0) for i in range(8)],
            "high": [(i, "fell" if i < 2 else "survived", 0.5 + i if i < 2 else 5.0) for i in range(8)],
        },
        5.0,
    )
    for method in ("km", "aj"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            table = survival.cell_table(df, "fell", method=method, events=["fell", "survived"] if method == "aj" else None)
        assert "event_rate_level" in table.columns
        cols = list(table.columns)
        # Beside the bounds: the level follows them.
        assert cols.index("event_rate_level") == cols.index("event_rate_hi") + 1
        for row in table.itertuples(index=False):
            assert row.event_rate_level == WILSON_LEVEL
            w = wilson(int(row.n_events), int(row.n), level=row.event_rate_level)
            assert abs(row.event_rate_lo - w.lo) <= 1e-12
            assert abs(row.event_rate_hi - w.hi) <= 1e-12


# ---------- PF4.22, PF4.23, PF4.48: Fisher's limits, both ways, within the room ----------


@settings(deadline=None, max_examples=40, suppress_health_check=[HealthCheck.too_slow])
@given(
    n_a=st.integers(min_value=1, max_value=48),
    n_b=st.integers(min_value=1, max_value=48),
    frac=st.floats(min_value=0.0, max_value=1.0),
    rows=st.sampled_from([1, 3, 9, 50]),
)
@example(n_a=100, n_b=20, frac=0.1, rows=9)
@example(n_a=20, n_b=100, frac=0.1, rows=9)
@example(n_a=4, n_b=4, frac=0.5, rows=1)
@example(n_a=30, n_b=30, frac=0.0, rows=3)
@example(n_a=30, n_b=30, frac=1.0, rows=3)
def test_pf4_23_fishers_limits_are_the_exact_power_definition_both_ways_on_any_arms(
    n_a: int, n_b: int, frac: float, rows: int
) -> None:
    """Each row's ``mde_rise`` and ``mde_fall`` against the enumeration written above (scipy's
    ``fisher_exact`` and ``binom``), at the level ``q / M`` (``M`` rows checked through ``q / M``, the
    file's reading), on equal and uneven arms both ways, from a baseline of 0 to 1."""
    events_a = round(frac * n_a)
    level = Q / rows
    result = _compare({"c": _counts(events_a, n_a)}, {"c": _counts(events_a, n_b)}, q=level)
    row = _cell(result, "fell", "c")
    rise, fall = _ref_fisher_limits(events_a, n_a, n_b, level)
    assert row["mde_test"] == "fisher" and row["mde_basis"] == "test"
    assert abs(row["mde_level"] - level) <= 1e-15 and row["mde_family"] == 1 and row["mde_power"] == POWER
    assert row["mde_anchor"] == "observed baseline"
    p_min = float(min(sps.fisher_exact([[n_a, 0], [0, n_b]])[1], sps.fisher_exact([[0, n_a], [n_b, 0]])[1]))
    assert abs(row["p_min"] - p_min) <= 1e-12 and row["flaggable"] is bool(p_min < level)
    if not p_min < level:
        assert row["mde_rise_note"] in ("cannot be flagged", "no room") and row["mde_fall_note"] in ("cannot be flagged", "no room")
        assert _none(row["mde_rise"]) and _none(row["mde_fall"])
        return
    _assert_limit(row["mde_rise"], rise, ("rise", n_a, n_b, events_a, rows))
    _assert_limit(row["mde_fall"], fall, ("fall", n_a, n_b, events_a, rows))
    for value, room in ((row["mde_rise"], 1 - events_a / n_a), (row["mde_fall"], events_a / n_a)):
        if not _none(value):
            assert 0 < value <= room + 1e-15  # PF4.48: never past the room


@pytest.mark.parametrize(
    "n_a,n_b,events_a,rows,rise,fall",
    [
        (100, 100, 50, 18, 0.2675, 0.2675),  # E21: 9 x 100 over 18 rows
        (100, 20, 10, 9, 0.3684, None),       # E18: 100/20 at 0.1 over 9 rows
        (20, 100, 2, 9, 0.4186, None),        # E18: 20/100 at 0.1 over 9 rows
    ],
    ids=["9x100-over-18", "100-20", "20-100"],
)
def test_pf4_23_the_addendums_measured_limits_hold(n_a: int, n_b: int, events_a: int, rows: int, rise: float, fall: float | None) -> None:
    result = _compare({"c": _counts(events_a, n_a)}, {"c": _counts(events_a, n_b)}, q=Q / rows)
    row = _cell(result, "fell", "c")
    assert abs(row["mde_rise"] - rise) <= GRID + 1e-12, row["mde_rise"]
    if fall is not None:
        assert abs(row["mde_fall"] - fall) <= GRID + 1e-12, row["mde_fall"]


def test_pf4_22_the_family_is_every_row_of_the_one_pass() -> None:
    """Nine conditions by two events is one pass of 18 rows: every row's level is q / 18 and its family
    18; a one-event comparison of the same runs is a pass of 9."""
    a = {f"c{i}": _counts(50, 100) + [(100 + j, "stuck", 2.0) for j in range(10)] for i in range(9)}
    two = _compare(a, a, events=("fell", "stuck"))
    one = _compare(a, a, events=("fell",))
    for result, m in ((two, 18), (one, 9)):
        for event in result.events:
            for row in result.by_event[event].cells.to_dict(orient="records"):
                assert row["mde_family"] == m and abs(row["mde_level"] - Q / m) <= 1e-15, (m, row["mde_family"])
    assert result.n_tests == 9


def test_pf4_48_a_fall_from_a_share_off_the_grid_never_steps_past_the_room() -> None:
    """A case found while the limits were designed: a fall from 5 of 194 with a grid that ran to room + step / 2 put
    B's share below 0 and turned "none detectable" into 0.0258."""
    result = _compare({"c": _counts(5, 194)}, {"c": _counts(5, 194)}, method="mcnemar_bh", q=Q / 18)
    row = _cell(result, "fell", "c")
    room = 5 / 194
    assert _none(row["mde_fall"]) or row["mde_fall"] <= room + 1e-15, row["mde_fall"]
    want = _ref_limit(lambda g: _ref_paired_power(5 / 194, 194, Q / 18, g, False), room)
    _assert_limit(row["mde_fall"], want, "fall from 5 of 194")
    if want is None:
        assert row["mde_fall_note"] == "none detectable"


# ---------- PF4.24: the paired test's limits ----------


PAIRED_CASES = [(pairs, frac, rows, unmatched) for pairs in (100, 194) for frac in (0.13, 0.5, 0.87) for rows in (9, 18)
                for unmatched in (False, True) if not (pairs == 194 and unmatched)]


@pytest.mark.parametrize("pairs,frac,rows,unmatched", PAIRED_CASES,
                         ids=[f"{p}-{f}-{r}{'-unmatched' if u else ''}" for p, f, r, u in PAIRED_CASES])
def test_pf4_24_the_paired_limits_are_the_independent_arms_enumeration_over_the_matched_pairs(
    pairs: int, frac: float, rows: int, unmatched: bool
) -> None:
    """Against an enumeration of the multinomial written above, with scipy's ``binomtest`` as the
    paired p; on arms with unmatched runs the limit uses the pairs, never n_a; and changing B's rows
    leaves it as it was (it reads nothing about B)."""
    k = round(frac * pairs)
    a = _counts(k, pairs)
    b = _counts(k, pairs)
    if unmatched:
        a = a + _counts(10, 30, start=1000)
        b = b + _counts(25, 30, start=2000)
    result = _compare({"c": a}, {"c": b}, method="mcnemar_bh", q=Q / rows)
    row = _cell(result, "fell", "c")
    assert row["pairs"] == pairs and row["mde_test"] == "mcnemar"
    p_a = k / pairs
    rise = _ref_limit(lambda g: _ref_paired_power(p_a, pairs, Q / rows, g, True), 1 - p_a)
    fall = _ref_limit(lambda g: _ref_paired_power(p_a, pairs, Q / rows, g, False), p_a)
    _assert_limit(row["mde_rise"], rise, "rise")
    _assert_limit(row["mde_fall"], fall, "fall")
    assert abs(row["p_min"] - min(1.0, 2 * 0.5**pairs)) <= 1e-15
    moved = _compare({"c": a}, {"c": _counts(pairs - k, pairs)}, method="mcnemar_bh", q=Q / rows)
    other = _cell(moved, "fell", "c")
    assert (other["mde_rise"], other["mde_fall"]) == (row["mde_rise"], row["mde_fall"])


def test_pf4_24_the_paired_limit_at_9_by_100_over_18_rows_is_e21s() -> None:
    result = _compare({"c": _counts(50, 100)}, {"c": _counts(50, 100)}, method="mcnemar_bh", q=Q / 18)
    assert abs(_cell(result, "fell", "c")["mde_rise"] - 0.2698) <= GRID + 1e-12


def test_pf4_27_a_paired_condition_with_no_matched_pair_has_no_limit() -> None:
    """'c' ran different replicates in the two runs; 'd' is matched, so the pair is pairable."""
    result = _compare({"c": _counts(5, 20), "d": _counts(5, 20)}, {"c": _counts(5, 20, start=100), "d": _counts(5, 20)},
                      method="mcnemar_bh")
    row = _cell(result, "fell", "c")
    assert row["pairs"] == 0
    assert (row["mde_rise_note"], row["mde_fall_note"], row["mde_note"]) == ("no matched pairs",) * 3
    assert _none(row["mde_rise"]) and _none(row["mde_fall"]) and _none(row["mde"])


# ---------- PF4.25 and PF4.43: log-rank in discrete time ----------


def _template(t: np.ndarray, o: np.ndarray) -> list[tuple[float, float, float]]:
    """A's risk set at each distinct time: (at risk, events, other endings)."""
    out = []
    for x in np.unique(t):
        out.append((float(np.sum(t >= x)), float(np.sum((t == x) & o)), float(np.sum((t == x) & ~o))))
    return out


def _ref_logrank(t_a: np.ndarray, o_a: np.ndarray, n_b: int, theta: float, level: float) -> tuple[float, float]:
    """(power, B's incidence at the horizon) under the discrete mapping of PF4.43, written from its
    definition: B's hazard of the event 1 - (1 - h_A)^theta at each of A's times, B's other endings A's
    share among the runs that did not have the event, and Lakatos's expected moments for A's O - E."""
    z = sps.norm.isf(level / 2)
    y_b, mu, var, cif = float(n_b), 0.0, 0.0, 0.0
    for y_a, d_a, c_a in _template(t_a, o_a):
        h = d_a / y_a
        e_b = y_b * (1 - (1 - h) ** theta)
        c_b = (y_b - e_b) * (c_a / (y_a - d_a) if y_a > d_a else 0.0)
        n, d = y_a + y_b, d_a + e_b
        if d > 0:
            mu += d_a - y_a * d / n
            if n > 1:
                var += y_a * y_b * d * (n - d) / (n * n * (n - 1))
        cif += e_b / n_b
        y_b -= e_b + c_b
    power = float(sps.norm.cdf(abs(mu) / math.sqrt(var) - z)) if var > 0 else 0.0
    return power, cif


def _logrank_frames(base: float, competing: float, n: int, seed: int) -> dict[str, list[tuple[int, str, float]]]:
    """n runs over 20 steps: each step, the event with a per-step chance that reaches ``base`` by the
    horizon, a competing ending with a chance that reaches ``competing``."""
    rng = np.random.default_rng(seed)
    per_event = 1 - (1 - base) ** (1 / 20)
    per_other = 1 - (1 - competing) ** (1 / 20) if competing else 0.0
    rows = []
    for i in range(n):
        for step in range(1, 21):
            u = rng.random()
            if u < per_event:
                rows.append((i, "fell", float(step)))
                break
            if u < per_event + per_other:
                rows.append((i, "stuck", float(step)))
                break
        else:
            rows.append((i, "ok", 20.0))
    return {"c": rows}


def _check_logrank_limits(a: dict[str, list[tuple[int, str, float]]], n: int, rows: int, both: bool) -> None:
    """Both directions against the reference: the rise at ``mde_hr`` and one grid step nearer 1, the
    fall at the grid step its printed change implies and one step nearer 1; a null direction has power
    below the target at the end of its grid (theta = 1e6 or 1e-6), so no grid value stays above it."""
    level = Q / rows
    row = _cell(_compare(a, a, method="logrank_bh", q=level, horizon=20.0), "fell", "c")
    assert row["mde_test"] == "logrank" and row["mde_basis"] == "test"
    t = np.array([r[2] for r in a["c"]])
    o = np.array([r[1] == "fell" for r in a["c"]])
    # No run is censored before the horizon, so A's incidence there is its share (lifelines'
    # AalenJohansenFitter agrees, read between steps: it jitters tied times).
    cif_a = float(o.mean())
    if both:
        assert not _none(row["mde_rise"]) and not _none(row["mde_fall"]), (row["mde_rise_note"], row["mde_fall_note"])
    if _none(row["mde_rise"]):
        assert _ref_logrank(t, o, n, 1e6, level)[0] < POWER and row["mde_hr"] is None
    else:
        hr = row["mde_hr"]
        assert hr is not None and hr > 1 and row["mde_rise"] >= GRID - 1e-12
        power, cif_b = _ref_logrank(t, o, n, hr, level)
        below, _ = _ref_logrank(t, o, n, hr / math.exp(1e-3), level)
        assert power >= POWER - 1e-9 and below < POWER, (power, below)
        assert abs(row["mde_rise"] - (cif_b - cif_a)) <= 1e-6, (row["mde_rise"], cif_b - cif_a)
    if _none(row["mde_fall"]):
        assert _ref_logrank(t, o, n, 1e-6, level)[0] < POWER
    else:
        assert row["mde_fall"] >= GRID - 1e-12
        k = _fall_step(t, o, n, row["mde_fall"], cif_a)
        assert k is not None and k >= 1, row["mde_fall"]
        power, _ = _ref_logrank(t, o, n, math.exp(-k * 1e-3), level)
        above, _ = _ref_logrank(t, o, n, math.exp(-(k - 1) * 1e-3), level)
        assert power >= POWER - 1e-9 and (k == 1 or above < POWER), (power, above)


@pytest.mark.parametrize("base,competing", [(0.2, 0.0), (0.5, 0.0), (0.2, 0.2), (0.5, 0.2)],
                         ids=["0.2", "0.5", "0.2-competing", "0.5-competing"])
def test_pf4_43_the_logrank_limit_is_the_discrete_mapping_on_as_risk_set(base: float, competing: float) -> None:
    _check_logrank_limits(_logrank_frames(base, competing, 100, seed=int(base * 100 + competing * 10)), 100, 18, True)


@settings(deadline=None, max_examples=8, suppress_health_check=[HealthCheck.too_slow])
@given(n=st.integers(min_value=20, max_value=150), base=st.floats(0.05, 0.7), competing=st.sampled_from([0.0, 0.15, 0.3]),
       rows=st.sampled_from([1, 9, 18]), seed=st.integers(0, 10_000))
@example(n=20, base=0.05, competing=0.3, rows=18, seed=7)
def test_pf4_43_on_any_template_both_limits_are_the_discrete_mapping(n: int, base: float, competing: float, rows: int, seed: int) -> None:
    a = _logrank_frames(base, competing, n, seed=seed)
    assume(any(outcome == "fell" for _, outcome, _ in a["c"]))  # a zero baseline is PF4.43's other branch
    _check_logrank_limits(a, n, rows, False)


def _fall_step(t: np.ndarray, o: np.ndarray, n_b: int, value: float, cif_a: float) -> int | None:
    """The step k of the fall's grid, theta = exp(-0.001 k), whose incidence change is ``value`` (the
    change grows with k, so a bisection finds it)."""
    def change(k: int) -> float:
        return cif_a - _ref_logrank(t, o, n_b, math.exp(-k * 1e-3), Q)[1]

    lo, hi = 1, int(math.floor(math.log(1e6) / 1e-3))
    while lo < hi:
        mid = (lo + hi) // 2
        if change(mid) < value - 1e-7:
            lo = mid + 1
        else:
            hi = mid
    return lo if abs(change(lo) - value) <= 1e-6 else None


def test_pf4_43_where_as_hazard_reaches_one_a_fall_cannot_be_reached_and_reads_none_detectable() -> None:
    """Every run of A fell, at steps 1 to 9, so at A's last time its hazard is 1 and
    1 - (1 - 1)^theta stays 1 for every theta: B's incidence cannot fall under the discrete mapping. The
    rise has no room, the fall is none detectable (never a change of 0), and the condition has no
    limit. On the lattice pair 37 conditions are like this (every run of its before arm tripped)."""
    a = {"c": [(i, "fell", 1.0 + (i % 9)) for i in range(40)]}
    row = _cell(_compare(a, a, method="logrank_bh", q=Q / 18), "fell", "c")
    assert row["mde_basis"] == "test"
    assert _none(row["mde_rise"]) and row["mde_rise_note"] == "no room"
    assert _none(row["mde_fall"]) and row["mde_fall_note"] == "none detectable"
    assert _none(row["mde"]) and row["mde_note"] == "none detectable"


def test_pf4_43_no_hazard_leaves_zero_and_one_however_large_theta() -> None:
    """Heavy ties: 30 of 100 fall at step 1. The old linear scaling put B's hazard there above 1 for
    theta above 3.3; the discrete mapping keeps the room at the incidence B reaches when every run at
    risk at A's first event time has the event, below 1."""
    a = {"c": _counts(30, 100, t_event=1.0, horizon=20.0)}
    result = _compare(a, a, method="logrank_bh", q=Q / 18, horizon=20.0)
    row = _cell(result, "fell", "c")
    assert not _none(row["mde_rise"]) and 0 < row["mde_rise"] <= 0.7 + 1e-12
    t = np.array([r[2] for r in a["c"]])
    o = np.array([r[1] == "fell" for r in a["c"]])
    _, cif_b = _ref_logrank(t, o, 100, row["mde_hr"], Q / 18)
    assert 0 <= cif_b <= 1


def _zero_baseline_kstar(n_a: int, other: int, n_b: int, r_b: int, level: float) -> int | None:
    """The fewest B events, all at the horizon among B's ``r_b`` runs at risk there, whose log-rank p
    (lifelines' ``logrank_test``) is below the level, against A's runs: ``other`` ended in another outcome
    at step 1 and the rest reached the horizon without the event."""
    from lifelines.statistics import logrank_test

    t_a = np.where(np.arange(n_a) < other, 1.0, 10.0)
    t_b = np.where(np.arange(n_b) < n_b - r_b, 1.0, 10.0)
    for k in range(1, r_b + 1):
        observed_b = np.arange(n_b) >= n_b - k
        if logrank_test(t_a, t_b, event_observed_A=np.zeros(n_a, bool), event_observed_B=observed_b).p_value < level:
            return k
    return None


@pytest.mark.parametrize("n_a,other,n_b,rows", [(100, 0, 100, 18), (40, 0, 40, 9), (194, 0, 194, 18), (100, 40, 100, 18),
                                                 (60, 20, 60, 9), (41, 13, 30, 9)],
                         ids=["100-over-18", "40-over-9", "194-over-18", "100-with-40-other", "60-with-20-other",
                              "41-with-13-other-against-30"])
def test_pf4_43_a_zero_baseline_uses_logranks_own_threshold_not_fishers(n_a: int, other: int, n_b: int, rows: int) -> None:
    """No event in A; ``other`` of A's runs ended in another outcome before the horizon, so A has
    ``r_a = n_a - other`` at risk there and B ``r_b = round(n_b r_a / n_a)`` (20 of 30 against 28 of 41).
    The power at a change delta is Binomial(r_b, delta n_b / r_b) reaching k*, over the grid up to the
    rise's room ``r_b / n_b``. The limit reads A only, so B's runs here are all 'ok'."""
    level = Q / rows
    arm_a = [(i, "stuck", 1.0) if i < other else (i, "ok", 10.0) for i in range(n_a)]
    arm_b = [(i, "ok", 10.0) for i in range(n_b)]
    result = _compare({"c": arm_a}, {"c": arm_b}, method="logrank_bh", q=level, salt_b="other-salt")
    row = _cell(result, "fell", "c")
    assert row["mde_basis"] == "zero baseline" and row["mde_test"] == "logrank"
    assert row["mde_fall_note"] == "no room"
    r_b = int(math.floor(n_b * (n_a - other) / n_a + 0.5))
    kstar = _zero_baseline_kstar(n_a, other, n_b, r_b, level)
    assert kstar is not None
    want = _ref_limit(lambda g: sps.binom.sf(kstar - 1, r_b, np.clip(g * n_b / r_b, 0.0, 1.0)), r_b / n_b)
    _assert_limit(row["mde_rise"], want, ("zero baseline", n_a, other, n_b, rows))
    assert want is None or want <= r_b / n_b + 1e-12


def test_pf4_43_a_zero_baseline_with_no_threshold_has_no_rise_and_says_none_detectable() -> None:
    """36 of A's 40 runs ended in another outcome at step 1: with four runs a side at risk at the
    horizon, even all four of B's having the event gives log-rank p about 0.008, above 0.05 / 18. The
    condition can still be flagged (an earlier event would) so ``flaggable`` holds, and the rise, whose
    power is 0 under the zero-baseline model, is null with ``none detectable``."""
    level = Q / 18
    arm = [(i, "stuck", 1.0) if i < 36 else (i, "ok", 10.0) for i in range(40)]
    row = _cell(_compare({"c": arm}, {"c": arm}, method="logrank_bh", q=level), "fell", "c")
    assert _zero_baseline_kstar(40, 36, 40, 4, level) is None
    assert row["mde_basis"] == "zero baseline" and row["flaggable"] is True
    assert _none(row["mde_rise"]) and row["mde_rise_note"] == "none detectable"
    assert row["mde_fall_note"] == "no room" and _none(row["mde"]) and row["mde_note"] == "none detectable"


# ---------- PF4.27, PF4.28: no limit, and the design facts ----------


def test_pf4_15_the_single_event_diff_also_reports_no_limit_at_ceiling() -> None:
    """PF4.15 on the single-event ``diff()`` result, which keeps its own record: a condition that had the event in every run has no limit, and the largest is the other's."""
    from poisson_prove.diff import diff
    from poisson_prove.survival import censor

    a = {"ceiling": [(i, "fell", 1.0) for i in range(20)],
         "half": [(i, "fell" if i < 10 else "ok", 1.0 if i < 10 else 10.0) for i in range(20)]}
    fa = censor(_frame(a, 10.0), "fell")
    fb = censor(_frame(a, 10.0), "fell")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = diff(fa, fb, event="fell", manifest_a=_manifest("A"), manifest_b=_manifest("B"))
    cells = result.cells.set_index("config_hash")
    assert math.isnan(cells.loc["ceiling", "mde"])
    assert result.max_mde == cells.loc["half", "mde"]


def test_pf4_27_at_a_baseline_of_one_the_rise_has_no_room_and_the_fall_is_the_limit() -> None:
    """Refines PF4.15: a cell whose baseline had the event in every run, decided from the
    counts, has no rise, a computed fall, and enters the maxima."""
    a = {
        "all_fell": [(i, "fell", 0.01 * (i + 1)) for i in range(40)],
        "low": _counts(4, 40),
    }
    result = _compare(a, a)
    top = _cell(result, "fell", "all_fell")
    assert top["events_a"] == top["n_a"] == 40
    assert _none(top["mde_rise"]) and top["mde_rise_note"] == "no room"
    _, fall = _ref_fisher_limits(40, 40, 40, Q / 2)
    _assert_limit(top["mde_fall"], fall, "fall from 40 of 40")
    assert top["mde"] == top["mde_fall"] and top["mde_note"] is None
    ev = result.by_event["fell"]
    numbers = [r["mde"] for r in ev.cells.to_dict(orient="records") if not _none(r["mde"])]
    assert ev.max_mde == max(numbers) and ev.max_mde_unchanged == max(numbers)


@settings(deadline=None, max_examples=30)
@given(n=st.integers(min_value=1, max_value=40), frac=st.floats(0, 1), method=st.sampled_from(["fisher_bh", "mcnemar_bh"]),
       rows=st.sampled_from([1, 9, 50]))
@example(n=3, frac=0.5, method="fisher_bh", rows=9)
@example(n=40, frac=0.0, method="fisher_bh", rows=1)
@example(n=40, frac=1.0, method="mcnemar_bh", rows=1)
@example(n=40, frac=0.95, method="fisher_bh", rows=50)
def test_pf4_27_every_null_has_a_note_from_the_closed_list_and_mde_follows_the_rule(n: int, frac: float, method: str, rows: int) -> None:
    k = round(frac * n)
    result = _compare({"c": _counts(k, n)}, {"c": _counts(k, n)}, method=method, q=Q / rows)
    row = _cell(result, "fell", "c")
    for way in ("rise", "fall"):
        value, note = row[f"mde_{way}"], row[f"mde_{way}_note"]
        assert (note is None) is (not _none(value)), (way, value, note)
        assert note is None or note in NOTES, note
    assert (row["mde_rise_note"] == "no room") is (k == n)
    assert (row["mde_fall_note"] == "no room") is (k == 0)
    if not row["flaggable"]:
        assert {row["mde_rise_note"], row["mde_fall_note"]} <= {"cannot be flagged", "no room"}
    rise, fall = row["mde_rise"], row["mde_fall"]
    if not _none(rise) and not _none(fall):
        assert row["mde"] == max(rise, fall) and row["mde_note"] is None
    elif not _none(rise) and row["mde_fall_note"] == "no room":
        assert row["mde"] == rise
    elif not _none(fall) and row["mde_rise_note"] == "no room":
        assert row["mde"] == fall
    else:
        assert _none(row["mde"])
        # The note of the direction that made it null, the rise's when both did; a direction
        # with no room never makes it null.
        made_null = [n for v, n in ((rise, row["mde_rise_note"]), (fall, row["mde_fall_note"])) if _none(v) and n != "no room"]
        assert row["mde_note"] == (made_null[0] if made_null else row["mde_rise_note"])


@pytest.mark.parametrize("n,rows,together,lone", [(4, 5, 3, 5), (4, 50, 29, 7), (8, 328, 2, 9)],
                         ids=["4-over-5", "4-over-50", "8-over-328"])
def test_pf4_28_when_no_lone_condition_can_be_flagged_the_event_carries_the_design_facts(
    n: int, rows: int, together: int, lone: int
) -> None:
    """E18's designs over real families of conditions: Fisher's smallest p with n a side, how many rows
    would have to move to their extremes together (Benjamini-Hochberg's step-up applied to the best
    case), and the smallest equal n at which a lone condition could be flagged."""
    a = {f"c{i:03d}": _counts(n // 2, n) for i in range(rows)}
    result = _compare(a, a)
    ev = result.by_event["fell"]
    p_min = sps.fisher_exact([[n, 0], [0, n]])[1]
    assert not p_min < Q / rows
    assert ev.n_unflaggable == rows
    assert ev.together_needed == together
    assert ev.replicates_for_lone_flag == lone
    doc = result.to_json()["by_event"]["fell"]
    assert (doc["n_unflaggable"], doc["together_needed"], doc["replicates_for_lone_flag"]) == (rows, together, lone)


# ---------- PF4.13: the log-rank direction is the statistic's ----------


def _observed_minus_expected_b(fa: pd.DataFrame, fb: pd.DataFrame, event: str) -> float:
    """B's observed minus expected events over the pooled event times, from lifelines'
    ``survival_table_from_events``: documented as a table indexed by the distinct times with an
    ``observed`` and an ``at_risk`` column, each summing ``weights`` when weights are given. A weight
    of 1 on B's rows and 0 on A's gives B's own columns on the pooled index."""
    from lifelines.utils import survival_table_from_events

    t = np.concatenate([fa["t"].to_numpy(float), fb["t"].to_numpy(float)])
    e = np.concatenate([(fa["outcome"] == event).to_numpy(), (fb["outcome"] == event).to_numpy()])
    w_b = np.concatenate([np.zeros(len(fa)), np.ones(len(fb))])
    pooled = survival_table_from_events(t, e)
    only_b = survival_table_from_events(t, e, weights=w_b)
    total = 0.0
    for time in pooled.index:
        d = float(pooled.loc[time, "observed"])
        if d == 0:
            continue
        n = float(pooled.loc[time, "at_risk"])
        total += float(only_b.loc[time, "observed"]) - float(only_b.loc[time, "at_risk"]) * d / n
    return total


def _lifelines_logrank_p(fa: pd.DataFrame, fb: pd.DataFrame, event: str) -> float:
    from lifelines.statistics import logrank_test

    res = logrank_test(
        fa["t"].to_numpy(float), fb["t"].to_numpy(float),
        event_observed_A=(fa["outcome"] == event).to_numpy(),
        event_observed_B=(fb["outcome"] == event).to_numpy(),
    )
    return float(res.p_value)


#: Four cells, one per relation between the horizon difference and the statistic, and one the test
#: does not reject.
LOGRANK_CELLS: dict[str, tuple[list[tuple[int, str, float]], list[tuple[int, str, float]]]] = {
    # Every run falls in both arms; B falls far earlier. delta is 0, the test rejects.
    "equal_rates_b_sooner": (
        [(i, "fell", 8.0 + 0.05 * i) for i in range(32)],
        [(i, "fell", 1.0 + 0.05 * i) for i in range(32)],
    ),
    # A falls in 24 just before the horizon; B in 23 near the start. delta < 0, B's hazard higher.
    "crossing_b_fewer_but_sooner": (
        [(i, "fell", 9.9) if i < 24 else (i, "ok", 10.0) for i in range(32)],
        [(i, "fell", 0.5 + 0.01 * i) if i < 23 else (i, "ok", 10.0) for i in range(32)],
    ),
    # B falls more and sooner: both read a rise.
    "agreeing_rise": (
        [(i, "fell", 6.0 + 0.1 * i) if i < 6 else (i, "ok", 10.0) for i in range(32)],
        [(i, "fell", 1.0 + 0.1 * i) if i < 26 else (i, "ok", 10.0) for i in range(32)],
    ),
    # B falls less and later: both read a fall.
    "agreeing_fall": (
        [(i, "fell", 1.0 + 0.1 * i) if i < 26 else (i, "ok", 10.0) for i in range(32)],
        [(i, "fell", 6.0 + 0.1 * i) if i < 6 else (i, "ok", 10.0) for i in range(32)],
    ),
    # The same runs in both arms: nothing to reject.
    "quiet": (
        [(i, "fell", 2.0 + 0.1 * i) if i < 8 else (i, "ok", 10.0) for i in range(32)],
        [(i, "fell", 2.0 + 0.1 * i) if i < 8 else (i, "ok", 10.0) for i in range(32)],
    ),
}
REJECTED = ("equal_rates_b_sooner", "crossing_b_fewer_but_sooner", "agreeing_rise", "agreeing_fall")


def _logrank_result() -> tuple[Any, pd.DataFrame, pd.DataFrame]:
    fa = _frame({name: a for name, (a, _) in LOGRANK_CELLS.items()}, 10.0)
    fb = _frame({name: b for name, (_, b) in LOGRANK_CELLS.items()}, 10.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = multi_diff(
            fa, fb, events=["fell"], method="logrank_bh",
            manifest_a=_manifest("A", "salt-a"), manifest_b=_manifest("B", "salt-b"),
        )
    return result, fa, fb


def test_pf4_13_the_logrank_p_value_is_lifelines_and_the_direction_is_the_statistics_sign() -> None:
    result, fa, fb = _logrank_result()
    for name in REJECTED:
        a, b = fa[fa["config_hash"] == name], fb[fb["config_hash"] == name]
        row = _cell(result, "fell", name)
        assert math.isclose(row["p"], _lifelines_logrank_p(a, b, "fell"), rel_tol=1e-9), name
        assert row["q"] < Q, name  # every one of the four rejects
        o_minus_e = _observed_minus_expected_b(a, b, "fell")
        assert o_minus_e != 0.0, name
        assert row["direction"] == ("higher" if o_minus_e > 0 else "lower"), (name, o_minus_e)


def test_pf4_13_a_rejected_cell_with_no_horizon_difference_is_a_change_not_unchanged() -> None:
    result, _, _ = _logrank_result()
    row = _cell(result, "fell", "equal_rates_b_sooner")
    assert row["delta"] == 0.0
    assert row["direction"] == "higher"
    ev = result.by_event["fell"]
    # The four rejected cells moved; only the quiet one is unchanged.
    assert ev.n_unchanged == 1
    quiet = _cell(result, "fell", "quiet")
    assert quiet["direction"] == "unchanged"


def test_pf4_13_the_timing_note_is_on_exactly_the_cells_whose_horizon_difference_disagrees() -> None:
    result, _, _ = _logrank_result()
    for name, disagrees in (
        ("equal_rates_b_sooner", True),
        ("crossing_b_fewer_but_sooner", True),
        ("agreeing_rise", False),
        ("agreeing_fall", False),
        ("quiet", False),
    ):
        row = _cell(result, "fell", name)
        note = row["direction_note"]
        if disagrees:
            # The note says the test read the timing: B's events came sooner on both cells.
            assert isinstance(note, str) and "sooner" in note, (name, note)
        else:
            assert note is None or (isinstance(note, float) and math.isnan(note)), (name, note)
    # The horizon difference is kept as it is on the disagreeing cells.
    crossing = _cell(result, "fell", "crossing_b_fewer_but_sooner")
    assert abs(crossing["delta"] - (23 / 32 - 24 / 32)) <= 1e-12


EDGE_ARMS = [
    pytest.param((0, 20), (9, 45), id="a-at-0pct-uneven"),
    pytest.param((20, 20), (30, 45), id="a-at-100pct-uneven"),
    pytest.param((0, 45), (0, 20), id="both-at-0pct"),
    pytest.param((45, 45), (3, 20), id="a-at-100pct-b-low"),
    pytest.param((7, 45), (20, 20), id="b-at-100pct"),
]


@pytest.mark.parametrize("arm_a,arm_b", EDGE_ARMS)
def test_pf4_13_each_tests_p_value_and_share_hold_at_0_and_100_percent_on_uneven_arms(arm_a: tuple[int, int], arm_b: tuple[int, int]) -> None:
    """The independent read's finding 3: 0% and 100% arms, uneven sizes both ways. Fisher's p is
    scipy's; log-rank's (events spread over steps 1 to 9) is lifelines'; with no censoring before the
    horizon each arm's incidence is its share; the direction is the sign of the shares' difference
    for Fisher and of B's observed minus expected events for log-rank."""
    (ka, na), (kb, nb) = arm_a, arm_b

    def arm(k: int, n: int) -> list[tuple[int, str, float]]:
        return [(i, "fell", 1.0 + (i % 9)) if i < k else (i, "ok", 10.0) for i in range(n)]

    a, b = {"c": arm(ka, na)}, {"c": arm(kb, nb)}
    fisher = _cell(_compare(a, b, salt_b="other-salt"), "fell", "c")
    assert abs(fisher["p"] - sps.fisher_exact([[ka, na - ka], [kb, nb - kb]])[1]) <= 1e-12
    assert abs(fisher["rate_a"] - ka / na) <= 1e-12 and abs(fisher["rate_b"] - kb / nb) <= 1e-12
    logrank = _cell(_compare(a, b, method="logrank_bh", salt_b="other-salt"), "fell", "c")
    fa, fb = _frame(a, 10.0), _frame(b, 10.0)
    if ka + kb:
        assert abs(logrank["p"] - _lifelines_logrank_p(fa, fb, "fell")) <= 1e-9 * max(1.0, logrank["p"])
    else:
        assert logrank["p"] == 1.0
    assert abs(logrank["rate_a"] - ka / na) <= 1e-12 and abs(logrank["rate_b"] - kb / nb) <= 1e-12
    if logrank["q"] < Q:
        sign = _observed_minus_expected_b(fa, fb, "fell")
        assert logrank["direction"] == ("higher" if sign > 0 else "lower"), (logrank["direction"], sign)


@pytest.mark.parametrize("a_events,b_events", [(40, 25), (0, 12), (40, 40), (0, 0)],
                         ids=["a-at-100pct", "a-at-0pct", "both-at-100pct", "both-at-0pct"])
def test_pf4_14_the_paired_p_value_holds_at_0_and_100_percent(a_events: int, b_events: int) -> None:
    """The independent read's finding 3 for the paired test: 40 matched pairs with A at 0% or 100%;
    statsmodels' exact McNemar on the matched table."""
    fa = _frame({"c": [(i, "fell" if i < a_events else "ok", 10.0) for i in range(40)]}, 10.0)
    fb = _frame({"c": [(i, "fell" if i < b_events else "ok", 10.0) for i in range(40)]}, 10.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = multi_diff(fa, fb, events=["fell"], method="mcnemar_bh", manifest_a=_manifest("A"), manifest_b=_manifest("B"))
    row = _cell(result, "fell", "c")
    p, n10, n01, pairs = _statsmodels_mcnemar(fa, fb, "fell")
    assert pairs == 40 and row["pairs"] == 40
    assert abs(row["p"] - p) <= 1e-12 if n10 + n01 else row["p"] == 1.0
    assert abs(row["delta"] - (n01 - n10) / pairs) <= 1e-12


def test_pf4_13_fisher_and_the_paired_test_carry_no_timing_note() -> None:
    fa = _frame({"c": [(i, "fell" if i < 6 else "ok", 10.0) for i in range(32)]}, 10.0)
    fb = _frame({"c": [(i, "fell" if i < 26 else "ok", 10.0) for i in range(32)]}, 10.0)
    for method in ("fisher_bh", "mcnemar_bh"):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = multi_diff(fa, fb, events=["fell"], method=method,
                                manifest_a=_manifest("A"), manifest_b=_manifest("B"))
        row = _cell(result, "fell", "c")
        assert row["direction"] == "higher"
        note = row.get("direction_note")
        assert note is None or (isinstance(note, float) and math.isnan(note)), (method, note)


# ---------- PF4.14: the paired test reports and labels the matched-pair difference ----------


def _unmatched_pair() -> tuple[pd.DataFrame, pd.DataFrame]:
    """32 rows an arm, 20 of them matched (replicates 0 to 19 in both). On the matched pairs A had
    the event in 4 and B in those 4 and 8 more; A's 12 unmatched rows all had it and B's 12
    unmatched rows none. Own rows: A 16 of 32, B 12 of 32, a fall; matched pairs: a rise of 8/20."""
    a = [(i, "fell" if i < 4 else "ok", 10.0) for i in range(20)]
    a += [(20 + j, "fell", 10.0) for j in range(12)]
    b = [(i, "fell" if i < 12 else "ok", 10.0) for i in range(20)]
    b += [(40 + j, "ok", 10.0) for j in range(12)]
    return _frame({"c": a}, 10.0), _frame({"c": b}, 10.0)


def _statsmodels_mcnemar(fa: pd.DataFrame, fb: pd.DataFrame, event: str) -> tuple[float, int, int, int]:
    """statsmodels' ``mcnemar(table, exact=True)`` on the 2x2 table of paired outcomes
    ``[[yes-yes, yes-no], [no-yes, no-no]]``. Its exact p is the binomial test of the smaller
    discordant count, which does not depend on which off-diagonal is which, so it checks no
    orientation; the discordant counts returned are the ones this function counts. Returns
    ``(p, n10, n01, pairs)``."""
    from statsmodels.stats.contingency_tables import mcnemar

    m = fa.merge(fb, on="replicate_index", suffixes=("_a", "_b"))
    ya = (m["outcome_a"] == event).to_numpy()
    yb = (m["outcome_b"] == event).to_numpy()
    n11, n10 = int((ya & yb).sum()), int((ya & ~yb).sum())
    n01, n00 = int((~ya & yb).sum()), int((~ya & ~yb).sum())
    res = mcnemar([[n11, n10], [n01, n00]], exact=True)
    return float(res.pvalue), n10, n01, len(m)


def test_pf4_14_with_unmatched_runs_the_paired_cell_reports_and_labels_the_matched_difference() -> None:
    fa, fb = _unmatched_pair()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = multi_diff(fa, fb, events=["fell"], method="mcnemar_bh",
                            manifest_a=_manifest("A"), manifest_b=_manifest("B"))
    row = _cell(result, "fell", "c")
    p, n10, n01, pairs = _statsmodels_mcnemar(fa, fb, "fell")
    assert (n10, n01, pairs) == (0, 8, 20)
    assert abs(row["p"] - p) <= 1e-12
    assert row["pairs"] == 20
    assert abs(row["delta"] - (n01 - n10) / pairs) <= 1e-12
    assert row["direction"] == "higher"
    # Each arm's own rate stays beside it.
    assert abs(row["rate_a"] - 16 / 32) <= 1e-12
    assert abs(row["rate_b"] - 12 / 32) <= 1e-12
    assert result.by_event["fell"].n_unchanged == 0


def test_pf4_14_on_fully_matched_arms_the_matched_and_own_row_differences_are_equal() -> None:
    fa = _frame({"c": [(i, "fell" if i < 9 else "ok", 10.0) for i in range(40)]}, 10.0)
    fb = _frame({"c": [(i, "fell" if 3 <= i < 25 else "ok", 10.0) for i in range(40)]}, 10.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = multi_diff(fa, fb, events=["fell"], method="mcnemar_bh",
                            manifest_a=_manifest("A"), manifest_b=_manifest("B"))
    row = _cell(result, "fell", "c")
    p, n10, n01, pairs = _statsmodels_mcnemar(fa, fb, "fell")
    assert pairs == 40 and row["pairs"] == 40
    assert abs(row["p"] - p) <= 1e-12
    assert abs(row["delta"] - (n01 - n10) / pairs) <= 1e-12
    assert abs(row["delta"] - (row["rate_b"] - row["rate_a"])) <= 1e-12
    assert row["direction"] == "higher"


def test_pf4_14_an_unpaired_test_keeps_the_own_row_difference() -> None:
    fa, fb = _unmatched_pair()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = multi_diff(fa, fb, events=["fell"], method="fisher_bh",
                            manifest_a=_manifest("A"), manifest_b=_manifest("B"))
    row = _cell(result, "fell", "c")
    assert abs(row["delta"] - (12 / 32 - 16 / 32)) <= 1e-12


# ---------- PF4.16: the Wilson interval at its default, against statsmodels ----------


def test_pf4_16_the_default_wilson_interval_is_statsmodels_at_alpha_0_05_without_passing_z() -> None:
    """statsmodels documents ``proportion_confint(count, nobs, alpha=0.05, method="wilson")``; no z
    is passed on either side. A literal 1.96 misses by up to 9.2e-6; a 90% interval by far more."""
    from statsmodels.stats.proportion import proportion_confint

    from poisson_prove.stats import wilson

    for n in range(1, 61):
        for k in range(0, n + 1):
            w = wilson(k, n)
            ref_lo, ref_hi = proportion_confint(k, n, alpha=0.05, method="wilson")
            assert abs(w.lo - float(ref_lo)) <= 1e-12, (k, n)
            assert abs(w.hi - float(ref_hi)) <= 1e-12, (k, n)


# ---------- PF4.18: Westfall-Young on one scale ----------


def _reference_min_p(observed: np.ndarray, permuted: np.ndarray) -> tuple[np.ndarray, float]:
    """The definition, member by member: the reference set is the B permutations and the
    observed point."""
    n_perm, n_stat = permuted.shape
    p_obs = (1 + (permuted >= observed[None, :]).sum(axis=0)) / (n_perm + 1)
    rank = np.empty_like(permuted)
    for b in range(n_perm):
        for j in range(n_stat):
            count = int((permuted[:, j] >= permuted[b, j]).sum()) + int(observed[j] >= permuted[b, j])
            rank[b, j] = count / (n_perm + 1)
    omnibus = (1 + int((rank.min(axis=1) <= p_obs.min()).sum())) / (n_perm + 1)
    return p_obs, omnibus


@pytest.mark.parametrize("seed", [2, 3, 5, 12, 14])
def test_pf4_18_the_min_p_is_the_definition_with_the_observed_point_in_the_reference_set(seed: int) -> None:
    from poisson_prove.tree import _min_p

    rng = np.random.default_rng(seed)
    n_perm, n_stat = 19, 4
    permuted = rng.normal(size=(n_perm, n_stat))
    observed = rng.normal(size=n_stat) + 0.5
    if seed % 2 == 0:
        # Ties, as discrete statistics give: every value on a coarse grid. Seeds chosen where the
        # old scales and this definition give a different omnibus.
        permuted = np.round(permuted, 0)
        observed = np.round(observed, 0)
    p_obs, omnibus = _min_p(observed, permuted)
    ref_p, ref_omnibus = _reference_min_p(observed, permuted)
    np.testing.assert_allclose(np.asarray(p_obs, dtype=float), ref_p, rtol=0, atol=1e-15)
    assert abs(float(omnibus) - ref_omnibus) <= 1e-15, (omnibus, ref_omnibus)


def test_pf4_18_with_one_statistic_the_omnibus_is_that_statistics_p() -> None:
    from poisson_prove.tree import _min_p

    rng = np.random.default_rng(11)
    for _ in range(50):
        permuted = rng.normal(size=(39, 1))
        observed = rng.normal(size=1)
        p_obs, omnibus = _min_p(observed, permuted)
        assert abs(float(omnibus) - float(np.asarray(p_obs)[0])) <= 1e-15


# ---------- PF4.19: the Kaplan-Meier warning fires on the real condition ----------


def _one_competitor_frame() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """An independent statistics check's run: 'fell' at a random time, and one other outcome,
    'stuck', that ends about half the runs before the horizon at 10."""
    rng = np.random.default_rng(7)
    n = 400
    t_fell = rng.uniform(0, 20, n)
    t_stuck = np.where(rng.random(n) < 0.5, rng.uniform(0, 10, n), np.inf)
    t = np.minimum(np.minimum(t_fell, t_stuck), 10.0)
    outcome = np.where(t == t_fell, "fell", "stuck")
    df = pd.DataFrame(
        {"config_hash": "c0", "config": [{"x": 0}] * n, "replicate_index": range(n),
         "outcome": outcome, "t": t, "horizon": 10.0}
    )
    return df, t, outcome


@pytest.mark.parametrize("case", ["one-competitor-early", "others-only-at-the-horizon", "names-each-early-outcome",
                                  "aalen-johansen"])
def test_pf4_19_the_kaplan_meier_warning_names_each_outcome_that_ends_runs_early_and_only_then(case: str) -> None:
    """PF4.19's four cases as one test. One other
    outcome that ends runs early draws the warning (lifelines documents
    ``KaplanMeierFitter().fit(durations, event_observed)`` and ``AalenJohansenFitter().fit(durations,
    event_observed, event_of_interest)`` with the event coded as an integer per cause; they disagree
    there, which is what the warning is for); outcomes seen only at the horizon draw none; the warning
    names each outcome that ends runs early; Aalen-Johansen draws none."""
    from lifelines import AalenJohansenFitter, KaplanMeierFitter

    if case == "one-competitor-early":
        df, t, outcome = _one_competitor_frame()
        km = KaplanMeierFitter().fit(t, outcome == "fell")
        aj = AalenJohansenFitter(calculate_variance=False).fit(t, np.where(outcome == "fell", 1, 2), event_of_interest=1)
        km_incidence = float(1 - km.survival_function_at_times(10.0).iloc[0])
        aj_incidence = float(aj.cumulative_density_.iloc[-1, 0])
        assert km_incidence - aj_incidence > 0.05
        with pytest.warns(UserWarning) as record:
            survival.cell_table(df, "fell", method="km")
        assert any("stuck" in str(w.message) for w in record)
    elif case == "others-only-at-the-horizon":
        rows = []
        for i in range(30):
            if i < 10:
                rows.append((i, "fell", 1.0 + 0.1 * i))
            elif i < 20:
                rows.append((i, "survived", 5.0))
            else:
                rows.append((i, "stuck_at_limit", 5.0))
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            survival.cell_table(_frame({"c": rows}, 5.0), "fell", method="km")
    elif case == "names-each-early-outcome":
        rows = [(i, "fell", 1.0 + 0.1 * i) for i in range(5)]
        rows += [(5 + i, "timeout", 3.0) for i in range(5)]
        rows += [(10 + i, "survived", 5.0) for i in range(5)]
        with pytest.warns(UserWarning) as record:
            survival.cell_table(_frame({"c": rows}, 5.0), "fell", method="km")
        assert any("timeout" in str(w.message) for w in record)
    else:
        df, _, _ = _one_competitor_frame()
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            survival.cell_table(df, "fell", method="aj", events=["fell", "stuck"])


# ---------- PF4.21: the past-the-horizon edge has the module's own error ----------


def test_pf4_21_every_row_past_the_common_horizon_is_a_diff_error() -> None:
    """A real store cannot write this; a hand-built frame can. A's horizon is 5 and every row of
    both arms lies past it, so nothing is left to compare."""
    fa = _frame({"c": [(i, "fell", 6.0 + i) for i in range(4)]}, 5.0)
    fb = _frame({"c": [(i, "fell", 7.0 + i) for i in range(4)]}, 10.0)
    with pytest.raises(DiffError) as caught:
        multi_diff(fa, fb, events=["fell"], method="fisher_bh")
    import re

    assert re.search(r"(?<![\d.])5(\.0)?(?![\d.])", str(caught.value)), str(caught.value)


# ---------- PF4.34: Holm for the verdict, Benjamini-Hochberg for the flags ----------


P_VECTORS = st.one_of(
    st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=1, max_size=60),
    st.lists(st.sampled_from([0.0, 1e-6, 0.001, 0.0028, 0.01, 0.02, 0.05, 0.5, 1.0]), min_size=1, max_size=60),
)


@settings(deadline=None, max_examples=300)
@given(p=P_VECTORS)
def test_pf4_34_the_two_corrections_are_statsmodels_holm_and_fdr_bh(p: list[float]) -> None:
    """statsmodels documents ``multipletests(pvals, alpha, method)`` returning the adjusted p-values
    second, with ``"holm"`` the step-down and ``"fdr_bh"`` Benjamini-Hochberg. A Holm rejection is
    always a Benjamini-Hochberg rejection."""
    from statsmodels.stats.multitest import multipletests

    arr = np.array(p, dtype=float)
    np.testing.assert_allclose(bh(arr, Q), multipletests(arr, alpha=Q, method="fdr_bh")[1], rtol=0, atol=1e-12)
    np.testing.assert_allclose(holm(arr, Q), multipletests(arr, alpha=Q, method="holm")[1], rtol=0, atol=1e-12)
    assert np.all((holm(arr, Q) < Q) <= (bh(arr, Q) < Q))


def test_pf4_34_an_adjusted_p_equal_to_q_neither_flags_nor_counts() -> None:
    """Both rules are strict. One paired condition, five discordant pairs all one way: the exact p is
    2 x 0.5^5 = 0.0625, so at q = 0.0625 Benjamini-Hochberg's and Holm's adjusted p both equal q, and
    the row is neither flagged nor counted."""
    a = {"c": _counts(0, 20)}
    b = {"c": _counts(5, 20)}
    result = _compare(a, b, method="mcnemar_bh", q=0.0625)
    row = _cell(result, "fell", "c")
    assert row["p"] == 0.0625 and row["q"] == 0.0625 and row["q_holm"] == 0.0625
    assert row["holm"] is False and row["direction"] == "unchanged"
    assert result.comparison_verdict() in ("no significant change", "too small to tell")


def _argon_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    """The methodology review's case: nine conditions fell far, 20 did not move, and one rose by a step-up margin. The
    rise's p (0 of 40 to 7 of 40, about 0.012) is under Benjamini-Hochberg's level at rank 10 of 30
    (0.0167) and over Holm's there (0.05 / 21)."""
    a = {f"down{i}": _counts(30, 40) for i in range(9)}
    b = {f"down{i}": _counts(2, 40) for i in range(9)}
    for i in range(20):
        a[f"same{i:02d}"] = b[f"same{i:02d}"] = _counts(5, 40)
    a["up"], b["up"] = _counts(0, 40), _counts(7, 40)
    return a, b


@pytest.mark.parametrize("kinds,word", [(None, "lower"), ({"fell": "failure"}, "safer"), ({"fell": "success"}, "worse")],
                         ids=["no-kind", "failure", "success"])
def test_pf4_34_the_word_counts_the_holm_rows_and_a_step_up_flag_does_not_make_a_trade(kinds: dict[str, str] | None, word: str) -> None:
    a, b = _argon_pair()
    result = _compare(a, b, kinds=kinds)
    up = _cell(result, "fell", "up")
    assert up["q"] < Q and not up["holm"] and up["q_holm"] >= Q, (up["q"], up["q_holm"])
    rows = [r for e in result.events for r in result.by_event[e].cells.to_dict(orient="records")]
    np.testing.assert_allclose([r["q_holm"] for r in rows], holm(np.array([r["p"] for r in rows]), Q), rtol=0, atol=1e-15)
    for r in rows:
        assert r["holm"] is bool(r["q_holm"] < Q)
        assert (not r["holm"]) or r["q"] < Q
    doc = result.to_json()
    assert doc["comparison_verdict"] == word
    assert (doc["verdict_rule"], doc["flag_rule"]) == ("holm", "benjamini-hochberg")
    assert doc["n_flagged_only"] == 1
    ev = doc["by_event"]["fell"]
    assert (ev["n_higher"], ev["n_lower"], ev["n_holm_higher"], ev["n_holm_lower"]) == (1, 9, 0, 9)
    if kinds is None:
        assert ev["n_holm_safer"] is None and ev["n_holm_worse"] is None
    else:
        assert (ev["n_holm_safer"], ev["n_holm_worse"]) == ((9, 0) if word == "safer" else (0, 9))


def test_pf4_34_with_flags_but_no_holm_row_the_word_is_a_nothing_moved_word() -> None:
    """Thirty conditions; three rose from 0 to 9 of 40 (Fisher p about 0.0026 each), under
    Benjamini-Hochberg's level at rank 3 of 30 (0.005) and over Holm's first step (0.05 / 30): three
    flags, and nothing counts for the verdict."""
    a = {f"s{i:02d}": _counts(5, 40) for i in range(27)}
    b = dict(a)
    for i in range(3):
        a[f"up{i}"], b[f"up{i}"] = _counts(0, 40), _counts(9, 40)
    result = _compare(a, b)
    doc = result.to_json()
    flagged = [r for r in result.by_event["fell"].cells.to_dict(orient="records") if r["q"] < Q]
    counted = [r for r in flagged if r["holm"]]
    assert flagged and not counted, ([r["q"] for r in flagged], [r["q_holm"] for r in flagged])
    assert doc["comparison_verdict"] in ("no significant change", "too small to tell")
    assert doc["n_flagged_only"] == len(flagged)


@pytest.mark.parametrize("threshold,word", [(0.25, "too small to tell"), (0.32, "no significant change")])
def test_pf4_34_the_nothing_moved_question_reads_the_rows_flagged_without_counting(threshold: float, word: str) -> None:
    """27 conditions of 200 a side that did not move (each tells a change under 0.2 both
    ways at q / 30) and three that rose from 0 to 9 of 40 (flagged, not counted), whose rise from 0 of 40
    is told only at about 0.299. The question reads every row that does not count, so the three decide
    between the two nothing-moved words, and the verdict limit is theirs."""
    a = {f"s{i:02d}": _counts(50, 200) for i in range(27)}
    b = dict(a)
    for i in range(3):
        a[f"up{i}"], b[f"up{i}"] = _counts(0, 40), _counts(9, 40)
    doc = _compare(a, b, env={"max_mde_accepted": threshold}).to_json()
    rise, _ = _ref_fisher_limits(0, 40, 40, Q / 30)
    s_rise, s_fall = _ref_fisher_limits(50, 200, 200, Q / 30)
    assert rise is not None and s_rise is not None and s_fall is not None
    assert max(s_rise, s_fall) < 0.25 < rise < 0.32
    assert doc["n_flagged_only"] == 3 and doc["comparison_verdict"] == word
    if word == "no significant change":
        assert abs(doc["verdict_limit"] - rise) <= GRID + 1e-12


def _ref_question(rise: float | None, fall: float | None, p_a: float, threshold: float) -> tuple[bool, float | None]:
    """PF4.29: T' = min(T, the larger room); each direction whose room is at least T' is asked, and the
    condition can tell when every asked limit exists and is at most T'. Returns (can tell, the largest
    limit asked)."""
    rooms = {"rise": 1.0 - p_a, "fall": p_a}
    t_prime = min(threshold, max(rooms.values()))
    asked = [v for way, v in (("rise", rise), ("fall", fall)) if rooms[way] >= t_prime - 1e-12]
    if any(v is None or v > t_prime + 1e-12 for v in asked):
        return False, None
    return True, max(asked) if asked else None


@pytest.mark.parametrize("threshold,word", [(0.24, "too small to tell"), (0.26, "no significant change")])
def test_pf4_40_the_verdict_limit_reads_the_verdict_level_limits_of_rows_that_move_together(threshold: float, word: str) -> None:
    """PF4.47: three conditions whose runs all ended in 'fell' or 'ok', both compared, so
    every row moves with its complement and its flag limit is at 2q/M; the question and the verdict limit
    read the limits at q/M, which are larger. At T = 0.24 every flag-level limit is under T and a
    verdict-level one is over it."""
    a = {f"c{i}": _counts(20 + 10 * i, 100) for i in range(3)}
    result = _compare(a, a, events=("fell", "ok"), env={"max_mde_accepted": threshold})
    doc = result.to_json()
    m = result.n_tests
    assert m == 6
    tells, reads, flag_level = [], [], []
    for i in range(3):
        k = 20 + 10 * i
        for events in (k, 100 - k):
            rise, fall = _ref_fisher_limits(events, 100, 100, Q / m)
            ok, read = _ref_question(rise, fall, events / 100, threshold)
            tells.append(ok)
            reads.append(read)
            flag_level += [v for v in _ref_fisher_limits(events, 100, 100, 2 * Q / m) if v is not None]
    assert max(flag_level) < 0.24 and all(tells) is (word == "no significant change")
    assert doc["comparison_verdict"] == word
    if word == "no significant change":
        assert abs(doc["verdict_limit"] - max(reads)) <= GRID + 1e-12
    else:
        assert doc["verdict_limit"] is None


# ---------- PF4.37: shares at the common horizon ----------


def test_pf4_37_the_shares_and_the_tests_count_by_the_common_horizon() -> None:
    """A ran to step 10, B to step 5. In 'late' half of A's runs fell after step 5: by the common
    horizon A had none, so its share is 0 of 40, as its rate and the test count it."""
    a = {"late": [(i, "fell", 6.0 + 0.1 * i) if i < 20 else (i, "ok", 10.0) for i in range(40)],
         "early": [(i, "fell", 1.0 + 0.1 * i) if i < 20 else (i, "ok", 10.0) for i in range(40)]}
    b = {"late": [(i, "ok", 5.0) for i in range(40)],
         "early": [(i, "fell", 1.0 + 0.1 * i) if i < 20 else (i, "ok", 5.0) for i in range(40)]}
    result = _compare(a, b, horizon_b=5.0)
    assert result.horizon == 5.0
    doc = result.to_json()
    cells = {c["config_hash"]: c for c in doc["by_event"]["fell"]["cells"]}
    late, early = cells["late"], cells["early"]
    assert late["events_a"] == 0 and late["share_a"]["value"] == 0.0 == late["rate_a"]
    assert abs(late["p"] - sps.fisher_exact([[0, 40], [0, 40]])[1]) <= 1e-12
    from statsmodels.stats.proportion import proportion_confint

    lo, hi = proportion_confint(0, 40, alpha=0.05, method="wilson")
    assert abs(late["share_a"]["lo"] - lo) <= 1e-12 and abs(late["share_a"]["hi"] - hi) <= 1e-12
    for c in (late, early):
        assert c["share_a_differs"] is False and c["share_b_differs"] is False
    assert early["share_a"]["value"] == 0.5 == early["share_b"]["value"]


# ---------- PF4.38: one case per condition ----------


@pytest.mark.parametrize(
    "meta_a,meta_b,refused",
    [
        ({"c": {"case_id": "t1"}, "d": {"case_id": "t2"}}, {"c": {"case_id": "t1"}, "d": {"case_id": "t2"}}, None),
        (None, None, None),
        ({"c": {}, "d": {}}, {"c": {}, "d": {}}, None),
        ({"c": {"case_id": "t1"}, "d": {"case_id": "t2"}}, {"c": {"case_id": "t9"}, "d": {"case_id": "t2"}}, "c"),
    ],
    ids=["one-id-each", "no-meta", "no-ids", "different-ids-by-arm"],
)
def test_pf4_38_a_condition_that_ran_more_than_one_case_is_refused(
    meta_a: dict[str, Any] | None, meta_b: dict[str, Any] | None, refused: str | None
) -> None:
    from poisson_prove.diff import MixedCases

    a = {"two-cases": _counts(3, 10), "one-case": _counts(4, 10)}
    rename = {"c": "two-cases", "d": "one-case"}
    meta_a = None if meta_a is None else {rename[k]: v for k, v in meta_a.items()}
    meta_b = None if meta_b is None else {rename[k]: v for k, v in meta_b.items()}
    if refused is None:
        _compare(a, a, meta_a=meta_a, meta_b=meta_b)
        return
    with pytest.raises(MixedCases) as caught:
        _compare(a, a, meta_a=meta_a, meta_b=meta_b)
    assert issubclass(MixedCases, DiffError)
    text = str(caught.value)
    assert rename[refused] in text and "one-case" not in text and "t1" in text and "t9" in text, text


def test_pf4_38_two_case_ids_inside_one_arms_condition_are_refused_and_runs_without_one_are_not_counted() -> None:
    from poisson_prove.diff import MixedCases

    rows = _counts(3, 10)
    fa = _frame({"c": rows}, 10.0)
    fa["case_id"] = ["t1" if i < 5 else "t2" for i in range(10)]
    fb = _frame({"c": rows}, 10.0)
    fb["case_id"] = ["t1"] * 10
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(MixedCases):
            multi_diff(fa, fb, events=["fell"], method="fisher_bh")
        fa["case_id"] = ["t1" if i < 5 else None for i in range(10)]
        multi_diff(fa, fb, events=["fell"], method="fisher_bh")


# ---------- PF4.41: a competing outcome that shifted, under log-rank ----------


def test_pf4_41_under_logrank_a_row_names_each_other_outcome_whose_share_moved() -> None:
    """In 'c' the competing ending 'stuck' rose from 5 to 25 of 60 while 'fell' stayed; 'ok' fell with
    it. Each other outcome's share is tested with scipy's ``fisher_exact`` at p < q, unadjusted."""
    def arm(fell: int, stuck: int, n: int) -> list[tuple[int, str, float]]:
        return [(i, "fell", 3.0) if i < fell else (i, "stuck", 2.0) if i < fell + stuck else (i, "ok", 10.0) for i in range(n)]

    a = {"c": arm(10, 5, 60), "quiet": arm(10, 5, 60)}
    b = {"c": arm(10, 25, 60), "quiet": arm(10, 5, 60)}
    result = _compare(a, b, method="logrank_bh")
    expected = []
    for other, (ka, kb) in {"ok": (45, 25), "stuck": (5, 25)}.items():
        if sps.fisher_exact([[ka, 60 - ka], [kb, 60 - kb]])[1] < Q:
            expected.append(other)
    assert list(_cell(result, "fell", "c")["competing_shift"]) == sorted(expected) == ["ok", "stuck"]
    assert list(_cell(result, "fell", "quiet")["competing_shift"]) == []
    unpaired = _compare(a, b, method="fisher_bh")
    assert _cell(unpaired, "fell", "c")["competing_shift"] is None


# ---------- PF4.42: intervals on the change, always ----------


def _restricted_mn_p(ea: int, na: int, eb: int, nb: int, delta: float) -> float:
    """Miettinen and Nurminen (1985): the score test of p_b - p_a = delta with the variance at the
    restricted maximum-likelihood rates and the N / (N - 1) factor; the restricted rates found with
    scipy's documented bounded scalar minimiser on the two binomial log-likelihoods."""
    from scipy.optimize import minimize_scalar

    lo, hi = max(0.0, -delta), min(1.0, 1.0 - delta)

    def nll(pa: float) -> float:
        pb = pa + delta
        out = 0.0
        for k, n, p in ((ea, na, pa), (eb, nb, pb)):
            out -= (k * math.log(max(p, 1e-300)) if k else 0.0) + ((n - k) * math.log(max(1 - p, 1e-300)) if n - k else 0.0)
        return out

    pa = minimize_scalar(nll, bounds=(lo, hi), method="bounded", options={"xatol": 1e-13}).x
    pb = pa + delta
    var = (pa * (1 - pa) / na + pb * (1 - pb) / nb) * (na + nb) / (na + nb - 1)
    excess = eb / nb - ea / na - delta
    if var <= 0:
        return 1.0 if abs(excess) < 1e-12 else 0.0
    return float(2 * sps.norm.sf(abs(excess) / math.sqrt(var)))


def _restricted_tango_p(b: int, c: int, n: int, delta: float) -> float:
    """Tango (1998): over n pairs, b where only A had the event and c where only B had it, the
    trinomial (b, c, the rest) with chances (psi, psi + delta, 1 - 2 psi - delta) under p_b - p_a =
    delta; Var(c - b) = n (2 psi + delta - delta^2) at the restricted psi, found with scipy."""
    from scipy.optimize import minimize_scalar

    rest = n - b - c
    lo, hi = max(0.0, -delta), (1.0 - delta) / 2.0

    def nll(psi: float) -> float:
        parts = ((b, psi), (c, psi + delta), (rest, 1 - 2 * psi - delta))
        return -sum(k * math.log(max(p, 1e-300)) for k, p in parts if k)

    psi = minimize_scalar(nll, bounds=(lo, hi), method="bounded", options={"xatol": 1e-13}).x
    var = n * (2 * psi + delta - delta * delta)
    excess = (c - b) - n * delta
    if var <= 0:
        return 1.0 if abs(excess) < 1e-12 else 0.0
    return float(2 * sps.norm.sf(abs(excess) / math.sqrt(var)))


def _invert(p_at: Callable[[float], float], point: float, alpha: float) -> tuple[float, float]:
    def edge(limit: float) -> float:
        if p_at(limit) > alpha:
            return limit
        inside, outside = point, limit
        for _ in range(60):
            mid = (inside + outside) / 2
            inside, outside = (mid, outside) if p_at(mid) > alpha else (inside, mid)
        return (inside + outside) / 2

    return edge(-1.0), edge(1.0)


@pytest.mark.parametrize("method", ["fisher_bh", "logrank_bh", "mcnemar_bh"])
@pytest.mark.parametrize("moved", [False, True], ids=["nothing-flagged", "some-flagged"])
def test_pf4_42_every_row_carries_its_interval_on_the_change_at_the_stated_level(method: str, moved: bool) -> None:
    a = {"c1": _counts(10, 40), "c2": _counts(6, 40), "c3": _counts(20, 40)}
    b = {"c1": _counts(30 if moved else 12, 40), "c2": _counts(6, 40), "c3": _counts(18, 40)}
    result = _compare(a, b, method=method)
    m = result.n_tests
    r = sum(1 for e in result.events for row in result.by_event[e].cells.to_dict(orient="records") if row["q"] < Q)
    assert (r > 0) is moved
    level = 1 - Q * max(r, 1) / m
    doc = result.to_json()
    assert abs(doc["interval_level"] - level) <= 1e-15
    assert doc["interval_rule"] == ("benjamini-yekutieli" if r else "bonferroni")
    assert len(doc["intervals"]) == m
    for name in a:
        row = _cell(result, "fell", name)
        assert abs(row["ci_level"] - level) <= 1e-15
        assert row["ci_method"] == ("tango" if method == "mcnemar_bh" else "miettinen-nurminen")
        if method == "mcnemar_bh":
            only_a = sum(oa == "fell" and ob != "fell" for (_, oa, _), (_, ob, _) in zip(a[name], b[name], strict=True))
            only_b = sum(oa != "fell" and ob == "fell" for (_, oa, _), (_, ob, _) in zip(a[name], b[name], strict=True))
            want = _invert(lambda d, x=only_a, y=only_b: _restricted_tango_p(x, y, 40, d), (only_b - only_a) / 40, 1 - level)
        else:
            ea, eb = row["events_a"], row["events_b"]
            want = _invert(lambda d, x=ea, y=eb: _restricted_mn_p(x, 40, y, 40, d), eb / 40 - ea / 40, 1 - level)
        assert abs(row["ci_lo"] - want[0]) <= 1e-6 and abs(row["ci_hi"] - want[1]) <= 1e-6, (name, row["ci_lo"], row["ci_hi"], want)


def test_pf4_42_an_interval_and_the_flag_answer_different_questions_and_both_are_carried() -> None:
    """At 0 of 40 against 4 of 40, one row, Fisher's p is about 0.116 (not flagged) while
    Miettinen-Nurminen's 95% interval excludes 0 (its lower bound is about 0.007); under log-rank, B's
    events far sooner at the same share are flagged while the interval on the shares at the horizon
    contains 0. Each row carries both as computed; the docs say why they can disagree (PF4.42)."""
    row = _cell(_compare({"c": _counts(0, 40)}, {"c": _counts(4, 40)}), "fell", "c")
    assert abs(row["p"] - sps.fisher_exact([[0, 40], [4, 36]])[1]) <= 1e-12 and row["q"] >= Q
    assert row["ci_lo"] > 0 and abs(row["ci_level"] - (1 - Q)) <= 1e-15
    result, _, _ = _logrank_result()
    lr = _cell(result, "fell", "equal_rates_b_sooner")
    assert lr["q"] < Q and lr["direction"] != "unchanged" and lr["events_a"] == lr["events_b"]
    assert lr["ci_lo"] < 0 < lr["ci_hi"]


ARMS = st.integers(min_value=1, max_value=60)
ALPHAS = st.sampled_from([0.05, Q / 18, 0.2])


@settings(deadline=None, max_examples=40, suppress_health_check=[HealthCheck.too_slow])
@given(na=ARMS, nb=ARMS, fa=st.floats(0, 1), fb=st.floats(0, 1), alpha=ALPHAS)
@example(na=40, nb=40, fa=0.0, fb=0.0, alpha=0.05)
@example(na=40, nb=40, fa=1.0, fb=1.0, alpha=0.05)
@example(na=40, nb=40, fa=0.0, fb=1.0, alpha=0.05)
@example(na=3, nb=57, fa=0.34, fb=0.9, alpha=Q / 18)
@example(na=57, nb=3, fa=0.9, fb=0.34, alpha=0.2)
@example(na=1, nb=1, fa=0.0, fb=1.0, alpha=0.05)
def test_pf4_42_the_miettinen_nurminen_interval_on_any_arms(na: int, nb: int, fa: float, fb: float, alpha: float) -> None:
    """On any arms, uneven both ways, 0% and 100% included: the reference's inversion, within [-1, 1]
    and holding the point estimate, the arms swapped give the interval negated, and a smaller alpha a
    wider interval."""
    ea, eb = round(fa * na), round(fb * nb)
    lo, hi = interval_rd(ea, na, eb, nb, alpha=alpha)
    point = eb / nb - ea / na
    assert -1 - 1e-12 <= lo <= point + 1e-6 and point - 1e-6 <= hi <= 1 + 1e-12, (lo, point, hi)
    want = _invert(lambda d: _restricted_mn_p(ea, na, eb, nb, d), point, alpha)
    assert abs(lo - want[0]) <= 1e-6 and abs(hi - want[1]) <= 1e-6, ((lo, hi), want)
    s_lo, s_hi = interval_rd(eb, nb, ea, na, alpha=alpha)
    assert abs(s_lo + hi) <= 1e-6 and abs(s_hi + lo) <= 1e-6
    w_lo, w_hi = interval_rd(ea, na, eb, nb, alpha=alpha / 2)
    assert w_lo <= lo + 1e-9 and w_hi >= hi - 1e-9


@settings(deadline=None, max_examples=40, suppress_health_check=[HealthCheck.too_slow])
@given(n=st.integers(min_value=1, max_value=60), fb=st.floats(0, 1), fc=st.floats(0, 1), alpha=ALPHAS)
@example(n=40, fb=0.0, fc=0.0, alpha=0.05)
@example(n=40, fb=0.0, fc=1.0, alpha=0.05)
@example(n=40, fb=1.0, fc=0.0, alpha=Q / 18)
@example(n=1, fb=0.0, fc=1.0, alpha=0.05)
def test_pf4_42_the_tango_interval_on_any_pairs(n: int, fb: float, fc: float, alpha: float) -> None:
    """Over any n pairs with b where only A had the event and c where only B had it (0 and all
    included): the reference's inversion, within [-1, 1] and holding (c - b) / n, b and c swapped give
    the interval negated, and a smaller alpha a wider interval."""
    b = round(fb * n)
    c = round(fc * (n - b))
    lo, hi = interval_rd_paired(b, c, n, alpha=alpha)
    point = (c - b) / n
    assert -1 - 1e-12 <= lo <= point + 1e-6 and point - 1e-6 <= hi <= 1 + 1e-12, (lo, point, hi)
    want = _invert(lambda d: _restricted_tango_p(b, c, n, d), point, alpha)
    assert abs(lo - want[0]) <= 1e-6 and abs(hi - want[1]) <= 1e-6, ((lo, hi), want)
    s_lo, s_hi = interval_rd_paired(c, b, n, alpha=alpha)
    assert abs(s_lo + hi) <= 1e-6 and abs(s_hi + lo) <= 1e-6
    w_lo, w_hi = interval_rd_paired(b, c, n, alpha=alpha / 2)
    assert w_lo <= lo + 1e-9 and w_hi >= hi - 1e-9


def test_pf4_42_with_unmatched_runs_the_paired_interval_is_tangos_on_the_matched_pairs() -> None:
    """PF4.14's unmatched design: 20 matched pairs, none where only A had the event and 8 where only B
    did; the 12 unmatched runs a side are not in the interval."""
    fa, fb = _unmatched_pair()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = multi_diff(fa, fb, events=["fell"], method="mcnemar_bh", manifest_a=_manifest("A"), manifest_b=_manifest("B"))
    row = _cell(result, "fell", "c")
    alpha = 1 - row["ci_level"]
    want = _invert(lambda d: _restricted_tango_p(0, 8, 20, d), 8 / 20, alpha)
    assert row["ci_method"] == "tango"
    assert abs(row["ci_lo"] - want[0]) <= 1e-6 and abs(row["ci_hi"] - want[1]) <= 1e-6, (row["ci_lo"], row["ci_hi"], want)
    assert (row["ci_lo"], row["ci_hi"]) == pytest.approx(interval_rd_paired(0, 8, 20, alpha=alpha), abs=1e-12)


def test_pf4_42_the_public_interval_functions_are_the_ones_the_rows_carry() -> None:
    a = {"c": _counts(10, 40)}
    b = {"c": _counts(25, 40)}
    for method in ("fisher_bh", "mcnemar_bh"):
        row = _cell(_compare(a, b, method=method), "fell", "c")
        alpha = 1 - row["ci_level"]
        got = interval_rd(10, 40, 25, 40, alpha=alpha) if method == "fisher_bh" else interval_rd_paired(0, 15, 40, alpha=alpha)
        assert (row["ci_lo"], row["ci_hi"]) == pytest.approx(got, abs=1e-12)


# ---------- PF4.44: fragility, the fewest outcomes that would change the word ----------


OUTSIDE = "flipped"  # an outcome outside the compared events, which no run had


def _flipped(cells: dict[str, list[tuple[int, str, float]]], flips: dict[tuple[str, int], str]) -> dict[str, list[tuple[int, str, float]]]:
    """The runs named in ``flips`` take the outcome given there, keeping their times."""
    return {name: [(rep, flips.get((name, rep), outcome), t) for rep, outcome, t in rows] for name, rows in cells.items()}


def _word(a: dict[str, Any], b: dict[str, Any], method: str, kinds: dict[str, str] | None, events: Sequence[str] = ("fell",)) -> str:
    return _compare(a, b, method=method, kinds=kinds, events=events).comparison_verdict()


def _exhaustive_fragility(a: dict[str, Any], b: dict[str, Any], method: str, kinds: dict[str, str] | None, upto: int,
                          events: Sequence[str] = ("fell",)) -> int | None:
    """Every set of flips of up to ``upto`` stored outcomes, both runs, through Prove's comparison. A flip
    moves one row: a run that ended in a compared event is made to end outside them, and a
    run that ended outside them in the first compared event (the designs here with such runs compare one)."""
    word = _word(a, b, method, kinds, events)

    def target(outcome: str) -> str:
        return OUTSIDE if outcome in events else events[0]

    runs = [("a", name, rep, o) for name, rows in a.items() for rep, o, _ in rows] + [
        ("b", name, rep, o) for name, rows in b.items() for rep, o, _ in rows]
    for size in range(1, upto + 1):
        for chosen in itertools.combinations(runs, size):
            fa = _flipped(a, {(n, r): target(o) for arm, n, r, o in chosen if arm == "a"})
            fb = _flipped(b, {(n, r): target(o) for arm, n, r, o in chosen if arm == "b"})
            if _word(fa, fb, method, kinds, events) != word:
                return size
    return None


def _apply_witness(a: dict[str, Any], b: dict[str, Any], flips: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The flips a result names, applied: ``to: event`` gives the run the row's event, ``to: not event``
    an outcome outside the compared events. Each run is named once."""
    chosen: dict[str, dict[tuple[str, int], str]] = {"a": {}, "b": {}}
    for flip in flips:
        assert flip["run"] in ("a", "b") and flip["to"] in ("event", "not event"), flip
        key = (flip["config_hash"], int(flip["replicate_index"]))
        assert key not in chosen[flip["run"]], flip
        chosen[flip["run"]][key] = flip["event"] if flip["to"] == "event" else OUTSIDE
    return _flipped(a, chosen["a"]), _flipped(b, chosen["b"])


FRAGILE = {
    "fisher-higher": ({"c": _counts(0, 8)}, {"c": _counts(7, 8)}, "fisher_bh", None),
    "fisher-nothing-moved": ({"c": _counts(1, 6)}, {"c": _counts(1, 6)}, "fisher_bh", None),
    "paired-knife-edge": ({"c": _counts(0, 8)}, {"c": _counts(6, 8)}, "mcnemar_bh", {"fell": "failure"}),
    "paired-two-conditions": ({"c": _counts(0, 8), "d": _counts(0, 8)}, {"c": _counts(8, 8), "d": _counts(0, 8)}, "mcnemar_bh", None),
}


def test_pf4_44_a_design_no_flips_can_move_has_no_fragility() -> None:
    """Six pairs over two rows: no result can be flagged (2 x 0.5^6 is not below 0.025) and no limit
    exists, so no set of flips changes the word."""
    doc = _compare({"c": _counts(1, 6), "d": _counts(0, 6)}, {"c": _counts(6, 6), "d": _counts(0, 6)}, method="mcnemar_bh").to_json()
    assert doc["fragility"] is None and isinstance(doc["fragility_note"], str) and doc["fragility_flips"] == []


@pytest.mark.parametrize("case", list(FRAGILE))
def test_pf4_44_fragility_is_the_fewest_flips_that_change_the_word_found_exhaustively(case: str) -> None:
    a, b, method, kinds = FRAGILE[case]
    doc = _compare(a, b, method=method, kinds=kinds).to_json()
    got = doc["fragility"]
    assert isinstance(got, int) and got >= 1 and doc["fragility_exact"] is True
    assert _exhaustive_fragility(a, b, method, kinds, got) == got
    assert len(doc["fragility_flips"]) == got


def _count_space_fragility(cells_a: dict[str, tuple[int, int]], cells_b: dict[str, tuple[int, int]], kinds: dict[str, str] | None,
                           env: dict[str, Any] | None, upto: int) -> int | None:
    """Fisher reads counts only, so a set of flips is a net change of events per condition and arm.
    Every vector of net changes of total size up to ``upto``, through Prove's comparison."""
    def build(cells: dict[str, tuple[int, int]], shift: dict[str, int]) -> dict[str, Any]:
        return {name: _counts(k + shift.get(name, 0), n) for name, (k, n) in cells.items()}

    def word(sa: dict[str, int], sb: dict[str, int]) -> str:
        fa, fb = build(cells_a, sa), build(cells_b, sb)
        return _compare(fa, fb, kinds=kinds, env=env).comparison_verdict()

    base = word({}, {})
    slots = [("a", n, k, m) for n, (k, m) in cells_a.items()] + [("b", n, k, m) for n, (k, m) in cells_b.items()]
    for size in range(1, upto + 1):
        for alloc in itertools.product(range(-size, size + 1), repeat=len(slots)):
            if sum(abs(x) for x in alloc) != size:
                continue
            if any(not 0 <= k + x <= m for (_, _, k, m), x in zip(slots, alloc, strict=True)):
                continue
            sa = {n: x for (arm, n, _, _), x in zip(slots, alloc, strict=True) if arm == "a"}
            sb = {n: x for (arm, n, _, _), x in zip(slots, alloc, strict=True) if arm == "b"}
            if word(sa, sb) != base:
                return size
    return None


@pytest.mark.parametrize(
    "cells_a,cells_b,kinds,env,want",
    [
        ({"c1": (0, 8), "c2": (8, 8)}, {"c1": (8, 8), "c2": (0, 8)}, {"fell": "failure"}, None, None),
        # 5 of 30 can just tell a rise of 0.37 (limit 0.3666); one more event in A puts its limit at 0.3757.
        ({"c": (5, 30)}, {"c": (5, 30)}, None, {"max_mde_accepted": 0.37}, 1),
        # 6 of 30 cannot (0.3757); one fewer event in A can.
        ({"c": (6, 30)}, {"c": (6, 30)}, None, {"max_mde_accepted": 0.37}, 1),
    ],
    ids=["trade", "no-change-by-a-limit-crossing", "too-small-by-a-limit-crossing"],
)
def test_pf4_44_on_counts_the_fewest_flips_include_a_limit_crossing_the_threshold(
    cells_a: dict[str, tuple[int, int]], cells_b: dict[str, tuple[int, int]], kinds: dict[str, str] | None,
    env: dict[str, Any] | None, want: int | None,
) -> None:
    """Fisher reads counts only, so the search over net changes per condition and arm is exhaustive;
    the last two pairs change their word only by moving a limit across the threshold."""
    a = {n: _counts(k, m) for n, (k, m) in cells_a.items()}
    b = {n: _counts(k, m) for n, (k, m) in cells_b.items()}
    doc = _compare(a, b, kinds=kinds, env=env).to_json()
    got = doc["fragility"]
    assert isinstance(got, int) and got >= 1
    assert want is None or got == want
    assert _count_space_fragility(cells_a, cells_b, kinds, env, got) == got


@pytest.mark.parametrize("method", ["fisher_bh", "mcnemar_bh", "logrank_bh"])
def test_pf4_44_the_flips_it_names_change_the_word(method: str) -> None:
    a = {f"c{i}": _counts(10 + i, 50, t_event=1.0 + i) for i in range(4)}
    b = {"c0": _counts(30, 50, t_event=1.0), **{f"c{i}": _counts(10 + i, 50, t_event=1.0 + i) for i in range(1, 4)}}
    doc = _compare(a, b, method=method).to_json()
    flips = doc["fragility_flips"]
    assert doc["fragility"] == len(flips) >= 1
    assert doc["fragility_exact"] is (method != "logrank_bh")
    assert all(flip["event"] == "fell" for flip in flips)
    fa, fb = _apply_witness(a, b, flips)
    assert _compare(fa, fb, method=method).to_json()["comparison_verdict"] != doc["comparison_verdict"]


@pytest.mark.parametrize("method,threshold", [("fisher_bh", 0.37), ("mcnemar_bh", 0.375)], ids=["fisher", "paired"])
def test_pf4_44_the_flips_it_names_for_a_limit_crossing_change_the_word(method: str, threshold: float) -> None:
    """5 of 30 in both runs at T just above the condition's rise limit (Fisher 0.3666, paired 0.3713;
    its fall's room is under T, so only the rise is asked): one more event in A puts the limit over T, so
    one flip in A turns "no significant change" into "too small to tell", and the result names it."""
    a = {"c": _counts(5, 30)}
    env = {"max_mde_accepted": threshold}
    doc = _compare(a, a, method=method, env=env).to_json()
    assert doc["comparison_verdict"] == "no significant change" and doc["fragility"] == 1
    flips = doc["fragility_flips"]
    assert len(flips) == 1 and flips[0]["run"] == "a" and flips[0]["to"] == "event"
    fa, fb = _apply_witness(a, a, flips)
    assert _compare(fa, fb, method=method, env=env).comparison_verdict() == "too small to tell"


def test_pf4_44_with_two_compared_events_a_flip_moves_one_row_and_the_search_says_it_is_not_exact() -> None:
    """Five a side whose runs all ended in 'fell' or 'ok', both compared, 'fell' rising from 0
    to 5 of 5, so both rows count and the word is worse. One flip from 'fell' to 'ok' in B would move
    both rows and change the word; flips that move one row need two, one per row. The result gives the
    one-row count, found exhaustively here, and ``fragility_exact`` false."""
    a, b = {"c": _counts(0, 5)}, {"c": _counts(5, 5)}
    kinds = {"fell": "failure", "ok": "success"}
    events = ("fell", "ok")
    doc = _compare(a, b, events=events, kinds=kinds).to_json()
    assert doc["comparison_verdict"] == "worse"
    assert doc["fragility"] == 2 == _exhaustive_fragility(a, b, "fisher_bh", kinds, 2, events=events)
    assert doc["fragility_exact"] is False and len(doc["fragility_flips"]) == 2
    fa, fb = _apply_witness(a, b, doc["fragility_flips"])
    assert _word(fa, fb, "fisher_bh", kinds, events) != "worse"
    between = {"c": [(rep, "ok" if rep == 0 else o, t) for rep, o, t in b["c"]]}
    assert _word(a, between, "fisher_bh", kinds, events) != "worse"


@settings(deadline=None, max_examples=10, suppress_health_check=[HealthCheck.too_slow])
@given(na=st.integers(5, 7), nb=st.integers(5, 7), fa=st.floats(0, 1), fb=st.floats(0, 1),
       kinds=st.sampled_from([None, {"fell": "failure"}]))
@example(na=5, nb=7, fa=0.0, fb=1.0, kinds=None)
@example(na=7, nb=5, fa=0.5, fb=0.5, kinds={"fell": "failure"})
def test_pf4_44_on_any_small_condition_fragility_is_the_exhaustive_count(na: int, nb: int, fa: float, fb: float,
                                                                        kinds: dict[str, str] | None) -> None:
    """One condition, uneven arms both ways: the fragility equals the search over every net change of
    the counts (exhaustive for Fisher, which reads counts only), null when no change of the word exists."""
    ka, kb = round(fa * na), round(fb * nb)
    doc = _compare({"c": _counts(ka, na)}, {"c": _counts(kb, nb)}, kinds=kinds).to_json()
    got = doc["fragility"]
    want = _count_space_fragility({"c": (ka, na)}, {"c": (kb, nb)}, kinds, None, got if got is not None else na + nb)
    assert got == want, (ka, na, kb, nb, got, want)
    assert (got is None) is (doc["fragility_note"] is not None)


# ---------- PF4.45: groups test spread as well as the mean ----------


def test_pf4_45_a_group_whose_conditions_moved_both_ways_is_flagged_by_its_spread() -> None:
    """Group x: two conditions rose by 0.4 and two fell by 0.4, so its mean change is 0; group y did
    not move. The group's test is the dual statistic, and x's dispersion flags it."""
    from poisson_prove import tree

    def frame(cells: dict[tuple[str, int], int]) -> pd.DataFrame:
        rows = []
        for (g, i), k in cells.items():
            for r in range(60):
                rows.append({"config_hash": f"{g}{i}", "config": {"g": g, "i": i}, "replicate_index": r, "seed": r,
                             "outcome": "fell" if r < k else "ok", "t": 1.0 if r < k else 10.0, "horizon": 10.0})
        return pd.DataFrame(rows)

    a_cells = {("x", 0): 12, ("x", 1): 12, ("x", 2): 42, ("x", 3): 42, ("y", 0): 20, ("y", 1): 20, ("y", 2): 20, ("y", 3): 20}
    b_cells = {("x", 0): 36, ("x", 1): 36, ("x", 2): 18, ("x", 3): 18, ("y", 0): 20, ("y", 1): 20, ("y", 2): 20, ("y", 3): 20}
    fa, fb = frame(a_cells), frame(b_cells)
    ma = RunManifest(run_id="A", target_id="pf4", t_unit="steps", run_salt="s", axis_types={"g": "categorical", "i": "categorical"},
                     backend="local", environment={})
    mb = RunManifest(run_id="B", target_id="pf4", t_unit="steps", run_salt="t", axis_types={"g": "categorical", "i": "categorical"},
                     backend="local", environment={})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        multi = multi_diff(fa, fb, events=["fell"], method="fisher_bh", manifest_a=ma, manifest_b=mb)
        result = tree.tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, by="g", n_permutations=999, seed=3,
                           max_group_mde=0.99)
    assert result.grouping.key == "g"
    groups = {g.label: g for g in result.fault_lines.groups}
    x = groups["x"]
    assert abs(x.location["fell"]) <= 1e-12 and x.dispersion["fell"] > 0.3
    assert x.p_dispersion is not None and x.p_dispersion["fell"] < Q / 2
    assert x.p_location is not None and x.p_location["fell"] > 0.5
    assert x.rejects is True and groups["y"].rejects is False
    assert result.fault_lines.mde_basis == "unconditional"


def test_pf4_45_a_groups_limit_follows_its_own_conditions_baselines() -> None:
    """Three groups of three conditions, 60 a side; group 'far' moved a long way, so the root rejects
    and the groups are formed. Only group x's baselines differ between the two designs (3 of 60 against
    30 of 60); every other cell, size and change is the same, so x's limit must differ between them: it
    reads each of its cells' own baseline, never one rate for every cell. (Which way it moves also
    depends on the other cells, through the root, so only the difference is pinned.)"""
    from poisson_prove import tree

    def frame(cells: dict[tuple[str, int], int]) -> pd.DataFrame:
        rows = []
        for (g, i), k in cells.items():
            for r in range(60):
                rows.append({"config_hash": f"{g}{i}", "config": {"g": g, "i": i}, "replicate_index": r, "seed": r,
                             "outcome": "fell" if r < k else "ok", "t": 1.0 if r < k else 10.0, "horizon": 10.0})
        return pd.DataFrame(rows)

    ma = RunManifest(run_id="A", target_id="pf4", t_unit="steps", run_salt="s", axis_types={"g": "categorical", "i": "categorical"},
                     backend="local", environment={})
    mb = RunManifest(run_id="B", target_id="pf4", t_unit="steps", run_salt="t", axis_types={"g": "categorical", "i": "categorical"},
                     backend="local", environment={})

    def limit_of_x(x_events: int) -> float:
        a_cells = {**{("x", i): x_events for i in range(3)}, **{("mid", i): 18 for i in range(3)}, **{("far", i): 6 for i in range(3)}}
        b_cells = {**a_cells, **{("far", i): 54 for i in range(3)}}
        fa, fb = frame(a_cells), frame(b_cells)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            multi = multi_diff(fa, fb, events=["fell"], method="fisher_bh", manifest_a=ma, manifest_b=mb)
            result = tree.tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, by="g", n_permutations=999, seed=3,
                               max_group_mde=0.99)
        assert result.grouping.key == "g"
        return float({g.label: g for g in result.fault_lines.groups}["x"].mde)

    low, mid = limit_of_x(3), limit_of_x(30)
    assert abs(low - mid) > 0.01, (low, mid)


# ---------- PF4.46: errored episodes that differ between the runs ----------


def test_pf4_46_conditions_whose_errored_share_differs_are_listed_with_their_counts() -> None:
    """scipy's ``fisher_exact`` on errored and not, per compared condition, at p < q unadjusted."""
    a = {"c": _counts(5, 40), "d": _counts(5, 40)}
    b = {"c": _counts(5, 30) + [(30 + i, None, 1.0) for i in range(10)], "d": _counts(5, 39) + [(39, None, 1.0)]}
    result = _compare(a, b)
    listed = {e["config_hash"]: e for e in result.to_json()["errors_differ"]}
    for name, (ea, ra, eb, rb) in {"c": (0, 40, 10, 40), "d": (0, 40, 1, 40)}.items():
        p = sps.fisher_exact([[ea, ra - ea], [eb, rb - eb]])[1]
        assert (name in listed) is bool(p < Q), (name, p)
    assert (listed["c"]["errored_a"], listed["c"]["rows_a"], listed["c"]["errored_b"], listed["c"]["rows_b"]) == (0, 40, 10, 40)
    quiet = _compare(a, a)
    assert quiet.to_json()["errors_differ"] == []


# ---------- PF4.47: outcomes that move together ----------


def test_pf4_47_exact_complements_are_flagged_together_and_their_limit_is_at_twice_the_level() -> None:
    """'fell' and 'ok' are the only outcomes in 'c', so their Fisher p-values are identical and a lone
    change in 'c' moves both rows: each row's limit is at 2q/M and names the other event; the verdict's
    limits stay at q/M. In 'd' a third outcome breaks the pairing."""
    a = {"c": _counts(30, 100), "d": _counts(30, 90) + [(90 + i, "stuck", 2.0) for i in range(10)]}
    result = _compare(a, a, events=("fell", "ok"))
    m = result.n_tests
    assert m == 4
    for event, other in (("fell", "ok"), ("ok", "fell")):
        c = _cell(result, event, "c")
        assert c["mde_moves_with"] == other and abs(c["mde_level"] - 2 * Q / m) <= 1e-15
        k = 30 if event == "fell" else 70
        rise, fall = _ref_fisher_limits(k, 100, 100, 2 * Q / m)
        _assert_limit(c["mde_rise"], rise, (event, "rise"))
        _assert_limit(c["mde_fall"], fall, (event, "fall"))
        vrise, vfall = _ref_fisher_limits(k, 100, 100, Q / m)
        _assert_limit(c["mde_rise_verdict"], vrise, (event, "verdict rise"))
        _assert_limit(c["mde_fall_verdict"], vfall, (event, "verdict fall"))
        d = _cell(result, event, "d")
        assert d["mde_moves_with"] is None and abs(d["mde_level"] - Q / m) <= 1e-15
        assert (d["mde_rise_verdict"], d["mde_fall_verdict"]) == (d["mde_rise"], d["mde_fall"])
    logrank = _compare(a, a, events=("fell", "ok"), method="logrank_bh")
    assert _cell(logrank, "fell", "c")["mde_moves_with"] is None


@settings(deadline=None, max_examples=15, suppress_health_check=[HealthCheck.too_slow])
@given(na=st.integers(2, 60), nb=st.integers(2, 60), fa=st.floats(0, 1), fb=st.floats(0, 1))
@example(na=5, nb=50, fa=0.2, fb=0.2)
@example(na=50, nb=5, fa=1.0, fb=0.0)
@example(na=40, nb=40, fa=0.0, fb=0.5)
def test_pf4_47_on_any_arms_rows_that_move_together_carry_both_levels_limits(na: int, nb: int, fa: float, fb: float) -> None:
    """Uneven arms both ways, 0% and 100% included: in 'c' every run ended in 'fell' or 'ok', in 'd' one
    of A's ended in 'stuck'. Over the four rows, c's limits are Fisher's at 2q/4 from its own baseline
    (the complement's for 'ok'), its verdict limits at q/4; d's are at q/4 and equal its verdict limits."""
    ka, kb = round(fa * na), round(fb * nb)
    a = {"c": _counts(ka, na), "d": _counts(ka, na) + [(na, "stuck", 2.0)]}
    b = {"c": _counts(kb, nb), "d": _counts(kb, nb)}
    result = _compare(a, b, events=("fell", "ok"))
    assert result.n_tests == 4
    for event, events_a in (("fell", ka), ("ok", na - ka)):
        c = _cell(result, event, "c")
        assert c["mde_moves_with"] == ("ok" if event == "fell" else "fell")
        for key, level in (("", 2 * Q / 4), ("_verdict", Q / 4)):
            rise, fall = _ref_fisher_limits(events_a, na, nb, level)
            _assert_limit(c[f"mde_rise{key}"], rise, (event, "rise", key))
            _assert_limit(c[f"mde_fall{key}"], fall, (event, "fall", key))
        d = _cell(result, event, "d")
        assert d["mde_moves_with"] is None and abs(d["mde_level"] - Q / 4) <= 1e-15
        rise, fall = _ref_fisher_limits(events_a, na + 1, nb, Q / 4)
        _assert_limit(d["mde_rise"], rise, (event, "d rise"))
        _assert_limit(d["mde_fall"], fall, (event, "d fall"))
        assert (d["mde_rise_verdict"], d["mde_fall_verdict"]) == (d["mde_rise"], d["mde_fall"])


@pytest.mark.parametrize("kinds,word", [(None, "mixed"), ({"fell": "failure", "ok": "success"}, "worse")], ids=["no-kinds", "kinds"])
def test_pf4_47_a_lone_change_in_rows_that_move_together_reads_mixed_without_kinds(kinds: dict[str, str] | None, word: str) -> None:
    """In 'c', 'fell' rose from 30 to 70 of 100, so 'ok' fell with it and both rows count.
    Without kinds that is a row higher and a row lower, which PF4.20's direction words call mixed; with
    the kinds both are worse."""
    a = {"c": _counts(30, 100), "d": _counts(30, 100)}
    b = {"c": _counts(70, 100), "d": _counts(30, 100)}
    result = _compare(a, b, events=("fell", "ok"), kinds=kinds)
    assert _cell(result, "fell", "c")["holm"] and _cell(result, "ok", "c")["holm"]
    assert result.comparison_verdict() == word


def test_pf4_47_on_rows_that_move_together_flaggable_and_the_notes_are_at_their_own_level() -> None:
    """One condition of 4 a side whose runs all ended in 'fell' or 'ok', both compared
    (M = 2). Fisher's smallest p, 2 / C(8, 4), about 0.029, is under the rows' own level 2q/M = 0.05 and
    over the verdict's q/M = 0.025: the rows are flaggable and their limits and notes read at 0.05; the
    verdict-level limits are null, so the question cannot tell."""
    a = {"c": _counts(2, 4)}
    result = _compare(a, a, events=("fell", "ok"))
    p_min = sps.fisher_exact([[4, 0], [0, 4]])[1]
    assert Q / 2 < p_min < Q
    for event in ("fell", "ok"):
        c = _cell(result, event, "c")
        assert c["mde_moves_with"] is not None and abs(c["mde_level"] - Q) <= 1e-15
        assert abs(c["p_min"] - p_min) <= 1e-12 and c["flaggable"] is True
        rise, fall = _ref_fisher_limits(2, 4, 4, Q)
        for way, want in (("rise", rise), ("fall", fall)):
            _assert_limit(c[f"mde_{way}"], want, (event, way))
            assert (c[f"mde_{way}_note"] == "none detectable") is (want is None)
        assert _none(c["mde_rise_verdict"]) and _none(c["mde_fall_verdict"])
    assert result.comparison_verdict() == "too small to tell"


# ---------- PF4.33 and PF4.44: the cost ----------


def _timed(fn: Callable[[], Any]) -> float:
    import time

    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


@pytest.mark.parametrize(
    "case",
    [
        pytest.param("quickstart", id="quickstart-9x194"),
        pytest.param("large", id="one-condition-5000-a-side", marks=pytest.mark.slow),
    ],
)
def test_pf4_33_the_limits_and_the_fragility_cost_what_the_spec_allows_on_the_runner(
    case: str, record_property: Callable[[str, Any], None]
) -> None:
    """The limits of a comparison of the quickstart's shape (9 conditions by 2 events at 194 a side)
    within 2 s and its fragility within 5 s more; one condition of 5,000 runs a side within 5 s. Measured
    always and recorded; asserted only where ``POISSON_PROVE_TIMING=assert`` is set, never by
    wall clock on a laptop."""
    import os

    if case == "quickstart":
        def arm(k_fell: int, k_stuck: int, n: int) -> list[tuple[int, str, float]]:
            return [(i, "fell", 2.0) if i < k_fell else (i, "stuck", 3.0) if i < k_fell + k_stuck else (i, "ok", 10.0)
                    for i in range(n)]

        a = {f"c{i}": arm(20 + 5 * i, 30, 194) for i in range(9)}
        b = {f"c{i}": arm(20 + 5 * i + (40 if i == 0 else 0), 30, 194) for i in range(9)}
        result: list[Any] = []
        limits = _timed(lambda: result.append(_compare(a, b, events=("fell", "stuck"))))
        fragility = _timed(lambda: result[0].fragility)
        record_property("limits_seconds", round(limits, 3))
        record_property("fragility_seconds", round(fragility, 3))
        assert isinstance(result[0].fragility, int)
        if os.environ.get("POISSON_PROVE_TIMING") == "assert":
            assert limits < 2.0, limits
            assert fragility < 5.0, fragility
    else:
        seconds = _timed(lambda: _compare({"c": _counts(1500, 5000)}, {"c": _counts(1500, 5000)}))
        record_property("limits_seconds", round(seconds, 3))
        if os.environ.get("POISSON_PROVE_TIMING") == "assert":
            assert seconds < 5.0, seconds
