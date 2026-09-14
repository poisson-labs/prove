"""The frozen fault vocabulary M11 injects, and the attribution it ships under.

**Attribution.** The fault *names*, their ``target_path`` values and their literal
replacement strings are copied from AgentChaos -- ``github.com/floritange/AgentChaos``,
the ``agentchaos-sdk`` distribution on PyPI, version ``0.1.0``, read from the installed
wheel at ``agentchaos/fault_config.py:19``-``:284``. AgentChaos is published under the
**MIT** licence and Proofload is published under the MIT licence, which is what makes the
copy clean and the attribution mandatory. The repository root's ``NOTICE`` says the same.

**No code is taken and no dependency is carried** (spec M11 D1): the mutation semantics
behind these names are Proofload's own, in ``proofload.chaos``, and this module imports
nothing but the standard library.

**The entries carry no state** (D17). Each is a frozen five-field record --
``(name, intercept, action, target_path, value)`` -- with no ``probability``, no
``max_count``, no ``min_count`` and no ``_count``: ``proofload.chaos`` owns the firing
decision, so an entry has nothing to count and the exhausted-singleton failure mode is
unrepresentable rather than guarded against.

**What is not here.** The ``persistent`` / ``intermittent`` / ``burst`` strategies and the
nine positional variants are policies over a global call ordinal, which ADR-075 refuses;
``rate`` and ``steps`` keyed on ``(step_name, attempt)`` supply the same expressiveness.
``compound_stale_cache`` is dropped because its action replays the previous response,
which is a policy across calls rather than a mutation of one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__: list[str] = []

#: The catalogue revision. It stamps which mutation semantics produced a body, and it bumps
#: when any entry or any action's semantics change -- never for an unrelated release.
ENGINE_VERSION = "m11-catalog/1"

CONTENT_PATH = "$.choices[0].message.content"
TOOL_CALLS_PATH = "$.choices[0].message.tool_calls"
FIRST_CALL_PATH = "$.choices[0].message.tool_calls[0]"
ARGUMENTS_PATH = "$.choices[0].message.tool_calls[0].function.arguments"
FINISH_PATH = "$.choices[0].finish_reason"
WHOLE_BODY_PATH = "$"


@dataclass(frozen=True)
class FaultEntry:
    """One mutation of one response body. Five fields, frozen, and no counter."""

    name: str
    intercept: str
    action: str
    target_path: str | None
    value: Any


_Row = tuple[str, str, str | None, Any]


def _entries(name: str, rows: tuple[_Row, ...]) -> tuple[FaultEntry, ...]:
    return tuple(FaultEntry(name, *row) for row in rows)


_ROWS: dict[str, tuple[_Row, ...]] = {
    "llm_error_single": (
        (
            "response",
            "set",
            CONTENT_PATH,
            "[API ERROR] HTTP 500: Internal Server Error. "
            "The server encountered an unexpected condition.",
        ),
    ),
    "llm_timeout_single": (
        (
            "response",
            "set",
            CONTENT_PATH,
            "[TIMEOUT] The request timed out. The server did not respond within the expected time.",
        ),
    ),
    "llm_empty_single": (("response", "set", CONTENT_PATH, ""),),
    "llm_truncate_single": (("response", "truncate", CONTENT_PATH, 0.3),),
    "llm_corrupt_single": (("response", "corrupt", CONTENT_PATH, "mojibake"),),
    "llm_schema_single": (
        (
            "response",
            "set",
            CONTENT_PATH,
            '{"error": "content_policy_violation", "message": "This response has been filtered."}',
        ),
    ),
    "tool_error_single": (("response", "set", ARGUMENTS_PATH, "{}"),),
    "tool_timeout_single": (("response", "drop", FIRST_CALL_PATH, None),),
    "tool_empty_single": (("response", "set", TOOL_CALLS_PATH, []),),
    "tool_truncate_single": (("response", "truncate", ARGUMENTS_PATH, 0.3),),
    "tool_corrupt_single": (("response", "corrupt", ARGUMENTS_PATH, "unicode"),),
    "tool_schema_single": (
        ("response", "set", ARGUMENTS_PATH, '{"wrong_param": "unexpected_value"}'),
    ),
    "compound_api_degradation": (
        ("response", "delay", WHOLE_BODY_PATH, 3000),
        (
            "response",
            "set",
            CONTENT_PATH,
            "[SERVICE UNAVAILABLE] HTTP 503: "
            "The server is temporarily unable to handle the request.",
        ),
    ),
    "compound_content_filter": (
        ("response", "set", TOOL_CALLS_PATH, []),
        (
            "response",
            "set",
            CONTENT_PATH,
            "[CONTENT FILTERED] This response has been blocked by the content safety filter.",
        ),
        ("response", "set", FINISH_PATH, "content_filter"),
    ),
    "compound_max_tokens": (
        ("response", "truncate", CONTENT_PATH, 0.5),
        ("response", "set", FINISH_PATH, "length"),
    ),
    "compound_proxy_html": (
        (
            "response",
            "set",
            CONTENT_PATH,
            "<!DOCTYPE html>\n<html><head><title>502 Bad Gateway</title></head>\n"
            "<body><center><h1>502 Bad Gateway</h1></center><hr>"
            "<center>nginx/1.24.0</center></body></html>",
        ),
    ),
    "compound_stale_data": (("response", "set", ARGUMENTS_PATH, '{"city": "Pyongyang"}'),),
    "compound_wrong_entity": (("response", "set", ARGUMENTS_PATH, '{"city": "Springfield"}'),),
    "compound_slow_response": (("response", "delay", WHOLE_BODY_PATH, 5000),),
}

#: Fault name -> the entries of that scenario, in application order. Read at call time by
#: ``proofload.chaos``: rebinding this name is how a test reaches an action no shipped entry
#: uses, and nothing caches it at import.
CATALOG: dict[str, tuple[FaultEntry, ...]] = {
    name: _entries(name, rows) for name, rows in _ROWS.items()
}
