"""FR frozen tests: invariants FR1 to FR20 of the first-run fixes, written before the
store check, the missing-flags refusal, the inference line's new wording and the parser edit exist, against
``f9b881f`` -- main's HEAD on 2026-09-18: P-1's landed build (``fe7b50f``) plus A8b's frozen
test file (``73a8ccb``, ``f9b881f``), which the A8b build had not yet built when this was frozen.

**The register this file is built to.** D1 (a missing store refuses at exit
2 on every verb that reads it, an empty one on every such verb but ``runs``, which exits 0 and says so on
stderr), D5 bound by D14 (E3 reaches ``report``, ``serve``, ``check`` and ``inspect``, and ``check`` never
passes on a missing argument), D7 (the ``Inferred events for this pair`` suggestion is retired) and D13
(every template pinned verbatim, the wording reviewed in the freeze's mapping table) are settled and
not reopened; FR19 and FR20 were added with them. The three store-refusal
templates are pinned in each source form (``--store``, ``$POISSON_PROVE_STORE``, the default), the seven
missing-flags literals (now on the generated lattice pair, ``tests/lattice.py``) and the inference lines byte for byte, as literals and never as a template the
implementation shares.

**Two cells, and no invariant is cell-specific -- a result, not an assumption** (one cell would do;
this file reports two because both were asked for). pandas 2.3.3 and pandas 3.0.5: every test here is asserted in both cells, nothing here reads a stored
null, and the map is the whole file twice: **106 + 106 = 212 ids over the two cells against this file's own
106.** The ids by invariant: FR1 3, FR2 1, FR3 1, FR4 7, FR5 4, FR6 3, FR7 3, FR8 3, FR9 6, FR10 5, FR11 7,
FR12 17, FR13 10, FR14 7, FR15 1, FR16 6, FR17 6, FR18 2, FR19 9, FR20 5.

**Measured before the build, at ``f9b881f``, and what it moved.** (1) The greps for frozen movers:
the first returns 26 lines in four files and the fifth five carriers, as at ``a626cd3``; the fourth gains one
line, ``test_p1_payload.py`` Y22's ``monkeypatch.chdir``, which drives ``serve`` on the fixture pair with an explicit
``--store``, ``--event`` and ``--x`` and moves nothing; A8b re-minted the pin on ``test_m3_timeout_trace.py``,
a file this change does not touch. The twenty-one frozen movers are the predicted ones, at new line numbers: ``test_m6_multi.py`` +5,
``test_m7_multi.py`` +14 and +15, ``test_m13_viewer.py`` +2, and I17 +1; ``test_m10_multi.py`` did not move
(it was listed among P-1's edits and P-1 did not touch it) and neither did I2. (2) Nothing that was
predicted about the inference path moved: ``infer_events`` and the inference branch of
``MultiDiffResult.to_markdown`` are byte-identical to ``a626cd3``'s (the branch is ``diff.py`` lines 700-704,
the method 698-750), the fixture pair infers its less frequent outcome over its more frequent one on the
pair and on its first run alone (on the lattice: ``held`` over ``tripped``, 1,443 / 3,165 on the pair and
533 / 1,771 on ``lattice-a``), and the mock pair infers ``violated, timeout`` over ``completed``. **What no longer holds:**
the base is not green -- a green base commit was assumed, and ``f9b881f`` carries A8b's
frozen test file against a tree that does not build it yet (63 failed and 2 errors, identical in both cells:
53 in ``test_a8b_cut_and_cap.py``, 4 in ``test_m3_capture.py``, one each in ``test_a8a_span_schema.py``,
``test_m3_crash_trace.py``, ``test_m3_timeout_trace.py`` and one other test file, and two failures and
two errors in a further test file); P-1's expected edit is done, ``to_markdown``'s parameter
line and ``headline``'s pairing token are in the tree with ``_write_summary``'s code unedited, so the two
changes no longer collide; the inference lines are 108 and 122 characters against 54 and 68 today,
not the predicted 107, 120, 55 and 68; and the fixture pair's verbs without a paired method now emit P-1's ``UnpairedAnalysis``
warning through the warnings machinery, never into the CLI's own stderr stream, which is what every
assertion here reads. (3) P-1 filed the whole-file route: ``ec05b676...`` in all five carriers of the
``diff.py`` digest, no live exclusion record, so D12 stands. (4) The digests below were read off
``f9b881f``: ``diff.py`` outside ``MultiDiffResult.to_markdown`` (the qualified-name resolver's lines 698
to 750) ``6413b54a...``, and ``report.py``, ``viewer.py``, ``store.py`` and ``tree.py`` whole-file.
``store.py`` is byte-identical to ``a626cd3``'s: P-1 touched ``cli.py``, ``diff.py``, ``report.py``,
``tree.py`` and ``viewer.py`` only, and A8b's build (``trace``, ``capture``, ``sampler``, ``executor``,
``executor_modal``) touches none of the five files this file pins. (5) ``Store.runs()`` and
``Store.manifest()`` are unchanged. (6) The shadow shim -- a scratch build of what this file pins -- turns every test
here green and leaves exactly group D red.

**Where this file reads the invariants differently, each with its hatch.** (a) FR20's explicit-event clause
carries its positive control in the same test, as FR20's own text says, so it is *red* on the bare tree;
it was predicted green before and after, and it cannot be both -- a negative with no control is the
vacuous shape group E4-b exists to prevent. The tie clause is FR20's one green half. (b) FR11's
two cross-checks read both lists off live output (E3's, and the error a wrong ``--x`` or ``--event``
provokes); comparing E3's list to a constant would have been green on the bare tree and pinned nothing. (c)
FR1 gives every invocation its own missing root, so FR6 is the sole catch for the mutant that creates the
root, as its mutation row says. (d) FR4 also pins the empty-store templates (E and E-runs) in each source form,
and a set-but-empty ``$POISSON_PROVE_STORE`` as *not* the source: ``_store_root`` reads it as unset and the
source must be "set and non-empty". (e) FR10 pins a third ``timeout`` case that FR10's
text does not state: a run whose ``timeout`` is already an outcome lists it once. (f) FR12's order matrix adds the
empty store to its store row. (g) FR13's "nothing else moves" is two green tests (the flag sets, and the five
tree flags' help against ``diff``'s), beside V30, W1, R13 and W11. (h) FR18's import clause is a subset test,
so it holds before the build as well: ``shlex`` may arrive and nothing else may. (i) FR5's fixture-pair verb digests
stay with A7's P7-10, which this file does not restate. (j) Not pinned: the inference lines' lengths, and the
``inspect`` wrong-``--event`` neighbour, which is out of scope.

**The classified red set on the update commit with this file added, measured on two
pristine ``git archive`` copies of ``f9b881f`` carrying the update and this file, venvs from the repo venv's
freeze closure differing in exactly pandas, collection verified 2071 = 2071 = 2071 at ``f9b881f`` (both
baseline cells and the repo) and 2177 = 2177 = 2177 = 2177 = 2177 with the update and this file (both
red-set cells, both shim-control cells, and the clone at the tip), baselines 63 failed / 2001 passed / 5
skipped / 2 errors in both cells at ``f9b881f``: 151 failed / 2019 passed / 5 skipped / 2 errors, identical
test by test in both cells.** The 153 red are the base's 65 and **88 of this change's**: **82** of this
file's 106 tests, each red for its expected cause (the store check, the missing-flags refusal, the parser and
the new wording do not exist yet), and the six frozen tests V1 and V4 (renamed, amended to the
``serve --x AXIS`` and ``serve --event NAME`` literals), A14, B9, B17 and C2 (``:504``), each for the new
wording. **Nothing else is red beyond the base's 65, and none of the base's 65 turned green.** Group D (F28,
L20, R19, W20, G20) is green on the update commit and red once the build edits ``diff.py``; nothing in this
commit touches it. The shim control -- the same copies with the shim built -- is 68 failed / 2102 passed / 5
skipped / 2 errors in both cells, identical test by test: the base's 65 and group D's five, nothing else.

**Green before and after, named so its green is not read as evidence** (count them out of
coverage): FR5's four tests, FR6's ``sweep`` half, FR12's ``check`` unknown-run id (today's ``check`` loads
the pair before it refuses), FR13's four "nothing else moves" ids, FR17's six, FR18's two, FR19's exit,
stdout and tripwire half (four ids) and its gate-pair controls (green by construction: they pin the
fixtures, not the build), and FR20's tie clause -- 24 of the 106 on the bare tree. **The five frozen tests
carrying the group E1 edit (I2 x3, I17 x2) and the four group E4-b negatives that are not also
E4-a are green before and after by construction**; the negatives are non-vacuous only because FR16 asserts
the marker matches real inferred output in the same test.

**Mutation list** (twenty-nine planned rows and eight this file added, measured
on the shim control with one interpreter per row, each row applying exact replacements that fail loudly when
a target is missing; control clean; **all 37 caught by this file alone**). The owners, by frozen test: 1
``exists()`` for ``is_dir()``: FR1's file-root pair alone. 2 and 3 missing and empty collapsed, and an empty
store keeping ``unknown run``: FR2, FR4's empty-source trio, FR7's empty hint, FR12's empty-store row. 4 and
5 ``runs`` on an empty store exiting 2, and its note on stdout: FR3, FR4's trio, FR6's empty-root test, FR7's
empty hint (with I17 x2 in the frozen amendment). 6 the source clause always the default: twenty ids across
FR1, FR2, FR3, FR4, FR7 and FR12. 7 env over flag in the clause: FR4's flag id alone. 8 the note on every
``runs``: FR5's two ``runs`` ids. 9 the check creating the root: FR6's missing-root test, and
incidentally FR1's file-root pair because ``mkdir`` raises on a file; **row 37 is the pure spelling, and FR6
alone catches it**. 10 the check gating ``sweep``: FR6's sweep test, and fifteen fixture errors because the
mock pair's own sweep is refused. 11 ``shlex.quote`` dropped: FR7 alone (three ids). 12 axes from
``axis_types``: FR11's disagreement pair and the property. 13 events as the inferred set: twenty-five ids in
FR8 to FR12 and FR19. 14 ``serve --x`` left argparse-required: FR9 (four of six), FR12, FR13. 15 E3 after
``_run_diffs``: FR12's tripwire, FR19's tripwire half x4, the FR11 property. 16 E3 before ``manifest``:
FR12's unknown-run row alone (three ids). 17 ``inspect`` omitting ``timeout``: FR10's timeout id and
FR11's single-run property. 18 ``check``'s reason clause dropped: FR10, FR12's tripwire. 19 the retired
suggestion kept: FR9 x6, FR10, FR12. 20 ``to_markdown`` keeping the parenthetical while ``_write_summary``
prints the new line: FR14's five surfaces and its API pair, FR16 x6. 21 the single-run copy left: FR15 and
FR20 x4. 22 the line on explicit events: FR16's ``diff`` pair. 23 a module-level ``_inference_line``: FR17's
region digest, FR18's names. 24 ``to_json`` gaining a key: FR17's keys and region digest. 25 and 26 ``check``
listing then exiting 0, or then gating on the inferred set: FR19's exit half x4 (the PASS pair and the FAIL
pair both leave 2), FR10, FR11, FR12. 27 the listing on stdout: FR19 both halves x8. 28 events joined with
``and``: FR20's mock id alone. 29 the line after the summary line: FR15, FR20 x4. The eight extras: 30 the
``--out`` refusal ahead of E3: FR12's non-empty-out pair; 31 E3 ahead of the arity refusal: FR12's report
arity id alone; 32 a set-but-empty ``$POISSON_PROVE_STORE`` named as the source: FR4's empty-env id alone; 33 axes
from the first run only and 36 events from the first run only: the FR11 property alone each; 34 the hint's
verb always ``runs``: seventeen ids in FR1, FR2, FR4, FR7 and FR12; 35 ``--store`` after the verb in the
create line: thirteen ids in FR1, FR4, FR7 and FR12; 37 above. Every row is re-applied against the
implementation, reporting where each lands; a row that needs both files (20) is two edits.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shlex
import sys
import tempfile
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import poisson_prove.cli as cli
from poisson_prove.diff import MultiDiffResult, UnpairedAnalysis, infer_events, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from poisson_prove.survival import competing_set
import lattice
from conftest import quickstart_design

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "poisson_prove"
LATTICE_ROOT = lattice.root()
# PF3: the one copy is the packaged spec; this is its design at
# the 100 replicates this file was frozen at.
QUICKSTART = quickstart_design()
# PF4 re-freeze (PF4.30, PF4.48a): the quickstart design at 100 replicates with nothing
# declared has a detection limit (0.262 at base rate 0.400) above the default accepted change of 0.20,
# so its sweep is refused; every frozen sweep of it in this file accepts 0.3, the smallest round value
# above the limit.
QUICKSTART_MAX_MDE = ("--max-mde", "0.3")
ROLLOUT = "poisson_prove.examples.mock_agent:rollout"
PATCHED = "poisson_prove.examples.mock_agent:rollout_patched"
QUICKSTART_SALT = "0000000000000015"
LATTICE_A, LATTICE_B = "lattice-a", "lattice-b"
LATTICE_X, LATTICE_Y = "gain", "load"
# PF2: every run has a name -- its target id up to the first ``/``, the UTC date it was
# created, and a letter in creation order among that target's runs that day. The lattice's two runs are of
# two targets created on 2026-01-15, so each is ``a``.
LATTICE_NAMES = {
    LATTICE_A: "lattice-before 2026-01-15 a",
    LATTICE_B: "lattice-after 2026-01-15 a",
}
assert (LATTICE_A, LATTICE_B, LATTICE_X, LATTICE_Y) == (lattice.RUN_A, lattice.RUN_B, lattice.X, lattice.Y)
assert LATTICE_NAMES == {lattice.RUN_A: lattice.NAME_A, lattice.RUN_B: lattice.NAME_B}
HORIZON = 10.0

# ---------- the pinned words, verbatim ----------

FROM_FLAG = "it came from --store"
FROM_ENV = "it came from $POISSON_PROVE_STORE"
FROM_DEFAULT = "it is the default, since neither --store nor $POISSON_PROVE_STORE is set"
SOURCES = (FROM_FLAG, FROM_ENV, FROM_DEFAULT)
SWEEP_TAIL = "sweep SPEC.toml --target pkg.module:rollout"
RUNS_HEADER = "run_id  status  backend  target_id  t_unit  rows  no_outcome\n"


# The three store-refusal templates are checked by their facts, not their words: a refusal is one
# ``error: `` line followed only by ``  next: `` lines, so the old hint
# lines are now commands on next lines, and ``--store`` may come before or after the verb.


def create_command(root: str) -> list[str]:
    """The command the create hint offers, as a shell reads it back."""
    return ["poisson-prove", "--store", root, *SWEEP_TAIL.split()]


def hinted_commands(err: str) -> list[list[str]]:
    """Every command an indented hint line offers: the text after the line's first ``: ``, read back the
    way a shell would read it."""
    commands = []
    for line in err.splitlines():
        if line.startswith("  ") and ": " in line:
            try:
                commands.append(shlex.split(line.strip().partition(": ")[2]))
            except ValueError:
                continue
    return commands


def reads_another_store(command: list[str], verb: str) -> bool:
    return command[:1] == ["poisson-prove"] and verb in command and any(
        command[i : i + 2] == ["--store", "PATH"] for i in range(len(command))
    )


def refusal_shape(err: str) -> list[str]:
    """What is wrong with ``err`` as a refusal's stderr: one ``error: `` line, then only ``  next: `` lines."""
    lines = err.splitlines()
    problems = [] if lines and lines[0].startswith("error: ") else ["the first line is not an error line"]
    return problems + [f"not a next line: {line}" for line in lines[1:] if not line.startswith("  next: ")]


def store_refusal_problems(err: str, head: str, root: str, source: str, verb: str) -> list[str]:
    problems = refusal_shape(err)
    if f"{head} {root}" not in err:
        problems.append(f"does not say {head} {root}")
    if source not in err:
        problems.append("the source clause is missing")
    if create_command(root) not in hinted_commands(err):
        problems.append("no next line offers the sweep that writes the first run there")
    if not any(reads_another_store(command, verb) for command in hinted_commands(err)):
        problems.append(f"no next line offers reading another store with {verb}")
    return problems


def missing_problems(err: str, root: str, source: str, verb: str) -> list[str]:
    """Store refusal M: a path with no directory at it, on a verb that reads the store."""
    return store_refusal_problems(err, "no store at", root, source, verb)


def empty_problems(err: str, root: str, source: str, verb: str) -> list[str]:
    """Store refusal E: a directory holding no manifest.json, on a verb that reads the store."""
    return store_refusal_problems(err, "no runs in", root, source, verb)


def empty_runs_problems(out: str, root: str) -> list[str]:
    """Store refusal E-runs: ``runs`` on an empty store, exit 0, no ``error: `` prefix.

    PF2: ``runs``' first stdout line is its verdict, so the message is now
    ``ok  no runs in <store>`` and one ``  next: `` line, both on stdout, with nothing on stderr (the
    callers check stderr); the verdict line carries no source clause, which the other verbs' empty-store
    refusal still does."""
    lines = out.splitlines()
    problems = [] if lines and lines[0] == f"ok  no runs in {root}" else [f"the first line is not ok  no runs in {root}"]
    problems += [f"not a next line: {line}" for line in lines[1:] if not line.startswith("  next: ")]
    if len(lines) < 2:
        problems.append("there is no next line")
    if create_command(root) not in hinted_commands(out):
        problems.append("no next line offers the sweep that writes the first run there")
    return problems


def unknown_run_problems(err: str, run: str) -> list[str]:
    """The unknown-run refusal: it names the run bare or double-quoted, never as a Python repr."""
    problems = refusal_shape(err)
    if "unknown run" not in err or run not in err:
        problems.append(f"does not name the unknown run {run}")
    if f"'{run}'" in err:
        problems.append("the run is shown as a Python repr")
    return problems


GATE_REASON = "a gate whose meaning changes when a new outcome appears is not a gate"
PICTURE_REASON = "a picture whose meaning changes when a new outcome appears is worse than a table with the same defect"

# The missing-flags refusal's seven literals, on the lattice pair: (argv after ``--store`` and the lattice's root, stderr).
E3_LATTICE: dict[str, tuple[list[str], str]] = {
    "report pair, no --x": (
        ["report", LATTICE_A, LATTICE_B, "--y", LATTICE_Y],
        "error: report requires --x AXIS, which was not given. lattice-a and lattice-b carry:\n"
        "  axes: gain, load\n"
        "  events: held, tripped\n",
    ),
    "report single run, no --x": (
        ["report", LATTICE_A],
        "error: report requires --x AXIS, which was not given. lattice-a carries:\n"
        "  axes: gain, load\n"
        "  events: held, tripped\n",
    ),
    "serve, neither": (
        ["serve", LATTICE_A, LATTICE_B],
        f"error: serve requires --x AXIS and --event NAME, and neither was given; {PICTURE_REASON}. lattice-a and lattice-b carry:\n"
        "  axes: gain, load\n"
        "  events: held, tripped\n",
    ),
    "serve, no --event": (
        ["serve", LATTICE_A, LATTICE_B, "--x", LATTICE_X],
        f"error: serve requires --event NAME, which was not given; {PICTURE_REASON}. lattice-a and lattice-b carry:\n"
        "  axes: gain, load\n"
        "  events: held, tripped\n",
    ),
    "serve, no --x": (
        ["serve", LATTICE_A, LATTICE_B, "--event", "tripped"],
        "error: serve requires --x AXIS, which was not given. lattice-a and lattice-b carry:\n"
        "  axes: gain, load\n"
        "  events: held, tripped\n",
    ),
    "check, no --event": (
        ["check", LATTICE_A, LATTICE_B],
        f"error: check requires --event NAME, which was not given; {GATE_REASON}. lattice-a and lattice-b carry:\n"
        "  events: held, tripped\n",
    ),
    "inspect, no --event": (
        ["inspect", LATTICE_A],
        "error: inspect requires --event NAME, which was not given. lattice-a carries:\n"
        "  events: held, tripped\n",
    ),
}
SERVE_ROWS = ("serve, neither", "serve, no --event", "serve, no --x")


def listed_values(err: str, label: str) -> list[str]:
    """Every list ``err`` gives after ``label: `` (``axes`` or ``events``), on a line of its own or inside a
    sentence, up to the ``;`` or ``.`` that ends it."""
    return re.findall(rf"(?<![\w-]){label}: (.+?)(?=[.;]\s|[.;]?$)", err, flags=re.MULTILINE)


def run_names(root: Path | str) -> dict[str, str]:
    """PF2: each run's name, as ``runs --json`` gives it beside its id."""
    r = run_cli(["--store", str(root), "runs", "--json"])
    assert r.code == 0, r
    return {entry["run_id"]: entry["run_name"] for entry in json.loads(r.out)["runs"]}


def next_commands(err: str) -> list[list[str]]:
    """Every ``  next: `` line's command, read back the way a shell would read it."""
    return [shlex.split(line.partition("next: ")[2]) for line in err.splitlines() if line.startswith("  next: ")]


def e3_problems(err: str, old: str, names: Mapping[str, str]) -> list[str]:
    """What is wrong with ``err`` as the listing refusal whose pre-PF1 words are ``old``. A refusal is now one
    ``error: `` line followed only by ``  next: `` lines, so the old
    ``  axes:`` and ``  events:`` lines are checked by their facts wherever stderr gives them: the verb, the
    missing flags, the runs, the reason clause where the old words had one and not where they did not, and
    each list exactly.

    PF2: the runs are named by name, double-quoted, in the error line (``names`` maps
    each id the old words gave to its name), and the next line that repeats the command has each typed id
    replaced by its name."""
    head, *rest = old.splitlines()
    problems = refusal_shape(err)
    verb = head.split()[1]
    if verb not in err.partition("\n")[0]:
        problems.append(f"the error line does not name {verb}")
    for flag in re.findall(r"--[a-z]+(?= [A-Z]+)", head):
        if flag not in err:
            problems.append(f"does not name {flag}")
    runs = re.search(r"\. (\S+) and (\S+) carry:$|\. (\S+) carries:$", head)
    assert runs, head
    for run in filter(None, runs.groups()):
        # PF2: the run is named by its name, and no next line carries its id.
        if f'"{names[run]}"' not in err.partition("\n")[0]:
            problems.append(f"the error line does not name {run} as \"{names[run]}\"")
        if not any(verb in command and names[run] in command for command in next_commands(err)):
            problems.append(f"no next line repeats the {verb} command with {names[run]}")
        if any(run in command for command in next_commands(err)):
            problems.append(f"a next line carries the id {run}")
    for reason in (GATE_REASON, PICTURE_REASON):
        if (reason in head) != (reason in err):
            problems.append(f"the reason clause is {'missing' if reason in head else 'added'}: {reason}")
    stated = dict(line.strip().split(": ", 1) for line in rest)
    for label in ("axes", "events"):
        if label in stated and listed_values(err, label) != [stated[label]]:
            problems.append(f"{label} listed as {listed_values(err, label)}, not {stated[label]}")
        if label not in stated and f"{label}:" in err:
            problems.append(f"{label} listed where the old words had none")
    return problems

# The inference line: the marker every negative assertion uses (a line prefix), and its lattice and A14 lines.
MARKER = "inferred: no event was given, so "
LATTICE_LINE = "inferred: no event was given, so the event set is held; the non-event is tripped, the most frequent outcome"
A14_LINE = "inferred: no event was given, so the event set is violated, timeout; the non-event is completed, the most frequent outcome"


def inference_line(events: Sequence[str], non_event: str) -> str:
    return f"inferred: no event was given, so the event set is {', '.join(events)}; the non-event is {non_event}, the most frequent outcome"


# Existing shipped sentences that the refusal order matrix pins as they are.
REPORT_FORMS = "report A B --x AXIS [...]  (two run ids: diff report) or report RUN --x AXIS [...]  (one run id: survival report)"
SERVE_FORM = "serve A B --event NAME --x AXIS [...]  (two run ids, always: a diff view)"

# Minted at f9b881f, the commit this file was frozen against (FR17, FR18). Named for what they
# pin: none of the names below ends in the suffix the exclusion-record sweeps count.
# Re-minted off the code at 173c25d: diff.py outside MultiDiffResult.to_markdown gains complementary_events and trade_line()'s complement branch; to_markdown itself is byte-identical to the bare tree's, checked. Read through this test's own measurement on the built tree, not predicted.
# Re-minted off the code at 662ceff (A10 declared expectations): diff.py outside MultiDiffResult.to_markdown: diff.py gains DeclaredSetMismatch(DiffError) and its refusal in diff() and multi_diff(), just before _pairing (A10 W9; _pairing is untouched); to_markdown itself is byte-identical to the bare tree's, checked. Read through this test's own measurement on the built tree, not predicted.
# PF0: no longer asserted. The rename changes diff.py, and no digest of a file this module
# changes can be frozen honestly before its build exists.
DIFF_OUTSIDE_TO_MARKDOWN_SHA256 = "0e1fa8a53987fbe8d2ac9b8fe32b4909341f7da9ffdeb3960972f19c497dcc87"
# Re-minted for truncation surfacing: report.py and viewer.py move, because that change edits both; store.py and tree.py do not.
# Re-minted again for the stored-trace read: store.py moves, because that change edits it; report.py, viewer.py and tree.py do not.
# CD: re-minted off the built `report.py` at `234513c`. D9's "no change to
# them" did not survive D3's "none" -- `_observation_cap`'s `isinstance(value, int)` filter drops
# the string -- so that one function lets the word through and nothing else in the file moved,
# which `test_cd_cap_declaration.py`'s digest over the file OUTSIDE `_observation_cap` is what
# pins. This literal and `test_s29_viewer.py`'s `REPORT_PY_SHA256` are the two carriers and moved
# together. The value before this change was `5cfdf03b...`, correct from the surfacing change
# through `46c5ac0`.
# Re-minted off the code at 173c25d: report.py is the built one (the wrap, the complement, mde_unchanged, LS16's Cells sentence); the whole-file sha256 of the built file. store.py and tree.py do not move. viewer.py is the built one (_LAYOUT's inert rule, the summary key, SCHEMA /6 and both refusals, the page order, the holes block, the unverified tail); the whole-file sha256 of the built file. Read through this test's own measurement on the built tree, not predicted.
# Re-minted off the code at 662ceff (A10 declared expectations): store.py gains RunManifest.declared, its thirteenth field, in to_dict() and from_dict() (A10 W4); report.py gains DeclarationCheck under TYPE_CHECKING, _run_declarations and _run_declaration, the declarations keyword on the three builders, and _provenance_lines printing an empty list as none (A10 W8); the whole-file sha256 of each built file. viewer.py and tree.py do not move. Read through this test's own measurement on the built tree, not predicted.
# PF0: no longer asserted. The rename changes all four files, and no digest of a file this module
# changes can be frozen honestly before its build exists.
UNTOUCHED_FILE_SHA256 = {
    "report.py": "06775d22522d897f8bf7c6086739e301ceb92baf5c0b9d9a806afecaa2962e61",
    "viewer.py": "6ed29eb6e77244d7b9d41de3004d08d89cb25f8af9e3cdfd98ba8f0ac22918ba",
    "store.py": "957c537786c3ef4e5b95abebec03af86bcaa99e8191c6856005f77cfe4159e51",
    "tree.py": "c0c011a3d194964a16f634d5450354645bb9132e0f47be192070a8daef9a8f3e",
}
MULTI_JSON_KEYS = [
    "alpha_star", "by_event", "comparison_verdict", "coverage", "dropped_a", "dropped_b", "errors_differ", "events",
    "flag_rule", "fragility", "fragility_exact", "fragility_flips", "fragility_note", "headline", "horizon",
    "inferred", "interval_level", "interval_rule", "intervals", "method", "n_flagged_only", "n_interval_only",
    "n_not_comparable", "n_rejected", "n_tests", "n_verdict_only", "non_event", "peeking", "q",
    "seed_identity_match", "t_unit", "threshold", "threshold_source", "trade_line", "trades", "truncated",
    "unpaired_analysis", "verdict_limit", "verdict_rule",
]
# PF4 re-freeze (PF4.34 to PF4.47): the comparison's JSON gains comparison_verdict, flag_rule,
# verdict_rule, n_flagged_only, verdict_limit, the fragility keys, errors_differ, peeking and
# interval_rule; the names are the reference build's, kept sorted as this list was.
# PF4 (PF4.5): the payload gains ``threshold`` and ``threshold_source``, the verdict's threshold and
# its source, which tests/test_pf4_surfaces.py names among the keys ``diff --json`` carries.
# A10 (W9): DeclaredSetMismatch is the one
# module-level name diff.py gains; the check itself sits in diff() and multi_diff(), before _pairing.
DIFF_MODULE_NAMES = frozenset(
    "CELLS_COLUMNS COVERAGE_COLUMNS DeclaredSetMismatch DiffError DiffResult EventDiff EventInferenceError INTERVAL_BASES "
    "INTERVAL_COLUMNS "
    "Method MultiDiffResult NotPairable SUMMARY_FIELDS UnitMismatch UnknownEvent UnpairedAnalysis _BASIS_BY_METHOD "
    "_CAUSES _CENSORED _CIF_EQUALITY_TOLERANCE _EVENT_SUMMARY_FIELDS _INVERSION_STEPS _MAX_EVENTS _METHODS "
    "_MULTI_SUMMARY_FIELDS _NO_OUTCOME_A _NO_OUTCOME_B _NO_OUTCOME_BOTH _ONLY_A _ONLY_B _PAIRED_METHODS _RAW_REQUIRED "
    "_REQUIRED _ROOT_RTOL _SCORE_RD _SCORE_RD_PAIRED _TRADES_COLUMNS _build_intervals _cause _coverage _discordant "
    "_endpoint _fisher _frame_horizon _indicator_frame _logrank _maximise _mcnemar _md_cell _nan_to_none _native "
    "_outcome_counts _pairing _power_two_proportion _require_alpha _require_arm _require_pairs _seed_identity _truncate "
    "_truncate_raw _unchanged_mde _validate_frame _validate_raw bh diff infer_events interval_rd interval_rd_paired "
    "mde_two_proportion multi_diff score_p_rd score_p_rd_paired".split()
)
# Re-minted for truncation surfacing: cli.py also imports report._observation_cap, for the limit ``inspect`` prints beside a cut.
# Re-minted for A10: cli.py calls steps.declaration_check beside _observation_counts and prints ``inspect``'s declaration block through report._provenance_lines.
CLI_IMPORTS = frozenset(
    {
        ("__future__", "annotations"), ("_typeshed", "SupportsWrite"), ("argparse", None), ("collections", "Counter"),
        ("collections.abc", "Callable"), ("collections.abc", "Mapping"), ("collections.abc", "Sequence"),
        ("dataclasses", None), ("dataclasses", "dataclass"), ("json", None), ("os", None), ("pandas", None),
        ("pathlib", "Path"), ("poisson_prove", "__version__"), ("poisson_prove._resolve", "resolve"),
        ("poisson_prove.diff", "COVERAGE_COLUMNS"), ("poisson_prove.diff", "DiffError"), ("poisson_prove.diff", "EventInferenceError"),
        ("poisson_prove.diff", "Method"), ("poisson_prove.diff", "MultiDiffResult"), ("poisson_prove.diff", "UnknownEvent"),
        ("poisson_prove.diff", "_CAUSES"), ("poisson_prove.diff", "_PAIRED_METHODS"), ("poisson_prove.diff", "_md_cell"),
        ("poisson_prove.diff", "infer_events"), ("poisson_prove.diff", "multi_diff"), ("poisson_prove.executor", "ExecutorError"),
        ("poisson_prove.executor", "Plan"), ("poisson_prove.executor", "RunSummary"), ("poisson_prove.executor", "check_power"),
        ("poisson_prove.executor", "plan"), ("poisson_prove.executor", "preflight"), ("poisson_prove.executor", "run_local"),
        ("poisson_prove.executor_modal", "ImageSpec"), ("poisson_prove.executor_modal", "ModalOptions"),
        ("poisson_prove.executor_modal", "ModalTarget"), ("poisson_prove.executor_modal", "preflight_modal"),
        ("poisson_prove.executor_modal", "run_modal"),
        ("poisson_prove.executor_burla", "BurlaOptions"), ("poisson_prove.executor_burla", "preflight_burla"), ("poisson_prove.executor_burla", "run_burla"),
        ("poisson_prove.paired", "Declaration"), ("poisson_prove.paired", "PairedError"), ("poisson_prove.paired", "_Bundle"),
        ("poisson_prove.paired", "_artifact_text"), ("poisson_prove.paired", "_bundle"), ("poisson_prove.paired", "_cost_block"),
        ("poisson_prove.paired", "_fold_html"), ("poisson_prove.paired", "_fold_markdown"), ("poisson_prove.paired", "cost"),
        ("poisson_prove.report", "MultiReport"), ("poisson_prove.report", "ReportError"),
        ("poisson_prove.report", "ReportSpec"), ("poisson_prove.report", "SurvivalReport"), ("poisson_prove.report", "_interval_lines"), ("poisson_prove.report", "_observation_cap"),
        ("poisson_prove.report", "_provenance_lines"), ("poisson_prove.report", "build_multi_report"), ("poisson_prove.report", "build_survival_report"),
        ("poisson_prove.sampler", "SamplerError"), ("poisson_prove.sampler", "SweepSpec"), ("poisson_prove.steps", "declaration_check"), ("poisson_prove.store", "RunManifest"),
        ("poisson_prove.store", "Store"), ("poisson_prove.store", "StoreError"), ("poisson_prove.survival", "SurvivalError"),
        ("poisson_prove.survival", "cell_table"), ("poisson_prove.survival", "competing_set"), ("poisson_prove.trace", "Trace"),
        ("poisson_prove.trace", "TraceValidationError"), ("poisson_prove.tree", "Bound"), ("poisson_prove.tree", "CellFamily"),
        ("poisson_prove.tree", "CellResult"), ("poisson_prove.tree", "DEFAULT_DEPTH"), ("poisson_prove.tree", "DEFAULT_MAX_GROUP_MDE"),
        ("poisson_prove.tree", "DEFAULT_PERMUTATIONS"), ("poisson_prove.tree", "DEFAULT_SEED"), ("poisson_prove.tree", "DEPTHS"),
        ("poisson_prove.tree", "FaultLines"), ("poisson_prove.tree", "GroupResult"), ("poisson_prove.tree", "Grouping"),
        ("poisson_prove.tree", "Leaves"), ("poisson_prove.tree", "RootResult"), ("poisson_prove.tree", "TASK_FAMILY_KEYS"),
        ("poisson_prove.tree", "TRACE_GROUPINGS"), ("poisson_prove.tree", "TreeResult"), ("poisson_prove.tree", "WHOLE_GRID"),
        ("poisson_prove.tree", "tree"), ("poisson_prove.viewer", "ViewerError"), ("poisson_prove.viewer", "_HOST"),
        ("poisson_prove.viewer", "build_structure"), ("poisson_prove.viewer", "render_html"), ("poisson_prove.viewer", "serve_page"),
        ("sys", None), ("tomllib", None), ("traceback", None), ("typing", "Any"), ("typing", "NoReturn"),
        ("typing", "TYPE_CHECKING"), ("typing", "TextIO"), ("typing", "cast"),
    }
)

#: Every name ``cli`` binds that E3, E1 or the gate could reach for work; armed by ``arm_tripwires``.
# PF5 (PF5.7): the comparison and the tree are the core's work, which
# ``cli`` no longer binds; building either result is the work, so the two result types are armed
# where they are made (``arm_work_tripwires``) and ``cli`` keeps only its renderers' names.
WORK_NAMES = ("build_multi_report", "build_survival_report", "build_structure", "serve_page")


# ---------- harness ----------


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


def run_cli(argv: Sequence[str]) -> Result:
    """Drive ``cli.main`` in-process. The seed-identity warning is a library warning that goes to
    the real stderr and never into ``err``; it is silenced so a run's own stderr is what is read."""
    out, err = StringIO(), StringIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpairedAnalysis)
        code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def arm_tripwires(monkeypatch: pytest.MonkeyPatch, *names: str) -> list[str]:
    """Replace each named binding of ``cli`` with a function that records the call and raises."""
    calls: list[str] = []
    for name in names:

        def trip(*args: Any, _name: str = name, **kwargs: Any) -> Any:
            calls.append(_name)
            raise AssertionError(f"{_name} was called")

        monkeypatch.setattr(cli, name, trip)
    return calls


def arm_work_tripwires(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """PF5: building a comparison or a tree, the core's work, records the call
    and raises, wherever the core does it."""
    from poisson_prove.tree import TreeResult

    calls: list[str] = []
    for result_type in (MultiDiffResult, TreeResult):

        def trip(self: Any, *args: Any, _name: str = result_type.__name__, **kwargs: Any) -> None:
            calls.append(_name)
            raise AssertionError(f"a {_name} was built")

        monkeypatch.setattr(result_type, "__init__", trip)
    return calls


def arm_gate_tripwire(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """``MultiDiffResult.check`` raises and no comparison can be built: the gate can never run.
    PF5: the comparison is built by the core, so the tripwire is on building
    it, where ``cli.multi_diff`` was."""
    calls: list[str] = arm_work_tripwires(monkeypatch)

    def trip_check(self: MultiDiffResult, *args: Any, **kwargs: Any) -> bool:
        calls.append("MultiDiffResult.check")
        raise AssertionError("the gate was reached")

    monkeypatch.setattr(MultiDiffResult, "check", trip_check)
    return calls


def listing(root: Path) -> list[str]:
    """Everything under ``root``, as relative paths: the store's directory listing."""
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


# ---------- synthetic stores, written through the store's own writer ----------


def manifest(run_id: str, *, salt: str = "syn", axis_types: Mapping[str, str] | None = None) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types or {"cell": "categorical"}), backend="synthetic",  # type: ignore[arg-type]
        environment={},
    )


def seed_of(config: Mapping[str, Any], replicate_index: int) -> int:
    """A stored seed that is a function of ``(config, replicate_index)`` and of nothing else."""
    return 1000 * (int(config_hash(config)[:6], 16) % 100_000) + replicate_index


NON_EVENTS = {"ok", "survived", "completed"}


def write_run(
    store: Store, run_id: str, cells: Sequence[tuple[Mapping[str, Any], Mapping[str, int], Mapping[str, int]]],
    *, salt: str = "syn", axis_types: Mapping[str, str] | None = None,
) -> None:
    """A complete run. Per cell ``(config, {outcome: rows}, {error: rows})``: outcome rows first, then
    errored rows, replicate indices running over both. Events sit at t=3, non-events at the horizon."""
    store.create_run(manifest(run_id, salt=salt, axis_types=axis_types))
    records = []
    for config, outcomes, errors in cells:
        k = 0
        for name, n in outcomes.items():
            for _ in range(n):
                t = HORIZON if name in NON_EVENTS else 3.0
                records.append(EpisodeRecord.from_episode(
                    Episode(outcome=name, t=t, horizon=HORIZON), run_id=run_id, config=dict(config),
                    seed=seed_of(config, k), replicate_index=k, wall_time=0.0,
                ))
                k += 1
        for error, n in errors.items():
            for _ in range(n):
                records.append(EpisodeRecord.errored(
                    run_id=run_id, config=dict(config), seed=seed_of(config, k), replicate_index=k, error=error, wall_time=0.0,
                ))
                k += 1
    store.append(run_id, records)
    store.mark_complete(run_id)


def fell_run(store: Store, run_id: str, fell_per_cell: Mapping[float, int], *, n: int = 32) -> None:
    """One cell per ``x``; ``fell_per_cell[x]`` of ``n`` rows fell and the rest survived."""
    write_run(
        store, run_id, [({"x": x}, {"fell": f, "survived": n - f}, {}) for x, f in fell_per_cell.items()],
        axis_types={"x": "continuous"},
    )


def one_run_store(tmp_path: Path) -> Path:
    root = tmp_path / "one-run"
    fell_run(Store(root), "only", {1.0: 4})
    return root


# ---------- fixtures ----------


@dataclass(frozen=True)
class MockPair:
    root: Path
    a: str
    b: str


@pytest.fixture(scope="module")
def mock_pair(tmp_path_factory: pytest.TempPathFactory) -> MockPair:
    """The two quickstart runs under the S12 salt: three outcomes, ``completed`` the non-event."""
    root = tmp_path_factory.mktemp("mock-store")
    first = run_cli(["--store", str(root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--salt", QUICKSTART_SALT, "--yes"])
    assert first.code == 0, first.err
    # A sweep no longer ends in a ``run_id:`` line: each sweep's run is the
    # one the store gained.
    (a,) = Store(root).runs()
    second = run_cli(["--store", str(root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", PATCHED, "--pair-with", a, "--yes"])
    assert second.code == 0, second.err
    (b,) = set(Store(root).runs()) - {a}
    return MockPair(root, a, b)


def mock_e3(pair: MockPair) -> tuple[list[str], str]:
    """The mock pair's ``report`` without ``--x``: its axes, and events read ``completed, timeout, violated``."""
    return (
        ["--store", str(pair.root), "report", pair.a, pair.b, "--y", "task_id"],
        f"error: report requires --x AXIS, which was not given. {pair.a} and {pair.b} carry:\n"
        "  axes: task_id, tool_fail_rate\n"
        "  events: completed, timeout, violated\n",
    )


# ---------- FR1 to FR7: E1, the store ----------


def read_argvs(store: str, out: Path) -> dict[str, list[str]]:
    """Every store-reading invocation, with every other argument valid for the lattice pair."""
    s = ["--store", store]
    o = ["--out", str(out)]
    return {
        "runs": [*s, "runs"],
        "diff": [*s, "diff", LATTICE_A, LATTICE_B, "--event", "tripped"],
        "report pair": [*s, "report", LATTICE_A, LATTICE_B, "--event", "tripped", "--x", LATTICE_X, "--y", LATTICE_Y, *o],
        "report single run": [*s, "report", LATTICE_A, "--event", "tripped", "--x", LATTICE_X, "--y", LATTICE_Y, *o],
        "check": [*s, "check", LATTICE_A, LATTICE_B, "--event", "tripped"],
        "serve": [*s, "serve", LATTICE_A, LATTICE_B, "--event", "tripped", "--x", LATTICE_X],
        "serve --json": [*s, "serve", LATTICE_A, LATTICE_B, "--event", "tripped", "--x", LATTICE_X, "--json"],
        "inspect": [*s, "inspect", LATTICE_A, "--event", "tripped"],
    }


def verb_of(label: str) -> str:
    return label.split()[0]


def test_fr1_a_missing_store_refuses_on_every_verb_that_reads_it(tmp_path: Path) -> None:
    """One fresh root per invocation, so a verb that made the root could not change what the next one sees."""
    for index, label in enumerate(read_argvs("", tmp_path)):
        root = str(tmp_path / f"nowhere-{index}")
        r = run_cli(read_argvs(root, tmp_path / "out")[label])
        # A refusal exits 1.
        assert r.code == 1, (label, r)
        assert r.out == "", (label, r.out)
        assert missing_problems(r.err, root, FROM_FLAG, verb_of(label)) == [], (label, r.err)
        assert "Traceback" not in r.err, label


@pytest.mark.parametrize("verb", ["runs", "diff"])
def test_fr1_a_regular_file_is_not_a_store_so_is_dir_and_not_exists(tmp_path: Path, verb: str) -> None:
    """A file at the root passes ``exists()`` and fails ``is_dir()``; only the second is the right test."""
    root = tmp_path / "a-file"
    root.write_text("not a store\n")
    r = run_cli(read_argvs(str(root), tmp_path / "out")[verb])
    # A refusal exits 1.
    assert r.code == 1, r
    assert r.out == "" and missing_problems(r.err, str(root), FROM_FLAG, verb) == [], r


def make_empty_root(tmp_path: Path) -> Path:
    """An existing directory holding one stray file and one subdirectory, and no manifest.json."""
    root = tmp_path / "empty"
    (root / "subdir").mkdir(parents=True)
    (root / "stray.txt").write_text("nothing here\n")
    (root / "subdir" / "notes.txt").write_text("nor here\n")
    return root


def test_fr2_an_empty_store_refuses_on_every_read_verb_but_runs(tmp_path: Path) -> None:
    root = make_empty_root(tmp_path)
    for label, argv in read_argvs(str(root), tmp_path / "out").items():
        if label == "runs":
            continue
        r = run_cli(argv)
        # A refusal exits 1.
        assert r.code == 1, (label, r)
        assert r.out == "", (label, r.out)
        assert empty_problems(r.err, str(root), FROM_FLAG, verb_of(label)) == [], (label, r.err)
        assert "unknown run" not in r.err, label


def test_fr3_runs_on_an_empty_store_exits_zero_says_so_on_stderr_and_keeps_its_stdout(tmp_path: Path) -> None:
    root = make_empty_root(tmp_path)
    r = run_cli(["--store", str(root), "runs"])
    assert r.code == 0, r
    # PF2: the empty store is runs' verdict line and its next line, both on stdout, in
    # place of the header and the stderr note; nothing is on stderr.
    assert empty_runs_problems(r.out, str(root)) == [], r.out
    assert r.err == "", r.err


@pytest.mark.parametrize("how", ["flag", "env", "default", "empty env"])
def test_fr4_the_source_clause_is_the_resolution_that_happened_and_only_that_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    flag, env = tmp_path / "flag-root", tmp_path / "env-root"
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    if how == "flag":
        monkeypatch.setenv("POISSON_PROVE_STORE", str(env))
        argv, root, source = ["--store", str(flag), "runs"], str(flag), FROM_FLAG
    elif how == "env":
        monkeypatch.setenv("POISSON_PROVE_STORE", str(env))
        argv, root, source = ["runs"], str(env), FROM_ENV
    elif how == "default":
        argv, root, source = ["runs"], "prove-runs", FROM_DEFAULT
    else:
        monkeypatch.setenv("POISSON_PROVE_STORE", "")
        argv, root, source = ["runs"], "prove-runs", FROM_DEFAULT
    r = run_cli(argv)
    # A refusal exits 1.
    assert r.code == 1 and r.out == "", r
    assert missing_problems(r.err, root, source, "runs") == [], r.err
    assert [clause for clause in SOURCES if clause in r.err] == [source], r.err
    if how == "flag":
        assert str(env) not in r.err


@pytest.mark.parametrize("how", ["flag", "env", "default"])
def test_fr4_the_empty_store_messages_name_the_same_three_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    """E on a read verb and E-runs on ``runs``, each in each source form: FR4's clause for the two templates
    its own runs (on a missing root) cannot reach."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    if how == "flag":
        root, source, flags = tmp_path / "flag-root", FROM_FLAG, ["--store", str(tmp_path / "flag-root")]
    elif how == "env":
        root, source, flags = tmp_path / "env-root", FROM_ENV, []
        monkeypatch.setenv("POISSON_PROVE_STORE", str(root))
    else:
        root, source, flags = tmp_path / "prove-runs", FROM_DEFAULT, []
    root.mkdir()
    shown = str(root) if how != "default" else "prove-runs"
    read = run_cli([*flags, "diff", LATTICE_A, LATTICE_B, "--event", "tripped"])
    # A refusal exits 1.
    assert read.code == 1 and read.out == "" and empty_problems(read.err, shown, source, "diff") == [], read
    listed_runs = run_cli([*flags, "runs"])
    # PF2: runs on an empty store says so on stdout (its verdict line and a next line)
    # and nothing on stderr; the verdict line carries no source clause, so only the read verb's refusal
    # is held to the source that happened.
    assert listed_runs.code == 0 and listed_runs.err == "" and empty_runs_problems(listed_runs.out, shown) == [], listed_runs
    assert [clause for clause in SOURCES if clause in read.err] == [source]


@pytest.mark.parametrize("which", ["runs on the lattice", "runs on a one-run store", "inspect on the lattice"])
def test_fr5_a_populated_store_is_silent_on_stderr(tmp_path: Path, which: str) -> None:
    """Green before and after: the fence around FR1 to FR3, and no evidence the build did anything."""
    argv = {
        "runs on the lattice": ["--store", str(LATTICE_ROOT), "runs"],
        "runs on a one-run store": ["--store", str(one_run_store(tmp_path)), "runs"],
        "inspect on the lattice": ["--store", str(LATTICE_ROOT), "inspect", LATTICE_A, "--event", "tripped", "--limit", "1"],
    }[which]
    r = run_cli(argv)
    assert r.code == 0 and r.err == "", r


def test_fr5_an_unknown_run_in_a_populated_store_keeps_its_message() -> None:
    """Green before and after. A7's verb digests (P7-10) carry the rest of FR5's clause."""
    r = run_cli(["--store", str(LATTICE_ROOT), "diff", LATTICE_A, "no-such-run", "--event", "tripped"])
    # A refusal exits 1, and names the run bare, never as a Python repr.
    assert r.code == 1 and r.out == "" and unknown_run_problems(r.err, "no-such-run") == [], r


def test_fr6_refusing_never_creates_the_missing_root(tmp_path: Path) -> None:
    root = tmp_path / "must-stay-absent"
    for label, argv in read_argvs(str(root), tmp_path / "out").items():
        r = run_cli(argv)
        # A refusal exits 1.
        assert r.code == 1, (label, r)
        assert not root.exists(), label
    assert listing(tmp_path) == [], listing(tmp_path)


def test_fr6_refusing_and_listing_never_touch_an_empty_root(tmp_path: Path) -> None:
    root = make_empty_root(tmp_path)
    before = listing(root)
    for label, argv in read_argvs(str(root), tmp_path / "out").items():
        r = run_cli(argv)
        # A refusal exits 1.
        assert r.code == (0 if label == "runs" else 1), (label, r)
        # PF2: runs says the store is empty on stdout now, every other verb on stderr.
        assert (r.out if label == "runs" else r.err) != "", label
        assert listing(root) == before, label
    assert listing(tmp_path) == ["empty", *[f"empty/{p}" for p in before]], listing(tmp_path)


def test_fr6_sweep_is_never_gated_and_creates_the_store(tmp_path: Path) -> None:
    """Green before and after: ``sweep`` is the verb that makes a store, so no check may precede it."""
    for root in (tmp_path / "missing-root", make_empty_root(tmp_path)):
        r = run_cli(["--store", str(root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT, "--yes"])
        assert r.code == 0, r
        assert len(Store(root).runs()) == 1, root


@pytest.mark.parametrize("name", ["with a space", "it's $HOME"])
def test_fr7_the_create_line_is_a_command_that_survives_a_shell(tmp_path: Path, name: str) -> None:
    root = tmp_path / name
    r = run_cli(["--store", str(root), "diff", LATTICE_A, LATTICE_B, "--event", "tripped"])
    # A refusal exits 1, and its create hint is a command on a next line.
    assert r.code == 1, r
    assert ["poisson-prove", "--store", str(root), "sweep", "SPEC.toml", "--target", "pkg.module:rollout"] in hinted_commands(r.err), r.err
    assert missing_problems(r.err, str(root), FROM_FLAG, "diff") == [], r.err


def test_fr7_the_empty_store_hint_lines_are_commands_that_survive_a_shell(tmp_path: Path) -> None:
    root = tmp_path / "an empty store"
    root.mkdir()
    expected = ["poisson-prove", "--store", str(root), "sweep", "SPEC.toml", "--target", "pkg.module:rollout"]
    read = run_cli(["--store", str(root), "check", LATTICE_A, LATTICE_B, "--event", "tripped"])
    # A refusal exits 1, and its hint is a command on a next line.
    assert read.code == 1 and expected in hinted_commands(read.err), read.err
    listed = run_cli(["--store", str(root), "runs"])
    # PF2: runs' hint is its next line on stdout now, and stderr is empty.
    assert listed.code == 0 and listed.err == "" and expected in hinted_commands(listed.out), listed
    assert empty_problems(read.err, str(root), FROM_FLAG, "check") == [] and empty_runs_problems(listed.out, str(root)) == []


# ---------- FR8 to FR13: E3, the missing flag ----------


def lattice_argv(label: str, *extra: str) -> list[str]:
    return ["--store", str(LATTICE_ROOT), *E3_LATTICE[label][0], *extra]


@pytest.mark.parametrize("label", ["report pair, no --x", "report single run, no --x"])
def test_fr8_report_without_x_lists_the_axes_and_events_instead_of_failing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, label: str) -> None:
    monkeypatch.chdir(tmp_path)
    r = run_cli(lattice_argv(label))
    # A refusal exits 1; its facts, not its line layout.
    assert r.code == 1 and r.out == "", r
    # PF2: the runs are named by name in the error line and the next line.
    assert e3_problems(r.err, E3_LATTICE[label][1], LATTICE_NAMES) == [], r.err
    assert "usage:" not in r.err
    assert listing(tmp_path) == [], "the default --out directory was created"


def test_fr8_report_without_x_lists_on_the_mock_pair_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_pair: MockPair) -> None:
    names = run_names(mock_pair.root)
    monkeypatch.chdir(tmp_path)
    argv, expected = mock_e3(mock_pair)
    r = run_cli(argv)
    # A refusal exits 1; its facts, not its line layout.
    # PF2: the runs are named by name in the error line and the next line.
    assert r.code == 1 and r.out == "" and e3_problems(r.err, expected, names) == [], r
    assert "usage:" not in r.err
    assert listing(tmp_path) == []


@pytest.mark.parametrize("as_json", [False, True], ids=["plain", "json"])
@pytest.mark.parametrize("label", SERVE_ROWS)
def test_fr9_serve_without_x_or_event_lists_instead_of_failing(monkeypatch: pytest.MonkeyPatch, label: str, as_json: bool) -> None:
    calls = arm_tripwires(monkeypatch, "serve_page")
    r = run_cli(lattice_argv(label, *(["--json"] if as_json else [])))
    # A refusal exits 1; its facts, not its line layout.
    assert r.code == 1 and r.out == "", r
    # PF2: the runs are named by name in the error line and the next line.
    assert e3_problems(r.err, E3_LATTICE[label][1], LATTICE_NAMES) == [], r.err
    assert calls == []


@pytest.mark.parametrize("label", ["check, no --event", "inspect, no --event"])
def test_fr10_check_and_inspect_without_event_list_and_never_suggest(label: str) -> None:
    r = run_cli(lattice_argv(label))
    # A refusal exits 1; its facts, not its line layout.
    assert r.code == 1 and r.out == "", r
    # PF2: the runs are named by name in the error line and the next line.
    assert e3_problems(r.err, E3_LATTICE[label][1], LATTICE_NAMES) == [], r.err
    assert "Inferred events" not in r.err and "Inferred events" not in r.out


TIMEOUT_CELLS = [({"cell": "c0"}, {"fell": 4, "ok": 6}, {"timeout": 3})]
QUIET_CELLS = [({"cell": "c0"}, {"fell": 4, "ok": 6}, {})]
OUTCOME_TIMEOUT_CELLS = [({"cell": "c0"}, {"fell": 4, "timeout": 6}, {"timeout": 3})]


@pytest.mark.parametrize(
    ("cells", "events"),
    [(TIMEOUT_CELLS, "episode_timeout, fell, ok"), (QUIET_CELLS, "fell, ok"), (OUTCOME_TIMEOUT_CELLS, "episode_timeout, fell, timeout")],
    ids=["timed-out rows and timeout is not an outcome", "no timed-out rows", "timed-out rows and timeout is already an outcome"],
)
def test_fr10_inspect_adds_episode_timeout_only_when_rows_timed_out(tmp_path: Path, cells: list[Any], events: str) -> None:
    write_run(Store(tmp_path), "t1", cells)
    r = run_cli(["--store", str(tmp_path), "inspect", "t1"])
    # A refusal exits 1; its facts, not its line layout.
    assert r.code == 1 and r.out == "", r
    # PF2: the run is named by name in the error line and the next line.
    assert e3_problems(r.err, f"error: inspect requires --event NAME, which was not given. t1 carries:\n  events: {events}\n", run_names(tmp_path)) == [], r.err


# FR11: the listed vocabulary is the stored vocabulary.

KEYS = ("a", "b", "c", "d")
LABELS = ("fell", "ok", "late", "slow")
ERRORS = ("timeout", "boom")
PROPERTY = settings(max_examples=60, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])


@st.composite
def run_specs(draw: st.DrawFn) -> list[tuple[dict[str, Any], str]]:
    """The rows of one run: a config over 1-4 of the four keys, and an outcome label or an error."""
    keys = draw(st.lists(st.sampled_from(KEYS), min_size=1, max_size=4, unique=True))
    labels = draw(st.lists(st.sampled_from(LABELS), min_size=1, max_size=4, unique=True))
    rows = draw(st.lists(st.tuples(st.sampled_from([0, 1]), st.sampled_from([*labels, *[f"!{e}" for e in ERRORS]])), min_size=1, max_size=8))
    return [({key: value for key in keys}, name) for value, name in rows]


def write_spec(store: Store, run_id: str, rows: Sequence[tuple[dict[str, Any], str]], *, axis_types: Mapping[str, str] | None = None) -> None:
    store.create_run(manifest(run_id, axis_types=axis_types))
    seen: dict[str, int] = {}
    records = []
    for config, name in rows:
        h = config_hash(config)
        k = seen[h] = seen.get(h, -1) + 1
        if name.startswith("!"):
            records.append(EpisodeRecord.errored(run_id=run_id, config=config, seed=seed_of(config, k), replicate_index=k, error=name[1:], wall_time=0.0))
        else:
            records.append(EpisodeRecord.from_episode(
                Episode(outcome=name, t=3.0, horizon=HORIZON), run_id=run_id, config=config, seed=seed_of(config, k), replicate_index=k, wall_time=0.0,
            ))
    store.append(run_id, records)
    store.mark_complete(run_id)


def listed(err: str, label: str) -> str:
    # The list may sit inside the error line now, not on an indented line of its own.
    values = listed_values(err, label)
    assert len(values) == 1, (label, err)
    return values[0]


@PROPERTY
@given(a=run_specs(), b=run_specs())
def test_fr11_the_listed_axes_and_events_are_the_stored_ones(a: list[Any], b: list[Any]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(tmp)
        write_spec(store, "ra", a)
        write_spec(store, "rb", b)
        fa, fb = store.read("ra", meta=False), store.read("rb", meta=False)
        axes = sorted({str(k) for frame in (fa, fb) for config in frame["config"] for k in config})
        events = list(competing_set(fa, fb))
        for verb, argv in (("report", ["report", "ra", "rb"]), ("check", ["check", "ra", "rb"])):
            r = run_cli(["--store", tmp, *argv])
            # A refusal exits 1.
            assert r.code == 1 and r.out == "", (verb, r)
            assert listed(r.err, "events") == (", ".join(events) or "none stored"), (verb, r.err)
            if verb == "report":
                assert listed(r.err, "axes") == ", ".join(axes), r.err
            else:
                assert listed_values(r.err, "axes") == [], r.err


@PROPERTY
@given(a=run_specs())
def test_fr11_the_listed_events_of_a_single_run_are_its_outcomes_and_episode_timeout_only_when_a_row_timed_out(a: list[Any]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(tmp)
        write_spec(store, "ra", a)
        frame = store.read("ra", meta=False)
        events = set(competing_set(frame)) | ({"episode_timeout"} if store.tally("ra").timed_out else set())
        r = run_cli(["--store", tmp, "inspect", "ra"])
        # A refusal exits 1.
        assert r.code == 1 and r.out == "", r
        assert listed(r.err, "events") == (", ".join(sorted(events)) or "none stored"), r.err


def known_keys_of(err: str) -> list[str]:
    # The keys are shown as their items, never as a Python list.
    match = re.search(r"known keys: (.+?)\.?$", err, flags=re.MULTILINE)
    assert match, err
    return match.group(1).split(", ")


def present_of(err: str) -> str:
    # The list may be followed by next lines now.
    match = re.search(r"Present: (.*?)\.?$", err, flags=re.MULTILINE)
    assert match, err
    return match.group(1)


def pair_of(which: str, request: pytest.FixtureRequest) -> tuple[list[str], str, str, str]:
    """``--store``, both run ids and a known event, for the lattice pair or for the mock pair."""
    if which == "lattice":
        return ["--store", str(LATTICE_ROOT)], LATTICE_A, LATTICE_B, "tripped"
    pair: MockPair = request.getfixturevalue("mock_pair")
    return ["--store", str(pair.root)], pair.a, pair.b, "violated"


@pytest.mark.parametrize("which", ["lattice", "mock"])
def test_fr11_the_listed_axes_equal_the_known_keys_the_axis_error_prints(which: str, request: pytest.FixtureRequest) -> None:
    """Both lists are read off live output: E3's ``axes:`` line, and the ``known keys`` of the error a wrong ``--x``
    provokes. The two agree wherever every config is compared."""
    store, a, b, event = pair_of(which, request)
    listing_run = run_cli([*store, "report", a, b])
    # A refusal exits 1.
    assert listing_run.code == 1, listing_run
    wrong = run_cli([*store, "serve", a, b, "--event", event, "--x", "nope", "--permutations", "50"])
    assert wrong.code == 1, wrong
    assert ", ".join(known_keys_of(wrong.err)) == listed(listing_run.err, "axes")


@pytest.mark.parametrize("which", ["lattice", "mock"])
def test_fr11_the_listed_events_equal_the_present_list_the_unknown_event_error_prints(which: str, request: pytest.FixtureRequest) -> None:
    store, a, b, _ = pair_of(which, request)
    listing_run = run_cli([*store, "check", a, b])
    # A refusal exits 1.
    assert listing_run.code == 1, listing_run
    wrong = run_cli([*store, "check", a, b, "--event", "nope"])
    assert wrong.code == 1, wrong
    assert present_of(wrong.err) == listed(listing_run.err, "events")


def test_fr11_the_axes_are_the_config_keys_and_never_the_manifests_axis_types(tmp_path: Path) -> None:
    """The one fixture that tells D8 from its mutant: no store ``sweep`` writes can disagree with itself."""
    store = Store(tmp_path)
    for run_id in ("dis-a", "dis-b"):
        write_run(
            store, run_id, [({"real_a": 0, "real_b": 1}, {"fell": 2, "ok": 3}, {})],
            axis_types={"declared_only": "categorical"},
        )
    r = run_cli(["--store", str(tmp_path), "report", "dis-a", "dis-b"])
    # A refusal exits 1; its facts, not its line layout.
    assert r.code == 1 and r.out == "", r
    assert e3_problems(r.err, (
        "error: report requires --x AXIS, which was not given. dis-a and dis-b carry:\n"
        "  axes: real_a, real_b\n"
        "  events: fell, ok\n"
    ), run_names(tmp_path)) == [], r.err  # PF2: the runs are named by name.


def e3_cases(pair: MockPair) -> list[tuple[str, list[str], str, Mapping[str, str]]]:
    # PF2: each case carries the names of its runs, read before any tripwire is armed.
    cases = [(label, ["--store", str(LATTICE_ROOT), *argv], err, LATTICE_NAMES) for label, (argv, err) in E3_LATTICE.items()]
    argv, err = mock_e3(pair)
    return [*cases, ("mock report pair, no --x", argv, err, run_names(pair.root))]


def test_fr12_the_listing_does_no_work(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mock_pair: MockPair) -> None:
    monkeypatch.chdir(tmp_path)
    cases = e3_cases(mock_pair)
    # PF5: the renderers ``cli`` binds, and the core's work, both armed.
    calls_cli = arm_tripwires(monkeypatch, *WORK_NAMES)
    calls_core = arm_work_tripwires(monkeypatch)
    for label, argv, expected, names in cases:
        r = run_cli(argv)
        # A refusal exits 1; its facts, not its line layout.
        # PF2: the runs are named by name in the error line and the next line.
        assert r.code == 1 and r.out == "" and e3_problems(r.err, expected, names) == [], (label, r)
    assert calls_cli == [] and calls_core == [], (calls_cli, calls_core)
    assert listing(tmp_path) == []


@pytest.mark.parametrize("label", ["report pair, no --x", "report single run, no --x"])
def test_fr12_a_non_empty_out_does_not_pre_empt_the_listing(tmp_path: Path, label: str) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("already here\n")
    r = run_cli(lattice_argv(label, "--out", str(out)))
    # A refusal exits 1; its facts, not its line layout.
    # PF2: the runs are named by name in the error line and the next line.
    assert r.code == 1 and r.out == "" and e3_problems(r.err, E3_LATTICE[label][1], LATTICE_NAMES) == [], r
    # The problem is stated on the error line; a next line is a command and may repeat the given flags.
    assert "--out" not in r.err.partition("\n")[0]
    assert listing(out) == ["keep.txt"]


ARITY = {
    "report": ("error: report takes one or two run ids, got 3: " + REPORT_FORMS + "\n", ["report", LATTICE_A, LATTICE_B, LATTICE_A]),
    "serve": ("error: serve takes two run ids, got 1: " + SERVE_FORM + "\n", ["serve", LATTICE_A]),
}
BARE = {"report": ["report", LATTICE_A, LATTICE_B], "serve": ["serve", LATTICE_A, LATTICE_B], "check": ["check", LATTICE_A, LATTICE_B], "inspect": ["inspect", LATTICE_A]}
BARE_UNKNOWN = {"report": ["report", LATTICE_A, "no-such-run"], "serve": ["serve", LATTICE_A, "no-such-run"], "check": ["check", LATTICE_A, "no-such-run"], "inspect": ["inspect", "no-such-run"]}


@pytest.mark.parametrize("verb", ["report", "serve", "check", "inspect"])
def test_fr12_a_missing_store_outranks_a_missing_flag(tmp_path: Path, verb: str) -> None:
    root = str(tmp_path / "nowhere")
    r = run_cli(["--store", root, *BARE[verb]])
    # A refusal exits 1.
    assert r.code == 1 and r.out == "" and missing_problems(r.err, root, FROM_FLAG, verb) == [], r


@pytest.mark.parametrize("verb", ["report", "serve", "check", "inspect"])
def test_fr12_an_empty_store_outranks_a_missing_flag(tmp_path: Path, verb: str) -> None:
    root = make_empty_root(tmp_path)
    r = run_cli(["--store", str(root), *BARE[verb]])
    # A refusal exits 1.
    assert r.code == 1 and r.out == "" and empty_problems(r.err, str(root), FROM_FLAG, verb) == [], r


@pytest.mark.parametrize("verb", ["report", "serve"])
def test_fr12_a_wrong_arity_outranks_a_missing_flag(verb: str) -> None:
    message, argv = ARITY[verb]
    r = run_cli(["--store", str(LATTICE_ROOT), *argv])
    # A wrong command line still exits 2; its error line is followed only by next lines.
    assert r.code == 2 and r.out == "" and refusal_shape(r.err) == [], r
    # PF2: no runs is now allowed too, so the arity sentence changes; its facts are
    # pinned instead of its old words: one error line, naming the verb and the count given, and not the
    # missing-flag listing it outranks.
    first = r.err.partition("\n")[0]
    count = re.search(r"got \d+", message)
    assert count and [line for line in r.err.splitlines() if line.startswith("error: ")] == [first], r.err
    assert first.startswith(f"error: {message.split()[1]} ") and count.group(0) in first, first
    assert "requires" not in r.err and "axes:" not in r.err and "events:" not in r.err, r.err


@pytest.mark.parametrize("verb", ["report", "serve", "check", "inspect"])
def test_fr12_an_unknown_run_outranks_a_missing_flag(verb: str) -> None:
    r = run_cli(["--store", str(LATTICE_ROOT), *BARE_UNKNOWN[verb]])
    # A refusal exits 1, and names the run bare, never as a Python repr.
    assert r.code == 1 and r.out == "" and unknown_run_problems(r.err, "no-such-run") == [], r


# FR13: the parser.


def help_text(verb: str) -> str:
    r = run_cli([verb, "--help"])
    assert r.code == 0, r
    return r.out


def usage_of(text: str) -> str:
    block = text.split("\n\n", 1)[0]
    assert block.startswith("usage:"), block
    return " ".join(block.split())


def help_entries(text: str) -> dict[str, str]:
    """Each long option's help entry, its wrapped lines joined and its spacing collapsed."""
    entries: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        head = re.match(r"^  (--[a-z][a-z-]*)", line)
        if head:
            current = head.group(1)
            entries[current] = [line.strip()]
        elif current is not None and line.startswith("    "):
            entries[current].append(line.strip())
        else:
            current = None
    return {flag: " ".join(" ".join(parts).split()) for flag, parts in entries.items()}


@pytest.mark.parametrize(("verb", "token"), [("report", "[--x AXIS]"), ("serve", "[--x AXIS]"), ("inspect", "[--event NAME]")])
def test_fr13_the_usage_line_no_longer_requires_the_flag(verb: str, token: str) -> None:
    usage = usage_of(help_text(verb))
    # The flag is shown required in the usage line, while a missing one is still the command's own
    # refusal, listing what the runs carry.
    assert token.strip("[]") in usage and token not in usage, usage


@pytest.mark.parametrize(("verb", "flag"), [("report", "--x"), ("serve", "--x"), ("inspect", "--event")])
def test_fr13_the_help_says_what_omitting_the_flag_does(verb: str, flag: str) -> None:
    assert "omitted: lists" in help_entries(help_text(verb))[flag], help_entries(help_text(verb))[flag]


FLAG_SETS = {
    "report": {
        "--event", "--method", "--q", "--methods", "--permutations", "--seed", "--by", "--max-group-mde", "--depth",
        "--x", "--y", "--fix", "--horizon", "--theme", "--top-n", "--forest", "--out", "--title", "--force",
        "--paired",
    },
    "serve": {
        "--event", "--method", "--q", "--permutations", "--seed", "--by", "--max-group-mde", "--depth",
        "--x", "--y", "--fix", "--theme", "--top-n", "--forest", "--title", "--json",
    },
    "inspect": {"--event", "--where", "--limit"},
}


@pytest.mark.parametrize("verb", ["report", "serve", "inspect"])
def test_fr13_no_flag_is_added_or_removed(verb: str) -> None:
    """Green before and after (with V30 and W1): the parser edit removes ``required`` and nothing else."""
    flags = set(help_entries(help_text(verb))) - {"--help"}
    # Every verb gains the global options and --json, and nothing else.
    expected = FLAG_SETS[verb] | {"--store", "--plain", "--debug", "--json"}
    assert flags == expected, flags ^ expected


def test_fr13_the_five_tree_flags_keep_diffs_help_on_report_and_serve() -> None:
    """Green before and after (with R13 and W11)."""
    diff_help = help_entries(help_text("diff"))
    for verb in ("report", "serve"):
        entries = help_entries(help_text(verb))
        for flag in ("--permutations", "--seed", "--by", "--max-group-mde", "--depth"):
            assert entries[flag] == diff_help[flag], (verb, flag)


# ---------- FR14 to FR17: E4, the inference line ----------


def lattice_multi(events: Sequence[str] | None) -> MultiDiffResult:
    store = Store(LATTICE_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpairedAnalysis)
        return multi_diff(
            store.read(LATTICE_A, meta=False), store.read(LATTICE_B, meta=False),
            events=events, manifest_a=store.manifest(LATTICE_A), manifest_b=store.manifest(LATTICE_B),
        )


def a14_multi(events: Sequence[str] | None) -> MultiDiffResult:
    """A14's frames: two cells of 32 rows, ``completed`` the most frequent outcome, events ``violated, timeout``."""
    a = [({"cell": "c1"}, {"completed": 20, "violated": 8, "timeout": 4}, {}), ({"cell": "c2"}, {"completed": 24, "violated": 6, "timeout": 2}, {})]
    b = [({"cell": "c1"}, {"completed": 16, "violated": 12, "timeout": 4}, {}), ({"cell": "c2"}, {"completed": 24, "violated": 6, "timeout": 2}, {})]
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(tmp)
        write_run(store, "a", a, salt="salt-a")
        write_run(store, "b", b, salt="salt-b")
        return multi_diff(
            store.read("a", meta=False), store.read("b", meta=False), events=events,
            manifest_a=store.manifest("a"), manifest_b=store.manifest("b"),
        )


@pytest.fixture(scope="module")
def lattice_inferred() -> MultiDiffResult:
    return lattice_multi(None)


@dataclass(frozen=True)
class Ran:
    result: Result
    out_dir: Path


@pytest.fixture(scope="module")
def lattice_ran(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Ran]:
    """The lattice's verbs on the pair and on one run, each run once: inferred, one event, two events."""
    base = tmp_path_factory.mktemp("lattice-ran")
    store = ["--store", str(LATTICE_ROOT)]
    knobs = ["--permutations", "50"]
    events = {"inferred": [], "tripped": ["--event", "tripped"], "both": ["--event", "tripped", "--event", "held"]}
    ran: dict[str, Ran] = {}
    for kind, extra in events.items():
        for verb in ("diff", "report", "single", "check"):
            if (verb == "check" and kind == "inferred") or (verb == "single" and kind != "inferred"):
                continue
            out = base / f"{verb}-{kind}"
            argv = {
                "diff": ["diff", LATTICE_A, LATTICE_B, *extra, *knobs],
                "report": ["report", LATTICE_A, LATTICE_B, *extra, "--x", LATTICE_X, "--y", LATTICE_Y, *knobs, "--out", str(out)],
                "single": ["report", LATTICE_A, *extra, "--x", LATTICE_X, "--y", LATTICE_Y, "--out", str(out)],
                # PF4 (PF4.20): the lattice's events carry no kind, so check's default --fail-on worse is refused;
                # --fail-on higher is the same gate (fail when a rate rose).
                "check": ["check", LATTICE_A, LATTICE_B, *extra, "--fail-on", "higher"],
            }[verb]
            r = run_cli([*store, *argv])
            # A gate that ran passes or fails; failed exits 4.
            assert r.code in ((0, 4) if verb == "check" else (0,)), (verb, kind, r)
            ran[f"{verb} {kind}"] = Ran(r, out)
    return ran


def first_line(r: Result) -> str:
    return r.out.splitlines()[0]


def after_verdict(r: Result) -> list[str]:
    """PF2: ``diff`` and ``check`` open with a verdict block, and ``report`` with its
    ``ok  wrote`` line and one ``  wrote`` line per file, each ended by one blank line; what the verb
    printed before follows it unchanged."""
    lines = r.out.splitlines()
    assert "" in lines, r.out
    return lines[lines.index("") + 1 :]


@pytest.mark.parametrize("which", ["lattice", "a14"])
def test_fr14_to_markdown_opens_with_the_plain_line_and_it_carries_no_parenthesis(which: str, lattice_inferred: MultiDiffResult) -> None:
    multi = lattice_inferred if which == "lattice" else a14_multi(None)
    assert multi.inferred
    line = multi.to_markdown().splitlines()[0]
    assert line == inference_line(multi.events, str(multi.non_event)), line
    assert "(" not in line and ")" not in line, line
    assert line == (LATTICE_LINE if which == "lattice" else A14_LINE), line


def svg_texts(path: Path) -> list[str]:
    return ["".join(el.itertext()) for el in ET.fromstring(path.read_text()).iter() if el.tag.endswith("text")]


# The figure's wrap rule, restated from ``test_ls_local_serve.py`` (LS2's ``wrap`` and ``budget``, its
# ``CHAR_EM`` and ``MIN_BUDGET``), never imported from the build: a text is broken on spaces into lines
# of at most ``budget`` glyphs, greedy, a word longer than the budget hard-split, and the budget is how
# many glyphs of the text's font fit from its ``x`` to 24 px short of the figure's right edge. The first
# line is drawn as a ``<text>`` without ``data-wrap`` and each further line as the next ``<text>`` with
# ``data-wrap="1"``, at the same ``x``.
CHAR_EM = 0.6
MIN_BUDGET = 8
#: The lattice's report figure is 600 px wide, so its header's budget at x 24 in the 11 px font is 83
#: glyphs and the 107-character inference line breaks once, after ``tripped,``.
LATTICE_LINE_DRAWN = [
    "inferred: no event was given, so the event set is held; the non-event is tripped,",
    "the most frequent outcome",
]


def wrap(text: str, budget: int) -> list[str]:
    """LS2's restatement of the figure's ``_wrap``: broken on spaces into lines of at most ``budget``
    characters, greedy, a word longer than the budget hard-split; ``[""]`` for empty text."""
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        while len(word) > budget:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:budget])
            word = word[budget:]
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= budget:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def budget(width: float, x: float, font: float) -> int:
    return max(MIN_BUDGET, int((width - x - 24) / (CHAR_EM * font)))


@dataclass(frozen=True)
class SvgRun:
    """One ``<text>`` of a figure as drawn: its words, whether it is a continuation, its x and font."""
    content: str
    wrap: bool
    x: float
    font: float


def svg_runs(svg: str) -> tuple[list[SvgRun], float]:
    """Every ``<text>`` of the figure in document order, with the font it inherits, and the figure's width."""
    root = ET.fromstring(svg)
    parents = {child: parent for parent in root.iter() for child in parent}

    def font_of(el: ET.Element) -> float:
        node: ET.Element | None = el
        while node is not None:
            if "font-size" in node.attrib:
                return float(node.attrib["font-size"])
            node = parents.get(node)
        raise AssertionError("a <text> with no font-size on it or above it")

    runs = [
        SvgRun("".join(el.itertext()), el.get("data-wrap") == "1", float(el.attrib["x"]), font_of(el))
        for el in root.iter()
        if el.tag.endswith("text")
    ]
    return runs, float(root.attrib["width"])


def svgs_in(path: Path) -> list[str]:
    """The figures a written file holds: ``heatmap.svg`` itself, or every ``<svg>`` a page embeds."""
    text = path.read_text()
    return [text] if path.suffix == ".svg" else re.findall(r"<svg\b.*?</svg>", text, flags=re.DOTALL)


def joined_lines(runs: Sequence[SvgRun]) -> list[str]:
    """The figure's texts with each continuation joined to the line before it by the space it broke at."""
    lines: list[str] = []
    for run in runs:
        if run.wrap:
            assert lines, "a continuation with no line before it"
            lines[-1] = f"{lines[-1]} {run.content}"
        else:
            lines.append(run.content)
    return lines


def drawn_line_problems(svg: str, line: str) -> list[str]:
    """What is wrong with the figure as the drawing of ``line``: one ``<text>`` opens it, without
    ``data-wrap``, and it and the continuations after it are the restated wrap of ``line`` at that text's
    budget, line for line, at its x and font, the continuations marked and the text after them not."""
    runs, width = svg_runs(svg)
    starts = [i for i, run in enumerate(runs) if run.content.startswith(MARKER)]
    if len(starts) != 1:
        return [f"{len(starts)} <text> elements start with the marker"]
    first = runs[starts[0]]
    expected = wrap(line, budget(width, first.x, first.font))
    drawn = runs[starts[0] : starts[0] + len(expected)]
    problems = []
    if [run.content for run in drawn] != expected:
        problems.append(f"drawn as {[run.content for run in drawn]}, not {expected}")
    if [run.wrap for run in drawn] != [False] + [True] * (len(expected) - 1):
        problems.append(f"continuation marks {[run.wrap for run in drawn]}")
    if {(run.x, run.font) for run in drawn} != {(first.x, first.font)}:
        problems.append("the lines do not share the first line's x and font")
    after = runs[starts[0] + len(expected) : starts[0] + len(expected) + 1]
    if after and after[0].wrap:
        problems.append(f"a further continuation follows: {after[0].content}")
    return problems


class ParagraphTexts(HTMLParser):
    """The text of every element of a page, keyed by the innermost open tag."""

    VOID = {"br", "meta", "img", "hr", "input", "link", "col", "area", "base", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.chunks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        while self.stack and self.stack.pop() != tag:
            pass

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.chunks.append((self.stack[-1] if self.stack else "", data.strip()))


def html_chunks(path: Path) -> list[tuple[str, str]]:
    parser = ParagraphTexts()
    parser.feed(path.read_text())
    parser.close()
    return parser.chunks


def marked_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(MARKER)]


def test_fr14_the_plain_line_is_line_one_of_diff_stdout(lattice_ran: dict[str, Ran]) -> None:
    # PF2: line one of the report diff prints, after its verdict block.
    assert after_verdict(lattice_ran["diff inferred"].result)[0] == LATTICE_LINE


def test_fr14_the_plain_line_is_line_one_of_report_stdout(lattice_ran: dict[str, Ran]) -> None:
    # PF2: line one of what report printed before, after its wrote block.
    assert after_verdict(lattice_ran["report inferred"].result)[0] == LATTICE_LINE


def test_fr14_the_plain_line_is_in_report_md(lattice_ran: dict[str, Ran]) -> None:
    assert marked_lines((lattice_ran["report inferred"].out_dir / "report.md").read_text()) == [LATTICE_LINE]


def test_fr14_the_plain_line_is_the_muted_header_of_heatmap_svg(lattice_ran: dict[str, Ran]) -> None:
    """The lattice's figure is narrower than the line, so the header draws it broken by the figure's wrap
    rule: where it breaks is checked against the restated rule and against the literal, not only the words."""
    (svg,) = svgs_in(lattice_ran["report inferred"].out_dir / "heatmap.svg")
    assert drawn_line_problems(svg, LATTICE_LINE) == []
    runs, width = svg_runs(svg)
    (start,) = [i for i, run in enumerate(runs) if run.content.startswith(MARKER)]
    assert (width, runs[start].x, runs[start].font) == (600.0, 24.0, 11.0), (width, runs[start])
    assert wrap(LATTICE_LINE, budget(width, runs[start].x, runs[start].font)) == LATTICE_LINE_DRAWN
    assert [run.content for run in runs[start : start + 2]] == LATTICE_LINE_DRAWN
    assert [t for t in svg_texts(lattice_ran["report inferred"].out_dir / "heatmap.svg") if t.startswith(MARKER)] == LATTICE_LINE_DRAWN[:1]


def test_fr14_the_plain_line_is_a_paragraph_of_receipt_html(lattice_ran: dict[str, Ran]) -> None:
    chunks = html_chunks(lattice_ran["report inferred"].out_dir / "receipt.html")
    assert [text for tag, text in chunks if tag == "p" and text.startswith(MARKER)] == [LATTICE_LINE]


def test_fr15_the_single_run_report_says_the_same_thing_as_the_pair(lattice_ran: dict[str, Ran]) -> None:
    single, pair = lattice_ran["single inferred"].result, lattice_ran["report inferred"].result
    # PF2: each report's line one is read after its wrote block.
    assert after_verdict(single)[0] == LATTICE_LINE == after_verdict(pair)[0]


def texts_of(ran: Ran) -> dict[str, list[str]]:
    """Every text a report writes, as lines: ``report.md``'s lines; the figure's ``<text>`` runs as drawn
    and, beside them, the same runs with each continuation joined to its line; the page's chunks as
    parsed and, beside them, the joined lines of every figure it embeds."""
    heatmap, receipt = ran.out_dir / "heatmap.svg", ran.out_dir / "receipt.html"
    return {
        "report.md": (ran.out_dir / "report.md").read_text().splitlines(),
        "heatmap.svg": [r.content for svg in svgs_in(heatmap) for r in svg_runs(svg)[0]]
        + [line for svg in svgs_in(heatmap) for line in joined_lines(svg_runs(svg)[0])],
        "receipt.html": [text for _, text in html_chunks(receipt)]
        + [line for svg in svgs_in(receipt) for line in joined_lines(svg_runs(svg)[0])],
    }


def control_problems(ran: Ran) -> dict[str, list[str]]:
    """The positive control on each surface of a report that inferred its events: ``report.md`` carries
    the line and no other marked line; each figure (the heatmap, and the one the page embeds) draws it
    by the wrap rule (``drawn_line_problems``); and the page's own paragraph is the line."""
    md = [line for line in (ran.out_dir / "report.md").read_text().splitlines() if line.startswith(MARKER)]
    figures = {name: svgs_in(ran.out_dir / name) for name in ("heatmap.svg", "receipt.html")}
    paragraphs = [text for tag, text in html_chunks(ran.out_dir / "receipt.html") if tag == "p" and text.startswith(MARKER)]
    out = {"report.md": [] if md and set(md) == {LATTICE_LINE} else [f"marked lines {md}"]}
    for name, svgs in figures.items():
        out[name] = [] if len(svgs) == 1 else [f"{len(svgs)} figures"]
        out[name] += [problem for svg in svgs for problem in drawn_line_problems(svg, LATTICE_LINE)]
    out["receipt.html"] += [] if paragraphs == [LATTICE_LINE] else [f"paragraphs {paragraphs}"]
    return out


@pytest.mark.parametrize("kind", ["tripped", "both"])
@pytest.mark.parametrize("verb", ["diff", "report", "check"])
def test_fr16_given_events_print_no_inference_line_and_the_marker_matches_where_it_should(lattice_ran: dict[str, Ran], verb: str, kind: str) -> None:
    given = lattice_ran[f"{verb} {kind}"]
    assert marked_lines(given.result.out) == [], given.result.out
    if verb == "report":
        # Over the raw ``<text>`` runs and the page's chunks as well as the joined lines, so a marked line
        # drawn as a continuation (and so merged into the line before it) is still seen.
        for name, lines in texts_of(given).items():
            assert [line for line in lines if line.startswith(MARKER)] == [], name
            assert not any(MARKER in line for line in lines), name
    # The positive control, on real output: the same pair without --event, same verb (check never infers).
    control = lattice_ran["diff inferred" if verb == "check" else f"{verb} inferred"]
    # PF2: the control's line one is read after diff's verdict block or report's wrote
    # block.
    assert after_verdict(control.result)[0].startswith(MARKER)
    if verb == "report":
        assert control_problems(control) == {"report.md": [], "heatmap.svg": [], "receipt.html": []}
        for name, lines in texts_of(control).items():
            assert any(line.startswith(MARKER) for line in lines), name


def test_fr17_to_json_carries_the_same_keys_and_the_same_inference_fields(lattice_inferred: MultiDiffResult) -> None:
    inferred, explicit = lattice_inferred.to_json(), lattice_multi(["tripped"]).to_json()
    assert sorted(inferred) == MULTI_JSON_KEYS == sorted(explicit)
    assert (inferred["inferred"], inferred["non_event"], inferred["events"]) == (True, "tripped", ["held"])
    assert (explicit["inferred"], explicit["non_event"], explicit["events"]) == (False, None, ["tripped"])


def test_fr17_infer_events_returns_what_it_returned(lattice_inferred: MultiDiffResult) -> None:
    store = Store(LATTICE_ROOT)
    a, b = store.read(LATTICE_A, meta=False), store.read(LATTICE_B, meta=False)
    assert infer_events(a, b) == (("held",), "tripped") == infer_events(a, a.iloc[0:0])
    assert (lattice_inferred.events, lattice_inferred.non_event) == (("held",), "tripped")
    multi = a14_multi(None)
    assert (multi.events, multi.non_event) == (("violated", "timeout"), "completed")


@pytest.mark.parametrize(("kind", "line"), [("inferred", "- inferred: true"), ("tripped", "- inferred: false")])
def test_fr17_report_md_provenance_still_prints_inferred(lattice_ran: dict[str, Ran], kind: str, line: str) -> None:
    md = (lattice_ran[f"report {kind}"].out_dir / "report.md").read_text().splitlines()
    assert line in md, [m for m in md if "inferred" in m]


# The resolver and the digest are restated, never imported.


def resolve_region(module: ast.Module, qualified: str) -> ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef:
    node: ast.AST = module
    definition: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None = None
    for segment in qualified.split("."):
        matches = [c for c in ast.iter_child_nodes(node) if isinstance(c, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and c.name == segment]
        assert len(matches) == 1, (qualified, segment, len(matches))
        definition = matches[0]
        node = definition
    assert definition is not None
    return definition


def digest_excluding(path: Path, regions: Sequence[str]) -> str:
    """The file's sha256 with each region's ``lineno`` to ``end_lineno`` removed, whole lines; the ``def``
    line is the region's first, so a decorator above it stays guarded."""
    source = path.read_bytes()
    spans = [(n.lineno, n.end_lineno or 0) for n in (resolve_region(ast.parse(source), q) for q in regions)]
    kept = [line for i, line in enumerate(source.decode().splitlines(keepends=True), start=1) if not any(lo <= i <= hi for lo, hi in spans)]
    return hashlib.sha256("".join(kept).encode()).hexdigest()


# PF0: test_fr17_diff_py_outside_the_one_method_is_the_dispatch_commits removed. It pinned the bytes of src/poisson_prove/diff.py outside one method, which the rename
# changes; no digest of a file this module changes can be frozen honestly before its build
# exists.


# PF0: test_fr17_report_viewer_store_and_tree_are_byte_untouched removed. It pinned the bytes of report.py, viewer.py, store.py and tree.py, which the rename
# changes; no digest of a file this module changes can be frozen honestly before its build
# exists.


# FR18: no new surface.


def module_level_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def imports_of(path: Path) -> set[tuple[str | None, str | None]]:
    found: set[tuple[str | None, str | None]] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update((alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.update((node.module, alias.name) for alias in node.names)
    return found


def test_fr18_all_is_main_and_diff_py_gains_no_module_level_name() -> None:
    """Green before and after: D11's template lives inside the one method, so no helper name is added."""
    assert cli.__all__ == ["main"]
    # PF4 (PF4.12 to PF4.20): the build changes diff.py (kinds, directions, detection-limit notes) and
    # adds module-level names of its own, so the exact set no longer holds and no new set is typed in;
    # what is kept is every name the set held, and that the inference line still has no helper of its own.
    names = module_level_names(PACKAGE / "diff.py")
    assert DIFF_MODULE_NAMES <= names, DIFF_MODULE_NAMES - names
    assert not any("inference" in name for name in names - DIFF_MODULE_NAMES), names - DIFF_MODULE_NAMES


def test_fr18_cli_py_imports_gain_shlex_and_nothing_else() -> None:
    """Green before and after (L3, U14, I21 and the four BinOp guards carry the rest of FR18).

    PF1 rewrites ``cli.py`` -- its errors, numbers, help and the plan -- so the
    exact import set no longer holds; what is kept is the guard behind it: ``cli.py`` gains no
    import from outside the standard library and Prove's own modules (the type-checking imports it
    already had stay allowed; Rich, when it arrives, is imported by a private rendering module)."""
    now = imports_of(PACKAGE / "cli.py")
    outside = {i for i in now if i[0].split(".")[0] not in sys.stdlib_module_names and i[0].split(".")[0] != "poisson_prove"}
    assert outside - CLI_IMPORTS == set(), outside - CLI_IMPORTS


# ---------- FR19: check never passes on a missing argument ----------

CHECK_VARIANTS: list[tuple[str, ...]] = [
    (), ("--fail-on", "worse"), ("--fail-on", "any"), ("--method", "fisher_bh"), ("--method", "mcnemar_bh"),
    ("--method", "logrank_bh"), ("--q", "0.5"), ("--fail-on", "any", "--method", "mcnemar_bh", "--q", "0.5"),
]


@dataclass(frozen=True)
class GatePair:
    root: Path
    a: str
    b: str
    events: str

    def argv(self, *extra: str) -> list[str]:
        return ["--store", str(self.root), "check", self.a, self.b, *extra]


@pytest.fixture(scope="module")
def gate_pairs(tmp_path_factory: pytest.TempPathFactory, mock_pair: MockPair) -> dict[str, GatePair]:
    """The lattice pair, the mock pair, and two synthetic pairs: one whose gate PASSes on ``--event fell`` (no cell worse),
    one whose gate FAILs on it (one cell worse, I14's shape). Same salt and seeds, so all four are pairable."""
    root = tmp_path_factory.mktemp("gate-pairs")
    store = Store(root)
    fell_run(store, "pass-a", {1.0: 10, 2.0: 20})
    fell_run(store, "pass-b", {1.0: 10, 2.0: 20})
    fell_run(store, "fail-a", {1.0: 0, 2.0: 8})
    fell_run(store, "fail-b", {1.0: 24, 2.0: 8})
    return {
        "lattice": GatePair(LATTICE_ROOT, LATTICE_A, LATTICE_B, "held, tripped"),
        "mock": GatePair(mock_pair.root, mock_pair.a, mock_pair.b, "completed, timeout, violated"),
        "pass": GatePair(root, "pass-a", "pass-b", "fell, survived"),
        "fail": GatePair(root, "fail-a", "fail-b", "fell, survived"),
    }


def test_fr19_the_gate_pairs_pass_and_fail_when_the_gate_runs(gate_pairs: dict[str, GatePair]) -> None:
    """Green before and after: the controls that make FR19's crossing mean something. Were ``check`` to run
    its gate on these pairs, one would exit 0 and one would exit 1, and a listing that fell through to the
    gate would show it."""
    # PF4 (PF4.20): ``fell`` carries no kind in these runs, so the default --fail-on worse is refused;
    # --fail-on higher is the same gate (fail when the rate rose).
    assert run_cli(gate_pairs["pass"].argv("--event", "fell", "--fail-on", "higher")).code == 0
    # A failed check exits 4.
    assert run_cli(gate_pairs["fail"].argv("--event", "fell", "--fail-on", "higher")).code == 4
    # The lattice pair shares a salt, so check's default is the paired test (McNemar); under it no
    # condition's tripped rose, as the exact McNemar reference with one BH family gives (27 lower, 0 higher).
    lower, higher = lattice.directions(lattice.mcnemar(lattice.EVENT, 0.05))
    assert (lower, higher) == (27, 0)
    gate = run_cli(gate_pairs["lattice"].argv("--event", "tripped", "--fail-on", "higher"))
    assert gate.code == 0, gate
    assert "(McNemar)" in gate.out and f"tripped: {higher} higher, {lower} lower in 72 conditions" in gate.out, gate.out
    store = Store(gate_pairs["fail"].root)
    events, non_event = infer_events(store.read("fail-a", meta=False), store.read("fail-b", meta=False))
    assert (events, non_event) == (("fell",), "survived"), "the FAIL pair infers fell, so a gate run on the inferred set FAILs too"
    store = Store(gate_pairs["pass"].root)
    assert infer_events(store.read("pass-a", meta=False), store.read("pass-b", meta=False)) == (("fell",), "survived")


@pytest.mark.parametrize("name", ["lattice", "mock", "pass", "fail"])
def test_fr19_check_that_lists_puts_the_list_on_stderr_and_none_of_it_on_stdout(gate_pairs: dict[str, GatePair], name: str) -> None:
    """The red half: the listing itself, on stderr, for every crossing."""
    pair = gate_pairs[name]
    for extra in CHECK_VARIANTS:
        r = run_cli(pair.argv(*extra))
        # The list may sit inside the error line now; the gate's words are passed and
        # failed.
        assert listed_values(r.err, "events") == [pair.events], (extra, r.err)
        assert "events:" not in r.out and "PASS" not in r.out and "FAIL" not in r.out, (extra, r.out)
        assert "passed" not in r.out and "failed" not in r.out, (extra, r.out)


@pytest.mark.parametrize("name", ["lattice", "mock", "pass", "fail"])
def test_fr19_check_that_lists_exits_two_never_zero_or_one_and_never_reaches_the_gate(
    gate_pairs: dict[str, GatePair], monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """The green half (today's refusal already has every clause): exit 2, and separately not 0 and not 1
    (1 is a FAIL, a gate that ran); stdout empty, no PASS, FAIL or headline; and the result is identical with
    ``MultiDiffResult.check`` and ``cli.multi_diff`` raising."""
    pair = gate_pairs[name]
    plain = [run_cli(pair.argv(*extra)) for extra in CHECK_VARIANTS]
    calls = arm_gate_tripwire(monkeypatch)
    armed = [run_cli(pair.argv(*extra)) for extra in CHECK_VARIANTS]
    assert calls == [], calls
    assert armed == plain
    for extra, r in zip(CHECK_VARIANTS, plain, strict=True):
        # A refusal exits 1, and a failed check 4.
        assert r.code == 1, (extra, r)
        assert r.code != 0, (extra, "a listing must never pass")
        assert r.code != 4, (extra, "4 is a failed check: the gate ran")
        assert r.out == "", (extra, r.out)
        assert r.err != "", extra


# ---------- FR20: the single-run report's own inference line ----------


def single_run_argv(root: Path, run: str, out: Path, *extra: str, x: str = LATTICE_X, y: str = LATTICE_Y) -> list[str]:
    return ["--store", str(root), "report", run, "--x", x, "--y", y, "--out", str(out), *extra]


@pytest.mark.parametrize("which", ["lattice", "mock"])
def test_fr20_the_single_run_line_is_the_plain_template_and_precedes_the_summary_line(tmp_path: Path, mock_pair: MockPair, which: str) -> None:
    if which == "lattice":
        root, run, argv = LATTICE_ROOT, LATTICE_A, single_run_argv(LATTICE_ROOT, LATTICE_A, tmp_path / "out")
    else:
        root, run = mock_pair.root, mock_pair.a
        argv = single_run_argv(root, run, tmp_path / "out", x="tool_fail_rate", y="task_id")
    frame = Store(root).read(run, meta=False)
    events, non_event = infer_events(frame, frame.iloc[0:0])
    name = run_names(root)[run]
    r = run_cli(argv)
    assert r.code == 0, r
    # PF2: the two lines are read after report's wrote block, and the summary line
    # names the run by its name in double quotes, not by its id.
    lines = after_verdict(r)
    assert lines[0] == inference_line(events, non_event), lines[:2]
    assert "(" not in lines[0] and ")" not in lines[0], lines[0]
    assert lines[1].startswith(f'"{name}": survival report over {", ".join(events)} at horizon '), lines[:2]
    assert lines[0] == (LATTICE_LINE if which == "lattice" else A14_LINE)


@pytest.mark.parametrize("kind", ["one event", "repeated events"])
def test_fr20_a_single_run_with_given_events_prints_no_inference_line(tmp_path: Path, mock_pair: MockPair, kind: str) -> None:
    """Green before and after, with its positive control in the same test: the same run's inferred line."""
    given = ["--event", "violated"] if kind == "one event" else ["--event", "violated", "--event", "timeout"]

    def argv(*extra: str) -> list[str]:
        return single_run_argv(mock_pair.root, mock_pair.a, tmp_path / f"out-{len(extra)}", *extra, x="tool_fail_rate", y="task_id")

    control = run_cli(argv())
    # PF2: the control's line one is read after report's wrote block.
    assert control.code == 0 and after_verdict(control)[0].startswith(MARKER), control.out
    explicit = run_cli(argv(*given))
    assert explicit.code == 0, explicit
    assert marked_lines(explicit.out) == [], explicit.out


def test_fr20_a_tie_on_a_single_run_refuses_byte_for_byte_as_before_with_nothing_ahead_of_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Green before and after: the refusal (``_report_run``) and its exact words are not this change's to move."""
    monkeypatch.chdir(tmp_path)
    write_run(Store(tmp_path / "store"), "tie", [({"cell": "c"}, {"fell": 16, "survived": 16}, {})])
    r = run_cli(["--store", str(tmp_path / "store"), "report", "tie", "--x", "cell"])
    # A refusal exits 1, is one error line then only next lines, and shows no Python repr,
    # so its facts are checked rather than its old bytes: the tie, both outcomes, their
    # count, and the --event hint.
    assert r.code == 1 and r.out == "", r
    first = r.err.partition("\n")[0]
    assert refusal_shape(r.err) == [] and "tied" in first, r.err
    assert "fell" in first and "survived" in first and "16" in first, r.err
    assert "--event" in r.err, r.err
    assert "['" not in r.err and "{'" not in r.err and "'fell'" not in r.err, r.err
    assert listing(tmp_path) == ["store", *[f"store/{p}" for p in listing(tmp_path / "store")]]

