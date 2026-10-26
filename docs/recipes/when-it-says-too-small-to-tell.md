# When it says too small to tell

`too small to tell` means no condition changed significantly, and at least one condition could
not have shown a change as large as the one you accepted. It is not a pass: nothing was seen
because not enough could be. This recipe makes one on purpose, reads it, and fixes it with the
numbers Prove gives.

## Make one

A baseline of the keyless example, then a quick re-check of the same agent at 20 replicates per
condition, paired with it. Twenty replicates cannot detect a change of 0.20, so the plan refuses
them unless you accept a larger change, here 0.7:

<!-- docs-check: run -->
```console
$ poisson-prove init --example
ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates
  next: poisson-prove sweep
$ poisson-prove sweep --yes --name before
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
…
$ poisson-prove sweep --yes --replicates 20 --max-mde 0.7 --pair-with before --name quick-check
plan  180 rollouts of mock-agent: 9 cells x 20 replicates on local, $0 (local)
…
  smallest rise one condition alone would be flagged for  0.660 at its worst base rate, 0.150 (the paired test, q 0.05 over 18 tests, 4 times in 5; you accept up to 0.700)
done  180 rollouts in run "quick-check" (complete) in … s, paired with "before"
…
```

## Read it

<!-- docs-check: run -->
```console
$ poisson-prove diff before quick-check
too small to tell  timeout: … safer, … worse · violated: … safer, … worse (paired test on shared seeds)
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
  threshold  0.200 (the smaller of the two the runs recorded at sweep time)
  before  before
  after  quick-check
…
```

The `threshold` line says what "could have shown" is measured against: the smaller of the changes
the two runs accepted when they were swept, 0.20 from the baseline. The `limits` line further down
says how large a change each condition could have caught; at 20 replicates most are far above
0.20. The could-not-detect page of the [dashboard](../dashboard.md), and the `d` screen of the
[terminal app](../terminal-app.md), list each condition's limit against the threshold.

## Fix it

Two levers, and the plan tells you how far to pull either before anything runs. More replicates:
dry-run the design you would sweep, paired with the baseline as the real sweep will be, and the
refusal names the replicates that reach the change you accept:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --replicates 20 --pair-with before --dry-run  # exits 1
plan  180 rollouts of mock-agent: 9 cells x 20 replicates on local, $0 (local)
…
error: underpowered design: one condition alone would be flagged for a change of 0.568 at its worst base rate, 0.000, and you accept 0.200
  next: poisson-prove sweep --replicates 194 --pair-with before --dry-run
  next: poisson-prove sweep --replicates 20 --pair-with before --dry-run --max-mde 0.662
$ poisson-prove sweep --replicates 194 --pair-with before --dry-run
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
…
  smallest rise one condition alone would be flagged for  0.200 at its worst base rate, 0.400 (the paired test, q 0.05 over 18 tests, 4 times in 5; you accept up to 0.200)
```

Or fewer conditions: every condition and event is one more test in the family, and the test each
one gets is stricter for it, so dropping axis values you do not need lowers every condition's
limit at the same replicates. Then sweep the design the plan accepts, paired with the baseline, and
compare the two. Every condition can now catch a change of 0.20, so the word is
`no significant change` when nothing counted, or names what did.

## What this does not tell you

That nothing changed. `no significant change` says a change as large as the threshold would have been
caught 4 times in 5 in each condition, and none was; a smaller change can still be there. And accepting a larger change with
`--max-mde` lets a small design pass the plan without letting it see more: the quick check above
could not have caught a change smaller than about 0.66 in its worst condition.
