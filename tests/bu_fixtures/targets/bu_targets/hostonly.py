"""A target that imports on the host and not in a worker: it needs a variable only the host's
environment carries (W6). A worker's environment holds none of the host's."""

import os
from typing import Any

from proofload.episode import Episode

if "BU_HOST_ONLY" not in os.environ:
    raise ImportError("bu_targets.hostonly imports only where BU_HOST_ONLY is set")


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    return Episode(outcome="survived", t=1.0, horizon=1.0, meta={})
