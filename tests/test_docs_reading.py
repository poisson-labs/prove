"""Two facts the docs owe a reader: what Burla does with Prove on its workers, and a ``__version__``
example that does not go stale.

**Readings this file fixes.**

- **r1** Burla pins every distribution the caller's environment installed from an index, and installs
  those pins on each node from the index, so a Prove from PyPI is installed there at the caller's
  version, and a version PyPI does not hold cannot be. Prove's bundle still goes first on the worker's
  path, so the code that runs the rollouts is the caller's own: the page says both, since either alone
  misleads. An editable checkout is shipped, not installed, so the page says that too.
- **r2** ``docs/python.md`` names no version of Prove: the page is copied to the site at each release,
  and an example number goes stale at the next one.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _burla_section() -> str:
    page = (ROOT / "docs" / "backends.md").read_text(encoding="utf-8")
    return page.split("\n## Burla\n", 1)[1].split("\n## ", 1)[0]


def _paragraphs(section: str) -> list[str]:
    return [" ".join(block.split()) for block in re.split(r"\n\s*\n", section)]


def _the_paragraph() -> str:
    found = [p for p in _paragraphs(_burla_section()) if "PyPI" in p and re.search(r"\b(worker|node)s?\b", p)]
    assert len(found) == 1, found
    return found[0]


def test_the_burla_section_says_its_workers_install_prove_from_pypi() -> None:
    paragraph = _the_paragraph()
    assert re.search(r"\b(installs?|reinstalls?)\b", paragraph), paragraph
    assert "Prove" in paragraph, paragraph
    assert re.search(r"\bversion\b", paragraph), paragraph


def test_it_says_a_version_pypi_does_not_hold_cannot_be_installed_there() -> None:
    assert re.search(r"(?i)\bversion\b[^.]*\bPyPI\b[^.]*\b(not|cannot|no)\b|\bnot\b[^.]*\bon PyPI\b", _the_paragraph()), _the_paragraph()


def test_it_says_the_bundle_is_what_runs_the_rollouts() -> None:
    paragraph = _the_paragraph()
    assert "bundle" in paragraph, paragraph
    assert re.search(r"\brollouts?\b", paragraph), paragraph


def test_it_says_an_editable_checkout_is_shipped_not_installed() -> None:
    paragraph = _the_paragraph()
    assert re.search(r"\beditable\b", paragraph) and re.search(r"\bcheckout\b", paragraph), paragraph


def test_only_the_burla_section_says_it() -> None:
    """Modal builds its image from what the spec declares: the sentence is about Burla."""
    page = (ROOT / "docs" / "backends.md").read_text(encoding="utf-8")
    modal = page.split("\n## Modal\n", 1)[1].split("\n## ", 1)[0] if "\n## Modal\n" in page else ""
    assert _the_paragraph() not in " ".join(modal.split())


def test_the_python_page_names_no_version_of_prove() -> None:
    page = (ROOT / "docs" / "python.md").read_text(encoding="utf-8")
    bullet = next(line for line in page.splitlines() if line.startswith("- `__version__`"))
    assert not re.search(r"\d+\.\d+", bullet), bullet
    assert "installed version" in bullet, bullet
    named = re.findall(r"(?<![\w.])\d+\.\d+\.\d+(?![\w.])", page)
    assert named == [], named
