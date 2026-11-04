"""The look file's two amendments: labels in the static UI may be in the system's sans, and a banner
section the tools share.

``docs/cli-look.md`` is the canonical copy, so these are made here first and the other tools copy
them. The file is pinned whole by its sha256 in ``test_pf6_look``; this file says what the change to
that hash is: ``tests/fixtures/cli-look/amendments.json`` holds each amendment's text, and taking them
back out of the file gives the file as it was, byte for byte.

**Readings this file fixes.**

- **r1** "Labels" are table headers, detail labels and captions: what the restyled pages already set
  in the sans. Table cells and detail values stay in the monospace.
- **r2** The banner is a section of its own between the terminal app's and the static UI's, since it
  is shared by a session and a full-screen app. Its numbers are held to the code that draws Prove's.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from poisson_prove import __version__, _banner

ROOT = Path(__file__).resolve().parents[1]
LOOK = ROOT / "docs" / "cli-look.md"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CHANGES = json.loads((FIXTURES / "cli-look" / "amendments.json").read_text(encoding="utf-8"))["changes"]
STYLE = ROOT / "src" / "poisson_prove" / "_ui_bundle" / "style.css"
#: The file before the amendments.
BEFORE_SHA256 = "92e71488c2824c056252be9a7b340e7fc138d15359fbcb7431bcfc6fa267d85f"
TYPE_RULE, BANNER = CHANGES
SANS = "system-ui"
MONO = "ui-monospace"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _look() -> str:
    return LOOK.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    return heading + text.split(heading, 1)[1].split("\n## ", 1)[0]


# ---------- the file is the file before plus the two amendments ----------


def test_the_fixture_is_the_two_amendments_of_the_file_before() -> None:
    """On the file as it was, each old text occurs once: the fixture can be applied. This holds the
    fixture to the file's history: green before the change and after it."""
    undone = _look().replace(BANNER["new"], "").replace(TYPE_RULE["new"], TYPE_RULE["old"])
    assert _sha256(undone) == BEFORE_SHA256
    assert undone.count(TYPE_RULE["old"]) == 1
    assert undone.count(BANNER["before"]) == 1


@pytest.mark.parametrize("change", CHANGES, ids=["type-rule", "banner"])
def test_each_amendment_is_in_the_file_once(change: dict[str, str]) -> None:
    assert _look().count(change["new"]) == 1, change["what"]


def test_the_old_type_rule_is_gone() -> None:
    assert TYPE_RULE["old"] not in _look()


def test_the_banner_section_sits_between_the_app_and_the_static_ui() -> None:
    headings = re.findall(r"^## .+$", _look(), re.MULTILINE)
    assert headings[-3:] == ["## The terminal app", "## The banner", "## The static UI"], headings


# ---------- the static UI: what the rule says is what the pages do ----------


def _rules(css: str, selector: str) -> list[str]:
    """Every rule whose selector list names ``selector``, outside any media block's nesting."""
    found = []
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        if selector in [part.strip() for part in selectors.split(",")]:
            found.append(body)
    return found


def _family_of(css: str, selector: str) -> str:
    """The font the selector's own rules set, last one winning; empty when they set none."""
    family = ""
    for body in _rules(css, selector):
        for match in re.finditer(r"(?:font-family\s*:|\bfont\s*:[^;]*?\d+px(?:/[\d.]+)?\s)\s*([^;]+)", body):
            family = match.group(1)
    return family


def test_the_rule_says_labels_are_in_the_sans() -> None:
    rule = " ".join(_section(_look(), "## The static UI").split("### Type", 1)[1].split("###", 1)[0].split())
    assert re.search(rf"labels .*?`{SANS}", rule), rule
    assert re.search(rf"table cells in `{MONO}", rule), rule


@pytest.mark.parametrize("label", ["th", "dt"])
def test_the_pages_labels_are_in_the_sans(label: str) -> None:
    family = _family_of(STYLE.read_text(encoding="utf-8"), label)
    assert SANS in family and MONO not in family, (label, family)


def test_a_caption_inherits_the_pages_sans() -> None:
    css = STYLE.read_text(encoding="utf-8")
    assert MONO not in _family_of(css, "figcaption")
    assert SANS in _family_of(css, "body")


@pytest.mark.parametrize("fact", ["td", "dd"])
def test_the_pages_facts_are_in_the_monospace(fact: str) -> None:
    family = _family_of(STYLE.read_text(encoding="utf-8"), fact)
    assert MONO in family and SANS not in family, (fact, family)


def test_the_tests_copy_of_the_static_ui_section_is_the_files() -> None:
    """``tests/fixtures/pf12/look-static-ui.md`` is the section, byte for byte, and the static UI
    tests read their colour tokens from it."""
    copy = (FIXTURES / "pf12" / "look-static-ui.md").read_text(encoding="utf-8")
    assert copy == "## The static UI" + _look().split("## The static UI", 1)[1]


# ---------- the banner: what the section says is what Prove draws ----------


def _banner_section() -> str:
    return " ".join(_section(_look(), "## The banner").split())


def test_the_banners_size_is_the_codes() -> None:
    section = _banner_section()
    (first, _), (second, _) = _banner.lines()
    assert _banner.WIDTH == 26 and "Two rows, 26 columns" in section
    assert len(first) == 26 and len(second) <= 26 + len(__version__), (first, second)
    assert len(_banner.MARK) == 12 and "twelve cells" in section
    assert _banner.NAME in section
    assert first.startswith(_banner.MARK + "  " + _banner.NAME), first
    assert second.lstrip().startswith(f"{_banner.TOOL}  {__version__}"), second
    assert len(second) - len(second.lstrip()) == first.index(_banner.NAME), (first, second)


def test_the_banners_hold_is_the_apps() -> None:
    from poisson_prove._cli_app import OPENING_HOLD

    assert f"{OPENING_HOLD:.1f} s" in _banner_section()


@pytest.mark.parametrize(
    "fact",
    [
        "No verb prints it",
        "Below 26 columns",
        "`Poisson Labs  <tool> <version>`",
        "`NO_COLOR`",
        "A headless run opens straight on the first screen",
        "`q` quits",
        "`Ctrl-C` exits 130",
    ],
)
def test_the_section_has_the_forms_and_the_opening_screen(fact: str) -> None:
    assert fact in _banner_section() or fact in _section(_look(), "## The banner"), fact


def test_the_look_says_where_colour_may_leave_the_four_meanings() -> None:
    """Rule 16 allows the four meanings and no others, and a tool's mark may carry its own colour: the
    section has to say it is the one exception, so the two do not read as a contradiction."""
    assert "the one colour outside the four meanings" in _banner_section()
