"""Compare two runs from Python: the same comparison, check and run names the command line
gives, as result objects.

Every function takes the store as a path, a string or a ``poisson_prove.store.Store``, and a run
in any form the command line takes: ``latest``, ``previous``, ``latest:TARGET``, ``#N``, a name
or an id. A refusal is ``Refusal``, whose text is the sentence the command line prints.

>>> from poisson_prove import compare
>>> result = compare.diff("prove-runs")          # previous against latest
>>> result.verdict, result.method                # doctest: +SKIP
('trade', 'mcnemar_bh')
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from poisson_prove import core
from poisson_prove.core import CheckResult, Comparison, Refusal, RunInfo
from poisson_prove.store import Store

__all__ = ["CheckResult", "Comparison", "Refusal", "RunInfo", "check", "diff", "resolve", "runs"]


def diff(
    store: str | Path | Store,
    a: str | None = None,
    b: str | None = None,
    *,
    events: Sequence[str] | None = None,
    method: str | None = None,
    q: float = 0.05,
) -> Comparison:
    """Compare run ``a`` with run ``b`` (``previous`` with ``latest`` when neither is given) over
    ``events`` (inferred when not given) by ``method`` (``fisher_bh``, ``mcnemar_bh`` or
    ``logrank_bh``; by default the paired test when the runs share their seeds, else Fisher's)
    at the false discovery rate ``q``. The result is what ``poisson-prove diff --json`` prints:
    its ``verdict`` and ``sentence``, the ``method`` and whether it was the default, every
    condition's row, the limits, the intervals, the fragility and the caveats."""
    result: Comparison = core.compare(store, a, b, events=events, method=method, q=q)
    return result


def check(
    store: str | Path | Store,
    a: str | None = None,
    b: str | None = None,
    *,
    events: Sequence[str],
    fail_on: str = "worse",
    method: str | None = None,
    q: float = 0.05,
) -> CheckResult:
    """A gate over two runs: ``passed`` unless a condition counted as a change of the kind
    ``fail_on`` names (``worse``, ``any``, ``higher`` or ``lower``) in one of ``events``. The
    result is what ``poisson-prove check --json`` prints; ``passed`` says how it went."""
    result: CheckResult = core.check(
        store, a, b, events=events, fail_on=fail_on, method=method, q=q
    )
    return result


def runs(store: str | Path | Store) -> Any:
    """Every run in the store, newest first, each a ``RunInfo`` with its id and name; the list's
    ``to_json()`` is what ``poisson-prove runs --json`` prints."""
    return core.runs(store)


def resolve(store: str | Path | Store, name: str) -> str:
    """The id of the one run ``name`` reaches, in any form the command line takes; a word that
    reaches no run, or more than one, is refused with ``Refusal``."""
    return str(core.resolve(store, name))
