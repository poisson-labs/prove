"""A fake of 1.8.4's ``burla/_local_head.py``: the head (coordinator) process, started and stopped.

What Prove's coordinator launcher may call, each with 1.8.4's signature:

- ``ensure_local_head() -> str`` (``_local_head.py:287-289``): reuse the account's recorded head
  when it is alive, else start one, detached (``start_new_session``, ``:1014-1055``), record it in
  ``head.json`` before waiting for it (``:808-822``), wait until it is ready, return its URL. 1.8.4
  prefers port 5001 and takes another when 5001 is held (``:63``, ``:211-225``); the fake takes
  5001 unless a live head holds it, and binds nothing.
- ``start_local_head_for_job() -> (url, pid)`` (``:292-297``).
- ``running_head_url() -> str | None`` (``:300-328``): the recorded head's URL when it is alive.
- ``_head_state_dir(project_id, namespace="") -> Path`` (``:78-87``).
- ``_pid_alive(pid) -> bool`` (``:242-248``).
- ``_recorded_head_pid(head_state_path) -> int | None`` (``:546-549``).
- ``_terminate_pid(pid)`` (``:469-480``): SIGTERM, 5 s, SIGKILL.
- ``_stop_recorded_head(head_state_path, head_pid)`` (``:552-559``): stop the head the record names
  if it is still the one named, and clear the record. It deletes no node (``main_service/
  __init__.py:497-508``: the head's own teardown deletes none).

The head is ``tests/bu_fixtures/burla_head.py``, a process that serves nothing and records its
environment and every signal it receives. ``ensure_local_head`` also records, as ``head start``
in ``management.jsonl``: its own environment's Burla and AWS variables, and a copy of every
ownership record Prove holds and of the ledger named in the state folder's ``ledger.path``, as
they were when the head was asked for (L7, L13).
"""

from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from burla import _cluster, _fake
from burla._auth import STATE_ROOT, LocalHeadError, detect_cloud

PREFERRED_HEAD_PORT = 5001
_HEAD = Path(__file__).resolve().parents[1] / "burla_head.py"
_ENV_KEYS = ("BURLA_CLOUD", "BURLA_PRIVATE", "DISABLE_BURLA_TELEMETRY", "AWS_REGION",
             "AWS_DEFAULT_REGION", "BURLA_CLUSTER_DASHBOARD_URL", "DISABLE_BURLA_KEEP_AWAKE")


def _head_state_dir(project_id: str, namespace: str = "") -> Path:
    directory = STATE_ROOT / project_id
    directory.mkdir(parents=True, exist_ok=True)
    if namespace:
        directory = directory / f"cluster-{namespace}"
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def _pid_alive(pid: int | None) -> bool:
    return _cluster.alive(pid)


def _recorded_head_pid(head_state_path: Path) -> int | None:
    if not Path(head_state_path).exists():
        return None
    return json.loads(Path(head_state_path).read_text()).get("head_pid")


def _terminate_pid(pid: int | None) -> None:
    if pid is None or not _pid_alive(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    until = time.time() + 5
    while time.time() < until and _pid_alive(pid):
        time.sleep(0.02)
    if _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _clear_process_state(head_state_path: Path, head_pid: int, frpc_pid: int | None) -> None:
    path = Path(head_state_path)
    if not path.exists():
        return
    state = json.loads(path.read_text())
    if state.get("head_pid") == head_pid:
        path.unlink()


def _stop_recorded_head(head_state_path: Path, head_pid: int) -> None:
    head_state = json.loads(Path(head_state_path).read_text())
    if head_state.get("head_pid") != head_pid:
        return
    _cluster.record("head stop", pid_stopped=head_pid, head=head_state.get("url"))
    _terminate_pid(head_pid)
    _clear_process_state(Path(head_state_path), head_pid, head_state.get("frpc_pid"))


def running_head_url() -> str | None:
    try:
        _, project_id, _ = detect_cloud()
    except Exception:  # noqa: BLE001 - as 1.8.4
        return None
    head = _cluster.recorded_head(project_id)
    if head and _pid_alive(head.get("head_pid")):
        return str(head.get("url"))
    return None


def _snapshots() -> dict[str, object]:
    out: dict[str, object] = {}
    state_home = os.environ.get("XDG_STATE_HOME", "")
    for path in sorted(glob.glob(os.path.join(state_home, "poisson-prove", "cloud", "*.json"))):
        try:
            out[os.path.basename(path)] = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            out[os.path.basename(path)] = f"unreadable: {exc}"
    try:
        ledger = Path(_cluster.path("ledger.path")).read_text(encoding="utf-8").strip()
        out["ledger"] = Path(ledger).read_text(encoding="utf-8") if os.path.exists(ledger) else ""
    except FileNotFoundError:
        pass
    return out


def _port() -> int:
    held = set()
    if STATE_ROOT.is_dir():
        for project in os.listdir(STATE_ROOT):
            head = _cluster.recorded_head(project)
            if head and _pid_alive(head.get("head_pid")):
                held.add(int(str(head["url"]).rsplit(":", 1)[-1]))
    port = PREFERRED_HEAD_PORT
    while port in held:
        port += 1
    return port


def ensure_local_head() -> str:
    _cluster.record(
        "head start",
        env={key: os.environ.get(key) for key in _ENV_KEYS if key in os.environ},
        snapshots=_snapshots(),
    )
    failure = _cluster.script().get("head_fails")
    if failure:
        raise LocalHeadError(str(failure))
    _, project_id, _ = detect_cloud()
    state_dir = _head_state_dir(project_id)
    head_state_path = state_dir / "head.json"
    recorded = _cluster.recorded_head(project_id)
    if recorded and _pid_alive(recorded.get("head_pid")):
        return str(recorded["url"])
    url = f"http://127.0.0.1:{_port()}"
    with open(state_dir / "head.log", "ab") as log:
        process = subprocess.Popen(
            [sys.executable, "-I", str(_HEAD), _fake.state_dir(), project_id],
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=dict(os.environ),
        )
    head_state = {
        "url": url,
        "head_pid": process.pid,
        "subdomain": f"fake-{process.pid}",
        "tls_port": 0,
        "project_id": project_id,
        "cloud": "aws",
        "logs_to_file": True,
        "private": os.environ.get("BURLA_PRIVATE", "").lower() == "true",
        "open_to_network": False,
        "cluster_name": "",
    }
    head_state_path.write_text(json.dumps(head_state))
    ready = Path(_cluster.path(f"head-{process.pid}.ready"))
    until = time.time() + 90  # _local_head.py's readiness wait
    while not ready.exists():
        if process.poll() is not None or time.time() > until:
            raise LocalHeadError("HEAD_UNREACHABLE: the head did not become ready")
        time.sleep(0.01)
    return url


def start_local_head_for_job() -> tuple[str, int]:
    url = ensure_local_head()
    _, project_id, _ = detect_cloud()
    head = _cluster.recorded_head(project_id) or {}
    return url, int(head["head_pid"])
