"""PF4, the claims Prove prints, simulated: the math suite's spine (PF4.26, PF4.36, PF4.51).

Every claim Prove prints about error rates is checked by simulating Prove's own comparison, never by
recomputing the formula that produced the number: the verdict's family-wise rate when nothing changed
(and when only some conditions fell), the flags' false-discovery rate, the "4 times in 5" of every
detection limit (each test, both directions, the lone-change level, outcomes that move together, a zero
baseline under log-rank, the power gate at its worst base rate, the fault-line groups), and the coverage
of the intervals on the change and of the Wilson shares.

**How a draw runs Prove's comparison.** Twenty thousand
draws of ``multi_diff`` per design would take hours, so each draw takes its per-row p-value from Prove's
own test (``stats.fisher_test``, ``stats.mcnemar_test``, ``stats.logrank_test``, the public forms of the
tests ``multi_diff`` runs on each row), its correction from Prove's own ``diff.bh`` and ``diff.holm``, and its direction from the
rule PF4.13 and PF4.14 freeze (B's observed minus expected events under log-rank). For **every design**
the first ``SUBSET`` draws (40) are also run through ``multi_diff`` itself on the drawn runs, every row
real, and must flag the same rows the same way, count the same rows by Holm, and give the word those
rows make (``comparison_verdict()``: the direction words, or one of the two nothing-moved words when no
row counts). Where a design's log-rank rows are many, the rows that did not move are drawn from a pool
of 4,000 draws of the same truth, sampled with replacement; the subset's rows are drawn fresh. The
group limit runs ``multi_diff`` and ``tree.tree`` on every draw.

**Tolerances.** ``se`` is the binomial standard error at the claimed rate over the draws. A rate that
must be at most ``x`` is checked against ``x + 3·se``; a power that must be at least ``π`` against
``π − 3·se``, and where both arms have at least 30 runs and the limit is exact (not cautious by
construction) at most ``π + 0.05 + 3·se`` (a limit far too cautious is also wrong), ``π + 0.10 + 3·se``
under log-rank, whose power is an approximation. Seeds are fixed here.

**Runtime.** Each test records its wall time as the junit property ``seconds``, so a run's times can
be read against the suite's time budgets.

**Lanes.** The math suite (``math``), and each test is ``calibration``: it runs on main, nightly and
before a release, and on a pull request that changes the statistics.
"""

from __future__ import annotations

import math
import time
import warnings
from collections.abc import Callable, Iterator, Sequence
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
import pytest

from poisson_prove import stats
from poisson_prove.diff import bh, holm, interval_rd, interval_rd_paired, multi_diff
from poisson_prove.store import RunManifest

pytestmark = [pytest.mark.math, pytest.mark.calibration]

Q = 0.05
POWER = 0.8
DRAWS = 20_000
NULL_DRAWS = 4_000
POOL = 4_000
SUBSET = 40
STEPS = 20
NOTHING = ("no significant change", "too small to tell")


@pytest.fixture(autouse=True)
def _seconds(record_property: Callable[[str, Any], None]) -> Iterator[None]:
    start = time.perf_counter()
    yield
    record_property("seconds", round(time.perf_counter() - start, 1))


def _se(rate: float, draws: int) -> float:
    return math.sqrt(rate * (1 - rate) / draws)


def _manifest(run_id: str, salt: str = "s") -> RunManifest:
    return RunManifest(run_id=run_id, target_id="pf4", t_unit="steps", run_salt=salt,
                       axis_types={"cell": "categorical"}, backend="local", environment={})


Row = tuple[str, Sequence[str], Sequence[str], Sequence[float], Sequence[float]]


def _frames_from_counts(rows: Sequence[Row]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Store frames from per-condition outcome lists: (name, outcomes A, outcomes B, times A, times B).
    Replicate i of a condition has the same seed in both runs, so the frames are a paired design."""
    fa, fb = [], []
    for name, oa, ob, ta, tb in rows:
        for frame, outs, times in ((fa, oa, ta), (fb, ob, tb)):
            for i, (o, t) in enumerate(zip(outs, times, strict=True)):
                frame.append({"config_hash": name, "config": {"cell": name}, "replicate_index": i, "seed": 1000 + i,
                              "outcome": o, "t": float(t), "horizon": float(STEPS)})
    return pd.DataFrame(fa), pd.DataFrame(fb)


def _run_multi(fa: pd.DataFrame, fb: pd.DataFrame, method: str, events: Sequence[str] = ("fell",), q: float = Q) -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return multi_diff(fa, fb, events=list(events), method=method, q=q,
                          manifest_a=_manifest("A"), manifest_b=_manifest("B", "s" if method == "mcnemar_bh" else "t"))


# ---------- the rows of a draw, as runs ----------


def _count_row(name: str, xa: int, n_a: int, xb: int, n_b: int) -> Row:
    return (name, ["fell"] * xa + ["ok"] * (n_a - xa), ["fell"] * xb + ["ok"] * (n_b - xb), [1.0] * n_a, [1.0] * n_b)


def _paired_row(name: str, ya: np.ndarray, yb: np.ndarray) -> Row:
    n = len(ya)
    return (name, ["fell" if y else "ok" for y in ya], ["fell" if y else "ok" for y in yb], [1.0] * n, [1.0] * n)


def _timed_outcomes(t: np.ndarray, event: np.ndarray) -> list[str]:
    return ["fell" if e else ("stuck" if x < STEPS else "ok") for x, e in zip(t, event, strict=True)]


def _logrank_row(name: str, a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray]) -> Row:
    return (name, _timed_outcomes(*a), _timed_outcomes(*b), list(a[0]), list(b[0]))


def _word_of(holm_flags: np.ndarray) -> str | None:
    """PF4.20's direction words from the rows that count (no kinds here); None when no row counts."""
    up, down = bool(np.any(holm_flags > 0)), bool(np.any(holm_flags < 0))
    return "mixed" if up and down else "higher" if up else "lower" if down else None


def _through_prove(rows: Sequence[Row], method: str, events: Sequence[str], bh_flags: np.ndarray, holm_flags: np.ndarray,
                   what: Any) -> None:
    """The seeded subset: Prove's whole comparison on the drawn runs flags the same rows the
    same way, counts the same rows by Holm, and gives the word those rows make. Flags are event-major:
    every row of the first event, then of the second."""
    fa, fb = _frames_from_counts(rows)
    result = _run_multi(fa, fb, method, events=events)
    got_bh, got_holm = [], []
    for event in events:
        cells = result.by_event[event].cells.set_index("config_hash")
        for name, *_ in rows:
            sign = {"higher": 1, "lower": -1, "unchanged": 0}[cells.loc[name, "direction"]]
            got_bh.append(sign)
            got_holm.append(sign if bool(cells.loc[name, "holm"]) else 0)
    np.testing.assert_array_equal(got_bh, bh_flags, err_msg=f"flags {what}")
    np.testing.assert_array_equal(got_holm, holm_flags, err_msg=f"Holm {what}")
    word = _word_of(np.asarray(holm_flags))
    got = result.comparison_verdict()
    assert got in NOTHING if word is None else got == word, (what, word, got)


# ---------- Prove's own per-row tests, cached ----------


@lru_cache(maxsize=64)
def _fisher_table(n_a: int, n_b: int) -> np.ndarray:
    out = np.empty((n_a + 1, n_b + 1))
    for xa in range(n_a + 1):
        for xb in range(n_b + 1):
            out[xa, xb] = stats.fisher_test(xa, n_a, xb, n_b)[1]
    return out


@lru_cache(maxsize=100_000)
def _mcnemar_p(only_a: int, only_b: int) -> float:
    return float(stats.mcnemar_test(only_a, only_b)[1])


def _paired_p(ya: np.ndarray, yb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per row (axis 0) of matched indicators: Prove's paired p and B's signed discordance."""
    only_a, only_b = (ya & ~yb).sum(axis=1), (~ya & yb).sum(axis=1)
    p = np.array([_mcnemar_p(int(x), int(y)) for x, y in zip(only_a, only_b, strict=True)])
    return p, (only_b - only_a).astype(float)


def _o_minus_e_b(a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray]) -> float:
    """B's observed minus expected events, the sign PF4.13 gives the log-rank direction."""
    (t_a, e_a), (t_b, e_b) = a, b
    total = 0.0
    for x in np.unique(np.concatenate([t_a[e_a], t_b[e_b]])):
        n_a, n_b = np.sum(t_a >= x), np.sum(t_b >= x)
        d_b = np.sum((t_b == x) & e_b)
        total += d_b - n_b * (np.sum((t_a == x) & e_a) + d_b) / (n_a + n_b)
    return float(total)


def _logrank(a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray]) -> tuple[float, float]:
    """Prove's log-rank p for the row and its signed direction."""
    return float(stats.logrank_test(a[0], a[1], b[0], b[1])[1]), _o_minus_e_b(a, b)


def _flags(p: np.ndarray, signed: np.ndarray, correction: Callable[..., np.ndarray]) -> np.ndarray:
    """+1 a row flagged upward, -1 downward, 0 not flagged, by Prove's correction over the row."""
    adjusted = correction(np.asarray(p, dtype=float), Q)
    return np.where(adjusted < Q, np.sign(signed), 0).astype(int)


def _logrank_arm(rng: np.random.Generator, n: int, h_event: np.ndarray, h_other: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """n runs over the steps: at each step the event with chance h_event[s], else another ending with
    chance h_other[s] among those that did not have the event; the rest reach the horizon."""
    alive = np.ones(n, bool)
    t = np.full(n, float(STEPS))
    event = np.zeros(n, bool)
    for s in range(STEPS):
        u = rng.random(n)
        ev = alive & (u < h_event[s])
        ot = alive & ~ev & (rng.random(n) < h_other[s])
        t[ev | ot] = s + 1
        event[ev] = True
        alive &= ~(ev | ot)
    return t, event


def _per_step(share: float) -> np.ndarray:
    """The constant per-step hazard that reaches ``share`` by the horizon on its own."""
    return np.full(STEPS, 1 - (1 - share) ** (1 / STEPS)) if share else np.zeros(STEPS)


# ---------- PF4.36: the verdict and the flags ----------


@pytest.mark.parametrize("method", ["fisher_bh", "mcnemar_bh"])
@pytest.mark.parametrize("rows,base", [(18, 0.3), (50, 0.13)], ids=["18-rows", "50-rows"])
def test_pf4_36_with_nothing_changed_the_word_names_a_change_at_most_q_of_the_time(method: str, rows: int, base: float) -> None:
    n = 100
    rng = np.random.default_rng(3600 + rows + (method == "mcnemar_bh"))
    moved = 0
    for d in range(NULL_DRAWS):
        if method == "fisher_bh":
            xa, xb = rng.binomial(n, base, rows), rng.binomial(n, base, rows)
            p, signed = _fisher_table(n, n)[xa, xb], (xb - xa).astype(float)
            drawn = [_count_row(f"r{j:03d}", int(xa[j]), n, int(xb[j]), n) for j in range(rows)] if d < SUBSET else []
        else:
            ya, yb = rng.random((rows, n)) < base, rng.random((rows, n)) < base
            p, signed = _paired_p(ya, yb)
            drawn = [_paired_row(f"r{j:03d}", ya[j], yb[j]) for j in range(rows)] if d < SUBSET else []
        counted = _flags(p, signed, holm)
        moved += int(np.any(counted != 0))
        if drawn:
            _through_prove(drawn, method, ("fell",), _flags(p, signed, bh), counted, (method, rows, d))
    rate = moved / NULL_DRAWS
    assert rate <= Q + 3 * _se(Q, NULL_DRAWS), rate


def test_pf4_36_with_nothing_changed_under_logrank_with_a_competing_outcome_the_word_moves_at_most_q_of_the_time() -> None:
    n, rows = 100, 18
    rng = np.random.default_rng(3618)
    h_event, h_other = _per_step(0.3), _per_step(0.2)
    moved = 0
    for d in range(NULL_DRAWS):
        arms = [(_logrank_arm(rng, n, h_event, h_other), _logrank_arm(rng, n, h_event, h_other)) for _ in range(rows)]
        tested = [_logrank(a, b) for a, b in arms]
        p, signed = np.array([x[0] for x in tested]), np.array([x[1] for x in tested])
        counted = _flags(p, signed, holm)
        moved += int(np.any(counted != 0))
        if d < SUBSET:
            drawn = [_logrank_row(f"r{j:03d}", a, b) for j, (a, b) in enumerate(arms)]
            _through_prove(drawn, "logrank_bh", ("fell",), _flags(p, signed, bh), counted, ("logrank", d))
    rate = moved / NULL_DRAWS
    assert rate <= Q + 3 * _se(Q, NULL_DRAWS), rate


@pytest.mark.parametrize("method", ["fisher_bh", "mcnemar_bh", "logrank_bh"])
def test_pf4_36_when_some_conditions_truly_fell_the_word_rarely_names_a_rise(method: str) -> None:
    """Argon's case: ten of fifty conditions truly fell (0.45 to 0.15 by the horizon), forty did not move
    (0.3). The word names a rise (higher or mixed here) only when a row passes Holm upward; with
    Benjamini-Hochberg's flags the ten true falls lift that rate, which is why the word reads Holm. Under
    log-rank the rows come from pools of 4,000 draws of each truth (the subset's are drawn fresh)."""
    n, rows, true = 100, 50, 10
    p_a = np.array([0.45] * true + [0.3] * (rows - true))
    p_b = np.array([0.15] * true + [0.3] * (rows - true))
    rng = np.random.default_rng(3650 + {"fisher_bh": 0, "mcnemar_bh": 1, "logrank_bh": 2}[method])
    pools: dict[str, np.ndarray] = {}
    if method == "logrank_bh":
        for key, (sa, sb) in {"fell": (0.45, 0.15), "same": (0.3, 0.3)}.items():
            pools[key] = np.array([_logrank(_logrank_arm(rng, n, _per_step(sa), _per_step(0)),
                                            _logrank_arm(rng, n, _per_step(sb), _per_step(0))) for _ in range(POOL)])
    rise_word = flagged_rise = 0
    for d in range(NULL_DRAWS):
        drawn: list[Row] = []
        if method == "fisher_bh":
            xa, xb = rng.binomial(n, p_a), rng.binomial(n, p_b)
            p, signed = _fisher_table(n, n)[xa, xb], (xb - xa).astype(float)
            if d < SUBSET:
                drawn = [_count_row(f"r{j:03d}", int(xa[j]), n, int(xb[j]), n) for j in range(rows)]
        elif method == "mcnemar_bh":
            ya = rng.random((rows, n)) < p_a[:, None]
            yb = rng.random((rows, n)) < p_b[:, None]
            p, signed = _paired_p(ya, yb)
            if d < SUBSET:
                drawn = [_paired_row(f"r{j:03d}", ya[j], yb[j]) for j in range(rows)]
        elif d < SUBSET:
            arms = [(_logrank_arm(rng, n, _per_step(p_a[j]), _per_step(0)), _logrank_arm(rng, n, _per_step(p_b[j]), _per_step(0)))
                    for j in range(rows)]
            tested = np.array([_logrank(a, b) for a, b in arms])
            p, signed = tested[:, 0], tested[:, 1]
            drawn = [_logrank_row(f"r{j:03d}", a, b) for j, (a, b) in enumerate(arms)]
        else:
            tested = np.concatenate([pools["fell"][rng.integers(0, POOL, true)], pools["same"][rng.integers(0, POOL, rows - true)]])
            p, signed = tested[:, 0], tested[:, 1]
        counted, flagged = _flags(p, signed, holm), _flags(p, signed, bh)
        rise_word += int(np.any(counted > 0))
        flagged_rise += int(np.any(flagged[true:] > 0))
        if drawn:
            _through_prove(drawn, method, ("fell",), flagged, counted, (method, d))
    rate = rise_word / NULL_DRAWS
    assert rate <= Q + 3 * _se(Q, NULL_DRAWS), rate
    # Read from the flags instead, the word would name a rise past the same bound.
    assert flagged_rise / NULL_DRAWS > Q + 3 * _se(Q, NULL_DRAWS), flagged_rise


def _two_cause_arm(rng: np.random.Generator, n: int, fell: float, stuck: float) -> tuple[np.ndarray, np.ndarray]:
    """n runs over the steps with two causes, each with a constant per-step hazard that alone would reach
    the given share: at each step 'fell' first, then 'stuck' among the rest; the rest end 'ok'."""
    h_f, h_s = _per_step(fell)[0], _per_step(stuck)[0]
    alive = np.ones(n, bool)
    t = np.full(n, float(STEPS))
    out = np.full(n, "ok", dtype=object)
    for s in range(STEPS):
        f = alive & (rng.random(n) < h_f)
        k = alive & ~f & (rng.random(n) < h_s)
        t[f | k] = s + 1
        out[f], out[k] = "fell", "stuck"
        alive &= ~(f | k)
    return t, out


def _two_cause_tests(a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray]) -> tuple[float, float, float, float]:
    """Prove's log-rank on each of the two events, the other a competing ending: (p, signed) for 'fell'
    then for 'stuck'."""
    out: list[float] = []
    for event in ("fell", "stuck"):
        out += list(_logrank((a[0], a[1] == event), (b[0], b[1] == event)))
    return out[0], out[1], out[2], out[3]


@pytest.mark.parametrize("method", ["fisher_bh", "mcnemar_bh", "logrank_bh"])
@pytest.mark.parametrize("share", [0.1, 0.5])
def test_pf4_36_the_flags_false_discovery_rate_holds_with_two_competing_events(method: str, share: float) -> None:
    """Thirty conditions, two events tested together (60 rows). Fisher and the paired test: in a share of
    the conditions 'fell' moved from 0.2 to 0.45 and so 'stuck' fell with it, each run multinomial over
    fell, stuck, ok, so both rows of a moved condition are true changes. Log-rank: in those conditions
    only the hazard of 'fell' rose (to reach 0.45 alone), so the row of 'stuck', whose cause-specific
    hazard did not move while its share fell, is a true null (conditions from pools of 4,000 each).
    Averaged over draws, the share of flagged rows that are false is at most q."""
    n, conds = 100, 30
    moved = int(round(share * conds))
    rng = np.random.default_rng(3660 + moved + {"fisher_bh": 0, "mcnemar_bh": 100, "logrank_bh": 200}[method])
    probs_a = np.array([0.2, 0.3, 0.5])
    probs_b_moved = np.array([0.45, 0.15, 0.4])
    names = np.array(["fell", "stuck", "ok"], dtype=object)
    table = _fisher_table(n, n)
    if method == "logrank_bh":
        truth = np.concatenate([np.arange(conds) < moved, np.zeros(conds, bool)])
        pools = {key: np.array([_two_cause_tests(_two_cause_arm(rng, n, 0.2, 0.3), _two_cause_arm(rng, n, fell_b, 0.3))
                                for _ in range(POOL)]) for key, fell_b in (("moved", 0.45), ("same", 0.2))}
    else:
        truth = np.concatenate([np.arange(conds) < moved, np.arange(conds) < moved])
    fdp = []
    for d in range(NULL_DRAWS):
        drawn: list[Row] = []
        if method == "fisher_bh":
            ca = rng.multinomial(n, probs_a, size=conds)
            cb = np.array([rng.multinomial(n, probs_b_moved if c < moved else probs_a) for c in range(conds)])
            p = np.concatenate([table[ca[:, 0], cb[:, 0]], table[ca[:, 1], cb[:, 1]]])
            signed = np.concatenate([cb[:, 0] - ca[:, 0], cb[:, 1] - ca[:, 1]]).astype(float)
            if d < SUBSET:
                drawn = [(f"c{c:02d}", list(np.repeat(names, ca[c])), list(np.repeat(names, cb[c])), [1.0] * n, [1.0] * n)
                         for c in range(conds)]
        elif method == "mcnemar_bh":
            oa = rng.choice(3, size=(conds, n), p=probs_a)
            ob = np.stack([rng.choice(3, size=n, p=probs_b_moved if c < moved else probs_a) for c in range(conds)])
            p_f, s_f = _paired_p(oa == 0, ob == 0)
            p_s, s_s = _paired_p(oa == 1, ob == 1)
            p, signed = np.concatenate([p_f, p_s]), np.concatenate([s_f, s_s])
            if d < SUBSET:
                drawn = [(f"c{c:02d}", list(names[oa[c]]), list(names[ob[c]]), [1.0] * n, [1.0] * n) for c in range(conds)]
        else:
            if d < SUBSET:
                arms = [(_two_cause_arm(rng, n, 0.2, 0.3), _two_cause_arm(rng, n, 0.45 if c < moved else 0.2, 0.3)) for c in range(conds)]
                tested = np.array([_two_cause_tests(a, b) for a, b in arms])
                drawn = [(f"c{c:02d}", list(a[1]), list(b[1]), list(a[0]), list(b[0])) for c, (a, b) in enumerate(arms)]
            else:
                tested = np.concatenate([pools["moved"][rng.integers(0, POOL, moved)], pools["same"][rng.integers(0, POOL, conds - moved)]])
            p = np.concatenate([tested[:, 0], tested[:, 2]])
            signed = np.concatenate([tested[:, 1], tested[:, 3]])
        flagged = _flags(p, signed, bh)
        r = int(np.count_nonzero(flagged))
        fdp.append(0.0 if r == 0 else float(np.count_nonzero((flagged != 0) & ~truth)) / r)
        if drawn:
            _through_prove(drawn, method, ("fell", "stuck"), flagged, _flags(p, signed, holm), (method, share, d))
    rate = float(np.mean(fdp))
    assert rate <= Q + 3 * float(np.std(fdp)) / math.sqrt(NULL_DRAWS), rate


# ---------- PF4.26: every limit's "4 times in 5" ----------


def _printed_limit(events_a: int, n_a: int, n_b: int, rows: int, method: str = "fisher_bh") -> tuple[float | None, float | None]:
    """The limits Prove prints for one row of a family of ``rows`` (through q / rows; the stats file's reading)."""
    fa, fb = _frames_from_counts([_count_row("c", events_a, n_a, min(events_a, n_b), n_b)])
    row = _run_multi(fa, fb, method, q=Q / rows).by_event["fell"].cells.iloc[0]
    rise, fall = row["mde_rise"], row["mde_fall"]
    return (None if rise is None or (isinstance(rise, float) and math.isnan(rise)) else float(rise),
            None if fall is None or (isinstance(fall, float) and math.isnan(fall)) else float(fall))


def _check_power(caught: int, draws: int, both_large: bool, what: Any, slack: float = 0.05) -> None:
    rate = caught / draws
    se = _se(POWER, draws)
    assert rate >= POWER - 3 * se, (what, rate)
    if both_large:
        assert rate <= POWER + slack + 3 * se, (what, rate)


FISHER_GRID = [(na, nb, base, rows) for na, nb in ((4, 4), (16, 16), (100, 100), (194, 194), (100, 20), (20, 100))
               for base in (0.05, 0.13, 0.4, 0.5, 0.9) for rows in (1, 9, 18, 50)]


def test_pf4_26_the_fisher_grid_has_a_limit_to_check_in_most_designs() -> None:
    """The grid of PF4.26 is 120 designs by two directions; at least 100 directions have a limit (the
    rest are checked by the stats file's notes)."""
    limits = [v for na, nb, base, rows in FISHER_GRID for v in _printed_limit(round(base * na), na, nb, rows)]
    assert sum(v is not None for v in limits) >= 100, sum(v is not None for v in limits)


@pytest.mark.parametrize("na,nb,base,rows", FISHER_GRID, ids=[f"{na}x{nb}-{base}-{rows}" for na, nb, base, rows in FISHER_GRID])
def test_pf4_26_fishers_limits_are_caught_four_times_in_five_by_the_flag_prove_raises(na: int, nb: int, base: float, rows: int) -> None:
    """Both directions: the moved row at exactly its printed limit, the other M - 1 rows unmoved at the
    same baseline; a direction with no limit has nothing to check."""
    i = FISHER_GRID.index((na, nb, base, rows))
    events_a = round(base * na)
    p_hat = events_a / na
    rise, fall = _printed_limit(events_a, na, nb, rows)
    table = _fisher_table(na, nb)
    for way, delta in (("rise", rise), ("fall", fall)):
        if delta is None:
            continue
        p_b = np.full(rows, p_hat)
        p_b[0] = p_hat + delta if way == "rise" else p_hat - delta
        rng = np.random.default_rng(2600 + 2 * i + (way == "fall"))
        xa = rng.binomial(na, p_hat, size=(DRAWS, rows))
        xb = rng.binomial(nb, np.clip(p_b, 0.0, 1.0), size=(DRAWS, rows))
        p = table[xa, xb]
        signed = xb / nb - xa / na
        flags = np.stack([_flags(p[d], signed[d], bh) for d in range(DRAWS)])
        for d in range(SUBSET):
            drawn = [_count_row(f"r{j:03d}", int(xa[d, j]), na, int(xb[d, j]), nb) for j in range(rows)]
            _through_prove(drawn, "fisher_bh", ("fell",), flags[d], _flags(p[d], signed[d], holm), (na, nb, base, rows, way, d))
        want = 1 if way == "rise" else -1
        _check_power(int((flags[:, 0] == want).sum()), DRAWS, min(na, nb) >= 30, (na, nb, base, rows, way, delta))


PAIRED_GRID = [(pairs, base, rows) for pairs in (100, 194) for base in (0.13, 0.5, 0.6) for rows in (9, 18)]


@pytest.mark.parametrize("pairs,base,rows", PAIRED_GRID, ids=[f"{p}-{b}-{r}" for p, b, r in PAIRED_GRID])
def test_pf4_26_the_paired_limits_are_caught_four_times_in_five(pairs: int, base: float, rows: int) -> None:
    i = PAIRED_GRID.index((pairs, base, rows))
    events_a = round(base * pairs)
    p_hat = events_a / pairs
    rise, fall = _printed_limit(events_a, pairs, pairs, rows, method="mcnemar_bh")
    for way, delta in (("rise", rise), ("fall", fall)):
        if delta is None:
            continue
        rng = np.random.default_rng(2700 + 2 * i + (way == "fall"))
        target = p_hat + delta if way == "rise" else p_hat - delta
        caught = 0
        for d in range(DRAWS):
            ya = rng.random((rows, pairs)) < p_hat
            yb = rng.random((rows, pairs)) < p_hat
            yb[0] = rng.random(pairs) < target
            p, signed = _paired_p(ya, yb)
            flags = _flags(p, signed, bh)
            caught += int(flags[0] == (1 if way == "rise" else -1))
            if d < SUBSET:
                drawn = [_paired_row(f"r{j:03d}", ya[j], yb[j]) for j in range(rows)]
                _through_prove(drawn, "mcnemar_bh", ("fell",), flags, _flags(p, signed, holm), (pairs, base, rows, way, d))
        _check_power(caught, DRAWS, True, (pairs, base, rows, way, delta))


@pytest.mark.parametrize("base,competing", [(0.2, 0.0), (0.5, 0.0), (0.2, 0.2), (0.5, 0.2)],
                         ids=["0.2", "0.5", "0.2-competing", "0.5-competing"])
def test_pf4_26_the_logrank_limits_are_caught_four_times_in_five(base: float, competing: float) -> None:
    """100 a side over 20 steps, 18 rows, both directions. A's template is one seeded draw and the truth
    is its per-step hazards; B's event hazard is the discrete mapping at the printed limit's hazard ratio
    (PF4.43: the rise's ``mde_hr``, the fall's grid point recovered from its printed change); B's other
    endings are A's. The 17 unmoved rows' (p, direction) come from a pool of 4,000 draws of the same
    truth, sampled with replacement, except in the subset, where every row is drawn fresh."""
    from test_pf4_stats import _fall_step

    n, rows = 100, 18
    rng = np.random.default_rng(int(2800 + base * 100 + competing * 10))
    ta, ea = _logrank_arm(rng, n, _per_step(base), _per_step(competing))
    fa, fb = _frames_from_counts([("c", _timed_outcomes(ta, ea), _timed_outcomes(ta, ea), list(ta), list(ta))])
    row = _run_multi(fa, fb, "logrank_bh", q=Q / rows).by_event["fell"].cells.iloc[0]
    # A's empirical hazards are the template, and the truth here.
    tmpl_e, tmpl_o = np.zeros(STEPS), np.zeros(STEPS)
    for s in range(STEPS):
        at_risk = np.sum(ta >= s + 1)
        if at_risk:
            had = np.sum((ta == s + 1) & ea)
            tmpl_e[s] = had / at_risk
            rest = at_risk - had
            tmpl_o[s] = np.sum((ta == s + 1) & ~ea & (ta < STEPS)) / rest if rest else 0.0
    k = _fall_step(ta, ea, n, float(row["mde_fall"]), float(ea.mean()))
    assert k is not None
    pool = np.array([_logrank(_logrank_arm(rng, n, tmpl_e, tmpl_o), _logrank_arm(rng, n, tmpl_e, tmpl_o)) for _ in range(POOL)])
    for way, theta in (("rise", float(row["mde_hr"])), ("fall", math.exp(-k * 1e-3))):
        h_b = 1 - (1 - tmpl_e) ** theta
        want = 1 if way == "rise" else -1
        caught = 0
        for d in range(DRAWS):
            a, b = _logrank_arm(rng, n, tmpl_e, tmpl_o), _logrank_arm(rng, n, h_b, tmpl_o)
            if d < SUBSET:
                others = [(_logrank_arm(rng, n, tmpl_e, tmpl_o), _logrank_arm(rng, n, tmpl_e, tmpl_o)) for _ in range(rows - 1)]
                tested = np.array([_logrank(a, b)] + [_logrank(x, y) for x, y in others])
            else:
                tested = np.concatenate([[_logrank(a, b)], pool[rng.integers(0, POOL, rows - 1)]])
            flags = _flags(tested[:, 0], tested[:, 1], bh)
            caught += int(flags[0] == want)
            if d < SUBSET:
                drawn = [_logrank_row("r000", a, b)] + [_logrank_row(f"r{j + 1:03d}", x, y) for j, (x, y) in enumerate(others)]
                _through_prove(drawn, "logrank_bh", ("fell",), flags, _flags(tested[:, 0], tested[:, 1], holm), (base, competing, way, d))
        # The expected-moments power is an approximation that errs cautious when few
        # events are expected (a fall from 0.2 with a competing outcome is caught about 86% of the
        # time), so the upper bound under log-rank allows 0.10.
        _check_power(caught, DRAWS, True, (base, competing, way, theta), slack=0.10)


@pytest.mark.parametrize("n,other,spread,rows", [(100, 0, False, 18), (40, 0, False, 9), (100, 0, True, 18), (100, 40, True, 18)],
                         ids=["100-at-the-horizon", "40-at-the-horizon", "100-spread", "100-spread-with-40-other"])
def test_pf4_43_the_zero_baseline_limit_is_caught_four_times_in_five(n: int, other: int, spread: bool, rows: int) -> None:
    """No event in A; ``other`` of A's runs ended in another outcome at step 1 (each run does so with that
    chance in both arms' truth). B's events come with chance delta, the printed limit, overall: at the
    horizon (the model's own case, so the rate is held to both bounds) or at a uniform step from 2 to 20
    among the runs still at risk (where events at the horizon are the worst case, so only the lower bound
    applies). The 17 unmoved rows have no event in either arm."""
    arm = [(i, "stuck", 1.0) if i < other else (i, "ok", float(STEPS)) for i in range(n)]
    fa, fb = _frames_from_counts([("c", [o for _, o, _ in arm], [o for _, o, _ in arm], [t for _, _, t in arm], [t for _, _, t in arm])])
    delta = float(_run_multi(fa, fb, "logrank_bh", q=Q / rows).by_event["fell"].cells.iloc[0]["mde_rise"])
    c = other / n
    rng = np.random.default_rng(4300 + n + other + spread)

    def draw(moved: bool) -> tuple[np.ndarray, np.ndarray]:
        stuck = rng.random(n) < c
        t = np.where(stuck, 1.0, float(STEPS))
        event = np.zeros(n, bool)
        if moved:
            event = ~stuck & (rng.random(n) < delta / (1 - c))
            if spread:
                t = np.where(event, rng.integers(2, STEPS + 1, n).astype(float), t)
        return t, event

    quiet = (np.full(n, float(STEPS)), np.zeros(n, bool))
    caught = 0
    for d in range(DRAWS):
        a, b = draw(False), draw(True)
        p, signed = _logrank(a, b)
        flags = _flags(np.concatenate([[p], np.ones(rows - 1)]), np.concatenate([[signed], np.zeros(rows - 1)]), bh)
        caught += int(flags[0] == 1)
        if d < SUBSET:
            drawn = [_logrank_row("r000", a, b)] + [_logrank_row(f"r{j:03d}", quiet, quiet) for j in range(1, rows)]
            counted = _flags(np.concatenate([[p], np.ones(rows - 1)]), np.concatenate([[signed], np.zeros(rows - 1)]), holm)
            _through_prove(drawn, "logrank_bh", ("fell",), flags, counted, (n, other, spread, d))
    _check_power(caught, DRAWS, n >= 30 and not spread, (n, other, spread, rows, delta))


def test_pf4_47_rows_that_move_together_are_caught_at_their_limits_and_the_verdict_at_its_own() -> None:
    """Nine conditions, two complementary events ('fell' and 'ok'): 18 rows. Moving one condition by the
    printed flag limit (at 2q/M) flags its row four times in five; moving it by the verdict limit (at
    q/M) makes Holm count it four times in five."""
    n, conds = 100, 9
    events_a = 40
    fa, fb = _frames_from_counts([_count_row(f"c{j}", events_a, n, events_a, n) for j in range(conds)])
    cell = _run_multi(fa, fb, "fisher_bh", events=("fell", "ok")).by_event["fell"].cells.iloc[0]
    assert cell["mde_moves_with"] == "ok"
    table = _fisher_table(n, n)
    for key, correction in (("mde_rise", bh), ("mde_rise_verdict", holm)):
        delta = float(cell[key])
        rng = np.random.default_rng(4700 + (key == "mde_rise"))
        xa = rng.binomial(n, events_a / n, size=(DRAWS, conds))
        xb = rng.binomial(n, events_a / n, size=(DRAWS, conds))
        xb[:, 0] = rng.binomial(n, events_a / n + delta, size=DRAWS)
        p_fell = table[xa, xb]
        p_ok = table[n - xa, n - xb]
        caught = 0
        for d in range(DRAWS):
            p = np.concatenate([p_fell[d], p_ok[d]])
            signed = np.concatenate([xb[d] - xa[d], xa[d] - xb[d]]).astype(float)
            caught += int(_flags(p, signed, correction)[0] == 1)
            if d < SUBSET:
                drawn = [_count_row(f"c{j}", int(xa[d, j]), n, int(xb[d, j]), n) for j in range(conds)]
                _through_prove(drawn, "fisher_bh", ("fell", "ok"), _flags(p, signed, bh), _flags(p, signed, holm), (key, d))
        _check_power(caught, DRAWS, True, key)


def _paired_power_at(base: float, pairs: int, level: float, change: float, rise: bool) -> float:
    """The paired test's exact power with independent arms (the gate's model), summed over the discordant
    pairs with Prove's own paired p."""
    from scipy.stats import binom

    p01 = (1 - base) * (base + change) if rise else (1 - base) * (base - change)
    p10 = base * (1 - base - change) if rise else base * (1 - base + change)
    s = p01 + p10
    total = 0.0
    for d in range(1, pairs + 1):
        w = binom.pmf(d, pairs, s)
        if w < 1e-15:
            continue
        for larger in range((d // 2) + 1, d + 1):
            only_b, only_a = (larger, d - larger) if rise else (d - larger, larger)
            if _mcnemar_p(only_a, only_b) < level:
                total += w * binom.pmf(larger, d, (p01 if rise else p10) / s)
    return total


@pytest.mark.parametrize("test", ["fisher", "mcnemar"])
def test_pf4_30_the_gates_limit_is_caught_four_times_in_five_at_its_worst_base_rate(test: str) -> None:
    """The quickstart's design, 9 conditions by 2 failures at 194 replicates: the worst base rate on the
    gate's 0.005 grid (found here with Prove's own per-row tests), and there a change of exactly the
    accepted 0.20 flagged four times in five by the flag Prove raises."""
    from scipy.stats import binom

    n, rows, change, level = 194, 18, 0.20, Q / 18
    table = _fisher_table(n, n)
    worst = (2.0, 0.0, True)
    for base in np.round(np.arange(0.0, 1.0 + 1e-9, 0.005), 3):
        for rise in (True, False):
            if (rise and base > 1 - change + 1e-9) or (not rise and base < change - 1e-9):
                continue
            if test == "fisher":
                x = np.arange(n + 1)
                moved = (x[None, :] > x[:, None]) if rise else (x[None, :] < x[:, None])
                region = (table < level) & moved
                target = base + change if rise else base - change
                power = float(binom.pmf(x, n, base) @ region.astype(float) @ binom.pmf(x, n, target))
            else:
                power = _paired_power_at(base, n, level, change, rise)
            if power < worst[0] - 1e-12:  # ties go to the lower base rate, a rise first (PF4.48a)
                worst = (power, base, rise)
    power, base, rise = worst
    assert power >= POWER, worst
    rng = np.random.default_rng(3000 + (test == "mcnemar"))
    target = base + change if rise else base - change
    method = "fisher_bh" if test == "fisher" else "mcnemar_bh"
    caught = 0
    for d in range(DRAWS):
        ya = rng.random((rows, n)) < base
        yb = rng.random((rows, n)) < base
        yb[0] = rng.random(n) < target
        if test == "fisher":
            xa, xb = ya.sum(axis=1), yb.sum(axis=1)
            p, signed = table[xa, xb], (xb - xa).astype(float)
        else:
            p, signed = _paired_p(ya, yb)
        flags = _flags(p, signed, bh)
        caught += int(flags[0] == (1 if rise else -1))
        if d < SUBSET:
            drawn = [_paired_row(f"r{j:03d}", ya[j], yb[j]) for j in range(rows)]
            _through_prove(drawn, method, ("fell",), flags, _flags(p, signed, holm), (test, d))
    _check_power(caught, DRAWS, True, (test, base, rise, power))


# ---------- PF4.45: the group limit, the tree's own flag, unconditionally ----------


@pytest.mark.slow
@pytest.mark.parametrize("design", ["even", "uneven"])
def test_pf4_45_the_group_limit_is_caught_four_times_in_five_root_and_group_together(design: str) -> None:
    """Four groups of three conditions, 80 runs a side; 'even' at a baseline of 0.3 everywhere,
    'uneven' with group x's conditions at 0.05, 0.3 and 0.6. Group x moves by its printed limit in every
    condition (each capped at its room); a draw counts when the root and group x both reject."""
    from poisson_prove import tree

    n = 80
    bases = {"even": {g: [0.3, 0.3, 0.3] for g in "xyzw"},
             "uneven": {"x": [0.05, 0.3, 0.6], "y": [0.3] * 3, "z": [0.3] * 3, "w": [0.3] * 3}}[design]
    ma = RunManifest(run_id="A", target_id="pf4", t_unit="steps", run_salt="s", axis_types={"g": "categorical", "i": "categorical"},
                     backend="local", environment={})
    mb = RunManifest(run_id="B", target_id="pf4", t_unit="steps", run_salt="t", axis_types={"g": "categorical", "i": "categorical"},
                     backend="local", environment={})

    def frame(rates: dict[str, list[float]], rng: np.random.Generator | None) -> pd.DataFrame:
        rows = []
        for g, rs in rates.items():
            for i, r in enumerate(rs):
                k = round(r * n) if rng is None else int(rng.binomial(n, r))
                for rep in range(n):
                    rows.append({"config_hash": f"{g}{i}", "config": {"g": g, "i": i}, "replicate_index": rep, "seed": rep,
                                 "outcome": "fell" if rep < k else "ok", "t": 1.0 if rep < k else 10.0, "horizon": 10.0})
        return pd.DataFrame(rows)

    # A group's limit reads arm A only; the tree builds its groups only when the root rejected, so the
    # printed limit is read from a pair whose group w moved far and x did not.
    template = frame(bases, None)
    shifted = frame({g: [min(1.0, r + 0.5) if g == "w" else r for r in rs] for g, rs in bases.items()}, None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        multi = multi_diff(template, shifted, events=["fell"], method="fisher_bh", manifest_a=ma, manifest_b=mb)
        shown = tree.tree(template, shifted, multi, manifest_a=ma, manifest_b=mb, by="g", n_permutations=999, seed=0,
                          max_group_mde=0.99)
    assert shown.root.rejects and shown.grouping.key == "g"
    assert shown.fault_lines.mde_basis == "unconditional"
    delta = float({g.label: g for g in shown.fault_lines.groups}["x"].mde)
    moved = {g: [min(1.0, r + delta) if g == "x" else r for r in rs] for g, rs in bases.items()}
    rng = np.random.default_rng(4500 + (design == "uneven"))
    draws = 1_000
    caught = 0
    for d in range(draws):
        fa, fb = frame(bases, rng), frame(moved, rng)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = multi_diff(fa, fb, events=["fell"], method="fisher_bh", manifest_a=ma, manifest_b=mb)
            t = tree.tree(fa, fb, m, manifest_a=ma, manifest_b=mb, by="g", n_permutations=999, seed=d, max_group_mde=0.99)
        groups = {g.label: g for g in t.fault_lines.groups}
        caught += int(bool(t.root.rejects) and bool(groups["x"].rejects))
    rate = caught / draws
    assert rate >= POWER - 3 * _se(POWER, draws), rate


@pytest.mark.slow
def test_pf4_45_with_two_events_the_group_limit_holds_whichever_event_moves() -> None:
    """Four groups of three conditions, 80 a side, two events compared ('fell' at 0.05,
    'stuck' at 0.3 in every condition). The printed limit is the larger of the two events' limits, so
    moving only the harder event ('stuck') of group x by it is still caught four times in five, root
    and group together."""
    from poisson_prove import tree

    n = 80
    groups = "xyzw"
    ma = RunManifest(run_id="A", target_id="pf4", t_unit="steps", run_salt="s", axis_types={"g": "categorical", "i": "categorical"},
                     backend="local", environment={})
    mb = RunManifest(run_id="B", target_id="pf4", t_unit="steps", run_salt="t", axis_types={"g": "categorical", "i": "categorical"},
                     backend="local", environment={})

    def frame(rates: dict[str, tuple[float, float]], rng: np.random.Generator | None) -> pd.DataFrame:
        rows = []
        for g in groups:
            fell, stuck = rates[g]
            for i in range(3):
                if rng is None:
                    k_f, k_s = round(fell * n), round(stuck * n)
                else:
                    k_f, k_s, _ = rng.multinomial(n, [fell, stuck, 1 - fell - stuck])
                for rep in range(n):
                    outcome = "fell" if rep < k_f else "stuck" if rep < k_f + k_s else "ok"
                    rows.append({"config_hash": f"{g}{i}", "config": {"g": g, "i": i}, "replicate_index": rep, "seed": rep,
                                 "outcome": outcome, "t": 1.0 if outcome != "ok" else 10.0, "horizon": 10.0})
        return pd.DataFrame(rows)

    base = {g: (0.05, 0.3) for g in groups}
    template = frame(base, None)
    shifted = frame({**base, "w": (0.05, 0.8)}, None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        multi = multi_diff(template, shifted, events=["fell", "stuck"], method="fisher_bh", manifest_a=ma, manifest_b=mb)
        shown = tree.tree(template, shifted, multi, manifest_a=ma, manifest_b=mb, by="g", n_permutations=999, seed=0,
                          max_group_mde=0.99)
    assert shown.root.rejects and shown.grouping.key == "g"
    delta = float({g.label: g for g in shown.fault_lines.groups}["x"].mde)
    moved = {**base, "x": (0.05, min(0.95, 0.3 + delta))}
    rng = np.random.default_rng(4510)
    draws = 1_000
    caught = 0
    for d in range(draws):
        fa, fb = frame(base, rng), frame(moved, rng)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = multi_diff(fa, fb, events=["fell", "stuck"], method="fisher_bh", manifest_a=ma, manifest_b=mb)
            t = tree.tree(fa, fb, m, manifest_a=ma, manifest_b=mb, by="g", n_permutations=999, seed=d, max_group_mde=0.99)
        found = {g.label: g for g in t.fault_lines.groups} if t.grouping.key == "g" else {}
        caught += int(bool(t.root.rejects) and "x" in found and bool(found["x"].rejects))
    rate = caught / draws
    assert rate >= POWER - 3 * _se(POWER, draws), rate


# ---------- PF4.42, PF4.51: the intervals' coverage ----------


@pytest.mark.parametrize("method", ["miettinen-nurminen", "tango"])
def test_pf4_51_each_interval_covers_its_truth_at_its_level(method: str) -> None:
    """Over a grid of true rates, 40 a side, at the levels Prove prints (0.95, 1 - 0.05/18): the
    interval Prove computes covers the true change at least its level less 0.01, less 3 se."""
    rng = np.random.default_rng(5100 + (method == "tango"))
    n, draws = 40, 2_000
    for level in (0.95, 1 - Q / 18):
        for pa, pb in ((0.1, 0.1), (0.2, 0.4), (0.5, 0.5), (0.05, 0.25), (0.7, 0.4)):
            covered = 0
            for _ in range(draws):
                if method == "miettinen-nurminen":
                    ea, eb = rng.binomial(n, pa), rng.binomial(n, pb)
                    lo, hi = interval_rd(int(ea), n, int(eb), n, alpha=1 - level)
                else:
                    ya, yb = rng.random(n) < pa, rng.random(n) < pb
                    lo, hi = interval_rd_paired(int((ya & ~yb).sum()), int((~ya & yb).sum()), n, alpha=1 - level)
                covered += int(lo <= pb - pa <= hi)
            rate = covered / draws
            assert rate >= level - 0.01 - 3 * _se(level, draws), (method, level, pa, pb, rate)


def test_pf4_51_with_nothing_flagged_the_intervals_cover_together() -> None:
    """Built at 1 - q/M, the level Prove prints when nothing is flagged, all M intervals cover their true
    changes together at least 1 - q of the time (Bonferroni)."""
    n, rows, draws = 60, 9, 2_000
    rng = np.random.default_rng(5200)
    pa = np.linspace(0.1, 0.5, rows)
    pb = pa + 0.04
    level = 1 - Q / rows
    all_cover = 0
    for _ in range(draws):
        ea, eb = rng.binomial(n, pa), rng.binomial(n, pb)
        ok = True
        for j in range(rows):
            lo, hi = interval_rd(int(ea[j]), n, int(eb[j]), n, alpha=1 - level)
            ok &= lo <= pb[j] - pa[j] <= hi
        all_cover += int(ok)
    rate = all_cover / draws
    assert rate >= 1 - Q - 3 * _se(1 - Q, draws), rate


def test_pf4_51_the_flagged_rows_intervals_hold_their_false_coverage_rate() -> None:
    """Through the comparison's own level, 1 - q·R/M with R the rows flagged (Benjamini-Yekutieli's
    false-coverage-statement rate), on 30 rows of 30 a side with changes in ten: averaged over draws, the
    share of flagged rows whose interval misses its truth is at most q."""
    n, rows, draws = 30, 30, 2_000
    rng = np.random.default_rng(5300)
    pa = np.full(rows, 0.3)
    pb = np.where(np.arange(rows) < 10, 0.75, 0.3)
    table = _fisher_table(n, n)
    fcp = []
    for _ in range(draws):
        ea, eb = rng.binomial(n, pa), rng.binomial(n, pb)
        flagged = bh(table[ea, eb], Q) < Q
        r = int(flagged.sum())
        if r == 0:
            fcp.append(0.0)
            continue
        alpha = Q * r / rows
        misses = 0
        for j in np.nonzero(flagged)[0]:
            lo, hi = interval_rd(int(ea[j]), n, int(eb[j]), n, alpha=alpha)
            misses += int(not lo <= pb[j] - pa[j] <= hi)
        fcp.append(misses / r)
    rate = float(np.mean(fcp))
    assert rate <= Q + 3 * float(np.std(fcp)) / math.sqrt(draws), rate


def test_pf4_51_the_wilson_share_interval_covers_near_its_level_averaged_over_the_rate() -> None:
    """Prove's Wilson interval at its default level, coverage computed exactly over the binomial: averaged
    over true rates from 0.01 to 0.99 it is within 0.01 of 0.95, and nowhere below 0.90, at 20 and 100."""
    from scipy.stats import binom

    from poisson_prove.stats import wilson

    for n in (20, 100):
        bounds = [wilson(k, n) for k in range(n + 1)]
        coverage = []
        for p in np.linspace(0.01, 0.99, 197):
            pmf = binom.pmf(np.arange(n + 1), n, p)
            coverage.append(sum(w for k, w in enumerate(pmf) if bounds[k].lo <= p <= bounds[k].hi))
        assert abs(float(np.mean(coverage)) - 0.95) <= 0.01, (n, float(np.mean(coverage)))
        assert min(coverage) >= 0.90, (n, min(coverage))


# ---------- PF4.18: Westfall-Young at its nominal rate ----------


def test_pf4_18_under_the_null_the_omnibus_rejects_at_its_nominal_rate_at_small_b() -> None:
    """Observed and permuted statistics drawn alike, B = 19, four statistics: the omnibus is a rank among
    20 exchangeable members, so it rejects at 0.10 in at most 10% of datasets. The old scales rejected in
    18.4%."""
    from poisson_prove.tree import _min_p

    rng = np.random.default_rng(20261020)
    datasets = 4000
    rejected = 0
    for _ in range(datasets):
        draws = rng.normal(size=(20, 4))
        _, omnibus = _min_p(draws[0], draws[1:])
        rejected += int(float(omnibus) <= 0.10)
    rate = rejected / datasets
    assert rate <= 0.10 + 3.0 * math.sqrt(0.1 * 0.9 / datasets), rate
