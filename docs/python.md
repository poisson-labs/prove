# Python API

Prove's public Python surface: what a rollout imports, what reads runs from a store, and the
statistics its comparisons are computed with. Everything listed here is in its module's
`__all__`, has a docstring and type annotations, and changes only with a CHANGELOG entry.
Everything else is private, whatever its spelling.

The examples run from a folder whose `./prove-runs` holds a pair of runs, as the quickstart
leaves it (`poisson-prove init --example`, then its two sweeps).

<!-- docs-check: setup quickstart -->

## `poisson_prove`

What a rollout needs.

- `Episode`: one episode's ending, its time and its horizon, with optional `meta`.
- `EpisodeValidationError`: an `Episode` that cannot be one.
- `Rollout`: the shape of a rollout, a function `(cfg, seed) -> Episode`.
- `record`: record a traced step inside a rollout.
- `step`: name a step of a rollout, for the trace.
- `__version__`: the installed version of Prove, as a string such as `0.1.1`.

<!-- docs-check: run -->
```python
from poisson_prove import Episode, Rollout, __version__, record, step

def rollout(cfg, seed):
    return Episode(outcome="completed", t=3.0, horizon=20.0)

print(__version__, rollout({"task_id": "search"}, 0).outcome)
```

## `poisson_prove.compare`

Compare two runs from Python, getting the result objects the command line prints.

- `diff`: compare two runs; the result's `to_json()` is what `poisson-prove diff --json`
  prints, under the comparison's own schema.
- `check`: a gate over two runs; the result's `to_json()` is what `poisson-prove check --json`
  prints, under the check's own schema.
- `runs`: every run in a store, newest first, named and numbered.
- `resolve`: the id of the run a word names: `latest`, `previous`, `#1`, a name or an id.
- `Comparison`: the result of `diff`: `verdict`, `sentence`, `method`, `method_chosen`, `rows`,
  `verdict_limit`, `fragility`, `peeking`, `errors_differ` and the rest of its JSON.
- `CheckResult`: the result of `check`, with `passed` and `fail_on`.
- `RunInfo`: one run of `runs`, with `run_id` and `run_name`.
- `Refusal`: what every function raises when it refuses; its text is the command line's sentence.

A `Comparison`, and so a `CheckResult`, builds its document and its tree the first time something
reads them. Get its JSON with `to_json()`: `json.dumps` on the result, or on its `payload` before
anything has read it, is not supported. It pickles whether or not it has been read, building
itself in full first, and the unpickled copy is equal to it.

<!-- docs-check: run -->
```python
from poisson_prove import compare

result = compare.diff("prove-runs")
print(result.verdict, result.method, result.method_chosen)
for row in result.rows[:3]:
    print(row["event"], row["config"], row["delta"], row["ci_lo"], row["ci_hi"])
```

<!-- docs-check: run -->
```python
from poisson_prove import compare

gate = compare.check("prove-runs", "previous", "latest", events=["violated"], fail_on="any")
print(gate.verdict, gate.passed)
```

<!-- docs-check: run -->
```python
from poisson_prove import compare

for run in compare.runs("prove-runs"):
    print(run.run_name, run.run_id)
print(compare.resolve("prove-runs", "latest"))
try:
    compare.resolve("prove-runs", "no run has this name")
except compare.Refusal as refused:
    print("refused:", refused)
```

## `poisson_prove.stats`

The statistics Prove's comparisons are computed with: the same numbers, given the same counts or
times.

- `wilson`: the Wilson score interval on k events in n trials at the level asked for.
- `WilsonInterval`: what `wilson` returns: `lo`, `hi`, `level`, `z` and `method`.
- `WILSON_LEVEL`: the level of every share's interval a surface shows, 0.95 unless changed.
- `POWER`: the power every detection limit is stated at, 0.8, said as "caught 4 times in 5".
- `kaplan_meier`: the Kaplan-Meier survival curve, with Greenwood's variance.
- `KMCurve`: what `kaplan_meier` returns: the event times, survival, variance and counts.
- `aalen_johansen`: each event's cumulative incidence when several events compete.
- `CIFCurve`: what `aalen_johansen` returns: the event times and each event's incidence.
- `bh`: Benjamini and Hochberg's adjusted p-values, the flags' rule.
- `holm`: Holm's step-down adjusted p-values, the verdict's rule.
- `interval_rd`: Miettinen and Nurminen's score interval on a change between two samples.
- `interval_rd_paired`: Tango's score interval on a change over matched pairs.
- `mde_two_proportion`: the smallest rise a normal-approximation test would catch.
- `fisher_test`: Fisher's exact test on two separate samples.
- `mcnemar_test`: the paired test on matched pairs (exact McNemar).
- `logrank_test`: the two-sample log-rank test of the cause-specific hazard.

<!-- docs-check: run -->
```python
import numpy as np
from poisson_prove import stats

print(stats.wilson(3, 20), stats.wilson(3, 20, level=0.9).z, stats.WILSON_LEVEL, stats.POWER)
print(stats.fisher_test(11, 30, 2, 30), stats.mcnemar_test(9, 0))
t_a, t_b = np.array([1.0, 2.0, 3.0, 4.0]), np.array([2.0, 3.0, 5.0, 6.0])
seen = np.array([True, True, False, True])
print(stats.logrank_test(t_a, seen, t_b, seen))
p = np.array([0.001, 0.02, 0.04, 0.3])
print(stats.bh(p, 0.05), stats.holm(p, 0.05))
print(stats.interval_rd(11, 30, 2, 30, alpha=0.05), stats.interval_rd_paired(9, 0, 30, alpha=0.05))
print(stats.mde_two_proportion(0.3, 194, 194, alpha=0.05, power=0.8))
curve = stats.kaplan_meier(t_a, seen)
ended = np.array(["violated", "timeout", "completed", "violated"], dtype=object)
incidence = stats.aalen_johansen(t_a, ended, ["violated", "timeout"])
print(curve.survival, incidence.cif["violated"])
```

## `poisson_prove.store`

Reading runs from Python.

- `Store`: a folder of runs; reads and writes them.
- `RunManifest`: a run's manifest: its id, target, salt, axes, status and what it recorded.
- `EpisodeRecord`: one stored episode.
- `RunTally`: how a run's rows divide into rows with an outcome and rows without one.
- `config_hash`: the digest of a condition, the key every stored row carries.
- `StoreError`: a store that cannot be read or written as asked.
- `SchemaMismatch`: a run written in a schema this Prove does not read.

## `poisson_prove.trace`

Building and reading traces. Its names, as its `__all__` lists them: `Span`, `Trace`,
`Declaration`, `SpanHandle`, `Collector`, `collect`, `record`, `step`, `from_otel`,
`from_litellm`, `merge`, `split`, `assemble`, `finalize`, `truncate_observations`,
`TraceValidationError`, and these constants:

- `SCHEMA`: the schema string every stored trace carries.
- `KINDS`: the kinds a span may have: `llm`, `tool`, `retrieval`, `db`, `http`, `agent` and `other`.
- `CONTENT_KEYS`: the span keys that hold captured content, dropped when content is not kept.
- `OBSERVATION_KEYS`: the span keys that hold what a step observed, stored apart from the envelope.
- `OBSERVATION_ROUTING_BYTES`: the size over which an attribute is stored as an observation.
- `TRUNCATED_KEY`: the key a cut observation's wrapper carries.
- `LOGPROBS_KEY`: the attribute that holds a model call's token log-probabilities.
- `GATE`: the attribute that marks a step as a gate.
- `OUTCOME_BY`: the attribute that names what decided an episode's outcome.
- `SOURCES`: the places a trace can come from, such as `record` and `otel`.
- `DROP_REASONS`: the reasons a span can be left out of a stored trace.
- `ATTRIBUTE_ALIASES`: the map from other tools' attribute names to Prove's.
- `ALIAS_MAP_VERSION`: the version of that map, recorded with each trace.
- `OTEL_KIND_MAP`: the map from OpenTelemetry span kinds to Prove's kinds.
- `OTEL_SEMCONV_VERSION`: the OpenTelemetry semantic conventions version the map follows.

## `poisson_prove.steps`

- `declaration_check`: a run's declared steps, outcomes and gates against its stored spans.
- `DeclarationCheck`: what `declaration_check` returns.

## `poisson_prove.chaos`

Fault injection inside a rollout: `ChaosError`, `ChaosSpec`, `ChaosStatus`, `FaultRecord`,
`fault_names`, `position`, `install` and `injecting`.

## `poisson_prove.otel`

Stamping spans in a traced agent (needs the `agent` extra).

- `episode`: stamp every span opened inside it with the run and episode.
- `EpisodeStamper`: the span processor that does the stamping.
- `RUN_ID_KEY`: the attribute that carries the run's id on a stamped span.
- `EPISODE_KEY`: the attribute that carries the episode's id on a stamped span.

## `poisson_prove.examples.mock_agent`

The keyless example: `rollout`, a mock tool-using agent, and `rollout_patched`, the same agent
retrying a failed call once.

## Private modules

These are private and may change in any release: `executor`, `executor_modal`, `executor_burla`,
`sampler`, `diff`, `tree`, `report`, `viewer`, `plain`, `paired`, `capture`, `chaos_catalog`,
`survival` (its functions are public through `stats`), `cli`, `_compat`, `_resolve`,
`_burla_submit`, and `core`, the core every face sits on.
