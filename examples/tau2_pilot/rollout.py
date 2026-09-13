"""``rollout(cfg, seed) -> Episode`` over one unmodified τ²-bench airline task.

This is the whole surface Proofload sees. τ²-bench is not forked and not patched: it is
installed from a pinned commit inside the image (``examples/tau2_pilot/Dockerfile``) and used
through the three public entry points its own README documents --
``registry.get_tasks_loader``, ``build_text_orchestrator`` and ``run_simulation``. The
benchmark computes the verdict; this module reads it.

``cfg`` carries one axis, ``task_id``. ``seed`` is the episode's seed and it reaches the
provider: τ²'s ``Orchestrator.initialize`` calls ``set_seed`` on both the agent and the user
simulator, and ``LLMConfigMixin.set_seed`` writes it into ``llm_args["seed"]``, which LiteLLM
passes through as the OpenAI ``seed`` request parameter. Both sides of the conversation
therefore ride the same seed, which is what a paired design needs.

**It never raises across the seam.** An exception out of ``run_simulation`` is caught and
*labelled*, because ``executor._classify`` turns a raise into an errored row with no outcome,
and an errored row is excluded from the analysis rather than counted as a failure. The label
used is ``infrastructure_error`` -- τ²'s own name for this case, the one
``tau2.runner.controller.make_infra_failure_sim`` assigns when a unit dies in its queue.
"""

from __future__ import annotations

import os
import time
import traceback
from collections.abc import Mapping, Sequence
from importlib import metadata
from typing import Any

from tau2.config import DEFAULT_MAX_ERRORS, DEFAULT_MAX_STEPS
from tau2.data_model.simulation import TerminationReason, TextRunConfig
from tau2.registry import registry
from tau2.runner.build import build_text_orchestrator
from tau2.runner.simulation import run_simulation

from proofload import Episode

from . import DOMAIN as DOMAIN
from . import MAX_ERRORS, MAX_STEPS, OUTCOMES
from . import T_UNIT as T_UNIT

#: The pinned models, one per side of the conversation. They are constants and not defaults of
#: the image, so the pin is committed and diffable; ``target_id`` in the sweep file names the
#: agent's and ``meta["llm_agent"]`` records what the requests actually carried, which is what
#: makes a mislabelled run detectable after the fact.
AGENT_MODEL = "openai/gpt-4.1-mini-2025-04-14"
USER_MODEL = "openai/gpt-4.1-mini-2025-04-14"

#: Both sides, τ²'s own default. Fixed so the request is a pure function of ``(cfg, seed)`` up
#: to the provider.
TEMPERATURE = 0.0

AGENT_MODEL_VAR = "TAU2_PILOT_AGENT_MODEL"
USER_MODEL_VAR = "TAU2_PILOT_USER_MODEL"

#: The longest error text that may reach ``meta``.
MESSAGE_CAP = 800

#: τ²'s ``TerminationReason`` value -> the outcome stored. Identity on every name but one:
#: ``timeout`` is stored as ``timed_out`` (see ``__init__.OUTCOMES``). ``agent_stop`` and
#: ``user_stop`` are absent because those two are the cases where τ²'s reward decides.
_TERMINATED: dict[str, str] = {
    TerminationReason.MAX_STEPS.value: "max_steps",
    TerminationReason.TOO_MANY_ERRORS.value: "too_many_errors",
    TerminationReason.TIMEOUT.value: "timed_out",
    TerminationReason.AGENT_ERROR.value: "agent_error",
    TerminationReason.USER_ERROR.value: "user_error",
    TerminationReason.INFRASTRUCTURE_ERROR.value: "infrastructure_error",
    TerminationReason.CONTEXT_WINDOW_EXCEEDED.value: "context_window_exceeded",
    TerminationReason.UNEXPECTED_ERROR.value: "unexpected_error",
}

#: The two reasons that mean the conversation ended by itself, so the reward is the verdict.
_COMPLETED = frozenset({TerminationReason.AGENT_STOP.value, TerminationReason.USER_STOP.value})

# --- pins, checked once at import so a re-pin of the benchmark fails loudly ---------------

if MAX_STEPS != DEFAULT_MAX_STEPS:  # pragma: no cover - a guard, not a branch
    raise RuntimeError(
        f"tau2_pilot.MAX_STEPS is {MAX_STEPS} but tau2.config.DEFAULT_MAX_STEPS is "
        f"{DEFAULT_MAX_STEPS}. Episode.horizon is τ²'s cap, not ours: re-pin both together or "
        f"every stored t is on a different scale from every earlier run's."
    )
if MAX_ERRORS != DEFAULT_MAX_ERRORS:  # pragma: no cover - a guard, not a branch
    raise RuntimeError(
        f"tau2_pilot.MAX_ERRORS is {MAX_ERRORS} but tau2.config.DEFAULT_MAX_ERRORS is "
        f"{DEFAULT_MAX_ERRORS}."
    )
_UNMAPPED = {r.value for r in TerminationReason} - set(_TERMINATED) - _COMPLETED
if _UNMAPPED:  # pragma: no cover - a guard, not a branch
    raise RuntimeError(
        f"τ² has termination reasons this wrapper does not map: {sorted(_UNMAPPED)}. "
        f"Add them to _TERMINATED and to tau2_pilot.OUTCOMES together."
    )
if set(_TERMINATED.values()) - set(OUTCOMES):  # pragma: no cover - a guard, not a branch
    raise RuntimeError("_TERMINATED maps to a label outside tau2_pilot.OUTCOMES")


def _tau2_version() -> str:
    try:
        return metadata.version("tau2")
    except metadata.PackageNotFoundError:  # pragma: no cover - only outside the image
        return "unknown"


#: Resolved once per container, not once per episode: the airline tasks are 150 kB of JSON and
#: the domain module is imported with them.
_TASKS = {task.id: task for task in registry.get_tasks_loader(DOMAIN)()}
_TAU2_VERSION = _tau2_version()


def _model(var: str, default: str) -> str:
    return os.environ.get(var) or default


def _usage(messages: Sequence[Any]) -> dict[str, Any]:
    """Measured tokens, split by which side of the conversation spent them.

    τ² records one ``usage`` dict per generated message (``llm_utils.get_response_usage``), so
    this is the provider's own count and not an estimate. ``missing`` counts generated messages
    that carried none: a nonzero value means the totals are a floor, and it is recorded rather
    than silently tolerated.
    """
    out = {
        "in": 0,
        "out": 0,
        "agent_in": 0,
        "agent_out": 0,
        "user_in": 0,
        "user_out": 0,
        "missing": 0,
    }
    for message in messages:
        role = getattr(message, "role", None)
        if role not in ("assistant", "user"):
            continue
        usage = getattr(message, "usage", None)
        if not usage:
            out["missing"] += 1
            continue
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        side = "agent" if role == "assistant" else "user"
        out["in"] += prompt
        out["out"] += completion
        out[f"{side}_in"] += prompt
        out[f"{side}_out"] += completion
    return out


def _shape(messages: Sequence[Any]) -> dict[str, int]:
    """How the conversation was shaped. Every field is a count τ² already carries."""
    calls = 0
    roles = {"assistant": 0, "user": 0, "tool": 0}
    for message in messages:
        role = getattr(message, "role", None)
        if role in roles:
            roles[role] += 1
        calls += len(getattr(message, "tool_calls", None) or ())
    return {
        "n_messages": len(messages),
        "n_agent_messages": roles["assistant"],
        "n_user_messages": roles["user"],
        "n_tool_messages": roles["tool"],
        "n_tool_calls": calls,
    }


def _breakdown(reward_info: Any) -> dict[str, float]:
    raw = getattr(reward_info, "reward_breakdown", None) or {}
    return {getattr(k, "value", str(k)): float(v) for k, v in raw.items()}


def _outcome(reward: float, reason: str) -> str:
    """τ²'s verdict as a label. The only judgement here is which of τ²'s fields to read."""
    if reason in _COMPLETED:
        return "solved" if reward >= 1.0 else "unsolved"
    return _TERMINATED[reason]


def rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """One τ² airline task, once, at ``seed``. Never raises for anything τ² or the model did."""
    task_id = str(cfg["task_id"])
    task = _TASKS[task_id]
    agent_model = _model(AGENT_MODEL_VAR, AGENT_MODEL)
    user_model = _model(USER_MODEL_VAR, USER_MODEL)

    run_config = TextRunConfig(
        domain=DOMAIN,
        agent="llm_agent",
        llm_agent=agent_model,
        llm_args_agent={"temperature": TEMPERATURE},
        user="user_simulator",
        llm_user=user_model,
        llm_args_user={"temperature": TEMPERATURE},
        max_steps=MAX_STEPS,
        max_errors=MAX_ERRORS,
        seed=seed,
    )
    orchestrator = build_text_orchestrator(
        run_config,
        task,
        seed=seed,
        # Deterministic rather than τ²'s uuid4, so two episodes at the same (cfg, seed) differ
        # in their timings and in nothing else. It is an identifier, and nothing in τ² branches
        # on it.
        simulation_id=f"tau2-pilot-{DOMAIN}-{task_id}-{seed}",
    )

    started = time.perf_counter()
    try:
        simulation = run_simulation(orchestrator)
    except Exception:
        # τ²'s own name for a simulation that died rather than finished: the label
        # tau2.runner.controller.make_infra_failure_sim assigns in exactly this case.
        elapsed = time.perf_counter() - started
        messages = list(getattr(orchestrator, "trajectory", None) or ())
        return Episode(
            outcome="infrastructure_error",
            t=float(getattr(orchestrator, "step_count", 0)),
            horizon=float(MAX_STEPS),
            meta={
                "task_id": task_id,
                "domain": DOMAIN,
                "llm_agent": agent_model,
                "llm_user": user_model,
                "temperature": TEMPERATURE,
                "reward": None,
                "reward_breakdown": {},
                "reward_note": None,
                "termination_reason": None,
                "error": traceback.format_exc()[-MESSAGE_CAP:],
                "tokens": _usage(messages),
                "cost_tau2": {"agent": None, "user": None},
                "duration_s": elapsed,
                "tau2_version": _TAU2_VERSION,
                "tau2_commit": os.environ.get("TAU2_COMMIT"),
                **_shape(messages),
            },
        )

    messages = list(simulation.messages or ())
    reward_info = simulation.reward_info
    reward = float(getattr(reward_info, "reward", 0.0) or 0.0)
    reason = simulation.termination_reason.value
    note = (getattr(reward_info, "info", None) or {}).get("note")

    return Episode(
        outcome=_outcome(reward, reason),
        # τ²'s step counter, the one budget τ² itself enforces (`Orchestrator._check_termination`
        # stops at max_steps), so t <= horizon holds by construction and needs no clamp.
        t=float(orchestrator.step_count),
        horizon=float(MAX_STEPS),
        meta={
            "task_id": task_id,
            "domain": DOMAIN,
            "llm_agent": agent_model,
            "llm_user": user_model,
            "temperature": TEMPERATURE,
            "reward": reward,
            "reward_breakdown": _breakdown(reward_info),
            "reward_note": str(note) if note is not None else None,
            "termination_reason": reason,
            "error": None,
            "tokens": _usage(messages),
            # LiteLLM's own dollar figure for the same episode, kept beside the token counts so
            # the price table used to turn tokens into dollars can be checked against it.
            "cost_tau2": {"agent": simulation.agent_cost, "user": simulation.user_cost},
            "duration_s": float(simulation.duration),
            "tau2_version": _TAU2_VERSION,
            "tau2_commit": os.environ.get("TAU2_COMMIT"),
            **_shape(messages),
        },
    )
