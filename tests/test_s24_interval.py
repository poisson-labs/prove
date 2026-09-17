"""S24 -- the interval on the delta: the oracle for C1-C19.

Written from "Proofload -- Spec S24 Interval on the Delta" section 4 as amended by S24.1.
Session B builds ``src/proofload/diff.py`` and ``src/proofload/cli.py`` against this file and
does not edit it.

**The S24 names are reached through the module** -- ``diff.score_p_rd``, not ``score_p_rd`` --
for the reason the S23 oracle gives: before Session B builds them, a ``from ... import`` of a
name that does not exist is a *collection* error, and pytest abandons the whole run on one.
Qualified, this file collects, its own tests fail, and every other test in the repo still
reports. The names that already exist (``multi_diff``, ``CELLS_COLUMNS``, ``Store``) are
imported normally.

**What the packet is.** Every number the tool reports about a cell says whether something moved
or what could not have been seen. Nothing says how big the thing that moved is. This adds an
interval on ``delta`` at a level that pays for the fact that the cell was chosen out of a grid,
and counts the interval's disagreement with the verdict rather than reconciling it.

Six findings from step zero, all measured on disk, all now carried by the spec as amendment
S24.1. They are restated here because they are why several tests below look the way they do.

1. **``R`` is the BH rejection count, not the verdict sum.** On Go1 with ``events=("fell",)``
   under ``logrank_bh`` the two are **196 and 88**: 108 cells are ``32/32`` vs ``32/32``, every
   episode fell in both arms, ``delta`` is exactly ``0`` so ``multi_diff`` labels them
   ``unchanged``, and log-rank rejects them on the fall *times*. That configuration is the only
   committed fixture on which the two definitions differ, so C2 and C19 are written on it and
   nowhere else. On every other committed configuration both definitions pass.
2. **The family is the flat BH family ``multi_diff`` runs**, and C1/C2/C18 say so. Rollout Plan
   Phase 4's nested family (leaves within a rejected Level 2 group) is a separate object with
   its own level; nothing here is designed for it.
3. **C4/C5/C6/C7 were mutually contradictory at the parameter-space boundary.** At ``0/32`` vs
   ``32/32`` the point estimate is ``1.0``, so C4 forces ``ci_hi >= 1.0``, C5 forces
   ``ci_hi <= 1.0``, and C7 then makes ``score_p_rd(..., delta=1.0)`` equal ``1.0`` rather than
   ``alpha``. C6 is scoped to interior endpoints and **C6b pins the boundary positively** --
   an exemption with nothing asserting the exempted behaviour is a hole. 245 of Go1's 400 cells
   (61%) sit on a boundary.
4. **Go1 is 0 safer / 60 worse under Fisher and 0 safer / 55 worse under McNemar**, not what
   spec section 6 said before S24.1.
5. **A committed ``R == 0`` fixture exists**: Go1 under ``logrank_bh`` with the inferred event
   set. C1's primary fixture is still the synthetic identical-arms pair, because the Go1 route
   rests on a log-rank tie convention the Rollout Plan still lists as open; Go1 corroborates.
6. **ADR-050's guard cannot fire.** ``_truncate_raw`` censors at the horizon, which is ``>=``
   every retained event time, and the estimator reduces to the naive proportion when no
   censoring precedes an event. Five constructed shapes were measured -- late truncation, two
   event times, a tie exactly at the horizon, three competing kinds, and 19 distinct event times
   -- and every one deviates by ``0.0``. ``basis == "censored"`` is unreachable from any input
   to ``multi_diff``, so **C13 pins the contract and the negative, not the branch**, and the
   handoff's "the censoring guard checks arm A only" mutant is uncatchable. Said here rather
   than left for someone to discover from a green suite.

**Conventions this oracle fixes where the spec is silent. Session B builds to these.**

- **``n_rejected`` and ``alpha_star`` are fields** (spec section 2 as amended). Section 3.4
  requires the CLI to print ``q x R / m``; ``R`` was a field nowhere, and recovering it as
  ``alpha_star * m / q`` is a float round-trip to an integer. Six defaulted fields, not four.
  Every one defaulted, so M7's two hand-built ``MultiDiffResult`` sites survive untouched.
- **``alpha_star`` is ``None`` when nothing was rejected**, not ``0.0``. Section 0.3's posture
  is that a result with nothing behind it must not claim a number, and a printed ``alpha* =
  0.0`` is the same false precision as a printed ``(-1, 1)``. ``n_rejected`` stays ``0``: that
  is a count, not a claim.
- **C18 pins the arithmetic's components, not the float formatting.** Section 3.4's example
  renders ``alpha*`` at four decimals, which prints ``0.0000`` for section 0.2's own motivating
  case (1200 cells, one rejection, ``alpha* = 4.2e-05``). Pinning that format would freeze a
  defect. The regex below captures the level, ``R`` and ``m`` and checks them against the
  fields; the family name and the basis are pinned as literals.
- **An endpoint is "interior" iff ``-1.0 < endpoint < 1.0``** -- observable from the return
  value alone, no reach into how it was found.
- **Render the percentage with the ``%`` format spec, not by multiplying.** C19 forbids any
  arithmetic on the six interval fields inside ``cli.py``, and ``interval_level * 100`` is
  arithmetic: it is indistinguishable, to a rule that has to stay robust, from the
  ``1 - interval_level`` and ``alpha_star * m / q`` recoveries the rule exists to stop.
  ``f"{multi.interval_level:.4%}"`` renders ``0.9925`` as ``99.2500%`` with no ``BinOp`` at
  all. The shadow shim tripped C19 on exactly this and the shim was corrected, not the test.
  Printing ``alpha_star`` with ``:g`` rather than ``:.4f`` also avoids section 3.4's own
  rounding defect, and the regex above accepts either.

**One collision this oracle does not resolve, because it is not this session's to resolve.**
``tests/test_s21_errors.py::test_e12_to_markdown_is_unchanged_and_diff_text_appends_the_coverage_block``
asserts ``r.out == md + "\n" + block`` -- the *entire* stdout of the ``diff`` verb, by exact
equality. Spec section 3.4 puts the interval block in that stream, so **E12 fails the moment
the block is added**, whatever it says. The S24 handoff's change table records "frozen tests:
none touched", and that is wrong: this one is. Measured by running the whole suite against the
shadow shim -- 1487 passed, and E12 the single failure. It is the only such site; the other
exact-equality assertion on this stream, ``test_m4_read.py:619``, compares two runs of the same
command and is unaffected. Session B cannot edit E12, so the placement or E12 has to give, and
that is a call for whoever owns the S21 packet.

**Named non-observables.** The constrained MLE is not asserted anywhere: spec section 0.1
deliberately leaves the route open (a Farrington-Manning cubic or a one-dimensional
maximisation), and C7, C8 and C10 pin the object by its properties instead. Nothing here reads
the bisector, its iteration cap, or its tolerance.
"""

from __future__ import annotations

import ast
import hashlib
import re
import warnings
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import proofload
from proofload import cli
from proofload import diff as diff_mod
from proofload.diff import CELLS_COLUMNS, multi_diff
from proofload.episode import Episode
from proofload.report import ReportSpec, build_multi_report
from proofload.store import EpisodeRecord, RunManifest, Store

PACKAGE = Path(proofload.__file__).resolve().parent
REPO = PACKAGE.parents[1]
GO1_ROOT = REPO / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"

#: Spec section 2 as amended. Stated in the spec, so constants here (standing rule 1).
EXPECTED_INTERVAL_COLUMNS = ("event", "config_hash", "config", "ci_lo", "ci_hi", "basis")
EXPECTED_INTERVAL_BASES = ("score_rd", "score_rd_paired", "censored")

#: Section 0.4's guard, per arm. The numeric form, not the structural one: it holds whatever a
#: later change does to the estimator.
CIF_TOLERANCE = 1e-12

#: Alphas the unit tests run at: the nominal one, and the two alpha* values Go1 actually
#: produces (fisher over both events, and the logrank-on-fell family).
ALPHAS = (0.05, 0.0245, 0.0075, 0.001)

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

#: Section 3.4's no-interval line, verbatim.
NO_INTERVAL_LINE = "intervals: none (nothing significant; the MDE lines above are the honest bound)"

#: C18's first line. The level, alpha*, R and m are captured and checked against the fields
#: rather than pinned as formatted floats -- see the docstring.
INTERVAL_LINE = re.compile(
    r"^intervals: ([0-9.]+)% \(alpha\* = ([0-9.eE+-]+) = q x (\d+) / (\d+) over the flat BH family\), "
    r"basis (\w+)$",
    re.MULTILINE,
)

#: C14. Minted on the bare tree at a597d9a (2026-09-07), before the build exists: a hash, never
#: a diff of two renders. ``PAIR`` is ``multi_diff(go1-v0, go1-v1, events=("fell", "survived"),
#: method="fisher_bh")``; ``FELL_LOGRANK`` is the same pair at ``events=("fell",)`` and
#: ``method="logrank_bh"``.
PAIR_MARKDOWN_SHA256 = "c4307336f43850388686742ce04c65acba664e1c504b079f1eea76b7062c37f5"
PAIR_HEADLINE = (
    "survived: 0 safer, 60 worse · fell: 60 safer, 0 worse\n"
    "(aalen_johansen + fisher_bh, BH q<0.05 over 800 tests, unpaired)"
)
PAIR_TRADE_LINE = (
    "Trade: fell fell in 60 cells where survived rose. "
    "The patch moved failures, it did not remove them."
)
PAIR_QCOLUMN_SHA256 = "1e8e75a1679a92ba553d45d4b4fcdfd946d0e77939fec7ae7c214270e77719f9"
PAIR_DELTA_SHA256 = "0b46042d58b4ce9d8ff7cadfef1a0e20637d66e43de58c08f710e2021d3b35bf"
COVERAGE_SHA256 = "e02aae9ac0d0f902d5fdb9d36340e3a7a72c1a7d6d86b0e5a75fffda95dee5fa"

FELL_LOGRANK_MARKDOWN_SHA256 = "6ffbb64ecbc8e6ead6aa415aaba0a10de49a5fe99ee7e8a81aba4bd60579991f"
FELL_LOGRANK_HEADLINE = (
    "fell: 88 safer, 0 worse\n"
    "(aalen_johansen + logrank_bh (cause-specific), BH q<0.05 over 400 tests, unpaired)"
)
FELL_LOGRANK_QCOLUMN_SHA256 = "175f731751711047063b840dacb61c3a9e8ac86ccd937d0043d4986283821e53"

#: C14, second half. The three digests S21's E14 already pins, restated rather than imported so
#: two frozen oracles do not couple. Minted on the bare tree at b10a146 by
#: ``report go1-v0 go1-v1 --event fell --x mu --y push_pct_bw``.
E14_ARGV = ("report", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw")
E14_SHA256 = {
    "report.md": "7c67c2178f82f97ed3cad5724cb3ba0241d8a1f6b32910bea9fa2e1a6b4884fe",
    "heatmap.svg": "2e0dfe4e27314d30f1514104a60d0a566a75f4c032fa1b25f92b779f70c324de",
    "receipt.html": "bd101bd0a111c3df36272614b34574a6a1b9b088bc7ff5c234f82788f8b78261",
}

#: Step zero, measurement 2, restated as a constant so C2's fixture cannot be swapped for one
#: that does not discriminate. Go1, ``events=("fell",)``, ``logrank_bh``.
FELL_LOGRANK_N_TESTS = 400
FELL_LOGRANK_REJECTIONS = 196
FELL_LOGRANK_VERDICT_SUM = 88


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


def go1_diff(events: tuple[str, ...] | None, method: str) -> Any:
    """``multi_diff`` on the committed Go1 pair; ``events=None`` takes the inferred set. The
    unpaired-analysis warning is expected on every non-McNemar call here (both manifests carry
    the same run_salt by construction) and is not what any test below is about."""
    store = Store(GO1_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return multi_diff(
            store.read(GO1_A),
            store.read(GO1_B),
            events=None if events is None else list(events),
            method=method,
            manifest_a=store.manifest(GO1_A),
            manifest_b=store.manifest(GO1_B),
        )


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_column(result: Any, column: str) -> str:
    """The per-event column, joined at full float precision. Used only for C14/C15, where the
    fact asserted is 'this did not move'."""
    return sha256_of_text(
        "|".join(
            f"{e}:" + ",".join(f"{v:.17g}" for v in result.by_event[e].cells[column])
            for e in result.events
        )
    )


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def enclosing_functions(tree: ast.Module) -> dict[ast.AST, str]:
    """Every node mapped to the name of the ``def`` it sits inside, for C16."""
    out: dict[ast.AST, str] = {}

    def walk(node: ast.AST, name: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else name
            if inner is not None:
                out[child] = inner
            walk(child, inner)

    walk(tree, None)
    return out


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def go1_pair() -> Any:
    """Go1 over both events under Fisher. R = 120 over 800 tests, and the rejection count and
    the verdict sum agree here -- which is exactly why C2 cannot be written on it alone."""
    return go1_diff(("fell", "survived"), "fisher_bh")


@pytest.fixture(scope="module")
def go1_fell_logrank() -> Any:
    """The one committed configuration on which the BH rejection count (196) and
    ``n_safer + n_worse`` (88) differ. C2's and C19's discriminating fixture."""
    return go1_diff(("fell",), "logrank_bh")


@pytest.fixture(scope="module")
def go1_inferred_logrank() -> Any:
    """Go1 with the inferred event set under log-rank: R == 0 over 400 tests. C1's
    corroborating zero fixture."""
    return go1_diff(None, "logrank_bh")


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


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(argv, stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


# ---------- C7: the analytic point, the one place the constrained MLE is known ----------


@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
def test_c7_the_unpaired_statistic_is_one_at_the_point_estimate(
    events_a: int, n_a: int, events_b: int, n_b: int
) -> None:
    """Spec section 0.1 leaves *how* the constrained MLE is found open, deliberately, because a
    mistranscribed Farrington-Manning cubic is a silent statistical bug no reviewer catches by
    reading. This is the guard on that openness: at ``delta == p_b_hat - p_a_hat`` the
    constrained MLEs coincide with the unconstrained ones, the score is exactly zero and the
    two-sided p-value is exactly 1. Build to this first; while it is red nothing downstream
    means anything (section 8, trap 1).
    """
    delta = events_b / n_b - events_a / n_a
    assert abs(diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=delta) - 1.0) <= 1e-12


@pytest.mark.parametrize("b,c,n", PAIRED_TABLES)
def test_c7_the_paired_statistic_is_one_at_the_point_estimate(b: int, c: int, n: int) -> None:
    """Tango's paired twin of the clause above. The point estimate for ``n`` pairs with ``b``
    discordant one way and ``c`` the other is ``(c - b) / n`` (spec section 2)."""
    assert abs(diff_mod.score_p_rd_paired(b, c, n, delta=(c - b) / n) - 1.0) <= 1e-12


@settings(deadline=None, max_examples=120)
@given(
    n_a=st.integers(min_value=1, max_value=200),
    n_b=st.integers(min_value=1, max_value=200),
    fa=st.floats(min_value=0.0, max_value=1.0),
    fb=st.floats(min_value=0.0, max_value=1.0),
)
def test_c7_the_unpaired_statistic_is_one_at_the_point_estimate_for_any_table(
    n_a: int, n_b: int, fa: float, fb: float
) -> None:
    """C7 is universal, not a property of the ten literal tables above. Spec section 7 asks for
    ``0 <= events <= n`` and ``1 <= n <= 200``; the two fractions draw the event counts so the
    boundary tables (all-zero, all-n) stay reachable."""
    events_a, events_b = round(fa * n_a), round(fb * n_b)
    delta = events_b / n_b - events_a / n_a
    assert abs(diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=delta) - 1.0) <= 1e-12


# ---------- C8: arm-swap symmetry ----------


@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
@pytest.mark.parametrize("delta", (-0.5, -0.125, 0.0, 0.125, 0.5))
def test_c8_swapping_the_arms_negates_the_delta_and_leaves_the_p_value_alone(
    events_a: int, n_a: int, events_b: int, n_b: int, delta: float
) -> None:
    """``H0: p_b - p_a == delta`` and ``H0: p_a - p_b == -delta`` are the same hypothesis. An
    implementation that pools, orders or clips asymmetrically fails here and passes C7, which is
    why both exist."""
    forward = diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=delta)
    reversed_ = diff_mod.score_p_rd(events_b, n_b, events_a, n_a, delta=-delta)
    assert abs(forward - reversed_) <= 1e-12


@settings(deadline=None, max_examples=120)
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


# ---------- C9: the sole-catch boundary guard ----------


def test_c9_the_all_zero_table_gets_a_finite_non_degenerate_interval() -> None:
    """**Sole-catch guard.** A Wald interval on the risk difference collapses to the single
    point ``(0.0, 0.0)`` here, because its standard error is zero at ``p_hat = 0`` in both arms.
    The S18 arm carried 77% boundary mass and Go1 carries 245 boundary cells of 400, so the
    estimator that fails at the boundary fails on most of a real grid, not on a corner case.

    Written as a literal ``0/32`` vs ``0/32`` table rather than pulled from a fixture because it
    is the guard against the implementation everyone reaches for first.
    """
    lo, hi = diff_mod.interval_rd(0, 32, 0, 32, alpha=0.05)
    assert -1.0 < lo < 0.0 < hi < 1.0, (lo, hi)


def test_c9_the_all_zero_paired_table_gets_a_finite_non_degenerate_interval() -> None:
    """The paired mirror: no discordant pairs either way, over 32 pairs."""
    lo, hi = diff_mod.interval_rd_paired(0, 0, 32, alpha=0.05)
    assert -1.0 < lo < 0.0 < hi < 1.0, (lo, hi)


# ---------- C6: the inversion, at interior endpoints ----------


@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
@pytest.mark.parametrize("alpha", ALPHAS)
def test_c6_an_interior_unpaired_endpoint_solves_the_score_test_at_alpha(
    events_a: int, n_a: int, events_b: int, n_b: int, alpha: float
) -> None:
    """The interval is the inversion of a score test, so each endpoint is a root of
    ``p(delta) = alpha``. Written against the p-value and not against a ``z`` quantile, so the
    ``alpha`` versus ``alpha/2`` error (section 8, trap 2) cannot be got wrong quietly: this is
    a two-sided p-value, and the endpoints solve ``p = alpha``, not ``p = alpha/2``.

    **Interior only.** Where an endpoint sits at ``±1`` the value is *attained* rather than
    solved for -- the parameter space ran out before the root did -- so there is nothing to
    invert. C6b pins that case positively rather than leaving it exempt and unasserted.
    """
    for endpoint in diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=alpha):
        if -1.0 < endpoint < 1.0:
            p = diff_mod.score_p_rd(events_a, n_a, events_b, n_b, delta=endpoint)
            assert abs(p - alpha) <= 1e-9, (endpoint, p, alpha)


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


@pytest.mark.parametrize("alpha", ALPHAS)
def test_c6b_the_lower_endpoint_is_exactly_minus_one_when_the_point_estimate_is_minus_one(
    alpha: float
) -> None:
    lo, hi = diff_mod.interval_rd(32, 32, 0, 32, alpha=alpha)
    assert lo == -1.0 and hi > -1.0, (lo, hi)


@pytest.mark.parametrize("alpha", ALPHAS)
def test_c6b_the_paired_endpoints_are_attained_at_the_two_extremes(alpha: float) -> None:
    """``c == n`` is every pair discordant in one direction, point estimate ``+1``; ``b == n`` is
    the mirror."""
    assert diff_mod.interval_rd_paired(0, 32, 32, alpha=alpha)[1] == 1.0
    assert diff_mod.interval_rd_paired(32, 0, 32, alpha=alpha)[0] == -1.0


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


@pytest.mark.parametrize("events_a,n_a,events_b,n_b", TABLES)
def test_c10_a_smaller_alpha_gives_an_interval_containing_the_larger_alphas(
    events_a: int, n_a: int, events_b: int, n_b: int
) -> None:
    """A smaller ``alpha`` rejects less, so its acceptance region is wider. The spec's original
    wording ("containing the larger one") inverted this; S24.1 corrected it. Nesting is what
    tells a bisector that found a root from one that found a fixed point."""
    wide = diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=0.001)
    narrow = diff_mod.interval_rd(events_a, n_a, events_b, n_b, alpha=0.05)
    assert wide[0] <= narrow[0] and narrow[1] <= wide[1], (wide, narrow)


@pytest.mark.parametrize("b,c,n", PAIRED_TABLES)
def test_c10_the_paired_interval_is_nested_in_alpha_too(b: int, c: int, n: int) -> None:
    wide = diff_mod.interval_rd_paired(b, c, n, alpha=0.001)
    narrow = diff_mod.interval_rd_paired(b, c, n, alpha=0.05)
    assert wide[0] <= narrow[0] and narrow[1] <= wide[1], (wide, narrow)


# ---------- C4 and C5 at the function level ----------


@settings(deadline=None, max_examples=150)
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


@settings(deadline=None, max_examples=120)
@given(data=st.data())
def test_c4_and_c5_hold_for_the_paired_interval_too(data: st.DataObject) -> None:
    """``b + c <= n``: the discordant pairs cannot outnumber the pairs."""
    n = data.draw(st.integers(min_value=1, max_value=200))
    b = data.draw(st.integers(min_value=0, max_value=n))
    c = data.draw(st.integers(min_value=0, max_value=n - b))
    lo, hi = diff_mod.interval_rd_paired(b, c, n, alpha=0.05)
    assert -1.0 <= lo <= (c - b) / n <= hi <= 1.0, (lo, hi)


# ---------- section 7's rejection paths (not a numbered invariant) ----------


@pytest.mark.parametrize("n", (0, -1))
def test_a_non_positive_denominator_is_refused_by_every_one_of_the_four_functions(n: int) -> None:
    """Spec section 7 asks for the rejection paths without giving them a C-number. A zero
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
    """``alpha = 0`` is section 8's trap 4 seen from the function side: a bisection at zero runs
    to its iteration cap and returns ``(-1, 1)``, which is the output section 0.3 exists to
    prevent. It is refused rather than returned."""
    with pytest.raises(diff_mod.DiffError):
        diff_mod.interval_rd(4, 32, 9, 32, alpha=alpha)
    with pytest.raises(diff_mod.DiffError):
        diff_mod.interval_rd_paired(4, 9, 32, alpha=alpha)


# ---------- C1: the object is whole, or it is absent ----------


def test_c1_identical_arms_reject_nothing_and_carry_no_interval_object(synth_root: Path) -> None:
    """C1's zero branch, on the synthetic identical pair: every cell has the same table in both
    arms, Fisher's p is 1.0 everywhere, BH rejects nothing.

    When nothing is significant the honest interval is ``(-1, 1)`` on every cell -- true, and
    worthless, because a reader skimming a column of ``(-1, 1)`` learns nothing while believing
    they were shown an error bar. So the whole object is absent, not wide. ``n_rejected`` stays
    ``0`` because a count of zero is a count; ``alpha_star`` and ``interval_level`` go to
    ``None`` because a level of zero would be a claim.
    """
    result = synth_diff(synth_root, "same-a", "same-b")
    rejections = sum(int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events)
    assert rejections == 0, rejections
    assert result.intervals is None
    assert result.interval_level is None
    assert result.alpha_star is None
    assert result.n_rejected == 0
    assert result.n_interval_only == 0 and result.n_verdict_only == 0


def test_c1_the_absent_frame_is_none_and_never_an_empty_frame(synth_root: Path) -> None:
    """Spec section 3.1. ``multi_diff`` always sets a frame when ``R > 0``, so ``None`` and
    empty never need telling apart -- which is only true if the absent case is spelt ``None``.
    An empty frame says "searched, found nothing"; this ran no search at all. Same rule
    ADR-035 wrote for ``coverage``."""
    result = synth_diff(synth_root, "same-a", "same-b")
    assert result.intervals is None, type(result.intervals)


def test_c1_go1_under_logrank_with_the_inferred_events_also_rejects_nothing(
    go1_inferred_logrank: Any,
) -> None:
    """The committed corroboration for C1's zero branch, found in step zero: Go1's inferred
    event set is ``("survived",)`` and log-rank rejects none of its 400 cells. Kept as
    corroboration and not as the primary fixture, because it rests on a log-rank tie convention
    the Rollout Plan still lists as open -- if that convention moves, this fixture stops being
    a zero and the synthetic pair above still is."""
    result = go1_inferred_logrank
    assert result.n_tests == 400
    assert result.intervals is None and result.interval_level is None and result.alpha_star is None


def test_c1_a_family_with_rejections_carries_every_part_of_the_object(go1_pair: Any) -> None:
    """The other half of the biconditional. Go1 over both events under Fisher rejects 120 of
    800, so all four of the interval fields are populated together. A build that sets the frame
    but leaves the level ``None``, or the reverse, fails here."""
    assert go1_pair.intervals is not None
    assert go1_pair.interval_level is not None
    assert go1_pair.alpha_star is not None
    assert go1_pair.n_rejected > 0


# ---------- C2: the level, and the R it is built from ----------


def test_c2_the_level_is_one_minus_q_times_the_rejection_count_over_n_tests(go1_pair: Any) -> None:
    """ADR-049, recomputed rather than read back. Comparing ``interval_level`` to itself proves
    nothing, so ``R`` is counted here from the ``q`` column the BH pass wrote.

    **Association matters.** The expression is ``1.0 - ((q * R) / m)``. A mathematically equal
    regrouping such as ``1.0 - q * (R / m)`` can differ in the last ulp, and the spec pins this
    exactly, so build it the way it is written in section 3.2.
    """
    result = go1_pair
    rejections = sum(int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events)
    assert result.n_rejected == rejections
    assert result.alpha_star == result.q * rejections / result.n_tests
    assert result.interval_level == 1.0 - result.q * rejections / result.n_tests


def test_c2_the_level_follows_the_rejection_count_and_not_the_verdict_sum(
    go1_fell_logrank: Any,
) -> None:
    """**The discriminating fixture, and the only committed one.** Go1 at ``events=("fell",)``
    under ``logrank_bh`` rejects 196 of 400 cells, but ``n_safer + n_worse`` is 88: 108 cells
    are ``32/32`` vs ``32/32``, ``delta`` is exactly ``0`` so ``multi_diff`` labels them
    ``unchanged``, and log-rank rejects them on the fall *times* rather than the horizon.

    Section 0.2's whole argument is that one threshold decides both the verdict and the
    interval. BH's threshold is ``q x 196 / 400``; a level built from the verdict sum would use
    ``q x 88 / 400`` and reinstate exactly the mismatch the section exists to remove. Every
    other committed configuration has the two counts equal and would let both definitions pass.
    """
    result = go1_fell_logrank
    rejections = sum(int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events)
    verdict_sum = sum(ev.n_safer + ev.n_worse for ev in result.by_event.values())
    assert (rejections, verdict_sum) == (FELL_LOGRANK_REJECTIONS, FELL_LOGRANK_VERDICT_SUM)
    assert result.n_rejected == FELL_LOGRANK_REJECTIONS
    assert result.interval_level == 1.0 - result.q * FELL_LOGRANK_REJECTIONS / FELL_LOGRANK_N_TESTS


def test_c2_the_discriminating_fixture_still_discriminates(go1_fell_logrank: Any) -> None:
    """Before asserting an invariant on a fixture, check the fixture could disagree with it.
    This is that check, promoted to a test of its own so it cannot rot silently: if a future
    change to log-rank, to the tie convention, or to the verdict rule makes these two counts
    equal, the test above stops discriminating and this one says so *here* rather than leaving
    a green suite that pins nothing."""
    result = go1_fell_logrank
    rejections = sum(int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events)
    verdict_sum = sum(ev.n_safer + ev.n_worse for ev in result.by_event.values())
    assert rejections != verdict_sum, (rejections, verdict_sum)
    assert 1.0 - result.q * rejections / result.n_tests != 1.0 - result.q * verdict_sum / result.n_tests


def test_c2_a_per_event_r_would_give_a_different_level_on_this_fixture(go1_pair: Any) -> None:
    """Section 8's trap 3: ``R`` counts the family, not one event. The mutant is a per-event
    ``R``, and it is only catchable on a fixture whose events reject at different rates. Go1
    over both events does: ``fell`` and ``survived`` do not carry the same count, so a level
    built per event cannot equal the family level."""
    result = go1_pair
    per_event = [int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events]
    assert len(set(per_event)) > 0 and sum(per_event) != max(per_event), per_event
    assert result.n_rejected == sum(per_event)


# ---------- C3: the frame's shape ----------


def test_c3_the_frame_has_the_interval_columns_in_order(go1_pair: Any) -> None:
    """Spec section 2's ``INTERVAL_COLUMNS``, restated here as a constant because the spec
    states it (standing rule 1) and read off the frame, so the tuple and the frame cannot
    drift apart."""
    assert tuple(diff_mod.INTERVAL_COLUMNS) == EXPECTED_INTERVAL_COLUMNS
    assert list(go1_pair.intervals.columns) == list(EXPECTED_INTERVAL_COLUMNS)
    assert isinstance(go1_pair.intervals, pd.DataFrame)


def test_c3_there_is_one_row_per_event_and_common_cell_and_no_duplicates(go1_pair: Any) -> None:
    """Section 8's trap 7: ``intervals`` is built over the common cells that ``cells`` covers,
    not over the raw frames. ``coverage`` had to come from the raw frames precisely because a
    wholly-errored cell is absent from the valid ones; an interval is only defined where a test
    ran. The two frames are built from different inputs for good reasons and a build that
    unifies them lands a different row count here."""
    frame = go1_pair.intervals
    expected = {
        (event, config_hash)
        for event in go1_pair.events
        for config_hash in go1_pair.by_event[event].cells["config_hash"]
    }
    seen = list(zip(frame["event"], frame["config_hash"]))
    assert len(seen) == len(expected) == go1_pair.n_tests
    assert set(seen) == expected
    assert len(set(seen)) == len(seen)


# ---------- C4 and C5 on the frame ----------


def test_c4_every_constructed_interval_brackets_the_cells_delta(go1_pair: Any) -> None:
    """The frame-level form of C4: the ``delta`` an interval is *on* is the one ``cells``
    already reports at the same ``(event, config_hash)``, not one recomputed inside the interval
    builder. Spec section 0.0 -- the point estimate does not change and no existing field
    moves."""
    deltas = {
        (event, row.config_hash): row.delta
        for event in go1_pair.events
        for row in go1_pair.by_event[event].cells.itertuples(index=False)
    }
    for row in go1_pair.intervals.itertuples(index=False):
        if row.ci_lo is None:
            continue
        delta = deltas[(row.event, row.config_hash)]
        assert row.ci_lo <= delta <= row.ci_hi, (row.event, row.config_hash, row.ci_lo, delta, row.ci_hi)


def test_c5_every_constructed_endpoint_is_inside_the_unit_interval(go1_pair: Any) -> None:
    for row in go1_pair.intervals.itertuples(index=False):
        if row.ci_lo is None:
            continue
        assert -1.0 <= row.ci_lo <= row.ci_hi <= 1.0, (row.event, row.config_hash, row.ci_lo, row.ci_hi)


# ---------- C11: the disagreement is counted, never reconciled ----------


def test_c11_the_two_counts_equal_the_counts_recomputed_from_the_frame_and_cells(
    go1_pair: Any,
) -> None:
    """Recomputed, not read back. ``n_interval_only`` is a cell the verdict left ``unchanged``
    whose interval excludes zero -- the price of Fisher's exactness, since its p-value is
    usually larger than the score p-value on the same table. ``n_verdict_only`` is the reverse.

    Neither number changes a verdict, a ``q`` or a ``check()`` result, and neither is asserted
    to be zero anywhere: section 0.6 is explicit that under ``logrank_bh`` disagreement runs in
    both directions and is not a bug.
    """
    result = go1_pair
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
    go1_fell_logrank: Any,
) -> None:
    """Section 0.6: ``logrank_bh`` tests the whole curve while the interval speaks about the
    horizon only. A curve that separates early and closes by ``h`` is a real rejection with an
    interval covering zero, and it is not an error. Same recomputation, on the fixture where the
    disagreement is expected rather than incidental."""
    result = go1_fell_logrank
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


def test_c11_the_two_counts_are_not_interchangeable_on_this_fixture(go1_pair: Any) -> None:
    """The handoff's "the two counts swapped" mutant is only catchable where the two differ.
    This says the fixture separates them, so the assertions above are load-bearing. Which of the
    two is larger is not asserted: section 0.6 gives the expected direction, and a run that
    contradicts it is a finding about the two tests, not a test failure."""
    assert go1_pair.n_interval_only != go1_pair.n_verdict_only, (
        go1_pair.n_interval_only,
        go1_pair.n_verdict_only,
    )


# ---------- C12: the basis follows the method, never the provenance ----------


def test_c12_the_same_frames_give_the_same_interval_pairable_or_not(synth_root: Path) -> None:
    """ADR-052, and the trap it was written for. ``moved-b`` and ``moved-b-unpaired`` hold
    identical episodes and differ only in ``run_salt``, so the two diffs below see the same
    tables and differ only in ``seed_identity_match`` (``paired`` until P-1).

    Two runs that happen to share a run salt must not get a different number from two that do
    not, or the statistic becomes a property of run provenance rather than of the request, and a
    reader could not tell which was run without going back to the manifests. This is the
    constraint the correctness queue's item 5 was written under, applied to the second statistic
    in the same function.
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


def test_c12_logrank_takes_the_unpaired_basis(go1_fell_logrank: Any) -> None:
    """The third row of section 0.7's table. ``logrank_bh`` runs on a pairable Go1 pair and
    still takes ``score_rd``: the basis follows the requested method, and log-rank is not a
    paired method however the runs were produced."""
    assert set(go1_fell_logrank.intervals["basis"]) == {"score_rd"}


# ---------- C13: the censoring contract, and what it cannot pin ----------


def test_c13_the_endpoints_are_none_exactly_when_the_basis_is_censored(
    go1_pair: Any, go1_fell_logrank: Any, synth_root: Path
) -> None:
    """Spec section 3.1's contract, over every fixture that produces a frame.

    **This does not pin the censored branch, and saying so is the point.** ADR-050's guard was
    written against ``_truncate_raw``, which censors at the horizon -- and the horizon is ``>=``
    every retained event time, so the Aalen-Johansen estimate there reduces to the naive
    proportion and the guard cannot fire. Five shapes were measured in step zero (late
    truncation, two event times, a tie exactly at the horizon, three competing kinds, and 19
    distinct event times) and every one deviates by ``0.0``. There is no input to ``multi_diff``
    that produces ``basis == "censored"``, so there is no fixture for the branch.

    What this *does* pin is the contract in both directions plus the negative: a build whose
    guard is inverted, or whose tolerance points the wrong way, marks a clean cell ``censored``
    and fails here. The guard stays in the build as a forward guard -- it is what stops a later
    change to truncation or to the estimator from silently putting a binomial interval on
    censored data.
    """
    for result in (go1_pair, go1_fell_logrank, synth_diff(synth_root, "moved-a", "moved-b")):
        for row in result.intervals.itertuples(index=False):
            assert (row.ci_lo is None) == (row.ci_hi is None) == (row.basis == "censored"), (
                row.event,
                row.config_hash,
                row.ci_lo,
                row.ci_hi,
                row.basis,
            )


def test_c13_no_cell_that_satisfies_the_censoring_guard_is_marked_censored(go1_pair: Any) -> None:
    """The negative, on the fixture where the guard's own input is known: every Go1 cell has
    ``|rate_x - events_x / n_x| == 0.0`` exactly, on both arms, measured in step zero. So no row
    of this frame may carry ``basis == "censored"``, and one that does means the guard is
    inverted or reading the wrong quantity."""
    rates = {
        (event, row.config_hash): (
            abs(row.rate_a - row.events_a / row.n_a),
            abs(row.rate_b - row.events_b / row.n_b),
        )
        for event in go1_pair.events
        for row in go1_pair.by_event[event].cells.itertuples(index=False)
    }
    assert max(max(pair) for pair in rates.values()) <= CIF_TOLERANCE
    for row in go1_pair.intervals.itertuples(index=False):
        assert row.basis != "censored", (row.event, row.config_hash)


def test_c13b_the_rejection_count_covers_every_cell_whatever_its_basis(go1_fell_logrank: Any) -> None:
    """The guard decides whether an *interval* is built, never whether a hypothesis was
    rejected. ``n_rejected`` is counted over the whole ``cells`` frame with no filter on basis,
    so a build that counts only the cells it managed to give an interval to lands a smaller
    ``R`` and a wider level. On today's fixtures no cell is filtered, so this pins the shape of
    the count rather than a difference; the censored half is unpinnable for the reason C13
    gives."""
    result = go1_fell_logrank
    total_cells = sum(len(result.by_event[e].cells) for e in result.events)
    assert total_cells == result.n_tests == len(result.intervals)
    assert result.n_rejected == sum(
        int((result.by_event[e].cells["q"] < result.q).sum()) for e in result.events
    )


# ---------- C17: the basis vocabulary ----------


def test_c17_interval_bases_is_exactly_the_three_names_the_spec_states() -> None:
    """Spec section 2. Written once in ``diff.py``, the way ``_CAUSES`` is (ADR-035)."""
    assert tuple(diff_mod.INTERVAL_BASES) == EXPECTED_INTERVAL_BASES


def test_c17_every_basis_on_every_frame_is_drawn_from_that_tuple(
    go1_pair: Any, go1_fell_logrank: Any, synth_root: Path
) -> None:
    for result in (
        go1_pair,
        go1_fell_logrank,
        synth_diff(synth_root, "moved-a", "moved-b", "fisher_bh"),
        synth_diff(synth_root, "moved-a", "moved-b", "mcnemar_bh"),
    ):
        assert set(result.intervals["basis"]) <= set(EXPECTED_INTERVAL_BASES), set(
            result.intervals["basis"]
        )


# ---------- C14: nothing that was already printed moves ----------


def test_c14_the_go1_markdown_is_byte_identical_to_the_bare_tree(go1_pair: Any) -> None:
    """``to_markdown()`` gains nothing from S24. It is the cheapest surface in the repo to break
    and the dearest to re-baseline, and S21 held the same line for ``coverage``. A digest minted
    before the build exists, never a diff of two renders. **Re-minted by P-1 Session A** off its
    shadow shim: the parameter line now reads ``seed_identity_match=True, unpaired_analysis=True``
    where ``paired=True`` stood and the headline ends ``unpaired)`` (P-1 section 3.3); S24 section
    0.8's *does not gain a byte* was S24's rule for S24's packet and P-1 retires it (P-1 section 8).
    The interval block's bytes, which S24 owns, are asserted unchanged by P-1's own Y11."""
    assert sha256_of_text(go1_pair.to_markdown()) == PAIR_MARKDOWN_SHA256


def test_c14_the_go1_logrank_markdown_is_byte_identical_too(go1_fell_logrank: Any) -> None:
    assert sha256_of_text(go1_fell_logrank.to_markdown()) == FELL_LOGRANK_MARKDOWN_SHA256


def test_c14_the_headline_the_trade_line_and_check_are_unchanged(
    go1_pair: Any, go1_fell_logrank: Any
) -> None:
    """``headline()``, ``trade_line()`` and ``check()`` gain nothing from S24. The literals are
    the ones the tree produces. **P-1 moved the headline's last token** to the requested method's
    pairing (ADR-052) -- ``unpaired`` under ``fisher_bh`` and ``logrank_bh`` however the runs were
    produced -- which is the Rollout Plan Phase 2 item this docstring once pinned as *current
    wording* so that S24 could not be what moved it; P-1 was."""
    assert go1_pair.headline() == PAIR_HEADLINE
    assert go1_pair.trade_line() == PAIR_TRADE_LINE
    assert go1_pair.check() is False and go1_pair.check("any") is False
    assert go1_fell_logrank.headline() == FELL_LOGRANK_HEADLINE
    assert go1_fell_logrank.trade_line() is None
    assert go1_fell_logrank.check() is True and go1_fell_logrank.check("any") is False


def test_c14_the_cells_columns_are_unchanged(go1_pair: Any) -> None:
    """ADR-051: the interval is its own frame, not two columns on ``cells``. ``CELLS_COLUMNS``
    has twelve pin sites across ``diff.py`` and two frozen M6 oracles, and M7's multi oracles
    build that frame by hand; S21 measured this cost and declined to pay it for ``coverage``,
    and nothing about an interval makes it cheaper. This is the test that fails if someone pays
    it anyway."""
    assert CELLS_COLUMNS == (
        "config_hash", "config", "n_a", "n_b", "events_a", "events_b",
        "rate_a", "rate_b", "delta", "stat", "p", "q", "verdict", "mde",
    )
    for event in go1_pair.events:
        assert list(go1_pair.by_event[event].cells.columns) == list(CELLS_COLUMNS)


def e14_builder_digests() -> dict[str, str]:
    """The E14 argv's ``multi`` and spec, rendered by the M7 builder with no tree, the way
    ``_report_pair`` builds them: the dark-theme report's markdown and the light-theme receipt."""
    store = Store(GO1_ROOT)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        multi = multi_diff(
            store.read(GO1_A, meta=False), store.read(GO1_B, meta=False), events=["fell"],
            manifest_a=ma, manifest_b=mb,
        )
    title = f"{GO1_A} vs {GO1_B}: fell"
    report = build_multi_report(
        multi, ReportSpec(title=title, x_axis="mu", y_axis="push_pct_bw"), manifests=(ma, mb)
    )
    receipt = build_multi_report(
        multi, ReportSpec(title=title, x_axis="mu", y_axis="push_pct_bw", theme="light"),
        manifests=(ma, mb),
    )
    return {
        "report.md": hashlib.sha256(report.to_markdown().encode("utf-8")).hexdigest(),
        "receipt.html": hashlib.sha256(receipt.to_html().encode("utf-8")).hexdigest(),
    }


def test_c14_the_go1_report_still_reproduces_the_three_digests_s21_minted(tmp_path: Path) -> None:
    """The three digests S21's E14 pins, restated rather than imported so two frozen oracles do
    not couple. ``report`` renders through ``MultiDiffResult``; if S24 leaks a byte into
    ``to_markdown``, the receipt or the heatmap, one of these three moves.

    Narrowed for S28 (draft ADR-074, spec S28 section 3.8): ``report`` on a pair now renders the
    layered report into ``report.md`` and ``receipt.html``, so those two files through the CLI
    are S28's to pin. The surface S21 owned is the tree-less M7 builder, which reproduces both
    digests bit for bit (S28 section 0.2), so the two markdown and HTML pins move to
    ``build_multi_report(multi, spec, manifests=...)`` with no tree; ``heatmap.svg`` never
    changes (S28 section 3.3) and stays pinned through the CLI. Narrowed, not deleted."""
    out = tmp_path / "report"
    code, text, _ = run_cli(["--store", str(GO1_ROOT), *E14_ARGV, "--out", str(out)])
    assert code == 0, text
    assert hashlib.sha256((out / "heatmap.svg").read_bytes()).hexdigest() == E14_SHA256["heatmap.svg"]
    for name, digest in e14_builder_digests().items():
        assert digest == E14_SHA256[name], name


# ---------- C15: the BH family does not move ----------


def test_c15_the_family_its_q_and_its_pairing_are_unchanged(go1_pair: Any) -> None:
    """S24 adds an interval around a number that is already there. It does not retest, rescope
    or reweight anything: ``n_tests`` is the same 800, ``q`` the same 0.05, ``seed_identity_match`` (``paired`` until P-1) the same
    ``True``, and ``coverage`` the same frame S21 built."""
    assert go1_pair.n_tests == 800
    assert go1_pair.q == 0.05
    assert go1_pair.seed_identity_match is True
    assert go1_pair.truncated == 0
    assert len(go1_pair.coverage) == 400
    assert sha256_of_text(go1_pair.coverage.to_json(orient="records")) == COVERAGE_SHA256


def test_c15_every_q_value_and_every_delta_on_cells_is_unchanged(
    go1_pair: Any, go1_fell_logrank: Any
) -> None:
    """The per-cell BH output itself, at full float precision. A build that reorders the rows
    fed to ``bh``, or slips the interval construction in before the BH pass rather than after
    it, moves one of these digests. Section 3.3 is exact about the order: after the BH pass and
    after ``by_event``, because the level cannot be known before ``R``."""
    assert sha256_of_column(go1_pair, "q") == PAIR_QCOLUMN_SHA256
    assert sha256_of_column(go1_pair, "delta") == PAIR_DELTA_SHA256
    assert sha256_of_column(go1_fell_logrank, "q") == FELL_LOGRANK_QCOLUMN_SHA256


def test_c15_to_json_gains_the_six_keys_and_keeps_every_key_it_had(go1_pair: Any) -> None:
    """Additive, like ``coverage`` before it. The six new keys are present and every key the
    bare tree emitted is still there."""
    payload = go1_pair.to_json()
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


def test_c15_a_hand_built_result_still_constructs_without_any_new_field(go1_pair: Any) -> None:
    """Section 8's trap 8, and the S21 lesson repeated. M7's two oracles build
    ``MultiDiffResult`` by hand from keywords; an undefaulted new field breaks every one of
    them. Rebuilt here from the fields that existed before this packet, and the result must
    carry the absent-interval state rather than a half-populated one."""
    before = (
        "events", "by_event", "method", "seed_identity_match", "unpaired_analysis", "q", "t_unit", "horizon", "n_tests",
        "n_not_comparable", "dropped_a", "dropped_b", "truncated", "trades", "inferred",
        "non_event",
    )
    bare = diff_mod.MultiDiffResult(**{name: getattr(go1_pair, name) for name in before})
    assert bare.intervals is None
    assert bare.interval_level is None and bare.alpha_star is None
    assert bare.n_rejected == 0 and bare.n_interval_only == 0 and bare.n_verdict_only == 0


# ---------- C16: one construction ----------


def test_c16_the_two_interval_functions_are_each_called_from_exactly_one_place() -> None:
    """**The rule, stated in prose rather than matched as a substring.** Where an ADR constrains
    how a value is built, a test must fail if it is built anywhere else -- ADR-021 was
    documented and then violated twice, which is where this rule came from.

    Here the constraint is ADR-049's: the level and the interval must not drift apart. Both
    ``interval_rd`` and ``interval_rd_paired`` take ``alpha`` from the caller, so a second call
    site is a second place ``alpha`` is chosen, and nothing would make the two agree. Each is
    called exactly once across the whole package, and both calls sit in the same function --
    the interval builder -- so ``alpha_star`` is computed once and spent once.
    """
    sites: dict[str, list[tuple[str, int, str]]] = {"interval_rd": [], "interval_rd_paired": []}
    for path in sorted(PACKAGE.glob("*.py")):
        tree = parsed(path)
        enclosing = enclosing_functions(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name in sites:
                sites[name].append((path.name, node.lineno, enclosing.get(node, "<module>")))
    assert len(sites["interval_rd"]) == 1, sites["interval_rd"]
    assert len(sites["interval_rd_paired"]) == 1, sites["interval_rd_paired"]
    assert sites["interval_rd"][0][0] == "diff.py", sites["interval_rd"]
    assert sites["interval_rd_paired"][0][0] == "diff.py", sites["interval_rd_paired"]
    assert sites["interval_rd"][0][2] == sites["interval_rd_paired"][0][2], sites


# ---------- C19: R is derived once, and the CLI derives nothing ----------


def test_c19_the_cli_does_no_arithmetic_on_any_interval_field() -> None:
    """**The rule, in prose.** ``cli.py`` computes nothing and decides nothing statistical. It
    may read a field and print it, and it may ask whether one is ``None``; it may not do
    arithmetic on one. Recovering ``R`` as ``alpha_star * m / q``, or ``alpha*`` as
    ``1 - interval_level``, would be a second derivation free to disagree with M6's -- which is
    the whole reason ``n_rejected`` and ``alpha_star`` are fields at all.

    Arithmetic is the line, not comparison: ``if multi.intervals is None`` is rendering logic
    and stays legal. Any ``BinOp`` whose subtree mentions one of the six names is not.
    """
    guarded = {
        "intervals", "interval_level", "alpha_star", "n_rejected",
        "n_interval_only", "n_verdict_only",
    }
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(parsed(PACKAGE / "cli.py")):
        if not isinstance(node, ast.BinOp):
            continue
        mentioned = {
            child.attr if isinstance(child, ast.Attribute) else child.id
            for child in ast.walk(node)
            if isinstance(child, (ast.Attribute, ast.Name))
        }
        if mentioned & guarded:
            offenders.append((node.lineno, sorted(mentioned & guarded)[0]))
    assert offenders == [], offenders


# ---------- C18: the CLI block ----------


def test_c18_the_diff_output_prints_the_alpha_star_arithmetic_and_names_the_family(
    synth_root: Path,
) -> None:
    """Section 3.4, through ``main()`` with ``StringIO`` streams. Both streams and the exit code.

    **The family is named.** Phase 4 introduces a nested family with a different level, so a
    bare ``alpha*`` on the page would be the one number a reader could not attribute. The level,
    ``R`` and ``m`` are captured from the line and checked against the fields rather than pinned
    as formatted floats: section 3.4's four-decimal example renders section 0.2's own motivating
    case (1200 cells, one rejection) as ``0.0000``, and pinning that format would freeze a
    defect into the oracle.
    """
    result = synth_diff(synth_root, "moved-a", "moved-b", "fisher_bh")
    code, out, err = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail"])
    assert code == 0, (out, err)
    assert err == "", err
    match = INTERVAL_LINE.search(out)
    assert match is not None, out
    level, alpha_star, rejections, tests, basis = match.groups()
    assert int(rejections) == result.n_rejected
    assert int(tests) == result.n_tests
    assert abs(float(level) / 100.0 - result.interval_level) <= 1e-9
    assert abs(float(alpha_star) - result.alpha_star) <= 1e-9
    assert basis == "score_rd"


def test_c18_the_diff_output_prints_both_disagreement_counts(synth_root: Path) -> None:
    """The two lines under the header, from section 3.4. The counts are fields; the CLI prints
    them and asserts nothing about their direction."""
    result = synth_diff(synth_root, "moved-a", "moved-b", "fisher_bh")
    code, out, _ = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail"])
    assert code == 0, out
    assert f"interval excludes zero, verdict unchanged: {result.n_interval_only} cells" in out
    assert f"verdict significant, interval covers zero: {result.n_verdict_only} cells" in out


def test_c18_the_diff_output_prints_the_no_interval_line_when_nothing_was_rejected(
    synth_root: Path,
) -> None:
    """Section 3.4's other branch, verbatim. On an underpowered grid this is the whole of S24's
    output, and it points at the object that *is* right there -- the MDE lines above it. That is
    correct and it is not a fix; S23 is the packet that acts on it, before the spend rather than
    after."""
    code, out, err = run_cli(["--store", str(synth_root), "diff", "same-a", "same-b", "--event", "fail"])
    assert code == 0, (out, err)
    assert err == "", err
    assert NO_INTERVAL_LINE in out, out
    assert INTERVAL_LINE.search(out) is None, out


def test_c18_the_interval_block_follows_the_coverage_block(synth_root: Path) -> None:
    """Section 3.4: after ``_coverage_block``. The order is the reading order -- what was
    measured, then what the measurement bounds."""
    code, out, _ = run_cli(["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail"])
    assert code == 0, out
    assert "## coverage" in out, out
    assert out.index("## coverage") < out.index("intervals: "), out


def test_c18_the_json_format_carries_the_fields_and_prints_no_block(synth_root: Path) -> None:
    """``--format json`` renders ``to_json()`` and nothing else. The interval block is text
    output; the JSON payload carries the same facts as fields, which is what a consumer reads."""
    code, out, _ = run_cli(
        ["--store", str(synth_root), "diff", "moved-a", "moved-b", "--event", "fail", "--format", "json"]
    )
    assert code == 0, out
    assert "intervals: " not in out
    assert '"interval_level"' in out and '"n_rejected"' in out and '"alpha_star"' in out
