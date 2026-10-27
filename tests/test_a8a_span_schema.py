"""A8a frozen tests: invariants P8-1 to P8-6, P8-13 to P8-16, P8-18 and P8-19 of
the A8a span schema: the eight span fields, the seventh trace key, ``OUTCOME_BY``, ``GATE``,
``ALIAS_MAP_VERSION``, the lifts, ``record()``'s three kwargs, ``inspect``'s four columns and the
two renames.

**What these tests hold to.** The alias map stays GenAI-only: a real OpenInference chat span
through ``from_otel`` has none of its 21 keys aliased or lifted, ten of them are observation
content, ``tokens`` and the model name do not reach the fields that exist for them, and none of
A8a's eight carriers is present. No ``graph.node.*`` identity
entries in ``ATTRIBUTE_ALIASES``. ``FAULT_KEY`` and ``FAULT_POSITION_KEY`` are not A8a's.
``ALIAS_MAP_VERSION == "1"``. ``EVALUATOR`` is not a gate marker. ``_ORIGINAL_ERROR_TYPE``
survives. ``inspect``'s four new columns come after ``error``.

**pandas 2 and pandas 3, and no invariant is specific to one.** Every one of A8a's nine fields
reaches disk inside the ``trace`` / ``trace_obs`` JSON columns, never as a Parquet column, so the
pandas major cannot see any of them. Nullness is by identity in every clause: ``is None`` /
``is not None``, never ``pd.isna`` and never a bare truth test.

**The guard on the kind ladder.** T36's tests in ``test_m12_kinds.py`` are the guard that fails if
the vendor keys are lifted before the kind ladder reads them: adding ``openinference.span.kind`` to
``_LIFTED_KEYS`` fails them.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
from collections.abc import Mapping
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import poisson_prove.cli as cli
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.trace import Span, Trace, TraceValidationError
from conftest import quickstart_design

TESTS = Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures" / "trace"
# PF3: the one copy is the packaged spec; this is its design at
# 100 replicates.
QUICKSTART = quickstart_design()
# PF4.30, PF4.48a: the quickstart design at 100 replicates with nothing
# declared has a detection limit (0.262 at base rate 0.400) above the default accepted change of 0.20,
# so its sweep is refused; every sweep of it in this file accepts 0.3, the smallest round value
# above the limit.
QUICKSTART_MAX_MDE = ("--max-mde", "0.3")
LOGGER_NAME = "poisson_prove.trace"
EPOCH = 1_756_900_000_000_000_000

# ---------- the schema's constants, spelled here rather than imported from the code ----------

SPAN_FIELDS_SPEC: tuple[str, ...] = (
    "span_id", "parent_id", "kind", "name", "start_ns", "end_ns",
    "input", "output", "tokens", "confidence", "error", "code", "attrs",
    "operation", "step_name", "outcome", "outcome_by", "attempt", "gate", "truncated", "bytes_original",
)
NEW_FIELDS: tuple[str, ...] = SPAN_FIELDS_SPEC[13:]
TRACE_KEYS_SPEC: tuple[str, ...] = ("schema", "source", "source_version", "dropped", "spans", "truncated", "alias_map_version")
OUTCOME_BY_SPEC = ("code", "llm", "self", "human")
GATE_SPEC = ("emitted", "declared")
ALIAS_MAP_VERSION_SPEC = "1"  # the alias map's only version
STATUS_CODES = frozenset({"OK", "UNSET", "ERROR"})
OTLP_FIXTURES = ("otlp_agent_chat.json", "otlp_kinds.json", "otlp_aliases.json", "otlp_dropped.json")

# ---------- helpers: data construction, never an assertion ----------


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def loop_spans() -> dict[int, Span]:
    """``otlp_loop.json`` through ``from_otel``, keyed by the span id as an integer (1..16)."""
    from poisson_prove.trace import from_otel

    tr = from_otel(load_fixture("otlp_loop.json"))
    assert tr.dropped == 0 and len(tr.spans) == 16, (tr.dropped, len(tr.spans))
    return {int(s.span_id, 16): s for s in tr.spans}


def plain_span(**overrides: Any) -> Span:
    base: dict[str, Any] = {"span_id": "00000000000000a1", "parent_id": None, "kind": "tool", "name": "x", "start_ns": EPOCH, "end_ns": EPOCH + 1_000}
    base.update(overrides)
    return Span(**base)


def span_dict(**overrides: Any) -> dict[str, Any]:
    d: dict[str, Any] = {name: None for name in SPAN_FIELDS_SPEC}
    d.update({"span_id": "00000000000000a1", "parent_id": None, "kind": "tool", "name": "x", "start_ns": EPOCH, "end_ns": EPOCH + 1_000, "attrs": {}})
    d.update(overrides)
    return d


def trace_dict(*spans: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "schema": "poisson-prove.trace/1", "source": "otel", "source_version": "1.42.0", "dropped": 0,
        "spans": [dict(s) for s in spans], "truncated": None, "alias_map_version": None,
    }
    d.update(overrides)
    return d


def flat_span(n: int, name: str, **attrs: Any) -> dict[str, Any]:
    """One flat OTLP span mapping (the second input form), string attributes."""
    return {
        "spanId": f"{n:016x}", "name": name, "startTimeUnixNano": str(EPOCH), "endTimeUnixNano": str(EPOCH + 1_000_000),
        "attributes": [{"key": k, "value": {"stringValue": str(v)}} for k, v in attrs.items()],
    }


def synthetic_run_with_trace(root: Path, run_id: str, trace: Mapping[str, Any]) -> None:
    """One violated row carrying ``trace`` in ``meta`` -- the shape T30's rejected-trace test stores."""
    store = Store(root)
    store.create_run(RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="tool_calls", run_salt="syn",
        axis_types={"x": "continuous"}, backend="synthetic", environment={},
    ))
    ep = Episode(outcome="violated", t=1.0, horizon=20.0, meta={"trace": dict(trace)})
    rec = EpisodeRecord.from_episode(ep, run_id=run_id, config={"x": 1.0}, seed=1, replicate_index=0, wall_time=0.0)
    store.append(run_id, [rec])
    store.mark_complete(run_id)


def inspect_lines(root: Path, run_id: str, event: str) -> list[str]:
    out, err = StringIO(), StringIO()
    code = cli.main(["--store", str(root), "inspect", run_id, "--event", event], stdout=out, stderr=err, stdin=StringIO())
    assert code == 0 and err.getvalue() == "", out.getvalue() + err.getvalue()
    return out.getvalue().splitlines()


STEP_LINE_RE = re.compile(r"^\s*\d+(?:\t[^\t]*){8}$")


# ---------- P8-1: the twenty-one-key span and the seven-key trace ----------


def test_p8_1_span_to_dict_has_exactly_the_twenty_one_keys_in_order_none_where_unset() -> None:
    d = plain_span().to_dict()
    assert list(d) == list(SPAN_FIELDS_SPEC), list(d)
    for name in NEW_FIELDS:
        assert d[name] is None, name
    assert tuple(f.name for f in dataclasses.fields(Span)) == SPAN_FIELDS_SPEC
    full = Span.from_dict(span_dict(operation="chat", step_name="plan", outcome="pass", outcome_by="code", attempt=2, gate="emitted", truncated="observation", bytes_original=9)).to_dict()
    assert [full[name] for name in NEW_FIELDS] == ["chat", "plan", "pass", "code", 2, "emitted", "observation", 9]
    assert Span.from_dict(full).to_dict() == full


def test_p8_1_from_dict_rejects_thirteen_keys_naming_the_first_missing_and_a_twenty_second_naming_it() -> None:
    thirteen = {k: v for k, v in span_dict().items() if k not in NEW_FIELDS}
    assert len(thirteen) == 13
    with pytest.raises(TraceValidationError) as info:
        Span.from_dict(thirteen)
    assert "missing" in str(info.value) and "attempt" in str(info.value), str(info.value)
    with pytest.raises(TraceValidationError) as info:
        Span.from_dict({**span_dict(), "latency_ms": 3})
    assert "latency_ms" in str(info.value), str(info.value)


def test_p8_1_trace_to_dict_has_exactly_seven_keys_and_from_dict_rejects_six_and_eight() -> None:
    d = Trace(spans=(), source="record").to_dict()
    assert list(d) == list(TRACE_KEYS_SPEC), list(d)
    assert d["alias_map_version"] is None
    assert tuple(f.name for f in dataclasses.fields(Trace)) == ("spans", "source", "source_version", "dropped", "truncated", "alias_map_version")
    six = {k: v for k, v in trace_dict().items() if k != "alias_map_version"}
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict(six)
    assert "alias_map_version" in str(info.value), str(info.value)
    with pytest.raises(TraceValidationError) as info:
        Trace.from_dict({**trace_dict(), "steps": []})
    assert "steps" in str(info.value), str(info.value)
    stamped = Trace.from_dict(trace_dict(span_dict(), alias_map_version="1"))
    assert stamped.alias_map_version == "1" and stamped.to_dict()["alias_map_version"] == "1"


# ---------- P8-2: the validators ----------


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param({"outcome": "pass", "outcome_by": "robot"}, id="outcome_by-not-in-OUTCOME_BY"),
        pytest.param({"gate": "maybe"}, id="gate-not-in-GATE"),
        pytest.param({"attempt": 0}, id="attempt-below-one"),
        pytest.param({"attempt": -1}, id="attempt-negative"),
        pytest.param({"attempt": True}, id="attempt-bool"),
        pytest.param({"attempt": "2"}, id="attempt-str"),
        pytest.param({"bytes_original": 3}, id="bytes_original-without-truncated"),
        pytest.param({"truncated": "observation", "bytes_original": 0}, id="bytes_original-below-one"),
        pytest.param({"truncated": "observation", "bytes_original": True}, id="bytes_original-bool"),
        pytest.param({"outcome_by": "code"}, id="outcome_by-without-outcome"),
        pytest.param({"operation": 3}, id="operation-not-str"),
        pytest.param({"step_name": 3}, id="step_name-not-str"),
        pytest.param({"outcome": 3}, id="outcome-not-str"),
        pytest.param({"truncated": 3}, id="truncated-not-str"),
    ],
)
def test_p8_2_each_invalid_value_raises_at_the_constructor_and_inside_from_dict(bad: dict[str, Any]) -> None:
    with pytest.raises(TraceValidationError):
        plain_span(**bad)
    with pytest.raises(TraceValidationError):
        Span.from_dict(span_dict(**bad))


def test_p8_2_the_vocabularies_and_the_free_fields() -> None:
    from poisson_prove import trace as trace_module
    from poisson_prove.trace import GATE, OUTCOME_BY

    assert OUTCOME_BY == OUTCOME_BY_SPEC and GATE == GATE_SPEC
    assert {"OUTCOME_BY", "GATE", "ALIAS_MAP_VERSION"} <= set(trace_module.__all__)
    for who in OUTCOME_BY:
        assert plain_span(outcome="x", outcome_by=who).outcome_by == who
    for gate in GATE:
        assert plain_span(gate=gate).gate == gate
    # operation is verbatim and never checked against a vocabulary; outcome is a free label.
    for op in ("chat", "frobnicate", "CHAT", "guardrail", ""):
        assert plain_span(operation=op).operation == op
    assert plain_span(outcome="").outcome == "" and plain_span(outcome="whatever").outcome == "whatever"
    assert plain_span(truncated="observation", bytes_original=1).bytes_original == 1
    # A trace-level truncated reason is a different field: setting it never sets a span's.
    cut = Trace(spans=(plain_span(),), source="otel", truncated="timeout")
    assert cut.truncated == "timeout" and cut.spans[0].truncated is None and cut.spans[0].bytes_original is None
    with pytest.raises(TraceValidationError):
        Trace(spans=(), source="record", alias_map_version=1)  # type: ignore[arg-type]


# ---------- P8-3: every producer leaves the eight None; the recorder's contrapositive ----------


def all_eight_none(span: Span) -> bool:
    return all(getattr(span, name) is None for name in NEW_FIELDS)


OPERATION_CARRIERS = ("gen_ai.operation.name", "llm.request.type", "openinference.span.kind", "traceloop.span.kind")


def raw_spans_with_an_operation_carrier(payload: Any) -> int:
    """How many raw span mappings in an OTLP payload (nested or flat) carry an operation carrier."""
    count = 0
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            attributes = node.get("attributes")
            if "spanId" in node or "span_id" in node:
                keys = {a.get("key") for a in attributes} if isinstance(attributes, list) else set()
                count += any(k in keys for k in OPERATION_CARRIERS)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return count


def test_p8_3_every_producer_leaves_all_eight_fields_none_without_a_carrier() -> None:
    from poisson_prove.examples import mock_agent
    from poisson_prove.trace import collect, from_litellm, from_otel, record

    with collect() as c:
        with record("tool", "search") as h:
            h.output = {"hits": 3}
    assert len(c.trace.spans) == 1 and all_eight_none(c.trace.spans[0])

    # The seven committed OTLP payloads carry gen_ai.operation.name on most spans, so operation --
    # whose carrier that is -- is exempt exactly there: non-None on as many spans as carried one,
    # and the other seven fields None everywhere (no fixture carries their carriers).
    payloads = [load_fixture(name) for name in OTLP_FIXTURES] + list(load_fixture("otlp_encodings.json").values())
    assert len(payloads) == 7
    seen = 0
    for name, payload in zip(OTLP_FIXTURES + ("encodings",) * 3, payloads, strict=True):
        tr = from_otel(payload)
        with_operation = 0
        for span in tr.spans:
            seen += 1
            assert all(getattr(span, field) is None for field in NEW_FIELDS if field != "operation"), (name, span.span_id, span.to_dict())
            with_operation += span.operation is not None
        if name != "otlp_dropped.json":  # dropped spans never reach the count
            assert with_operation == raw_spans_with_an_operation_carrier(payload), name
    assert seen >= 20

    from datetime import datetime

    calls = load_fixture("litellm_calls.json")
    for call in calls:
        for key in ("start_time", "end_time"):
            if isinstance(call.get(key), str):
                call[key] = datetime.fromisoformat(call[key])
    lite = from_litellm(calls)
    assert len(lite.spans) >= 1 and all(all_eight_none(s) for s in lite.spans)

    for seed in range(5):
        ep = mock_agent.rollout({"task_id": "checkout", "tool_fail_rate": 0.3}, seed)
        tr = Trace.from_dict(ep.meta["trace"])
        assert len(tr.spans) >= 1 and all(all_eight_none(s) for s in tr.spans)


def test_p8_3_contrapositive_a_record_block_that_sets_each_field_sees_it_on_the_closed_span() -> None:
    from poisson_prove.trace import SpanHandle, collect, record, step

    assert {"outcome", "outcome_by"} <= {f.name for f in dataclasses.fields(SpanHandle)}
    with collect() as c:
        with record("tool", "search", step_name="lookup", attempt=2, gate="emitted") as h:
            h.outcome = "pass"
            h.outcome_by = "self"
        with record("tool", "plain"):
            pass
    by_name = {s.name: s for s in c.trace.spans}
    full = by_name["search"]
    assert (full.step_name, full.attempt, full.gate, full.outcome, full.outcome_by) == ("lookup", 2, "emitted", "pass", "self")
    assert full.operation is None and full.truncated is None and full.bytes_original is None
    assert all_eight_none(by_name["plain"])

    @step(name="verify", step_name="verify")
    def verify() -> int:
        return 1

    @step(name="bare")
    def bare() -> int:
        return 2

    with collect() as c:
        assert verify() == 1 and bare() == 2
    by_name = {s.name: s for s in c.trace.spans}
    assert by_name["verify"].step_name == "verify" and all(getattr(by_name["verify"], n) is None for n in NEW_FIELDS if n != "step_name")
    assert all_eight_none(by_name["bare"])


def test_p8_3_a_bad_handle_value_drops_the_span_with_a_warning_and_never_raises(caplog: pytest.LogCaptureFixture) -> None:
    from poisson_prove.trace import collect, record

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    with collect() as c:
        with record("tool", "judged") as h:
            h.outcome = "pass"
            h.outcome_by = "robot"
        with record("tool", "kept"):
            pass
    assert [s.name for s in c.trace.spans] == ["kept"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "judged" in r.getMessage()]
    assert len(warnings) == 1, [r.getMessage() for r in caplog.records]


# ---------- P8-4: the lifts on otlp_loop.json ----------


def test_p8_4_graph_node_name_and_poisson_prove_attempt_are_lifted_and_leave_attrs() -> None:
    by = loop_spans()
    for sid, step_name in ((2, "lookup"), (3, "lookup"), (4, "lookup"), (6, "check"), (7, "check"), (8, "check"), (1, "plan"), (5, "verify")):
        assert by[sid].step_name == step_name, (sid, by[sid].step_name)
        assert "graph.node.name" not in by[sid].attrs, sid
    assert by[2].attempt == 1 and by[3].attempt == 2
    assert "poisson_prove.attempt" not in by[2].attrs and "poisson_prove.attempt" not in by[3].attrs
    assert (by[2].outcome, by[2].outcome_by) == ("pass", "code")
    assert (by[3].outcome, by[3].outcome_by) == ("fail", "llm")
    for sid in (2, 3):
        assert "poisson_prove.outcome" not in by[sid].attrs and "poisson_prove.outcome_by" not in by[sid].attrs
    for sid in (12, 13):
        assert "poisson_prove.step_name" not in by[sid].attrs and "poisson_prove.gate" not in by[sid].attrs
    assert by[12].step_name == "policy" and by[13].step_name == "hook"


def test_p8_4_guardrail_is_an_emitted_gate_and_evaluator_is_not_and_graph_node_ids_survive() -> None:
    by = loop_spans()
    assert (by[9].kind, by[9].operation, by[9].gate) == ("other", "guardrail", "emitted")
    assert (by[10].kind, by[10].operation, by[10].gate) == ("other", "evaluator", None)
    for sid in (9, 10, 11, 14):
        assert "openinference.span.kind" not in by[sid].attrs, sid
    assert "traceloop.span.kind" not in by[15].attrs and (by[15].kind, by[15].operation) == ("agent", "workflow")
    # graph.node.id and graph.node.parent_id are neither lifted nor aliased; they survive in attrs.
    for sid, node, parent in ((2, "n2", "n1"), (3, "n3", "n1"), (4, "n4", "n1"), (6, "n6", "n5")):
        assert by[sid].attrs["graph.node.id"] == node and by[sid].attrs["graph.node.parent_id"] == parent, sid
    assert by[1].attrs["graph.node.id"] == "n1" and "graph.node.parent_id" not in by[1].attrs
    from poisson_prove.trace import ATTRIBUTE_ALIASES

    assert "graph.node.id" not in ATTRIBUTE_ALIASES and "graph.node.parent_id" not in ATTRIBUTE_ALIASES


# ---------- P8-5: attempt is never derived ----------


def test_p8_5_attempt_is_never_derived_from_name_repetition_or_nesting() -> None:
    by = loop_spans()
    # Three spans of one step_name under one parent, no counter anywhere: all None.
    assert [by[sid].step_name for sid in (6, 7, 8)] == ["check"] * 3
    assert all(by[sid].attempt is None for sid in (6, 7, 8)), [by[sid].attempt for sid in (6, 7, 8)]
    # The third lookup, beside siblings carrying 1 and 2, is still None: a counter is read, never inferred.
    assert by[4].attempt is None
    # And the same shape through the recorder: three same-named spans in one block.
    from poisson_prove.trace import collect, record

    with collect() as c:
        for _ in range(3):
            with record("tool", "retry_me", step_name="retry"):
                pass
    assert [s.attempt for s in c.trace.spans] == [None, None, None]


# ---------- P8-6: gate is never inferred ----------


def test_p8_6_a_span_named_guardrail_with_kind_tool_has_no_gate() -> None:
    by = loop_spans()
    assert by[11].name == "guardrail" and (by[11].kind, by[11].operation, by[11].gate) == ("tool", "tool", None)


def test_p8_6_declared_on_the_wire_is_dropped_with_one_warning_and_emitted_is_taken(caplog: pytest.LogCaptureFixture) -> None:
    from poisson_prove.trace import from_otel

    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    tr = from_otel([
        flat_span(21, "policy_check", **{"poisson_prove.gate": "declared"}),
        flat_span(22, "hook", **{"poisson_prove.gate": "emitted"}),
        flat_span(23, "junk", **{"poisson_prove.gate": "sometimes"}),
    ])
    assert tr.dropped == 0
    by = {int(s.span_id, 16): s for s in tr.spans}
    assert by[21].gate is None and by[22].gate == "emitted" and by[23].gate is None
    assert all("poisson_prove.gate" not in s.attrs for s in tr.spans)
    warned = [r for r in caplog.records if r.levelno == logging.WARNING and "declared" in r.getMessage()]
    assert len(warned) == 1, [r.getMessage() for r in caplog.records]
    assert loop_spans()[12].gate is None and loop_spans()[13].gate == "emitted"


# ---------- P8-13: ALIAS_MAP_VERSION ----------


def test_p8_13_alias_map_version_is_one() -> None:
    from poisson_prove.trace import ALIAS_MAP_VERSION

    assert ALIAS_MAP_VERSION == ALIAS_MAP_VERSION_SPEC


def test_p8_13_from_otel_stamps_it_and_record_and_litellm_leave_it_none() -> None:
    from poisson_prove.trace import ALIAS_MAP_VERSION, collect, from_litellm, from_otel, record

    for name in OTLP_FIXTURES + ("otlp_loop.json",):
        assert from_otel(load_fixture(name)).alias_map_version == ALIAS_MAP_VERSION, name
    assert from_otel([]).alias_map_version == ALIAS_MAP_VERSION
    with collect() as c:
        with record("tool", "x"):
            pass
    assert c.trace.alias_map_version is None
    assert from_litellm([]).alias_map_version is None
    # The recorder's capture path reaches it for free: Recorder._trace builds through from_otel.
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    from poisson_prove.capture import CaptureSpec, Recorder

    rec = Recorder(CaptureSpec(max_observation_bytes=8192), "r-a8a", "cfg:1")  # a [capture] table's cap has no default
    empty = rec._trace([], None)
    assert empty is None  # nothing captured, so _trace itself builds no envelope
    stamped = rec._trace([flat_span(0x31, "captured")], None)
    assert stamped is not None and stamped["alias_map_version"] == ALIAS_MAP_VERSION


def test_p8_13_merge_mirrors_source_version_keeps_agreement_and_erases_disagreement() -> None:
    from poisson_prove.trace import ALIAS_MAP_VERSION, collect, from_otel, merge, record

    a = from_otel([flat_span(0x41, "a")])
    b = from_otel([flat_span(0x42, "b")])
    assert merge(a, b).alias_map_version == ALIAS_MAP_VERSION
    with collect() as c:
        with record("tool", "r"):
            pass
    assert merge(a, c.trace).alias_map_version == ALIAS_MAP_VERSION
    assert merge(c.trace, a).alias_map_version == ALIAS_MAP_VERSION
    one = Trace(spans=(plain_span(span_id="00000000000000c1"),), source="otel", alias_map_version="1")
    two = Trace(spans=(plain_span(span_id="00000000000000c2"),), source="otel", alias_map_version="2")
    assert merge(one, two).alias_map_version is None
    assert merge(c.trace, c.trace.__class__(spans=(), source="record")).alias_map_version is None


# ---------- P8-14: the trace id and the status code ----------


def test_p8_14_on_the_fixtures_every_span_carries_both_and_error_keeps_the_shipped_rule() -> None:
    from poisson_prove.trace import from_otel

    by = loop_spans()
    assert by[1].attrs["otel.status_code"] == "UNSET" and by[2].attrs["otel.status_code"] == "OK"
    assert by[3].attrs["otel.status_code"] == "ERROR" and by[4].attrs["otel.status_code"] == "UNSET"
    for span in by.values():
        assert span.attrs["otel.trace_id"] == "7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a", span.span_id
        assert span.attrs["otel.status_code"] in STATUS_CODES, span.span_id
    assert by[3].error == "lookup failed" and by[2].error is None
    # otlp_kinds.json's two error spans under the shipped rule: status.message first, then error.type.
    kinds = {s.span_id: s for s in from_otel(load_fixture("otlp_kinds.json")).spans}
    assert kinds["0000000000000001"].error == "boom" and kinds["000000000000000e"].error == "TimeoutError"
    assert all(s.error is None for sid, s in kinds.items() if sid not in ("0000000000000001", "000000000000000e"))
    assert all(s.attrs["otel.status_code"] in STATUS_CODES and "otel.trace_id" in s.attrs for s in kinds.values())


# ---------- P8-15: the two renames ----------


def test_p8_15_modal_backend_meta_carries_infra_attempt_and_no_attempt() -> None:
    from poisson_prove import executor_modal

    job = ({"x": 1.0}, 7, 3, "hash", 0)
    record = executor_modal._infra_record(SimpleNamespace(run_id="r-modal"), job, RuntimeError("boom"), 2)
    assert record.backend_meta.get("infra_attempt") == 2 and "attempt" not in record.backend_meta, record.backend_meta
    assert record.backend_meta.get("i") == 3


def test_p8_15_the_mock_emits_tries_and_never_attempt() -> None:
    from poisson_prove.examples import mock_agent

    seen = set()
    for seed in range(20):
        for fn in (mock_agent.rollout, mock_agent.rollout_patched):
            tr = Trace.from_dict(fn({"task_id": "checkout", "tool_fail_rate": 0.55}, seed).meta["trace"])
            for span in tr.spans:
                assert set(span.attrs) == {"tries"} and span.attrs["tries"] in (1, 2), span.attrs
                assert span.attempt is None and span.step_name is None
                seen.add(span.attrs["tries"])
    assert seen == {1, 2}


# ---------- P8-16: operation is verbatim ----------


def test_p8_16_operation_is_the_source_operation_name_stripped_and_lowercased_including_unrecognised() -> None:
    from poisson_prove.trace import from_otel

    raw = load_fixture("otlp_kinds.json")
    expected = {}
    for span in raw:
        for a in span["attributes"]:
            if a["key"] == "gen_ai.operation.name":
                expected[span["spanId"]] = a["value"]["stringValue"].strip().lower()
    assert "frobnicate" in expected.values() and len(expected) >= 10
    for span in from_otel(raw).spans:
        assert span.operation == expected.get(span.span_id), (span.span_id, span.operation)
        assert "poisson_prove.original_operation" not in span.attrs and "gen_ai.operation.name" not in span.attrs
    by = loop_spans()
    assert (by[16].operation, by[16].kind) == ("frobnicate", "other")
    assert (by[14].operation, by[14].kind, by[14].name) == ("chat", "llm", "gpt-4o")
    from poisson_prove import trace as trace_module

    assert not hasattr(trace_module, "_ORIGINAL_OPERATION")
    assert getattr(trace_module, "_ORIGINAL_ERROR_TYPE", None) == "poisson_prove.error_type"  # survives


# ---------- P8-18: inspect's nine columns ----------


def test_p8_18_inspect_prints_nine_columns_the_first_five_unchanged_and_dashes_for_none(tmp_path: Path) -> None:
    root = tmp_path / "store"
    out, err = StringIO(), StringIO()
    code = cli.main(
        ["--store", str(root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", "poisson_prove.examples.mock_agent:rollout", "--yes"],
        stdout=out, stderr=err, stdin=StringIO(),
    )
    assert code == 0, out.getvalue() + err.getvalue()
    # A sweep now ends with a verdict line, not 'run_id: <id>'; the run is
    # the one the empty store gained.
    (run_id,) = Store(root).runs()
    df = Store(root).read(run_id)
    rows = df[df["outcome"] == "violated"]
    # Text output shows a config_hash at 12 hex characters (rule 10).
    by_key = {(row.config_hash[:12], int(row.seed)): row for row in rows.itertuples(index=False)}
    lines = inspect_lines(root, run_id, "violated")
    blocks: list[list[str]] = []
    for line in lines:
        if line.startswith("config_hash: "):
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
    assert len(blocks) == len(rows) >= 1
    checked = 0
    for block in blocks:
        config_hash = block[0].split(": ", 1)[1][:12]
        seed = int(next(line for line in block if line.startswith("seed: ")).split(": ", 1)[1])
        spans = Trace.from_dict(by_key[(config_hash, seed)].meta["trace"]).ordered()
        step_lines = [line for line in block if STEP_LINE_RE.match(line)]
        assert len(step_lines) == len(spans) >= 1, "\n".join(block)
        for j, (line, span) in enumerate(zip(step_lines, spans, strict=True)):
            # The five columns as before A8a, byte for byte, then four dashes: every new field is None on the mock.
            assert line == f"  {j}\t{span.kind}\t{span.name}\t{span.duration_ms}\t{'-' if span.error is None else span.error}\t-\t-\t-\t-", line
            checked += 1
    assert checked >= 1


def test_p8_18_the_four_new_columns_carry_step_name_attempt_outcome_and_gate(tmp_path: Path) -> None:
    root = tmp_path / "store"
    spans = (
        span_dict(span_id="00000000000000d1", name="plan", kind="agent", step_name="plan", attempt=None, outcome=None, gate=None),
        span_dict(span_id="00000000000000d2", name="lookup", start_ns=EPOCH + 10, end_ns=EPOCH + 20, step_name="lookup", attempt=2, outcome="pass", outcome_by="code", gate="emitted", operation="execute_tool"),
    )
    synthetic_run_with_trace(root, "nine", trace_dict(*spans, source="record", source_version=None))
    lines = inspect_lines(root, "nine", "violated")
    step_lines = [line for line in lines if STEP_LINE_RE.match(line)]
    assert len(step_lines) == 2, "\n".join(lines)
    first, second = (line.split("\t") for line in step_lines)
    assert first[1:3] == ["agent", "plan"] and first[5:] == ["plan", "-", "-", "-"], first
    assert second[1:3] == ["tool", "lookup"] and second[5:] == ["lookup", "2", "pass", "emitted"], second
    assert all(len(cols) == 9 for cols in (first, second))
    # operation, outcome_by, truncated and bytes_original are not printed anywhere in the block.
    assert not any("execute_tool" in line or "code" in line.split("\t") for line in lines)


# ---------- P8-19: the round trip over the widened span ----------

hex_ids = st.text(alphabet="0123456789abcdef", min_size=16, max_size=16)
json_scalars = st.none() | st.booleans() | st.integers(min_value=-(2**63), max_value=2**63) | st.floats(allow_nan=False, allow_infinity=False) | st.text(max_size=8)
json_values = st.recursive(json_scalars, lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=4), inner, max_size=3), max_leaves=8)
observation_attr_keys = st.sampled_from(["gen_ai.input.messages", "gen_ai.tool.call.result", "input.value", "poisson_prove.logprobs", "gen_ai.prompt.0.content", "llm.output_messages.0.message.content"])
plain_attr_keys = st.sampled_from(["tries", "otel.trace_id", "otel.status_code", "poisson_prove.run_id", "graph.node.id", "graph.node.parent_id"])
attr_maps = st.dictionaries(plain_attr_keys | observation_attr_keys, json_values, max_size=5)
text1 = st.text(min_size=1, max_size=8)


@st.composite
def verdicts(draw: st.DrawFn) -> dict[str, Any]:
    """The eight new fields, each None or non-None, under the two pair rules."""
    outcome = draw(st.none() | text1 | st.just(""))
    truncated = draw(st.none() | st.just("observation"))
    return {
        "operation": draw(st.none() | text1),
        "step_name": draw(st.none() | text1),
        "outcome": outcome,
        "outcome_by": None if outcome is None else draw(st.none() | st.sampled_from(OUTCOME_BY_SPEC)),
        "attempt": draw(st.none() | st.integers(min_value=1, max_value=10**6)),
        "gate": draw(st.none() | st.sampled_from(GATE_SPEC)),
        "truncated": truncated,
        "bytes_original": None if truncated is None else draw(st.none() | st.integers(min_value=1, max_value=10**9)),
    }


@st.composite
def span_forests(draw: st.DrawFn) -> list[dict[str, Any]]:
    ids = draw(st.lists(hex_ids, min_size=0, max_size=5, unique=True))
    spans = []
    for i, sid in enumerate(ids):
        start = draw(st.integers(min_value=0, max_value=2**62))
        delta = draw(st.none() | st.integers(min_value=0, max_value=10**12))
        spans.append({
            "span_id": sid, "parent_id": draw(st.sampled_from([None, *ids[:i]])),
            "kind": draw(st.sampled_from(("llm", "tool", "retrieval", "db", "http", "agent", "other"))),
            "name": draw(text1), "start_ns": start, "end_ns": None if delta is None else start + delta,
            "input": draw(json_values), "output": draw(json_values),
            "tokens": draw(st.none() | st.dictionaries(st.text(min_size=1, max_size=4), st.integers(min_value=0, max_value=10**6), max_size=3)),
            "confidence": draw(st.none() | st.floats(min_value=0.0, max_value=1.0)),
            "error": draw(st.none() | text1), "code": None, "attrs": draw(attr_maps),
            **draw(verdicts()),
        })
    return spans


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(spans=span_forests(), source=st.sampled_from(("record", "otel", "litellm", "mixed")), alias=st.none() | st.sampled_from(["1", "2"]), truncated=st.none() | st.just("timeout"))
def test_p8_19_assemble_of_split_round_trips_the_twenty_one_key_span_and_the_seventh_trace_key(spans: list[dict[str, Any]], source: str, alias: str | None, truncated: str | None) -> None:
    from poisson_prove.trace import OBSERVATION_KEYS, assemble, split

    t = Trace.from_dict(trace_dict(*spans, source=source, source_version=None, alias_map_version=alias, truncated=truncated))
    envelope, obs = split(t)
    assert envelope["alias_map_version"] == alias and set(envelope) == set(TRACE_KEYS_SPEC)
    for raw, span in zip(envelope["spans"], t.spans, strict=True):
        assert set(raw) == set(SPAN_FIELDS_SPEC)
        # The eight ride in the envelope untouched: none of them is observation content.
        assert all(raw[name] == getattr(span, name) for name in NEW_FIELDS), raw
        assert raw["input"] is None and raw["output"] is None and not any(k in OBSERVATION_KEYS for k in raw["attrs"])
    assert assemble(envelope, obs).to_dict() == t.to_dict()
    if not obs:
        assert assemble(envelope, None).to_dict() == t.to_dict()
