# The τ²-bench pilot

A Proofload rollout wrapper over **sierra-research/tau2-bench** (τ³), airline domain, and the
ten-episode measurement it exists to make. This is step one of T.4 and it is **not a sweep**:
there is no pair, no diff, no report and no finding here. What it produces is the number nothing
else can supply — what one τ² episode costs, how long it takes, and whether the same
`(cfg, seed)` gives the same outcome twice.

τ² is **not forked and not patched**. It is installed from a pinned commit inside the image and
used through three public entry points: `registry.get_tasks_loader`, `build_text_orchestrator`
and `run_simulation`. Nothing in `src/proofload` changed and no test moved.

## The three decisions, and why

**Domain: airline.** It is the only τ² domain whose every task is graded without an LLM judge —
all 50 airline tasks carry `reward_basis == [DB, COMMUNICATE]`, a deterministic database
comparison and a substring search over the agent's own messages. Retail puts `NL_ASSERTION` on
112 of its 114 tasks, which runs a judge model and makes the gate partly ours with its own error
term. Telecom is deterministic (`ENV_ASSERTION`) but is 2,285 tasks over 88 MB and mostly
solo-mode workflow shapes. Airline is also the domain the Airline worked example already targets.

**Outcome: τ²'s own, never ours.** `reward_info.reward == 1.0` under a conversation that ended by
itself is `solved`; `0.0` is `unsolved`; anything else is τ²'s own `TerminationReason` value.
τ²'s evaluator already forces `reward = 0.0` for every premature termination, so folding those
into `unsolved` would fuse "the agent finished and got it wrong" with "the run never finished" —
and `diff` reads the episode frame narrow and never touches `meta`, so a distinction that lives
only in `meta` cannot be seen downstream. One spelling is ours: τ²'s `timeout` is stored as
`timed_out`, because S16 gave the bare string `timeout` to the executor's *errored* rows.

**`t` = τ² orchestrator steps, `horizon` = τ²'s own `DEFAULT_MAX_STEPS` (200).** It is the only
budget τ² itself enforces, so `t <= horizon` holds by construction and needs no clamp; and
`step_count` is readable even when `run()` raises, so an errored episode still reports how far it
got. Wall seconds would have needed a horizon we invented. Both pins are asserted against
`tau2.config` at import, so a re-pin that moves them fails loudly instead of silently rescaling
every stored `t`.

## Reproduce

```bash
pip install -e '.[modal]'                                  # from the repository root
export PYTHONPATH="$PWD/examples${PYTHONPATH:+:$PYTHONPATH}"
export PROOFLOAD_STORE=~/code/poisson-labs/proofload-runs
export MODAL_IMAGE_BUILDER_VERSION=2024.10                 # required; Dockerfile note 6

# the canary: one episode, proves the image before the ten
proofload sweep examples/tau2_pilot/ten.toml --target tau2_pilot.rollout:rollout \
  --backend modal --max-mde 0.5 --max-rollouts 1 --yes

# run A, then the same ten seeds again
proofload sweep examples/tau2_pilot/ten.toml --target tau2_pilot.rollout:rollout \
  --backend modal --max-mde 0.5 --yes
proofload sweep examples/tau2_pilot/ten.toml --target tau2_pilot.rollout:rollout \
  --backend modal --max-mde 0.5 --pair-with <A> --yes
```

`--max-mde 0.5` is not a workaround, it is the honest declaration: at one replicate the per-cell
MDE *is* 0.5, and nothing here is a design with power. The secret is the golden pilot's
`golden-pilot`; the wrapper needs `OPENAI_API_KEY` from it and reads nothing else.

## What the ten measured (2026-09-13, `gpt-4.1-mini-2025-04-14`, both sides)

Runs `20260913T113444Z-d44e` (A) and `20260913T113537Z-a06a` (A′), 10 episodes each, 20/20 ok,
0 errored, 0 infra-retried.

| | mean | median | min | max |
|---|---|---|---|---|
| tokens in | 54,046 | 48,926 | 20,136 | 118,961 |
| tokens out | 1,023 | 945 | 332 | 2,174 |
| wall s | 20.7 | 19.2 | 10.6 | 41.4 |
| steps `t` (of 200) | 21.5 | 20.0 | 11 | 41 |

- **$0.0233 per episode in model tokens** at list price, against **$0.00027** of Modal
  container-seconds attributable to the episode itself (its own `wall_time` at the shipped CPU
  rate) and **$0.00058–0.00072** per episode counting whole containers, cold start included
  (run wall clock x `concurrency`, the upper bound). Either way tokens are **97–99 %** of the
  bill, and `estimate_cost` does not see them.
- **The list-price figure is an upper bound.** LiteLLM's own per-message cost, computed inside the
  container, is **$0.0106** — 46 % of it. The whole gap is OpenAI prompt caching: solving it for a
  cached-token count at the table's $0.10/M read rate gives 67–87 % of prompt tokens cached, and
  every implied count is an exact multiple of 128, which is the cache's own granularity.
- **87.9 % of prompt tokens are the agent's**, 12.1 % the user simulator's. An episode is two
  models' traffic, and the split is not even.
- **Reproducibility: 7/10.** Same `(cfg, seed)`, same image, same models, twice: seven episodes
  gave the same outcome, three did not, and no episode reproduced its token count. Details and
  what it means for a paired design are in the T.4 report.

## Known warts in the substrate

1. **`import tau2` needs `websockets`**, which is in the `[voice]` extra and not in the base
   dependencies. A plain `pip install` of the package cannot be imported.
2. **`requires-python >=3.12` is conservative** for the half-duplex text path — `compileall` over
   all of `tau2` is clean on 3.11 — but it is **not** conservative for 3.13, where the same voice
   import chain imports `audioop`, removed from the standard library in 3.13.
3. **The wheel ships no data.** `TAU2_DATA_DIR` must be set or every domain load fails after a
   warning at import.
4. **Modal's own client requirements land on top of the image** and break τ² twice over: the
   workspace default builder pins `fastapi==0.88.0` → `pydantic<2`, and the next one up pins
   `typing_extensions==4.12.2`, which a current `pydantic_core` cannot import. See the Dockerfile.
5. **The `COMMUNICATE` half of the airline verdict is a substring match**, and τ² says so itself
   (`# TODO: This could be improved!`, `evaluator_communicate.py`). The test is
   `info_str.lower() in message.content.lower().replace(",", "")` over every assistant message
   with text: a required fact counts as communicated if its characters appear anywhere in
   anything the agent said, including inside a question or a refusal. It is deterministic, which
   is why this domain was chosen — but it is deterministic, not correct, and a finding that lands
   on `COMMUNICATE` rather than `DB` inherits that. `meta["reward_breakdown"]` keeps the two
   apart on every row, so which half moved is answerable after the fact.
6. **`(cfg, seed)` does not fix the episode.** τ² passes the seed to both models as OpenAI's
   `seed` request parameter, which is best-effort; at temperature 0 on 10 paired episodes, seven
   reproduced their outcome, two reproduced their step count and none reproduced their token
   count. Pairing on this substrate buys much less than pairing on a deterministic one.
