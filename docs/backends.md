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

A Modal sweep first checks that this machine is signed in to Modal, without reading the token;
`modal setup` signs it in.

<!-- docs-check: skip: needs a Modal sign-in on this machine -->
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

## Your cloud account

`--backend cloud` runs the rollouts on a cluster Prove starts in your own cloud account and stops
when the sweep ends, whether it finished, failed, stopped early or was interrupted. This release
offers AWS; a spec naming Google Cloud or Azure is refused as not yet supported. It is not
available on Windows: there it is refused before anything else.

<!-- docs-check: skip: needs your own AWS account -->
```bash
pip install "poisson-prove[cloud]"
aws login
```

The extra installs the cluster software Prove uses, pinned to exactly one version
(`burla==1.8.4`), and `botocore[crt]`, which a sign-in made by `aws login` needs. The AWS CLI is
not a Python package: install it yourself, and Prove names it when it is missing. Before anything
starts Prove checks, in this order, the extra, the AWS CLI, that this machine is signed in (a
read-only `aws sts get-caller-identity`), the region and machine type against its price table,
the image's Python against this machine's, the vCPU ceiling and the account's vCPU quota. Every
install line Prove prints for this backend is `pip install "poisson-prove[cloud]"`.

These keys are required: `provider`, `region`, `machine_type`, `nodes`, `ledger` (a JSON-lines
file of what has been spent, checked before anything starts and written as the job goes),
`stop_cost` (the spend at which Prove stops the job itself), `max_cost` (the estimate above which
the sweep is refused) and `est_seconds_per_episode`. The price comes from Prove's own AWS price
table unless `usd_per_node_hour` and `price_asof` are given together.
[The sweep spec](sweep-spec.md#cloud) has the optional keys.

<!-- docs-check: run -->
```toml
[cloud]
provider = "aws"
region = "us-east-2"
machine_type = "m7i.2xlarge"
nodes = 4
ledger = "cloud-ledger.jsonl"
stop_cost = 2.0
max_cost = 3.0
est_seconds_per_episode = 0.5
```

What leaves this machine: your code, its inputs and its results go between this machine and the
nodes through Burla's relay (the cluster software Prove uses), and the plan's `Traffic` line says
so. Prove turns the software's telemetry off. The store stays on this machine. If this machine
stops first, the nodes stop themselves within `idle_minutes` (5 by default) or 3 minutes,
whichever is longer, and the next cloud sweep finds what was left, stops it and closes its ledger
line. What Prove started is recorded under `$XDG_STATE_HOME/poisson-prove/cloud/`
(`~/.local/state` when the variable is unset), beside the cluster software's log. The sign-in
check reads which AWS profile is active from `AWS_PROFILE` (or `AWS_DEFAULT_PROFILE`) and
`AWS_CONFIG_FILE`, to name `aws sso login` for an SSO profile; it never reads a credential.

Prove ships its own code and your local packages to the workers as one bundle, and the plan names
it with its digest. The cluster software pins every distribution your environment installed from
an index and installs those pins on each node from the index: a Prove installed from PyPI is
reinstalled there at the same version, so a version that is not on PyPI cannot be installed on
the workers. An editable checkout of Prove is shipped in the bundle, not installed. Either way the
bundle goes first on each worker's path, so the code that runs your rollouts is the Prove on this
machine.

## Threads in a worker

A Modal container or a Burla worker runs your rollout's BLAS, the linear algebra numpy and SciPy
call, on one thread. A run's workers share machines, and OpenBLAS, which numpy and SciPy use on
Linux and on macOS below numpy 2.0, otherwise starts a thread on every core in each worker. If a
worker's environment sets `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` or
`BLIS_NUM_THREADS`, for example through your Dockerfile, Prove leaves that count alone. A local
sweep runs one episode at a time and sets no count.

## What a backend never changes

The rows. A sweep's seeds come from its run salt, not from where it ran, so a local run and a
Modal run of the same spec paired with `--pair-with` are compared episode by episode like any
other pair. The store is always on this machine.

What leaves the machine is up to the backend you choose. Locally, nothing but your agent's own
calls. On Modal, your rollout's code, the image you declare and each batch's conditions and seeds
go to your Modal account, and the rows come back. On Burla, Prove's bundle of your code and the
same inputs go to your cluster, through Burla's relay unless its head runs in private mode
(`BURLA_PRIVATE=True`). Prove itself sends nothing to Poisson Labs or anyone else.
