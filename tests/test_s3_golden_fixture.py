"""Frozen tests for the lattice fixture (``tests/lattice.py``), the pair the suite generates itself.

Every test runs against the generated store through the ``lattice_store`` fixture in
conftest.py, and checks it against the design (``lattice.DESIGN``), which is written down
before any row is generated. The two exceptions are I9 and I10, which exercise the
generator itself into a tmp_path: two independent writes are byte for byte the same and the
same as the store handed out, and the generator refuses an inconsistent design and a store
that disagrees with its digests.

Generator contract assumed by I9 and I10:

    lattice.write(<dir>) -> {relative path: sha256}

writes <dir>/lattice-a and <dir>/lattice-b (a manifest and one part each) and returns each
file's digest; ``lattice.root()`` hands out a store only when every file matches the digests
it wrote (and no other file or folder exists), rebuilds it otherwise while the session has not
checked it (``lattice.CHECKED``), and refuses it once the session has.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from poisson_prove.store import Store

import lattice

RUNS = [lattice.RUN_A, lattice.RUN_B]
CELLS = 72
SEEDS_PER_CELL = 32
ROWS_PER_RUN = CELLS * SEEDS_PER_CELL
HORIZON_S = 5.0
#: Each run's share of ``tripped`` in percent, to one decimal, from the design's counts.
DESIGN_TRIPPED_PCT = {lattice.RUN_A: 76.9, lattice.RUN_B: 60.5}
DESIGN_TRIPPED = {lattice.RUN_A: 1771, lattice.RUN_B: 1394}
DESIGN_SAFER, DESIGN_WORSE = 22, 0
GAIN_GRID = [round(0.1 * k, 1) for k in range(1, 13)]
LOAD_GRID = [10.0, 20.0, 30.0, 40.0, 50.0, 100.0]


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def frames(lattice_store: Store) -> dict[str, pd.DataFrame]:
    return {run_id: lattice_store.read(run_id) for run_id in RUNS}


def _by_cell(rows: list[dict]) -> dict[tuple[float, float], dict[int, dict]]:
    out: dict[tuple[float, float], dict[int, dict]] = {}
    for row in rows:
        out.setdefault((row["config"]["gain"], row["config"]["load"]), {})[row["replicate_index"]] = row
    return out


# ---------- I1: runs ----------


def test_i1_runs_are_exactly_a_and_b(lattice_store: Store) -> None:
    assert lattice_store.runs() == RUNS == ["lattice-a", "lattice-b"]


# ---------- I2: shape ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i2_row_cell_and_replicate_counts(frames: dict[str, pd.DataFrame], run_id: str) -> None:
    df = frames[run_id]
    assert len(df) == ROWS_PER_RUN == lattice.ROWS
    assert df["config_hash"].nunique() == CELLS == lattice.CELLS
    per_cell = df.groupby("config_hash")["replicate_index"]
    assert (per_cell.size() == SEEDS_PER_CELL).all()
    expected = list(range(SEEDS_PER_CELL))
    assert per_cell.apply(lambda s: sorted(s) == expected).all()


# ---------- I3: manifests ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i3_manifest_complete_and_seconds(lattice_store: Store, run_id: str) -> None:
    m = lattice_store.manifest(run_id)
    assert m.status == "complete"
    assert m.t_unit == "seconds"


def test_i3_manifests_pairable_salt_and_distinct_target(lattice_store: Store) -> None:
    m0, m1 = lattice_store.manifest(lattice.RUN_A), lattice_store.manifest(lattice.RUN_B)
    assert m0.run_salt == m1.run_salt == lattice.SALT
    assert m0.target_id != m1.target_id
    assert (m0.target_id, m1.target_id) == (lattice.TARGET_A, lattice.TARGET_B)


# ---------- I4: pairing ----------


def test_i4_seeds_paired_across_runs(frames: dict[str, pd.DataFrame]) -> None:
    key = ["config_hash", "replicate_index"]
    v0 = frames[lattice.RUN_A].set_index(key)["seed"]
    v1 = frames[lattice.RUN_B].set_index(key)["seed"]
    assert v0.index.is_unique and v1.index.is_unique
    assert set(v0.index) == set(v1.index)
    aligned = v1.reindex(v0.index)
    assert not aligned.isna().any()
    assert (v0.to_numpy() == aligned.to_numpy()).all()
    assert v0.nunique() == ROWS_PER_RUN, "pairing is vacuous if seeds are not distinct"


# ---------- I5: row-level invariants ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i5_row_level_invariants(frames: dict[str, pd.DataFrame], run_id: str) -> None:
    df = frames[run_id]
    assert df["error"].isna().all()
    assert set(df["outcome"]) <= {lattice.EVENT, lattice.OTHER}
    assert (df["horizon"] == HORIZON_S).all()
    assert (df["t"] <= HORIZON_S).all()
    assert (df["t"] >= 0.0).all()
    survivors = df.loc[df["outcome"] == lattice.OTHER, "t"]
    assert (survivors == HORIZON_S).all()
    assert df["confidence"].isna().all()
    # Every trip is before the horizon, on the generator's 0.02 s step.
    trips = df.loc[df["outcome"] == lattice.EVENT, "t"]
    assert (trips < HORIZON_S).all()
    assert all(abs(t / lattice.STEP - round(t / lattice.STEP)) < 1e-9 for t in trips)


# ---------- I6: the design's tripped fraction ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i6_tripped_fraction_rounds_to_design(
    frames: dict[str, pd.DataFrame], run_id: str
) -> None:
    df = frames[run_id]
    assert int((df["outcome"] == lattice.EVENT).sum()) == lattice.tripped_total(run_id) == DESIGN_TRIPPED[run_id]
    pct = 100.0 * float((df["outcome"] == lattice.EVENT).mean())
    assert round(pct, 1) == round(100.0 * lattice.tripped_total(run_id) / lattice.ROWS, 1) == DESIGN_TRIPPED_PCT[run_id]


# ---------- I7: config grid ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i7_config_grid_exact(frames: dict[str, pd.DataFrame], run_id: str) -> None:
    configs = list(frames[run_id]["config"])
    assert all(set(c) == {lattice.X, lattice.Y} for c in configs)
    observed = {(c["gain"], c["load"]) for c in configs}
    expected = {(gain, load) for gain in GAIN_GRID for load in LOAD_GRID}
    assert observed == expected == {(c.gain, c.load) for c in lattice.design_cells()}
    assert len(expected) == CELLS
    assert (tuple(GAIN_GRID), tuple(LOAD_GRID)) == (lattice.GAIN, lattice.LOAD)


# ---------- I8: the design's own consistency checks ----------


def test_i8_design_reference_diff() -> None:
    # The design's flagged conditions under scipy's Fisher test and one BH family over all 72.
    assert lattice.directions(lattice.fisher()) == (DESIGN_SAFER, DESIGN_WORSE)
    # Every condition's stored rows hold exactly the design's counts and pairing, read with
    # pyarrow alone: trips per run, trips in both, in the before run only, in the after run only.
    a, b = _by_cell(lattice.rows(lattice.RUN_A)), _by_cell(lattice.rows(lattice.RUN_B))
    for cell in lattice.design_cells():
        ra, rb = a[(cell.gain, cell.load)], b[(cell.gain, cell.load)]
        assert sorted(ra) == sorted(rb) == list(range(lattice.N))
        ta = {r for r, row in ra.items() if row["outcome"] == lattice.EVENT}
        tb = {r for r, row in rb.items() if row["outcome"] == lattice.EVENT}
        assert (len(ta), len(tb)) == (cell.tripped_a, cell.tripped_b), cell
        assert (len(ta & tb), len(ta - tb), len(tb - ta)) == (cell.both, cell.before_only, cell.after_only), cell
        for r in ta & tb:
            if cell.timing == "same":
                assert rb[r]["t"] == ra[r]["t"], (cell, r)
            elif cell.timing == "sooner":
                assert abs(rb[r]["t"] - round(ra[r]["t"] * lattice.SOONER / lattice.STEP) * lattice.STEP) < 1e-9, (cell, r)
        assert all(ra[r]["seed"] == rb[r]["seed"] for r in ra)
        assert {row["config_hash"] for row in ra.values()} == {lattice.config_hash(cell.config)}


def test_i8_design_grid_and_tripped_pct() -> None:
    design = list(lattice.design_cells())
    assert {
        "cells": len(design),
        "seeds_per_cell": lattice.N,
        "rollouts_per_run": len(design) * lattice.N,
    } == {
        "cells": CELLS,
        "seeds_per_cell": SEEDS_PER_CELL,
        "rollouts_per_run": ROWS_PER_RUN,
    }
    for run_id in RUNS:
        assert round(100.0 * lattice.tripped_total(run_id) / lattice.ROWS, 1) == DESIGN_TRIPPED_PCT[run_id]
    # tripped is the more frequent outcome in each run and in the two together.
    assert all(2 * lattice.tripped_total(run_id) > lattice.ROWS for run_id in RUNS)
    # No run carries an errored row (the drift guard's "diverged" count).
    for run_id in RUNS:
        assert all(row["error"] is None for row in lattice.rows(run_id))


# ---------- I9: deterministic generation ----------


def test_i9_generator_is_deterministic(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    digests = [lattice.write(out) for out in (a, b)]
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert files_a and files_a == files_b
    assert [p for p in files_a if p.suffix == ".parquet"]
    for rel in files_a:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel
    assert digests[0] == digests[1] == {
        str(rel): hashlib.sha256((a / rel).read_bytes()).hexdigest() for rel in files_a
    }


def test_i9_generated_store_matches_fresh_build(
    lattice_store: Store, frames: dict[str, pd.DataFrame], tmp_path: Path
) -> None:
    assert lattice.intact()
    out = tmp_path / "fresh"
    digests = lattice.write(out)
    fresh = Store(out)
    assert fresh.runs() == RUNS
    for run_id in RUNS:
        pd.testing.assert_frame_equal(fresh.read(run_id), frames[run_id])
        assert json.loads((out / run_id / "manifest.json").read_text()) == lattice.manifest(run_id)
    root = lattice.root()
    assert digests == json.loads((root.parent / "SHA256SUMS.json").read_text())
    for rel in digests:
        assert (out / rel).read_bytes() == (root / rel).read_bytes(), rel


# ---------- I10: drift guard ----------


def test_i10_generator_refuses_an_inconsistent_design_or_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A condition whose counts cannot pair (more trips in both runs than the before run has, or
    # more after-only trips than the after run has) is refused when the design is drawn up.
    for active, after_only in (
        ({**lattice._ACTIVE, 0.1: ((10, 14), (24, 10), (22, 6))}, dict(lattice._AFTER_ONLY)),
        (dict(lattice._ACTIVE), {**lattice._AFTER_ONLY, (1.2, 10.0): 2}),
        ({**lattice._ACTIVE, 0.1: ((33, 14), (24, 10), (22, 6))}, dict(lattice._AFTER_ONLY)),
    ):
        with monkeypatch.context() as m:
            m.setattr(lattice, "_ACTIVE", active)
            m.setattr(lattice, "_AFTER_ONLY", after_only)
            with pytest.raises(AssertionError):
                lattice._design()
    assert lattice._design() == lattice.DESIGN
    # A store that disagrees with the digests it was written with is never handed out. Before the
    # session has checked it (a crash or an earlier session left it), it is rebuilt and the
    # tampered bytes are gone; once the session has checked it, the change was a test's, so it is
    # refused, its bytes left in place, and the session-end check fails. Built under tmp_path so
    # the session's store is untouched.
    monkeypatch.setattr(lattice.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.delenv(lattice.CHECKED, raising=False)
    monkeypatch.setattr(lattice, "_ROOT", [])
    store = lattice.root()
    assert store.parent.parent == tmp_path and lattice.intact() and lattice.unchanged()
    part = store / lattice.RUN_A / "episodes" / "part-00000.parquet"
    good = part.read_bytes()
    sums = store.parent / "SHA256SUMS.json"
    written = sums.read_bytes()

    def tampered(change: Any) -> None:
        change()
        assert not lattice.intact() and not lattice.unchanged()
        monkeypatch.setenv(lattice.CHECKED, "1")
        monkeypatch.setattr(lattice, "_ROOT", [])
        with pytest.raises(RuntimeError, match="changed during this test session"):
            lattice.root()
        assert not lattice.unchanged()
        monkeypatch.delenv(lattice.CHECKED)
        monkeypatch.setattr(lattice, "_ROOT", [])
        again = lattice.root()
        assert again == store and lattice.intact() and lattice.unchanged()
        assert part.read_bytes() == good and sums.read_bytes() == written

    def flip_bytes() -> None:
        part.write_bytes(good[:-8] + bytes(8))
        assert part.read_bytes() != good

    tampered(flip_bytes)
    tampered(lambda: (store / lattice.RUN_B / "extra.json").write_text("{}"))
    tampered(lambda: (store / lattice.RUN_B / "empty").mkdir())
    tampered(lambda: sums.write_text(written.decode()[:-7]))
    # A store the session checked and that is gone has changed too.
    monkeypatch.setenv(lattice.CHECKED, "1")
    renamed = store.with_name("moved")
    store.rename(renamed)
    assert not lattice.unchanged()
    renamed.rename(store)
    assert lattice.unchanged()
    assert not list(store.parent.glob(".store-*"))
