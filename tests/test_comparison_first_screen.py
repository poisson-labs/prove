"""The comparison's first screen in the dashboard shows the chart: the shape of the change is in view
before the detail.

**What is pinned.** The page ``poisson-prove ui`` writes for a comparison, read as text in the code
suite and, in the slow check, opened in a browser at the sizes a laptop opens it.

**Readings this file fixes.**

- **r1** The first screen is what a browser shows of the page before any scrolling, at 1,280 by 800.
  Moving the charts to just above the conditions table is not enough: the verdict panel, the
  per-event table and the trades put that place about 1,000 pixels down.
- **r2** The charts that go there are the heatmaps, one per event, side by side where there is room:
  they show which conditions moved. The differences and limits charts stay where they are, after the
  conditions table.
- **r3** The verdict stays first. The heatmaps follow the verdict's word and its first detail lines,
  and come before "What the verdict rests on", which is what would push them down.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from pf12_support import copy_store, shared_world
from reading_support import QS_A, QS_B, cli, reading_world  # noqa: F401

BROWSERS = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or Path.home() / ("Library/Caches" if sys.platform == "darwin" else ".cache") / "ms-playwright")
SIZES = [(1280, 800), (1440, 900)]
VERDICT_RESTS_ON = "What the verdict rests on"


def _build(world: dict[str, Path], folder: Path) -> dict[str, Any]:
    pages: dict[str, str] = {}
    for key, more in (("two_events", ()), ("one_event", ("--event", "violated"))):
        store = copy_store(world["old"], folder / key / "prove-runs")
        saved = cli(store, "diff", QS_A, QS_B, "--save", *more)
        assert saved.code == 0, saved.err
        built = cli(store, "ui")
        assert built.code == 0, built.err
        found = list((store / ".poisson" / "ui" / "comparisons").glob("*.html"))
        assert len(found) == 1, found
        pages[key] = str(found[0])
    return pages


@pytest.fixture(scope="module")
def pages(tmp_path_factory: pytest.TempPathFactory, reading_world: dict[str, Path]) -> dict[str, Path]:  # noqa: F811
    _, built = shared_world(tmp_path_factory, "first-screen", lambda folder: _build(reading_world, folder))
    return {key: Path(path) for key, path in built.items()}


def _html(pages: dict[str, Path], key: str) -> str:
    return pages[key].read_text(encoding="utf-8")


def _figures(page: str) -> dict[str, int]:
    return {m.group(1): m.start() for m in re.finditer(r'<figure id="([^"]+)"', page)}


@pytest.mark.parametrize(("key", "heatmaps"), [("two_events", 2), ("one_event", 1)])
def test_every_heatmap_comes_before_the_detail(key: str, heatmaps: int, pages: dict[str, Path]) -> None:
    page = _html(pages, key)
    figures = _figures(page)
    found = [where for name, where in figures.items() if name.startswith("heatmap-")]
    assert len(found) == heatmaps, figures
    for anchor in (VERDICT_RESTS_ON, 'id="counts"', 'id="trades"', 'id="conditions"'):
        at = page.find(anchor)
        assert at >= 0, anchor
        assert max(found) < at, (anchor, figures, at)


@pytest.mark.parametrize("key", ["two_events", "one_event"])
def test_the_verdict_stays_first(key: str, pages: dict[str, Path]) -> None:
    page = _html(pages, key)
    first = min(_figures(page).values())
    verdict = page.find('id="verdict"')
    assert 0 <= verdict < first
    between = page[verdict:first]
    assert 'class="verdict' in between, between[:400]
    for label in (">before<", ">after<", ">method<"):
        assert label in between, label


@pytest.mark.parametrize("key", ["two_events", "one_event"])
def test_the_differences_and_limits_stay_after_the_conditions(key: str, pages: dict[str, Path]) -> None:
    page = _html(pages, key)
    figures = _figures(page)
    others = [where for name, where in figures.items() if not name.startswith("heatmap-")]
    assert others, figures
    assert min(others) > page.find('id="conditions"'), figures
    assert page.find('id="charts"') > page.find('id="conditions"')


@pytest.mark.parametrize(("key", "total"), [("two_events", 6), ("one_event", 3)])
def test_every_chart_is_on_the_page_once(key: str, total: int, pages: dict[str, Path]) -> None:
    page = _html(pages, key)
    names = re.findall(r'<figure id="([^"]+)"', page)
    assert len(names) == total and len(set(names)) == total, names
    assert page.count("<figure") == total


@pytest.mark.parametrize("key", ["two_events", "one_event"])
def test_each_chart_keeps_its_caption_and_its_link_in_the_restyled_panel(key: str, pages: dict[str, Path]) -> None:
    page = _html(pages, key)
    for name, where in _figures(page).items():
        end = page.find("</figure>", where)
        figure = page[where:end]
        assert "<figcaption>" in figure and ">open<" in figure and "<svg" in figure, name
        opened = page.rfind('<div class="charts">', 0, where)
        closed = page.rfind("</div>", opened, where) if opened >= 0 else -1
        assert opened >= 0, (name, "not in a charts panel")
        assert closed == -1 or "</svg>" in page[opened:closed + 6], (name, "outside its panel")


def _launch(playwright: Any) -> Any:
    try:
        return playwright.chromium.launch()
    except Exception as exc:
        # A cached headless shell of another Playwright build drives these pages as well.
        shells = sorted(BROWSERS.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
        if shells:
            return playwright.chromium.launch(executable_path=str(shells[-1]))
        pytest.fail(f"Playwright's chromium is not installed ({type(exc).__name__}); install it with: python -m playwright install chromium")


@pytest.mark.slow
@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("key", ["two_events", "one_event"])
def test_the_chart_is_on_the_first_screen_in_a_browser(key: str, size: tuple[int, int], scheme: str, pages: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Before any scrolling: at least half of every heatmap is in view, the verdict's word above it,
    and with two events the two sit side by side. The page does not scroll sideways."""
    from playwright.sync_api import sync_playwright

    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS))
    width, height = size
    with sync_playwright() as p:
        browser = _launch(p)
        try:
            context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
            page = context.new_page()
            page.goto(pages[key].resolve().as_uri(), wait_until="load")
            boxes = page.evaluate(
                "[...document.querySelectorAll('figure[id^=\"heatmap-\"]')].map(e => {const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height];})"
            )
            verdict_top = page.evaluate("document.querySelector('.verdict').getBoundingClientRect().top")
            scroll, inner = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
            context.close()
        finally:
            browser.close()
    assert boxes, key
    for _, top, _, box_height in boxes:
        assert verdict_top < top, (verdict_top, top)
        assert height - top >= box_height / 2, (key, size, top, box_height)
    if len(boxes) == 2:
        assert boxes[0][1] == pytest.approx(boxes[1][1], abs=1), boxes
        assert boxes[0][0] + boxes[0][2] <= boxes[1][0], boxes
    assert scroll <= inner, (scroll, inner)
