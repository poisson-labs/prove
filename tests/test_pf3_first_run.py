"""PF3, ``init`` and the first run: the frozen tests.

Written from the invariants PF3.1 to PF3.8 (PF3.6b included), with the choices they leave
settled (among them: the paired test as the default when the runs share a salt, an ``init`` that
asks nothing, and a packaged example that runs 194 replicates), and two carried behaviours: the
bare ``sweep --resume`` that PF1's ``next:`` line names, and a resume command that does not carry
the spec.

What PF3 promises, in one line: a new user gets from install to a first proved comparison with
no key and no id pasted. ``init`` writes ``prove.toml``; ``sweep`` reads it and its ``target``;
every ``next:`` line on the way is a whole command; and the comparison of two runs paired at
sweep time uses the paired test unless told otherwise, saying which test it used everywhere.

**Readings, named here** (lettered for reference).

- (a) PF3.4's "with the counts" is read as the verdict word and the shape of the
  result, not the counts: each sweep draws a fresh salt, so the counts move from run to run.
  ``trade`` first, the paired test named, a ``trade`` detail line, the runs by name.
- (b) The ``next:`` lines of the first run are pinned as the first run prints them: after
  ``init --example``, ``poisson-prove sweep``; after a sweep of the packaged mock agent's
  ``rollout``, the sweep of ``rollout_patched`` paired with ``latest``; after a paired sweep,
  ``poisson-prove diff``. After ``init --target T``, ``poisson-prove sweep``; after
  ``init --example --out PATH``, ``poisson-prove sweep PATH``. A sweep of any other target, and
  the bare ``init``, are not pinned here.
- (c) The plan "says which was used" is read as: the plan names the target it used (the flag's
  when given, else the spec's) and not the other one, in its text and in ``--json``'s
  ``plan.target``. With neither, the exit-2 refusal's error line names ``--target``, the key
  ``target`` and the spec file it read.
- (d) With no spec given and no ``./prove.toml``, ``sweep`` refuses (exit 1) with
  ``poisson-prove init`` among its ``next:`` lines; the ``init --agent`` line PF11 adds
  there is neither required nor forbidden here.
- (e) A ``stopped`` sweep's ``next:`` line is a command that resumes it as typed: bare
  ``poisson-prove sweep --resume`` when the spec was ``./prove.toml`` and the target the spec's,
  otherwise carrying the spec (before ``--resume``) and the ``--target`` that was typed.
- (f) Strict specs: ``[modal.NAME]`` tables are image sections (``--image NAME`` picks one), so a
  table under ``[modal]`` is known and its keys are checked; ``[[scenarios]]`` entries are
  configs and hold any key. Every other table and key is checked against the spec's own set,
  whatever the backend, and the nearest known key is the closest spelling.
- (g) PF3.5's ``[declare]`` failures ``timeout`` and ``violated`` are in the packaged file, so
  ``sweep`` reads ``failures`` (and ``successes``) in ``[declare]``, recorded as PF4.20 records
  them; what they change in the words is PF4's.
- (h) The method's JSON keeps ``method`` as the method's name (the JSON keeps its other keys)
  and adds ``method_chosen`` (``"default"`` or ``"named"``) right after it; ``serve --json``, the
  page structure, gains both at its top level, right after ``sentence``. ``diff --methods all
  --json`` keeps its shape (one object per method) and is not pinned here.
- (i) "Names the method" is read as: the verdict line carries the method's plain words
  (``shared seeds``, ``separate samples``, ``time to the event``); the ``method`` detail line,
  the report's header (``report.md`` before its first ``##``), the receipt's header and the
  page's first block (what the body shows before the first ``<h2>``) and the page's Summary each
  have one line (one block) carrying the method's own name (McNemar, Fisher, log-rank) and
  ``default`` or ``named``.
- (p) On those files the method's words stand on a line of their own (in ``report.md`` a
  paragraph: the line and a blank line after it), so taking them out leaves the rest of the file
  as it was: the pinned digests are taken over ``conftest.without_method_lines``.
- (j) The pairing ``note:`` is a stderr line beginning ``note:`` that mentions seeds; other
  notes may come and go.
- (k) ``--fix KEY=VALUE`` on a categorical axis matches VALUE against the axis's values as
  text, so ``--fix level=7`` picks the value ``"7"``; on a continuous axis it is a number,
  so ``0.550`` is ``0.55``. A value the axis does not hold is refused, exit 1, the error line
  listing the axis's values.
- (l) The power gate's offer is the refusal's ``next:`` line that carries ``--replicates`` (and
  not ``--max-mde``); PF1's ``--max-mde`` offer may stand beside it, before or after. The command
  typed carries ``--yes``, so the gate is the refusal.
- (m) The bare template ``init`` writes holds ``target`` as a commented line and is a strict
  spec: with a ``--target`` (and ``--replicates 50``) it plans.
- (q) ``init`` gets what every verb gets: help naming each option and an
  example, ``--json`` (``poisson-prove.init/1``, ``next`` last), abbreviations refused, the tool's
  own options after the verb, ``python -m`` the same; and it asks nothing (stderr empty).
- (r) The manifest records the target run as ``environment.import_path`` and the
  replicates run as ``environment.sweep.replicates`` (the spec's record, which ``--replicates``
  overrides).

**Seams with other modules.** ``init --agent`` and ``--print`` are PF11's: not
tested here, and the refusal without a spec leaves room for its ``next:`` line (d). The
``target`` and ``outcomes`` plan lines with "(imports, takes cfg and seed)" are PF11's; this
file asks only that the plan name the target used (c). Opening the terminal app is PF6's.
``compare``'s result objects naming the method are PF5.4's. That the power gate accepts 194
and refuses 193 is PF4.30's; PF3.8 is checked by running the offered command, so it does not
depend on the gate's arithmetic. ``diff``'s verdict word is PF4's rule; PF3.4 reads ``trade``.

**Suite.** The code suite. PF3.4 and PF3.5 each have one case marked ``slow`` (the wheel built
and installed into a fresh environment with ``uv``, which needs ``uv`` and the dependencies in
its cache or the network for the install; the five commands themselves run offline); every other
case is fast. The module fixtures sweep the keyless mock agent at small sizes.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF3.1 ``init`` writes one file; refuses an existing one; ``--example``, ``--target``, ``--out`` | ``test_pf3_1_*`` |
| PF3.2 ``sweep`` reads ``./prove.toml`` and its ``target``; neither is exit 2 | ``test_pf3_2_*`` |
| PF3.3 an unknown key or table is refused with the file, the line and the nearest key | ``test_pf3_3_*`` |
| PF3.4 the five commands from a fresh install, keyless, offline | ``test_pf3_4_*`` |
| PF3.5 the packaged quickstart, written byte for byte, the one copy | ``test_pf3_5_*`` |
| PF3.6 the paired default and the pairing note | ``test_pf3_6_*`` |
| PF3.6b every surface names the method and how it was chosen | ``test_pf3_6b_*`` |
| PF3.7 ``--fix`` by the axis's type | ``test_pf3_7_*`` |
| PF3.8 ``--replicates``; the gate's ``next:`` names the smallest that passes | ``test_pf3_8_*`` |
| carried: the bare ``sweep --resume`` and the ``stopped`` line's command; ``init`` gets what every verb gets | ``test_pf3_carried_*`` |
"""

from __future__ import annotations

import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
import urllib.request
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from conftest import blas_thread_cap

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGED = SRC / "poisson_prove" / "examples" / "quickstart.toml"
PACKAGED_IN_WHEEL = "poisson_prove/examples/quickstart.toml"
COMMAND = "poisson-prove"
MOCK = "poisson_prove.examples.mock_agent"
ROLLOUT = f"{MOCK}:rollout"
PATCHED = f"{MOCK}:rollout_patched"
LOOSE = ("--max-mde", "0.99")
FIRST_LINE = re.compile(r"^([a-z][a-z ]*?)  \S")
RUN_ID = re.compile(r"\b\d{8}T\d{6}Z-[0-9a-f]{4}\b")
DAY = r"mock-agent \d{4}-\d{2}-\d{2}"

#: The keyless mock agent, small: 2 x 2 conditions x 50 replicates, its target in the spec.
SPEC = f"""\
target = "{ROLLOUT}"
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = 50

[axes.task_id]
type = "categorical"
values = ["search", "refund"]

[axes.tool_fail_rate]
type = "continuous"
values = [0.3, 0.55]
"""
NO_TARGET_SPEC = SPEC.split("\n", 1)[1]

#: Each method's plain words, and its own name kept beside them.
PLAIN = {"mcnemar_bh": "shared seeds", "fisher_bh": "separate samples", "logrank_bh": "time to the event"}
OWN_NAME = {"mcnemar_bh": "mcnemar", "fisher_bh": "fisher", "logrank_bh": "log-rank"}


# ---------- the command line ----------


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
    """``poisson-prove ARGV`` in this process, in ``cwd``, stdin not a terminal."""
    from poisson_prove import cli as module

    out, err = StringIO(), StringIO()
    with inside(cwd):
        code = module.main([str(a) for a in argv], stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def closing_word(text: str) -> str:
    """A sweep's verdict: the last line of its stdout that is a verdict line (the plan's comes
    first)."""
    words = [m.group(1) for m in (FIRST_LINE.match(line) for line in text.splitlines()) if m]
    assert words, f"no verdict line: {text[:300]!r}"
    return words[-1]


def plan_of(text: str) -> str:
    """A sweep's plan block: its stdout up to the next verdict line."""
    lines = text.splitlines()
    assert lines and lines[0].startswith("plan  "), text[:300]
    end = next((i for i, line in enumerate(lines[1:], 1) if FIRST_LINE.match(line)), len(lines))
    return "\n".join(lines[:end])


def first_word(text: str) -> str:
    first = text.splitlines()[0] if text else ""
    m = FIRST_LINE.match(first)
    assert m, f"no verdict line first: {text[:300]!r}"
    return m.group(1)


def strict_json(text: str) -> Any:
    def refuse(token: str) -> Any:
        raise ValueError(f"not strict JSON: {token}")

    return json.loads(text, parse_constant=refuse)


def assert_refusal(r: Result, *facts: str, code: int = 1) -> None:
    """PF1.2's assertions: the exit code, one ``error:`` line then only ``next:`` lines, nothing
    on stdout; and the facts, read from the ``error:`` line."""
    assert r.code == code, r
    assert r.out == "", r.out
    lines = [line for line in r.err.splitlines() if not line.startswith("note: ")]
    assert lines and lines[0].startswith("error: "), r.err
    assert all(line.startswith("  next: ") for line in lines[1:]), r.err
    for fact in facts:
        assert fact in lines[0], (fact, r.err)


def listing(*roots: Path) -> list[str]:
    return sorted(f"{root.name}/{p.relative_to(root)}" for root in roots if root.exists() for p in root.rglob("*"))


def runs_of(store: Path) -> list[dict[str, Any]]:
    r = run(store.parent, "--store", store, "runs", "--json")
    assert r.code == 0, r.err
    return list(strict_json(r.out)["runs"])


def manifest_of(store: Path, run_id: str) -> dict[str, Any]:
    return json.loads((store / run_id / "manifest.json").read_text(encoding="utf-8"))


def without_option(tokens: list[str], option: str) -> list[str]:
    out, skip = [], False
    for token in tokens:
        if skip:
            skip = False
        elif token == option:
            skip = True
        elif not token.startswith(option + "="):
            out.append(token)
    return out


def visible(markup: str) -> str:
    markup = re.sub(r"<(style|script)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", markup)).split())


def block_lines(markup: str) -> list[str]:
    """The visible text of an HTML fragment, one block element to a line."""
    markup = re.sub(r"<(style|script|head)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    markup = re.sub(r"</?(?:p|li|tr|div|br|h\d|section|header|footer|table|ul|ol|dl|dt|dd|pre|caption|summary|details|figcaption)\b[^>]*>", "\n", markup, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def before_first_h2(markup: str) -> list[str]:
    """(i): a page's first block is what its body shows before its first ``<h2>``; ``<head>``
    (the ``<title>``) is not on the page."""
    at = re.search(r"<h2\b", markup, flags=re.I)
    return block_lines(markup[: at.start()] if at else markup)


def h2_section(markup: str, heading: str) -> list[str]:
    at = re.search(rf"<h2\b[^>]*>\s*{re.escape(heading)}\s*</h2>", markup, flags=re.I)
    assert at, f"no {heading} section"
    rest = markup[at.end():]
    end = re.search(r"<h2\b", rest, flags=re.I)
    return block_lines(rest[: end.start()] if end else rest)


# ---------- child processes ----------

SOCKET_GUARD = '''\
import os, socket

_LOG = os.environ["PF3_SOCKET_LOG"]
_LOOPBACK = ("127.", "::1", "localhost")


def _allowed(sock, address):
    if sock.family == getattr(socket, "AF_UNIX", None):
        return True
    host = address[0] if isinstance(address, tuple) else str(address)
    return str(host).startswith(_LOOPBACK)


_getaddrinfo = socket.getaddrinfo


def getaddrinfo(host, *args, **kwargs):
    if host is not None and not str(host).startswith(_LOOPBACK):
        _refuse((host,) + args[:1])
    return _getaddrinfo(host, *args, **kwargs)


def _refuse(address):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(repr(address) + "\\n")
    raise OSError("the network is blocked in this test: " + repr(address))


_connect, _connect_ex = socket.socket.connect, socket.socket.connect_ex


def connect(self, address):
    if not _allowed(self, address):
        _refuse(address)
    return _connect(self, address)


def connect_ex(self, address):
    if not _allowed(self, address):
        _refuse(address)
    return _connect_ex(self, address)


socket.socket.connect, socket.socket.connect_ex = connect, connect_ex
socket.getaddrinfo = getaddrinfo
'''


def guarded_env(home: Path, guard: Path, *, bindir: Path, src: Path | None) -> dict[str, str]:
    """An environment built from nothing: no key, no store variable, ``HOME`` empty, the socket
    guard first on the path, and the checkout's ``src`` only when the install is the checkout."""
    guard.mkdir(parents=True, exist_ok=True)
    (guard / "sitecustomize.py").write_text(SOCKET_GUARD, encoding="utf-8")
    paths = [str(guard)] + ([str(src)] if src is not None else [])
    return {
        "PATH": f"{bindir}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(home),
        "PYTHONPATH": os.pathsep.join(paths),
        "PF3_SOCKET_LOG": str(guard / "attempts.log"),
        "PYTHONIOENCODING": "utf-8",
        "LANG": "C.UTF-8",
        "TMPDIR": str(home),
        **blas_thread_cap(),
    }


def child(command: Path, cwd: Path, env: dict[str, str], *argv: str, timeout: float = 300) -> Result:
    done = subprocess.run([str(command), *argv], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=timeout)
    return Result(done.returncode, done.stdout, done.stderr)


@dataclass(frozen=True)
class Install:
    command: Path
    src: Path | None
    wheel: Path | None


def checkout_install() -> Install:
    command = Path(sys.executable).parent / COMMAND
    assert command.is_file(), f"the checkout's environment has no {COMMAND} command: {command}"
    return Install(command, SRC, None)


@pytest.fixture(scope="module")
def wheel_install(tmp_path_factory: pytest.TempPathFactory) -> Install:
    """The wheel built from this checkout, installed with its dependencies into a fresh
    environment of its own; ``pip install poisson-prove`` as a stranger runs it."""
    uv = shutil.which("uv")
    assert uv is not None, "the wheel is built and installed with uv"
    base = tmp_path_factory.mktemp("wheel")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env.update(UV_PYTHON_PREFERENCE="only-system", UV_PYTHON_DOWNLOADS="never")
    built = subprocess.run([uv, "build", "--wheel", "--out-dir", str(base / "dist"), str(ROOT)], env=env, capture_output=True, text=True, timeout=600)
    assert built.returncode == 0, built.stderr
    (wheel,) = (base / "dist").glob("*.whl")
    venv = base / "venv"
    made = subprocess.run([uv, "venv", "--python", sys.executable, str(venv)], env=env, capture_output=True, text=True, timeout=300)
    assert made.returncode == 0, made.stderr
    put = subprocess.run([uv, "pip", "install", "--python", str(venv / "bin" / "python"), str(wheel)], env=env, capture_output=True, text=True, timeout=900)
    assert put.returncode == 0, put.stderr
    return Install(venv / "bin" / COMMAND, None, wheel)


def install_for(kind: str, request: pytest.FixtureRequest) -> Install:
    return checkout_install() if kind == "checkout" else request.getfixturevalue("wheel_install")


INSTALLS = ["checkout", pytest.param("wheel", marks=pytest.mark.slow)]


# ---------- PF3.1 init ----------


INIT_CASES = {
    "bare": ([], "cwd/prove.toml", False),
    "example": (["--example"], "cwd/prove.toml", False),
    "target": (["--target", ROLLOUT], "cwd/prove.toml", False),
    "out": (["--example", "--out", "{elsewhere}/mine.toml"], "elsewhere/mine.toml", False),
    "existing, bare": ([], "cwd/prove.toml", True),
    "existing, example": (["--example"], "cwd/prove.toml", True),
    "existing, out": (["--out", "{elsewhere}/mine.toml"], "elsewhere/mine.toml", True),
}


@pytest.mark.parametrize("case", list(INIT_CASES))
def test_pf3_1_init_writes_one_spec_file_and_nothing_else_and_refuses_an_existing_one(case: str, tmp_path: Path) -> None:
    flags, written, existing = INIT_CASES[case]
    cwd, elsewhere, home = tmp_path / "cwd", tmp_path / "elsewhere", Path(os.environ["HOME"])
    cwd.mkdir()
    elsewhere.mkdir()
    argv = [f.format(elsewhere=elsewhere) for f in flags]
    target = tmp_path / written
    if existing:
        target.write_text("# mine\n", encoding="utf-8")
    before = listing(cwd, elsewhere, home)

    r = run(cwd, "init", *argv)
    if existing:
        assert_refusal(r, target.name)
        assert any("--force" in n for n in r.nexts), r.nexts
        assert target.read_text(encoding="utf-8") == "# mine\n"
        assert listing(cwd, elsewhere, home) == before
        forced = run(cwd, "init", *argv, "--force")
        assert forced.code == 0, forced.err
        assert target.read_text(encoding="utf-8") != "# mine\n"
        assert listing(cwd, elsewhere, home) == before
        return

    assert r.code == 0, r.err
    assert r.err == "", r.err  # init asks nothing
    assert first_word(r.out) == "ok"
    assert target.name in r.out.splitlines()[0], r.out
    assert listing(cwd, elsewhere, home) == sorted([*before, f"{target.parent.name}/{target.name}"])
    doc = tomllib.loads(target.read_text(encoding="utf-8"))
    assert doc.get("axes"), doc
    if case == "bare":
        assert "target" not in doc, doc
        assert re.search(r"(?m)^#\s*target\s*=", target.read_text(encoding="utf-8")), "no commented target placeholder"
        assert "target" in r.out.splitlines()[0], r.out
    if case == "target":
        assert doc["target"] == ROLLOUT
    if "--example" in argv:
        assert target.read_bytes() == PACKAGED.read_bytes()
    if case in ("example", "target"):
        assert r.nexts == [f"{COMMAND} sweep"], r.nexts
    if case == "out":
        assert [shlex.split(n) for n in r.nexts] == [[COMMAND, "sweep", str(target)]], r.nexts
    # (m): the file is a strict spec, and with a target it plans.
    planned = run(cwd, "sweep", target, "--target", ROLLOUT, "--replicates", "50", "--dry-run", *LOOSE)
    assert planned.code == 0, planned.err
    assert first_word(planned.out) == "plan"


@pytest.mark.parametrize("case", ["--help", "--json", "an abbreviation", "a global option after the verb", "python -m"])
def test_pf3_carried_init_gets_what_every_verb_gets(case: str, tmp_path: Path) -> None:
    """What every verb gets, for the verb PF3 adds: help with every option's default and an example,
    the JSON envelope, abbreviations refused, the tool's own options after the verb, and
    ``python -m`` the same as the command."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    if case == "--help":
        r = run(cwd, "init", "--help")
        assert r.code == 0 and r.err == "", r.err
        for option in ("--example", "--target", "--out", "--force", "--json"):
            assert option in r.out, option
        assert "default" in r.out and f"{COMMAND} init --example" in r.out, r.out
        assert not (cwd / "prove.toml").exists()
    elif case == "--json":
        r = run(cwd, "init", "--example", "--json")
        assert r.code == 0, r.err
        doc = strict_json(r.out)
        assert list(doc)[:3] == ["schema", "verdict", "sentence"] and list(doc)[-1] == "next", list(doc)
        assert (doc["schema"], doc["verdict"]) == (f"{COMMAND}.init/1", "ok"), doc
        assert doc["next"] == [f"{COMMAND} sweep"], doc
        assert (cwd / "prove.toml").read_bytes() == PACKAGED.read_bytes()
    elif case == "an abbreviation":
        r = run(cwd, "init", "--exam")
        assert_refusal(r, code=2)
        assert not (cwd / "prove.toml").exists()
    elif case == "a global option after the verb":
        r = run(cwd, "init", "--example", "--plain")
        assert r.code == 0, r.err
        assert (cwd / "prove.toml").is_file()
    else:
        home = Path(os.environ["HOME"])
        env = {**child_env_for(home)}
        (cwd / "a").mkdir()
        (cwd / "b").mkdir()
        by_module = subprocess.run([sys.executable, "-m", "poisson_prove", "init", "--example"], cwd=cwd / "a", env=env, capture_output=True, text=True, timeout=120)
        by_command = subprocess.run([str(Path(sys.executable).parent / COMMAND), "init", "--example"], cwd=cwd / "b", env=env, capture_output=True, text=True, timeout=120)
        assert (by_module.returncode, by_module.stdout, by_module.stderr) == (by_command.returncode, by_command.stdout, by_command.stderr)
        assert by_module.returncode == 0, by_module.stderr


# ---------- PF3.2 the default spec and its target ----------


def import_path_of(store: Path) -> str:
    (entry,) = runs_of(store)
    return str(manifest_of(store, entry["run_id"])["environment"]["import_path"])


SWEEP_CASES = ["the spec's target", "the flag wins", "a spec given, its target", "neither", "no spec here"]


@pytest.mark.parametrize("case", SWEEP_CASES)
def test_pf3_2_sweep_reads_prove_toml_and_its_target_and_with_neither_names_both_ways(case: str, tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    store = cwd / "prove-runs"
    if case == "the spec's target":
        (cwd / "prove.toml").write_text(SPEC, encoding="utf-8")
        plan = run(cwd, "sweep", "--dry-run", "--json", *LOOSE)
        assert plan.code == 0, plan.err
        assert strict_json(plan.out)["plan"]["target"] == ROLLOUT
        r = run(cwd, "sweep", "--yes", *LOOSE)
        assert r.code == 0, r.err
        assert import_path_of(store) == ROLLOUT
        assert ROLLOUT in plan_of(r.out) and PATCHED not in plan_of(r.out), r.out
    elif case == "the flag wins":
        (cwd / "prove.toml").write_text(SPEC, encoding="utf-8")
        plan = run(cwd, "sweep", "--target", PATCHED, "--dry-run", "--json", *LOOSE)
        assert plan.code == 0, plan.err
        assert strict_json(plan.out)["plan"]["target"] == PATCHED
        r = run(cwd, "sweep", "--target", PATCHED, "--yes", *LOOSE)
        assert r.code == 0, r.err
        assert import_path_of(store) == PATCHED
        assert PATCHED in plan_of(r.out) and not re.search(rf"{re.escape(ROLLOUT)}(?!_patched)", plan_of(r.out)), r.out
    elif case == "a spec given, its target":
        other = tmp_path / "other"
        other.mkdir()
        (other / "spec.toml").write_text(SPEC, encoding="utf-8")
        # A ./prove.toml naming the other target is there too: the spec typed is the one read.
        (cwd / "prove.toml").write_text(SPEC.replace(f'target = "{ROLLOUT}"', f'target = "{PATCHED}"'), encoding="utf-8")
        r = run(cwd, "sweep", other / "spec.toml", "--yes", *LOOSE)
        assert r.code == 0, r.err
        assert import_path_of(store) == ROLLOUT
    elif case == "neither":
        (cwd / "prove.toml").write_text(NO_TARGET_SPEC, encoding="utf-8")
        r = run(cwd, "sweep", "--yes", *LOOSE)
        # Both ways on the error line: the flag, and the key in the spec file it read.
        assert_refusal(r, "--target", "prove.toml", code=2)
        assert re.search(r"(?<![-\w])target(?![-\w])", r.error.replace("--target", "")), r.error
        assert not store.exists()
    else:
        r = run(cwd, "sweep", "--yes", *LOOSE)
        assert_refusal(r)
        assert f"{COMMAND} init" in r.nexts, r.nexts
        assert not store.exists()


# ---------- carried: the bare sweep --resume ----------


@pytest.mark.parametrize("given", ["prove.toml", "a spec elsewhere and --target"])
def test_pf3_carried_a_stopped_sweep_resumes_with_the_command_its_next_line_gives(given: str, tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    store = cwd / "prove-runs"
    if given == "prove.toml":
        (cwd / "prove.toml").write_text(SPEC, encoding="utf-8")
        typed: list[str] = []
    else:
        (tmp_path / "other").mkdir()
        spec = tmp_path / "other" / "spec.toml"
        spec.write_text(NO_TARGET_SPEC, encoding="utf-8")
        typed = [str(spec), "--target", ROLLOUT]
    stopped = run(cwd, "sweep", *typed, "--max-rollouts", "30", "--yes", *LOOSE)
    assert stopped.code == 3, stopped.err
    assert closing_word(stopped.out) == "stopped"
    (command,) = [n for n in stopped.nexts if "--resume" in n]
    assert not RUN_ID.search(command), command
    if given == "prove.toml":
        assert command == f"{COMMAND} sweep --resume"
    tokens = shlex.split(command)
    assert tokens[:2] == [COMMAND, "sweep"], command
    (partial,) = runs_of(store)

    resumed = run(cwd, *tokens[1:], "--yes")
    assert resumed.code == 0, resumed.err
    assert closing_word(resumed.out) == "done"
    (entry,) = runs_of(store)
    assert entry["run_id"] == partial["run_id"] and entry["status"] == "complete", entry
    assert entry["rows"] == 4 * 50, entry


# ---------- PF3.3 strict specs ----------

#: (the text added to SPEC, the word that is misspelt in it, the nearest known key, a known key
#: of the same table that is not the nearest); a text that starts with a key goes after the
#: comment lines that open the file and before the first table, so the key is a top-level one
#: on a line whose number has two digits.
OPENING = "".join(f"# line {i}\n" for i in range(1, 10))
STRICT_CASES = {
    "a top-level key": ('replicate = 5\n', "replicate", "replicates", "scenarios"),
    "the target key": ('targt = "x:y"\n', "targt", "target", "scenarios"),
    "a top-level table": ('\n[declair]\noutcomes = ["violated"]\n', "[declair]", "declare", "scenarios"),
    "a key in an axis": None,  # built below: a key inside [axes.task_id]
    "a key in [capture]": ('\n[capture]\ninstrumnt = "record"\n', "instrumnt", "instrument", "max_spans"),
    "a key in [chaos]": ('\n[chaos]\nfualt = "x"\n', "fualt", "fault", "steps"),
    "a key in [declare]": ('\n[declare]\noutcome = ["violated"]\n', "outcome", "outcomes", "gates"),
    "a key in [modal]": ('\n[modal]\nconcurency = 4\n', "concurency", "concurrency", "est_seconds_per_episode"),
    "a key in a [modal] image table": ('\n[modal.image]\npyhton = "3.11"\n', "pyhton", "python", "dockerfile"),
    "a key in [burla]": ('\n[burla]\nnodez = 2\n', "nodez", "nodes", "head_url"),
}


@pytest.mark.parametrize("case", list(STRICT_CASES))
def test_pf3_3_an_unknown_key_or_table_is_refused_naming_the_file_the_line_and_the_nearest_key(case: str, tmp_path: Path) -> None:
    if case == "a key in an axis":
        text, word, nearest, other = OPENING + SPEC.replace('type = "categorical"\n', 'type = "categorical"\nvalus = 1\n', 1), "valus", "values", "type"
    else:
        added, word, nearest, other = STRICT_CASES[case]
        text = OPENING + (added + SPEC if not added.startswith("\n") else SPEC + added)
    line = next(i for i, row in enumerate(text.splitlines(), 1) if row.strip() == word or row.split("=")[0].strip() == word)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "spec.toml").write_text(text, encoding="utf-8")
    r = run(cwd, "sweep", "spec.toml", "--yes", *LOOSE)
    assert_refusal(r, "spec.toml", nearest)
    after_file = r.error.split("spec.toml", 1)[1]
    assert re.search(rf"(?<![\d.]){line}(?![\d.])", after_file), (line, r.error)
    assert other not in r.error, (other, r.error)
    assert not (cwd / "prove-runs").exists()


# ---------- PF3.4 the five commands ----------


@pytest.mark.parametrize("install", INSTALLS)
def test_pf3_4_the_five_commands_run_from_a_fresh_install_with_no_key_and_no_network(install: str, request: pytest.FixtureRequest, tmp_path: Path) -> None:
    got = install_for(install, request)
    home, cwd = tmp_path / "home", tmp_path / "cwd"
    home.mkdir()
    cwd.mkdir()
    env = guarded_env(home, tmp_path / "guard", bindir=got.command.parent, src=got.src)
    attempts = tmp_path / "guard" / "attempts.log"
    # The guard's control: in this environment a connection out is refused and logged.
    probe = subprocess.run([str(got.command.parent / "python"), "-c", "import socket; socket.create_connection(('192.0.2.1', 9), timeout=1)"],
                           cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
    assert probe.returncode != 0 and attempts.is_file(), (probe.returncode, probe.stderr[-400:])
    attempts.unlink()

    init = child(got.command, cwd, env, "init", "--example")
    assert init.code == 0, init.err
    assert init.nexts == [f"{COMMAND} sweep"], init.nexts

    first = child(got.command, cwd, env, "sweep", "--yes")
    second = child(got.command, cwd, env, "sweep", "--target", PATCHED, "--pair-with", "latest", "--yes")
    assert first.code == 0, first.err
    assert closing_word(first.out) == "done"
    assert first.nexts == [f"{COMMAND} sweep --target {PATCHED} --pair-with latest"], first.nexts
    assert second.code == 0, second.err
    assert closing_word(second.out) == "done"
    assert second.nexts == [f"{COMMAND} diff"], second.nexts

    diff = child(got.command, cwd, env, "diff")
    assert diff.code == 0, diff.err
    lines = diff.out.splitlines()
    assert first_word(diff.out) == "trade", diff.out[:400]
    assert PLAIN["mcnemar_bh"] in lines[0].lower(), lines[0]
    details = {m.group(1): m.group(2) for m in (re.match(r"^  (method|before|after)  (.*)$", x) for x in lines) if m}
    assert OWN_NAME["mcnemar_bh"] in details["method"].lower(), details
    # A and B by name; across UTC midnight B is the next day's "a".
    assert re.fullmatch(rf"{DAY} a", details["before"]) and re.fullmatch(rf"{DAY} [ab]", details["after"]), details
    assert details["before"] != details["after"], details
    assert any(re.match(r"^  trade  \S", x) for x in lines), diff.out[:800]
    assert f"{COMMAND} report --x task_id --y tool_fail_rate" in diff.nexts, diff.nexts
    assert not attempts.exists(), attempts.read_text(encoding="utf-8")


# ---------- PF3.5 the packaged quickstart ----------


@pytest.mark.parametrize("source", ["package", pytest.param("wheel", marks=pytest.mark.slow)])
def test_pf3_5_the_packaged_quickstart_is_written_byte_for_byte_and_is_the_only_copy(source: str, request: pytest.FixtureRequest, tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    if source == "package":
        packaged = PACKAGED.read_bytes()
        r = run(cwd, "init", "--example")
    else:
        got: Install = request.getfixturevalue("wheel_install")
        assert got.wheel is not None
        with zipfile.ZipFile(got.wheel) as wheel:
            assert PACKAGED_IN_WHEEL in wheel.namelist()
            packaged = wheel.read(PACKAGED_IN_WHEEL)
        assert packaged == PACKAGED.read_bytes()
        home = tmp_path / "home"
        home.mkdir()
        r = child(got.command, cwd, guarded_env(home, tmp_path / "guard", bindir=got.command.parent, src=None), "init", "--example")
    assert r.code == 0, r.err
    assert (cwd / "prove.toml").read_bytes() == packaged

    doc = tomllib.loads(packaged.decode("utf-8"))
    assert doc["target"] == ROLLOUT
    assert doc["target_id"] == "mock-agent"
    assert doc["replicates"] == 194
    assert set(doc["declare"]["failures"]) == {"timeout", "violated"}
    assert list(doc["axes"]) == ["task_id", "tool_fail_rate"]
    assert len(doc["axes"]["task_id"]["values"]) * len(doc["axes"]["tool_fail_rate"]["values"]) == 9

    # Every file of the checkout outside its environments and work folders, git or not.
    skip = {".git", ".venv", ".work", "dist", "build", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache"}
    copies = []
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in skip and not d.endswith(".egg-info")]
        for name in files:
            path = Path(folder) / name
            if name.endswith("quickstart.toml") or (path.stat().st_size == len(packaged) and path.read_bytes() == packaged):
                copies.append(str(path.relative_to(ROOT)))
    assert sorted(copies) == ["src/poisson_prove/examples/quickstart.toml"], copies
    assert not (ROOT / "examples" / "quickstart.toml").exists()


# ---------- the runs PF3.6 to PF3.8 compare ----------


@dataclass(frozen=True)
class Runs:
    cwd: Path
    store: Path
    a: str
    b: str
    c: str
    home: Path


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> Runs:
    """Three runs of ``SPEC``: A; B, the patched agent paired with A at sweep time; C, the agent
    again on a salt of its own. (A, B) are paired, (C, B) are not. Named as they go by."""
    base = tmp_path_factory.mktemp("runs")
    cwd, home = base / "cwd", base / "home"
    cwd.mkdir()
    home.mkdir()
    (cwd / "prove.toml").write_text(SPEC, encoding="utf-8")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", str(home))
        mp.delenv("PROOFLOAD_STORE", raising=False)
        mp.delenv("POISSON_PROVE_STORE", raising=False)
        # The spec and the target are typed, so these runs do not lean on PF3.2.
        explicit = ["sweep", "prove.toml", "--target"]
        for argv in ([*explicit, ROLLOUT], [*explicit, PATCHED, "--pair-with", "latest"], [*explicit, ROLLOUT]):
            r = run(cwd, *argv, "--yes", *LOOSE)
            assert r.code == 0, r.err
        listed = sorted(runs_of(cwd / "prove-runs"), key=lambda e: e["created_at"])
    a, b, c = (e["run_name"] for e in listed)
    return Runs(cwd, cwd / "prove-runs", a, b, c, home)


#: (which pair, the --method typed or None, the method used, how it was chosen, a pairing note)
METHOD_CASES = {
    "paired, no --method": ("paired", None, "mcnemar_bh", "default", False),
    "paired, --method fisher_bh": ("paired", "fisher_bh", "fisher_bh", "named", True),
    "paired, --method logrank_bh": ("paired", "logrank_bh", "logrank_bh", "named", True),
    "paired, --method mcnemar_bh": ("paired", "mcnemar_bh", "mcnemar_bh", "named", False),
    "unpaired, no --method": ("unpaired", None, "fisher_bh", "default", False),
    "unpaired, --method fisher_bh": ("unpaired", "fisher_bh", "fisher_bh", "named", False),
    "unpaired, --method logrank_bh": ("unpaired", "logrank_bh", "logrank_bh", "named", False),
}
AXES = ("--x", "task_id", "--y", "tool_fail_rate")


def child_env_for(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PROOFLOAD_STORE", "POISSON_PROVE_STORE", "NO_COLOR", "CI")}
    env.update(PYTHONPATH=str(SRC), HOME=str(home), PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    return env


def served_page(r: Runs, argv: list[str]) -> str:
    proc = subprocess.Popen([sys.executable, "-m", "poisson_prove", "serve", *argv], cwd=r.cwd, env=child_env_for(r.home),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert proc.stdout is not None
        import selectors

        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        url = None
        while url is None:
            assert selector.select(timeout=120), "serve printed no address within 120 s"
            line = proc.stdout.readline()
            assert line, f"serve ended before its address: {proc.stderr.read() if proc.stderr else ''}"
            url = re.search(r"http://127\.0\.0\.1:\d+/", line)
        with urllib.request.urlopen(url.group(0), timeout=60) as response:
            return str(response.read().decode("utf-8"))
    finally:
        proc.terminate()
        proc.wait(timeout=60)


@cache
def _compared(cwd: str, home: str, a: str, b: str, method: str | None, out: str) -> dict[str, Any]:
    """Every surface of one comparison: the text and JSON of diff and check, report's JSON and
    files, serve's JSON and its served page. Cached per comparison for the two tests that read it."""
    r = Runs(Path(cwd), Path(cwd) / "prove-runs", a, b, "", Path(home))
    m = [] if method is None else ["--method", method]
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", home)
        got = {
            "diff": run(r.cwd, "diff", a, b, *m),
            "diff --json": run(r.cwd, "diff", a, b, *m, "--json"),
            "check": run(r.cwd, "check", a, b, "--event", "violated", "--fail-on", "any", *m),
            "check --json": run(r.cwd, "check", a, b, "--event", "violated", "--fail-on", "any", *m, "--json"),
            "report --json": run(r.cwd, "report", a, b, *AXES, "--out", out, *m, "--json"),
            "serve --json": run(r.cwd, "serve", a, b, *AXES, "--event", "violated", *m, "--json"),
        }
    for label, result in got.items():
        assert result.code in (0, 4), (label, result.err)
    page = served_page(r, [a, b, *AXES, "--event", "violated", *m])
    return {**got, "page": page, "report.md": (Path(out) / "report.md").read_text(encoding="utf-8"),
            "receipt.html": (Path(out) / "receipt.html").read_text(encoding="utf-8")}


def compared(r: Runs, case: str) -> dict[str, Any]:
    pair, method, *_ = METHOD_CASES[case]
    a, b = (r.a, r.b) if pair == "paired" else (r.c, r.b)
    out = r.cwd.parent / ("report-" + re.sub(r"\W+", "-", case))
    return _compared(str(r.cwd), str(r.home), a, b, method, str(out))


def pairing_notes(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("note:") and "seed" in line.lower()]


# ---------- PF3.6 the paired default ----------


@pytest.mark.parametrize("case", list(METHOD_CASES))
def test_pf3_6_runs_paired_at_sweep_time_default_to_the_paired_test_and_an_unpaired_method_named_on_them_is_noted(case: str, runs: Runs) -> None:
    _, _, used, _, noted = METHOD_CASES[case]
    got = compared(runs, case)
    for label in ("diff --json", "check --json", "report --json", "serve --json"):
        result = got[label]
        assert strict_json(result.out)["method"] == used, (label, case)
        assert bool(pairing_notes(result.err)) is noted, (label, case, result.err)
    assert bool(pairing_notes(got["diff"].err)) is noted, got["diff"].err


# ---------- PF3.6b every surface names the method ----------


@pytest.mark.parametrize("case", list(METHOD_CASES))
def test_pf3_6b_every_surface_names_the_method_it_used_and_whether_it_was_the_default_or_named(case: str, runs: Runs) -> None:
    _, _, used, chosen, _ = METHOD_CASES[case]
    got = compared(runs, case)
    plain, own = PLAIN[used], OWN_NAME[used]
    word = "default" if chosen == "default" else "named"

    for verb in ("diff", "check"):
        lines = got[verb].out.splitlines()
        assert plain in lines[0].lower(), (verb, lines[0])
        (method_line,) = [x for x in lines[1:4] if x.startswith("  method  ")]
        assert own in method_line.lower() and plain in method_line.lower() and word in method_line.lower(), (verb, method_line)
        doc = strict_json(got[f"{verb} --json"].out)
        assert (doc["method"], doc["method_chosen"]) == (used, chosen), (verb, doc.get("method_chosen"))
    for label in ("report --json", "serve --json"):
        doc = strict_json(got[label].out)
        assert (doc["method"], doc["method_chosen"]) == (used, chosen), (label, doc.get("method_chosen"))

    surfaces = {
        "report.md header": got["report.md"].split("\n## ", 1)[0].splitlines(),
        "receipt.html header": before_first_h2(got["receipt.html"]),
        "the page's first block": before_first_h2(got["page"]),
        "the page's Summary": h2_section(got["page"], "Summary"),
    }
    for label, lines in surfaces.items():
        # The method's own name and how it was chosen, on one line (one block).
        assert any(own in x.lower() and word in x.lower() for x in lines), (label, case, lines[:12])


# ---------- PF3.7 --fix by the axis's type ----------


@pytest.fixture(scope="module")
def digits(tmp_path_factory: pytest.TempPathFactory) -> Runs:
    """Two runs over a categorical axis whose values are digits as text."""
    base = tmp_path_factory.mktemp("digits")
    cwd, home = base / "cwd", base / "home"
    cwd.mkdir()
    home.mkdir()
    spec = SPEC.replace("replicates = 50", "replicates = 20").replace("[axes.task_id]", "[axes.level]").replace('["search", "refund"]', '["707", "818"]')
    (cwd / "prove.toml").write_text(spec, encoding="utf-8")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", str(home))
        mp.delenv("PROOFLOAD_STORE", raising=False)
        mp.delenv("POISSON_PROVE_STORE", raising=False)
        explicit = ["sweep", "prove.toml", "--target"]
        for argv in ([*explicit, ROLLOUT], [*explicit, PATCHED, "--pair-with", "latest"]):
            r = run(cwd, *argv, "--yes", *LOOSE)
            assert r.code == 0, r.err
        listed = sorted(runs_of(cwd / "prove-runs"), key=lambda e: e["created_at"])
    a, b = (e["run_name"] for e in listed)
    return Runs(cwd, cwd / "prove-runs", a, b, "", home)


#: (which runs, the --fix typed, the other axis for --x, the value pinned, or the values listed)
FIX_CASES = {
    "a category as typed": ("runs", "task_id=refund", "tool_fail_rate", "refund", None),
    "a number": ("runs", "tool_fail_rate=0.55", "task_id", 0.55, None),
    "a number spelt another way": ("runs", "tool_fail_rate=0.550", "task_id", 0.55, None),
    "a category of digits": ("digits", "level=707", "tool_fail_rate", "707", None),
    "a category not on the axis": ("runs", "task_id=refnd", "tool_fail_rate", None, ["search", "refund"]),
    "a number not on the axis": ("runs", "tool_fail_rate=0.5", "task_id", None, ["0.3", "0.55"]),
    "digits not on the axis": ("digits", "level=909", "tool_fail_rate", None, ["707", "818"]),
}


@pytest.mark.parametrize("verb", ["report", "serve"])
@pytest.mark.parametrize("case", list(FIX_CASES))
def test_pf3_7_fix_reads_its_value_by_the_axis_type_and_refuses_a_value_not_on_the_axis(case: str, verb: str, request: pytest.FixtureRequest, tmp_path: Path) -> None:
    which, fix, x, pinned, listed = FIX_CASES[case]
    r: Runs = request.getfixturevalue(which)
    key = fix.split("=", 1)[0]
    if verb == "report":
        got = run(r.cwd, "report", r.a, r.b, "--x", x, "--fix", fix, "--out", tmp_path / "out")
    else:
        got = run(r.cwd, "serve", r.a, r.b, "--x", x, "--fix", fix, "--event", "violated", "--json")
    if listed is not None:
        assert_refusal(got, *listed)
        assert not (tmp_path / "out").exists()
        return
    assert got.code == 0, got.err
    if verb == "serve":
        fixed = strict_json(got.out)["view"]["fixed"]
        assert fixed == {key: pinned} and type(fixed[key]) is type(pinned), fixed
    else:
        # The same report as the value spelt the way a TOML scalar always read.
        spelt = f'{key}="{pinned}"' if isinstance(pinned, str) else f"{key}={pinned!r}"
        if spelt == fix:
            # Typed as the scalar already reads: the same number in exponent form instead.
            spelt = f"{key}={pinned:e}"
        assert spelt != fix, spelt
        same = run(r.cwd, "report", r.a, r.b, "--x", x, "--fix", spelt, "--out", tmp_path / "spelt")
        assert same.code == 0, same.err
        assert (tmp_path / "out" / "report.md").read_bytes() == (tmp_path / "spelt" / "report.md").read_bytes()


# ---------- PF3.8 --replicates ----------


#: The command typed after one roomy run is in the store; ``--yes`` so the gate is the refusal.
GATE_CASES = {
    "the default spec": ["--yes"],
    "every option kept, --replicates added": ["{spec}", "--target", PATCHED, "--name", "my second run", "--pair-with", "latest", "--episode-timeout", "30", "--yes"],
    "--replicates replaced": ["--replicates", "6", "--name", "mine", "--yes"],
}


@pytest.mark.parametrize("case", ["the override is recorded", *GATE_CASES])
def test_pf3_8_replicates_overrides_the_spec_and_the_power_gate_offers_the_smallest_that_passes(case: str, tmp_path: Path) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    store = cwd / "prove-runs"
    if case == "the override is recorded":
        (cwd / "prove.toml").write_text(SPEC, encoding="utf-8")
        r = run(cwd, "sweep", "--replicates", "7", "--yes", *LOOSE)
        assert r.code == 0, r.err
        (entry,) = runs_of(store)
        assert entry["rows"] == 4 * 7, entry
        assert manifest_of(store, entry["run_id"])["environment"]["sweep"]["replicates"] == 7
        return

    small = SPEC.replace("replicates = 50", "replicates = 5")
    (cwd / "prove.toml").write_text(small, encoding="utf-8")
    (cwd / "spec.toml").write_text(small, encoding="utf-8")
    # The run --pair-with takes is roomy, so the pairs never cap what the offered replicates reach.
    base = run(cwd, "sweep", "--replicates", "400", "--yes", *LOOSE)
    assert base.code == 0, base.err
    typed = ["sweep", *[t.format(spec="spec.toml") for t in GATE_CASES[case]]]

    refused = run(cwd, *typed)
    assert refused.code == 1, refused.err
    assert first_word(refused.out) == "plan"
    assert refused.err.splitlines()[0].startswith("error: "), refused.err
    (line,) = [n for n in refused.nexts if "--replicates" in shlex.split(n) and "--max-mde" not in shlex.split(n)]
    offered = shlex.split(line)
    assert offered[0] == COMMAND and "--replicates" in offered, offered
    assert without_option(offered[1:], "--replicates") == without_option(typed, "--replicates"), offered
    n = int(offered[offered.index("--replicates") + 1])
    assert n > 6

    passes = run(cwd, *offered[1:], "--dry-run")
    assert passes.code == 0, passes.err
    fewer = [*without_option(offered[1:], "--replicates"), "--replicates", str(n - 1), "--dry-run"]
    short = run(cwd, *fewer)
    assert short.code == 1 and first_word(short.out) == "plan", short.err
    assert len(runs_of(store)) == 1
