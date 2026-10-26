# `poisson-prove diff`

Compares two runs condition by condition, for each outcome that counts as an event: which
conditions got worse, which got safer, and for every condition that did not move, the smallest
change it could have detected. The first line is the verdict word; the lines under it say how it
was reached; then come the per-condition tables and the layered report.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove diff --help
usage: poisson-prove diff [-h] [--event NAME]
                          [--method {fisher_bh,mcnemar_bh,logrank_bh}] [--q Q]
                          [--methods {all}] [--json] [--save]
                          [--permutations N] [--seed N] [--by KEY]
                          [--max-group-mde FRACTION] [--depth N]
                          [--store PATH] [--plain] [--debug]
                          [RUN ...]

Compare two stored runs condition by condition: which conditions got worse, which
got safer, and what the comparison could not have seen.

positional arguments:
  RUN                   the baseline and the candidate (default: previous and
                        latest)

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
  --methods {all}       also run the other two methods and print them side by
                        side (default: one method)
  --json                print the comparison as one JSON document instead of
                        text
  --save                save the comparison into the store, under
                        .poisson/artifacts/ (default: not saved)
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
  poisson-prove diff previous latest
  poisson-prove diff previous latest --event violated --json
```

## Options

- `RUN ...` names the baseline and the candidate, in that order: a run's name, its id, `latest`,
  `previous` or `#1`, as `runs` numbers them. With none, `previous` and `latest`.
- `--event NAME` is an outcome that counts as the event; give it once per event. Without it the
  events are inferred: every outcome but the most frequent, which is named as the non-event.
  The inference does not read the runs' `[declare]` tables: when the most frequent outcome is a
  failure, it is left out, so name the events you mean when it matters. Whether a rise of an event
  is worse or safer comes from those tables; for runs that declare nothing, the name can carry it,
  `--event timeout:failure`, and otherwise the verdict uses the kindless words `higher`, `lower`
  and `mixed`.
- `--method` is the test each condition gets. `mcnemar_bh` pairs the runs' episodes on their shared
  seeds, and is the default for runs paired at sweep time; `fisher_bh` treats the runs as two
  separate samples, the default otherwise; `logrank_bh` compares the time to the event. Naming
  `fisher_bh` on paired runs works and prints a `note:` saying the pairing is unused.
- `--q Q` is the false discovery rate the flags are held to, 0.05 by default; the verdict word
  counts the changes that also hold at the family-wise level at `q` (Holm).
- `--methods all` also runs the other two methods and prints their tables beside the first.
- `--json` prints the comparison as one JSON document, `poisson-prove.diff/1`.
- `--save` saves the comparison into the store, under `.poisson/artifacts/`, where the
  [dashboard](../dashboard.md) and the [terminal app](../terminal-app.md) find it.
- `--permutations N` and `--seed N` set the within-condition permutations behind the omnibus test
  (4,000, seed 0); `--by KEY` chooses the grouping the fault lines test (an axis both runs declare,
  `task_family`, `task_id`, `task`, or `grid` for the whole grid); `--max-group-mde FRACTION` is
  the largest group-level detectable change you accept (0.200 by default, the same constant
  `--max-mde` of `sweep` uses); `--depth N` stops at the fault lines (2) or goes on to the
  conditions under each rejecting group (3, the default).
  [The layered report](../concepts/the-layered-report.md) explains the four layers.
- `--store PATH` is the store folder; `--plain` prints plain text on a terminal too; `--debug`
  adds the traceback of an unexpected failure.

## Reading the first line

The first word is the verdict: `worse`, `safer`, `trade` (both), `no significant change` or
`too small to tell` when nothing counted, or the kindless `higher`, `lower` and `mixed`.
[What the statistics claim](../concepts/what-the-statistics-claim.md) defines each. Then, per
event, how many conditions were flagged safer and worse at the false discovery rate, and the test.
A clause after the test, `counted at the family-wise level`, gives the changes the word counts
when they differ from the flags; an event it does not name counted as flagged.

## Examples

The two runs of the example, with the method chosen for paired runs:

<!-- docs-check: run -->
```console
$ poisson-prove diff
trade  timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds); …
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  before  mock-agent 2026-10-26 a
  after  mock-agent 2026-10-26 b
…
  verdict rule  the verdict counts changes at the family-wise level (Holm, q 0.05 over 18 tests); a condition's flag is Benjamini-Hochberg's, at the false discovery rate q 0.05 over 18 tests
…
  limits  the smallest change one condition alone would be flagged for, 4 times in 5, if it alone changed, from where the condition was (the paired test (McNemar), q 0.05 over 18 tests); …
  intervals  on each condition's change: Tango at 97.5%, false coverage (Benjamini-Yekutieli) over the … flagged; …
…
  next: poisson-prove report --x task_id --y tool_fail_rate
```

One event, with the unpaired test named: the `note:` says the shared seeds go unused, and the
verdict for the forbidden fallback alone is `safer`:

<!-- docs-check: run -->
```console
$ poisson-prove diff --event violated --method fisher_bh
note: fisher_bh compares two runs that share their seeds as independent samples: …
safer  violated: … safer, … worse (two separate samples)
  method  two separate samples (Fisher), named with --method
  before  mock-agent 2026-10-26 a
  after  mock-agent 2026-10-26 b
…
```

Saved, so the dashboard and the terminal app show it, and as JSON:

<!-- docs-check: run -->
```console
$ poisson-prove diff --save
trade  timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds); …
…
  saved  comparison …
…
$ poisson-prove diff --json
{
  "schema": "poisson-prove.diff/1",
  "verdict": "trade",
  "sentence": "timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds); …",
  "method": "mcnemar_bh",
  "method_chosen": "default"
  …
}
```

## Exit codes

- `0`: the comparison was printed, whatever it says: `too small to tell` and
  `no significant change` are results too.
- `1`: refused, and nothing was compared: a run the store does not have, two runs that declare
  different outcomes, an event neither run has, no condition with an outcome in both runs, or a
  condition that ran several cases. A partial run is compared over the conditions it has.
- `2`: the command line is wrong, such as an unknown `--method`.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: interrupted with Ctrl-C.

## What it writes

Nothing, unless `--save`: then one saved comparison under the store's
`.poisson/artifacts/comparison/`, named by a digest of what it compared, so saving the same
comparison twice keeps one. A dashboard the store already has is refreshed.
