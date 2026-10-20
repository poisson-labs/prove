# The τ²-bench pilot

A Proofload rollout wrapper over **sierra-research/tau2-bench** (τ³), airline domain: the
ten-episode measurement it was built for, and the two arms of the T.4 run it now carries.

**Nothing here has run as a sweep.** The ten-episode pair below is the only τ² data, and it is
discovery. The T.4 confirmation — `t4.toml`, three arms, 2,200 episodes each — is
pre-registered and not launched.

τ² is **not forked and not patched**. It is installed from a pinned commit inside the image and
used through public entry points: `registry.get_tasks_loader`, `build_text_orchestrator`,
`run_simulation`, and — for arm B — `registry.register_agent_factory`. Nothing in
`src/poisson_prove` changed.

## The two arms

| entry point | arm | what differs |
|---|---|---|
| `tau2_pilot.rollout:rollout` | A, A′ | nothing: τ²'s stock `llm_agent` |
| `tau2_pilot.rollout:rollout_patched` | B | one policy-adherence paragraph after the domain policy |

The paragraph is `tau2_pilot.guardrail.GUARDRAIL`, fixed before any arm runs, 421 bytes,
sha256 **`fce8dcd12119b7e6c2ea288e14a60c4cd9dcc1bca0f8bbaffb0847e5cfc85156`**. It reaches τ²
as a subclass of `LLMAgent` whose `system_prompt` property appends it, registered under the
name `tau2_pilot_guardrail` through τ²'s own public `register_agent_factory`; `build_agent`
resolves `config.effective_agent` by that name and no τ² file is edited.

**`build_agent` calls a factory with seven keyword arguments**, not the five the
pre-registration lists — `task`, `audio_native_config` and `audio_taps_dir` ride along on every
path — so the factory takes `**kwargs`, the way τ²'s own `create_llm_agent` does.

**Nothing in the container caps spend.** See *Spend* below: the cap is a launch gate and a
project-level limit at the provider, and the wrapper carries no budget of its own.

**Every row carries the proof, in both arms.** τ²'s `SimulationRun` has no field for the system
message and its `messages` are the orchestrator's trajectory, so the guardrail cannot be read
back out of a stored conversation. `rollout` hashes the prompt the agent it just built will
send and stores `meta["system_prompt_sha256"]` and `meta["guardrail_in_system_prompt"]` beside
`meta["agent"]`. That is what K7 is read from.

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

## The T.4 sweep file

`t4.toml` is **generated, never hand-written**: `scripts/tau2_t4_sweep.py` reads τ²'s own
`tasks.json` at the pin, applies the pre-registration's mechanical family rule to each task's
`evaluation_criteria.actions`, and writes the file with the design's numbers recomputed from
`poisson_prove.diff.mde_two_proportion` in its header.

```bash
python scripts/tau2_t4_sweep.py --tasks <tau2-checkout>/data/tau2/domains/airline/tasks.json
python scripts/tau2_t4_sweep.py --tasks <...>/tasks.json --check   # exits 1 if the file drifted
```

The rule gives **`no_write` 24 / `modify_in_place` 14 / `cancel_or_book` 12**, which is not the
21 / 16 / 13 the pre-registration's hand-read table prints; ten of the fifty tasks move. The
rule is what was pre-registered, so the script is right and the table is a correction. The
binding family is therefore 12 cells rather than 13, and N rises from 40 to **44** — the least
replicate count at which the resolver admits every family at `--max-group-mde 0.10`.

Three cells per arm are junk and are declared: `SweepSpec.load` refuses a file with no
`[axes.*]` table, so the required `[axes.task_family]` grid produces three configs carrying no
`task_id`. The wrapper raises `KeyError`, the executor records an errored row, and `multi_diff`
filters `outcome.notna()` before pairing, so they never reach the tree.

## D0: the junk-cell shape, confirmed by running it

`synthetic.py` is the wrapper's shape with no τ², no model and no money. Run the pair and read
the coverage before spending anything:

```bash
export PYTHONPATH="$PWD/examples${PYTHONPATH:+:$PYTHONPATH}"
export POISSON_PROVE_STORE=$(mktemp -d)
python scripts/tau2_t4_sweep.py --tasks <...>/tasks.json --replicates 8 --out /tmp/d0.toml
poisson-prove sweep /tmp/d0.toml --target tau2_pilot.synthetic:rollout \
  --backend local --max-mde 0.60 --yes
poisson-prove sweep /tmp/d0.toml --target tau2_pilot.synthetic:rollout_patched \
  --backend local --max-mde 0.60 --pair-with <A> --yes
poisson-prove diff <A> <B> --event unsolved --method mcnemar_bh --q 0.05 \
  --by task_family --max-group-mde 0.30 --depth 3 --methods all
```

Measured 2026-09-14: `n_errored` 24 = 3N per arm; `n_tests=50`; `coverage: holes=3 … 
no_outcome_both=3`; the fault-lines rung resolves on `task_family` with 3 groups; the synthetic
patch's effect lands in `no_write` alone.

**K8 must be read from `coverage`, not from `n_not_comparable`.** That field counts cells one
arm ran and the other did not and is **0** here; a wholly-errored cell has rows in both arms.

**`report --x task_family` is refused** — two free axes. The forms that render are
`--x task_family --y task_id` and `--x task_id --fix 'task_family="no_write"'`, and a string
`--fix` value has to carry its TOML quotes.

## Spend

`estimate_cost` guards Modal compute and has never seen a token (C20), so the cap is not
Proofload's `--max-cost` and is not anything in the container:

```bash
python scripts/tau2_t4_budget.py --arm A          # refuses if the cap cannot cover this arm
```

The gate reads what T.4 has already spent from the store's own `meta.cost_tau2` and projects the
arm about to launch at the provider's list price. **It gates at arm granularity: once an arm is
launched nothing here stops it, and a launch gate is not a stop.**

**The only stop that binds is a project-level spend limit at the provider.** It is an account
setting, no session sets it, and it is owed before arm A.

There is deliberately **no per-container ceiling**. One was built and dropped: sized low enough
to make `episodes × ceiling` fit the cap it lands at $0.023, at or under the most expensive
*legitimate* episode measured ($0.0246), and would have killed real episodes and biased the arm;
sized safely it bounded nothing worth bounding.

**gpt-4.1-mini list price, read at source 2026-09-14** from
<https://developers.openai.com/api/docs/pricing> (a 301 from `platform.openai.com/docs/pricing`):
**$0.40 / $0.10 / $1.60** per million tokens, input / cached input / output. The page prices the
`gpt-4.1-mini` alias; the run pins the `-2025-04-14` snapshot and the table carries one price for
both. Those rates reproduce both anchors: 54,046 in / 1,023 out is **$0.0233** at list, and the
$0.10/M cached-read rate is what the 67–87 % cache solve used.

**The spread at 6,600 episodes is $73 measured against $153 at list**, and list has been a 2.2×
overestimate on every measurement so far. The cap is **$175**. K1 watches the *measured* number —
`meta.cost_tau2` is litellm's own cache-aware figure — against $175 / 6,600 = **$0.0265** per
episode in arm A; the list figure is what the launch gate refuses on, and it is a bound, not a
forecast.

## Reproduce

```bash
pip install -e '.[modal]'                                  # from the repository root
export PYTHONPATH="$PWD/examples${PYTHONPATH:+:$PYTHONPATH}"
export POISSON_PROVE_STORE=~/code/poisson-labs/prove-runs
export MODAL_IMAGE_BUILDER_VERSION=2024.10                 # required; Dockerfile note 6

# the canary: one episode, proves the image before the ten
poisson-prove sweep examples/tau2_pilot/ten.toml --target tau2_pilot.rollout:rollout \
  --backend modal --max-mde 0.5 --max-rollouts 1 --yes

# run A, then the same ten seeds again
poisson-prove sweep examples/tau2_pilot/ten.toml --target tau2_pilot.rollout:rollout \
  --backend modal --max-mde 0.5 --yes
poisson-prove sweep examples/tau2_pilot/ten.toml --target tau2_pilot.rollout:rollout \
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
6. **`[capture].content = true` is necessary and not sufficient.** Measured 2026-09-14
   against litellm 1.80.0, openai 2.54.0 and `opentelemetry-instrumentation-openai-v2` 2.4b0,
   with a local mock server and no provider spend: the instrumentor emits
   `gen_ai.input.messages` / `gen_ai.output.messages` **only** when
   `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` is `SPAN_ONLY` or `SPAN_AND_EVENT`.
   Proofload's flag decides what capture *keeps*; that variable decides what the instrumentor
   *gives*. With the flag on and the variable unset the span carries `gen_ai.request.*` and
   `gen_ai.response.*` and no content at all, silently. The Dockerfile sets it.
7. **LiteLLM does not call the symbol the instrumentor wraps — and the span appears anyway.**
   `litellm.llms.openai.openai` calls `chat.completions.with_raw_response.create`, not
   `Completions.create`. Measured the same day: the span *is* produced, because
   `with_raw_response` binds `completions.create` through the class attribute and wrapt's
   descriptor is what it gets, provided the client is built after `instrument()`.
8. **`litellm.max_budget` is inert on this call shape** — recorded because the next person to
   reach for it will assume otherwise. litellm adds a call's cost only when the result
   `isinstance(result, dict) and "content" in result`; τ²'s results are `ModelResponse` objects
   whose agent turns are tool calls with `content=None`. Ten calls at $0.0233 left
   `_current_cost` at `0.0` and a $0.05 budget never fired: a run that merely set it would have
   carried a guard that looked installed and was not. With the accounting supplied the stop does
   fire, about **two calls late**, because litellm runs success callbacks on a thread pool.
   Measured 2026-09-14; nothing here depends on it, since the per-container ceiling was dropped.
9. **`(cfg, seed)` does not fix the episode.** τ² passes the seed to both models as OpenAI's
   `seed` request parameter, which is best-effort; at temperature 0 on 10 paired episodes, seven
   reproduced their outcome, two reproduced their step count and none reproduced their token
   count. Pairing on this substrate buys much less than pairing on a deterministic one.
