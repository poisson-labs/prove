"""``remote_parallel_map`` as 1.8.1 behaves from the caller's side, over a local worker pool.

What it mirrors, by line of the tag's ``client/src/burla/``:

- **Signature and defaults**: ``_remote_parallel_map.py:708-723``.
- **Inputs**: a non-tuple input becomes a one-tuple and a tuple input is unpacked into the
  function's arguments (``:823``, ``:835-838``); an empty list returns at once (``:824-825``).
- **The submit-time rule**: ``_env_scan.py`` here, called where 1.8.1 calls it (``:844-847``),
  synchronously, before anything else is started.
- **Serialisation**: the function is cloudpickled (a ``__main__`` function travels by value)
  and so is each input (``:335``, ``_node.py:780-806``); a function over 0.1 GB is refused with
  ``FunctionTooBig`` (``:336-339``).
- **Signals**: handlers for SIGINT, SIGTERM, SIGHUP and SIGQUIT are installed on the calling
  thread when the call is made (``:873-875``, ``_helpers.py:11-14``, ``:113-116``), which raises
  ``ValueError`` off the main thread. The first signal cancels the job and the calls in flight;
  later ones do nothing (``_helpers.py:73-75``); the call then raises
  ``JobCanceled("Job canceled by user.")`` (``:976-985``). The handlers are restored when the
  call ends (``:999``).
- **The heartbeat**: a stand-in child in the caller's own session for the length of the call,
  which never checks its parent (``_heartbeat.py:16-35``, started at ``:666-671``).
- **Results**: with ``generator=True`` the call returns a generator; bare return values come
  back in completion order, and it stops after ``len(inputs)`` results however many were
  distinct (``:954-967``). So a result that arrives twice pushes the last one out: in 1.8.1 a
  result goes missing *without* an exception only that way, since a job that ends short
  otherwise raises ``JobStalled`` (``:678-688``). The fake's ``withhold`` is therefore the
  withheld input's slot filled by a second copy of another result. An exception from the
  function comes back as a value carrying ``burla_input_index`` when ``raise_errors=False``
  (``_node.py:820-846``), and its traceback is printed.
- **Job-level failures**: ``NodeDisconnected`` ends the call even with ``raise_errors=False``
  (``_node.py:823-827``), and a heartbeat that dies ends it with a bare ``Exception`` whose
  message starts ``Heartbeat process failed!`` (``:673-675``).
- **The head**: a call made without ``BURLA_CLUSTER_DASHBOARD_URL`` would find or start a head
  of its own (``__init__.py:105-173``); the fake refuses it instead. With the variable, the value
  must be https or local (``__init__.py:111-121``).
"""

from __future__ import annotations

import os
import pickle
import random
import signal
import subprocess
import sys
import threading
import traceback
import uuid
from collections import deque
from collections.abc import Callable, Iterator
from queue import Empty, Queue
from typing import Any
from urllib.parse import urlparse

import cloudpickle

from burla import _env_scan, _fake
from burla._node import (
    AllNodesBusy,
    ClusterRestarted,
    ClusterShutdown,
    DetachRequiresDeployedCluster,
    JobCanceled,
    JobStalled,
    NoCompatibleNodes,
    NodeDisconnected,
    NodesFailedToBoot,
    NoNodes,
    _FakeNode,
)

_SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT)
_MAX_FUNCTION_GB = 0.1
_POLL_S = 0.05
_HEARTBEAT = "import time\nwhile True:\n    time.sleep(1)\n"


class FunctionTooBig(Exception):  # _remote_parallel_map.py:228-237
    def __init__(self, function_name: str) -> None:
        super().__init__(
            f"\n\nYour function `{function_name}` is referencing some large objects!\n"
            "Functions submitted to Burla, including objects they reference that are defined "
            "elsewhere, must be less than 0.1GB.\n"
        )


def _refusal(name: str, token: str, n_inputs: int) -> BaseException:
    """The exceptions a test can ask a call to end with, each as 1.8.1 builds it. The token
    marks the ones whose 1.8.1 message has a free part, so a test can find it again."""
    if name == "JobStalled":
        return JobStalled(
            f"Job ended before all results were received (0/{n_inputs}).\nFinal node states:\n"
            f"  fake-node-0: python 3.11 on the worker, 3.12 here ({token})\n"
        )
    if name == "NodesFailedToBoot":
        return NodesFailedToBoot([_FakeNode("fake-node-0")])
    if name == "NoNodes":
        return NoNodes(f"No nodes are running ({token}).")
    if name == "NoCompatibleNodes":
        return NoCompatibleNodes(None)
    if name == "UnsupportedLocalImport":
        return _env_scan.UnsupportedLocalImport([f"    fake.py:1 in `f()`: import local_{token}"])
    if name == "FunctionTooBig":
        return FunctionTooBig(f"_bootstrap_{token}")
    if name == "ClusterShutdown":
        return ClusterShutdown()
    if name == "ClusterRestarted":
        return ClusterRestarted()
    if name == "JobCanceled":
        return JobCanceled("Job canceled by user.")
    if name == "AllNodesBusy":
        return AllNodesBusy()
    if name == "Unnamed":
        return RuntimeError(f"an exception no backend names ({token})")
    raise ValueError(f"fake burla: the script names an unknown refusal {name!r}")


def _describe(item: Any) -> dict[str, Any]:
    """An input as the record keeps it: its shape, and its fields when it is Prove's six."""
    described: dict[str, Any] = {"type": type(item).__name__}
    if isinstance(item, tuple):
        described["arity"] = len(item)
        if len(item) == 6:
            k, jobs, import_path, episode_timeout, capture, chaos = item
            described.update(
                k=k,
                jobs=[list(job) for job in jobs] if isinstance(jobs, (list, tuple)) else repr(jobs),
                import_path=import_path,
                episode_timeout=episode_timeout,
                capture=capture,
                chaos=chaos,
            )
    return described


def _head_refusal() -> BaseException | None:
    url = os.environ.get("BURLA_CLUSTER_DASHBOARD_URL")
    if not url:
        return RuntimeError(
            "fake burla: this call would find or start a head of its own "
            "(BURLA_CLUSTER_DASHBOARD_URL is unset)"
        )
    host = urlparse(url.rstrip("/")).hostname or ""
    if not url.startswith("https://") and host not in ("localhost", "127.0.0.1", "main_service"):
        return ValueError("BURLA_CLUSTER_DASHBOARD_URL must use HTTPS")
    return None


def _edit_rows(value: Any, script: dict[str, Any]) -> Any:
    """``strip_chaos_record`` and ``alter_record``, applied to Prove's ``(k, rows, failure)``."""
    if not (script.get("strip_chaos_record") or script.get("alter_record")):
        return value
    if not (isinstance(value, tuple) and len(value) == 3 and isinstance(value[1], list)):
        return value
    for row in value[1]:
        meta = row.get("backend_meta") if isinstance(row, dict) else None
        if not isinstance(meta, dict):
            continue
        if script.get("strip_chaos_record"):
            meta.pop("chaos", None)
        elif isinstance(meta.get("chaos"), dict):
            meta["chaos"].update(script["alter_record"])
    return value


class _Dispatch:
    """The job: inputs handed to the pool's workers, one at a time each, replies in a queue."""

    def __init__(
        self,
        fn_bytes: bytes,
        inputs: list[tuple[Any, ...]],
        pool: list[dict[str, Any]],
        parallelism: int,
        call_no: int,
        script: dict[str, Any],
    ) -> None:
        self.fn_bytes = fn_bytes
        self.todo: deque[tuple[int, tuple[Any, ...]]] = deque(enumerate(inputs))
        self.lock = threading.Lock()
        self.replies: Queue[tuple[int, Any]] = Queue()
        self.stopped = threading.Event()
        self.call_no = call_no
        self.script = script
        self.served = os.path.join(_fake.state_dir(), "served.jsonl")
        self.threads = [
            threading.Thread(target=self._serve, args=(worker,), daemon=True)
            for worker in pool[: max(1, parallelism)]
        ]
        for thread in self.threads:
            thread.start()

    def _serve(self, worker: dict[str, Any]) -> None:
        try:
            conn = _fake.connect(worker["socket"])
        except OSError:
            self.replies.put((-1, ("infra", traceback.format_exc())))
            return
        index = -1
        try:
            _fake.send(conn, ("reset",))
            _fake.recv(conn)
            _fake.send(conn, ("load", self.fn_bytes, self.served, self.call_no))
            _fake.recv(conn)
            while not self.stopped.is_set():
                with self.lock:
                    if not self.todo:
                        return
                    index, item = self.todo.popleft()
                if self.script.get("strip_chaos_field") and len(item) == 6:
                    item = (*item[:5], None)
                _fake.send(conn, ("call", index, cloudpickle.dumps(item)))
                reply = _fake.recv(conn)
                if self.stopped.is_set():
                    return  # a cancelled call's late result is dropped (worker_client.py:1858-1868)
                self.replies.put((index, reply))
        except (OSError, EOFError):
            if not self.stopped.is_set():
                self.replies.put((index, ("infra", traceback.format_exc())))
        finally:
            conn.close()

    def stop(self) -> None:
        self.stopped.set()


def remote_parallel_map(
    function_: Callable[..., Any],
    inputs: list[Any],
    func_cpu: int | str = "dynamic",
    func_ram: int | str = "dynamic",
    func_gpu: str | None = None,
    image: str | None = None,
    grow: bool = False,
    max_parallelism: int | None = None,
    detach: bool = False,
    generator: bool = False,
    raise_errors: bool = True,
    spinner: bool = True,
    region: str | None = None,
    disk_gb: int | None = None,
) -> Any:
    call_no, script = _fake.next_attempt()
    token = uuid.uuid4().hex
    inputs = list(inputs)
    scan = _env_scan.scan_environment()
    shipped = _env_scan.modules_to_pickle_by_value(scan)
    offenders = _env_scan.offenders(function_, scan, shipped)
    watch = _fake.watched()
    start: dict[str, Any] = {
        "call": call_no,
        "event": "start",
        "time": _fake.now(),
        "token": token,
        "launcher_pid": os.getpid(),
        "session_leader": os.getsid(0) == os.getpid(),
        "main_thread": threading.current_thread() is threading.main_thread(),
        "env": {
            name: os.environ.get(name)
            for name in ("DISABLE_BURLA_TELEMETRY", "BURLA_CLUSTER_DASHBOARD_URL")
        },
        "function": {
            "name": getattr(function_, "__name__", None),
            "module": getattr(function_, "__module__", None),
            "qualname": getattr(function_, "__qualname__", None),
        },
        "kwargs": {
            "func_cpu": func_cpu,
            "func_ram": func_ram,
            "func_gpu": func_gpu,
            "image": image,
            "grow": grow,
            "max_parallelism": max_parallelism,
            "detach": detach,
            "generator": generator,
            "raise_errors": raise_errors,
            "spinner": spinner,
            "region": region,
            "disk_gb": disk_gb,
        },
        "n_inputs": len(inputs),
        "items": [_describe(item) for item in inputs],
        "watched_modules": sorted(
            name for name in sys.modules if name.partition(".")[0] in watch
        ),
        "shipped": sorted(shipped),
        "offenders": offenders,
    }
    _fake.record("calls.jsonl", start)
    # Burla prints on the caller's terminal (its spinner, a returned exception's traceback). The
    # line carries the call's token so a test can find where the launcher's output went.
    print(f"fake burla stdout {token}", flush=True)
    print(f"fake burla stderr {token}", file=sys.stderr, flush=True)
    if script.get("print"):
        print(str(script["print"]), flush=True)
        print(str(script["print"]), file=sys.stderr, flush=True)

    def end(how: str, **extra: Any) -> None:
        _fake.record("calls.jsonl", {"call": call_no, "event": "end", "how": how,
                                     "time": _fake.now(), **extra})

    inputs = [item if isinstance(item, tuple) else (item,) for item in inputs]  # :823
    if not inputs:
        end("empty")
        return iter([]) if generator else []
    refused = _head_refusal()
    if refused is None and offenders:
        refused = _env_scan.UnsupportedLocalImport(offenders)
    if refused is None and script.get("refuse") == "UnsupportedLocalImport":
        refused = _refusal("UnsupportedLocalImport", token, len(inputs))
    if refused is not None:
        end("raised", type=type(refused).__name__, message=str(refused))
        raise refused

    def wrapped_function_(args_tuple: tuple[Any, ...]) -> Any:  # :835-838
        return function_(*args_tuple)

    wrapped_function_.__name__ = function_.__name__
    fn_bytes = cloudpickle.dumps(wrapped_function_)
    cancel = threading.Event()
    signals: list[tuple[int, float]] = []

    def handler(signum: int, frame: Any) -> None:
        if cancel.is_set():
            return  # _helpers.py:73-75
        signals.append((signum, _fake.now()))
        cancel.set()

    try:
        original = {sig: signal.getsignal(sig) for sig in _SIGNALS}
        for sig in _SIGNALS:
            signal.signal(sig, handler)  # ValueError off the main thread, as in 1.8.1
    except ValueError as exc:
        end("raised", type="ValueError", message=str(exc))
        raise
    heartbeat = subprocess.Popen([sys.executable, "-I", "-S", "-c", _HEARTBEAT])
    _fake.record("calls.jsonl", {"call": call_no, "event": "heartbeat", "pid": heartbeat.pid,
                                 "fn_bytes": len(fn_bytes)})

    def outputs() -> Iterator[Any]:
        dispatch: _Dispatch | None = None
        yielded: list[int] = []
        how = "complete"
        extra: dict[str, Any] = {}
        try:
            if detach:
                raise DetachRequiresDeployedCluster()
            if len(fn_bytes) / (1024**3) > _MAX_FUNCTION_GB:
                raise FunctionTooBig(function_.__name__)
            if script.get("busy"):
                raise AllNodesBusy()
            if script.get("refuse") and script.get("refuse_after") is None:
                raise _refusal(str(script["refuse"]), token, len(inputs))
            pool = _fake.workers()
            parallelism = min(len(pool), max_parallelism or len(inputs), len(inputs))
            dispatch = _Dispatch(fn_bytes, inputs, pool, parallelism, call_no, script)
            for index, value in _results(dispatch, len(inputs), script, cancel, raise_errors, token):
                yielded.append(index)
                yield value
            if cancel.is_set():
                raise JobCanceled("Job canceled by user.")
        except BaseException as exc:
            how = "cancelled" if cancel.is_set() else "raised"
            extra = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            if dispatch is not None:
                dispatch.stop()
            if heartbeat.poll() is None:
                heartbeat.kill()
            heartbeat.wait()
            for sig, previous in original.items():
                signal.signal(sig, previous)
            end(how, yielded=yielded, signals=signals, **extra)

    stream = outputs()
    return stream if generator else list(stream)


def _value(index: int, reply: Any, script: dict[str, Any], raise_errors: bool) -> Any:
    kind = reply[0]
    if kind == "infra":
        message = f"Worker on node fake-node-0 failed while executing input index {index}:\n\n"
        raise NodeDisconnected(_FakeNode("fake-node-0"), message + str(reply[1]))
    if kind == "ok":
        return _edit_rows(cloudpickle.loads(reply[1]), script)
    try:
        exc = pickle.loads(reply[1])
    except Exception:  # noqa: BLE001 - an unpicklable exception still comes back as one
        exc = RuntimeError(reply[2])
    exc.burla_input_index = index
    if raise_errors:
        raise exc
    print(f"Input at index {index} raised an exception (returned in results):\n{reply[2]}")
    return exc


def _scripted(index: int, value: Any, script: dict[str, Any]) -> Any:
    for entry in script.get("exceptions", []):
        if entry["index"] == index:
            exc = RuntimeError(f"fake burla: a scripted exception value for input {index}")
            if entry.get("with_index", True):
                exc.burla_input_index = index  # type: ignore[attr-defined]
            return exc
    return value


def _results(
    dispatch: _Dispatch,
    n: int,
    script: dict[str, Any],
    cancel: threading.Event,
    raise_errors: bool,
    token: str,
) -> Iterator[tuple[int, Any]]:
    """``(input index, value)`` in the order the caller sees them, stopping after ``n``."""
    collect = any(
        script.get(key) is not None
        for key in ("shuffle", "order", "duplicate", "withhold", "exceptions")
    )
    arrived: list[tuple[int, Any]] = []

    def pull() -> tuple[int, Any] | None:
        while not cancel.is_set():
            try:
                return dispatch.replies.get(timeout=_POLL_S)
            except Empty:
                continue
        return None

    if collect:
        while len(arrived) < n:
            got = pull()
            if got is None:
                return
            if got[1][0] == "infra":
                _value(got[0], got[1], script, raise_errors)
            arrived.append(got)
        order = list(arrived)
        if script.get("shuffle") is not None:
            random.Random(script["shuffle"]).shuffle(order)
        if script.get("order") is not None:
            rank = {index: position for position, index in enumerate(script["order"])}
            order.sort(key=lambda entry: rank.get(entry[0], len(rank)))
        withheld = set(script.get("withhold", []))
        composed: list[tuple[int, Any]] = []
        for position, (index, reply) in enumerate(order):
            if index in withheld:
                # Its slot goes to a second copy of another result. A call whose every input is
                # withheld has none to copy, and ends short without one.
                others = [entry for entry in order if entry[0] not in withheld]
                if others:
                    composed.append(others[min(position, len(others) - 1)])
                continue
            composed.append((index, reply))
            if index in script.get("duplicate", []):
                composed.append((index, reply))
        source: Iterator[tuple[int, Any]] = iter(composed[:n])  # :957 counts, it does not dedup
    else:
        source = iter(())
    count = 0
    while count < n:
        if cancel.is_set():
            return
        for key, build in (
            ("disconnect_after", lambda: NodeDisconnected(_FakeNode("fake-node-1"))),
            ("heartbeat_fails_after", lambda: Exception(
                "Heartbeat process failed!\nfake burla: the stand-in heartbeat exited\n")),
            ("refuse_after", lambda: _refusal(str(script.get("refuse")), token, n)),
        ):
            if script.get(key) is not None and count >= script[key]:
                raise build()
        if script.get("hang_after") is not None and count >= script["hang_after"]:
            if not cancel.wait(_fake.HANG_LIMIT_S):
                raise JobStalled("fake burla: the scripted hang expired without a cancel")
            return
        if collect:
            got = next(source, None)
            if got is None:
                return
        else:
            got = pull()
            if got is None:
                return
        index, reply = got
        value = _scripted(index, _value(index, reply, script, raise_errors), script)
        count += 1
        yield index, value
