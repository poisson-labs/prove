# The demo agent

A small support bot to try Poisson Prove on. It is a stand-in: it calls no model and needs no key
and no network. Its replies are drawn at random from the seed, so the same case and seed always
end the same way.

- `support_bot.py` is the bot: three tickets, and a reply for each.
- `prompts.py` is its system prompt, `SYSTEM`.

## What to do with it

1. Set Prove up on it with your coding agent. `poisson-prove init --agent` writes a skill and a
   prompt; give your coding agent the prompt, and it writes `prove_rollout.py` and `prove.toml`
   and stops for you to review. With no coding agent, `poisson-prove init --demo --with-setup`
   writes those two files for you.
2. Sweep it as it is: `poisson-prove sweep`.
3. Make the change to try: add "step by step" to `SYSTEM` in `prompts.py`.
4. Sweep again on the same seeds: `poisson-prove sweep --pair-with latest`.
5. Compare the two runs: `poisson-prove diff`.

The comparison should read `safer`: with the change, fewer tickets end unresolved.

## What the demo cannot show

The stand-in reads only that one phrase: any other wording of `SYSTEM` changes nothing, while a
real agent's prompt matters in ways this one cannot show.

## A real agent

[`examples/your-first-real-agent/`](https://github.com/poisson-labs/prove/tree/main/examples/your-first-real-agent)
is a small agent that calls a real model (OpenAI's `gpt-4.1-mini`). It needs an OpenAI API key in
`OPENAI_API_KEY`, `pip install "poisson-prove[agent]"`, and a network; each sweep makes 1,200
short requests, billed to your OpenAI account. Without the key every case errors and the sweep
stops; without a network every case ends `api_error`.
