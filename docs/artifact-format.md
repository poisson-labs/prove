# The artifact format

Every run `poisson-prove` writes, and every comparison it saves, is written in the Poisson
artifact format: a documented, versioned layout that a dashboard reads, that another tool can
read, and that maps onto a team's own tracker when they want it there. This page is the format
as Prove writes it: every file, every key of every JSON file at every depth, every column and
metric of the table, and every schema string. Nothing Prove writes under the format is left off
this page.

Three principles hold throughout. **Append, never rewrite:** a writer adds files and never
changes a file another writer wrote, with two named exceptions (a run's own `manifest.json`
while that run is still going, and the store descriptor's `writers` list). **Records are the
truth; artifacts are named results over them:** a run record is what a run wrote, an artifact is
a saved result computed from records and named by a digest of its inputs, so saving it twice is
one artifact. **Local and private by default:** nothing here needs a network, and no artifact or
page holds an absolute path, a platform string, a key or content a run captured.

## The layout of a store

<!-- docs-check: skip: a picture of a store's folders, not a command -->
```text
<store>/
  .poisson/
    store.json                      the store descriptor
    artifacts/comparison/<id>/      a saved comparison
      artifact.json                   its descriptor
      comparison.json                 the result
      conditions.parquet              the long-form table
      charts/heatmap-<event>.svg      the verdict heatmap, with heatmap-<event>.json beside it
      charts/differences-<event>.svg  each condition's change and interval
      charts/limits-<event>.svg       the limits against the threshold
      charts/<condition hash>/incidence-<event>.svg   each run's cumulative incidence
    artifacts/check/<id>/           a saved check: artifact.json, check.json, conditions.parquet
    ui/                             the static dashboard (derived; `ui` builds it, a writing command refreshes it)
  <run id>/                         a run record
    manifest.json
    events.jsonl
    episodes/                       the run's rows, as Parquet parts
```

`.poisson/` is the one folder every tool shares; every reader of runs ignores it. A store
written before this format (Prove 0.0.1, under its old name) has no `.poisson/`: it is read as
it is, and the first write by this version adds `.poisson/store.json` and touches nothing else.

Every JSON document the format adds says what it is in its first key: `format` in a descriptor,
`schema` in a result or an event line, a string `poisson.<kind>/<major>` for a shared kind or
`poisson-prove.<kind>/<major>` for Prove's own. The schemas on this page are
`poisson.store/1`, `poisson.artifact/1`, `poisson.run-event/1`, `poisson.table/1`,
`poisson-prove.comparison/1`, `poisson-prove.check/1` and `poisson-prove.chart/1`.

## The store descriptor: `store.json` (`poisson.store/1`)

Written on the first write into a store by any command that writes into it (`sweep` and its
resume, a save, `ui`, a refresh of the dashboard); a command that writes nothing creates nothing.

| key | meaning |
|---|---|
| `format` | `poisson.store/1` |
| `created_by` | the tool that created the descriptor: `tool` (`poisson-prove`) and its `version` |
| `created_at` | when, UTC, `Z` |
| `writers` | one entry per tool and major.minor version that has written into the store: `tool`, `version` (the full version at its first write) and `first_write` (when) |

`writers` is the one key a later writer may append to, through a temporary file renamed in,
never edited in place; every other key, and every key the writer does not know, is kept as it
is. A reader that finds a newer major format than it knows refuses in one line naming both
versions and the upgrade, `pip install -U poisson-prove`.

## The run record

### `manifest.json`

The run's manifest, as `sweep` writes it: `run_id`, `target_id`, `t_unit`, `run_salt`,
`axis_types`, `backend`, `environment`, `retain_traces_for`, `status` (`partial` or `complete`),
`created_at`, `poisson_prove_version`, `schema_version`, `declared` and `name`. A manifest written
by 0.0.1 recorded its version under the old name's key and reads as it is. The manifest's
`environment` keeps the run's provenance (the platform, the Python build, the target's import
path, the sweep as planned); no artifact and no page copies those out.

### `events.jsonl` (`poisson.run-event/1`)

One JSON object per line, appended and flushed line by line, never rewritten: every run a
0.1.0 sweep starts or resumes has one; a run written before (every 0.0.1 run) has none, and
every view says so. A reader tolerates a partial last line (a run still writing, or one that
died) and reads every whole line.

| key | meaning |
|---|---|
| `schema` | `poisson.run-event/1` |
| `at` | when, UTC, `Z` |
| `kind` | one of the kinds below, or a tool's own kind named `<tool>.<kind>`, which a reader passes over when it does not know it |
| `detail` | the event's own keys, by kind |

The kinds, in the grammar a run follows: `planned` (`run_id`, `rollouts`, `backend`, `cost`),
then `started` (`run_id`), then any number of `progress` (`done`, `kept`, `errored`, `total`:
`kept + errored == done <= total`; at most once a second, plus once just before the segment
ends) and `note` (`sentence`), then `finished` (`status`, `kept`) or `interrupted` (`status`,
`kept`, and `error` when the run stopped on an error). A resume appends `resumed` (`run_id`,
`already_stored`, `rollouts`), then the same middle, then `finished` or `interrupted` again. A
run stopped short, by Ctrl-C, by a cancel or by `--max-rollouts`, ends its segment with
`interrupted` and is resumable.

## Saved results

`report` and `serve` save the comparison they show (as will the terminal app); `diff` and
`check` save only with `--save`. A save prints one detail line, `saved  comparison <id>` (`saved  check <id>`),
the id's first twelve characters; `--json` carries `saved`, the folder relative to the store. A
store that cannot be written to does not stop the command: it prints
`note: the comparison was not saved: <the system's words>` and goes on.

### The descriptor: `artifact.json` (`poisson.artifact/1`)

| key | meaning |
|---|---|
| `format` | `poisson.artifact/1` |
| `kind` | `comparison` or `check` |
| `id` | the folder's name: the first 16 hex characters of the SHA-256 of the canonical JSON (sorted keys, no spaces, UTF-8) of the kind, the tool, its major.minor version, the `inputs` and the result-changing settings (`settings` less `method_chosen`). Same inputs and result-changing settings, same artifact |
| `tool`, `tool_version` | `poisson-prove` and its full version |
| `created_at` | when the result was saved, UTC |
| `inputs` | `runs`: the two run ids, before then after |
| `settings` | what changes the result, and how it was asked for: `method` as resolved, `method_chosen` (`default` or `named`; recorded, not in the id), `events` (each with `name` and `kind`: `failure`, `success` or null, sorted by name), `q`, `power`, `horizon`; for a comparison the tree's `by` (the axis asked for, null when none), `depth`, `permutations`, `seed` and `max_group_mde`; for a check `fail_on` |
| `summary` | the result's `verdict` and `sentence`, and `detail`: the verdict block's detail lines as `[label, text]` pairs, the facts every face prints under the verdict (the method, the runs, the trades, the verdict rule, the limits, the intervals, the fragility, any peeking caveat and any errored-episodes warning) |
| `files` | every file in the folder but the descriptor itself, each with its `path`, `role` (`result`, `table`, `chart`), `media_type`, `schema` where it has one, `sha256`, and for a chart `data`, the path of the JSON file holding what it was drawn from |

A save writes into a temporary folder beside its place and renames it in last, so an interrupted
save leaves no artifact; saving an id that exists writes nothing, and two saves of the same result
at once are one artifact.

### The result: `comparison.json` (`poisson-prove.comparison/1`) and `check.json` (`poisson-prove.check/1`)

The result object as the core computed it: the same document `diff --json` (or `check --json`)
prints, under the format's schema. Its first keys are `schema`, `verdict` and `sentence`; its last
is `next`, the commands to run next. A check carries `passed` and `fail_on` as well, and no tree.

**The comparison, top level.**

| key | meaning |
|---|---|
| `method`, `method_chosen` | the test (`fisher_bh`, `mcnemar_bh` or `logrank_bh`) and whether it was the default for the pair or named |
| `seed_identity_match`, `unpaired_analysis` | whether the runs share their seeds, and whether an unpaired test was run on paired runs |
| `q` | the false discovery rate the flags are controlled at |
| `t_unit`, `horizon` | the time unit, and the horizon the comparison was read at |
| `n_tests` | the size of the family: every (condition, event) tested |
| `n_not_comparable`, `dropped_a`, `dropped_b` | conditions that could not be compared, and those only one run had |
| `truncated` | rows cut at the horizon |
| `inferred`, `non_event`, `events` | whether the events were defaulted (to the failures and successes the runs declare, else to every outcome but the most frequent), that most frequent outcome when it was used (null otherwise), and the events compared |
| `by_event` | per event, its counts and its conditions (below) |
| `trades` | conditions where one event got safer and another worse: `config`, `config_hash`, `safer_events`, `worse_events` |
| `coverage` | per condition, the rows each run had, those with no outcome, whether it is `comparable` and, when not, the `cause`: `config`, `config_hash`, `rows_a`, `rows_b`, `no_outcome_a`, `no_outcome_b`, `comparable`, `cause` |
| `intervals` | per condition and event, the interval on the change: `event`, `config`, `config_hash`, `ci_lo`, `ci_hi`, `basis` |
| `interval_level`, `interval_rule`, `alpha_star` | the level every interval on a change is stated at, its rule (`benjamini-yekutieli` when anything is flagged, `bonferroni` when nothing is) and the per-test level it rests on |
| `n_rejected`, `n_interval_only`, `n_verdict_only`, `n_flagged_only` | conditions flagged, flagged by their interval alone, counted by the verdict alone, and flagged at the false discovery rate without counting at the family-wise level |
| `threshold`, `threshold_source` | the change the verdict asks about, and where it came from: `recorded` by both runs, `smaller` when the two runs recorded different thresholds and the smaller one was taken, or `default` |
| `comparison_verdict`, `flag_rule`, `verdict_rule` | the verdict word, the rule a condition's flag follows (`benjamini-hochberg`) and the rule the verdict follows (`holm`) |
| `verdict_limit` | under `no significant change`, the largest limit the verdict read; null otherwise |
| `fragility`, `fragility_flips`, `fragility_note`, `fragility_exact` | how many stored outcomes would change the word, which (`config_hash`, `event`, `run`, `replicate_index`, `to`), why there is none, and whether the search was exhaustive |
| `peeking` | runs whose tests do not hold their error rates (`run_id`, `run_name`, `reason`): a partial run, or one resumed after a comparison of it was read |
| `errors_differ` | conditions whose errored episodes differ between the runs: `config`, `config_hash`, `errored_a`, `rows_a`, `errored_b`, `rows_b`, `p` |
| `headline`, `trade_line` | the counts in words, and the trade line when there is one |
| `omnibus`, `tree` | the layered report over the comparison (below); a check carries neither |

**Per event (`by_event.<event>`).** `event`, `kind` (`failure`, `success` or null), the
direction counts `n_higher` and `n_lower`, the judged counts `n_worse` and `n_safer` (null when
the kind is not known), `n_unchanged`, the counts that decided the word `n_holm_higher`,
`n_holm_lower`, `n_holm_worse`, `n_holm_safer`, the limits `max_mde`, `max_mde_unchanged` and
`max_mde_unchanged_cell`, `cause_specific` (true under log-rank), and what the design could not
flag: `n_unflaggable`, `together_needed`, `replicates_for_lone_flag`; then `cells`, one per
condition.

**Per condition (`by_event.<event>.cells[]`).**

| key | meaning |
|---|---|
| `config`, `config_hash` | the condition's axis values and their 16-hex digest |
| `n_a`, `n_b`, `events_a`, `events_b`, `rate_a`, `rate_b` | each run's episodes, those that ended in the event, and the rates the test compared |
| `share_a`, `share_b` | each run's share of episodes ending in the event (under `mcnemar_bh`, of the condition's matched pairs, as `delta` is) with its Wilson interval: `value`, `lo`, `hi`, `level`, `method`; `share_a_differs`, `share_b_differs` mark a share that is not its rate (a run censored before the horizon) |
| `delta` | the change, after minus before |
| `pairs`, `n01`, `n10` | the pairs a paired test read, and the discordant ones among them: `n01` where only the after run had the event, `n10` where only the before run had it (null under the other tests) |
| `stat`, `p`, `q`, `q_holm`, `holm` | the test statistic, its p, the Benjamini-Hochberg q, Holm's adjusted p, and whether the condition counted for the verdict |
| `direction`, `direction_note`, `verdict` | which way the rate moved, why no direction is given, and the condition's word (`worse`, `safer`, `higher`, `lower`, `unchanged`) |
| `ci_lo`, `ci_hi`, `ci_level`, `ci_method` | the interval on the change, its level and its method (`tango` for the paired test, `miettinen-nurminen` otherwise) |
| `mde_rise`, `mde_fall`, `mde_rise_note`, `mde_fall_note` | the smallest rise and the smallest fall this condition alone would be flagged for, each with the reason when it has none (`no room`, `none detectable`) |
| `mde_rise_verdict`, `mde_fall_verdict` | the same limits at the verdict's level |
| `mde`, `mde_note`, `mde_test`, `mde_basis`, `mde_level`, `mde_family`, `mde_power`, `mde_anchor`, `mde_hr`, `mde_moves_with` | the limit as one number where the two agree, its note, the test, basis, level, family and power it was computed at, where it was anchored (`observed baseline`), the hazard ratio form under log-rank, and what moved with it |
| `p_min`, `flaggable` | the smallest p this condition could reach, and whether that is under the flag's level |
| `competing_shift` | under log-rank, the other outcomes whose share changed too |

**The layered report (`omnibus` and `tree`).** The tree holds `root`, `grouping`, `fault_lines`,
`leaves`, `bound` and `agreement`. `omnibus` (also `tree.root`) is the root test
over the whole grid: `events`, `method`, `scheme` (how arms are exchanged), `q`, `n_cells`,
`n_informative_cells`, `n_uninformative_cells`, `n_discordant`, `n_permutations`, `p_floor`,
`seed`, `units` (each unit's `config`, `config_hash`, `event`, `n_a`, `n_b`, `events_a`,
`events_b`, `delta`), the `location` and `dispersion` statistics per event with `p_location`,
`p_dispersion` and `p_omnibus`, `rejects` and the `headline`. `tree.grouping` is how the grid was
grouped: `key`, `resolved_by`, `requested`, `labels`, `groups` (label to condition hashes),
`n_groups`, `group_sizes`, `size_min`, `size_median`, `size_max`, `alpha_floor`, `max_group_mde`,
`group_mde`, `n_resolvable_groups` and the rungs `refused` (each with `key`, `rung`, `reason`,
`detail`, `next_rung`, `n_groups`, `n_resolvable_groups`, `offered_max_group_mde`). `tree.fault_lines`
tests each group: `tested`, `reason`, `null`, `q`, `n_groups`, `n_degenerate_groups`,
`n_rejected_groups`, `rejected_groups`, `mde_basis` and `groups` (each with `label`, `key`,
`cells`, `n_cells`, `n_informative_cells`, `n_uninformative_cells`, `n_discordant`, `n_a`, `n_b`,
`mde`, `degenerate`, `location`, `dispersion`, `p_location`, `p_dispersion`, `p_group`, `q_group`,
`rejects`). `tree.leaves` tests the cells within each family: `tested`, `reason`, `null`, `q`,
`n_families`, `n_tests`, `n_rejected` and `families` (each with `label`, `key`, `n_tests`,
`n_rejected`, `rejected`, `mde_median`, `mde_max` and `cells`, each with `config`, `config_hash`,
`event`, `group`, `n_a`, `n_b`, `events_a`, `events_b`, `delta`, `p`, `q_within`, `rejects`,
`mde`, `mde_note`). `tree.bound` is the bound on the discoveries: `depth_configured`, `depth`,
`q`, `delta_star`, `bound`, `discoveries`. `tree.agreement` is the digest the layered report is
checked by.

**A check (`check.json`)** carries the comparison's top level and `by_event` with `passed`
(whether the gate passed) and `fail_on` (`worse`, `any`, `higher` or `lower`), and neither
`omnibus` nor `tree`.

### The long-form table: `conditions.parquet` (`poisson.table/1`)

One row per (event, condition, arm, metric), so the table maps onto any tracker's metrics and
onto a dataframe without reshaping. The nine key columns come first, in this order:

| column | type | meaning |
|---|---|---|
| `artifact_id` | string | the artifact the row belongs to |
| `event` | string | the event |
| `condition` | string | the condition's canonical JSON |
| `condition_hash` | string | its 16-hex digest |
| `arm` | string | `a` (before), `b` (after) or `both` |
| `metric` | string | the metric's name |
| `value` | double | the value; null with `note` set when there is none |
| `note` | string | why a value is null: `no room`, `none detectable`, `not computed`, or no episode with an outcome |
| `level` | double | the level of an interval bound or a limit, where the metric has one |

The metrics, from each condition's row of the result: per arm `n`, `events`, `rate`, `share`,
`share_lo` and `share_hi` (the share and its bounds carry the Wilson level); for the pair, under
`both`, `delta`, `stat`, `p`, `q`, `q_holm`, `ci_lo` and `ci_hi` (at the interval's level),
`mde_rise` and `mde_fall` (at the limit's level), `mde_rise_verdict`, `mde_fall_verdict` and
`p_min`.

### The charts (`poisson-prove.chart/1`)

A saved comparison carries its charts as SVG, each drawn by Prove from the data beside it:
`charts/heatmap-<event>.svg`, `charts/differences-<event>.svg` and `charts/limits-<event>.svg`
per event, and `charts/<condition hash>/incidence-<event>.svg` per condition and event. Each
chart's data is the JSON file of the same name beside it, listed in the descriptor as the chart's
`data`:

| key | meaning |
|---|---|
| `schema` | `poisson-prove.chart/1` |
| `kind` | `heatmap`, `differences`, `limits` or `incidence` |
| `event` | the event drawn |
| `condition` | the condition's hash for an incidence chart; null for a chart over every condition |
| `title`, `caption` | what the chart shows, in the words its page and its SVG's own title and description carry |
| `columns`, `rows` | the data as a table: the column names (the axes' names among them), and one row per point |

The heatmap's rows hold each condition's axis values, both shares, the change, q and the verdict;
the differences' rows the verdict, the change and the interval's bounds and q; the limits' rows
the verdict, each direction's limit (or why it has none), the threshold and whether the condition
could tell; the incidence's rows the time and each run's cumulative incidence by then.

## Export to MLflow and W&B

No exporter is built in this version. Each kind maps onto a run in either tracker, and every key
the mapping needs is in the format already:

| Poisson | MLflow | W&B |
|---|---|---|
| a run record | a run: `run_name` the run's name, params the manifest's settings and conditions, tags `poisson.tool` and `poisson.run_id` | a run: `name` the run's name, `config` the same settings |
| `events.jsonl` | an artifact file of the run | an artifact file of the run |
| a comparison | a run of its own, tagged `poisson.kind=comparison`, with the two run ids as params and the verdict as a tag; the long-form table as an artifact and as metrics keyed `<event>/<condition_hash>/<metric>` | a run of its own, the long-form table as a `wandb.Table`, the verdict in the summary |
| a check | a run of its own, tagged `poisson.kind=check`, with `passed` and `fail_on` as tags and the table as an artifact | a run of its own with the table as a `wandb.Table` and `passed` in the summary |
| a chart | an artifact file (the SVG, with its data file) | a `wandb.Html` of the SVG, or an image |

## Versioning

`poisson.store/1`, `poisson.artifact/1`, `poisson.run-event/1`, `poisson.table/1` and Prove's
`poisson-prove.comparison/1`, `poisson-prove.check/1` and `poisson-prove.chart/1` are version 1.
Adding an optional key, a kind or a column is a minor change a reader ignores when it does not
know it; removing or renaming one, or changing its meaning, is a new major, and a reader refuses a
newer major than it knows in one line naming both versions and how to upgrade.

## The dashboard's place in the store

`.poisson/ui/` holds the static dashboard: fixed files copied from the package (`style.css`,
`ui.js`) and pages built from the records and the artifacts. It is derived: deleting it loses
nothing, `poisson-prove ui` builds it, and every command that writes a run or saves a comparison
refreshes a dashboard the store already has. Each page's address is relative to `ui/`
(`comparisons/<id>.html`), and a later local server serves the same addresses under its root.
