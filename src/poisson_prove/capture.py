"""In-process trace capture — the wire from a rollout's spans into ``Episode.meta``.

The trace schema and its converters (``trace.py``) and the episode stamper (``otel.py``) came
first; nothing carried a trace into an ``Episode``. This module is the missing half: it activates
the instrumentors the user named in their sweep file, owns (or joins) the process's
``TracerProvider``, and hands the executor one ``Trace.to_dict()`` per episode.

``opentelemetry`` is imported **lazily, inside** ``install()`` — never at module scope, and
``poisson_prove.otel`` with it, since that module imports the SDK at import time. ``executor.py``
can therefore import this file unconditionally and the trace layer's promise still holds: a run
with no ``[capture]`` table imports no OpenTelemetry module at all.

Three facts drive the design, all of them measured:

* A ``TracerProvider`` set in a forking parent makes the child's ``set_tracer_provider``
  a refused no-op, so the child captures nothing, silently. ``install()`` verifies it owns —
  or was added to — the global provider and reports ``active=False`` otherwise; on the forking
  paths the executor calls it in the child.
* OTel's default ``RandomIdGenerator`` draws from the global ``random``, which Prove's
  own seeds collide. The provider this module builds carries an id generator seeded from
  ``os.urandom`` and never touches the global stream.
* Installing a provider is permanent: there is no ``remove_span_processor`` and
  ``set_tracer_provider`` refuses a second call. Where the user already set an SDK provider we
  **add** our two processors to theirs and leave their exporters alone; ``install()`` is once
  per process and a second call adds no second collector.

Only instrumentors the user named are activated, resolved through the
``opentelemetry_instrumentor`` entry-point group. No auto-discovery, no import hook, no wrapper
of our own. An unknown name, a missing SDK or an instrumentor that raises all yield
``CaptureStatus(active=False, reason=...)`` and the run proceeds.

The timed-out episode: the collector also remembers the live spans of each open
episode from ``on_start`` to ``on_end``, and the private ``_snapshot(reason)`` hands the
executor's ``SIGTERM`` handler the episode as it stands -- every closed span, then every open
one with no end -- as a trace marked ``truncated=reason``. Every lock on that path is
re-entrant, because the handler runs inside whatever the rollout's thread was doing.
"""

from __future__ import annotations

import heapq
import logging
import os
import random
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any

from poisson_prove.trace import (
    CONTENT_KEYS,
    OTEL_KIND_MAP,
    from_otel,
    truncate_observations,
)

if TYPE_CHECKING:  # imports for typing only; the runtime import lives in install()
    from opentelemetry.context import Context
    from opentelemetry.sdk.trace import ReadableSpan, Span, TracerProvider

__all__ = ["CaptureSpec", "CaptureStatus", "Recorder", "capture", "install"]

_LOG = logging.getLogger(__name__)

#: The group every ``opentelemetry-instrumentation-*`` package registers under. The only place
#: an instrumentor name is resolved; discovering the group's other members is forbidden.
_ENTRY_POINT_GROUP = "opentelemetry_instrumentor"

# ---------- process state: one provider, one collector, one status ----------

#: Guards ``install()`` alone and is never taken on the snapshot path, so it can stay plain.
#: The locks the executor's SIGTERM handler can meet are the collector's and the recorder's,
#: and those are re-entrant.
_LOCK = threading.Lock()
_STATUS: CaptureStatus | None = None
_BUCKET: _Bucket | None = None


@dataclass(frozen=True, kw_only=True)
class CaptureSpec:
    """The ``[capture]`` table of the sweep file, as the executor carries it.

    ``kw_only`` so the required field keeps its place in the declaration order:
    ``_CAPTURE_FIELDS`` is that order in both the sampler and the Modal transport, and
    Python would otherwise force a required field in front of the defaulted ones. There is
    not one positional construction of this class anywhere in the package or its tests, so
    it costs nothing today and forecloses one that would silently reorder later.
    """

    instrument: tuple[str, ...] = ()
    content: bool = False
    #: The bound on one stored observation value, whether or not ``content`` is on. Required,
    #: and supplied by nothing: every run says what it keeps whole, and ``None`` is *keep
    #: every value whole* (the sweep file's ``"none"``).
    max_observation_bytes: int | None
    #: The span cap, off by default: ``None`` keeps every closed span. A runaway loop is
    #: bounded by ``episode_timeout`` and by the horizon, and when neither fires it is a
    #: finding the trace should show in full rather than a ``dropped`` count.
    max_spans: int | None = None

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
    is anything but JSON-native. The live ``Span`` objects still open are held too, keyed by
    span id, so ``_snapshot`` can read them as they stand when the executor terminates the
    episode.
    """

    def __init__(self, spec: CaptureSpec, run_id: str, episode_id: str) -> None:
        self._spec = spec
        self._run_id = run_id
        self._episode_id = episode_id
        # Re-entrant, not plain: the executor's SIGTERM handler snapshots from inside whatever
        # the rollout's thread was doing, which may be this recorder's own ``_take``.
        self._lock = threading.RLock()
        # A bounded max-heap on start time, at most ``max_spans`` entries, keyed so the
        # latest-started span sits on top and is the one evicted when an earlier one arrives.
        self._kept: list[tuple[int, int, dict[str, Any]]] = []
        self._seq = 0
        self._dropped = 0
        self._warned = False
        # The episode's open spans, the live SDK objects, keyed by span id. ``on_end`` hands
        # the collector a fresh ``ReadableSpan``, never the object ``on_start`` saw, so
        # identity cannot key this: an ``id(span)`` registry never shrinks, and every closed
        # span then reaches ``from_otel`` twice.
        self._live: dict[int, Span] = {}

    def to_meta(self) -> dict[str, Any] | None:
        """``Trace.to_dict()`` for the episode just closed, or None if nothing was captured.

        None is rule zero: a capture with zero spans and zero drops must leave ``meta``
        untouched, so switching capture on cannot disturb a rollout that records its own trace.
        """
        return self._trace([], None)

    def _snapshot(self, reason: str) -> dict[str, Any] | None:
        """The episode as it stands: every closed span, then every open one, cut with ``reason``.

        The executor's drain, run from its SIGTERM handler: each open span is read in one pass
        (see ``_span_mapping``) and no lock but the re-entrant one is taken. Open spans are
        exempt from ``max_spans`` -- the one open at the kill is usually the latest-started,
        which the cap would drop first, and it is the span the user wants -- so they are
        appended after the capped closed spans. An open span that cannot be read is dropped
        and counted, never raised. Rule zero still holds: nothing captured, no trace.
        """
        with self._lock:
            live = list(self._live.values())
        open_spans: list[dict[str, Any]] = []
        unreadable = 0
        for span in live:
            try:
                open_spans.append(_span_mapping(span, content=self._spec.content, live=True))
            except Exception:  # noqa: BLE001 - one unreadable span never loses the snapshot
                unreadable += 1
        return self._trace(open_spans, reason, unreadable)

    def _trace(
        self, open_spans: list[dict[str, Any]], truncated: str | None, unreadable: int = 0
    ) -> dict[str, Any] | None:
        with self._lock:
            spans = [m for _, _, m in sorted(self._kept, key=lambda e: (-e[0], -e[1]))]
            dropped = self._dropped + unreadable
        spans.extend(open_spans)  # after the cap, never inside it
        if not spans and not dropped:
            return None
        trace = from_otel(spans)
        # Unconditional: the cut is a storage bound, not a privacy one, so it runs whether or
        # not content capture is on. A captured observation never crosses the pipe uncut.
        trace = truncate_observations(trace, limit=self._spec.max_observation_bytes)
        if dropped or truncated is not None:
            trace = replace(trace, dropped=trace.dropped + dropped, truncated=truncated)
        return trace.to_dict()

    def _track(self, span: Span) -> None:
        """One started span, from the collector: open until ``_take`` sees it end."""
        context = span.get_span_context()
        if context is None:
            return
        with self._lock:
            self._live[context.span_id] = span

    def _forget(self, span_id: int | None) -> None:
        if span_id is not None:
            self._live.pop(span_id, None)

    def _take(self, span: ReadableSpan) -> None:
        """One ended span, from the collector. Never raises: this runs inside ``on_end``."""
        context = span.get_span_context()
        span_id = None if context is None else context.span_id
        try:
            mapping = _span_mapping(span, content=self._spec.content)
        except Exception:  # noqa: BLE001 - one unconvertible span is never fatal
            _LOG.warning("capture: dropping a span that could not be read")
            with self._lock:
                self._forget(span_id)
                self._dropped += 1
            return
        start = mapping.get("startTimeUnixNano")
        with self._lock:
            # One lock hold moves the span from open to closed, so a snapshot taken under the
            # same lock sees it in exactly one of the two.
            self._forget(span_id)
            self._seq += 1
            entry = (-(start if isinstance(start, int) else 0), -self._seq, mapping)
            cap = self._spec.max_spans
            if cap is None or len(self._kept) < cap:
                heapq.heappush(self._kept, entry)
                return
            # Full. The cap is in start order: the earliest-started spans are kept, so
            # a capped trace keeps its root and loses its deepest spans. Spans end
            # innermost-first, and a cap applied in end order would keep the leaves.
            if self._kept and entry > self._kept[0]:
                heapq.heapreplace(self._kept, entry)
            self._dropped += 1
            if not self._warned:
                self._warned = True
                _LOG.warning(
                    "capture: episode %s hit max_spans=%d; the latest-started spans are "
                    "dropped and counted in the trace",
                    self._episode_id,
                    self._spec.max_spans,
                )


class _Bucket:
    """The one collector this process installs, and the open episodes it routes spans to.

    Spans are bucketed by the two attributes ``EpisodeStamper`` wrote at ``on_start`` and read
    back off the span at ``on_end`` — not by a second ``ContextVar``. That is thread-safe
    without a context, reuses exactly what the stamper writes, and makes a fire-and-forget span that
    closes after its episode ended fall on the floor instead of leaking into the next row.
    ``on_start`` routes the same way, one processor later than the stamper, so the open-span
    registry is per episode and goes away with the recorder when the episode closes.
    """

    def __init__(self, spec: CaptureSpec, run_id_key: str, episode_key: str) -> None:
        self.spec = spec
        self._run_id_key = run_id_key
        self._episode_key = episode_key
        self._lock = threading.RLock()  # re-entrant: see Recorder
        self._open: dict[tuple[str, str], Recorder] = {}

    def open(self, key: tuple[str, str], recorder: Recorder) -> None:
        with self._lock:
            self._open[key] = recorder

    def close(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._open.pop(key, None)

    def only(self) -> Recorder | None:
        """The one open episode, or None when there is none or more than one to choose from."""
        with self._lock:
            if len(self._open) != 1:
                return None
            return next(iter(self._open.values()))

    def _route(self, attrs: Mapping[str, Any] | None) -> Recorder | None:
        stamped: Mapping[str, Any] = attrs or {}
        run_id = stamped.get(self._run_id_key)
        episode_id = stamped.get(self._episode_key)
        if not isinstance(run_id, str) or not isinstance(episode_id, str):
            return None  # belongs to no rollout: dropped, never repaired
        with self._lock:
            return self._open.get((run_id, episode_id))

    def start(self, span: Span) -> None:
        """A span just started, stamped already: the stamper registers before this collector.
        A live span's ``get`` is a plain dict read and takes no SDK lock."""
        recorder = self._route(span.attributes)
        if recorder is not None:
            recorder._track(span)

    def take(self, span: ReadableSpan) -> None:
        recorder = self._route(span.attributes)
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
        except Exception as exc:  # noqa: BLE001 - install() never raises
            status, bucket = _inactive(f"capture could not be installed: {exc!r}"), None
        _STATUS, _BUCKET = status, bucket
        return status


#: The spec of a recorder nothing feeds. ``capture()`` with no bucket yields a recorder no
#: collector writes to and whose ``to_meta()`` returns None, so the cap it carries is never
#: read -- and it is ``None`` rather than a number precisely so that no integer in this
#: package can be mistaken for a cap that something supplies.
_INERT_SPEC = CaptureSpec(max_observation_bytes=None)


@contextmanager
def capture(run_id: str, episode_id: str) -> Iterator[Recorder]:
    """Collect the spans of one episode, keyed by ``(run_id, episode_id)``.

    Mirrors ``trace.py``'s ``collect()`` / ``Collector.trace`` shape: the same house idiom for the
    same job one layer up. Inert when ``install()`` did not activate — the recorder still yields,
    and ``to_meta()`` returns None.
    """
    bucket = _BUCKET
    recorder = Recorder(_INERT_SPEC if bucket is None else bucket.spec, run_id, episode_id)
    if bucket is None:
        yield recorder
        return
    from poisson_prove.otel import episode  # imported by install(); a sys.modules hit here

    key = (run_id, episode_id)
    bucket.open(key, recorder)
    try:
        with episode(run_id, episode_id):
            yield recorder
    finally:
        bucket.close(key)


def _snapshot(reason: str) -> dict[str, Any] | None:
    """The executor's drain: the one open episode's spans, closed and open, cut with ``reason``.

    Private on purpose -- ``capture`` stays at five public symbols -- and reached by the
    executor's ``SIGTERM`` handler from the child that owns the spans. With no collector, or
    with anything but exactly one open episode, it answers None and the row keeps the bare
    ``("timeout", None)`` it would have without the snapshot.
    """
    bucket = _BUCKET
    if bucket is None:
        return None
    recorder = bucket.only()
    if recorder is None:
        return None
    return recorder._snapshot(reason)


# ---------- installation ----------


def _inactive(reason: str) -> CaptureStatus:
    return CaptureStatus(requested=True, active=False, reason=reason, instrumented=())


def _install(spec: CaptureSpec) -> tuple[CaptureStatus, _Bucket | None]:
    try:
        from opentelemetry import trace as trace_api
        from opentelemetry.sdk.trace import TracerProvider

        from poisson_prove.otel import EPISODE_KEY, RUN_ID_KEY, EpisodeStamper
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
        except Exception as exc:  # noqa: BLE001 - an instrumentor never fails a run
            return (), f"instrumentor {name!r} could not be activated: {exc!r}"
        activated.append(name)
    return tuple(activated), None


def _new_provider() -> TracerProvider:
    """A provider whose span ids do not come from the global ``random``.

    A rollout that re-seeds ``random`` between calls — which Prove's own per-episode seed
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
        def on_start(self, span: Span, parent_context: Context | None = None) -> None:
            bucket.start(span)

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
    return key in CONTENT_KEYS


#: OpenInference's prompt and answer on a span: content on a model call, and a
#: tool's arguments and result elsewhere, which ``content = false`` leaves alone.
_MODEL_CALL_VALUES = ("input.value", "output.value")


def _is_model_call(attributes: Mapping[str, Any] | None) -> bool:
    """Whether a span reads as an ``llm`` span by ``from_otel``'s ladder on its two model-call
    keys: a recognized ``gen_ai.operation.name`` (or its old spelling) that maps to ``llm``, else
    OpenInference's span kind. Looked up key by key, never iterated, so a live span's attributes
    are safe to read here."""
    if not attributes:
        return False
    operation = attributes.get("gen_ai.operation.name", attributes.get("llm.request.type"))
    if operation is not None and str(operation) in OTEL_KIND_MAP:
        return OTEL_KIND_MAP[str(operation)] == "llm"
    vendor = attributes.get("openinference.span.kind")
    return isinstance(vendor, str) and vendor.strip().lower() == "llm"


def _stripped(key: str, model_call: bool) -> bool:
    """Whether ``content = false`` drops this attribute: every content key, and on a model call
    its OpenInference prompt and answer too."""
    return _is_content(key) or (model_call and key in _MODEL_CALL_VALUES)


def _live_attributes(attributes: Mapping[str, Any] | None) -> list[tuple[str, Any]]:
    """A live span's attributes, copied in one pass without iterating them.

    The SDK hands a live span's attributes out as a proxy over ``BoundedAttributes``, whose
    ``__iter__`` takes a plain lock that the rollout's thread holds inside ``set_attribute`` --
    exactly where a signal may land. ``copy()`` on that class is a bare ``dict.copy()``,
    lock-free and atomic under the GIL, so it is the read. A copy that fails is an empty one.
    """
    if not attributes:
        return []
    copier = getattr(attributes, "copy", None)
    try:
        copied = dict(copier()) if callable(copier) else dict(attributes)
    except Exception:  # noqa: BLE001 - torn: the attributes are dropped, the span is not
        return []
    return list(copied.items())


def _span_mapping(span: ReadableSpan, *, content: bool, live: bool = False) -> dict[str, Any]:
    """One span as the flat span mapping ``from_otel`` consumes.

    Hand-rolled and standard-library-only on purpose: the OTLP encoder the stamper's tests use
    lives in the ``dev`` extra, and making it a runtime dependency would put protobuf in the
    ``agent`` extra for nothing.

    ``live=True`` reads a span that has not ended -- the executor's snapshot -- as it stands:
    ``endTimeUnixNano`` is None whatever the object says by now, the attributes are taken in
    one pass, and an attribute whose value cannot be coerced is dropped alone. Everything else
    is the same mapping, so the closed spans of a snapshot are byte-identical to a normal
    close's.
    """
    context = span.get_span_context()
    parent = span.parent
    model_call = _is_model_call(span.attributes)
    if live:
        attributes: list[dict[str, Any]] = []
        for key, value in _live_attributes(span.attributes):
            if not content and _stripped(key, model_call):
                continue
            try:
                attributes.append({"key": key, "value": _attribute_value(value)})
            except Exception:  # noqa: BLE001 - a torn attribute is a dropped attribute
                continue
    else:
        attributes = [
            {"key": key, "value": _attribute_value(value)}
            for key, value in (span.attributes or {}).items()
            if content or not _stripped(key, model_call)
        ]
    mapping: dict[str, Any] = {
        # The OTel trace id a user's own collector keys on; from_otel keeps it in attrs.
        "traceId": "" if context is None else format(context.trace_id, "032x"),
        # A span with no context has no id: from_otel drops it as ``no_span_id`` and counts it.
        "spanId": "" if context is None else format(context.span_id, "016x"),
        "parentSpanId": None if parent is None else format(parent.span_id, "016x"),
        "name": span.name,
        "startTimeUnixNano": span.start_time,
        "endTimeUnixNano": None if live else span.end_time,
        "attributes": attributes,
    }
    status = span.status
    if status is not None and status.status_code is not None:
        mapping["status"] = {
            "code": status.status_code.name,
            "message": status.description,
        }
    return mapping
