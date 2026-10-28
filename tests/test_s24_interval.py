"""S24 -- the interval on the delta: the frozen tests for C1-C19.

An interval on each compared cell's change, at a level that pays for the choice of the cell.

**The S24 names are reached through the module** -- ``diff.score_p_rd``, not ``score_p_rd`` --
so a name that does not exist fails the tests that use it rather than the collection of the whole
run. The other names (``multi_diff``, ``CELLS_COLUMNS``, ``Store``) are imported normally.

**What S24 is.** The other numbers the tool reports about a cell say whether something moved or
what could not have been seen; the interval says how big the move is. It is an interval on
``delta`` at a level that pays for the fact that the cell was chosen out of a grid, and its
disagreement with the verdict is counted rather than reconciled.

Six facts about the data and the method explain why several tests below look the way they do.

1. **``R`` is the BH rejection count, not the count of cells that moved at the horizon.** On
   the lattice (``tests/lattice.py``) with ``events=("tripped",)`` under ``logrank_bh`` the
   rejection count is **39** and the count a horizon rule would label is **27**: the twelve
   ``load`` 100 conditions are ``32/32`` vs ``32/32``, every episode tripped in both arms,
   ``delta`` is exactly ``0``, and log-rank rejects them on the trip *times* (the after run trips
   sooner). That configuration is the only fixture on which the two definitions differ, so C2 is
   written on it and nowhere else. On every other configuration both definitions pass.
2. **The family is the flat BH family ``multi_diff`` runs**, and C1/C2/C18 say so. A nested
   family (leaves within a rejected Level 2 group) is a separate object with
   its own level; nothing here is designed for it.
3. **C4/C5/C6/C7 would contradict each other at the parameter-space boundary.** At ``0/32`` vs
   ``32/32`` the point estimate is ``1.0``, so C4 forces ``ci_hi >= 1.0``, C5 forces
   ``ci_hi <= 1.0``, and C7 then makes ``score_p_rd(..., delta=1.0)`` equal ``1.0`` rather than
   ``alpha``. So C6 is scoped to interior endpoints and **C6b pins the boundary positively** --
   an exemption with nothing asserting the exempted behaviour is a hole. 39 of the lattice's 72
   conditions (54%) sit on a boundary.
4. **The lattice is 22 lower / 0 higher under Fisher and 27 lower / 0 higher under McNemar**, the
   counts its own references give (``lattice.fisher``, ``lattice.mcnemar``).
5. **An ``R == 0`` fixture exists**: the lattice under ``logrank_bh`` with the inferred event
   set (``held``). C1's primary fixture is still the synthetic identical-arms pair, because the
   lattice route rests on a log-rank tie convention that is still open; the
   lattice corroborates.
6. **The censoring guard cannot fire.** ``_truncate_raw`` censors at the horizon, which is ``>=``
   every retained event time, and the estimator reduces to the naive proportion when no
   censoring precedes an event. Five constructed shapes were measured -- late truncation, two
   event times, a tie exactly at the horizon, three competing kinds, and 19 distinct event times
   -- and every one deviates by ``0.0``. ``basis == "censored"`` is unreachable from any input
   to ``multi_diff``, so **C13 pins the contract and the negative, not the branch**, and a
   guard that checked arm A only could not be caught. Said here rather than left for someone to
   discover from a green suite.

**Conventions this file fixes.**

- **``n_rejected`` and ``alpha_star`` are fields.** The CLI prints ``q x R / m``, and recovering
  ``R`` as ``alpha_star * m / q`` would be a float round-trip to an integer. Every interval field
  is defaulted, so a ``MultiDiffResult`` built by hand from the other fields still constructs.
- **``alpha_star`` is ``None`` when nothing was rejected**, not ``0.0``. Prove's posture
  is that a result with nothing behind it must not claim a number, and a printed ``alpha* =
  0.0`` is the same false precision as a printed ``(-1, 1)``. ``n_rejected`` stays ``0``: that
  is a count, not a claim.
- **C18 pins the arithmetic's components, not the float formatting.** Rendering
  ``alpha*`` at four decimals prints ``0.0000`` for the motivating
  case (1200 cells, one rejection, ``alpha* = 4.2e-05``). Pinning that format would pin a
  defect. The regex below captures the level, ``R`` and ``m`` and checks them against the
  fields; the family name and the basis are pinned as literals.
- **An endpoint is "interior" iff ``-1.0 < endpoint < 1.0``** -- observable from the return
  value alone, no reach into how it was found.
- **Render the percentage with the ``%`` format spec, not by multiplying.**
  ``f"{multi.interval_level:.4%}"`` renders ``0.9925`` as ``99.2500%``. Printing ``alpha_star``
  with ``:g`` rather than ``:.4f`` also avoids that four-decimal rounding defect, and the regex
  above accepts either.

**Named non-observables.** The constrained MLE is not asserted anywhere: the route is
deliberately left open (a Farrington-Manning cubic or a one-dimensional
maximisation), and C7, C8 and C10 pin the object by its properties instead. Nothing here reads
the bisector, its iteration cap, or its tolerance.
"""

from __future__ import annotations

import json
import math
import re
import warnings
from collections.abc import Mapping
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from poisson_prove import cli
from poisson_prove import diff as diff_mod
from poisson_prove.diff import CELLS_COLUMNS, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store

import lattice

#: The generated pair (``tests/lattice.py``): the before run and the after run.
LATTICE_ROOT = lattice.root()
RUN_A, RUN_B = lattice.RUN_A, lattice.RUN_B
EVENT, OTHER = lattice.EVENT, lattice.OTHER

#: The interval frame's columns and bases, stated as constants here.
EXPECTED_INTERVAL_COLUMNS = ("event", "config_hash", "config", "ci_lo", "ci_hi", "basis")
EXPECTED_INTERVAL_BASES = ("score_rd", "score_rd_paired", "censored")

#: The censoring guard, per arm. The numeric form, not the structural one: it holds whatever a
#: later change does to the estimator.
CIF_TOLERANCE = 1e-12

#: Alphas the unit tests run at: the nominal one, the two alpha* values the lattice produces
#: (``q x R / m``: the log-rank family on ``tripped``, 39 of 72, and Fisher over both events, 44 of
#: 144), and a small one.
ALPHAS = (0.05, 0.05 * 39 / 72, 0.05 * 44 / 144, 0.001)

#: Literal tables. ``(events_a, n_a, events_b, n_b)``. The first three are boundary shapes:
#: nothing anywhere (C9's sole-catch table), a full sweep up, and a full sweep down.
TABLES = (
    (0, 32, 0, 32),
    (0, 32, 32, 32),
    (32, 32, 0, 32),
    (32, 32, 32, 32),
    (5, 32, 12, 32),
    (16, 32, 16, 32),
    (1, 8, 7, 8),
    (3, 10, 3, 15),
    (0, 5, 1, 5),
    (2, 7, 6, 11),
)

#: Paired tables, ``(b, c, n)``: ``b`` discordant one way, ``c`` the other, ``b + c <= n``.
PAIRED_TABLES = (
    (0, 0, 32),
    (0, 32, 32),
    (32, 0, 32),
    (4, 9, 32),
    (7, 7, 32),
    (1, 2, 8),
    (0, 1, 5),
)

#: The no-interval line, verbatim.
NO_INTERVAL_LINE = "intervals: none (nothing significant; the MDE lines above are the honest bound)"

#: C18's first line. The level, alpha*, R and m are captured and checked against the fields
#: rather than pinned as formatted floats -- see the docstring.
INTERVAL_LINE = re.compile(
    r"^intervals: ([0-9.]+)% \(alpha\* = ([0-9.eE+-]+) = q x (\d+) / (\d+) over the flat BH family\), "
    r"basis (\w+)$",
    re.MULTILINE,
)

#: C14. ``PAIR`` is ``multi_diff(before, after, events=(EVENT, OTHER), method="fisher_bh")``;
#: ``LOGRANK`` is the same pair at ``events=(EVENT,)`` and ``method="logrank_bh"``.
# PF4.3, PF4.15, PF4.20: C14 reads the markdown's facts from the result itself (the headline,
# the trade line, each table's rows), not a hash of its bytes.
# PF4.20: the lattice's runs give ``tripped`` and ``held`` no kind, so the headline counts
# read in direction words; the numbers are the ones ``lattice.fisher`` gives (22 and 0 each way).
PAIR_HEADLINE = (
    "held: 0 lower, 22 higher · tripped: 22 lower, 0 higher\n"
    "(aalen_johansen + fisher_bh, BH q<0.05 over 144 tests, unpaired)"
)
#: LS: ``tripped`` and ``held`` are exact complements in all 72 cells and both arms,
#: so this pair's trade line is the complement sentence and the
#: "moved failures" sentence appears in no file under ``src/`` (LS13).
PAIR_TRADE_LINE = (
    "tripped and held are complements here: in all 72 conditions every trial recorded exactly one "
    "of the two, so each rate is one minus the other and each change is the other's with its sign "
    "flipped. The 22 conditions where held rose are the 22 where tripped fell: one finding, reported "
    "twice. Naming one of the two shows it once."
)
#: The pair's direction counts per event, as ``lattice.fisher`` gives them: ``(lower, higher)``.
PAIR_DIRECTIONS = {EVENT: (22, 0), OTHER: (0, 22)}

# PF4.13, PF4.20: under log-rank a rejected cell's direction is the sign of B's observed
# minus expected events; ``lattice.logrank`` gives 27 lower / 12 higher / 33 unchanged (the twelve
# higher are the ``load`` 100 conditions, where the after run trips sooner), printed in direction
# words.
# PF4.41: every surface that names logrank_bh says it tests the cause-specific
# hazard, the headline's method included.
LOGRANK_HEADLINE = (
    "tripped: 27 lower, 12 higher\n"
    "(aalen_johansen + logrank_bh (cause-specific hazard), BH q<0.05 over 72 tests, unpaired)"
)
LOGRANK_DIRECTIONS = (27, 12)

#: Fact 1 above, restated as a constant so C2's fixture cannot be
#: swapped for one that does not discriminate. The lattice, ``events=(EVENT,)``, ``logrank_bh``.
LOGRANK_N_TESTS = 72
LOGRANK_REJECTIONS = 39
# PF4.13: a rejected cell is labelled by the log-rank statistic, so the 12 rejected
# cells at 32/32 vs 32/32 (``delta`` exactly 0) are changes too and the verdict sum equals the
# rejection count: 27 lower + 12 higher (``lattice.logrank``). The 27 rejected cells whose horizon
# ``delta`` is not 0 are the count a horizon rule would label, and that is the count a wrong
# level would be built from.
LOGRANK_VERDICT_SUM = 39
LOGRANK_HORIZON_MOVED = 27


# ---------- data builders: construction only, no assertions and no decisions ----------


def write_run(
    store: Store,
    run_id: str,
    *,
    salt: str,
    cells: dict[str, int],
    n: int = 8,
    horizon: float = 5.0,
) -> None:
    """A complete synthetic run over one categorical ``task``: ``cells[task]`` of ``n`` rows end
    in ``fail`` at t=2, the rest in ``ok`` at the horizon. ``test_m13_viewer.write_run``'s shape,
    restated here rather than imported."""
    store.create_run(
        RunManifest(
            run_id=run_id,
            target_id="synthetic@v0",
            t_unit="steps",
            run_salt=salt,
            axis_types={"task": "categorical"},
            backend="synthetic",
            environment={"note": "built by test_s24_interval"},
        )
    )
    records = []
    for index, (task, fails) in enumerate(cells.items()):
        for k in range(n):
            episode = (
                Episode(outcome="fail", t=2.0, horizon=horizon)
                if k < fails
                else Episode(outcome="ok", t=horizon, horizon=horizon)
            )
            records.append(
                EpisodeRecord.from_episode(
                    episode,
                    run_id=run_id,
                    config={"task": task},
                    seed=1000 * index + k,
                    replicate_index=k,
                    wall_time=0.0,
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


def bh_over(values: Any) -> list[float]:
    """``lattice.bh`` (BH written out, independent of ``diff.bh``) over a column of p values."""
    return [float(v) for v in lattice.bh(list(values))]


def assert_q_column_is_bh_over_its_p_column(result: Any, reference: Mapping[str, Mapping[str, Mapping[str, Any]]] | None, events: tuple[str, ...]) -> None:
    """The q column, as facts: the family covers ``events`` in that order, one row per condition
    of the lattice design each, in sorted-hash order; its q
    values, in that order, equal BH over its p values exactly (one family over every event); and
    where ``reference`` (per event, per condition) holds an independent p, each p equals it exactly
    and each q equals BH over the reference's p column exactly."""
    assert tuple(result.events) == events and result.n_tests == len(events) * lattice.CELLS, (result.events, result.n_tests)
    order = sorted(lattice.config_hash(c.config) for c in lattice.design_cells())
    for event in result.events:
        assert list(result.by_event[event].cells["config_hash"]) == order, event
    ps = [float(v) for e in result.events for v in result.by_event[e].cells["p"]]
    qs = [float(v) for e in result.events for v in result.by_event[e].cells["q"]]
    assert len(ps) == result.n_tests
    assert qs == bh_over(ps)
    if reference is not None:
        ref_p = [reference[e][h]["p"] for e in result.events for h in result.by_event[e].cells["config_hash"]]
        assert ps == ref_p
        assert qs == bh_over(ref_p)


def assert_delta_column_is_the_naive_difference(result: Any, events: tuple[str, ...]) -> None:
    """The delta column, as facts: the family covers ``events`` in that order, each in
    sorted-hash order; every row's delta is ``events_b/n_b - events_a/n_a`` exactly, with the
    reference's sign of zero (``-0`` apart from ``0``), and its counts and delta are the lattice
    design's (``lattice.fisher``'s)."""
    assert tuple(result.events) == events and result.n_tests == len(events) * lattice.CELLS, (result.events, result.n_tests)
    for event in result.events:
        reference = lattice.fisher(event)
        cells = result.by_event[event].cells
        assert list(cells["config_hash"]) == sorted(reference), event
        for row in cells.itertuples(index=False):
            ref = reference[row.config_hash]
            assert (row.n_a, row.n_b, row.events_a, row.events_b) == (ref["n_a"], ref["n_b"], ref["events_a"], ref["events_b"]), (event, row.config_hash)
            assert row.delta == row.events_b / row.n_b - row.events_a / row.n_a == ref["delta"], (event, row.config_hash)
            assert math.copysign(1.0, row.delta) == math.copysign(1.0, ref["delta"]), (event, row.config_hash, row.delta)


def assert_coverage_is_the_design(result: Any) -> None:
    """The coverage frame, as facts: ``coverage.to_json(orient="records")`` is the string the
    lattice design gives -- one record per condition in
    sorted-hash order, each with its own condition, every row of both runs present and holding an
    outcome, every condition comparable with no cause -- with its columns in order and its
    integers, booleans and nulls typed as written."""
    design = {lattice.config_hash(c.config): c.config for c in lattice.design_cells()}
    assert len(result.coverage) == len(design) == lattice.CELLS
    expected = [
        {"config_hash": h, "config": design[h], "rows_a": lattice.N, "rows_b": lattice.N, "no_outcome_a": 0,
         "no_outcome_b": 0, "comparable": True, "cause": None}
        for h in sorted(design)
    ]
    assert result.coverage.to_json(orient="records") == json.dumps(expected, separators=(",", ":"))


def assert_logrank_column_is_the_reference(result: Any) -> None:
    """The log-rank family (one event, the lattice design's conditions in sorted-hash order) has its q
    column BH over its p column exactly, and each condition's p, q and direction are the
    independent log-rank reference's (``lattice.logrank``: lifelines on the stored times, BH
    written out) to 1e-12 relative."""
    assert_q_column_is_bh_over_its_p_column(result, None, (EVENT,))
    reference = lattice.logrank(EVENT)
    cells = result.by_event[EVENT].cells
    assert set(cells["config_hash"]) == set(reference)
    for row in cells.itertuples(index=False):
        assert row.p == pytest.approx(reference[row.config_hash]["p"], rel=1e-12, abs=0), row.config_hash
        assert row.q == pytest.approx(reference[row.config_hash]["q"], rel=1e-12, abs=0), row.config_hash
        assert row.direction == reference[row.config_hash]["direction"], row.config_hash


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def lattice_pair(lattice_trees: Any) -> Any:
    """The lattice over both events under Fisher. R = 44 over 144 tests, and the rejection count
    and the verdict sum agree here -- which is exactly why C2 cannot be written on it alone. The
    unpaired-analysis warning (both manifests carry the same run_salt by construction) is not what
    any test below is about; the shared comparison silences it."""
    return lattice_trees.multi((EVENT, OTHER), "fisher_bh")


@pytest.fixture(scope="module")
def lattice_logrank(lattice_trees: Any) -> Any:
    """The one configuration on which the BH rejection count (39) and the count of rejected cells
    whose horizon delta moved (27) differ. C2's discriminating fixture."""
    return lattice_trees.multi((EVENT,), "logrank_bh")


@pytest.fixture(scope="module")
def lattice_inferred_logrank(lattice_trees: Any) -> Any:
    """The lattice with the inferred event set under log-rank: R == 0 over 72 tests. C1's
    corroborating zero fixture."""
    return lattice_trees.multi(None, "logrank_bh")


@pytest.fixture(scope="module")
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One store holding four runs: an identical pair (nothing to reject), a moved pair
    (everything rejected), and a second candidate identical to the moved one but carrying a
    different run salt, so C12 can hold the frames fixed and vary only the provenance."""
    root = tmp_path_factory.mktemp("s24-synth")
    store = Store(root)
    write_run(store, "same-a", salt="same-salt", cells={"t0": 2, "t1": 4, "t2": 6})
    write_run(store, "same-b", salt="same-salt", cells={"t0": 2, "t1": 4, "t2": 6})
    write_run(store, "moved-a", salt="moved-salt", cells={"t0": 0, "t1": 2, "t2": 4}, n=32)
    write_run(store, "moved-b", salt="moved-salt", cells={"t0": 32, "t1": 26, "t2": 20}, n=32)
    write_run(store, "moved-b-unpaired", salt="other-salt", cells={"t0": 32, "t1": 26, "t2": 20}, n=32)
    return root


def synth_diff(root: Path, a: str, b: str, method: str = "fisher_bh") -> Any:
    store = Store(root)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return multi_diff(
            store.read(a),
            store.read(b),
            events=["fail"],
            method=method,
            manifest_a=store.manifest(a),
            manifest_b=store.manifest(b),
        )


def assert_intervals_always(result: Any, rejections: int) -> None:
    """PF4.42: the interval frame has a row for every compared row, the level is
    ``1 - q * max(R, 1) / M`` and ``alpha_star`` its complement, and every cell carries its interval
    at that level, whether anything was flagged or not."""
    assert isinstance(result.intervals, pd.DataFrame), type(result.intervals)
    assert len(result.intervals) == result.n_tests > 0, (len(result.intervals), result.n_tests)
    level = 1.0 - result.q * max(rejections, 1) / result.n_tests
    assert result.interval_level is not None and abs(result.interval_level - level) <= 1e-12, result.interval_level
    assert result.alpha_star is not None and abs(result.alpha_star - result.q * max(rejections, 1) / result.n_tests) <= 1e-12
    for event in result.events:
        cells = result.by_event[event].cells
        assert ((cells["ci_level"] - level).abs() <= 1e-12).all(), event
        assert cells["ci_lo"].notna().all() and cells["ci_hi"].notna().all(), event


def format_level(level: float) -> str:
    """PF4.42: a level as a percentage to at most three decimals (``95%``, ``99.722%``)."""
    return f"{level * 100:.3f}".rstrip("0").rstrip(".") + "%"


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(argv, stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def without_notes(err: str) -> str:
    """Stderr with the ``note:`` lines removed. Prove's own warning (``UnpairedAnalysis``, on two
    runs sharing a salt) reaches the CLI's stderr as one ``note:`` line."""
    return "".join(line for line in err.splitlines(keepends=True) if not line.startswith("note: "))


# ---------- C7: the analytic point, the one place the constrained MLE is known ----------


@pytest.mark.math
@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
def test_c7_the_unpaired_statistic_is_one_at_the_point_estimate(
    events_a: int, n_a: int, events_b: int, n_b: int
) -> None:
    """*How* the constrained MLE is found is left open, deliberately, because a
    mistranscribed Farrington-Manning cubic is a silent statistical bug no reviewer catches by
    reading. This is the guard on that openness: at ``delta == p_b_hat - p_a_hat`` the
    constrained MLEs coincide with the unconstrained ones, the score is exactly zero and the
    two-sided p-value is exactly 1. While this fails, nothing downstream means anything.
    """
    delta = events_b / n_b - events_a / n_a
    assert abs(diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=delta) - 1.0) <= 1e-12


@pytest.mark.math
@pytest.mark.parametrize("b,c,n", PAIRED_TABLES)
def test_c7_the_paired_statistic_is_one_at_the_point_estimate(b: int, c: int, n: int) -> None:
    """Tango's paired twin of the clause above. The point estimate for ``n`` pairs with ``b``
    discordant one way and ``c`` the other is ``(c - b) / n``."""
    assert abs(diff_mod.score_p_rd_paired(b, c, n, delta=(c - b) / n) - 1.0) <= 1e-12


@settings(deadline=None, max_examples=120)
@pytest.mark.math
@given(
    n_a=st.integers(min_value=1, max_value=200),
    n_b=st.integers(min_value=1, max_value=200),
    fa=st.floats(min_value=0.0, max_value=1.0),
    fb=st.floats(min_value=0.0, max_value=1.0),
)
def test_c7_the_unpaired_statistic_is_one_at_the_point_estimate_for_any_table(
    n_a: int, n_b: int, fa: float, fb: float
) -> None:
    """C7 is universal, not a property of the ten literal tables above. It is drawn over
    ``0 <= events <= n`` and ``1 <= n <= 200``; the two fractions draw the event counts so the
    boundary tables (all-zero, all-n) stay reachable."""
    events_a, events_b = round(fa * n_a), round(fb * n_b)
    delta = events_b / n_b - events_a / n_a
    assert abs(diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=delta) - 1.0) <= 1e-12


# ---------- C8: arm-swap symmetry ----------


@pytest.mark.math
@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
@pytest.mark.parametrize("delta", (-0.5, -0.125, 0.0, 0.125, 0.5))
def test_c8_swapping_the_arms_negates_the_delta_and_leaves_the_p_value_alone(
    events_a: int, n_a: int, events_b: int, n_b: int, delta: float
) -> None:
    """``H0: p_b - p_a == delta`` and ``H0: p_a - p_b == -delta`` are the same hypothesis. Code
    that pools, orders or clips asymmetrically fails here and passes C7, which is
    why both exist."""
    forward = diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=delta)
    reversed_ = diff_mod.score_p_rd(events_b, n_b, events_a, n_a, delta=-delta)
    assert abs(forward - reversed_) <= 1e-12


@settings(deadline=None, max_examples=120)
@pytest.mark.math
@given(
    n_a=st.integers(min_value=1, max_value=200),
    n_b=st.integers(min_value=1, max_value=200),
    fa=st.floats(min_value=0.0, max_value=1.0),
    fb=st.floats(min_value=0.0, max_value=1.0),
    delta=st.floats(min_value=-0.999, max_value=0.999),
)
def test_c8_arm_swap_symmetry_holds_for_any_table_and_any_delta(
    n_a: int, n_b: int, fa: float, fb: float, delta: float
) -> None:
    events_a, events_b = round(fa * n_a), round(fb * n_b)
    forward = diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=delta)
    reversed_ = diff_mod.score_p_rd(events_b, n_b, events_a, n_a, delta=-delta)
    assert abs(forward - reversed_) <= 1e-12


# ---------- C9: the boundary guard ----------


@pytest.mark.math
def test_c9_the_all_zero_table_gets_a_finite_non_degenerate_interval() -> None:
    """**The boundary guard.** A Wald interval on the risk difference collapses to the single
    point ``(0.0, 0.0)`` here, because its standard error is zero at ``p_hat = 0`` in both arms.
    The lattice puts 39 of its 72 conditions on a boundary (a run at 0/32 or 32/32), so the
    estimator that fails at the boundary fails on most of a grid, not on a corner case.

    Written as a literal ``0/32`` vs ``0/32`` table rather than pulled from a fixture because it
    is the guard against the estimator everyone reaches for first.
    """
    lo, hi = diff_mod.interval_rd(0, 32, 0, 32, alpha=0.05)
    assert -1.0 < lo < 0.0 < hi < 1.0, (lo, hi)


@pytest.mark.math
def test_c9_the_all_zero_paired_table_gets_a_finite_non_degenerate_interval() -> None:
    """The paired mirror: no discordant pairs either way, over 32 pairs."""
    lo, hi = diff_mod.interval_rd_paired(0, 0, 32, alpha=0.05)
    assert -1.0 < lo < 0.0 < hi < 1.0, (lo, hi)


# ---------- C6: the inversion, at interior endpoints ----------


@pytest.mark.math
@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
@pytest.mark.parametrize("alpha", ALPHAS)
def test_c6_an_interior_unpaired_endpoint_solves_the_score_test_at_alpha(
    events_a: int, n_a: int, events_b: int, n_b: int, alpha: float
) -> None:
    """The interval is the inversion of a score test, so each endpoint is a root of
    ``p(delta) = alpha``. Written against the p-value and not against a ``z`` quantile, so the
    ``alpha`` versus ``alpha/2`` error cannot be got wrong quietly: this is
    a two-sided p-value, and the endpoints solve ``p = alpha``, not ``p = alpha/2``.

    **Interior only.** Where an endpoint sits at ``±1`` the value is *attained* rather than
    solved for -- the parameter space ran out before the root did -- so there is nothing to
    invert. C6b pins that case positively rather than leaving it exempt and unasserted.
    """
    for endpoint in diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=alpha):
        if -1.0 < endpoint < 1.0:
            p = diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=endpoint)
            assert abs(p - alpha) <= 1e-9, (endpoint, p, alpha)


@pytest.mark.math
@pytest.mark.parametrize("b,c,n", PAIRED_TABLES)
@pytest.mark.parametrize("alpha", ALPHAS)
def test_c6_an_interior_paired_endpoint_solves_the_paired_score_test_at_alpha(
    b: int, c: int, n: int, alpha: float
) -> None:
    for endpoint in diff_mod.interval_rd_paired(b, c, n, alpha=alpha):
        if -1.0 < endpoint < 1.0:
            p = diff_mod.score_p_rd_paired(b, c, n, delta=endpoint)
            assert abs(p - alpha) <= 1e-9, (endpoint, p, alpha)


# ---------- C6b: the boundary the carve-out exempts, pinned positively ----------


@pytest.mark.math
@pytest.mark.parametrize("alpha", ALPHAS)
def test_c6b_the_upper_endpoint_is_exactly_one_when_the_point_estimate_is_one(
    alpha: float
) -> None:
    """``0/32`` vs ``32/32``: the point estimate is ``1.0``. C4 puts the point estimate inside
    the interval and C5 caps the interval at ``1.0``, so ``ci_hi`` is ``1.0`` exactly and C7
    makes the p-value there ``1.0`` rather than ``alpha``. That is the carve-out C6 takes, and
    this is the assertion that stops it being a hole.
    """
    lo, hi = diff_mod.interval_rd(0, 32, 32, 32, alpha=alpha)
    assert hi == 1.0 and lo < 1.0, (lo, hi)


@pytest.mark.math
@pytest.mark.parametrize("alpha", ALPHAS)
def test_c6b_the_lower_endpoint_is_exactly_minus_one_when_the_point_estimate_is_minus_one(
    alpha: float
) -> None:
    lo, hi = diff_mod.interval_rd(32, 32, 0, 32, alpha=alpha)
    assert lo == -1.0 and hi > -1.0, (lo, hi)


@pytest.mark.math
@pytest.mark.parametrize("alpha", ALPHAS)
def test_c6b_the_paired_endpoints_are_attained_at_the_two_extremes(alpha: float) -> None:
    """``c == n`` is every pair discordant in one direction, point estimate ``+1``; ``b == n`` is
    the mirror."""
    assert diff_mod.interval_rd_paired(0, 32, 32, alpha=alpha)[1] == 1.0
    assert diff_mod.interval_rd_paired(32, 0, 32, alpha=alpha)[0] == -1.0


@pytest.mark.math
@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
def test_c6b_an_endpoint_reaches_the_boundary_only_where_the_point_estimate_does(
    events_a: int, n_a: int, events_b: int, n_b: int
) -> None:
    """The carve-out's scope, stated as a biconditional rather than left as a licence. ``delta =
    1`` forces ``p_a = 0`` and ``p_b = 1`` exactly; on any other table the likelihood there is
    zero, the score test rejects, and the root lies strictly inside. So an endpoint at the
    boundary is not a fallback the bisector may take when it runs out of iterations -- it means
    one specific thing about the data, and nothing else may produce it.
    """
    lo, hi = diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=0.05)
    assert (hi == 1.0) == (events_a == 0 and events_b == n_b), (lo, hi)
    assert (lo == -1.0) == (events_a == n_a and events_b == 0), (lo, hi)


# ---------- C10: nesting in alpha ----------


@pytest.mark.math
@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
def test_c10_a_smaller_alpha_gives_an_interval_containing_the_larger_alphas(
    events_a: int, n_a: int, events_b: int, n_b: int
) -> None:
    """A smaller ``alpha`` rejects less, so its acceptance region is wider. Nesting is what
    tells a bisector that found a root from one that found a fixed point."""
    wide = diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=0.001)
    narrow = diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=0.05)
    assert wide[0] <= narrow[0] and narrow[1] <= wide[1], (wide, narrow)


@pytest.mark.math
@pytest.mark.parametrize("b,c,n", PAIRED_TABLES)
def test_c10_the_paired_interval_is_nested_in_alpha_too(b: int, c: int, n: int) -> None:
    wide = diff_mod.interval_rd_paired(b, c, n, alpha=0.001)
    narrow = diff_mod.interval_rd_paired(b, c, n, alpha=0.05)
    assert wide[0] <= narrow[0] and narrow[1] <= wide[1], (wide, narrow)


# ---------- C4 and C5 at the function level ----------


@settings(deadline=None, max_examples=150)
@pytest.mark.math
@given(
    n_a=st.integers(min_value=1, max_value=200),
    n_b=st.integers(min_value=1, max_value=200),
    fa=st.floats(min_value=0.0, max_value=1.0),
    fb=st.floats(min_value=0.0, max_value=1.0),
)
def test_c4_every_interval_contains_the_point_estimate(
    n_a: int, n_b: int, fa: float, fb: float
) -> None:
    """An interval that excludes its own point estimate has inverted a test it did not run."""
    events_a, events_b = round(fa * n_a), round(fb * n_b)
    lo, hi = diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=0.05)
    assert lo <= events_b / n_b - events_a / n_a <= hi, (lo, hi)


@settings(deadline=None, max_examples=150)
@pytest.mark.math
@given(
    n_a=st.integers(min_value=1, max_value=200),
    n_b=st.integers(min_value=1, max_value=200),
    fa=st.floats(min_value=0.0, max_value=1.0),
    fb=st.floats(min_value=0.0, max_value=1.0),
)
def test_c5_every_interval_lies_inside_the_unit_interval(
    n_a: int, n_b: int, fa: float, fb: float
) -> None:
    """``delta`` is a difference of two probabilities. An endpoint outside ``[-1, 1]`` is
    outside the parameter space, which is the shape a Wald interval takes near the boundary."""
    events_a, events_b = round(fa * n_a), round(fb * n_b)
    lo, hi = diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=0.05)
    assert -1.0 <= lo <= hi <= 1.0, (lo, hi)


@pytest.mark.math
@settings(deadline=None, max_examples=120)
@given(data=st.data())
def test_c4_and_c5_hold_for_the_paired_interval_too(data: st.DataObject) -> None:
    """``b + c <= n``: the discordant pairs cannot outnumber the pairs."""
    n = data.draw(st.integers(min_value=1, max_value=200))
    b = data.draw(st.integers(min_value=0, max_value=n))
    c = data.draw(st.integers(min_value=0, max_value=n - b))
    lo, hi = diff_mod.interval_rd_paired(b, c, n, alpha=0.05)
    assert -1.0 <= lo <= (c - b) / n <= hi <= 1.0, (lo, hi)


# ---------- the rejection paths (not a numbered invariant) ----------


@pytest.mark.parametrize("n", (0, -1))
def test_a_non_positive_denominator_is_refused_by_score_p_rd_score_p_rd_paired_and_interval_rd(n: int) -> None:
    """The rejection paths have no C-number. A zero
    denominator is not a wide interval and not a NaN; it is a caller error."""
    with pytest.raises(diff_mod.DiffError):
        diff_mod.score_p_rd(0, n, 0, 8)
    with pytest.raises(diff_mod.DiffError):
        diff_mod.score_p_rd(0, 8, 0, n)
    with pytest.raises(diff_mod.DiffError):
        diff_mod.score_p_rd_paired(0, 0, n)
    with pytest.raises(diff_mod.DiffError):
        diff_mod.interval_rd(0, n, 0, 8, alpha=0.05)


@pytest.mark.parametrize("alpha", (0.0, 1.0, -0.1, 1.5))
def test_an_alpha_outside_the_open_unit_interval_is_refused(alpha: float) -> None:
    """``alpha = 0`` seen from the function side: a bisection at zero runs
    to its iteration cap and returns ``(-1, 1)``, the false precision the interval exists to
    prevent. It is refused rather than returned."""
    with pytest.raises(diff_mod.DiffError):
        diff_mod.interval_rd(4, 32, 9, 32, alpha=alpha)
    with pytest.raises(diff_mod.DiffError):
        diff_mod.interval_rd_paired(4, 9, 32, alpha=alpha)


# ---------- C1: the object is whole, or it is absent ----------


def test_c1_identical_arms_reject_nothing_and_still_carry_an_interval_on_every_row(synth_root: Path) -> None:
    """C1's zero branch, on the synthetic identical pair: every cell has the same table in both
    arms, Fisher's p is 1.0 everywhere, BH rejects nothing. The interval frame is still there, one
    row per compared row, at the simultaneous level, and ``n_rejected`` is ``0``.
    """
    result = synth_diff(synth_root, "same-a", "same-b")
    rejections = sum(int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events)
    assert rejections == 0, rejections
    # PF4.42: every comparison carries an interval on the change for every compared row, flagged or
    # not; with nothing flagged its level is the simultaneous one, 1 - q / M (Bonferroni), so the
    # object is present, one row per compared row, never None.
    assert_intervals_always(result, rejections)
    assert result.n_rejected == 0
    assert result.n_interval_only == 0 and result.n_verdict_only == 0


def test_c1_lattice_under_logrank_with_the_inferred_events_also_rejects_nothing(
    lattice_inferred_logrank: Any,
) -> None:
    """The corroboration for C1's zero branch: the lattice's inferred event set is
    ``("held",)`` and log-rank rejects none of its 72 cells (``lattice.logrank(OTHER)`` flags
    none either). Kept as
    corroboration and not as the primary fixture, because it rests on a log-rank tie convention
    that is still open -- if that convention moves, this fixture stops being
    a zero and the synthetic pair above still is."""
    result = lattice_inferred_logrank
    assert result.events == (OTHER,)
    assert result.n_tests == lattice.CELLS == 72
    assert lattice.directions(lattice.logrank(OTHER)) == (0, 0)
    # PF4.42: nothing is rejected, and the interval is there for all 72 rows at the
    # simultaneous level 1 - q / 72.
    assert result.n_rejected == 0
    assert_intervals_always(result, 0)


# ---------- C2: the level, and the R it is built from ----------


def test_c2_the_level_is_one_minus_q_times_the_rejection_count_over_n_tests(lattice_pair: Any) -> None:
    """The level, recomputed rather than read back. Comparing ``interval_level`` to itself proves
    nothing, so ``R`` is counted here from the ``q`` column the BH pass wrote.

    **Association matters.** The expression is ``1.0 - ((q * R) / m)``. A mathematically equal
    regrouping such as ``1.0 - q * (R / m)`` can differ in the last ulp, and this is
    pinned exactly, so compute it the way it is written above.
    """
    result = lattice_pair
    rejections = sum(int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events)
    assert result.n_rejected == rejections
    assert result.alpha_star == result.q * rejections / result.n_tests
    assert result.interval_level == 1.0 - result.q * rejections / result.n_tests


def test_c2_the_level_follows_the_rejection_count_and_not_the_verdict_sum(
    lattice_logrank: Any,
) -> None:
    """**The discriminating fixture, and the only one.** The lattice at ``events=("tripped",)``
    under ``logrank_bh`` rejects 39 of 72 cells, but only 27 of them moved at the horizon: 12 cells
    are ``32/32`` vs ``32/32``, ``delta`` is exactly ``0``, and log-rank rejects them on the trip
    *times* rather than the horizon.

    The whole argument is that one threshold decides both the verdict and the
    interval. BH's threshold is ``q x 39 / 72``; a level built from the horizon count would use
    ``q x 27 / 72`` and reinstate exactly the mismatch the interval exists to remove. Every
    other committed configuration has the two counts equal and would let both definitions pass.
    """
    result = lattice_logrank
    rejections = sum(int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events)
    # PF4.20: tripped has no kind, so n_safer and n_worse are None on the result and the verdict sum
    # is the direction counts.
    assert all(ev.n_safer is None and ev.n_worse is None for ev in result.by_event.values())
    verdict_sum = sum(ev.n_lower + ev.n_higher for ev in result.by_event.values())
    # PF4.13: the verdict sum is the rejection count; the count that differs is
    # the rejected cells whose horizon delta moved (the horizon rule's 27).
    horizon_moved = sum(
        int(((ev.cells["q"] < result.q) & (ev.cells["delta"] != 0.0)).sum())
        for ev in result.by_event.values()
    )
    # The counts the independent log-rank reference gives (lattice.logrank, lifelines on the
    # stored times): every flagged condition, and those whose share moved by the horizon.
    reference = lattice.logrank(EVENT)
    ref_rejections = sum(r["direction"] != "unchanged" for r in reference.values())
    ref_horizon_moved = sum(r["direction"] != "unchanged" and r["delta"] != 0.0 for r in reference.values())
    assert (ref_rejections, ref_horizon_moved) == (LOGRANK_REJECTIONS, LOGRANK_HORIZON_MOVED)
    assert (rejections, verdict_sum) == (LOGRANK_REJECTIONS, LOGRANK_VERDICT_SUM)
    assert horizon_moved == LOGRANK_HORIZON_MOVED
    assert result.n_rejected == LOGRANK_REJECTIONS
    assert result.n_tests == LOGRANK_N_TESTS
    assert result.interval_level == 1.0 - result.q * LOGRANK_REJECTIONS / LOGRANK_N_TESTS


def test_c2_a_per_event_r_would_give_a_different_level_on_this_fixture(lattice_pair: Any) -> None:
    """A known trap: ``R`` counts the family, not one event. A per-event ``R`` is only caught on
    a fixture where more than one event rejects. The lattice
    over both events does: ``tripped`` and ``held`` each carry 22, so a level built from one
    event's count (22) cannot equal the family level (44)."""
    result = lattice_pair
    per_event = [int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events]
    assert per_event == [sum(PAIR_DIRECTIONS[e]) for e in result.events] == [22, 22], per_event
    assert sum(per_event) != max(per_event), per_event
    assert result.n_rejected == sum(per_event)


# ---------- C3: the frame's shape ----------


def test_c3_the_frame_has_the_interval_columns_in_order(lattice_pair: Any) -> None:
    """``INTERVAL_COLUMNS``, restated here as a constant because it is a stated
    contract, and read off the frame, so the tuple and the frame cannot
    drift apart."""
    assert tuple(diff_mod.INTERVAL_COLUMNS) == EXPECTED_INTERVAL_COLUMNS
    assert list(lattice_pair.intervals.columns) == list(EXPECTED_INTERVAL_COLUMNS)
    assert isinstance(lattice_pair.intervals, pd.DataFrame)


def test_c3_there_is_one_row_per_event_and_common_cell_and_no_duplicates(lattice_pair: Any) -> None:
    """A known trap: ``intervals`` is built over the common cells that ``cells`` covers,
    not over the raw frames. ``coverage`` had to come from the raw frames precisely because a
    wholly-errored cell is absent from the valid ones; an interval is only defined where a test
    ran. The two frames are built from different inputs for good reasons, and code that
    unifies them lands a different row count here."""
    frame = lattice_pair.intervals
    expected = {
        (event, config_hash)
        for event in lattice_pair.events
        for config_hash in lattice_pair.by_event[event].cells["config_hash"]
    }
    seen = list(zip(frame["event"], frame["config_hash"]))
    assert len(seen) == len(expected) == lattice_pair.n_tests
    assert set(seen) == expected
    assert len(set(seen)) == len(seen)


# ---------- C4 and C5 on the frame ----------


@pytest.mark.math
def test_c4_every_constructed_interval_brackets_the_cells_delta(lattice_pair: Any) -> None:
    """The frame-level form of C4: the ``delta`` an interval is *on* is the one ``cells``
    already reports at the same ``(event, config_hash)``, not one recomputed inside the interval
    builder. The interval leaves the point estimate and every other field as they are."""
    deltas = {
        (event, row.config_hash): row.delta
        for event in lattice_pair.events
        for row in lattice_pair.by_event[event].cells.itertuples(index=False)
    }
    for row in lattice_pair.intervals.itertuples(index=False):
        if row.ci_lo is None:
            continue
        delta = deltas[(row.event, row.config_hash)]
        assert row.ci_lo <= delta <= row.ci_hi, (row.event, row.config_hash, row.ci_lo, delta, row.ci_hi)


@pytest.mark.math
def test_c5_every_constructed_endpoint_is_inside_the_unit_interval(lattice_pair: Any) -> None:
    for row in lattice_pair.intervals.itertuples(index=False):
        if row.ci_lo is None:
            continue
        assert -1.0 <= row.ci_lo <= row.ci_hi <= 1.0, (row.event, row.config_hash, row.ci_lo, row.ci_hi)


# ---------- C11: the disagreement is counted, never reconciled ----------


def test_c11_the_two_counts_equal_the_counts_recomputed_from_the_frame_and_cells(
    lattice_pair: Any,
) -> None:
    """Recomputed, not read back. ``n_interval_only`` is a cell the verdict left ``unchanged``
    whose interval excludes zero -- the price of Fisher's exactness, since its p-value is
    usually larger than the score p-value on the same table. ``n_verdict_only`` is the reverse.

    Neither number changes a verdict, a ``q`` or a ``check()`` result, and neither is asserted
    to be zero anywhere: under ``logrank_bh`` disagreement runs in
    both directions and is not a bug.
    """
    result = lattice_pair
    verdicts = {
        (event, row.config_hash): row.verdict
        for event in result.events
        for row in result.by_event[event].cells.itertuples(index=False)
    }
    interval_only = 0
    verdict_only = 0
    for row in result.intervals.itertuples(index=False):
        if row.ci_lo is None:
            continue
        verdict = verdicts[(row.event, row.config_hash)]
        excludes_zero = row.ci_lo > 0.0 or row.ci_hi < 0.0
        if verdict == "unchanged" and excludes_zero:
            interval_only += 1
        if verdict != "unchanged" and not excludes_zero:
            verdict_only += 1
    assert result.n_interval_only == interval_only
    assert result.n_verdict_only == verdict_only


def test_c11_the_counts_are_recomputed_under_logrank_where_both_directions_are_expected(
    lattice_logrank: Any,
) -> None:
    """``logrank_bh`` tests the whole curve while the interval speaks about the
    horizon only. A curve that separates early and closes by ``h`` is a real rejection with an
    interval covering zero, and it is not an error. Same recomputation, on the fixture where the
    disagreement is expected rather than incidental."""
    result = lattice_logrank
    verdicts = {
        (event, row.config_hash): row.verdict
        for event in result.events
        for row in result.by_event[event].cells.itertuples(index=False)
    }
    interval_only = 0
    verdict_only = 0
    for row in result.intervals.itertuples(index=False):
        if row.ci_lo is None:
            continue
        verdict = verdicts[(row.event, row.config_hash)]
        excludes_zero = row.ci_lo > 0.0 or row.ci_hi < 0.0
        if verdict == "unchanged" and excludes_zero:
            interval_only += 1
        if verdict != "unchanged" and not excludes_zero:
            verdict_only += 1
    assert result.n_interval_only == interval_only
    assert result.n_verdict_only == verdict_only


def test_c11_the_two_counts_are_not_interchangeable_on_this_fixture(lattice_pair: Any) -> None:
    """Swapping the two counts is only caught where the two differ.
    This says the fixture separates them, so the assertions above are load-bearing. Which of the
    two is larger is not asserted: the expected direction is known, and a run that
    contradicts it is a finding about the two tests, not a test failure."""
    assert lattice_pair.n_interval_only != lattice_pair.n_verdict_only, (
        lattice_pair.n_interval_only,
        lattice_pair.n_verdict_only,
    )


# ---------- C12: the basis follows the method, never the provenance ----------


def test_c12_the_same_frames_give_the_same_interval_pairable_or_not(synth_root: Path) -> None:
    """The basis follows the method, and the trap that rule is there for. ``moved-b`` and ``moved-b-unpaired`` hold
    identical episodes and differ only in ``run_salt``, so the two diffs below see the same
    tables and differ only in ``seed_identity_match``.

    Two runs that happen to share a run salt must not get a different number from two that do
    not, or the statistic becomes a property of run provenance rather than of the request, and a
    reader could not tell which was run without going back to the manifests.
    """
    paired = synth_diff(synth_root, "moved-a", "moved-b", "fisher_bh")
    unpaired = synth_diff(synth_root, "moved-a", "moved-b-unpaired", "fisher_bh")
    assert paired.seed_identity_match is True and unpaired.seed_identity_match is False
    left = paired.intervals.sort_values(["event", "config_hash"]).reset_index(drop=True)
    right = unpaired.intervals.sort_values(["event", "config_hash"]).reset_index(drop=True)
    assert list(left["basis"]) == list(right["basis"]) == ["score_rd"] * len(left)
    assert list(left["ci_lo"]) == list(right["ci_lo"])
    assert list(left["ci_hi"]) == list(right["ci_hi"])


def test_c12_the_paired_method_takes_the_paired_basis_on_the_very_same_frames(
    synth_root: Path,
) -> None:
    """The positive half. Same pairable frames, and only ``method`` changes: ``fisher_bh`` takes
    ``score_rd`` and ``mcnemar_bh`` takes ``score_rd_paired``. ``mcnemar_bh`` already refuses an
    unpairable pair with ``NotPairable`` before any cell is tested, so ``score_rd_paired`` is
    never reached without pairing."""
    fisher = synth_diff(synth_root, "moved-a", "moved-b", "fisher_bh")
    mcnemar = synth_diff(synth_root, "moved-a", "moved-b", "mcnemar_bh")
    assert fisher.seed_identity_match is True and mcnemar.seed_identity_match is True
    assert set(fisher.intervals["basis"]) == {"score_rd"}
    assert set(mcnemar.intervals["basis"]) == {"score_rd_paired"}


def test_c12_logrank_takes_the_unpaired_basis(lattice_logrank: Any) -> None:
    """The log-rank row. ``logrank_bh`` runs on the pairable lattice pair and
    still takes ``score_rd``: the basis follows the requested method, and log-rank is not a
    paired method however the runs were produced."""
    assert set(lattice_logrank.intervals["basis"]) == {"score_rd"}


# ---------- C13: the censoring contract, and what it cannot pin ----------


def test_c13_the_endpoints_are_none_exactly_when_the_basis_is_censored(
    lattice_pair: Any, lattice_logrank: Any, synth_root: Path
) -> None:
    """The frame's contract, over every fixture that produces a frame.

    **This does not pin the censored branch, and saying so is the point.** The censoring guard was
    written against ``_truncate_raw``, which censors at the horizon -- and the horizon is ``>=``
    every retained event time, so the Aalen-Johansen estimate there reduces to the naive
    proportion and the guard cannot fire. Five shapes were measured (late
    truncation, two event times, a tie exactly at the horizon, three competing kinds, and 19
    distinct event times) and every one deviates by ``0.0``. There is no input to ``multi_diff``
    that produces ``basis == "censored"``, so there is no fixture for the branch.

    What this *does* pin is the contract in both directions plus the negative: code whose
    guard is inverted, or whose tolerance points the wrong way, marks a clean cell ``censored``
    and fails here. The guard stays in the code as a forward guard -- it is what stops a later
    change to truncation or to the estimator from silently putting a binomial interval on
    censored data.
    """
    for result in (lattice_pair, lattice_logrank, synth_diff(synth_root, "moved-a", "moved-b")):
        for row in result.intervals.itertuples(index=False):
            assert (row.ci_lo is None) == (row.ci_hi is None) == (row.basis == "censored"), (
                row.event,
                row.config_hash,
                row.ci_lo,
                row.ci_hi,
                row.basis,
            )


def test_c13_no_cell_that_satisfies_the_censoring_guard_is_marked_censored(lattice_pair: Any) -> None:
    """The negative, on the fixture where the guard's own input is known: every lattice cell has
    ``|rate_x - events_x / n_x| == 0.0`` exactly, on both arms. So no row
    of this frame may carry ``basis == "censored"``, and one that does means the guard is
    inverted or reading the wrong quantity."""
    rates = {
        (event, row.config_hash): (
            abs(row.rate_a - row.events_a / row.n_a),
            abs(row.rate_b - row.events_b / row.n_b),
        )
        for event in lattice_pair.events
        for row in lattice_pair.by_event[event].cells.itertuples(index=False)
    }
    assert max(max(pair) for pair in rates.values()) <= CIF_TOLERANCE
    for row in lattice_pair.intervals.itertuples(index=False):
        assert row.basis != "censored", (row.event, row.config_hash)


def test_c13b_the_rejection_count_covers_every_cell_whatever_its_basis(lattice_logrank: Any) -> None:
    """The guard decides whether an *interval* is built, never whether a hypothesis was
    rejected. ``n_rejected`` is counted over the whole ``cells`` frame with no filter on basis,
    so code that counts only the cells it managed to give an interval to lands a smaller
    ``R`` and a wider level. On these fixtures no cell is filtered, so this pins the shape of
    the count rather than a difference; the censored half is unpinnable for the reason C13
    gives."""
    result = lattice_logrank
    total_cells = sum(len(result.by_event[e].cells) for e in result.events)
    assert total_cells == result.n_tests == len(result.intervals)
    assert result.n_rejected == sum(
        int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events
    )


# ---------- C17: the basis vocabulary ----------


def test_c17_interval_bases_is_exactly_the_three_names_the_spec_states() -> None:
    """Written once in ``diff.py``, the way ``_CAUSES`` is."""
    assert tuple(diff_mod.INTERVAL_BASES) == EXPECTED_INTERVAL_BASES


def test_c17_every_basis_on_every_frame_is_drawn_from_that_tuple(
    lattice_pair: Any, lattice_logrank: Any, synth_root: Path
) -> None:
    for result in (
        lattice_pair,
        lattice_logrank,
        synth_diff(synth_root, "moved-a", "moved-b", "fisher_bh"),
        synth_diff(synth_root, "moved-a", "moved-b", "mcnemar_bh"),
    ):
        assert set(result.intervals["basis"]) <= set(EXPECTED_INTERVAL_BASES), set(
            result.intervals["basis"]
        )


# ---------- C14: the interval leaves the existing output alone ----------


def test_c14_the_lattice_markdown_carries_the_result(lattice_pair: Any) -> None:
    """``to_markdown()`` opens with the headline, carries the trade line and the parameter line,
    gains no interval block, and holds one table per event whose rows are that event's cells with
    their numbers (``assert_markdown_carries_the_result``)."""
    # PF4.3, PF4.15, PF4.20: the markdown is read as facts, not hashed.
    assert_markdown_carries_the_result(lattice_pair)


def test_c14_the_lattice_logrank_markdown_carries_the_result_too(lattice_logrank: Any) -> None:
    # PF4.3, PF4.13, PF4.15, PF4.20: the markdown is read as facts, not hashed.
    assert_markdown_carries_the_result(lattice_logrank)


def _close(printed: str, value: float) -> bool:
    """A number the markdown prints (``:g``, six significant digits) against the frame's value."""
    if pd.isna(value):
        return printed == "nan"
    return abs(float(printed) - float(value)) <= 1e-5 * max(1.0, abs(float(value)))


def assert_markdown_carries_the_result(result: Any) -> None:
    """C14's markdown, as facts. ``to_markdown()`` opens with ``headline()``,
    carries the trade line and the parameter line, gains no interval block, and holds one table
    per event whose rows are that event's cells in order, each with the frame's counts, delta, p, q
    and limit (or the cell's limit note), and the cell's direction word as its verdict: no event
    here has a kind (PF4.20)."""
    md = result.to_markdown()
    lines = md.splitlines()
    head = result.headline().splitlines()
    assert lines[: len(head)] == head
    trade = result.trade_line()
    assert trade is None or trade in lines
    assert "intervals:" not in md and "alpha*" not in md
    (params,) = [line for line in lines if line.startswith("method=")]
    assert params.startswith(f"method={result.method}") and f"n_tests={result.n_tests}," in params
    for event in result.events:
        ev = result.by_event[event]
        assert ev.kind is None
        header = f"## {event}: n_lower={ev.n_lower}, n_higher={ev.n_higher}, n_unchanged={ev.n_unchanged},"
        (start,) = [i for i, line in enumerate(lines) if line.startswith(header)]
        top = next(i for i in range(start, len(lines)) if lines[i].startswith("| config_hash |"))
        columns = [c.strip() for c in lines[top].strip("|").split("|")]
        rows = []
        for line in lines[top + 2 :]:
            if not line.startswith("|"):
                break
            rows.append(dict(zip(columns, (c.strip() for c in line.strip("|").split("|")), strict=True)))
        cells = list(ev.cells.itertuples(index=False))
        assert [r["config_hash"] for r in rows] == [c.config_hash for c in cells], event
        for r, c in zip(rows, cells, strict=True):
            for key in ("n_a", "n_b", "events_a", "events_b"):
                assert int(r[key]) == int(getattr(c, key)), (event, c.config_hash, key)
            for key in ("delta", "p", "q"):
                assert _close(r[key], getattr(c, key)), (event, c.config_hash, key, r[key])
            assert r["verdict"] == c.direction, (event, c.config_hash)
            # The limit column may carry a mark after its value (a log-rank cell read on the timing
            # is marked there), so the value is read from the column's start.
            # PF4.22, PF4.27, PF4.32: the column carries both directions, each its
            # limit to three decimals (a change size above 0) or its note in words.
            # When the two ways agree to three decimals the column prints the one number.
            if not pd.isna(c.mde_rise) and not pd.isna(c.mde_fall) and abs(c.mde_rise - c.mde_fall) < 0.001:
                assert _close(r["mde"].split()[0], round(float(c.mde_rise), 3)), (event, c.config_hash, r["mde"])
                assert float(r["mde"].split()[0]) > 0, (event, c.config_hash, r["mde"])
                parts = []
            else:
                parts = r["mde"].split(", ")
                assert len(parts) == 2, (event, c.config_hash, r["mde"])
            for way, part in zip(("rise", "fall")[: len(parts)], parts, strict=True):
                value, note = getattr(c, f"mde_{way}"), getattr(c, f"mde_{way}_note")
                if value is None or pd.isna(value):
                    assert part.startswith(f"{way}: {note}"), (event, c.config_hash, way, r["mde"])
                else:
                    printed = part.split()[1]
                    assert part.startswith(f"{way} ") and abs(float(printed) - float(value)) <= 5e-4 + 1e-12, (
                        event, c.config_hash, way, r["mde"])
                    assert float(value) > 0 and float(printed) > 0, (event, c.config_hash, way, value, r["mde"])
            # PF4.42: the table prints the interval on the change for every row,
            # labelled with its level as a percentage and its method.
            (change,) = [k for k in r if k.startswith("change [")]
            assert change == f"change [{format_level(c.ci_level)}, Miettinen-Nurminen]", (change, c.ci_level)
            assert r[change] == f"[{c.ci_lo:.3f}, {c.ci_hi:.3f}]", (event, c.config_hash, r[change])


def test_c14_the_headline_the_trade_line_and_check_are_unchanged(
    lattice_pair: Any, lattice_logrank: Any
) -> None:
    """``headline()``, ``trade_line()`` and ``check()`` gain nothing from S24. The literals are
    the ones the tree produces. The headline's last token is the requested method's pairing --
    ``unpaired`` under ``fisher_bh`` and ``logrank_bh`` however the runs were produced."""
    # The headline's counts are the ones the independent Fisher reference gives each event.
    assert {e: lattice.directions(lattice.fisher(e)) for e in (EVENT, OTHER)} == PAIR_DIRECTIONS
    assert {e: (lattice_pair.by_event[e].n_lower, lattice_pair.by_event[e].n_higher) for e in lattice_pair.events} == PAIR_DIRECTIONS
    assert lattice_pair.headline() == PAIR_HEADLINE
    # PF4.20: the trade line is unchanged (its words are fell and rose), and check()'s default gate
    # on "worse" is refused (a DiffError) on the kindless pair rather than failed; check("any")
    # gates over the rows that count.
    assert lattice_pair.trade_line() == PAIR_TRADE_LINE
    with pytest.raises(diff_mod.DiffError):
        lattice_pair.check()
    assert lattice_pair.check("any") is False
    assert lattice_logrank.headline() == LOGRANK_HEADLINE
    assert lattice_logrank.trade_line() is None
    # PF4.13: 12 cells rose under log-rank (lattice.logrank: the load 100 conditions).
    # PF4.20: the rise is counted in direction words (n_higher), n_worse is None, check() is refused
    # and check("higher") fails.
    tripped = lattice_logrank.by_event[EVENT]
    assert lattice.directions(lattice.logrank(EVENT)) == LOGRANK_DIRECTIONS
    assert (tripped.n_lower, tripped.n_higher, tripped.n_worse, tripped.n_safer) == (*LOGRANK_DIRECTIONS, None, None)
    with pytest.raises(diff_mod.DiffError):
        lattice_logrank.check()
    assert lattice_logrank.check("any") is False and lattice_logrank.check("higher") is False


def test_c14_the_cells_columns_are_unchanged(lattice_pair: Any) -> None:
    """``CELLS_COLUMNS``, exactly and in order, on every event's ``cells``. The interval frame
    (``intervals``) is its own frame; the cell rows carry the interval on the change as well
    (PF4.42)."""
    # PF4.13, PF4.14, PF4.15: four per-cell fields (direction, the log-rank timing note, the
    # matched-pair count, the limit note).
    # PF4.34, PF4.27, PF4.32, PF4.41, PF4.42, PF4.47: Holm's adjusted p and whether the row counts,
    # the limit keys, the competing outcomes, and the interval on the change (ci_lo, ci_hi, its
    # level and method), in this order.
    assert CELLS_COLUMNS == (
        "config_hash", "config", "n_a", "n_b", "events_a", "events_b",
        "rate_a", "rate_b", "delta", "stat", "p", "q", "verdict", "mde",
        "direction", "direction_note", "pairs", "n01", "n10", "mde_note",
        "q_holm", "holm", "mde_rise", "mde_fall", "mde_rise_note", "mde_fall_note", "mde_test",
        "mde_basis", "mde_level", "mde_family", "mde_power", "mde_anchor", "mde_hr", "p_min",
        "flaggable", "mde_moves_with", "mde_rise_verdict", "mde_fall_verdict", "competing_shift",
        "ci_lo", "ci_hi", "ci_level", "ci_method",
    )
    for event in lattice_pair.events:
        assert list(lattice_pair.by_event[event].cells.columns) == list(CELLS_COLUMNS)


# ---------- C15: the BH family does not move ----------


def test_c15_the_family_its_q_and_its_pairing_are_unchanged(lattice_pair: Any) -> None:
    """S24 adds an interval around a number that is already there. It does not retest, rescope
    or reweight anything: ``n_tests`` is the same 144, ``q`` the same 0.05, ``seed_identity_match`` the same
    ``True``, and ``coverage`` the same frame S21 built."""
    assert lattice_pair.n_tests == 2 * lattice.CELLS == 144
    assert lattice_pair.q == 0.05
    assert lattice_pair.seed_identity_match is True
    assert lattice_pair.truncated == 0
    assert len(lattice_pair.coverage) == lattice.CELLS == 72
    # The coverage, as facts: one row per condition of the lattice design,
    # every row of both runs counted and holding an outcome, every condition comparable.
    assert_coverage_is_the_design(lattice_pair)


def test_c15_every_q_value_and_every_delta_on_cells_is_unchanged(
    lattice_pair: Any, lattice_logrank: Any
) -> None:
    """The per-cell BH output itself, at full float precision. Code that reorders the rows
    fed to ``bh``, or slips the interval construction in before the BH pass rather than after
    it, fails one of these checks. The order is exact: after the BH pass and
    after ``by_event``, because the level cannot be known before ``R``.

    The checks: the pair's q column is BH over
    its p column, and both are the Fisher reference's exactly (``lattice.fisher``, one family over
    both events); its delta column is the naive difference of the lattice design's counts; the log-rank q
    column is BH over its p column, and each p and q is the independent log-rank reference's
    (``lattice.logrank``, lifelines on the stored times) to 1e-12 relative."""
    fisher = {e: lattice.fisher(e) for e in lattice_pair.events}
    assert_q_column_is_bh_over_its_p_column(lattice_pair, fisher, (EVENT, OTHER))
    assert_delta_column_is_the_naive_difference(lattice_pair, (EVENT, OTHER))
    assert_logrank_column_is_the_reference(lattice_logrank)


def test_c15_to_json_gains_the_six_keys_and_keeps_every_key_it_had(lattice_pair: Any) -> None:
    """Additive, like ``coverage``: the six interval keys are present beside every other key
    ``to_json()`` emits."""
    payload = lattice_pair.to_json()
    for key in (
        "method", "seed_identity_match", "unpaired_analysis", "q", "t_unit", "horizon", "n_tests", "n_not_comparable",
        "dropped_a", "dropped_b", "truncated", "inferred", "non_event",
        "events", "by_event", "trades", "coverage", "headline", "trade_line",
    ):
        assert key in payload, key
    for key in (
        "intervals", "interval_level", "alpha_star", "n_rejected",
        "n_interval_only", "n_verdict_only",
    ):
        assert key in payload, key


def test_c15_a_hand_built_result_still_constructs_without_any_new_field(lattice_pair: Any) -> None:
    """A known trap, the same one ``coverage`` has. M7's two frozen test files build
    ``MultiDiffResult`` by hand from keywords; an undefaulted interval field would break every one
    of them. Rebuilt here from the fields other than S24's, and the result must carry the
    absent-interval state rather than a half-populated one."""
    before = (
        "events", "by_event", "method", "seed_identity_match", "unpaired_analysis", "q", "t_unit", "horizon", "n_tests",
        "n_not_comparable", "dropped_a", "dropped_b", "truncated", "trades", "inferred",
        "non_event",
    )
    bare = diff_mod.MultiDiffResult(**{name: getattr(lattice_pair, name) for name in before})
    assert bare.intervals is None
    assert bare.interval_level is None and bare.alpha_star is None
    assert bare.n_rejected == 0 and bare.n_interval_only == 0 and bare.n_verdict_only == 0


# ---------- C18: the CLI block ----------


def test_c18_the_diff_output_prints_the_alpha_star_arithmetic_and_names_the_family(
    synth_root: Path,
) -> None:
    """The interval line, through ``main()`` with ``StringIO`` streams. Both streams and the exit code.

    **The family is named.** A nested family would carry a different level, so a
    bare ``alpha*`` on the page would be the one number a reader could not attribute. The level,
    ``R`` and ``m`` are captured from the line and checked against the fields rather than pinned
    as formatted floats: a four-decimal rendering prints the motivating
    case (1200 cells, one rejection) as ``0.0000``, and pinning that format would pin a
    defect.
    """
    result = synth_diff(synth_root, "moved-a", "moved-b", "fisher_bh")
    # PF3: the synthetic pair shares a salt, so the default is the paired test (basis
    # score_rd_paired); these fields are the unpaired test's, named.
    code, out, err = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--method", "fisher_bh"])
    assert code == 0, (out, err)
    # A shared salt adds one note line on stderr; nothing else is there.
    assert without_notes(err) == "", err
    match = INTERVAL_LINE.search(out)
    assert match is not None, out
    level, alpha_star, rejections, tests, basis = match.groups()
    assert int(rejections) == result.n_rejected
    assert int(tests) == result.n_tests
    assert abs(float(level) / 100.0 - result.interval_level) <= 1e-9
    assert abs(float(alpha_star) - result.alpha_star) <= 1e-9
    assert basis == "score_rd"


def test_c18_the_diff_output_prints_both_disagreement_counts(lattice_pair: Any) -> None:
    """The two lines under the header, on the lattice over both events under Fisher, where the two
    counts differ (C11). The counts are fields; the CLI prints them and asserts nothing about their
    direction."""
    result = lattice_pair
    assert result.n_interval_only != result.n_verdict_only, (result.n_interval_only, result.n_verdict_only)
    code, out, _ = run_cli(
        ["--store", str(LATTICE_ROOT), "diff", RUN_A, RUN_B, "--event", EVENT, "--event", OTHER, "--method", "fisher_bh"]
    )
    assert code == 0, out
    assert f"interval excludes zero, verdict unchanged: {result.n_interval_only} cells" in out
    assert f"verdict significant, interval covers zero: {result.n_verdict_only} cells" in out


def test_c18_the_diff_output_prints_the_no_interval_line_when_nothing_was_rejected(
    synth_root: Path,
) -> None:
    """The branch where nothing was rejected. The interval line is printed there too, at the
    simultaneous level 1 - q / M, and no line says no interval was computed."""
    code, out, err = run_cli(["--store", str(synth_root), "diff", "same-a", "same-b", "--event", "fail"])
    assert code == 0, (out, err)
    # A shared salt adds one note line on stderr; nothing else is there.
    assert without_notes(err) == "", err
    # PF4.42: intervals always, so there is no no-interval line; the interval line is printed at the
    # simultaneous level 1 - q / M (Bonferroni), and the arithmetic it prints is true: alpha* is q
    # times max(R, 1) over M.
    result = synth_diff(synth_root, "same-a", "same-b", "mcnemar_bh")
    assert NO_INTERVAL_LINE not in out, out
    match = INTERVAL_LINE.search(out)
    assert match is not None, out
    level, alpha_star, rejections, tests, _ = match.groups()
    assert result.n_rejected == 0 and int(tests) == result.n_tests
    assert abs(float(level) / 100.0 - (1.0 - result.q / result.n_tests)) <= 5e-4, level
    assert abs(float(alpha_star) - result.q / result.n_tests) <= 5e-4, alpha_star
    assert int(rejections) == max(result.n_rejected, 1), match.group(0)
    assert abs(float(alpha_star) - result.q * int(rejections) / int(tests)) <= 5e-4, match.group(0)


def test_c18_the_interval_block_follows_the_coverage_block(synth_root: Path) -> None:
    """After ``_coverage_block``. The order is the reading order -- what was
    measured, then what the measurement bounds."""
    code, out, _ = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail"])
    assert code == 0, out
    assert "## coverage" in out, out
    assert out.index("## coverage") < out.index("intervals: "), out


def test_c18_the_json_format_carries_the_fields_and_prints_no_block(synth_root: Path) -> None:
    """``--format json`` renders ``to_json()`` and nothing else. The interval block is text
    output; the JSON payload carries the same facts as fields, which is what a consumer reads."""
    # --json replaces --format json.
    code, out, _ = run_cli(
        ["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--json"]
    )
    assert code == 0, out
    assert "intervals: " not in out
    assert '"interval_level"' in out and '"n_rejected"' in out and '"alpha_star"' in out
