"""Oracle for M3: the local executor.

Seed derivation, run ids, plan/pair/resume, pre-flight text, batched runs, per-episode
error capture, timeout under fork, caps, progress, paired reproducibility, and trace
retention. Every store lives under tmp_path; no fixture from S3 is used.

Test rollouts live at module top level so they pickle by reference under fork. The ones
that need to single out a pair read module-level sets of seeds (``RAISE_SEEDS``,
``SLEEP_SEEDS``) that a test fills in from its plan before running; a forked child
inherits them. An autouse fixture clears them between tests.

Conventions the oracle fixes for the implementation session:

- ``derive_seed`` is ``int.from_bytes(sha256(f"{salt}:{hash}:{k}").digest()[:4], "big")``.
  The spec says "first 4 bytes as unsigned int" without naming byte order; big-endian is
  pinned here by a reference-implementation test.
- ``new_run_id`` matches ``^\\d{8}T\\d{6}Z-[0-9a-fA-F]{4}$``; ``new_run_salt`` is 16 hex.
- ``backend_meta["i"]`` is the execution index within one ``run_local`` call, starting
  at 0 in plan-pair order. Only fresh runs are checked for it.
- ``max_rollouts=N`` stores exactly N rows: the partial batch holding the Nth episode is
  flushed and the run stops there.
- ``Episode`` carries a ``MappingProxyType`` and does not pickle; a forked child must
  send ``episode.to_dict()`` (or the record) back, not the ``Episode`` itself.
- The pre-flight MDE is compared to ``mde_two_proportion(0.5, N, N)`` to 5e-3, so two
  decimals of formatting are fine.
"""

import dataclasses
import hashlib
import math
import multiprocessing
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from poisson_prove.diff import mde_two_proportion
from poisson_prove.episode import Episode
from poisson_prove.executor import (
    ExecutorError,
    NotResumable,
    Pair,
    PairMismatch,
    Plan,
    RunSummary,
    derive_seed,
    new_run_id,
    new_run_salt,
    plan,
    preflight,
    run_local,
)
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import Store, config_hash

HORIZON = 10.0
CELLS = ({"x": 0.1}, {"x": 0.2}, {"x": 0.3})
REPLICATES = 4
TOTAL = len(CELLS) * REPLICATES
SALT_A = "salt-a"
SALT_B = "salt-b"
TARGET = "policy@test"
T_UNIT = "steps"
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-fA-F]{4}$")

# ---------- module-level rollouts (pickle by reference under fork) ----------

RAISE_SEEDS: set[int] = set()
SLEEP_SEEDS: set[int] = set()
CALLS: list[int] = []


def _outcome(cfg: dict[str, Any], seed: int) -> str:
    return "fell" if (seed + int(cfg["x"] * 10)) % 3 == 0 else "survived"


def deterministic_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    outcome = _outcome(cfg, seed)
    return Episode(outcome=outcome, t=3.0 if outcome == "fell" else HORIZON, horizon=HORIZON)


def raising_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    if seed in RAISE_SEEDS:
        raise ValueError("boom")
    return deterministic_rollout(cfg, seed)


def wrong_type_rollout(cfg: dict[str, Any], seed: int) -> Any:
    return {"outcome": "fell", "t": 1.0, "horizon": HORIZON}


def sleeping_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    if seed in SLEEP_SEEDS:
        time.sleep(3.0)
    return deterministic_rollout(cfg, seed)


def mutating_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    episode = deterministic_rollout(cfg, seed)
    cfg["x"] = 999.0
    cfg["injected"] = True
    return episode


def trace_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    outcome = _outcome(cfg, seed)
    return Episode(
        outcome=outcome,
        t=3.0 if outcome == "fell" else HORIZON,
        horizon=HORIZON,
        meta={"trace": ["step-a", "step-b"], "k": 1},
    )


def counting_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    CALLS.append(seed)
    return deterministic_rollout(cfg, seed)


@pytest.fixture(autouse=True)
def _reset_rollout_state():
    RAISE_SEEDS.clear()
    SLEEP_SEEDS.clear()
    CALLS.clear()
    yield
    RAISE_SEEDS.clear()
    SLEEP_SEEDS.clear()
    CALLS.clear()


# ---------- helpers ----------


def _ref_seed(salt: str, h: str, k: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{salt}:{h}:{k}".encode()).digest()[:4], "big")


def _spec(
    *,
    cells: tuple[dict[str, Any], ...] = CELLS,
    replicates: int = REPLICATES,
    target_id: str = TARGET,
    t_unit: str = T_UNIT,
    retain: tuple[str, ...] | None = None,
) -> SweepSpec:
    return SweepSpec.build(
        [dict(c) for c in cells],
        replicates=replicates,
        target_id=target_id,
        t_unit=t_unit,
        retain_traces_for=retain,
    )


def _store(tmp_path: Path, name: str = "store") -> Store:
    return Store(tmp_path / name)


def _all_pairs(spec: SweepSpec) -> list[tuple[str, int]]:
    return [(h, k) for h in spec.cells() for k in range(spec.replicates)]


def _keyed(df: pd.DataFrame) -> pd.DataFrame:
    return df.set_index(["config_hash", "replicate_index"]).sort_index()


def _pair_index(p: Plan, cell: int, replicate: int) -> int:
    return cell * p.spec.replicates + replicate


def _parts(store_root: Path, run_id: str) -> list[Path]:
    return sorted((store_root / run_id / "episodes").glob("part-*.parquet"))


# ---------- I1: derive_seed ----------


def test_i1_derive_seed_matches_reference_formula() -> None:
    for salt, h, k in [("s", "0" * 16, 0), ("salt-a", config_hash({"x": 0.1}), 3), ("z", "ab" * 8, 10**6)]:
        assert derive_seed(salt, h, k) == _ref_seed(salt, h, k)


@settings(max_examples=200)
@given(
    salt=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=20),
    h=st.text(alphabet="0123456789abcdef", min_size=16, max_size=16),
    k=st.integers(min_value=0, max_value=10**6),
)
def test_i1_derive_seed_deterministic_in_range_and_sensitive(salt: str, h: str, k: int) -> None:
    seed = derive_seed(salt, h, k)
    assert type(seed) is int
    assert 0 <= seed < 2**32
    assert derive_seed(salt, h, k) == seed
    assert derive_seed(salt + "x", h, k) != seed
    assert derive_seed(salt, h[:-1] + ("0" if h[-1] != "0" else "1"), k) != seed
    assert derive_seed(salt, h, k + 1) != seed


def test_i1_derive_seed_no_collisions_across_ten_thousand_inputs() -> None:
    hashes = [config_hash({"i": i}) for i in range(100)]
    seeds = [derive_seed(s, h, k) for s in (SALT_A, SALT_B) for h in hashes for k in range(50)]
    assert len(seeds) == 10_000
    assert len(set(seeds)) == 10_000


# ---------- I2: run ids and salts ----------


def test_i2_new_run_id_shape_and_uniqueness() -> None:
    a, b = new_run_id(TARGET), new_run_id(TARGET)
    for rid in (a, b):
        assert RUN_ID_RE.match(rid), rid
        assert not any(ch in rid for ch in "/\\ :")
        assert rid[15] == "Z" and rid[16] == "-" and len(rid[:16]) == 16
    assert a != b


def test_i2_new_run_salt_is_sixteen_hex_and_unique() -> None:
    a, b = new_run_salt(), new_run_salt()
    assert re.fullmatch(r"[0-9a-f]{16}", a) and re.fullmatch(r"[0-9a-f]{16}", b)
    assert a != b


# ---------- I3: fresh plan ----------


def test_i3_fresh_plan_pairs_order_seeds_and_flags(tmp_path: Path) -> None:
    spec = _spec()
    p = plan(spec, _store(tmp_path))
    assert isinstance(p, Plan) and p.spec is spec
    assert p.backend == "local" and p.resumed is False and p.already_stored == 0
    assert RUN_ID_RE.match(p.run_id) and re.fullmatch(r"[0-9a-f]{16}", p.run_salt)
    assert len(p.pairs) == len(spec.configs) * spec.replicates == TOTAL
    cells = spec.cells()
    for i, pair in enumerate(p.pairs):
        assert isinstance(pair, Pair)
        assert pair.config == spec.configs[i // spec.replicates]
        assert pair.config_hash == cells[i // spec.replicates] == config_hash(pair.config)
        assert pair.replicate_index == i % spec.replicates
        assert pair.seed == derive_seed(p.run_salt, pair.config_hash, pair.replicate_index)


def test_i3_fresh_plan_honors_explicit_salt_and_backend(tmp_path: Path) -> None:
    p = plan(_spec(), _store(tmp_path), run_salt=SALT_A, backend="local")
    assert p.run_salt == SALT_A
    assert [pair.seed for pair in p.pairs] == [_ref_seed(SALT_A, h, k) for h, k in _all_pairs(p.spec)]


def test_i3_fresh_plan_does_not_touch_the_store(tmp_path: Path) -> None:
    store = _store(tmp_path)
    plan(_spec(), store)
    assert store.runs() == []


# ---------- I4: pair_with ----------


def test_i4_pair_with_inherits_salt_and_seeds(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = plan(_spec(), store)
    run_local(first, deterministic_rollout, store)
    second = plan(_spec(), store, pair_with=first.run_id)
    assert second.run_salt == first.run_salt
    assert second.run_id != first.run_id
    assert second.resumed is False and second.already_stored == 0
    assert [(q.config_hash, q.replicate_index, q.seed) for q in second.pairs] == [
        (q.config_hash, q.replicate_index, q.seed) for q in first.pairs
    ]


def test_i4_pair_with_t_unit_mismatch_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = plan(_spec(t_unit="steps"), store)
    run_local(first, deterministic_rollout, store)
    with pytest.raises(PairMismatch):
        plan(_spec(t_unit="seconds"), store, pair_with=first.run_id)


# ---------- I5: resume ----------


def test_i5_resume_reuses_id_and_salt_and_pairs_equal_missing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    first = plan(spec, store, run_salt=SALT_A)
    run_local(first, deterministic_rollout, store, max_rollouts=5)
    resumed = plan(spec, store, resume=first.run_id)
    assert resumed.run_id == first.run_id
    assert resumed.run_salt == SALT_A
    assert resumed.resumed is True
    assert resumed.already_stored == 5
    expected = store.missing(first.run_id, _all_pairs(spec))
    assert [(q.config_hash, q.replicate_index) for q in resumed.pairs] == expected
    assert len(resumed.pairs) == TOTAL - 5
    for q in resumed.pairs:
        assert q.seed == derive_seed(SALT_A, q.config_hash, q.replicate_index)


def test_i5_resume_of_complete_run_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    first = plan(spec, store)
    run_local(first, deterministic_rollout, store)
    with pytest.raises(NotResumable):
        plan(spec, store, resume=first.run_id)


@pytest.mark.parametrize("change", ["target_id", "axis_types", "t_unit"])
def test_i5_resume_with_mismatched_spec_raises(tmp_path: Path, change: str) -> None:
    store = _store(tmp_path)
    first = plan(_spec(), store)
    run_local(first, deterministic_rollout, store, max_rollouts=3)
    if change == "target_id":
        other = _spec(target_id="other@target")
    elif change == "t_unit":
        other = _spec(t_unit="seconds")
    else:
        other = SweepSpec.build(
            [dict(c) for c in CELLS],
            replicates=REPLICATES,
            target_id=TARGET,
            t_unit=T_UNIT,
            axis_types={"x": "categorical"},
        )
    with pytest.raises(NotResumable):
        plan(other, store, resume=first.run_id)


def test_i5_resume_is_exclusive_with_salt_and_pair_with(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    first = plan(spec, store)
    run_local(first, deterministic_rollout, store, max_rollouts=3)
    with pytest.raises(ExecutorError):
        plan(spec, store, resume=first.run_id, run_salt=SALT_A)
    with pytest.raises(ExecutorError):
        plan(spec, store, resume=first.run_id, pair_with=first.run_id)
    with pytest.raises(ExecutorError):
        plan(spec, store, run_salt=SALT_A, pair_with=first.run_id)


# ---------- I6: well-behaved run ----------


def test_i6_well_behaved_run_completes_and_stores_every_pair(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    p = plan(spec, store)
    summary = run_local(p, deterministic_rollout, store)
    assert isinstance(summary, RunSummary)
    assert summary.run_id == p.run_id
    assert summary.n_ok == TOTAL and summary.n_errored == 0 and summary.n_timeout == 0
    assert summary.stopped_by is None and summary.complete is True
    assert summary.wall_time > 0
    assert store.manifest(p.run_id).status == "complete"
    df = store.read(p.run_id)
    assert len(df) == TOTAL
    assert df["error"].isna().all() and df["outcome"].notna().all()
    keyed = _keyed(df)
    for q in p.pairs:
        row = keyed.loc[(q.config_hash, q.replicate_index)]
        assert int(row["seed"]) == q.seed
        assert row["config"] == q.config
        assert row["outcome"] == _outcome(q.config, q.seed)


# ---------- I7: raising rollout ----------


def test_i7_raising_rollout_records_traceback_and_run_completes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = plan(_spec(), store)
    bad = p.pairs[_pair_index(p, cell=1, replicate=2)]
    RAISE_SEEDS.add(bad.seed)
    summary = run_local(p, raising_rollout, store)
    assert summary.n_ok == TOTAL - 1 and summary.n_errored == 1 and summary.n_timeout == 0
    assert summary.complete is True
    assert store.manifest(p.run_id).status == "complete"
    keyed = _keyed(store.read(p.run_id))
    row = keyed.loc[(bad.config_hash, bad.replicate_index)]
    assert pd.isna(row["outcome"]) and pd.isna(row["t"])
    assert "ValueError" in row["error"] and "boom" in row["error"]
    others = keyed.drop(index=(bad.config_hash, bad.replicate_index))
    assert others["error"].isna().all() and others["outcome"].notna().all()
    assert len(keyed) == TOTAL


# ---------- I8: wrong-type return ----------


def test_i8_wrong_type_return_is_recorded_and_run_completes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = plan(_spec(), store)
    summary = run_local(p, wrong_type_rollout, store)
    assert summary.n_errored == TOTAL and summary.n_ok == 0
    assert summary.complete is True
    df = store.read(p.run_id)
    assert len(df) == TOTAL
    assert df["outcome"].isna().all()
    assert all("expected Episode" in e for e in df["error"])
    assert all("dict" in e for e in df["error"])


# ---------- I9: timeout (fork only) ----------


@pytest.mark.skipif(not FORK_AVAILABLE, reason="episode_timeout test needs the fork start method")
def test_i9_timeout_kills_one_episode_and_run_continues(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = plan(_spec(), store)
    slow = p.pairs[_pair_index(p, cell=0, replicate=1)]
    SLEEP_SEEDS.add(slow.seed)
    t0 = time.perf_counter()
    summary = run_local(p, sleeping_rollout, store, episode_timeout=0.5)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, elapsed
    assert summary.n_timeout == 1 and summary.n_errored == 1 and summary.n_ok == TOTAL - 1
    assert summary.complete is True
    keyed = _keyed(store.read(p.run_id))
    assert keyed.loc[(slow.config_hash, slow.replicate_index), "error"] == "timeout"
    others = keyed.drop(index=(slow.config_hash, slow.replicate_index))
    assert others["error"].isna().all()
    for q in p.pairs:
        if q.seed != slow.seed:
            assert keyed.loc[(q.config_hash, q.replicate_index), "outcome"] == _outcome(
                q.config, q.seed
            )


# ---------- I10: max_rollouts ----------


@pytest.mark.parametrize("n", [1, 5, TOTAL - 1])
def test_i10_max_rollouts_stops_after_exactly_n(tmp_path: Path, n: int) -> None:
    store = _store(tmp_path)
    p = plan(_spec(), store)
    summary = run_local(p, deterministic_rollout, store, max_rollouts=n)
    assert summary.stopped_by == "max_rollouts"
    assert summary.complete is False
    assert summary.n_ok + summary.n_errored == n
    assert store.manifest(p.run_id).status == "partial"
    df = store.read(p.run_id)
    assert len(df) == n
    executed = [(q.config_hash, q.replicate_index) for q in p.pairs[:n]]
    assert sorted(zip(df["config_hash"], df["replicate_index"], strict=True)) == sorted(executed)


def test_i10_max_rollouts_at_or_above_total_completes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = plan(_spec(), store)
    summary = run_local(p, deterministic_rollout, store, max_rollouts=TOTAL)
    assert summary.stopped_by is None and summary.complete is True
    assert store.manifest(p.run_id).status == "complete"


# ---------- I11: batching and resume ----------


def test_i11_batch_size_controls_part_count(tmp_path: Path) -> None:
    root = tmp_path / "store"
    store = Store(root)
    for b in (1, 5, 64):
        p = plan(_spec(), store)
        run_local(p, deterministic_rollout, store, batch_size=b)
        assert len(_parts(root, p.run_id)) == math.ceil(TOTAL / b)


def test_i11_resume_after_cap_matches_uninterrupted_run(tmp_path: Path) -> None:
    spec = _spec()
    batch = 5
    stop_at = 7

    root_full = tmp_path / "full"
    full_store = Store(root_full)
    full = plan(spec, full_store, run_salt=SALT_A)
    full_summary = run_local(full, deterministic_rollout, full_store, batch_size=batch)
    assert full_summary.complete is True
    assert len(_parts(root_full, full.run_id)) == math.ceil(TOTAL / batch)

    root_part = tmp_path / "partial"
    part_store = Store(root_part)
    first = plan(spec, part_store, run_salt=SALT_A)
    stopped = run_local(first, deterministic_rollout, part_store, max_rollouts=stop_at, batch_size=batch)
    assert stopped.stopped_by == "max_rollouts" and stopped.complete is False
    assert len(_parts(root_part, first.run_id)) == math.ceil(stop_at / batch)
    assert len(part_store.read(first.run_id)) == stop_at

    resumed = plan(spec, part_store, resume=first.run_id)
    assert resumed.already_stored == stop_at and len(resumed.pairs) == TOTAL - stop_at
    finish = run_local(resumed, deterministic_rollout, part_store, batch_size=batch)
    assert finish.complete is True and finish.stopped_by is None
    assert finish.n_ok == TOTAL - stop_at
    assert part_store.manifest(first.run_id).status == "complete"
    assert len(_parts(root_part, first.run_id)) == math.ceil(stop_at / batch) + math.ceil(
        (TOTAL - stop_at) / batch
    )

    cols = ["seed", "outcome", "t", "horizon", "config", "error"]
    a = _keyed(full_store.read(full.run_id))[cols]
    b = _keyed(part_store.read(first.run_id))[cols]
    assert len(a) == len(b) == TOTAL
    pd.testing.assert_frame_equal(a, b)


# ---------- I12: preflight ----------


def _line_with(text: str, token: str) -> str:
    matches = [line for line in text.splitlines() if token in line]
    assert matches, f"{token!r} not found in preflight text:\n{text}"
    return matches[0]


def test_i12_preflight_fresh_plan(tmp_path: Path) -> None:
    spec = _spec()
    p = plan(spec, _store(tmp_path))
    text = preflight(p)
    sweep_line = _line_with(text, "cells")
    for token in ("1 axes", f"{len(spec.configs)} cells", f"N={REPLICATES}", f"{TOTAL} rollouts"):
        assert token in sweep_line, (token, sweep_line)
    backend_line = _line_with(text, "Backend: local")
    assert TARGET in backend_line and T_UNIT in backend_line
    cost_line = _line_with(text, "Cost: $0")
    mde_line = _line_with(text, "MDE at N=")
    assert f"MDE at N={REPLICATES}" in mde_line
    found = re.search(r"MDE at N=\d+[^:]*:\s*([0-9]*\.?[0-9]+)", mde_line)
    assert found, mde_line
    assert abs(float(found.group(1)) - mde_two_proportion(0.5, REPLICATES, REPLICATES)) <= 5e-3
    assert len({sweep_line, backend_line, cost_line, mde_line}) == 4
    assert "Resuming" not in text


def test_i12_preflight_cost_estimate_and_resume_line(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    p = plan(spec, store)
    assert "$12.34" in _line_with(preflight(p, cost_estimate="$12.34"), "Cost:")
    run_local(p, deterministic_rollout, store, max_rollouts=5)
    resumed = plan(spec, store, resume=p.run_id)
    text = preflight(resumed)
    line = _line_with(text, "Resuming")
    assert p.run_id in line
    assert re.search(r"\b5 stored\b", line) and re.search(rf"\b{TOTAL - 5} to run\b", line)


# ---------- I13: config isolation ----------


def test_i13_rollout_gets_a_fresh_dict_each_call(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    p = plan(spec, store)
    originals = [dict(q.config) for q in p.pairs]
    run_local(p, mutating_rollout, store)
    assert [dict(q.config) for q in p.pairs] == originals
    assert [dict(c) for c in spec.configs] == [dict(c) for c in CELLS]
    keyed = _keyed(store.read(p.run_id))
    for q in p.pairs:
        stored = keyed.loc[(q.config_hash, q.replicate_index), "config"]
        assert stored == q.config
        assert "injected" not in stored and stored["x"] != 999.0


# ---------- I14: manifest ----------


def test_i14_manifest_fields_and_environment(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec(retain=("fell",))
    p = plan(spec, store)
    run_local(p, deterministic_rollout, store)
    m = store.manifest(p.run_id)
    assert m.run_id == p.run_id
    assert m.backend == "local"
    assert m.run_salt == p.run_salt
    assert m.target_id == TARGET and m.t_unit == T_UNIT
    assert dict(m.axis_types) == dict(spec.axis_types)
    assert m.retain_traces_for == spec.retain_traces_for == ("fell",)
    env = dict(m.environment)
    for key in ("python", "platform", "poisson_prove_version", "sweep"):
        assert key in env, key
    assert isinstance(env["python"], str) and env["python"]
    assert isinstance(env["platform"], str) and env["platform"]
    assert env["sweep"] == spec.to_dict()


# ---------- I15: wall_time and execution index ----------


def test_i15_wall_time_positive_and_execution_index_recorded(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = plan(_spec(), store)
    run_local(p, deterministic_rollout, store)
    keyed = _keyed(store.read(p.run_id))
    assert (keyed["wall_time"] > 0).all()
    for i, q in enumerate(p.pairs):
        assert keyed.loc[(q.config_hash, q.replicate_index), "backend_meta"]["i"] == i


# ---------- I16: progress ----------


@pytest.mark.parametrize("cap", [None, 5])
def test_i16_on_progress_called_once_per_executed_episode(tmp_path: Path, cap: int | None) -> None:
    store = _store(tmp_path)
    p = plan(_spec(), store)
    calls: list[tuple[int, int]] = []
    run_local(p, deterministic_rollout, store, max_rollouts=cap, on_progress=lambda d, t: calls.append((d, t)))
    n_executed = TOTAL if cap is None else cap
    assert len(calls) == n_executed
    assert [d for d, _ in calls] == list(range(1, n_executed + 1))
    assert all(t == TOTAL for _, t in calls)


# ---------- I17: paired reproducibility ----------


def _outcome_set(store: Store, run_id: str) -> set[tuple[str, int, str, float]]:
    df = store.read(run_id)
    return set(
        zip(df["config_hash"], df["replicate_index"], df["outcome"], df["t"], strict=True)
    )


def test_i17_same_salt_reproduces_and_different_salt_differs(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    runs = {}
    for label, salt in (("a1", SALT_A), ("a2", SALT_A), ("b", SALT_B)):
        p = plan(spec, store, run_salt=salt)
        run_local(p, deterministic_rollout, store)
        runs[label] = _outcome_set(store, p.run_id)
    assert runs["a1"] == runs["a2"]
    assert len(runs["a1"]) == TOTAL
    assert runs["a1"] != runs["b"]


def test_i17_pair_with_reproduces_the_paired_run(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    first = plan(spec, store)
    run_local(first, deterministic_rollout, store)
    second = plan(spec, store, pair_with=first.run_id)
    run_local(second, deterministic_rollout, store)
    assert _outcome_set(store, first.run_id) == _outcome_set(store, second.run_id)


# ---------- I18: refuse to run into a complete run ----------


def test_i18_run_local_refuses_complete_run_before_any_rollout(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    first = plan(spec, store)
    run_local(first, deterministic_rollout, store)
    assert store.manifest(first.run_id).status == "complete"
    stale = dataclasses.replace(plan(spec, store, run_salt=first.run_salt), run_id=first.run_id)
    with pytest.raises(ExecutorError):
        run_local(stale, counting_rollout, store)
    assert CALLS == []
    assert len(store.read(first.run_id)) == TOTAL


# ---------- I19: trace retention ----------


def test_i19_trace_retention_flows_through_to_store(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec(retain=("fell",))
    p = plan(spec, store, run_salt=SALT_A)
    run_local(p, trace_rollout, store)
    df = store.read(p.run_id)
    outcomes = set(df["outcome"])
    assert outcomes == {"fell", "survived"}
    for outcome, meta in zip(df["outcome"], df["meta"], strict=True):
        assert meta["k"] == 1
        if outcome == "fell":
            assert meta["trace"] == ["step-a", "step-b"]
        else:
            assert "trace" not in meta


def test_i19_no_retention_keeps_every_trace(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = plan(_spec(retain=None), store, run_salt=SALT_A)
    run_local(p, trace_rollout, store)
    df = store.read(p.run_id)
    assert all("trace" in meta for meta in df["meta"])
