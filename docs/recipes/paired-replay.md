# Paired replay

Your pipeline asks a model for a score and acts on a threshold: a grader passes an answer at 0.6,
a router escalates a ticket at 0.8. Send the same request twice; how often does the decision flip?
Paired replay records two arms that send the same requests, checks pair by pair that they did,
and counts the flips at each threshold, with an interval clustered by item.
[`paired`](../commands/paired.md) runs the whole thing on a stand-in grader with no key.

## Record the arms

Each episode makes one request and records it as a span, with the request body as the span's
input, and stores the score in `meta`. The item being scored is one axis of the sweep (each item
its own axis value), and the threshold group (the stratum) another:

<!-- docs-check: skip: needs runs recorded against a real model -->
```python
with collect() as collected:
    with record("llm", "grader.request", input=json.dumps(body)) as span:
        reply = client.chat.completions.create(**body)
        span.tokens = {"in": reply.usage.prompt_tokens, "out": reply.usage.completion_tokens}
meta = {"trace": collected.trace.to_dict(), "grade": {"score": parse_score(reply)}}
```

Then sweep twice on the same seeds, so each pair is the same request sent twice:

<!-- docs-check: skip: needs runs recorded against a real model -->
```bash
poisson-prove sweep grading.toml --yes --name replay-a
poisson-prove sweep grading.toml --yes --pair-with replay-a --name replay-b
```

## Declare it

The declaration is written before you read any result, and every key is checked: an unknown one
is refused, and none of the required ones has a default. The `sweeps` table names the arms by
their run ids, from `poisson-prove runs`.

<!-- docs-check: file replay.toml -->
```toml
value_key = "grade.score"          # where the score is in each episode's meta
cluster_key = "answer"             # the axis that names the item scored
stratum_key = "rubric"             # the axis that names the threshold group
request_span = "grader.request"    # the span that holds the request
model_key = "model"                # the request body's model field
model_pin = "grader-2026-09"       # the model every pair must have called
exemptions = ["x-request-id"]      # headers or transport ids allowed to differ
headers = "not_recorded"           # "asserted" when the arms recorded their headers
retries = "not_recorded"           # "asserted" when they recorded every retry
bootstrap_b = 2000                 # bootstrap resamples behind the intervals
bootstrap_seed = 7
floor = 0.05                       # optional: the flip rate that would matter
token_cap = 2000000                # optional: the input-token budget
price_per_input_token = 0.0000004  # optional: dollars per input token

[[cuts]]
name = "pass-mark"
threshold = 0.60
comparison = "ge"                  # the decision is score >= 0.60

[[sweeps]]
name = "replay"
a = "the run id of replay-a"
b = "the run id of replay-b"
```

Each item is analysed under the cut whose `name` equals its value of the `stratum_key` axis, so
name the cuts after that axis's values. A pair is eligible only when both arms sent one request, with the same body apart from the
exemptions, to the pinned model, and recorded a score between 0 and 1. Every other pair is
excluded under one named cause, and the counts reconcile.

## Run it

Check the spend between sweeps, before the next costs money, then analyse:

<!-- docs-check: skip: needs runs recorded against a real model -->
```bash
poisson-prove paired --declaration replay.toml --cap-check
poisson-prove paired --declaration replay.toml --out replay
```

`--cap-check` sums the input tokens the arms recorded and exits 4 at or above `token_cap`.
`paired` writes five files. Read three:

- `pair_assertion.json`: every pair, eligible or excluded with its cause. Look here first: a
  replay where most pairs were excluded measured little.
- `intervals_by_cut.json`: per cut, `flip_rate`, the share of eligible pairs whose decision differed
  between the arms, with an interval from a bootstrap over items, and `net_swing`, whether the
  flips leaned one way. With a `floor`, an `outcome`: A when the interval sits below the floor,
  B when it excludes zero, C when it spans both.
- `cost.json`: the tokens each arm recorded, and dollars at your price.

`windows.json` says how far apart in time the two arms' requests were; `contingency_by_cut.json`
has the 2 by 2 of decisions behind the flip rate. To fold the replay into a comparison report,
`poisson-prove report replay-a replay-b --x answer --paired replay.toml`.

## What this does not tell you

Whether the model is right. A flip rate of zero says the same request gets the same decision; it
says nothing about whether the decision is correct, or about requests you did not replay. A
replay days apart also measures the provider's drift between them; `windows.json` says how far
apart the arms ran, and a `declared_window_s` says how far apart they were meant to.
