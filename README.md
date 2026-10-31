# Poisson Prove

[![CI](https://img.shields.io/github/actions/workflow/status/poisson-labs/prove/ci.yml?branch=main&event=push&style=flat-square&label=CI)](https://github.com/poisson-labs/prove/actions/workflows/ci.yml?query=branch%3Amain+event%3Apush) [![PyPI version](https://img.shields.io/pypi/v/poisson-prove?style=flat-square&color=3B5BDB)](https://pypi.org/project/poisson-prove/) [![Python versions](https://img.shields.io/pypi/pyversions/poisson-prove?style=flat-square&color=3B5BDB)](https://pypi.org/project/poisson-prove/) [![Licence: MIT](https://img.shields.io/pypi/l/poisson-prove?style=flat-square&color=3B5BDB)](https://github.com/poisson-labs/prove/blob/main/LICENSE)

Did your change to the agent really change how often it fails?

![The terminal app as it opens, drawn in a terminal: the poisson labs prove banner between the header and the keys enter home, ? help and q quit](https://raw.githubusercontent.com/poisson-labs/prove/main/docs/images/opening-screen.png)

Prove replays the same cases before and after a change, on the same seeds, and tells you per condition whether failures went up, went down, or did not move by more than it could have detected, with stated error bounds and detection limits. Every verdict comes with the smallest change that condition could have shown.

<!-- docs-check: run -->

    python3 -m venv .venv && source .venv/bin/activate
    pip install poisson-prove
    poisson-prove init --example
    poisson-prove sweep --yes
    poisson-prove sweep --yes --target poisson_prove.examples.mock_agent:rollout_patched --pair-with latest
    poisson-prove diff

- No key and no account for the example; your own agent runs on your machine by default.
- Prove sends nothing anywhere: no telemetry, no update check; `serve` binds to 127.0.0.1 only.
- Python 3.11 to 3.14 on macOS and Linux. MIT licensed.

For your own agent you write one function that runs one case and says how it ended: see
[Your own agent](https://github.com/poisson-labs/prove/blob/main/docs/your-own-agent.md).
`uv tool install poisson-prove` or `pipx install poisson-prove` installs the command alone: enough
for the example, not for importing your agent.

## What the first run showed

The example sweeps a small mock agent over three tasks and three tool failure rates, 194 episodes
in each of the nine conditions, then sweeps a patched version of it (it retries a failed tool call
once) on the same seeds. `diff` compares the two runs:

<!-- docs-check: run -->
```console
$ poisson-prove diff
trade  timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds); …
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  before  mock-agent 2026-10-26 a
  after  mock-agent 2026-10-26 b
…
  next: poisson-prove report --x task_id --y tool_fail_rate
```

Read the first line word by word. `trade` is the verdict: some conditions got safer and at least
one got worse. Then, per outcome, how many conditions were flagged as falling (safer) and rising
(worse); the clause after the test names the changes that also hold at the stricter level the word
is decided at, where they differ from the flags.
`violated` (the agent took a forbidden fallback) falls in most conditions and rises in none;
`timeout` (the agent ran out of its 20 tool calls) falls in some and rises in the hardest one. The
patch trades one failure for another: retrying keeps the agent off the forbidden path, and where
tools fail most the retries use up its budget. "Paired test on shared seeds" says the two runs drew
the same random numbers, so each episode is compared with its twin. The counts move a little from
one pair of sweeps to the next, since each pair draws fresh seeds; the verdict did not, in our runs.

The lines under it name the method and the two runs; the full output goes on, with every
condition's change, an interval on it and the smallest change it could have detected. The `next:`
line is the command to run next, whole.

## Let your coding agent set it up

<!-- docs-check: run -->
```console
$ poisson-prove init --agent
ok  wrote the setup for your coding agent (4 files)
…
  prompt  Use the poisson-prove-setup skill in this repository: set Poisson Prove up for me to review, then stop.
  next: give your coding agent the prompt above, then review what it wrote
```

This writes a skill your coding agent (Claude Code, Codex, Cursor) follows. Give it the prompt: it
reads your code, writes `prove_rollout.py` and `prove.toml`, checks them with
`poisson-prove sweep --dry-run`, and stops for you to review. Prove makes no model call and reads no
key. When the files look right, run `poisson-prove sweep` yourself. The whole procedure is in
[Set Prove up with your coding agent](https://github.com/poisson-labs/prove/blob/main/docs/setup-with-your-agent.md).

## The terminal app and the dashboard

On a terminal, `poisson-prove` with no verb opens the terminal app: your runs, your comparisons and
their verdicts, a sweep from the folder's `prove.toml`, all by keys. `poisson-prove ui` builds a
dashboard of the same views as pages you open from disk:

<!-- docs-check: run -->
```console
$ poisson-prove ui
ok  dashboard at file:///…/prove-runs/.poisson/ui/index.html
```

See [The terminal app](https://github.com/poisson-labs/prove/blob/main/docs/terminal-app.md) and
[The dashboard](https://github.com/poisson-labs/prove/blob/main/docs/dashboard.md).

## Your own agent

A rollout is a function `(cfg, seed) -> Episode`: it runs one case of your agent under the
condition `cfg` names, with randomness seeded from `seed`, and says how the case ended. This one
wraps a support bot:

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

The sweep spec names it with `target`, lists the conditions as axes (each case its own axis value,
so a condition runs one case) and says which outcomes count against the agent:

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

An agent traced with OpenTelemetry can have its spans stored with each episode by adding a
`[capture]` table (it needs `pip install "poisson-prove[agent]"` and the instrumentor you name):

<!-- docs-check: run -->
```toml
[capture]
instrument = ["openai"]
content = false
max_observation_bytes = 16384
```

[Your own agent](https://github.com/poisson-labs/prove/blob/main/docs/your-own-agent.md) runs this
example end to end and says what each piece does.

## Recipes

- [First look](https://github.com/poisson-labs/prove/blob/main/docs/recipes/first-look.md): the example, and how to read every block of `diff`.
- [A prompt change](https://github.com/poisson-labs/prove/blob/main/docs/recipes/a-prompt-change.md): before and after a change to your prompt, paired, with a gate.
- [A model change, with its cost](https://github.com/poisson-labs/prove/blob/main/docs/recipes/a-model-change-with-cost.md): a cheaper model as an axis, and what it saves.
- [In CI](https://github.com/poisson-labs/prove/blob/main/docs/recipes/in-ci.md): `check` as a step that fails the build.
- [When it says too small to tell](https://github.com/poisson-labs/prove/blob/main/docs/recipes/when-it-says-too-small-to-tell.md): what to change so it can tell.
- [Paired replay](https://github.com/poisson-labs/prove/blob/main/docs/recipes/paired-replay.md): does the same request, sent twice, get the same decision?

## Commands

- `init`: write `prove.toml`, the keyless example, or the setup for your coding agent ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/init.md)).
- `sweep`: show the plan, then run every condition of the spec ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/sweep.md)).
- `diff`: compare two runs condition by condition ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/diff.md)).
- `check`: the same comparison as a gate that exits 4 when it fails ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/check.md)).
- `report`: write a report folder with a heatmap and a receipt ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/report.md)).
- `paired`: check that two arms replayed the same requests, then analyse them ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/paired.md)).
- `serve`: one comparison as a page on a loopback port ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/serve.md)).
- `inspect`: the episodes behind an outcome, with code to reproduce one ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/inspect.md)).
- `runs`: the runs in the store ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/runs.md)).
- `ui`: build the dashboard ([page](https://github.com/poisson-labs/prove/blob/main/docs/commands/ui.md)).

## What the numbers claim, and what they do not

Each condition's change is tested on its own, and the flags are held to a false discovery rate
(Benjamini-Hochberg, q 0.05 by default); the verdict word counts only the changes that also hold
at the family-wise level (Holm). Every condition that did not move says how large a change it would
have caught 4 times in 5. `no significant change` means no change counted and every condition could
have caught one of the size you accepted; `too small to tell` means at least one could not. Before
a sweep runs, the plan refuses a design too small to detect the change you accept.

What Prove does not claim: that the change caused anything (it compares two runs), anything about
conditions you did not sweep, or that an outcome label means what you meant by it. It is not a
benchmark, an agent framework or an observability tool, and it never edits your code. [What the statistics claim](https://github.com/poisson-labs/prove/blob/main/docs/concepts/what-the-statistics-claim.md)
says it in full, and [Defining outcomes](https://github.com/poisson-labs/prove/blob/main/docs/defining-outcomes.md)
says how to choose labels that measure your agent and not your provider. The serve page and the
traces have pages of their own:
[Reading a serve page](https://github.com/poisson-labs/prove/blob/main/docs/reading-a-serve-page.md) and
[What capture stores](https://github.com/poisson-labs/prove/blob/main/docs/what-capture-stores.md).

## Where Prove sits beside Trace and Tasks

Tasks makes the cases; Prove says whether a change moved the failure rate, and by how much it
could have; Trace says where in a run it failed, and whether that moved. Prove installs alone and
calls neither; Trace reads Prove's store. See
[Prove with Trace and Tasks](https://github.com/poisson-labs/prove/blob/main/docs/with-trace-and-tasks.md).

## Backends

Sweeps run on your machine by default. `--backend modal` runs them in parallel Modal containers on
your own account (`pip install "poisson-prove[modal]"`), with a cost estimate in the plan.
`--backend burla` runs them on your own Burla cluster (`pip install "poisson-prove[burla]"`); it is
experimental. Your rollout's code and conditions go to the account you choose, and the rows come
back to the same local store. See [Backends](https://github.com/poisson-labs/prove/blob/main/docs/backends.md).

Prove never phones home. No telemetry, no analytics, no update checks. `poisson-prove serve` binds a
loopback listener on request and makes no outbound connection: it holds one page built from data
already on the machine, and dies with the process.

## Python

The comparisons, the store and the statistics are importable; `compare.diff` returns the result
`diff` prints:

<!-- docs-check: run -->
```python
from poisson_prove import compare

for run in compare.runs("prove-runs"):
    print(run.run_name, run.run_id)
```

See [Python API](https://github.com/poisson-labs/prove/blob/main/docs/python.md).

## Development

[CONTRIBUTING.md](https://github.com/poisson-labs/prove/blob/main/CONTRIBUTING.md) says how to
install a checkout, run the two test suites and send a change.

## Licence

MIT. See [LICENSE](https://github.com/poisson-labs/prove/blob/main/LICENSE) and
[NOTICE](https://github.com/poisson-labs/prove/blob/main/NOTICE) for what Prove includes from others.

## Citation

<!-- docs-check: skip: a citation to copy, not a command -->
```bibtex
@software{poisson_prove,
  title  = {Poisson Prove},
  author = {{Poisson Labs}},
  year   = {2026},
  url    = {https://github.com/poisson-labs/prove}
}
```
