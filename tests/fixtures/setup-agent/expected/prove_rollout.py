"""The rollout Poisson Prove runs: one support ticket, end to end, through the agent's own
handle_ticket. The agent's code is unchanged; this file only calls it and names how it ended."""

from __future__ import annotations

from typing import Any

from poisson_prove import Episode
from support_agent.agent import MAX_CALLS, handle_ticket
from support_agent.cases import CASES


def rollout(cfg: dict[str, Any], seed: int) -> Episode:
    ticket = CASES[seed % len(CASES)]
    try:
        result = handle_ticket(ticket, prompt_version=cfg["prompt_version"], temperature=cfg["temperature"], seed=seed)
    except TimeoutError:
        return Episode(outcome="timeout", t=MAX_CALLS, horizon=MAX_CALLS)
    return Episode(outcome=result.status, t=result.calls, horizon=MAX_CALLS)
