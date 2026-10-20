"""PF4, the statistics: the frozen tests at the library's level.

Written from the front-door spec's section 8 (8.2 to 8.5) and its invariants PF4.1 to PF4.21, the
last ten of which were added on 2026-10-20 from the statistics re-check ruled on that
day (``log/stats-recheck/README.md``). The build is written against this file and does not edit it.
``tests/test_pf4_surfaces.py`` holds the invariants a user reads on a screen or in a file; this file
holds the numbers underneath them.

**How each statistic is checked.** Every number is recomputed with an outside library (scipy,
statsmodels or lifelines) whose arguments are taken from that library's documentation, never from
Prove's code, and each test says which documented convention it uses. Where no library computes the
quantity (the Westfall-Young min-p over Prove's own statistics), the reference is the definition
the spec writes out, computed directly in the test, and a simulation checks the property the
definition exists for. Uneven arms and rates of 0% and 100% are covered wherever an estimator takes
them.

**Readings, named here.**

- ``poisson_prove.stats`` is created by PF4 with at least ``wilson``, ``WilsonInterval`` and
  ``WILSON_LEVEL`` (spec section 8.2: "the function sits in PF4's code; PF5's stats module exposes
  it unchanged"). PF5 adds the module's other names and its ``__all__``.
- The library's cell frames (``EventDiff.cells``) carry the new per-condition fields the spec names
  (``direction``, ``direction_note``, ``pairs``) as columns. Their ``verdict`` column is the
  library's own record and is not read here: what a reader sees is frozen in the surfaces file.
- A refused level raises ``ValueError``: the spec says only "refused", and a public function's
  bad argument is a ``ValueError`` in the standard library's sense.
- The Westfall-Young tests call ``tree._min_p(observed, permuted)`` by its current signature: it is
  the one function that holds the calibration, and no public path exposes the permutation draws.

**Lanes.** Every test here is fast except the two simulations, each a few seconds.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
import pytest

from poisson_prove import survival
from poisson_prove.diff import DiffError, mde_two_proportion, multi_diff
from poisson_prove.store import RunManifest

Q = 0.05
POWER = 0.8
#: The bisection in the references below stops at 1e-12; the two computations then differ only in
#: floating-point order, far below this.
TOL_MDE = 1e-7


# ---------- frames and manifests, built by hand ----------


def _frame(cells: dict[str, list[tuple[int, str | None, float]]], horizon: float) -> pd.DataFrame:
    """A raw store frame: one row per ``(replicate_index, outcome, t)`` in each named cell. The seed
    is the replicate index plus 1000 in both arms, so a pair of frames is a paired design."""
    rows = []
    for name, entries in cells.items():
        for rep, outcome, t in entries:
            rows.append(
                {
                    "config_hash": name,
                    "config": {"cell": name},
                    "replicate_index": rep,
                    "seed": 1000 + rep,
                    "outcome": outcome,
                    "t": t,
                    "horizon": horizon,
                }
            )
    return pd.DataFrame(rows)


def _manifest(run_id: str, salt: str = "shared-salt") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        target_id="pf4",
        t_unit="steps",
        run_salt=salt,
        axis_types={"cell": "categorical"},
        backend="local",
        environment={},
    )


def _cell(result: Any, event: str, name: str) -> dict[str, Any]:
    cells = result.by_event[event].cells
    rows = cells[cells["config_hash"] == name]
    assert len(rows) == 1, (name, list(cells["config_hash"]))
    return dict(rows.iloc[0].to_dict())


# ---------- PF4.1: the public Wilson interval states its level ----------


def test_pf4_1_wilson_returns_its_bounds_level_z_and_method_at_the_default_level() -> None:
    from scipy.stats import norm

    from poisson_prove.stats import WILSON_LEVEL, WilsonInterval, wilson

    assert WILSON_LEVEL == 0.95
    w = wilson(10, 32)
    assert isinstance(w, WilsonInterval)
    assert w.level == 0.95
    assert w.method == "wilson"
    # scipy documents ``norm.isf(q)`` as the inverse survival function: the two-sided 95% quantile
    # leaves 0.025 in the upper tail.
    assert abs(w.z - float(norm.isf(0.025))) <= 1e-12
    lo, hi = survival.wilson(10, 32, z=w.z)
    assert abs(w.lo - lo) <= 1e-12 and abs(w.hi - hi) <= 1e-12


def test_pf4_1_wilson_at_another_level_returns_that_level_and_its_two_sided_quantile() -> None:
    from scipy.stats import norm

    from poisson_prove.stats import wilson

    for level in (0.90, 0.975, 0.5):
        w = wilson(7, 20, level=level)
        assert w.level == level
        assert abs(w.z - float(norm.isf((1.0 - level) / 2.0))) <= 1e-12
        lo, hi = survival.wilson(7, 20, z=w.z)
        assert abs(w.lo - lo) <= 1e-12 and abs(w.hi - hi) <= 1e-12


def test_pf4_1_wilson_bounds_equal_the_private_two_tuple_over_the_existing_grid() -> None:
    """The grid of ``test_m5_survival``'s Wilson tests (n up to 500, k from 0 to n), sampled on a
    fixed lattice so the comparison is the same on every run."""
    from poisson_prove.stats import wilson

    for n in (1, 2, 3, 5, 10, 32, 99, 100, 257, 500):
        for k in sorted({0, 1, n // 3, n // 2, n - 1, n} - {-1}):
            if not 0 <= k <= n:
                continue
            for level in (0.95, 0.90):
                w = wilson(k, n, level=level)
                lo, hi = survival.wilson(k, n, z=w.z)
                assert abs(w.lo - lo) <= 1e-12, (k, n, level)
                assert abs(w.hi - hi) <= 1e-12, (k, n, level)


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.5])
def test_pf4_1_a_level_outside_zero_and_one_is_refused(level: float) -> None:
    from poisson_prove.stats import wilson

    with pytest.raises(ValueError):
        wilson(3, 10, level=level)


def test_pf4_1_the_private_wilson_two_tuple_is_unchanged() -> None:
    out = survival.wilson(5, 10)
    assert isinstance(out, tuple) and len(out) == 2
    out_z = survival.wilson(5, 10, z=1.0)
    assert isinstance(out_z, tuple) and len(out_z) == 2
    assert out_z[1] - out_z[0] < out[1] - out[0]


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


# ---------- PF4.12: the detection limit pairs the changed rate with arm B ----------


def _guard(p_a: float, n_a: int) -> float:
    """Prove's documented continuity guard at a rate of exactly 0 or 1 (``0.5 / n_a``), applied to
    the reference too: it is a modelling choice, not the pairing under test."""
    if p_a <= 0.0:
        return 0.5 / n_a
    if p_a >= 1.0:
        return 1.0 - 0.5 / n_a
    return p_a


def _statsmodels_power(delta: float, p_a: float, n_a: int, n_b: int, alpha: float) -> float:
    """statsmodels documents ``power_proportions_2indep(diff, prop2, nobs1, ratio)`` as the power
    for ``p1 = prop2 + diff`` in sample 1 of size ``nobs1``, with ``nobs2 = ratio * nobs1``. The
    changed arm is B, so B is sample 1: ``nobs1 = n_b`` and ``ratio = n_a / n_b``."""
    from statsmodels.stats.proportion import power_proportions_2indep

    return float(
        power_proportions_2indep(
            delta, p_a, n_b, ratio=n_a / n_b, alpha=alpha, alternative="two-sided",
            return_results=False,
        )
    )


def _reference_mde(p_a: float, n_a: int, n_b: int) -> float | None:
    """The smallest rise of B over A detectable at ``Q`` and ``POWER``, by bisection on
    statsmodels' power; ``None`` when even the whole headroom is not detectable."""
    g = _guard(p_a, n_a)
    cap = 1.0 - g
    if _statsmodels_power(cap, g, n_a, n_b, Q) < POWER:
        return None
    lo, hi = 0.0, cap
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _statsmodels_power(mid, g, n_a, n_b, Q) >= POWER:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-12:
            break
    return hi


RATES = [0.0, 1 / 32, 0.1, 0.25, 0.5, 0.75, 0.9]
SIZES = [(32, 32), (100, 20), (20, 100), (32, 31), (32, 16), (16, 32), (300, 290)]


@pytest.mark.parametrize("n_a,n_b", SIZES, ids=[f"{a}-{b}" for a, b in SIZES])
def test_pf4_12_the_detection_limit_matches_statsmodels_with_its_documented_argument_order(
    n_a: int, n_b: int
) -> None:
    checked = 0
    for p_a in RATES:
        ref = _reference_mde(p_a, n_a, n_b)
        if ref is None:
            continue
        ours = mde_two_proportion(p_a, n_a, n_b, alpha=Q, power=POWER)
        assert abs(ours - ref) <= TOL_MDE, (p_a, n_a, n_b, ours, ref)
        checked += 1
    assert checked >= 4


def test_pf4_12_the_limit_on_uneven_arms_is_not_symmetric_in_the_two_sizes() -> None:
    """Swapping which arm is large changes the limit, and the two values are exactly the
    re-check's independent numbers (README section 1's table)."""
    big_a = mde_two_proportion(0.10, 100, 20, alpha=Q, power=POWER)
    big_b = mde_two_proportion(0.10, 20, 100, alpha=Q, power=POWER)
    assert abs(big_a - 0.2623) <= 5e-5, big_a
    assert abs(big_b - 0.2987) <= 5e-5, big_b


def _simulated_power(delta: float, p_a: float, n_a: int, n_b: int, reps: int, seed: int) -> float:
    """The pooled two-sided z-test, simulated: A ~ Bin(n_a, p_a), B ~ Bin(n_b, p_a + delta). No
    library's convention is involved."""
    from scipy.stats import norm

    rng = np.random.default_rng(seed)
    xa = rng.binomial(n_a, p_a, reps)
    xb = rng.binomial(n_b, p_a + delta, reps)
    pooled = (xa + xb) / (n_a + n_b)
    se = np.sqrt(pooled * (1.0 - pooled) * (1.0 / n_a + 1.0 / n_b))
    z = np.divide(xb / n_b - xa / n_a, se, out=np.zeros_like(se), where=se > 0)
    return float(np.mean(np.abs(z) > float(norm.isf(Q / 2.0))))


@pytest.mark.parametrize("p_a,n_a,n_b", [(0.1, 100, 20), (0.1, 20, 100), (0.5, 100, 20), (0.5, 20, 100)])
def test_pf4_12_a_simulated_test_reaches_the_target_power_at_the_reported_limit(
    p_a: float, n_a: int, n_b: int
) -> None:
    """The normal approximation is within about 0.015 of the simulated power at the right limit;
    the swapped pairing lands 0.04 to 0.09 away on these four (0.88, 0.71, 0.76, 0.85)."""
    delta = mde_two_proportion(p_a, n_a, n_b, alpha=Q, power=POWER)
    power = _simulated_power(delta, p_a, n_a, n_b, reps=200_000, seed=20261020)
    assert abs(power - POWER) <= 0.03, (p_a, n_a, n_b, delta, power)


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
            assert isinstance(note, str) and note.strip(), name
        else:
            assert note is None or (isinstance(note, float) and math.isnan(note)), (name, note)
    # The horizon difference is kept as it is on the disagreeing cells.
    crossing = _cell(result, "fell", "crossing_b_fewer_but_sooner")
    assert abs(crossing["delta"] - (23 / 32 - 24 / 32)) <= 1e-12


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
    """statsmodels documents ``mcnemar(table, exact=True)`` on a 2x2 table of paired outcomes,
    rows the first measurement and columns the second: ``[[yes-yes, yes-no], [no-yes, no-no]]``.
    Returns ``(p, n10, n01, pairs)``."""
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


# ---------- PF4.15: no detection limit at a 100% baseline ----------


@pytest.mark.parametrize("n_a,n_b", [(32, 32), (100, 20), (20, 100), (1, 1)])
def test_pf4_15_the_limit_at_a_baseline_of_one_is_not_a_number(n_a: int, n_b: int) -> None:
    assert math.isnan(mde_two_proportion(1.0, n_a, n_b, alpha=Q, power=POWER))


def test_pf4_15_a_baseline_that_failed_every_run_has_no_limit_whatever_its_float_incidence() -> None:
    """Thirteen falls at distinct times sum to 0.9999999999999998 by Aalen-Johansen, one ulp-pair
    short of 1; the cell is at ceiling by its counts all the same. A cell one fall short of every
    run keeps a number, and the maxima are over the cells with a number."""
    a = {
        "all_fell": [(i, "fell", 0.01 * (i + 1)) for i in range(13)],
        "all_fell_exact": [(i, "fell", 1.0) for i in range(13)],
        "one_short": [(i, "fell", 0.01 * (i + 1)) if i < 12 else (i, "ok", 10.0) for i in range(13)],
        "low": [(i, "fell", 1.0) if i < 2 else (i, "ok", 10.0) for i in range(13)],
    }
    b = {name: list(rows) for name, rows in a.items()}
    fa, fb = _frame(a, 10.0), _frame(b, 10.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = multi_diff(fa, fb, events=["fell"], method="fisher_bh",
                            manifest_a=_manifest("A"), manifest_b=_manifest("B"))
    rounded = _cell(result, "fell", "all_fell")
    assert rounded["events_a"] == rounded["n_a"] == 13
    # Today's estimator sums these to 0.9999999999999998; a build that sums exactly may give 1.0.
    assert math.isnan(rounded["mde"])
    assert math.isnan(_cell(result, "fell", "all_fell_exact")["mde"])
    short = _cell(result, "fell", "one_short")
    low = _cell(result, "fell", "low")
    assert math.isfinite(short["mde"]) and math.isfinite(low["mde"])
    ev = result.by_event["fell"]
    assert ev.max_mde == max(short["mde"], low["mde"])
    assert ev.max_mde_unchanged == max(short["mde"], low["mde"])


def test_pf4_15_the_single_event_diff_also_reports_no_limit_at_ceiling() -> None:
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


def test_pf4_16_the_private_wilson_keeps_its_default_z_of_1_96() -> None:
    """statsmodels documents its quantile as ``norm.isf(alpha / 2)``, so z = 1.96 is ``alpha =
    2 * norm.sf(1.96)``. This passes on today's code and fails a default of any other z (the
    re-check's 1.645 mutant went uncaught by the whole suite)."""
    from scipy.stats import norm
    from statsmodels.stats.proportion import proportion_confint

    alpha = 2.0 * float(norm.sf(1.96))
    for n in (1, 4, 10, 32, 100):
        for k in sorted({0, 1, n // 2, n - 1, n}):
            if not 0 <= k <= n:
                continue
            lo, hi = survival.wilson(k, n)
            ref_lo, ref_hi = proportion_confint(k, n, alpha=alpha, method="wilson")
            assert abs(lo - float(ref_lo)) <= 1e-12, (k, n)
            assert abs(hi - float(ref_hi)) <= 1e-12, (k, n)


# ---------- PF4.18: Westfall-Young on one scale ----------


def _reference_min_p(observed: np.ndarray, permuted: np.ndarray) -> tuple[np.ndarray, float]:
    """The spec's definition, member by member: the reference set is the B permutations and the
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


def test_pf4_18_under_the_null_the_omnibus_rejects_at_its_nominal_rate_at_small_b() -> None:
    """Observed and permuted statistics drawn alike, B = 19, four statistics: the omnibus is a rank
    among 20 exchangeable members, so it rejects at 0.10 in at most 10% of datasets. The old
    scales rejected in 18.4% (README section 6)."""
    from poisson_prove.tree import _min_p

    rng = np.random.default_rng(20261020)
    datasets = 4000
    rejected = 0
    for _ in range(datasets):
        draws = rng.normal(size=(20, 4))
        _, omnibus = _min_p(draws[0], draws[1:])
        rejected += int(float(omnibus) <= 0.10)
    rate = rejected / datasets
    assert rate <= 0.10 + 3.0 * math.sqrt(0.1 * 0.9 / datasets), rate


# ---------- PF4.19: the Kaplan-Meier warning fires on the real condition ----------


def _one_competitor_frame() -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """The re-check's run (README section 7): 'fell' at a random time, and one other outcome,
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


def test_pf4_19_one_other_outcome_that_ends_runs_early_draws_the_warning() -> None:
    from lifelines import AalenJohansenFitter, KaplanMeierFitter

    df, t, outcome = _one_competitor_frame()
    # lifelines documents ``KaplanMeierFitter().fit(durations, event_observed)`` and
    # ``AalenJohansenFitter().fit(durations, event_observed, event_of_interest)`` with the event
    # coded as an integer per competing cause. They disagree here, which is what the warning is for.
    km = KaplanMeierFitter().fit(t, outcome == "fell")
    aj = AalenJohansenFitter(calculate_variance=False).fit(
        t, np.where(outcome == "fell", 1, 2), event_of_interest=1
    )
    km_incidence = float(1 - km.survival_function_at_times(10.0).iloc[0])
    aj_incidence = float(aj.cumulative_density_.iloc[-1, 0])
    assert km_incidence - aj_incidence > 0.05
    with pytest.warns(UserWarning) as record:
        survival.cell_table(df, "fell", method="km")
    assert any("stuck" in str(w.message) for w in record)


def test_pf4_19_other_outcomes_seen_only_at_the_horizon_draw_no_warning() -> None:
    rows = []
    for i in range(30):
        if i < 10:
            rows.append((i, "fell", 1.0 + 0.1 * i))
        elif i < 20:
            rows.append((i, "survived", 5.0))
        else:
            rows.append((i, "stuck_at_limit", 5.0))
    df = _frame({"c": rows}, 5.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        survival.cell_table(df, "fell", method="km")


def test_pf4_19_the_warning_names_each_outcome_that_ends_runs_early() -> None:
    rows = [(i, "fell", 1.0 + 0.1 * i) for i in range(5)]
    rows += [(5 + i, "timeout", 3.0) for i in range(5)]
    rows += [(10 + i, "survived", 5.0) for i in range(5)]
    df = _frame({"c": rows}, 5.0)
    with pytest.warns(UserWarning) as record:
        survival.cell_table(df, "fell", method="km")
    assert any("timeout" in str(w.message) for w in record)


def test_pf4_19_aalen_johansen_draws_no_warning() -> None:
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
