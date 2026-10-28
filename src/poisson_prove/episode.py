"""The Episode contract: the one data type user code returns to Prove."""

from __future__ import annotations

import math
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol


class EpisodeValidationError(ValueError):
    """Raised when an Episode violates one of its invariants."""


@dataclass(frozen=True, eq=True)
class Episode:
    """Frozen dataclass. Constructed by user code, consumed by the executor."""

    outcome: str
    t: float
    horizon: float
    confidence: float | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    __hash__ = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, str) or not self.outcome:
            raise EpisodeValidationError("outcome must be a non-empty str")
        if not _is_number(self.t):
            raise EpisodeValidationError("t must be a number")
        if not _is_number(self.horizon):
            raise EpisodeValidationError("horizon must be a number")
        t = float(self.t)
        horizon = float(self.horizon)
        if not t >= 0:
            raise EpisodeValidationError(f"t must be >= 0, got {t}")
        if not horizon > 0:
            raise EpisodeValidationError(f"horizon must be > 0, got {horizon}")
        if not t <= horizon:
            raise EpisodeValidationError(f"t must be <= horizon, got t={t} horizon={horizon}")
        confidence = self.confidence
        if confidence is not None:
            if not _is_number(confidence):
                raise EpisodeValidationError("confidence must be a number or None")
            confidence = float(confidence)
            if math.isnan(confidence) or not 0.0 <= confidence <= 1.0:
                raise EpisodeValidationError(f"confidence must be in [0, 1], got {confidence}")
        if not isinstance(self.meta, Mapping):
            raise EpisodeValidationError("meta must be a mapping")
        object.__setattr__(self, "t", t)
        object.__setattr__(self, "horizon", horizon)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "meta", MappingProxyType(deepcopy(dict(self.meta))))

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "t": self.t,
            "horizon": self.horizon,
            "confidence": self.confidence,
            "meta": deepcopy(dict(self.meta)),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Episode:
        meta = d.get("meta")
        return cls(
            outcome=d["outcome"],
            t=d["t"],
            horizon=d["horizon"],
            confidence=d.get("confidence"),
            meta={} if meta is None else meta,
        )


class Rollout(Protocol):
    """A rollout: a function ``(cfg, seed) -> Episode`` that runs one episode of the target for
    one condition and seed."""

    def __call__(self, cfg: Mapping[str, Any], seed: int) -> Episode: ...


def _is_number(x: object) -> bool:
    return isinstance(x, (int, float))
