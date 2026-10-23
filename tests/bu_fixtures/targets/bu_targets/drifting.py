"""A target whose episode depends on this machine's environment, so the worker's view of job 0
differs from this process's (P4)."""

import os
from typing import Any

from poisson_prove.episode import Episode


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    marker = os.environ.get("BU_DRIFT_MARKER", "absent-in-the-worker-view")
    return Episode(outcome="survived", t=1.0, horizon=1.0, meta={"marker": marker})
