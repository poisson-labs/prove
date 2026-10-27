# Your own agent

Prove runs your agent through a rollout, a function you write that runs one case and says how it
ended. A sweep calls it many times, once per condition and replicate, and stores every ending; a
comparison then reads two such runs. This page is the contract, an example that runs as it is,
and the one mistake Prove refuses outright.

If you would rather have your coding agent write the rollout and the spec,
[Set Prove up with your coding agent](setup-with-your-agent.md) does that and stops for you to
review.

## The rollout contract

A rollout is `rollout(cfg, seed) -> Episode`, a plain function of `(cfg, seed)`:

- `cfg` is the condition: a dictionary with one value per axis of the sweep spec, such as
  `{"ticket": "refund", "temperature": 0.7}`.
- `seed` is an integer. Seed every random choice your agent makes from it (a model's `seed`, a
  sampler, your own `random.Random(seed)`). Two runs paired with `--pair-with` get the same seeds,
  which is what lets Prove compare each episode with its twin.
- It returns `poisson_prove.Episode(outcome, t, horizon, meta)`:
  - `outcome`, a name for how the case ended: `resolved`, `timeout`, `refused`, whatever your code
    can tell apart. [Defining outcomes](defining-outcomes.md) says how to choose them.
  - `t`, when it ended, in the spec's `t_unit` (steps, tool calls, seconds), and `horizon`, the
    most `t` could have been. `t` is between 0 and `horizon`.
  - `meta`, a dictionary of anything else, and `case_id` in it: the id of the case this episode
    ran.

A rollout that raises, or returns something that is not an `Episode`, is stored as an errored
episode with the error's type and message, and the sweep goes on. `inspect` shows those.

## An example, end to end

The rollout below wraps a support bot. Here the bot is a stand-in, so that this page runs as it
is; in your repository it is your own code:

<!-- docs-check: file prompts.py -->
```python
SYSTEM = "Answer the customer's ticket. Ask before refunding."
```

<!-- docs-check: file support_bot.py -->
```python
"""A stand-in for your own agent, so this page runs as it is."""
import random
from dataclasses import dataclass

from prompts import SYSTEM

#: Each ticket, as the share of attempts on it that end unresolved.
TICKETS = {"refund": 0.30, "password": 0.10, "shipping": 0.20}


@dataclass
class Reply:
    resolved: bool
    timed_out: bool
    steps: int


def handle(ticket, temperature, seed):
    rng = random.Random(seed)
    steps = rng.randint(2, 20)
    gives_up = ticket * (1 + temperature) * (0.5 if "step by step" in SYSTEM else 1.0)
    return Reply(resolved=steps < 20 and rng.random() >= gives_up, timed_out=steps == 20, steps=steps)
```

The rollout runs the case `cfg` names, maps how it ended to an outcome, and returns the case's id
in `meta`:

<!-- docs-check: file my_rollout.py -->
```python
from poisson_prove import Episode
from support_bot import TICKETS, handle  # your agent and its cases


def rollout(cfg, seed):
    ticket = TICKETS[cfg["ticket"]]
    reply = handle(ticket, temperature=cfg["temperature"], seed=seed)
    if reply.timed_out:
        outcome = "timeout"
    elif reply.resolved:
        outcome = "resolved"
    else:
        outcome = "unresolved"
    return Episode(outcome=outcome, t=reply.steps, horizon=20, meta={"case_id": cfg["ticket"]})
```

The sweep spec names the rollout with `target`, an import path `module:function`, read with the
spec's own folder first on the import path. The axes are the conditions; `[declare]` lists the
outcomes and says which count against the agent (`failures`) and which for it (`successes`), so
a rise reads as worse or safer. Every key is on [The sweep spec](sweep-spec.md).

<!-- docs-check: file support.toml -->
```toml
target = "my_rollout:rollout"
target_id = "support-bot"
t_unit = "steps"
replicates = 200

[axes.ticket]
type = "categorical"
values = ["refund", "password", "shipping"]

[axes.temperature]
type = "continuous"
values = [0.0, 0.7]

[declare]
outcomes = ["resolved", "unresolved", "timeout"]
failures = ["unresolved", "timeout"]
successes = ["resolved"]
```

`--dry-run` checks all of it and runs nothing: it reads the spec, imports the rollout in a process
of its own with the network blocked, checks it takes `(cfg, seed)` without calling it, and prints
the plan with the smallest change the design could detect:

<!-- docs-check: run -->
```console
$ poisson-prove sweep support.toml --dry-run
plan  1,200 rollouts of support-bot: 6 cells x 200 replicates on local, $0 (local)
  target  my_rollout:rollout (imports, takes cfg and seed)
  outcomes  failures: timeout, unresolved; successes: resolved
…
```

Run it, change the agent (here, its prompt), and run it again on the same seeds:

<!-- docs-check: run -->
```console
$ poisson-prove sweep support.toml --yes
plan  1,200 rollouts of support-bot: 6 cells x 200 replicates on local, $0 (local)
…
done  1,200 rollouts in run "support-bot 2026-10-26 a" (complete) in … s
```

<!-- docs-check: file prompts.py -->
```python
SYSTEM = "Answer the customer's ticket step by step. Ask before refunding."
```

<!-- docs-check: run -->
```console
$ poisson-prove sweep support.toml --yes --pair-with latest
plan  1,200 rollouts of support-bot: 6 cells x 200 replicates on local, $0 (local)
…
done  1,200 rollouts in run "support-bot 2026-10-26 b" (complete) in … s, paired with "support-bot 2026-10-26 a"
…
  next: poisson-prove diff
$ poisson-prove diff
safer  unresolved: … safer, … worse · timeout: … safer, … worse (paired test on shared seeds); …
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  before  support-bot 2026-10-26 a
  after  support-bot 2026-10-26 b
…
```

`safer`: the new prompt left fewer tickets unresolved, and no condition got worse. To stop a build
on a change for the worse instead, `check` exits 4 when it fails; see [In CI](recipes/in-ci.md).

## One case per condition

Each case is its own sweep axis. Put the cases on one axis (here `ticket`), have the rollout pick
its case from `cfg`, never from `seed`, and return the case's id as `meta={"case_id": ...}`. A
condition then runs exactly one case, and its replicates are repeats of that case.

A rollout that picks its case from the seed runs several cases inside one condition. Its rate
mixes easy and hard cases in whatever proportion the seeds fell, and a change in that mix reads as
a change in the agent. Prove reads the `case_id` each episode recorded and refuses to compare such
a condition. Here is that mistake, in a store of its own:

<!-- docs-check: file mixed_rollout.py -->
```python
from poisson_prove import Episode
from support_bot import TICKETS, handle


def rollout(cfg, seed):
    name = sorted(TICKETS)[seed % len(TICKETS)]  # the case picked from the seed: wrong
    reply = handle(TICKETS[name], temperature=cfg["temperature"], seed=seed)
    outcome = "timeout" if reply.timed_out else "resolved" if reply.resolved else "unresolved"
    return Episode(outcome=outcome, t=reply.steps, horizon=20, meta={"case_id": name})
```

<!-- docs-check: file mixed.toml -->
```toml
target = "mixed_rollout:rollout"
target_id = "support-bot"
t_unit = "steps"
replicates = 200

[axes.temperature]
type = "continuous"
values = [0.0, 0.7]

[declare]
outcomes = ["resolved", "unresolved", "timeout"]
failures = ["unresolved", "timeout"]
successes = ["resolved"]
```

<!-- docs-check: run -->
```console
$ poisson-prove --store mixed-runs sweep mixed.toml --yes
plan  400 rollouts of support-bot: 2 cells x 200 replicates on local, $0 (local)
…
$ poisson-prove --store mixed-runs sweep mixed.toml --yes --pair-with latest
plan  400 rollouts of support-bot: 2 cells x 200 replicates on local, $0 (local)
…
$ poisson-prove --store mixed-runs diff  # exits 1
error: condition temperature 0.0 ran 3 cases (password, refund, shipping); each case must be its own sweep axis
  next: make each case its own sweep axis in the spec, an [axes.<name>] table whose values are the cases, then sweep again
…
```

Nothing is compared and nothing is written. Episodes that record no `case_id` are not counted, so
a rollout with one case per condition and no ids is compared as before; recording the id is what
lets Prove catch the mistake.

## A traced agent: `[capture]`

An agent instrumented with OpenTelemetry can have its spans stored with each episode, so `inspect`
and the reports can show where a failed episode went. Install the `agent` extra and the
instrumentor for your client, and name the instrumentor in a `[capture]` table:

<!-- docs-check: skip: needs an OpenTelemetry instrumentor installed -->
```bash
pip install "poisson-prove[agent]" opentelemetry-instrumentation-openai-v2
```

<!-- docs-check: run -->
```toml
[capture]
instrument = ["openai"]
content = false
max_observation_bytes = 16384
```

`instrument` lists instrumentors by the name they register under OpenTelemetry's
`opentelemetry_instrumentor` entry points; only those are switched on. `content = false` (the
default) keeps prompts and completions out of the store; `max_observation_bytes` has no default
and bounds each stored value. An instrumentor that is not installed is not refused: the plan's
`capture` line and the `done` line name it, the run goes on without its spans and the manifest
records why, so check that `inspect` shows spans after a first small sweep. [What capture stores](what-capture-stores.md) says exactly what is kept. A rollout can also record its own steps with `poisson_prove.record` and
`poisson_prove.step`, with no OpenTelemetry at all; see [Traces](concepts/traces.md).

## What Prove does with your code

It imports the module `target` names and calls the function. It never edits your code and reads
no key: your agent reads its own keys, as it does today. What it writes is the store
(`./prove-runs` or the one you name) and two files of its own under `~/.cache/poisson-prove/`:
`compared.jsonl`, the comparisons it has printed (so a run resumed after one was read carries a
note), and `errors.log`, the details of any unexpected failure. Only the tables you add
change what happens around a call: `[capture]` switches on the instrumentors you name, and
`[chaos]` injects the faults you name into your client's HTTP calls
([Fault injection](fault-injection.md)). On the local backend each call runs in Prove's own
process, one after another; with `--episode-timeout` each runs in a child process, and one that
runs past the limit is stopped and stored with no outcome, as an error of kind `episode_timeout`. The
other backends are on [Backends](backends.md).
