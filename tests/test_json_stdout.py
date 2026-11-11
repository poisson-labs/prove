"""``--json`` keeps stdout one strict JSON document whatever the target writes, and the exit code
still says what happened (issue 28; rule 9 of ``docs/cli-look.md``).

**What is pinned.** The command line as a caller runs it: a real process with real pipes, read as
bytes. ``main(stdout=StringIO())`` hides the defect, because a print goes to the real stdout and not
to the StringIO, so every case here that means to see it starts an interpreter of its own.

**Readings this file fixes.**

- **r1** What the target writes goes to stderr: every write once, as it happens, not at exit. That
  covers every level a target can write at: ``print``, ``sys.stdout.buffer``, ``sys.__stdout__``,
  ``os.write(1, ...)``, the C library, a child process that inherits stdout, a thread, a logging
  handler, an ``atexit`` hook, and the same under ``--episode-timeout``.
  A timed rollout's forked child is ended the moment the parent has its outcome, and on main that
  loses whatever it has not flushed, in some runs; under ``--json`` every write arrives.
- **r2** A refusal or a failure before any document leaves stdout empty, with an ``error: `` line on
  stderr, and exits as it does without ``--json``. A run that started and stopped still has its
  document and exits 3; Ctrl-C has its document and exits 130.
- **r3** The verbs. ``sweep`` is the one verb that runs the target. ``ui --open`` is the one other
  that starts a program, the browser, which inherits stdout. Every verb that takes ``--json`` is held
  here in a real process: ``init``, ``sweep``, ``diff``, ``report``, ``check``, ``serve``, ``inspect``,
  ``runs``, ``paired`` and ``ui``.
- **r4** Without ``--json`` nothing moves: the target's text stays on stdout at every level.
- **r5** ``main(stdout=...)`` stays as it is: the document goes to the stream it was given, the
  target's print stays on the caller's stdout, and the caller's stdout is left as it was found. Under
  ``contextlib.redirect_stdout`` the document goes to the redirect.
- **r6** Modal. The target runs in the container and is never imported in the sweep's process, so a
  target's write cannot reach the document there; the fake's container shows that. The Modal client
  does run in the sweep's process, and whatever it writes to stdout is held like a target's.
- **r7** The cloud backend (0.2.1's Burla backend, renamed in 0.3.0). The target is imported in the
  sweep's process, so a print at import and an ``atexit`` hook break the document as they do locally. A rollout runs on a worker, and what it writes there
  stays there; the launcher's own output goes to its log.
- **r8** The cloud backend's rehearsal and its fresh-interpreter batches read a pickle from a child's
  stdout, so a rollout that writes through fd 1 fails the sweep with ``UnpicklingError``, with or without
  ``--json``. An unflushed ``print`` only escapes because the pickle overtakes it. Held here so that
  such a target runs.
- **r9** A target that ends the process by ``sys.exit`` must not leave exit 0 and no document: the code
  says it failed, or the document says so. ``os._exit`` in
  the sweep's own process cannot be held and is not pinned.
- **r10** A target that closes or replaces its stdout still leaves one document. ``sys.stdout.detach()`` is not pinned: it ends in exit 120 from the
  interpreter's own shutdown, after the document.

The marker text starts with ``f`` on purpose: ``MARK\\n`` happens to parse as pickle opcodes, and
hid r8 the first time it was tried.
"""

from __future__ import annotations

import contextlib
import json
import multiprocessing
import os
import pty
import select
import signal
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from pf12_support import copy_store
from reading_support import cli, reading_world  # noqa: F401
from rb_cloud_support import CloudWorld, world
from test_bu_cloud_backend import LAUNCH, PIN, SUBMIT, Fake, Pool, cloud_fields, write_sweep

SRC = Path(__file__).resolve().parents[1] / "src"
BANNER = "framework banner"
SPEC = """\
target = "noisy:rollout"
target_id = "noisy"
t_unit = "steps"
replicates = 2

[axes.task]
type = "categorical"
values = ["a"]

[declare]
failures = ["timeout"]
"""
ROLLOUTS = 2
SWEEP = ("sweep", "--json", "--yes", "--max-mde", "1")
TIMEOUT = ("--episode-timeout", "60")
PATHS = {"in process": (), "under --episode-timeout": TIMEOUT}


def _target(at_import: str = "", in_rollout: str = "pass", outcome: str = "completed") -> str:
    return (
        "from poisson_prove.episode import Episode\n"
        "import atexit, ctypes, logging, os, subprocess, sys, threading, time\n"
        f"{at_import}\n"
        "def rollout(cfg, seed):\n"
        f"    {in_rollout}\n"
        f'    return Episode(outcome="{outcome}", t=1.0, horizon=1.0)\n'
    )


class Way(NamedTuple):
    """One way of writing to stdout: the code at import and in the rollout, and how many times the
    marker is written over a sweep of two rollouts."""

    at_import: str
    in_rollout: str
    times: int


_B = BANNER
WAYS: dict[str, Way] = {
    "print in the rollout": Way("", f'print("{_B}")', ROLLOUTS),
    "flushed print in the rollout": Way("", f'print("{_B}", flush=True)', ROLLOUTS),
    "write with no newline": Way("", f'sys.stdout.write("{_B}")', ROLLOUTS),
    "the binary buffer": Way("", f'sys.stdout.buffer.write(b"{_B}\\n")', ROLLOUTS),
    "the interpreter's own stdout": Way("", f'sys.__stdout__.write("{_B}\\n")', ROLLOUTS),
    "os.write in the rollout": Way("", f'os.write(1, b"{_B}\\n")', ROLLOUTS),
    "the C library": Way("", f'ctypes.CDLL(None).puts(b"{_B}"); ctypes.CDLL(None).fflush(None)', ROLLOUTS),
    "a child that inherits stdout": Way("", f'subprocess.run(["sh", "-c", "echo {_B}"])', ROLLOUTS),
    "os.system": Way("", f'os.system("echo {_B}")', ROLLOUTS),
    "a thread": Way("", f't = threading.Thread(target=print, args=("{_B}",)); t.start(); t.join()', ROLLOUTS),
    "a logging handler": Way('logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")', f'logging.info("{_B}")', ROLLOUTS),
    "print at import": Way(f'print("{_B}")', "pass", 1),
    "flushed print at import": Way(f'print("{_B}", flush=True)', "pass", 1),
    "os.write at import": Way(f'os.write(1, b"{_B}\\n")', "pass", 1),
    "a child at import": Way(f'subprocess.run(["sh", "-c", "echo {_B}"])', "pass", 1),
    "print from atexit": Way(f'atexit.register(lambda: print("{_B}"))', "pass", 1),
    "os.write from atexit": Way(f'atexit.register(lambda: os.write(1, b"{_B}\\n"))', "pass", 1),
    "a child from atexit": Way(f'atexit.register(lambda: subprocess.run(["sh", "-c", "echo {_B}"]))', "pass", 1),
}
#: The ways whose text sits in a buffer of the rollout's process until something flushes it.
HELD_IN_THE_CHILDS_BUFFER = {
    "print in the rollout", "write with no newline", "the binary buffer", "the interpreter's own stdout", "a thread", "a logging handler",
}
IMPORT_WAYS = [name for name in WAYS if name.endswith("at import")]
#: What the look's rule 9 asks of a document, and what a reader of these tests can count on.
FIRST_KEYS = ["schema", "verdict", "sentence"]


def _child_env(base: Path, **more: str) -> dict[str, str]:
    drop = ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "PYTHONWARNINGS", "CI", "BROWSER", "PYTHONUNBUFFERED")
    env = {key: value for key, value in os.environ.items() if key not in drop}
    home = base / "home"
    home.mkdir(exist_ok=True)
    env.update(PYTHONPATH=os.pathsep.join([str(SRC), str(base)]), HOME=str(home), NO_COLOR="1", PYTHONIOENCODING="utf-8")
    env.update(more)
    return env


def _folder(base: Path, source: str, spec: str = SPEC) -> Path:
    (base / "noisy.py").write_text(source, encoding="utf-8")
    (base / "prove.toml").write_text(spec, encoding="utf-8")
    return base


def _prove(base: Path, *argv: str, env: dict[str, str] | None = None, timeout: float = 300) -> subprocess.CompletedProcess[bytes]:
    """One command in a process of its own: stdout and stderr each a pipe of its own, read as bytes."""
    return subprocess.run(
        [sys.executable, "-m", "poisson_prove", *argv], cwd=base, env=env or _child_env(base), stdin=subprocess.DEVNULL,
        capture_output=True, timeout=timeout,
    )


def _refuse(word: str) -> Any:
    raise AssertionError(f"{word} in a strict JSON document")


def _document(raw: bytes, schema: str = "poisson-prove.sweep/1") -> dict[str, Any]:
    """The whole of ``raw`` as one strict JSON document, as rule 9 says it: nothing before it, nothing
    after it, UTF-8, no ``NaN``, ``schema``, ``verdict`` and ``sentence`` first."""
    text = raw.decode("utf-8")
    try:
        document = json.loads(text, parse_constant=_refuse)
    except json.JSONDecodeError as exc:
        pytest.fail(f"stdout is not one JSON document ({exc}): {text[:400]!r}")
    assert isinstance(document, dict), text[:200]
    assert list(document)[:3] == FIRST_KEYS, list(document)[:5]
    assert document["schema"] == schema, document["schema"]
    assert text.endswith("}\n"), repr(text[-20:])
    return document


def _err(done: subprocess.CompletedProcess[bytes]) -> str:
    return done.stderr.decode("utf-8", "replace")


def _report(done: subprocess.CompletedProcess[bytes]) -> str:
    return f"exit {done.returncode}\nstdout {done.stdout[:400]!r}\nstderr {done.stderr[-600:]!r}"


def _error_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("error: ")]


def _stored(base: Path) -> list[dict[str, Any]]:
    done = _prove(base, "runs", "--json")
    assert done.returncode == 0, _report(done)
    return _document(done.stdout, "poisson-prove.runs/1")["runs"]


# ---------- the issue's reproduction ----------


def test_the_issues_reproduction_parses(tmp_path: Path) -> None:
    """The issue's commands as it gives them, the pipe included: the console script, a print in the
    rollout, stderr dropped, stdout read by ``json.tool``. Today: ``Expecting value``."""
    (tmp_path / "noisy.py").write_text(
        "from poisson_prove.episode import Episode\n\n"
        "def rollout(cfg, seed):\n"
        '    print("framework banner")\n'
        '    return Episode(outcome="completed", t=1.0, horizon=1.0)\n',
        encoding="utf-8",
    )
    (tmp_path / "prove.toml").write_text(SPEC, encoding="utf-8")
    script = Path(sys.executable).with_name("poisson-prove")
    assert script.is_file(), script
    line = f"set -o pipefail; {script} sweep --json --yes --max-mde 1 2>/dev/null | {sys.executable} -m json.tool"
    done = subprocess.run(["bash", "-c", line], cwd=tmp_path, env=_child_env(tmp_path), stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
    assert done.returncode == 0, _report(done)
    assert b"Expecting value" not in done.stderr
    assert json.loads(done.stdout)["verdict"] == "done", _report(done)


# ---------- every way of writing, on both paths through the executor ----------


@pytest.mark.parametrize("path", list(PATHS))
@pytest.mark.parametrize("way", list(WAYS))
def test_stdout_is_one_document_and_the_text_is_on_stderr_once_a_write(way: str, path: str, tmp_path: Path) -> None:
    at_import, in_rollout, times = WAYS[way]
    _folder(tmp_path, _target(at_import, in_rollout))
    done = _prove(tmp_path, *SWEEP, *PATHS[path])
    assert done.returncode == 0, _report(done)
    document = _document(done.stdout)
    assert document["verdict"] == "done", document["sentence"]
    assert document["status"] == "complete", document
    assert BANNER.encode() not in done.stdout
    assert _err(done).count(BANNER) == times, _report(done)


@pytest.mark.parametrize(
    "write",
    [f'print("{BANNER}")', f'sys.stdout.write("{BANNER}")', f'sys.stdout.buffer.write(b"{BANNER}\\n")', f'sys.__stdout__.write("{BANNER}\\n")'],
    ids=["print", "no newline", "binary buffer", "interpreter's stdout"],
)
def test_text_in_a_timed_childs_buffer_is_not_lost_when_the_parent_ends_it(write: str, tmp_path: Path) -> None:
    """r1. The parent ends a timed child the moment it has the outcome. A thread the rollout left
    running keeps the child alive at that moment, so what it has not flushed by then is gone, every
    time: the race the other cases only sometimes lose."""
    leave = "threading.Thread(target=time.sleep, args=(30,)).start()"
    _folder(tmp_path, _target(in_rollout=f"{write}; {leave}"))
    done = _prove(tmp_path, *SWEEP, *TIMEOUT)
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert _err(done).count(BANNER) == ROLLOUTS, _report(done)


def test_binary_text_from_the_target_leaves_the_document_utf8(tmp_path: Path) -> None:
    _folder(tmp_path, _target(in_rollout=r'os.write(1, b"\xff\xfe framework banner\n")'))
    done = _prove(tmp_path, *SWEEP)
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert done.stderr.count(b"\xff\xfe framework banner\n") == ROLLOUTS, _report(done)


@pytest.mark.parametrize("path", list(PATHS))
def test_a_chatty_target_loses_no_text_and_no_document(path: str, tmp_path: Path) -> None:
    """More than a pipe holds, 200 kB a rollout, the size that hangs a reader of stdout alone, read
    here on both streams as ``subprocess.run(capture_output=True)`` reads them."""
    _folder(tmp_path, _target(in_rollout='print("x" * 200_000 + "framework banner")'))
    done = _prove(tmp_path, *SWEEP, *PATHS[path])
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert _err(done).count("x" * 200_000 + BANNER) == ROLLOUTS


@pytest.mark.parametrize("path", list(PATHS))
def test_the_chatty_sweeps_document_has_the_quiet_sweeps_facts(path: str, tmp_path: Path) -> None:
    """Writing changes nothing about what the document says."""
    documents = []
    for name, source in (("quiet", _target()), ("chatty", _target(f'print("{BANNER}")', f'os.write(1, b"{BANNER}\\n")'))):
        base = tmp_path / name
        base.mkdir()
        _folder(base, source)
        done = _prove(base, *SWEEP, "--salt", "0123456789abcdef", *PATHS[path])
        assert done.returncode == 0, _report(done)
        documents.append(_document(done.stdout))
    quiet, chatty = documents
    assert list(chatty) == list(quiet)
    for key in ("schema", "verdict", "status"):
        assert chatty[key] == quiet[key], key


@pytest.mark.parametrize("way_in", ["--pair-with", "--resume"])
def test_the_other_ways_into_a_sweep_keep_the_document(way_in: str, tmp_path: Path) -> None:
    _folder(tmp_path, _target())
    if way_in == "--pair-with":
        assert _prove(tmp_path, *SWEEP).returncode == 0
        more = ("--pair-with", "latest")
    else:
        stopped = _prove(tmp_path, *SWEEP, "--max-rollouts", "1")
        assert stopped.returncode == 3, _report(stopped)
        more = ("--resume", _stored(tmp_path)[0]["run_id"])
    _folder(tmp_path, _target(f'print("{BANNER}")', f'print("{BANNER}")'))
    done = _prove(tmp_path, *SWEEP, *more)
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert BANNER in _err(done)


def test_a_capture_sweep_keeps_the_document_and_an_instrumentors_text(tmp_path: Path) -> None:
    """A ``[capture]`` table runs an instrumentor's code in the sweep's process."""
    (tmp_path / "chatty_inst.py").write_text(
        "class Instrumentor:\n"
        "    def instrument(self):\n"
        '        print("instrumentor banner")\n',
        encoding="utf-8",
    )
    info = tmp_path / "chatty_inst-1.0.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: chatty-inst\nVersion: 1.0\n", encoding="utf-8")
    (info / "entry_points.txt").write_text("[opentelemetry_instrumentor]\nchatty = chatty_inst:Instrumentor\n", encoding="utf-8")
    _folder(tmp_path, _target(in_rollout=f'print("{BANNER}")'), SPEC + '\n[capture]\ninstrument = ["chatty"]\nmax_observation_bytes = 8192\n')
    done = _prove(tmp_path, *SWEEP)
    assert done.returncode == 0, _report(done)
    assert b"banner" not in done.stdout
    _document(done.stdout)
    assert _err(done).count(BANNER) == ROLLOUTS, _report(done)
    assert "instrumentor banner" in _err(done), _report(done)


def test_python_unbuffered_changes_nothing(tmp_path: Path) -> None:
    _folder(tmp_path, _target(f'print("{BANNER}")', f'print("{BANNER}")'))
    done = _prove(tmp_path, *SWEEP, env=_child_env(tmp_path, PYTHONUNBUFFERED="1"))
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert _err(done).count(BANNER) == ROLLOUTS + 1, _report(done)


# ---------- as it happens, not at exit ----------


def test_the_text_comes_before_the_last_progress_line(tmp_path: Path) -> None:
    _folder(tmp_path, _target(in_rollout=f'print("{BANNER}")'))
    done = _prove(tmp_path, *SWEEP)
    assert done.returncode == 0, _report(done)
    lines = _err(done).splitlines()
    last_progress = max(i for i, line in enumerate(lines) if line.endswith(f"{ROLLOUTS}/{ROLLOUTS}"))
    written = [i for i, line in enumerate(lines) if BANNER in line]
    assert len(written) == ROLLOUTS, lines
    assert written[0] < last_progress, lines


@pytest.mark.parametrize("path", list(PATHS))
@pytest.mark.parametrize(
    "write",
    [f'print("{BANNER}")', f'os.write(1, b"{BANNER}\\n")', f'subprocess.run(["sh", "-c", "echo {BANNER}"])'],
    ids=["print", "os.write", "child"],
)
def test_the_text_reaches_stderr_while_the_rollout_is_still_running(write: str, path: str, tmp_path: Path) -> None:
    """The rollout writes, then waits for a file only this test makes, and makes it only on seeing
    the text on stderr. A print held in a block buffer until exit never gets the file."""
    go, gave_up = tmp_path / "go", tmp_path / "gave-up"
    wait = f'deadline = time.time() + 15\n    while not os.path.exists({str(go)!r}):\n        if time.time() > deadline:\n            open({str(gave_up)!r}, "w").close()\n            break\n        time.sleep(0.02)'
    _folder(tmp_path, _target(in_rollout=f"{write}\n    {wait}"))
    proc = subprocess.Popen(
        [sys.executable, "-m", "poisson_prove", *SWEEP, *PATHS[path]], cwd=tmp_path, env=_child_env(tmp_path),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert proc.stderr is not None and proc.stdout is not None
    seen = b""
    deadline = time.monotonic() + 180
    drained: list[bytes] = []
    threading.Thread(target=lambda: drained.append(proc.stdout.read()), daemon=True).start()  # type: ignore[union-attr]
    try:
        while BANNER.encode() not in seen and time.monotonic() < deadline:
            ready, _, _ = select.select([proc.stderr], [], [], 0.5)
            if ready:
                chunk = os.read(proc.stderr.fileno(), 65536)
                if not chunk:
                    break
                seen += chunk
        go.touch()
        rest = proc.stderr.read()
        code = proc.wait(timeout=180)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert BANNER.encode() in seen, f"no text on stderr while the rollout waited: {seen[-300:]!r}, then {rest[-300:]!r}"
    assert not gave_up.exists(), "the text reached stderr only after the rollout gave up waiting"
    assert code == 0, (code, rest[-400:])


# ---------- the exit code still says what happened ----------


class Ending(NamedTuple):
    source: str
    argv: tuple[str, ...]
    code: int
    #: Whether stdout holds a document (a run that started) or nothing (nothing started).
    document: bool


_NOISY = f'print("{BANNER}")'
ENDINGS: dict[str, Ending] = {
    "done": Ending(_target(_NOISY, _NOISY), ("--yes", "--max-mde", "1"), 0, True),
    "every rollout raised": Ending(_target(_NOISY, f'{_NOISY}; raise ValueError("no")'), ("--yes", "--max-mde", "1"), 3, True),
    "stopped at --max-rollouts": Ending(_target(_NOISY, _NOISY), ("--yes", "--max-mde", "1", "--max-rollouts", "1"), 3, True),
    "no --yes and no terminal": Ending(_target(_NOISY), ("--max-mde", "1"), 1, False),
    "the power gate": Ending(_target(_NOISY), ("--yes",), 1, False),
    "the import raises ImportError": Ending(_target(f'{_NOISY}; raise ImportError("no")'), ("--yes", "--max-mde", "1"), 1, False),
    "the import raises anything else": Ending(_target(f'{_NOISY}; raise KeyError("no")'), ("--yes", "--max-mde", "1"), 3, False),
    "the name is not in the module": Ending(_target(_NOISY), ("--yes", "--max-mde", "1", "--target", "noisy:nothing"), 1, False),
}


@pytest.mark.parametrize("ending", list(ENDINGS))
def test_every_ending_keeps_its_exit_code_and_stdout_says_only_the_document(ending: str, tmp_path: Path) -> None:
    source, argv, code, has_document = ENDINGS[ending]
    _folder(tmp_path, source)
    done = _prove(tmp_path, "sweep", "--json", *argv)
    assert done.returncode == code, _report(done)
    assert BANNER in _err(done), _report(done)
    if has_document:
        _document(done.stdout)
    else:
        assert done.stdout == b"", _report(done)
        assert len(_error_lines(_err(done))) == 1, _report(done)


@pytest.mark.parametrize("ending", list(ENDINGS))
def test_the_exit_code_is_the_same_without_json(ending: str, tmp_path: Path) -> None:
    """Rule 9: the exit code is the same as without ``--json``. A guard for the fix as much as for
    the defect: what moves the streams must move no ending."""
    source, argv, code, _ = ENDINGS[ending]
    _folder(tmp_path, source)
    done = _prove(tmp_path, "sweep", *argv)
    assert done.returncode == code, _report(done)
    assert BANNER in done.stdout.decode(), _report(done)


@pytest.mark.parametrize("path", list(PATHS))
def test_ctrl_c_during_a_chatty_sweep_has_its_document_and_exits_130(path: str, tmp_path: Path) -> None:
    started = tmp_path / "started"
    _folder(tmp_path, _target(f'print("{BANNER}")', f'print("{BANNER}"); open({str(started)!r}, "w").close(); time.sleep(60)'))
    proc = subprocess.Popen(
        [sys.executable, "-m", "poisson_prove", *SWEEP, *PATHS[path]], cwd=tmp_path, env=_child_env(tmp_path),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        # A run started from a background shell inherits SIGINT ignored, and would never see this one.
        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),
    )
    deadline = time.monotonic() + 120
    while not started.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert started.exists()
    proc.send_signal(signal.SIGINT)
    out, err = proc.communicate(timeout=120)
    assert proc.returncode == 130, (proc.returncode, out[:300], err[-300:])
    assert _document(out)["verdict"] == "stopped"
    assert BANNER.encode() in err


#: A Ctrl-C that lands while the sweep starts the process of a timed rollout (prove#39, the nightly
#: of 2026-11-09). The target puts it there itself, so nothing here is timed: the first sends the
#: signal from an after-fork callback, where Python reports or drops what is raised and never raises
#: it; the second sends it once the child exists and before the start returns.
_SIGINT_ME = "os.kill(os.getpid(), signal.SIGINT)"
STARTS = {
    "inside the fork": f"import signal; os.register_at_fork(after_in_parent=lambda: {_SIGINT_ME})",
    "after the fork, before the start returns": (
        "import signal, multiprocessing.context as _mpc; _start = _mpc.ForkProcess.start; "
        f"_mpc.ForkProcess.start = lambda self: (_start(self), {_SIGINT_ME})[0]"
    ),
}
CAPTURE = "\n[capture]\nmax_observation_bytes = 16384\n"


def _interrupted_while_starting(base: Path, start: str, spec: str = SPEC) -> tuple[int, bytes, bytes]:
    """A sweep whose every rollout would hold for ten minutes, interrupted by its own target as
    ``start`` says. A sweep that lost the interrupt, or left the rollout's process running, is
    still there after two minutes and is killed."""
    _folder(base, _target(start, "time.sleep(600)"), spec)
    proc = subprocess.Popen(
        [sys.executable, "-m", "poisson_prove", *SWEEP, "--episode-timeout", "600"], cwd=base, env=_child_env(base),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL),
    )
    try:
        out, err = proc.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        pytest.fail(f"the sweep did not stop for the interrupt: stdout {out[:300]!r}\nstderr {err[-600:]!r}")
    return proc.returncode, out, err


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="the rollout's process is forked only where fork exists")
@pytest.mark.parametrize("start", list(STARTS))
def test_ctrl_c_while_a_rollouts_process_starts_stops_the_sweep_and_exits_130(start: str, tmp_path: Path) -> None:
    code, out, err = _interrupted_while_starting(tmp_path, STARTS[start])
    assert code == 130, (code, out[:300], err[-600:])
    assert _document(out)["verdict"] == "stopped"
    assert b"Exception ignored" not in err and b"Traceback" not in err, err[-600:]
    (run,) = _stored(tmp_path)
    assert run["status"] != "complete", run


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="the capture probe is forked only where fork exists")
def test_ctrl_c_while_the_capture_probe_starts_stops_the_sweep_before_a_run_exists(tmp_path: Path) -> None:
    """With ``[capture]`` and a timeout the first process the sweep starts is the capture probe,
    before the run is created: an interrupt taken in that fork ends the sweep there, with no store
    made."""
    code, out, err = _interrupted_while_starting(tmp_path, STARTS["inside the fork"], SPEC + CAPTURE)
    assert code == 130, (code, out[:300], err[-600:])
    assert _document(out)["verdict"] == "stopped"
    assert b"Exception ignored" not in err and b"Traceback" not in err, err[-600:]
    assert not (tmp_path / "prove-runs").exists(), "the sweep went on to create its run"


@pytest.mark.parametrize(
    ("at_import", "in_rollout"),
    [("sys.exit(0)", "pass"), ("sys.exit(7)", "pass"), ("", "sys.exit(0)"), ("", "sys.exit(7)")],
    ids=["import-0", "import-7", "rollout-0", "rollout-7"],
)
def test_sys_exit_from_the_target_does_not_end_with_success_and_no_document(at_import: str, in_rollout: str, tmp_path: Path) -> None:
    """r9. Today exit 0 and an empty stdout, or a code the look's table does not have. Either the run
    is a document that says so (the row errored, exit 3), or stdout is empty with an ``error: `` line."""
    _folder(tmp_path, _target(at_import, in_rollout))
    done = _prove(tmp_path, *SWEEP)
    assert done.returncode in (1, 3), _report(done)
    if done.stdout:
        _document(done.stdout)
    else:
        assert len(_error_lines(_err(done))) == 1, _report(done)


# ---------- a target that closes or replaces its stdout ----------


@pytest.mark.parametrize(
    "at_import",
    ["sys.stdout.close()", "os.close(1)"],
    ids=["sys.stdout.close", "os.close"],
)
def test_a_target_that_closes_its_stdout_still_leaves_one_document(at_import: str, tmp_path: Path) -> None:
    """r10. Today exit 1 or 120 with a traceback and no document."""
    _folder(tmp_path, _target(at_import))
    done = _prove(tmp_path, *SWEEP)
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert b"Traceback" not in done.stderr, _report(done)
    assert _err(done).strip().endswith(f"{ROLLOUTS}/{ROLLOUTS}"), "stderr still works after the target closed its stdout: " + _report(done)


def test_a_target_that_replaces_sys_stdout_leaves_the_document_alone(tmp_path: Path) -> None:
    """A guard: the document's stream is Prove's own, not whatever ``sys.stdout`` is by then."""
    _folder(tmp_path, _target("import io; sys.stdout = io.StringIO()"))
    done = _prove(tmp_path, *SWEEP)
    assert done.returncode == 0, _report(done)
    _document(done.stdout)


# ---------- children that outlive the sweep ----------


def test_a_child_that_outlives_the_sweep_cannot_reach_the_document_later(tmp_path: Path) -> None:
    """The reader sees the document and nothing after it, even from a child that writes once the
    sweep has gone. The child keeps its own stdout, so this test reads until it has finished."""
    wrote = tmp_path / "late-wrote"
    late = f'sleep 1; echo {BANNER}; touch {wrote}'
    _folder(tmp_path, _target(f'subprocess.Popen(["sh", "-c", {late!r}])'))
    done = _prove(tmp_path, *SWEEP)
    deadline = time.monotonic() + 30
    while not wrote.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert wrote.exists()
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert BANNER in _err(done), _report(done)


@pytest.mark.parametrize(
    "start",
    [
        'open({pid!r}, "w").write(str(subprocess.Popen(["sleep", "60"]).pid))',
        # Through a shell, which passes on every inheritable descriptor; its own stdout is elsewhere,
        # so only a copy of the pipe that was left inheritable could hold stdout open.
        'os.system("sleep 60 > /dev/null 2>&1 & echo $! > {pid}")',
    ],
    ids=["inherits stdout", "inherits only what is inheritable"],
)
def test_a_background_child_does_not_hold_stdout_open(start: str, tmp_path: Path) -> None:
    """Stdout reaches its end when the sweep exits, though a child the target left running holds its
    own stdout: the document's copy of the pipe is not inherited, so a caller reading to the end of
    stdout does not wait for that child. Stderr is a file here because the child keeps that open."""
    pid_file = tmp_path / "child.pid"
    _folder(tmp_path, _target(start.format(pid=str(pid_file))))
    with (tmp_path / "stderr.txt").open("wb") as err:
        proc = subprocess.Popen(
            [sys.executable, "-m", "poisson_prove", *SWEEP], cwd=tmp_path, env=_child_env(tmp_path),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=err,
        )
    assert proc.stdout is not None
    out = b""
    ended = False
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([proc.stdout], [], [], 0.5)
            if ready:
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    ended = True
                    break
                out += chunk
        assert ended, f"stdout was still open 30 s on, with the sweep's exit code {proc.poll()}: {out[:200]!r}"
        assert proc.wait(timeout=30) == 0
        _document(out)
    finally:
        if proc.poll() is None:
            proc.kill()
        with contextlib.suppress(FileNotFoundError, ProcessLookupError, ValueError):
            os.kill(int(pid_file.read_text().strip()), signal.SIGKILL)


# ---------- terminals ----------


def _on_a_pty(base: Path, argv: Sequence[str], *, pty_is: str) -> tuple[int, bytes, bytes]:
    """``argv`` with stdout or stderr a terminal and the other a pipe. Returns the code, stdout and
    stderr; the terminal's bytes have every carriage return taken out, since a terminal adds them and
    macOS adds an extra one at its queue's edge."""
    master, slave = pty.openpty()
    streams = {"stdout": slave, "stderr": subprocess.PIPE} if pty_is == "stdout" else {"stdout": subprocess.PIPE, "stderr": slave}
    proc = subprocess.Popen([sys.executable, "-m", "poisson_prove", *argv], cwd=base, env=_child_env(base), stdin=subprocess.DEVNULL, **streams)
    os.close(slave)
    piped = proc.stderr if pty_is == "stdout" else proc.stdout
    assert piped is not None
    got: dict[str, bytes] = {"pipe": b""}
    reader = threading.Thread(target=lambda: got.update(pipe=piped.read()), daemon=True)
    reader.start()
    screen = b""
    deadline = time.monotonic() + 180
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.5)
            if ready:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                screen += chunk
            elif proc.poll() is not None:
                break
        code = proc.wait(timeout=60)
        reader.join(timeout=60)
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(master)
    screen = screen.replace(b"\r", b"")
    return (code, screen, got["pipe"]) if pty_is == "stdout" else (code, got["pipe"], screen)


def test_with_stdout_a_terminal_it_holds_one_document_and_nothing_else(tmp_path: Path) -> None:
    _folder(tmp_path, _target(f'print("{BANNER}")', f'print("{BANNER}")'))
    code, out, err = _on_a_pty(tmp_path, SWEEP, pty_is="stdout")
    assert code == 0, (out[:300], err[-300:])
    _document(out)
    assert err.decode().count(BANNER) == ROLLOUTS + 1


def test_with_stderr_a_terminal_stdout_holds_one_document(tmp_path: Path) -> None:
    _folder(tmp_path, _target(f'print("{BANNER}")', f'print("{BANNER}")'))
    code, out, err = _on_a_pty(tmp_path, SWEEP, pty_is="stderr")
    assert code == 0, (out[:300], err[-300:])
    _document(out)
    assert err.decode().count(BANNER) == ROLLOUTS + 1


# ---------- the document's bytes: encodings and a reader that has gone ----------


@pytest.mark.parametrize(("encoding", "plain"), [("ascii", True), ("utf-8", False)], ids=["ascii", "utf-8"])
def test_the_documents_encoding_follows_stdouts_as_it_does_today(encoding: str, plain: bool, tmp_path: Path) -> None:
    """A guard: the document's own stream keeps the encoding the real stdout had, so an ASCII stdout
    still gets escapes and a UTF-8 one the characters."""
    _folder(tmp_path, _target(in_rollout=f'print("{BANNER}")'))
    done = _prove(tmp_path, *SWEEP, "--name", "café run", env=_child_env(tmp_path, PYTHONIOENCODING=encoding))
    assert done.returncode == 0, _report(done)
    assert done.stdout.isascii() is plain, done.stdout[:400]
    assert _document(done.stdout)["run_name"] == "café run"


@pytest.mark.parametrize(
    "in_rollout", ["pass", f'print("{BANNER}", flush=True)', f'os.write(1, b"{BANNER}\\n")'], ids=["quiet", "print", "os.write"]
)
def test_a_reader_that_has_gone_is_not_an_error_and_the_run_is_whole(in_rollout: str, tmp_path: Path) -> None:
    """The look's closed pipe: nothing to say, exit 0, and no line about it on stderr. The target is
    not hurt by it either: every rollout is stored as it finished."""
    _folder(tmp_path, _target(in_rollout=in_rollout))
    read, write = os.pipe()
    os.close(read)
    try:
        done = subprocess.run(
            [sys.executable, "-m", "poisson_prove", *SWEEP], cwd=tmp_path, env=_child_env(tmp_path),
            stdin=subprocess.DEVNULL, stdout=write, stderr=subprocess.PIPE, timeout=300,
        )
    finally:
        os.close(write)
    assert done.returncode == 0, (done.returncode, done.stderr[-600:])
    for word in (b"Traceback", b"BrokenPipe", b"Exception ignored"):
        assert word not in done.stderr, done.stderr[-600:]
    (run,) = _stored(tmp_path)
    assert (run["rows"], run["no_outcome"]) == (ROLLOUTS, 0), run


# ---------- --dry-run, which is already clean ----------


@pytest.mark.parametrize("way", [*IMPORT_WAYS, "print from atexit"])
def test_dry_run_keeps_one_document(way: str, tmp_path: Path) -> None:
    """A guard. The check imports the target in a process of its own with stdout discarded, so what
    it writes there is not shown, with or without ``--json``. That stays."""
    _folder(tmp_path, _target(WAYS[way].at_import))
    done = _prove(tmp_path, "sweep", "--json", "--dry-run", "--max-mde", "1")
    assert done.returncode == 0, _report(done)
    assert _document(done.stdout)["verdict"] == "plan"
    assert BANNER.encode() not in done.stdout


# ---------- every other verb ----------


def _browser(base: Path, text: str = "browser banner") -> str:
    path = base / "browser.sh"
    path.write_text(f'#!/bin/sh\necho "{text}"\n', encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return f"{path} %s"


def _paired_declaration(base: Path) -> tuple[Path, Path]:
    from test_defaults_refusals_and_faces import _declaration, _paired_store

    root = _paired_store(base / "paired-store", ("0.30", "0.30"))
    return root, _declaration(base / "replay.toml", "grade-a-run", "grade-b-run")


VERBS: dict[str, tuple[tuple[str, ...], int, str]] = {
    "diff": (("diff", "previous", "latest", "--json"), 0, "diff"),
    "diff --save": (("diff", "previous", "latest", "--save", "--json"), 0, "diff"),
    "check passed": (("check", "previous", "latest", "--event", "violated", "--fail-on", "higher", "--json"), 0, "check"),
    "report": (("report", "previous", "latest", "--x", "tool_fail_rate", "--y", "task_id", "--event", "violated", "--json", "--out", "out-pair"), 0, "report"),
    "report of one run": (("report", "latest", "--x", "tool_fail_rate", "--y", "task_id", "--event", "violated", "--json", "--out", "out-run"), 0, "report"),
    "serve": (("serve", "previous", "latest", "--x", "tool_fail_rate", "--y", "task_id", "--event", "violated", "--json"), 0, "viewpair"),
    "inspect": (("inspect", "latest", "--event", "violated", "--limit", "2", "--json"), 0, "inspect"),
    "runs": (("runs", "--json"), 0, "runs"),
    "ui": (("ui", "--json"), 0, "ui"),
    "init": (("init", "--json", "--example", "--out", "fresh.toml"), 0, "init"),
    "init --agent": (("init", "--agent", "--json"), 0, "init"),
}


def _schema(name: str) -> str:
    return "poisson-prove.viewpair/7" if name == "viewpair" else f"poisson-prove.{name}/1"


@pytest.mark.parametrize("verb", list(VERBS))
def test_every_verb_writes_one_document_in_a_real_process(verb: str, tmp_path: Path, reading_world: dict[str, Path]) -> None:  # noqa: F811
    argv, code, schema = VERBS[verb]
    store = copy_store(reading_world["kinds"], tmp_path / "prove-runs")
    (tmp_path / "repo").mkdir()
    cwd = tmp_path / "repo" if verb == "init --agent" else tmp_path
    done = _prove(cwd, "--store", str(store), *argv, env=_child_env(tmp_path))
    assert done.returncode == code, _report(done)
    _document(done.stdout, _schema(schema))


def test_paired_writes_one_document_in_a_real_process(tmp_path: Path) -> None:
    store, declaration = _paired_declaration(tmp_path)
    done = _prove(tmp_path, "--store", str(store), "paired", "--declaration", str(declaration), "--json")
    assert done.returncode == 0, _report(done)
    _document(done.stdout, "poisson-prove.paired/1")


def test_a_refused_verb_leaves_stdout_empty_with_an_error_line(tmp_path: Path, reading_world: dict[str, Path]) -> None:  # noqa: F811
    store = copy_store(reading_world["kinds"], tmp_path / "prove-runs")
    done = _prove(tmp_path, "--store", str(store), "diff", "no-such-run", "latest", "--json")
    assert done.returncode == 1, _report(done)
    assert done.stdout == b"", _report(done)
    assert len(_error_lines(_err(done))) == 1, _report(done)


def test_ui_open_keeps_the_document_when_the_browser_writes_to_stdout(tmp_path: Path, reading_world: dict[str, Path]) -> None:  # noqa: F811
    """``ui --open`` is the one verb besides ``sweep`` that starts a program, and it inherits stdout."""
    store = copy_store(reading_world["kinds"], tmp_path / "prove-runs")
    done = _prove(tmp_path, "--store", str(store), "ui", "--open", "--json", env=_child_env(tmp_path, BROWSER=_browser(tmp_path)))
    assert done.returncode == 0, _report(done)
    _document(done.stdout, _schema("ui"))
    assert "browser banner" in _err(done), _report(done)


def test_ui_open_without_json_leaves_the_browsers_text_on_stdout(tmp_path: Path, reading_world: dict[str, Path]) -> None:  # noqa: F811
    store = copy_store(reading_world["kinds"], tmp_path / "prove-runs")
    done = _prove(tmp_path, "--store", str(store), "ui", "--open", env=_child_env(tmp_path, BROWSER=_browser(tmp_path)))
    assert done.returncode == 0, _report(done)
    assert b"browser banner" in done.stdout, _report(done)
    assert b"browser banner" not in done.stderr, _report(done)


# ---------- without --json, nothing moves ----------


@pytest.mark.parametrize("path", list(PATHS))
@pytest.mark.parametrize("way", list(WAYS))
def test_without_json_the_text_stays_on_stdout(way: str, path: str, tmp_path: Path) -> None:
    at_import, in_rollout, times = WAYS[way]
    _folder(tmp_path, _target(at_import, in_rollout))
    done = _prove(tmp_path, "sweep", "--yes", "--max-mde", "1", *PATHS[path])
    assert done.returncode == 0, _report(done)
    found = done.stdout.decode().count(BANNER)
    if path == "under --episode-timeout" and way in HELD_IN_THE_CHILDS_BUFFER:
        # Today the parent ends a timed child the moment it has the outcome, so text still in the
        # child's buffer can be lost, one rollout in some runs. Not pinned either way without --json.
        assert found <= times, _report(done)
    else:
        assert found == times, _report(done)
    assert BANNER not in _err(done), _report(done)
    assert 'done  2 rollouts in run' in done.stdout.decode(), _report(done)


def test_without_json_a_print_at_import_comes_first_and_an_atexit_print_comes_last(tmp_path: Path) -> None:
    _folder(tmp_path, _target(f'print("{BANNER} first"); atexit.register(lambda: print("{BANNER} last"))'))
    done = _prove(tmp_path, "sweep", "--yes", "--max-mde", "1")
    assert done.returncode == 0, _report(done)
    lines = done.stdout.decode().splitlines()
    assert lines[0] == f"{BANNER} first", lines
    assert lines[-1] == f"{BANNER} last", lines


def test_without_json_the_target_finds_its_stdout_as_it_was(tmp_path: Path) -> None:
    """Fd 1 is the pipe the caller gave and ``sys.stdout`` the interpreter's, both from the import on."""
    facts = tmp_path / "facts.json"
    _folder(tmp_path, _target(
        "import json\n"
        f"json.dump({{'one_is_two': os.fstat(1).st_ino == os.fstat(2).st_ino, 'same': sys.stdout is sys.__stdout__, 'fd': sys.stdout.fileno()}}, open({str(facts)!r}, 'w'))"
    ))
    done = _prove(tmp_path, "sweep", "--yes", "--max-mde", "1")
    assert done.returncode == 0, _report(done)
    assert json.loads(facts.read_text()) == {"one_is_two": False, "same": True, "fd": 1}


# ---------- main(stdout=...) ----------

_DRIVER = """\
import contextlib, io, json, os, sys
from poisson_prove.cli import main

before = os.fstat(1).st_ino
stream = sys.stdout
out, err = io.StringIO(), io.StringIO()
mode = sys.argv[1]
argv = ["sweep", "--json", "--yes", "--max-mde", "1"]
if mode == "given":
    code = main(argv, stdout=out, stderr=err, stdin=io.StringIO())
else:
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, stdin=io.StringIO())
print("driver after")
sys.stdout.flush()
os.write(2, json.dumps({
    "code": code, "document": out.getvalue(), "err": err.getvalue(),
    "same_fd": os.fstat(1).st_ino == before, "same_stream": sys.stdout is stream,
}).encode())
"""


@pytest.mark.parametrize("mode", ["given", "redirected"])
def test_in_process_the_document_goes_where_the_caller_said_and_its_stdout_stays(mode: str, tmp_path: Path) -> None:
    """r5. The target's print stays on the caller's stdout, the document goes to the stream the caller
    gave or to its redirect, and the process's stdout is left as it was found."""
    _folder(tmp_path, _target(in_rollout=f'os.write(1, b"{BANNER}\\n")'))
    (tmp_path / "driver.py").write_text(_DRIVER, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "driver.py", mode], cwd=tmp_path, env=_child_env(tmp_path), stdin=subprocess.DEVNULL, capture_output=True, timeout=300,
    )
    assert done.returncode == 0, _report(done)
    facts = json.loads(done.stderr[done.stderr.rindex(b'{"code"'):])
    assert facts["code"] == 0, facts
    assert facts["same_fd"] is True and facts["same_stream"] is True, facts
    _document(facts["document"].encode())
    assert done.stdout.decode() == f"{BANNER}\n" * ROLLOUTS + "driver after\n", _report(done)


# ---------- the Modal backend, on a fake client ----------

MODAL_SPEC = SPEC + """
[modal]
concurrency = 1
batch_size = 1

[modal.image]
python = "3.11"
"""

_FAKE_MODAL = """\
\"\"\"A fake of Modal's client. What it writes stands for anything the real client may write in the
sweep's process; the batches run in a child standing for the container, whose stdout is not ours.\"\"\"
import contextlib, os, pickle, subprocess, sys, tempfile, types

{client_write}

_CONTAINER = (
    "import os, pickle, sys\\n"
    "from poisson_prove.executor_modal import _container_batch\\n"
    "item, out = pickle.load(sys.stdin.buffer)\\n"
    "with open(out, 'wb') as fh:\\n"
    "    pickle.dump(_container_batch(item), fh)\\n"
)


class _Image:
    def __getattr__(self, name):
        return lambda *args, **kwargs: self


class _Function:
    def __init__(self, fn):
        self.fn = fn

    def map(self, items, **kwargs):
        {client_write}
        for item in items:
            with tempfile.TemporaryDirectory() as scratch:
                out = os.path.join(scratch, "out.pickle")
                subprocess.run([sys.executable, "-c", _CONTAINER], input=pickle.dumps((item, out)), check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with open(out, "rb") as fh:
                    yield pickle.load(fh)


class App:
    def __init__(self, name, *args, **kwargs):
        pass

    def function(self, **kwargs):
        return _Function

    @contextlib.contextmanager
    def run(self):
        {client_write}
        yield self


Image = types.SimpleNamespace(debian_slim=lambda *a, **k: _Image(), from_dockerfile=lambda *a, **k: _Image())
Secret = types.SimpleNamespace(from_name=lambda *a, **k: object())
"""


def _fake_modal(base: Path, client_write: str = "pass") -> None:
    package = base / "modal"
    package.mkdir()
    (package / "__init__.py").write_text(_FAKE_MODAL.format(client_write=client_write), encoding="utf-8")


def test_modal_a_targets_writes_stay_in_the_container(tmp_path: Path) -> None:
    """A guard, and the finding for Modal: the target's writes, at import, in the rollout, and from
    ``atexit``, happen in the container and never reach the sweep's stdout. Green on main."""
    pids = tmp_path / "pids.txt"
    at_import = f'print("{BANNER}", flush=True); atexit.register(lambda: print("{BANNER}")); open({str(pids)!r}, "a").write(f"{{os.getpid()}}\\n")'
    _folder(tmp_path, _target(at_import, f'os.write(1, b"{BANNER}\\n")'), MODAL_SPEC)
    _fake_modal(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-m", "poisson_prove", *SWEEP, "--backend", "modal"], cwd=tmp_path, env=_child_env(tmp_path),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    out, err = proc.communicate(timeout=300)
    assert proc.returncode == 0, (proc.returncode, out[:300], err[-500:])
    _document(out)
    imported_in = {int(line) for line in pids.read_text().splitlines()}
    assert imported_in and proc.pid not in imported_in, "the target was imported in the sweep's process"


@pytest.mark.parametrize(
    "client_write",
    [f'print("{BANNER}")', f'os.write(1, b"{BANNER}\\n")', f'subprocess.run(["sh", "-c", "echo {BANNER}"])'],
    ids=["print", "os.write", "child"],
)
def test_modal_what_the_client_writes_goes_to_stderr(client_write: str, tmp_path: Path) -> None:
    """The fake's client writes at its import, as the app runs, and as the map starts: three times."""
    _folder(tmp_path, _target(), MODAL_SPEC)
    _fake_modal(tmp_path, client_write)
    done = _prove(tmp_path, *SWEEP, "--backend", "modal")
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert _err(done).count(BANNER) == 3, _report(done)


# ---------- the cloud backend, on the fake of its client ----------

_CLOUD_MAIN = """\
import sys
import poisson_prove.executor_cloud as ec
for name, argv in {seams!r}.items():
    setattr(ec, name, lambda argv=argv: list(argv))
from poisson_prove.cli import main
sys.exit(main())
"""


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def cloud_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    """Since 0.3.0 a cloud sweep starts and stops its cluster: the fake coordinator, the fake CLI,
    the fake AWS CLI on ``PATH`` and the ownership record, in the test's own folder."""
    with world(tmp_path, monkeypatch, pool) as made:
        yield made


class Cloud(NamedTuple):
    base: Path
    fake: Fake
    spec: Path

    def run(self, *more: str, json_flag: bool = True) -> subprocess.CompletedProcess[bytes]:
        flag = ("--json",) if json_flag else ()
        findable = self.base / "findable"
        env = _child_env(self.base)
        env["PYTHONPATH"] = os.pathsep.join([str(SRC), str(self.base), str(findable)])
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        return subprocess.run(
            [sys.executable, str(self.base / "main.py"), "--store", str(self.base / "store"), "sweep", str(self.spec),
             "--target", "noisy_bu.target:rollout", "--backend", "cloud", "--salt", "0123456789abcdef", "--max-mde", "1", "--yes", *flag, *more],
            cwd=self.base, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=600,
        )


def _cloud(w: CloudWorld, source: str, *, capture: bool = False) -> Cloud:
    """A real process of the command line, with its three seams pointed at the fake (the job's
    launcher as the cloud backend's own tests point it, the coordinator and the CLI as the world's).
    The target is a package of its own, which the bundle carries to the workers."""
    base = w.root
    package = base / "noisy_bu"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "target.py").write_text(source, encoding="utf-8")
    findable = base / "findable"
    (findable / "burla").mkdir(parents=True)
    (findable / "burla" / "__init__.py").write_text("", encoding="utf-8")
    (findable / f"burla-{PIN}.dist-info").mkdir()
    (findable / f"burla-{PIN}.dist-info" / "METADATA").write_text(f"Metadata-Version: 2.1\nName: burla\nVersion: {PIN}\n", encoding="utf-8")
    fake = Fake(base / "fake-state", w.pool)
    spec = write_sweep(base, capture=capture, cloud=cloud_fields(packages=["noisy_bu"], ledger=str(base / "ledger.jsonl")))
    seams = {**w.seams(), "_launcher_argv": [sys.executable, "-I", str(LAUNCH), str(fake.state), "fake", str(SUBMIT)]}
    (base / "main.py").write_text(_CLOUD_MAIN.format(seams=seams), encoding="utf-8")
    return Cloud(base, fake, spec)


#: ``write_sweep``'s two cells at two replicates.
CLOUD_ROWS = 4


def _cloud_stored(base: Path) -> dict[str, Any]:
    done = _prove(base, "--store", str(base / "store"), "runs", "--json")
    assert done.returncode == 0, _report(done)
    (run,) = _document(done.stdout, "poisson-prove.runs/1")["runs"]
    return run


@pytest.mark.parametrize(
    ("at_import", "where"),
    [(f'print("{BANNER}")', "print at import"), (f'atexit.register(lambda: print("{BANNER}"))', "print from atexit")],
    ids=["import", "atexit"],
)
def test_cloud_what_the_sweeps_own_process_writes_goes_to_stderr(at_import: str, where: str, cloud_world: CloudWorld) -> None:
    """The target is imported in the sweep's process to plan the run, so these break the document as
    they do locally (r7). Exit 0 and an unparseable stdout on main."""
    cloud = _cloud(cloud_world, _target(at_import))
    done = cloud.run()
    assert done.returncode == 0, (where, _report(done))
    _document(done.stdout)
    assert BANNER in _err(done), _report(done)


def test_cloud_the_launchers_output_stays_in_its_log(cloud_world: CloudWorld) -> None:
    """A guard, and part of the finding: the launcher's stdout and stderr are its log, so what the
    client prints never reaches the document. Green on main."""
    cloud = _cloud(cloud_world, _target())
    cloud.fake.script(default={"print": BANNER})
    done = cloud.run()
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert BANNER not in _err(done), _report(done)
    logs = [path.read_text(encoding="utf-8", errors="replace") for path in cloud_world.root.rglob("*.log")]
    assert any(BANNER in text for text in logs), "the launcher's output is not in its log"


def test_cloud_a_rollouts_unflushed_print_stays_off_the_document(cloud_world: CloudWorld) -> None:
    """A guard: green on main, by luck (r8). The pickle overtakes the text still in its buffer."""
    cloud = _cloud(cloud_world, _target(in_rollout=f'print("{BANNER}")'))
    done = cloud.run()
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    assert (_cloud_stored(cloud_world.root)["rows"], _cloud_stored(cloud_world.root)["no_outcome"]) == (CLOUD_ROWS, 0)


_THROUGH_FD_1 = {
    "flushed print": f'print("{BANNER}", flush=True)',
    "os.write": f'os.write(1, b"{BANNER}\\n")',
    "a child": f'subprocess.run(["sh", "-c", "echo {BANNER}"])',
}


@pytest.mark.parametrize("write", list(_THROUGH_FD_1))
def test_cloud_rollout_writing_through_fd_1_does_not_fail_the_sweep(write: str, cloud_world: CloudWorld) -> None:
    """r8. The rehearsal reads a pickle from the child's stdout, so on main this ends in exit 3 and an
    ``UnpicklingError`` in the errors log, for a target that does nothing wrong."""
    cloud = _cloud(cloud_world, _target(in_rollout=_THROUGH_FD_1[write]))
    done = cloud.run()
    assert done.returncode == 0, _report(done)
    assert _document(done.stdout)["status"] == "complete"
    run = _cloud_stored(cloud_world.root)
    assert (run["rows"], run["no_outcome"]) == (CLOUD_ROWS, 0), run


def test_cloud_rollout_print_under_a_timeout_does_not_fail_the_sweep(cloud_world: CloudWorld) -> None:
    """r8. A timed rollout's forked child flushes as it ends, so a plain print is enough here."""
    cloud = _cloud(cloud_world, _target(in_rollout=f'print("{BANNER}")'))
    done = cloud.run(*TIMEOUT)
    assert done.returncode == 0, _report(done)
    _document(done.stdout)
    run = _cloud_stored(cloud_world.root)
    assert (run["rows"], run["no_outcome"]) == (CLOUD_ROWS, 0), run


def test_cloud_rollout_writing_under_capture_keeps_its_rows(cloud_world: CloudWorld) -> None:
    """r8, the other reader of a child's stdout: a batch with ``[capture]`` or ``[chaos]`` runs in an
    interpreter spawned for it, and its pickle comes back the same way."""
    cloud = _cloud(cloud_world, _target(in_rollout=f'os.write(1, b"{BANNER}\\n")'), capture=True)
    done = cloud.run()
    assert done.returncode == 0, _report(done)
    assert _document(done.stdout)["status"] == "complete"
    run = _cloud_stored(cloud_world.root)
    assert (run["rows"], run["no_outcome"]) == (CLOUD_ROWS, 0), run


def test_cloud_rollout_writing_through_fd_1_runs_without_json_too(cloud_world: CloudWorld) -> None:
    """r8 is not about the document, so it holds without ``--json`` as well. This is the one change
    in this file that a person without ``--json`` sees: a sweep that failed now runs."""
    cloud = _cloud(cloud_world, _target(in_rollout=f'os.write(1, b"{BANNER}\\n")'))
    done = cloud.run(json_flag=False)
    assert done.returncode == 0, _report(done)
    run = _cloud_stored(cloud_world.root)
    assert (run["rows"], run["no_outcome"]) == (CLOUD_ROWS, 0), run
