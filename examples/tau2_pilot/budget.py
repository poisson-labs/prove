"""The T.4 spend guard: a per-episode ceiling the container enforces, not a note in a doc.

**What this can and cannot do, measured before it was written.**

``estimate_cost`` guards Modal compute and has never seen a token (C20), so nothing in
Proofload bounds provider spend. This module supplies the one bound a *container* can: a
ceiling on what one episode may spend, enforced inside the episode. The run-level cap is
arithmetic over that ceiling and the episode count, checked before each arm by
``scripts/tau2_t4_budget.py``; the only stop that binds unconditionally is a spend limit set on
the provider's own project, which lives outside this repository.

**Three measurements, 2026-09-14, litellm 1.80.0 against a local mock server -- no provider
spend.**

1. ``litellm.max_budget`` **is inert on τ²'s call shape.** litellm's own accumulator
   (``litellm_core_utils/litellm_logging.py``, the ``max_budget`` branch) adds a call's cost
   only when the result ``isinstance(result, dict) and "content" in result``. τ²'s results are
   ``ModelResponse`` objects, and its agent turns are tool calls whose ``content`` is ``None``.
   Ten calls at $0.0233 each left ``litellm._current_cost`` at ``0.0`` and ``max_budget = 0.05``
   never fired. So the budget must do its own accounting; setting ``max_budget`` alone is a
   guard that looks installed and is not.
2. **With accounting supplied, litellm's own pre-call check fires** -- ``utils.py``'s
   ``if litellm.max_budget: if litellm._current_cost > litellm.max_budget: raise
   BudgetExceededError``. That check is synchronous and is the stop.
3. **The stop lags by about two calls.** litellm runs success callbacks on a thread pool, so
   the cost of call *n* lands after call *n+1* has already been sent. Measured: budget $0.05,
   per-call $0.0233, stopped after **four** calls at $0.093 -- 86 % over. The ceiling is
   therefore sized as a runaway guard with headroom, never as a tight cap.

**Why the ceiling is not the run cap.** The most expensive episode in the smoke pair cost
$0.0246 by litellm's own cache-aware figure. A ceiling low enough to make ``episodes × ceiling``
fit $150 over three arms is $0.023 -- at or below the largest *legitimate* episode, so it would
kill real episodes and bias the arm. The ceiling here is roughly 2.4x the worst episode
measured; the cap is enforced at arm granularity by the launch gate instead, and the only stop
that binds unconditionally is a spend limit set on the provider's project, which is outside
this repository and is nobody's to set from a session.
"""

from __future__ import annotations

import os
import threading
from typing import Any

__all__ = [
    "BUDGET_VAR",
    "DEFAULT_EPISODE_BUDGET_USD",
    "BudgetStatus",
    "episode_budget",
    "install",
    "reset",
    "spent",
]

#: About 2.4x the most expensive episode in the 2026-09-13 smoke pair and 5.5x its mean.
#: Measured on the stored pair rather than quoted: over the twenty episodes of
#: ``20260913T113444Z-d44e`` and ``20260913T113537Z-a06a``, ``meta.cost_tau2.agent + .user`` is
#: $0.0101 and $0.0112 mean per run and **$0.0246 at the worst single episode**, over 18.5 LLM
#: calls per episode on average and 36 at the most.
#:
#: A runaway guard, and deliberately not the run cap: a ceiling low enough to make
#: ``episodes x ceiling`` fit $150 over three arms would sit at $0.023, at or under the most
#: expensive *legitimate* episode measured, and would kill real episodes and bias the arm.
DEFAULT_EPISODE_BUDGET_USD = 0.060

BUDGET_VAR = "TAU2_PILOT_EPISODE_BUDGET_USD"

_LOCK = threading.Lock()
_INSTALLED: BudgetStatus | None = None


class BudgetStatus:
    """What ``install()`` did, recorded on every row so a run without a guard is visible."""

    __slots__ = ("budget_usd", "active", "reason")

    def __init__(self, budget_usd: float, active: bool, reason: str | None) -> None:
        self.budget_usd = budget_usd
        self.active = active
        self.reason = reason

    def to_meta(self) -> dict[str, Any]:
        return {"budget_usd": self.budget_usd, "active": self.active, "reason": self.reason}

    def __repr__(self) -> str:  # pragma: no cover - a debugging aid
        return f"BudgetStatus(budget_usd={self.budget_usd}, active={self.active!r})"


def episode_budget() -> float:
    """The ceiling for this container, from the environment or the default."""
    raw = os.environ.get(BUDGET_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_EPISODE_BUDGET_USD
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_EPISODE_BUDGET_USD
    return value if value > 0 else DEFAULT_EPISODE_BUDGET_USD


def reset() -> None:
    """Zero the accumulator. **Called at the start of every episode, and that is not optional.**

    ``install()`` is once per process and Modal reuses a container across invocations, so
    ``batch_size = 1`` makes a container one episode *at a time* and not one episode ever. An
    accumulator that only zeroed at install would turn a per-episode ceiling into a
    per-container one and start refusing the third or fourth episode of every warm container --
    a failure that looks like the substrate and is ours.
    """
    try:
        import litellm
    except Exception:  # pragma: no cover - only outside the image
        return
    litellm._current_cost = 0.0


def spent() -> float:
    """What litellm has accounted for in this process so far, in dollars."""
    try:
        import litellm
    except Exception:  # pragma: no cover - only outside the image
        return 0.0
    return float(getattr(litellm, "_current_cost", 0.0) or 0.0)


def install(budget_usd: float | None = None) -> BudgetStatus:
    """Arm the per-episode ceiling. Once per process; the second call returns the first's status.

    Registers a litellm callback that adds each call's ``response_cost`` to
    ``litellm._current_cost`` -- the accounting measurement 1 showed litellm does not do for
    this call shape -- and sets ``litellm.max_budget``, which is the pre-call check that raises.
    """
    global _INSTALLED
    with _LOCK:
        if _INSTALLED is not None:
            return _INSTALLED
        ceiling = episode_budget() if budget_usd is None else float(budget_usd)
        try:
            import litellm
            from litellm.integrations.custom_logger import CustomLogger
        except Exception as exc:  # pragma: no cover - only outside the image
            _INSTALLED = BudgetStatus(ceiling, False, f"litellm unavailable: {exc!r}")
            return _INSTALLED

        class _Meter(CustomLogger):  # type: ignore[misc, valid-type]
            def log_success_event(
                self, kwargs: Any, response_obj: Any, start_time: Any, end_time: Any
            ) -> None:
                cost = kwargs.get("response_cost")
                if cost:
                    # litellm's own accumulator is the one the pre-call check reads; adding to
                    # it rather than keeping a second total is what makes the check fire.
                    litellm._current_cost += float(cost)

        litellm.callbacks = [*(litellm.callbacks or []), _Meter()]
        litellm._current_cost = 0.0
        litellm.max_budget = ceiling
        _INSTALLED = BudgetStatus(ceiling, True, None)
        return _INSTALLED
