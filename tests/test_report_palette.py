"""The report's verdict colours: cobalt where a rate fell, hatched ink where it rose."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from poisson_prove.report import (
    NEUTRAL_FILL,
    Cell,
    _contrast,
    _fill,
    _hatch,
    _ink_attr,
    _is_hatched,
    build_report,
)

from test_m7_report import grid_diff, spec2

SAFER = {"dark": "#3B82F6", "light": "#2A4DD0"}
WORSE = {"dark": "#E6E6E6", "light": "#111111"}
THEMES = ("dark", "light")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _both_ways(theme: str) -> ET.Element:
    d = grid_diff(
        [0.1, 0.2],
        [10, 20],
        delta_fn=lambda i, j: -0.4 if i == 0 else 0.4,
        verdict_fn=lambda i, j, dl: "worse" if dl > 0 else "safer",
    )
    return ET.fromstring(build_report(d, spec2(theme=theme)).to_svg())


@pytest.mark.parametrize("theme", THEMES)
def test_the_ends_of_the_ramp_are_the_two_verdict_colours(theme: str) -> None:
    assert _fill(-1.0, True, theme).upper() == SAFER[theme]
    assert _fill(1.0, True, theme).upper() == WORSE[theme]
    assert _fill(0.0, True, theme) == NEUTRAL_FILL[theme]


@pytest.mark.parametrize("theme", THEMES)
def test_only_a_significant_rise_is_hatched(theme: str) -> None:
    root = _both_ways(theme)
    hatches = [e for e in root.iter() if e.attrib.get("data-hatch") == "1"]
    cells = [e for e in root.iter() if "data-cell" in e.attrib and _local(e.tag) == "rect"]
    # half the conditions rose; the legend adds its two swatches on that arm
    assert len(hatches) == len(cells) // 2 + 2


def _cell(delta: float, verdict: str, rate_a: float = 0.4, rate_b: float = 0.5) -> Cell:
    return Cell(("a", 1), "h", True, 10, 10, rate_a, rate_b, delta, 0.01, 0.01, verdict, 0.1)


def test_a_rise_that_is_not_significant_and_a_saturated_cell_carry_no_hatch() -> None:
    assert _is_hatched(_cell(0.1, "worse"), "diff")
    assert not _is_hatched(_cell(0.1, "unchanged"), "diff")
    assert not _is_hatched(_cell(0.0, "worse", 1.0, 1.0), "diff")
    assert not _is_hatched(_cell(-0.1, "safer"), "diff")
    assert not _is_hatched(_cell(0.1, "worse"), "rate")


@pytest.mark.parametrize("theme", THEMES)
def test_digits_read_and_every_significance_square_has_a_backing(theme: str) -> None:
    """On the old palette these marks had one colour; ink and white fills would swallow them."""
    root = _both_ways(theme)
    marks = [e for e in root.iter() if e.attrib.get("data-sig") == "1"]
    backs = [e for e in root.iter() if e.attrib.get("data-sig-back") == "1"]
    assert marks and len(backs) == len(marks)
    for back in backs:
        assert _contrast(back.attrib["fill"], "#FFFFFF" if theme == "dark" else "#000000") >= 7
    worst = _fill(1.0, True, theme)
    text = "#000000" if worst == "#E6E6E6" else "#FFFFFF"
    assert (
        _ink_attr(worst, {"dark": "#E6E6E6", "light": "#1A1A1A"}[theme], 4.5) == f' fill="{text}"'
    )


def test_the_ink_attribute_is_only_written_when_it_is_needed() -> None:
    assert _ink_attr("#111111", "#FFFFFF") == ""
    assert _ink_attr("#111111", "#000000") == ' fill="#FFFFFF"'
    assert _ink_attr("#E6E6E6", "#FFFFFF") == ' fill="#000000"'


def test_the_hatch_stays_inside_its_rectangle_and_references_nothing() -> None:
    path = _hatch(10, 20, 40, 10, "#111111")
    assert "url(" not in path and "<defs" not in path and "<pattern" not in path
    numbers = [int(n) for n in re.findall(r"\d+", re.search(r'd="([^"]*)"', path).group(1))]
    xs, ys = numbers[0::2], numbers[1::2]
    assert min(xs) >= 10 and max(xs) <= 50 and min(ys) >= 20 and max(ys) <= 30


def test_the_hatch_is_white_on_a_dark_fill_and_black_on_a_light_one() -> None:
    assert 'stroke="#FFFFFF"' in _hatch(0, 0, 40, 10, "#111111")
    assert 'stroke="#000000"' in _hatch(0, 0, 40, 10, "#E6E6E6")


@pytest.mark.parametrize("theme", THEMES)
def test_no_green_or_red_is_left_in_a_comparison(theme: str) -> None:
    root = _both_ways(theme)
    assert not re.search("3ECF8E|FF4D4D", ET.tostring(root, encoding="unicode"), re.I)
