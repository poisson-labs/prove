"""Run one lane of the test suite and write what it ran to the job summary.

    python .github/lanes/lane.py LANE BUDGET_SECONDS [--over SECONDS] [PYTEST ARGS ...]

Runs ``python -m pytest`` with the arguments given, in a child whose SIGINT is the default (a
step started in the background of a non-interactive shell may inherit it ignored), and writes
to ``$GITHUB_STEP_SUMMARY`` (or prints, outside Actions) a table row: the lane, the Python, the
tests run and how they ended, the wall time against the lane's budget, and the machine's load
average sampled every five seconds while the lane ran. With ``--over SECONDS`` it also lists
every test whose setup, call and teardown together took longer, slowest first: the code lane's
measure of which tests are slow on the runner. Exits with pytest's exit code. A lane over its
budget is reported, not failed.
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


def over(junit: Path, seconds: float) -> list[tuple[float, str]]:
    """``(time, test id)`` for every test in the report that took longer than ``seconds``."""
    if not junit.exists():
        return []
    found = []
    for case in ET.parse(junit).getroot().iter("testcase"):
        took = float(case.get("time", 0))
        if took > seconds:
            path = case.get("classname", "").replace(".", "/")
            found.append((took, f"{path}.py::{case.get('name')}"))
    return sorted(found, reverse=True)


def clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def main(argv: list[str]) -> int:
    lane, budget, pytest_args = argv[0], float(argv[1]), argv[2:]
    threshold = None
    if pytest_args[:1] == ["--over"]:
        threshold, pytest_args = float(pytest_args[1]), pytest_args[2:]
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
    report = ["-o", "junit_duration_report=total", f"--junitxml={junit}"]
    code = subprocess.call([sys.executable, "-m", "pytest", *report, *pytest_args])
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
    text = header + row
    if threshold is not None:
        slow = over(junit, threshold)
        text += f"\n{len(slow)} tests over {threshold:g} s (setup, call and teardown):\n\n"
        text += "".join(f"- {took:.1f} s `{test}`\n" for took, test in slow)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write(text)
    print(text, end="")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
