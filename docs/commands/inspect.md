# `poisson-prove inspect`

Prints the episodes of one run that ended in an outcome, or in an error of a kind: each with its
condition, its seed and, when the run stored one, its trace, step by step. It ends with a snippet
that reproduces the first of them: the rollout, called with that condition and that seed. It is
the one verb that reads what a rollout put in `meta`.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove inspect --help
usage: poisson-prove inspect [-h] --event NAME [--where KEY=VALUE] [--limit N]
                             [--json] [--store PATH] [--plain] [--debug]
                             [RUN]

Print the episodes of a run that ended in an event, or in an error of a kind,
each with its config and seed, then a snippet that reproduces one of them.

positional arguments:
  RUN                the run to inspect (default: latest)

options:
  -h, --help         show this help message and exit
  --event NAME       required: the outcome, or the error kind, to show
                     (omitted: lists the events the run carries; no default)
  --where KEY=VALUE  keep only episodes whose config has this value;
                     repeatable (default: all)
  --limit N          show at most N episodes (default: all)
  --json             print the episodes as one JSON document instead of text
  --store PATH       the store folder (default: $POISSON_PROVE_STORE when set,
                     else ./prove-runs)
  --plain            print plain text, as a pipe gets it, on a terminal too
                     (default: pretty on a terminal, plain otherwise)
  --debug            also print the traceback of an unexpected failure

examples:
  poisson-prove inspect latest --event violated
  poisson-prove inspect latest --event timeout --limit 5
```

## Options

- `RUN` is the run to read, `latest` when none is named; a name, an id or `#N` from `runs` works.
- `--event NAME` is required: an outcome (`timeout`), or the kind of error an errored episode
  stored. Without it the refusal lists the events the run carries.
- `--where KEY=VALUE` keeps only the episodes whose condition has that value; repeat it to narrow
  further. The value is read as TOML, so a word is quoted: `--where 'task_id="refund"'`.
- `--limit N` prints at most `N` episodes; `N` is 1 or more.
- `--json` prints the episodes and the snippet's parts as one JSON document,
  `poisson-prove.inspect/1`.
- `--store PATH` is the store folder; `--plain` prints plain text on a terminal too; `--debug`
  adds the traceback of an unexpected failure.

## Examples

One episode of the patched agent that took the forbidden fallback on a refund: its condition, its
seed, its trace (each tool call, with the failed ones marked `ToolError`), and how to run it again:

<!-- docs-check: run -->
```console
$ poisson-prove inspect latest --event violated --where 'task_id="refund"' --limit 1
ok  1 of … episodes with outcome or error "violated" in run "mock-agent 2026-10-26 b"
config_hash: …
config: …
seed: …
replicate_index: …
t: …
…
# reproduce one episode
from poisson_prove.examples.mock_agent import rollout_patched
…
```

The same, as JSON, on a time-out:

<!-- docs-check: run -->
```console
$ poisson-prove inspect latest --event timeout --limit 1 --json
{
  "schema": "poisson-prove.inspect/1",
  "verdict": "ok",
  "run_name": "mock-agent 2026-10-26 b",
  "event": "timeout",
  "episodes": [{"config": {"task_id": "refund"}, "seed": 2226271928, "outcome": "timeout", "error": null}],
  "reproduce": {"module": "poisson_prove.examples.mock_agent", "function": "rollout_patched"}
  …
}
```

With no event, the refusal lists what the run carries:

<!-- docs-check: run -->
```console
$ poisson-prove inspect  # exits 1
error: inspect requires --event NAME, which was not given. …
…
```

## Exit codes

- `0`: the episodes were printed; none matching is a result too, said on the first line.
- `1`: refused: no `--event`, a run the store does not have, or a `--where` value that is not TOML.
- `2`: the command line is wrong.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: interrupted with Ctrl-C.

## What it writes

Nothing.
