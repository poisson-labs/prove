"""A28 frozen tests: invariants G1-G22 of M14's agreement digest,
written before ``tree.agreement_digest``, ``TreeResult.agreement`` and the two renderers' digest
clauses exist, against ``03d7ed2`` (A24's build; ``src/poisson_prove/{tree,report,viewer,diff}.py``
are byte-identical to ``38e8df9``, measured).

**What closes.** C16: two 5-cell pairs over ``('fail', 'crash')`` with the same salt and the same
five configs, different outcome mixes, crossed, are accepted by both renderers at ``03d7ed2`` --
one root reading *rejected, p = 0.0033* beside the other's *not rejected, p = 0.90* -- and are
refused on all four crossings by a source carrying the digest's interface, without refusing any
tree grown beside its own diff (G2, G10, G11).

**Twenty-two invariants, not twenty.** G1-G20 were specified in advance. G21 and G22 are the knob
clause, taken as written: a second clause in each renderer comparing ``tree.root.method`` and
``tree.root.q`` to the diff's, with its own nameable message, after the digest clause. Measured
cost the spec did not list: ``test_s29_viewer.py``'s first W16 test rendered a ``mcnemar_bh`` tree
beside a ``fisher_bh`` diff to show a same-events tree is accepted; the update re-grows that tree
under a different ``seed`` instead, which keeps the clause's point (events and cells decide, knobs
the digest ignores do not) and no longer pins the behaviour the knob clause removes.

**The canonical form is the ``json.dumps`` one, and G17's reference is written from it.** The
first published ``b1423bc1...`` / ``1ac9386b...`` were measured on a prototype, which
joined rows with ``\\x1f`` and newlines rather than ``json.dumps`` -- measured here by re-running
that form: it reproduces those values, and the ``json.dumps`` form does not. G17 recomputes the
JSON form's digest in this file from the generated lattice pair's design counts
(``lattice.counts``), at K = 1 and K = 2, and requires both methods to carry it.

**The freeze commit is red here by construction.** On the update commit, before any source edit, the red set in this file is **fifteen**:
G1-G5, G7-G11, G13, G16, G17, G21 and G22. Every one reaches ``agreement_digest``,
``.agreement``, ``/4`` or a refusal that does not exist yet, inside a test body, so
``--collect-only`` is exact on the bare tree. **Green before and after, named so their green is
not read as evidence:** G6 (``omnibus`` and ``RootResult`` do not move), G12 (the five older
refusals and their messages -- a preservation clause, and the sole catch for mutant 11 all the
same) and G15 (``cli.py`` never mentions ``agreement``). The two-cell rule does not bind: one
environment, one cell.

**Fixture limits, stated rather than left to be rediscovered:**

- **The lattice pair** (``tests/lattice.py``) is one pair and cannot be crossed with anything; it
  guards G2, G6, G17's method half and every round trip, and nothing about C16.
- **The crossed pair P/Q** is the smallest shape that reproduces the measured hole; it says nothing
  about how a refusal reads on a 656-hash mismatch. **R**, four cells over the same events and salt,
  exists only so the arity clause has a same-events input to fire on (G12).
- **A27's vocabulary and hostile pairs** have disjoint ``task`` values and so disjoint hashes; they
  exercise the multiset clause (G12) and can never reach the digest clause. Their red or green says
  nothing about A28's guard, and G10's fixture is deliberately not them.
- **The holed pair** (five configs in arm a, four in arm b, plus an event nobody ran) is one shape
  of hole; it does not exercise a diff whose ``cells`` carry a hash the rebuild lacks.
- **A ``mcnemar_bh`` lattice pair** shows the digest is scheme-blind, not how far ``units`` and ``cells``
  can drift apart.

**Mutants, measured over the whole suite on copies of the shadow shim** (the planned
twelve plus 13 and 14 for the knob clause; control 1866 passed with W20's whole-file ``tree.py`` clause the
one expected red, present in every row and not counted): 1 viewer digest clause deleted -> G10, G13;
2 report digest clause deleted -> G11, G13; 3 ``_require_agreement`` stops raising -> G5, and S25's
O13, S26's F30 and S27's L24, which already pinned that refusal -- the spec's "G5 alone" holds in
this file only; 4 mint from ``cells`` instead of the rebuilt tuples -> survives by construction, as
predicted; 5 sort dropped -> every render refuses, 18 failures and 131 fixture errors; 6
``AGREEMENT_SCHEMA`` dropped -> G16, G17; 7 separator join instead of ``json.dumps`` -> G16, G17,
**not** the survivor the spec predicted, because G17 pins values of the JSON form; 8 ``SCHEMA``
left at ``/3`` -> G9 and the seven schema literals of M13, S21 and S29; 9 field carried but not
serialised -> G7, G8, G9, L10, W12; 10 digest compared to itself -> G10, G11, G13; 11 digest clause
before the multiset clause -> G12 and W16, nothing else; 12 digest widened with ``multi.method`` ->
G17, G21, G22; 13 viewer knob clause deleted -> G21 alone; 14 report knob clause deleted -> G22
alone.

Restated rather than imported, as every frozen test file's helpers are: the store builders and
the two-value cells.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import re
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import poisson_prove
import lattice
from poisson_prove import diff as diff_mod
from poisson_prove import report as report_mod
from poisson_prove import tree as tree_mod
from poisson_prove.diff import MultiDiffResult, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import MultiReport, ReportSpec, build_multi_report
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.tree import RootResult, TreeError, TreeResult, omnibus
from poisson_prove.tree import tree as grow_tree

PACKAGE = Path(poisson_prove.__file__).resolve().parent
CLI_SOURCE = PACKAGE / "cli.py"
LATTICE_ROOT = lattice.root()

# ---------- the literals ----------

#: G9. The schema in force.
# LS update: /5 retires with the ``summary`` key.
SCHEMA = "poisson-prove.viewpair/7"
#: G4, G5. The four episode counts the agreement digest is minted over, per (event, cell).
REBUILD_COLUMNS = ("n_a", "n_b", "events_a", "events_b")
#: G7. ``TreeResult``'s six fields in order and ``to_json()``'s six keys in the same order.
TREE_RESULT_FIELDS = ("root", "grouping", "fault_lines", "leaves", "bound", "agreement")
#: G17. The tag inside the hashed payload; never a sibling key.
AGREEMENT_SCHEMA = "poisson-prove.agreement/1"
#: G17. The schema string the 0.0.1 builds hashed behind, before the PF0 freeze renamed it.
OLD_AGREEMENT_SCHEMA = "proofload.agreement/1"
# The PF0 freeze kept the old fixture's 0.0.1 digests beside its renamed ones; they were never
# asserted in this file (a dead digest) and went with that fixture. G17 now checks the digest the
# trees carry is not the old string's, from the reference. Lattice port, 2026-10-25.


def reference_agreement(events: Sequence[str], schema: str = AGREEMENT_SCHEMA) -> str:
    """G17's reference, written from the canonical form and not from ``tree.py``: one line per
    ``(event, cell)`` of the lattice pair, ``[event, config_hash, n_a, n_b, events_a, events_b]``
    from the design's counts (``lattice.counts``), the lines sorted, the pair ``[schema, lines]``
    as compact ASCII JSON, sha256, lowercase hex. Nothing about the method enters."""
    lines = sorted(
        [str(event), r["config_hash"], int(r["n_a"]), int(r["n_b"]), int(r["events_a"]), int(r["events_b"])]
        for event in events
        for r in lattice.counts(event)
    )
    payload = json.dumps([schema, lines], separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


HEX64 = re.compile(r"^[0-9a-f]{64}$")
#: G6. ``omnibus``'s signature as ``test_s27_leaves.py`` pins it, restated.
OMNIBUS_SIGNATURE = "(a: 'pd.DataFrame', b: 'pd.DataFrame', multi: 'MultiDiffResult', *, n_permutations: 'int' = 4000, seed: 'int' = 0) -> 'RootResult'"
#: G12. The five pre-existing refusal messages, as substrings, so a digest clause placed ahead of
#: them (mutant 11) or a reworded clause is noticed. The digest clause's own message must not
#: carry any of these, because at that point no cell and no count differs.
VIEWER_EVENTS_MESSAGE = "the tree is over events"
VIEWER_ARITY_MESSAGE = "cell-event units"
VIEWER_MULTISET_MESSAGE = "the tree's cells are not this pair's"
REPORT_EVENTS_MESSAGE = "the tree is over events"
REPORT_ARITY_MESSAGE = "cells x"
#: G10, G11, G21, G22. What the two new clauses must say, by one word each.
DIGEST_WORD = "digest"

# ---------- the store builders (S27's and S29's, restated) ----------

NON_EVENTS = frozenset({"ok"})
EVENT_T = 2.0
HORIZON = 5.0
SALT = "a28-salt"
TYPES = {"task": "categorical", "temp": "continuous"}
EVENTS = ("fail", "crash")
N = 32
PERMUTATIONS = 300
SEED = 0
Q = 0.05
OTHER_Q = 0.01
#: A27's two crossed pairs, restated: two ``task`` values each, disjoint between the pairs.
VOCABULARY_VALUES = ("given the root", "where it broke")
HOSTILE = "".join(["<", "/script><img src=x onerror=", chr(34), "alert(1)", chr(34), ">&", chr(34)])
HOSTILE_TABLE = "".join(["<", "/table><script>alert(1)</script>&", chr(34)])
HOSTILE_VALUES = (HOSTILE, HOSTILE_TABLE)
NEVER_RAN = "never_happened"


def manifest(run_id: str, salt: str, axis_types: Mapping[str, str]) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types), backend="synthetic", environment={"note": "built by these tests"},  # type: ignore[arg-type]
    )


def write_run(store: Store, run_id: str, *, salt: str, axis_types: Mapping[str, str], cells: Mapping[tuple[tuple[str, Any], ...], Sequence[str]]) -> None:
    """A complete synthetic run over multi-key configs, one episode per outcome, through the
    store's own writer."""
    store.create_run(manifest(run_id, salt, axis_types))
    records = []
    for index, (key, outcomes) in enumerate(cells.items()):
        for k, outcome in enumerate(outcomes):
            t = HORIZON if outcome in NON_EVENTS else EVENT_T
            records.append(EpisodeRecord.from_episode(
                Episode(outcome=outcome, t=t, horizon=HORIZON), run_id=run_id, config=dict(key), seed=1000 * index + k,
                replicate_index=k, wall_time=0.0,
            ))
    store.append(run_id, records)
    store.mark_complete(run_id)


def crossed_cells(n_fail_a: int, n_fail_b: int, n_crash: int, n_cells: int = 5) -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """The crossed shape: identical ``(task, temp)`` configs in every pair, only the mix varies."""
    a: dict[Any, list[str]] = {}
    b: dict[Any, list[str]] = {}
    for i in range(n_cells):
        key = (("task", f"t{i}"), ("temp", 0.0))
        a[key] = ["fail"] * n_fail_a + ["crash"] * n_crash + ["ok"] * (N - n_fail_a - n_crash)
        b[key] = ["fail"] * n_fail_b + ["crash"] * n_crash + ["ok"] * (N - n_fail_b - n_crash)
    return a, b


def two_value_cells(values: Sequence[str], moved: bool) -> dict[Any, list[str]]:
    return {(("task", v), ("temp", 0.0)): (["fail"] * 8 if moved else ["ok"] * 8) for v in values}


def holed_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """Five configs in arm a, four in arm b: ``common`` and ``cells`` are the four-cell
    intersection and ``coverage`` carries the fifth."""
    a = {(("task", f"t{i}"), ("temp", 0.0)): ["fail"] * 4 + ["ok"] * 12 for i in range(5)}
    b = {(("task", f"t{i}"), ("temp", 0.0)): ["fail"] * 8 + ["ok"] * 8 for i in range(4)}
    return a, b


@pytest.fixture(scope="module")
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("a28-synth")
    store = Store(root)
    pa, pb = crossed_cells(4, 20, 2)
    qa, qb = crossed_cells(6, 7, 3)
    ra, rb = crossed_cells(4, 20, 2, n_cells=4)
    for run_id, cells in (("p-a", pa), ("p-b", pb), ("q-a", qa), ("q-b", qb), ("r-a", ra), ("r-b", rb)):
        write_run(store, run_id, salt=SALT, axis_types=TYPES, cells=cells)
    ha, hb = holed_cells()
    write_run(store, "h-a", salt=SALT, axis_types=TYPES, cells=ha)
    write_run(store, "h-b", salt=SALT, axis_types=TYPES, cells=hb)
    write_run(store, "vocab-a", salt=SALT, axis_types=TYPES, cells=two_value_cells(VOCABULARY_VALUES, False))
    write_run(store, "vocab-b", salt=SALT, axis_types=TYPES, cells=two_value_cells(VOCABULARY_VALUES, True))
    write_run(store, "hostile-a", salt=SALT, axis_types=TYPES, cells=two_value_cells(HOSTILE_VALUES, False))
    write_run(store, "hostile-b", salt=SALT, axis_types=TYPES, cells=two_value_cells(HOSTILE_VALUES, True))
    return root


@dataclasses.dataclass(frozen=True)
class Grown:
    name: str
    root: Path
    a: str
    b: str
    frames: tuple[pd.DataFrame, pd.DataFrame]
    manifests: tuple[RunManifest, RunManifest]
    multi: MultiDiffResult
    result: Any

    @property
    def store(self) -> Store:
        return Store(self.root)


_GROWN: dict[tuple[Any, ...], Grown] = {}


def grown(name: str, root: Path, a: str, b: str, *, events: Sequence[str] = EVENTS, method: str = "fisher_bh", q: float = Q, **knobs: Any) -> Grown:
    """``(multi, tree)`` on a stored pair the way the CLI reaches them, cached; the frames read
    with ``meta=False`` and the tree at 300 permutations unless a knob says otherwise."""
    key = (name, str(root), a, b, tuple(events), method, q, tuple(sorted(knobs.items())))
    if key not in _GROWN:
        store = Store(root)
        fa, fb = store.read(a, meta=False), store.read(b, meta=False)
        ma, mb = store.manifest(a), store.manifest(b)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
            multi = multi_diff(fa, fb, events=list(events), method=method, q=q, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]
        options = {"n_permutations": PERMUTATIONS, "seed": SEED, **knobs}
        result = grow_tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, **options)
        _GROWN[key] = Grown(name, root, a, b, (fa, fb), (ma, mb), multi, result)
    return _GROWN[key]


@pytest.fixture(scope="module")
def crossed(synth_root: Path) -> dict[str, Grown]:
    return {
        "P": grown("P", synth_root, "p-a", "p-b"),
        "Q": grown("Q", synth_root, "q-a", "q-b"),
        "R": grown("R", synth_root, "r-a", "r-b"),
    }


@pytest.fixture(scope="module")
def every_fixture(synth_root: Path, crossed: dict[str, Grown]) -> list[Grown]:
    """The fixture set: the lattice pair under both schemes at K = 1 and K = 2, the crossed pairs, the
    holed pair with an event nobody ran, and A27's two disjoint pairs."""
    return [
        grown("lattice", LATTICE_ROOT, lattice.RUN_A, lattice.RUN_B, events=(lattice.EVENT,)),
        grown("lattice-mcnemar", LATTICE_ROOT, lattice.RUN_A, lattice.RUN_B, events=(lattice.EVENT,), method="mcnemar_bh"),
        grown("lattice-two", LATTICE_ROOT, lattice.RUN_A, lattice.RUN_B, events=(lattice.EVENT, lattice.OTHER)),
        grown("lattice-two-mcnemar", LATTICE_ROOT, lattice.RUN_A, lattice.RUN_B, events=(lattice.EVENT, lattice.OTHER), method="mcnemar_bh"),
        *crossed.values(),
        grown("holed", synth_root, "h-a", "h-b", events=("fail", NEVER_RAN)),
        grown("vocab", synth_root, "vocab-a", "vocab-b", events=("fail",)),
        grown("hostile", synth_root, "hostile-a", "hostile-b", events=("fail",)),
    ]


def viewer() -> Any:
    """``poisson_prove.viewer``, imported on demand so the changed surface is reached inside bodies."""
    import poisson_prove.viewer as module

    return module


def spec_for(g: Grown) -> ReportSpec:
    x, y = (lattice.X, lattice.Y) if g.root == LATTICE_ROOT else ("task", "temp")
    return ReportSpec(title=f"{g.a} vs {g.b}", x_axis=x, y_axis=y, fixed={})


def structure_for(g: Grown, result: Any) -> dict[str, Any]:
    m = viewer()
    store = g.store
    report = build_multi_report(g.multi, spec_for(g), manifests=g.manifests, tree=result)
    return m.build_structure(  # type: ignore[no-any-return]
        report, g.multi, tree=result, manifest_a=g.manifests[0], manifest_b=g.manifests[1], rows_a=store.count(g.a), rows_b=store.count(g.b),
        tally_a=store.tally(g.a), tally_b=store.tally(g.b), store_root=str(g.root),
    )


def structure_kwargs(g: Grown) -> dict[str, Any]:
    store = g.store
    return dict(
        manifest_a=g.manifests[0], manifest_b=g.manifests[1], rows_a=store.count(g.a), rows_b=store.count(g.b),
        tally_a=store.tally(g.a), tally_b=store.tally(g.b), store_root=str(g.root),
    )


def report_for(g: Grown) -> MultiReport:
    return build_multi_report(g.multi, spec_for(g), manifests=g.manifests)


def hashes_of(g: Grown) -> set[str]:
    return {str(h) for e in g.multi.events for h in g.multi.by_event[e].cells["config_hash"]}


def with_cells(multi: MultiDiffResult, event: str, cells: pd.DataFrame) -> MultiDiffResult:
    return replace(multi, by_event={**multi.by_event, event: replace(multi.by_event[event], cells=cells)})


def same_family_shape(diff: Grown, other: Grown) -> None:
    """The three older clauses cannot be what refuses: events equal, arity equal, multiset equal."""
    from collections import Counter

    assert tuple(other.result.root.events) == tuple(diff.multi.events)
    assert len(other.result.root.units) == diff.multi.n_tests == other.result.root.n_cells * len(diff.multi.events)
    carried = Counter((str(e), str(h)) for e, h in zip(other.result.root.units["event"], other.result.root.units["config_hash"], strict=True))
    tested = Counter((str(e), str(h)) for e in diff.multi.events for h in diff.multi.by_event[e].cells["config_hash"])
    assert carried == tested


# ---------- ast helpers (restated; never imported across test modules) ----------


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


# ---------- G1-G4: the digest itself ----------


def test_g1_the_digest_and_the_field_are_64_hex_lowercase_strings(every_fixture: list[Grown]) -> None:
    for g in every_fixture:
        recomputed = tree_mod.agreement_digest(g.multi)
        assert isinstance(recomputed, str) and HEX64.match(recomputed), (g.name, recomputed)
        assert isinstance(g.result.agreement, str) and HEX64.match(g.result.agreement), g.name


def test_g2_every_tree_grown_beside_its_own_diff_carries_the_digest_the_diff_recomputes(every_fixture: list[Grown]) -> None:
    """The invariant that makes the guard usable: over the lattice pair under both schemes at K = 1 and 2, the
    three crossed pairs, the holed pair with an event nobody ran, and A27's two pairs -- and the
    holed pair's shape is asserted, so its green is the over-refusal check it is meant to be."""
    for g in every_fixture:
        assert g.result.agreement == tree_mod.agreement_digest(g.multi), g.name
    holed = next(g for g in every_fixture if g.name == "holed")
    assert holed.result.root.n_cells == 4 and holed.multi.n_tests == 8
    assert holed.multi.coverage is not None and len(holed.multi.coverage) == 5
    assert NEVER_RAN in holed.multi.events


def test_g3_the_digest_is_a_function_of_the_multiset_and_not_of_row_or_event_order(every_fixture: list[Grown]) -> None:
    two_event = [g for g in every_fixture if len(g.multi.events) == 2]
    assert two_event
    for g in two_event:
        expected = tree_mod.agreement_digest(g.multi)
        shuffled = g.multi
        for k, event in enumerate(g.multi.events):
            cells = g.multi.by_event[event].cells
            shuffled = with_cells(shuffled, event, cells.sample(frac=1, random_state=7 + k).reset_index(drop=True))
            assert not shuffled.by_event[event].cells["config_hash"].equals(cells["config_hash"]) or len(cells) < 2, g.name
        assert tree_mod.agreement_digest(shuffled) == expected, g.name
        reversed_events = replace(g.multi, events=tuple(reversed(g.multi.events)))
        assert tree_mod.agreement_digest(reversed_events) == expected, g.name


def test_g4_changing_any_one_rebuild_integer_in_any_one_cell_of_any_one_event_changes_the_digest(crossed: dict[str, Grown]) -> None:
    p = crossed["P"]
    expected = tree_mod.agreement_digest(p.multi)
    moved: set[str] = set()
    for event in p.multi.events:
        cells = p.multi.by_event[event].cells
        for index in range(len(cells)):
            for column in REBUILD_COLUMNS:
                bumped = cells.copy()
                bumped.loc[bumped.index[index], column] = int(bumped.loc[bumped.index[index], column]) + 1
                digest = tree_mod.agreement_digest(with_cells(p.multi, event, bumped))
                assert digest != expected, (event, index, column)
                moved.add(digest)
    assert len(moved) == len(p.multi.events) * 5 * len(REBUILD_COLUMNS)


# ---------- G5, G6: the mint site, and what does not move ----------


def test_g5_tree_carries_the_digest_and_still_raises_on_both_paths_with_the_messages_unchanged(crossed: dict[str, Grown]) -> None:
    """Sole catch for mutant 3. ``tree`` carries the digest the diff recomputes, and its two
    ``TreeError`` paths and their messages are pinned by substring: a cell rebuilt but absent from
    an event's family, and a rebuild that disagrees."""
    p = crossed["P"]
    fa, fb = (frame.copy() for frame in p.frames)
    options = {"manifest_a": p.manifests[0], "manifest_b": p.manifests[1], "n_permutations": PERMUTATIONS, "seed": SEED}
    again = grow_tree(fa, fb, p.multi, **options)
    assert isinstance(again.agreement, str) and again.agreement == tree_mod.agreement_digest(p.multi) == p.result.agreement
    event = p.multi.events[0]
    cells = p.multi.by_event[event].cells
    absent = with_cells(p.multi, event, cells.iloc[1:].reset_index(drop=True))
    with pytest.raises(TreeError) as info:
        grow_tree(fa, fb, absent, **options)
    message = str(info.value)
    assert f"rebuilt from the frames but absent from the {event!r} family" in message, message
    assert "the frames are not the pair this diff was computed from" in message
    bumped = cells.copy()
    bumped.loc[bumped.index[0], "events_a"] = int(bumped.loc[bumped.index[0], "events_a"]) + 1
    with pytest.raises(TreeError) as info:
        grow_tree(fa, fb, with_cells(p.multi, event, bumped), **options)
    message = str(info.value)
    assert f"the rebuild disagrees with the diff on event {event!r}" in message, message
    assert str(REBUILD_COLUMNS) in message and "on cells; the frames are not the pair this diff was computed from" in message


def test_g6_omnibus_is_untouched_and_root_result_carries_no_digest(crossed: dict[str, Grown]) -> None:
    """Green before and after: the signature literal, the return type, the
    byte-equality of ``tree(...).root`` with ``omnibus(...)`` on the same knobs, and no digest on
    ``RootResult``, in either its fields or its payload."""
    p = crossed["P"]
    assert str(inspect.signature(omnibus)) == OMNIBUS_SIGNATURE
    root = omnibus(*p.frames, p.multi, n_permutations=PERMUTATIONS, seed=SEED)
    assert isinstance(root, RootResult)
    assert json.dumps(root.to_json(), sort_keys=True) == json.dumps(p.result.root.to_json(), sort_keys=True)
    assert "agreement" not in {field.name for field in dataclasses.fields(RootResult)}
    assert "agreement" not in root.to_json()


# ---------- G7-G9: the payload ----------


def test_g7_tree_result_has_exactly_six_fields_in_order_and_to_json_six_keys_with_agreement_last(every_fixture: list[Grown]) -> None:
    assert [field.name for field in dataclasses.fields(TreeResult)] == list(TREE_RESULT_FIELDS)
    for g in every_fixture:
        payload = g.result.to_json()
        assert list(payload) == list(TREE_RESULT_FIELDS), (g.name, list(payload))
        assert isinstance(payload["agreement"], str) and payload["agreement"] == g.result.agreement


def test_g8_the_payload_survives_a_json_round_trip_on_every_fixture(every_fixture: list[Grown]) -> None:
    for g in every_fixture:
        text = json.dumps(g.result.to_json(), allow_nan=False)
        assert json.loads(text)["agreement"] == g.result.agreement, g.name
        assert list(json.loads(text)) == list(TREE_RESULT_FIELDS), g.name


def test_g9_the_structure_carries_the_schema_and_the_trees_agreement_and_renders(crossed: dict[str, Grown]) -> None:
    m = viewer()
    assert m.SCHEMA == SCHEMA
    p = crossed["P"]
    structure = structure_for(p, p.result)
    assert structure["schema"] == SCHEMA
    assert structure["tree"]["agreement"] == p.result.agreement
    assert isinstance(m.render_html(structure), str)


# ---------- G10-G13: the two renderers ----------


def test_g10_the_viewer_refuses_c16s_crossed_tree_from_the_digest_clause_naming_neither_a_cell_nor_a_count(crossed: dict[str, Grown]) -> None:
    """Sole catch for mutant 1. Both crossings; the three older clauses are shown unable to fire
    first (same events, same arity, same multiset), and the message names no hash of either pair
    and none of the three older clauses' phrases, because nothing they could name differs."""
    m = viewer()
    p, q = crossed["P"], crossed["Q"]
    assert hashes_of(p) == hashes_of(q) and p.result.root.rejects != q.result.root.rejects
    for diff, other in ((p, q), (q, p)):
        same_family_shape(diff, other)
        with pytest.raises(m.ViewerError) as info:
            m.build_structure(report_for(diff), diff.multi, tree=other.result, **structure_kwargs(diff))
        message = str(info.value)
        assert DIGEST_WORD in message.lower(), message
        assert not any(h in message for h in hashes_of(p)), message
        for phrase in (VIEWER_EVENTS_MESSAGE, VIEWER_ARITY_MESSAGE, VIEWER_MULTISET_MESSAGE):
            assert phrase not in message, (phrase, message)
        assert not re.search(r"\d+ cell", message) and "tests" not in message, message
    assert isinstance(structure_for(p, p.result), dict) and isinstance(structure_for(q, q.result), dict)


def test_g11_the_report_refuses_c16s_crossed_tree_with_comparison_mismatch(crossed: dict[str, Grown]) -> None:
    """Sole catch for mutant 2."""
    p, q = crossed["P"], crossed["Q"]
    for diff, other in ((p, q), (q, p)):
        same_family_shape(diff, other)
        with pytest.raises(report_mod.ComparisonMismatch) as info:
            build_multi_report(diff.multi, spec_for(diff), manifests=diff.manifests, tree=other.result)
        assert isinstance(info.value, report_mod.ReportError)
        message = str(info.value)
        assert DIGEST_WORD in message.lower() and not any(h in message for h in hashes_of(p)), message
        for phrase in (REPORT_EVENTS_MESSAGE, REPORT_ARITY_MESSAGE):
            assert phrase not in message, (phrase, message)
        assert build_multi_report(diff.multi, spec_for(diff), manifests=diff.manifests, tree=diff.result).tree is diff.result


def test_g12_the_five_pre_existing_refusals_fire_first_with_their_messages_unchanged(crossed: dict[str, Grown], every_fixture: list[Grown]) -> None:
    """Sole catch for mutant 11 (the digest clause ahead of the multiset clause), and the reason the
    digest is an addition rather than a replacement. The viewer's events, arity and
    multiset clauses and the report's events and arity clauses each fire on the input that fired
    them before, with their vocabulary, and none of those refusals mentions the digest. The
    multiset input is A27's crossing, whose hashes are disjoint by construction."""
    m = viewer()
    by_name = {g.name: g for g in every_fixture}
    p, r = crossed["P"], crossed["R"]
    single, two = by_name["lattice"], by_name["lattice-two"]
    vocab, hostile = by_name["vocab"], by_name["hostile"]
    assert not (hashes_of(vocab) & hashes_of(hostile)) and vocab.multi.n_tests == hostile.multi.n_tests == len(hostile.result.root.units)
    assert r.result.root.n_cells == 4 and p.multi.n_tests == 10 and tuple(r.result.root.events) == tuple(p.multi.events)

    def viewer_refusal(diff: Grown, other: Grown, phrase: str) -> str:
        with pytest.raises(m.ViewerError) as info:
            m.build_structure(report_for(diff), diff.multi, tree=other.result, **structure_kwargs(diff))
        message = str(info.value)
        assert phrase in message and DIGEST_WORD not in message.lower(), (phrase, message)
        return message

    def report_refusal(diff: Grown, other: Grown, phrase: str) -> str:
        with pytest.raises(report_mod.ComparisonMismatch) as info:
            build_multi_report(diff.multi, spec_for(diff), manifests=diff.manifests, tree=other.result)
        message = str(info.value)
        assert phrase in message and DIGEST_WORD not in message.lower(), (phrase, message)
        return message

    viewer_refusal(single, two, VIEWER_EVENTS_MESSAGE)
    message = viewer_refusal(p, r, VIEWER_ARITY_MESSAGE)
    assert "8 cell-event units" in message and "10 tests" in message, message
    message = viewer_refusal(vocab, hostile, VIEWER_MULTISET_MESSAGE)
    assert any(h in message for h in hashes_of(hostile)), message
    report_refusal(single, two, REPORT_EVENTS_MESSAGE)
    message = report_refusal(p, r, REPORT_ARITY_MESSAGE)
    assert "4 cells x 2 events" in message and "10 tests" in message, message


# ---------- G15: the CLI ----------


def test_g15_cli_neither_binds_nor_reads_agreement() -> None:
    """``cli.py`` serialises ``nested.to_json()`` wholesale and reads no attribute named
    ``agreement`` and binds no such name."""
    cli = parsed(CLI_SOURCE)
    assert [n.lineno for n in ast.walk(cli) if isinstance(n, ast.Attribute) and n.attr == "agreement"] == []
    assert [n.lineno for n in ast.walk(cli) if isinstance(n, ast.Name) and n.id == "agreement"] == []


# ---------- G17: not a config hash, not a method hash ----------


def test_g17_a_digest_is_not_a_config_hash_and_not_a_method_hash(crossed: dict[str, Grown], every_fixture: list[Grown]) -> None:
    """The discrimination half on C16's fixture (identical ``config_hash`` sets, different
    counts, different digests) and the method-equality half on the lattice pair at K = 1 and K = 2:
    both methods carry the one digest this file's reference recomputes from the design's counts in
    the canonical form, so a later change that makes the form scheme-sensitive -- or drops the
    schema tag (mutant 6), or widens it with ``multi.method`` (mutant 12), or changes the
    serialiser (mutant 7) -- is caught rather than welcomed. The digest is not the one the 0.0.1
    schema string gives."""
    p, q = crossed["P"], crossed["Q"]
    assert hashes_of(p) == hashes_of(q)
    assert p.result.agreement != q.result.agreement
    by_name = {g.name: g for g in every_fixture}
    for k, fisher, mcnemar in ((1, "lattice", "lattice-mcnemar"), (2, "lattice-two", "lattice-two-mcnemar")):
        events = (lattice.EVENT,) if k == 1 else (lattice.EVENT, lattice.OTHER)
        expected = reference_agreement(events)
        assert by_name[fisher].result.agreement != reference_agreement(events, OLD_AGREEMENT_SCHEMA), k
        assert tuple(by_name[fisher].multi.events) == tuple(by_name[mcnemar].multi.events) == events, k
        assert by_name[fisher].multi.method == "fisher_bh" and by_name[mcnemar].multi.method == "mcnemar_bh"
        assert by_name[fisher].result.root.scheme != by_name[mcnemar].result.root.scheme
        assert by_name[fisher].result.agreement == by_name[mcnemar].result.agreement == expected, k
        assert tree_mod.agreement_digest(by_name[mcnemar].multi) == expected


# ---------- G21, G22: the knob clause ----------


def test_g21_the_viewer_refuses_a_tree_grown_under_another_method_or_q_naming_both_values(synth_root: Path, crossed: dict[str, Grown]) -> None:
    """Sole catch for mutant 13. The digest is scheme-blind and q-blind by construction, so a tree
    grown under ``mcnemar_bh`` or at ``q = 0.01`` passes the digest clause beside this pair's
    ``fisher_bh`` diff at ``q = 0.05`` -- asserted first -- and the knob clause is what refuses,
    naming both values. Not the digest's message: nothing the digest covers differs."""
    m = viewer()
    p = crossed["P"]
    other_method = grown("P-mcnemar", synth_root, "p-a", "p-b", method="mcnemar_bh")
    other_q = grown("P-q", synth_root, "p-a", "p-b", q=OTHER_Q)
    for other, names in ((other_method, ("mcnemar_bh", "fisher_bh")), (other_q, (f"{OTHER_Q:g}", f"{Q:g}"))):
        assert other.result.agreement == p.result.agreement == tree_mod.agreement_digest(p.multi)
        with pytest.raises(m.ViewerError) as info:
            m.build_structure(report_for(p), p.multi, tree=other.result, **structure_kwargs(p))
        message = str(info.value)
        assert all(name in message for name in names) and DIGEST_WORD not in message.lower(), (names, message)


def test_g22_the_report_refuses_a_tree_grown_under_another_method_or_q_naming_both_values(synth_root: Path, crossed: dict[str, Grown]) -> None:
    """Sole catch for mutant 14."""
    p = crossed["P"]
    other_method = grown("P-mcnemar", synth_root, "p-a", "p-b", method="mcnemar_bh")
    other_q = grown("P-q", synth_root, "p-a", "p-b", q=OTHER_Q)
    for other, names in ((other_method, ("mcnemar_bh", "fisher_bh")), (other_q, (f"{OTHER_Q:g}", f"{Q:g}"))):
        assert other.result.agreement == p.result.agreement
        with pytest.raises(report_mod.ComparisonMismatch) as info:
            build_multi_report(p.multi, spec_for(p), manifests=p.manifests, tree=other.result)
        message = str(info.value)
        assert all(name in message for name in names) and DIGEST_WORD not in message.lower(), (names, message)
