# Your first real agent

A small agent that calls a real model: three short questions, each its own case, asked at two
temperatures and graded by exact match. It shows the whole loop on something that costs a few
cents: sweep it, change its prompt, sweep again on the same seeds, and compare.

- `agent.py` is the agent and its rollout, in under twenty lines of code. The OpenAI client is made
  inside the rollout, so importing the file needs no key, and a failed API call is an outcome of
  its own, `api_error`, never counted as a wrong answer. It still competes with the other endings:
  if one run hit more API errors, fewer of its episodes could end `wrong`, so read `api_error`'s own
  line in the comparison before trusting a fall in `wrong`.
- `prove.toml` is the sweep spec: the questions as one axis, the temperature as another, 200
  replicates each, and which outcomes count against the agent.

## Check it, with no key

Install Prove with the `agent` extra, which brings the OpenAI client, then check the setup. The
check imports the rollout, checks it takes `(cfg, seed)`, prints the plan and runs nothing:

<!-- docs-check: run -->
```bash
pip install "poisson-prove[agent]"
```

<!-- docs-check: run -->
```console
$ poisson-prove sweep --dry-run
plan  1,200 rollouts of first-real-agent: 6 cells x 200 replicates on local, $0 (local)
  target  agent:rollout (imports, takes cfg and seed)
  outcomes  failures: wrong; successes: correct; neither: api_error
…
```

The `$0` is this machine's compute. The model calls are on your OpenAI bill: 1,200 short requests
per sweep to `gpt-4.1-mini`.

## Run it, with your key

With `OPENAI_API_KEY` set in your environment, sweep the agent, then the stricter prompt in
`rollout_strict` on the same seeds, and compare:

<!-- docs-check: skip: needs a model key, OPENAI_API_KEY -->
```bash
poisson-prove sweep --yes
poisson-prove sweep --yes --target agent:rollout_strict --pair-with latest
poisson-prove diff
```

The first line of `diff` is the verdict: `safer` if the strict prompt left fewer answers wrong
somewhere and worse nowhere, `worse` the other way, and `no significant change` or
`too small to tell` if nothing moved. A model does not promise the same answer for the same
`seed`, so twins can differ for reasons of the model's own; the comparison counts that as noise.

## Make it yours

Replace the questions with your own cases, the grading with your own, and the model call with your
agent's; keep the case on its own axis and its id in `meta`. [Your own agent](https://github.com/poisson-labs/prove/blob/main/docs/your-own-agent.md)
says why, and [Defining outcomes](https://github.com/poisson-labs/prove/blob/main/docs/defining-outcomes.md)
says how to choose outcomes that measure the agent and not the provider.
