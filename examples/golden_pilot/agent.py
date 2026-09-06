"""The pilot's agent: a thin, ordinary tool-using loop over one golden.

Two entry points, and they are the only surface Proofload sees::

    rollout(cfg, seed)          -> Episode      arm A / A'
    rollout_patched(cfg, seed)  -> Episode      arm B

``cfg`` carries the sweep's two axes, ``task_id`` and ``temperature``; ``seed`` is the
episode's seed and rides every request. The loop is deliberately unremarkable: the pilot
measures the statistics, not the agent (spec section 1).

**This module refuses to import outside the isolation boundary.** It executes model-generated
code, so it raises ``RuntimeError`` at import unless ``GOLDEN_PILOT_BOUNDARY`` names the
container -- which only the Dockerfile does. A local ``sweep`` therefore fails at target
resolution with that message and never reaches a candidate (spec section 3, P13). This is a
refusal, not a warning, and it is checked at import rather than at call time so that the
failure is loud and early.

**The reply convention** is one fenced ``json`` block per turn holding exactly two keys,
``tool`` (``run_tests`` or ``submit``) and ``code`` (the complete candidate source). No
provider tool-call API: the fenced-JSON convention keeps the loop portable across
OpenAI-compatible endpoints and keeps every model call a ``chat.completions.create``, which
is the one surface ``opentelemetry-instrumentation-openai-v2`` wraps (spec section 0, gap 1).

**The trace.** The loop runs inside ``collect()`` under one ``record("agent", "golden")``
root, with a ``record("tool", ...)`` span per tool call, so the recorder's trace has
parentage and a ``tool`` vocabulary. Before returning, ``code.filepath`` on those spans is
rewritten relative to ``examples/`` -- the same string on a laptop and inside the container
(spec section 0, gap 2). The captured llm spans are merged in by the executor *after* this
function returns, so they are not ours to touch, and the episode stamps ride them alone.
Nothing model-written enters the trace: a span records whether the check passed, never the
candidate source or the conversation.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import openai

from proofload import Episode, record
from proofload.trace import Trace, collect

from . import HORIZON as HORIZON
from . import OUTCOMES as OUTCOMES
from . import T_UNIT as T_UNIT
from . import sandbox, suite

BOUNDARY_VAR = "GOLDEN_PILOT_BOUNDARY"
BOUNDARY_VALUE = "container"

if os.environ.get(BOUNDARY_VAR) != BOUNDARY_VALUE:
    raise RuntimeError(
        f"golden_pilot.agent executes model-generated code and imports only inside the "
        f"isolation boundary: {BOUNDARY_VAR}={BOUNDARY_VALUE} is not set. "
        f"examples/golden_pilot/Dockerfile sets it for the Modal image; the local backend is "
        f"unsupported for this suite, so run the sweep with --backend modal."
    )

#: Backoff between the attempt and each of its three retries. Read at call time.
BACKOFF_S = (1.0, 2.0, 4.0)

#: Fixed, so the request is a pure function of ``(cfg, seed)`` up to the model's reply.
MAX_TOKENS = 2048

#: The model name rides the environment and is pinned in the sweep's ``target_id``.
MODEL_VAR = "GOLDEN_PILOT_MODEL"
DEFAULT_MODEL = "gpt-4o-mini"

#: The longest failure text that may reach the model (P6): the whole message, not the reason.
MESSAGE_CAP = 500

#: ``examples/``. A span's ``code.filepath`` is rewritten relative to this.
_PILOT_DIR = Path(__file__).resolve().parent
_RELATIVE_BASE = _PILOT_DIR.parent

SYSTEM_PROMPT = (
    "You are completing one Python function. Reply with exactly one fenced json block and "
    "nothing that matters outside it. The block holds a JSON object with exactly two keys:\n"
    '  "tool": either "run_tests" or "submit"\n'
    '  "code": the complete source of the function, imports and signature included\n'
    "run_tests runs the hidden tests against your code and reports the first failure. "
    "submit ends the task with the code you give it. You have a budget of "
    f"{HORIZON} tool calls."
)

REPAIR_PROMPT = (
    "That reply had no usable tool call. Reply with exactly one fenced json block holding a "
    'JSON object with exactly the two keys "tool" and "code".'
)

REFUSAL_MESSAGE = (
    "tool error: run_tests must be called at least once in this episode before submit."
)
_REFUSAL_SPAN_ERROR = "ToolError: submit before run_tests"

_PARSE_FAILURE = "unparseable reply after one repair turn: no fenced json tool call"

#: The fenced block, matched on its delimiters rather than on braces: the candidate source is
#: JSON-escaped inside the object and routinely contains ``}``, which a brace-matching regex
#: would cut the object short on.
_FENCE = re.compile(r"```json\s*(.*?)```", re.S)

_TOOLS = ("run_tests", "submit")


def client_factory() -> openai.OpenAI:
    """The one place a client is built. Replaced wholesale by the oracle's scripted transport.

    ``max_retries=0`` because the loop owns its retry policy: the SDK's own retries would
    triple the request count behind ``meta["retries"]`` and hide the API errors this pilot
    counts. ``OPENAI_BASE_URL`` and ``OPENAI_API_KEY`` come from the environment.
    """
    return openai.OpenAI(max_retries=0)


def _model() -> str:
    return os.environ.get(MODEL_VAR) or DEFAULT_MODEL


def _parse(content: str | None) -> tuple[str, str] | None:
    """``(tool, code)`` from a model reply, or None when there is no usable tool call."""
    if not content:
        return None
    match = _FENCE.search(content)
    if match is None:
        return None
    try:
        call = json.loads(match.group(1).strip())
    except ValueError:
        return None
    if not isinstance(call, dict) or set(call) != {"tool", "code"}:
        return None
    tool, code = call["tool"], call["code"]
    if tool not in _TOOLS or not isinstance(code, str):
        return None
    return str(tool), code


def _call(
    client: Any,
    messages: list[dict[str, str]],
    temperature: float,
    seed: int,
    tokens: dict[str, int],
) -> tuple[str | None, str | None, int]:
    """One model turn: ``(reply text, error text, retries made)``.

    The attempt and three retries, then the episode crashes. ``BACKOFF_S`` and the model name
    are read here, at call time, so a caller may replace either.
    """
    backoff = BACKOFF_S
    retries = 0
    while True:
        try:
            response = client.chat.completions.create(
                model=_model(),
                messages=messages,
                max_tokens=MAX_TOKENS,
                seed=seed,
                temperature=temperature,
            )
        except openai.APIError as exc:
            if retries >= len(backoff):
                text = f"API error after {retries} retries: {type(exc).__name__}: {exc}"
                return None, text[:MESSAGE_CAP], retries
            time.sleep(backoff[retries])
            retries += 1
            continue
        usage = getattr(response, "usage", None)
        if usage is not None:
            tokens["in"] += int(getattr(usage, "prompt_tokens", 0) or 0)
            tokens["out"] += int(getattr(usage, "completion_tokens", 0) or 0)
        choices = getattr(response, "choices", None) or ()
        content = choices[0].message.content if choices else ""
        return content or "", None, retries


def _checked(result: sandbox.TestResult) -> sandbox.TestResult:
    """The sandbox's verdict, or a raise when the sandbox itself broke.

    A broken sandbox is Proofload failing to observe, not the agent failing the task. Scoring
    it ``failed_assertion`` would put a harness fault in the pilot's headline number; raising
    puts the episode in an errored row where ``numbers.py`` counts it apart (spec section 3).
    """
    if result.harness_error:
        raise RuntimeError(f"golden_pilot sandbox failed, not the candidate: {result.reason}")
    return result


def _tool_message(result: sandbox.TestResult) -> str:
    body = "PASS: every assertion held." if result.passed else f"FAIL: {result.reason}"
    return body[:MESSAGE_CAP]


def _relative(filepath: Any) -> str:
    """``code.filepath`` as ``golden_pilot/<file>`` -- the same string on both backends."""
    raw = Path(str(filepath))
    try:
        return raw.resolve().relative_to(_RELATIVE_BASE).as_posix()
    except (ValueError, OSError):
        return f"{_PILOT_DIR.name}/{raw.name}"


def _scrubbed(trace: Trace) -> Trace:
    """The recorder's trace with every absolute ``code.filepath`` made relative (gap 2)."""
    spans = []
    for span in trace.spans:
        if span.code is None:
            spans.append(span)
            continue
        code = {**span.code, "filepath": _relative(span.code["filepath"])}
        spans.append(dataclasses.replace(span, code=code))
    return dataclasses.replace(trace, spans=tuple(spans))


def _loop(cfg: Mapping[str, Any], seed: int, *, require_tests: bool) -> Episode:
    """The whole agent. Never raises for anything the model or the candidate did."""
    task_id = str(cfg["task_id"])
    temperature = float(cfg["temperature"])
    golden = suite.by_id(task_id)
    client = client_factory()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": golden.prompt},
    ]
    tokens = {"in": 0, "out": 0}
    t = 0
    retries = 0
    tested = False
    outcome: str | None = None
    crash_reason: str | None = None

    with collect() as collector:
        with record("agent", "golden"):
            while outcome is None:
                if t >= HORIZON:
                    outcome = "timed_out"
                    break
                content, error, made = _call(client, messages, temperature, seed, tokens)
                retries += made
                if content is None:
                    outcome, crash_reason = "crashed", error
                    break
                messages.append({"role": "assistant", "content": content})
                call = _parse(content)
                if call is None:
                    # One repair turn, then the episode crashes (spec section 3).
                    messages.append({"role": "user", "content": REPAIR_PROMPT})
                    content, error, made = _call(client, messages, temperature, seed, tokens)
                    retries += made
                    if content is None:
                        outcome, crash_reason = "crashed", error
                        break
                    messages.append({"role": "assistant", "content": content})
                    call = _parse(content)
                    if call is None:
                        outcome, crash_reason = "crashed", _PARSE_FAILURE
                        break
                tool, code = call
                t += 1
                if tool == "run_tests":
                    with record("tool", "run_tests") as span:
                        result = _checked(sandbox.run_tests(code, golden))
                        span.output = {"passed": result.passed}
                    tested = True
                    messages.append({"role": "user", "content": _tool_message(result)})
                    continue
                if require_tests and not tested:
                    # Arm B's patch: the refusal is a tool call spent, and nothing else about
                    # the episode changes -- same prompt, same request shape as arm A.
                    with record("tool", "submit") as span:
                        span.error = _REFUSAL_SPAN_ERROR
                    messages.append({"role": "user", "content": REFUSAL_MESSAGE})
                    continue
                with record("tool", "submit") as span:
                    result = _checked(sandbox.run_tests(code, golden))
                    span.output = {"passed": result.passed}
                outcome = "passed" if result.passed else "failed_assertion"

    return Episode(
        outcome=outcome if outcome is not None else "crashed",
        t=t,
        horizon=HORIZON,
        meta={
            "task_id": task_id,
            # The model the requests actually carried. target_id names one too, and nothing
            # makes them agree; recording it here is what makes a mislabelled run detectable
            # after the fact instead of only documented in the README.
            "model": _model(),
            "crash_reason": crash_reason,
            "retries": retries,
            "tokens": tokens,
            "trace": _scrubbed(collector.trace).to_dict(),
        },
    )


def rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """Arm A: the agent as it stands. Submit is accepted whenever the model asks for it."""
    return _loop(cfg, seed, require_tests=False)


def rollout_patched(cfg: Mapping[str, Any], seed: int) -> Episode:
    """Arm B: submit is refused until ``run_tests`` has run once, and the refusal costs a call.

    A guardrail in the loop, not a change to the prompt: arm A and arm B send byte-identical
    requests until the first refusal, so whatever the paired diff shows is the patch.
    """
    return _loop(cfg, seed, require_tests=True)
