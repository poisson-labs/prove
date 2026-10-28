"""The fake's own machinery: its state folder, the script a test writes, the records it keeps, the
worker pool it talks to, and the network tripwire. Nothing here stands for a Burla module.

State folder (``BU_FAKE_BURLA_STATE``), written by the test before a run:

- ``script.json``: ``{"version": ..., "watch": [...], "attempts": [{...}, ...], "default": {...}}``.
  Call attempt ``n`` (counted across every launcher that shares the folder) follows
  ``attempts[n]`` when there is one, else ``default``. ``watch`` names the top-level packages
  whose modules must be absent from the launcher (``poisson_prove`` and the bundled packages).
- ``workers.json``: the pool, ``[{"socket": path, "pid": pid}, ...]``, written by the fixture
  that started the workers.

Records, appended by the fake, one JSON object per line:

- ``calls.jsonl``: one line per call attempt when it starts, one ``"event": "end"`` line when it
  ends, however it ends.
- ``served.jsonl``: one line per input a worker served, written by the worker itself.

The script's keys, each a fault the Burla backend must survive:
``busy`` (AllNodesBusy at the first iteration), ``refuse`` (a named exception at the first
iteration) or ``refuse_after`` (the same after that many results), ``shuffle`` (a seed),
``duplicate`` and ``withhold`` (input indices), ``exceptions`` (``[{"index", "with_index"}]``),
``disconnect_after``, ``heartbeat_fails_after``, ``hang_after``, ``strip_chaos_field``,
``strip_chaos_record``, ``alter_record`` (fields to overwrite in every row's chaos record),
``order`` (input indices, the order results are returned in), and ``print`` (a line the call
writes to its stdout and stderr).
"""

from __future__ import annotations

import fcntl
import json
import os
import pickle
import socket
import struct
import time
from typing import Any

STATE_VAR = "BU_FAKE_BURLA_STATE"
HANG_LIMIT_S = 600.0


def state_dir() -> str:
    path = os.environ.get(STATE_VAR)
    if not path:
        raise RuntimeError(f"fake burla: {STATE_VAR} is unset; start the launcher through launch.py")
    return path


def _script() -> dict[str, Any]:
    try:
        with open(os.path.join(state_dir(), "script.json"), encoding="utf-8") as fh:
            loaded = json.load(fh)
    except FileNotFoundError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def fake_version(default: str) -> str:
    if not os.environ.get(STATE_VAR):
        return default
    return str(_script().get("version", default))


def watched() -> list[str]:
    return [str(name) for name in _script().get("watch", [])]


def next_attempt() -> tuple[int, dict[str, Any]]:
    """This call's attempt number and its entry of the script, under a lock: launchers that
    share the folder count one sequence."""
    lock_path = os.path.join(state_dir(), "attempts.lock")
    count_path = os.path.join(state_dir(), "attempts.count")
    with open(lock_path, "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(count_path, encoding="utf-8") as fh:
                n = int(fh.read().strip() or "0")
        except FileNotFoundError:
            n = 0
        with open(count_path, "w", encoding="utf-8") as fh:
            fh.write(str(n + 1))
        fcntl.flock(lock, fcntl.LOCK_UN)
    script = _script()
    attempts = script.get("attempts", [])
    entry = attempts[n] if n < len(attempts) else script.get("default", {})
    return n, dict(entry or {})


def record(name: str, entry: dict[str, Any]) -> None:
    line = json.dumps(entry, default=repr, sort_keys=True) + "\n"
    with open(os.path.join(state_dir(), name), "a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
        fcntl.flock(fh, fcntl.LOCK_UN)


def workers() -> list[dict[str, Any]]:
    with open(os.path.join(state_dir(), "workers.json"), encoding="utf-8") as fh:
        pool = json.load(fh)
    return [dict(worker) for worker in pool]


# ---------- the wire to a worker: length-prefixed pickles over a Unix socket ----------


def send(conn: socket.socket, message: Any) -> None:
    data = pickle.dumps(message)
    conn.sendall(struct.pack(">Q", len(data)) + data)


def _exactly(conn: socket.socket, n: int) -> bytes:
    chunks = []
    while n:
        chunk = conn.recv(min(n, 1 << 20))
        if not chunk:
            raise EOFError("worker closed the connection")
        chunks.append(chunk)
        n -= len(chunk)
    return b"".join(chunks)


def recv(conn: socket.socket) -> Any:
    (size,) = struct.unpack(">Q", _exactly(conn, 8))
    return pickle.loads(_exactly(conn, size))


def connect(path: str) -> socket.socket:
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.connect(path)
    return conn


def now() -> float:
    return time.time()
