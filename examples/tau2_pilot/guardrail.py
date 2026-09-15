"""T.4 arm B: the one policy-adherence paragraph, its hash, and the agent it is attached to.

**This module is free of side effects and does not import ``tau2``.** The text and its hash
are the pre-registered constants of arm B, and a session that wants to check the hash -- or a
test that wants to check the patch -- must not need the benchmark installed to do it. The two
τ²-facing helpers take the agent class and the factory as *arguments*, so the attachment is
testable against a stand-in and the real classes are supplied by ``rollout.py``.

**What is fixed here.** ``GUARDRAIL`` is the paragraph, exactly. ``GUARDRAIL_SHA256`` is the
sha256 of its UTF-8 bytes. The line breaks inside the paragraph are soft wraps and are not
semantic -- but they *are* hashed, because the hash is of the bytes that reach the provider,
not of some normalization of them. Re-wrapping the text is a new arm and gets a new hash.

**Where it attaches.** ``LLMAgent.system_prompt`` is a read-only property returning
``SYSTEM_PROMPT.format(domain_policy=..., agent_instruction=AGENT_INSTRUCTION)``, and
``SYSTEM_PROMPT`` closes with ``</policy>``. The guardrail goes *after* that -- after the
policy, not inside it -- so the agent reads the airline policy τ² wrote and then one
instruction of ours, and a reader of the stored prompt can tell the two apart.

**Why a subclass and not a string edit.** τ² is unforked. ``register_agent_factory`` is public
at the pin (``registry.py``), ``build_text_orchestrator`` resolves ``config.effective_agent``
through ``get_agent_factory``, and ``build_agent`` calls the factory as
``factory(tools=..., domain_policy=..., llm=..., llm_args=..., task=...,
audio_native_config=..., audio_taps_dir=...)``. **Seven keyword arguments, not the five the
pre-registration lists** -- ``audio_taps_dir`` is passed by ``build_agent`` on every path and
is absent from §2.2's list -- which is why the factory here takes ``**kwargs`` the way τ²'s
own ``create_llm_agent`` does, rather than naming its parameters.
"""

from __future__ import annotations

import hashlib
from typing import Any

__all__ = [
    "GUARDRAIL",
    "GUARDRAIL_SHA256",
    "PATCHED_AGENT_NAME",
    "WRITE_TOOLS",
    "append_guardrail",
    "guardrail_agent_class",
    "guardrail_factory",
]

#: The six airline tools whose call changes a reservation. The guardrail names them, and the
#: sweep file's family rule partitions on the same set -- one list, two readers, so a tool that
#: enters or leaves the set cannot move one without the other.
WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "book_reservation",
        "cancel_reservation",
        "update_reservation_flights",
        "update_reservation_passengers",
        "update_reservation_baggages",
        "send_certificate",
    }
)

#: The arm-B paragraph, fixed before any arm runs. §2.2 of the pre-registration.
GUARDRAIL = """
Before you call any tool that changes a reservation (book_reservation, cancel_reservation,
update_reservation_flights, update_reservation_passengers, update_reservation_baggages,
send_certificate): state to the user the policy rule that permits the change, the exact
change, and its cost, and proceed only after the user says yes. If no policy rule permits the
change, say which rule prevents it and do not call the tool.
""".strip()

#: sha256 of ``GUARDRAIL``'s UTF-8 bytes. Recorded in the pre-registration and the devlog so the
#: arm is identifiable from a stored run without the text being stored on every row.
GUARDRAIL_SHA256 = hashlib.sha256(GUARDRAIL.encode("utf-8")).hexdigest()

#: The name arm B registers the patched factory under. Never ``llm_agent``: registering over
#: τ²'s own name would patch the baseline too, and ``register_agent_factory`` refuses a
#: duplicate name anyway, so a collision fails loudly rather than silently swapping arm A.
PATCHED_AGENT_NAME = "tau2_pilot_guardrail"


def append_guardrail(system_prompt: str) -> str:
    """τ²'s system prompt with the guardrail after it, separated by one blank line.

    The whole of the patch, in one function, so the test that asserts what arm B sends and the
    code that sends it read the same rule.
    """
    return f"{system_prompt}\n\n{GUARDRAIL}"


#: One subclass per base class, not one per episode. A container serves many episodes and
#: ``guardrail_factory`` is called for each; building a fresh class every time would leave a
#: new type object behind per episode for no gain, and would make ``type(agent)`` differ
#: between two episodes of the same arm.
_SUBCLASSES: dict[type, type] = {}


def guardrail_agent_class(base: type) -> type:
    """``base`` with ``system_prompt`` overridden to append the guardrail.

    ``base`` is τ²'s ``LLMAgent`` in the container and a stand-in in the tests. The override is
    a property because τ²'s is: shadowing a property with a plain attribute on the subclass
    would not take, and shadowing it with a method would return a bound method where the
    orchestrator expects a string.
    """

    cached = _SUBCLASSES.get(base)
    if cached is not None:
        return cached

    class GuardrailAgent(base):  # type: ignore[misc, valid-type]
        """τ²'s agent with one paragraph appended after the domain policy."""

        @property
        def system_prompt(self) -> str:
            # ``super()`` on a property: fget through the parent class, not the instance.
            base_prompt: str = base.system_prompt.fget(self)  # type: ignore[attr-defined]
            return append_guardrail(base_prompt)

    GuardrailAgent.__name__ = f"Guardrail{base.__name__}"
    GuardrailAgent.__qualname__ = GuardrailAgent.__name__
    _SUBCLASSES[base] = GuardrailAgent
    return GuardrailAgent


def guardrail_factory(base: type, tools: Any, domain_policy: Any, **kwargs: Any) -> Any:
    """The factory τ² calls, with ``base`` bound by the caller.

    Signature and kwarg handling mirror τ²'s own ``create_llm_agent``: positional ``tools`` and
    ``domain_policy``, everything else by ``**kwargs``, so an argument τ² adds to ``build_agent``
    later -- as it already did with ``audio_taps_dir`` -- does not raise ``TypeError`` here.
    """
    return guardrail_agent_class(base)(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm"),
        llm_args=kwargs.get("llm_args"),
    )
