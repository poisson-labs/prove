# `poisson-prove report`

Writes a report folder you can keep or share. Two runs give the comparison `diff` prints, with a
heatmap of the change in every condition; one run gives its survival report, how soon and how
often each outcome happened. The folder holds `report.md`, `heatmap.svg` and `receipt.html`, a
one-page record of what was compared and how. A comparison is also saved into the store.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove report --help
usage: poisson-prove report [-h] [--event NAME]
                            [--method {fisher_bh,mcnemar_bh,logrank_bh}]
                            [--q Q] [--methods {all}] [--permutations N]
                            [--seed N] [--by KEY] [--max-group-mde FRACTION]
                            [--depth N] --x AXIS [--y AXIS] [--fix KEY=VALUE]
                            [--horizon T] [--theme {dark,light}] [--top-n N]
                            [--forest {auto,always,never}] [--out DIR]
                            [--title TEXT] [--force] [--paired DECL] [--json]
                            [--store PATH] [--plain] [--debug]
                            [RUN ...]

Write a report folder: two runs give the comparison with its heatmap, one run gives
its survival report. The folder holds report.md, heatmap.svg and receipt.html. A
comparison is also saved into the store, under .poisson/artifacts/.

positional arguments:
  RUN                   A B for a comparison, one RUN for a survival report
                        (default: previous and latest)

options:
  -h, --help            show this help message and exit
  --event NAME          an outcome that counts as the event; repeatable
                        (default: inferred from the outcomes present)
  --method {fisher_bh,mcnemar_bh,logrank_bh}
                        the per-condition test: fisher_bh treats the two runs
                        as separate samples, mcnemar_bh pairs them on their
                        shared seeds, logrank_bh is time to the event
                        (default: mcnemar_bh for runs paired at sweep time,
                        else fisher_bh)
  --q Q                 the level of the per-condition flags (false discovery
                        rate) and of the verdict (family-wise) (default: 0.05)
  --methods {all}       add the method comparison table (default: one method;
                        two runs only)
  --x AXIS              required: the config key on the x axis (omitted: lists
                        the axes and events the runs carry; no default)
  --y AXIS              the config key on the y axis (default: none)
  --fix KEY=VALUE       pin a config key to one value; repeatable (default:
                        nothing pinned)
  --horizon T           truncate a survival report at this time (default: the
                        run's own horizon)
  --theme {dark,light}  the report's colours (default: dark)
  --top-n N             worst conditions listed (default: 10)
  --forest {auto,always,never}
                        single-axis panels as a forest plot: auto, always or
                        never (default: auto)
  --out DIR             the folder to write (default: ./prove-report-A-vs-B,
                        or ./prove-report-RUN)
  --title TEXT          the report's title (default: the runs and the events)
  --force               write into a folder that is not empty
  --paired DECL         a paired-replay declaration whose sweep (A, B) is;
                        folds its sections into the report and writes its
                        files beside it (default: none; two runs only)
  --json                print the comparison and the files written as one JSON
                        document instead of text
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
  poisson-prove report previous latest --x tool_fail_rate --y task_id
  poisson-prove report latest --x tool_fail_rate --event violated
```

## Options

- `RUN ...` is `A B` for a comparison, one run for its survival report; with none, `previous` and
  `latest`.
- `--x AXIS` is required: the axis across the heatmap. `--y AXIS` is the axis down it. Every other
  axis of the runs must be pinned to one value with `--fix KEY=VALUE` (repeatable), so each cell of
  the heatmap is one condition; the refusal names the axis left free.
- `--event NAME`, `--method`, `--q Q` and `--methods all` are `diff`'s: the events, the
  per-condition test, the false discovery rate of the flags, and the other two methods' table.
- `--permutations N`, `--seed N`, `--by KEY`, `--max-group-mde FRACTION` and `--depth N` set the
  layered report as they do for `diff` (the group-level limit defaults to 0.200, the constant
  `--max-mde` of `sweep` uses): see [The layered report](../concepts/the-layered-report.md).
- `--horizon T` cuts a survival report at time `T`, in the run's `t_unit`; by default, the run's own
  horizon.
- `--theme` draws the heatmap `dark` (the default) or `light`; `--top-n N` is how many of the worst
  conditions the report lists (10); `--forest` draws a single-axis panel as a forest plot: `auto`,
  `always` or `never`.
- `--out DIR` is the folder to write, `./prove-report-A-vs-B` by default (the runs' names, in
  lower case with dashes); `--title TEXT` replaces the report's title; `--force` writes into a
  folder that is not empty.
- `--paired DECL` folds a paired-replay declaration's sections into a comparison of its two arms
  and writes its files beside the report; see [`paired`](paired.md).
- `--json` prints the comparison and the files written as one JSON document.
- `--store PATH` is the store folder; `--plain` prints plain text on a terminal too; `--debug`
  adds the traceback of an unexpected failure.

## Examples

The comparison of the example's two runs, with the task across and the tool failure rate down:

<!-- docs-check: run -->
```console
$ poisson-prove report --x task_id --y tool_fail_rate
ok  wrote prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b (3 files)
  wrote  prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b/report.md
  wrote  prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b/heatmap.svg
  wrote  prove-report-mock-agent-2026-10-26-a-vs-mock-agent-2026-10-26-b/receipt.html
  saved  comparison …
…
```

One run's survival report on the forbidden fallback, in a folder named for it:

<!-- docs-check: run -->
```console
$ poisson-prove report latest --x task_id --y tool_fail_rate --event violated --out one-run
ok  wrote one-run (3 files)
  wrote  one-run/report.md
  wrote  one-run/heatmap.svg
  wrote  one-run/receipt.html
…
```

One axis, the other pinned to its hardest value, as JSON:

<!-- docs-check: run -->
```console
$ poisson-prove report --x task_id --fix tool_fail_rate=0.55 --out hardest --json
{
  "schema": "poisson-prove.report/1",
  "verdict": "ok",
  "out": "hardest",
  "wrote": ["hardest/report.md", "hardest/heatmap.svg", "hardest/receipt.html"],
  "method": "mcnemar_bh"
  …
}
```

Without `--x`, the refusal lists the axes and events the runs carry:

<!-- docs-check: run -->
```console
$ poisson-prove report  # exits 1
error: report requires --x AXIS, which was not given. …
  next: poisson-prove report --x task_id
```

## Exit codes

- `0`: the folder was written.
- `1`: refused, and nothing was written: no `--x`, an axis left free, a folder that is not empty
  without `--force`, or any refusal of `diff`.
- `2`: the command line is wrong.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: interrupted with Ctrl-C.

## What it writes

The report folder: `report.md`, `heatmap.svg` and `receipt.html`, and with `--paired` the paired
replay's files beside them. A comparison of two runs is also saved into the store, under
`.poisson/artifacts/comparison/`, with its charts, and a dashboard the store already has is
refreshed; a survival report of one run saves nothing.
