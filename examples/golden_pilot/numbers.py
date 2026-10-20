"""What the pilot must come back with: the three numbers and the four checks.

``numbers(store, run_id, paired_with=...)`` reads one run out of a Prove store and
returns one JSON-native dict (spec sections 0 and 3):

* **the three numbers** -- span count, ``dropped``, the ``other`` share -- with the kind
  histogram and the ``tool`` share beside them, because the finding this phase is for groups
  by what the agent was doing when it failed. The denominator is the whole stored trace, the
  rollout's own ``record()`` spans included -- that is what makes a ``tool`` share exist at
  all, and section 0 asks for the two together. All of it is over the **ok rows'** stored
  traces: an errored row's trace is a snapshot of an episode Prove cut short, and mixing
  it into the integration's span census would report a number nobody could reproduce.
* **contract survival** -- ok rows that decode as an ``Episode`` with an outcome in
  ``OUTCOMES``, ``0 <= t <= horizon``, the run's declared ``t_unit``, and a trace that
  decodes uncut with both episode stamps on every captured llm span.
* **the errored-row rate**, split by error text and by whether the row kept a trace. An
  errored row is Prove failing to observe, never the agent failing the task: S16's
  ``timeout`` and S17's traceback are counted here and never as outcomes.
* **zero-n holes** -- (cell, event) pairs the run never produced, the honesty block's input.
* **pairing agreement and Cohen's kappa** at the same ``(task_id, temperature, seed)``, per
  temperature: the noise floor in one number, beside the null diff's headline.

Read it from the shell after each arm::

    python -m golden_pilot.numbers <store> <run-id> [--paired-with <run-id>]

**The ``-m`` form is the only one**, and it is what the README uses. This module reads the
outcome vocabulary from its package with ``from . import ...``, which needs a parent package,
so ``python examples/golden_pilot/numbers.py`` -- which used to work -- now raises
``ImportError`` at import. That is the price of one definition of the vocabulary instead of
two (spec S22 section 2), and it is paid here because this module is the one that cannot
import ``agent``.

**This file is called numbers.py, which is a standard-library module name.** Under the
dropped script form, Python put this directory first on ``sys.path`` and ``import numbers``
then found *this* file -- and numpy imports ``numbers``, so ``poisson_prove.store`` would fail
with a baffling traceback from inside numpy. :func:`main` still drops that path entry before
it imports ``Store``, now as belt and braces, and the module-level imports here stay
deliberately numpy-free so nothing is loaded before it can. The name is fixed by spec
section 2; the shadowing is not, so do not move the ``Store`` import back up to the top.

``timed_out`` (the agent spent its budget) and ``timeout`` (Prove cut a hung episode) are
different facts and are reported apart -- the first as an outcome, the second in the errored
split. Nothing here re-runs anything; it reads the store the arms already wrote.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from poisson_prove import Episode
from poisson_prove.trace import Trace

from . import FAILURE_EVENTS, OUTCOMES, T_UNIT

if TYPE_CHECKING:  # the runtime import lives in main(): see the module docstring
    from poisson_prove.store import Store

#: Prove's span kinds, spelled here rather than imported: P12 holds the pilot to five
#: names plus ``Store`` from ``poisson_prove``, and ``KINDS`` is not one of them. A kind the core
#: grows and this tuple does not still lands in the histogram -- the counter adds the key --
#: so nothing is lost; what goes stale is the guarantee that every kind appears, zero
#: included, which is the only reason to write the seven out. Re-read ``poisson_prove.trace``
#: whenever core's vocabulary changes.
KINDS = ("llm", "tool", "retrieval", "db", "http", "agent", "other")

#: The two attributes the episode stamper writes on every captured span.
RUN_ID_KEY = "poisson_prove.run_id"
EPISODE_KEY = "poisson_prove.episode"


def _isnull(value: Any) -> bool:
    """``Store.read`` hands back a pandas frame, which spells a null column value ``NaN``."""
    return value is None or (isinstance(value, float) and math.isnan(value))


def _errored(row: dict[str, Any]) -> bool:
    return not _isnull(row.get("error"))


def _trace(meta: Any) -> Trace | None:
    """The row's stored trace, or None when there is none or it does not decode."""
    if not isinstance(meta, dict) or meta.get("trace") is None:
        return None
    try:
        return Trace.from_dict(meta["trace"])
    except Exception:  # noqa: BLE001 - an undecodable trace is a contract failure, not a crash
        return None


def _survives(row: dict[str, Any], t_unit: str) -> bool:
    """One ok row against the contract of spec section 3."""
    try:
        episode = Episode.from_dict(
            {
                "outcome": row["outcome"],
                "t": None if _isnull(row["t"]) else row["t"],
                "horizon": None if _isnull(row["horizon"]) else row["horizon"],
                "confidence": None if _isnull(row["confidence"]) else row["confidence"],
                "meta": row["meta"],
            }
        )
    except Exception:  # noqa: BLE001 - Episode validates t <= horizon, so this is the check
        return False
    if episode.outcome not in OUTCOMES or t_unit != T_UNIT:
        return False
    if not 0 <= episode.t <= episode.horizon:
        return False
    trace = _trace(row["meta"])
    if trace is None or trace.truncated is not None:
        return False
    # The stamps ride the captured llm spans; a record() span never meets the stamper (S15,
    # and spec section 3 as amended), so asserting them on every span would fail every row.
    return all(
        RUN_ID_KEY in span.attrs and EPISODE_KEY in span.attrs
        for span in trace.spans
        if span.kind == "llm"
    )


def _last_line(text: str) -> str:
    lines = [line.strip() for line in str(text).rstrip().splitlines() if line.strip()]
    return lines[-1] if lines else "<empty error text>"


def _agreement(pairs: list[tuple[str, str]]) -> float | None:
    """The share of triples whose two outcomes match, or None when nothing paired."""
    if not pairs:
        return None
    return sum(a == b for a, b in pairs) / len(pairs)


def _kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa over the outcome vocabulary. None when nothing paired.

    Chance agreement is the product of the two runs' marginals. When both runs used one label
    throughout, chance agreement is 1 and kappa is undefined (0/0); the convention here is
    1.0 for perfect agreement and 0.0 otherwise, which is what a degenerate stratum deserves.
    """
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    chance = sum(left[label] * right[label] for label in set(left) | set(right)) / (n * n)
    if math.isclose(chance, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - chance) / (1.0 - chance)


def _triple(row: dict[str, Any]) -> tuple[str, float, int]:
    config = row["config"]
    return (str(config["task_id"]), float(config["temperature"]), int(row["seed"]))


def _pairing(
    ok: list[dict[str, Any]], other: list[dict[str, Any]], paired_with: str
) -> dict[str, Any]:
    """Agreement and kappa over the triples both runs produced an ok row for."""
    left = {_triple(row): str(row["outcome"]) for row in ok}
    right = {_triple(row): str(row["outcome"]) for row in other}
    shared = sorted(set(left) & set(right))
    strata: dict[str, list[tuple[str, str]]] = {}
    for key in shared:
        strata.setdefault(str(key[1]), []).append((left[key], right[key]))
    every = [pair for pairs in strata.values() for pair in pairs]
    return {
        "paired_with": paired_with,
        "triples": len(shared),
        "agreement": {
            "all": _agreement(every),
            "by_temperature": {t: _agreement(pairs) for t, pairs in sorted(strata.items())},
        },
        "kappa": {
            "all": _kappa(every),
            "by_temperature": {t: _kappa(pairs) for t, pairs in sorted(strata.items())},
        },
    }


def numbers(store: Store, run_id: str, *, paired_with: str | None = None) -> dict[str, Any]:
    """The three numbers and the four checks for one run. JSON-native throughout."""
    t_unit = store.manifest(run_id).t_unit
    rows: list[dict[str, Any]] = store.read(run_id).to_dict("records")
    ok = [row for row in rows if not _errored(row)]
    errored = [row for row in rows if _errored(row)]

    spans = 0
    dropped = 0
    kinds = dict.fromkeys(KINDS, 0)
    for row in ok:
        trace = _trace(row["meta"])
        if trace is None:
            continue
        spans += len(trace.spans)
        dropped += trace.dropped
        for span in trace.spans:
            kinds[span.kind] = kinds.get(span.kind, 0) + 1

    survived = sum(_survives(row, t_unit) for row in ok)
    # Every episode makes at least one model call, so an ok row with no llm span means the
    # capture did not reach it. The stamp check above is vacuously true for such a row --
    # ``all()`` over nothing -- so contract survival alone would report a run with no captured
    # spans as perfectly healthy. This is the number that notices (spec section 8, T33).
    traces = [_trace(row["meta"]) for row in ok]
    without_llm = sum(
        1 for trace in traces if trace is not None and not any(s.kind == "llm" for s in trace.spans)
    )
    by_error = Counter(_last_line(row["error"]) for row in errored)
    with_trace = sum(_trace(row["meta"]) is not None for row in errored)

    cells = sorted({str(row["config_hash"]) for row in rows})
    seen = {(str(row["config_hash"]), str(row["outcome"])) for row in ok}
    holes = [
        [cell, event]
        for cell in cells
        for event in FAILURE_EVENTS
        if (cell, event) not in seen
    ]

    out: dict[str, Any] = {
        "run_id": run_id,
        "rows": len(rows),
        "ok_rows": len(ok),
        "errored_rows": len(errored),
        "spans": spans,
        "dropped": dropped,
        "kinds": kinds,
        "other_share": kinds["other"] / spans if spans else 0.0,
        "tool_share": kinds["tool"] / spans if spans else 0.0,
        "contract": {
            "rows": len(ok),
            "survived": survived,
            "failed": len(ok) - survived,
            "without_llm_spans": without_llm,
        },
        "errored": {
            "rows": len(errored),
            "rate": len(errored) / len(rows) if rows else 0.0,
            "by_error": dict(by_error),
            "with_trace": with_trace,
            "without_trace": len(errored) - with_trace,
        },
        "zero_n": {
            "cells": len(cells),
            "events": list(FAILURE_EVENTS),
            "count": len(holes),
            "holes": holes,
        },
        "pairing": None,
    }
    if paired_with is not None:
        other = [row for row in store.read(paired_with).to_dict("records") if not _errored(row)]
        out["pairing"] = _pairing(ok, other, paired_with)
    return out


def main(argv: list[str] | None = None) -> int:
    # Run as a script, sys.path[0] is this directory and this file shadows the standard
    # library's ``numbers``, which numpy imports. Drop it before anything reaches numpy.
    here = str(Path(__file__).resolve().parent)
    if sys.path and Path(sys.path[0]).resolve() == Path(here):
        sys.path.pop(0)
    from poisson_prove.store import Store

    parser = argparse.ArgumentParser(description="the three numbers and the four checks")
    parser.add_argument("store", help="the store root the sweep wrote into")
    parser.add_argument("run_id", help="the run to read")
    parser.add_argument("--paired-with", default=None, metavar="RUN", help="the paired run")
    args = parser.parse_args(argv)
    report = numbers(Store(args.store), args.run_id, paired_with=args.paired_with)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
