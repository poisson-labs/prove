"""PF11, the setup agent: the frozen tests.

Written from the front-door spec's section 20 and its invariants PF11.1 to PF11.8, from the shared
page "Poisson - Spec Setup File" (format 1, 2026-10-23) and from the ruling Q64 of 2026-10-23
(the skill goes to ``.agents/skills/poisson-prove-setup/`` and ``.claude/skills/poisson-prove-setup/``,
the same bytes). The build is written against this file and does not edit it.

What PF11 promises, in one line: ``poisson-prove init --agent`` writes a skill and a prompt that the
person's own coding agent follows to set Prove up for them to review, and ``sweep --dry-run`` tells
that agent, without calling the rollout or the network, what is wrong with what it wrote. Prove
makes no model call; no test here calls a model, a coding agent or any paid service.

**Readings, named here** (each is a yes/no in the session log; the letters are the log's).

- (a) The packaged template is package data at ``poisson_prove/skills/poisson-prove-setup/SKILL.md``
  (beside the quickstart spec, as section 20.4's "packaged template" asks); each written ``SKILL.md``
  differs from it in exactly one line, the ``poisson-tool-version`` line, whose value is the version
  ``--version`` prints. What the template holds in that line's place is not pinned.
- (b) ``init --agent`` prints section 20.1's lines, pinned by their facts: a verdict line ``ok  wrote
  … (4 files)``, one ``  wrote  <path>`` line per file (each path, read from the folder the command
  ran in, is the file written; their order is free), ``  prompt  <the prompt>`` exactly, and one
  ``  next:`` line, nothing else on stdout and nothing on stderr. That ``next:`` line (section 20.1:
  give your coding agent the prompt, then review what it wrote) is the one ``next:`` line in Prove
  that is not a command.
- (c) "The user's repository" is the folder the command runs in, or ``--repo DIR`` as given; Prove
  does not look upward for a repository root.
- (d) The refusal of an existing file: exit 1, stdout empty, the ``error:`` line naming each of the
  four that exists by its path inside the repository, a ``next:`` line that is the command as typed
  with ``--force`` added, and nothing written. ``--force`` replaces the four and leaves every other
  file, a file of the person's own inside the skill's folder included. ``--print`` is never refused
  for existing files: it prints exactly the bytes ``init --agent`` writes and writes nothing.
- (e) ``--agent`` with ``--example``, ``--target`` or ``--out``, ``--repo`` or ``--print`` without
  ``--agent``, and ``--print`` with ``--json`` are wrong command lines (exit 2, nothing written).
  ``init --agent --json`` prints ``poisson-prove.init/1`` with ``wrote`` (the four paths) and
  ``prompt``.
- (f) The shared rules' ``<docs-url>`` is filled with ``https://pypi.org/project/poisson-prove/``.
- (g) The frontmatter holds exactly ``name``, ``description`` and ``metadata``; ``name`` follows the
  Agent Skills rules (lowercase letters, digits and single hyphens, at most 64 characters) and
  equals its folder; ``description`` is 1 to 1,024 characters; every ``metadata`` value is a string.
- (h) The body's ``#`` and ``##`` headings are the shared page's section 2.2, in order (the last,
  "Words Prove uses", optional); ``### Prove's own rules`` follows the shared rules directly and
  names ``--dry-run``, ``prove-runs/`` and ``.poisson/``; "What you are doing" is one paragraph;
  "Files you write" is one ``- `path` ...`` line per file, in ``poisson-writes``' order; "Steps" is
  six numbered items, each opening with its title in bold, the last two titled "Run the check" and
  "Stop and hand over", step 2 naming ``prove_rollout.py``, step 3 ``prove.toml`` and step 4
  ``[declare]``, ``failures`` and ``successes``, step 1 showing no command, step 5 naming
  ``--replicates``, ``next:`` and ``prove.toml``; "Hand over" is the shared opening and then Prove's
  list of four things to confirm, one each naming the axes, the outcomes, the replicates with their
  cost, and the wrapper.
- (i) Commands: every line of a ``bash`` block is a ``poisson-prove`` command (step 1 says "run
  nothing", so the agent runs no other program); "parses" is read as ``<command> --help`` exiting 0
  and every option the command carries appearing in its verb's help; every fenced block carries a
  language tag, and a line starting ``poisson-prove`` sits only in a ``bash`` block or in the one
  ``text`` block under "Hand over", which is ``poisson-prove sweep``.
- (j) Until PF8 freezes the plain-words test's pattern list, PF11 checks the skill and the prompt
  against the families section 9.3 lists; PF8 then adds both files to its corpus.
- (k) The scripted run reads the steps by number from the written skill and plays them with the
  expected files: ``expected/prove.toml`` is what step 3 writes (20 replicates, below the gate),
  without its ``[declare]`` table, which step 4 adds; the run's last ``prove.toml`` is that file
  with only ``replicates`` changed, to the number the refusal's ``--replicates`` named.
- (l) ``sweep`` imports the target with the spec file's folder first on the import path, so
  ``prove_rollout:rollout`` resolves when ``poisson-prove`` runs as an installed command; no test
  puts the sample repository on ``PYTHONPATH``.
- (m) "No socket opens" is read with a guard that logs every ``connect`` and every ``getaddrinfo``,
  loopback included; "no connection is made" means the blocked import's attempt never reaches that
  guard: Prove's own block stops it first, whether it patches the socket functions or raises from an
  audit hook (the guard raises the audit events before it logs). The check imports the target in a
  process that keeps the environment the command runs in (the person's own path and site setup),
  which is where the guard lives; each case that reads the guard checks it was loaded there.
- (n) The block covers name lookups too: the import of a module that connects to a host by name is
  refused naming ``host:port`` without a lookup leaving the machine.
- (o) "Changes nothing" holds for Python's byte code too: ``sweep --dry-run`` writes no
  ``__pycache__`` into the repository.
- (p) A target "takes (cfg, seed)" when its first two parameters are named ``cfg`` and ``seed`` and
  any further one has a default; section 20.3's own example, ``(task, client)``, is refused though
  it takes two arguments.
- (q) The listing of the module's callables may sit on the ``error:`` line or the ``next:`` lines.
- (r) The import failure's traceback is appended to ``~/.cache/poisson-prove/errors.log``.
- (s) "No kinds declared" covers a ``[declare]`` with outcomes only and a spec with no ``[declare]``;
  its note names ``higher`` and ``lower``. "An axis with one value, or none" covers an axis with one
  value and a spec in which no axis varies (one condition), the notes naming each such axis. A spec
  with no ``[axes]`` at all stays refused, as ``test_m2_sampler::test_i11`` freezes.
- (t) "A missing extra for ``[capture]``": any ``[capture]`` table without the ``[agent]`` extra's
  OpenTelemetry is refused at ``--dry-run``, the ``error:`` line naming ``[capture]`` and the extra
  and the install line ``poisson-prove[agent]`` on stderr, as ``--backend modal`` without ``modal``
  names its extra and ``poisson-prove[modal]``.
- (u) The two design rows pin the shape, not the numbers (the corrected gate is PF4's): the plan on
  stdout then the refusal, a ``next:`` line carrying ``--replicates``; a design that cannot flag a
  lone condition carries no ``--max-mde`` offer.
- (v) The plan of a right setup: its first line ``plan  `` with the rollout count, the target id and
  ``$0``; the ``target`` detail line ``prove_rollout:rollout (imports, takes cfg and seed)``; the
  ``outcomes`` detail line naming each failure after ``failures:`` and each success after
  ``successes:``; no ``note:``. The conditions, replicates and limit lines are PF4's and PF3's.
- (w) The import over 30 s waits 30 s, so its case is marked ``slow``.
- (x) Only ``--dry-run`` blocks the network: a real sweep's import reaches the socket layer.
- (y) ``docs/setup-with-your-agent.md`` is written by PF11's build with the table of locations
  PF11.8 reads (a Markdown table, a row per folder in backticks naming the agents that read it);
  PF7 writes the rest of the page around it.
- (z) A ``--repo`` that is not a folder is a refusal (exit 1, the path on the ``error:`` line), not
  a wrong command line.
- (aa) Every refusal of section 20.3 but the two design rows leaves stdout empty: the check refuses
  before it plans.
- (bb) "Parses" reads ``--help``'s stdout starting with ``usage``.
- (cc) Each check imports the target afresh from its spec's folder and leaves Python's import path
  and the person's modules as it found them, so a second check in the same process (the terminal
  app's, after an edit) reads the wrapper as it is now.
- (dd) ``init --agent`` in a repository that already holds ``prove_rollout.py`` and ``prove.toml``
  is not refused for them: only the four files it writes are its own.

**Where the agents read skills (Q64), checked against each one's own documentation on
2026-10-24.**

- Cursor, https://cursor.com/docs/context/skills: project skills in ``.agents/skills/`` and
  ``.cursor/skills/``; "for compatibility" it also loads ``.claude/skills/`` and ``.codex/skills/``.
- Codex, https://developers.openai.com/codex/skills (redirects to
  https://learn.chatgpt.com/docs/build-skills): it "scans ``.agents/skills`` in every directory from
  your current working directory up to the repository root"; ``.codex/skills`` is not named.
- Claude Code, https://code.claude.com/docs/en/skills: project skills in ``.claude/skills/`` from
  the starting folder up to the repository root; ``.agents/skills`` is not named.
- The format, https://agentskills.io/specification: ``name`` 1 to 64 characters, lowercase letters,
  digits and hyphens, no leading, trailing or doubled hyphen, equal to its folder; ``description``
  1 to 1,024 characters; ``metadata`` a map from string keys to string values.

**Seams with other modules.** ``init``, ``prove.toml``, ``target``, strict specs and the exit-2
refusal are PF3's (frozen on the PF3 freeze branch); the rows here that reuse them check only what section
20.3 adds. ``[declare]``'s kinds and their refusals are PF4.20's; the power gate and the design
that cannot flag are section 8.10's (PF4's re-freeze). The core's ``init_agent`` is PF5's and
private (Q28), so it is reached only through the command. The README section and the rest of
``docs/setup-with-your-agent.md`` are PF7's; the plain-words pattern list is PF8's.

**Lanes.** The code suite. One case is marked ``slow`` (the import that takes over 30 s). The
checks that import the person's code run as child processes, so no test's imports leak into
another's.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF11.1 the four files, the same bytes, the template, nothing else changed, the output | ``test_pf11_1_*`` |
| PF11.2 the refusal, ``--force``, ``--print`` | ``test_pf11_2_*`` |
| PF11.3 the shared setup-file check | ``test_pf11_3_*`` |
| PF11.4 the commands, ``--yes``, ``--dry-run``, the plain words | ``test_pf11_4_*`` |
| PF11.5 the scripted run | ``test_pf11_5_*`` |
| PF11.6 each wrong setup of section 20.3 | ``test_pf11_6_*`` |
| PF11.7 the rollout never called; the network blocked; the time limit (its case is PF11.6's) | ``test_pf11_7_*`` |
| PF11.8 the locations in the docs match the verified table | ``test_pf11_8_*`` |
| carried: ``init --agent`` gets what every verb gets | ``test_pf11_carried_*`` |
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURES = ROOT / "tests" / "fixtures" / "setup-agent"
SAMPLE = FIXTURES / "sample-repo"
EXPECTED = FIXTURES / "expected"
FORMAT = FIXTURES / "setup-file-format-1.txt"
TEMPLATE = SRC / "poisson_prove" / "skills" / "poisson-prove-setup" / "SKILL.md"
DOCS_PAGE = ROOT / "docs" / "setup-with-your-agent.md"
COMMAND = "poisson-prove"

SKILL = "poisson-prove-setup"
FOLDERS = (f".agents/skills/{SKILL}", f".claude/skills/{SKILL}")
FOUR = tuple(f"{folder}/{name}" for folder in FOLDERS for name in ("SKILL.md", "prompt.txt"))
PROMPT = "Use the poisson-prove-setup skill in this repository: set Poisson Prove up for me to review, then stop."
WRITES = ["prove_rollout.py", "prove.toml"]
CHECK = "poisson-prove sweep --dry-run"
NEXT_COMMAND = "poisson-prove sweep"
#: What Prove fills into the shared text (the shared page, sections 3 to 6; reading f).
NAMES = {
    "<Product full name>": "Poisson Prove",
    "<next command>": NEXT_COMMAND,
    "<docs-url>": "https://pypi.org/project/poisson-prove/",
    "<command>": COMMAND,
    "<Product>": "Prove",
    "<check>": CHECK,
    "<tool>": "prove",
}
METADATA_KEYS = ("poisson-setup-format", "poisson-tool", "poisson-tool-version", "poisson-writes", "poisson-check")
HEADINGS = [
    "# Set up Prove in this repository",
    "## What you are doing",
    "## Rules",
    "## Files you write",
    "## Steps",
    "## The check",
    "## Hand over",
]
OPTIONAL_LAST_HEADING = "## Words Prove uses"
OWN_RULES = "### Prove's own rules"

#: Q64's locations and the agents verified to read each, with where and when (PF11.8).
LOCATIONS: dict[str, tuple[str, ...]] = {
    ".agents/skills/": ("Codex", "Cursor"),
    ".claude/skills/": ("Claude Code", "Cursor"),
}
AGENTS = ("Claude Code", "Codex", "Cursor")
PROVENANCE = {
    "Cursor": ("https://cursor.com/docs/context/skills", "2026-10-24"),
    "Codex": ("https://developers.openai.com/codex/skills", "2026-10-24"),
    "Claude Code": ("https://code.claude.com/docs/en/skills", "2026-10-24"),
    "Agent Skills format": ("https://agentskills.io/specification", "2026-10-24"),
}

FIRST_LINE = re.compile(r"^([a-z][a-z ]*?)  \S")
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# ---------- the command line, in this process ----------


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

    @property
    def nexts(self) -> list[str]:
        return [line[len("  next: "):] for line in (self.out + self.err).splitlines() if line.startswith("  next: ")]

    @property
    def error(self) -> str:
        lines = [line for line in self.err.splitlines() if line.startswith("error: ")]
        assert lines, self.err
        return lines[0]

    @property
    def notes(self) -> list[str]:
        return [line for line in self.err.splitlines() if line.startswith("note: ")]


@pytest.fixture(autouse=True)
def _empty_home_and_no_store_variables(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)


@contextmanager
def inside(folder: Path) -> Iterator[None]:
    before = os.getcwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(before)


def run(cwd: Path, *argv: str | Path) -> Result:
    """``poisson-prove ARGV`` in this process, in ``cwd``, stdin not a terminal. Only for commands
    that import none of the person's code (``init``, ``--help``, ``--version``)."""
    from poisson_prove import cli as module

    out, err = StringIO(), StringIO()
    with inside(cwd):
        code = module.main([str(a) for a in argv], stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def assert_refusal(r: Result, *facts: str | re.Pattern[str], code: int = 1, plan_first: bool = False) -> None:
    """PF1.2's shape: the exit code, one ``error:`` line then only ``next:`` lines; stdout empty,
    or the plan and nothing else for the refusals that keep it; the facts on the ``error:`` line."""
    assert r.code == code, r
    if plan_first:
        out = r.out.splitlines()
        assert out and out[0].startswith("plan  "), r.out[:400]
        assert not [line for line in out[1:] if FIRST_LINE.match(line)], r.out
    else:
        assert r.out == "", r.out
    lines = [line for line in r.err.splitlines() if not line.startswith("note: ")]
    assert lines and lines[0].startswith("error: "), r.err
    assert all(line.startswith("  next: ") for line in lines[1:]), r.err
    for fact in facts:
        found = fact.search(lines[0]) if isinstance(fact, re.Pattern) else fact in lines[0]
        assert found, (fact, r.err)


def version() -> str:
    r = run(ROOT, "--version")
    assert r.code == 0, r
    return r.out.split()[1]


# ---------- files ----------


def snapshot(*roots: Path) -> dict[str, str]:
    """Every file and folder under the roots: a file by its sha256, a folder by ``dir``."""
    found: dict[str, str] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            key = f"{root.name}/{path.relative_to(root)}"
            found[key] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "dir"
    return found


def added(before: dict[str, str], after: dict[str, str], root: Path) -> list[str]:
    """Files under ``root`` that are new; asserts nothing that was there changed or went, and that
    every new folder holds a new file (an empty folder is a change too)."""
    changed = {k for k in before if after.get(k) != before[k]}
    assert not changed, sorted(changed)
    new = {k for k in after if k not in before}
    assert all(k.startswith(f"{root.name}/") for k in new), sorted(new)
    files = {k for k in new if after[k] != "dir"}
    lonely = [k for k in new if after[k] == "dir" and not any(f.startswith(k + "/") for f in files)]
    assert not lonely, lonely
    return sorted(k[len(root.name) + 1:] for k in files)


def users_own_files(repo: Path) -> None:
    """Files the person owns that a setup must never write to (section 20.1)."""
    for name, text in (
        ("AGENTS.md", "# Notes for coding agents\n\nRun the tests with pytest.\n"),
        ("CLAUDE.md", "Follow AGENTS.md.\n"),
        (".cursor/rules/style.mdc", "---\ndescription: house style\n---\nShort functions.\n"),
        (".claude/settings.json", "{}\n"),
        (".agents/skills/release-log/SKILL.md", "---\nname: release-log\ndescription: Write release notes.\n---\n# Release notes\n"),
    ):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def sample_repo(base: Path, *, with_expected: bool = False, user_files: bool = False) -> Path:
    repo = base / "repo"
    shutil.copytree(SAMPLE, repo, ignore=shutil.ignore_patterns("__pycache__"))
    if with_expected:
        for name in WRITES:
            shutil.copy(EXPECTED / name, repo / name)
    if user_files:
        users_own_files(repo)
    return repo


def fresh_skill(tmp_path: Path) -> str:
    """The skill as ``init --agent`` writes it into an empty folder."""
    folder = tmp_path / "fresh"
    folder.mkdir()
    r = run(folder, "init", "--agent")
    assert r.code == 0, r
    return (folder / FOUR[0]).read_text(encoding="utf-8")


# ---------- the skill's text ----------


def shared_text() -> dict[str, str]:
    """The shared page's byte-fixed text (format 1), parts by name, with Prove's names filled."""
    raw = FORMAT.read_text(encoding="utf-8")
    parts = re.split(r"^==> ([a-z-]+) <==\n", raw, flags=re.M)
    texts = dict(zip(parts[1::2], parts[2::2]))
    assert set(texts) == {"rules", "check", "prompt", "hand-over"}, sorted(texts)
    filled = {}
    for name, text in texts.items():
        for placeholder, value in NAMES.items():
            text = text.replace(placeholder, value)
        assert not re.search(r"<[A-Za-z][^>]*>", text), (name, text)
        filled[name] = text.rstrip("\n")
    return filled


def split_frontmatter(text: str) -> tuple[str, str]:
    assert text.startswith("---\n"), text[:80]
    end = text.index("\n---\n", 4)
    return text[4:end + 1], text[end + len("\n---\n"):]


@dataclass(frozen=True)
class Fence:
    lang: str
    lines: tuple[str, ...]
    #: the ``##`` heading the block sits under
    section: str


def fences(body: str) -> list[Fence]:
    found: list[Fence] = []
    section, opened, lang, indent, held = "", False, "", "", []
    for line in body.splitlines():
        if not opened:
            m = re.match(r"^(\s*)```(.*)$", line)
            if m:
                opened, indent, lang, held = True, m.group(1), m.group(2).strip(), []
            elif line.startswith("## ") or line.startswith("# "):
                section = line
            continue
        if line.strip() == "```":
            found.append(Fence(lang, tuple(held), section))
            opened = False
        else:
            held.append(line[len(indent):] if line.startswith(indent) else line)
    assert not opened, "a fenced block is never closed"
    return found


def headings(body: str) -> list[str]:
    out, opened = [], False
    for line in body.splitlines():
        if re.match(r"^\s*```", line):
            opened = not opened
        elif not opened and re.match(r"^#{1,6} ", line):
            out.append(line)
    return out


def section(body: str, heading: str) -> str:
    """The text under a heading, up to the next heading of the same or a higher level."""
    lines = body.splitlines()
    assert heading in lines, (heading, headings(body))
    at = lines.index(heading)
    level = len(heading) - len(heading.lstrip("#"))
    opened, end = False, len(lines)
    for i in range(at + 1, len(lines)):
        if re.match(r"^\s*```", lines[i]):
            opened = not opened
        elif not opened and re.match(rf"^#{{1,{level}}} ", lines[i]):
            end = i
            break
    return "\n".join(lines[at:end])


@dataclass(frozen=True)
class Step:
    number: int
    title: str
    text: str


def steps_of(body: str) -> list[Step]:
    """The numbered items of "Steps"; each opens with its title in bold (reading h)."""
    text = section(body, "## Steps")
    items = re.split(r"^(\d+)\. ", text, flags=re.M)
    steps = []
    for number, item in zip(items[1::2], items[2::2]):
        m = re.match(r"\*\*(.+?)\.?\*\*", item)
        assert m, f"step {number} does not open with its title in bold: {item[:80]!r}"
        steps.append(Step(int(number), m.group(1).rstrip("."), item))
    return steps


def commands(body: str, lang: str) -> list[tuple[str, str]]:
    """(section, command) for every non-empty line of every block tagged ``lang``."""
    return [(f.section, line.strip()) for f in fences(body) if f.lang == lang for line in f.lines if line.strip()]


#: The families section 9.3 lists, until PF8 freezes the full pattern list (reading j).
PLAIN_WORDS = [
    re.compile(r"\b[A-Z]{1,2}-?\d+(?:\.\d+)?[a-z]?\b"),
    re.compile(r"\b(?:LST|ADR)-?\d+\b"),
    re.compile(r"\bPhase \d|\bSession [AB]\b|\boracle\b|\bretrofit\b|\bshim\b|\bpacket\b|\bruled\b", re.I),
    re.compile(r"\bTaylor\b|\bGo1\b|\bHUMAIN\b|\bBorderless\b|\bCodestrap\b|45/44"),
    re.compile(r"\[\[|\bvault\b|\bObsidian\b|note[s]/|\bdispatch\b", re.I),
    re.compile(r"/User[s]/|~/cod[e]/"),
    re.compile(r"proofload", re.I),
]


# ---------- child processes ----------

GUARD = '''\
import os, socket, sys

_LOG = os.environ["PF11_SOCKET_LOG"]
_LOOPBACK = ("127.", "::1", "localhost")
sys._pf11_guard = True
for _name in filter(None, os.environ.get("PF11_HIDE", "").split(",")):
    sys.modules[_name] = None


def _log(what, address):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(what + " " + repr(address) + "\\n")


def _loopback(sock, address):
    if sock.family == getattr(socket, "AF_UNIX", None):
        return True
    host = address[0] if isinstance(address, tuple) else str(address)
    return str(host).startswith(_LOOPBACK)


_getaddrinfo = socket.getaddrinfo


def getaddrinfo(host, *args, **kwargs):
    # The audit event first: a build that blocks with an audit hook stops the lookup here.
    sys.audit("socket.getaddrinfo", host, args[0] if args else kwargs.get("port"), 0, 0, 0, 0)
    if host is not None and not str(host).startswith(_LOOPBACK):
        _log("lookup refused", (host,) + args[:1])
        raise OSError("the network is blocked in this test: " + repr(host))
    return _getaddrinfo(host, *args, **kwargs)


_connect, _connect_ex = socket.socket.connect, socket.socket.connect_ex


def connect(self, address):
    sys.audit("socket.connect", self, address)
    if not _loopback(self, address):
        _log("connect refused", address)
        raise OSError("the network is blocked in this test: " + repr(address))
    if self.family != getattr(socket, "AF_UNIX", None):
        _log("connect loopback", address)
    return _connect(self, address)


def connect_ex(self, address):
    sys.audit("socket.connect", self, address)
    if not _loopback(self, address):
        _log("connect refused", address)
        raise OSError("the network is blocked in this test: " + repr(address))
    if self.family != getattr(socket, "AF_UNIX", None):
        _log("connect loopback", address)
    return _connect_ex(self, address)


socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
socket.getaddrinfo = getaddrinfo
'''


@dataclass(frozen=True)
class Child:
    """A ``poisson-prove`` command run as the coding agent runs it: the installed command, in the
    repository, no key, ``HOME`` empty, a socket guard first on the path and nothing of the
    repository on it (reading l)."""

    code: int
    out: str
    err: str
    attempts: list[str]
    home: Path
    seconds: float
    #: the sweep spec the command read, as it was
    spec: str = ""
    #: the guard was loaded where the person's code was imported (set by code the test injects)
    live: bool = False

    @property
    def result(self) -> Result:
        return Result(self.code, self.out, self.err)


def run_child(repo: Path, base: Path, *argv: str, hide: tuple[str, ...] = (), extra: dict[str, str] | None = None,
              timeout: float = 120) -> Child:
    guard, home = base / "guard", base / "home"
    guard.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    (guard / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
    log = guard / "attempts.log"
    log.unlink(missing_ok=True)
    Path(f"{log}.live").unlink(missing_ok=True)
    command = Path(sys.executable).parent / COMMAND
    assert command.is_file(), f"the checkout's environment has no {COMMAND} command: {command}"
    env = {
        "PATH": f"{command.parent}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(home),
        "PYTHONPATH": os.pathsep.join([str(guard), str(SRC)]),
        "PF11_SOCKET_LOG": str(log),
        "PF11_HIDE": ",".join(hide),
        "PYTHONIOENCODING": "utf-8",
        "LANG": "C.UTF-8",
        "TMPDIR": str(home),
        **(extra or {}),
    }
    spec = repo / "prove.toml"
    written = spec.read_text(encoding="utf-8") if spec.is_file() else ""
    started = time.monotonic()
    done = subprocess.run([str(command), *argv], cwd=repo, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=timeout)
    seconds = time.monotonic() - started
    attempts = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    live = Path(f"{log}.live").exists()
    return Child(done.returncode, done.stdout, done.stderr, attempts, home, seconds, written, live)


def replicates_offered(r: Result) -> int:
    offers = [shlex.split(line) for line in r.nexts if "--replicates" in shlex.split(line)]
    assert len(offers) == 1, r.nexts
    words = offers[0]
    return int(words[words.index("--replicates") + 1])


def with_replicates(text: str, n: int) -> str:
    out, count = re.subn(r"^replicates = \d+$", f"replicates = {n}", text, flags=re.M)
    assert count == 1, text
    return out


def detail(plan: str, label: str) -> list[str]:
    return [m.group(1) for m in (re.match(rf"^  {label} {{2,}}(\S.*)$", line) for line in plan.splitlines()) if m]


# ---------- PF11.1 the four files ----------

PF11_1_CASES = ["an empty folder", "a repository with the person's own files", "a repository already set up",
                "--repo from another folder", "a folder inside a git repository", pytest.param("the built wheel", marks=pytest.mark.slow)]


@pytest.mark.parametrize("case", PF11_1_CASES)
def test_pf11_1_init_agent_writes_the_four_files_the_same_skill_twice_from_the_template_and_nothing_else(case: str, tmp_path: Path) -> None:
    home = Path(os.environ["HOME"])
    if case == "the built wheel":
        # The template ships as package data: the wheel carries it byte for byte.
        uv = shutil.which("uv")
        assert uv is not None, "the wheel is built with uv"
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
        built = subprocess.run([uv, "build", "--wheel", "--out-dir", str(tmp_path / "dist"), str(ROOT)], env=env, capture_output=True, text=True, timeout=600)
        assert built.returncode == 0, built.stderr
        (wheel,) = (tmp_path / "dist").glob("*.whl")
        with zipfile.ZipFile(wheel) as archive:
            assert archive.read("poisson_prove/skills/poisson-prove-setup/SKILL.md") == TEMPLATE.read_bytes()
        return
    if case == "an empty folder":
        repo = cwd = tmp_path / "empty"
        repo.mkdir()
        argv: list[str] = ["init", "--agent"]
    elif case == "a repository with the person's own files":
        repo = cwd = sample_repo(tmp_path, user_files=True)
        argv = ["init", "--agent"]
    elif case == "a repository already set up":
        # The agent's two files are there already: setting up again is not refused for them.
        repo = cwd = sample_repo(tmp_path, with_expected=True, user_files=True)
        argv = ["init", "--agent"]
    elif case == "--repo from another folder":
        repo = sample_repo(tmp_path, user_files=True)
        cwd = tmp_path / "elsewhere"
        cwd.mkdir()
        argv = ["init", "--agent", "--repo", str(repo)]
    else:
        (tmp_path / "project" / ".git").mkdir(parents=True)
        repo = cwd = tmp_path / "project" / "service"
        repo.mkdir()
        argv = ["init", "--agent"]
    roots = (tmp_path, home)
    before = snapshot(*roots)

    r = run(cwd, *argv)

    assert r.code == 0, r
    assert r.err == "", r.err
    # Exactly the four files, in the repository as given (reading c), and nothing else anywhere.
    assert added(before, snapshot(*roots), tmp_path) == sorted(str((repo / f).relative_to(tmp_path)) for f in FOUR)
    skills = [(repo / f).read_bytes() for f in FOUR if f.endswith("SKILL.md")]
    assert skills[0] == skills[1]
    for f in FOUR:
        if f.endswith("prompt.txt"):
            assert (repo / f).read_text(encoding="utf-8") == PROMPT + "\n"
    # The packaged template with only the version filled (reading a).
    written, template = skills[0].decode("utf-8").splitlines(), TEMPLATE.read_text(encoding="utf-8").splitlines()
    assert len(written) == len(template), (len(written), len(template))
    differ = [i for i, (w, t) in enumerate(zip(written, template)) if w != t]
    assert len(differ) == 1 and written[differ[0]].startswith("  poisson-tool-version:"), [written[i] for i in differ]
    assert yaml.safe_load(split_frontmatter(skills[0].decode("utf-8"))[0])["metadata"]["poisson-tool-version"] == version()
    # The output (reading b).
    out = r.out.splitlines()
    assert re.match(r"^ok  wrote .*\(4 files\)$", out[0]), r.out
    wrote = [line[len("  wrote  "):] for line in out if line.startswith("  wrote  ")]
    assert sorted((cwd / w).resolve() for w in wrote) == sorted((repo / f).resolve() for f in FOUR), wrote
    assert f"  prompt  {PROMPT}" in out, r.out
    assert len([line for line in out if line.startswith("  next: ")]) == 1, r.out
    assert len(out) == 1 + 4 + 2, r.out


# ---------- PF11.2 refusal, --force, --print ----------

PF11_2_CASES = [*(f"refused: {f} exists" for f in FOUR), "refused: two exist", "--force replaces the four only", "--print in an empty folder", "--print where the four exist"]


@pytest.mark.parametrize("case", PF11_2_CASES)
def test_pf11_2_an_existing_file_is_refused_force_replaces_only_the_four_and_print_writes_nothing(case: str, tmp_path: Path) -> None:
    skill = fresh_skill(tmp_path)
    repo = sample_repo(tmp_path, user_files=True)
    home = Path(os.environ["HOME"])
    if case.startswith("refused"):
        existing = (FOUR[0], FOUR[3]) if case == "refused: two exist" else (case[len("refused: "):-len(" exists")],)
        for f in existing:
            (repo / f).parent.mkdir(parents=True, exist_ok=True)
            (repo / f).write_text("the person's own text\n", encoding="utf-8")
        before = snapshot(repo, home)
        r = run(repo, "init", "--agent")
        assert_refusal(r, *existing)
        for f in FOUR:
            if f not in existing:
                assert f not in r.error, (f, r.error)
        assert snapshot(repo, home) == before
        assert any(sorted(shlex.split(n)) == sorted([COMMAND, "init", "--agent", "--force"]) for n in r.nexts), r.nexts
        return
    if case == "--force replaces the four only":
        for f in FOUR:
            (repo / f).parent.mkdir(parents=True, exist_ok=True)
            (repo / f).write_text("an older setup\n", encoding="utf-8")
        own = repo / FOLDERS[0] / "my-notes.md"
        own.write_text("the person's own note beside the skill\n", encoding="utf-8")
        before = snapshot(repo, home)
        r = run(repo, "init", "--agent", "--force")
        assert r.code == 0, r
        after = snapshot(repo, home)
        changed = sorted(k for k in before if after.get(k) != before[k])
        assert changed == sorted(f"repo/{f}" for f in FOUR), changed
        assert set(after) == set(before)
        for f in FOUR:
            assert (repo / f).read_text(encoding="utf-8") == (skill if f.endswith("SKILL.md") else PROMPT + "\n")
        return
    if case == "--print where the four exist":
        for f in FOUR:
            (repo / f).parent.mkdir(parents=True, exist_ok=True)
            (repo / f).write_text("an older setup\n", encoding="utf-8")
    else:
        repo = tmp_path / "empty"
        repo.mkdir()
    before = snapshot(repo, home)
    r = run(repo, "init", "--agent", "--print")
    assert r.code == 0, r
    assert r.err == "", r.err
    assert r.out == skill
    assert r.out.splitlines()[0] == "---"
    assert snapshot(repo, home) == before


# ---------- PF11.3 the shared setup-file check ----------

PF11_3_PARTS = ["the frontmatter", "the sections in order", "the shared text", "poisson-writes equals the files listed"]


@pytest.mark.parametrize("part", PF11_3_PARTS)
def test_pf11_3_the_skill_passes_the_shared_setup_file_check(part: str, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert run(repo, "init", "--agent").code == 0
    text = (repo / FOUR[0]).read_text(encoding="utf-8")
    front, body = split_frontmatter(text)
    meta = yaml.safe_load(front)
    shared = shared_text()

    if part == "the frontmatter":
        assert isinstance(meta, dict) and set(meta) == {"name", "description", "metadata"}, meta
        for folder in FOLDERS:
            assert meta["name"] == Path(folder).name
        assert SKILL_NAME.match(meta["name"]) and len(meta["name"]) <= 64, meta["name"]
        assert isinstance(meta["description"], str) and 1 <= len(meta["description"]) <= 1024, meta["description"]
        metadata = meta["metadata"]
        assert isinstance(metadata, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()), metadata
        assert set(METADATA_KEYS) <= set(metadata), sorted(metadata)
        assert metadata["poisson-setup-format"] == "1"
        assert metadata["poisson-tool"] == "poisson-prove"
        assert metadata["poisson-tool-version"] == version()
        assert metadata["poisson-writes"] == " ".join(WRITES)
        assert metadata["poisson-check"] == CHECK
    elif part == "the sections in order":
        top = [h for h in headings(body) if re.match(r"^#{1,2} ", h)]
        assert top in (HEADINGS, [*HEADINGS, OPTIONAL_LAST_HEADING]), top
        rules = section(body, "## Rules").splitlines()
        assert OWN_RULES in rules, rules
        own = section(body, OWN_RULES)
        for fact in ("--dry-run", "prove-runs/", ".poisson/"):
            assert fact in own, (fact, own)
        doing = section(body, "## What you are doing").split("\n", 1)[1].strip()
        assert doing and "\n\n" not in doing, doing
        steps = steps_of(body)
        assert [s.number for s in steps] == [1, 2, 3, 4, 5, 6], [s.number for s in steps]
        assert [s.title for s in steps[4:]] == ["Run the check", "Stop and hand over"], [s.title for s in steps]
        assert "```" not in steps[0].text and COMMAND not in steps[0].text, steps[0].text
        assert "prove_rollout.py" in steps[1].text, steps[1].text
        assert "case_id" in steps[1].text, steps[1].text
        assert "prove.toml" in steps[2].text, steps[2].text
        assert re.search(r"each case is its own (?:sweep )?axis", steps[2].text, re.I), steps[2].text
        for fact in ("[declare]", "failures", "successes"):
            assert fact in steps[3].text, (fact, steps[3].text)
        for fact in ("--replicates", "next:", "prove.toml"):
            assert fact in steps[4].text, (fact, steps[4].text)
        hand_over = section(body, "## Hand over")
        assert hand_over.startswith(shared["hand-over"]), hand_over
        tail = hand_over[len(shared["hand-over"]):]
        items = [line for line in tail.splitlines() if re.match(r"^(?:- |\d+\. )", line)]
        assert len(items) == 4, tail
        for facts in (("axes",), ("outcomes",), ("replicates", "cost"), ("wrapper",)):
            assert len([i for i in items if all(f in i for f in facts)]) == 1, (facts, items)
    elif part == "the shared text":
        rules = section(body, "## Rules")
        assert rules.startswith(shared["rules"] + "\n\n" + OWN_RULES), rules[:2000]
        assert section(body, "## The check").rstrip("\n") == shared["check"]
        assert section(body, "## Hand over").startswith(shared["hand-over"] + "\n"), section(body, "## Hand over")
        assert PROMPT == shared["prompt"]
    else:
        listed = []
        for line in section(body, "## Files you write").splitlines()[1:]:
            if line.strip():
                m = re.match(r"^- `([^`]+)`", line)
                assert m, f"not a file line: {line!r}"
                listed.append(m.group(1))
        assert listed == meta["metadata"]["poisson-writes"].split() == WRITES, listed


# ---------- PF11.4 the commands and the words ----------

PF11_4_PARTS = ["every command parses", "no --yes", "every sweep the agent runs carries --dry-run",
                "the person's command is one text block under Hand over", "commands only in tagged blocks", "the plain-words test"]


@pytest.mark.parametrize("part", PF11_4_PARTS)
def test_pf11_4_every_command_parses_none_answers_for_the_person_no_sweep_without_dry_run_and_the_words_are_plain(part: str, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert run(repo, "init", "--agent").code == 0
    text = (repo / FOUR[0]).read_text(encoding="utf-8")
    body = split_frontmatter(text)[1]
    agent = [command for _, command in commands(body, "bash")]
    person = commands(body, "text")
    assert agent, "no bash block"
    everything = agent + [command for _, command in person]

    if part == "every command parses":
        for command in everything:
            words = shlex.split(command)
            assert words[0] == COMMAND, command
            helped = run(repo, *words[1:], "--help")
            assert helped.code == 0 and helped.out.startswith("usage"), (command, helped)
            verb = next((w for w in words[1:] if not w.startswith("-")), None)
            verb_help = run(repo, verb, "--help").out if verb else run(repo, "--help").out
            for option in (w.split("=", 1)[0] for w in words[1:] if w.startswith("--")):
                assert re.search(rf"(?<![\w-]){re.escape(option)}(?![\w-])", verb_help), (command, option)
    elif part == "no --yes":
        for command in everything:
            assert not {"--yes", "-y"} & set(shlex.split(command)), command
    elif part == "every sweep the agent runs carries --dry-run":
        sweeps = [c for c in agent if "sweep" in shlex.split(c)]
        assert sweeps, agent
        for command in sweeps:
            assert "--dry-run" in shlex.split(command), command
    elif part == "the person's command is one text block under Hand over":
        under = [c for s, c in person if s == "## Hand over"]
        assert under == [NEXT_COMMAND], person
    elif part == "commands only in tagged blocks":
        blocks = fences(body)
        assert all(b.lang for b in blocks), [b.lines[:1] for b in blocks if not b.lang]
        for b in blocks:
            if b.lang == "bash" or (b.lang == "text" and b.section == "## Hand over"):
                continue
            stray = [line for line in b.lines if line.strip().startswith(COMMAND)]
            assert not stray, (b.lang, b.section, stray)
    else:
        for name in ("SKILL.md", "prompt.txt"):
            words = (repo / FOLDERS[0] / name).read_text(encoding="utf-8")
            found = [m.group(0) for pattern in PLAIN_WORDS for m in pattern.finditer(words)]
            assert not found, (name, found)


# ---------- PF11.5 the scripted run ----------


def test_pf11_5_the_scripted_run_plays_the_six_steps_and_ends_in_the_check_passing(tmp_path: Path) -> None:
    repo = sample_repo(tmp_path)
    assert run(repo, "init", "--agent").code == 0
    skill = (repo / FOUR[0]).read_text(encoding="utf-8")
    body = split_frontmatter(skill)[1]
    steps = steps_of(body)
    assert [s.number for s in steps] == [1, 2, 3, 4, 5, 6] and [s.title for s in steps[4:]] == ["Run the check", "Stop and hand over"], steps
    before = snapshot(repo)
    toml = (EXPECTED / "prove.toml").read_text(encoding="utf-8")
    without_declare, declare = toml.split("\n[declare]\n")

    # 1: read the code; run nothing. 2: the wrapper. 3: prove.toml, too few replicates. 4: [declare].
    assert "prove_rollout.py" in steps[1].text
    shutil.copy(EXPECTED / "prove_rollout.py", repo / "prove_rollout.py")
    assert "prove.toml" in steps[2].text
    (repo / "prove.toml").write_text(without_declare + "\n", encoding="utf-8")
    assert "[declare]" in steps[3].text
    (repo / "prove.toml").write_text(toml, encoding="utf-8")

    # 5: the check, as the skill shows it, until it passes; at most three fixes.
    (check,) = [c for s, c in commands(body, "bash") if s == "## The check"]
    runs: list[Child] = []
    for _ in range(4):
        runs.append(run_child(repo, tmp_path / f"check-{len(runs)}", *shlex.split(check)[1:]))
        last = runs[-1]
        if last.code == 0:
            break
        assert_refusal(last.result, plan_first=True)
        offered = replicates_offered(last.result)
        (repo / "prove.toml").write_text(with_replicates((repo / "prove.toml").read_text(encoding="utf-8"), offered), encoding="utf-8")
    assert [c.code for c in runs] == [1, 0], [(c.code, c.err) for c in runs]
    offered = replicates_offered(runs[0].result)
    assert offered > 20
    assert (repo / "prove.toml").read_text(encoding="utf-8") == with_replicates(toml, offered)
    assert (repo / "prove_rollout.py").read_bytes() == (EXPECTED / "prove_rollout.py").read_bytes()

    # The plan's detail lines, exit 0.
    last = runs[-1]
    assert last.out.splitlines()[0].startswith("plan  "), last.out
    assert detail(last.out, "target") == ["prove_rollout:rollout (imports, takes cfg and seed)"], last.out
    assert len(detail(last.out, "outcomes")) == 1, last.out
    # Nothing outside the two files changed (byte code included, reading o); no store; no socket.
    assert added(before, snapshot(repo), repo) == sorted(WRITES)
    assert not (repo / "prove-runs").exists() and not (repo / ".poisson").exists()
    assert not any(c.attempts for c in runs), [c.attempts for c in runs]


# ---------- PF11.6 each wrong setup of section 20.3 ----------

#: A guard check, then a connection the wrapper attempts when it is imported (reading m).
LIVE = 'import os, socket, sys\nif getattr(sys, "_pf11_guard", False):\n    open(os.environ["PF11_SOCKET_LOG"] + ".live", "w").close()\n'
CONNECT = LIVE + 'socket.create_connection(("{host}", 443), timeout=2)\n'


def edit(path: str, old: str, new: str) -> Callable[[Path], None]:
    def apply(repo: Path) -> None:
        text = (repo / path).read_text(encoding="utf-8")
        assert text.count(old) == 1, (path, old)
        (repo / path).write_text(text.replace(old, new), encoding="utf-8")
    return apply


def prepend(path: str, text: str) -> Callable[[Path], None]:
    def apply(repo: Path) -> None:
        (repo / path).write_text(text + (repo / path).read_text(encoding="utf-8"), encoding="utf-8")
    return apply


def at_import(text: str) -> Callable[[Path], None]:
    """Code the wrapper runs when it is imported, put right after its ``__future__`` import."""
    def apply(repo: Path) -> None:
        (repo / "prove_rollout.py").write_text(early(text, (repo / "prove_rollout.py").read_text(encoding="utf-8")), encoding="utf-8")
    return apply


def early(code: str, module: str) -> str:
    anchor = "from __future__ import annotations\n"
    assert module.count(anchor) == 1, module[:200]
    return module.replace(anchor, anchor + code)


def append(path: str, text: str) -> Callable[[Path], None]:
    def apply(repo: Path) -> None:
        (repo / path).write_text((repo / path).read_text(encoding="utf-8") + text, encoding="utf-8")
    return apply


def remove(path: str) -> Callable[[Path], None]:
    def apply(repo: Path) -> None:
        (repo / path).unlink()
    return apply


def cut(path: str, start: str, end: str | None = None) -> Callable[[Path], None]:
    """Remove from the line starting ``start`` up to (not including) the line starting ``end``,
    or to the end of the file."""
    def apply(repo: Path) -> None:
        lines = (repo / path).read_text(encoding="utf-8").splitlines(keepends=True)
        at = next(i for i, line in enumerate(lines) if line.startswith(start))
        stop = next((i for i, line in enumerate(lines) if i > at and end is not None and line.startswith(end)), len(lines))
        (repo / path).write_text("".join(lines[:at] + lines[stop:]), encoding="utf-8")
    return apply


def word(text: str) -> re.Pattern[str]:
    """``text`` as a whole word: ``t_unit`` is not found inside ``t_units``, nor ``target`` inside
    ``--target``."""
    return re.compile(rf"(?<![\w-]){re.escape(text)}(?![\w-])")


@dataclass(frozen=True)
class Row:
    edits: tuple[Callable[[Path], None], ...] = ()
    argv: tuple[str, ...] = ("--dry-run",)
    hide: tuple[str, ...] = ()
    #: the spec's replicates; None is the number the gate accepts
    replicates: int | None = None
    code: int = 1
    #: facts on the error line
    error: tuple[str | re.Pattern[str], ...] = ()
    #: facts anywhere on stderr
    stderr: tuple[str, ...] = ()
    #: whole next: lines that must be among the next: lines
    nexts: tuple[str, ...] = ()
    plan_first: bool = False
    #: facts a passing row's notes must carry between them
    note: tuple[str, ...] | None = None
    slow: bool = False
    check: Callable[[Child], None] | None = field(default=None)


def _one_traceback_in_the_log(child: Child) -> None:
    logged = (child.home / ".cache" / "poisson-prove" / "errors.log").read_text(encoding="utf-8")
    assert "Traceback" in logged and "ModuleNotFoundError" in logged, logged[-600:]


def _the_limit_is_kept(child: Child) -> None:
    assert 29 <= child.seconds < 60, child.seconds


def _offers_replicates_and_not_max_mde(child: Child) -> None:
    words = [shlex.split(n) for n in child.result.nexts]
    assert words and "--replicates" in words[0], child.result.nexts
    assert not any("--max-mde" in w for w in words), child.result.nexts


def _offers_replicates_and_max_mde(child: Child) -> None:
    words = [shlex.split(n) for n in child.result.nexts]
    assert any("--replicates" in w for w in words), child.result.nexts
    assert any("--max-mde" in w for w in words), child.result.nexts


def _the_line_of_the_key(child: Child) -> None:
    line = next(i for i, row in enumerate(child.spec.splitlines(), 1) if row.startswith("t_units = "))
    assert line >= 10, line
    after_file = child.result.error.split("prove.toml", 1)[1]
    assert re.search(rf"(?<![\d.]){line}(?![\d.])", after_file), (line, child.result.error)


def _the_callables_and_nothing_else(child: Child) -> None:
    assert "rollout_v1" in child.err, child.err
    for name in ("CASES", "MAX_CALLS"):
        assert not word(name).search(child.err), (name, child.err)


def _points_to_the_rollout_contract(child: Child) -> None:
    assert any("your-own-agent" in n for n in child.result.nexts), child.result.nexts


def _plan_lines(child: Child) -> None:
    first = child.out.splitlines()[0]
    assert first.startswith("plan  ") and "support-agent" in first and "$0" in first, first
    rollouts = re.search(r"([\d,]+) rollouts", first)
    found = re.search(r"^replicates = (\d+)$", child.spec, flags=re.M)
    assert found, child.spec
    assert rollouts and rollouts.group(1) == f"{16 * int(found.group(1)):,}", first
    assert detail(child.out, "target") == ["prove_rollout:rollout (imports, takes cfg and seed)"], child.out
    (outcomes,) = detail(child.out, "outcomes")
    failures = re.search(r"failures: ([^;]+)", outcomes)
    successes = re.search(r"successes: ([^;]+)", outcomes)
    assert failures and {w.strip() for w in failures.group(1).split(",")} == {"wrong_refund", "timeout"}, outcomes
    assert successes and {w.strip() for w in successes.group(1).split(",")} == {"resolved"}, outcomes


def _right(child: Child) -> None:
    _plan_lines(child)
    assert child.result.notes == [], child.err


def _right_and_run(child: Child) -> None:
    """A real sweep of the expected files: the same plan lines, and the wrapper runs to the end."""
    _plan_lines(child)
    assert [line for line in child.out.splitlines() if line.startswith("done  ")], child.out


#: Comment lines put first, so the line an unknown key is on has two digits.
OPENING = "".join(f"# line {i}\n" for i in range(1, 10))

ROWS: dict[str, Row] = {
    "no prove.toml": Row((remove("prove.toml"),), nexts=(f"{COMMAND} init", f"{COMMAND} init --agent")),
    "an unknown key": Row((prepend("prove.toml", OPENING), edit("prove.toml", "t_unit = ", "t_units = ")),
                          error=("prove.toml", "t_units", word("t_unit")), check=_the_line_of_the_key),
    "no target": Row((cut("prove.toml", "target = ", "target_id"),), code=2, error=("--target", word("target"), "prove.toml")),
    "the target's module does not import": Row(
        (edit("prove_rollout.py", "from support_agent.agent import", "from support_agnt.agent import"),),
        error=('"prove_rollout:rollout"', "ModuleNotFoundError", "support_agnt"), check=_one_traceback_in_the_log),
    "importing the target connects to a host": Row((at_import(CONNECT.format(host="api.example.com")),), error=("api.example.com:443",)),
    "importing the target takes over 30 s": Row((at_import("import time\ntime.sleep(90)\n"),), error=("30 s",), slow=True, check=_the_limit_is_kept),
    "the module has no such name": Row((edit("prove_rollout.py", "def rollout(", "def rollout_v1("),), error=('"prove_rollout"', '"rollout"'),
                                       check=_the_callables_and_nothing_else),
    "the name is not callable": Row(
        (edit("prove_rollout.py", "def rollout(", "def rollout_v1("), append("prove_rollout.py", 'rollout = "not a function"\n')),
        error=('"prove_rollout"', '"rollout"'), check=_the_callables_and_nothing_else),
    "the target takes (task, client)": Row(
        (edit("prove_rollout.py", "def rollout(cfg: dict[str, Any], seed: int)", "def rollout(task: dict[str, Any], client: int)"),),
        error=("(task, client)", "(cfg, seed)"), check=_points_to_the_rollout_contract),
    "the target takes (cfg)": Row((edit("prove_rollout.py", "def rollout(cfg: dict[str, Any], seed: int)", "def rollout(cfg: dict[str, Any])"),),
                                  error=("(cfg)", "(cfg, seed)")),
    "a failure not among the outcomes": Row((edit("prove.toml", 'failures = ["wrong_refund", "timeout"]', 'failures = ["wrong_refund", "timeout", "crashed"]'),),
                                            error=(word("crashed"),)),
    "an outcome both a failure and a success": Row((edit("prove.toml", 'successes = ["resolved"]', 'successes = ["resolved", "timeout"]'),),
                                                   error=(word("timeout"),)),
    "no kinds declared": Row((cut("prove.toml", "failures = "),), code=0, note=("higher", "lower")),
    "no [declare]": Row((cut("prove.toml", "[declare]"),), code=0, note=("higher", "lower")),
    "an axis with one value": Row((edit("prove.toml", "values = [0.0, 0.7]", "values = [0.0]"),), code=0, note=("temperature",)),
    "no axis varies": Row((edit("prove.toml", "values = [0.0, 0.7]", "values = [0.0]"), edit("prove.toml", 'values = ["v1", "v2"]', 'values = ["v2"]'),
                           edit("prove.toml", 'values = ["t1", "t2", "t3", "t4"]', 'values = ["t1"]')),
                          code=0, note=("prompt_version", "temperature", "ticket")),
    "--backend modal without its extra": Row(argv=("--dry-run", "--backend", "modal"), hide=("modal",), error=(word("modal"),),
                                             stderr=("poisson-prove[modal]",)),
    "[capture] without its extra": Row(
        (append("prove.toml", "\n[capture]\ninstrument = []\nmax_observation_bytes = 4096\n"),), hide=("opentelemetry",),
        error=("[capture]", word("agent")), stderr=("poisson-prove[agent]",)),
    "an underpowered design": Row(replicates=20, plan_first=True, check=_offers_replicates_and_max_mde),
    "a design that cannot flag a lone condition": Row(replicates=2, plan_first=True, check=_offers_replicates_and_not_max_mde),
    "everything right": Row(code=0, check=_right),
    "everything right, as a real sweep": Row(argv=("--yes",), code=0, check=_right_and_run),
}


@pytest.fixture(scope="module")
def ready(tmp_path_factory: pytest.TempPathFactory) -> int:
    """The replicates the gate accepts for the expected files: the number the expected setup's
    refusal offers (the scripted run proves that number passes)."""
    base = tmp_path_factory.mktemp("ready")
    repo = sample_repo(base, with_expected=True)
    first = run_child(repo, base / "first", "sweep", "--dry-run")
    assert first.code == 1, first.err
    return replicates_offered(first.result)


def setup_with(row: Row, base: Path, ready: int) -> Path:
    """The expected files in the sample repository, with the row's wrong setup applied."""
    repo = sample_repo(base, with_expected=True)
    spec = repo / "prove.toml"
    spec.write_text(with_replicates(spec.read_text(encoding="utf-8"), ready if row.replicates is None else row.replicates), encoding="utf-8")
    for change in row.edits:
        change(repo)
    return repo


@pytest.mark.parametrize("name", [pytest.param(n, marks=pytest.mark.slow) if r.slow else n for n, r in ROWS.items()])
def test_pf11_6_each_wrong_setup_gives_its_rows_exit_code_and_facts(name: str, tmp_path: Path, ready: int) -> None:
    row = ROWS[name]
    repo = setup_with(row, tmp_path, ready)
    before = snapshot(repo)
    child = run_child(repo, tmp_path, "sweep", *row.argv, hide=row.hide)
    r = child.result
    if "--dry-run" in row.argv:
        # The check changes nothing, empty folders and byte code included (reading o).
        after = snapshot(repo)
        assert after == before, sorted(set(after) ^ set(before))
    assert "Traceback" not in r.err, r.err
    if row.code == 0:
        assert r.code == 0, r
        assert r.out.splitlines()[0].startswith("plan  "), r.out
        if row.note is not None:
            assert r.notes, r.err
            for fact in row.note:
                assert any(fact in note for note in r.notes), (fact, r.notes)
    else:
        assert_refusal(r, *row.error, code=row.code, plan_first=row.plan_first)
        for fact in row.stderr:
            assert fact in r.err, (fact, r.err)
        for line in row.nexts:
            assert line in r.nexts, (line, r.nexts)
    if row.check is not None:
        row.check(child)


# ---------- PF11.7 the rollout never called, the network blocked ----------

MARKS = """\
import os
from pathlib import Path

Path(os.environ["PF11_MARKS"], "imported").touch()
"""
CALLED = """

def rollout(cfg, seed):
    Path(os.environ["PF11_MARKS"], "called").touch()
    raise RuntimeError("the rollout was called")
"""
#: Ways an import reaches for the network, and the ``host:port`` its refusal names.
REACHES = {
    "a connection by name": ('socket.create_connection(("api.example.com", 443), timeout=2)\n', "api.example.com:443"),
    "a raw connection to an address": ('_s = socket.socket()\n_s.settimeout(2)\n_s.connect(("203.0.113.7", 443))\n', "203.0.113.7:443"),
    "a name lookup alone": ('socket.getaddrinfo("api.example.com", 443)\n', "api.example.com:443"),
    "an attempt the import catches": ('try:\n    socket.create_connection(("api.example.com", 443), timeout=2)\nexcept OSError:\n    pass\n',
                                      "api.example.com:443"),
}
TWO_FOLDERS = "two checks in one process each read their own folder's wrapper"
PF11_7_CASES = ["the rollout is never called", *(f"{reach} is refused and never made" for reach in REACHES),
                "a loopback connection is allowed", "a real sweep imports without the block", TWO_FOLDERS]


@pytest.mark.parametrize("case", PF11_7_CASES)
def test_pf11_7_dry_run_never_calls_the_rollout_and_blocks_the_network_while_it_imports(case: str, tmp_path: Path, ready: int) -> None:
    repo = setup_with(Row(), tmp_path, ready)
    wrapper = repo / "prove_rollout.py"
    if case == "the rollout is never called":
        marks = tmp_path / "marks"
        marks.mkdir()
        wrapper.write_text(MARKS + CALLED, encoding="utf-8")
        child = run_child(repo, tmp_path, "sweep", "--dry-run", extra={"PF11_MARKS": str(marks)})
        assert child.code == 0, child.err
        assert (marks / "imported").exists(), "the check did not import the target"
        assert not (marks / "called").exists(), "the check called the rollout"
    elif case.endswith(" is refused and never made"):
        code, where = REACHES[case[: -len(" is refused and never made")]]
        wrapper.write_text(early(LIVE + code, wrapper.read_text(encoding="utf-8")), encoding="utf-8")
        child = run_child(repo, tmp_path, "sweep", "--dry-run")
        assert child.live, "the test's socket guard was not loaded where the target was imported"
        assert_refusal(child.result, where)
        assert child.result.nexts, child.err
        assert child.attempts == [], child.attempts
    elif case == "a loopback connection is allowed":
        with listening() as port:
            wrapper.write_text(early(CONNECT.format(host="127.0.0.1").replace("443", str(port)), wrapper.read_text(encoding="utf-8")), encoding="utf-8")
            child = run_child(repo, tmp_path, "sweep", "--dry-run")
        assert child.code == 0, child.err
        assert [a for a in child.attempts if a.startswith("connect loopback")], child.attempts
    elif case == "a real sweep imports without the block":
        wrapper.write_text(early(CONNECT.format(host="api.example.com"), wrapper.read_text(encoding="utf-8")), encoding="utf-8")
        child = run_child(repo, tmp_path, "sweep", "--yes", "--max-rollouts", "1")
        assert child.live, "the test's socket guard was not loaded where the target was imported"
        assert child.code != 0, child.out
        assert child.attempts, "a real sweep's import was blocked like the check's"
    else:
        other = setup_with(Row(), tmp_path / "other", ready)
        edit("prove_rollout.py", "def rollout(cfg: dict[str, Any], seed: int)", "def rollout(task: dict[str, Any], client: int)")(other)
        path, modules = list(sys.path), set(sys.modules)
        try:
            first = run(repo, "sweep", "--dry-run")
            second = run(other, "sweep", "--dry-run")
            assert first.code == 0, first
            assert_refusal(second, "(task, client)")
            assert sys.path == path, sorted(set(sys.path) ^ set(path))
        finally:
            for name in set(sys.modules) - modules:
                if name == "prove_rollout" or name.split(".")[0] == "support_agent":
                    sys.modules.pop(name, None)
            sys.path[:] = path


@contextmanager
def listening() -> Iterator[int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    stop = threading.Event()

    def accept() -> None:
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
                conn.close()
            except OSError:
                pass

    thread = threading.Thread(target=accept, daemon=True)
    thread.start()
    try:
        yield server.getsockname()[1]
    finally:
        stop.set()
        thread.join(2)
        server.close()


# ---------- PF11.8 the locations in the docs ----------


def test_pf11_8_the_docs_name_the_agents_each_location_was_verified_for() -> None:
    assert DOCS_PAGE.is_file(), DOCS_PAGE
    rows = [line for line in DOCS_PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")]
    for folder, agents in LOCATIONS.items():
        mine = [r for r in rows if re.search(rf"`{re.escape(folder)}[^`]*`", r.split("|")[1])]
        assert len(mine) == 1, (folder, rows)
        named = {agent for agent in AGENTS if re.search(rf"\b{agent}\b", mine[0])}
        assert named == set(agents), (folder, named, agents)
    assert {f"{Path(folder).parent}/" for folder in FOLDERS} == set(LOCATIONS)
    assert all(agent in PROVENANCE for agents in LOCATIONS.values() for agent in agents)


# ---------- carried: init --agent gets what every verb gets ----------

CARRIED = ["help names the options and their defaults", "--json", "--agent with --example", "--agent with --target",
           "--agent with --out", "--repo without --agent", "--print without --agent", "--print with --json",
           "--repo that is a file", "--repo that does not exist"]


@pytest.mark.parametrize("case", CARRIED)
def test_pf11_carried_init_agent_gets_what_every_verb_gets(case: str, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = Path(os.environ["HOME"])
    before = snapshot(tmp_path, home)
    if case == "help names the options and their defaults":
        r = run(repo, "init", "--help")
        assert r.code == 0, r
        for option in ("--agent", "--repo", "--print", "--force"):
            assert re.search(rf"(?<![\w-]){option}(?![\w-])", r.out), option
        lines = r.out.splitlines()
        at = next(i for i, line in enumerate(lines) if line.strip().startswith("--repo"))
        block = [lines[at]] + [line for line in lines[at + 1:at + 4] if line.startswith(" " * 8) and not line.strip().startswith("-")]
        assert "default" in " ".join(block), block
        assert re.search(r"init --agent", r.out), r.out
        return
    if case == "--json":
        r = run(repo, "init", "--agent", "--json")
        assert r.code == 0, r
        doc = json.loads(r.out)
        assert list(doc)[:3] == ["schema", "verdict", "sentence"] and doc["schema"] == "poisson-prove.init/1", doc
        assert doc["verdict"] == "ok" and doc["prompt"] == PROMPT, doc
        assert sorted((repo / w).resolve() for w in doc["wrote"]) == sorted((repo / f).resolve() for f in FOUR), doc
        assert list(doc)[-1] == "next", doc
        return
    if case.startswith("--repo that"):
        target = tmp_path / ("a-file.txt" if "file" in case else "nowhere")
        if "file" in case:
            target.write_text("not a folder\n", encoding="utf-8")
        before = snapshot(tmp_path, home)
        r = run(repo, "init", "--agent", "--repo", str(target))
        assert_refusal(r, str(target))
        assert snapshot(tmp_path, home) == before
        return
    argv = {
        "--agent with --example": ["--agent", "--example"],
        "--agent with --target": ["--agent", "--target", "my_agent:rollout"],
        "--agent with --out": ["--agent", "--out", "spec.toml"],
        "--repo without --agent": ["--repo", str(repo)],
        "--print without --agent": ["--print"],
        "--print with --json": ["--agent", "--print", "--json"],
    }[case]
    r = run(repo, "init", *argv)
    assert r.code == 2 and r.out == "", r
    assert snapshot(tmp_path, home) == before
