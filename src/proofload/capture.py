"""M3: in-process trace capture — the wire from a rollout's spans into ``Episode.meta``.

M12 shipped the schema, the converters and the episode stamper; nothing carried a trace into
an ``Episode``. This module is the missing half: it activates the instrumentors the user named
in their sweep file, owns (or joins) the process's ``TracerProvider``, and hands the executor
one ``Trace.to_dict()`` per episode.

``opentelemetry`` is imported **lazily, inside** ``install()`` — never at module scope, and
``proofload.otel`` with it, since that module imports the SDK at import time. ``executor.py``
can therefore import this file unconditionally and M12's T27 still holds: a run with no
``[capture]`` table imports no OpenTelemetry module at all.

Three facts drive the design, all of them measured (spec §4):

* **C1** A ``TracerProvider`` set in a forking parent makes the child's ``set_tracer_provider``
  a refused no-op, so the child captures nothing, silently. ``install()`` verifies it owns —
  or was added to — the global provider and reports ``active=False`` otherwise; on the forking
  paths the executor calls it in the child.
* **C2** OTel's default ``RandomIdGenerator`` draws from the global ``random``, which Proofload's
  own seeds collide. The provider this module builds carries an id generator seeded from
  ``os.urandom`` and never touches the global stream.
* **C2a** Installing a provider is permanent: there is no ``remove_span_processor`` and
  ``set_tracer_provider`` refuses a second call. Where the user already set an SDK provider we
  **add** our two processors to theirs and leave their exporters alone; ``install()`` is once
  per process and a second call adds no second collector.

ADR-027: only instrumentors the user named are activated, resolved through the
``opentelemetry_instrumentor`` entry-point group. No auto-discovery, no import hook, no wrapper
of our own. An unknown name, a missing SDK or an instrumentor that raises all yield
``CaptureStatus(active=False, reason=...)`` and the run proceeds.
"""

from __future__ import annotations

import json
import logging
import os
import random
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from proofload.trace import Trace, from_otel

if TYPE_CHECKING:  # imports for typing only; the runtime import lives in install()
    from opentelemetry.sdk.trace import ReadableSpan, TracerProvider

__all__ = ["CaptureSpec", "CaptureStatus", "Recorder", "capture", "install"]

_LOG = logging.getLogger(__name__)

#: The group every ``opentelemetry-instrumentation-*`` package registers under. The only place
#: an instrumentor name is resolved; discovering the group's other members is forbidden.
_ENTRY_POINT_GROUP = "opentelemetry_instrumentor"

#: Prompt and completion content, which never leaves the process unless ``content`` is on. The
#: two GenAI semconv keys, plus the vendor spellings M12 already reads traces from.
_CONTENT_KEYS = frozenset({"gen_ai.input.messages", "gen_ai.output.messages"})
_CONTENT_PREFIXES = (
    "gen_ai.prompt",
    "gen_ai.completion",
    "traceloop.entity.input",
    "traceloop.entity.output",
)

_TRUNCATION_MARKER = "<proofload: {n} bytes over max_span_bytes, value dropped>"

# ---------- process state: one provider, one collector, one status ----------

_LOCK = threading.Lock()
_STATUS: CaptureStatus | None = None
_BUCKET: _Bucket | None = None


@dataclass(frozen=True)
class CaptureSpec:
    """The ``[capture]`` table of the sweep file, as the executor carries it."""

    instrument: tuple[str, ...] = ()
    content: bool = False
    max_span_bytes: int = 8_192
    max_spans: int = 1_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrument", tuple(str(name) for name in self.instrument))


@dataclass(frozen=True)
class CaptureStatus:
    """What ``install()`` did, for the manifest and the per-batch ``backend_meta``."""

    requested: bool
    active: bool
    reason: str | None
    instrumented: tuple[str, ...]


class Recorder:
    """The handle a ``capture()`` block yields: the spans of one episode, on their way to meta.

    Spans arrive already converted to the flat mapping ``from_otel`` reads, on the thread that
    ended them, so no ``ReadableSpan`` is held past ``on_end`` and nothing that crosses a pipe
    is anything but JSON-native.
    """

    def __init__(self, spec: CaptureSpec, run_id: str, episode_id: str) -> None:
        self._spec = spec
        self._run_id = run_id
        self._episode_id = episode_id
        self._lock = threading.Lock()
        self._spans: list[dict[str, Any]] = []
        self._dropped = 0
        self._warned = False

    def to_meta(self) -> dict[str, Any] | None:
        """``Trace.to_dict()`` for the episode just closed, or None if nothing was captured.

        None is rule zero: a capture with zero spans and zero drops must leave ``meta``
        untouched, so switching capture on cannot disturb a rollout that records its own trace.
        """
        with self._lock:
            spans = list(self._spans)
            dropped = self._dropped
        if not spans and not dropped:
            return None
        trace = from_otel(spans)
        if self._spec.content:
            trace = _apply_budget(trace, self._spec.max_span_bytes)
        if dropped:
            trace = Trace(
                spans=trace.spans,
                source=trace.source,
                source_version=trace.source_version,
                dropped=trace.dropped + dropped,
            )
        return trace.to_dict()

    def _take(self, span: ReadableSpan) -> None:
        """One ended span, from the collector. Never raises: this runs inside ``on_end``."""
        with self._lock:
            if len(self._spans) >= self._spec.max_spans:
                self._dropped += 1
                if not self._warned:
                    self._warned = True
                    _LOG.warning(
                        "capture: episode %s hit max_spans=%d; later spans are dropped "
                        "and counted in the trace",
                        self._episode_id,
                        self._spec.max_spans,
                    )
                return
        try:
            mapping = _span_mapping(span, content=self._spec.content)
        except Exception:  # noqa: BLE001 - one unconvertible span is never fatal
            _LOG.warning("capture: dropping a span that could not be read")
            with self._lock:
                self._dropped += 1
            return
        with self._lock:
            self._spans.append(mapping)


class _Bucket:
    """The one collector this process installs, and the open episodes it routes spans to.

    Spans are bucketed by the two attributes ``EpisodeStamper`` wrote at ``on_start`` and read
    back off the span at ``on_end`` — not by a second ``ContextVar``. That is thread-safe
    without a context, reuses exactly what M12 shipped, and makes a fire-and-forget span that
    closes after its episode ended fall on the floor instead of leaking into the next row.
    """

    def __init__(self, spec: CaptureSpec, run_id_key: str, episode_key: str) -> None:
        self.spec = spec
        self._run_id_key = run_id_key
        self._episode_key = episode_key
        self._lock = threading.Lock()
        self._open: dict[tuple[str, str], Recorder] = {}

    def open(self, key: tuple[str, str], recorder: Recorder) -> None:
        with self._lock:
            self._open[key] = recorder

    def close(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._open.pop(key, None)

    def take(self, span: ReadableSpan) -> None:
        attrs: Mapping[str, Any] = span.attributes or {}
        run_id = attrs.get(self._run_id_key)
        episode_id = attrs.get(self._episode_key)
        if not isinstance(run_id, str) or not isinstance(episode_id, str):
            return  # belongs to no rollout: dropped, never repaired (M12 T33)
        with self._lock:
            recorder = self._open.get((run_id, episode_id))
        if recorder is not None:
            recorder._take(span)


def install(spec: CaptureSpec) -> CaptureStatus:
    """Activate the named instrumentors and register the collector. Once per process.

    Never raises: a missing ``opentelemetry-sdk``, an unknown instrumentor name, a provider
    this process cannot own and an instrumentor that raises all come back as
    ``CaptureStatus(active=False, reason=...)`` and the run proceeds without a trace.

    A second call returns the first call's status and adds no second collector, because a
    ``TracerProvider`` cannot be replaced and a processor cannot be removed.
    """
    global _STATUS, _BUCKET
    with _LOCK:
        if _STATUS is not None:
            return _STATUS
        try:
            status, bucket = _install(spec)
        except Exception as exc:  # noqa: BLE001 - install() never raises (C4)
            status, bucket = _inactive(f"capture could not be installed: {exc!r}"), None
        _STATUS, _BUCKET = status, bucket
        return status


@contextmanager
def capture(run_id: str, episode_id: str) -> Iterator[Recorder]:
    """Collect the spans of one episode, keyed by ``(run_id, episode_id)``.

    Mirrors M12's ``collect()`` / ``Collector.trace`` shape: the same house idiom for the same
    job one layer up. Inert when ``install()`` did not activate — the recorder still yields,
    and ``to_meta()`` returns None.
    """
    bucket = _BUCKET
    recorder = Recorder(CaptureSpec() if bucket is None else bucket.spec, run_id, episode_id)
    if bucket is None:
        yield recorder
        return
    from proofload.otel import episode  # imported by install(); a sys.modules hit here

    key = (run_id, episode_id)
    bucket.open(key, recorder)
    try:
        with episode(run_id, episode_id):
            yield recorder
    finally:
        bucket.close(key)


# ---------- installation ----------


def _inactive(reason: str) -> CaptureStatus:
    return CaptureStatus(requested=True, active=False, reason=reason, instrumented=())


def _install(spec: CaptureSpec) -> tuple[CaptureStatus, _Bucket | None]:
    try:
        from opentelemetry import trace as trace_api
        from opentelemetry.sdk.trace import TracerProvider

        from proofload.otel import EPISODE_KEY, RUN_ID_KEY, EpisodeStamper
    except ImportError as exc:
        return _inactive(f"opentelemetry-sdk is not importable: {exc}"), None

    instrumented, failure = _activate(spec.instrument)
    if failure is not None:
        return _inactive(failure), None

    current = trace_api.get_tracer_provider()
    if isinstance(current, TracerProvider):
        provider = current  # the user's own SDK provider: add to it, never replace it
    elif not isinstance(current, trace_api.ProxyTracerProvider):
        return (
            _inactive(
                f"a {type(current).__name__} is already the global TracerProvider and it "
                "cannot be overridden; capture would collect nothing"
            ),
            None,
        )
    else:
        provider = _new_provider()
        trace_api.set_tracer_provider(provider)
        if trace_api.get_tracer_provider() is not provider:
            return _inactive("the global TracerProvider was set by someone else first"), None

    bucket = _Bucket(spec, RUN_ID_KEY, EPISODE_KEY)
    provider.add_span_processor(EpisodeStamper())
    provider.add_span_processor(_collecting_processor(bucket))
    return CaptureStatus(True, True, None, instrumented), bucket


def _activate(names: tuple[str, ...]) -> tuple[tuple[str, ...], str | None]:
    """Instantiate and ``instrument()`` exactly the named entry points, or explain why not.

    Every name is resolved before any is activated, so an unknown name patches nothing.
    """
    if not names:
        return (), None
    found = {ep.name: ep for ep in entry_points(group=_ENTRY_POINT_GROUP)}
    missing = [name for name in names if name not in found]
    if missing:
        return (), (
            f"no {_ENTRY_POINT_GROUP} entry point named {', '.join(repr(n) for n in missing)}; "
            "install the instrumentation package or drop the name from [capture].instrument"
        )
    activated: list[str] = []
    for name in names:
        try:
            found[name].load()().instrument()
        except Exception as exc:  # noqa: BLE001 - an instrumentor never fails a run (C4)
            return (), f"instrumentor {name!r} could not be activated: {exc!r}"
        activated.append(name)
    return tuple(activated), None


def _new_provider() -> TracerProvider:
    """A provider whose span ids do not come from the global ``random`` (C2).

    A rollout that re-seeds ``random`` between calls — which Proofload's own per-episode seed
    invites — makes OTel's default generator emit identical span ids, and ``from_otel`` drops
    them as duplicates: measured at 10 spans in, 1 kept.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.id_generator import IdGenerator

    class _UrandomIdGenerator(IdGenerator):
        def __init__(self) -> None:
            self._rng = random.Random(os.urandom(32))

        def generate_span_id(self) -> int:
            span_id = self._rng.getrandbits(64)
            while span_id == 0:
                span_id = self._rng.getrandbits(64)
            return span_id

        def generate_trace_id(self) -> int:
            trace_id = self._rng.getrandbits(128)
            while trace_id == 0:
                trace_id = self._rng.getrandbits(128)
            return trace_id

        def is_trace_id_random(self) -> bool:
            return True

    return TracerProvider(id_generator=_UrandomIdGenerator())


def _collecting_processor(bucket: _Bucket) -> Any:
    """The collector as a real ``SpanProcessor``; the class cannot exist at module scope."""
    from opentelemetry.sdk.trace import SpanProcessor

    class _Collector(SpanProcessor):
        def on_end(self, span: ReadableSpan) -> None:
            bucket.take(span)

    return _Collector()


# ---------- ReadableSpan -> the flat mapping from_otel reads ----------


def _attribute_value(value: Any) -> Any:
    """One OTel attribute value, JSON-native. Coercion ships with capture: one unserializable
    value in one span would otherwise cost the whole batch at ``Store.append``."""
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_attribute_value(item) for item in value]
    return str(value)


def _is_content(key: str) -> bool:
    return key in _CONTENT_KEYS or any(
        key == prefix or key.startswith(prefix + ".") for prefix in _CONTENT_PREFIXES
    )


def _span_mapping(span: ReadableSpan, *, content: bool) -> dict[str, Any]:
    """One finished span as the flat span mapping ``from_otel`` consumes.

    Hand-rolled and standard-library-only on purpose: the OTLP encoder the stamper oracle uses
    lives in the ``dev`` extra, and making it a runtime dependency would put protobuf in the
    ``agent`` extra for nothing.
    """
    context = span.get_span_context()
    parent = span.parent
    mapping: dict[str, Any] = {
        # A span with no context has no id: from_otel drops it as ``no_span_id`` and counts it.
        "spanId": "" if context is None else format(context.span_id, "016x"),
        "parentSpanId": None if parent is None else format(parent.span_id, "016x"),
        "name": span.name,
        "startTimeUnixNano": span.start_time,
        "endTimeUnixNano": span.end_time,
        "attributes": [
            {"key": key, "value": _attribute_value(value)}
            for key, value in (span.attributes or {}).items()
            if content or not _is_content(key)
        ],
    }
    status = span.status
    if status is not None and status.status_code is not None:
        mapping["status"] = {
            "code": status.status_code.name,
            "message": status.description,
        }
    return mapping


# ---------- the per-span byte budget (attrs, never input/output) ----------


def _json_size(value: Any) -> int:
    try:
        return len(json.dumps(value).encode("utf-8"))
    except (TypeError, ValueError):
        return len(str(value).encode("utf-8"))


def _apply_budget(trace: Trace, max_span_bytes: int) -> Trace:
    """Replace the oversized values in ``attrs`` with a marker recording their byte length.

    ``from_otel`` never populates ``input``/``output``: a captured prompt arrives as the
    *attributes* ``gen_ai.input.messages`` and ``gen_ai.output.messages``, so a budget written
    against those two fields would be inert and would look like it was working. Only the
    offending values are replaced — small values and the two routing stamps survive, because
    the stamps are the whole mechanism for attaching a span to its row.
    """
    from proofload.otel import EPISODE_KEY, RUN_ID_KEY

    protected = {RUN_ID_KEY, EPISODE_KEY}
    spans = []
    changed = False
    for span in trace.spans:
        if _json_size(dict(span.attrs)) <= max_span_bytes:
            spans.append(span)
            continue
        attrs = dict(span.attrs)
        candidates = sorted(
            (key for key in attrs if key not in protected),
            key=lambda key: _json_size(attrs[key]),
            reverse=True,
        )
        for key in candidates:
            if _json_size(attrs) <= max_span_bytes:
                break
            attrs[key] = _TRUNCATION_MARKER.format(n=_json_size(attrs[key]))
        spans.append(replace(span, attrs=attrs))
        changed = True
    if not changed:
        return trace
    return Trace(
        spans=tuple(spans),
        source=trace.source,
        source_version=trace.source_version,
        dropped=trace.dropped,
    )
