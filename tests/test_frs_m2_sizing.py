"""First run M2 -- the first sweep is sized for the paired comparison (#6): the frozen tests for Z1 to
Z3 and Z5 to Z8 (First Run Spec section 3). Z4, the grid, is ``test_frs_m2_pair_grid.py`` in the math
suite.

**What M2 is for.** A sweep paired with nothing used to be read with Fisher's test alone, and the sweep
paired with it afterwards with the paired test, which can need more replicates. So a first sweep sized
by the plan's own ``next:`` line could be followed by a paired sweep the plan refused. From 0.5.0 a
sweep that is neither paired nor resumed is read both ways and passes only when both readings do.

**Where the expected numbers come from.** Never from the code under test: every limit, base rate,
replicate count and accepted change is read from the references the power-gate tests keep
(``test_s23_power.ref_admits`` and its neighbours, which stand on ``test_pf4_stats``).

**The designs.** Small ones, so a whole sweep is a few hundred calls of the keyless mock agent. Two
tasks by two failure rates with one declared failure is four tests; at an accepted change of 0.4
Fisher's reading passes from 37 replicates and the paired reading from 40, and at 20 neither does.
One condition with one failure at the default 0.2 is the mirror: at 107 the paired reading passes
and Fisher's does not. Each test checks those facts against the references before using them.

**What a refusal is pinned by.** Its exit code, the reading it names, its numbers, its ``next:``
lines as commands, and what happens when each is typed. Not its sentences.
"""

from __future__ import annotations

import functools
import importlib.machinery
import importlib.util
import json
import math
import re
import shlex
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from pf6_support import run_pty, says, strip_escapes
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import Store
from rb_cloud_support import CloudWorld, Pool, cloud_table, world
from test_pf4_stats import ref_fisher_power, ref_limit, ref_paired_power
from test_s23_power import MOCK_ROLLOUT, POWER, Q, Result, ref_offer, ref_offer_both, run_cli

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
COMMAND = "poisson-prove"

#: The accepted change the four-test design is planned at, and how it is typed.
ACCEPTED = 0.4
LOOSE = ("--max-mde", "0.4")
#: Four tests at 0.4: Fisher's reading alone passes, both pass, neither passes.
FISHER_ONLY, BOTH, NEITHER = 37, 40, 20
#: One test at the default 0.2: the paired reading alone passes.
PAIRED_ONLY = 107

PAIRED_LINE = "and in a sweep paired with this one"
FISHER_LINE = "smallest"
DESIGN_KEYS = {"mde", "base_rate", "direction", "test", "level", "family", "conditions", "events", "q",
               "power", "flaggable"}


# ---------- the gate's rule, from the stats file's references ----------
#
# The power-gate tests' own references (``test_s23_power.ref_admits`` and ``ref_worst``) build, for
# Fisher's reading, a table over every accepted change, which costs tens of seconds at the replicates
# a passing design needs. These read one accepted change at a time, by the same rule.


@functools.cache
def _powers(n: int, rows: int, accepted: float, test: str) -> tuple[tuple[float, str, float], ...]:
    """For each base rate on the 0.005 grid and each way with room for ``accepted`` (a rise first),
    the reading's power at exactly ``accepted``, at level q / rows (PF4.30)."""
    level = Q / rows
    change = np.array([accepted])
    out: list[tuple[float, str, float]] = []
    for base in np.round(np.arange(0.0, 1.0 + 1e-9, 0.005), 3):
        for way in ("rise", "fall"):
            room = 1 - base if way == "rise" else base
            if accepted > room + 1e-9:
                continue
            if test == "fisher":
                power = ref_fisher_power(float(base), n, n, level, change, way == "rise")[0]
            else:
                power = ref_paired_power(float(base), n, level, change, way == "rise")[0]
            out.append((float(base), way, float(power)))
    return tuple(out)


def ref_admits(n: int, rows: int, accepted: float, test: str = "fisher") -> bool:
    """A reading admits a design when its power at exactly ``accepted`` reaches the target at every
    base rate with room."""
    return all(power >= POWER for _, _, power in _powers(n, rows, accepted, test))


def ref_admits_both(n: int, rows: int, accepted: float) -> bool:
    return ref_admits(n, rows, accepted) and ref_admits(n, rows, accepted, test="mcnemar")


def ref_worst(n: int, rows: int, accepted: float, test: str = "fisher") -> tuple[float, str, float | None]:
    """The worst base rate at exactly ``accepted`` (ties within 1e-12 to the lower base rate, a rise
    first; PF4.48a), the way the change goes there, and the reading's limit that way at that base rate."""
    worst = (2.0, 0.0, "rise")
    for base, way, power in _powers(n, rows, accepted, test):
        if power < worst[0] - 1e-12:
            worst = (power, base, way)
    _, base, way = worst
    level = Q / rows
    room = 1 - base if way == "rise" else base
    if test == "fisher":
        return base, way, ref_limit(lambda g: ref_fisher_power(base, n, n, level, g, way == "rise"), room)
    return base, way, ref_limit(lambda g: ref_paired_power(base, n, level, g, way == "rise"), room)


def ref_named(n: int, rows: int, accepted: float) -> tuple[str, float, str, float | None]:
    """The reading a refusal names: the paired one when it fails, else Fisher's."""
    test = "fisher" if ref_admits(n, rows, accepted, test="mcnemar") else "mcnemar"
    return (test, *ref_worst(n, rows, accepted, test))


# ---------- helpers ----------


def spec_toml(replicates: int, *, tasks: Sequence[str] = ("search", "refund"), rates: Sequence[float] = (0.3, 0.55),
              failures: Sequence[str] = ("violated",), target_id: str = "sized") -> str:
    """The keyless mock agent over ``tasks`` by ``rates``, its ``failures`` declared: the conditions
    times the failures are the tests a comparison will make."""
    return (
        f'target = "{MOCK_ROLLOUT}"\n'
        f'target_id = "{target_id}"\n'
        't_unit = "tool_calls"\n'
        f"replicates = {replicates}\n\n"
        "[axes.task_id]\n"
        'type = "categorical"\n'
        f"values = {json.dumps(list(tasks))}\n\n"
        "[axes.tool_fail_rate]\n"
        'type = "continuous"\n'
        f"values = {json.dumps(list(rates))}\n\n"
        "[declare]\n"
        f"failures = {json.dumps(list(failures))}\n"
    )


class Folder:
    """One test's folder: a spec, a store, and the command line run in this process."""

    def __init__(self, tmp_path: Path, replicates: int, **spec: Any) -> None:
        self.root = tmp_path / "runs"
        self.spec = tmp_path / "prove.toml"
        self.write(replicates, **spec)

    def write(self, replicates: int, **spec: Any) -> None:
        self.spec.write_text(spec_toml(replicates, **spec), encoding="utf-8")

    def sweep(self, *args: str) -> Result:
        return run_cli(["--store", str(self.root), "sweep", str(self.spec), *args])

    def follow(self, command: Sequence[str]) -> Result:
        """A ``next:`` line typed as it was printed."""
        assert command[0] == COMMAND, command
        return run_cli(list(command[1:]))

    def runs(self) -> list[str]:
        return Store(self.root).runs()

    def manifest(self, run_id: str) -> dict[str, Any]:
        return json.loads((self.root / run_id / "manifest.json").read_text(encoding="utf-8"))


def nexts(r: Result) -> list[str]:
    return [line[len("  next: "):] for line in r.err.splitlines() if line.startswith("  next: ")]


def commands(r: Result) -> list[list[str]]:
    """The ``next:`` lines that are commands, split as a shell would."""
    return [shlex.split(line) for line in nexts(r) if line.startswith(COMMAND + " ")]


def option(words: Sequence[str], name: str) -> str | None:
    return words[words.index(name) + 1] if name in words else None


def error_line(r: Result) -> str:
    (line,) = [x for x in r.err.splitlines() if x.startswith("error: ")]
    return line


def design_lines(out: str) -> list[str]:
    """The plan's lines that state a detection limit, in the order printed."""
    return [line.strip() for line in out.splitlines() if "worst base rate" in line]


def refused_for_size(r: Result) -> bool:
    return r.code != 0 and ("underpowered" in r.err or "can be flagged" in r.err)


def assert_states(line: str, *, limit: float | None, base: float, accepted: float | None = None) -> None:
    assert limit is not None
    assert f"{limit:.3f}" in line and f"{base:.3f}" in line, (line, limit, base)
    if accepted is not None:
        assert f"{accepted:.3f}" in line, (line, accepted)


def the_four_test_design_is_what_the_file_says() -> None:
    """The three replicate counts of the four-test design, from the references."""
    assert ref_admits(FISHER_ONLY, 4, ACCEPTED) and not ref_admits(FISHER_ONLY, 4, ACCEPTED, test="mcnemar")
    assert ref_admits_both(BOTH, 4, ACCEPTED) and not ref_admits_both(BOTH - 1, 4, ACCEPTED)
    assert not ref_admits(NEITHER, 4, ACCEPTED) and not ref_admits(NEITHER, 4, ACCEPTED, test="mcnemar")


@pytest.fixture
def folder(tmp_path: Path) -> Folder:
    the_four_test_design_is_what_the_file_says()
    return Folder(tmp_path, BOTH)


# ---------- Z1: both readings gate a sweep paired with nothing ----------


@pytest.mark.parametrize("replicates", [FISHER_ONLY, NEITHER], ids=["the paired reading alone fails", "both fail"])
def test_z1_a_design_the_paired_reading_cannot_pass_is_refused_naming_that_reading(replicates: int, folder: Folder) -> None:
    """Z1 and Z3. ``--replicates`` on the command line is gated as the spec's own count is. When both
    readings fail the refusal is still the paired one's, the larger need."""
    r = folder.sweep("--replicates", str(replicates), "--yes", *LOOSE)
    assert r.code == 1, r.text
    assert folder.runs() == [], "a refused sweep ran"
    test, base, _, limit = ref_named(replicates, 4, ACCEPTED)
    assert test == "mcnemar"
    error = error_line(r)
    assert "paired" in error, error
    assert_states(error, limit=limit, base=base, accepted=ACCEPTED)
    if replicates == NEITHER:
        # Fisher's own limit at this count is another number, and it is not the one named.
        _, _, fisher_limit = ref_worst(replicates, 4, ACCEPTED)
        assert fisher_limit is not None and f"{fisher_limit:.3f}" != f"{limit:.3f}"
        assert f"{fisher_limit:.3f}" not in error, error


def test_z1_a_design_only_fishers_reading_cannot_pass_is_refused_with_fishers_sentence(tmp_path: Path) -> None:
    """Z1 and Z3: the mirror. One test at the default 0.2 and 107 replicates: the paired reading passes,
    Fisher's does not, and the refusal is the one a sweep has always printed for it."""
    assert ref_admits(PAIRED_ONLY, 1, 0.2, test="mcnemar") and not ref_admits(PAIRED_ONLY, 1, 0.2)
    one = Folder(tmp_path, PAIRED_ONLY, tasks=("search",), rates=(0.3,))
    r = one.sweep("--yes")
    assert r.code == 1, r.text
    assert one.runs() == []
    base, _, limit = ref_worst(PAIRED_ONLY, 1, 0.2)
    error = error_line(r)
    assert "one condition alone would be flagged for a change of" in error, error
    assert "paired" not in error, error
    assert_states(error, limit=limit, base=base, accepted=0.2)


# ---------- Z2: the plan carries both readings ----------


def test_z2_the_plan_prints_fishers_line_then_the_paired_one(folder: Folder) -> None:
    """Z2, and section 3.3's one sentence: the paired line says the plan needs no pilot run."""
    r = folder.sweep("--dry-run", *LOOSE)
    assert r.code == 0, r.text
    lines = r.out.splitlines()
    (at,) = [i for i, line in enumerate(lines) if line.strip().startswith(FISHER_LINE) and "worst base rate" in line]
    first, second = lines[at].strip(), lines[at + 1].strip()
    assert design_lines(r.out) == [first, second], r.out
    base, _, limit = ref_worst(BOTH, 4, ACCEPTED)
    assert "Fisher" in first and "over 4 tests" in first, first
    assert_states(first, limit=limit, base=base, accepted=ACCEPTED)
    assert second.startswith(PAIRED_LINE), second
    base, _, limit = ref_worst(BOTH, 4, ACCEPTED, test="mcnemar")
    assert "paired test" in second and "over 4 tests" in second and "4 times in 5" in second, second
    assert_states(second, limit=limit, base=base)
    assert "pilot" in second, second


def test_z2_a_terminal_is_shown_both_lines(folder: Folder, tmp_path: Path) -> None:
    """Z2, pretty: on a terminal the plan draws the facts the plain plan prints."""
    plain = folder.sweep("--dry-run", *LOOSE)
    assert plain.code == 0, plain.text
    home = tmp_path / "home"
    home.mkdir()
    pretty = run_pty(["--store", str(folder.root), "sweep", str(folder.spec), "--dry-run", *LOOSE], home=home,
                     cwd=tmp_path, stdin="null", stdout="pty", stderr="own", cols=240, rows=60)
    assert pretty.code == 0, pretty.err
    screen = strip_escapes(pretty.out)
    first, second = design_lines(plain.out)
    for line in (first, second):
        label, _, value = line.partition("  ")
        assert says(screen, label) and says(screen, value), (line, screen[-3000:])


def test_z2_json_carries_the_paired_reading_beside_the_design_with_the_same_keys(folder: Folder) -> None:
    """Z2 and FRS-8: ``design_paired`` is the paired reading as ``design_mde`` is Fisher's."""
    r = folder.sweep("--dry-run", "--json", *LOOSE)
    assert r.code == 0, r.text
    doc = json.loads(r.out)
    fisher, paired = doc["design_mde"], doc["design_paired"]
    assert set(fisher) == set(paired) == DESIGN_KEYS, (sorted(fisher), sorted(paired))
    assert (fisher["test"], paired["test"]) == ("fisher", "mcnemar")
    base, way, limit = ref_worst(BOTH, 4, ACCEPTED, test="mcnemar")
    assert limit is not None
    assert (paired["base_rate"], paired["direction"]) == (base, way), paired
    assert abs(paired["mde"] - limit) <= 1e-4 + 1e-12, (paired, limit)
    assert (paired["family"], paired["conditions"], paired["events"]) == (4, 4, 1), paired
    assert abs(paired["level"] - Q / 4) <= 1e-15 and paired["q"] == Q and paired["power"] == 0.8, paired
    assert paired["flaggable"] is True


def test_z2_a_design_accepted_whole_says_when_the_paired_reading_can_flag_nothing(folder: Folder) -> None:
    """``--max-mde 1`` admits any design. At 7 replicates over four tests Fisher's reading can still
    flag a lone condition and the paired one cannot: the plan runs, and says so in ``design_paired``."""
    level = Q / 4
    assert 2 * 0.5 ** 7 >= level > 2 / math.comb(14, 7)
    r = folder.sweep("--replicates", "7", "--dry-run", "--json", "--max-mde", "1")
    assert r.code == 0, r.text
    doc = json.loads(r.out)
    assert doc["design_mde"]["flaggable"] is True
    assert doc["design_paired"]["flaggable"] is False and doc["design_paired"]["mde"] is None, doc["design_paired"]


# ---------- Z3: the refusal's next lines ----------


#: The harder reading of a refused design: what is typed, the tests, the accepted change, the
#: replicates the refusal offers, and the reading that alone would have offered a smaller change.
HARDER: dict[str, dict[str, Any]] = {
    "the paired reading is the harder": dict(typed=FISHER_ONLY, rows=4, accepted=ACCEPTED, more=BOTH, easier="fisher"),
    "Fisher's reading is the harder": dict(typed=PAIRED_ONLY, rows=1, accepted=0.2, more=PAIRED_ONLY + 1, easier="mcnemar"),
}


@pytest.mark.parametrize("case", HARDER)
def test_z3_each_next_of_the_refusal_is_the_smallest_that_passes_both_and_passes_when_typed(case: str, tmp_path: Path) -> None:
    """Z3. The replicates offered pass both readings and one fewer does not; the accepted change
    offered admits both and one step of 0.001 below it does not; each command passes when typed.
    Once where the paired reading is the harder of the two and once where Fisher's is."""
    made = HARDER[case]
    typed, rows, accepted = made["typed"], made["rows"], made["accepted"]
    shape: dict[str, Any] = dict(tasks=("search",), rates=(0.3,)) if rows == 1 else {}
    loose = ("--max-mde", f"{accepted:g}")
    folder = Folder(tmp_path, typed, **shape)
    r = folder.sweep("--replicates", str(typed), "--dry-run", *loose)
    assert r.code == 1, r.text
    more, wider = commands(r)
    assert len(nexts(r)) == 2, r.err

    n = int(option(more, "--replicates") or 0)
    assert option(more, "--max-mde") == loose[1], more
    assert ref_admits_both(n, rows, accepted) and not ref_admits_both(n - 1, rows, accepted), n
    assert n == made["more"]
    assert folder.follow(more).code == 0

    offered = float(option(wider, "--max-mde") or 0)
    assert option(wider, "--replicates") == str(typed), wider
    assert offered == pytest.approx(ref_offer_both(typed, rows, accepted), abs=1e-12), offered
    assert offered > ref_offer(typed, rows, accepted, test=made["easier"]), "the easier reading alone would have offered less"
    assert folder.follow(wider).code == 0
    below = folder.sweep("--replicates", str(typed), "--dry-run", "--max-mde", f"{offered - 0.001:.3f}")
    assert below.code == 1, below.text


def test_z3_where_the_paired_reading_can_flag_nothing_the_fewer_conditions_line_counts_for_both(folder: Folder) -> None:
    """Z3's last clause. Seven replicates over four tests: Fisher's reading could flag each of 85
    conditions alone, the paired reading each of 3, and the line says the smaller. No accepted change
    is offered (the one typed is kept), and the replicates offered pass when typed."""
    paired_p, fisher_p = 2 * 0.5 ** 7, 2 / math.comb(14, 7)

    def most(p_min: float) -> int:
        return max(k for k in range(0, 200) if k == 0 or Q / k > p_min)

    assert (most(paired_p), most(fisher_p)) == (3, 85)
    r = folder.sweep("--replicates", "7", "--dry-run", *LOOSE)
    assert r.code == 1, r.text
    assert "paired" in error_line(r), r.err
    (fewer,) = [line for line in nexts(r) if not line.startswith(COMMAND + " ")]
    assert "fewer conditions" in fewer and re.search(r"\bat most 3\b", fewer), fewer
    (more,) = commands(r)
    assert option(more, "--max-mde") == LOOSE[1], more
    n = int(option(more, "--replicates") or 0)
    assert ref_admits_both(n, 4, ACCEPTED) and not ref_admits_both(n - 1, 4, ACCEPTED), n
    assert folder.follow(more).code == 0


# ---------- Z5: an earlier run too small to pair ----------


#: The earlier run's replicates, this sweep's, and the design: its failures (two tasks by two rates,
#: so four tests each), or one condition with one failure at the default accepted change, where
#: Fisher's reading needs one replicate more than the paired one. ``flags`` is whether the pair as it
#: stands can flag anything at all.
TOO_SMALL: dict[str, dict[str, Any]] = {
    "the same size, sized for Fisher's reading alone": dict(earlier=FISHER_ONLY, replicates=FISHER_ONLY),
    "this sweep asks for more than the earlier run has": dict(earlier=NEITHER, replicates=60),
    "this sweep asks for fewer, and the earlier run is short too": dict(earlier=30, replicates=NEITHER),
    "the spec gained an event since": dict(earlier=BOTH, replicates=BOTH, failures=("violated", "timeout")),
    "so small the pair can flag nothing": dict(earlier=5, replicates=5, flags=False),
    "Fisher's reading needs more than the paired one": dict(earlier=100, replicates=100, one=True),
}


@pytest.mark.parametrize("case", TOO_SMALL)
def test_z5_an_earlier_run_too_small_to_pair_is_named_and_every_command_offered_passes(case: str, tmp_path: Path) -> None:
    """Z5 and FRS-10. The refusal names the run, its replicates and the replicates a pair needs. Its
    commands are a new baseline at that size, with no ``--pair-with``, and the accepted change that
    admits the pair as it stands; never more replicates of this sweep, which the earlier run's size
    would refuse again. Each is typed once and is not refused for size. Rule 4 of the look holds: one
    ``error:`` line, then only ``next:`` lines, and the pairing step that follows a new baseline is
    said in a line that is not a ``next:``."""
    made = TOO_SMALL[case]
    earlier, replicates, flaggable = made["earlier"], made["replicates"], made.get("flags", True)
    failures = made.get("failures", ("violated",))
    shape: dict[str, Any] = dict(tasks=("search",), rates=(0.3,)) if made.get("one") else {}
    accepted = 0.2 if made.get("one") else ACCEPTED
    loose = ("--max-mde", f"{accepted:g}")
    rows = (1 if made.get("one") else 4) * len(failures)
    folder = Folder(tmp_path, replicates, **shape)
    first = folder.sweep("--replicates", str(earlier), "--yes", "--max-mde", "1", "--name", "small")
    assert first.code == 0, first.text
    (small,) = folder.runs()
    folder.write(replicates, failures=failures, **shape)
    pairs = min(earlier, replicates)
    assert not ref_admits(pairs, rows, accepted, test="mcnemar"), "the pair is not too small"

    r = folder.sweep("--pair-with", "small", "--replicates", str(replicates), "--dry-run", *loose)
    assert r.code == 1, r.text
    assert folder.runs() == [small]

    said = [line for line in r.err.splitlines() if not line.startswith("note: ")]
    assert said[0].startswith("error: ") and all(line.startswith("  next: ") for line in said[1:]), r.err
    baseline = [c for c in commands(r) if "--pair-with" not in c]
    wider = [c for c in commands(r) if "--pair-with" in c]
    assert len(baseline) == 1 and len(wider) == (1 if flaggable else 0), nexts(r)
    assert len(commands(r)) == len(baseline) + len(wider)

    # The run by its name, its replicates, and the replicates a pair needs: the smallest above the
    # earlier run's at which a new baseline and the sweep paired with it both pass.
    need = int(option(baseline[0], "--replicates") or 0)
    error = error_line(r)
    assert '"small"' in error and small not in error, error
    assert re.search(rf"\b{earlier}\b", error) and re.search(rf"\b{need}\b", error), (error, earlier, need)
    assert need > earlier and ref_admits_both(need, rows, accepted) and not ref_admits_both(need - 1, rows, accepted), need
    assert option(baseline[0], "--max-mde") == loose[1], baseline
    unsaid = "\n".join(line for line in r.err.splitlines() if not line.startswith("  next: "))
    assert f"--pair-with latest --replicates {need}" in unsaid, r.err

    for command in wider:
        assert option(command, "--pair-with") == "small" and option(command, "--replicates") == str(replicates), command
        offered = float(option(command, "--max-mde") or 0)
        assert offered == pytest.approx(ref_offer(pairs, rows, accepted, test="mcnemar"), abs=1e-12), offered
    for command in commands(r):
        followed = folder.follow(command)
        assert followed.code == 0 and not refused_for_size(followed), (command, followed.text)


# ---------- Z6: a resume is read as before; every backend plans the same way ----------


def test_z6_a_resume_is_read_with_fishers_reading_alone(folder: Folder) -> None:
    """Z6. A run stopped short at 40 replicates is resumed from a spec that now says 37: Fisher's
    reading passes there and the paired one does not, and the resume goes on. Its plan carries no
    paired reading."""
    started = folder.sweep("--yes", "--max-rollouts", "4", *LOOSE)
    assert started.code == 3, started.text
    (run,) = folder.runs()
    folder.write(FISHER_ONLY)
    planned = folder.sweep("--resume", run, "--dry-run", "--json")
    assert planned.code == 0, planned.text
    doc = json.loads(planned.out)
    assert doc["design_mde"]["test"] == "fisher" and "design_paired" not in doc, sorted(doc)
    resumed = folder.sweep("--resume", run, "--yes")
    assert resumed.code == 0, resumed.text
    assert PAIRED_LINE not in resumed.out, resumed.out
    assert Store(folder.root).manifest(run).status == "complete"


def _same_plan(local: Result, remote: Result) -> None:
    assert remote.code == local.code, (remote.text, local.text)
    assert design_lines(remote.out) == design_lines(local.out), (remote.out, local.out)
    if local.code:
        assert error_line(remote) == error_line(local)
        assert [option(c, "--replicates") for c in commands(remote)] == [option(c, "--replicates") for c in commands(local)]
        assert [option(c, "--max-mde") for c in commands(remote)] == [option(c, "--max-mde") for c in commands(local)]


@pytest.mark.parametrize("replicates", [FISHER_ONLY, BOTH], ids=["refused", "planned"])
def test_z6_modal_plans_as_this_machine_does(replicates: int, folder: Folder, monkeypatch: pytest.MonkeyPatch) -> None:
    """Z6: the gate and the plan's two lines are the same on Modal (a stand-in package; nothing is
    called: a refusal and a dry run both stop before Modal is used)."""
    monkeypatch.setitem(sys.modules, "modal", importlib.util.module_from_spec(importlib.machinery.ModuleSpec("modal", None)))
    typed = ("--replicates", str(replicates), "--dry-run", *LOOSE)
    local = folder.sweep(*typed)
    assert local.code == (0 if replicates == BOTH else 1), local.text
    assert len(design_lines(local.out)) == (2 if replicates == BOTH else 0), local.out
    _same_plan(local, folder.sweep(*typed, "--backend", "modal"))


@pytest.fixture(scope="module")
def pool() -> Iterator[Pool]:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    with world(tmp_path, monkeypatch, pool) as made:
        yield made


#: Two tests at 0.4: Fisher's reading passes at 32 and the paired one does not.
CLOUD_FISHER_ONLY = 32


@pytest.mark.parametrize("planned", [False, True], ids=["refused", "planned"])
def test_z6_your_cloud_account_plans_as_this_machine_does(planned: bool, w: CloudWorld) -> None:
    """Z6: and on the cloud backend (the fakes; a refusal and a dry run start no node)."""
    assert ref_admits(CLOUD_FISHER_ONLY, 2, ACCEPTED) and not ref_admits(CLOUD_FISHER_ONLY, 2, ACCEPTED, test="mcnemar")
    more = CLOUD_FISHER_ONLY
    while not ref_admits_both(more, 2, ACCEPTED):
        more += 1
    replicates = more if planned else CLOUD_FISHER_ONLY
    w.aws_state(quota=40)
    w.write_spec(table=cloud_table(), replicates=replicates)
    typed = ("sweep", w.spec.name, "--target", "bu_targets.cloud:quick", "--dry-run", *LOOSE)
    local = w.run(*typed, "--backend", "local")
    assert local.code == (0 if planned else 1), local
    assert len(design_lines(local.out)) == (2 if planned else 0), local.out
    cloud = w.run(*typed, "--backend", "cloud")
    _same_plan(Result(local.code, local.out, local.err), Result(cloud.code, cloud.out, cloud.err))


# ---------- Z7: the run record is unchanged ----------


def test_z7_each_run_records_its_own_reading_and_no_new_key(folder: Folder) -> None:
    """Z7 and FRS-9. A run paired with nothing records Fisher's reading as ``design_mde``; the run
    paired with it records the paired one, whose plan has no second reading. Neither record has a key
    it did not have in 0.4, and the artifact format's page names no version after 1.2."""
    first = folder.sweep("--yes", *LOOSE)
    assert first.code == 0, first.text
    (before,) = folder.runs()
    planned = folder.sweep("--pair-with", before, "--dry-run", "--json", *LOOSE)
    assert planned.code == 0, planned.text
    doc = json.loads(planned.out)
    assert doc["design_mde"]["test"] == "mcnemar" and "design_paired" not in doc, sorted(doc)
    second = folder.sweep("--pair-with", before, "--yes", *LOOSE)
    assert second.code == 0, second.text
    (after,) = [run for run in folder.runs() if run != before]

    top = {"run_id", "target_id", "t_unit", "run_salt", "axis_types", "backend", "environment", "retain_traces_for",
           "status", "created_at", "poisson_prove_version", "schema_version", "declared", "name", "note",
           "produced_by"}
    environment = {"python", "platform", "poisson_prove_version", "sweep", "import_path", "max_mde_accepted",
                   "design_mde"}
    for run, test in ((before, "fisher"), (after, "mcnemar")):
        record = folder.manifest(run)
        assert set(record) <= top, sorted(set(record) - top)
        assert set(record["environment"]) <= environment, sorted(set(record["environment"]) - environment)
        design = record["environment"]["design_mde"]
        assert set(design) == DESIGN_KEYS and design["test"] == test, design
        base, way, limit = ref_worst(BOTH, 4, ACCEPTED, test=test)
        assert limit is not None and (design["base_rate"], design["direction"]) == (base, way), design
        assert abs(design["mde"] - limit) <= 1e-4 + 1e-12, (design, limit)
    page = (DOCS / "artifact-format.md").read_text(encoding="utf-8")
    assert "the format's 1.2" in page
    assert not re.search(r"the format's 1\.(?:[3-9]|\d\d)", page), "the artifact format moved past 1.2"


# ---------- Z8: the quickstart ----------


def test_z8_the_quickstarts_194_pass_both_readings_and_its_paired_sweep_is_planned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Z8, and Z4 on the one design every new user meets: ``init --example`` writes 194 replicates over
    nine conditions and two failures; the first sweep's plan has both lines, and the documented second
    sweep on the same seeds is planned, not refused. (That 194 is the fewest the paired reading passes
    is PF4.30's, pinned from the references by the power-gate tests.)"""
    monkeypatch.chdir(tmp_path)
    made = run_cli(["init", "--example"])
    assert made.code == 0, made.text
    assert SweepSpec.load(tmp_path / "prove.toml").replicates == 194
    first = run_cli(["sweep", "--yes"])
    assert first.code == 0, first.text
    fisher, paired = design_lines(first.out)
    assert fisher.startswith(FISHER_LINE) and "Fisher" in fisher and paired.startswith(PAIRED_LINE), first.out
    # PF4.30's own numbers for this design (test_pf4_surfaces pins them from the references, in the
    # nightly run): the paired reading's limit is 0.1998 at its worst base rate, 0.4.
    assert_states(paired, limit=0.1998, base=0.4)
    (pairing,) = [line.strip()[len("next: "):] for line in first.out.splitlines() if line.strip().startswith("next: ")]
    second = run_cli([*shlex.split(pairing)[1:], "--dry-run"])
    assert second.code == 0 and not refused_for_size(second), second.text
    (line,) = design_lines(second.out)
    assert "paired test" in line and not line.startswith(PAIRED_LINE), line


# ---------- the pages (section 3.4) and the CHANGELOG (section 8) ----------


def console_lines(page: str) -> list[str]:
    """Every line of every fenced block of a page."""
    out: list[str] = []
    inside = False
    for line in page.splitlines():
        if line.startswith("```"):
            inside = not inside
            continue
        if inside:
            out.append(line)
    return out


def test_a_page_that_quotes_the_first_sweeps_design_line_quotes_the_paired_line_under_it() -> None:
    """Section 3.4: the plan excerpts gain the line. Every Fisher design line a page shows is followed
    by the paired one; at least the quickstart and ``sweep``'s page show one."""
    showing = []
    for path in sorted([*DOCS.rglob("*.md"), ROOT / "README.md"]):
        lines = console_lines(path.read_text(encoding="utf-8"))
        for at, line in enumerate(lines):
            if line.strip().startswith(FISHER_LINE) and "worst base rate" in line and "(Fisher," in line:
                showing.append(path.name)
                under = lines[at + 1].strip() if at + 1 < len(lines) else ""
                assert under.startswith(PAIRED_LINE), (path.name, line, under)
    assert {"quickstart.md", "sweep.md"} <= set(showing), showing


def test_sweeps_page_says_no_pilot_run_is_needed_and_shows_the_too_small_refusal() -> None:
    """Section 3.4: ``docs/commands/sweep.md`` says the plan needs no pilot run, and shows the refusal
    of a pair whose earlier run is too small with its two ways out: a new baseline, with no
    ``--pair-with``, and the accepted change that admits the pair."""
    page = (DOCS / "commands" / "sweep.md").read_text(encoding="utf-8")
    prose = "\n".join(line for line in page.splitlines() if line not in console_lines(page))
    assert re.search(r"\bno pilot\b", " ".join(prose.split())), "sweep.md does not say the plan needs no pilot run"
    lines = console_lines(page)
    shown = False
    for at, line in enumerate(lines):
        if not line.startswith("error: "):
            continue
        after = []
        for following in lines[at + 1:]:
            if not following.startswith("  next: "):
                break
            after.append(shlex.split(following[len("  next: "):]))
        baseline = [c for c in after if "--pair-with" not in c and "--replicates" in c]
        wider = [c for c in after if "--pair-with" in c and "--max-mde" in c]
        shown = shown or (len(baseline) == 1 and len(wider) == 1 and len(after) == 2)
    assert shown, "sweep.md does not show the refusal of an earlier run too small to pair"


def test_the_statistics_page_says_a_first_sweep_is_planned_for_the_paired_one() -> None:
    """Section 3.4: one sentence in the power gate's paragraph of the concepts page."""
    page = (DOCS / "concepts" / "what-the-statistics-claim.md").read_text(encoding="utf-8")
    (paragraph,) = [p for p in page.split("\n\n") if p.startswith("**The power gate**")]
    assert "paired" in paragraph, paragraph


def test_the_0_5_0_entry_says_a_first_sweep_is_sized_for_the_paired_one() -> None:
    """Section 8: under ``## 0.5.0``, a Changed item that names the issue and ``sweep --pair-with``,
    and says what a too-small earlier run is offered. Its facts, not its sentences."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = text.split("\n## 0.5.0", 1)[1].split("\n## ", 1)[0]
    assert "\n### Changed\n" in entry, entry[:400]
    changed = entry.split("\n### Changed\n", 1)[1].split("\n### ", 1)[0]
    items = [" ".join(item.split()) for item in re.split(r"(?m)^- ", changed) if item.strip()]
    sized = [item for item in items if "(#6)" in item]
    assert len(sized) == 1, items
    assert "--pair-with" in sized[0] and "paired" in sized[0] and "baseline" in sized[0], sized[0]
