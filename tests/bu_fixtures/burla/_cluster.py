"""The fake's cluster: the coordinator's state, its nodes, its settings and every management call.

Nothing here stands for a Burla module; ``_local_head.py``, ``_auth.py`` and ``_cli.py`` stand for
those of 1.8.4 and keep their state here. Everything lives under the fake's state folder
(``BU_FAKE_BURLA_STATE``):

- ``cluster.json``: ``{"settings": {...}, "nodes": [{"name", "status", "booted_at"}, ...]}``, the
  nodes as the cloud holds them. A node is listed while its status is ``BOOTING``, ``READY`` or
  ``RUNNING`` (``main_service/endpoints/management.py:222-245``); a deleted node is ``DELETED``.
- ``clusters/<project>/head.json``: the head's own record, as ``_local_head.py:810-822`` writes it.
- ``management.jsonl``: one line per management call the fake served, ``{"time", "route",
  "head", "argv", "body", "pid"}``, and one per head started or stopped (``"route": "head start"``,
  ``"head stop"``).
- ``cluster-script.json``, written by the test: the faults (below).

The script's keys:

- ``boot_s``: seconds each node takes from ``BOOTING`` to ``READY`` (default 0.05).
- ``start_fails_after``: ``{"nodes": k, "message": text}``: cluster start boots k nodes, then
  answers ``PROVIDER_ERROR`` with ``message`` (the nodes it booted stay up: no rollback,
  ``management.py:319-341``).
- ``start_hangs``: cluster start boots nothing and blocks until it is killed.
- ``status_fails``, ``settings_fails``, ``stop_fails``: that call answers an error envelope
  (``{"code", "message"}``), every time, or only the first ``"times"`` calls.
- ``stop_leaves``: cluster stop answers ok and leaves this many nodes listed.
- ``stop_s``: seconds cluster stop takes before it answers.
- ``preexisting``: nodes listed before Prove asks for any (``[{"status": "READY"}]``), or
  ``jobs``: an active job count the status reports.
- ``head_fails``: ``ensure_local_head`` raises ``LocalHeadError`` with this text.
- ``head_start_s``, ``head_fails_after_start``, ``head_stop_fails``: the head's own faults,
  described in ``_local_head.py``.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import signal
import sys
from collections.abc import Iterator
from typing import Any

from burla import _fake

LISTED = ("BOOTING", "READY", "RUNNING")
#: ``providers/catalog.py:39-44``: the vCPUs of each m7i size the fake knows.
VCPUS = {
    "m7i.large": 2, "m7i.xlarge": 4, "m7i.2xlarge": 8, "m7i.4xlarge": 16, "m7i.8xlarge": 32,
    "m7i.16xlarge": 64,
}


def path(*parts: str) -> str:
    return os.path.join(_fake.state_dir(), *parts)


def script() -> dict[str, Any]:
    try:
        with open(path("cluster-script.json"), encoding="utf-8") as fh:
            loaded = json.load(fh)
    except FileNotFoundError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


@contextlib.contextmanager
def locked() -> Iterator[dict[str, Any]]:
    """``cluster.json`` under the fake's lock, written back when the block ends."""
    with open(path("cluster.lock"), "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            try:
                with open(path("cluster.json"), encoding="utf-8") as fh:
                    state = json.load(fh)
            except FileNotFoundError:
                state = {"settings": {}, "nodes": []}
            yield state
            tmp = path(f"cluster.json.{os.getpid()}")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
            os.replace(tmp, path("cluster.json"))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def snapshot() -> dict[str, Any]:
    with locked() as state:
        return json.loads(json.dumps(state))


def listed(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [node for node in state.get("nodes", []) if node.get("status") in LISTED]


def record(route: str, **entry: Any) -> None:
    _fake.record(
        "management.jsonl",
        {"time": _fake.now(), "route": route, "pid": os.getpid(), **entry},
    )


def seed_preexisting() -> None:
    """The script's ``preexisting`` nodes, put in place once, before anything asks for status."""
    wanted = script().get("preexisting")
    if not wanted:
        return
    with locked() as state:
        if state.get("seeded"):
            return
        state["seeded"] = True
        for i, node in enumerate(wanted):
            state["nodes"].append(
                {"name": f"burla-node-pre{i:04d}", "status": node.get("status", "READY"),
                 "booted_at": _fake.now()}
            )


def status_document(state: dict[str, Any]) -> dict[str, Any]:
    """``management.py:222-267``."""
    nodes = listed(state)
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node["status"].lower()] = counts.get(node["status"].lower(), 0) + 1
    if any(n["status"] == "RUNNING" for n in nodes):
        status = "running"
    elif any(n["status"] == "READY" for n in nodes):
        status = "ready"
    elif nodes:
        status = "booting"
    else:
        status = "off"
    vcpus = VCPUS.get(str(state.get("settings", {}).get("machine_type")), 0)
    return {
        "status": status,
        "head_mode": "client_hosted",
        "desired_node_count": int(state.get("settings", {}).get("quantity", 0) or 0),
        "node_counts": counts,
        "vcpu_count": vcpus * len(nodes),
        "memory_bytes": vcpus * 4 * 1024**3 * len(nodes),
        "active_job_count": int(script().get("jobs", 0) or 0),
        "active_function_count": 0,
    }


def recorded_head(project: str) -> dict[str, Any] | None:
    try:
        with open(path("clusters", project, "head.json"), encoding="utf-8") as fh:
            loaded = json.load(fh)
    except (FileNotFoundError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A zombie child of this process still answers kill(0); reap it if it is ours.
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return True
    return done == 0


def head_for(url: str) -> dict[str, Any] | None:
    """The live head whose URL is ``url``, if any (the CLI's ``--head``)."""
    clusters = path("clusters")
    if not os.path.isdir(clusters):
        return None
    for project in sorted(os.listdir(clusters)):
        head = recorded_head(project)
        if head and head.get("url") == url and alive(head.get("head_pid")):
            return head
    return None


def interrupted_quietly() -> None:
    """A fake CLI process killed by a signal leaves as the real one would, without a traceback."""
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda signum, _frame: sys.exit(128 + signum))
