# The artifact format

Every run `poisson-prove` writes, and every comparison it saves, is written in the Poisson
artifact format: a documented, versioned layout that a dashboard reads, that another tool can
read, and that maps onto a team's own tracker when they want it there.

This page is the format as Prove writes it: every file, every key of every JSON file at every
depth, every column and metric of the table, and every schema string. Nothing Prove writes under
the format is left off this page. The examples are from the quickstart's two runs.

## Three principles

- **Append, never rewrite.** A writer adds files and never changes a file another writer wrote,
  with two named exceptions: a run's own `manifest.json` while that run is still going, and the
  store descriptor's `writers` list.
- **Records are the truth; artifacts are named results over them.** A run record is what a run
  wrote. An artifact is a saved result computed from records and named by a digest of its inputs,
  so saving it twice is one artifact.
- **Local and private by default.** Nothing here needs a network, and no artifact or page holds an
  absolute path, a platform string, a key or content a run captured.

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

`.poisson/` is the one folder every tool shares; every reader of runs ignores it.

A store written before this format (Prove 0.0.1, under its old name) has no `.poisson/`. It is
read as it is, and the first write by this version adds `.poisson/store.json` and touches nothing
else.

### The schemas

Every JSON document the format adds says what it is in its first key: `format` in a descriptor,
`schema` in a result or an event line. The value is a string `poisson.<kind>/<major>` for a shared
kind, or `poisson-prove.<kind>/<major>` for Prove's own. The schemas on this page:

- `poisson.store/1`, `poisson.artifact/1`, `poisson.run-event/1` and `poisson.table/1`, shared;
- `poisson-prove.comparison/1`, `poisson-prove.check/1` and `poisson-prove.chart/1`, Prove's own.

## The store descriptor: `store.json` (`poisson.store/1`)

Written on the first write into a store by any command that writes into it (`sweep` and its
resume, a save, `ui`, a refresh of the dashboard); a command that writes nothing creates nothing.

<!-- docs-check: run -->
```json
{
  "format": "poisson.store/1",
  "created_by": {
    "tool": "poisson-prove",
    "version": "0.2.2"
  },
  "created_at": "2026-11-08T16:13:50Z",
  "writers": [
    {
      "tool": "poisson-prove",
      "version": "0.2.2",
      "first_write": "2026-11-08T16:13:50Z"
    }
  ]
}
```

| key | meaning |
|---|---|
| `format` | `poisson.store/1` |
| `created_by` | the tool that created the descriptor: `tool` (`poisson-prove`) and its `version` |
| `created_at` | when, UTC, `Z` |
| `writers` | one entry per tool and major.minor version that has written into the store: `tool`, `version` (the full version at its first write) and `first_write` (when) |

`writers` is the one key a later writer may append to, through a temporary file renamed in, never
edited in place. Every other key, and every key the writer does not know, is kept as it is.

A reader that finds a newer major format than it knows refuses in one line naming both versions
and the upgrade, `pip install -U poisson-prove`.

## The run record

### `manifest.json`

The run's manifest, as `sweep` writes it: `run_id`, `target_id`, `t_unit`, `run_salt`,
`axis_types`, `backend`, `environment`, `retain_traces_for`, `status` (`partial` or `complete`),
`created_at`, `poisson_prove_version`, `schema_version`, `declared` and, when the sweep was given
`--name`, `name`. A manifest
written by 0.0.1 recorded its version under the old name's key and reads as it is.

The manifest's `environment` keeps the run's provenance (the platform, the Python build, the
target's import path, the sweep as planned); no artifact and no page copies those out. A
quickstart run's manifest, less its `environment`:

<!-- docs-check: run -->
```json
{
  "axis_types": {"task_id": "categorical", "tool_fail_rate": "continuous"},
  "backend": "local",
  "created_at": "2026-11-08T16:13:50.929807Z",
  "declared": {"failures": ["timeout", "violated"], "gates": [], "outcomes": [], "steps": []},
  "poisson_prove_version": "0.2.2",
  "produced_by": {
    "backend": "local",
    "from": [
      {"name": "prove.toml", "sha256": "161f57ddd8996b092934fcda293c31c88a91055444cb37d7097ab99181484994"},
      {"name": "poisson_prove.examples.mock_agent", "sha256": "3f8fb80c7dfc1afa833c7fe2aec6b87384ef4a633d17c404258e20abd35ffba9"}
    ],
    "tool": "poisson-prove",
    "version": "0.2.2"
  },
  "retain_traces_for": null,
  "run_id": "20261108T161350Z-e76a",
  "run_salt": "9eeda186cf334361",
  "schema_version": 1,
  "status": "complete",
  "t_unit": "tool_calls",
  "target_id": "mock-agent"
}
```

`backend` is where the run's rollouts ran: `"local"`, `"modal"` or `"cloud"`. A run made on your
own cloud account records `"cloud"`, and its placement, where and on what it ran, as a `cloud`
object under the manifest's `environment` (the key is `environment.cloud`; no key is named
`placement`):

- the `provider`, `region`, `machine_type`, `nodes`, `slots_per_node`, `image`, `max_vcpus` and
  `idle_minutes` the cluster ran with;
- the price and the money: `usd_per_node_hour`, `price_asof`, `estimate`, `ledger`,
  `ledger_total`, `stop_cost` and `max_cost`;
- `func_cpu`, `func_ram` and `boot_minutes`;
- `account`, masked to its first and last four digits, as the plan shows it;
- `engine`, the cluster software the run was made on, by `name` and `version`:
  `{"name": "burla", "version": "1.8.4"}`.

A run stored by 0.2 or earlier on a cluster of your own has `"burla"` as its `backend`, which is
read as cloud: `runs`, `inspect`, the terminal app and the dashboard show it as `cloud`. Its
manifest is never rewritten, and the placement it recorded stays as stored.

Two optional keys follow, which a reader that does not know them ignores.

#### `produced_by`

`produced_by` (the format's 1.1) says what made the run:

- `version`, the writing tool's version;
- `from`, a list of `{"name", "sha256"}` digests: the sweep spec by its file name and then the
  target's module by its import path, each over its bytes (`sha256` is null for a module with no
  source file);
- and Prove's own `tool` (`poisson-prove`), `backend`, and on a cloud account `bundle` (the
  bundle's `sha256`).

It is written when the run is opened; a resume keeps it and records its own under its `resumed`
event.

#### `stopped_by`

`stopped_by` is `"first_batch_errored"` when a remote sweep stopped because no rollout of its first
stored batch had an outcome; a later segment that completes the run removes it.

### `events.jsonl` (`poisson.run-event/1`)

One JSON object per line, appended and flushed line by line, never rewritten. Every run a 0.1.0
sweep starts or resumes has one; a run written before (every 0.0.1 run) has none, and every view
says so. A reader tolerates a partial last line (a run still writing, or one that died) and reads
every whole line.

| key | meaning |
|---|---|
| `schema` | `poisson.run-event/1` |
| `at` | when, UTC, `Z` |
| `kind` | one of the kinds below, or a tool's own kind named `<tool>.<kind>`, which a reader passes over when it does not know it |
| `detail` | the event's own keys, by kind |

The kinds, in the order a run writes them:

| kind | when | `detail` |
|---|---|---|
| `planned` | first | `run_id`, `rollouts`, `backend`, `cost` |
| `started` | then | `run_id` |
| `progress` | any number, in the middle: at most once a second, plus once just before the segment ends | `done`, `kept`, `errored`, `total`: `kept + errored == done <= total` |
| `note` | any number, in the middle | `sentence` |
| `finished` | last | `status`, `kept` |
| `interrupted` | last, in place of `finished` | `status`, `kept`, and `error` when the run stopped on an error |
| `resumed` | first in a resume's segment | `run_id`, `already_stored`, `rollouts` |

A resume appends `resumed`, then the same middle, then `finished` or `interrupted` again. A run
stopped short, by Ctrl-C, by a cancel or by `--max-rollouts`, ends its segment with `interrupted`
and is resumable. A run's first lines and its last:

<!-- docs-check: skip: four lines of a run's event log, as the store holds them -->
```text
{"schema": "poisson.run-event/1", "at": "2026-11-08T16:13:50.931507Z", "kind": "planned", "detail": {"run_id": "20261108T161350Z-e76a", "rollouts": 1746, "backend": "local", "cost": "$0 (local)"}}
{"schema": "poisson.run-event/1", "at": "2026-11-08T16:13:50.931649Z", "kind": "started", "detail": {"run_id": "20261108T161350Z-e76a"}}
{"schema": "poisson.run-event/1", "at": "2026-11-08T16:13:50.931703Z", "kind": "progress", "detail": {"done": 1, "kept": 1, "errored": 0, "total": 1746}}
{"schema": "poisson.run-event/1", "at": "2026-11-08T16:13:52.008688Z", "kind": "finished", "detail": {"status": "complete", "kept": 1746}}
```

## Saved results

`report` and `serve` save the comparison they show (as will the terminal app); `diff` and `check`
save only with `--save`.

A save prints one detail line, `saved  comparison <id>` (`saved  check <id>`), the id's first
twelve characters; `--json` carries `saved`, the folder relative to the store:

<!-- docs-check: skip: the line a save prints and the key --json carries, from the quickstart's runs -->
```text
  saved  comparison 9235266ae4f7
"saved": ".poisson/artifacts/comparison/9235266ae4f7bb87"
```

A store that cannot be written to does not stop the command: it prints
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

One entry of `files`, a chart's:

<!-- docs-check: run -->
```json
{
  "path": "charts/heatmap-timeout.svg",
  "role": "chart",
  "media_type": "image/svg+xml",
  "data": "charts/heatmap-timeout.json",
  "sha256": "8e6f322b19bfe8b1b6c1816b09afb92e60234256bb8dd6b3b0543423a1f0fb53"
}
```

A save writes into a temporary folder beside its place and renames it in last, so an interrupted
save leaves no artifact. Saving an id that exists writes nothing, and two saves of the same result
at once are one artifact.

### The result: `comparison.json` (`poisson-prove.comparison/1`) and `check.json` (`poisson-prove.check/1`)

The result object as the core computed it: the same document `diff --json` (or `check --json`)
prints, under the format's schema. Its first keys are `schema`, `verdict` and `sentence`; its last
is `next`, the commands to run next. A check carries `passed` and `fail_on` as well, and no tree.

#### The comparison's top level

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

#### Per event: `by_event.<event>`

| key | meaning |
|---|---|
| `event` | the event |
| `kind` | `failure`, `success` or null |
| `n_higher`, `n_lower` | the direction counts |
| `n_worse`, `n_safer`, `n_unchanged` | the judged counts; `n_worse` and `n_safer` are null when the kind is not known |
| `n_holm_higher`, `n_holm_lower`, `n_holm_worse`, `n_holm_safer` | the counts that decided the word |
| `max_mde`, `max_mde_unchanged`, `max_mde_unchanged_cell` | the limits |
| `cause_specific` | true under log-rank |
| `n_unflaggable`, `together_needed`, `replicates_for_lone_flag` | what the design could not flag |
| `cells` | one per condition (below) |

#### Per condition: `by_event.<event>.cells[]`

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

#### The layered report: `omnibus` and `tree`

The tree holds `root`, `grouping`, `fault_lines`, `leaves`, `bound` and `agreement`.

| part | what it is | its keys |
|---|---|---|
| `omnibus` (also `tree.root`) | the root test over the whole grid | `events`, `method`, `scheme` (how arms are exchanged), `q`, `n_cells`, `n_informative_cells`, `n_uninformative_cells`, `n_discordant`, `n_permutations`, `p_floor`, `seed`, `units` (each unit's `config`, `config_hash`, `event`, `n_a`, `n_b`, `events_a`, `events_b`, `delta`), the `location` and `dispersion` statistics per event with `p_location`, `p_dispersion` and `p_omnibus`, `rejects` and the `headline` |
| `tree.grouping` | how the grid was grouped | `key`, `resolved_by`, `requested`, `labels`, `groups` (label to condition hashes), `n_groups`, `group_sizes`, `size_min`, `size_median`, `size_max`, `alpha_floor`, `max_group_mde`, `group_mde`, `n_resolvable_groups` and the rungs `refused` (each with `key`, `rung`, `reason`, `detail`, `next_rung`, `n_groups`, `n_resolvable_groups`, `offered_max_group_mde`) |
| `tree.fault_lines` | tests each group | `tested`, `reason`, `null`, `q`, `n_groups`, `n_degenerate_groups`, `n_rejected_groups`, `rejected_groups`, `mde_basis` and `groups` (each with `label`, `key`, `cells`, `n_cells`, `n_informative_cells`, `n_uninformative_cells`, `n_discordant`, `n_a`, `n_b`, `mde`, `degenerate`, `location`, `dispersion`, `p_location`, `p_dispersion`, `p_group`, `q_group`, `rejects`) |
| `tree.leaves` | tests the cells within each family | `tested`, `reason`, `null`, `q`, `n_families`, `n_tests`, `n_rejected` and `families` (each with `label`, `key`, `n_tests`, `n_rejected`, `rejected`, `mde_median`, `mde_max` and `cells`, each with `config`, `config_hash`, `event`, `group`, `n_a`, `n_b`, `events_a`, `events_b`, `delta`, `p`, `q_within`, `rejects`, `mde`, `mde_note`) |
| `tree.bound` | the bound on the discoveries | `depth_configured`, `depth`, `q`, `delta_star`, `bound`, `discoveries` |
| `tree.agreement` | the digest the layered report is checked by | |

#### A check: `check.json`

A check carries the comparison's top level and `by_event` with `passed` (whether the gate passed)
and `fail_on` (`worse`, `any`, `higher` or `lower`), and neither `omnibus` nor `tree`.

### The long-form table: `conditions.parquet` (`poisson.table/1`)

One row per (event, condition, arm, metric), so the table maps onto any tracker's metrics and onto
a dataframe without reshaping. The nine key columns come first, in this order:

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

The metrics, from each condition's row of the result:

- per arm: `n`, `events`, `rate`, `share`, `share_lo` and `share_hi` (the share and its bounds
  carry the Wilson level);
- for the pair, under `both`: `delta`, `stat`, `p`, `q`, `q_holm`, `ci_lo` and `ci_hi` (at the
  interval's level), `mde_rise` and `mde_fall` (at the limit's level), `mde_rise_verdict`,
  `mde_fall_verdict` and `p_min`.

Five rows of one condition, less `artifact_id` and `condition`:

<!-- docs-check: skip: rows of a saved table from the quickstart's runs, not a command -->
```text
event    condition_hash    arm   metric    value                 note             level
timeout  1ad7c42d72bbb09d  a     rate      0.04123711340206186   null             null
timeout  1ad7c42d72bbb09d  b     rate      0.0                   null             null
timeout  1ad7c42d72bbb09d  both  delta     -0.041237113402061855 null             null
timeout  1ad7c42d72bbb09d  both  mde_rise  0.1184                null             0.002777777777777778
timeout  1ad7c42d72bbb09d  both  mde_fall  null                  none detectable  0.002777777777777778
```

### The charts (`poisson-prove.chart/1`)

A saved comparison carries its charts as SVG, each drawn by Prove from the data beside it:

- per event: `charts/heatmap-<event>.svg`, `charts/differences-<event>.svg` and
  `charts/limits-<event>.svg`;
- per condition and event: `charts/<condition hash>/incidence-<event>.svg`.

Each chart's data is the JSON file of the same name beside it, listed in the descriptor as the
chart's `data`:

| key | meaning |
|---|---|
| `schema` | `poisson-prove.chart/1` |
| `kind` | `heatmap`, `differences`, `limits` or `incidence` |
| `event` | the event drawn |
| `condition` | the condition's hash for an incidence chart; null for a chart over every condition |
| `title`, `caption` | what the chart shows, in the words its page and its SVG's own title and description carry |
| `columns`, `rows` | the data as a table: the column names (the axes' names among them), and one row per point |

What each kind's rows hold:

- the heatmap's: each condition's axis values, both shares, the change, q and the verdict;
- the differences': the verdict, the change and the interval's bounds and q;
- the limits': the verdict, each direction's limit (or why it has none), the threshold and whether
  the condition could tell;
- the incidence's: the time and each run's cumulative incidence by then.

An incidence chart's data, whole:

<!-- docs-check: run -->
```json
{
  "schema": "poisson-prove.chart/1",
  "event": "timeout",
  "condition": "1ad7c42d72bbb09d",
  "kind": "incidence",
  "title": "Cumulative incidence of timeout, each run: task_id checkout · tool_fail_rate 0.3",
  "caption": "The share of each run's episodes in task_id checkout · tool_fail_rate 0.3 that had ended in timeout by each time, before in grey and after in violet, to the horizon (20 tool_calls).",
  "columns": ["t", "before", "after"],
  "rows": [[0.0, 0.0, 0.0], [20.0, 0.04123711340206186, 0.0]]
}
```

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

- Adding an optional key, a kind or a column is a minor change a reader ignores when it does not
  know it.
- Removing or renaming one, or changing its meaning, is a new major.
- A reader refuses a newer major than it knows in one line naming both versions and how to
  upgrade.

## The dashboard's place in the store

`.poisson/ui/` holds the static dashboard: fixed files copied from the package (`style.css`,
`ui.js`) and pages built from the records and the artifacts.

It is derived: deleting it loses nothing, `poisson-prove ui` builds it, and every command that
writes a run or saves a comparison refreshes a dashboard the store already has.

Each page's address is relative to `ui/` (`comparisons/<id>.html`), and a later local server
serves the same addresses under its root.
