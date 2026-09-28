"""A target that returns its own version string (W4). The test copies this package to a temporary
folder and edits ``VERSION`` between two runs, so the two bundles differ only here."""

from typing import Any

from proofload.episode import Episode

VERSION = "one"


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    return Episode(outcome="survived", t=1.0, horizon=1.0, meta={"version": VERSION})
