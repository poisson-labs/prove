"""PF6, the look's file and the pretty rendering: the frozen tests (the code suite).

Written from the front-door spec's section 5.1 (the look file is Prove's), section 5.5 (pretty and
plain), its invariants PF6.0 to PF6.7, the rulings Q20, Q25 (as amended 2026-10-23), Q51 and Q62,
the look file the design session filed on 2026-10-23 (rulings Y1 to Y30, all as recommended) and the
test standard (section 10.6). ``tests/test_pf6_app.py`` holds the terminal app. The build is written
against these files and does not edit them.

**How the rendering is reached.** Every command runs as ``python -m poisson_prove`` in a process of
its own, as a user's shell runs it: on pipes, or with stdout and stderr each on a pseudo-terminal of
its own (so the two streams stay apart while both are terminals), 100 columns by 40 rows unless a
test says otherwise, ``HOME`` an empty folder, the planted keys set, none of section 5.5's switches set
unless the case sets one. Colour is read by role from the SGR escapes (green, yellow, red, bold, dim),
never by exact bytes.

**The corpus** (``CORPUS``) is PF6's own: one invocation of every verdict word section 5.5 gives a
meaning (``ok``, ``done``, ``passed``, ``under cap``; ``stopped``, ``too small to tell``, ``no
significant change``, ``note:``; ``error:``, ``failed``, ``at cap``; ``plan``, ``worse``/``safer``
through ``trade``, ``mixed``), every verb that prints a result, a cell table, a run table, a
reproduce block, the files ``report`` writes and the ``--json`` of the verbs that compare, list and
plan, on small stores so the whole corpus runs in seconds. PF1's corpus run both ways is the ``slow``
test at the end (reading L3).

**Readings, named here** (each is a yes/no in the session log, ``log/pf6/session-a.md``).

- L1 PF6.0's "equal, byte for byte, the base with the three changes applied": the base is committed
  as ``tests/fixtures/cli-look/bfe802d.md`` with each change's old and new text in ``changes.json``
  (each old text occurs exactly once), and the file's first 120 lines are the result; the build
  copies ``docs/cli-look.md`` from the design session's filing (sha256 ``92e71488…d85f``), so these
  tests commit the base and the changes, not the file.
- L2 "Piped, the pretty build's output equals the plain build's": the same build on streams that are
  not terminals gives the same bytes with and without ``--plain`` and with Rich unimportable, each
  variant running the whole corpus through the command's own entry point in a process of its own; a
  sweep's new run id, the times and the durations are replaced before comparing, since they differ
  from one run to the next by design, and so is the folder the variant ran in; a sweep's progress
  lines on stderr are left out, since how many come (one per tenth, from events at most once a
  second) depends on how fast the rollouts ran.
- L3 PF6.2 and PF6.3 "over the corpus": PF6's corpus above in the code suite; PF1's whole corpus
  both ways is marked ``slow`` (it runs every verb's processes three more times, about four minutes
  of processes, against the pull-request lane's five-minute budget).
- L4 PF6.3's first line in a pseudo-terminal "carries the same verdict word and sentence": with
  escapes removed and whitespace collapsed, the terminal's stdout begins with the piped first line,
  wherever the terminal wrapped it.
- L5 PF6.4's "no number is coloured": no digit is drawn in a colour; "only the 16 named colours, bold
  and dim": no SGR parameter outside 0, 1, 2, 22, 30 to 37, 39 and 90 to 97 (no background, no 256 or
  true colour, no italic, underline or reverse) on either stream; and since colour has four meanings,
  the only colours drawn are green, yellow and red, plain or bright (dim is the fourth meaning).
- L6 PF6.6's "wide tables fold as item 27 says": in a terminal of 80 and of 100 columns no line of a
  table, of pretty or of plain, is wider than the terminal; the cell table's condition column prints
  the axes (``task_id refund · tool_fail_rate 0.55``), never the config's JSON; a line longer than the
  terminal is allowed only when it carries a command to copy, which is never broken; plain's own
  wrapped lines continue with a hanging indent. Item 27's "a unit every cell repeats moves into the
  header" is read through the same width rule and is not pinned on its own.
- L7 PF6.7's "gone from the screen when the work ends": the stderr terminal's final screen, read by
  a terminal emulator, holds no progress line, and stdout's stream never held one.
- L8 Q20 and Q60's "imported only by": ``rich`` only by renderer modules (``poisson_prove._render_*``)
  and the app's modules (``poisson_prove._cli_app*``), ``textual`` only by the app's modules, and
  neither by ``cli.py``; importing ``poisson_prove.cli`` imports no Textual.
- L9 Rich and Textual are core dependencies with a floor each (section 5.5: the lowest working
  version measured by PF6, recorded in the build's log); the test checks a floor is declared and that
  the installed versions meet it, not the measurement.
- L10 On a terminal, plain wraps its own long lines (PF6.6), so "plain" there is read word for word, not
  byte for byte: PF6.1's plain cases read as ``--plain`` on the same terminal (``--plain`` taken out of
  a line that repeats the command as typed), and PF6.5's terminal run with Rich missing reads as the
  pipe, its progress aside (a terminal gets one rewritten line, a pipe a line per tenth).

**Frozen assertions this file's commit moves (section 14):** ``test_s0_scaffold::test_core_deps``
and ``test_a22_pandas3::test_v14_…`` (the core dependency list gains ``rich`` and ``textual``, Q20 and
Q60). The second is not in section 14's table; the session log names it as a finding.

**Lanes.** The code suite, but for PF1's corpus both ways (``slow``).
"""

from __future__ import annotations

import ast
import difflib
import json
import re
import shutil
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from packaging.requirements import Requirement
from packaging.version import Version
from pf6_support import (
    LOOK, LOOK_FIXTURES, MOCK, PLANTED_KEYS, ROLE_OF_WORD, ROOT, RUN_ID, SMALL_SPEC, SRC, blocker, prove,
    run_pty, sha256_of, shared_world, split_first_line, squash, strip_escapes, styled, styled_lines,
)

LOOK_SHA256 = "92e71488c2824c056252be9a7b340e7fc138d15359fbcb7431bcfc6fa267d85f"
BASE_SHA256 = "af0bb656e8a955befbdcdc031cce7c78d62248cd3b90adebf1e63d837298ce79"
PREFIX_SHA256 = "fca2017b1923ed0725d54fd8829e288f677b75a78b93eff12bd862ad07312697"
#: The two sections the design session added, each from its heading to the next one (or the end).
APP_SECTION_SHA256 = "2b18ab73f23aa95571ab971d548e464ed5dfeec1678e836e0b35eee5a1312049"
UI_SECTION_SHA256 = "f39b5a83b13e3a3378a994150a3187cc7e764d63e01365641b9409e9c6febfa7"
#: Section 5.2's codes and meanings, the look file's exit-code table's first column and the start of
#: its second.
EXIT_CODES = {
    "0": "done: the result is printed, whatever it says",
    "1": "refused: nothing was spent or written",
    "2": "the command line is wrong",
    "3": "stopped or failed after work started, or an unexpected failure",
    "4": "a check you asked for did not pass",
    "130": "interrupted",
}


# ---------- PF6.0 the look file ----------


def _look() -> str:
    assert LOOK.is_file(), f"{LOOK.relative_to(ROOT)} is missing"
    return LOOK.read_text(encoding="utf-8")


def _amended_base() -> str:
    base_path = LOOK_FIXTURES / "bfe802d.md"
    assert sha256_of(base_path) == BASE_SHA256
    text = base_path.read_text(encoding="utf-8")
    changes = json.loads((LOOK_FIXTURES / "changes.json").read_text(encoding="utf-8"))["changes"]
    assert [c["rule"] for c in changes] == [10, 16, 15]
    for change in changes:
        assert text.count(change["old"]) == 1, change["what"]
        text = text.replace(change["old"], change["new"])
    return text


def test_pf6_0_the_look_file_is_the_one_the_design_session_filed() -> None:
    """``docs/cli-look.md`` is Prove's canonical copy: its sha256 is the one filed with it (section
    13.3), so any later edit is a re-hash the spec names."""
    assert sha256_of(LOOK) == LOOK_SHA256


def test_pf6_0_its_rules_and_exit_code_table_are_the_base_with_the_three_changes() -> None:
    """Rules 1 to 16 and the exit-code table, up to the paragraph that closes it, equal byte for byte
    the base at ``bfe802d`` with rule 10's dollars, rule 16's two renderings and rule 15's options
    applied (reading L1); rule 16 has eleven bullets; there are sixteen rules."""
    amended = _amended_base()
    assert squash(amended) and len(amended.splitlines()) == 120
    look = _look()
    assert look.startswith(amended), "the file's rules or exit-code table differ from the amended base"
    import hashlib

    assert hashlib.sha256(amended.encode("utf-8")).hexdigest() == PREFIX_SHA256
    rules = re.findall(r"^(\d+)\. \*\*", amended, re.MULTILINE)
    assert rules == [str(i) for i in range(1, 17)], rules
    rule_16 = amended.split("\n16. ", 1)[1].split("\n## ", 1)[0]
    assert len(re.findall(r"^    - ", rule_16, re.MULTILINE)) == 11


def test_pf6_0_the_exit_code_table_has_section_5_2s_codes_and_meanings() -> None:
    table = _look().split("\n## Exit codes\n", 1)[1].split("\n## ", 1)[0]
    rows = dict(re.findall(r"^\| (\d+) \| (.+?) \|$", table, re.MULTILINE))
    assert sorted(rows, key=int) == sorted(EXIT_CODES, key=int), rows
    for code, meaning in EXIT_CODES.items():
        assert rows[code].startswith(meaning), (code, rows[code])


def test_pf6_0_the_new_sections_follow_the_files_old_end_and_no_dated_note_is_added() -> None:
    """After the exit-code table's closing paragraph come exactly the terminal app's and the static
    UI's sections, in that order, as filed; the file carries no dated note (Q62): no date anywhere
    and nothing between the title and the first paragraph but a blank line."""
    look = _look()
    rest = look[len(_amended_base()):]
    assert rest.startswith("\n## The terminal app\n"), rest[:60]
    assert re.findall(r"^## .+$", rest, re.MULTILINE) == ["## The terminal app", "## The static UI"]
    app = rest[1:].split("## The static UI", 1)[0]
    ui = "## The static UI" + rest.split("## The static UI", 1)[1]
    import hashlib

    assert hashlib.sha256(app.encode("utf-8")).hexdigest() == APP_SECTION_SHA256
    assert hashlib.sha256(ui.encode("utf-8")).hexdigest() == UI_SECTION_SHA256
    assert not re.search(r"\b\d{4}-\d\d-\d\d\b", look), re.findall(r"^.*\d{4}-\d\d-\d\d.*$", look, re.MULTILINE)
    lines = look.splitlines()
    assert lines[0] == "# The command-line look" and lines[1] == "" and not lines[2].startswith(">"), lines[:4]


# ---------- the corpus ----------


@dataclass(frozen=True)
class Call:
    name: str
    #: the command line, run from the variant's own folder; stores are relative to it
    argv: str
    code: int
    #: the verdict word the first stdout line carries, ``error`` for a refusal, ``json`` for --json
    word: str
    #: a ``note:`` line the call prints on stderr
    note: bool = False
    #: the word of the closing verdict line a sweep prints after its plan
    closing: str = ""


CORPUS: tuple[Call, ...] = (
    Call("runs", "--store stores/small runs", 0, "ok"),
    Call("runs-empty", "--store stores/empty runs", 0, "ok"),
    Call("diff-paired", "--store stores/small diff", 0, "trade|worse|safer|no significant change|too small to tell"),
    Call("diff-trade", "--store stores/standard diff", 0, "trade"),
    Call("diff-mixed", "--store stores/nokind diff --event fell", 0, "mixed"),
    Call("diff-no-change", "--store stores/mid diff", 0, "no significant change"),
    Call("diff-too-small", "--store stores/tiny diff", 0, "too small to tell"),
    Call("diff-note", "--store stores/small diff --method fisher_bh", 0, "trade|worse|safer|no significant change|too small to tell", note=True),
    Call("check-passed", "--store stores/mid check --event fell --fail-on worse", 0, "passed"),
    Call("check-failed", "--store stores/standard check --event fell --fail-on worse", 4, "failed"),
    Call("paired-under-cap", "--store stores/paired paired --declaration decl-under.toml --cap-check", 0, "under cap"),
    Call("paired-at-cap", "--store stores/paired paired --declaration decl-at.toml --cap-check", 4, "at cap"),
    Call("inspect", "--store stores/small inspect latest --event timeout --limit 3", 0, "ok"),
    Call("sweep-plan", "--store stores/plan sweep small.toml --dry-run --max-mde 1", 0, "plan"),
    Call("sweep-done", "--store stores/done sweep small.toml --yes --max-mde 1", 0, "plan", closing="done"),
    Call("sweep-stopped", "--store stores/stopped sweep small.toml --yes --max-mde 1 --max-rollouts 10", 3, "plan", closing="stopped"),
    Call("refused", "--store stores/nowhere runs", 1, "error"),
    Call("report", "--store stores/standard report --x cell --out out-report", 0, "ok"),
    Call("init", "init --out spec.toml", 0, "ok"),
    Call("ui", "--store stores/ui ui", 0, "ok"),
    Call("json-runs", "--store stores/small runs --json", 0, "json"),
    Call("json-diff", "--store stores/standard diff --json", 0, "json"),
    Call("json-check", "--store stores/standard check --event fell --fail-on worse --json", 4, "json"),
    Call("json-plan", "--store stores/plan sweep small.toml --dry-run --max-mde 1 --json", 0, "json"),
    Call("json-inspect", "--store stores/small inspect latest --event timeout --limit 3 --json", 0, "json"),
)
CALLS = {c.name: c for c in CORPUS}
VARIANTS = ("pipe", "pipe-plain", "pipe-norich", "pty", "pty-norich")
COLS, ROWS = 100, 40
#: The 16 named colours' green, yellow and red, plain and bright: the only colours with a meaning.
MEANING_COLOURS = frozenset({1, 2, 3, 9, 10, 11})


def _write_stores(stores: Path) -> None:
    """The corpus's stores, written once and copied into each variant's folder."""
    from pf6_support import cli
    from test_pf1_look import PAIRED_DECLARATION, write_paired_store
    from test_pf4_surfaces import MID, STANDARD_A, STANDARD_B, _arm, _declared, _pair

    failures = _declared(failures=("fell",))
    # A condition where nothing happens, so a comparison given no event infers ``fell``.
    quiet = {"quiet": _arm(0, 120)}
    small = stores / "small"
    spec = stores.parent / "small.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    for argv in (["sweep", str(spec), "--yes", "--max-mde", "1"],
                 ["sweep", str(spec), "--yes", "--max-mde", "1", "--target", f"{MOCK}:rollout_patched", "--pair-with", "latest"]):
        result = cli("--store", small, *argv)
        assert result.code == 0, result
    _pair(stores / "standard", {**STANDARD_A, **quiet}, {**STANDARD_B, **quiet}, declared_a=failures, declared_b=failures)
    _pair(stores / "nokind", {**STANDARD_A, **quiet}, {**STANDARD_B, **quiet})
    env = {"max_mde_accepted": 0.3}
    _pair(stores / "mid", {**MID, **quiet}, {**MID, **quiet}, environment_a=env, environment_b=env, declared_a=failures, declared_b=failures)
    _pair(stores / "tiny", {"c": _arm(1, 4), "d": _arm(2, 4), "q": _arm(0, 8)}, {"c": _arm(3, 4), "d": _arm(2, 4), "q": _arm(0, 8)},
          declared_a=failures, declared_b=failures)
    write_paired_store(stores / "paired")
    (stores.parent / "decl-under.toml").write_text(PAIRED_DECLARATION.format(cap="token_cap = 1000000000\n"), encoding="utf-8")
    (stores.parent / "decl-at.toml").write_text(PAIRED_DECLARATION.format(cap="token_cap = 1000\n"), encoding="utf-8")
    (stores / "empty").mkdir()
    shutil.copytree(small, stores / "ui")


def _build_template(base: Path) -> dict[str, Any]:
    """The corpus's folder: its stores and the files its calls name, copied for each variant."""
    (base / "stores").mkdir()
    _write_stores(base / "stores")
    return {}


@pytest.fixture(scope="session")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return shared_world(tmp_path_factory, "pretty-template", _build_template)[0]


#: The piped variants run every call of the corpus in one process each, through the command's own
#: entry point with streams that are not terminals: what a pipe gives it, at one import's cost.
_PIPED = r"""
import json, os, sys
from io import StringIO
if os.environ.get("PF6_WITHOUT_RICH"):
    sys.modules["rich"] = None
from poisson_prove import cli
out = []
for job in json.loads(sys.stdin.read()):
    os.chdir(job["cwd"])
    o, e = StringIO(), StringIO()
    code = cli.main(job["argv"], stdout=o, stderr=e, stdin=StringIO())
    texts = [o.getvalue(), e.getvalue()]
    for where in sorted({job["cwd"], os.path.realpath(job["cwd"])}, key=len, reverse=True):
        texts = [text.replace(where, "<folder>") for text in texts]
    out.append({"code": code, "out": texts[0], "err": texts[1]})
sys.stdout.write(json.dumps(out))
"""


def _piped(variant: str, folder: Path, home: Path) -> dict[str, dict[str, Any]]:
    import subprocess

    from pf6_support import child_env

    jobs = [{"cwd": str(folder), "argv": (["--plain"] if variant == "pipe-plain" else []) + c.argv.split()} for c in CORPUS]
    extra = {"PF6_WITHOUT_RICH": "1"} if variant == "pipe-norich" else {}
    done = subprocess.run([sys.executable, "-c", _PIPED], input=json.dumps(jobs), cwd=folder, env=child_env(home, **extra),
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    return {c.name: r for c, r in zip(CORPUS, json.loads(done.stdout))}


def _on_terminals(call: Call, folder: Path, home: Path, paths: tuple[Path, ...]) -> dict[str, Any]:
    t = run_pty(call.argv.split(), home=home, cwd=folder, paths=paths, cols=COLS, rows=ROWS, stdin="null", stdout="pty", stderr="own")
    out, err = t.out, t.err
    for where in sorted({str(folder), str(folder.resolve())}, key=len, reverse=True):
        out, err = out.replace(where, "<folder>"), err.replace(where, "<folder>")
    return {"code": t.code, "out": out, "err": err}


def _build_corpus(base: Path, template: Path) -> dict[str, Any]:
    home = base / "home"
    home.mkdir()
    norich = blocker(base / "norich", "rich")
    folders = {v: shutil.copytree(template, base / v) for v in VARIANTS}
    out: dict[str, Any] = {v: {} for v in VARIANTS}
    with ThreadPoolExecutor(max_workers=8) as pool:
        piped = {v: pool.submit(_piped, v, folders[v], home) for v in VARIANTS if v.startswith("pipe")}
        shown = [(c.name, v, pool.submit(_on_terminals, c, folders[v], home, (norich,) if v == "pty-norich" else ()))
                 for v in VARIANTS if v.startswith("pty") for c in CORPUS if not (c.word == "json" and v == "pty-norich")]
        for v, future in piped.items():
            out[v] = future.result()
        for name, v, future in shown:
            out[v][name] = future.result()
    return out


@pytest.fixture(scope="session")
def corpus(tmp_path_factory: pytest.TempPathFactory, template: Path) -> dict[str, dict[str, dict[str, Any]]]:
    return shared_world(tmp_path_factory, "pretty-corpus", lambda base: _build_corpus(base, template))[1]


def _same_bytes(text: str) -> str:
    """Text with what differs between two runs of the same sweep by design replaced (reading L2):
    run ids, UTC times and durations, in text and in JSON."""
    text = RUN_ID.sub("<run-id>", text)
    text = re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", "<time>", text)
    text = re.sub(r'("(?:wall_time|elapsed|seconds)\w*": )[-0-9.eE+]+', r"\1<duration>", text)
    return re.sub(r"\b\d+(?:\.\d+)? (?:s|min|h)\b(?: \d+(?:\.\d+)? s)?", "<duration>", text)


def _without_progress(text: str) -> str:
    """A stream without its progress, which a terminal gets as one rewritten line and a pipe as a
    line per tenth (section 5.5)."""
    parts = re.split(r"[\r\n]", text)
    return "\n".join(p for p in parts if not re.fullmatch(r"\s*[\d,]+/[\d,]+\s*", p))


def _closing_word(text: str) -> str:
    """The word of the last verdict line, the one a sweep ends with after its plan."""
    words = [m.group(1) for m in (re.match(r"^([a-z][a-z ]*?)  \S", line) for line in text.splitlines()) if m and m.group(1) in ROLE_OF_WORD]
    return words[-1] if words else ""


def test_pf6_corpus_ran_as_designed_on_pipes(corpus: dict[str, dict[str, dict[str, Any]]]) -> None:
    """The corpus is what it says it is: each call's exit code and first stdout word as listed, so
    the tests below read every verdict word section 5.5 gives a colour."""
    for call in CORPUS:
        r = corpus["pipe"][call.name]
        assert r["code"] == call.code, (call.name, r["code"], r["err"][-500:])
        if call.word == "json":
            json.loads(r["out"])
        elif call.word == "error":
            assert r["out"] == "" and r["err"].startswith("error: "), (call.name, r)
        else:
            word, _ = split_first_line(r["out"])
            assert re.fullmatch(call.word, word), (call.name, word)
        assert ("\nnote: " in "\n" + r["err"]) is call.note or not call.note, (call.name, r["err"])
        if call.closing:
            assert _closing_word(r["out"]) == call.closing, (call.name, r["out"][-300:])
    words = {split_first_line(corpus["pipe"][c.name]["out"])[0] for c in CORPUS if c.word not in ("json", "error")} | {c.closing for c in CORPUS if c.closing}
    assert {"ok", "done", "passed", "under cap", "stopped", "too small to tell", "no significant change", "failed", "at cap", "plan", "trade", "mixed"} <= words


# ---------- PF6.1 pretty only under section 5.5's conditions ----------

#: (case, how the process runs, whether it draws pretty). Each case changes one condition from the
#: first. ``stdout``/``stderr``: ``pty`` a terminal, ``pipe`` not; ``env`` and ``argv`` as given.
SWITCH_CASES: tuple[tuple[str, dict[str, Any], bool], ...] = (
    ("both streams terminals, nothing set", {}, True),
    ("NO_COLOR set but empty", {"env": {"NO_COLOR": ""}}, True),
    ("stdout piped", {"stdout": "pipe"}, False),
    ("stderr piped", {"stderr": "pipe"}, False),
    ("NO_COLOR set", {"env": {"NO_COLOR": "1"}}, False),
    ("CI set", {"env": {"CI": "true"}}, False),
    ("CI set but empty", {"env": {"CI": ""}}, False),
    ("TERM dumb", {"env": {"TERM": "dumb"}}, False),
    ("stdout not UTF-8", {"env": {"PYTHONIOENCODING": "latin-1", "LANG": "C", "LC_ALL": "C"}}, False),
    ("--json", {"argv": ["--json"]}, False),
    ("--plain before the verb", {"before": ["--plain"]}, False),
    ("--plain after the verb", {"argv": ["--plain"]}, False),
)
SWITCH_ARGV = ["--store", "stores/standard", "diff"]


@pytest.fixture
def switch_folder(template: Path, tmp_path: Path) -> Path:
    return shutil.copytree(template, tmp_path / "corpus")


@pytest.mark.parametrize("case,how,pretty", SWITCH_CASES, ids=[c[0] for c in SWITCH_CASES])
def test_pf6_1_pretty_runs_only_when_every_condition_holds_and_each_alone_turns_it_off(
    case: str, how: dict[str, Any], pretty: bool, switch_folder: Path, tmp_path: Path
) -> None:
    """Section 5.5's switch, each condition alone: pretty when stdout and stderr are both terminals,
    ``NO_COLOR`` unset or empty, ``CI`` unset, ``TERM`` not ``dumb``, stdout UTF-8, no ``--json`` and no
    ``--plain`` (before or after the verb); otherwise plain, which on a terminal reads word for word as
    what ``--plain`` prints on the same terminal."""
    home = tmp_path / "home"
    home.mkdir()
    argv = [*how.get("before", []), *SWITCH_ARGV, *how.get("argv", [])]
    env = how.get("env", {})
    stdout, stderr = how.get("stdout", "pty"), how.get("stderr", "own")
    run = run_pty(argv, home=home, cwd=switch_folder, stdin="null", stdout=stdout, stderr=stderr, cols=COLS, rows=ROWS, **env)
    assert run.code == 0, (case, run.err[-800:])
    escapes = "\x1b[" in run.out or "\x1b[" in run.err
    assert escapes is pretty, (case, run.out[:300])
    if not pretty and stdout == "pty" and "--json" not in argv:
        plain = run_pty(["--plain", *argv], home=home, cwd=switch_folder, stdin="null", stdout=stdout, stderr=stderr, cols=COLS, rows=ROWS, **env)
        # A line may repeat the command as typed, so ``--plain`` is taken out of it, and the terminal
        # may then wrap it at another place: the two read the same, word for word.
        for got, want in ((run.out, plain.out), (run.err, plain.err)):
            got, want = squash(got), squash(want.replace(" --plain", ""))
            assert got == want, (case, "".join(difflib.unified_diff(want.split(" "), got.split(" "), "--plain", "as run", lineterm=""))[:3000])


# ---------- PF6.2 piped, pretty and plain are the same bytes ----------


@pytest.mark.parametrize("other", ["pipe-plain", "pipe-norich"])
def test_pf6_2_piped_every_call_prints_the_same_bytes_with_plain_asked_for_or_rich_missing(
    other: str, corpus: dict[str, dict[str, dict[str, Any]]]
) -> None:
    """Reading L2: on pipes the build prints, for every call of the corpus, the same stdout, stderr
    and exit code as with ``--plain`` and as with Rich unimportable; a sweep's progress lines are left
    out of stderr, since how many come depends on how fast the rollouts ran (one per tenth, from events
    that come at most once a second)."""
    for call in CORPUS:
        if call.name not in corpus[other]:
            continue
        a, b = corpus["pipe"][call.name], corpus[other][call.name]
        assert a["code"] == b["code"], (call.name, other)
        assert _same_bytes(a["out"]) == _same_bytes(b["out"]), (call.name, other)
        assert _without_progress(_same_bytes(a["err"])) == _without_progress(_same_bytes(b["err"])), (call.name, other)


# ---------- PF6.3 in a terminal, the same verdict line, exit code and JSON ----------


def test_pf6_3_in_a_terminal_the_first_line_exit_code_and_json_are_the_pipes(corpus: dict[str, dict[str, dict[str, Any]]]) -> None:
    """Reading L4: with escapes removed, each call's terminal stdout begins with the piped first
    line (its verdict word and sentence), the exit code is the same, a refusal's ``error:`` line is the
    same, and ``--json`` is the same document."""
    for call in CORPUS:
        piped, shown = corpus["pipe"][call.name], corpus["pty"][call.name]
        assert shown["code"] == piped["code"], call.name
        out = strip_escapes(shown["out"])
        if call.word == "json":
            assert json.loads(_same_bytes(out)) == json.loads(_same_bytes(piped["out"])), call.name
            assert "\x1b" not in shown["out"], call.name
            continue
        if call.word == "error":
            assert out.strip() == "", call.name
            assert squash(strip_escapes(shown["err"])).startswith(squash(piped["err"].splitlines()[0])), call.name
            continue
        first = piped["out"].splitlines()[0]
        assert squash(_same_bytes(out)).startswith(squash(_same_bytes(first))), (call.name, first, out[:300])


# ---------- PF6.4 colour has four meanings ----------


def _first_word_role(text: str) -> tuple[str, str]:
    for line in styled_lines(text):
        chars = "".join(c.char for c in line)
        if not chars.strip():
            continue
        word, _ = split_first_line(chars)
        from pf6_support import role_of

        roles = {role_of(c) for c in line[: len(word)] if c.char != " "}
        assert len(roles) == 1, (word, roles)
        return word, roles.pop()
    raise AssertionError("no line")


def test_pf6_4_every_verdict_word_takes_its_meanings_colour_and_no_number_is_coloured(corpus: dict[str, dict[str, dict[str, Any]]]) -> None:
    """Section 5.5's four meanings on a terminal: green for ``ok``, ``done``, ``passed``, ``under cap``;
    yellow for ``stopped``, ``too small to tell``, ``no significant change`` and ``note:``; red for
    ``error:``, ``failed`` and ``at cap``; bold with no colour for ``plan``, ``worse``, ``safer``,
    ``trade`` and the direction words (reading A9); no digit coloured; only the 16 named colours, bold
    and dim (reading L5), on stdout and on stderr."""
    from pf6_support import role_of

    for call in CORPUS:
        shown = corpus["pty"][call.name]
        for stream in ("out", "err"):
            _, odd = styled(shown[stream])
            assert odd == [], (call.name, stream, odd[:5])
            for line in styled_lines(shown[stream]):
                coloured_digits = [c.char for c in line if c.char.isdigit() and c.fg is not None]
                assert coloured_digits == [], (call.name, stream, "".join(c.char for c in line))
                other = {c.fg for c in line if c.fg is not None and c.fg not in MEANING_COLOURS}
                assert other == set(), (call.name, stream, "a colour with no meaning", other, "".join(c.char for c in line))
                text = "".join(c.char for c in line)
                for prefix, role in (("note:", "Y"), ("error:", "R")):
                    if text.startswith(prefix):
                        assert {role_of(c) for c in line[: len(prefix)]} == {role}, (call.name, text)
        if call.word in ("json", "error"):
            continue
        word, role = _first_word_role(shown["out"])
        assert role == ROLE_OF_WORD[word], (call.name, word, role)
        if call.closing:
            (line,) = [line for line in styled_lines(shown["out"]) if "".join(c.char for c in line).startswith(call.closing + "  ")][-1:]
            assert {role_of(c) for c in line[: len(call.closing)]} == {ROLE_OF_WORD[call.closing]}, (call.name, call.closing)


# ---------- PF6.5 Rich missing ----------


def test_pf6_5_with_rich_missing_a_terminal_gets_the_plain_rendering_and_nothing_is_said(corpus: dict[str, dict[str, dict[str, Any]]]) -> None:
    """With Rich unimportable, every call on a terminal prints the plain rendering, no escape on either
    stream, the pipe's facts in the pipe's order (only plain's own wrapping differs, PF6.6) and the
    pipe's exit code, and nothing more on stderr than the pipe has, so nothing is said about Rich; on
    pipes, PF6.2."""
    for call in CORPUS:
        if call.word == "json":
            continue
        a, piped = corpus["pty-norich"][call.name], corpus["pipe"][call.name]
        assert a["code"] == piped["code"], call.name
        assert "\x1b" not in a["out"] and "\x1b" not in a["err"], call.name
        assert squash(_same_bytes(a["out"])) == squash(_same_bytes(piped["out"])), call.name
        assert squash(_without_progress(_same_bytes(a["err"]))) == squash(_without_progress(_same_bytes(piped["err"]))), call.name


# ---------- PF6.6 widths ----------

WIDTH_CALLS = ("diff-trade", "diff-paired", "runs", "inspect", "sweep-plan", "sweep-done", "check-failed", "report")


def _commands(piped: dict[str, Any]) -> list[str]:
    """The commands a call prints for the user to copy: its ``next:`` lines and the lines of a
    reproduce block (``inspect``'s, which name ``poisson_prove`` or ``rollout(``)."""
    found = []
    for line in (piped["out"] + "\n" + piped["err"]).splitlines():
        s = line.strip()
        if s.startswith("next: "):
            found.append(s.removeprefix("next: "))
        elif s.startswith(("from ", "import ", "rollout(", "poisson-prove ")):
            found.append(s)
    return found


@pytest.mark.parametrize("cols", [80, 100])
@pytest.mark.parametrize("rendering", ["pretty", "plain"])
def test_pf6_6_tables_fit_the_terminal_and_no_command_to_copy_is_broken(
    cols: int, rendering: str, switch_folder: Path, corpus: dict[str, dict[str, dict[str, Any]]], tmp_path: Path
) -> None:
    """Reading L6, at 80 and 100 columns: no line wider than the terminal unless it carries a command
    to copy; every command the call prints appears whole on one line; pretty's cell table prints the
    axes, never the config's JSON; plain's own long lines wrap with a hanging indent and read, joined,
    as the piped line."""
    home = tmp_path / "home"
    home.mkdir()
    for name in WIDTH_CALLS:
        call = CALLS[name]
        folder = tmp_path / name
        shutil.copytree(switch_folder, folder)
        argv = call.argv.split() if rendering == "pretty" else ["--plain", *call.argv.split()]
        run = run_pty(argv, home=home, cwd=folder, stdin="null", stdout="pty", stderr="own", cols=cols, rows=ROWS)
        assert run.code == call.code, (name, run.err[-500:])
        piped = corpus["pipe"][name]
        commands = _commands(piped)
        for stream in ("out", "err"):
            text = _same_bytes(strip_escapes(getattr(run, stream)))
            for line in text.splitlines():
                if len(line) > cols:
                    assert any(_same_bytes(c) in line for c in commands), (name, rendering, cols, line)
            for command in commands:
                assert _same_bytes(command) in _same_bytes(strip_escapes(run.out + "\n" + run.err)), (name, rendering, command)
        if rendering == "pretty" and name == "diff-paired":
            # the cell table's condition is its axes, never the config's JSON, one field per line at most
            shown = strip_escapes(run.out)
            assert '{"' not in shown, (name, cols)
            for axis in ("task_id refund", "tool_fail_rate 0.55"):
                assert axis in shown, (name, cols, axis)
        if rendering == "plain":
            shown = strip_escapes(run.out).splitlines()
            i = 0
            for want in piped["out"].splitlines():
                got = [shown[i]]
                i += 1
                while squash(" ".join(got)) != squash(want) and i < len(shown) and len(squash(" ".join(got))) < len(squash(want)):
                    assert shown[i].startswith(" "), (name, cols, want, shown[i])
                    got.append(shown[i])
                    i += 1
                assert _same_bytes(squash(" ".join(got))) == _same_bytes(squash(want)), (name, cols, want, got)


# ---------- PF6.7 progress ----------

SLOW_TARGET = '''\
import time

from poisson_prove.examples import mock_agent


def rollout(cfg, seed):
    time.sleep(0.015)
    return mock_agent.rollout(cfg, seed)
'''
PROGRESS = re.compile(r"\d[\d,]*\s*(?:/|of)\s*\d[\d,]*")


def test_pf6_7_pretty_progress_is_on_stderr_and_gone_from_the_screen_when_the_sweep_ends(tmp_path: Path) -> None:
    """Reading L7: a pretty sweep long enough to report progress draws it on stderr's terminal, never
    on stdout, and the terminal's final screen holds no progress line; the result is on stdout."""
    home = tmp_path / "home"
    home.mkdir()
    (tmp_path / "pf6_slow.py").write_text(SLOW_TARGET, encoding="utf-8")
    (tmp_path / "small.toml").write_text(SMALL_SPEC.replace(f'"{MOCK}:rollout"', '"pf6_slow:rollout"'), encoding="utf-8")
    run = run_pty(["sweep", "small.toml", "--yes", "--max-mde", "1"], home=home, cwd=tmp_path, paths=(tmp_path,),
                  stdin="null", stdout="pty", stderr="own", cols=COLS, rows=ROWS)
    assert run.code == 0, run.err[-800:]
    assert "\x1b[" in run.out, "not pretty"
    assert PROGRESS.search(strip_escapes(run.err)), "no progress was drawn"
    # stdout holds no live line: nothing redrawn in place, and no line that is a count of the work
    assert "\r" not in run.out.replace("\r\n", "\n") and not re.search(r"\x1b\[\d*[AK]|\x1b\[2K", run.out), run.out[:300]
    assert not [line for line in strip_escapes(run.out).splitlines() if re.search(r"\d[\d,]*/\d[\d,]*", line)], run.out
    left = [line for line in run.err_screen if PROGRESS.search(line)]
    assert left == [], left
    assert _closing_word(strip_escapes(run.out)) == "done", strip_escapes(run.out)[-400:]


# ---------- Q20, Q60: where Rich and Textual are imported; the dependencies ----------


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def test_pf6_rich_and_textual_are_imported_only_by_the_renderer_and_the_app() -> None:
    """Reading L8 (Q20, Q60): ``rich`` only in ``poisson_prove._render_*`` and ``poisson_prove._cli_app*``,
    ``textual`` only in ``poisson_prove._cli_app*``; at least one module imports each; ``cli.py`` neither."""
    users: dict[str, set[str]] = {"rich": set(), "textual": set()}
    for path in sorted(SRC.rglob("*.py")):
        name = _module_name(path)
        for lib in _imports(path) & set(users):
            users[lib].add(name)
    assert users["rich"] and users["textual"], users
    assert all(m.startswith(("poisson_prove._render_", "poisson_prove._cli_app")) for m in users["rich"]), users["rich"]
    assert all(m.startswith("poisson_prove._cli_app") for m in users["textual"]), users["textual"]
    assert "poisson_prove.cli" not in users["rich"] | users["textual"]


def test_pf6_importing_the_command_line_imports_no_textual(tmp_path: Path) -> None:
    """Q60: Textual is imported by the app's module only, when the app opens, so the plain
    commands do not pay for it."""
    home = tmp_path / "home"
    home.mkdir()
    import subprocess

    from pf6_support import child_env

    done = subprocess.run([sys.executable, "-c", "import sys, poisson_prove.cli; print('textual' in sys.modules)"],
                          env=child_env(home), capture_output=True, text=True, timeout=60)
    assert done.returncode == 0 and done.stdout.strip() == "False", (done.stdout, done.stderr)


def test_pf6_rich_and_textual_are_core_dependencies_with_a_floor_the_install_meets() -> None:
    """Q20 and Q60 with reading L9: both in ``[project] dependencies``, each with a ``>=`` floor, which
    the installed versions meet; the terminal emulator the tests read screens with is in ``[dev]``."""
    from importlib.metadata import version

    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    core = {Requirement(d).name.lower(): Requirement(d) for d in data["project"]["dependencies"]}
    for name in ("rich", "textual"):
        assert name in core, sorted(core)
        floors = [s for s in core[name].specifier if s.operator == ">="]
        assert floors, (name, str(core[name].specifier))
        assert Version(version(name)) in core[name].specifier, (name, version(name), str(core[name].specifier))
    dev = {Requirement(d).name.lower() for d in data["project"]["optional-dependencies"]["dev"]}
    assert "pyte" in dev, sorted(dev)


# ---------- PF6.2 and PF6.3 over PF1's whole corpus (slow) ----------


@pytest.mark.slow
def test_pf6_2_and_6_3_over_pf1s_corpus_both_ways(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Reading L3: PF1's corpus over one PF1 world, copied for each variant (its sweeps draw new
    seeds, so a world built twice is two different worlds), each invocation run on pipes as PF1 runs
    it, with ``--plain``, with Rich unimportable, and with stdout and stderr on terminals: the piped
    three print the same bytes (PF6.2), and on terminals the first line, the exit code and ``--json``
    are the pipe's (PF6.3). Invocations that would ask a question or open the app on a terminal are
    left out of the terminal run, each named: no arguments (the app, PF6.8) and a sweep that waits
    for its ``[y/N]``. Each variant's folder, the sweeps' run ids, times and durations, and the
    sweeps' progress lines are replaced or left out before comparing (L2)."""
    import dataclasses

    import test_pf1_look as pf1

    interactive = {"usage-no-arguments", "refuse-stdin-not-a-terminal"}
    built = pf1.world.__wrapped__(tmp_path_factory)

    def copied(variant: str) -> Any:
        base = tmp_path_factory.mktemp(f"pf1-{variant}")
        shutil.copytree(built.base, base, dirs_exist_ok=True, symlinks=True)

        def moved(path: Path) -> Path:
            return base / path.relative_to(built.base)

        return dataclasses.replace(built, base=base, home=moved(built.home), store=moved(built.store), paired_store=moved(built.paired_store),
                                   folders={k: moved(v) for k, v in built.folders.items()})

    def masked(text: str, base: Path) -> str:
        for where in sorted({str(base), str(base.resolve())}, key=len, reverse=True):
            text = text.replace(where, "<base>")
        return text

    results: dict[str, dict[str, Any]] = {}
    for variant in ("pipe", "pipe-plain", "pipe-norich", "pty"):
        world = copied(variant)
        norich = blocker(world.base / "norich", "rich")

        def one(call: Any, variant: str = variant, world: Any = world, norich: Path = norich) -> tuple[str, dict[str, Any]]:
            argv = [world.fill(word) for word in call.argv.split()]
            cwd = world.folders[call.cwd] if call.cwd else world.base
            paths = tuple(world.folders[p] for p in call.paths)
            if variant == "pipe-plain" and call.kind != "usage":
                argv = ["--plain", *argv]
            if variant == "pipe-norich":
                paths = (*paths, norich)
            if variant == "pty":
                if call.name in interactive:
                    return call.name, {}
                r: Any = run_pty(argv, home=world.home, cwd=cwd, paths=paths, stdin="null", stdout="pty", stderr="own", cols=COLS, rows=ROWS, timeout=300)
            else:
                r = prove(argv, home=world.home, cwd=cwd, paths=paths, timeout=300)
            return call.name, {"code": r.code, "out": masked(r.out, world.base), "err": masked(r.err, world.base)}

        with ThreadPoolExecutor(max_workers=8) as pool:
            results[variant] = dict(pool.map(one, pf1.CORPUS))

    def same(text: str) -> str:
        return _without_progress(_same_bytes(text))

    for call in pf1.CORPUS:
        a = results["pipe"][call.name]
        for other in ("pipe-plain", "pipe-norich"):
            if other == "pipe-plain" and call.kind == "usage":
                continue
            b = results[other][call.name]
            assert (a["code"], same(a["out"]), same(a["err"])) == (b["code"], same(b["out"]), same(b["err"])), (call.name, other)
        t = results["pty"][call.name]
        if not t:
            continue
        assert t["code"] == a["code"], call.name
        if call.kind == "json":
            assert json.loads(same(strip_escapes(t["out"]))) == json.loads(same(a["out"])), call.name
        elif a["out"]:
            assert squash(same(strip_escapes(t["out"]))).startswith(squash(same(a["out"].splitlines()[0]))), call.name


def test_pf6_planted_keys_are_never_printed(corpus: dict[str, dict[str, dict[str, Any]]]) -> None:
    """Rule 8 on both renderings: no planted key's value reaches any stream of any call."""
    for variant, calls in corpus.items():
        for name, r in calls.items():
            for value in PLANTED_KEYS.values():
                assert value not in r["out"] and value not in r["err"], (variant, name)
