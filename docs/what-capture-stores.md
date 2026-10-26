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

`input.value` and `output.value` are OpenInference's prompt and answer on a
model call, and its arguments and result on a tool call. Under `content =
false` they are dropped from a span that is a model call (its
`gen_ai.operation.name`, or OpenInference's span kind, says `llm`) and kept on
every other span, like the tool attributes above.

**`max_observation_bytes` is required, and bounds one observation value.** Every
`[capture]` table declares it and the tool supplies no number of its own: a
wrong number fails silently, where a missing declaration fails loudly, at parse,
before the run exists. A value whose byte form is larger than the declared limit
is stored as its leading `limit - limit // 4` bytes, its trailing `limit // 4`
bytes and its original byte length — together never more than the limit, at any
limit. Lowering it is the supported way to measure how large observations really
are without storing them: every value's true length is still recorded, though
the values themselves are not kept.

**`max_observation_bytes = "none"` keeps every value whole.** It is the one
spelling of *no bound*, and it is a declaration like any other: the manifest
records `none`, and `report`, the receipt, the viewer page and `inspect` read it
back as `none` — which is a different fact from a run that recorded no limit at
all, and prints in different words.

**A sweep file with no `[capture]` table declares nothing and is not refused.**
It did not ask for capture, and what reaches the store on that path is a
rollout's own `record()` trace, which is stored whole. Nothing is backfilled: a
run stored by an older version keeps what it recorded, under the spelling it
recorded it in.

**A sweep file written for an older version** has no `max_observation_bytes`:
those versions stored every value up to 8192 bytes whole. Add
`max_observation_bytes = 8192` to store what they stored — and to `--resume` a
run one of them began, since a resume whose declaration differs from what the
run recorded is refused rather than mixed into one run.

**A cut is not silent.** `poisson-prove inspect` prints an `observation: cut (...)`
line above the span lines of any row whose trace has a cut span, naming each cut
span by the index it prints under, its values' original size in bytes, and the
limit the run recorded. `report` and `serve` print, for each run, the byte limit
it recorded, how many spans its stored traces hold and how many of them were
stamped as cut, in the provenance list of `report.md`, `receipt.html` and the
viewer page. The count is over spans, read from the stored envelopes and nothing
else, and a span with two cut values counts once. A run written by an older
version that cut values differently recorded its limit under another name and
stamped nothing, so its counts read `not counted` and never `0`; a run with no capture record reads
`not recorded` for the limit.

**A sweep file may declare what the run expects.** A `[declare]` table names
the steps the target is expected to execute (`steps`), the outcome labels it
can emit (`outcomes`), which of those steps are gates (`gates`, a subset of
`steps`), and which outcomes are failures and which successes (`failures`,
`successes`). Any of them may be absent; a table that declares nothing is
refused, and so is a duplicate — a repeated name in a hand-written list is a
typo, and collapsing it would be guessing at what was meant. The declaration is recorded on the
run's manifest as `declared`. It is not part of the sweep's identity, so a
declaring arm and a non-declaring arm derive the same seeds and still pair
under `diff`. On the way to the store, a span whose `step_name` is a declared
gate and which carries no gate of its own is stamped `gate = "declared"`; a
span the target itself marked `"emitted"` keeps that.

**What `never reached` means, and what it does not.** For a run that declared,
`report`, the receipt, `serve` and `inspect` print, against the declaration:
the declared steps, the declared steps no span in this run carried (`never
reached`), the observed step names the declaration does not name, the declared
outcomes, the observed outcomes it does not name, the declared gates, the
declared gates with no span (`gates never reached`), and the gates the target
emitted that the declaration does not name. A declared step with no span means
exactly that: this run's spans did not show it. It does not mean the target
cannot reach the step; it does not mean the step was not instrumented; it does
not mean anything is wrong — a sweep whose configs never take the `verify`
branch reports `never reached: verify` correctly, and that is the finding; and
it says nothing at all about a run with no declaration, for which the lines do
not exist and the phrase appears nowhere. A declaration that matches nothing,
as on a run whose capture was off for the whole run, prints every declared step
and is not refused. `diff` refuses two runs that declare different, non-empty
outcome sets, since two competing sets are two quantities wearing one name;
`--resume` refuses a sweep whose declaration differs from what the run
recorded, while `--pair-with` does not.

**A misspelt table or key is refused.** The sweep file is checked whole when it
is read: a `[declair]` table, or an unknown key inside `[declare]`, `[capture]`
or `[chaos]`, is refused with its line and the nearest name the spec has, before
anything runs. [The sweep spec](sweep-spec.md) lists every key.
