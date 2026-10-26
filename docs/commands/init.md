# `poisson-prove init`

Writes a sweep spec and nothing else: the keyless example, or a commented template to edit for
your own rollout. With `--agent` it writes instead the setup your own coding agent follows. It
asks no question and never touches a store.

## Help

<!-- docs-check: run -->
```console
$ poisson-prove init --help
usage: poisson-prove init [-h] [--example] [--target pkg.module:rollout]
                          [--out PATH] [--force] [--agent] [--repo DIR]
                          [--print] [--json] [--store PATH] [--plain]
                          [--debug]

Write a sweep spec, ./prove.toml unless --out names another file, and nothing
else: a commented template to edit, or with --example the keyless quickstart,
runnable as it is. With --agent, write instead the setup your own coding agent
follows (a skill and the prompt to give it), in the two folders coding agents read
skills from. Nothing is asked.

options:
  -h, --help            show this help message and exit
  --example             write the keyless quickstart, which runs as it is
                        (default: the template)
  --target pkg.module:rollout
                        fill the template's target with this rollout (default:
                        a commented placeholder)
  --out PATH            the file to write (default: ./prove.toml)
  --force               replace the file if it exists (default: refuse)
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
}
```

## Exit codes

- `0`: the file, or the four files of `--agent`, were written (or printed, with `--print`).
- `1`: refused, and nothing was written: a file exists and `--force` was not given, or a folder
  cannot be written.
- `2`: the command line is wrong, such as `--repo` without `--agent`.
- `3`: an unexpected failure; `--debug` prints its traceback.
- `130`: interrupted with Ctrl-C.

## What it writes

`./prove.toml`, or the file `--out` names; with `--agent`, the four files above in the folder, or
in `--repo`. Nothing else: no store, no `.gitignore` entry, none of your agent's own files
(`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`).
