"""Run one lane of the test suite and write what it ran to the job summary.

    python .github/scripts/lane.py LANE BUDGET_SECONDS [PYTEST ARGS ...]

Runs ``python -m pytest`` with the arguments given, in a child whose SIGINT is the default (a
step started in the background of a non-interactive shell may inherit it ignored), and writes
to ``$GITHUB_STEP_SUMMARY`` (or prints, outside Actions) a table row: the lane, the Python, the
tests run and how they ended, the wall time against the lane's budget, and the machine's load
average sampled every five seconds while the lane ran. Exits with pytest's exit code. A lane
over its budget is reported, not failed.
"""

from __future__ import annotations

import os
import platform
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path


def counts(junit: Path) -> dict[str, int]:
    """Tests, failures, errors and skips, summed over the report's suites."""
    if not junit.exists():
        return {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    return {
        key: sum(int(s.get(key, 0)) for s in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }


def clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def main(argv: list[str]) -> int:
    lane, budget, pytest_args = argv[0], float(argv[1]), argv[2:]
    loads: list[float] = []
    done = threading.Event()

    def sample() -> None:
        while not done.is_set():
            loads.append(os.getloadavg()[0])
            done.wait(5)

    junit = Path(tempfile.mkdtemp(prefix=f"lane-{lane}-")) / "junit.xml"
    signal.signal(signal.SIGINT, signal.default_int_handler)
    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    start = time.monotonic()
    code = subprocess.call([sys.executable, "-m", "pytest", f"--junitxml={junit}", *pytest_args])
    wall = time.monotonic() - start
    done.set()
    sampler.join()
    n = counts(junit)
    passed = n["tests"] - n["failures"] - n["errors"] - n["skipped"]
    verdict = "within" if wall <= budget else "over"
    load = f"{min(loads):.1f} / {statistics.median(loads):.1f} / {max(loads):.1f}" if loads else "-"
    columns = ["lane", "python", "ran", "passed", "failed", "errors", "skipped", "wall", "budget"]
    columns += ["load min / median / max", "cores", "exit"]
    cells = [lane, platform.python_version(), n["tests"], passed, n["failures"], n["errors"]]
    cells += [n["skipped"], clock(wall), f"{clock(budget)} ({verdict})", load, os.cpu_count(), code]
    header = "| " + " | ".join(columns) + " |\n" + "|---" * len(columns) + "|\n"
    row = "| " + " | ".join(str(cell) for cell in cells) + " |\n"
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(header + row)
    print(header + row, end="")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
