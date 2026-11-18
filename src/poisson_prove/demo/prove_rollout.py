from poisson_prove import Episode
from support_bot import TICKETS, handle  # your agent and its cases


def rollout(cfg, seed):
    ticket = TICKETS[cfg["ticket"]]
    reply = handle(ticket, temperature=cfg["temperature"], seed=seed)
    if reply.timed_out:
        outcome = "timeout"
    elif reply.resolved:
        outcome = "resolved"
    else:
        outcome = "unresolved"
    return Episode(outcome=outcome, t=reply.steps, horizon=20, meta={"case_id": cfg["ticket"]})
