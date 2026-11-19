"""One real call of a rollout, in a process of its own: what ``sweep --try`` runs.

The call's process is started with this interpreter and this environment, the spec's folder first
on its import path, the network allowed, no byte code written, and in a session of its own, so
that everything it starts can be ended with it. It imports the target, calls it once and leaves
its answer in a scratch folder that is gone when the call is over, as the check's import does; the
folder the command ran in is never written to. Its stdout and stderr are pipes: what arrives on
either is handed to the caller as it arrives, and the lines on stdout are counted. A limit, an
interrupt and the end of the call each end the process and its group.

Nothing here prints, asks or exits: the core's ``try_once`` decides what an answer means and a
face renders it.
"""

from __future__ import annotations

import codecs
import contextlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__: list[str] = []

#: How long the call may take when no limit is given.
DEFAULT_LIMIT_S = 300.0
#: How long the call's process has to end by itself once it has answered (its exit hooks run in
#: that time), and how long what it left in its pipes is waited for after it is ended.
_EXIT_GRACE_S = 5.0
_DRAIN_GRACE_S = 5.0
_POLL_S = 0.02

#: The call's own process. Standard library only until the target is imported. It leaves two
#: files in the scratch folder the request names: ``imported``, once the target is in hand (the
#: call's limit counts from there), and ``answer.json``, how the call ended, moved into place whole.
_CALL = r"""
import json, os, sys

sys.dont_write_bytecode = True
_scratch, _folder, _module, _attr, _path, _config, _seed = json.loads(sys.argv[1])
sys.path[:] = [_folder, *(p for p in _path if p != _folder)]


def _frames(exc, origin):
    import traceback

    frames = [(f.filename, f.lineno) for f in traceback.extract_tb(exc.__traceback__)]
    raised = frames[-1] if frames else None
    called = None
    if origin is not None:
        for frame in reversed(frames):
            if os.path.abspath(frame[0]) == origin:
                called = frame
                break
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "raised": raised,
        "called": called,
        "traceback": "".join(traceback.format_exception(exc)),
    }


def _flush():
    for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):
        try:
            stream.flush()
        except Exception:
            pass


def _main():
    import importlib
    import importlib.util

    origin = None
    try:
        found = importlib.util.find_spec(_module)
        if found is not None and isinstance(found.origin, str):
            origin = os.path.abspath(found.origin)
        module = importlib.import_module(_module)
        rollout = getattr(module, _attr)
    except BaseException as exc:
        return {"ended": "raised", "during": "import", **_frames(exc, origin)}
    from time import perf_counter

    from poisson_prove.episode import Episode

    open(os.path.join(_scratch, "imported"), "w").close()
    began = perf_counter()
    try:
        result = rollout(_config, _seed)
    except BaseException as exc:
        return {"ended": "raised", "during": "call", **_frames(exc, origin)}
    seconds = perf_counter() - began
    if not isinstance(result, Episode):
        return {"ended": "not an episode", "type": type(result).__name__, "seconds": seconds}
    episode = result.to_dict()
    try:
        json.dumps(episode)
    except (TypeError, ValueError) as exc:
        return {"ended": "unstorable", "message": str(exc), "seconds": seconds}
    return {"ended": "episode", "episode": episode, "seconds": seconds}


_document = _main()
_flush()
_staged = os.path.join(_scratch, "answer.json.new")
with open(_staged, "w", encoding="utf-8") as _fh:
    json.dump(_document, _fh)
os.replace(_staged, os.path.join(_scratch, "answer.json"))
"""


@dataclass(frozen=True)
class Call:
    """How one call ended, as the call's process said it or as its end showed it.

    ``ended`` is ``episode`` (with ``episode``, the Episode as a dict), ``raised`` (with ``kind``,
    ``message``, ``raised`` and ``called``, each a ``(file, line)`` or None, ``traceback`` and
    ``during``, ``import`` or ``call``), ``not an episode`` (with ``kind``, the type returned),
    ``unstorable`` (with ``message``), ``timeout`` (with ``during``) or ``exited`` (with
    ``exit_code``: the process ended before it answered)."""

    ended: str
    #: The call's own seconds for an Episode; else the seconds until the call was over.
    seconds: float
    #: The lines the rollout wrote to its stdout, a last line with no newline among them.
    printed: int
    episode: Mapping[str, Any] | None = None
    kind: str = ""
    message: str = ""
    raised: tuple[str, int] | None = None
    called: tuple[str, int] | None = None
    traceback: str = ""
    during: str = "call"
    exit_code: int | None = None
    limit: float = DEFAULT_LIMIT_S


class _Pump(threading.Thread):
    """One of the call's output pipes, read to its end and handed on as text as it arrives."""

    def __init__(
        self,
        pipe: Any,
        name: str,
        on_output: Callable[[str, str], None] | None,
        lock: threading.Lock,
    ) -> None:
        super().__init__(daemon=True)
        self.pipe = pipe
        self.stream = name
        self.on_output = on_output
        self.lock = lock
        self.newlines = 0
        self.last = b""
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def run(self) -> None:
        fd = self.pipe.fileno()
        while True:
            try:
                chunk = os.read(fd, 65536)
            except (OSError, ValueError):
                break
            if not chunk:
                break
            self.newlines += chunk.count(b"\n")
            self.last = chunk[-1:]
            self._hand_on(self.decoder.decode(chunk))
        self._hand_on(self.decoder.decode(b"", final=True))

    def _hand_on(self, text: str) -> None:
        if not text or self.on_output is None:
            return
        with self.lock, contextlib.suppress(Exception):
            self.on_output(self.stream, text)

    @property
    def lines(self) -> int:
        return self.newlines + (1 if self.last not in (b"", b"\n") else 0)


def _end(proc: subprocess.Popen[bytes]) -> None:
    """The call's process ended, with everything it started in its group."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except OSError:
        pass
    with contextlib.suppress(Exception):
        proc.wait()


def _pair(value: Any) -> tuple[str, int] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return str(value[0]), int(value[1])
    return None


def _answer(scratch: Path) -> dict[str, Any] | None:
    try:
        document = json.loads((scratch / "answer.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) and "ended" in document else None


def call_once(
    module: str,
    attr: str,
    *,
    folder: str,
    config: Mapping[str, Any],
    seed: int,
    limit: float | None = None,
    on_output: Callable[[str, str], None] | None = None,
    path: Sequence[str] | None = None,
) -> Call:
    """Call ``module:attr`` once on ``(config, seed)`` in a process of its own and say how it
    ended. ``on_output(stream, text)`` gets what the process writes to ``stdout`` and ``stderr``
    as it arrives, from a thread of its own. ``limit`` is the seconds the import may take and
    then the seconds the call may take. An interrupt ends the process and is raised again."""
    limit = DEFAULT_LIMIT_S if limit is None else float(limit)
    lock = threading.Lock()
    began = time.monotonic()
    proc: subprocess.Popen[bytes] | None = None
    pumps: list[_Pump] = []
    answer: dict[str, Any] | None = None
    timed_out: str | None = None
    exit_code: int | None = None
    with tempfile.TemporaryDirectory(prefix="poisson-prove-try-") as held:
        scratch = Path(held)
        request = json.dumps(
            [
                str(scratch),
                folder,
                module,
                attr,
                list(sys.path if path is None else path),
                dict(config),
                seed,
            ]
        )
        try:
            proc = subprocess.Popen(
                [sys.executable, "-B", "-c", _CALL, request],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            pumps = [
                _Pump(proc.stdout, "stdout", on_output, lock),
                _Pump(proc.stderr, "stderr", on_output, lock),
            ]
            for pump in pumps:
                pump.start()
            phase = "import"
            deadline = time.monotonic() + limit
            while True:
                answer = _answer(scratch)
                if answer is not None:
                    break
                if phase == "import" and (scratch / "imported").exists():
                    phase = "call"
                    deadline = time.monotonic() + limit
                if proc.poll() is not None:
                    answer = _answer(scratch)  # written just before it ended
                    break
                if time.monotonic() >= deadline:
                    timed_out = phase
                    break
                time.sleep(_POLL_S)
            if timed_out is None:
                # Its exit hooks run, and what they write is passed on, before anything is ended.
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(_EXIT_GRACE_S)
        finally:
            if proc is not None:
                exit_code = proc.poll()
                _end(proc)
                for pump in pumps:
                    pump.join(_DRAIN_GRACE_S)
                for stream in (proc.stdout, proc.stderr):
                    with contextlib.suppress(Exception):
                        stream.close()  # type: ignore[union-attr]
    seconds = time.monotonic() - began
    printed = pumps[0].lines if pumps else 0
    if timed_out is not None:
        return Call("timeout", seconds, printed, during=timed_out, limit=limit)
    if answer is None:
        return Call("exited", seconds, printed, exit_code=exit_code, limit=limit)
    ended = str(answer["ended"])
    took = float(answer.get("seconds", seconds))
    if ended == "episode":
        return Call(ended, took, printed, episode=dict(answer["episode"]), limit=limit)
    if ended == "raised":
        return Call(
            ended,
            seconds,
            printed,
            kind=str(answer.get("type", "")),
            message=str(answer.get("message", "")),
            raised=_pair(answer.get("raised")),
            called=_pair(answer.get("called")),
            traceback=str(answer.get("traceback", "")),
            during=str(answer.get("during", "call")),
            limit=limit,
        )
    if ended == "not an episode":
        return Call(ended, took, printed, kind=str(answer.get("type", "")), limit=limit)
    return Call(ended, took, printed, message=str(answer.get("message", "")), limit=limit)
