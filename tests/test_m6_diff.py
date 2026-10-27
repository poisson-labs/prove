"""Frozen tests for M6: run diff with Fisher/BH, paired McNemar, log-rank, and MDE.

Golden tests (I2, I8, I10, I12, I17, I18) run on the generated lattice pair
(``tests/lattice.py``) through ``lattice_store``; frames are produced with ``poisson_prove.survival.censor``. Reference tests (I3, I6,
I7, I9) import ``statsmodels`` / ``lifelines`` with ``pytest.importorskip`` in the test
body and run hypothesis on an inner function, so a missing dev extra is a clean skip.
I4 is a seeded Monte Carlo. I11-I14 and I16 use small synthetic censored frames built
directly with the six columns M6 reads: ``config_hash``, ``config``, ``replicate_index``,
``t``, ``observed``, ``horizon``.

Notes on the references:

- The reference ``q`` is BH over all 72 conditions. BH over only the conditions with at least
  one event gives 23 lower, not 22.
- I9's reference is ``statsmodels.stats.proportion.power_proportions_2indep`` inverted by
  bisection. It uses the pooled-null and alternative standard errors, which
  ``NormalIndPower`` (Cohen's h) does not. The reference bisection runs to 1e-10, so Prove's
  own bisection must converge to well under 1e-6.
- I7 draws times from a short grid so ties and censoring are both exercised; lifelines'
  ``logrank_test`` counts all ties at a time in that time's ``d_j``.
- I6 includes a cell where one arm lacks a replicate; the pair must be dropped, and the
  test is built so that positional mis-pairing changes ``stat``.
- I8 asserts ``p == 1.0`` exactly on identical arms. The expected count must be computed as
  ``n_a_j * d_j / n_j`` (integer-exact) rather than ``n_a_j * (d_j / n_j)``, or the
  statistic picks up a ~1e-30 residue and ``chi2.sf`` returns just under 1.0.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from scipy.stats import fisher_exact

from poisson_prove.diff import (
    DiffError,
    DiffResult,
    NotPairable,
    UnitMismatch,
    bh,
    diff,
    mde_two_proportion,
)
from poisson_prove.store import RunManifest, Store, config_hash
from poisson_prove.survival import censor

import lattice

ROOT = Path(__file__).resolve().parents[1]
RUNS = [lattice.RUN_A, lattice.RUN_B]
EVENT = lattice.EVENT
METHODS = ["fisher_bh", "mcnemar_bh", "logrank_bh"]
Q = 0.05
POWER = 0.8
CELLS = 72
#: The reference's flagged conditions under fisher_bh (``lattice.directions(lattice.fisher())``).
REFERENCE_SAFER, REFERENCE_WORSE = 22, 0
TOL_EXACT = 1e-12
TOL_ORACLE = 1e-9
TOL_MDE = 1e-6

CELLS_COLUMNS = [
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
    # PF4 (PF4.13, PF4.14, PF4.15): every cell carries its direction from the test, the
    # log-rank timing note, the matched-pair count and the note on a missing detection limit.
    "direction",
    "direction_note",
    "pairs",
    "n01",
    "n10",
    "mde_note",
    # PF4.34 to PF4.47: every cell row carries Holm's adjusted p and decision, the limit keys
    # both ways, the competing shift and the interval on the change, in this order.
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
]
SUMMARY_FIELDS = [
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
]

TIME_GRID = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]


# ---------- helpers ----------


def _manifest(run_id: str = "r", *, run_salt: str = "salt", t_unit: str = "seconds") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        target_id=f"target@{run_id}",
        t_unit=t_unit,
        run_salt=run_salt,
        axis_types={"cell": "categorical"},
        backend="local",
        environment={},
    )


def _seed_of(h: str, replicate_index: int) -> int:
    """A stored seed that is a function of ``(config_hash, replicate_index)``. Two arms built by
    ``_cframe`` store the same seed at the same ``(config_hash, replicate_index)``, which is what a
    stored pair from one sweep does, so ``mcnemar_bh`` has a stored seed to establish every I6 pair
    on; without the column a fixture would pair on nothing."""
    return 1000 * (int(h[:6], 16) % 100_000) + replicate_index


def _cframe(cells: dict[str, list[tuple]], *, horizon: float = 5.0) -> pd.DataFrame:
    """Censored frame from {cell label: [(t, observed) or (t, observed, replicate_index)]}, with
    the stored ``seed`` a censored store frame carries."""
    records = []
    for label, rows in cells.items():
        config = {"cell": label}
        h = config_hash(config)
        for i, row in enumerate(rows):
            t, observed = row[0], row[1]
            rep = row[2] if len(row) > 2 else i
            records.append(
                {
                    "config_hash": h,
                    "config": dict(config),
                    "replicate_index": int(rep),
                    "t": float(t),
                    "observed": bool(observed),
                    "horizon": float(horizon),
                    "seed": _seed_of(h, int(rep)),
                }
            )
    columns = ["config_hash", "config", "replicate_index", "t", "observed", "horizon", "seed"]
    df = pd.DataFrame.from_records(records, columns=columns)
    df["observed"] = df["observed"].astype(bool)
    return df


def _one_cell(rows: list[tuple], *, horizon: float = 5.0) -> pd.DataFrame:
    return _cframe({"c": rows}, horizon=horizon)


def _paired(
    method: str, a: pd.DataFrame, b: pd.DataFrame, *, salt: str = "salt", q: float = Q
) -> DiffResult:
    return diff(
        a, b, event=EVENT, method=method, q=q, power=POWER,
        manifest_a=_manifest("a", run_salt=salt), manifest_b=_manifest("b", run_salt=salt),
    )


def _fisher_table(events_a: int, n_a: int, events_b: int, n_b: int) -> list[list[int]]:
    return [[events_a, n_a - events_a], [events_b, n_b - events_b]]


def _same_or_both_nan(x: float, y: float) -> bool:
    return (np.isnan(x) and np.isnan(y)) or x == y


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def frames(lattice_store: Store) -> dict[str, pd.DataFrame]:
    return {run_id: censor(lattice_store.read(run_id), EVENT) for run_id in RUNS}


@pytest.fixture(scope="module")
def manifests(lattice_store: Store) -> dict[str, RunManifest]:
    return {run_id: lattice_store.manifest(run_id) for run_id in RUNS}


def _fixture_diff(
    frames: dict[str, pd.DataFrame],
    manifests: dict[str, RunManifest],
    method: str,
    a: str = lattice.RUN_A,
    b: str = lattice.RUN_B,
) -> DiffResult:
    return diff(
        frames[a], frames[b], event=EVENT, method=method, q=Q, power=POWER,
        manifest_a=manifests[a], manifest_b=manifests[b],
    )


@pytest.fixture(scope="module")
def golden(frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]) -> DiffResult:
    return _fixture_diff(frames, manifests, "fisher_bh")


# ---------- I2: null diff ----------


@pytest.mark.parametrize("method", METHODS)
def test_i2_null_diff_finds_nothing(
    frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest], method: str
) -> None:
    result = _fixture_diff(frames, manifests, method, a=lattice.RUN_A, b=lattice.RUN_A)
    assert result.n_safer == 0 and result.n_worse == 0
    assert result.n_unchanged == len(result.cells) == CELLS
    assert (result.cells["delta"] == 0.0).all()
    if method != "logrank_bh":
        assert (result.cells["p"] == 1.0).all()


# ---------- I3: BH against statsmodels ----------


def test_i3_bh_matches_statsmodels() -> None:
    multitest = pytest.importorskip("statsmodels.stats.multitest")

    p_values = st.one_of(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        st.sampled_from([0.0, 1e-6, 0.01, 0.04, 0.05, 0.5, 1.0]),
    )

    @settings(max_examples=100, deadline=None)
    @given(p=st.lists(p_values, min_size=1, max_size=60))
    def check(p: list[float]) -> None:
        arr = np.asarray(p, dtype=float)
        ours = bh(arr, Q)
        ref = multitest.multipletests(arr, alpha=Q, method="fdr_bh")[1]
        assert ours.shape == arr.shape
        np.testing.assert_allclose(ours, ref, rtol=0, atol=TOL_EXACT)

    check()


def test_i3_bh_hand_example() -> None:
    p = np.array([0.01, 0.04, 0.03, 0.5, 1.0])
    q = bh(p, Q)
    # sorted: 0.01, 0.03, 0.04, 0.5, 1.0 -> raw 0.05, 0.075, 0.0667, 0.625, 1.0 ->
    # cumulative min from the top -> 0.05, 0.0667, 0.0667, 0.625, 1.0, then un-sorted.
    expected = np.array([0.05, 1 / 15, 1 / 15, 0.625, 1.0])
    np.testing.assert_allclose(q, expected, rtol=0, atol=TOL_EXACT)


# ---------- I4: BH controls FDR on uniform nulls ----------


def test_i4_bh_controls_false_discovery_on_uniform_nulls() -> None:
    rng = np.random.default_rng(20260902)
    draws, m = 250, 400
    any_rejection = 0
    for _ in range(draws):
        p = rng.uniform(size=m)
        any_rejection += bool(np.any(bh(p, Q) < Q))
    assert any_rejection / draws <= Q + 0.03


# ---------- I5: Fisher is scipy's two-sided Fisher ----------


@settings(deadline=None)
@given(
    n_a=st.integers(min_value=1, max_value=40),
    n_b=st.integers(min_value=1, max_value=40),
    fa=st.floats(min_value=0, max_value=1),
    fb=st.floats(min_value=0, max_value=1),
)
def test_i5_fisher_p_equals_scipy_exactly(n_a: int, n_b: int, fa: float, fb: float) -> None:
    events_a, events_b = min(n_a, int(round(fa * n_a))), min(n_b, int(round(fb * n_b)))
    a = _one_cell([(1.0, i < events_a) for i in range(n_a)])
    b = _one_cell([(1.0, i < events_b) for i in range(n_b)])
    result = _paired("fisher_bh", a, b)
    ref_stat, ref_p = fisher_exact(_fisher_table(events_a, n_a, events_b, n_b), alternative="two-sided")
    row = result.cells.iloc[0]
    assert row["p"] == ref_p
    assert _same_or_both_nan(float(row["stat"]), float(ref_stat))
    assert row["events_a"] == events_a and row["events_b"] == events_b
    assert row["n_a"] == n_a and row["n_b"] == n_b


# ---------- I6: McNemar against statsmodels ----------


def test_i6_mcnemar_matches_statsmodels() -> None:
    tables = pytest.importorskip("statsmodels.stats.contingency_tables")

    @settings(max_examples=100, deadline=None)
    @given(
        n=st.integers(min_value=1, max_value=40),
        seed_a=st.lists(st.booleans(), min_size=40, max_size=40),
        seed_b=st.lists(st.booleans(), min_size=40, max_size=40),
    )
    def check(n: int, seed_a: list[bool], seed_b: list[bool]) -> None:
        obs_a, obs_b = seed_a[:n], seed_b[:n]
        a = _one_cell([(1.0, o) for o in obs_a])
        b = _one_cell([(1.0, o) for o in obs_b])
        result = _paired("mcnemar_bh", a, b)
        assert result.seed_identity_match is True
        bb = sum(1 for x, y in zip(obs_a, obs_b, strict=True) if x and not y)
        cc = sum(1 for x, y in zip(obs_a, obs_b, strict=True) if (not x) and y)
        both = sum(1 for x, y in zip(obs_a, obs_b, strict=True) if x and y)
        neither = n - bb - cc - both
        ref = tables.mcnemar([[both, bb], [cc, neither]], exact=True)
        row = result.cells.iloc[0]
        assert row["stat"] == bb - cc
        assert abs(row["p"] - float(ref.pvalue)) <= TOL_EXACT
        if bb + cc == 0:
            assert row["p"] == 1.0

    check()


def test_i6_mcnemar_p_is_one_when_no_discordant_pairs() -> None:
    a = _one_cell([(1.0, True), (5.0, False), (5.0, False)])
    result = _paired("mcnemar_bh", a, a.copy())
    assert result.cells.iloc[0]["p"] == 1.0 and result.cells.iloc[0]["stat"] == 0


def test_i6_mcnemar_drops_unmatched_replicate_instead_of_mispairing() -> None:
    a = _one_cell([(1.0, True, 0), (5.0, False, 1), (2.0, True, 2)])
    b = _one_cell([(1.0, True, 0), (5.0, False, 2)])
    result = _paired("mcnemar_bh", a, b)
    row = result.cells.iloc[0]
    # Correct pairing on replicate_index: pairs (0: T,T) and (2: T,F) -> b=1, c=0.
    # Positional mis-pairing would give (T,T), (F,F) -> b=c=0.
    assert row["stat"] == 1
    assert row["p"] == 1.0
    assert row["n_a"] == 3 and row["n_b"] == 2


# ---------- I7: log-rank against lifelines ----------


def test_i7_logrank_matches_lifelines() -> None:
    statistics = pytest.importorskip("lifelines.statistics")

    @st.composite
    def arm(draw):
        n = draw(st.integers(min_value=2, max_value=30))
        t = draw(st.lists(st.sampled_from(TIME_GRID), min_size=n, max_size=n))
        o = draw(st.lists(st.booleans(), min_size=n, max_size=n))
        return list(zip(t, o, strict=True))

    @settings(max_examples=80, deadline=None)
    @given(rows_a=arm(), rows_b=arm())
    def check(rows_a: list[tuple[float, bool]], rows_b: list[tuple[float, bool]]) -> None:
        assume(any(o for _, o in rows_a) or any(o for _, o in rows_b))
        t_a, o_a = [t for t, _ in rows_a], [o for _, o in rows_a]
        t_b, o_b = [t for t, _ in rows_b], [o for _, o in rows_b]
        ref = statistics.logrank_test(t_a, t_b, event_observed_A=o_a, event_observed_B=o_b)
        assume(np.isfinite(ref.test_statistic) and np.isfinite(ref.p_value))
        result = _paired("logrank_bh", _one_cell(rows_a), _one_cell(rows_b), salt="x")
        row = result.cells.iloc[0]
        assert abs(row["stat"] - float(ref.test_statistic)) <= TOL_ORACLE
        assert abs(row["p"] - float(ref.p_value)) <= TOL_ORACLE

    check()


# ---------- I8: log-rank on identical frames ----------


def test_i8_logrank_identical_frames_p_is_one_everywhere(
    frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]
) -> None:
    result = _fixture_diff(frames, manifests, "logrank_bh", a=lattice.RUN_B, b=lattice.RUN_B)
    assert len(result.cells) == CELLS
    assert (result.cells["p"] == 1.0).all()
    assert np.all(np.abs(result.cells["stat"].to_numpy(dtype=float)) <= TOL_EXACT)


def test_i8_logrank_identical_synthetic_including_no_events() -> None:
    a = _cframe(
        {
            "events": [(1.0, True), (2.0, True), (2.0, False), (5.0, False)],
            "quiet": [(5.0, False), (5.0, False), (5.0, False)],
        }
    )
    result = _paired("logrank_bh", a, a.copy())
    assert (result.cells["p"] == 1.0).all()


# ---------- I9: MDE ----------


def _reference_mde(rate_a: float, n_a: int, n_b: int, alpha: float, power: float, proportion) -> float:
    # PF4 (PF4.12): the arguments follow statsmodels' documentation of
    # ``power_proportions_2indep(diff, prop2, nobs1, ratio)``: sample 1 has ``prop1 = prop2 + diff``
    # and size ``nobs1``, and ``nobs2 = ratio * nobs1``. The changed arm B is sample 1, so
    # ``diff = delta``, ``prop2 = rate_a``, ``nobs1 = n_b`` and ``ratio = n_a / n_b`` (the old
    # call passed ``nobs1 = n_a, ratio = n_b / n_a``, copied from Prove's argument order).
    def pow_at(delta: float) -> float:
        return float(
            proportion.power_proportions_2indep(
                delta, rate_a, n_b, ratio=n_a / n_b, alpha=alpha,
                alternative="two-sided", return_results=False,
            )
        )

    lo, hi = 0.0, 1.0 - rate_a
    assume(pow_at(hi) >= power)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if pow_at(mid) >= power:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-10:
            break
    return hi


def test_i9_mde_matches_statsmodels_power_inversion() -> None:
    proportion = pytest.importorskip("statsmodels.stats.proportion")

    @settings(max_examples=60, deadline=None)
    @given(
        rate_a=st.floats(min_value=0.05, max_value=0.9),
        n_a=st.integers(min_value=8, max_value=400),
        n_b=st.integers(min_value=8, max_value=400),
    )
    def check(rate_a: float, n_a: int, n_b: int) -> None:
        ref = _reference_mde(rate_a, n_a, n_b, Q, POWER, proportion)
        ours = mde_two_proportion(rate_a, n_a, n_b, alpha=Q, power=POWER)
        assert abs(ours - ref) <= TOL_MDE

    check()


@given(
    rate_a=st.floats(min_value=0.0, max_value=0.95),
    n=st.integers(min_value=2, max_value=2000),
    ratio=st.sampled_from([1, 2, 3]),
)
def test_i9_mde_positive_bounded_and_decreasing_in_n(rate_a: float, n: int, ratio: int) -> None:
    m = mde_two_proportion(rate_a, n, n * ratio, alpha=Q, power=POWER)
    assert m > 0.0
    assert rate_a + m <= 1.0 + TOL_EXACT
    bigger = mde_two_proportion(rate_a, 2 * n, 2 * n * ratio, alpha=Q, power=POWER)
    assert bigger <= m + TOL_ORACLE


def test_i9_mde_guards_rate_zero_and_one() -> None:
    # A rate of exactly 0 goes through the 0.5/n continuity guard: finite, positive, unit-bounded.
    m = mde_two_proportion(0.0, 32, 32)
    assert np.isfinite(m) and 0.0 < m <= 1.0
    assert mde_two_proportion(0.0, 32, 32) <= 1.0
    # PF4 (PF4.15): at 1.0 no rise is possible, so there is no limit: NaN, not a guarded number.
    assert np.isnan(mde_two_proportion(1.0, 32, 32))


# ---------- I10: max_mde ----------


def test_i10_max_mde_is_column_max_and_positive_on_fixture(golden: DiffResult) -> None:
    # PF4 (PF4.15): a cell whose baseline had the event in every run (decided from the counts) has
    # no limit (NaN) and is left out of max_mde; every other cell keeps a positive limit, and
    # max_mde is the maximum over those.
    ceiling = golden.cells["events_a"] == golden.cells["n_a"]
    # 37 conditions of the before run trip in every episode (by design: load 40, 50, 100 and
    # gain 0.1 at load 10).
    assert int(ceiling.sum()) == sum(c.tripped_a == lattice.N for c in lattice.design_cells()) == 37
    assert golden.cells.loc[ceiling, "mde"].isna().all()
    rest = golden.cells.loc[~ceiling, "mde"]
    assert len(rest) > 0 and (rest > 0.0).all()
    assert golden.max_mde == rest.max()
    assert golden.max_mde > 0.0


def test_i10_cell_mde_is_mde_two_proportion_at_q(golden: DiffResult) -> None:
    for row in golden.cells.head(50).itertuples(index=False):
        expected = mde_two_proportion(row.rate_a, int(row.n_a), int(row.n_b), alpha=Q, power=POWER)
        # PF4 (PF4.15): a cell at a 100% baseline has no limit, NaN in the cell and from the
        # function alike; every other cell still equals the function at the cell's counts.
        if row.events_a == row.n_a:
            assert np.isnan(row.mde) and np.isnan(expected)
            continue
        assert abs(row.mde - expected) <= TOL_ORACLE


# ---------- I11: verdict rule ----------


def _assert_verdicts(cells: pd.DataFrame, q_threshold: float) -> None:
    for row in cells.itertuples(index=False):
        if row.q < q_threshold and row.delta < 0:
            expected = "safer"
        elif row.q < q_threshold and row.delta > 0:
            expected = "worse"
        else:
            expected = "unchanged"
        assert row.verdict == expected, (row.q, row.delta, row.verdict)


def test_i11_verdict_rule_on_golden(golden: DiffResult) -> None:
    _assert_verdicts(golden.cells, Q)
    assert set(golden.cells["verdict"]) <= {"safer", "worse", "unchanged"}


@settings(deadline=None)
@given(
    tables=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=32),
            st.integers(min_value=0, max_value=32),
        ),
        min_size=1,
        max_size=6,
    ),
    q_threshold=st.sampled_from([0.01, 0.05, 0.2, 0.5]),
)
def test_i11_verdict_rule_property(tables: list[tuple[int, int]], q_threshold: float) -> None:
    a = _cframe({f"c{i}": [(1.0, j < ea) for j in range(32)] for i, (ea, _) in enumerate(tables)})
    b = _cframe({f"c{i}": [(1.0, j < eb) for j in range(32)] for i, (_, eb) in enumerate(tables)})
    result = _paired("fisher_bh", a, b, q=q_threshold)
    assert len(result.cells) == len(tables)
    _assert_verdicts(result.cells, q_threshold)
    counts = result.cells["verdict"].value_counts()
    assert result.n_safer == counts.get("safer", 0)
    assert result.n_worse == counts.get("worse", 0)
    assert result.n_unchanged == counts.get("unchanged", 0)


# ---------- I12: counts ----------


def test_i12_counts_add_up_on_golden(golden: DiffResult) -> None:
    assert golden.n_safer + golden.n_worse + golden.n_unchanged == len(golden.cells)
    assert len(golden.cells) + golden.n_not_comparable == CELLS
    assert golden.dropped_a == 0 and golden.dropped_b == 0


def test_i12_counts_with_partial_overlap() -> None:
    a = _cframe({"x": [(1.0, True)] * 4, "y": [(5.0, False)] * 4, "z": [(2.0, True)] * 4})
    b = _cframe({"y": [(5.0, False)] * 4, "z": [(2.0, True)] * 4, "w": [(1.0, True)] * 4})
    result = _paired("fisher_bh", a, b)
    union = set(a["config_hash"]) | set(b["config_hash"])
    assert len(result.cells) == 2
    assert result.n_not_comparable == 2
    assert len(result.cells) + result.n_not_comparable == len(union)
    assert result.dropped_a == 1 and result.dropped_b == 1
    assert result.n_safer + result.n_worse + result.n_unchanged == len(result.cells)
    assert set(result.cells["config_hash"]) == set(a["config_hash"]) & set(b["config_hash"])
    assert list(result.cells["config_hash"]) == sorted(result.cells["config_hash"])


# ---------- I13: units and pairing ----------


def test_i13_unit_mismatch_raises() -> None:
    a = _one_cell([(1.0, True), (5.0, False)])
    with pytest.raises(UnitMismatch):
        diff(
            a, a.copy(), event=EVENT, method="fisher_bh",
            manifest_a=_manifest("a", t_unit="seconds"), manifest_b=_manifest("b", t_unit="steps"),
        )


def test_i13_unit_mismatch_is_a_diff_error() -> None:
    assert issubclass(UnitMismatch, DiffError) and issubclass(NotPairable, DiffError)


def test_i13_mcnemar_requires_matching_salts() -> None:
    a = _one_cell([(1.0, True), (5.0, False)])
    with pytest.raises(NotPairable):
        diff(
            a, a.copy(), event=EVENT, method="mcnemar_bh",
            manifest_a=_manifest("a", run_salt="s1"), manifest_b=_manifest("b", run_salt="s2"),
        )


@pytest.mark.parametrize("which", ["a", "b", "both"])
def test_i13_mcnemar_requires_manifests(which: str) -> None:
    a = _one_cell([(1.0, True), (5.0, False)])
    ma = None if which in ("a", "both") else _manifest("a")
    mb = None if which in ("b", "both") else _manifest("b")
    with pytest.raises(NotPairable):
        diff(a, a.copy(), event=EVENT, method="mcnemar_bh", manifest_a=ma, manifest_b=mb)


@pytest.mark.parametrize("method", ["fisher_bh", "logrank_bh"])
def test_i13_unpaired_methods_run_with_different_salts_and_report_it(method: str) -> None:
    a = _one_cell([(1.0, True), (5.0, False), (2.0, True)])
    result = diff(
        a, a.copy(), event=EVENT, method=method,
        manifest_a=_manifest("a", run_salt="s1"), manifest_b=_manifest("b", run_salt="s2"),
    )
    assert result.seed_identity_match is False
    without = diff(a, a.copy(), event=EVENT, method=method)
    assert without.seed_identity_match is False


def test_i13_seed_identity_match_true_when_salts_and_stored_seeds_match() -> None:
    """P-1: the flag is seed identity, not salt equality -- ``_cframe`` stores a seed and both arms
    carry the same one at each ``(config_hash, replicate_index)``."""
    a = _one_cell([(1.0, True), (5.0, False)])
    assert _paired("fisher_bh", a, a.copy()).seed_identity_match is True
    assert _paired("mcnemar_bh", a, a.copy()).seed_identity_match is True


# ---------- I14: horizon truncation ----------


def test_i14_horizon_truncation_recensors_and_counts() -> None:
    # Only the t=4 event in A lies above the shared horizon of 3; the censored rows at
    # t=3 and t=2 are untouched, so exactly one row is re-censored.
    a = _one_cell([(1.0, True), (4.0, True), (3.0, False), (2.0, False)], horizon=5.0)
    b = _one_cell([(1.0, True), (3.0, False), (3.0, False), (3.0, False)], horizon=3.0)
    result = _paired("fisher_bh", a, b)
    assert result.horizon == 3.0
    assert result.truncated == 1
    row = result.cells.iloc[0]
    assert row["events_a"] == 1 and row["n_a"] == 4
    assert row["events_b"] == 1 and row["n_b"] == 4
    assert row["p"] == 1.0


def test_i14_no_truncation_when_horizons_match(golden: DiffResult) -> None:
    assert golden.truncated == 0


def test_i14_truncation_applies_to_both_runs() -> None:
    a = _one_cell([(2.5, True), (5.0, False)], horizon=5.0)
    b = _one_cell([(4.5, True), (2.0, False)], horizon=5.0)
    both = _paired("logrank_bh", a, b)
    assert both.truncated == 0 and both.horizon == 5.0
    # Shared horizon 2.0: both rows of A (t=2.5 event, t=5.0 censored) are re-censored,
    # nothing in C is above it. The event in A disappears; the event in C at 1.5 stays.
    c = _one_cell([(1.5, True), (2.0, False)], horizon=2.0)
    result = _paired("fisher_bh", a, c)
    assert result.horizon == 2.0
    assert result.truncated == 2
    assert result.cells.iloc[0]["events_a"] == 0 and result.cells.iloc[0]["events_b"] == 1


# ---------- I15: rendering ----------


def test_i15_to_markdown_has_header_and_summary(golden: DiffResult) -> None:
    md = golden.to_markdown()
    lines = [line for line in md.splitlines() if line.strip()]
    header = next(line for line in lines if line.lstrip().startswith("|"))
    assert [cell.strip() for cell in header.strip().strip("|").split("|")] == CELLS_COLUMNS, header
    summary = [line for line in lines if not line.lstrip().startswith("|")]
    joined = " ".join(summary)
    for token in ("n_safer", "n_worse", "max_mde", "method", "seed_identity_match", "unpaired_analysis"):
        assert token in joined, token
    assert str(golden.n_safer) in joined and golden.method in joined


def test_i15_to_json_round_trips_summary(golden: DiffResult) -> None:
    js = golden.to_json()
    assert isinstance(js, dict)
    for field in SUMMARY_FIELDS:
        assert field in js, field
        assert js[field] == getattr(golden, field), field
    json.dumps(js)


# ---------- I16: check ----------


def test_i16_check_on_golden(golden: DiffResult) -> None:
    assert golden.check(fail_on="worse") is True
    assert golden.check(fail_on="any") is False
    assert golden.check() is True


def test_i16_check_on_null_and_worse_diffs(
    frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]
) -> None:
    null = _fixture_diff(frames, manifests, "fisher_bh", a=lattice.RUN_B, b=lattice.RUN_B)
    assert null.check(fail_on="worse") is True and null.check(fail_on="any") is True
    a = _one_cell([(5.0, False)] * 32)
    b = _one_cell([(1.0, i < 20) for i in range(32)])
    worse = _paired("fisher_bh", a, b)
    assert worse.n_worse == 1 and worse.n_safer == 0
    assert worse.check(fail_on="worse") is False and worse.check(fail_on="any") is False
    safer = _paired("fisher_bh", b, a)
    assert safer.n_safer == 1 and safer.n_worse == 0
    assert safer.check(fail_on="worse") is True and safer.check(fail_on="any") is False


# ---------- I17: paired methods on the fixture, captured and checked against the references ----------


def test_i17_capture_paired_and_logrank_counts(
    frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest], tmp_path: Path
) -> None:
    mcnemar = _fixture_diff(frames, manifests, "mcnemar_bh")
    logrank = _fixture_diff(frames, manifests, "logrank_bh")
    assert mcnemar.seed_identity_match is True and mcnemar.method == "mcnemar_bh"
    assert logrank.method == "logrank_bh"
    # Each count is the count of an independent reference: the exact McNemar test (a binomial on
    # the lattice design's discordant pairs) and lifelines' log-rank test on the stored times, each
    # with one BH family.
    ref_mcnemar, ref_logrank = lattice.mcnemar(EVENT, Q), lattice.logrank(EVENT, Q)
    assert (mcnemar.n_safer, mcnemar.n_worse) == lattice.directions(ref_mcnemar) == (27, 0)
    assert (logrank.n_safer, logrank.n_worse) == lattice.directions(ref_logrank) == (27, 12)
    for result, reference in ((mcnemar, ref_mcnemar), (logrank, ref_logrank)):
        assert set(result.cells["config_hash"]) == set(reference)
        for row in result.cells.itertuples(index=False):
            ref = reference[row.config_hash]
            assert float(row.p) == pytest.approx(ref["p"], rel=1e-12, abs=0), (result.method, row.config)
            assert float(row.q) == pytest.approx(ref["q"], rel=1e-12, abs=0), (result.method, row.config)
    captured = {
        "event": EVENT,
        "q": Q,
        "fisher_safer": REFERENCE_SAFER,
        "fisher_worse": REFERENCE_WORSE,
        "mcnemar_safer": int(mcnemar.n_safer),
        "mcnemar_worse": int(mcnemar.n_worse),
        "mcnemar_max_mde": float(mcnemar.max_mde),
        "logrank_safer": int(logrank.n_safer),
        "logrank_worse": int(logrank.n_worse),
        "logrank_max_mde": float(logrank.max_mde),
    }
    # The capture round-trips in tmp_path; the copy into the study fixture's folder is gone with
    # that folder.
    out = tmp_path / "phase2.json"
    out.write_text(json.dumps(captured, indent=2) + "\n")
    assert json.loads(out.read_text()) == captured


# ---------- I18: determinism ----------


def _assert_same_result(x: DiffResult, y: DiffResult) -> None:
    for field in SUMMARY_FIELDS:
        assert getattr(x, field) == getattr(y, field), field
    pd.testing.assert_frame_equal(x.cells, y.cells)


def test_i18_diff_is_deterministic_on_fixture(
    frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest], golden: DiffResult
) -> None:
    again = _fixture_diff(frames, manifests, "fisher_bh")
    _assert_same_result(golden, again)


@pytest.mark.parametrize("method", METHODS)
def test_i18_diff_is_deterministic_on_synthetic(method: str) -> None:
    a = _cframe(
        {
            "x": [(1.0, True), (2.0, True), (5.0, False), (5.0, False), (3.0, True)],
            "y": [(5.0, False), (5.0, False), (4.0, True), (5.0, False), (5.0, False)],
        }
    )
    b = _cframe(
        {
            "x": [(1.5, True), (5.0, False), (5.0, False), (5.0, False), (2.5, True)],
            "y": [(5.0, False), (1.0, True), (4.0, True), (5.0, False), (2.0, True)],
        }
    )
    first = _paired(method, a, b)
    second = _paired(method, a.copy(), b.copy())
    _assert_same_result(first, second)


def test_i18_bh_and_mde_are_deterministic() -> None:
    p = np.array([0.2, 0.01, 0.01, 0.7, 1.0, 0.03])
    np.testing.assert_array_equal(bh(p, Q), bh(p.copy(), Q))
    assert mde_two_proportion(0.3, 32, 32) == mde_two_proportion(0.3, 32, 32)
