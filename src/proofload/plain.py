"""The plain register: the sentences the serve page opens with, built once over the payload's own
objects and carried in it as ``summary``, so that ``serve``, the dashboard and any later surface say
the same words from one source.

**It states, it does not decide.** Counts, changes, how sure, and what the run could not have seen.
No sentence recommends, and no word here is a verdict. **It computes nothing**: every number in a
sentence is a ``text`` value, a ``config_text`` value or an integer field of the payload, carried
verbatim; the two thresholds are the only constants.

"How sure" attaches to a cell's ``q`` -- the BH-adjusted p-value its verdict was decided on --
and never to ``p``: very sure below 0.001, sure below 0.01, fairly sure below 0.05, and above that
no label, with the value printed. "Too small to tell" attaches to the event's ``mde_unchanged`` --
the detection limit over the cells the run did not call a change -- at 50 points or more, and
qualifies the absence of a finding, never a finding.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = ["CONFIDENCE_THRESHOLDS", "TOO_SMALL_TO_TELL", "build_summary"]

#: (upper bound, label): a cell's ``q`` strictly below the bound takes the label, first match wins.
CONFIDENCE_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (0.001, "very sure"),
    (0.01, "sure"),
    (0.05, "fairly sure"),
)
#: The detection limit, as a fraction, at or above which the absence of a finding is labelled.
TOO_SMALL_TO_TELL: float = 0.50
_TOO_SMALL_LABEL = "too small to tell"
_LABELS_START = str(CONFIDENCE_THRESHOLDS[-1][0])
_POINTER = (
    "Every number above is below with the statistics it came from: the omnibus, the honesty "
    "block and its bound, the per-condition table, the intervals, and what this comparison could "
    "not establish."
)
_NO_LIMIT = (
    "Every condition moved significantly, so there is no condition left to state a detection "
    "limit from."
)


def _confidence(q: float) -> str | None:
    for bound, label in CONFIDENCE_THRESHOLDS:
        if q < bound:
            return label
    return None


def _counts(panel: Mapping[str, Any], q: str) -> str:
    return (
        f"{panel['event']}: {panel['n_worse']} of {panel['n_present']} conditions got worse, "
        f"{panel['n_safer']} got safer, and {panel['n_unchanged']} show no significant change "
        f"at q = {q}."
    )


def _row(event: str, cell: Mapping[str, Any]) -> dict[str, Any]:
    text = cell["text"]
    label = _confidence(cell["q"])
    head = (
        f"{cell['coords']}: {event} was {text['rate_a']}% of trials and is now {text['rate_b']}%, "
        f"a rise of {text['delta']} percentage points. How sure: "
    )
    if label is None:
        line = f"{head}no label (q = {text['q']}; the labels start at {_LABELS_START})."
    else:
        line = f"{head}{label} (q = {text['q']})."
    return {
        "where": cell["coords"],
        "config_hash": cell["config_hash"],
        "before": text["rate_a"],
        "after": text["rate_b"],
        "change": text["delta"],
        "confidence": label,
        "q": text["q"],
        "line": line,
    }


def _worse(panel: Mapping[str, Any], top_n: int) -> list[dict[str, Any]]:
    cells = sorted(
        (c for c in panel["cells"] if c["verdict"] == "worse"),
        key=lambda c: (-c["delta"], c["q"], c["mde"], c["config_hash"]),
    )
    return [_row(str(panel["event"]), c) for c in cells[:top_n]]


def _limit(panel: Mapping[str, Any]) -> dict[str, Any]:
    block = panel["mde_unchanged"]
    if block["value"] is None:
        return {"label": None, "mde": None, "where": None, "line": _NO_LIMIT}
    cell = next(c for c in panel["cells"] if c["coords"] == block["where"])
    where, n_a, n_b, mde = block["where"], cell["n_a"], cell["n_b"], block["text"]
    if block["value"] >= TOO_SMALL_TO_TELL:
        label: str | None = _TOO_SMALL_LABEL
        line = (
            f"Too small to tell: the least sensitive condition among those this run did not call "
            f"a change ({where}, n = {n_a}/{n_b}) could only have seen a rise of {mde}pp or more. "
            "Below that, this run cannot tell a change from none."
        )
    else:
        label = None
        line = (
            f"The least sensitive condition among those this run did not call a change ({where}, "
            f"n = {n_a}/{n_b}) could only have seen a rise of {mde}pp or more."
        )
    return {"label": label, "mde": mde, "where": where, "line": line}


def _partial(pair: Mapping[str, Any]) -> dict[str, Any] | None:
    arms = [pair["a"], pair["b"]]
    partial = [arm for arm in arms if arm["status"] != "complete"]
    if not partial:
        return None
    lines = [
        f"Run {arm['run_id']} ({arm['role']}) recorded status \"partial\": it stopped before "
        "everything it planned had run. What is below compares the conditions both runs have."
        for arm in partial
    ]
    return {"runs": [str(arm["run_id"]) for arm in partial], "line": " ".join(lines)}


_PAIRING = (
    "Compared as two separate samples. The runs share their seeds; this test does not use that."
)


def _pairing(diff: Mapping[str, Any]) -> dict[str, Any]:
    """The one plain line beside the word "unpaired": printed only when the runs share their seeds
    and the requested test treats them as separate samples, which is what ``unpaired_analysis``
    records."""
    return {"line": _PAIRING if diff["unpaired_analysis"] else None}


def _complement(
    complement: tuple[str, ...] | None, trade_line: str | None
) -> dict[str, Any] | None:
    """M6's answer as data, and M6's own sentence beside it: the complement line is ``trade_line``
    verbatim, never composed here, so the page's Result block, report.md, the receipt and this
    object say one thing from one source. ``None`` line when nothing traded."""
    if complement is None:
        return None
    return {"events": list(complement), "line": trade_line}


def build_summary(
    *,
    panels: Sequence[Mapping[str, Any]],
    view: Mapping[str, Any],
    pair: Mapping[str, Any],
    diff: Mapping[str, Any],
    complement: tuple[str, ...] | None,
    trade_line: str | None,
) -> dict[str, Any]:
    """The ``summary`` object: the partial banner, the complement, one entry per event in
    ``panels`` order, and the pointer down the page. Takes the payload's own objects and nothing
    else, so a stored payload can rebuild it."""
    q = str(diff["q"])
    top_n = int(view["top_n"])
    return {
        "partial": _partial(pair),
        "complement": _complement(complement, trade_line),
        "pairing": _pairing(diff),
        "events": [
            {
                "event": str(panel["event"]),
                "line": _counts(panel, q),
                "worse": _worse(panel, top_n),
                "limit": _limit(panel),
            }
            for panel in panels
        ],
        "pointer": _POINTER,
    }
