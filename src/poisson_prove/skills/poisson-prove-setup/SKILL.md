---
name: poisson-prove-setup
description: Set up Poisson Prove in this repository so the person can compare runs of their agent before and after a change. Use when asked to set up Prove or poisson-prove.
metadata:
  poisson-setup-format: "1"
  poisson-tool: poisson-prove
  poisson-tool-version: "filled in when the skill is written"
  poisson-writes: prove_rollout.py prove.toml
  poisson-check: poisson-prove sweep --dry-run
---

# Set up Prove in this repository

## What you are doing

Poisson Prove runs the person's agent many times under conditions they choose, once before a change and once after, and says which conditions got worse, which got safer and which it could not tell apart, with stated error bounds and detection limits. You write two files that let Prove run the agent: a rollout wrapper that runs one case end to end, and a sweep spec that says what to vary. You run Prove's check, which spends nothing, and you hand the result over for the person to review; the person runs the sweep itself, never you.

## Rules

- Do only what these steps say. Change nothing outside the files listed under "Files you write".
- Run nothing that can spend money or call a model. The only poisson-prove commands you run are the ones
  these steps show, and the check runs with its own flag that spends nothing.
- Never pass --yes, or any flag that answers a question for the person.
- Never read, print, copy or write an API key, a token or a .env file, and never ask the person for one.
- Install nothing. If poisson-prove is not installed where this repository runs, stop and tell the person
  the install command from https://pypi.org/project/poisson-prove/.
- When something is unclear, choose the smaller change and say in the hand-over what you chose and why.
- Quote Prove's output as it prints it. Never reword a verdict, a number or an error.
- If you cannot finish, stop and say what blocked you.

### Prove's own rules

- Never run `poisson-prove sweep` without `--dry-run`.
- Never touch `prove-runs/` or `.poisson/`: they hold the person's runs.
- Change nothing outside `prove_rollout.py` and `prove.toml`, even to make the check pass.

## Files you write

- `prove_rollout.py`: the rollout wrapper, `rollout(cfg, seed)`, which runs one case through the agent's own entry point and names how it ended.
- `prove.toml`: the sweep spec: the target, the conditions to vary (the cases among them), the replicates and the outcomes.

## Steps

1. **Find the agent's entry point.** Read the code; run nothing. Find the function or command that runs one case end to end, where the model is called and through which client, what varies between cases (the prompt, the model, the tools, the temperature, retries, the set of cases), and how a case can end (a success, a refusal, an error of some type, a time-out, a guard).
2. **Write the rollout wrapper.** Write `prove_rollout.py` at the repository root with `def rollout(cfg: dict, seed: int) -> Episode`. It runs the entry point on the case `cfg` names, with the other values in `cfg` and with `seed`; it maps how the case ended to an outcome name; and it returns `poisson_prove.Episode(outcome=..., t=..., horizon=..., meta={"case_id": ...})`, the id of the case it ran in `meta["case_id"]` on every ending. It picks the case from `cfg`, never from `seed`. It imports nothing that calls the model when it is imported, reads no key itself (the agent's own code reads its keys as it does today), and does nothing else.
3. **Write the sweep spec.** Write `prove.toml` at the repository root with `target = "prove_rollout:rollout"`, a `target_id`, `t_unit`, and the conditions worth varying as `[axes.NAME]` tables: what the code shows varies and a person would want to compare, two or three axes of two to four values each, besides the cases. Each case is its own sweep axis: add one axis whose values are the case ids, as many as there are, so that one condition never runs more than one case (Prove refuses to compare a condition whose episodes report different case ids). Set `replicates = 20` for now; the check says what it should be.
4. **Declare the outcomes.** Add a `[declare]` table: `outcomes`, every outcome name the wrapper can return; then `failures` and `successes`, each from what the code shows. No outcome is in both.
5. **Run the check.** Run it from the repository root, as "The check" below shows. If it refuses because the design is too small, write the number its `next:` line gives after `--replicates` into `replicates` in `prove.toml`, and run it again. If it refuses for anything else, fix what the `error:` line names.
6. **Stop and hand over.** Do what "Hand over" below says, and nothing more.

## The check

Run this. It reads what you wrote, spends nothing and changes nothing.

```bash
poisson-prove sweep --dry-run
```

- If it exits 0, its first line starts with a word such as `plan` or `ok`: the setup is ready for the
  person to review. Go to "Hand over".
- If it exits 1, it printed `error:` and then `next:` lines. Do what the `error:` line names, using
  the `next:` lines, and run the check again.
- If it exits 2, the command line or a setting it needs was wrong; the `error:` line says which. Fix
  what it names.
- Fix at most three times. If the check still fails, stop and hand over what you have, with the last
  output.

## Hand over

Stop here and tell the person, in this order:

1. Each file you wrote, with one line on why it is there.
2. The last output of the check, exactly as printed.
3. What they must confirm before running anything for real (the list below).
4. The one command they run next themselves, in its own block:

   ```text
   poisson-prove sweep
   ```

Do not run that command for them.

What the person must confirm:

- The axes and their values: are these the conditions they want compared, and is every case its own value?
- The outcomes and their kinds: is each failure a failure and each success a success?
- The replicates, and what running them will cost: each rollout runs the agent once, with all its model calls.
- How the wrapper maps each way a case can end to an outcome.

## Words Prove uses

- `worse` and `safer`: a failure rose or fell (or a success fell or rose) in a condition, beyond what chance explains.
- `trade`: some conditions got worse and others safer.
- `higher`, `lower` and `mixed`: the same, for an outcome declared neither a failure nor a success.
- `no significant change` and `too small to tell`: nothing moved that the design could have seen, or the design was too small to see it.
