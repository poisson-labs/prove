"""M12 -- Trace: one immutable schema for what a target actually did.

``proofload.trace/1`` carries a span forest with wall-clock start and end, parentage and
code location, plus the three ways one gets built: converted from OpenTelemetry spans
(:func:`from_otel`), converted from LiteLLM call logs (:func:`from_litellm`), or recorded
explicitly by the user (:func:`collect` / :func:`record` / :func:`step`) for the calls
nothing else can see.

The module performs no acquisition of any kind (ADR-025): the converters parse mappings
someone else collected and this file opens nothing, reads nothing and patches nothing. It
imports only the standard library, so neither converter puts an OTel or LiteLLM package on
core's import graph.

Three values are built in exactly one place each, because a value built twice is ADR-021
again: :data:`SCHEMA` (ADR-024), :data:`OTEL_SEMCONV_VERSION` (ADR-024) and the span clock
helper that mints ``start_ns`` and ``end_ns`` (ADR-023).
"""

from __future__ import annotations

import base64
import contextlib
import contextvars
import functools
import inspect
import itertools
import logging
import re
import sys
import time
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

__all__ = [
    "ATTRIBUTE_ALIASES",
    "DROP_REASONS",
    "KINDS",
    "OTEL_KIND_MAP",
    "OTEL_SEMCONV_VERSION",
    "SCHEMA",
    "SOURCES",
    "Collector",
    "Span",
    "SpanHandle",
    "Trace",
    "TraceValidationError",
    "collect",
    "from_litellm",
    "from_otel",
    "merge",
    "record",
    "step",
]

# ---------- constants ----------

#: The one place the schema id is written (ADR-024). Every other site reaches it from here.
SCHEMA = "proofload.trace/1"

KINDS: tuple[str, ...] = ("llm", "tool", "retrieval", "db", "http", "agent", "other")
SOURCES: tuple[str, ...] = ("record", "otel", "litellm", "mixed")
DROP_REASONS: tuple[str, ...] = (
    "no_span_id",
    "duplicate_span_id",
    "bad_timestamps",
    "unparseable",
)

#: The one place the semantic-convention pin is written (ADR-024). The GenAI conventions are
#: badged Development, so a stored trace records which vocabulary it was read under.
OTEL_SEMCONV_VERSION = "1.42.0"

ATTRIBUTE_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "code.filepath": "code.file.path",
        "code.function": "code.function.name",
        "code.lineno": "code.line.number",
        "gen_ai.usage.prompt_tokens": "gen_ai.usage.input_tokens",
        "gen_ai.usage.completion_tokens": "gen_ai.usage.output_tokens",
        "llm.usage.prompt_tokens": "gen_ai.usage.input_tokens",
        "llm.usage.completion_tokens": "gen_ai.usage.output_tokens",
        "llm.request.model": "gen_ai.request.model",
        "llm.request.type": "gen_ai.operation.name",
        "exception.type": "error.type",
    }
)

OTEL_KIND_MAP: Mapping[str, str] = MappingProxyType(
    {
        "chat": "llm",
        "text_completion": "llm",
        "generate_content": "llm",
        "execute_tool": "tool",
        "retrieval": "retrieval",
        "embeddings": "retrieval",
        "invoke_agent": "agent",
        "create_agent": "agent",
        "invoke_workflow": "agent",
        "plan": "agent",
    }
)

_LOG = logging.getLogger(__name__)

_SPAN_FIELDS: tuple[str, ...] = (
    "span_id",
    "parent_id",
    "kind",
    "name",
    "start_ns",
    "end_ns",
    "input",
    "output",
    "tokens",
    "confidence",
    "error",
    "code",
    "attrs",
)
_SPAN_KEYS = frozenset(_SPAN_FIELDS)
_TRACE_FIELDS: tuple[str, ...] = ("schema", "source", "source_version", "dropped", "spans")
_TRACE_KEYS = frozenset(_TRACE_FIELDS)
_CODE_KEYS = frozenset({"filepath", "function", "lineno"})

#: Attributes read into a first-class field and therefore removed from ``attrs`` (T20).
_LIFTED_KEYS: tuple[str, ...] = (
    "gen_ai.request.model",
    "gen_ai.tool.name",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.operation.name",
    "code.file.path",
    "code.function.name",
    "code.line.number",
    "error.type",
)

#: An unrecognized operation name, and an ``error.type`` on a span whose status is not an
#: error, travel under keys of Proofload's own: the keys they arrived under are lifted, and
#: T20 bans a lifted key from ``attrs``. Dropping them instead would be silent data loss.
_ORIGINAL_OPERATION = "proofload.original_operation"
_ORIGINAL_ERROR_TYPE = "proofload.error_type"

_HEX_RE = re.compile(r"\A[0-9a-fA-F]+\Z")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class TraceValidationError(ValueError):
    """Raised when a Trace, a Span or a stored trace dict violates one of its invariants."""


# ---------- the span clock (ADR-023): the only place a span timestamp is minted ----------


def _span_clock() -> tuple[int, int]:
    """The wall clock and the monotonic clock, read together, in one place (T17).

    ``time.time_ns()`` is not monotonic -- an NTP step mid-block would otherwise produce a
    span whose end precedes its start. Callers open a span on the wall reading and close it
    at ``start_ns`` plus a monotonic delta, so ``end_ns >= start_ns`` always holds.
    """
    return time.time_ns(), time.perf_counter_ns()


_SPAN_SEQUENCE = itertools.count()


def _new_span_id() -> str:
    """A 16-hex-character id whose leading counter makes minting order sort order.

    ``ordered()`` breaks a ``start_ns`` tie on ``span_id``; a purely random id would let two
    spans opened inside the same clock tick come back in an arbitrary order.
    """
    return f"{next(_SPAN_SEQUENCE) & 0xFFFFFFFF:08x}{uuid.uuid4().hex[:8]}"


# ---------- the schema ----------


def _require_keys(d: Any, expected: frozenset[str], label: str) -> Mapping[str, Any]:
    if not isinstance(d, Mapping):
        raise TraceValidationError(f"{label} must be a mapping, got {type(d).__name__}")
    keys = set(d)
    # str() before sorting: a non-string key is a schema violation to report, not a TypeError
    # to leak out of sorted() on a mixed-type set.
    unknown = sorted(str(key) for key in keys - expected)
    if unknown:
        raise TraceValidationError(
            f"unknown {label} key(s): {', '.join(unknown)}; "
            f"{label} keys are exactly {', '.join(sorted(expected))}"
        )
    missing = sorted(expected - keys)
    if missing:
        raise TraceValidationError(
            f"missing {label} key(s): {', '.join(missing)}; "
            f"{label} keys are exactly {', '.join(sorted(expected))}"
        )
    return d


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True, eq=True)
class Span:
    """One node of the span forest. Frozen; validated at construction, so also in ``from_dict``."""

    span_id: str
    parent_id: str | None
    kind: str
    name: str
    start_ns: int
    end_ns: int | None
    input: Any | None = None
    output: Any | None = None
    tokens: Mapping[str, int] | None = None
    confidence: float | None = None
    error: str | None = None
    code: Mapping[str, Any] | None = None
    attrs: Mapping[str, Any] = field(default_factory=dict)

    __hash__ = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if not isinstance(self.span_id, str) or not self.span_id:
            raise TraceValidationError("span_id must be a non-empty str")
        if self.parent_id is not None and not isinstance(self.parent_id, str):
            raise TraceValidationError("parent_id must be a str or None")
        if self.kind not in KINDS:
            raise TraceValidationError(
                f"kind {self.kind!r} is not a Proofload span kind; KINDS are {', '.join(KINDS)}"
            )
        if not isinstance(self.name, str):
            raise TraceValidationError("name must be a str")
        if not _is_int(self.start_ns):
            raise TraceValidationError(
                f"start_ns must be an int of Unix epoch nanoseconds, got {self.start_ns!r}"
            )
        if self.end_ns is not None:
            if not _is_int(self.end_ns):
                raise TraceValidationError(
                    f"end_ns must be an int of Unix epoch nanoseconds or None, got {self.end_ns!r}"
                )
            if self.end_ns < self.start_ns:
                raise TraceValidationError(
                    f"end_ns must be >= start_ns, got start_ns={self.start_ns} end_ns={self.end_ns}"
                )
        if self.tokens is not None:
            if not isinstance(self.tokens, Mapping):
                raise TraceValidationError("tokens must be a mapping or None")
            object.__setattr__(self, "tokens", dict(self.tokens))
        if self.confidence is not None and not isinstance(self.confidence, (int, float)):
            raise TraceValidationError("confidence must be a number or None")
        if self.error is not None and not isinstance(self.error, str):
            raise TraceValidationError("error must be a str or None")
        if self.code is not None:
            code = _require_keys(self.code, _CODE_KEYS, "code")
            lineno = code["lineno"]
            if lineno is not None and not (_is_int(lineno) and lineno > 0):
                raise TraceValidationError(
                    f"code lineno must be a positive int or None, got {lineno!r}"
                )
            object.__setattr__(self, "code", dict(code))
        if not isinstance(self.attrs, Mapping):
            raise TraceValidationError("attrs must be a mapping")
        object.__setattr__(self, "attrs", dict(self.attrs))

    @property
    def duration_ms(self) -> float | None:
        """``(end_ns - start_ns) / 1e6``, or None for a span never observed to close."""
        if self.end_ns is None:
            return None
        return (self.end_ns - self.start_ns) / 1e6

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "kind": self.kind,
            "name": self.name,
            "start_ns": self.start_ns,
            "end_ns": self.end_ns,
            "input": self.input,
            "output": self.output,
            "tokens": None if self.tokens is None else dict(self.tokens),
            "confidence": self.confidence,
            "error": self.error,
            "code": None if self.code is None else dict(self.code),
            "attrs": dict(self.attrs),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Span:
        checked = _require_keys(d, _SPAN_KEYS, "span")
        return cls(**{name: checked[name] for name in _SPAN_FIELDS})


@dataclass(frozen=True, eq=True)
class Trace:
    """A span forest plus its provenance. Frozen; validated at construction."""

    spans: tuple[Span, ...]
    source: str
    source_version: str | None = None
    dropped: int = 0

    __hash__ = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if isinstance(self.spans, Span) or not isinstance(self.spans, (tuple, list)):
            raise TraceValidationError("spans must be a tuple of Span")
        spans = tuple(self.spans)
        for span in spans:
            if not isinstance(span, Span):
                raise TraceValidationError(f"spans must hold Span, got {type(span).__name__}")
        object.__setattr__(self, "spans", spans)
        if self.source not in SOURCES:
            raise TraceValidationError(
                f"source {self.source!r} is not a Proofload trace source; "
                f"SOURCES are {', '.join(SOURCES)}"
            )
        if self.source_version is not None and not isinstance(self.source_version, str):
            raise TraceValidationError("source_version must be a str or None")
        if not _is_int(self.dropped) or self.dropped < 0:
            raise TraceValidationError(f"dropped must be a non-negative int, got {self.dropped!r}")
        by_id: dict[str, Span] = {}
        for span in spans:
            if span.span_id in by_id:
                raise TraceValidationError(f"duplicate span_id {span.span_id!r} in one trace")
            by_id[span.span_id] = span
        for span in spans:
            seen = {span.span_id}
            parent = span.parent_id
            while parent is not None and parent in by_id:
                if parent in seen:
                    raise TraceValidationError(f"parent cycle through span_id {parent!r}")
                seen.add(parent)
                parent = by_id[parent].parent_id

    def ordered(self) -> tuple[Span, ...]:
        """Canonical chronological order: sorted by ``(start_ns, span_id)``. Total."""
        return tuple(sorted(self.spans, key=lambda s: (s.start_ns, s.span_id)))

    def roots(self) -> tuple[Span, ...]:
        """Spans with no parent, plus spans whose parent resolves to nothing in this trace.

        An orphan is preserved, never repaired: ``parent_id`` still holds its original value.
        """
        known = {span.span_id for span in self.spans}
        return tuple(
            span
            for span in self.ordered()
            if span.parent_id is None or span.parent_id not in known
        )

    def children(self, span_id: str) -> tuple[Span, ...]:
        """The spans whose ``parent_id`` is ``span_id``, in ``ordered()`` order. Never raises."""
        return tuple(span for span in self.ordered() if span.parent_id == span_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "source": self.source,
            "source_version": self.source_version,
            "dropped": self.dropped,
            "spans": [span.to_dict() for span in self.spans],
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Trace:
        checked = _require_keys(d, _TRACE_KEYS, "trace")
        schema = checked["schema"]
        if schema != SCHEMA:
            raise TraceValidationError(
                f"schema {schema!r} is not {SCHEMA!r}; this reader reads {SCHEMA!r} only"
            )
        raw_spans = checked["spans"]
        if not isinstance(raw_spans, (list, tuple)):
            raise TraceValidationError("spans must be a list of span mappings")
        return cls(
            spans=tuple(Span.from_dict(span) for span in raw_spans),
            source=checked["source"],
            source_version=checked["source_version"],
            dropped=checked["dropped"],
        )


def merge(*traces: Trace) -> Trace:
    """Concatenate span sets into one trace. Never invents cross-source parentage."""
    spans: list[Span] = []
    seen: set[str] = set()
    dropped = 0
    for trace in traces:
        dropped += trace.dropped
        for span in trace.spans:
            if span.span_id in seen:
                raise TraceValidationError(
                    f"duplicate span_id {span.span_id!r} across the traces being merged"
                )
            seen.add(span.span_id)
            spans.append(span)
    # A pin the inputs agree on still describes the merged spans; only disagreement erases it,
    # because a trace that does not record its vocabulary is uninterpretable later.
    versions = {trace.source_version for trace in traces if trace.source_version is not None}
    version = versions.pop() if len(versions) == 1 else None
    return Trace(spans=tuple(spans), source="mixed", source_version=version, dropped=dropped)


# ---------- recording (tier 3 -- the floor, not the path) ----------


@dataclass
class SpanHandle:
    """The mutable handle a ``record()`` block yields. Assignments land on the closed span."""

    input: Any | None = None
    output: Any | None = None
    tokens: Mapping[str, int] | None = None
    confidence: float | None = None
    error: str | None = None


class Collector:
    """Holds the spans recorded inside one ``collect()`` block."""

    def __init__(self) -> None:
        self._spans: list[Span] = []
        self._trace: Trace | None = None

    def _append(self, span: Span) -> None:
        if self._trace is not None:
            # A span opened inside the block but closed after it left -- a fire-and-forget
            # task, or a thread outliving its collect(). The trace is already sealed, so the
            # span cannot be delivered. Say so rather than appending where nothing reads.
            _LOG.warning(
                "span %r closed after its collect() block exited and was not recorded",
                span.name,
            )
            return
        self._spans.append(span)

    def _seal(self) -> None:
        self._trace = Trace(spans=tuple(self._spans), source="record")

    @property
    def trace(self) -> Trace:
        """The completed trace. Raises before the enclosing ``collect()`` block exits."""
        if self._trace is None:
            raise TraceValidationError(
                "the trace is not available until the collect() block exits"
            )
        return self._trace


_COLLECTOR: contextvars.ContextVar[Collector | None] = contextvars.ContextVar(
    "proofload_trace_collector", default=None
)
_STACK: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "proofload_trace_stack", default=()
)


@contextlib.contextmanager
def collect() -> Iterator[Collector]:
    """Collect every ``record()`` and ``@step`` span opened inside this block into one Trace."""
    collector = Collector()
    collector_token = _COLLECTOR.set(collector)
    stack_token = _STACK.set(())
    try:
        yield collector
    finally:
        _STACK.reset(stack_token)
        _COLLECTOR.reset(collector_token)
        collector._seal()


@contextlib.contextmanager
def _span(
    kind: str,
    name: str,
    span_input: Any | None,
    attrs: Mapping[str, Any] | None,
    code: Mapping[str, Any] | None,
) -> Iterator[SpanHandle]:
    handle = SpanHandle(input=span_input)
    collector = _COLLECTOR.get()
    if collector is None:
        # Outside collect() this is a silent no-op, which is what makes a decorated tool safe
        # to leave in production code.
        yield handle
        return
    span_id = _new_span_id()
    stack = _STACK.get()
    parent_id = stack[-1] if stack else None
    start_ns, mono_start = _span_clock()
    stack_token = _STACK.set((*stack, span_id))
    try:
        yield handle
    except BaseException as exc:
        handle.error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        with contextlib.suppress(ValueError):
            _STACK.reset(stack_token)
        _, mono_end = _span_clock()
        try:
            span = Span(
                span_id=span_id,
                parent_id=parent_id,
                kind=kind,
                name=name,
                start_ns=start_ns,
                end_ns=start_ns + (mono_end - mono_start),
                input=handle.input,
                output=handle.output,
                tokens=handle.tokens,
                confidence=handle.confidence,
                error=handle.error,
                code=None if code is None else dict(code),
                attrs=dict(attrs or {}),
            )
        except TraceValidationError as exc:
            # An unknown kind, or a handle assignment the schema cannot hold. The recorder has
            # no crash path: losing one span is worth less than crashing the rollout, and
            # closing a span must never displace the exception the user's block raised. So
            # this is logged and dropped, never raised -- which is what lets a decorated tool
            # stay in production code.
            _LOG.warning("dropping recorded span %r: %s", name, exc)
        else:
            collector._append(span)


def record(
    kind: str,
    name: str,
    *,
    input: Any | None = None,
    attrs: Mapping[str, Any] | None = None,
) -> contextlib.AbstractContextManager[SpanHandle]:
    """Record one span for a call nothing else can see. A no-op outside ``collect()``.

    The code location comes from ``sys._getframe``: ``inspect.stack()`` opens and reads the
    caller's source file on every call, which a recorder on a hot tool path cannot afford.
    """
    frame = sys._getframe(1)
    code = {
        "filepath": frame.f_code.co_filename,
        "function": frame.f_code.co_qualname,
        "lineno": frame.f_lineno,
    }
    return _span(kind, name, input, attrs, code)


def _decorate(fn: Callable[..., Any], kind: str, name: str | None) -> Callable[..., Any]:
    raw_name = getattr(fn, "__qualname__", None) or getattr(fn, "__name__", None)
    qualname = raw_name if isinstance(raw_name, str) else "<callable>"
    span_name = qualname if name is None else name
    code_obj = getattr(fn, "__code__", None)
    code = (
        None
        if code_obj is None
        else {
            "filepath": code_obj.co_filename,
            "function": qualname,
            "lineno": code_obj.co_firstlineno,
        }
    )
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _span(kind, span_name, None, None, code):
                return await fn(*args, **kwargs)

        return async_wrapper

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with _span(kind, span_name, None, None, code):
            return fn(*args, **kwargs)

    return wrapper


def step(
    kind: str | Callable[..., Any] = "tool", name: str | None = None
) -> Callable[..., Any]:
    """Sugar over ``record()``. Usable bare (``@step``) or called (``@step(kind="db")``).

    The bare form arrives with the decorated function as the first positional argument, so
    ``callable(kind)`` is handled explicitly -- get this wrong and the bare form returns a
    partial and the user's tool stops being callable.
    """
    if callable(kind):
        return _decorate(kind, "tool", None)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        return _decorate(fn, kind, name)

    return decorator


# ---------- converters (pure data; import nothing) ----------


def _first(d: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in d:
            value = d[name]
            if value is not None:
                return value
    return None


def _unless_all_zero(hex_id: str | None) -> str | None:
    """An all-zero id is OTel's spelling of "unset", not a span to point at."""
    if hex_id is None or not hex_id.strip("0"):
        return None
    return hex_id


def _base64_to_hex(text: str) -> str | None:
    """Decode a base64 id, tolerating the url-safe alphabet and missing padding."""
    candidate = text.replace("-", "+").replace("_", "/")
    candidate += "=" * (-len(candidate) % 4)
    try:
        decoded = base64.b64decode(candidate, validate=True)
    except (ValueError, TypeError):
        return None
    return decoded.hex() if decoded else None


def _decode_id(raw: Any) -> str | None:
    """Canonicalize a span id to lowercase hex, accepting every spelling seen in the wild.

    Protobuf-JSON encodes ids as base64; several collectors' HTTP-JSON emits hex. Accepting
    one and not the other is the likeliest way this converter silently returns an empty
    trace, so both are read, and the base64 branch also tolerates url-safe characters and
    stripped padding. Length disambiguates: an 8-byte id is 16 hex characters or 11--12
    base64 ones, so an all-hex string is only read as base64 when it cannot be an id in hex.
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    looks_hex = bool(_HEX_RE.match(text))
    if looks_hex and len(text) in (16, 32):
        return _unless_all_zero(text.lower())
    if not looks_hex or len(text) in (11, 22):
        return _unless_all_zero(_base64_to_hex(text))
    if len(text) % 2 == 0:
        return _unless_all_zero(text.lower())
    return _unless_all_zero(_base64_to_hex(text))


def _nanos(raw: Any) -> int | None:
    """Epoch nanoseconds, accepting the JSON strings protobuf-JSON encodes int64 as."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw) if raw.is_integer() else None
    if isinstance(raw, str):
        text = raw.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def _as_int(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw) if raw.is_integer() else None
    if isinstance(raw, str):
        text = raw.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def _any_value(value: Any) -> Any:
    """Unwrap one OTel ``AnyValue``. Flattening happens before aliasing, never after."""
    if not isinstance(value, Mapping):
        return value
    for key in ("stringValue", "string_value", "boolValue", "bool_value"):
        if key in value:
            return value[key]
    for key in ("intValue", "int_value"):
        if key in value:
            parsed = _as_int(value[key])
            return value[key] if parsed is None else parsed
    for key in ("doubleValue", "double_value"):
        if key in value:
            return value[key]
    for key in ("bytesValue", "bytes_value"):
        if key in value:
            return value[key]
    for key in ("arrayValue", "array_value"):
        if key in value:
            inner = value[key]
            values = inner.get("values") if isinstance(inner, Mapping) else None
            return [_any_value(item) for item in values or ()]
    for key in ("kvlistValue", "kvlist_value"):
        if key in value:
            inner = value[key]
            values = inner.get("values") if isinstance(inner, Mapping) else None
            return _flatten_attributes(values)
    return value


def _flatten_attributes(raw: Any) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if not isinstance(raw, (list, tuple)):
        return flat
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        key = item.get("key")
        if isinstance(key, str):
            flat[key] = _any_value(item.get("value"))
    return flat


def _iter_otel_spans(
    payload: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> Iterator[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Yield ``(span mapping, inherited resource+scope attrs)`` for every span in a payload."""
    if isinstance(payload, Mapping):
        resource_spans = _first(payload, "resourceSpans", "resource_spans")
        if resource_spans is None:
            yield payload, {}
            return
        for resource_span in resource_spans or ():
            if not isinstance(resource_span, Mapping):
                continue
            resource = resource_span.get("resource")
            resource_attrs = _flatten_attributes(
                resource.get("attributes") if isinstance(resource, Mapping) else None
            )
            scope_spans = _first(resource_span, "scopeSpans", "scope_spans") or ()
            for scope_span in scope_spans:
                if not isinstance(scope_span, Mapping):
                    continue
                scope = scope_span.get("scope")
                scope_attrs = _flatten_attributes(
                    scope.get("attributes") if isinstance(scope, Mapping) else None
                )
                inherited = {**resource_attrs, **scope_attrs}
                for span in scope_span.get("spans") or ():
                    if isinstance(span, Mapping):
                        yield span, inherited
        return
    for span in payload:
        if isinstance(span, Mapping):
            yield span, {}


def _otel_error(raw: Mapping[str, Any], error_type: Any) -> tuple[str | None, str | None]:
    """``(error, unclaimed error.type)`` -- section 3 maps ``error`` from an ERROR status only."""
    status = raw.get("status")
    code = status.get("code") if isinstance(status, Mapping) else None
    message = status.get("message") if isinstance(status, Mapping) else None
    is_error = (isinstance(code, str) and "ERROR" in code) or (_as_int(code) == 2)
    if not is_error:
        return None, None if error_type is None else str(error_type)
    if isinstance(message, str) and message:
        return message, None
    if error_type is not None:
        return str(error_type), None
    return "STATUS_CODE_ERROR", None


def _otel_span(raw: Mapping[str, Any], inherited: Mapping[str, Any]) -> Span:
    flat = {**inherited, **_flatten_attributes(raw.get("attributes"))}
    attrs: dict[str, Any] = {}
    for key, value in flat.items():
        canonical = ATTRIBUTE_ALIASES.get(key, key)
        if canonical != key and canonical in flat:
            continue  # the source spelled the canonical key too; the deprecated one loses
        attrs[canonical] = value
    lifted = {key: attrs.pop(key, None) for key in _LIFTED_KEYS}

    operation = lifted["gen_ai.operation.name"]
    operation_name = None if operation is None else str(operation)
    if operation_name is not None and operation_name in OTEL_KIND_MAP:
        kind = OTEL_KIND_MAP[operation_name]
    else:
        if operation_name is not None:
            attrs[_ORIGINAL_OPERATION] = operation_name
        if "db.system" in attrs:
            kind = "db"
        elif "http.request.method" in attrs or "url.full" in attrs:
            kind = "http"
        else:
            kind = "other"

    name = lifted["gen_ai.tool.name"] or lifted["gen_ai.request.model"] or raw.get("name")

    tokens: dict[str, int] = {}
    for field_name, token_key in (
        ("gen_ai.usage.input_tokens", "in"),
        ("gen_ai.usage.output_tokens", "out"),
    ):
        count = _as_int(lifted[field_name])
        if count is not None:
            tokens[token_key] = count

    code: dict[str, Any] | None = None
    code_keys = ("code.file.path", "code.function.name", "code.line.number")
    if any(lifted[key] is not None for key in code_keys):
        lineno = _as_int(lifted["code.line.number"])
        code = {
            "filepath": lifted["code.file.path"],
            "function": lifted["code.function.name"],
            "lineno": lineno if lineno is not None and lineno > 0 else None,
        }

    error, unclaimed_error_type = _otel_error(raw, lifted["error.type"])
    if unclaimed_error_type is not None:
        attrs[_ORIGINAL_ERROR_TYPE] = unclaimed_error_type

    return Span(
        span_id=_decode_id(_first(raw, "spanId", "span_id")) or "",
        parent_id=_decode_id(_first(raw, "parentSpanId", "parent_span_id")),
        kind=kind,
        name=str(name) if name is not None else "",
        start_ns=_nanos(_first(raw, "startTimeUnixNano", "start_time_unix_nano")) or 0,
        end_ns=_nanos(_first(raw, "endTimeUnixNano", "end_time_unix_nano")),
        error=error,
        code=code,
        tokens=tokens or None,
        attrs=attrs,
    )


def _cyclic_span_ids(spans: Iterable[Span]) -> set[str]:
    """The ids that lie on a parent cycle. Their descendants are orphans, and orphans survive."""
    by_id = {span.span_id: span for span in spans}
    cyclic: set[str] = set()
    for span in by_id.values():
        path: list[str] = []
        walked: set[str] = set()
        current: str | None = span.span_id
        while current is not None and current in by_id and current not in walked:
            walked.add(current)
            path.append(current)
            current = by_id[current].parent_id
        if current is not None and current in walked:
            cyclic.update(path[path.index(current):])
    return cyclic


def from_otel(payload: Mapping[str, Any] | Iterable[Mapping[str, Any]]) -> Trace:
    """Normalize an OTLP/JSON payload, or a flat iterable of span mappings, into a Trace.

    Unusable spans are dropped, counted and logged at WARNING on the ``proofload.trace``
    logger, one record per span: data loss is never silent and never fatal.
    """
    spans: list[Span] = []
    seen: set[str] = set()
    dropped = 0
    for raw, inherited in _iter_otel_spans(payload):
        source_id = _first(raw, "spanId", "span_id")
        label = source_id if isinstance(source_id, str) and source_id else "<no id>"
        span_id = _decode_id(source_id)
        reason: str | None = None
        if span_id is None:
            reason = "no_span_id"
        elif span_id in seen:
            reason = "duplicate_span_id"
        else:
            start = _nanos(_first(raw, "startTimeUnixNano", "start_time_unix_nano"))
            raw_end = _first(raw, "endTimeUnixNano", "end_time_unix_nano")
            end = None if raw_end is None else _nanos(raw_end)
            if start is None or (raw_end is not None and end is None):
                reason = "unparseable"
            elif end is not None and end < start:
                reason = "bad_timestamps"
        if reason is None:
            try:
                span = _otel_span(raw, inherited)
            except Exception:  # noqa: BLE001 - one unconvertible span is never fatal
                reason = "unparseable"
            else:
                seen.add(span.span_id)
                spans.append(span)
        if reason is not None:
            dropped += 1
            _LOG.warning("dropping OTel span %s: %s", label, reason)
    cyclic = _cyclic_span_ids(spans)
    if cyclic:
        # A parent cycle cannot be stored, and parent_id is never rewritten, so the spans on
        # the cycle go the same way as any other unusable span: dropped, counted, logged.
        for span in spans:
            if span.span_id in cyclic:
                dropped += 1
                _LOG.warning("dropping OTel span %s: %s", span.span_id, "unparseable")
        spans = [span for span in spans if span.span_id not in cyclic]
    return Trace(
        spans=tuple(spans),
        source="otel",
        source_version=OTEL_SEMCONV_VERSION,
        dropped=dropped,
    )


def _datetime_ns(value: Any) -> int | None:
    """Epoch nanoseconds from a LiteLLM timestamp, or None when it cannot be read.

    A naive datetime is read as local time, which is both Python's own convention for
    ``datetime.timestamp()`` and what LiteLLM's ``datetime.now()`` actually hands over;
    reading it as UTC would shift every span by the machine's offset.
    """
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.astimezone()
        delta = moment - _EPOCH
        return (delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1_000
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value * 1_000_000_000)
    return None


def from_litellm(payloads: Iterable[Mapping[str, Any]]) -> Trace:
    """One ``kind="llm"`` span per LiteLLM logging payload.

    Every span is a root: a LiteLLM callback sees LLM calls and nothing around them, so there
    is no parentage to recover and none is invented. Confidence is never derived here -- the
    logprobs ladder is M9's.
    """
    spans: list[Span] = []
    for payload in payloads:
        logged = payload.get("standard_logging_object")
        logged = logged if isinstance(logged, Mapping) else {}
        response = payload.get("response_obj")
        if not isinstance(response, Mapping):
            candidate = logged.get("response")
            response = candidate if isinstance(candidate, Mapping) else None
        usage = response.get("usage") if isinstance(response, Mapping) else None
        usage = usage if isinstance(usage, Mapping) else logged
        tokens: dict[str, int] = {}
        for source_key, token_key in (("prompt_tokens", "in"), ("completion_tokens", "out")):
            count = _as_int(usage.get(source_key))
            if count is not None:
                tokens[token_key] = count
        status = logged.get("status")
        failure = payload.get("exception") or payload.get("traceback_exception")
        model = payload.get("model") or logged.get("model")
        name = str(model) if model is not None else ""
        start_ns = _datetime_ns(payload.get("start_time"))
        if start_ns is None:
            _LOG.warning("LiteLLM payload %r has no readable start_time; using the epoch", name)
            start_ns = 0
        end_ns = _datetime_ns(payload.get("end_time"))
        if end_ns is not None and end_ns < start_ns:
            # Unrepresentable, and clamping would invent a zero-duration call. A span that was
            # never observed to close is exactly what end_ns=None means.
            _LOG.warning("LiteLLM payload %r ends before it starts; recording it as open", name)
            end_ns = None
        if failure is not None:
            error = str(failure)
        elif status in (None, "success"):
            error = None
        else:
            error = str(status)
        spans.append(
            Span(
                span_id=_new_span_id(),
                parent_id=None,
                kind="llm",
                name=name,
                start_ns=start_ns,
                end_ns=end_ns,
                input=payload.get("messages") or logged.get("messages"),
                output=response,
                tokens=tokens or None,
                error=error,
                attrs={},
            )
        )
    return Trace(spans=tuple(spans), source="litellm", source_version=None, dropped=0)
