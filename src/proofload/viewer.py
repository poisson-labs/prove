"""M13: the viewer. A versioned structure for one run pair, a renderer over it, and a server.

Three halves that never reach back into each other. ``build_structure`` assembles
``proofload.viewpair/4`` -- identity and run tallies, diff parameters, panels, cells, holes,
the flat family's intervals, M14's layered report and what could not be verified -- from M6's
result, M7's report, M14's tree, the two ``RunManifest``s and the two ``RunTally``s.
``render_html`` turns that structure, and nothing else, into one page.
``serve_page`` holds the page on an ephemeral loopback port until Ctrl-C.

**It renders, it does not compute.** Every rate, delta, p, q, MDE, verdict, count and colour
bound comes from M6, M7 and M14 already formatted by M7's own ``_fmt``; the tree rides
verbatim with a ``text`` member beside every float the page prints, so the renderer reads
``text`` and never a raw number; reading a stored field off a
manifest and printing it is rendering. ``build_structure`` performs exactly one arithmetic
operation, the ``created_at`` gap, computed once here so no consumer recomputes it;
``render_html`` performs none.

**Nothing outbound.** ``http.server`` is a listener on loopback, bound on request, serving one
snapshot taken before the socket exists. No client module is imported, nothing is written, and
the page's own CSP forbids the browser from fetching anything.
"""

from __future__ import annotations

import html as _html
import json
import math
from collections import Counter
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

from proofload.report import (
    _EPISTEMIC_FENCE,
    _coord_text,
    _fmt,
    _html_style,
    _html_table,
    _provenance_lines,
    _worst_header,
    _worst_table_rows,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from proofload.diff import MultiDiffResult
    from proofload.report import Cell, MultiReport, Report, ReportSpec
    from proofload.store import RunManifest, RunTally
    from proofload.tree import TreeResult

__all__ = ["ViewerError", "build_structure", "render_html", "serve_page"]

# The version bumps whenever a key set changes, because this structure's consumers pin key
# sets -- its own oracle does. ``/2`` adds the per-arm tally, four coverage integers and
# ``config_text`` per cell, and the top-level ``holes`` list; ``/3`` adds ``tree``, M14's
# layered report carried verbatim; ``/4`` adds ``agreement`` inside ``tree`` -- the digest of the
# rebuild the tree's own construction verified, so a consumer holding this payload can check that
# the tree is the tree of the pair beside it (A28) -- and then, behind A28 and under the same
# version, P-1's thirteenth top-level key ``intervals``, the two provenance keys that replace
# ``paired`` in the ``diff`` object, and ``p_floor`` inside ``tree.root``.
#
# **Two packets on one ``/4``, and why that is honest rather than a broken rule.** The rule above
# is the one P-1 breaks: A28 had landed and been pushed before P-1 was written, so "lands with
# A28" was not available. Nothing stores a structure (ADR-036; ``--json`` prints to stdout and
# the page is a snapshot), the package is private at ``0.0.1`` with no tag, and no published
# consumer read ``/4`` before P-1 -- so no stored shape can be misread. What keeps the one
# version honest is ``render_html``'s refusal below: a ``/4`` assembled before ``intervals``
# joined it is refused by name rather than drawn with a section missing.
SCHEMA = "proofload.viewpair/4"

#: Which BH family ``intervals.level`` and ``intervals.alpha_star`` belong to. The layered
#: report introduces a nested family with a different level, so a bare ``alpha*`` on the page
#: would be the one number a reader could attribute to either.
#:
#: **Spelled here rather than imported**, deliberately: the set of names this module may take
#: from ``report`` is frozen by two oracles (M13 V35, S21 E22) as assembly helpers plus render
#: helpers, and a shared constant is neither. It must agree with the prose in
#: ``report._interval_lines`` -- *over the flat BH family* -- which is the one formatter every
#: surface reads; P-1 Y10 pins this value and Y12 pins that prose, so the pair cannot drift
#: unnoticed. The escape hatch, if a third spelling ever appears: widen the partition in those
#: two oracles under their own re-freeze rather than adding a second constant here.
_INTERVAL_FAMILY = "flat"

_HOST = "127.0.0.1"
_CONTENT_TYPE = "text/html; charset=utf-8"
_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
    "img-src data:; form-action 'none'; base-uri 'none'"
)

_INDEX_ID = "proofload-cells"
_HOLES_ID = "proofload-holes"
_SIGN_CONVENTION = "delta = rate_b - rate_a"
_EVENT_LINE_TAIL = "given by --event, not inferred"
_HOLE_MESSAGE = "No comparable data for this cell."
_HOLES_HEADING = "Holes"
_HOLES_OPTGROUP = "holes"
_HOLES_HEADER = ["coords", "cause", "config_hash", "rows (a/b)", "no outcome (a/b)"]

# The seven float fields each cell carries raw, and the kind M7 formats each with.
_FLOAT_KINDS: dict[str, str] = {
    "rate_a": "pp1",
    "rate_b": "pp1",
    "delta": "pp1",
    "stat": "sig3",
    "p": "sig3",
    "q": "sig3",
    "mde": "pp0",
}
# M14's tree, one row per (object, field) the page prints, keyed by the object's dotted path in
# ``TreeResult.to_json()`` with list indices dropped. The table is S28 section 3.6's, restated
# here rather than imported: ``report.py`` calls ``_fmt`` with a kind at each site and has no
# table to import, and importing one would make this module's build depend on that one.
# ``config`` is this module's own row -- a leaf's config value is spelled the way the
# drill-down already spells it, through ``_config_text``, so every token on the page is a
# string the structure carries (V16's rule, one object over).
_TREE_KINDS: dict[str, dict[str, str]] = {
    "root": {
        "p_floor": "sig3",
        "p_omnibus": "sig3",
        "p_location": "sig3",
        "p_dispersion": "sig3",
        "q": "sig3",
        "location": "pp1",
        "dispersion": "pp1",
    },
    "grouping": {
        "alpha_floor": "sig3",
        "max_group_mde": "pp0",
        "size_median": "num",
        "group_mde": "pp1",
    },
    "fault_lines": {"q": "sig3"},
    "fault_lines.groups": {
        "mde": "pp1",
        "location": "pp1",
        "dispersion": "pp1",
        "p_location": "sig3",
        "p_dispersion": "sig3",
        "p_group": "sig3",
        "q_group": "sig3",
    },
    "leaves": {"q": "sig3"},
    "leaves.families": {"mde_median": "pp0", "mde_max": "pp0"},
    "leaves.families.cells": {
        "delta": "pp1",
        "q_within": "sig3",
        "mde": "pp0",
        "config": "coord",
    },
    "bound": {"bound": "sig3", "q": "sig3", "delta_star": "sig3"},
}

_N_FIELDS = ("n_a", "n_b")
_EVENT_FIELDS = ("events_a", "events_b")

# M6's coverage integers, joined onto a cell (and onto a hole) by ``config_hash``. Read from
# the coverage row, never recomputed: ``n_a + no_outcome_a`` would be arithmetic here and the
# wrong number besides, because the coverage row already carries ``rows_a``.
_COVERAGE_FIELDS = ("rows_a", "rows_b", "no_outcome_a", "no_outcome_b")
_NO_COVERAGE: dict[str, int] = dict.fromkeys(_COVERAGE_FIELDS, 0)

# The five tally rows the identity table prints after ``rows_stored``, read from the arm's own
# ``tally`` object rather than from five more arm keys.
_TALLY_ROWS = ("with_outcome", "no_outcome", "timed_out", "infra", "other")

# What this page cannot confirm. Constant across every pair by construction: these are limits
# of the instrument, not facts about two runs. A fact about a particular pair -- a partial
# status, two different targets -- is shown as its own value in the identity block instead.
_UNVERIFIED: tuple[tuple[str, str, str | None], ...] = (
    (
        "outcome_labels",
        "with_outcome and no_outcome count rows by whether the executor stored an outcome. A "
        "row whose outcome is a label such as crashed is a row with an outcome: nothing on "
        "this page reads what an outcome means, and a run every one of whose episodes ended "
        "in the same label shows no_outcome 0.",
        "B.1",
    ),
    (
        "status_basis",
        "status is what the writing process recorded when it finished. This page does not "
        "re-derive it from the sweep's expected cell count, and for a run imported from "
        "elsewhere it could not.",
        None,
    ),
    (
        "created_at_meaning",
        "created_at is when the run's manifest was opened in this store. For a run imported "
        "from elsewhere that is the import time, not when the experiment ran.",
        None,
    ),
    (
        # Reworded, not added, by P-1: after C18 the stored seeds *are* compared on every matched
        # row, so the old sentence -- "matching salts do not prove the two runs consumed their
        # seeds identically" -- no longer describes the check. What stays unverifiable is what
        # the target did with a seed (ADR-076), which is a finding about the target and not a
        # roadmap item, so ``blocked_by`` stays ``None``.
        "seed_identity_basis",
        "seed_identity_match is true when both manifests carry the same run_salt and every row "
        "this comparison matched stores the same seed in both arms at the same (config_hash, "
        "replicate_index). It compares the seeds that were stored, not what the target did with "
        "them.",
        None,
    ),
)

# The identity rows, in the order the two-column block prints them. ``environment`` is not
# here: it is the one open-ended user object on the page and goes inside <details>.
_ARM_SCALARS = (
    "role",
    "run_id",
    "target_id",
    "backend",
    "status",
    "created_at",
    "run_salt",
    "t_unit",
    "proofload_version",
    "schema_version",
    "retain_traces_for",
    "axis_types",
    "rows_stored",
)


class ViewerError(Exception):
    """The structure cannot be assembled or the address cannot be bound."""


# ---------- assembly ----------


def _axes(spec: ReportSpec) -> list[str]:
    return [spec.x_axis] + ([spec.y_axis] if spec.y_axis is not None else [])


def _coords(cell: Cell) -> tuple[str, ...]:
    """The cell's axis values as M7 renders them in a table row, for joining worst rows back."""
    return tuple(_fmt(value, "coord") for value in cell.coords)


def _finite(value: Any) -> float | None:
    """A raw float, or ``None`` when it is not finite.

    Fisher's odds ratio is ``inf`` on a zero cell and ``nan`` on a degenerate table, and both
    are Python-only tokens ``json.dumps`` would emit and no strict reader would accept. The
    number moves to ``text``, which can carry it; the raw slot carries null.
    """
    number = float(value)
    return number if math.isfinite(number) else None


def _gap_seconds(created_a: str, created_b: str) -> float | None:
    """The signed gap between two stored ``created_at`` values, or ``None`` when either is
    unreadable. The viewer is read-only: M4 validates a manifest, this renders what is stored.

    The one arithmetic operation in this half of the module. It lives here rather than in the
    renderer so that the renderer, the ``--json`` consumer and the Phase 7 MCP server read one
    number instead of implementing the subtraction three times.
    """
    try:
        first = datetime.fromisoformat(created_a)
        second = datetime.fromisoformat(created_b)
    except (TypeError, ValueError):
        return None
    return (second - first).total_seconds()


def _arm(manifest: RunManifest, role: str, rows_stored: int, tally: RunTally) -> dict[str, Any]:
    """One arm's identity, plus the run's own tally.

    ``rows_stored`` and ``tally["rows"]`` are two reads of the same parts -- one through the
    Parquet footers, one through two columns -- and they agree. Nothing here assumes it: the
    oracle asserts it, which is what would catch a tally that came from somewhere else.
    """
    stored = manifest.to_dict()
    arm: dict[str, Any] = {"role": role}
    for name in (
        "run_id",
        "target_id",
        "backend",
        "status",
        "created_at",
        "run_salt",
        "t_unit",
        "proofload_version",
        "schema_version",
        "retain_traces_for",
        "axis_types",
        "environment",
    ):
        arm[name] = stored[name]
    arm["rows_stored"] = int(rows_stored)
    arm["tally"] = tally.to_dict()
    return arm


def _config_text(config: Mapping[str, Any]) -> dict[str, str | None]:
    """M7's coordinate rendering of every scalar config value; ``None`` for anything else.

    The server-rendered drill-down has to print the config and V16 forbids a formatter here,
    so this is one ``_fmt`` pass -- the same kind ``_coord_text`` uses -- over values the
    structure already carries. A list, a mapping or a null has no coordinate rendering and
    gets ``None``; a bool renders as ``True``, which is what an axis value of that kind
    already renders as.
    """
    return {
        str(name): _fmt(value, "coord") if isinstance(value, (bool, int, float, str)) else None
        for name, value in config.items()
    }


def _cell(
    spec: ReportSpec, cell: Cell, row: dict[str, Any], coverage: Mapping[str, Any]
) -> dict[str, Any]:
    """One present cell: M6's own fields raw, plus M7's rendering of each float.

    Both, never one alone. The raw float is canonical -- a consumer that has to parse ``"37.5"``
    back into a number has lost the units and three significant figures. ``text`` is M7's
    rendering of that same float, so no second formatter exists to drift from it.

    ``rows_*`` and ``no_outcome_*`` are the coverage row's own integers, joined on
    ``config_hash`` the way ``events_a`` and ``config`` already are, so "ran 32, no outcome
    20, compared 12" is three integers on one screen. They have no ``text`` entry, as the
    other integers do not.
    """
    out: dict[str, Any] = {
        "coords": _coord_text(spec, cell),
        "config_hash": str(cell.config_hash),
    }
    for name in _N_FIELDS:
        out[name] = int(row[name])
    for name in _COVERAGE_FIELDS:
        out[name] = int(coverage[name])
    for name in _EVENT_FIELDS:
        out[name] = int(row[name])
    for name in _FLOAT_KINDS:
        out[name] = _finite(row[name])
    out["verdict"] = str(row["verdict"])
    out["config"] = row["config"]
    out["config_text"] = _config_text(row["config"])
    out["text"] = {name: _fmt(row[name], kind) for name, kind in _FLOAT_KINDS.items()}
    return out


def _panel(
    spec: ReportSpec,
    event: str,
    panel: Report,
    rows: dict[str, dict[str, Any]],
    coverage: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    present = [c for c in panel.cells if c.present]
    cells = [
        _cell(spec, c, rows[str(c.config_hash)], coverage.get(str(c.config_hash), _NO_COVERAGE))
        for c in present
    ]
    header = _worst_header(panel)
    worst_rows = _worst_table_rows(panel)
    axes = _axes(spec)
    by_coords = {_coords(c): str(c.config_hash) for c in present}
    return {
        "event": event,
        "caption": panel.headline,
        "honesty": panel.honesty,
        "n_safer": int(panel.n_safer),
        "n_worse": int(panel.n_worse),
        "n_unchanged": int(panel.n_unchanged),
        "n_absent": int(panel.n_absent),
        "n_present": int(panel.n_present),
        "x_values": [_fmt(v, "coord") for v in panel.x_values],
        "y_values": [_fmt(v, "coord") for v in panel.y_values],
        "cells": cells,
        "worst_header": header,
        "worst_rows": worst_rows,
        "worst_hashes": [by_coords[tuple(row[: len(axes)])] for row in worst_rows],
    }


def _hole(
    coords: str | None,
    config_hash: str | None,
    cause: str,
    coverage: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """One hole. A grid coordinate that no coverage row explains -- ``unsampled``, or a
    ``multiple`` that more than one row maps to -- carries no hash, no config and four zeros;
    every other hole carries its coverage row's. A hole never has a ``text`` entry: there is
    no float to format."""
    row = None if config_hash is None else coverage[config_hash]
    config = None if row is None else row["config"]
    out: dict[str, Any] = {"coords": coords, "config_hash": config_hash, "cause": cause}
    for name in _COVERAGE_FIELDS:
        out[name] = 0 if row is None else int(row[name])
    out["config"] = config
    out["config_text"] = None if config is None else _config_text(config)
    return out


def _holes(
    spec: ReportSpec, report: MultiReport, coverage: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Every hole the pair has, once: M7's absent grid cells in grid order, then the
    non-comparable coverage rows no grid cell carries, by hash.

    The grid is identical across panels -- every event's cells carry the same ``common`` -- so
    the list is built from the first panel and lives at the top level rather than once per
    event. The off-grid half is real and is not drawn: M7's axis values come from the
    *present* cells, so a non-comparable cell at an axis value no comparable cell has appears
    on no heatmap, and a ``--fix`` can exclude one that otherwise would. Carrying them here is
    what makes the count of holes on the page the count of holes in the data.
    """
    on_grid = {
        str(cell.config_hash)
        for panel in report.panels.values()
        for cell in panel.cells
        if cell.config_hash is not None
    }
    entries: list[dict[str, Any]] = []
    for cell in report.panels[report.events[0]].cells:
        if cell.present or cell.hole_cause is None:
            continue
        found = None if cell.config_hash is None else str(cell.config_hash)
        entries.append(_hole(_coord_text(spec, cell), found, str(cell.hole_cause), coverage))
    off_grid = sorted(
        name
        for name, row in coverage.items()
        if not row["comparable"] and name not in on_grid
    )
    entries.extend(_hole(None, name, str(coverage[name]["cause"]), coverage) for name in off_grid)
    return entries


def _tree_text(raw: Any, kind: str) -> Any:
    """M7's rendering of one tree field, shaped like the field.

    A mapping keyed by event gets a mapping over the same keys, a list gets a list of the same
    length, a scalar gets one string, and a config gets ``_config_text``'s coordinate rendering
    -- the spelling the drill-down already uses for a config value. The raw float is canonical
    and this is its text; no second formatter exists to drift from ``_fmt``.
    """
    if kind == "coord":
        return _config_text(raw)
    if isinstance(raw, dict):
        return {key: _fmt(value, kind) for key, value in raw.items()}
    if isinstance(raw, list):
        return [_fmt(value, kind) for value in raw]
    return _fmt(raw, kind)


def _tree_payload(raw: Any, path: str = "") -> Any:
    """``TreeResult.to_json()`` decorated, never rewritten.

    Every key, in order, with two additions and no other change: a non-finite float becomes
    ``null`` with its spelling kept in ``text`` (``_finite``'s rule, as the cells have it), and
    every object the kind table names gains a ``text`` member whose keys are exactly that
    object's printed floats. A field that is ``None`` prints nothing and gets no entry;
    ``root.units`` is named by no row and gets none, because the page never prints a unit.
    Removing every ``text`` at every depth gives ``to_json()`` back (invariant W2), which is
    what makes the tree on the page and the tree in the JSON one object.
    """
    if isinstance(raw, dict):
        out: dict[str, Any] = {}
        for key, value in raw.items():
            child = f"{path}.{key}" if path else str(key)
            out[key] = _tree_payload(value, child)
        kinds = _TREE_KINDS.get(path)
        if kinds is not None:
            out["text"] = {
                field: _tree_text(raw[field], kind)
                for field, kind in kinds.items()
                if raw.get(field) is not None
            }
        return out
    if isinstance(raw, list):
        return [_tree_payload(value, path) for value in raw]
    if isinstance(raw, float):
        return _finite(raw)
    return raw


def _check_tree(multi: MultiDiffResult, tree: TreeResult) -> None:
    """A tree is carried beside the diff it was grown from or not at all.

    I18's shape at the assembly boundary, and M7's ``_check_tree`` one module over: the tree's
    events must be the family's, and its units -- one per cell per event -- must be the family's
    tests. Checked before anything is assembled, so a mismatched pair costs no page.

    S29 amendment 5, built in A27: the third clause compares the ``(event, config_hash)``
    multiset and not only its size. Arity alone accepts a tree grown on a different pair that
    happens to have the same events and the same number of cells -- measured on this oracle's
    own vocabulary and hostile pairs, whose ``task`` values and so whose hashes are disjoint --
    and a page assembled from one would carry another pair's cells under this pair's identity.
    A multiset rather than a set, because a cell repeated in one side and not the other is the
    same defect. The arity clause runs first, so by the time the multiset is compared the two
    totals are equal and a difference has a cell on each side to name; ``none`` is spelled
    anyway rather than indexed, because a refusal that raises ``IndexError`` from inside its
    own message is worse than the mismatch it was reporting. One cell each way and not the
    whole list: a Go1-sized mismatch is 656 hashes, and one is enough to name the other pair.

    A28 appends two more and rewords none of the three above. The **agreement digest** closes
    C16, which the multiset clause cannot: two pairs over the same events, the same cell count
    and the same config grid -- so the same ``(event, config_hash)`` multiset -- differing only
    in what happened, are accepted by all three clauses above and refused by this one. Its
    message names neither a cell nor a count because at that point there is no cell and no
    count that differs, which is also why it runs *last*: placed ahead of the multiset clause it
    still refuses, and the refusal simply stops naming the cell that would have been named.
    The **knob clause** follows it because the digest covers the cell set, the event set and the
    four episode counts and nothing else (spec A28 section 3.3), so a tree grown under another
    method or at another ``q`` passes it. ``agreement_digest`` is imported inside the function:
    W20 pins that this module's body imports ``proofload.tree`` nowhere and that this closure
    applies exactly one arithmetic node, and a function-level import and a compare move neither.
    """
    from proofload.tree import agreement_digest

    if tuple(tree.root.events) != tuple(multi.events):
        raise ViewerError(
            f"the tree is over events {list(tree.root.events)}; this pair's diff is over "
            f"{list(multi.events)}"
        )
    if len(tree.root.units) != multi.n_tests:
        raise ViewerError(
            f"the tree carries {len(tree.root.units)} cell-event units; this pair's diff is "
            f"over {multi.n_tests} tests"
        )
    carried = Counter(
        (str(event), str(config_hash))
        for event, config_hash in zip(
            tree.root.units["event"], tree.root.units["config_hash"], strict=True
        )
    )
    tested = Counter(
        (str(event), str(config_hash))
        for event in multi.events
        for config_hash in multi.by_event[event].cells["config_hash"]
    )
    if carried != tested:
        only_tree = sorted(key for key in carried if carried[key] != tested[key])
        only_diff = sorted(key for key in tested if tested[key] != carried[key])
        in_tree = ", ".join(f"{event}/{h}" for event, h in only_tree[:1]) or "none"
        in_diff = ", ".join(f"{event}/{h}" for event, h in only_diff[:1]) or "none"
        raise ViewerError(
            f"the tree's cells are not this pair's: {in_tree} is in the tree and not in "
            f"this diff, {in_diff} is in this diff and not in the tree; the tree carries "
            f"{sum(carried.values())} cell-event units and this pair's diff tests "
            f"{sum(tested.values())}"
        )
    if tree.agreement != agreement_digest(multi):
        raise ViewerError(
            "the tree's agreement digest is not this pair's; the tree was grown from a "
            "different pair with the same family shape, so nothing above can be named"
        )
    if tree.root.method != multi.method or tree.root.q != multi.q:
        raise ViewerError(
            f"the tree was grown under {tree.root.method} at q = {tree.root.q:g}; this pair's "
            f"diff is {multi.method} at q = {multi.q:g}"
        )


def _intervals(report: MultiReport, multi: MultiDiffResult) -> dict[str, Any]:
    """The flat family's intervals as data: M6's fields, M7's one formatter's lines, and one row
    per M6 interval row in M6's order.

    Always an object, never ``null``: ``R == 0`` is read from ``level: null``, ``rows: []`` and
    the one line, not from an absent key, because a consumer cannot tell an absent key from an
    older payload. Each row carries ``event`` **and** ``config_hash``; a panel cell carries
    ``config_hash``, and the join back is a string equality, which is the only arithmetic-free
    join there is (ADR-032).

    A ``None`` endpoint gets no ``text`` entry rather than a spelling of nothing, the rule the
    tree's decoration already uses: a field that prints nothing gets no entry.
    """
    rows: list[dict[str, Any]] = []
    records = [] if multi.intervals is None else multi.intervals.to_dict(orient="records")
    for record in records:
        text: dict[str, str] = {}
        row: dict[str, Any] = {
            "event": str(record["event"]),
            "config_hash": str(record["config_hash"]),
        }
        for name in ("ci_lo", "ci_hi"):
            value = record[name]
            if value is None or value != value:
                row[name] = None
                continue
            row[name] = float(value)
            text[name] = _fmt(value, "pp1")
        row["basis"] = str(record["basis"])
        row["text"] = text
        rows.append(row)
    return {
        "family": _INTERVAL_FAMILY,
        "q": float(multi.q),
        "n_tests": int(multi.n_tests),
        "n_rejected": int(multi.n_rejected),
        "level": None if multi.interval_level is None else float(multi.interval_level),
        "alpha_star": None if multi.alpha_star is None else float(multi.alpha_star),
        "n_interval_only": int(multi.n_interval_only),
        "n_verdict_only": int(multi.n_verdict_only),
        "lines": list(report.interval_lines),
        "rows": rows,
    }


def build_structure(
    report: MultiReport,
    multi: MultiDiffResult,
    *,
    tree: TreeResult,
    manifest_a: RunManifest,
    manifest_b: RunManifest,
    rows_a: int,
    rows_b: int,
    tally_a: RunTally,
    tally_b: RunTally,
    store_root: str,
) -> dict[str, Any]:
    """The pair as data, per the spec's section 3.3.

    Pure: equal inputs give an equal dict. Reads no file, opens no socket, writes nothing, and
    derives no statistic -- every number here is already a field on M6's result, M7's report,
    M14's tree, a stored manifest or a ``RunTally``. The single exception is
    ``pair.created_at_gap_s``.

    ``tree`` is required: a structure that could be built without one could serve a page whose
    honesty block is missing the bound, and ADR-033's rule is together or not at all.
    """
    _check_tree(multi, tree)
    spec = report.spec
    coverage = {
        str(record["config_hash"]): record
        for record in (
            [] if multi.coverage is None else multi.coverage.to_dict(orient="records")
        )
    }
    panels = []
    for event in report.events:
        rows = {
            str(record["config_hash"]): record
            for record in multi.by_event[event].cells.to_dict(orient="records")
        }
        panels.append(_panel(spec, event, report.panels[event], rows, coverage))
    return {
        "schema": SCHEMA,
        "pair": {
            "store_root": store_root,
            "created_at_gap_s": _gap_seconds(manifest_a.created_at, manifest_b.created_at),
            "a": _arm(manifest_a, "baseline", rows_a, tally_a),
            "b": _arm(manifest_b, "candidate", rows_b, tally_b),
        },
        "diff": dict(report.provenance),
        "holes": _holes(spec, report, coverage),
        "view": {
            "title": spec.title,
            "x_axis": spec.x_axis,
            "y_axis": spec.y_axis,
            "fixed": dict(spec.fixed),
            "theme": spec.theme,
            "top_n": int(spec.top_n),
            "forest": spec.forest,
            "bound": float(report.bound),
            "sign_convention": _SIGN_CONVENTION,
        },
        "headline": report.headline,
        "trade_line": report.trade_line,
        "fence": _EPISTEMIC_FENCE,
        "panels": panels,
        "intervals": _intervals(report, multi),
        "tree": _tree_payload(tree.to_json()),
        "unverified": [
            {"id": name, "statement": statement, "blocked_by": blocked}
            for name, statement, blocked in _UNVERIFIED
        ],
        "heatmap_svg": report.to_svg(),
    }


# ---------- rendering ----------


def _lines_html(text: str) -> str:
    return "<br>".join(_html.escape(line) for line in text.splitlines())


def _scalar_text(value: Any) -> str:
    """A stored manifest value as one line. Nothing is parsed and nothing is derived."""
    if value is None:
        return "none"
    if isinstance(value, dict):
        return ", ".join(f"{key}={item}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _env_rows(value: Any, prefix: str) -> list[list[str]]:
    """``environment`` flattened to dotted key / value rows. Carried verbatim: nothing is read
    out of it, because a local run's shape and an imported run's shape have no key in common."""
    rows: list[list[str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(_env_rows(item, f"{prefix}.{key}" if prefix else str(key)))
        return rows
    if isinstance(value, list):
        for item in value:
            rows.extend(_env_rows(item, prefix))
        return rows
    rows.append([prefix, str(value)])
    return rows


def _identity_html(pair: Mapping[str, Any]) -> list[str]:
    a, b = pair["a"], pair["b"]
    rows = [[name, _scalar_text(a[name]), _scalar_text(b[name])] for name in _ARM_SCALARS]
    # The tally rows sit in the same table as ``rows_stored`` and outside the <details>: a
    # reader who can see how many rows a run stored and not how many of them carry no outcome
    # is reading ``rows_stored`` as a count of results.
    rows.extend(
        [name, _scalar_text(a["tally"][name]), _scalar_text(b["tally"][name])]
        for name in _TALLY_ROWS
    )
    gap = pair["created_at_gap_s"]
    parts = [
        "<h2>Run pair</h2>",
        _html_table(["field", "A (baseline)", "B (candidate)"], rows),
        f"<p>created_at gap, B minus A: {_html.escape(_scalar_text(gap))} seconds. "
        f"Store root: {_html.escape(str(pair['store_root']))}.</p>",
        f"<p>Sign convention: {_html.escape(_SIGN_CONVENTION)}.</p>",
        "<details><summary>environment, both arms (the runs' own configuration)</summary>",
    ]
    for key, role in (("a", "A (baseline)"), ("b", "B (candidate)")):
        parts.append(f"<h3>{_html.escape(role)}</h3>")
        parts.append(_html_table(["key", "value"], _env_rows(pair[key]["environment"], "")))
    parts.append("</details>")
    return parts


def _unverified_html(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    """The block naming what the page could not verify. Never collapsible and never below the
    figure: a page that cannot say it is unable to confirm the two runs are comparable renders
    a confidently wrong comparison in silence."""
    items = []
    for entry in entries:
        blocked = entry["blocked_by"]
        tail = (
            f" (closed by {_html.escape(str(blocked))})"
            if blocked is not None
            else " (nothing on the roadmap closes this)"
        )
        items.append(
            f"<li><strong>{_html.escape(str(entry['id']))}</strong> "
            f"{_html.escape(str(entry['statement']))}{tail}</li>"
        )
    return ["<h2>Not verified</h2>", "<ul>", *items, "</ul>"]


def _cell_rows(cell: Mapping[str, Any]) -> list[list[str]]:
    """The drill-down's own table. Every float goes through the structure's ``text`` or
    ``config_text``; the raw floats and the full config are in the index, where the page's
    script reads them.

    ``rows`` and ``no outcome`` sit immediately under ``n``, because the three together are
    the sentence: this cell ran that many replicates, that many stored no outcome, and the
    rest are what ``n`` compares.
    """
    text = cell["text"]
    config_text = cell["config_text"]
    rows = [
        ["coords", str(cell["coords"])],
        ["config_hash", str(cell["config_hash"])],
        ["n (a/b)", f"{cell['n_a']}/{cell['n_b']}"],
        ["rows (a/b)", f"{cell['rows_a']}/{cell['rows_b']}"],
        ["no outcome (a/b)", f"{cell['no_outcome_a']}/{cell['no_outcome_b']}"],
        ["events (a/b)", f"{cell['events_a']}/{cell['events_b']}"],
        ["rate_a (pp)", text["rate_a"]],
        ["rate_b (pp)", text["rate_b"]],
        ["delta (pp)", text["delta"]],
        ["stat", text["stat"]],
        ["p", text["p"]],
        ["q", text["q"]],
        ["MDE (pp)", text["mde"]],
        ["verdict", str(cell["verdict"])],
    ]
    for name, value in cell["config"].items():
        shown = config_text.get(str(name))
        rows.append([f"config.{name}", shown if isinstance(shown, str) else _scalar_text(value)])
    return rows


def _holes_html(holes: Sequence[Mapping[str, Any]]) -> list[str]:
    """The Holes section. With no holes it says so in as many words rather than rendering an
    empty table: a page that shows nothing where the holes go reads as a page with no holes
    only if it says which."""
    parts = [f"<h2>{_HOLES_HEADING}</h2>"]
    if not holes:
        parts.append(f"<p>{str(len(holes))} holes</p>")
        return parts
    rows = [
        [
            _scalar_text(hole["coords"]),
            str(hole["cause"]),
            _scalar_text(hole["config_hash"]),
            f"{hole['rows_a']}/{hole['rows_b']}",
            f"{hole['no_outcome_a']}/{hole['no_outcome_b']}",
        ]
        for hole in holes
    ]
    parts.append(_html_table(_HOLES_HEADER, rows))
    return parts


# ---------- the tree on the page ----------

#: What an untested level prints, by the reason's name. Four keys, and a reason this mapping
#: does not carry raises rather than printing a sentence nobody wrote. M14's three reason tuples
#: are never named here and never iterated for display order: precedence is M14's and is pinned
#: there, so a renderer that read a tuple would couple presentation to precedence and the next
#: person to reorder it for the page would "fix" M14's own guard (draft ADR-073).
_NOT_TESTED_SENTENCES: dict[str, str] = {
    "depth": "depth {configured} configured",
    "root_not_rejected": "the root did not reject",
    "no_group_rejected": "no group rejected",
    "one_group": "one group is the whole family restated",
}

#: What the leaf row's MDE column means, said once on the page: free text with no number in it.
_LEAF_MDE_MEANING = (
    "MDE is ADR-018's smallest detectable increase from arm A's rate, capped at the headroom, "
    "so on a cell at ceiling it reads the headroom and is not a power number."
)

#: The bound's assumption, beside the number rather than in a footnote.
_BOUND_ASSUMPTION = (
    "Yekutieli (2008) Corollary A.2 assumes each p-value is independent of its ancestors; this "
    "tree's group and root statistics aggregate their own cells, so that assumption is not "
    "established here."
)

_OMNIBUS_HEADING = "Omnibus"
_FAULT_LINES_HEADING = "Fault lines"
_CELLS_HEADING = "Cells"
_OMNIBUS_HEADER = ["event", "mean delta (pp)", "p", "rms delta (pp)", "p"]
_GROUP_HEADER_TAIL = [
    "cells",
    "informative",
    "unchanged by every exchange",
    "units (a/b)",
    "group MDE (pp)",
]
_DISCORDANT_HEADER = "discordant pairs"
_TESTED_HEADER_TAIL = ["p", "q", "verdict"]
_CELLS_HEADER = ["cell", "event", "delta (pp)", "q", "MDE"]
_PAIR_SWAP = "pair_swap"


def _not_tested_text(reason: Any, bound: Mapping[str, Any]) -> str:
    """The sentence an untested level prints, looked up by its reason's name."""
    try:
        sentence = _NOT_TESTED_SENTENCES[str(reason)]
    except KeyError:
        raise ViewerError(
            f"no sentence for the untested reason {reason!r}; this renderer prints the four "
            f"reasons {sorted(_NOT_TESTED_SENTENCES)} and does not invent a fifth"
        ) from None
    return sentence.replace("{configured}", str(bound["depth_configured"]))


def _paragraph(text: str) -> str:
    return f"<p>{_lines_html(text)}</p>"


def _omnibus_html(root: Mapping[str, Any]) -> list[str]:
    """The root's own headline verbatim, how the omnibus was drawn, one row per event in the
    root's order, and the informative line whose complement is a field and not a subtraction."""
    text = root["text"]
    rows = [
        [
            str(event),
            text["location"][event],
            text["p_location"][event],
            text["dispersion"][event],
            text["p_dispersion"][event],
        ]
        for event in root["events"]
    ]
    method_line = (
        f"min-p of location and dispersion; {root['n_permutations']} within-cell permutations, "
        f"{root['scheme']}, seed {root['seed']}"
    )
    informative = (
        f"informative cells: {root['n_informative_cells']} of {root['n_cells']}; "
        f"{root['n_uninformative_cells']} unchanged by every exchange"
    )
    floor = (
        f"p floor {text['p_floor']}: the smallest p {root['n_permutations']} permutations can "
        "express; a p at the floor is a bound, not a measurement"
    )
    return [
        f"<h2>{_OMNIBUS_HEADING}</h2>",
        _paragraph(str(root["headline"])),
        _paragraph(method_line),
        _paragraph(floor),
        _html_table(_OMNIBUS_HEADER, rows),
        _paragraph(informative),
    ]


def _bound_html(bound: Mapping[str, Any]) -> str:
    """The rule's number with every term of the rule beside it -- the ``2`` and the ``x`` are
    text around four fields -- then the assumption the source's corollary rests on.

    One paragraph, the last block of the honesty section: V19's rules hold for it as they do
    for a panel's, because it is the second number of that block and not a footnote.
    """
    text = bound["text"]
    rule = (
        f"depth {bound['depth']} ({bound['depth_configured']} configured); outer-nodes false "
        f"discovery rate at most {text['bound']} = 2 x {bound['depth']} x {text['q']} x "
        f"{text['delta_star']}"
    )
    return _paragraph("\n".join((rule, _BOUND_ASSUMPTION)))


def _fault_lines_html(tree: Mapping[str, Any]) -> list[str]:
    """Level 2: the grouping and the shape it was admitted on; every refused key in chain order
    with its detail verbatim; the null and what tested it, or why nothing did; one row per group
    in label order, never ordered by result.

    The discordant column exists only under pair swap and the p, q and verdict columns only
    when the level was tested: a column that does not exist cannot be read.
    """
    grouping, fault, root = tree["grouping"], tree["fault_lines"], tree["root"]
    grouping_text = grouping["text"]
    head = (
        f"grouping {grouping['key']} ({grouping['resolved_by']}), {grouping['n_groups']} groups; "
        f"cells per group min {grouping['size_min']} / median {grouping_text['size_median']} / "
        f"max {grouping['size_max']}; {fault['n_degenerate_groups']} degenerate; "
        f"{grouping['n_resolvable_groups']} of {grouping['n_groups']} groups resolve "
        f"{grouping_text['max_group_mde']}pp at alpha {grouping_text['alpha_floor']}"
    )
    parts = [f"<h2>{_FAULT_LINES_HEADING}</h2>", _paragraph(head)]
    for refusal in grouping["refused"]:
        parts.append(
            _paragraph(
                f"refused {refusal['key']} ({refusal['rung']}): {refusal['reason']}; "
                f"{refusal['detail']} next: {refusal['next_rung']}"
            )
        )
    if fault["tested"]:
        null = (
            f"\"{fault['null']}\" tested by BH across {fault['n_groups']} groups at q "
            f"{fault['text']['q']}: {fault['n_rejected_groups']} rejected"
        )
    else:
        null = (
            f"\"{fault['null']}\" not tested: "
            f"{_not_tested_text(fault['reason'], tree['bound'])}"
        )
    parts.append(_paragraph(null))
    if fault["tested"]:
        # C33 (b), only where the level was tested: there is no floor under a p nobody drew.
        parts.append(
            _paragraph(
                f"group p floor {root['text']['p_floor']}: the same "
                f"{root['n_permutations']} permutations; a group p at the floor is a bound, "
                "not a measurement"
            )
        )
    pair_swap = root["scheme"] == _PAIR_SWAP
    header = [str(grouping["key"]), *_GROUP_HEADER_TAIL]
    if pair_swap:
        header.append(_DISCORDANT_HEADER)
    if fault["tested"]:
        header.extend(_TESTED_HEADER_TAIL)
    rows = []
    for group in fault["groups"]:
        group_text = group["text"]
        row = [
            str(group["label"]),
            str(group["n_cells"]),
            str(group["n_informative_cells"]),
            str(group["n_uninformative_cells"]),
            f"{group['n_a']}/{group['n_b']}",
            f"{group_text['mde']}pp",
        ]
        if pair_swap:
            row.append(str(group["n_discordant"]))
        if fault["tested"]:
            row.append(group_text["p_group"])
            row.append(group_text["q_group"])
            row.append("rejected" if group["rejects"] else "not rejected")
        rows.append(row)
    parts.append(_html_table(header, rows))
    return parts


def _leaf_config(leaf: Mapping[str, Any]) -> str:
    """A leaf as ``key=value`` over every key of its config, in the config's own order.

    Every key, not the figure's axes: the tree is over the whole family and ``--fix`` slices
    only the figure. The value is the structure's own coordinate text, exactly as the
    drill-down spells it, so no token on this page is a number nothing carries as a string.
    """
    shown = leaf["text"]["config"]
    return ", ".join(
        f"{name}={shown[name] if isinstance(shown.get(name), str) else _scalar_text(value)}"
        for name, value in leaf["config"].items()
    )


def _cells_html(leaves: Mapping[str, Any], bound: Mapping[str, Any]) -> list[str]:
    """Level 3: the null and what tested it, or the one reason nothing did and nothing else;
    what the MDE column means; then per family, in the tree's order, its line and under it one
    row per rejected cell in the family's own order."""
    parts = [f"<h2>{_CELLS_HEADING}</h2>"]
    if not leaves["tested"]:
        parts.append(_paragraph(f"not tested: {_not_tested_text(leaves['reason'], bound)}"))
        return parts
    head = (
        f"\"{leaves['null']}\" tested by BH within each of {leaves['n_families']} rejecting "
        f"groups at q {leaves['text']['q']}: {leaves['n_rejected']} of {leaves['n_tests']} "
        "rejected"
    )
    parts.append(_paragraph(head))
    if leaves["families"]:
        parts.append(_paragraph(_LEAF_MDE_MEANING))
    for family in leaves["families"]:
        family_text = family["text"]
        parts.append(
            _paragraph(
                f"{family['key']}={family['label']}: {family['n_tests']} tests, "
                f"{family['n_rejected']} rejected; cell MDE median "
                f"{family_text['mde_median']}pp / max {family_text['mde_max']}pp"
            )
        )
        rows = [
            [
                _leaf_config(leaf),
                str(leaf["event"]),
                leaf["text"]["delta"],
                leaf["text"]["q_within"],
                f"{leaf['text']['mde']}pp",
            ]
            for leaf in family["cells"]
            if leaf["rejects"]
        ]
        if rows:
            parts.append(_html_table(_CELLS_HEADER, rows))
    return parts


def _index_key(event: str, config_hash: str) -> str:
    return f"{event} {config_hash}"


def _script_json(payload: Any) -> str:
    """``json.dumps`` does not escape the less-than character, so a config value carrying a
    closing script tag would close the block. The three markup characters become their
    backslash-u escapes, which JSON reads back as themselves."""
    dump = json.dumps(payload, sort_keys=False, allow_nan=False)
    return dump.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _picker_html(
    panels: Sequence[Mapping[str, Any]], selected: str, holes: Sequence[Mapping[str, Any]]
) -> list[str]:
    """One group per event, then the holes. The holes group is always present, empty on a pair
    that has none: a picker that grows a group when something goes wrong hides the question."""
    parts = ['<select id="pl-picker">']
    for panel in panels:
        parts.append(f'<optgroup label="{_html.escape(str(panel["event"]))}">')
        for cell in panel["cells"]:
            key = _index_key(str(panel["event"]), str(cell["config_hash"]))
            mark = " selected" if key == selected else ""
            parts.append(
                f'<option value="{_html.escape(key)}"{mark}>'
                f'{_html.escape(str(cell["coords"]))}</option>'
            )
        parts.append("</optgroup>")
    parts.append(f'<optgroup label="{_HOLES_OPTGROUP}">')
    for index, hole in enumerate(holes):
        coords = hole["coords"]
        label = hole["config_hash"] if coords is None else coords
        parts.append(f'<option value="hole:{index}">{_html.escape(str(label))}</option>')
    parts.append("</optgroup>")
    parts.append("</select>")
    return parts


_SCRIPT = """
(function () {
  var block = document.getElementById("PL_INDEX_ID");
  var target = document.getElementById("pl-cell");
  var picker = document.getElementById("pl-picker");
  var figure = document.getElementById("pl-figure");
  if (!block || !target || !picker) { return; }
  var index = JSON.parse(block.textContent);
  var missing = "PL_HOLE_MESSAGE";
  var order = ["coords", "config_hash", "n_a", "n_b", "rows_a", "rows_b",
               "no_outcome_a", "no_outcome_b", "events_a", "events_b",
               "rate_a", "rate_b", "delta", "stat", "p", "q", "mde", "verdict"];
  function row(table, label, value) {
    var tr = document.createElement("tr");
    var th = document.createElement("td");
    var td = document.createElement("td");
    th.textContent = label;
    td.textContent = value === null ? "none" : String(value);
    tr.appendChild(th);
    tr.appendChild(td);
    table.appendChild(tr);
  }
  function mark(key) {
    var chosen = document.querySelectorAll("[data-selected]");
    for (var i = 0; i < chosen.length; i++) { chosen[i].removeAttribute("data-selected"); }
    var panels = document.querySelectorAll("[data-panel]");
    for (var p = 0; p < panels.length; p++) {
      var name = panels[p].getAttribute("data-panel");
      var cells = panels[p].querySelectorAll("[data-cell]");
      for (var c = 0; c < cells.length; c++) {
        if (name + " " + cells[c].getAttribute("data-cell") === key) {
          cells[c].setAttribute("data-selected", "1");
        }
      }
    }
  }
  function show(key) {
    while (target.firstChild) { target.removeChild(target.firstChild); }
    var cell = index[key];
    if (!cell) {
      target.textContent = missing;
      mark(key);
      return;
    }
    var table = document.createElement("table");
    for (var i = 0; i < order.length; i++) {
      var name = order[i];
      var shown = cell.text && name in cell.text ? cell.text[name] : cell[name];
      row(table, name, shown);
    }
    var config = cell.config || {};
    var texts = cell.config_text || {};
    for (var key2 in config) {
      if (Object.prototype.hasOwnProperty.call(config, key2)) {
        var shown2 = typeof texts[key2] === "string" ? texts[key2] : config[key2];
        row(table, "config." + key2, shown2);
      }
    }
    target.appendChild(table);
    mark(key);
  }
  picker.addEventListener("change", function () { show(picker.value); });
  if (figure) {
    figure.addEventListener("click", function (ev) {
      var hit = ev.target.closest ? ev.target.closest("[data-cell]") : null;
      var panel = ev.target.closest ? ev.target.closest("[data-panel]") : null;
      if (!hit || !panel) { return; }
      var key = panel.getAttribute("data-panel") + " " + hit.getAttribute("data-cell");
      picker.value = key;
      show(key);
    });
  }
  show(picker.value);
})();
"""

# Layout only: the base sheet is M7's own, and no rule here sets a colour.
#
# ``pointer-events`` is load-bearing and grid-shaped. M7 draws the significance glyph and the
# trade notch in later sibling groups, painted over the cell rect but not descended from it, so
# without this a click on a significant cell resolves to no cell at all -- and those are the
# cells a reader clicks first. ``[data-mde]`` is deliberately absent: it exists only in forest
# mode, where it is a child of ``<g data-cell>`` and is the widest target in the row.
_LAYOUT = (
    "[data-sig],svg path{pointer-events:none}"
    "[data-cell]{cursor:pointer}"
    "[data-selected]{outline:2px solid currentColor;outline-offset:1px}"
    "details{margin:12px 0}"
    "summary{cursor:pointer}"
    "select{max-width:100%;font-family:inherit;font-size:inherit}"
    "#pl-cell table{margin:8px 0}"
)


def render_html(structure: Mapping[str, Any]) -> str:
    """The whole document as one string, from the structure alone.

    Never sees a ``MultiReport``, a ``DiffResult`` or a ``DataFrame``, and derives nothing: the
    ``created_at`` gap it prints was computed once during assembly, and every tree number it
    prints was formatted once there. The honesty and unverified blocks sit above the figure --
    a real sweep's heatmap is taller than a screen, so below it is below the fold -- and so do
    the tree's own four regions, for the same reason; the only collapsible thing on the page is
    the runs' own ``environment``.
    """
    schema = structure.get("schema")
    if schema != SCHEMA:
        raise ViewerError(
            f"unknown structure schema {schema!r}; this renderer reads {SCHEMA!r} only and "
            "does not attempt a best-effort render"
        )
    # Two shapes cannot share a schema string silently. ``/4`` carries two packets (the comment
    # above SCHEMA says why), so a ``/4`` assembled before the flat family's intervals joined it
    # is refused by name rather than drawn with a section missing. The dashboard's stored
    # fixtures are exactly such structures, which is the point.
    if "intervals" not in structure:
        raise ViewerError(
            "this structure carries no intervals; it was assembled before the flat family's "
            "intervals joined proofload.viewpair/4 and is not a page this renderer will draw"
        )
    if "tree" not in structure:
        raise ViewerError(
            "this structure carries no tree; a page whose honesty block cannot state the bound "
            "is not a page this renderer will draw, and the two ship together or not at all"
        )
    pair = structure["pair"]
    view = structure["view"]
    diff = structure["diff"]
    panels = structure["panels"]
    tree = structure["tree"]
    title = str(view["title"])

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{_html.escape(title)}</title>",
        f"<style>{_html_style(view['theme'])}{_LAYOUT}</style>",
        "</head>",
        "<body>",
        f"<h1>{_html.escape(title)}</h1>",
    ]
    parts.extend(_identity_html(pair))

    events = ", ".join(str(name) for name in diff["events"])
    parts.append("<h2>Events</h2>")
    parts.append(f"<p>Events: {_html.escape(events)} ({_EVENT_LINE_TAIL}).</p>")

    # The omnibus is the first result on the page: the ladder's rung three, above the flat
    # family's rung two, because it is the headline of the layered report.
    parts.extend(_omnibus_html(tree["root"]))

    parts.append("<h2>Result</h2>")
    parts.append(f"<p>{_lines_html(str(structure['headline']))}</p>")
    if structure["trade_line"] is not None:
        parts.append(f"<p>{_html.escape(str(structure['trade_line']))}</p>")

    parts.append("<h2>Honesty</h2>")
    for panel in panels:
        parts.append(f"<h3>{_html.escape(str(panel['event']))}</h3>")
        parts.append(f"<p>{_lines_html(str(panel['honesty']))}</p>")
    # ADR-060: the flat family's intervals are the last thing in the honesty band before the
    # bound, and never beside a leaf row -- *Not verified*, *Fault lines* and *Cells* sit between
    # this paragraph and the first leaf. One paragraph, the lines as M7 formatted them.
    parts.append(_paragraph("\n".join(str(line) for line in structure["intervals"]["lines"])))
    # The bound is the second number of the honesty block, not a footnote: what this run could
    # not have seen, then what the whole procedure controls at, on one screen.
    parts.append(_bound_html(tree["bound"]))

    parts.extend(_unverified_html(structure["unverified"]))

    parts.extend(_fault_lines_html(tree))
    parts.extend(_cells_html(tree["leaves"], tree["bound"]))

    svg = str(structure["heatmap_svg"]).rstrip("\n")
    parts.append("<h2>Heatmap</h2>")
    parts.append(f'<div id="pl-figure" class="figure">{svg}</div>')

    index = {}
    for panel in panels:
        for cell in panel["cells"]:
            index[_index_key(str(panel["event"]), str(cell["config_hash"]))] = cell
    first = panels[0]
    selected = _index_key(str(first["event"]), str(first["worst_hashes"][0]))
    holes = structure["holes"]
    parts.append("<h2>Cell</h2>")
    parts.append('<div class="picker">')
    parts.extend(_picker_html(panels, selected, holes))
    parts.append("</div>")
    opened = _html_table(["field", "value"], _cell_rows(index[selected]))
    parts.append(f'<div id="pl-cell">{opened}</div>')
    parts.append(
        f'<script type="application/json" id="{_INDEX_ID}">{_script_json(index)}</script>'
    )
    # The holes ride in a block of their own rather than as entries in the cell index: every
    # absent rect carries the same ``data-cell="absent"`` and cannot say which hole it is, so
    # a hole is reached through the picker and the table, and a click on a hole still gets the
    # one message that is true of all of them.
    parts.append(
        f'<script type="application/json" id="{_HOLES_ID}">{_script_json(holes)}</script>'
    )
    script = _SCRIPT.replace("PL_INDEX_ID", _INDEX_ID).replace("PL_HOLE_MESSAGE", _HOLE_MESSAGE)
    parts.append(f"<script>{script}</script>")

    parts.extend(_holes_html(holes))

    parts.append("<h2>Worst cells</h2>")
    for panel in panels:
        parts.append(f"<h3>{_html.escape(str(panel['event']))}</h3>")
        parts.append(_html_table(panel["worst_header"], panel["worst_rows"]))

    parts.append(f"<blockquote>{_html.escape(str(structure['fence']))}</blockquote>")
    parts.append("<h2>Provenance</h2>")
    items = "".join(f"<li>{_html.escape(line[2:])}</li>" for line in _provenance_lines(diff))
    parts.append(f"<ul>{items}</ul>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"


# ---------- the server ----------


class _Server(ThreadingHTTPServer):
    """A loopback listener that says nothing.

    ``handle_error`` matters more than ``log_message``: ``socketserver``'s default prints a
    separator, the client address and a full traceback to the real ``sys.stderr`` on any
    exception inside a handler, which is the loudest stream this process has and the one every
    other verb routes through its given ``_IO``. Both are silenced.
    """

    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        return


def _handler(body: bytes) -> type[BaseHTTPRequestHandler]:
    """One handler class closing over the page bytes.

    The page is a snapshot taken before the socket existed and is never re-read: if the store
    gains rows while the server runs, this page keeps showing what it was built from. That is
    the read-only guarantee working, which is why both arms' ``status`` is on the page.
    """

    class _Page(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server's own dispatch name
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", _CONTENT_TYPE)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", _CSP)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
            return

    return _Page


def serve_page(page: str, *, on_bind: Callable[[HTTPServer], None]) -> None:
    """Bind an ephemeral port on loopback and serve ``page`` at ``GET /`` until Ctrl-C.

    ``on_bind`` gets the bound server, not the port: the CLI wants ``server_address[1]`` for
    its URL line and a test wants ``shutdown()``, and handing back an ``int`` gives the test
    nothing. It is required rather than optional -- an ephemeral port nobody is told about is
    a page nobody can open.
    """
    body = page.encode("utf-8")
    try:
        server = _Server((_HOST, 0), _handler(body))
    except OSError as exc:
        raise ViewerError(f"cannot bind a loopback port: {exc}") from exc
    try:
        on_bind(server)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
