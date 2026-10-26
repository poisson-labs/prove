"""The tickets the agent is checked on."""

from __future__ import annotations

CASES: tuple[dict[str, str], ...] = (
    {"id": "t1", "text": "My order arrived broken, can I get a refund?", "eligible": "yes"},
    {"id": "t2", "text": "How do I change the delivery address?", "eligible": "no"},
    {"id": "t3", "text": "I was charged twice, please refund one charge.", "eligible": "yes"},
    {"id": "t4", "text": "I want a refund for a gift card I used last year.", "eligible": "no"},
)
