"""The model client the agent talks to.

This copy is a stand-in: it answers from a random generator seeded by the ticket's seed, the model
and the temperature, and makes no network call.
"""

from __future__ import annotations

import random

MODEL = "support-model-1"


class StandInClient:
    """Answers like a chat model would, without calling one."""

    def __init__(self, *, model: str = MODEL, temperature: float = 0.0, seed: int = 0) -> None:
        self.model = model
        self.temperature = temperature
        self.calls = 0
        self._random = random.Random(f"{model}/{temperature}/{seed}")

    def complete(self, prompt: str) -> str:
        """One answer to one prompt."""
        self.calls += 1
        noise = self._random.random() * (0.5 + self.temperature)
        if "refund" in prompt and noise > 0.55:
            return "REFUND"
        if noise > 0.45:
            return "ESCALATE"
        return "RESOLVE"
