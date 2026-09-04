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
