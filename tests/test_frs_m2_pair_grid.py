"""First run M2, Z4 -- the pair is never refused for size (#6). One property, over a grid, in the math
suite.

**The property.** Take a design the gate refuses, and the replicates its refusal offers (the number the
command line prints as ``next: ... --replicates N``). A first sweep at that N is accepted. Then a sweep
of the same spec at the same N, paired with that first run, is accepted too. Before 0.5.0 the first
half held and the second did not: the first sweep was read with Fisher's test alone and the paired one
with the paired test, which can need more.

**The grid** is the First Run Spec's (section 3.2, Z4): conditions 1 to 24, declared events 1 to 4,
accepted changes 0.05 to 0.40 in steps of 0.05, and for each the N the gate itself offers when asked
from 2 replicates. 768 designs.

**What it costs, and where each part runs.** The gate's readings are exact, so a design's cost grows
with the square of its replicates, and the replicates grow as the accepted change shrinks: a design at
0.40 (about 50 replicates a side) takes a second or two, one at 0.05 (1,600 to 3,800 a side) about two
minutes. Measured on a 16-core Mac with other test runs on it, the whole grid is about 4.9 hours of
test time: 3.3 hours for the 96 designs at 0.05, 45 minutes for those at 0.10, and 3 to 7 minutes for
each of the other six accepted changes. So:

- 0.35 and 0.40 (192 designs) run in the math lane, on every pull request that changes the statistics
  or a math test;
- 0.15 to 0.30 (384 designs) are marked ``slow`` and run nightly with the other slow math tests;
- 0.05 and 0.10 (192 designs) are marked ``slow`` and also wait for ``POISSON_PROVE_FULL_GRID=1``: no
  lane has room for them, so they are run by hand, before a release and when the gate changes.

**How the pair is made.** With no sweep: the first run is a run record in a store whose
``environment.sweep.replicates`` is N, which is what a sweep writes and what ``plan(..., pair_with=)``
reads. Nothing is called and nothing is estimated.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import poisson_prove.executor as executor
from poisson_prove.executor import plan
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import RunManifest, Store

pytestmark = pytest.mark.math

CONDITIONS = range(1, 25)
EVENTS = range(1, 5)
ACCEPTED = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40)
#: At or below this accepted change a design is ``slow``: nightly, not on a pull request.
SLOW_AT_OR_BELOW = 0.30
#: At or below this one it also waits to be asked for by hand.
BY_HAND_AT_OR_BELOW = 0.10
FULL_GRID = "POISSON_PROVE_FULL_GRID"
by_hand = pytest.mark.skipif(
    os.environ.get(FULL_GRID) != "1",
    reason=f"about two hours of processor time a column; set {FULL_GRID}=1 to run the designs at 0.05 and 0.10",
)


def _marks(accepted: float) -> list[pytest.MarkDecorator]:
    marks: list[pytest.MarkDecorator] = []
    if accepted <= SLOW_AT_OR_BELOW + 1e-9:
        marks.append(pytest.mark.slow)
    if accepted <= BY_HAND_AT_OR_BELOW + 1e-9:
        marks.append(by_hand)
    return marks


GRID = [
    pytest.param(conditions, events, accepted, id=f"{conditions}x{events}-at-{accepted:.2f}", marks=_marks(accepted))
    for accepted in ACCEPTED for events in EVENTS for conditions in CONDITIONS
]


def test_z4_the_grid_is_the_specs() -> None:
    """Every design of the grid is here, whichever lane runs it."""
    assert len(GRID) == 24 * 4 * 8 == 768
    cut = [(sum(1 for case in GRID if len(case.marks) == n)) for n in (0, 1, 2)]
    assert cut == [192, 384, 192], cut


def spec_of(folder: Path, conditions: int, events: int, replicates: int) -> SweepSpec:
    path = folder / f"spec-{replicates}.toml"
    path.write_text(
        'target_id = "grid"\n'
        't_unit = "steps"\n'
        f"replicates = {replicates}\n\n"
        "[axes.condition]\n"
        'type = "categorical"\n'
        f"values = {json.dumps([f'c{i}' for i in range(conditions)])}\n\n"
        "[declare]\n"
        f"failures = {json.dumps([f'e{i}' for i in range(events)])}\n",
        encoding="utf-8",
    )
    return SweepSpec.load(path)


@pytest.mark.parametrize("conditions,events,accepted", GRID)
def test_z4_a_first_sweep_at_the_replicates_the_gate_offers_can_always_be_paired(
    conditions: int, events: int, accepted: float, tmp_path: Path
) -> None:
    store = Store(tmp_path / "runs")
    asked = spec_of(tmp_path, conditions, events, 2)
    assert len(asked.configs) == conditions
    with pytest.raises(executor.UnderpoweredDesign) as refused:
        executor.check_power(plan(asked, store), max_mde=accepted)
    offered = refused.value.replicates_needed
    assert offered is not None and offered > 2, offered

    sized = spec_of(tmp_path, conditions, events, offered)
    first = plan(sized, store)
    assert executor.check_power(first, max_mde=accepted) is None, f"the gate refuses the {offered} it offered"

    store.create_run(RunManifest(
        run_id="first", target_id=sized.target_id, t_unit=sized.t_unit, run_salt=first.run_salt,
        axis_types=dict(sized.axis_types), backend="local", environment={"sweep": {"replicates": offered}},
    ))
    paired = plan(sized, store, pair_with="first")
    assert paired.run_salt == first.run_salt
    assert executor.check_power(paired, max_mde=accepted) is None, (
        f"a sweep of {offered} replicates paired with a first sweep of {offered} is refused"
    )
