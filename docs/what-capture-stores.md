# What capture stores

`[capture]` in the sweep file turns on OpenTelemetry capture. Two of its four fields decide what
ends up in the store: `content` and `max_observation_bytes`.

What a run expects of its steps, outcomes and gates is a separate table, `[declare]`:
[What a declaration checks](what-a-declaration-checks.md) says what Prove does with it.

## Prompts and completions: `content`

**`content` is `false` by default, and under that default prompts and completions never leave
the process.** An attribute is dropped when its key is:

- `gen_ai.input.messages` or `gen_ai.output.messages`;
- one of `gen_ai.prompt`, `gen_ai.completion`, `traceloop.entity.input`,
  `traceloop.entity.output`, `llm.input_messages`, `llm.output_messages`, or anything under them.

It is dropped in the child process, before the span is serialised, so it reaches neither the pipe
nor the Parquet file. `content = true` keeps all of it.

## Tool arguments and results

**Tool arguments and results are kept whichever way `content` is set.**
`gen_ai.tool.call.arguments` and `gen_ai.tool.call.result` are what the agent *did* rather than
what the model was told, and a run that cannot see them cannot tell a wrong tool call from a right
one. If they carry data you will not store, do not instrument that span.

## OpenInference's `input.value` and `output.value`

`input.value` and `output.value` are OpenInference's prompt and answer on a model call, and its
arguments and result on a tool call. Under `content = false` they are dropped from a span that is a
model call (its `gen_ai.operation.name`, or OpenInference's span kind, says `llm`) and kept on
every other span, like the tool attributes above.

## One value's size: `max_observation_bytes`

**`max_observation_bytes` is required, and bounds one observation value.** Every `[capture]` table
declares it and the tool supplies no number of its own: a wrong number fails silently, where a
missing declaration fails loudly, at parse, before the run exists.

A value whose byte form is larger than the declared limit is stored as:

- its leading `limit - limit // 4` bytes;
- its trailing `limit // 4` bytes;
- its original byte length.

Together they are never more than the limit, at any limit. Under `max_observation_bytes = 64`, a
tool result of 306 bytes is stored as 48 bytes, 16 bytes and its length:

<!-- docs-check: run -->
```json
{
  "gen_ai.tool.call.result": {
    "poisson_prove.truncated": {
      "bytes_original": 306,
      "head": "order 012345678901234567890123456789012345678901",
      "tail": "4567890123456789"
    }
  }
}
```

Lowering the limit is the supported way to measure how large observations really are without
storing them: every value's true length is still recorded, though the values themselves are not
kept.

### `"none"` keeps every value whole

**`max_observation_bytes = "none"` is the one spelling of *no bound*.** It is a declaration like
any other: the manifest records `none`, and `report`, the receipt, the viewer page and `inspect`
read it back as `none`. That is a different fact from a run that recorded no limit at all, and it
prints in different words.

### No `[capture]` table

**A sweep file with no `[capture]` table declares nothing and is not refused.** It did not ask for
capture, and what reaches the store on that path is a rollout's own `record()` trace, which is
stored whole.

### A resume keeps the declaration

`--resume` of a run whose `[capture]` table differs from what the run recorded is refused rather
than mixed into one run.

## A cut is not silent

`poisson-prove inspect` prints an `observation: cut (...)` line above the span lines of any row
whose trace has a cut span. It names each cut span by the index it prints under, its values'
original size in bytes, and the limit the run recorded:

<!-- docs-check: skip: a line of inspect's output on a run made for this page, not a command -->
```text
observation: cut (limit max_observation_bytes=64; span 2: 306 bytes originally)
```

`report` and `serve` print, for each run, in the provenance list of `report.md`, `receipt.html`
and the viewer page:

- the byte limit it recorded;
- how many spans its stored traces hold;
- how many of them were stamped as cut.

The count is over spans, read from the stored envelopes and nothing else, and a span with two cut
values counts once. A run written by an older version that cut values differently recorded its
limit under another name and stamped nothing, so its counts read `not counted` and never `0`. A
run with no capture record reads `not recorded` for the limit.

## A misspelt table or key is refused

The sweep file is checked whole when it is read: a `[declair]` table, or an unknown key inside
`[declare]`, `[capture]` or `[chaos]`, is refused with its line and the nearest name the spec has,
before anything runs:

<!-- docs-check: skip: the refusal of a misspelt sweep file made for this page, not a command -->
```text
error: prove.toml, line 14: [declair] is not a key or table a sweep spec has; the nearest known key is "declare"
```

[The sweep spec](sweep-spec.md) lists every key.
