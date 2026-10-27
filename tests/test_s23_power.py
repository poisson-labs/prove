"""S23 -- the power gate: the frozen tests for W1-W12.

Written from the S23 invariants. The build changes
``src/poisson_prove/executor.py``, ``executor_modal.py`` and ``cli.py`` against this file and does
not edit it. ``examples/quickstart.toml`` was rebalanced before the build and is not the build's.

**What the gate is for.** ``MDE at N=32 (worst case, rate 0.5): 0.3251`` printed before a single
episode of an earlier sweep ran, was close to the realised per-cell maximum, and was read
twice and acted on zero times. A louder warning is not the fix -- ``--yes`` is on every command
in that sweep's README, so the prompt was never a gate either. The number gets a threshold, the
threshold fires before any spend, and clearing it costs a number rather than a shrug.

No network, no backend, no dollar. The Modal half of W8 goes through ``run_with_mapper`` with an
in-process mapper, which is how the M3 modal frozen tests reach that path without ``modal``
installed.

**The four S23 names are reached through the module** -- ``executor.check_power``, not
``check_power`` -- for one reason: before the build adds them, a ``from ... import`` of a name
that does not exist yet is a *collection* error, and pytest abandons the whole run on one. That
would leave the entire suite unrunnable for as long as this file sits frozen and unbuilt, which
is exactly the window in which someone wants to run it. Qualified, this file collects, its own
tests fail, and every other test in the repo still reports. The names that already exist
(``Plan``, ``plan``, ``preflight``, ``ExecutorError``) are imported normally.

**Conventions these frozen tests fix where S23 is silent, recorded so they are not
re-litigated. The build follows these.**

- **The seam that carries the accepted value to the manifest is ``Plan.max_mde_accepted``**, a
  field with a default of ``None`` set through ``plan(..., max_mde_accepted=...)``. S23
  states ``check_power``'s signature and where the value lands; nothing states
  how it gets there. ``Plan.import_path`` is the exact precedent: a value the CLI supplies purely
  so the runners can put it in ``environment``, read by nothing else. W11 forbids ``check_power``
  *mutating* the plan, which this does not -- the CLI builds the plan with it. **Measured:** the
  obvious alternative, a keyword on ``run_local`` / ``run_with_mapper`` / ``run_modal``, breaks
  ten frozen tests whose fakes double those signatures (``CapturedRunModal`` and friends in the
  M10 and M3-modal-launch frozen tests) for no gain. When ``None``, both runners record
  ``DEFAULT_MAX_MDE``: that is the threshold that was in force, and W8 requires every launched
  run to carry one.
- **A resume inherits by the CLI resolving the effective threshold, not by skipping the gate.**
  S23 says ``check_power`` is skipped on a resume whose manifest still covers the
  design, but ``check_power`` takes no store and so cannot read a manifest. Instead ``_cmd_sweep``
  passes ``max_mde=ns.max_mde`` when given, else ``manifest.environment["max_mde_accepted"]`` on a
  resume, else ``None``; ``check_power`` then compares against the *current* design exactly as it
  always does. That keeps the comparison in M3 (the CLI decides nothing statistical),
  and it is why a resume whose design grew is still refused (W9).
- **``cli.py`` imports ``DEFAULT_MAX_MDE``; it does not define one.** S23 forbids
  putting the constant in ``cli.py`` "beside ``_DEFAULT_METHOD``" -- that is a prohibition on a
  second *definition*, which would be a threshold that can drift from M3's. The CLI needs the
  value for one non-statistical purpose: deciding what to record when no flag was passed. It
  imports M3's single definition, makes no comparison of its own, and never calls
  ``preflight_mde``.
- **``--max-mde``'s range is enforced in M3, not in the CLI**, by exact analogy with ``--q``:
  ``0.0 < q < 1.0`` lives in ``diff.py`` and reaches the user as a ``DiffError`` at exit 2. So an
  out-of-range ``--max-mde`` is an ``ExecutorError`` from ``check_power``. W6 says "refused at
  exit 2 before planning"; ``plan()`` writes nothing, so the observable fact is *before anything
  is written*, and that is what is asserted here. A non-float is argparse's, also exit 2.
- **The suggested override in the refusal message must itself clear the gate** (W4, last
  clause). This is not decoration: at N=32 the true MDE is 0.32510999..., the pre-flight prints
  it as ``0.3251``, and ``--max-mde 0.3251`` *refuses*. A message telling the reader to paste a
  number that does not work is the gate's usability failing at its one interaction. Round the
  suggestion up at four decimals, or print it with more; either satisfies this.

**Three findings from the pass before the build, recorded here because they contradict S23.**

1. **No test pinned ``worst case``.** S23 says the M3 local and modal frozen tests pin the
   pre-flight text including that label. They do not: both match the line with
   ``MDE at N=\\d+[^:]*:``, which swallows either label, and the string appears in no test in the
   repo. Verified by making the W10 edit in ``src/`` and running the M3 and M10 frozen tests unchanged.
   W10 below is therefore the only guard the label has ever had.
2. **The quickstart's headline is pinned nowhere.** M10's I20 asserts ``worse == 0 and safer >=
   1``, never a cell count. ``8 of 15 cells safer`` lives in the project's records' renders and in no test.
3. **Four frozen test files pinned the quickstart grid, not one.** M10 (cells, replicates, axis width),
   M12 (its own second copy of both), M13 (the BH family size) and M7 (the mock-agent trade
   golden). S23 expected M10 and explicitly not M7. All four moved before the build.
"""

from __future__ import annotations

import functools
import io
import math
import re
from collections.abc import Iterator, Sequence
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from poisson_prove import cli
from poisson_prove.diff import mde_two_proportion
import poisson_prove.executor as executor
from poisson_prove.executor import ExecutorError, Plan, plan, preflight
from poisson_prove.executor_modal import (
    Job,
    ModalOptions,
    Result as ModalResult,
    preflight_modal,
    run_with_mapper,
    worker_batch,
)
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import RunManifest, Store
import lattice
from conftest import PACKAGED_QUICKSTART, quickstart_design

# PF3: the one copy is the packaged spec; this is its design at
# the 100 replicates this file was frozen at.
QUICKSTART = quickstart_design()

MOCK_ROLLOUT = "poisson_prove.examples.mock_agent:rollout"
MOCK_PATCHED = "poisson_prove.examples.mock_agent:rollout_patched"

#: The default limit. S23 states it, so it may be a constant here.
EXPECTED_DEFAULT = 0.20

#: The lattice's design (``tests/lattice.py``), twelve ``gain`` by six ``load`` at N=32, built here in
#: code and never read from a store: one of the two N=32 designs the default is calibrated to refuse
#: (W12), the four-condition ``spec_at(32)`` the other.
LATTICE_REPLICATES = 32
LATTICE_GAIN = [round(0.1 * k, 1) for k in range(1, 13)]
LATTICE_LOAD = [10.0, 20.0, 30.0, 40.0, 50.0, 100.0]
LATTICE_TARGET = "lattice-before"
assert (LATTICE_REPLICATES, tuple(LATTICE_GAIN), tuple(LATTICE_LOAD), LATTICE_TARGET) == (
    lattice.N, lattice.GAIN, lattice.LOAD, lattice.TARGET_A
)

#: A design that clears the default (W12's second half). S23 names 105; it is not the
#: bisection answer (that is 93, below) and nothing here depends on which it is.
# PF4 re-freeze (PF4.30): the gate asks Fisher's exact test at q / M at the worst base rate, so
# 105 replicates over the four conditions below no longer clear the default; 150 do, which
# test_w12_a_design_at_the_clearing_replicate_count_passes_at_the_default checks against the
# references rather than trusting.
CLEARING_REPLICATES = 150

#: The gate's false discovery rate and target power, as S23 states them.
Q = 0.05
POWER = 0.8

#: PF4 re-freeze: the quickstart's design at 100 replicates with nothing declared
#: (nine rows) is refused at the default 0.20; ``--max-mde 0.3`` is the round value above its limit.
QUICKSTART_MAX_MDE = 0.3

#: The conditions of ``spec_at`` and ``underpowered_toml``, one event each (nothing declared).
FOUR = 4

MDE_LINE = re.compile(r"MDE at N=(\d+) \(base rate 0\.5\): ([0-9]*\.?[0-9]+)")


# ---------- helpers ----------


def spec_at(replicates: int, *, cells: int = 4, target_id: str = "gate@v0") -> SweepSpec:
    return SweepSpec.build(
        [{"x": float(i)} for i in range(cells)],
        replicates=replicates,
        target_id=target_id,
        t_unit="tool_calls",
    )


def lattice_spec() -> SweepSpec:
    return SweepSpec.build(
        [{"gain": gain, "load": load} for gain in LATTICE_GAIN for load in LATTICE_LOAD],
        replicates=LATTICE_REPLICATES,
        target_id=LATTICE_TARGET,
        t_unit="seconds",
    )


class Result:
    def __init__(self, code: int, out: str, err: str) -> None:
        self.code, self.out, self.err = code, out, err

    @property
    def text(self) -> str:
        return self.out + self.err


def run_cli(argv: Sequence[str]) -> Result:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=io.StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def sweep_argv(root: Path, spec_path: Path, target: str, *extra: str) -> list[str]:
    return ["--store", str(root), "sweep", str(spec_path), "--target", target, "--yes", *extra]


def write_spec(path: Path, spec_toml: str) -> Path:
    path.write_text(spec_toml, encoding="utf-8")
    return path


def underpowered_toml(replicates: int = 16) -> str:
    """The quickstart's old shape: three tasks, three rates, too few replicates to resolve."""
    return (
        'target_id = "mock-agent@v0"\n'
        't_unit = "tool_calls"\n'
        f"replicates = {replicates}\n\n"
        "[axes.task_id]\n"
        'type = "categorical"\n'
        'values = ["search", "checkout"]\n\n'
        "[axes.tool_fail_rate]\n"
        'type = "continuous"\n'
        "values = [0.0, 0.55]\n"
    )


def store_is_untouched(root: Path) -> bool:
    """No run exists, by both readings: the store's own listing and the directory tree."""
    if not root.exists():
        return True
    if Store(root).runs():
        return False
    return not [p for p in root.iterdir() if p.is_dir()]


def run_id_of(root: Path) -> str:
    """The run a sweep created. A sweep no longer ends with a ``run_id:`` line,
    so the run is read from the store, which held no run before the sweep."""
    created = sorted(Store(root).runs())
    assert len(created) == 1, created
    return created[0]


def in_process_mapper(
    batches: Sequence[Sequence[Job]],
) -> Iterator[tuple[int, list[ModalResult] | BaseException]]:
    """The M3 modal frozen tests' shape: every batch run here, in submission order, no modal import."""
    for index, jobs in enumerate(batches):
        yield index, worker_batch(jobs, MOCK_ROLLOUT, None)


# ---------- PF4.30, PF4.48a: the gate's rule, from the stats file's references ----------

#: Every accepted change a refusal can offer: three decimals, above 0 and up to 1 (PF4.49).
GATE_T = np.arange(1, 1001) / 1000


@functools.cache
def _ref_gate_table(n: int, rows: int, test: str) -> tuple[tuple[tuple[float, str], ...], np.ndarray]:
    """For each base rate on the 0.005 grid and each way (a rise first), the power at exactly each
    accepted change of ``GATE_T``, at level q / rows, NaN where that change has no room (PF4.30)."""
    from test_pf4_stats import _ref_fisher_power, _ref_paired_power

    level = Q / rows
    keys: list[tuple[float, str]] = []
    table: list[np.ndarray] = []
    for base in np.round(np.arange(0.0, 1.0 + 1e-9, 0.005), 3):
        for way in ("rise", "fall"):
            room = 1 - base if way == "rise" else base
            if test == "fisher":
                power = _ref_fisher_power(float(base), n, n, level, GATE_T, way == "rise")
            else:
                power = _ref_paired_power(float(base), n, level, GATE_T, way == "rise")
            keys.append((float(base), way))
            table.append(np.where(GATE_T <= room + 1e-9, power, np.nan))
    return tuple(keys), np.array(table)


def _column(accepted: float) -> int:
    k = int(round(accepted * 1000)) - 1
    assert abs(GATE_T[k] - accepted) <= 1e-12, accepted
    return k


def ref_admits(n: int, rows: int, accepted: float, test: str = "fisher") -> bool:
    """The gate's rule: the power at exactly ``accepted`` reaches the target at every base rate
    where it has room."""
    _, table = _ref_gate_table(n, rows, test)
    column = table[:, _column(accepted)]
    return bool((column[~np.isnan(column)] >= POWER).all())


def ref_worst(n: int, rows: int, accepted: float, test: str = "fisher") -> tuple[float, str, float | None]:
    """The worst base rate at exactly ``accepted`` (ties within 1e-12 to the lower base rate, a rise
    first; PF4.48a), the way the change goes there, and the limit that way at that base rate."""
    from test_pf4_stats import _ref_fisher_power, _ref_limit, _ref_paired_power

    keys, table = _ref_gate_table(n, rows, test)
    worst = (2.0, 0.0, "rise")
    for (base, way), power in zip(keys, table[:, _column(accepted)]):
        if not np.isnan(power) and power < worst[0] - 1e-12:
            worst = (float(power), base, way)
    _, base, way = worst
    level = Q / rows
    room = 1 - base if way == "rise" else base
    if test == "fisher":
        limit = _ref_limit(lambda g: _ref_fisher_power(base, n, n, level, g, way == "rise"), room)
    else:
        limit = _ref_limit(lambda g: _ref_paired_power(base, n, level, g, way == "rise"), room)
    return base, way, limit


def ref_offer(n: int, rows: int, accepted: float, test: str = "fisher") -> float:
    """The smallest three-decimal accepted change at or above ``accepted`` that admits the design."""
    for t in GATE_T:
        if t >= accepted - 1e-12 and ref_admits(n, rows, float(t), test):
            return float(t)
    raise AssertionError((n, rows, accepted, test))


def assert_design_recorded(design: dict, *, n: int, rows: int, accepted: float) -> None:
    """``environment["design_mde"]`` (PF4.30, PF4.48a): the limit at the worst base rate for the
    accepted change, its base rate and way, Fisher's test at q / M, and the design's family."""
    base, way, limit = ref_worst(n, rows, accepted)
    assert set(design) == {"mde", "base_rate", "direction", "test", "level", "family", "conditions",
                           "events", "q", "power", "flaggable"}, sorted(design)
    assert (design["base_rate"], design["direction"]) == (base, way), (design, base, way)
    assert limit is not None and abs(design["mde"] - limit) <= 1e-4 + 1e-12, (design, limit)
    assert (design["test"], design["family"], design["conditions"], design["events"]) == ("fisher", rows, rows, 1)
    assert abs(design["level"] - Q / rows) <= 1e-15 and design["q"] == Q and design["power"] == POWER
    assert design["flaggable"] is True


# ---------- W1: one statistic, and it is the one already computed ----------


@pytest.mark.parametrize("replicates", [2, 3, 8, 16, 32, 64, 93, 100, 105, 256, 1000])
def test_w1_preflight_mde_is_mde_two_proportion_at_base_rate_one_half(replicates: int) -> None:
    assert executor.preflight_mde(spec_at(replicates)) == mde_two_proportion(0.5, replicates, replicates)


def saturation_ceiling() -> int:
    """The largest N whose MDE is still the saturated 0.5, found rather than written."""
    n = 2
    while executor.preflight_mde(spec_at(n + 1)) == executor.preflight_mde(spec_at(n)) and n < 1000:
        n += 1
    return n


@given(a=st.integers(min_value=2, max_value=1000), b=st.integers(min_value=2, max_value=1000))
@settings(deadline=None, max_examples=60)
def test_w1_preflight_mde_never_rises_with_replicates(a: int, b: int) -> None:
    lo, hi = min(a, b), max(a, b)
    assert executor.preflight_mde(spec_at(hi)) <= executor.preflight_mde(spec_at(lo)), (lo, hi)


@given(a=st.integers(min_value=11, max_value=1000), b=st.integers(min_value=11, max_value=1000))
@settings(deadline=None, max_examples=60)
def test_w1_preflight_mde_is_strictly_decreasing_above_the_saturation_point(a: int, b: int) -> None:
    """W1 says "strictly decreasing" over 2-1000 and it is not, below N=11.

    ``mde_two_proportion`` returns the largest possible increase when even that is
    undetectable, so at base rate 0.5 every design with ten or fewer replicates reports exactly
    0.5 and they are all equal. Strictness holds from the first N that resolves anything, and
    the flat region is pinned separately below rather than papered over. Nothing the gate does
    depends on it: 0.5 is refused at every threshold the gate can be given.
    """
    lo, hi = min(a, b), max(a, b)
    if lo == hi:
        return
    assert saturation_ceiling() < 11
    assert executor.preflight_mde(spec_at(hi)) < executor.preflight_mde(spec_at(lo)), (lo, hi)


def test_w1_the_statistic_saturates_at_the_largest_possible_increase_for_tiny_designs() -> None:
    ceiling = saturation_ceiling()
    assert ceiling == 10, ceiling
    for n in range(2, ceiling + 1):
        assert executor.preflight_mde(spec_at(n)) == 0.5, n
    assert executor.preflight_mde(spec_at(ceiling + 1)) < 0.5
    # and every one of them is refused, so the flat region never reaches a decision
    for n in range(2, ceiling + 1):
        with pytest.raises(executor.UnderpoweredDesign):
            executor.check_power(_bare_plan(spec_at(n)), max_mde=None)


def test_w1_the_default_refuses_the_lattice_design_and_the_four_condition_design_at_n_32() -> None:
    """S23's calibration claim, asserted rather than believed: the default refuses an N=32
    design, here the lattice's 72 conditions (twelve ``gain`` by six ``load``) and the four conditions of
    ``spec_at(32)``, by the gate's own rule from the references and by ``check_power``. A default that
    passed N=32 designs would be calibrated to pass everything."""
    assert executor.DEFAULT_MAX_MDE == EXPECTED_DEFAULT
    # PF4 re-freeze (PF4.30): the gate's own rule decides, read from the references, not the
    # normal approximation at base rate 0.5.
    assert not ref_admits(LATTICE_REPLICATES, len(lattice_spec().configs), executor.DEFAULT_MAX_MDE)
    assert not ref_admits(LATTICE_REPLICATES, FOUR, executor.DEFAULT_MAX_MDE)
    for spec in (lattice_spec(), spec_at(LATTICE_REPLICATES)):
        with pytest.raises(executor.UnderpoweredDesign):
            executor.check_power(_bare_plan(spec), max_mde=None)


# ---------- W3: the comparison ----------


def test_w3_check_power_passes_below_the_threshold_and_refuses_above_it() -> None:
    spec = spec_at(LATTICE_REPLICATES)
    # PF4 re-freeze (PF4.30): the design's limit is the gate's, Fisher's test at q / M at the worst
    # base rate for the accepted change, read from the references; the normal approximation at base
    # rate 0.5 no longer decides.
    _, _, mde = ref_worst(LATTICE_REPLICATES, FOUR, executor.DEFAULT_MAX_MDE)
    assert mde is not None
    below = math.floor(mde / 2 * 1000) / 1000
    above = min(1.0, math.ceil(mde * 2 * 1000) / 1000)
    assert not ref_admits(LATTICE_REPLICATES, FOUR, below) and ref_admits(LATTICE_REPLICATES, FOUR, above), (below, above)
    p = _bare_plan(spec)
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(p, max_mde=below)
    assert executor.check_power(p, max_mde=above) is None
    # PF4 re-freeze (PF4.49): an accepted change of exactly 1 admits any design.
    assert executor.check_power(p, max_mde=1.0) is None


def test_w3_equality_passes(tmp_path: Path) -> None:
    """``>`` and not ``>=``: a design that exactly meets what the caller accepts is accepted."""
    spec = spec_at(LATTICE_REPLICATES)
    p = plan(spec, Store(tmp_path / "s"))
    # PF4 re-freeze (PF4.30): a design passes when its power at exactly the accepted change is at
    # least the target at every base rate with room, so the boundary is the smallest accepted change
    # the references admit; it passes and one step of 0.001 below it is refused.
    boundary = ref_offer(LATTICE_REPLICATES, FOUR, executor.DEFAULT_MAX_MDE)
    assert not ref_admits(LATTICE_REPLICATES, FOUR, round(boundary - 0.001, 3)), boundary
    assert executor.check_power(p, max_mde=boundary) is None
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(p, max_mde=round(boundary - 0.001, 3))


def test_w3_max_mde_none_means_the_default(tmp_path: Path) -> None:
    store = Store(tmp_path / "s")
    under = plan(spec_at(LATTICE_REPLICATES), store)
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(under, max_mde=None)
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(under)
    over = plan(spec_at(CLEARING_REPLICATES), store)
    assert executor.check_power(over, max_mde=None) is None
    assert executor.check_power(over) is None


def test_w3_underpowered_design_is_an_executor_error() -> None:
    assert issubclass(executor.UnderpoweredDesign, ExecutorError)


# PF4 re-freeze (PF4.49): --max-mde accepts (0, 1], so 1.0 left this list for 1.01 (1.0 is admitted
# in test_w3_check_power_passes_below_the_threshold_and_refuses_above_it).
@pytest.mark.parametrize("bad", [0.0, -0.1, -1.0, 1.01, 1.5, 2.0])
def test_w3_an_out_of_range_accepted_value_is_refused_by_the_executor(bad: float, tmp_path: Path) -> None:
    """M3 owns the range, exactly as M6 owns ``0 < q < 1`` -- see the module docstring."""
    p = plan(spec_at(CLEARING_REPLICATES), Store(tmp_path / "s"))
    with pytest.raises(ExecutorError):
        executor.check_power(p, max_mde=bad)


def _bare_plan(spec: SweepSpec) -> Plan:
    return Plan(
        spec=spec, run_id="w3-run", run_salt="0" * 16, backend="local",
        pairs=(), resumed=False, already_stored=0,
    )


def test_w8_the_plan_carries_the_accepted_value_the_way_it_carries_import_path() -> None:
    """The seam, pinned: a defaulted field, set at plan time, read by the runners only."""
    import dataclasses

    fields = {f.name: f for f in dataclasses.fields(Plan)}
    assert "max_mde_accepted" in fields, sorted(fields)
    assert fields["max_mde_accepted"].default is None
    assert _bare_plan(spec_at(16)).max_mde_accepted is None


# ---------- W4: the message names four facts, and its advice works ----------


def refusal_text(spec: SweepSpec, max_mde: float | None) -> str:
    p = _bare_plan(spec)
    with pytest.raises(executor.UnderpoweredDesign) as excinfo:
        executor.check_power(p, max_mde=max_mde)
    return str(excinfo.value)


def refusal(spec: SweepSpec, max_mde: float | None) -> executor.UnderpoweredDesign:
    p = _bare_plan(spec)
    with pytest.raises(executor.UnderpoweredDesign) as excinfo:
        executor.check_power(p, max_mde=max_mde)
    return excinfo.value


@pytest.mark.parametrize("replicates", [8, 16, LATTICE_REPLICATES, 64])
def test_w4_the_refusal_names_the_mde_the_accepted_value_the_n_and_a_reachable_n(replicates: int) -> None:
    spec = spec_at(replicates)
    accepted = executor.DEFAULT_MAX_MDE
    # PF4 re-freeze (PF4.30, PF4.48a): the refusal's facts are the limit at the worst base rate, that
    # base rate and the accepted change, to three decimals (`one condition alone would be flagged for
    # a change of X at its worst base rate, B, and you accept T`), all read from the references; the
    # design's N and the N that passes are the refusal's numbers, which the command line prints as
    # its `--replicates N` next: line.
    base, _, mde = ref_worst(replicates, FOUR, accepted)
    assert mde is not None
    exc = refusal(spec, accepted)
    message = str(exc)
    assert f"{mde:.3f}" in message, message
    assert f"{base:.3f}" in message, message
    assert f"{accepted:.3f}" in message, message
    assert exc.replicates == replicates, exc.replicates
    needed = exc.replicates_needed
    assert needed is not None and needed > replicates, needed
    assert ref_admits(needed, FOUR, accepted), needed
    assert not ref_admits(needed - 1, FOUR, accepted), needed
    # The offered --max-mde is the smallest three-decimal value that admits the design as it is.
    assert exc.offered == pytest.approx(ref_offer(replicates, FOUR, accepted), abs=1e-12), exc.offered


def test_w4_the_override_the_message_suggests_actually_clears_the_gate() -> None:
    """The clause that is not decoration, and the one S23's own example gets wrong.

    S23's worked message tells the reader ``--max-mde 0.3251 accepts this design as it
    stands``. It does not: the true MDE at N=32 is 0.32510999..., the pre-flight prints it to
    four decimals as 0.3251, and 0.3251 < 0.32510999 so the gate refuses again. Whatever value
    the message names as an override has to pass ``check_power`` on the same design -- round the
    suggestion up at four decimals, or print more of them.
    """
    spec = lattice_spec()
    rows = len(spec.configs)
    # PF4 re-freeze (PF4.30): the refusal's limit is printed to three decimals at the worst base rate
    # for the accepted change, and the --max-mde it offers (the command line's second next: line) is
    # the smallest three-decimal change that admits the design. Pasting the printed limit back does
    # not admit it; the offer does, and one step of 0.001 below the offer does not.
    _, _, mde = ref_worst(LATTICE_REPLICATES, rows, executor.DEFAULT_MAX_MDE)
    assert mde is not None
    exc = refusal(spec, executor.DEFAULT_MAX_MDE)
    assert f"{mde:.3f}" in str(exc), str(exc)
    offered = exc.offered
    assert offered is not None, str(exc)
    assert offered == pytest.approx(ref_offer(LATTICE_REPLICATES, rows, executor.DEFAULT_MAX_MDE), abs=1e-12)
    printed = float(f"{mde:.3f}")
    assert printed < offered and not ref_admits(LATTICE_REPLICATES, rows, printed), (printed, offered)  # the trap is real
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(_bare_plan(spec), max_mde=printed)
    assert executor.check_power(_bare_plan(spec), max_mde=offered) is None, (offered, mde, str(exc))
    assert not ref_admits(LATTICE_REPLICATES, rows, round(offered - 0.001, 3)), offered


# ---------- W5: --yes does not clear the gate, and nothing is created ----------


def test_w5_yes_does_not_clear_the_gate_and_the_store_stays_empty(tmp_path: Path) -> None:
    spec_path = write_spec(tmp_path / "under.toml", underpowered_toml())
    root = tmp_path / "runs"
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT))
    # A refusal exits 1.
    assert r.code == 1, r.text
    assert "underpowered" in r.err.lower(), r.err
    assert store_is_untouched(root), sorted(p.name for p in root.iterdir()) if root.exists() else root
    assert "Traceback" not in r.text, r.text


def test_w5_the_refusal_creates_no_manifest_even_beside_an_existing_run(tmp_path: Path) -> None:
    """The mutant this exists for fires the gate after ``create_run``, leaving a manifest behind."""
    root = tmp_path / "runs"
    good = write_spec(tmp_path / "good.toml", underpowered_toml(replicates=CLEARING_REPLICATES))
    first = run_cli(sweep_argv(root, good, MOCK_ROLLOUT))
    assert first.code == 0, first.text
    before = Store(root).runs()
    assert len(before) == 1

    bad = write_spec(tmp_path / "bad.toml", underpowered_toml())
    r = run_cli(sweep_argv(root, bad, MOCK_ROLLOUT))
    # A refusal exits 1.
    assert r.code == 1, r.text
    assert Store(root).runs() == before, Store(root).runs()


# ---------- W6: the flag ----------


def test_w6_an_accepted_value_at_or_above_the_computed_mde_proceeds(tmp_path: Path) -> None:
    spec_path = write_spec(tmp_path / "under.toml", underpowered_toml())
    root = tmp_path / "runs"
    # PF4 re-freeze (PF4.30): the computed value is the smallest accepted change the gate admits for
    # this design (the references' Fisher power at q / M at every base rate), not the normal
    # approximation at base rate 0.5.
    mde = ref_offer(SweepSpec.load(spec_path).replicates, FOUR, executor.DEFAULT_MAX_MDE)
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT, "--max-mde", repr(mde)))
    assert r.code == 0, r.text
    assert len(Store(root).runs()) == 1
    # PF4 re-freeze (PF4.49): an accepted change of exactly 1, however typed, admits any design.
    for value in ("1", "1.0"):
        again = run_cli(sweep_argv(tmp_path / f"runs-{value}", spec_path, MOCK_ROLLOUT, "--max-mde", value))
        assert again.code == 0, again.text
        assert len(Store(tmp_path / f"runs-{value}").runs()) == 1


def test_w6_an_accepted_value_below_the_computed_mde_refuses(tmp_path: Path) -> None:
    spec_path = write_spec(tmp_path / "under.toml", underpowered_toml())
    root = tmp_path / "runs"
    # PF4 re-freeze (PF4.30): below the smallest accepted change the gate admits, by one step of 0.001.
    mde = ref_offer(SweepSpec.load(spec_path).replicates, FOUR, executor.DEFAULT_MAX_MDE)
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT, "--max-mde", repr(round(mde - 0.001, 3))))
    # A refusal exits 1.
    assert r.code == 1, r.text
    assert store_is_untouched(root)


@pytest.mark.parametrize("value", ["nope", "", "0.5.1"])
def test_w6_a_non_float_is_refused_at_exit_two_with_nothing_written(value: str, tmp_path: Path) -> None:
    spec_path = write_spec(tmp_path / "under.toml", underpowered_toml())
    root = tmp_path / "runs"
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT, "--max-mde", value))
    assert r.code == 2, r.text
    assert store_is_untouched(root)


# PF4 re-freeze (PF4.49): --max-mde accepts (0, 1], so "1" and "1.0" left this list for "1.01" and
# "1.001" (they are admitted in test_w6_an_accepted_value_at_or_above_the_computed_mde_proceeds).
@pytest.mark.parametrize("value", ["0", "0.0", "-0.2", "1.01", "1.001", "1.5"])
def test_w6_a_value_outside_the_open_unit_interval_is_refused_with_nothing_written(value: str, tmp_path: Path) -> None:
    spec_path = write_spec(tmp_path / "clear.toml", underpowered_toml(replicates=CLEARING_REPLICATES))
    root = tmp_path / "runs"
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT, "--max-mde", value))
    # A refusal exits 1.
    assert r.code == 1, r.text
    assert store_is_untouched(root), Store(root).runs()


# ---------- W7: the gate is ordered after the description ----------


def test_w7_the_refusal_follows_the_complete_preflight_block_on_stdout(tmp_path: Path) -> None:
    """A reader who gets the refusal has already been shown the number it is about.

    The mutant this exists for runs the gate before the pre-flight is written, so the reader is
    told the design is underpowered and never shown the MDE line, the cell count or the cost.
    """
    spec_path = write_spec(tmp_path / "under.toml", underpowered_toml())
    root = tmp_path / "runs"
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT))
    # A refusal exits 1.
    assert r.code == 1, r.text
    spec = SweepSpec.load(spec_path)
    for token in ("Sweep:", "Backend: local", "Cost:", f"N={spec.replicates}"):
        assert token in r.out, (token, r.out)
    # PF4 re-freeze (PF4.22): the plan no longer prints the normal approximation's
    # `MDE at N=... (base rate 0.5)` line; the number the refusal is about is the gate's limit at the
    # worst base rate, on the refusal's own error line, to three decimals (rule 10), from the
    # references.
    assert not MDE_LINE.search(r.out), r.out
    base, _, limit = ref_worst(spec.replicates, FOUR, executor.DEFAULT_MAX_MDE)
    assert limit is not None
    (error,) = [line for line in r.err.splitlines() if line.startswith("error: ")]
    assert f"{limit:.3f}" in error and f"{base:.3f}" in error, error
    assert "underpowered" in r.err.lower() and "underpowered" not in r.out.lower(), r.text


# ---------- W8: the accepted value is recorded, on both backends ----------


def test_w8_a_launched_local_run_records_the_accepted_value(tmp_path: Path) -> None:
    spec_path = write_spec(tmp_path / "under.toml", underpowered_toml())
    root = tmp_path / "runs"
    # PF4 re-freeze (PF4.30): the accepted value is the smallest the gate admits for this design,
    # from the references, where it was the normal approximation rounded up.
    replicates = SweepSpec.load(spec_path).replicates
    accepted = ref_offer(replicates, FOUR, executor.DEFAULT_MAX_MDE)
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT, "--max-mde", repr(accepted)))
    assert r.code == 0, r.text
    environment = Store(root).manifest(run_id_of(root)).environment
    assert environment["max_mde_accepted"] == pytest.approx(accepted)
    # PF4 re-freeze (PF4.30, PF4.48a): the run also records the gate's design limit for that value.
    assert_design_recorded(environment["design_mde"], n=replicates, rows=FOUR, accepted=accepted)


def test_w8_a_run_that_clears_the_default_records_the_default(tmp_path: Path) -> None:
    spec_path = write_spec(tmp_path / "clear.toml", underpowered_toml(replicates=CLEARING_REPLICATES))
    root = tmp_path / "runs"
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT))
    assert r.code == 0, r.text
    environment = Store(root).manifest(run_id_of(root)).environment
    assert environment["max_mde_accepted"] == pytest.approx(executor.DEFAULT_MAX_MDE)


def test_w8_the_modal_path_records_it_too(tmp_path: Path) -> None:
    """The one likely to be missed: both backends build ``environment`` separately."""
    store = Store(tmp_path / "runs")
    spec = spec_at(CLEARING_REPLICATES, cells=2, target_id="mock-agent@v0")
    accepted = 0.25
    p = plan(
        spec, store, backend="modal", import_path=MOCK_ROLLOUT, max_mde_accepted=accepted
    )
    run_with_mapper(p, in_process_mapper, store, options=ModalOptions(batch_size=8))
    assert store.manifest(p.run_id).environment["max_mde_accepted"] == pytest.approx(accepted)
    # PF4 re-freeze (PF4.30): design_mde is recorded on every backend, the modal path included.
    assert_design_recorded(store.manifest(p.run_id).environment["design_mde"], n=CLEARING_REPLICATES, rows=2,
                           accepted=accepted)


def test_w8_the_other_environment_keys_are_unchanged_and_no_manifest_field_is_added(tmp_path: Path) -> None:
    import dataclasses

    spec_path = write_spec(tmp_path / "clear.toml", underpowered_toml(replicates=CLEARING_REPLICATES))
    root = tmp_path / "runs"
    r = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT))
    assert r.code == 0, r.text
    environment = Store(root).manifest(run_id_of(root)).environment
    assert {"python", "platform", "poisson_prove_version", "sweep", "import_path"} <= set(environment)
    assert "max_mde_accepted" in environment
    # PF4 re-freeze (PF4.30): new runs also record the gate's design limit, in environment, not as a
    # manifest field.
    assert "design_mde" in environment
    assert_design_recorded(environment["design_mde"], n=CLEARING_REPLICATES, rows=FOUR, accepted=executor.DEFAULT_MAX_MDE)
    fields = {f.name for f in dataclasses.fields(RunManifest)}
    assert "max_mde_accepted" not in fields, sorted(fields)


# ---------- W9: a resume inherits; a pair does not ----------


def launched_underpowered(root: Path, spec_path: Path, accepted: float, *extra: str) -> Result:
    return run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT, "--max-mde", repr(accepted), *extra))


def test_w9_a_resume_inherits_the_accepted_value_without_the_flag(tmp_path: Path) -> None:
    spec_path = write_spec(tmp_path / "under.toml", underpowered_toml())
    root = tmp_path / "runs"
    spec = SweepSpec.load(spec_path)
    # PF4 re-freeze (PF4.30): the smallest accepted change the gate admits, from the references.
    accepted = ref_offer(spec.replicates, FOUR, executor.DEFAULT_MAX_MDE)
    first = launched_underpowered(root, spec_path, accepted, "--max-rollouts", "4")
    # A sweep stopped by --max-rollouts exits 3.
    assert first.code == 3, first.text
    run_id = run_id_of(root)

    resumed = run_cli(sweep_argv(root, spec_path, MOCK_ROLLOUT, "--resume", run_id))
    assert resumed.code == 0, resumed.text
    assert Store(root).manifest(run_id).status == "complete"


def test_w9_a_resume_is_refused_when_the_recorded_value_no_longer_covers_the_design(tmp_path: Path) -> None:
    """A resumed run's spec may differ: ``plan`` checks target_id, t_unit and axis_types, never
    ``replicates``. So the recorded value is compared against the *current* design."""
    root = tmp_path / "runs"
    started = write_spec(tmp_path / "a.toml", underpowered_toml(replicates=64))
    # PF4 re-freeze (PF4.30): the accepted change and whether it still covers the design are the
    # gate's rule, read from the references.
    accepted = ref_offer(64, FOUR, executor.DEFAULT_MAX_MDE)
    first = launched_underpowered(root, started, accepted, "--max-rollouts", "4")
    # A sweep stopped by --max-rollouts exits 3.
    assert first.code == 3, first.text
    run_id = run_id_of(root)

    grown = write_spec(tmp_path / "b.toml", underpowered_toml(replicates=8))
    assert not ref_admits(SweepSpec.load(grown).replicates, FOUR, accepted)
    resumed = run_cli(sweep_argv(root, grown, MOCK_ROLLOUT, "--resume", run_id))
    # A refusal exits 1.
    assert resumed.code == 1, resumed.text
    assert "underpowered" in resumed.err.lower(), resumed.err


def test_w9_pair_with_does_not_inherit(tmp_path: Path) -> None:
    """A paired arm is a different run making its own claim, and the flag is one word."""
    spec_path = write_spec(tmp_path / "under.toml", underpowered_toml())
    root = tmp_path / "runs"
    # PF4 re-freeze (PF4.30): under --pair-with the gate asks the paired test with independent arms,
    # its pairs the earlier run's replicates, so the accepted change is the larger of the two tests'
    # smallest admitted values: the first run is admitted by it, and so is the pair once the flag is
    # typed, which is what makes "does not inherit" a fact about inheritance.
    replicates = SweepSpec.load(spec_path).replicates
    accepted = max(ref_offer(replicates, FOUR, executor.DEFAULT_MAX_MDE),
                   ref_offer(replicates, FOUR, executor.DEFAULT_MAX_MDE, test="mcnemar"))
    first = launched_underpowered(root, spec_path, accepted)
    assert first.code == 0, first.text
    run_a = run_id_of(root)

    paired = run_cli(sweep_argv(root, spec_path, MOCK_PATCHED, "--pair-with", run_a))
    # A refusal exits 1.
    assert paired.code == 1, paired.text
    assert "underpowered" in paired.err.lower(), paired.err
    assert Store(root).runs() == [run_a], Store(root).runs()

    with_flag = run_cli(sweep_argv(root, spec_path, MOCK_PATCHED, "--pair-with", run_a, "--max-mde", repr(accepted)))
    assert with_flag.code == 0, with_flag.text


# ---------- W10: the label no longer claims a worst case ----------


def test_w10_both_preflights_say_base_rate_and_neither_says_worst_case(tmp_path: Path) -> None:
    """The label S23 says three frozen test files pinned. None of them did -- see the module
    docstring, finding 1 -- so this is the only guard it has."""
    from poisson_prove.executor_modal import ImageSpec, ModalTarget

    spec = spec_at(LATTICE_REPLICATES, cells=2)
    p = plan(spec, Store(tmp_path / "s"))
    local = preflight(p)
    modal = preflight_modal(
        plan(spec, Store(tmp_path / "s2"), backend="modal"),
        ModalTarget(import_path=MOCK_ROLLOUT, image=ImageSpec()),
        ModalOptions(),
    )
    for text in (local, modal):
        # PF4 re-freeze (PF4.22): neither pre-flight block prints a limit; the
        # normal approximation's `MDE at N=... (base rate 0.5)` line is gone.
        assert not MDE_LINE.search(text) and "MDE at N=" not in text, text
        assert "worst case" not in text, text
    # PF4 re-freeze (PF4.30): the plan's one limit is the command line's gate line, and
    # it names the limit at the worst base rate, that base rate, the test and the family; the
    # numbers are the references'.
    spec_path = write_spec(tmp_path / "plan.toml", underpowered_toml(replicates=LATTICE_REPLICATES))
    accepted = ref_offer(LATTICE_REPLICATES, FOUR, executor.DEFAULT_MAX_MDE)
    r = run_cli(sweep_argv(tmp_path / "runs", spec_path, MOCK_ROLLOUT, "--max-mde", repr(accepted), "--dry-run"))
    assert r.code == 0, r.text
    base, _, limit = ref_worst(LATTICE_REPLICATES, FOUR, accepted)
    assert limit is not None
    (line,) = [x for x in r.out.splitlines() if "worst base rate" in x]
    assert f"{limit:.3f}" in line and f"{base:.3f}" in line and "Fisher" in line and "over 4 tests" in line, line


# ---------- W11: the gate decides and does nothing else ----------


def test_w11_check_power_prints_nothing_on_either_path(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    store = Store(tmp_path / "s")
    assert executor.check_power(plan(spec_at(CLEARING_REPLICATES), store), max_mde=executor.DEFAULT_MAX_MDE) is None
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(plan(spec_at(LATTICE_REPLICATES), store), max_mde=executor.DEFAULT_MAX_MDE)
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", ""), captured


def test_w11_check_power_touches_neither_the_store_nor_the_plan(tmp_path: Path) -> None:
    import dataclasses

    root = tmp_path / "s"
    store = Store(root)
    p = plan(spec_at(LATTICE_REPLICATES), store)
    before = dataclasses.asdict(p)
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(p, max_mde=executor.DEFAULT_MAX_MDE)
    assert dataclasses.asdict(p) == before
    assert store_is_untouched(root)


def test_w11_the_preflights_still_return_text_and_still_raise_nothing(tmp_path: Path) -> None:
    """They describe; the gate decides. An underpowered design still renders its block."""
    p = plan(spec_at(LATTICE_REPLICATES, cells=2), Store(tmp_path / "s"))
    text = preflight(p)
    assert isinstance(text, str) and text.endswith("\n") and "Sweep:" in text


# ---------- W12: golden, on the lattice's design and on a design that clears ----------


def test_w12_the_lattice_design_passes_at_its_own_mde_and_not_at_the_printed_rounding() -> None:
    """Both halves come from ``preflight_mde``. The second is S23's example, and it
    is wrong: ``--max-mde 0.3251`` is what the message tells the reader to paste and it refuses.
    See ``test_w4_the_override_the_message_suggests_actually_clears_the_gate``."""
    spec = lattice_spec()
    rows = len(spec.configs)
    # PF4 re-freeze (PF4.30): the design's own value is the smallest accepted change the gate admits
    # (the references' Fisher power at q / 72 at every base rate); the printed limit at the worst
    # base rate, rounded to three decimals, is below it and refused.
    own = ref_offer(LATTICE_REPLICATES, rows, executor.DEFAULT_MAX_MDE)
    _, _, mde = ref_worst(LATTICE_REPLICATES, rows, executor.DEFAULT_MAX_MDE)
    assert mde is not None
    assert executor.check_power(_bare_plan(spec), max_mde=own) is None
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(_bare_plan(spec), max_mde=float(f"{mde:.3f}"))
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(_bare_plan(spec), max_mde=round(own - 0.001, 3))


def test_w12_a_design_at_the_clearing_replicate_count_passes_at_the_default() -> None:
    spec = spec_at(CLEARING_REPLICATES)
    # PF4 re-freeze (PF4.30): the clearing count is checked against the gate's rule from the references.
    assert ref_admits(CLEARING_REPLICATES, FOUR, executor.DEFAULT_MAX_MDE)
    assert executor.check_power(_bare_plan(spec), max_mde=None) is None


def test_w12_the_rebalanced_quickstart_clears_its_own_gate_with_no_flag() -> None:
    """S23's acceptance clause, and the reason the grid was rebalanced before the build rather
    than teaching a stranger to pass an override on the first command they ever run."""
    # PF4 re-freeze (PF4.30): the packaged quickstart (194 replicates, its two failures
    # declared, 9 conditions by 2 events) clears the default with no flag; its design at the 100
    # replicates this file was frozen at, nothing declared (nine rows), is refused at the default and
    # admitted at --max-mde 0.3. Both decisions are read from the references.
    packaged = SweepSpec.load(PACKAGED_QUICKSTART)
    assert len(packaged.configs) == 9
    assert ref_admits(packaged.replicates, 9 * 2, executor.DEFAULT_MAX_MDE), packaged.replicates
    assert executor.check_power(_bare_plan(packaged), max_mde=None) is None
    spec = SweepSpec.load(QUICKSTART)
    assert not ref_admits(spec.replicates, len(spec.configs), executor.DEFAULT_MAX_MDE)
    assert ref_admits(spec.replicates, len(spec.configs), QUICKSTART_MAX_MDE)
    with pytest.raises(executor.UnderpoweredDesign):
        executor.check_power(_bare_plan(spec), max_mde=None)
    assert executor.check_power(_bare_plan(spec), max_mde=QUICKSTART_MAX_MDE) is None
