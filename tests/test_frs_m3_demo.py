"""First run M3 -- a demo agent that needs no key (#3): the frozen tests for D1 to D8 (First Run Spec
section 4; FRS-12 to FRS-15).

**What M3 is for.** The keyless example lives inside the package, so there is nothing to edit and
nothing to set Prove up on, and the one agent on a real model needs a key. From 0.5.0
``poisson-prove init --demo`` writes a small support bot into a folder: ``support_bot.py`` and
``prompts.py``, the stand-in ``docs/your-own-agent.md`` has always shown, and ``demo.md``, which says
what it is and what to do with it. ``--with-setup`` also writes the two files a coding agent would
write for it, ``prove_rollout.py`` and ``prove.toml``. The agent on a real model,
``examples/your-first-real-agent/``, is linked and never shipped, and every page that links it says
what it needs.

**Readings, named here** (each a point read one way and lettered).

- (a) The demo's five files are package data at ``poisson_prove/demo/``, under the names they are
  written as, beside the quickstart spec and the setup skill. What ``init --demo`` writes is those
  bytes; ``test_pf7_packaging`` lists them in the wheel and the sdist (D8).
- (b) ``init --demo`` prints its lines, pinned by their facts: a verdict line ``ok  wrote … (3 files)``
  (five with ``--with-setup``) that says the demo needs no key, one ``  wrote  <path>`` line per
  file (each path, read from the folder the command ran in, is the file written; their order is
  free), and one ``  next:`` line; nothing else on stdout and nothing on stderr. On a terminal it
  asks nothing: the question ``init`` asks after it writes a spec is not asked of the demo, whose
  ``--runs-on`` is a wrong command line.
- (c) The ``next:`` line is ``poisson-prove init --agent``, with ``--repo DIR`` as typed when the
  demo went into another folder. With ``--with-setup`` it is ``poisson-prove sweep`` here; into
  another folder the spec does not give its words, so it is pinned by what it does: a ``sweep``
  command that, typed from the folder the command ran in with ``--dry-run`` added, plans the demo.
- (d) ``--repo DIR`` is made when it is missing, parents included. A ``--repo`` that is a file is a
  refusal (exit 1), as it is for ``init --agent``.
- (e) Wrong command lines (exit 2, nothing written): ``--demo`` with ``--example``, ``--target``,
  ``--out``, ``--runs-on`` or ``--agent`` (section 4.1 step 3), and two the spec does not list:
  ``--demo`` with ``--print``, which goes with ``--agent`` alone, and ``--with-setup`` without
  ``--demo``.
- (f) The demo's files are the ones the command writes: three without ``--with-setup``, five with
  it. A ``prove.toml`` or ``prove_rollout.py`` of the person's own is not the demo's when
  ``--with-setup`` was not typed, so it is neither refused nor replaced. A link standing at one of
  the names counts as a file there, where it points or nowhere. A folder standing at one is refused
  with ``--force`` too, naming it, and nothing is written.
- (g) "Written whole or not at all (written aside, then renamed)" is read two ways: with
  ``--force`` a link standing at a name is replaced by a file and the file it pointed at is left as
  it was; and an interrupt at the second move into place leaves the first file whole and no other
  file in the folder, a file written aside included. The interrupt is Ctrl-C raised where the
  second file would be moved into place (``os.replace`` or ``os.rename``). The command then exits
  130 and does not say that nothing was written.
- (h) "Every outbound socket blocked" is a guard loaded before anything else in a process of its
  own that refuses and records every connection, send and name lookup, loopback included. "No key
  variable set" is that process's environment built from nothing: a path, an empty ``HOME``, and
  nothing whose name says key, token, secret, password or credential.
- (i) "Nothing outside the standard library and its sibling" is read from the source of
  ``support_bot.py`` and ``prompts.py``: every import, wherever it sits, names a standard-library
  module or the other of the two. ``prove_rollout.py`` imports those and ``poisson_prove``.
- (j) "The same Episode in two processes": two interpreters started with different hash seeds.
- (k) D5's change is one more line in ``prompts.py`` that adds "step by step" to ``SYSTEM``; its
  salts are twenty fixed ones, typed with ``--salt``. All twenty run as a user types them, each
  command a process of its own, in the slow lane: that test took 132 s on this machine under load,
  and the same twenty in one process 52 s. One salt, the first, runs in the code lane in this
  process (3 s), so a pull request that breaks the demo's change turns red. On 220 measured salts the verdict was ``safer``
  220 times.
- (l) In one process a second sweep reads the person's modules as the first left them, so the
  one-salt case forgets ``prompts``, ``support_bot`` and ``prove_rollout`` between its sweeps, as a
  second command would start without them.
- (m) "The replicates the M2 gate accepts" is read as the number the setup skill would write: the
  one the check's refusal names when the spec is set to the skill's own 20.
- (n) D7's link answering 200 is the release session's check. Here: every page that links the
  example (the README, every page under ``docs/``, the shipped ``demo.md``) links it on GitHub and
  says, in one paragraph that holds a link to it, the key's variable, the extra, a network (named
  twice: as a need, and in what happens without one), the model, the requests a sweep makes and
  whose account pays, that without the key every case errors, and that without a network every
  case ends ``api_error``. The request count and the model are read
  from the example itself. Both failure behaviours were run on 2026-11-18 with every socket
  refused: with no key the sweep ends ``stopped  every rollout errored`` (exit 3); with a key that
  is no key and no network every case ends ``api_error`` and the sweep completes.
- (o) The docs and the CHANGELOG are pinned by facts, not sentences (section 4.4, section 8).
  demo.md too: its facts, and one sentence each for the change to try and for the one phrase.
- (p) Windows writes the same files (section 4.3); no lane runs on Windows, so no test here does.
- (q) One test per behaviour, and a test that caught no planted change alone was cut: a test of
  the spec's keys read one by one, and the cases of D1 and D2 that another case covered. What is
  kept although it is caught together with others is D6's first test, which is the invariant
  itself, and the packaging list, which D8 names.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| D1 the files, the output, exit 0, the shipped bytes | ``test_d1_init_demo_writes_exactly_its_files_and_prints_them`` (four cases), ``test_d1_json_prints_the_init_document``, ``test_d1_on_a_terminal_it_asks_nothing``, ``test_d1_demo_goes_with_no_other_way_of_init`` (seven cases) |
| D2 refused naming each, writing none | ``test_d2_an_existing_file_of_the_demos_is_refused_naming_each_and_writing_none`` (six cases), ``test_d2_only_the_files_it_writes_are_the_demos`` |
| D2 ``--force`` replaces the demo's files only | ``test_d2_force_replaces_the_demos_files_and_nothing_else`` (two cases) |
| D2 whole or not at all; section 4.3's Ctrl-C | ``test_d2_a_link_standing_at_a_name_is_replaced_not_written_through``, ``test_d2_an_interrupt_leaves_whole_files_and_the_rest_unwritten`` |
| D3 keyless and offline | ``test_d3_two_thousand_rollouts_of_every_condition_with_every_socket_blocked_and_no_key``, ``test_d3_the_demo_imports_the_standard_library_and_its_sibling_alone`` |
| D4 deterministic | ``test_d4_the_same_cfg_and_seed_give_the_same_episode_in_two_processes`` |
| D5 it shows a change | ``test_d5_the_change_reads_safer_on_one_salt`` (code lane), ``test_d5_the_change_reads_safer_in_at_least_19_of_20_salts`` (slow) |
| D6 ``init --agent`` beside the demo; the check passes | ``test_d6_init_agent_writes_its_four_beside_the_demo_and_the_skills_check_passes``, ``test_d6_the_setups_replicates_are_the_ones_the_check_names`` |
| D7 the facts on every page that links the real agent | ``test_d7_every_page_that_links_the_real_agent_says_what_it_needs`` |
| D8 the wheel holds the demo | ``test_pf7_packaging::test_pf7_6_each_archive_holds_exactly_its_set`` (changed) |
| FRS-13 what ``--with-setup`` writes: the target, the tickets as one axis, the temperature as another, the outcomes declared | ``test_each_condition_runs_the_ticket_and_the_temperature_it_names``; the target by D6's check, the declared outcomes by D3, the declared kinds by D5, the size of the family by reading m |
| FRS-15 the docs page's stand-in, one phrase | ``test_the_demo_is_the_docs_pages_stand_in``, ``test_the_stand_ins_prompt_matters_only_through_the_one_phrase``, ``test_demo_md_says_what_the_demo_is_and_what_to_do_with_it`` |
| section 4.4 the docs, section 8 the CHANGELOG | ``test_the_docs_put_the_demo_one_command_away`` (five pages), ``test_the_0_5_0_entry_adds_the_demo`` |
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from conftest import blas_thread_cap
from pf6_support import run_pty, strip_escapes
from test_pf11_setup_agent import (FOUR, Result, added, assert_refusal, commands, detail, replicates_offered, run,
                                   run_child, snapshot, split_frontmatter, with_replicates)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DOCS = ROOT / "docs"
COMMAND = "poisson-prove"

#: What ``init --demo`` writes, and what ``--with-setup`` adds (FRS-12, FRS-13).
DEMO = ("support_bot.py", "prompts.py", "demo.md")
SETUP = ("prove_rollout.py", "prove.toml")
FIVE = DEMO + SETUP

PHRASE = "step by step"
#: The change demo.md names, as one more line of ``prompts.py`` (reading k).
THE_CHANGE = f'\nSYSTEM = SYSTEM + " Work {PHRASE}."\n'
#: The demo's modules, as a sweep in this process leaves them imported (reading l).
PERSONS_MODULES = ("prompts", "support_bot", "prove_rollout")

#: D5's twenty salts.
SALTS = tuple(hashlib.sha256(f"m3-demo-{i}".encode()).hexdigest()[:16] for i in range(20))

REAL_AGENT = ROOT / "examples" / "your-first-real-agent"
REAL_AGENT_LINK = re.compile(r"\]\((\S*examples/your-first-real-agent[^)\s]*)\)")
REAL_AGENT_ON_GITHUB = re.compile(r"https://github\.com/poisson-labs/prove/(?:tree|blob)/main/examples/your-first-real-agent(?:/[^)\s]*)?")
FIRST_LINE = re.compile(r"^([a-z][a-z ]*?)  \S")


@pytest.fixture(autouse=True)
def _empty_home_and_no_store_variables(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)


# ---------- helpers ----------


def packaged(name: str) -> bytes:
    """A file of the demo as the package ships it (reading a)."""
    return (resources.files("poisson_prove") / "demo" / name).read_bytes()


def packaged_text(name: str) -> str:
    return packaged(name).decode("utf-8")


def folder(base: Path, name: str = "repo") -> Path:
    made = base / name
    made.mkdir(parents=True)
    return made


def demo_in(base: Path, *flags: str, name: str = "repo") -> Path:
    """A new folder with the demo written into it by the command itself."""
    repo = folder(base, name)
    r = run(repo, "init", "--demo", *flags)
    assert r.code == 0, r
    return repo


def persons_own_files(repo: Path) -> None:
    """Files of the person's own that the demo must never write to, a README among them (FRS-12)."""
    for name, text in (
        ("README.md", "# My service\n\nWhat it does.\n"),
        ("AGENTS.md", "# Notes for coding agents\n"),
        ("src/app.py", "print('mine')\n"),
        ("work/my-own.md", "my own words\n"),
    ):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def wrote_lines(out: str) -> list[str]:
    return [line[len("  wrote  "):] for line in out.splitlines() if line.startswith("  wrote  ")]


def the_next(r: Result) -> list[str]:
    (line,) = r.nexts
    return shlex.split(line)


GUARD = '''\
import os, socket, sys

_LOG = os.environ["M3_SOCKET_LOG"]
sys._m3_guard = True


def _refuse(what, address=None):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(what + " " + repr(address) + "\\n")
    raise OSError("every socket is blocked in this test: " + what + " " + repr(address))


def _connect(self, address):
    _refuse("connect", address)


def _connect_ex(self, address):
    _refuse("connect_ex", address)


def _sendto(self, *args):
    _refuse("sendto", args[-1] if args else None)


def _sendmsg(self, *args):
    _refuse("sendmsg")


def _getaddrinfo(host, *args, **kwargs):
    _refuse("getaddrinfo", host)


def _name(host):
    _refuse("name lookup", host)


def _create_connection(address, *args, **kwargs):
    _refuse("create_connection", address)


socket.socket.connect, socket.socket.connect_ex = _connect, _connect_ex
socket.socket.sendto, socket.socket.sendmsg = _sendto, _sendmsg
socket.getaddrinfo, socket.create_connection = _getaddrinfo, _create_connection
socket.gethostbyname = socket.gethostbyname_ex = _name
'''

#: Every condition of the folder's ``prove.toml`` at seeds 0 to ``M3_SEEDS`` - 1, through its own
#: rollout: what came back, as one JSON line.
EPISODES = '''\
import hashlib, itertools, json, os, re, sys, tomllib

with open("prove.toml", "rb") as fh:
    spec = tomllib.load(fh)
from poisson_prove import Episode
from prove_rollout import rollout

names = list(spec["axes"])
rows, bad, outcomes, conditions, counts = [], [], set(), 0, {}
for values in itertools.product(*(spec["axes"][name]["values"] for name in names)):
    cfg = dict(zip(names, values))
    conditions += 1
    ended = counts.setdefault(json.dumps(cfg, sort_keys=True), {})
    for seed in range(int(os.environ["M3_SEEDS"])):
        e = rollout(dict(cfg), seed)
        whole = (isinstance(e, Episode) and isinstance(e.outcome, str) and 0 <= e.t <= e.horizon
                 and e.meta.get("case_id") == cfg["ticket"])
        if not whole:
            bad.append([cfg, seed, repr(e)])
            continue
        outcomes.add(e.outcome)
        ended[e.outcome] = ended.get(e.outcome, 0) + 1
        rows.append([sorted(cfg.items()), seed, e.outcome, e.t, e.horizon, sorted(e.meta.items())])
print(json.dumps({
    "guard": bool(getattr(sys, "_m3_guard", False)),
    "keys": sorted(k for k in os.environ if re.search("KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", k.upper())),
    "conditions": conditions,
    "rollouts": len(rows) + len(bad),
    "bad": bad[:5],
    "outcomes": sorted(outcomes),
    "counts": counts,
    "digest": hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest(),
}))
'''


def episodes(repo: Path, base: Path, *, seeds: int, hash_seed: str = "0") -> dict[str, Any]:
    """``EPISODES`` in an interpreter of its own, in ``repo``: every socket blocked, an environment
    built from nothing (reading h). Also what the guard recorded, as ``attempts``."""
    guard, home = base / "guard", base / "home"
    guard.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    (guard / "sitecustomize.py").write_text(GUARD, encoding="utf-8")
    log = guard / "attempts.log"
    log.unlink(missing_ok=True)
    env = {
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(home),
        "PYTHONPATH": os.pathsep.join([str(guard), str(SRC)]),
        "PYTHONHASHSEED": hash_seed,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "M3_SOCKET_LOG": str(log),
        "M3_SEEDS": str(seeds),
        "TMPDIR": str(home),
        **blas_thread_cap(),
    }
    done = subprocess.run([sys.executable, "-c", EPISODES], cwd=repo, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr[-3000:]
    found: dict[str, Any] = json.loads(done.stdout.splitlines()[-1])
    found["attempts"] = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return found


def conditions_of(spec_text: str) -> int:
    return math.prod(len(axis["values"]) for axis in tomllib.loads(spec_text)["axes"].values())


@contextmanager
def the_demos_modules_forgotten() -> Iterator[None]:
    """This process without the demo's modules, before and after (reading l)."""
    for name in PERSONS_MODULES:
        sys.modules.pop(name, None)
    try:
        yield
    finally:
        for name in PERSONS_MODULES:
            sys.modules.pop(name, None)


def verdict_word(out: str) -> str:
    lines = out.splitlines()
    found = FIRST_LINE.match(lines[0]) if lines else None
    return found.group(1) if found else ""


def add_the_phrase(repo: Path) -> None:
    prompts = repo / "prompts.py"
    before = prompts.read_text(encoding="utf-8")
    assert PHRASE not in before, "the demo's prompt already holds the phrase, so the change would change nothing"
    prompts.write_text(before + THE_CHANGE, encoding="utf-8")


def paragraphs(text: str) -> list[str]:
    return [" ".join(block.split()) for block in re.split(r"\n\s*\n", text) if block.strip()]


def code_spans(text: str) -> list[str]:
    return re.findall(r"`([^`\n]+)`", text)


# ---------- D1: the files, the lines, the exit code ----------

D1_CASES = ["here, in a repository with its own README", "here, with the setup", "--repo, a folder that is missing",
            "--repo, a folder that is there, with the setup"]


@pytest.mark.parametrize("case", D1_CASES)
def test_d1_init_demo_writes_exactly_its_files_and_prints_them(case: str, tmp_path: Path) -> None:
    """D1, FRS-12, FRS-13, readings b, c and d: the three files (five with ``--with-setup``), each
    the package's own bytes, into this folder or ``--repo``, and nothing else anywhere; a README and
    the person's other files are never touched; the lines of section 4.1."""
    home = Path(os.environ["HOME"])
    names = FIVE if "with the setup" in case else DEMO
    flags = ["--with-setup"] if "with the setup" in case else []
    if case.startswith("--repo"):
        cwd = folder(tmp_path, "elsewhere")
        repo = tmp_path / "new" / "deeper" if "missing" in case else folder(tmp_path)
        typed = str(repo)
        argv = ["init", "--demo", *flags, "--repo", typed]
    else:
        repo = cwd = folder(tmp_path)
        typed = ""
        argv = ["init", "--demo", *flags]
    if "README" in case:
        persons_own_files(repo)
    roots = (tmp_path, home)
    before = snapshot(*roots)

    r = run(cwd, *argv)

    assert r.code == 0, r
    assert r.err == "", r.err
    assert added(before, snapshot(*roots), tmp_path) == sorted(str((repo / name).relative_to(tmp_path)) for name in names)
    for name in names:
        assert (repo / name).read_bytes() == packaged(name), name
        assert not (repo / name).is_symlink()
    out = r.out.splitlines()
    assert re.match(rf"^ok  wrote .*\({len(names)} files\)$", out[0]) and "no key" in out[0], r.out
    assert sorted((cwd / w).resolve() for w in wrote_lines(r.out)) == sorted((repo / name).resolve() for name in names), r.out
    assert len(out) == 1 + len(names) + 1, r.out
    words = the_next(r)
    if not flags:
        assert words == [COMMAND, "init", "--agent", *(["--repo", typed] if typed else [])], words
    elif not typed:
        assert words == [COMMAND, "sweep"], words
    else:
        # Into another folder, with the setup: the line is a sweep that plans the demo when typed
        # from the folder the command ran in (reading c).
        assert words[:2] == [COMMAND, "sweep"], words
        planned = run_child(cwd, tmp_path / "followed", *words[1:], "--dry-run")
        assert planned.code == 0, planned.err
        assert detail(planned.out, "target") == ["prove_rollout:rollout (imports, takes cfg and seed)"], planned.out
        assert planned.attempts == [], planned.attempts


def test_d1_json_prints_the_init_document(tmp_path: Path) -> None:
    """Section 4.1 step 3: ``--json`` prints ``poisson-prove.init/1`` as ``init`` does, the files
    written under ``wrote`` and ``next`` last."""
    repo = folder(tmp_path)
    r = run(repo, "init", "--demo", "--with-setup", "--json")
    assert r.code == 0 and r.err == "", r
    doc = json.loads(r.out)
    assert list(doc)[:3] == ["schema", "verdict", "sentence"] and doc["schema"] == "poisson-prove.init/1", doc
    assert doc["verdict"] == "ok" and list(doc)[-1] == "next", doc
    assert sorted((repo / w).resolve() for w in doc["wrote"]) == sorted((repo / name).resolve() for name in FIVE), doc
    assert [shlex.split(line) for line in doc["next"]] == [[COMMAND, "sweep"]], doc
    assert all((repo / name).read_bytes() == packaged(name) for name in FIVE)


def test_d1_on_a_terminal_it_asks_nothing(tmp_path: Path) -> None:
    """Reading b: on a terminal ``init`` asks where sweeps of a spec it wrote should run. The demo
    is not asked: the command ends by itself with every file written."""
    repo, home = folder(tmp_path), folder(tmp_path, "home")
    done = run_pty(["init", "--demo", "--with-setup"], home=home, cwd=repo, stdin="pty", stdout="pty", stderr="own", timeout=60)
    shown = strip_escapes(done.out + done.err)
    assert done.code == 0, shown
    assert "where should sweeps run" not in shown, shown
    assert sorted(p.name for p in repo.iterdir()) == sorted(FIVE)


WRONG_LINES = {
    "--demo with --example": ["--demo", "--example"],
    "--demo with --target": ["--demo", "--target", "my_agent:rollout"],
    "--demo with --out": ["--demo", "--out", "spec.toml"],
    "--demo with --runs-on": ["--demo", "--runs-on", "local"],
    "--demo with --agent": ["--demo", "--agent"],
    "--demo with --print": ["--demo", "--print"],
    "--with-setup without --demo": ["--with-setup"],
}


@pytest.mark.parametrize("case", list(WRONG_LINES))
def test_d1_demo_goes_with_no_other_way_of_init(case: str, tmp_path: Path) -> None:
    """Section 4.1 step 3 and reading e: a wrong command line, exit 2, nothing printed on stdout
    and nothing written."""
    repo = folder(tmp_path)
    home = Path(os.environ["HOME"])
    before = snapshot(tmp_path, home)
    r = run(repo, "init", *WRONG_LINES[case])
    assert r.code == 2 and r.out == "", r
    assert snapshot(tmp_path, home) == before


# ---------- D2: an existing file, --force, whole or not at all ----------

D2_REFUSED = {
    "support_bot.py exists": (("support_bot.py",), ()),
    "prompts.py is a link that points nowhere": (("prompts.py",), ()),
    "demo.md exists": (("demo.md",), ()),
    "both of the setup's exist, with the setup": (SETUP, ("--with-setup",)),
    "prove.toml is a folder, with the setup and --force": (("prove.toml",), ("--with-setup", "--force")),
    "--repo that is a file": ((), ()),
}


@pytest.mark.parametrize("case", list(D2_REFUSED))
def test_d2_an_existing_file_of_the_demos_is_refused_naming_each_and_writing_none(case: str, tmp_path: Path) -> None:
    """D2 and readings d and f: exit 1, the ``error:`` line naming each file that exists and no
    other, a ``next:`` that is the command as typed with ``--force``, and nothing written. A folder
    standing at a name is refused with ``--force`` too: the demo writes files."""
    existing, flags = D2_REFUSED[case]
    repo = folder(tmp_path)
    persons_own_files(repo)
    home = Path(os.environ["HOME"])
    if case == "--repo that is a file":
        target = tmp_path / "a-file.txt"
        target.write_text("not a folder\n", encoding="utf-8")
        before = snapshot(tmp_path, home)
        r = run(repo, "init", "--demo", "--repo", target)
        assert_refusal(r, str(target))
        assert snapshot(tmp_path, home) == before
        return
    for name in existing:
        if "link" in case:
            (repo / name).symlink_to(tmp_path / "nowhere.py")
        elif "folder" in case:
            (repo / name).mkdir()
            (repo / name / "kept.txt").write_text("the person's own folder\n", encoding="utf-8")
        else:
            (repo / name).write_text("the person's own text\n", encoding="utf-8")
    before = snapshot(tmp_path, home)
    r = run(repo, "init", "--demo", *flags)
    assert_refusal(r, *existing)
    for name in FIVE:
        if name not in existing:
            assert name not in r.error, (name, r.error)
    assert snapshot(tmp_path, home) == before
    assert not (tmp_path / "nowhere.py").exists()
    if "--force" not in flags:
        assert any(sorted(shlex.split(n)) == sorted([COMMAND, "init", "--demo", *flags, "--force"]) for n in r.nexts), r.nexts


def test_d2_only_the_files_it_writes_are_the_demos(tmp_path: Path) -> None:
    """Reading f: without ``--with-setup`` a ``prove.toml`` and a ``prove_rollout.py`` of the
    person's own are not the demo's. They are not refused and not touched."""
    repo = folder(tmp_path)
    for name in SETUP:
        (repo / name).write_text("the person's own setup\n", encoding="utf-8")
    before = snapshot(tmp_path)
    r = run(repo, "init", "--demo")
    assert r.code == 0, r
    assert added(before, snapshot(tmp_path), tmp_path) == sorted(f"repo/{name}" for name in DEMO)
    assert all(name not in r.out for name in SETUP), r.out


@pytest.mark.parametrize("names", [DEMO, FIVE], ids=["the three", "the five"])
def test_d2_force_replaces_the_demos_files_and_nothing_else(names: tuple[str, ...], tmp_path: Path) -> None:
    """D2: ``--force`` replaces the files this command writes, each with the package's bytes, and
    leaves every other file as it was, the setup's two included when they were not asked for."""
    repo = folder(tmp_path)
    persons_own_files(repo)
    for name in FIVE:
        (repo / name).write_text("an older copy\n", encoding="utf-8")
    (repo / "prove-runs").mkdir()
    (repo / "prove-runs" / "kept.txt").write_text("a run\n", encoding="utf-8")
    home = Path(os.environ["HOME"])
    before = snapshot(repo, home)
    r = run(repo, "init", "--demo", *(["--with-setup"] if names == FIVE else []), "--force")
    assert r.code == 0, r
    after = snapshot(repo, home)
    assert sorted(k for k in before if after.get(k) != before[k]) == sorted(f"repo/{name}" for name in names)
    assert set(after) == set(before)
    for name in names:
        assert (repo / name).read_bytes() == packaged(name), name


def test_d2_a_link_standing_at_a_name_is_replaced_not_written_through(tmp_path: Path) -> None:
    """D2 and reading g: each file is written aside and renamed into place, so with ``--force`` a
    link standing at a name becomes the file, and the file it pointed at is left as it was."""
    repo = folder(tmp_path)
    own = tmp_path / "mine.py"
    own.write_text("SYSTEM = 'my own prompt'\n", encoding="utf-8")
    (repo / "prompts.py").symlink_to(own)
    r = run(repo, "init", "--demo", "--force")
    assert r.code == 0, r
    assert not (repo / "prompts.py").is_symlink()
    assert (repo / "prompts.py").read_bytes() == packaged("prompts.py")
    assert own.read_text(encoding="utf-8") == "SYSTEM = 'my own prompt'\n"


def test_d2_an_interrupt_leaves_whole_files_and_the_rest_unwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """D2, section 4.3 and reading g: Ctrl-C as the second file would be moved into place. Exit 130;
    the one file already in place is whole and the folder holds nothing else; the command does not
    say that nothing was written. Running it again is refused naming that file, with ``--force``
    as the way on, and ``--force`` then writes all five."""
    repo = folder(tmp_path)
    moved: list[str] = []

    def interrupting(real: Any) -> Any:
        def move(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
            target = Path(os.fspath(dst))
            if target.name in FIVE and target.parent.resolve() == repo.resolve():
                if len(moved) == 1:
                    raise KeyboardInterrupt
                moved.append(target.name)
            return real(src, dst, *args, **kwargs)

        return move

    with monkeypatch.context() as patched:
        patched.setattr(os, "replace", interrupting(os.replace))
        patched.setattr(os, "rename", interrupting(os.rename))
        stopped = run(repo, "init", "--demo", "--with-setup")
    assert stopped.code == 130, stopped
    assert len(moved) == 1, "no file was moved into place: the demo's files are written aside, then renamed"
    assert sorted(p.name for p in repo.iterdir()) == moved, sorted(p.name for p in repo.iterdir())
    assert (repo / moved[0]).read_bytes() == packaged(moved[0])
    assert "nothing was written" not in stopped.out + stopped.err, stopped

    again = run(repo, "init", "--demo", "--with-setup")
    assert_refusal(again, moved[0])
    assert any(sorted(shlex.split(n)) == sorted([COMMAND, "init", "--demo", "--with-setup", "--force"]) for n in again.nexts), again.nexts
    assert run(repo, "init", "--demo", "--with-setup", "--force").code == 0
    assert all((repo / name).read_bytes() == packaged(name) for name in FIVE)


# ---------- D3: keyless and offline ----------


def test_d3_two_thousand_rollouts_of_every_condition_with_every_socket_blocked_and_no_key(tmp_path: Path) -> None:
    """D3 and reading h: the demo imported and run in a process whose every socket is refused and
    whose environment holds no key. Every rollout returns a whole Episode with one of the declared
    outcomes and the id of the case it ran, and nothing reaches for a socket."""
    repo = demo_in(tmp_path, "--with-setup")
    spec = (repo / "prove.toml").read_text(encoding="utf-8")
    ran = episodes(repo, tmp_path / "offline", seeds=2000)
    assert ran["guard"], "the socket guard was not loaded where the demo ran"
    assert ran["keys"] == [], ran["keys"]
    assert ran["attempts"] == [], ran["attempts"]
    assert ran["bad"] == [], ran["bad"]
    assert ran["conditions"] == conditions_of(spec) and ran["rollouts"] == 2000 * conditions_of(spec), ran
    assert ran["outcomes"] == sorted(tomllib.loads(spec)["declare"]["outcomes"]), ran["outcomes"]


def imports_of(source: str) -> set[str]:
    """The top-level module of every import in ``source``, wherever it sits."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module, "a relative import: the demo's files are not a package"
            found.add(node.module.split(".")[0])
    return found


def test_d3_the_demo_imports_the_standard_library_and_its_sibling_alone() -> None:
    """D3 and reading i: the agent's two files import the standard library and each other; the
    rollout imports those and Prove. Nothing is imported by name at run time."""
    siblings = {"support_bot", "prompts"}
    for name in ("support_bot.py", "prompts.py", "prove_rollout.py"):
        source = packaged_text(name)
        allowed = set(sys.stdlib_module_names) | siblings | ({"poisson_prove"} if name == "prove_rollout.py" else set())
        assert imports_of(source) <= allowed, (name, sorted(imports_of(source) - allowed))
        assert not re.search(r"__import__|importlib|\bexec\(|\beval\(", source), name
    assert "prompts" in imports_of(packaged_text("support_bot.py")), "the agent reads its prompt from prompts.py"
    assert {"support_bot", "poisson_prove"} <= imports_of(packaged_text("prove_rollout.py"))


# ---------- D4: deterministic ----------


def test_d4_the_same_cfg_and_seed_give_the_same_episode_in_two_processes(tmp_path: Path) -> None:
    """D4 and reading j: every condition at 300 seeds, in two interpreters started with different
    hash seeds, ends the same way every time."""
    repo = demo_in(tmp_path, "--with-setup")
    first = episodes(repo, tmp_path / "one", seeds=300, hash_seed="1")
    second = episodes(repo, tmp_path / "two", seeds=300, hash_seed="2")
    assert first["bad"] == second["bad"] == []
    assert len(first["outcomes"]) > 1, first["outcomes"]
    assert first["digest"] == second["digest"]


# ---------- D5: it shows a change ----------


def test_d5_the_change_reads_safer_on_one_salt(tmp_path: Path) -> None:
    """D5 and readings k and l, in the code lane: on the ``--with-setup`` spec a sweep, "step by
    step" added to ``SYSTEM``, a sweep with ``--pair-with latest`` and ``diff`` read ``safer``."""
    repo = demo_in(tmp_path, "--with-setup")
    with the_demos_modules_forgotten():
        before = run(repo, "sweep", "--yes", "--salt", SALTS[0])
        assert before.code == 0, before
    add_the_phrase(repo)
    with the_demos_modules_forgotten():
        after = run(repo, "sweep", "--yes", "--pair-with", "latest")
        assert after.code == 0, after
    compared = run(repo, "diff")
    assert compared.code == 0, compared
    assert verdict_word(compared.out) == "safer", compared.out


@pytest.mark.slow
def test_d5_the_change_reads_safer_in_at_least_19_of_20_salts(tmp_path: Path) -> None:
    """D5 and reading k: the same three commands at each of twenty salts, each a process of its own
    as a user types them, with no key and nothing reaching for the network. The verdict word alone
    is read; the counts move by salt."""
    words: dict[str, str] = {}
    for at, salt in enumerate(SALTS):
        repo = demo_in(tmp_path, "--with-setup", name=f"salt-{at:02d}")
        base = tmp_path / f"runs-{at:02d}"
        before = run_child(repo, base, "sweep", "--yes", "--salt", salt)
        assert before.code == 0, (salt, before.err)
        add_the_phrase(repo)
        after = run_child(repo, base, "sweep", "--yes", "--pair-with", "latest")
        assert after.code == 0, (salt, after.err)
        compared = run_child(repo, base, "diff")
        assert compared.code == 0, (salt, compared.err)
        assert before.attempts == after.attempts == compared.attempts == [], salt
        words[salt] = verdict_word(compared.out)
    safer = [salt for salt, word in words.items() if word == "safer"]
    assert len(safer) >= 19, {salt: word for salt, word in words.items() if word != "safer"}


# ---------- D6: the setup skill beside the demo ----------


def test_d6_init_agent_writes_its_four_beside_the_demo_and_the_skills_check_passes(tmp_path: Path) -> None:
    """D6: in a folder holding the demo ``init --agent`` writes its four files as on any folder and
    changes none of the demo's; the check the skill shows then passes on the ``--with-setup``
    files, plans the demo's rollout, reaches for no socket and writes nothing."""
    repo = demo_in(tmp_path, "--with-setup")
    before = snapshot(repo)
    r = run(repo, "init", "--agent")
    assert r.code == 0 and r.err == "", r
    assert added(before, snapshot(repo), repo) == sorted(FOUR)
    body = split_frontmatter((repo / FOUR[0]).read_text(encoding="utf-8"))[1]
    (check,) = [c for s, c in commands(body, "bash") if s == "## The check"]
    ready = snapshot(repo)
    checked = run_child(repo, tmp_path / "check", *shlex.split(check)[1:])
    assert checked.code == 0, checked.err
    assert checked.out.splitlines()[0].startswith("plan  "), checked.out
    assert detail(checked.out, "target") == ["prove_rollout:rollout (imports, takes cfg and seed)"], checked.out
    assert checked.attempts == [], checked.attempts
    assert snapshot(repo) == ready


def test_d6_the_setups_replicates_are_the_ones_the_check_names(tmp_path: Path) -> None:
    """D6 and reading m: set to the skill's own 20 replicates, the check refuses and names a number
    for ``--replicates``; that number is the one ``--with-setup`` wrote."""
    repo = demo_in(tmp_path, "--with-setup")
    spec = repo / "prove.toml"
    written = spec.read_text(encoding="utf-8")
    spec.write_text(with_replicates(written, 20), encoding="utf-8")
    refused = run_child(repo, tmp_path / "check", "sweep", "--dry-run")
    assert refused.code == 1, refused.out + refused.err
    assert tomllib.loads(written)["replicates"] == replicates_offered(refused.result)


# ---------- FRS-13: what --with-setup writes ----------


def tickets_of(source: str) -> dict[str, float]:
    """``TICKETS`` in the agent's source, each ticket with the share of attempts on it that end
    unresolved, read without importing it."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TICKETS" for t in node.targets):
            found: dict[str, float] = ast.literal_eval(node.value)
            return found
    raise AssertionError("support_bot.py has no TICKETS")


def test_each_condition_runs_the_ticket_and_the_temperature_it_names(tmp_path: Path) -> None:
    """Section 4.1 step 2 and ``docs/your-own-agent.md``'s "one case per condition": the rollout runs
    the ticket and the temperature ``cfg`` names, never a case picked from the seed. Over 2,000
    seeds, at each temperature a ticket the agent leaves unresolved more often ends against it more
    often, and each ticket ends differently at the two temperatures."""
    repo = demo_in(tmp_path, "--with-setup")
    spec = tomllib.loads((repo / "prove.toml").read_text(encoding="utf-8"))
    successes = set(spec["declare"]["successes"])
    temperatures = spec["axes"]["temperature"]["values"]
    ran = episodes(repo, tmp_path / "each", seeds=2000)
    assert ran["bad"] == [], ran["bad"]

    def ended(ticket: str, temperature: float) -> dict[str, int]:
        found: dict[str, int] = ran["counts"][json.dumps({"temperature": temperature, "ticket": ticket}, sort_keys=True)]
        return found

    rates = tickets_of(packaged_text("support_bot.py"))
    easiest_first = sorted(rates, key=lambda ticket: rates[ticket])
    assert len(set(rates.values())) == len(rates), rates
    for temperature in temperatures:
        against = [sum(n for outcome, n in ended(ticket, temperature).items() if outcome not in successes) for ticket in easiest_first]
        assert against == sorted(against) and len(set(against)) == len(against), (temperature, dict(zip(easiest_first, against)))
    for ticket in rates:
        assert len({json.dumps(ended(ticket, temperature), sort_keys=True) for temperature in temperatures}) == len(temperatures), ticket


# ---------- FRS-15: the docs page's stand-in, and its one phrase ----------


def page_files(page: str) -> dict[str, list[str]]:
    """Each file a docs page writes with ``docs-check: file NAME``, every version of it in order."""
    found: dict[str, list[str]] = {}
    for name, text in re.findall(r"<!-- docs-check: file (\S+) -->\n```\w*\n(.*?)\n```", page, flags=re.S):
        found.setdefault(name, []).append(text + "\n")
    return found


def test_the_demo_is_the_docs_pages_stand_in() -> None:
    """FRS-15: the agent ``init --demo`` writes is the stand-in ``docs/your-own-agent.md`` shows,
    byte for byte, and the change the page makes to its prompt is the phrase."""
    shown = page_files((DOCS / "your-own-agent.md").read_text(encoding="utf-8"))
    assert shown["support_bot.py"] == [packaged_text("support_bot.py")]
    assert shown["prompts.py"][0] == packaged_text("prompts.py")
    assert PHRASE not in shown["prompts.py"][0] and PHRASE in shown["prompts.py"][1], shown["prompts.py"]


#: Prompts without the phrase: none at all, and a long one that holds each of its words apart.
OTHER_PROMPTS = (
    "",
    "Be brief. Never refund without asking. Think hard, one step at a time, and go through the customer's "
    "ticket line by line before you answer it. Say what you checked, what you did not, and what happens next.",
)


def test_the_stand_ins_prompt_matters_only_through_the_one_phrase(tmp_path: Path) -> None:
    """FRS-15, what demo.md says of the stand-in, held to: no prompt at all and a long prompt of
    other words change no ending; the phrase changes some."""
    repo = demo_in(tmp_path, "--with-setup")
    as_written = episodes(repo, tmp_path / "written", seeds=300)
    assert as_written["bad"] == []
    for at, prompt in enumerate(OTHER_PROMPTS):
        assert PHRASE not in prompt
        (repo / "prompts.py").write_text(f"SYSTEM = {json.dumps(prompt)}\n", encoding="utf-8")
        other = episodes(repo, tmp_path / f"other-{at}", seeds=300)
        assert other["bad"] == [] and other["digest"] == as_written["digest"], prompt
    (repo / "prompts.py").write_text(f'SYSTEM = "Be brief and work {PHRASE}."\n', encoding="utf-8")
    with_the_phrase = episodes(repo, tmp_path / "phrase", seeds=300)
    assert with_the_phrase["bad"] == [] and with_the_phrase["digest"] != as_written["digest"]


def test_demo_md_says_what_the_demo_is_and_what_to_do_with_it(tmp_path: Path) -> None:
    """Section 4.1 step 1 and FRS-15, by facts: a stand-in that calls no model and needs no key or
    network, its replies drawn from the seed; the loop in order (set up with your coding agent,
    sweep, sweep again with ``--pair-with``, ``diff``); the change to try, "step by step" in
    ``SYSTEM`` in ``prompts.py``; and, in one sentence, that the stand-in reads only that phrase,
    with what that means for a real agent beside it. Every command it shows is one this build
    takes."""
    text = packaged_text("demo.md")
    flat = " ".join(text.split())
    for fact in (r"\bstand-in\b", r"\bno model\b", r"\bno key\b", r"\bnetwork\b", r"\bseed\b"):
        assert re.search(fact, flat), fact
    sentences = re.split(r"(?<=[.!?])\s+", flat)
    assert any(all(fact in s for fact in (PHRASE, "`SYSTEM`", "`prompts.py`")) for s in sentences), "demo.md does not say, in one sentence, the change to try: the phrase, in `SYSTEM`, in `prompts.py`"
    said = [p for p in paragraphs(text) if any(re.search(r"\bonly\b", s) and re.search(r"\bphrase\b", s) for s in re.split(r"(?<=[.!?])\s+", p))]
    assert said, "demo.md does not say, in one sentence, that the stand-in reads only the one phrase"
    assert any(re.search(r"\breal agent\b", p) for p in said), "nor that a real agent's prompt matters in ways this one cannot show"
    shown = [shlex.split(span) for span in code_spans(text) if span.startswith(COMMAND + " ")]
    loop = {
        "init --agent": lambda words: words[1] == "init" and "--agent" in words,
        "sweep": lambda words: words[1] == "sweep" and "--pair-with" not in words,
        "sweep --pair-with": lambda words: words[1] == "sweep" and "--pair-with" in words,
        "diff": lambda words: words[1] == "diff",
    }
    places = []
    for step, is_step in loop.items():
        hits = [at for at, words in enumerate(shown) if is_step(words)]
        assert hits, (step, shown)
        places.append(hits[0])
    assert places == sorted(places), (places, shown)
    helps: dict[str, str] = {}
    for words in shown:
        verb = words[1]
        if verb not in helps:
            r = run(tmp_path, verb, "--help")
            assert r.code == 0, (words, r)
            helps[verb] = r.out
        for option in (w for w in words[2:] if w.startswith("--")):
            assert re.search(rf"(?<![\w-]){re.escape(option)}(?![\w-])", helps[verb]), (words, option)


# ---------- D7: the facts on every page that links the real agent ----------


def real_agent_facts() -> list[str]:
    """What section 4.1 step 4 says of the example, the number and the model read from the example."""
    spec = tomllib.loads((REAL_AGENT / "prove.toml").read_text(encoding="utf-8"))
    requests = conditions_of((REAL_AGENT / "prove.toml").read_text(encoding="utf-8")) * spec["replicates"]
    (model,) = re.findall(r'^MODEL = "([^"]+)"$', (REAL_AGENT / "agent.py").read_text(encoding="utf-8"), flags=re.M)
    assert "api_error" in spec["declare"]["outcomes"]
    return ["OPENAI_API_KEY", "poisson-prove[agent]", model, f"{requests:,}", "OpenAI account", "api_error"]


def test_d7_every_page_that_links_the_real_agent_says_what_it_needs() -> None:
    """D7, FRS-14 and reading n: the README, the quickstart, the setup page and the shipped demo.md
    link the example on GitHub, and every page that links it says, in one paragraph that holds a
    link to it, the key's variable, the extra, a network, the model, the requests a sweep makes and whose
    account pays for them, that without the key every case errors, and ``api_error`` without a
    network."""
    pages = {str(p.relative_to(ROOT)): p.read_text(encoding="utf-8") for p in [ROOT / "README.md", *sorted(DOCS.rglob("*.md"))]}
    pages["demo.md"] = packaged_text("demo.md")
    facts = real_agent_facts()
    linking = []
    for name, text in pages.items():
        fewest: list[str] | None = None
        for paragraph in paragraphs(text):
            targets = REAL_AGENT_LINK.findall(paragraph)
            for target in targets:
                assert REAL_AGENT_ON_GITHUB.fullmatch(target), (name, target)
            if not targets:
                continue
            missing = [fact for fact in facts if fact not in paragraph]
            if not re.search(r"\berrors\b", paragraph):
                missing.append("without the key every case errors")
            if len(re.findall(r"\bnetwork\b", paragraph)) < 2:
                missing.append("a network, as a need and in what happens without one")
            fewest = missing if fewest is None or len(missing) < len(fewest) else fewest
        if fewest is not None:
            linking.append(name)
            assert fewest == [], (name, fewest)
    assert {"README.md", "docs/quickstart.md", "docs/setup-with-your-agent.md", "demo.md"} <= set(linking), sorted(linking)


# ---------- section 4.4 the docs, section 8 the CHANGELOG ----------


def section_of(page: str, heading: str) -> str:
    assert f"\n{heading}\n" in page, heading
    level = heading.split(" ", 1)[0]
    return re.split(rf"(?m)^{re.escape(level)} ", page.split(f"\n{heading}\n", 1)[1], maxsplit=1)[0]


def _init_page() -> list[str]:
    page = (DOCS / "commands" / "init.md").read_text(encoding="utf-8")
    options = section_of(page, "## Options")
    missing = [f"an Options item for {flag}" for flag in ("--demo", "--with-setup") if not re.search(rf"(?m)^- `{flag}`", options)]
    console = re.findall(r"(?m)^\$ (poisson-prove init [^\n#]*?)\s*(?:#.*)?$", page)
    if not any("--demo" in shlex.split(line) for line in console):
        missing.append("an example that runs init --demo")
    if not any({"--demo", "--with-setup"} <= set(shlex.split(line)) for line in console):
        missing.append("an example that runs init --demo --with-setup")
    return missing


DOCS_CASES = {
    "commands/init.md: the two options and their examples": _init_page,
    "your-own-agent.md: the stand-in is one command away": lambda: [] if "poisson-prove init --demo --with-setup" in code_spans((DOCS / "your-own-agent.md").read_text(encoding="utf-8")) else ["`poisson-prove init --demo --with-setup`"],
    "setup-with-your-agent.md: practise on the demo": lambda: [] if any(span.startswith("poisson-prove init --demo") for span in code_spans((DOCS / "setup-with-your-agent.md").read_text(encoding="utf-8"))) else ["`poisson-prove init --demo`"],
    "README.md: the demo, under the coding agent's section": lambda: [] if "init --demo" in section_of((ROOT / "README.md").read_text(encoding="utf-8"), "## Let your coding agent set it up") else ["init --demo"],
    "quickstart.md: the demo, under your own rollout": lambda: [] if "init --demo" in section_of((DOCS / "quickstart.md").read_text(encoding="utf-8"), "## On your own rollout") else ["init --demo"],
}


@pytest.mark.parametrize("case", list(DOCS_CASES))
def test_the_docs_put_the_demo_one_command_away(case: str) -> None:
    """Section 4.4 and section 7, by facts (reading o): each page that M3 changes names the command."""
    assert DOCS_CASES[case]() == [], case


def test_the_0_5_0_entry_adds_the_demo() -> None:
    """Section 8: under ``## 0.5.0`` an Added item that names the issue, ``init --demo``,
    ``--with-setup`` and the example on a real model. Its facts, not its sentences."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = text.split("\n## 0.5.0", 1)[1].split("\n## ", 1)[0]
    assert "\n### Added\n" in entry, entry[:400]
    added_items = entry.split("\n### Added\n", 1)[1].split("\n### ", 1)[0]
    items = [" ".join(item.split()) for item in re.split(r"(?m)^- ", added_items) if item.strip()]
    demo = [item for item in items if "(#3)" in item]
    assert len(demo) == 1, items
    for fact in ("init --demo", "--with-setup", "examples/your-first-real-agent", "key"):
        assert fact in demo[0], (fact, demo[0])
