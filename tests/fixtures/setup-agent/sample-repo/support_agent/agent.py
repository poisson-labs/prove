"""The agent: classify a ticket, draft a reply, decide what happens to the ticket."""

from __future__ import annotations

from dataclasses import dataclass

from support_agent.client import StandInClient

#: The most model calls one ticket may take before the agent gives up.
MAX_CALLS = 6

PROMPTS = {
    "v1": "Classify this support ticket as resolve, refund or escalate: {text}",
    "v2": "You are a careful support agent. Refund only when the policy allows it. Ticket: {text}",
}


@dataclass(frozen=True)
class Result:
    #: "resolved", "escalated" or "wrong_refund"
    status: str
    calls: int


def classify(ticket: dict[str, str], client: StandInClient, prompt_version: str) -> str:
    """What the model says should happen to the ticket."""
    return client.complete(PROMPTS[prompt_version].format(text=ticket["text"]))


def draft_reply(ticket: dict[str, str], decision: str, client: StandInClient) -> str:
    """The reply the customer gets; the model is asked again until it agrees with itself."""
    for _ in range(MAX_CALLS - 1):
        if client.complete(f"Draft a reply that will {decision.lower()}: {ticket['text']}") == decision:
            return f"We will {decision.lower()} ticket {ticket['id']}."
    raise TimeoutError(f"no reply for ticket {ticket['id']} after {MAX_CALLS} model calls")


def handle_ticket(ticket: dict[str, str], *, prompt_version: str, temperature: float, seed: int) -> Result:
    """One ticket, end to end. Raises TimeoutError when the model never settles."""
    client = StandInClient(temperature=temperature, seed=seed)
    decision = classify(ticket, client, prompt_version)
    draft_reply(ticket, decision, client)
    if decision == "REFUND":
        status = "resolved" if ticket["eligible"] == "yes" else "wrong_refund"
    elif decision == "ESCALATE":
        status = "escalated"
    else:
        status = "resolved"
    return Result(status=status, calls=client.calls)
