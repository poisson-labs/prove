# Paired-replay arms

Two stored runs of one paired replay: 50 tasks, four replicates each, the same seeds in both
arms, so 200 episode pairs. `test_pr2_paired_analysis.py` reads them to check that the paired
analysis reproduces the published two-by-two table, interval and swing.

## What is kept

Every episode of both runs, with only the fields that test reads: `config_hash`, `config` (the
task id), `seed`, `replicate_index`, `outcome`, `t`, `horizon`, `confidence`, and `meta["reward"]`.
Everything else the runs stored (the traces, token counts, model text and timings) is dropped;
`wall_time` is 0.0 and `backend_meta` is empty. Each manifest keeps the run's id, target id,
time unit, run salt, axis types and creation time; its `environment` says it was reduced.

Written with `poisson_prove.store.Store` on 2026-10-24 from the two stored runs, and checked to
read back with the same `config_hash`, `seed`, `replicate_index` and `outcome` on every row.
