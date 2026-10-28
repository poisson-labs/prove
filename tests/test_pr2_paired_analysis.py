"""PR-2 frozen tests: the per-cut paired analysis, the item-clustered bootstrap and the outcome of
the paired replay -- invariants PR22 to PR39.

The code under test is the analysis part of ``src/poisson_prove/paired.py``: ``CutResult``,
``PairedResult`` and ``analyse``. Their names are read through ``getattr`` inside each test, so a
missing name fails test by test on ``AttributeError`` and never at collection. A ``Cut`` declares
its ``comparison`` with no default, so every cut this file builds carries ``"ge"`` -- the reading
PR23 had -- and the PR23 tests take the comparison as a parameter with ``"gt"`` rows beside the
``"ge"`` ones; PR24 has one test for the tie under ``"gt"``. Both artifacts print the cut's
``comparison`` beside its ``threshold``, pinned by one line in PR37's nesting test.

**What the analysis is.** ``analyse`` takes a ``PairAssertion`` and nothing else (PR9, pinned by
the PR-1 frozen tests) and answers one question per declared cut: did the binary action at that cut
reproduce? The action, on ``Decimal`` (PR23, PR24), is ``value >= threshold`` when the cut declares
``comparison = "ge"`` and ``value > threshold`` when it declares ``"gt"``, a tie being action 1
under the first and action 0 under the second and counted per arm under both; the 2x2, the flip rate
and the net swing are paired quantities (PR25 to PR27); the pooled interval is the percentile
cluster bootstrap over items, with its declared fallback and its
design effect (PR28 to PR34); McNemar is the arm-order check and nothing else (PR35, PR36); no
statistic crosses a cut (PR37); the outcome fires only against a declared floor (PR38); and the
whole of it, read off two stored arms, gives what an independent reference gives (PR39).

**Conventions this file fixes** (where the declared interface leaves them
open):

- *The result.* ``PairedResult`` is its two declared fields and no other; ``cuts`` is one
  ``CutResult`` per declared cut, in declaration order. ``CutResult`` is its seven declared
  fields and no other. ``declaration_digest == assertion.declaration.digest``.
- *``per_sweep``.* One mapping per declared sweep, in declaration order, carrying ``sweep``,
  ``n11``, ``n10``, ``n01``, ``n00``, ``n``, ``ties`` (``{"a": int, "b": int}``), ``rate_a`` and
  ``rate_b`` (descriptive floats, no interval), ``flip_rate`` (``{estimate, lo, hi, basis}`` with
  ``basis == "exact_binomial"``: the two-sided 95% Clopper-Pearson interval on the discordant
  count), ``net_swing`` (``{estimate}``; a per-sweep interval on it is not pinned) and
  ``arm_order_check`` (``{p, n_discordant, can_reject}``).
- *``pooled``.* ``n`` is ``{"items": G, "sweeps": S}`` (PR34); ``flip_rate`` and ``net_swing`` are
  ``{estimate, lo, hi, basis}``; ``ineligibility_rate`` is PR22's rate,
  ``counts["by_cut"][cut]["ineligible"] / counts["by_cut"][cut]["matched"]`` off the assertion's
  own counts block. ``basis`` is ``"cluster_bootstrap"``, or under PR31's fallback
  ``"exact_upper_one_sided"`` with ``lower_bound_by_observation: true`` on ``flip_rate``; the net
  swing under the fallback is ``{estimate, lo: null, hi: null, basis: "not_estimated"}``, because a
  signed quantity has no one-sided exact bound and a bootstrap that degenerated for the flip rate
  degenerated for the swing too.
- *The bootstrap, exactly as ``cluster_bootstrap`` below writes it.* A fresh
  ``numpy.random.default_rng(bootstrap_seed)`` per quantity and per cut; the item clusters in
  ascending order of the cluster key (``groupby(sort=True)``: strings sort as strings, and the
  stored arms pin that); one index matrix ``rng.integers(0, G, size=(B, G))``; each resample's
  per-observation indicators concatenated and averaged; ``numpy.percentile`` at 2.5 and 97.5.
  Two consequences are pinned: the same seed gives the flip-rate and net-swing intervals the same
  draws, and a cut's interval does not move when another cut is added to the declaration (PR37).
- *The fallback.* ``k`` is the number of item clusters carrying at least one flip over all sweeps.
  ``k < 5`` gives ``lo = 0.0`` and ``hi`` equal to the one-sided 95% Clopper-Pearson upper bound
  on ``k`` of ``G`` items, ``scipy.stats.beta.ppf(0.95, k + 1, G - k)``; at ``k = 0`` that is
  ``1 - 0.05 ** (1 / G)``.
- *The design effect.* ``design_effect`` is ``{"icc", "m_bar", "deff"}`` per cut: one-way ANOVA
  ``ICC(1)`` on each item's flip indicators, ``(MSB - MSW) / (MSB + (m_bar - 1) MSW)`` clipped at
  zero, ``m_bar`` the mean observations per item, ``deff = 1 + (m_bar - 1) icc``. Pinned on
  balanced fixtures; the unbalanced ``m_bar`` is not pinned. At ``m_bar = 1`` ``deff`` is ``1.0``.
- *McNemar.* ``p`` is the two-sided exact binomial on ``min(n10, n01)`` of ``n10 + n01`` at one
  half (``diff._mcnemar``'s own arithmetic, ``1.0`` at zero discordant pairs); ``can_reject`` is
  ``n_discordant >= 6``.
- *The outcome.* With ``floor`` declared: ``"A"`` when ``lo == 0 and hi < floor``, ``"B"`` when
  ``lo > 0``, ``"C"`` when ``lo == 0 and hi >= floor``, decided from the pooled ``flip_rate``
  interval; ``None`` without a floor. ``hi == floor`` exactly is not pinned.
- *The two artifacts.* ``contingency_json()`` and ``intervals_json()`` each return one JSON object
  with exactly the top-level keys ``declaration_digest`` and ``cuts``; ``cuts`` is keyed by cut
  name in declaration order. A contingency cut block carries ``threshold`` (the literal text),
  ``per_sweep`` (keyed by sweep name: the 2x2, ``n``, ``ties``, ``arm_order_check``) and ``ties``.
  An intervals cut block carries ``threshold``, ``n``, ``flip_rate``, ``net_swing``,
  ``design_effect``, ``per_sweep`` (keyed by sweep name: ``rate_a``, ``rate_b``, ``flip_rate``,
  ``net_swing``), ``ineligibility_rate``, ``outcome`` and ``outcome_interval`` (the pooled
  ``flip_rate`` interval the outcome was decided from, ``null`` without a floor). Every number
  is a JSON number; ``threshold`` is the one string. Key order is stable across calls, processes
  and hash seeds.
- *The sign of the net swing.* PR26 writes ``net_swing = (n01 - n10) / n``,
  the second arm (``b``, arm A') minus the first (``a``, arm A); a reader who subtracts the other
  way gets the same interval with its sign flipped. **The
  formula is PR26's**, and
  **every ``net_swing`` mapping -- per sweep, pooled, and in ``intervals_json`` -- carries
  ``direction: "b_minus_a"``** so a reader never has to guess which way it subtracts.

**Invariants.** PR22 to PR39; two functions are the control. Every test name starts
``test_prN_``.

**Fixtures, and what each cannot express.** Every ``PairAssertion`` but two is built in test code,
frame by frame -- that is the intended way in for the analysis, and it is
what lets a fixture carry exactly the flip pattern an invariant needs. The two exceptions: the
control runs a hand-built store through ``assert_pairs`` so the frames ``analyse`` reads are the
frames the pair assertion emits; and PR39 reads two stored arms the suite generates (``tests/replay_arms.py``)
and builds their assertion in test code, matched on ``(config_hash, replicate_index)`` with the
five eligibility rules. The stored arms carry one cut, four pairs per item and 36 flips, so PR37, PR32's
``m_bar = 3`` reading and PR31 each have a hand-built frame here instead.

**The three ``hypothesis`` tests are derandomized,** so a run of this file is the same run every
time and a failure does not depend on a seed.

**Named gaps, not pinned.** Which function raises ``NoEligiblePairs`` and what an empty cut does
(no test here empties a cut; every declaration lists exactly the cuts its rows carry); a row whose
``cut`` names no declared cut; ``m_bar`` on unbalanced clusters and ``icc`` at ``m_bar = 1``;
``hi == floor`` exactly; a per-sweep interval on the net swing; pooled arm rates (if emitted they
carry no ``lo``/``hi``, which PR27's scan enforces); the order of observations within one cluster
(the mean does not see it).
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import pickle
import random
import subprocess
import sys
import typing
from collections.abc import Callable, Iterator, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.stats import beta, binomtest

import poisson_prove
from poisson_prove import paired
from poisson_prove.episode import Episode
from poisson_prove.executor import derive_seed
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from poisson_prove.trace import Span, Trace

import replay_arms

EPOCH = 1_790_000_000_000_000_000
SALT = "9f4a1c62d08e5b37"
REQUEST_SPAN = "scorer.request"
MODEL_PIN = "scorer-1.13.0"
VALUE_KEY = "answers.q1.score"
CUT = "c60"
THRESHOLD = "0.60"
HI, LO = "0.95", "0.05"  # action 1 and action 0 under every cut here, never a tie
B_SMALL = 400
SEED = 20260922

CUT_RESULT_FIELDS = (
    "name", "threshold", "per_sweep", "pooled", "ties", "design_effect", "outcome",
)
PAIRED_RESULT_FIELDS = ("declaration_digest", "cuts")
PER_SWEEP_KEYS = frozenset({
    "sweep", "n11", "n10", "n01", "n00", "n", "ties", "rate_a", "rate_b", "flip_rate",
    "net_swing", "arm_order_check",
})
INTERVAL_KEYS = frozenset({"estimate", "lo", "hi", "basis"})
PAIRED_QUANTITIES = frozenset({"flip_rate", "net_swing", "outcome_interval"})

#: The seed PR39 declares for the two stored arms' bootstrap.
STORED_SEED = 20260120
INSTRUMENT_SIDE = frozenset(
    {"infrastructure_error", "agent_error", "user_error", "unexpected_error"}
)


def P() -> Any:
    """The module under test. The analysis names are read off it inside each test, so a missing
    one fails on ``AttributeError`` test by test."""
    return paired


# ---------- reference implementations, the arithmetic written out ----------


def cp_two_sided(k: int, n: int) -> tuple[float, float]:
    lo = 0.0 if k == 0 else float(beta.ppf(0.025, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(0.975, k + 1, n - k))
    return lo, hi


def cp_upper_one_sided(k: int, g: int) -> float:
    return float(beta.ppf(0.95, k + 1, g - k))


def cluster_bootstrap(
    clusters: Sequence[Any], values: Sequence[int], *, seed: int, b: int
) -> tuple[float, float]:
    """The percentile cluster bootstrap in twelve lines: ``default_rng(seed)``,
    ``groupby(cluster, sort=True)``, ``rng.integers(0, G, size=(B, G))``, concatenate, mean,
    2.5 / 97.5."""
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({"cluster": list(clusters), "v": list(values)})
    groups = [g["v"].to_numpy() for _, g in frame.groupby("cluster", sort=True)]
    idx = rng.integers(0, len(groups), size=(b, len(groups)))
    draws = np.array([np.concatenate([groups[i] for i in row]).mean() for row in idx])
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def observation_bootstrap(values: Sequence[int], *, seed: int, b: int) -> tuple[float, float]:
    """The naive bootstrap PR30 forbids: observations resampled, the item ignored."""
    rng = np.random.default_rng(seed)
    v = np.asarray(list(values))
    idx = rng.integers(0, len(v), size=(b, len(v)))
    draws = v[idx].mean(axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def icc1(clusters: Sequence[Any], values: Sequence[int]) -> tuple[float, float, float]:
    """One-way ANOVA ``ICC(1)`` on a balanced design: ``(icc, m_bar, deff)``."""
    frame = pd.DataFrame({"c": list(clusters), "y": [float(v) for v in values]})
    g = frame["c"].nunique()
    m = len(frame) / g
    grand = frame["y"].mean()
    means = frame.groupby("c")["y"].mean()
    msb = m * float(((means - grand) ** 2).sum()) / (g - 1)
    msw = float(((frame["y"] - frame["c"].map(means)) ** 2).sum()) / (g * (m - 1))
    denominator = msb + (m - 1) * msw
    icc = 0.0 if denominator == 0 else max(0.0, (msb - msw) / denominator)
    return icc, m, 1 + (m - 1) * icc


def mcnemar_p(n10: int, n01: int) -> float:
    if n10 + n01 == 0:
        return 1.0
    return float(binomtest(min(n10, n01), n10 + n01, 0.5).pvalue)


# ---------- helpers: a PairAssertion built in test code ----------


@dataclasses.dataclass
class Pair:
    cluster: str
    a: str  # the stored literal of arm A's value
    b: str  # the stored literal of arm A''s value
    sweep: str = "S1"
    cut: str = CUT


def pairs_frame(rows: Sequence[Pair]) -> pd.DataFrame:
    records = [
        {
            "sweep": r.sweep, "cut": r.cut, "cluster": r.cluster,
            "config_hash": config_hash({"item": r.cluster, "cut": r.cut}),
            "replicate_index": 0, "request_digest": "0" * 64, "exemptions_exercised": (),
            "value_a": Decimal(r.a), "value_b": Decimal(r.b),
        }
        for r in rows
    ]
    return pd.DataFrame(records, columns=[
        "sweep", "cut", "cluster", "config_hash", "replicate_index", "request_digest",
        "exemptions_exercised", "value_a", "value_b",
    ])


def excluded_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=[
        "sweep", "cut", "cluster", "config_hash", "replicate_index", "cause", "arm", "detail",
    ])


def counts_for(pairs: pd.DataFrame, excluded: pd.DataFrame, cuts: Sequence[str]) -> dict[str, Any]:
    """PR20's block, consistent with the two frames, so the code may read either."""
    def block(kept: pd.DataFrame, dropped: pd.DataFrame) -> dict[str, Any]:
        unmatched = int((dropped["cause"] == "unmatched").sum()) if len(dropped) else 0
        ineligible = len(dropped) - unmatched
        matched = len(kept) + ineligible
        return {
            "keys": matched + unmatched, "matched": matched, "unmatched": unmatched,
            "eligible": len(kept), "ineligible": ineligible,
            "by_cause": dict(dropped["cause"].value_counts()) if len(dropped) else {},
            "by_arm": dict(dropped["arm"].value_counts()) if len(dropped) else {},
            "reconciles": True,
        }
    by_cut = {
        cut: block(pairs[pairs["cut"] == cut], excluded[excluded["cut"] == cut]) for cut in cuts
    }
    return {"total": block(pairs, excluded), "by_cut": by_cut, "exemptions_exercised": {}}


def declaration(
    *,
    cuts: Sequence[tuple[str, ...]] = ((CUT, THRESHOLD),),
    sweeps: Sequence[str] = ("S1",),
    b: int = B_SMALL,
    seed: int = SEED,
    floor: str | None = None,
    **over: Any,
) -> Any:
    kwargs: dict[str, Any] = {
        "value_key": VALUE_KEY, "cluster_key": "item", "stratum_key": "cut",
        # A cut is ``(name, threshold)`` or ``(name, threshold, comparison)``; the comparison
        # defaults to ``"ge"`` here, in the helper, because that is the reading every test below
        # was cut against. The module itself has no default.
        "cuts": tuple(
            paired.Cut(name=c[0], threshold=Decimal(c[1]), comparison=c[2] if len(c) > 2 else "ge")
            for c in cuts
        ),
        "sweeps": tuple(paired.SweepPair(name=s, a=f"{s}-a", b=f"{s}-b") for s in sweeps),
        "request_span": REQUEST_SPAN, "model_key": "model", "model_pin": MODEL_PIN,
        "exemptions": ("x-request-id",), "headers": "not_recorded", "retries": "not_recorded",
        "bootstrap_b": b, "bootstrap_seed": seed,
        "floor": None if floor is None else Decimal(floor),
    }
    kwargs.update(over)
    return paired.Declaration(**kwargs)


def assertion(
    rows: Sequence[Pair],
    *,
    excluded: Sequence[Mapping[str, Any]] = (),
    decl: Any = None,
    **decl_over: Any,
) -> Any:
    """A ``PairAssertion`` over hand-built rows. The declaration lists exactly the cuts and sweeps
    the rows carry unless one is passed, so no cut is ever empty."""
    if decl is None:
        cuts = list(dict.fromkeys(r.cut for r in rows))
        sweeps = list(dict.fromkeys(r.sweep for r in rows))
        thresholds = {CUT: THRESHOLD, "c50": "0.50", "c90": "0.90"}
        decl = declaration(
            cuts=[(c, thresholds.get(c, THRESHOLD)) for c in cuts], sweeps=sweeps, **decl_over
        )
    pairs = pairs_frame(rows)
    dropped = excluded_frame(excluded)
    return paired.PairAssertion(
        declaration=decl, pairs=pairs, excluded=dropped, environment={"sweeps": {}, "gaps": []},
        counts=counts_for(pairs, dropped, [c.name for c in decl.cuts]),
    )


def grid(
    g: int,
    sweeps: Sequence[str],
    action: Callable[[int, str], tuple[int, int]],
    *,
    cut: str = CUT,
) -> list[Pair]:
    """``g`` items by the sweeps, each pair's two actions given by ``action(item, sweep)``."""
    return [
        Pair(f"i{i:03d}", HI if a else LO, HI if b else LO, sweep=s, cut=cut)
        for i in range(g)
        for s in sweeps
        for a, b in (action(i, s),)
    ]


def concordant(_: int, __: str) -> tuple[int, int]:
    return (1, 1)


def analyse(a: Any) -> Any:
    return P().analyse(a)


def cut_of(result: Any, name: str = CUT) -> Any:
    by_name = {c.name: c for c in result.cuts}
    assert name in by_name, list(by_name)
    return by_name[name]


def sweep_of(cut: Any, name: str = "S1") -> Mapping[str, Any]:
    by_name = {s["sweep"]: s for s in cut.per_sweep}
    assert name in by_name, list(by_name)
    return by_name[name]


def two_by_two(cut: Any, sweep: str = "S1") -> tuple[int, int, int, int]:
    s = sweep_of(cut, sweep)
    return int(s["n11"]), int(s["n10"]), int(s["n01"]), int(s["n00"])


def walk(node: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    """Every leaf and every mapping in a JSON tree, with the key path that reaches it."""
    yield path, node
    if isinstance(node, Mapping):
        for key, value in node.items():
            yield from walk(value, (*path, str(key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, (*path, f"[{i}]"))


def artifacts(result: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    contingency = json.loads(result.contingency_json())
    intervals = json.loads(result.intervals_json())
    assert isinstance(contingency, dict) and isinstance(intervals, dict)
    return contingency, intervals


# ---------- helpers: a store the pair assertion accepts (the control only) ----------


def _span(body: str, k: int) -> Span:
    return Span(
        span_id=f"{k + 1:016x}", parent_id=None, kind="http", name=REQUEST_SPAN,
        start_ns=EPOCH + k * 1_000_000, end_ns=EPOCH + k * 1_000_000 + 500_000, input=body,
        output='{"answers": {"q1": {"score": 0.62}}}', tokens={"in": 400, "out": 12},
        attrs={"url.full": "https://api.example.test/v1/evaluate", "http.request.method": "POST"},
    )


def _record(run_id: str, item: str, cut: str, value: str) -> EpisodeRecord:
    config = {"item": item, "cut": cut}
    body = (
        f'{{"model": "{MODEL_PIN}", "state": "state of {item}", "temperature": 0.30, '
        '"max_tokens": 64}'
    )
    meta: dict[str, Any] = {
        "trace": Trace(spans=(_span(body, 0),), source="record").to_dict(),
        "answers": {"q1": {"score": value}},
    }
    episode = Episode(outcome="scored", t=1.0, horizon=10.0, meta=meta)
    return EpisodeRecord.from_episode(
        episode, run_id=run_id, config=config, seed=derive_seed(SALT, config_hash(config), 0),
        replicate_index=0, wall_time=0.1,
    )


def make_store(root: Path, values: Mapping[tuple[str, str], tuple[str, str]]) -> Store:
    """``values`` maps ``(cut, item)`` to the two arms' stored literals."""
    store = Store(root / "store")
    for arm, run_id in (("a", "S1-a"), ("b", "S1-b")):
        store.create_run(RunManifest(
            run_id=run_id, target_id="scorer@v1", t_unit="steps", run_salt=SALT,
            axis_types={"item": "categorical", "cut": "categorical"}, backend="local",
            environment={
                "python": "3.11.7", "platform": "oracle",
                "poisson_prove_version": poisson_prove.__version__,
                "capture": {"content": True, "max_observation_bytes": "none"},
            },
        ))
        store.append(run_id, [
            _record(run_id, item, cut, pair[0 if arm == "a" else 1])
            for (cut, item), pair in values.items()
        ])
        store.mark_complete(run_id)
    return store


STORE_VALUES: dict[tuple[str, str], tuple[str, str]] = {
    # c50 at 0.50: two concordant-1, one 1->0, one 0->0
    ("c50", "p0"): ("0.80", "0.90"), ("c50", "p1"): ("0.55", "0.51"),
    ("c50", "p2"): ("0.70", "0.20"), ("c50", "p3"): ("0.10", "0.30"),
    # c60 at 0.60: one concordant-1 (a tie in arm b), two 0->1, one 0->0
    ("c60", "q0"): ("0.75", "0.60"), ("c60", "q1"): ("0.25", "0.75"),
    ("c60", "q2"): ("0.40", "0.99"), ("c60", "q3"): ("0.00", "0.10"),
    # c90 at 0.90: all four concordant-0
    ("c90", "r0"): ("0.10", "0.20"), ("c90", "r1"): ("0.89", "0.85"),
    ("c90", "r2"): ("0.50", "0.50"), ("c90", "r3"): ("0.30", "0.30"),
}
STORE_TABLES = {"c50": (2, 1, 0, 1), "c60": (1, 0, 2, 1), "c90": (0, 0, 0, 4)}


def store_declaration() -> Any:
    return declaration(
        cuts=(("c50", "0.50"), ("c60", "0.60"), ("c90", "0.90")), sweeps=("S1",),
        b=B_SMALL, seed=SEED,
    )


# ---------- the control: analyse reads what assert_pairs emits ----------


def test_control_analyse_consumes_the_frames_assert_pairs_emits(tmp_path: Path) -> None:
    """The one road through the pair assertion: a hand-built store, ``assert_pairs``, then
    ``analyse``. Every later test builds its ``PairAssertion`` directly; this is what says the two
    shapes agree."""
    store = make_store(tmp_path, STORE_VALUES)
    a = paired.assert_pairs(store, store_declaration())
    assert len(a.pairs) == 12 and len(a.excluded) == 0
    before = a.pairs.copy(deep=True)
    result = analyse(a)
    pd.testing.assert_frame_equal(a.pairs, before)  # analyse does not touch its input
    assert [c.name for c in result.cuts] == ["c50", "c60", "c90"]
    for name, table in STORE_TABLES.items():
        assert two_by_two(cut_of(result, name)) == table, name
    assert result.declaration_digest == a.declaration.digest
    assert cut_of(result, "c60").ties == {"a": 0, "b": 1}


def test_control_a_hand_built_assertion_reads_like_the_stored_one() -> None:
    rows = [
        Pair(item, a, b, cut=cut) for (cut, item), (a, b) in STORE_VALUES.items()
    ]
    result = analyse(assertion(rows, decl=store_declaration()))
    for name, table in STORE_TABLES.items():
        assert two_by_two(cut_of(result, name)) == table, name


# ---------- PR22: the ineligibility rate per cut is carried into the analysis ----------


@pytest.mark.math
def test_pr22_the_ineligibility_rate_per_cut_is_carried_into_the_analysis() -> None:
    rows = grid(9, ["S1"], concordant) + grid(4, ["S1"], concordant, cut="c50")
    dropped = [
        {"sweep": "S1", "cut": CUT, "cluster": f"x{i}", "config_hash": f"h{i}",
         "replicate_index": 0, "cause": "errored", "arm": "a", "detail": "timeout"}
        for i in range(3)
    ]
    result = analyse(assertion(rows, excluded=dropped))
    assert cut_of(result, CUT).pooled["ineligibility_rate"] == pytest.approx(3 / 12)
    assert cut_of(result, "c50").pooled["ineligibility_rate"] == 0.0
    _, intervals = artifacts(result)
    assert intervals["cuts"][CUT]["ineligibility_rate"] == pytest.approx(3 / 12)
    assert intervals["cuts"]["c50"]["ineligibility_rate"] == 0.0


@pytest.mark.math
def test_pr22_an_unmatched_key_is_not_an_ineligible_pair() -> None:
    """PR20 read to the letter: ``ineligible`` counts matched pairs that failed; an unmatched key
    is its own count and does not enter the rate."""
    rows = grid(6, ["S1"], concordant)
    dropped = [
        {"sweep": "S1", "cut": CUT, "cluster": "u0", "config_hash": "hu", "replicate_index": 0,
         "cause": "unmatched", "arm": "a", "detail": "in arm a only"},
        {"sweep": "S1", "cut": CUT, "cluster": "x0", "config_hash": "hx", "replicate_index": 0,
         "cause": "value_missing", "arm": "b", "detail": "no value"},
        {"sweep": "S1", "cut": CUT, "cluster": "x1", "config_hash": "hy", "replicate_index": 0,
         "cause": "body", "arm": "both", "detail": "temperature"},
    ]
    result = analyse(assertion(rows, excluded=dropped))
    assert cut_of(result).pooled["ineligibility_rate"] == pytest.approx(2 / 8)


@pytest.mark.math
def test_pr22_the_module_computes_the_rate_and_chooses_no_threshold_for_it() -> None:
    """Half the matched pairs ineligible: the cut still carries its full result and the rate, and
    nothing in the block flags, refuses or grades the rate."""
    rows = grid(6, ["S1"], lambda i, _: (1, 0) if i < 2 else (1, 1))
    dropped = [
        {"sweep": "S1", "cut": CUT, "cluster": f"x{i}", "config_hash": f"h{i}",
         "replicate_index": 0, "cause": "errored", "arm": "both", "detail": "429"}
        for i in range(6)
    ]
    result = analyse(assertion(rows, excluded=dropped))
    cut = cut_of(result)
    assert cut.pooled["ineligibility_rate"] == pytest.approx(0.5)
    assert two_by_two(cut) == (4, 2, 0, 0)
    assert INTERVAL_KEYS <= set(cut.pooled["flip_rate"])
    _, intervals = artifacts(result)
    block = intervals["cuts"][CUT]
    mentions = [p for p, _ in walk(block) if p and "ineligib" in p[-1]]
    assert mentions == [("ineligibility_rate",)], mentions


# ---------- PR23: the action is value >= threshold (ge) or value > threshold (gt), on Decimal ----------


@pytest.mark.math
@pytest.mark.parametrize(
    ("comparison", "literal", "action"),
    [("ge", "0.59", 0), ("ge", "0.60", 1), ("ge", "0.61", 1), ("ge", "0.6", 1), ("ge", "0.599", 0),
     ("ge", "0.6000", 1), ("ge", "1", 1), ("ge", "0", 0),
     # Under ``gt`` the tie does not act, and nothing else moves.
     ("gt", "0.59", 0), ("gt", "0.60", 0), ("gt", "0.61", 1), ("gt", "0.6", 0), ("gt", "0.599", 0),
     ("gt", "0.6000", 0), ("gt", "1", 1), ("gt", "0", 0), ("gt", "0.6000000000000000001", 1)],
)
def test_pr23_the_action_is_value_at_or_above_the_threshold(comparison: str, literal: str, action: int) -> None:
    decl = declaration(cuts=((CUT, THRESHOLD, comparison),))
    result = analyse(assertion([Pair("i0", literal, HI)], decl=decl))
    n11, _, n01, _ = two_by_two(cut_of(result))
    assert (n11, n01) == ((1, 0) if action else (0, 1)), (comparison, literal, two_by_two(cut_of(result)))


@pytest.mark.math
@pytest.mark.parametrize(
    ("comparison", "literal", "threshold", "action"),
    [
        # An item stored at 0.60 must clear a cut of 0.60, which a float comparison fails.
        # ``float("0.60") >= Decimal("0.60")`` is False, because Python compares the two exactly.
        ("ge", "0.60", "0.60", 1),
        # And as all-float arithmetic hides it: below the cut to Decimal, a tie to a double.
        ("ge", "0.59999999999999999999", "0.60", 0),
        ("ge", "0.6000000000000000001", "0.60000000000000000011", 0),
        ("ge", "0.60000000000000000011", "0.6000000000000000001", 1),
        # 0.1 + 0.2 is the double above 0.3; the literal is not, and is below a cut of 0.3.
        ("ge", "0.29999999999999998", "0.3", 0),
        ("ge", "0.3", "0.30000000000000004", 0),
        # The same literals under ``gt``: the tie at 0.60 does not act,
        # a float would call ``0.60000000000000000011 > 0.6000000000000000001`` a tie, and it is not.
        ("gt", "0.60", "0.60", 0),
        ("gt", "0.60000000000000000011", "0.6000000000000000001", 1),
        ("gt", "0.6000000000000000001", "0.60000000000000000011", 0),
        ("gt", "0.30000000000000004", "0.3", 1),
    ],
)
def test_pr23_a_literal_a_float_cannot_place_is_placed_by_its_text(
    comparison: str, literal: str, threshold: str, action: int
) -> None:
    if comparison == "ge":
        assert Decimal(literal) >= Decimal(threshold) if action else Decimal(literal) < Decimal(threshold)
    else:
        assert Decimal(literal) > Decimal(threshold) if action else Decimal(literal) <= Decimal(threshold)
    decl = declaration(cuts=((CUT, threshold, comparison),))
    result = analyse(assertion([Pair("i0", literal, "1")], decl=decl))
    n11, _, n01, _ = two_by_two(cut_of(result))
    assert (n11, n01) == ((1, 0) if action else (0, 1)), (literal, threshold)


@pytest.mark.math
def test_pr23_no_rounding_is_applied_before_the_comparison() -> None:
    """A value one ten-thousandth under the cut stays under it; rounding to two places would
    lift it across, and the module would be measuring the rounding."""
    result = analyse(assertion([Pair("i0", "0.5999", "0.6001"), Pair("i1", "0.5951", "0.5949")]))
    assert two_by_two(cut_of(result)) == (0, 0, 1, 1)


@settings(max_examples=150, deadline=None, derandomize=True)
@pytest.mark.math
@given(
    value=st.decimals(min_value=Decimal(0), max_value=Decimal(1), places=22, allow_nan=False),
    value_b=st.decimals(min_value=Decimal(0), max_value=Decimal(1), places=22, allow_nan=False),
    threshold=st.decimals(min_value=Decimal("0.0001"), max_value=Decimal(1), places=22, allow_nan=False),
    comparison=st.sampled_from(["ge", "gt"]),
)
def test_pr23_property_the_action_is_the_decimal_comparison_at_any_length(
    value: Decimal, value_b: Decimal, threshold: Decimal, comparison: str
) -> None:
    decl = declaration(cuts=((CUT, str(threshold), comparison),))
    result = analyse(assertion([Pair("i0", str(value), str(value_b))], decl=decl))
    acted_a = value >= threshold if comparison == "ge" else value > threshold
    acted_b = value_b >= threshold if comparison == "ge" else value_b > threshold
    expected = {(True, True): (1, 0, 0, 0), (True, False): (0, 1, 0, 0), (False, True): (0, 0, 1, 0), (False, False): (0, 0, 0, 1)}
    assert two_by_two(cut_of(result)) == expected[(acted_a, acted_b)], (value, threshold, comparison)


# ---------- PR24: a tie is action 1 and is counted, per cut and per arm ----------


@pytest.mark.math
@pytest.mark.parametrize(("comparison", "table"), [("ge", (3, 1, 0, 1)), ("gt", (0, 1, 1, 3))], ids=["ge", "gt"])
def test_pr24_a_tie_acts_only_under_ge_and_is_counted_per_arm_under_both(comparison: str, table: tuple[int, ...]) -> None:
    """The same five pairs under each comparison. Under ``ge`` every tie acts; under ``gt`` the
    ties change side -- 0.60 no longer acts -- and the tie counts do not move, because a tie is a
    value equal to the threshold whichever way the cut is declared."""
    rows = [
        Pair("i0", "0.60", "0.60"), Pair("i1", "0.60", "0.90"), Pair("i2", "0.70", "0.6"),
        Pair("i3", "0.50", "0.50"), Pair("i4", "0.6000", "0.25"),
    ]
    result = analyse(assertion(rows, decl=declaration(cuts=((CUT, THRESHOLD, comparison),))))
    cut = cut_of(result)
    assert two_by_two(cut) == table
    assert cut.ties == {"a": 3, "b": 2}
    assert sweep_of(cut)["ties"] == {"a": 3, "b": 2}
    contingency, _ = artifacts(result)
    assert contingency["cuts"][CUT]["ties"] == {"a": 3, "b": 2}
    assert contingency["cuts"][CUT]["per_sweep"]["S1"]["ties"] == {"a": 3, "b": 2}


@pytest.mark.math
def test_pr24_ties_are_per_cut_and_summed_over_sweeps() -> None:
    rows = [
        Pair("i0", "0.60", "0.25", sweep="S1"), Pair("i0", "0.60", "0.60", sweep="S2"),
        Pair("j0", "0.50", "0.90", sweep="S1", cut="c50"),
        Pair("j0", "0.90", "0.90", sweep="S2", cut="c50"),
    ]
    result = analyse(assertion(rows))
    assert cut_of(result, CUT).ties == {"a": 2, "b": 1}
    assert cut_of(result, "c50").ties == {"a": 1, "b": 0}
    assert sweep_of(cut_of(result, CUT), "S1")["ties"] == {"a": 1, "b": 0}
    assert sweep_of(cut_of(result, CUT), "S2")["ties"] == {"a": 1, "b": 1}


# ---------- PR25: the 2x2 per cut and per sweep sums to that cut's eligible pairs ----------


@pytest.mark.math
def test_pr25_the_two_by_two_sums_to_the_cuts_eligible_pairs_in_that_sweep() -> None:
    def action(i: int, s: str) -> tuple[int, int]:
        return {(0, "S1"): (1, 0), (1, "S1"): (0, 1), (2, "S2"): (1, 0)}.get((i, s), (1, 1))

    rows = grid(6, ["S1", "S2"], action)
    rows = [r for r in rows if not (r.sweep == "S2" and r.cluster == "i005")]  # S2 lost a pair
    rows += grid(3, ["S1", "S2"], lambda i, s: (0, 0), cut="c90")
    result = analyse(assertion(rows))
    cut = cut_of(result)
    assert two_by_two(cut, "S1") == (4, 1, 1, 0) and sweep_of(cut, "S1")["n"] == 6
    assert two_by_two(cut, "S2") == (4, 1, 0, 0) and sweep_of(cut, "S2")["n"] == 5
    assert [s["sweep"] for s in cut.per_sweep] == ["S1", "S2"]
    assert two_by_two(cut_of(result, "c90"), "S1") == (0, 0, 0, 3)
    for s in cut.per_sweep:
        assert s["n11"] + s["n10"] + s["n01"] + s["n00"] == s["n"]
        assert PER_SWEEP_KEYS <= set(s), set(s)
    contingency, _ = artifacts(result)
    for name, s in contingency["cuts"][CUT]["per_sweep"].items():
        assert s["n11"] + s["n10"] + s["n01"] + s["n00"] == s["n"], name


# ---------- PR26: flip rate and net swing, paired ----------


@pytest.mark.math
def test_pr26_flip_rate_and_net_swing_per_sweep_and_pooled() -> None:
    def action(i: int, s: str) -> tuple[int, int]:
        if s == "S1":
            return (1, 0) if i < 3 else (0, 1) if i < 4 else (1, 1)
        return (0, 1) if i < 2 else (0, 0)

    result = analyse(assertion(grid(10, ["S1", "S2"], action)))
    cut = cut_of(result)
    s1, s2 = sweep_of(cut, "S1"), sweep_of(cut, "S2")
    assert two_by_two(cut, "S1") == (6, 3, 1, 0) and two_by_two(cut, "S2") == (0, 0, 2, 8)
    assert s1["flip_rate"]["estimate"] == pytest.approx(4 / 10)
    assert s1["net_swing"]["estimate"] == pytest.approx((1 - 3) / 10)
    assert s2["flip_rate"]["estimate"] == pytest.approx(2 / 10)
    assert s2["net_swing"]["estimate"] == pytest.approx(2 / 10)
    assert cut.pooled["flip_rate"]["estimate"] == pytest.approx(6 / 20)
    assert cut.pooled["net_swing"]["estimate"] == pytest.approx((3 - 3) / 20)
    assert s1["rate_a"] == pytest.approx(9 / 10) and s1["rate_b"] == pytest.approx(7 / 10)
    # The output says which way it subtracts, everywhere the swing appears.
    assert s1["net_swing"]["direction"] == s2["net_swing"]["direction"] == "b_minus_a"
    assert cut.pooled["net_swing"]["direction"] == "b_minus_a"
    _, intervals = artifacts(result)
    assert intervals["cuts"][CUT]["net_swing"]["direction"] == "b_minus_a"
    assert intervals["cuts"][CUT]["per_sweep"]["S1"]["net_swing"]["direction"] == "b_minus_a"


@pytest.mark.math
def test_pr26_each_item_contributes_one_indicator_built_from_both_arms() -> None:
    """Two arms with the same action rate and every pair flipped. An unpaired reading -- the
    difference of the two rates -- sees nothing; the paired one sees a flip rate of one."""
    result = analyse(assertion(grid(8, ["S1"], lambda i, _: (1, 0) if i % 2 else (0, 1))))
    s = sweep_of(cut_of(result))
    assert s["rate_a"] == s["rate_b"] == pytest.approx(0.5)
    assert s["flip_rate"]["estimate"] == 1.0 and s["net_swing"]["estimate"] == 0.0
    assert cut_of(result).pooled["flip_rate"]["estimate"] == 1.0


@settings(max_examples=100, deadline=None, derandomize=True)
@pytest.mark.math
@given(
    actions=st.lists(
        st.tuples(st.integers(0, 1), st.integers(0, 1)), min_size=1, max_size=24
    ),
)
def test_pr26_property_the_two_by_two_and_both_rates_follow_from_the_actions(
    actions: list[tuple[int, int]]
) -> None:
    rows = [Pair(f"i{k:03d}", HI if a else LO, HI if b else LO) for k, (a, b) in enumerate(actions)]
    cut = cut_of(analyse(assertion(rows)))
    n11, n10, n01, n00 = two_by_two(cut)
    n = len(actions)
    assert (n11, n10, n01, n00) == (
        sum(a and b for a, b in actions), sum(a and not b for a, b in actions),
        sum(not a and b for a, b in actions), sum(not a and not b for a, b in actions),
    )
    s = sweep_of(cut)
    assert s["flip_rate"]["estimate"] == pytest.approx((n10 + n01) / n)
    assert s["net_swing"]["estimate"] == pytest.approx((n01 - n10) / n)
    assert cut.pooled["flip_rate"]["estimate"] == pytest.approx((n10 + n01) / n)
    assert cut.pooled["net_swing"]["estimate"] == pytest.approx((n01 - n10) / n)
    assert cut.pooled["n"] == {"items": n, "sweeps": 1}


# ---------- PR27: no interval on an arm's rate or on the unpaired difference ----------


@pytest.mark.math
def test_pr27_arm_rates_are_descriptive_and_every_interval_sits_on_a_paired_quantity() -> None:
    result = analyse(assertion(grid(12, ["S1", "S2"], lambda i, s: (1, 0) if i < 5 else (0, 0))))
    cut = cut_of(result)
    for s in cut.per_sweep:
        assert isinstance(s["rate_a"], float) and isinstance(s["rate_b"], float)
    contingency, intervals = artifacts(result)
    for tree in (contingency, intervals, json.loads(json.dumps(
        {"per_sweep": list(cut.per_sweep), "pooled": dict(cut.pooled)}, default=str
    ))):
        for path, node in walk(tree):
            if isinstance(node, Mapping) and ({"lo", "hi"} & set(node)):
                assert path and path[-1] in PAIRED_QUANTITIES, path
            if path and path[-1] in ("rate_a", "rate_b"):
                assert isinstance(node, int | float), path
            if path:
                assert "difference" not in path[-1] and "unpaired" not in path[-1], path


# ---------- PR28: the pooled interval is the percentile cluster bootstrap ----------


def correlated(i: int, s: str) -> tuple[int, int]:
    """The first five items flip in every sweep, the rest never: five, so PR31's fallback does
    not fire, and all-or-nothing per item, so the within-item correlation is total."""
    return (1, 0) if i < 5 else (1, 1)


@pytest.mark.math
def test_pr28_the_pooled_flip_rate_interval_is_the_cluster_bootstrap_as_published() -> None:
    rows = grid(12, ["S1", "S2", "S3"], correlated)
    cut = cut_of(analyse(assertion(rows, b=500, seed=7)))
    clusters = [r.cluster for r in rows]
    flips = [int(r.a != r.b) for r in rows]
    lo, hi = cluster_bootstrap(clusters, flips, seed=7, b=500)
    assert cut.pooled["flip_rate"]["basis"] == "cluster_bootstrap"
    assert math.isclose(cut.pooled["flip_rate"]["lo"], lo, abs_tol=1e-12)
    assert math.isclose(cut.pooled["flip_rate"]["hi"], hi, abs_tol=1e-12)
    assert lo <= cut.pooled["flip_rate"]["estimate"] <= hi


@pytest.mark.math
def test_pr28_the_net_swing_interval_is_the_same_procedure_on_d() -> None:
    def action(i: int, s: str) -> tuple[int, int]:
        return (1, 0) if i < 3 else (0, 1) if i < 8 else (1, 1)

    rows = grid(15, ["S1", "S2", "S3"], action)
    cut = cut_of(analyse(assertion(rows, b=500, seed=11)))
    clusters = [r.cluster for r in rows]
    d = [int(Decimal(r.b) >= Decimal(THRESHOLD)) - int(Decimal(r.a) >= Decimal(THRESHOLD)) for r in rows]
    lo, hi = cluster_bootstrap(clusters, d, seed=11, b=500)
    assert cut.pooled["net_swing"]["basis"] == "cluster_bootstrap"
    assert math.isclose(cut.pooled["net_swing"]["lo"], lo, abs_tol=1e-12)
    assert math.isclose(cut.pooled["net_swing"]["hi"], hi, abs_tol=1e-12)
    assert cut.pooled["net_swing"]["estimate"] == pytest.approx((5 - 3) / 15)


# ---------- PR29: reproducible, seeded from bootstrap_seed alone, clusters stably sorted ----------


@pytest.mark.math
def test_pr29_the_same_declaration_over_the_same_rows_is_byte_identical(tmp_path: Path) -> None:
    """In process twice, shuffled, and in two child processes under two hash seeds."""
    rows = grid(12, ["S1", "S2", "S3"], correlated)
    a = assertion(rows, b=300, seed=3)
    first = analyse(a).intervals_json()
    assert analyse(a).intervals_json() == first
    shuffled = list(rows)
    random.Random(5).shuffle(shuffled)
    assert analyse(assertion(shuffled, decl=a.declaration)).intervals_json() == first
    assert analyse(assertion(list(reversed(rows)), decl=a.declaration)).contingency_json() == (
        analyse(a).contingency_json()
    )
    pickled = tmp_path / "assertion.pkl"
    pickled.write_bytes(pickle.dumps(a))
    child = (
        "import pickle, sys; from poisson_prove.paired import analyse; "
        f"a = pickle.load(open({str(pickled)!r}, 'rb')); "
        "sys.stdout.write(analyse(a).intervals_json())"
    )
    for hash_seed in ("1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        out = subprocess.run(
            [sys.executable, "-c", child], capture_output=True, text=True, env=env, check=False
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout == first, hash_seed


@pytest.mark.math
def test_pr29_the_seed_alone_moves_the_interval() -> None:
    rows = grid(12, ["S1", "S2", "S3"], correlated)
    base = cut_of(analyse(assertion(rows, b=300, seed=3))).pooled["flip_rate"]
    other_seed = cut_of(analyse(assertion(rows, b=300, seed=4))).pooled["flip_rate"]
    assert (base["lo"], base["hi"]) != (other_seed["lo"], other_seed["hi"])
    for change in (
        {"conditioning": "on near-cut items"}, {"declared_window_s": 1200.0},
        {"token_cap": 6_000_000}, {"floor": "0.01"},
    ):
        moved = cut_of(analyse(assertion(rows, b=300, seed=3, **change))).pooled["flip_rate"]
        assert (moved["lo"], moved["hi"]) == (base["lo"], base["hi"]), change


@pytest.mark.math
def test_pr29_clusters_are_ordered_by_a_stable_sort_of_the_cluster_key_not_by_row_order() -> None:
    """The reference with its groups in a different order gives a different interval on this
    fixture -- so the sort is load-bearing -- and ``analyse`` matches the sorted one whatever the
    row order."""
    names = ["k", "b", "z", "a", "m", "c", "y", "d", "x", "e", "w", "f"]
    # Item i flips in its first i mod 4 sweeps, so the flip counts are 0, 1, 2, 3 repeating:
    # unequal counts put the resample mean on a fine lattice, where the two orders differ.
    rows = [
        Pair(names[i], HI if a else LO, HI if b else LO, sweep=s)
        for i in range(12) for s in ("S1", "S2", "S3")
        for a, b in (((1, 0) if int(s[1]) - 1 < i % 4 else (1, 1)),)
    ]
    clusters = [r.cluster for r in rows]
    flips = [int(r.a != r.b) for r in rows]
    sorted_ref = cluster_bootstrap(clusters, flips, seed=3, b=300)
    rng = np.random.default_rng(3)
    frame = pd.DataFrame({"cluster": clusters, "v": flips})
    groups = [g["v"].to_numpy() for _, g in frame.groupby("cluster", sort=False)]
    idx = rng.integers(0, len(groups), size=(300, len(groups)))
    draws = np.array([np.concatenate([groups[i] for i in row]).mean() for row in idx])
    unsorted_ref = (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)))
    assert sorted_ref != unsorted_ref
    decl = declaration(sweeps=("S1", "S2", "S3"), b=300, seed=3)
    for order in (rows, list(reversed(rows))):
        got = cut_of(analyse(assertion(order, decl=decl))).pooled["flip_rate"]
        assert math.isclose(got["lo"], sorted_ref[0], abs_tol=1e-12)
        assert math.isclose(got["hi"], sorted_ref[1], abs_tol=1e-12)


@pytest.mark.math
def test_pr29_an_item_only_a_later_sweep_holds_takes_its_sorted_place_in_the_bootstrap() -> None:
    """The analysis reads its rows sweep by sweep, so an item that only the second sweep holds
    arrives after every item of the first even when its key sorts first. The bootstrap must still
    draw over the items in key order: here the arrival order gives a different interval, and
    ``analyse`` must give the sorted one."""
    names = ["b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m"]
    rows: list[Pair] = []
    for sweep, items in (("S1", names), ("S2", ["a", *names])):
        for i, name in enumerate(items):
            flips = (i % 4) != 0 and sweep == "S1" or (i % 3) == 0
            rows.append(Pair(name, HI, LO if flips else HI, sweep=sweep))
    clusters = [r.cluster for r in rows]
    flips = [int(r.a != r.b) for r in rows]
    sorted_ref = cluster_bootstrap(clusters, flips, seed=5, b=300)
    rng = np.random.default_rng(5)
    frame = pd.DataFrame({"cluster": clusters, "v": flips})
    arrived = [g["v"].to_numpy() for _, g in frame.groupby("cluster", sort=False)]
    idx = rng.integers(0, len(arrived), size=(300, len(arrived)))
    draws = np.array([np.concatenate([arrived[i] for i in row]).mean() for row in idx])
    assert (float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))) != sorted_ref
    got = cut_of(analyse(assertion(rows, b=300, seed=5))).pooled["flip_rate"]
    assert math.isclose(got["lo"], sorted_ref[0], abs_tol=1e-12), (got, sorted_ref)
    assert math.isclose(got["hi"], sorted_ref[1], abs_tol=1e-12), (got, sorted_ref)


@pytest.mark.math
@settings(max_examples=25, deadline=None, derandomize=True)
@given(permutation=st.permutations(list(range(36))))
def test_pr29_property_any_row_order_gives_the_same_bytes(permutation: list[int]) -> None:
    rows = grid(12, ["S1", "S2", "S3"], correlated)
    a = assertion(rows, b=100, seed=9)
    expected = analyse(a).intervals_json()
    assert analyse(assertion([rows[i] for i in permutation], decl=a.declaration)).intervals_json() == expected


# ---------- PR30: whole items are resampled, never observations ----------


@pytest.mark.math
def test_pr30_the_bootstrap_resamples_whole_items_never_observations() -> None:
    """On a fixture with within-item correlation the observation bootstrap is narrower -- right
    shape, wrong width -- so a bootstrap that resamples observations fails here."""
    rows = grid(20, ["S1", "S2", "S3"], lambda i, s: (1, 0) if i < 5 else (1, 1))
    clusters = [r.cluster for r in rows]
    flips = [int(r.a != r.b) for r in rows]
    cluster_lo, cluster_hi = cluster_bootstrap(clusters, flips, seed=SEED, b=B_SMALL)
    obs_lo, obs_hi = observation_bootstrap(flips, seed=SEED, b=B_SMALL)
    assert obs_hi - obs_lo < cluster_hi - cluster_lo  # the fixture can tell them apart
    got = cut_of(analyse(assertion(rows))).pooled["flip_rate"]
    assert math.isclose(got["lo"], cluster_lo, abs_tol=1e-12)
    assert math.isclose(got["hi"], cluster_hi, abs_tol=1e-12)
    assert not math.isclose(got["hi"] - got["lo"], obs_hi - obs_lo, abs_tol=1e-9)


@pytest.mark.math
def test_pr30_control_a_frame_with_no_within_item_correlation_has_no_design_effect() -> None:
    """Each item flips in exactly one of its three sweeps: the item means are all equal, ``MSB``
    is zero, the ICC clips to zero and ``deff`` is one. The correlated fixture is the other end."""
    spread = grid(12, ["S1", "S2", "S3"], lambda i, s: (1, 0) if s == f"S{i % 3 + 1}" else (1, 1))
    design = cut_of(analyse(assertion(spread))).design_effect
    assert design["icc"] == 0.0 and design["deff"] == 1.0 and design["m_bar"] == 3.0
    clumped = cut_of(analyse(assertion(grid(12, ["S1", "S2", "S3"], correlated)))).design_effect
    assert clumped["icc"] == pytest.approx(1.0) and clumped["deff"] == pytest.approx(3.0)


# ---------- PR31: the declared fallback ----------


@pytest.mark.math
def test_pr31_zero_flips_is_the_exact_upper_bound_and_never_a_precise_zero() -> None:
    """Zero flips give the one-sided exact upper bound, never a zero-width interval at zero."""
    g = 20
    cut = cut_of(analyse(assertion(grid(g, ["S1", "S2", "S3"], concordant))))
    flip = cut.pooled["flip_rate"]
    assert flip["basis"] == "exact_upper_one_sided"
    assert flip["estimate"] == 0.0 and flip["lo"] == 0.0
    assert flip["hi"] == pytest.approx(1 - 0.05 ** (1 / g))
    assert flip["hi"] == pytest.approx(cp_upper_one_sided(0, g))
    assert flip["hi"] > 0.0
    assert flip["lower_bound_by_observation"] is True
    swing = cut.pooled["net_swing"]
    assert swing["basis"] == "not_estimated" and swing["lo"] is None and swing["hi"] is None
    assert swing["estimate"] == 0.0
    _, intervals = artifacts(analyse(assertion(grid(g, ["S1", "S2", "S3"], concordant))))
    block = intervals["cuts"][CUT]["flip_rate"]
    assert block["basis"] == "exact_upper_one_sided" and block["lower_bound_by_observation"] is True
    assert block["lo"] == 0.0 and block["hi"] > 0.0


@pytest.mark.math
@pytest.mark.parametrize("k", [1, 2, 3, 4])
def test_pr31_fewer_than_five_flipping_items_fall_back_too(k: int) -> None:
    g = 40
    rows = grid(g, ["S1", "S2", "S3"], lambda i, s: (1, 0) if i < k and s == "S2" else (1, 1))
    flip = cut_of(analyse(assertion(rows))).pooled["flip_rate"]
    assert flip["basis"] == "exact_upper_one_sided"
    assert flip["lo"] == 0.0 and flip["lower_bound_by_observation"] is True
    assert flip["hi"] == pytest.approx(cp_upper_one_sided(k, g))
    assert flip["estimate"] == pytest.approx(k / (3 * g))


@pytest.mark.math
def test_pr31_five_flipping_items_is_the_bootstrap_again() -> None:
    rows = grid(40, ["S1", "S2", "S3"], lambda i, s: (1, 0) if i < 5 and s == "S2" else (1, 1))
    flip = cut_of(analyse(assertion(rows))).pooled["flip_rate"]
    assert flip["basis"] == "cluster_bootstrap"
    assert "lower_bound_by_observation" not in flip or flip["lower_bound_by_observation"] is False
    clusters = [r.cluster for r in rows]
    lo, hi = cluster_bootstrap(clusters, [int(r.a != r.b) for r in rows], seed=SEED, b=B_SMALL)
    assert math.isclose(flip["lo"], lo, abs_tol=1e-12) and math.isclose(flip["hi"], hi, abs_tol=1e-12)


@pytest.mark.math
def test_pr31_the_fallback_counts_flipping_items_not_flip_observations() -> None:
    """Two items flipping in all three sweeps are six flips and two clusters: still the fallback."""
    rows = grid(30, ["S1", "S2", "S3"], lambda i, s: (0, 1) if i < 2 else (0, 0))
    flip = cut_of(analyse(assertion(rows))).pooled["flip_rate"]
    assert flip["basis"] == "exact_upper_one_sided"
    assert flip["hi"] == pytest.approx(cp_upper_one_sided(2, 30))


# ---------- PR32: ICC(1) and the design effect ----------


@pytest.mark.math
def test_pr32_icc_is_one_way_anova_on_the_items_flip_indicators_and_deff_reads_one_plus_two_rho() -> None:
    def action(i: int, s: str) -> tuple[int, int]:
        if i < 3:
            return (1, 0)
        if i < 6:
            return (0, 1) if s == "S1" else (0, 0)
        return (1, 1)

    rows = grid(12, ["S1", "S2", "S3"], action)
    icc, m_bar, deff = icc1([r.cluster for r in rows], [int(r.a != r.b) for r in rows])
    assert 0.0 < icc < 1.0 and m_bar == 3.0
    design = cut_of(analyse(assertion(rows))).design_effect
    assert set(design) == {"icc", "m_bar", "deff"}
    assert design["icc"] == pytest.approx(icc) and design["m_bar"] == 3.0
    assert design["deff"] == pytest.approx(deff) and design["deff"] == pytest.approx(1 + 2 * icc)
    _, intervals = artifacts(analyse(assertion(rows)))
    assert intervals["cuts"][CUT]["design_effect"]["deff"] == pytest.approx(deff)


@pytest.mark.math
def test_pr32_the_icc_is_clipped_at_zero_and_m_bar_is_observations_per_item() -> None:
    spread = grid(9, ["S1", "S2", "S3"], lambda i, s: (1, 0) if s == f"S{i % 3 + 1}" else (1, 1))
    icc, _, _ = icc1([r.cluster for r in spread], [int(r.a != r.b) for r in spread])
    assert icc == 0.0
    design = cut_of(analyse(assertion(spread))).design_effect
    assert design["icc"] == 0.0 and design["deff"] == 1.0
    one_sweep = cut_of(analyse(assertion(grid(9, ["S1"], lambda i, s: (1, 0) if i < 4 else (1, 1)))))
    assert one_sweep.design_effect["m_bar"] == 1.0 and one_sweep.design_effect["deff"] == 1.0
    two_sweeps = cut_of(analyse(assertion(grid(9, ["S1", "S2"], correlated))))
    assert two_sweeps.design_effect["m_bar"] == 2.0
    assert two_sweeps.design_effect["deff"] == pytest.approx(1 + 1 * two_sweeps.design_effect["icc"])


# ---------- PR33: a per-sweep interval is exact binomial, never clustered ----------


@pytest.mark.math
def test_pr33_a_per_sweep_interval_is_exact_binomial_and_never_labelled_clustered() -> None:
    def action(i: int, s: str) -> tuple[int, int]:
        if s == "S1":
            return (1, 0) if i < 7 else (1, 1)
        if s == "S2":
            return (1, 1)
        return (0, 1)

    rows = grid(20, ["S1", "S2", "S3"], action)
    cut = cut_of(analyse(assertion(rows)))
    for name, k in (("S1", 7), ("S2", 0), ("S3", 20)):
        s = sweep_of(cut, name)
        lo, hi = cp_two_sided(k, 20)
        assert s["flip_rate"]["basis"] == "exact_binomial", name
        assert s["flip_rate"]["lo"] == pytest.approx(lo) and s["flip_rate"]["hi"] == pytest.approx(hi)
        assert s["flip_rate"]["estimate"] == pytest.approx(k / 20)
        assert "cluster" not in json.dumps(dict(s), default=str).lower(), name
    assert sweep_of(cut, "S2")["flip_rate"]["lo"] == 0.0
    assert sweep_of(cut, "S3")["flip_rate"]["hi"] == 1.0
    _, intervals = artifacts(analyse(assertion(rows)))
    for name, block in intervals["cuts"][CUT]["per_sweep"].items():
        assert block["flip_rate"]["basis"] == "exact_binomial", name
        assert "cluster" not in json.dumps(block).lower(), name


# ---------- PR34: the pooled n is items and sweeps, never their product ----------


@pytest.mark.math
def test_pr34_the_pooled_n_is_items_and_sweeps_and_no_key_holds_their_product() -> None:
    """Seven items by three sweeps is twenty-one observations, and the number
    twenty-one appears nowhere in either artifact."""
    rows = grid(7, ["S1", "S2", "S3"], lambda i, s: (1, 0) if i == 0 and s == "S1" else (1, 1))
    result = analyse(assertion(rows, b=50))
    cut = cut_of(result)
    assert cut.pooled["n"] == {"items": 7, "sweeps": 3}
    assert not isinstance(cut.pooled["n"], int)
    contingency, intervals = artifacts(result)
    assert intervals["cuts"][CUT]["n"] == {"items": 7, "sweeps": 3}
    for tree in (contingency, intervals):
        for path, node in walk(tree):
            if isinstance(node, int) and not isinstance(node, bool):
                assert node != 21, path
            if isinstance(node, float):
                assert node != 21.0, path


# ---------- PR35: McNemar under arm_order_check only, with its floor ----------


@pytest.mark.math
def test_pr35_mcnemar_is_per_cut_per_sweep_under_arm_order_check_only() -> None:
    def action(i: int, s: str) -> tuple[int, int]:
        if s == "S1":
            return (1, 0) if i < 9 else (0, 1) if i < 12 else (1, 1)
        return (1, 0) if i < 2 else (0, 1) if i < 4 else (0, 0)

    rows = grid(16, ["S1", "S2"], action)
    rows += grid(16, ["S1", "S2"], lambda i, s: (0, 1) if i < 1 else (1, 1), cut="c90")
    result = analyse(assertion(rows, b=50))
    cut = cut_of(result)
    s1, s2 = sweep_of(cut, "S1"), sweep_of(cut, "S2")
    assert s1["arm_order_check"] == {"p": pytest.approx(mcnemar_p(9, 3)), "n_discordant": 12, "can_reject": True}
    assert s2["arm_order_check"] == {"p": pytest.approx(mcnemar_p(2, 2)), "n_discordant": 4, "can_reject": False}
    assert s2["arm_order_check"]["p"] == 1.0
    assert sweep_of(cut_of(result, "c90"), "S1")["arm_order_check"]["n_discordant"] == 1
    contingency, intervals = artifacts(result)
    assert contingency["cuts"][CUT]["per_sweep"]["S1"]["arm_order_check"]["n_discordant"] == 12
    assert "arm_order_check" not in json.dumps(intervals)
    in_memory = json.loads(json.dumps(
        {"pooled": dict(cut.pooled), "per_sweep": list(cut.per_sweep), "ties": dict(cut.ties),
         "design_effect": dict(cut.design_effect)},
        default=str,
    ))
    for tree in (contingency, intervals, in_memory):
        for path, _ in walk(tree):
            if path and (path[-1] == "p" or "mcnemar" in path[-1].lower() or "p_value" in path[-1]):
                assert "arm_order_check" in path[:-1], path
    assert "arm_order_check" not in cut.pooled


@pytest.mark.math
@pytest.mark.parametrize("n_d", list(range(0, 9)))
def test_pr35_can_reject_is_false_below_six_discordant_pairs_however_lopsided(n_d: int) -> None:
    rows = grid(12, ["S1"], lambda i, s: (1, 0) if i < n_d else (1, 1))
    check = sweep_of(cut_of(analyse(assertion(rows, b=50))))["arm_order_check"]
    assert check["n_discordant"] == n_d
    assert check["can_reject"] is (n_d >= 6)
    assert check["p"] == pytest.approx(mcnemar_p(n_d, 0))
    if n_d == 0:
        assert check["p"] == 1.0
    if n_d == 5:
        assert check["p"] > 0.05
    if n_d == 6:
        assert check["p"] <= 0.05


# ---------- PR36: nothing downstream reads the arm-order check ----------


@pytest.mark.math
def test_pr36_the_outcome_and_every_interval_are_blind_to_the_arm_order_check() -> None:
    """Two fixtures with the same flip pattern -- the same items flip in the same sweeps -- one
    with every flip one way and one balanced. McNemar moves from near zero to one; the flip-rate
    intervals, the design effect and the outcome do not move at all."""
    lopsided = grid(20, ["S1", "S2", "S3"], lambda i, s: (1, 0) if i < 10 else (1, 1))
    balanced = grid(20, ["S1", "S2", "S3"], lambda i, s: ((1, 0) if i % 2 else (0, 1)) if i < 10 else (1, 1))
    one = cut_of(analyse(assertion(lopsided, floor="0.01")))
    two = cut_of(analyse(assertion(balanced, floor="0.01")))
    for name in ("S1", "S2", "S3"):
        assert sweep_of(one, name)["arm_order_check"]["p"] < 0.01
        assert sweep_of(two, name)["arm_order_check"]["p"] == 1.0
        assert sweep_of(one, name)["flip_rate"] == sweep_of(two, name)["flip_rate"], name
    assert one.pooled["flip_rate"] == two.pooled["flip_rate"]
    assert one.design_effect == two.design_effect
    assert one.outcome == two.outcome == "B"
    assert one.pooled["n"] == two.pooled["n"]


def test_pr36_the_artifacts_never_say_reproducible() -> None:
    """The JSON half of PR36 is pinned here; the rendered half is not this file's."""
    result = analyse(assertion(grid(8, ["S1", "S2"], correlated), floor="0.01", b=50))
    for text in (result.contingency_json(), result.intervals_json()):
        assert "reproducib" not in text.lower()


# ---------- PR37: no cross-cut statistic exists ----------


@pytest.mark.math
def test_pr37_every_statistic_is_nested_under_exactly_one_cut_name() -> None:
    rows = grid(6, ["S1", "S2"], correlated) + grid(6, ["S1", "S2"], concordant, cut="c50")
    rows += grid(6, ["S1", "S2"], lambda i, s: (0, 1) if i < 5 else (0, 0), cut="c90")
    result = analyse(assertion(rows, b=50, floor="0.02"))
    assert tuple(f.name for f in dataclasses.fields(P().PairedResult)) == PAIRED_RESULT_FIELDS
    assert tuple(f.name for f in dataclasses.fields(P().CutResult)) == CUT_RESULT_FIELDS
    assert [c.name for c in result.cuts] == [CUT, "c50", "c90"]
    contingency, intervals = artifacts(result)
    for tree in (contingency, intervals):
        assert set(tree) == {"declaration_digest", "cuts"}, set(tree)
        assert list(tree["cuts"]) == [CUT, "c50", "c90"]
        assert tree["declaration_digest"] == result.declaration_digest
        for name, block in tree["cuts"].items():
            assert block["threshold"] == {CUT: "0.60", "c50": "0.50", "c90": "0.90"}[name]
            assert block["comparison"] == "ge"  # printed beside the threshold
            for path, _ in walk(block):
                assert not any(
                    word in p.lower() for p in path for word in ("across", "between_cut", "trend")
                ), path


@pytest.mark.math
def test_pr37_a_cuts_result_does_not_depend_on_any_other_cut() -> None:
    """The c60 block is byte-for-byte the same whether the declaration lists one cut or three,
    which also pins a fresh generator per cut: the draws c50 takes cannot move c60."""
    c60 = grid(10, ["S1", "S2", "S3"], correlated)
    c50 = grid(10, ["S1", "S2", "S3"], lambda i, s: (1, 0) if i < 6 else (0, 0), cut="c50")
    c90 = grid(10, ["S1", "S2", "S3"], lambda i, s: (0, 1) if i < 3 else (1, 1), cut="c90")
    alone = analyse(assertion(c60, b=200, floor="0.01"))
    with_others = analyse(assertion(c50 + c60 + c90, b=200, floor="0.01"))
    assert [c.name for c in with_others.cuts] == ["c50", CUT, "c90"]
    for artifact in ("contingency_json", "intervals_json"):
        one = json.loads(getattr(alone, artifact)())["cuts"][CUT]
        three = json.loads(getattr(with_others, artifact)())["cuts"][CUT]
        assert json.dumps(one, sort_keys=True) == json.dumps(three, sort_keys=True), artifact
    assert dataclasses.asdict(cut_of(alone)) == dataclasses.asdict(cut_of(with_others))


def test_pr37_analyse_and_its_two_result_types_are_public_and_no_function_returns_a_cross_cut_figure() -> None:
    module = P()
    public = {
        name for name, value in vars(module).items()
        if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
    }
    assert {"CutResult", "PairedResult", "analyse"} <= public
    hints = typing.get_type_hints(module.analyse)
    assert list(hints) == ["assertion", "return"]
    assert hints["return"] is module.PairedResult
    for name in ("contingency_json", "intervals_json"):
        assert typing.get_type_hints(getattr(module.PairedResult, name))["return"] is str


# ---------- PR38: the outcome, only against a declared floor ----------


@pytest.mark.math
def test_pr38_outcome_a_flips_ruled_out_below_the_floor_needs_a_large_stratum() -> None:
    """Three hundred items, one sweep, no flip, floor 0.01: the exact upper bound is 0.00994 and
    outcome A fires. Ten items under the same floor cannot rule anything out: outcome C."""
    a = cut_of(analyse(assertion(grid(300, ["S1"], concordant), floor="0.01", b=50)))
    assert a.outcome == "A"
    assert a.pooled["flip_rate"]["hi"] == pytest.approx(1 - 0.05 ** (1 / 300))
    assert a.pooled["flip_rate"]["hi"] < 0.01 and a.pooled["flip_rate"]["lo"] == 0.0
    c = cut_of(analyse(assertion(grid(10, ["S1"], concordant), floor="0.01", b=50)))
    assert c.outcome == "C"
    assert c.pooled["flip_rate"]["hi"] >= 0.01 and c.pooled["flip_rate"]["lo"] == 0.0


@pytest.mark.math
def test_pr38_outcome_c_under_the_fallback_when_the_upper_bound_reaches_the_floor() -> None:
    """Two of forty items flip: the fallback fires, the lower bound is zero by observation, the
    upper bound is 0.153 and clears a floor of 0.01, so the reading is C -- and under a floor of
    0.20 the same numbers read A. Once five items flip a bootstrap lower bound cannot be zero
    (the chance that a resample holds none of them is below e to the minus five), so C only ever
    comes from the fallback, and the test says so rather than pretending otherwise."""
    rows = grid(40, ["S1"], lambda i, s: (1, 0) if i < 2 else (1, 1))
    c = cut_of(analyse(assertion(rows, floor="0.01", b=50)))
    assert c.pooled["flip_rate"]["basis"] == "exact_upper_one_sided"
    assert c.pooled["flip_rate"]["lo"] == 0.0
    assert c.pooled["flip_rate"]["hi"] == pytest.approx(cp_upper_one_sided(2, 40))
    assert c.outcome == "C"
    a = cut_of(analyse(assertion(rows, floor="0.20", b=50)))
    assert a.pooled["flip_rate"]["hi"] < 0.20 and a.outcome == "A"


@pytest.mark.math
def test_pr38_the_outcome_is_per_cut_and_is_emitted_with_the_interval_it_was_decided_from() -> None:
    rows = grid(300, ["S1"], concordant, cut="c50") + grid(10, ["S1"], concordant, cut="c90")
    rows += grid(20, ["S1", "S2", "S3"], correlated)
    result = analyse(assertion(rows, floor="0.01", b=100))
    assert {c.name: c.outcome for c in result.cuts} == {"c50": "A", "c90": "C", CUT: "B"}
    _, intervals = artifacts(result)
    for name, block in intervals["cuts"].items():
        assert block["outcome"] == {"c50": "A", "c90": "C", CUT: "B"}[name]
        decided = block["outcome_interval"]
        assert decided["lo"] == block["flip_rate"]["lo"] and decided["hi"] == block["flip_rate"]["hi"]
        assert decided["basis"] == block["flip_rate"]["basis"]


@pytest.mark.math
def test_pr38_outcome_b_when_the_lower_bound_leaves_zero_and_with_no_floor_the_outcome_is_null() -> None:
    rows = grid(20, ["S1", "S2", "S3"], correlated)
    with_floor = analyse(assertion(rows, floor="0.01"))
    without = analyse(assertion(rows))
    assert cut_of(with_floor).pooled["flip_rate"]["lo"] > 0.0
    assert cut_of(with_floor).outcome == "B" and cut_of(without).outcome is None
    _, intervals = artifacts(without)
    assert intervals["cuts"][CUT]["outcome"] is None
    assert intervals["cuts"][CUT]["outcome_interval"] is None
    assert cut_of(with_floor).pooled == cut_of(without).pooled
    assert cut_of(with_floor).per_sweep == cut_of(without).per_sweep


# ---------- PR39: two stored arms, read back and analysed whole ----------


def stored_assertion(*, b: int = 10_000, seed: int = STORED_SEED) -> Any:
    """The two generated arms (``tests/replay_arms.py``), matched on ``(config_hash,
    replicate_index)`` in test code, with the five eligibility rules a reader of stored arms
    applies: both outcomes present (E1), neither instrument-side (E2), seeds equal within the pair
    (E3), no duplicate key (E4), one salt (E5). The event is ``outcome == "solved"``, which the
    stored ``reward`` carries as the literal ``1.0`` against ``0.0`` -- asserted here, not
    assumed -- so the value under test is ``meta["reward"]`` at a single cut with threshold ``1``."""
    store = Store(replay_arms.root())
    ma, mb = store.manifest(replay_arms.ARM_A), store.manifest(replay_arms.ARM_B)
    assert ma.run_salt == mb.run_salt == replay_arms.SALT, (ma.run_salt, mb.run_salt)  # E5
    fa, fb = store.read(replay_arms.ARM_A), store.read(replay_arms.ARM_B)
    key = ["config_hash", "replicate_index"]
    assert not fa.duplicated(key).any() and not fb.duplicated(key).any()  # E4
    merged = fa.merge(fb, on=key, suffixes=("_a", "_b"), how="inner")
    assert len(merged) == replay_arms.PAIRS and (merged["seed_a"] == merged["seed_b"]).all()  # E3
    eligible = merged[
        merged["outcome_a"].notna() & merged["outcome_b"].notna()  # E1
        & ~merged["outcome_a"].isin(INSTRUMENT_SIDE) & ~merged["outcome_b"].isin(INSTRUMENT_SIDE)  # E2
    ]
    assert len(eligible) == replay_arms.PAIRS
    records = []
    for row in eligible.to_dict("records"):
        reward_a, reward_b = row["meta_a"]["reward"], row["meta_b"]["reward"]
        assert (reward_a == 1.0) == (row["outcome_a"] == "solved")
        assert (reward_b == 1.0) == (row["outcome_b"] == "solved")
        assert row["config_a"]["task_id"] == row["config_b"]["task_id"]
        records.append({
            "sweep": "R", "cut": "solved", "cluster": row["config_a"]["task_id"],
            "config_hash": row["config_hash"], "replicate_index": int(row["replicate_index"]),
            "request_digest": "0" * 64, "exemptions_exercised": (),
            "value_a": Decimal(str(reward_a)), "value_b": Decimal(str(reward_b)),
        })
    pairs = pd.DataFrame(records)
    decl = paired.Declaration(
        value_key="reward", cluster_key="task_id", stratum_key="cut",
        cuts=(paired.Cut(name="solved", threshold=Decimal("1"), comparison="ge"),),
        sweeps=(paired.SweepPair(name="R", a=replay_arms.ARM_A, b=replay_arms.ARM_B),),
        request_span="llm", model_key="model", model_pin=MODEL_PIN,
        exemptions=(), headers="not_recorded", retries="not_recorded",
        bootstrap_b=b, bootstrap_seed=seed,
    )
    dropped = excluded_frame([])
    return paired.PairAssertion(
        declaration=decl, pairs=pairs, excluded=dropped, environment={"sweeps": {}, "gaps": []},
        counts=counts_for(pairs, dropped, ["solved"]),
    )


_STORED: dict[str, Any] = {}


def stored_cut() -> Any:
    if "cut" not in _STORED:
        _STORED["cut"] = cut_of(analyse(stored_assertion()), "solved")
    return _STORED["cut"]


def stored_columns() -> tuple[list[str], list[int], list[int]]:
    """Each pair's item, its flip indicator and its signed change, from the generator's own
    record of the pairs and never from the store or the analysis."""
    pairs = replay_arms.pairs()
    return ([p["item"] for p in pairs], [int(p["a"] != p["b"]) for p in pairs], [p["b"] - p["a"] for p in pairs])


@pytest.mark.math
def test_pr39_the_stored_arms_give_their_two_by_two_and_the_arm_order_check() -> None:
    cut = stored_cut()
    n11, n10, n01, n00 = replay_arms.TWO_BY_TWO
    assert two_by_two(cut, "R") == (n11, n10, n01, n00) == (64, 21, 15, 100)
    r = sweep_of(cut, "R")
    assert r["n"] == 200 and r["arm_order_check"]["n_discordant"] == n10 + n01 == 36
    assert r["arm_order_check"]["p"] == pytest.approx(mcnemar_p(n10, n01), abs=1e-12)
    assert round(r["arm_order_check"]["p"], 3) == 0.405
    assert r["arm_order_check"]["can_reject"] is True
    assert r["rate_a"] == pytest.approx(0.425) and r["rate_b"] == pytest.approx(0.395)
    assert cut.ties == {"a": 85, "b": 79}  # every solved episode sits exactly at the cut


@pytest.mark.math
def test_pr39_the_item_clustered_interval_on_the_stored_arms_is_0_095_to_0_275() -> None:
    cut = stored_cut()
    flip = cut.pooled["flip_rate"]
    assert flip["estimate"] == pytest.approx(36 / 200) and flip["basis"] == "cluster_bootstrap"
    clusters, flips, _ = stored_columns()
    assert (flip["lo"], flip["hi"]) == cluster_bootstrap(clusters, flips, seed=STORED_SEED, b=10_000)
    assert round(flip["lo"], 3) == 0.095 and round(flip["hi"], 3) == 0.275
    # The item matters on these arms: the interval that ignores it is narrower.
    naive = observation_bootstrap(flips, seed=STORED_SEED, b=10_000)
    assert flip["lo"] < naive[0] and flip["hi"] > naive[1]
    assert cut.pooled["n"] == {"items": 50, "sweeps": 1}
    per_sweep = sweep_of(cut, "R")["flip_rate"]
    lo, hi = cp_two_sided(36, 200)
    assert per_sweep["basis"] == "exact_binomial"
    assert per_sweep["lo"] == pytest.approx(lo) and per_sweep["hi"] == pytest.approx(hi)
    assert (round(lo, 4), round(hi, 4)) == (0.1294, 0.2404)


@pytest.mark.math
def test_pr39_the_net_swing_on_the_stored_arms_is_b_minus_a_with_its_clustered_interval() -> None:
    """PR26 is A' minus A -- kept as written -- so the swing is ``(n01 - n10) / n`` and
    the output says which way it subtracts."""
    swing = stored_cut().pooled["net_swing"]
    assert swing["estimate"] == pytest.approx((15 - 21) / 200)
    assert swing["direction"] == "b_minus_a"
    assert round(swing["estimate"] * 100, 1) == -3.0
    assert swing["basis"] == "cluster_bootstrap"
    clusters, _, changes = stored_columns()
    assert (swing["lo"], swing["hi"]) == cluster_bootstrap(clusters, changes, seed=STORED_SEED, b=10_000)
    assert (round(swing["lo"], 3), round(swing["hi"], 3)) == (-0.080, 0.015)


@pytest.mark.math
def test_pr39_the_design_effect_and_the_outcome_on_the_stored_arms() -> None:
    cut = stored_cut()
    clusters, flips, _ = stored_columns()
    icc, m_bar, deff = icc1(clusters, flips)
    assert cut.design_effect["m_bar"] == m_bar == 4.0
    assert cut.design_effect["icc"] == pytest.approx(icc) and 0.0 < icc < 1.0
    assert cut.design_effect["deff"] == pytest.approx(1 + 3 * cut.design_effect["icc"]) == pytest.approx(deff)
    assert cut.outcome is None  # no floor declared
    assert cut.pooled["ineligibility_rate"] == 0.0
    assert cut.threshold == Decimal("1") and cut.name == "solved"


@pytest.mark.math
def test_pr39_the_interval_follows_the_declared_seed_and_moves_off_it() -> None:
    """The same arms under another seed give the reference's interval at that seed, which is not
    the first one: the interval is the procedure at the declared seed, not a property of the arms."""
    other = cut_of(analyse(stored_assertion(seed=STORED_SEED + 1)), "solved").pooled["flip_rate"]
    declared = stored_cut().pooled["flip_rate"]
    assert (other["lo"], other["hi"]) != (declared["lo"], declared["hi"])
    clusters, flips, _ = stored_columns()
    assert (other["lo"], other["hi"]) == cluster_bootstrap(clusters, flips, seed=STORED_SEED + 1, b=10_000)
