"""Frozen tests for the M6 multi-event amendment: per-event CIF diff over one BH family.

A1 is the gate. It asserts the single-event ``diff`` against a reference record of the
lattice pair (``tests/lattice.py``), built in this file in the frozen record's shape from
sources Prove never touches: the design's counts, scipy's Fisher test with BH written out
(``lattice.fisher``, equal to Prove's p and q bit for bit), and the pre-amendment detection
limits at 32 against 32 (``MDE_AT_32``, as the frozen single-event record held them). It is
never checked against Prove recomputing itself. If A1 fails the amendment is wrong, not the
golden.

Fixture tests (A1, A2, A5, A6, A8, A10, A14, A19) run on the generated lattice pair
through ``lattice_store``: raw frames go to ``multi_diff``, censored frames to ``diff``.
Everything else uses small raw frames built directly with M4's thirteen columns, as the
M5 frozen tests do; synthetic rows sit at the horizon unless a test needs otherwise, so the
CIF at horizon equals the terminal rate and verdict direction follows the counts.

Two invariants are deliberately absent, left out at the freeze rather than adapted:

- A4 names "the ordering helper" (delta desc, q asc, mde asc, config_hash) but the public API
  declares no such symbol, and no extra public symbol may be added. M7's
  private ``_worst`` sorts by (delta desc, config_hash) and is covered by M7 I19.
- A7 asks for early censoring from errored rows, but M4's ``EpisodeRecord`` requires
  ``t`` and ``horizon`` to be None on errored rows, so they carry no censoring time, and
  A20 excludes them from every denominator. As written the CIF cannot differ from the
  rate on such a frame.

Notes for the implementation:

- The A11 fixture builder searches for the smallest swing that leaves cell X significant
  in both directions after BH over the whole family, and a cell Y whose opposite move is
  the largest non-significant one. It uses ``bh`` and ``scipy.stats.fisher_exact``, the
  same two calls the implementation makes, so it survives a change of ``q``.
- A17's "before any event is tested" is probed with a cell whose arms carry duplicate
  ``replicate_index`` values, which the per-cell McNemar rejects with its own
  ``NotPairable``; the salt mismatch must win, so the message must not be that one.
- ``to_json`` per-event counts (A14) are located by walking the returned tree for a dict
  carrying ``n_safer`` / ``n_worse`` / ``n_unchanged`` that is either keyed by the event
  name or carries ``event == name``; the exact layout is the implementer's.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.stats import fisher_exact

from poisson_prove.diff import (
    DiffError,
    DiffResult,
    EventDiff,
    EventInferenceError,
    MultiDiffResult,
    NotPairable,
    UnitMismatch,
    bh,
    diff,
    holm,
    infer_events,
    multi_diff,
)
from poisson_prove.store import RunManifest, Store, config_hash
from poisson_prove.survival import censor
from test_pf4_stats import _assert_limit, _ref_fisher_limits

import lattice

ROOT = Path(__file__).resolve().parents[1]

RUNS = [lattice.RUN_A, lattice.RUN_B]
EVENT = lattice.EVENT
METHODS = ["fisher_bh", "mcnemar_bh", "logrank_bh"]
Q = 0.05
POWER = 0.8
CELLS = 72
#: The reference's flagged conditions under fisher_bh (``lattice.directions(lattice.fisher())``).
REFERENCE_SAFER, REFERENCE_WORSE = 22, 0
HORIZON = 5.0
N = 32
TOL_EXACT = 1e-12
BANNED_CAUSAL = ("caused", "because", "due to")
TIME_GRID = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
OUTCOMES = ["timeout", "violated", "completed"]

CELLS_COLUMNS = [
    "config_hash",
    "config",
    "n_a",
    "n_b",
    "events_a",
    "events_b",
    "rate_a",
    "rate_b",
    "delta",
    "stat",
    "p",
    "q",
    "verdict",
    "mde",
    # PF4 (PF4.13, PF4.14, PF4.15): every cell now carries its direction from the test, the
    # log-rank timing note, the matched-pair count and the note on a missing detection limit.
    "direction",
    "direction_note",
    "pairs",
    "n01",
    "n10",
    "mde_note",
    # PF4 re-freeze (PF4.34 to PF4.47): every cell row gains Holm's adjusted p and decision, the
    # limit keys both ways, the competing shift and the interval on the change; the order is the
    # reference build's.
    "q_holm",
    "holm",
    "mde_rise",
    "mde_fall",
    "mde_rise_note",
    "mde_fall_note",
    "mde_test",
    "mde_basis",
    "mde_level",
    "mde_family",
    "mde_power",
    "mde_anchor",
    "mde_hr",
    "p_min",
    "flaggable",
    "mde_moves_with",
    "mde_rise_verdict",
    "mde_fall_verdict",
    "competing_shift",
    "ci_lo",
    "ci_hi",
    "ci_level",
    "ci_method",
]
REGRESSION_CELL_KEYS = [
    "config_hash",
    "n_a",
    "n_b",
    "events_a",
    "events_b",
    "rate_a",
    "rate_b",
    "delta",
    "p",
    "q",
    "verdict",
    "mde",
]
REGRESSION_INT_KEYS = ("n_a", "n_b", "events_a", "events_b")
REGRESSION_STR_KEYS = ("config_hash", "verdict")
#: The single-event ``diff``'s detection limit (``mde_two_proportion`` at q 0.05, power 0.8) at
#: 32 against 32, by the baseline's count: the values the frozen pre-amendment record held at
#: these counts, bit for bit, except 15 and 21, which that record had no cell at and which were
#: measured on main's unchanged build (05cd1e8). A baseline of 32 has no limit (PF4.15).
MDE_AT_32 = {
    0: 0.23272860124178862,
    4: 0.3084586246584422,
    11: 0.34361923907337655,
    12: 0.34231764190792546,
    14: 0.3360426082663821,
    15: 0.3311476663122903,
    16: 0.32510999650094163,
    17: 0.31793560258449816,
    18: 0.3096184808103999,
    19: 0.30014029828805633,
    20: 0.2894693869952789,
    21: 0.2775589204333073,
    22: 0.26434401505014193,
    23: 0.24973730400301974,
    24: 0.2336221980422124,
    26: 0.1875,
}
#: The single-event record's words for the reference's directions (the event has no kind there).
AS_VERDICT = {"lower": "safer", "higher": "worse", "unchanged": "unchanged"}


def reference_record() -> dict[str, Any]:
    """The single-event fisher_bh diff of the lattice pair as the frozen record laid it out, built
    from the design and the references alone. A condition whose baseline tripped in every episode
    holds ``mde`` None (no limit); the frozen record held the old 0.5/n guard's number there."""
    reference = lattice.fisher(EVENT, Q)
    manifests = {run_id: lattice.manifest(run_id) for run_id in RUNS}
    cells = []
    for key in sorted(reference):
        r = reference[key]
        cells.append({
            "config_hash": key, "delta": r["delta"], "events_a": r["events_a"], "events_b": r["events_b"],
            "mde": None if r["events_a"] == r["n_a"] else MDE_AT_32[r["events_a"]],
            "n_a": r["n_a"], "n_b": r["n_b"], "p": r["p"], "q": r["q"],
            "rate_a": r["events_a"] / r["n_a"], "rate_b": r["events_b"] / r["n_b"],
            "verdict": AS_VERDICT[r["direction"]],
        })
    verdicts = [c["verdict"] for c in cells]
    return {
        "a": lattice.RUN_A, "b": lattice.RUN_B, "event": EVENT, "method": "fisher_bh",
        "q_threshold": Q, "power": POWER, "n_cells": len(cells),
        "n_safer": verdicts.count("safer"), "n_worse": verdicts.count("worse"),
        "n_unchanged": verdicts.count("unchanged"),
        # By construction: every condition is in both runs, at one horizon, with no errored row.
        "n_not_comparable": 0, "dropped_a": 0, "dropped_b": 0, "truncated": 0,
        "max_mde": max(c["mde"] for c in cells if c["mde"] is not None),
        # The two manifests share one salt, and every (condition, replicate) one seed.
        "paired": manifests[lattice.RUN_A]["run_salt"] == manifests[lattice.RUN_B]["run_salt"],
        "horizon": lattice.HORIZON, "t_unit": lattice.T_UNIT,
        "cells": cells,
    }
TRADES_COLUMNS = ["config_hash", "config", "safer_events", "worse_events"]
MULTI_SCALAR_FIELDS = [
    "method",
    "seed_identity_match",
    "unpaired_analysis",
    "q",
    "t_unit",
    "horizon",
    "n_tests",
    "n_not_comparable",
    "dropped_a",
    "dropped_b",
    "truncated",
    "inferred",
    "non_event",
]
EVENT_COUNT_FIELDS = ["n_safer", "n_worse", "n_unchanged"]
M4_COLUMNS = [
    "run_id",
    "config_hash",
    "config",
    "seed",
    "replicate_index",
    "outcome",
    "t",
    "horizon",
    "confidence",
    "meta",
    "error",
    "wall_time",
    "backend_meta",
]


# ---------- helpers: frames and manifests ----------


def _manifest(run_id: str = "r", *, run_salt: str = "salt", t_unit: str = "steps") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        target_id=f"target@{run_id}",
        t_unit=t_unit,
        run_salt=run_salt,
        axis_types={"cell": "categorical"},
        backend="local",
        environment={},
    )


Row = tuple  # (outcome | None, t) or (outcome | None, t, replicate_index)


def _raw(cells: dict[str, list[Row]], *, horizon: float = HORIZON, run_id: str = "r") -> pd.DataFrame:
    """Store.read()-shaped frame from {cell label: [(outcome, t[, replicate_index])]}.

    ``outcome is None`` is an errored row: t, horizon and confidence are None and
    ``error`` is set, exactly as M4's EpisodeRecord requires.
    """
    records = []
    for label, rows in cells.items():
        config = {"cell": label}
        h = config_hash(config)
        for i, row in enumerate(rows):
            outcome, t = row[0], row[1]
            rep = int(row[2]) if len(row) > 2 else i
            errored = outcome is None
            records.append(
                {
                    "run_id": run_id,
                    "config_hash": h,
                    "config": dict(config),
                    "seed": 1000 + rep,
                    "replicate_index": rep,
                    "outcome": outcome,
                    "t": None if errored else float(t),
                    "horizon": None if errored else float(horizon),
                    "confidence": None,
                    "meta": {},
                    "error": "boom" if errored else None,
                    "wall_time": 0.0,
                    "backend_meta": {},
                }
            )
    df = pd.DataFrame.from_records(records, columns=M4_COLUMNS)
    df["t"] = df["t"].astype(float)
    df["horizon"] = df["horizon"].astype(float)
    df["outcome"] = df["outcome"].astype(object)
    return df


def _cell(n: int = N, *, fill: str = "completed", t: float = HORIZON, **counts: int) -> list[Row]:
    """n rows at time t: the given outcome counts, the remainder ``fill``."""
    rows: list[Row] = []
    for outcome, k in counts.items():
        rows.extend((outcome, t) for _ in range(k))
    if len(rows) > n:
        raise ValueError(f"counts {counts} exceed n={n}")
    rows.extend((fill, t) for _ in range(n - len(rows)))
    return rows


def _hash(label: str) -> str:
    return config_hash({"cell": label})


def _multi(
    a: pd.DataFrame,
    b: pd.DataFrame,
    events: Sequence[str] | None,
    *,
    method: str = "fisher_bh",
    q: float = Q,
    salt_a: str = "salt",
    salt_b: str = "salt",
    manifests: bool = True,
    t_unit_b: str = "steps",
    kinds: dict[str, str] | None = None,
) -> MultiDiffResult:
    return multi_diff(
        a, b, events=events, method=method, q=q, power=POWER,
        manifest_a=_manifest("a", run_salt=salt_a) if manifests else None,
        manifest_b=_manifest("b", run_salt=salt_b, t_unit=t_unit_b) if manifests else None,
        kinds=kinds,
    )


def _single(a: pd.DataFrame, b: pd.DataFrame, event: str, *, method: str = "fisher_bh", q: float = Q) -> DiffResult:
    return diff(
        censor(a, event), censor(b, event), event=event, method=method, q=q, power=POWER,
        manifest_a=_manifest("a"), manifest_b=_manifest("b"),
    )


def _fisher_p(ea: int, eb: int, n: int = N) -> float:
    return float(fisher_exact([[ea, n - ea], [eb, n - eb]], alternative="two-sided")[1])


def _headline_counts(headline: str) -> tuple[list[tuple[str, int, int]], str]:
    """(per-event (event, n_lower, n_higher) in printed order, parenthetical)."""
    lines = [line for line in headline.splitlines() if line.strip()]
    assert len(lines) == 2, headline
    # PF4 (PF4.20): no frame here gives its event a kind, so the headline prints direction words,
    # "N lower, M higher", in place of "N safer, M worse"; the counts are the same numbers.
    events = [(e, int(lo), int(hi)) for e, lo, hi in re.findall(r"(\S+): (\d+) lower, (\d+) higher", lines[0])]
    paren = lines[1].strip()
    assert paren.startswith("(") and paren.endswith(")"), headline
    return events, paren[1:-1]


def _walk(tree: Any, key: str | None = None) -> Iterator[tuple[str | None, dict]]:
    if isinstance(tree, dict):
        yield key, tree
        for k, v in tree.items():
            yield from _walk(v, k)
    elif isinstance(tree, list):
        for v in tree:
            yield from _walk(v, key)


def _json_event_counts(js: dict, event: str) -> dict:
    for key, d in _walk(js):
        if all(f in d for f in EVENT_COUNT_FIELDS) and (key == event or d.get("event") == event):
            return d
    raise AssertionError(f"to_json() carries no per-event counts for {event!r}")


def _assert_same_multi(x: MultiDiffResult, y: MultiDiffResult) -> None:
    assert x.events == y.events
    for field in MULTI_SCALAR_FIELDS:
        assert getattr(x, field) == getattr(y, field), field
    for event in x.events:
        ex, ey = x.by_event[event], y.by_event[event]
        for field in [*EVENT_COUNT_FIELDS, "max_mde_unchanged_cell", "cause_specific", "event"]:
            assert getattr(ex, field) == getattr(ey, field), (event, field)
        # PF4 (PF4.15): a condition at a 100% baseline is left out of max_mde, so an event whose
        # every condition is there has no max_mde (NaN), compared like max_mde_unchanged.
        assert _same_or_both_nan(ex.max_mde, ey.max_mde), (event, "max_mde")
        assert _same_or_both_nan(ex.max_mde_unchanged, ey.max_mde_unchanged)
        pd.testing.assert_frame_equal(ex.cells, ey.cells)
    pd.testing.assert_frame_equal(x.trades, y.trades)
    assert x.headline() == y.headline()
    assert x.trade_line() == y.trade_line()
    assert x.to_markdown() == y.to_markdown()


def _same_or_both_nan(x: float, y: float) -> bool:
    return (math.isnan(x) and math.isnan(y)) or x == y


# ---------- helpers: the A11 trade builder ----------


def _trade_counts(q_threshold: float, *, n: int = N, n_fillers: int = 6) -> dict[str, tuple[int, int, int, int]]:
    """Search counts for two cells over events (timeout, violated) with n rows per arm.

    Returns {"x": (t_a, v_a, t_b, v_b), "y": (t_a, v_a, t_b, v_b)} where, after BH over the
    whole family (X, Y and ``n_fillers`` identical-arm cells, two tests each):

    - X: timeout hi -> lo is significantly safer AND violated lo -> hi is significantly
      worse, using the smallest swing that achieves both;
    - Y: timeout hi -> lo is significantly safer, violated lo -> lo + s rises by the
      largest step that stays non-significant, so Y's opposite move is a sign, not a
      trade.

    Both hold in the family with X and Y together (the trade case) and in the family
    with Y alone (the no-trade case), which is smaller and therefore stricter on Y.
    """
    filler_p = [1.0] * (2 * n_fillers)

    def holds(p_swing: float, p_step: float) -> bool:
        together = bh(np.array([p_swing, p_swing, p_swing, p_step, *filler_p]), q_threshold)
        alone = bh(np.array([p_swing, p_step, *filler_p]), q_threshold)
        swings_significant = bool(np.all(together[:3] < q_threshold)) and alone[0] < q_threshold
        # PF4 re-freeze (PF4.34): a trade reads the rows that count for the verdict, Holm's, so the
        # swings must also count under Holm over the same family.
        holm_together = holm(np.array([p_swing, p_swing, p_swing, p_step, *filler_p]), q_threshold)
        holm_alone = holm(np.array([p_swing, p_step, *filler_p]), q_threshold)
        swings_significant = (
            swings_significant and bool(np.all(holm_together[:3] < q_threshold)) and holm_alone[0] < q_threshold
        )
        step_not = together[3] >= q_threshold and alone[1] >= q_threshold
        return swings_significant and step_not

    for gap in range(1, n + 1):
        for lo in range(0, n - gap + 1):
            hi = lo + gap
            if hi + lo > n:
                continue
            p_swing = _fisher_p(hi, lo, n)
            best_step = None
            for step in range(1, n - 2 * lo + 1):
                if holds(p_swing, _fisher_p(lo, lo + step, n)):
                    best_step = step
            if best_step is not None:
                return {"x": (hi, lo, lo, hi), "y": (hi, lo, lo, lo + best_step)}
    raise AssertionError(f"no trade counts found for q={q_threshold}, n={n}")


def _trade_frames(
    counts: dict[str, tuple[int, int, int, int]], *, include: Sequence[str] = ("x", "y"), n_fillers: int = 6
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cells_a: dict[str, list[Row]] = {}
    cells_b: dict[str, list[Row]] = {}
    for label in include:
        t_a, v_a, t_b, v_b = counts[label]
        cells_a[label] = _cell(timeout=t_a, violated=v_a)
        cells_b[label] = _cell(timeout=t_b, violated=v_b)
    for i in range(n_fillers):
        cells_a[f"f{i}"] = _cell(timeout=4, violated=4)
        cells_b[f"f{i}"] = _cell(timeout=4, violated=4)
    return _raw(cells_a), _raw(cells_b)


# ---------- helpers: hypothesis strategies ----------


@st.composite
def run_pair(draw, *, max_cells: int = 4, n: int = 8) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two raw frames over OUTCOMES, sharing 1..max_cells cells, each side optionally
    holding one cell the other lacks."""
    k = draw(st.integers(min_value=1, max_value=max_cells))
    row = st.tuples(st.sampled_from(OUTCOMES), st.sampled_from(TIME_GRID))
    arm = st.lists(row, min_size=n, max_size=n)
    cells_a: dict[str, list[Row]] = {}
    cells_b: dict[str, list[Row]] = {}
    for i in range(k):
        cells_a[f"c{i}"] = draw(arm)
        cells_b[f"c{i}"] = draw(arm)
    if draw(st.booleans()):
        cells_a["only_a"] = draw(arm)
    if draw(st.booleans()):
        cells_b["only_b"] = draw(arm)
    return _raw(cells_a), _raw(cells_b)


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def raw(lattice_store: Store) -> dict[str, pd.DataFrame]:
    return {run_id: lattice_store.read(run_id) for run_id in RUNS}


@pytest.fixture(scope="module")
def manifests(lattice_store: Store) -> dict[str, RunManifest]:
    return {run_id: lattice_store.manifest(run_id) for run_id in RUNS}


@pytest.fixture(scope="module")
def regression() -> dict:
    return reference_record()


@pytest.fixture(scope="module")
def golden(raw: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]) -> DiffResult:
    return diff(
        censor(raw[lattice.RUN_A], EVENT), censor(raw[lattice.RUN_B], EVENT), event=EVENT,
        method="fisher_bh", q=Q, power=POWER,
        manifest_a=manifests[lattice.RUN_A], manifest_b=manifests[lattice.RUN_B],
    )


def _fixture_multi(
    raw: dict[str, pd.DataFrame], manifests: dict[str, RunManifest], events: Sequence[str] | None,
    method: str = "fisher_bh", a: str = lattice.RUN_A, b: str = lattice.RUN_B,
) -> MultiDiffResult:
    return multi_diff(
        raw[a], raw[b], events=events, method=method, q=Q, power=POWER,
        manifest_a=manifests[a], manifest_b=manifests[b],
    )


@pytest.fixture(scope="module")
def multi_tripped(raw: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]) -> MultiDiffResult:
    return _fixture_multi(raw, manifests, [EVENT])


@pytest.fixture(scope="module")
def trade_counts() -> dict[str, tuple[int, int, int, int]]:
    return _trade_counts(Q)


@pytest.fixture(scope="module")
def trade_result(trade_counts: dict[str, tuple[int, int, int, int]]) -> MultiDiffResult:
    a, b = _trade_frames(trade_counts)
    return _multi(a, b, ["timeout", "violated"])


# PF4 re-freeze (PF4.20, the library follows the screen): an event with no kind has no safer or
# worse and a kindless pair has no trade, so the trade tests give both events the kind "failure"
# (a fall is safer, a rise worse), which is what the safer/worse words of A11 read.
TRADE_KINDS = {"timeout": "failure", "violated": "failure"}


@pytest.fixture(scope="module")
def kinded_trade_result(trade_counts: dict[str, tuple[int, int, int, int]]) -> MultiDiffResult:
    a, b = _trade_frames(trade_counts)
    return _multi(a, b, ["timeout", "violated"], kinds=TRADE_KINDS)


@pytest.fixture(scope="module")
def headline_case() -> MultiDiffResult:
    # x: worse in c1 and c2; y: safer in c3; z: safer in c4. Passed as z, x, y so the
    # headline order (n_worse desc, n_safer desc, name) differs from the input order.
    a = _raw(
        {
            "c1": _cell(), "c2": _cell(), "c3": _cell(y=N), "c4": _cell(z=N),
            "c5": _cell(x=8, y=8, z=8),
        }
    )
    b = _raw(
        {
            "c1": _cell(x=N), "c2": _cell(x=N), "c3": _cell(), "c4": _cell(),
            "c5": _cell(x=8, y=8, z=8),
        }
    )
    return _multi(a, b, ["z", "x", "y"], salt_a="s1", salt_b="s2")


# ---------- A1: golden untouched, against the reference record ----------


def test_a1_regression_fixture_is_well_formed(regression: dict) -> None:
    assert regression["a"] == "lattice-a" and regression["b"] == "lattice-b"
    assert regression["event"] == EVENT and regression["method"] == "fisher_bh"
    assert regression["q_threshold"] == Q and regression["power"] == POWER
    cells = regression["cells"]
    assert len(cells) == regression["n_cells"] == CELLS
    hashes = [c["config_hash"] for c in cells]
    assert hashes == sorted(hashes) and len(set(hashes)) == CELLS
    for c in cells:
        assert list(c) == sorted(REGRESSION_CELL_KEYS), c["config_hash"]
    assert regression["n_safer"] == REFERENCE_SAFER and regression["n_worse"] == REFERENCE_WORSE
    assert regression["n_safer"] + regression["n_worse"] + regression["n_unchanged"] == CELLS
    # The frozen record's ceiling cells held the old 0.5/n guard's number; the reference holds
    # None there (no limit, PF4.15), so the maximum is over the cells with a limit.
    assert regression["max_mde"] == max(c["mde"] for c in cells if c["mde"] is not None) == MDE_AT_32[11]
    assert sum(c["mde"] is None for c in cells) == sum(c["events_a"] == c["n_a"] for c in cells) == 37
    verdicts = [c["verdict"] for c in cells]
    assert verdicts.count("safer") == REFERENCE_SAFER and verdicts.count("worse") == REFERENCE_WORSE
    # The record is the design: every condition's counts are the design's, in key order.
    design = {lattice.config_hash(c.config): c for c in lattice.design_cells()}
    assert set(hashes) == set(design)
    for c in cells:
        cell = design[c["config_hash"]]
        assert (c["n_a"], c["n_b"], c["events_a"], c["events_b"]) == (lattice.N, lattice.N, cell.tripped_a, cell.tripped_b)


def test_a1_golden_summary_matches_regression_fixture(golden: DiffResult, regression: dict) -> None:
    assert golden.n_safer == regression["n_safer"] == REFERENCE_SAFER
    assert golden.n_worse == regression["n_worse"] == REFERENCE_WORSE
    assert golden.n_unchanged == regression["n_unchanged"]
    assert golden.n_not_comparable == regression["n_not_comparable"]
    assert golden.dropped_a == regression["dropped_a"] and golden.dropped_b == regression["dropped_b"]
    assert golden.truncated == regression["truncated"]
    assert golden.max_mde == regression["max_mde"]
    # The S3 record's ``paired`` was salt equality; P-1's ``seed_identity_match`` is the salt plus the
    # stored seeds on every matched row, and on the lattice (2,304 matched, 0 differ) the two coincide.
    assert golden.seed_identity_match is regression["paired"] is True
    assert golden.unpaired_analysis is True
    assert golden.horizon == regression["horizon"] and golden.t_unit == regression["t_unit"]
    assert golden.q == regression["q_threshold"] and golden.method == regression["method"]
    assert len(golden.cells) == regression["n_cells"]
    assert list(golden.cells.columns) == CELLS_COLUMNS


def test_a1_golden_per_cell_bit_identical_to_regression_fixture(golden: DiffResult, regression: dict) -> None:
    frozen = {c["config_hash"]: c for c in regression["cells"]}
    assert set(golden.cells["config_hash"]) == set(frozen)
    for row in golden.cells.itertuples(index=False):
        ref = frozen[row.config_hash]
        for key in REGRESSION_CELL_KEYS:
            ours = getattr(row, key)
            if key == "mde" and ref["events_a"] == ref["n_a"]:
                # PF4 (PF4.15): a cell whose baseline had the event in every run has no detection
                # limit; the frozen file held the old 0.5/n guard's number there, now NaN.
                assert math.isnan(float(ours)), (row.config_hash, key, float(ours))
                continue
            if key in REGRESSION_INT_KEYS:
                assert int(ours) == ref[key], (row.config_hash, key)
            elif key in REGRESSION_STR_KEYS:
                assert str(ours) == ref[key], (row.config_hash, key)
            else:
                assert float(ours) == ref[key], (row.config_hash, key, float(ours), ref[key])


# ---------- A2: max_mde_unchanged ----------


def _expected_unchanged(cells: pd.DataFrame) -> tuple[float, set[str]]:
    unchanged = cells[cells["verdict"] == "unchanged"]
    top = float(unchanged["mde"].max())
    return top, set(unchanged.loc[unchanged["mde"] == top, "config_hash"])


def test_a2_diff_result_reports_max_mde_unchanged_on_golden(golden: DiffResult, regression: dict) -> None:
    top, attaining = _expected_unchanged(golden.cells)
    assert golden.max_mde_unchanged == top
    assert golden.max_mde_unchanged_cell in attaining
    assert golden.max_mde_unchanged_cell is not None and not math.isnan(golden.max_mde_unchanged)
    assert golden.max_mde_unchanged <= golden.max_mde
    frozen_top = max(c["mde"] for c in regression["cells"] if c["verdict"] == "unchanged" and c["mde"] is not None)
    assert frozen_top == MDE_AT_32[12]
    assert golden.max_mde_unchanged == frozen_top


def test_a2_event_diff_reports_max_mde_unchanged_on_golden(multi_tripped: MultiDiffResult) -> None:
    ev = multi_tripped.by_event[EVENT]
    top, attaining = _expected_unchanged(ev.cells)
    assert ev.max_mde_unchanged == top
    assert ev.max_mde_unchanged_cell in attaining
    assert ev.max_mde_unchanged <= ev.max_mde
    assert ev.max_mde == float(ev.cells["mde"].max())


def _mde_split_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    # "safer" is n=32 at rate 0.5 -> 0 (mde ~0.3); the two unchanged cells are n=200 at
    # rate 0.5 (mde ~0.14), so max_mde lands on a safer cell and max_mde_unchanged must
    # be strictly smaller and attained by an unchanged cell.
    a = _raw({"safer": _cell(fell=16), "u1": _cell(200, fell=100), "u2": _cell(160, fell=80)})
    b = _raw({"safer": _cell(fell=0), "u1": _cell(200, fell=100), "u2": _cell(160, fell=80)})
    return a, b


def test_a2_max_mde_unchanged_is_over_unchanged_cells_only_single_event() -> None:
    a, b = _mde_split_frames()
    result = _single(a, b, "fell")
    assert result.n_safer == 1 and result.n_unchanged == 2
    top, attaining = _expected_unchanged(result.cells)
    assert result.max_mde_unchanged == top
    assert result.max_mde_unchanged_cell in attaining
    assert result.max_mde_unchanged < result.max_mde
    assert result.max_mde_unchanged_cell != _hash("safer")


def test_a2_max_mde_unchanged_is_over_unchanged_cells_only_multi_event() -> None:
    a, b = _mde_split_frames()
    ev = _multi(a, b, ["fell"]).by_event["fell"]
    # PF4 re-freeze (PF4.20, the library follows the screen): "fell" has no kind here, so the
    # object carries no safer/worse counts; the one cell that was "safer" is the one that fell.
    assert ev.n_safer is None and ev.n_lower == 1 and ev.n_unchanged == 2
    top, attaining = _expected_unchanged(ev.cells)
    assert ev.max_mde_unchanged == top
    assert ev.max_mde_unchanged_cell in attaining
    assert ev.max_mde_unchanged < ev.max_mde


# ---------- A3: no unchanged cells ----------


def _all_significant_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    a = _raw({"c1": _cell(fell=N), "c2": _cell(fell=20)})
    b = _raw({"c1": _cell(fell=0), "c2": _cell(fell=0)})
    return a, b


def test_a3_no_unchanged_cells_single_event() -> None:
    a, b = _all_significant_frames()
    result = _single(a, b, "fell")
    assert result.n_unchanged == 0 and result.n_safer == 2
    assert math.isnan(result.max_mde_unchanged)
    assert result.max_mde_unchanged_cell is None
    assert result.max_mde > 0.0


def test_a3_no_unchanged_cells_multi_event() -> None:
    a, b = _all_significant_frames()
    ev = _multi(a, b, ["fell"]).by_event["fell"]
    # PF4 re-freeze (PF4.20, the library follows the screen): no kind, so the two "safer" cells are
    # counted as lower and n_safer is null.
    assert ev.n_unchanged == 0 and ev.n_safer is None and ev.n_lower == 2
    assert math.isnan(ev.max_mde_unchanged)
    assert ev.max_mde_unchanged_cell is None


# ---------- A4: worst-cells ordering — NOT MAPPED, see module docstring ----------


# ---------- A5: single event via multi ----------


def test_a5_single_event_via_multi_matches_diff(golden: DiffResult, multi_tripped: MultiDiffResult) -> None:
    assert multi_tripped.events == (EVENT,)
    assert set(multi_tripped.by_event) == {EVENT}
    ev = multi_tripped.by_event[EVENT]
    assert isinstance(ev, EventDiff) and ev.event == EVENT
    # PF4 re-freeze (PF4.20, the library follows the screen): the comparison object
    # gives "tripped" no kind, so its reference 22 safer and 0 worse are 22 lower and 0 higher, with
    # n_safer and n_worse null; the single-event DiffResult keeps its safer/worse record.
    assert ev.n_safer is None and ev.n_worse is None
    assert ev.n_lower == golden.n_safer == REFERENCE_SAFER
    assert ev.n_higher == golden.n_worse == REFERENCE_WORSE
    assert ev.n_unchanged == golden.n_unchanged
    assert multi_tripped.n_tests == CELLS
    assert len(ev.cells) == CELLS and multi_tripped.n_not_comparable == 0
    assert list(ev.cells.columns) == CELLS_COLUMNS
    assert multi_tripped.method == "fisher_bh" and multi_tripped.seed_identity_match is True
    assert multi_tripped.q == Q and multi_tripped.t_unit == "seconds" and multi_tripped.horizon == HORIZON
    assert multi_tripped.inferred is False and multi_tripped.non_event is None


def test_a5_single_event_via_multi_per_cell_agrees_with_diff(golden: DiffResult, multi_tripped: MultiDiffResult) -> None:
    ours = multi_tripped.by_event[EVENT].cells.set_index("config_hash")
    ref = golden.cells.set_index("config_hash")
    assert list(ours.index) == list(ref.index)
    for col in ("n_a", "n_b", "events_a", "events_b"):
        assert (ours[col].to_numpy() == ref[col].to_numpy()).all(), col
    for col in ("p", "q", "delta"):
        np.testing.assert_allclose(ours[col].to_numpy(dtype=float), ref[col].to_numpy(dtype=float), rtol=0, atol=TOL_EXACT)
    # PF4 re-freeze (PF4.22, PF4.23, PF4.27): the comparison's limit is Fisher's exact
    # power at the lone-change level q / M, both ways, with mde the larger, while the
    # single-event DiffResult keeps its own record, so the two mde columns no longer agree; the
    # comparison's is recomputed here from the stats suite's reference.
    level = Q / multi_tripped.n_tests
    refs: dict[int, tuple[float | None, float | None]] = {}
    for row in ours.itertuples():
        n_a, events_a = int(row.n_a), int(row.events_a)
        if events_a not in refs:
            refs[events_a] = _ref_fisher_limits(events_a, n_a, int(row.n_b), level)
        rise, fall = refs[events_a]
        if events_a == n_a:
            rise = None  # no room to rise
        if events_a == 0:
            fall = None  # no room to fall
        if rise is not None and fall is not None:
            want = max(rise, fall)
        elif events_a in (0, n_a):
            want = rise if fall is None else fall
        else:
            want = None  # a direction with room and no limit leaves no single number
        assert abs(float(row.mde_level) - level) <= 1e-15, row.Index
        _assert_limit(row.mde, want, (row.Index, events_a))
    # PF4 re-freeze (PF4.20, the library follows the screen): the comparison's "tripped"
    # has no kind, so its verdict column reads direction words where DiffResult's reads safer/worse.
    as_direction = {"safer": "lower", "worse": "higher", "unchanged": "unchanged"}
    assert list(ours["verdict"]) == [as_direction[v] for v in ref["verdict"]]


# ---------- A6: CIF equals the rate without censoring ----------


def test_a6_cif_equals_rate_on_fixture(multi_tripped: MultiDiffResult, regression: dict) -> None:
    cells = multi_tripped.by_event[EVENT].cells
    rate_a = cells["events_a"].to_numpy(dtype=float) / cells["n_a"].to_numpy(dtype=float)
    rate_b = cells["events_b"].to_numpy(dtype=float) / cells["n_b"].to_numpy(dtype=float)
    np.testing.assert_allclose(cells["rate_a"].to_numpy(dtype=float), rate_a, rtol=0, atol=TOL_EXACT)
    np.testing.assert_allclose(cells["rate_b"].to_numpy(dtype=float), rate_b, rtol=0, atol=TOL_EXACT)
    np.testing.assert_allclose(cells["delta"].to_numpy(dtype=float), rate_b - rate_a, rtol=0, atol=TOL_EXACT)
    frozen = {c["config_hash"]: c for c in regression["cells"]}
    for row in cells.itertuples(index=False):
        assert abs(row.rate_a - frozen[row.config_hash]["rate_a"]) <= TOL_EXACT


# ---------- A7: CIF is used, not the rate — NOT MAPPED, see module docstring ----------


# ---------- A8: one BH family ----------


def _pooled_p_and_q(result: MultiDiffResult) -> tuple[np.ndarray, np.ndarray]:
    p = np.concatenate([result.by_event[e].cells["p"].to_numpy(dtype=float) for e in result.events])
    q = np.concatenate([result.by_event[e].cells["q"].to_numpy(dtype=float) for e in result.events])
    return p, q


def _a8_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    a = _raw(
        {
            "c1": _cell(timeout=20, violated=2), "c2": _cell(timeout=10, violated=10),
            "c3": _cell(timeout=4, violated=12), "c4": _cell(timeout=1, violated=1),
            "only_a": _cell(timeout=8),
        }
    )
    b = _raw(
        {
            "c1": _cell(timeout=4, violated=12), "c2": _cell(timeout=12, violated=6),
            "c3": _cell(timeout=4, violated=12), "c4": _cell(timeout=9, violated=0),
            "only_b": _cell(violated=8),
        }
    )
    return a, b


def test_a8_n_tests_is_cells_times_events_synthetic() -> None:
    a, b = _a8_frames()
    result = _multi(a, b, ["timeout", "violated"])
    assert result.n_not_comparable == 2 and result.dropped_a == 1 and result.dropped_b == 1
    for e in result.events:
        assert len(result.by_event[e].cells) == 4
    assert result.n_tests == 4 * 2


def test_a8_n_tests_is_cells_times_events_fixture(raw: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]) -> None:
    result = _fixture_multi(raw, manifests, [lattice.EVENT, lattice.OTHER])
    assert result.n_tests == CELLS * 2
    assert all(len(result.by_event[e].cells) == CELLS for e in result.events)


def test_a8_every_q_is_bh_over_pooled_p_synthetic() -> None:
    a, b = _a8_frames()
    result = _multi(a, b, ["timeout", "violated"])
    p, q = _pooled_p_and_q(result)
    assert len(p) == result.n_tests
    np.testing.assert_allclose(q, bh(p, Q), rtol=0, atol=TOL_EXACT)


def test_a8_every_q_is_bh_over_pooled_p_fixture(raw: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]) -> None:
    result = _fixture_multi(raw, manifests, [lattice.EVENT, lattice.OTHER])
    p, q = _pooled_p_and_q(result)
    assert len(p) == result.n_tests == CELLS * 2
    np.testing.assert_allclose(q, bh(p, Q), rtol=0, atol=TOL_EXACT)


def _assert_family_never_smaller(both: MultiDiffResult, singles: dict[str, MultiDiffResult]) -> None:
    assert both.n_tests == sum(s.n_tests for s in singles.values())
    for e in both.events:
        joint = both.by_event[e].cells.set_index("config_hash")
        alone = singles[e].by_event[e].cells.set_index("config_hash")
        assert list(joint.index) == list(alone.index)
        np.testing.assert_allclose(joint["p"].to_numpy(dtype=float), alone["p"].to_numpy(dtype=float), rtol=0, atol=TOL_EXACT)
        assert np.all(joint["q"].to_numpy(dtype=float) >= alone["q"].to_numpy(dtype=float) - TOL_EXACT), e
        # PF4 re-freeze (PF4.20, the library follows the screen): no event here has a kind, so the
        # counts compared are the direction counts (n_safer and n_worse are null).
        assert both.by_event[e].n_lower <= singles[e].by_event[e].n_lower
        assert both.by_event[e].n_higher <= singles[e].by_event[e].n_higher


def test_a8_two_events_together_never_smaller_q_than_separately_synthetic() -> None:
    a, b = _a8_frames()
    both = _multi(a, b, ["timeout", "violated"])
    singles = {e: _multi(a, b, [e]) for e in ("timeout", "violated")}
    _assert_family_never_smaller(both, singles)
    # The family really is larger: at least one q strictly grows.
    _, q_both = _pooled_p_and_q(both)
    q_alone = np.concatenate([singles[e].by_event[e].cells["q"].to_numpy(dtype=float) for e in both.events])
    assert np.any(q_both > q_alone + TOL_EXACT)


def test_a8_two_events_together_never_smaller_q_than_separately_fixture(
    raw: dict[str, pd.DataFrame], manifests: dict[str, RunManifest]
) -> None:
    both = _fixture_multi(raw, manifests, [lattice.EVENT, lattice.OTHER])
    singles = {e: _fixture_multi(raw, manifests, [e]) for e in (lattice.EVENT, lattice.OTHER)}
    _assert_family_never_smaller(both, singles)


# ---------- A9: counts ----------


def _assert_counts(result: MultiDiffResult, a: pd.DataFrame, b: pd.DataFrame) -> None:
    union = set(a["config_hash"]) | set(b["config_hash"])
    common = set(a["config_hash"]) & set(b["config_hash"])
    for e in result.events:
        ev = result.by_event[e]
        # PF4 re-freeze (PF4.20, the library follows the screen): no event here has a kind, so the
        # verdict column holds direction words and the counts are n_lower and n_higher.
        assert ev.n_safer is None and ev.n_worse is None, e
        assert ev.n_lower + ev.n_higher + ev.n_unchanged == len(ev.cells) == len(common), e
        counts = ev.cells["verdict"].value_counts()
        assert ev.n_lower == counts.get("lower", 0) and ev.n_higher == counts.get("higher", 0)
        assert ev.n_unchanged == counts.get("unchanged", 0)
        assert list(ev.cells["config_hash"]) == sorted(common)
    assert len(common) + result.n_not_comparable == len(union)
    assert result.n_not_comparable == result.dropped_a + result.dropped_b


@settings(max_examples=40, deadline=None)
@given(pair=run_pair())
def test_a9_counts_add_up_property(pair: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    a, b = pair
    result = _multi(a, b, ["timeout", "violated"])
    _assert_counts(result, a, b)


def test_a9_counts_add_up_on_fixture(multi_tripped: MultiDiffResult, raw: dict[str, pd.DataFrame]) -> None:
    _assert_counts(multi_tripped, raw[lattice.RUN_A], raw[lattice.RUN_B])
    ev = multi_tripped.by_event[EVENT]
    # PF4 re-freeze (PF4.20, the library follows the screen): the direction counts, "tripped" having no kind.
    assert ev.n_lower + ev.n_higher + ev.n_unchanged == CELLS


# ---------- A10: headline ----------


def _assert_headline(result: MultiDiffResult) -> None:
    printed, paren = _headline_counts(result.headline())
    # PF4 (PF4.20): with no kind the order "worse, then safer, then name" reads as "higher, then
    # lower, then name", and the printed counts are each event's n_lower and n_higher.
    assert [e for e, _, _ in printed] == sorted(
        result.events, key=lambda e: (-result.by_event[e].n_higher, -result.by_event[e].n_lower, e)
    )
    for e, lower, higher in printed:
        assert lower == result.by_event[e].n_lower and higher == result.by_event[e].n_higher, e
    assert result.method in paren
    assert f"q<{result.q}" in paren or f"q<{result.q:g}" in paren, paren
    assert re.search(rf"\b{result.n_tests}\b", paren), paren
    # P-1: the token states the requested method's pairing, never the runs' seed identity.
    if result.method == "mcnemar_bh":
        assert "paired" in paren and "unpaired" not in paren
    else:
        assert "unpaired" in paren


def test_a10_headline_on_fixture(multi_tripped: MultiDiffResult) -> None:
    printed, paren = _headline_counts(multi_tripped.headline())
    # PF4 (PF4.20): printed as "22 lower, 0 higher"; the reference's 22 safer are the 22 conditions where tripped went down.
    assert printed == [(EVENT, REFERENCE_SAFER, REFERENCE_WORSE)]
    assert "fisher_bh" in paren and "72" in paren and "unpaired" in paren
    _assert_headline(multi_tripped)


def test_a10_headline_orders_worse_then_safer_then_name(headline_case: MultiDiffResult) -> None:
    by = headline_case.by_event
    # PF4 re-freeze (PF4.20, the library follows the screen): no kind, so (n_lower, n_higher) where
    # the object read (n_safer, n_worse); the numbers are the same.
    assert (by["x"].n_lower, by["x"].n_higher) == (0, 2)
    assert (by["y"].n_lower, by["y"].n_higher) == (1, 0)
    assert (by["z"].n_lower, by["z"].n_higher) == (1, 0)
    assert headline_case.events == ("z", "x", "y")
    printed, paren = _headline_counts(headline_case.headline())
    assert [e for e, _, _ in printed] == ["x", "y", "z"]
    # PF4 (PF4.20): (event, lower, higher); x rose in two cells, y and z each fell in one.
    assert printed == [("x", 0, 2), ("y", 1, 0), ("z", 1, 0)]
    assert headline_case.seed_identity_match is False and "unpaired" in paren
    assert re.search(r"\b15\b", paren) and headline_case.n_tests == 15
    _assert_headline(headline_case)


def test_a10_headline_on_trade_case(trade_result: MultiDiffResult) -> None:
    _assert_headline(trade_result)


# ---------- A11: trade detection ----------


def test_a11_trade_builder_finds_counts(trade_counts: dict[str, tuple[int, int, int, int]]) -> None:
    (xt_a, xv_a, xt_b, xv_b), (yt_a, yv_a, yt_b, yv_b) = trade_counts["x"], trade_counts["y"]
    assert xt_a > xt_b and xv_a < xv_b
    assert yt_a > yt_b and yv_a < yv_b
    assert xt_a + xv_a <= N and xt_b + xv_b <= N and yt_a + yv_a <= N and yt_b + yv_b <= N


def test_a11_engineered_cell_is_exactly_one_trade(
    trade_result: MultiDiffResult, kinded_trade_result: MultiDiffResult, trade_counts: dict[str, tuple[int, int, int, int]]
) -> None:
    # PF4 re-freeze (PF4.20, the library follows the screen): with no kind the engineered cell reads
    # lower in timeout and higher in violated; it is still recorded as the one condition that moved
    # both ways, its line in direction words, and the comparison's word is mixed ...
    kindless_t = trade_result.by_event["timeout"].cells.set_index("config_hash")
    kindless_v = trade_result.by_event["violated"].cells.set_index("config_hash")
    assert kindless_t.loc[_hash("x"), "verdict"] == "lower" and kindless_v.loc[_hash("x"), "verdict"] == "higher"
    assert len(trade_result.trades) == 1 and list(trade_result.trades.columns) == TRADES_COLUMNS
    assert trade_result.comparison_verdict() == "mixed"
    line = trade_result.trade_line()
    assert line is not None and "fell" in line and "rose" in line and "safer" not in line and "worse" not in line
    # ... and with both events failures it is exactly the one trade A11 froze.
    trade_result = kinded_trade_result
    timeout = trade_result.by_event["timeout"].cells.set_index("config_hash")
    violated = trade_result.by_event["violated"].cells.set_index("config_hash")
    x, y = _hash("x"), _hash("y")
    assert timeout.loc[x, "verdict"] == "safer" and violated.loc[x, "verdict"] == "worse"
    assert timeout.loc[y, "verdict"] == "safer" and violated.loc[y, "verdict"] == "unchanged"
    assert violated.loc[y, "delta"] > 0
    assert list(trade_result.trades.columns) == TRADES_COLUMNS
    assert len(trade_result.trades) == 1
    row = trade_result.trades.iloc[0]
    assert row["config_hash"] == x
    assert row["config"] == {"cell": "x"}
    assert tuple(row["safer_events"]) == ("timeout",)
    assert tuple(row["worse_events"]) == ("violated",)


def test_a11_trade_line_names_both_events_and_the_count(kinded_trade_result: MultiDiffResult) -> None:
    # PF4 re-freeze (PF4.20): a trade needs kinds, so the line is read from the kinded result.
    line = kinded_trade_result.trade_line()
    assert line is not None
    assert "timeout" in line and "violated" in line
    assert re.search(r"\b1 cell", line), line


def test_a11_no_trade_when_the_opposite_move_is_not_significant(
    trade_counts: dict[str, tuple[int, int, int, int]]
) -> None:
    a, b = _trade_frames(trade_counts, include=("y",))
    # PF4 re-freeze (PF4.20): the safer/unchanged words need kinds; both events are failures.
    result = _multi(a, b, ["timeout", "violated"], kinds=TRADE_KINDS)
    y = _hash("y")
    timeout = result.by_event["timeout"].cells.set_index("config_hash")
    violated = result.by_event["violated"].cells.set_index("config_hash")
    assert timeout.loc[y, "verdict"] == "safer" and violated.loc[y, "verdict"] == "unchanged"
    assert violated.loc[y, "delta"] > 0
    assert len(result.trades) == 0
    assert list(result.trades.columns) == TRADES_COLUMNS
    assert result.trade_line() is None


def test_a11_no_trade_on_fixture(multi_tripped: MultiDiffResult) -> None:
    assert len(multi_tripped.trades) == 0
    assert multi_tripped.trade_line() is None


# ---------- A12: trade line is a count, not a claim ----------


def test_a12_trade_line_has_no_causal_verb(kinded_trade_result: MultiDiffResult) -> None:
    # PF4 re-freeze (PF4.20): a trade needs kinds, so the line is read from the kinded result.
    line = kinded_trade_result.trade_line()
    assert line is not None
    lowered = line.lower()
    for word in BANNED_CAUSAL:
        assert word not in lowered, (word, line)


# ---------- A13: inference ----------


def test_a13_infer_events_drops_the_most_frequent_outcome() -> None:
    a = _raw({"c": _cell(100, completed=30, violated=15, timeout=5)})
    b = _raw({"c": _cell(100, completed=30, violated=15, timeout=5)})
    assert infer_events(a, b) == (("violated", "timeout"), "completed")


def test_a13_infer_events_pools_both_runs() -> None:
    # Run B has no timeouts at all; pooled counts are completed 60, violated 30, timeout 10.
    a = _raw({"c": _cell(100, completed=20, violated=20, timeout=10)})
    b = _raw({"c": _cell(100, completed=40, violated=10)})
    assert infer_events(a, b) == (("violated", "timeout"), "completed")


def test_a13_infer_events_ignores_errored_rows() -> None:
    a = _raw({"c": [*_cell(40, completed=30, violated=10), *[(None, 0.0)] * 50]})
    b = _raw({"c": _cell(40, completed=30, violated=10)})
    assert infer_events(a, b) == (("violated",), "completed")


def test_a13_frequency_tie_raises_naming_both() -> None:
    a = _raw({"c": _cell(60, completed=30, violated=30)})
    b = _raw({"c": _cell(60, completed=30, violated=30)})
    with pytest.raises(EventInferenceError) as info:
        infer_events(a, b)
    assert "completed" in str(info.value) and "violated" in str(info.value)


def test_a13_zero_events_raises_naming_the_outcome() -> None:
    a = _raw({"c": _cell(completed=N)})
    with pytest.raises(EventInferenceError) as info:
        infer_events(a, a.copy())
    assert "completed" in str(info.value)


def test_a13_more_than_six_events_raises_naming_the_outcomes() -> None:
    names = [f"o{i}" for i in range(7)]
    counts = {"completed": 20, **{name: 7 - i for i, name in enumerate(names)}}
    a = _raw({"c": _cell(60, **counts)})
    with pytest.raises(EventInferenceError) as info:
        infer_events(a, a.copy())
    message = str(info.value)
    for name in ["completed", *names]:
        assert name in message, name


def test_a13_six_events_is_allowed() -> None:
    names = [f"o{i}" for i in range(6)]
    counts = {"completed": 20, **{name: 6 - i for i, name in enumerate(names)}}
    a = _raw({"c": _cell(60, **counts)})
    events, non_event = infer_events(a, a.copy())
    assert non_event == "completed" and set(events) == set(names) and len(events) == 6


def test_a13_event_inference_error_is_a_diff_error() -> None:
    assert issubclass(EventInferenceError, DiffError)


#: The inference line's marker, a line prefix and never a substring: report.md's Provenance prints ``- inferred: false``, which a bare ``inferred: `` would match.
INFERENCE_MARKER = "inferred: no event was given, so "


def _inference_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    a = _raw({"c1": _cell(completed=20, violated=8, timeout=4), "c2": _cell(completed=24, violated=6, timeout=2)})
    b = _raw({"c1": _cell(completed=16, violated=12, timeout=4), "c2": _cell(completed=24, violated=6, timeout=2)})
    return a, b


def test_a13_multi_diff_infers_when_events_is_none() -> None:
    a, b = _inference_frames()
    result = _multi(a, b, None)
    assert result.inferred is True and result.non_event == "completed"
    assert result.events == ("violated", "timeout")
    explicit = _multi(a, b, ["violated", "timeout"])
    assert explicit.inferred is False and explicit.non_event is None
    assert result.n_tests == explicit.n_tests == 4


# ---------- A14: to_markdown / to_json ----------


def test_a14_markdown_prints_inference_line_iff_inferred() -> None:
    a, b = _inference_frames()
    inferred = _multi(a, b, None)
    first = inferred.to_markdown().splitlines()[0]
    assert first == "inferred: no event was given, so the event set is violated, timeout; the non-event is completed, the most frequent outcome"
    explicit = _multi(a, b, ["violated", "timeout"])
    assert not [line for line in explicit.to_markdown().splitlines() if line.startswith(INFERENCE_MARKER)]


def test_a14_markdown_has_no_inference_line_on_fixture(multi_tripped: MultiDiffResult) -> None:
    assert not [line for line in multi_tripped.to_markdown().splitlines() if line.startswith(INFERENCE_MARKER)]


def _assert_json_round_trip(result: MultiDiffResult) -> None:
    js = result.to_json()
    assert isinstance(js, dict)
    for field in MULTI_SCALAR_FIELDS:
        assert field in js, field
        assert js[field] == getattr(result, field), field
    assert list(js["events"]) == list(result.events)
    for e in result.events:
        counts = _json_event_counts(js, e)
        ev = result.by_event[e]
        # PF4 (PF4.20): no frame here gives its event a kind, so the JSON carries ``kind`` null,
        # ``n_safer`` and ``n_worse`` null, and the direction counts ``n_higher``/``n_lower``
        # beside them; ``n_unchanged`` is unchanged.
        assert ev.kind is None and counts["kind"] is None, e
        assert counts["n_safer"] is None and counts["n_worse"] is None, e
        assert counts["n_higher"] == ev.n_higher and counts["n_lower"] == ev.n_lower, e
        assert counts["n_unchanged"] == ev.n_unchanged, e
    text = json.dumps(js)
    assert not re.search(r"-0\.0+(?!\d)", text)
    assert not re.search(r"-0\.0+(?!\d)", result.to_markdown())


def test_a14_json_round_trips_on_fixture(multi_tripped: MultiDiffResult) -> None:
    _assert_json_round_trip(multi_tripped)


def test_a14_json_round_trips_on_inferred_and_trade_cases(trade_result: MultiDiffResult) -> None:
    a, b = _inference_frames()
    _assert_json_round_trip(_multi(a, b, None))
    _assert_json_round_trip(trade_result)


def test_a14_no_negative_zero_when_deltas_vanish() -> None:
    a = _raw({"c1": _cell(timeout=0, violated=4), "c2": _cell(timeout=8, violated=0)})
    result = _multi(a, a.copy(), ["timeout", "violated"])
    for e in result.events:
        assert (result.by_event[e].cells["delta"] == 0.0).all()
    _assert_json_round_trip(result)


# ---------- A15: check ----------


def _assert_check(result: MultiDiffResult) -> None:
    # PF4 re-freeze (PF4.20, the library follows the screen; PF4.34): no event here has a
    # kind, so the default gate on worse is refused, and the gate reads the direction of the rows
    # that count for the verdict (Holm's): "higher" where it read "worse", "any" over both ways.
    with pytest.raises(DiffError):
        result.check()
    with pytest.raises(DiffError):
        result.check(fail_on="worse")
    rise_free = all(e.n_holm_higher == 0 for e in result.by_event.values())
    fall_free = all(e.n_holm_lower == 0 for e in result.by_event.values())
    assert result.check(fail_on="higher") is rise_free
    assert result.check(fail_on="lower") is fall_free
    assert result.check(fail_on="any") is (rise_free and fall_free)


def test_a15_check_on_fixture(multi_tripped: MultiDiffResult) -> None:
    _assert_check(multi_tripped)
    # PF4 re-freeze (PF4.20): "higher" where this read "worse" ("tripped" has no kind).
    assert multi_tripped.check(fail_on="higher") is True and multi_tripped.check(fail_on="any") is False


def test_a15_check_on_synthetic_cases(trade_result: MultiDiffResult, headline_case: MultiDiffResult) -> None:
    # PF4 re-freeze (PF4.20): every check below gates on "higher" where it gated on "worse"; no
    # event has a kind.
    _assert_check(trade_result)
    assert trade_result.check(fail_on="higher") is False and trade_result.check(fail_on="any") is False
    _assert_check(headline_case)
    assert headline_case.check(fail_on="higher") is False
    a = _raw({"c1": _cell(timeout=N), "c2": _cell(timeout=4)})
    b = _raw({"c1": _cell(timeout=0), "c2": _cell(timeout=4)})
    safer_only = _multi(a, b, ["timeout", "violated"])
    _assert_check(safer_only)
    assert safer_only.check(fail_on="higher") is True and safer_only.check(fail_on="any") is False
    null = _multi(a, a.copy(), ["timeout", "violated"])
    _assert_check(null)
    assert null.check(fail_on="higher") is True and null.check(fail_on="any") is True


# ---------- A16: logrank_bh is labelled cause-specific ----------


@pytest.mark.parametrize("method", METHODS)
def test_a16_cause_specific_iff_logrank(method: str) -> None:
    a = _raw({"c1": _cell(timeout=12, violated=4, t=2.0), "c2": _cell(timeout=2, violated=2, t=3.0)})
    b = _raw({"c1": _cell(timeout=6, violated=8, t=1.0), "c2": _cell(timeout=2, violated=2, t=3.0)})
    result = _multi(a, b, ["timeout", "violated"], method=method)
    expected = method == "logrank_bh"
    for e in result.events:
        assert result.by_event[e].cause_specific is expected, (method, e)
    assert ("cause-specific" in result.to_markdown()) is expected, method
    assert result.method == method


# ---------- A17: mcnemar_bh pairing ----------


def _dup_replicate_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    # Every row in cell c carries replicate_index 0, which the per-cell McNemar rejects
    # with its own NotPairable; the salt / manifest check must fire before that.
    a = _raw({"c": [("timeout", HORIZON, 0)] * 4 + [("completed", HORIZON, 0)] * 4})
    b = _raw({"c": [("timeout", HORIZON, 0)] * 2 + [("completed", HORIZON, 0)] * 6})
    return a, b


def test_a17_mcnemar_requires_matching_salts_before_testing() -> None:
    a, b = _dup_replicate_frames()
    with pytest.raises(NotPairable) as info:
        _multi(a, b, ["timeout"], method="mcnemar_bh", salt_a="s1", salt_b="s2")
    assert "duplicate" not in str(info.value).lower()


@pytest.mark.parametrize("which", ["a", "b", "both"])
def test_a17_mcnemar_requires_manifests_before_testing(which: str) -> None:
    a, b = _dup_replicate_frames()
    ma = None if which in ("a", "both") else _manifest("a")
    mb = None if which in ("b", "both") else _manifest("b")
    with pytest.raises(NotPairable) as info:
        multi_diff(a, b, events=["timeout"], method="mcnemar_bh", manifest_a=ma, manifest_b=mb)
    assert "duplicate" not in str(info.value).lower()


def test_a17_mcnemar_runs_when_paired() -> None:
    a = _raw({"c": _cell(timeout=12, violated=2)})
    b = _raw({"c": _cell(timeout=4, violated=6)})
    result = _multi(a, b, ["timeout", "violated"], method="mcnemar_bh")
    assert result.seed_identity_match is True and result.method == "mcnemar_bh"
    assert result.n_tests == 2


@pytest.mark.parametrize("method", ["fisher_bh", "logrank_bh"])
def test_a17_unpaired_methods_run_with_different_salts(method: str) -> None:
    a = _raw({"c": _cell(timeout=12, violated=2)})
    b = _raw({"c": _cell(timeout=4, violated=6)})
    result = _multi(a, b, ["timeout", "violated"], method=method, salt_a="s1", salt_b="s2")
    assert result.seed_identity_match is False
    assert _multi(a, b, ["timeout", "violated"], method=method, manifests=False).seed_identity_match is False


# ---------- A18: unit and horizon guards ----------


def test_a18_unit_mismatch_raises() -> None:
    a = _raw({"c": _cell(timeout=4)})
    with pytest.raises(UnitMismatch):
        _multi(a, a.copy(), ["timeout"], t_unit_b="seconds")


def test_a18_unit_mismatch_is_checked_before_any_event() -> None:
    a, b = _dup_replicate_frames()
    with pytest.raises(UnitMismatch):
        _multi(a, b, ["timeout"], method="mcnemar_bh", t_unit_b="seconds")


def test_a18_horizon_truncation_applies_once_to_both_runs() -> None:
    # A (horizon 5): a timeout at t=4 and a violation at t=4 both lie above the shared
    # horizon 3 and are re-censored; the rest sit at or below 3. B (horizon 3): nothing
    # above 3. Two events tested, but exactly two rows truncated, and neither re-censored
    # row counts as an event of any kind.
    a = _raw(
        {"c": [("timeout", 4.0), ("violated", 4.0), ("timeout", 3.0), ("violated", 2.0), ("completed", 3.0), ("completed", 1.0)]},
        horizon=5.0,
    )
    b = _raw(
        {"c": [("timeout", 3.0), ("violated", 3.0), ("completed", 3.0), ("completed", 2.0), ("completed", 1.0), ("completed", 3.0)]},
        horizon=3.0,
    )
    result = _multi(a, b, ["timeout", "violated"])
    assert result.horizon == 3.0
    assert result.truncated == 2
    timeout = result.by_event["timeout"].cells.iloc[0]
    violated = result.by_event["violated"].cells.iloc[0]
    assert timeout["n_a"] == 6 and timeout["events_a"] == 1 and timeout["events_b"] == 1
    assert violated["n_a"] == 6 and violated["events_a"] == 1 and violated["events_b"] == 1


def test_a18_no_truncation_when_horizons_match(multi_tripped: MultiDiffResult) -> None:
    assert multi_tripped.truncated == 0 and multi_tripped.horizon == HORIZON


# ---------- A19: determinism ----------


@settings(max_examples=25, deadline=None)
@given(pair=run_pair(max_cells=3))
def test_a19_multi_diff_is_deterministic_property(pair: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    a, b = pair
    first = _multi(a, b, ["timeout", "violated"])
    second = _multi(a.copy(), b.copy(), ["timeout", "violated"])
    _assert_same_multi(first, second)


@pytest.mark.parametrize("method", METHODS)
def test_a19_multi_diff_is_deterministic_per_method(method: str) -> None:
    a = _raw({"c1": _cell(timeout=12, violated=4, t=2.0), "c2": _cell(timeout=2, violated=2, t=3.0)})
    b = _raw({"c1": _cell(timeout=6, violated=8, t=1.0), "c2": _cell(timeout=2, violated=2, t=3.0)})
    first = _multi(a, b, ["timeout", "violated"], method=method)
    second = _multi(a.copy(), b.copy(), ["timeout", "violated"], method=method)
    _assert_same_multi(first, second)


def test_a19_multi_diff_is_deterministic_on_fixture(
    raw: dict[str, pd.DataFrame], manifests: dict[str, RunManifest], multi_tripped: MultiDiffResult
) -> None:
    _assert_same_multi(multi_tripped, _fixture_multi(raw, manifests, [EVENT]))


def test_a19_inference_is_deterministic() -> None:
    a, b = _inference_frames()
    _assert_same_multi(_multi(a, b, None), _multi(a.copy(), b.copy(), None))
    assert infer_events(a, b) == infer_events(a.copy(), b.copy())


# ---------- A20: errored rows never become events ----------


def test_a20_errored_rows_are_excluded_from_numerator_and_denominator() -> None:
    clean_a = {"c1": _cell(20, timeout=8, violated=4), "c2": _cell(20, timeout=2, violated=2)}
    clean_b = {"c1": _cell(20, timeout=2, violated=10), "c2": _cell(20, timeout=2, violated=2)}
    errored_a = {k: [*v, *[(None, 0.0)] * 5] for k, v in clean_a.items()}
    errored_b = {k: [*v, *[(None, 0.0)] * 3] for k, v in clean_b.items()}
    with_errors = _multi(_raw(errored_a), _raw(errored_b), ["timeout", "violated"])
    without = _multi(_raw(clean_a), _raw(clean_b), ["timeout", "violated"])
    for e in with_errors.events:
        cells = with_errors.by_event[e].cells
        assert (cells["n_a"] == 20).all() and (cells["n_b"] == 20).all()
    c1_timeout = with_errors.by_event["timeout"].cells.set_index("config_hash").loc[_hash("c1")]
    assert c1_timeout["events_a"] == 8 and c1_timeout["events_b"] == 2
    _assert_same_multi(with_errors, without)


def test_a20_errored_rows_are_not_an_inferred_event() -> None:
    a = _raw({"c": [*_cell(20, completed=12, timeout=8), *[(None, 0.0)] * 30]})
    b = _raw({"c": _cell(20, completed=12, timeout=8)})
    result = _multi(a, b, None)
    assert result.events == ("timeout",) and result.non_event == "completed"
    assert (result.by_event["timeout"].cells["n_a"] == 20).all()
