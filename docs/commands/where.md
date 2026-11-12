# `poisson-prove where`

Says where sweeps of the spec in this folder run, and whether that is ready on this machine: this
machine, Modal, or your own cloud account. With `local`, `modal` or `cloud` it sets it, by writing
the matching table into `./prove.toml`.

A spec runs where its table says. A `[cloud]` table means your cloud account, a `[modal]` table
means Modal, and neither means this machine. `poisson-prove sweep` with no `--backend` runs there.
[Backends](../backends.md) says what each choice needs and does.

<!-- docs-check: setup quickstart -->

## Help

<!-- docs-check: run -->
```console
$ poisson-prove where --help
usage: poisson-prove where [-h] [--spec PATH] [--cloud NAME] [--region REGION]
                           [--machine-type TYPE] [--nodes N] [--max-vcpus N]
                           [--stop-cost USD] [--max-cost USD] [--yes] [--json]
                           [--store PATH] [--plain] [--debug]
                           [{local,modal,cloud}]

Say where sweeps of ./prove.toml run (this machine, Modal or your own cloud
account) and whether that is ready on this machine; or, with local, modal or
cloud, set it, by writing the matching table into the spec and nothing else.
In a terminal it asks for what no option gives and the spec does not hold;
--yes takes the defaults instead. It asks for no secret and signs in to
nothing: a cloud is reached through that cloud's own sign-in on this machine.

positional arguments:
  {local,modal,cloud}  where sweeps run from now on (default: only say where
                       they run)

options:
  -h, --help           show this help message and exit
  --spec PATH          the sweep spec to read or change (default:
                       ./prove.toml)
  --cloud NAME         with cloud: which cloud (default: aws, the one offered)
  --region REGION      with cloud: where the nodes start (default: us-east-2)
  --machine-type TYPE  with cloud: the nodes' machine type (default:
                       m7i.2xlarge)
  --nodes N            with cloud: how many nodes Prove starts (default: 4)
  --max-vcpus N        with cloud: the vCPU ceiling (default: the nodes times
                       the machine's vCPUs)
  --stop-cost USD      with cloud: the spend at which Prove stops the sweep
                       (default: 2)
  --max-cost USD       with cloud or modal: the estimate above which a sweep
                       is refused (default: 3 on a cloud account, no cap on
                       Modal)
  --yes                take the default for what no option gives, and ask
                       nothing (default: ask in a terminal)
  --json               print where sweeps run as one JSON document instead of
                       text
  --store PATH         the store folder (default: $POISSON_PROVE_STORE when
                       set, else ./prove-runs)
  --plain              print plain text, as a pipe gets it, on a terminal too
                       (default: pretty on a terminal, plain otherwise)
  --debug              also print the traceback of an unexpected failure

examples:
  poisson-prove where
  poisson-prove where cloud
  poisson-prove where cloud --region us-east-2 --nodes 4 --yes
  poisson-prove where modal --max-cost 5
  poisson-prove where local
```

## Options

- `local`, `modal` or `cloud`, the one positional word, sets where sweeps run from now on.
  `poisson-prove where local` takes the table out of the spec. `poisson-prove where modal` writes
  a `[modal]` table. `poisson-prove where cloud` writes a `[cloud]` table. With no word, `where`
  only says where sweeps run, and writes nothing.
- `--spec PATH` names the spec to read or change, when it is not `./prove.toml`.
- `--cloud NAME` names the cloud. This release offers `aws`. Google Cloud and Azure are refused as
  not yet supported.
- `--region REGION` is where the nodes start, `us-east-2` by default. `--machine-type TYPE` is the
  nodes' machine type, `m7i.2xlarge` by default. Both come from Prove's price table, which
  [The sweep spec](../sweep-spec.md#cloud) lists.
- `--nodes N` is how many nodes Prove starts, 4 by default.
- `--max-vcpus N` is the vCPU ceiling: a plan whose nodes need more is refused. Without it the
  ceiling is the nodes times the machine's vCPUs.
- `--stop-cost USD` is the spend at which Prove stops the sweep, $2 by default.
- `--max-cost USD` is the estimate above which a sweep is refused, $3 by default on a cloud
  account. With `modal` it sets the Modal table's cap, which has no default, and the table then
  also gets `est_seconds_per_episode = 1.0`.
- `--yes` takes the default for everything no option gives, and asks nothing.
- `--json` prints the answer as one JSON document, `poisson-prove.where/1`.
- `--store PATH` is the store folder. `where` reads it only to name the run of a cluster an
  earlier sweep left. `--plain` prints plain text on a terminal too. `--debug` adds the traceback
  of an unexpected failure.

The options from `--cloud` to `--stop-cost` go with `cloud` alone, and `--max-cost` with `cloud`
or `modal`. Given with another word, each is a usage error, exit 2.

**What is asked.** In a terminal, `where cloud` asks for each value that no option gives and the
spec does not already hold, one question a line, with its default in brackets. Enter takes the
default. `where modal` asks for the cap. With `--yes` nothing is asked and the defaults stand. Off
a terminal with no `--yes`, the first missing value is refused, naming its option.

**What is kept.** A table already in the spec keeps every value no option changes, so
`poisson-prove where cloud --nodes 8` changes the nodes and nothing else. Your comments, spacing
and key order inside the table stay too. The one exception is a table holding a value written over
several lines: `where` then writes the table whole, and comments inside it go.

## Examples

The quickstart's spec holds neither table, so it runs on this machine:

<!-- docs-check: run -->
```console
$ poisson-prove where
where  this machine
  next: poisson-prove sweep
```

`where local` sets that, taking a `[modal]` or `[cloud]` table out when one is there. The same
answer as JSON, for a script:

<!-- docs-check: run -->
```console
$ poisson-prove where local
where  this machine
  next: poisson-prove sweep
$ poisson-prove where --json
{
  "schema": "poisson-prove.where/1",
  "verdict": "where",
  "sentence": "this machine",
  "runs_on": "local",
  "spec": "prove.toml",
  "ready": true,
  "checks": [],
  "next": ["poisson-prove sweep"]
}
```

`ready` is false when a check failed. `checks` holds each check's `label`, `value`, `ok` and
`next`, the one command that fixes a failed check or `null`.

### Your cloud account

`where cloud` writes the `[cloud]` table and checks that this machine can use the account: the
extra, the AWS CLI, the sign-in, the region and machine type, and the vCPU quota. The account is
shown masked. The first line is the sentence bare `where` prints, shown in the block after this
one:

<!-- docs-check: skip: needs your own AWS account -->
```console
$ poisson-prove where cloud --region us-east-2 --nodes 4 --yes
…
  signed in  AWS 6030…4933
  wrote  [cloud] into prove.toml
  next: poisson-prove sweep --dry-run
```

The table it writes for those answers is the one below. `ledger` and `est_seconds_per_episode`
are not asked for. The estimate in the plan follows `est_seconds_per_episode`, the seconds one
rollout takes, so set it from a run on this machine before you trust the estimate.

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

Bare `where` then gives the answer and whether it is ready, and `next:` is the sweep:

<!-- docs-check: skip: shows a machine that is signed in to AWS -->
```console
$ poisson-prove where
where  your AWS account, us-east-2, 4 × m7i.2xlarge; signed in, ready
  signed in  AWS 6030…4933
  next: poisson-prove sweep
```

A check that fails does not stop the table being written: you can fix it later. `where` still
exits 0, the sentence says what is not ready, and `next:`, when one command fixes it, is that
command. A sweep is refused until the check passes. On a machine that has not signed in:

<!-- docs-check: skip: shows a machine that is not yet signed in to AWS -->
```console
$ poisson-prove where
where  your AWS account, us-east-2, 4 × m7i.2xlarge; not ready: this machine is not signed in to AWS
  next: aws login
```

A value Prove cannot use on any machine is refused, and nothing is written. That covers a cloud
this release does not offer, a region or machine type outside the price table, and a number out
of its range:

<!-- docs-check: skip: needs your own AWS account -->
```console
$ poisson-prove where cloud --cloud gcp --yes  # exits 1
error: Google Cloud is not yet supported by Prove; AWS is
```

### Modal

`where modal` writes the `[modal]` table and asks Modal's own client whether this machine is
signed in. It does not read the token and never shows it. When the machine is not signed in, the
sentence says so and `next:` is `modal setup`:

<!-- docs-check: skip: needs the modal extra and a Modal sign-in on this machine -->
```console
$ poisson-prove where modal --yes
where  Modal; signed in, ready
  signed in  Modal
  wrote  [modal] into prove.toml
  next: poisson-prove sweep --dry-run
```

With `--yes` and no `--max-cost`, the table holds no cap. With a cap, `where modal` also writes
`est_seconds_per_episode = 1.0`, the seconds one rollout takes, because a cap is held against an
estimate and Modal's estimate needs that time. It is the same default the cloud table gets, with
the same advice: set it from a run on this machine before you trust the estimate.

<!-- docs-check: run -->
```toml
[modal]
max_cost = 5.0
est_seconds_per_episode = 1.0
```

### A 0.2 spec's `[burla]` table

In 0.2 a sweep on your own cluster read a `[burla]` table, and you started the cluster yourself.
That table is now `[cloud]`, and Prove starts and stops the cluster. A sweep of a spec that still
holds `[burla]` is refused. Bare `where` says the answer is not ready, exit 0, with
`next: poisson-prove where cloud`.

`where cloud` moves the table in place. It keeps every key that carries over, in the order you had
them. It deletes `head_url`. It adds `provider` and `region`, which it asks for or takes from
`--cloud` and `--region`. Given this table:

<!-- docs-check: skip: a 0.2 table, which this release refuses until where cloud rewrites it -->
```toml
[burla]
head_url = "http://127.0.0.1:5001"
nodes = 3
machine_type = "m7i.xlarge"
slots_per_node = 2
usd_per_node_hour = 0.31
price_asof = "read off the AWS console, 2026-10-30"
ledger = "old-ledger.jsonl"
stop_cost = 4.0
max_cost = 6.0
est_seconds_per_episode = 0.75
```

the one command moves it:

<!-- docs-check: skip: needs your own AWS account -->
```console
$ poisson-prove where cloud --cloud aws --region us-east-2 --yes
…
  signed in  AWS 6030…4933
  wrote  [cloud] into prove.toml
  next: poisson-prove sweep --dry-run
```

Its first line, left out above, says `your AWS account, us-east-2, 3 × m7i.xlarge`: the nodes and
the machine type came from the old table. The spec then holds:

<!-- docs-check: run -->
```toml
[cloud]
provider = "aws"
region = "us-east-2"
nodes = 3
machine_type = "m7i.xlarge"
slots_per_node = 2
usd_per_node_hour = 0.31
price_asof = "read off the AWS console, 2026-10-30"
ledger = "old-ledger.jsonl"
stop_cost = 4.0
max_cost = 6.0
est_seconds_per_episode = 0.75
```

### A ceiling the nodes do not fit

`--max-vcpus` below what the nodes need is written as asked, and the answer says it is not ready.
There is no `next:` line, because no one command fixes it: raise the ceiling or ask for fewer
nodes.

<!-- docs-check: skip: needs your own AWS account -->
```console
$ poisson-prove where cloud --max-vcpus 8 --yes
where  your AWS account, us-east-2, 4 × m7i.2xlarge; not ready: 4 × m7i.2xlarge is 32 vCPUs, over max_vcpus 8
  wrote  [cloud] into prove.toml
```

### A spec that holds both tables

A spec that holds `[cloud]` and `[modal]` together does not say where it runs. A sweep of it with
no `--backend` is refused, exit 1, and so is bare `where`, in one line that names both tables.
`poisson-prove where cloud`, `where modal` or `where local` keeps one answer and takes the other
table out.

### What an earlier sweep left running

A cloud sweep stops its nodes when it ends. If this machine stopped first (a crash, a `kill -9`,
a lost network), the nodes stop themselves, and Prove's record of what it started stays open.

Bare `where`, on a spec that runs on your cloud account and a machine signed in to it, looks for
such a record. When it finds one it stops any node still listed, stops the cluster software on
this machine, closes the run's ledger line if it is still open, and says so in one `note:` line
before its answer. The next cloud sweep does the same.

When `where` cannot confirm that the nodes stopped, it says they may still be running, leaves the
record as it is, and exits 3. `where cloud`, `where modal` and `where local` do not look: they
change the spec only.

## Exit codes

- `0`: the answer was printed, ready or not. With `local`, `modal` or `cloud`, the table was
  written or taken out.
- `1`: refused, and nothing was written. The causes are: no spec in this folder; a spec that holds
  both tables, for bare `where`; a cloud that is not offered; a region or machine type outside the
  price table; a number out of its range; a value that is missing with no terminal to ask on and
  no `--yes`; a table holding a key Prove does not know, which is never dropped; your cloud
  account chosen on Windows; another sweep running on the account from this machine.
- `2`: the command line is wrong.
- `3`: Prove could not confirm that what an earlier cloud sweep left has stopped; or an unexpected
  failure, whose traceback `--debug` prints.
- `130`: interrupted with Ctrl-C.

## What it writes

Bare `where` writes nothing to the spec. With `local`, `modal` or `cloud` it writes the spec and
nothing else. It replaces the spec's `[modal]` or `[cloud]` table, or a 0.2 `[burla]` table, with
the new one where the old one stood. It appends the table after a blank line when there was none.
For `local` it takes the table out. Every other byte of the file stays as it was, and the file is
replaced in one step, so a write that is cut short leaves the spec you had.

`where` never stores a cloud secret and never asks for one. Your cloud is reached only through
its own sign-in on this machine, and the checks are read-only: they write no cloud configuration,
sign in to nothing and create nothing in the account.

When bare `where` stops what an earlier cloud sweep left, it also closes that run's line in the
spend ledger and updates Prove's record under `$XDG_STATE_HOME/poisson-prove/cloud/`
(`~/.local/state` when the variable is unset).
