"""M3 -- trace capture: the frozen tests for C1-C12, C2a included.

Written from "Proofload -- Spec M3 Executor (trace capture amendment)" section 4. The build
builds ``src/proofload/capture.py`` and the four wiring changes against this file and does not
edit it. Every test imports ``proofload.capture`` inside its own body, so the file collects
while the module does not exist. The capture module lives behind the ``agent`` extra; the
whole file skips without ``opentelemetry-sdk``, the way the stamper frozen tests do, and the one
test that feeds finished spans through the OTLP encoder skips at that helper -- the encoder
is a dev-only reference, like lifelines.

C1 and C2 come first because both were found by running code and both fail silently: a run
completes normally and every trace is empty or nearly empty. C1 uses a real fork, both ways,
from a driver written to a real file (``spawn`` re-imports ``__main__`` and cannot re-import
``<stdin>``). C2 re-seeds the global ``random`` between spans against the real provider
``install()`` builds. Neither uses a mock provider.

Installing a provider is permanent (C2a), so every test that calls ``install()`` -- directly,
or through ``run_local``, ``worker_batch`` or the CLI -- runs it in a child process forked from
this one (``isolated``) and reads the store, the results and the child's log records back
through a pipe. The pytest process itself never installs, so every child starts from the same
clean state and the in-process tests can assert the global provider was left alone.
OpenTelemetry objects are imported inside test bodies, never held at module level: M12's T27
purges ``opentelemetry*`` from ``sys.modules`` earlier in the suite, and a module-level
reference would then point at a different copy of the SDK than the code under test.

Conventions the frozen tests fix where the spec is silent, recorded so they are not re-litigated:

- The episode id stamped as ``proofload.episode`` is ``f"{config_hash}:{replicate_index}"`` on
  every path. Section 3 derives it from those two fields inside ``worker_batch``; the local
  path has the same two on its ``Pair``.
- ``worker_batch``'s keyword-only ``capture`` dict carries the four ``CaptureSpec`` fields as
  JSON-native values (``instrument`` a list) plus ``"run_id"``. Section 3 fixes the signature
  at one new parameter and says the run id rides the map item, so at the ``worker_batch``
  boundary it can only travel inside that dict.
- ``CaptureSpec.instrument`` names resolve through the ``opentelemetry_instrumentor``
  entry-point group, the group every ``opentelemetry-instrumentation-*`` package registers
  under; a name with no entry point is C4's "unknown instrumentor name". The frozen tests register
  two fakes in a throwaway dist-info under ``tmp_path``, so no instrumentation package is
  installed and nothing is patched.
- A ``[capture]`` table with ``instrument = []`` still installs the provider and is active:
  ``install(CaptureSpec(max_observation_bytes=...))`` must capture for C2 to be testable at all --
  CD (D1) took the cap's default away, and this file declares ``DECLARED_LIMIT`` for it -- and a
  target that emits spans through the OTel API itself needs no instrumentor.
- ``run_local`` learns of the request from the ``[capture]`` table ``SweepSpec.load`` reads.
  The tests drive it from a TOML file only and pin no field name on ``SweepSpec``.
- C7's collision WARNING is asserted as exactly one WARNING record on a logger under
  ``proofload`` during a one-episode run; the logger's exact name is not pinned.
- C10's marker "recording each original byte length" is accepted with either defensible
  measure of the replaced value: its UTF-8 length or the length of its JSON encoding.
- The manifest record of section 3 is asserted only when a ``[capture]`` table is present.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import importlib.machinery
import importlib.util
import inspect
import json
import logging
import multiprocessing
import random
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, ExitStack
from io import StringIO
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

import poisson_prove
import poisson_prove.cli as cli
import poisson_prove.executor as executor
from poisson_prove.episode import Episode
from poisson_prove.executor import RunSummary, plan, run_local
from poisson_prove.executor_modal import Job, Mapper, Result, worker_batch
from poisson_prove.sampler import SweepSpec
from poisson_prove.store import EpisodeRecord, Store
from poisson_prove.trace import OTEL_SEMCONV_VERSION, Span, Trace

pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")

MODULE = __name__
PACKAGE = Path(poisson_prove.__file__).resolve().parent  # the tree under test; a shadow tree under PYTHONPATH
RUN_ID_KEY = "poisson_prove.run_id"
EPISODE_KEY = "poisson_prove.episode"
#: A8b: test-local and narrower than the public ``trace.CONTENT_KEYS`` (six prefix families more);
#: renamed so it cannot shadow it. C9 covers the shipped half only -- the widening is the A8b frozen tests' P8-10.
GENAI_CONTENT_KEYS = ("gen_ai.input.messages", "gen_ai.output.messages")
OVERRIDE_MESSAGE = "Overriding of current TracerProvider is not allowed"
PUBLIC_SURFACE = frozenset({"CaptureSpec", "CaptureStatus", "install", "Recorder", "capture"})
SPEC_FIELDS = ("instrument", "content", "max_observation_bytes", "max_spans")  # A8b: the rename
#: CD (D1): ``CaptureSpec`` has no default cap and a ``[capture]`` table must declare one. This is
#: the number every caller in this file was getting from the dataclass before, so what the tests
#: below measure is unchanged -- it is now declared rather than supplied.
DECLARED_LIMIT = 8192
STATUS_FIELDS = ("requested", "active", "reason", "instrumented")
MANIFEST_KEYS = frozenset({*STATUS_FIELDS, "semconv", "alias_map_version", "content", "max_observation_bytes", "max_spans"})  # A8a: + alias_map_version; A8b: the byte field renamed
TOUCHED_FILES = ("capture.py", "executor.py", "executor_modal.py", "sampler.py", "cli.py")
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
FAKE_INSTRUMENTOR = "oracle-fake"
CONFLICT_INSTRUMENTOR = "oracle-conflict"
UNKNOWN_INSTRUMENTOR = "no-such-instrumentor-xyz"
FAKE_MODULE = "oracle_fake_instrumentation"
MOCK_ROLLOUT = "poisson_prove.examples.mock_agent:rollout"
HORIZON = 10.0
SALT = "capture-oracle-salt"
EPOCH = 1_756_900_000_000_000_000
RUN_ID = "r-2026-09-04-oracle"
GARBAGE_TRACES: dict[str, Any] = {
    "list": ["step-a", "step-b"],
    "dict": {"schema": "not/proofload", "steps": []},
}


# ---------- module-level rollouts (pickle by reference under fork and spawn) ----------


def _outcome(cfg: dict[str, Any], seed: int) -> str:
    return "fell" if (seed + int(float(cfg.get("x", 0.0)) * 10)) % 3 == 0 else "survived"


def _episode(cfg: dict[str, Any], seed: int, **meta: Any) -> Episode:
    outcome = _outcome(cfg, seed)
    return Episode(
        outcome=outcome, t=3.0 if outcome == "fell" else HORIZON, horizon=HORIZON, meta=meta
    )


def _tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer("oracle.instrumentation", "0.1.0")


def plain_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    """No trace, no OpenTelemetry import: the C3 target."""
    return _episode(cfg, seed)


def otel_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    """An instrumented agent as the API sees it: an ``invoke_agent`` root with a ``chat``
    child. Span names carry the seed, so a span in the wrong row is visible by name. No
    ``gen_ai.request.model`` here: M12 lifts it into ``name`` and the seed would vanish."""
    tracer = _tracer()
    with tracer.start_as_current_span(f"invoke_agent {seed}") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        with tracer.start_as_current_span(f"chat {seed}") as child:
            child.set_attribute("gen_ai.operation.name", "chat")
    return _episode(cfg, seed)


def _own_trace(span_id: str) -> dict[str, Any]:
    span = Span(
        span_id=span_id,
        parent_id=None,
        kind="tool",
        name="recorded-tool",
        start_ns=EPOCH,
        end_ns=EPOCH + 1_000_000,
        attrs={"attempts": 1},
    )
    return Trace(spans=(span,), source="record").to_dict()


def recording_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    """Writes its own valid record trace and also emits an OTel span: C7's merge case."""
    with _tracer().start_as_current_span(f"chat {seed}") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
    return _episode(cfg, seed, trace=_own_trace(f"{seed:016x}"))


def colliding_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    """Emits one OTel span, then writes a record trace reusing that span's id: C7's collision."""
    with _tracer().start_as_current_span(f"chat {seed}") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span_id = format(span.get_span_context().span_id, "016x")
    return _episode(cfg, seed, trace=_own_trace(span_id))


def garbage_trace_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    """Writes a ``meta["trace"]`` that is not a trace dict, and emits an OTel span: C7's
    last clause. The shape comes from the ``shape`` axis."""
    with _tracer().start_as_current_span(f"chat {seed}"):
        pass
    return _episode(cfg, seed, trace=GARBAGE_TRACES[str(cfg["shape"])], k=1)


def _resolve(import_path: str) -> Any:
    module_name, attr = import_path.split(":", 1)
    return getattr(importlib.import_module(module_name), attr)


# ---------- helpers: sweep files, jobs, the store on disk ----------


def sweep_toml(
    *,
    capture: dict[str, Any] | None,
    replicates: int = 2,
    axes: dict[str, list[Any]] | None = None,
    target_id: str = "capture-oracle@v0",
    t_unit: str = "steps",
) -> str:
    """A sweep file; ``capture`` is the ``[capture]`` table of section 3, or absent."""
    axes = {"x": [0.1, 0.2]} if axes is None else axes
    lines = [f'target_id = "{target_id}"', f't_unit = "{t_unit}"', f"replicates = {replicates}", ""]
    for name, values in axes.items():
        kind = "continuous" if all(isinstance(v, float) for v in values) else "categorical"
        lines += [f"[axes.{name}]", f'type = "{kind}"', f"values = {json.dumps(values)}", ""]
    if capture is not None:
        # CD (D1): a [capture] table declares its cap; a caller that named one, or a bad one, is left alone.
        if "max_observation_bytes" not in capture and "max_span_bytes" not in capture:
            capture = {**capture, "max_observation_bytes": DECLARED_LIMIT}
        lines.append("[capture]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in capture.items()]
    return "\n".join(lines) + "\n"


def mock_toml(*, capture: dict[str, Any] | None, replicates: int = 4) -> str:
    return sweep_toml(
        capture=capture,
        replicates=replicates,
        axes={"task_id": ["search", "checkout", "refund"], "tool_fail_rate": [0.0, 0.5]},
        target_id="mock-agent@v0",
        t_unit="tool_calls",
    )


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


def raw_meta(store_root: Path, run_id: str) -> dict[tuple[str, int], str]:
    """The ``meta`` column exactly as stored, keyed by (config_hash, replicate_index)."""
    out: dict[tuple[str, int], str] = {}
    for part in sorted((store_root / run_id / "episodes").glob("part-*.parquet")):
        table = pq.read_table(part, columns=["config_hash", "replicate_index", "meta"])
        for h, k, meta in zip(*(table.column(c).to_pylist() for c in table.column_names), strict=True):
            out[(str(h), int(k))] = str(meta)
    return out


def names(meta: dict[str, Any] | None) -> list[str]:
    assert meta is not None, "expected a captured trace, got None"
    return [span.name for span in Trace.from_dict(meta).ordered()]


def warnings_under_proofload(records: list[list[str]]) -> list[list[str]]:
    return [r for r in records if r[1] == "WARNING" and r[0].split(".")[0] == "poisson_prove"]


def _global_provider_is_sdk() -> bool:
    from opentelemetry import trace

    return type(trace.get_tracer_provider()).__module__.startswith("opentelemetry.sdk")


class TtyStringIO(StringIO):
    """A StringIO that claims to be a terminal, so the CLI reaches its prompt (M10 I4)."""

    def isatty(self) -> bool:
        return True


# ---------- helpers: the fake instrumentors ----------

FAKE_SOURCE = '''\
"""Two throwaway instrumentors for the M3 capture oracle. Nothing here patches anything."""

INSTRUMENTED = []


class DependencyConflict(Exception):
    pass


class FakeInstrumentor:
    def instrumentation_dependencies(self):
        return ()

    def instrument(self, **kwargs):
        INSTRUMENTED.append(sorted(kwargs))

    def uninstrument(self, **kwargs):
        return None


class ConflictingInstrumentor(FakeInstrumentor):
    def instrument(self, **kwargs):
        raise DependencyConflict("oracle-lib 1.0 found, oracle-lib>=2.0 required")
'''


def register_fake_instrumentors(root: Path) -> Path:
    """A dist-info under ``root`` exposing two ``opentelemetry_instrumentor`` entry points.
    Put ``root`` on ``sys.path`` and ``importlib.metadata`` finds them like any installed
    instrumentation package."""
    write(root / f"{FAKE_MODULE}.py", FAKE_SOURCE)
    info = root / f"{FAKE_MODULE}-0.0.1.dist-info"
    write(info / "METADATA", f"Metadata-Version: 2.1\nName: {FAKE_MODULE}\nVersion: 0.0.1\n")
    write(
        info / "entry_points.txt",
        "[opentelemetry_instrumentor]\n"
        f"{FAKE_INSTRUMENTOR} = {FAKE_MODULE}:FakeInstrumentor\n"
        f"{CONFLICT_INSTRUMENTOR} = {FAKE_MODULE}:ConflictingInstrumentor\n",
    )
    return root


# ---------- helpers: isolation ----------


class LogSink(logging.Handler):
    """Collects every record the root logger sees, as ``[logger, level, message]``."""

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
    """Run ``fn(*args)`` in a child process and return its (JSON-native) result.

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


def status_dict(status: Any) -> dict[str, Any]:
    return {name: list(v) if isinstance(v, tuple) else v for name, v in dataclasses.asdict(status).items()}


def _purge(*prefixes: str) -> None:
    for name in [n for n in sys.modules if any(n == p or n.startswith(p + ".") for p in prefixes)]:
        del sys.modules[name]


# ---------- the children: everything that installs a provider runs here ----------


def child_run_local(
    store_root: str,
    toml_path: str,
    target: str,
    salt: str,
    episode_timeout: float | None,
    extra_path: str | None,
) -> dict[str, Any]:
    if extra_path is not None:
        sys.path.insert(0, extra_path)
    sink = watch_logs()
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=salt, import_path=target)
    summary = run_local(p, _resolve(target), store, episode_timeout=episode_timeout)
    return {
        "run_id": p.run_id,
        "summary": dataclasses.asdict(summary),
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
        "logs": sink.records,
    }


def child_worker_batch(
    jobs: list[Job], import_path: str, episode_timeout: float | None, capture: dict[str, Any] | None
) -> dict[str, Any]:
    sink = watch_logs()
    results = worker_batch(jobs, import_path, episode_timeout, capture=capture)
    return {
        "results": results,
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
        "logs": sink.records,
    }


def child_run_without_capture(
    store_root: str, toml_path: str, target: str, salt: str, worker: bool
) -> dict[str, Any]:
    """T27's move, one layer up: purge OTel, run with no ``[capture]`` table, then look at
    what came back into ``sys.modules``."""
    _purge("opentelemetry", "poisson_prove.otel", "poisson_prove.capture")
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=salt)
    results: list[Result] | None = None
    if worker:
        results = worker_batch(jobs_of(p), target, None)
    else:
        run_local(p, _resolve(target), store)
    return {
        "run_id": p.run_id,
        "results": results,
        "opentelemetry_modules": sorted(n for n in sys.modules if n.split(".")[0] == "opentelemetry"),
        "otel_helper_loaded": "poisson_prove.otel" in sys.modules,
    }


def child_import_capture_clean() -> dict[str, Any]:
    _purge("opentelemetry", "poisson_prove.otel", "poisson_prove.capture")
    importlib.import_module("poisson_prove.capture")
    return {
        "opentelemetry_modules": sorted(n for n in sys.modules if n.split(".")[0] == "opentelemetry"),
        "otel_helper_loaded": "poisson_prove.otel" in sys.modules,
    }


def child_install(
    spec_kwargs: dict[str, Any],
    extra_path: str | None = None,
    preset: str | None = None,
    block_sdk: bool = False,
    twice: bool = False,
) -> dict[str, Any]:
    """``install()`` in a prepared process, then one capture block holding one span.

    ``preset="noop"`` sets the API's no-op provider globally first; ``preset="sdk"`` sets a
    user's SDK provider with its own exporter; ``block_sdk`` makes ``opentelemetry.sdk``
    unimportable; ``twice`` calls ``install()`` a second time with the same spec.
    """
    if extra_path is not None:
        sys.path.insert(0, extra_path)
    sink = watch_logs()
    user: dict[str, Any] = {}
    if block_sdk:
        _purge("opentelemetry.sdk", "poisson_prove.otel", "poisson_prove.capture")
        sys.modules["opentelemetry.sdk"] = None  # type: ignore[assignment]
    if preset == "noop":
        from opentelemetry import trace

        trace.set_tracer_provider(trace.NoOpTracerProvider())
    elif preset == "sdk":
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        user = {"provider": provider, "exporter": exporter}

    from poisson_prove.capture import CaptureSpec, capture, install

    spec_kwargs = {"max_observation_bytes": DECLARED_LIMIT, **spec_kwargs}  # CD (D1)
    status = install(CaptureSpec(**spec_kwargs))
    second = install(CaptureSpec(**spec_kwargs)) if twice else None
    with capture(RUN_ID, "cfg-7:3") as recorder:
        with _tracer().start_as_current_span("probe") as span:
            span.set_attribute("server.address", "oracle")
    out: dict[str, Any] = {
        "status": status_dict(status),
        "second": None if second is None else status_dict(second),
        "meta": recorder.to_meta(),
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
        "logs": sink.records,
        "instrument_calls": getattr(sys.modules.get(FAKE_MODULE), "INSTRUMENTED", None),
    }
    if user:
        from opentelemetry import trace

        user["provider"].force_flush()
        out["global_is_user_provider"] = trace.get_tracer_provider() is user["provider"]
        out["user_exporter"] = [
            {"name": s.name, "attrs": dict(s.attributes or {})}
            for s in user["exporter"].get_finished_spans()
        ]
    return out


def child_capture_spans(
    spec_kwargs: dict[str, Any], spans: list[dict[str, Any]], reseed: int | None = None
) -> dict[str, Any]:
    """``install(CaptureSpec(**spec_kwargs))``, then one capture block emitting ``spans`` in
    order (``{"name", "attrs"}`` each), re-seeding the global ``random`` before every span
    when ``reseed`` is given. With ``reseed`` a second block first checks the global stream."""
    sink = watch_logs()
    from poisson_prove.capture import CaptureSpec, capture, install

    spec_kwargs = {"max_observation_bytes": DECLARED_LIMIT, **spec_kwargs}  # CD (D1)
    status = install(CaptureSpec(**spec_kwargs))
    tracer = _tracer()
    stream_untouched = None
    if reseed is not None:
        random.seed(reseed)
        expected = random.random()
        with capture(RUN_ID, "cfg-7:0"):
            random.seed(reseed)
            with tracer.start_as_current_span("stream-probe"):
                pass
            stream_untouched = random.random() == expected
    with capture(RUN_ID, "cfg-7:1") as recorder:
        for spec in spans:
            if reseed is not None:
                random.seed(reseed)
            with tracer.start_as_current_span(spec["name"]) as span:
                for key, value in spec.get("attrs", {}).items():
                    span.set_attribute(key, value)
    return {
        "status": status_dict(status),
        "meta": recorder.to_meta(),
        "stream_untouched": stream_untouched,
        "logs": sink.records,
    }


def child_nested_capture(spec_kwargs: dict[str, Any], depth: int) -> dict[str, Any]:
    """One capture block holding a chain of ``depth`` nested spans, ``depth-0`` outermost.
    Each start waits for the wall clock to tick, so start times are strictly increasing."""
    from poisson_prove.capture import CaptureSpec, capture, install

    spec_kwargs = {"max_observation_bytes": DECLARED_LIMIT, **spec_kwargs}  # CD (D1)
    status = install(CaptureSpec(**spec_kwargs))
    tracer = _tracer()
    with capture(RUN_ID, "cfg-7:1") as recorder:
        with ExitStack() as stack:
            for i in range(depth):
                tick = time.time_ns()
                while time.time_ns() == tick:
                    pass
                stack.enter_context(tracer.start_as_current_span(f"depth-{i}"))
    return {"status": status_dict(status), "meta": recorder.to_meta()}


def child_sequential_captures() -> dict[str, Any]:
    """Two episodes back to back in one process, plus a span opened in the first and closed
    inside the second."""
    from poisson_prove.capture import CaptureSpec, capture, install

    install(CaptureSpec(max_observation_bytes=DECLARED_LIMIT))  # CD (D1)
    tracer = _tracer()
    with capture(RUN_ID, "cfg-7:0") as first:
        with tracer.start_as_current_span("first-own"):
            pass
        late = tracer.start_span("first-late")
    with capture(RUN_ID, "cfg-7:1") as second:
        late.end()
        with tracer.start_as_current_span("second-own"):
            pass
    return {"first": first.to_meta(), "second": second.to_meta()}


def child_cli(argv: list[str], extra_path: str | None) -> dict[str, Any]:
    if extra_path is not None:
        sys.path.insert(0, extra_path)
    out, err = StringIO(), StringIO()
    code = cli.main(argv, stdout=out, stderr=err, stdin=StringIO())
    return {
        "code": code,
        "out": out.getvalue(),
        "err": err.getvalue(),
        "sdk_provider_in_this_process": _global_provider_is_sdk(),
    }


# ---------- C1: the parent must not set a global TracerProvider before forking ----------

C1_DRIVER = '''\
"""C1 driver: a real fork, both ways. ``python c1_driver.py set`` or ``... unset``."""

import json
import logging
import multiprocessing
import sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

PARENT_EXPORTER = InMemorySpanExporter()


class Sink(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def child(conn):
    sink = Sink()
    logging.getLogger().addHandler(sink)
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    with trace.get_tracer("child").start_as_current_span("in-child"):
        pass
    provider.force_flush()
    trace.get_tracer_provider().force_flush()
    conn.send(
        {
            "captured": [span.name for span in exporter.get_finished_spans()],
            "owns_global": trace.get_tracer_provider() is provider,
            "landed_in_parent_provider": [
                span.name for span in PARENT_EXPORTER.get_finished_spans()
            ],
            "messages": sink.messages,
        }
    )
    conn.close()


def main(parent_sets):
    if parent_sets:
        parent_provider = TracerProvider()
        parent_provider.add_span_processor(SimpleSpanProcessor(PARENT_EXPORTER))
        trace.set_tracer_provider(parent_provider)
    ctx = multiprocessing.get_context("fork")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=child, args=(child_conn,))
    proc.start()
    child_conn.close()
    result = parent_conn.recv()
    proc.join()
    print(json.dumps(result))


if __name__ == "__main__":
    main(sys.argv[1] == "set")
'''


def run_c1_driver(script: Path, way: str) -> dict[str, Any]:
    r = subprocess.run(
        [sys.executable, str(script), way],
        capture_output=True,
        text=True,
        timeout=60.0,
        cwd=script.parent,
    )
    assert r.returncode == 0, f"driver {way!r} failed:\n{r.stderr}"
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not FORK_AVAILABLE, reason="C1 is a fork hazard; needs the fork start method")
def test_c1_a_forked_child_captures_only_when_the_parent_set_no_provider(tmp_path: Path) -> None:
    script = write(tmp_path / "c1_driver.py", C1_DRIVER)

    unset = run_c1_driver(script, "unset")
    assert unset["captured"] == ["in-child"], unset
    assert unset["owns_global"] is True, unset
    assert not any(OVERRIDE_MESSAGE in m for m in unset["messages"]), unset["messages"]

    already_set = run_c1_driver(script, "set")
    assert already_set["captured"] == [], already_set
    assert already_set["owns_global"] is False, already_set
    assert any(OVERRIDE_MESSAGE in m for m in already_set["messages"]), already_set["messages"]
    # The span was not lost to nowhere: it went to the first provider, the parent's, whose
    # exporter the child inherited a copy of. Nothing crossed back to the real parent.
    assert already_set["landed_in_parent_provider"] == ["in-child"], already_set


def test_c1_install_reports_inactive_when_it_cannot_own_the_global_provider() -> None:
    r = isolated(child_install, {}, None, "noop")
    assert r["status"]["active"] is False, r["status"]
    assert r["status"]["requested"] is True
    assert isinstance(r["status"]["reason"], str) and r["status"]["reason"], r["status"]
    assert r["meta"] is None, r["meta"]
    assert r["sdk_provider_in_this_process"] is False


@pytest.mark.skipif(not FORK_AVAILABLE, reason="the timeout path needs the fork start method")
def test_c1_the_local_fork_path_installs_in_the_child_not_the_parent(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": []}))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:otel_rollout", SALT, 30.0, None)
    assert r["sdk_provider_in_this_process"] is False, "run_local installed in the forking parent"
    assert r["summary"]["n_ok"] == 4 and r["summary"]["n_timeout"] == 0, r["summary"]
    df = Store(tmp_path / "store").read(r["run_id"])
    for row in df.itertuples():
        trace = Trace.from_dict(row.meta["trace"])
        assert [s.attrs.get(RUN_ID_KEY) for s in trace.spans] == [r["run_id"]] * 2, row.config_hash


# ---------- C2: the capture provider does not use the global random ----------


def _reseeded_span_ids(n: int, seed: int) -> list[int]:
    """Span ids from a naive ``TracerProvider()`` when the global ``random`` is re-seeded
    before each span. A private provider, never the global one."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("oracle.naive")
    for i in range(n):
        random.seed(seed)
        with tracer.start_as_current_span(f"span-{i}"):
            pass
    provider.force_flush()
    return [span.context.span_id for span in exporter.get_finished_spans()]


def as_otlp(spans: Sequence[Any]) -> Any:
    """Finished ``ReadableSpan`` objects as the OTLP/JSON payload ``from_otel`` consumes."""
    pytest.importorskip(
        "opentelemetry.exporter.otlp.proto.common",
        reason="the OTLP encoder is a dev-only oracle, like lifelines",
    )
    from google.protobuf.json_format import MessageToDict

    try:
        from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    except ImportError:  # pragma: no cover - the module moved between SDK releases
        from opentelemetry.exporter.otlp.proto.common._internal.trace_encoder import (
            encode_spans,
        )
    return MessageToDict(encode_spans(list(spans)))


def test_c2_a_naive_provider_reseeded_between_spans_repeats_its_span_ids() -> None:
    ids = _reseeded_span_ids(10, 1234)
    assert len(ids) == 10 and len(set(ids)) == 1, ids


def test_c2_from_otel_drops_the_repeated_ids_as_duplicates() -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from poisson_prove.trace import from_otel

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("oracle.naive")
    for i in range(10):
        random.seed(1234)
        with tracer.start_as_current_span(f"span-{i}"):
            pass
    provider.force_flush()
    trace = from_otel(as_otlp(exporter.get_finished_spans()))
    assert (len(trace.spans), trace.dropped) == (1, 9)


def test_c2_capture_ids_stay_distinct_when_the_global_random_is_reseeded() -> None:
    spans = [{"name": f"span-{i}"} for i in range(10)]
    r = isolated(child_capture_spans, {}, spans, 1234)
    assert r["status"]["active"] is True, r["status"]
    trace = Trace.from_dict(r["meta"])
    assert trace.dropped == 0 and len(trace.spans) == 10, r["meta"]
    assert len({s.span_id for s in trace.spans}) == 10, [s.span_id for s in trace.spans]
    assert not warnings_under_proofload(r["logs"]), r["logs"]


def test_c2_capture_never_draws_from_the_global_random() -> None:
    r = isolated(child_capture_spans, {}, [{"name": "one"}], 1234)
    assert r["stream_untouched"] is True, "a span consumed bits from the global random stream"


# ---------- C2a: installing a provider is permanent ----------


def test_c2a_the_sdk_provider_has_no_remove_span_processor() -> None:
    from opentelemetry.sdk.trace import TracerProvider

    assert hasattr(TracerProvider, "add_span_processor")
    assert not hasattr(TracerProvider, "remove_span_processor")


def test_c2a_install_adds_its_processors_to_a_user_provider_and_leaves_their_exporter_alone() -> None:
    r = isolated(child_install, {}, None, "sdk")
    assert r["status"]["active"] is True, r["status"]
    assert r["global_is_user_provider"] is True, "install() replaced the user's provider"
    assert not any(OVERRIDE_MESSAGE in m for _, _, m in r["logs"]), r["logs"]
    # Their exporter still sees every span, now stamped: the stamper was added to theirs.
    assert [s["name"] for s in r["user_exporter"]] == ["probe"], r["user_exporter"]
    assert r["user_exporter"][0]["attrs"][RUN_ID_KEY] == RUN_ID
    assert r["user_exporter"][0]["attrs"][EPISODE_KEY] == "cfg-7:3"
    # And so does the capture.
    trace = Trace.from_dict(r["meta"])
    assert names(r["meta"]) == ["probe"] and trace.source == "otel"


def test_c2a_install_is_once_per_process() -> None:
    r = isolated(child_install, {}, None, None, False, True)
    assert r["status"]["active"] is True and r["second"] is not None
    assert r["second"]["active"] is True, r["second"]
    # A second install() must not add a second collector: one span emitted, one captured.
    trace = Trace.from_dict(r["meta"])
    assert names(r["meta"]) == ["probe"] and trace.dropped == 0


# ---------- C3: capture is off unless requested ----------


def test_c3_no_capture_table_means_no_trace_and_no_otel_import_on_the_local_path(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture=None))
    r = isolated(child_run_without_capture, str(tmp_path / "store"), str(toml), f"{MODULE}:plain_rollout", SALT, False)
    assert r["opentelemetry_modules"] == [], r["opentelemetry_modules"]
    assert r["otel_helper_loaded"] is False
    df = Store(tmp_path / "store").read(r["run_id"])
    assert len(df) == 4 and df["error"].isna().all()
    assert all("trace" not in meta for meta in df["meta"]), list(df["meta"])
    record = Store(tmp_path / "store").manifest(r["run_id"]).environment.get("capture")
    if record is not None:
        assert record["requested"] is False and record["active"] is False, record


def test_c3_no_capture_means_no_trace_and_no_otel_import_in_worker_batch(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture=None))
    r = isolated(child_run_without_capture, str(tmp_path / "store"), str(toml), f"{MODULE}:plain_rollout", SALT, True)
    assert r["opentelemetry_modules"] == [], r["opentelemetry_modules"]
    assert r["otel_helper_loaded"] is False
    assert len(r["results"]) == 4
    for result in r["results"]:
        assert isinstance(result, dict) and "trace" not in result["meta"], result


# ---------- C4: install() never raises ----------


def test_c4_a_missing_sdk_yields_an_inactive_status_with_a_reason() -> None:
    r = isolated(child_install, {}, None, None, True)
    assert r["status"]["active"] is False and r["status"]["requested"] is True, r["status"]
    assert "opentelemetry" in str(r["status"]["reason"]).lower(), r["status"]
    assert r["meta"] is None


def test_c4_an_unknown_instrumentor_name_yields_an_inactive_status_naming_it(tmp_path: Path) -> None:
    fake = register_fake_instrumentors(tmp_path / "fake")
    r = isolated(child_install, {"instrument": (FAKE_INSTRUMENTOR, UNKNOWN_INSTRUMENTOR)}, str(fake))
    assert r["status"]["active"] is False, r["status"]
    assert UNKNOWN_INSTRUMENTOR in str(r["status"]["reason"]), r["status"]
    assert r["meta"] is None


def test_c4_an_instrumentor_raising_a_dependency_conflict_yields_an_inactive_status(tmp_path: Path) -> None:
    fake = register_fake_instrumentors(tmp_path / "fake")
    r = isolated(child_install, {"instrument": (CONFLICT_INSTRUMENTOR,)}, str(fake))
    assert r["status"]["active"] is False, r["status"]
    reason = str(r["status"]["reason"])
    assert CONFLICT_INSTRUMENTOR in reason or "oracle-lib" in reason or "DependencyConflict" in reason, reason
    assert r["meta"] is None


def test_c4_a_named_instrumentor_is_activated_and_recorded(tmp_path: Path) -> None:
    fake = register_fake_instrumentors(tmp_path / "fake")
    r = isolated(child_install, {"instrument": (FAKE_INSTRUMENTOR,)}, str(fake))
    assert r["status"] == {"requested": True, "active": True, "reason": None, "instrumented": [FAKE_INSTRUMENTOR]}, r["status"]
    assert r["instrument_calls"] is not None and len(r["instrument_calls"]) == 1, r["instrument_calls"]
    assert names(r["meta"]) == ["probe"]


def test_c4_the_reason_reaches_the_manifest_and_the_run_proceeds(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": [UNKNOWN_INSTRUMENTOR]}))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:otel_rollout", SALT, None, None)
    assert r["summary"]["n_ok"] == 4 and r["summary"]["complete"] is True, r["summary"]
    store = Store(tmp_path / "store")
    record = store.manifest(r["run_id"]).environment["capture"]
    assert record["requested"] is True and record["active"] is False, record
    assert UNKNOWN_INSTRUMENTOR in str(record["reason"]), record
    df = store.read(r["run_id"])
    assert df["error"].isna().all()
    assert all("trace" not in meta for meta in df["meta"]), "an inactive capture stored a trace"


def test_c4_the_manifest_records_the_whole_capture_request(tmp_path: Path) -> None:
    fake = register_fake_instrumentors(tmp_path / "fake")
    table = {"instrument": [FAKE_INSTRUMENTOR], "content": True, "max_observation_bytes": 4096, "max_spans": 50}
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture=table))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:otel_rollout", SALT, None, str(fake))
    record = Store(tmp_path / "store").manifest(r["run_id"]).environment["capture"]
    assert set(record) == MANIFEST_KEYS, sorted(record)
    assert record["requested"] is True and record["active"] is True and record["reason"] is None, record
    assert record["instrumented"] == [FAKE_INSTRUMENTOR]
    assert record["semconv"] == OTEL_SEMCONV_VERSION
    assert (record["content"], record["max_observation_bytes"], record["max_spans"]) == (True, 4096, 50)


# ---------- C5: every row of a local run carries a stamped trace ----------


def assert_stamped_rows(df: Any, run_id: str) -> None:
    assert len(df) == 4 and df["error"].isna().all()
    for row in df.itertuples():
        trace = Trace.from_dict(row.meta["trace"])
        assert trace.source == "otel" and trace.dropped == 0, row.meta["trace"]
        assert sorted(s.name for s in trace.spans) == sorted([f"invoke_agent {row.seed}", f"chat {row.seed}"])
        for span in trace.spans:
            assert span.attrs[RUN_ID_KEY] == run_id, (span.name, span.attrs)
            assert span.attrs[EPISODE_KEY] == episode_id(row.config_hash, row.replicate_index), (span.name, span.attrs)
        assert {s.kind for s in trace.spans} == {"agent", "llm"} and len(trace.roots()) == 1


@pytest.mark.parametrize(
    "episode_timeout",
    [
        None,
        pytest.param(30.0, marks=pytest.mark.skipif(not FORK_AVAILABLE, reason="needs fork")),
    ],
    ids=["no-timeout", "fork"],
)
def test_c5_every_row_of_a_local_run_carries_a_stamped_trace(tmp_path: Path, episode_timeout: float | None) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": []}))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:otel_rollout", SALT, episode_timeout, None)
    assert r["summary"]["n_ok"] == 4 and r["summary"]["complete"] is True, r["summary"]
    store = Store(tmp_path / "store")
    assert_stamped_rows(store.read(r["run_id"]), r["run_id"])
    record = store.manifest(r["run_id"]).environment["capture"]
    assert record["requested"] is True, record
    if episode_timeout is None:
        assert record["active"] is True, record
        assert r["sdk_provider_in_this_process"] is True, "the no-timeout path runs in the caller's process"


# ---------- C6: the same holds for the Modal backend, both worker_batch branches ----------


def capture_payload(run_id: str, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"run_id": run_id, "instrument": [], "content": False, "max_observation_bytes": 8192, "max_spans": 1000}  # A8b: the renamed transport field
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "episode_timeout",
    [
        None,
        pytest.param(30.0, marks=pytest.mark.skipif(not FORK_AVAILABLE, reason="needs fork")),
    ],
    ids=["no-timeout", "fork"],
)
def test_c6_worker_batch_carries_stamped_traces_in_both_branches(tmp_path: Path, episode_timeout: float | None) -> None:
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), Store(tmp_path / "store"), run_salt=SALT)
    jobs = jobs_of(p)
    r = isolated(child_worker_batch, jobs, f"{MODULE}:otel_rollout", episode_timeout, capture_payload(RUN_ID))
    results = r["results"]
    assert len(results) == len(jobs) == 4
    for job, result in zip(jobs, results, strict=True):
        _, seed, i, config_hash, replicate_index = job
        assert isinstance(result, dict), result
        assert result["backend_meta"]["i"] == i
        trace = Trace.from_dict(result["meta"]["trace"])
        assert trace.source == "otel" and trace.dropped == 0
        assert sorted(s.name for s in trace.spans) == sorted([f"invoke_agent {seed}", f"chat {seed}"])
        for span in trace.spans:
            assert span.attrs[RUN_ID_KEY] == RUN_ID, (span.name, span.attrs)
            assert span.attrs[EPISODE_KEY] == episode_id(config_hash, replicate_index), (span.name, span.attrs)
        # Section 3: the per-batch backend_meta["capture"] carries what happened in the container.
        status = result["backend_meta"]["capture"]
        assert set(STATUS_FIELDS) <= set(status) and status["active"] is True, status
    if episode_timeout is not None:
        assert r["sdk_provider_in_this_process"] is False, "worker_batch installed in the forking parent"
    else:
        assert r["sdk_provider_in_this_process"] is True


# ---------- C7: collision with a rollout that already wrote meta["trace"] ----------


def test_c7_rule_zero_the_mock_agent_trace_is_byte_identical_with_capture_on_and_off(tmp_path: Path) -> None:
    off_toml = write(tmp_path / "off.toml", mock_toml(capture=None))
    on_toml = write(tmp_path / "on.toml", mock_toml(capture={"instrument": []}))
    off = isolated(child_run_local, str(tmp_path / "off"), str(off_toml), MOCK_ROLLOUT, SALT, None, None)
    on = isolated(child_run_local, str(tmp_path / "on"), str(on_toml), MOCK_ROLLOUT, SALT, None, None)
    assert Store(tmp_path / "on").manifest(on["run_id"]).environment["capture"]["active"] is True
    assert on["summary"]["n_ok"] == off["summary"]["n_ok"] == 24

    stored_off = raw_meta(tmp_path / "off", off["run_id"])
    stored_on = raw_meta(tmp_path / "on", on["run_id"])
    assert len(stored_on) == 24 and set(stored_on) == set(stored_off)
    for key in stored_off:
        assert stored_on[key] == stored_off[key], key
    # A7 (spec section 3.2, P7-2): the trace is stored beside ``meta``, not inside it, so the
    # rollout's own trace is read back through the store's full read, where ``meta["trace"]`` is
    # reassembled. Amended from a ``json.loads`` of the raw ``meta`` cell, which no longer carries
    # the key; the raw byte identity above is rule zero's own clause and is unchanged.
    for row in Store(tmp_path / "on").read(on["run_id"]).itertuples(index=False):
        assert row.meta["trace"]["source"] == "record" and Trace.from_dict(row.meta["trace"]).dropped == 0
    assert not warnings_under_proofload(on["logs"]), on["logs"]


def test_c7_a_valid_user_trace_gets_the_capture_merged_in(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": []}, axes={"x": [0.1]}))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:recording_rollout", SALT, None, None)
    df = Store(tmp_path / "store").read(r["run_id"])
    assert len(df) == 2 and df["error"].isna().all()
    for row in df.itertuples():
        trace = Trace.from_dict(row.meta["trace"])
        assert trace.source == "mixed" and trace.dropped == 0, row.meta["trace"]
        by_name = {s.name: s for s in trace.spans}
        assert set(by_name) == {"recorded-tool", f"chat {row.seed}"}, sorted(by_name)
        recorded, captured = by_name["recorded-tool"], by_name[f"chat {row.seed}"]
        assert recorded.span_id == f"{row.seed:016x}" and recorded.attrs == {"attempts": 1}
        assert captured.kind == "llm"
        assert captured.attrs[RUN_ID_KEY] == r["run_id"]
        assert captured.attrs[EPISODE_KEY] == episode_id(row.config_hash, row.replicate_index)


def test_c7_a_span_id_collision_keeps_the_user_trace_drops_the_capture_and_warns_once(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": []}, replicates=1, axes={"x": [0.1]}))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:colliding_rollout", SALT, None, None)
    assert r["summary"]["n_ok"] == 1 and r["summary"]["n_errored"] == 0, r["summary"]
    df = Store(tmp_path / "store").read(r["run_id"])
    row = df.iloc[0]
    assert row["error"] is None and row["outcome"] in ("fell", "survived")
    trace = Trace.from_dict(row["meta"]["trace"])
    assert trace.source == "record" and len(trace.spans) == 1 and trace.dropped == 0
    assert trace.spans[0].name == "recorded-tool" and trace.spans[0].attrs == {"attempts": 1}
    warned = warnings_under_proofload(r["logs"])
    assert len(warned) == 1, r["logs"]


def test_c7_an_invalid_user_trace_is_left_exactly_as_the_rollout_wrote_it(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": []}, replicates=1, axes={"shape": ["list", "dict"]}))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:garbage_trace_rollout", SALT, None, None)
    assert r["summary"]["n_ok"] == 2 and r["summary"]["n_errored"] == 0, r["summary"]
    store = Store(tmp_path / "store")
    assert store.manifest(r["run_id"]).environment["capture"]["active"] is True, "capture was not on"
    df = store.read(r["run_id"])
    assert len(df) == 2 and df["error"].isna().all()
    for row in df.itertuples():
        shape = str(row.config["shape"])
        assert row.meta == {"trace": GARBAGE_TRACES[shape], "k": 1}, (shape, row.meta)


# ---------- C8: the transport does not change shape ----------


def test_c8_worker_batch_keeps_three_positional_parameters_and_adds_only_capture() -> None:
    params = list(inspect.signature(worker_batch).parameters.values())
    assert [p.name for p in params[:3]] == ["jobs", "import_path", "episode_timeout"]
    for p in params[:3]:
        assert p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD), p
    added = params[3:]
    # M11a: the rule is one keyword-only, None-defaulted parameter per seam (Spec M11 section 0.1)
    assert [p.name for p in added] == ["capture", "chaos"], [p.name for p in added]
    for p in added:
        assert p.kind is p.KEYWORD_ONLY and p.default is None, p


def test_c8_job_result_outcome_mapper_and_from_episode_are_unchanged() -> None:
    assert Job == tuple[dict[str, Any], int, int, str, int]
    assert Result == dict[str, Any] | str
    assert executor._Outcome == tuple[str, Any]
    assert Mapper == Callable[[Sequence[Sequence[Job]]], Iterator[tuple[int, list[Result] | BaseException]]]
    assert list(inspect.signature(EpisodeRecord.from_episode).parameters) == [
        "ep", "run_id", "config", "seed", "replicate_index", "wall_time", "backend_meta",
    ]


def test_c8_the_existing_positional_call_still_works(tmp_path: Path) -> None:
    p = plan(SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(capture=None))), Store(tmp_path / "store"), run_salt=SALT)
    jobs = jobs_of(p)
    results = worker_batch(jobs, f"{MODULE}:plain_rollout", None)
    assert len(results) == len(jobs) == 4
    for job, result in zip(jobs, results, strict=True):
        assert isinstance(result, dict) and result["backend_meta"]["i"] == job[2], result
        assert result["outcome"] == _outcome(job[0], job[1]) and "trace" not in result["meta"]
    assert not _global_provider_is_sdk(), "a positional call without capture installed a provider"


# ---------- C9: content capture off by default ----------

CONTENT_ATTRS = {
    "gen_ai.input.messages": json.dumps([{"role": "user", "content": "plan the refund"}]),
    "gen_ai.output.messages": json.dumps([{"role": "assistant", "content": "lookup_order first"}]),
    "server.address": "api.example",
}


def test_c9_content_is_off_by_default_in_the_spec() -> None:
    from poisson_prove.capture import CaptureSpec

    # CD (D1): ``content`` keeps its default; only the cap loses one.
    assert CaptureSpec(max_observation_bytes=DECLARED_LIMIT).content is False


def test_c9_content_attributes_are_stripped_when_content_is_off() -> None:
    r = isolated(child_capture_spans, {}, [{"name": "chat", "attrs": CONTENT_ATTRS}])
    assert r["status"]["active"] is True
    (span,) = Trace.from_dict(r["meta"]).spans
    for key in GENAI_CONTENT_KEYS:
        assert key not in span.attrs, (key, span.attrs)
    assert span.attrs["server.address"] == "api.example"
    assert span.attrs[RUN_ID_KEY] == RUN_ID and span.attrs[EPISODE_KEY] == "cfg-7:1"


def test_c9_content_attributes_survive_when_content_is_on() -> None:
    r = isolated(child_capture_spans, {"content": True}, [{"name": "chat", "attrs": CONTENT_ATTRS}])
    (span,) = Trace.from_dict(r["meta"]).spans
    for key in GENAI_CONTENT_KEYS:
        assert span.attrs[key] == CONTENT_ATTRS[key], (key, span.attrs)


# ---------- C10: the cut (A8b; was the size budget), asserted against attrs ----------


def test_c10_an_oversized_observation_value_is_stored_head_and_tail_in_attrs() -> None:
    """A8b (spec section 7.1 group 4): was ``..._has_its_offending_attribute_replaced_by_a_marker_in_attrs``.
    The marker, the per-span total and C30's wording are retired; the unit is one observation value
    and the bounds are the limit's split (ADR-082): 768 + 256 at 1024. The per-span ``<= 1024``
    clause is deleted, not ported -- the wrapper alone holds 1,024 bytes of content plus its keys."""
    giant = json.dumps([{"role": "user", "content": "x" * 8192}])
    assert len(giant.encode("utf-8")) == 8225 and giant.isascii()
    attrs = {"gen_ai.input.messages": giant, "gen_ai.output.messages": "[]", "server.address": "api.example"}
    r = isolated(child_capture_spans, {"content": True, "max_observation_bytes": 1024}, [{"name": "chat", "attrs": attrs}])
    (span,) = Trace.from_dict(r["meta"]).spans
    # from_otel never populates these two on a captured span; the cut itself covers both fields.
    assert span.input is None and span.output is None
    wrapper = span.attrs["gen_ai.input.messages"]
    assert isinstance(wrapper, dict) and set(wrapper) == {"poisson_prove.truncated"}, wrapper
    cut = wrapper["poisson_prove.truncated"]
    assert set(cut) == {"head", "tail", "bytes_original"}, sorted(cut)
    assert cut["head"] == giant[:768] and cut["tail"] == giant[-256:] and cut["bytes_original"] == 8225, cut
    assert span.truncated == "observation" and span.bytes_original == 8225, (span.truncated, span.bytes_original)
    # Only the over-limit value is cut; small values and the routing stamps are stored whole.
    assert span.attrs["gen_ai.output.messages"] == "[]" and span.attrs["server.address"] == "api.example"
    assert span.attrs[RUN_ID_KEY] == RUN_ID and span.attrs[EPISODE_KEY] == "cfg-7:1"


def test_c10_the_cut_runs_when_content_is_off() -> None:
    """A8b (spec section 7.1 group 4): was ``test_c10_the_budget_is_inert_when_content_is_off``, whose
    name stated the behaviour A8b inverts. Spec section 0.4's worked case: A6's absolute constants
    would store ``"y" * 300`` as both head and tail; the limit's split stores 48 + 16."""
    big = "y" * 300
    r = isolated(child_capture_spans, {"max_observation_bytes": 64}, [{"name": "chat", "attrs": {"big.attribute": big}}])
    (span,) = Trace.from_dict(r["meta"]).spans
    assert span.attrs["big.attribute"] == {"poisson_prove.truncated": {"head": "y" * 48, "tail": "y" * 16, "bytes_original": 300}}, span.attrs
    assert 48 + 16 <= 64 < 300
    assert span.truncated == "observation" and span.bytes_original == 300, (span.truncated, span.bytes_original)


def test_c10_spans_beyond_max_spans_are_dropped_and_counted() -> None:
    spans = [{"name": f"s{i}"} for i in range(5)]
    r = isolated(child_capture_spans, {"max_spans": 3}, spans)
    trace = Trace.from_dict(r["meta"])
    assert len(trace.spans) == 3 and trace.dropped == 2, r["meta"]
    assert names(r["meta"]) == ["s0", "s1", "s2"]


def test_c10_max_spans_keeps_the_earliest_started_spans_and_drops_the_deepest() -> None:
    """Spans end innermost-first, so a cap applied as spans end keeps the leaves and loses the
    root. C10 (amended 2026-09-05) caps in start order: the root and its first descendants
    survive, the deepest spans are the ones dropped."""
    r = isolated(child_nested_capture, {"max_spans": 3}, 5)
    trace = Trace.from_dict(r["meta"])
    assert len(trace.spans) == 3 and trace.dropped == 2, r["meta"]
    assert names(r["meta"]) == ["depth-0", "depth-1", "depth-2"]
    assert [s.name for s in trace.roots()] == ["depth-0"]
    assert trace.children(trace.roots()[0].span_id)[0].name == "depth-1"


# ---------- C11: two episodes in one process stay apart ----------


def test_c11_two_episodes_in_one_process_keep_their_spans_apart(tmp_path: Path) -> None:
    toml = write(tmp_path / "sweep.toml", sweep_toml(capture={"instrument": []}))
    r = isolated(child_run_local, str(tmp_path / "store"), str(toml), f"{MODULE}:otel_rollout", SALT, None, None)
    df = Store(tmp_path / "store").read(r["run_id"])
    assert len(df) == 4
    episodes: list[str] = []
    for row in df.itertuples():
        trace = Trace.from_dict(row.meta["trace"])
        assert {s.name.split(" ")[1] for s in trace.spans} == {str(row.seed)}, "a span from another episode leaked in"
        stamps = {s.attrs[EPISODE_KEY] for s in trace.spans}
        assert stamps == {episode_id(row.config_hash, row.replicate_index)}, stamps
        episodes.extend(stamps)
    assert len(set(episodes)) == 4, episodes


def test_c11_a_span_closing_after_its_episode_falls_on_the_floor() -> None:
    r = isolated(child_sequential_captures)
    assert names(r["second"]) == ["second-own"], r["second"]
    assert r["first"] is None or names(r["first"]) == ["first-own"], r["first"]
    if r["first"] is not None:
        first = Trace.from_dict(r["first"]).spans[0].attrs[EPISODE_KEY]
        second = Trace.from_dict(r["second"]).spans[0].attrs[EPISODE_KEY]
        assert (first, second) == ("cfg-7:0", "cfg-7:1")


# ---------- C12: the pre-flight names what will be activated ----------


def capture_lines(out: str) -> tuple[list[str], list[int]]:
    lines = out.splitlines()
    # The pre-flight lines now follow the plan line and may be indented (spec section 5.3).
    return lines, [i for i, line in enumerate(lines) if line.lstrip().startswith("Capture:")]


class LoggedStringIO(StringIO):
    """A StringIO that also appends every write to a log shared with another stream, so the
    order of writes across stdout and stderr can be read back."""

    def __init__(self, log: list[str]) -> None:
        super().__init__()
        self.log = log

    def write(self, s: str) -> int:
        self.log.append(s)
        return super().write(s)


#: These fixtures are two-cell plumbing grids, not powered designs: N is 1, 2 or 4 and
#: the MDE saturates at 0.5. S23 gates a sweep on that number, so every end-to-end
#: invocation here states what it accepts. The flag is the honest answer -- these runs
#: really can only see a fifty-point move -- and it is what the gate exists to make
#: people say out loud.
# PF4 re-freeze (PF4.30, reading R17): at 1, 2 or 4 replicates a side no lone condition of these
# grids can be flagged at q / M, so any accepted change below 1 refuses them (no fifty-point limit
# exists any more); --max-mde 1 admits any design, which is what 0.5 did here.
PLUMBING_MAX_MDE = ("--max-mde", "1")


def test_c12_preflight_prints_one_capture_line_before_the_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(register_fake_instrumentors(tmp_path / "fake")))
    toml = write(tmp_path / "sweep.toml", mock_toml(capture={"instrument": [FAKE_INSTRUMENTOR]}))
    log: list[str] = []
    out, err = LoggedStringIO(log), LoggedStringIO(log)
    code = cli.main(
        ["--store", str(tmp_path / "store"), "sweep", str(toml), "--target", MOCK_ROLLOUT,
         *PLUMBING_MAX_MDE],
        stdout=out, stderr=err, stdin=TtyStringIO("n\n"),
    )
    # Declining is a refusal and exits 1 (spec section 5.2).
    assert code == 1 and "Traceback" not in out.getvalue() + err.getvalue()
    lines, found = capture_lines(out.getvalue())
    assert len(found) == 1, out.getvalue()
    assert FAKE_INSTRUMENTOR in lines[found[0]], lines[found[0]]
    # The question now goes to stderr (spec section 5.3); the shared log keeps the order of
    # both streams, so the capture line is still checked to come before it.
    assert "[y/N]" in err.getvalue(), err.getvalue()
    both = "".join(log).splitlines()
    capture_at = [i for i, line in enumerate(both) if line.lstrip().startswith("Capture:")]
    prompt = [i for i, line in enumerate(both) if "[y/N]" in line]
    assert capture_at and prompt and capture_at[0] < prompt[0], "".join(log)
    assert Store(tmp_path / "store").runs() == []
    assert not _global_provider_is_sdk(), "a declined pre-flight installed a provider"


def test_c12_yes_does_not_suppress_the_capture_line(tmp_path: Path) -> None:
    fake = register_fake_instrumentors(tmp_path / "fake")
    toml = write(tmp_path / "sweep.toml", mock_toml(capture={"instrument": [FAKE_INSTRUMENTOR]}, replicates=1))
    argv = ["--store", str(tmp_path / "store"), "sweep", str(toml), "--target", MOCK_ROLLOUT, "--yes",
            *PLUMBING_MAX_MDE]
    r = isolated(child_cli, argv, str(fake))
    assert r["code"] == 0, r["out"] + r["err"]
    lines, found = capture_lines(r["out"])
    assert len(found) == 1, r["out"]
    assert FAKE_INSTRUMENTOR in lines[found[0]]
    # The sweep now ends with a verdict line, not 'run_id: <id>' (spec section 5.3); the capture
    # line still comes before the end, and the run is the one the empty store gained.
    done_line = [i for i, line in enumerate(lines) if line.startswith("done")]
    assert done_line and found[0] < done_line[0], r["out"]
    (run_id,) = Store(tmp_path / "store").runs()
    record = Store(tmp_path / "store").manifest(run_id).environment["capture"]
    assert record["active"] is True and record["instrumented"] == [FAKE_INSTRUMENTOR], record


def test_c12_the_modal_preflight_prints_the_capture_line_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    def fake_run_modal(p: Any, target: Any, store: Any, *, options: Any = None, on_progress: Any = None) -> RunSummary:
        calls.append(p)
        return RunSummary(run_id=p.run_id, n_ok=len(p.pairs), n_errored=0, n_timeout=0, wall_time=0.0, stopped_by=None, complete=True)

    # A missing modal package is now refused before the plan, so modal must import here.
    monkeypatch.setitem(sys.modules, "modal", importlib.util.module_from_spec(importlib.machinery.ModuleSpec("modal", None)))
    # PF5 (spec section 17; PF5.7): the face runs no backend; the core calls the Modal runner, so
    # the stand-in replaces it where it is defined, which the core reads when it runs a plan.
    monkeypatch.setattr(importlib.import_module("poisson_prove.executor_modal"), "run_modal", fake_run_modal)
    monkeypatch.syspath_prepend(str(register_fake_instrumentors(tmp_path / "fake")))
    toml = write(tmp_path / "sweep.toml", mock_toml(capture={"instrument": [FAKE_INSTRUMENTOR]}, replicates=1))
    out, err = StringIO(), StringIO()
    code = cli.main(
        ["--store", str(tmp_path / "store"), "sweep", str(toml), "--target", MOCK_ROLLOUT, "--backend", "modal", "--yes",
         *PLUMBING_MAX_MDE],
        stdout=out, stderr=err, stdin=StringIO(),
    )
    assert code == 0 and len(calls) == 1, out.getvalue() + err.getvalue()
    lines, found = capture_lines(out.getvalue())
    assert len(found) == 1 and FAKE_INSTRUMENTOR in lines[found[0]], out.getvalue()
    assert not _global_provider_is_sdk(), "the host installed a provider for a Modal run"


# ---------- section 2: the public interface ----------


def test_section_2_public_surface_is_exactly_five_symbols() -> None:
    import poisson_prove.capture as capture_module

    exported = getattr(capture_module, "__all__", None)
    if exported is not None:
        assert set(exported) == PUBLIC_SURFACE, sorted(exported)
    defined = {
        name
        for name, obj in vars(capture_module).items()
        if not name.startswith("_") and getattr(obj, "__module__", None) == "poisson_prove.capture"
    }
    assert defined == PUBLIC_SURFACE, sorted(defined)


def test_section_2_capture_spec_fields_defaults_and_frozenness() -> None:
    from poisson_prove.capture import CaptureSpec

    assert tuple(f.name for f in dataclasses.fields(CaptureSpec)) == SPEC_FIELDS
    with pytest.raises(TypeError):
        CaptureSpec()  # type: ignore[call-arg]  # CD (D1): the cap has no default
    spec = CaptureSpec(max_observation_bytes=DECLARED_LIMIT)
    assert (spec.instrument, spec.content, spec.max_observation_bytes, spec.max_spans) == ((), False, 8192, None)  # A8b: the rename, and D6's cap off by default
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.content = True  # type: ignore[misc]


def test_section_2_capture_status_fields_and_frozenness() -> None:
    from poisson_prove.capture import CaptureStatus

    assert tuple(f.name for f in dataclasses.fields(CaptureStatus)) == STATUS_FIELDS
    status = CaptureStatus(requested=False, active=False, reason=None, instrumented=())
    with pytest.raises(dataclasses.FrozenInstanceError):
        status.active = True  # type: ignore[misc]


def test_section_2_capture_is_a_context_manager_yielding_a_recorder() -> None:
    from poisson_prove.capture import Recorder, capture, install

    assert list(inspect.signature(capture).parameters) == ["run_id", "episode_id"]
    assert list(inspect.signature(install).parameters) == ["spec"]
    assert callable(getattr(Recorder, "to_meta", None))
    assert isinstance(capture(RUN_ID, "cfg-7:0"), AbstractContextManager)


def test_section_2_capture_module_imports_opentelemetry_lazily() -> None:
    r = isolated(child_import_capture_clean)
    assert r["opentelemetry_modules"] == [], r["opentelemetry_modules"]
    assert r["otel_helper_loaded"] is False


def module_scope_imports(path: Path) -> set[str]:
    """Import targets at module scope, descending into if/try/with but not into functions,
    classes or ``if TYPE_CHECKING:`` blocks."""
    found: set[str] = set()

    def is_type_checking(test: ast.expr) -> bool:
        return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )

    def visit(nodes: Sequence[ast.stmt]) -> None:
        for node in nodes:
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
                found.add(node.module)
            elif isinstance(node, ast.If):
                if not is_type_checking(node.test):
                    visit(node.body)
                visit(node.orelse)
            elif isinstance(node, ast.Try):
                visit(node.body)
                for handler in node.handlers:
                    visit(handler.body)
                visit(node.orelse)
                visit(node.finalbody)
            elif isinstance(node, (ast.With, ast.For, ast.While)):
                visit(node.body)

    visit(ast.parse(path.read_text(encoding="utf-8")).body)
    return found


def test_section_2_no_touched_module_imports_opentelemetry_at_module_scope() -> None:
    assert (PACKAGE / "capture.py").is_file(), f"{PACKAGE / 'capture.py'} does not exist"
    for name in TOUCHED_FILES:
        imports = module_scope_imports(PACKAGE / name)
        offending = {m for m in imports if m.split(".")[0] == "opentelemetry" or m == "poisson_prove.otel"}
        assert offending == set(), (name, sorted(offending))
