"""A stand-in for your own agent: it calls no model, and its replies are drawn from the seed."""
import random
from dataclasses import dataclass

from prompts import SYSTEM

#: Each ticket, as the share of attempts on it that end unresolved.
TICKETS = {"refund": 0.30, "password": 0.10, "shipping": 0.20}


@dataclass
class Reply:
    resolved: bool
    timed_out: bool
    steps: int


def handle(ticket, temperature, seed):
    rng = random.Random(seed)
    steps = rng.randint(2, 20)
    gives_up = ticket * (1 + temperature) * (0.5 if "step by step" in SYSTEM else 1.0)
    return Reply(resolved=steps < 20 and rng.random() >= gives_up, timed_out=steps == 20, steps=steps)
