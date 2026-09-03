"""Tiny CPU rollout shipped into the Modal image for the live parity test (M3 I19).

Same formula as the M3 oracles' deterministic rollout so the local and Modal runs can be
compared cell for cell.
"""

from typing import Any

from proofload.episode import Episode

HORIZON = 10.0


def rollout(cfg: Any, seed: int) -> Episode:
    fell = (seed + int(cfg["x"] * 10)) % 3 == 0
    return Episode(outcome="fell" if fell else "survived", t=3.0 if fell else HORIZON, horizon=HORIZON)
