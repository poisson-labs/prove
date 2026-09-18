"""M3 -- the crashed episode's trace: the oracle for K1-K8.

Written from "Proofload -- Spec M3 Executor (crashed episode trace)" section 4. Session B
builds the two touched files (``executor.py``, ``executor_modal.py``) against this file and
does not edit it.

The conventions of ``tests/test_m3_capture.py`` and ``tests/test_m3_timeout_trace.py`` carry
over unchanged: the whole file skips without ``opentelemetry-sdk``; every test that installs
capture -- directly, through ``_call_in_process`` with a capture call, or through ``run_local``,
``worker_batch`` or ``run_with_mapper`` -- runs it in a child forked from this process
(``isolated``) and reads the store and the results back through a pipe, so the pytest process
never installs and the in-process tests can assert the global provider was left alone;
OpenTelemetry objects are imported inside test bodies, never at module level, because M12's T27
purges ``opentelemetry*`` from ``sys.modules`` earlier in the suite; the episode id is
``f"{config_hash}:{replicate_index}"``; ``worker_batch``'s ``capture`` dict is the four
``CaptureSpec`` fields plus ``run_id``. ``cli.main`` is driven in-process on a store a child
wrote; ``inspect`` installs nothing. ``modal`` is never imported. Nothing sleeps.

Conventions this oracle fixes where the spec is silent, recorded so they are not re-litigated:

- The row that crashes is chosen by config, as the timed-out row was: one categorical axis
  ``role`` over ``a``, ``b``, ``c`` and ``crash`` with one replicate, so every run has exactly
  one crashed row and three ok rows, and one file drives ``run_local``, ``worker_batch`` and
  ``run_with_mapper`` without shared state.
- The crashing rollout opens an ``invoke_agent`` root, closes a ``chat`` child, opens an
  ``execute_tool`` child and raises ``RuntimeError`` inside it; span names carry the seed. A
  second rollout returns a dict instead of an ``Episode`` after the same two closed spans
  (K3). A third raises before opening any span (K2, rule zero). A fourth replaces
  ``Trace.to_dict`` on the class in its own child and then raises, so ``to_meta()`` raises
  after the rollout did: section 3's "the string when it is None *or raised*", section 8's
  "``format_exc()`` first".
- **What the SDK marks, measured against opentelemetry-sdk before this file was written.**
  ``start_as_current_span`` sets ``ERROR`` status on *every* span the exception unwinds
  through, not only the innermost: with the shape above both ``execute_tool`` and the
  ``invoke_agent`` root close with ``error == "RuntimeError: boom <seed>"``, and only ``chat``,
  which closed before the raise, has ``error is None``. K1 as section 4 states it -- the span
  open at the raise marked, every span that closed *before* it unmarked -- holds; section 7's
  "one span with ``error`` set and two without" does not. This file pins what the SDK does in
  one test of its own (``test_k1_the_root_the_exception_unwound_through_is_marked_too``) so
  the fact is asserted rather than rediscovered, and so that, should the spec choose
  otherwise, exactly that test moves. Nothing in ``src/`` sets or clears a status (section 8).
- The fork path is exercised with ``episode_timeout`` set to a deadline no rollout here
  approaches: the crash returns long before it, the outcome crosses the pipe as a normal
  return and nothing is terminated, so ``n_timeout`` is 0 on that path by construction and
  the S16 drain never runs.
- K7's ``--event`` is the stored row's ``error`` text verbatim, a multi-line traceback; the
  block is read the way the M10 and S16 oracles read it. E9's "no ``Traceback`` in the output"
  cannot hold here, because the traceback *is* the error line; ``stderr`` empty and exit 0
  stand in for it.
- K8 pins the S16 oracle by the SHA-256 of its bytes (38 tests at that hash): a Session A that
  amends that file re-pins the hash in the same commit.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import multiprocessing
import os
import re
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import proofload
import proofload.cli as cli
import proofload.executor as executor
import proofload.executor_modal as executor_modal
from proofload.episode import Episode
from proofload.executor import plan, run_local
from proofload.executor_modal import Job, Mapper, ModalOptions, Result, run_with_mapper, worker_batch
from proofload.sampler import SweepSpec
from proofload.store import EpisodeRecord, RunManifest, Store
from proofload.trace import OTEL_SEMCONV_VERSION, Span, Trace

pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")

MODULE = __name__
HERE = Path(__file__).resolve().parent
PACKAGE = Path(proofload.__file__).resolve().parent  # the tree under test; a shadow tree under PYTHONPATH
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
needs_fork = pytest.mark.skipif(not FORK_AVAILABLE, reason="the timeout path needs the fork start method")

RUN_ID_KEY = "proofload.run_id"
EPISODE_KEY = "proofload.episode"
RUN_ID = "r-2026-09-05-crash-oracle"
EPISODE = "cfg-7:1"
SALT = "crash-oracle-salt"
TIMEOUT_ERROR = "timeout"  # S16's error and reason: a crashed row never carries it
CRASH = "crash"
ROLES = ("a", "b", "c", CRASH)
HORIZON = 10.0
EXCEPTION = "RuntimeError"
MESSAGE = "boom"
NON_EPISODE_TEXT = "rollout returned dict, expected Episode"  # the existing text, verbatim
POISON = "the oracle broke Trace.to_dict in this child"
NO_HANG_TIMEOUT_S = 30.0  # the fork path with nothing to terminate: every rollout here returns at once
EPOCH = 1_756_900_000_000_000_000
SNIPPET_MARKER = "# reproduce one episode"
STEP_LINE_RE = re.compile(r"^\s*\d+(?:\t[^\t]*){8}$")  # the M10 oracle's I15 regex, verbatim (nine columns since A8a)
STEP_LINE_SAMPLE = "  0\ttool\tsearch_catalog\t12.5\t-\t-\t-\t-\t-"  # nine columns: P8-21's positive control for every negative use

S16_ORACLE = HERE / "test_m3_timeout_trace.py"
S16_ORACLE_SHA256 = "4781c8d8330bae7076a943e46720c5e5e51915ed0df8bd343fbfebe3ccf82e65"  # 38 tests; re-minted by A8b Session A over the amended file (32 exports, the renamed payload field)

TRACE_KEYS = frozenset({"schema", "source", "source_version", "dropped", "spans", "truncated", "alias_map_version"})  # A8a: the seventh key
PUBLIC_CAPTURE = frozenset({"CaptureSpec", "CaptureStatus", "install", "Recorder", "capture"})
TRACE_EXPORTS = [
    # A7 (spec section 7.1): four mints; A8a (spec section 7.1 group 3): three constants --
    # ALIAS_MAP_VERSION, GATE, OUTCOME_BY; A8b (spec section 7.1 group 5): five constants --
    # CONTENT_KEYS, OBSERVATION_HEAD_BYTES, OBSERVATION_LIMIT_BYTES, OBSERVATION_TAIL_BYTES,
    # TRUNCATED_KEY -- and two functions, finalize and truncate_observations. trace.py's own
    # order: constants, classes, functions, each sorted. 32 names.
    "ALIAS_MAP_VERSION", "ATTRIBUTE_ALIASES", "CONTENT_KEYS", "DROP_REASONS", "GATE", "KINDS", "LOGPROBS_KEY",
    "OBSERVATION_HEAD_BYTES", "OBSERVATION_KEYS", "OBSERVATION_LIMIT_BYTES", "OBSERVATION_TAIL_BYTES",
    "OTEL_KIND_MAP", "OTEL_SEMCONV_VERSION", "OUTCOME_BY", "SCHEMA", "SOURCES", "TRUNCATED_KEY",
    "Collector", "Span", "SpanHandle", "Trace", "TraceValidationError",
    "assemble", "collect", "finalize", "from_litellm", "from_otel", "merge", "record", "split", "step",
    "truncate_observations",
]
OTEL_EXPORTS = ["EPISODE_KEY", "RUN_ID_KEY", "EpisodeStamper", "episode"]
MODAL_EXPORTS = [
    "CostGuard", "ImageSpec", "Job", "Mapper", "ModalBackendError", "ModalNotInstalled",
    "ModalOptions", "ModalTarget", "Result", "estimate_cost", "preflight_modal", "run_modal",
    "run_with_mapper", "worker_batch",
]
# Every public name each touched module defines itself (E12's measure): no new public symbol.
EXECUTOR_PUBLIC = frozenset({
    "ExecutorError", "NotResumable", "Pair", "PairMismatch", "Plan", "RunSummary",
    "derive_seed", "new_run_id", "new_run_salt", "plan", "preflight", "run_local",
    # S23: the power gate. DEFAULT_MAX_MDE is a constant and not a defined object, so it
    # does not reach _defined(); these three do.
    "UnderpoweredDesign", "check_power", "preflight_mde",
})
MODAL_PUBLIC = frozenset({
    "CostGuard", "ImageSpec", "ModalBackendError", "ModalNotInstalled", "ModalOptions",
    "ModalTarget", "estimate_cost", "preflight_modal", "run_modal", "run_with_mapper",
    "worker_batch",
})
EPISODE_FIELDS = ("outcome", "t", "horizon", "confidence", "meta")
SUMMARY_FIELDS = (
    "run_id", "n_ok", "n_errored", "n_timeout", "wall_time", "stopped_by", "complete",
    "n_infra_retried", "n_infra_failed",
)

CRASH_PATH = f"{MODULE}:crashing_rollout"
DICT_PATH = f"{MODULE}:dict_returning_rollout"
SPANLESS_PATH = f"{MODULE}:spanless_raising_rollout"
POISONED_PATH = f"{MODULE}:to_meta_poisoning_rollout"

# Three hand-built spans in the stored shape, all closed, the tool marked: a complete crash trace.
ROOT_ID = "b7ad6b7169203331"
CHAT_ID = "9c1f4e2a7b3d5061"
TOOL_ID = "0af7651916cd43dd"
STAMPS = {RUN_ID_KEY: RUN_ID, EPISODE_KEY: EPISODE}


def _stored_span(
    span_id: str, parent_id: str | None, kind: str, name: str, start_ns: int, end_ns: int, error: str | None = None
) -> dict[str, Any]:
    return {
        "span_id": span_id,
        "parent_id": parent_id,
        "kind": kind,
        "name": name,
        "start_ns": start_ns,
        "end_ns": end_ns,
        "input": None,
        "output": None,
        "tokens": None,
        "confidence": None,
        "error": error,
        "code": None,
        "attrs": dict(STAMPS),
        "operation": None,
        "step_name": None,
        "outcome": None,
        "outcome_by": None,
        "attempt": None,
        "gate": None,
        "truncated": None,
        "bytes_original": None,
    }


SPAN_ROOT = _stored_span(ROOT_ID, None, "agent", "invoke_agent planner", EPOCH, EPOCH + 812_000_000)
SPAN_CHAT = _stored_span(CHAT_ID, ROOT_ID, "llm", "chat planner", EPOCH + 100_000_000, EPOCH + 400_000_000)
SPAN_TOOL = _stored_span(
    TOOL_ID, ROOT_ID, "tool", "execute_tool lookup_order", EPOCH + 500_000_000, EPOCH + 810_000_000,
    error=f"{EXCEPTION}: {MESSAGE}",
)
TRACEBACK_TEXT = (
    "Traceback (most recent call last):\n"
    '  File "agent.py", line 3, in rollout\n'
    f'    raise {EXCEPTION}("{MESSAGE}")\n'
    f"{EXCEPTION}: {MESSAGE}\n"
)


# ---------- module-level rollouts (pickle by reference under fork and spawn) ----------


def _outcome(cfg: Mapping[str, Any], seed: int) -> str:
    return "fell" if (seed + int(float(cfg.get("x", 0.0)) * 10)) % 3 == 0 else "survived"


def _episode(cfg: Mapping[str, Any], seed: int, **meta: Any) -> Episode:
    outcome = _outcome(cfg, seed)
    return Episode(
        outcome=outcome, t=3.0 if outcome == "fell" else HORIZON, horizon=HORIZON, meta=meta
    )


def _tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer("oracle.instrumentation", "0.1.0")


def is_crash(cfg: Any) -> bool:
    return isinstance(cfg, Mapping) and cfg.get("role") == CRASH


def crashing_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The K1/K4/K5/K7 target. Every row opens an ``invoke_agent`` root and closes a ``chat``
    child; the ``crash`` row then opens an ``execute_tool`` child and raises inside it. Every
    span is closed by the time the executor reads the recorder -- the rollout's own ``with``
    blocks end them as the exception unwinds -- and the SDK has marked the ones it unwound
    through. The rollout sets no status itself."""
    tracer = _tracer()
    with tracer.start_as_current_span(f"invoke_agent {seed}") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        with tracer.start_as_current_span(f"chat {seed}") as chat:
            chat.set_attribute("gen_ai.operation.name", "chat")
        if is_crash(cfg):
            with tracer.start_as_current_span(f"execute_tool {seed}") as tool:
                tool.set_attribute("gen_ai.operation.name", "execute_tool")
                raise RuntimeError(f"{MESSAGE} {seed}")
    return _episode(cfg, seed)


def dict_returning_rollout(cfg: Mapping[str, Any], seed: int) -> Any:
    """K3: the same two closed spans, then a dict where an ``Episode`` was expected. The
    capture block completes normally and the recorder is full."""
    tracer = _tracer()
    with tracer.start_as_current_span(f"invoke_agent {seed}") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        with tracer.start_as_current_span(f"chat {seed}") as chat:
            chat.set_attribute("gen_ai.operation.name", "chat")
    return {"outcome": "fell", "t": 1.0, "horizon": HORIZON}


def spanless_raising_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """K2, rule zero: raises before its first span. No OpenTelemetry call at all."""
    raise RuntimeError(f"{MESSAGE} {seed}")


def _raise_at_to_dict(self: Any) -> dict[str, Any]:
    raise RuntimeError(POISON)


def to_meta_poisoning_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """K2, section 3's "or raised": one span, then ``Trace.to_dict`` broken on the class in
    this child, then the raise. ``to_meta()`` now raises on every path to a dict, after the
    rollout's own exception is already in hand (section 8: ``format_exc()`` first)."""
    tracer = _tracer()
    with tracer.start_as_current_span(f"invoke_agent {seed}") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        Trace.to_dict = _raise_at_to_dict  # type: ignore[method-assign]
        raise RuntimeError(f"{MESSAGE} {seed}")


def _resolve(import_path: str) -> Any:
    module_name, attr = import_path.split(":", 1)
    import importlib

    return getattr(importlib.import_module(module_name), attr)


# ---------- helpers: sweep files, jobs, trace dicts ----------


def sweep_toml(
    *,
    capture: dict[str, Any] | None,
    replicates: int = 1,
    axes: dict[str, list[Any]] | None = None,
    target_id: str = "crash-oracle@v0",
    t_unit: str = "steps",
) -> str:
    """A sweep file over ``role``; ``capture`` is the ``[capture]`` table, or absent."""
    axes = {"role": list(ROLES)} if axes is None else axes
    lines = [f'target_id = "{target_id}"', f't_unit = "{t_unit}"', f"replicates = {replicates}", ""]
    for name, values in axes.items():
        kind = "continuous" if all(isinstance(v, float) for v in values) else "categorical"
        lines += [f"[axes.{name}]", f'type = "{kind}"', f"values = {json.dumps(values)}", ""]
    if capture is not None:
        lines.append("[capture]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in capture.items()]
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def episode_id(config_hash: str, replicate_index: int) -> str:
    return f"{config_hash}:{replicate_index}"


def jobs_of(p: Any) -> list[Job]:
    return [
        (dict(pair.config), pair.seed, i, pair.config_hash, pair.replicate_index)
        for i, pair in enumerate(p.pairs)
    ]


def capture_payload(run_id: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"run_id": run_id, "instrument": [], "content": False, "max_observation_bytes": 8192, "max_spans": 1000}  # A8b: the renamed transport field
    payload.update(overrides)
    return payload


def trace_dict(*spans: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """A valid stored-shape trace dict around the given span dicts: the six keys of ADR-028 plus A8a's ``alias_map_version``."""
    d: dict[str, Any] = {
        "schema": "proofload.trace/1",
        "source": "otel",
        "source_version": OTEL_SEMCONV_VERSION,
        "dropped": 0,
        "spans": [dict(s) for s in spans],
        "truncated": None,
        "alias_map_version": None,
    }
    d.update(overrides)
    return d


def crash_trace_dict() -> dict[str, Any]:
    """The stored shape of a crash: three closed spans, the tool marked, ``truncated`` None."""
    return trace_dict(SPAN_ROOT, SPAN_CHAT, SPAN_TOOL)


def manifest(**kw: Any) -> RunManifest:
    base: dict[str, Any] = dict(
        run_id="r1", target_id="policy@abc123", t_unit="steps", run_salt="salt",
        axis_types={"friction": "continuous"}, backend="local", environment={"python": "3.11"},
    )
    base.update(kw)
    return RunManifest(**base)


def ok_record(outcome: str, replicate_index: int, meta: dict[str, Any]) -> EpisodeRecord:
    ep = Episode(outcome=outcome, t=3.0, horizon=HORIZON, meta=meta)
    return EpisodeRecord.from_episode(
        ep, run_id="r1", config={"friction": 0.5}, seed=replicate_index, replicate_index=replicate_index, wall_time=0.1
    )


def errored_record(replicate_index: int, error: str, meta: dict[str, Any] | None = None) -> EpisodeRecord:
    return EpisodeRecord.errored(
        run_id="r1", config={"friction": 0.5}, seed=replicate_index, replicate_index=replicate_index,
        error=error, wall_time=0.1, meta=meta,
    )


def by_name(trace: Trace) -> dict[str, Span]:
    return {span.name: span for span in trace.spans}


def _global_provider_is_sdk() -> bool:
    from opentelemetry import trace

    return type(trace.get_tracer_provider()).__module__.startswith("opentelemetry.sdk")


def _defined(module: Any) -> set[str]:
    """The public names a module defines itself: E12's measure of its surface."""
    return {
        name
        for name, obj in vars(module).items()
        if not name.startswith("_") and getattr(obj, "__module__", None) == module.__name__
    }


# ---------- helpers: isolation (the M3 capture oracle's, verbatim in behaviour) ----------


def _child_entry(conn: Any, fn: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        outcome: tuple[str, Any] = ("ok", fn(*args))
    except BaseException:  # noqa: BLE001 - the child must always report
        outcome = ("error", traceback.format_exc())
    try:
        conn.send(outcome)
    finally:
        conn.close()


def isolated(fn: Callable[..., Any], *args: Any, timeout: float = 120.0) -> Any:
    """Run ``fn(*args)`` in a child process and return its (pickle-native) result.

    Forked when the platform allows, so the child inherits this process's imports and its
    untouched OTel globals; spawned otherwise, which works because ``fn`` and everything it
    reaches live in this real file.
    """
    ctx = multiprocessing.get_context("fork" if FORK_AVAILABLE else "spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child_entry, args=(child_conn, fn, args))
    proc.start()
    child_conn.close()
    deadline = time.perf_counter() + timeout
    outcome: tuple[str, Any] | None = None
    try:
        while outcome is None:
            if parent_conn.poll(0.05):
                outcome = parent_conn.recv()
            elif not proc.is_alive():
                outcome = ("error", f"child exited with code {proc.exitcode} before reporting")
            elif time.perf_counter() > deadline:
                outcome = ("error", f"child produced nothing within {timeout}s")
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
        proc.join(10.0)
    kind, payload = outcome
    if kind != "ok":
        pytest.fail(f"isolated {fn.__name__} failed:\n{payload}")
    return payload


# ---------- the children: everything that installs a provider runs here ----------


def child_call_in_process(target: str, config: dict[str, Any], seed: int, with_capture: bool) -> dict[str, Any]:
    """One ``_call_in_process`` call, with or without a capture call; with one, it installs here."""
    from proofload.capture import CaptureSpec

    call = (
        executor._CaptureCall(spec=CaptureSpec(), run_id=RUN_ID, episode_id=EPISODE)
        if with_capture
        else None
    )
    kind, payload = executor._call_in_process(_resolve(target), dict(config), seed, call)
    return {
        "kind": kind,
        "payload": payload,
        "pid": os.getpid(),
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
    }


def child_run_local(
    store_root: str, toml_path: str, target: str, salt: str, episode_timeout: float | None
) -> dict[str, Any]:
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=salt, import_path=target)
    summary = run_local(p, _resolve(target), store, episode_timeout=episode_timeout)
    return {
        "run_id": p.run_id,
        "summary": dataclasses.asdict(summary),
        "pid": os.getpid(),
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
    }


def child_worker_batch(
    jobs: list[Job], import_path: str, episode_timeout: float | None, capture: dict[str, Any] | None
) -> dict[str, Any]:
    results = worker_batch(jobs, import_path, episode_timeout, capture=capture)
    return {
        "results": results,
        "pid": os.getpid(),
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
    }


def child_run_with_mapper(
    store_root: str, toml_path: str, target: str, salt: str, episode_timeout: float | None
) -> dict[str, Any]:
    """``run_with_mapper`` driven by a mapper that runs ``worker_batch`` with capture, all in
    this one child: with a timeout the fork branch installs in the episode children, never here."""
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, backend="modal", run_salt=salt, import_path=target)
    payload = capture_payload(p.run_id)
    seen: list[Result] = []

    def mapper(batches: Sequence[Sequence[Job]]) -> Iterator[tuple[int, list[Result] | BaseException]]:
        for k, jobs in enumerate(batches):
            results = worker_batch([tuple(job) for job in jobs], target, episode_timeout, capture=payload)
            seen.extend(results)
            yield k, results

    summary = run_with_mapper(p, mapper, store, options=ModalOptions(episode_timeout=episode_timeout))
    return {
        "run_id": p.run_id,
        "summary": dataclasses.asdict(summary),
        "results": seen,
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
    }


# ---------- fixtures: the K1 payload and the two runs K4/K7 read ----------


@pytest.fixture(scope="module")
def crash_outcome() -> dict[str, Any]:
    """One ``_call_in_process`` call with a capture call on the crashing rollout, in a child."""
    return isolated(child_call_in_process, CRASH_PATH, {"role": CRASH}, 7, True)


@dataclasses.dataclass(frozen=True)
class CrashRun:
    """One ``run_local`` written by a child: one crashed row (``role = "crash"``), three ok rows."""

    root: Path
    run_id: str
    report: dict[str, Any]

    @property
    def store(self) -> Store:
        return Store(self.root)

    @property
    def df(self) -> pd.DataFrame:
        return self.store.read(self.run_id)

    @property
    def crashed(self) -> Any:
        df = self.df
        rows = df[[is_crash(cfg) for cfg in df["config"]]]
        assert len(rows) == 1, rows
        return rows.iloc[0]

    @property
    def others(self) -> pd.DataFrame:
        df = self.df
        return df[[not is_crash(cfg) for cfg in df["config"]]].reset_index(drop=True)


def _crash_run(tmp_path_factory: pytest.TempPathFactory, *, episode_timeout: float | None) -> CrashRun:
    if episode_timeout is not None and not FORK_AVAILABLE:
        pytest.skip("the timeout path needs the fork start method")
    root = tmp_path_factory.mktemp("crash-run")
    toml = write(root / "sweep.toml", sweep_toml(capture={"instrument": []}))
    r = isolated(child_run_local, str(root / "store"), str(toml), CRASH_PATH, SALT, episode_timeout)
    return CrashRun(root=root / "store", run_id=r["run_id"], report=r)


@pytest.fixture(scope="module")
def crash_run(tmp_path_factory: pytest.TempPathFactory) -> CrashRun:
    """No ``episode_timeout``: the in-process path, and the store K7 reads."""
    return _crash_run(tmp_path_factory, episode_timeout=None)


@pytest.fixture(scope="module")
def forked_crash_run(tmp_path_factory: pytest.TempPathFactory) -> CrashRun:
    """``episode_timeout`` set: every episode in a forked child, the outcome over the pipe."""
    return _crash_run(tmp_path_factory, episode_timeout=NO_HANG_TIMEOUT_S)


# ---------- assertion helpers ----------


def assert_traceback_of(text: Any, seed: int) -> None:
    """The traceback text the string form carries today: ``format_exc()`` of the rollout's raise."""
    assert isinstance(text, str), text
    assert text.startswith("Traceback (most recent call last):"), text
    assert text.rstrip("\n").splitlines()[-1] == f"{EXCEPTION}: {MESSAGE} {seed}", text
    assert text != TIMEOUT_ERROR


def assert_crash_trace_of(trace: Trace, seed: int, run_id: str, episode: str) -> None:
    """The crashed row's trace: an ``invoke_agent`` root, a ``chat`` child that closed before
    the raise, an ``execute_tool`` child that was open at it -- all closed, all stamped, all
    named for this seed, the failing span's ``error`` naming the exception, nothing cut."""
    assert trace.truncated is None, trace.truncated
    assert trace.source == "otel" and trace.source_version == OTEL_SEMCONV_VERSION and trace.dropped == 0
    spans = by_name(trace)
    assert set(spans) == {f"invoke_agent {seed}", f"chat {seed}", f"execute_tool {seed}"}, sorted(spans)
    root, chat, tool = spans[f"invoke_agent {seed}"], spans[f"chat {seed}"], spans[f"execute_tool {seed}"]
    for span in trace.spans:
        assert span.end_ns is not None, (span.name, "a span was left open: nothing was terminated")
        assert span.duration_ms is not None and span.duration_ms >= 0.0, span
        assert span.attrs[RUN_ID_KEY] == run_id and span.attrs[EPISODE_KEY] == episode, (span.name, span.attrs)
    # The span open at the raise carries the SDK's ERROR status, "<Type>: <message>".
    assert isinstance(tool.error, str) and tool.error, tool
    assert EXCEPTION in tool.error and f"{MESSAGE} {seed}" in tool.error, tool.error
    # The span that closed before the raise: nothing marked it.
    assert chat.error is None, chat
    assert root.parent_id is None and chat.parent_id == root.span_id and tool.parent_id == root.span_id
    assert (root.kind, chat.kind, tool.kind) == ("agent", "llm", "tool")
    assert {s.name.split(" ")[1] for s in trace.spans} == {str(seed)}, "a span from another row leaked in"
    assert [s.name for s in trace.ordered()] == [f"invoke_agent {seed}", f"chat {seed}", f"execute_tool {seed}"]
    assert [s.name for s in trace.roots()] == [f"invoke_agent {seed}"]


def assert_dict_form(payload: Any) -> tuple[str, dict[str, Any]]:
    """Exactly the two keys; ``meta`` exactly ``{"trace": t}`` with ``t`` a six-key trace dict."""
    assert isinstance(payload, dict), payload
    assert set(payload) == {"error", "meta"}, sorted(payload)
    assert isinstance(payload["error"], str)
    assert isinstance(payload["meta"], dict) and set(payload["meta"]) == {"trace"}, payload["meta"]
    t = payload["meta"]["trace"]
    assert isinstance(t, dict) and set(t) == TRACE_KEYS, t
    return payload["error"], t


def assert_intact_ok_rows(others: pd.DataFrame, run_id: str) -> None:
    """What I8/I9 require of every other row, plus the complete stamped trace C5 gives it."""
    assert len(others) == 3 and others["error"].isna().all()
    for row in others.itertuples(index=False):
        assert row.outcome == _outcome(row.config, row.seed), row
        trace = Trace.from_dict(row.meta["trace"])
        assert trace.truncated is None and trace.dropped == 0
        assert sorted(s.name for s in trace.spans) == sorted([f"invoke_agent {row.seed}", f"chat {row.seed}"])
        for span in trace.spans:
            assert span.end_ns is not None and span.error is None, span
            assert span.attrs[RUN_ID_KEY] == run_id
            assert span.attrs[EPISODE_KEY] == episode_id(row.config_hash, row.replicate_index)


# ---------- K1: _call_in_process with a capture call, the rollout raises after spans ----------


def test_k1_call_in_process_with_capture_returns_the_two_key_dict_around_the_traceback_and_the_complete_trace(
    crash_outcome: dict[str, Any],
) -> None:
    assert crash_outcome["kind"] == "error", crash_outcome
    error, t = assert_dict_form(crash_outcome["payload"])
    assert_traceback_of(error, 7)
    assert "crashing_rollout" in error, error  # the rollout's own frame, not another's
    assert_crash_trace_of(Trace.from_dict(t), 7, RUN_ID, EPISODE)
    assert crash_outcome["sdk_provider_in_this_process"] is True, "_call_in_process with a capture call did not install"
    assert not _global_provider_is_sdk(), "the pytest process installed a provider"


def test_k1_the_root_the_exception_unwound_through_is_marked_too(crash_outcome: dict[str, Any]) -> None:
    """Measured, not specified: ``start_as_current_span`` marks every span the exception unwinds
    through, so the root closes with the same ``ERROR`` status as the failing child and section
    7's "one span with ``error`` set" is two. Pinned on its own so the fact is asserted once and
    so that, should the spec choose otherwise, exactly this test moves."""
    _, t = assert_dict_form(crash_outcome["payload"])
    spans = by_name(Trace.from_dict(t))
    root, chat, tool = spans["invoke_agent 7"], spans["chat 7"], spans["execute_tool 7"]
    assert tool.error == f"{EXCEPTION}: {MESSAGE} 7", tool.error
    assert root.error == tool.error, (root.error, tool.error)
    assert chat.error is None, chat.error


# ---------- K2: the string form, where it stays ----------


def test_k2_without_a_capture_call_the_payload_is_the_string_it_always_was() -> None:
    kind, text = executor._call_in_process(crashing_rollout, {"role": CRASH}, 7)
    assert kind == "error"
    assert_traceback_of(text, 7)
    kind, text = executor._call_in_process(dict_returning_rollout, {"role": "a"}, 7)
    assert (kind, text) == ("error", NON_EPISODE_TEXT)
    kind, text = executor._call_in_process(spanless_raising_rollout, {"role": "a"}, 7)
    assert kind == "error"
    assert_traceback_of(text, 7)
    assert not _global_provider_is_sdk(), "a call without a capture call installed a provider"


def test_k2_with_a_capture_call_a_rollout_that_emitted_no_span_yields_the_string_never_a_dict_with_an_empty_meta() -> None:
    r = isolated(child_call_in_process, SPANLESS_PATH, {"role": CRASH}, 7, True)
    assert r["kind"] == "error", r
    assert isinstance(r["payload"], str), r["payload"]  # rule zero: nothing captured, no trace claimed
    assert_traceback_of(r["payload"], 7)
    assert "spanless_raising_rollout" in r["payload"], r["payload"]
    assert r["sdk_provider_in_this_process"] is True, "capture was not installed: rule zero was not exercised"
    assert not _global_provider_is_sdk(), "the pytest process installed a provider"


def test_k2_a_recorder_that_raises_at_to_meta_yields_the_rollouts_own_traceback_as_the_string() -> None:
    """Section 3: the string when ``to_meta()`` is None *or raised*, guarded as ``_classify``
    guards it; section 8: ``format_exc()`` first, so nothing that raises after it replaces the
    traceback the user needs."""
    r = isolated(child_call_in_process, POISONED_PATH, {"role": CRASH}, 7, True)
    assert r["kind"] == "error", r
    text = r["payload"]
    assert isinstance(text, str), text
    assert_traceback_of(text, 7)
    assert "to_meta_poisoning_rollout" in text, text
    assert POISON not in text, text
    assert r["sdk_provider_in_this_process"] is True
    assert not _global_provider_is_sdk(), "the pytest process installed a provider"


# ---------- K3: a non-Episode return after spans ----------


def test_k3_a_non_episode_return_after_spans_yields_the_dict_form_around_the_existing_text() -> None:
    r = isolated(child_call_in_process, DICT_PATH, {"role": "a"}, 7, True)
    assert r["kind"] == "error", r
    error, t = assert_dict_form(r["payload"])
    assert error == NON_EPISODE_TEXT, error
    trace = Trace.from_dict(t)
    assert trace.truncated is None and trace.dropped == 0 and trace.source == "otel"
    spans = by_name(trace)
    assert set(spans) == {"invoke_agent 7", "chat 7"}, sorted(spans)
    for span in trace.spans:
        assert span.end_ns is not None and span.error is None, span  # nothing raised: nothing marked
        assert span.attrs[RUN_ID_KEY] == RUN_ID and span.attrs[EPISODE_KEY] == EPISODE, (span.name, span.attrs)
    assert spans["chat 7"].parent_id == spans["invoke_agent 7"].span_id
    assert (spans["invoke_agent 7"].kind, spans["chat 7"].kind) == ("agent", "llm")
    assert not _global_provider_is_sdk(), "the pytest process installed a provider"


# ---------- K4: run_local, both paths ----------


@pytest.mark.parametrize("fixture", ["crash_run", "forked_crash_run"], ids=["in-process", "forked"])
def test_k4_run_local_stores_the_crashed_row_with_its_trace_counted_as_errored_and_not_as_timeout(
    request: pytest.FixtureRequest, fixture: str
) -> None:
    run: CrashRun = request.getfixturevalue(fixture)
    summary = run.report["summary"]
    assert (summary["n_ok"], summary["n_errored"], summary["n_timeout"], summary["complete"]) == (3, 1, 0, True), summary
    record = run.store.manifest(run.run_id).environment["capture"]
    assert record["requested"] is True and record["active"] is True, record
    crashed = run.crashed
    seed = int(crashed["seed"])
    assert crashed["outcome"] is None and pd.isna(crashed["t"])
    assert crashed["error"] != TIMEOUT_ERROR
    assert_traceback_of(crashed["error"], seed)
    assert set(crashed["meta"]) == {"trace"}, crashed["meta"]
    assert_crash_trace_of(
        Trace.from_dict(crashed["meta"]["trace"]), seed, run.run_id,
        episode_id(crashed["config_hash"], int(crashed["replicate_index"])),
    )
    assert_intact_ok_rows(run.others, run.run_id)


@needs_fork
def test_k4_on_the_fork_path_the_parent_never_installs_and_the_row_is_the_same(
    forked_crash_run: CrashRun, crash_run: CrashRun
) -> None:
    assert forked_crash_run.report["sdk_provider_in_this_process"] is False, "run_local installed in the forking parent"
    assert not _global_provider_is_sdk(), "the pytest process installed a provider"
    a, b = crash_run.crashed, forked_crash_run.crashed
    assert a["seed"] == b["seed"] and a["config"] == b["config"]  # the same salt, the same pair
    assert a["outcome"] is None and b["outcome"] is None
    assert a["error"].rstrip("\n").splitlines()[-1] == b["error"].rstrip("\n").splitlines()[-1]
    assert set(a["meta"]) == {"trace"} and set(b["meta"]) == {"trace"}, (a["meta"], b["meta"])
    ta, tb = Trace.from_dict(a["meta"]["trace"]), Trace.from_dict(b["meta"]["trace"])
    shape = [(s.name, s.kind, s.parent_id is None, s.error, s.end_ns is not None) for s in ta.ordered()]
    assert shape == [(s.name, s.kind, s.parent_id is None, s.error, s.end_ns is not None) for s in tb.ordered()]
    assert ta.truncated is None and tb.truncated is None


# ---------- K5: worker_batch and run_with_mapper ----------


@pytest.mark.parametrize(
    "episode_timeout", [None, pytest.param(NO_HANG_TIMEOUT_S, marks=needs_fork)], ids=["in-process", "forked"]
)
def test_k5_worker_batch_returns_the_two_key_dict_for_the_crashing_job_with_capture(
    tmp_path: Path, episode_timeout: float | None
) -> None:
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), Store(tmp_path / "store"), run_salt=SALT)
    jobs = jobs_of(p)
    r = isolated(child_worker_batch, jobs, CRASH_PATH, episode_timeout, capture_payload(RUN_ID))
    results = r["results"]
    assert len(results) == len(jobs) == 4
    crashed = 0
    for job, result in zip(jobs, results, strict=True):
        config, seed, i, config_hash, replicate_index = job
        assert isinstance(result, dict), result
        if is_crash(config):
            crashed += 1
            error, t = assert_dict_form(result)
            assert_traceback_of(error, seed)
            assert_crash_trace_of(Trace.from_dict(t), seed, RUN_ID, episode_id(config_hash, replicate_index))
        else:
            assert result["outcome"] == _outcome(config, seed) and result["backend_meta"]["i"] == i
            assert result["backend_meta"]["capture"]["active"] is True, result["backend_meta"]
            assert Trace.from_dict(result["meta"]["trace"]).truncated is None
    assert crashed == 1
    # In-process, worker_batch installed in its own process; forked, the episode children did
    # and the process that called worker_batch did not (C1).
    assert r["sdk_provider_in_this_process"] is (episode_timeout is None), r["sdk_provider_in_this_process"]
    assert not _global_provider_is_sdk(), "the pytest process installed a provider"


def test_k5_worker_batch_returns_the_string_for_the_crashing_job_without_capture(tmp_path: Path) -> None:
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), Store(tmp_path / "store"), run_salt=SALT)
    jobs = jobs_of(p)
    results = worker_batch(jobs, CRASH_PATH, None)  # I2's call: three positionals, no capture
    assert len(results) == 4
    for job, result in zip(jobs, results, strict=True):
        config, seed, i, _, _ = job
        if is_crash(config):
            assert isinstance(result, str), result
            assert_traceback_of(result, seed)
            assert EXCEPTION in result and MESSAGE in result and "Traceback" in result  # I2's three words
        else:
            assert isinstance(result, dict) and result["outcome"] == _outcome(config, seed), result
            assert "trace" not in result["meta"] and result["backend_meta"]["i"] == i
    assert sum(isinstance(result, str) for result in results) == 1
    # I2's other string, the wrong-type return, is a string on every job too.
    assert worker_batch(jobs, DICT_PATH, None) == [NON_EPISODE_TEXT] * 4
    assert not _global_provider_is_sdk(), "a worker_batch call without capture installed a provider"


@needs_fork
def test_k5_run_with_mapper_stores_the_dict_form_as_an_errored_row_with_its_trace(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": []}))
    r = isolated(child_run_with_mapper, str(tmp_path / "store"), str(toml), CRASH_PATH, SALT, NO_HANG_TIMEOUT_S)
    summary = r["summary"]
    assert (summary["n_ok"], summary["n_errored"], summary["n_timeout"], summary["complete"]) == (3, 1, 0, True), summary
    assert (summary["n_infra_retried"], summary["n_infra_failed"]) == (0, 0), summary
    dict_forms = [x for x in r["results"] if isinstance(x, dict) and "error" in x]
    assert len(dict_forms) == 1, r["results"]
    error, t = assert_dict_form(dict_forms[0])
    run = CrashRun(root=tmp_path / "store", run_id=r["run_id"], report=r)
    crashed = run.crashed
    seed = int(crashed["seed"])
    assert crashed["outcome"] is None and pd.isna(crashed["t"])
    assert crashed["error"] == error, "the row's error is not the result's"
    assert_traceback_of(crashed["error"], seed)
    assert crashed["meta"] == {"trace": t}, "the row's meta is not the result's"
    assert_crash_trace_of(
        Trace.from_dict(crashed["meta"]["trace"]), seed, r["run_id"],
        episode_id(crashed["config_hash"], int(crashed["replicate_index"])),
    )
    assert_intact_ok_rows(run.others, r["run_id"])
    assert r["sdk_provider_in_this_process"] is False, "the mapper's process installed a provider"
    assert not _global_provider_is_sdk(), "the pytest process installed a provider"


# ---------- K6: retention never strips the crashed row ----------


@pytest.mark.parametrize("retain", [("violated",), ()], ids=["one-outcome", "nothing"])
def test_k6_retention_keeps_the_crashed_rows_trace_and_still_strips_an_unretained_ok_row(
    tmp_path: Path, retain: tuple[str, ...]
) -> None:
    store = Store(tmp_path)
    store.create_run(manifest(retain_traces_for=retain))
    trace = crash_trace_dict()
    records = [
        ok_record("completed", 0, {"trace": ["a"], "k": 1}),
        errored_record(2, TRACEBACK_TEXT, {"trace": trace, "k": 3}),
        errored_record(3, NON_EPISODE_TEXT, {"trace": trace}),
        errored_record(4, TRACEBACK_TEXT),  # the string form's row: no meta at all
    ]
    if retain:
        records.append(ok_record("violated", 1, {"trace": ["b"], "k": 2}))
    store.append("r1", records)
    df = store.read("r1").set_index("replicate_index")
    assert df.loc[0, "meta"] == {"k": 1}  # I8's existing half: an unretained ok row loses its trace
    assert df.loc[2, "meta"] == {"trace": trace, "k": 3}
    assert df.loc[3, "meta"] == {"trace": trace}
    assert df.loc[4, "meta"] == {}
    assert df.loc[2, "error"] == TRACEBACK_TEXT and df.loc[3, "error"] == NON_EPISODE_TEXT
    assert df.loc[2, "outcome"] is None and pd.isna(df.loc[2, "t"])
    kept = Trace.from_dict(df.loc[2, "meta"]["trace"])
    assert kept.truncated is None and kept.dropped == 0
    assert by_name(kept)["execute_tool lookup_order"].error == f"{EXCEPTION}: {MESSAGE}"
    assert all(s.end_ns is not None for s in kept.spans)
    if retain:
        assert df.loc[1, "meta"] == {"trace": ["b"], "k": 2}


# ---------- K7: inspect ----------


@dataclasses.dataclass(frozen=True)
class CliResult:
    code: int
    out: str
    err: str

    @property
    def text(self) -> str:
        return self.out + self.err


def inspect_run(root: Path, run_id: str, event: str, *extra: str) -> CliResult:
    out, err = StringIO(), StringIO()
    code = cli.main(
        ["--store", str(root), "inspect", run_id, "--event", event, *extra],
        stdout=out, stderr=err, stdin=StringIO(),
    )
    return CliResult(code, out.getvalue(), err.getvalue())


def inspect_blocks(out: str, hashes: set[str]) -> tuple[list[list[str]], list[str]]:
    """Split inspect output into per-row blocks (each starting at a line naming a config_hash)
    and the trailing reproduction snippet. The M10 oracle's helper."""
    body, marker, tail = out.partition(SNIPPET_MARKER)
    assert marker, f"no {SNIPPET_MARKER!r} snippet in inspect output:\n{out}"
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in body.splitlines():
        if any(h in line for h in hashes):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return blocks, (marker + tail).splitlines()


def assert_block_is_row(block: list[str], row: Any) -> None:
    text = "\n".join(block)
    assert row.config_hash in block[0], block[0]
    assert re.search(rf"\b{row.seed}\b", text), f"seed {row.seed} missing from block:\n{text}"
    found = False
    for line in block:
        m = re.search(r"\{.*\}", line)
        if m is None:
            continue
        try:
            found = found or json.loads(m.group(0)) == row.config
        except json.JSONDecodeError:
            continue
    assert found, f"no JSON line equal to {row.config!r} in block:\n{text}"


def test_k7_inspect_selects_the_crashed_row_by_its_exact_error_text_and_prints_its_complete_trace(
    crash_run: CrashRun,
) -> None:
    crashed = crash_run.crashed
    seed = int(crashed["seed"])
    error_text = str(crashed["error"])
    assert "\n" in error_text  # a traceback: the exact text is the only selector until --errored lands (section 5)
    r = inspect_run(crash_run.root, crash_run.run_id, error_text)
    assert r.code == 0, r.text
    assert not r.err.strip(), r.err
    blocks, snippet = inspect_blocks(r.out, set(crash_run.df["config_hash"]))
    assert len(blocks) == 1, r.out
    block = blocks[0]
    assert_block_is_row(block, crashed)
    text = "\n".join(block)
    # Section 3's errored-row lines, where an ok row prints t: <float>.
    assert "outcome: -" in block and "t: -" in block, text
    assert [line for line in block if line.startswith("t: ")] == ["t: -"], text
    error_lines = [line for line in block if line.startswith("error: ")]
    assert error_lines == ["error: Traceback (most recent call last):"], error_lines
    assert f"error: {error_text}" in text, text  # printed as it is stored, multi-line (section 5)
    # No truncated line: nothing was cut.
    assert "trace: truncated" not in r.out, r.out
    assert not [line for line in block if line.startswith("trace:")], text
    # One span line per span, every one closed: a float in every duration column.
    step_at = [i for i, line in enumerate(block) if STEP_LINE_RE.match(line)]
    assert len(step_at) == 3, f"{len(step_at)} span lines, expected 3:\n{text}"
    assert set(crashed["meta"]) == {"trace"}, crashed["meta"]
    trace = Trace.from_dict(crashed["meta"]["trace"])
    assert len(trace.spans) == 3, trace
    assert all(i > block.index(error_lines[0]) for i in step_at), text
    assert STEP_LINE_RE.match(STEP_LINE_SAMPLE), "STEP_LINE_RE matches nothing; a negative use below would be vacuous"
    assert not [line for line in error_text.splitlines() if STEP_LINE_RE.match(line)], error_text
    columns = [block[i].split("\t") for i in step_at]
    assert [cols[0].strip() for cols in columns] == ["0", "1", "2"]
    assert [cols[2] for cols in columns] == [s.name for s in trace.ordered()]
    assert all(float(cols[3]) >= 0.0 for cols in columns), columns
    by_col = {cols[2]: cols for cols in columns}
    assert by_col[f"invoke_agent {seed}"][1] == "agent"
    assert by_col[f"chat {seed}"][1] == "llm" and by_col[f"chat {seed}"][4] == "-"
    assert by_col[f"execute_tool {seed}"][1] == "tool" and EXCEPTION in by_col[f"execute_tool {seed}"][4], columns
    # The snippet reproduces the crashed episode, the only row printed.
    assert f"seed={seed}" in "\n".join(snippet), snippet
    assert not _global_provider_is_sdk(), "inspect installed a provider"


# ---------- K8: the timed-out path and every public surface are untouched ----------


def test_k8_the_s16_oracle_is_byte_identical() -> None:
    assert S16_ORACLE.is_file(), S16_ORACLE
    assert hashlib.sha256(S16_ORACLE.read_bytes()).hexdigest() == S16_ORACLE_SHA256, "the S16 oracle moved"


def test_k8_the_transport_aliases_and_signatures_are_untouched() -> None:
    assert Job == tuple[dict[str, Any], int, int, str, int]
    assert Result == dict[str, Any] | str
    assert executor._Outcome == tuple[str, Any]
    assert Mapper == Callable[[Sequence[Sequence[Job]]], Iterator[tuple[int, list[Result] | BaseException]]]
    assert executor._TIMEOUT_ERROR == TIMEOUT_ERROR
    assert tuple(f.name for f in dataclasses.fields(Episode)) == EPISODE_FIELDS
    assert set(Episode(outcome="fell", t=1.0, horizon=HORIZON).to_dict()) == set(EPISODE_FIELDS)
    assert tuple(f.name for f in dataclasses.fields(executor.RunSummary)) == SUMMARY_FIELDS
    params = list(inspect.signature(worker_batch).parameters.values())
    # M11a: ``chaos`` rides beside ``capture``, keyword-only, default None (Spec M11 section 0.1)
    assert [p.name for p in params] == ["jobs", "import_path", "episode_timeout", "capture", "chaos"]
    assert params[3].kind is params[3].KEYWORD_ONLY and params[3].default is None
    assert params[4].kind is params[4].KEYWORD_ONLY and params[4].default is None
    call = inspect.signature(executor._call_in_process).parameters
    assert list(call) == ["rollout", "config", "seed", "capture_call", "chaos_call"]
    assert call["capture_call"].default is None and call["chaos_call"].default is None
    meta = inspect.signature(EpisodeRecord.errored).parameters["meta"]
    assert meta.kind is meta.KEYWORD_ONLY and meta.default is None


def test_k8_no_new_public_symbol_in_the_touched_modules_or_their_neighbours() -> None:
    import proofload.capture as capture_module
    import proofload.otel as otel_module
    import proofload.trace as trace_module

    assert _defined(executor) == EXECUTOR_PUBLIC, sorted(_defined(executor) ^ EXECUTOR_PUBLIC)
    assert _defined(executor_modal) == MODAL_PUBLIC, sorted(_defined(executor_modal) ^ MODAL_PUBLIC)
    assert list(executor_modal.__all__) == MODAL_EXPORTS, executor_modal.__all__
    assert set(capture_module.__all__) == PUBLIC_CAPTURE and _defined(capture_module) == PUBLIC_CAPTURE
    assert list(trace_module.__all__) == TRACE_EXPORTS, trace_module.__all__
    assert list(otel_module.__all__) == OTEL_EXPORTS, otel_module.__all__
    assert (PACKAGE / "executor.py").is_file() and (PACKAGE / "executor_modal.py").is_file(), PACKAGE
