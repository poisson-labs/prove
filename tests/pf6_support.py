"""What PF6's two test files share: the command line in process and in a process of its own, a
pseudo-terminal and the screen it shows, the terminal app driven by Textual's test pilot and its
screen read cell by cell, a record of what the core returned to the app, and the stores the tests
read.

PF6 (the pretty rendering, the terminal app and the look file) is reached the way a user reaches
it: commands run on a pipe or on a pseudo-terminal, the app driven by keys, what is on the screen,
the files left in the store, and the core's boundary as its public names draw it
(``poisson_prove.core``). The one private name the tests take from Prove is the app's entry point,
the terminal app's class ``ProveApp`` (reading A1 in ``test_pf6_app.py``), which Textual's pilot needs.

**The stores are built once per test session.** ``shared_world`` builds each behind a lock file in
the folder the ``-n`` workers share; the others wait and read it. Nothing a test does may change a
shared store: a test that writes copies one first (``copy_world``).
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import hashlib
import json
import os
import re
import select
import shutil
import stat
import struct
import subprocess
import sys
import termios
import time
import traceback
import warnings
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
OLD = TESTS / "fixtures" / "stores-0.0.1"
OLD_RUNS: dict[str, str] = json.loads((OLD / "runs.json").read_text(encoding="utf-8"))
QS_A = OLD_RUNS["quickstart_before"]
QS_B = OLD_RUNS["quickstart_after"]
LOOK = ROOT / "docs" / "cli-look.md"
LOOK_FIXTURES = TESTS / "fixtures" / "cli-look"
#: Under a ``__snapshots__`` folder, where PF8's public-hygiene test reads the app's screens.
SNAPSHOTS = TESTS / "__snapshots__" / "pf6"
#: The one documented command that rewrites the snapshots, the same for PF6 and PF12.
SNAPSHOT_COMMAND = "python -m pytest tests -k snapshot --update-snapshots"
COMMAND = "poisson-prove"
MOCK = "poisson_prove.examples.mock_agent"

#: Keys planted in the environment while the app runs and while every shared store is built: Prove
#: reads no key, so none may appear in anything it shows or writes (PF6.12).
PLANTED_KEYS = {
    "OPENAI_API_KEY": "sk-pf6-planted-openai-00000000000000000",
    "ANTHROPIC_API_KEY": "sk-ant-pf6-planted-anthropic-0000000000",
    "MODAL_TOKEN_SECRET": "as-pf6-planted-modal-secret-000000000",
    "BURLA_API_KEY": "pf6-planted-burla-key-0000000000000000",
}

#: Rule 3's verdict line: a lowercase word or phrase, two spaces, then the sentence.
FIRST_LINE = re.compile(r"^([a-z][a-z ]*?)  (\S.*)$")
RUN_ID = re.compile(r"\b\d{8}T\d{6}Z-[0-9a-f]{4}\b")
HEX = re.compile(r"^[0-9a-f]{12}$|^[0-9a-f]{16}$|^[0-9a-f]{64}$")
ISO_UTC = re.compile(r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d)(:\d\d)(\.\d+)?Z$")
#: A value spelled as a code (``mcnemar_bh``, ``tool_calls``): shown verbatim or by its words.
CODE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")

#: The look's four meanings, as each verdict word takes them (the direction words and a row's
#: ``unchanged`` are among the results that are bold with no colour).
GREEN_WORDS = ("ok", "done", "passed", "under cap")
YELLOW_WORDS = ("stopped", "too small to tell", "no significant change")
RED_WORDS = ("failed", "at cap")
BOLD_WORDS = ("plan", "worse", "safer", "trade", "mixed", "higher", "lower", "unchanged")
ROLE_OF_WORD = {**{w: "G" for w in GREEN_WORDS}, **{w: "Y" for w in YELLOW_WORDS}, **{w: "R" for w in RED_WORDS}, **{w: "B" for w in BOLD_WORDS}}


# ---------- small things ----------


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[-\u2010-\u2015]", " ", text.lower()).split())


def says(text: str, words: str) -> bool:
    """A phrase, whatever its case, wherever a line breaks it, and whichever hyphen or dash joins
    its words."""
    return _norm(words) in _norm(text)


def squash(text: str) -> str:
    return " ".join(text.split())


def split_first_line(text: str) -> tuple[str, str]:
    first = text.splitlines()[0] if text else ""
    m = FIRST_LINE.match(first)
    assert m, first
    return m.group(1), m.group(2)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def listing(root: Path, *, outside: tuple[str, ...] = ()) -> dict[str, str]:
    """Every file under ``root`` with its sha256, but those under a top folder named in ``outside``."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if rel.parts and rel.parts[0] in outside:
            continue
        if p.is_file():
            out[rel.as_posix()] = sha256_of(p)
        elif p.is_dir():
            out[rel.as_posix() + "/"] = ""
    return out


@contextlib.contextmanager
def environment(**variables: str | None) -> Iterator[None]:
    saved = {k: os.environ.get(k) for k in variables}
    try:
        for k, v in variables.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def read_only(root: Path) -> Iterator[None]:
    """``root`` and every folder under it without write permission, restored afterwards; the test is
    skipped where that does not stop a write (root)."""
    from conftest import skip_if_still_writable

    folders = [root, *[p for p in root.rglob("*") if p.is_dir()]]
    modes = {p: p.stat().st_mode for p in folders}
    for p in folders:
        p.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)
    try:
        skip_if_still_writable(root)
        yield
    finally:
        for p in reversed(folders):
            p.chmod(modes[p])


# ---------- the command line, in process ----------


@dataclass
class Result:
    code: int
    out: str
    err: str

    def lines(self) -> list[str]:
        return self.out.splitlines()

    def errors(self) -> list[str]:
        return [line for line in self.err.splitlines() if line.startswith("error: ")]

    def nexts(self) -> list[str]:
        return [line.removeprefix("  next: ") for line in self.err.splitlines() if line.startswith("  next: ")]


def cli(*argv: str | Path, cwd: Path | None = None) -> Result:
    """``poisson-prove ARGV…`` in this process, stdin empty (not a terminal), from ``cwd``."""
    from poisson_prove import cli as prove_cli

    out, err = StringIO(), StringIO()
    here = Path.cwd()
    if cwd is not None:
        os.chdir(cwd)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            code = prove_cli.main([str(a) for a in argv], stdout=out, stderr=err, stdin=StringIO())
    finally:
        os.chdir(here)
    return Result(code, out.getvalue(), err.getvalue())


def doc(result: Result) -> dict[str, Any]:
    def refuse(name: str) -> Any:
        raise AssertionError(f"not strict JSON: {name}")

    parsed = json.loads(result.out, parse_constant=refuse)
    assert isinstance(parsed, dict), result.out[:200]
    return parsed


def saved_id(store: Path) -> list[str]:
    """The saved comparisons' ids, from the folders under ``.poisson/artifacts/comparison/``."""
    folder = store / ".poisson" / "artifacts" / "comparison"
    return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []


# ---------- the command in a process of its own ----------

#: What blocks an import in a child process: a ``sitecustomize`` on the path that makes the named
#: modules unimportable, as a missing install would (PF6.5, PF6.15).
_BLOCKER = """\
import sys
for _name in {names!r}:
    sys.modules[_name] = None
"""


def blocker(folder: Path, *modules: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sitecustomize.py").write_text(_BLOCKER.format(names=list(modules)), encoding="utf-8")
    return folder


def child_env(home: Path, *paths: Path, **extra: str | None) -> dict[str, str]:
    """A ``poisson-prove`` process's environment: this checkout's ``src`` first on its path, then
    ``paths``; ``HOME`` an empty folder; no store variable; none of the switches the look reads
    (``NO_COLOR``, ``CI``, ``TERM``, ``COLUMNS``) unless ``extra`` sets one; the planted keys set; UTF-8
    streams. ``extra`` with ``None`` removes a variable."""
    drop = ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "PYTHONWARNINGS", "PYTHONIOENCODING", "NO_COLOR", "CI",
            "TERM", "COLUMNS", "LINES", "FORCE_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE", "TEXTUAL", "XDG_CACHE_HOME")
    env = {k: v for k, v in os.environ.items() if k not in drop and not k.startswith("GITHUB_")}
    env.update(PYTHONPATH=os.pathsep.join([str(SRC), *(str(p) for p in paths)]), HOME=str(home),
               PYTHONIOENCODING="utf-8", TERM="xterm-256color", LANG="en_US.UTF-8", LC_ALL="en_US.UTF-8", **PLANTED_KEYS)
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = v
    return env


#: Every child starts through this launcher, which then runs Python again with the command's own
#: arguments: a child started from a background shell inherits SIGINT ignored and Ctrl-C needs it
#: live, and a terminal's child needs a session of its own with that terminal as its controlling
#: one. Done here rather than in ``preexec_fn``, which is not safe when the tests start children
#: from several threads.
_LAUNCH = """\
import fcntl, os, signal, sys, termios
signal.signal(signal.SIGINT, signal.SIG_DFL)
if sys.argv[1] == "session":
    os.setsid()
    for fd in (0, 1, 2):
        if os.isatty(fd):
            fcntl.ioctl(fd, termios.TIOCSCTTY, 0)
            break
os.execv(sys.executable, [sys.executable, *sys.argv[2:]])
"""


def launched(*python_args: str, session: bool = False) -> list[str]:
    """The command line that runs ``python PYTHON_ARGS…`` through the launcher."""
    return [sys.executable, "-c", _LAUNCH, "session" if session else "plain", *python_args]


def prove(argv: list[str], *, home: Path, cwd: Path, paths: tuple[Path, ...] = (), timeout: float = 120, **extra: str | None) -> Result:
    """``python -m poisson_prove ARGV…`` on pipes, stdin empty."""
    done = subprocess.run(
        launched("-m", "poisson_prove", *argv), cwd=cwd, env=child_env(home, *paths, **extra),
        stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
    )
    return Result(done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"))


# ---------- a pseudo-terminal ----------

#: Escape sequences: CSI, OSC (ended by BEL or ST), a character-set choice, and two-byte escapes.
_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][0-9A-Za-z]|\x1b[@-Z\\-_=>]")
_SGR = re.compile(r"\x1b\[([0-9;:]*)m")


def strip_escapes(text: str) -> str:
    return _ESCAPE.sub("", text)


@dataclass
class Step:
    """Wait until the terminal's screen shows ``until`` (or ``delay`` seconds pass), then type ``send``."""

    send: bytes
    until: str | tuple[str, ...] | None = None
    delay: float = 0.0


@dataclass
class PtyRun:
    code: int
    #: Everything written to stdout, as bytes decoded (a pseudo-terminal's ``\r\n`` read back as ``\n``).
    out: str
    #: Everything written to stderr, the same way.
    err: str
    #: The screens the program left on the stdout and stderr terminals, read by a terminal emulator.
    out_screen: list[str] = field(default_factory=list)
    err_screen: list[str] = field(default_factory=list)
    #: The screen as it stood when each step was taken.
    seen: list[list[str]] = field(default_factory=list)


def _winsize(fd: int, cols: int, rows: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def run_pty(
    argv: list[str],
    *,
    home: Path,
    cwd: Path,
    paths: tuple[Path, ...] = (),
    cols: int = 100,
    rows: int = 40,
    stdin: str = "pty",
    stdout: str = "pty",
    stderr: str = "pty",
    steps: tuple[Step, ...] = (),
    timeout: float = 120,
    command: list[str] | None = None,
    **extra: str | None,
) -> PtyRun:
    """``python -m poisson_prove ARGV…`` with each of stdin, stdout and stderr on a terminal or not.

    ``stdin`` is ``pty`` (the terminal stdout uses, or a terminal of its own when stdout is piped)
    or ``null``; ``stdout`` is ``pty`` or ``pipe``; ``stderr`` is ``pty`` (stdout's terminal),
    ``own`` (a terminal of its own, so the two streams stay apart while both are terminals) or
    ``pipe``. Every terminal is ``cols`` × ``rows``; the first is the process's controlling terminal.
    ``steps`` are typed into stdin's terminal in turn."""
    import pyte

    terminals: dict[str, tuple[int, int]] = {}

    def terminal(name: str) -> tuple[int, int]:
        if name not in terminals:
            controller, user = os.openpty()
            _winsize(user, cols, rows)
            terminals[name] = (controller, user)
        return terminals[name]

    if stdout == "pty":
        out_fd: Any = terminal("main")[1]
    else:
        out_fd = subprocess.PIPE
    if stdin == "pty":
        in_fd: Any = terminal("main")[1] if stdout == "pty" else terminal("input")[1]
    else:
        in_fd = subprocess.DEVNULL
    if stderr == "pty":
        err_fd: Any = terminal("main")[1] if "main" in terminals else terminal("errors")[1]
    elif stderr == "own":
        err_fd = terminal("errors")[1]
    else:
        err_fd = subprocess.PIPE
    proc = subprocess.Popen(
        launched(*(command or ["-m", "poisson_prove", *argv]), session=True), cwd=cwd, env=child_env(home, *paths, **extra),
        stdin=in_fd, stdout=out_fd, stderr=err_fd, close_fds=True,
    )
    for _, user in terminals.values():
        os.close(user)
    readers: dict[int, str] = {controller: name for name, (controller, _) in terminals.items()}
    if proc.stdout is not None:
        readers[proc.stdout.fileno()] = "out-pipe"
    if proc.stderr is not None:
        readers[proc.stderr.fileno()] = "err-pipe"
    raw: dict[str, bytearray] = {name: bytearray() for name in readers.values()}
    screens = {name: pyte.Screen(cols, rows) for name in terminals}
    streams = {name: pyte.ByteStream(screens[name]) for name in terminals}
    typed_into = terminals.get("main", terminals.get("input", (None, None)))[0]
    pending = list(steps)
    seen: list[list[str]] = []
    step_started = time.monotonic()
    deadline = time.monotonic() + timeout
    open_fds = set(readers)
    try:
        while open_fds:
            if time.monotonic() > deadline:
                raise AssertionError(f"timed out after {timeout} s; screen: {screens.get('main', screens.get('errors')).display if screens else raw}")
            ready, _, _ = select.select(list(open_fds), [], [], 0.05)
            for fd in ready:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    open_fds.discard(fd)
                    continue
                name = readers[fd]
                raw[name] += chunk
                if name in streams:
                    streams[name].feed(chunk)
            if pending and typed_into is not None:
                step = pending[0]
                shown = "\n".join(screens["main" if "main" in screens else next(iter(screens))].display)
                waited = time.monotonic() - step_started
                wanted = (step.until,) if isinstance(step.until, str) else step.until or ()
                if all(w in shown for w in wanted) and waited >= step.delay:
                    seen.append(list(screens["main" if "main" in screens else next(iter(screens))].display))
                    os.write(typed_into, step.send)
                    pending.pop(0)
                    step_started = time.monotonic()
            if proc.poll() is not None and not ready:
                # drain what is left, then stop: a closed terminal reads as an error, not as an end
                for fd in list(open_fds):
                    with contextlib.suppress(OSError):
                        while True:
                            r, _, _ = select.select([fd], [], [], 0.05)
                            if not r:
                                break
                            chunk = os.read(fd, 65536)
                            if not chunk:
                                break
                            raw[readers[fd]] += chunk
                            if readers[fd] in streams:
                                streams[readers[fd]].feed(chunk)
                    open_fds.discard(fd)
        code = proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        for controller, _ in terminals.values():
            with contextlib.suppress(OSError):
                os.close(controller)
    assert not pending, f"steps left untaken: {pending}; screen: {screens['main'].display if 'main' in screens else raw}"

    def text(name: str) -> str:
        return raw.get(name, bytearray()).decode("utf-8", "replace").replace("\r\n", "\n")

    out = text("main") if stdout == "pty" else text("out-pipe")
    if stderr == "pty" and stdout == "pty":
        err = out
    elif stderr in ("pty", "own"):
        err = text("errors")
    else:
        err = text("err-pipe")
    return PtyRun(
        code, out, err,
        out_screen=list(screens["main"].display) if "main" in screens else [],
        err_screen=list(screens["errors"].display) if "errors" in screens else [],
        seen=seen,
    )


def after_app(text: str) -> str:
    """What a terminal shows once a full-screen app has left: the text after its last return from
    the alternate screen, escapes removed."""
    cut = text.rfind("\x1b[?1049l")
    return strip_escapes(text[cut + len("\x1b[?1049l"):] if cut >= 0 else text)


@dataclass(frozen=True)
class Styled:
    char: str
    bold: bool
    dim: bool
    fg: int | None  # one of the 16 named colours (0 to 15), or None for the terminal's own
    other: tuple[str, ...]  # any other attribute set (italic, underline, reverse, a background, …)


#: SGR parameters: what each sets. 38 and 48 (256 and true colour) are always "other".
def styled(text: str) -> tuple[list[Styled], list[str]]:
    """``text`` read as a terminal would draw it, character by character with its SGR state, and
    every SGR parameter list that is not one of the 16 named colours, bold, dim or a reset."""
    out: list[Styled] = []
    odd: list[str] = []
    bold = dim = False
    fg: int | None = None
    other: set[str] = set()
    pos = 0
    plain_escape = _ESCAPE
    while pos < len(text):
        m = _SGR.match(text, pos)
        if m:
            params = [p for p in re.split("[;:]", m.group(1))] or ["0"]
            i = 0
            while i < len(params):
                p = int(params[i] or 0)
                if p == 0:
                    bold = dim = False
                    fg = None
                    other.clear()
                elif p == 1:
                    bold = True
                elif p == 2:
                    dim = True
                elif p == 22:
                    bold = dim = False
                elif 30 <= p <= 37:
                    fg = p - 30
                elif 90 <= p <= 97:
                    fg = p - 90 + 8
                elif p == 39:
                    fg = None
                elif p in (23, 24, 25, 27, 29, 49, 54, 55):
                    other.discard({23: "italic", 24: "underline", 25: "blink", 27: "reverse", 29: "strike", 49: "background", 54: "frame", 55: "overline"}[p])
                else:
                    name = {3: "italic", 4: "underline", 5: "blink", 7: "reverse", 8: "hidden", 9: "strike", 53: "overline"}.get(p)
                    if 40 <= p <= 47 or 100 <= p <= 107:
                        name = "background"
                    if p in (38, 48):
                        name = "256 or true colour"
                        i += 2 if i + 1 < len(params) and params[i + 1] == "5" else 4
                    odd.append(f"{p} in {m.group(0)!r}")
                    if name:
                        other.add(name)
                i += 1
            pos = m.end()
            continue
        e = plain_escape.match(text, pos)
        if e:
            pos = e.end()
            continue
        out.append(Styled(text[pos], bold, dim, fg, tuple(sorted(other))))
        pos += 1
    return out, odd


def role_of(cell: Styled) -> str:
    """A cell's colour role, as a snapshot's masks mark it: ``G`` green, ``Y`` yellow, ``R`` red,
    ``B`` bold, ``D`` dim, blank for none."""
    if cell.fg in (2, 10):
        return "G"
    if cell.fg in (3, 11):
        return "Y"
    if cell.fg in (1, 9):
        return "R"
    if cell.bold:
        return "B"
    if cell.dim:
        return "D"
    return " "


def styled_lines(text: str) -> list[list[Styled]]:
    cells, _ = styled(text.replace("\r\n", "\n"))
    lines: list[list[Styled]] = [[]]
    for c in cells:
        if c.char == "\n":
            lines.append([])
        elif c.char != "\r":
            lines[-1].append(c)
    return lines


# ---------- the app on Textual's pilot ----------


@dataclass
class Grid:
    """One screen of the app: each row's text, exactly as wide as the window, and each cell's role:
    ``V`` reverse (the focus), ``G``/``Y``/``R`` green, yellow, red, ``B`` bold, ``D`` dim, blank."""

    rows: list[str]
    masks: list[str]
    #: Every colour the look does not allow: a background, or a foreground other than the terminal's
    #: own and the 16 named colours' green, yellow and red.
    off_palette: set[str]

    @property
    def width(self) -> int:
        return len(self.rows[0]) if self.rows else 0

    @property
    def height(self) -> int:
        return len(self.rows)

    def text(self) -> str:
        return "\n".join(r.rstrip() for r in self.rows)

    @property
    def header(self) -> str:
        return self.rows[0]

    @property
    def body(self) -> list[str]:
        return self.rows[2:-3]

    @property
    def message(self) -> str:
        return self.rows[-3].rstrip()

    @property
    def keybar(self) -> str:
        return self.rows[-1].rstrip()

    def title(self) -> str:
        """The screen's title: the header's words after ``poisson-prove · ``, up to two spaces."""
        m = re.match(r"^poisson-prove · (\S+(?: \S+)*)", self.header)
        assert m, self.header
        return m.group(1)

    def focused(self) -> list[int]:
        return [i for i, row in enumerate(self.rows) if row.startswith("›")]

    def mask_of(self, row: int, start: int, length: int) -> str:
        return self.masks[row][start:start + length]

    def to_json(self) -> dict[str, Any]:
        return {"rows": self.rows, "masks": self.masks, "off_palette": sorted(self.off_palette)}

    @classmethod
    def from_json(cls, doc: dict[str, Any]) -> Grid:
        return cls(list(doc["rows"]), list(doc["masks"]), set(doc["off_palette"]))


def _role(style: Any) -> str:
    if style is None:
        return " "
    if style.reverse:
        return "V"
    color = style.color
    number = None
    if color is not None and not color.is_default and color.number is not None and color.type.name in ("STANDARD", "WINDOWS"):
        number = color.number
    if number in (2, 10):
        return "G"
    if number in (3, 11):
        return "Y"
    if number in (1, 9):
        return "R"
    if style.bold:
        return "B"
    if style.dim:
        return "D"
    return " "


def _off(color: Any, *, background: bool = False) -> str | None:
    """A colour the look does not allow: any background, and any foreground but the 16 named
    colours' green, yellow and red (the look: colour has four meanings, and dim is the fourth)."""
    if color is None or color.is_default:
        return None
    if not background and color.type.name in ("STANDARD", "WINDOWS") and color.number in (1, 2, 3, 9, 10, 11):
        return None
    return f"{'background' if background else 'foreground'} {color.type.name}:{color.name}"


def grid_of(app: Any) -> Grid:
    """The screen as the user's terminal shows it, cell by cell: the compositor's full update, the
    one Textual's own ``export_screenshot`` reads."""
    from rich.segment import Segment

    width, height = app.size
    update = app.screen._compositor.render_update(full=True, screen_stack=app._background_screens)
    rows: list[str] = []
    masks: list[str] = []
    off: set[str] = set()
    for line in update.strips:
        text, mask = [], []
        for strip in line:
            for seg in strip:
                if seg.control:
                    continue
                for ch in seg.text:
                    text.append(ch)
                    mask.append(_role(seg.style))
                if seg.style is not None:
                    for c, background in ((seg.style.color, False), (seg.style.bgcolor, True)):
                        bad = _off(c, background=background)
                        if bad:
                            off.add(bad)
        row, m = "".join(text), "".join(mask)
        rows.append(row[:width].ljust(width))
        masks.append(m[:width].ljust(width))
    assert len(rows) == height, (len(rows), height)
    _ = Segment  # the compositor's strips are Rich segments
    return Grid(rows, masks, off)


class Spy:
    """What the core returned to the app: every call of an operation the app reads through
    ``poisson_prove.core`` (reading f in ``test_pf5_api_core.py``), with its arguments and result or refusal, and
    every event ``start`` and ``resume`` reported."""

    OPERATIONS = ("open_store", "runs", "resolve", "run", "episodes", "read_spec", "plan", "start", "resume", "compare",
                  "check", "inspect", "save", "artifacts", "artifact", "build_ui", "view")

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any], Any]] = []
        self.events: list[Any] = []

    def clear(self) -> None:
        """Forget every call so far: ``drive`` clears each spy as the app opens, so what a test's own
        command lines asked of the core never stands in for what the app asked."""
        self.calls.clear()
        self.events.clear()

    @contextlib.contextmanager
    def installed(self) -> Iterator[Spy]:
        """The spy installed for a block, outside a test (a shared store's builder)."""
        from poisson_prove import core

        module = sys.modules[__name__]
        saved = {name: getattr(core, name) for name in self.OPERATIONS if hasattr(core, name)}
        spies = module._SPIES
        module._SPIES = [*spies, self]
        try:
            for name, real in saved.items():
                setattr(core, name, self._wrap(name, real))
            yield self
        finally:
            for name, real in saved.items():
                setattr(core, name, real)
            module._SPIES = spies

    def install(self, monkeypatch: pytest.MonkeyPatch) -> Spy:
        from poisson_prove import core

        monkeypatch.setattr(sys.modules[__name__], "_SPIES", [*_SPIES, self])  # undone after the test

        for name in self.OPERATIONS:
            real = getattr(core, name, None)
            if real is None:
                continue
            monkeypatch.setattr(core, name, self._wrap(name, real))
        return self

    def _wrap(self, name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any, **kwargs: Any) -> Any:
            if name in ("start", "resume") and kwargs.get("on_event") is not None:
                face = kwargs["on_event"]

                def on_event(event: Any) -> Any:
                    self.events.append(event)
                    return face(event)

                kwargs = {**kwargs, "on_event": on_event}
            try:
                result = real(*args, **kwargs)
            except BaseException as exc:
                self.calls.append((name, args, kwargs, exc))
                raise
            self.calls.append((name, args, kwargs, result))
            return result

        return call

    def results(self, name: str) -> list[Any]:
        return [r for n, _, _, r in self.calls if n == name and not isinstance(r, BaseException)]

    def refusals(self) -> list[BaseException]:
        from poisson_prove import core

        return [r for _, _, _, r in self.calls if isinstance(r, core.Refusal)]

    def views(self, kind: str) -> list[tuple[str, dict[str, Any]]]:
        """Every view of ``kind`` the core gave the app, newest last, as (address, document)."""
        out = []
        for name, args, kwargs, result in self.calls:
            if name != "view" or isinstance(result, BaseException):
                continue
            address = kwargs.get("address", args[1] if len(args) > 1 else None)
            if kind_of(str(address)) == kind:
                out.append((str(address), as_document(result)))
        return out


#: The spies installed for the test that is running (``Spy.install``); ``drive`` clears them.
_SPIES: list[Spy] = []


def as_document(obj: Any) -> dict[str, Any]:
    """A core result's or view's ``to_json()``: one strict JSON document with a ``schema`` (PF5.9),
    read as text or as the parsed mapping."""
    raw = obj.to_json()
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    parsed = json.loads(raw) if isinstance(raw, str) else json.loads(json.dumps(raw, allow_nan=False))
    assert isinstance(parsed, dict) and isinstance(parsed.get("schema"), str), str(raw)[:200]
    return parsed


HEX16 = r"[0-9a-f]{16}"
#: The views' addresses: PF12's seven, and home's (reading A5).
VIEW_ADDRESSES = {
    "home": re.compile(r"^home$"),
    "runs": re.compile(r"^index\.html$"),
    "run": re.compile(r"^runs/[^/]+\.html$"),
    "comparison": re.compile(rf"^comparisons/{HEX16}\.html$"),
    "condition": re.compile(rf"^comparisons/{HEX16}/{HEX16}\.html$"),
    "episodes": re.compile(rf"^runs/[^/]+/episodes/[^/]+/{HEX16}\.html$"),
    "could_not_detect": re.compile(rf"^comparisons/{HEX16}/could-not-detect\.html$"),
    "chart": re.compile(rf"^comparisons/{HEX16}/((heatmap|differences|limits)-[^/]+|{HEX16}/incidence-[^/]+)\.html$"),
}


def kind_of(address: str) -> str:
    address = address.split("#", 1)[0]
    for kind, pattern in VIEW_ADDRESSES.items():
        if pattern.match(address):
            return kind
    return "none"


class Session:
    """The app under Textual's pilot: keys in, screens out."""

    def __init__(self, pilot: Any) -> None:
        self.pilot = pilot

    @property
    def app(self) -> Any:
        return self.pilot.app

    def grid(self) -> Grid:
        return grid_of(self.app)

    async def press(self, *keys: str) -> None:
        for key in keys:
            await self.pilot.press(key)
            await self.pilot.pause()

    async def settle(self) -> Grid:
        """The screen once it stops changing (two reads 0.05 s apart agree). A screen still waiting
        for a result can be still too, so a test that needs a result waits for it by content."""
        last = None
        for _ in range(600):
            await self.pilot.pause(0.05)
            now = self.grid()
            if last is not None and now.rows == last.rows and now.masks == last.masks:
                return now
            last = now
        return last if last is not None else self.grid()

    async def wait(self, predicate: Callable[[Grid], bool], timeout: float = 90.0, what: str = "") -> Grid:
        deadline = time.monotonic() + timeout
        while True:
            await self.pilot.pause(0.05)
            if not self.app.is_running:
                raise AssertionError(f"the app exited (return code {self.app.return_code}) while waiting for {what}")
            g = self.grid()
            if predicate(g):
                return g
            if time.monotonic() > deadline:
                raise AssertionError(f"timed out waiting for {what}; the screen:\n{g.text()}")

    async def wait_text(self, text: str, timeout: float = 90.0) -> Grid:
        return await self.wait(lambda g: says(g.text(), text), timeout, repr(text))

    async def wait_title(self, title: str, timeout: float = 90.0) -> Grid:
        def ok(g: Grid) -> bool:
            try:
                return g.title() == title
            except AssertionError:
                return False

        g = await self.wait(ok, timeout, f"the {title} screen")
        return await self.settle() if g else g

    async def focus_row(self, predicate: Callable[[str], bool], limit: int = 60) -> Grid:
        """Press ``↓`` until the focused row satisfies ``predicate`` (from the top: ``Home`` first)."""
        await self.press("home")
        for _ in range(limit):
            g = await self.settle()
            rows = [g.rows[i] for i in g.focused()]
            if rows and predicate(rows[0]):
                return g
            await self.press("down")
        raise AssertionError(f"no row satisfies the predicate; the screen:\n{self.grid().text()}")

    async def read_through(self) -> str:
        """Every row the screen shows, its table read through to the end by ``PgDn``: the text of
        every screen seen, top to bottom, joined."""
        seen = [self.grid().text()]
        for _ in range(200):
            await self.press("pagedown")
            g = await self.settle()
            if g.text() == seen[-1]:
                break
            seen.append(g.text())
        await self.press("end")
        seen.append((await self.settle()).text())
        return "\n".join(seen)


def drive(
    scenario: Callable[[Session], Awaitable[Any]],
    *,
    cwd: Path,
    store: str | None = None,
    size: tuple[int, int] = (80, 24),
) -> tuple[int | None, Any]:
    """The app opened on ``store`` (as ``--store`` would give it; ``None`` for none) from ``cwd``, at
    ``size``, driven by ``scenario``; returns the app's return code and what the scenario returned."""
    from poisson_prove._cli_app import ProveApp

    async def main() -> tuple[int | None, Any]:
        for spy in _SPIES:
            spy.clear()
        app = ProveApp(store=store)
        async with app.run_test(size=size) as pilot:
            session = Session(pilot)
            await session.settle()
            value = await scenario(session)
            await pilot.pause()
        return app.return_code, value

    here = Path.cwd()
    os.chdir(cwd)
    try:
        return asyncio.run(main())
    finally:
        os.chdir(here)


# ---------- the network ----------

#: The recorders of the network attempts the running test watches, fed by one audit hook.
_NETWORK: list[list[str]] = []
_HOOKED: list[bool] = []
_NETWORK_EVENTS = frozenset({"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.sendto", "socket.bind"})


def _audit(event: str, args: tuple[Any, ...]) -> None:
    if not _NETWORK or event not in _NETWORK_EVENTS:
        return
    if event in ("socket.connect", "socket.sendto", "socket.bind"):
        import socket

        sock = args[0]
        if getattr(sock, "family", None) == socket.AF_UNIX:
            return
    for record in _NETWORK:
        record.append(f"{event} {args[1:]!r}")
    raise OSError(f"network blocked in this test: {event}")


@contextlib.contextmanager
def network_attempts() -> Iterator[list[str]]:
    """Every network connection or name lookup this process tries while the block runs, each
    refused: an audit hook sees them whatever reference to ``socket`` the code holds (PF6.12)."""
    if not _HOOKED:
        sys.addaudithook(_audit)
        _HOOKED.append(True)
    record: list[str] = []
    _NETWORK.append(record)
    try:
        yield record
    finally:
        _NETWORK.remove(record)


# ---------- facts: a document's scalars, and whether a screen shows them ----------


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def leaves(document: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every scalar in a JSON document with its JSON pointer (RFC 6901)."""
    if isinstance(document, dict):
        for key, value in document.items():
            yield from leaves(value, f"{prefix}/{_escape(str(key))}")
    elif isinstance(document, list):
        for i, value in enumerate(document):
            yield from leaves(value, f"{prefix}/{i}")
    else:
        yield prefix, document


_NUMBER = re.compile(r"[+\-\u2212]?\d+(?:\.\d+)?(?:e[+\-\u2212]?\d+)?%?", re.IGNORECASE)
_DURATION = re.compile(r"(?:(\d+) h)?\s*(?:(\d+) min)?\s*(?:(\d+(?:\.\d+)?) s)?")


def shows_number(text: str, value: float) -> bool:
    """Whether ``text`` prints ``value`` as rule 10 does: some number in it equals the value at the
    precision it was printed to (a percentage read over 100, a duration read in seconds). A value
    that is not a whole number is shown only by a number printed with two decimals or more, in
    ``2.3e-08`` form or as a percentage, so a ``0`` or a ``1`` elsewhere on the screen never shows a
    share, a p-value or a limit; a date's parts are not numbers."""
    plain = re.sub(r"\d{4}-\d\d-\d\d", " ", text).replace(",", "").replace("\u2212", "-")
    whole = float(value).is_integer()
    # a value written as it was recorded, as an axis's value is (``tool_fail_rate 0.3``)
    if not whole and re.search(rf"(?<![\d.]){re.escape(repr(float(value)))}(?![\d])", plain):
        return True
    # a whole token only: never a run of digits inside a hex id or a word (``c3bc1b052e785f44``)
    for m in re.finditer(rf"(?<![0-9A-Za-z])(?>{_NUMBER.pattern})(?![0-9A-Za-z])", plain, re.IGNORECASE):
        token = m.group(0)
        percent = token.endswith("%")
        body = token.rstrip("%")
        try:
            shown = float(body)
        except ValueError:
            continue
        if not whole and not percent and "e" not in body.lower() and len(body.split(".")[1] if "." in body else "") < 2:
            continue
        if percent:
            shown /= 100.0
        if "e" in body.lower():
            mantissa, exponent = body.lower().split("e")
            power = int(exponent.replace("\u2212", "-"))
            if abs(power) > 400:
                continue  # no float has this exponent: a whole token of digits, an e and digits
            decimals = len(mantissa.split(".")[1]) if "." in mantissa else 0
            tolerance = 0.5 * 10 ** (power - decimals)
        else:
            decimals = len(body.split(".")[1]) if "." in body else 0
            tolerance = 0.5 * 10 ** (-decimals) * (0.01 if percent else 1.0)
        if abs(shown - value) <= tolerance * (1 + 1e-9) + 1e-15:
            return True
    for m in _DURATION.finditer(text):
        if not any(m.groups()) or not m.group(0).strip().endswith(("s", "min", "h")):
            continue
        hours, minutes, seconds = (float(g) if g else 0.0 for g in m.groups())
        if abs(hours * 3600 + minutes * 60 + seconds - value) <= 0.5 + 0.05 * abs(value):
            return True
    return False


def shows_value(text: str, key: str, value: Any) -> bool:
    """Whether a screen's ``text`` shows one scalar of a view (reading A6): a number by rule 10; a
    hash by its first 12 hex (rule 10's hashes in text); a UTC time as written, to the second or to
    the minute, or its clock time alone; a code (``mcnemar_bh``) verbatim or by its words; any
    other string verbatim, matched without regard to case, line breaks or dashes."""
    if isinstance(value, bool) or value is None:
        return True
    if isinstance(value, (int, float)):
        return shows_number(text, float(value))
    value = str(value)
    if value == "":
        return True
    if HEX.match(value):
        return value[:12] in text
    m = ISO_UTC.match(value)
    if m:
        date, hm, sec = m.group(1), m.group(2), m.group(3)
        return any(form in text for form in (value, f"{date}T{hm}{sec}Z", f"{date} {hm}", f"{date}T{hm}", f"{hm}{sec}"))
    if CODE.match(value):
        words = value.removesuffix("_bh").replace("_", " ")
        return says(text, value) or says(text, words) or says(text, words.replace("logrank", "log rank"))
    if " → " in value:
        return says(text, value) or says(text, comparison_name(value)) or cut_shown(text, comparison_name(value))
    if len(value) <= 3:  # a short word is shown as a word, not as letters inside another
        return re.search(rf"(?<![\w.]){re.escape(value)}(?![\w])", text, re.IGNORECASE) is not None
    return says(text, value) or cut_shown(text, value)


def cut_shown(text: str, value: str) -> bool:
    """Whether ``text`` shows ``value`` cut in the middle with ``…``, as the look file cuts a name too
    long for its table column (its whole form is on the screen the row opens)."""
    for m in re.finditer(r"(\S+)…(\S+)", text):
        head, tail = m.group(1), m.group(2)
        if len(head) + len(tail) >= 4 and value.startswith(head.split(" ")[-1]) and value.endswith(tail):
            return True
    for m in re.finditer(r"(\S[^…\n]*?)…([^…\n]*\S)", text):
        head, tail = m.group(1).split("  ")[-1], m.group(2).split("  ")[0]
        if len(head) + len(tail) >= 4 and value.startswith(head) and value.endswith(tail):
            return True
    return False


def comparison_name(name: str) -> str:
    """A comparison's name as the app writes it: ``<before> → <after>`` with the words the two
    runs' names share at the start written once (``mock-agent 2026-10-23 a → b``)."""
    before, _, after = name.partition(" → ")
    a, b = before.split(" "), after.split(" ")
    shared = 0
    while shared < min(len(a), len(b)) - 1 and a[shared] == b[shared]:
        shared += 1
    return f"{before} → {' '.join(b[shared:])}" if shared else name


#: Keys a screen shows by what they stand for, not as text (reading A6): the document's schema and
#: kind by the screen itself; a condition's hash by the condition's axes; an address by the link or
#: the row that opens it (PF6.11 holds the links); a chart's drawing by its link (the
#: app draws no chart).
IDENTIFYING_KEYS = frozenset({"schema", "view", "config_hash", "condition_hash", "svg"})
#: A page's address inside the UI, whatever key holds it.
ADDRESS = re.compile(r"^(?:index|(?:runs|comparisons)/\S+)\.html(?:#\S*)?$")

#: The tables each view's screen shows, with the columns the screen gives them at 120
#: columns: a list item's other facts are on the screen the row opens, so only these are
#: checked here (reading A6). ``*`` is any key or index; a column's ``_note`` (its value's reason when
#: it is null) goes with it. A list not named is shown whole.
TABLE_COLUMNS: dict[str, dict[str, tuple[str, ...]]] = {
    "home": {"/items": ("kind", "name", "result", "rows", "id", "created", "limit")},
    "runs": {"/runs": ("number", "name", "run_id", "status", "backend", "target", "rows", "rows_without_outcome", "created_at"),
             "/comparisons": ()},
    "run": {"/cells": ("config/*", "n", "shares/*/value", "shares/*/lo", "shares/*/hi")},
    "comparison": {
        "/events": ("name", "kind", "n_worse", "n_safer", "n_higher", "n_lower", "n_unchanged", "n_could_not_tell", "n_conditions"),
        "/rows": ("config/*", "event", "share_a", "share_a/value", "share_a/lo", "share_a/hi", "share_a_lo", "share_a_hi", "share_b",
                  "share_b/value", "delta", "p", "q", "verdict", "mde_rise", "mde_fall"),
    },
    "episodes": {"/episodes": ("replicate_index", "seed", "outcome", "t")},
    "could_not_detect": {"/rows": ("config/*", "event", "share_a", "share_a/value", "mde_rise", "mde_fall", "could_tell")},
}


def unshown_rows(document: dict[str, Any], text: str, kind: str) -> list[str]:
    """Each row of a table ``TABLE_COLUMNS`` names, whose listed columns are not all on one line
    of ``text`` (its rows joined into lines where a row wraps): a table's facts are checked row by
    row, so a value shown in another row never stands in for this one (reading A6)."""
    lines = [line for line in joined_lines(text) if line.strip()]
    missing = []
    for table, columns in TABLE_COLUMNS.get(kind, {}).items():
        items = document.get(table.strip("/"))
        if not isinstance(items, list) or not columns:
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            wanted = []
            for pointer, value, _parent in _with_parents(item):
                rel = pointer.strip("/").split("/")
                key = rel[-1]
                if key.endswith("_note"):  # a null value's reason: on the screen (``unshown``), not pinned to its row
                    continue
                if key in IDENTIFYING_KEYS or key.endswith("address") or isinstance(value, bool) or value is None:
                    continue
                if any(_matches(rel, col) for col in columns):
                    wanted.append((key, value))
            if wanted and not any(all(shows_value(line, k, v) for k, v in wanted) for line in lines):
                missing.append(f"{table}/{i}: {wanted}")
    return missing


def joined_lines(text: str) -> list[str]:
    """A screen's rows joined into its lines: a row that starts deeper than the line above it
    continues that line (a wrapped line's hanging indent)."""
    out: list[str] = []
    indent = -1
    for row in text.splitlines():
        if not row.strip():
            out.append("")
            indent = -1
            continue
        lead = len(row) - len(row.lstrip(" "))
        if out and out[-1] and indent >= 0 and lead > indent + 2:
            out[-1] = out[-1] + " " + row.strip()
        else:
            out.append(row)
            indent = lead
    return out


def _matches(rel: list[str], pattern: str) -> bool:
    parts = pattern.split("/")
    return len(parts) == len(rel) and all(p == "*" or p == r for p, r in zip(parts, rel))


def _with_parents(document: Any, prefix: str = "") -> Iterator[tuple[str, Any, Any]]:
    if isinstance(document, dict):
        for key, value in document.items():
            if isinstance(value, (dict, list)):
                yield from _with_parents(value, f"{prefix}/{_escape(str(key))}")
            else:
                yield f"{prefix}/{_escape(str(key))}", value, document
    elif isinstance(document, list):
        for i, value in enumerate(document):
            if isinstance(value, (dict, list)):
                yield from _with_parents(value, f"{prefix}/{i}")
            else:
                yield f"{prefix}/{i}", value, document


def unshown(document: dict[str, Any], text: str, kind: str = "") -> list[str]:
    """The pointers of ``document``'s scalars that ``text`` does not show (reading A6). A ``_note`` is
    the reason a value is null, so it is checked only beside a null value (PF1.11)."""
    tables = TABLE_COLUMNS.get(kind, {})
    missing = []
    for pointer, value, parent in _with_parents(document):
        key = pointer.rsplit("/", 1)[-1]
        if key in IDENTIFYING_KEYS or key.endswith("address") or (isinstance(value, str) and ADDRESS.match(value)):
            continue
        if key.endswith("_note") and isinstance(parent, dict) and parent.get(key.removesuffix("_note")) is not None:
            continue
        table = next((t for t in tables if pointer.startswith(t + "/")), None)
        if table is not None:
            rel = pointer[len(table) + 1:].split("/")[1:]  # past the item's index
            if rel and rel[-1].endswith("_note"):
                rel = [*rel[:-1], rel[-1].removesuffix("_note")]
            if not any(_matches(rel, col) for col in tables[table]):
                continue
        if not shows_value(text, key, value):
            missing.append(f"{pointer}={value!r}")
    return missing


# ---------- the stores ----------


def _shared_base(factory: pytest.TempPathFactory) -> Path:
    base = factory.getbasetemp()
    if os.environ.get("PYTEST_XDIST_WORKER"):
        base = base.parent
    path = base / "pf6-shared"
    path.mkdir(parents=True, exist_ok=True)
    return path


def shared_world(factory: pytest.TempPathFactory, name: str, build: Callable[[Path], dict[str, Any]]) -> tuple[Path, dict[str, Any]]:
    """The folder ``name`` built once for the whole session by ``build(folder)``, which returns what
    the tests need to know about it (written beside it as JSON); every other worker waits."""
    base = _shared_base(factory)
    folder, done, failed, lock = base / name, base / f"{name}.json", base / f"{name}.error", base / f"{name}.lock"
    deadline = time.monotonic() + 1800
    while True:
        if time.monotonic() > deadline:
            raise RuntimeError(f"the shared store {name} was not built within 30 min ({lock} is held)")
        if done.exists():
            return folder, json.loads(done.read_text(encoding="utf-8"))
        if failed.exists():
            raise RuntimeError(f"building the shared store {name} failed:\n{failed.read_text(encoding='utf-8')}")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            time.sleep(0.2)
            continue
        try:
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir()
            home = base / f"{name}-home"
            home.mkdir(exist_ok=True)
            with environment(HOME=str(home), POISSON_PROVE_STORE=None, PROOFLOAD_STORE=None, XDG_CACHE_HOME=None, **PLANTED_KEYS):
                facts = build(folder)
            tmp = done.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(facts, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(done)
        except BaseException:
            failed.write_text(traceback.format_exc(), encoding="utf-8")
            raise
        finally:
            os.close(fd)


def copy_world(src: Path, dest: Path) -> Path:
    shutil.copytree(src, dest, symlinks=True)
    return dest


def _ok(result: Result) -> Result:
    assert result.code == 0, (result.code, result.out[-2000:], result.err[-2000:])
    return result


def run_names(store: Path) -> dict[str, str]:
    return {r["run_id"]: r["run_name"] for r in doc(_ok(cli("--store", store, "runs", "--json")))["runs"]}


def previous_and_latest(store: Path) -> tuple[str, str]:
    """The two newest complete runs, older first: what ``previous`` and ``latest`` name."""
    runs = doc(_ok(cli("--store", store, "runs", "--json")))["runs"]
    complete = sorted((r for r in runs if r["status"] == "complete"), key=lambda r: str(r["created_at"]))
    return complete[-2]["run_id"], complete[-1]["run_id"]


def build_old(folder: Path) -> dict[str, Any]:
    """The 0.0.1 store, copied as ``prove-runs``; its quickstart pair compared and saved (``diff
    --save``, the runs as 0.0.1 wrote them, paired at sweep time, events inferred); then ``ui``."""
    store = folder / "prove-runs"
    shutil.copytree(OLD / "store", store, symlinks=True)
    _ok(cli("--store", store, "diff", QS_A, QS_B, "--save", cwd=folder))
    _ok(cli("--store", store, "ui", cwd=folder))
    (cid,) = saved_id(store)
    return {"store": str(store), "a": QS_A, "b": QS_B, "comparison": cid, "names": run_names(store)}


def build_qs(folder: Path) -> dict[str, Any]:
    """The quickstart as a stranger runs it with this build: ``init --example``, the two sweeps of
    ``prove.toml`` (the second patched and paired with the first), then ``diff --save`` and ``ui``."""
    _ok(cli("init", "--example", cwd=folder))
    store = folder / "prove-runs"
    _ok(cli("sweep", "--yes", cwd=folder))
    _ok(cli("sweep", "--yes", "--target", f"{MOCK}:rollout_patched", "--pair-with", "latest", cwd=folder))
    _ok(cli("diff", "--save", cwd=folder))
    _ok(cli("ui", cwd=folder))
    (cid,) = saved_id(store)
    a, b = previous_and_latest(store)
    return {"store": str(store), "a": a, "b": b, "comparison": cid, "names": run_names(store)}


#: A small paired pair of the mock agent: two tasks by two failure rates, 30 replicates, so a
#: comparison takes well under a second. No comparison saved and no UI built.
SMALL_SPEC = """\
target = "poisson_prove.examples.mock_agent:rollout"
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = 30

[axes.task_id]
type = "categorical"
values = ["search", "refund"]

[axes.tool_fail_rate]
type = "continuous"
values = [0.0, 0.55]

[declare]
failures = ["timeout", "violated"]
"""
LOOSE = ("--max-mde", "1")


def build_small(folder: Path) -> dict[str, Any]:
    (folder / "small.toml").write_text(SMALL_SPEC, encoding="utf-8")
    store = folder / "prove-runs"
    _ok(cli("sweep", "small.toml", "--yes", *LOOSE, cwd=folder))
    _ok(cli("sweep", "small.toml", "--yes", *LOOSE, "--target", f"{MOCK}:rollout_patched", "--pair-with", "latest", cwd=folder))
    a, b = previous_and_latest(store)
    return {"store": str(store), "a": a, "b": b, "names": run_names(store)}


def _stats_stores() -> dict[str, Callable[[Path], dict[str, Any]]]:
    """Hand-written pairs, one store each, for the facts the verdict, conditions and condition
    screens must carry from the statistics (PF4.34 to PF4.46). Every run
    is written through the public ``Store`` by PF4's own test helpers."""
    from test_pf4_surfaces import A_ID, B_ID, MID, STANDARD_A, STANDARD_B, argon_pair, arm_runs, declared_outcomes, write_pair, write_run

    failures = declared_outcomes(failures=("fell",))
    # A condition where nothing ever happens, in both runs, so the runs' commonest outcome is ``ok``
    # and a comparison given no event infers ``fell``, as one given ``--event fell`` reads it.
    quiet = {"quiet": arm_runs(0, 120)}

    def standard(root: Path) -> dict[str, Any]:
        write_pair(root, {**STANDARD_A, **quiet}, {**STANDARD_B, **quiet}, declared_a=failures, declared_b=failures)
        return {}

    def mid(root: Path) -> dict[str, Any]:
        env = {"max_mde_accepted": 0.3}
        write_pair(root, {**MID, **quiet}, {**MID, **quiet}, environment_a=env, environment_b=env, declared_a=failures, declared_b=failures)
        return {}

    def argon(root: Path) -> dict[str, Any]:
        argon_pair(root, declared_a=failures, declared_b=failures)
        return {}

    def errors(root: Path) -> dict[str, Any]:
        a = {"c": arm_runs(5, 40), "d": arm_runs(5, 40)}
        b = {"c": arm_runs(5, 30) + [(30 + i, None, 1.0) for i in range(10)], "d": arm_runs(5, 40)}
        write_pair(root, a, b, declared_a=failures, declared_b=failures)
        return {}

    def peeking(root: Path) -> dict[str, Any]:
        resumed = {"max_mde_accepted": 0.2, "resumes": [{
            "at": "2026-10-20T10:05:00Z", "episodes_before": 160, "episodes_after": 240,
            "replicates_before": 20, "replicates_after": 40, "after_comparison": True,
        }]}
        write_pair(root, {**STANDARD_A, **quiet}, {**STANDARD_B, **quiet}, environment_b=resumed, declared_a=failures, declared_b=failures)
        return {}

    def cases(root: Path) -> dict[str, Any]:
        rows = arm_runs(5, 20)
        write_run(root, A_ID, {"c": rows, "d": rows}, meta={"c": {"case_id": "t1"}, "d": {"case_id": "t2"}})
        write_run(root, B_ID, {"c": rows, "d": rows}, meta={"c": {"case_id": "t3"}, "d": {"case_id": "t2"}},
                   created_at="2026-10-20T10:01:00Z")
        return {}

    def nothing(root: Path) -> dict[str, Any]:
        write_run(root, A_ID, {"only_a": arm_runs(5, 20)})
        write_run(root, B_ID, {"only_b": arm_runs(5, 20)}, created_at="2026-10-20T10:01:00Z")
        return {}

    def tiny(root: Path) -> dict[str, Any]:
        write_pair(root, {"c": arm_runs(1, 4), "d": arm_runs(2, 4), "q": arm_runs(0, 8)}, {"c": arm_runs(3, 4), "d": arm_runs(2, 4), "q": arm_runs(0, 8)},
              declared_a=failures, declared_b=failures)
        return {}

    def logrank(root: Path) -> dict[str, Any]:
        from test_pf4_surfaces import HORIZON

        def arm(fell: int, stuck: int, n: int) -> list[tuple[int, str | None, float]]:
            return [(i, "fell", 3.0) if i < fell else (i, "stuck", 2.0) if i < fell + stuck else (i, "ok", HORIZON) for i in range(n)]

        write_pair(root, {"c": arm(10, 5, 60), "quiet": arm(10, 5, 60)}, {"c": arm(10, 25, 60), "quiet": arm(10, 5, 60)}, salt="unshared")
        _ok(cli("--store", root, "diff", A_ID, B_ID, "--event", "fell", "--method", "logrank_bh", "--save"))
        (cid,) = saved_id(root)
        return {"comparison": cid}

    return {"standard": standard, "mid": mid, "argon": argon, "errors": errors, "peeking": peeking, "cases": cases,
            "nothing": nothing, "tiny": tiny, "logrank": logrank}


STATS_STORES = ("standard", "mid", "argon", "errors", "peeking", "cases", "nothing", "tiny", "logrank")


def build_stats(folder: Path) -> dict[str, Any]:
    """Each pair in its own folder, as ``<folder>/<name>/prove-runs``."""
    from test_pf4_surfaces import A_ID, B_ID

    facts: dict[str, Any] = {"a": A_ID, "b": B_ID}
    for name, build in _stats_stores().items():
        root = folder / name / "prove-runs"
        root.parent.mkdir()
        facts[name] = {"store": str(root), **build(root), "names": run_names(root)}
    return facts


# ---------- snapshots ----------


def normalise(text: str, *, comparison: str | None = None, keep: set[str] = frozenset()) -> str:  # type: ignore[assignment]
    """A screen with what changes from build to build replaced: the saved comparison's id (and its
    12-hex form) by ``<comparison-id>``, every UTC time not in ``keep`` (the runs' own) by ``<time>``,
    and the running version by ``<version>``."""
    from poisson_prove import __version__

    if comparison:
        text = text.replace(comparison, "<comparison-id>").replace(comparison[:12], "<comparison-id>")

    def time_of(m: re.Match[str]) -> str:
        return m.group(0) if m.group(0) in keep else "<time>"

    text = re.sub(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?Z", time_of, text)
    return re.sub(rf"(?<![\d.]){re.escape(__version__)}(?![\d.])", "<version>", text)


def run_times(store: Path) -> set[str]:
    """The UTC times the store's runs recorded, in every form a screen may print them."""
    times: set[str] = set()
    for manifest in store.glob("*/manifest.json"):
        for t in re.findall(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", manifest.read_text(encoding="utf-8")):
            m = ISO_UTC.match(t)
            assert m
            times |= {t, f"{m.group(1)}T{m.group(2)}{m.group(3)}Z", f"{m.group(1)} {m.group(2)}Z", f"{m.group(1)}T{m.group(2)}Z"}
    return times


if str(TESTS) not in sys.path:  # PF4's test helpers are imported by name from its test file
    sys.path.insert(0, str(TESTS))
