"""The tau2-bench pilot (T.4, step one): a rollout wrapper over an unmodified τ²-bench.

Importing this package is free of side effects and does **not** import ``tau2``: the sweep is
launched from a laptop that need not have the benchmark installed, and only the container does.
``tau2_pilot.rollout`` is the module that imports it.

**Nothing here is a verdict of ours.** The pass/fail an episode carries is τ²'s own
``RewardInfo.reward``, computed by τ²'s evaluator from the airline domain's database diff and
its ``communicate_info`` substring checks. The premature-termination labels are τ²'s own
``TerminationReason`` values. This module only spells them.

**Why airline.** It is the only τ² domain whose every task is graded without an LLM judge:
all 50 airline tasks have ``reward_basis == [DB, COMMUNICATE]``, where ``DB`` is a
deterministic comparison of the final database against the task's expected state and
``COMMUNICATE`` is a substring search over the agent's own messages. Retail puts
``NL_ASSERTION`` on 112 of its 114 tasks, which runs a judge model and makes the gate partly
ours, with its own error term. Telecom is deterministic too (``ENV_ASSERTION``) but is 2,285
tasks over 88 MB of domain data and is mostly solo-mode workflow shapes. Airline is also the
domain the Airline worked example already targets.
"""

#: The τ² domain. See the module docstring for why this one and not retail or telecom.
DOMAIN = "airline"

#: What ``Episode.t`` counts: τ² orchestrator steps, the only budget τ² itself enforces.
T_UNIT = "steps"

#: ``Episode.horizon``. Must equal ``tau2.config.DEFAULT_MAX_STEPS``; ``rollout`` asserts it at
#: import, so a re-pin of the benchmark that moves the default fails loudly instead of silently
#: rescaling every stored ``t``.
MAX_STEPS = 200

#: τ²'s ``DEFAULT_MAX_ERRORS``. Asserted against ``tau2.config`` the same way.
MAX_ERRORS = 10

#: Exactly these, exactly one per episode. The first two are τ²'s reward under a conversation
#: that ended by itself; the other eight are τ²'s own ``TerminationReason`` values, because
#: ``evaluate_simulation`` forces ``reward = 0.0`` for every one of them and collapsing them
#: into ``unsolved`` would fuse "the agent finished and got it wrong" with "the run never
#: finished at all". ``diff`` reads the episode frame narrow and never touches ``meta``, so a
#: distinction that lives only in ``meta`` cannot be seen downstream (S22's lesson).
#:
#: One spelling is ours and only one: τ²'s ``timeout`` is stored as ``timed_out``, because S16
#: section 5 gave the bare string ``timeout`` to the executor's *errored* rows and an outcome
#: sharing it would be unreadable beside them. The verdict is unchanged; only the label is.
OUTCOMES: tuple[str, ...] = (
    "solved",
    "unsolved",
    "max_steps",
    "too_many_errors",
    "timed_out",
    "agent_error",
    "user_error",
    "infrastructure_error",
    "context_window_exceeded",
    "unexpected_error",
)

#: Every outcome but the absorbing one. Derived, never spelled twice.
FAILURE_EVENTS: tuple[str, ...] = tuple(o for o in OUTCOMES if o != "solved")
