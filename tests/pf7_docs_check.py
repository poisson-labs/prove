"""The docs check: every block of code in the README and the docs is marked, and every block marked
to run runs, from a folder of its page's own, and does what its page shows.

**The marks.** A block is a fenced or an indented block of code. Its mark is an HTML comment alone
on its line before the block, with nothing but blank lines between them; GitHub and PyPI do not
show it:

    <!-- docs-check: run -->              run the block
    <!-- docs-check: skip: REASON -->     leave it, for the reason given in plain words
    <!-- docs-check: file NAME -->        write the block to NAME in the page's folder

and one mark for the page, before its first block, when its examples start from the quickstart
pair (``prove.toml`` and a ``./prove-runs`` holding the two quickstart runs, as the README's first
commands leave them):

    <!-- docs-check: setup quickstart -->

A block with no mark, a mark with no block straight under it, a mark the check does not know, a
skip with no reason, a ``setup`` mark after a block, and a block marked ``run`` that has nothing to
run (a ``console`` block with no ``$ `` line or with text before its first one, a shell block of
comments only) are each a failure of the page.

**What a block marked ``run`` does**, by the first word of its fence's info string:

- ``console``: every line starting with ``$ `` is a command (a line ending in ``\\`` goes on to the
  next); the lines under it, up to the next command, are what it printed.
- ``bash``, ``sh``, ``shell``, and an indented block: every line is a command; blank lines and
  lines starting with ``#`` are not.
- ``python``: the block runs as a script from the page's folder (``python -`` with the block on its
  stdin, so a module the page wrote there imports), with the environment's Python.
- ``toml``, ``json``, ``yaml`` (or ``yml``): the block parses; a TOML block that sets a key or a
  table a sweep spec has is also read by the spec reader's strict check, so a misspelt key in a
  table it knows is refused.
- anything else (``text``, no info string) is not run; such a block is marked ``skip`` or ``file``.

A ``file`` block is also parsed by its name's suffix (``.py`` compiles; ``.toml``, ``.json``,
``.yaml`` and ``.yml`` parse, a TOML file as a ``toml`` block is).

**What "does what its page shows" means.** Every command exits 0, or the code a trailing shell
comment ``# exits N`` gives (the page's shell sets ``pipefail``, so a pipe exits with its first
failure). Under a ``console`` command, the lines shown are checked against what
it printed (stdout and stderr together, in the order printed; progress counters such as
``412/1,746`` are left out, and so are blank lines):

- the shown lines appear in what was printed, in their order; a line ``…`` may stand anywhere for
  lines left out, and the first shown line, unless it is ``…``, is the first line printed;
- a shown line matches a printed one when both have the same indent and the same first field: the
  text up to the first two spaces (``trade``, ``no significant change``, ``error:``, ``method``),
  or, in a line with no two spaces, its first word. So the verdict word and the detail labels are
  checked, never the counts, names, times or sentences, which change from one run to the next;
- a ``next:`` line is a command to copy, so it matches only the same command exactly;
- before fields and ``next:`` lines are compared, a run's id (``20261025T235823Z-aba9``) and a
  date with the letter a run's name gives it (``2026-10-25 a``) are read as the same on both
  sides, since a page is written on one day and checked on another;
- the output of a command with ``--help`` is compared whole, line for line, except its usage
  block (from ``usage:`` to the first blank line), which is compared with its line breaks and runs
  of spaces read as one space: Python's versions wrap a usage line differently;
- where the page shows a JSON document under a command with ``--json``, what it printed is one
  JSON document; every key the page shows is one it holds, and the ``schema`` and ``verdict``
  shown are its own (a refusal under ``--json`` is text, and is read as any other output).

**Where it runs.** Each page runs in a folder of its own (a page of the example in a copy of the
example's folder), its blocks in order in one ``bash`` process, so ``cd``, ``export`` and
``source`` carry from one command to the next. The environment
is built, never inherited: ``PATH`` starts with the install's ``bin``, ``HOME`` is an empty folder
of the page's own, ``COLUMNS`` is 80, ``BROWSER`` opens nothing, no key or ``CI`` variable is set,
and every Python process the page starts blocks a network connection or a name lookup other than
loopback (an audit hook in ``sitecustomize``; an attempt is recorded and fails the page even when
the code under test swallowed the error). The guard sees Python only: a program that is not
Python (``curl``, ``uv``) or a Python started with ``-I`` is not covered. A page that does not
finish in five minutes fails, and everything it started is stopped.

**Two installs.** ``checkout``: the environment these tests run in, with the package installed from
this checkout; a line that installs Prove or makes a virtual environment (``python3 -m venv ...``,
``source .../bin/activate``, ``pip install ...``, ``uv pip install ...``, ``pipx install ...``,
``uv tool install ...``) is the install step: Prove is already installed, and any other package
the line names must be installed already too, or the page fails. ``wheel`` (slow): the wheel built
from this checkout, in a fresh environment of the page's own made with ``uv``; a
virtual-environment line runs as written, and an install line installs the built wheel (with the
extras it names) or the packages it names, with ``uv`` (which reaches the package index), into the
Python the page has active. Options are read as pip reads them: an option with a value takes it,
``-r FILE`` and ``-e PATH`` are passed on as written.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The lab's two standards are copied byte for byte from their canonical copies, so they carry no
#: marks and are not read by this check.
STANDARDS = ("docs/cli-look.md", "docs/repo-hygiene.md")
EXAMPLE = "examples/your-first-real-agent"

MARK = re.compile(r"<!--\s*docs-check:\s*(?P<body>.*?)\s*-->")
RUNNABLE = {"console", "bash", "sh", "shell", "python", "toml", "json", "yaml", "yml"}
SHELL = {"bash", "sh", "shell"}
PROGRESS = re.compile(r"^\s*\d[\d,]*/\d[\d,]*\s*$")
RUN_ID = re.compile(r"\b\d{8}T\d{6}Z-[0-9a-f]{4}\b")
DATED = re.compile(r"\b\d{4}-\d{2}-\d{2}(?: [a-z]{1,3}\b)?")
#: pip's options that take a value as their next word.
PIP_VALUED = {"-i", "--index-url", "--extra-index-url", "-f", "--find-links", "-c", "--constraint", "--python",
              "--target", "--prefix", "--root", "--platform", "--python-version", "--implementation", "--abi"}
EXITS = re.compile(r"#\s*exits\s+(\d+)\s*$")
VENV = re.compile(r"^python3?\s+-m\s+venv\s+(?P<venv>\S+)(?:\s*&&\s*(?:source|\.)\s+(?P=venv)/bin/activate)?$")
ACTIVATE = re.compile(r"^(?:source|\.)\s+\S+/bin/activate$")
INSTALL = re.compile(r"^(?:pip3?|python3?\s+-m\s+pip|uv\s+pip|uv\s+tool|pipx)\s+install\s+(?P<reqs>.+)$")
QUICKSTART = (
    "poisson-prove init --example",
    "poisson-prove sweep --yes",
    "poisson-prove sweep --yes --target poisson_prove.examples.mock_agent:rollout_patched --pair-with latest",
)

SITECUSTOMIZE = '''\
import os
import socket
import sys

_LOG = os.environ.get("DOCS_CHECK_NETWORK")
_LOCAL = {"127.0.0.1", "::1", "localhost", "", None}


def _host(value):
    if isinstance(value, bytes):
        value = value.decode("ascii", "replace")
    return value


def _refuse(what):
    if _LOG:
        with open(_LOG, "a", encoding="utf-8") as log:
            log.write(what + "\\n")
    raise OSError("the docs check allows no network connection: " + what)


def _hook(event, args):
    if event in ("socket.connect", "socket.sendto"):
        sock, address = args[0], args[1]
        if getattr(sock, "family", None) == getattr(socket, "AF_UNIX", object()):
            return
        host = _host(address[0]) if isinstance(address, tuple) else _host(address)
        if host not in _LOCAL:
            _refuse(event + " " + repr(address))
    elif event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
        if _host(args[0]) not in _LOCAL:
            _refuse(event + " " + repr(args[0]))


sys.addaudithook(_hook)
'''


# ---------- reading a page ----------


@dataclass(frozen=True)
class Mark:
    kind: str  #: run, skip, file
    arg: str  #: the reason of a skip, the name of a file, "" for run


@dataclass(frozen=True)
class Block:
    line: int  #: the page's line the block starts on, from 1
    lang: str  #: the first word of the info string, lower case; "" for an indented block
    indented: bool
    text: str
    mark: Mark | None


@dataclass(frozen=True)
class Page:
    path: str
    blocks: tuple[Block, ...]
    setup: str | None
    problems: tuple[tuple[str, str], ...]  #: (kind, what), kind one of KINDS


def corpus() -> list[str]:
    """The pages the check reads, as found: the README, ``CONTRIBUTING.md``, every Markdown page
    under ``docs/`` but the two standards, and the example's own Markdown."""
    found = [p for p in ("README.md", "CONTRIBUTING.md") if (ROOT / p).is_file()]
    for folder in ("docs", EXAMPLE):
        for path in sorted((ROOT / folder).rglob("*.md")) if (ROOT / folder).is_dir() else []:
            rel = path.relative_to(ROOT).as_posix()
            if rel not in STANDARDS:
                found.append(rel)
    return found


def read_mark(body: str) -> Mark | tuple[str, str]:
    """A mark's body, or the problem with it as (kind, what)."""
    if body == "run":
        return Mark("run", "")
    skip = re.fullmatch(r"skip\s*:\s*(.*)", body)
    if skip:
        reason = skip.group(1).strip()
        if len(re.findall(r"[A-Za-z]{2,}", reason)) < 2:
            return ("no-reason", f"a skip names no reason in plain words: {body!r}")
        return Mark("skip", reason)
    named = re.fullmatch(r"file\s+(\S+)", body)
    if named:
        name = named.group(1)
        if name.startswith("/") or ".." in Path(name).parts:
            return ("unknown-mark", f"a file mark names a path outside the page's folder: {name!r}")
        return Mark("file", name)
    return ("unknown-mark", f"a mark the docs check does not know: {body!r}")


def page_path(rel: str) -> Path:
    """A page by its path in the repository, or a page outside it by its absolute path."""
    return Path(rel) if Path(rel).is_absolute() else ROOT / rel


def read_page(rel: str) -> Page:
    from markdown_it import MarkdownIt

    text = page_path(rel).read_text(encoding="utf-8")
    blocks: list[Block] = []
    problems: list[tuple[str, str]] = []
    setup: str | None = None
    pending: tuple[int, Mark] | None = None
    for token in MarkdownIt("commonmark").parse(text):
        line = token.map[0] + 1 if token.map else 0
        if token.type == "html_block":
            found = MARK.fullmatch(token.content.strip())
            if pending is not None:
                problems.append(("dangling", f"line {pending[0]}: a mark with no block straight under it"))
                pending = None
            if found is None:
                if MARK.search(token.content):
                    problems.append(("unknown-mark", f"line {line}: a mark that is not alone in its comment"))
                continue
            body = found.group("body")
            setup_mark = re.fullmatch(r"setup\s+(\S+)", body)
            if setup_mark:
                if setup_mark.group(1) != "quickstart":
                    problems.append(("unknown-mark", f"line {line}: a setup the docs check does not know: {body!r}"))
                elif blocks or setup is not None:
                    problems.append(("setup-order", f"line {line}: the setup mark comes after a block or a second time"))
                else:
                    setup = "quickstart"
                continue
            mark = read_mark(body)
            if isinstance(mark, tuple):
                problems.append((mark[0], f"line {line}: {mark[1]}"))
            else:
                pending = (line, mark)
        elif token.type in ("fence", "code_block"):
            mark = pending[1] if pending is not None else None
            pending = None
            lang = token.info.strip().split()[0].lower() if token.type == "fence" and token.info.strip() else ""
            block = Block(line, lang, token.type == "code_block", token.content, mark)
            blocks.append(block)
            if mark is None:
                problems.append(("unmarked", f"line {line}: a block with no docs-check mark"))
            elif mark.kind == "run" and not block.indented and lang not in RUNNABLE:
                problems.append(("not-runnable", f"line {line}: a {lang or 'plain'} block cannot be run; mark it skip or file"))
            elif mark.kind == "run" and (block.indented or lang in SHELL | {"console"}) and nothing_to_run(block):
                problems.append(("not-runnable", f"line {line}: a block marked run with nothing to run"))
        elif pending is not None and token.type not in ("inline",):
            problems.append(("dangling", f"line {pending[0]}: a mark with no block straight under it"))
            pending = None
    if pending is not None:
        problems.append(("dangling", f"line {pending[0]}: a mark with no block straight under it"))
    return Page(rel, tuple(blocks), setup, tuple(problems))


def commands(block: Block) -> list[tuple[str, list[str] | None]]:
    """A runnable shell or console block's commands, each with the lines shown under it (a console
    block) or None (a shell block)."""
    lines = block.text.splitlines()
    out: list[tuple[str, list[str] | None]] = []
    if block.lang == "console":
        current: list[str] | None = None
        command = ""
        for raw in lines:
            if command.endswith("\\"):
                command = command[:-1] + " " + raw.strip()
                continue
            if raw.startswith("$ "):
                if command:
                    out.append((command, current))
                command, current = raw[2:].strip(), []
            elif command:
                assert current is not None
                current.append(raw)
        if command:
            out.append((command, current))
        return out
    command = ""
    for raw in lines:
        stripped = raw.strip()
        if command:
            command = command[:-1] + " " + stripped
        else:
            if not stripped or stripped.startswith("#"):
                continue
            command = stripped
        if not command.endswith("\\"):
            out.append((command, None))
            command = ""
    if command:
        out.append((command, None))
    return out


def nothing_to_run(block: Block) -> bool:
    """A shell block of comments only, or a console block with no command or text before its first."""
    if block.lang == "console":
        lines = [line for line in block.text.splitlines() if line.strip()]
        return not lines or not lines[0].startswith("$ ")
    return not commands(block)


def command_lines(page: Page) -> list[str]:
    """Every command a page's shell and console blocks give, marked or not."""
    return [c for b in page.blocks if b.indented or b.lang in SHELL | {"console"} for c, _ in commands(b)]


def expected_code(command: str) -> int:
    found = EXITS.search(command)
    return int(found.group(1)) if found else 0


def bare(command: str) -> str:
    """The command without a trailing ``# exits N``."""
    return EXITS.sub("", command).rstrip()


# ---------- the install step ----------


@dataclass
class Install:
    """Where a page's commands come from."""

    kind: str  #: checkout or wheel
    bin: Path  #: the folder whose commands come first on PATH
    wheel: Path | None = None


def _refused(why: str) -> str:
    """Shell text that fails its step, saying why, without ending the page's shell."""
    return f"( echo {shlex.quote('docs check: ' + why)} >&2; exit 1 )"


def install_command(command: str, install: Install) -> str | None:
    """What the check runs for a line that installs Prove or makes an environment; None for any
    other line. A line the check cannot read fails its step, saying why."""
    from importlib.metadata import PackageNotFoundError, distribution

    from packaging.requirements import InvalidRequirement, Requirement

    line = bare(command)
    if not (VENV.match(line) or ACTIVATE.match(line) or INSTALL.match(line)):
        return None
    if VENV.match(line) or ACTIVATE.match(line):
        return ":" if install.kind == "checkout" else line
    try:
        words = shlex.split(INSTALL.match(line).group("reqs"))  # type: ignore[union-attr]
    except ValueError as exc:
        return _refused(f"cannot read the install line: {exc}")
    targets: list[str] = []
    missing: list[str] = []
    at = 0
    while at < len(words):
        word = words[at]
        if word in ("-r", "--requirement", "-e", "--editable"):
            if at + 1 == len(words):
                return _refused(f"{word} with nothing after it")
            targets += [word, words[at + 1]]
            at += 2
            continue
        if word.split("=", 1)[0] in PIP_VALUED:
            at += 1 if "=" in word else 2
            continue
        if word.startswith("-"):
            at += 1
            continue
        at += 1
        try:
            parsed = Requirement(word)
        except InvalidRequirement:
            targets.append(word)  # a path, a URL or a wheel file, passed on as written
            continue
        if re.sub(r"[-_.]+", "-", parsed.name).lower() == "poisson-prove":
            extras = f"[{','.join(sorted(parsed.extras))}]" if parsed.extras else ""
            targets.append(f"{install.wheel}{extras}")
            continue
        targets.append(word)
        try:
            distribution(parsed.name)
        except PackageNotFoundError:
            missing.append(parsed.name)
    if install.kind == "checkout":
        return _refused(f"the test environment lacks {', '.join(missing)}") if missing else ":"
    uv = shutil.which("uv")
    if uv is None:
        return _refused("the wheel install needs uv: https://docs.astral.sh/uv/")
    return f'{shlex.quote(uv)} pip install --quiet --python "$(command -v python)" ' + " ".join(shlex.quote(t) for t in targets)


# ---------- running a page ----------


@dataclass
class Step:
    line: int
    run: str  #: the shell text the check runs
    shown: str  #: the command as the page shows it
    expect: int = 0
    output: list[str] | None = None


#: The ways a page can fail the check.
KINDS = ("unmarked", "dangling", "unknown-mark", "no-reason", "not-runnable", "setup-order", "parse", "exit",
         "first-line", "not-printed", "help", "json", "network", "timeout", "shell")


@dataclass
class Result:
    page: str
    found: list[tuple[str, str]] = field(default_factory=list)  #: (kind, what)
    #: every step that ran, with its exit code and what it printed
    ran: list[tuple[Step, int, list[str]]] = field(default_factory=list)
    folder: Path | None = None  #: the page's folder, left as the page left it

    @property
    def problems(self) -> list[str]:
        return [what for _, what in self.found]

    @property
    def kinds(self) -> set[str]:
        return {kind for kind, _ in self.found}


def utf8_locale() -> str:
    """A UTF-8 locale this machine has (``C.UTF-8`` on Linux, ``en_US.UTF-8`` on macOS)."""
    try:
        listed = subprocess.run(["locale", "-a"], capture_output=True, text=True, timeout=30).stdout.split()
    except (OSError, subprocess.SubprocessError):
        listed = []
    for name in ("C.UTF-8", "C.utf8", "en_US.UTF-8", "en_US.utf8"):
        if name in listed:
            return name
    return "C"


def uv_cache() -> str | None:
    """uv's own cache folder, so a fresh environment reuses what it downloaded before."""
    uv = shutil.which("uv")
    if uv is None:
        return None
    done = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True, timeout=60)
    return done.stdout.strip() or None


def environment(install: Install, home: Path, guard: Path, network_log: Path) -> dict[str, str]:
    locale = utf8_locale()
    env = {
        "PATH": f"{install.bin}:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(home),
        "LANG": locale,
        "LC_ALL": locale,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(guard),
        "COLUMNS": "80",
        "BROWSER": "true",
        "TMPDIR": str(home.parent / "tmp"),
        "DOCS_CHECK_NETWORK": str(network_log),
    }
    if install.kind == "wheel":
        env["UV_PYTHON_PREFERENCE"] = "only-system"
        env["UV_PYTHON_DOWNLOADS"] = "never"
        cache = os.environ.get("UV_CACHE_DIR") or uv_cache()
        if cache:
            env["UV_CACHE_DIR"] = cache
    return env


def plan(page: Page, install: Install, work: Path) -> tuple[list[Step], list[tuple[str, str]]]:
    """The steps a page's marked blocks give, and the problems found without running anything."""
    steps: list[Step] = []
    problems: list[tuple[str, str]] = []
    for n, block in enumerate(page.blocks):
        if block.mark is None or block.mark.kind == "skip":
            continue
        if block.mark.kind == "file":
            problem = parse_problem(Path(block.mark.arg).suffix.lstrip("."), block.text, block.mark.arg)
            if problem:
                problems.append(("parse", f"line {block.line}: {block.mark.arg} does not parse: {problem}"))
            source = work / f"block-{n}.file"
            source.write_text(block.text, encoding="utf-8")
            steps.append(Step(block.line, f"cp {shlex.quote(str(source))} {shlex.quote(block.mark.arg)}", f"(write {block.mark.arg})"))
            continue
        if not block.indented and block.lang not in RUNNABLE:
            continue
        if block.lang in ("toml", "json", "yaml", "yml"):
            problem = parse_problem(block.lang, block.text, f"the block on line {block.line}")
            if problem:
                problems.append(("parse", f"line {block.line}: the {block.lang} block does not parse: {problem}"))
            continue
        if block.lang == "python":
            script = work / f"block-{n}.py"
            script.write_text(block.text, encoding="utf-8")
            steps.append(Step(block.line, f"python - < {shlex.quote(str(script))}", "(the python block)"))
            continue
        for command, shown in commands(block):
            run = install_command(command, install)
            steps.append(Step(block.line, run if run is not None else bare(command), bare(command), expected_code(command), shown))
    return steps, problems


def parse_problem(kind: str, text: str, name: str = "block") -> str | None:
    try:
        if kind == "py":
            compile(text, "block", "exec")
        elif kind == "toml":
            data = tomllib.loads(text)
            from poisson_prove import sampler

            if set(data) & set(sampler._TOP_FIELDS):
                sampler._strict(Path(name), text, data)
        elif kind == "json":
            json.loads(text)
        elif kind in ("yaml", "yml"):
            import yaml

            yaml.safe_load(text)
    except Exception as exc:  # noqa: BLE001 -- any failure to parse is the finding
        return f"{type(exc).__name__}: {exc}"
    return None


def script_for(steps: list[Step], out: Path) -> str:
    lines = ["set -o pipefail", "__last=0"]
    for i, step in enumerate(steps):
        lines.append(f"( exit $__last ); {{\n{step.run}\n}} >{shlex.quote(str(out / f'{i}.out'))} 2>&1 </dev/null; "
                     f"__last=$?; echo $__last >{shlex.quote(str(out / f'{i}.rc'))}")
    return "\n".join(lines) + "\n"


def check_page(rel: str, install: Install, tmp: Path, quickstart: Path | None = None, timeout: int = 300) -> Result:
    """Run one page; the result lists every way it failed."""
    page = read_page(rel)
    work, folder, home = tmp / "work", tmp / "page", tmp / "home"
    result = Result(rel, list(page.problems), folder=folder)
    for made in (work, folder, home, tmp / "tmp", tmp / "guard"):
        made.mkdir(parents=True, exist_ok=True)
    (tmp / "guard" / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    network_log = tmp / "network.log"
    if rel.startswith(EXAMPLE + "/"):
        shutil.copytree(ROOT / EXAMPLE, folder, dirs_exist_ok=True)
    if page.setup == "quickstart":
        if quickstart is None:
            quickstart = build_quickstart(install, tmp / "quickstart")
        shutil.copytree(quickstart, folder, dirs_exist_ok=True)
    steps, problems = plan(page, install, work)
    result.found.extend(problems)
    if not steps:
        return result
    env = environment(install, home, tmp / "guard", network_log)
    shell = subprocess.Popen(["bash", "-c", script_for(steps, work)], cwd=folder, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        _, stderr = shell.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(shell.pid, signal.SIGKILL)
        shell.communicate()
        result.found.append(("timeout", f"the page did not finish in {timeout} s"))
        return result
    finally:
        try:
            os.killpg(shell.pid, signal.SIGKILL)  # whatever the page left running
        except ProcessLookupError:
            pass
    said = [line for line in stderr.splitlines() if line.strip() and "setlocale" not in line]
    if said:
        result.found.append(("shell", "the page's shell wrote: " + "\n".join(said)[:400]))
    for i, step in enumerate(steps):
        rc_file, out_file = work / f"{i}.rc", work / f"{i}.out"
        if not rc_file.exists():
            result.found.append(("exit", f"line {step.line}: `{step.shown}` never ran"))
            continue
        code = int(rc_file.read_text().strip() or "-1")
        printed = out_file.read_text(encoding="utf-8", errors="replace").splitlines()
        result.ran.append((step, code, printed))
        if code != step.expect:
            result.found.append(("exit", f"line {step.line}: `{step.shown}` exited {code}, the page says {step.expect}\n"
                                 + "\n".join(printed[:30])))
            continue
        if step.output is not None:
            problem = compare(step.shown, step.output, printed)
            if problem:
                result.found.append((problem[0], f"line {step.line}: `{step.shown}`: {problem[1]}"))
    if network_log.exists() and network_log.read_text().strip():
        result.found.append(("network", f"the page tried the network: {network_log.read_text().strip()[:400]}"))
    return result


# ---------- comparing what was shown with what was printed ----------


def head(line: str) -> str:
    """A line's first field: the text up to its first two spaces, else its first word."""
    text = line.strip()
    found = re.search(r"\S {2,}", text)
    if found:
        return text[: found.start() + 1]
    return text.split()[0] if text else ""


def indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def undated(text: str) -> str:
    """A line with run ids and dated run names read as one placeholder each."""
    return DATED.sub("<date>", RUN_ID.sub("<id>", text))


def same(shown: str, printed: str) -> bool:
    if indent(shown) != indent(printed):
        return False
    if shown.strip().startswith("next:"):
        return undated(shown.strip()) == undated(printed.strip())
    return head(undated(shown)) == head(undated(printed))


def help_lines(lines: list[str]) -> list[str]:
    """A help text with its usage block (``usage:`` to the first blank line) as one line, its
    spaces read as one: argparse wraps a usage line differently from one Python to the next."""
    text = "\n".join(lines).rstrip("\n").splitlines()
    if text and text[0].startswith("usage:"):
        end = next((i for i, line in enumerate(text) if not line.strip()), len(text))
        return [" ".join(" ".join(text[:end]).split())] + text[end:]
    return text


def compare(command: str, shown: list[str], printed: list[str]) -> tuple[str, str] | None:
    """How what was printed differs from what the page shows, as (kind, what), or None."""
    words = shlex.split(command, comments=True)
    if "--help" in words or "-h" in words:
        want, got = help_lines(shown), help_lines(printed)
        if want != got:
            return "help", "the help shown is not the help printed:\n" + "\n".join(
                f"  shown:   {w!r}\n  printed: {g!r}" for w, g in zip(want + [""] * len(got), got + [""] * len(want)) if w != g
            )[:1500]
        return None
    if "--json" in words and any(line.lstrip().startswith("{") for line in shown):
        return compare_json(shown, printed)
    want = [line for line in shown if line.strip()]
    if not want:
        return None
    got = [line for line in printed if line.strip() and not PROGRESS.match(line)]
    anchored = want[0].strip() != "…"
    want = [line for line in want if line.strip() != "…"]
    at = 0
    for k, line in enumerate(want):
        if k == 0 and anchored:
            if not got or not same(line, got[0]):
                return "first-line", f"the first line printed is {got[0] if got else '(nothing)'!r}, the page shows {line!r}"
            at = 1
            continue
        while at < len(got) and not same(line, got[at]):
            at += 1
        if at == len(got):
            return "not-printed", f"the page shows {line!r}, which was not printed (in that order):\n" + "\n".join(printed[:40])
        at += 1
    return None


def compare_json(shown: list[str], printed: list[str]) -> tuple[str, str] | None:
    text = "\n".join(printed)
    start = text.find("{")
    if start < 0:
        return "json", "no JSON document was printed"
    try:
        document, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        return "json", f"what was printed is not one JSON document: {exc}"
    keys: set[str] = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                keys.add(key)
                walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    walk(document)
    page = "\n".join(shown)
    for key in re.findall(r'"([^"\\]+)"\s*:', page):
        if key not in keys:
            return "json", f"the page shows the key {key!r}, which the document does not hold"
    for key in ("schema", "verdict"):
        found = re.search(rf'"{key}"\s*:\s*"([^"]*)"', page)
        if found and (not isinstance(document, dict) or document.get(key) != found.group(1)):
            return "json", f"the page shows {key} {found.group(1)!r}, the document says {document.get(key) if isinstance(document, dict) else None!r}"
    return None


# ---------- the installs and the quickstart pair ----------


def once(base: Path, name: str, build) -> Path:  # type: ignore[no-untyped-def]
    """``build(folder)`` once per test run, shared by every worker of the run."""
    folder, done = base / f"pf7-{name}", base / f"pf7-{name}.done"
    with open(base / f"pf7-{name}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not done.exists():
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True)
            build(folder)
            done.write_text("", encoding="utf-8")
    return folder


def build_quickstart(install: Install, folder: Path) -> Path:
    """The quickstart pair as the README's first commands leave it, made with the install's own
    command in an empty folder."""
    folder.mkdir(parents=True, exist_ok=True)
    home = folder.parent / (folder.name + "-home")
    home.mkdir(exist_ok=True)
    (folder.parent / "tmp").mkdir(exist_ok=True)
    env = environment(install, home, home, home / "network.log")
    for command in QUICKSTART:
        done = subprocess.run(shlex.split(command), cwd=folder, env=env, capture_output=True, text=True, timeout=600)
        assert done.returncode == 0, (command, done.stdout[-2000:], done.stderr[-2000:])
    return folder


def checkout_install() -> Install:
    bin_folder = Path(sys.executable).parent
    assert (bin_folder / "poisson-prove").is_file(), f"the test environment has no poisson-prove command in {bin_folder}"
    return Install("checkout", bin_folder)


def build_wheel(folder: Path) -> Path:
    """The wheel, built from a copy of the files a commit of this checkout would hold."""
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, timeout=60, check=True).stdout.decode().split("\0")
    source = folder / "source"
    for rel in files:
        if rel and (ROOT / rel).is_file() and not (ROOT / rel).is_symlink():
            (source / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, source / rel)
    script = "import sys\nfrom hatchling.build import build_wheel\nprint(build_wheel(sys.argv[1]))\n"
    done = subprocess.run([sys.executable, "-c", script, str(folder / "dist")], cwd=source, capture_output=True,
                          text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    (wheel,) = (folder / "dist").glob("*.whl")
    return wheel


def wheel_install(base: Path, tmp: Path) -> Install:
    """A fresh environment with the built wheel installed, for one page."""
    uv = shutil.which("uv")
    assert uv is not None, "the wheel install needs uv: https://docs.astral.sh/uv/"
    built = once(base, "wheel", build_wheel)
    (wheel,) = (built / "dist").glob("*.whl")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env.update(UV_PYTHON_PREFERENCE="only-system", UV_PYTHON_DOWNLOADS="never")
    venv = tmp / "venv"
    made = subprocess.run([uv, "venv", "--quiet", "--python", sys.executable, str(venv)], env=env, capture_output=True,
                          text=True, timeout=300)
    assert made.returncode == 0, made.stderr
    put = subprocess.run([uv, "pip", "install", "--quiet", "--python", str(venv / "bin" / "python"), str(wheel)], env=env,
                         capture_output=True, text=True, timeout=900)
    assert put.returncode == 0, put.stderr
    return Install("wheel", venv / "bin", wheel)
