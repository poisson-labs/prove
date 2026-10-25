"""The statistics a user may call, each stating what it was asked for.

``wilson`` is the Wilson score interval on one share at the level asked for, returned with that
level and the normal quantile it used, so no surface ever has to say "95%" without the level
having been recorded beside the interval (section 8.2). ``WILSON_LEVEL`` and ``POWER`` are the
two settings every surface reads when it computes, never copies: the level of the shares'
intervals and the power every detection limit is stated at.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from scipy import stats as _scipy_stats

from poisson_prove import survival as _survival

__all__ = ["WILSON_LEVEL", "WilsonInterval", "wilson"]

#: The level of every Wilson interval a surface shows unless it asks for another.
WILSON_LEVEL: float = 0.95

#: The power every detection limit is stated at: "caught 4 times in 5" (PF4.32). Read by each
#: surface when it computes, as ``WILSON_LEVEL`` is.
POWER: float = 0.8


@dataclass(frozen=True)
class WilsonInterval:
    """A Wilson score interval with the level it was built at and that level's two-sided
    normal quantile ``z``."""

    lo: float
    hi: float
    level: float
    z: float
    method: str = "wilson"


def wilson(k: int, n: int, *, level: float | None = None) -> WilsonInterval:
    """The Wilson score interval on ``k`` events in ``n`` trials at ``level`` (``WILSON_LEVEL``
    when not given). ``z`` is the quantile that leaves ``(1 - level) / 2`` in each tail; a level
    outside (0, 1) is refused with ``ValueError``."""
    chosen = WILSON_LEVEL if level is None else float(level)
    if not 0.0 < chosen < 1.0:
        raise ValueError(f"level must be between 0 and 1, got {level!r}")
    z = float(_scipy_stats.norm.isf((1.0 - chosen) / 2.0))
    lo, hi = _survival.wilson(k, n, z=z)
    return WilsonInterval(lo=lo, hi=hi, level=chosen, z=z)


def share(k: int, n: int) -> dict[str, Any]:
    """One arm's share of a condition as every saved result carries it: ``k / n`` with its
    Wilson interval at ``WILSON_LEVEL`` and that level beside it (PF4.1b)."""
    interval = wilson(k, n)
    return {
        "value": k / n,
        "lo": interval.lo,
        "hi": interval.hi,
        "level": interval.level,
        "method": interval.method,
    }


def times_in(power: float) -> str:
    """A power in words, ``0.8`` as "4 times in 5" (PF4.32): the simplest fraction within a
    twentieth of it."""
    from fractions import Fraction

    fraction = Fraction(power).limit_denominator(20)
    return f"{fraction.numerator} times in {fraction.denominator}"


def level_label(level: float) -> str:
    """A level as a percentage to at most three decimals: ``0.95`` as "95%", ``0.99722`` as
    "99.722%". The one function every label of a level comes from (PF4.1c, PF4.42)."""
    if math.isnan(level):
        raise ValueError("a level must be a number")
    text = f"{float(level) * 100.0:.3f}".rstrip("0").rstrip(".")
    return f"{text}%"
