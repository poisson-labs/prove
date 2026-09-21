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
import json
import logging
import re
import sys
import time
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

__all__ = [
    "ALIAS_MAP_VERSION",
    "ATTRIBUTE_ALIASES",
    "CONTENT_KEYS",
    "DROP_REASONS",
    "GATE",
    "KINDS",
    "LOGPROBS_KEY",
    "OBSERVATION_KEYS",
    "OBSERVATION_ROUTING_BYTES",
    "OTEL_KIND_MAP",
    "OTEL_SEMCONV_VERSION",
    "OUTCOME_BY",
    "SCHEMA",
    "SOURCES",
    "TRUNCATED_KEY",
    "Collector",
    "Span",
    "SpanHandle",
    "Trace",
    "TraceValidationError",
    "assemble",
    "collect",
    "finalize",
    "from_litellm",
    "from_otel",
    "merge",
    "record",
    "split",
    "step",
    "truncate_observations",
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

#: Who judged a span's ``outcome`` (ADR-053). A span whose emitter does not say carries None,
#: never a guess.
OUTCOME_BY: tuple[str, ...] = ("code", "llm", "self", "human")

#: How a span came to be a gate (ADR-074). ``"emitted"``: the target's own instrumentation marked
#: the span as a check its control flow consulted. ``"declared"``: the sweep's manifest names the
#: step as one -- which is why a span arriving with ``proofload.gate = "declared"`` is refused.
GATE: tuple[str, ...] = ("emitted", "declared")

#: The one place the semantic-convention pin is written (ADR-024). The GenAI conventions are
#: badged Development, so a stored trace records which vocabulary it was read under.
OTEL_SEMCONV_VERSION = "1.42.0"

#: Which alias map a stored ``from_otel`` trace was normalised under (CAP1). ``source_version``
#: names a *core* semconv release; the GenAI conventions live in
#: ``open-telemetry/semantic-conventions-genai``, which has no release, and the operation list
#: this module reads was taken at commit ``94f432d7``. What identifies the vocabulary is the map,
#: so the map gets the version.
#:
#: Bumped, with a visible diff, by any change to ``ATTRIBUTE_ALIASES``, ``OTEL_KIND_MAP``,
#: ``_VENDOR_KIND_MAPS``, ``_LIFTED_KEYS``, ``OBSERVATION_KEYS`` or ``CONTENT_KEYS``. The rule binds
#: from A8a forward: A7's observation keys, A8a's lifts and A8b's content keys are not bumps but
#: the state this value is first minted against.
ALIAS_MAP_VERSION: str = "1"

#: A21's surrogate field. An observation value like any other, and a member of
#: ``OBSERVATION_KEYS``: written here so the name a sweep declares and the name the split routes
#: on are the same string.
LOGPROBS_KEY = "proofload.logprobs"

#: The four prefix families of the observation table: a key *under* one of these is an
#: observation value, whatever follows the prefix. They are kept apart from the exact members
#: because no membership test can express them -- see ``_ObservationKeys``.
_OBSERVATION_PREFIXES: tuple[str, ...] = (
    "gen_ai.prompt.",
    "gen_ai.completion.",
    "llm.input_messages.",
    "llm.output_messages.",
)


class _ObservationKeys(frozenset[str]):
    """The observation table as one object: exact members *and* prefix families.

    A plain ``frozenset`` carries the eight exact keys and silently loses the four prefix rows,
    because a prefix rule is ``str.startswith`` and a set tests identity. Keeping the prefixes
    in a second private constant would work inside this module and hand every other reader of
    the public name an incomplete rule -- and the rule is the whole point, since it decides what
    leaves the envelope. So the set answers ``in`` for both, and stays a ``frozenset`` so the
    public annotation, ``isinstance`` and every set operation still hold.

    ``in`` is therefore wider than iteration: the members are the exact keys, and a prefixed key
    is a member by the rule rather than by enumeration. Set algebra (``&``, ``<=``) reads the
    members only, which is what a caller asking *which exact keys are these* means.
    """

    __slots__ = ()

    def __contains__(self, key: object) -> bool:
        if super().__contains__(key):
            return True
        return isinstance(key, str) and key.startswith(_OBSERVATION_PREFIXES)


#: Every attribute key whose value is observation content rather than envelope structure. These
#: leave the envelope at the store boundary so it stays bounded by step count alone (ADR-047).
#: The two routing stamps (``proofload.run_id``, ``proofload.episode``) are never observation
#: values whatever their size, and are not here.
OBSERVATION_KEYS: frozenset[str] = _ObservationKeys(
    {
        # GenAI semconv
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.tool.call.arguments",
        "gen_ai.tool.call.result",
        # Traceloop
        "traceloop.entity.input",
        "traceloop.entity.output",
        # OpenInference: the span's ``kind`` decides the class, never the membership
        "input.value",
        "output.value",
        # Proofload
        LOGPROBS_KEY,
    }
)

#: The two span fields that carry observation content. Named rather than derived, because they
#: are the only two of the span's fields that are content: every other one is structure.
_OBSERVATION_FIELDS: tuple[str, ...] = ("input", "output")

#: The two routing stamps, written here because they are read here. ``split`` and the cut both
#: have to exclude them by name, and core cannot import ``proofload.otel`` -- that module pulls
#: in the OTel SDK at import time. ``otel.py`` re-exports these two as its public
#: ``RUN_ID_KEY`` / ``EPISODE_KEY``, so the strings are still built in exactly one place.
_RUN_ID_KEY = "proofload.run_id"
_EPISODE_KEY = "proofload.episode"
_ROUTING_STAMPS: frozenset[str] = frozenset({_RUN_ID_KEY, _EPISODE_KEY})

#: The wrapper key a cut observation value is stored under (A8b). A value is a wrapper iff it
#: is a mapping whose *sole* key is this one -- detection is on the key and never on the shape.
TRUNCATED_KEY = "proofload.truncated"

#: The byte size at which ``split`` moves an attribute nobody named out of the envelope and
#: into ``trace_obs`` (ADR-090). **It decides which column a value is stored in and never
#: whether a value is cut.** There is no observation cap here or anywhere else in the package:
#: every run declares its own (ADR-096).
#:
#: The value is the one ADR-090's classification was measured at, and it does not move with the
#: rename: changing the number would be a storage-layout change wearing a rename's clothes.
OBSERVATION_ROUTING_BYTES: int = 8192

#: The six prompt/completion prefix families ``content = false`` strips, dotted. The bare family
#: names are exact members of ``CONTENT_KEYS`` below, because the shipped rule matched
#: ``key == prefix`` as well as a descendant and normalising to a trailing dot alone would stop
#: a bare ``gen_ai.prompt`` being stripped.
_CONTENT_PREFIXES: tuple[str, ...] = (
    "gen_ai.prompt.",
    "gen_ai.completion.",
    "traceloop.entity.input.",
    "traceloop.entity.output.",
    "llm.input_messages.",
    "llm.output_messages.",
)


class _ContentKeys(frozenset[str]):
    """``CONTENT_KEYS`` as one object: exact members *and* prefix families, on
    ``_ObservationKeys``'s shape and for its reason -- a plain ``frozenset`` carries the exact
    keys and silently loses the families, and the public name would hand every reader half a
    rule. ``in`` answers both; set algebra reads the exact members.
    """

    __slots__ = ()

    def __contains__(self, key: object) -> bool:
        if super().__contains__(key):
            return True
        return isinstance(key, str) and key.startswith(_CONTENT_PREFIXES)


#: Prompt and completion content, which never leaves the process unless ``content`` is on. The
#: two GenAI semconv keys, the two Traceloop entity families, the two ``gen_ai`` families and --
#: added by A8b (ADR-083) -- OpenInference's two flattened-message families, because a default
#: that strips a prompt in one convention's spelling and keeps it in another's is a gap left by
#: the order the conventions arrived in, not a default anyone chose.
#:
#: Tool arguments and results are **not** here and are retained by default; they are bounded by
#: the cut, not by the strip. ``input.value`` / ``output.value`` on an ``llm``-kind span are
#: prompt content under OpenInference and are **not** stripped: this is a key test, called
#: before a span's ``kind`` exists, and a kind-aware rule is not a membership test. That row is
#: owed to a later packet and is named rather than silently absent.
CONTENT_KEYS: frozenset[str] = _ContentKeys(
    {
        "gen_ai.input.messages",
        "gen_ai.output.messages",
        "gen_ai.prompt",
        "gen_ai.completion",
        "traceloop.entity.input",
        "traceloop.entity.output",
        "llm.input_messages",
        "llm.output_messages",
    }
)

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
        # Emitted by opentelemetry-util-genai and previously unmapped: fetch_response
        # retrieves a previously created response, execute_task is a framework's unit of
        # agent work. Both were landing in "other" (kind-ratio spike, 2026-09-04).
        "fetch_response": "llm",
        "execute_task": "agent",
    }
)

#: Conventions that are not OpenTelemetry's but carry most real agent instrumentation. They
#: decide ``kind`` only when no recognized ``gen_ai.operation.name`` is present. Both keys are
#: lifted -- the value lands in ``operation`` -- so the ladder reads them from the lifted values,
#: never from ``attrs``. Values are matched lowercased because the two conventions disagree on
#: case.
_VENDOR_KIND_MAPS: tuple[tuple[str, Mapping[str, str]], ...] = (
    (
        "openinference.span.kind",
        MappingProxyType(
            {
                "llm": "llm",
                "tool": "tool",
                "retriever": "retrieval",
                "embedding": "retrieval",
                "reranker": "retrieval",
                "agent": "agent",
                "chain": "agent",
            }
        ),
    ),
    (
        "traceloop.span.kind",
        MappingProxyType({"tool": "tool", "agent": "agent", "workflow": "agent", "task": "agent"}),
    ),
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
    "operation",
    "step_name",
    "outcome",
    "outcome_by",
    "attempt",
    "gate",
    "truncated",
    "bytes_original",
)
_SPAN_KEYS = frozenset(_SPAN_FIELDS)
_TRACE_FIELDS: tuple[str, ...] = (
    "schema",
    "source",
    "source_version",
    "dropped",
    "spans",
    "truncated",
    "alias_map_version",
)
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
    # A8a: the carriers of the eight span fields. graph.node.id and graph.node.parent_id are
    # deliberately absent -- they stay in attrs, because parent_id already carries parentage.
    "openinference.span.kind",
    "traceloop.span.kind",
    "graph.node.name",
    "proofload.step_name",
    "proofload.outcome",
    "proofload.outcome_by",
    "proofload.attempt",
    "proofload.gate",
)

#: An ``error.type`` on a span whose status is not an error travels under a key of Proofload's
#: own: the key it arrived under is lifted, T20 bans a lifted key from ``attrs``, and no span
#: field holds it. Dropping it instead would be silent data loss. (An unrecognized operation
#: name needed the same stash until A8a gave it ``operation``.)
_ORIGINAL_ERROR_TYPE = "proofload.error_type"

#: The two attributes ``_otel_span`` writes rather than reads: the OTel trace id a user's own
#: collector keys on, and the raw span status, which separates an instrumentor that sets ``OK``
#: from one that never sets a status. Neither is a field, because nothing groups by either.
_OTEL_TRACE_ID = "otel.trace_id"
_OTEL_STATUS_CODE = "otel.status_code"

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
    # A8a's eight. None on every one means *not recorded*, and no other default exists: a
    # reader asks ``is None``, never a truth test, because an empty-string outcome and an
    # unrecorded one are different facts (ADR-039).
    #: The source operation name, stripped and lowercased, never checked against a vocabulary.
    operation: str | None = None
    #: The logical step this span is an execution of (ADR-055). Never derived from ``name``.
    step_name: str | None = None
    #: The verdict a judge recorded, as a free label (ADR-039). None is never a pass.
    outcome: str | None = None
    #: Who judged ``outcome``: one of ``OUTCOME_BY``. Set only beside an ``outcome``.
    outcome_by: str | None = None
    #: Which try of ``step_name`` this is, from 1 (ADR-054, ADR-075). Read from an emitted
    #: counter, never derived from ordering, name repetition or nesting.
    attempt: int | None = None
    #: One of ``GATE`` when the span is a check the control flow consulted (ADR-074).
    gate: str | None = None
    #: ``"observation"`` when an observation value of this span was cut. A8a ships no writer.
    truncated: str | None = None
    #: The cut values' original byte lengths, summed; set only beside ``truncated``.
    bytes_original: int | None = None

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
        # The free-text four: a str or None, and nothing else is checked. ``operation`` in
        # particular is never held to a vocabulary (D7) -- that is what ``kind`` is for.
        for label, value in (
            ("operation", self.operation),
            ("step_name", self.step_name),
            ("outcome", self.outcome),
            ("truncated", self.truncated),
        ):
            if value is not None and not isinstance(value, str):
                raise TraceValidationError(
                    f"{label} must be a str or None, got {type(value).__name__}"
                )
        if self.outcome_by is not None:
            if self.outcome_by not in OUTCOME_BY:
                raise TraceValidationError(
                    f"outcome_by {self.outcome_by!r} is not one of {', '.join(OUTCOME_BY)}"
                )
            if self.outcome is None:
                raise TraceValidationError(
                    "outcome_by is set but outcome is None: nobody judged a verdict that was "
                    "not recorded"
                )
        if self.attempt is not None and not (_is_int(self.attempt) and self.attempt >= 1):
            raise TraceValidationError(
                f"attempt must be an int >= 1 or None, got {self.attempt!r}"
            )
        if self.gate is not None and self.gate not in GATE:
            raise TraceValidationError(f"gate {self.gate!r} is not one of {', '.join(GATE)}")
        if self.bytes_original is not None:
            if not (_is_int(self.bytes_original) and self.bytes_original >= 1):
                raise TraceValidationError(
                    f"bytes_original must be an int >= 1 or None, got {self.bytes_original!r}"
                )
            if self.truncated is None:
                raise TraceValidationError(
                    "bytes_original is set but truncated is None: nothing was cut"
                )

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
            "operation": self.operation,
            "step_name": self.step_name,
            "outcome": self.outcome,
            "outcome_by": self.outcome_by,
            "attempt": self.attempt,
            "gate": self.gate,
            "truncated": self.truncated,
            "bytes_original": self.bytes_original,
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
    #: ADR-028: why the forest stops where it does. ``"timeout"`` on the snapshot the executor
    #: drains from an episode it terminated; None on every trace a converter or the recorder
    #: builds. A trace-level fact, not a span-level one: a snapshot with no open span is
    #: otherwise indistinguishable from a complete trace, and a trace is meant to be readable
    #: without its row. A span's ``truncated`` is a different field with a different meaning.
    truncated: str | None = None
    #: ``ALIAS_MAP_VERSION`` on a trace ``from_otel`` built; None on the recorder's and
    #: ``from_litellm``'s, which read no alias map. Merges exactly as ``source_version`` does.
    alias_map_version: str | None = None

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
        if self.truncated is not None and not isinstance(self.truncated, str):
            raise TraceValidationError(
                f"truncated must be a str or None, got {type(self.truncated).__name__}"
            )
        if self.alias_map_version is not None and not isinstance(self.alias_map_version, str):
            raise TraceValidationError(
                "alias_map_version must be a str or None, "
                f"got {type(self.alias_map_version).__name__}"
            )
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
            "truncated": self.truncated,
            "alias_map_version": self.alias_map_version,
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
            truncated=checked["truncated"],
            alias_map_version=checked["alias_map_version"],
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
    # The alias map is the same kind of pin, so the same rule, never the first-wins rule below.
    maps = {trace.alias_map_version for trace in traces if trace.alias_map_version is not None}
    alias_map_version = maps.pop() if len(maps) == 1 else None
    # A cut anywhere is a cut of the whole: the first reason among the inputs, in argument
    # order, and never one the inputs did not carry.
    truncated = next((trace.truncated for trace in traces if trace.truncated is not None), None)
    return Trace(
        spans=tuple(spans),
        source="mixed",
        source_version=version,
        dropped=dropped,
        truncated=truncated,
        alias_map_version=alias_map_version,
    )


# ---------- the observation cut (A8b) ----------


def _byte_form(value: Any) -> bytes:
    """One observation value as bytes: a ``str`` is its UTF-8, anything else the UTF-8 of its
    canonical JSON. A value no encoder can reach falls back to ``str``, which is the posture
    the retired per-span budget took, kept so one exotic ``record()`` value that no encoder
    can serialise cannot cost a whole batch at the store boundary.
    """
    if isinstance(value, str):
        return value.encode("utf-8")
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        return str(value).encode("utf-8")


def _is_wrapper(value: Any) -> bool:
    """A value is already cut iff it is a mapping whose **sole** key is ``TRUNCATED_KEY``.

    On the key, never on the shape: a user observation that happens to be a dict with ``head``,
    ``tail`` and ``bytes_original`` keys is not a wrapper and is cut like anything else.
    """
    return isinstance(value, Mapping) and len(value) == 1 and TRUNCATED_KEY in value


def _longest_prefix(raw: bytes, bound: int) -> str:
    """The longest valid-UTF-8 prefix of ``raw`` no longer than ``bound`` bytes.

    A UTF-8 character is at most four bytes, so a character straddling the bound costs at most
    three bytes of back-off; the loop decodes strictly rather than with ``errors="ignore"``,
    which would drop the partial character and can swallow a valid one at some edges.
    """
    end = min(bound, len(raw))
    for n in range(end, max(end - 4, -1), -1):
        try:
            return raw[:n].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return ""


def _longest_suffix(raw: bytes, bound: int) -> str:
    """The mirror of ``_longest_prefix``: the longest valid suffix is found by *advancing* the
    start, not by retreating the end."""
    start = len(raw) - min(bound, len(raw))
    for begin in range(start, min(start + 4, len(raw) + 1)):
        try:
            return raw[begin:].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return ""


def _wrap(value: Any, limit: int) -> dict[str, Any]:
    """One over-limit value as its wrapper: head, tail and the original byte length.

    The bounds are the limit's split (ADR-082) -- ``limit - limit // 4`` and ``limit // 4``,
    which sum to exactly ``limit`` at every positive integer limit -- and not the two module
    constants, which are that split at the default and bound nothing anywhere else.
    """
    raw = _byte_form(value)
    return {
        TRUNCATED_KEY: {
            "head": _longest_prefix(raw, limit - limit // 4),
            "tail": _longest_suffix(raw, limit // 4),
            "bytes_original": len(raw),
        }
    }


def _is_observation(key: str, value: Any) -> bool:
    """Whether ``split`` routes one attribute out of the envelope.

    Three clauses, and the second is what keeps the store's classification and the child's cut
    in step at every limit: a value cut at a lowered sweep limit is a small wrapper, well under
    the routing size, and would otherwise ride back into the envelope. The two routing stamps
    are excluded by name and never by size -- a large stamp is still a stamp.
    """
    if key in OBSERVATION_KEYS:
        return True
    if key in _ROUTING_STAMPS:
        return False
    return _is_wrapper(value) or len(_byte_form(value)) > OBSERVATION_ROUTING_BYTES


def _cut_span(span: Span, limit: int) -> Span:
    """One span's observation values cut, with both span fields recomputed from the wrappers it
    carries afterwards. The same object back when nothing moved."""
    fields: dict[str, Any] = {}
    for name in _OBSERVATION_FIELDS:
        value = getattr(span, name)
        if value is not None and not _is_wrapper(value) and len(_byte_form(value)) > limit:
            fields[name] = _wrap(value, limit)
    attrs = dict(span.attrs)
    for key, value in span.attrs.items():
        if key in _ROUTING_STAMPS or _is_wrapper(value):
            continue
        if len(_byte_form(value)) > limit:
            attrs[key] = _wrap(value, limit)
    carried = [fields.get(name, getattr(span, name)) for name in _OBSERVATION_FIELDS]
    carried += list(attrs.values())
    wrappers = [value for value in carried if _is_wrapper(value)]
    if not wrappers:
        return span
    # Recomputed from the wrappers present, never accumulated: the accumulate spelling is
    # byte-identical on the first pass and doubles on the second.
    total = sum(int(value[TRUNCATED_KEY]["bytes_original"]) for value in wrappers)
    cut = replace(span, **fields, attrs=attrs, truncated="observation", bytes_original=total)
    return span if cut == span else cut


def truncate_observations(trace: Trace, *, limit: int | None) -> Trace:
    """Every observation value over ``limit`` bytes, stored as its head, its tail and its
    original byte length.

    The unit is **one observation value** -- ``input``, ``output`` and every attribute but the
    two routing stamps -- and not the span's whole ``attrs`` dict. A value at or under the limit
    is stored whole; a value already wrapped is never cut again; and the wrapper's head and tail
    sum to at most the limit, so a cut is always a reduction (ADR-082).

    ``limit`` is required and the caller always has one: every run declares what it keeps whole
    (ADR-096), and ``None`` is a declaration too -- *cut nothing*, either because the sweep said
    ``"none"`` or because it asked for no capture at all. The trace itself comes back in that
    case, as it does whenever nothing was cut, so an uncut trace is stored byte for byte as it
    arrived. ``0`` is not a spelling of *nothing*: a limit below one is refused.

    Idempotent, byte for byte, including each span's ``truncated`` and ``bytes_original``.
    """
    if limit is None:
        return trace
    if limit < 1:
        raise ValueError(
            f"truncate_observations(limit=...) must be an int >= 1 or None, got {limit!r}"
        )
    spans: list[Span] = []
    changed = False
    for span in trace.spans:
        cut = _cut_span(span, limit)
        changed = changed or cut is not span
        spans.append(cut)
    if not changed:
        return trace
    return replace(trace, spans=tuple(spans))


def finalize(trace: Trace, *, declaration: None, limit: int | None) -> Trace:
    """The one site a stored trace passes through before it is written.

    A8b mints it with ``declaration`` accepting ``None`` only and calls
    ``truncate_observations``; A10 widens the parameter to ``Declaration | None`` and fills the
    ``gate="declared"`` stamp in front of the cut. A non-``None`` declaration is **refused**
    rather than accepted and dropped, so the half that is not built is visible at the call site
    A10 will change instead of silently doing nothing.

    ``limit`` is the run's own, required and passed down unchanged. A8b left it to a module
    constant, so every stored row was cut at 8192 whatever its sweep file declared -- the
    funnel ran on every row of both backends while being described as a backstop for one path.
    """
    if declaration is not None:
        raise TypeError(
            "finalize(declaration=...) is A10's: A8b takes None only, got "
            f"{type(declaration).__name__}"
        )
    return truncate_observations(trace, limit=limit)


# ---------- the storage split (A7) ----------


def split(trace: Trace) -> tuple[dict[str, Any], dict[str, Any]]:
    """A trace's envelope and its observation bodies, as two JSON-native dicts.

    The envelope is a trace dict whose spans carry no ``input``, no ``output`` and no
    observation attribute; everything else about the trace is unchanged, so the envelope's size
    is bounded by step count and not by content (ADR-047). The bodies are keyed by ``span_id``,
    hold only the sub-keys that had a value, and carry no entry at all for a span that had none.

    An attribute is an observation by its key, by already carrying a cut value's wrapper, or by
    being over ``OBSERVATION_ROUTING_BYTES`` -- A8b widened the third clause in, so an attribute
    nobody named is still bounded if it is large enough to matter. The two routing stamps are
    excluded by name whatever their size. ``split`` classifies and moves; it never cuts.

    Neither the span key set nor the trace key set is spelled here: the envelope starts as
    ``trace.to_dict()`` and only the content fields are cleared, so a field added to ``Span``
    later rides through both directions without this function being touched.
    """
    envelope = trace.to_dict()
    bodies: dict[str, Any] = {}
    for span in envelope["spans"]:
        body: dict[str, Any] = {}
        for name in _OBSERVATION_FIELDS:
            if span[name] is not None:
                body[name] = span[name]
                span[name] = None
        # An observation attribute whose value is None is still observation content, and
        # leaving it behind puts a content key in the envelope.
        moved = {
            key: value
            for key, value in span["attrs"].items()
            if _is_observation(key, value)
        }
        if moved:
            body["attrs"] = moved
            span["attrs"] = {
                key: value for key, value in span["attrs"].items() if key not in moved
            }
        if body:
            bodies[span["span_id"]] = body
    return envelope, bodies


def assemble(envelope: Mapping[str, Any], obs: Mapping[str, Any] | None) -> Trace:
    """The inverse of ``split``: ``assemble(*split(t)).to_dict() == t.to_dict()`` for every valid
    ``t``. ``obs=None`` and ``obs={}`` are the same input and both mean no span had one."""
    bodies: Mapping[str, Any] = {} if obs is None else obs
    restored = dict(envelope)
    spans: list[dict[str, Any]] = []
    for raw in restored.get("spans", ()):
        span = dict(raw)
        span_id = span.get("span_id")
        body = bodies.get(span_id) if isinstance(span_id, str) else None
        if body:
            for name in _OBSERVATION_FIELDS:
                if name in body:
                    span[name] = body[name]
            if "attrs" in body:
                span["attrs"] = {**span.get("attrs", {}), **body["attrs"]}
        spans.append(span)
    restored["spans"] = spans
    return Trace.from_dict(restored)


# ---------- recording (tier 3 -- the floor, not the path) ----------


@dataclass
class SpanHandle:
    """The mutable handle a ``record()`` block yields. Assignments land on the closed span.

    The handle carries what is known *after* the block runs -- results, and a verdict is one.
    What is known before it opens (``step_name``, ``attempt``, ``gate``) is ``record()``'s.
    """

    input: Any | None = None
    output: Any | None = None
    tokens: Mapping[str, int] | None = None
    confidence: float | None = None
    error: str | None = None
    outcome: str | None = None
    outcome_by: str | None = None


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
    step_name: str | None = None,
    attempt: int | None = None,
    gate: str | None = None,
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
                # Hand-written on purpose, like the rest of this call: a field left out here
                # stays None with no error, so each of the five is spelled.
                step_name=step_name,
                attempt=attempt,
                gate=gate,
                outcome=handle.outcome,
                outcome_by=handle.outcome_by,
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
    step_name: str | None = None,
    attempt: int | None = None,
    gate: str | None = None,
) -> contextlib.AbstractContextManager[SpanHandle]:
    """Record one span for a call nothing else can see. A no-op outside ``collect()``.

    ``step_name``, ``attempt`` and ``gate`` are what the caller knows when the span opens: which
    logical step this is, which try of it (from 1, and only if the caller counted), and whether
    the step is a check the control flow consults (``gate="emitted"``). A verdict is known only
    after the block runs, so it goes on the handle: ``handle.outcome`` and
    ``handle.outcome_by``, the latter one of ``OUTCOME_BY`` and only beside an outcome.

    **A value the schema refuses loses the span, and never raises.** An ``attempt`` of 0, a
    ``gate`` outside ``GATE``, or ``handle.outcome_by = "robot"`` is logged at WARNING on the
    ``proofload.trace`` logger and the span is dropped -- the same no-crash rule as an unknown
    ``kind``, because a recorder must never displace the rollout's own result.

    The code location comes from ``sys._getframe``: ``inspect.stack()`` opens and reads the
    caller's source file on every call, which a recorder on a hot tool path cannot afford.
    """
    frame = sys._getframe(1)
    code = {
        "filepath": frame.f_code.co_filename,
        "function": frame.f_code.co_qualname,
        "lineno": frame.f_lineno,
    }
    return _span(kind, name, input, attrs, code, step_name, attempt, gate)


def _decorate(
    fn: Callable[..., Any], kind: str, name: str | None, step_name: str | None = None
) -> Callable[..., Any]:
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
            with _span(kind, span_name, None, None, code, step_name):
                return await fn(*args, **kwargs)

        return async_wrapper

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with _span(kind, span_name, None, None, code, step_name):
            return fn(*args, **kwargs)

    return wrapper


def step(
    kind: str | Callable[..., Any] = "tool",
    name: str | None = None,
    *,
    step_name: str | None = None,
) -> Callable[..., Any]:
    """Sugar over ``record()``. Usable bare (``@step``) or called (``@step(kind="db")``).

    The bare form arrives with the decorated function as the first positional argument, so
    ``callable(kind)`` is handled explicitly -- get this wrong and the bare form returns a
    partial and the user's tool stops being callable.

    ``step_name`` is the only one of ``record()``'s three new arguments a decorator takes: the
    decorated function *is* the step, while an attempt and a gate are facts about one call that
    a decorator cannot see.
    """
    if callable(kind):
        return _decorate(kind, "tool", None)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        return _decorate(fn, kind, name, step_name)

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


def _status_code(raw: Mapping[str, Any]) -> str:
    """``"OK"``, ``"UNSET"`` or ``"ERROR"``: the span's raw status, in either spelling OTLP/JSON
    uses (``STATUS_CODE_OK`` or the enum's integer). A span that carries no status is ``UNSET``,
    which is OpenTelemetry's own default and not an inference."""
    status = raw.get("status")
    code = status.get("code") if isinstance(status, Mapping) else None
    if (isinstance(code, str) and "ERROR" in code) or (_as_int(code) == 2):
        return "ERROR"
    if (isinstance(code, str) and code.strip().upper() in ("OK", "STATUS_CODE_OK")) or (
        _as_int(code) == 1
    ):
        return "OK"
    return "UNSET"


def _otel_error(raw: Mapping[str, Any], error_type: Any) -> tuple[str | None, str | None]:
    """``(error, unclaimed error.type)`` -- section 3 maps ``error`` from an ERROR status only."""
    status = raw.get("status")
    message = status.get("message") if isinstance(status, Mapping) else None
    is_error = _status_code(raw) == "ERROR"
    if not is_error:
        return None, None if error_type is None else str(error_type)
    if isinstance(message, str) and message:
        return message, None
    if error_type is not None:
        return str(error_type), None
    return "STATUS_CODE_ERROR", None


def _vendor_kind(lifted: Mapping[str, Any]) -> str | None:
    """The kind a non-OTel convention claims, or None. Never invents a kind for a value
    outside the tables -- an unknown one falls through to the rest of the ladder.

    Reads the *lifted* values: both vendor keys are in ``_LIFTED_KEYS`` and have already left
    ``attrs`` by the time the ladder runs, so passing ``attrs`` here would send every
    OpenInference and Traceloop span to ``"other"`` with no error.
    """
    for key, table in _VENDOR_KIND_MAPS:
        value = lifted.get(key)
        if isinstance(value, str):
            kind = table.get(value.strip().lower())
            if kind is not None:
                return kind
    return None


def _transport_kind(attrs: Mapping[str, Any]) -> str:
    """The last two rungs: what the span talked to, when nothing said what it was."""
    if "db.system" in attrs:
        return "db"
    if "http.request.method" in attrs or "url.full" in attrs:
        return "http"
    return "other"


def _otel_span(raw: Mapping[str, Any], inherited: Mapping[str, Any]) -> Span:
    flat = {**inherited, **_flatten_attributes(raw.get("attributes"))}
    attrs: dict[str, Any] = {}
    for key, value in flat.items():
        canonical = ATTRIBUTE_ALIASES.get(key, key)
        if canonical != key and canonical in flat:
            continue  # the source spelled the canonical key too; the deprecated one loses
        attrs[canonical] = value
    lifted = {key: attrs.pop(key, None) for key in _LIFTED_KEYS}
    source_id = _first(raw, "spanId", "span_id")
    label = source_id if isinstance(source_id, str) and source_id else "<no id>"

    source_operation = lifted["gen_ai.operation.name"]
    operation_name = None if source_operation is None else str(source_operation)
    if operation_name is not None and operation_name in OTEL_KIND_MAP:
        kind = OTEL_KIND_MAP[operation_name]
    else:
        kind = _vendor_kind(lifted) or _transport_kind(attrs)

    name =lifted["gen_ai.tool.name"] or lifted["gen_ai.request.model"] or raw.get("name")

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

    trace_id = _decode_id(_first(raw, "traceId", "trace_id"))
    if trace_id is not None:
        attrs[_OTEL_TRACE_ID] = trace_id
    attrs[_OTEL_STATUS_CODE] = _status_code(raw)

    outcome = _carried_str(label, "proofload.outcome", lifted["proofload.outcome"])
    return Span(
        span_id=_decode_id(source_id) or "",
        parent_id=_decode_id(_first(raw, "parentSpanId", "parent_span_id")),
        kind=kind,
        name=str(name) if name is not None else "",
        start_ns=_nanos(_first(raw, "startTimeUnixNano", "start_time_unix_nano")) or 0,
        end_ns=_nanos(_first(raw, "endTimeUnixNano", "end_time_unix_nano")),
        error=error,
        code=code,
        tokens=tokens or None,
        attrs=attrs,
        operation=_operation(lifted),
        step_name=_step_name(label, lifted),
        outcome=outcome,
        outcome_by=_outcome_by(label, lifted["proofload.outcome_by"], outcome),
        attempt=_attempt(label, lifted["proofload.attempt"]),
        gate=_gate(label, lifted),
    )


# ---------- A8a's carriers: one reader per field; a refused value is logged, not guessed ----------


def _carried_str(label: str, key: str, value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    _LOG.warning("OTel span %s: %s = %r is not a string; left unrecorded", label, key, value)
    return None


def _operation(lifted: Mapping[str, Any]) -> str | None:
    """The source operation name, verbatim but for ``strip().lower()``: the GenAI key when
    present, else OpenInference's span kind, else Traceloop's. Held to no vocabulary (D7)."""
    for key in ("gen_ai.operation.name", "openinference.span.kind", "traceloop.span.kind"):
        value = lifted[key]
        if value is not None:
            return str(value).strip().lower()
    return None


def _step_name(label: str, lifted: Mapping[str, Any]) -> str | None:
    """``graph.node.name``, else ``proofload.step_name`` (ADR-055). Never the span's name."""
    for key in ("graph.node.name", "proofload.step_name"):
        if lifted[key] is not None:
            return _carried_str(label, key, lifted[key])
    return None


def _outcome_by(label: str, value: Any, outcome: str | None) -> str | None:
    if value is None:
        return None
    if value not in OUTCOME_BY:
        _LOG.warning(
            "OTel span %s: proofload.outcome_by = %r is not one of %s; left unrecorded",
            label,
            value,
            ", ".join(OUTCOME_BY),
        )
        return None
    if outcome is None:
        _LOG.warning(
            "OTel span %s: proofload.outcome_by = %r arrived with no outcome; left unrecorded",
            label,
            value,
        )
        return None
    return str(value)


def _attempt(label: str, value: Any) -> int | None:
    """``proofload.attempt`` as the adapter wrote it: already 1-based, never re-based here."""
    if value is None:
        return None
    attempt = _as_int(value)
    if attempt is None or attempt < 1:
        _LOG.warning(
            "OTel span %s: proofload.attempt = %r is not an int >= 1; left unrecorded", label, value
        )
        return None
    return attempt


def _gate(label: str, lifted: Mapping[str, Any]) -> str | None:
    """``"emitted"`` for an OpenInference guardrail span or a span carrying
    ``proofload.gate = "emitted"``; otherwise None. Never inferred from the span's name.

    ``EVALUATOR`` is not a gate marker: an evaluator scores and may not gate, so the allowlist
    starts at one entry (spec A8a section 10 Q6). And a ``"declared"`` gate comes from the
    sweep's manifest, never from a span, so one arriving on the wire is dropped and logged.
    """
    gate: str | None = None
    vendor = lifted["openinference.span.kind"]
    if isinstance(vendor, str) and vendor.strip().lower() == "guardrail":
        gate = "emitted"
    wire = lifted["proofload.gate"]
    if wire == "emitted":
        gate = "emitted"
    elif wire == "declared":
        _LOG.warning(
            "OTel span %s: proofload.gate = 'declared' dropped; a declared gate comes from the "
            "manifest, not from a span",
            label,
        )
    elif wire is not None:
        _LOG.warning(
            "OTel span %s: proofload.gate = %r is not a value a span may carry; left unrecorded",
            label,
            wire,
        )
    return gate


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
        alias_map_version=ALIAS_MAP_VERSION,
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
