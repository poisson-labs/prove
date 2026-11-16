"""0.3.1, prove#33: a one-row append costs the same however large the run is. The frozen tests.

``Store.append`` checks for a duplicate episode by reading the ``config_hash`` and
``replicate_index`` of every part the run already has, and each append writes one new part, so a
caller that appends one row as each episode finishes reads every earlier part on every append and
the run costs the square of its rows. These tests pin the fix the issue calls "keep the keys"
without choosing how it is built, and pin everything the issue says does not change.

**How the work is counted.** Not by a clock. A part the store must not read again is *blinded*:
its bytes are overwritten in place with zeros of the same length and its modification time is put
back, so the file keeps its name, its inode, its size and its mtime, and any read of it (data,
footer or schema) fails. A one-row append that succeeds with every earlier part blinded read none
of them. The one timing test (A2) compares an append with a read of the run's keys, taken in
turn, so load on the machine slows both alike, and its bound is wide: it catches the square, not
a constant.

**Readings, named here** (where the issue leaves a choice, the one this file makes).

- R1 "The parts that have appeared since" is per ``Store`` object: a new ``Store`` on a run reads
  each of its parts once, at its first append (or ``missing``), and that is allowed. A part is
  "the same part" when its name, inode, size and modification time are unchanged; a part whose
  name is gone, or whose name now holds another file, is not, and the store reads the run again
  rather than trust what it remembered. The ``Store`` may remember nothing on disk (yes/no 1).
- R2 "Duplicates are still refused exactly as today": the refusal is ``DuplicateEpisode``, a
  ``StoreError``, its message begins as today's does, nothing is written, and the keys checked
  against are exactly the keys on disk at the moment of the append, whoever wrote them: this
  ``Store``, another ``Store``, another process. A batch refused, or a write that failed, leaves
  no key behind; a part removed by hand frees its keys, as today.
- R3 "Rows, the schema and part names stay as they are": a one-row append writes exactly one new
  file in ``episodes/``, named ``part-NNNNN.parquet`` one past the highest, and changes no byte of
  any other part. No folding of parts in 0.3.1 (yes/no 2).
- R4 "A run killed part-way keeps everything appended": every row whose ``append`` returned is
  read back by a fresh ``Store`` after the writer is killed with SIGKILL, and the run takes the
  rest; a ``.tmp`` file the kill left is not a part.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| A1 a one-row append reads no part this ``Store`` has read or written, and reads every part another writer added | ``test_a1_*`` |
| A2 one more append, at 1,000 parts, costs a small fraction of reading the run (the one timed test) | ``test_a2_*`` |
| A3 duplicates refused exactly as today | ``test_a3_*`` |
| A4 a run killed part-way keeps everything appended | ``test_a4_*`` |
| A5 runs already stored read and append unchanged; parts as today | ``test_a5_*`` |
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store, StoreError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
OLD = TESTS / "fixtures" / "stores-0.0.1"
OLD_RUNS: dict[str, str] = json.loads((OLD / "runs.json").read_text(encoding="utf-8"))
CONFIG = {"case": "c"}


# ---------- helpers ----------


def make_run(store: Store, run_id: str) -> None:
    store.create_run(
        RunManifest(
            run_id=run_id,
            target_id="t",
            t_unit="seconds",
            run_salt="s",
            axis_types={"case": "categorical"},
            backend="b",
            environment={},
        )
    )


def row(run_id: str, i: int, *, config: dict[str, Any] | None = None) -> EpisodeRecord:
    """Replicate ``i`` of one condition: its key is ``(config_hash(config), i)``."""
    return EpisodeRecord.from_episode(
        Episode(outcome="ok", t=1.0, horizon=30.0),
        run_id=run_id,
        config=dict(config or CONFIG),
        seed=1000 + i,
        replicate_index=i,
        wall_time=0.01,
        backend_meta={},
    )


def parts(root: Path, run_id: str) -> list[Path]:
    return sorted((root / run_id / "episodes").glob("part-*.parquet"))


def episodes_listing(root: Path, run_id: str) -> dict[str, str]:
    """Every file in the run's ``episodes/``, by name, with the sha256 of its bytes."""
    folder = root / run_id / "episodes"
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}


def replicates(store: Store, run_id: str) -> list[int]:
    return sorted(int(i) for i in store.read(run_id, meta=False)["replicate_index"])


def blind(paths: list[Path]) -> None:
    """Make each part unreadable while it stays the same part by name, inode, size and mtime."""
    for path in paths:
        before = path.stat()
        size = before.st_size
        with open(path, "r+b") as f:
            f.write(b"\0" * size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = path.stat()
        assert (after.st_ino, after.st_size, after.st_mtime_ns) == (before.st_ino, before.st_size, before.st_mtime_ns)
    for path in paths:
        with pytest.raises(Exception):  # noqa: B017 - any read of a blinded part must fail
            pq.read_metadata(path)


def forge_parts(root: Path, run_id: str, n: int, *, start: int = 0) -> None:
    """``n`` one-row parts written into the run beside any it has, as an earlier build or another
    process would have left them: the bytes of one real part, its replicate index and seed
    changed, so every part is a distinct key and none was written by the ``Store`` under test."""
    scratch = root / ".forge"
    if not scratch.exists():
        s = Store(scratch)
        make_run(s, "template")
        s.append("template", [row("template", 0)])
    template = pq.read_table(parts(scratch, "template")[0])
    names = template.column_names
    folder = root / run_id / "episodes"
    have = parts(root, run_id)
    first = 0 if not have else int(have[-1].name[len("part-") : -len(".parquet")]) + 1
    for k in range(n):
        i = start + k
        table = template
        for column, value in (("run_id", run_id), ("replicate_index", i), ("seed", 1000 + i)):
            at = names.index(column)
            table = table.set_column(at, template.schema.field(at), pa.array([value], type=template.schema.field(at).type))
        pq.write_table(table, folder / f"part-{first + k:05d}.parquet")


# ---------- A1: what an append reads ----------


def test_a1_a_one_row_append_reads_no_part_this_store_already_wrote(tmp_path: Path) -> None:
    store = Store(tmp_path)
    make_run(store, "r")
    for i in range(60):
        store.append("r", [row("r", i)])
    blind(parts(tmp_path, "r"))
    assert store.append("r", [row("r", 60)]) == 1
    assert len(parts(tmp_path, "r")) == 61


def test_a1_a_new_store_reads_the_run_once_then_only_what_is_new(tmp_path: Path) -> None:
    """R1: a ``Store`` opened on a run another wrote may read every part at its first append; after
    that, the parts it read are not read again."""
    first = Store(tmp_path)
    make_run(first, "r")
    for i in range(40):
        first.append("r", [row("r", i)])
    second = Store(tmp_path)
    assert second.append("r", [row("r", 40)]) == 1
    blind(parts(tmp_path, "r"))
    for i in range(41, 45):
        assert second.append("r", [row("r", i)]) == 1
    assert len(parts(tmp_path, "r")) == 45


def test_a1_a_part_another_store_wrote_since_is_read_before_the_write(tmp_path: Path) -> None:
    """The duplicate check stays as strong as it is: a key another writer stored after this store's
    last append is refused, though every part this store already knew is unreadable."""
    mine, theirs = Store(tmp_path), Store(tmp_path)
    make_run(mine, "r")
    for i in range(20):
        mine.append("r", [row("r", i)])
    known = parts(tmp_path, "r")
    for i in range(20, 25):
        theirs.append("r", [row("r", i)])
    blind(known)
    before = episodes_listing(tmp_path, "r")
    with pytest.raises(StoreError) as refused:
        mine.append("r", [row("r", 22)])
    assert type(refused.value).__name__ == "DuplicateEpisode"
    assert episodes_listing(tmp_path, "r") == before
    assert mine.append("r", [row("r", 25)]) == 1


def test_a1_a_part_written_by_another_process_is_read_before_the_write(tmp_path: Path) -> None:
    """The same, with the other writer a separate Python process."""
    mine = Store(tmp_path)
    make_run(mine, "r")
    for i in range(10):
        mine.append("r", [row("r", i)])
    known = parts(tmp_path, "r")
    script = (
        "import sys\n"
        "from poisson_prove.episode import Episode\n"
        "from poisson_prove.store import EpisodeRecord, Store\n"
        "s = Store(sys.argv[1])\n"
        "for i in (10, 11, 12):\n"
        "    s.append('r', [EpisodeRecord.from_episode(Episode(outcome='ok', t=1.0, horizon=30.0), run_id='r',"
        " config={'case': 'c'}, seed=1000 + i, replicate_index=i, wall_time=0.01, backend_meta={})])\n"
    )
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    done = subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=env, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    blind(known)
    with pytest.raises(StoreError) as refused:
        mine.append("r", [row("r", 11)])
    assert type(refused.value).__name__ == "DuplicateEpisode"
    assert mine.append("r", [row("r", 13)]) == 1


def test_a1_missing_counts_every_key_on_disk_whoever_wrote_it(tmp_path: Path) -> None:
    """``missing``, which a resume reads, answers from the keys on disk, as today."""
    mine, theirs = Store(tmp_path), Store(tmp_path)
    make_run(mine, "r")
    for i in range(0, 10, 2):
        mine.append("r", [row("r", i)])
    for i in range(1, 10, 2):
        if i != 7:
            theirs.append("r", [row("r", i)])
    expected = [(row("r", i).config_hash, i) for i in range(12)]
    assert mine.missing("r", expected) == [(row("r", 7).config_hash, 7), (row("r", 10).config_hash, 10), (row("r", 11).config_hash, 11)]


# ---------- A2: the cost, timed, under load ----------


def test_a2_one_more_append_costs_a_small_fraction_of_reading_the_run_at_1000_parts(tmp_path: Path) -> None:
    """The issue's table: at 1,000 rows one more append took 208 ms, because it read every part.
    A run of 1,000 parts (written as an earlier build would have left them) takes one row at a
    time, 30 times, through one ``Store`` after a first append (which may read the run, R1); in
    turn with those appends, the same run's keys are read whole, 10 times, as today's append reads
    them. The median append costs at most a quarter of the median whole read. Taken in turn, the
    two see the same load, so the bound holds on a loaded machine: today's append is one whole read
    and more, and an append that lists the folder (the issue's "one directory listing") is about a
    tenth of one on a Mac."""
    make_run(Store(tmp_path), "large")
    forge_parts(tmp_path, "large", 1000)
    store = Store(tmp_path)
    store.append("large", [row("large", 1000)])
    appends: list[float] = []
    reads: list[float] = []
    for k in range(30):
        began = time.perf_counter()
        store.append("large", [row("large", 1001 + k)])
        appends.append(time.perf_counter() - began)
        if k % 3 == 0:
            began = time.perf_counter()
            keys = [pq.read_table(p, columns=["config_hash", "replicate_index"]).num_rows for p in parts(tmp_path, "large")]
            reads.append(time.perf_counter() - began)
            assert sum(keys) == 1002 + k
    append, read = statistics.median(appends), statistics.median(reads)
    assert append <= read / 4, f"median one-row append {append * 1000:.1f} ms; median read of the run's keys {read * 1000:.1f} ms"
    assert len(parts(tmp_path, "large")) == 1031 and store.count("large") == 1031


# ---------- A3: duplicates, exactly as today ----------


def test_a3_a_key_already_stored_is_refused_as_today_and_nothing_is_written(tmp_path: Path) -> None:
    store = Store(tmp_path)
    make_run(store, "r")
    for i in range(5):
        store.append("r", [row("r", i)])
    before = episodes_listing(tmp_path, "r")
    with pytest.raises(StoreError) as refused:
        store.append("r", [row("r", 5), row("r", 3)])
    assert type(refused.value).__name__ == "DuplicateEpisode"
    assert str(refused.value).startswith("(config_hash, replicate_index) already in store: ")
    assert str((row("r", 3).config_hash, 3)) in str(refused.value)
    assert episodes_listing(tmp_path, "r") == before
    assert replicates(store, "r") == [0, 1, 2, 3, 4]


def test_a3_a_duplicate_inside_one_batch_is_refused_as_today(tmp_path: Path) -> None:
    store = Store(tmp_path)
    make_run(store, "r")
    store.append("r", [row("r", 0)])
    before = episodes_listing(tmp_path, "r")
    with pytest.raises(StoreError) as refused:
        store.append("r", [row("r", 1), row("r", 1)])
    assert type(refused.value).__name__ == "DuplicateEpisode"
    assert str(refused.value).startswith("duplicate (config_hash, replicate_index) in batch: ")
    assert episodes_listing(tmp_path, "r") == before


def test_a3_a_refused_batch_leaves_no_key_behind(tmp_path: Path) -> None:
    """The batch's other rows were never stored, so they are not duplicates later."""
    store = Store(tmp_path)
    make_run(store, "r")
    store.append("r", [row("r", 0)])
    with pytest.raises(StoreError):
        store.append("r", [row("r", 1), row("r", 2), row("r", 0)])
    with pytest.raises(StoreError):
        store.append("r", [row("r", 3), row("r", 3)])
    assert store.append("r", [row("r", 1), row("r", 2)]) == 2
    assert store.append("r", [row("r", 3)]) == 1
    assert replicates(store, "r") == [0, 1, 2, 3]


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root writes into a read-only folder")
def test_a3_a_write_that_failed_leaves_no_key_behind(tmp_path: Path) -> None:
    store = Store(tmp_path)
    make_run(store, "r")
    store.append("r", [row("r", 0)])
    folder = tmp_path / "r" / "episodes"
    mode = folder.stat().st_mode
    folder.chmod(0o555)
    try:
        with pytest.raises(OSError):
            store.append("r", [row("r", 1)])
    finally:
        folder.chmod(mode)
    assert store.append("r", [row("r", 1)]) == 1
    assert replicates(store, "r") == [0, 1]


def test_a3_a_part_removed_by_hand_frees_its_keys_as_today(tmp_path: Path) -> None:
    store = Store(tmp_path)
    make_run(store, "r")
    for i in range(4):
        store.append("r", [row("r", i)])
    parts(tmp_path, "r")[2].unlink()
    assert store.append("r", [row("r", 2)]) == 1
    assert replicates(store, "r") == [0, 1, 2, 3]


def test_a3_a_run_removed_and_made_again_by_another_store_is_checked_against_what_it_holds_now(tmp_path: Path) -> None:
    """R1: a name that now holds another file is another part. Store ``mine`` stored replicates 0
    to 2; another store removes the run, opens it again under the same id and stores 10 to 12, in
    parts with the same three names. ``mine`` must refuse 11 and take 1."""
    mine, theirs = Store(tmp_path), Store(tmp_path)
    make_run(mine, "r")
    for i in range(3):
        mine.append("r", [row("r", i)])
    shutil.rmtree(tmp_path / "r")
    time.sleep(0.01)  # a different modification time even on a coarse clock
    make_run(theirs, "r")
    for i in (10, 11, 12):
        theirs.append("r", [row("r", i)])
    assert sorted(p.name for p in parts(tmp_path, "r")) == ["part-00000.parquet", "part-00001.parquet", "part-00002.parquet"]
    with pytest.raises(StoreError) as refused:
        mine.append("r", [row("r", 11)])
    assert type(refused.value).__name__ == "DuplicateEpisode"
    assert mine.append("r", [row("r", 1)]) == 1
    assert replicates(mine, "r") == [1, 10, 11, 12]


def test_a3_a_run_removed_and_made_again_through_the_same_store_starts_with_no_keys(tmp_path: Path) -> None:
    store = Store(tmp_path)
    make_run(store, "r")
    for i in range(3):
        store.append("r", [row("r", i)])
    shutil.rmtree(tmp_path / "r")
    make_run(store, "r")
    assert store.append("r", [row("r", 0), row("r", 1)]) == 2
    assert replicates(store, "r") == [0, 1]


def test_a3_two_runs_in_one_store_keep_their_keys_apart(tmp_path: Path) -> None:
    store = Store(tmp_path)
    make_run(store, "a")
    make_run(store, "b")
    store.append("a", [row("a", 0)])
    assert store.append("b", [row("b", 0)]) == 1
    with pytest.raises(StoreError):
        store.append("a", [row("a", 0)])


# ---------- A4: a run killed part-way ----------

_WRITER = """
import sys
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store
s = Store(sys.argv[1])
s.create_run(RunManifest(run_id="r", target_id="t", t_unit="seconds", run_salt="s",
                         axis_types={"case": "categorical"}, backend="b", environment={}))
for i in range(100000):
    s.append("r", [EpisodeRecord.from_episode(Episode(outcome="ok", t=1.0, horizon=30.0), run_id="r",
                   config={"case": "c"}, seed=1000 + i, replicate_index=i, wall_time=0.01, backend_meta={})])
    print(i + 1, flush=True)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL")
def test_a4_a_writer_killed_part_way_keeps_every_row_whose_append_returned(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONUNBUFFERED": "1"}
    child = subprocess.Popen([sys.executable, "-c", _WRITER, str(tmp_path)], env=env, stdout=subprocess.PIPE, text=True)
    assert child.stdout is not None
    returned = 0
    deadline = time.monotonic() + 120
    try:
        while returned < 150 and time.monotonic() < deadline:
            line = child.stdout.readline()
            if not line:
                break
            returned = int(line)
    finally:
        os.kill(child.pid, signal.SIGKILL)
        child.wait(timeout=30)
    assert returned >= 150, f"the writer stored {returned} rows before the deadline"
    store = Store(tmp_path)
    got = replicates(store, "r")
    assert got[:returned] == list(range(returned)), "a row whose append returned is missing"
    assert got == list(range(len(got))) and len(got) in (returned, returned + 1)
    assert store.count("r") == len(got)
    assert store.missing("r", [(row("r", i).config_hash, i) for i in range(len(got) + 3)]) == [
        (row("r", i).config_hash, i) for i in range(len(got), len(got) + 3)
    ]
    for i in range(len(got), len(got) + 3):
        assert store.append("r", [row("r", i)]) == 1
    assert replicates(store, "r") == list(range(len(got) + 3))


# ---------- A5: what does not change ----------


def test_a5_a_one_row_append_writes_one_part_one_past_the_highest_and_touches_no_other(tmp_path: Path) -> None:
    """Part names as today, a gap in the numbering included: the next is one past the highest."""
    store = Store(tmp_path)
    make_run(store, "r")
    forge_parts(tmp_path, "r", 4)
    shutil.move(str(parts(tmp_path, "r")[-1]), str(tmp_path / "r" / "episodes" / "part-00009.parquet"))
    after: dict[str, str] = {}
    for i in (4, 5):
        before = episodes_listing(tmp_path, "r")
        assert store.append("r", [row("r", i)]) == 1
        after = episodes_listing(tmp_path, "r")
        new = sorted(set(after) - set(before))
        assert len(new) == 1 and {k: after[k] for k in before} == before
        assert new[0] == f"part-{int(max(before)[len('part-') : -len('.parquet')]) + 1:05d}.parquet"
    assert sorted(after) == ["part-00000.parquet", "part-00001.parquet", "part-00002.parquet", "part-00009.parquet", "part-00010.parquet", "part-00011.parquet"]


@pytest.mark.parametrize("which", ["quickstart_before", "pre_split"])
def test_a5_a_run_an_earlier_build_stored_reads_as_it_did_and_takes_one_row_appends(which: str, tmp_path: Path) -> None:
    """A 0.0.1 run (the quickstart's, in many parts; and one in parts written before the trace's
    two columns), reopened as a run stopped early would be: its rows read back as before, it takes
    one-row appends, and every part it had keeps its bytes."""
    run_id = OLD_RUNS[which]
    shutil.copytree(OLD / "store" / run_id, tmp_path / run_id)
    manifest = tmp_path / run_id / "manifest.json"
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["status"] = "partial"
    manifest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    store = Store(tmp_path)
    before_rows = store.read(run_id)
    before_files = episodes_listing(tmp_path, run_id)
    config = {"pf_a5_new_condition": "x"}
    for i in range(3):
        assert store.append(run_id, [row(run_id, i, config=config)]) == 1
    after_files = episodes_listing(tmp_path, run_id)
    assert {k: after_files[k] for k in before_files} == before_files and len(after_files) == len(before_files) + 3
    after_rows = store.read(run_id)
    old = after_rows[after_rows["config_hash"].isin(set(before_rows["config_hash"]))].reset_index(drop=True)
    assert old.drop(columns=["case_id"], errors="ignore").to_json() == before_rows.drop(columns=["case_id"], errors="ignore").to_json()
    assert len(after_rows) == len(before_rows) + 3
    with pytest.raises(StoreError):
        store.append(run_id, [row(run_id, 1, config=config)])
    first = before_rows.iloc[0]
    with pytest.raises(StoreError):
        Store(tmp_path).append(
            run_id,
            [EpisodeRecord(run_id=run_id, config_hash=str(first["config_hash"]), config=dict(first["config"]), seed=1,
                           replicate_index=int(first["replicate_index"]), outcome="ok", t=1.0, horizon=30.0, confidence=None,
                           meta={}, error=None, wall_time=0.01, backend_meta={})],
        )


def test_a5_the_parts_read_as_a_sibling_reads_them(tmp_path: Path) -> None:
    """Poisson Tasks' own Prove check reads a run by globbing ``episodes/part-*.parquet`` in name
    order and reading each with plain pyarrow (``scripts/release/prove_e2e.py``, ``STORE``)."""
    store = Store(tmp_path)
    make_run(store, "r")
    for i in range(8):
        store.append("r", [row("r", i)])
    rows: list[dict[str, Any]] = []
    for part in sorted((tmp_path / "r" / "episodes").glob("part-*.parquet")):
        rows.extend(pq.read_table(part).to_pylist())
    assert [r["replicate_index"] for r in rows] == list(range(8))
    assert all(r["outcome"] == "ok" and json.loads(r["meta"]) == {} and r["error"] is None for r in rows)
