"""A target that reports the interpreter it ran in: its process, its flags, its path, its
environment's variable names, where its own package was loaded from, and a value read from a data
file beside its own source, and its working directory (W2, W3, W5)."""

import json
import os
import sys
from pathlib import Path
from typing import Any

from poisson_prove.episode import Episode

DATA = Path(__file__).resolve().parent / "data" / "table.json"


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    table = json.loads(DATA.read_text(encoding="utf-8"))
    return Episode(
        outcome="survived",
        t=1.0,
        horizon=1.0,
        meta={
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "isolated": sys.flags.isolated,
            "no_site": sys.flags.no_site,
            "path": list(sys.path),
            "environ": sorted(os.environ),
            "file": __file__,
            "table": table["value"],
        },
    )
