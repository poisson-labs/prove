"""Frozen tests for M5: derived censoring, Kaplan-Meier, Aalen-Johansen, Wilson, cell table.

Property tests (I2-I5, I7, I8) use hypothesis over ``t`` arrays drawn from a small grid,
so ties are common, with random censoring masks. Reference tests (I6, I9, I10) import
``lifelines`` / ``statsmodels`` through ``pytest.importorskip`` and skip when the dev
extras are absent. Golden tests (I14-I18) run on the generated lattice pair
(``tests/lattice.py``) through the ``lattice_store`` fixture in conftest.py.

Per-cell golden counts for I14/I15 come from the lattice's design (``lattice.design_cells()``,
each condition's count of ``tripped`` in each run, written down before any run is generated),
so they never skip. Cells are matched on the decoded ``config`` (gain, load), never on
``config_hash``.

Notes for a reader of these tests:

- I9 draws distinct event times on purpose. ``lifelines.AalenJohansenFitter`` jitters
  tied event times at random, which makes a 1e-9 comparison impossible on tied data.
- I5 checks the cumulative Greenwood sum ``var / S**2`` for monotonicity, not ``var``
  itself. ``Var(S) = S**2 * sum(d / (n (n - d)))`` is not monotone in general: with two
  events at distinct times among two subjects it goes 0.125 then 0.
- ``lifelines`` zeroes the ``n == d`` Greenwood term (``_additive_var`` replaces inf with
  0), so the sum holds its last finite value there and ``var`` is 0 once ``S`` is 0.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from poisson_prove.store import Store, config_hash
from poisson_prove.survival import (
    CIFCurve,
    KMCurve,
    SurvivalError,
    aalen_johansen,
    cell_table,
    censor,
    kaplan_meier,
    multi_outcome_guard,
    wilson,
)

import lattice

ROOT = Path(__file__).resolve().parents[1]
RUNS = [lattice.RUN_A, lattice.RUN_B]
TRIPPED_KEY = {lattice.RUN_A: "tripped_a", lattice.RUN_B: "tripped_b"}
CELLS = 72
HORIZON_S = 5.0
TOL_EXACT = 1e-12
TOL_ORACLE = 1e-9

CELL_TABLE_COLUMNS = [
    "config_hash",
    "config",
    "n",
    "n_errored",
    "n_events",
    "event_rate",
    "event_rate_lo",
    "event_rate_hi",
    # PF4 (PF4.1b): the table records the Wilson interval's level beside its bounds.
    "event_rate_level",
    "s_at_horizon",
    "s_var_at_horizon",
    "median_t",
    "curve",
]

# ---------- strategies ----------

TIME_GRID = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]


@st.composite
def tied_survival_data(draw, min_size: int = 1, max_size: int = 40):
    """(t, observed) with ties by construction: times come from a short grid."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    t = draw(st.lists(st.sampled_from(TIME_GRID), min_size=n, max_size=n))
    observed = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    return np.asarray(t, dtype=float), np.asarray(observed, dtype=bool)


@st.composite
def tied_competing_data(draw, events: tuple[str, ...], min_size: int = 1, max_size: int = 40):
    """(t, outcome) over a short time grid; outcomes drawn from events plus 'survived'."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    t = draw(st.lists(st.sampled_from(TIME_GRID), min_size=n, max_size=n))
    labels = [*events, "survived"]
    outcome = draw(st.lists(st.sampled_from(labels), min_size=n, max_size=n))
    return np.asarray(t, dtype=float), np.asarray(outcome, dtype=object)


@st.composite
def distinct_competing_data(
    draw, events: tuple[str, ...], min_size: int = 4, max_size: int = 40
):
    """(t, outcome) with strictly distinct times, for the tie-averse lifelines AJ reference."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    t = draw(
        st.lists(
            st.floats(min_value=0.1, max_value=100.0, allow_nan=False, allow_infinity=False),
            min_size=n,
            max_size=n,
            unique=True,
        )
    )
    labels = [*events, "survived"]
    outcome = draw(st.lists(st.sampled_from(labels), min_size=n, max_size=n))
    return np.asarray(t, dtype=float), np.asarray(outcome, dtype=object)


# ---------- helpers ----------

M4_COLUMNS = [
    "run_id",
    "config_hash",
    "config",
    "seed",
    "replicate_index",
    "outcome",
    "t",
    "horizon",
    "confidence",
    "meta",
    "error",
    "wall_time",
    "backend_meta",
]


def _frame(rows: list[tuple[dict, str | None, float | None, float]]) -> pd.DataFrame:
    """Build a Store.read()-shaped frame from (config, outcome, t, horizon) tuples."""
    records = []
    counters: dict[str, int] = {}
    for config, outcome, t, horizon in rows:
        h = config_hash(config)
        rep = counters.get(h, 0)
        counters[h] = rep + 1
        errored = outcome is None
        records.append(
            {
                "run_id": "r",
                "config_hash": h,
                "config": dict(config),
                "seed": 1000 + rep,
                "replicate_index": rep,
                "outcome": outcome,
                "t": None if errored else t,
                "horizon": None if errored else horizon,
                "confidence": None,
                "meta": {},
                "error": "boom" if errored else None,
                "wall_time": 0.0,
                "backend_meta": {},
            }
        )
    df = pd.DataFrame.from_records(records, columns=M4_COLUMNS)
    df["t"] = df["t"].astype(float)
    df["horizon"] = df["horizon"].astype(float)
    return df.sort_values(["config_hash", "replicate_index"]).reset_index(drop=True)


def _empirical_survival(t: np.ndarray, times: np.ndarray) -> np.ndarray:
    return np.array([np.mean(t > ti) for ti in times])


def _greenwood_sum(curve: KMCurve) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(curve.survival > 0, curve.var / curve.survival**2, np.nan)


def _load_golden_cells() -> dict[tuple[float, float], lattice.Cell]:
    return {(c.gain, c.load): c for c in lattice.design_cells()}


@pytest.fixture(scope="module")
def frames(lattice_store: Store) -> dict[str, pd.DataFrame]:
    return {run_id: lattice_store.read(run_id) for run_id in RUNS}


@pytest.fixture(scope="module")
def km_tables(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {run_id: cell_table(frames[run_id], lattice.EVENT) for run_id in RUNS}


# ---------- I1: censor ----------


def test_i1_censor_adds_observed_and_drops_errored() -> None:
    df = _frame(
        [
            ({"a": 1}, "fell", 1.0, 5.0),
            ({"a": 1}, "survived", 5.0, 5.0),
            ({"a": 1}, None, None, 5.0),
            ({"a": 2}, "timeout", 3.0, 5.0),
        ]
    )
    out = censor(df, "fell")
    assert list(out.columns) == [*df.columns, "observed"]
    assert len(out) == 3
    assert out["outcome"].notna().all()
    assert out.attrs["n_errored"] == 1
    assert out["observed"].dtype == bool
    assert list(out["observed"]) == list(out["outcome"] == "fell")
    kept = df[df["outcome"].notna()]
    assert list(out["t"]) == list(kept["t"])


def test_i1_censor_no_errored_rows_records_zero() -> None:
    df = _frame([({"a": 1}, "fell", 1.0, 5.0), ({"a": 1}, "survived", 5.0, 5.0)])
    out = censor(df, "fell")
    assert out.attrs["n_errored"] == 0 and len(out) == 2


# ---------- I2: KM with zero censoring is the empirical survival function ----------


@given(data=tied_survival_data())
def test_i2_km_uncensored_equals_empirical_survival(data) -> None:
    t, _ = data
    observed = np.ones_like(t, dtype=bool)
    curve = kaplan_meier(t, observed)
    assert list(curve.times) == sorted(set(t.tolist()))
    np.testing.assert_allclose(
        curve.survival, _empirical_survival(t, curve.times), rtol=0, atol=TOL_EXACT
    )


# ---------- I3: monotone, starts at 1, right-continuous ----------


@given(data=tied_survival_data())
def test_i3_km_monotone_and_starts_at_one(data) -> None:
    t, observed = data
    curve = kaplan_meier(t, observed)
    assert np.all(np.diff(curve.times) > 0)
    assert np.all(curve.survival <= 1.0 + TOL_EXACT) and np.all(curve.survival >= -TOL_EXACT)
    assert np.all(np.diff(curve.survival) <= TOL_EXACT)
    assert curve.at(0.0) == 1.0
    assert curve.at(-1.0) == 1.0
    if len(curve.times):
        assert curve.at(curve.times[0] - 1e-6) == 1.0
    else:
        assert curve.at(1e9) == 1.0


@given(data=tied_survival_data())
def test_i3_km_at_is_right_continuous_step(data) -> None:
    t, observed = data
    assume(observed.any())
    curve = kaplan_meier(t, observed)
    eps = 1e-6
    for i, ti in enumerate(curve.times):
        before = 1.0 if i == 0 else curve.survival[i - 1]
        assert curve.at(ti) == curve.survival[i]
        assert curve.at(ti - eps) == before
        assert curve.at(ti + eps) == curve.survival[i]
    assert curve.at(curve.times[-1] + 1e6) == curve.survival[-1]


# ---------- I4: ties ----------


@given(data=tied_survival_data())
def test_i4_km_ties_one_step_per_distinct_time(data) -> None:
    t, observed = data
    assume(observed.any())
    curve = kaplan_meier(t, observed)
    event_times = np.unique(t[observed])
    assert list(curve.times) == list(event_times)
    for i, ti in enumerate(curve.times):
        assert curve.n_at_risk[i] == np.sum(t >= ti)
        assert curve.n_events[i] == np.sum((t == ti) & observed)
    factors = 1.0 - curve.n_events / curve.n_at_risk
    np.testing.assert_allclose(curve.survival, np.cumprod(factors), rtol=0, atol=TOL_EXACT)


def test_i4_km_tie_factor_worked_example() -> None:
    t = np.array([1.0, 1.0, 1.0, 2.0, 2.0, 3.0])
    observed = np.array([True, True, False, True, True, False])
    curve = kaplan_meier(t, observed)
    assert list(curve.times) == [1.0, 2.0]
    assert list(curve.n_at_risk) == [6, 3]
    assert list(curve.n_events) == [2, 2]
    np.testing.assert_allclose(curve.survival, [4 / 6, (4 / 6) * (1 / 3)], atol=TOL_EXACT)


# ---------- I5: Greenwood ----------


@given(data=tied_survival_data())
def test_i5_greenwood_starts_from_zero_and_sum_is_non_decreasing(data) -> None:
    t, observed = data
    assume(observed.any())
    curve = kaplan_meier(t, observed)
    assert np.all(np.isfinite(curve.var))
    assert np.all(curve.var >= -TOL_EXACT)
    n0, d0 = curve.n_at_risk[0], curve.n_events[0]
    first_term = 0.0 if n0 == d0 else d0 / (n0 * (n0 - d0))
    assert abs(curve.var[0] - curve.survival[0] ** 2 * first_term) <= TOL_EXACT
    gsum = _greenwood_sum(curve)
    alive = ~np.isnan(gsum)
    assert np.all(np.diff(gsum[alive]) >= -TOL_EXACT)
    assert np.all(curve.var[~alive] == 0.0)


def test_i5_greenwood_all_censored_has_no_variance() -> None:
    t = np.array([1.0, 2.0, 3.0])
    curve = kaplan_meier(t, np.zeros(3, dtype=bool))
    assert len(curve.times) == 0 and len(curve.var) == 0
    assert curve.at(10.0) == 1.0


# ---------- I6: lifelines KM reference ----------


def test_i6_km_matches_lifelines() -> None:
    lifelines = pytest.importorskip("lifelines")

    @settings(max_examples=60, deadline=None)
    @given(data=tied_survival_data(min_size=2, max_size=60))
    def check(data) -> None:
        t, observed = data
        assume(observed.any())
        curve = kaplan_meier(t, observed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kmf = lifelines.KaplanMeierFitter().fit(t, observed)
        ref_s = kmf.survival_function_.iloc[:, 0]
        ref_sum = kmf._cumulative_sq_
        ref_s_at = ref_s.reindex(curve.times, method="ffill").to_numpy()
        ref_var_at = (ref_s**2 * ref_sum).reindex(curve.times, method="ffill").to_numpy()
        np.testing.assert_allclose(curve.survival, ref_s_at, rtol=0, atol=TOL_EXACT)
        np.testing.assert_allclose(curve.var, ref_var_at, rtol=0, atol=TOL_ORACLE)

    check()


# ---------- I7: AJ with one event is 1 - KM ----------


@given(data=tied_competing_data(events=("fell",)))
def test_i7_aj_single_event_equals_one_minus_km(data) -> None:
    t, outcome = data
    observed = outcome == "fell"
    assume(observed.any())
    km = kaplan_meier(t, observed)
    cif = aalen_johansen(t, outcome, ["fell"])
    assert isinstance(cif, CIFCurve) and set(cif.cif) == {"fell"}
    for tau in np.unique(t):
        assert abs(cif.at("fell", tau) - (1.0 - km.at(tau))) <= TOL_EXACT
    assert abs(cif.at("fell", 0.0)) <= TOL_EXACT


# ---------- I8: CIF shape ----------


@given(data=tied_competing_data(events=("fell", "violated", "timeout")))
def test_i8_cif_monotone_and_sum_bounded(data) -> None:
    t, outcome = data
    events = ["fell", "violated", "timeout"]
    cif = aalen_johansen(t, outcome, events)
    assert set(cif.cif) == set(events)
    assert np.all(np.diff(cif.times) > 0)
    total = np.zeros(len(cif.times))
    for k in events:
        f = cif.cif[k]
        assert len(f) == len(cif.times)
        assert np.all(f >= -TOL_EXACT)
        assert np.all(np.diff(f) >= -TOL_EXACT)
        total += f
    assert np.all(total <= 1.0 + TOL_EXACT)
    for tau in [0.0, *np.unique(t), 1e9]:
        assert sum(cif.at(k, tau) for k in events) <= 1.0 + TOL_EXACT


@given(data=tied_competing_data(events=("fell", "violated")))
def test_i8_rows_outside_events_are_censored(data) -> None:
    t, outcome = data
    both = aalen_johansen(t, outcome, ["fell", "violated"])
    only = aalen_johansen(t, outcome, ["fell"])
    assert set(only.cif) == {"fell"}
    tail = both.at("fell", 1e9) + both.at("violated", 1e9)
    assert tail <= 1.0 + TOL_EXACT
    assert only.at("fell", 1e9) >= both.at("fell", 1e9) - TOL_EXACT


# ---------- I9: lifelines Aalen-Johansen reference ----------


def test_i9_aj_matches_lifelines() -> None:
    lifelines = pytest.importorskip("lifelines")

    @settings(max_examples=25, deadline=None)
    @given(data=distinct_competing_data(events=("a", "b", "c"), min_size=6, max_size=40))
    def check(data) -> None:
        t, outcome = data
        events = ["a", "b", "c"]
        assume(all(np.any(outcome == k) for k in events))
        cif = aalen_johansen(t, outcome, events)
        codes = {"survived": 0, "a": 1, "b": 2, "c": 3}
        e = np.array([codes[o] for o in outcome])
        taus = np.unique(t)
        for k in events:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ajf = lifelines.AalenJohansenFitter(calculate_variance=False).fit(
                    t, e, event_of_interest=codes[k]
                )
            ref = ajf.cumulative_density_.iloc[:, 0].reindex(taus, method="ffill").to_numpy()
            ours = np.array([cif.at(k, tau) for tau in taus])
            np.testing.assert_allclose(ours, ref, rtol=0, atol=TOL_ORACLE)

    check()


# ---------- I10: Wilson ----------


@given(n=st.integers(min_value=1, max_value=500), frac=st.floats(min_value=0, max_value=1))
def test_i10_wilson_bounds_and_containment(n: int, frac: float) -> None:
    k = min(n, int(round(frac * n)))
    lo, hi = wilson(k, n)
    assert 0.0 <= lo <= k / n <= hi <= 1.0
    if k == 0:
        assert lo == 0.0
    if k == n:
        assert hi == 1.0


def test_i10_wilson_edges_exact() -> None:
    assert wilson(0, 10)[0] == 0.0
    assert wilson(10, 10)[1] == 1.0
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi


def test_i10_wilson_matches_statsmodels() -> None:
    proportion = pytest.importorskip("statsmodels.stats.proportion")
    from scipy.stats import norm

    z = float(norm.ppf(0.975))

    @given(n=st.integers(min_value=1, max_value=500), frac=st.floats(min_value=0, max_value=1))
    def check(n: int, frac: float) -> None:
        k = min(n, int(round(frac * n)))
        lo, hi = wilson(k, n, z=z)
        ref_lo, ref_hi = proportion.proportion_confint(k, n, alpha=0.05, method="wilson")
        assert abs(lo - float(ref_lo)) <= TOL_EXACT
        assert abs(hi - float(ref_hi)) <= TOL_EXACT

    check()


# ---------- I11: cell_table shape ----------
# `n` counts the rows that survive censor(): errored rows are excluded from `n` and
# reported in `n_errored`, so event_rate = n_events / n is a rate over analyzable episodes.


def _two_cell_frame() -> pd.DataFrame:
    rows = []
    for rep in range(8):
        rows.append(({"mu": 0.2}, "fell" if rep < 5 else "survived", 1.0 + rep if rep < 5 else 5.0, 5.0))
        rows.append(({"mu": 0.9}, "fell" if rep < 2 else "survived", 0.5 + rep if rep < 2 else 5.0, 5.0))
    rows.append(({"mu": 0.9}, None, None, 5.0))
    return _frame(rows)


def test_i11_cell_table_one_row_per_hash_sorted_exact_columns() -> None:
    df = _two_cell_frame()
    table = cell_table(df, "fell")
    assert list(table.columns) == CELL_TABLE_COLUMNS
    assert list(table["config_hash"]) == sorted(df["config_hash"].unique())
    assert len(table) == df["config_hash"].nunique()
    by_hash = table.set_index("config_hash")
    h_low, h_high = config_hash({"mu": 0.2}), config_hash({"mu": 0.9})
    assert by_hash.loc[h_low, "n"] == 8 and by_hash.loc[h_low, "n_errored"] == 0
    assert by_hash.loc[h_high, "n"] == 8 and by_hash.loc[h_high, "n_errored"] == 1
    assert by_hash.loc[h_low, "n_events"] == 5 and by_hash.loc[h_high, "n_events"] == 2
    assert abs(by_hash.loc[h_low, "event_rate"] - 5 / 8) <= TOL_EXACT
    assert by_hash.loc[h_low, "config"] == {"mu": 0.2}
    assert isinstance(by_hash.loc[h_low, "curve"], KMCurve)
    assert by_hash.loc[h_low, "event_rate_lo"] <= 5 / 8 <= by_hash.loc[h_low, "event_rate_hi"]


def test_i11_cell_table_aj_curve_type_and_s_at_horizon() -> None:
    df = _two_cell_frame()
    table = cell_table(df, "fell", method="aj", events=["fell"])
    assert list(table.columns) == CELL_TABLE_COLUMNS
    assert all(isinstance(c, CIFCurve) for c in table["curve"])
    assert np.all((table["s_at_horizon"] >= -TOL_EXACT) & (table["s_at_horizon"] <= 1 + TOL_EXACT))


def test_i11_cell_table_horizon_defaults_to_frame_max() -> None:
    df = _two_cell_frame()
    default = cell_table(df, "fell").drop(columns=["curve"])
    explicit = cell_table(df, "fell", horizon=5.0).drop(columns=["curve"])
    pd.testing.assert_frame_equal(default, explicit)


# ---------- I12: mixed horizons ----------


def test_i12_cell_table_rejects_mixed_horizons() -> None:
    df = _frame(
        [
            ({"mu": 0.2}, "fell", 1.0, 5.0),
            ({"mu": 0.2}, "survived", 5.0, 5.0),
            ({"mu": 0.9}, "survived", 8.0, 8.0),
        ]
    )
    with pytest.raises(SurvivalError):
        cell_table(df, "fell")


# ---------- I13: multi-outcome guard ----------


def test_i13_guard_empty_for_event_plus_one_other() -> None:
    df = _frame([({"a": 1}, "fell", 1.0, 5.0), ({"a": 1}, "survived", 5.0, 5.0)])
    assert multi_outcome_guard(df, "fell") == []


def test_i13_guard_lists_sorted_others() -> None:
    df = _frame(
        [
            ({"a": 1}, "fell", 1.0, 5.0),
            ({"a": 1}, "timeout", 4.0, 5.0),
            ({"a": 1}, "survived", 5.0, 5.0),
            ({"a": 1}, "violated", 2.0, 5.0),
        ]
    )
    assert multi_outcome_guard(df, "fell") == ["survived", "timeout", "violated"]


def test_i13_cell_table_km_warns_with_names() -> None:
    df = _frame(
        [
            ({"a": 1}, "fell", 1.0, 5.0),
            ({"a": 1}, "timeout", 4.0, 5.0),
            ({"a": 1}, "survived", 5.0, 5.0),
        ]
    )
    with pytest.warns(UserWarning) as record:
        cell_table(df, "fell", method="km")
    messages = " ".join(str(w.message) for w in record)
    # PF4 (PF4.19): the warning names the outcomes that end a run before the horizon; "timeout"
    # does (t = 4.0), "survived" is seen only at the horizon (t = 5.0) and is not named.
    assert "timeout" in messages and "survived" not in messages


def test_i13_cell_table_km_silent_when_guard_empty() -> None:
    df = _frame([({"a": 1}, "fell", 1.0, 5.0), ({"a": 1}, "survived", 5.0, 5.0)])
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        cell_table(df, "fell", method="km")


# ---------- I14 / I15: golden per-cell counts ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i14_i15_golden_per_cell_event_counts(km_tables: dict[str, pd.DataFrame], run_id: str) -> None:
    golden_cells = _load_golden_cells()
    assert len(golden_cells) == CELLS
    table = km_tables[run_id]
    assert len(table) == CELLS
    matched = 0
    for _, row in table.iterrows():
        key = (row["config"]["gain"], row["config"]["load"])
        assert key in golden_cells, key
        assert row["n_events"] == getattr(golden_cells[key], TRIPPED_KEY[run_id]), key
        assert row["n"] == 32 and row["n_errored"] == 0
        matched += 1
    assert matched == CELLS


# ---------- I17: no mid-horizon censoring on the fixture ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i17_s_at_horizon_is_one_minus_event_rate(
    km_tables: dict[str, pd.DataFrame], run_id: str
) -> None:
    table = km_tables[run_id]
    np.testing.assert_allclose(
        table["s_at_horizon"].to_numpy(dtype=float),
        1.0 - table["event_rate"].to_numpy(dtype=float),
        rtol=0,
        atol=TOL_EXACT,
    )


# ---------- I18: AJ with a single event agrees with KM on the fixture ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i18_aj_single_event_matches_km_on_fixture(
    frames: dict[str, pd.DataFrame], km_tables: dict[str, pd.DataFrame], run_id: str
) -> None:
    km = km_tables[run_id]
    aj = cell_table(frames[run_id], lattice.EVENT, method="aj", events=[lattice.EVENT])
    assert list(aj["config_hash"]) == list(km["config_hash"])
    np.testing.assert_allclose(
        aj["s_at_horizon"].to_numpy(dtype=float),
        km["s_at_horizon"].to_numpy(dtype=float),
        rtol=0,
        atol=TOL_EXACT,
    )


# ---------- KMCurve.median (not an invariant) ----------


def test_median_none_when_survival_never_reaches_half() -> None:
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    observed = np.array([True, False, False, False, False])
    assert kaplan_meier(t, observed).median() is None


def test_median_is_first_crossing_time() -> None:
    t = np.array([1.0, 2.0, 3.0, 4.0])
    observed = np.array([True, True, True, True])
    assert kaplan_meier(t, observed).median() == 2.0
