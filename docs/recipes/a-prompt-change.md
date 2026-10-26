# A prompt change

You changed your agent's prompt. Did it leave fewer tickets unresolved, and did it make anything
worse? Run the agent before and after the change on the same cases and the same seeds, compare,
and gate on it.

## The two prompts as two targets

Give the rollout one function per prompt, so each run names its prompt with `--target` and the
spec stays the same. Here the agent is a stand-in that runs as it is; in your code, `answer` is
your agent:

<!-- docs-check: file support.py -->
```python
"""A stand-in support agent: how often it gives up depends on the ticket and the prompt."""
import random

from poisson_prove import Episode

GIVES_UP = {"refund": 0.30, "password": 0.10, "shipping": 0.20}
PROMPT_V1 = "Answer the ticket."
PROMPT_V2 = "Answer the ticket step by step, and check the order before you reply."


def answer(ticket, prompt, seed):
    rng = random.Random(seed)
    steps = rng.randint(2, 20)
    gives_up = GIVES_UP[ticket] * (0.5 if prompt == PROMPT_V2 else 1.0)
    outcome = "timeout" if steps == 20 else "unresolved" if rng.random() < gives_up else "resolved"
    return Episode(outcome=outcome, t=steps, horizon=20, meta={"case_id": ticket})


def rollout_v1(cfg, seed):
    return answer(cfg["ticket"], PROMPT_V1, seed)


def rollout_v2(cfg, seed):
    return answer(cfg["ticket"], PROMPT_V2, seed)
```

<!-- docs-check: file prompt.toml -->
```toml
target = "support:rollout_v1"
target_id = "support"
t_unit = "steps"
replicates = 200

[axes.ticket]
type = "categorical"
values = ["refund", "password", "shipping"]

[declare]
outcomes = ["resolved", "unresolved", "timeout"]
failures = ["unresolved", "timeout"]
successes = ["resolved"]
```

## Before and after, paired

The first run uses the spec's target, the old prompt. The second names the new one and takes the
first run's seeds with `--pair-with latest`:

<!-- docs-check: run -->
```console
$ poisson-prove sweep prompt.toml --yes
plan  600 rollouts of support: 3 cells x 200 replicates on local, $0 (local)
…
$ poisson-prove sweep prompt.toml --yes --target support:rollout_v2 --pair-with latest
plan  600 rollouts of support: 3 cells x 200 replicates on local, $0 (local)
…
  next: poisson-prove diff
$ poisson-prove diff
safer  unresolved: … safer, … worse · timeout: … safer, … worse (paired test on shared seeds); …
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
…
```

`safer`: the new prompt left fewer tickets unresolved in at least one ticket type, and no ticket
type got worse. Time-outs did not move: the stand-in's steps come from the seed alone, and the
seeds are shared.

## The gate

`check` reads the events you name and exits 4 if any condition got worse, so a script or a CI job
stops on it. Here it passes:

<!-- docs-check: run -->
```console
$ poisson-prove check --event unresolved --event timeout --fail-on worse
passed  …
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  comparison  safer
…
```

`--fail-on any` would also fail on a change for the better, for a change you meant to have no
effect. [In CI](in-ci.md) runs this as a build step.

## With a real model

The same shape, with your client. Each prompt is a function; the model and the client are made
inside the rollout, so importing it needs no key:

<!-- docs-check: skip: needs a model key -->
```python
import openai

from poisson_prove import Episode

PROMPT_V1 = "Answer the ticket."
PROMPT_V2 = "Answer the ticket step by step, and check the order before you reply."


def answer(ticket, prompt, seed):
    client = openai.OpenAI()
    reply = client.chat.completions.create(model="gpt-4.1-mini", seed=seed, messages=[
        {"role": "system", "content": prompt}, {"role": "user", "content": TICKETS[ticket]}])
    return Episode(outcome=judge(reply), t=1, horizon=1, meta={"case_id": ticket})
```

<!-- docs-check: skip: needs a model key -->
```bash
poisson-prove sweep prompt.toml --yes
poisson-prove sweep prompt.toml --yes --target support:rollout_v2 --pair-with latest
poisson-prove check --event unresolved --fail-on worse
```

`TICKETS` and `judge` are yours: the ticket texts, and the code that decides how a reply ended.
Pass `seed` to the model where it takes one: a model does not promise the same answer for the
same seed, but it narrows the difference between twins.

## What this does not tell you

Why the new prompt is better, or whether it is better on tickets you did not sweep. It says that,
on these ticket types and these seeds, the share left unresolved fell, by how much, and how small a
rise each ticket type could have caught. A model's answers vary with its version and its
provider's load, so two runs days apart differ in more than the prompt: run them close together.
