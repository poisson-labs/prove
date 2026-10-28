"""The history check the release bar asks for: no commit reachable from HEAD names an AI assistant
in its message, and every author and committer address is the work identity.

    python .github/scripts/history.py

An address passes when it ends ``@poissonlabs.ai`` or is GitHub's own ``noreply@github.com``, the
committer of a merge GitHub makes. Prints each commit that fails and why; exits 1 if any does.
The check needs the whole history (``fetch-depth: 0``).
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable

#: An attribution line an assistant leaves, matched case-insensitively.
ATTRIBUTION = re.compile(
    r"^co-authored-by:.*\b(claude|anthropic|openai|chatgpt|gpt|copilot|gemini|cursor|codex)\b"
    r"|generated (with|by) .*\b(claude|chatgpt|copilot|gemini|cursor|codex|ai)\b",
    re.IGNORECASE | re.MULTILINE,
)
WORK_DOMAIN = "@poissonlabs.ai"
GITHUB = "noreply@github.com"


def problems(commits: Iterable[tuple[str, str, str, str]]) -> list[str]:
    """``(sha, author email, committer email, message)`` -> one line per failing commit."""
    out = []
    for sha, author, committer, message in commits:
        why = []
        for role, address in (("author", author), ("committer", committer)):
            if not (address.lower().endswith(WORK_DOMAIN) or address.lower() == GITHUB):
                why.append(f"{role} {address}")
        if ATTRIBUTION.search(message):
            why.append("an assistant named in the message")
        if why:
            out.append(f"{sha[:12]}: " + "; ".join(why))
    return out


def commits() -> list[tuple[str, str, str, str]]:
    raw = subprocess.run(
        ["git", "log", "--format=%H%x00%ae%x00%ce%x00%B%x1e"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        tuple(record.strip("\n").split("\x00", 3)) for record in raw.split("\x1e") if record.strip()
    ]  # type: ignore[misc]


def main() -> int:
    found = problems(commits())
    print("\n".join(found) if found else "every commit is clean")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
