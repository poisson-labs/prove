"""Oracle for M6: run diff with Fisher/BH, paired McNemar, log-rank, and MDE.

Golden tests (I1, I2, I8, I10, I12, I17, I18) run on the committed Go1 fixture through
``go1_store``; frames are produced with ``proofload.survival.censor``. Oracle tests (I3, I6,
I7, I9) import ``statsmodels`` / ``lifelines`` with ``pytest.importorskip`` in the test
body and run hypothesis on an inner function, so a missing dev extra is a clean skip.
I4 is a seeded Monte Carlo. I11-I14 and I16 use small synthetic censored frames built
directly with the six columns M6 reads: ``config_hash``, ``config``, ``replicate_index``,
``t``, ``observed``, ``horizon``.

Per-cell published p/q values for I1 come from ``tests/fixtures/go1/golden.json`` under
``cells`` when those entries carry ``fisher_p`` / ``fisher_q``, otherwise from the source
diff JSON, and that test skips when neither is available. The 60/0 assertion never skips.

Notes for the implementation session:

- The published ``fisher_q`` is BH over all 400 cells. BH over only cells with at least
  one event gives 61 safer, not 60.
- I9's oracle is ``statsmodels.stats.proportion.power_proportions_2indep`` inverted by
  bisection. It uses the pooled-null and alternative standard errors of section 3, which
  ``NormalIndPower`` (Cohen's h) does not. The reference bisection runs to 1e-10, so the
  implementation's own bisection must converge to well under 1e-6.
- I7 draws times from a short grid so ties and censoring are both exercised; lifelines'
  ``logrank_test`` counts all ties at a time in that time's ``d_j``.
- I6 includes a cell where one arm lacks a replicate; the pair must be dropped, and the
  test is built so that positional mis-pairing changes ``stat``.
- I8 asserts ``p == 1.0`` exactly on identical arms. Compute the expected count as
  ``n_a_j * d_j / n_j`` (integer-exact) rather than ``n_a_j * (d_j / n_j)``, or the
  statistic picks up a ~1e-30 residue and ``chi2.sf`` returns just under 1.0.
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from scipy.stats import fisher_exact

from proofload.diff import (
    DiffError,
    DiffResult,
    NotPairable,
    UnitMismatch,
    bh,
    diff,
    mde_two_proportion,
)
from proofload.store import RunManifest, Store, config_hash
from proofload.survival import censor

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "go1"
GOLDEN_JSON = FIXTURE_DIR / "golden.json"
DIFF_JSON = (
    Path.home()
    / "code"
    / "poisson-labs"
    / "policy-robustness-sweep"
    / "docs"
    / "measurements"
    / "2026-08-18-v0-v1-diff.json"
)

RUNS = ["go1-v0", "go1-v1"]
EVENT = "fell"
METHODS = ["fisher_bh", "mcnemar_bh", "logrank_bh"]
Q = 0.05
POWER = 0.8
CELLS = 400
PUBLISHED_SAFER, PUBLISHED_WORSE = 60, 0
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
    """A stored seed that is a function of ``(config_hash, replicate_index)``. **C49 (P-1 section
    7.3), added in P-1 Session A's retrofit**: ``_cframe`` carried no ``seed`` column at all, so
    ``mcnemar_bh`` ran on every I6 pair with nothing to establish the pairing on -- C18's blindness
    inside a fixture. Two arms built by ``_cframe`` now store the same seed at the same
    ``(config_hash, replicate_index)``, which is what a stored pair from one sweep does. Green
    before and after on the bare tree (nothing reads the column there), so its green is not
    evidence."""
    return 1000 * (int(h[:6], 16) % 100_000) + replicate_index


def _cframe(cells: dict[str, list[tuple]], *, horizon: float = 5.0) -> pd.DataFrame:
    """Censored frame from {cell label: [(t, observed) or (t, observed, replicate_index)]}, with
    the stored ``seed`` a censored store frame carries (C49)."""
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


def _load_published_cells() -> dict[tuple[float, float], dict]:
    if GOLDEN_JSON.is_file():
        cells = json.loads(GOLDEN_JSON.read_text()).get("cells")
        if cells and all("fisher_p" in c and "fisher_q" in c for c in cells):
            return {(c["mu"], c["push_pct_bw"]): c for c in cells}
    if not DIFF_JSON.is_file():
        pytest.skip(f"no published per-cell p/q: golden.json lacks them and {DIFF_JSON} absent")
    cells = json.loads(DIFF_JSON.read_text())["cells_diff"]
    return {(c["mu"], c["push_pct_bw"]): c for c in cells}


def _fisher_table(events_a: int, n_a: int, events_b: int, n_b: int) -> list[list[int]]:
    return [[events_a, n_a - events_a], [events_b, n_b - events_b]]


def _same_or_both_nan(x: float, y: float) -> bool:
    return (np.isnan(x) and np.isnan(y)) or x == y


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def frames(go1_store: Store) -> dict[str, pd.DataFrame]:
    return {run_id: censor(go1_store.read(run_id), EVENT) for run_id in RUNS}


@pytest.fixture(scope="module")
def manifests(go1_store: Store) -> dict[str, RunManifest]:
    return {run_id: go1_store.manifest(run_id) for run_id in RUNS}


def _fixture_diff(
    frames: dict[str, pd.DataFrame],
    manifests: dict[str, RunManifest],
    method: str,
    a: str = "go1-v0",
    b: str = "go1-v1",
) -> DiffResult:
    return diff(
        frames[a], frames[b], event=EVENT, method=method, q=Q, power=POWER,
        manifest_a=manifests[a], manifest_b=manifests[b],
    )


@pytest.fixture(scope="module")
def golden(frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]) -> DiffResult:
    return _fixture_diff(frames, manifests, "fisher_bh")


# ---------- I1: golden ----------


def test_i1_golden_sixty_safer_zero_worse(golden: DiffResult) -> None:
    assert golden.n_safer == PUBLISHED_SAFER
    assert golden.n_worse == PUBLISHED_WORSE
    assert len(golden.cells) == CELLS and golden.n_not_comparable == 0
    assert golden.method == "fisher_bh" and golden.q == Q and golden.event == EVENT
    assert golden.t_unit == "seconds" and golden.horizon == 5.0
    assert golden.seed_identity_match is True
    assert list(golden.cells.columns) == CELLS_COLUMNS


def test_i1_golden_per_cell_p_and_q_match_publication(golden: DiffResult) -> None:
    published = _load_published_cells()
    assert len(published) == CELLS
    for row in golden.cells.itertuples(index=False):
        key = (row.config["mu"], row.config["push_pct_bw"])
        pub = published[key]
        assert row.events_a == pub["fell_a"] and row.events_b == pub["fell_b"], key
        assert row.n_a == pub["n_a"] and row.n_b == pub["n_b"], key
        assert abs(row.p - pub["fisher_p"]) <= TOL_ORACLE, key
        assert abs(row.q - pub["fisher_q"]) <= TOL_ORACLE, key


# ---------- I2: null diff ----------


@pytest.mark.parametrize("method", METHODS)
def test_i2_null_diff_finds_nothing(
    frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest], method: str
) -> None:
    result = _fixture_diff(frames, manifests, method, a="go1-v0", b="go1-v0")
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
    result = _fixture_diff(frames, manifests, "logrank_bh", a="go1-v1", b="go1-v1")
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
    def pow_at(delta: float) -> float:
        return float(
            proportion.power_proportions_2indep(
                delta, rate_a, n_a, ratio=n_b / n_a, alpha=alpha,
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
    # Rates of exactly 0 and 1 go through the 0.5/n continuity guard. At 1.0 no increase
    # is detectable at all, so only finiteness, positivity, and the unit bound are pinned.
    for rate_a in (0.0, 1.0):
        m = mde_two_proportion(rate_a, 32, 32)
        assert np.isfinite(m) and 0.0 < m <= 1.0
    assert mde_two_proportion(0.0, 32, 32) <= 1.0


# ---------- I10: max_mde ----------


def test_i10_max_mde_is_column_max_and_positive_on_fixture(golden: DiffResult) -> None:
    assert golden.max_mde == golden.cells["mde"].max()
    assert golden.max_mde > 0.0
    assert (golden.cells["mde"] > 0.0).all()


def test_i10_cell_mde_is_mde_two_proportion_at_q(golden: DiffResult) -> None:
    for row in golden.cells.head(50).itertuples(index=False):
        expected = mde_two_proportion(row.rate_a, int(row.n_a), int(row.n_b), alpha=Q, power=POWER)
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
    carry the same one at each ``(config_hash, replicate_index)`` (C49)."""
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
    for col in CELLS_COLUMNS:
        assert col in header, col
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
    null = _fixture_diff(frames, manifests, "fisher_bh", a="go1-v1", b="go1-v1")
    assert null.check(fail_on="worse") is True and null.check(fail_on="any") is True
    a = _one_cell([(5.0, False)] * 32)
    b = _one_cell([(1.0, i < 20) for i in range(32)])
    worse = _paired("fisher_bh", a, b)
    assert worse.n_worse == 1 and worse.n_safer == 0
    assert worse.check(fail_on="worse") is False and worse.check(fail_on="any") is False
    safer = _paired("fisher_bh", b, a)
    assert safer.n_safer == 1 and safer.n_worse == 0
    assert safer.check(fail_on="worse") is True and safer.check(fail_on="any") is False


# ---------- I17: paired methods on the fixture, reported not pinned ----------


def test_i17_capture_paired_and_logrank_counts(
    frames: dict[str, pd.DataFrame], manifests: dict[str, RunManifest], tmp_path: Path
) -> None:
    mcnemar = _fixture_diff(frames, manifests, "mcnemar_bh")
    logrank = _fixture_diff(frames, manifests, "logrank_bh")
    assert mcnemar.seed_identity_match is True and mcnemar.method == "mcnemar_bh"
    assert logrank.method == "logrank_bh"
    captured = {
        "event": EVENT,
        "q": Q,
        "fisher_safer": PUBLISHED_SAFER,
        "fisher_worse": PUBLISHED_WORSE,
        "mcnemar_safer": int(mcnemar.n_safer),
        "mcnemar_worse": int(mcnemar.n_worse),
        "mcnemar_max_mde": float(mcnemar.max_mde),
        "logrank_safer": int(logrank.n_safer),
        "logrank_worse": int(logrank.n_worse),
        "logrank_max_mde": float(logrank.max_mde),
    }
    out = tmp_path / "phase2.json"
    out.write_text(json.dumps(captured, indent=2) + "\n")
    assert json.loads(out.read_text()) == captured
    if FIXTURE_DIR.is_dir():
        shutil.copyfile(out, FIXTURE_DIR / "phase2.json")


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
