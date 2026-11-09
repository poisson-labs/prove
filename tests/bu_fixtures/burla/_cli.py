"""A fake of 1.8.4's management CLI (``burla/_cli.py``, ``_management_client.py``), over the fake's
cluster (``_cluster.py``) instead of a head's HTTP routes.

    python -m burla [--head URL] [--debug] cluster status|start|stop
    python -m burla [--head URL] settings show
    python -m burla [--head URL] settings update [--image I] [--machine-type T] [--quantity N]
                                                 [--region R] [--disk-gb N]
                                                 [--inactivity-timeout-seconds N] [--max-vcpus N]

What 1.8.4 does and the fake keeps:

- One JSON document on stdout, ``{"schema_version": 1, "ok": true, "command", "request_id",
  "data"}``, or ``{"schema_version": 1, "ok": false, "command", "request_id", "error": {"code",
  "message", "retryable", "details", "remediation"}}`` (``_cli.py:1023-1043``), with the exit code
  of ``ERROR_EXIT_CODES`` (``_management_client.py:14-29``).
- ``cluster status`` is ``GET /v1/management/cluster``; ``cluster start``, ``stop``, ``restart``
  ``POST /v1/management/cluster/<verb>``; ``settings show`` ``GET`` and ``settings update``
  ``PATCH /v1/management/settings`` with only the flags given (``_cli.py:337-398``, ``:792-858``,
  ``:1375-1398``). Each call is recorded in ``management.jsonl`` with its route and ``--head``.
- A ``--head`` no live head answers at is ``HEAD_UNREACHABLE``, exit 3.
- ``settings update`` checks each value against the catalogue and the ranges
  (``providers/catalog.py:526-531``): quantity 1-1000, disk 10-2000, inactivity 0-86400,
  max_vcpus 0-100000; a bad one is ``INVALID_ARGUMENT``, exit 2.
- ``cluster start`` is a no-op when the listed nodes already number ``quantity``; otherwise it
  boots the missing nodes one by one and answers when every one is ready, with no rollback when
  one fails (``management.py:319-341``). ``cluster stop`` deletes every listed node, booting ones
  included (``cluster_lifecycle.py:61-88``: ``READY``, ``BOOTING``, ``RUNNING``).
- ``PROVIDER_ERROR`` is exit 6 and its ``message`` the provider's text as the head passes it on.

Nothing here is one of Burla's routes Prove must not call (``POST /v1/settings``,
``/v1/cluster/import_history``, ``/v1/cluster/restart``, ``DELETE /v1/cluster/{node}``); the
fake records ``cluster restart`` like the rest so a test can see it was called.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from typing import Any

from burla import _cluster, _fake

ERROR_EXIT_CODES = {
    "INVALID_ARGUMENT": 2, "INVALID_CURSOR": 2, "CONTEXT_REQUIRED": 3, "HEAD_UNREACHABLE": 3,
    "HEAD_UPGRADE_REQUIRED": 3, "AUTH_REQUIRED": 3, "FORBIDDEN": 3, "NOT_FOUND": 4,
    "CLUSTER_BUSY": 5, "TIMEOUT": 6, "TRANSPORT_ERROR": 6, "PROVIDER_ERROR": 6, "JOB_FAILED": 7,
    "JOB_CANCELED": 8,
}
AWS_TYPES = ("m7i.large", "m7i.xlarge", "m7i.2xlarge", "m7i.4xlarge", "m7i.8xlarge",
             "m7i.16xlarge", "r7i.16xlarge", "p4d.24xlarge", "p4de.24xlarge", "p5.4xlarge",
             "p5.48xlarge")
REGION = re.compile(r"^[a-z]{2}(-[a-z]+)+-\d$")


class _Error(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


def _emit(document: dict[str, Any]) -> None:
    print(json.dumps(document, separators=(",", ":")), flush=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="burla", allow_abbrev=False)
    parser.add_argument("--head", metavar="URL")
    parser.add_argument("--debug", action="store_true")
    root = parser.add_subparsers(dest="root_command", required=True)
    cluster = root.add_parser("cluster", allow_abbrev=False)
    cluster.add_argument("cluster_command", choices=("status", "start", "stop", "restart", "watch"))
    settings = root.add_parser("settings", allow_abbrev=False)
    commands = settings.add_subparsers(dest="settings_command", required=True)
    commands.add_parser("show", allow_abbrev=False)
    update = commands.add_parser("update", allow_abbrev=False)
    update.add_argument("--image")
    update.add_argument("--machine-type")
    update.add_argument("--quantity", type=int)
    update.add_argument("--region")
    update.add_argument("--disk-gb", type=int)
    update.add_argument("--inactivity-timeout-seconds", type=int)
    update.add_argument("--max-vcpus", type=int)
    update.add_argument("--max-gpus", action="append")
    return parser


def _scripted_error(key: str) -> None:
    """The script's failure for ``key``; with ``"times": n`` only the first n calls fail."""
    failure = _cluster.script().get(key)
    if not failure:
        return
    times = failure.get("times")
    if times is not None:
        with _cluster.locked() as state:
            seen = state.setdefault("failed", {}).get(key, 0)
            state["failed"][key] = seen + 1
        if seen >= int(times):
            return
    raise _Error(str(failure.get("code", "PROVIDER_ERROR")), str(failure.get("message", "")),
                 retryable=True)


def _status() -> dict[str, Any]:
    _cluster.seed_preexisting()
    _scripted_error("status_fails")
    with _cluster.locked() as state:
        return _cluster.status_document(state)


def _update(args: argparse.Namespace) -> dict[str, Any]:
    body = {
        key: value
        for key, value in (
            ("image", args.image), ("machine_type", args.machine_type),
            ("quantity", args.quantity), ("region", args.region), ("disk_gb", args.disk_gb),
            ("inactivity_timeout_seconds", args.inactivity_timeout_seconds),
            ("max_vcpus", args.max_vcpus), ("max_gpus", args.max_gpus),
        )
        if value is not None
    }
    if not body:
        raise _Error("INVALID_ARGUMENT", "settings update requires at least one setting flag.")
    checks = [
        ("machine_type", lambda v: v in AWS_TYPES),
        ("region", lambda v: bool(REGION.match(v))),
        ("quantity", lambda v: 1 <= v <= 1000),
        ("disk_gb", lambda v: 10 <= v <= 2000),
        ("inactivity_timeout_seconds", lambda v: 0 <= v <= 86400),
        ("max_vcpus", lambda v: 0 <= v <= 100000),
    ]
    for key, ok in checks:
        if key in body and not ok(body[key]):
            raise _Error("INVALID_ARGUMENT", f"Invalid {key}: {body[key]!r}")
    _scripted_error("settings_fails")
    with _cluster.locked() as state:
        state["settings"].update(body)
        return dict(state["settings"])


def _start() -> dict[str, Any]:
    _cluster.seed_preexisting()
    script = _cluster.script()
    with _cluster.locked() as state:
        wanted = int(state["settings"].get("quantity", 0) or 0)
        have = len(_cluster.listed(state))
        if have >= wanted:
            return {"changed": False, "cluster": _cluster.status_document(state)}
        names = []
        for _ in range(wanted - have):
            name = f"burla-node-{uuid.uuid4().hex[:8]}"
            names.append(name)
            state["nodes"].append({"name": name, "status": "BOOTING", "booted_at": _fake.now()})
    if script.get("start_hangs"):
        while True:
            time.sleep(0.5)
    fails = script.get("start_fails_after")
    boot_s = float(script.get("boot_s", 0.05))
    for i, name in enumerate(names):
        if fails is not None and i >= int(fails.get("nodes", 0)):
            with _cluster.locked() as state:
                for node in state["nodes"]:
                    if node["name"] in names[i:]:
                        node["status"] = "FAILED"
            raise _Error("PROVIDER_ERROR", str(fails.get("message", "")), retryable=True)
        time.sleep(boot_s)
        with _cluster.locked() as state:
            for node in state["nodes"]:
                if node["name"] == name and node["status"] == "BOOTING":
                    node["status"] = "READY"
    with _cluster.locked() as state:
        return {"changed": True, "cluster": _cluster.status_document(state)}


def _stop() -> dict[str, Any]:
    script = _cluster.script()
    time.sleep(float(script.get("stop_s", 0)))
    _scripted_error("stop_fails")
    leave = int(script.get("stop_leaves", 0) or 0)
    with _cluster.locked() as state:
        listed = _cluster.listed(state)
        changed = bool(listed)
        for node in listed[leave:]:
            node["status"] = "DELETED"
        return {"changed": changed, "cluster": _cluster.status_document(state)}


ROUTES = {
    ("cluster", "status"): ("GET /v1/management/cluster", "cluster.status"),
    ("cluster", "start"): ("POST /v1/management/cluster/start", "cluster.start"),
    ("cluster", "stop"): ("POST /v1/management/cluster/stop", "cluster.stop"),
    ("cluster", "restart"): ("POST /v1/management/cluster/restart", "cluster.restart"),
    ("cluster", "watch"): ("GET /v1/management/cluster/watch", "cluster.watch"),
    ("settings", "show"): ("GET /v1/management/settings", "settings.show"),
    ("settings", "update"): ("PATCH /v1/management/settings", "settings.update"),
}


def main(argv: list[str] | None = None) -> int:
    _cluster.interrupted_quietly()
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(argv)
    verb = args.cluster_command if args.root_command == "cluster" else args.settings_command
    route, command = ROUTES[(args.root_command, verb)]
    request_id = uuid.uuid4().hex
    body = None
    if command == "settings.update":
        body = {k: v for k, v in vars(args).items()
                if k not in ("head", "debug", "root_command", "settings_command") and v is not None}
    _cluster.record(route, head=args.head, argv=argv, body=body)
    try:
        if not args.head or _cluster.head_for(args.head) is None:
            raise _Error("HEAD_UNREACHABLE", f"No head answers at {args.head}.", retryable=True)
        if command == "cluster.status":
            data = _status()
        elif command == "settings.update":
            data = _update(args)
        elif command == "settings.show":
            data = _cluster.snapshot()["settings"]
        elif command == "cluster.start":
            data = _start()
        elif command == "cluster.stop":
            data = _stop()
        else:
            raise _Error("INVALID_ARGUMENT", f"the fake does not serve {command}")
    except _Error as error:
        _emit({"schema_version": 1, "ok": False, "command": command, "request_id": request_id,
               "error": {"code": error.code, "message": error.message,
                         "retryable": error.retryable, "details": {}, "remediation": []}})
        _cluster.record(route + " answered", head=args.head, error=error.code)
        return ERROR_EXIT_CODES.get(error.code, 6)
    _emit({"schema_version": 1, "ok": True, "command": command, "request_id": request_id,
           "data": data})
    _cluster.record(route + " answered", head=args.head, error=None)
    return 0
