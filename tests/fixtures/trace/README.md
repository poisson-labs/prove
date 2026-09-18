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
  P8-14, P8-16). **A8b does not extend this file**, against spec A8b §6: A8a's frozen `loop_spans()` helper asserts
  `len(tr.spans) == 16`, so a seventeenth span would turn five A8a tests red. A8b's over-limit spans
  are in `otlp_cut.json` below; every span here is A8a's.
- `otlp_cut.json` — **A8b's fixture** (spec A8b §6), a flat span list of two spans built at the default limit of 8192 bytes by
  a fixed recipe. Span 1 is an `execute_tool` span whose `gen_ai.tool.call.result` is 24,576 bytes (3 × limit): `"r" * 6143`, a
  three-byte `€` straddling byte 6144, `"m" * 16381`, a second `€` straddling byte `L − 2048`, then `"t" * 2046` — so the cut's head is
  6,143 bytes and its tail 2,046, each one UTF-8 back-off short of its bound. Span 2 carries four attributes outside
  `OBSERVATION_KEYS` — `app.debug.dump` (16,384 bytes, 2 × limit), `app.note.at_limit` (exactly 8,192), `app.note.over_by_one` (8,193)
  and `app.note.small` — and both routing stamps, `proofload.run_id` at 9,000 bytes (over the limit on purpose: a stamp under it proves
  nothing). Used by `tests/test_a8b_cut_and_cap.py` (P8-7, P8-10, P8-11, P8-20). Nothing here was captured live.
