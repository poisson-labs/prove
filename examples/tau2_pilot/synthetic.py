"""D0: a rollout with the T.4 sweep file's shape and no τ², no model and no money.

**What D0 is for.** The T.4 design declares three wholly-errored cells per arm -- the grid the
required ``[axes.task_family]`` table produces, which carries no ``task_id`` -- and asserts,
from a read of ``diff.py``, that they never reach the tree. A read is not a measurement (MAL
§18 rule 14), and this is the cheapest place to find out that the read was wrong: before arm A,
on a substrate that costs nothing. Pre-registration §10 step D0, and K8 is the criterion.

**It is a stand-in for the wrapper, not for τ².** It reads ``cfg["task_id"]`` exactly the way
``rollout`` does -- so the three junk configs raise ``KeyError`` here for the same reason they
will there -- and ignores ``task_family`` exactly the way ``rollout`` does. Everything else is
a deterministic function of ``(task_id, seed)``: no network, no clock, no global state.

``rollout_patched`` is a **positive control for the plumbing and nothing else.** It moves
``no_write`` and leaves the write families alone, which is the shape the real claim predicts,
so D0 can check that a located effect renders as one. Its effect size is chosen, not measured,
and no number out of a D0 run is evidence about τ², about the guardrail, or about anything
else.

It also emits one span per "turn" through the OpenTelemetry API, so a D0 run exercises the
capture path the sweep file asks for. ``_capture_table``'s own rule is that an empty
``instrument`` list is still a request: a target that emits spans itself needs no instrumentor,
and that is what this module is.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from proofload import Episode

#: How many "turns" a synthetic episode takes. Constant, so ``t`` carries the only thing D0
#: needs from it: a value the survival panel can render.
_TURNS = 4

#: Arm A's pass rate, and the family arm B moves. Chosen to make D0's tree legible, never
#: measured and never cited.
_BASE_PASS = 0.50
_PATCH_LIFT = 0.25
_PATCHED_FAMILY = "no_write"


def _unit(task_id: str, seed: int, salt: str) -> float:
    """A deterministic draw in [0, 1) from ``(task_id, seed)``. No RNG state, no global."""
    digest = hashlib.sha256(f"{salt}:{task_id}:{seed}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(1 << 64)


def _episode(cfg: Mapping[str, Any], seed: int, pass_rate: float, arm: str) -> Episode:
    task_id = str(cfg["task_id"])
    solved = _unit(task_id, seed, "outcome") < pass_rate
    try:
        from opentelemetry import trace

        tracer = trace.get_tracer("tau2_pilot.synthetic")
        for turn in range(_TURNS):
            with tracer.start_as_current_span("chat gpt-synthetic") as span:
                span.set_attribute("gen_ai.provider.name", "synthetic")
                span.set_attribute("gen_ai.request.temperature", 0.0)
                span.set_attribute("gen_ai.request.seed", seed)
                # The payload grows with the turn, the way a conversation's message list
                # does, so one episode straddles the 8192-byte budget: the early turns are
                # kept whole and the late ones are replaced by the marker. A D0 run therefore
                # exercises both sides of ``_apply_budget`` rather than one.
                span.set_attribute(
                    "gen_ai.input.messages",
                    f"turn {turn} of task {task_id}: " + "x" * (512 * 6**turn),
                )
                span.set_attribute("gen_ai.output.messages", f"turn {turn} reply")
    except Exception:  # noqa: BLE001 - a D0 run without the SDK still tests the junk cells
        pass
    return Episode(
        outcome="solved" if solved else "unsolved",
        t=float(_TURNS),
        horizon=float(_TURNS * 4),
        meta={
            "task_id": task_id,
            "task_family": cfg.get("task_family"),
            "arm": arm,
            "synthetic": True,
        },
    )


def rollout(cfg: Mapping[str, Any], seed: int) -> Episode:
    """D0's arm A. ``KeyError`` on a config with no ``task_id``, exactly as ``rollout`` does."""
    return _episode(cfg, seed, _BASE_PASS, "A")


def rollout_patched(cfg: Mapping[str, Any], seed: int) -> Episode:
    """D0's arm B: ``no_write`` lifted, the write families untouched."""
    rate = _BASE_PASS + (_PATCH_LIFT if cfg.get("task_family") == _PATCHED_FAMILY else 0.0)
    return _episode(cfg, seed, rate, "B")
