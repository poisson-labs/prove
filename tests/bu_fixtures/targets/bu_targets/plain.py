"""A quick target whose every field is a function of the cell and the seed, so two backends that
run the same plan store the same rows (M3, P6)."""

from typing import Any

from proofload.episode import Episode

HORIZON = 10.0


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    fell = seed % 3 == 0
    return Episode(
        outcome="fell" if fell else "survived",
        t=float(1 + seed % 7) if fell else HORIZON,
        horizon=HORIZON,
        meta={"cell": cfg.get("cell"), "seed": seed},
    )
