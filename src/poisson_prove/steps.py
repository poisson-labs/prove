"""Per-run step statements: what a run declared against what its stored spans show.

``DeclarationCheck`` and ``declaration_check``. Everything here is a set or the difference of
two sets; nothing is derived, nothing is persisted, no rate is computed and no trace object is
constructed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from poisson_prove.store import RunManifest
from poisson_prove.trace import Declaration

__all__ = ["DeclarationCheck", "declaration_check"]


@dataclass(frozen=True)
class DeclarationCheck:
    """A run's declaration held against its stored spans.

    ``never_reached`` is each name in ``declared_steps`` that no span of this run carries as its
    ``step_name``. It does not say the target cannot reach the step, that the step was not
    instrumented, or that anything is wrong: this run's spans did not show it, and the
    declaration's owner said the step exists. ``declared_never_reached`` is the same over the
    declared gates, read from ``step_name`` and never from the ``"declared"`` stamp, which would
    say the stamp ran and not that the step did. ``emitted_not_declared`` is a finding about the
    declaration, never a refusal. Sets and their sizes only: a fraction of a declared set is a
    rate, and a rate is a verdict.
    """

    declared_steps: frozenset[str]
    observed_steps: frozenset[str]
    never_reached: frozenset[str]
    undeclared_steps: frozenset[str]
    declared_outcomes: frozenset[str]
    observed_outcomes: frozenset[str]
    undeclared_outcomes: frozenset[str]
    declared_gates: frozenset[str]
    emitted_gates: frozenset[str]
    emitted_not_declared: frozenset[str]
    declared_never_reached: frozenset[str]

    def provenance(self) -> dict[str, list[str]]:
        """The eight provenance keys in the report's order, each a sorted list."""
        return {
            "declared_steps": sorted(self.declared_steps),
            "never_reached": sorted(self.never_reached),
            "undeclared_steps": sorted(self.undeclared_steps),
            "declared_outcomes": sorted(self.declared_outcomes),
            "undeclared_outcomes": sorted(self.undeclared_outcomes),
            "declared_gates": sorted(self.declared_gates),
            "gates_never_reached": sorted(self.declared_never_reached),
            "emitted_gates_not_declared": sorted(self.emitted_not_declared),
        }


def declaration_check(manifest: RunManifest, frame: pd.DataFrame) -> DeclarationCheck | None:
    """``None`` when the run declared no step, outcome or gate (nothing, or only which outcomes
    are failures and successes, which are the comparison's to read); otherwise its declaration
    against its spans.

    ``frame`` is ``Store.read(run, meta=False, trace="envelope")`` and nothing else: the
    envelope's spans are walked as plain mappings and never validated, so a run ``inspect``
    prints is never a run this check refuses, runs written by older builds included.
    ``observed_steps`` is every non-null ``step_name``; ``emitted_gates`` the ``step_name`` of
    every span whose ``gate`` is ``"emitted"`` (a marker with no name matches no declaration and
    is not an error); ``observed_outcomes`` every non-null value of the frame's ``outcome``
    column, so a row with no trace still counts and a run whose capture was off still has a
    meaningful ``undeclared_outcomes``.
    """
    declared: Declaration | None = manifest.declared
    if declared is None or not (declared.steps or declared.outcomes or declared.gates):
        return None
    observed: set[str] = set()
    emitted: set[str] = set()
    for envelope in frame["trace"]:
        if not isinstance(envelope, Mapping):
            continue
        for span in envelope.get("spans", ()):
            if not isinstance(span, Mapping):
                continue
            step = span.get("step_name")
            if step is None:
                continue
            observed.add(step)
            if span.get("gate") == "emitted":
                emitted.add(step)
    outcomes = frozenset(outcome for outcome in frame["outcome"] if outcome is not None)
    steps = frozenset(declared.steps)
    gates = frozenset(declared.gates)
    declared_outcomes = frozenset(declared.outcomes)
    never_reached = steps - observed
    return DeclarationCheck(
        declared_steps=steps,
        observed_steps=frozenset(observed),
        never_reached=never_reached,
        undeclared_steps=frozenset(observed) - steps,
        declared_outcomes=declared_outcomes,
        observed_outcomes=outcomes,
        undeclared_outcomes=outcomes - declared_outcomes,
        declared_gates=gates,
        emitted_gates=frozenset(emitted),
        emitted_not_declared=frozenset(emitted) - gates,
        declared_never_reached=gates & never_reached,
    )
