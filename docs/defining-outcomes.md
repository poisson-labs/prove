# Defining outcomes

Prove compares the rate of an outcome between two runs. Everything it
reports — the change, the verdict, the detection limit — is downstream of
one thing you choose before the first episode runs: **what the outcome labels
mean.**

The instrument never infers that meaning. It cannot. `crashed` is a string, and
the tool has no way to know whether it names your agent throwing an exception,
your sandbox running out of memory, or your API key having no balance left on
it. It will happily and correctly measure the difference in `crashed` rate
between two runs where the label meant different things on different days.

This page is the one rule that matters, the case that taught it, and a checklist.

---

## The rule

> **An outcome names what happened to the system under test. It never names what
> happened to the instrument.**

A *system failure* is the thing you are measuring: the agent wrote a wrong
patch, exhausted its horizon, violated a constraint, returned an unparseable
tool call.

An *instrument failure* is everything between you and the system: the provider
returned 429, the balance was empty, the container was OOM-killed, the network
dropped, the sandbox image failed to build, a dependency was yanked.

They are different events with different causes, and mixing them into one label
produces a number that looks exactly like a finding.

The test to apply to any candidate label:

> **If I re-ran this identical episode against a *different* candidate, would
> this outcome have been just as likely?**

If yes, it is an instrument failure and it must not share a label with anything
else. An instrument failure is a property of the day, the account and the
network. A system failure is a property of the thing you are comparing.

---

## The case: a legal outcome, a well-formed row, every gate green

From an early pilot: an agent run against a suite of coding problems.

The pilot agent had four outcomes: `passed`, `failed_assertion`, `timed_out`,
`crashed`. Four separate places in the agent assigned `crashed`: the model call
returned no content, the repair turn returned no content, the response could not
be parsed as a tool call, and a defensive fallback at the return. The first two
are *the API failed*. The third is *the agent failed*. They are the same label.

One arm of the pilot ran with an empty balance on the provider account. Every
call failed. Every episode ended `crashed`. And:

- the outcome was **legal** — `crashed` is in the declared vocabulary;
- the row was **well formed** — `outcome`, `t`, `horizon`, `config_hash`,
  `replicate_index`, all valid;
- a **trace was attached** to every episode;
- `t` was inside `[0, horizon]` and the `t_unit` matched the manifest;
- `poisson-prove runs` would have reported **0 rows without an outcome** for that arm — and
  that number is *correct*: every episode did have an outcome. Its label was
  `crashed`.

Every gate the tool has was green. Nothing anywhere was red. The arm was
worthless.

At a 100% failure rate it was obvious within a minute of looking. The reason
this page exists is the other case: **at 1%, split across two arms run hours
apart under different provider load, it is invisible, and it reads as a real
effect.** Arm B's apparent rise in crash rate would have been the provider having
a bad afternoon while arm B happened to be running.

---

## Why the analysis cannot rescue you

The distinction did exist in the data. The pilot recorded
`meta["crash_reason"]` on every crashed episode, and the API failures were
distinguishable from the parse failures by that string.

It made no difference, because **`diff` never reads `meta`.**

The comparison verbs read the frame narrow — `config_hash`, `config`,
`replicate_index`, `outcome`, `t`, `horizon`, and the `case_id` a rollout
recorded, which they read only to refuse a condition that ran several cases —
and nothing else. This is not an oversight to be fixed. It is deliberate and it
is load-bearing:

- Reading `meta` on a large store — 25,600 rows, about 9.7 KB of trace per
  row — took 6.1 s and 1.13 GB of peak memory, against 0.18 s without it,
  because `meta` carries the traces. `diff`, `report` and `check` all read with `meta=False`,
  and a deliberately poisoned-`meta` store in the test suite proves they never
  decode it.
- More importantly, a comparison that reached into free-form metadata would be a
  comparison whose meaning depended on a schema nobody declared. Two runs could
  carry different `meta` shapes and the diff would silently mean different
  things.

`inspect` reads `meta`, because it prints rows for a human rather than computing
a statistic over them. That is the only verb that does.

So:

> **A distinction that lives only in `meta` cannot be seen by the analysis. If it
> matters to the comparison, it has to be in the outcome label.**

You can find the conflation after the fact with `poisson-prove inspect`, if you
think to look. You cannot correct for it in the diff, and nothing will tell you
to look.

---

## What Prove does and does not check

Worth being exact, because "every gate was green" is the part of the story people
find hardest to believe.

| the tool checks | the tool does not check |
|---|---|
| the outcome is a string, and `t` is inside `[0, horizon]` | what the outcome *means* |
| `t_unit` matches between the two runs being compared | that the two runs' labels were assigned by the same rule |
| how many rows were stored with **no** outcome (`rows without an outcome`) | whether a stored outcome was the right one |
| which cells are holes, and why (`unsampled`, `no_outcome_a`, …) | whether a *populated* cell is populated with garbage |
| that a paired method is only run on pairable runs | that two pairable runs were run under the same conditions |
| what size of change each condition could have detected (the detection limit) | whether the change it detected is a change in your system |

Every row on the left is a real guard and each is worth having. None of them
would have caught the dead arm, and none of them is meant to.

---

## Checklist, before the first episode runs

**1. Write the vocabulary down, with a one-line definition of each label.**
If a label needs "or" in its definition, it is two labels.

**2. Give every instrument failure its own terminal outcome.**
Not a flag in `meta`, not a reason-string prefix — an outcome, in the declared
vocabulary, so the difference survives into `diff`. For the case above that
means an `api_error` label that is not `crashed`.

**3. Check every assignment site, not every label.**
The pilot declared four labels and assigned them in six places. The bug was that
four of those six wrote `crashed`, for reasons that were not the same kind of
thing. Read the code that assigns, not the tuple that declares.

**4. Ask the re-run question of each label.** *If this episode ran against a
different candidate, would this outcome have been just as likely?* Anything that
answers yes goes in its own bucket.

**5. Look for these three conflations specifically.** They are the ones that
recur:

- **`crashed`** — the agent's own failure, versus anything between you and the
  model. The case above.
- **`timed_out`** — the agent exhausting its declared horizon, versus a sandbox
  wall clock cutting off a slow candidate. The first is a property of the
  candidate; the second is a property of the machine that day, and it is
  *biased*: a slower candidate hits it more often, so it looks like a
  behavioural difference.
- **`passed`** — the task actually solved, versus the harness failing to detect
  a failure. A verifier that errors and defaults to pass is an instrument
  failure wearing the success label, which is the worst direction for this to
  go in.

**6. Print the outcome distribution before you diff.**
One line per label per arm. The dead arm was 100% one label; a glance would have
caught it. Today this is a `poisson-prove inspect` call or three lines of pandas over
the store — do it anyway, and do it before you look at the comparison.

**7. Decide what you will do if it happens anyway.**
There is exactly one honest window to change the analysis after seeing the data:
before any comparison is run, when the change is stated and recorded. The pilot
amended its pre-registration to exclude API-error crashes by `crash_reason`
prefix, in writing, before diffing. That is a stopgap and it is why the outcome
change exists. Excluding rows *after* seeing which way the comparison went is
not a repair; it is the finding being chosen.

---

## The short version

A well-formed row with a legal outcome, a full trace and a green gate can still
be a number about your provider's billing rather than about your system. The
instrument cannot tell the difference, by design — it never infers what your
labels mean, because a tool that guessed would be wrong silently and at scale.

Deciding what your outcomes mean is the one part of the measurement that is
yours, and it is the part that cannot be corrected afterwards.
