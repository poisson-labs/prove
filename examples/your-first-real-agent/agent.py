"""Your first real agent: one short question per case, asked of an OpenAI model, graded by exact
match. The client is made inside the rollout, so importing this file needs no key."""
import openai

from poisson_prove import Episode

MODEL = "gpt-4.1-mini"
QUESTIONS = {"sum": ("What is 2 + 2?", "4"), "capital": ("What is the capital of France?", "Paris"),
             "letters": ("How many letters are in the word 'agent'?", "5")}


def rollout(cfg, seed, system="Answer briefly."):
    question, expected = QUESTIONS[cfg["case"]]
    meta = {"case_id": cfg["case"]}
    try:
        reply = openai.OpenAI().chat.completions.create(
            model=MODEL, temperature=cfg["temperature"], seed=seed,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": question}])
    except openai.APIError:  # the provider failed, not the agent: an outcome of its own
        return Episode(outcome="api_error", t=1, horizon=1, meta=meta)
    answer = (reply.choices[0].message.content or "").strip().rstrip(".")
    return Episode(outcome="correct" if answer == expected else "wrong", t=1, horizon=1, meta=meta)


def rollout_strict(cfg, seed):
    """The change to test: a system prompt that asks for the bare answer."""
    return rollout(cfg, seed, system="Reply with the answer alone: one number or one word.")
