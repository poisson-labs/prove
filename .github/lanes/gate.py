"""The gate's verdict: the one check main's ruleset requires.

    python .github/lanes/gate.py

Reads ``$NEEDS``, the JSON of the gate job's ``needs`` context, and passes only when every job
the gate depends on passed, or was skipped because the change did not call for it: the math suite
when ``changes`` decided ``math=false``, the backend tests when it decided ``backends=false``.
Any other job skipped, failed or cancelled fails the gate, and so does a conditional job skipped
when ``changes`` asked for it. Writes one line per job to the job summary; exits 1 on any problem.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from typing import Any

#: Jobs that run only when ``changes`` says so, and the output that says it.
CONDITIONAL = {"math": "math", "backends": "backends"}


def problems(needs: Mapping[str, Any]) -> list[str]:
    """One line per job that keeps the gate shut; empty when it opens."""
    out = []
    asked = needs.get("changes", {}).get("outputs", {})
    for job, state in needs.items():
        result = state.get("result")
        if result == "success":
            continue
        if result == "skipped" and job in CONDITIONAL and asked.get(CONDITIONAL[job]) == "false":
            continue
        out.append(f"{job}: {result}")
    return out


def main() -> int:
    needs = json.loads(os.environ["NEEDS"])
    wrong = problems(needs)
    lines = [f"- {job}: {state.get('result')}" for job, state in needs.items()]
    verdict = "closed: " + "; ".join(wrong) if wrong else "open"
    text = "### Gate\n\n" + "\n".join(lines) + "\n\n" + verdict + "\n"
    print(text, end="")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(text)
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
