"""First run, module M4: the setup agent calls the rollout once and hands over the whole loop
(issue 5). The frozen tests for invariants K1 to K10.

What M4 promises, in one line: ``poisson-prove sweep --try`` calls the spec's rollout once, for
real, on this machine, and stores nothing; the setup skill asks the person, makes that call, and
hands over as ready or not ready with the whole loop; and a first sweep of your own agent ends
with the paired sweep as its ``next:``. No test here calls a model, a coding agent, Modal, a cloud
account or any paid service: everything runs on a rollout the test writes, the sample repository
of the setup-agent tests and the demo agent ``init --demo`` writes.

**Readings, named here** (each a point read one way and lettered).

- (a) The trial's lines. On stdout: a verdict line ``try  …`` that names the target, the first
  condition's values, the seed and "this machine", then a ``cost`` detail line; after a good call
  a second verdict line ``ok  …`` that quotes the outcome, the detail lines ``condition``,
  ``seed``, ``outcome`` (with the outcome's declared kind), ``t`` (the steps, the horizon and the
  spec's unit), ``case_id`` when the Episode carries one, ``printed`` when the rollout wrote to its
  stdout, and one ``next:``. The question ``Call it? [y/N]`` goes to stderr, as a sweep's does.
  Facts are pinned, not sentences.
- (b) The exit codes are K1's and K3's, and they differ from a plain sweep's on purpose: off a
  terminal without ``--yes`` is 2 (a plain sweep exits 1 there), a no at the question is 0 (a
  plain sweep exits 1), and 1 is kept for a call that was made and did not end in an Episode Prove
  can store. A coding agent can then tell "the call failed" from "the command was typed wrong".
- (c) A failed call: stdout keeps the ``try`` lines and gains no ``ok`` line; stderr has exactly
  one ``error:`` line, then for a raise a ``  raised in  FILE:LINE`` line for the frame the
  exception was raised in and, when that frame is not in the target's own module, one more
  ``  LABEL  FILE:LINE`` line for the innermost frame in the target's module (its label is the
  build's to choose), then one ``next:`` line, the trial as typed. A file under the spec's folder
  is shown by its path from that folder. No traceback is printed. A timeout, a value that is not
  an Episode and an outcome ``[declare]`` does not list have no frames to show.
- (d) "A missing ``t``" is an Episode built with no usable ``t``: Prove's own Episode refuses it,
  so it is a raise whose innermost frame is Prove's and whose frame in the target's module is the
  line that built the Episode.
- (e) "Writes nothing" is read over the whole folder the command ran in (the store, ``.poisson/``,
  a cloud ledger, byte code and empty folders included) on every ending, and over ``HOME`` too on
  a good call, a no and a Ctrl-C. Whether a failed call's traceback goes to the errors log under
  ``HOME`` is left to the build.
- (f) "Reads and checks the spec as ``--dry-run`` does": a setup the check refuses is refused by
  the trial with the same exit code and the same ``error:`` line, and the rollout is not called.
  A design too small for the gate is such a setup.
- (g) What the rollout "prints" is what reaches its stdout, by any of the ways 0.2.1 pinned for
  ``--json`` (``print``, the binary buffer, file descriptor 1, a child process), in the rollout or
  when the target is imported. With and without ``--json`` every such write is on stderr once and
  never on stdout. The count of printed lines is the lines written to stdout, a last line with no
  newline among them, and not what went to the rollout's stderr; under ``--json`` it is the
  ``try`` object's ``printed``.
- (h) Under ``--json`` a good call is one ``poisson-prove.sweep/1`` document, verdict ``ok``, with
  a ``try`` object holding ``condition``, ``seed``, ``outcome``, ``t``, ``horizon``, ``meta``,
  ``seconds`` and ``printed``; a failed call leaves stdout empty, with the same exit code and the
  ``error:`` line on stderr, as every refusal under ``--json`` does.
- (i) "The first condition in the spec's order" is the first value of every axis, as the spec file
  writes them.
- (j) ``--try`` with ``--dry-run``, ``--resume`` or ``--pair-with`` is a wrong command line (exit
  2, nothing called): the first contradicts it, and the other two name a stored run for a call
  that stores nothing.
- (k) A rollout that ends its own process before it returns is a failed call (exit 1), never a
  good one.
- (l) The typed spec path, ``--target`` and ``--store`` are carried into the trial's ``next:``
  lines, so each runs as printed from the same folder.
- (m) The 300 s limit is pinned by a rollout that outlasts it; that case is marked ``slow``. The
  limit ``--episode-timeout`` gives is pinned in the code suite.
- (n) K5's note is a ``note:`` line that says "this machine". A spec "names Modal or a cloud
  account" when it holds a ``[modal]`` or a ``[cloud]`` table. Neither extra needs to be
  installed for the trial, and nothing reaches for a socket.
- (o) K6: the interrupt is sent to the command's own process alone, the harder case: the process
  the rollout runs in must then be ended by the command.
- (p) K7 pins the skill by structure. "The four loop commands in their own blocks" are the three
  of the loop (the sweep before with a note, the paired sweep with a note, ``diff``) and the trial
  the person runs first when the hand-over is not ready: four ``text`` blocks under "Hand over",
  one command each. Since First run M6 (L1, M6-23) a fifth block follows the loop, the comparison
  of one outcome the loop's ``diff`` leaves out (``diff --event NAME``), pinned in
  ``test_frs_m6_cost.py``; the four are the blocks before it. Since M6 (A3) the hand-over also
  has an item for the axes the skill did not add, so "one reason line per axis" is read on the
  item that opens with the axes of ``prove.toml``. The frozen setup-agent tests keep the rest (the frontmatter, the sections, the
  shared rules and prompt, every command parsing).
- (q) K8, the scripted run. The stand-in for a coding agent reads the steps and the commands from
  the written skill and decides as step 6 says: a call that exits 1 with its ``raised in`` line
  naming ``prove_rollout.py`` is the wrapper's to fix, anything else is handed over as not ready
  with nothing changed. The hands-on's broken wrapper passes the ticket's name where the bot wants
  its rate, and the ``TypeError`` is raised inside ``support_bot.py`` (measured), with
  ``prove_rollout.py`` the frame that called it. So the stand-in changes nothing and hands over
  ``not ready:`` quoting the ``TypeError``, with the call's output naming ``prove_rollout.py`` and
  the line; with the wrapper fixed it reaches ``ready:``.
- (r) K9: "another folder" is read after links and relative parts are resolved. The line carries
  DIR as typed and sits between the ``wrote`` lines and the ``prompt`` line. Since First run M6
  (A7) every ``init --agent`` prints one more detail line after the ``prompt`` line, so each
  case's output is one line longer.
- (s) K10: the ``then`` line is the line before the one ``next:``. The run is named by a word that
  reaches it alone, its name when that does. "Run as printed" is the printed command with ``--yes``
  added, since the test's stdin is not a terminal. The command must start a paired sweep in every
  typed form tried: bare; with a spec path, ``--target`` and ``--store``; with ``--replicates``;
  and with ``--max-mde`` (without the last two carried, the printed command is refused for its
  size).
- (t) The docs and the CHANGELOG are pinned by facts, not sentences.

**Seams with other modules.** The check and its refusals are PF11's and M2's. The demo is M3's.
``--json``'s one-document rule on a real sweep is 0.2.1's. The skill's shared format is PF11's;
its seven steps and its hand-over are pinned here and in the PF11 file.

**Suite.** The code suite, but the one case that waits out the 300 s limit, marked ``slow``.
Commands that import the person's code run as child processes.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| K1 the question, a no, Ctrl-C, off a terminal | ``test_k1_*`` |
| K2 once, the first condition, a fresh seed, nothing written | ``test_k2_*`` |
| K3 every ending's exit code and lines | ``test_k3_*`` |
| K4 stdout holds only Prove's result; the ``--json`` document | ``test_k4_*`` |
| K5 this machine on every spec, with the note | ``test_k5_*`` |
| K6 Ctrl-C during the call | ``test_k6_*`` |
| K7 the skill's seven steps and hand-over | ``test_k7_*``, and the PF11 file |
| K8 the scripted run | ``test_k8_*`` |
| K9 the ``open`` line | ``test_k9_*`` |
| K10 the ``then`` line and the paired ``next:`` | ``test_k10_*`` |
| section 5.4, section 8: the docs and the CHANGELOG | ``test_the_docs_*``, ``test_the_0_5_0_*`` |
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

import test_pf11_setup_agent as pf11
from conftest import blas_thread_cap
from pf6_support import Step, run_pty, strip_escapes

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
COMMAND = "poisson-prove"
TRY = f"{COMMAND} sweep --try"
BANNER = "framework banner"

SPEC = """\
target = "prove_rollout:rollout"
target_id = "counted"
t_unit = "steps"
replicates = 200

[axes.ticket]
type = "categorical"
values = ["refund", "password"]

[axes.temperature]
type = "continuous"
values = [0.0, 0.7]

[declare]
outcomes = ["resolved", "unresolved", "timeout"]
failures = ["unresolved", "timeout"]
successes = ["resolved"]
"""
FIRST_CONDITION = {"ticket": "refund", "temperature": 0.0}

#: A rollout that counts its calls: each call adds a line to the file ``M4_CALLS`` names, outside
#: the folder, with what it was called on and the process it ran in.
WRAPPER = """\
import json, os, subprocess, sys, time

from poisson_prove import Episode
{at_import}

def rollout(cfg, seed):
    with open(os.environ["M4_CALLS"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"cfg": cfg, "seed": seed, "pid": os.getpid()}}) + "\\n")
    {body}
    return Episode(outcome="resolved", t=7, horizon=20, meta={{"case_id": cfg["ticket"]}})
"""
#: The agent's own code, in a folder of its own (``bot/agent.py``), which the wrapper of one ending
#: calls with the wrong kind of value.
AGENT = """\
def handle(rate):
    return rate * 1.5
"""


@pytest.fixture(autouse=True)
def _empty_home_and_no_store_variables(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)


def counted(base: Path, body: str = "pass", at_import: str = "", spec: str = SPEC) -> Path:
    """A folder with the counting rollout and its spec."""
    repo = base / "repo"
    repo.mkdir(parents=True)
    (repo / "prove_rollout.py").write_text(WRAPPER.format(at_import=at_import, body=body), encoding="utf-8")
    (repo / "prove.toml").write_text(spec, encoding="utf-8")
    (repo / "bot").mkdir()
    (repo / "bot" / "agent.py").write_text(AGENT, encoding="utf-8")
    return repo


def line_of(repo: Path, text: str, file: str = "prove_rollout.py") -> int:
    lines = (repo / file).read_text(encoding="utf-8").splitlines()
    (at,) = [i for i, line in enumerate(lines, 1) if text in line]
    return at


def tried(repo: Path, base: Path, *argv: str, hide: tuple[str, ...] = (), timeout: float = 120) -> pf11.Child:
    """``poisson-prove sweep --try ARGV`` as a coding agent runs it: the installed command, off a
    terminal, no key, ``HOME`` empty, a socket guard first on the path."""
    return pf11.run_child(repo, base, "sweep", "--try", *argv, hide=hide, extra={"M4_CALLS": str(base / "calls.jsonl")}, timeout=timeout)


def calls(base: Path) -> list[dict[str, Any]]:
    log = base / "calls.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def verdicts(out: str) -> list[str]:
    """The verdict words of stdout's verdict lines, in order."""
    return [m.group(1) for m in (pf11.FIRST_LINE.match(line) for line in out.splitlines()) if m]


def error_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("error: ")]


def frame_lines(err: str) -> dict[str, str]:
    """The ``  label  value`` lines of stderr, by label (a ``next:`` line is not one)."""
    found = {}
    for line in err.splitlines():
        m = re.match(r"^  ([a-z][a-z ]*?) {2,}(\S.*)$", line)
        if m:
            found[m.group(1)] = m.group(2)
    return found


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def gone(pid: int, within: float = 10) -> bool:
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if not alive(pid):
            return True
        time.sleep(0.05)
    return not alive(pid)


def files_under(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


# ---------- K1 the question ----------


def test_k1_off_a_terminal_without_yes_it_is_refused_naming_yes_and_calls_nothing(tmp_path: Path) -> None:
    repo = counted(tmp_path)
    before = pf11.snapshot(repo)
    child = tried(repo, tmp_path)
    assert child.code == 2, child.result
    (error,) = error_lines(child.err)
    assert "--yes" in error, error
    assert any({"sweep", "--try", "--yes"} <= set(shlex.split(n)) for n in child.result.nexts), child.result.nexts
    assert "ok" not in verdicts(child.out), child.out
    assert calls(tmp_path) == []
    assert pf11.snapshot(repo) == before


#: What is typed at the question, the exit code and the calls made. With ``--yes`` on the command
#: line nothing is asked, on a terminal too.
K1_ANSWERS: dict[str, tuple[bytes | None, int, int]] = {
    "a no": (b"n\r", 0, 0),
    "Enter alone": (b"\r", 0, 0),
    "Ctrl-C": (b"\x03", 130, 0),
    "a yes": (b"y\r", 0, 1),
    "--yes on the command line": (None, 0, 1),
}


@pytest.mark.parametrize("answer", list(K1_ANSWERS))
def test_k1_on_a_terminal_it_asks_once_and_only_a_yes_makes_the_call(answer: str, tmp_path: Path) -> None:
    """All three streams on one terminal, the plain rendering."""
    typed, code, made = K1_ANSWERS[answer]
    repo = counted(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    before = pf11.snapshot(repo)
    asked = typed is not None
    done = run_pty(["--plain", "sweep", "--try", *([] if asked else ["--yes"])], home=home, cwd=repo, cols=200, rows=50,
                   steps=(Step(typed, until="[y/N]"),) if typed is not None else (), timeout=120,
                   M4_CALLS=str(tmp_path / "calls.jsonl"), **blas_thread_cap())
    shown = strip_escapes(done.out)
    assert done.code == code, shown
    assert shown.count("[y/N]") == (1 if asked else 0), shown
    # The question comes after the line that says what the call is, on the first condition.
    said = shown.index("[y/N]") if asked else len(shown)
    assert 0 <= shown.find("try  ") < said and "refund" in shown[:said], shown
    assert len(calls(tmp_path)) == made, shown
    assert ("ok  " in shown and '"resolved"' in shown) == bool(made), shown
    assert "error:" not in shown, shown
    assert pf11.snapshot(repo) == before
    assert files_under(home) == []


# ---------- K2 once, the first condition, a fresh seed, nothing written ----------


def test_k2_it_calls_the_rollout_exactly_once_on_the_specs_first_condition(tmp_path: Path) -> None:
    repo = counted(tmp_path)
    child = tried(repo, tmp_path, "--yes")
    assert child.code == 0, child.result
    made = calls(tmp_path)
    assert len(made) == 1, made
    assert made[0]["cfg"] == FIRST_CONDITION, made
    (condition,) = pf11.detail(child.out, "condition")
    assert "refund" in condition and "password" not in condition, condition
    assert re.search(r"temperature\W+0(?:\.0)?(?![\d.])", condition), condition


def test_k2_the_seed_is_from_a_fresh_salt_and_is_the_one_printed(tmp_path: Path) -> None:
    seeds = []
    for turn in ("first", "second"):
        base = tmp_path / turn
        child = tried(counted(base), base, "--yes")
        assert child.code == 0, child.result
        (made,) = calls(base)
        assert pf11.detail(child.out, "seed") == [str(made["seed"])], child.out
        first = child.out.splitlines()[0]
        assert first.startswith("try  ") and re.search(rf"(?<!\d){made['seed']}(?!\d)", first), first
        seeds.append(made["seed"])
    assert seeds[0] != seeds[1], seeds


def test_k2_a_good_call_writes_nothing(tmp_path: Path) -> None:
    repo = counted(tmp_path)
    before = pf11.snapshot(repo)
    child = tried(repo, tmp_path, "--yes")
    assert child.code == 0, child.result
    after = pf11.snapshot(repo)
    assert after == before, sorted(set(after) ^ set(before))
    assert files_under(child.home) == []
    assert child.attempts == [], child.attempts


# ---------- K3 every ending ----------


def test_k3_a_good_call_exits_0_with_its_lines(tmp_path: Path) -> None:
    repo = counted(tmp_path)
    child = tried(repo, tmp_path, "--yes")
    assert child.code == 0, child.result
    out = child.out.splitlines()
    assert verdicts(child.out) == ["try", "ok"], child.out
    first = out[0]
    assert "prove_rollout:rollout" in first and "this machine" in first, first
    assert len(pf11.detail(child.out, "cost")) == 1, child.out
    ok = next(line for line in out if line.startswith("ok  "))
    assert '"resolved"' in ok and re.search(r"\d s\b", ok), ok
    (outcome,) = pf11.detail(child.out, "outcome")
    assert "resolved" in outcome and "success" in outcome and "failure" not in outcome, outcome
    (t,) = pf11.detail(child.out, "t")
    assert re.search(r"(?<![\d.])7(?![\d.])", t) and re.search(r"(?<![\d.])20(?![\d.])", t) and "steps" in t, t
    assert pf11.detail(child.out, "case_id") == ["refund"], child.out
    assert pf11.detail(child.out, "printed") == [], child.out
    assert child.result.nexts == [f"{COMMAND} sweep"], child.result.nexts
    assert out[-1] == f"  next: {COMMAND} sweep", out[-3:]
    assert error_lines(child.err) == [] and child.result.notes == [], child.err


def test_k3_a_call_that_ends_in_a_declared_failure_is_still_a_good_call(tmp_path: Path) -> None:
    repo = counted(tmp_path, 'return Episode(outcome="unresolved", t=20, horizon=20, meta={"case_id": cfg["ticket"]})')
    child = tried(repo, tmp_path, "--yes")
    assert child.code == 0, child.result
    (outcome,) = pf11.detail(child.out, "outcome")
    assert "unresolved" in outcome and "failure" in outcome and "success" not in outcome, outcome


@dataclass(frozen=True)
class Ending:
    body: str
    #: facts on the one ``error:`` line
    error: tuple[str, ...]
    #: the text of the line the exception was raised on, and the file it is in; None for no frames
    raised: tuple[str, str] | None = None
    #: the text of the wrapper's line that called it, when the raise is not in the wrapper
    called: str | None = None
    argv: tuple[str, ...] = ()
    check: Callable[[pf11.Child, Path], None] | None = field(default=None)


def _ended_in_time_and_its_process_is_gone(child: pf11.Child, base: Path) -> None:
    assert child.seconds < 60, child.seconds
    (made,) = calls(base)
    assert gone(made["pid"]), "the rollout's process outlived the trial"


ENDINGS: dict[str, Ending] = {
    "a raise in the wrapper": Ending('ticket = cfg["tickets"]', ("KeyError", "tickets"), raised=('cfg["tickets"]', "prove_rollout.py")),
    "a raise in the agent's own code": Ending(
        'from bot.agent import handle; handle(cfg["ticket"])', ("TypeError", "multiply"),
        raised=("return rate * 1.5", "bot/agent.py"), called='handle(cfg["ticket"])'),
    "an Episode with no t": Ending(
        'return Episode(outcome="resolved", t=None, horizon=20)', ("t must be a number",),
        raised=None, called='t=None'),
    "a timeout": Ending("time.sleep(120)", ("1 s",), argv=("--episode-timeout", "1"), check=_ended_in_time_and_its_process_is_gone),
    "a value that is not an Episode": Ending('return "resolved"', ("Episode", "str")),
    "an outcome [declare] does not list": Ending('return Episode(outcome="escalated", t=1, horizon=20)', ("escalated", "declare")),
    "the rollout ends its own process": Ending("sys.stdout.flush(); os._exit(0)", ()),
}


@pytest.mark.parametrize("name", list(ENDINGS))
def test_k3_a_call_that_does_not_end_in_an_episode_exits_1_with_its_error_its_frames_and_the_trial_as_next(name: str, tmp_path: Path) -> None:
    ending = ENDINGS[name]
    repo = counted(tmp_path, ending.body)
    before = pf11.snapshot(repo)
    child = tried(repo, tmp_path, "--yes", *ending.argv)
    assert child.code == 1, child.result
    assert len(calls(tmp_path)) == 1, calls(tmp_path)
    # stdout: what the call was, and no result (reading c).
    assert verdicts(child.out) == ["try"], child.out
    assert child.out.count("  next: ") == 0, child.out
    # stderr: one error line with its facts, the frames, one next, no traceback.
    (error,) = error_lines(child.err)
    for fact in ending.error:
        assert fact in error, (fact, error)
    assert "Traceback" not in child.err and 'File "' not in child.err, child.err
    frames = frame_lines(child.err)
    if ending.raised is not None:
        text, file = ending.raised
        assert frames.get("raised in") == f"{file}:{line_of(repo, text, file)}", child.err
    if ending.called is not None:
        wanted = f"prove_rollout.py:{line_of(repo, ending.called)}"
        assert wanted in frames.values(), child.err
    if ending.raised is None and ending.called is None:
        assert frames == {}, child.err
    assert child.result.nexts == [TRY], child.result.nexts
    assert child.err.rstrip("\n").splitlines()[-1] == f"  next: {TRY}", child.err
    after = pf11.snapshot(repo)
    assert after == before, sorted(set(after) ^ set(before))
    if ending.check is not None:
        ending.check(child, tmp_path)


@pytest.mark.slow
def test_k3_a_rollout_that_never_returns_is_ended_at_300_s(tmp_path: Path) -> None:
    """Reading m: with no ``--episode-timeout`` the limit is 300 s, no sooner and not much later."""
    repo = counted(tmp_path, "time.sleep(900)")
    child = tried(repo, tmp_path, "--yes", timeout=420)
    assert child.code == 1, child.result
    assert 295 <= child.seconds < 360, child.seconds
    (error,) = error_lines(child.err)
    assert "300 s" in error, error
    assert child.result.nexts == [TRY], child.result.nexts
    (made,) = calls(tmp_path)
    assert gone(made["pid"])


def test_k3_an_unexpected_failure_of_proves_own_exits_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prove's own failure is not the rollout's: the look's line for it and exit 3, with no
    ``next:`` that sends the person back to the trial. Made here by a stdout that fails when Prove
    writes to it."""
    from poisson_prove import cli as module

    repo = counted(tmp_path)
    monkeypatch.setenv("M4_CALLS", str(tmp_path / "calls.jsonl"))

    class Broken(Exception):
        """Nothing Prove expects."""

    class Failing(StringIO):
        def write(self, text: str) -> int:
            raise Broken("this stream cannot be written to")

    err = StringIO()
    with pf11.inside(repo):
        code = module.main(["sweep", "--try", "--yes"], stdout=Failing(), stderr=err, stdin=StringIO())
    r = pf11.Result(code, "", err.getvalue())
    assert r.code == 3, r
    assert re.match(rf"^error: an unexpected failure inside {COMMAND} \(Broken\)", r.error), r.err
    assert r.nexts == [], r.nexts


K3_WRONG = {
    "the target takes (task, client)": (lambda repo: pf11.edit("prove_rollout.py", "def rollout(cfg, seed)", "def rollout(task, client)")(repo), ()),
    "a design too small for the gate": (lambda repo: pf11.edit("prove.toml", "replicates = 200", "replicates = 20")(repo), ()),
    "--dry-run with it": (lambda repo: None, ("--dry-run",)),
    "--resume with it": (lambda repo: None, ("--resume",)),
    "--pair-with with it": (lambda repo: None, ("--pair-with", "latest")),
}


@pytest.mark.parametrize("name", list(K3_WRONG))
def test_k3_what_the_check_refuses_the_trial_refuses_the_same_way_and_calls_nothing(name: str, tmp_path: Path) -> None:
    """Readings f and j."""
    change, more = K3_WRONG[name]
    repo = counted(tmp_path)
    change(repo)
    before = pf11.snapshot(repo)
    child = tried(repo, tmp_path, "--yes", *more)
    if more:
        assert child.code == 2, child.result
        assert "--try" in child.result.error and more[0] in child.result.error, child.err
    else:
        check = pf11.run_child(repo, tmp_path / "check", "sweep", "--dry-run")
        assert check.code == 1, check.result
        assert (child.code, child.result.error) == (check.code, check.result.error), (child.result, check.result)
    assert "try" not in verdicts(child.out) and "ok" not in verdicts(child.out), child.out
    assert calls(tmp_path) == []
    assert pf11.snapshot(repo) == before


def test_k3_the_trials_next_lines_carry_the_typed_spec_target_and_store(tmp_path: Path) -> None:
    """Reading l: each ``next:`` runs as printed from the folder the trial was typed in."""
    repo = counted(tmp_path, 'if os.path.exists("fail"): raise ValueError("asked to fail")')
    os.rename(repo / "prove.toml", repo / "other.toml")
    (repo / "other.toml").write_text((repo / "other.toml").read_text(encoding="utf-8").replace('target = "prove_rollout:rollout"\n', ""), encoding="utf-8")
    typed = ("other.toml", "--target", "prove_rollout:rollout", "--store", "kept-runs")
    good = tried(repo, tmp_path / "good", "--yes", *typed)
    assert good.code == 0, good.result
    (after_good,) = good.result.nexts
    assert sorted(shlex.split(after_good)) == sorted([COMMAND, "sweep", *typed]), after_good
    (repo / "fail").touch()
    bad = tried(repo, tmp_path / "bad", "--yes", *typed)
    assert bad.code == 1, bad.result
    (after_bad,) = bad.result.nexts
    assert sorted(shlex.split(after_bad)) == sorted([COMMAND, "sweep", "--try", *typed]), after_bad
    assert not (repo / "kept-runs").exists()


# ---------- K4 stdout holds only Prove's result ----------

WAYS: dict[str, tuple[str, str]] = {
    "print in the rollout": ("", f'print("{BANNER}")'),
    "a write with no newline": ("", f'sys.stdout.write("{BANNER}")'),
    "the binary buffer": ("", f'sys.stdout.buffer.write(b"{BANNER}\\n")'),
    "file descriptor 1": ("", f'os.write(1, b"{BANNER}\\n")'),
    "a child process that inherits stdout": ("", f'subprocess.run(["sh", "-c", "echo {BANNER}"])'),
    "print when the target is imported": (f'print("{BANNER}")', "pass"),
}
TRY_KEYS = {"condition", "seed", "outcome", "t", "horizon", "meta", "seconds", "printed"}


def document(out: str) -> dict[str, Any]:
    """The whole of stdout as one strict JSON document of ``sweep``'s schema."""
    doc = json.loads(out, parse_constant=lambda word: pytest.fail(f"{word} in a strict JSON document"))
    assert isinstance(doc, dict) and list(doc)[:3] == ["schema", "verdict", "sentence"], list(doc)[:5]
    assert doc["schema"] == "poisson-prove.sweep/1", doc["schema"]
    assert out.endswith("}\n"), repr(out[-20:])
    return doc


@pytest.mark.parametrize("form", ["text", "--json"])
@pytest.mark.parametrize("way", list(WAYS))
def test_k4_whatever_the_rollout_writes_is_on_stderr_once_and_never_on_stdout(way: str, form: str, tmp_path: Path) -> None:
    at_import, body = WAYS[way]
    repo = counted(tmp_path, body, at_import)
    child = tried(repo, tmp_path, "--yes", *(() if form == "text" else ("--json",)))
    assert child.code == 0, child.result
    assert BANNER not in child.out, child.out
    assert child.err.count(BANNER) == 1, child.err
    if form == "--json":
        assert document(child.out)["try"]["printed"] == 1, child.out
    else:
        # Every line of stdout is one of Prove's own kinds.
        for line in child.out.splitlines():
            assert pf11.FIRST_LINE.match(line) or re.match(r"^  \S.*? {2,}\S", line) or line.startswith("  next: "), line
        (printed,) = pf11.detail(child.out, "printed")
        assert re.match(r"^1 lines?\b", printed) and "stderr" in printed, printed


def test_k4_json_is_one_sweep_document_with_a_try_object(tmp_path: Path) -> None:
    # What the rollout writes to its stderr is passed on and is not counted as printed (reading g).
    repo = counted(tmp_path, 'print("said on stderr", file=sys.stderr)')
    child = tried(repo, tmp_path, "--yes", "--json")
    assert child.code == 0, child.result
    assert child.err.count("said on stderr") == 1, child.err
    doc = document(child.out)
    (made,) = calls(tmp_path)
    assert doc["verdict"] == "ok" and '"resolved"' in doc["sentence"], doc
    assert list(doc)[-1] == "next" and doc["next"] == [f"{COMMAND} sweep"], doc
    trial = doc["try"]
    assert TRY_KEYS <= set(trial), sorted(trial)
    assert trial["condition"] == FIRST_CONDITION and trial["seed"] == made["seed"], trial
    assert (trial["outcome"], trial["t"], trial["horizon"]) == ("resolved", 7, 20), trial
    assert trial["meta"] == {"case_id": "refund"}, trial
    assert isinstance(trial["seconds"], float) and 0 < trial["seconds"] < 120, trial
    assert trial["printed"] == 0, trial
    assert "run_id" not in doc and "run_name" not in doc, sorted(doc)


def test_k4_a_failed_call_under_json_leaves_stdout_empty_with_the_same_exit_code(tmp_path: Path) -> None:
    repo = counted(tmp_path, f'print("{BANNER}"); raise ValueError("no")')
    child = tried(repo, tmp_path, "--yes", "--json")
    assert child.code == 1, child.result
    assert child.out == "", child.out
    assert len(error_lines(child.err)) == 1 and child.err.count(BANNER) == 1, child.err
    assert child.result.nexts == [TRY], child.result.nexts


# ---------- K5 this machine, on every spec ----------

K5_TABLES = {
    "[modal]": '\n[modal]\nconcurrency = 2\n\n[modal.image]\npython = "3.11"\n',
    "[cloud]": '\n[cloud]\nprovider = "aws"\nregion = "eu-west-1"\nmachine_type = "m7i.xlarge"\nnodes = 2\nledger = "spend.jsonl"\n'
               "stop_cost = 1.0\nmax_cost = 1.5\nest_seconds_per_episode = 0.25\n",
}


@pytest.mark.parametrize("table", list(K5_TABLES))
def test_k5_a_spec_set_to_modal_or_a_cloud_account_is_still_tried_on_this_machine_with_a_note(table: str, tmp_path: Path) -> None:
    repo = counted(tmp_path, spec=SPEC + K5_TABLES[table])
    before = pf11.snapshot(repo)
    # Neither extra is there to import, so nothing of Modal's or the cluster's can be called.
    child = tried(repo, tmp_path, "--yes", hide=("modal", "burla"))
    assert child.code == 0, child.result
    assert len(calls(tmp_path)) == 1
    assert "this machine" in child.out.splitlines()[0], child.out
    here = [note for note in child.result.notes if "this machine" in note]
    assert len(here) == 1, child.err
    assert child.attempts == [], child.attempts
    assert pf11.snapshot(repo) == before


# ---------- K6 Ctrl-C during the call ----------


def test_k6_ctrl_c_during_the_call_ends_the_calls_process_exits_130_and_writes_nothing(tmp_path: Path) -> None:
    repo = counted(tmp_path, "time.sleep(300)")
    before = pf11.snapshot(repo)
    home = tmp_path / "home"
    home.mkdir()
    command = Path(sys.executable).parent / COMMAND
    env = {
        "PATH": f"{command.parent}{os.pathsep}/usr/bin{os.pathsep}/bin", "HOME": str(home), "PYTHONPATH": str(SRC), "TMPDIR": str(home),
        "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8", "M4_CALLS": str(tmp_path / "calls.jsonl"), **blas_thread_cap(),
    }
    # Through the launcher, so the interrupt is live however the tests themselves were started.
    launch = [sys.executable, "-c", "import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execv(sys.argv[1], sys.argv[1:])"]
    proc = subprocess.Popen([*launch, str(command), "sweep", "--try", "--yes"], cwd=repo, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 90
        while not calls(tmp_path) and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        made = calls(tmp_path)
        assert len(made) == 1, (proc.poll(), made)
        pid = made[0]["pid"]
        assert pid != proc.pid, "the rollout ran in the command's own process"
        assert alive(pid)
        proc.send_signal(signal.SIGINT)
        out, err = proc.communicate(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert proc.returncode == 130, (out, err)
    assert gone(pid), "the call's process outlived the interrupt"
    assert "ok" not in verdicts(out) and "Traceback" not in err, (out, err)
    assert len(calls(tmp_path)) == 1
    assert pf11.snapshot(repo) == before
    assert files_under(home) == []


# ---------- K7 the skill ----------


def skill_body(tmp_path: Path) -> str:
    return pf11.split_frontmatter(pf11.fresh_skill(tmp_path))[1]


def words_of(command: str) -> list[str]:
    return shlex.split(command)


def hand_over_items(body: str) -> list[str]:
    """The numbered items of "Hand over", each with everything under it."""
    text = pf11.section(body, "## Hand over")
    parts = re.split(r"^(\d+)\. ", text, flags=re.M)
    assert [int(n) for n in parts[1::2]] == list(range(1, len(parts[1::2]) + 1)), parts[1::2]
    return parts[2::2]


K7_PARTS = [
    "seven steps in order",
    "step 6 asks before it calls",
    "--yes goes to the trial and to nothing else",
    "the hand-over's first line is ready or not ready",
    "the four commands of the loop, each in its own block",
    "one reason line for each axis",
    "the last output of the check and of the call, as printed",
    "the cost line names no model call for an agent that calls none",
]


@pytest.mark.parametrize("part", K7_PARTS)
def test_k7_the_skill_is_seven_steps_that_ask_call_once_and_hand_over_the_loop(part: str, tmp_path: Path) -> None:
    body = skill_body(tmp_path)
    steps = pf11.steps_of(body)
    agent = [command for _, command in pf11.commands(body, "bash")]
    person = [command for section, command in pf11.commands(body, "text") if section == "## Hand over"]
    hand_over = pf11.section(body, "## Hand over")

    if part == "seven steps in order":
        assert [s.number for s in steps] == [1, 2, 3, 4, 5, 6, 7], [s.number for s in steps]
        assert [s.title for s in steps[4:]] == ["Run the check", "Call it once", "Hand over"], [s.title for s in steps]
        # What the agent runs: the check, and the one call.
        assert sorted(words_of(c)[1:] for c in agent) == [["sweep", "--dry-run"], ["sweep", "--try", "--yes"]], agent
        assert "--try" not in steps[4].text and "--try" in steps[5].text, (steps[4].text, steps[5].text)
    elif part == "step 6 asks before it calls":
        text = steps[5].text
        blocks = [f for f in pf11.fences("## Steps\n" + text) if f.lang == "bash"]
        assert [list(f.lines) for f in blocks] == [[f"{TRY} --yes"]], blocks
        asked = re.search(r'"[^"\n]*\?"', text)
        assert asked and asked.start() < text.index("```bash"), text
        question = asked.group(0)
        assert "once" in question and "cost" in question, question
        before_the_call = text[: text.index("```bash")]
        assert re.search(r"\byes\b", before_the_call) and re.search(r"\bno\b", before_the_call), before_the_call
        # What each exit code means: go on, fix the wrapper and check again, or hand over as it is.
        after_the_call = text[text.index("```bash"):]
        assert "prove_rollout.py" in after_the_call and "not ready" in after_the_call, after_the_call
        assert re.search(r"\bsteps? 5\b", after_the_call), after_the_call
        assert "not ready" in before_the_call, before_the_call
    elif part == "--yes goes to the trial and to nothing else":
        everything = agent + [command for _, command in pf11.commands(body, "text")]
        assert [c for c in everything if {"--yes", "-y"} & set(words_of(c))] == [f"{TRY} --yes"], everything
        own = pf11.section(body, pf11.OWN_RULES)
        assert "--yes" in own and "--try" in own and re.search(r"\bsaid yes\b|\ba yes\b|\bsays yes\b", own), own
        # No rule still says a sweep is never run without --dry-run alone: the trial is one too.
        never = [line for line in own.splitlines() if re.search(r"\bnever run\b", line, re.I) and "--dry-run" in line]
        assert never and all("--try" in line for line in never), own
    elif part == "the hand-over's first line is ready or not ready":
        first = hand_over_items(body)[0]
        ready = re.search(r"`ready: [^`\n]*`", first)
        not_ready = re.search(r"`not ready: [^`\n]*`", first)
        assert ready and not_ready, first
        assert "check" in ready.group(0) and "returned" in ready.group(0) and '"' in ready.group(0), ready.group(0)
        assert re.search(r"first line", first, re.I), first
    elif part == "the four commands of the loop, each in its own block":
        blocks = [f for f in pf11.fences(body) if f.lang == "text" and f.section == "## Hand over"]
        assert all(len([line for line in f.lines if line.strip()]) == 1 for f in blocks), blocks
        # First run M6, L1: after the loop, one more block, the comparison of an outcome the
        # loop's diff leaves out; the four of the loop are the blocks before it (reading p).
        assert len(person) == 5 and "--event" in words_of(person[4]), person
        person = person[:4]
        shapes = []
        for command in person:
            words = words_of(command)
            assert words[0] == COMMAND, command
            shapes.append(tuple(w for w in words[1:] if w.startswith("-") or w in ("sweep", "diff", "latest")))
        loop = [("sweep", "--note"), ("sweep", "--pair-with", "latest", "--note"), ("diff",)]
        assert sorted(shapes) == sorted([*loop, ("sweep", "--try")]), shapes
        assert [s for s in shapes if s in loop] == loop, shapes
        (before,) = [words_of(c) for c in person if "--pair-with" not in c and "--note" in c]
        assert before[before.index("--note") + 1].startswith("before:"), before
        # Between the two sweeps the person is told to make the change.
        text = hand_over
        first, second = text.index(person[shapes.index(loop[0])]), text.index(person[shapes.index(loop[1])])
        assert re.search(r"\bchange\b", text[first:second]), text[first:second]
        assert re.search(r"not ready", text[text.index("```text"):], re.I), "the trial is the first command when not ready"
        # The loop is the person's to run: the hand-over says so after its last command.
        assert re.search(r"\b(?:do not|never) run\b", text[text.rindex("```"):], re.I), text[text.rindex("```"):]
    elif part == "one reason line for each axis":
        # First run M6, A3: the item for the axes not added also speaks of axes; this is the item
        # that opens with the axes of prove.toml (reading p).
        items = [item for item in hand_over_items(body) if re.match(r"Each axis\b[^.\n]*`prove\.toml`", item)]
        assert len(items) == 1 and "values" in items[0] and re.search(r"\bwhy\b", items[0]), hand_over
    elif part == "the last output of the check and of the call, as printed":
        items = [item.splitlines()[0] for item in hand_over_items(body) if re.search(r"\boutput\b", item.splitlines()[0])]
        assert len(items) == 1, hand_over
        assert re.search(r"\bcheck\b", items[0]) and re.search(r"\bcall\b", items[0]) and "printed" in items[0], items[0]
    else:
        tail = hand_over.split("What the person must confirm:", 1)
        assert len(tail) == 2, hand_over
        costs = [line for line in tail[1].splitlines() if line.startswith("- ") and "replicates" in line and "cost" in line]
        assert len(costs) == 1, tail[1]
        assert "with all its model calls" not in costs[0], costs[0]
        assert re.search(r"calls no model", costs[0]) and re.search(r"model calls", costs[0]), costs[0]


# ---------- K8 the scripted run ----------


@dataclass
class HandOver:
    #: the hand-over's first line, as the stand-in would say it
    first: str
    #: every command the stand-in ran, with how it ended
    ran: list[tuple[str, pf11.Child]]
    fixes: int = 0

    @property
    def tries(self) -> list[pf11.Child]:
        return [child for command, child in self.ran if "--try" in shlex.split(command)]


def follow(repo: Path, base: Path, *, wrapper: str, spec: str, fix: str | None = None) -> HandOver:
    """A coding agent's stand-in, following the written skill step by step in ``repo`` with a
    person who says yes to the call. It runs only the commands the skill shows, reads Prove's
    output the way the skill says to, and writes only the skill's two files. ``fix`` is the wrapper
    it would write if step 6 told it the wrapper was wrong."""
    body = pf11.split_frontmatter((repo / pf11.FOUR[0]).read_text(encoding="utf-8"))[1]
    steps = pf11.steps_of(body)
    assert [s.number for s in steps] == [1, 2, 3, 4, 5, 6, 7], steps
    (check,) = [c for s, c in pf11.commands(body, "bash") if s == "## The check"]
    (call,) = [line for f in pf11.fences("## Steps\n" + steps[5].text) if f.lang == "bash" for line in f.lines]
    ran: list[tuple[str, pf11.Child]] = []

    def run(command: str) -> pf11.Child:
        child = pf11.run_child(repo, base / f"run-{len(ran)}", *shlex.split(command)[1:])
        ran.append((command, child))
        return child

    # 1 to 4: read the code and run nothing; the wrapper; the spec at 20 replicates with [declare].
    assert "prove_rollout.py" in steps[1].text and "prove.toml" in steps[2].text and "[declare]" in steps[3].text
    (repo / "prove_rollout.py").write_text(wrapper, encoding="utf-8")
    (repo / "prove.toml").write_text(spec, encoding="utf-8")
    fixes = 0
    while True:
        # 5: the check, until it passes; at most three fixes over the whole setup.
        last = run(check)
        while last.code != 0:
            assert fixes < 3, [(c, child.err) for c, child in ran]
            fixes += 1
            offered = pf11.replicates_offered(last.result)
            (repo / "prove.toml").write_text(pf11.with_replicates((repo / "prove.toml").read_text(encoding="utf-8"), offered), encoding="utf-8")
            last = run(check)
        # 6: the person says yes; the one call.
        assert "--try" in steps[5].text
        called = run(call)
        if called.code == 0:
            (returned,) = re.findall(r'returned "([^"]+)"', called.out)
            return HandOver(f'ready: the check passed and one real call returned "{returned}"', ran, fixes)
        assert called.code == 1, called.result
        raised_in = frame_lines(called.err).get("raised in", "")
        if raised_in.split(":")[0] == "prove_rollout.py" and fix is not None and fixes < 3:
            fixes += 1
            (repo / "prove_rollout.py").write_text(fix, encoding="utf-8")
            fix = None
            continue
        return HandOver(f"not ready: {called.result.error}", ran, fixes)


def demo_repo(base: Path) -> tuple[Path, str, str]:
    """A repository holding the demo agent and the written skill, and the wrapper and the spec a
    coding agent would write for it (the spec at the skill's 20 replicates)."""
    repo = base / "repo"
    repo.mkdir(parents=True)
    scratch = base / "with-setup"
    scratch.mkdir()
    assert pf11.run(repo, "init", "--demo").code == 0
    assert pf11.run(scratch, "init", "--demo", "--with-setup").code == 0
    assert pf11.run(repo, "init", "--agent").code == 0
    wrapper = (scratch / "prove_rollout.py").read_text(encoding="utf-8")
    spec = pf11.with_replicates((scratch / "prove.toml").read_text(encoding="utf-8"), 20)
    return repo, wrapper, spec


#: The hands-on's wrapper: the ticket's name passed where the bot wants its rate.
RIGHT_CALL = '    ticket = TICKETS[cfg["ticket"]]\n    reply = handle(ticket, temperature=cfg["temperature"], seed=seed)\n'
BROKEN_CALL = '    reply = handle(cfg["ticket"], temperature=cfg["temperature"], seed=seed)\n'


def test_k8_on_the_hands_on_wrapper_the_stand_in_stops_not_ready_naming_the_typeerror_and_with_the_fix_is_ready(tmp_path: Path) -> None:
    repo, right, spec = demo_repo(tmp_path)
    assert right.count(RIGHT_CALL) == 1, right
    broken = right.replace(RIGHT_CALL, BROKEN_CALL)
    before = pf11.snapshot(repo)

    first = follow(repo, tmp_path / "first", wrapper=broken, spec=spec, fix=right)

    # The check passed on a wrapper that fails on every call; the one call caught it.
    assert [child.code for child in first.tries] == [1], first.ran
    assert first.first.startswith("not ready: ") and "TypeError" in first.first, first.first
    called = first.tries[0]
    frames = frame_lines(called.err)
    assert frames.get("raised in", "").startswith("support_bot.py:"), called.err
    wanted = f"prove_rollout.py:{line_of(repo, BROKEN_CALL.strip())}"
    assert wanted in frames.values(), called.err
    # Before any fix: the raise is in the agent's own code, so the stand-in changed nothing.
    assert (repo / "prove_rollout.py").read_text(encoding="utf-8") == broken
    assert pf11.added(before, pf11.snapshot(repo), repo) == sorted(pf11.WRITES)

    second = follow(repo, tmp_path / "second", wrapper=right, spec=(repo / "prove.toml").read_text(encoding="utf-8"))

    assert [child.code for child in second.tries] == [0], second.ran
    declared = set(re.search(r"^outcomes = \[(.*)\]$", spec, flags=re.M).group(1).replace('"', "").split(", "))  # type: ignore[union-attr]
    found = re.fullmatch(r'ready: the check passed and one real call returned "([^"]+)"', second.first)
    assert found and found.group(1) in declared, second.first
    assert pf11.added(before, pf11.snapshot(repo), repo) == sorted(pf11.WRITES)
    assert not (repo / "prove-runs").exists() and not (repo / ".poisson").exists()


def test_k8_on_the_demo_with_no_key_and_no_network_the_stand_in_reaches_ready(tmp_path: Path) -> None:
    repo, wrapper, spec = demo_repo(tmp_path)
    before = pf11.snapshot(repo)

    over = follow(repo, tmp_path / "runs", wrapper=wrapper, spec=spec)

    assert re.fullmatch(r'ready: the check passed and one real call returned "(resolved|unresolved|timeout)"', over.first), over.first
    commands = [shlex.split(command)[1:] for command, _ in over.ran]
    # The check was refused for its size once and fixed; --yes went to the trial alone.
    assert commands == [["sweep", "--dry-run"], ["sweep", "--dry-run"], ["sweep", "--try", "--yes"]], commands
    assert [child.code for _, child in over.ran] == [1, 0, 0], over.ran
    # No key in the environment the commands ran in, and nothing reached for a socket.
    assert not any(child.attempts for _, child in over.ran), [child.attempts for _, child in over.ran]
    # Nothing but the skill's two files: no run, no store, no byte code.
    assert pf11.added(before, pf11.snapshot(repo), repo) == sorted(pf11.WRITES)
    assert not (repo / "prove-runs").exists() and not (repo / ".poisson").exists()


# ---------- K9 the open line ----------

K9_CASES = ["no --repo", "--repo .", "--repo a link to this folder", "--repo another folder", "--repo another folder, from here"]


@pytest.mark.parametrize("case", K9_CASES)
def test_k9_init_agent_prints_the_open_line_exactly_when_repo_is_another_folder(case: str, tmp_path: Path) -> None:
    here = tmp_path / "here"
    here.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    (tmp_path / "link").symlink_to(here, target_is_directory=True)
    typed = {
        "no --repo": None, "--repo .": ".", "--repo a link to this folder": str(tmp_path / "link"),
        "--repo another folder": str(other), "--repo another folder, from here": "../other",
    }[case]
    elsewhere = "another folder" in case
    r = pf11.run(here, "init", "--agent", *([] if typed is None else ["--repo", typed]))
    assert r.code == 0 and r.err == "", r
    out = r.out.splitlines()
    opened = pf11.detail(r.out, "open")
    if elsewhere:
        assert len(opened) == 1 and opened[0].endswith(f" {typed}") and "coding agent" in opened[0], r.out
        at = out.index(f"  open  {opened[0]}")
        assert out[at - 1].startswith("  wrote  ") and out[at + 1] == f"  prompt  {pf11.PROMPT}", out
    else:
        assert opened == [], r.out
    # First run M6, A7: one more detail line, on how to ask for more than the cases (reading r).
    assert len(out) == 1 + 4 + (4 if elsewhere else 3), r.out
    # The four files are what they are without the line.
    repo = other if elsewhere else here
    fresh = pf11.fresh_skill(tmp_path)
    for f in pf11.FOUR:
        assert (repo / f).read_text(encoding="utf-8") == (fresh if f.endswith("SKILL.md") else pf11.PROMPT + "\n"), f


# ---------- K10 the loop's next line ----------


def swept(repo: Path, base: Path, *argv: str) -> pf11.Child:
    child = pf11.run_child(repo, base, "sweep", *argv, "--yes", timeout=300)
    assert child.code == 0, child.result
    return child


def run_name(out: str) -> str:
    (done,) = [line for line in out.splitlines() if line.startswith("done  ")]
    (name,) = re.findall(r'run "([^"]+)"', done)
    return name


def with_setup(base: Path, replicates: int | None = None) -> Path:
    repo = base / "demo"
    repo.mkdir(parents=True)
    assert pf11.run(repo, "init", "--demo", "--with-setup").code == 0
    if replicates is not None:
        (repo / "prove.toml").write_text(pf11.with_replicates((repo / "prove.toml").read_text(encoding="utf-8"), replicates), encoding="utf-8")
    return repo


def test_k10_a_complete_sweep_of_your_own_agent_ends_with_the_then_line_and_the_paired_sweep_naming_the_run(tmp_path: Path) -> None:
    repo = with_setup(tmp_path)
    child = swept(repo, tmp_path / "before")
    out = child.out.splitlines()
    name = run_name(child.out)
    assert child.result.nexts == [f'{COMMAND} sweep --pair-with "{name}"'], child.result.nexts
    assert out[-1].startswith("  next: ") and out[-2].startswith("  then  "), out[-3:]
    then = out[-2]
    assert "change" in then and "same seeds" in then, then
    assert len(pf11.detail(child.out, "then")) == 1, child.out
    assert "latest" not in child.result.nexts[0], child.result.nexts


K10_TYPED: dict[str, tuple[int | None, tuple[str, ...]]] = {
    "nothing typed": (None, ()),
    "a spec path, --target and --store typed": (None, ("bot.toml", "--target", "prove_rollout:rollout", "--store", "kept-runs")),
    "--replicates typed": (20, ("--replicates", "194")),
    "--max-mde typed": (20, ("--max-mde", "1")),
}


@pytest.mark.parametrize("typed", list(K10_TYPED))
def test_k10_the_printed_next_run_once_starts_a_sweep_paired_with_that_run(typed: str, tmp_path: Path) -> None:
    replicates, argv = K10_TYPED[typed]
    repo = with_setup(tmp_path, replicates)
    if argv and argv[0].endswith(".toml"):
        os.rename(repo / "prove.toml", repo / argv[0])
    first = swept(repo, tmp_path / "before", *argv)
    name = run_name(first.out)
    (printed,) = first.result.nexts
    words = shlex.split(printed)
    assert words[:2] == [COMMAND, "sweep"] and words[words.index("--pair-with") + 1] == name, printed
    for word in argv:
        assert word in words, (word, printed)

    second = swept(repo, tmp_path / "after", *words[2:])

    (done,) = [line for line in second.out.splitlines() if line.startswith("done  ")]
    assert f'paired with "{name}"' in done, done
    # A paired sweep's ending is as it was: the comparison next, and no then line.
    assert len(second.result.nexts) == 1 and shlex.split(second.result.nexts[0])[:2] == [COMMAND, "diff"], second.result.nexts
    assert pf11.detail(second.out, "then") == [], second.out


def test_k10_a_sweep_finished_by_resume_ends_the_same_way(tmp_path: Path) -> None:
    """A first sweep stopped part way and finished with ``--resume`` is a complete sweep paired with
    nothing: it ends with the ``then`` line and the paired sweep, which starts when run."""
    repo = with_setup(tmp_path)
    part_way = pf11.run_child(repo, tmp_path / "part", "sweep", "--max-rollouts", "100", "--yes", timeout=300)
    assert part_way.code == 3, part_way.result
    finished = swept(repo, tmp_path / "rest", "--resume")
    name = run_name(finished.out)
    assert finished.result.nexts == [f'{COMMAND} sweep --pair-with "{name}"'], finished.result.nexts
    assert len(pf11.detail(finished.out, "then")) == 1, finished.out
    second = swept(repo, tmp_path / "after", *shlex.split(finished.result.nexts[0])[2:])
    assert f'paired with "{name}"' in second.out, second.out


def test_k10_the_packaged_mocks_ending_is_as_it_was(tmp_path: Path) -> None:
    repo = tmp_path / "quickstart"
    repo.mkdir()
    assert pf11.run(repo, "init", "--example").code == 0
    child = swept(repo, tmp_path / "before")
    assert child.result.nexts == [f"{COMMAND} sweep --target poisson_prove.examples.mock_agent:rollout_patched --pair-with latest"], child.result.nexts
    assert pf11.detail(child.out, "then") == [], child.out


# ---------- section 5.4 and section 8: the docs and the CHANGELOG ----------


def page(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def part(text: str, heading: str) -> str:
    """The text under a ``##`` heading that starts with ``heading``, up to the next ``##``."""
    found = re.search(rf"(?ms)^## {re.escape(heading)}.*?(?=^## |\Z)", text)
    assert found, heading
    return found.group(0)


def missing(text: str, *facts: str | re.Pattern[str]) -> list[str]:
    flat = " ".join(text.split())
    return [str(fact) for fact in facts if not (fact.search(flat) if isinstance(fact, re.Pattern) else fact in flat)]


DOCS_CASES: dict[str, Callable[[], list[str]]] = {
    # The seven steps, the trial call and its question, the hand-over, the loop, the one exception
    # to "never --yes", the open line.
    "docs/setup-with-your-agent.md": lambda: missing(
        page("docs/setup-with-your-agent.md"), re.compile(r"\bseven steps\b", re.I), "sweep --try", "ready:", "not ready:",
        "--pair-with latest", f"{COMMAND} diff", "--note", "--yes", "your coding agent in", "init --demo"),
    # --try and what it does, its limit, its exit codes; the then line and the paired next.
    "docs/commands/sweep.md": lambda: missing(
        page("docs/commands/sweep.md"), "--try", "this machine", "stores nothing", "300 s", "--episode-timeout", "[y/N]", "raised in",
        "then change your agent", re.compile(r'next: poisson-prove sweep --pair-with "[^"]+"'))
    + missing(part(page("docs/commands/sweep.md"), "Exit codes"), "--try", "130"),
    "docs/commands/init.md": lambda: missing(page("docs/commands/init.md"), "open your coding agent in", "--repo"),
    "README.md": lambda: missing(part(page("README.md"), "Let your coding agent set it up"), "sweep --try", "--pair-with", "ready"),
}


@pytest.mark.parametrize("case", list(DOCS_CASES))
def test_the_docs_teach_the_trial_call_the_hand_over_and_the_loop(case: str) -> None:
    """Section 5.4, by facts (reading t)."""
    assert DOCS_CASES[case]() == [], case


def test_the_0_5_0_entry_has_the_trial_the_skill_and_the_loops_next() -> None:
    """Section 8: under ``## 0.5.0`` an Added item for ``sweep --try``, a Changed item for the
    skill and a Changed item for the ``next:`` after a sweep of your own agent."""
    text = page("CHANGELOG.md")
    entry = text.split("\n## 0.5.0", 1)[1].split("\n## ", 1)[0]

    def items(heading: str) -> list[str]:
        assert f"\n### {heading}\n" in entry, entry[:400]
        block = entry.split(f"\n### {heading}\n", 1)[1].split("\n### ", 1)[0]
        return [" ".join(item.split()) for item in re.split(r"(?m)^- ", block) if item.strip()]

    # First run M6 adds an item of its own on the trial and one on the skill; M4's are the two for #5.
    trial = [item for item in items("Added") if "sweep --try" in item and "(#5)" in item]
    assert len(trial) == 1, items("Added")
    assert missing(trial[0], "(#5)", "once", "this machine", "stores nothing") == [], trial[0]
    skill = [item for item in items("Changed") if "skill" in item and "(#5)" in item]
    assert len(skill) == 1, items("Changed")
    assert missing(skill[0], "(#5)", "init --agent", "sweep --try", "ready", "not ready", "--pair-with", "diff") == [], skill[0]
    loop = [item for item in items("Changed") if "next:" in item and "skill" not in item]
    assert len(loop) == 1, items("Changed")
    assert missing(loop[0], "your own agent", "pairs") == [], loop[0]
