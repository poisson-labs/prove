"""``rollout`` and ``rollout_patched``: one unmodified τ²-bench airline task, two arms.

``rollout`` is arm A and A′; ``rollout_patched`` is arm B, the same episode with one
policy-adherence paragraph appended after the domain policy (``guardrail.py``). The patch
reaches τ² through ``registry.register_agent_factory``, which is public at the pin and is
what ``build_agent`` resolves ``config.effective_agent`` through -- **no τ² file is edited,
and the two arms differ in one identifier.**

This is the whole surface Proofload sees. τ²-bench is not forked and not patched: it is
installed from a pinned commit inside the image (``examples/tau2_pilot/Dockerfile``) and used
through the three public entry points its own README documents --
``registry.get_tasks_loader``, ``build_text_orchestrator`` and ``run_simulation``. The
benchmark computes the verdict; this module reads it.

``cfg`` carries ``task_id`` and, for the T.4 sweep, ``task_family``. **``task_family`` is
read by nothing here on purpose**: it is a declared grouping key, not an input, and a
rollout that branched on it would make the two families different systems. The three junk
configs the sweep file's required ``[axes.task_family]`` grid produces carry no ``task_id``
at all; ``cfg["task_id"]`` raises ``KeyError`` on them, the executor records an errored row
with no outcome, and ``diff`` drops the cell as non-comparable. That is the declared
``n_errored = 3N`` per arm, and K8 is the check that it stayed three.

``seed`` is the episode's seed and it reaches the
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

import hashlib
import os
import time
import traceback
from collections.abc import Mapping, Sequence
from importlib import metadata
from typing import Any

from tau2.agent.llm_agent import LLMAgent
from tau2.config import DEFAULT_MAX_ERRORS, DEFAULT_MAX_STEPS
from tau2.data_model.simulation import TerminationReason, TextRunConfig
from tau2.registry import registry
from tau2.runner.build import build_text_orchestrator
from tau2.runner.simulation import run_simulation

from proofload import Episode

from . import DOMAIN as DOMAIN
from . import MAX_ERRORS, MAX_STEPS, OUTCOMES
from . import T_UNIT as T_UNIT
from .guardrail import GUARDRAIL, GUARDRAIL_SHA256, PATCHED_AGENT_NAME, guardrail_factory

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


#: The stock τ² agent, arm A's. Named rather than spelled at the call site so the two arms
#: differ in exactly one identifier.
STOCK_AGENT_NAME = "llm_agent"


def _register_guardrail_agent() -> None:
    """Register arm B's factory with τ², once per container.

    ``register_agent_factory`` raises ``ValueError`` on a duplicate name, and the executor may
    call the rollout many times in one process, so the guard is a lookup rather than a
    try/except: a genuine name collision -- somebody else registering ``tau2_pilot_guardrail``
    -- must still raise, and swallowing ``ValueError`` would hide it.
    """
    if registry.get_agent_factory(PATCHED_AGENT_NAME) is not None:
        return
    registry.register_agent_factory(
        lambda tools, domain_policy, **kwargs: guardrail_factory(
            LLMAgent, tools, domain_policy, **kwargs
        ),
        PATCHED_AGENT_NAME,
    )


def _prompt_proof(orchestrator: Any) -> dict[str, Any]:
    """What the agent this episode actually built will send, as two facts on the row.

    **This exists because K7 cannot be read the way the pre-registration states it.** K7 says
    to read "the system message of every stored conversation": τ²'s ``SimulationRun`` has no
    such field -- ``messages`` is ``Orchestrator.get_trajectory()``, which carries user,
    assistant and tool messages and no ``SystemMessage`` -- and the wrapper stores counts, not
    text. So the proof is taken here, from the agent τ² just built, and stored per row:
    whether the guardrail is in the prompt, and the prompt's digest, which is what tells arm A's
    rows from arm B's without storing either prompt.
    """
    agent = getattr(orchestrator, "agent", None)
    try:
        prompt = agent.system_prompt
    except Exception:  # noqa: BLE001 - a proof that cannot be taken is recorded as absent
        return {"system_prompt_sha256": None, "guardrail_in_system_prompt": None}
    text = prompt if isinstance(prompt, str) else str(prompt)
    return {
        "system_prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "guardrail_in_system_prompt": GUARDRAIL in text,
    }


def _run(cfg: Mapping[str, Any], seed: int, agent_name: str) -> Episode:
    """One τ² airline task, once, at ``seed``, under ``agent_name``.

    Arm A and arm B differ here in one argument and nowhere else: the same task, the same
    models, the same temperature, the same ``TextRunConfig`` fields, the same seed. Never
    raises for anything τ² or the model did.
    """
    task_id = str(cfg["task_id"])
    task = _TASKS[task_id]
    agent_model = _model(AGENT_MODEL_VAR, AGENT_MODEL)
    user_model = _model(USER_MODEL_VAR, USER_MODEL)
    if agent_name == PATCHED_AGENT_NAME:
        _register_guardrail_agent()

    arm_meta: dict[str, Any] = {
        "agent": agent_name,
        "guardrail_sha256": GUARDRAIL_SHA256 if agent_name == PATCHED_AGENT_NAME else None,
    }

    run_config = TextRunConfig(
        domain=DOMAIN,
        agent=agent_name,
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
        # on it. The arm is in it so arm A and arm B do not share a simulation id.
        simulation_id=f"tau2-pilot-{DOMAIN}-{agent_name}-{task_id}-{seed}",
    )
    arm_meta.update(_prompt_proof(orchestrator))

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
                **arm_meta,
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
            **arm_meta,
            **_shape(messages),
        },
    )


def rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """Arm A and A′: τ²'s stock ``llm_agent``, unpatched."""
    return _run(cfg, seed, STOCK_AGENT_NAME)


def rollout_patched(cfg: Mapping[str, Any], seed: int) -> Episode:
    """Arm B: the same episode with one policy-adherence paragraph after the domain policy.

    The only difference from ``rollout`` is ``agent_name``. τ² is unforked: the patched agent
    reaches it through ``registry.register_agent_factory``, which ``build_agent`` resolves by
    name, and no τ² file is read differently because of it.
    """
    return _run(cfg, seed, PATCHED_AGENT_NAME)
