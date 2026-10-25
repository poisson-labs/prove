"""Oracle for the M7 multi-event amendment: per-event panels, trade line, saturation, forest,
survival report.

B1 is the gate. It once compared ``build_report`` against an S8.1 output frozen on disk (built
with the pre-amendment renderer, ``fisher_bh``, the admitted knob on x, dark theme, diff with
manifests, ``build_report`` without). The frozen file went with the study fixture it was built
on; B1 now renders the generated lattice pair (``tests/lattice.py``) the same way and checks
every fact that record carried -- the title and headline, the worst-cells table's rows,
coordinates and values, the Methods row, the honesty block's place, the fence and the
provenance list -- against the lattice's own references (its design's counts and scipy's
Fisher test with one BH family), never against Prove's own diff.

Every ``data-`` assertion is made on the ``xml.etree.ElementTree`` tree, never on the raw
string. Fixture tests use the lattice pair through ``lattice_store``; B17 regenerates the two S10
quickstart runs with ``cli.main`` under a fixed salt; everything else uses synthetic
``EventDiff`` / ``MultiDiffResult`` values built directly from M6's ``cells`` columns, with
``max_mde_unchanged`` / ``max_mde_unchanged_cell`` and ``trades`` derived the way M6
derives them.

Structural pins this oracle adds where the spec leaves the SVG open (as S8's did for
``data-cell``):

- **Panel captions.** ``<event>: <n_safer> safer, <n_worse> worse`` appears as a Markdown
  line of its own (not the headline), as a ``<text>`` inside the panel's
  ``<g data-panel="<event>">``, and in the HTML text; panel sections in Markdown run from one
  caption to the next.
- **Forest rows.** Each row is ``<g data-cell="<hash>">`` (spec). Inside it the point carries
  ``data-point="1"`` (a ``<circle>`` with ``cx`` or a ``<rect>``), the MDE bracket carries
  ``data-mde="1"`` (a ``<rect>`` with ``width`` or a ``<line>`` with ``x1``/``x2``), and the
  significance glyph is a descendant of its row, which is how I7 recovers the significant
  set after attribute stripping on a forest panel.
- **Saturation legend.** The legend entry's text contains ``both 0% / both 100%``.
- **Survival panel headings.** A survival panel has no safer/worse caption; its Markdown
  section starts at the first heading line (``#``-prefixed) naming the event, and worst-cells
  rows lead with the coordinate cells in axis order, as S8's table does.
- **Honesty lines.** Line 1 matches ``Worst-powered unchanged cell (<coords>, n=a/b) can only
  detect a Npp rise. "<n_worse> worse" is an honest claim only above that.`` or is the fixed
  sentence; line 2 matches ``Worst-powered cell overall: Npp (<coords>).``

Deliberately absent, reported to the spec author rather than adapted (see the session
report): B1's SVG/HTML clause (the fixture's saturated cells change their fills and the legend)
and B3 on the single-event ``build_report`` (its tiebreak reorders the frozen I19 data and the
top-10 table that B1's Markdown clause pins). B3 is asserted on the multi-report panels only.
"""

from __future__ import annotations

import hashlib
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from html import escape as html_escape
from html import unescape as html_unescape
from io import StringIO
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import lattice
from poisson_prove import cli
from poisson_prove.diff import DiffResult, EventDiff, MultiDiffResult, diff, multi_diff
from poisson_prove.report import (
    SATURATED_FILL,
    SEQUENTIAL_RAMP,
    Cell,
    MultiReport,
    Report,
    ReportSpec,
    SurvivalReport,
    build_multi_report,
    build_report,
    build_survival_report,
)
from poisson_prove.store import RunManifest, Store, config_hash
from poisson_prove.survival import cell_table, censor
from conftest import quickstart_design
from test_pf4_stats import POWER, _ref_fisher_power

ROOT = Path(__file__).resolve().parents[1]
#: B1. The single-event report's title on the lattice pair.
LATTICE_TITLE = "Lattice before -> after"
# PF3 (spec sections 8.8 and 14): the one copy is the packaged spec; this is its design at
# the 100 replicates this file was frozen at.
QUICKSTART = quickstart_design()
# PF4 re-freeze (PF4.30, PF4.48a, reading R33): the quickstart design at 100 replicates with nothing
# declared has a detection limit (0.262 at base rate 0.400) above the default accepted change of 0.20,
# so its sweep is refused; every frozen sweep of it in this file accepts 0.3, the smallest round value
# above the limit.
QUICKSTART_MAX_MDE = ("--max-mde", "0.3")
MOCK_ROLLOUT = "poisson_prove.examples.mock_agent:rollout"
MOCK_PATCHED = "poisson_prove.examples.mock_agent:rollout_patched"
QUICKSTART_SALT = "0000000000000015"

CELL_COLUMNS = [
    "config_hash", "config", "n_a", "n_b", "events_a", "events_b", "rate_a", "rate_b",
    "delta", "stat", "p", "q", "verdict", "mde",
]
TRADES_COLUMNS = ["config_hash", "config", "safer_events", "worse_events"]
M4_COLUMNS = [
    "run_id", "config_hash", "config", "seed", "replicate_index", "outcome", "t", "horizon",
    "confidence", "meta", "error", "wall_time", "backend_meta",
]
STRIP = ("fill", "stroke", "style", "class")
HONESTY_FIRST_RE = re.compile(
    r'^Worst-powered unchanged cell \((.*), n=(\d+)/(\d+)\) can only detect a (\d+)pp rise\. '
    r'"(\d+) worse" is an honest claim only above that\.$'
)
HONESTY_NONE = "No unchanged cells; every cell moved significantly."
HONESTY_OVERALL_RE = re.compile(r"^Worst-powered cell overall: (\d+)pp \((.*)\)\.$")
CAPTION_RE = re.compile(r"^(\S+): (\d+) safer, (\d+) worse$")
HEADLINE_EVENT_RE = re.compile(r"(\S+): (\d+) safer, (\d+) worse")
COVERAGE_RE = re.compile(r"n=(\d+)\.\.(\d+) per cell, (\d+) cells with n < 16")
SATURATION_LEGEND = "both 0% / both 100%"
# LS retrofit, 2026-09-22 (local serve pass, Phase A): the retired tail "The patch moved failures, it did not remove them." leaves every surface
# (spec LS D2, D10, LS13); a trade line is recognised by its ``Trade:`` head alone.
TRADE_MARK = "Trade:"
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
HASH_RE = re.compile(r"\b[0-9a-f]{16}\b")
WORDS = ["alpha", "bravo", "charlie", "dingo", "echo", "foxtrot", "golf", "hotel", "india", "juliet"]


# ---------- reference formatting ----------


def _no_neg_zero(s: str) -> str:
    return s[1:] if s.startswith("-") and float(s) == 0.0 else s


def _pp1(x: float) -> str:
    return _no_neg_zero(format(x * 100, ".1f"))


def _pp0(x: float) -> str:
    return _no_neg_zero(format(x * 100, ".0f"))


# ---------- synthetic factories ----------


def make_cell(
    config: dict[str, Any],
    *,
    n_a: int = 32,
    n_b: int = 32,
    rate_a: float = 0.5,
    rate_b: float | None = None,
    delta: float = 0.0,
    p: float = 0.5,
    q: float = 0.5,
    verdict: str = "unchanged",
    mde: float = 0.2,
    stat: float = 1.0,
) -> dict[str, Any]:
    rb = rate_b if rate_b is not None else min(1.0, max(0.0, rate_a + delta))
    return {
        "config_hash": config_hash(config),
        "config": dict(config),
        "n_a": n_a,
        "n_b": n_b,
        "events_a": int(round(rate_a * n_a)),
        "events_b": int(round(rb * n_b)),
        "rate_a": rate_a,
        "rate_b": rb,
        "delta": delta,
        "stat": stat,
        "p": p,
        "q": q,
        "verdict": verdict,
        "mde": mde,
    }


def _cells_frame(cells: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(cells, columns=CELL_COLUMNS)
    frame["config"] = frame["config"].astype(object)
    frame["verdict"] = frame["verdict"].astype(object)
    return frame


def _unchanged_mde(frame: pd.DataFrame) -> tuple[float, str | None]:
    unchanged = frame[frame["verdict"] == "unchanged"]
    if len(unchanged) == 0:
        return math.nan, None
    top = float(unchanged["mde"].max())
    return top, str(min(unchanged.loc[unchanged["mde"] == top, "config_hash"]))


def make_diff(
    cells: list[dict[str, Any]],
    *,
    method: str = "fisher_bh",
    seed_identity_match: bool = False,
    unpaired_analysis: bool = False,
    q: float = 0.05,
    event: str = "fell",
    t_unit: str = "steps",
    horizon: float = 10.0,
    max_mde: float | None = None,
) -> DiffResult:
    """Single-event DiffResult with the two S11 fields filled the way M6 fills them."""
    frame = _cells_frame(cells)
    verdicts = list(frame["verdict"])
    top_unchanged, top_cell = _unchanged_mde(frame)
    return DiffResult(
        cells=frame,
        method=method,  # type: ignore[arg-type]
        seed_identity_match=seed_identity_match,
        unpaired_analysis=unpaired_analysis,
        q=q,
        event=event,
        t_unit=t_unit,
        horizon=horizon,
        n_safer=verdicts.count("safer"),
        n_worse=verdicts.count("worse"),
        n_unchanged=verdicts.count("unchanged"),
        n_not_comparable=0,
        max_mde=max_mde if max_mde is not None else (float(frame["mde"].max()) if len(frame) else 0.0),
        dropped_a=0,
        dropped_b=0,
        truncated=0,
        max_mde_unchanged=top_unchanged,
        max_mde_unchanged_cell=top_cell,
    )


#: PF4 (PF4.20): an event's kind. ``safer`` and ``worse`` are a reader's words only for an event
#: whose kind is known; the tests about the safer/worse captions and honesty words build their
#: hand-made events as failure events, which keeps the old words (a rise is worse).
FAILURE = "failure"


def make_event(
    event: str, cells: list[dict[str, Any]], *, cause_specific: bool = False, kind: str | None = None
) -> EventDiff:
    frame = _cells_frame(cells)
    verdicts = list(frame["verdict"])
    top_unchanged, top_cell = _unchanged_mde(frame)
    return EventDiff(
        event=event,
        cells=frame,
        n_safer=verdicts.count("safer"),
        n_worse=verdicts.count("worse"),
        n_unchanged=verdicts.count("unchanged"),
        max_mde=float(frame["mde"].max()) if len(frame) else 0.0,
        max_mde_unchanged=top_unchanged,
        max_mde_unchanged_cell=top_cell,
        cause_specific=cause_specific,
        kind=kind,
    )


def make_multi(
    events: Sequence[EventDiff],
    *,
    method: str = "fisher_bh",
    seed_identity_match: bool = False,
    unpaired_analysis: bool = False,
    q: float = 0.05,
    t_unit: str = "steps",
    horizon: float = 10.0,
    inferred: bool = False,
    non_event: str | None = None,
    n_not_comparable: int = 0,
    dropped_a: int = 0,
    dropped_b: int = 0,
    truncated: int = 0,
) -> MultiDiffResult:
    """MultiDiffResult whose ``trades`` are derived from the per-event verdicts as M6 does."""
    by_event = {e.event: e for e in events}
    names = tuple(by_event)
    hashes: dict[str, dict[str, Any]] = {}
    for e in events:
        for row in e.cells.itertuples(index=False):
            hashes.setdefault(str(row.config_hash), row.config)
    hash_sets = [set(e.cells["config_hash"]) for e in events]
    common = sorted(h for h in hashes if all(h in hs for hs in hash_sets))
    verdict_of = {
        e.event: dict(zip(e.cells["config_hash"], e.cells["verdict"], strict=True)) for e in events
    }
    trade_rows = []
    for h in common:
        safer = tuple(k for k in names if verdict_of[k][h] == "safer")
        worse = tuple(k for k in names if verdict_of[k][h] == "worse")
        if safer and worse:
            trade_rows.append(
                {"config_hash": h, "config": hashes[h], "safer_events": safer, "worse_events": worse}
            )
    trades = pd.DataFrame.from_records(trade_rows, columns=TRADES_COLUMNS)
    for col in ("config", "safer_events", "worse_events"):
        trades[col] = trades[col].astype(object)
    return MultiDiffResult(
        events=names,
        by_event=by_event,
        method=method,  # type: ignore[arg-type]
        seed_identity_match=seed_identity_match,
        unpaired_analysis=unpaired_analysis,
        q=q,
        t_unit=t_unit,
        horizon=horizon,
        n_tests=len(common) * len(names),
        n_not_comparable=n_not_comparable,
        dropped_a=dropped_a,
        dropped_b=dropped_b,
        truncated=truncated,
        trades=trades,
        inferred=inferred,
        non_event=non_event,
    )


def grid_cells(
    xs: Sequence[Any],
    ys: Sequence[Any] | None,
    *,
    x_key: str = "mu",
    y_key: str = "push",
    delta_fn: Any = None,
    verdict_fn: Any = None,
    mde_fn: Any = None,
    **cell_kw: Any,
) -> list[dict[str, Any]]:
    cells = []
    for i, x in enumerate(xs):
        for j, y in enumerate(ys if ys is not None else [None]):
            config = {x_key: x} if ys is None else {x_key: x, y_key: y}
            delta = delta_fn(i, j) if delta_fn else 0.0
            verdict = verdict_fn(i, j, delta) if verdict_fn else "unchanged"
            mde = mde_fn(i, j) if mde_fn else 0.1 + 0.01 * ((i + j) % 5)
            cells.append(make_cell(config, delta=delta, verdict=verdict, mde=mde, **cell_kw))
    return cells


def sign_verdict(i: int, j: int, delta: float) -> str:
    return "safer" if delta < 0 else "worse" if delta > 0 else "unchanged"


def spec2(**kw: Any) -> ReportSpec:
    base: dict[str, Any] = {"title": "t", "x_axis": "mu", "y_axis": "push"}
    base.update(kw)
    return ReportSpec(**base)


def _manifest(run_id: str, *, run_salt: str = "salt", t_unit: str = "steps") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        target_id=f"target@{run_id}",
        t_unit=t_unit,
        run_salt=run_salt,
        axis_types={"mu": "continuous", "push": "continuous"},
        backend="local",
        environment={},
    )


def two_event_multi(*, kind: str | None = None, **multi_kw: Any) -> MultiDiffResult:
    """3x2 grid, two events; (0.1, 10) and (0.3, 20) are trades, (0.2, 10) is safer in one only."""
    xs, ys = [0.1, 0.2, 0.3], [10, 20]

    def d1(i: int, j: int) -> float:
        return {(0, 0): -0.3, (2, 1): 0.25, (1, 0): -0.2}.get((i, j), 0.05 * (i - j))

    def d2(i: int, j: int) -> float:
        return {(0, 0): 0.2, (2, 1): -0.15}.get((i, j), 0.02 * (j - i))

    def v1(i: int, j: int, dl: float) -> str:
        return sign_verdict(i, j, dl) if (i, j) in {(0, 0), (2, 1), (1, 0)} else "unchanged"

    def v2(i: int, j: int, dl: float) -> str:
        return sign_verdict(i, j, dl) if (i, j) in {(0, 0), (2, 1)} else "unchanged"

    alpha = make_event("alpha", grid_cells(xs, ys, delta_fn=d1, verdict_fn=v1), kind=kind)
    beta = make_event("beta", grid_cells(xs, ys, delta_fn=d2, verdict_fn=v2), kind=kind)
    return make_multi([alpha, beta], **multi_kw)


# ---------- SVG helpers ----------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def svg_root(report: Report | MultiReport | SurvivalReport) -> ET.Element:
    return ET.fromstring(report.to_svg())


def cell_nodes(root: ET.Element) -> list[ET.Element]:
    """Cell carriers in document order: heatmap/strip ``<rect data-cell>`` or forest ``<g data-cell>``."""
    return [e for e in root.iter() if "data-cell" in e.attrib and _local(e.tag) in ("rect", "g")]


def cell_rects(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if _local(e.tag) == "rect" and "data-cell" in e.attrib]


def glyphs(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if e.attrib.get("data-sig") == "1"]


def panel_groups(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if "data-panel" in e.attrib]


def texts(root: ET.Element) -> list[str]:
    """Every ``<text>`` in document order. LS retrofit, 2026-09-22 (local serve pass, Phase A, found by the shim run): a long title, headline,
    trade line or legend caption is drawn as several ``<text>`` elements, the continuation lines
    carrying ``data-wrap="1"`` (spec LS D9, section 3.1 (b)); those are joined back onto their first
    line with a space, so a text reads as one whatever the box width."""
    out: list[str] = []
    for e in root.iter():
        if _local(e.tag) != "text":
            continue
        content = "".join(e.itertext())
        if e.attrib.get("data-wrap") == "1" and out:
            out[-1] = f"{out[-1]} {content}"
        else:
            out.append(content)
    return out


def strip_presentation(root: ET.Element) -> ET.Element:
    for e in root.iter():
        for attr in STRIP:
            e.attrib.pop(attr, None)
    return root


def tree_signature(e: ET.Element) -> tuple:
    return (
        _local(e.tag),
        tuple(sorted(e.attrib.items())),
        (e.text or "").strip(),
        tuple(tree_signature(c) for c in e),
    )


def rgb(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_distance(a: str, b: str) -> float:
    return math.dist(rgb(a), rgb(b))


def is_red_family(hexstr: str) -> bool:
    r, g, b = rgb(hexstr)
    return r > g and r > b


def fills_by_hash(root: ET.Element) -> dict[str, str]:
    return {
        r.attrib["data-cell"]: r.attrib["fill"]
        for r in cell_rects(root)
        if r.attrib["data-cell"] != "absent"
    }


def _parents(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def owning_row(e: ET.Element, parents: dict[ET.Element, ET.Element]) -> ET.Element | None:
    node = parents.get(e)
    while node is not None:
        if "data-cell" in node.attrib:
            return node
        node = parents.get(node)
    return None


def check_svg_hygiene(svg: str) -> ET.Element:
    root = ET.fromstring(svg)
    assert _local(root.tag) == "svg"
    assert "viewBox" in root.attrib and len(root.attrib["viewBox"].split()) == 4
    assert not [e for e in root.iter() if _local(e.tag) == "script"]
    for e in root.iter():
        for key, value in e.attrib.items():
            assert not key.endswith("href"), (key, value)
            assert "url(" not in value and "@import" not in value
        assert "url(" not in (e.text or "") and "@import" not in (e.text or "")
    assert "<script" not in svg
    assert svg.lstrip().startswith("<svg") or svg.lstrip().startswith("<?xml")
    return root


def panel_kind(report: Report) -> str:
    root = svg_root(report)
    groups = [e for e in root.iter() if _local(e.tag) == "g" and "data-cell" in e.attrib]
    rects = cell_rects(root)
    if groups and not rects:
        return "forest"
    assert rects and not groups, "a panel is either rows or rects"
    return "strip" if len({r.attrib["y"] for r in rects}) == 1 else "heatmap"


# ---------- text helpers ----------


def html_text(html: str) -> str:
    # LS retrofit, 2026-09-25 (local serve pass, Phase C, ruled on Session B's finding): the inline figure's honesty
    # lines wrap (ruling 2 of 2026-09-22), continuation lines carrying ``data-wrap="1"``; each is joined back onto
    # the line before with one space, the way ``texts()`` joins them, so a line reads as rendered whatever the box width.
    html = re.sub(r'</text>\s*<text[^>]*\bdata-wrap="1"[^>]*>', " ", html)
    return html_unescape(re.sub(r"<[^>]+>", " ", html))


def visible_texts(report: Report | MultiReport | SurvivalReport) -> tuple[str, str, str]:
    """(markdown, svg text content, html text content)."""
    return (
        report.to_markdown(),
        "\n".join(texts(svg_root(report))),
        html_text(report.to_html()),
    )


def caption(rep: MultiReport, event: str) -> str:
    panel = rep.panels[event]
    return f"{event}: {panel.n_safer} safer, {panel.n_worse} worse"


def _sections(lines: list[str], events: Sequence[str], starts: list[int]) -> dict[str, str]:
    assert starts == sorted(starts), "panels out of order"
    bounds = [*starts, len(lines)]
    return {e: "\n".join(lines[s:t]) for e, s, t in zip(events, bounds[:-1], bounds[1:], strict=True)}


def panel_sections(md: str, rep: MultiReport) -> dict[str, str]:
    """Markdown from each panel's caption line to the next caption (the last runs to the end)."""
    lines = md.splitlines()
    headline_first = rep.headline.splitlines()[0]
    starts = []
    for e in rep.events:
        cap = caption(rep, e)
        hits = [i for i, line in enumerate(lines) if cap in line and line.strip() != headline_first]
        assert hits, f"no caption line for {e!r}: {cap!r}"
        starts.append(hits[0])
    # PF4 (PF4.3): the report gains a section after the panels whose share table repeats every
    # condition's coordinates, so the last panel runs to the next heading rather than to the end.
    ends = [i for i, line in enumerate(lines) if i > starts[-1] and line.startswith("## ")]
    return _sections(lines[: ends[0]] if ends else lines, rep.events, starts)


def survival_sections(md: str, rep: SurvivalReport) -> dict[str, str]:
    """Survival panels have no safer/worse caption; each starts at a Markdown heading naming
    the event (the first heading line containing the event name as a whole word)."""
    lines = md.splitlines()
    starts = []
    for e in rep.events:
        hits = [
            i for i, line in enumerate(lines)
            if line.startswith("#") and re.search(rf"\b{re.escape(e)}\b", line)
        ]
        assert hits, f"no heading names panel {e!r}"
        starts.append(hits[0])
    return _sections(lines, rep.events, starts)


def worst_rows(md: str, coord_words: Sequence[str]) -> list[str]:
    rows = []
    for line in md.splitlines():
        if line.startswith("|") and not set(line.strip()) <= set("|-: "):
            if any(tok in line for tok in coord_words):
                rows.append(line)
    return rows


def table_order(md: str, coord_words: Sequence[str]) -> list[str]:
    order = []
    for row in worst_rows(md, coord_words):
        for w in coord_words:
            if w in row:
                order.append(w)
                break
    return order


def numbers_in(text: str) -> list[float]:
    return [float(m) for m in NUMBER_RE.findall(HASH_RE.sub(" ", text))]


def honesty_lines(report: Report) -> tuple[str, str]:
    lines = report.honesty.splitlines()
    assert len(lines) == 2, report.honesty
    return lines[0], lines[1]


def printed_coords(coords_text: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in coords_text.split(", "))


def coords_match(report: Report, cell: Cell, printed: dict[str, str]) -> bool:
    axes = [report.spec.x_axis] + ([report.spec.y_axis] if report.spec.y_axis else [])
    if set(printed) != set(axes):
        return False
    for axis, value in zip(axes, cell.coords, strict=True):
        shown = printed[axis]
        try:
            if not math.isclose(float(shown), float(value)):
                return False
        except (TypeError, ValueError):
            if shown != str(value):
                return False
    return True


def named_cell(report: Report, coords_text: str) -> Cell:
    printed = printed_coords(coords_text)
    matches = [c for c in report.cells if c.present and coords_match(report, c, printed)]
    assert len(matches) == 1, (coords_text, matches)
    return matches[0]


def present_cells(report: Report) -> list[Cell]:
    return [c for c in report.cells if c.present]


def headline_order(multi: MultiDiffResult) -> tuple[str, ...]:
    return tuple(m[0] for m in HEADLINE_EVENT_RE.findall(multi.headline().splitlines()[0]))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _shuffled(cells: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    order = list(range(len(cells)))
    for k in range(len(order) - 1, 0, -1):
        swap = (seed * 31 + k * 17) % (k + 1)
        order[k], order[swap] = order[swap], order[k]
    return [cells[i] for i in order]


# ---------- raw-frame factory for the survival report ----------


def raw_frame(cells: dict[tuple[str, float], list[tuple[str, float]]], *, horizon: float) -> pd.DataFrame:
    """Store.read()-shaped frame from {(task, rate): [(outcome, t), ...]} with M4's columns."""
    records = []
    for (task, rate), rows in cells.items():
        config = {"task": task, "rate": rate}
        h = config_hash(config)
        for i, (outcome, t) in enumerate(rows):
            records.append(
                {
                    "run_id": "r",
                    "config_hash": h,
                    "config": dict(config),
                    "seed": 1000 + i,
                    "replicate_index": i,
                    "outcome": outcome,
                    "t": float(t),
                    "horizon": float(horizon),
                    "confidence": None,
                    "meta": {},
                    "error": None,
                    "wall_time": 0.0,
                    "backend_meta": {},
                }
            )
    df = pd.DataFrame.from_records(records, columns=M4_COLUMNS)
    df["t"] = df["t"].astype(float)
    df["horizon"] = df["horizon"].astype(float)
    df["outcome"] = df["outcome"].astype(object)
    return df


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def golden_frames(lattice_store: Store) -> dict[str, Any]:
    return {
        "raw_a": lattice_store.read(lattice.RUN_A),
        "raw_b": lattice_store.read(lattice.RUN_B),
        "ma": lattice_store.manifest(lattice.RUN_A),
        "mb": lattice_store.manifest(lattice.RUN_B),
    }


@pytest.fixture(scope="module")
def golden_diff(golden_frames: dict[str, Any]) -> DiffResult:
    return diff(
        censor(golden_frames["raw_a"], lattice.EVENT), censor(golden_frames["raw_b"], lattice.EVENT),
        event=lattice.EVENT, method="fisher_bh", q=0.05,
        manifest_a=golden_frames["ma"], manifest_b=golden_frames["mb"],
    )


@pytest.fixture(scope="module")
def golden_report(golden_diff: DiffResult) -> Report:
    return build_report(
        golden_diff, ReportSpec(title=LATTICE_TITLE, x_axis=lattice.Y, y_axis=lattice.X, theme="dark")
    )


@pytest.fixture(scope="module")
def golden_multi(golden_frames: dict[str, Any]) -> MultiDiffResult:
    return multi_diff(
        golden_frames["raw_a"], golden_frames["raw_b"], events=[lattice.EVENT, lattice.OTHER],
        manifest_a=golden_frames["ma"], manifest_b=golden_frames["mb"],
    )


def _sweep(store: Path, target: str) -> str:
    out, err = StringIO(), StringIO()
    argv = ["--store", str(store), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", target, "--yes",
            "--salt", QUICKSTART_SALT]
    # A sweep no longer ends with a run_id line (its end is a verdict line, front-door spec section
    # 5.3), so the new run is the one the store gained.
    before = set(Store(store).runs())
    code = cli.main(argv, stdout=out, stderr=err, stdin=StringIO())
    assert code == 0, err.getvalue() + out.getvalue()
    added = set(Store(store).runs()) - before
    assert len(added) == 1, out.getvalue()
    return added.pop()


@pytest.fixture(scope="module")
def quickstart(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The two S10 quickstart runs under a fixed salt, diffed with inferred events."""
    root = tmp_path_factory.mktemp("quickstart-store")
    a = _sweep(root, MOCK_ROLLOUT)
    b = _sweep(root, MOCK_PATCHED)
    store = Store(root)
    ma, mb = store.manifest(a), store.manifest(b)
    multi = multi_diff(store.read(a), store.read(b), manifest_a=ma, manifest_b=mb)
    return {"multi": multi, "ma": ma, "mb": mb}


# ---------- B1: single-event output unchanged except the honesty block ----------


def _is_honesty_line(line: str) -> bool:
    return "Worst-powered" in line or HONESTY_NONE in line


def strip_honesty(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not _is_honesty_line(line))


def as_0_0_1_wrote_it(text: str) -> str:
    """PF0 (Q4, section 2.3): the one line of a rendered report the rename changes is the version
    in its provenance list. First assert it is there as the rename writes it -- one ``Prove version:``
    line and no ``proofload version:`` -- then put it back as 0.0.1 wrote it and drop any separate
    ``written by proofload`` line, so every other byte is still compared."""
    found = re.findall(r"(?m)^- Prove version: [^\n]*$", text)
    assert len(found) == 1 and "proofload version:" not in text, found
    text = re.sub(r"(?m)^- Prove version: [^\n]*$", "- proofload version: 0.0.1", text)
    return re.sub(r"(?m)^- [^\n]*written by proofload[^\n]*\n", "", text)


def lattice_headline() -> str:
    """The single-event headline the lattice's references give: Fisher + BH over the design's counts."""
    lower, higher = lattice.directions(lattice.fisher())
    return f"{lower} of {lattice.CELLS} cells safer, {higher} worse (fisher_bh, BH q<0.05, unpaired)."


def test_b1_the_lattice_record_is_intact_and_the_report_carries_its_headline_on_every_surface(golden_report: Report) -> None:
    """Lattice port: B1's record is no longer a file frozen on disk but the generated lattice pair
    and its references. The pair is the one the generator wrote (every file by digest); its
    references give a headline in S8's form; and the build's three surfaces exist and carry it --
    the Markdown with that headline once and the honesty block's two lines, the SVG parsing."""
    assert lattice.intact()
    headline = lattice_headline()
    assert headline == "22 of 72 cells safer, 0 worse (fisher_bh, BH q<0.05, unpaired)."
    md = golden_report.to_markdown()
    assert md.splitlines().count(headline) == 1
    assert sum(_is_honesty_line(line) for line in md.splitlines()) == 2
    ET.fromstring(golden_report.to_svg())
    assert headline in html_unescape(golden_report.to_html())


#: PF4 (PF4.15): the worst-cells table's width and its MDE column.
_MDE_COLUMN, _TABLE_WIDTH = 9, 10


def _set_aside_mde(text: str) -> tuple[str, list[tuple[str, str]]]:
    """PF4 (PF4.15): the text with every worst-cells row's MDE cell blanked, and each row's
    coordinates (``x=.., y=..``, the report's axes) with the MDE cell it held, so every other byte is
    still compared and each limit is checked against its condition."""
    out, held = [], []
    header: list[str] = []
    for line in text.splitlines():
        cells = line[1:-1].split("|") if line.startswith("|") and line.endswith("|") else []
        if len(cells) == _TABLE_WIDTH and cells[_MDE_COLUMN].strip() == "MDE":
            header = [c.strip() for c in cells]
        elif len(cells) == _TABLE_WIDTH and header and not set(line) <= set("|-: "):
            coords = f"{header[0]}={cells[0].strip()}, {header[1]}={cells[1].strip()}"
            held.append((coords, cells[_MDE_COLUMN].strip()))
            cells[_MDE_COLUMN] = " <limit> "
            line = "|" + "|".join(cells) + "|"
        out.append(line)
    return "\n".join(out), held


#: B1. What S8's record printed in each place, read off the lattice's design and its references,
#: and the numbers only Prove computes on it, re-measured on main's build (lattice port): the
#: largest detection limit over the conditions (Methods row) and every condition's printed limit
#: where it has one, by ``(gain, load)``. The rest print a note: the ceiling note at a baseline that
#: had the event in every run, the none-detectable note where even the whole headroom is not caught.
LATTICE_MAX_MDE_PP = "34pp"
LATTICE_LIMITS = {
    (0.1, 20.0): "23pp", (0.1, 30.0): "26pp", (0.2, 20.0): "25pp", (0.2, 30.0): "29pp", (0.3, 10.0): "23pp",
    (0.3, 20.0): "26pp", (0.3, 30.0): "30pp", (0.4, 10.0): "26pp", (0.4, 20.0): "28pp", (0.4, 30.0): "30pp",
    (0.5, 10.0): "29pp", (0.5, 20.0): "29pp", (0.5, 30.0): "31pp", (0.6, 10.0): "31pp", (0.6, 20.0): "30pp",
    (0.6, 30.0): "31pp", (0.7, 10.0): "32pp", (0.7, 20.0): "31pp", (0.7, 30.0): "32pp", (0.8, 10.0): "33pp",
    (0.8, 20.0): "32pp", (0.8, 30.0): "32pp", (0.9, 10.0): "34pp", (0.9, 20.0): "33pp", (0.9, 30.0): "33pp",
    (1.0, 10.0): "34pp", (1.0, 20.0): "33pp", (1.0, 30.0): "34pp", (1.1, 10.0): "23pp", (1.1, 20.0): "31pp",
    (1.1, 30.0): "33pp", (1.2, 10.0): "23pp", (1.2, 20.0): "34pp", (1.2, 30.0): "34pp",
}
#: B1. The lattice's one condition whose whole headroom is not detectable (baseline 26 of 32).
LATTICE_NONE_DETECTABLE = {(0.2, 10.0)}
#: B1. The epistemic fence, as S8 printed it.
FENCE = (
    "> This is empirical evidence under a stated test envelope, not formal verification. Cells outside "
    "the envelope were not tested; cells inside it were tested at the stated replicate count and can only "
    "detect effects at or above the reported MDE."
)


def _sig3(x: float) -> str:
    """The report's p and q format (M7's spec): three significant figures, scientific below 1e-3."""
    if x == 0:
        return "0"
    return format(x, ".2e") if x < 1e-3 else format(x, ".3g")


def lattice_worst_rows(top: int = 10) -> list[tuple[tuple[float, float], str, str]]:
    """The first ``top`` rows of the worst-cells table from the references: the conditions in
    descending change and then by key (I19's order), each as ``((load, gain), its row with the MDE
    cell set aside, its key)``. The change, both shares, p, q and the verdict are the reference's."""
    reference = lattice.fisher()
    words = {"lower": "safer", "higher": "worse", "unchanged": "unchanged"}
    ranked = sorted(reference.values(), key=lambda r: (-r["delta"], r["config_hash"]))[:top]
    out = []
    for r in ranked:
        load, gain = r["config"][lattice.Y], r["config"][lattice.X]
        row = (
            f"| {load:g} | {gain:g} | {r['n_a']}/{r['n_b']} | {_pp1(r['events_a'] / r['n_a'])} | "
            f"{_pp1(r['events_b'] / r['n_b'])} | {_pp1(r['delta'])} | {_sig3(r['p'])} | {_sig3(r['q'])} | "
            f"{words[r['direction']]} | <limit> |"
        )
        out.append(((load, gain), row, r["config_hash"]))
    return out


def limit_kind(gain: float, load: float) -> str:
    """What a condition's MDE cell must hold, from the design and an exact reference, never from
    Prove: ``ceiling`` where the baseline had the event in all 32 runs; ``none`` where even a rise
    to 32 of 32 is caught with less than the target power by a two-sided Fisher test at 0.05
    (``test_pf4_stats``'s exact power, the binomial over every table); ``limit`` otherwise."""
    cell = lattice.cell_at(gain, load)
    if cell.tripped_a == lattice.N:
        return "ceiling"
    p_a = cell.tripped_a / lattice.N
    power = float(_ref_fisher_power(p_a, lattice.N, lattice.N, 0.05, np.array([1.0 - p_a]), True)[0])
    return "none" if power < POWER else "limit"


def check_limit(report: Report, notes: dict[str, Any], coords: str, after: str, gain: float, load: float, key: str) -> str:
    """One row's MDE cell against its condition's kind; returns the kind."""
    cell = named_cell(report, coords)
    assert cell.config_hash == key, (coords, key)
    kind = limit_kind(gain, load)
    if kind == "limit":
        assert not isinstance(notes[key], str), (coords, notes[key])
        assert after == LATTICE_LIMITS[(gain, load)] == f"{_pp0(cell.mde)}pp", (coords, after)
    elif kind == "ceiling":
        assert isinstance(notes[key], str) and math.isnan(cell.mde), (coords, notes[key])
        assert not re.search(r"\d+pp|(?i:nan)", after) and "ceiling" in after and "none detectable" not in after, (coords, after)
    else:
        assert isinstance(notes[key], str) and not math.isnan(cell.mde), (coords, notes[key])
        assert not re.search(r"\d+pp|(?i:nan)", after) and "none detectable" in after and "ceiling" not in after, (coords, after)
    return kind


def test_b1_markdown_matches_frozen_s8_output_outside_the_honesty_block(golden_report: Report, golden_diff: DiffResult) -> None:
    """S8's record was a frozen file; on the lattice pair the same layout is built here from the
    references and compared line for line outside the honesty block (B2 owns its two lines). What
    P-1 moved in S8's record is written the way it reads now: the headline's last token states the
    requested method's pairing (ADR-052, C1), the Methods row's second column reads ``unpaired``
    for ``fisher_bh``, the provenance list carries ``seed identity match`` and ``unpaired
    analysis`` where ``paired`` stood, and (truncation surfacing, 2026-09-20) ``episodes censored
    at horizon`` where ``truncated`` stood. PF4 (PF4.15): every MDE cell is set aside and each
    row's limit checked against its condition (``limit_kind``): the re-measured limit where it has
    one, the ceiling words at a 32-of-32 baseline, the none-detectable words where even the whole
    headroom is not caught. The default top ten holds limits and ceilings only, so the same report
    is rendered again with every condition in the table and every row checked the same way, the
    lattice's one none-detectable condition among them."""
    lower, higher = lattice.directions(lattice.fisher())
    worst = lattice_worst_rows()
    expected = [
        f"# {LATTICE_TITLE}", "", lattice_headline(), "", "![delta heatmap](heatmap.svg)", "",
        "## Worst cells", "",
        f"| {lattice.Y} | {lattice.X} | n (a/b) | rate_a (pp) | rate_b (pp) | delta (pp) | p | q | verdict | MDE |",
        "|---|---|---|---|---|---|---|---|---|---|",
        *(row for _, row, _ in worst),
        "", "## Methods", "",
        "| method | pairing | safer | worse | unchanged | max MDE | q |",
        "|---|---|---|---|---|---|---|",
        f"| fisher_bh | unpaired | {lower} | {higher} | {lattice.CELLS - lower - higher} | {LATTICE_MAX_MDE_PP} | 0.05 |",
        "", "## Honesty", "", "", FENCE, "", "## Provenance", "",
        f"- event: {lattice.EVENT}", f"- t unit: {lattice.T_UNIT}", f"- horizon: {lattice.HORIZON:g}",
        "- method: fisher_bh", "- seed identity match: true", "- unpaired analysis: true", "- q: 0.05",
        "- n not comparable: 0", "- dropped a: 0", "- dropped b: 0", "- episodes censored at horizon: 0",
        "- n absent: 0", "- proofload version: 0.0.1",
    ]
    # The record's own facts, pinned so a drift of the generator or of the references is seen too.
    assert expected[2] == "22 of 72 cells safer, 0 worse (fisher_bh, BH q<0.05, unpaired)."
    assert [coords for coords, _, _ in worst][:2] == [(20.0, 1.1), (30.0, 0.9)]
    kinds = {(c.gain, c.load): limit_kind(c.gain, c.load) for c in lattice.design_cells()}
    assert {k for k, v in kinds.items() if v == "none"} == LATTICE_NONE_DETECTABLE
    assert {k for k, v in kinds.items() if v == "limit"} == set(LATTICE_LIMITS)
    assert sum(v == "ceiling" for v in kinds.values()) == 37
    assert LATTICE_MAX_MDE_PP == f"{_pp0(golden_diff.max_mde)}pp"
    now, printed = _set_aside_mde(as_0_0_1_wrote_it(golden_report.to_markdown()))
    assert strip_honesty(now).splitlines() == expected
    assert len(printed) == len(worst) == golden_report.spec.top_n
    notes = dict(zip(golden_diff.cells["config_hash"], golden_diff.cells["mde_note"], strict=True))
    seen = [check_limit(golden_report, notes, coords, after, gain, load, key)
            for ((load, gain), _, key), (coords, after) in zip(worst, printed, strict=True)]
    assert seen.count("ceiling") == 8 and seen.count("limit") == 2, seen

    # Every condition in the table: the same rows from the references, every MDE cell checked.
    full = build_report(golden_diff, ReportSpec(title=LATTICE_TITLE, x_axis=lattice.Y, y_axis=lattice.X, theme="dark", top_n=lattice.CELLS))
    every = lattice_worst_rows(lattice.CELLS)
    assert every[: len(worst)] == worst
    full_now, full_printed = _set_aside_mde(full.to_markdown())
    lines = full_now.splitlines()
    first = lines.index(expected[8]) + 2
    assert lines[first : first + len(every) + 1] == [row for _, row, _ in every] + [""]
    assert len(full_printed) == len(every) == lattice.CELLS
    seen = [check_limit(full, notes, coords, after, gain, load, key)
            for ((load, gain), _, key), (coords, after) in zip(every, full_printed, strict=True)]
    assert (seen.count("limit"), seen.count("ceiling"), seen.count("none")) == (34, 37, 1), seen


# ---------- B2: honesty block, both lines ----------


def _check_honesty(report: Report, *, max_mde: float, max_mde_unchanged: float, panel: bool = False) -> None:
    first, second = honesty_lines(report)
    if math.isnan(max_mde_unchanged) and panel:
        # PF4 (PF4.17): with no unchanged condition, the two-run report's honesty line says how many
        # conditions were compared (and how many were not, when any were not), and never that every
        # cell moved.
        compared = sum(c.present for c in report.cells)
        assert re.search(rf"(?<![\d.]){compared}(?![\d.])", first) and "compared" in first, first
        assert "every" not in first.lower() and first != HONESTY_NONE, first
        if report.n_absent:
            assert re.search(rf"(?<![\d.]){report.n_absent}(?![\d.])", first), first
    elif math.isnan(max_mde_unchanged):
        assert first == HONESTY_NONE
    else:
        m = HONESTY_FIRST_RE.match(first)
        assert m, first
        coords_text, n_a, n_b, mde_pp, worse = m.groups()
        cell = named_cell(report, coords_text)
        assert cell.verdict == "unchanged"
        assert cell.mde == max_mde_unchanged
        assert (int(n_a), int(n_b)) == (cell.n_a, cell.n_b)
        assert mde_pp == _pp0(max_mde_unchanged)
        assert int(worse) == report.n_worse
    m2 = HONESTY_OVERALL_RE.match(second)
    assert m2, second
    overall_pp, overall_coords = m2.groups()
    assert overall_pp == _pp0(max_mde)
    assert named_cell(report, overall_coords).mde == max_mde
    md, svg_text, html = visible_texts(report)
    for text in (md, svg_text, html):
        assert first in text, (first, text[:200])
        assert second in text, (second, text[:200])


def test_b2_fixture_first_line_names_an_unchanged_cell_at_max_mde_unchanged(
    golden_report: Report, golden_diff: DiffResult
) -> None:
    assert not math.isnan(golden_diff.max_mde_unchanged)
    _check_honesty(
        golden_report, max_mde=golden_diff.max_mde, max_mde_unchanged=golden_diff.max_mde_unchanged
    )


def test_b2_first_line_uses_max_mde_unchanged_not_max_mde() -> None:
    d = make_diff([
        make_cell({"mu": 0.1, "push": 10}, delta=-0.3, q=1e-3, verdict="safer", mde=0.5),
        make_cell({"mu": 0.1, "push": 20}, delta=0.0, q=0.9, verdict="unchanged", mde=0.2, n_a=40, n_b=41),
        make_cell({"mu": 0.5, "push": 10}, delta=0.01, q=0.8, verdict="unchanged", mde=0.1),
        make_cell({"mu": 0.5, "push": 20}, delta=0.3, q=1e-3, verdict="worse", mde=0.45),
    ])
    assert d.max_mde == 0.5 and d.max_mde_unchanged == 0.2
    report = build_report(d, spec2())
    first, second = honesty_lines(report)
    assert "20pp" in first and "n=40/41" in first and '"1 worse"' in first
    assert second.startswith("Worst-powered cell overall: 50pp (")
    _check_honesty(report, max_mde=0.5, max_mde_unchanged=0.2)


def test_b2_nan_max_mde_unchanged_prints_the_fixed_sentence() -> None:
    d = make_diff([
        make_cell({"mu": 0.1, "push": 10}, delta=-0.3, q=1e-3, verdict="safer", mde=0.3),
        make_cell({"mu": 0.1, "push": 20}, delta=0.2, q=1e-3, verdict="worse", mde=0.25),
        make_cell({"mu": 0.5, "push": 10}, delta=-0.4, q=1e-3, verdict="safer", mde=0.34),
        make_cell({"mu": 0.5, "push": 20}, delta=0.5, q=1e-3, verdict="worse", mde=0.2),
    ])
    assert math.isnan(d.max_mde_unchanged) and d.max_mde_unchanged_cell is None
    report = build_report(d, spec2())
    first, second = honesty_lines(report)
    assert first == HONESTY_NONE
    assert second.startswith("Worst-powered cell overall: 34pp (")
    _check_honesty(report, max_mde=0.34, max_mde_unchanged=math.nan)


# ---------- B3: worst-cells tiebreak (multi-report panels) ----------


def _tiebreak_key(row: Any) -> tuple:
    return (-row.delta, row.q, row.mde, row.config_hash)


def _ten_zero_cells(qs: Sequence[float], mdes: Sequence[float]) -> list[dict[str, Any]]:
    return [
        make_cell({"task": w}, delta=0.0, q=q, mde=m, verdict="unchanged")
        for w, q, m in zip(WORDS, qs, mdes, strict=True)
    ]


# PF4 (PF4.20): the B3 panels are found by their safer/worse captions, which a reader sees only for
# an event whose kind is known, so these hand-built events are failure events.


def _panel_table_order(multi: MultiDiffResult, event: str) -> list[str]:
    rep = build_multi_report(multi, ReportSpec(title="t", x_axis="task", top_n=10, forest="never"))
    return table_order(panel_sections(rep.to_markdown(), rep)[event], WORDS)


def test_b3_panel_rows_with_equal_delta_follow_q_then_mde_then_hash() -> None:
    qs = [0.5, 0.2, 0.2, 0.9, 0.2, 0.1, 0.1, 0.2, 0.9, 0.5]
    mdes = [0.3, 0.2, 0.1, 0.3, 0.1, 0.4, 0.4, 0.1, 0.2, 0.3]
    cells = _ten_zero_cells(qs, mdes)
    ev = make_event("alpha", cells, kind=FAILURE)
    expected = [r.config["task"] for r in sorted(ev.cells.itertuples(index=False), key=_tiebreak_key)]
    assert len(set(expected)) == 10
    assert _panel_table_order(make_multi([ev]), "alpha") == expected
    shuffled = make_event("alpha", _shuffled(cells, 7), kind=FAILURE)
    assert _panel_table_order(make_multi([shuffled]), "alpha") == expected


def test_b3_delta_stays_the_primary_key_in_each_panel() -> None:
    deltas = [0.2, -0.1, 0.2, 0.05, 0.2, -0.3, 0.0, 0.0, 0.2, -0.1]
    cells = [
        make_cell({"task": w}, delta=dl, q=0.2 * ((i * 7) % 5 + 1) / 6, mde=0.1 + 0.05 * (i % 3),
                  verdict=sign_verdict(i, 0, dl) if abs(dl) >= 0.2 else "unchanged")
        for i, (w, dl) in enumerate(zip(WORDS, deltas, strict=True))
    ]
    ev = make_event("alpha", cells, kind=FAILURE)
    other = make_event("beta", [dict(c, delta=0.0, verdict="unchanged") for c in cells], kind=FAILURE)
    expected = [r.config["task"] for r in sorted(ev.cells.itertuples(index=False), key=_tiebreak_key)]
    assert _panel_table_order(make_multi([ev, other]), "alpha") == expected
    assert _panel_table_order(make_multi([make_event("alpha", _shuffled(cells, 3), kind=FAILURE), other]), "alpha") == expected


def test_b3_hypothesis_ten_zero_delta_rows_order_by_q_mde_hash_under_shuffling() -> None:
    @settings(max_examples=40, deadline=None)
    @given(
        qs=st.lists(st.sampled_from([0.1, 0.2, 0.3, 0.6]), min_size=10, max_size=10),
        mdes=st.lists(st.sampled_from([0.05, 0.1, 0.2]), min_size=10, max_size=10),
        seed=st.integers(min_value=0, max_value=10**6),
    )
    def check(qs: list[float], mdes: list[float], seed: int) -> None:
        cells = _ten_zero_cells(qs, mdes)
        ev = make_event("alpha", cells, kind=FAILURE)
        expected = [
            r.config["task"] for r in sorted(ev.cells.itertuples(index=False), key=_tiebreak_key)
        ]
        spec = ReportSpec(title="t", x_axis="task", top_n=10, forest="never")
        straight = build_multi_report(make_multi([ev]), spec)
        shuffled = build_multi_report(make_multi([make_event("alpha", _shuffled(cells, seed), kind=FAILURE)]), spec)
        assert table_order(panel_sections(straight.to_markdown(), straight)["alpha"], WORDS) == expected
        assert shuffled.to_markdown() == straight.to_markdown()
        assert shuffled.to_svg() == straight.to_svg()
        assert shuffled.to_html() == straight.to_html()

    check()


# ---------- B4: saturation ----------


def _saturation_diff() -> tuple[DiffResult, set[str]]:
    cells = [
        make_cell({"mu": 1, "push": 1}, rate_a=0.0, rate_b=0.0, delta=0.0, verdict="unchanged"),
        make_cell({"mu": 1, "push": 2}, rate_a=1.0, rate_b=1.0, delta=0.0, verdict="unchanged"),
        make_cell({"mu": 2, "push": 1}, rate_a=0.5, rate_b=0.5, delta=0.0, verdict="unchanged"),
        make_cell({"mu": 2, "push": 2}, rate_a=0.3, delta=0.2, q=0.01, verdict="worse"),
        make_cell({"mu": 3, "push": 1}, rate_a=0.0, rate_b=0.1, delta=0.1, verdict="unchanged"),
        make_cell({"mu": 3, "push": 2}, rate_a=1.0, rate_b=0.9, delta=-0.1, verdict="unchanged"),
    ]
    saturated = {config_hash({"mu": 1, "push": 1}), config_hash({"mu": 1, "push": 2})}
    return make_diff(cells), saturated


def _check_saturation(root: ET.Element, saturated: set[str], theme: str) -> None:
    rects = cell_rects(root)
    flagged = {r.attrib["data-cell"] for r in rects if r.attrib.get("data-sat") == "1"}
    assert flagged == saturated
    for r in rects:
        if r.attrib["data-cell"] in saturated:
            assert r.attrib["fill"] == SATURATED_FILL[theme], r.attrib
            assert "data-sig" not in r.attrib
        else:
            assert "data-sat" not in r.attrib, r.attrib
    for e in root.iter():
        if "data-sat" in e.attrib:
            assert "data-cell" in e.attrib, "data-sat only on cell carriers"
    has_legend = any(SATURATION_LEGEND in t for t in texts(root))
    assert has_legend == bool(saturated)


def test_b4_saturated_fill_constant_is_public_and_hex() -> None:
    assert set(SATURATED_FILL) == {"dark", "light"}
    assert all(HEX_RE.match(v) for v in SATURATED_FILL.values())


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_b4_saturated_cells_carry_data_sat_and_the_saturated_fill(theme: str) -> None:
    d, saturated = _saturation_diff()
    _check_saturation(svg_root(build_report(d, spec2(theme=theme))), saturated, theme)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_b4_no_saturated_cell_means_no_marker_and_no_legend_entry(theme: str) -> None:
    d = make_diff(grid_cells([0.1, 0.2], [10, 20], delta_fn=lambda i, j: 0.1 * (i - j), rate_a=0.5))
    _check_saturation(svg_root(build_report(d, spec2(theme=theme))), set(), theme)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_b4_saturation_applies_per_panel_in_the_multi_report(theme: str) -> None:
    d, saturated = _saturation_diff()
    plain = grid_cells([1, 2, 3], [1, 2], delta_fn=lambda i, j: 0.05 * (i - j), rate_a=0.5)
    multi = make_multi([
        make_event("alpha", [dict(r) for r in d.cells.to_dict(orient="records")]),
        make_event("beta", plain),
    ])
    rep = build_multi_report(multi, spec2(theme=theme))
    groups = {g.attrib["data-panel"]: g for g in panel_groups(svg_root(rep))}
    _check_saturation(groups["alpha"], saturated, theme)
    _check_saturation(groups["beta"], set(), theme)
    _check_saturation(svg_root(rep.panels["alpha"]), saturated, theme)


def test_b4_fixture_data_sat_count_equals_cells_with_equal_extreme_event_counts(
    golden_report: Report, golden_diff: DiffResult
) -> None:
    c = golden_diff.cells
    expected = set(c.loc[(c["events_a"] == c["events_b"]) & c["events_a"].isin([0, 32]), "config_hash"])
    # The lattice's saturated conditions by design: every ceiling condition at load 40, 50 and 100 and the
    # two that never trip at load 10.
    designed = {r["config_hash"] for r in lattice.counts() if r["events_a"] == r["events_b"] and r["events_a"] in (0, lattice.N)}
    assert expected == designed and len(expected) == 37, "the lattice fixture has saturated cells"
    root = svg_root(golden_report)
    flagged = {r.attrib["data-cell"] for r in cell_rects(root) if r.attrib.get("data-sat") == "1"}
    assert len(flagged) == len(expected)
    assert flagged == expected
    _check_saturation(root, expected, "dark")


# ---------- B5: shared bound ----------


def _bound_ok(bound: float, biggest: float, color_max: float | None) -> None:
    if color_max is not None:
        assert bound == color_max
        return
    assert bound >= biggest - 1e-12
    assert bound <= biggest + 0.05 + 1e-12
    assert abs(bound * 20 - round(bound * 20)) < 1e-9, bound
    assert bound >= 0.05


def _strip_multi(a_deltas: Sequence[float], b_deltas: Sequence[float], **kw: Any) -> MultiDiffResult:
    xs = list(range(max(len(a_deltas), len(b_deltas))))
    alpha = make_event("alpha", grid_cells(
        xs[: len(a_deltas)], None, x_key="k",
        delta_fn=lambda i, j: a_deltas[i], verdict_fn=lambda i, j, dl: sign_verdict(i, j, dl) if abs(dl) > 0.3 else "unchanged",
    ))
    beta = make_event("beta", grid_cells(
        xs[: len(b_deltas)], None, x_key="k",
        delta_fn=lambda i, j: b_deltas[i], verdict_fn=lambda i, j, dl: sign_verdict(i, j, dl) if abs(dl) > 0.3 else "unchanged",
    ))
    return make_multi([alpha, beta], **kw)


def test_b5_two_events_with_different_ranges_share_one_bound_and_one_ramp() -> None:
    multi = _strip_multi([0.05, 0.1, -0.12, 0.12], [0.05, 0.3, -0.43, 0.1])
    rep = build_multi_report(multi, ReportSpec(title="t", x_axis="k"))
    assert rep.bound == 0.45
    fills = {e: fills_by_hash(svg_root(rep.panels[e])) for e in rep.events}
    h = lambda k: config_hash({"k": k})  # noqa: E731
    assert fills["alpha"][h(0)] == fills["beta"][h(0)]  # +0.05 in both
    assert fills["alpha"][h(1)] == fills["beta"][h(3)]  # +0.10 in both
    assert fills["alpha"][h(1)] != fills["alpha"][h(0)]
    stacked = {g.attrib["data-panel"]: fills_by_hash(g) for g in panel_groups(svg_root(rep))}
    assert stacked == fills
    capped = build_multi_report(multi, ReportSpec(title="t", x_axis="k", color_max=0.2))
    assert capped.bound == 0.2
    alone = build_report(
        make_diff([dict(r) for r in multi.by_event["alpha"].cells.to_dict(orient="records")]),
        ReportSpec(title="t", x_axis="k"),
    )
    assert fills_by_hash(svg_root(alone))[h(1)] != fills["alpha"][h(1)], "panel bound differs from the event's own"


def test_b5_hypothesis_identical_delta_gives_identical_fill_across_panels() -> None:
    @settings(max_examples=40, deadline=None)
    @given(
        common=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
        a_rest=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), min_size=1, max_size=5),
        b_rest=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), min_size=1, max_size=5),
        color_max=st.one_of(st.none(), st.floats(min_value=0.05, max_value=1.0, allow_nan=False)),
    )
    def check(common: float, a_rest: list[float], b_rest: list[float], color_max: float | None) -> None:
        multi = _strip_multi([common, *a_rest], [common, *b_rest])
        rep = build_multi_report(multi, ReportSpec(title="t", x_axis="k", color_max=color_max))
        biggest = max(abs(x) for x in (common, *a_rest, *b_rest))
        _bound_ok(rep.bound, biggest, color_max)
        h0 = config_hash({"k": 0})
        assert fills_by_hash(svg_root(rep.panels["alpha"]))[h0] == fills_by_hash(svg_root(rep.panels["beta"]))[h0]

    check()


# ---------- B6: panel order and captions ----------


def _three_event_multi(*, kind: str | None = None) -> MultiDiffResult:
    xs, ys = [0.1, 0.2, 0.3], [10, 20]
    # tested order alpha, beta, gamma; headline order is gamma (2 worse), beta (1 worse, 2 safer), alpha
    alpha = make_event("alpha", grid_cells(xs, ys, delta_fn=lambda i, j: -0.2 if (i, j) == (0, 0) else 0.0,
                                           verdict_fn=sign_verdict), kind=kind)
    beta = make_event("beta", grid_cells(xs, ys, delta_fn=lambda i, j: {(0, 0): -0.2, (1, 0): -0.3, (2, 1): 0.2}.get((i, j), 0.0),
                                         verdict_fn=sign_verdict), kind=kind)
    gamma = make_event("gamma", grid_cells(xs, ys, delta_fn=lambda i, j: {(0, 1): 0.2, (1, 1): 0.3}.get((i, j), 0.0),
                                           verdict_fn=sign_verdict), kind=kind)
    return make_multi([alpha, beta, gamma])


def test_b6_panel_order_is_headline_order_and_captions_parse_to_counts() -> None:
    # PF4 (PF4.20): the captions and the headline read safer/worse only for an event whose kind is
    # known, so the three hand-built events are failure events.
    multi = _three_event_multi(kind=FAILURE)
    rep = build_multi_report(multi, spec2())
    assert rep.events == headline_order(multi) == ("gamma", "beta", "alpha")
    assert rep.events != multi.events
    assert set(rep.panels) == set(rep.events) and len(rep.panels) == 3
    md, svg_text, html = visible_texts(rep)
    sections = panel_sections(md, rep)
    groups = panel_groups(svg_root(rep))
    assert [g.attrib["data-panel"] for g in groups] == list(rep.events)
    for e, g in zip(rep.events, groups, strict=True):
        ev = multi.by_event[e]
        panel = rep.panels[e]
        assert (panel.n_safer, panel.n_worse, panel.n_unchanged) == (ev.n_safer, ev.n_worse, ev.n_unchanged)
        cap = caption(rep, e)
        m = CAPTION_RE.match(cap)
        assert m and (m.group(1), int(m.group(2)), int(m.group(3))) == (e, ev.n_safer, ev.n_worse)
        assert cap in sections[e].splitlines()[0]
        assert any(cap in t for t in texts(g)), (e, texts(g))
        assert cap in html
    caption_positions = [html.index(caption(rep, e)) for e in rep.events]
    assert caption_positions == sorted(caption_positions)


# ---------- B7: headline and trade line verbatim ----------


def _first_panel_text_index(root: ET.Element) -> int:
    """Index (in document order over <text> elements) of the first text inside a panel group."""
    inside: set[ET.Element] = set()
    for g in panel_groups(root):
        inside.update(e for e in g.iter() if _local(e.tag) == "text")
    all_text = [e for e in root.iter() if _local(e.tag) == "text"]
    return next(i for i, e in enumerate(all_text) if e in inside)


def test_b7_headline_then_trade_line_then_panels_in_all_three_formats() -> None:
    # PF4 (PF4.20): the panel captions read safer/worse only for an event whose kind is known, so
    # the two hand-built events are failure events.
    multi = two_event_multi(kind=FAILURE)
    assert len(multi.trades) == 2 and multi.trade_line() is not None
    rep = build_multi_report(multi, spec2())
    assert rep.headline == multi.headline()
    assert rep.trade_line == multi.trade_line()
    line1, line2 = multi.headline().splitlines()
    trade = multi.trade_line()
    assert trade is not None
    md = rep.to_markdown()
    assert multi.headline() in md
    first_caption = md.index(next(line for line in md.splitlines() if caption(rep, rep.events[0]) in line and line1 not in line))
    assert md.index(multi.headline()) < md.index(trade) < first_caption
    html = html_text(rep.to_html())
    assert html.index(line1) < html.index(line2) < html.index(trade) < html.index(caption(rep, rep.events[0]), html.index(trade))
    root = svg_root(rep)
    tx = texts(root)
    idx = lambda needle: next(i for i, t in enumerate(tx) if needle in t)  # noqa: E731
    assert idx(line1) < idx(line2) < idx(trade) < _first_panel_text_index(root)


def test_b7_trade_line_absent_when_none() -> None:
    plain = make_multi([
        make_event("alpha", grid_cells([0.1, 0.2], [10, 20], delta_fn=lambda i, j: -0.2 * i, verdict_fn=sign_verdict)),
        make_event("beta", grid_cells([0.1, 0.2], [10, 20], delta_fn=lambda i, j: -0.1 * j, verdict_fn=sign_verdict)),
    ])
    assert plain.trade_line() is None
    rep = build_multi_report(plain, spec2())
    assert rep.trade_line is None
    assert rep.headline == plain.headline()
    for text in visible_texts(rep):
        assert TRADE_MARK not in text
        assert plain.headline().splitlines()[0] in text


# ---------- B8: trade marker in every panel ----------


def _traded_hashes(node: ET.Element) -> list[str]:
    return [e.attrib["data-cell"] for e in cell_nodes(node) if e.attrib.get("data-trade") == "1"]


def test_b8_every_traded_cell_is_marked_in_every_panel_and_nothing_else_is() -> None:
    multi = two_event_multi()
    traded = set(multi.trades["config_hash"])
    assert len(traded) == 2
    rep = build_multi_report(multi, spec2())
    groups = panel_groups(svg_root(rep))
    assert len(groups) == 2
    for g in groups:
        marks = _traded_hashes(g)
        assert len(marks) == len(traded) == 2
        assert set(marks) == traded
    for e in rep.events:
        marks = _traded_hashes(svg_root(rep.panels[e]))
        assert len(marks) == 2 and set(marks) == traded
    for e in svg_root(rep).iter():
        if "data-trade" in e.attrib:
            assert "data-cell" in e.attrib and e.attrib["data-cell"] in traded


def test_b8_no_trades_means_no_data_trade_anywhere() -> None:
    multi = make_multi([
        make_event("alpha", grid_cells([0.1, 0.2], [10, 20], delta_fn=lambda i, j: -0.3 * i, verdict_fn=sign_verdict)),
        make_event("beta", grid_cells([0.1, 0.2], [10, 20], delta_fn=lambda i, j: 0.3 if (i, j) == (0, 1) else 0.0, verdict_fn=sign_verdict)),
    ])
    assert len(multi.trades) == 0
    rep = build_multi_report(multi, spec2())
    assert not [e for e in svg_root(rep).iter() if "data-trade" in e.attrib]
    for e in rep.events:
        assert not [x for x in svg_root(rep.panels[e]).iter() if "data-trade" in x.attrib]


# ---------- B9: inference line ----------

#: The inference line's marker, a line prefix and never a substring: report.md's Provenance prints ``- inferred: false``, which a bare ``inferred: `` would match.
INFERENCE_MARKER = "inferred: no event was given, so "


def test_b9_inference_line_present_iff_inferred_and_precedes_the_headline() -> None:
    inferred = two_event_multi(inferred=True, non_event="completed")
    rep = build_multi_report(inferred, spec2())
    expected = inferred.to_markdown().splitlines()[0]
    assert expected.startswith(INFERENCE_MARKER)
    assert rep.inference_line == expected
    md, svg_text, html = visible_texts(rep)
    line1 = inferred.headline().splitlines()[0]
    for text in (md, svg_text, html):
        assert expected in text
        assert text.index(expected) < text.index(line1)
    explicit = two_event_multi(inferred=False, non_event=None)
    rep2 = build_multi_report(explicit, spec2())
    assert rep2.inference_line is None
    for text in visible_texts(rep2):
        assert not [line for line in text.splitlines() if line.startswith(INFERENCE_MARKER)]


# ---------- B10: per-panel honesty from per-event fields ----------


def test_b10_each_panel_honesty_uses_its_own_events_fields() -> None:
    # PF4 (PF4.20): the honesty line's '"N worse"' and the panel captions are a reader's words only
    # for an event whose kind is known, so the three hand-built events are failure events.
    xs, ys = [0.1, 0.2], [10, 20]
    alpha = make_event("alpha", [
        make_cell({"mu": 0.1, "push": 10}, delta=-0.3, q=1e-3, verdict="safer", mde=0.5),
        make_cell({"mu": 0.1, "push": 20}, delta=0.0, verdict="unchanged", mde=0.2, n_a=40, n_b=41),
        make_cell({"mu": 0.2, "push": 10}, delta=0.0, verdict="unchanged", mde=0.1),
        make_cell({"mu": 0.2, "push": 20}, delta=0.0, verdict="unchanged", mde=0.05),
    ], kind=FAILURE)
    beta = make_event("beta", [
        make_cell({"mu": 0.1, "push": 10}, delta=0.0, verdict="unchanged", mde=0.3, n_a=12, n_b=13),
        make_cell({"mu": 0.1, "push": 20}, delta=-0.3, q=1e-3, verdict="safer", mde=0.45),
        make_cell({"mu": 0.2, "push": 10}, delta=0.3, q=1e-3, verdict="worse", mde=0.1),
        make_cell({"mu": 0.2, "push": 20}, delta=-0.3, q=1e-3, verdict="safer", mde=0.05),
    ], kind=FAILURE)
    gamma = make_event(
        "gamma", grid_cells(xs, ys, delta_fn=lambda i, j: 0.3, verdict_fn=sign_verdict, mde_fn=lambda i, j: 0.25), kind=FAILURE
    )
    multi = make_multi([alpha, beta, gamma])
    rep = build_multi_report(multi, spec2())
    sections = panel_sections(rep.to_markdown(), rep)
    for e in rep.events:
        ev = multi.by_event[e]
        panel = rep.panels[e]
        _check_honesty(panel, max_mde=ev.max_mde, max_mde_unchanged=ev.max_mde_unchanged, panel=True)
        first, second = honesty_lines(panel)
        assert first in sections[e] and second in sections[e]
        if ev.max_mde_unchanged_cell is not None:
            m = HONESTY_FIRST_RE.match(first)
            assert m
            assert named_cell(panel, m.group(1)).config_hash == ev.max_mde_unchanged_cell
    a_first, _ = honesty_lines(rep.panels["alpha"])
    b_first, _ = honesty_lines(rep.panels["beta"])
    g_first, _ = honesty_lines(rep.panels["gamma"])
    assert "20pp" in a_first and "n=40/41" in a_first
    assert "30pp" in b_first and "n=12/13" in b_first
    # PF4 (PF4.17): gamma has no unchanged condition, so its line counts the four compared ones.
    assert g_first != HONESTY_NONE and re.search(r"(?<![\d.])4(?![\d.])", g_first)
    assert len({a_first, b_first, g_first}) == 3


# ---------- B11: forest auto-detection ----------


def _categorical_cells() -> list[dict[str, Any]]:
    return [
        make_cell({"task_id": "a"}, delta=-0.2, q=0.01, verdict="safer", mde=0.1, n_a=10, n_b=12),
        make_cell({"task_id": "b"}, delta=0.0, q=0.9, verdict="unchanged", mde=0.2, n_a=20, n_b=20),
        make_cell({"task_id": "c"}, delta=0.3, q=0.02, verdict="worse", mde=0.05, n_a=5, n_b=7),
    ]


def _numeric_cells() -> list[dict[str, Any]]:
    return [
        dict(c, config={"k": k}, config_hash=config_hash({"k": k}))
        for c, k in zip(_categorical_cells(), [0.1, 0.2, 0.3], strict=True)
    ]


def test_b11_default_forest_setting_is_auto() -> None:
    assert ReportSpec(title="t", x_axis="task_id").forest == "auto"


def test_b11_auto_picks_forest_for_categorical_x_strip_for_numeric_x_heatmap_with_y() -> None:
    assert panel_kind(build_report(make_diff(_categorical_cells()), ReportSpec(title="t", x_axis="task_id"))) == "forest"
    assert panel_kind(build_report(make_diff(_numeric_cells()), ReportSpec(title="t", x_axis="k"))) == "strip"
    with_y = make_diff(grid_cells(["a", "b", "c"], [1, 2], x_key="task_id", y_key="level", delta_fn=lambda i, j: 0.1 * (i - j)))
    assert panel_kind(build_report(with_y, ReportSpec(title="t", x_axis="task_id", y_axis="level"))) == "heatmap"
    numeric_y = make_diff(grid_cells([0.1, 0.2], [1, 2], delta_fn=lambda i, j: 0.1 * (i - j)))
    assert panel_kind(build_report(numeric_y, spec2())) == "heatmap"


def test_b11_always_and_never_override_the_detection() -> None:
    assert panel_kind(build_report(make_diff(_numeric_cells()), ReportSpec(title="t", x_axis="k", forest="always"))) == "forest"
    assert panel_kind(build_report(make_diff(_categorical_cells()), ReportSpec(title="t", x_axis="task_id", forest="never"))) == "strip"
    with_y = make_diff(grid_cells(["a", "b", "c"], [1, 2], x_key="task_id", y_key="level", delta_fn=lambda i, j: 0.1 * (i - j)))
    assert panel_kind(build_report(with_y, ReportSpec(title="t", x_axis="task_id", y_axis="level", forest="always"))) == "heatmap"


def test_b11_multi_report_panels_render_as_forest_for_a_categorical_axis() -> None:
    alpha = make_event("alpha", _categorical_cells())
    beta = make_event("beta", [dict(c, delta=-c["delta"], verdict={"safer": "worse", "worse": "safer"}.get(c["verdict"], "unchanged")) for c in _categorical_cells()])
    rep = build_multi_report(make_multi([alpha, beta]), ReportSpec(title="t", x_axis="task_id"))
    for e in rep.events:
        assert panel_kind(rep.panels[e]) == "forest"
    for g in panel_groups(svg_root(rep)):
        rows = [x for x in g.iter() if _local(x.tag) == "g" and "data-cell" in x.attrib]
        assert len(rows) == 3 and not cell_rects(g)


def test_b11_forest_panel_satisfies_i7_i10_i12_i13() -> None:
    d = make_diff(_categorical_cells())
    dark = build_report(d, ReportSpec(title="t", x_axis="task_id", theme="dark"))
    light = build_report(d, ReportSpec(title="t", x_axis="task_id", theme="light"))
    assert panel_kind(dark) == "forest"
    # I13
    assert dark.y_values == () and dark.x_values == ("a", "b", "c") and len(dark.cells) == 3
    assert all(len(c.coords) == 1 for c in dark.cells)
    # I10
    root = check_svg_hygiene(dark.to_svg())
    # I7
    strip_presentation(root)
    sig = glyphs(root)
    assert len(sig) == dark.n_safer + dark.n_worse == 2
    for e in root.iter():
        assert e.attrib.get("data-sig", "1") == "1"
    parents = _parents(root)
    recovered = set()
    for g in sig:
        owner = owning_row(g, parents)
        assert owner is not None, "glyph must be a descendant of its row's <g data-cell>"
        recovered.add(owner.attrib["data-cell"])
    assert recovered == {c.config_hash for c in dark.cells if c.verdict != "unchanged"}
    # I12
    assert tree_signature(root) == tree_signature(strip_presentation(svg_root(light)))


# ---------- B12: forest content ----------


def _point_x(e: ET.Element) -> float:
    if "cx" in e.attrib:
        return float(e.attrib["cx"])
    return float(e.attrib["x"]) + float(e.attrib.get("width", 0)) / 2


def _bracket_half_width(e: ET.Element) -> float:
    if "x1" in e.attrib and "x2" in e.attrib:
        return abs(float(e.attrib["x2"]) - float(e.attrib["x1"])) / 2
    return float(e.attrib["width"]) / 2


def _forest_rows(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if _local(e.tag) == "g" and "data-cell" in e.attrib]


def test_b12_forest_rows_points_brackets_glyphs_and_legend() -> None:
    d = make_diff(_categorical_cells())
    report = build_report(d, ReportSpec(title="t", x_axis="task_id"))
    assert report.spec.forest == "auto" and panel_kind(report) == "forest"
    root = svg_root(report)
    rows = _forest_rows(root)
    by_hash = {c.config_hash: c for c in report.cells}
    assert [r.attrib["data-cell"] for r in rows] == [config_hash({"task_id": t}) for t in ("a", "b", "c")]
    xs: dict[str, float] = {}
    halves: dict[str, float] = {}
    for row in rows:
        points = [e for e in row.iter() if e.attrib.get("data-point") == "1"]
        brackets = [e for e in row.iter() if e.attrib.get("data-mde") == "1"]
        assert len(points) == 1 and len(brackets) == 1, row.attrib
        xs[row.attrib["data-cell"]] = _point_x(points[0])
        halves[row.attrib["data-cell"]] = _bracket_half_width(brackets[0])
        cell = by_hash[row.attrib["data-cell"]]
        row_text = " ".join(texts(row))
        assert f"{cell.n_a}/{cell.n_b}" in row_text, row_text
        has_glyph = bool([e for e in row.iter() if e.attrib.get("data-sig") == "1"])
        assert has_glyph == (cell.verdict != "unchanged"), cell
    ha, hb, hc = (config_hash({"task_id": t}) for t in ("a", "b", "c"))
    scale = (xs[hc] - xs[ha]) / (by_hash[hc].delta - by_hash[ha].delta)
    assert scale > 0
    predicted_b = xs[ha] + scale * (by_hash[hb].delta - by_hash[ha].delta)
    assert abs(xs[hb] - predicted_b) <= 1.0, (xs, scale)
    for h in (ha, hb, hc):
        assert abs(halves[h] - by_hash[h].mde * scale) <= 1.0, (h, halves[h], by_hash[h].mde * scale)
    assert halves[hb] > halves[ha] > halves[hc]
    legend = "\n".join(texts(root))
    assert "MDE" in legend
    assert not re.search(r"\bCI\b", legend)
    assert "confidence interval" not in legend.lower()
    assert len(glyphs(root)) == 2


def test_b12_forest_point_scale_is_the_shared_bound_in_the_multi_report() -> None:
    alpha = make_event("alpha", _categorical_cells())
    beta = make_event("beta", [dict(c, delta=c["delta"] * 2, verdict=c["verdict"]) for c in _categorical_cells()])
    rep = build_multi_report(make_multi([alpha, beta]), ReportSpec(title="t", x_axis="task_id"))
    assert rep.bound == 0.6
    scales = {}
    for e in rep.events:
        root = svg_root(rep.panels[e])
        rows = {r.attrib["data-cell"]: r for r in _forest_rows(root)}
        by_hash = {c.config_hash: c for c in rep.panels[e].cells}
        ha, hc = config_hash({"task_id": "a"}), config_hash({"task_id": "c"})
        xa = _point_x(next(x for x in rows[ha].iter() if x.attrib.get("data-point") == "1"))
        xc = _point_x(next(x for x in rows[hc].iter() if x.attrib.get("data-point") == "1"))
        scales[e] = (xc - xa) / (by_hash[hc].delta - by_hash[ha].delta)
    assert abs(scales["alpha"] - scales["beta"]) <= 3.0, scales


# ---------- B13: stacked SVG ----------


def test_b13_stacked_svg_is_one_root_with_one_panel_group_per_event_matching_standalone() -> None:
    multi = _three_event_multi()
    rep = build_multi_report(multi, spec2())
    svg = rep.to_svg()
    root = check_svg_hygiene(svg)
    assert not [e for e in root.iter() if _local(e.tag) == "svg" and e is not root], "no nested <svg>"
    groups = panel_groups(root)
    assert [g.attrib["data-panel"] for g in groups] == list(rep.events)
    assert all(_local(g.tag) == "g" for g in groups)
    for e, g in zip(rep.events, groups, strict=True):
        standalone = ET.fromstring(rep.panels[e].to_svg())
        assert [tree_signature(c) for c in g] == [tree_signature(c) for c in standalone], e
    assert "<script" not in rep.to_html()


def test_b13_stacked_svg_re_roots_escaped_text_intact() -> None:
    cells = [
        make_cell({"kind": "a<b&c", "level": 1}, delta=0.1),
        make_cell({"kind": 'x"y', "level": 1}, delta=-0.1, verdict="safer"),
        make_cell({"kind": "a<b&c", "level": 2}, delta=0.0),
        make_cell({"kind": 'x"y', "level": 2}, delta=0.05),
    ]
    multi = make_multi([make_event("al<pha", cells), make_event("be&ta", cells)])
    rep = build_multi_report(multi, ReportSpec(title='ti<tle & "q"', x_axis="kind", y_axis="level"))
    root = check_svg_hygiene(rep.to_svg())
    groups = panel_groups(root)
    assert [g.attrib["data-panel"] for g in groups] == list(rep.events)
    for e, g in zip(rep.events, groups, strict=True):
        standalone = ET.fromstring(rep.panels[e].to_svg())
        assert [tree_signature(c) for c in g] == [tree_signature(c) for c in standalone], e
    assert any("a<b&c" in t for t in texts(root))
    assert "a<b&c" not in rep.to_svg() and "a<b&c" not in rep.to_html()


# ---------- B14: determinism and theme separation ----------

_SUBPROCESS_SCRIPT = """
import hashlib, sys
from pathlib import Path
from poisson_prove.store import Store
from poisson_prove.diff import multi_diff
from poisson_prove.report import ReportSpec, build_multi_report
store = Store(Path(sys.argv[1]))
run_a, run_b, event, other, x, y, title = sys.argv[2:9]
a, b = store.read(run_a), store.read(run_b)
m = multi_diff(a, b, events=[event, other],
               manifest_a=store.manifest(run_a), manifest_b=store.manifest(run_b))
rep = build_multi_report(m, ReportSpec(title=title, x_axis=x, y_axis=y),
                         manifests=(store.manifest(run_a), store.manifest(run_b)))
for text in (rep.to_markdown(), rep.to_svg(), rep.to_html()):
    print(hashlib.sha256(text.encode("utf-8")).hexdigest())
"""


def test_b14_multi_report_is_byte_identical_across_hash_seeds(
    golden_multi: MultiDiffResult, golden_frames: dict[str, Any], tmp_path: Path
) -> None:
    rep = build_multi_report(
        golden_multi, ReportSpec(title=LATTICE_TITLE, x_axis=lattice.Y, y_axis=lattice.X),
        manifests=(golden_frames["ma"], golden_frames["mb"]),
    )
    local = [_sha(rep.to_markdown()), _sha(rep.to_svg()), _sha(rep.to_html())]
    script = tmp_path / "render.py"
    script.write_text(_SUBPROCESS_SCRIPT)
    for seed in ("1", "4242"):
        proc = subprocess.run(
            [sys.executable, str(script), str(lattice.root()), lattice.RUN_A, lattice.RUN_B, lattice.EVENT, lattice.OTHER,
             lattice.Y, lattice.X, LATTICE_TITLE],
            capture_output=True, text=True, cwd=ROOT,
            env={"PYTHONHASHSEED": seed, "PATH": "", "HOME": str(tmp_path)},
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.split() == local, seed


def test_b14_dark_and_light_stacked_trees_identical_after_stripping_presentation() -> None:
    multi = two_event_multi()
    dark = strip_presentation(svg_root(build_multi_report(multi, spec2(theme="dark"))))
    light = strip_presentation(svg_root(build_multi_report(multi, spec2(theme="light"))))
    assert tree_signature(dark) == tree_signature(light)
    assert len(panel_groups(dark)) == 2
    assert any("data-trade" in e.attrib for e in dark.iter())


def test_b14_hypothesis_repeat_renders_identical_and_themes_differ_only_in_presentation() -> None:
    @settings(max_examples=25, deadline=None)
    @given(
        nx=st.integers(min_value=2, max_value=4),
        ny=st.integers(min_value=1, max_value=3),
        seed=st.integers(min_value=0, max_value=10**6),
        n_events=st.integers(min_value=1, max_value=3),
        inferred=st.booleans(),
    )
    def check(nx: int, ny: int, seed: int, n_events: int, inferred: bool) -> None:
        xs = [round(0.1 * (i + 1), 2) for i in range(nx)]
        ys = [10 * (j + 1) for j in range(ny)]
        events = []
        for k in range(n_events):
            def delta_fn(i: int, j: int, k: int = k) -> float:
                return ((i * 7 + j * 3 + k * 5 + seed) % 11 - 5) / 20

            def verdict_fn(i: int, j: int, dl: float, k: int = k) -> str:
                return sign_verdict(i, j, dl) if (i + j + k + seed) % 3 == 0 else "unchanged"

            events.append(make_event(WORDS[k], grid_cells(xs, ys, delta_fn=delta_fn, verdict_fn=verdict_fn)))
        multi = make_multi(events, inferred=inferred, non_event="completed" if inferred else None)
        spec_dark, spec_light = spec2(theme="dark"), spec2(theme="light")
        first = build_multi_report(multi, spec_dark)
        second = build_multi_report(multi, spec_dark)
        assert (first.to_markdown(), first.to_svg(), first.to_html()) == (second.to_markdown(), second.to_svg(), second.to_html())
        light = build_multi_report(multi, spec_light)
        assert tree_signature(strip_presentation(svg_root(first))) == tree_signature(strip_presentation(svg_root(light)))
        assert first.headline == light.headline and first.trade_line == light.trade_line

    check()


# ---------- B15: provenance ----------


def test_b15_provenance_carries_the_multi_fields_and_run_ids_only_with_manifests() -> None:
    multi = two_event_multi(seed_identity_match=True, unpaired_analysis=True, inferred=True, non_event="completed", t_unit="tool_calls", horizon=50.0)
    bare = build_multi_report(multi, spec2())
    for key in ("n_tests", "events", "inferred", "non_event", "method", "seed_identity_match", "unpaired_analysis", "q", "horizon", "t_unit"):
        assert key in bare.provenance, key
    assert bare.provenance["n_tests"] == multi.n_tests == 12
    assert sorted(bare.provenance["events"]) == sorted(multi.events)  # type: ignore[arg-type]
    assert bare.provenance["inferred"] is True and bare.provenance["non_event"] == "completed"
    assert bare.provenance["method"] == "fisher_bh" and bare.provenance["seed_identity_match"] is True
    assert bare.provenance["unpaired_analysis"] is True and "paired" not in bare.provenance
    assert bare.provenance["q"] == 0.05 and bare.provenance["horizon"] == 50.0
    assert bare.provenance["t_unit"] == "tool_calls"
    assert "run_id_a" not in bare.provenance and "run_id_b" not in bare.provenance
    assert "run-a" not in bare.to_markdown()
    with_runs = build_multi_report(multi, spec2(), manifests=(_manifest("run-a"), _manifest("run-b")))
    assert with_runs.provenance["run_id_a"] == "run-a" and with_runs.provenance["run_id_b"] == "run-b"
    assert "run-a" in with_runs.to_markdown() and "run-b" in with_runs.to_html()
    # Retrofitted 2026-09-20 (truncation surfacing): the manifests also give each run's recorded byte
    # limit, an ``observation_cap_*`` key beside the ``run_*`` identity ones and no number of the report's.
    assert {k: v for k, v in with_runs.provenance.items() if not k.startswith(("run_", "observation_"))} == {
        k: v for k, v in bare.provenance.items() if not k.startswith(("run_", "observation_"))
    }


# ---------- B16: survival report ----------

H = 50.0
TASKS = ["search", "checkout", "refund"]
RATES = [0.0, 0.5]


def _survival_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    def rows(n: int, timeout: int, violated: int) -> list[tuple[str, float]]:
        out = [("timeout", H)] * timeout + [("violated", 30.0)] * violated
        return out + [("completed", 20.0)] * (n - len(out))

    cells = {
        ("search", 0.0): rows(32, 0, 0),          # both rates 0
        ("search", 0.5): rows(32, 32, 0),         # timeout rate 1
        ("checkout", 0.0): rows(8, 2, 1),         # n < 16
        ("checkout", 0.5): rows(12, 6, 3),        # n < 16
        ("refund", 0.0): rows(16, 4, 8),
        ("refund", 0.5): rows(20, 10, 2),
    }
    df = raw_frame(cells, horizon=H)
    table = cell_table(df, "timeout", method="aj", events=["timeout", "violated"], horizon=H)
    return df, table


def _survival_report(theme: str = "dark") -> tuple[pd.DataFrame, SurvivalReport]:
    _, table = _survival_inputs()
    rep = build_survival_report(
        table, ReportSpec(title="first sweep", x_axis="rate", y_axis="task", theme=theme),
        events=["timeout", "violated"], horizon=H,
    )
    return table, rep


def test_b16_sequential_ramp_is_public_with_nine_stops_ending_in_the_failed_family() -> None:
    assert set(SEQUENTIAL_RAMP) == {"dark", "light"}
    for theme, stops in SEQUENTIAL_RAMP.items():
        assert len(stops) == 9, theme
        assert all(HEX_RE.match(s) for s in stops)
        assert is_red_family(stops[-1])
        assert len(set(stops)) == 9


def test_b16_one_panel_per_event_with_cif_at_horizon_as_rate_a_and_nothing_else() -> None:
    table, rep = _survival_report()
    assert rep.events == ("timeout", "violated") and set(rep.panels) == set(rep.events)
    curves = dict(zip(table["config_hash"], table["curve"], strict=True))
    for e in rep.events:
        panel = rep.panels[e]
        present = present_cells(panel)
        assert len(present) == 6 and panel.n_absent == 0
        for c in present:
            assert c.config_hash is not None
            assert abs(c.rate_a - curves[c.config_hash].at(e, H)) <= 1e-12, (e, c)
            assert all(math.isnan(v) for v in (c.rate_b, c.delta, c.p, c.q, c.mde)), c
            assert c.verdict == ""
        assert (panel.n_safer, panel.n_worse) == (0, 0)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_b16_fill_is_the_sequential_ramp_in_rate_a(theme: str) -> None:
    _, rep = _survival_report(theme)
    stops = SEQUENTIAL_RAMP[theme]
    for e in rep.events:
        panel = rep.panels[e]
        fills = fills_by_hash(svg_root(panel))
        by_hash = {c.config_hash: c for c in present_cells(panel)}
        assert set(fills) == set(by_hash)
        for h, c in by_hash.items():
            if c.rate_a == 0.0:
                assert fills[h] == stops[0], (e, h)
            if c.rate_a == 1.0:
                assert fills[h] == stops[-1], (e, h)
        ordered = sorted((c.rate_a, fills[h]) for h, c in by_hash.items())
        dists = [rgb_distance(f, stops[0]) for _, f in ordered]
        assert all(b >= a - 1e-9 for a, b in pairwise(dists)), (e, ordered)
    timeout_cells = {c.config_hash: c for c in present_cells(rep.panels["timeout"])}
    assert any(c.rate_a == 0.0 for c in timeout_cells.values())
    assert any(c.rate_a == 1.0 for c in timeout_cells.values())


def test_b16_worst_cells_sort_by_rate_a_desc_and_coverage_line_counts_n() -> None:
    table, rep = _survival_report()
    md = rep.to_markdown()
    sections = survival_sections(md, rep)
    n_min, n_max = int(table["n"].min()), int(table["n"].max())
    n_small = int((table["n"] < 16).sum())
    assert (n_min, n_max, n_small) == (8, 32, 2)
    for e in rep.events:
        panel = rep.panels[e]
        rate_of = {(c.coords[0], c.coords[1]): c.rate_a for c in present_cells(panel)}
        rows = worst_rows(sections[e], TASKS)
        assert len(rows) == 6
        printed = []
        for row in rows:
            first, second = [c.strip() for c in row.strip().strip("|").split("|")][:2]
            rate = next(r for r in RATES if math.isclose(float(first), r))
            assert second in TASKS, row
            printed.append(rate_of[(rate, second)])
        assert printed == sorted(printed, reverse=True), (e, printed)
        m = COVERAGE_RE.search(sections[e])
        assert m, sections[e]
        assert tuple(int(x) for x in m.groups()) == (n_min, n_max, n_small)
    md_text, svg_text, html = visible_texts(rep)
    for text in (md_text, svg_text, html):
        assert len(COVERAGE_RE.findall(text)) == len(rep.events), text[:300]


def test_b16_no_trade_line_no_method_table_no_delta_or_q_in_the_text() -> None:
    _, rep = _survival_report()
    md, svg_text, html = visible_texts(rep)
    for text in (md, svg_text, html):
        assert TRADE_MARK not in text
        assert re.search(r"\bdelta\b", text, re.IGNORECASE) is None, text[:300]
        assert re.search(r"\bq\b", text) is None, text[:300]
        assert "Worst-powered" not in text
    assert not [line for line in md.splitlines() if line.startswith("## Method")]
    assert not [line for line in md.splitlines() if line.startswith("|") and "| method " in line]
    assert "events" in rep.provenance and "horizon" in rep.provenance
    check_svg_hygiene(rep.to_svg())


def test_b16_manifest_supplies_run_identity_only_when_given() -> None:
    _, table = _survival_inputs()
    spec = ReportSpec(title="first sweep", x_axis="rate", y_axis="task")
    bare = build_survival_report(table, spec, events=["timeout", "violated"], horizon=H)
    assert "run_id" not in bare.provenance and "run_id_a" not in bare.provenance
    stamped = build_survival_report(table, spec, events=["timeout", "violated"], horizon=H, manifest=_manifest("run-x"))
    assert "run-x" in stamped.to_markdown() and "run-x" not in bare.to_markdown()


# ---------- B17: mock-agent golden ----------


#: The trade count is a property of the rebalanced quickstart grid (S23: 3 tasks x 3
#: tool_fail_rate values x N=100), read off it and not chosen. Before S23 the grid was 15
#: cells at N=16 and traded two cells; the grid moved because the old one could not clear the
#: pre-flight power gate, and this golden moved with it. The panel order did not move: M7
#: orders panels itself (worst first), so it is still timeout then violated even though
#: ``multi.events`` now infers violated first.
QUICKSTART_TRADES = 1
QUICKSTART_PANEL_ORDER = ["timeout", "violated"]


def test_b17_quickstart_pair_reads_timeout_first_with_one_trade(quickstart: dict[str, Any]) -> None:
    multi: MultiDiffResult = quickstart["multi"]
    assert multi.inferred and multi.non_event == "completed"
    assert len(multi.trades) == QUICKSTART_TRADES, (
        f"salt {QUICKSTART_SALT} gave {len(multi.trades)} trades: the mock-agent golden is "
        f"salt-specific and grid-specific"
    )
    rep = build_multi_report(
        multi, ReportSpec(title="quickstart", x_axis="tool_fail_rate", y_axis="task_id"),
        manifests=(quickstart["ma"], quickstart["mb"]),
    )
    assert rep.events == tuple(QUICKSTART_PANEL_ORDER)
    assert rep.trade_line is not None and "timeout" in rep.trade_line and "violated" in rep.trade_line
    assert rep.trade_line == multi.trade_line()
    assert rep.inference_line == multi.to_markdown().splitlines()[0]
    assert rep.inference_line is not None and rep.inference_line.startswith(INFERENCE_MARKER)
    groups = panel_groups(svg_root(rep))
    assert [g.attrib["data-panel"] for g in groups] == QUICKSTART_PANEL_ORDER
    traded = set(multi.trades["config_hash"])
    assert len(traded) == QUICKSTART_TRADES
    for g in groups:
        marks = _traded_hashes(g)
        assert len(marks) == QUICKSTART_TRADES and set(marks) == traded
    md, svg_text, html = visible_texts(rep)
    for text in (md, svg_text, html):
        assert rep.inference_line in text and rep.trade_line in text
    assert rep.provenance["run_id_a"] == quickstart["ma"].run_id


# ---------- B18: scale guard ----------


def test_b18_three_events_by_a_thousand_cells_render_in_all_formats() -> None:
    xs, ys = list(range(40)), list(range(25))
    events = [
        make_event(name, grid_cells(
            xs, ys, x_key="x", y_key="y",
            delta_fn=lambda i, j, k=k: ((i * j + k) % 21 - 10) / 20,
            verdict_fn=lambda i, j, dl: "safer" if dl < -0.3 else "worse" if dl > 0.3 else "unchanged",
        ))
        for k, name in enumerate(("alpha", "beta", "gamma"))
    ]
    multi = make_multi(events)
    assert multi.n_tests == 3000
    rep = build_multi_report(multi, ReportSpec(title="big", x_axis="x", y_axis="y"))
    assert len(rep.panels) == 3
    for e in rep.events:
        assert len(rep.panels[e].cells) == 1000 and rep.panels[e].n_absent == 0
    md = rep.to_markdown()
    root = check_svg_hygiene(rep.to_svg())
    html = rep.to_html()
    assert len(panel_groups(root)) == 3
    assert sum(len(cell_nodes(g)) for g in panel_groups(root)) == 3000
    assert multi.headline().splitlines()[0] in md and html_escape(multi.headline().splitlines()[0]) in html


# ---------- B19: no computation ----------


def test_b19_report_module_imports_no_numpy_or_scipy() -> None:
    import poisson_prove.report as report_module

    source = Path(report_module.__file__).read_text()
    for banned in ("import numpy", "from numpy", "import scipy", "from scipy"):
        assert banned not in source, banned


def _word_multi(**overrides: Any) -> MultiDiffResult:
    def cells() -> list[dict[str, Any]]:
        return [
            make_cell({"row": y, "col": x}, rate_a=0.25, delta=0.125, p=0.02, q=0.03, mde=0.15, n_a=30, n_b=31)
            for x in ("alpha", "beta") for y in ("north", "south")
        ]

    first = cells()
    target = first[0]
    target.update(overrides)
    if "delta" in overrides and "rate_b" not in overrides:
        target["rate_b"] = target["rate_a"] + target["delta"]
    # PF4 (PF4.3): the report prints each arm's share, events over runs, so a changed run count
    # keeps the cell's event count within it (the factory counted events at n=30 and n=31).
    for n, k, rate in (("n_a", "events_a", "rate_a"), ("n_b", "events_b", "rate_b")):
        if n in overrides:
            target[k] = int(round(target[rate] * target[n]))
    return make_multi([make_event("ev1", first), make_event("ev2", cells())])


@pytest.mark.parametrize(
    "field, value",
    [("n_a", 7), ("n_b", 9), ("rate_a", 0.75), ("rate_b", 0.9), ("delta", -0.4),
     ("p", 0.4), ("q", 0.6), ("mde", 0.45)],
)
def test_b19a_changing_a_cell_field_in_one_event_changes_the_visible_output(field: str, value: Any) -> None:
    spec = ReportSpec(title="t", x_axis="col", y_axis="row", top_n=10)
    base = build_multi_report(_word_multi(), spec)
    changed = build_multi_report(_word_multi(**{field: value}), spec)
    assert visible_texts(base)[:2] != visible_texts(changed)[:2]


def test_b19b_all_zero_multi_prints_only_zeros_in_tables_captions_and_honesty() -> None:
    def zero_cells() -> list[dict[str, Any]]:
        return [
            make_cell({"row": y, "col": x}, n_a=0, n_b=0, rate_a=0.0, rate_b=0.0, delta=0.0, p=0.0, q=0.0, mde=0.0, stat=0.0)
            for x in ("alpha", "beta") for y in ("north", "south")
        ]

    # PF4 (PF4.20): the captions read safer/worse only for an event whose kind is known, so the
    # two hand-built events are failure events.
    multi = make_multi([make_event("uno", zero_cells(), kind=FAILURE), make_event("dos", zero_cells(), kind=FAILURE)])
    for ev in multi.by_event.values():
        assert ev.max_mde == 0.0 and ev.max_mde_unchanged == 0.0
    rep = build_multi_report(multi, ReportSpec(title="t", x_axis="col", y_axis="row", top_n=10))
    sections = panel_sections(rep.to_markdown(), rep)
    for e in rep.events:
        rows = worst_rows(sections[e], ["alpha", "beta"])
        assert len(rows) == 4
        for row in rows:
            assert all(v == 0.0 for v in numbers_in(row)), row
        for line in honesty_lines(rep.panels[e]):
            assert all(v == 0.0 for v in numbers_in(line)), line
        assert all(v == 0.0 for v in numbers_in(caption(rep, e)))
        honesty_in_md = [line for line in sections[e].splitlines() if _is_honesty_line(line)]
        assert honesty_in_md
        for line in honesty_in_md:
            assert all(v == 0.0 for v in numbers_in(line)), line
