"""The golden suite pilot (Phase 3.5): a user of Prove, outside the package.

Importing this package is free of side effects. ``golden_pilot.agent`` refuses to import
outside the isolation boundary (``GOLDEN_PILOT_BOUNDARY``, which only the Dockerfile sets),
so it is deliberately not imported here: ``suite``, ``sandbox``, ``numbers`` and ``make_toml``
run on a laptop, and only the module that executes model-generated code is gated.

**The outcome vocabulary lives here and nowhere else.** It used to be spelled twice -- once
in ``agent.py`` and once in ``numbers.py``, which cannot import the agent because the agent
refuses to import outside the boundary and ``numbers.py`` runs on a laptop. Two spellings of
one vocabulary drift on the next change. This module is the one both can reach: boundary-free,
side-effect free, and already imported by every module in the tree.
"""

#: Exactly these, exactly one per episode, in this order. Never ``timeout`` (S16 section 5
#: gave that string to the executor's errored rows), never ``error``, never empty -- and note
#: that ``api_error`` *contains* ``error`` and is excluded by neither, because the exclusion
#: is of the whole name and not of a substring.
#:
#: ``crashed`` is **the agent's own code could not continue**: a reply that did not parse
#: after its repair turn. ``api_error`` is **the agent could not reach the model**: an
#: ``openai.APIError`` that survived the attempt and all three backoffs. They were one label
#: until S22. ``diff`` reads the episode frame narrow and never touches ``meta``, so a
#: distinction that lives in ``meta["crash_reason"]`` cannot be seen by anything downstream;
#: the label is the only place it can live.
OUTCOMES: tuple[str, ...] = (
    "passed", "failed_assertion", "timed_out", "crashed", "api_error",
)

#: The competing risks: every outcome but the absorbing one. **Derived, never spelled** -- a
#: literal here would be a third copy of the vocabulary, and a further outcome would join it
#: or not by whoever remembered.
FAILURE_EVENTS: tuple[str, ...] = tuple(o for o in OUTCOMES if o != "passed")

#: What ``t`` counts, and the budget it counts against.
T_UNIT = "tool_calls"
HORIZON = 6
