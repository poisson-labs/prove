"""The comparison's word (PF4.34, PF4.29, PF4.20) and how many outcomes would change it (PF4.44).

The word is read over the rows that count at the family-wise level, by Holm's procedure at ``q``:
section 8.4's table when every compared event's kind is known (``trade``, ``worse``, ``safer``),
PF4.20's direction words when one is not (``mixed``, ``higher``, ``lower``), and, when no row
counts, one of the two nothing-moved words, decided by PF4.29's question over every row that does
not count: ``no significant change`` when each could have told a change of the threshold, from
where it was, at the verdict's level ``q / M``; ``too small to tell`` otherwise.

The fragility is the fewest stored outcomes, over both runs, whose flipping gives a different word.
A flip moves one run's outcome, keeping its time, so that it moves exactly one row (reading R26): a
run that ended in the row's event is made to end outside the compared events, and a run that ended
outside them is made to end in the event. The search tries three ways the word can change, cheapest
first, and decides the word again on the flipped rows before it accepts a set, so the flips it names
always change the word:

- **a direction appears.** One row that does not count is moved below ``q / (M - R)``, ``R`` the
  rows that count, in a direction the word does not hold; or the step-down is made to go a few
  places further, so a row the word does not hold counts without a flip of its own;
- **a direction disappears.** For a direction the word rests on and each place ``k`` the step-down
  could be made to stop (``tau = q / (M - k)``), every row of that direction below ``tau`` is moved
  to or above it, and of the other rows below ``tau`` all but the ``k`` costliest to move are too;
- **the nothing-moved word switches.** With no row counting, one row that could tell is made unable
  to, or every row that could not is made able to, by flips in run A (the limits read A only).

Within a row the cheapest move is exhaustive for Fisher's test and the paired test, whose p-values
are functions of counts; under the log-rank test it is a greedy path, each step the one flip that
moves the statistic most (reading R13). The result is exact when the test is not log-rank and one
event is compared: with two or more, a run moving between two compared events would move two rows
at once, which no one-row search can see (reading R26).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cached_property, lru_cache, partial
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy import stats

from poisson_prove import _limits

HIGHER, LOWER, UNCHANGED = "higher", "lower", "unchanged"
NO_SIGNIFICANT_CHANGE = "no significant change"
TOO_SMALL_TO_TELL = "too small to tell"
NOTHING_MOVED = (NO_SIGNIFICANT_CHANGE, TOO_SMALL_TO_TELL)
#: Why a comparison has no fragility.
NO_FLIPS = "no set of flips changes the word"
#: How many flips into one row a search goes.
_CAP = 400
_NEVER = np.iinfo(np.int64).max


# ---------- the word ----------


def judged(direction: str, kind: str | None) -> str:
    """A significant direction as a judgement: a rise of a failure is ``worse``, of a success
    ``safer``. Only for an event whose kind is known."""
    if kind == "success":
        return "safer" if direction == HIGHER else "worse"
    return "worse" if direction == HIGHER else "safer"


def word_of(directions: Iterable[str], kinds_known: bool, could_tell: bool) -> str:
    """The word from the directions of the rows that count, each already in the vocabulary the
    kinds allow (``worse``/``safer`` when every kind is known, else ``higher``/``lower``)."""
    present = set(directions)
    up, down = ("worse", "safer") if kinds_known else (HIGHER, LOWER)
    if up in present and down in present:
        return "trade" if kinds_known else "mixed"
    if up in present:
        return up
    if down in present:
        return down
    return NO_SIGNIFICANT_CHANGE if could_tell else TOO_SMALL_TO_TELL


def direction_of(signed: float) -> str | None:
    """The way a row moved, from the sign of its change (B's way: positive is a rise)."""
    return HIGHER if signed > 0 else LOWER if signed < 0 else None


@dataclass(frozen=True)
class RowFacts:
    """What the word reads from one row of the pass: its p, the sign of its change, its event's
    kind, and its limits at the verdict's level ``q / M`` (``at_verdict``: the limits, or how to
    compute them, so a flipped row's are computed only when the nothing-moved question reads
    them)."""

    p: float
    signed: float
    kind: str | None
    at_verdict: _limits.Limits | Callable[[], _limits.Limits]

    @cached_property
    def limits(self) -> _limits.Limits:
        found = self.at_verdict
        return found if isinstance(found, _limits.Limits) else found()

    def way(self, kinds_known: bool) -> str | None:
        """The row's direction in the vocabulary the word uses."""
        direction = direction_of(self.signed)
        if direction is None or not kinds_known:
            return direction
        return judged(direction, self.kind)


@dataclass(frozen=True)
class Verdict:
    """The word and what it rests on: which rows count, each other row's answer to the
    nothing-moved question, and the verdict limit (PF4.40)."""

    word: str
    counts: tuple[bool, ...]
    tells: Mapping[int, bool]
    verdict_limit: float | None


def decide(
    rows: Sequence[RowFacts], q: float, threshold: float, *, word_only: bool = False
) -> Verdict:
    """The comparison's word over ``rows``, one per row of the pass, in the pass's order. With
    ``word_only`` a word that names a change is returned without asking the nothing-moved
    question, which it does not read (its ``tells`` and verdict limit are then empty)."""
    # Imported here: ``diff`` defines the two corrections and imports this module.
    from poisson_prove.diff import holm

    kinds_known = all(r.kind is not None for r in rows)
    counts = tuple(bool(c) for c in holm(np.array([r.p for r in rows], dtype=np.float64), q) < q)
    directions: list[str] = []
    tells: dict[int, bool] = {}
    largest: float | None = None
    unread = False
    for row, counted in zip(rows, counts, strict=True):
        if counted:
            way = row.way(kinds_known)
            if way is not None:
                directions.append(way)
    if word_only and directions:
        return Verdict(word_of(directions, kinds_known, True), counts, {}, None)
    for index, (row, counted) in enumerate(zip(rows, counts, strict=True)):
        if counted:
            continue
        could, read = row.limits.could_tell(threshold)
        tells[index] = could
        if read is None:
            unread = True
        else:
            largest = read if largest is None else max(largest, read)
    word = word_of(directions, kinds_known, all(tells.values()))
    return Verdict(word, counts, tells, None if unread or not tells else largest)


# ---------- moving one row ----------


@dataclass(frozen=True)
class Move:
    """A set of ``cost`` flips inside one row; ``plan`` says which, in the row's own terms, and
    ``after`` the row's p and signed change once they are made, when the search already knows
    them."""

    cost: int
    plan: Any
    after: tuple[float, float] | None = None


def _meets(p: float, signed: float, target: float, want: str | None) -> bool:
    """Whether a row with this p and change is at or above ``target`` or has no direction (``want``
    None), or below ``target`` in direction ``want``."""
    if want is None:
        return p >= target or signed == 0
    return p < target and direction_of(signed) == want


def _cheapest_cell(
    p: NDArray[np.float64],
    signed: NDArray[np.int64],
    cost: NDArray[np.int64],
    reachable: NDArray[np.bool_],
    target: float,
    want: str | None,
) -> tuple[int, ...] | None:
    """The cheapest reachable cell of a table of outcomes that meets the target."""
    if want is None:
        ok = (p >= target) | (signed == 0)
    else:
        ok = (p < target) & ((signed > 0) if want == HIGHER else (signed < 0))
    ok &= reachable
    priced = np.where(ok, cost, _NEVER)
    best = np.unravel_index(int(np.argmin(priced)), priced.shape)
    return tuple(int(i) for i in best) if ok[best] else None


def _flip(row: Row, arm: str, replicate: int, to: str) -> dict[str, Any]:
    return {
        "config_hash": row.config_hash,
        "event": row.event,
        "run": arm,
        "replicate_index": int(replicate),
        "to": to,
    }


@dataclass(frozen=True)
class FisherRow:
    """A row under Fisher's test, which reads counts only. ``had`` are the replicates of each arm
    that ended in the event; ``spare`` those that ended outside the compared events."""

    facts: RowFacts
    event: str
    config_hash: str
    n: tuple[int, int]
    had: tuple[tuple[int, ...], tuple[int, ...]]
    spare: tuple[tuple[int, ...], tuple[int, ...]]
    level: float
    power: float

    def cheapest(self, target: float, want: str | None, cap: int = _CAP) -> Move | None:
        """The fewest flips that meet the target, over every table the flips can reach."""
        (n_a, n_b), (e_a, e_b) = self.n, (len(self.had[0]), len(self.had[1]))
        x_a = np.arange(0, e_a + len(self.spare[0]) + 1)[:, None]
        x_b = np.arange(0, e_b + len(self.spare[1]) + 1)[None, :]
        p = _limits._fisher_table(n_a, n_b)[x_a, x_b]
        cost = np.abs(x_a - e_a) + np.abs(x_b - e_b)
        best = _cheapest_cell(p, x_b * n_a - x_a * n_b, cost, cost <= cap, target, want)
        if best is None:
            return None
        return Move(int(cost[best]), (int(x_a[best[0], 0]) - e_a, int(x_b[0, best[1]]) - e_b))

    def cheapest_tell(self, could: bool, threshold: float, cap: int = _CAP) -> Move | None:
        """The fewest flips in run A that make the row's answer to the nothing-moved question
        ``could``: A's events move by one per flip, and its limits with them."""
        n_a, n_b = self.n
        had, spare = len(self.had[0]), len(self.spare[0])
        for k in range(1, min(cap, max(had, spare)) + 1):
            for change in (k, -k):
                if -had <= change <= spare:
                    limits = _limits.fisher_limits(had + change, n_a, n_b, self.level, self.power)
                    if limits.could_tell(threshold)[0] is could:
                        return Move(k, (change, 0))
        return None

    def after(self, move: Move) -> FisherRow:
        (n_a, n_b), (d_a, d_b) = self.n, move.plan
        had, spare = (
            [list(self.had[0]), list(self.had[1])],
            [list(self.spare[0]), list(self.spare[1])],
        )
        for arm, change in ((0, d_a), (1, d_b)):
            if change > 0:
                had[arm] += spare[arm][:change]
                spare[arm] = spare[arm][change:]
            elif change < 0:
                spare[arm] += had[arm][:-change]
                had[arm] = had[arm][-change:]
        e_a, e_b = len(had[0]), len(had[1])
        facts = replace(
            self.facts,
            p=_limits.fisher_p(e_a, n_a, e_b, n_b),
            signed=e_b * n_a - e_a * n_b,
            at_verdict=partial(_limits.fisher_limits, e_a, n_a, n_b, self.level, self.power),
        )
        return replace(
            self,
            facts=facts,
            had=(tuple(had[0]), tuple(had[1])),
            spare=(tuple(spare[0]), tuple(spare[1])),
        )

    def flips(self, move: Move) -> list[dict[str, Any]]:
        out = []
        for arm, change, had, spare in zip("ab", move.plan, self.had, self.spare, strict=True):
            if change > 0:
                out += [_flip(self, arm, rep, "event") for rep in spare[:change]]
            else:
                out += [_flip(self, arm, rep, "not event") for rep in had[:-change]]
        return out


@lru_cache(maxsize=256)
def _paired_table(max_only_a: int, max_only_b: int) -> NDArray[np.float64]:
    """The paired p of every pair of discordant counts up to these."""
    only_a = np.arange(max_only_a + 1)[:, None]
    only_b = np.arange(max_only_b + 1)[None, :]
    total = only_a + only_b
    p = np.minimum(
        1.0, 2.0 * stats.binom.cdf(np.minimum(only_a, only_b), np.maximum(total, 1), 0.5)
    )
    return np.where(total == 0, 1.0, p)


@dataclass(frozen=True)
class PairedRow:
    """A row under the paired test, over its matched pairs by replicate: ``only_a`` the pairs in
    which only A had the event, ``only_b`` only B, ``both`` and ``neither``. ``spare_a`` and
    ``spare_b`` are the replicates whose run in that arm ended outside the compared events."""

    facts: RowFacts
    event: str
    config_hash: str
    only_a: tuple[int, ...]
    only_b: tuple[int, ...]
    both: tuple[int, ...]
    neither: tuple[int, ...]
    spare_a: frozenset[int]
    spare_b: frozenset[int]
    level: float
    power: float

    def _gains(self) -> tuple[list[int], list[int], list[int]]:
        """The neither pairs that can become only-A (A's run may gain the event), only-B, or
        either."""
        by_a = [r for r in self.neither if r in self.spare_a and r not in self.spare_b]
        by_b = [r for r in self.neither if r in self.spare_b and r not in self.spare_a]
        either = [r for r in self.neither if r in self.spare_a and r in self.spare_b]
        return by_a, by_b, either

    def cheapest(self, target: float, want: str | None, cap: int = _CAP) -> Move | None:
        """Each flip changes one discordant count by one: an only-A pair loses A's event, a both
        pair loses either run's, a neither pair gains one where that run ended outside the
        compared events (and the mirrors for B). Every reachable pair of counts at once."""
        by_a, by_b, either = (len(x) for x in self._gains())
        b0, c0, both = len(self.only_a), len(self.only_b), len(self.both)
        b = np.arange(0, b0 + both + by_a + either + 1)[:, None]
        c = np.arange(0, c0 + both + by_b + either + 1)[None, :]
        up_b, up_c = np.maximum(b - b0, 0), np.maximum(c - c0, 0)
        cost = np.abs(b - b0) + np.abs(c - c0)
        reachable = (
            (up_b <= both + by_a + either)
            & (up_c <= both + by_b + either)
            & (up_b + up_c <= both + by_a + by_b + either)
            & (cost <= cap)
        )
        p = _paired_table(int(b[-1, 0]), int(c[0, -1]))
        best = _cheapest_cell(p, c - b, cost, reachable, target, want)
        if best is None:
            return None
        return Move(int(cost[best]), ("pairs", int(b[best[0], 0]) - b0, int(c[0, best[1]]) - c0))

    def cheapest_tell(self, could: bool, threshold: float, cap: int = _CAP) -> Move | None:
        """The fewest flips in run A, over the matched pairs, that make the row's answer to the
        nothing-moved question ``could``: A's events over the pairs move by one per flip."""
        matched = len(self.only_a) + len(self.only_b) + len(self.both) + len(self.neither)
        had = len(self.only_a) + len(self.both)
        spare = sum(1 for r in (*self.neither, *self.only_b) if r in self.spare_a)
        for k in range(1, min(cap, max(had, spare)) + 1):
            for change in (k, -k):
                if -had <= change <= spare:
                    limits = _limits.paired_limits(had + change, matched, self.level, self.power)
                    if limits.could_tell(threshold)[0] is could:
                        return Move(k, ("run a", change))
        return None

    def _plan(self, move: Move) -> list[tuple[str, int, str]]:
        """A move's flips as ``(arm, replicate, to)``."""
        if move.plan[0] == "run a":
            change = move.plan[1]
            if change > 0:
                gain = [r for r in (*self.neither, *self.only_b) if r in self.spare_a]
                return [("a", r, "event") for r in gain[:change]]
            return [("a", r, "not event") for r in (*self.only_a, *self.both)[:-change]]
        _, d_b, d_c = move.plan
        out = [("a", r, "not event") for r in self.only_a[: max(-d_b, 0)]]
        out += [("b", r, "not event") for r in self.only_b[: max(-d_c, 0)]]
        by_a, by_b, either = self._gains()
        shared = list(self.both)
        # Each side takes the pairs only it can use first, then the shared ones: a both pair
        # (losing the other arm's event) before a neither pair either arm may gain in.
        for gained_by, needed, own in (("a", max(d_b, 0), by_a), ("b", max(d_c, 0), by_b)):
            for _ in range(needed):
                if own:
                    out.append((gained_by, own.pop(0), "event"))
                elif shared:
                    out.append(("b" if gained_by == "a" else "a", shared.pop(0), "not event"))
                else:
                    out.append((gained_by, either.pop(0), "event"))
        return out

    def after(self, move: Move) -> PairedRow:
        had = {("a", r) for r in (*self.only_a, *self.both)} | {
            ("b", r) for r in (*self.only_b, *self.both)
        }
        for arm, rep, to in self._plan(move):
            (had.add if to == "event" else had.discard)((arm, rep))
        types: dict[str, list[int]] = {"only_a": [], "only_b": [], "both": [], "neither": []}
        for rep in sorted((*self.only_a, *self.only_b, *self.both, *self.neither)):
            in_a, in_b = ("a", rep) in had, ("b", rep) in had
            types[
                "both" if in_a and in_b else "only_a" if in_a else "only_b" if in_b else "neither"
            ].append(rep)
        b, c, matched = (
            len(types["only_a"]),
            len(types["only_b"]),
            sum(len(v) for v in types.values()),
        )
        limits = partial(
            _limits.paired_limits, b + len(types["both"]), matched, self.level, self.power
        )
        return replace(
            self,
            facts=replace(self.facts, p=_limits.paired_p(b, c), signed=c - b, at_verdict=limits),
            only_a=tuple(types["only_a"]),
            only_b=tuple(types["only_b"]),
            both=tuple(types["both"]),
            neither=tuple(types["neither"]),
        )

    def flips(self, move: Move) -> list[dict[str, Any]]:
        return [_flip(self, arm, rep, to) for arm, rep, to in self._plan(move)]


class LogrankRow:
    """A row under the log-rank test: each run's time and whether it had the event, per arm, which
    runs ended outside the compared events (the ones that may be made to have it), and each run's
    replicate index."""

    def __init__(
        self,
        facts: RowFacts,
        *,
        event: str,
        config_hash: str,
        t: tuple[NDArray[np.float64], NDArray[np.float64]],
        had: tuple[NDArray[np.bool_], NDArray[np.bool_]],
        spare: tuple[NDArray[np.bool_], NDArray[np.bool_]],
        reps: tuple[NDArray[np.int64], NDArray[np.int64]],
        horizon: float,
        level: float,
        power: float,
    ) -> None:
        self.facts, self.event, self.config_hash = facts, event, config_hash
        self.t, self.had, self.spare, self.reps = t, had, spare, reps
        self.horizon, self.level, self.power = horizon, level, power
        self._paths: dict[str | None, _GreedyPath] = {}

    def cheapest(self, target: float, want: str | None, cap: int = _CAP) -> Move | None:
        """The first point of the greedy path toward ``want`` that meets the target."""
        if _meets(self.facts.p, self.facts.signed, target, want):
            return Move(0, (), (self.facts.p, self.facts.signed))
        path = self._paths.get(want)
        if path is None:
            path = self._paths[want] = _GreedyPath(self, want)
        for k in range(1, cap + 1):
            step = path.step(k)
            if step is None:
                return None
            if _meets(*step, target, want):
                return Move(k, path.runs(k), step)
        return None

    def cheapest_tell(self, could: bool, threshold: float, cap: int = _CAP) -> Move | None:
        """Not searched: a log-rank limit reads A's whole risk set, not a count a flip moves by
        one, and the result already says the search is not exact (reading R13)."""
        return None

    def after(self, move: Move) -> LogrankRow:
        from poisson_prove.diff import _logrank, _logrank_signed

        had = [self.had[0].copy(), self.had[1].copy()]
        for arm, run in move.plan:
            side = "ab".index(arm)
            had[side][run] = not had[side][run]
        if move.after is None:
            p = _logrank(self.t[0], had[0], self.t[1], had[1])[1]
            signed = _logrank_signed(self.t[0], had[0], self.t[1], had[1])
        else:
            p, signed = move.after
        limits = partial(
            _limits.logrank_limits,
            self.t[0],
            had[0],
            int(self.t[1].size),
            self.horizon,
            self.level,
            self.power,
        )
        facts = replace(self.facts, p=p, signed=signed, at_verdict=limits)
        return LogrankRow(
            facts,
            event=self.event,
            config_hash=self.config_hash,
            t=self.t,
            had=(had[0], had[1]),
            spare=self.spare,
            reps=self.reps,
            horizon=self.horizon,
            level=self.level,
            power=self.power,
        )

    def flips(self, move: Move) -> list[dict[str, Any]]:
        out = []
        for arm, run in move.plan:
            side = "ab".index(arm)
            out.append(
                _flip(
                    self,
                    arm,
                    int(self.reps[side][run]),
                    "not event" if self.had[side][run] else "event",
                )
            )
        return out


class _GreedyPath:
    """The greedy path of one log-rank row toward ``want`` (None: toward no significance), grown
    one flip at a time as far as a search asks: each step takes the one flip that moves the
    statistic most that way.

    A flip keeps the run's time, so it changes one time's event count, and the log-rank sums
    change at that time only: each step scores every candidate time at once from the totals."""

    def __init__(self, row: LogrankRow, want: str | None) -> None:
        self.want = want
        times = np.unique(np.concatenate(row.t))
        index = [np.searchsorted(times, t) for t in row.t]
        self.at_risk = [
            np.bincount(i, minlength=times.size)[::-1].cumsum()[::-1].astype(np.float64)
            for i in index
        ]
        self.events = [
            np.bincount(i[h], minlength=times.size).astype(np.float64)
            for i, h in zip(index, row.had, strict=True)
        ]
        # The runs each flip can take, per arm and way, per time: into the event only from a run
        # that ended outside the compared events, out of it from a run that had it.
        self.pools: dict[tuple[int, int], list[list[int]]] = {}
        for arm in (0, 1):
            for way, members in ((1, row.spare[arm] & ~row.had[arm]), (-1, row.had[arm])):
                stacks: list[list[int]] = [[] for _ in range(times.size)]
                for run in np.nonzero(members)[0]:
                    stacks[int(index[arm][run])].append(int(run))
                self.pools[(arm, way)] = stacks
        self.gap, self.variance = _logrank_terms(self.events[0], self.events[1], *self.at_risk)
        self.total_gap, self.total_variance = float(self.gap.sum()), float(self.variance.sum())
        self.taken: list[tuple[float, float, tuple[str, int]]] = []
        self.ended = False

    def step(self, k: int) -> tuple[float, float] | None:
        """The p and the signed change after the first ``k`` flips; None when the path ends
        first."""
        while len(self.taken) < k and not self.ended:
            self._grow()
        if len(self.taken) < k:
            return None
        p, signed, _ = self.taken[k - 1]
        return p, signed

    def runs(self, k: int) -> tuple[tuple[str, int], ...]:
        return tuple(run for _, _, run in self.taken[:k])

    def _grow(self) -> None:
        best: tuple[float, int, int, int, float, float] | None = None
        for arm in (0, 1):
            for way in (1, -1):
                stacks = self.pools[(arm, way)]
                open_times = np.array(
                    [j for j, stack in enumerate(stacks) if stack], dtype=np.int64
                )
                if open_times.size == 0:
                    continue
                d_a = self.events[0][open_times] + (way if arm == 0 else 0)
                d_b = self.events[1][open_times] + (way if arm == 1 else 0)
                gap, variance = _logrank_terms(
                    d_a, d_b, self.at_risk[0][open_times], self.at_risk[1][open_times]
                )
                total_gap = self.total_gap - self.gap[open_times] + gap
                total_variance = self.total_variance - self.variance[open_times] + variance
                usable = total_variance > 1e-15
                chi2 = np.where(usable, total_gap**2 / np.where(usable, total_variance, 1.0), 0.0)
                p_values = np.where(usable, stats.chi2.sf(chi2, 1), 1.0)
                signs = -total_gap  # B's observed minus expected is minus A's
                if self.want is None:
                    score = np.where(signs != 0, p_values, 2.0)
                else:
                    # The signed z toward the wanted way: a flip that moves the statistic that
                    # way scores higher whichever side of zero it starts on.
                    z = np.where(
                        usable, signs / np.sqrt(np.where(usable, total_variance, 1.0)), 0.0
                    )
                    score = z if self.want == HIGHER else -z
                pick = int(np.argmax(score))
                if best is None or score[pick] > best[0]:
                    best = (
                        float(score[pick]),
                        arm,
                        way,
                        int(open_times[pick]),
                        float(p_values[pick]),
                        float(signs[pick]),
                    )
        if best is None:
            self.ended = True
            return
        _, arm, way, j, p, signed = best
        run = self.pools[(arm, way)][j].pop(0)
        self.events[arm][j] += way
        gap, variance = _logrank_terms(
            self.events[0][j : j + 1],
            self.events[1][j : j + 1],
            self.at_risk[0][j : j + 1],
            self.at_risk[1][j : j + 1],
        )
        self.total_gap += float(gap[0] - self.gap[j])
        self.total_variance += float(variance[0] - self.variance[j])
        self.gap[j], self.variance[j] = gap[0], variance[0]
        self.taken.append((p, signed, ("ab"[arm], run)))
        self.ended = len(self.taken) >= _CAP


def _logrank_terms(
    d_a: NDArray[np.float64],
    d_b: NDArray[np.float64],
    y_a: NDArray[np.float64],
    y_b: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Each time's share of the log-rank sums as ``diff._logrank`` adds them: A's observed minus
    expected events, and the variance."""
    d, y = d_a + d_b, y_a + y_b
    safe = np.maximum(y, 1.0)
    gap = np.where(y > 0, d_a - y_a * d / safe, 0.0)
    variance = np.where(
        y > 1, y_a * y_b * d * (y - d) / (safe * safe * np.maximum(y - 1.0, 1.0)), 0.0
    )
    return gap, variance


Row = FisherRow | PairedRow | LogrankRow


# ---------- the search ----------


@dataclass(frozen=True)
class Fragility:
    """PF4.44: the fewest outcomes that would change the word, one such set of flips, why there
    is none when there is none, and whether the search was exhaustive."""

    value: int | None
    flips: tuple[Mapping[str, Any], ...] = ()
    note: str | None = None
    exact: bool = True


class _Search:
    """The best verified set of flips so far, which bounds every later search."""

    def __init__(self, rows: Sequence[Row], q: float, threshold: float) -> None:
        self.rows, self.q, self.threshold = rows, q, threshold
        self.before = decide([row.facts for row in rows], q, threshold)
        self.best: tuple[int, list[tuple[int, Move]]] | None = None

    @property
    def cap(self) -> int:
        """Flips worth searching for: fewer than the best set found."""
        return _CAP if self.best is None else self.best[0] - 1

    def offer(self, plan: list[tuple[int, Move]]) -> None:
        cost = sum(move.cost for _, move in plan)
        if cost == 0 or cost > self.cap:
            return
        moved = list(self.rows)
        for index, move in plan:
            moved[index] = self.rows[index].after(move)
        decided = decide([row.facts for row in moved], self.q, self.threshold, word_only=True)
        if decided.word != self.before.word:
            self.best = (cost, plan)


def fragility(rows: Sequence[Row], *, q: float, threshold: float, events: int) -> Fragility:
    """Search ``rows``, one per row of the pass in the pass's order, for the fewest flips that
    change the word (the module's docstring says how)."""
    exact = events == 1 and not any(isinstance(row, LogrankRow) for row in rows)
    search = _Search(rows, q, threshold)
    kinds_known = all(row.facts.kind is not None for row in rows)
    _add_a_direction(search, kinds_known)
    _step_further(search, kinds_known)
    _remove_a_direction(search, kinds_known)
    if search.before.word in NOTHING_MOVED:
        _switch_the_question(search)
    if search.best is None:
        return Fragility(None, (), NO_FLIPS, exact)
    flips = [flip for index, move in search.best[1] for flip in rows[index].flips(move)]
    return Fragility(len(flips), tuple(flips), None, exact)


def _present(search: _Search, kinds_known: bool) -> set[str]:
    ways = (
        row.facts.way(kinds_known)
        for row, c in zip(search.rows, search.before.counts, strict=True)
        if c
    )
    return {way for way in ways if way is not None}


def _add_a_direction(search: _Search, kinds_known: bool) -> None:
    rows, before = search.rows, search.before
    counted = sum(before.counts)
    if counted >= len(rows):
        return
    present = _present(search, kinds_known)
    tau = search.q / (len(rows) - counted)
    for index, row in enumerate(rows):
        if before.counts[index]:
            continue
        for way in (HIGHER, LOWER):
            if (judged(way, row.facts.kind) if kinds_known else way) in present:
                continue
            move = row.cheapest(tau, way, search.cap)
            if move is not None:
                search.offer([(index, move)])


#: How many places past the rows that count the step-down search looks.
_FURTHER = 4


def _step_further(search: _Search, kinds_known: bool) -> None:
    """A direction appears because Holm's step-down goes further: for each place ``k`` up to
    ``_FURTHER`` past the rows that count, fill places 1 to ``k`` in turn, each with the row whose
    p is already below that place's threshold ``q / (M - j + 1)``, else with the cheapest row to
    move below it; a row the word does not hold may then count without a flip of its own."""
    rows, before, q, m = search.rows, search.before, search.q, len(search.rows)
    words = {"worse", "safer"} if kinds_known else {HIGHER, LOWER}
    if words <= _present(search, kinds_known):
        return
    order = sorted(range(m), key=lambda i: rows[i].facts.p)
    counted = sum(before.counts)
    for k in range(counted + 2, min(m, counted + _FURTHER) + 1):
        placed: set[int] = set()
        plan: list[tuple[int, Move]] = []
        cost = 0
        for j in range(1, k + 1):
            tau = q / (m - j + 1)
            free = next((i for i in order if i not in placed and rows[i].facts.p < tau), None)
            if free is not None:
                placed.add(free)
                continue
            found: tuple[int, Move] | None = None
            for index, row in enumerate(rows):
                if index in placed:
                    continue
                way = direction_of(row.facts.signed)
                for want in (way,) if way is not None else (HIGHER, LOWER):
                    move = row.cheapest(tau, want, search.cap - cost)
                    if move is not None and (found is None or move.cost < found[1].cost):
                        found = (index, move)
            if found is None or cost + found[1].cost > search.cap:
                break
            placed.add(found[0])
            plan.append(found)
            cost += found[1].cost
        else:
            if plan:
                search.offer(plan)


def _remove_a_direction(search: _Search, kinds_known: bool) -> None:
    rows, m = search.rows, len(search.rows)
    for gone in sorted(_present(search, kinds_known)):
        for keep in range(m):
            tau = search.q / (m - keep)
            must: list[tuple[int, Move]] = []
            others: list[tuple[int, Move | None]] = []
            for index, row in enumerate(rows):
                if row.facts.p >= tau:
                    continue
                move = row.cheapest(tau, None, search.cap)
                if row.facts.way(kinds_known) == gone:
                    if move is None:
                        break
                    must.append((index, move))
                else:
                    others.append((index, move))
            else:
                # The ``keep`` costliest of the other rows may stay below tau; the rest must move.
                others.sort(key=lambda item: -(math.inf if item[1] is None else item[1].cost))
                rest = others[keep:]
                if all(move is not None for _, move in rest):
                    search.offer(must + [(index, move) for index, move in rest if move is not None])


def _switch_the_question(search: _Search) -> None:
    rows, tells = search.rows, search.before.tells
    if all(tells.values()):
        # "no significant change": one row that could tell, made unable to.
        for index in tells:
            move = rows[index].cheapest_tell(False, search.threshold, search.cap)
            if move is not None:
                search.offer([(index, move)])
        return
    # "too small to tell": every row that could not, made able to.
    plan = []
    for index, could in tells.items():
        if not could:
            move = rows[index].cheapest_tell(True, search.threshold, search.cap)
            if move is None:
                return
            plan.append((index, move))
    search.offer(plan)
