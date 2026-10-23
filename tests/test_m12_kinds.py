"""M12 -- the kind ladder: the oracle for T35-T37.

Written from the invariants added to "Proofload -- Spec M12 Trace" section 4 after the
2026-09-04 kind-ratio spike, which ran real instrumentation and found two gaps:
``opentelemetry-util-genai`` emits ``fetch_response`` and ``execute_task`` (unmapped), and
the two conventions carrying most real agent instrumentation -- openinference (Arize Phoenix)
and traceloop (OpenLLMetry) -- typed nothing at all, so every one of their spans became
``other``.

Payloads here are hand-built flat span mappings, the shape section 3's second input form
accepts. No network, no keys, no instrumentation packages: the spike proved what real
encoders emit, and these pin what the converter does with it.
"""

from __future__ import annotations

from typing import Any

import pytest

EPOCH = 1_756_900_000_000_000_000


def span(span_id: str, name: str, **attrs: Any) -> dict[str, Any]:
    """One flat OTLP span mapping with the given attributes, protobuf-JSON spellings."""
    return {
        "spanId": span_id,
        "name": name,
        "startTimeUnixNano": str(EPOCH),
        "endTimeUnixNano": str(EPOCH + 1_000_000),
        "attributes": [
            {"key": key, "value": {"stringValue": str(value)}} for key, value in attrs.items()
        ],
    }


# ---------- T35: the two operation values the spike found missing ----------


def test_t35_fetch_response_and_execute_task_are_mapped() -> None:
    from poisson_prove.trace import OTEL_KIND_MAP

    assert OTEL_KIND_MAP["fetch_response"] == "llm"
    assert OTEL_KIND_MAP["execute_task"] == "agent"


@pytest.mark.parametrize(
    ("operation", "kind"), [("fetch_response", "llm"), ("execute_task", "agent")]
)
def test_t35_they_convert_and_are_not_treated_as_unrecognized(operation: str, kind: str) -> None:
    from poisson_prove.trace import from_otel

    tr = from_otel([span("0000000000000001", operation, **{"gen_ai.operation.name": operation})])
    assert tr.dropped == 0 and len(tr.spans) == 1
    got = tr.spans[0]
    assert got.kind == kind, (operation, got.kind)
    # A recognized operation is never stashed as an original.
    assert "poisson_prove.original_operation" not in got.attrs
    assert "gen_ai.operation.name" not in got.attrs


# ---------- T36: the vendor-convention rung ----------

OPENINFERENCE = {
    "LLM": "llm",
    "TOOL": "tool",
    "RETRIEVER": "retrieval",
    "EMBEDDING": "retrieval",
    "RERANKER": "retrieval",
    "AGENT": "agent",
    "CHAIN": "agent",
}
TRACELOOP = {"tool": "tool", "agent": "agent", "workflow": "agent", "task": "agent"}


@pytest.mark.parametrize(("value", "kind"), sorted(OPENINFERENCE.items()))
def test_t36_openinference_span_kind_types_the_span(value: str, kind: str) -> None:
    from poisson_prove.trace import from_otel

    tr = from_otel([span("0000000000000002", "some span", **{"openinference.span.kind": value})])
    assert tr.dropped == 0
    assert tr.spans[0].kind == kind, (value, tr.spans[0].kind)


@pytest.mark.parametrize(("value", "kind"), sorted(TRACELOOP.items()))
def test_t36_traceloop_span_kind_types_the_span(value: str, kind: str) -> None:
    from poisson_prove.trace import from_otel

    tr = from_otel([span("0000000000000003", "some span", **{"traceloop.span.kind": value})])
    assert tr.dropped == 0
    assert tr.spans[0].kind == kind, (value, tr.spans[0].kind)


def test_t36_matching_is_case_insensitive_both_ways() -> None:
    from poisson_prove.trace import from_otel

    lowered = from_otel([span("0000000000000004", "s", **{"openinference.span.kind": "tool"})])
    uppered = from_otel([span("0000000000000005", "s", **{"traceloop.span.kind": "TOOL"})])
    assert lowered.spans[0].kind == "tool"
    assert uppered.spans[0].kind == "tool"


def test_t36_an_unrecognized_vendor_value_falls_through_the_rest_of_the_ladder() -> None:
    from poisson_prove.trace import from_otel

    # GUARDRAIL is a real openinference value with no Proofload kind: it must not invent one.
    plain = from_otel([span("0000000000000006", "s", **{"openinference.span.kind": "GUARDRAIL"})])
    assert plain.spans[0].kind == "other"
    # ...and the db/http rungs still work underneath it.
    with_db = from_otel(
        [span("0000000000000007", "s", **{"openinference.span.kind": "GUARDRAIL",
                                          "db.system": "postgresql"})]
    )
    assert with_db.spans[0].kind == "db"
    with_http = from_otel(
        [span("0000000000000008", "s", **{"traceloop.span.kind": "nonsense",
                                          "http.request.method": "GET"})]
    )
    assert with_http.spans[0].kind == "http"


# ---------- T37: the standard outranks the vendors, and both keys are lifted (A8a) ----------


def test_t37_gen_ai_operation_name_wins_over_a_conflicting_vendor_kind() -> None:
    from poisson_prove.trace import from_otel

    tr = from_otel(
        [
            span(
                "0000000000000009",
                "s",
                **{
                    "gen_ai.operation.name": "chat",
                    "openinference.span.kind": "TOOL",
                    "traceloop.span.kind": "workflow",
                },
            )
        ]
    )
    assert tr.spans[0].kind == "llm"


def test_t37_vendor_keys_are_lifted_into_operation_and_do_not_survive_in_attrs() -> None:
    """A8a inverts the shipped rule (spec A8a section 3.5): ``openinference.span.kind`` and
    ``traceloop.span.kind`` are lifted, the value lands in ``operation`` stripped and lowercased,
    the kind ladder still reads it, and the key never survives in ``attrs`` (T20)."""
    from poisson_prove.trace import from_otel

    payload = [
        span("000000000000000a", "s", **{"openinference.span.kind": "TOOL", "tool.name": "search"}),
        span("000000000000000b", "s", **{"traceloop.span.kind": "workflow"}),
        span("000000000000000c", "s", **{"gen_ai.operation.name": "chat",
                                         "openinference.span.kind": "LLM"}),
    ]
    tr = from_otel(payload)
    assert tr.dropped == 0 and len(tr.spans) == 3
    by_id = {s.span_id: s for s in tr.spans}
    a, b, c = by_id["000000000000000a"], by_id["000000000000000b"], by_id["000000000000000c"]
    assert "openinference.span.kind" not in a.attrs and a.attrs["tool.name"] == "search"
    assert (a.kind, a.operation) == ("tool", "tool")
    assert "traceloop.span.kind" not in b.attrs
    assert (b.kind, b.operation) == ("agent", "workflow")
    # The standard still decides the kind and names the operation; the vendor key is lifted, not kept.
    assert "openinference.span.kind" not in c.attrs
    assert (c.kind, c.operation) == ("llm", "chat")
