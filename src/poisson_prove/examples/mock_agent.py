"""The keyless mock agent: a fixture with the shape of a tool-using agent, not an agent.

Its point is that the quickstart runs end to end with no API key and no network. Config keys
are the ``tool-reliability`` preset's: ``task_id`` (categorical) and ``tool_fail_rate``
(continuous). A ``random.Random(seed)`` walks up to ``HORIZON`` tool calls; each call fails
with probability ``tool_fail_rate``; three consecutive failures mean the agent takes a
forbidden fallback (``outcome="violated"``); finishing the task's tool sequence is
``"completed"``; reaching the horizon is ``"timeout"``. ``t`` counts tool calls.

``rollout_patched`` retries a failed call once before counting the failure. Both agents draw
the same random numbers per call, so a call that fails for the patched agent also fails for
the original: the patched agent violates no more often than the original for every
``(cfg, seed)``, which is what makes the quickstart's paired diff clean.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from typing import Any

from poisson_prove.episode import Episode
from poisson_prove.trace import Span, Trace

__all__ = ["rollout", "rollout_patched"]

HORIZON = 20
T_UNIT = "tool_calls"

#: Simulated wall clock. A simulation gets simulated time: reading the real clock would let two
#: consecutive spans tie on ``start_ns``, and the mock would stop being a pure function of
#: ``(cfg, seed)``. A later change that wants the mock to dogfood ``record()`` injects a fake
#: clock through the same helper the tests pin.
MOCK_EPOCH_NS = 1_700_000_000_000_000_000

_MAX_CONSECUTIVE_FAILURES = 3
_TOOL_ERROR = "ToolError"

_TASKS: dict[str, tuple[str, ...]] = {
    "search": (
        "parse_query",
        "search_catalog",
        "open_result",
        "read_page",
        "extract_answer",
        "cross_check",
        "cite_source",
        "compose_reply",
    ),
    "checkout": (
        "search_catalog",
        "open_product",
        "check_stock",
        "add_to_cart",
        "apply_coupon",
        "enter_address",
        "validate_address",
        "select_shipping",
        "compute_tax",
        "confirm_payment",
        "record_receipt",
        "send_confirmation",
    ),
    "refund": (
        "lookup_order",
        "verify_identity",
        "read_policy",
        "check_eligibility",
        "open_ticket",
        "attach_receipt",
        "inspect_item",
        "compute_amount",
        "request_approval",
        "await_approval",
        "issue_refund",
        "update_ledger",
        "notify_customer",
        "log_outcome",
        "archive_ticket",
        "close_ticket",
    ),
}
_DEFAULT_TASK = "checkout"


def _tools_for(task_id: Any) -> tuple[str, ...]:
    return _TASKS.get(str(task_id), _TASKS[_DEFAULT_TASK])


def _rate(cfg: Mapping[str, Any]) -> float:
    rate = float(cfg.get("tool_fail_rate", 0.0))
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"tool_fail_rate must be in [0, 1], got {rate}")
    return rate


def _walk(cfg: Mapping[str, Any], seed: int, *, retry: bool) -> Episode:
    rate = _rate(cfg)
    task_id = str(cfg.get("task_id", _DEFAULT_TASK))
    tools = _tools_for(task_id)
    rng = random.Random(seed)
    spans: list[Span] = []
    start_ns = MOCK_EPOCH_NS
    done = 0
    consecutive = 0
    outcome = "timeout"
    for i in range(HORIZON):
        first, second, jitter = rng.random(), rng.random(), rng.random()
        tries = 1
        failed = first < rate
        if failed and retry:
            tries = 2
            failed = second < rate
        latency_ms = round(5.0 + 45.0 * jitter + 30.0 * (tries - 1), 1)
        end_ns = start_ns + round(latency_ms * 1_000_000)
        spans.append(
            Span(
                span_id=f"{i:016x}",
                parent_id=None,
                kind="tool",
                name=tools[done],
                start_ns=start_ns,
                end_ns=end_ns,
                error=_TOOL_ERROR if failed else None,
                code=None,
                attrs={"tries": tries},
            )
        )
        start_ns = end_ns
        if failed:
            consecutive += 1
            if consecutive >= _MAX_CONSECUTIVE_FAILURES:
                outcome = "violated"
                break
        else:
            consecutive = 0
            done += 1
            if done == len(tools):
                outcome = "completed"
                break
    trace = Trace(spans=tuple(spans), source="record").to_dict()
    return Episode(
        outcome=outcome, t=len(spans), horizon=HORIZON, meta={"trace": trace, "task_id": task_id}
    )


def rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The "before" agent: one attempt per tool call."""
    return _walk(cfg, seed, retry=False)


def rollout_patched(cfg: Mapping[str, Any], seed: int) -> Episode:
    """The "after" agent: retries a failed tool call once before counting the failure."""
    return _walk(cfg, seed, retry=True)
