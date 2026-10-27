"""The Burla backend's launcher: a script run as ``python -I <this file>``, in its own session.

It imports the standard library and, inside ``main()``, ``burla``: nothing of Prove, Tasks or the
demo. Burla 1.8.2 ships every local module in the calling process's ``sys.modules`` and refuses
one that imports local code inside a function, so the one function it is handed is
``_bootstrap``, defined here in ``__main__`` and shipped by value with the bundle in its globals.

On a worker, ``_bootstrap`` unpacks the bundle once per process into a private folder under the
temporary directory, puts it first on ``sys.path`` after unloading whatever another bundle left
there, and runs Prove's ``_container_batch``. A batch of a run with ``[chaos]`` or ``[capture]``
runs in an interpreter spawned for that batch, since both arm once per process and a warm worker
may have armed another run's.

The folder is the process's own. It holds a lock on a file inside it for as long as it lives,
which the kernel releases however the process ends, so any other process can tell a folder whose
owner is gone and remove it. A process removes its folder when another bundle replaces it and at
exit, and reaps the folders of dead owners whenever it unpacks a new one. What a worker holds
across jobs lives in a small module in ``sys.modules``, which Burla's per-job reset leaves alone.

The parent sends the request on stdin and reads length-prefixed pickles on a pipe of its own.
A watchdog stops the job when the round's deadline passes or the parent's end of the watch pipe
closes, by signalling this process, which is Burla's own cancel.
"""

from __future__ import annotations

import atexit
import fcntl
import importlib
import io
import os
import pickle
import select
import shutil
import signal
import struct
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import traceback
import types
from typing import IO, Any

BUNDLE = b""
BUNDLE_SHA256 = ""
_BUSY_RETRY_S = 15.0
_PREFIX = "poisson-prove-bundle-"
_LOCK = ".held"
_STATE = "_poisson_prove_bundle_held"
#: A folder with no lock file yet is being created, unless it has been sitting this long.
_STALE_S = 600.0
_FRESH = (
    "import pickle, sys\n"
    "paths, item = pickle.load(sys.stdin.buffer)\n"
    "sys.path[:] = paths\n"
    "module = __import__('poisson_prove.executor_modal', fromlist=['_container_batch'])\n"
    "sys.stdout.buffer.write(pickle.dumps(module._container_batch(item)))\n"
)


def _held() -> dict[str, Any]:
    """What this process holds: its bundle folder, that bundle's sha256 and the lock's file
    descriptor. Kept in ``sys.modules`` so it outlives the function objects of one job."""
    module = sys.modules.get(_STATE)
    if module is None:
        module = types.ModuleType(_STATE, "the bundle folder this worker process holds")
        vars(module).update(root=None, sha256=None, lock=None)
        sys.modules[_STATE] = module
        atexit.register(_release)
    return vars(module)


def _release() -> None:
    """At interpreter exit: remove the folder this process holds, if any."""
    held = _held()
    root, lock = held.get("root"), held.get("lock")
    held.update(root=None, sha256=None, lock=None)
    if root is not None:
        shutil.rmtree(root, ignore_errors=True)
    if lock is not None:
        os.close(lock)


def _reap(tmp: str, keep: str | None) -> None:
    """Remove every bundle folder in ``tmp`` whose owner is gone. Each folder's lock is held for
    its owner's life and released by the kernel when the process ends, however it ends; a lock
    that can be taken belongs to nobody. A folder with no lock file yet is being created and is
    left alone, unless it has been sitting for longer than a creation takes."""
    try:
        names = os.listdir(tmp)
    except OSError:
        return
    for name in names:
        folder = os.path.join(tmp, name)
        if not name.startswith(_PREFIX) or folder == keep or not os.path.isdir(folder):
            continue
        try:
            fd = os.open(os.path.join(folder, _LOCK), os.O_RDONLY)
        except FileNotFoundError:
            try:
                age = time.time() - os.stat(folder).st_mtime
            except OSError:
                continue
            if age > _STALE_S:
                shutil.rmtree(folder, ignore_errors=True)
            continue
        except OSError:
            continue
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                continue  # its owner is alive
            shutil.rmtree(folder, ignore_errors=True)
        finally:
            os.close(fd)


def _purge(keep: str) -> None:
    """Unload what another bundle left in this process: its folder off ``sys.path``, every module
    of every package it carried out of ``sys.modules``, and the folder itself, which this process
    owns. ``keep`` is the folder that replaces it."""
    held = _held()
    old = held.get("root")
    if old is None or old == keep:
        return
    names: set[str] = set()
    try:
        names.update(entry.split(".")[0] for entry in os.listdir(old) if not entry.startswith("."))
    except OSError:
        pass
    while old in sys.path:
        sys.path.remove(old)
    for name in list(sys.modules):
        if name.partition(".")[0] in names:
            del sys.modules[name]
    shutil.rmtree(old, ignore_errors=True)
    lock = held.get("lock")
    if lock is not None:
        os.close(lock)
    held.update(root=None, sha256=None, lock=None)


def _materialise(bundle: bytes, sha256: str) -> str:
    """The bundle's folder, unpacked once per process and first on ``sys.path``."""
    held = _held()
    root = held.get("root")
    if root is not None and held.get("sha256") == sha256 and os.path.isdir(root):
        if not sys.path or sys.path[0] != root:
            while root in sys.path:
                sys.path.remove(root)
            sys.path.insert(0, root)
        return str(root)
    tmp = tempfile.gettempdir()
    new = tempfile.mkdtemp(prefix=_PREFIX + sha256[:12] + "-", dir=tmp)
    lock = os.open(os.path.join(new, _LOCK), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz") as tar:
            tar.extractall(new, filter="data")
    except BaseException:
        os.close(lock)
        shutil.rmtree(new, ignore_errors=True)
        raise
    _purge(new)
    held.update(root=new, sha256=sha256, lock=lock)
    sys.path.insert(0, new)
    importlib.invalidate_caches()
    _reap(tmp, new)
    return new


def _bootstrap(
    k: int,
    jobs: list[Any],
    import_path: str,
    episode_timeout: float | None,
    capture: dict[str, Any] | None,
    chaos: dict[str, Any] | None,
) -> tuple[int, list[Any] | None, str | None]:
    root = _materialise(BUNDLE, BUNDLE_SHA256)
    item = (k, jobs, import_path, episode_timeout, capture, chaos)
    out: tuple[int, list[Any] | None, str | None]
    if capture is None and chaos is None:
        out = importlib.import_module("poisson_prove.executor_modal")._container_batch(item)
        return out
    done = subprocess.run(
        [sys.executable, "-I", "-S", "-c", _FRESH],
        input=pickle.dumps(([root, *[p for p in sys.path if p != root]], item)),
        capture_output=True,
    )
    if done.returncode != 0 or not done.stdout:
        return k, None, done.stderr.decode("utf-8", "replace")
    out = pickle.loads(done.stdout)
    return out


def _send(out: IO[bytes], message: object) -> None:
    data = pickle.dumps(message)
    out.write(struct.pack(">Q", len(data)) + data)
    out.flush()


def _watch(watch_fd: int, deadline: float, fired: threading.Event, why: list[str]) -> None:
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            why.append("stop")
            break
        ready, _, _ = select.select([watch_fd], [], [], min(remaining, 0.2))
        if ready and not os.read(watch_fd, 1):
            why.append("parent")
            break
    fired.set()
    os.kill(os.getpid(), signal.SIGINT)


def main() -> int:
    out: IO[bytes] = os.fdopen(int(sys.argv[1]), "wb")
    watch_fd = int(sys.argv[2])
    request = pickle.load(sys.stdin.buffer)
    try:
        import burla
        from burla._node import AllNodesBusy
    except ImportError as exc:
        _send(out, ("missing", str(exc)))
        return 3
    _send(out, ("version", burla.__version__))
    if burla.__version__ != request["pin"]:
        _send(out, ("done", "refused", "version", burla.__version__))
        return 3
    global BUNDLE, BUNDLE_SHA256
    BUNDLE, BUNDLE_SHA256 = request["bundle"], request["bundle_sha256"]
    fired = threading.Event()
    why: list[str] = []
    threading.Thread(
        target=_watch, args=(watch_fd, request["deadline"], fired, why), daemon=True
    ).start()
    call = request["call"]
    try:
        while True:
            try:
                results = burla.remote_parallel_map(
                    _bootstrap,
                    request["items"],
                    func_cpu=call["func_cpu"],
                    func_ram=call["func_ram"],
                    grow=False,
                    max_parallelism=call["max_parallelism"],
                    generator=True,
                    raise_errors=False,
                    spinner=False,
                )
                for value in results:
                    if isinstance(value, BaseException):
                        index = getattr(value, "burla_input_index", None)
                        _send(out, ("exception", type(value).__name__, str(value), index))
                    else:
                        _send(out, ("result", value))
                _send(out, ("done", "complete"))
                return 0
            except AllNodesBusy:
                if fired.wait(_BUSY_RETRY_S):
                    raise KeyboardInterrupt from None
    except KeyboardInterrupt:
        _send(out, ("done", "stopped" if why == ["stop"] else "canceled", "interrupted"))
    except BaseException as exc:
        name = type(exc).__name__
        if name == "JobCanceled":
            if fired.is_set():
                _send(out, ("done", "stopped" if why == ["stop"] else "canceled", str(exc)))
            else:
                _send(out, ("done", "canceled", str(exc)))
        elif name == "NodeDisconnected" or str(exc).startswith("Heartbeat process failed!"):
            _send(out, ("done", "interrupted", name, str(exc)))
        elif name in ("ClusterShutdown", "ClusterRestarted"):
            _send(out, ("done", "ended", name, str(exc)))
        else:
            _send(out, ("done", "refused", name, str(exc) or traceback.format_exc()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
