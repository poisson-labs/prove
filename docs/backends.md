# Backends

A backend is where a sweep's rollouts run: on this machine (`local`, the default), in parallel
Modal containers on your own Modal account (`modal`), or on your own Burla cluster (`burla`,
experimental). Whichever runs them, the episodes land in the same local store, as the same rows,
and every other command reads them the same way. The plan always says where the sweep will run and
what it will cost before anything starts.

<!-- docs-check: setup quickstart -->

## Local

`--backend local`, the default, runs every rollout in Prove's own process, one after another, on
this machine. It needs nothing beyond `pip install poisson-prove`, and costs nothing but your
agent's own calls.

`--episode-timeout S` limits one episode to `S` seconds: each episode then runs in a child process,
and one past the limit is stopped and stored with no outcome, as an error of kind `episode_timeout`, with
the trace it had so far. Without it an episode that hangs holds up the sweep. A rollout that
raises is stored as an errored episode either way, and the sweep goes on.

<!-- docs-check: run -->
```console
$ poisson-prove sweep --dry-run --episode-timeout 30
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on local, $0 (local)
…
```

## Modal

`--backend modal` runs the rollouts in parallel containers on [Modal](https://modal.com), on your
own account: Prove builds the image, sends the episodes in batches, retries a batch that fails for
an infrastructure reason, and writes the rows to your local store as they come back. It needs the
`modal` extra and a Modal account set up on this machine (`modal setup` signs you in):

<!-- docs-check: run -->
```bash
pip install "poisson-prove[modal]"
```

The `[modal]` table of the spec says how it runs, and a `[modal.image]` table what the containers
hold: the Python, the packages your agent needs (`pip`), system packages (`apt`), or a
`dockerfile`. Your rollout is imported inside the container, not on this machine. Keys your agent
needs reach it as Modal secrets, named in `secrets`: Prove mounts them by name and never reads
their values. Every key of both tables is on [The sweep spec](sweep-spec.md#modal).

<!-- docs-check: run -->
```toml
[modal]
concurrency = 32
est_seconds_per_episode = 4.0
max_cost = 5.0
secrets = ["openai"]

[modal.image]
python = "3.11"
pip = ["openai>=2.20"]
```

The plan prints the cost estimate: Modal's compute for the containers, from Modal's prices of
2026-09-03, which Prove carries and names on every plan. It covers compute only, not model tokens:
what your agent spends at its model provider is on that provider's bill. Without
`est_seconds_per_episode` there is no estimate and the plan says so; with `max_cost` (or
`--max-cost`) a sweep whose estimate is above it is refused before anything starts:

<!-- docs-check: run -->
```console
$ poisson-prove sweep --backend modal --dry-run
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on modal, unknown (no estimate; Modal's 2026-09-03 prices, which cover compute, not model tokens)
…
  Cost: unknown (no estimate; Modal's 2026-09-03 prices, which cover compute, not model tokens)
…
```

Episodes that hit an infrastructure failure after their retries are recorded as such, apart from
your agent's own errors. A sweep stopped part way is resumed with `sweep --resume`, as a local one
is.

## Burla

`--backend burla` runs the rollouts on a Burla cluster in your own cloud. It is experimental: it
runs with exactly one version of the Burla client, `burla==1.8.2`, which the extra pins, and its
plan and refusals may change. It is not available on Windows: there it is refused before anything
else.

<!-- docs-check: skip: needs your own Burla cluster -->
```bash
pip install "poisson-prove[burla]"
```

Spend is capped by Prove, not only stated, so a `[burla]` table has no defaults for money or for
the cluster. These keys are required: `nodes`, `machine_type`, `slots_per_node`,
`usd_per_node_hour`, `price_asof` (where and when you read that price), `ledger` (a JSON-lines
file of what has been spent, checked before anything starts and written as the job goes),
`head_url` (the cluster's head), `stop_cost` (the spend at which Prove stops the job itself),
`max_cost` (the estimate above which the sweep is refused) and `est_seconds_per_episode`.
[The sweep spec](sweep-spec.md#burla) has the optional keys.

<!-- docs-check: run -->
```toml
[burla]
nodes = 2
machine_type = "n4-standard-4"
slots_per_node = 4
usd_per_node_hour = 0.19
price_asof = "the cloud's price page, 2026-10-20"
ledger = "burla-ledger.jsonl"
head_url = "http://localhost:5001"
stop_cost = 2.0
max_cost = 3.0
est_seconds_per_episode = 0.5
```

Prove ships its own code and your local packages to the workers as one bundle, and the plan names
it with its digest. The plan's `Traffic` line says where your data goes: code, inputs and results
pass through Burla's relay unless the cluster's head was started with `DISABLE_BURLA_RELAY=True`,
which Prove cannot see from the head; the store stays on this machine either way.

<!-- docs-check: skip: needs the burla extra and your own cluster's settings -->
```console
$ poisson-prove sweep --backend burla --dry-run
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on burla, ~$0.080 this run (2 × $0.19/node-hour, the cloud's price page, 2026-10-20) · ledger burla-ledger.jsonl $0 so far · stop $2.00 · cap $3.00
…
  Cluster: 2 × n4-standard-4 · 4 slots each · 8 at once · grow off · idle allowance 5 min · head http://localhost:5001
…
  Traffic: code, inputs and results go through Burla's relay unless the head was started with DISABLE_BURLA_RELAY=True; Prove cannot tell from the head whether it was; the store stays on this machine
…
```

A Burla client the Python running Prove cannot import is refused before the plan, with the
install line. Every Burla install line Prove prints is `pip install "poisson-prove[burla]"`.

## What a backend never changes

The rows. A sweep's seeds come from its run salt, not from where it ran, so a local run and a
Modal run of the same spec paired with `--pair-with` are compared episode by episode like any
other pair. The store is always on this machine.

What leaves the machine is up to the backend you choose. Locally, nothing but your agent's own
calls. On Modal, your rollout's code, the image you declare and each batch's conditions and seeds
go to your Modal account, and the rows come back. On Burla, Prove's bundle of your code and the
same inputs go to your cluster, through Burla's relay unless its head runs with
`DISABLE_BURLA_RELAY=True`. Prove itself sends nothing to Poisson Labs or anyone else.
