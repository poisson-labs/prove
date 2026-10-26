# A model change, with its cost

A cheaper model would save money. Does your agent fail more often on it, and what would it save?
Prove answers the first question per condition, with the smallest change each condition could
have caught, and records what each run's requests cost in tokens. The decision you are after
reads: cheaper model, same failure rate within the detectable change.

## Both models side by side

Put the model on an axis and one sweep runs both, on the same cases. The rollout reads it from
`cfg`, and a `[capture]` table stores each request's spans, with the token usage the provider
reported:

<!-- docs-check: file models.toml -->
```toml
target = "my_agent:rollout"
target_id = "support"
t_unit = "steps"
replicates = 200

[axes.model]
type = "categorical"
values = ["gpt-4.1", "gpt-4.1-mini"]

[axes.ticket]
type = "categorical"
values = ["refund", "password", "shipping"]

[declare]
outcomes = ["resolved", "unresolved", "timeout"]
failures = ["unresolved", "timeout"]
successes = ["resolved"]

[capture]
instrument = ["openai"]
content = false
max_observation_bytes = 16384
```

<!-- docs-check: skip: needs two model keys -->
```bash
poisson-prove sweep models.toml --yes --name both-models
poisson-prove report both-models --x model --y ticket --event unresolved
```

The report shows each model's share of unresolved tickets, per ticket type, with a 95% interval on
each. That is a description, not a test: `diff` compares the same condition across two runs, and
`model=gpt-4.1` and `model=gpt-4.1-mini` are different conditions of one run.

## The test: one model per run, paired

To test the switch, make the model the change between two runs, as you would a prompt: one rollout
function per model, the conditions without a model axis, the second run paired with the first.

<!-- docs-check: skip: needs two model keys -->
```python
def rollout_current(cfg, seed):
    return run_ticket(cfg["ticket"], model="gpt-4.1", seed=seed)


def rollout_cheaper(cfg, seed):
    return run_ticket(cfg["ticket"], model="gpt-4.1-mini", seed=seed)
```

<!-- docs-check: skip: needs two model keys -->
```bash
poisson-prove sweep tickets.toml --yes --target my_agent:rollout_current --name current
poisson-prove sweep tickets.toml --yes --target my_agent:rollout_cheaper --pair-with current --name cheaper
poisson-prove diff current cheaper
poisson-prove check current cheaper --event unresolved --event timeout --fail-on worse
```

`no significant change` is the answer you hoped for, and it means exactly this: in no ticket type
did the cheaper model fail significantly more often, and each ticket type could have shown a change
as large as the one you accepted when you swept (`--max-mde`, 0.20 by default), 4 times in 5. If it
says `too small to tell`, some ticket type could not have: more replicates, or a larger change you
are willing to accept. If it says `worse`, the cheaper model costs you reliability somewhere, and
the table says where.

## The cost

Before the full sweep, check that a pilot pair stays inside your budget. `paired`'s cost check
sums the input tokens recorded on the request spans of the runs a paired-replay declaration names,
against the `token_cap` it declares. The declaration needs every key of
[Paired replay](paired-replay.md), and its `request_span` must be the exact name of the span that
holds the model call in both runs:

<!-- docs-check: skip: needs two model keys -->
```bash
poisson-prove paired --declaration pilot.toml --cap-check
```

It exits 4 at or above the cap, so a script can stop before the full sweep spends more. It counts
input tokens only, and the dollars are your declared price times those; Prove carries no price
list for model providers. What the switch saves is yours to compute: each run's input and output
tokens per episode, at each model's own prices.

## What this does not tell you

That the cheaper model is as good. It says that on these ticket types, at these replicates, no rise
in its failure rate counted, and that a rise as large as each condition's detection limit would
have been caught 4 times in 5. A smaller rise, or a missed one, can still be there; a ticket type you did not sweep can behave differently; and a model's version
can change behind its name, so record which version each run called.
