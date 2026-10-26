# `poisson-prove runs`

Lists every run in the store, newest first, with its number, name, id, status, backend, target and
row counts, so the next command can name a run. Any of the three works wherever a command takes a
run: the name (`"mock-agent 2026-10-26 a"`), the id, or the number (`#1` is the newest complete
run). So do `latest` and `previous`, the two newest complete runs, and `latest:TARGET`, the newest
complete run of one target. A partial run has no number and is never `latest`; name it by its name
or id.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove runs --help
usage: poisson-prove runs [-h] [--json] [--store PATH] [--plain] [--debug]

List every run in the store with its status, backend, target and row counts,
so the next command can name one.

options:
  -h, --help    show this help message and exit
  --json        print the list as one JSON document instead of text
  --store PATH  the store folder (default: $POISSON_PROVE_STORE when set, else
                ./prove-runs)
  --plain       print plain text, as a pipe gets it, on a terminal too
                (default: pretty on a terminal, plain otherwise)
  --debug       also print the traceback of an unexpected failure

examples:
  poisson-prove runs
  poisson-prove runs --json
```

## Options

- `--json` prints the list as one JSON document, `poisson-prove.runs/1`, each run with its
  `run_id`, `run_name`, status and counts.
- `--store PATH` lists another store than `./prove-runs` (or `$POISSON_PROVE_STORE`); `--plain`
  prints plain text on a terminal too; `--debug` adds the traceback of an unexpected failure.

## Examples

The example's two runs:

<!-- docs-check: run -->
```console
$ poisson-prove runs
ok  2 runs in prove-runs
#  name                     id                     status    backend  target      rows   rows without an outcome  created
1  mock-agent 2026-10-26 b  20261026T144648Z-0eef  complete  local    mock-agent  1,746  0                        2026-10-26T14:46:48Z
2  mock-agent 2026-10-26 a  20261026T144646Z-ba84  complete  local    mock-agent  1,746  0                        2026-10-26T14:46:46Z
```

`rows without an outcome` counts the episodes that errored, those stopped at `--episode-timeout`
included; `inspect` shows them by their error. The same list as JSON:

<!-- docs-check: run -->
```console
$ poisson-prove runs --json
{
  "schema": "poisson-prove.runs/1",
  "verdict": "ok",
  "store": "prove-runs",
  "runs": [{"run_id": "20261026T144648Z-0eef", "run_name": "mock-agent 2026-10-26 b", "status": "complete"}]
  …
}
```

A store that does not exist is refused, with the command that would make one:

<!-- docs-check: run -->
```console
$ poisson-prove --store nowhere runs  # exits 1
error: no store at nowhere. …
  next: poisson-prove --store nowhere sweep SPEC.toml --target pkg.module:rollout
```

## Exit codes

- `0`: the list was printed; an empty store is listed as empty.
- `1`: refused: no store at that path, or a store this version cannot read.
- `2`: the command line is wrong.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: interrupted with Ctrl-C.

## What it writes

Nothing.
