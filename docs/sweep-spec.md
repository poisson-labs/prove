# The sweep spec

A sweep spec is a TOML file, `prove.toml` by default, that says what to run, under which
conditions, and how many times each. `poisson-prove init --example` writes a working one, and
`poisson-prove init --target pkg.module:rollout` a commented template. This page is every key and
table it can hold. Every key is checked when the spec is read, before anything is imported or
run: a key the spec does not have is refused with its line and the nearest key it does have.

A whole spec, with the optional tables:

<!-- docs-check: run -->
~~~toml
target = "my_rollout:rollout"
target_id = "support-bot"
t_unit = "steps"
replicates = 200
retain_traces_for = ["unresolved", "timeout"]

[axes.ticket]
type = "categorical"
values = ["refund", "password", "shipping"]

[axes.temperature]
type = "continuous"
values = [0.0, 0.7]

[declare]
outcomes = ["resolved", "unresolved", "timeout"]
failures = ["unresolved", "timeout"]
successes = ["resolved"]

[capture]
instrument = ["openai"]
content = false
max_observation_bytes = 16384
~~~

## The top level

| key | type | default | what it is |
|---|---|---|---|
| `target` | string, `module:function` | no default; `--target` gives it on the command line | the rollout, imported with the spec's folder first on the import path. A `--target` wins over it. |
| `target_id` | string | no default, required | the name the runs go by: a run is named by it, the date and a letter |
| `t_unit` | string | no default, required | the unit an episode's `t` and `horizon` are counted in: `steps`, `tool_calls`, `seconds` |
| `replicates` | integer, 1 or more | no default, required | episodes per condition; `--replicates` overrides it for one run |
| `retain_traces_for` | list of outcome names | every trace is kept | keep the stored trace only of episodes that ended in one of these outcomes (an errored episode always keeps its trace) |
| `[axes.<name>]` | table, one per axis | at least one is required | a condition is one value of every axis; the grid is every combination |
| `scenarios` | array of tables, each headed by the table name in double brackets | none | conditions added to the grid as written, one table each, with any keys |
| `[declare]` | table | none | what the run expects: its outcomes and their kinds, its steps and gates |
| `[capture]` | table | no capture | store the OpenTelemetry spans of a traced agent with each episode |
| `[chaos]` | table | no faults | inject a fault into the target's HTTP calls |
| `[modal]` | table | Modal's defaults below | how a `--backend modal` sweep runs |
| `[burla]` | table | required for `--backend burla` | how a `--backend burla` sweep runs |

A spec has no `name`: a run is named on the command line with `sweep --name`.

## `[axes.<name>]`

One table per axis, in the order the conditions are listed. The grid is every combination of the
axes' values, the last axis varying fastest; the cases your agent runs are one axis, so a
condition runs one case ([Your own agent](your-own-agent.md#one-case-per-condition) says why).

| key | type | default | what it is |
|---|---|---|---|
| `type` | `"categorical"` or `"continuous"` | no default, required | `continuous` for numbers whose order means something (a rate, a temperature), `categorical` for anything else |
| `values` | non-empty list | no default, required | the axis's values, passed to the rollout as they are written (`5` stays an integer) |

## `scenarios`

Each `scenarios` table is one more condition, with whatever keys it holds, added after the
grid. A scenario equal to a grid condition is run once. Use it for a few hand-picked conditions
the grid does not have:

<!-- docs-check: run -->
~~~toml
[[scenarios]]
ticket = "refund"
temperature = 1.2
~~~

## `[declare]`

What the run expects of itself, recorded in its manifest. It is not part of what makes two
sweeps the same sweep, so a run that declares and one that does not still share their seeds when
paired.

| key | type | default | what it is |
|---|---|---|---|
| `outcomes` | list of names | none | every outcome the rollout can return; `diff` refuses two runs that declare different outcomes |
| `failures` | list of outcome names | none | outcomes that count against the agent: a rise of one is `worse` |
| `successes` | list of outcome names | none | outcomes that count for it: a rise of one is `safer` |
| `steps` | list of step names | none | the steps the agent is expected to run, checked against its trace |
| `gates` | list of step names, among `steps` | none | the steps that are checks the agent's control flow consults |

Refused: a name in both `failures` and `successes`; a failure or success that is not among
`outcomes`, when `outcomes` is given; a gate that is not among `steps`; a name listed twice; and a
table that declares nothing. Without `failures` or `successes` a comparison says `higher` and `lower` for
an outcome, never `worse` and `safer`, and the plan says so. What `steps` and `gates` report is in
[What capture stores](what-capture-stores.md).

## `[capture]`

Turns on OpenTelemetry capture for a traced agent: the instrumentors you name are switched on in
the process that runs the rollout, and each episode's spans are stored with it. It needs the
`agent` extra, `pip install "poisson-prove[agent]"`.

| key | type | default | what it is |
|---|---|---|---|
| `instrument` | list of names | `[]` | instrumentors to switch on, by the name they register under OpenTelemetry's `opentelemetry_instrumentor` entry points (`openai` for `opentelemetry-instrumentation-openai-v2`); empty for an agent that makes its own spans |
| `content` | `true` or `false` | `false` | whether prompts and completions are stored; with `false` they never leave the process |
| `max_observation_bytes` | integer, 1 or more, or `"none"` | no default, required | the largest single value (one prompt, one tool result) stored whole; a larger one is stored as its head, its tail and its length. `"none"` stores every value whole |
| `max_spans` | integer, 1 or more | no limit | the most spans one episode keeps: the earliest-started, so the root survives |

[What capture stores](what-capture-stores.md) says exactly what each setting keeps.

## `[chaos]`

Injects a fault into the target's HTTP calls, so you can measure how the agent copes. It needs no
extra package: it hooks the `httpx` client the target's model client uses.
[Fault injection](fault-injection.md) lists every fault.

| key | type | default | what it is |
|---|---|---|---|
| `fault` | a fault's name | `"none"` | which fault to inject; an unknown name is refused before the run |
| `rate` | number from 0 to 1 | `1.0` | the share of eligible calls that get the fault |
| `steps` | list of step names | every step | inject only inside these steps |

Like `[declare]`, it is not part of the sweep's identity: a faulted run and a clean one paired with
it share their seeds.

## `[modal]`

How a `--backend modal` sweep runs. Every key is optional; the command line's `--concurrency`,
`--infra-retries`, `--max-cost`, `--est-seconds` and `--app-name` override it for one run.
[Backends](backends.md#modal) says what a Modal sweep needs.

| key | type | default | what it is |
|---|---|---|---|
| `concurrency` | integer | `16` | containers at once |
| `batch_size` | integer | `64` | episodes per call to a container |
| `episode_timeout` | seconds, or none | `300` | the limit on one episode inside a container |
| `infra_retries` | integer | `2` | retries of a batch that failed for an infrastructure reason |
| `max_rollouts` | integer, or none | no limit | stop after this many and leave the run partial |
| `max_cost` | dollars, or none | no cap | refuse before anything starts when the estimate is above it |
| `est_seconds_per_episode` | seconds, or none | no estimate | the time one episode takes, for the cost estimate |
| `app_name` | string | `"poisson-prove"` | the Modal app's name |
| `secrets` | list of names | none | Modal secrets mounted on the function, by name; Prove never reads their values |

## `[modal.<image>]`

The container image, a table under `[modal]`. The section named `image`, `[modal.image]`, is used
unless `--image SECTION` names another, so one spec can hold several images.

| key | type | default | what it is |
|---|---|---|---|
| `python` | version string | `"3.11"` | the image's Python |
| `pip` | list of requirements | none | packages to install, your agent's dependencies among them |
| `apt` | list of packages | none | system packages |
| `dockerfile` | path | none | build from this Dockerfile instead |
| `local_packages` | list of package names | none | importable local packages shipped into the image (Prove itself always is); `dockerfile` excludes `pip` and `apt` |
| `gpu` | a GPU type, or none | no GPU | the GPU to attach, such as `"A10G"` |

## `[burla]`

How a `--backend burla` sweep runs, on your own Burla cluster. The first ten keys are required:
there is no default for a price, a cap or a cluster. [Backends](backends.md#burla) says what it
needs.

| key | type | default | what it is |
|---|---|---|---|
| `nodes` | integer | no default, required | the cluster's nodes |
| `machine_type` | string | no default, required | the nodes' machine type |
| `slots_per_node` | integer | no default, required | episodes run at once on a node |
| `usd_per_node_hour` | dollars | no default, required | the price of a node for an hour |
| `price_asof` | string | no default, required | where and when that price was read |
| `ledger` | path | no default, required | the spend ledger, checked before the run starts and written as it goes |
| `head_url` | URL | no default, required | the cluster's head, a local `http` URL or an `https` one |
| `stop_cost` | dollars | no default, required | the spend at which the job is stopped |
| `max_cost` | dollars, at least `stop_cost` | no default, required | the estimate above which the sweep is refused before it starts |
| `est_seconds_per_episode` | seconds | no default, required | the time one episode takes, for the estimate |
| `packages` | list of package names | none | local packages shipped to the workers, beside Prove itself |
| `func_cpu` | integer | `1` | CPUs per worker |
| `func_ram` | gigabytes | `4` | memory per worker |
| `boot_minutes` | minutes | `5.0` | billed time to boot the cluster, in the estimate |
| `idle_minutes` | minutes | `5.0` | billed idle time before the cluster stops, in the estimate |
| `batch_size` | integer | `256` | episodes per worker call |
| `episode_timeout` | seconds, or none | no limit | the limit on one episode |
| `infra_retries` | integer | `2` | retries of a batch that failed for an infrastructure reason |
| `max_rollouts` | integer, or none | no limit | stop after this many and leave the run partial |

## The mistakes it refuses

Every mistake is refused with exit 1 before anything runs, naming what to fix. Here is a
misspelt key, made by renaming `t_unit` in the example spec:

<!-- docs-check: run -->
~~~bash
poisson-prove init --example --out good.toml
sed 's/^t_unit =/t_units =/' good.toml > typo.toml
~~~

<!-- docs-check: run -->
~~~console
$ poisson-prove sweep typo.toml --dry-run  # exits 1
error: typo.toml, line 10: "t_units" is not a key or table a sweep spec has; the nearest known key is "t_unit"
~~~

The others, each in one line: a required key missing (`target_id`, `t_unit`, `replicates`); no
`[axes.<name>]` table; an axis without `type` or `values`, or with a type other than the two; an
unknown key inside any table; a value of the wrong type or out of range (`replicates = 0`, a
`[chaos]` `rate` of 2); a `[capture]` table without `max_observation_bytes`; a `target` that is not
`module:function`, cannot be imported, or does not take `(cfg, seed)`; and a design too small to
detect the change you accept, which names the replicates it needs.
