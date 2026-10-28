"""The statistics a user may call, each stating what it was asked for.

These are the functions Prove's comparisons are computed with: the same numbers, given the same
counts or times. ``wilson`` returns its interval with the level it was built at and the normal
quantile it used. ``WILSON_LEVEL`` and ``POWER`` are the two settings every surface reads when it
computes, never copies: the level of the shares' intervals, and the power every detection limit is
stated at.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import stats as _scipy_stats

from poisson_prove import _look
from poisson_prove import survival as _survival
from poisson_prove.survival import CIFCurve, KMCurve

__all__ = [
    "CIFCurve",
    "KMCurve",
    "POWER",
    "WILSON_LEVEL",
    "WilsonInterval",
    "aalen_johansen",
    "bh",
    "fisher_test",
    "holm",
    "interval_rd",
    "interval_rd_paired",
    "kaplan_meier",
    "logrank_test",
    "mcnemar_test",
    "mde_two_proportion",
    "wilson",
]

#: The level of every Wilson interval a surface shows unless it asks for another.
WILSON_LEVEL: float = 0.95

#: The power every detection limit is stated at: "caught 4 times in 5". Read by each surface
#: when it computes, as ``WILSON_LEVEL`` is.
POWER: float = 0.8

# The functions the comparisons are computed with, given here under their public names.
from poisson_prove.diff import (  # noqa: E402
    _fisher,
    _logrank,
    bh,
    holm,
    interval_rd,
    interval_rd_paired,
    mde_two_proportion,
)
from poisson_prove.survival import aalen_johansen, kaplan_meier  # noqa: E402


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
    """The Wilson score interval on ``k`` events in ``n`` trials at the level asked for
    (``WILSON_LEVEL``, 0.95, by default), with that level and its ``z``: the quantile that
    leaves ``(1 - level) / 2`` in each tail. A level outside (0, 1) is refused with
    ``ValueError``.

    >>> round(wilson(3, 20).hi, 3)
    0.36
    """
    chosen = WILSON_LEVEL if level is None else float(level)
    if not 0.0 < chosen < 1.0:
        raise ValueError(f"level must be between 0 and 1, got {level!r}")
    z = float(_scipy_stats.norm.isf((1.0 - chosen) / 2.0))
    lo, hi = _survival.wilson(k, n, z=z)
    return WilsonInterval(lo=lo, hi=hi, level=chosen, z=z)


def fisher_test(events_a: int, n_a: int, events_b: int, n_b: int) -> tuple[float, float]:
    """Fisher's exact test on two separate samples, ``events_a`` of ``n_a`` against
    ``events_b`` of ``n_b``: the odds ratio and the two-sided p-value."""
    return _fisher(int(events_a), int(n_a), int(events_b), int(n_b))


def mcnemar_test(only_a: int, only_b: int) -> tuple[float, float]:
    """The paired test on matched pairs (McNemar's, exact): ``only_a`` pairs had the event in the
    first run only and ``only_b`` in the second only. The difference ``only_a - only_b`` and the
    two-sided p-value, 1 when no pair differs."""
    if only_a < 0 or only_b < 0:
        raise ValueError(f"the counts must not be negative, got {only_a} and {only_b}")
    if only_a + only_b == 0:
        return 0.0, 1.0
    p = float(_scipy_stats.binomtest(min(only_a, only_b), only_a + only_b, 0.5).pvalue)
    return float(only_a - only_b), p


def logrank_test(
    t_a: NDArray[Any], observed_a: NDArray[Any], t_b: NDArray[Any], observed_b: NDArray[Any]
) -> tuple[float, float]:
    """The two-sample log-rank test of the cause-specific hazard: times and whether each ended
    in the event, for each run. The chi-square statistic with one degree of freedom and its
    p-value."""
    return _logrank(
        np.asarray(t_a, dtype=np.float64),
        np.asarray(observed_a, dtype=bool),
        np.asarray(t_b, dtype=np.float64),
        np.asarray(observed_b, dtype=bool),
    )


def share(k: int, n: int) -> dict[str, Any]:
    """One arm's share of a condition as every saved result carries it: ``k / n`` with its
    Wilson interval at ``WILSON_LEVEL`` and that level beside it."""
    interval = wilson(k, n)
    return {
        "value": k / n,
        "lo": interval.lo,
        "hi": interval.hi,
        "level": interval.level,
        "method": interval.method,
    }


def times_in(power: float) -> str:
    """A power in words, ``0.8`` as "4 times in 5"."""
    return _look.times_in(power)


def level_label(level: float) -> str:
    """A level as a percentage to at most three decimals."""
    if math.isnan(level):
        raise ValueError("a level must be a number")
    return _look.level_label(level)
