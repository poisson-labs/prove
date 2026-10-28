"""Run a function in a child process and return its result: what the capture, storage, chaos and
backend tests share.

``install()`` is once per process and claims OpenTelemetry's global provider, so nothing that
installs capture may run in pytest's own process. ``isolated`` runs ``fn(*args)`` in a child,
forked when the platform allows (the child inherits this process's imports and its untouched
OTel globals) and spawned otherwise, which works because ``fn`` and everything it reaches live in
a real test file. The child always reports: its result, or the traceback of what it raised.
"""

from __future__ import annotations

import multiprocessing
import time
import traceback
from typing import Any
from collections.abc import Callable

import pytest

FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()


def _child_entry(
    conn: Any, fn: Callable[..., Any], args: tuple[Any, ...], prepare: Callable[[], None] | None
) -> None:
    try:
        if prepare is not None:
            prepare()
        outcome: tuple[str, Any] = ("ok", fn(*args))
    except BaseException:  # noqa: BLE001 - the child must always report
        outcome = ("error", traceback.format_exc())
    try:
        conn.send(outcome)
    finally:
        conn.close()


def _silent(proc: Any) -> tuple[str, Any]:
    return ("error", f"child exited with code {proc.exitcode} before reporting")


def _receive(conn: Any, proc: Any) -> tuple[str, Any]:
    """The child's report, or the error of a child whose end of the pipe closed with nothing on it."""
    try:
        return conn.recv()
    except EOFError:
        proc.join(10.0)
        return _silent(proc)


def isolated(
    fn: Callable[..., Any],
    *args: Any,
    timeout: float = 120.0,
    method: str | None = None,
    prepare: Callable[[], None] | None = None,
) -> Any:
    """Run ``fn(*args)`` in a child process and return its (picklable) result.

    ``method`` is the start method (``"fork"`` when available, else ``"spawn"``, by default);
    ``prepare`` runs in the child before ``fn``. A result the child sent just before it exited is
    still read: the pipe is polled once more after the child is seen to be gone.
    """
    ctx = multiprocessing.get_context(method or ("fork" if FORK_AVAILABLE else "spawn"))
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child_entry, args=(child_conn, fn, args, prepare))
    proc.start()
    child_conn.close()
    deadline = time.perf_counter() + timeout
    outcome: tuple[str, Any] | None = None
    try:
        while outcome is None:
            if parent_conn.poll(0.05):
                outcome = _receive(parent_conn, proc)
            elif not proc.is_alive():
                proc.join(10.0)
                outcome = _receive(parent_conn, proc) if parent_conn.poll() else _silent(proc)
            elif time.perf_counter() > deadline:
                outcome = ("error", f"child produced nothing within {timeout}s")
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
        proc.join(10.0)
    kind, payload = outcome
    if kind != "ok":
        pytest.fail(f"isolated {fn.__name__} failed:\n{payload}")
    return payload
