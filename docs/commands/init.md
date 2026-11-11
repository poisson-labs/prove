# `poisson-prove init`

Writes a sweep spec and nothing else: the keyless example, or a commented template to edit for
your own rollout. With `--agent` it writes instead the setup your own coding agent follows. It
never touches a store.

In a terminal, after it writes a spec, `init` asks one question: where sweeps of the spec should
run. This machine is the default, and Enter takes it. `--runs-on` answers on the command line.
Piped or with `--json` it does not ask, and writes the spec alone, as it always has. It asks only
when stdin and stderr are both terminals.

## Help

<!-- docs-check: run -->
```console
$ poisson-prove init --help
usage: poisson-prove init [-h] [--example] [--target pkg.module:rollout]
                          [--out PATH] [--force]
                          [--runs-on {local,modal,cloud}] [--agent]
                          [--repo DIR] [--print] [--json] [--store PATH]
                          [--plain] [--debug]

Write a sweep spec, ./prove.toml unless --out names another file, and nothing
else: a commented template to edit, or with --example the keyless quickstart,
runnable as it is. With --agent, write instead the setup your own coding agent
follows (a skill and the prompt to give it), in the two folders coding agents read
skills from. In a terminal, init then asks where sweeps should run; --runs-on
answers that on the command line, and off a terminal nothing is asked.

options:
  -h, --help            show this help message and exit
  --example             write the keyless quickstart, which runs as it is
                        (default: the template)
  --target pkg.module:rollout
                        fill the template's target with this rollout (default:
                        a commented placeholder)
  --out PATH            the file to write (default: ./prove.toml)
  --force               replace the file if it exists (default: refuse)
  --runs-on {local,modal,cloud}
                        where sweeps of this spec run: this machine, Modal or
                        your cloud account (default: asked in a terminal, this
                        machine otherwise)
  --agent               write the setup your own coding agent follows, a skill
                        and its prompt, instead of a sweep spec
  --repo DIR            with --agent: the repository to write the setup into
                        (default: this folder)
  --print               with --agent: print the skill and write nothing
                        (default: write the files)
  --json                print the file written as one JSON document instead of
                        text
  --store PATH          the store folder (default: $POISSON_PROVE_STORE when
                        set, else ./prove-runs)
  --plain               print plain text, as a pipe gets it, on a terminal too
                        (default: pretty on a terminal, plain otherwise)
  --debug               also print the traceback of an unexpected failure

examples:
  poisson-prove init --example
  poisson-prove init --target my_agent:rollout
  poisson-prove init --agent
```

## Options

- `--example` writes the keyless quickstart: the mock agent over three tasks and three tool
  failure rates, 194 replicates each. It runs as it is: `poisson-prove sweep` next.
- `--target pkg.module:rollout` fills the template's `target` with your rollout, so `sweep` finds
  it without `--target`.
- `--out PATH` writes to another file than `./prove.toml`; `sweep` then takes that file's name.
- `--force` replaces a file that exists. Without it an existing file is refused and left as it is.
- `--runs-on local`, `--runs-on modal` or `--runs-on cloud` says where sweeps of the spec run,
  and `init` then asks nothing: `local` writes the spec alone, `modal` adds a `[modal]` table,
  and `cloud` adds a `[cloud]` table with the defaults the question offers (AWS, `us-east-2`,
  four `m7i.2xlarge` nodes, stop at $2.00, refuse above $3.00). It then checks that this machine
  is ready, as [`poisson-prove where`](where.md) does, and says what to do when it is not. It
  goes with a spec, not with `--agent`. On Windows `--runs-on cloud` is refused before anything is
  written.
- `--agent` writes the setup for your coding agent instead of a spec: a skill, `SKILL.md`, and the
  prompt to give it, `prompt.txt`, in `.agents/skills/poisson-prove-setup/` and
  `.claude/skills/poisson-prove-setup/`. [Set Prove up with your coding agent](../setup-with-your-agent.md)
  says what the skill asks of your agent.
- `--repo DIR`, with `--agent`, writes the setup into another folder.
- `--print`, with `--agent`, prints the skill and writes nothing.
- `--json` prints what was written as one JSON document.
- `--store PATH`, `--plain` and `--debug` are the options every verb takes: the store folder
  (`init` reads none), plain text on a terminal too, and the traceback of an unexpected failure.

## Examples

The keyless example, then a template for your own rollout in a second file:

<!-- docs-check: run -->
```console
$ poisson-prove init --example
ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates
  next: poisson-prove sweep
$ poisson-prove init --target my_rollout:rollout --out mine.toml
ok  wrote mine.toml: a template; set its axes to what you vary
  next: poisson-prove sweep mine.toml
```

A file that exists is refused, and the refusal says how to replace it:

<!-- docs-check: run -->
```console
$ poisson-prove init --example  # exits 1
error: prove.toml exists; init replaces it only with --force
  next: poisson-prove init --example --force
```

`--runs-on` answers the question on the command line. `local` writes what `init` writes with no
answer:

<!-- docs-check: run -->
```console
$ poisson-prove init --example --runs-on local --out local.toml
ok  wrote local.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates
  next: poisson-prove sweep local.toml
```

`cloud` adds the `[cloud]` table and checks the sign-in; the account is shown masked. The table
is written even when a check fails, and the `next:` line is then the command that fixes it, such
as `aws login`:

<!-- docs-check: skip: needs your own AWS account -->
```console
$ poisson-prove init --example --runs-on cloud
ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates
  signed in  AWS 6030…4933
  wrote  [cloud] into prove.toml
  next: poisson-prove sweep --dry-run
```

In a terminal, with no `--runs-on`, `init` asks. Enter, or `1`, keeps this machine and adds
nothing to the spec:

<!-- docs-check: skip: a terminal session, since init asks only when stdin and stderr are both terminals -->
```console
$ poisson-prove init --example
ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates
where should sweeps run?  1 this machine (default)  2 Modal  3 your cloud account (AWS)
  next: poisson-prove sweep
```

`3` asks five more, one a line, each with its default in brackets; here every answer is Enter.
Google Cloud and Azure are listed as not yet supported and cannot be chosen:

<!-- docs-check: skip: a terminal session, since init asks only when stdin and stderr are both terminals -->
```console
$ poisson-prove init --example
ok  wrote prove.toml: a sweep of the keyless mock agent, 9 conditions x 194 replicates
where should sweeps run?  1 this machine (default)  2 Modal  3 your cloud account (AWS) 3
Google Cloud  not yet supported by Prove
Azure  not yet supported by Prove
region [us-east-2]
machine type [m7i.2xlarge]
nodes [4]
stop at [$2.00]
refuse above [$3.00]
  signed in  AWS 6030…4933
  wrote  [cloud] into prove.toml
  next: poisson-prove sweep --dry-run
```

The questions go to stderr and the result to stdout, so a script that reads stdout sees the same
lines either way. An answer that is not one of those offered keeps this machine, with a `note:`.
A value Prove cannot use (a region outside its price table, a word where a number goes) ends
`init` with exit 1 and `next: poisson-prove where cloud`: the spec is written and runs on this
machine until `where` sets it. To change the answer later, use
[`poisson-prove where`](where.md).

With `--json` and `--runs-on`, the one document also says where the spec runs (`runs_on`) and
whether that is ready on this machine (`ready`), and its `next` is the command that follows from
that. With `--json` alone the document is the one below, as it always was.

The setup for your coding agent, and the same as JSON for a script:

<!-- docs-check: run -->
```console
$ poisson-prove init --agent
ok  wrote the setup for your coding agent (4 files)
  wrote  .agents/skills/poisson-prove-setup/SKILL.md
  wrote  .agents/skills/poisson-prove-setup/prompt.txt
  wrote  .claude/skills/poisson-prove-setup/SKILL.md
  wrote  .claude/skills/poisson-prove-setup/prompt.txt
  prompt  Use the poisson-prove-setup skill in this repository: set Poisson Prove up for me to review, then stop.
  next: give your coding agent the prompt above, then review what it wrote
$ poisson-prove init --example --out other.toml --json
{
  "schema": "poisson-prove.init/1",
  "verdict": "ok",
  "wrote": ["other.toml"],
  "next": ["poisson-prove sweep other.toml"]
  …
}
```

## Exit codes

- `0`: the file, or the four files of `--agent`, were written (or printed, with `--print`).
- `1`: refused, and nothing was written: a file exists and `--force` was not given, or a folder
  cannot be written. Also a value at one of its questions that Prove cannot use: the spec is
  written then, and its where-to-run table is not.
- `2`: the command line is wrong, such as `--repo` without `--agent`, or `--runs-on` with it.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: interrupted with Ctrl-C.

## What it writes

`./prove.toml`, or the file `--out` names; with `--agent`, the four files above in the folder, or
in `--repo`. When the answer to its question is Modal or your cloud account, the spec it wrote
also holds that `[modal]` or `[cloud]` table. Nothing else: no store, no `.gitignore` entry, none
of your agent's own files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`). It stores no secret and
asks for none.
