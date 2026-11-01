"""What a release tag must agree with before anything is built.

    python .github/lanes/release_check.py TAG

A release is a version bump and a dated CHANGELOG entry, merged through the gate, then a tag. The
tag ``vX.Y.Z`` must name the version ``pyproject.toml`` and ``poisson_prove.__version__`` carry,
and ``CHANGELOG.md`` must have an entry headed ``## X.Y.Z — YYYY-MM-DD`` with a real date. Prints
each disagreement; exits 1 if there is any.
"""

from __future__ import annotations

import datetime
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def problems(tag: str, pyproject: str, init: str, changelog: str) -> list[str]:
    """One line per disagreement between the tag and the files; empty when they agree."""
    out = []
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return [f"the tag {tag} is not vX.Y.Z"]
    version = tag[1:]
    declared = tomllib.loads(pyproject)["project"]["version"]
    if declared != version:
        out.append(f"pyproject.toml says {declared}, the tag {tag}")
    found = re.search(r'^__version__ = "([^"]+)"', init, re.MULTILINE)
    if not found or found.group(1) != version:
        out.append(f"__version__ is {found.group(1) if found else 'missing'}, the tag {tag}")
    entry = re.search(rf"^## {re.escape(version)} — (\S+)$", changelog, re.MULTILINE)
    if not entry:
        out.append(f"CHANGELOG.md has no entry headed '## {version} — YYYY-MM-DD'")
    else:
        try:
            datetime.date.fromisoformat(entry.group(1))
        except ValueError:
            dated = entry.group(1)
            out.append(f"the CHANGELOG entry for {version} is dated {dated}, not YYYY-MM-DD")
    return out


def main(tag: str) -> int:
    wrong = problems(
        tag,
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        (ROOT / "src" / "poisson_prove" / "__init__.py").read_text(encoding="utf-8"),
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
    )
    print("\n".join(wrong) if wrong else f"{tag}: the version and the CHANGELOG entry agree")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
