"""PF12, the static UI: the pages ``poisson-prove ui`` and every writing verb build in the store (the code suite).

Written from the front-door spec's section 18.3 (ruling Q65), section 16.3 items 5 and 6, its
invariants PF12.6 to PF12.11 and PF12.13, the design session's ``views.md`` and the look file's
static-UI section (rulings Y1 to Y30 of 2026-10-23, all as recommended), and the test standard
(section 10.6). ``tests/test_pf12_artifacts.py`` holds the format. The build is written against these
files and does not edit them.

**How a page is read.** No browser in the code suite: each page is parsed as HTML (Q65). A page is
the rendering of exactly one core view (section 17.1's ``view(store, address)``, the address being
the page's path inside the UI, Y17), and says which fact is which, so a test can hold every page to
its view without knowing the view's field names (Y2 leaves those to PF5 and PF12):

- R19 Every element that shows a fact carries ``data-fact``, the JSON pointer of that fact in the
  view's document (``/rows/3/delta``), and ``data-value``, the fact's value as JSON; its text is the
  fact as rule 10 prints it. Every scalar of the view is shown by at least one such element, and no
  element names a pointer the view does not have; a chart's drawing, a view string named ``svg``
  (``views.md``'s chart field), is shown by the SVG itself, inline in the page.
- R20 The renderer computes nothing: every digit a reader sees on a page, outside links, charts, the
  header, the navigation and the footer, sits inside an element that carries ``data-fact``.
- R21 The episodes view has one page per run of a saved comparison, event of that comparison and
  condition it compared (``runs/<run>/episodes/<event>/<condition hash>.html``), empty pages included,
  as ``views.md`` draws them (2 runs, 2 events, 9 conditions: 36 pages); a run in no saved comparison
  has no episodes pages, so a store of many runs does not grow a page per outcome and condition.
- R22 A saved check has no page in v0, and the runs view lists the saved comparisons only (Y6).
- R25 "On the same line" in a page is the same block: the nearest ``p``, ``li``, ``tr``, ``dd``, ``dt``,
  ``h1``–``h6``, ``caption`` or ``figcaption`` around the words.
- R26 A page carries no build time and nothing of where the store is: the same records give the same
  page bytes wherever the store sits.
- R28 A page names the store by its folder's name only.
- R29 A chart is an SVG whose first two children are ``title`` and ``desc`` (its text alternative),
  with ``role="img"`` and ``aria-labelledby`` naming both; it holds no script, no foreign object and no
  reference outside itself; its colours are the look's chart tokens (as ``var(--…)`` or their light
  and dark values), never the four meanings'.
- R30 A number in a chart's text has at most three decimals, or is ``2.3e-08``-shaped.
- R31 A page that shows a verdict shows it first: the first fact in ``main`` is the verdict word.
- R18 Every file in ``.poisson/ui/`` is a page (``.html``) or a fixed bundle file, byte for byte one
  file of the same name in the package (so in the wheel); the bundle holds at least ``style.css`` and
  ``ui.js``, and its style sheets set the look's twelve tokens for light and dark.
- R17 ``ui`` prints ``ok  dashboard at <the file URI of the store's .poisson/ui/index.html>``; its
  ``--json`` (``poisson-prove.ui/1``) carries ``location``, the same URI; on a store folder with no runs
  it builds the empty runs view, and on a missing store it refuses as ``runs`` does.
- R34 An interrupted build: after Ctrl-C the previous pages stand byte for byte; after a kill they
  stand or there are none, never a mix, and the next build is whole.
- R42 The views' field names are frozen here, as ``views.md`` gives them (``VIEW_FIELDS``): PF5's freeze
  leaves them to PF12 and PF6 (Y2). A condition view's per-event blocks are a list ``events``, each
  naming its ``event``; its ``test`` also carries ``q_holm`` (section 18.3 item 4: Holm's adjusted p).
- R40 "Every writing verb refreshes the pages" refreshes the UI a store has: a store with no
  ``.poisson/ui/`` gets none from ``sweep``, a save, ``report`` or ``serve``; ``ui`` (or the terminal
  app, before it shows a link) builds the first. So the frozen tests that run ``report`` and ``serve``
  on the committed Go1 fixture do not rebuild a 1,600-page UI each time.
- R23 Snapshots (PF12.13): seven pages of the 0.0.1 quickstart pair (R33: the committed fixture, so
  the same records every time), compared as text after the build's times, the running version and the
  comparison's id are replaced. A page is one file for both themes (it follows the system's), so light
  and dark are held by the style sheets' tokens here and by the browser check below.
- R24 The browser check (marked ``slow``): Playwright's Chromium, Firefox and WebKit (Safari's engine)
  open the snapshot pages from ``file://`` at 390 and 1280 px in light and dark; a missing engine fails
  with the line that installs it.
- R37 Each page's ``Content-Security-Policy`` meta comes before any style or script, sets
  ``default-src 'none'``, allows scripts from ``'self'`` only, styles from ``'self'`` and inline (the
  charts' own), images from ``'self'`` and ``data:``, and names no host.

**Lanes.** The code suite, but for the browser check and the wheel's bytes (``slow``).
"""

from __future__ import annotations

import fractions
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile
from collections import deque
from pathlib import Path
from typing import Any

import pytest

from pf12_support import (
    CHART_TOKENS, MEANING_TOKENS, PLANTED_KEYS, QS_A, QS_B, ROOT, SNAPSHOT_COMMAND, SNAPSHOTS, SRC, TESTS,
    Node, Page, cli, config_hash_of, copy_store, doc, first_word,
    fixture_times, leaves, listing, look_tokens, normalise, pages_of, read_page, resolve_pointer, says,
    shows_number, view_document,
)



@pytest.fixture(autouse=True)
def _empty_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    for name in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)


def _store(world: tuple[Path, dict[str, Any]]) -> Path:
    return Path(world[1]["store"])


def _ui(store: Path) -> Path:
    return store / ".poisson" / "ui"


# ---------- the seven views and their addresses (Y17) ----------

HEX16 = r"[0-9a-f]{16}"
VIEW_ADDRESSES = {
    "runs": re.compile(r"^index\.html$"),
    "run": re.compile(r"^runs/[^/]+\.html$"),
    "comparison": re.compile(rf"^comparisons/{HEX16}\.html$"),
    "condition": re.compile(rf"^comparisons/{HEX16}/{HEX16}\.html$"),
    "episodes": re.compile(rf"^runs/[^/]+/episodes/[^/]+/{HEX16}\.html$"),
    "could_not_detect": re.compile(rf"^comparisons/{HEX16}/could-not-detect\.html$"),
    "chart": re.compile(rf"^comparisons/{HEX16}/((heatmap|differences|limits)-[^/]+|{HEX16}/incidence-[^/]+)\.html$"),
}
CHARTS = ("heatmap", "differences", "limits")


def kind_of(address: str) -> str:
    (kind,) = [k for k, pattern in VIEW_ADDRESSES.items() if pattern.match(address)] or ["none"]
    return kind


def _comparisons(store: Path) -> dict[str, dict[str, Any]]:
    folder = store / ".poisson" / "artifacts" / "comparison"
    if not folder.exists():
        return {}
    return {p.name: json.loads((p / "comparison.json").read_text(encoding="utf-8")) for p in sorted(folder.iterdir()) if (p / "comparison.json").is_file()}


def _hashes(result: dict[str, Any]) -> list[str]:
    return sorted({str(c["config_hash"]) for e in result["by_event"].values() for c in e["cells"]})


def _compared_runs(store: Path, cid: str) -> list[str]:
    return json.loads((store / ".poisson" / "artifacts" / "comparison" / cid / "artifact.json").read_text(encoding="utf-8"))["inputs"]["runs"]


def expected_pages(store: Path) -> set[str]:
    """Every page the UI holds for a store: the runs view, a run page per run, and per saved
    comparison its page, a page per condition, its could-not-detect page, its charts (Y17, Y19) and
    its runs' episodes pages for its events and conditions (R21)."""
    from poisson_prove.store import Store

    pages = {"index.html"} | {f"runs/{run}.html" for run in Store(store).runs()}
    for cid, result in _comparisons(store).items():
        events = list(result["by_event"])
        pages |= {f"runs/{r}/episodes/{e}/{h}.html" for r in _compared_runs(store, cid) for e in events for h in _hashes(result)}
        pages |= {f"comparisons/{cid}.html", f"comparisons/{cid}/could-not-detect.html"}
        pages |= {f"comparisons/{cid}/{h}.html" for h in _hashes(result)}
        pages |= {f"comparisons/{cid}/{chart}-{e}.html" for chart in CHARTS for e in events}
        pages |= {f"comparisons/{cid}/{h}/incidence-{e}.html" for h in _hashes(result) for e in events}
    return pages


def _relative_links(page: Page) -> list[str]:
    out = []
    for _tag, attrs in page.tags:
        for name in ("href", "src"):
            value = attrs.get(name)
            if value is not None and not value.startswith(("#", "data:")):
                out.append(value)
    return out


def _target(page: Page, link: str, ui: Path) -> tuple[Path, str]:
    path, _, anchor = link.partition("#")
    return (page.path.parent / urllib.parse.unquote(path)).resolve(), anchor


WORLDS = ("old", "stats", "sweep")


def _world(name: str, request: pytest.FixtureRequest) -> tuple[Path, dict[str, Any]]:
    return request.getfixturevalue(f"{name}_world")


@pytest.mark.parametrize("world", WORLDS)
def test_pf12_7_the_pages_are_exactly_the_seven_views_and_all_reachable_from_the_runs_view(world: str, request: pytest.FixtureRequest) -> None:
    """Section 18.3: the views are exactly its seven, at the addresses ``views.md`` gives them (Y17),
    one page each where the store has something to show (R21, R22); every comparison has its
    could-not-detect view; and every page is reached by following links from ``index.html``."""
    store = _store(_world(world, request))
    ui = _ui(store)
    built = {p.relative_to(ui).as_posix() for p in pages_of(ui)}
    assert {a for a in built if kind_of(a) == "none"} == set(), sorted(a for a in built if kind_of(a) == "none")
    expected = expected_pages(store)
    assert built == expected, {"extra": sorted(built - expected)[:10], "missing": sorted(expected - built)[:10]}
    if world == "old":
        assert {kind_of(a) for a in built} == set(VIEW_ADDRESSES)
    seen, queue = {"index.html"}, deque(["index.html"])
    while queue:
        page = read_page(ui, ui / queue.popleft())
        for link in _relative_links(page):
            target, _ = _target(page, link, ui)
            if target.suffix == ".html" and target.is_relative_to(ui.resolve()):
                address = target.relative_to(ui.resolve()).as_posix()
                if address not in seen:
                    seen.add(address)
                    queue.append(address)
    assert seen == built, sorted(built - seen)[:10]


def _ids(page: Page) -> set[str]:
    return {attrs["id"] for _, attrs in page.tags if "id" in attrs}


def _links(page: Page, ui: Path) -> set[str]:
    out = set()
    for link in _relative_links(page):
        target, _ = _target(page, link, ui)
        if target.suffix == ".html" and target.is_relative_to(ui.resolve()):
            out.add(target.relative_to(ui.resolve()).as_posix())
    return out


@pytest.mark.parametrize("world", WORLDS)
def test_pf12_7_the_pages_hold_the_designs_anchors_embeds_and_footer(world: str, request: pytest.FixtureRequest) -> None:
    """The design's rulings that pages show by structure: the runs view links every saved comparison
    (Y6); a comparison page has the anchors ``views.md`` gives (Y17) and embeds its six charts, each
    linking to its page (Y19), and links each condition and its could-not-detect page; a condition page
    has a block per event (Y18) and links both runs' episodes for it and its incidence charts; an
    episodes page shows each episode's ``rollout(cfg, seed=…)`` and names ``poisson-prove inspect``
    for the import line (Y11); the differences, limits and heatmap charts have a row for every
    condition (Y12: an interval on every row); every page's footer names its address and says nothing
    was loaded from the network (Y30)."""
    store = _store(_world(world, request))
    ui = _ui(store)
    index = read_page(ui, ui / "index.html")
    comparisons = _comparisons(store)
    assert {f"comparisons/{cid}.html" for cid in comparisons} <= _links(index, ui)
    for cid, result in comparisons.items():
        events = list(result["by_event"])
        page = read_page(ui, ui / f"comparisons/{cid}.html")
        charts = [f"{c}-{e}" for c in CHARTS for e in events]
        assert {"verdict", "counts", "trades", "conditions", "charts", *charts} <= _ids(page), (cid, sorted(_ids(page)))
        assert len(page.root.find_all("svg")) >= len(charts), cid
        assert {f"comparisons/{cid}/{c}.html" for c in charts} | {f"comparisons/{cid}/{h}.html" for h in _hashes(result)} | {f"comparisons/{cid}/could-not-detect.html"} <= _links(page, ui)
        runs = _compared_runs(store, cid)
        for h in _hashes(result):
            condition = read_page(ui, ui / f"comparisons/{cid}/{h}.html")
            assert set(events) <= _ids(condition), (cid, h, sorted(_ids(condition)))
            assert {f"comparisons/{cid}/{h}/incidence-{e}.html" for e in events} <= _links(condition, ui), (cid, h)
            assert {f"runs/{r}/episodes/{e}/{h}.html" for r in runs for e in events} <= _links(condition, ui), (cid, h)
        for chart in ("heatmap", "differences", "limits"):
            for e in events:
                data = json.loads((store / ".poisson" / "artifacts" / "comparison" / cid / "charts" / f"{chart}-{e}.json").read_text(encoding="utf-8"))
                assert len(data["rows"]) == len(result["by_event"][e]["cells"]), (cid, chart, e)
    from poisson_prove.store import Store

    frames: dict[str, Any] = {}
    for path in pages_of(ui):
        page = read_page(ui, path)
        footers = page.root.find_all("footer")
        assert len(footers) == 1, page.address
        assert page.address in footers[0].text() and says(footers[0].text(), "nothing was loaded from the network"), (page.address, footers[0].text())
        if kind_of(page.address) == "episodes":
            _, run, _, outcome, name = page.address.split("/")
            frame = frames.setdefault(run, Store(store).read(run))
            ended = int(((frame["outcome"] == outcome) & (frame["config_hash"] == name.removesuffix(".html"))).sum())
            text = page.body_text()
            assert "poisson-prove inspect" in text, page.address
            assert ("rollout(" in text and "seed=" in text) is (ended > 0), (page.address, ended)


def _pages_by_kind(request: pytest.FixtureRequest, kind: str) -> list[tuple[Path, Page]]:
    out = []
    for world in WORLDS:
        store = _store(_world(world, request))
        ui = _ui(store)
        for path in pages_of(ui):
            if kind_of(path.relative_to(ui).as_posix()) == kind:
                out.append((store, read_page(ui, path)))
    assert out, kind
    return out


#: The elements a reader sees whose digits name addresses and the tool, not facts (R20).
NOT_FACTS = frozenset({"a", "svg", "header", "nav", "footer", "head", "script", "style", "title"})


def _loose_digits(node: Node, inside_fact: bool = False) -> list[str]:
    """Text a reader sees that holds a digit outside every element carrying ``data-fact`` (R20)."""
    if node.tag in NOT_FACTS:
        return []
    inside_fact = inside_fact or "data-fact" in node.attrs
    found = []
    for child in node.children:
        if isinstance(child, str):
            if not inside_fact and re.search(r"\d", child):
                found.append(child.strip())
        else:
            found += _loose_digits(child, inside_fact)
    return found


@pytest.mark.parametrize("kind", list(VIEW_ADDRESSES))
def test_pf12_7_each_page_holds_every_fact_of_its_core_view(kind: str, request: pytest.FixtureRequest) -> None:
    """Every page is its core view, rendered: each scalar of ``view(store, address)`` is shown by an
    element naming its pointer and value, the text agreeing with the number; no element names a fact
    the view lacks; and every digit a reader sees outside links, charts and the frame is a fact's
    (R19, R20; section 17.1: renderers format the facts and never recompute them)."""
    for store, page in _pages_by_kind(request, kind):
        view = view_document(store, page.address)
        shown: dict[str, list[Node]] = {}
        for node in page.facts():
            shown.setdefault(node.attrs["data-fact"], []).append(node)
        for pointer, nodes in shown.items():
            value = resolve_pointer(view, pointer)
            for node in nodes:
                assert json.loads(node.attrs.get("data-value", "\u0000")) == value, (page.address, pointer, node.attrs.get("data-value"), value)
                text = node.text()
                if isinstance(value, bool):
                    continue
                assert text, (page.address, pointer)
                if isinstance(value, (int, float)):
                    assert shows_number(text, float(value)), (page.address, pointer, text, value)
                if isinstance(value, str) and pointer.rsplit("/", 1)[-1] in ("verdict", "sentence"):
                    assert says(text, value), (page.address, pointer, text, value)  # a word reads as its value
        drawings = [(p, value) for p, value in leaves(view) if p.endswith("/svg")]
        for pointer, value in drawings:
            assert isinstance(value, str) and value.strip() in page.source, (page.address, pointer)
        missing = [p for p, value in leaves(view) if p != "/schema" and not p.endswith("/svg") and p not in shown]
        assert missing == [], (page.address, missing[:10])
        loose = _loose_digits(page.root.find_all("body")[0])
        assert loose == [], (page.address, loose[:5])


#: The views' field names, frozen here from ``views.md`` (the design session's proposals, which Y2 left
#: to PF5 and PF12; PF5's freeze leaves them to PF12 and PF6: reading R42). A view may hold more; it
#: holds at least these. ``*`` is every item of a list, or every value of a mapping keyed by data.
VIEW_FIELDS: dict[str, dict[str, set[str]]] = {
    "runs": {
        "": {"verdict", "sentence", "runs", "comparisons"},
        "/runs/*": {"number", "name", "run_id", "status", "backend", "target", "rows", "rows_without_outcome", "created_at"},
        "/comparisons/*": {"name", "verdict", "method", "saved_at", "id"},
    },
    "run": {
        "": {"name", "run_id", "status", "done", "total", "created_at", "target", "backend", "t_unit", "horizon", "paired_with",
             "conditions", "axes", "replicates", "outcomes", "declared", "design_mde", "comparisons", "cells", "events"},
        "/cells/*": {"config", "n", "shares"},
        "/cells/*/shares/*": {"value", "lo", "hi", "level", "method"},
        "/events/*": {"at", "kind", "detail"},
    },
    "comparison": {
        "": {"verdict", "sentence", "method", "before", "after", "threshold", "family", "id", "events", "trades", "rows", "charts"},
        "/method": {"name", "words", "chosen"},
        "/threshold": {"value", "source"},
        "/family": {"tests", "conditions", "events", "q"},
        "/events/*": {"name", "kind", "n_worse", "n_safer", "n_unchanged", "n_could_not_tell", "n_conditions"},
        "/rows/*": {"config", "config_hash", "event", "share_a", "share_b", "rate_a", "rate_b", "delta", "p", "q", "verdict", "mde_rise", "mde_fall"},
        "/charts/*": {"kind", "event", "address"},
    },
    "condition": {
        "": {"events"},
        "/events/*": {"event", "verdict", "sentence", "share_a", "share_b", "k", "n", "delta", "ci", "test", "mde_rise", "mde_fall",
                      "mde_test", "mde_level", "mde_family", "mde_power", "mde_anchor", "charts"},
        "/events/*/ci": {"lo", "hi", "level", "basis"},
        "/events/*/test": {"name", "n01", "n10", "p", "q", "q_holm"},
        "/events/*/share_a": {"value", "lo", "hi", "level", "method"},
        "/events/*/share_b": {"value", "lo", "hi", "level", "method"},
    },
    "episodes": {
        "": {"verdict", "sentence", "run", "condition", "episodes", "reproduce"},
        "/episodes/*": {"replicate_index", "seed", "outcome", "t"},
    },
    "could_not_detect": {
        "": {"verdict", "sentence", "question", "n_unchanged", "n_could_not_tell", "flaggable", "p_min", "level", "family", "design_mde", "threshold", "rows"},
        "/rows/*": {"config", "event", "share_a", "mde_rise", "mde_fall", "could_tell"},
    },
    "chart": {"": {"kind", "event", "condition", "caption", "svg", "data", "source"}},
}


def _at(document: Any, path: str) -> list[Any]:
    """Every node a ``VIEW_FIELDS`` path names (``*`` over a list's items or a mapping's values)."""
    nodes = [document]
    for token in [t for t in path.split("/") if t]:
        nxt: list[Any] = []
        for node in nodes:
            if token == "*":
                nxt += list(node.values()) if isinstance(node, dict) else list(node) if isinstance(node, list) else []
            elif isinstance(node, dict) and token in node:
                nxt.append(node[token])
        nodes = nxt
    return nodes


@pytest.mark.parametrize("kind", list(VIEW_ADDRESSES))
def test_pf12_7_each_view_carries_the_fields_views_md_names_and_the_results_numbers(kind: str, request: pytest.FixtureRequest) -> None:
    """R42: each core view holds the fields ``views.md`` gives it (at least), so the terminal app (PF6)
    and the next stage's server read the same object; and the numbers in it are the result's: a
    comparison's rows and a condition's blocks are its cells' (p, q, Holm's p, the change, its interval
    and level, both limits, the shares and their bounds), the could-not-detect rows are exactly the
    unchanged rows with the could-not-tell rows first (Y20), the runs view lists runs newest first
    (section 18.3 item 1) and a run's shares are its Wilson intervals at the recorded level."""
    from poisson_prove import stats
    from poisson_prove.store import Store

    for store, page in _pages_by_kind(request, kind):
        view = view_document(store, page.address)
        for path, fields in VIEW_FIELDS[kind].items():
            for node in _at(view, path):
                if node is None:
                    continue
                assert isinstance(node, dict) and fields <= set(node), (page.address, path, sorted(fields - set(node if isinstance(node, dict) else {})))
        if kind == "runs":
            created = [r["created_at"] for r in view["runs"]]
            assert created == sorted(created, reverse=True), (page.address, created)
            assert {r["run_id"] for r in view["runs"]} == set(Store(store).runs())
        if kind == "run":
            run = page.address.removeprefix("runs/").removesuffix(".html")
            frame = Store(store).read(run)
            for cell in view["cells"]:
                rows = frame[(frame["config_hash"] == config_hash_of(cell["config"])) & frame["outcome"].notna()]
                for outcome, share in cell["shares"].items():
                    if not len(rows):  # every run of the condition errored: no share to show
                        assert share["value"] is None, (page.address, outcome, share)
                        continue
                    k = int((rows["outcome"] == outcome).sum())
                    w = stats.wilson(k, len(rows))
                    assert (share["value"], share["lo"], share["hi"], share["level"]) == (k / len(rows), w.lo, w.hi, stats.WILSON_LEVEL), (page.address, outcome, share)
        if kind in ("comparison", "condition", "could_not_detect"):
            result = _comparisons(store)[_cid(page.address)]
            cells = {(e, str(c["config_hash"])): c for e, entry in result["by_event"].items() for c in entry["cells"]}
        if kind == "comparison":
            assert {(r["event"], str(r["config_hash"])) for r in view["rows"]} == set(cells)
            for row in view["rows"]:
                cell = cells[(row["event"], str(row["config_hash"]))]
                assert [row[k] for k in ("delta", "p", "q", "mde_rise", "mde_fall", "verdict")] == [cell[k] for k in ("delta", "p", "q", "mde_rise", "mde_fall", "verdict")], (page.address, row)
        if kind == "condition":
            h = page.address.rsplit("/", 1)[-1].removesuffix(".html")
            assert {b["event"] for b in view["events"]} == {e for e, ch in cells if ch == h}
            for block in view["events"]:
                cell = cells[(block["event"], h)]
                assert (block["test"]["p"], block["test"]["q"], block["test"]["q_holm"]) == (cell["p"], cell["q"], cell["q_holm"]), (page.address, block["test"])
                assert (block["ci"]["lo"], block["ci"]["hi"], block["ci"]["level"]) == (cell["ci_lo"], cell["ci_hi"], cell["ci_level"]), (page.address, block["ci"])
                assert (block["delta"], block["mde_rise"], block["mde_fall"]) == (cell["delta"], cell["mde_rise"], cell["mde_fall"]), page.address
                for side in ("a", "b"):
                    assert {k: block[f"share_{side}"][k] for k in ("value", "lo", "hi", "level")} == {k: cell[f"share_{side}"][k] for k in ("value", "lo", "hi", "level")}, (page.address, side)
        if kind == "could_not_detect":
            unchanged = {key for key, c in cells.items() if c["verdict"] == "unchanged"}
            assert {(r["event"], config_hash_of(r["config"])) for r in view["rows"]} == unchanged, page.address
            tells = [bool(r["could_tell"]) for r in view["rows"]]
            assert tells == sorted(tells), (page.address, tells)  # could-not-tell rows first (Y20)


def _level(level: float) -> str:
    """A level as every surface prints it: a percentage to at most three decimals (PF4.42)."""
    return f"{100 * level:.3f}".rstrip("0").rstrip(".") + "%"


def _power_words() -> str:
    from poisson_prove import stats

    f = fractions.Fraction(stats.POWER).limit_denominator(20)
    return f"{f.numerator} times in {f.denominator}"


TEST_WORDS = {"fisher_bh": "Fisher", "mcnemar_bh": "McNemar", "logrank_bh": "log-rank"}
INTERVAL_WORDS = {"miettinen-nurminen": "Miettinen-Nurminen", "tango": "Tango"}


def _cid(address: str) -> str:
    return address.split("/")[1].removesuffix(".html")


DESIGN_TESTS = {"fisher": "Fisher", "mcnemar": "McNemar", "logrank": "log-rank"}


def _required_words(kind: str, address: str, store: Path, comparisons: dict[str, dict[str, Any]]) -> list[str]:
    """What a page of this kind must state of the method, the levels and the limits it shows."""
    if kind in ("runs", "episodes"):
        return []
    if kind == "run":
        from poisson_prove import stats
        from poisson_prove.store import Store

        run = address.removeprefix("runs/").removesuffix(".html")
        words = [_level(stats.WILSON_LEVEL)] if Store(store).read(run)["outcome"].notna().any() else []
        design = (json.loads((store / run / "manifest.json").read_text(encoding="utf-8")).get("environment") or {}).get("design_mde")
        if isinstance(design, dict) and design.get("test") in DESIGN_TESTS:
            words += [DESIGN_TESTS[design["test"]], _power_words()]
        return words
    result = comparisons[_cid(address)]
    method, tests = result["method"], f"over {result['n_tests']} tests"
    cells = [c for e in result["by_event"].values() for c in e["cells"]]
    wilson = _level(cells[0]["share_a"]["level"])
    interval = [_level(result["interval_level"]), *sorted({INTERVAL_WORDS[c["ci_method"]] for c in cells if c["ci_method"]})]
    rule = ["false coverage", "Benjamini-Yekutieli"] if result["n_rejected"] else ["simultaneous", "Bonferroni"]
    flags = ["Benjamini", "Hochberg", "false discovery rate"]
    verdict = ["Holm", "family-wise"]
    hazard = ["cause-specific hazard"] if method == "logrank_bh" else []
    limits = [_power_words(), "rise", "fall"]
    name = address.rsplit("/", 1)[-1]
    if kind == "comparison":
        return [TEST_WORDS[method], tests, *flags, *verdict, *interval, *rule, wilson, *limits, *hazard]
    if kind == "condition":
        return [TEST_WORDS[method], tests, *flags, "Holm", *interval, wilson, *limits, *hazard]
    if kind == "could_not_detect":
        return [TEST_WORDS[method], tests, "Holm", _power_words(), f"{result['threshold']:.3f}", *hazard]
    if name.startswith("differences-"):
        return [TEST_WORDS[method], *interval, *rule, *hazard]
    if name.startswith("limits-"):
        return [TEST_WORDS[method], tests, _power_words(), f"{result['threshold']:.3f}", *hazard]
    if name.startswith("heatmap-"):
        return [TEST_WORDS[method], tests, *flags, *hazard]
    return [name.removeprefix("incidence-").removesuffix(".html")]


@pytest.mark.parametrize("kind", list(VIEW_ADDRESSES))
def test_pf12_7_every_page_states_the_method_levels_and_limits_it_shows(kind: str, request: pytest.FixtureRequest) -> None:
    """PF12.7, and PF4.35, PF4.41 and PF4.42 on the static UI: a page that shows a comparison's rows
    names the test, the family (``over M tests``), the flags' rule (Benjamini-Hochberg, the false
    discovery rate) beside the verdict's (Holm, family-wise), each interval's method, level and rule,
    the shares' Wilson level, the limits' power and both directions; log-rank says it tests the
    cause-specific hazard; a chart's page what its chart shows. The runs view names each saved
    comparison's word and test."""
    for store, page in _pages_by_kind(request, kind):
        comparisons = _comparisons(store)
        text = page.body_text()
        for words in _required_words(kind, page.address, store, comparisons):
            assert says(text, words), (page.address, words)
        if kind == "runs":
            for result in comparisons.values():
                assert says(text, TEST_WORDS[result["method"]]) and result["verdict"] in text, (page.address, result["verdict"])


def _block_of(node: Node) -> Node:
    for ancestor in node.ancestors():
        if ancestor.tag in ("p", "li", "tr", "dd", "dt", "h1", "h2", "h3", "h4", "h5", "h6", "caption", "figcaption"):
            return ancestor
    raise AssertionError(node.tag)


def _nodes_saying(page: Page, words: str) -> list[Node]:
    """The innermost elements whose own text says the words."""
    found = [n for n in page.root.find_all("body")[0].iter() if n.tag not in NOT_FACTS and says(n.text(), words)]
    return [n for n in found if not any(isinstance(c, Node) and says(c.text(), words) for c in n.children)]


def _run_name(store: Path, run_id: str) -> str:
    (name,) = [r["run_name"] for r in doc(cli(store, "runs", "--json"))["runs"] if r["run_id"] == run_id]
    return name


#: (pair, the page kinds that must carry it, what they say).
VERDICT_FACTS = [
    ("quickstart", ("comparison", "could_not_detect"), "the word mixed, first"),
    ("trade", ("comparison", "could_not_detect"), "the word trade, first, and the fragility"),
    ("nothing", ("comparison", "could_not_detect", "runs"), "no significant change with its limit on the same line"),
    ("tiny", ("comparison", "could_not_detect"), "too small to tell"),
    ("peeking", ("comparison", "could_not_detect"), "the peeking caveat naming the run"),
    ("errors", ("comparison", "could_not_detect"), "the errored-episodes warning"),
    ("logrank", ("comparison", "condition", "could_not_detect", "chart"), "the cause-specific hazard, and the shifted outcome"),
]


@pytest.mark.parametrize("pair, kinds, what", VERDICT_FACTS, ids=[c[0] for c in VERDICT_FACTS])
def test_pf12_7_the_verdict_facts_reach_every_page_that_shows_the_verdict(pair: str, kinds: tuple[str, ...], what: str, old_world: Any, stats_world: Any) -> None:
    """What section 18.3 lists for the comparison view, from PF4's build: the Holm-based word first
    (R31), the fragility, ``no significant change`` always with its verdict limit on the same line
    (PF4.40, R25), the peeking caveat (PF4.39), the errored-episodes warning (PF4.46) and log-rank as
    the cause-specific hazard with its shifted outcomes (PF4.41), on every page that shows them."""
    if pair == "quickstart":
        store, cid = _store(old_world), old_world[1]["comparison"]
    else:
        store, cid = _store(stats_world), stats_world[1]["pairs"][pair]["comparison"]
    ui = _ui(store)
    result = _comparisons(store)[cid]
    if pair == "quickstart":
        assert result["verdict"] == "mixed"
    addresses = {
        "comparison": [f"comparisons/{cid}.html"],
        "could_not_detect": [f"comparisons/{cid}/could-not-detect.html"],
        "runs": ["index.html"],
        "condition": [f"comparisons/{cid}/{h}.html" for h in _hashes(result)],
        "chart": [f"comparisons/{cid}/{c}-{e}.html" for c in CHARTS for e in result["by_event"]],
    }
    for kind in kinds:
        for address in addresses[kind]:
            page = read_page(ui, ui / address)
            text = page.body_text()
            if kind in ("comparison", "could_not_detect"):
                main = page.root.find_all("main")
                assert main, address
                facts = [n for n in main[0].iter() if "data-fact" in n.attrs]
                assert facts and json.loads(facts[0].attrs["data-value"]) == result["verdict"], (address, facts[:1] and facts[0].attrs)
            if pair == "trade" and kind == "comparison":
                assert says(text, "fragility") and str(result["fragility"]) in text, address
            if pair == "nothing":
                assert result["verdict"] == "no significant change" and result["verdict_limit"] is not None
                lines = _nodes_saying(page, "no significant change")
                assert lines, address
                for node in lines:
                    assert f"{result['verdict_limit']:.3f}" in _block_of(node).text(), (address, _block_of(node).text())
                if kind == "comparison":  # nothing flagged: the intervals are simultaneous (PF4.42)
                    assert says(text, "simultaneous") and says(text, "Bonferroni"), address
            if pair == "tiny":
                assert result["verdict"] == "too small to tell" and "too small to tell" in text, address
            if pair == "peeking":
                (entry,) = result["peeking"]
                assert says(text, "peeking") and _run_name(store, entry["run_id"]) in text, address
            if pair == "errors":
                assert result["errors_differ"] and says(text, "errored"), address
            if pair == "logrank":
                assert says(text, "cause-specific hazard"), address
                if kind == "condition" and address.endswith(f"{config_hash_of({'cell': 'c1'})}.html"):
                    assert "slow" in text and says(text, "need not move together"), address


# ---------- PF12.8 nothing from the network ----------

URL_ATTRIBUTES = ("href", "src", "srcset", "action", "formaction", "data", "poster", "xlink:href", "background", "cite", "longdesc", "manifest")
FORBIDDEN_JS = ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "import(", "importScripts", "http://", "https://")


def _bundle_files(ui: Path) -> list[Path]:
    return sorted(p for p in ui.rglob("*") if p.is_file() and p.suffix != ".html")


def _css_urls(text: str) -> list[str]:
    return re.findall(r"url\(\s*['\"]?([^'\")]+)", text) + re.findall(r"@import\s+['\"]?([^'\";\s]+)", text)


@pytest.mark.parametrize("world", WORLDS)
def test_pf12_8_nothing_loads_from_the_network_and_every_link_is_relative_and_resolves(world: str, request: pytest.FixtureRequest) -> None:
    """No ``src``, ``href``, ``url()`` or import names an ``http://`` or ``https://`` address, a
    protocol-relative ``//`` one or an absolute path; no page has an inline script or an ``on…``
    handler; the script fetches nothing; every font and script is the bundle's; every link inside the
    UI is relative and lands on a page or anchor that exists (section 16.3 item 6). The artifacts'
    SVG files reference nothing outside themselves. (SVG's ``xmlns`` and text a page shows are not
    loads.)"""
    store = _store(_world(world, request))
    ui = _ui(store)
    anchors: dict[Path, set[str]] = {}
    for path in pages_of(ui):
        page = read_page(ui, path)
        anchors[path.resolve()] = {attrs["id"] for _, attrs in page.tags if "id" in attrs}
    for path in pages_of(ui):
        page = read_page(ui, path)
        for tag, attrs in page.tags:
            for name in attrs:
                assert not name.startswith("on"), (page.address, tag, name)
            if tag == "script":
                assert attrs.get("src"), (page.address, "inline script")
            if tag == "link":
                assert attrs.get("rel") in ("stylesheet", "icon"), (page.address, attrs)
            for name in URL_ATTRIBUTES:
                value = attrs.get(name)
                if value is None or (tag == "svg" and name == "xmlns"):
                    continue
                for part in value.split(",") if name == "srcset" else [value]:
                    part = part.strip().split(" ")[0]
                    assert not re.match(r"^([a-z][a-z0-9+.-]*:|//|/)", part, re.IGNORECASE) or part.startswith(("data:", "#")), (page.address, tag, name, part)
                    if part.startswith("data:"):
                        assert tag in ("img", "link"), (page.address, tag, part[:30])
                        continue
                    target, anchor = _target(page, part, ui)
                    if part.startswith("#"):
                        target = page.path.resolve()
                    assert target.is_relative_to(ui.resolve()) and target.is_file(), (page.address, part)
                    if anchor and target.suffix == ".html":
                        assert anchor in anchors[target], (page.address, part)
        for style in page.root.find_all("style"):
            css = " ".join(c for c in style.children if isinstance(c, str))
            assert all(u.startswith(("data:", "#")) for u in _css_urls(css)), (page.address, _css_urls(css))
    for path in _bundle_files(ui):
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".css":
            loads = re.sub(r"http://www\.w3\.org/2000/svg", "", text)  # a data: image's namespace is not a load
            assert "@font-face" not in text and "http:" not in loads and "https:" not in loads, path.name
            assert all(not re.match(r"^([a-z]+:|//|/)", u) or u.startswith("data:") for u in _css_urls(text)), (path.name, _css_urls(text))
        elif path.suffix == ".js":
            assert not [w for w in FORBIDDEN_JS if w in text], (path.name, [w for w in FORBIDDEN_JS if w in text])
    for svg in (store / ".poisson" / "artifacts").rglob("*.svg"):
        text = svg.read_text(encoding="utf-8")
        refs = re.findall(r"(?:href|src)\s*=\s*\"([^\"]*)\"", text) + _css_urls(text)
        assert all(r.startswith("#") for r in refs), (svg.name, refs)


def _csp(page: Page) -> dict[str, list[str]]:
    metas = [(i, attrs) for i, (tag, attrs) in enumerate(page.tags) if tag == "meta" and attrs.get("http-equiv", "").lower() == "content-security-policy"]
    assert len(metas) == 1, (page.address, metas)
    position, attrs = metas[0]
    loads = [i for i, (tag, a) in enumerate(page.tags) if tag in ("link", "script", "style")]
    assert not loads or position < min(loads), (page.address, "the policy comes after a style or script")
    directives: dict[str, list[str]] = {}
    for part in attrs["content"].split(";"):
        words = part.split()
        if words:
            directives[words[0].lower()] = words[1:]
    return directives


@pytest.mark.parametrize("world", WORLDS)
def test_pf12_8_every_page_carries_a_policy_that_allows_only_the_bundle(world: str, request: pytest.FixtureRequest) -> None:
    """Y16: one ``Content-Security-Policy`` meta on every page, before any style or script, allowing
    only the bundle's own files (R37): ``default-src 'none'``; scripts ``'self'``; styles ``'self'`` and
    inline; images ``'self'`` and ``data:``; no host, no scheme but ``data:``, no ``'unsafe-eval'``."""
    ui = _ui(_store(_world(world, request)))
    allowed = {"script-src": {"'self'"}, "style-src": {"'self'", "'unsafe-inline'"}, "img-src": {"'self'", "data:"}, "font-src": {"'self'"}}
    for path in pages_of(ui):
        page = read_page(ui, path)
        policy = _csp(page)
        assert policy.get("default-src") == ["'none'"], (page.address, policy)
        assert "'self'" in policy.get("script-src", []) and "'self'" in policy.get("style-src", []), (page.address, policy)
        for directive, sources in policy.items():
            if directive in ("default-src", "base-uri", "form-action", "frame-ancestors", "connect-src", "object-src", "frame-src", "child-src", "worker-src", "media-src", "manifest-src"):
                assert sources == ["'none'"], (page.address, directive, sources)
            else:
                assert set(sources) <= allowed.get(directive, set()), (page.address, directive, sources)


# ---------- PF12.9 the never-list ----------


def _strings_in(path: Path) -> str:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        return "\n".join(str(v) for column in table.columns for v in column.to_pylist() if v is not None) + "\n" + "\n".join(table.column_names)
    return path.read_text(encoding="utf-8", errors="replace")


def _forbidden(store: Path, world: dict[str, Any]) -> dict[str, str]:
    """What no page and no artifact may hold for this store (PF4.11 extended): where the store is, the
    platform and Python build strings (this interpreter's and the ones the runs recorded), every target
    import path a run recorded, and the keys planted while the store was built."""
    import platform

    out = {"the store's path": str(store), "the store's real path": str(store.resolve()), "the store's parent": str(store.parent),
           "this platform": platform.platform(), "this Python build": sys.version}
    for manifest in store.glob("*/manifest.json"):
        environment = json.loads(manifest.read_text(encoding="utf-8")).get("environment") or {}
        for key in ("platform", "python", "import_path"):
            if environment.get(key):
                out[f"{manifest.parent.name}'s {key}"] = str(environment[key])
    out |= {f"the planted {k}": v for k, v in PLANTED_KEYS.items()}
    for i, text in enumerate(sorted(_captured(store))):
        out[f"captured content {i}"] = text
    return out


def _captured(store: Path) -> set[str]:
    """The content a run captured: every string of its stored observations (``trace_obs``) and of its
    spans' content attributes (``poisson_prove.trace``'s public ``CONTENT_KEYS``), eight characters
    or more. No run here set ``content = true`` for a view, so none may show (section 18.3)."""
    import pyarrow.parquet as pq

    from poisson_prove.trace import CONTENT_KEYS, OBSERVATION_KEYS

    found: set[str] = set()

    def strings(node: Any) -> None:
        if isinstance(node, str):
            if len(node) >= 8:
                found.add(node)
        elif isinstance(node, dict):
            for value in node.values():
                strings(value)
        elif isinstance(node, list):
            for value in node:
                strings(value)

    for part in store.glob("*/episodes/*.parquet"):
        table = pq.read_table(part)
        for column in ("trace_obs", "trace"):
            if column not in table.column_names:
                continue
            for raw in table.column(column).to_pylist():
                if not raw:
                    continue
                doc_ = json.loads(raw) if isinstance(raw, str) else raw
                if column == "trace_obs":
                    strings(doc_)
                else:
                    for span in doc_.get("spans", []):
                        for key, value in (span.get("attrs") or {}).items():
                            if key in CONTENT_KEYS or key in OBSERVATION_KEYS:
                                strings(value)
    return found


@pytest.mark.parametrize("world", WORLDS)
def test_pf12_9_no_page_or_artifact_holds_a_path_platform_python_build_import_path_or_key(world: str, request: pytest.FixtureRequest, tmp_path: Path) -> None:
    """Section 18.3's never-list over every file under ``.poisson/`` (pages, bundle, descriptors,
    results, tables, charts) and over ``ui --json``, whose ``location`` is the one exempt field: it is
    the address a person opens, so it must say where the store is. Captured content too: the 0.0.1
    store's capture run stored a tool result, which no page shows. (The episodes page shows
    ``rollout(cfg, seed=…)`` and names ``poisson-prove inspect`` for the import line: Y11.)"""
    store_world = _world(world, request)
    store = _store(store_world)
    forbidden = _forbidden(store, store_world[1])
    for path in sorted((store / ".poisson").rglob("*")):
        if path.is_file():
            text = _strings_in(path)
            held = [what for what, value in forbidden.items() if value and value in text]
            assert held == [], (path.relative_to(store).as_posix(), held)
    copy = copy_store(store, tmp_path / "prove-runs")  # the shared store is never written to
    located = doc(cli(copy, "ui", "--json"))
    assert located["location"].startswith("file:///")
    forbidden |= {"the copy's path": str(copy), "the copy's real path": str(copy.resolve())}
    text = json.dumps({k: v for k, v in located.items() if k != "location"})
    assert [what for what, value in forbidden.items() if value in text] == []


def test_pf12_9_the_pages_do_not_depend_on_where_the_store_is(old_world: Any, tmp_path: Path) -> None:
    """The same records give the same page bytes wherever the store sits, and whether ``--store`` was
    given as an absolute path or relative to the working folder (R26, R28)."""
    near = copy_store(_store(old_world), tmp_path / "a" / "prove-runs")
    far = copy_store(_store(old_world), tmp_path / "b" / "c" / "d" / "prove-runs")
    for root in (near, far):
        shutil.rmtree(_ui(root))
    assert cli(near, "ui").code == 0
    assert cli("prove-runs", "ui", cwd=far.parent).code == 0
    assert listing(_ui(near)) == listing(_ui(far))


# ---------- PF12.10 charts ----------


def _svg_root(text: str) -> Node:
    from pf12_support import _Builder

    builder = _Builder()
    builder.feed(text)
    (svg,) = [n for n in builder.root.children if isinstance(n, Node) and n.tag == "svg"]
    return svg


def _hexes(text: str) -> set[str]:
    return {h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}\b", text)}


#: Colour forms a chart may not use: its colours are the look's tokens, as six-hex values or ``var()``.
OTHER_COLOURS = re.compile(r"\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(|#[0-9a-fA-F]{3,4}\b(?![0-9a-fA-F])|(?:fill|stroke|color)\s*[:=]\s*[\"']?(red|green|blue|black|white|gray|grey|orange|purple|yellow)\b", re.IGNORECASE)
MARKS = ("rect", "circle", "path", "polyline", "polygon", "line", "ellipse")


def _chart_files(store: Path) -> list[Path]:
    return sorted((store / ".poisson" / "artifacts" / "comparison").rglob("*.svg"))


@pytest.mark.parametrize("world", ["old", "stats"])
def test_pf12_10_every_chart_is_proves_own_svg_with_a_title_a_text_alternative_and_its_data(world: str, request: pytest.FixtureRequest) -> None:
    """Each chart is an SVG Prove drew (R29): ``title`` and ``desc`` first, ``role="img"`` and
    ``aria-labelledby`` naming both, nothing outside itself, numbers per rule 10 (R30), the look's
    chart tokens only (never the four meanings' colours, Y13); and its page shows it inline, the
    artifact's own file, with its data as a table beside it (Y19)."""
    store = _store(_world(world, request))
    tokens = look_tokens()
    allowed = {v for t in CHART_TOKENS for v in tokens[t]}
    meanings = {v for t in MEANING_TOKENS for v in tokens[t]}
    charts = _chart_files(store)
    assert charts
    for path in charts:
        text = path.read_text(encoding="utf-8")
        svg = _svg_root(text)
        assert svg.attrs.get("xmlns") == "http://www.w3.org/2000/svg" and svg.attrs.get("role") == "img", path
        elements = [c for c in svg.children if isinstance(c, Node)]
        title, desc = elements[0], elements[1]
        assert (title.tag, desc.tag) == ("title", "desc"), path
        title_text = " ".join(c for c in title.children if isinstance(c, str)).strip()
        desc_text = " ".join(c for c in desc.children if isinstance(c, str)).strip()
        assert title_text and desc_text, path
        assert set(svg.attrs.get("aria-labelledby", "").split()) == {title.attrs.get("id"), desc.attrs.get("id")} and None not in {title.attrs.get("id"), desc.attrs.get("id")}, path
        tags = {n.tag for n in svg.iter()}
        assert not tags & {"script", "foreignobject", "image", "iframe", "a"}, (path.name, tags)
        assert "matplotlib" not in text.lower(), path
        for node in svg.iter():
            if node.tag == "text":
                for token in re.findall(r"[+\-−]?\d[\d,]*(?:\.\d+)?(?:e[+\-−]?\d+)?%?", node.text()):
                    assert re.match(r"^[+\-−]?(\d{1,3}(,\d{3})*|\d+)(\.\d{1,3})?%?$", token) or re.match(r"^\d\.\de[+\-−]\d\d$", token), (path.name, token)
        assert not (_hexes(text) & meanings), (path.name, _hexes(text) & meanings)
        assert _hexes(text) <= allowed, (path.name, _hexes(text) - allowed)
        assert not set(re.findall(r"var\((--[a-z]+)", text)) & set(MEANING_TOKENS), path.name
        assert not OTHER_COLOURS.search(text), (path.name, OTHER_COLOURS.search(text))
        # The look's chart rules: solid hairlines, never dashed; every mark but an axis or a threshold
        # line carries a hover title; direction shown by shape as well as colour (a rise marked ▲, a
        # fall ▼); a threshold written on its line; the first run in --dim, the second in --after.
        assert "dasharray" not in text, path.name
        for node in svg.iter():
            if node.tag in MARKS and node.tag != "line":
                assert any(isinstance(c, Node) and c.tag == "title" for c in node.children), (path.name, node.tag, node.attrs)
        name = path.name.split("-")[0]
        if name in ("differences", "limits"):
            cid = path.relative_to(store / ".poisson" / "artifacts" / "comparison").parts[0]
            event = path.stem.split("-", 1)[1]
            cells = _comparisons(store)[cid]["by_event"][event]["cells"]
            labels = " ".join(n.text() for n in svg.iter() if n.tag == "text")
            if name == "limits":
                assert "▲" in labels and "▼" in labels, path.name
                assert f"{_comparisons(store)[cid]['threshold']:.3f}" in labels, path.name
            else:
                if any(c["delta"] > 0 for c in cells):
                    assert "▲" in labels, path.name
                if any(c["delta"] < 0 for c in cells):
                    assert "▼" in labels, path.name
        if name == "incidence":
            assert (tokens["--dim"][0] in text.lower() or "var(--dim" in text) and (tokens["--after"][0] in text.lower() or "var(--after" in text), path.name
        cid = path.relative_to(store / ".poisson" / "artifacts" / "comparison").parts[0]
        relative = path.relative_to(store / ".poisson" / "artifacts" / "comparison" / cid / "charts").as_posix()
        page_path = _ui(store) / "comparisons" / cid / relative.replace(".svg", ".html")
        source = page_path.read_text(encoding="utf-8")
        inline = re.sub(r"^<\?xml[^>]*\?>\s*", "", text).strip()
        assert inline in source, page_path
        data = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        page = read_page(_ui(store), page_path)
        tables = page.root.find_all("table")
        assert tables, page_path
        table = tables[-1]
        header = [th.text() for th in table.find_all("th") if th.parent is not None and th.parent.tag == "tr"][: len(data["columns"])]
        assert header == [str(c) for c in data["columns"]], (page_path, header, data["columns"])
        body_rows = [tr for tr in table.find_all("tr") if tr.find_all("td")]
        assert len(body_rows) == len(data["rows"]), (page_path, len(body_rows), len(data["rows"]))


def test_pf12_10_interval_labels_come_from_the_level_the_comparison_recorded(stats_world: Any, tmp_path: Path) -> None:
    """PF4.1c on the charts: the differences chart labels its intervals with the level the saved
    comparison recorded, so the same pair at another ``q`` labels another level."""
    pair = stats_world[1]["pairs"]["trade"]
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    for q in ("0.05", "0.2"):
        r = cli(store, "diff", pair["a"], pair["b"], *pair["argv"], "--q", q, "--save")
        assert r.code == 0, r.err
    levels = {}
    for cid, result in _comparisons(store).items():
        if result["q"] in (0.05, 0.2) and len(result["by_event"]) == 1 and result["n_tests"] == 6:
            svg = (store / ".poisson" / "artifacts" / "comparison" / cid / "charts" / "differences-fell.svg").read_text(encoding="utf-8")
            levels[result["q"]] = (_level(result["interval_level"]), svg)
    assert set(levels) == {0.05, 0.2}
    (label_a, svg_a), (label_b, svg_b) = levels[0.05], levels[0.2]
    assert label_a != label_b
    assert label_a in svg_a and label_b not in svg_a and label_b in svg_b and label_a not in svg_b


SYSTEM_FONTS = {"system-ui", "-apple-system", "segoe ui", "sans-serif", "ui-monospace", "menlo", "consolas", "monospace", "inherit"}


def _dark_blocks(css: str) -> tuple[str, str]:
    """A style sheet split into what its ``prefers-color-scheme: dark`` media blocks hold and the rest."""
    dark, rest, i = [], [], 0
    for m in re.finditer(r"@media[^{]*prefers-color-scheme\s*:\s*dark[^{]*\{", css):
        if m.start() < i:
            continue
        rest.append(css[i:m.start()])
        depth, j = 1, m.end()
        while depth and j < len(css):
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        dark.append(css[m.end():j - 1])
        i = j
    rest.append(css[i:])
    return "".join(dark), "".join(rest)


def test_pf12_10_the_bundle_sets_the_looks_tokens_for_light_and_dark_and_only_the_systems_fonts(old_world: Any) -> None:
    """Y14 and Y15: the bundle's style sheets set each of the look's twelve colour tokens to its light
    value outside, and its dark value inside, a ``prefers-color-scheme: dark`` block (the pages follow the
    system's theme), and name no font but the system's."""
    css = "\n".join(p.read_text(encoding="utf-8") for p in _bundle_files(_ui(_store(old_world))) if p.suffix == ".css")
    assert css
    dark, light = _dark_blocks(css)
    for token, (light_value, dark_value) in look_tokens().items():
        assert re.search(rf"{re.escape(token)}\s*:\s*{light_value}\b", light, re.IGNORECASE), (token, light_value)
        assert re.search(rf"{re.escape(token)}\s*:\s*{dark_value}\b", dark, re.IGNORECASE), (token, dark_value)
    for families in re.findall(r"font-family\s*:\s*([^;}]+)", css) + re.findall(r"\bfont\s*:[^;}]*?\d+px(?:/[\d.]+)?\s+([^;}]+)", css):
        names = {f.strip().strip("'\"").lower() for f in families.split(",")}
        assert names <= SYSTEM_FONTS, names - SYSTEM_FONTS


# ---------- PF12.11 old stores ----------


def test_pf12_11_a_0_0_1_store_renders_every_view_and_says_its_events_were_not_recorded(old_world: Any, stats_world: Any, sweep_world: Any) -> None:
    """Every 0.0.1 run, and every run written without a sweep, has its page saying its events were not
    recorded; a run 0.1.0 swept shows its event log instead. (That every view of the old store renders,
    with its facts, is the two tests above, over the old store.)"""
    for world in (old_world, stats_world):
        store = _store(world)
        for manifest in store.glob("*/manifest.json"):
            page = read_page(_ui(store), _ui(store) / "runs" / f"{manifest.parent.name}.html")
            assert says(page.body_text(), "events were not recorded"), page.address
    for run in sweep_world[1]["runs"].values():
        page = read_page(_ui(_store(sweep_world)), _ui(_store(sweep_world)) / "runs" / f"{run}.html")
        assert not says(page.body_text(), "events were not recorded"), page.address
    assert {kind_of(p.relative_to(_ui(_store(old_world))).as_posix()) for p in pages_of(_ui(_store(old_world)))} == set(VIEW_ADDRESSES)


# ---------- PF12.6 the ui verb, refreshing, the bundle ----------


def _location(result_out: str) -> str:
    first = result_out.splitlines()[0]
    m = re.match(r"^ok  dashboard at (file:///\S+)$", first)
    assert m, first
    return m.group(1)


def _path_of(uri: str) -> Path:
    return Path(urllib.request.url2pathname(urllib.parse.urlparse(uri).path))


def test_pf12_6_ui_builds_the_dashboard_and_prints_where_it_is(old_world: Any, tmp_path: Path) -> None:
    """``poisson-prove ui`` prints ``ok  dashboard at file://…/index.html`` (R17), the store's own
    index; ``--json`` carries the same address as ``location``; an empty store folder gets the empty
    runs view; a missing store is refused as ``runs`` refuses it, and nothing is made."""
    store = _store(old_world)
    built = old_world[1]["ui"]
    assert built["code"] == 0 and built["err"] == "", built
    uri = _location(built["out"])
    assert uri.endswith("/.poisson/ui/index.html") and _path_of(uri).samefile(_ui(store) / "index.html"), uri
    located = json.loads(old_world[1]["ui_json"]["out"])
    assert list(located)[:3] == ["schema", "verdict", "sentence"] and located["schema"] == "poisson-prove.ui/1" and located["verdict"] == "ok"
    assert located["location"] == uri and list(located)[-1] == "next"
    copy = copy_store(store, tmp_path / "copy" / "prove-runs")  # the shared store is never written to
    relative = cli("prove-runs", "ui", cwd=copy.parent)
    assert relative.code == 0 and _path_of(_location(relative.out)).samefile(_ui(copy) / "index.html")
    empty = tmp_path / "empty"
    empty.mkdir()
    r = cli(empty, "ui")
    assert r.code == 0 and first_word(r.out) == "ok" and (_ui(empty) / "index.html").is_file(), r.err
    missing = tmp_path / "missing"
    refused, runs = cli(missing, "ui"), cli(missing, "runs")
    assert (refused.code, runs.code) == (1, 1) and refused.err.splitlines()[0].startswith("error: "), refused.err
    assert not missing.exists()


def test_pf12_6_ui_open_calls_the_browser_opener_once_and_nothing_else_opens_it(old_world: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``ui --open`` opens the dashboard's address in the browser once; ``ui`` without it, and every
    other command, opens nothing (section 17.3: the core never opens a browser)."""
    import webbrowser

    calls: list[tuple[str, tuple[Any, ...]]] = []
    for name in ("open", "open_new", "open_new_tab"):
        monkeypatch.setattr(webbrowser, name, lambda *a, _n=name, **k: calls.append((_n, a)) or True)
    class Opener:
        def open(self, *a: Any, **k: Any) -> bool:
            calls.append(("get().open", a))
            return True

        open_new = open_new_tab = open

    monkeypatch.setattr(webbrowser, "get", lambda *a, **k: Opener())
    store = copy_store(_store(old_world), tmp_path / "prove-runs")
    opened = cli(store, "ui", "--open")
    assert opened.code == 0, opened.err
    assert len(calls) == 1 and calls[0][1][0] == _location(opened.out), calls
    calls.clear()
    for argv in (["ui"], ["ui", "--json"], ["diff", QS_A, QS_B, "--save"], ["runs"]):
        assert cli(store, *argv).code == 0
    assert calls == []


REFRESHING = ("sweep", "sweep --resume", "diff --save", "check --save", "report", "serve --json")


@pytest.mark.parametrize("has_ui", [True, False], ids=["with a UI", "without one"])
@pytest.mark.parametrize("verb", REFRESHING)
def test_pf12_6_every_writing_verb_refreshes_the_pages_and_says_nothing_about_it(verb: str, has_ui: bool, stats_world: Any, tmp_path: Path) -> None:
    """A command that writes a run or saves an artifact rebuilds the store's UI, so its pages show what
    the store now holds; the pages are derived files, so the refresh prints nothing (the one exception to
    rule 12). A store with no UI yet gets none from it: ``ui`` builds the first (reading R40)."""
    from pf12_support import LOOSE, MOCK, SMALL_SPEC

    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    work = tmp_path / "work"
    work.mkdir()
    spec = work / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    pair = stats_world[1]["pairs"]["grid"]
    a, b, ev = pair["a"], pair["b"], pair["argv"]
    shutil.rmtree(store / ".poisson" / "artifacts")
    if verb == "sweep --resume":
        stopped = cli(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--max-rollouts", "3", "--yes", *LOOSE, cwd=work)
        assert stopped.code == 3, stopped.err
    shutil.rmtree(_ui(store))
    if has_ui:
        assert cli(store, "ui").code == 0
    before = listing(_ui(store)) if has_ui else {}
    argv = {
        "sweep": ["sweep", spec, "--target", f"{MOCK}:rollout", "--yes", *LOOSE],
        "sweep --resume": ["sweep", spec, "--resume", "--yes", *LOOSE],
        "diff --save": ["diff", a, b, *ev, "--save"], "check --save": ["check", a, b, *ev, "--save"],
        "report": ["report", a, b, *ev, "--x", "task", "--y", "rate", "--out", str(work / "r")],
        "serve --json": ["serve", a, b, *ev, "--x", "task", "--y", "rate", "--json"],
    }[verb]
    r = cli(store, *argv, cwd=work)
    assert r.code in (0, 4), r.err
    for text in (r.out, r.err):
        assert ".poisson/ui" not in text and "dashboard" not in text, text[-400:]
    if not has_ui:
        assert not _ui(store).exists()
        return
    built = {p.relative_to(_ui(store)).as_posix() for p in pages_of(_ui(store))}
    assert built == expected_pages(store), sorted(built ^ expected_pages(store))[:10]
    if verb != "check --save":  # a check has no page (R22); every other write changes a page at least
        assert listing(_ui(store)) != before, verb


def _package_files() -> dict[str, list[bytes]]:
    from importlib import resources

    found: dict[str, list[bytes]] = {}

    def walk(node: Any) -> None:
        for child in node.iterdir():
            if child.is_dir():
                walk(child)
            elif child.is_file() and child.name != "__pycache__":
                found.setdefault(child.name, []).append(child.read_bytes())

    walk(resources.files("poisson_prove"))
    return found


def test_pf12_6_the_fixed_bundle_files_are_the_packages_bytes(old_world: Any) -> None:
    """Every file of the UI that is not a page is copied from the package byte for byte (R18), at
    least the style sheet and the script; the wheel check below reads the built wheel itself."""
    bundle = _bundle_files(_ui(_store(old_world)))
    names = {p.name for p in bundle}
    assert {"style.css", "ui.js"} <= names, names
    package = _package_files()
    for path in bundle:
        assert package.get(path.name) == [path.read_bytes()], (path.name, len(package.get(path.name, [])))


@pytest.mark.slow
def test_pf12_6_the_fixed_bundle_files_equal_the_wheels_bytes(old_world: Any, tmp_path: Path) -> None:
    """The same, against the wheel built from this checkout: each fixed file is one entry under
    ``poisson_prove/`` with the same bytes. (Two tests for one invariant: building the wheel is slow.)"""
    uv = shutil.which("uv")
    assert uv is not None, "the wheel is built with uv"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env.update(UV_PYTHON_PREFERENCE="only-system", UV_PYTHON_DOWNLOADS="never")
    built = subprocess.run([uv, "build", "--wheel", "--out-dir", str(tmp_path), str(ROOT)], env=env, capture_output=True, text=True, timeout=600)
    assert built.returncode == 0, built.stderr
    (wheel,) = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as z:
        entries = {}
        for info in z.infolist():
            if info.filename.startswith("poisson_prove/"):
                entries.setdefault(info.filename.rsplit("/", 1)[-1], []).append(z.read(info))
    for path in _bundle_files(_ui(_store(old_world))):
        assert entries.get(path.name) == [path.read_bytes()], path.name


def _interrupted_build(store: Path, how: str) -> subprocess.CompletedProcess[str]:
    script = f"""
import os, sys
real_replace, real_rename = os.replace, os.rename
fired = []
def guard(real):
    def move(src, dst, *a, **k):
        d = os.fspath(dst)
        if not fired and os.path.basename(os.path.dirname(d)) == '.poisson' and os.path.basename(d).startswith('ui'):
            fired.append(dst)
            if {how!r} == 'killed':
                os._exit(70)
            raise KeyboardInterrupt
        return real(src, dst, *a, **k)
    return move
os.replace, os.rename = guard(real_replace), guard(real_rename)
from poisson_prove import cli
sys.exit(cli.main(sys.argv[1:]))
"""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(SRC), str(TESTS)])}
    return subprocess.run([sys.executable, "-c", script, "--store", str(store), "ui"], capture_output=True, text=True, env=env, timeout=300)


@pytest.mark.parametrize("how", ["ctrl-c", "killed"])
def test_pf12_6_an_interrupted_build_leaves_the_previous_pages(how: str, old_world: Any, tmp_path: Path) -> None:
    """Section 18.3: the pages are written beside and renamed in, so an interrupted build leaves the
    previous pages; after a kill, the previous pages or none, never a mix of two builds, and the next
    build is whole (R34)."""
    store = copy_store(_store(old_world), tmp_path / "prove-runs")
    index = _ui(store) / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace("</body>", "<!-- the previous build --></body>"), encoding="utf-8")
    previous = listing(_ui(store))
    stopped = _interrupted_build(store, how)
    assert stopped.returncode == (130 if how == "ctrl-c" else 70), (stopped.returncode, stopped.stderr[-500:])
    now = listing(_ui(store)) if _ui(store).exists() else {}
    if how == "ctrl-c":
        assert now == previous
        assert sorted(p.name for p in (store / ".poisson").iterdir()) == sorted(["store.json", "artifacts", "ui"])
    else:
        assert now in (previous, {}), sorted(set(now) ^ set(previous))[:5]
    rebuilt = cli(store, "ui")
    assert rebuilt.code == 0, rebuilt.err
    assert {p.relative_to(_ui(store)).as_posix() for p in pages_of(_ui(store))} == expected_pages(store)


# ---------- PF12.13 snapshots ----------

REFUND_055 = config_hash_of({"task_id": "refund", "tool_fail_rate": 0.55})
SNAPSHOT_PAGES = {
    "runs": "index.html",
    "run": f"runs/{QS_B}.html",
    "comparison": "comparisons/{cid}.html",
    "condition": "comparisons/{cid}/" + REFUND_055 + ".html",
    "episodes": f"runs/{QS_B}/episodes/timeout/{REFUND_055}.html",
    "could-not-detect": "comparisons/{cid}/could-not-detect.html",
    "chart": "comparisons/{cid}/heatmap-timeout.html",
}
assert len(SNAPSHOT_PAGES) <= 8  # section 10.6: at most eight


@pytest.mark.parametrize("name", list(SNAPSHOT_PAGES))
def test_pf12_13_snapshot(name: str, old_world: Any, request: pytest.FixtureRequest) -> None:
    """One page of the 0.0.1 quickstart pair, whole, against its snapshot (R23, R33); rewritten only by
    the documented command, and reviewed in the pull request."""
    store, cid = _store(old_world), old_world[1]["comparison"]
    address = SNAPSHOT_PAGES[name].format(cid=cid)
    text = normalise((_ui(store) / address).read_text(encoding="utf-8"), fixture_times(store)).replace(cid, "<comparison-id>")
    snapshot = SNAPSHOTS / f"{name}.html"
    if request.config.getoption("--update-snapshots"):
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(text, encoding="utf-8")
        return
    assert snapshot.is_file(), f"no snapshot {snapshot.relative_to(ROOT)}; write it with: {SNAPSHOT_COMMAND}"
    assert text == snapshot.read_text(encoding="utf-8"), f"{address} differs from {snapshot.relative_to(ROOT)}; if the change is meant, rewrite it with: {SNAPSHOT_COMMAND}"


def test_pf12_13_the_snapshots_are_few_and_written_only_by_the_documented_command() -> None:
    """At most eight, exactly the pages above, and ``CONTRIBUTING.md`` names the one command that
    rewrites them (section 10.6)."""
    assert sorted(p.name for p in SNAPSHOTS.iterdir()) == sorted(f"{n}.html" for n in SNAPSHOT_PAGES), sorted(p.name for p in SNAPSHOTS.iterdir()) if SNAPSHOTS.exists() else None
    contributing = ROOT / "CONTRIBUTING.md"
    assert contributing.is_file() and SNAPSHOT_COMMAND in contributing.read_text(encoding="utf-8")


# ---------- the browser check (slow) ----------

ENGINES = ("chromium", "firefox", "webkit")
#: Where Playwright keeps its browsers for this user, read before any test points ``HOME`` elsewhere.
BROWSERS = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or Path.home() / ("Library/Caches" if sys.platform == "darwin" else ".cache") / "ms-playwright")


def _launch(playwright: Any, engine: str) -> Any:
    kind = getattr(playwright, engine)
    try:
        return kind.launch()
    except Exception as exc:
        if engine == "chromium":
            # A cached headless shell of another Playwright build drives these pages as well.
            shells = sorted(BROWSERS.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
            if shells:
                return kind.launch(executable_path=str(shells[-1]))
        pytest.fail(f"Playwright's {engine} is not installed ({type(exc).__name__}); install it with: python -m playwright install {engine}")


def _rgb(value: str) -> str:
    return "rgb({}, {}, {})".format(*(int(value[i:i + 2], 16) for i in (1, 3, 5)))


@pytest.mark.slow
@pytest.mark.parametrize("engine", ENGINES)
def test_pf12_8_the_pages_open_offline_in_each_browser_without_sideways_scroll(engine: str, old_world: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Y16 and the render check: each snapshot page, opened from ``file://`` in Chromium, Firefox and
    WebKit (R24), light and dark, 390 and 1280 px wide, requests nothing but ``file:`` URLs, logs no
    error (a policy violation is one), never scrolls sideways, takes the look's background for its
    theme, shows every fact, and shows the same facts with the script off (the script only sorts and
    filters)."""
    from playwright.sync_api import sync_playwright

    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))
    store, cid = _store(old_world), old_world[1]["comparison"]
    tokens = look_tokens()
    with sync_playwright() as p:
        browser = _launch(p, engine)
        try:
            for name, address in SNAPSHOT_PAGES.items():
                url = (_ui(store) / address.format(cid=cid)).resolve().as_uri()
                seen: dict[bool, list[tuple[str, str]]] = {}
                for scheme in ("light", "dark"):
                    for width in (390, 1280):
                        for script in (True, False):
                            context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme, java_script_enabled=script)
                            page = context.new_page()
                            requests: list[str] = []
                            errors: list[str] = []
                            page.on("request", lambda r, seen=requests: seen.append(r.url))
                            page.on("console", lambda m, seen=errors: seen.append(m.text) if m.type == "error" else None)
                            page.on("pageerror", lambda e, seen=errors: seen.append(str(e)))
                            page.goto(url, wait_until="load")
                            assert all(u.startswith("file:") for u in requests), (engine, name, [u for u in requests if not u.startswith("file:")])
                            assert errors == [], (engine, name, scheme, width, errors)
                            scroll, inner = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
                            assert scroll <= inner, (engine, name, scheme, width, scroll, inner)
                            background = page.evaluate("getComputedStyle(document.body).backgroundColor")
                            assert background == _rgb(tokens["--bg"][0 if scheme == "light" else 1]), (engine, name, scheme, background)
                            hidden = page.evaluate("[...document.querySelectorAll('[data-fact]')].filter(e => !e.getClientRects().length || getComputedStyle(e).visibility === 'hidden').map(e => e.dataset.fact)")
                            assert hidden == [], (engine, name, scheme, width, hidden[:5])
                            facts = page.evaluate("[...document.querySelectorAll('[data-fact]')].map(e => [e.dataset.fact, e.dataset.value])")
                            seen.setdefault(script, facts) if width == 1280 and scheme == "light" else None
                            context.close()
                assert sorted(map(tuple, seen[True])) == sorted(map(tuple, seen[False])), (engine, name)
        finally:
            browser.close()
