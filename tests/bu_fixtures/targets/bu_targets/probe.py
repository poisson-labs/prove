"""The MC-shaped chaos probe: one chat completion at the declared position ``solve``, over
``httpx.MockTransport`` (no socket). It records the injection block the executor opened around the
episode, if any, the content it received, and its process id. A faulted episode falls."""

import os
from typing import Any

import httpx

from poisson_prove import chaos
from poisson_prove.episode import Episode

SCRIPTED = "SCRIPTED-OK"
HORIZON = 10.0
BODY = {
    "id": "chatcmpl-scripted",
    "object": "chat.completion",
    "created": 0,
    "model": "scripted-model",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": SCRIPTED}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
}


def _handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=BODY)


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    block = chaos._BLOCK
    seen = (
        None
        if block is None
        else {"fault": block.spec.fault, "rate": block.spec.rate, "steps": list(block.spec.steps)}
    )
    transport = httpx.MockTransport(_handler)
    with httpx.Client(transport=transport, base_url="http://scripted.invalid") as client:
        with chaos.position("solve", 1):
            response = client.post(
                "/v1/chat/completions",
                json={"model": "scripted-model", "messages": [{"role": "user", "content": "hi"}]},
            )
    content = response.json()["choices"][0]["message"]["content"]
    injected = content != SCRIPTED
    return Episode(
        outcome="fell" if injected else "survived",
        t=1.0 if injected else HORIZON,
        horizon=HORIZON,
        meta={"chaos_block": seen, "content": content, "pid": os.getpid()},
    )
