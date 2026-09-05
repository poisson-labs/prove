# The golden suite pilot

One real, cheap, agentic substrate through Proofload's full loop — sweep, pair, diff, report,
check — producing a finding worth writing up before any frontier-model spend. It is also the
first real integration to measure the three numbers M12 asked for: span count, `dropped`, and
the `other` share of a real autoinstrumented agent's trace.

**The defect it attacks.** A golden test suite runs each case once, at one temperature, with
no seeds, so it structurally cannot tell a regression from a resample. This runs all 164
HumanEval problems at 32 seeds and two temperatures and reports which failures reproduce at
every seed and which are coin flips.

**What it is not.** On HumanEval the agent is thin — prompt, generate, run the tests, submit —
so the sweep measures model behaviour under temperature and task, not agent behaviour under
perturbation. That is the right measurement for a pilot proving the plumbing, and it is not
the agentic surface Phase 4 needs. Do not read this as that integration.

## The isolation boundary, before anything else

The agent executes model-generated code. **The Modal container is the isolation boundary and
the local backend is unsupported for this suite.** `golden_pilot.agent` raises at import
unless the environment sets `GOLDEN_PILOT_BOUNDARY` to `container`, which only this
directory's `Dockerfile` does, so a local sweep fails at target resolution and never reaches
a candidate. The subprocess limits inside `sandbox.py` — a fresh `python -I -S`, a 10 s wall
clock, an address-space cap, no `socket` — are hygiene so one bad candidate costs one tool
call; they are not the boundary.

Every command below runs `--backend modal`. There is no local path.

> **Known blocker — read this before booking time.** As of the S18 build, `proofload sweep`
> cannot launch this pilot on *either* backend. `cli.py` resolves `--target` before it
> branches on the backend, so the launching process imports `golden_pilot.agent` on your
> laptop, where the boundary variable is correctly absent, and the refusal fires there:
>
> ```
> RuntimeError: golden_pilot.agent executes model-generated code and imports only inside
> the isolation boundary: ... is not set.
> ```
>
> The resolved callable is only ever used by the local backend; the Modal path passes the
> import path as a string and resolves it inside the container. So the fix is one line in
> core — resolve on the local branch only — or one sentence in the spec. It is deliberately
> not patched from inside the pilot: weakening the import-time refusal, or moving it to first
> call, is the thing spec section 3 chose against. See the S18 Session B devlog entry for the
> three candidate resolutions.
>
> **And a second one, independent of the first.** There is no way for `OPENAI_API_KEY` to
> reach the container. `executor_modal.py` builds the remote function with `image`, `gpu`,
> `timeout`, `retries`, `max_containers` and `serialized` — no `secrets=`, no `env=` — and
> neither `ImageSpec` nor `ModalOptions` carries one. The `modal secret create` step below is
> therefore inert today: the secret exists, and nothing attaches it. Baking a key into the
> `Dockerfile` is not the answer — that is a credential in the repository. This wants a
> `secrets` field on `ImageSpec` or `ModalOptions` and one argument at `app.function(...)`.
>
> Both gaps are in core, and the pilot is a user (spec section 6), so neither is patched from
> here. They are, between them, the most useful thing this phase has produced so far: the
> first user that needed a credential in a container found that Proofload cannot put one
> there.

## Setup

```bash
pip install -e '.[agent,modal]'                      # from the repository root
pip install -r examples/golden_pilot/requirements.txt
export PYTHONPATH="$PWD/examples${PYTHONPATH:+:$PYTHONPATH}"
python examples/golden_pilot/fetch_suite.py          # HumanEval, once, by hand (MIT)
python examples/golden_pilot/make_toml.py            # regenerates pilot.toml and smoke.toml
```

**The third line is not optional.** `golden_pilot` is not a package and is not installed —
the wheel ships `src/proofload` only, and `examples/` is deliberately outside it. Nothing in
`proofload` puts it on the path, so `--target golden_pilot.agent:rollout` cannot be resolved
without it. Run everything below from the repository root with that variable set.

`fetch_suite.py` is the only thing here that touches the network, and nothing calls it for
you. The suite lands at `suite/HumanEval.jsonl.gz`, is not committed, and is pinned by
SHA-256.

**The container fetches its own copy of the suite, and that is deliberate.** The Modal
backend ships the pilot with `Image.add_local_python_source`, which copies `*.py` files only,
so the `.jsonl.gz` does not travel with the package. The `Dockerfile` therefore downloads it
at image build from the same URL, checks the same digest, and points `GOLDEN_PILOT_SUITE` at
it. The digest is what makes the laptop's copy and the container's copy the same bytes — and
therefore what makes `pilot.toml`'s 164-id axis, generated here, describe the suite the
container actually loads. If you re-pin one, re-pin the other; `fetch_suite.py` warns when
the `Dockerfile` has stopped agreeing with it.

Two environment variables reach the container, both through your Modal secret: your
`OPENAI_API_KEY` (and `OPENAI_BASE_URL` for a non-OpenAI endpoint), and `GOLDEN_PILOT_MODEL`,
which names the model the agent calls.

```bash
modal secret create golden-pilot OPENAI_API_KEY=<your-key> GOLDEN_PILOT_MODEL=gpt-4o-mini
```

Create it, but read the second blocker above first: nothing in Proofload attaches a Modal
secret to the function yet, so this step does not reach the container until that is fixed.

**The model name lives in two places and they must agree.** `GOLDEN_PILOT_MODEL` is what the
requests carry; `target_id` in the sweep files is what the manifest records. If you change
the model, regenerate both files so the store does not name a model the run did not use:

```bash
python examples/golden_pilot/make_toml.py --model <your-model>
```

Do that **before** the smoke, not after. `make_toml.py` rewrites both files from the
template, where `est_seconds_per_episode` and `max_cost` sit commented out, so regenerating
over a sized `pilot.toml` would discard the numbers the smoke gave you. It refuses to when it
would; `--force` says you meant it.

## 1. The smoke, and the cap

5 tasks × 2 temperatures × 2 replicates = 20 episodes, in the same environment the arms will
run in. It proves the image, the boundary variable, the instrumentor inside the container and
the store round trip, and it measures what the arms will cost.

```bash
proofload sweep examples/golden_pilot/smoke.toml \
  --target golden_pilot.agent:rollout --backend modal --yes
python -m golden_pilot.numbers <store> <smoke-run-id>
```

Read seconds and tokens per episode out of the smoke, then do the arithmetic **before** the
sized run and never after:

```
episodes   = 164 tasks x 2 temperatures x 32 replicates x 3 arms = 31,488
model cost = episodes x (tokens_in x $/in + tokens_out x $/out)
wall time  = episodes x est_seconds_per_episode / concurrency
```

Write `est_seconds_per_episode` and `max_cost` into `pilot.toml`'s `[modal]` table, where
they sit commented out. **`max_cost` guards Modal compute only** — `estimate_cost` is
`jobs × est_seconds_per_episode × the container rate` and it has never seen a token. **The
$50 cap is model spend plus compute, and nothing enforces it**: it is the arithmetic above,
done by you, before you launch. If three arms do not fit, drop `replicates` to 16 for all
three arms **before** cutting `task_id`: 32 seeds per case is the finding, and 164 cases is
only the surface.

**Watch the per-episode wall time, not just the cost.** `episode_timeout` is 120 s and spec
section 8 intends it to fire only on an anomaly, but the agent's own worst case can reach it
without anything being wrong: six tool calls at a 10 s sandbox wall clock is 60 s, and up to
twelve model calls (six turns plus a repair turn each) carrying `1 + 2 + 4` s of retry
backoff is another 84 s, before a single token is decoded. A cut episode becomes an errored
row, and the episodes most likely to be cut are the slow ones — hanging candidates, repair
turns, retries — so the censoring correlates with the outcome being measured. Read the p99
wall time out of the smoke. If it is anywhere near 120 s, raise `episode_timeout` before the
arms; that number is pinned at 120.0 by the oracle, so raising it is a spec change and not a
config tweak.

Confirm the smoke's rows before spending anything: `n_errored` should be 0, every ok row's
outcome should be one of `passed`, `failed_assertion`, `timed_out`, `crashed`, and
`numbers.py` should report `contract.failed == 0` and a non-empty kind histogram with `llm`
and `tool` both present. An empty `llm` count means the instrumentor did not activate in the
container, and nothing downstream is worth running until it does.

## 2. The three arms

```bash
# A — the baseline
proofload sweep examples/golden_pilot/pilot.toml \
  --target golden_pilot.agent:rollout --backend modal --yes

# A' — the null diff: same target, same seeds, paired with A
proofload sweep examples/golden_pilot/pilot.toml \
  --target golden_pilot.agent:rollout --backend modal --pair-with <A> --yes

# B — the patch: submit is refused until run_tests has run once
proofload sweep examples/golden_pilot/pilot.toml \
  --target golden_pilot.agent:rollout_patched --backend modal --pair-with <A> --yes
```

A′ is the noise floor and it is published before any finding is claimed. **The patch in B is
a guardrail in the loop, not a change to the prompt** — A and B send byte-identical requests
until the first refusal — so whatever the paired diff shows is the patch and not a reworded
system message. The prediction, stated here before the run: `failed_assertion` falls,
`timed_out` rises, and the trade line names which cells paid.

## 3. Diff, report, check, inspect

Every command names the three failure events explicitly; `passed` is the absorbing state and
nothing here infers an event set.

```bash
proofload diff   <A> <A'> --event failed_assertion --event timed_out --event crashed
proofload diff   <A> <B>  --event failed_assertion --event timed_out --event crashed
proofload report <A> <B>  --event failed_assertion --event timed_out --event crashed \
  --x temperature --y task_id --out notes/log/pilot-report
proofload check  <A> <B>  --event failed_assertion --event timed_out --event crashed
proofload inspect <A> --event failed_assertion --where temperature=0.0 --limit 5
```

`check` is the golden suite becoming a gate: it fails if B is significantly worse on any
named event. 164 rows on a heatmap is tall but legible; `--where temperature=0.0` and
`--limit` are the working views.

## 4. The numbers, per arm

`<store>` is the same store root the sweeps wrote into — whatever you passed to
`proofload --store`, or `$PROOFLOAD_STORE`, or `./proofload-runs` by default. Run it from the
repository root so `golden_pilot` is importable, or put `examples/` on `PYTHONPATH`.

```bash
python -m golden_pilot.numbers <store> <A>
python -m golden_pilot.numbers <store> <A> --paired-with <A'>
```

That prints, as JSON:

- **the three numbers** — `spans`, `dropped`, `other_share` — with `kinds` and `tool_share`;
- **contract survival** — ok rows that decode as an `Episode` with an outcome in `OUTCOMES`,
  `0 <= t <= horizon`, the declared `t_unit`, and an uncut trace with both episode stamps on
  every captured llm span;
- **the errored-row rate**, split by error text and by whether the row kept a trace. An
  errored row is Proofload failing to observe, never the agent failing the task: a hung API
  call cut at `episode_timeout` is an errored `timeout` row carrying its drained trace, and
  it is a different fact from the `timed_out` outcome, which is the agent spending its
  budget of tool calls;
- **zero-n holes** — (cell, event) pairs the run never produced, over 328 cells;
- **pairing agreement and Cohen's kappa** at the same `(task_id, temperature, seed)`, per
  temperature.

## 5. What goes in the devlog

The run is complete when the devlog carries, with run ids: the three numbers per arm; the
four checks; the null diff's headline and kappa per temperature; B's paired diff and its
trade line; `check`'s verdict; and the finding — which cases fail at every seed and which are
coin flips, at each temperature. Publish figures and that record, never raw traces.

## The files

| file | what it is |
|---|---|
| `suite.py` | `load()` over the HumanEval JSONL; 164 goldens, ids stable |
| `fetch_suite.py` | downloads the suite once, by hand; nothing else calls it |
| `sandbox.py` | `run_tests(candidate, golden)` in a fresh subprocess; never raises |
| `agent.py` | `rollout` and `rollout_patched`; refuses to import outside the boundary |
| `numbers.py` | the three numbers and the four checks, from the store |
| `make_toml.py` | writes both sweep files from `suite.load()`, so they cannot drift |
| `pilot.toml` | 164 tasks × 2 temperatures × 32 replicates |
| `smoke.toml` | the same shape over 5 tasks at 2 replicates |
| `Dockerfile` | the Modal image, and the only place the boundary variable is set |
| `requirements.txt` | the contract: `openai<2`, the instrumentor, `proofload[agent]` |
