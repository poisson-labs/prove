"""The Burla pin agrees everywhere it is named: the backend's ``_BURLA_PIN``, the ``[burla]`` and
``[all]`` extras, and every Burla version the README, the docs pages and Prove's own source name.

**What is pinned.** The launcher runs exactly one client, ``_BURLA_PIN``; both extras require
exactly that version; and a page or docstring that names a Burla version (``burla==X.Y.Z`` or
"Burla X.Y.Z") names that one. The backends page must name the pin, so the scan cannot pass by
finding nothing.

**Choices:**

- The CHANGELOG is left out: a released entry keeps the version it shipped with.
- Tests are left out: a fake cites the Burla tag it was written against, and the version cases
  of ``test_pf9_backends.py`` name versions the backend refuses on purpose.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from poisson_prove import executor_burla

REPO = Path(__file__).resolve().parents[1]
PIN = executor_burla._BURLA_PIN
#: ``burla==1.8.4``, ``Burla 1.8.4``, ``burla client 1.8.4``: a Burla version as a page names one.
NAMED = re.compile(r"(?i)\bburla(?:==|\s+(?:client\s+)?v?)(\d+\.\d+\.\d+)")


def _pages() -> list[Path]:
    return [REPO / "README.md", *sorted((REPO / "docs").rglob("*.md")),
            *sorted((REPO / "src" / "poisson_prove").rglob("*.py"))]


def test_the_extras_require_exactly_the_client_the_backend_runs() -> None:
    extras = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]["optional-dependencies"]
    for extra in ("burla", "all"):
        burla = [req for req in extras[extra] if re.match(r"burla\b", req)]
        assert burla == [f"burla=={PIN}"], (extra, burla, PIN)


def test_every_burla_version_a_page_names_is_the_pin() -> None:
    named: dict[str, set[str]] = {}
    for page in _pages():
        for version in NAMED.findall(page.read_text(encoding="utf-8")):
            named.setdefault(str(page.relative_to(REPO)), set()).add(version)
    assert PIN in named.get("docs/backends.md", set()), named
    wrong = {page: sorted(versions - {PIN}) for page, versions in named.items() if versions - {PIN}}
    assert wrong == {}, (PIN, wrong)
