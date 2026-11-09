"""Targets for the cloud backend's lifecycle tests (C3, C4). Each reads only its cell and seed.

- ``quick``: an outcome at once.
- ``slow``: an outcome after ``cfg["wait_s"]`` seconds (default 0.3), so a job runs long enough
  for the record's heartbeat or the spend stop to be seen.
- ``raises``: no outcome, ever: every rollout raises.
- ``hold``: in the cell ``"hold"``, writes the file ``cfg["marker"]`` names and then sleeps, so a
  test knows the job is running before it signals; in any other cell, an outcome at once. Job 0
  (the first cell's first replicate, which the plan rehearses twice on this machine) is never in
  ``"hold"`` when the spec lists that cell last.
"""

import os
import time
from typing import Any

from poisson_prove.episode import Episode

HORIZON = 10.0


def _episode(cfg: dict[str, Any], seed: int) -> Episode:
    fell = seed % 3 == 0
    return Episode(
        outcome="fell" if fell else "survived",
        t=float(1 + seed % 7) if fell else HORIZON,
        horizon=HORIZON,
        meta={"cell": cfg.get("cell"), "seed": seed},
    )


def quick(cfg: dict[str, Any], seed: int) -> Episode:
    return _episode(cfg, seed)


def slow(cfg: dict[str, Any], seed: int) -> Episode:
    time.sleep(float(cfg.get("wait_s", 0.3)))
    return _episode(cfg, seed)


def raises(cfg: dict[str, Any], seed: int) -> Episode:
    raise ValueError("the wrapper's client is not configured")


def hold(cfg: dict[str, Any], seed: int) -> Episode:
    if cfg.get("cell") == "hold":
        marker = str(cfg["marker"])
        with open(marker + f".{os.getpid()}.{seed}", "w", encoding="utf-8") as fh:
            fh.write(str(seed))
        os.replace(marker + f".{os.getpid()}.{seed}", marker)
        time.sleep(300)
    return _episode(cfg, seed)
