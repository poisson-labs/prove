"""The detection limits: one function family for every limit Prove prints.

A condition's limit answers one question: if this condition alone had changed, from where it was,
how large a change would the flag Prove raises catch at the stated power? The flag is the row's own
test p below ``q / M`` (Benjamini-Hochberg flags any p below that whatever the other rows do, and
Holm counts it) and the change in its direction, so each limit here is computed for the test the
comparison used, at the level it is handed, by that test's exact power where one exists (Fisher,
the paired test) and by expected moments for the log-rank test.

Every limit is searched on a grid inside its room and is the smallest grid value whose power
reaches the target **and stays there** at every larger grid value (exact power is not monotone for
small samples); the grid never passes the room. A direction with no limit is null with one of four
notes: ``no room``, ``none detectable``, ``cannot be flagged``, ``no matched pairs``.

The comparison's rows (``diff``), the power gate at sweep time (``executor``), the single-run
report's design limit and the fault-line groups (``tree``) all read their numbers here.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import special, stats

#: The step of every grid of changes in a share or an incidence.
GRID_STEP = 1e-4
#: The step of the log-rank search over the log of the hazard ratio.
LOG_THETA_STEP = 1e-3
#: The hazard ratio the log-rank rise's grid runs to: the room is the incidence there.
THETA_MAX = 1e6

NO_ROOM = "no room"
NONE_DETECTABLE = "none detectable"
CANNOT_BE_FLAGGED = "cannot be flagged"
NO_MATCHED_PAIRS = "no matched pairs"
#: The closed list a null limit's note is taken from.
NOTES = (NO_ROOM, NONE_DETECTABLE, CANNOT_BE_FLAGGED, NO_MATCHED_PAIRS)

#: scipy's ``fisher_exact`` counts a table as extreme as the observed one when its probability is
#: within a factor ``1 + 1e-14`` of it, which reads exact ties between tables as ties. The table
#: below computes probabilities from log-factorials, good to about 1e-13 relative, so it reads a
#: tie within ``1 + 1e-9``: far above that error and far below any gap between unequal tables.
_FISHER_GAMMA = 1.0 + 1e-9
#: Grid points per block when a power is evaluated over a grid, to bound the memory a large arm
#: takes (5,000 runs a side over 10,000 grid points would be a 400 MB matrix at once).
_BLOCK = 1 << 20


@dataclass(frozen=True)
class Limit:
    """One direction's limit: a number, or None with the note saying why. ``hazard_ratio`` is the
    log-rank hazard ratio at the limit, when there is one."""

    value: float | None
    note: str | None
    hazard_ratio: float | None = None


@dataclass(frozen=True)
class Limits:
    """Both directions of one row, with what they were computed from."""

    rise: Limit
    fall: Limit
    p_min: float
    test: str
    basis: str
    room_rise: float
    room_fall: float

    def one_number(self) -> tuple[float | None, str | None]:
        """The row's one ``mde`` and ``mde_note``: the larger limit when both are numbers; the
        number when the other direction has no room; else None, with the note of the direction
        that made it null (the rise's when both did; a direction with no room never does)."""
        rise, fall = self.rise, self.fall
        if rise.value is not None and fall.value is not None:
            return max(rise.value, fall.value), None
        if rise.value is not None and fall.note == NO_ROOM:
            return rise.value, None
        if fall.value is not None and rise.note == NO_ROOM:
            return fall.value, None
        if rise.value is None and rise.note != NO_ROOM:
            return None, rise.note
        if fall.value is None and fall.note != NO_ROOM:
            return None, fall.note
        return None, rise.note

    def could_tell(self, threshold: float) -> tuple[bool, float | None]:
        """Whether the row could tell a change of ``threshold``: with ``T' = min(threshold, the
        larger room)``, every direction whose room is at least ``T'`` must have a limit at or below
        ``T'``. Returns whether the row could tell, and the largest limit the question read (the
        verdict limit's candidate)."""
        asked = min(threshold, max(self.room_rise, self.room_fall))
        largest: float | None = None
        for limit, room in ((self.rise, self.room_rise), (self.fall, self.room_fall)):
            if room < asked - 1e-12:
                continue
            if limit.value is None or limit.value > asked + 1e-12:
                return False, None
            largest = limit.value if largest is None else max(largest, limit.value)
        return True, largest


# ---------- the search ----------


def _grid(room: float) -> NDArray[np.float64]:
    """The multiples of the grid step from one step up to the room, never past it."""
    steps = int(math.floor(room / GRID_STEP + 1e-9))
    grid = np.arange(1, steps + 1, dtype=np.float64) * GRID_STEP
    return grid[grid <= room + 1e-15]


def _first_staying(power: NDArray[np.float64], target: float) -> int | None:
    """The first index from which the power is at or above the target at every later index."""
    if power.size == 0:
        return None
    floor_after = np.minimum.accumulate(power[::-1])[::-1]
    hits = np.nonzero(floor_after >= target)[0]
    return int(hits[0]) if hits.size else None


def _search(power: NDArray[np.float64], grid: NDArray[np.float64], target: float) -> Limit:
    index = _first_staying(power, target)
    if index is None:
        return Limit(None, NONE_DETECTABLE)
    return Limit(float(grid[index]), None)


# ---------- Fisher's exact test ----------


@lru_cache(maxsize=16)
def _fisher_table(n_a: int, n_b: int) -> NDArray[np.float64]:
    """Fisher's two-sided p for every table ``(x_a, x_b)`` of these arm sizes, by scipy's own
    rule: under the hypergeometric of the margins, the sum over every table no more probable
    than the observed one (``fisher_exact``, the test ``diff`` runs).

    The hypergeometric is computed from log-factorials, one vector per total of events, rather
    than through ``scipy.stats.hypergeom`` (15 ms a call at 5,000 a side, 10,001 calls). With equal
    arms a table and its mirror sum the same two terms, so their probabilities are equal to the
    bit and the tie rule reads them as scipy does."""
    table = np.empty((n_a + 1, n_b + 1), dtype=np.float64)
    total = n_a + n_b
    log_factorial = special.gammaln(np.arange(total + 1) + 1.0)
    for k in range(total + 1):
        xb = np.arange(max(0, k - n_a), min(k, n_b) + 1)
        xa = k - xb
        log_pmf = (log_factorial[n_b] - log_factorial[xb] - log_factorial[n_b - xb]) + (
            log_factorial[n_a] - log_factorial[xa] - log_factorial[n_a - xa]
        )
        log_pmf -= log_factorial[total] - log_factorial[k] - log_factorial[total - k]
        pmf = np.exp(log_pmf)
        ordered = np.sort(pmf)
        cumulative = np.cumsum(ordered)
        at_most = np.searchsorted(ordered, pmf * _FISHER_GAMMA, side="right")
        table[k - xb, xb] = np.minimum(1.0, cumulative[at_most - 1])
    return table


def fisher_p(events_a: int, n_a: int, events_b: int, n_b: int) -> float:
    """Fisher's two-sided p of one table, read from the table of its arm sizes."""
    return float(_fisher_table(n_a, n_b)[events_a, events_b])


def fisher_p_min(n_a: int, n_b: int) -> float:
    """The smallest p Fisher's test can give these arm sizes: every run of one arm with the
    event and none of the other."""
    table = _fisher_table(n_a, n_b)
    return float(min(table[n_a, 0], table[0, n_b]))


@lru_cache(maxsize=32)
def _fisher_region(n_a: int, n_b: int, level: float, rise: bool) -> NDArray[np.bool_]:
    """Every table whose p is below the level and whose B share moved the given way."""
    xa = np.arange(n_a + 1)[:, None]
    xb = np.arange(n_b + 1)[None, :]
    moved = (xb * n_a > xa * n_b) if rise else (xb * n_a < xa * n_b)
    return (_fisher_table(n_a, n_b) < level) & moved


def _fisher_weights(
    p_a: float, n_a: int, n_b: int, level: float, rise: bool
) -> NDArray[np.float64]:
    """For each count of events in B, the chance over A ~ Binomial(n_a, p_a) that the table is in
    the rejection region; summed in blocks of A's counts so a large arm stays small in memory."""
    region = _fisher_region(n_a, n_b, level, rise)
    pmf_a = stats.binom.pmf(np.arange(n_a + 1), n_a, p_a)
    weights = np.zeros(n_b + 1, dtype=np.float64)
    block = max(1, _BLOCK // (n_b + 1))
    for start in range(0, n_a + 1, block):
        weights += pmf_a[start : start + block] @ region[start : start + block]
    return weights


def _binomial_mean(
    weights: NDArray[np.float64], n: int, rates: NDArray[np.float64]
) -> NDArray[np.float64]:
    """``E[weights[X]]`` for ``X ~ Binomial(n, rate)`` at each rate, in blocks of the rates."""
    counts = np.arange(n + 1)
    out = np.empty(rates.size, dtype=np.float64)
    block = max(1, _BLOCK // (n + 1))
    for start in range(0, rates.size, block):
        chunk = np.clip(rates[start : start + block], 0.0, 1.0)
        out[start : start + block] = stats.binom.pmf(counts[None, :], n, chunk[:, None]) @ weights
    return out


def fisher_power(
    p_a: float, n_a: int, n_b: int, level: float, changes: NDArray[np.float64], rise: bool
) -> NDArray[np.float64]:
    """With A ~ Binomial(n_a, p_a) and B ~ Binomial(n_b, p_a +- change), the chance that
    Fisher's p is below the level and B's share moved the way of the change."""
    weights = _fisher_weights(p_a, n_a, n_b, level, rise)
    rates = p_a + changes if rise else p_a - changes
    return _binomial_mean(weights, n_b, np.asarray(rates, dtype=np.float64))


def _fisher_search(
    p_a: float,
    n_a: int,
    n_b: int,
    level: float,
    grid: NDArray[np.float64],
    rise: bool,
    target: float,
) -> Limit:
    """The Fisher limit on a grid. When the rejection region only grows as B's count moves the
    way of the change, the power is monotone in the change (a binomial mean of a monotone
    function is monotone in its rate), so the first grid point that reaches the target stays and
    a bisection finds it; otherwise every grid point is evaluated."""
    weights = _fisher_weights(p_a, n_a, n_b, level, rise)
    steps = np.diff(weights) if rise else -np.diff(weights)
    if not np.all(steps >= -1e-15):
        rates = p_a + grid if rise else p_a - grid
        return _search(_binomial_mean(weights, n_b, rates), grid, target)

    def power_at(index: int) -> float:
        rate = p_a + grid[index] if rise else p_a - grid[index]
        return float(_binomial_mean(weights, n_b, np.array([rate]))[0])

    if grid.size == 0 or power_at(grid.size - 1) < target:
        return Limit(None, NONE_DETECTABLE)
    lo, hi = 0, grid.size - 1
    while lo < hi:
        middle = (lo + hi) // 2
        if power_at(middle) >= target:
            hi = middle
        else:
            lo = middle + 1
    return Limit(float(grid[lo]), None)


@lru_cache(maxsize=1 << 16)
def fisher_limits(events_a: int, n_a: int, n_b: int, level: float, power: float) -> Limits:
    """A condition's limits under Fisher's test, from A's ``events_a`` of ``n_a`` against an arm B
    of ``n_b``, at the level the flag applies to the row."""
    p_a = events_a / n_a
    p_min = fisher_p_min(n_a, n_b)
    found = []
    for rise, room in ((True, 1.0 - p_a), (False, p_a)):
        grid = _grid(room)
        if grid.size == 0:
            found.append(Limit(None, NO_ROOM))
        elif not p_min < level:
            found.append(Limit(None, CANNOT_BE_FLAGGED))
        else:
            found.append(_fisher_search(p_a, n_a, n_b, level, grid, rise, power))
    return Limits(found[0], found[1], p_min, "fisher", "test", 1.0 - p_a, p_a)


# ---------- the paired test ----------


def paired_p(only_a: int, only_b: int) -> float:
    """The exact paired p ``diff`` computes: a two-sided binomial test of the smaller discordant
    count at one half (twice its lower tail, at most 1)."""
    discordant = only_a + only_b
    if discordant == 0:
        return 1.0
    return float(min(1.0, 2.0 * stats.binom.cdf(min(only_a, only_b), discordant, 0.5)))


def paired_p_min(pairs: int) -> float:
    """The smallest paired p over ``pairs`` matched pairs: every pair discordant one way."""
    return float(min(1.0, 2.0 * 0.5**pairs)) if pairs > 0 else 1.0


@lru_cache(maxsize=256)
def _paired_critical(pairs: int, level: float) -> NDArray[np.int64]:
    """For each count of discordant pairs ``d``, the smallest larger count whose paired p is
    below the level (``d + 1`` when none is)."""
    critical = np.empty(pairs + 1, dtype=np.int64)
    for d in range(pairs + 1):
        larger = np.arange((d // 2) + 1, d + 1)
        p = np.minimum(1.0, 2.0 * stats.binom.cdf(d - larger, d, 0.5))
        hits = np.nonzero(p < level)[0]
        critical[d] = int(larger[hits[0]]) if hits.size else d + 1
    return critical


def paired_power(
    p_a: float, pairs: int, level: float, changes: NDArray[np.float64], rise: bool
) -> NDArray[np.float64]:
    """The two arms independent within a pair at A's share, B's moved by the change; the
    chance that the paired p is below the level and the larger discordant count is the
    direction's. The pairs' multinomial is enumerated through the discordant total."""
    changes = np.asarray(changes, dtype=np.float64)
    if rise:
        only_b = (1.0 - p_a) * (p_a + changes)
        only_a = p_a * (1.0 - p_a - changes)
    else:
        only_b = (1.0 - p_a) * (p_a - changes)
        only_a = p_a * (1.0 - p_a + changes)
    only_a, only_b = np.clip(only_a, 0.0, 1.0), np.clip(only_b, 0.0, 1.0)
    discordant = np.clip(only_a + only_b, 0.0, 1.0)
    toward = only_b if rise else only_a
    share = np.divide(toward, discordant, out=np.zeros_like(discordant), where=discordant > 0)
    critical = _paired_critical(pairs, level)
    totals = np.arange(pairs + 1)
    out = np.empty(changes.size, dtype=np.float64)
    block = max(1, _BLOCK // (pairs + 1))
    for start in range(0, changes.size, block):
        stop = start + block
        p_total = stats.binom.pmf(totals[None, :], pairs, discordant[start:stop, None])
        p_tail = stats.binom.sf(critical[None, :] - 1, totals[None, :], share[start:stop, None])
        p_tail[:, critical > totals] = 0.0
        out[start:stop] = np.sum(p_total * p_tail, axis=1)
    return out


@lru_cache(maxsize=1 << 16)
def paired_limits(events_a: int, pairs: int, level: float, power: float) -> Limits:
    """A condition's limits under the paired test, from A's ``events_a`` events over its
    ``pairs`` matched pairs. With no matched pair there is no limit either way."""
    if pairs == 0:
        none = Limit(None, NO_MATCHED_PAIRS)
        return Limits(none, none, 1.0, "mcnemar", "test", 0.0, 0.0)
    p_a = events_a / pairs
    p_min = paired_p_min(pairs)
    found = []
    for rise, room in ((True, 1.0 - p_a), (False, p_a)):
        grid = _grid(room)
        if grid.size == 0:
            found.append(Limit(None, NO_ROOM))
        elif not p_min < level:
            found.append(Limit(None, CANNOT_BE_FLAGGED))
        else:
            found.append(_search(paired_power(p_a, pairs, level, grid, rise), grid, power))
    return Limits(found[0], found[1], p_min, "mcnemar", "test", 1.0 - p_a, p_a)


# ---------- the log-rank test ----------


@dataclass(frozen=True)
class _Template:
    """Arm A's risk set at each of its distinct times: at risk, events, other endings."""

    at_risk: NDArray[np.float64]
    events: NDArray[np.float64]
    other: NDArray[np.float64]
    n: int

    @classmethod
    def of(cls, t: NDArray[np.float64], event: NDArray[np.bool_]) -> _Template:
        times, index = np.unique(t, return_inverse=True)
        events = np.bincount(index, weights=event.astype(np.float64), minlength=times.size).astype(
            np.float64
        )
        ended = np.bincount(index, minlength=times.size).astype(np.float64)
        at_risk = ended[::-1].cumsum()[::-1]
        return cls(at_risk=at_risk, events=events, other=ended - events, n=int(t.size))


def _logrank_moments(
    template: _Template, n_b: int, theta: NDArray[np.float64], level: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """For each hazard ratio: (the power, B's incidence at the horizon).

    At each of A's times B's hazard of the event is ``1 - (1 - h_A)^theta``, B's other endings
    take A's share of other endings among the runs that did not have the event, and the expected
    counts at risk follow. The power is Lakatos's expected moments for A's observed minus
    expected events with Prove's log-rank variance at the expected counts."""
    z = float(stats.norm.isf(level / 2.0))
    at_risk_b = np.full(theta.shape, float(n_b))
    mean = np.zeros_like(at_risk_b)
    variance = np.zeros_like(at_risk_b)
    incidence_b = np.zeros_like(at_risk_b)
    for at_risk_a, events_a, other_a in zip(
        template.at_risk, template.events, template.other, strict=True
    ):
        hazard = events_a / at_risk_a
        events_b = at_risk_b * (1.0 - (1.0 - hazard) ** theta)
        survivors_a = at_risk_a - events_a
        other_b = (at_risk_b - events_b) * (other_a / survivors_a if survivors_a > 0 else 0.0)
        at_risk = at_risk_a + at_risk_b
        events = events_a + events_b
        live = events > 0
        mean += np.where(live, events_a - at_risk_a * events / at_risk, 0.0)
        variance += np.where(
            live & (at_risk > 1),
            at_risk_a
            * at_risk_b
            * events
            * (at_risk - events)
            / (at_risk * at_risk * np.maximum(at_risk - 1.0, 1.0)),
            0.0,
        )
        incidence_b += events_b / n_b
        at_risk_b = at_risk_b - events_b - other_b
    with np.errstate(divide="ignore", invalid="ignore"):
        power = np.where(variance > 0, stats.norm.cdf(np.abs(mean) / np.sqrt(variance) - z), 0.0)
    return power, incidence_b


def _logrank_p(
    t_a: NDArray[np.float64],
    o_a: NDArray[np.bool_],
    t_b: NDArray[np.float64],
    o_b: NDArray[np.bool_],
) -> float:
    from poisson_prove.diff import _logrank

    return _logrank(t_a, o_a, t_b, o_b)[1]


@lru_cache(maxsize=1024)
def logrank_p_min(n_a: int, n_b: int) -> float:
    """The smallest log-rank p for these arm sizes, an asymptotic value: every run of one arm
    has the event at the first time while every run of the other reaches the horizon."""
    first, last = 0.0, 1.0

    def p(n_event: int, n_quiet: int) -> float:
        return _logrank_p(
            np.full(n_quiet, last),
            np.zeros(n_quiet, bool),
            np.full(n_event, first),
            np.ones(n_event, bool),
        )

    return float(min(p(n_b, n_a), p(n_a, n_b)))


@lru_cache(maxsize=1024)
def _zero_baseline_threshold(at_risk_a: int, at_risk_b: int, level: float) -> int | None:
    """The zero-baseline threshold ``k*``: the fewest events in B, all at the horizon among its
    runs at risk there, whose log-rank p against A's runs at risk there (none with the event) is
    below the level."""
    horizon = 1.0
    t_a, o_a = np.full(at_risk_a, horizon), np.zeros(at_risk_a, bool)
    t_b = np.full(at_risk_b, horizon)
    for k in range(1, at_risk_b + 1):
        if _logrank_p(t_a, o_a, t_b, np.arange(at_risk_b) < k) < level:
            return k
    return None


def logrank_limits(
    t_a: NDArray[np.float64],
    o_a: NDArray[np.bool_],
    n_b: int,
    horizon: float,
    level: float,
    power: float,
) -> Limits:
    """A condition's limits under the log-rank test, read from arm A's risk set.

    The rise searches ``log theta`` upward to ``THETA_MAX`` and the fall downward to its inverse,
    each grid point turned into the change it makes to the incidence at the horizon; every limit
    is at least one grid step of incidence. Where A's hazard reaches 1 at a time no theta lowers
    B's there, so a fall the mapping cannot reach is ``none detectable``. With no event in A
    the limit uses log-rank's own threshold for events at the horizon."""
    n_a = int(t_a.size)
    p_min = logrank_p_min(n_a, n_b)
    flaggable = p_min < level
    if not o_a.any():
        return _zero_baseline_limits(t_a, n_b, horizon, level, power, p_min, flaggable)
    template = _Template.of(t_a, o_a)
    incidence_a = float(template.events.sum()) / n_a
    steps = np.arange(1, int(math.floor(math.log(THETA_MAX) / LOG_THETA_STEP)) + 1)
    found = []
    rooms = []
    for rise in (True, False):
        theta = np.exp(steps * LOG_THETA_STEP) if rise else np.exp(-steps * LOG_THETA_STEP)
        powers, incidence_b = _logrank_moments(template, n_b, theta, level)
        change = incidence_b - incidence_a if rise else incidence_a - incidence_b
        room = float(change[-1]) if rise else incidence_a
        rooms.append(room)
        if room < GRID_STEP - 1e-12:
            found.append(Limit(None, NO_ROOM))
            continue
        if not flaggable:
            # A direction with no room says so even when nothing can be flagged.
            found.append(Limit(None, CANNOT_BE_FLAGGED))
            continue
        reachable = change >= GRID_STEP - 1e-12
        index = _first_staying(powers[reachable], power) if reachable.any() else None
        if index is None:
            found.append(Limit(None, NONE_DETECTABLE))
            continue
        at = int(np.nonzero(reachable)[0][index])
        found.append(Limit(float(change[at]), None, float(theta[at]) if rise else None))
    return Limits(found[0], found[1], p_min, "logrank", "test", rooms[0], rooms[1])


def _zero_baseline_limits(
    t_a: NDArray[np.float64],
    n_b: int,
    horizon: float,
    level: float,
    power: float,
    p_min: float,
    flaggable: bool,
) -> Limits:
    """The log-rank limits with no event in A: B's events placed at the horizon against A's runs
    at risk there, B's at risk ``r_b = n_b r_a / n_a`` rounded; the power at a change is ``P(K >=
    k*)`` with ``K ~ Binomial(r_b, change n_b / r_b)`` up to the rise's room ``r_b / n_b``. No
    ``k*`` means no rise (its power is 0 under the model), though an earlier event could still be
    flagged."""
    n_a = int(t_a.size)
    at_risk_a = int(np.sum(t_a >= horizon))
    at_risk_b = int(math.floor(n_b * at_risk_a / n_a + 0.5))
    room = at_risk_b / n_b
    grid = _grid(room)
    k_star = (
        _zero_baseline_threshold(at_risk_a, at_risk_b, level)
        if flaggable and at_risk_a and grid.size
        else None
    )
    if grid.size == 0:
        rise = Limit(None, NO_ROOM)
    elif not flaggable:
        rise = Limit(None, CANNOT_BE_FLAGGED)
    elif k_star is None:
        rise = Limit(None, NONE_DETECTABLE)
    else:
        powers = stats.binom.sf(k_star - 1, at_risk_b, np.clip(grid * n_b / at_risk_b, 0.0, 1.0))
        rise = _search(powers, grid, power)
    return Limits(rise, Limit(None, NO_ROOM), p_min, "logrank", "zero baseline", room, 0.0)


# ---------- what a design can flag ----------


def together_needed(p_mins: Sequence[float], q: float, family: int) -> int | None:
    """The fewest rows that, all at their extremes together, Benjamini-Hochberg would
    flag: the smallest ``k`` whose ``k``-th smallest ``p_min`` is below ``q k / M``."""
    for k, p in enumerate(sorted(p_mins), start=1):
        if p < q * k / family:
            return k
    return None


@lru_cache(maxsize=1024)
def replicates_for_lone_flag(test: str, level: float) -> int | None:
    """The smallest equal number of runs a side at which a lone condition could be
    flagged at all under ``test``."""

    def smallest(n: int) -> float:
        if test == "mcnemar":
            return paired_p_min(n)
        return fisher_p_min(n, n) if test == "fisher" else logrank_p_min(n, n)

    for n in range(1, 100_000):
        if smallest(n) < level:
            return n
    return None


# ---------- the power gate ----------

#: The gate's grid of base rates.
_BASE_RATES = np.round(np.arange(0.0, 1.0 + 1e-9, 0.005), 3)


@dataclass(frozen=True)
class Design:
    """The gate's reading of a design: its limit at its worst base rate for the accepted change,
    and whether it passes."""

    mde: float | None
    base_rate: float
    direction: str
    test: str
    level: float
    family: int
    conditions: int
    events: int
    q: float
    power: float
    flaggable: bool
    p_min: float
    worst_power: float
    passes: bool

    def record(self) -> dict[str, Any]:
        """What the manifest records as ``design_mde``."""
        keys = (
            "mde",
            "base_rate",
            "direction",
            "test",
            "level",
            "family",
            "conditions",
            "events",
            "q",
            "power",
            "flaggable",
        )
        return {key: getattr(self, key) for key in keys}


def _power_at(
    base: float, n_a: int, n_b: int, level: float, change: float, test: str, rise: bool
) -> float:
    changes = np.array([change])
    if test == "mcnemar":
        return float(paired_power(base, min(n_a, n_b), level, changes, rise)[0])
    return float(fisher_power(base, n_a, n_b, level, changes, rise)[0])


def design(
    *,
    conditions: int,
    events: int,
    n_a: int,
    n_b: int,
    threshold: float,
    q: float,
    power: float,
    test: str,
) -> Design:
    """The gate's limit: Fisher's test, or the paired test with independent arms
    under ``--pair-with``, at ``q / M`` with ``M`` the conditions times the events. A design
    passes when, at every base rate on a 0.005 grid with room for a change of ``threshold``, the
    power at exactly that change reaches the target; the worst base rate is the one with the
    lowest power, ties within 1e-12 going to the lower base rate and a rise before a fall. An
    accepted change of 1 passes every design."""
    family = max(1, conditions * events)
    level = q / family
    p_min = paired_p_min(min(n_a, n_b)) if test == "mcnemar" else fisher_p_min(n_a, n_b)
    flaggable = bool(p_min < level)
    change = min(threshold, 1.0)
    worst_power, worst_base, worst_rise = 2.0, 0.0, True
    for base in _BASE_RATES:
        for rise in (True, False):
            if (rise and base > 1.0 - change + 1e-9) or (not rise and base < change - 1e-9):
                continue
            at = _power_at(float(base), n_a, n_b, level, change, test, rise) if flaggable else 0.0
            if at < worst_power - 1e-12:
                worst_power, worst_base, worst_rise = at, float(base), rise
    mde: float | None = None
    if flaggable:
        room = 1.0 - worst_base if worst_rise else worst_base
        grid = _grid(room)
        if test == "mcnemar":
            found = _search(
                paired_power(worst_base, min(n_a, n_b), level, grid, worst_rise), grid, power
            )
        else:
            found = _fisher_search(worst_base, n_a, n_b, level, grid, worst_rise, power)
        mde = found.value
    passes = threshold >= 1.0 or (flaggable and worst_power >= power - 1e-12)
    return Design(
        mde=mde,
        base_rate=worst_base,
        direction="rise" if worst_rise else "fall",
        test=test,
        level=level,
        family=family,
        conditions=conditions,
        events=events,
        q=q,
        power=power,
        flaggable=flaggable,
        p_min=p_min,
        worst_power=worst_power,
        passes=passes,
    )


# ---------- the fault-line groups ----------


def group_limit(
    n_a: NDArray[np.float64],
    n_b: NDArray[np.float64],
    p_a: NDArray[np.float64],
    members: NDArray[np.int64],
    *,
    alpha: float,
    groups: int,
    events: int,
    power: float,
) -> float:
    """One group's limit for one event: the smallest change ``delta`` such that, every condition
    of the group moved by ``delta`` from its own baseline (capped at its room) and nothing else
    moving, the tree flags the group with the root and the group both rejecting, unconditionally.

    A normal approximation to the tree's location statistics, cautious by construction: the
    dispersion statistics and the root's Westfall-Young gain are left out, the group's mean change
    is read at ``alpha`` (``q / G``), the root's mean over every condition at ``q / (2K)`` over its
    ``2K`` statistics, and the two are treated as independent, so the power is
    their product. 1.0 when the group has no room or nothing within it reaches the target."""
    rooms = 1.0 - p_a[members]
    if rooms.size == 0 or float(rooms.max()) <= 0.0:
        return 1.0
    q = alpha * groups
    z_group = float(stats.norm.isf(alpha / 2.0))
    z_root = float(stats.norm.isf(q / (2.0 * 2.0 * max(1, events))))
    baseline_var = p_a * (1.0 - p_a) / np.maximum(n_a, 1.0)
    grid = _grid(float(rooms.max()))
    moved = np.minimum(grid[:, None], rooms[None, :])
    p_b = p_a[members][None, :] + moved
    cell_var = baseline_var[members][None, :] + p_b * (1.0 - p_b) / np.maximum(
        n_b[members][None, :], 1.0
    )
    others = np.setdiff1d(np.arange(p_a.size), members)
    group_mean = moved.mean(axis=1)
    group_sd = np.sqrt(cell_var.sum(axis=1)) / members.size
    root_mean = moved.sum(axis=1) / p_a.size
    # An unmoved condition's change has both arms' variance at its baseline, each at its size.
    unmoved_var = p_a * (1.0 - p_a) * (1.0 / np.maximum(n_a, 1.0) + 1.0 / np.maximum(n_b, 1.0))
    root_sd = np.sqrt(cell_var.sum(axis=1) + unmoved_var[others].sum()) / p_a.size
    with np.errstate(divide="ignore", invalid="ignore"):
        # No variance left (every condition moved to 0 or 1): the change is certain, seen exactly
        # when there is one.
        group_power = np.where(
            group_sd > 0, stats.norm.cdf(group_mean / group_sd - z_group), group_mean > 0
        )
        root_power = np.where(
            root_sd > 0, stats.norm.cdf(root_mean / root_sd - z_root), root_mean > 0
        )
    found = _search(group_power * root_power, grid, power)
    return 1.0 if found.value is None else found.value
