"""A target that imports another local package, ``bu_helper`` (P3)."""

from typing import Any

import bu_helper

from poisson_prove.episode import Episode


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    return Episode(outcome="survived", t=1.0, horizon=1.0, meta={"word": bu_helper.WORD})
