"""M3 -- the timed-out episode's trace: the frozen tests for E1-E12.

Written after the M12 frozen tests were amended, in their own commit, for the trace-level ``truncated``
key. The implementation changes the six touched files
(``trace.py``, ``capture.py``, ``executor.py``, ``executor_modal.py``, ``store.py``, ``cli.py``)
against this file and does not edit it.

The conventions of ``tests/test_m3_capture.py`` carry over unchanged: the whole file skips
without ``opentelemetry-sdk``; every test that installs capture -- through ``run_local`` or
``worker_batch`` -- runs it in a child forked from this process (``isolated``) and reads the store and the results back through a pipe, so the pytest
process never installs and the in-process tests can assert the global provider was left alone
(E10); OpenTelemetry objects are imported inside test bodies, never at module level; the episode id
is ``f"{config_hash}:{replicate_index}"``; ``worker_batch``'s ``capture`` dict is the four
``CaptureSpec`` fields plus ``run_id``. ``cli.main`` is driven in-process on a store a child
wrote, as the M10 frozen tests drive it; ``inspect`` installs nothing.

Conventions these frozen tests fix where the design is silent, recorded so they are not re-litigated:

- The row that hangs is chosen by config, not by a module-level seed set: the sweep has one
  categorical axis ``role`` over ``a``, ``b``, ``c`` and ``hang`` with one replicate, so every
  run has exactly one timed-out row and three ok rows, and the same file drives ``run_local``,
  ``worker_batch`` and ``run_with_mapper`` without shared state.
- The timed-out rollout opens an ``invoke_agent`` root, closes a ``chat`` child, opens an
  ``execute_tool`` child and sleeps: one closed span and two open ones, one per nesting level,
  which is the shape an agent hung inside a tool call leaves. Span names carry the seed, so a span from another
  row is visible by name.
- The child's ``SIGTERM`` disposition (E5) is read by the *sibling* rollouts of the same run and
  returned in their ``Episode.meta["sigterm"]``: the timed-out child cannot report, and every
  episode child of a run is started by the same ``_child_main`` with the same capture call. The
  contrast is asserted both ways: ``default`` without a ``[capture]`` table, a handler with one.
- E1's ``str | None`` is asserted at the constructor and at ``from_dict``, the M12 frozen tests'
  convention for every typed field of the schema.
- E9 pins the errored row's three lines (``outcome: -``, ``t: -``,
  ``error: timeout``) and pins nothing about an ``outcome:`` line on an ok row, where the
  design can be read two ways; the "no rows" message is pinned to the words
  ``no rows`` and the event name, not to its wording.
- The wall-clock bounds are the only timing assertions, and every one is an upper bound.

E13 (added after the implementation) pins one of its deviations back to the intended
behaviour: a Modal dict-form result whose ``meta`` is absent or not a Mapping raises
``ModalBackendError`` naming the job, as an invalid episode does, instead of being stored
without it.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import logging
import multiprocessing
import os
import re
import signal
import time
import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import poisson_prove.cli as cli
from poisson_prove.episode import Episode
from poisson_prove.executor import plan, run_local
from poisson_prove.executor_modal import (
    Job, ModalBackendError, ModalOptions, Result, run_with_mapper, worker_batch,
)
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import OTEL_SEMCONV_VERSION, Span, Trace, TraceValidationError, merge

pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")

MODULE = __name__
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
needs_fork = pytest.mark.skipif(not FORK_AVAILABLE, reason="the timeout path needs the fork start method")

RUN_ID_KEY = "poisson_prove.run_id"
EPISODE_KEY = "poisson_prove.episode"
RUN_ID = "r-2026-09-05-timeout-oracle"
EPISODE = "cfg-7:1"
SALT = "timeout-oracle-salt"
REASON = "timeout"  # the executor's error and the reason the drain mints: one vocabulary
HANG = "hang"
ROLES = ("a", "b", "c", HANG)
HORIZON = 10.0
TIMEOUT_S = 0.5  # the deadline, as the frozen I9 and I3 tests set it
HANG_S = 12.0  # longer than timeout + both graces: only the handler's exit, SIGTERM's default, or kill() ends a hung child
DRAIN_GRACE_S = 2.0  # the executor's _DRAIN_GRACE_S
JOIN_GRACE_S = 5.0  # the executor's existing _JOIN_GRACE_S
PROCESS_SLACK_S = 1.0  # poll steps, kill and join on top of the deadline plus both graces
PID_KEY = "oracle.pid"
EPOCH = 1_756_900_000_000_000_000
TRUNCATED_LINE = f"trace: truncated ({REASON})"
SNIPPET_MARKER = "# reproduce one episode"
STEP_LINE_RE = re.compile(r"^\s*\d+(?:\t[^\t]*){8}$")  # the M10 frozen tests' I15 regex, verbatim (nine columns since A8a)
STEP_LINE_SAMPLE = "  0\ttool\tsearch_catalog\t12.5\t-\t-\t-\t-\t-"  # nine columns: P8-21's positive control for every negative use

#: CD (D1): the cap a [capture] table must now declare; the value the dataclass used to supply.
DECLARED_LIMIT = 8192
TRACE_KEYS = frozenset({"schema", "source", "source_version", "dropped", "spans", "truncated", "alias_map_version"})  # A8a: the seventh key
TRACE_FIELDS = ("spans", "source", "source_version", "dropped", "truncated", "alias_map_version")  # A8a: the seventh field

HANG_PATH = f"{MODULE}:hanging_rollout"
PLAIN_PATH = f"{MODULE}:plain_rollout"

# Two hand-built spans in the stored shape: a closed root and a child left open, both stamped.
ROOT_ID = "b7ad6b7169203331"
OPEN_ID = "0af7651916cd43dd"
STAMPS = {RUN_ID_KEY: RUN_ID, EPISODE_KEY: EPISODE}
SPAN_CLOSED: dict[str, Any] = {
    "span_id": ROOT_ID,
    "parent_id": None,
    "kind": "agent",
    "name": "invoke_agent planner",
    "start_ns": EPOCH,
    "end_ns": EPOCH + 812_000_000,
    "input": None,
    "output": None,
    "tokens": None,
    "confidence": None,
    "error": None,
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
SPAN_OPEN: dict[str, Any] = {
    "span_id": OPEN_ID,
    "parent_id": ROOT_ID,
    "kind": "tool",
    "name": "execute_tool lookup_order",
    "start_ns": EPOCH + 500_000_000,
    "end_ns": None,
    "input": None,
    "output": None,
    "tokens": None,
    "confidence": None,
    "error": None,
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


def _sigterm_disposition() -> str:
    """The calling process's ``SIGTERM`` disposition, as a word a pipe can carry."""
    handler = signal.getsignal(signal.SIGTERM)
    if handler is signal.SIG_DFL:
        return "default"
    if handler is signal.SIG_IGN:
        return "ignore"
    if handler is None:
        return "none"
    return "handler"


def is_hang(cfg: Any) -> bool:
    return isinstance(cfg, Mapping) and cfg.get("role") == HANG


def hanging_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The E4/E7/E9 target. Every row opens an ``invoke_agent`` root and closes a ``chat`` child;
    the ``hang`` row then opens an ``execute_tool`` child and sleeps past every deadline, so at
    the kill one span is closed and two are open, one per nesting level. The ok rows report the
    child's ``SIGTERM`` disposition in their meta (E5)."""
    tracer = _tracer()
    with tracer.start_as_current_span(f"invoke_agent {seed}") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        with tracer.start_as_current_span(f"chat {seed}") as chat:
            chat.set_attribute("gen_ai.operation.name", "chat")
        if is_hang(cfg):
            with tracer.start_as_current_span(f"execute_tool {seed}") as tool:
                tool.set_attribute("gen_ai.operation.name", "execute_tool")
                tool.set_attribute(PID_KEY, os.getpid())
                time.sleep(HANG_S)
    return _episode(cfg, seed, sigterm=_sigterm_disposition())


def plain_rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """No trace, no OpenTelemetry import: the ok rows of the synthetic mapper."""
    return _episode(cfg, seed)


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
    target_id: str = "timeout-oracle@v0",
    t_unit: str = "steps",
) -> str:
    """A sweep file over ``role``; ``capture`` is the sweep's ``[capture]`` table, or absent."""
    axes = {"role": list(ROLES)} if axes is None else axes
    lines = [f'target_id = "{target_id}"', f't_unit = "{t_unit}"', f"replicates = {replicates}", ""]
    for name, values in axes.items():
        kind = "continuous" if all(isinstance(v, float) for v in values) else "categorical"
        lines += [f"[axes.{name}]", f'type = "{kind}"', f"values = {json.dumps(values)}", ""]
    if capture is not None:
        # CD (D1): a [capture] table declares its cap. DECLARED_LIMIT is what these callers were
        # getting from the dataclass before, so nothing they measure moves.
        if "max_observation_bytes" not in capture and "max_span_bytes" not in capture:
            capture = {**capture, "max_observation_bytes": DECLARED_LIMIT}
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
    """A valid stored-shape trace dict around the given span dicts: the six keys (the trace-level ``truncated`` among them) plus A8a's ``alias_map_version``."""
    d: dict[str, Any] = {
        "schema": "poisson-prove.trace/1",
        "source": "otel",
        "source_version": OTEL_SEMCONV_VERSION,
        "dropped": 0,
        "spans": [dict(s) for s in spans],
        "truncated": None,
        "alias_map_version": None,
    }
    d.update(overrides)
    return d


def truncated_trace_dict() -> dict[str, Any]:
    """The stored shape of a snapshot: a closed root, an open child, ``truncated = "timeout"``."""
    return trace_dict(SPAN_CLOSED, SPAN_OPEN, truncated=REASON)


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


def by_name(trace: Trace) -> dict[str, Span]:
    return {span.name: span for span in trace.spans}


def _global_provider_is_sdk() -> bool:
    from opentelemetry import trace

    return type(trace.get_tracer_provider()).__module__.startswith("opentelemetry.sdk")


# ---------- helpers: isolation (the M3 capture frozen tests', verbatim in behaviour) ----------


class LogSink(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[list[str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append([record.name, record.levelname, record.getMessage()])


def watch_logs() -> LogSink:
    sink = LogSink()
    logging.getLogger().addHandler(sink)
    return sink


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


def child_run_local(
    store_root: str, toml_path: str, target: str, salt: str, episode_timeout: float | None
) -> dict[str, Any]:
    sink = watch_logs()
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=salt, import_path=target)
    t0 = time.perf_counter()
    summary = run_local(p, _resolve(target), store, episode_timeout=episode_timeout)
    return {
        "run_id": p.run_id,
        "summary": dataclasses.asdict(summary),
        "elapsed": time.perf_counter() - t0,
        "pid": os.getpid(),
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
        "logs": sink.records,
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
    store_root: str, toml_path: str, target: str, salt: str, episode_timeout: float
) -> dict[str, Any]:
    """``run_with_mapper`` driven by a mapper that runs ``worker_batch`` with capture, all in
    this one child: the fork branch installs in the episode children, never here."""
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


# ---------- fixtures: the two runs the E4/E5/E9/E10 tests read ----------


@dataclasses.dataclass(frozen=True)
class TimeoutRun:
    """One ``run_local`` with ``episode_timeout``, written by a forked child: one timed-out row
    (``role = "hang"``) and three ok rows."""

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
    def timed_out(self) -> Any:
        df = self.df
        rows = df[[is_hang(cfg) for cfg in df["config"]]]
        assert len(rows) == 1, rows
        return rows.iloc[0]

    @property
    def others(self) -> pd.DataFrame:
        df = self.df
        return df[[not is_hang(cfg) for cfg in df["config"]]].reset_index(drop=True)


def _timeout_run(tmp_path_factory: pytest.TempPathFactory, *, capture: dict[str, Any] | None) -> TimeoutRun:
    if not FORK_AVAILABLE:
        pytest.skip("the timeout path needs the fork start method")
    root = tmp_path_factory.mktemp("timeout-run")
    toml = write(root / "sweep.toml", sweep_toml(capture=capture))
    r = isolated(child_run_local, str(root / "store"), str(toml), HANG_PATH, SALT, TIMEOUT_S)
    return TimeoutRun(root=root / "store", run_id=r["run_id"], report=r)


@pytest.fixture(scope="module")
def timeout_run(tmp_path_factory: pytest.TempPathFactory) -> TimeoutRun:
    """With a ``[capture]`` table: the run E4, E9 and E10 read."""
    return _timeout_run(tmp_path_factory, capture={"instrument": []})


@pytest.fixture(scope="module")
def bare_timeout_run(tmp_path_factory: pytest.TempPathFactory) -> TimeoutRun:
    """Without one: the run E5 reads, and E9's row that has no trace to print."""
    return _timeout_run(tmp_path_factory, capture=None)


# ---------- hypothesis strategies: the M12 frozen tests', plus the truncated draw ----------

hex_ids = st.text(alphabet="0123456789abcdef", min_size=16, max_size=16)
json_scalars = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-(2**63), max_value=2**63)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=8)
)
json_values = st.recursive(
    json_scalars,
    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=4), inner, max_size=3),
    max_leaves=8,
)
json_objects = st.dictionaries(st.text(min_size=1, max_size=6), json_values, max_size=3)
epoch_ns = st.integers(min_value=0, max_value=2**62)
token_maps = st.none() | st.dictionaries(st.text(min_size=1, max_size=4), st.integers(min_value=0, max_value=10**6), max_size=3)
code_dicts = st.none() | st.fixed_dictionaries(
    {
        "filepath": st.text(min_size=1, max_size=10),
        "function": st.text(min_size=1, max_size=10),
        "lineno": st.none() | st.integers(min_value=1, max_value=10**6),
    }
)
KINDS_SPEC = ("llm", "tool", "retrieval", "db", "http", "agent", "other")
SOURCES_SPEC = ("record", "otel", "litellm", "mixed")
truncated_reasons = st.none() | st.text(min_size=1, max_size=8)


@st.composite
def span_forests(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Span dicts whose parent list is drawn over earlier ids, so acyclicity holds by construction."""
    ids = draw(st.lists(hex_ids, min_size=0, max_size=6, unique=True))
    spans: list[dict[str, Any]] = []
    for i, sid in enumerate(ids):
        start = draw(epoch_ns)
        delta = draw(st.none() | st.integers(min_value=0, max_value=10**12))
        spans.append(
            {
                "span_id": sid,
                "parent_id": draw(st.sampled_from([None, *ids[:i]])),
                "kind": draw(st.sampled_from(KINDS_SPEC)),
                "name": draw(st.text(min_size=1, max_size=8)),
                "start_ns": start,
                "end_ns": None if delta is None else start + delta,
                "input": draw(json_values),
                "output": draw(json_values),
                "tokens": draw(token_maps),
                "confidence": draw(st.none() | st.floats(min_value=0.0, max_value=1.0)),
                "error": draw(st.none() | st.text(min_size=1, max_size=10)),
                "code": draw(code_dicts),
                "attrs": draw(json_objects),
                "operation": None,
                "step_name": None,
                "outcome": None,
                "outcome_by": None,
                "attempt": None,
                "gate": None,
                "truncated": None,
                "bytes_original": None,
            }
        )
    return spans


# ---------- E1: the sixth key ----------


def test_e1_truncated_is_the_sixth_field_a_str_or_none_defaulting_to_none() -> None:
    assert tuple(f.name for f in dataclasses.fields(Trace)) == TRACE_FIELDS
    assert Trace(spans=(), source="record").truncated is None
    cut = Trace(spans=(), source="otel", truncated=REASON)
    assert cut.truncated == REASON
    with pytest.raises(dataclasses.FrozenInstanceError):
        cut.truncated = None  # type: ignore[misc]
    with pytest.raises(TraceValidationError):
        Trace(spans=(), source="record", truncated=3)  # type: ignore[arg-type]
    with pytest.raises(TraceValidationError):
        Trace.from_dict(trace_dict(truncated=3))


def test_e1_to_dict_emits_exactly_the_seven_keys() -> None:
    bare = Trace(spans=(), source="record").to_dict()
    assert set(bare) == TRACE_KEYS and bare["truncated"] is None and bare["alias_map_version"] is None
    d = Trace(
        spans=(Span.from_dict(SPAN_CLOSED),), source="otel", source_version="1.42.0", dropped=2, truncated=REASON
    ).to_dict()
    assert set(d) == TRACE_KEYS
    assert (d["source"], d["source_version"], d["dropped"], d["truncated"]) == ("otel", "1.42.0", 2, REASON)
    assert d["spans"] == [SPAN_CLOSED]


def test_e1_from_dict_rejects_a_six_key_dict_naming_truncated() -> None:
    six = trace_dict(SPAN_CLOSED)
    del six["truncated"]
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(six)
    assert "truncated" in str(info.value)


def test_e1_from_dict_rejects_an_eighth_key_naming_it() -> None:
    eight = trace_dict(SPAN_CLOSED, reason=REASON)
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(eight)
    assert "reason" in str(info.value)
    # Neither direction has an optional key: the six-key dict with the reason set reads back.
    assert Trace.from_dict(trace_dict(SPAN_CLOSED, SPAN_OPEN, truncated=REASON)).truncated == REASON
    assert Trace.from_dict(trace_dict(SPAN_CLOSED)).truncated is None


@settings(max_examples=75, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    spans=span_forests(),
    source=st.sampled_from(SOURCES_SPEC),
    source_version=st.none() | st.text(min_size=1, max_size=8),
    dropped=st.integers(min_value=0, max_value=100),
    truncated=truncated_reasons,
)
def test_e1_json_round_trip_holds_with_truncated_set(
    spans: list[dict[str, Any]], source: str, source_version: str | None, dropped: int, truncated: str | None
) -> None:
    tr = Trace(
        spans=tuple(Span(**d) for d in spans),
        source=source,
        source_version=source_version,
        dropped=dropped,
        truncated=truncated,
    )
    encoded = json.dumps(tr.to_dict())
    assert json.loads(encoded) == tr.to_dict()  # JSON-native: no tuples, no non-str keys
    again = Trace.from_dict(json.loads(encoded))
    assert again == tr
    assert again.truncated == truncated


# ---------- E2: converters and the recorder never truncate; merge propagates ----------


def test_e2_from_otel_yields_truncated_none_even_when_a_span_is_open() -> None:
    from poisson_prove.trace import from_otel

    closed = {
        "spanId": ROOT_ID, "parentSpanId": None, "name": "invoke_agent",
        "startTimeUnixNano": EPOCH, "endTimeUnixNano": EPOCH + 1_000_000, "attributes": [],
    }
    left_open = {
        "spanId": OPEN_ID, "parentSpanId": ROOT_ID, "name": "execute_tool",
        "startTimeUnixNano": EPOCH + 500, "endTimeUnixNano": None, "attributes": [],
    }
    tr = from_otel([closed, left_open])
    assert tr.truncated is None and len(tr.spans) == 2 and tr.dropped == 0
    assert by_name(tr)["execute_tool"].end_ns is None  # an open span on its own says nothing
    assert from_otel([]).truncated is None


def test_e2_from_litellm_yields_truncated_none() -> None:
    from poisson_prove.trace import from_litellm

    payload = {"model": "gpt-4o", "start_time": 1.0, "end_time": 2.0, "messages": []}
    assert from_litellm([payload]).truncated is None
    assert from_litellm([]).truncated is None


def test_e2_the_recorder_yields_truncated_none() -> None:
    from poisson_prove.trace import collect, record, step

    @step
    def lookup(x: int) -> int:
        return x + 1

    with collect() as collector:
        with record("tool", "search") as handle:
            handle.output = lookup(1)
    assert collector.trace.truncated is None
    assert [s.name for s in collector.trace.ordered()] == ["search", lookup.__qualname__]


def _cut(reason: str | None, span_id: str) -> Trace:
    span = Span(span_id=span_id, parent_id=None, kind="tool", name=span_id, start_ns=EPOCH, end_ns=None)
    return Trace(spans=(span,), source="otel", truncated=reason)


def test_e2_merge_yields_the_first_reason_and_never_invents_one() -> None:
    a, b, c = "000000000000000a", "000000000000000b", "000000000000000c"
    assert merge(_cut(None, a), _cut(None, b)).truncated is None
    assert merge(_cut(None, a), _cut(REASON, b)).truncated == REASON
    assert merge(_cut(REASON, a), _cut(None, b)).truncated == REASON
    assert merge(_cut(None, a), _cut("first", b), _cut("second", c)).truncated == "first"
    assert merge(_cut(None, a)).truncated is None
    assert merge().truncated is None
    merged = merge(_cut(None, a), _cut(REASON, b))
    assert merged.source == "mixed" and {s.span_id for s in merged.spans} == {a, b}


# ---------- E4: run_local with a timeout and capture ----------


def assert_snapshot_of(trace: Trace, seed: int, run_id: str, episode: str) -> None:
    """The timed-out row's trace: one closed ``chat``, an open ``invoke_agent`` root and an open
    ``execute_tool`` child, all with this seed's name and this row's stamps, nothing else."""
    assert trace.truncated == REASON
    assert trace.source == "otel" and trace.dropped == 0
    spans = by_name(trace)
    assert set(spans) == {f"invoke_agent {seed}", f"chat {seed}", f"execute_tool {seed}"}, sorted(spans)
    root, chat, tool = spans[f"invoke_agent {seed}"], spans[f"chat {seed}"], spans[f"execute_tool {seed}"]
    assert chat.end_ns is not None and chat.duration_ms is not None and chat.duration_ms >= 0.0
    for open_span in (root, tool):
        assert open_span.end_ns is None and open_span.duration_ms is None, open_span
        assert open_span.error is None, open_span
    assert root.parent_id is None and chat.parent_id == root.span_id and tool.parent_id == root.span_id
    assert (root.kind, chat.kind, tool.kind) == ("agent", "llm", "tool")
    for span in trace.spans:
        assert span.attrs[RUN_ID_KEY] == run_id and span.attrs[EPISODE_KEY] == episode, (span.name, span.attrs)
    assert {s.name.split(" ")[1] for s in trace.spans} == {str(seed)}, "a span from another row leaked in"
    assert len(trace.ordered()) == 3 and [s.name for s in trace.roots()] == [f"invoke_agent {seed}"]


def assert_intact_ok_rows(others: pd.DataFrame, run_id: str) -> None:
    """What I9 requires of every other row, plus the complete stamped trace C5 gives it."""
    assert len(others) == 3 and others["error"].isna().all()
    for row in others.itertuples(index=False):
        assert row.outcome == _outcome(row.config, row.seed), row
        trace = Trace.from_dict(row.meta["trace"])
        assert trace.truncated is None and trace.dropped == 0
        assert sorted(s.name for s in trace.spans) == sorted([f"invoke_agent {row.seed}", f"chat {row.seed}"])
        for span in trace.spans:
            assert span.end_ns is not None
            assert span.attrs[RUN_ID_KEY] == run_id
            assert span.attrs[EPISODE_KEY] == episode_id(row.config_hash, row.replicate_index)


@needs_fork
def test_e4_the_timed_out_row_carries_its_truncated_trace_and_every_other_row_is_intact(timeout_run: TimeoutRun) -> None:
    summary = timeout_run.report["summary"]
    assert (summary["n_ok"], summary["n_errored"], summary["n_timeout"], summary["complete"]) == (3, 1, 1, True), summary
    record = timeout_run.store.manifest(timeout_run.run_id).environment["capture"]
    assert record["requested"] is True and record["active"] is True, record
    slow = timeout_run.timed_out
    assert slow["outcome"] is None and slow["error"] == REASON and pd.isna(slow["t"])
    assert set(slow["meta"]) == {"trace"}, slow["meta"]
    # The handler exited the child (never back into the rollout), so the parent's
    # join was immediate: _call_with_timeout returned well inside the drain grace, not at kill().
    assert float(slow["wall_time"]) < TIMEOUT_S + DRAIN_GRACE_S + PROCESS_SLACK_S, slow["wall_time"]
    assert_snapshot_of(
        Trace.from_dict(slow["meta"]["trace"]), int(slow["seed"]), timeout_run.run_id,
        episode_id(slow["config_hash"], int(slow["replicate_index"])),
    )
    assert_intact_ok_rows(timeout_run.others, timeout_run.run_id)


# ---------- E5: no [capture] table, nothing changes ----------


@needs_fork
def test_e5_without_a_capture_table_the_timed_out_row_is_bare_and_the_child_keeps_the_default_disposition(
    bare_timeout_run: TimeoutRun, timeout_run: TimeoutRun
) -> None:
    summary = bare_timeout_run.report["summary"]
    assert (summary["n_ok"], summary["n_errored"], summary["n_timeout"], summary["complete"]) == (3, 1, 1, True), summary
    slow = bare_timeout_run.timed_out
    assert slow["outcome"] is None and slow["error"] == REASON
    assert slow["meta"] == {}, slow["meta"]
    # _call_with_timeout returned within timeout + _JOIN_GRACE_S, as today: wall_time is that call.
    assert float(slow["wall_time"]) < TIMEOUT_S + JOIN_GRACE_S, slow["wall_time"]
    others = bare_timeout_run.others
    assert len(others) == 3 and others["error"].isna().all()
    assert all("trace" not in meta for meta in others["meta"]), list(others["meta"])
    assert {meta["sigterm"] for meta in others["meta"]} == {"default"}, list(others["meta"])
    # The other half of "a handler when and only when there is a capture call": with one, the child has a handler.
    assert {meta["sigterm"] for meta in timeout_run.others["meta"]} == {"handler"}, list(timeout_run.others["meta"])
    assert bare_timeout_run.report["sdk_provider_in_this_process"] is False


# ---------- E7: worker_batch and run_with_mapper ----------


@needs_fork
def test_e7_worker_batch_returns_the_dict_form_for_the_timed_out_job_with_capture(tmp_path: Path) -> None:
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), Store(tmp_path / "store"), run_salt=SALT)
    jobs = jobs_of(p)
    r = isolated(child_worker_batch, jobs, HANG_PATH, TIMEOUT_S, capture_payload(RUN_ID))
    results = r["results"]
    assert len(results) == len(jobs) == 4
    timed_out = 0
    for job, result in zip(jobs, results, strict=True):
        config, seed, i, config_hash, replicate_index = job
        assert isinstance(result, dict), result
        if is_hang(config):
            timed_out += 1
            assert set(result) == {"error", "meta"}, sorted(result)
            assert result["error"] == REASON
            assert set(result["meta"]) == {"trace"}, result["meta"]
            assert_snapshot_of(Trace.from_dict(result["meta"]["trace"]), seed, RUN_ID, episode_id(config_hash, replicate_index))
        else:
            assert result["outcome"] == _outcome(config, seed) and result["backend_meta"]["i"] == i
            assert Trace.from_dict(result["meta"]["trace"]).truncated is None
    assert timed_out == 1
    assert r["sdk_provider_in_this_process"] is False, "worker_batch installed in the forking parent"


@needs_fork
def test_e7_worker_batch_returns_the_string_for_the_timed_out_job_without_capture(tmp_path: Path) -> None:
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), Store(tmp_path / "store"), run_salt=SALT)
    jobs = jobs_of(p)
    results = worker_batch(jobs, HANG_PATH, TIMEOUT_S)  # I3's call: three positionals, no capture
    assert len(results) == 4
    for job, result in zip(jobs, results, strict=True):
        config, seed, i, _, _ = job
        if is_hang(config):
            assert result == REASON, result
        else:
            assert isinstance(result, dict) and result["outcome"] == _outcome(config, seed), result
            assert "trace" not in result["meta"] and result["backend_meta"]["i"] == i
    assert sum(1 for result in results if result == REASON) == 1
    assert not _global_provider_is_sdk(), "a worker_batch call without capture installed a provider"


@needs_fork
def test_e7_run_with_mapper_stores_the_dict_form_as_an_errored_row_with_its_trace(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": []}))
    r = isolated(child_run_with_mapper, str(tmp_path / "store"), str(toml), HANG_PATH, SALT, TIMEOUT_S)
    summary = r["summary"]
    assert (summary["n_ok"], summary["n_errored"], summary["n_timeout"], summary["complete"]) == (3, 1, 1, True), summary
    dict_forms = [x for x in r["results"] if isinstance(x, dict) and "error" in x]
    assert len(dict_forms) == 1 and set(dict_forms[0]) == {"error", "meta"}, r["results"]
    run = TimeoutRun(root=tmp_path / "store", run_id=r["run_id"], report=r)
    slow = run.timed_out
    assert slow["outcome"] is None and slow["error"] == REASON
    assert set(slow["meta"]) == {"trace"}, slow["meta"]
    assert_snapshot_of(
        Trace.from_dict(slow["meta"]["trace"]), int(slow["seed"]), r["run_id"],
        episode_id(slow["config_hash"], int(slow["replicate_index"])),
    )
    assert_intact_ok_rows(run.others, r["run_id"])
    assert r["sdk_provider_in_this_process"] is False, "the mapper's process installed a provider"


def test_e7_record_dispatches_str_to_bare_error_error_dict_to_errored_with_meta_and_any_other_dict_to_episode(tmp_path: Path) -> None:
    store = Store(tmp_path / "store")
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), store, backend="modal", run_salt=SALT)
    jobs = jobs_of(p)
    episodes = worker_batch(jobs, PLAIN_PATH, None)  # in-process, no fork, no OTel
    assert all(isinstance(e, dict) and "error" not in e for e in episodes)
    trace = truncated_trace_dict()
    forms: list[Result] = [episodes[0], REASON, {"error": REASON, "meta": {"trace": trace}}, "Traceback: boom"]

    def mapper(batches: Sequence[Sequence[Job]]) -> Iterator[tuple[int, list[Result] | BaseException]]:
        assert len(batches) == 1 and len(batches[0]) == 4
        yield 0, list(forms)

    summary = run_with_mapper(p, mapper, store, options=ModalOptions())
    assert (summary.n_ok, summary.n_errored, summary.n_timeout, summary.complete) == (1, 3, 2, True), summary
    df = store.read(p.run_id)
    keyed = {(row.config_hash, int(row.replicate_index)): row for row in df.itertuples(index=False)}
    rows = [keyed[(job[3], job[4])] for job in jobs]
    assert rows[0].error is None and rows[0].outcome == _outcome(jobs[0][0], jobs[0][1])
    assert rows[1].error == REASON and rows[1].outcome is None and rows[1].meta == {}
    assert rows[2].error == REASON and rows[2].outcome is None and rows[2].meta == {"trace": trace}
    assert Trace.from_dict(rows[2].meta["trace"]).truncated == REASON
    assert rows[3].error == "Traceback: boom" and rows[3].meta == {}


# ---------- E8: errored(meta=) and retention ----------


def test_e8_errored_stores_the_given_meta_and_defaults_to_empty() -> None:
    parameter = inspect.signature(EpisodeRecord.errored).parameters["meta"]
    assert parameter.kind is parameter.KEYWORD_ONLY and parameter.default is None
    meta = {"trace": truncated_trace_dict(), "k": 1}
    common: dict[str, Any] = dict(run_id="r1", config={"a": 1}, seed=0, replicate_index=0, error=REASON, wall_time=0.1)
    carried = EpisodeRecord.errored(**common, meta=meta)
    assert carried.meta == meta and carried.error == REASON and carried.outcome is None
    assert (carried.t, carried.horizon, carried.confidence) == (None, None, None)
    assert Trace.from_dict(carried.meta["trace"]).truncated == REASON
    assert EpisodeRecord.errored(**common).meta == {}
    assert EpisodeRecord.errored(**common, meta=None).meta == {}
    assert EpisodeRecord.errored(**common, backend_meta={"i": 3}).meta == {}


@pytest.mark.parametrize("retain", [("violated",), ()], ids=["one-outcome", "nothing"])
def test_e8_retention_never_strips_an_errored_row_and_still_strips_an_unretained_ok_row(tmp_path: Path, retain: tuple[str, ...]) -> None:
    store = Store(tmp_path)
    store.create_run(manifest(retain_traces_for=retain))
    trace = truncated_trace_dict()
    records = [
        ok_record("completed", 0, {"trace": ["a"], "k": 1}),
        EpisodeRecord.errored(run_id="r1", config={"friction": 0.5}, seed=2, replicate_index=2, error=REASON, wall_time=0.1, meta={"trace": trace, "k": 3}),
        EpisodeRecord.errored(run_id="r1", config={"friction": 0.5}, seed=3, replicate_index=3, error="boom", wall_time=0.1, meta={"trace": ["c"], "k": 4}),
    ]
    if retain:
        records.append(ok_record("violated", 1, {"trace": ["b"], "k": 2}))
    store.append("r1", records)
    df = store.read("r1").set_index("replicate_index")
    assert df.loc[0, "meta"] == {"k": 1}  # I8's existing half: an unretained ok row loses its trace
    assert df.loc[2, "meta"] == {"trace": trace, "k": 3}
    assert df.loc[3, "meta"] == {"trace": ["c"], "k": 4}
    assert Trace.from_dict(df.loc[2, "meta"]["trace"]).truncated == REASON
    if retain:
        assert df.loc[1, "meta"] == {"trace": ["b"], "k": 2}


# ---------- E9: inspect ----------


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
    and the trailing reproduction snippet. The M10 frozen tests' helper."""
    body, marker, tail = out.partition(SNIPPET_MARKER)
    assert marker, f"no {SNIPPET_MARKER!r} snippet in inspect output:\n{out}"
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in body.splitlines():
        # Text output shows a config_hash at 12 hex characters.
        if any(h[:12] in line for h in hashes):
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
    # Text output shows a config_hash at 12 hex characters.
    assert row.config_hash[:12] in block[0], block[0]
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


def step_columns(block: list[str]) -> list[list[str]]:
    return [line.split("\t") for line in block if STEP_LINE_RE.match(line)]


@needs_fork
def test_e9_inspect_selects_the_timed_out_row_by_error_and_prints_its_truncated_trace(timeout_run: TimeoutRun) -> None:
    r = inspect_run(timeout_run.root, timeout_run.run_id, REASON)
    assert r.code == 0, r.text
    assert "Traceback" not in r.text and not r.err.strip(), r.text
    blocks, snippet = inspect_blocks(r.out, set(timeout_run.df["config_hash"]))
    assert len(blocks) == 1, r.out
    block = blocks[0]
    slow = timeout_run.timed_out
    assert_block_is_row(block, slow)
    # The errored row's lines, where an ok row prints t: <float>.
    assert block.count(f"error: {REASON}") == 1, "\n".join(block)
    assert "outcome: -" in block and "t: -" in block, "\n".join(block)
    # Exactly one truncated line, before the span lines, and never a span line itself.
    truncated_at = [i for i, line in enumerate(block) if line == TRUNCATED_LINE]
    assert len(truncated_at) == 1, "\n".join(block)
    assert STEP_LINE_RE.match(STEP_LINE_SAMPLE), "STEP_LINE_RE matches nothing; a negative use below would be vacuous"
    step_at = [i for i, line in enumerate(block) if STEP_LINE_RE.match(line)]
    trace = Trace.from_dict(slow["meta"]["trace"])
    assert len(step_at) == len(trace.spans) == 3, "\n".join(block)
    assert truncated_at[0] < step_at[0], "\n".join(block)
    # The five tab-delimited columns: index, kind, name, duration, error; "-" for an open span.
    columns = [block[i].split("\t") for i in step_at]
    assert [cols[0].strip() for cols in columns] == ["0", "1", "2"]
    assert [cols[2] for cols in columns] == [s.name for s in trace.ordered()]
    seed = int(slow["seed"])
    by_col = {cols[2]: cols for cols in columns}
    assert by_col[f"invoke_agent {seed}"][1:2] == ["agent"] and by_col[f"invoke_agent {seed}"][3] == "-"
    assert by_col[f"execute_tool {seed}"][1:2] == ["tool"] and by_col[f"execute_tool {seed}"][3] == "-"
    assert by_col[f"chat {seed}"][1] == "llm" and float(by_col[f"chat {seed}"][3]) >= 0.0
    assert all(cols[4] == "-" for cols in columns), columns
    # The snippet reproduces the timed-out episode, the only row printed.
    assert f"seed={seed}" in "\n".join(snippet), snippet


@needs_fork
def test_e9_a_row_selected_by_outcome_prints_no_truncated_line(timeout_run: TimeoutRun) -> None:
    others = timeout_run.others
    event = str(others.iloc[0]["outcome"])
    expected = others[others["outcome"] == event].reset_index(drop=True)
    r = inspect_run(timeout_run.root, timeout_run.run_id, event)
    assert r.code == 0, r.text
    assert "Traceback" not in r.text and not r.err.strip(), r.text
    blocks, _ = inspect_blocks(r.out, set(timeout_run.df["config_hash"]))
    assert len(blocks) == len(expected) >= 1, r.out
    assert TRUNCATED_LINE not in r.out and "trace: truncated" not in r.out, r.out
    for block, row in zip(blocks, expected.itertuples(index=False), strict=True):
        assert_block_is_row(block, row)
        assert f"error: {REASON}" not in block, "\n".join(block)
        t_lines = [line for line in block if line.startswith("t: ")]
        assert len(t_lines) == 1 and float(t_lines[0][3:]) == float(row.t), t_lines
        columns = step_columns(block)
        assert len(columns) == 2, "\n".join(block)
        assert all(float(cols[3]) >= 0.0 for cols in columns), columns


@needs_fork
def test_e9_a_timed_out_row_without_a_trace_prints_its_error_and_no_trace_lines(bare_timeout_run: TimeoutRun) -> None:
    r = inspect_run(bare_timeout_run.root, bare_timeout_run.run_id, REASON)
    assert r.code == 0, r.text
    assert "Traceback" not in r.text and not r.err.strip(), r.text
    blocks, _ = inspect_blocks(r.out, set(bare_timeout_run.df["config_hash"]))
    assert len(blocks) == 1, r.out
    block = blocks[0]
    assert_block_is_row(block, bare_timeout_run.timed_out)
    assert block.count(f"error: {REASON}") == 1, "\n".join(block)
    assert STEP_LINE_RE.match(STEP_LINE_SAMPLE), "STEP_LINE_RE matches nothing; a negative use below would be vacuous"
    assert "trace: truncated" not in r.out and not step_columns(block), "\n".join(block)


@needs_fork
def test_e9_an_event_matching_neither_outcome_nor_error_prints_the_no_rows_message_naming_it(timeout_run: TimeoutRun) -> None:
    r = inspect_run(timeout_run.root, timeout_run.run_id, "no-such-event")
    assert r.code == 0, r.text
    assert "Traceback" not in r.text and not r.err.strip(), r.text
    assert "no rows" in r.out and "no-such-event" in r.out, r.out
    assert SNIPPET_MARKER not in r.out
    assert STEP_LINE_RE.match(STEP_LINE_SAMPLE), "STEP_LINE_RE matches nothing; a negative use below would be vacuous"
    assert not [line for line in r.out.splitlines() if STEP_LINE_RE.match(line)], r.out


# ---------- E10: the parent never installs; the child owned the spans ----------


@needs_fork
def test_e10_the_forking_parent_never_installs_and_the_snapshot_came_from_the_child_that_owned_the_spans(timeout_run: TimeoutRun) -> None:
    assert timeout_run.report["sdk_provider_in_this_process"] is False, "run_local installed in the forking parent"
    slow = timeout_run.timed_out
    trace = Trace.from_dict(slow["meta"]["trace"])
    tool = by_name(trace)[f"execute_tool {int(slow['seed'])}"]
    # The open span's attributes are the child's, read live: its pid is not the parent's.
    assert isinstance(tool.attrs.get(PID_KEY), int), tool.attrs
    assert tool.attrs[PID_KEY] != timeout_run.report["pid"]
    assert tool.attrs[PID_KEY] != os.getpid()
    assert not _global_provider_is_sdk(), "the pytest process installed a provider"


# ---------- E11: merge with a truncated capture ----------


def test_e11_merging_a_record_trace_with_a_truncated_capture_yields_the_reason_and_mixed() -> None:
    own = Trace(
        spans=(Span(span_id="00000000000000aa", parent_id=None, kind="tool", name="recorded-tool", start_ns=EPOCH, end_ns=EPOCH + 1_000_000, attrs={"attempts": 1}),),
        source="record",
    )
    captured = Trace.from_dict(truncated_trace_dict())
    assert own.truncated is None and captured.truncated == REASON
    for merged in (merge(own, captured), merge(captured, own)):
        assert merged.truncated == REASON and merged.source == "mixed"
        assert {s.span_id for s in merged.spans} == {"00000000000000aa", ROOT_ID, OPEN_ID}
        assert merged.dropped == 0
        assert by_name(merged)[SPAN_OPEN["name"]].end_ns is None
        assert Trace.from_dict(json.loads(json.dumps(merged.to_dict()))) == merged


# ---------- E13: a dict-form result with a bad meta is refused, never stored bare ----------


@pytest.mark.parametrize(
    "bad",
    [{"error": REASON, "meta": ["not", "a", "mapping"]}, {"error": REASON, "meta": "text"}, {"error": REASON, "meta": None}, {"error": REASON}],
    ids=["list", "str", "none", "absent"],
)
def test_e13_a_dict_form_result_whose_meta_is_not_a_mapping_raises_naming_the_job_and_stores_nothing(tmp_path: Path, bad: dict[str, Any]) -> None:
    store = Store(tmp_path / "store")
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), store, backend="modal", run_salt=SALT)
    jobs = jobs_of(p)
    episodes = worker_batch(jobs, PLAIN_PATH, None)
    forms: list[Result] = [episodes[0], episodes[1], dict(bad), episodes[3]]

    def mapper(batches: Sequence[Sequence[Job]]) -> Iterator[tuple[int, list[Result] | BaseException]]:
        yield 0, list(forms)

    with pytest.raises(ModalBackendError) as info:
        run_with_mapper(p, mapper, store, options=ModalOptions())
    assert re.search(r"\bjob 2\b", str(info.value)), str(info.value)
    assert store.count(p.run_id) == 0, "a batch with a malformed result was stored"
