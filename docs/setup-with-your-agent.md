# Set Prove up with your coding agent

`poisson-prove init --agent` writes a skill your own coding agent follows, and the prompt to give
it. Your agent reads your code, writes the two files Prove needs (`prove_rollout.py` and
`prove.toml`), runs `poisson-prove sweep --dry-run` until it passes (fixing at most three times), and stops for you to review
what it wrote. Prove makes no model call and reads no key; your agent does the work, and you run the
sweep yourself.

```bash
poisson-prove init --agent
```

It writes four files and nothing else: the skill, `SKILL.md`, and the prompt, `prompt.txt`, in each
of two folders, because the coding agents do not all read skills from the same place.

| folder | read by |
|---|---|
| `.agents/skills/poisson-prove-setup/` | Codex, Cursor |
| `.claude/skills/poisson-prove-setup/` | Claude Code, Cursor |

Checked against each agent's own documentation on 2026-10-24. Cursor reads both folders, so it
finds the same skill twice.

The prompt it prints, and saves in each `prompt.txt`:

```text
Use the poisson-prove-setup skill in this repository: set Poisson Prove up for me to review, then stop.
```

- An existing file is refused, naming each; `--force` replaces those four files and nothing else.
- `--repo DIR` writes into another folder; `--print` prints the skill and writes nothing.
- `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/` and your other files are never written.

## Each case is its own sweep axis

The skill tells your agent to make the cases its own sweep axis: one axis whose values are the case
ids, and a wrapper that picks its case from `cfg` (never from the seed) and returns
`Episode(..., meta={"case_id": ...})`. A condition then runs one case, and a comparison whose
condition reports different case ids is refused.

## What the check reports

`poisson-prove sweep --dry-run` imports your wrapper in a process of its own, with outbound network
connections blocked and a 30 s limit, checks that it takes `(cfg, seed)`, and never calls it. The
block covers Python code in that process; a separate program the import starts is not covered, so a
wrapper should start nothing when it is imported. When something is wrong it says
what, with an `error:` line and `next:` lines; when everything is right it prints the plan, with the
`target` and `outcomes` lines, and spends nothing.
