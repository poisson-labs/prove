"""The cloud's own view of the nodes a cloud sweep launched, read with the AWS CLI.

The cluster software's status is not the cloud's: a launch still in flight when its stop answers
``off`` lands as a node it never lists, and a node it deleted keeps counting against the
account's vCPU quota while it shuts down. So after the software's stop Prove reads the instances
the software tags ``burla-cluster-node`` (1.8.4 ``main_service/providers/aws.py:103-112``) in the
sweep's region, keeps those launched in the sweep's window, terminates any still running, and
waits for them to end. The real-cloud check of 2026-11-12 met both.

Two calls only: ``aws ec2 describe-instances``, read-only, filtered by the tag, and
``aws ec2 terminate-instances`` of instances that read showed in the window. Like every process
Prove starts for the cloud backend, each runs in a session of its own with the CLI's limit.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime

from poisson_prove import _where_checks

TAG_FILTER = "Name=tag:burla-cluster-node,Values=true"
#: States of an instance that still runs, or could run again: Prove terminates these.
LIVE = ("pending", "running", "stopping", "stopped")
#: States the stop waits out: the live ones and ``shutting-down``, which the quota still counts.
WAITED = (*LIVE, "shutting-down")


@dataclass(frozen=True)
class Instance:
    id: str
    state: str
    launched: float


def _launched(text: str) -> float:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def read(region: str, since: float, until: float | None = None) -> list[Instance] | None:
    """The tagged instances in ``region`` launched from ``since`` to ``until`` (open when None),
    every state; None when the cloud could not be read.

    ``LaunchTime`` comes in whole seconds and the window is compared as it comes: a sweep's
    ``started_at`` precedes its first launch by the coordinator's start, the status and the
    settings, seconds on any cloud, so no launch of the sweep falls in the second it began."""
    aws = shutil.which("aws")
    if aws is None:
        return None
    out = _where_checks._aws(  # noqa: SLF001 - the one AWS CLI runner of the cloud backend
        aws,
        *("ec2", "describe-instances", "--region", region),
        *("--filters", TAG_FILTER, "--output", "json"),
    )
    if out is None:
        return None
    try:
        reservations = json.loads(out)["Reservations"]
        found = [
            Instance(str(i["InstanceId"]), str(i["State"]["Name"]), _launched(str(i["LaunchTime"])))
            for r in reservations
            for i in r["Instances"]
        ]
    except (ValueError, KeyError, TypeError):
        return None
    return [i for i in found if since <= i.launched and (until is None or i.launched <= until)]


def terminate(region: str, ids: list[str]) -> bool:
    """Terminate the named instances; whether the cloud took the request."""
    aws = shutil.which("aws")
    if aws is None or not ids:
        return False
    out = _where_checks._aws(  # noqa: SLF001
        aws,
        *("ec2", "terminate-instances", "--region", region),
        *("--instance-ids", *ids, "--output", "json"),
    )
    return out is not None
