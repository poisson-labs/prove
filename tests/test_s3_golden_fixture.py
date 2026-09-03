"""Oracle for the S3 Go1 golden fixture.

Every test runs against the committed fixture at tests/fixtures/go1/ through the
``go1_store`` fixture in conftest.py. The two exceptions are I9 and I10, which
invoke the builder against the source manifests into a tmp_path and skip when the
source measurements directory is absent (CI does not have it).

Builder contract assumed by I9 and I10:

    python scripts/build_golden_fixture.py --v0 <manifest> --v1 <manifest> --out <dir>

Exit 0 on success, having written <dir>/go1-v0, <dir>/go1-v1 and <dir>/golden.json.
Non-zero exit with no Parquet written when the computed fell fractions disagree
with the published numbers. The builder must not depend on files that sit next
to the manifests it is given; I10 passes a lone tampered copy.
"""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from proofload.store import Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "go1"
BUILDER = ROOT / "scripts" / "build_golden_fixture.py"

MEASUREMENTS = (
    Path.home() / "code" / "poisson-labs" / "policy-robustness-sweep" / "docs" / "measurements"
)
V0_MANIFEST = MEASUREMENTS / "2026-08-18-g4-v0-32-sweep-manifest.json"
V1_MANIFEST = MEASUREMENTS / "2026-08-18-g4-v1-32-sweep-manifest.json"

RUNS = ["go1-v0", "go1-v1"]
CELLS = 400
SEEDS_PER_CELL = 32
ROWS_PER_RUN = CELLS * SEEDS_PER_CELL
HORIZON_S = 5.0
PUBLISHED_FELL_PCT = {"go1-v0": 62.7, "go1-v1": 52.8}
PUBLISHED_SAFER, PUBLISHED_WORSE = 60, 0
MU_GRID = [round(0.05 * k, 2) for k in range(1, 21)]
PUSH_GRID = [10.0 * k for k in range(1, 21)]

needs_source = pytest.mark.skipif(
    not MEASUREMENTS.is_dir(), reason=f"source measurements dir absent: {MEASUREMENTS}"
)


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def frames(go1_store: Store) -> dict[str, pd.DataFrame]:
    if not FIXTURE_DIR.is_dir():
        pytest.fail(f"committed fixture missing at {FIXTURE_DIR}; build it with {BUILDER.name}")
    return {run_id: go1_store.read(run_id) for run_id in RUNS}


def _golden() -> dict:
    return json.loads((FIXTURE_DIR / "golden.json").read_text())


def _run_builder(v0: Path, v1: Path, out: Path) -> subprocess.CompletedProcess[str]:
    assert BUILDER.is_file(), f"builder missing at {BUILDER}"
    cmd = [sys.executable, str(BUILDER), "--v0", str(v0), "--v1", str(v1), "--out", str(out)]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


# ---------- I1: runs ----------


def test_i1_runs_are_exactly_v0_and_v1(go1_store: Store) -> None:
    assert go1_store.runs() == RUNS


# ---------- I2: shape ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i2_row_cell_and_replicate_counts(frames: dict[str, pd.DataFrame], run_id: str) -> None:
    df = frames[run_id]
    assert len(df) == ROWS_PER_RUN
    assert df["config_hash"].nunique() == CELLS
    per_cell = df.groupby("config_hash")["replicate_index"]
    assert (per_cell.size() == SEEDS_PER_CELL).all()
    expected = list(range(SEEDS_PER_CELL))
    assert per_cell.apply(lambda s: sorted(s) == expected).all()


# ---------- I3: manifests ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i3_manifest_complete_and_seconds(go1_store: Store, run_id: str) -> None:
    m = go1_store.manifest(run_id)
    assert m.status == "complete"
    assert m.t_unit == "seconds"


def test_i3_manifests_pairable_salt_and_distinct_target(go1_store: Store) -> None:
    m0, m1 = go1_store.manifest("go1-v0"), go1_store.manifest("go1-v1")
    assert m0.run_salt == m1.run_salt
    assert m0.target_id != m1.target_id


# ---------- I4: pairing ----------


def test_i4_seeds_paired_across_runs(frames: dict[str, pd.DataFrame]) -> None:
    key = ["config_hash", "replicate_index"]
    v0 = frames["go1-v0"].set_index(key)["seed"]
    v1 = frames["go1-v1"].set_index(key)["seed"]
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
    assert set(df["outcome"]) <= {"fell", "survived"}
    assert (df["horizon"] == HORIZON_S).all()
    assert (df["t"] <= HORIZON_S).all()
    assert (df["t"] >= 0.0).all()
    survivors = df.loc[df["outcome"] == "survived", "t"]
    assert (survivors == HORIZON_S).all()
    assert df["confidence"].isna().all()


# ---------- I6: published fell fraction ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i6_fell_fraction_rounds_to_published(
    frames: dict[str, pd.DataFrame], run_id: str
) -> None:
    df = frames[run_id]
    pct = 100.0 * float((df["outcome"] == "fell").mean())
    assert round(pct, 1) == PUBLISHED_FELL_PCT[run_id]


# ---------- I7: config grid ----------


@pytest.mark.parametrize("run_id", RUNS)
def test_i7_config_grid_exact(frames: dict[str, pd.DataFrame], run_id: str) -> None:
    configs = list(frames[run_id]["config"])
    assert all(set(c) == {"mu", "push_pct_bw"} for c in configs)
    observed = {(c["mu"], c["push_pct_bw"]) for c in configs}
    expected = {(mu, push) for mu in MU_GRID for push in PUSH_GRID}
    assert observed == expected
    assert len(expected) == CELLS


# ---------- I8: golden.json ----------


def test_i8_golden_json_published_diff() -> None:
    golden = _golden()
    assert golden["diff"]["safer"] == PUBLISHED_SAFER
    assert golden["diff"]["worse"] == PUBLISHED_WORSE


def test_i8_golden_json_grid_and_fell_pct() -> None:
    golden = _golden()
    assert golden["grid"] == {
        "cells": CELLS,
        "seeds_per_cell": SEEDS_PER_CELL,
        "rollouts_per_run": ROWS_PER_RUN,
    }
    assert golden["v0"]["fell_pct"] == PUBLISHED_FELL_PCT["go1-v0"]
    assert golden["v1"]["fell_pct"] == PUBLISHED_FELL_PCT["go1-v1"]
    assert golden["v0"]["diverged"] == 0
    assert golden["v1"]["diverged"] == 0


# ---------- I9: deterministic conversion ----------


@needs_source
def test_i9_builder_is_deterministic(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    for out in (a, b):
        r = _run_builder(V0_MANIFEST, V1_MANIFEST, out)
        assert r.returncode == 0, r.stderr
    parts_a = sorted(p.relative_to(a) for p in a.rglob("*.parquet"))
    parts_b = sorted(p.relative_to(b) for p in b.rglob("*.parquet"))
    assert parts_a and parts_a == parts_b
    for rel in parts_a:
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel


@needs_source
def test_i9_committed_fixture_matches_fresh_build(
    go1_store: Store, frames: dict[str, pd.DataFrame], tmp_path: Path
) -> None:
    out = tmp_path / "fresh"
    r = _run_builder(V0_MANIFEST, V1_MANIFEST, out)
    assert r.returncode == 0, r.stderr
    fresh = Store(out)
    assert fresh.runs() == RUNS
    for run_id in RUNS:
        pd.testing.assert_frame_equal(fresh.read(run_id), frames[run_id])
    assert json.loads((out / "golden.json").read_text()) == _golden()


# ---------- I10: drift guard ----------


@needs_source
def test_i10_builder_refuses_on_fell_fraction_drift(tmp_path: Path) -> None:
    manifest = json.loads(V0_MANIFEST.read_text())
    flipped = 0
    for rec in manifest["records"]:
        if rec["fell_time_upz_s"] is not None:
            rec["fell_time_upz_s"] = None
            flipped += 1
            if flipped == 2 * SEEDS_PER_CELL * 4:
                break
    assert flipped / ROWS_PER_RUN > 0.01, "tamper must move the fell fraction past one decimal"
    tampered = tmp_path / "v0-tampered.json"
    tampered.write_text(json.dumps(manifest))
    out = tmp_path / "out"
    r = _run_builder(tampered, V1_MANIFEST, out)
    assert r.returncode != 0
    assert not list(out.rglob("*.parquet"))
    assert not (out / "golden.json").exists()
