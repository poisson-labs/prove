"""Remote backends, C7: Ctrl-C with a closed output pipe (#12), invariants K1 to K5 and the half of K7
that ruling RB-34 keeps (local and Modal sweeps keep Python's default for SIGTERM and SIGHUP).

``poisson-prove sweep … | head`` and Ctrl-C: the terminal signals the whole foreground group, so
``head`` exits and Prove's stdout is a pipe nobody reads. The rule: an interrupt wins over a closed
pipe, so an interrupted verb exits 130 whatever the state of stdout and stderr; the run's event log
ends with ``interrupted`` before anything is written to either stream; nothing more goes to a closed
stdout; no traceback and no ``Exception ignored`` line. A closed pipe with no interrupt still exits 0
quietly.

**How it is reached.** Every case is a real process with real pipes: ``python -m poisson_prove`` with
stdout (and in some cases stderr) on a pipe this test holds the reading end of. The test reads what
the command writes, as ``head`` would, until the command is mid-run, then closes its end, as
``head`` does when it exits, and only then sends SIGINT to the process. "Mid-run" is made exact, not
timed: the target writes a marker file and then sleeps (or writes past the pipe's capacity), so no
progress line can land between the close and the signal. ``ui --open`` is held mid-run by a
``BROWSER`` command that writes its marker and sleeps.

K6 and the cluster half of K7 (the cluster stop on SIGINT, SIGTERM and SIGHUP, with stdout closed
or not) need the cloud backend's own fake and are held with the cluster's life, not here.
"""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from poisson_prove import cli

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
MOCK = "poisson_prove.examples.mock_agent"
INTERRUPTED = 130
WAIT_S = 120.0

SPEC = """target_id = "rb-interrupt@v0"
t_unit = "steps"
replicates = 50

[axes.cell]
type = "categorical"
values = ["a", "b"]
"""
MODAL_TABLE = '\n[modal]\nconcurrency = 1\nbatch_size = 4\n\n[modal.image]\npython = "3.11"\n'

#: The target: its first ``FAST`` rollouts return at once; the next writes the marker and then holds
#: (``HOLD``: sleeps; ``FLOOD``: writes 4 MB to stdout, more than any pipe holds). Rollouts are counted
#: in a file, since a backend may run each batch in a process of its own.
TARGET = """\
import os, sys, time
from poisson_prove.episode import Episode

MARKER = {marker!r}
COUNT = {count!r}
FAST = 12


def rollout(cfg, seed):
    with open(COUNT, "a") as fh:
        fh.write(".")
    with open(COUNT) as fh:
        n = len(fh.read())
    if n > FAST:
        with open(MARKER, "a") as fh:
            fh.write(f"{{os.getpid()}}\\n")
        {hold}
    return Episode(outcome="survived", t=1.0, horizon=1.0)
"""
HOLD = "time.sleep(600)"
FLOOD = 'sys.stdout.write("x" * 4_000_000); sys.stdout.flush()'

#: A fake of Modal's client, a package on the child's path: ``map`` runs Prove's container function
#: on each item in this process, in order.
FAKE_MODAL = '''\
import contextlib, types


class _Image:
    def __getattr__(self, name):
        return lambda *args, **kwargs: self


class _Function:
    def __init__(self, fn):
        self.fn = fn

    def map(self, items, **kwargs):
        for item in items:
            yield self.fn(item)


class App:
    def __init__(self, *args, **kwargs):
        pass

    def function(self, **kwargs):
        return _Function

    @contextlib.contextmanager
    def run(self):
        yield self


Image = types.SimpleNamespace(debian_slim=lambda *a, **k: _Image(), from_dockerfile=lambda *a, **k: _Image())
Secret = types.SimpleNamespace(from_name=lambda *a, **k: object())
'''

BROWSER = """\
#!/bin/sh
echo $$ >> {marker}
exec sleep 600
"""


# ---------- the world, the child and its pipes ----------


def child_env(base: Path, **more: str) -> dict[str, str]:
    drop = ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "PYTHONWARNINGS", "CI", "BROWSER", "PYTHONUNBUFFERED")
    env = {key: value for key, value in os.environ.items() if key not in drop}
    home = base / "home"
    home.mkdir(exist_ok=True)
    env.update(PYTHONPATH=os.pathsep.join([str(SRC), str(base)]), HOME=str(home), NO_COLOR="1",
               PYTHONIOENCODING="utf-8")
    env.update(more)
    return env


def folder(base: Path, hold: str = HOLD, *, modal: bool = False) -> Path:
    marker = base / "marker.txt"
    (base / "held.py").write_text(TARGET.format(marker=str(marker), count=str(base / "count.txt"), hold=hold),
                                  encoding="utf-8")
    (base / "prove.toml").write_text(SPEC + (MODAL_TABLE if modal else ""), encoding="utf-8")
    if modal:
        (base / "modal").mkdir()
        (base / "modal" / "__init__.py").write_text(FAKE_MODAL, encoding="utf-8")
    return marker


SWEEP = ("--store", "store", "sweep", "prove.toml", "--target", "held:rollout", "--max-mde", "1", "--yes",
         "--batch-size", "4")


class Child:
    """``python -m poisson_prove ARGV`` from ``base``; stdout always a pipe whose reading end this test
    holds, stderr a pipe too when ``err_pipe``, else a file."""

    def __init__(self, base: Path, argv: Sequence[str], *, err_pipe: bool = False, **env: str) -> None:
        self.base = base
        self.out_r, out_w = os.pipe()
        self.err_path = base / "stderr.txt"
        self.err_r: int | None = None
        if err_pipe:
            self.err_r, err_w = os.pipe()
            err: Any = err_w
        else:
            err = self.err_path.open("wb")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "poisson_prove", *argv], cwd=base, env=child_env(base, **env),
            stdin=subprocess.DEVNULL, stdout=out_w, stderr=err,
        )
        os.close(out_w)
        if err_pipe:
            os.close(err)
        else:
            err.close()
        self.out = b""
        self.err = b""
        for fd in self.readable():
            os.set_blocking(fd, False)

    def readable(self) -> list[int]:
        return [fd for fd in (self.out_r, self.err_r) if fd is not None and fd >= 0]

    def drain(self) -> None:
        for fd in self.readable():
            while True:
                try:
                    chunk = os.read(fd, 1 << 16)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                if fd == self.out_r:
                    self.out += chunk
                else:
                    self.err += chunk

    def until(self, ready: Callable[[], bool], what: str, *, drain: bool = True) -> None:
        deadline = time.monotonic() + WAIT_S
        while not ready():
            if drain:
                self.drain()
            if self.proc.poll() is not None:
                raise AssertionError(f"the command ended ({self.proc.returncode}) before {what}: {self.report()}")
            if time.monotonic() > deadline:
                raise AssertionError(f"timed out waiting for {what}: {self.report()}")
            time.sleep(0.05)

    def close_stdout(self) -> None:
        """What ``head`` does when it exits: the reading end goes away."""
        self.drain()
        os.close(self.out_r)
        self.out_r = -1

    def close_stderr(self) -> None:
        assert self.err_r is not None
        self.drain()
        os.close(self.err_r)
        self.err_r = None

    def finish(self, timeout: float = WAIT_S) -> int:
        try:
            return self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
            raise AssertionError(f"the command did not end within {timeout} s: {self.report()}") from None
        finally:
            for fd in (self.out_r, self.err_r):
                if fd is not None and fd >= 0:
                    os.close(fd)

    def stderr(self) -> str:
        if self.err_r is not None or not self.err_path.exists():
            return self.err.decode("utf-8", "replace")
        return self.err_path.read_text(encoding="utf-8", errors="replace")

    def report(self) -> str:
        return f"stdout {self.out[-600:]!r}; stderr {self.stderr()[-1500:]!r}"


def held(marker: Path) -> Callable[[], bool]:
    return lambda: marker.exists() and marker.read_text(encoding="utf-8").strip() != ""


def the_run(base: Path) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    store = base / "store"
    (run_id,) = [p.name for p in store.iterdir() if (p / "manifest.json").is_file()]
    manifest = json.loads((store / run_id / "manifest.json").read_text(encoding="utf-8"))
    text = (store / run_id / "events.jsonl").read_text(encoding="utf-8")
    events = [json.loads(line) for line in text.splitlines() if line.strip()]
    return run_id, manifest, events


def assert_quiet(child: Child) -> None:
    text = child.stderr()
    assert "Traceback" not in text and "Exception ignored" not in text, child.report()


def assert_interrupted_run(base: Path, child: Child) -> None:
    _, manifest, events = the_run(base)
    assert events and events[-1]["kind"] == "interrupted", (events[-3:], child.report())
    assert manifest["status"] == "partial", manifest


def reap(marker: Path) -> None:
    """End anything a holding child left behind (a browser stand-in, say)."""
    if not marker.exists():
        return
    for line in marker.read_text(encoding="utf-8").split():
        try:
            os.kill(int(line), signal.SIGKILL)
        except (ProcessLookupError, ValueError, PermissionError):
            pass


# ---------- K1, K2: sweep, SIGINT, closed stdout ----------


@pytest.mark.parametrize(
    "json_doc, close_stderr",
    [(False, False), (False, True), (True, False), (True, True)],
    ids=["plain", "plain-stderr-closed", "json", "json-stderr-closed"],
)
def test_k1_k2_an_interrupted_sweep_with_stdout_closed_exits_130_and_logs_interrupted(
    tmp_path: Path, json_doc: bool, close_stderr: bool
) -> None:
    marker = folder(tmp_path)
    argv = [*SWEEP, *(["--json"] if json_doc else [])]
    child = Child(tmp_path, argv, err_pipe=close_stderr)
    try:
        child.until(held(marker), "the target to hold mid-run")
        child.close_stdout()
        if close_stderr:
            child.close_stderr()
        child.proc.send_signal(signal.SIGINT)
        code = child.finish()
    finally:
        reap(marker)
    assert code == INTERRUPTED, (code, child.report())
    assert_interrupted_run(tmp_path, child)
    if not close_stderr:
        assert_quiet(child)


# ---------- K3: the record comes before any write ----------


def test_k3_a_sweep_blocked_on_a_full_stdout_still_logs_interrupted_first(tmp_path: Path) -> None:
    """Nobody reads stdout; the target writes more than the pipe holds and blocks. SIGINT: the
    ``interrupted`` event is in the log while the command is still blocked on stdout. Then the reader
    goes away, and the command exits 130 with no traceback."""
    marker = folder(tmp_path, FLOOD)
    child = Child(tmp_path, list(SWEEP))
    try:
        child.until(held(marker), "the target to start flooding stdout", drain=False)
        time.sleep(0.5)
        assert child.proc.poll() is None, child.report()
        child.proc.send_signal(signal.SIGINT)

        def logged() -> bool:
            try:
                _, _, events = the_run(tmp_path)
            except (ValueError, FileNotFoundError, json.JSONDecodeError):
                return False
            return bool(events) and events[-1]["kind"] == "interrupted"

        child.until(logged, "the interrupted event, with stdout still full", drain=False)
        child.close_stdout()
        code = child.finish()
    finally:
        reap(marker)
    assert code == INTERRUPTED, (code, child.report())
    assert_interrupted_run(tmp_path, child)
    assert_quiet(child)


# ---------- K4: serve and ui ----------


def _two_runs(base: Path) -> tuple[str, str]:
    from conftest import quickstart_design

    design = base / "quickstart.toml"
    design.write_text(quickstart_design(10).read_text(encoding="utf-8").replace("replicates = 10", "replicates = 4"),
                      encoding="utf-8")
    ids = []
    for target, more in ((f"{MOCK}:rollout", []), (f"{MOCK}:rollout_patched", ["--pair-with", "latest"])):
        out = io.StringIO()
        code = cli.main(["--store", str(base / "store"), "sweep", str(design), "--target", target, "--max-mde", "1",
                         "--yes", "--json", *more], stdout=out, stderr=io.StringIO(), stdin=io.StringIO())
        assert code == 0, out.getvalue()
        ids.append(json.loads(out.getvalue())["run_id"])
    return ids[0], ids[1]


def test_k4_serve_interrupted_with_stdout_closed_exits_130(tmp_path: Path) -> None:
    a, b = _two_runs(tmp_path)
    child = Child(tmp_path, ["--store", "store", "serve", a, b, "--x", "task_id", "--y", "tool_fail_rate",
                             "--event", "violated"])
    child.until(lambda: b"http://127.0.0.1:" in child.out, "the page's address on stdout")
    child.close_stdout()
    child.proc.send_signal(signal.SIGINT)
    code = child.finish()
    assert code == INTERRUPTED, (code, child.report())
    assert_quiet(child)


def test_k4_ui_interrupted_with_stdout_closed_exits_130(tmp_path: Path) -> None:
    _two_runs(tmp_path)
    marker = tmp_path / "browser.txt"
    browser = tmp_path / "browser.sh"
    browser.write_text(BROWSER.format(marker=marker), encoding="utf-8")
    browser.chmod(0o755)
    child = Child(tmp_path, ["--store", "store", "ui", "--open"], BROWSER=f"{browser} %s")
    try:
        child.until(held(marker), "the browser to be opened")
        child.close_stdout()
        child.proc.send_signal(signal.SIGINT)
        code = child.finish()
    finally:
        reap(marker)
    assert code == INTERRUPTED, (code, child.report())
    assert_quiet(child)


# ---------- K5: a closed pipe and no interrupt ----------


@pytest.mark.parametrize("verb", ["sweep", "runs"])
def test_k5_a_closed_pipe_with_no_interrupt_still_exits_0_quietly(tmp_path: Path, verb: str) -> None:
    """The reader took what it wanted and left (``| head -1``): exit 0, nothing on stderr about it."""
    (tmp_path / "prove.toml").write_text(SPEC.replace("replicates = 50", "replicates = 2"), encoding="utf-8")
    sweep_argv = ["--store", "store", "sweep", "prove.toml", "--target", f"{MOCK}:rollout", "--max-mde", "1", "--yes"]
    if verb == "runs":
        done = subprocess.run([sys.executable, "-m", "poisson_prove", *sweep_argv], cwd=tmp_path,
                              env=child_env(tmp_path), capture_output=True, timeout=WAIT_S)
        assert done.returncode == 0, done.stderr
    argv = sweep_argv if verb == "sweep" else ["--store", "store", "runs"]
    child = Child(tmp_path, argv)
    child.close_stdout()
    code = child.finish()
    assert code == 0, (code, child.report())
    assert_quiet(child)


# ---------- K7, RB-34: local and Modal keep Python's default ----------


@pytest.mark.parametrize("backend", ["local", "modal"])
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP], ids=["SIGTERM", "SIGHUP"])
def test_k7_rb34_a_local_or_modal_sweep_keeps_pythons_default_for_sigterm_and_sighup(
    tmp_path: Path, backend: str, sig: signal.Signals
) -> None:
    """No handler in this release outside the cloud backend: the signal ends the process as Python's
    default does, by the signal itself."""
    marker = folder(tmp_path, modal=backend == "modal")
    argv = [*SWEEP, *(["--backend", "modal"] if backend == "modal" else [])]
    child = Child(tmp_path, argv)
    try:
        child.until(held(marker), "the target to hold mid-run")
        child.proc.send_signal(sig)
        code = child.finish()
    finally:
        reap(marker)
    assert code == -sig, (code, child.report())
