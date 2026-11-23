# Set Prove up with your coding agent

`poisson-prove init --agent` writes a skill your own coding agent follows, and the prompt to give
it. Your agent reads your code, writes the two files Prove needs (`prove_rollout.py` and
`prove.toml`), runs `poisson-prove sweep --dry-run` until it passes (fixing at most three times),
asks you before it calls your agent once on one real case with `poisson-prove sweep --try`, and
stops for you to review what it wrote: a first line that says `ready:` or `not ready:`, then the
whole loop for you to run. Prove makes no model call and reads no key; your agent does the work,
and you run every sweep yourself.

Where sweeps run is your choice, not your agent's. The skill does not ask it or set it: the spec
it writes runs on this machine, and `poisson-prove where` moves it to Modal or your own cloud
account when you want that. (`poisson-prove init` asks the same question when you write a spec
yourself in a terminal.)

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

The skill has your agent write your cases and nothing more to compare. To compare more than your
cases, add it to the prompt in your own words, with the values you want:

<!-- docs-check: skip: the prompt you give your coding agent, not a command -->
```text
Use the poisson-prove-setup skill in this repository: set Poisson Prove up for me to review, then stop. Also compare temperature 0 and 0.7.
```

`init --agent` says so on a line of its own under the prompt:
`more  to compare more than your cases, add it to the prompt in your own words`.

- An existing file is refused, naming each; `--force` replaces those four files and nothing else.
- `--repo DIR` writes into another folder; `--print` prints the skill and writes nothing. When
  `DIR` is another folder than the one you are in, one more line says where to start your coding
  agent, since it reads the skill from the folder it is opened in:
  `open  your coding agent in DIR`.
- `AGENTS.md`, `CLAUDE.md`, `.cursor/rules/` and your other files are never written.

## Practise on the demo

With no agent of your own at hand, `poisson-prove init --demo` writes a small support bot into
this folder: a stand-in that calls no model and needs no key and no network. Run
`poisson-prove init --agent` beside it and give your coding agent the prompt, as above; the
`demo.md` it comes with says what to change between the two sweeps. The one call of step 6 costs
nothing there: the demo calls no model. With no coding agent either,
`poisson-prove init --demo --with-setup` also writes the two files your agent would, and
`poisson-prove sweep` runs them as they are. That spec carries a `[cost]` table with
`usd_per_rollout = 0`, which declares that a rollout costs nothing, so the demo's plan reads `$0`;
Prove wrote it, with the tickets and a temperature as its two axes.

For an agent on a real model,
[`examples/your-first-real-agent/`](https://github.com/poisson-labs/prove/tree/main/examples/your-first-real-agent)
is a small agent that calls a real model (OpenAI's `gpt-4.1-mini`). It needs an OpenAI API key in
`OPENAI_API_KEY`, `pip install "poisson-prove[agent]"`, and a network; each sweep makes 1,200
short requests, billed to your OpenAI account. Without the key every case errors and the sweep
stops; without a network every case ends `api_error`.

## What the skill asks your agent to do

Seven steps, in order. The skill says each in full; here is what each is for.

1. **Find the agent's entry point.** It reads your code and runs nothing: where one case runs end
   to end, which client calls the model, what varies between cases, and how a case can end.
2. **Write the rollout wrapper.** `prove_rollout.py` at the repository root, with
   `rollout(cfg, seed)`: it runs the case `cfg` names, maps how it ended to an outcome, and returns
   an `Episode` with the case's id in `meta`. It calls nothing when it is imported and reads no
   key; your code reads its own keys, as it does today.
3. **Write the sweep spec.** `prove.toml` with the target and the cases as one axis of their own,
   and one more axis only for each thing you asked to compare, with the values you named. It adds
   no other axis, and never one over the model, the provider or a setting that changes what a
   call is billed at (the temperature, the reasoning effort, a token limit) unless you asked for
   it: every value of an axis multiplies the rollouts, and those are the axes that also change
   what each one costs. For an agent that calls no model it also writes a `[cost]` table with
   `usd_per_rollout = 0`; it never writes another figure, since what a rollout costs is yours to
   declare ([the sweep spec](sweep-spec.md#cost)).
4. **Declare the outcomes.** A `[declare]` table: every outcome the wrapper can return, and which
   are failures and which successes.
5. **Run the check.** `poisson-prove sweep --dry-run`. If the design is too small, it writes the
   replicates the check names into `prove.toml` and runs it again; for anything else, it fixes what
   the `error:` line says. Three fixes at most. The replicates the check names are sized for the
   paired sweep that follows the first one.
6. **Call it once.** The check imports your wrapper and never calls it, so a wrapper that fails
   on every call still passes. So your agent asks you: "Next I call your agent once, on one real
   case, at your agent's own cost (its model calls for one case). May I?" Only on a yes it runs
   `poisson-prove sweep --try --yes`, which calls the rollout once on this machine and stores
   nothing ([the trial call](commands/sweep.md#the-trial-call---try)). When the call returns an
   outcome, it goes on. When the call fails with its `raised in` line naming `prove_rollout.py`,
   the wrapper is wrong: it fixes the wrapper (one of the three fixes), runs the check again and
   asks again. When the call fails anywhere else (your agent's own code, a missing key, no
   network, a refused request, the limit), it changes nothing and hands over as not ready. On a
   no it makes no call and hands over as not ready, saying so.
7. **Hand over.** It stops and tells you, in this order:
   - a first line, `ready: the check passed and one real call returned "<outcome>"`, or
     `not ready: <what failed, quoted>`;
   - each file it wrote and why;
   - each axis, with its values and one line on why those values;
   - axes I did not add: up to three things your code shows could vary and it left out, each with
     the values it would take, the factor it would multiply the rollouts by, and how to add it
     (ask again naming it, or add its `[axes.NAME]` table and run `poisson-prove sweep --dry-run`);
     "none" when your code shows nothing else;
   - the last output of the check and of the call, as printed;
   - what you must confirm: the axes, the outcomes and their kinds, how endings map to outcomes,
     and the replicates and what they will cost. The cost item has a fixed shape: the plan's
     headline as printed; the rollouts of one sweep and of the loop, which is two sweeps; the
     model calls one rollout makes, as your code shows them, or "none: this agent calls no
     model"; the trial's `model calls` and `tokens` lines, when it printed them; the sentence
     "Prove's plan does not price your agent's own calls unless `prove.toml` declares `[cost]`";
     and how to declare it. Your coding agent gives no dollar figure of its own;
   - the whole loop, each command in its own block, for you to run, and after it which outcomes
     the comparison reads and which it leaves out.

Its rules: it never runs a sweep itself, only the check with `--dry-run` and the one call with
`--try`; it passes `--yes` to that one call alone, and only after you said yes to it, so nothing
is spent without your word; it never reads, prints or writes a key or a `.env` file; it installs
nothing; it changes nothing outside its two files, and never touches `prove-runs/` or
`.poisson/`; it leaves where sweeps run to you; and it quotes Prove's output, never rewording it.

## The loop it hands over

The hand-over ends with the loop, which is yours to run. When the first line says `not ready:`,
fix what it names (a key to set, a network to reach, a bug in your agent the call found) and make
the call yourself until it returns an outcome:

<!-- docs-check: skip: needs the two files your coding agent writes for your own agent -->
```bash
poisson-prove sweep --try
```

Then, ready or not ready before, the loop itself: a sweep before your change, the change, a sweep
after it on the same seeds, and the comparison. The notes say what each run was, and every
comparison shows them beside the runs:

<!-- docs-check: skip: needs the two files your coding agent writes for your own agent -->
```bash
poisson-prove sweep --note "before: <what this version is>"
# now make the change you want to test, in your agent's own code
poisson-prove sweep --pair-with latest --note "<what you changed>"
poisson-prove diff
```

`poisson-prove diff` with no event named compares the outcomes your `[declare]` table names a
failure or a success, and leaves out the ones it names neither. The hand-over says which are
compared and which are left out, with one block for each outcome left out, and `diff` says the
same on its `inferred:` line:

<!-- docs-check: skip: needs the two files your coding agent writes for your own agent -->
```bash
poisson-prove diff --event guardrail_blocked
```

When every declared outcome is a failure or a success, the hand-over says "every declared outcome
is compared" and gives no such block.

The command line says the same as you go: a complete first sweep of your own agent ends with
`then  change your agent; the next sweep runs it on the same seeds` and a `next:` that is the
paired sweep, naming the run.

## Each case is its own sweep axis

The skill tells your agent to make the cases its own sweep axis: one axis whose values are the case
ids, and a wrapper that picks its case from `cfg` (never from the seed) and returns
`Episode(..., meta={"case_id": ...})`. A condition then runs one case, and a comparison whose
condition reports different case ids is refused. [Your own agent](your-own-agent.md#one-case-per-condition)
shows why, and the refusal.

## What the check and the call report

`poisson-prove sweep --dry-run` imports your wrapper in a process of its own, with outbound network
connections blocked and a 30 s limit, checks that it takes `(cfg, seed)`, and never calls it. The
block covers Python code in that process; a separate program the import starts is not covered, so a
wrapper should start nothing when it is imported. When something is wrong it says
what, with an `error:` line and `next:` lines; when everything is right it prints the plan, with the
`target` and `outcomes` lines, and spends nothing.

`poisson-prove sweep --try` then makes one real call, in a process of its own with the network
allowed, on the spec's first condition, and stores nothing. A good call prints `ok`, the outcome
it returned and how long it took; a call that raises, runs past its limit (300 s, or
`--episode-timeout`) or returns something a sweep could not store exits 1 with one `error:` line
and, for a raise, the file and line it was raised in. What your agent prints during the call
goes to stderr. The call runs on this machine even when the spec is set to Modal or your cloud
account, so the keys your agent reads must be set here for it.

## After the review

Read `prove_rollout.py` and `prove.toml` as you would any change to your repository: the mapping of
endings to outcomes is the part that decides what the numbers mean
([Defining outcomes](defining-outcomes.md)). Then run the loop above: the sweep, your change, the
sweep again with `--pair-with latest`, and `poisson-prove diff`, as in the
[quickstart](quickstart.md). To run the sweeps on Modal or your own cloud account, say so first
with [`poisson-prove where`](commands/where.md).
