# M12 trace fixtures

Hand-built payload dicts for `tests/test_m12_trace.py`, written from the shapes in
"Proofload — Spec M12 Trace" §3. Nothing here was captured live: no network, no API key.

- `otlp_agent_chat.json` — a full OTLP/JSON payload (`resourceSpans` → `scopeSpans` → `spans`)
  with `proofload.run_id` / `proofload.episode` resource attributes, one scope attribute, and an
  `invoke_agent` root span with a `chat` child. Timestamps are protobuf-JSON strings; span ids
  are hex. Used by T20, T23, T25, T27.
- `otlp_kinds.json` — a flat span list covering every `OTEL_KIND_MAP` entry, the `db.system` /
  `http.request.method` / `url.full` / nothing fallbacks, an unrecognized operation name, and
  two error-status spans (`status.message` and `error.type`). Used by T20 and the §3 kind map.
- `otlp_aliases.json` — one span spelled with the deprecated `code.filepath` key. Used by T20.
- `otlp_dropped.json` — six spans, four unusable, one per `DROP_REASONS` entry. Used by T22.
- `otlp_encodings.json` — the same span three ways: camelCase + string nanoseconds + base64
  ids, snake_case + integer nanoseconds + hex ids, camelCase + integer + hex. Used by T21.
- `litellm_calls.json` — three LiteLLM logging payloads. `start_time` / `end_time` are stored as
  ISO-8601 strings and converted to `datetime` by the test before `from_litellm` sees them.
  The first carries logprobs and no confidence. Used by T24 and T27.
- `otlp_loop.json` — **A8a's fixture** (spec A8a §6), a flat span list of sixteen spans: `graph.node.{id,name,parent_id}`
  on the loop spans; `proofload.attempt` 1 and 2 on two spans sharing `step_name` `lookup` and a
  third of that name with no counter; three `check` spans under one parent with no counter at all
  (P8-5); an `openinference.span.kind` of `GUARDRAIL`, of `EVALUATOR`, and a span *named*
  `guardrail` whose kind attribute is `TOOL`; `proofload.gate = "declared"` and `"emitted"` on the
  wire, each beside a `proofload.step_name`; `proofload.outcome` / `proofload.outcome_by` on the two
  counted attempts; a `gen_ai.operation.name` conflicting with a vendor kind; one
  `traceloop.span.kind`; one unrecognised operation spelled with case and whitespace; and one status
  of each of `OK`, `UNSET`, `ERROR`. Used by `tests/test_a8a_span_schema.py` (P8-4, P8-5, P8-6,
  P8-14, P8-16). **A8b extends this file** with the two over-limit spans A6 §6 lists (a 3 × limit
  `gen_ai.tool.call.result` and a 2 × limit non-observation attribute); they are not here because
  A8a names no byte threshold.
