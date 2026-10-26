# Pairing

Two runs are paired when they share their seeds: replicate 7 of a condition gets the same seed in
both. If your rollout seeds its randomness from `seed`, the two episodes start from the same draw,
and much of what differs between them is what you changed (a model's own sampling can still
differ, below). Prove can then compare each episode with its twin instead of two crowds, which
sees a change more easily when the twins mostly end the same way.

## Seeds and the run salt

Every run has a run salt, and each episode's seed is derived from the salt, the condition and the
replicate number. A new run gets a fresh salt. Two ways to share one:

- `--pair-with RUN` takes the salt of a run you already have: `sweep --pair-with latest` is the
  usual way to run the candidate after the baseline.
- `--salt HEX` sets the salt yourself, to pair two runs started on different machines.

Both runs record the salt in their manifests, and that record is what pairs them: Prove never
infers pairing from timing or names. `[declare]` and `[chaos]` tables are not part of what makes a
sweep the same sweep, so a run with a fault or a declaration still pairs with one without.

## Why the paired test is stronger

Fisher's test compares the two runs' rates as if they were two separate samples, so the noise of
both runs is in the comparison. The paired test (exact McNemar) looks only at the twin pairs that
ended differently: pairs where both episodes failed, or both succeeded, say nothing about the
change and are left out. When most episodes end the same way in both runs, as they do when only
your change differs, those few discordant pairs carry the whole signal, and a smaller change can
be flagged from the same number of episodes. The detection limits Prove prints do not count on
that gain: the plan and the limits treat twins as if they were independent, the safe assumption
when you cannot know in advance how far the runs will agree. So a paired plan states about the
same limit as an unpaired one, and the gain shows only in what gets flagged.

## When Prove pairs by default

`diff`, `check`, `report` and `serve` use the paired test when the two runs share a salt, and
Fisher's otherwise; the `method` line says which and why:

<!-- docs-check: setup quickstart -->

<!-- docs-check: run -->
```console
$ poisson-prove diff --event violated
safer  violated: … safer, … worse (paired test on shared seeds)
  method  paired test on shared seeds (McNemar), the default for runs paired at sweep time
…
```

You can name the unpaired test on paired runs; Prove runs it and says the pairing went unused:

<!-- docs-check: run -->
```console
$ poisson-prove diff --event violated --method fisher_bh
note: fisher_bh compares two runs that share their seeds as independent samples: …
safer  violated: … safer, … worse (two separate samples)
  method  two separate samples (Fisher), named with --method
…
```

The paired test on runs that do not share a salt is refused: there are no twins to compare.

## What pairing does not do

Shared seeds make your rollout's own random choices the same. They do not make the world the same:
a model that answers differently to the same request, a provider under different load, a tool
whose data changed between the runs. Those still differ between twins, and they are part of what
the comparison measures. To measure the first of them directly, how often the same request gets a
different answer, use paired replay.

## Paired replay

Paired replay is its own question, asked by `paired`: when the same request is sent twice, does it
get the same decision at a threshold? It checks pair by pair that the two arms sent the same
request, then counts the flips. See [`paired`](../commands/paired.md) and
[Paired replay](../recipes/paired-replay.md).
