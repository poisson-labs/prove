# Fault injection

How does your agent cope when its model misbehaves: an error in place of an answer, a tool call
with broken arguments, no tool call at all, a reply cut short? A `[chaos]` table in the sweep spec
injects one such fault into the responses your agent's client receives, at a rate you choose and
only where you say. Run the same spec with and without it, paired, and `diff` says per condition
how much worse the fault made things.

It needs no package of its own: Prove hooks the `httpx` client your agent's model client is built
on (the OpenAI client is, and the `agent` extra brings it), and the agent's code is not changed.

## Where a fault can land: `position()`

A fault is injected only into a call made inside a `position()` block, which your agent uses to
say which logical step it is in, and which attempt:

<!-- docs-check: skip: a fragment of an agent, not a whole program -->
~~~python
from poisson_prove.chaos import position

with position("choose_tool", attempt=1):
    reply = client.chat.completions.create(...)
~~~

A call outside every `position()` passes through untouched. Whether a fault fires is decided from
the episode's seed and the position, never from a count of calls: the same seed and position
always get the same decision, so a change to your agent that adds or removes calls elsewhere does
not move where the faults land, and two runs that differ only in the fault are faulted at the
same places.

## The `[chaos]` table

| key | default | what it is |
|---|---|---|
| `fault` | `"none"` | the fault's name, from the list below; `none` injects nothing |
| `rate` | `1.0` | the share of eligible positions that get the fault, from 0 to 1 |
| `steps` | every step | only positions with one of these names are eligible |

A fault that cannot apply stops the sweep, never a quiet no-op. An unknown name, or a faulted run
whose process has no `httpx` client loaded, passes `--dry-run` but stops the sweep before any
episode runs, as an unexpected failure (exit 3) whose details are in
`~/.cache/poisson-prove/errors.log`; nothing is stored, so check the name against the list below.
A target path missing from a response, a mutation that changes nothing, or a streamed response at
an eligible position fails the episode. The table is not part of the sweep's identity, so a faulted run
paired with a clean one shares its seeds.

## The faults

Each mutates one Chat Completions response body.

| fault | what the agent receives |
|---|---|
| `llm_error_single` | the message text replaced by an HTTP 500 error message |
| `llm_timeout_single` | the message text replaced by a time-out message |
| `llm_empty_single` | an empty message |
| `llm_truncate_single` | the message cut to its first 30% |
| `llm_corrupt_single` | the message garbled, as text decoded with the wrong encoding |
| `llm_schema_single` | the message replaced by a content-policy error object |
| `tool_error_single` | the first tool call's arguments replaced by `{}` |
| `tool_timeout_single` | the first tool call dropped |
| `tool_empty_single` | no tool calls at all |
| `tool_truncate_single` | the first tool call's arguments cut to their first 30% |
| `tool_corrupt_single` | the first tool call's arguments garbled with stray Unicode |
| `tool_schema_single` | the first tool call's arguments replaced by a parameter it does not take |
| `compound_api_degradation` | a 3 s delay, then the message replaced by an HTTP 503 message |
| `compound_content_filter` | no tool calls, a content-filter message, and finish reason `content_filter` |
| `compound_max_tokens` | the message cut to half, and finish reason `length` |
| `compound_proxy_html` | the message replaced by a proxy's HTML error page |
| `compound_stale_data` | the first tool call's arguments replaced by stale values |
| `compound_wrong_entity` | the first tool call's arguments replaced by the wrong entity |
| `compound_slow_response` | a 5 s delay, the response otherwise unchanged |
| `none` | nothing: the clean run |

The names, what each targets and the replacement text come from AgentChaos, an MIT-licensed fault
catalogue for agents; Prove copies its vocabulary and none of its code, and implements every
mutation itself. [NOTICE](../NOTICE) carries the attribution and its licence.

## An example

A stand-in agent asks a stand-in model which tool to call. The model answers in process, through
`httpx`'s own mock transport, so this runs with no key and no network:

<!-- docs-check: run -->
~~~bash
pip install "poisson-prove[agent]"
~~~

<!-- docs-check: file tool_agent.py -->
~~~python
"""A stand-in agent that asks a model which tool to call. The model is an in-process stand-in
behind httpx; a real agent's client sends the same request over the wire."""
import json

import httpx

from poisson_prove import Episode
from poisson_prove.chaos import position

CALL = {"id": "call-1", "type": "function", "function": {"name": "lookup_order", "arguments": '{"order": 42}'}}
REPLY = {"choices": [{"index": 0, "finish_reason": "tool_calls",
                      "message": {"role": "assistant", "content": None, "tool_calls": [CALL]}}]}


def model(request):
    return httpx.Response(200, json=REPLY)


def rollout(cfg, seed):
    client = httpx.Client(transport=httpx.MockTransport(model), base_url="http://model.test")
    with position("choose_tool"):
        reply = client.post("/v1/chat/completions", json={"model": "m", "case": cfg["case"]}).json()
    calls = reply["choices"][0]["message"].get("tool_calls") or []
    if not calls:
        outcome = "no_tool_call"
    else:
        try:
            json.loads(calls[0]["function"]["arguments"])["order"]
            outcome = "acted"
        except (ValueError, KeyError):
            outcome = "bad_arguments"
    return Episode(outcome=outcome, t=1, horizon=1, meta={"case_id": cfg["case"]})
~~~

<!-- docs-check: file clean.toml -->
~~~toml
target = "tool_agent:rollout"
target_id = "tool-agent"
t_unit = "calls"
replicates = 200

[axes.case]
type = "categorical"
values = ["order-42", "order-77"]

[declare]
outcomes = ["acted", "no_tool_call", "bad_arguments"]
failures = ["no_tool_call", "bad_arguments"]
successes = ["acted"]
~~~

The faulted spec is the same with a `[chaos]` table: no tool call in a fifth of the replies.

<!-- docs-check: file faulted.toml -->
~~~toml
target = "tool_agent:rollout"
target_id = "tool-agent"
t_unit = "calls"
replicates = 200

[axes.case]
type = "categorical"
values = ["order-42", "order-77"]

[chaos]
fault = "tool_empty_single"
rate = 0.2

[declare]
outcomes = ["acted", "no_tool_call", "bad_arguments"]
failures = ["no_tool_call", "bad_arguments"]
successes = ["acted"]
~~~

<!-- docs-check: run -->
~~~console
$ poisson-prove sweep clean.toml --yes
plan  400 rollouts of tool-agent: 2 cells x 200 replicates on local, $0 (local)
…
$ poisson-prove sweep faulted.toml --yes --pair-with latest
plan  400 rollouts of tool-agent: 2 cells x 200 replicates on local, $0 (local)
…
$ poisson-prove diff
worse  no_tool_call: … safer, … worse (paired test on shared seeds)
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
…
~~~

Each run's manifest records what it asked for and what was armed: the fault, its rate, its steps
and the client hooks installed. A clean run records that it installed none, so it cannot be
mistaken for a faulted run whose fault failed to arm.
