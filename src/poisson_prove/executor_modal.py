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
off to ``run_with_mapper``. Core ``poisson_prove`` imports and runs without ``modal`` installed.
"""

from __future__ import annotations

import importlib.metadata
import re
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from poisson_prove._resolve import resolve, split_import_path
from poisson_prove.capture import CaptureSpec, CaptureStatus, install
from poisson_prove.chaos import ChaosSpec, ChaosStatus, _installed_hooks
from poisson_prove.chaos import install as chaos_install
from poisson_prove.chaos_catalog import ENGINE_VERSION as CATALOG_VERSION
from poisson_prove.episode import Episode
from poisson_prove.executor import (
    _TIMEOUT_ERROR,
    ExecutorError,
    Plan,
    RunSummary,
    _accepted_mde,
    _call_in_process,
    _call_with_timeout,
    _capture_line,
    _capture_probe,
    _capture_record,
    _CaptureCall,
    _chaos_record,
    _ChaosCall,
    _declared_limit,
    _environment,
    _episode_id,
    _mp_context,
    _spec_declared,
    _with_capture_envelope,
    preflight_mde,
)
from poisson_prove.store import EpisodeRecord, RunManifest, Store, StoreError

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
_INSTALL_HINT = 'pip install "poisson-prove[modal]"'

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
    (``poisson_prove`` itself is always shipped). ``gpu`` is a Modal gpu string such as ``"A10G"``.
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


# A Modal secret is named here and never read here: the value stays in the Modal workspace,
# so "no Prove output can carry it" is structural rather than a filter over strings
# (ADR-030). The bounds below are Prove's own and deliberately narrower than whatever
# Modal accepts; widening them is a one-constant change.
_SECRET_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SECRET_NAME_MAX = 64
_SECRET_CREATE_FORM = "modal secret create <name> KEY=VALUE"


def _secret_names(value: object) -> tuple[str, ...]:
    """``[modal] secrets`` -> a tuple of names; ValueError on anything else.

    A bare ``str`` is refused rather than iterated: ``"golden-pilot"`` silently becoming
    twelve one-character names is the worst available reading of a typo. No message below
    repeats an entry, because the likeliest malformed entry is a pasted credential and a
    refusal that echoed one would put it in the terminal, the shell history and the CI log.
    """
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ValueError(
            "ModalOptions: secrets must be a list of Modal secret names, "
            f"got {type(value).__name__}"
        )
    names: list[str] = []
    for position, entry in enumerate(value):
        where = f"secrets[{position}]"
        if not isinstance(entry, str):
            raise ValueError(f"ModalOptions: {where} must be a name, got {type(entry).__name__}")
        if "=" in entry:
            raise ValueError(
                f"ModalOptions: {where} looks like KEY=VALUE. secrets holds the names of "
                f"secrets that already exist in your Modal workspace; create one with "
                f"`{_SECRET_CREATE_FORM}` and list <name> here"
            )
        if not entry:
            raise ValueError(f"ModalOptions: {where} is empty")
        if len(entry) > _SECRET_NAME_MAX:
            raise ValueError(
                f"ModalOptions: {where} is {len(entry)} characters, over the "
                f"{_SECRET_NAME_MAX} a secret name may have"
            )
        if any(char.isspace() for char in entry):
            raise ValueError(f"ModalOptions: {where} contains whitespace")
        if _SECRET_NAME_RE.match(entry) is None:
            raise ValueError(
                f"ModalOptions: {where} is not a secret name: letters, digits, '.', '_' and "
                "'-' only, starting with a letter or a digit"
            )
        if entry in names:
            raise ValueError(f"ModalOptions: {where} repeats a name already listed")
        names.append(entry)
    return tuple(names)


@dataclass(frozen=True)
class ModalOptions:
    concurrency: int = 16
    batch_size: int = 64
    episode_timeout: float | None = 300.0
    infra_retries: int = 2
    max_rollouts: int | None = None
    max_cost: float | None = None
    est_seconds_per_episode: float | None = None
    app_name: str = "poisson-prove"
    # The names of Modal secrets mounted on the remote function, never their values. Last and
    # defaulted, so every existing keyword construction and comparison is untouched.
    secrets: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "secrets", _secret_names(self.secrets))


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
"""``episode.to_dict()`` merged with ``wall_time`` and ``backend_meta``, an error string, or --
for an errored job that kept its trace -- ``{"error": <text>, "meta": {"trace": ...}}``, exactly
those two keys, whatever the error was: ``"timeout"`` for a child that drained on SIGTERM, the
traceback text or ``"rollout returned <type>, expected Episode"`` for a rollout that crashed
under capture."""

Mapper = Callable[[Sequence[Sequence[Job]]], Iterator[tuple[int, list[Result] | BaseException]]]
"""Given batches, yields ``(batch_index, results-or-exception)`` in completion order. An
exception is an infra failure of the whole batch; ``batch_index`` refers to the call's input."""


def _resolve_rollout(import_path: str) -> Any:
    return resolve(import_path)


_CAPTURE_FIELDS = ("instrument", "content", "max_observation_bytes", "max_spans")


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
        "max_observation_bytes": spec.max_observation_bytes,
        "max_spans": spec.max_spans,
    }


def _capture_request(payload: Mapping[str, Any] | None) -> tuple[CaptureSpec | None, str]:
    """The inverse, inside the container: the run id off the front, the spec from the rest.

    **Strict about the field names, and the strictness is the point.** Reading by intersection
    would drop a key this side does not know -- a retired spelling, or a host one version
    ahead -- and run the whole batch at the default with no error on either side of the
    process boundary, while the manifest recorded what the sweep file asked for. That is a
    wrong measurement rather than a crash, and it is invisible from both ends. The sweep-file
    parser already refuses an unknown field loudly; this is the same rename one process
    boundary over, so it refuses one too.
    """
    if payload is None:
        return None, ""
    unknown = sorted(set(payload) - {"run_id", *_CAPTURE_FIELDS})
    if unknown:
        raise ValueError(
            f"capture payload has unknown field(s): {', '.join(unknown)}; "
            f"the fields are {', '.join(_CAPTURE_FIELDS)}"
        )
    missing = [name for name in _CAPTURE_FIELDS if name not in payload]
    if missing:
        raise ValueError(
            f"capture payload is missing field(s): {', '.join(missing)}; "
            f"the fields are {', '.join(_CAPTURE_FIELDS)}. There is no default: a "
            "payload without one of these is a host and a container at different versions."
        )
    fields = {name: payload[name] for name in _CAPTURE_FIELDS}
    return CaptureSpec(**fields), str(payload.get("run_id", ""))


_CHAOS_FIELDS: tuple[str, ...] = ("fault", "rate", "steps")


def _chaos_payload(spec: ChaosSpec | None) -> dict[str, Any] | None:
    """The ``chaos`` argument of ``worker_batch``: the three ``ChaosSpec`` fields as JSON-native
    values. It rides ``_MapItem`` to the container beside the capture request."""
    if spec is None:
        return None
    return {"fault": spec.fault, "rate": spec.rate, "steps": list(spec.steps)}


def _chaos_request(payload: Mapping[str, Any] | None) -> ChaosSpec | None:
    """The ``[chaos]`` table as it crosses into the container: three JSON-native fields."""
    if payload is None:
        return None
    fields = {name: payload[name] for name in _CHAOS_FIELDS if name in payload}
    if "steps" in fields:
        fields["steps"] = tuple(fields["steps"])
    return ChaosSpec(**fields)


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
    chaos: dict[str, Any] | None = None,
) -> list[Result]:
    """Run one batch. This is the code inside the container: pure Python, no modal import.

    ``import_path`` is resolved once per call; the rollout is called once per job with a fresh
    ``dict(config)``. One ``Result`` per job, in job order: the episode dict, the traceback text
    of a raising rollout, ``"rollout returned <type>, expected Episode"``, or ``"timeout"``
    (a fork-and-join per episode, the local backend's mechanics). An error rides as
    ``{"error": <text>, "meta": {"trace": ...}}`` when the episode kept a trace, which only an
    episode with capture does: the terminated child drained the snapshot of its spans, or the
    rollout raised (or returned the wrong thing) after emitting spans. Anything that fails
    outside a single episode (a resolve failure, a bad timeout) raises, so the whole batch is
    an infra failure rather than N identical episode errors.

    ``capture`` is the sweep's ``[capture]`` table plus the run id. It is keyword-only with a
    None default because nine existing call sites pass three positional arguments. What
    actually happened in the container comes back on every result at
    ``backend_meta["capture"]``: the host cannot know, and a manifest that claimed to would
    be lying.

    ``chaos`` rides beside it, the sweep's ``[chaos]`` table as three JSON-native fields, and
    comes back the same way at ``backend_meta["chaos"]``. Arming it is the batch's first act:
    a refused injection raises out of the whole batch rather than producing N episodes that
    quietly measure the control arm twice.
    """
    if episode_timeout is not None and episode_timeout <= 0:
        raise ValueError(f"episode_timeout must be > 0 when given, got {episode_timeout}")
    rollout = _resolve_rollout(import_path)
    ctx = _mp_context() if episode_timeout is not None else None
    capture_spec, run_id = _capture_request(capture)
    chaos_spec = _chaos_request(chaos)
    chaos_status: ChaosStatus | None = None
    if chaos_spec is not None:
        chaos_status = chaos_install(chaos_spec)
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
        chaos_call = None if chaos_spec is None else _ChaosCall(spec=chaos_spec)
        t0 = time.perf_counter()
        if ctx is None:
            outcome = _call_in_process(rollout, fresh, seed, call, chaos_call)
        else:
            assert episode_timeout is not None
            outcome = _call_with_timeout(
                rollout, fresh, seed, episode_timeout, ctx, call, chaos_call
            )
        wall_time = time.perf_counter() - t0
        kind, payload = outcome
        if kind == "ok":
            result: dict[str, Any] = dict(payload)
            result["wall_time"] = wall_time
            result["backend_meta"] = {"i": i}
            if status is not None:
                result["backend_meta"]["capture"] = _capture_status(status)
            if chaos_spec is not None and chaos_status is not None:
                result["backend_meta"]["chaos"] = _chaos_record(
                    chaos_spec, chaos_status, _installed_hooks()
                )
            results.append(result)
        elif kind == _TIMEOUT_ERROR:
            # The dict form, exactly two keys, only when the terminated child drained a trace;
            # the bare string otherwise, as the frozen I3 test sees it without capture.
            results.append(
                {"error": _TIMEOUT_ERROR, "meta": {"trace": payload}}
                if isinstance(payload, dict)
                else _TIMEOUT_ERROR
            )
        elif kind == "error" and isinstance(payload, dict):
            # An error that kept its trace: the two-key dict is the Result it already is. The
            # kind was read first, so a timeout's bare trace dict never lands here.
            results.append(payload)
        else:
            results.append(str(payload))
    return results


# ---------- orchestration ----------


def _jobs(p: Plan) -> list[Job]:
    return [
        (dict(pair.config), pair.seed, i, pair.config_hash, pair.replicate_index)
        for i, pair in enumerate(p.pairs)
    ]


_SHARED_FIELDS = (
    "python",
    "platform",
    "poisson_prove_version",
    "sweep",
    "infra_retries",
    "import_path",
    "max_mde_accepted",
    "capture",
    "chaos",
)
_MODAL_CAPTURE_REASON = (
    "the host installs nothing for a Modal run; the container may not even "
    "hold the packages. Each batch records what happened at "
    "backend_meta['capture']"
)
_WORKER_CAPTURE_REASON = (
    "the host installs nothing for a {name} run; each batch records what happened in its "
    "worker at backend_meta['capture']"
)


def _open_run(
    p: Plan,
    store: Store,
    options: ModalOptions,
    image: ImageSpec,
    import_path: str | None,
    *,
    backend: str = _BACKEND,
    placement: Mapping[str, Any] | None = None,
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
    if placement is None:
        environment.update(
            image=image.to_dict(),
            modal_app=options.app_name,
            concurrency=options.concurrency,
            infra_retries=options.infra_retries,
            import_path=import_path,
            secrets=list(options.secrets),
            max_mde_accepted=_accepted_mde(p),
        )
    else:
        environment.update(
            infra_retries=options.infra_retries,
            import_path=import_path,
            max_mde_accepted=_accepted_mde(p),
        )
        environment.update(placement)
    if p.spec.capture is not None:
        reason = (
            _MODAL_CAPTURE_REASON
            if backend == _BACKEND
            else _WORKER_CAPTURE_REASON.format(name=backend.capitalize())
        )
        environment["capture"] = _capture_record(
            p.spec.capture,
            CaptureStatus(requested=True, active=False, reason=reason, instrumented=()),
        )
    if p.spec.chaos is not None:
        # The host arms nothing: the hooks belong to the process that makes the calls, and
        # that is a container. The manifest carries the request, and every result carries
        # what the container actually armed at ``backend_meta["chaos"]``.
        environment["chaos"] = _chaos_record(
            p.spec.chaos,
            ChaosStatus(
                requested=True,
                fault=p.spec.chaos.fault,
                rate=p.spec.chaos.rate,
                steps=p.spec.chaos.steps,
                engine_version=None if p.spec.chaos.fault == "none" else CATALOG_VERSION,
            ),
            (),
        )
    store.create_run(
        RunManifest(
            run_id=p.run_id,
            target_id=p.spec.target_id,
            t_unit=p.spec.t_unit,
            run_salt=p.run_salt,
            axis_types=dict(p.spec.axis_types),
            backend=backend,
            environment=environment,
            retain_traces_for=p.spec.retain_traces_for,
            declared=_spec_declared(p.spec),
            name=p.name,
        )
    )


def _batch_capture_active(payload: Sequence[Result]) -> bool:
    """Whether capture was active in the container that ran this batch.

    The host cannot know: it is the container that installs, and what happened there comes back
    on ``backend_meta["capture"]``. A batch is one map item in one container, so the flag is the
    batch's and not the row's -- which is what makes it readable at all, since an errored result
    carries no ``backend_meta`` and the ok results beside it are what say so.
    """
    for result in payload:
        if isinstance(result, Mapping):
            capture = (result.get("backend_meta") or {}).get("capture")
            if isinstance(capture, Mapping):
                return bool(capture.get("active"))
    return False


def _require_chaos_records(p: Plan, records: Sequence[EpisodeRecord]) -> None:
    """A chaos run's ok rows each carry ``backend_meta["chaos"]``, or the batch is refused.

    The host arms nothing on a mapper run: the hooks belong to the process that makes the calls,
    and only that process can say what it armed. An ok row without the record ran in a worker
    that was never handed the table, so it measured the control arm while the manifest records
    the fault -- a wrong measurement that reads as a clean one. It is refused before it is
    stored, whichever mapper produced it. Errored rows carry no ``backend_meta`` from the worker
    and are not asked for one.
    """
    if p.spec.chaos is None:
        return
    missing = sum(1 for r in records if r.error is None and "chaos" not in r.backend_meta)
    if missing:
        raise ModalBackendError(
            f"run {p.run_id!r} requested [chaos] (fault {p.spec.chaos.fault!r}), but {missing} "
            'ok row(s) came back without backend_meta["chaos"], the per-row chaos record: '
            "the worker that ran them was never handed the chaos table, so they measured the "
            "control arm. Refused before storing them; a mapper passes chaos= to worker_batch"
        )


def _record(
    p: Plan, job: Job, result: Result, attempt: int, *, capture_active: bool = False
) -> EpisodeRecord:
    """A string is an error without meta, a dict with ``"error"`` is one with it, and any
    other dict is an episode. A dict with ``"error"`` whose meta is not a mapping is refused
    (E13), as an invalid episode dict is."""
    config, seed, i, _config_hash, replicate_index = job
    if isinstance(result, str) or "error" in result:
        meta: Mapping[str, Any] | None = None
        if isinstance(result, str):
            error = result
        else:
            error = str(result["error"])
            carried = result.get("meta")
            if not isinstance(carried, Mapping):
                # The dict form is exactly {"error", "meta"} with a mapping meta. Anything else
                # is a malformed worker result, refused like an invalid episode dict: a row
                # stored without the meta it carried is the silent loss S16 exists to end.
                raise ModalBackendError(
                    f"worker returned an errored result with a non-mapping meta for job {i}: "
                    f"{type(carried).__name__}"
                )
            meta = carried
        return _with_capture_envelope(
            EpisodeRecord.errored(
                run_id=p.run_id,
                config=config,
                seed=seed,
                replicate_index=replicate_index,
                error=error,
                wall_time=0.0,
                backend_meta={"i": i, "infra_attempt": attempt},
                meta=meta,
            ),
            capture_active,
            _declared_limit(p.spec),
            _spec_declared(p.spec),
        )
    backend_meta = dict(result.get("backend_meta") or {})
    backend_meta.setdefault("i", i)
    backend_meta["infra_attempt"] = attempt
    try:
        episode = Episode.from_dict(result)
    except Exception as exc:
        raise ModalBackendError(f"worker returned an invalid episode for job {i}: {exc}") from exc
    return _with_capture_envelope(
        EpisodeRecord.from_episode(
            episode,
            run_id=p.run_id,
            config=config,
            seed=seed,
            replicate_index=replicate_index,
            wall_time=float(result.get("wall_time", 0.0)),
            backend_meta=backend_meta,
        ),
        capture_active,
        _declared_limit(p.spec),
        _spec_declared(p.spec),
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
        backend_meta={"i": i, "infra_attempt": attempt},
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
    backend: str = _BACKEND,
    placement: Mapping[str, Any] | None = None,
    cost_check: Callable[[Plan], None] | None = None,
) -> RunSummary:
    """Execute a plan through ``mapper``; never imports modal.

    Batches are ``batch_size`` jobs in plan order; each is one map item and one store part,
    flushed the moment it arrives, in completion order. A batch whose mapper result is an
    exception is re-submitted with the same jobs up to ``infra_retries`` times; exhausted
    batches are stored one row per job with ``error="infra: <repr>"``. ``max_rollouts`` limits
    submission to the batches up to the one holding the Nth episode; those are all drained and
    stored, then the run is left partial with ``stopped_by="max_rollouts"``. Anything the
    mapper raises propagates after every batch that arrived has been stored. A batch of a
    ``[chaos]`` run whose ok rows lack ``backend_meta["chaos"]`` is refused before it is stored.
    """
    _validate_options(options)
    if backend != _BACKEND and (placement is None or cost_check is None):
        raise ModalBackendError(
            f"backend {backend!r} must pass both placement= and cost_check=: without them its "
            "run would be labelled with Modal's placement fields and priced with Modal's table"
        )
    if placement is not None:
        clash = sorted(set(placement) & set(_SHARED_FIELDS))
        if clash:
            raise ModalBackendError(
                f"placement names shared manifest field(s) {', '.join(clash)}; the runner writes "
                "those itself, whatever the backend"
            )
    image_spec = ImageSpec() if image is None else image
    if cost_check is None:
        _check_cost(p, options, image_spec)
    else:
        cost_check(p)
    _open_run(
        p,
        store,
        options,
        image_spec,
        getattr(mapper, "import_path", None),
        backend=backend,
        placement=placement,
    )

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
            batch_capture = _batch_capture_active(payload)
            for job, result in zip(batch, payload, strict=True):
                record = _record(p, job, result, attempts[k], capture_active=batch_capture)
                records.append(record)
                if record.error is None:
                    n_ok += 1
                else:
                    n_errored += 1
                    if record.error == _TIMEOUT_ERROR:
                        n_timeout += 1
            _require_chaos_records(p, records)
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
    mde = preflight_mde(spec)
    estimate = estimate_cost(p, options, image)
    gpu = "none" if image.gpu is None else image.gpu
    timeout = "none" if options.episode_timeout is None else f"{options.episode_timeout:g}s"
    mounts = (
        "Secrets: none"
        if not options.secrets
        else f"Secrets: {', '.join(options.secrets)} · mounted by name; "
        "Prove never reads the values"
    )
    covers = f"Modal's {_PRICES_ASOF} prices, which cover compute, not model tokens"
    if estimate is not None:
        cost = f"Cost: ~${_format_usd(estimate)} (best-effort, {covers})"
    elif options.est_seconds_per_episode is None:
        cost = f"Cost: unknown (no estimate; {covers})"
    else:
        cost = f"Cost: unknown (no price for gpu {gpu} in the table; {covers})"
    lines = [
        f"Sweep: {len(spec.axis_types)} axes · {len(spec.configs)} cells · "
        f"N={spec.replicates} → {total} rollouts",
        f"Backend: {_BACKEND} · target: {spec.target_id} · t_unit: {spec.t_unit}",
        f"Image: python {image.python} · {len(image.pip)} pip · gpu: {gpu} · "
        f"import: {target.import_path}",
        f"Target: {target.import_path} · resolved inside the container, not on this machine",
        f"Containers: up to {options.concurrency} · batch: {options.batch_size} · "
        f"episode timeout: {timeout}",
        mounts,
        cost,
        f"MDE at N={spec.replicates} (base rate 0.5): {mde:.4f}",
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
    """Prove's own runtime requirements, which the worker needs inside the container.
    These are Prove's, not the user's; the user's dependencies are never inferred."""
    try:
        requires = importlib.metadata.requires("poisson-prove") or []
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
    return image.add_local_python_source("poisson_prove", *spec.local_packages)


def _outer_timeout(options: ModalOptions) -> int:
    """The Modal function's own timeout: a whole-batch hang is an infra failure, not silence."""
    if options.episode_timeout is None:
        return _MAX_OUTER_TIMEOUT_S
    seconds = options.episode_timeout * options.batch_size + _OUTER_TIMEOUT_GRACE_S
    return int(min(max(seconds, 1.0), _MAX_OUTER_TIMEOUT_S))


_MapItem = tuple[int, list[Job], str, float | None, dict[str, Any] | None, dict[str, Any] | None]
_MapOutput = tuple[int, list[Result] | None, str | None]


def _container_batch(item: _MapItem) -> _MapOutput:
    """The Modal function body. The batch index travels inside the item and comes back inside
    the output, because ``order_outputs=False`` loses position. A failure of the batch as a
    whole (a resolve error, for one) comes back as ``(k, None, traceback)`` so it keeps its
    index; only a container death loses it. The capture request rides the item too: it is the
    only way the run id reaches ``worker_batch`` without extending ``Job``. The chaos request
    rides beside it for the same reason: the hooks belong to the container, and nothing else
    crosses the boundary."""
    k, jobs, import_path, episode_timeout, capture, chaos = item
    try:
        results = worker_batch(jobs, import_path, episode_timeout, capture=capture, chaos=chaos)
        return k, results, None
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
        chaos: dict[str, Any] | None = None,
    ) -> None:
        self.remote = remote
        self.import_path = import_path
        self.episode_timeout = episode_timeout
        self.capture = capture
        self.chaos = chaos

    def __call__(
        self, batches: Sequence[Sequence[Job]]
    ) -> Iterator[tuple[int, list[Result] | BaseException]]:
        items: list[_MapItem] = [
            (
                k,
                [tuple(job) for job in jobs],  # type: ignore[misc]
                self.import_path,
                self.episode_timeout,
                self.capture,
                self.chaos,
            )
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
    counted and recorded), ``max_containers=concurrency`` and the named secrets of
    ``options.secrets`` mounted on that function; then ``run_with_mapper`` does the rest. The
    cost guard fires before the app starts. A secret is looked up by name in the caller's Modal
    workspace: no value is read on this machine, and none is attached to the image (ADR-030).
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
    secrets = [modal.Secret.from_name(name) for name in options.secrets]
    remote = app.function(
        image=image,
        gpu=target.image.gpu,
        timeout=_outer_timeout(options),
        retries=0,
        max_containers=options.concurrency,
        serialized=True,
        secrets=secrets,
    )(_container_batch)
    mapper = _ModalMapper(
        remote,
        target.import_path,
        options.episode_timeout,
        _capture_payload(p.spec.capture, p.run_id),
        _chaos_payload(p.spec.chaos),
    )
    with app.run():
        return run_with_mapper(
            p, mapper, store, options=options, image=target.image, on_progress=on_progress
        )
