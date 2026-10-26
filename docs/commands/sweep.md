# `poisson-prove sweep`

Runs every condition of a sweep spec, a number of replicates each, and stores every episode as a
run. It prints the plan first: what will run, where, what it costs, and the smallest change in a
condition's failure rate the design can catch. A design too small for the change you accept is
refused before anything runs. On a terminal it then asks `[y/N]`; piped or in CI it needs
`--yes`.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove sweep --help
usage: poisson-prove sweep [-h] [--target pkg.module:rollout] [--replicates N]
                           [--backend {local,modal,burla}]
                           [--salt HEX | --pair-with RUN | --resume [RUN]]
                           [--name TEXT] [--episode-timeout S]
                           [--max-rollouts N] [--batch-size N]
                           [--max-mde FRACTION] [--dry-run] [--yes] [--json]
                           [--concurrency N] [--infra-retries N]
                           [--max-cost USD] [--est-seconds S]
                           [--app-name NAME] [--image SECTION] [--store PATH]
                           [--plain] [--debug]
                           [SPEC.toml]

Run every condition of a sweep spec, N replicates each, on the local machine or a
remote backend. The plan is printed first, with its cost estimate, and the sweep
starts only after a yes.

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
  --backend {local,modal,burla}
                        where the rollouts run: local, modal or burla (burla
                        is experimental; default: local)
  --salt HEX            the run salt seeds are derived from (default: a fresh
                        one)
  --pair-with RUN       inherit that run's salt, so the two runs share their
                        seeds (default: none)
  --resume [RUN]        continue that partial run where it stopped; alone, the
                        latest partial run; written after SPEC.toml when a
                        spec is given, so the spec is not read as the run
                        (default: none)
  --name TEXT           the name the new run goes by (default: computed)
  --episode-timeout S   seconds an episode may take before it is recorded as
                        timed out (default: no limit)
  --max-rollouts N      stop after N rollouts and leave the run partial
                        (default: run them all)
  --batch-size N        rows written to the store at a time (default: 64)
  --max-mde FRACTION    the largest minimum detectable effect you accept for
                        this design (default: 0.200)
  --dry-run             print the plan and stop; nothing is run or written
  --yes                 skip the question after the plan
  --json                print the plan and the result as one JSON document
                        instead of text
  --store PATH          the store folder (default: $POISSON_PROVE_STORE when
                        set, else ./prove-runs)
  --plain               print plain text, as a pipe gets it, on a terminal too
                        (default: pretty on a terminal, plain otherwise)
  --debug               also print the traceback of an unexpected failure

remote backends (override the [modal] table; --infra-retries, --max-cost and --est-seconds also override [burla]):
  --concurrency N       containers at once (default: the table's)
  --infra-retries N     retries per batch (default: the table's)
  --max-cost USD        refuse before anything starts when the estimate is
                        above this (default: no cap)
  --est-seconds S       seconds per episode, for the estimate (default: the
                        table's)
  --app-name NAME       the Modal app name (default: the table's)
  --image SECTION       the [modal.SECTION] image table to build from
                        (default: image)

examples:
  poisson-prove sweep
  poisson-prove sweep --target my_agent:rollout_patched --pair-with latest --yes
  poisson-prove sweep other.toml --target my_agent:rollout --replicates 300
```

## Options

- `SPEC.toml` is the sweep spec, `./prove.toml` when none is named. [The sweep spec](../sweep-spec.md)
  has every key.
- `--target pkg.module:rollout` runs another rollout than the spec's `target`: the usual way to
  sweep a changed agent against the same spec.
- `--replicates N` overrides the spec's replicates for this run; the manifest records what ran.
- `--backend` chooses where the rollouts run: `local` (this machine, the default), `modal` or
  `burla` (experimental). See [Backends](../backends.md).
- `--salt HEX` sets the run salt every seed is derived from; two runs with one salt share their
  seeds. `--pair-with RUN` takes another run's salt, which is how you pair a run with an earlier
  one: `--pair-with latest`. `--resume [RUN]` continues a partial run where it stopped; alone, the
  latest partial run. Only one of the three may be given.
- `--name TEXT` names the run. Without it the run is named by its target, the date and a letter,
  such as `mock-agent 2026-10-26 a`; every verb accepts the name in place of the run's id.
- `--episode-timeout S` stops an episode that runs longer than `S` seconds and stores it with no
  outcome, as an error of kind `timeout`. On the local backend each episode then runs in a child
  process that can be stopped.
- `--max-rollouts N` stops after `N` rollouts and leaves the run partial, to resume later.
- `--batch-size N` is how many rows are written to the store at a time; a stopped run keeps every
  whole batch.
- `--max-mde FRACTION` is the largest smallest-detectable-change you accept, 0.200 by default: the
  plan refuses a design whose worst condition could not catch a change that size 4 times in 5.
- `--dry-run` prints the plan and stops. It checks the spec, imports the rollout in a process of
  its own with the network blocked, and checks it takes `(cfg, seed)`, without calling it.
- `--yes` skips the question after the plan.
- `--json` prints the plan and the result as one JSON document.
- `--concurrency N`, `--infra-retries N`, `--max-cost USD`, `--est-seconds S`, `--app-name NAME`
  and `--image SECTION` override the `[modal]` table for one run; `--infra-retries`, `--max-cost`
  and `--est-seconds` also override `[burla]`. `--max-cost` refuses a sweep whose estimate is above
  it before anything starts.
- `--store PATH` is the store folder, `./prove-runs` unless `$POISSON_PROVE_STORE` says otherwise;
  `--plain` prints plain text on a terminal too; `--debug` adds the traceback of an unexpected
  failure.

## Examples

`--dry-run` shows the plan and runs nothing:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --dry-run
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
  target  poisson_prove.examples.mock_agent:rollout (imports, takes cfg and seed)
  outcomes  failures: timeout, violated
…
  smallest rise one condition alone would be flagged for  0.199 at its worst base rate, 0.400 (Fisher, q 0.05 over 18 tests, 4 times in 5; you accept up to 0.200)
```

Twenty replicates per condition are too few to catch a change of 0.20, so the plan is refused,
with the two ways out: more replicates, or accepting a larger change:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --replicates 20 --dry-run  # exits 1
plan  180 rollouts of mock-agent: 9 cells x 20 replicates on local, $0 (local)
…
error: underpowered design: one condition alone would be flagged for a change of 0.519 at its worst base rate, 0.000, and you accept 0.200
  next: poisson-prove sweep --replicates 193 --dry-run
  next: poisson-prove sweep --replicates 20 --dry-run --max-mde 0.625
```

A sweep stopped short keeps what it ran, exits 3 and says how to go on:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --yes --max-rollouts 100 --name stopped-early  # exits 3
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
…
stopped  100 of 1,746 rollouts kept in run "stopped-early" (partial) in … s
…
  next: poisson-prove sweep --resume
$ poisson-prove sweep --resume --yes
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
…
  Resuming "stopped-early": 100 stored, 1,646 to run
…
done  1,746 rollouts in run "stopped-early" (complete) in … s
```

The plan as JSON, for a script:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --dry-run --json
{
  "schema": "poisson-prove.sweep/1",
  "verdict": "plan",
  "sentence": "1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)",
  "plan": {"rollouts": 1746, "cells": 9, "replicates": 194, "backend": "local"},
  "design_mde": {"mde": 0.1991, "base_rate": 0.4, "direction": "rise"}
}
```

## Exit codes

- `0`: the sweep ran to the end and the run is complete; with `--dry-run`, the plan was printed.
- `1`: refused before anything ran, and nothing was written: the spec or the rollout is wrong, the
  design is underpowered, the backend's extra is missing, the estimate is above `--max-cost`, or
  the question cannot be asked (piped, without `--yes`). Declining the question also writes
  nothing.
- `2`: the command line is wrong, such as `--pair-with` and `--resume` together.
- `3`: stopped or failed after work started: `--max-rollouts` reached (resume it), or every
  rollout errored (the run is stored complete; `inspect` shows the errors).
- `130`: interrupted with Ctrl-C; what ran is kept and the run is partial, to resume.

## What it writes

One run in the store: a folder named by the run's id under `./prove-runs` (or `--store`) holding
`manifest.json` (the spec, the salt, the backend, the design and the status), `events.jsonl` (the
run's progress, line by line) and `episodes/`, the episodes as Parquet. A dashboard the store
already has is refreshed. `--dry-run` writes nothing. The layout is in
[The artifact format](../artifact-format.md).
