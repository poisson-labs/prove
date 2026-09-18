# What capture stores

`[capture]` in the sweep file turns on OpenTelemetry capture. Two of its four
fields decide what ends up in the store.

**`content` is `false` by default, and under that default prompts and
completions never leave the process.** An attribute whose key is
`gen_ai.input.messages` or `gen_ai.output.messages`, or which is one of
`gen_ai.prompt`, `gen_ai.completion`, `traceloop.entity.input`,
`traceloop.entity.output`, `llm.input_messages`, `llm.output_messages` or
anything under them, is dropped in the child process, before the span is
serialised — so it reaches neither the pipe nor the Parquet file. `content =
true` keeps all of it.

**Tool arguments and results are kept whichever way `content` is set.**
`gen_ai.tool.call.arguments` and `gen_ai.tool.call.result` are what the agent
*did* rather than what the model was told, and a run that cannot see them cannot
tell a wrong tool call from a right one. If they carry data you will not store,
do not instrument that span.

One gap, named rather than left to be discovered: `input.value` and
`output.value` on an **`llm`** span are prompt content under OpenInference's
convention, and the default keeps them. The strip runs on the attribute key
alone, before a span's kind is known, so closing that is a later change.

**`max_observation_bytes` (default 8192) bounds one observation value.** A value
whose byte form is larger is stored as its leading `limit - limit // 4` bytes,
its trailing `limit // 4` bytes and its original byte length — together never
more than the limit, at any limit. Lowering it is the supported way to measure
how large observations really are without storing them: every value's true
length is still recorded.
