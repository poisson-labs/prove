# Backends

A backend is where a sweep's rollouts run. There are three: this machine (`local`), parallel
containers on Modal (`modal`), or a cluster in your cloud account (`cloud`), which Prove starts
and stops. Whichever runs them, the episodes land in the same local store, as the same rows, and
every other command reads them the same way. The plan always says where the sweep will run and
what it will cost before anything starts.

<!-- docs-check: setup quickstart -->

## Choosing where a sweep runs

A spec says where its sweeps run by the table it holds: a `[cloud]` table means your cloud
account, a `[modal]` table means Modal, and neither means this machine. `poisson-prove sweep` runs
there. `poisson-prove where` says which it is and whether it is ready:

<!-- docs-check: run -->
```console
$ poisson-prove where
where  this machine
  next: poisson-prove sweep
```

`poisson-prove where local`, `poisson-prove where modal` and `poisson-prove where cloud` change it,
by writing the table into `./prove.toml` or taking it out. [Its page](commands/where.md) has the
options. `poisson-prove init` asks the same question when it writes a spec in a terminal, and the
terminal app has a page for it, behind `w`.

`--backend` on `sweep` overrides the spec for one run. A spec that holds both tables does not say
where it runs, so a sweep of it with no `--backend` is refused, with exit 1, before anything
starts.

## Local

`--backend local` runs every rollout in Prove's own process, one after another, on this machine.
It is where a spec with neither table runs. It needs nothing beyond `pip install poisson-prove`,
and costs nothing but your agent's own calls.

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

A Modal sweep first checks that this machine is signed in to Modal. The check asks Modal's own
client whether a sign-in is there; it does not read the token and never shows it. A machine that
is not signed in is refused before anything starts, with the one command that fixes it:

<!-- docs-check: skip: needs the modal extra, on a machine not yet signed in to Modal -->
```console
$ poisson-prove where modal --yes
where  Modal; this machine is not signed in
  wrote  [modal] into prove.toml
  next: modal setup
$ poisson-prove sweep --dry-run  # exits 1
error: this machine is not signed in to Modal
  next: modal setup
```

The plan prints the cost estimate: Modal's compute for the containers, from Modal's prices of
2026-09-03, which Prove carries and names on every plan. It covers compute only, not model tokens:
what your agent spends at its model provider is on that provider's bill. Without
`est_seconds_per_episode` there is no estimate and the plan says so. With `max_cost` (or
`--max-cost`) a sweep whose estimate is above it is refused before anything starts, and so is one
with a cap and no estimate to hold against it:

<!-- docs-check: skip: needs a Modal sign-in on this machine -->
```console
$ poisson-prove sweep --backend modal --dry-run
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on modal, unknown (no estimate; Modal's 2026-09-03 prices, which cover compute, not model tokens)
…
  Cost: unknown (no estimate; Modal's 2026-09-03 prices, which cover compute, not model tokens)
…
```

Episodes that hit an infrastructure failure after their retries are recorded as such, apart from
your agent's own errors. When no rollout of the first batch to come back has an outcome, the sweep
stops there, with exit 3, and does not pay for the rest. A sweep stopped part way by
`--max-rollouts` or Ctrl-C is resumed with `sweep --resume`, as a local one is.

## Your cloud account

`--backend cloud` runs the rollouts on a cluster in your own cloud account. Prove starts the nodes,
runs the sweep on them, and stops them when the sweep ends, however it ends: done, failed, stopped
early, or interrupted. This release offers AWS. Google Cloud and Azure are shown as not yet
supported, and a spec that names one is refused. It is not available on Windows: there it is
refused before anything else.

<!-- docs-check: skip: needs your own AWS account -->
```bash
pip install "poisson-prove[cloud]"
aws login
```

The extra installs the cluster software Prove uses, pinned to exactly one version, and
`botocore[crt]>=1.42.39`, which a sign-in made by `aws login` needs. The AWS CLI is not a Python
package: install it yourself, and Prove names it when it is missing. `poisson-prove[burla]`, the
extra's name in 0.2, installs the same until 0.4.0.

`poisson-prove where cloud` writes the `[cloud]` table and checks that this machine is ready.
The plan then names the account (masked to its first and last four digits), the nodes and what
they cost, and who carries your code:

<!-- docs-check: skip: needs your own AWS account -->
```console
$ poisson-prove sweep --dry-run
plan  1,746 rollouts of mock-agent: 9 cells x 194 replicates on your AWS account, ~$0.45 this run (4 × m7i.2xlarge at $0.4687/node-hour, Prove's AWS prices for us-east-2 of 2026-11-06, each node's disk priced at 52 GB) · ledger cloud-ledger.jsonl $0 so far · stop $2.00 · cap $3.00
…
  Backend: cloud · AWS · target: mock-agent · t_unit: tool_calls
  Account: AWS 6030…4933, signed in with the AWS CLI
  Cluster: Prove starts 4 × m7i.2xlarge in us-east-2 (8 vCPU each, 32 in all, ceiling 32) running python:3.11, and stops them when the sweep ends · 8 slots each · 32 at once · if this machine stops first, the nodes stop themselves within 5 min · this machine is kept from idle sleep while they run
…
  Traffic: your code, its inputs and its results go between this machine and the nodes through Burla's relay (the cluster software Prove uses); the store stays on this machine
  Cost: ~$0.45 this run (4 × m7i.2xlarge at $0.4687/node-hour, Prove's AWS prices for us-east-2 of 2026-11-06, each node's disk priced at 52 GB) · ledger cloud-ledger.jsonl $0 so far · stop $2.00 · cap $3.00
…
```

### The table

These keys are required: `provider`, `region`, `machine_type`, `nodes`, `ledger` (a JSON-lines
file of what has been spent, checked before anything starts and written as the job goes),
`stop_cost` (the spend at which Prove stops the job itself), `max_cost` (the estimate above which
the sweep is refused) and `est_seconds_per_episode`. The price comes from Prove's own AWS price
table unless `usd_per_node_hour` and `price_asof` are given together.
[The sweep spec](sweep-spec.md#cloud) has the optional keys and the price table. This is the table
`poisson-prove where cloud --yes` writes:

<!-- docs-check: run -->
```toml
[cloud]
provider = "aws"
region = "us-east-2"
machine_type = "m7i.2xlarge"
nodes = 4
max_vcpus = 32
ledger = "cloud-ledger.jsonl"
stop_cost = 2.0
max_cost = 3.0
est_seconds_per_episode = 1.0
```

### What is checked before anything starts

Before a cloud sweep starts anything Prove checks, in this order: the extra, the AWS CLI, that
this machine is signed in (a read-only `aws sts get-caller-identity`), the region and machine type
against its price table, the image's Python against this machine's, the vCPU ceiling and the
account's vCPU quota. Each refusal is one `error:` line with the one command that fixes it, and
every install line Prove prints for this backend is `pip install "poisson-prove[cloud]"`. The
sign-in check reads which AWS profile is active from `AWS_PROFILE` (or `AWS_DEFAULT_PROFILE`) and
`AWS_CONFIG_FILE`, to name `aws sso login` for an SSO profile; it never reads a credential.
Prove stores no cloud secret and asks for none: it reaches your account only through the AWS
CLI's own sign-in on this machine. An account's spend limit with its early controls on (such as
"Stop new resource launches") can stop new launches after a heavy day of sweeps; Prove then says
that a policy on the account, such as a spend limit, does not allow starting instances.

### What Prove starts and stops

A cloud sweep goes in this order. Prove starts the cluster software's coordinator on this machine.
It starts the nodes in your account and waits until they are ready. It runs the sweep. Then it
stops the nodes and the coordinator, and the result says how long the nodes were up and what the
ledger was charged.

The stop does not take the cluster software's word alone. Once the coordinator has stopped, Prove
reads the instances the cluster software tagged as its nodes in the sweep's region, launched since
the sweep began (a read-only `aws ec2 describe-instances`). A node still running there, such as
one whose launch was on its way when an interrupt stopped the boot, is terminated with
`aws ec2 terminate-instances`, and one `note:` line names it. Prove then waits, up to 2 minutes,
until every node of the sweep is terminated, since a node still shutting down counts against the
account's vCPU quota and would refuse a sweep started right after. Those two calls are the only
ones Prove makes to your instances, and it terminates only instances launched while its own sweep
ran. A node of another cluster of the same software, launched in the same account and region while
a Prove sweep runs, would be ended as Prove's, because the cluster software tags every cluster's
nodes alike and names every cluster the same unless its environment gives it a name of its own;
Prove does refuse to start a sweep while another coordinator runs for your account, so only a
cluster started after the sweep began could meet this. The `stopped` line counts the nodes that
started.

The stop happens on every ending: the sweep is done, it failed, it stopped early (the spend
reached `stop_cost`, or no rollout of the first batch had an outcome), or it was interrupted. An
interrupt is Ctrl-C, and on a cloud sweep SIGTERM and SIGHUP too (a `kill`, a closed terminal):
each stops the cluster, keeps what ran, and exits 130. A second Ctrl-C while the cluster is
stopping does not leave; Prove says so once. A third leaves at once, and what is left is found
later, as below.

Prove never changes or stops a coordinator or nodes it did not start. When it finds either
running for your account, the sweep is refused before anything starts.

While the nodes run, this machine is kept from idle sleep. A closed lid still puts it to sleep.

### If this machine stops first

Two bounds hold when Prove cannot stop the nodes itself:

- Prove is killed or crashes, and the coordinator lives: the job ends, the nodes go idle, and they
  stop themselves after `idle_minutes`, 5 by default.
- The coordinator is gone too, the machine sleeps, or the network is lost: the nodes cannot reach
  the coordinator and shut themselves down after 3 minutes.

So the nodes stop themselves within `idle_minutes` or 3 minutes, whichever is longer, and the
plan's `Cluster` line names that bound. `idle_minutes` cannot be set below 2.

The next cloud sweep, or `poisson-prove where`, finds what was left: it stops any node still
listed, closes the run's ledger line if it is still open, with a charge that is an upper bound,
and says so in one `note:` line. It also reads the account's instances again for the last sweep,
from its start to its stop, and terminates any node of it still running, with its own `note:`. When Prove cannot confirm that the nodes stopped, it exits 3,
says they may still be running, and names `poisson-prove where` as the next command.

What Prove started is recorded under `$XDG_STATE_HOME/poisson-prove/cloud/` (`~/.local/state` when
the variable is unset), beside the cluster software's log.

### What leaves this machine

The cluster software is Burla, and the extra pins it to the one version Prove runs
(`burla==1.8.4`). On a cloud sweep:

- Prove registers your cloud account with Burla's service by a proof that you own the account.
  There is no sign-in to that service, no password and no key.
- Your code, its inputs and its results go between this machine and the nodes through Burla's
  relay. The plan's `Traffic` line says the same before every cloud sweep.
- The coordinator on this machine fetches a licence key from that service when it starts.
- Prove turns the software's telemetry off, on this machine and on the nodes.

The nodes fetch their container image from Docker Hub and your packages from PyPI. Prove ships its
own code and your local packages to the workers as one bundle, and the plan names it with its
digest. The cluster software pins every distribution your environment installed from an index and
installs those pins on each node from the index: a Prove installed from PyPI is reinstalled there
at the same version, so a version that is not on PyPI cannot be installed on the workers. An
editable checkout of Prove is shipped in the bundle, not installed. Either way the bundle goes
first on each worker's path, so the code that runs your rollouts is the Prove on this machine.

The store stays on this machine. Prove itself sends nothing to Poisson Labs or anyone else.

## Threads in a worker

A Modal container or a worker on a cloud node runs your rollout's BLAS, the linear algebra numpy
and SciPy call, on one thread. A run's workers share machines, and OpenBLAS, which numpy and SciPy
use on Linux and on macOS below numpy 2.0, otherwise starts a thread on every core in each worker.
If a worker's environment sets `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS` or
`BLIS_NUM_THREADS`, for example through your Dockerfile, Prove leaves that count alone. A local
sweep runs one episode at a time and sets no count.

## What a backend never changes

The rows. A sweep's seeds come from its run salt, not from where it ran, so a local run and a
Modal run of the same spec paired with `--pair-with` are compared episode by episode like any
other pair. The store is always on this machine.

What leaves the machine is up to the backend you choose. Locally, nothing but your agent's own
calls. On Modal, your rollout's code, the image you declare and each batch's conditions and seeds
go to your Modal account, and the rows come back. On your cloud account, Prove's bundle of your
code and the same inputs go to the nodes through the cluster software's relay:
[What leaves this machine](#what-leaves-this-machine) says who carries them. Prove itself sends
nothing to Poisson Labs or anyone else.
