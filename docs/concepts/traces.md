# Traces

A trace is what one episode did, step by step: each model call, tool call or check as a span, with
its start and end, its parent, where in the code it ran, and what went in and came out. Prove
stores an episode's trace with the episode, so `inspect` can show you how a failed episode got
there, and a run's declared steps can be checked against what it actually ran.

A trace is never needed to compare two runs: the comparison reads outcomes and times only. It is
there to explain them.

## Where a trace comes from

- **`[capture]`**, for an agent already instrumented with OpenTelemetry: the sweep switches on the
  instrumentors you name in the process that runs the rollout, and each episode's spans are stored
  with it. See [Your own agent](../your-own-agent.md#a-traced-agent-capture).
- **`record()` and `@step`**, for the calls nothing else can see, recorded by your rollout itself.
- **The converters**, `poisson_prove.trace.from_otel` and `from_litellm`, for spans or call logs
  you collected some other way.

Every trace has the same shape, `poisson-prove.trace/1`, whatever made it.

## Recording a trace yourself

Open `collect()` around the episode, record each step inside it, and return the trace in the
episode's `meta` under `trace`:

<!-- docs-check: file traced_agent.py -->
```python
import random

from poisson_prove import Episode, record, step
from poisson_prove.trace import collect


@step
def lookup_order(order):
    return {"order": order, "status": "shipped"}


def rollout(cfg, seed):
    rng = random.Random(seed)
    with collect() as collected:
        with record("llm", "plan", input=f"ticket {cfg['ticket']}", step_name="plan") as span:
            span.output = "call lookup_order"
            span.tokens = {"input": 120, "output": 8}
        lookup_order(42)
        with record("tool", "check_refund", step_name="check", gate="emitted") as span:
            approved = rng.random() < 0.8
            span.outcome, span.outcome_by = ("pass" if approved else "fail"), "code"
    outcome = "resolved" if approved else "refused"
    meta = {"case_id": cfg["ticket"], "trace": collected.trace.to_dict()}
    return Episode(outcome=outcome, t=3, horizon=10, meta=meta)
```

<!-- docs-check: run -->
```python
from poisson_prove.trace import Trace
from traced_agent import rollout

episode = rollout({"ticket": "refund"}, seed=3)
for span in Trace.from_dict(episode.meta["trace"]).ordered():
    print(span.kind, span.name, span.step_name, span.gate, span.outcome)
```

`record(kind, name)` opens one span. `kind` is one of `llm`, `tool`, `retrieval`, `db`, `http`,
`agent` and `other`. What is known when the span opens is passed to `record()`: its `input`, any
`attrs`, the logical step it executes (`step_name`), which try of that step it is (`attempt`,
from 1, only if your code counts them), and `gate="emitted"` when the step is a check your
agent's control flow consults. What is known after is set on the handle the block yields:
`output`, `tokens`, `confidence`, `error`, and a check's verdict as `outcome` with who decided it,
`outcome_by` (`code`, `llm`, `self` or `human`). `@step` records every call of a function as a
`tool` span (or the kind you give it, `@step(kind="db")`).

Outside a `collect()` block `record()` and `@step` do nothing, so they are safe to leave in
production code. A value the schema refuses (an `attempt` of 0, an unknown `kind`) drops that span
with a warning and never raises: a recorder must not change the rollout's result.

## What `[capture]` does in the process

When a sweep has a `[capture]` table, the process that runs the rollout installs an OpenTelemetry
tracer provider, switches on the instrumentors named in `instrument`, and opens a collector around
each episode. Every span is stamped with the run's id and the episode's (`poisson_prove.run_id`,
`poisson_prove.episode`), so spans from concurrent work are not mixed up. On the way to the store:

- with `content = false`, prompts and completions are dropped inside the process, before the span
  is serialised;
- a value larger than `max_observation_bytes` is stored as its head, its tail and its length;
- with `max_spans`, the earliest-started spans are kept, so the root survives;
- an episode stopped at `--episode-timeout` keeps the spans it had, its open span marked.

Nothing is sent anywhere: the spans go to the local store and nowhere else.
[What capture stores](../what-capture-stores.md) has the exact rules.

## Where traces show

`inspect` prints an episode's spans under its condition and seed, one line each, with errors
marked. A run with a `[declare]` table of `steps` and `gates` is checked against its stored spans:
`report`, the receipt, `serve` and `inspect` list the declared steps no span carried
(`never reached`) and the steps seen that were not declared. `retain_traces_for` in the sweep spec
keeps only the traces of the outcomes you name, to keep a large store small.
