# `poisson-prove init`

Writes a sweep spec and nothing else: the keyless example, or a commented template to edit for
your own rollout. With `--agent` it writes instead the setup your own coding agent follows, and
with `--demo` a small support bot that needs no key, to try Prove on. It never touches a store.

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
                          [--repo DIR] [--print] [--demo] [--with-setup]
                          [--json] [--store PATH] [--plain] [--debug]

Write a sweep spec, ./prove.toml unless --out names another file, and nothing
else: a commented template to edit, or with --example the keyless quickstart,
runnable as it is. With --agent, write instead the setup your own coding agent
follows (a skill and the prompt to give it), in the two folders coding agents read
skills from. With --demo, write instead a small support bot that needs no key, to
try Prove on. In a terminal, init then asks where sweeps of a spec it wrote should
run; --runs-on answers that on the command line, and off a terminal nothing is
asked.

options:
  -h, --help            show this help message and exit
  --example             write the keyless quickstart, which runs as it is
                        (default: the template)
  --target pkg.module:rollout
                        fill the template's target with this rollout (default:
                        a commented placeholder)
  --out PATH            the file to write (default: ./prove.toml)
  --force               replace what init writes if it exists (default:
                        refuse)
  --runs-on {local,modal,cloud}
                        where sweeps of this spec run: this machine, Modal or
                        your cloud account (default: asked in a terminal, this
                        machine otherwise)
  --agent               write the setup your own coding agent follows, a skill
                        and its prompt, instead of a sweep spec
  --repo DIR            with --agent or --demo: the folder to write into, made
                        by --demo when it is missing (default: this folder)
  --print               with --agent: print the skill and write nothing
                        (default: write the files)
  --demo                write the demo agent, a support bot that needs no key
                        (support_bot.py, prompts.py, demo.md), instead of a
                        sweep spec
  --with-setup          with --demo: also write the two files a coding agent
                        would, prove_rollout.py and prove.toml (default: the
                        demo alone)
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
  poisson-prove init --demo
```

## Options

- `--example` writes the keyless quickstart: the mock agent over three tasks and three tool
  failure rates, 194 replicates each. It runs as it is: `poisson-prove sweep` next.
- `--target pkg.module:rollout` fills the template's `target` with your rollout, so `sweep` finds
  it without `--target`.
- `--out PATH` writes to another file than `./prove.toml`; `sweep` then takes that file's name.
- `--force` replaces a file that exists, and only a file `init` was going to write. Without it an
  existing file is refused and left as it is.
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
- `--repo DIR`, with `--agent` or `--demo`, writes into another folder. `--demo` makes the folder
  when it is missing; `--agent` wants a folder that is there. With `--agent`, when `DIR` is
  another folder than this one, one more line, `open  your coding agent in DIR`, says where to
  start your coding agent: it reads the skill from the folder it is opened in.
- `--print`, with `--agent`, prints the skill and writes nothing.
- `--demo` writes the demo agent instead of a spec: `support_bot.py`, a support bot that calls no
  model and needs no key and no network; `prompts.py`, its system prompt; and `demo.md`, which says
  what it is and what to do with it. It is the stand-in [Your own agent](../your-own-agent.md)
  walks through. It asks nothing, and goes with `--with-setup`, `--repo`, `--force` and `--json`
  only.
- `--with-setup`, with `--demo`, also writes the two files a coding agent would write for the demo:
  `prove_rollout.py` and `prove.toml`, three tickets at two temperatures, 194 replicates each. The
  demo then sweeps as it is, for someone with no coding agent. Its spec declares that a rollout
  costs nothing (`usd_per_rollout = 0` under `[cost]`), so its plan reads `$0`.
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

The example's spec ends with a `[cost]` table, `usd_per_rollout = 0`: the mock agent calls no
model, so the spec declares that a rollout costs nothing and its plan reads `$0`. A template
declares no `[cost]`, and its plan says your agent's own calls are not priced until you declare
what a rollout costs ([The sweep spec](../sweep-spec.md#cost)). Prove 0.4.0 and earlier refuse a
spec that has a `[cost]` table.

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

The setup for your coding agent, and the same as JSON for a script. The `more` line says where to
ask for more than your cases: the skill writes your cases as the one axis, so to compare anything
else, add it to the prompt in your own words ("Also compare temperature 0 and 0.7."):

<!-- docs-check: run -->
```console
$ poisson-prove init --agent
ok  wrote the setup for your coding agent (4 files)
  wrote  .agents/skills/poisson-prove-setup/SKILL.md
  wrote  .agents/skills/poisson-prove-setup/prompt.txt
  wrote  .claude/skills/poisson-prove-setup/SKILL.md
  wrote  .claude/skills/poisson-prove-setup/prompt.txt
  prompt  Use the poisson-prove-setup skill in this repository: set Poisson Prove up for me to review, then stop.
  more  to compare more than your cases, add it to the prompt in your own words
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

The setup written into another folder, with the line that says where to open your coding agent.
The line is printed only when `--repo` names another folder than this one, read after links and
relative parts are resolved; the four files are the same either way.

<!-- docs-check: run -->
```console
$ mkdir my-agent
$ poisson-prove init --agent --repo my-agent
ok  wrote the setup for your coding agent (4 files)
  wrote  my-agent/.agents/skills/poisson-prove-setup/SKILL.md
  wrote  my-agent/.agents/skills/poisson-prove-setup/prompt.txt
  wrote  my-agent/.claude/skills/poisson-prove-setup/SKILL.md
  wrote  my-agent/.claude/skills/poisson-prove-setup/prompt.txt
  open  your coding agent in my-agent
  prompt  Use the poisson-prove-setup skill in this repository: set Poisson Prove up for me to review, then stop.
  more  to compare more than your cases, add it to the prompt in your own words
  next: give your coding agent the prompt above, then review what it wrote
```

The demo agent, into a folder of its own, and then with the two files a coding agent would write:

<!-- docs-check: run -->
```console
$ poisson-prove init --demo --repo support-bot
ok  wrote the demo agent, a support bot that needs no key (3 files)
  wrote  support-bot/support_bot.py
  wrote  support-bot/prompts.py
  wrote  support-bot/demo.md
  next: poisson-prove init --agent --repo support-bot
$ poisson-prove init --demo --with-setup --repo support-bot  # exits 1
error: support-bot/support_bot.py, support-bot/prompts.py and support-bot/demo.md already exist; init --demo replaces them only with --force
  next: poisson-prove init --demo --with-setup --repo support-bot --force
$ poisson-prove init --demo --with-setup --repo support-bot --force
ok  wrote the demo agent, a support bot that needs no key (5 files)
  wrote  support-bot/support_bot.py
  wrote  support-bot/prompts.py
  wrote  support-bot/demo.md
  wrote  support-bot/prove_rollout.py
  wrote  support-bot/prove.toml
  next: poisson-prove sweep support-bot/prove.toml
```

Without `--repo` the files go into this folder, and the `next:` lines are
`poisson-prove init --agent` and, with `--with-setup`, `poisson-prove sweep`.

## Exit codes

- `0`: the file, the four files of `--agent` or the files of `--demo` were written (or printed,
  with `--print`).
- `1`: refused, and nothing was written: a file exists and `--force` was not given, or a folder
  cannot be written. Also a value at one of its questions that Prove cannot use: the spec is
  written then, and its where-to-run table is not.
- `2`: the command line is wrong, such as `--repo` without `--agent` or `--demo`, `--runs-on`
  with either, `--demo` with `--example`, `--target`, `--out`, `--agent` or `--print`, or
  `--with-setup` without `--demo`.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: interrupted with Ctrl-C. Under `--demo`, each file already in place is whole and is
  named, the rest are not written, and `--force` is the way on.

## What it writes

`./prove.toml`, or the file `--out` names; with `--agent`, the four files above in the folder, or
in `--repo`; with `--demo`, the demo's three files, or five with `--with-setup`, in the folder or
in `--repo`, never a `README.md`. When the answer to its question is Modal or your cloud account, the spec it wrote
also holds that `[modal]` or `[cloud]` table. Nothing else: no store, no `.gitignore` entry, none
of your agent's own files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`). It stores no secret and
asks for none.
