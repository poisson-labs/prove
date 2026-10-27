# `poisson-prove serve`

Serves one comparison of two runs as a read-only page in your browser, on a loopback port it
chooses: the plain summary first, then the statistics it came from, condition by condition. The
page is built before anything is bound, holds only data already on the machine, and stops with
the process. The comparison it shows is saved into the store first, so the
[dashboard](../dashboard.md) and the [terminal app](../terminal-app.md) have it too.
[Reading a serve page](../reading-a-serve-page.md) says what each section of the page answers.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove serve --help
usage: poisson-prove serve [-h] --event NAME
                           [--method {fisher_bh,mcnemar_bh,logrank_bh}]
                           [--q Q] [--permutations N] [--seed N] [--by KEY]
                           [--max-group-mde FRACTION] [--depth N] --x AXIS
                           [--y AXIS] [--fix KEY=VALUE] [--theme {dark,light}]
                           [--top-n N] [--forest {auto,always,never}]
                           [--title TEXT] [--json] [--store PATH] [--plain]
                           [--debug]
                           [RUN ...]

Serve a read-only page for one pair of runs on an ephemeral loopback port, built
before the bind; the comparison it shows is saved into the store, under
.poisson/artifacts/, before the page is served; Ctrl-C stops it.

positional arguments:
  RUN                   the baseline and the candidate, in that order
                        (default: previous and latest)

options:
  -h, --help            show this help message and exit
  --event NAME          an outcome that counts as the event; repeatable
                        (required: for runs that declare no kinds, since a
                        picture never infers its event, and omitted lists the
                        axes and events the runs carry; default: the failures
                        and successes the runs declare)
  --method {fisher_bh,mcnemar_bh,logrank_bh}
                        the per-condition test: fisher_bh treats the two runs
                        as separate samples, mcnemar_bh pairs them on their
                        shared seeds, logrank_bh is time to the event
                        (default: mcnemar_bh for runs paired at sweep time,
                        else fisher_bh)
  --q Q                 the level of the per-condition flags (false discovery
                        rate) and of the verdict (family-wise) (default: 0.05)
  --x AXIS              required: the config key on the x axis (omitted: lists
                        the axes and events the runs carry; no default)
  --y AXIS              the config key on the y axis (default: none)
  --fix KEY=VALUE       pin a config key to one value; repeatable (default:
                        nothing pinned)
  --theme {dark,light}  the page's colours (default: dark)
  --top-n N             worst conditions listed (default: 10)
  --forest {auto,always,never}
                        single-axis panels as a forest plot: auto, always or
                        never (default: auto)
  --title TEXT          the page's title (default: the runs and the events)
  --json                print the page's structure as one JSON document and
                        exit; bind nothing
  --store PATH          the store folder (default: $POISSON_PROVE_STORE when
                        set, else ./prove-runs)
  --plain               print plain text, as a pipe gets it, on a terminal too
                        (default: pretty on a terminal, plain otherwise)
  --debug               also print the traceback of an unexpected failure

the omnibus over the whole family:
  --permutations N      within-cell permutations behind the omnibus (default:
                        4000)
  --seed N              the permutation seed (default: 0)

the fault lines under the omnibus:
  --by KEY              the grouping for the fault lines: an axis both runs
                        declare, task_family/task_id/task, or grid (default:
                        resolved in a stated order and named either way)
  --max-group-mde FRACTION
                        the largest group-level minimum detectable effect you
                        accept (default: 0.200, the constant sweep's --max-mde
                        uses)
  --depth N             levels the procedure tests: 2 stops at the fault
                        lines, 3 adds the cells under each rejecting group
                        (default: 3); the bound is computed from this and the
                        grouping's shape, never from what rejected

examples:
  poisson-prove serve previous latest --x tool_fail_rate --event violated
  poisson-prove serve previous latest --x tool_fail_rate --event violated --json
```

## Options

- `RUN ...` names the baseline and the candidate, in that order; with none, `previous` and
  `latest`.
- `--event NAME` is an outcome to show, once per event. Without it the page shows the failures
  and successes the runs' `[declare]` tables name; for runs that declare none it is required,
  since a picture never infers its event, and the refusal lists the axes and events the runs
  carry.
- `--x AXIS` is required: the axis across the page's heatmap. `--y AXIS` is the axis down it, and
  `--fix KEY=VALUE` pins every other axis to one value, as for `report`.
- `--method`, `--q Q`, `--permutations N`, `--seed N`, `--by KEY`, `--max-group-mde FRACTION`
  and `--depth N` are `diff`'s: the per-condition test, the false discovery rate, and the layered
  report's settings (the group-level limit defaults to 0.200, the constant `--max-mde` of `sweep`
  uses).
- `--theme`, `--top-n N`, `--forest` and `--title TEXT` are `report`'s: the colours, how many of
  the worst conditions are listed, single-axis panels as a forest plot, and the page's title.
- `--json` prints the page's structure as one JSON document, `poisson-prove.viewpair/7`, instead
  of serving it.
- `--store PATH` is the store folder; `--plain` prints plain text on a terminal too; `--debug`
  adds the traceback of an unexpected failure.

## Examples

The timeouts of the example's two runs, by task, at the hardest tool failure rate. This serves the
page until Ctrl-C:

<!-- docs-check: skip: serves a page until it is stopped with Ctrl-C -->
```console
$ poisson-prove serve --event timeout --x task_id --fix tool_fail_rate=0.55
ok  serving "mock-agent 2026-10-26 a" against "mock-agent 2026-10-26 b" at http://127.0.0.1:52838/ (Ctrl-C stops)
  saved  comparison 96f8a747966e
```

Open the address it prints. `--json` prints what the page holds instead, and binds nothing:

<!-- docs-check: run -->
```console
$ poisson-prove serve --event timeout --x task_id --fix tool_fail_rate=0.55 --json
{
  "schema": "poisson-prove.viewpair/7",
  "verdict": "ok",
  "method": "mcnemar_bh",
  "pair": {"a": {"role": "baseline", "run_name": "mock-agent 2026-10-26 a"}}
  …
}
```

With no axis named, it is refused and says which it could use:

<!-- docs-check: run -->
```console
$ poisson-prove serve --event timeout  # exits 1
error: serve requires --x AXIS, which was not given. …
  next: poisson-prove serve --event timeout --x task_id
```

## Exit codes

- `0`: with `--json`, the structure was printed.
- `1`: refused, and nothing was served: no `--x`, no `--event` for runs that declare no kinds, an
  axis left free, or any refusal of `diff`.
- `2`: the command line is wrong.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: stopped with Ctrl-C, which is how a served page ends.

## What it writes

The comparison it shows, saved under the store's `.poisson/artifacts/comparison/` before the page
is served, with `--json` too (saving the same comparison again keeps one), and a dashboard the
store already has is refreshed. Nothing else: the page lives in memory, on 127.0.0.1 only, and goes when the process
does. It makes no outbound connection.
