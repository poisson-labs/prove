"""The pseudo-terminal reader the PF6 tests share (``run_pty`` in ``tests/pf6_support.py``): a reader
that is late still reads everything the child wrote (the code suite).

On macOS, the last close of a pseudo-terminal's far end waits about 0.6 s for output not yet read,
then throws it away, and the near end reads as ended. A reader that a loaded runner holds back that
long would lose the tail of what the child wrote last, unless the test process keeps its own copy of
that end open until it has read all of it. A nightly run lost the end of an ``inspect --json``
document this way.

**How the reader is made late.** Every ``select`` the reader makes first sleeps ``LATE`` seconds,
past the 0.6 s, the way a descheduled reader is late. The child runs at full speed. Without the copy
kept open, each case here loses its tail on macOS, every time. On Linux the kernel keeps the output,
and the cases check that the reader still reads to the end and stops there.
"""

from __future__ import annotations

import select as real_select
import time
import types
from pathlib import Path
from typing import Any

import pytest

import pf6_support
from pf6_support import run_pty

LATE = 1.0

#: The child: ``lines`` numbered lines and ``END`` on stdout, then ``ERR END`` on stderr, then it exits.
CHILD = (
    "import sys\n"
    "lines = int(sys.argv[1])\n"
    "sys.stdout.write(''.join(f'line {i:04d} ' + 'x' * 60 + '\\n' for i in range(lines)) + 'END\\n')\n"
    "sys.stdout.flush()\n"
    "sys.stderr.write('ERR END\\n')\n"
    "sys.stderr.flush()\n"
)


def _written(lines: int) -> str:
    return "".join(f"line {i:04d} " + "x" * 60 + "\n" for i in range(lines)) + "END\n"


@pytest.fixture
def late_reader(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Make every ``select`` of the reader sleep ``LATE`` seconds first; the list holds when each
    began, so a case can tell that the reader was slowed at all."""
    began: list[float] = []

    def late_select(*args: Any, **kwargs: Any) -> Any:
        began.append(time.monotonic())
        time.sleep(LATE)
        return real_select.select(*args, **kwargs)

    monkeypatch.setattr(pf6_support, "select", types.SimpleNamespace(select=late_select))
    return began


@pytest.mark.parametrize("lines", [5, 20], ids=["one-buffer", "past-one-buffer"])
@pytest.mark.parametrize(("stdout", "stderr"), [("pty", "own"), ("pty", "pty"), ("pipe", "own")])
def test_pf6_reader_a_reader_late_past_the_terminals_wait_still_reads_all_the_child_wrote(
    late_reader: list[float], tmp_path: Path, stdout: str, stderr: str, lines: int,
) -> None:
    run = run_pty([], home=tmp_path, cwd=tmp_path, stdin="null", stdout=stdout, stderr=stderr,
                  command=["-c", CHILD, str(lines)], timeout=60)
    assert late_reader, "the reader was not slowed"
    assert run.code == 0
    if stderr == "pty":
        # one terminal for both streams: stdout's text, then stderr's line
        assert run.out == _written(lines) + "ERR END\n"
    else:
        assert run.out == _written(lines)
        assert run.err == "ERR END\n"
