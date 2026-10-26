# Set Prove up with your coding agent

`poisson-prove init --agent` writes a skill your own coding agent follows, and the prompt to give
it. Your agent reads your code, writes the two files Prove needs (`prove_rollout.py` and
`prove.toml`), runs `poisson-prove sweep --dry-run` until it passes (fixing at most three times),
and stops for you to review what it wrote. Prove makes no model call and reads no key; your agent
does the work, and you run the sweep yourself.

<!-- docs-check: run -->
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

<!-- docs-check: skip: the prompt you give your coding agent, not a command -->
```text
Use the poisson-prove-setup skill in this repository: set Poisson Prove up for me to review, then stop.
```

- An existing file is refused, naming each; `--force` replaces those four files and nothing else.
- `--repo DIR` writes into another folder; `--print` prints the skill and writes nothing.
- `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/` and your other files are never written.

## What the skill asks your agent to do

Six steps, in order. The skill says each in full; here is what each is for.

1. **Find the agent's entry point.** It reads your code and runs nothing: where one case runs end
   to end, which client calls the model, what varies between cases, and how a case can end.
2. **Write the rollout wrapper.** `prove_rollout.py` at the repository root, with
   `rollout(cfg, seed)`: it runs the case `cfg` names, maps how it ended to an outcome, and returns
   an `Episode` with the case's id in `meta`. It calls nothing when it is imported and reads no
   key; your code reads its own keys, as it does today.
3. **Write the sweep spec.** `prove.toml` with the target, the conditions worth comparing as axes,
   and the cases as one axis of their own.
4. **Declare the outcomes.** A `[declare]` table: every outcome the wrapper can return, and which
   are failures and which successes.
5. **Run the check.** `poisson-prove sweep --dry-run`. If the design is too small, it writes the
   replicates the check names into `prove.toml` and runs it again; for anything else, it fixes what
   the `error:` line says. Three fixes at most.
6. **Stop and hand over.** It lists the files it wrote and why, pastes the check's last output,
   lists what you must confirm (the axes, the outcomes and their kinds, the replicates and what
   they will cost, how endings map to outcomes), and gives you the one command to run next:
   `poisson-prove sweep`.

Its rules: it never runs a sweep without `--dry-run` and never passes `--yes`, so nothing is spent;
it never reads, prints or writes a key or a `.env` file; it installs nothing; it changes nothing
outside its two files, and never touches `prove-runs/` or `.poisson/`; and it quotes Prove's
output, never rewording it.

## Each case is its own sweep axis

The skill tells your agent to make the cases its own sweep axis: one axis whose values are the case
ids, and a wrapper that picks its case from `cfg` (never from the seed) and returns
`Episode(..., meta={"case_id": ...})`. A condition then runs one case, and a comparison whose
condition reports different case ids is refused. [Your own agent](your-own-agent.md#one-case-per-condition)
shows why, and the refusal.

## What the check reports

`poisson-prove sweep --dry-run` imports your wrapper in a process of its own, with outbound network
connections blocked and a 30 s limit, checks that it takes `(cfg, seed)`, and never calls it. The
block covers Python code in that process; a separate program the import starts is not covered, so a
wrapper should start nothing when it is imported. When something is wrong it says
what, with an `error:` line and `next:` lines; when everything is right it prints the plan, with the
`target` and `outcomes` lines, and spends nothing.

## After the review

Read `prove_rollout.py` and `prove.toml` as you would any change to your repository: the mapping of
endings to outcomes is the part that decides what the numbers mean
([Defining outcomes](defining-outcomes.md)). Then run the sweep, change your agent, and sweep again
with `--pair-with latest`, as in the [quickstart](quickstart.md).
