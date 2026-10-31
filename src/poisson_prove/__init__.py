"""Poisson Prove: find where an agent breaks, and prove a change fixed it.

Write a rollout, a function ``(cfg, seed) -> Episode``; record its steps with ``record`` and
``step``; sweep it with the ``poisson-prove`` command; compare two runs from Python with
``poisson_prove.compare``.
"""

from poisson_prove.episode import Episode as Episode
from poisson_prove.episode import EpisodeValidationError as EpisodeValidationError
from poisson_prove.episode import Rollout as Rollout
from poisson_prove.trace import record as record
from poisson_prove.trace import step as step

__version__ = "0.1.2"

__all__ = ["Episode", "EpisodeValidationError", "Rollout", "__version__", "record", "step"]
