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
| `[cloud]` | table | required for `--backend cloud` | how a `--backend cloud` sweep runs on your own cloud account |

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
[What a declaration checks](what-a-declaration-checks.md).

## `[capture]`

Turns on OpenTelemetry capture for a traced agent: the instrumentors you name are switched on in
the process that runs the rollout, and each episode's spans are stored with it. It needs the
`agent` extra, `pip install "poisson-prove[agent]"`.

| key | type | default | what it is |
|---|---|---|---|
| `instrument` | list of names | `[]` | instrumentors to switch on, by the name they register under OpenTelemetry's `opentelemetry_instrumentor` entry points (`openai` for `opentelemetry-instrumentation-openai-v2`); empty for an agent that makes its own spans. A name that is not installed is not refused: the run goes on without capture, and its manifest says so |
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
| `fault` | a fault's name | `"none"` | which fault to inject; an unknown name is refused when the sweep is planned |
| `rate` | number from 0 to 1 | `1.0` | the share of eligible calls that get the fault |
| `steps` | list of step names | every step | inject only inside these steps |

Like `[declare]`, it is not part of the sweep's identity: a faulted run and a clean one paired with
it share their seeds.

## `[modal]`

How a sweep on Modal runs. A spec that holds this table runs there unless `--backend` says
otherwise, and `poisson-prove where modal` writes it. Every key is optional; the command line's
`--concurrency`, `--infra-retries`, `--max-cost`, `--est-seconds`, `--app-name`, `--batch-size`,
`--episode-timeout` and `--max-rollouts` override it for one run.
[Backends](backends.md#modal) says what a Modal sweep needs.

| key | type | default | what it is |
|---|---|---|---|
| `concurrency` | integer | `16` | containers at once |
| `batch_size` | integer | `64` | episodes per call to a container |
| `episode_timeout` | seconds, or none | `300` | the limit on one episode inside a container |
| `infra_retries` | integer | `2` | retries of a batch that failed for an infrastructure reason |
| `max_rollouts` | integer, or none | no limit | stop after this many and leave the run partial |
| `max_cost` | dollars, or none | no cap | refuse before anything starts when the estimate is above it, or when there is no estimate to hold against it |
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

## `[cloud]`

How a sweep on your own cloud account runs: the cluster Prove starts there and stops when the
sweep ends. `poisson-prove where cloud` writes this table, and a spec that holds it runs there
unless `--backend` says otherwise. The first eight keys are required: there is no default for a
cap or a cluster. [Backends](backends.md#your-cloud-account) says what it needs.

| key | type | default | what it is |
|---|---|---|---|
| `provider` | `"aws"` | no default, required | the cloud (Google Cloud and Azure are refused as not yet supported) |
| `region` | string | no default, required | where the nodes start, from Prove's price table |
| `machine_type` | string | no default, required | the nodes' machine type, from Prove's price table |
| `nodes` | integer | no default, required | how many nodes Prove starts |
| `ledger` | path | no default, required | the spend ledger, checked before the run starts and written as it goes |
| `stop_cost` | dollars | no default, required | the spend at which the job is stopped |
| `max_cost` | dollars, at least `stop_cost` | no default, required | the estimate above which the sweep is refused before it starts |
| `est_seconds_per_episode` | seconds | no default, required | the time one episode takes, for the estimate |
| `max_vcpus` | integer | `nodes` × the machine's vCPUs | the ceiling: a plan whose nodes need more is refused |
| `slots_per_node` | integer | the machine's vCPUs ÷ `func_cpu` | episodes run at once on a node |
| `image` | string | `python:3.<this machine's minor>` | the container the rollouts run in; its Python must be this machine's |
| `idle_minutes` | minutes, 2 to 60 | `5` | billed idle time in the estimate, and the nodes' own idle stop |
| `boot_minutes` | minutes | `5.0` | billed time to boot the cluster, in the estimate |
| `usd_per_node_hour` | dollars | Prove's price table | the price of a node for an hour, given with `price_asof` |
| `price_asof` | string | Prove's price table | where and when that price was read, given with `usd_per_node_hour` |
| `disk_gb` | integer, 10 to 2,000 | the cluster software's default | each node's disk |
| `packages` | list of package names | none | local packages shipped to the workers, beside Prove itself |
| `func_cpu` | integer | `1` | CPUs per worker |
| `func_ram` | gigabytes | `4` | memory per worker |
| `batch_size` | integer | `256` | episodes per worker call |
| `episode_timeout` | seconds, or none | no limit | the limit on one episode |
| `infra_retries` | integer | `2` | retries of a batch that failed for an infrastructure reason |
| `max_rollouts` | integer, or none | no limit | stop after this many and leave the run partial |

### The price table

Prove carries a dated table of AWS prices, as it carries Modal's, so a spec needs no price. Each
figure is dollars for one node for one hour: the on-demand price of the machine, plus its public
IPv4 address, plus its disk at 50 GB. They were read from AWS's price list, which needs no
account, on 2026-11-09; the `m7i.2xlarge` row for `us-east-2` was first read on 2026-11-06 and
keeps that date. The plan names the date of the row it uses.

| machine type | vCPUs | `us-east-1` | `us-east-2` | `us-west-2` | `eu-west-1` | `eu-central-1` |
|---|---|---|---|---|---|---|
| `m7i.large` | 2 | $0.1661 | $0.1661 | $0.1661 | $0.1837 | $0.1975 |
| `m7i.xlarge` | 4 | $0.2669 | $0.2669 | $0.2669 | $0.2960 | $0.3183 |
| `m7i.2xlarge` | 8 | $0.4685 | $0.4685 | $0.4685 | $0.5207 | $0.5598 |
| `m7i.4xlarge` | 16 | $0.8717 | $0.8717 | $0.8717 | $0.9701 | $1.0428 |
| `m7i.8xlarge` | 32 | $1.6781 | $1.6781 | $1.6781 | $1.8689 | $2.0088 |
| `m7i.16xlarge` | 64 | $3.2909 | $3.2909 | $3.2909 | $3.6665 | $3.9408 |

A region or a machine type outside the table is refused, naming the ones the table has, unless
the spec gives `usd_per_node_hour` and `price_asof` together. The estimate is compute only: what
your agent spends at its model provider is on that provider's bill.

### A 0.2 spec's `[burla]` table

`[burla]` is now `[cloud]`, and Prove starts and stops the cluster itself. A spec that still
holds a `[burla]` table is refused, whichever backend it is swept on, naming the move:

<!-- docs-check: run -->
~~~bash
poisson-prove init --example --out old.toml
printf '\n[burla]\nhead_url = "http://127.0.0.1:5001"\n' >> old.toml
~~~

<!-- docs-check: run -->
~~~console
$ poisson-prove sweep old.toml --dry-run  # exits 1
error: old.toml, line 25: [burla] is now [cloud]; rename the table, delete head_url, and add provider and region (Prove now starts the cluster on your cloud account and stops it after)
  next: poisson-prove where cloud
~~~

`poisson-prove where cloud` makes the move in place: it renames the table, keeps every key that
carries over, deletes `head_url` (Prove runs the coordinator now) and adds `provider` and
`region`. [Its page](commands/where.md) shows it.

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
