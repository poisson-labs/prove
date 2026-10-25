"""M4 read-amendment oracle: invariants R1-R9 of the M4 Store (read amendment) spec, written
before ``Store.read(meta=, keys=)`` and ``Store.count`` exist.

Stores are written under ``tmp_path`` in the M4 oracle's ``_rec``/``_manifest`` shape; the CLI
is driven in-process through ``cli.main`` with ``StringIO`` streams, as the M10 oracle does; the
golden reads the generated lattice pair (``tests/lattice.py``) through the ``lattice_store``
conftest fixture.

The numbers in the spec's section 1 (a duration, a byte count, a row count) are the motivation
and never an assertion: nothing here measures a duration or a byte count. What this file asserts is which
paths decode ``meta``, and the poisoned store is how it knows. A poisoned store is a run written
through ``Store.append`` whose part files were rewritten in place with the string ``not json``
in the ``meta`` cells of chosen rows, each part keeping its own schema. On such a store the
default read raises, and every path that never decodes ``meta`` reads it exactly as it reads
the intact twin.

Two facts a builder should know before the shim hits them:

- ``keys=[]`` must short-circuit before the reader: pyarrow raises ``ArrowTypeError`` on an
  empty ``in`` list (verified 2026-09-05 against the venv's pyarrow). The explicit empty-keys
  tests exist because of that.
- The ``config_hash`` half of ``keys`` is pushed to the reader and the pair is masked after it.
  Two replicates of one cell share a hash, so the mock-agent run for R6 is built so that cells
  mix outcomes: a poisoned replicate sits in the same part, under the same hash, as a printed
  one, and only the printed one may be decoded.
"""

from __future__ import annotations

import inspect
import json
import re
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import poisson_prove.cli as cli
import poisson_prove.store as store_module
from poisson_prove.episode import Episode
from poisson_prove.examples.mock_agent import rollout
from poisson_prove.executor import plan, run_local
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store, StoreError, config_hash

import lattice

ROOT = Path(__file__).resolve().parents[1]
LATTICE_ROOT = lattice.root()
LATTICE_RUNS = (lattice.RUN_A, lattice.RUN_B)
LATTICE_ROWS = 2_304
LATTICE_TOTAL_ROWS = 4_608  # the two generated runs together

THIRTEEN = [
    "run_id", "config_hash", "config", "seed", "replicate_index", "outcome", "t", "horizon",
    "confidence", "meta", "error", "wall_time", "backend_meta",
]
ELEVEN = [c for c in THIRTEEN if c not in ("meta", "backend_meta")]
# PF4 re-freeze (reading R5): the store copies a rollout's case id into its own nullable string
# column, appended after trace_obs on disk, and every read returns it last (null for older parts), so
# a read frame is the thirteen columns plus case_id and a narrow read the eleven plus case_id.
FRAME = THIRTEEN + ["case_id"]
NARROW = ELEVEN + ["case_id"]
JSON_COLUMNS = ("config", "meta", "backend_meta")

POISON = "not json"
MOCK_ROLLOUT = "poisson_prove.examples.mock_agent:rollout"
MOCK_SALT = "m4-read-oracle"
SNIPPET_MARKER = "# reproduce one episode"
STEP_LINE_RE = re.compile(r"^\s*\d+(?:\t[^\t]*){8}$")  # the M10 oracle's I15 regex, verbatim (nine columns since A8a)

PUBLIC_STORE_METHODS = {
    "create_run", "manifest", "mark_complete", "runs", "append", "read", "missing", "count",
    "tally",
}
PUBLIC_STORE_SYMBOLS = {
    "StoreError", "SchemaMismatch", "DuplicateEpisode", "MetaNotSerializable", "InvalidConfig",
    "RunManifest", "EpisodeRecord", "Store", "config_hash", "RunTally",
}

# The keyed run: four cells x three replicates over three parts, appended out of key order,
# with one errored row. Its key set is computable at import time, which is what lets the R3
# property draw from it.
KEYED_RUN = "keyed"
KEYED_CELLS: tuple[dict[str, Any], ...] = (
    {"f": 0.1}, {"f": 0.5}, {"f": 0.9}, {"f": 0.5, "g": "x"},
)
KEYED_REPS = 3
ERRORED_KEY = (3, 2)  # (cell index, replicate) of the one errored row
PRESENT_KEYS = [(config_hash(cfg), k) for cfg in KEYED_CELLS for k in range(KEYED_REPS)]
ABSENT_KEYS = [
    (config_hash({"f": 123.0}), 0),  # a hash no row carries
    (PRESENT_KEYS[0][0], KEYED_REPS + 5),  # a present hash with an absent replicate index
    ("0" * 16, 0),
]
KEY_POOL = PRESENT_KEYS + ABSENT_KEYS

# The twins for R5: two synthetic runs, same salt, built so that check exits 0 with one safer
# cell and no worse one.
TWIN_RUNS = ("syn-a", "syn-b")
TWIN_N = 16

# The mock-agent run for R6: two tasks x two fail rates x six replicates in parts of five, so
# that cells mix outcomes and a poisoned replicate shares a part and a hash with a printed one.
MOCK_CONFIGS = [
    {"task_id": task, "tool_fail_rate": rate}
    for task in ("search", "checkout")
    for rate in (0.45, 0.5)
]
MOCK_REPLICATES = 6
MOCK_BATCH = 5


# ---------- helpers: the M4 oracle's record shape ----------


def _manifest(run_id: str = "r1", **kw: Any) -> RunManifest:
    base: dict[str, Any] = dict(
        run_id=run_id, target_id="policy@abc123", t_unit="steps", run_salt="salt",
        axis_types={"friction": "continuous"}, backend="local", environment={"python": "3.11"},
    )
    base.update(kw)
    return RunManifest(**base)


def _rec(
    run_id: str = "r1",
    cfg: dict[str, Any] | None = None,
    seed: int = 0,
    rep: int = 0,
    outcome: str = "fell",
    t: float = 3.0,
    horizon: float = 10.0,
    confidence: float | None = None,
    meta: dict[str, Any] | None = None,
    backend_meta: dict[str, Any] | None = None,
) -> EpisodeRecord:
    cfg = cfg if cfg is not None else {"friction": 0.5}
    ep = Episode(outcome=outcome, t=t, horizon=horizon, confidence=confidence, meta=meta or {})
    return EpisodeRecord.from_episode(
        ep, run_id=run_id, config=cfg, seed=seed, replicate_index=rep, wall_time=0.1,
        backend_meta=backend_meta,
    )


def keys_of(frame: pd.DataFrame) -> list[tuple[str, int]]:
    return [
        (str(h), int(r))
        for h, r in zip(frame["config_hash"], frame["replicate_index"], strict=True)
    ]


def _keyed_meta(cell: int, rep: int) -> dict[str, Any]:
    return {"cell": cell, "rep": rep, "trace": {"spans": [rep]}}


def _write_keyed_run(store: Store, run_id: str = KEYED_RUN) -> None:
    store.create_run(_manifest(run_id, axis_types={"f": "continuous", "g": "categorical"}))

    def batch(cells: Sequence[int]) -> list[EpisodeRecord]:
        out: list[EpisodeRecord] = []
        for c in cells:
            cfg = KEYED_CELLS[c]
            for k in range(KEYED_REPS):
                if (c, k) == ERRORED_KEY:
                    out.append(
                        EpisodeRecord.errored(
                            run_id=run_id, config=cfg, seed=100 * c + k, replicate_index=k,
                            error="boom", wall_time=0.2,
                        )
                    )
                    continue
                outcome, t = ("fell", 3.0 + k) if k % 2 == 0 else ("survived", 10.0)
                out.append(
                    _rec(
                        run_id, cfg=cfg, seed=100 * c + k, rep=k, outcome=outcome, t=t,
                        confidence=0.25 * k, meta=_keyed_meta(c, k), backend_meta={"i": c, "k": k},
                    )
                )
        return out

    store.append(run_id, batch([2]))
    store.append(run_id, batch([0, 3]))
    store.append(run_id, batch([1]))


def _synthetic_run(store: Store, run_id: str, *, fell_per_cell: dict[float, int]) -> None:
    """One cell per ``x``, ``fell_per_cell[x]`` of ``TWIN_N`` fell, a small JSON ``meta`` on
    every row so the intact twin has something real to decode."""
    store.create_run(
        _manifest(
            run_id, run_salt="twin", axis_types={"x": "continuous"}, target_id="synthetic@v0",
            t_unit="seconds",
        )
    )
    records = []
    for x, fell in fell_per_cell.items():
        for k in range(TWIN_N):
            outcome, t = ("fell", 3.0) if k < fell else ("survived", 10.0)
            records.append(
                _rec(
                    run_id, cfg={"x": x}, seed=1000 * int(x) + k, rep=k, outcome=outcome, t=t,
                    meta={"note": "intact", "k": k}, backend_meta={"i": k},
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


# ---------- helpers: poisoning, the CLI, inspect output ----------


def poison_meta(run_dir: Path, keys: set[tuple[str, int]] | None = None) -> int:
    """Rewrite every ``part-NNNNN.parquet`` under ``run_dir/episodes`` in place, replacing the
    ``meta`` cell of each row whose key is in ``keys`` (every row when None) with a string that
    is not JSON. Each part keeps its own schema, so nothing private to ``proofload.store`` is
    imported. Returns the number of rows poisoned."""
    poisoned = 0
    for part in sorted((run_dir / "episodes").glob("part-*.parquet")):
        table = pq.read_table(part)
        rows = zip(
            table.column("config_hash").to_pylist(),
            table.column("replicate_index").to_pylist(),
            table.column("meta").to_pylist(),
            strict=True,
        )
        hit: list[bool] = []
        meta: list[str] = []
        for h, r, m in rows:
            chosen = keys is None or (str(h), int(r)) in keys
            hit.append(chosen)
            meta.append(POISON if chosen else m)
        index = table.schema.get_field_index("meta")
        table = table.set_column(index, table.schema.field(index), pa.array(meta, pa.string()))
        pq.write_table(table, part)
        poisoned += sum(hit)
    return poisoned


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

    @property
    def text(self) -> str:
        return self.out + self.err


def run_cli(argv: Sequence[str]) -> Result:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def inspect_blocks(out: str, hashes: set[str]) -> tuple[list[list[str]], list[str]]:
    """Split inspect output into per-row blocks (each starting at a line naming a config_hash)
    and the trailing reproduction snippet. ``hashes`` is every hash in the run, so any row the
    verb prints starts a block, wanted or not. A hash is printed at 12 hex characters in text
    (front-door spec section 5.4, rule 10), so a block starts at a line naming that prefix."""
    body, marker, tail = out.partition(SNIPPET_MARKER)
    assert marker, f"no {SNIPPET_MARKER!r} snippet in inspect output:\n{out}"
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in body.splitlines():
        if any(h[:12] in line for h in hashes):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return blocks, (marker + tail).splitlines()


def assert_block_prints_row_with_trace(block: list[str], row: Any) -> None:
    """The block names the row and carries one tab-delimited trace line per stored span, with
    the span's kind and name in the second and third columns."""
    text = "\n".join(block)
    # 12 hex characters in text (front-door spec section 5.4, rule 10).
    assert row.config_hash[:12] in block[0], block[0]
    assert f"seed: {row.seed}" in block, text
    assert f"replicate_index: {row.replicate_index}" in block, text
    spans = row.meta["trace"]["spans"]
    step_lines = [line for line in block if STEP_LINE_RE.match(line)]
    assert len(step_lines) == len(spans) == int(row.t), text
    printed = sorted((cols[1], cols[2]) for cols in (line.split("\t") for line in step_lines))
    stored = sorted((str(span["kind"]), str(span["name"])) for span in spans)
    assert printed == stored, text


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def keyed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Store, pd.DataFrame]:
    """The keyed run and its default frame, read through the frozen M4 path. Never mutated."""
    store = Store(tmp_path_factory.mktemp("keyed-store"))
    _write_keyed_run(store)
    return store, store.read(KEYED_RUN)


@dataclass(frozen=True)
class Twins:
    """Two copies of one two-run store: ``intact`` as written, ``poisoned`` with every ``meta``
    cell rewritten. ``stage`` copies either into ``live``, the one path the CLI is pointed at,
    so the same argv prints the same store and report paths on both twins."""

    live: Path
    intact: Path
    poisoned: Path

    def stage(self, twin: Path) -> Path:
        if self.live.exists():
            shutil.rmtree(self.live)
        shutil.copytree(twin, self.live)
        return self.live


@pytest.fixture(scope="module")
def twins(tmp_path_factory: pytest.TempPathFactory) -> Twins:
    root = tmp_path_factory.mktemp("twins")
    poisoned = root / "poisoned"
    store = Store(poisoned)
    _synthetic_run(store, "syn-a", fell_per_cell={1.0: TWIN_N, 2.0: TWIN_N // 2})
    _synthetic_run(store, "syn-b", fell_per_cell={1.0: 0, 2.0: TWIN_N // 2})
    intact = root / "intact"
    intact.mkdir()
    for run_id in TWIN_RUNS:
        shutil.copytree(poisoned / run_id, intact / run_id)
    for run_id in TWIN_RUNS:
        assert poison_meta(poisoned / run_id) == 2 * TWIN_N
        for part in (poisoned / run_id / "episodes").glob("part-*.parquet"):
            assert set(pq.read_table(part).column("meta").to_pylist()) == {POISON}
    return Twins(live=root / "store", intact=intact, poisoned=poisoned)


@dataclass(frozen=True)
class MockRun:
    root: Path
    run_id: str
    frame: pd.DataFrame  # the default read, taken while the run was intact

    @property
    def hashes(self) -> set[str]:
        return set(self.frame["config_hash"])

    @property
    def violated(self) -> pd.DataFrame:
        return self.frame[self.frame["outcome"] == "violated"].reset_index(drop=True)


@pytest.fixture(scope="module")
def mock_run(tmp_path_factory: pytest.TempPathFactory) -> MockRun:
    """The mock agent over a small grid, through run_local, with traces on every row. Never
    mutated: each R6 test poisons its own copy."""
    root = tmp_path_factory.mktemp("mock-store")
    store = Store(root)
    spec = SweepSpec.build(
        MOCK_CONFIGS, replicates=MOCK_REPLICATES, target_id="mock-agent@v0", t_unit="tool_calls"
    )
    p = plan(spec, store, run_salt=MOCK_SALT, import_path=MOCK_ROLLOUT)
    summary = run_local(p, rollout, store, batch_size=MOCK_BATCH)
    assert summary.complete and summary.n_errored == 0
    frame = store.read(p.run_id)
    violated = frame["outcome"] == "violated"
    assert violated.sum() >= 2 and (~violated).sum() >= 1, frame["outcome"].value_counts()
    assert (frame.groupby("config_hash")["outcome"].nunique() > 1).any(), "no cell mixes outcomes"
    assert len(list((root / p.run_id / "episodes").glob("part-*.parquet"))) > 1
    assert all("trace" in meta for meta in frame["meta"])
    return MockRun(root=root, run_id=p.run_id, frame=frame)


def poisoned_copy(mock: MockRun, dest: Path, keys: set[tuple[str, int]]) -> Path:
    """Copy the mock run into a fresh store root and poison exactly ``keys``."""
    shutil.copytree(mock.root / mock.run_id, dest / mock.run_id)
    assert keys and poison_meta(dest / mock.run_id, keys) == len(keys)
    return dest


def inspect_violated(root: Path, run_id: str, *extra: str) -> Result:
    return run_cli(["--store", str(root), "inspect", run_id, "--event", "violated", *extra])


def assert_inspect_prints_exactly(r: Result, rows: pd.DataFrame, hashes: set[str]) -> None:
    assert r.code == 0, r.text
    assert not r.err, r.err
    blocks, snippet = inspect_blocks(r.out, hashes)
    assert len(blocks) == len(rows), r.out
    for block, row in zip(blocks, rows.itertuples(index=False), strict=True):
        assert_block_prints_row_with_trace(block, row)
    assert "from poisson_prove.examples.mock_agent import rollout" in snippet, snippet


# ---------- R1: the default read is unchanged, and meta=True is the default ----------


def test_r1_default_read_is_the_thirteen_column_frame(keyed: tuple[Store, pd.DataFrame]) -> None:
    _, frame = keyed
    assert list(frame.columns) == FRAME
    assert len(frame) == len(PRESENT_KEYS)
    assert keys_of(frame) == sorted(PRESENT_KEYS)
    for col in JSON_COLUMNS:
        assert all(isinstance(v, dict) for v in frame[col]), col
    cell, rep = 2, 1
    row = frame[
        (frame["config_hash"] == config_hash(KEYED_CELLS[cell])) & (frame["replicate_index"] == rep)
    ].iloc[0]
    assert row["meta"] == _keyed_meta(cell, rep)
    assert row["backend_meta"] == {"i": cell, "k": rep}
    assert row["config"] == KEYED_CELLS[cell]


def test_r1_meta_true_is_the_default_read(keyed: tuple[Store, pd.DataFrame]) -> None:
    store, frame = keyed
    explicit = store.read(KEYED_RUN, meta=True)
    pd.testing.assert_frame_equal(explicit, store.read(KEYED_RUN))
    pd.testing.assert_frame_equal(explicit, frame)


# ---------- R2: meta=False is the eleven-column projection ----------


def test_r2_narrow_read_is_the_eleven_columns_of_the_default_frame(
    keyed: tuple[Store, pd.DataFrame],
) -> None:
    store, frame = keyed
    narrow = store.read(KEYED_RUN, meta=False)
    assert list(narrow.columns) == NARROW
    assert all(isinstance(cfg, dict) for cfg in narrow["config"])
    assert keys_of(narrow) == sorted(PRESENT_KEYS)
    pd.testing.assert_frame_equal(narrow, frame[NARROW])


def test_r2_narrow_read_of_an_empty_run_keeps_columns_and_dtypes(
    keyed: tuple[Store, pd.DataFrame], tmp_path: Path
) -> None:
    store, _ = keyed
    empty = Store(tmp_path)
    empty.create_run(_manifest("empty"))
    narrow = empty.read("empty", meta=False)
    assert list(narrow.columns) == NARROW and len(narrow) == 0
    assert narrow.dtypes.equals(store.read(KEYED_RUN, meta=False).dtypes)


# ---------- R3: keys= selects exactly those rows ----------


@settings(max_examples=60, deadline=None)
@given(
    keys=st.lists(st.sampled_from(KEY_POOL), max_size=2 * len(KEY_POOL)),
    meta=st.booleans(),
    container=st.sampled_from([list, tuple, set, frozenset, iter]),
)
def test_r3_keys_select_exactly_those_rows(
    keyed: tuple[Store, pd.DataFrame],
    keys: list[tuple[str, int]],
    meta: bool,
    container: Any,
) -> None:
    store, frame = keyed
    wanted = set(keys)
    expected = frame[[k in wanted for k in keys_of(frame)]]
    if not meta:
        expected = expected[NARROW]
    got = store.read(KEYED_RUN, keys=container(keys), meta=meta)
    pd.testing.assert_frame_equal(got, expected.reset_index(drop=True))
    assert keys_of(got) == sorted(keys_of(got))


def test_r3_absent_keys_and_duplicates_change_nothing(keyed: tuple[Store, pd.DataFrame]) -> None:
    store, frame = keyed
    two = [PRESENT_KEYS[0], PRESENT_KEYS[4]]
    expected = frame[[k in set(two) for k in keys_of(frame)]].reset_index(drop=True)
    assert len(expected) == 2
    pd.testing.assert_frame_equal(store.read(KEYED_RUN, keys=two), expected)
    pd.testing.assert_frame_equal(store.read(KEYED_RUN, keys=two + two + ABSENT_KEYS), expected)
    assert len(store.read(KEYED_RUN, keys=ABSENT_KEYS)) == 0


@pytest.mark.parametrize(
    "meta, columns", [(True, FRAME), (False, NARROW)], ids=["meta", "no-meta"]
)
def test_r3_empty_keys_is_an_empty_frame_with_the_requested_columns(
    keyed: tuple[Store, pd.DataFrame], meta: bool, columns: list[str]
) -> None:
    # pyarrow raises ArrowTypeError on an empty `in` list: keys=[] must short-circuit.
    store, _ = keyed
    got = store.read(KEYED_RUN, keys=[], meta=meta)
    assert list(got.columns) == columns and len(got) == 0
    assert got.dtypes.equals(store.read(KEYED_RUN, meta=meta).dtypes)


def test_r3_empty_keys_touch_no_part(tmp_path: Path) -> None:
    store = Store(tmp_path)
    _write_keyed_run(store)
    parts = list((tmp_path / KEYED_RUN / "episodes").glob("part-*.parquet"))
    assert parts
    for part in parts:
        part.write_bytes(b"\x00 not a parquet file")
        with pytest.raises(pa.ArrowInvalid):
            pq.read_table(part)
    for meta, columns in ((True, FRAME), (False, NARROW)):
        got = store.read(KEYED_RUN, keys=[], meta=meta)
        assert list(got.columns) == columns and len(got) == 0


def test_r3_keys_compose_with_narrow_read(keyed: tuple[Store, pd.DataFrame]) -> None:
    store, frame = keyed
    cell_hash = config_hash(KEYED_CELLS[3])
    keys = [(cell_hash, k) for k in range(KEYED_REPS)]  # includes the errored row
    got = store.read(KEYED_RUN, keys=keys, meta=False)
    assert list(got.columns) == NARROW
    expected = frame[frame["config_hash"] == cell_hash][NARROW].reset_index(drop=True)
    assert len(expected) == KEYED_REPS
    pd.testing.assert_frame_equal(got, expected)
    assert got["error"].notna().sum() == 1


# ---------- R4: count reads the footers ----------


def test_r4_count_tracks_len_read_across_parts(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.create_run(_manifest())
    batches = (
        [_rec(rep=0), _rec(rep=1)],
        [_rec(rep=2)],
        [_rec(cfg={"friction": 0.9}, rep=k) for k in range(4)],
    )
    total = 0
    for n, batch in enumerate(batches, start=1):
        total += store.append("r1", batch)
        assert store.count("r1") == len(store.read("r1")) == total
        assert len(list((tmp_path / "r1" / "episodes").glob("part-*.parquet"))) == n


def test_r4_count_of_the_keyed_run(keyed: tuple[Store, pd.DataFrame]) -> None:
    store, frame = keyed
    assert store.count(KEYED_RUN) == len(frame) == len(PRESENT_KEYS)


def test_r4_count_of_an_empty_run_is_zero(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.create_run(_manifest("empty"))
    assert store.count("empty") == 0 == len(store.read("empty"))


def test_r4_count_of_an_unknown_run_raises_store_error(tmp_path: Path) -> None:
    store = Store(tmp_path)
    with pytest.raises(StoreError):
        store.count("nope")
    store.create_run(_manifest("other"))
    with pytest.raises(StoreError):
        store.count("nope")


def test_r4_tmp_part_changes_neither_count_nor_read(tmp_path: Path) -> None:
    store = Store(tmp_path)
    _write_keyed_run(store)
    default = store.read(KEYED_RUN)
    narrow = store.read(KEYED_RUN, meta=False)
    count = store.count(KEYED_RUN)
    assert count == len(default) == len(PRESENT_KEYS)
    two = keys_of(default)[:2]
    keyed_before = store.read(KEYED_RUN, keys=two)

    tmp = tmp_path / KEYED_RUN / "episodes" / "part-00099.parquet.tmp"
    tmp.write_bytes(b"\x00\x01 half-written garbage, not parquet")

    assert store.count(KEYED_RUN) == count
    pd.testing.assert_frame_equal(store.read(KEYED_RUN), default)
    pd.testing.assert_frame_equal(store.read(KEYED_RUN, meta=False), narrow)
    pd.testing.assert_frame_equal(store.read(KEYED_RUN, keys=two), keyed_before)
    assert tmp.is_file()


# ---------- R5: the guard ----------


def r5_argv(verb: str, out: Path) -> list[str]:
    a, b = TWIN_RUNS
    if verb == "diff":
        return ["diff", a, b, "--event", "fell"]
    if verb == "check":
        # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and the twins
        # declare none; --fail-on higher is the same gate ("fail when the rate rose").
        return ["check", a, b, "--event", "fell", "--fail-on", "higher"]
    if verb == "report-pair":
        return ["report", a, b, "--event", "fell", "--x", "x", "--out", str(out)]
    if verb == "report-run":
        return ["report", a, "--event", "fell", "--x", "x", "--out", str(out)]
    assert verb == "runs"
    return ["runs"]


@pytest.mark.parametrize("verb", ["diff", "check", "report-pair", "report-run", "runs"])
def test_r5_verbs_read_the_poisoned_store_exactly_as_the_intact_one(
    twins: Twins, tmp_path: Path, verb: str
) -> None:
    out = tmp_path / "report"
    argv = r5_argv(verb, out)
    results: dict[str, Result] = {}
    reports: dict[str, bytes | None] = {}
    for name, twin in (("intact", twins.intact), ("poisoned", twins.poisoned)):
        if out.exists():
            shutil.rmtree(out)
        live = twins.stage(twin)
        results[name] = run_cli(["--store", str(live), *argv])
        report = out / "report.md"
        reports[name] = report.read_bytes() if report.is_file() else None
    intact, poisoned = results["intact"], results["poisoned"]
    assert intact.code == 0, intact.text
    assert intact.out.strip(), "the intact run printed nothing"
    if verb == "check":
        # check's verdict is its first stdout line, passed or failed (front-door spec section 5.3).
        # PF4 (PF4.20): an event of unknown kind is counted in direction words, so no rise reads
        # "0 higher" where it read "0 worse".
        assert intact.out.startswith("passed  ") and "0 higher" in intact.out, intact.out
    if verb.startswith("report"):
        assert reports["intact"] is not None
    assert poisoned.code == intact.code, poisoned.text
    assert poisoned.out == intact.out
    assert poisoned.err == intact.err
    assert reports["poisoned"] == reports["intact"]


@pytest.mark.parametrize("run_id", TWIN_RUNS)
def test_r5_poisoned_meta_raises_on_the_default_read_and_not_on_the_narrow_paths(
    twins: Twins, run_id: str
) -> None:
    intact, poisoned = Store(twins.intact), Store(twins.poisoned)
    reference = intact.read(run_id)
    assert list(reference.columns) == FRAME and len(reference) == 2 * TWIN_N
    assert reference.iloc[0]["meta"] == {"note": "intact", "k": 0}

    with pytest.raises(ValueError):
        poisoned.read(run_id)
    with pytest.raises(ValueError):
        poisoned.read(run_id, meta=True)
    narrow = poisoned.read(run_id, meta=False)
    pd.testing.assert_frame_equal(narrow, intact.read(run_id, meta=False))
    pd.testing.assert_frame_equal(narrow, reference[NARROW])
    assert poisoned.count(run_id) == intact.count(run_id) == 2 * TWIN_N


# ---------- R6: inspect decodes only the rows it prints ----------


def test_r6_inspect_prints_the_event_rows_when_every_other_row_is_poisoned(
    mock_run: MockRun, tmp_path: Path
) -> None:
    selected = mock_run.violated
    others = set(keys_of(mock_run.frame)) - set(keys_of(selected))
    assert others
    root = poisoned_copy(mock_run, tmp_path / "store", others)
    r = inspect_violated(root, mock_run.run_id)
    assert_inspect_prints_exactly(r, selected, mock_run.hashes)


def test_r6_inspect_where_decodes_only_the_rows_the_filter_keeps(
    mock_run: MockRun, tmp_path: Path
) -> None:
    violated = mock_run.violated
    selected = violated[[cfg["tool_fail_rate"] == 0.5 for cfg in violated["config"]]]
    selected = selected.reset_index(drop=True)
    assert 0 < len(selected) < len(violated)
    others = set(keys_of(mock_run.frame)) - set(keys_of(selected))
    root = poisoned_copy(mock_run, tmp_path / "store", others)
    r = inspect_violated(root, mock_run.run_id, "--where", "tool_fail_rate=0.5")
    assert_inspect_prints_exactly(r, selected, mock_run.hashes)


def test_r6_inspect_limit_decodes_only_the_rows_it_keeps(mock_run: MockRun, tmp_path: Path) -> None:
    violated = mock_run.violated
    assert len(violated) >= 2
    first = violated.head(1)
    others = set(keys_of(mock_run.frame)) - set(keys_of(first))
    assert others >= set(keys_of(violated.iloc[1:]))
    root = poisoned_copy(mock_run, tmp_path / "store", others)
    r = inspect_violated(root, mock_run.run_id, "--limit", "1")
    assert_inspect_prints_exactly(r, first, mock_run.hashes)


def test_r6_one_poisoned_selected_row_is_loud(mock_run: MockRun, tmp_path: Path) -> None:
    violated = mock_run.violated
    assert len(violated) >= 2
    victim = violated.iloc[1]
    victim_key = (str(victim["config_hash"]), int(victim["replicate_index"]))
    root = poisoned_copy(mock_run, tmp_path / "store", {victim_key})

    r = inspect_violated(root, mock_run.run_id)
    assert r.code == 3, r.text
    assert "JSONDecodeError" in r.err, r.err

    store = Store(root)
    with pytest.raises(ValueError):
        store.read(mock_run.run_id, keys=[victim_key])

    # The row it does not name is still readable and decoded, and the narrow paths never notice.
    other = violated.iloc[0]
    other_key = (str(other["config_hash"]), int(other["replicate_index"]))
    got = store.read(mock_run.run_id, keys=[other_key])
    assert keys_of(got) == [other_key]
    assert got.iloc[0]["meta"] == other["meta"]
    pd.testing.assert_frame_equal(store.read(mock_run.run_id, meta=False), mock_run.frame[NARROW])
    assert store.count(mock_run.run_id) == len(mock_run.frame)


# ---------- R7: no schema change; the lattice golden ----------


@pytest.mark.parametrize("run_id", LATTICE_RUNS)
def test_r7_lattice_default_read_is_2304_by_13(lattice_store: Store, run_id: str) -> None:
    df = lattice_store.read(run_id)
    # PF4 re-freeze (reading R5): the thirteen columns plus case_id, null on parts written before it.
    assert df.shape == (LATTICE_ROWS, 13 + 1)
    assert LATTICE_ROWS == lattice.ROWS == len(lattice.rows(run_id))
    assert list(df.columns) == FRAME
    assert df["case_id"].isna().all()


@pytest.mark.parametrize("run_id", LATTICE_RUNS)
def test_r7_lattice_narrow_read_is_2304_by_11(lattice_store: Store, run_id: str) -> None:
    df = lattice_store.read(run_id, meta=False)
    # PF4 re-freeze (reading R5): the eleven columns plus case_id, null on parts written before it.
    assert df.shape == (LATTICE_ROWS, 11 + 1)
    assert list(df.columns) == NARROW
    assert df["case_id"].isna().all()


def test_r7_lattice_count_is_2304_per_run_and_4608_together(lattice_store: Store) -> None:
    counts = {run_id: lattice_store.count(run_id) for run_id in LATTICE_RUNS}
    assert counts == {run_id: LATTICE_ROWS for run_id in LATTICE_RUNS}
    assert sum(counts.values()) == LATTICE_TOTAL_ROWS == 2 * lattice.ROWS


def test_r7_on_disk_schema_and_manifest_are_unchanged(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.create_run(_manifest())
    store.append("r1", [_rec()])
    fresh = pq.read_schema(next((tmp_path / "r1" / "episodes").glob("part-*.parquet")))
    golden = pq.read_schema(LATTICE_ROOT / lattice.RUN_A / "episodes" / "part-00000.parquet")
    # The lattice part is written in the legacy (pre-A7) layout, the thirteen columns.
    assert golden.names == THIRTEEN == list(lattice.LEGACY_COLUMNS)
    # A7 (spec section 3.1, 7.1): the on-disk schema is the legacy golden's thirteen fields plus
    # ``trace`` and ``trace_obs``, both nullable strings, appended in that order. Amended from
    # ``fresh.equals(golden)`` / ``fresh.names == THIRTEEN``; the golden comparison is kept.
    # PF4 re-freeze (reading R5): a nullable string case_id column follows trace_obs.
    expected = golden.append(pa.field("trace", pa.string(), nullable=True)).append(
        pa.field("trace_obs", pa.string(), nullable=True)
    ).append(pa.field("case_id", pa.string(), nullable=True))
    assert fresh.equals(expected), f"\n{fresh}\n!=\n{expected}"
    assert fresh.names == THIRTEEN + ["trace", "trace_obs", "case_id"]
    golden_manifest = json.loads((LATTICE_ROOT / lattice.RUN_A / "manifest.json").read_text())
    assert set(golden_manifest) == lattice.LEGACY_MANIFEST_KEYS
    # A10 (spec section 3.3, 7.1 group 1, W4): the manifest's top-level keys are the legacy golden's
    # twelve plus ``declared``, which is null for a sweep that declares nothing. Amended from
    # ``== set(golden_manifest)``; the golden comparison is kept. A23/A26 re-amends this line.
    # PF0 (Q4): the version key is written as ``poisson_prove_version``; the golden, written by
    # 0.0.1, keeps ``proofload_version``.
    assert set(store.manifest("r1").to_dict()) == (set(golden_manifest) - {"proofload_version"}) | {"poisson_prove_version", "declared"}


# ---------- R8: runs on the lattice store ----------


def test_r8_runs_on_lattice_prints_each_run_with_2304_rows(lattice_store: Store) -> None:
    r = run_cli(["--store", str(LATTICE_ROOT), "runs"])
    assert r.code == 0, r.text
    assert not r.err
    lines = [line for line in r.out.splitlines() if line.strip()]
    # PF2 (spec section 4.3): the first line is the verdict `ok  N runs in <store>` instead of
    # `store: <root>`, and the table has the columns #, name, id, status, backend, target, rows,
    # rows without an outcome, created (t_unit is no longer a column). A name holds single
    # spaces, so cells are split on runs of two or more spaces.
    assert lines[0] == f"ok  {len(LATTICE_RUNS)} runs in {LATTICE_ROOT}"
    assert re.split(r"\s{2,}", lines[1].strip()) == [
        "#", "name", "id", "status", "backend", "target", "rows", "rows without an outcome",
        "created",
    ]
    cells = [re.split(r"\s{2,}", line.rstrip()) for line in lines[2:]]
    rows = {cell[2]: cell for cell in cells}
    # PF2 (spec section 4.3): newest first by created_at, where the old table was in id order.
    newest_first = sorted(
        LATTICE_RUNS, key=lambda run_id: lattice_store.manifest(run_id).created_at, reverse=True,
    )
    assert list(rows) == newest_first == [lattice.RUN_B, lattice.RUN_A]
    names = {lattice.RUN_A: lattice.NAME_A, lattice.RUN_B: lattice.NAME_B}
    for number, run_id in enumerate(newest_first, start=1):
        m = lattice_store.manifest(run_id)
        assert f"{m.target_id.split('/')[0]} {m.created_at[:10]} a" == names[run_id]
        assert rows[run_id] == [
            # PF2 (spec section 4.3): a number and the computed name lead the row; created ends it.
            str(number), f"{m.target_id.split('/')[0]} {m.created_at[:10]} a",
            # Counts carry thousands separators in text (front-door spec section 5.4, rule 10).
            run_id, m.status, m.backend, m.target_id, f"{LATTICE_ROWS:,}", "0",
            f"{m.created_at[:19]}Z",
        ]


# ---------- R9: the public surface ----------


def test_r9_read_gains_exactly_meta_and_keys_keyword_only() -> None:
    params = inspect.signature(Store.read).parameters
    # A7 (spec section 2, 7.1): ``trace=`` is appended last, keyword-only, default None. Four
    # names to five; ``meta`` and ``keys`` keep their kind and default.
    assert list(params) == ["self", "run_id", "meta", "keys", "trace"]
    assert params["trace"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["trace"].default is None
    assert params["run_id"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert params["run_id"].default is inspect.Parameter.empty
    assert params["meta"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["meta"].default is True
    assert params["keys"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["keys"].default is None


def test_r9_count_takes_a_run_id_and_nothing_else() -> None:
    params = inspect.signature(Store.count).parameters
    assert list(params) == ["self", "run_id"]
    assert params["run_id"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD


def test_r9_store_public_methods_are_exactly_the_nine() -> None:
    methods = {
        name for name, _ in inspect.getmembers(Store, inspect.isfunction)
        if not name.startswith("_")
    }
    assert methods == PUBLIC_STORE_METHODS


def test_r9_nothing_else_in_the_module_changes() -> None:
    public = {
        name
        for name, obj in vars(store_module).items()
        if not name.startswith("_") and getattr(obj, "__module__", None) == store_module.__name__
    }
    assert public == PUBLIC_STORE_SYMBOLS
