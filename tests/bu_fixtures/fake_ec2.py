"""The fake cloud's instances: what EC2 holds for the fake cluster's nodes, shared by the fake
cluster software (``burla/_cluster.py``, ``burla/_cli.py``) and the fake AWS CLI
(``cloud_bin/aws.py``). Nothing here stands for a Burla module or for botocore.

The cloud and the cluster software keep one list, the nodes of ``cluster.json`` in the fake's
state folder, under its lock (``cluster.lock``). Each node is one instance tagged
``burla-cluster-node`` = ``true`` and ``burla-cluster-id`` = ``default`` (1.8.4
``main_service/providers/aws.py:103-112``; Prove sets no ``BURLA_CLUSTER_NAME``, so the id is
1.8.4's default, ``main_service/__init__.py:53``). A node's fields, beside the software's own
``name``, ``status`` and ``booted_at``:

- ``id``: the instance id, ``i-`` and 17 hex digits;
- ``launched_at``: the instance's ``LaunchTime``;
- ``ended_at``: when it was deleted by the software's stop or terminated by the AWS CLI;
- ``hidden``: true while ``describe-instances`` does not show it yet (a test reveals it).

How the cloud sees each status of the software's:

=================  ==============================================================
``BOOTING``        ``pending``
``READY``,         ``running``
``RUNNING``
``ORPHAN``         ``running``: launched while the software's stop answered ``off``,
                   so the software never lists it and nothing of its stops it
                   (the AWS check of 2026-11-12, case c)
``DELETED``,       ``shutting-down`` for the script's ``shutdown_s`` seconds after
``TERMINATED``     ``ended_at`` (default 0), then ``terminated``
``FAILED``         no instance: the launch was refused
=================  ==============================================================

``shutting-down`` instances still count against the account's vCPU quota, as on AWS (finding 2
of the same check). The real CLI gives ``LaunchTime`` in whole seconds; the fake keeps the
fraction, so two sweeps a few milliseconds apart stay apart, as two real ones a minute apart are.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

TAG = "burla-cluster-node"
CLUSTER_ID = "default"
#: ``providers/catalog.py:39-44``: the vCPUs of each m7i size the fake knows.
VCPUS = {
    "m7i.large": 2, "m7i.xlarge": 4, "m7i.2xlarge": 8, "m7i.4xlarge": 16, "m7i.8xlarge": 32,
    "m7i.16xlarge": 64,
}
#: EC2's state codes.
CODES = {"pending": 0, "running": 16, "shutting-down": 32, "terminated": 48, "stopping": 64,
         "stopped": 80}


def new_id() -> str:
    return "i-" + uuid.uuid4().hex[:17]


def script(state_dir: str) -> dict[str, Any]:
    try:
        with open(os.path.join(state_dir, "cluster-script.json"), encoding="utf-8") as fh:
            loaded = json.load(fh)
    except FileNotFoundError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


@contextlib.contextmanager
def locked(state_dir: str) -> Iterator[dict[str, Any]]:
    """``cluster.json`` under the fake's lock, written back when the block ends."""
    with open(os.path.join(state_dir, "cluster.lock"), "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            try:
                with open(os.path.join(state_dir, "cluster.json"), encoding="utf-8") as fh:
                    state = json.load(fh)
            except FileNotFoundError:
                state = {"settings": {}, "nodes": []}
            yield state
            tmp = os.path.join(state_dir, f"cluster.json.{os.getpid()}")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
            os.replace(tmp, os.path.join(state_dir, "cluster.json"))
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def cloud_state(node: dict[str, Any], now: float, shutdown_s: float) -> str | None:
    """The instance's state as EC2 reports it, or None when there is no instance (yet)."""
    status = node.get("status")
    if status == "FAILED" or node.get("hidden"):
        return None
    if status == "BOOTING":
        return "pending"
    if status in ("READY", "RUNNING", "ORPHAN"):
        return "running"
    if status in ("DELETED", "TERMINATED"):
        ended = float(node.get("ended_at") or 0.0)
        return "shutting-down" if now < ended + shutdown_s else "terminated"
    return None


def ensure_ids(state: dict[str, Any]) -> None:
    for node in state.get("nodes", []):
        node.setdefault("id", new_id())
        node.setdefault("launched_at", node.get("booted_at", time.time()))


def in_use_vcpus(state: dict[str, Any], now: float, shutdown_s: float, machine: str) -> int:
    """The vCPUs the account's quota counts: every instance pending, running or shutting down."""
    held = [n for n in state.get("nodes", [])
            if cloud_state(n, now, shutdown_s) in ("pending", "running", "shutting-down")]
    return sum(VCPUS.get(str(n.get("machine_type") or machine), 0) for n in held)


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, UTC).isoformat()


def describe(state_dir: str, region: str) -> dict[str, Any]:
    """``aws ec2 describe-instances --output json``: one reservation per instance, as RunInstances
    with ``MinCount = MaxCount = 1`` makes them."""
    shutdown_s = float(script(state_dir).get("shutdown_s", 0) or 0)
    now = time.time()
    reservations = []
    with locked(state_dir) as state:
        ensure_ids(state)
        machine = str(state.get("settings", {}).get("machine_type") or "m7i.2xlarge")
        for node in state["nodes"]:
            shown = cloud_state(node, now, shutdown_s)
            if shown is None:
                continue
            reservations.append({
                "ReservationId": "r-" + node["id"][2:],
                "OwnerId": "603052864933",
                "Instances": [{
                    "InstanceId": node["id"],
                    "InstanceType": node.get("machine_type") or machine,
                    "LaunchTime": _iso(float(node["launched_at"])),
                    "Placement": {"AvailabilityZone": f"{region}a"},
                    "State": {"Code": CODES[shown], "Name": shown},
                    "Tags": [{"Key": "Name", "Value": node["name"]},
                             {"Key": TAG, "Value": "true"},
                             {"Key": "burla-cluster-id", "Value": CLUSTER_ID}],
                }],
            })
    return {"Reservations": reservations}


def terminate(state_dir: str, ids: list[str]) -> dict[str, Any]:
    """``aws ec2 terminate-instances --instance-ids ...``: each named instance starts shutting
    down; an unknown id is EC2's ``InvalidInstanceID.NotFound``."""
    shutdown_s = float(script(state_dir).get("shutdown_s", 0) or 0)
    now = time.time()
    changes = []
    with locked(state_dir) as state:
        ensure_ids(state)
        by_id = {n["id"]: n for n in state["nodes"] if cloud_state(n, now, shutdown_s) is not None}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise KeyError(missing[0])
        for instance_id in ids:
            node = by_id[instance_id]
            before = cloud_state(node, now, shutdown_s) or "terminated"
            if before not in ("shutting-down", "terminated"):
                node["status"] = "TERMINATED"
                node["ended_at"] = now
            after = cloud_state(node, now, shutdown_s) or "terminated"
            changes.append({"InstanceId": instance_id,
                            "CurrentState": {"Code": CODES[after], "Name": after},
                            "PreviousState": {"Code": CODES[before], "Name": before}})
    return {"TerminatingInstances": changes}
