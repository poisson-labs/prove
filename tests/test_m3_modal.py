"""Frozen tests for M3: the Modal backend.

Lazy import, the in-container worker contract, mapper-driven orchestration (chunking,
out-of-order flush, infra retry and exhaustion, finally-flush, caps, resume), the modal
manifest, the cost guard, the pre-flight text, ImageSpec validity, and progress. Nothing
here touches the network: the mapper is the seam, and every mapper below runs
``worker_batch`` in-process. Every store lives under tmp_path.

Test rollouts and fake mappers live at module top level. Rollouts are addressed by import
path (``f"{__name__}:<name>"``) so ``worker_batch`` resolves them the way it resolves a
user's rollout inside a container; the ones that single out a job read module-level seed
sets (``RAISE_SEEDS``, ``SLEEP_SEEDS``) that a test fills in from its plan. A forked child
inherits them. An autouse fixture clears them between tests.

Conventions the frozen tests fix for the implementation session:

- The deterministic rollout is the M3-local one, formula included, so I5 compares like with
  like across ``run_local`` and ``run_with_mapper``.
- A ``Job`` is ``(config, seed, i, config_hash, replicate_index)`` with ``i`` the plan index
  (position in ``p.pairs``); ``backend_meta["i"]`` equals that ``i`` regardless of the order
  batches complete in.
- Retries re-submit the *same jobs*. The stateful mappers identify a batch by the tuple of
  its jobs' plan indices, never by the ``batch_index`` of a particular mapper call, so an
  orchestrator may retry in a fresh mapper call, in the same one, or in any grouping.
- An infra failure is *yielded* as ``(batch_index, exception)``; only the I10 mapper raises
  from the generator itself.
- ``on_progress(done, total)``: ``total`` is ``len(p.pairs)``; ``done`` is cumulative
  episodes stored so far and is reported once per completed batch.
- ``n_executed`` for a capped run is ``n_ok + n_errored``, which equals the rows stored.
- I11 is exercised only where the batch holding the Nth episode is not the final batch; the
  edge where a cap lands inside the last batch (every pair executed anyway) is left to the
  implementation to decide between ``complete`` and ``partial``.
- I12 checks ``environment["import_path"]`` for presence only: ``run_with_mapper`` has no
  import path input, so its value on a mapper-driven run is the implementation's call.
- ``ImageSpec.to_dict()`` is JSON-native (lists, not tuples; ``dockerfile`` as ``str``) under
  the field names ``python``, ``pip``, ``apt``, ``dockerfile``, ``local_packages``, ``gpu``, so
  it equals its own JSON round-trip and the manifest's ``environment["image"]``.
- I4 counts every attribute lookup of the rollout name on its module (a module-level
  ``__getattr__`` hook), so resolve ``import_path`` with a single ``getattr`` per call, not a
  ``hasattr`` probe followed by a ``getattr``.
- The cap in I11 may leave the last batch whole or truncated to N rows; only the bounds
  ``N <= rows <= N + batch_size - 1`` and ``ceil(rows / batch_size)`` parts are asserted.
"""

import dataclasses
import importlib
import json
import math
import multiprocessing
import re
import sys
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import poisson_prove
import poisson_prove.executor_modal as executor_modal
from poisson_prove.episode import Episode
from poisson_prove.executor import ExecutorError, Plan, RunSummary, plan, run_local
from poisson_prove.executor_modal import (
    CostGuard,
    ImageSpec,
    Job,
    ModalBackendError,
    ModalNotInstalled,
    ModalOptions,
    ModalTarget,
    Result,
    estimate_cost,
    preflight_modal,
    run_with_mapper,
    worker_batch,
)
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import Store

HORIZON = 10.0
CELLS = ({"x": 0.1}, {"x": 0.2}, {"x": 0.3})
REPLICATES = 4
TOTAL = len(CELLS) * REPLICATES
BATCH = 5
N_BATCHES = math.ceil(TOTAL / BATCH)
TAIL = TOTAL - BATCH * (N_BATCHES - 1)
SALT_A = "salt-a"
TARGET = "policy@test"
T_UNIT = "steps"
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()

DET_PATH = f"{__name__}:deterministic_rollout"
RAISE_PATH = f"{__name__}:raising_rollout"
WRONG_TYPE_PATH = f"{__name__}:wrong_type_rollout"
SLEEP_PATH = f"{__name__}:sleeping_rollout"
MUTATE_PATH = f"{__name__}:mutating_rollout"
COUNTED_PATH = f"{__name__}:counted_rollout"

assert N_BATCHES == 3 and TAIL == 2, "the mapper tests assume batches of 5, 5, 2"

# ---------- module-level rollouts (importable by path; pickle by reference under fork) ----------

RAISE_SEEDS: set[int] = set()
SLEEP_SEEDS: set[int] = set()
RESOLVES: list[str] = []


def _outcome(cfg: dict[str, Any], seed: int) -> str:
    return "fell" if (seed + int(cfg["x"] * 10)) % 3 == 0 else "survived"


def _t(cfg: dict[str, Any], seed: int) -> float:
    return 3.0 if _outcome(cfg, seed) == "fell" else HORIZON


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


def __getattr__(name: str) -> Any:
    """``counted_rollout`` exists only through this hook, so every resolution of
    ``COUNTED_PATH`` (getattr, attrgetter, resolve_name, ...) is observable in ``RESOLVES``."""
    if name == "counted_rollout":
        RESOLVES.append(name)
        return deterministic_rollout
    raise AttributeError(name)


@pytest.fixture(autouse=True)
def _reset_rollout_state():
    RAISE_SEEDS.clear()
    SLEEP_SEEDS.clear()
    RESOLVES.clear()
    yield
    RAISE_SEEDS.clear()
    SLEEP_SEEDS.clear()
    RESOLVES.clear()


# ---------- module-level fake mappers ----------

Batches = Sequence[Sequence[Job]]
Yielded = tuple[int, list[Result] | BaseException]


def _run_batch(jobs: Sequence[Job]) -> list[Result]:
    return worker_batch(jobs, DET_PATH, None)


def _batch_key(jobs: Sequence[Job]) -> tuple[int, ...]:
    return tuple(job[2] for job in jobs)


def in_process_mapper(batches: Batches) -> Iterator[Yielded]:
    """Runs every batch through ``worker_batch`` locally, in submission order."""
    for index, jobs in enumerate(batches):
        yield index, _run_batch(jobs)


class ReversedMapper:
    """Completes batches last-first. With ``watch`` set to a run's episodes directory it also
    records how many part files exist each time it is resumed for the next batch."""

    def __init__(self, watch: Path | None = None) -> None:
        self.watch = watch
        self.parts_seen: list[int] = []

    def __call__(self, batches: Batches) -> Iterator[Yielded]:
        for index in reversed(range(len(batches))):
            if self.watch is not None:
                self.parts_seen.append(len(_parts_in(self.watch)))
            yield index, _run_batch(batches[index])


class RaiseKThenSucceed:
    """Infra-fails the batch containing plan index ``target_i`` on its first ``k`` attempts
    and runs it on attempt ``k + 1``. Attempts are counted per batch content."""

    def __init__(self, target_i: int, k: int) -> None:
        self.target_i = target_i
        self.k = k
        self.attempts: dict[tuple[int, ...], int] = {}

    def __call__(self, batches: Batches) -> Iterator[Yielded]:
        for index, jobs in enumerate(batches):
            key = _batch_key(jobs)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            if self.target_i in key and self.attempts[key] <= self.k:
                yield index, RuntimeError(f"container lost on attempt {self.attempts[key]}")
            else:
                yield index, _run_batch(jobs)


class AlwaysRaiseOneBatch:
    """Infra-fails the batch containing plan index ``target_i`` on every attempt."""

    def __init__(self, target_i: int) -> None:
        self.target_i = target_i
        self.attempts: dict[tuple[int, ...], int] = {}

    def __call__(self, batches: Batches) -> Iterator[Yielded]:
        for index, jobs in enumerate(batches):
            key = _batch_key(jobs)
            self.attempts[key] = self.attempts.get(key, 0) + 1
            if self.target_i in key:
                yield index, RuntimeError("container OOM")
            else:
                yield index, _run_batch(jobs)


def yield_two_then_raise_mapper(batches: Batches) -> Iterator[Yielded]:
    """Yields the first two batches, then dies as a generator (not an infra failure)."""
    for index, jobs in enumerate(batches):
        if index == 2:
            raise RuntimeError("mapper died after two batches")
        yield index, _run_batch(jobs)


class RecordingMapper:
    """Records every call and every batch it is handed, then behaves like the in-process one."""

    def __init__(self) -> None:
        self.calls: list[list[list[Job]]] = []

    @property
    def batches(self) -> list[list[Job]]:
        return [batch for call in self.calls for batch in call]

    def __call__(self, batches: Batches) -> Iterator[Yielded]:
        self.calls.append([list(jobs) for jobs in batches])
        yield from in_process_mapper(batches)


# ---------- helpers ----------


def _spec(
    *,
    cells: tuple[dict[str, Any], ...] = CELLS,
    replicates: int = REPLICATES,
    target_id: str = TARGET,
    t_unit: str = T_UNIT,
) -> SweepSpec:
    return SweepSpec.build(
        [dict(c) for c in cells], replicates=replicates, target_id=target_id, t_unit=t_unit
    )


def _store(tmp_path: Path, name: str = "store") -> Store:
    return Store(tmp_path / name)


def _modal_plan(spec: SweepSpec, store: Store, **kwargs: Any) -> Plan:
    return plan(spec, store, backend="modal", **kwargs)


def _options(**overrides: Any) -> ModalOptions:
    kwargs: dict[str, Any] = {"batch_size": BATCH}
    kwargs.update(overrides)
    return ModalOptions(**kwargs)


def _jobs(p: Plan) -> list[Job]:
    return [
        (dict(q.config), q.seed, i, q.config_hash, q.replicate_index)
        for i, q in enumerate(p.pairs)
    ]


def _keyed(df: pd.DataFrame) -> pd.DataFrame:
    return df.set_index(["config_hash", "replicate_index"]).sort_index()


def _parts_in(episodes_dir: Path) -> list[Path]:
    return sorted(episodes_dir.glob("part-*.parquet"))


def _parts(store_root: Path, run_id: str) -> list[Path]:
    return _parts_in(store_root / run_id / "episodes")


def _outcome_set(store: Store, run_id: str) -> set[tuple[str, int, int, str, float]]:
    df = store.read(run_id)
    return set(
        zip(df["config_hash"], df["replicate_index"], df["seed"], df["outcome"], df["t"], strict=True)
    )


COMPARE_COLS = ["seed", "outcome", "t", "horizon", "config", "error"]


def _reference_frame(tmp_path: Path, spec: SweepSpec, name: str = "reference") -> pd.DataFrame:
    """The uninterrupted in-process run of ``spec`` under SALT_A, keyed and trimmed."""
    store = _store(tmp_path, name)
    p = _modal_plan(spec, store, run_salt=SALT_A)
    summary = run_with_mapper(p, in_process_mapper, store, options=_options())
    assert summary.complete is True
    return _keyed(store.read(p.run_id))[COMPARE_COLS]


def _line_with(text: str, token: str) -> str:
    matches = [line for line in text.splitlines() if token in line]
    assert matches, f"{token!r} not found in preflight text:\n{text}"
    return matches[0]


# ---------- I1: lazy import ----------


def test_i1_imports_succeed_without_modal_and_only_run_modal_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in [n for n in sys.modules if n == "modal" or n.startswith("modal.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "modal", None)
    monkeypatch.setattr(poisson_prove, "executor_modal", executor_modal, raising=False)
    monkeypatch.delitem(sys.modules, "poisson_prove.executor_modal")
    monkeypatch.delitem(sys.modules, "poisson_prove")

    pkg = importlib.import_module("poisson_prove")
    fresh = importlib.import_module("poisson_prove.executor_modal")
    assert pkg.__version__ == poisson_prove.__version__
    assert fresh is not executor_modal
    assert sys.modules["modal"] is None
    assert issubclass(fresh.ModalNotInstalled, fresh.ModalBackendError)
    assert issubclass(fresh.ModalBackendError, ExecutorError)

    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    target = fresh.ModalTarget(import_path=DET_PATH, image=fresh.ImageSpec())
    options = fresh.ModalOptions(batch_size=BATCH)
    assert "Backend: modal" in fresh.preflight_modal(p, target, options)
    assert fresh.estimate_cost(p, options, target.image) is None
    with pytest.raises(fresh.ModalNotInstalled) as excinfo:
        fresh.run_modal(p, target, store, options=options)
    assert "pip install \"poisson-prove[modal]\"" in str(excinfo.value)


def test_i1_exception_hierarchy() -> None:
    assert issubclass(ModalBackendError, ExecutorError)
    assert issubclass(ModalNotInstalled, ModalBackendError)
    assert issubclass(CostGuard, ModalBackendError)


# ---------- I2: worker contract ----------


def test_i2_worker_batch_good_rollout_one_result_per_job_in_order(tmp_path: Path) -> None:
    p = _modal_plan(_spec(), _store(tmp_path))
    jobs = _jobs(p)
    results = worker_batch(jobs, DET_PATH, None)
    assert isinstance(results, list) and len(results) == len(jobs) == TOTAL
    for job, result in zip(jobs, results, strict=True):
        config, seed, i, _, _ = job
        assert isinstance(result, dict), result
        assert {"outcome", "t", "horizon", "meta", "wall_time", "backend_meta"} <= set(result)
        assert result["backend_meta"]["i"] == i
        assert result["outcome"] == _outcome(config, seed)
        assert result["t"] == _t(config, seed)
        assert result["horizon"] == HORIZON
        assert result["wall_time"] > 0
        assert Episode.from_dict(result).outcome == result["outcome"]


def test_i2_worker_batch_raising_rollout_yields_traceback_string(tmp_path: Path) -> None:
    p = _modal_plan(_spec(), _store(tmp_path))
    jobs = _jobs(p)
    bad = 4
    RAISE_SEEDS.add(jobs[bad][1])
    results = worker_batch(jobs, RAISE_PATH, None)
    assert len(results) == TOTAL
    assert isinstance(results[bad], str)
    assert "ValueError" in results[bad] and "boom" in results[bad]
    assert "Traceback" in results[bad]
    for i, result in enumerate(results):
        if i != bad:
            assert isinstance(result, dict) and result["backend_meta"]["i"] == i


def test_i2_worker_batch_wrong_type_return_is_recorded(tmp_path: Path) -> None:
    p = _modal_plan(_spec(), _store(tmp_path))
    results = worker_batch(_jobs(p), WRONG_TYPE_PATH, None)
    assert len(results) == TOTAL
    assert all(isinstance(r, str) for r in results)
    assert all("expected Episode" in r and "dict" in r for r in results)


# ---------- I3: worker timeout (fork only) ----------


@pytest.mark.skipif(not FORK_AVAILABLE, reason="episode_timeout test needs the fork start method")
def test_i3_worker_timeout_kills_one_job_and_leaves_the_rest(tmp_path: Path) -> None:
    p = _modal_plan(_spec(), _store(tmp_path))
    jobs = _jobs(p)
    slow = 1
    SLEEP_SEEDS.add(jobs[slow][1])
    t0 = time.perf_counter()
    results = worker_batch(jobs, SLEEP_PATH, 0.5)
    elapsed = time.perf_counter() - t0
    assert elapsed < 5.0, elapsed
    assert len(results) == TOTAL
    assert results[slow] == "timeout"
    assert sum(1 for r in results if r == "timeout") == 1
    for i, (job, result) in enumerate(zip(jobs, results, strict=True)):
        if i != slow:
            assert isinstance(result, dict), result
            assert result["outcome"] == _outcome(job[0], job[1])
            assert result["backend_meta"]["i"] == i


# ---------- I4: worker purity ----------


def test_i4_worker_batch_runs_with_modal_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in [n for n in sys.modules if n == "modal" or n.startswith("modal.")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "modal", None)
    results = worker_batch(_jobs(_modal_plan(_spec(), _store(tmp_path))), DET_PATH, None)
    assert len(results) == TOTAL and all(isinstance(r, dict) for r in results)


def test_i4_import_path_resolved_once_per_call(tmp_path: Path) -> None:
    jobs = _jobs(_modal_plan(_spec(), _store(tmp_path)))
    assert RESOLVES == []
    results = worker_batch(jobs, COUNTED_PATH, None)
    assert len(RESOLVES) == 1, RESOLVES
    for job, result in zip(jobs, results, strict=True):
        assert isinstance(result, dict) and result["outcome"] == _outcome(job[0], job[1])


def test_i4_rollout_gets_a_fresh_dict_per_job(tmp_path: Path) -> None:
    jobs = _jobs(_modal_plan(_spec(), _store(tmp_path)))
    originals = [dict(job[0]) for job in jobs]
    results = worker_batch(jobs, MUTATE_PATH, None)
    assert [dict(job[0]) for job in jobs] == originals
    for original, job, result in zip(originals, jobs, results, strict=True):
        assert isinstance(result, dict), result
        assert result["outcome"] == _outcome(original, job[1])
        assert "injected" not in job[0] and job[0]["x"] != 999.0


# ---------- I5: parity with the local backend ----------


def test_i5_in_process_mapper_matches_run_local_under_shared_salt(tmp_path: Path) -> None:
    spec = _spec()
    local_store = _store(tmp_path, "local")
    local_plan = plan(spec, local_store, run_salt=SALT_A)
    local_summary = run_local(local_plan, deterministic_rollout, local_store, batch_size=BATCH)

    modal_store = _store(tmp_path, "modal")
    modal_plan = _modal_plan(spec, modal_store, run_salt=SALT_A)
    modal_summary = run_with_mapper(modal_plan, in_process_mapper, modal_store, options=_options())

    assert local_summary.complete is True and modal_summary.complete is True
    assert modal_summary.n_ok == local_summary.n_ok == TOTAL
    assert modal_summary.n_errored == 0 and modal_summary.n_timeout == 0
    assert modal_summary.n_infra_retried == 0 and modal_summary.n_infra_failed == 0
    local_set = _outcome_set(local_store, local_plan.run_id)
    modal_set = _outcome_set(modal_store, modal_plan.run_id)
    assert len(local_set) == TOTAL
    assert modal_set == local_set
    a = _keyed(local_store.read(local_plan.run_id))[COMPARE_COLS]
    b = _keyed(modal_store.read(modal_plan.run_id))[COMPARE_COLS]
    pd.testing.assert_frame_equal(a, b)


# ---------- I6: chunking ----------


@pytest.mark.parametrize("batch_size", [1, BATCH, 64])
def test_i6_batches_are_plan_order_chunks_and_one_part_each(tmp_path: Path, batch_size: int) -> None:
    root = tmp_path / "store"
    store = Store(root)
    p = _modal_plan(_spec(), store)
    recording = RecordingMapper()
    summary = run_with_mapper(p, recording, store, options=_options(batch_size=batch_size))
    assert summary.complete is True
    n_batches = math.ceil(TOTAL / batch_size)
    batches = recording.batches
    assert len(batches) == n_batches
    sizes = [len(b) for b in batches]
    assert sizes[:-1] == [batch_size] * (n_batches - 1)
    assert sizes[-1] == TOTAL - batch_size * (n_batches - 1)
    flat = [job for batch in batches for job in batch]
    assert len(flat) == TOTAL
    for i, (config, seed, job_i, config_hash, replicate_index) in enumerate(flat):
        q = p.pairs[i]
        assert job_i == i
        assert config == q.config and seed == q.seed
        assert config_hash == q.config_hash and replicate_index == q.replicate_index
    assert len(_parts(root, p.run_id)) == n_batches
    assert len(store.read(p.run_id)) == TOTAL


# ---------- I7: out-of-order flush ----------


def test_i7_reversed_completion_order_gives_same_frame_and_flushes_as_batches_arrive(
    tmp_path: Path,
) -> None:
    spec = _spec()
    reference = _reference_frame(tmp_path, spec)

    root = tmp_path / "reversed"
    store = Store(root)
    p = _modal_plan(spec, store, run_salt=SALT_A)
    mapper = ReversedMapper(watch=root / p.run_id / "episodes")
    summary = run_with_mapper(p, mapper, store, options=_options())
    assert summary.complete is True and summary.n_ok == TOTAL

    assert mapper.parts_seen == list(range(N_BATCHES))
    assert len(_parts(root, p.run_id)) == N_BATCHES
    df = store.read(p.run_id)
    pd.testing.assert_frame_equal(_keyed(df)[COMPARE_COLS], reference)
    keyed = _keyed(df)
    for i, q in enumerate(p.pairs):
        assert keyed.loc[(q.config_hash, q.replicate_index), "backend_meta"]["i"] == i


# ---------- I8: infra retry ----------


@pytest.mark.parametrize("k", [1, 2])
def test_i8_batch_that_fails_k_times_then_succeeds_counts_one_retry(tmp_path: Path, k: int) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    target_i = BATCH  # first job of batch 1
    mapper = RaiseKThenSucceed(target_i=target_i, k=k)
    options = _options(infra_retries=2)
    assert k <= options.infra_retries
    summary = run_with_mapper(p, mapper, store, options=options)
    assert summary.complete is True and summary.stopped_by is None
    assert summary.n_infra_retried == 1
    assert summary.n_infra_failed == 0
    assert summary.n_ok == TOTAL and summary.n_errored == 0 and summary.n_timeout == 0
    assert store.manifest(p.run_id).status == "complete"
    df = store.read(p.run_id)
    assert len(df) == TOTAL
    assert df["error"].isna().all() and df["outcome"].notna().all()
    assert not any(str(e).startswith("infra:") for e in df["error"].dropna())
    key = tuple(range(BATCH, 2 * BATCH))
    assert mapper.attempts[key] == k + 1
    assert all(n == 1 for other, n in mapper.attempts.items() if other != key)
    keyed = _keyed(df)
    for q in p.pairs:
        assert keyed.loc[(q.config_hash, q.replicate_index), "outcome"] == _outcome(q.config, q.seed)


# ---------- I9: infra exhaustion ----------


@pytest.mark.parametrize(
    ("batch_index", "size"), [(0, BATCH), (N_BATCHES - 1, TAIL)], ids=["full-batch", "tail"]
)
def test_i9_exhausted_batch_is_recorded_as_infra_rows_and_run_completes(
    tmp_path: Path, batch_index: int, size: int
) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    first_i = batch_index * BATCH
    mapper = AlwaysRaiseOneBatch(target_i=first_i)
    options = _options(infra_retries=2)
    summary = run_with_mapper(p, mapper, store, options=options)

    assert summary.n_infra_failed == size
    assert summary.n_errored == size
    assert summary.n_ok == TOTAL - size
    assert summary.n_timeout == 0
    assert summary.n_infra_retried == 0
    assert summary.complete is True and summary.stopped_by is None
    assert store.manifest(p.run_id).status == "complete"

    key = tuple(range(first_i, first_i + size))
    assert mapper.attempts[key] == options.infra_retries + 1
    assert all(n == 1 for other, n in mapper.attempts.items() if other != key)

    df = store.read(p.run_id)
    assert len(df) == TOTAL
    assert not (df["error"] == "timeout").any()
    keyed = _keyed(df)
    infra_keys = {(q.config_hash, q.replicate_index) for q in p.pairs[first_i : first_i + size]}
    for q in p.pairs:
        row = keyed.loc[(q.config_hash, q.replicate_index)]
        if (q.config_hash, q.replicate_index) in infra_keys:
            assert isinstance(row["error"], str) and row["error"].startswith("infra: ")
            assert "RuntimeError" in row["error"] and "container OOM" in row["error"]
            assert pd.isna(row["outcome"]) and pd.isna(row["t"])
        else:
            assert pd.isna(row["error"])
            assert row["outcome"] == _outcome(q.config, q.seed)


# ---------- I10: finally flush ----------


def test_i10_mapper_that_dies_after_two_batches_leaves_them_stored_and_reraises(
    tmp_path: Path,
) -> None:
    root = tmp_path / "store"
    store = Store(root)
    spec = _spec()
    p = _modal_plan(spec, store, run_salt=SALT_A)
    with pytest.raises(RuntimeError, match="mapper died after two batches"):
        run_with_mapper(p, yield_two_then_raise_mapper, store, options=_options())
    assert store.manifest(p.run_id).status == "partial"
    assert len(_parts(root, p.run_id)) == 2
    df = store.read(p.run_id)
    assert len(df) == 2 * BATCH
    stored = {(q.config_hash, q.replicate_index) for q in p.pairs[: 2 * BATCH]}
    assert set(zip(df["config_hash"], df["replicate_index"], strict=True)) == stored

    resumed = _modal_plan(spec, store, resume=p.run_id)
    assert resumed.already_stored == 2 * BATCH and len(resumed.pairs) == TAIL
    finish = run_with_mapper(resumed, in_process_mapper, store, options=_options())
    assert finish.complete is True
    assert len(store.read(p.run_id)) == TOTAL


# ---------- I11: max_rollouts and resume ----------


@pytest.mark.parametrize("n", [1, 7])
def test_i11_max_rollouts_stops_after_the_batch_holding_the_nth_episode(tmp_path: Path, n: int) -> None:
    assert (n - 1) // BATCH < N_BATCHES - 1, "cap must land before the final batch"
    root = tmp_path / "store"
    store = Store(root)
    p = _modal_plan(_spec(), store)
    summary = run_with_mapper(p, in_process_mapper, store, options=_options(max_rollouts=n))
    assert summary.stopped_by == "max_rollouts"
    assert summary.complete is False
    assert store.manifest(p.run_id).status == "partial"
    df = store.read(p.run_id)
    assert n <= len(df) <= n + BATCH - 1
    assert summary.n_ok + summary.n_errored == len(df)
    executed = [(q.config_hash, q.replicate_index) for q in p.pairs[: len(df)]]
    assert sorted(zip(df["config_hash"], df["replicate_index"], strict=True)) == sorted(executed)
    assert len(_parts(root, p.run_id)) == math.ceil(len(df) / BATCH)


def test_i11_resume_after_cap_matches_uninterrupted_run(tmp_path: Path) -> None:
    spec = _spec()
    stop_at = 7
    reference = _reference_frame(tmp_path, spec)

    root = tmp_path / "partial"
    store = Store(root)
    first = _modal_plan(spec, store, run_salt=SALT_A)
    stopped = run_with_mapper(first, in_process_mapper, store, options=_options(max_rollouts=stop_at))
    assert stopped.stopped_by == "max_rollouts" and stopped.complete is False
    n_stored = len(store.read(first.run_id))
    assert stop_at <= n_stored <= stop_at + BATCH - 1

    resumed = _modal_plan(spec, store, resume=first.run_id)
    assert resumed.run_id == first.run_id and resumed.run_salt == SALT_A
    assert resumed.already_stored == n_stored and len(resumed.pairs) == TOTAL - n_stored
    finish = run_with_mapper(resumed, in_process_mapper, store, options=_options())
    assert finish.complete is True and finish.stopped_by is None
    assert finish.n_ok == TOTAL - n_stored
    assert store.manifest(first.run_id).status == "complete"
    assert len(_parts(root, first.run_id)) == math.ceil(n_stored / BATCH) + math.ceil((TOTAL - n_stored) / BATCH)

    b = _keyed(store.read(first.run_id))[COMPARE_COLS]
    assert len(reference) == len(b) == TOTAL
    pd.testing.assert_frame_equal(reference, b)


# ---------- I12: manifest ----------


def test_i12_manifest_records_modal_backend_and_environment(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    p = _modal_plan(spec, store)
    image = ImageSpec(python="3.11", pip=("numpy",), gpu=None, local_packages=("poisson_prove",))
    options = _options(concurrency=3, app_name="proofload-oracle")
    run_with_mapper(p, in_process_mapper, store, options=options, image=image)
    m = store.manifest(p.run_id)
    assert m.run_id == p.run_id
    assert m.backend == "modal"
    assert m.run_salt == p.run_salt
    assert m.target_id == TARGET and m.t_unit == T_UNIT
    assert m.status == "complete"
    env = dict(m.environment)
    for key in ("python", "platform", "poisson_prove_version", "sweep", "image", "modal_app", "concurrency", "import_path"):
        assert key in env, key
    assert env["image"] == image.to_dict()
    assert env["modal_app"] == "proofload-oracle"
    assert env["concurrency"] == 3
    assert env["sweep"] == spec.to_dict()
    assert json.loads(json.dumps(env)) == env


# ---------- I13: cost guard ----------


def test_i13_max_cost_without_estimate_refuses_before_the_mapper_is_called(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    recording = RecordingMapper()
    options = _options(max_cost=1.0, est_seconds_per_episode=None)
    with pytest.raises(CostGuard):
        run_with_mapper(p, recording, store, options=options, image=ImageSpec())
    assert recording.calls == [] and recording.batches == []


def test_i13_estimate_above_cap_refuses_and_estimate_within_cap_runs(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    image = ImageSpec()
    base = _options(est_seconds_per_episode=100.0)
    estimate = estimate_cost(p, base, image)
    assert estimate is not None and estimate > 0

    recording = RecordingMapper()
    with pytest.raises(CostGuard):
        run_with_mapper(
            p, recording, store, options=dataclasses.replace(base, max_cost=estimate / 2), image=image
        )
    assert recording.calls == []

    summary = run_with_mapper(
        p, recording, store, options=dataclasses.replace(base, max_cost=estimate), image=image
    )
    assert summary.complete is True and summary.n_ok == TOTAL
    assert len(recording.batches) == N_BATCHES


# ---------- I14: estimate_cost ----------


def test_i14_estimate_cost_none_without_estimate_and_linear_with_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    cpu = ImageSpec()
    assert estimate_cost(p, _options(est_seconds_per_episode=None), cpu) is None

    one = estimate_cost(p, _options(est_seconds_per_episode=10.0), cpu)
    assert one is not None and one > 0
    twice_seconds = estimate_cost(p, _options(est_seconds_per_episode=20.0), cpu)
    assert twice_seconds == pytest.approx(2 * one)

    bigger = _modal_plan(_spec(replicates=2 * REPLICATES), store)
    assert len(bigger.pairs) == 2 * TOTAL
    twice_jobs = estimate_cost(bigger, _options(est_seconds_per_episode=10.0), cpu)
    assert twice_jobs == pytest.approx(2 * one)


def test_i14_gpu_price_is_at_least_cpu_price_and_unknown_gpu_gives_none(tmp_path: Path) -> None:
    p = _modal_plan(_spec(), _store(tmp_path))
    options = _options(est_seconds_per_episode=10.0)
    cpu = estimate_cost(p, options, ImageSpec())
    gpu = estimate_cost(p, options, ImageSpec(gpu="A10G"))
    assert cpu is not None and gpu is not None
    assert gpu >= cpu
    assert estimate_cost(p, options, ImageSpec(gpu="no-such-gpu-xyz")) is None


# ---------- I15: pre-flight ----------


def test_i15_preflight_fresh_plan_with_and_without_estimate(tmp_path: Path) -> None:
    spec = _spec()
    p = _modal_plan(spec, _store(tmp_path))
    image = ImageSpec(python="3.11", pip=("numpy", "torch"), gpu="A10G")
    target = ModalTarget(import_path=DET_PATH, image=image)
    options = _options(concurrency=3, est_seconds_per_episode=10.0, episode_timeout=120.0)
    text = preflight_modal(p, target, options)

    sweep_line = _line_with(text, "Sweep:")
    for token in ("1 axes", f"{len(spec.configs)} cells", f"N={REPLICATES}", f"{TOTAL} rollouts"):
        assert token in sweep_line, (token, sweep_line)
    backend_line = _line_with(text, "Backend: modal")
    assert TARGET in backend_line and T_UNIT in backend_line
    image_line = _line_with(text, "Image:")
    for token in ("python 3.11", "2 pip", "gpu: A10G", DET_PATH):
        assert token in image_line, (token, image_line)
    containers_line = _line_with(text, "Containers: up to 3")
    assert f"batch: {BATCH}" in containers_line
    assert "episode timeout" in containers_line and "120" in containers_line
    cost_line = _line_with(text, "Cost: ~$")
    assert "best-effort" in cost_line and "prices" in cost_line
    assert "Cost: unknown" not in text
    # PF4 re-freeze (PF4.22, reading R36): the preflight block no longer prints the old limit at a base
    # rate of 0.5 (the normal approximation, beside the gate's own); the plan's one limit is the gate's.
    assert "MDE at N=" not in text and "base rate 0.5" not in text
    assert "Resuming" not in text

    no_estimate = preflight_modal(
        p, ModalTarget(import_path=DET_PATH, image=ImageSpec()), _options(concurrency=3)
    )
    assert "Cost: unknown" in _line_with(no_estimate, "Cost:")
    assert "Cost: ~$" not in no_estimate
    assert "gpu: none" in _line_with(no_estimate, "Image:")
    assert "0 pip" in _line_with(no_estimate, "Image:")


def test_i15_preflight_resumed_plan_adds_resuming_line(tmp_path: Path) -> None:
    store = _store(tmp_path)
    spec = _spec()
    p = _modal_plan(spec, store)
    run_with_mapper(p, in_process_mapper, store, options=_options(max_rollouts=BATCH))
    n_stored = len(store.read(p.run_id))
    resumed = _modal_plan(spec, store, resume=p.run_id)
    text = preflight_modal(resumed, ModalTarget(import_path=DET_PATH, image=ImageSpec()), _options())
    assert "Backend: modal" in text
    line = _line_with(text, "Resuming")
    assert p.run_id in line
    assert re.search(rf"\b{n_stored} stored\b", line) and re.search(rf"\b{TOTAL - n_stored} to run\b", line)


# ---------- I16: ImageSpec validity ----------


def test_i16_dockerfile_is_exclusive_with_pip_and_apt(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM python:3.11\n")
    with pytest.raises(ValueError):
        ImageSpec(dockerfile=dockerfile, pip=("numpy",))
    with pytest.raises(ValueError):
        ImageSpec(dockerfile=dockerfile, apt=("git",))
    only_dockerfile = ImageSpec(dockerfile=dockerfile)
    assert only_dockerfile.dockerfile == dockerfile


@pytest.mark.parametrize(
    "image",
    [
        ImageSpec(),
        ImageSpec(python="3.12", pip=("numpy", "torch==2.3"), apt=("git",), gpu="A10G", local_packages=("mypkg",)),
    ],
    ids=["default", "full"],
)
def test_i16_to_dict_round_trips_through_json(image: ImageSpec) -> None:
    d = image.to_dict()
    assert isinstance(d, dict)
    assert json.loads(json.dumps(d)) == d
    assert d["python"] == image.python
    assert list(d["pip"]) == list(image.pip) and list(d["apt"]) == list(image.apt)
    assert d["gpu"] == image.gpu


def test_i16_to_dict_with_dockerfile_round_trips_through_json(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM python:3.11\n")
    d = ImageSpec(dockerfile=dockerfile).to_dict()
    assert json.loads(json.dumps(d)) == d
    assert str(dockerfile) in json.dumps(d)


def test_i16_target_import_path_needs_a_colon() -> None:
    with pytest.raises(ValueError):
        ModalTarget(import_path="pkg.module.rollout", image=ImageSpec())
    target = ModalTarget(import_path="pkg.module:rollout", image=ImageSpec(gpu="A10G"))
    assert target.import_path == "pkg.module:rollout" and target.image.gpu == "A10G"


def test_i16_frozen_dataclasses() -> None:
    image = ImageSpec()
    with pytest.raises(dataclasses.FrozenInstanceError):
        image.python = "3.12"  # type: ignore[misc]
    options = ModalOptions()
    with pytest.raises(dataclasses.FrozenInstanceError):
        options.concurrency = 1  # type: ignore[misc]


# ---------- I17: progress ----------


@pytest.mark.parametrize("cap", [None, 7], ids=["uncapped", "capped"])
@pytest.mark.parametrize("order", ["submission", "reversed"])
def test_i17_on_progress_once_per_completed_batch_strictly_increasing(
    tmp_path: Path, cap: int | None, order: str
) -> None:
    store = _store(tmp_path)
    p = _modal_plan(_spec(), store)
    mapper = in_process_mapper if order == "submission" else ReversedMapper()
    calls: list[tuple[int, int]] = []
    summary = run_with_mapper(
        p, mapper, store, options=_options(max_rollouts=cap), on_progress=lambda d, t: calls.append((d, t))
    )
    n_executed = summary.n_ok + summary.n_errored
    assert n_executed == len(store.read(p.run_id))
    dones = [d for d, _ in calls]
    assert dones == sorted(set(dones)), dones
    assert dones[-1] == n_executed
    assert all(t == TOTAL for _, t in calls)
    assert len(calls) == math.ceil(n_executed / BATCH)


# ---------- I18: local backend unchanged ----------


def test_i18_run_summary_constructs_without_the_new_fields() -> None:
    assert (s := RunSummary(run_id="r", n_ok=1, n_errored=0, n_timeout=0, wall_time=0.1, stopped_by=None, complete=True)).n_infra_retried == 0 and s.n_infra_failed == 0


# ---------- I19: live parity lives in tests/live/test_m3_modal_live.py ----------
