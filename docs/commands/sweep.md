# `poisson-prove sweep`

Runs every condition of a sweep spec, a number of replicates each, and stores every episode as a
run. It prints the plan first: what will run, where, what Prove prices of it and what it does
not, and the smallest change in a condition's failure rate the design can catch. A design too small for the change you accept is
refused before anything runs. On a terminal it then asks `[y/N]`; piped or in CI it needs
`--yes`.

A sweep that is not paired with an earlier one is planned twice over: as it stands, and as the
first half of the pair that `--pair-with` makes of it later. The plan gives both readings and
passes only when both do, so the sweep you pair with it, on the same spec and replicates, is
never refused for its size. Both readings are planned for the worst base rate and with no credit
for pairing, so the plan needs no pilot run: nothing is estimated from earlier data.

The plan prices the compute a backend bills, which is nothing on this machine, and your agent's
own calls only when the spec declares what a rollout costs under `[cost]`; with nothing declared
it says they are not priced ([What the plan prices](#what-the-plan-prices) below).

Where the rollouts run is the spec's to say: this machine, Modal or your own cloud account.
`poisson-prove where` shows and changes it, and `--backend` overrides it for one run.

With `--try` it runs no sweep: it calls the rollout once, for real, on this machine, says how the
call ended and stores nothing. That is the way to find a rollout that fails on every call before a
sweep spends anything on it ([The trial call](#the-trial-call---try) below).

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove sweep --help
usage: poisson-prove sweep [-h] [--target pkg.module:rollout] [--replicates N]
                           [--backend {local,modal,cloud}]
                           [--salt HEX | --pair-with RUN | --resume [RUN]]
                           [--name TEXT] [--note TEXT] [--episode-timeout S]
                           [--max-rollouts N] [--batch-size N]
                           [--max-mde FRACTION] [--dry-run] [--try] [--yes]
                           [--json] [--concurrency N] [--infra-retries N]
                           [--max-cost USD] [--est-seconds S]
                           [--app-name NAME] [--image SECTION] [--store PATH]
                           [--plain] [--debug]
                           [SPEC.toml]

Run every condition of a sweep spec, N replicates each, on the local machine or a
remote backend. The plan is printed first, with its cost estimate, and the sweep
starts only after a yes. With --try, call the rollout once instead, on this
machine, and say how it ended; nothing is stored.

positional arguments:
  SPEC.toml             the sweep spec: the target, the axes, the replicates
                        (default: ./prove.toml)

options:
  -h, --help            show this help message and exit
  --target pkg.module:rollout
                        import path of the rollout function; wins over the
                        spec's target (default: the spec's target)
  --replicates N        replicates per condition for this run, recorded in its
                        manifest (default: the spec's replicates)
  --backend {local,modal,cloud}
                        where the rollouts run: local (this machine), modal,
                        or cloud (your own cloud account; Prove starts the
                        cluster and stops it after) (default: where the spec
                        says, see the where verb; local when it says nothing)
  --salt HEX            the run salt seeds are derived from (default: a fresh
                        one)
  --pair-with RUN       inherit that run's salt, so the two runs share their
                        seeds (default: none)
  --resume [RUN]        continue that partial run where it stopped; alone, the
                        latest partial run; written after SPEC.toml when a
                        spec is given, so the spec is not read as the run
                        (default: none)
  --name TEXT           the name the new run goes by (default: computed)
  --note TEXT           what changed for this run, one line of at most 200
                        characters, shown beside it wherever a comparison
                        shows it (default: none)
  --episode-timeout S   seconds an episode may take before it is recorded as
                        timed out (default: no limit; with --try, 300)
  --max-rollouts N      stop after N rollouts and leave the run partial
                        (default: run them all)
  --batch-size N        rows written to the store at a time (default: 64)
  --max-mde FRACTION    the largest minimum detectable effect you accept for
                        this design (default: 0.200)
  --dry-run             print the plan and stop; nothing is run or written
  --try                 call the rollout once, for real, on this machine, on
                        the spec's first condition, and say how it ended;
                        nothing is stored (default: run the sweep)
  --yes                 skip the question after the plan, or with --try the
                        question before the call
  --json                print the plan and the result as one JSON document
                        instead of text
  --store PATH          the store folder (default: $POISSON_PROVE_STORE when
                        set, else ./prove-runs)
  --plain               print plain text, as a pipe gets it, on a terminal too
                        (default: pretty on a terminal, plain otherwise)
  --debug               also print the traceback of an unexpected failure

remote backends (override the [modal] table; --infra-retries, --max-cost and --est-seconds also override [cloud]; --max-cost holds a sweep on this machine too):
  --concurrency N       containers at once (default: the table's)
  --infra-retries N     retries per batch (default: the table's)
  --max-cost USD        refuse before anything starts when what the plan
                        priced is above this: the compute estimate, and your
                        agent's own calls when [cost] declares them (default:
                        no cap)
  --est-seconds S       seconds per episode, for the estimate (default: the
                        table's)
  --app-name NAME       the Modal app name (default: the table's)
  --image SECTION       the [modal.SECTION] image table to build from
                        (default: image)

examples:
  poisson-prove sweep
  poisson-prove sweep --try
  poisson-prove sweep --target my_agent:rollout_patched --pair-with latest --yes
  poisson-prove sweep other.toml --target my_agent:rollout --replicates 300
```

## Options

- `SPEC.toml` is the sweep spec, `./prove.toml` when none is named. [The sweep spec](../sweep-spec.md)
  has every key.
- `--target pkg.module:rollout` runs another rollout than the spec's `target`: the usual way to
  sweep a changed agent against the same spec.
- `--replicates N` overrides the spec's replicates for this run; the manifest records what ran.
- `--backend` chooses where the rollouts run for this run: `local` (this machine), `modal` or
  `cloud` (your own cloud account; Prove starts the cluster and stops it after). Without it the
  sweep runs where the spec says: a `[cloud]` table means your cloud account, a `[modal]` table
  Modal, neither this machine. [`poisson-prove where`](where.md) writes that table. A spec holding
  both tables is refused unless `--backend` is given. See [Backends](../backends.md).
- `--salt HEX` sets the run salt every seed is derived from; two runs with one salt share their
  seeds. `--pair-with RUN` takes another run's salt, which is how you pair a run with an earlier
  one: `--pair-with latest`. `--resume [RUN]` continues a partial run where it stopped; alone, the
  latest partial run. Only one of the three may be given.
- `--name TEXT` names the run. Without it the run is named by its target, the date and a letter,
  such as `mock-agent 2026-10-26 a`; every verb accepts the name in place of the run's id.
- `--note TEXT` records what changed for this run, such as `--note "retry each tool call once"`,
  in the run's manifest. `diff`, `check` and `report` show each run's note under that run, and
  `runs`, `inspect`, the dashboard and the terminal app show it with the run. A note is one line
  of 1 to 200 characters once the spaces at its ends are trimmed, with no tab or other control
  character; one that is not is refused before anything is written. A note may begin with a dash,
  written `--note=-TEXT`. A resume keeps the note the run was opened with, and `--resume` with
  `--note` is refused.
- `--episode-timeout S` stops an episode that runs longer than `S` seconds and stores it with no
  outcome, as an error of kind `episode_timeout`; `--event episode_timeout` reaches those episodes
  (as `--event timeout` does in a run whose agent has no `timeout` outcome of its own). On the local
  backend each episode then runs in a child process that can be stopped. With `--try` it is how
  long the one call may take, 300 s when it is not given.
- `--max-rollouts N` stops after `N` rollouts and leaves the run partial, to resume later.
- `--batch-size N` is how many rows are written to the store at a time; a stopped run keeps every
  whole batch.
- `--max-mde FRACTION` is the largest smallest-detectable-change you accept, 0.200 by default: the
  plan refuses a design whose worst condition could not catch a change that size 4 times in 5,
  in this sweep or, for a sweep paired with nothing, in the sweep paired with it afterwards.
- `--dry-run` prints the plan and stops. It checks the spec, imports the rollout in a process of
  its own with the network blocked, and checks it takes `(cfg, seed)`, without calling it.
- `--try` calls the rollout once, for real, on this machine, on the spec's first condition, and
  says how the call ended. It stores nothing. See [The trial call](#the-trial-call---try).
- `--yes` skips the question after the plan, and with `--try` the question before the call.
- `--json` prints the plan and the result as one JSON document on stdout, and nothing else
  there: what the target writes to stdout goes to stderr (see "What the target prints, with
  `--json`" below).
- `--concurrency N`, `--infra-retries N`, `--max-cost USD`, `--est-seconds S`, `--app-name NAME`
  and `--image SECTION` override the `[modal]` table for one run; `--infra-retries`, `--max-cost`
  and `--est-seconds` also override `[cloud]`.
- `--max-cost USD` holds everything the plan priced, on every backend, and refuses a sweep whose
  estimate is above it before anything starts. On this machine that is your agent's own calls as
  `[cost]` declares them, so a spec with no `[cost]` gives it nothing to hold and is refused. On
  Modal and a cloud account it holds the compute estimate plus the declared calls (and, on a
  cloud account, the ledger so far); with no `[cost]` it holds compute alone, and the cost line
  says `compute only` beside the cap. See [What the plan prices](#what-the-plan-prices).
- `--store PATH` is the store folder, `./prove-runs` unless `$POISSON_PROVE_STORE` says otherwise;
  `--plain` prints plain text on a terminal too; `--debug` adds the traceback of an unexpected
  failure.

## Examples

`--dry-run` shows the plan and runs nothing:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --dry-run
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0
  target  poisson_prove.examples.mock_agent:rollout (imports, takes cfg and seed)
  outcomes  failures: timeout, violated
…
  smallest rise one condition alone would be flagged for  0.199 at its worst base rate, 0.400 (Fisher, q 0.05 over 18 tests, 4 times in 5; you accept up to 0.200)
  and in a sweep paired with this one  0.200 at its worst base rate, 0.400 (paired test on shared seeds, McNemar, q 0.05 over 18 tests, 4 times in 5; planned for the worst base rate and with no credit for pairing, so it needs no pilot run)
```

The first of the two lines reads this sweep beside another one on separate seeds (Fisher's test);
the second reads it beside the sweep you will pair with it on the same seeds (the paired test).
The paired reading counts on no agreement between the two runs of a pair, so a pair that agrees
more than chance, as runs on shared seeds usually do, can only catch more than the plan says.

The example's plan reads `$0` because its spec declares that a rollout costs nothing
(`usd_per_rollout = 0` under `[cost]`): the mock agent calls no model. That declaration is the
only way a plan reads `$0`.

Twenty replicates per condition are too few to catch a change of 0.20, so the plan is refused,
naming the reading that failed (the paired one when both do), with the two ways out: the fewest
replicates that pass both readings, or the smallest larger change that admits both:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --replicates 20 --dry-run  # exits 1
plan  180 rollouts of mock-agent: 9 cells x 20 replicates on local, $0
…
error: underpowered design: a sweep paired with this one would flag a change of 0.568 at its worst base rate, 0.000, and you accept 0.200
  next: poisson-prove sweep --replicates 194 --dry-run
  next: poisson-prove sweep --replicates 20 --dry-run --max-mde 0.662
```

A paired sweep is read with the paired test alone, its pairs the smaller of the two runs'
replicates. When the earlier run is the short one, more replicates of the new sweep cannot help,
and the refusal says so. Here the baseline was swept at 100 replicates under a larger accepted
change, and the sweep paired with it asks for the default 0.20:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --yes --replicates 100 --max-mde 0.3 --name short-baseline
plan  900 rollouts of mock-agent: 9 cells x 100 replicates on local, $0
…
done  900 rollouts in run "short-baseline" (complete) in … s
…
$ poisson-prove sweep --pair-with short-baseline --dry-run  # exits 1
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0
…
error: underpowered design: run "short-baseline" has 100 replicates, and a sweep paired with it needs 194 on both sides; sweep a new baseline at 194, then your change with --pair-with latest --replicates 194
  next: poisson-prove sweep --dry-run --replicates 194
  next: poisson-prove sweep --pair-with short-baseline --dry-run --max-mde 0.281
```

The first way out is a new baseline at the size that passes, typed with no `--pair-with`; sweep
it, then sweep your change paired with it. The second keeps the pair as it stands and accepts
the larger change it can catch. Neither is refused for its size when typed.

A sweep stopped short keeps what it ran, exits 3 and says how to go on:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --yes --max-rollouts 100 --name stopped-early  # exits 3
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0
…
stopped  100 of 1,746 rollouts kept in run "stopped-early" (partial) in … s
…
  next: poisson-prove sweep --resume
$ poisson-prove sweep --resume --yes
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0
…
  Resuming "stopped-early": 100 stored, 1,646 to run
…
done  1,746 rollouts in run "stopped-early" (complete) in … s
```

A complete sweep of your own agent that is paired with nothing ends by saying what comes next:
change your agent, then sweep it again on the same seeds. Its `next:` is that second sweep,
paired with this one by the run's name, on the spec, `--target`, `--replicates`, `--max-mde` and
`--store` you typed. Here on the demo agent `init --demo --with-setup` writes:

<!-- docs-check: run -->
```console
$ poisson-prove init --demo --with-setup --repo support-bot
ok  wrote the demo agent, a support bot that needs no key (5 files)
…
$ cd support-bot
$ poisson-prove sweep --yes
plan  1,164 rollouts of support-bot: 6 cells x 194 replicates on local, $0
…
done  1,164 rollouts in run "support-bot 2026-11-18 a" (complete) in … s
…
  then  change your agent; the next sweep runs it on the same seeds
  next: poisson-prove sweep --pair-with "support-bot 2026-11-18 a"
$ cd ..
```

A sweep paired with an earlier one still ends with `next: poisson-prove diff`, and a sweep of the
packaged example with the sweep of its patched twin, as in the quickstart. A sweep that
`--resume` finishes ends as it would have had it not stopped.

A spec that holds both a `[modal]` and a `[cloud]` table does not say where it runs. Swept with
no `--backend` it is refused, in one line that names both tables and what keeps one:

<!-- docs-check: run -->
```bash
poisson-prove init --example --out both.toml
printf '\n[modal]\n\n[cloud]\nprovider = "aws"\n' >> both.toml
```

<!-- docs-check: run -->
```console
$ poisson-prove sweep both.toml --dry-run  # exits 1
error: both.toml holds both [cloud] and [modal], so it does not say where its sweeps run; give --backend, or keep one table with poisson-prove where --spec both.toml cloud, modal or local
```

On your own cloud account (here after `poisson-prove where cloud` wrote the spec's `[cloud]`
table), the sweep starts the cluster, runs, and stops the cluster before it prints the result.
The cluster's four lines go to stderr with the progress; the result's `cluster` line says what
ran, for how long, when it stopped and what the ledger was charged:

<!-- docs-check: skip: needs your own AWS account -->
```console
$ poisson-prove sweep --yes
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on your AWS account, ~$0.45 this run (4 × m7i.2xlarge at $0.4687/node-hour, Prove's AWS prices for us-east-2 of 2026-11-06, each node's disk priced at 52 GB) · ledger cloud-ledger.jsonl $0 so far · stop $2.00 · cap $3.00 · your agent's own calls: $0 (prove.toml declares that a rollout costs nothing)
…
starting  4 × m7i.2xlarge in us-east-2  0 of 4 ready · 35 s
ready  4 nodes · 32 vCPU · 1 min 12 s
stopping  the cluster
stopped  4 nodes, up 2 min 3 s
done  1,746 rollouts in run "mock-agent 2026-11-11 a" (complete) in 48.6 s
…
  cluster  4 × m7i.2xlarge up 2 min 3 s, stopped 23:00:45Z · ledger $0.38
…
```

The times and the charge are an example: nodes take about a minute to be ready. On a terminal the
`starting` line is one live line that counts the nodes as they come up; piped, it is printed once.
The ledger's charge counts the boot and the idle allowance on top of the time the nodes were up,
so it is an upper bound on what the cloud bills. [Backends](../backends.md#your-cloud-account)
says what Prove starts and stops, and what happens if this machine stops first.

The plan as JSON, for a script:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --dry-run --json
{
  "schema": "poisson-prove.sweep/1",
  "verdict": "plan",
  "sentence": "1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0",
  "plan": {"rollouts": 1746, "cells": 9, "replicates": 194, "backend": "local"},
  "cost": {"compute_usd": 0.0, "agent_usd_per_rollout": 0.0, "agent_usd": 0.0, "agent_basis": null, "total_usd": 0.0, "cap_usd": null},
  "design_mde": {"mde": 0.1991, "base_rate": 0.4, "direction": "rise", "test": "fisher"},
  "design_paired": {"mde": 0.1998, "base_rate": 0.4, "direction": "rise", "test": "mcnemar"}
  …
}
```

The `cost` object says what the plan priced, in dollars: `compute_usd`, the backend's estimate
(0 on this machine, null on Modal when there is no estimate); `agent_usd_per_rollout`, `agent_usd`
and `agent_basis`, the figure `[cost]` declares, that figure times the rollouts this command will
run, and the declaration's `basis` (each null when nothing is declared); `total_usd`, the two
parts together, a number only when both are; and `cap_usd`, the cap that holds them, or null.
`plan.cost` stays the cost line's own words, as text.

## What the plan prices

Prove prices two things, and says which it did.

**The compute a backend bills.** This machine adds nothing. Modal's and a cloud account's
estimates are in [Backends](../backends.md).

**Your agent's own calls**, at its own providers: the model calls and anything else a rollout
pays for. Prove cannot see these and holds no price of any model, so it prices them only by a
figure you declare. With nothing declared the plan says so, and on this machine it gives no
dollar figure at all:

<!-- docs-check: file unpriced.toml -->
```toml
target = "poisson_prove.examples.mock_agent:rollout"
target_id = "airline-triage-agent"
t_unit = "tool_calls"
replicates = 194

[axes.task_id]
type = "categorical"
values = ["search", "checkout", "refund"]

[declare]
failures = ["timeout", "violated"]
```

<!-- docs-check: run -->
```console
$ poisson-prove sweep unpriced.toml --dry-run
plan  582 rollouts of airline-triage-agent: 3 cells x 194 replicates on local, your agent's own calls not priced
…
  Cost: your agent's own calls are not priced (unpriced.toml declares no [cost]); this machine adds nothing
…
```

The line is the same for every agent whose spec has no `[cost]`, one that calls no model among
them: Prove does not guess which kind of agent it has. To have the plan price your agent's calls,
declare what one rollout costs, as you measured or reckon it, in a `[cost]` table
([The sweep spec](../sweep-spec.md#cost)):

<!-- docs-check: file priced.toml -->
```toml
target = "poisson_prove.examples.mock_agent:rollout"
target_id = "airline-triage-agent"
t_unit = "tool_calls"
replicates = 194

[axes.task_id]
type = "categorical"
values = ["search", "checkout", "refund"]

[declare]
failures = ["timeout", "violated"]

[cost]
usd_per_rollout = 0.0016
basis = "costliest conversation measured on Haiku 5.5, 2026-11-21"
```

The plan multiplies the figure by the rollouts this command will run (those left, on `--resume`;
`--replicates` and `--max-rollouts` as typed), and says whose figure it is, the rate as the spec
writes it:

<!-- docs-check: run -->
```console
$ poisson-prove sweep priced.toml --dry-run
plan  582 rollouts of airline-triage-agent: 3 cells x 194 replicates on local, ~$0.93 of your agent's own calls
…
  Cost: ~$0.93 of your agent's own calls (582 rollouts at $0.0016 each, declared in priced.toml: costliest conversation measured on Haiku 5.5, 2026-11-21); this machine adds nothing
…
```

`usd_per_rollout = 0` declares that a rollout costs nothing, and the plan then reads `$0` and
says it is declared. The spec `init --example` writes and the demo's declare it. A paired sweep
is priced as the first one is.

**`--max-cost` holds everything the plan priced**, on every backend. On this machine, with
`[cost]` declared, an estimate above the cap is refused before anything runs. The first `next:`
is the same sweep with the smallest cap that admits the estimate; the other way down is fewer
conditions, since the replicates are what the design needs:

<!-- docs-check: run -->
```console
$ poisson-prove sweep priced.toml --dry-run --max-cost 0.50  # exits 1
plan  582 rollouts of airline-triage-agent: 3 cells x 194 replicates on local, ~$0.93 of your agent's own calls
…
error: this sweep's estimate, ~$0.93 of your agent's own calls (582 rollouts at $0.0016 each, declared in priced.toml), is over --max-cost $0.50
  next: poisson-prove sweep priced.toml --dry-run --max-cost 0.94
  next: sweep fewer conditions: each one is 194 rollouts, ~$0.31 at the declared rate
```

An estimate at or under the cap passes, and the cost line then ends `· cap $0.94`. The other
cases:

| where | `[cost]` | what `--max-cost` holds |
|---|---|---|
| this machine | declared | your agent's declared calls |
| this machine | not declared | nothing, so the cap is refused: `--max-cost has nothing to hold on this machine` |
| Modal, a cloud account | declared | the compute estimate plus your agent's declared calls (on a cloud account, plus the ledger so far); the refusal names each part |
| Modal, a cloud account | not declared | the compute estimate alone, as before, and the cost line says `compute only` beside the cap |

A cloud account's `stop_cost` and its ledger stay compute only: Prove cannot see your agent's
spend as it happens.

## The trial call, `--try`

`poisson-prove sweep --try` calls the spec's rollout once, for real, and stores nothing. A
`--dry-run` imports the rollout and never calls it, so a rollout that fails on every call passes
it; one real call finds that before a sweep runs a thousand of them.

1. It reads and checks the spec as `--dry-run` does: the same refusals, with the same `error:`
   lines and exit codes, a design too small among them. Nothing is called when the check refuses.
2. It says what the call is, on a `try` line (the target, the spec's first condition, the first
   value of every axis as the spec writes them, the seed, and "on this machine") and a `cost`
   line, which follows what the spec declares under `[cost]`: with nothing declared, that the
   call spends your agent's own calls for one case; with a figure, that figure for the one
   rollout; with `usd_per_rollout = 0`, that it costs nothing. The seed comes from a fresh salt each time, unless `--salt` gives one.
3. On a terminal it asks `Call it? [y/N]` on stderr, and only `y` or `yes` makes the call; a no
   calls nothing, writes nothing and exits 0. Piped or in CI it needs `--yes`, and without it the
   command line is wrong: exit 2, with `--yes` on the `error:` line.
4. It makes the call in a process of its own, with the network allowed, since the call is your
   agent's real one. The call may take `--episode-timeout` seconds, 300 s when that is not given;
   a call that runs longer is ended, with everything it started.
5. It says how the call ended, and exits 0 for a call that returned an Episode the sweep could
   store, whatever its outcome: a declared failure is a good call too.

The call always runs on this machine. On a spec set to Modal or your cloud account it says so in
a `note:` line, and nothing of Modal's or the cluster's is checked, started or called, so your
agent's keys must be set on this machine for the trial.

<!-- docs-check: run -->
```console
$ poisson-prove sweep --try --yes
try  one call of poisson_prove.examples.mock_agent:rollout on task_id search · tool_fail_rate 0, seed 3783313349, on this machine
  cost  nothing: prove.toml declares that a rollout costs nothing; Prove stores nothing
ok  the rollout ran once and returned "completed" in 0.0 s
  condition  task_id search · tool_fail_rate 0
  seed  3783313349
  outcome  completed (declared neither a failure nor a success)
  t  8 of 20 tool_calls
  model calls  none in the trace this call returned
  next: poisson-prove sweep
```

The result's lines are the condition and the seed the call ran on, the outcome with the kind the
spec declares for it (a failure, a success or neither), `t` beside the horizon in the spec's
unit, what the call shows of its model calls, `case_id` when the Episode carries one in `meta`,
and `printed` when the rollout wrote to its stdout. Its `next:` is the sweep itself, on the spec, the target and the store you
typed.

**The model calls of the one call** are counted from the trace the rollout returned in
`meta["trace"]`, when it returned one ([Traces](../concepts/traces.md)). The mock agent's trace
holds tool steps and no model call, so its line says none. A rollout whose trace has `llm` spans
gets up to three lines after `t`:

<!-- docs-check: skip: the lines of a rollout that returns a trace with model calls, which the example's does not -->
```text
  model calls  7 in this call (the llm spans of the trace it returned)
  tokens  4,812 in, 391 out (recorded on 7 of 7 model calls)
  at a sweep's size  3,568 rollouts like this one would make about 24,976 model calls; other conditions can differ
```

`model calls` is the number of `llm` spans. `tokens` sums the tokens those spans carry, and says
on how many of them tokens were recorded; it is left out when none carries any. `at a sweep's
size` is the same count times the rollouts the sweep would run. When the call returned no trace
the one line is `model calls  not counted: this call returned no trace`, and when the trace is
one Prove cannot read it is `not counted` too; the call is still a good one. No line gives
dollars from tokens: Prove holds no price of a model, so the only dollar figure for your agent's
calls is the one `[cost]` declares. The trial does not apply a `[capture]` table, so an agent
whose calls are recorded only by capture is `not counted` here, and a sweep's stored traces hold
its calls. Nothing is stored to remember the count.

**What the rollout prints goes to stderr, never to stdout**, with `--json` or without, however it
is written: a `print` in the rollout or when the target is imported, a write to
`sys.stdout.buffer`, `os.write(1, ...)`, a program the rollout starts. It arrives as it is
written, each line once. The `printed` line counts the lines written to stdout (a last line with
no newline among them), not what the rollout wrote to its own stderr, which is passed on too.

**A call that does not end in an Episode the sweep could store** exits 1. Stdout keeps the `try`
lines and gains no `ok` line. Stderr gets one `error:` line, then for a raise the file and line it
was raised in (`raised in`), the line of the target's own module that called it when that is
another line (`called from`), and where the whole traceback was appended (`traceback`); then one
`next:` line, the trial again. A file under the spec's folder is shown by its path from there.
`--debug` prints the traceback too.

<!-- docs-check: file broken_rollout.py -->
```python
from poisson_prove import Episode


def rollout(cfg, seed):
    task = cfg["task"]  # the spec's axis is task_id: this raises on every call
    return Episode(outcome="success", t=1, horizon=20, meta={"case_id": task})
```

<!-- docs-check: run -->
```console
$ poisson-prove sweep --dry-run --target broken_rollout:rollout
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0
…
$ poisson-prove sweep --try --yes --target broken_rollout:rollout  # exits 1
try  one call of broken_rollout:rollout on task_id search · tool_fail_rate 0, seed 3849055552, on this machine
  cost  nothing: prove.toml declares that a rollout costs nothing; Prove stores nothing
error: the rollout raised KeyError: "task"
  raised in  broken_rollout.py:5
  traceback  ~/.cache/poisson-prove/errors.log
  next: poisson-prove sweep --try --target broken_rollout:rollout
```

The endings that exit 1, each with its `error:` line:

| the call | the `error:` line says |
|---|---|
| raised, in the rollout or while the target was imported | the exception's type and message, with the `raised in` and `called from` lines |
| ran past its limit | `the rollout ran past 300 s and was ended`, with the limit that applied |
| returned something that is not an Episode | the type it returned |
| returned an outcome `[declare]` does not list | the outcome, and the outcomes the table lists |
| returned an Episode whose `meta` cannot be stored as JSON | what could not be stored |
| ended its own process before it returned | the exit code |

With `--json`, a good call prints one `poisson-prove.sweep/1` document, verdict `ok`, with a `try`
object: `condition`, `seed`, `outcome`, `t`, `horizon`, `meta` (all of it: the packaged example's
also holds the steps it recorded, left out below), `seconds`, `printed` (the count of lines),
`model_calls` (the count of `llm` spans, or null when the call returned no trace Prove can read)
and `tokens` (`input`, `output` and `calls_with_tokens`, or null when no `llm` span carries
tokens).
A failed call leaves stdout empty, with the same exit code and the same lines on
stderr, as every refusal does.

<!-- docs-check: run -->
```console
$ poisson-prove sweep --try --yes --json
{
  "schema": "poisson-prove.sweep/1",
  "verdict": "ok",
  "sentence": "the rollout ran once and returned \"completed\" in 0.0 s",
  "try": {
    "condition": {"task_id": "search", "tool_fail_rate": 0.0},
    "seed": 4088004625,
    "outcome": "completed",
    "t": 8.0,
    "horizon": 20.0,
    "meta": {"task_id": "search"},
    "seconds": 0.0004,
    "printed": 0,
    "model_calls": 0,
    "tokens": null
  },
  "next": ["poisson-prove sweep"]
}
```

`--try` goes with the spec, `--target`, `--replicates`, `--max-mde`, `--salt`,
`--episode-timeout`, `--yes`, `--json` and `--store`. With `--dry-run`, `--resume` or
`--pair-with` it is a wrong command line (exit 2): the first contradicts it, and the other two
name a stored run for a call that stores nothing. The options that shape a stored run or a remote
sweep (`--name`, `--note`, `--max-rollouts`, `--batch-size` and the remote backends' own) are
read as a sweep reads them and change nothing about the one call. `--max-cost` holds a sweep's
estimate, so the one call is made whatever the cap is, and a `note:` line says so. It calls the rollout as it is,
with no `[capture]` recording and no `[chaos]` fault.

## What the target prints, with `--json`

With `--json`, stdout holds the one document and nothing else, whatever the target does.
Everything the target writes to stdout goes to stderr instead, once, as it is written: a `print`
in the rollout or at import, a write to `sys.stdout.buffer`, `os.write(1, ...)`, the C library, a
program the target starts, an `atexit` hook, and all of these under `--episode-timeout` too.
Nothing is dropped, and the exit code is the one the sweep would have had without `--json`.

For a caller, three things follow:

- Read both streams. A caller that pipes stdout and stderr and reads only stdout can hang on a
  target that prints a lot, because stderr's pipe fills: 200 kB a rollout is enough.
  `subprocess.run(capture_output=True)` reads both and does not hang.
- Look for the line that starts `error: `, not for stderr's first line, which can be the
  target's text. The target's lines sit among the progress lines, and text the target left
  without a newline at its end sits in front of whatever stderr gets next.
- The target sees stderr as its stdout. With stdout piped and stderr a terminal,
  `sys.stdout.isatty()` is true in the target, so a framework may draw there.

A target that calls `sys.exit`, at import or in a rollout, ends a `--json` sweep with exit 3 and
one `error: ` line that names the errors log, never with exit 0 and an empty stdout.

Without `--json` nothing moves in a sweep: the target's text stays on stdout, around Prove's own
lines. (`--try` is the exception: there the rollout's text goes to stderr either way.)
`--dry-run` shows nothing of what the import writes, with `--json` or without, because the check
is not a run. On Modal and on a cloud account, what a rollout writes stays with the worker, in
Modal's logs or the cluster's; what the target's import or the Modal client writes in the sweep's
own process goes to stderr as above.

## When the first batch has no outcome

A Modal or cloud sweep whose first batch has no outcome in any rollout stops there. Every rollout
of that batch raised, timed out, or failed for an infrastructure reason after its retries, so the
rest would only cost money to say the same. The first batch is the first to come back, of at
least 32 rows (or a whole batch, when batches are smaller). The sweep cancels what is in flight,
keeps every batch that already came back, stops the cluster on a cloud account, and leaves the run
partial. It prints `stopped  every rollout of the first batch had no outcome, so the sweep stopped
after …`, the commonest error, one `next:` line that inspects three of the errored episodes, and
an `error:` line, and exits 3. There is no resume line: resuming would run the same broken target.
A first batch with one outcome in it does not stop the sweep, and errors in later batches never
do. A local sweep is not stopped this way.

## Exit codes

- `0`: the sweep ran to the end and the run is complete; with `--dry-run`, the plan was printed.
  With `--try`, the one call returned an Episode the sweep could store, or the answer at the
  question was no and nothing was called.
- `1`: refused before anything ran, and nothing was written: the spec or the rollout is wrong, the
  design is underpowered, the backend's extra is missing, the estimate is above `--max-cost`
  (or, on this machine, `--max-cost` was given and the spec declares no `[cost]`), or the
  question cannot be asked (piped, without `--yes`). Declining the question also writes
  nothing. With `--try`, also a call that was made and did not end in an Episode the sweep could
  store: it raised, ran past its limit, returned something else or an outcome `[declare]` does
  not list, or ended its own process.
- `2`: the command line is wrong, such as `--pair-with` and `--resume` together. With `--try`,
  also `--dry-run`, `--resume` or `--pair-with` beside it, and a stdin that is not a terminal
  without `--yes`.
- `3`: stopped or failed after work started: `--max-rollouts` reached (resume it), every rollout
  errored (the run is stored complete; `inspect` shows the errors), on Modal or a cloud account
  the first batch had no outcome in any rollout (the run is partial), or on a cloud account the
  spend reached `stop_cost`, the cluster failed to start after a node was started, or Prove could
  not confirm the nodes stopped. With `--json`, also a target that called `sys.exit`.
- `130`: interrupted with Ctrl-C; what ran is kept and the run is partial, to resume, and the run
  records that it was interrupted. With `--try`, Ctrl-C at the question or during the call: the
  call's process is ended and nothing is written. On a cloud sweep SIGTERM and SIGHUP (a `kill`, a closed
  terminal) are handled as Ctrl-C is: the cluster is stopped first, then the sweep exits 130. The
  code is 130 even when the output pipe is closed, as when the sweep is piped into a program that
  has already exited.

## What it writes

One run in the store: a folder named by the run's id under `./prove-runs` (or `--store`) holding
`manifest.json` (the spec, the salt, the backend, the design and the status), `events.jsonl` (the
run's progress, line by line) and `episodes/`, the episodes as Parquet. A dashboard the store
already has is refreshed. `--dry-run` writes nothing. The layout is in
[The artifact format](../artifact-format.md).

`--try` stores nothing: no run, no store folder, no ledger line, nothing under `.poisson/`, and
no byte code beside your files. The one thing it can write is the traceback of a call that
raised, appended to `~/.cache/poisson-prove/errors.log`, the log an unexpected failure goes to.

A cloud sweep also appends to the spend ledger the `[cloud]` table names, and keeps a record of
what it started, and whether it has stopped it, under `$XDG_STATE_HOME/poisson-prove/cloud/`
(`~/.local/state` when the variable is unset). `sweep` never writes the spec.
