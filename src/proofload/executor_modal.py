"""M3: the Modal backend.

Runs the plan the local executor runs, across parallel Modal containers, and lands the same
rows in the same store. The local backend is the reference; this module adds placement (an
image, N containers, an outer timeout), infra failure handling (retry, then record what could
not be retried, distinct from episode errors), and a cost guard.

The mapper is the seam. ``run_with_mapper`` owns every piece of orchestration (chunking,
retries, out-of-order flush, caps, manifest, completion) and is driven by any ``Mapper``, so it
is tested without a network. ``worker_batch`` is the code that runs inside a container: pure
Python, no modal import, unit-tested locally. ``run_modal`` is the only function that imports
``modal``; it builds the app, image and function, wraps ``.map`` in a real mapper, and hands
off to ``run_with_mapper``. Core ``proofload`` imports and runs without ``modal`` installed.
"""

from __future__ import annotations

import importlib.metadata
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from proofload._resolve import resolve, split_import_path
from proofload.capture import CaptureSpec, CaptureStatus, install
from proofload.diff import mde_two_proportion
from proofload.episode import Episode
from proofload.executor import (
    _TIMEOUT_ERROR,
    ExecutorError,
    Plan,
    RunSummary,
    _call_in_process,
    _call_with_timeout,
    _capture_line,
    _capture_probe,
    _capture_record,
    _CaptureCall,
    _environment,
    _episode_id,
    _mp_context,
)
from proofload.store import EpisodeRecord, RunManifest, Store, StoreError

__all__ = [
    "CostGuard",
    "ImageSpec",
    "Job",
    "Mapper",
    "ModalBackendError",
    "ModalNotInstalled",
    "ModalOptions",
    "ModalTarget",
    "Result",
    "estimate_cost",
    "preflight_modal",
    "run_modal",
    "run_with_mapper",
    "worker_batch",
]

_BACKEND = "modal"
_INFRA_PREFIX = "infra: "
_OUTER_TIMEOUT_GRACE_S = 60
_MAX_OUTER_TIMEOUT_S = 24 * 3600
_INSTALL_HINT = "pip install proofload[modal]"

# Published Modal per-second prices (USD), read from modal.com/pricing on the date below.
# Keys are Modal gpu strings, upper-cased; "CPU" is the no-gpu rate per physical core.
# A missing key means "no estimate", never a guess.
_PRICES_ASOF = "2026-09-03"
_PRICES_PER_SECOND: dict[str, float] = {
    "CPU": 0.0000131,
    "T4": 0.000164,
    "L4": 0.000222,
    "A10G": 0.000306,
    "A10": 0.000306,
    "L40S": 0.000542,
    "A100": 0.000583,
    "A100-40GB": 0.000583,
    "A100-80GB": 0.000694,
    "RTX-PRO-6000": 0.000842,
    "H100": 0.001097,
    "H200": 0.001261,
    "B200": 0.001736,
    "B300": 0.001972,
}


class ModalBackendError(ExecutorError):
    """The Modal backend cannot run as requested."""


class ModalNotInstalled(ModalBackendError):
    """``run_modal`` was called without the ``modal`` package (the ``[modal]`` extra)."""


class CostGuard(ModalBackendError):
    """``max_cost`` is set and the run is refused before any container starts."""


# ---------- specs ----------


def _split_import_path(import_path: str) -> tuple[str, str]:
    return split_import_path(import_path)


@dataclass(frozen=True)
class ImageSpec:
    """What the container image is built from. Nothing is inferred: the user lists it.

    ``dockerfile`` replaces the ``python``/``pip``/``apt`` build and is exclusive with ``pip``
    and ``apt``. ``local_packages`` are importable local packages shipped into the image
    (``proofload`` itself is always shipped). ``gpu`` is a Modal gpu string such as ``"A10G"``.
    """

    python: str = "3.11"
    pip: tuple[str, ...] = ()
    apt: tuple[str, ...] = ()
    dockerfile: Path | None = None
    local_packages: tuple[str, ...] = ()
    gpu: str | None = None

    def __post_init__(self) -> None:
        for name in ("pip", "apt", "local_packages"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.dockerfile is not None:
            object.__setattr__(self, "dockerfile", Path(self.dockerfile))
            if self.pip or self.apt:
                raise ValueError("ImageSpec: dockerfile is mutually exclusive with pip and apt")
        if not isinstance(self.python, str) or not self.python:
            raise ValueError("ImageSpec: python must be a non-empty version string")

    def to_dict(self) -> dict[str, Any]:
        """JSON-native view (lists, ``dockerfile`` as a string); what the manifest stores."""
        return {
            "python": self.python,
            "pip": list(self.pip),
            "apt": list(self.apt),
            "dockerfile": None if self.dockerfile is None else str(self.dockerfile),
            "local_packages": list(self.local_packages),
            "gpu": self.gpu,
        }


@dataclass(frozen=True)
class ModalTarget:
    """The rollout as the container sees it: an import path resolved inside ``image``."""

    import_path: str
    image: ImageSpec

    def __post_init__(self) -> None:
        _split_import_path(self.import_path)
        if not isinstance(self.image, ImageSpec):
            raise ValueError("ModalTarget: image must be an ImageSpec")


@dataclass(frozen=True)
class ModalOptions:
    concurrency: int = 16
    batch_size: int = 64
    episode_timeout: float | None = 300.0
    infra_retries: int = 2
    max_rollouts: int | None = None
    max_cost: float | None = None
    est_seconds_per_episode: float | None = None
    app_name: str = "proofload"


_DEFAULT_OPTIONS = ModalOptions()


def _validate_options(options: ModalOptions) -> None:
    if options.concurrency < 1:
        raise ExecutorError(f"concurrency must be >= 1, got {options.concurrency}")
    if options.batch_size < 1:
        raise ExecutorError(f"batch_size must be >= 1, got {options.batch_size}")
    if options.infra_retries < 0:
        raise ExecutorError(f"infra_retries must be >= 0, got {options.infra_retries}")
    if options.max_rollouts is not None and options.max_rollouts < 1:
        raise ExecutorError(f"max_rollouts must be >= 1 when given, got {options.max_rollouts}")
    if options.episode_timeout is not None and options.episode_timeout <= 0:
        raise ExecutorError(
            f"episode_timeout must be > 0 when given, got {options.episode_timeout}"
        )
    if options.max_cost is not None and options.max_cost < 0:
        raise ExecutorError(f"max_cost must be >= 0 when given, got {options.max_cost}")
    if options.est_seconds_per_episode is not None and options.est_seconds_per_episode <= 0:
        raise ExecutorError(
            f"est_seconds_per_episode must be > 0 when given, got {options.est_seconds_per_episode}"
        )
    if not options.app_name:
        raise ExecutorError("app_name must be a non-empty string")


# ---------- the map boundary ----------

Job = tuple[dict[str, Any], int, int, str, int]
"""``(config, seed, i, config_hash, replicate_index)``; ``i`` is the position in ``p.pairs``."""

Result = dict[str, Any] | str
"""``episode.to_dict()`` merged with ``wall_time`` and ``backend_meta``, or an error string."""

Mapper = Callable[[Sequence[Sequence[Job]]], Iterator[tuple[int, list[Result] | BaseException]]]
"""Given batches, yields ``(batch_index, results-or-exception)`` in completion order. An
exception is an infra failure of the whole batch; ``batch_index`` refers to the call's input."""


def _resolve_rollout(import_path: str) -> Any:
    return resolve(import_path)


_CAPTURE_FIELDS = ("instrument", "content", "max_span_bytes", "max_spans")


def _capture_payload(spec: CaptureSpec | None, run_id: str) -> dict[str, Any] | None:
    """The ``capture`` argument of ``worker_batch``: the four ``CaptureSpec`` fields as
    JSON-native values, plus the run id. The id rides ``_MapItem`` to the container and then
    travels inside this dict, because ``Job`` is not extended and there is no other route."""
    if spec is None:
        return None
    return {
        "run_id": run_id,
        "instrument": list(spec.instrument),
        "content": spec.content,
        "max_span_bytes": spec.max_span_bytes,
        "max_spans": spec.max_spans,
    }


def _capture_request(payload: Mapping[str, Any] | None) -> tuple[CaptureSpec | None, str]:
    """The inverse, inside the container: the run id off the front, the spec from the rest."""
    if payload is None:
        return None, ""
    fields = {name: payload[name] for name in _CAPTURE_FIELDS if name in payload}
    return CaptureSpec(**fields), str(payload.get("run_id", ""))


def _capture_status(status: CaptureStatus) -> dict[str, Any]:
    return {
        "requested": status.requested,
        "active": status.active,
        "reason": status.reason,
        "instrumented": list(status.instrumented),
    }


def worker_batch(
    jobs: Sequence[Job],
    import_path: str,
    episode_timeout: float | None,
    *,
    capture: dict[str, Any] | None = None,
) -> list[Result]:
    """Run one batch. This is the code inside the container: pure Python, no modal import.

    ``import_path`` is resolved once per call; the rollout is called once per job with a fresh
    ``dict(config)``. One ``Result`` per job, in job order: the episode dict, the traceback text
    of a raising rollout, ``"rollout returned <type>, expected Episode"``, or ``"timeout"``
    (a fork-and-join per episode, the local backend's mechanics). Anything that fails outside
    a single episode (a resolve failure, a bad timeout) raises, so the whole batch is an infra
    failure rather than N identical episode errors.

    ``capture`` is the sweep's ``[capture]`` table plus the run id. It is keyword-only with a
    None default because nine existing call sites pass three positional arguments. What
    actually happened in the container comes back on every result at
    ``backend_meta["capture"]``: the host cannot know, and a manifest that claimed to would
    be lying.
    """
    if episode_timeout is not None and episode_timeout <= 0:
        raise ValueError(f"episode_timeout must be > 0 when given, got {episode_timeout}")
    rollout = _resolve_rollout(import_path)
    ctx = _mp_context() if episode_timeout is not None else None
    capture_spec, run_id = _capture_request(capture)
    status: CaptureStatus | None = None
    if capture_spec is not None:
        # With a timeout each episode is a forked child, so the provider goes in there (C1)
        # and one probe child measures what those children will get.
        status = _capture_probe(capture_spec) if ctx is not None else install(capture_spec)
    results: list[Result] = []
    for config, seed, i, config_hash, replicate_index in jobs:
        fresh = dict(config)
        call = (
            None
            if capture_spec is None
            else _CaptureCall(
                spec=capture_spec,
                run_id=run_id,
                episode_id=_episode_id(config_hash, replicate_index),
            )
        )
        t0 = time.perf_counter()
        if ctx is None:
            outcome = _call_in_process(rollout, fresh, seed, call)
        else:
            assert episode_timeout is not None
            outcome = _call_with_timeout(rollout, fresh, seed, episode_timeout, ctx, call)
        wall_time = time.perf_counter() - t0
        kind, payload = outcome
        if kind == "ok":
            result: dict[str, Any] = dict(payload)
            result["wall_time"] = wall_time
            result["backend_meta"] = {"i": i}
            if status is not None:
                result["backend_meta"]["capture"] = _capture_status(status)
            results.append(result)
        elif kind == _TIMEOUT_ERROR:
            results.append(_TIMEOUT_ERROR)
        else:
            results.append(str(payload))
    return results


# ---------- orchestration ----------


def _jobs(p: Plan) -> list[Job]:
    return [
        (dict(pair.config), pair.seed, i, pair.config_hash, pair.replicate_index)
        for i, pair in enumerate(p.pairs)
    ]


def _open_run(
    p: Plan, store: Store, options: ModalOptions, image: ImageSpec, import_path: str | None
) -> None:
    """The local backend's run gating, with the modal manifest on fresh runs."""
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
        return
    if existing is not None:
        raise ExecutorError(f"run {p.run_id!r} already exists; plan with resume= to continue it")
    environment = _environment(p.spec)
    environment.update(
        image=image.to_dict(),
        modal_app=options.app_name,
        concurrency=options.concurrency,
        import_path=import_path,
    )
    if p.spec.capture is not None:
        environment["capture"] = _capture_record(
            p.spec.capture,
            CaptureStatus(
                requested=True,
                active=False,
                reason=(
                    "the host installs nothing for a Modal run; the container may not even "
                    "hold the packages. Each batch records what happened at "
                    "backend_meta['capture']"
                ),
                instrumented=(),
            ),
        )
    store.create_run(
        RunManifest(
            run_id=p.run_id,
            target_id=p.spec.target_id,
            t_unit=p.spec.t_unit,
            run_salt=p.run_salt,
            axis_types=dict(p.spec.axis_types),
            backend=_BACKEND,
            environment=environment,
            retain_traces_for=p.spec.retain_traces_for,
        )
    )


def _record(p: Plan, job: Job, result: Result, attempt: int) -> EpisodeRecord:
    config, seed, i, _config_hash, replicate_index = job
    if isinstance(result, str):
        return EpisodeRecord.errored(
            run_id=p.run_id,
            config=config,
            seed=seed,
            replicate_index=replicate_index,
            error=result,
            wall_time=0.0,
            backend_meta={"i": i, "attempt": attempt},
        )
    backend_meta = dict(result.get("backend_meta") or {})
    backend_meta.setdefault("i", i)
    backend_meta["attempt"] = attempt
    try:
        episode = Episode.from_dict(result)
    except Exception as exc:
        raise ModalBackendError(f"worker returned an invalid episode for job {i}: {exc}") from exc
    return EpisodeRecord.from_episode(
        episode,
        run_id=p.run_id,
        config=config,
        seed=seed,
        replicate_index=replicate_index,
        wall_time=float(result.get("wall_time", 0.0)),
        backend_meta=backend_meta,
    )


def _infra_record(p: Plan, job: Job, exc: BaseException, attempt: int) -> EpisodeRecord:
    config, seed, i, _config_hash, replicate_index = job
    return EpisodeRecord.errored(
        run_id=p.run_id,
        config=config,
        seed=seed,
        replicate_index=replicate_index,
        error=f"{_INFRA_PREFIX}{exc!r}",
        wall_time=0.0,
        backend_meta={"i": i, "attempt": attempt},
    )


def _check_cost(p: Plan, options: ModalOptions, image: ImageSpec) -> None:
    if options.max_cost is None:
        return
    estimate = estimate_cost(p, options, image)
    if estimate is None:
        raise CostGuard(
            "max_cost is set but no estimate is possible: pass est_seconds_per_episode "
            "(and a gpu with a known price) or drop max_cost"
        )
    if estimate > options.max_cost:
        raise CostGuard(
            f"estimated cost ~${estimate:.2f} exceeds max_cost ${options.max_cost:.2f} "
            f"(best-effort, {_PRICES_ASOF} prices)"
        )


def run_with_mapper(
    p: Plan,
    mapper: Mapper,
    store: Store,
    *,
    options: ModalOptions,
    image: ImageSpec | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> RunSummary:
    """Execute a plan through ``mapper``; never imports modal.

    Batches are ``batch_size`` jobs in plan order; each is one map item and one store part,
    flushed the moment it arrives, in completion order. A batch whose mapper result is an
    exception is re-submitted with the same jobs up to ``infra_retries`` times; exhausted
    batches are stored one row per job with ``error="infra: <repr>"``. ``max_rollouts`` limits
    submission to the batches up to the one holding the Nth episode; those are all drained and
    stored, then the run is left partial with ``stopped_by="max_rollouts"``. Anything the
    mapper raises propagates after every batch that arrived has been stored.
    """
    _validate_options(options)
    image_spec = ImageSpec() if image is None else image
    _check_cost(p, options, image_spec)
    _open_run(p, store, options, image_spec, getattr(mapper, "import_path", None))

    total = len(p.pairs)
    jobs = _jobs(p)
    size = options.batch_size
    batches = [jobs[k : k + size] for k in range(0, total, size)]
    n_submit = len(batches)
    if options.max_rollouts is not None:
        n_submit = min(n_submit, (options.max_rollouts - 1) // size + 1)

    attempts = [0] * len(batches)
    pending = list(range(n_submit))
    n_ok = n_errored = n_timeout = n_infra_retried = n_infra_failed = 0
    executed = 0
    t_run = time.perf_counter()

    def store_batch(records: list[EpisodeRecord]) -> None:
        nonlocal executed
        store.append(p.run_id, list(records))
        executed += len(records)
        if on_progress is not None:
            on_progress(executed, total)

    def infra(k: int, exc: BaseException) -> None:
        nonlocal n_infra_failed, n_errored
        if attempts[k] <= options.infra_retries:
            pending.append(k)
            return
        records = [_infra_record(p, job, exc, attempts[k]) for job in batches[k]]
        n_infra_failed += len(records)
        n_errored += len(records)
        store_batch(records)

    while pending:
        submitted, pending = pending, []
        for k in submitted:
            attempts[k] += 1
        seen: set[int] = set()
        for local_index, payload in mapper([batches[k] for k in submitted]):
            if not 0 <= local_index < len(submitted):
                raise ModalBackendError(
                    f"mapper yielded batch index {local_index} for {len(submitted)} batches"
                )
            k = submitted[local_index]
            if k in seen:
                raise ModalBackendError(f"mapper yielded batch {local_index} twice")
            seen.add(k)
            if isinstance(payload, BaseException):
                infra(k, payload)
                continue
            batch = batches[k]
            if len(payload) != len(batch):
                raise ModalBackendError(
                    f"mapper returned {len(payload)} results for a batch of {len(batch)} jobs"
                )
            if attempts[k] > 1:
                n_infra_retried += 1
            records: list[EpisodeRecord] = []
            for job, result in zip(batch, payload, strict=True):
                record = _record(p, job, result, attempts[k])
                records.append(record)
                if record.error is None:
                    n_ok += 1
                else:
                    n_errored += 1
                    if record.error == _TIMEOUT_ERROR:
                        n_timeout += 1
            store_batch(records)
        for k in submitted:
            if k not in seen:
                infra(k, ModalBackendError("mapper returned no result for the batch"))

    stopped_by = "max_rollouts" if n_submit < len(batches) else None
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
        n_infra_retried=n_infra_retried,
        n_infra_failed=n_infra_failed,
    )


# ---------- cost and pre-flight ----------


def _rate_per_second(gpu: str | None) -> float | None:
    if gpu is None:
        return _PRICES_PER_SECOND["CPU"]
    name, _, count = gpu.partition(":")
    base = _PRICES_PER_SECOND.get(name.strip().upper())
    if base is None:
        return None
    if not count:
        return base
    return base * int(count) if count.isdigit() and int(count) > 0 else None


def estimate_cost(p: Plan, options: ModalOptions, image: ImageSpec) -> float | None:
    """USD, best effort: ``jobs × est_seconds_per_episode × rate(gpu)``. ``None`` without an
    estimate or for a gpu that is not in the price table."""
    if options.est_seconds_per_episode is None:
        return None
    rate = _rate_per_second(image.gpu)
    if rate is None:
        return None
    return len(p.pairs) * options.est_seconds_per_episode * rate


def _format_usd(amount: float) -> str:
    return f"{amount:,.2f}" if amount >= 0.1 else f"{amount:.4f}"


def preflight_modal(p: Plan, target: ModalTarget, options: ModalOptions) -> str:
    """Text block describing the run. Non-interactive; M10 prints it and asks."""
    spec = p.spec
    image = target.image
    total = spec.total_rollouts()
    mde = mde_two_proportion(0.5, spec.replicates, spec.replicates)
    estimate = estimate_cost(p, options, image)
    gpu = "none" if image.gpu is None else image.gpu
    timeout = "none" if options.episode_timeout is None else f"{options.episode_timeout:g}s"
    cost = (
        "Cost: unknown (no estimate)"
        if estimate is None
        else f"Cost: ~${_format_usd(estimate)} (best-effort, {_PRICES_ASOF} prices)"
    )
    lines = [
        f"Sweep: {len(spec.axis_types)} axes · {len(spec.configs)} cells · "
        f"N={spec.replicates} → {total} rollouts",
        f"Backend: {_BACKEND} · target: {spec.target_id} · t_unit: {spec.t_unit}",
        f"Image: python {image.python} · {len(image.pip)} pip · gpu: {gpu} · "
        f"import: {target.import_path}",
        f"Containers: up to {options.concurrency} · batch: {options.batch_size} · "
        f"episode timeout: {timeout}",
        cost,
        f"MDE at N={spec.replicates} (worst case, rate 0.5): {mde:.4f}",
    ]
    capture_line = _capture_line(spec.capture)
    if capture_line is not None:
        lines.append(capture_line)
    if p.resumed:
        lines.append(f"Resuming {p.run_id}: {p.already_stored} stored, {len(p.pairs)} to run")
    return "\n".join(lines) + "\n"


# ---------- the real mapper ----------

_CORE_REQUIREMENTS_FALLBACK = ("numpy", "pandas", "scipy", "pyarrow")


def _core_requirements() -> tuple[str, ...]:
    """proofload's own runtime requirements, which the worker needs inside the container.
    These are proofload's, not the user's; the user's dependencies are never inferred."""
    try:
        requires = importlib.metadata.requires("proofload") or []
    except importlib.metadata.PackageNotFoundError:
        return _CORE_REQUIREMENTS_FALLBACK
    core = tuple(req.strip() for req in requires if ";" not in req)
    return core or _CORE_REQUIREMENTS_FALLBACK


def _build_image(modal: Any, spec: ImageSpec) -> Any:
    if spec.dockerfile is not None:
        image = modal.Image.from_dockerfile(str(spec.dockerfile))
    else:
        image = modal.Image.debian_slim(python_version=spec.python)
        if spec.apt:
            image = image.apt_install(*spec.apt)
    image = image.pip_install(*_core_requirements())
    if spec.pip:
        image = image.pip_install(*spec.pip)
    return image.add_local_python_source("proofload", *spec.local_packages)


def _outer_timeout(options: ModalOptions) -> int:
    """The Modal function's own timeout: a whole-batch hang is an infra failure, not silence."""
    if options.episode_timeout is None:
        return _MAX_OUTER_TIMEOUT_S
    seconds = options.episode_timeout * options.batch_size + _OUTER_TIMEOUT_GRACE_S
    return int(min(max(seconds, 1.0), _MAX_OUTER_TIMEOUT_S))


_MapItem = tuple[int, list[Job], str, float | None, dict[str, Any] | None]
_MapOutput = tuple[int, list[Result] | None, str | None]


def _container_batch(item: _MapItem) -> _MapOutput:
    """The Modal function body. The batch index travels inside the item and comes back inside
    the output, because ``order_outputs=False`` loses position. A failure of the batch as a
    whole (a resolve error, for one) comes back as ``(k, None, traceback)`` so it keeps its
    index; only a container death loses it. The capture request rides the item too: it is the
    only way the run id reaches ``worker_batch`` without extending ``Job``."""
    k, jobs, import_path, episode_timeout, capture = item
    try:
        return k, worker_batch(jobs, import_path, episode_timeout, capture=capture), None
    except Exception:
        return k, None, traceback.format_exc()


class _ModalMapper:
    """Wraps ``function.map(order_outputs=False, return_exceptions=True)`` as a ``Mapper``.

    Exceptions arrive as values without their batch index. Every input produces exactly one
    output, so once the map is drained the indices that never came back are the failed
    batches; the stray exceptions are paired with them in arrival order (only their repr
    matters, and only once retries are exhausted).
    """

    def __init__(
        self,
        remote: Any,
        import_path: str,
        episode_timeout: float | None,
        capture: dict[str, Any] | None = None,
    ) -> None:
        self.remote = remote
        self.import_path = import_path
        self.episode_timeout = episode_timeout
        self.capture = capture

    def __call__(
        self, batches: Sequence[Sequence[Job]]
    ) -> Iterator[tuple[int, list[Result] | BaseException]]:
        items: list[_MapItem] = [
            (k, [tuple(job) for job in jobs], self.import_path, self.episode_timeout, self.capture)  # type: ignore[misc]
            for k, jobs in enumerate(batches)
        ]
        seen: set[int] = set()
        stray: list[BaseException] = []
        for payload in self.remote.map(items, order_outputs=False, return_exceptions=True):
            if isinstance(payload, BaseException):
                stray.append(payload)
                continue
            k, results, failure = payload
            if k in seen:
                continue
            seen.add(k)
            if results is None:
                yield k, ModalBackendError(f"worker failed: {failure}")
            else:
                yield k, results
        for k in range(len(batches)):
            if k not in seen:
                exc = stray.pop(0) if stray else ModalBackendError("no result returned")
                yield k, exc


def run_modal(
    p: Plan,
    target: ModalTarget,
    store: Store,
    *,
    options: ModalOptions = _DEFAULT_OPTIONS,
    on_progress: Callable[[int, int], None] | None = None,
) -> RunSummary:
    """Run the plan on Modal. Imports ``modal`` here and nowhere else.

    Builds the app, the image from ``target.image``, and one function with the outer timeout
    (``episode_timeout × batch_size + 60``), ``retries=0`` (retries are ours, so attempts are
    counted and recorded) and ``max_containers=concurrency``; then ``run_with_mapper`` does the
    rest. The cost guard fires before the app starts.
    """
    try:
        import modal
    except ImportError as exc:
        raise ModalNotInstalled(
            f"the Modal backend needs the `modal` package: {_INSTALL_HINT}"
        ) from exc
    _validate_options(options)
    _check_cost(p, options, target.image)
    image = _build_image(modal, target.image)
    app = modal.App(options.app_name)
    remote = app.function(
        image=image,
        gpu=target.image.gpu,
        timeout=_outer_timeout(options),
        retries=0,
        max_containers=options.concurrency,
        serialized=True,
    )(_container_batch)
    mapper = _ModalMapper(
        remote,
        target.import_path,
        options.episode_timeout,
        _capture_payload(p.spec.capture, p.run_id),
    )
    with app.run():
        return run_with_mapper(
            p, mapper, store, options=options, image=target.image, on_progress=on_progress
        )
