"""Tiny CPU rollout shipped into the Modal image for the live parity test (M3 I19).

Same formula as the M3 frozen tests' deterministic rollout so the local and Modal runs can be
compared cell for cell.
"""

import os
from typing import Any

from poisson_prove.episode import Episode

HORIZON = 10.0


def rollout(cfg: Any, seed: int) -> Episode:
    fell = (seed + int(cfg["x"] * 10)) % 3 == 0
    return Episode(outcome="fell" if fell else "survived", t=3.0 if fell else HORIZON, horizon=HORIZON)


def rollout_secret(cfg: Any, seed: int) -> Episode:
    """L15: reports whether the named Modal secret reached the container's environment."""
    present = "PROOFLOAD_LIVE_SECRET" in os.environ
    return Episode(outcome="present" if present else "absent", t=1.0, horizon=1.0)
