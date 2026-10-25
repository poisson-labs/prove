# support-agent

A small customer-support agent: it classifies a ticket, drafts a reply with a model, and decides
whether to resolve the ticket, refund it or hand it to a person.

    from support_agent.agent import handle_ticket
    from support_agent.cases import CASES

    result = handle_ticket(CASES[0], prompt_version="v2", temperature=0.0, seed=1)

This copy ships a stand-in model client that answers from a seeded random generator and makes no
call, so the agent runs anywhere.
