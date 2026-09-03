"""M3: the local executor.

Turns a ``SweepSpec`` into a completed run in the store: one seed per (config, replicate),
one call of the user's ``rollout`` per pair, every misbehavior caught and recorded as an
errored row, episodes written in resumable batches, and the run marked complete. Serial
and in-process by design; it is the reference behavior the Modal backend must match.

M3 mints the four manifest fields no other module owns: ``run_id``, ``run_salt``,
``backend``, ``environment``.
"""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import platform
import sys
import time
import traceback
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from typing import Any

from proofload import __version__
from proofload.diff import mde_two_proportion
from proofload.episode import Episode
from proofload.sampler import SweepSpec
from proofload.store import EpisodeRecord, RunManifest, Store, StoreError

Rollout = Callable[[Mapping[str, Any], int], Episode]

_TIMEOUT_ERROR = "timeout"
_POLL_STEP_S = 0.05
_JOIN_GRACE_S = 5.0


class ExecutorError(Exception):
    """A run cannot be planned or executed as requested."""


class NotResumable(ExecutorError):
    """The run named by ``resume=`` cannot be continued."""


class PairMismatch(ExecutorError):
    """The run named by ``pair_with=`` cannot be paired with this spec."""


# ---------- identity ----------


def derive_seed(run_salt: str, config_hash: str, replicate_index: int) -> int:
    """Deterministic 32-bit seed: SHA-256 of ``salt:hash:replicate``, first 4 bytes big-endian."""
    digest = hashlib.sha256(f"{run_salt}:{config_hash}:{replicate_index}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def new_run_salt() -> str:
    return os.urandom(8).hex()


def new_run_id(target_id: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{os.urandom(2).hex()}"


# ---------- plan ----------


@dataclass(frozen=True)
class Pair:
    config: dict[str, Any]
    config_hash: str
    replicate_index: int
    seed: int


@dataclass(frozen=True)
class Plan:
    spec: SweepSpec
    run_id: str
    run_salt: str
    backend: str
    pairs: tuple[Pair, ...]
    resumed: bool
    already_stored: int
    import_path: str | None = None


def _all_keys(spec: SweepSpec) -> list[tuple[str, int]]:
    return [(h, k) for h in spec.cells() for k in range(spec.replicates)]


def _manifest_or_raise(store: Store, run_id: str, error: type[ExecutorError]) -> RunManifest:
    try:
        return store.manifest(run_id)
    except StoreError as exc:
        raise error(f"run {run_id!r} is not in the store: {exc}") from exc


def plan(
    spec: SweepSpec,
    store: Store,
    *,
    backend: str = "local",
    run_salt: str | None = None,
    pair_with: str | None = None,
    resume: str | None = None,
    import_path: str | None = None,
) -> Plan:
    """Build the ordered list of (config, replicate, seed) pairs for a run.

    pair_with=<run_id>: inherit that run's salt; t_unit must match.
    resume=<run_id>: reuse that run's id + salt; pairs = store.missing(...).
    run_salt, pair_with, resume are mutually exclusive; none -> new salt.
    import_path, when given, is recorded at manifest.environment["import_path"] by
    run_local, matching the Modal backend; the executor still receives the callable.
    """
    options = (("run_salt", run_salt), ("pair_with", pair_with), ("resume", resume))
    given = [name for name, value in options if value is not None]
    if len(given) > 1:
        raise ExecutorError(f"{' and '.join(given)} are mutually exclusive")

    resumed = False
    already_stored = 0
    wanted: list[tuple[str, int]] | None = None

    if resume is not None:
        manifest = _manifest_or_raise(store, resume, NotResumable)
        if manifest.status == "complete":
            raise NotResumable(f"run {resume!r} is already complete")
        if manifest.target_id != spec.target_id:
            raise NotResumable(
                f"run {resume!r} targets {manifest.target_id!r}, spec targets {spec.target_id!r}"
            )
        if manifest.t_unit != spec.t_unit:
            raise NotResumable(
                f"run {resume!r} uses t_unit {manifest.t_unit!r}, spec uses {spec.t_unit!r}"
            )
        if dict(manifest.axis_types) != dict(spec.axis_types):
            raise NotResumable(f"run {resume!r} has different axis_types than the spec")
        run_id = resume
        salt = manifest.run_salt
        wanted = store.missing(resume, _all_keys(spec))
        already_stored = len(spec.configs) * spec.replicates - len(wanted)
        resumed = True
    elif pair_with is not None:
        manifest = _manifest_or_raise(store, pair_with, PairMismatch)
        if manifest.t_unit != spec.t_unit:
            raise PairMismatch(
                f"run {pair_with!r} uses t_unit {manifest.t_unit!r}, spec uses {spec.t_unit!r}"
            )
        run_id = new_run_id(spec.target_id)
        salt = manifest.run_salt
    else:
        run_id = new_run_id(spec.target_id)
        salt = run_salt if run_salt is not None else new_run_salt()

    by_hash = dict(zip(spec.cells(), spec.configs, strict=True))
    keys = wanted if wanted is not None else _all_keys(spec)
    pairs = tuple(
        Pair(
            config=dict(by_hash[h]),
            config_hash=h,
            replicate_index=k,
            seed=derive_seed(salt, h, k),
        )
        for h, k in keys
    )
    return Plan(
        spec=spec,
        run_id=run_id,
        run_salt=salt,
        backend=backend,
        pairs=pairs,
        resumed=resumed,
        already_stored=already_stored,
        import_path=import_path,
    )


def preflight(p: Plan, *, cost_estimate: str | None = None) -> str:
    """Text block describing the run. Non-interactive; M10 prints it and asks."""
    spec = p.spec
    total = spec.total_rollouts()
    mde = mde_two_proportion(0.5, spec.replicates, spec.replicates)
    lines = [
        f"Sweep: {len(spec.axis_types)} axes · {len(spec.configs)} cells · "
        f"N={spec.replicates} → {total} rollouts",
        f"Backend: {p.backend} · target: {spec.target_id} · t_unit: {spec.t_unit}",
        f"Cost: {cost_estimate if cost_estimate is not None else '$0 (local)'}",
        f"MDE at N={spec.replicates} (worst case, rate 0.5): {mde:.4f}",
    ]
    if p.resumed:
        lines.append(f"Resuming {p.run_id}: {p.already_stored} stored, {len(p.pairs)} to run")
    return "\n".join(lines) + "\n"


# ---------- per-episode execution ----------

# Outcome of one rollout call: ("ok", episode_dict) | ("error", text) | ("timeout", None)
_Outcome = tuple[str, Any]


def _classify(result: Any) -> _Outcome:
    if isinstance(result, Episode):
        return ("ok", result.to_dict())
    return ("error", f"rollout returned {type(result).__name__}, expected Episode")


def _call_in_process(rollout: Rollout, config: dict[str, Any], seed: int) -> _Outcome:
    try:
        return _classify(rollout(config, seed))
    except Exception:
        return ("error", traceback.format_exc())


def _child_main(conn: Connection, rollout: Rollout, config: dict[str, Any], seed: int) -> None:
    try:
        outcome = _call_in_process(rollout, config, seed)
    except BaseException:  # noqa: BLE001 - the child must always report
        outcome = ("error", traceback.format_exc())
    try:
        conn.send(outcome)
    finally:
        conn.close()


def _call_with_timeout(
    rollout: Rollout, config: dict[str, Any], seed: int, timeout: float, ctx: Any
) -> _Outcome:
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child_main, args=(child_conn, rollout, config, seed))
    proc.start()
    child_conn.close()
    deadline = time.perf_counter() + timeout
    outcome: _Outcome | None = None
    try:
        while outcome is None:
            remaining = deadline - time.perf_counter()
            if parent_conn.poll(min(_POLL_STEP_S, max(remaining, 0.0))):
                outcome = parent_conn.recv()
            elif not proc.is_alive():
                if parent_conn.poll():
                    outcome = parent_conn.recv()
                else:
                    outcome = (
                        "error",
                        f"rollout worker exited with code {proc.exitcode} before returning",
                    )
            elif remaining <= 0.0:
                outcome = (_TIMEOUT_ERROR, None)
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
            proc.join(_JOIN_GRACE_S)
            if proc.is_alive():
                proc.kill()
                proc.join()
        else:
            proc.join(_JOIN_GRACE_S)
        proc.close()
    return outcome


def _mp_context() -> Any:
    methods = multiprocessing.get_all_start_methods()
    return multiprocessing.get_context("fork" if "fork" in methods else "spawn")


# ---------- run ----------


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    n_ok: int
    n_errored: int
    n_timeout: int
    wall_time: float
    stopped_by: str | None
    complete: bool
    n_infra_retried: int = 0
    n_infra_failed: int = 0


def _environment(spec: SweepSpec) -> dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "proofload_version": __version__,
        "sweep": spec.to_dict(),
    }


def _record(p: Plan, pair: Pair, index: int, outcome: _Outcome, wall_time: float) -> EpisodeRecord:
    kind, payload = outcome
    backend_meta = {"i": index}
    if kind == "ok":
        return EpisodeRecord.from_episode(
            Episode.from_dict(payload),
            run_id=p.run_id,
            config=pair.config,
            seed=pair.seed,
            replicate_index=pair.replicate_index,
            wall_time=wall_time,
            backend_meta=backend_meta,
        )
    error = _TIMEOUT_ERROR if kind == _TIMEOUT_ERROR else str(payload)
    return EpisodeRecord.errored(
        run_id=p.run_id,
        config=pair.config,
        seed=pair.seed,
        replicate_index=pair.replicate_index,
        error=error,
        wall_time=wall_time,
        backend_meta=backend_meta,
    )


def run_local(
    p: Plan,
    rollout: Rollout,
    store: Store,
    *,
    episode_timeout: float | None = None,
    max_rollouts: int | None = None,
    batch_size: int = 64,
    on_progress: Callable[[int, int], None] | None = None,
) -> RunSummary:
    """Execute a plan serially, in-process, writing episodes in batches of ``batch_size``.

    The rollout receives a fresh shallow copy of the pair's config on every call.
    """
    if batch_size < 1:
        raise ExecutorError(f"batch_size must be >= 1, got {batch_size}")
    if max_rollouts is not None and max_rollouts < 1:
        raise ExecutorError(f"max_rollouts must be >= 1 when given, got {max_rollouts}")
    if episode_timeout is not None and episode_timeout <= 0:
        raise ExecutorError(f"episode_timeout must be > 0 when given, got {episode_timeout}")

    existing: RunManifest | None
    try:
        existing = store.manifest(p.run_id)
    except StoreError:
        existing = None
    if existing is not None and existing.status == "complete":
        raise ExecutorError(f"run {p.run_id!r} is already complete")
    if p.resumed:
        if existing is None:
            raise ExecutorError(f"resumed run {p.run_id!r} is not in the store")
    else:
        if existing is not None:
            raise ExecutorError(
                f"run {p.run_id!r} already exists; plan with resume= to continue it"
            )
        environment = _environment(p.spec)
        if p.import_path is not None:
            environment["import_path"] = p.import_path
        store.create_run(
            RunManifest(
                run_id=p.run_id,
                target_id=p.spec.target_id,
                t_unit=p.spec.t_unit,
                run_salt=p.run_salt,
                axis_types=dict(p.spec.axis_types),
                backend=p.backend,
                environment=environment,
                retain_traces_for=p.spec.retain_traces_for,
            )
        )

    ctx = _mp_context() if episode_timeout is not None else None
    total = len(p.pairs)
    batch: list[EpisodeRecord] = []
    n_ok = n_errored = n_timeout = 0
    executed = 0
    stopped_by: str | None = None
    t_run = time.perf_counter()

    def flush() -> None:
        if batch:
            store.append(p.run_id, list(batch))
            batch.clear()

    try:
        for index, pair in enumerate(p.pairs):
            config = dict(pair.config)
            t0 = time.perf_counter()
            if ctx is None:
                outcome = _call_in_process(rollout, config, pair.seed)
            else:
                assert episode_timeout is not None
                outcome = _call_with_timeout(rollout, config, pair.seed, episode_timeout, ctx)
            wall_time = time.perf_counter() - t0
            batch.append(_record(p, pair, index, outcome, wall_time))
            executed += 1
            if outcome[0] == "ok":
                n_ok += 1
            else:
                n_errored += 1
                if outcome[0] == _TIMEOUT_ERROR:
                    n_timeout += 1
            if on_progress is not None:
                on_progress(executed, total)
            if len(batch) >= batch_size:
                flush()
            if max_rollouts is not None and executed >= max_rollouts and executed < total:
                stopped_by = "max_rollouts"
                break
    finally:
        flush()

    complete = executed == total and stopped_by is None
    if complete:
        store.mark_complete(p.run_id)
    return RunSummary(
        run_id=p.run_id,
        n_ok=n_ok,
        n_errored=n_errored,
        n_timeout=n_timeout,
        wall_time=time.perf_counter() - t_run,
        stopped_by=stopped_by,
        complete=complete,
    )
