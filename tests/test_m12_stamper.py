"""M12 -- the episode stamper: the oracle for T31-T34.

Written from the invariants added to "Proofload -- Spec M12 Trace" section 4 after the
2026-09-04 OTel spike, which found that a per-episode *resource* attribute cannot be varied
inside one process: ``Resource.attributes`` is immutable, ``TracerProvider.resource`` has no
setter, and a second ``set_tracer_provider()`` is refused. Proofload therefore stamps
``proofload.run_id`` and ``proofload.episode`` as *span* attributes, which land in the same
place once ``from_otel`` merges resource, scope and span attributes into ``attrs``.

Every test imports ``proofload.otel`` inside its own body, the way the M12 oracle does, so the
file collects while the module does not exist. The stamper lives behind the ``agent`` extra;
the whole file skips when the SDK is absent so a core-only install still runs green.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

pytest.importorskip("opentelemetry.sdk", reason="the stamper lives behind the [agent] extra")

from opentelemetry.sdk.resources import Resource  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

RUN_ID_SPEC = "poisson_prove.run_id"
EPISODE_SPEC = "poisson_prove.episode"


def build() -> tuple[Any, InMemorySpanExporter, Any]:
    """A provider with the stamper registered, its exporter, and a tracer. No global state."""
    from poisson_prove.otel import EpisodeStamper

    provider = TracerProvider(resource=Resource.create({"service.name": "oracle"}))
    provider.add_span_processor(EpisodeStamper())
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter, provider.get_tracer("oracle.instrumentation", "0.1.0")


def as_otlp(exporter: InMemorySpanExporter) -> Any:
    """The finished spans as the OTLP/JSON payload ``from_otel`` actually consumes."""
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
    return MessageToDict(encode_spans(exporter.get_finished_spans()))


def attrs_by_name(exporter: InMemorySpanExporter) -> dict[str, dict[str, Any]]:
    return {s.name: dict(s.attributes or {}) for s in exporter.get_finished_spans()}


# ---------- T31: the ContextVar is set for the block and reset after it ----------


def test_t31_episode_sets_and_resets_the_context_var() -> None:
    from poisson_prove.otel import EPISODE_KEY, RUN_ID_KEY, episode

    assert (RUN_ID_KEY, EPISODE_KEY) == (RUN_ID_SPEC, EPISODE_SPEC)

    _, exporter, tracer = build()
    with tracer.start_as_current_span("before"):
        pass
    with episode("r-a", "cfg-7:seed-3"):
        with tracer.start_as_current_span("inside"):
            pass
    with tracer.start_as_current_span("after"):
        pass

    seen = attrs_by_name(exporter)
    assert seen["inside"][RUN_ID_KEY] == "r-a"
    assert seen["inside"][EPISODE_KEY] == "cfg-7:seed-3"
    for name in ("before", "after"):
        assert RUN_ID_KEY not in seen[name], name
        assert EPISODE_KEY not in seen[name], name


def test_t31_the_context_var_is_reset_even_when_the_block_raises() -> None:
    from poisson_prove.otel import EPISODE_KEY, RUN_ID_KEY, episode

    _, exporter, tracer = build()

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with episode("r-a", "cfg-1:seed-0"):
            raise Boom("mid-episode")
    with tracer.start_as_current_span("after_the_raise"):
        pass

    seen = attrs_by_name(exporter)["after_the_raise"]
    assert RUN_ID_KEY not in seen and EPISODE_KEY not in seen


def test_t31_nested_episodes_restore_the_enclosing_one() -> None:
    from poisson_prove.otel import EPISODE_KEY, episode

    _, exporter, tracer = build()
    with episode("r-a", "outer"):
        with episode("r-a", "inner"):
            with tracer.start_as_current_span("in_inner"):
                pass
        with tracer.start_as_current_span("back_in_outer"):
            pass

    seen = attrs_by_name(exporter)
    assert seen["in_inner"][EPISODE_KEY] == "inner"
    assert seen["back_in_outer"][EPISODE_KEY] == "outer"


# ---------- T32: stamped spans carry both keys, and they survive from_otel ----------


def test_t32_both_keys_reach_attrs_through_from_otel() -> None:
    from poisson_prove.trace import from_otel

    from poisson_prove.otel import EPISODE_KEY, RUN_ID_KEY, episode

    provider, exporter, tracer = build()
    with episode("r-2026-09-04", "cfg-7:seed-3"):
        with tracer.start_as_current_span("invoke_agent planner") as parent:
            parent.set_attribute("gen_ai.operation.name", "invoke_agent")
            with tracer.start_as_current_span("chat gpt-4o") as child:
                child.set_attribute("gen_ai.operation.name", "chat")
                child.set_attribute("gen_ai.request.model", "gpt-4o-2024-08-06")
    provider.force_flush()

    trace = from_otel(as_otlp(exporter))
    assert trace.dropped == 0 and len(trace.spans) == 2
    for span in trace.spans:
        assert span.attrs[RUN_ID_KEY] == "r-2026-09-04", span.name
        assert span.attrs[EPISODE_KEY] == "cfg-7:seed-3", span.name
    # The stamp does not disturb the rest of the section 3 mapping.
    kinds = {s.kind for s in trace.spans}
    assert kinds == {"agent", "llm"}
    assert len(trace.roots()) == 1


def test_t32_each_episode_gets_its_own_values_in_one_process() -> None:
    from poisson_prove.trace import from_otel

    from poisson_prove.otel import EPISODE_KEY, RUN_ID_KEY, episode

    provider, exporter, tracer = build()
    wanted = [("r-a", "cfg-7:seed-3"), ("r-a", "cfg-7:seed-4"), ("r-b", "cfg-2:seed-0")]
    for run_id, ep in wanted:
        with episode(run_id, ep):
            with tracer.start_as_current_span(f"execute_tool {ep}") as span:
                span.set_attribute("gen_ai.operation.name", "execute_tool")
                span.set_attribute("gen_ai.tool.name", ep)
    provider.force_flush()

    trace = from_otel(as_otlp(exporter))
    assert trace.dropped == 0 and len(trace.spans) == 3
    got = {(s.attrs[RUN_ID_KEY], s.attrs[EPISODE_KEY]) for s in trace.spans}
    assert got == set(wanted)


# ---------- T33: an unstamped span carries neither key and is not repaired ----------


def test_t33_a_span_outside_any_episode_carries_neither_key() -> None:
    from poisson_prove.trace import from_otel

    from poisson_prove.otel import EPISODE_KEY, RUN_ID_KEY, episode

    provider, exporter, tracer = build()
    with episode("r-a", "cfg-1:seed-1"):
        with tracer.start_as_current_span("inside"):
            pass
    with tracer.start_as_current_span("outside"):
        pass
    provider.force_flush()

    trace = from_otel(as_otlp(exporter))
    assert trace.dropped == 0 and len(trace.spans) == 2
    by_name = {s.name: s for s in trace.spans}
    assert by_name["inside"].attrs[RUN_ID_KEY] == "r-a"
    assert RUN_ID_KEY not in by_name["outside"].attrs
    assert EPISODE_KEY not in by_name["outside"].attrs
    # Unstamped is a signal, not a defect: the span is kept, not dropped.
    assert by_name["outside"].kind == "other"


# ---------- T34: concurrent asyncio episodes stay separated ----------


def test_t34_two_concurrent_asyncio_episodes_do_not_see_each_other() -> None:
    from poisson_prove.trace import from_otel

    from poisson_prove.otel import EPISODE_KEY, RUN_ID_KEY, episode

    provider, exporter, tracer = build()

    async def one(run_id: str, ep: str) -> None:
        with episode(run_id, ep):
            with tracer.start_as_current_span(f"{ep}:outer"):
                await asyncio.sleep(0)
                with tracer.start_as_current_span(f"{ep}:nested"):
                    await asyncio.sleep(0)

    async def main() -> None:
        await asyncio.gather(one("r-a", "cfg-7:seed-3"), one("r-b", "cfg-2:seed-0"))

    asyncio.run(main())
    provider.force_flush()

    trace = from_otel(as_otlp(exporter))
    assert trace.dropped == 0 and len(trace.spans) == 4
    expected = {"cfg-7:seed-3": "r-a", "cfg-2:seed-0": "r-b"}
    for span in trace.spans:
        ep = span.name.split(":outer")[0].split(":nested")[0]
        assert span.attrs[EPISODE_KEY] == ep, (span.name, dict(span.attrs))
        assert span.attrs[RUN_ID_KEY] == expected[ep], (span.name, dict(span.attrs))
