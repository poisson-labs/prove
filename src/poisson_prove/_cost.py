"""What a plan says a sweep costs, and what it says it does not price.

Prove prices two things. The compute a backend bills (nothing on this machine; an estimate on
Modal and on a cloud account), which each backend words itself. And the agent's own calls at its
own providers, which Prove cannot see: it prices them only by the figure the person declares
under ``[cost]`` in the sweep spec, multiplied by the rollouts the command will run, and says
whose figure it is. With nothing declared it says they are not priced. It reads ``$0`` only when
the spec declares that a rollout costs nothing.

This module words the agent's part, the same way on every backend, and does the arithmetic. It
holds no price of any provider, opens nothing and writes nothing. Every line it returns is
already spelled the look's way and is printed as it is: the declared rate is given back as the
spec writes it, which the look's own dollar rule would cut short.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Any

from poisson_prove import _look
from poisson_prove.sampler import CostSpec, SweepSpec

#: What the agent's calls are called, on every line that speaks of them.
CALLS = "your agent's own calls"


def spec_name(spec: SweepSpec) -> str:
    """The spec file by its own name, or ``the spec`` for one built in code."""
    return spec.source or "the spec"


def priced_rollouts(left: int, max_rollouts: int | None) -> int:
    """The rollouts this command will run: those not yet stored, at most ``--max-rollouts``."""
    return left if max_rollouts is None else max(0, min(left, int(max_rollouts)))


@dataclass(frozen=True)
class Agent:
    """The agent's part of a plan's cost: what the spec declares, times the rollouts."""

    name: str
    cost: CostSpec | None
    rollouts: int

    @property
    def declared(self) -> bool:
        return self.cost is not None

    @property
    def free(self) -> bool:
        """The spec declares that a rollout costs nothing."""
        return self.cost is not None and self.cost.usd_per_rollout == 0

    @property
    def exact(self) -> Decimal | None:
        """The product, to the last digit of the rate as written; None with nothing declared."""
        if self.cost is None:
            return None
        return Decimal(self.cost.written) * self.rollouts

    @property
    def usd(self) -> float | None:
        exact = self.exact
        return None if exact is None else float(exact)

    @property
    def count(self) -> str:
        return f"{_look.fmt_count(self.rollouts)} {'rollout' if self.rollouts == 1 else 'rollouts'}"

    @property
    def rate(self) -> str:
        """The rate as the spec writes it: ``$0.0274 each``."""
        assert self.cost is not None
        return f"${self.cost.written}" + ("" if self.rollouts == 1 else " each")

    def figure(self) -> str:
        """``~$2.43 of your agent's own calls``."""
        return f"~{_look.fmt_dollars(self.usd)} of {CALLS}"

    def phrase(self, *, basis: bool = True) -> str:
        """The declared estimate: the product, the count, the rate as written, whose figure it
        is, and the basis when the spec gives one."""
        assert self.cost is not None
        told = f": {self.cost.basis}" if basis and self.cost.basis else ""
        return f"{self.figure()} ({self.count} at {self.rate}, declared in {self.name}{told})"

    def not_priced(self) -> str:
        return f"{CALLS} are not priced ({self.name} declares no [cost])"

    def nothing(self) -> str:
        return f"{self.name} declares that a rollout costs nothing"


def agent_of(spec: SweepSpec, left: int, max_rollouts: int | None = None) -> Agent:
    return Agent(spec_name(spec), spec.cost, priced_rollouts(left, max_rollouts))


def cap_words(cap: float) -> str:
    return f"cap {_look.fmt_dollars(cap)}"


def local_line(agent: Agent, cap: float | None = None) -> str:
    """The ``Cost:`` line of a sweep on this machine, less its label."""
    capped = "" if cap is None else f" · {cap_words(cap)}"
    if not agent.declared:
        return f"{agent.not_priced()}; this machine adds nothing"
    if agent.free:
        return f"$0 ({agent.nothing()}; this machine adds nothing){capped}"
    return f"{agent.phrase()}; this machine adds nothing{capped}"


def local_short(agent: Agent) -> str:
    """The same, as the plan's first line says it."""
    if not agent.declared:
        return f"{CALLS} not priced"
    return "$0" if agent.free else agent.figure()


def remote_tail(
    agent: Agent, *, compute_usd: float | None, cap: float | None, cap_shown: bool
) -> str:
    """What follows the compute part of Modal's or the cloud's ``Cost:`` line: the agent's part,
    the sum when both parts are figures, and the cap. ``cap_shown`` says the compute part
    already names the cap (the cloud's does). With nothing declared the cap holds compute only,
    and the line says so beside it."""
    if not agent.declared:
        held = (
            ""
            if cap is None
            else " (compute only)"
            if cap_shown
            else f" · {cap_words(cap)} (compute only)"
        )
        return f"{held} · {agent.not_priced()}"
    capped = "" if cap is None or cap_shown else f" · {cap_words(cap)}"
    if agent.free:
        return f" · {CALLS}: $0 ({agent.nothing()}){capped}"
    if compute_usd is None:
        return f" · {agent.phrase()}{capped}"
    total = compute_usd + (agent.usd or 0.0)
    return f" + {agent.phrase()} = ~{_look.fmt_dollars(total)}{capped}"


def document(agent: Agent, *, compute_usd: float | None, cap: float | None) -> dict[str, Any]:
    """The plan's ``cost`` object under ``--json``. ``total_usd`` is a number only when both
    parts are."""
    usd = agent.usd
    return {
        "compute_usd": compute_usd,
        "agent_usd_per_rollout": None if agent.cost is None else agent.cost.usd_per_rollout,
        "agent_usd": usd,
        "agent_basis": None if agent.cost is None else agent.cost.basis,
        "total_usd": None if usd is None or compute_usd is None else compute_usd + usd,
        "cap_usd": None if cap is None else float(cap),
    }


def over(agent: Agent, cap: float, *, compute_usd: float = 0.0) -> bool:
    """Whether the declared spend, with ``compute_usd`` beside it, is over ``cap``. The declared
    part is compared to the last digit of the rate as written, so an estimate that is the cap to
    the cent passes."""
    exact = agent.exact
    if exact is None:
        return False
    return exact + Decimal(repr(float(compute_usd))) > Decimal(repr(float(cap)))


def smallest_cap(agent: Agent, *, compute_usd: float = 0.0) -> str:
    """The smallest whole-cent cap that admits the estimate, as ``--max-cost`` takes it."""
    exact = (agent.exact or Decimal(0)) + Decimal(repr(float(compute_usd)))
    cents = exact.quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    if not math.isfinite(float(cents)):
        return str(cents)
    return f"{cents:.2f}"


def trial_line(agent: Agent) -> str:
    """The ``cost`` line of the trial call, by what the spec declares."""
    if agent.cost is None:
        return f"{CALLS} for one case; Prove stores nothing"
    if agent.free:
        return f"nothing: {agent.nothing()}; Prove stores nothing"
    rate = f"~${agent.cost.written} as {agent.name} declares"
    return f"{CALLS} for one case, {rate}; Prove stores nothing"
