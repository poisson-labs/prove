"""Run one candidate against one golden's ``check``, and come back with a verdict.

Hygiene, not the boundary (spec section 8). **The Modal container is the isolation boundary**;
these limits exist so that one bad candidate costs one tool call instead of the batch:

* a fresh ``python -I -S`` subprocess per call -- no site packages, no inherited environment
  beyond ``PATH``, no shared interpreter state, an empty working directory;
* a seeded ``random``, so a golden whose own check draws random inputs still yields the same
  verdict for the same candidate. Three of HumanEval's 164 do (see the preamble);
* a wall clock (:data:`WALL_CLOCK_S`), enforced on the whole process *group*, so a candidate
  that forks does not leave a grandchild burning the container's CPU for the rest of the arm;
* best-effort address-space and file-size limits (:data:`MEMORY_LIMIT_BYTES`,
  :data:`FILE_SIZE_LIMIT_BYTES`), soft *and* hard so the candidate cannot raise them back;
* ``socket`` and ``_socket`` replaced with ``None``, so an ordinary attempt to reach the
  network -- directly, or through ``urllib``, ``http.client``, anything -- fails at the
  import;
* the candidate's ``stdout`` discarded and its ``stderr`` written to a file we read the tail
  of, so a candidate that prints without stopping cannot grow the *agent's* memory. Reading
  an unbounded pipe into the parent would put one chatty candidate in a position to kill the
  whole batch, which is the thing these limits exist to prevent.

**None of this is adversary-proof and none of it is meant to be.** A candidate that wants out
can ``del sys.modules["socket"]``, write the success marker itself, or fill the container's
disk; ``PATH`` is inherited. These limits stop the *accidents* -- an infinite loop, a runaway
allocation, a library that phones home, a stray ``sys.exit(0)`` -- so one bad candidate costs
one tool call. The thing that stops the rest is the ephemeral Modal container (spec 8).

:func:`run_tests` never raises into the agent and never returns an untruncated reason: a
failure text goes to the model, and :data:`REASON_CAP` is where it stops.

**The memory limit is best effort, and on macOS it does nothing.** ``resource.setrlimit``
there refuses every finite ``RLIMIT_AS`` / ``RLIMIT_DATA`` / ``RLIMIT_RSS`` with ``ValueError``
whatever the value, so the preamble swallows that error rather than failing every candidate on
a laptop. The limit bites on the Linux image, which is where it matters and where spec
section 8 asks for it to be verified once before the pilot runs for real.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .suite import Golden

#: Seconds a candidate gets. Read at call time, so a caller may lower it.
WALL_CLOCK_S = 10.0

#: Address space a candidate gets, where the platform enforces it at all.
MEMORY_LIMIT_BYTES = 1 << 30

#: What the candidate's ``random`` is seeded with, so the golden's check draws the same
#: inputs every time. Any fixed value does; this one is not special.
RANDOM_SEED = 0

#: CPU seconds a candidate gets on top of the wall clock, as a kernel-enforced backstop for
#: the case where the parent dies before it can enforce anything.
_CPU_GRACE_S = 5

#: The largest file a candidate may write. Its stderr goes to a file, and without this a
#: candidate that never stops printing fills the container's disk instead of the parent's RAM.
FILE_SIZE_LIMIT_BYTES = 64 << 20

#: The longest failure text that may reach the model (spec section 3, P6).
REASON_CAP = 500

#: How many trailing traceback lines the model is shown. See :func:`_failure_text`.
_FAILURE_LINES = 4

#: How much of the candidate's ``stderr`` is read back. A traceback is a few hundred bytes;
#: anything past this is a candidate being noisy, and only the last line is ever used.
STDERR_TAIL_BYTES = 64 * 1024

#: Written to stderr once ``check`` has returned. Exit status 0 alone does not mean the
#: assertions ran: a candidate with a bare ``sys.exit()`` in it exits clean having tested
#: nothing, and without this marker that scores as a pass.
CHECK_PASSED_MARKER = "__golden_pilot_check_passed__"

_PREAMBLE = """\
# --- golden_pilot sandbox preamble: hygiene only; the container is the boundary ---
import sys

try:
    import resource
except ImportError:  # pragma: no cover - resource is POSIX-only
    resource = None

if resource is not None:
    for _name, _wanted in (
        ("RLIMIT_AS", {limit}),
        ("RLIMIT_DATA", {limit}),
        ("RLIMIT_FSIZE", {fsize}),
        # CPU seconds, enforced by the kernel and not by us. The wall clock above needs a
        # live parent to fire; if the executor terminates the whole episode mid-check
        # (episode_timeout, S16) nothing is left to kill a spinning candidate and it burns a
        # container core for the rest of the arm. This is the backstop for that.
        ("RLIMIT_CPU", {cpu}),
    ):
        _limit = getattr(resource, _name, None)
        if _limit is None:
            continue
        try:
            _soft, _hard = resource.getrlimit(_limit)
            # Soft and hard together: a lowered hard limit cannot be raised back.
            _value = _wanted if _hard == resource.RLIM_INFINITY else min(_wanted, _hard)
            resource.setrlimit(_limit, (_value, _value))
        except (ValueError, OSError):
            pass  # macOS refuses every finite memory value; the Linux image does not

# Three of HumanEval's own checks draw unseeded random test inputs (HumanEval/38, /50 and
# /53; /32 seeds itself). Without this line run_tests is not a function of
# (candidate, golden): the same candidate flips verdict across identical calls, and those
# flips are indistinguishable from the model coin flips this pilot exists to count. Seeding
# fixes the inputs those three checks draw. It narrows what they test -- one sample of the
# input space instead of a fresh one each run -- and that is the right trade for an
# instrument whose whole claim is that a repeated failure means something.
import random as _random
_random.seed({seed})

sys.modules["socket"] = None
sys.modules["_socket"] = None
# --- end preamble ---
"""


@dataclass(frozen=True)
class TestResult:
    """What the golden's ``check`` did. ``reason`` is empty exactly when ``passed``.

    ``harness_error`` separates *the sandbox broke* from *the candidate failed*. They are
    different facts and the pilot counts them apart: a candidate failure is the episode's
    outcome, a sandbox failure is Prove failing to observe and belongs in an errored row
    (spec section 3). Without the flag a full disk would be indistinguishable from a wrong
    answer, and would land in the pilot's headline failure event.
    """

    passed: bool
    reason: str
    harness_error: bool = False


def program(candidate: str, golden: Golden) -> str:
    """The complete source the subprocess runs: preamble, candidate, check, call."""
    return "\n".join(
        (
            _PREAMBLE.format(
                limit=MEMORY_LIMIT_BYTES,
                fsize=FILE_SIZE_LIMIT_BYTES,
                cpu=int(WALL_CLOCK_S) + _CPU_GRACE_S,
                seed=RANDOM_SEED,
            ),
            candidate,
            "",
            golden.test,
            "",
            f"check({golden.entry_point})",
            f"__import__('sys').stderr.write({CHECK_PASSED_MARKER!r})",
            "",
        )
    )


def _failure_text(text: str) -> str:
    """The end of the child's traceback: the failing source line and the exception.

    Spec section 3 wants "the first failure line" in the tool result. HumanEval's checks are
    bare ``assert`` statements with no message, so the exception line alone is the six
    characters ``AssertionError`` -- one bit, and the model cannot act on it. The line above
    it is the assertion itself, naming the input and the expectation, and that is the line
    worth sending. Keeping the last few gets both without parsing tracebacks.
    """
    keep = []
    for line in text.strip().splitlines():
        stripped = line.strip()
        # Frame headers carry the sandbox's temporary directory, which is both noise to the
        # model and an absolute path of ours (spec section 0, gap 2). Caret rulers are noise
        # too once the source line above them is gone.
        if not stripped or stripped.startswith(('Traceback (most recent', 'File "')):
            continue
        if set(stripped) <= {"^", "~"}:
            continue
        keep.append(stripped)
    return "\n".join(keep[-_FAILURE_LINES:])


def _tail(path: Path) -> str:
    """The last :data:`STDERR_TAIL_BYTES` of a file, as text. Never raises."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - STDERR_TAIL_BYTES))
            return handle.read().decode("utf-8", "replace")
    except OSError:  # pragma: no cover - the temporary directory is ours
        return ""


def _kill_group(pgid: int) -> None:
    """SIGKILL the candidate's whole process group. Never raises.

    Run on every path, not only the timeout: a candidate that returns cleanly having spawned
    a child leaves that child running, and over an arm of 10,496 episodes those accumulate in
    the container until they are what the wall clock is actually measuring.
    """
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def run_tests(candidate: str, golden: Golden) -> TestResult:
    """``passed`` iff the candidate satisfies every assertion in the golden's ``check``.

    Never raises: an assertion failure, an exception, a hang, an allocation past the limit, a
    socket, a killed interpreter and a broken sandbox all come back as ``passed=False`` with a
    reason of at most :data:`REASON_CAP` characters.
    """
    limit = WALL_CLOCK_S
    try:
        with tempfile.TemporaryDirectory(prefix="golden-pilot-") as tmp:
            path = Path(tmp) / "candidate.py"
            path.write_text(program(candidate, golden), encoding="utf-8")
            errors = Path(tmp) / "stderr.txt"
            with errors.open("wb") as sink:
                proc = subprocess.Popen(
                    [sys.executable, "-I", "-S", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=sink,
                    cwd=tmp,
                    env={"PATH": os.environ.get("PATH", "")},
                    start_new_session=True,
                )
                # start_new_session makes the child its own process-group leader, so its pid
                # is the pgid and stays usable for the group after the child itself is reaped.
                pgid = proc.pid
                timed_out = False
                try:
                    try:
                        proc.wait(timeout=limit)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        _kill_group(pgid)
                        try:
                            proc.wait(timeout=5.0)
                        except subprocess.TimeoutExpired:  # pragma: no cover - SIGKILLed
                            pass
                finally:
                    _kill_group(pgid)  # anything the candidate spawned, on every path
            if timed_out:
                return TestResult(False, f"timed out after {limit:g} s wall clock"[:REASON_CAP])
            err = _tail(errors)
    except Exception as exc:  # noqa: BLE001 - the sandbox never raises into the agent
        reason = f"sandbox error: {type(exc).__name__}: {exc}"
        return TestResult(False, reason[:REASON_CAP], harness_error=True)
    if proc.returncode == 0 and CHECK_PASSED_MARKER in err:
        return TestResult(True, "")
    if proc.returncode == 0:
        return TestResult(False, "the candidate exited before the golden's check ran")
    reason = _failure_text(err) or f"exited with status {proc.returncode}"
    return TestResult(False, reason[:REASON_CAP])
