"""The comparison page's heatmap panels do not clip their charts (issue 31).

**The defect.** Each heatmap's panel hides what overflows it, and the chart is 30 to 36 px wider than
the panel at 1,280, 1,440 and 1,920 wide, so the last column is cut at the panel's edge with no scroll.

**What is pinned.** The page ``poisson-prove ui`` writes for a comparison, opened in a browser, measured
and hit-tested. Nothing here reads the stylesheet: a panel may grow, the chart may shrink, or the panel
may scroll.

**Readings this file fixes.**

- **r1** "At least as wide as its chart, or scrolls" means: the chart's whole box fits inside the panel;
  or the panel, or something between it and the chart, scrolls sideways far enough to show all of it.
- **r2** Beyond the box, every cell and every label the chart draws can be reached: inside every box
  that clips it, or by a scroller's scrolling. And the last column's far edge answers a hit test as part
  of the chart once the page is scrolled to it, which no measurement of boxes can fake.
  Nor may a chart fit by shrinking away: it stays within 15% of its panel's width, or at 540 px or
  more, its cells being unreadable well before that. The chart stops at about 600 px on a wide panel.
- **r3** The widths are 1,280, 1,440 and 1,920, and phone width is 390 and 375, with the shapes of chart
  a comparison can have: two events side by side, one event alone, two axes, and one axis wrapped into
  rows of six.
- **r4** The first-screen rule 0.2.0 shipped still holds on every one of these pages at 1,280 by 800: the
  verdict above, at least half of every heatmap in view with no scrolling, two events side by side.
  ``test_comparison_first_screen.py`` holds the example at 1,280 and 1,440; this adds the other shapes,
  because a fix that widens a panel past half the page would stack the two and push the second down.
- **r5** A phone is held to no clipping and no sideways scroll of the page, and not to the first screen.
- **r6** Chromium holds every case; Firefox and WebKit hold one desktop and one phone width, as the
  dashboard's other browser check does.
- **r7** The same fault cuts other panels on main: at phone width the differences and limits charts on
  the comparison page and the charts on a condition's page. Held by one test of its own.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest
from pf12_support import SRC, copy_store, shared_world
from reading_support import QS_A, QS_B, cli, reading_world  # noqa: F401

BROWSERS = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or Path.home() / ("Library/Caches" if sys.platform == "darwin" else ".cache") / "ms-playwright")
DESKTOP = [(1280, 800), (1440, 900), (1920, 1080)]
PHONE = [(390, 844), (375, 812)]
SIZES = DESKTOP + PHONE
FIRST_SCREEN = (1280, 800)
SHAPES = ["two_events", "one_event", "two_axes", "wrapped"]

_TARGETS = """\
from poisson_prove import Episode


def rollout(cfg, seed):
    return Episode(outcome="violated" if seed % 2 == 0 else "completed", t=1, horizon=10, meta={})
"""
_TWO_AXES = """\
target_id = "agent"
t_unit = "tool_calls"
replicates = 3

[axes.load]
type = "continuous"
values = [1, 2, 3, 4, 5, 6]

[axes.mode]
type = "categorical"
values = ["a", "b", "c"]
"""
_WRAPPED = """\
target_id = "agent"
t_unit = "tool_calls"
replicates = 3

[axes.task]
type = "categorical"
values = ["t01", "t02", "t03", "t04", "t05", "t06", "t07", "t08", "t09", "t10"]
"""


def _sweeps(base: Path, spec: str) -> Path:
    """Two runs of ``spec`` in a folder of their own: the store they are in."""
    from reading_support import _prove

    base.mkdir(parents=True)
    (base / "panel_targets.py").write_text(_TARGETS, encoding="utf-8")
    (base / "spec.toml").write_text(spec, encoding="utf-8")
    for more in ((), ("--pair-with", "latest")):
        done = _prove(base, "sweep", "spec.toml", "--target", "panel_targets:rollout", "--yes", "--max-mde", "1", *more)
        assert done.returncode == 0, done.stderr[-800:]
    return base / "prove-runs"


def _page(store: Path, *more: str) -> str:
    saved = cli(store, "diff", *more, "--save")
    assert saved.code == 0, saved.err
    built = cli(store, "ui")
    assert built.code == 0, built.err
    found = list((store / ".poisson" / "ui" / "comparisons").glob("*.html"))
    assert len(found) == 1, found
    return str(found[0])


def _build(world: dict[str, Path], folder: Path) -> dict[str, Any]:
    assert SRC.is_dir()
    pages: dict[str, str] = {}
    for key, more in (("two_events", ()), ("one_event", ("--event", "violated"))):
        store = copy_store(world["old"], folder / key / "prove-runs")
        pages[key] = _page(store, QS_A, QS_B, *more)
    pages["two_axes"] = _page(_sweeps(folder / "two_axes", _TWO_AXES), "--event", "violated")
    pages["wrapped"] = _page(_sweeps(folder / "wrapped", _WRAPPED), "--event", "violated")
    return pages


@pytest.fixture(scope="module")
def pages(tmp_path_factory: pytest.TempPathFactory, reading_world: dict[str, Path]) -> dict[str, Path]:  # noqa: F811
    _, built = shared_world(tmp_path_factory, "heatmap-panels", lambda folder: _build(reading_world, folder))
    return {key: Path(path) for key, path in built.items()}


#: For each heatmap's panel: the chart's and the panel's widths, whether anything from the chart up to
#: the panel scrolls sideways, every drawn thing that lies past a box that hides it, and how far a
#: scroller can show. A box that hides overflow clips at its padding box.
_MEASURE = """
() => [...document.querySelectorAll('figure[id^="heatmap-"]')].map(panel => {
  const chart = panel.querySelector('svg');
  const between = [];
  for (let e = chart.parentElement; e; e = e.parentElement) { between.push(e); if (e === panel) break; }
  const scrollers = between.filter(e => /(auto|scroll)/.test(getComputedStyle(e).overflowX));
  const box = chart.getBoundingClientRect();
  const drawn = [...chart.querySelectorAll('rect, text')].map(e => e.getBoundingClientRect()).filter(r => r.width > 0);
  const right = Math.max(box.right, ...drawn.map(r => r.right));
  const left = Math.min(box.left, ...drawn.map(r => r.left));
  const clipped = [];
  let start = left, end = right;
  for (let e = chart.parentElement; e && e !== document.documentElement; e = e.parentElement) {
    const overflow = getComputedStyle(e).overflowX;
    const r = e.getBoundingClientRect();
    if (/(auto|scroll)/.test(overflow)) {
      const hidden = Math.max(0, end - (r.left + e.clientLeft + e.clientWidth)) ;
      if (e.scrollWidth - e.clientWidth < hidden - 0.5) {
        clipped.push({by: e.tagName + '#' + e.id, overflow, past: hidden, canScroll: e.scrollWidth - e.clientWidth});
      }
      start = r.left; end = r.right;
    } else if (/(hidden|clip)/.test(overflow)) {
      const inner = r.left + e.clientLeft, outer = inner + e.clientWidth;
      if (end > outer + 0.5 || start < inner - 0.5) {
        clipped.push({by: e.tagName + '#' + e.id, overflow, past: Math.max(end - outer, inner - start), clientWidth: e.clientWidth});
      }
    }
  }
  return {
    id: panel.id, chart: box.width, panel: panel.clientWidth,
    scrolls: scrollers.map(e => [e.tagName, e.clientWidth, e.scrollWidth]),
    clipped,
  };
})
"""

#: After scrolling any scroller and the page to the chart's far edge: the elements at the far edge of
#: the last column, in the middle of each row of cells, and whether the chart holds each.
_HIT = """
() => [...document.querySelectorAll('figure[id^="heatmap-"]')].map(panel => {
  const chart = panel.querySelector('svg');
  for (let e = chart.parentElement; e; e = e.parentElement) {
    if (/(auto|scroll)/.test(getComputedStyle(e).overflowX)) e.scrollLeft = e.scrollWidth;
    if (e === panel) break;
  }
  const cells = [...chart.querySelectorAll('rect.cell')];
  const far = Math.max(...cells.map(c => c.getBoundingClientRect().right));
  const last = cells.filter(c => Math.abs(c.getBoundingClientRect().right - far) < 1);
  const box = last[0].getBoundingClientRect();
  window.scrollTo(Math.max(0, box.left - innerWidth / 2), window.scrollY + box.top - innerHeight / 2);
  const misses = [];
  for (const cell of last) {
    const r = cell.getBoundingClientRect();
    const hit = document.elementFromPoint(r.right - 1, r.top + r.height / 2);
    if (!hit || !chart.contains(hit)) misses.push({row: r.top, x: r.right - 1, hit: hit ? hit.tagName + '.' + hit.className : null});
  }
  return {id: panel.id, cells: last.length, misses};
})
"""


def _launch(playwright: Any, engine: str = "chromium") -> Any:
    try:
        return getattr(playwright, engine).launch()
    except Exception as exc:
        # A cached headless shell of another Playwright build drives these pages as well.
        shells = sorted(BROWSERS.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
        if engine == "chromium" and shells:
            return playwright.chromium.launch(executable_path=str(shells[-1]))
        pytest.fail(f"Playwright's {engine} is not installed ({type(exc).__name__}); install it with: python -m playwright install {engine}")


def _open(pages: dict[str, Path], key: str, size: tuple[int, int], monkeypatch: pytest.MonkeyPatch, engine: str = "chromium") -> dict[str, Any]:
    """The page at ``size``: what ``_MEASURE`` and ``_HIT`` return, and the page's own sideways scroll."""
    from playwright.sync_api import sync_playwright

    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))
    width, height = size
    with sync_playwright() as p:
        browser = _launch(p, engine)
        try:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            page.goto(pages[key].resolve().as_uri(), wait_until="load")
            first = page.evaluate(
                "[...document.querySelectorAll('figure[id^=\"heatmap-\"]')].map(e => {const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height];})"
            )
            verdict_top = page.evaluate("document.querySelector('.verdict').getBoundingClientRect().top")
            measured = page.evaluate(_MEASURE)
            scroll, inner = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
            hits = page.evaluate(_HIT)
            context.close()
        finally:
            browser.close()
    return {"measured": measured, "hits": hits, "scroll": scroll, "inner": inner, "first": first, "verdict_top": verdict_top}


def _holds_every_chart(found: dict[str, Any], key: str, size: tuple[int, int]) -> None:
    assert found["measured"], (key, size, "no heatmap on the page")
    for panel in found["measured"]:
        fits = panel["panel"] >= panel["chart"] - 0.5
        scrolls = any(scroll_width >= panel["chart"] - 0.5 and scroll_width > client for _, client, scroll_width in panel["scrolls"])
        assert fits or scrolls, (key, size, panel)
        assert panel["clipped"] == [], (key, size, panel)
        # Fitting by shrinking away is no fix: the chart stays near the panel's width, or its own 540 px.
        assert panel["chart"] >= min(0.85 * panel["panel"], 540), (key, size, panel)
    for hit in found["hits"]:
        assert hit["cells"] >= 1, (key, size, hit)
        assert hit["misses"] == [], (key, size, hit)
    assert found["scroll"] <= found["inner"], (key, size, found["scroll"], found["inner"])


@pytest.mark.slow
@pytest.mark.parametrize("size", SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
@pytest.mark.parametrize("key", SHAPES)
def test_no_heatmap_panel_clips_its_chart(key: str, size: tuple[int, int], pages: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _holds_every_chart(_open(pages, key, size, monkeypatch), key, size)


@pytest.mark.slow
@pytest.mark.parametrize("size", [DESKTOP[0], PHONE[0]], ids=["1280x800", "390x844"])
@pytest.mark.parametrize("engine", ["firefox", "webkit"])
def test_no_heatmap_panel_clips_its_chart_in_the_other_engines(engine: str, size: tuple[int, int], pages: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _holds_every_chart(_open(pages, "two_events", size, monkeypatch, engine), f"two_events on {engine}", size)


@pytest.mark.slow
@pytest.mark.parametrize("key", SHAPES)
def test_the_first_screen_still_holds_at_1280_by_800(key: str, pages: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """r4: the verdict above, at least half of every heatmap in view with no scrolling, and two events
    still side by side."""
    found = _open(pages, key, FIRST_SCREEN, monkeypatch)
    height = FIRST_SCREEN[1]
    boxes = found["first"]
    assert boxes, key
    for _, top, _, box_height in boxes:
        assert found["verdict_top"] < top, (key, found["verdict_top"], top)
        assert height - top >= box_height / 2, (key, top, box_height)
    if len(boxes) == 2:
        assert boxes[0][1] == pytest.approx(boxes[1][1], abs=1), boxes
        assert boxes[0][0] + boxes[0][2] <= boxes[1][0], boxes


@pytest.mark.slow
@pytest.mark.parametrize("size", [DESKTOP[0], PHONE[0]], ids=["1280x800", "390x844"])
def test_no_panel_on_any_page_of_the_dashboard_clips_its_chart(size: tuple[int, int], pages: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """r7. Every figure on every page the dashboard writes for a two-event comparison."""
    from playwright.sync_api import sync_playwright

    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))
    root = pages["two_events"].parent.parent
    files = sorted(root.rglob("*.html"))
    assert len(files) > 5, files
    width, height = size
    cut: list[Any] = []
    seen = 0
    with sync_playwright() as p:
        browser = _launch(p)
        try:
            page = browser.new_page(viewport={"width": width, "height": height})
            for path in files:
                page.goto(path.as_uri(), wait_until="load")
                figures = page.evaluate(
                    """() => [...document.querySelectorAll('figure')].filter(f => f.querySelector('svg')).map(f => {
                      const chart = f.querySelector('svg');
                      const between = [];
                      for (let e = chart.parentElement; e; e = e.parentElement) { between.push(e); if (e === f) break; }
                      return {panel: f.clientWidth, chart: chart.getBoundingClientRect().width,
                              scrolls: between.some(e => /(auto|scroll)/.test(getComputedStyle(e).overflowX))};
                    })"""
                )
                seen += len(figures)
                cut += [(path.relative_to(root).as_posix(), figure) for figure in figures if figure["chart"] > figure["panel"] + 0.5 and not figure["scrolls"]]
        finally:
            browser.close()
    assert seen, files
    assert cut == [], (len(cut), cut[:5])
