# `poisson-prove check`

The comparison `diff` makes, as a gate: it reads the events you name and exits 0 when the
comparison passes and 4 when it fails, so a pipeline can stop on a change for the worse. It never
infers its events: a gate whose meaning changed when a new outcome appeared would not be a gate.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove check --help
usage: poisson-prove check [-h] --event NAME
                           [--method {fisher_bh,mcnemar_bh,logrank_bh}]
                           [--q Q] [--fail-on {worse,any,higher,lower}]
                           [--json] [--save] [--store PATH] [--plain]
                           [--debug]
                           [RUN ...]

Gate on a comparison of two runs over the events you name: passed exits 0 and
failed exits 4, so a pipeline can stop on a change for the worse.

positional arguments:
  RUN                   the baseline and the candidate (default: previous and
                        latest)

options:
  -h, --help            show this help message and exit
  --event NAME          an outcome that counts as the event; repeatable
                        (required: a gate never infers its events; omitted:
                        lists the events the runs carry; no default)
  --method {fisher_bh,mcnemar_bh,logrank_bh}
                        the per-condition test: fisher_bh treats the two runs
                        as separate samples, mcnemar_bh pairs them on their
                        shared seeds, logrank_bh is time to the event
                        (default: mcnemar_bh for runs paired at sweep time,
                        else fisher_bh)
  --q Q                 the false discovery rate the verdicts are held to
                        (default: 0.05)
  --fail-on {worse,any,higher,lower}
                        fail on a condition significantly worse, on any
                        significant change, or on a rate that rose (higher) or
                        fell (lower); worse needs each event's kind (default:
                        worse)
  --json                print the verdict and the comparison as one JSON
                        document instead of text
  --save                save the check into the store, under
                        .poisson/artifacts/ (default: not saved)
  --store PATH          the store folder (default: $POISSON_PROVE_STORE when
                        set, else ./prove-runs)
  --plain               print plain text, as a pipe gets it, on a terminal too
                        (default: pretty on a terminal, plain otherwise)
  --debug               also print the traceback of an unexpected failure

examples:
  poisson-prove check latest previous --event violated
  poisson-prove check latest previous --event violated --fail-on any
```

## Options

- `RUN ...` names the baseline and the candidate, in that order; with none, `previous` and
  `latest`.
- `--event NAME` is required: each outcome the gate reads, once per event. Without it `check` is
  refused and lists the events the runs carry. When the runs do not declare whether an event is a
  failure or a success, the name can say it: `--event timeout:failure`.
- `--fail-on` says what fails the gate. `worse` (the default) fails on any condition significantly
  worse, which needs each event's kind (its `[declare]` table says which outcomes are failures and
  which successes); `any` fails on any significant change either way; `higher` and `lower` fail on
  a rate that rose or fell, whatever the event's kind.
- `--method` and `--q Q` are `diff`'s: the per-condition test (the paired one by default for runs
  paired at sweep time) and the false discovery rate of the flags, 0.05 by default.
- `--json` prints the verdict and the comparison as one JSON document, `poisson-prove.check/1`,
  with `passed` and `fail_on` beside the comparison's own keys.
- `--save` saves the check into the store, under `.poisson/artifacts/`.
- `--store PATH` is the store folder; `--plain` prints plain text on a terminal too; `--debug`
  adds the traceback of an unexpected failure.

## Examples

The patched agent never takes the forbidden fallback more often, so a gate on `violated` passes;
the comparison's own word is on the `comparison` line:

<!-- docs-check: run -->
```console
$ poisson-prove check --event violated
passed  violated: … worse, … safer in 9 conditions; fail on worse (paired test on shared seeds)
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  comparison  safer
  before  mock-agent 2026-10-26 a
  after  mock-agent 2026-10-26 b
…
```

It runs out of tool calls more often where tools fail most, so a gate on `timeout` fails, names the
condition, and exits 4:

<!-- docs-check: run -->
```console
$ poisson-prove check --event timeout  # exits 4
failed  timeout: … worse, … safer in 9 conditions; fail on worse; failed in task_id refund · tool_fail_rate 0.55 (paired test on shared seeds)
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  comparison  trade
…
$ poisson-prove check --event timeout --fail-on any --json  # exits 4
{
  "schema": "poisson-prove.check/1",
  "verdict": "failed",
  "passed": false,
  "fail_on": "any",
  "method": "mcnemar_bh"
}
```

With no event, the gate is refused and lists what it could read:

<!-- docs-check: run -->
```console
$ poisson-prove check  # exits 1
error: check requires --event NAME, which was not given; a gate whose meaning changes when a new outcome appears is not a gate. …
…
```

## Exit codes

- `0`: the gate passed.
- `1`: refused, and nothing was compared: no `--event`, an event neither run has, `--fail-on
  worse` on an event whose kind neither the runs nor the command line give, or any refusal of
  `diff`.
- `2`: the command line is wrong.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `4`: the gate failed: a condition changed the way `--fail-on` names.
- `130`: interrupted with Ctrl-C.

## What it writes

Nothing, unless `--save`: then one saved check under the store's `.poisson/artifacts/check/`. A
dashboard the store already has is refreshed. [In CI](../recipes/in-ci.md) uses `check` as a build
step.
