"""M12 -- Trace: the test oracle.

Generated from the invariants T1-T30 in "Proofload -- Spec M12 Trace" section 4. Session B
builds ``src/proofload/trace.py`` against this file and does not edit it.

Every test imports ``proofload.trace`` inside its own body rather than at module level, so
that the file collects (and every test fails honestly) while ``trace.py`` does not exist.
Strategy constants below are spelled from the spec, not read from the module, for the same
reason; T3 pins the module's tuples to them.

Reading notes for Session B, recorded here so the oracle is not re-litigated:

- Span-level validation (T3, T4, T6) and trace-level validation (T7, T8) are asserted at
  *both* the constructor and ``from_dict``. The spec says ``from_dict`` is the validator and
  also that "a Trace holding two spans ... is valid" of a constructed Trace; the package
  convention (``Episode``, ``EpisodeRecord``, ``RunManifest``) is ``__post_init__``
  validation, which satisfies both readings at once.
- T20 is asserted over every OTLP fixture, including the span whose ``gen_ai.operation.name``
  is unrecognized. Section 3 says that original is "preserved in attrs"; T20 says no lifted
  key appears in ``attrs``. Both hold if the original is preserved under a key that is not
  ``gen_ai.operation.name``; the unrecognized-operation test only checks the value survives
  somewhere in ``attrs``.
- The stored token shape ``{"in": ..., "out": ...}`` is taken from the section 3 example,
  which is the only place the spec spells it.
- T17 is two tests: the vacuous half (no clock call outside ``trace.py``) passes at baseline;
  the strong half (exactly one helper in ``trace.py`` making both calls) fails until Session B.
- T30's first clause maps to the two amended M10 tests by name. The fourth column
  (``duration_ms``) is not read by M10's ``assert_trace_lines``, so a second T30 test here
  sweeps the mock agent through ``cli.main`` and reads it.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import functools
import itertools
import json
import logging
import re
import sys
import time
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import proofload.cli as cli
from proofload.episode import Episode
from proofload.sampler import SweepSpec
from proofload.store import EpisodeRecord, RunManifest, Store

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "proofload"
TRACE_SOURCE = SRC / "trace.py"
CLI_SOURCE = SRC / "cli.py"
MOCK_AGENT_SOURCE = SRC / "examples" / "mock_agent.py"
QUICKSTART = ROOT / "examples" / "quickstart.toml"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "trace"

# ---------- spec constants (section 2 and 3), spelled here so the file collects at baseline ----------

SCHEMA_SPEC = "proofload.trace/1"
KINDS_SPEC = ("llm", "tool", "retrieval", "db", "http", "agent", "other")
SOURCES_SPEC = ("record", "otel", "litellm", "mixed")
DROP_REASONS_SPEC = ("no_span_id", "duplicate_span_id", "bad_timestamps", "unparseable")
OTEL_SEMCONV_VERSION_SPEC = "1.42.0"
LOGGER_NAME = "proofload.trace"
MOCK_EPOCH_NS_SPEC = 1_700_000_000_000_000_000
QUICKSTART_REPLICATES = 16

SPAN_KEYS = frozenset(
    {
        "span_id", "parent_id", "kind", "name", "start_ns", "end_ns",
        "input", "output", "tokens", "confidence", "error", "code", "attrs",
    }
)
TRACE_KEYS = frozenset({"schema", "source", "source_version", "dropped", "spans", "truncated"})
CODE_KEYS = frozenset({"filepath", "function", "lineno"})
LIFTED_KEYS = (
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
OTEL_KIND_MAP_SPEC = {
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
    # Added 2026-09-04 after the kind-ratio spike: both are emitted by
    # opentelemetry-util-genai 1.1b0 and were landing in "other".
    "fetch_response": "llm",
    "execute_task": "agent",
}
CLOCK_ATTRS = ("time_ns", "perf_counter_ns")

AGENT_ID = "b7ad6b7169203331"
CHAT_ID = "0af7651916cd43dd"
EPOCH = 1_756_900_000_000_000_000
STEP_LINE_RE = re.compile(r"^\s*\d+(?:\t[^\t]*){4}$")  # the same five columns M10 I15 reads, tab-delimited

# The section 3 example span, as a dict. Tests copy it with dict(...) before mutating.
SPAN_A: dict[str, Any] = {
    "span_id": CHAT_ID,
    "parent_id": AGENT_ID,
    "kind": "llm",
    "name": "gpt-4o-2024-08-06",
    "start_ns": EPOCH,
    "end_ns": EPOCH + 812_000_000,
    "input": {"messages": []},
    "output": {"choices": []},
    "tokens": {"in": 1200, "out": 85},
    "confidence": 0.91,
    "error": None,
    "code": {"filepath": "agent/planner.py", "function": "plan", "lineno": 88},
    "attrs": {"gen_ai.system": "openai", "proofload.run_id": "r-2026-09-03-a"},
}
SPAN_B: dict[str, Any] = {
    "span_id": AGENT_ID,
    "parent_id": None,
    "kind": "agent",
    "name": "plan",
    "start_ns": EPOCH - 1_000_000,
    "end_ns": EPOCH + 900_000_000,
    "input": None,
    "output": None,
    "tokens": None,
    "confidence": None,
    "error": None,
    "code": None,
    "attrs": {},
}


def trace_dict(*spans: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """A valid stored-shape trace dict around the given span dicts. Plain data, no logic."""
    d: dict[str, Any] = {
        "schema": SCHEMA_SPEC,
        "source": "otel",
        "source_version": OTEL_SEMCONV_VERSION_SPEC,
        "dropped": 0,
        "spans": [dict(s) for s in spans],
        "truncated": None,
    }
    d.update(overrides)
    return d


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def litellm_payloads() -> list[dict[str, Any]]:
    """The LiteLLM fixture with its ISO strings turned back into the datetimes LiteLLM passes."""
    payloads = load_fixture("litellm_calls.json")
    for p in payloads:
        p["start_time"] = datetime.fromisoformat(p["start_time"])
        p["end_time"] = datetime.fromisoformat(p["end_time"])
    return payloads


async def yield_to_loop() -> None:
    """One trip through the event loop with no wall-clock wait."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[None] = loop.create_future()
    loop.call_soon(fut.set_result, None)
    await fut


def _plain_tool(x: int) -> int:
    """Doubles its argument. Module-level so ``__name__ == __qualname__`` (T18 bare form)."""
    return 2 * x


# ---------- hypothesis strategies: JSON-native payloads only (section 7) ----------

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
            }
        )
    return spans


# ---------- T12: overlap is representable -- the reason the schema changed ----------


def test_t12_overlapping_sibling_spans_are_valid_round_trip_and_overlap_is_computable() -> None:
    from proofload.trace import Span, Trace

    # Two roots whose [start_ns, end_ns) intervals overlap by exactly 200 ms: a concurrent pair.
    a = Span(
        span_id="000000000000000a", parent_id=None, kind="tool", name="fetch_prices",
        start_ns=EPOCH + 100_000_000, end_ns=EPOCH + 500_000_000,
    )
    b = Span(
        span_id="000000000000000b", parent_id=None, kind="tool", name="fetch_stock",
        start_ns=EPOCH + 300_000_000, end_ns=EPOCH + 700_000_000,
    )
    tr = Trace(spans=(a, b), source="record")
    assert len(tr.spans) == 2
    assert tr.roots() == (a, b)

    decoded = Trace.from_dict(tr.to_dict())
    assert decoded == tr
    decoded_json = Trace.from_dict(json.loads(json.dumps(tr.to_dict())))
    assert decoded_json == tr

    da, db = decoded_json.ordered()
    assert (da.span_id, db.span_id) == ("000000000000000a", "000000000000000b")
    assert da.end_ns is not None and db.end_ns is not None
    overlap_ns = min(da.end_ns, db.end_ns) - max(da.start_ns, db.start_ns)
    assert overlap_ns == 200_000_000
    assert da.start_ns < db.start_ns < da.end_ns < db.end_ns


def test_t12_overlapping_parent_and_child_intervals_are_valid() -> None:
    from proofload.trace import Span, Trace

    # A child that outlives its parent (a fire-and-forget tool call) is still a valid trace.
    parent = Span(
        span_id="00000000000000aa", parent_id=None, kind="agent", name="plan",
        start_ns=EPOCH, end_ns=EPOCH + 100,
    )
    child = Span(
        span_id="00000000000000bb", parent_id="00000000000000aa", kind="tool", name="notify",
        start_ns=EPOCH + 50, end_ns=EPOCH + 150,
    )
    tr = Trace.from_dict(json.loads(json.dumps(Trace(spans=(child, parent), source="record").to_dict())))
    assert tr.children("00000000000000aa") == (tr.ordered()[1],)
    assert tr.ordered()[1].end_ns == EPOCH + 150 and tr.ordered()[0].end_ns == EPOCH + 100


# ---------- T1: schema id and exact key sets ----------


def test_t1_schema_constant_and_to_dict_schema() -> None:
    from proofload.trace import SCHEMA, Span, Trace

    assert SCHEMA == SCHEMA_SPEC
    assert Trace(spans=(), source="record").to_dict()["schema"] == SCHEMA
    assert Trace(spans=(Span.from_dict(SPAN_A),), source="otel").to_dict()["schema"] == SCHEMA


def test_t1_from_dict_rejects_another_schema_naming_the_value_found() -> None:
    from proofload.trace import Trace, TraceValidationError

    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(trace_dict(SPAN_A, schema="proofload.trace/2"))
    assert "proofload.trace/2" in str(info.value)
    with pytest.raises(TraceValidationError):
        Trace.from_dict(trace_dict(SPAN_A, schema=None))


def test_t1_from_dict_rejects_unknown_top_level_key_naming_it() -> None:
    from proofload.trace import Trace, TraceValidationError

    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(trace_dict(SPAN_A, task_id="checkout"))
    assert "task_id" in str(info.value)
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(trace_dict(SPAN_A, outcome="violated"))
    assert "outcome" in str(info.value)


def test_t1_from_dict_rejects_unknown_span_key_naming_it() -> None:
    from proofload.trace import Span, Trace, TraceValidationError

    for extra in ("latency_ms", "i", "attempts"):
        bad = dict(SPAN_A)
        bad[extra] = 1
        with pytest.raises(TraceValidationError) as info:
            Trace.from_dict(trace_dict(bad))
        assert extra in str(info.value), extra
        with pytest.raises(TraceValidationError) as info:
            Span.from_dict(bad)
        assert extra in str(info.value), extra


def test_t1_from_dict_rejects_a_missing_span_key() -> None:
    from proofload.trace import Trace, TraceValidationError

    bad = dict(SPAN_A)
    del bad["start_ns"]
    with pytest.raises(TraceValidationError):
        Trace.from_dict(trace_dict(bad))


# ---------- T2: JSON round-trip (property) ----------


@settings(max_examples=75, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    spans=span_forests(),
    source=st.sampled_from(SOURCES_SPEC),
    source_version=st.none() | st.text(min_size=1, max_size=8),
    dropped=st.integers(min_value=0, max_value=100),
)
def test_t2_json_round_trip(
    spans: list[dict[str, Any]], source: str, source_version: str | None, dropped: int
) -> None:
    from proofload.trace import Span, Trace

    tr = Trace(
        spans=tuple(Span(**d) for d in spans),
        source=source,
        source_version=source_version,
        dropped=dropped,
    )
    encoded = json.dumps(tr.to_dict())
    assert json.loads(encoded) == tr.to_dict()  # JSON-native: no tuples, no non-str keys
    assert Trace.from_dict(json.loads(encoded)) == tr


def test_t2_section_3_example_round_trips() -> None:
    from proofload.trace import Trace

    d = trace_dict(SPAN_B, SPAN_A)
    tr = Trace.from_dict(d)
    assert Trace.from_dict(json.loads(json.dumps(tr.to_dict()))) == tr
    assert tr.to_dict() == d


# ---------- T3: kind and source vocabularies ----------


def test_t3_constants_match_the_spec() -> None:
    from proofload.trace import DROP_REASONS, KINDS, SOURCES

    assert KINDS == KINDS_SPEC
    assert SOURCES == SOURCES_SPEC
    assert DROP_REASONS == DROP_REASONS_SPEC


def test_t3_bad_kind_raises_naming_kind_and_listing_kinds() -> None:
    from proofload.trace import Span, Trace, TraceValidationError

    with pytest.raises(TraceValidationError) as info:
        Span(span_id=CHAT_ID, parent_id=None, kind="function", name="x", start_ns=EPOCH, end_ns=None)
    assert "function" in str(info.value)
    for kind in KINDS_SPEC:
        assert kind in str(info.value), kind

    bad = dict(SPAN_A)
    bad["kind"] = "step"
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(trace_dict(bad))
    assert "step" in str(info.value)
    for kind in KINDS_SPEC:
        assert kind in str(info.value), kind


def test_t3_bad_source_raises_naming_source_and_listing_sources() -> None:
    from proofload.trace import Trace, TraceValidationError

    with pytest.raises(TraceValidationError) as info:
        Trace(spans=(), source="manual")
    assert "manual" in str(info.value)
    for source in SOURCES_SPEC:
        assert source in str(info.value), source

    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(trace_dict(SPAN_A, source="manual"))
    assert "manual" in str(info.value)
    for source in SOURCES_SPEC:
        assert source in str(info.value), source


def test_t3_every_kind_and_source_is_accepted() -> None:
    from proofload.trace import Span, Trace

    for kind in KINDS_SPEC:
        assert Span(span_id=CHAT_ID, parent_id=None, kind=kind, name="x", start_ns=EPOCH, end_ns=None).kind == kind
    for source in SOURCES_SPEC:
        assert Trace(spans=(), source=source).source == source


# ---------- T4: timestamps ----------


def test_t4_end_before_start_raises() -> None:
    from proofload.trace import Span, Trace, TraceValidationError

    with pytest.raises(TraceValidationError):
        Span(span_id=CHAT_ID, parent_id=None, kind="tool", name="x", start_ns=EPOCH, end_ns=EPOCH - 1)
    bad = dict(SPAN_A)
    bad["end_ns"] = bad["start_ns"] - 1
    with pytest.raises(TraceValidationError):
        Trace.from_dict(trace_dict(bad))


def test_t4_open_span_and_zero_length_span_are_valid() -> None:
    from proofload.trace import Span

    never_closed = Span(span_id=CHAT_ID, parent_id=None, kind="tool", name="x", start_ns=EPOCH, end_ns=None)
    assert never_closed.end_ns is None
    instant = Span(span_id=CHAT_ID, parent_id=None, kind="tool", name="x", start_ns=EPOCH, end_ns=EPOCH)
    assert instant.end_ns == instant.start_ns == EPOCH
    assert isinstance(instant.start_ns, int) and isinstance(instant.end_ns, int)


def test_t4_non_integer_timestamps_are_rejected_by_from_dict() -> None:
    from proofload.trace import Trace, TraceValidationError

    for value in ("1756900000000000000", 1756900000.5):
        bad = dict(SPAN_A)
        bad["start_ns"] = value
        with pytest.raises(TraceValidationError):
            Trace.from_dict(trace_dict(bad))


# ---------- T5: duration is derived; key sets are exact ----------


def test_t5_duration_ms_is_derived_exactly() -> None:
    from proofload.trace import Span

    closed = Span.from_dict(SPAN_A)
    assert closed.duration_ms == (SPAN_A["end_ns"] - SPAN_A["start_ns"]) / 1e6 == 812.0
    odd = Span(span_id=CHAT_ID, parent_id=None, kind="tool", name="x", start_ns=EPOCH, end_ns=EPOCH + 1_234_567)
    assert odd.duration_ms == 1_234_567 / 1e6
    open_span = Span(span_id=CHAT_ID, parent_id=None, kind="tool", name="x", start_ns=EPOCH, end_ns=None)
    assert open_span.duration_ms is None


def test_t5_span_to_dict_has_exactly_the_thirteen_keys() -> None:
    from proofload.trace import Span

    full = Span.from_dict(SPAN_A).to_dict()
    assert set(full) == SPAN_KEYS
    sparse = Span(span_id=CHAT_ID, parent_id=None, kind="tool", name="x", start_ns=EPOCH, end_ns=None).to_dict()
    assert set(sparse) == SPAN_KEYS
    for key in ("parent_id", "end_ns", "input", "output", "tokens", "confidence", "error", "code"):
        assert sparse[key] is None, key
    assert sparse["attrs"] == {}
    assert "latency_ms" not in full and "i" not in full


def test_t5_trace_to_dict_has_exactly_the_six_keys() -> None:
    from proofload.trace import Span, Trace

    assert set(Trace(spans=(), source="record").to_dict()) == TRACE_KEYS
    d = Trace(spans=(Span.from_dict(SPAN_A),), source="otel", source_version="1.42.0", dropped=2).to_dict()
    assert set(d) == TRACE_KEYS
    assert (d["source"], d["source_version"], d["dropped"]) == ("otel", "1.42.0", 2)
    assert d["spans"] == [SPAN_A]


# ---------- T6: code location ----------


def test_t6_code_is_none_or_exactly_the_three_keys() -> None:
    from proofload.trace import Span, Trace, TraceValidationError

    assert Span.from_dict(SPAN_A).code == {"filepath": "agent/planner.py", "function": "plan", "lineno": 88}
    assert Span.from_dict(SPAN_B).code is None
    unknown_line = dict(SPAN_A)
    unknown_line["code"] = {"filepath": "agent/planner.py", "function": "plan", "lineno": None}
    assert Span.from_dict(unknown_line).code["lineno"] is None

    bad_codes = [
        {"filepath": "a.py", "function": "f"},
        {"filepath": "a.py", "function": "f", "lineno": 1, "column": 2},
        {"file": "a.py", "function": "f", "lineno": 1},
        {"filepath": "a.py", "function": "f", "lineno": 0},
        {"filepath": "a.py", "function": "f", "lineno": -3},
        {},
    ]
    for code in bad_codes:
        with pytest.raises(TraceValidationError):
            Span(span_id=CHAT_ID, parent_id=None, kind="tool", name="x", start_ns=EPOCH, end_ns=None, code=code)
        bad = dict(SPAN_A)
        bad["code"] = code
        with pytest.raises(TraceValidationError):
            Trace.from_dict(trace_dict(bad))


# ---------- T7: unique span ids ----------


def test_t7_duplicate_span_id_raises_naming_the_id() -> None:
    from proofload.trace import Span, Trace, TraceValidationError

    a = Span.from_dict(SPAN_A)
    twin = dict(SPAN_A)
    twin["name"] = "another"
    with pytest.raises(TraceValidationError) as info:
        Trace(spans=(a, Span.from_dict(twin)), source="otel")
    assert CHAT_ID in str(info.value)
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(trace_dict(SPAN_A, twin))
    assert CHAT_ID in str(info.value)


# ---------- T8: acyclic parentage ----------


def test_t8_self_parent_raises() -> None:
    from proofload.trace import Span, Trace, TraceValidationError

    with pytest.raises(TraceValidationError):
        Trace(
            spans=(Span(span_id=CHAT_ID, parent_id=CHAT_ID, kind="tool", name="x", start_ns=EPOCH, end_ns=None),),
            source="record",
        )
    loop = dict(SPAN_A)
    loop["parent_id"] = CHAT_ID
    with pytest.raises(TraceValidationError):
        Trace.from_dict(trace_dict(loop))


def test_t8_two_and_three_cycles_raise() -> None:
    from proofload.trace import Span, Trace, TraceValidationError

    def span(sid: str, parent: str) -> Span:
        return Span(span_id=sid, parent_id=parent, kind="tool", name=sid, start_ns=EPOCH, end_ns=None)

    with pytest.raises(TraceValidationError):
        Trace(spans=(span("000000000000000a", "000000000000000b"), span("000000000000000b", "000000000000000a")), source="record")
    three = [
        span("000000000000000a", "000000000000000b"),
        span("000000000000000b", "000000000000000c"),
        span("000000000000000c", "000000000000000a"),
    ]
    with pytest.raises(TraceValidationError):
        Trace(spans=tuple(three), source="record")
    with pytest.raises(TraceValidationError):
        Trace.from_dict(trace_dict(*(s.to_dict() for s in three), source="record"))


# ---------- T9: orphans are preserved ----------


def test_t9_orphan_parent_id_is_kept_and_the_span_is_a_root() -> None:
    from proofload.trace import Trace

    # SPAN_A's parent is AGENT_ID, which is not in this trace.
    tr = Trace.from_dict(trace_dict(SPAN_A))
    orphan = tr.spans[0]
    assert orphan.parent_id == AGENT_ID
    assert tr.roots() == (orphan,)
    again = Trace.from_dict(json.loads(json.dumps(tr.to_dict())))
    assert again.spans[0].parent_id == AGENT_ID
    assert again.roots() == (again.spans[0],)
    assert again.to_dict()["spans"][0]["parent_id"] == AGENT_ID


# ---------- T10: children ----------


def test_t10_children_are_exact_and_in_ordered_order() -> None:
    from proofload.trace import Span, Trace

    def span(sid: str, parent: str | None, start: int) -> Span:
        return Span(span_id=sid, parent_id=parent, kind="tool", name=sid, start_ns=start, end_ns=None)

    root = span("0000000000000001", None, EPOCH)
    late = span("0000000000000002", "0000000000000001", EPOCH + 30)
    early = span("0000000000000003", "0000000000000001", EPOCH + 10)
    tie_hi = span("00000000000000ff", "0000000000000001", EPOCH + 20)
    tie_lo = span("0000000000000010", "0000000000000001", EPOCH + 20)
    grandchild = span("0000000000000004", "0000000000000002", EPOCH + 40)
    tr = Trace(spans=(grandchild, late, tie_hi, root, early, tie_lo), source="record")
    assert tr.children("0000000000000001") == (early, tie_lo, tie_hi, late)
    assert tr.children("0000000000000002") == (grandchild,)
    assert tr.children("0000000000000004") == ()
    assert tr.children("no-such-span") == ()


# ---------- T11: ordered() is total and deterministic ----------


def test_t11_ordered_sorts_by_start_then_span_id() -> None:
    from proofload.trace import Span, Trace

    def span(sid: str, start: int) -> Span:
        return Span(span_id=sid, parent_id=None, kind="tool", name=sid, start_ns=start, end_ns=None)

    spans = [
        span("00000000000000ff", EPOCH + 5),
        span("0000000000000001", EPOCH + 9),
        span("0000000000000000", EPOCH + 5),
        span("00000000000000aa", EPOCH),
    ]
    expected = (spans[3], spans[2], spans[0], spans[1])
    assert Trace(spans=tuple(spans), source="record").ordered() == expected
    assert Trace(spans=tuple(reversed(spans)), source="record").ordered() == expected


@settings(max_examples=75, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(spans=span_forests(), data=st.data())
def test_t11_ordered_is_independent_of_input_order(spans: list[dict[str, Any]], data: st.DataObject) -> None:
    from proofload.trace import Span, Trace

    built = [Span(**d) for d in spans]
    shuffled = data.draw(st.permutations(built))
    expected = tuple(sorted(built, key=lambda s: (s.start_ns, s.span_id)))
    assert Trace(spans=tuple(built), source="record").ordered() == expected
    assert Trace(spans=tuple(shuffled), source="record").ordered() == expected
    assert len(expected) == len(built)


# ---------- T13: record() inside collect() ----------


def test_t13_one_record_appends_exactly_one_span() -> None:
    from proofload.trace import collect, record

    with collect() as c:
        with record("tool", "search_catalog", input={"q": "boots"}, attrs={"attempts": 1}) as h:
            h.output = {"hits": 3}
    tr = c.trace
    assert len(tr.spans) == 1
    span = tr.spans[0]
    assert (span.kind, span.name) == ("tool", "search_catalog")
    assert span.input == {"q": "boots"}
    assert span.output == {"hits": 3}
    assert dict(span.attrs) == {"attempts": 1}
    assert span.parent_id is None and tr.roots() == (span,)
    assert span.end_ns is not None and span.end_ns >= span.start_ns
    assert tr.source == "record" and tr.dropped == 0


def test_t13_nested_record_gets_the_enclosing_span_as_parent() -> None:
    from proofload.trace import collect, record

    with collect() as c:
        with record("agent", "outer") as outer:
            with record("tool", "inner") as inner:
                inner.output = {"rows": 3}
                inner.tokens = {"in": 1, "out": 2}
                inner.confidence = 0.5
            outer.output = "done"
    tr = c.trace
    assert len(tr.spans) == 2
    by_name = {s.name: s for s in tr.spans}
    assert by_name["inner"].parent_id == by_name["outer"].span_id
    assert by_name["outer"].parent_id is None
    assert tr.roots() == (by_name["outer"],)
    assert tr.children(by_name["outer"].span_id) == (by_name["inner"],)
    assert by_name["outer"].output == "done"
    assert by_name["inner"].output == {"rows": 3}
    assert dict(by_name["inner"].tokens or {}) == {"in": 1, "out": 2}
    assert by_name["inner"].confidence == 0.5
    assert by_name["inner"].error is None
    assert by_name["outer"].start_ns <= by_name["inner"].start_ns
    assert by_name["inner"].end_ns is not None and by_name["outer"].end_ns is not None
    assert by_name["inner"].end_ns <= by_name["outer"].end_ns


def test_t13_sequential_records_are_siblings_and_the_trace_round_trips() -> None:
    from proofload.trace import Trace, collect, record

    with collect() as c:
        with record("tool", "first"):
            pass
        with record("tool", "second"):
            pass
    tr = c.trace
    assert [s.name for s in tr.ordered()] == ["first", "second"]
    assert all(s.parent_id is None for s in tr.spans)
    assert Trace.from_dict(json.loads(json.dumps(tr.to_dict()))) == tr


def test_t13_collector_trace_read_before_exit_raises() -> None:
    from proofload.trace import TraceValidationError, collect, record

    with collect() as c:
        with pytest.raises(TraceValidationError):
            _ = c.trace
        with record("tool", "x"):
            with pytest.raises(TraceValidationError):
                _ = c.trace
    assert len(c.trace.spans) == 1


# ---------- T14: record() outside collect() is a silent no-op ----------


def test_t14_record_outside_collect_is_a_usable_no_op() -> None:
    from proofload.trace import collect, record

    with record("tool", "orphan", input={"q": 1}, attrs={"k": 1}) as h:
        h.output = {"rows": 2}
        h.tokens = {"in": 1, "out": 1}
        h.confidence = 0.4
        h.error = None
    assert h.output == {"rows": 2}
    assert h.tokens == {"in": 1, "out": 1}
    assert h.confidence == 0.4
    with collect() as c:
        pass
    assert c.trace.spans == ()


def test_t14_exception_inside_record_outside_collect_still_propagates_unchanged() -> None:
    from proofload.trace import record

    exc = KeyError("missing")
    with pytest.raises(KeyError) as info:
        with record("tool", "orphan"):
            raise exc
    assert info.value is exc


# ---------- T15: exceptions ----------


def test_t15_exception_sets_error_closes_span_and_reraises_the_same_object() -> None:
    from proofload.trace import collect, record

    class Boom(RuntimeError):
        pass

    exc = Boom("kaboom")
    with collect() as c:
        with pytest.raises(Boom) as info:
            with record("tool", "explode"):
                raise exc
    assert info.value is exc
    span = c.trace.spans[0]
    assert span.error == "Boom: kaboom"
    assert span.end_ns is not None and span.end_ns >= span.start_ns


def test_t15_exception_inside_a_decorated_function_behaves_the_same() -> None:
    from proofload.trace import collect, step

    exc = ValueError("bad input")

    @step(kind="tool", name="parse")
    def parse() -> None:
        raise exc

    with collect() as c:
        with pytest.raises(ValueError) as info:
            parse()
    assert info.value is exc
    span = c.trace.spans[0]
    assert span.name == "parse"
    assert span.error == "ValueError: bad input"
    assert span.end_ns is not None and span.end_ns >= span.start_ns


def test_t15_nested_exception_closes_both_spans_outermost_last() -> None:
    from proofload.trace import collect, record

    with collect() as c:
        with pytest.raises(RuntimeError):
            with record("agent", "outer"):
                with record("tool", "inner"):
                    raise RuntimeError("inner failed")
    by_name = {s.name: s for s in c.trace.spans}
    assert by_name["inner"].error == "RuntimeError: inner failed"
    assert by_name["outer"].error == "RuntimeError: inner failed"
    assert by_name["inner"].end_ns is not None and by_name["outer"].end_ns is not None
    assert by_name["inner"].end_ns <= by_name["outer"].end_ns


# ---------- T16: monotonic close under a backwards-stepping wall clock (ADR-023) ----------


def test_t16_end_ns_is_not_below_start_ns_when_the_wall_clock_steps_back(monkeypatch: pytest.MonkeyPatch) -> None:
    from proofload.trace import collect, record

    wall = itertools.count(EPOCH, -1_000_000_000)  # every read is one second earlier than the last
    mono = itertools.count(5_000_000_000, 250_000)  # every read is 250 us later than the last
    monkeypatch.setattr(time, "time_ns", functools.partial(next, wall))
    monkeypatch.setattr(time, "perf_counter_ns", functools.partial(next, mono))

    with collect() as c:
        with record("tool", "clock"):
            with record("tool", "inner"):
                pass
    for span in c.trace.spans:
        assert span.end_ns is not None
        assert span.end_ns >= span.start_ns, (span.name, span.start_ns, span.end_ns)
        assert span.start_ns <= EPOCH and span.start_ns % 1_000_000_000 == 0  # opened on the wall clock


# ---------- T17: the span clock is one helper (ADR-023 enforced) ----------


def clock_call_sites(path: Path) -> list[tuple[str, str]]:
    """(innermost enclosing function, attr) for every ``time.time_ns()`` / ``time.perf_counter_ns()``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    owner: dict[ast.AST, str] = {}

    def walk(node: ast.AST, name: str) -> None:
        for child in ast.iter_child_nodes(node):
            child_name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else name
            owner[child] = child_name
            walk(child, child_name)

    walk(tree, "<module>")
    sites: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        func = node.func
        if isinstance(func.value, ast.Name) and func.value.id == "time" and func.attr in CLOCK_ATTRS:
            sites.append((owner.get(node, "<module>"), func.attr))
    return sites


def clock_names_imported_from_time(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "time"
        for alias in node.names
        if alias.name in CLOCK_ATTRS
    ]


def test_t17_no_module_outside_trace_py_reads_the_span_clock() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path == TRACE_SOURCE:
            continue
        offenders.extend((path.name, attr) for _, attr in clock_call_sites(path))
        offenders.extend((path.name, name) for name in clock_names_imported_from_time(path))
    assert offenders == [], offenders


def test_t17_trace_py_reads_both_clocks_inside_exactly_one_helper() -> None:
    assert TRACE_SOURCE.is_file(), "src/proofload/trace.py does not exist"
    assert clock_names_imported_from_time(TRACE_SOURCE) == []
    sites = clock_call_sites(TRACE_SOURCE)
    assert sites, "trace.py never reads time.time_ns() or time.perf_counter_ns()"
    helpers = {owner for owner, _ in sites}
    assert len(helpers) == 1 and "<module>" not in helpers, sites
    assert {attr for _, attr in sites} == set(CLOCK_ATTRS), sites


# ---------- T18: step ----------


def test_t18_step_bare_form_records_one_span_and_preserves_metadata() -> None:
    from proofload.trace import collect, step

    decorated = step(_plain_tool)  # what ``@step`` does
    assert decorated.__name__ == "_plain_tool"
    assert decorated.__doc__ == _plain_tool.__doc__
    assert decorated.__wrapped__ is _plain_tool
    with collect() as c:
        assert decorated(21) == 42
    assert len(c.trace.spans) == 1
    span = c.trace.spans[0]
    assert (span.kind, span.name) == ("tool", "_plain_tool")
    assert span.end_ns is not None and span.error is None


def test_t18_step_called_form_sets_kind_and_name() -> None:
    from proofload.trace import collect, step

    decorated = step(kind="db", name="lookup_order")(_plain_tool)
    assert decorated.__name__ == "_plain_tool" and decorated.__wrapped__ is _plain_tool
    with collect() as c:
        assert decorated(2) == 4
        assert decorated(3) == 6
    assert [(s.kind, s.name) for s in c.trace.ordered()] == [("db", "lookup_order"), ("db", "lookup_order")]


def test_t18_decorated_coroutine_produces_one_span_spanning_its_awaits() -> None:
    from proofload.trace import collect, record, step

    async def run_agent() -> str:
        await yield_to_loop()
        with record("tool", "inner"):
            await yield_to_loop()
        await yield_to_loop()
        return "ok"

    decorated = step(kind="agent", name="run_agent")(run_agent)
    assert decorated.__wrapped__ is run_agent
    with collect() as c:
        assert asyncio.run(decorated()) == "ok"
    by_name = {s.name: s for s in c.trace.spans}
    assert set(by_name) == {"run_agent", "inner"}
    outer, inner = by_name["run_agent"], by_name["inner"]
    assert outer.kind == "agent" and outer.parent_id is None
    assert inner.parent_id == outer.span_id
    assert outer.end_ns is not None and inner.end_ns is not None
    assert outer.start_ns <= inner.start_ns and inner.end_ns <= outer.end_ns
    assert c.trace.roots() == (outer,)


def test_t18_decorated_functions_outside_collect_return_normally_and_record_nothing() -> None:
    from proofload.trace import collect, step

    sync_tool = step(_plain_tool)
    assert sync_tool(5) == 10

    async def coro(x: int) -> int:
        await yield_to_loop()
        return x + 1

    async_tool = step(kind="agent")(coro)
    assert asyncio.run(async_tool(1)) == 2

    with collect() as c:
        pass
    assert c.trace.spans == ()


# ---------- T19: concurrency ----------


def test_t19_concurrent_tasks_nest_independently_in_one_trace() -> None:
    from proofload.trace import collect, record

    async def worker(tag: str, mine: asyncio.Event, other: asyncio.Event) -> None:
        with record("agent", f"outer_{tag}"):
            mine.set()
            await other.wait()  # both outer spans are open before either inner span opens
            with record("tool", f"inner_{tag}"):
                await yield_to_loop()
                await yield_to_loop()

    async def main() -> None:
        a_open, b_open = asyncio.Event(), asyncio.Event()
        task_a = asyncio.create_task(worker("a", a_open, b_open))
        task_b = asyncio.create_task(worker("b", b_open, a_open))
        await asyncio.gather(task_a, task_b)

    with collect() as c:
        asyncio.run(main())

    tr = c.trace
    by_name = {s.name: s for s in tr.spans}
    assert set(by_name) == {"outer_a", "inner_a", "outer_b", "inner_b"}
    assert by_name["inner_a"].parent_id == by_name["outer_a"].span_id
    assert by_name["inner_b"].parent_id == by_name["outer_b"].span_id
    assert by_name["outer_a"].parent_id is None and by_name["outer_b"].parent_id is None
    assert {s.span_id for s in tr.roots()} == {by_name["outer_a"].span_id, by_name["outer_b"].span_id}
    assert tr.children(by_name["outer_a"].span_id) == (by_name["inner_a"],)
    assert tr.children(by_name["outer_b"].span_id) == (by_name["inner_b"],)
    for span in tr.spans:
        assert span.end_ns is not None and span.end_ns >= span.start_ns, span.name


# ---------- T20: no un-normalized key reaches the store (ADR-024) ----------


def test_t20_no_alias_or_lifted_key_survives_in_attrs_across_every_otlp_fixture() -> None:
    from proofload.trace import ATTRIBUTE_ALIASES, from_otel

    assert ATTRIBUTE_ALIASES["code.filepath"] == "code.file.path"
    payloads = [
        load_fixture("otlp_agent_chat.json"),
        load_fixture("otlp_kinds.json"),
        load_fixture("otlp_aliases.json"),
        load_fixture("otlp_dropped.json"),
        *load_fixture("otlp_encodings.json").values(),
    ]
    seen = 0
    for payload in payloads:
        for span in from_otel(payload).spans:
            seen += 1
            for key in ATTRIBUTE_ALIASES:
                assert key not in span.attrs, (span.span_id, key)
            for key in LIFTED_KEYS:
                assert key not in span.attrs, (span.span_id, key)
    assert seen >= 20


def test_t20_every_alias_key_is_absorbed_when_it_arrives_alone() -> None:
    from proofload.trace import ATTRIBUTE_ALIASES, from_otel

    assert len(ATTRIBUTE_ALIASES) >= 1
    for source_key, canonical in ATTRIBUTE_ALIASES.items():
        numeric = "tokens" in canonical or "line" in canonical
        value = {"intValue": "7"} if numeric else {"stringValue": "aliased"}
        payload = [
            {
                "spanId": CHAT_ID,
                "name": "chat",
                "startTimeUnixNano": str(EPOCH),
                "endTimeUnixNano": str(EPOCH + 1000),
                "attributes": [{"key": source_key, "value": value}],
            }
        ]
        tr = from_otel(payload)
        assert len(tr.spans) == 1 and tr.dropped == 0, source_key
        assert source_key not in tr.spans[0].attrs, source_key


def test_t20_deprecated_code_filepath_is_lifted_into_code() -> None:
    from proofload.trace import from_otel

    tr = from_otel(load_fixture("otlp_aliases.json"))
    assert len(tr.spans) == 1 and tr.dropped == 0
    span = tr.spans[0]
    assert span.code == {"filepath": "agent/tools.py", "function": "search", "lineno": 41}
    assert span.kind == "tool" and span.name == "search"
    assert dict(span.tokens or {}) == {"in": 7, "out": 3}
    assert span.attrs["proofload.run_id"] == "r-aliases"
    assert "code.filepath" not in span.attrs and "code.file.path" not in span.attrs


# ---------- T21: encoding-agnostic ----------


def test_t21_same_span_three_encodings_yield_equal_traces() -> None:
    from proofload.trace import from_otel

    variants = load_fixture("otlp_encodings.json")
    assert set(variants) == {"camel_string_base64", "snake_int_hex", "camel_int_hex"}
    # Guard the fixture itself: the base64 ids are the hex ids.
    b64 = variants["camel_string_base64"][0]
    assert base64.b64decode(b64["spanId"]).hex() == CHAT_ID
    assert base64.b64decode(b64["parentSpanId"]).hex() == AGENT_ID
    assert isinstance(b64["startTimeUnixNano"], str)
    assert isinstance(variants["snake_int_hex"][0]["start_time_unix_nano"], int)

    traces = {name: from_otel(payload) for name, payload in variants.items()}
    assert traces["camel_string_base64"] == traces["snake_int_hex"] == traces["camel_int_hex"]
    tr = traces["snake_int_hex"]
    assert len(tr.spans) == 1 and tr.dropped == 0
    span = tr.spans[0]
    assert span.span_id == CHAT_ID and span.parent_id == AGENT_ID
    assert span.start_ns == EPOCH + 100_000_000 and span.end_ns == EPOCH + 912_000_000
    assert span.kind == "llm" and span.name == "gpt-4o"
    assert dict(span.tokens or {}) == {"in": 12, "out": 4}
    assert tr.roots() == (span,)  # the parent is not in this payload: an orphan, preserved


def test_t21_uppercase_hex_ids_are_canonicalized_to_lowercase() -> None:
    from proofload.trace import from_otel

    upper = json.loads(json.dumps(load_fixture("otlp_encodings.json")["camel_int_hex"]))
    upper[0]["spanId"] = CHAT_ID.upper()
    upper[0]["parentSpanId"] = AGENT_ID.upper()
    span = from_otel(upper).spans[0]
    assert span.span_id == CHAT_ID and span.parent_id == AGENT_ID


# ---------- T22: unusable spans are dropped, counted and logged ----------


def test_t22_dropped_spans_are_counted_and_each_is_logged_once_at_warning(caplog: pytest.LogCaptureFixture) -> None:
    from proofload.trace import DROP_REASONS, from_otel

    payload = load_fixture("otlp_dropped.json")
    assert len(payload) == 6
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    tr = from_otel(payload)

    assert tr.dropped == 4
    assert len(tr.spans) == 6 - 4
    assert {s.span_id for s in tr.spans} == {"0000000000000001", "0000000000000002"}

    records = [r for r in caplog.records if r.name == LOGGER_NAME and r.levelno == logging.WARNING]
    assert len(records) == 4, [r.getMessage() for r in caplog.records]
    assert not [r for r in caplog.records if r.levelno > logging.WARNING]
    messages = [r.getMessage() for r in records]
    for message in messages:
        assert any(reason in message for reason in DROP_REASONS), message
    assert any("<no id>" in m for m in messages), messages
    for source_id in ("0000000000000001", "0000000000000005", "0000000000000006"):
        assert any(source_id in m for m in messages), (source_id, messages)


def test_t22_all_spans_unusable_is_an_empty_trace_not_an_error(caplog: pytest.LogCaptureFixture) -> None:
    from proofload.trace import from_otel

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    payload = [
        {"name": "no id", "startTimeUnixNano": str(EPOCH), "endTimeUnixNano": str(EPOCH + 1)},
        {"spanId": CHAT_ID, "name": "backwards", "startTimeUnixNano": str(EPOCH + 1), "endTimeUnixNano": str(EPOCH)},
    ]
    tr = from_otel(payload)
    assert tr.spans == () and tr.dropped == 2
    assert tr.source == "otel"
    assert len([r for r in caplog.records if r.name == LOGGER_NAME and r.levelno == logging.WARNING]) == 2


def test_t22_a_clean_payload_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    from proofload.trace import from_otel

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    tr = from_otel(load_fixture("otlp_agent_chat.json"))
    assert tr.dropped == 0 and len(tr.spans) == 2
    assert [r for r in caplog.records if r.name == LOGGER_NAME] == []


# ---------- T23: parentage and resource attributes survive from_otel ----------


def test_t23_chat_under_invoke_agent_and_resource_attrs_survive() -> None:
    from proofload.trace import from_otel

    tr = from_otel(load_fixture("otlp_agent_chat.json"))
    assert tr.source == "otel" and tr.dropped == 0 and len(tr.spans) == 2
    by_id = {s.span_id: s for s in tr.spans}
    agent, chat = by_id[AGENT_ID], by_id[CHAT_ID]
    assert agent.kind == "agent" and chat.kind == "llm"
    assert chat.parent_id == AGENT_ID and agent.parent_id is None
    assert tr.children(AGENT_ID) == (chat,)
    assert tr.roots() == (agent,)
    for span in tr.spans:
        assert span.attrs["proofload.run_id"] == "r-2026-09-03-a", span.span_id
        assert span.attrs["proofload.episode"] == "cfg-7:seed-3", span.span_id
        assert span.attrs["service.name"] == "airline-agent", span.span_id
        assert span.attrs["scope.flavor"] == "hand-built", span.span_id


def test_t23_section_3_per_span_mapping() -> None:
    from proofload.trace import from_otel

    tr = from_otel(load_fixture("otlp_agent_chat.json"))
    by_id = {s.span_id: s for s in tr.spans}
    agent, chat = by_id[AGENT_ID], by_id[CHAT_ID]
    assert agent.start_ns == EPOCH and agent.end_ns == EPOCH + 1_000_000_000
    assert chat.start_ns == EPOCH + 100_000_000 and chat.end_ns == EPOCH + 912_000_000
    assert isinstance(chat.start_ns, int) and isinstance(chat.end_ns, int)
    assert agent.code == {"filepath": "agent/planner.py", "function": "plan", "lineno": 88}
    assert chat.code is None
    assert chat.name == "gpt-4o-2024-08-06"  # gen_ai.request.model lifted into name
    assert agent.name == "invoke_agent planner"  # nothing better-typed to lift: the span name
    assert dict(chat.tokens or {}) == {"in": 1200, "out": 85}
    assert chat.error is None and agent.error is None
    assert chat.confidence is None
    assert chat.attrs["gen_ai.system"] == "openai"
    assert chat.attrs["gen_ai.request.temperature"] == 0.2
    assert chat.attrs["gen_ai.request.stop_sequences"] == ["END"]
    assert agent.attrs["gen_ai.agent.name"] == "planner"


def test_t23_kind_map_and_fallbacks() -> None:
    from proofload.trace import OTEL_KIND_MAP, from_otel

    assert dict(OTEL_KIND_MAP) == OTEL_KIND_MAP_SPEC
    tr = from_otel(load_fixture("otlp_kinds.json"))
    assert tr.dropped == 0 and len(tr.spans) == 14
    kinds = {s.span_id: s.kind for s in tr.spans}
    assert kinds == {
        "0000000000000001": "tool",
        "0000000000000002": "retrieval",
        "0000000000000003": "db",
        "0000000000000004": "http",
        "0000000000000005": "http",
        "0000000000000006": "other",
        "0000000000000007": "other",
        "0000000000000008": "llm",
        "0000000000000009": "llm",
        "000000000000000a": "retrieval",
        "000000000000000b": "agent",
        "000000000000000c": "agent",
        "000000000000000d": "agent",
        "000000000000000e": "tool",
    }
    by_id = {s.span_id: s for s in tr.spans}
    assert by_id["0000000000000001"].name == "search_catalog"  # gen_ai.tool.name lifted into name
    assert by_id["0000000000000001"].error is not None and "boom" in by_id["0000000000000001"].error
    assert by_id["000000000000000e"].error is not None and "TimeoutError" in by_id["000000000000000e"].error
    assert by_id["0000000000000002"].error is None
    assert by_id["0000000000000003"].attrs["db.system"] == "postgresql"
    assert by_id["0000000000000006"].name == "mystery"
    assert all(s.parent_id is None for s in tr.spans)


def test_t23_unrecognized_operation_name_lands_in_other_and_is_preserved() -> None:
    from proofload.trace import from_otel

    tr = from_otel(load_fixture("otlp_kinds.json"))
    span = {s.span_id: s for s in tr.spans}["0000000000000007"]
    assert span.kind == "other"
    assert "frobnicate" in list(span.attrs.values()), dict(span.attrs)


# ---------- T24: from_litellm ----------


def test_t24_one_root_llm_span_per_payload_and_no_confidence_from_logprobs() -> None:
    from proofload.trace import from_litellm

    payloads = litellm_payloads()
    assert len(payloads) == 3
    assert "logprobs" in json.dumps(payloads[0]["response_obj"])
    tr = from_litellm(payloads)
    assert tr.source == "litellm"
    assert tr.source_version is None
    assert tr.dropped == 0
    assert len(tr.spans) == 3
    for span in tr.spans:
        assert span.kind == "llm", span.span_id
        assert span.parent_id is None, span.span_id
        assert span.confidence is None, span.span_id
        assert span.end_ns is not None and span.end_ns >= span.start_ns, span.span_id
    assert len(tr.roots()) == 3
    assert len({s.span_id for s in tr.spans}) == 3


def test_t24_empty_iterable_is_an_empty_litellm_trace() -> None:
    from proofload.trace import from_litellm

    tr = from_litellm([])
    assert tr.spans == () and tr.source == "litellm" and tr.dropped == 0


# ---------- T25: the semconv pin ----------


def string_constant_sites(literal: str) -> list[str]:
    sites = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == literal:
                sites.append(f"{path.relative_to(SRC)}:{node.lineno}")
    return sites


def test_t25_source_version_is_the_pinned_semconv_version() -> None:
    from proofload.trace import OTEL_SEMCONV_VERSION, from_otel

    assert OTEL_SEMCONV_VERSION == OTEL_SEMCONV_VERSION_SPEC
    for name in ("otlp_agent_chat.json", "otlp_kinds.json", "otlp_dropped.json"):
        assert from_otel(load_fixture(name)).source_version == OTEL_SEMCONV_VERSION, name
    assert from_otel([]).source_version == OTEL_SEMCONV_VERSION


def test_t25_semconv_literal_appears_exactly_once_in_src() -> None:
    assert TRACE_SOURCE.is_file(), "src/proofload/trace.py does not exist"
    sites = string_constant_sites(OTEL_SEMCONV_VERSION_SPEC)
    assert len(sites) == 1 and sites[0].startswith("trace.py:"), sites


# ---------- T26: merge ----------


def test_t26_merge_concatenates_sums_dropped_and_keeps_parentage() -> None:
    from proofload.trace import Span, Trace, merge

    a_root = Span.from_dict(SPAN_B)
    a_child = Span.from_dict(SPAN_A)
    b_root = Span(span_id="00000000000000b1", parent_id=None, kind="tool", name="search", start_ns=EPOCH + 5, end_ns=EPOCH + 9)
    b_orphan = Span(span_id="00000000000000b2", parent_id="00000000000000ee", kind="tool", name="orphan", start_ns=EPOCH + 6, end_ns=None)
    a = Trace(spans=(a_root, a_child), source="otel", source_version="1.42.0", dropped=1)
    b = Trace(spans=(b_root, b_orphan), source="record", dropped=2)

    m = merge(a, b)
    assert m.source == "mixed"
    assert m.dropped == 3
    assert m.ordered() == Trace(spans=(a_root, a_child, b_root, b_orphan), source="mixed").ordered()
    assert {(s.span_id, s.parent_id) for s in m.spans} == {(s.span_id, s.parent_id) for s in (*a.spans, *b.spans)}
    assert {s.span_id for s in m.roots()} == {a_root.span_id, b_root.span_id, b_orphan.span_id}
    assert m.children(a_root.span_id) == (a_child,)
    assert Trace.from_dict(json.loads(json.dumps(m.to_dict()))) == m


def test_t26_merge_raises_on_span_id_collision_naming_the_id() -> None:
    from proofload.trace import Span, Trace, TraceValidationError, merge

    a = Trace(spans=(Span.from_dict(SPAN_A),), source="otel")
    other = dict(SPAN_A)
    other["name"] = "same id, different span"
    b = Trace(spans=(Span.from_dict(other),), source="record")
    with pytest.raises(TraceValidationError) as info:
        merge(a, b)
    assert CHAT_ID in str(info.value)


# ---------- T27: core stays clean ----------


def test_t27_trace_module_and_both_converters_import_neither_opentelemetry_nor_litellm() -> None:
    for name in [n for n in sys.modules if n.split(".")[0] in ("opentelemetry", "litellm")]:
        del sys.modules[name]

    import proofload.trace as trace_module

    trace_module.from_otel(load_fixture("otlp_agent_chat.json"))
    trace_module.from_otel(load_fixture("otlp_kinds.json"))
    trace_module.from_litellm(litellm_payloads())

    loaded = {n.split(".")[0] for n in sys.modules}
    assert "opentelemetry" not in loaded
    assert "litellm" not in loaded
    assert not [n for n in sys.modules if n.startswith("opentelemetry")]


def test_t27_trace_py_source_imports_only_the_standard_library_and_proofload() -> None:
    assert TRACE_SOURCE.is_file(), "src/proofload/trace.py does not exist"
    tree = ast.parse(TRACE_SOURCE.read_text(encoding="utf-8"))
    tops = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tops.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            tops.add(node.module.split(".")[0])
    third_party = {t for t in tops if t not in sys.stdlib_module_names and t != "proofload"}
    assert third_party == set(), third_party


# ---------- T28: the schema id is built in one place (ADR-024) ----------


def imports_proofload_trace(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "proofload.trace":
            return True
        if isinstance(node, ast.Import) and any(alias.name == "proofload.trace" for alias in node.names):
            return True
    return False


def test_t28_schema_literal_appears_exactly_once_in_src() -> None:
    assert TRACE_SOURCE.is_file(), "src/proofload/trace.py does not exist"
    sites = string_constant_sites(SCHEMA_SPEC)
    assert len(sites) == 1 and sites[0].startswith("trace.py:"), sites


def test_t28_cli_and_mock_agent_reach_the_schema_through_proofload_trace() -> None:
    assert imports_proofload_trace(CLI_SOURCE), "cli.py does not import proofload.trace"
    assert imports_proofload_trace(MOCK_AGENT_SOURCE), "mock_agent.py does not import proofload.trace"


# ---------- T29: the mock agent emits the schema, deterministically ----------


def test_t29_mock_agent_traces_decode_and_are_deterministic() -> None:
    import proofload.examples.mock_agent as mock_agent
    from proofload.trace import Trace

    cells = SweepSpec.load(QUICKSTART).configs
    assert len(cells) == 15
    for cfg in cells:
        for seed in range(QUICKSTART_REPLICATES):
            for fn in (mock_agent.rollout, mock_agent.rollout_patched):
                ep = fn(dict(cfg), seed)
                tr = Trace.from_dict(ep.meta["trace"])
                assert len(tr.spans) == int(ep.t), (cfg, seed, fn.__name__)
                for span in tr.spans:
                    assert span.kind == "tool", (cfg, seed, span)
                    assert span.parent_id is None, (cfg, seed, span)
                    assert span.end_ns is not None and span.end_ns >= span.start_ns, (cfg, seed, span)
                assert tr.ordered() == tr.spans, (cfg, seed, fn.__name__)
                assert fn(dict(cfg), seed).meta["trace"] == ep.meta["trace"], (cfg, seed, fn.__name__)


def test_t29_mock_agent_per_step_shape_from_section_3() -> None:
    import proofload.examples.mock_agent as mock_agent
    from proofload.trace import Trace

    assert mock_agent.MOCK_EPOCH_NS == MOCK_EPOCH_NS_SPEC
    cfg = {"task_id": "checkout", "tool_fail_rate": 0.45}
    ep = mock_agent.rollout(cfg, 3)
    assert ep.meta["task_id"] == "checkout"
    tr = Trace.from_dict(ep.meta["trace"])
    assert tr.source == "record" and tr.dropped == 0
    assert tr.spans[0].start_ns == MOCK_EPOCH_NS_SPEC
    for earlier, later in zip(tr.spans, tr.spans[1:], strict=False):
        assert later.start_ns == earlier.end_ns, (earlier, later)  # cumulative simulated latency
    for span in tr.spans:
        assert span.code is None
        assert set(span.attrs) == {"attempts"} and span.attrs["attempts"] in (1, 2)
        assert span.error in (None, "ToolError")
        assert span.name in mock_agent._TASKS["checkout"]


# ---------- T30: inspect reads spans ----------


def test_t30_inspect_prints_no_trace_lines_and_no_error_for_a_rejected_trace_dict(tmp_path: Path) -> None:
    from proofload.trace import Trace, TraceValidationError

    bad = trace_dict(SPAN_B, source="record", source_version=None, task_id="checkout")  # extra top-level key
    with pytest.raises(TraceValidationError):
        Trace.from_dict(bad)

    root = tmp_path / "syn"
    store = Store(root)
    run_id = "bad-trace"
    store.create_run(
        RunManifest(
            run_id=run_id,
            target_id="synthetic@v0",
            t_unit="tool_calls",
            run_salt="syn",
            axis_types={"x": "continuous"},
            backend="synthetic",
            environment={},
        )
    )
    ep = Episode(outcome="violated", t=1.0, horizon=20.0, meta={"trace": bad})
    record = EpisodeRecord.from_episode(ep, run_id=run_id, config={"x": 1.0}, seed=1, replicate_index=0, wall_time=0.0)
    store.append(run_id, [record])
    store.mark_complete(run_id)
    assert store.read(run_id).iloc[0]["meta"]["trace"] == bad

    out, err = StringIO(), StringIO()
    code = cli.main(
        ["--store", str(root), "inspect", run_id, "--event", "violated"],
        stdout=out, stderr=err, stdin=StringIO(),
    )
    assert code == 0, out.getvalue() + err.getvalue()
    assert err.getvalue() == ""
    assert "Traceback" not in out.getvalue()
    lines = out.getvalue().splitlines()
    assert any(line.startswith("config_hash: ") for line in lines), out.getvalue()
    assert "seed: 1" in lines
    assert [line for line in lines if STEP_LINE_RE.match(line)] == [], out.getvalue()


def test_t30_inspect_prints_ordered_spans_with_duration_ms_in_the_fourth_column(tmp_path: Path) -> None:
    from proofload.trace import Trace

    root = tmp_path / "store"
    out, err = StringIO(), StringIO()
    code = cli.main(
        ["--store", str(root), "sweep", str(QUICKSTART), "--target", "proofload.examples.mock_agent:rollout", "--yes"],
        stdout=out, stderr=err, stdin=StringIO(),
    )
    assert code == 0, out.getvalue() + err.getvalue()
    last = [line for line in out.getvalue().splitlines() if line.strip()][-1]
    assert last.startswith("run_id: "), out.getvalue()
    run_id = last.split(": ", 1)[1]

    df = Store(root).read(run_id)
    rows = df[df["outcome"] == "violated"]
    assert len(rows) >= 1
    by_key = {(row.config_hash, int(row.seed)): row for row in rows.itertuples(index=False)}

    out, err = StringIO(), StringIO()
    code = cli.main(
        ["--store", str(root), "inspect", run_id, "--event", "violated"],
        stdout=out, stderr=err, stdin=StringIO(),
    )
    assert code == 0, out.getvalue() + err.getvalue()
    assert err.getvalue() == ""

    blocks: list[list[str]] = []
    for line in out.getvalue().splitlines():
        if line.startswith("config_hash: "):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    assert len(blocks) == len(rows), out.getvalue()

    for block in blocks:
        config_hash = block[0].split(": ", 1)[1]
        seed = int(next(line for line in block if line.startswith("seed: ")).split(": ", 1)[1])
        row = by_key[(config_hash, seed)]
        spans = Trace.from_dict(row.meta["trace"]).ordered()
        step_lines = [line for line in block if STEP_LINE_RE.match(line)]
        assert len(step_lines) == len(spans) == int(row.t), "\n".join(block)
        for j, (line, span) in enumerate(zip(step_lines, spans, strict=True)):
            cols = line.split("\t")
            assert int(cols[0]) in (j, j + 1), line
            assert cols[1] == span.kind and cols[2] == span.name, (line, span)
            assert span.duration_ms is not None and float(cols[3]) == span.duration_ms, (line, span)
            assert cols[4] == ("-" if span.error is None else span.error), (line, span)
