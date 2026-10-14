"""PR-3 oracle, the replicates packet: k calls per item, of which a pair is the case k = 2 --
invariants PR57 to PR76 of "Prove -- Spec PR Paired Replay", section 4.H, and named mutants 9 to
16. PR77 (the rendered Replicates section) is the output packet's, with PR7 and PR40 to PR55,
and is not here: section 7 lets a Session A cut PR-3 into two files, and this is the first.

Written by Session A on 2026-09-22 off ``pr2-build`` ``7bb1a3b`` (phases 1 and 2 built) plus the
two retrofits ruled the same day and committed first on this branch: R1 (``733ac35``, two names
into the PR-1 oracle's ``SPEC_PUBLIC_NAMES``) and R3 (``fd4266d``, a ``Cut`` declares its
comparison, ``gt`` or ``ge``, with no default). **Frozen 2026-09-22 in one commit over both PR-3
files, over the reviewed ``ef9f4ef``**, after Taylor approved the four tables in the handoff
(``log/prove-pr3-session-a/README.md``) and an independent recompute of every hard-coded
expectation passed (``recompute_expectations.py`` there, 83 of 83). Session B builds phase 3's
replicate half of ``src/proofload/paired.py``
-- ``SweepPair.more``, the k-arm assertion, ``ReplicateResult`` and ``replicates`` -- against this
file and does not edit it. Phase 3's names are read through ``getattr`` inside each test, so the
bare tree fails test by test and never at collection.

**What the packet is.** A sweep declares ``more``, the arms after ``a`` and ``b``, so a replicate
set is ``k = 2 + len(more)`` calls of one request in one sweep; the key is PR10's, unchanged; the
declared pair still carries the whole of section 4.C (PR61) and a declaration with no ``more``
produces what today's build produces (PR60). ``replicates`` is a second reader of the same
``PairAssertion`` and answers, per cut and under both action rules: ``agree@j``, how often the
first ``j`` calls all took the same action (PR65, PR66), and ``MS@j``, how often two sweeps'
``j``-call majorities agreed (PR67 to PR69), each with the item-clustered interval of PR28 through
the one ``_cluster_bootstrap`` (PR71), the fallback of PR31 pointed the other way (PR72), the
design effect of PR32 on that metric's own footing (PR73), no cross-cut and no cross-rule figure
(PR74), a paired step between prefixes and never two intervals to eyeball (PR75), and the cost
framing pre-declared whole (PR76).

**Conventions this file fixes for the build session** (section 2 leaves them open; each goes into
the spec's change log on the freeze):

- *Arm labels.* ``a`` and ``b`` keep their names; the arms in ``more`` are labelled by their
  1-based position in the declared order, ``"3"`` to ``"k"``, as strings. ``pairs`` gains one
  column per extra arm, ``value_3`` to ``value_k`` (``Decimal``), beside ``value_a`` and
  ``value_b``; at ``k = 2`` it has exactly the PR-1 oracle's nine columns.
  ``environment["sweeps"][<sweep>]`` gains the same labels.
- *``excluded`` at ``k > 2``.* One row per replicate set, as one pair is one row. ``arm`` keeps
  PR10's reading for ``unmatched`` -- the first arm, in declared order, that holds the key -- and
  ``detail`` names every arm that lacks it (PR62). A per-arm cause (``errored``,
  ``no_request_span``, ``retry_or_multicall``, ``malformed_body``, ``model_pin``,
  ``value_missing``, ``value_out_of_range``) names the failing arm's label; a comparison cause
  (``body``, ``body_field_absent``, ``target``, ``header``) reads ``"both"`` as it does at
  ``k = 2`` and names the differing arm in ``detail``. Tests build one failure per set, so the
  precedence between two causes on one set is not pinned (ambiguity 9 of the spec session).
- *PR57 fires in the constructor and at load.* ``Declaration(...)`` with two sweeps of different
  ``k``, or a run id repeated inside one sweep's ``arms``, raises ``DeclarationError``;
  ``from_toml`` therefore does too. ``SweepPair.arms`` is ``(a, b, *more)``.
- *The result.* ``ReplicateResult`` is the seven fields of section 2 and no other, one per
  declared cut in declaration order; ``replicates()`` returns ``()`` when every sweep is a pair.
  ``ReplicateResult.to_json()`` is one JSON object with the keys ``name``, ``threshold`` (the
  literal text), ``comparison``, ``k``, ``agree``, ``majority``, ``counts`` and ``cost_framing``,
  every number a JSON number, key order stable across calls, processes and hash seeds. The
  artifact ``replicates_by_cut.json`` -- top level, ``declaration_digest``, the ``cuts`` wrapper
  and the fact that nothing is written at ``k = 2`` -- is the CLI's and is the output packet's
  to pin.
- *Rules.* ``agree`` and ``majority`` are keyed ``"primary"`` then ``"sensitivity"``, in that
  order, always both (PR70). The primary is the cut's declared ``comparison``; the sensitivity is
  the other one. ``counts["rules"]`` says which is which.
- *``agree[rule]``.* ``"j2"`` to ``"jk"``, one block per prefix, every ``j`` (section 3 as
  written; ambiguity 6 of the spec session is one yes/no in the handoff), plus ``"steps"``: for
  each consecutive pair of prefixes, ``"j2_to_j3"`` and so on, the paired step of PR75. A prefix
  block is ``{estimate, lo, hi, basis, observation: "within_sweep", design_effect}`` and, under
  the fallback, ``upper_bound_by_observation: true``.
- *``majority[rule]``.* ``"j1"``, ``"j3"``, ... for odd ``j <= k`` and nothing else; a block is
  ``{estimate, lo, hi, basis, observation: "across_sweeps", design_effect}`` with the same
  fallback key. The observation is one item and one **unordered** pair of distinct sweeps whose
  two sets are both eligible, sweep pairs in declared order.
- *The fallback (PR72).* ``k_dis`` is the number of item clusters carrying at least one
  disagreement for that metric at that prefix under that rule; ``k_dis < 5`` gives ``hi = 1.0``,
  ``lo = scipy.stats.beta.ppf(0.05, G - k_dis, k_dis + 1)`` (``0.05 ** (1 / G)`` at zero),
  ``basis: "exact_lower_one_sided"``, ``upper_bound_by_observation: true``. A step whose either
  endpoint is under the fallback is ``basis: "not_estimated"`` with null bounds.
- *The design effect (PR73).* ``{icc, m_bar, deff}`` per block on PR32's footing: ``m_bar`` is
  observations per item for that metric -- the eligible sets per item for ``agree@j``, the eligible
  sweep pairs per item for ``MS@j`` -- and the one-way ANOVA cluster size ``m0`` sits in the ICC
  denominator when eligibility leaves the clusters unbalanced (ruled 2026-09-22).
- *``counts``.* ``items`` (``G``), ``sweeps`` (``S``), ``eligible_sets`` keyed by sweep,
  ``sweep_pairs`` keyed ``"S1|S2"`` (items with both sets eligible), ``excluded_by_arm`` keyed by
  arm label off this cut's rows of ``excluded``, ``ties`` keyed by arm label over all sweeps,
  ``rules`` and ``majority_stops_at`` (``k`` when odd, ``k - 1`` when even; PR68's "the artifact
  says so"). No key holds ``G x S``.
- *``cost_framing[rule]``.* Keyed by the odd ``j`` that have a majority. Each object carries
  ``per_10000`` -- ``{n, n_lo, n_hi, conditioning}`` with ``n = round(10000 * (1 - MS@j))``,
  ``n_lo`` from the interval's upper bound and ``n_hi`` from its lower bound -- **only when the
  declaration carries ``conditioning``**, ``dollars_per_decision`` only when ``cost`` was passed
  with a price, and ``latency_per_decision`` only when ``windows`` was passed. What is absent is
  absent, never zero (PR7). *Ruled 2026-09-22:* the two arithmetic rows read the two inputs the
  output packet's spec gained the same day. ``dollars_per_decision`` is ``{estimate,
  mean_input_tokens, price_per_input_token}`` with ``mean_input_tokens = cost.input_tokens /
  cost.recorded_spans`` and ``estimate = j * mean_input_tokens * price``, the price echoed as its
  literal; ``latency_per_decision`` is ``{median_call_s, serial_s, at_declared_concurrency_s}``
  with ``median_call_s`` the median of the per-sweep ``latency_s["median"]`` values
  ``windows.per_sweep`` carries, ``serial_s = j * median_call_s``, and
  ``at_declared_concurrency_s = serial_s / concurrency`` when every arm's recorded
  ``environment["sweeps"][S][arm]["concurrency"]`` is one non-null number, else absent.

**Invariant-to-test map** is in the handoff (``log/prove-pr3-session-a/README.md``). Every test
name starts ``test_prN_`` or ``test_control_``.

**Fixtures, and what each cannot express.** Every ``PairAssertion`` is built in test code or by
running a hand-built k-arm store through ``assert_pairs``; the three frames section 6 names are
here: a ``k = 5`` store with one arm errored on some items (PR63), a ``k = 5`` frame on which every
item agrees at every cut (PR72), and a ``k = 4`` frame whose only job is to be refused a majority
(PR68). No committed fixture carries a third arm, so none is used. ``S`` is never more than 3 in
this file, so whether an ordered or an unordered sweep pair is the ``MS@j`` observation at
``S > 3`` (ambiguity 5) is not pinned.

**Green before and after -- named so their green is not read as coverage.**
``test_pr71_no_default_rng_site_is_added_to_paired_py`` is green on the bare tree, because the
one site is already there, and stays green: it guards the build against adding a second. Every
other test in this file is red on the bare tree, on ``TypeError`` from ``Cut`` without
``comparison`` or from ``SweepPair`` without ``more``, or on ``AttributeError`` for
``ReplicateResult`` and ``replicates``. The PR60 digests were minted on the pre-amendment build
(``7bb1a3b``'s ``src/``) by ``mint_pr60.py`` in the handoff, so the test that carries them is red
on the bare tree only because it builds cuts with a comparison; on the build it is the
byte-identity guard.

**The three ``hypothesis`` tests are derandomized.**

**Named gaps, not pinned.** An empty cut under ``replicates()`` (ambiguity 7); cause precedence
on a set broken in two arms (ambiguity 9); the ``MS@j`` observation at ``S > 3`` (ambiguity 5);
a run id shared between two different sweeps; the order of ``excluded_by_arm``'s keys. (The
dollars and latency values and the ``comparison`` in the phase-2 artifacts were ruled 2026-09-22
and are pinned.)
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import itertools
import json
import math
import os
import pickle
import random
import re
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
from scipy.stats import beta

import poisson_prove
from poisson_prove import paired
from poisson_prove.episode import Episode
from poisson_prove.executor import derive_seed
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from poisson_prove.trace import Span, Trace

EPOCH = 1_790_000_000_000_000_000
SALT = "9f4a1c62d08e5b37"
REQUEST_SPAN = "scorer.request"
MODEL_PIN = "scorer-1.13.0"
VALUE_KEY = "answers.q1.score"
URL = "https://api.example.test/v1/evaluate"
CUT = "c60"
THRESHOLD = "0.60"
HI, LO = "0.95", "0.05"  # action 1 and action 0 under both rules at every cut here, never a tie
TIE = "0.60"  # action 1 under ge, action 0 under gt, at the c60 cut
B_SMALL = 400
SEED = 20260922
K = 5

REPLICATE_RESULT_FIELDS = (
    "name", "threshold", "k", "agree", "majority", "counts", "cost_framing",
)
JSON_KEYS = ("name", "threshold", "comparison", "k", "agree", "majority", "counts", "cost_framing")
RULES = ("primary", "sensitivity")
BLOCK_KEYS = frozenset({"estimate", "lo", "hi", "basis", "observation", "design_effect"})
COUNT_KEYS = frozenset({
    "items", "sweeps", "eligible_sets", "sweep_pairs", "excluded_by_arm", "ties", "rules",
    "majority_stops_at",
})
PREFIX = re.compile(r"\Aj(\d+)\Z")
STEP = re.compile(r"\Aj(\d+)_to_j(\d+)\Z")
OTHER = {"ge": "gt", "gt": "ge"}

# PR60: the bytes the pre-amendment build (``7bb1a3b``'s ``src/``) writes for ``pr60_store``
# through ``assert_pairs`` and ``analyse`` at ``k = 2``, minted by ``mint_pr60.py`` in the
# handoff through ``pr60_digests`` below, which masks what later rulings add on top of today's
# bytes: the declaration digest and block (they move with R3), the ``comparison`` the two
# artifacts print beside the threshold (ruled 2026-09-22), and the four timing columns phase 3's
# windows add to ``pairs`` (``TIMING_COLUMNS``). Every other byte is pinned.
TIMING_COLUMNS = ("start_ns_a", "end_ns_a", "start_ns_b", "end_ns_b")
PR60_PAIRS_SHA256 = "120c9c73ff9c68f9063b177da266d0f5712184f44238e359d551f3b7fa4f843e"
PR60_ASSERTION_SHA256 = "1599b827d6274ac7fd149dcba4ad47f43a75414ad4d2592b1b04dd14f7077526"
PR60_CONTINGENCY_SHA256 = "b4a14e176172f65823ec9276def0b1f9dfb6e1c03dbde6dde13fa2ded2a84809"
PR60_INTERVALS_SHA256 = "efefd40a6d2d63da52f090deb67e710f1d364fd3d7cb741683f486a796da6fb5"


def P() -> Any:
    """The module under test. Phase 3's names are read off it inside each test."""
    return paired


def labels(k: int) -> tuple[str, ...]:
    return ("a", "b", *(str(i) for i in range(3, k + 1)))


def value_columns(k: int) -> tuple[str, ...]:
    return ("value_a", "value_b", *(f"value_{i}" for i in range(3, k + 1)))


# ---------- reference implementations ----------


def act(literal: str, threshold: str, comparison: str) -> int:
    value, cut = Decimal(literal), Decimal(threshold)
    return int(value >= cut) if comparison == "ge" else int(value > cut)


def agree_j(acts: Sequence[int], j: int) -> int:
    return int(len(set(acts[:j])) == 1)


def maj_j(acts: Sequence[int], j: int) -> int:
    return int(2 * sum(acts[:j]) > j)


def cluster_bootstrap(
    clusters: Sequence[Any], values: Sequence[float], *, seed: int, b: int
) -> tuple[float, float]:
    """The twelve lines of ``scripts/repro_r1_agreement.py``, as the PR-2 oracle carries them."""
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({"cluster": list(clusters), "v": list(values)})
    groups = [g["v"].to_numpy() for _, g in frame.groupby("cluster", sort=True)]
    idx = rng.integers(0, len(groups), size=(b, len(groups)))
    draws = np.array([np.concatenate([groups[i] for i in row]).mean() for row in idx])
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def observation_bootstrap(values: Sequence[float], *, seed: int, b: int) -> tuple[float, float]:
    """The naive bootstrap PR71 forbids (named mutant 11): observations resampled, the item
    ignored."""
    rng = np.random.default_rng(seed)
    v = np.asarray(list(values), dtype=float)
    idx = rng.integers(0, len(v), size=(b, len(v)))
    draws = v[idx].mean(axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def cp_lower_one_sided(k_dis: int, g: int) -> float:
    """The one-sided exact 95% Clopper-Pearson lower bound on the item-level agreement
    probability with ``g - k_dis`` agreeing items of ``g``."""
    return float(beta.ppf(0.05, g - k_dis, k_dis + 1))


def icc1(clusters: Sequence[Any], values: Sequence[float]) -> tuple[float, float, float]:
    """One-way ANOVA ``ICC(1)`` with the ANOVA cluster size ``m0`` in the denominator (ruled
    2026-09-22) and ``m_bar = N / G`` in the design effect: ``(icc, m_bar, deff)``."""
    frame = pd.DataFrame({"c": list(clusters), "y": [float(v) for v in values]})
    total, g = len(frame), frame["c"].nunique()
    m_bar = total / g
    if g < 2 or total <= g:
        return 0.0, m_bar, 1.0
    grand = frame["y"].mean()
    by = frame.groupby("c")["y"]
    sizes, means = by.size().astype(float), by.mean()
    msb = float((sizes * (means - grand) ** 2).sum()) / (g - 1)
    msw = float(((frame["y"] - frame["c"].map(means)) ** 2).sum()) / (total - g)
    m0 = (total - float((sizes**2).sum()) / total) / (g - 1)
    denominator = msb + (m0 - 1) * msw
    icc = 0.0 if denominator == 0 else max(0.0, (msb - msw) / denominator)
    return icc, m_bar, 1 + (m_bar - 1) * icc


# ---------- helpers: a k-arm PairAssertion built in test code ----------


@dataclasses.dataclass
class RSet:
    """One replicate set: one item in one sweep, ``k`` stored literals in declared arm order."""

    cluster: str
    values: tuple[str, ...]
    sweep: str = "S1"
    cut: str = CUT

    @property
    def k(self) -> int:
        return len(self.values)


def acts_of(r: RSet, threshold: str = THRESHOLD, comparison: str = "ge") -> tuple[int, ...]:
    return tuple(act(v, threshold, comparison) for v in r.values)


def from_actions(
    cluster: str, actions: Sequence[int], *, sweep: str = "S1", cut: str = CUT
) -> RSet:
    return RSet(cluster, tuple(HI if a else LO for a in actions), sweep=sweep, cut=cut)


def pairs_frame(rows: Sequence[RSet]) -> pd.DataFrame:
    ks = {r.k for r in rows}
    assert len(ks) == 1, ks
    (k,) = ks
    columns = [
        "sweep", "cut", "cluster", "config_hash", "replicate_index", "request_digest",
        "exemptions_exercised", *value_columns(k),
    ]
    records = [
        {
            "sweep": r.sweep, "cut": r.cut, "cluster": r.cluster,
            "config_hash": config_hash({"item": r.cluster, "cut": r.cut}),
            "replicate_index": 0, "request_digest": "0" * 64, "exemptions_exercised": (),
            **{col: Decimal(v) for col, v in zip(value_columns(k), r.values, strict=True)},
        }
        for r in rows
    ]
    return pd.DataFrame(records, columns=columns)


def excluded_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=[
        "sweep", "cut", "cluster", "config_hash", "replicate_index", "cause", "arm", "detail",
    ])


def names_arm(detail: str, label: str) -> bool:
    """``detail`` names an arm as ``arm <label>``, the phrase phase 1's build already uses."""
    return re.search(rf"\barm {re.escape(label)}\b", str(detail)) is not None


def excluded_row(
    cluster: str, cause: str, arm: str, *, sweep: str = "S1", cut: str = CUT, detail: str = ""
) -> dict[str, Any]:
    return {
        "sweep": sweep, "cut": cut, "cluster": cluster,
        "config_hash": config_hash({"item": cluster, "cut": cut}), "replicate_index": 0,
        "cause": cause, "arm": arm, "detail": detail,
    }


def counts_for(pairs: pd.DataFrame, excluded: pd.DataFrame, cuts: Sequence[str]) -> dict[str, Any]:
    """PR20's block, consistent with the two frames, as the PR-2 oracle builds it."""
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


def sweep_pair(name: str, k: int, *, more: Sequence[str] | None = None) -> Any:
    extra = tuple(f"{name}-{i}" for i in range(3, k + 1)) if more is None else tuple(more)
    if not extra:
        return P().SweepPair(name=name, a=f"{name}-a", b=f"{name}-b")
    return P().SweepPair(name=name, a=f"{name}-a", b=f"{name}-b", more=extra)


def declaration(
    *,
    cuts: Sequence[tuple[str, ...]] = ((CUT, THRESHOLD, "ge"),),
    sweeps: Sequence[str] = ("S1",),
    k: int = K,
    b: int = B_SMALL,
    seed: int = SEED,
    floor: str | None = None,
    conditioning: str | None = None,
    more: Mapping[str, Sequence[str]] | None = None,
    **over: Any,
) -> Any:
    """A cut is ``(name, threshold)`` or ``(name, threshold, comparison)``, ``"ge"`` when not
    said; every sweep has ``k`` arms, its extra run ids ``<sweep>-3`` .. unless ``more`` names
    them."""
    kwargs: dict[str, Any] = {
        "value_key": VALUE_KEY, "cluster_key": "item", "stratum_key": "cut",
        "cuts": tuple(
            P().Cut(name=c[0], threshold=Decimal(c[1]), comparison=c[2] if len(c) > 2 else "ge")
            for c in cuts
        ),
        "sweeps": tuple(
            sweep_pair(s, k, more=None if more is None else more.get(s)) for s in sweeps
        ),
        "request_span": REQUEST_SPAN, "model_key": "model", "model_pin": MODEL_PIN,
        "exemptions": ("x-request-id",), "headers": "not_recorded", "retries": "not_recorded",
        "bootstrap_b": b, "bootstrap_seed": seed,
        "floor": None if floor is None else Decimal(floor),
        "conditioning": conditioning,
    }
    kwargs.update(over)
    return P().Declaration(**kwargs)


THRESHOLDS = {CUT: THRESHOLD, "c50": "0.50", "c90": "0.90"}


def assertion(
    rows: Sequence[RSet],
    *,
    excluded: Sequence[Mapping[str, Any]] = (),
    decl: Any = None,
    comparison: str = "ge",
    **decl_over: Any,
) -> Any:
    """A ``PairAssertion`` over hand-built sets. The declaration lists exactly the cuts and
    sweeps the rows carry unless one is passed, with ``k`` read off the rows, so no cut is empty."""
    if decl is None:
        cuts = list(dict.fromkeys(r.cut for r in rows))
        sweeps = list(dict.fromkeys(r.sweep for r in rows))
        decl = declaration(
            cuts=[(c, THRESHOLDS.get(c, THRESHOLD), comparison) for c in cuts], sweeps=sweeps,
            k=rows[0].k, **decl_over,
        )
    pairs = pairs_frame(rows)
    dropped = excluded_frame(excluded)
    return P().PairAssertion(
        declaration=decl, pairs=pairs, excluded=dropped, environment={"sweeps": {}, "gaps": []},
        counts=counts_for(pairs, dropped, [c.name for c in decl.cuts]),
    )


def grid(
    g: int,
    sweeps: Sequence[str],
    pattern: Callable[[int, str], Sequence[int]],
    *,
    cut: str = CUT,
) -> list[RSet]:
    """``g`` items by the sweeps, each set's ``k`` actions given by ``pattern(item, sweep)``."""
    return [
        from_actions(f"i{i:03d}", pattern(i, s), sweep=s, cut=cut)
        for i in range(g)
        for s in sweeps
    ]


def all_agree(_: int, __: str) -> tuple[int, ...]:
    return (1,) * K


def replicates(a: Any, **kw: Any) -> Any:
    return P().replicates(a, **kw)


def result_of(a: Any, name: str = CUT, **kw: Any) -> Any:
    results = replicates(a, **kw)
    by_name = {r.name: r for r in results}
    assert name in by_name, list(by_name)
    return by_name[name]


def loaded(r: Any) -> dict[str, Any]:
    payload = json.loads(r.to_json())
    assert isinstance(payload, dict)
    return payload


def prefixes(rule_block: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    out: dict[int, Mapping[str, Any]] = {}
    for key, value in rule_block.items():
        m = PREFIX.fullmatch(key)
        if m:
            out[int(m.group(1))] = value
    return out


def walk(node: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    yield path, node
    if isinstance(node, Mapping):
        for key, value in node.items():
            yield from walk(value, (*path, str(key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, (*path, f"[{i}]"))


def reference_agree(
    rows: Sequence[RSet], j: int, *, comparison: str = "ge", threshold: str = THRESHOLD
) -> tuple[float, list[str], list[int]]:
    indicators = [agree_j(acts_of(r, threshold, comparison), j) for r in rows]
    return float(np.mean(indicators)), [r.cluster for r in rows], indicators


def reference_ms(
    rows: Sequence[RSet], j: int, sweeps: Sequence[str], *, comparison: str = "ge",
    threshold: str = THRESHOLD,
) -> tuple[float, list[str], list[int]]:
    """One observation per item and per unordered pair of distinct sweeps, both sets eligible."""
    by_item: dict[str, dict[str, int]] = {}
    for r in rows:
        by_item.setdefault(r.cluster, {})[r.sweep] = maj_j(acts_of(r, threshold, comparison), j)
    clusters: list[str] = []
    indicators: list[int] = []
    for item in sorted(by_item):
        majorities = by_item[item]
        for s1, s2 in itertools.combinations(sweeps, 2):
            if s1 in majorities and s2 in majorities:
                clusters.append(item)
                indicators.append(int(majorities[s1] == majorities[s2]))
    return float(np.mean(indicators)), clusters, indicators


def assert_block_is(
    block: Mapping[str, Any], estimate: float, clusters: Sequence[str],
    indicators: Sequence[int], *, seed: int, b: int, observation: str,
) -> None:
    lo, hi = cluster_bootstrap(clusters, indicators, seed=seed, b=b)
    assert block["basis"] == "cluster_bootstrap", block
    assert block["estimate"] == pytest.approx(estimate, abs=1e-12)
    assert math.isclose(block["lo"], lo, abs_tol=1e-12) and math.isclose(block["hi"], hi, abs_tol=1e-12)
    assert block["observation"] == observation
    icc, m_bar, deff = icc1(clusters, indicators)
    assert block["design_effect"]["icc"] == pytest.approx(icc, abs=1e-12)
    assert block["design_effect"]["m_bar"] == pytest.approx(m_bar, abs=1e-12)
    assert block["design_effect"]["deff"] == pytest.approx(deff, abs=1e-12)


# ---------- helpers: a k-arm store the phase 1 assertion reads ----------


@dataclasses.dataclass
class KRow:
    """One item in one sweep, as ``k`` stored episodes. Every per-arm override is keyed by the
    arm label, so a row can break exactly one arm in exactly one way."""

    item: str
    cut: str
    values: tuple[str, ...]
    error: dict[str, str] = dataclasses.field(default_factory=dict)
    n_spans: dict[str, int] = dataclasses.field(default_factory=dict)
    absent: frozenset[str] = frozenset()
    value_missing: frozenset[str] = frozenset()
    model: dict[str, str] = dataclasses.field(default_factory=dict)
    body_extra: dict[str, str] = dataclasses.field(default_factory=dict)  # label -> raw JSON field


def _span(body: str, k: int) -> Span:
    return Span(
        span_id=f"{k + 1:016x}", parent_id=None, kind="http", name=REQUEST_SPAN,
        start_ns=EPOCH + k * 1_000_000, end_ns=EPOCH + k * 1_000_000 + 500_000, input=body,
        output='{"answers": {"q1": {"score": 0.62}}}', tokens={"in": 400, "out": 12},
        attrs={"url.full": URL, "http.request.method": "POST"},
    )


def _record(run_id: str, row: KRow, label: str) -> EpisodeRecord:
    config = {"item": row.item, "cut": row.cut}
    seed = derive_seed(SALT, config_hash(config), 0)
    if label in row.error:
        return EpisodeRecord.errored(
            run_id=run_id, config=config, seed=seed, replicate_index=0, error=row.error[label],
            wall_time=0.1,
        )
    model = row.model.get(label, MODEL_PIN)
    body = (
        f'{{"model": "{model}", "state": "state of {row.item}", "temperature": 0.30, '
        '"max_tokens": 64' + (", " + row.body_extra[label] if label in row.body_extra else "")
        + "}"
    )
    spans = [_span(body, k) for k in range(row.n_spans.get(label, 1))]
    meta: dict[str, Any] = {"trace": Trace(spans=tuple(spans), source="record").to_dict()}
    if label not in row.value_missing:
        meta["answers"] = {"q1": {"score": row.values[labels(len(row.values)).index(label)]}}
    episode = Episode(outcome="scored", t=1.0, horizon=10.0, meta=meta)
    return EpisodeRecord.from_episode(
        episode, run_id=run_id, config=config, seed=seed, replicate_index=0, wall_time=0.1,
    )


def make_k_store(
    root: Path,
    rows: Sequence[KRow],
    *,
    k: int = K,
    sweeps: Sequence[str] = ("S1",),
    run_ids: Mapping[str, Mapping[str, str]] | None = None,
    creation_order: Sequence[str] | None = None,
    per_sweep: Mapping[str, Sequence[KRow]] | None = None,
    name: str = "store",
) -> Store:
    """``rows`` are replayed in every sweep, or ``per_sweep[sweep]`` where given.
    ``run_ids[sweep][label]`` names a run; the default is ``<sweep>-<label>``. ``creation_order``
    is the label order the runs are written in."""
    store = Store(root / name)
    for sweep in sweeps:
        sweep_rows = rows if per_sweep is None or sweep not in per_sweep else per_sweep[sweep]
        for label in creation_order or labels(k):
            run_id = (run_ids or {}).get(sweep, {}).get(label, f"{sweep}-{label}")
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
                _record(run_id, row, label) for row in sweep_rows if label not in row.absent
            ])
            store.mark_complete(run_id)
    return store


def k_rows(g: int, pattern: Callable[[int], Sequence[int]], *, cut: str = CUT, k: int = K) -> list[KRow]:
    return [
        KRow(f"{cut}-i{i:03d}", cut, tuple(HI if a else LO for a in pattern(i)))
        for i in range(g)
    ]


def pr60_store(root: Path) -> Store:
    """The fixed ``k = 2`` store the PR60 digests were minted on: two cuts, four items each,
    two sweeps, values chosen so c60 has three flipping items and a tie in arm b."""
    rows = [
        KRow("c60-p0", CUT, ("0.75", "0.60")), KRow("c60-p1", CUT, ("0.25", "0.75")),
        KRow("c60-p2", CUT, ("0.40", "0.99")), KRow("c60-p3", CUT, ("0.00", "0.10")),
        KRow("c50-q0", "c50", ("0.80", "0.90")), KRow("c50-q1", "c50", ("0.55", "0.51")),
        KRow("c50-q2", "c50", ("0.70", "0.20")), KRow("c50-q3", "c50", ("0.10", "0.30")),
    ]
    return make_k_store(root, rows, k=2, sweeps=("S1", "S2"))


def pr60_digests(store: Store, decl: Any) -> dict[str, str]:
    """The four PR60 digests off a store and a declaration, with the declaration digest masked
    and the declaration block dropped, exactly as ``mint_pr60.py`` computes them."""
    a = P().assert_pairs(store, decl)
    result = P().analyse(a)
    mask = re.compile(r'"declaration_digest": "[0-9a-f]{64}"|\n *"comparison": "g[te]",?')
    payload = json.loads(a.to_json())
    payload.pop("declaration", None)
    payload.pop("declaration_digest", None)
    for row in payload.get("pairs", []):
        if isinstance(row, dict):
            for column in TIMING_COLUMNS:
                row.pop(column, None)
    frozen = [c for c in a.pairs.columns if c not in TIMING_COLUMNS]
    frame = a.pairs[frozen].astype(str).to_csv(index=False)
    return {
        "pairs": hashlib.sha256(frame.encode()).hexdigest(),
        # PF0 (Q4): each arm's identity echoes the manifest's version under its new key; under the old
        # key the assertion is the pre-amendment build's byte for byte.
        "assertion": hashlib.sha256(json.dumps(
            json.loads(json.dumps(payload).replace('"poisson_prove_version":', '"proofload_version":')), sort_keys=True,
        ).encode()).hexdigest(),
        "contingency": hashlib.sha256(mask.sub("", result.contingency_json()).encode()).hexdigest(),
        "intervals": hashlib.sha256(mask.sub("", result.intervals_json()).encode()).hexdigest(),
    }


def store_declaration(**over: Any) -> Any:
    return declaration(cuts=((CUT, THRESHOLD, "ge"), ("c50", "0.50", "ge")), **over)


# ---------- the control: replicates reads what assert_pairs emits ----------


CONTROL_PATTERN: dict[str, tuple[int, ...]] = {
    "c60-i000": (1, 1, 1, 1, 1), "c60-i001": (1, 0, 1, 1, 0), "c60-i002": (0, 0, 1, 0, 0),
    "c50-i000": (0, 0, 0, 0, 0), "c50-i001": (1, 1, 0, 1, 1), "c50-i002": (1, 0, 0, 0, 1),
}


def control_rows() -> list[KRow]:
    return [
        KRow(item, item[:3], tuple(HI if a else LO for a in acts))
        for item, acts in CONTROL_PATTERN.items()
    ]


def control_sets() -> list[RSet]:
    return [
        from_actions(item, acts, sweep=s, cut=item[:3])
        for item, acts in CONTROL_PATTERN.items()
        for s in ("S1", "S2")
    ]


def test_control_replicates_consumes_the_frames_assert_pairs_emits(tmp_path: Path) -> None:
    """The one road through phase 1 at ``k = 5``: a hand-built five-arm store, ``assert_pairs``,
    then ``replicates`` beside ``analyse``. Every later test builds its ``PairAssertion``
    directly; this is what says the two shapes agree."""
    store = make_k_store(tmp_path, control_rows(), k=5, sweeps=("S1", "S2"))
    decl = store_declaration(sweeps=("S1", "S2"))
    a = P().assert_pairs(store, decl)
    assert set(value_columns(5)) <= set(a.pairs.columns), set(a.pairs.columns)
    assert len(a.pairs) == 12 and len(a.excluded) == 0
    assert set(a.environment["sweeps"]["S1"]) == set(labels(5))
    results = replicates(a)
    assert [r.name for r in results] == [CUT, "c50"]
    r = results[0]
    assert r.k == 5 and r.threshold == Decimal(THRESHOLD)
    assert sorted(prefixes(r.agree["primary"])) == [2, 3, 4, 5]
    assert sorted(prefixes(r.majority["primary"])) == [1, 3, 5]
    pooled = {c.name: c for c in P().analyse(a).cuts}[CUT].pooled["flip_rate"]["estimate"]
    assert r.agree["primary"]["j2"]["estimate"] == pytest.approx(1 - pooled)
    assert r.agree["primary"]["j2"]["estimate"] == pytest.approx(2 / 3)  # i001 and i002 flip
    assert r.agree["primary"]["j5"]["estimate"] == pytest.approx(1 / 3)
    assert r.counts["eligible_sets"] == {"S1": 3, "S2": 3}


def test_control_a_hand_built_assertion_reads_like_the_stored_one(tmp_path: Path) -> None:
    store = make_k_store(tmp_path, control_rows(), k=5, sweeps=("S1", "S2"))
    decl = store_declaration(sweeps=("S1", "S2"))
    stored = replicates(P().assert_pairs(store, decl))
    built = replicates(assertion(control_sets(), decl=decl))
    assert [r.to_json() for r in stored] == [r.to_json() for r in built]


# ---------- PR57: arms are (a, b, *more), one k per declaration, no repeated run id ----------


def test_pr57_a_sweeps_arms_are_a_b_then_more_in_that_order_and_k_is_two_plus_len_more() -> None:
    s = P().SweepPair(name="S1", a="run-a", b="run-b", more=("run-x", "run-y", "run-z"))
    assert s.arms == ("run-a", "run-b", "run-x", "run-y", "run-z")
    assert dataclasses.is_dataclass(P().SweepPair) and P().SweepPair.__dataclass_params__.frozen
    r = result_of(assertion(grid(6, ["S1"], all_agree)))
    assert r.k == 5 == 2 + len(declaration().sweeps[0].more)


@pytest.mark.parametrize("k_second", [2, 3, 4])
def test_pr57_two_sweeps_with_different_replicate_counts_are_refused_naming_both(k_second: int) -> None:
    """``agree@k`` at two different ``k`` is two estimands under one name."""
    paired = P()
    declaration(sweeps=("S1", "S2"), k=5)  # the control: two sweeps at one k load
    with pytest.raises(paired.DeclarationError) as caught:
        paired.Declaration(**{
            **dataclasses.asdict(declaration(k=5)),
            "cuts": declaration(k=5).cuts,
            "sweeps": (sweep_pair("S1", 5), sweep_pair("S2", k_second)),
        })
    message = str(caught.value)
    assert re.search(r"\bS1\b", message) and re.search(r"\bS2\b", message), message
    assert re.search(r"\b5\b", message) and re.search(rf"\b{k_second}\b", message), message


def test_pr57_two_sweeps_with_different_replicate_counts_are_refused_at_load_too(tmp_path: Path) -> None:
    load(tmp_path, toml_text(), "control.toml")
    text = toml_text(sweeps=[
        {"name": '"S1"', "a": '"S1-a"', "b": '"S1-b"', "more": '["S1-3", "S1-4", "S1-5"]'},
        {"name": '"S2"', "a": '"S2-a"', "b": '"S2-b"', "more": '["S2-3"]'},
    ])
    with pytest.raises(P().DeclarationError):
        load(tmp_path, text)


@pytest.mark.parametrize(
    "more",
    [("S1-a",), ("S1-b",), ("S1-3", "S1-3"), ("S1-3", "S1-4", "S1-3")],
    ids=["a_again", "b_again", "third_twice", "third_thrice"],
)
def test_pr57_a_run_id_repeated_inside_one_sweeps_arms_is_refused(tmp_path: Path, more: tuple[str, ...]) -> None:
    paired = P()
    with pytest.raises(paired.DeclarationError):
        declaration(more={"S1": more}, k=2 + len(more))
    text = toml_text(sweeps=[
        {"name": '"S1"', "a": '"S1-a"', "b": '"S1-b"', "more": json.dumps(list(more))},
    ])
    with pytest.raises(paired.DeclarationError):
        load(tmp_path, text)


# ---------- PR58: the TOML key ``more``, optional, absent == empty ----------


TOML_TOP: dict[str, str] = {
    "value_key": f'"{VALUE_KEY}"', "cluster_key": '"item"', "stratum_key": '"cut"',
    "request_span": f'"{REQUEST_SPAN}"', "model_key": '"model"', "model_pin": f'"{MODEL_PIN}"',
    "exemptions": '["x-request-id"]', "headers": '"not_recorded"', "retries": '"not_recorded"',
    "bootstrap_b": str(B_SMALL), "bootstrap_seed": str(SEED),
}


def toml_text(
    *,
    top: Mapping[str, str] | None = None,
    cuts: Sequence[Mapping[str, str]] | None = None,
    sweeps: Sequence[Mapping[str, str]] | None = None,
) -> str:
    merged = dict(TOML_TOP)
    merged.update(top or {})
    lines = [f"{k} = {v}" for k, v in merged.items()]
    cut_tables = [{"name": f'"{CUT}"', "threshold": THRESHOLD, "comparison": '"ge"'}] if cuts is None else cuts
    sweep_tables = (
        [{"name": '"S1"', "a": '"S1-a"', "b": '"S1-b"', "more": '["S1-3", "S1-4", "S1-5"]'}]
        if sweeps is None else sweeps
    )
    for header, tables in (("cuts", cut_tables), ("sweeps", sweep_tables)):
        for table in tables:
            lines += ["", f"[[{header}]]"] + [f"{k} = {v}" for k, v in table.items()]
    return "\n".join(lines) + "\n"


def load(tmp_path: Path, text: str, name: str = "decl.toml") -> Any:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return P().Declaration.from_toml(path)


def test_pr58_more_is_a_list_of_strings_inside_a_sweep_table_in_declared_order(tmp_path: Path) -> None:
    d = load(tmp_path, toml_text(sweeps=[
        {"name": '"S1"', "a": '"S1-a"', "b": '"S1-b"', "more": '["S1-z", "S1-m", "S1-c"]'},
    ]))
    (s,) = d.sweeps
    assert s.more == ("S1-z", "S1-m", "S1-c") and s.arms == ("S1-a", "S1-b", "S1-z", "S1-m", "S1-c")


def test_pr58_an_absent_more_and_an_empty_more_load_to_the_same_declaration_and_digest(tmp_path: Path) -> None:
    absent = load(tmp_path, toml_text(sweeps=[{"name": '"S1"', "a": '"S1-a"', "b": '"S1-b"'}]), "absent.toml")
    empty = load(tmp_path, toml_text(sweeps=[{"name": '"S1"', "a": '"S1-a"', "b": '"S1-b"', "more": "[]"}]), "empty.toml")
    assert absent == empty and absent.digest == empty.digest
    assert absent.sweeps[0].more == () and absent.sweeps[0].arms == ("S1-a", "S1-b")
    built = P().SweepPair(name="S1", a="S1-a", b="S1-b")
    assert built == absent.sweeps[0] and built.more == ()


@pytest.mark.parametrize(
    ("key", "value"),
    [("c", '"S1-c"'), ("arms", '["S1-3"]'), ("k", "5"), ("mores", '["S1-3"]')],
)
def test_pr58_pr8_is_unchanged_an_unknown_sweep_key_beside_more_is_still_refused(tmp_path: Path, key: str, value: str) -> None:
    load(tmp_path, toml_text(), "control.toml")
    with pytest.raises(P().DeclarationError):
        load(tmp_path, toml_text(sweeps=[
            {"name": '"S1"', "a": '"S1-a"', "b": '"S1-b"', "more": '["S1-3"]', key: value},
        ]))


@pytest.mark.parametrize("value", ['"S1-3"', "[3, 4]", '[["S1-3"]]', "true"])
def test_pr58_more_that_is_not_a_list_of_strings_is_refused(tmp_path: Path, value: str) -> None:
    load(tmp_path, toml_text(), "control.toml")
    with pytest.raises(P().DeclarationError):
        load(tmp_path, toml_text(sweeps=[
            {"name": '"S1"', "a": '"S1-a"', "b": '"S1-b"', "more": value},
        ]))


# ---------- PR59: the digest covers more ----------


def test_pr59_adding_removing_and_reordering_an_arm_each_change_the_digest() -> None:
    base = declaration(more={"S1": ("S1-3", "S1-4", "S1-5")}, k=5).digest
    added = declaration(more={"S1": ("S1-3", "S1-4", "S1-5", "S1-6")}, k=6).digest
    removed = declaration(more={"S1": ("S1-3", "S1-4")}, k=4).digest
    reordered = declaration(more={"S1": ("S1-4", "S1-3", "S1-5")}, k=5).digest
    renamed = declaration(more={"S1": ("S1-3", "S1-4", "S1-x")}, k=5).digest
    pair = declaration(k=2).digest
    assert len({base, added, removed, reordered, renamed, pair}) == 6
    assert declaration(more={"S1": ("S1-3", "S1-4", "S1-5")}, k=5).digest == base


RUN_IDS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=8)


@settings(max_examples=60, deadline=None, derandomize=True)
@given(first=st.lists(RUN_IDS, unique=True, max_size=4), second=st.lists(RUN_IDS, unique=True, max_size=4))
def test_pr59_property_two_declarations_share_a_digest_only_if_more_is_the_same_sequence(
    first: list[str], second: list[str]
) -> None:
    ids_first = tuple(f"x-{i}" for i in first)
    ids_second = tuple(f"x-{i}" for i in second)
    a = declaration(more={"S1": ids_first}, k=2 + len(ids_first))
    b = declaration(more={"S1": ids_second}, k=2 + len(ids_second))
    assert (a.digest == b.digest) == (ids_first == ids_second)


# ---------- PR60: k = 2 is byte-identical, and replicates() returns nothing for it ----------


def test_pr60_replicates_returns_an_empty_tuple_when_every_sweep_is_a_pair(tmp_path: Path) -> None:
    built = assertion([RSet("i0", ("0.95", "0.05")), RSet("i1", ("0.95", "0.95"))])
    assert replicates(built) == ()
    stored = P().assert_pairs(pr60_store(tmp_path), store_declaration(sweeps=("S1", "S2"), k=2))
    assert replicates(stored) == ()
    assert list(stored.pairs.columns) == [
        "sweep", "cut", "cluster", "config_hash", "replicate_index", "request_digest",
        "exemptions_exercised", "value_a", "value_b", *TIMING_COLUMNS,
    ]


def test_pr60_at_k_two_the_frames_and_both_phase_two_artifacts_are_the_bytes_the_pre_amendment_build_wrote(
    tmp_path: Path,
) -> None:
    """Minted on ``7bb1a3b``'s ``src/`` (no ``more``, no ``comparison``, no timing) by
    ``mint_pr60.py`` through ``pr60_digests``: the ``pairs`` frame's nine frozen columns,
    ``pair_assertion.json`` without its declaration block, digest and timing columns,
    ``contingency_by_cut.json`` and ``intervals_by_cut.json`` with the digest and the
    ``comparison`` line masked. What the masks cover was ruled in after the mint; every other
    byte is pinned, so a build that changes a ``k = 2`` byte anywhere else fails here."""
    digests = pr60_digests(pr60_store(tmp_path), store_declaration(sweeps=("S1", "S2"), k=2))
    assert digests == {
        "pairs": PR60_PAIRS_SHA256, "assertion": PR60_ASSERTION_SHA256,
        "contingency": PR60_CONTINGENCY_SHA256, "intervals": PR60_INTERVALS_SHA256,
    }


def test_pr60_a_sweep_pair_built_without_more_is_the_sweep_pair_built_with_an_empty_more() -> None:
    paired = P()
    assert paired.SweepPair(name="S1", a="x", b="y") == paired.SweepPair(name="S1", a="x", b="y", more=())
    assert declaration(k=2).digest == declaration(more={"S1": ()}, k=2).digest


# ---------- PR61: the declared pair carries the whole of section 4.C ----------


def test_pr61_arms_three_to_k_move_no_byte_of_the_two_phase_two_artifacts_and_do_move_the_replicates() -> None:
    """Named mutant 15. Two assertions under one declaration, identical in arms a and b, wild in
    arms 3 to 5: ``analyse`` writes the same bytes for both and ``replicates`` does not."""
    def tame(i: int, s: str) -> tuple[int, ...]:
        return (1, 0, 1, 1, 0) if i < 6 else (1, 1, 1, 1, 1)

    def wild(i: int, s: str) -> tuple[int, ...]:
        return (1, 0, 0, 0, 1) if i < 6 else (1, 1, 0, 0, 0)

    a = assertion(grid(12, ["S1", "S2", "S3"], tame), b=300)
    b = assertion(grid(12, ["S1", "S2", "S3"], wild), decl=a.declaration)
    ra, rb = P().analyse(a), P().analyse(b)
    assert ra.contingency_json() == rb.contingency_json()
    assert ra.intervals_json() == rb.intervals_json()
    assert result_of(a).to_json() != result_of(b).to_json()
    cut = {c.name: c for c in ra.cuts}[CUT]
    assert (cut.per_sweep[0]["n11"], cut.per_sweep[0]["n10"], cut.per_sweep[0]["n01"], cut.per_sweep[0]["n00"]) == (6, 6, 0, 0)


def test_pr61_the_pair_statistics_at_k_five_equal_the_same_rows_analysed_as_pairs() -> None:
    def pattern(i: int, s: str) -> tuple[int, ...]:
        return ((i + ord(s[-1])) % 2, (i // 2) % 2, 1, 0, 1)

    rows = grid(10, ["S1", "S2", "S3"], pattern)
    five = P().analyse(assertion(rows, b=200))
    pairs = [RSet(r.cluster, r.values[:2], sweep=r.sweep, cut=r.cut) for r in rows]
    two = P().analyse(assertion(pairs, b=200))
    mask = re.compile(r'"declaration_digest": "[0-9a-f]{64}"')
    assert mask.sub("", five.contingency_json()) == mask.sub("", two.contingency_json())
    assert mask.sub("", five.intervals_json()) == mask.sub("", two.intervals_json())


def test_pr61_a_tie_in_arm_three_is_not_a_pair_tie_and_is_a_replicate_tie() -> None:
    rows = [RSet("i0", (HI, HI, TIE, HI, TIE)), RSet("i1", (TIE, LO, LO, LO, LO))]
    cut = {c.name: c for c in P().analyse(assertion(rows)).cuts}[CUT]
    assert cut.ties == {"a": 1, "b": 0}
    assert result_of(assertion(rows)).counts["ties"] == {"a": 1, "b": 0, "3": 1, "4": 0, "5": 1}


# ---------- PR62: matched across all k arms ----------


def test_pr62_a_key_absent_from_one_arm_makes_the_set_unmatched_and_names_the_arm_that_lacked_it(tmp_path: Path) -> None:
    rows = k_rows(4, lambda i: (1, 1, 1, 1, 1))
    rows[1] = dataclasses.replace(rows[1], absent=frozenset({"4"}))
    rows[2] = dataclasses.replace(rows[2], absent=frozenset({"a"}))
    a = P().assert_pairs(make_k_store(tmp_path, rows), declaration())
    assert set(a.pairs["cluster"]) == {"c60-i000", "c60-i001", "c60-i003"}
    lacking_4 = a.excluded[a.excluded["cluster"] == "c60-i001"].iloc[0]
    lacking_a = a.excluded[a.excluded["cluster"] == "c60-i002"].iloc[0]
    assert lacking_4["cause"] == "unmatched" and lacking_4["arm"] == "a" and names_arm(lacking_4["detail"], "4")
    assert lacking_a["cause"] == "unmatched" and lacking_a["arm"] == "b" and names_arm(lacking_a["detail"], "a")
    assert not names_arm(lacking_4["detail"], "3") and not names_arm(lacking_a["detail"], "3")
    assert a.counts["by_cut"][CUT]["unmatched"] == 1 and a.counts["by_cut"][CUT]["reconciles"]
    assert a.counts["by_cut"][CUT]["keys"] == 4
    assert result_of(a).counts["eligible_sets"] == {"S1": 2}


def test_pr62_a_set_matched_in_all_k_arms_is_one_row_of_pairs_carrying_k_values(tmp_path: Path) -> None:
    rows = [KRow("c60-i000", CUT, ("0.95", "0.05", "0.60", "0.61", "0.59"))]
    a = P().assert_pairs(make_k_store(tmp_path, rows), declaration())
    assert len(a.pairs) == 1
    row = a.pairs.iloc[0]
    assert [row[c] for c in value_columns(5)] == [Decimal(v) for v in rows[0].values]
    assert all(isinstance(row[c], Decimal) for c in value_columns(5))


def test_pr62_at_k_two_pr10_reads_exactly_as_the_frozen_oracle_pinned_it(tmp_path: Path) -> None:
    rows = k_rows(3, lambda i: (1, 1), k=2)
    rows[1] = dataclasses.replace(rows[1], absent=frozenset({"b"}))
    a = P().assert_pairs(make_k_store(tmp_path, rows, k=2), declaration(k=2))
    only_a = a.excluded.iloc[0]
    assert (only_a["cause"], only_a["arm"]) == ("unmatched", "a")


# ---------- PR63: all k, or none (fixture 1, named mutant 9) ----------


def errored_rows() -> list[KRow]:
    """Twelve items; arm 4 errored on three of them, arm 3 on one more. The four broken sets
    disagree in their first two arms, so a build that analyses them at ``j = 2`` moves
    ``agree@2``; the eight whole sets agree at every prefix but one."""
    rows = k_rows(12, lambda i: (1, 1, 1, 1, 1) if i != 7 else (1, 0, 1, 1, 1))
    for i in (0, 1, 2):
        rows[i] = dataclasses.replace(
            rows[i], values=(HI, LO, HI, HI, HI), error={"4": "HTTP 502"},
        )
    rows[3] = dataclasses.replace(rows[3], values=(LO, HI, HI, HI, HI), error={"3": "timeout"})
    return rows


def test_pr63_a_set_with_one_errored_arm_is_excluded_whole_with_the_cause_and_the_arm_named(tmp_path: Path) -> None:
    a = P().assert_pairs(make_k_store(tmp_path, errored_rows()), declaration())
    assert len(a.pairs) == 12 and len(a.excluded) == 4
    by_item = {r["cluster"]: r for r in a.excluded.to_dict("records")}
    for item in ("c60-i000", "c60-i001", "c60-i002"):
        assert (by_item[item]["cause"], by_item[item]["arm"]) == ("errored", "4"), by_item[item]
    assert (by_item["c60-i003"]["cause"], by_item["c60-i003"]["arm"]) == ("errored", "3")
    block = a.counts["by_cut"][CUT]
    assert (block["keys"], block["matched"], block["eligible"], block["ineligible"]) == (12, 12, 12, 0)
    assert block["by_cause"]["errored"] == 0 and block["reconciles"]
    assert result_of(a).counts["excluded_by_arm"] == {**result_of(a).counts["excluded_by_arm"], "4": 3, "3": 1}


def test_pr63_a_partial_set_is_never_analysed_at_the_j_its_calls_reached(tmp_path: Path) -> None:
    """Named mutant 9: ``agree@2`` on the easy items and the errored ones under one name."""
    a = P().assert_pairs(make_k_store(tmp_path, errored_rows()), declaration())
    r = result_of(a)
    for j in (2, 3, 4, 5):
        assert r.agree["primary"][f"j{j}"]["estimate"] == pytest.approx(7 / 8), j
    assert r.counts["eligible_sets"] == {"S1": 8} and r.counts["items"] == 8
    assert r.counts["excluded_by_arm"] == {**r.counts["excluded_by_arm"], "4": 3, "3": 1}


@pytest.mark.parametrize(
    ("change", "cause", "arm"),
    [
        ({"error": {"5": "HTTP 500"}}, "errored", "5"),
        ({"n_spans": {"5": 0}}, "no_request_span", "5"),
        ({"n_spans": {"5": 2}}, "retry_or_multicall", "5"),
        ({"value_missing": frozenset({"5"})}, "value_missing", "5"),
        ({"values": (HI, HI, HI, HI, "1.5")}, "value_out_of_range", "5"),
        ({"model": {"5": "scorer-1.14.0"}}, "model_pin", "5"),
        ({"body_extra": {"5": '"top_p": 0.90'}}, "body_field_absent", "both"),
        ({"error": {"3": "HTTP 500"}}, "errored", "3"),
        ({"values": ("1.5", HI, HI, HI, HI)}, "value_out_of_range", "a"),
    ],
    ids=["errored_5", "no_span_5", "retry_5", "value_missing_5", "out_of_range_5", "model_pin_5",
         "body_field_5", "errored_3", "out_of_range_a"],
)
def test_pr63_every_pr19_cause_on_any_arm_excludes_the_whole_set(
    tmp_path: Path, change: Mapping[str, Any], cause: str, arm: str
) -> None:
    rows = k_rows(3, lambda i: (1, 1, 1, 1, 1))
    rows[1] = dataclasses.replace(rows[1], **change)
    a = P().assert_pairs(make_k_store(tmp_path, rows), declaration())
    past_the_pair = arm != "a"  # every case but out_of_range_a breaks an arm past the declared pair
    assert set(a.pairs["cluster"]) == ({"c60-i000", "c60-i001", "c60-i002"} if past_the_pair else {"c60-i000", "c60-i002"})
    assert result_of(a).counts["eligible_sets"] == {"S1": 2}
    (row,) = a.excluded.to_dict("records")
    assert (row["cluster"], row["cause"], row["arm"]) == ("c60-i001", cause, arm), row
    if arm == "both":
        assert names_arm(row["detail"], "5"), row["detail"]
    assert a.counts["by_cut"][CUT]["ineligible"] == (0 if past_the_pair else 1) and a.counts["by_cut"][CUT]["reconciles"]


def test_pr63_an_excluded_set_leaves_every_sweep_pair_it_was_in(tmp_path: Path) -> None:
    """An item eligible in two sweeps of three contributes one ``MS`` observation, not three."""
    rows = k_rows(4, lambda i: (1, 1, 1, 1, 1))
    broken = dataclasses.replace(rows[0], error={"b": "HTTP 500"})
    store = make_k_store(tmp_path, rows, sweeps=("S1", "S2", "S3"), per_sweep={"S3": [broken, *rows[1:]]})
    a = P().assert_pairs(store, declaration(sweeps=("S1", "S2", "S3")))
    r = result_of(a)
    assert r.counts["eligible_sets"] == {"S1": 4, "S2": 4, "S3": 3}
    assert r.counts["sweep_pairs"] == {"S1|S2": 4, "S1|S3": 3, "S2|S3": 3}
    assert r.majority["primary"]["j3"]["design_effect"]["m_bar"] == pytest.approx(10 / 4)


# ---------- PR64: arm order is the declaration's (named mutant 13) ----------


def test_pr64_the_prefix_at_j_is_the_declared_order_not_the_run_id_order_nor_the_store_order(tmp_path: Path) -> None:
    """Arms 3, 4, 5 are the runs ``S1-z``, ``S1-m``, ``S1-c`` in that declared order, written to
    the store as ``c``, ``m``, ``z``. Only the declared third arm disagrees, so ``agree@3`` is
    ``0`` under the declaration and ``1`` under either other order."""
    rows = [KRow(f"c60-i{i:03d}", CUT, (HI, HI, LO, HI, HI)) for i in range(6)]
    ids = {"S1": {"3": "S1-z", "4": "S1-m", "5": "S1-c"}}
    store = make_k_store(tmp_path, rows, run_ids=ids, creation_order=("a", "b", "5", "4", "3"))
    decl = declaration(more={"S1": ("S1-z", "S1-m", "S1-c")})
    a = P().assert_pairs(store, decl)
    assert [a.pairs.iloc[0][c] for c in value_columns(5)] == [Decimal(v) for v in (HI, HI, LO, HI, HI)]
    r = result_of(a)
    assert r.agree["primary"]["j2"]["estimate"] == 1.0
    assert r.agree["primary"]["j3"]["estimate"] == 0.0
    assert r.agree["primary"]["j5"]["estimate"] == 0.0
    assert r.majority["primary"]["j3"]["estimate"] is None  # one sweep: no sweep pair to compare


def test_pr64_the_prefix_is_never_a_per_set_subset_chosen_after_the_calls_are_seen() -> None:
    """Named mutant 13. Every set has some three arms that agree; the first three never do."""
    rows = [from_actions(f"i{i}", (1, 1, 0, 1, 1)) for i in range(4)]
    rows += [from_actions(f"j{i}", (0, 0, 1, 0, 0)) for i in range(4)]
    r = result_of(assertion(rows))
    assert r.agree["primary"]["j2"]["estimate"] == 1.0
    assert r.agree["primary"]["j3"]["estimate"] == 0.0
    assert r.agree["primary"]["j4"]["estimate"] == 0.0
    assert r.agree["primary"]["j5"]["estimate"] == 0.0


# ---------- PR65: agree@j, defined ----------


AGREE_PATTERN: dict[int, tuple[int, ...]] = {
    0: (1, 1, 1, 1, 1), 1: (1, 1, 1, 1, 0), 2: (1, 1, 1, 0, 0), 3: (1, 1, 0, 0, 0),
    4: (1, 0, 0, 0, 0), 5: (0, 0, 0, 0, 0), 6: (0, 0, 0, 0, 1), 7: (0, 0, 0, 1, 1),
    8: (0, 0, 1, 1, 1), 9: (0, 1, 1, 1, 1), 10: (1, 0, 1, 0, 1), 11: (1, 1, 1, 1, 1),
}


def agree_pattern(i: int, s: str) -> tuple[int, ...]:
    return AGREE_PATTERN[i % 12]


def test_pr65_agree_at_j_is_the_mean_over_eligible_sets_of_the_first_j_actions_all_equal() -> None:
    rows = grid(12, ["S1", "S2"], agree_pattern)
    r = result_of(assertion(rows))
    # by hand: j=2 agrees on all but items 4, 9 and 10 (9 of 12); j=3 on 0,1,2,5,6,7,11 (7);
    # j=4 on 0,1,5,6,11 (5); j=5 on 0,5,11 (3)
    assert r.agree["primary"]["j2"]["estimate"] == pytest.approx(9 / 12)
    assert r.agree["primary"]["j3"]["estimate"] == pytest.approx(7 / 12)
    assert r.agree["primary"]["j4"]["estimate"] == pytest.approx(5 / 12)
    assert r.agree["primary"]["j5"]["estimate"] == pytest.approx(3 / 12)
    assert sorted(prefixes(r.agree["primary"])) == [2, 3, 4, 5]
    for j in (2, 3, 4, 5):
        estimate, _, _ = reference_agree(rows, j)
        assert r.agree["primary"][f"j{j}"]["estimate"] == pytest.approx(estimate)


def test_pr65_the_interval_is_the_item_clustered_percentile_bootstrap_with_pr29s_seed() -> None:
    rows = grid(24, ["S1", "S2", "S3"], agree_pattern)
    r = result_of(assertion(rows, b=500, seed=7))
    for j in (2, 3, 4, 5):
        estimate, clusters, indicators = reference_agree(rows, j)
        assert_block_is(
            r.agree["primary"][f"j{j}"], estimate, clusters, indicators, seed=7, b=500,
            observation="within_sweep",
        )


def test_pr65_agree_is_over_every_sweep_and_the_cluster_is_the_item_not_the_set() -> None:
    """Twelve items in three sweeps: 36 sets, 12 clusters, ``m_bar = 3``."""
    rows = grid(12, ["S1", "S2", "S3"], agree_pattern)
    r = result_of(assertion(rows))
    assert r.counts["items"] == 12 and r.counts["sweeps"] == 3
    assert r.counts["eligible_sets"] == {"S1": 12, "S2": 12, "S3": 12}
    assert r.agree["primary"]["j3"]["design_effect"]["m_bar"] == 3.0


@settings(max_examples=60, deadline=None, derandomize=True)
@given(
    actions=st.lists(
        st.tuples(*([st.integers(0, 1)] * 5)), min_size=6, max_size=14,
    ),
    comparison=st.sampled_from(["ge", "gt"]),
)
def test_pr65_property_agree_at_every_j_follows_from_the_actions(
    actions: list[tuple[int, ...]], comparison: str
) -> None:
    rows = [from_actions(f"i{i:03d}", a) for i, a in enumerate(actions)]
    r = result_of(assertion(rows, comparison=comparison, b=50))
    for j in (2, 3, 4, 5):
        assert r.agree["primary"][f"j{j}"]["estimate"] == pytest.approx(
            float(np.mean([agree_j(a, j) for a in actions]))
        )


# ---------- PR66: agree@2 is PR26's flip indicator, row by row ----------


def test_pr66_agree_at_two_plus_the_pairs_flip_is_one_for_every_replicate_set_from_the_modules_own_outputs() -> None:
    """Row by row, not on the two means: each set alone through ``replicates`` and through
    ``analyse``, the module's ``agree_2`` against the module's own ``n10 + n01``."""
    rows = grid(12, ["S1"], agree_pattern)
    seen = set()
    for r in rows:
        alone = assertion([r], b=20)
        agree_2 = result_of(alone).agree["primary"]["j2"]["estimate"]
        sweep = {c.name: c for c in P().analyse(alone).cuts}[CUT].per_sweep[0]
        flip = sweep["n10"] + sweep["n01"]
        assert agree_2 + flip == 1, (r, agree_2, flip)
        seen.add(agree_2)
    assert seen == {0.0, 1.0}


def test_pr66_the_agree_at_two_interval_is_the_flip_rate_interval_reflected_on_the_same_draws() -> None:
    rows = grid(24, ["S1", "S2", "S3"], agree_pattern)  # six items disagree at j = 2: the bootstrap
    a = assertion(rows, b=500, seed=11)
    block = result_of(a).agree["primary"]["j2"]
    flip = {c.name: c for c in P().analyse(a).cuts}[CUT].pooled["flip_rate"]
    assert flip["basis"] == "cluster_bootstrap" == block["basis"]
    assert block["estimate"] == pytest.approx(1 - flip["estimate"], abs=1e-12)
    assert math.isclose(block["lo"], 1 - flip["hi"], abs_tol=1e-12)
    assert math.isclose(block["hi"], 1 - flip["lo"], abs_tol=1e-12)


def test_pr66_under_the_sensitivity_rule_agree_at_two_is_the_flip_of_the_other_declaration() -> None:
    rows = [RSet("i0", (TIE, HI, HI, TIE, LO)), RSet("i1", (TIE, TIE, LO, LO, LO)),
            RSet("i2", (LO, TIE, HI, HI, HI)), RSet("i3", (HI, HI, HI, HI, HI)),
            RSet("i4", (HI, TIE, LO, LO, LO))]
    r = result_of(assertion(rows, comparison="ge"))
    gt_cut = {c.name: c for c in P().analyse(assertion(rows, comparison="gt")).cuts}[CUT]
    assert r.agree["sensitivity"]["j2"]["estimate"] == pytest.approx(1 - gt_cut.pooled["flip_rate"]["estimate"])
    assert r.agree["primary"]["j2"]["estimate"] == pytest.approx(4 / 5)  # ge: only i2 flips
    assert r.agree["sensitivity"]["j2"]["estimate"] == pytest.approx(3 / 5)  # gt: i0 and i4 flip


# ---------- PR67: MS@j, defined ----------


MS_PATTERN: dict[tuple[int, str], tuple[int, ...]] = {
    # item 0: majority 1 in every sweep at every odd j
    (0, "S1"): (1, 1, 1, 1, 1), (0, "S2"): (1, 1, 1, 0, 0), (0, "S3"): (1, 0, 1, 0, 1),
    # item 1: maj@1 differs between S1 and the others; maj@3 and maj@5 agree everywhere
    (1, "S1"): (0, 1, 1, 1, 1), (1, "S2"): (1, 1, 1, 0, 0), (1, "S3"): (1, 1, 0, 1, 0),
    # item 2: maj@3 is 1 in every sweep; maj@5 differs in S3 only
    (2, "S1"): (1, 1, 1, 0, 0), (2, "S2"): (1, 1, 0, 1, 0), (2, "S3"): (1, 1, 0, 0, 0),
    # item 3: every majority 0 everywhere
    (3, "S1"): (0, 0, 0, 0, 0), (3, "S2"): (0, 0, 1, 0, 0), (3, "S3"): (0, 1, 0, 0, 1),
}


def ms_pattern(i: int, s: str) -> tuple[int, ...]:
    return MS_PATTERN[(i % 4, s)]


def test_pr67_ms_at_j_is_the_rate_at_which_two_sweeps_majorities_agree_over_unordered_sweep_pairs() -> None:
    rows = grid(4, ["S1", "S2", "S3"], ms_pattern)
    r = result_of(assertion(rows))
    # by hand, three sweep pairs per item, twelve observations:
    # j=1: item 0 all agree (3), item 1 S1 differs (1), item 2 all 1 (3), item 3 all 0 (3) -> 10/12
    # j=3: every item's three majorities agree -> 12/12
    # j=5: item 0 (3), item 1 (3), item 2 majorities (1, 1, 0): S3 differs (1), item 3 (3) -> 10/12
    assert r.majority["primary"]["j1"]["estimate"] == pytest.approx(10 / 12)
    assert r.majority["primary"]["j3"]["estimate"] == pytest.approx(12 / 12)
    assert r.majority["primary"]["j5"]["estimate"] == pytest.approx(10 / 12)
    for j in (1, 3, 5):
        estimate, _, _ = reference_ms(rows, j, ["S1", "S2", "S3"])
        assert r.majority["primary"][f"j{j}"]["estimate"] == pytest.approx(estimate)
    assert r.counts["sweep_pairs"] == {"S1|S2": 4, "S1|S3": 4, "S2|S3": 4}
    assert sorted(prefixes(r.majority["primary"])) == [1, 3, 5]


def test_pr67_the_interval_is_the_item_clustered_bootstrap_over_the_sweep_pair_observations() -> None:
    def pattern(i: int, s: str) -> tuple[int, ...]:
        base = MS_PATTERN[(i % 4, s)]
        return base if i < 12 else tuple(1 - x for x in base)

    rows = grid(24, ["S1", "S2", "S3"], pattern)
    r = result_of(assertion(rows, b=500, seed=13))
    for j in (1, 3, 5):
        estimate, clusters, indicators = reference_ms(rows, j, ["S1", "S2", "S3"])
        if len({c for c, v in zip(clusters, indicators, strict=True) if v == 0}) < 5:
            continue  # the fallback's case is PR72's
        assert_block_is(
            r.majority["primary"][f"j{j}"], estimate, clusters, indicators, seed=13, b=500,
            observation="across_sweeps",
        )


def test_pr67_with_two_sweeps_there_is_one_observation_per_item_and_with_one_sweep_none() -> None:
    rows = grid(8, ["S1", "S2"], ms_pattern)
    r = result_of(assertion(rows))
    assert r.counts["sweep_pairs"] == {"S1|S2": 8}
    assert r.majority["primary"]["j3"]["design_effect"]["m_bar"] == 1.0
    one = result_of(assertion(grid(8, ["S1"], ms_pattern)))
    assert one.counts["sweep_pairs"] == {}
    for j in (1, 3, 5):
        block = one.majority["primary"][f"j{j}"]
        assert block["estimate"] is None and block["lo"] is None and block["hi"] is None
        assert block["basis"] == "not_estimated"


# ---------- PR68: no majority on an even j (fixture 3, named mutant 10) ----------


def even_rows() -> list[RSet]:
    """``k = 4``, and every set splits two against two, so an even-``j`` majority would need a
    tie-break: a build that breaks it toward the action reads ``maj_4 = 1`` everywhere."""
    return [from_actions(f"i{i:03d}", (1, 0, 1, 0) if i % 2 else (0, 1, 0, 1), sweep=s)
            for i in range(8) for s in ("S1", "S2")]


def test_pr68_at_k_four_the_majority_curve_stops_at_three_and_the_artifact_says_so() -> None:
    r = result_of(assertion(even_rows()))
    assert r.k == 4
    for rule in RULES:
        assert sorted(prefixes(r.majority[rule])) == [1, 3]
        assert sorted(prefixes(r.agree[rule])) == [2, 3, 4]
    assert r.counts["majority_stops_at"] == 3
    five = result_of(assertion(grid(4, ["S1", "S2"], all_agree)))
    assert five.counts["majority_stops_at"] == 5 and sorted(prefixes(five.majority["primary"])) == [1, 3, 5]


def test_pr68_no_even_j_majority_appears_under_any_key_and_no_tie_is_broken() -> None:
    r = result_of(assertion(even_rows(), conditioning="near-cut items"))
    payload = loaded(r)
    for path, _ in walk(payload["majority"]):
        for key in path:
            m = PREFIX.fullmatch(key)
            if m:
                assert int(m.group(1)) % 2 == 1, path
    for path, _ in walk(payload["cost_framing"]):
        for key in path:
            m = PREFIX.fullmatch(key)
            if m:
                assert int(m.group(1)) % 2 == 1, path
    # maj_3 on (1, 0, 1) is 1 and on (0, 1, 0) is 0: the two families disagree across nothing,
    # since each item keeps its family in both sweeps, so MS@3 is 1 and no tie was broken.
    assert r.majority["primary"]["j3"]["estimate"] == 1.0
    assert r.majority["primary"]["j1"]["estimate"] == 1.0


# ---------- PR69: MS@1 is not the flip rate (named mutant 16) ----------


def test_pr69_ms_at_one_compares_two_sweeps_single_calls_and_the_flip_rate_two_arms_in_one_sweep() -> None:
    """Arm a is the same in both sweeps for every item, so ``MS@1 = 1``; arm b flips half the
    pairs inside each sweep, so ``agree@2 = 1/2`` and the flip rate is ``1/2``."""
    def pattern(i: int, s: str) -> tuple[int, ...]:
        return (1, 0, 1, 1, 1) if i % 2 else (1, 1, 1, 1, 1)

    rows = grid(10, ["S1", "S2"], pattern)
    r = result_of(assertion(rows))
    assert r.majority["primary"]["j1"]["estimate"] == 1.0
    assert r.agree["primary"]["j2"]["estimate"] == pytest.approx(0.5)
    flip = {c.name: c for c in P().analyse(assertion(rows)).cuts}[CUT].pooled["flip_rate"]["estimate"]
    assert flip == pytest.approx(0.5)
    assert r.majority["primary"]["j1"]["estimate"] != pytest.approx(1 - flip)


def test_pr69_the_keys_say_which_and_no_key_equates_or_subtracts_the_two() -> None:
    payload = loaded(result_of(assertion(grid(8, ["S1", "S2", "S3"], ms_pattern))))
    for rule in RULES:
        for j, block in prefixes(payload["majority"][rule]).items():
            assert block["observation"] == "across_sweeps", (rule, j)
        for j, block in prefixes(payload["agree"][rule]).items():
            assert block["observation"] == "within_sweep", (rule, j)
    for path, _ in walk(payload["majority"]):
        assert not any(word in key.lower() for key in path for word in ("flip", "within", "agree")), path
    for path, _ in walk(payload["agree"]):
        assert not any(word in key.lower() for key in path for word in ("ms", "majority", "across", "flip")), path
    for path, _ in walk(payload):
        assert not any(word in key.lower() for key in path for word in ("minus", "difference", "delta", "versus")), path


# ---------- PR70: both rules, always, never one ----------


TIED_PATTERN: dict[int, tuple[str, ...]] = {
    0: (TIE, TIE, TIE, TIE, TIE), 1: (HI, TIE, HI, TIE, HI), 2: (TIE, LO, LO, LO, LO),
    3: (HI, HI, HI, HI, HI), 4: (LO, LO, LO, LO, LO), 5: (HI, HI, TIE, TIE, TIE),
}


def tied_rows(sweeps: Sequence[str] = ("S1", "S2")) -> list[RSet]:
    return [RSet(f"i{i:03d}", TIED_PATTERN[i % 6], sweep=s) for i in range(12) for s in sweeps]


@pytest.mark.parametrize("declared", ["ge", "gt"])
def test_pr70_every_k_metric_is_under_primary_then_sensitivity_and_the_primary_is_the_declared_comparison(declared: str) -> None:
    r = result_of(assertion(tied_rows(), comparison=declared))
    assert list(r.agree) == list(RULES) and list(r.majority) == list(RULES)
    assert list(r.cost_framing) == list(RULES)
    assert r.counts["rules"] == {"primary": declared, "sensitivity": OTHER[declared]}
    ge = {j: reference_agree(tied_rows(), j, comparison="ge")[0] for j in (2, 3, 4, 5)}
    gt = {j: reference_agree(tied_rows(), j, comparison="gt")[0] for j in (2, 3, 4, 5)}
    assert ge != gt  # the fixture separates the two rules
    for j in (2, 3, 4, 5):
        assert r.agree["primary"][f"j{j}"]["estimate"] == pytest.approx((ge if declared == "ge" else gt)[j])
        assert r.agree["sensitivity"][f"j{j}"]["estimate"] == pytest.approx((gt if declared == "ge" else ge)[j])
    for j in (1, 3, 5):
        for rule, comparison in (("primary", declared), ("sensitivity", OTHER[declared])):
            estimate, _, _ = reference_ms(tied_rows(), j, ["S1", "S2"], comparison=comparison)
            assert r.majority[rule][f"j{j}"]["estimate"] == pytest.approx(estimate), (rule, j)


def test_pr70_ties_are_counted_per_arm_over_all_k_arms_and_carried_beside_both_rules() -> None:
    r = result_of(assertion(tied_rows()))
    # per sweep: arm a ties on items 0, 2 (x2 each) -> 4; b on 0, 1 -> 4; 3 on 0, 5 -> 4;
    # 4 on 0, 1, 5 -> 6; 5 on 0, 5 -> 4; two sweeps double it
    assert r.counts["ties"] == {"a": 8, "b": 8, "3": 8, "4": 12, "5": 8}
    payload = loaded(r)
    assert payload["counts"]["ties"] == r.counts["ties"]
    assert set(payload["agree"]) == set(payload["majority"]) == set(RULES)


def test_pr70_the_sensitivity_never_replaces_the_primary_where_the_two_agree() -> None:
    """With no tie anywhere the two rules give one number, and both are still emitted."""
    r = result_of(assertion(grid(8, ["S1", "S2"], agree_pattern)))
    for j in (2, 3, 4, 5):
        assert r.agree["primary"][f"j{j}"] == r.agree["sensitivity"][f"j{j}"]
    assert list(r.agree) == list(RULES)


# ---------- PR71: one bootstrap, one seed, no new default_rng site (named mutant 11) ----------


def test_pr71_no_default_rng_site_is_added_to_paired_py() -> None:
    """Green before and after: the one site is already there. The S25 guard pins the package;
    this pins the file, so a second stream in ``paired.py`` fails here by name."""
    source = Path(paired.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    sites: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) and inner.func.attr == "default_rng":
                    sites.append(node.name)
    assert sites == ["_cluster_bootstrap"], sites


def test_pr71_every_k_metric_interval_is_pr28s_estimator_and_never_the_observation_bootstrap() -> None:
    """Named mutant 11. Items agree or disagree all-or-nothing across three sweeps, so the
    observation bootstrap is narrower (asserted on the fixture) and the build matches the
    cluster one."""
    def pattern(i: int, s: str) -> tuple[int, ...]:
        return (1, 0, 1, 1, 1) if i < 6 else (1, 1, 1, 1, 1)

    rows = grid(20, ["S1", "S2", "S3"], pattern)
    r = result_of(assertion(rows, b=500, seed=5))
    estimate, clusters, indicators = reference_agree(rows, 2)
    lo, hi = cluster_bootstrap(clusters, indicators, seed=5, b=500)
    nlo, nhi = observation_bootstrap(indicators, seed=5, b=500)
    assert nhi - nlo < hi - lo, (nlo, nhi, lo, hi)
    block = r.agree["primary"]["j2"]
    assert math.isclose(block["lo"], lo, abs_tol=1e-12) and math.isclose(block["hi"], hi, abs_tol=1e-12)
    assert not (math.isclose(block["lo"], nlo, abs_tol=1e-12) and math.isclose(block["hi"], nhi, abs_tol=1e-12))
    for j in (3, 4, 5):
        estimate, clusters, indicators = reference_agree(rows, j)
        assert_block_is(r.agree["primary"][f"j{j}"], estimate, clusters, indicators, seed=5, b=500, observation="within_sweep")


def test_pr71_the_same_declaration_over_the_same_rows_is_byte_identical(tmp_path: Path) -> None:
    """In process twice, shuffled, reversed, and in two child processes under two hash seeds."""
    rows = grid(12, ["S1", "S2", "S3"], agree_pattern)
    a = assertion(rows, b=300, seed=3, conditioning="near-cut items")
    first = result_of(a).to_json()
    assert result_of(a).to_json() == first
    shuffled = list(rows)
    random.Random(5).shuffle(shuffled)
    assert result_of(assertion(shuffled, decl=a.declaration)).to_json() == first
    assert result_of(assertion(list(reversed(rows)), decl=a.declaration)).to_json() == first
    pickled = tmp_path / "assertion.pkl"
    pickled.write_bytes(pickle.dumps(a))
    child = (
        "import pickle, sys; from poisson_prove.paired import replicates; "
        f"a = pickle.load(open({str(pickled)!r}, 'rb')); "
        "sys.stdout.write(replicates(a)[0].to_json())"
    )
    outputs = []
    for hash_seed in ("0", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        done = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True, env=env, check=False)
        assert done.returncode == 0, done.stderr
        outputs.append(done.stdout)
    assert outputs[0] == outputs[1] == first


def test_pr71_the_seed_alone_moves_a_k_metric_interval() -> None:
    """Items disagree in none, one, two or all three sweeps, so the resample means sit on a
    fine grid and two seeds land on two intervals; the other declared fields move nothing."""
    def pattern(i: int, s: str) -> tuple[int, ...]:
        return (1, 0, 1, 0, 1) if int(s[1]) <= i % 4 else (1, 1, 1, 1, 1)

    rows = grid(24, ["S1", "S2", "S3"], pattern)
    base = result_of(assertion(rows, b=300, seed=3))
    other = result_of(assertion(rows, b=300, seed=4))
    same = result_of(assertion(rows, b=300, seed=3, conditioning="x", floor="0.01", declared_window_s=9.0, token_cap=5))
    for j in (2, 3, 4, 5):
        assert base.agree["primary"][f"j{j}"]["basis"] == "cluster_bootstrap"
        assert (base.agree["primary"][f"j{j}"]["lo"], base.agree["primary"][f"j{j}"]["hi"]) != (
            other.agree["primary"][f"j{j}"]["lo"], other.agree["primary"][f"j{j}"]["hi"]
        ), j
        assert base.agree["primary"][f"j{j}"] == same.agree["primary"][f"j{j}"]
    assert base.majority == same.majority  # the conditioning moves the cost framing, and only it


def test_pr71_a_fresh_generator_per_quantity_per_prefix_per_cut_and_per_rule() -> None:
    """Every interval in a cut is drawn from ``default_rng(bootstrap_seed)`` afresh, so each
    equals the reference on its own, and a cut's block is the same alone or beside two others."""
    def c50(i: int, s: str) -> tuple[int, ...]:
        return (1, 0, 0, 0, 0) if i < 7 else (0, 0, 0, 0, 0)

    def c90(i: int, s: str) -> tuple[int, ...]:
        return (0, 1, 1, 1, 1) if i < 6 else (1, 1, 1, 1, 1)

    c60 = grid(12, ["S1", "S2", "S3"], agree_pattern)
    alone = result_of(assertion(c60, b=200)).to_json()
    others = grid(12, ["S1", "S2", "S3"], c50, cut="c50") + grid(12, ["S1", "S2", "S3"], c90, cut="c90")
    results = replicates(assertion(others + c60, b=200))
    assert [r.name for r in results] == ["c50", "c90", CUT]
    assert {r.name: r for r in results}[CUT].to_json() == alone


# ---------- PR72: the fallback, mirrored (fixture 2, named mutant 12) ----------


def test_pr72_zero_disagreeing_items_is_the_exact_lower_bound_and_never_a_certainty() -> None:
    """Named mutant 12: ``[1, 1]`` where no item disagreed. Twenty items, three sweeps, three
    cuts, every set agreeing at every prefix under both rules."""
    rows = grid(20, ["S1", "S2", "S3"], all_agree)
    rows += grid(20, ["S1", "S2", "S3"], lambda i, s: (0,) * 5, cut="c50")
    rows += grid(20, ["S1", "S2", "S3"], all_agree, cut="c90")
    for r in replicates(assertion(rows)):
        for rule in RULES:
            blocks = list(prefixes(r.agree[rule]).values()) + list(prefixes(r.majority[rule]).values())
            assert len(blocks) == 7
            for block in blocks:
                assert block["estimate"] == 1.0
                assert block["basis"] == "exact_lower_one_sided", (r.name, rule, block)
                assert block["hi"] == 1.0 and block["upper_bound_by_observation"] is True
                assert block["lo"] == pytest.approx(0.05 ** (1 / 20), abs=1e-12)
                assert block["lo"] == pytest.approx(cp_lower_one_sided(0, 20), abs=1e-12)
                assert 0 < block["lo"] < 1


@pytest.mark.parametrize("k_dis", [1, 2, 3, 4])
def test_pr72_fewer_than_five_disagreeing_items_fall_back_too(k_dis: int) -> None:
    def pattern(i: int, s: str) -> tuple[int, ...]:
        return (1, 1, 1, 1, 0) if i < k_dis else (1, 1, 1, 1, 1)

    r = result_of(assertion(grid(40, ["S1", "S2"], pattern)))
    block = r.agree["primary"]["j5"]
    assert block["basis"] == "exact_lower_one_sided" and block["hi"] == 1.0
    assert block["lo"] == pytest.approx(cp_lower_one_sided(k_dis, 40), abs=1e-12)
    assert block["estimate"] == pytest.approx(1 - k_dis / 40)
    assert block["upper_bound_by_observation"] is True
    assert r.agree["primary"]["j4"]["basis"] == "exact_lower_one_sided"  # zero disagree at j = 4


def test_pr72_five_disagreeing_items_is_the_bootstrap_again() -> None:
    def pattern(i: int, s: str) -> tuple[int, ...]:
        return (1, 1, 1, 1, 0) if i < 5 else (1, 1, 1, 1, 1)

    rows = grid(40, ["S1", "S2"], pattern)
    r = result_of(assertion(rows, b=300, seed=9))
    estimate, clusters, indicators = reference_agree(rows, 5)
    assert_block_is(r.agree["primary"]["j5"], estimate, clusters, indicators, seed=9, b=300, observation="within_sweep")
    assert "upper_bound_by_observation" not in r.agree["primary"]["j5"]


def test_pr72_the_fallback_counts_disagreeing_items_not_disagreeing_sets() -> None:
    """Two items disagreeing in all three sweeps are six sets and two clusters: the fallback."""
    def pattern(i: int, s: str) -> tuple[int, ...]:
        return (1, 0, 1, 1, 1) if i < 2 else (1, 1, 1, 1, 1)

    r = result_of(assertion(grid(30, ["S1", "S2", "S3"], pattern)))
    block = r.agree["primary"]["j2"]
    assert block["basis"] == "exact_lower_one_sided"
    assert block["lo"] == pytest.approx(cp_lower_one_sided(2, 30), abs=1e-12)
    assert block["estimate"] == pytest.approx(1 - 6 / 90)


def test_pr72_the_trigger_is_per_metric_per_prefix_and_per_rule() -> None:
    """The first two arms always agree; arm 5 disagrees on eight items; a tie in arm 3 on twelve
    items separates the rules at ``j = 3``."""
    def pattern(i: int, s: str) -> tuple[str, ...]:
        third = TIE if i < 12 else HI
        fifth = LO if i < 8 else HI
        return (HI, HI, third, HI, fifth)

    rows = [RSet(f"i{i:03d}", pattern(i, s), sweep=s) for i in range(30) for s in ("S1", "S2")]
    r = result_of(assertion(rows, b=200))
    assert r.agree["primary"]["j2"]["basis"] == "exact_lower_one_sided"
    assert r.agree["primary"]["j3"]["basis"] == "exact_lower_one_sided"  # a tie acts under ge
    assert r.agree["sensitivity"]["j3"]["basis"] == "cluster_bootstrap"  # and not under gt
    assert r.agree["primary"]["j5"]["basis"] == "cluster_bootstrap"
    assert r.majority["primary"]["j5"]["basis"] == "exact_lower_one_sided"  # majorities agree
    assert r.majority["sensitivity"]["j5"]["basis"] == "exact_lower_one_sided"


def test_pr72_ms_falls_back_on_items_whose_majorities_disagree() -> None:
    def pattern(i: int, s: str) -> tuple[int, ...]:
        if i < 3 and s == "S2":
            return (0, 0, 0, 1, 1)
        return (1, 1, 1, 0, 0)

    r = result_of(assertion(grid(25, ["S1", "S2", "S3"], pattern)))
    block = r.majority["primary"]["j3"]
    assert block["basis"] == "exact_lower_one_sided" and block["hi"] == 1.0
    assert block["lo"] == pytest.approx(cp_lower_one_sided(3, 25), abs=1e-12)
    assert block["estimate"] == pytest.approx(1 - 6 / 75)  # three items, two disagreeing pairs each


# ---------- PR73: the design effect on that metric's footing ----------


def test_pr73_m_bar_is_observations_per_item_for_that_metric_and_never_the_number_of_calls() -> None:
    rows3 = grid(12, ["S1", "S2", "S3"], agree_pattern)
    r3 = result_of(assertion(rows3))
    for j in (2, 3, 4, 5):
        assert r3.agree["primary"][f"j{j}"]["design_effect"]["m_bar"] == 3.0
    for j in (1, 3, 5):
        assert r3.majority["primary"][f"j{j}"]["design_effect"]["m_bar"] == 3.0  # C(3, 2)
    r2 = result_of(assertion(grid(12, ["S1", "S2"], agree_pattern)))
    assert r2.agree["primary"]["j5"]["design_effect"]["m_bar"] == 2.0
    assert r2.majority["primary"]["j5"]["design_effect"]["m_bar"] == 1.0
    assert r2.majority["primary"]["j5"]["design_effect"]["deff"] == 1.0
    for r in (r3, r2):
        for path, value in walk(loaded(r)["agree"]):
            if path and path[-1] == "m_bar":
                assert value != 5.0, path


def test_pr73_the_icc_is_one_way_anova_on_the_items_indicators_for_that_metric() -> None:
    """An intermediate correlation: the first four items disagree in two sweeps of three, the
    next four in one, the rest in none."""
    def pattern(i: int, s: str) -> tuple[int, ...]:
        if i < 4 and s != "S3":
            return (1, 1, 0, 1, 1)
        if 4 <= i < 8 and s == "S1":
            return (1, 1, 0, 1, 1)
        return (1, 1, 1, 1, 1)

    rows = grid(16, ["S1", "S2", "S3"], pattern)
    r = result_of(assertion(rows, b=200, seed=17))
    estimate, clusters, indicators = reference_agree(rows, 3)
    icc, m_bar, deff = icc1(clusters, indicators)
    assert 0 < icc < 1
    assert_block_is(r.agree["primary"]["j3"], estimate, clusters, indicators, seed=17, b=200, observation="within_sweep")
    assert r.agree["primary"]["j3"]["design_effect"] == pytest.approx({"icc": icc, "m_bar": m_bar, "deff": deff})
    assert deff == pytest.approx(1 + 2 * icc)
    estimate, clusters, indicators = reference_ms(rows, 3, ["S1", "S2", "S3"])
    icc, m_bar, deff = icc1(clusters, indicators)
    assert r.majority["primary"]["j3"]["design_effect"] == pytest.approx({"icc": icc, "m_bar": m_bar, "deff": deff})


def test_pr73_an_unbalanced_cut_keeps_m0_in_the_denominator_and_n_over_g_in_deff() -> None:
    rows = grid(10, ["S1", "S2", "S3"], agree_pattern)
    rows = [r for r in rows if not (r.cluster in {"i000", "i001", "i002"} and r.sweep == "S3")]
    excluded = [excluded_row(f"i{i:03d}", "errored", "3", sweep="S3") for i in range(3)]
    r = result_of(assertion(rows, excluded=excluded, b=100))
    estimate, clusters, indicators = reference_agree(rows, 3)
    icc, m_bar, deff = icc1(clusters, indicators)
    assert m_bar == pytest.approx(27 / 10)
    assert r.agree["primary"]["j3"]["design_effect"] == pytest.approx({"icc": icc, "m_bar": m_bar, "deff": deff})


# ---------- PR74: no cross-cut and no cross-rule k-statistic ----------


def test_pr74_every_k_statistic_is_nested_under_one_cut_and_one_rule_and_no_key_crosses_either() -> None:
    def c50(i: int, s: str) -> tuple[int, ...]:
        return (1, 0, 0, 0, 0) if i < 7 else (0, 0, 0, 0, 0)

    rows = grid(12, ["S1", "S2"], agree_pattern) + grid(12, ["S1", "S2"], c50, cut="c50")
    rows += [RSet(r.cluster, r.values, sweep=r.sweep, cut="c90") for r in tied_rows(("S1", "S2"))]
    results = replicates(assertion(rows, b=50, conditioning="near-cut items"))
    assert [r.name for r in results] == [CUT, "c50", "c90"]
    assert tuple(f.name for f in dataclasses.fields(P().ReplicateResult)) == REPLICATE_RESULT_FIELDS
    for r in results:
        payload = loaded(r)
        assert list(payload) == list(JSON_KEYS), list(payload)
        assert payload["threshold"] == {CUT: "0.60", "c50": "0.50", "c90": "0.90"}[r.name]
        assert payload["comparison"] == "ge" and payload["k"] == 5
        assert set(payload["counts"]) == COUNT_KEYS, set(payload["counts"])
        for section in ("agree", "majority", "cost_framing"):
            assert list(payload[section]) == list(RULES), section
        for path, _ in walk(payload):
            assert not any(
                word in key.lower() for key in path
                for word in ("across_cut", "between", "trend", "primary_minus", "sensitivity_minus", "vs_")
            ), path
            assert not any(other in key for key in path for other in ("c50", "c90", CUT)), path


def test_pr74_a_cuts_result_does_not_depend_on_any_other_cut_or_on_the_other_rule() -> None:
    c60 = tied_rows(("S1", "S2", "S3"))
    c50 = grid(12, ["S1", "S2", "S3"], lambda i, s: (1, 0, 1, 0, 1) if i < 6 else (0,) * 5, cut="c50")
    alone = result_of(assertion(c60, b=200))
    beside = result_of(assertion(c50 + c60, b=200))
    assert alone.to_json() == beside.to_json()
    assert dataclasses.asdict(alone) == dataclasses.asdict(beside)
    # the primary under ``gt`` is the sensitivity under ``ge``, number for number
    ge = result_of(assertion(c60, b=200, comparison="ge"))
    gt = result_of(assertion(c60, b=200, comparison="gt"))
    assert ge.agree["sensitivity"] == gt.agree["primary"] and ge.agree["primary"] == gt.agree["sensitivity"]
    assert ge.majority["sensitivity"] == gt.majority["primary"]


def test_pr74_replicates_returns_one_result_per_cut_and_no_public_function_returns_a_figure_spanning_two() -> None:
    module = P()
    hints = typing.get_type_hints(module.replicates)
    assert list(hints) == ["assertion", "cost", "windows", "return"], hints
    assert hints["assertion"] is module.PairAssertion
    assert hints["return"] == tuple[module.ReplicateResult, ...]
    assert hints["cost"] == (module.CostReport | None)
    assert hints["windows"] == (module.WindowReport | None)
    params = list(typing.get_type_hints(module.replicates))
    assert params[:1] == ["assertion"]
    import inspect
    signature = inspect.signature(module.replicates)
    assert [p.kind for p in signature.parameters.values()] == [
        inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.KEYWORD_ONLY,
    ]
    assert signature.parameters["cost"].default is None and signature.parameters["windows"].default is None
    assert typing.get_type_hints(module.ReplicateResult.to_json)["return"] is str
    assert dataclasses.is_dataclass(module.ReplicateResult) and module.ReplicateResult.__dataclass_params__.frozen
    public = {
        name for name, value in vars(module).items()
        if not name.startswith("_") and getattr(value, "__module__", None) == module.__name__
    }
    assert {"ReplicateResult", "replicates"} <= public


# ---------- PR75: a prefix comparison is paired on the same draws ----------


def step_pattern(i: int, s: str) -> tuple[int, ...]:
    """Six items disagree at ``j = 2`` in every sweep, so that prefix is over the fallback; the
    other eighteen lose agreement at ``j = 3`` in one, two or three sweeps, so the step's
    per-item sums vary and its resample means sit on a fine grid -- two seeds give two
    intervals, which is what lets the test see which draws the step was taken on."""
    if i % 4 == 0:
        return (1, 0, 1, 1, 1)
    return (1, 1, 0, 1, 1) if int(s[1]) <= i % 4 else (1, 1, 1, 1, 1)


def test_pr75_a_step_between_two_prefixes_is_the_paired_bootstrap_on_the_same_resample_indices() -> None:
    rows = grid(24, ["S1", "S2", "S3"], step_pattern)
    r = result_of(assertion(rows, b=500, seed=21))
    steps = r.agree["primary"]["steps"]
    assert list(steps) == ["j2_to_j3", "j3_to_j4", "j4_to_j5"]
    m = STEP.fullmatch("j2_to_j3")
    assert m and (int(m.group(1)), int(m.group(2))) == (2, 3)
    block = steps["j2_to_j3"]
    _, clusters, low = reference_agree(rows, 2)
    _, _, high = reference_agree(rows, 3)
    d = [h - lo_ for h, lo_ in zip(high, low, strict=True)]
    lo, hi = cluster_bootstrap(clusters, d, seed=21, b=500)
    other = cluster_bootstrap(clusters, d, seed=22, b=500)
    assert other != (lo, hi)  # the fixture separates the seeds
    assert block["basis"] == "cluster_bootstrap"
    assert block["estimate"] == pytest.approx(float(np.mean(d)), abs=1e-12)
    assert math.isclose(block["lo"], lo, abs_tol=1e-12) and math.isclose(block["hi"], hi, abs_tol=1e-12)
    assert not (math.isclose(block["lo"], other[0], abs_tol=1e-12) and math.isclose(block["hi"], other[1], abs_tol=1e-12))
    # and it is not two intervals compared by overlap
    a, b = r.agree["primary"]["j2"], r.agree["primary"]["j3"]
    naive = (b["lo"] - a["hi"], b["hi"] - a["lo"])
    assert not (math.isclose(block["lo"], naive[0], abs_tol=1e-9) and math.isclose(block["hi"], naive[1], abs_tol=1e-9))
    assert naive[1] - naive[0] > block["hi"] - block["lo"]
    # the two later steps have no disagreement to move, and read as exactly zero
    for key in ("j3_to_j4", "j4_to_j5"):
        assert steps[key]["estimate"] == 0.0 and steps[key]["basis"] == "cluster_bootstrap"


def test_pr75_a_step_whose_endpoint_is_under_the_fallback_is_not_estimated() -> None:
    def pattern(i: int, s: str) -> tuple[int, ...]:
        return (1, 1, 1, 1, 0) if i < 6 else (1, 1, 1, 1, 1)

    r = result_of(assertion(grid(30, ["S1", "S2"], pattern)))
    steps = r.agree["primary"]["steps"]
    assert steps["j2_to_j3"] == {"estimate": 0.0, "lo": None, "hi": None, "basis": "not_estimated"}
    assert steps["j4_to_j5"]["basis"] == "not_estimated"  # j = 4 is under the fallback
    assert steps["j4_to_j5"]["lo"] is None and steps["j4_to_j5"]["hi"] is None
    assert steps["j4_to_j5"]["estimate"] == pytest.approx(-12 / 60)  # six items in two sweeps
    assert r.agree["primary"]["j5"]["basis"] == "cluster_bootstrap"


# ---------- PR76: the cost framing, pre-declared and emitted whole (named mutant 14) ----------


def test_pr76_the_per_ten_thousand_figure_carries_both_bounds_from_the_same_interval_and_the_conditioning() -> None:
    def pattern(i: int, s: str) -> tuple[int, ...]:
        base = MS_PATTERN[(i % 4, s)]
        return base if i < 12 else tuple(1 - x for x in base)

    rows = grid(24, ["S1", "S2", "S3"], pattern)
    r = result_of(assertion(rows, b=300, seed=23, conditioning="near-cut items only"))
    for rule in RULES:
        assert list(r.cost_framing[rule]) == ["j1", "j3", "j5"]
        for j in (1, 3, 5):
            ms = r.majority[rule][f"j{j}"]
            block = r.cost_framing[rule][f"j{j}"]["per_10000"]
            assert block == {
                "n": round(10000 * (1 - ms["estimate"])),
                "n_lo": round(10000 * (1 - ms["hi"])),
                "n_hi": round(10000 * (1 - ms["lo"])),
                "conditioning": "near-cut items only",
            }, (rule, j)
            assert block["n_lo"] <= block["n"] <= block["n_hi"]
    assert r.cost_framing["primary"]["j1"]["per_10000"]["n"] > 0


def test_pr76_under_the_fallback_the_lower_count_is_zero_and_the_upper_comes_from_the_exact_bound() -> None:
    r = result_of(assertion(grid(20, ["S1", "S2"], all_agree), conditioning="c"))
    block = r.cost_framing["primary"]["j5"]["per_10000"]
    assert block["n"] == 0 and block["n_lo"] == 0
    assert block["n_hi"] == round(10000 * (1 - cp_lower_one_sided(0, 20)))


def test_pr76_without_a_declared_conditioning_no_per_ten_thousand_figure_is_emitted() -> None:
    """Named mutant 14, half of it: a near-cut rate read as a production rate."""
    r = result_of(assertion(grid(8, ["S1", "S2"], ms_pattern)))
    for rule in RULES:
        for j in (1, 3, 5):
            block = r.cost_framing[rule][f"j{j}"]
            assert "per_10000" not in block, block
            for path, _ in walk(block):
                assert not any("10000" in key or "10_000" in key for key in path), path
    assert result_of(assertion(grid(8, ["S1", "S2"], ms_pattern), conditioning="c")).cost_framing["primary"]["j1"]["per_10000"]["n"] >= 0


def test_pr76_n_is_never_emitted_without_both_bounds() -> None:
    """Named mutant 14, the other half: the point estimate alone."""
    payload = loaded(result_of(assertion(grid(8, ["S1", "S2"], ms_pattern), conditioning="c")))
    seen = 0
    for path, value in walk(payload["cost_framing"]):
        if isinstance(value, Mapping) and "n" in value:
            assert {"n", "n_lo", "n_hi", "conditioning"} <= set(value), path
            seen += 1
    assert seen == 6


def test_pr76_without_a_price_or_a_cost_report_the_dollar_row_is_absent_not_zero_and_so_is_latency_without_windows() -> None:
    paired = P()
    a = assertion(grid(8, ["S1", "S2"], ms_pattern), conditioning="c")
    without = result_of(a)
    for rule in RULES:
        for j in (1, 3, 5):
            block = without.cost_framing[rule][f"j{j}"]
            assert "dollars_per_decision" not in block and "latency_per_decision" not in block
            for path, value in walk(block):
                assert not any("dollar" in key or "latency" in key for key in path), path
                assert value != 0 or path[-1:] == ("n_lo",) or path[-1:] == ("n",), path
    unpriced = paired.CostReport(
        phases=(), input_tokens=0, output_tokens=0, recorded_spans=0, unrecorded_spans=0,
        price_per_input_token=None, dollars=None, token_cap=None, cap_reached=False,
    )
    with_cost = result_of(a, cost=unpriced)
    for rule in RULES:
        for j in (1, 3, 5):
            assert "dollars_per_decision" not in with_cost.cost_framing[rule][f"j{j}"]


def test_pr76_the_dollar_row_is_j_times_the_mean_recorded_input_tokens_times_the_price() -> None:
    """Ruled 2026-09-22: the mean is ``input_tokens / recorded_spans`` off the cost report,
    never a tokeniser and never a rate card; the price is echoed as its literal."""
    paired = P()
    priced = paired.CostReport(
        phases=(), input_tokens=1_723_267, output_tokens=90_000, recorded_spans=4_500,
        unrecorded_spans=3, price_per_input_token=Decimal("0.000000042"), dollars=None,
        token_cap=None, cap_reached=False,
    )
    r = result_of(assertion(grid(8, ["S1", "S2"], ms_pattern), conditioning="c"), cost=priced)
    mean = 1_723_267 / 4_500
    for rule in RULES:
        for j in (1, 3, 5):
            row = r.cost_framing[rule][f"j{j}"]["dollars_per_decision"]
            assert row["mean_input_tokens"] == pytest.approx(mean, abs=1e-9)
            assert row["price_per_input_token"] == "0.000000042"
            assert row["estimate"] == pytest.approx(j * mean * 0.000000042, rel=1e-12), (rule, j)
    assert r.cost_framing["primary"]["j3"]["dollars_per_decision"]["estimate"] == pytest.approx(
        3 * r.cost_framing["primary"]["j1"]["dollars_per_decision"]["estimate"], rel=1e-12
    )


def test_pr76_the_latency_row_is_j_times_the_recorded_per_call_median_serial_and_at_the_declared_concurrency() -> None:
    """Ruled 2026-09-22: the median is the median of the per-sweep medians ``windows`` carries;
    the concurrency is the arms' recorded one, and with none recorded that row is absent."""
    paired = P()
    windows = paired.WindowReport(
        per_sweep=(
            {"sweep": "S1", "latency_s": {"median": 0.30, "n": 40}},
            {"sweep": "S2", "latency_s": {"median": 0.40, "n": 40}},
            {"sweep": "S3", "latency_s": {"median": 0.338, "n": 40}},
        ),
        replay_gap={CUT: {"min": 1.0, "median": 2.0, "max": 3.0}},
    )
    rows = grid(8, ["S1", "S2", "S3"], ms_pattern)
    a = assertion(rows, conditioning="c")
    r = result_of(a, windows=windows)
    for rule in RULES:
        for j in (1, 3, 5):
            row = r.cost_framing[rule][f"j{j}"]["latency_per_decision"]
            assert row["median_call_s"] == pytest.approx(0.338)
            assert row["serial_s"] == pytest.approx(j * 0.338)
            assert "at_declared_concurrency_s" not in row  # no arm records a concurrency
    recorded = dataclasses.replace(a, environment={
        "sweeps": {s: {label: {"concurrency": 4} for label in labels(5)} for s in ("S1", "S2", "S3")},
        "gaps": [],
    })
    row = result_of(recorded, windows=windows).cost_framing["primary"]["j5"]["latency_per_decision"]
    assert row["at_declared_concurrency_s"] == pytest.approx(5 * 0.338 / 4)
    without = result_of(recorded)
    assert "latency_per_decision" not in without.cost_framing["primary"]["j5"]


def test_pr76_the_cost_framing_is_per_cut_per_rule_and_per_odd_j_in_the_artifact() -> None:
    results = replicates(assertion(
        grid(8, ["S1", "S2"], ms_pattern) + grid(8, ["S1", "S2"], ms_pattern, cut="c50"),
        conditioning="c",
    ))
    for r in results:
        payload = loaded(r)["cost_framing"]
        assert list(payload) == list(RULES)
        for rule in RULES:
            assert list(payload[rule]) == ["j1", "j3", "j5"]
            for j in ("j1", "j3", "j5"):
                assert payload[rule][j]["per_10000"]["conditioning"] == "c"
