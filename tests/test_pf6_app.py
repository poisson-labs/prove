"""PF6, the terminal app: the frozen tests (the code suite).

Written from what the terminal app must do (what a face may do, and that the app saves the
comparison it shows), the invariants PF6.8 to PF6.15, the app's screen designs (``screens/*.md``,
their grids at 80 × 24 and 120 × 40 with colour masks), ``views.md`` (where the chart links land),
the look file's terminal-app section, PF12's frozen view field names (``test_pf12_ui.VIEW_FIELDS``)
and the test standard. The implementation is written against this file and does not edit it.

**How the app is reached.** Two ways, as a user reaches it. Textual's test pilot runs the app in
this process, presses keys and reads the screen cell by cell, with each cell's colour role (``V``
reverse, ``G`` green, ``Y`` yellow, ``R`` red, ``B`` bold, ``D`` dim), as the design's masks mark them.
A pseudo-terminal runs ``python -m poisson_prove`` with no arguments, as a shell does, for what
happens before the app opens and after it leaves (PF6.8, PF6.15, Ctrl-C in a sweep). What the core
returned to the app is recorded by wrapping the operations on ``poisson_prove.core`` (faces call
``core.<op>``), so a test holds each screen to the object it renders and never to a number of its
own.

**The stores.** ``old``: the committed 0.0.1 store (its quickstart pair, compared and saved, so the
same records every time: the snapshots read it). ``qs``: the quickstart as a stranger runs it with
this build (``init --example``, two sweeps of ``prove.toml``, ``diff --save``, ``ui``); its counts change
from one sweep to the next, so no test pins them, only words and structure. ``small``: a small paired
pair of the mock agent, compared in well under a second, no comparison saved and no UI built.
``stats``: hand-written pairs, one store each, for the facts the statistics give the verdict
and condition screens. Each is built once per session; every test that opens the app opens it on its
own copy, since the app writes into the store it shows.

**Readings, named here** (where the invariants leave a choice, the one this file makes).

- A1 The app's entry point is ``poisson_prove._cli_app.ProveApp``, a Textual ``App`` built as
  ``ProveApp(store=None)``: ``store`` is the ``--store`` value as typed, ``None`` when none was given
  (the store is then found as every verb finds it, from the folder the app runs in); ``sweep`` reads
  that folder's ``prove.toml``. Its exit code is Textual's ``return_code``; ``poisson-prove`` with no
  verb on a terminal returns it.
- A2 Each screen's header begins ``poisson-prove · <title>``: ``home``, ``runs``, ``run``, ``sweep``,
  ``compare``, ``comparison`` (the verdict screen, as the design draws it), ``conditions``, ``condition``,
  ``episodes``, ``could not detect``, ``help``.
- A3 The keys that reach each screen from home are the design's: ``r`` runs, ``Enter`` on a run its
  screen, ``Enter`` there its focused condition's episodes, ``s`` sweep, ``c`` compare, ``Enter`` in the
  picker the verdict (``previous`` and ``latest`` chosen), ``Enter`` on a home row that is a saved
  comparison its verdict, ``t`` conditions, ``Enter`` there a condition, ``d`` could not detect, ``?`` help.
- A4 What each screen renders: the core's ``view(store, address)`` at the addresses ``views.md`` gives,
  home's address being ``home``; the episodes of a run that is in no saved comparison, which
  has no page, the core's ``episodes`` page for that run, event and
  condition; the sweep screen renders the core's ``plan`` result, then the events ``start`` reports
  and its result; the verdict and conditions screens the two halves of the ``comparison`` view, or,
  when the comparison could not be saved, of the ``compare`` result itself.
- A5 Home's view carries the fields ``screens/01-home.md`` names (``HOME_FIELDS``, frozen here as PF12
  froze the seven static views'), each item also its ``limit`` (a saved comparison's verdict limit, null
  for a run), so home's row can carry it beside ``no significant change`` (PF4.40); ``plan``'s and
  ``progress``'s are the core's ``Plan`` and events, which PF5 froze.
- A6 "Shows every fact that view carries", at 120 columns and 60 rows with the screen's table read
  through to its end (at 80 columns columns drop by design and are checked by their headers):
  every scalar of the view's document is on the screen, a number as rule 10 prints it (a share 0.448 as
  ``0.448``, a level 0.975 as ``97.5%``, 1746 as ``1,746``), a hash by its first 12 hex, a UTC time as
  written, to the minute or as its clock time, a code (``mcnemar_bh``) verbatim or by its words, any other
  string verbatim (case, line breaks and dashes aside); a comparison's name may be written in the app's
  short form, and a name in a table may be cut in the middle with ``…`` as the look file allows. Not checked
  as text: the schema and the view's kind (the screen itself), a condition's hash (its axes), an
  address (its link or the row that opens it, PF6.11), a chart's drawing, and a value's
  ``_note`` beside a value that is not null (a note gives a null value's reason, PF1.11). A value that
  is not a whole number is shown only by a number with two decimals or more, a ``2.3e-08`` form or a
  percentage, so a ``0`` or a ``1`` elsewhere never shows it; a word of three letters or fewer is matched
  as a word. A table's rows are checked row by row, each row's columns the design gives that table at
  120 columns (``TABLE_COLUMNS`` in ``pf6_support``) on one line; a row's other facts are on the screen
  the row opens. A true or false fact (``could_tell``) is not read as text.
- A7 The compare the picker starts is ``diff`` of the two chosen runs with no options (the default test
  for the pair, the events declared or inferred, ``q`` 0.05), and the app saves it: the verdict
  screen's first line is ``diff``'s, word and sentence.
- A8 PF6.11's "a link to that view's chart anchor" is the chart's own page at the address ``views.md``
  gives; Enter on a focused link calls ``webbrowser`` once with
  ``file://<the store>/.poisson/ui/<address>``, and ``y`` copies that same address (Textual's
  ``copy_to_clipboard``).
- A9 PF4.20's direction words (``mixed``, ``higher``, ``lower``) and a row's ``unchanged`` are results, bold
  with no colour.
- A10 ``NO_COLOR`` set and not empty keeps the app and drops its colours (green, yellow, red); bold, dim
  and reverse stay; set but empty it changes nothing, as the CLI's switch reads it. Textual itself
  takes an empty ``NO_COLOR`` as set, and greys its colours when it is not drawing in the terminal's
  own colours, so the app reads the switch as the CLI does and draws in the 16 named colours.
- A11 A refusal inside the app is one ``error:`` line on the message line, the sentence the plain
  command prints for the same request (``runs`` for a store, ``diff`` for a pair, ``sweep`` for ``prove.toml``,
  which refuses at the plan before it asks), with that command's ``next`` commands on the screen; when the
  sentence is wider than the window the message line begins it and the whole sentence is on the screen;
  the app stays open and ``q`` exits 0. Choosing a partial run in the picker is the app's own refusal (the design's ``05-compare``), naming
  the run and saying it is partial.
- A12 The snapshots (PF6.14) are eight screens of the 0.0.1 quickstart pair, each saved as its rows and
  its colour roles, with the saved comparison's id, the times it was saved and the running version
  replaced; they are written by the one documented command PF12's snapshots use.
- A13 PF6.12's "writes only through the core": browsing changes no file outside the store's
  ``.poisson/``; the folder's ``prove.toml`` is never written; ``HOME`` gains files only under
  ``.cache/poisson-prove/`` (the read record, PF4.39); no planted key's value is on any screen or in any
  file the app's work wrote.
- A14 Ctrl-C during a sweep the app launched stops it through the core's cancel token, leaves the run
  ``partial`` and, once the app has left the terminal, prints the ``stopped`` line ``sweep`` prints for a
  run stopped short (``stopped  N of M rollouts kept in run "NAME" (partial)``, with or without Ctrl-C's
  ``interrupted:``) and ``  next: poisson-prove sweep --resume``; exit 130.
- A15 Below 80 × 24 the one line is ``the window is W × H; the app needs at least 80 × 24``, with
  ``q quit``.
- A16 PF6.15's line: ``error:`` and a sentence naming the terminal app and saying it cannot start, then
  ``  next: poisson-prove --help``, nothing on stdout, exit 1.
- A17 The quickstart's runs record no event kinds when 0.0.1 wrote them, so the old pair's word is a
  direction word (``mixed``); the qs pair's kinds are declared (``prove.toml``), so its word is a
  kinded one (``safer``, ``worse``, ``trade`` or a nothing-moved word); neither pins a count.
- A18 At 80 columns the conditions screen's ``limit`` column is the larger of the two limits the row
  carries (``07-conditions``), chosen from the view, not computed; at 120 both show.
- A19 The verdict screen's detail lines are ``diff``'s verdict block for the same comparison, each
  label in ``diff``'s order and each line carrying that line's facts (its numbers as rule 10 prints
  them, the run names it gives, the binding words of PF4.35, PF4.41 and PF4.42), not its exact words:
  the look file's "then its label value detail lines in the command's order", pinned as PF4 pins a
  text surface's line, by its facts. The app may add lines of its own (``saved``, the family) between
  them. This holds at 120 × 40.
- A20 At 80 × 24 ``diff``'s whole verdict block does not fit above the events table (it is about 20
  rows at 80 columns and the body has 19), and the look file keeps the rows above a table from
  scrolling: so at 80 the verdict screen keeps its verdict line, the events table and the focused
  event's chart links, and the detail lines it has no room for are a second block behind one key, as
  the look file's layout says of a second block. No test pins which lines stay at 80.
- A21 The app opens when stdin and stdout are terminals, whatever stderr is, so a piped
  stderr still opens it (PF6.8's case). Textual draws on stderr; the app makes it draw on the
  terminal stdout is.
- A22 The screen is read as Textual's own ``export_screenshot`` reads it, from the screen's compositor
  (``pf6_support.grid_of``, the one place); a Textual that changes it changes that function only.
- A23 A run that declares no failure (every 0.0.1 run) opens, on Enter, the episodes of the first
  outcome its view lists that is not its commonest; no test pins which.
- A24 A partial run is resumed by launching it again from the app: the app's sweep of a spec whose latest
  run of that spec is partial resumes that run (its plan says so), and accepting finishes it.
- A25 The app opened with no ``--store`` where no store exists yet (a stranger's first run) shows
  home's empty state, ``ok`` and no runs, naming ``init --example`` and the sweep key, not ``runs``'s
  refusal; a store named by ``--store`` that does not exist is that refusal (A11).

**Frozen assertions this file's commit moves:** none. PF1.3's "no arguments exits 2" holds as frozen,
since its process's stdin is not a terminal; PF6.8 adds the terminal case.

**Lanes.** The code suite.
"""

from __future__ import annotations

import json
import re
import shutil
import webbrowser
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from pf6_support import (
    MOCK, PLANTED_KEYS, QS_B, ROLE_OF_WORD, SMALL_SPEC, SNAPSHOT_COMMAND, SNAPSHOTS, Grid, Session, Spy, Step,
    after_app, as_document, blocker, build_old, build_qs, build_small, build_stats, cli, copy_world, doc,
    drive, joined_lines, kind_of, listing, network_attempts, normalise, prove, read_only, run_pty, run_times,
    saved_id, says, shared_world, shows_number, split_first_line, squash, strip_escapes, unshown, unshown_rows,
)

ROOT = Path(__file__).resolve().parents[1]
BIG = (120, 60)
SIZES = {"80x24": (80, 24), "120x40": (120, 40)}

#: Home's view, frozen here from ``screens/01-home.md`` (reading A5). A view may hold more.
HOME_FIELDS: dict[str, set[str]] = {
    "": {"store", "n_runs", "n_comparisons", "verdict", "sentence", "latest_run", "latest_comparison", "next", "ui", "items"},
    "/items/*": {"kind", "name", "result", "rows", "id", "created", "limit"},
}

#: The screens' titles (reading A2) and the screen each is opened from on the way the tests take.
TITLES = ("home", "runs", "run", "episodes", "sweep", "compare", "comparison", "conditions", "condition", "could not detect", "help")
OPENED_FROM = {
    "runs": "home", "run": "runs", "episodes": "run", "sweep": "home", "compare": "home", "comparison": "compare",
    "conditions": "comparison", "condition": "conditions", "could not detect": "comparison", "help": "home",
}
#: The view each screen renders (reading A4); the sweep renders the core's plan.
VIEW_OF = {
    "home": "home", "runs": "runs", "run": "run", "episodes": "episodes", "compare": "runs", "comparison": "comparison",
    "conditions": "comparison", "condition": "condition", "could not detect": "could_not_detect",
}


# ---------- the worlds ----------


@pytest.fixture(autouse=True)
def _empty_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    for name in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE", "XDG_CACHE_HOME", "NO_COLOR", "CI", "TEXTUAL"):
        monkeypatch.delenv(name, raising=False)
    for k, v in PLANTED_KEYS.items():
        monkeypatch.setenv(k, v)
    return home


@pytest.fixture(scope="session")
def old_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    return shared_world(tmp_path_factory, "old", build_old)


@pytest.fixture(scope="session")
def qs_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    return shared_world(tmp_path_factory, "qs", build_qs)


@pytest.fixture(scope="session")
def small_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    return shared_world(tmp_path_factory, "small", build_small)


@pytest.fixture(scope="session")
def stats_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    return shared_world(tmp_path_factory, "stats", build_stats)


def _copy(world: tuple[Path, dict[str, Any]], tmp_path: Path, sub: str = "") -> Path:
    """A copy of a world's folder (or of one stats pair's folder) for one test: the folder the app
    runs in, holding ``prove-runs``."""
    src = world[0] / sub if sub else world[0]
    return copy_world(src, tmp_path / "w")


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> Spy:
    return Spy().install(monkeypatch)


@pytest.fixture
def opener(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every browser open the app asks for, none carried out."""
    opened: list[str] = []

    def record(url: str, *args: Any, **kwargs: Any) -> bool:
        opened.append(url)
        return True

    class Controller:
        def open(self, url: str, *args: Any, **kwargs: Any) -> bool:
            return record(url)

        open_new = open_new_tab = open

    for name in ("open", "open_new", "open_new_tab"):
        monkeypatch.setattr(webbrowser, name, record)
    monkeypatch.setattr(webbrowser, "get", lambda *args, **kwargs: Controller())
    return opened


@pytest.fixture
def clipboard(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from textual.app import App

    copied: list[str] = []
    monkeypatch.setattr(App, "copy_to_clipboard", lambda self, text: copied.append(text))
    return copied


# ---------- getting about ----------


async def _title(s: Session, title: str) -> Grid:
    return await s.wait_title(title)


async def reach(s: Session, screen: str, *, saved: bool = False, run_row: Callable[[str], bool] | None = None) -> Grid:
    """From home to ``screen`` by keys alone (reading A3). ``saved`` opens the verdict from home's saved
    comparison instead of the picker; ``run_row`` picks the run on the runs screen (default: the
    first)."""
    g = await _title(s, "home")
    if screen == "home":
        return g
    if screen == "help":
        await s.press("?")
        return await _title(s, "help")
    if screen == "sweep":
        await s.press("s")
        return await _title(s, "sweep")
    if screen in ("runs", "run", "episodes"):
        await s.press("r")
        g = await _title(s, "runs")
        if screen == "runs":
            return g
        if run_row is not None:
            await s.focus_row(run_row)
        await s.press("enter")
        g = await _title(s, "run")
        if screen == "run":
            return g
        await s.press("enter")
        return await _title(s, "episodes")
    if screen == "compare":
        await s.press("c")
        return await _title(s, "compare")
    if saved:
        await s.focus_row(lambda row: "→" in row or row[1:].lstrip().startswith("comparison "))
        await s.press("enter")
    else:
        await s.press("c")
        await _title(s, "compare")
        await s.press("enter")
    g = await _verdict(s)
    if screen == "comparison":
        return g
    if screen == "could not detect":
        await s.press("d")
        return await _title(s, "could not detect")
    await s.press("t")
    g = await _title(s, "conditions")
    if screen == "conditions":
        return g
    await s.press("home", "enter")
    return await _title(s, "condition")


def _verdict_shown(g: Grid) -> bool:
    """The verdict screen with its verdict line drawn, or a refusal on the message line: a comparison
    takes a moment, and the screen may open before its result is in."""
    if g.message.startswith("error:"):
        return True
    try:
        return g.title() == "comparison" and FIRST_WORD.match(g.body[0]) is not None
    except AssertionError:
        return False


async def _verdict(s: Session) -> Grid:
    await s.wait(_verdict_shown, what="the verdict or a refusal")
    return await s.settle()


def rendered(spy: Spy, screen: str) -> dict[str, Any] | None:
    """The document the core gave the app for ``screen`` (reading A4), the newest: its view, or for
    the episodes of a run that is in no saved comparison (which has no page) the core's
    ``episodes`` page."""
    views = spy.views(VIEW_OF[screen])
    if views:
        return views[-1][1]
    if screen == "episodes" and spy.results("episodes"):
        return as_document(spy.results("episodes")[-1])
    return None


async def _rendered_soon(s: Session, spy: Spy, screen: str) -> dict[str, Any]:
    await s.wait(lambda g: rendered(spy, screen) is not None, what=f"the {VIEW_OF[screen]} view")
    document = rendered(spy, screen)
    assert document is not None
    return document


def _rc(result: tuple[int | None, Any]) -> int | None:
    return result[0]


def _shows_error(g: Grid, error: str) -> bool:
    """Reading A11's line: the message line is the ``error:`` line, or, when the sentence is longer
    than the window, begins it and the screen shows the whole sentence."""
    if len(error) <= g.width:
        return g.message == error
    return g.message.startswith("error: ") and says(g.text(), error.removeprefix("error: "))


def _first_block(g: Grid) -> str:
    """The body's first block, up to its first blank row: the verdict line, wrapped as it may be."""
    out = []
    for row in g.body:
        if not row.strip():
            break
        out.append(row)
    return squash(" ".join(out))


# ---------- PF6.8 when no arguments opens the app ----------

#: (case, how the process runs, whether the app opens). Each case changes one thing from the first.
OPEN_CASES: tuple[tuple[str, dict[str, Any], bool], ...] = (
    ("stdin and stdout terminals, CI unset, TERM not dumb", {}, True),
    ("stderr piped", {"stderr": "pipe"}, True),
    ("NO_COLOR set", {"env": {"NO_COLOR": "1"}}, True),
    ("--store given, no verb", {"argv": ["--store", "prove-runs"]}, True),
    ("stdin not a terminal", {"stdin": "null"}, False),
    ("stdout piped", {"stdout": "pipe"}, False),
    ("CI set", {"env": {"CI": "1"}}, False),
    ("CI set but empty", {"env": {"CI": ""}}, False),
    ("TERM dumb", {"env": {"TERM": "dumb"}}, False),
    ("--plain and no verb", {"argv": ["--plain"]}, False),
)


@pytest.mark.parametrize("case,how,opens", OPEN_CASES, ids=[c[0] for c in OPEN_CASES])
def test_pf6_8_no_arguments_opens_the_app_only_on_a_terminal_outside_ci(
    case: str, how: dict[str, Any], opens: bool, small_world: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    """No verb, stdin and stdout terminals, ``CI`` unset (set to anything, empty included,
    is CI), ``TERM`` not ``dumb``: the app opens (its home screen on the terminal), and ``q`` leaves it,
    exit 0; ``NO_COLOR`` keeps it; ``--store PATH`` opens it on that store, named as typed. Any one of
    those not so, or ``--plain`` with no verb: PF1.3's exit 2, ``error: no verb given`` and ``  next:
    poisson-prove --help`` on stderr, nothing on stdout, unchanged."""
    folder = _copy(small_world, tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    steps = (Step(b"q", until=("poisson-prove · home", "prove-runs")),) if opens else ()
    run = run_pty(how.get("argv", []), home=home, cwd=folder, cols=80, rows=24, stdin=how.get("stdin", "pty"),
                  stdout=how.get("stdout", "pty"), stderr=how.get("stderr", "pty"), steps=steps, timeout=90, **how.get("env", {}))
    if opens:
        assert run.code == 0, (case, run.err[-500:])
        assert "\x1b[?1049h" in run.out, case  # the app took the whole screen
        (shown,) = run.seen
        assert shown[0].startswith("poisson-prove · home") and shown[0].rstrip().endswith("prove-runs"), (case, shown[0])
    else:
        assert run.code == 2, (case, run.code, run.out[-300:])
        err = strip_escapes(run.err).splitlines()
        assert err == ["error: no verb given", "  next: poisson-prove --help"], (case, err)
        if how.get("stdout", "pty") == "pipe":
            assert run.out == "", case
        else:
            assert "\x1b[?1049h" not in run.out and strip_escapes(run.out).strip() in ("", "\n".join(err)), case


# ---------- PF6.9 every screen, by keys alone ----------

SMALL_SCREENS = tuple(t for t in TITLES if t != "home")


@pytest.mark.parametrize("screen", SMALL_SCREENS)
def test_pf6_9_every_screen_is_reached_from_home_by_keys_renders_its_view_and_esc_goes_back(
    screen: str, small_world: tuple[Path, dict[str, Any]], spy: Spy, tmp_path: Path
) -> None:
    """Every screen of the app is reached from home by keys alone (A3); it renders the core object
    reading A4 names, which the core returned to the app before the screen showed; its header has its
    title (A2); ``Esc`` returns to the screen it was opened from, with the focus on the row it had."""
    folder = _copy(small_world, tmp_path)
    if screen == "sweep":
        (folder / "prove.toml").write_text(SMALL_SPEC.replace("replicates = 30", "replicates = 194"), encoding="utf-8")

    async def scenario(s: Session) -> None:
        await reach(s, OPENED_FROM[screen])
        await s.press("end")  # the focus off the first row, so going back must put it back where it was
        before = await s.settle()
        focus_before = [before.rows[i] for i in before.focused()]
        g = await reach_from(s, screen)
        assert g.title() == screen
        if screen == "sweep":
            await s.wait_text("[y/N]")
            assert spy.results("plan"), "the sweep screen rendered no plan of the core's"
        elif screen != "help":
            await s.wait(lambda g: rendered(spy, screen) is not None, what=f"the {VIEW_OF[screen]} view")
        await s.press("escape")
        back = await s.wait_title(OPENED_FROM[screen])
        assert [back.rows[i] for i in back.focused()] == focus_before, (screen, focus_before, back.focused())
        await s.press("q")

    assert _rc(drive(scenario, cwd=folder, size=(120, 40))) == 0


async def reach_from(s: Session, screen: str) -> Grid:
    """The last key from the screen ``screen`` is opened from (``OPENED_FROM``) to ``screen``."""
    key = {
        "runs": "r", "run": "enter", "episodes": "enter", "sweep": "s", "compare": "c", "comparison": "enter",
        "conditions": "t", "condition": "enter", "could not detect": "d", "help": "?",
    }[screen]
    await s.press(key)
    if screen == "comparison":
        return await _verdict(s)
    return await s.wait_title(screen)


@pytest.mark.parametrize("screen", TITLES)
@pytest.mark.parametrize("key,code", [("q", 0), ("ctrl+c", 130)], ids=["q", "ctrl-c"])
def test_pf6_9_q_exits_0_and_ctrl_c_exits_130_from_every_screen(
    screen: str, key: str, code: int, small_world: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    folder = _copy(small_world, tmp_path)
    (folder / "prove.toml").write_text(SMALL_SPEC.replace("replicates = 30", "replicates = 194"), encoding="utf-8")

    async def scenario(s: Session) -> None:
        await reach(s, screen)
        if screen == "sweep" and key == "q":
            await s.wait_text("[y/N]")
            await s.press("q")  # q at the question answers no and stays in the app
            await s.settle()
            assert s.app.is_running, "q at the question left the app"
        await s.press(key)
        for _ in range(100):
            if not s.app.is_running:
                return
            await s.pilot.pause(0.05)

    assert _rc(drive(scenario, cwd=folder, size=(80, 24))) == code


def _halves(g1: str, g2: str) -> str:
    return g1 + "\n" + g2


#: The screens whose every fact is checked, on the stores that reach them (the old store has no
#: ``prove.toml``, so its sweep screen is the refusal, checked elsewhere).
FACT_CASES = [(w, s) for w in ("old", "qs") for s in ("home", "runs", "run", "episodes", "comparison", "condition", "could not detect")] + [("qs", "sweep")]


@pytest.mark.parametrize("world,screen", FACT_CASES, ids=[f"{w}-{s}" for w, s in FACT_CASES])
def test_pf6_9_each_screen_shows_every_fact_of_the_object_it_renders(
    world: str, screen: str, request: pytest.FixtureRequest, spy: Spy, tmp_path: Path
) -> None:
    """Reading A6: every scalar of the view the core gave the screen (A4) is on it, at 120 × 60 with
    its table read through; the verdict and conditions screens together show the whole comparison
    view; the sweep screen the whole plan; home holds ``HOME_FIELDS`` (A5)."""
    w = request.getfixturevalue(f"{world}_world")
    folder = _copy(w, tmp_path)
    b_id = w[1]["b"]

    kind = VIEW_OF.get(screen, "plan")

    async def read(s: Session) -> tuple[dict[str, Any], str]:
        if screen == "comparison":
            first = (await _verdict(s)).text()
            await s.press("t")
            await s.wait_title("conditions")
            text = _halves(first, await s.read_through())
            await s.press("escape")
            await s.wait_title("comparison")
            return await _rendered_soon(s, spy, "comparison"), text
        if screen == "sweep":
            await s.wait_text("[y/N]")
            return as_document(spy.results("plan")[-1]), await s.read_through()
        document = await _rendered_soon(s, spy, screen)
        return document, await s.read_through()

    async def scenario(s: Session) -> tuple[dict[str, Any], str]:
        await reach(s, screen, saved=True, run_row=lambda row: b_id in row)  # the id column shows at 120
        document, text = await read(s)
        for _ in range(2):  # a screen still drawing what it was given is read again, not failed
            if not unshown(document, text, kind) and not unshown_rows(document, text, kind):
                break
            await s.pilot.pause(0.5)
            document, text = await read(s)
        return document, text

    rc, (document, text) = drive(scenario, cwd=folder, size=BIG)
    missing = unshown(document, text, kind)
    assert missing == [], (screen, missing[:12])
    rows = unshown_rows(document, text, kind)
    assert rows == [], (screen, "a table row's facts are not on one line", rows[:5])
    if screen == "home":
        for path, fields in HOME_FIELDS.items():
            nodes = [document] if not path else list(document.get("items", []))
            for node in nodes:
                assert fields <= set(node), (path, sorted(fields - set(node)))
        # One table of runs and comparisons, newest first, in the view's order
        at = [text.find(str(item["id"])[:12]) for item in document["items"]]
        assert -1 not in at and at == sorted(at), [item["id"] for item in document["items"]]


@pytest.mark.parametrize("world", ["old", "qs", "small"])
def test_pf6_9_a_result_screen_opens_with_its_views_verdict_line(world: str, request: pytest.FixtureRequest, spy: Spy, tmp_path: Path) -> None:
    """The look file's layout: a screen that shows a result opens its body with that result's verdict
    line, the view's word and sentence, at column 3 (home, runs, the verdict, conditions, could not
    detect, episodes); the verdict screen's is ``diff``'s for the same pair (A7) when the picker compared."""
    w = request.getfixturevalue(f"{world}_world")
    folder = _copy(w, tmp_path)
    saved = world != "small"

    async def scenario(s: Session) -> dict[str, str]:
        seen = {}
        for screen in ("home", "runs", "episodes", "comparison", "could not detect"):
            if s.grid().title() != "home":
                for _ in range(8):
                    if s.grid().title() == "home":
                        break
                    await s.press("escape")
                    await s.settle()
            g = await reach(s, screen, saved=saved)
            view = await _rendered_soon(s, spy, screen)
            assert view is not None, screen
            line = _first_block(g)
            assert g.body[0].startswith("  " + view["verdict"] + "  "), (screen, g.body[0])
            assert line == squash(f"{view['verdict']}  {view['sentence']}"), (screen, line, view["verdict"], view["sentence"])
            seen[screen] = line
        return seen

    _, seen = drive(scenario, cwd=folder, size=(120, 40))
    if world == "small":
        first = cli("diff", cwd=folder).out.splitlines()[0]
        assert seen["comparison"] == squash(first), (seen["comparison"], first)


# ---------- the layout, the focus, the keys and the colours (the look file's terminal-app section) ----------

TOUR = ("home", "runs", "run", "episodes", "compare", "comparison", "conditions", "condition", "could not detect", "help", "sweep")


async def _back_home(s: Session) -> None:
    for _ in range(8):
        if s.grid().title() == "home":
            return
        await s.press("escape")
        await s.settle()


async def _tour(s: Session, *, saved: bool) -> list[Grid]:
    grids = []
    for screen in TOUR:
        await _back_home(s)
        grids.append(await reach(s, screen, saved=saved))
    return grids


def _build_tour(size: str, qs: Path) -> Callable[[Path], dict[str, Any]]:
    """The tour of every screen on a copy of the quickstart at ``size``, recorded once for the tests
    that read it (the bands, the columns, the colours): its grids and, at 80 columns, the conditions
    screen read through with the comparison view it rendered."""

    def build(folder: Path) -> dict[str, Any]:
        work = copy_world(qs, folder / "w")

        async def scenario(s: Session) -> dict[str, Any]:
            grids = await _tour(s, saved=True)
            out: dict[str, Any] = {"grids": [g.to_json() for g in grids]}
            if size == "80x24":
                await _back_home(s)
                await reach(s, "conditions", saved=True)
                out["conditions"] = await s.read_through()
            return out

        with Spy().installed() as spy:
            _, out = drive(scenario, cwd=work, size=SIZES[size])
            if size == "80x24":
                out["rows"] = spy.views("comparison")[-1][1]["rows"]
        return out

    return build


@pytest.fixture(scope="session")
def tours(tmp_path_factory: pytest.TempPathFactory, qs_world: tuple[Path, dict[str, Any]]) -> Callable[[str], dict[str, Any]]:
    def tour(size: str) -> dict[str, Any]:
        return shared_world(tmp_path_factory, f"tour-{size}", _build_tour(size, qs_world[0]))[1]

    return tour


@pytest.mark.parametrize("size", list(SIZES))
def test_pf6_every_screen_has_the_six_bands_one_focus_and_its_key_bar(size: str, tours: Callable[[str], dict[str, Any]]) -> None:
    """The look's layout: row 1 the header (``poisson-prove · <title>``, the store at the
    right edge), row 2 and row H − 1 a dim hairline, row H the key bar (keys bold, words dim, ending ``?
    help`` then ``q quit`` but on help), no border character anywhere; exactly one row has the focus,
    drawn in reverse video with ``›`` in column 1."""
    w, h = SIZES[size]
    grids = [Grid.from_json(g) for g in tours(size)["grids"]]
    assert [g.title() for g in grids] == list(TOUR)
    for g in grids:
        title = g.title()
        assert (g.width, g.height) == (w, h)
        assert g.header.rstrip().endswith("prove-runs"), g.header
        for row in (1, h - 2):
            assert set(g.rows[row]) == {"─"}, (title, row, g.rows[row])
            assert set(g.masks[row]) == {"D"}, (title, row)
        if title != "help":
            assert re.search(r"\? help\s+q quit$", g.keybar), (title, g.keybar)
        bar_mask = g.masks[-1]
        for m in re.finditer(r"\S+", g.keybar):
            word = m.group(0)
            roles = set(bar_mask[m.start():m.end()])
            assert roles <= {"B", "D"}, (title, word, roles)
        assert not set("".join(g.rows)) & set("│┃┌┐└┘├┤┬┴┼╭╮╰╯═║"), title
        focused = g.focused()
        if title not in ("help", "sweep"):  # help and the plan have neither rows nor links to focus
            assert len(focused) == 1, (title, focused)
            (i,) = focused
            assert {c for c, ch in zip(g.masks[i], g.rows[i]) if ch != " "} <= {"V"}, (title, g.masks[i])


@pytest.mark.parametrize("no_color", [None, "", "1"], ids=["unset", "empty", "set"])
def test_pf6_colour_follows_the_four_meanings_in_the_16_named_colours_and_no_color_drops_it(
    no_color: str | None, stats_world: tuple[Path, dict[str, Any]], tours: Callable[[str], dict[str, Any]], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The look's colour rules on the app: each verdict word in its meaning's colour
    (A9); ``note:`` yellow and ``error:`` red on the message line; no digit coloured; no colour but green, yellow
    and red of the 16 named colours, and no background; under ``NO_COLOR`` set and not empty, no green, yellow
    or red, and the focus still reversed (A10). Unset, every screen of the tour is read too; set and
    empty, home, four verdicts and a refusal."""
    if no_color is not None:
        monkeypatch.setenv("NO_COLOR", no_color)
    drops = bool(no_color)
    grids: list[Grid] = []
    for name in ("mid", "tiny", "standard", "cases"):
        folder = copy_world(stats_world[0] / name, tmp_path / name)

        async def scenario(s: Session) -> list[Grid]:
            out = [await reach(s, "home")]
            await s.press("c")
            await s.wait_title("compare")
            await s.press("enter")
            out.append(await _verdict(s))
            return out

        grids += drive(scenario, cwd=folder, size=(120, 40))[1]
    if no_color is None:
        grids += [Grid.from_json(g) for g in tours("120x40")["grids"]]
    words_seen = set()
    for g in grids:
        assert g.off_palette == set(), (g.title(), sorted(g.off_palette))
        for row, mask in zip(g.rows, g.masks):
            coloured = [ch for ch, m in zip(row, mask) if ch.isdigit() and m in "GYR"]
            assert coloured == [], (g.title(), row)
        if drops:
            assert not set("".join(g.masks)) & set("GYR"), g.title()
        if g.focused():
            assert "V" in g.masks[g.focused()[0]], g.title()
        msg = g.message
        for prefix, role in (("note:", "Y"), ("error:", "R")):
            if msg.startswith(prefix) and not drops:
                assert set(g.masks[-3][: len(prefix)]) == {role}, (g.title(), msg)
        if g.body and FIRST_WORD.match(g.body[0]):
            word = FIRST_WORD.match(g.body[0]).group(1)  # type: ignore[union-attr]
            if word in ROLE_OF_WORD:
                words_seen.add(word)
                roles = {m for ch, m in zip(g.body[0][2:2 + len(word)], g.masks[2][2:2 + len(word)]) if ch != " "}
                if drops:
                    assert roles <= {"B", " "}, (g.title(), word, roles)
                else:
                    assert roles == {ROLE_OF_WORD[word]}, (g.title(), word, roles)
    assert {"ok", "no significant change", "too small to tell", "trade"} <= words_seen, words_seen


FIRST_WORD = re.compile(r"^  ([a-z][a-z ]*?)  \S")


# ---------- widths: the columns each screen keeps at 80 and adds at 120 ----------

#: Each screen's table header words in order, at 80 and at 120 columns (``screens/*.md``, Widths).
COLUMNS = {
    "home": (("kind", "name", "result", "rows", "created"), ("kind", "name", "result", "rows", "id", "created")),
    "runs": (("#", "name", "status", "rows", "no outcome", "created"), ("#", "name", "id", "status", "backend", "target", "rows", "no outcome", "created")),
    "compare": (("#", "name", "status", "rows", "created"), ("#", "name", "id", "status", "backend", "target", "rows", "created")),
    "comparison": (("event", "kind", "worse", "safer", "unchanged", "could not tell"), ("event", "kind", "worse", "safer", "unchanged", "could not tell", "conditions")),
    "conditions": (("condition", "event", "before", "after", "change", "q", "verdict", "limit"), ("condition", "event", "before", "after", "change", "p", "q", "verdict", "rise", "fall")),
    "run": (("timeout", "violated"), ("episodes", "completed", "timeout", "violated")),
    "episodes": (("replicate", "seed", "outcome", "t"), ("replicate", "seed", "outcome", "t")),
    "could not detect": (("event", "before", "rise", "fall", "could tell"), ("event", "before", "rise", "fall", "could tell")),
}


def _has_in_order(line: str, words: tuple[str, ...]) -> bool:
    pos = 0
    for word in words:
        m = re.search(rf"(?<![\w#]){re.escape(word)}(?![\w])", line[pos:])
        if not m:
            return False
        pos += m.end()
    return True


@pytest.mark.parametrize("size", list(SIZES))
def test_pf6_each_tables_columns_at_80_and_120_are_the_designs(size: str, tours: Callable[[str], dict[str, Any]]) -> None:
    """Each table's columns at 80 and 120, as ``screens/*.md`` gives them, in their order, and
    the columns 120 adds absent at 80; at 80 the conditions screen's ``limit`` is each row's larger
    limit, or its note when neither direction has one (reading A18)."""
    at = 0 if size == "80x24" else 1
    tour = tours(size)
    grids = [Grid.from_json(g) for g in tour["grids"]]
    if at == 0:
        lines = joined_lines(tour["conditions"])
        for row in tour["rows"]:
            both = [x for x in (row["mde_rise"], row["mde_fall"]) if x is not None]
            limit = f"{max(both):.3f}" if both else str(row.get("mde_rise_note") or row.get("mde_fall_note"))
            values = [str(v) for v in row["config"].values()]
            assert any(all(v in line for v in values) and row["event"] in line and limit in line for line in lines), (row["config"], row["event"], limit)
    for g in grids:
        title = g.title()
        if title not in COLUMNS:
            continue
        want = COLUMNS[title][at]
        headers = [row for row in g.body if _has_in_order(row, want)]
        assert headers, (title, size, want, g.text())
        dropped = set(COLUMNS[title][1]) - set(want)
        if at == 0 and dropped:
            assert any(not any(_has_in_order(h, (d,)) for d in dropped) for h in headers), (title, headers, sorted(dropped))


# ---------- the facts the statistics give the verdict and condition screens ----------


def _compare_in_app(folder: Path, size: tuple[int, int] = (120, 40), then: Callable[[Session], Awaitable[Any]] | None = None) -> Any:
    async def scenario(s: Session) -> Any:
        await reach(s, "home")
        await s.press("c")
        await s.wait_title("compare")
        await s.press("enter")
        g = await _verdict(s)
        out = {"verdict": g, "text": await s.read_through() if g.title() == "comparison" else g.text()}
        if then is not None:
            out["then"] = await then(s)
        await s.press("q")
        return out

    return drive(scenario, cwd=folder, size=size)


def _detail(text: str, label: str) -> list[str]:
    """The screen lines labelled ``label`` (a ``label  value`` detail line), each with its wrapped
    continuation rows joined."""
    rows = text.splitlines()
    out = []
    for i, row in enumerate(rows):
        m = re.match(rf"^  {re.escape(label)}\s{{2,}}(\S.*)$", row)
        if m:
            parts = [m.group(1)]
            indent = len(row) - len(m.group(1))
            j = i + 1
            while j < len(rows) and rows[j].startswith(" " * indent) and rows[j][indent:indent + 1] != " " and not re.match(r"^  \S", rows[j]):
                parts.append(rows[j].strip())
                j += 1
            out.append(squash(" ".join(parts)))
    return out


#: The binding words of PF4.35, PF4.41 and PF4.42 (and the words its other surfaces print for
#: PF4.39 and PF4.46), matched without regard to case, hyphens or dashes.
BINDING = ("Benjamini", "Hochberg", "false discovery rate", "Holm", "family-wise", "cause-specific hazard", "Miettinen-Nurminen",
           "Tango", "simultaneous", "Bonferroni", "false coverage", "Benjamini-Yekutieli", "peeking", "errored", "would change the word")
_NAME = re.compile(r'"[^"]+"|\b\S+ \d{4}-\d\d-\d\d [a-z]+\b')


def _block(text: str) -> tuple[str, list[tuple[str, str]]]:
    """``diff``'s verdict block: its first line and its ``label  text`` detail lines."""
    lines = text.split("\n\n", 1)[0].splitlines()
    details = []
    for line in lines[1:]:
        m = re.match(r"^  (\S(?:.*?\S)?)  (\S.*)$", line)
        assert m, line
        details.append((m.group(1), m.group(2)))
    return lines[0], details


def _carries(line: str, text: str, names: dict[str, str]) -> list[str]:
    """What of ``text`` (a plain detail line) the app's ``line`` lacks: its numbers as rule 10 prints
    them, the run names it gives, and its binding words (as PF4 reads it: a text surface's line is
    pinned only by its facts)."""
    lacks = []
    for name in names.values():
        if name in text and not says(line, name):
            lacks.append(name)
    bare = _NAME.sub(" ", text)
    for m in re.finditer(r"[+\-−]?\d[\d,]*(?:\.\d+)?(?:e[+\-−]?\d+)?%?", bare):
        token = m.group(0).replace(",", "")
        value = float(token.rstrip("%")) / (100 if token.endswith("%") else 1)
        if not shows_number(line, value):
            lacks.append(m.group(0))
    lacks += [w for w in BINDING if says(text, w) and not says(line, w)]
    return lacks


#: (store, ``diff``'s arguments that made it, how the app reaches it, the detail labels the case is for).
BLOCK_CASES = {
    "standard": ((), "picker", ("verdict rule", "fragility")),
    "mid": ((), "picker", ("threshold",)),
    "argon": ((), "picker", ("flagged only",)),
    "errors": ((), "picker", ("errors",)),
    "peeking": ((), "picker", ("peeking",)),
    "logrank": (("--event", "fell", "--method", "logrank_bh"), "saved", ("competing",)),
    "tiny": ((), "picker", ()),
}


@pytest.mark.parametrize("name", list(BLOCK_CASES))
def test_pf6_the_verdict_screen_opens_with_diffs_verdict_line_and_carries_its_detail_lines_in_order(
    name: str, stats_world: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    """The verdict screen's list, as the look file's layout puts it ("the same word and sentence the command
    prints, then its label value detail lines in the command's order"): the verdict screen's first line
    is ``diff``'s; then, in ``diff``'s order, a line for each of its verdict block's detail lines, with
    the label, the numbers as rule 10 prints them, the run names and the binding words: the method and
    how it was chosen, the word counted at the family-wise level by Holm and the flags by
    Benjamini–Hochberg (PF4.34, PF4.35), the rows flagged only, the threshold under the nothing-moved
    words, the limits, the intervals on the change, the fragility with its flips (PF4.44), the peeking
    caveat naming the run (PF4.39), the errored-episodes warning (PF4.46) and log-rank's
    cause-specific hazard and competing note (PF4.41). The app reads them from the core: nothing it
    shows differs from the command."""
    argv, how, labels = BLOCK_CASES[name]
    folder = _copy(stats_world, tmp_path, name)
    first, details = _block(cli("diff", *argv, cwd=folder).out)
    assert {lb for lb, _ in details} >= set(labels), (name, [lb for lb, _ in details])
    if how == "saved":
        async def saved(s: Session) -> tuple[Grid, str]:
            g = await reach(s, "comparison", saved=True)
            return g, await s.read_through()

        _, (g, text) = drive(saved, cwd=folder, size=(120, 40))
    else:
        _, out = _compare_in_app(folder)
        g, text = out["verdict"], out["text"]
    assert _first_block(g) == squash(first), (_first_block(g), first)
    lines = joined_lines(text)
    at = 0
    names = stats_world[1][name]["names"]
    for label, words in details:
        found = next((i for i in range(at, len(lines)) if re.match(rf"^  {re.escape(label)}\s{{2,}}\S", lines[i])), None)
        assert found is not None, (name, label, "not on the screen after the line before it", lines[at:at + 12])
        assert _carries(lines[found], words, names) == [], (name, label, lines[found], words)
        at = found + 1


def test_pf6_the_conditions_screen_names_the_flags_rule_beside_them(stats_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """PF4.35 on the terminal app's conditions screen: the flags' rule beside them, on one line,
    Benjamini–Hochberg at the false discovery rate over M tests."""
    folder = _copy(stats_world, tmp_path, "argon")
    plain = doc(cli("diff", "--json", cwd=folder))

    async def conditions(s: Session) -> str:
        await s.press("t")
        await s.wait_title("conditions")
        return await s.read_through()

    _, out = _compare_in_app(folder, then=conditions)
    rows = out["then"]
    words = ("Benjamini", "Hochberg", "false discovery rate", f"{plain['n_tests']} tests")
    assert any(all(says(line, w) for w in words) for line in joined_lines(rows)), (words, rows[:800])


def test_pf6_no_significant_change_carries_its_verdict_limit_on_the_same_line_everywhere_in_the_app(
    stats_world: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    """PF4.40: wherever the app writes ``no significant change`` (the verdict line and the screens that
    repeat it, and home's row for the saved comparison), the same line (a wrapped line is one line)
    carries the verdict limit to three decimals; ``diff --json``'s ``verdict_limit`` is that number."""
    folder = _copy(stats_world, tmp_path, "mid")
    plain = doc(cli("diff", "--json", cwd=folder))
    assert plain["verdict"] == "no significant change"
    limit = f"{plain['verdict_limit']:.3f}"

    async def scenario(s: Session) -> list[Grid]:
        await reach(s, "home")
        await s.press("c")
        await s.wait_title("compare")
        await s.press("enter")
        grids = [await _verdict(s)]
        await s.press("t")
        grids.append(await s.wait_title("conditions"))
        await s.press("escape")
        await s.wait_title("comparison")
        await s.press("d")
        grids.append(await s.wait_title("could not detect"))
        for _ in range(3):
            await s.press("escape")
            await s.settle()
        grids.append(await s.wait_title("home"))
        return grids

    _, grids = drive(scenario, cwd=folder, size=(120, 40))
    found = 0
    for g in grids:
        for line in joined_lines(g.text()):
            if "no significant change" in line:
                found += 1
                assert limit in line, (g.title(), line, limit)
    assert found >= 4, found


def test_pf6_the_condition_screen_shows_both_limits_and_the_interval_on_the_change_as_diff_gives_them(
    stats_world: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    """PF4.22, PF4.27 and PF4.42 on the condition screen, for every condition of a pair whose rows
    span a rise, a fall, no change, no room and nothing detectable: the rise and fall limits (each a
    number to three decimals, or its null note), the interval on the change with its bounds, its level
    as a percentage and its rule (false coverage, Benjamini–Yekutieli; or simultaneous, Bonferroni) and
    its method (Tango or Miettinen–Nurminen), each as ``diff --json`` gives it: read from the core, not
    recomputed."""
    folder = _copy(stats_world, tmp_path, "standard")
    plain = doc(cli("diff", "--json", cwd=folder))
    cells = plain["by_event"]["fell"]["cells"]

    async def scenario(s: Session) -> dict[str, str]:
        await reach(s, "conditions")
        seen: dict[str, str] = {}
        for i in range(len(cells)):
            await s.press("home", *(["down"] * i), "enter")
            g = await s.wait_title("condition")
            seen[squash(g.header)] = await s.read_through()
            await s.press("escape")
            await s.wait_title("conditions")
        return seen

    _, seen = drive(scenario, cwd=folder, size=BIG)
    assert len(seen) == len(cells)
    for cell in cells:
        name = cell["config"]["cell"]
        (text,) = [t for header, t in seen.items() if re.search(rf"\b{re.escape(name)}\b", header)]
        for side in ("rise", "fall"):
            value, note = cell[f"mde_{side}"], cell[f"mde_{side}_note"]
            lines = _detail(text, side)
            assert lines, (name, side, text[:400])
            if value is None:
                assert any(says(line, note) for line in lines), (name, side, note, lines)
            else:
                assert any(f"{value:.3f}" in line for line in lines), (name, side, value, lines)
        change = _detail(text, "change")
        assert change, (name, text[:400])
        level = f"{100 * cell['ci_level']:.3f}".rstrip("0").rstrip(".") + "%"
        for number in (cell["ci_lo"], cell["ci_hi"]):
            assert any(shows_number(line, number) for line in change), (name, number, change)
        assert any(level in line for line in change), (name, level, change)
        method = {"tango": "Tango", "miettinen-nurminen": "Miettinen-Nurminen"}[cell["ci_method"]]
        rule = ("false coverage", "Benjamini-Yekutieli") if plain["interval_rule"] == "benjamini-yekutieli" else ("simultaneous", "Bonferroni")
        assert says(text, method) and all(says(text, w) for w in rule), (name, method, rule)


def test_pf6_a_log_rank_conditions_shifted_competitor_is_noted_on_its_screen(stats_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """PF4.41 on a comparison saved under ``logrank_bh`` and opened from home: the condition screen of
    the condition whose competing outcome shifted notes it (``stuck``) with the cause-specific hazard;
    the verdict screen's method line is the block test's."""
    folder = _copy(stats_world, tmp_path, "logrank")

    async def scenario(s: Session) -> dict[str, str]:
        g = await reach(s, "comparison", saved=True)
        out = {"verdict": g.text()}
        await s.press("t")
        await s.wait_title("conditions")
        for name in ("c",):  # the condition whose competing outcome shifted
            await s.focus_row(lambda row, name=name: re.search(rf"\b{name}\b", row) is not None)
            await s.press("enter")
            out[name] = (await s.wait_title("condition")).text()
            await s.press("escape")
            await s.wait_title("conditions")
        return out

    _, out = drive(scenario, cwd=folder, size=BIG)
    assert says(out["c"], "cause-specific hazard") and says(out["c"], "stuck"), out["c"][:600]


@pytest.mark.parametrize("name,verb", [("cases", "diff"), ("nothing", "diff")])
def test_pf6_a_comparison_the_core_refuses_is_one_error_line_and_the_app_stays_open(
    name: str, verb: str, stats_world: tuple[Path, dict[str, Any]], spy: Spy, tmp_path: Path
) -> None:
    """Reading A11 for the pair: a condition that ran several cases (PF4.38: make each case its own
    sweep axis) and a pair with no condition in both runs (PF4.7): the message line is ``diff``'s
    ``error:`` line, its ``next`` commands are on the screen, the refusal is the core's, nothing is
    saved, the app stays open, and ``q`` exits 0."""
    folder = _copy(stats_world, tmp_path, name)
    plain = cli(verb, cwd=folder)
    assert plain.code == 1
    (error,) = plain.errors()
    rc, out = _compare_in_app(folder)
    g = out["verdict"]
    assert _shows_error(g, error), (g.message, error)
    for command in plain.nexts():
        assert says(g.text(), command), (command, g.text())
    assert spy.refusals() and str(spy.refusals()[-1]) == error.removeprefix("error: ")
    assert saved_id(folder / "prove-runs") == []
    assert rc == 0


def test_pf6_too_small_to_tell_reads_yellow_and_could_not_detect_says_why(stats_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """A design too small to flag anything: the word ``too small to tell`` (yellow), and
    the could-not-detect screen lists every unchanged row with ``cannot be flagged`` and the smallest
    possible p against the level."""
    folder = _copy(stats_world, tmp_path, "tiny")
    plain = doc(cli("diff", "--json", cwd=folder))
    assert plain["verdict"] == "too small to tell"

    async def detect(s: Session) -> str:
        await s.press("escape")
        await s.wait_title("compare")
        await s.press("enter")
        await _verdict(s)
        await s.press("d")
        await s.wait_title("could not detect")
        return await s.read_through()

    _, out = _compare_in_app(folder, then=detect)
    g = out["verdict"]
    word = "too small to tell"
    assert g.body[0].startswith(f"  {word}  "), g.body[0]
    assert {m for ch, m in zip(g.body[0][2:2 + len(word)], g.masks[2][2:2 + len(word)]) if ch != " "} == {"Y"}, g.masks[2][:20]
    assert says(out["then"], "cannot be flagged"), out["then"][:600]


# ---------- PF6.10 a sweep from the app ----------


def _sweep_folder(tmp_path: Path, name: str, replicates: int = 194, target: str = f"{MOCK}:rollout") -> Path:
    folder = tmp_path / name
    folder.mkdir()
    assert cli("init", "--example", cwd=folder).code == 0
    spec = folder / "prove.toml"
    text = spec.read_text(encoding="utf-8")
    assert text.count("replicates = 194") == 1 and text.count(f'target = "{MOCK}:rollout"') == 1, text
    text = text.replace("replicates = 194", f"replicates = {replicates}")
    spec.write_text(text.replace(f'target = "{MOCK}:rollout"', f'target = "{target}"'), encoding="utf-8")
    return folder


def _asked(folder: Path, home: Path) -> str:
    """The question ``sweep`` asks on a terminal, answered no."""
    run = run_pty(["sweep"], home=home, cwd=folder, cols=120, rows=40, steps=(Step(b"n\r", until="[y/N]"),), timeout=90)
    (line,) = [squash(strip_escapes(line)) for line in run.err.splitlines() if "[y/N]" in line]
    return line[: line.index("[y/N]") + len("[y/N]")]


@pytest.mark.parametrize("decline", ["n", "escape", "q", "enter", "x"])
def test_pf6_10_the_apps_sweep_shows_sweeps_plan_asks_its_question_and_no_writes_nothing(
    decline: str, spy: Spy, tmp_path: Path
) -> None:
    """The sweep screen shows every line of the plan ``sweep --dry-run`` prints and asks the
    question ``sweep`` asks, ``[y/N]``; ``n``, ``Esc``, ``q`` and ``Enter`` each answer no (no is the only
    default; ``q`` at the question stays in the app), and no other key answers yes (the look file:
    only ``y`` does); nothing is written: the folder is byte for byte as it was."""
    folder = _sweep_folder(tmp_path, "s")
    home = tmp_path / "home2"
    home.mkdir()
    plan = cli("sweep", "--dry-run", cwd=folder).out
    question = _asked(folder, home)
    before = listing(folder)

    async def scenario(s: Session) -> tuple[str, Grid]:
        g = await reach(s, "sweep")
        await s.wait_text("[y/N]")
        g = await s.settle()
        text = g.text()
        await s.press(decline)
        after = await s.settle()
        assert after.title() in ("sweep", "home"), after.title()
        assert s.app.is_running, "an answer of no left the app"
        if decline != "x":
            assert "[y/N]" not in after.text(), "the question is still asked after it was answered no"
        else:
            await s.press("n")
            await s.settle()
        await s.press("q")
        if s.app.is_running:
            await s.press("q")
        return text, after

    rc, (text, _) = drive(scenario, cwd=folder, size=(120, 40))
    assert rc == 0
    plan_block = plan.split("\n\n", 1)[0]
    for line in plan_block.splitlines():
        assert says(text, line.strip()), (line, text)
    assert says(text, question), (question, text)
    assert listing(folder) == before
    assert spy.results("plan") and not spy.results("start")


SLOW_TARGET = '''\
import time

from poisson_prove.examples import mock_agent


def rollout(cfg, seed):
    time.sleep(0.002)
    return mock_agent.rollout(cfg, seed)
'''
EVENT_GRAMMAR = re.compile(r"^PS[gn]*[FI]$")
EVENT_LETTERS = {"planned": "P", "started": "S", "progress": "g", "note": "n", "finished": "F", "interrupted": "I", "resumed": "R"}


def test_pf6_10_yes_writes_the_run_sweep_yes_writes_with_live_progress_and_the_result(spy: Spy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``y`` runs the sweep: while it runs the plan stays on screen with one progress line,
    the counts of a progress event the core reported, and the run's name; at the end the screen shows
    ``sweep``'s result line. The run is the one ``sweep --yes`` from the same spec writes, judged on what
    does not depend on the run's identity: the same conditions and replicates, the same manifest keys,
    status complete, and an ``events.jsonl`` in the run event log's grammar."""
    (tmp_path / "pf6_slow_app.py").write_text(SLOW_TARGET, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    folder = _sweep_folder(tmp_path, "app", target="pf6_slow_app:rollout")
    other = _sweep_folder(tmp_path, "cli", target="pf6_slow_app:rollout")

    async def scenario(s: Session) -> dict[str, Any]:
        await reach(s, "sweep")
        await s.wait_text("[y/N]")
        plan_line = _first_block(await s.settle())
        await s.press("y")

        def progressing(g: Grid) -> bool:
            events = [e for e in spy.events if getattr(e, "kind", None) == "progress"]
            return any(shows_number(g.text(), e.detail["done"]) and shows_number(g.text(), e.detail["total"]) and 0 < e.detail["done"] < e.detail["total"] for e in events)

        during = await s.wait(progressing, what="a progress line")
        done = await s.wait(lambda g: _first_block(g).startswith("done "), timeout=120, what="the result")
        await s.press("q")
        return {"plan_line": plan_line, "during": during, "done": done}

    rc, out = drive(scenario, cwd=folder, size=(120, 40))
    assert rc == 0
    assert squash(_first_block(out["during"])).startswith(out["plan_line"][:20]), "the plan left the screen while the sweep ran"
    result = as_document(spy.results("start")[-1])
    assert says(out["during"].text(), result["run_name"])
    assert _first_block(out["done"]).startswith("done ") and says(out["done"].text(), result["run_name"])
    assert cli("sweep", "--yes", cwd=other).code == 0
    from poisson_prove.store import Store

    (mine,), (theirs,) = Store(folder / "prove-runs").runs(), Store(other / "prove-runs").runs()
    m1, m2 = (json.loads((root / "prove-runs" / r / "manifest.json").read_text(encoding="utf-8")) for root, r in ((folder, mine), (other, theirs)))
    assert set(m1) == set(m2) and m1["status"] == m2["status"] == "complete"
    assert set(m1["environment"]) == set(m2["environment"])
    f1, f2 = Store(folder / "prove-runs").read(mine), Store(other / "prove-runs").read(theirs)
    assert sorted(f1["config_hash"].value_counts().items()) == sorted(f2["config_hash"].value_counts().items())
    events = [json.loads(line)["kind"] for line in (folder / "prove-runs" / mine / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert EVENT_GRAMMAR.match("".join(EVENT_LETTERS[k] for k in events)), events


def test_pf6_10_an_underpowered_spec_keeps_its_plan_and_p_plans_again_with_the_named_replicates(spy: Spy, tmp_path: Path) -> None:
    """The design's sweep refusal: the quickstart at 100 replicates: the plan stays with
    ``sweep``'s ``error:`` line and its ``next`` commands; ``p`` plans again with the replicates
    the refusal names, which pass, and never writes the spec; nothing runs until ``y``."""
    folder = _sweep_folder(tmp_path, "low", replicates=100)
    plain = cli("sweep", cwd=folder)  # refused at the plan, before any question
    assert plain.code == 1
    (error,) = plain.errors()
    (named,) = {int(m) for c in plain.nexts() for m in re.findall(r"--replicates (\d+)", c)}
    spec_before = (folder / "prove.toml").read_bytes()

    async def scenario(s: Session) -> tuple[Grid, Grid]:
        await reach(s, "sweep")
        sentence = error.removeprefix("error: ")[:40]
        refused = await s.wait(lambda g: g.title() == "sweep" and g.message.startswith("error:") and says(g.text(), sentence), what="sweep's refusal")
        await s.press("p")
        again = await s.wait_text("[y/N]")
        await s.press("n")
        await s.press("q")
        if s.app.is_running:
            await s.press("q")
        return refused, again

    _, (refused, again) = drive(scenario, cwd=folder, size=(120, 40))
    assert _shows_error(refused, error), (refused.message, error)
    for command in plain.nexts():
        assert says(refused.text(), command), command
    assert shows_number(again.text(), named) and not again.message.startswith("error:")
    assert (folder / "prove.toml").read_bytes() == spec_before
    assert not (folder / "prove-runs").exists() or not list((folder / "prove-runs").glob("*/manifest.json"))
    assert not spy.results("start")


def test_pf6_10_no_spec_in_the_folder_is_sweeps_refusal_naming_init(spy: Spy, tmp_path: Path) -> None:
    """The sweep screen's empty state, in a folder with no store and no ``prove.toml``: ``sweep``'s
    ``error:`` line and its ``next`` commands (``init``, and ``init --agent`` once the setup
    agent names it), and the app stays open."""
    folder = tmp_path / "empty"
    folder.mkdir()
    plain = cli("sweep", cwd=folder)  # refused at the plan, before any question
    assert plain.code in (1, 2)
    (error,) = plain.errors()

    async def scenario(s: Session) -> Grid:
        await s.press("s")
        sentence = error.removeprefix("error: ")[:40]
        g = await s.wait(lambda g: g.title() == "sweep" and g.message.startswith("error:") and says(g.text(), sentence), what="sweep's refusal")
        await s.press("q")
        return g

    rc, g = drive(scenario, cwd=folder, size=(120, 40))
    assert rc == 0 and _shows_error(g, error), (g.message, error)
    assert plain.nexts() and any("init" in c for c in plain.nexts()), plain.nexts()
    for command in plain.nexts():
        assert says(g.text(), command), (command, g.text())


def test_pf6_10_ctrl_c_during_the_apps_sweep_keeps_the_partial_run_and_says_so(tmp_path: Path) -> None:
    """Reading A14, in a pseudo-terminal: ``s``, ``y``, then Ctrl-C once progress shows: exit 130, the
    run partial, its event log ending ``interrupted``, and once the app has left the terminal the two
    lines ``sweep`` prints; then, the app opened again, ``s`` and ``y`` resume that run to the end (A24)."""
    home = tmp_path / "home2"
    home.mkdir()
    # slow while the file ``pf6-slow`` is in the folder, so Ctrl-C lands mid-sweep and the resume is quick
    (tmp_path / "pf6_slow_app.py").write_text(SLOW_TARGET.replace("    time.sleep(0.002)", "    if os.path.exists('pf6-slow'):\n        time.sleep(0.02)").replace("import time", "import os\nimport time"), encoding="utf-8")
    folder = _sweep_folder(tmp_path, "c", target="pf6_slow_app:rollout")
    (folder / "pf6-slow").write_text("", encoding="utf-8")
    run = run_pty([], home=home, cwd=folder, paths=(tmp_path,), cols=120, rows=40, timeout=120, steps=(
        Step(b"s", until="poisson-prove · home"), Step(b"y", until="[y/N]"), Step(b"\x03", until=" of 1,746", delay=0.5),
    ))
    assert run.code == 130, (run.code, after_app(run.out)[-500:])
    from poisson_prove.store import Store

    store = Store(folder / "prove-runs")
    (run_id,) = store.runs()
    assert store.manifest(run_id).status == "partial"
    events = [json.loads(line)["kind"] for line in (folder / "prove-runs" / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert events[-1] == "interrupted", events
    left = [line for line in after_app(run.out).splitlines() if line.strip()]
    name = cli("runs", "--json", cwd=folder)
    run_name = doc(name)["runs"][0]["run_name"]
    stopped = [line for line in left if line.startswith("stopped  ")]
    assert len(stopped) == 1 and re.match(rf'stopped  (?:interrupted: )?[\d,]+ of 1,746 rollouts kept in run "{re.escape(run_name)}" \(partial\)', stopped[0]), left[-3:]
    assert left[-1] == "  next: poisson-prove sweep --resume", left[-3:]
    # Launching the sweep again from the app resumes the partial run (reading A24).
    (folder / "pf6-slow").unlink()
    again = run_pty([], home=home, cwd=folder, paths=(tmp_path,), cols=120, rows=40, timeout=300, steps=(
        Step(b"s", until="poisson-prove · home"), Step(b"y", until="[y/N]"), Step(b"q", until="(complete)"),
    ))
    assert again.code == 0, after_app(again.out)[-500:]
    assert store.runs() == [run_id] and store.manifest(run_id).status == "complete", store.runs()
    kinds = [json.loads(line)["kind"] for line in (folder / "prove-runs" / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "resumed" in kinds and kinds[-1] == "finished", kinds


# ---------- PF6.11 chart links ----------

#: A page's address inside the UI, as a link on a screen shows it.
LINK = re.compile(r"(?<![\w/.])((?:comparisons|runs)/[\w./-]+\.html|index\.html)")
#: (screen, the kind of page its link opens, from ``views.md``'s table).
LINK_CASES = (
    ("home", "runs"), ("run", "run"), ("episodes", "episodes"), ("comparison", "chart"), ("condition", "chart"), ("could not detect", "chart"),
)


@pytest.mark.parametrize("screen,page", LINK_CASES, ids=[c[0] for c in LINK_CASES])
def test_pf6_11_each_link_names_a_page_that_exists_and_enter_opens_it_once(
    screen: str, page: str, qs_world: tuple[Path, dict[str, Any]], spy: Spy, opener: list[str], clipboard: list[str], tmp_path: Path
) -> None:
    """Reading A8: the screen's links are the addresses inside the UI ``views.md`` names for it (the
    verdict's the charts the comparison view lists, for the focused event at 80 columns and all at
    120); after the app shows a link its page exists, though the store had no UI before the app
    opened (the app builds the first); ``Tab`` focuses the first link, ``Enter`` opens it in the
    browser once, ``y`` copies its whole ``file://`` address; nothing opens on its own."""
    folder = _copy(qs_world, tmp_path)
    shutil.rmtree(folder / "prove-runs" / ".poisson" / "ui")
    ui = (folder / "prove-runs" / ".poisson" / "ui").resolve()

    async def scenario(s: Session) -> tuple[Grid, list[str]]:
        await reach(s, screen, saved=True)
        await s.wait(lambda g: LINK.search(g.text()) is not None, what="a link")
        before = list(opener)
        await s.press("tab")
        g = await s.settle()
        await s.press("enter")
        await s.settle()
        await s.press("y")
        await s.settle()
        return g, before

    _, (g, before) = drive(scenario, cwd=folder, size=(120, 40))
    assert before == [], before
    addresses = LINK.findall(g.text())
    assert addresses, g.text()
    for address in addresses:
        assert kind_of(address) == page, (screen, address)
        assert (ui / address).is_file(), (screen, address)
    if screen == "comparison":
        view = spy.views("comparison")[-1][1]
        assert sorted(addresses) == sorted(c["address"] for c in view["charts"]), (addresses, view["charts"])
    if screen == "condition":
        view = spy.views("condition")[-1][1]
        charts = [c["address"] for block in view["events"] for c in (block.get("charts") or [])] if isinstance(view.get("events"), list) else []
        assert charts and sorted(addresses) == sorted(charts), (addresses, charts)
    assert len(opener) == 1, opener
    assert opener[0].startswith("file://") and opener[0].split("#")[0] == (ui / addresses[0]).as_uri(), (opener, addresses[0])
    assert clipboard[-1:] == [opener[0]], clipboard


def test_pf6_11_a_store_that_cannot_be_written_shows_the_verdict_unsaved_with_no_link(small_world: tuple[Path, dict[str, Any]], spy: Spy, tmp_path: Path) -> None:
    """The verdict's empty state: the store is read-only: the verdict is shown, the
    message line is ``note: the comparison was not saved: <the system's words>``, and no chart link is
    shown, so none points at a missing page; the app renders the core's result itself (A4)."""
    folder = _copy(small_world, tmp_path)

    async def scenario(s: Session) -> dict[str, Any]:
        await reach(s, "home")
        await s.press("c")
        await s.wait_title("compare")
        await s.press("enter")
        await _verdict(s)
        g = await s.wait(lambda g: g.message.startswith("note:"), what="the note that it was not saved")
        out = {"verdict": g, "text": await s.read_through()}
        await s.press("q")
        return out

    with read_only(folder / "prove-runs"):
        _, out = drive(scenario, cwd=folder, size=(120, 40))
    g = out["verdict"]
    assert g.title() == "comparison"
    assert g.message.startswith("note: the comparison was not saved: "), g.message
    assert not re.search(r"comparisons/[0-9a-f]{16}", out["text"]), out["text"]
    result = as_document(spy.results("compare")[-1])
    assert _first_block(g).startswith(result["verdict"] + " ")


def test_pf6_the_app_saves_the_comparison_it_shows_and_names_it(small_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Comparing in the app saves the comparison into the store; the verdict screen's ``saved``
    line names it by its id's first 12 hex; comparing the same pair again is the same artifact."""
    folder = _copy(small_world, tmp_path)
    _, out = _compare_in_app(folder)
    (cid,) = saved_id(folder / "prove-runs")
    assert any(cid[:12] in line for line in _detail(out["text"], "saved")), out["text"]
    _compare_in_app(folder)
    assert saved_id(folder / "prove-runs") == [cid]


def test_pf6_the_picker_starts_on_previous_and_latest_and_refuses_a_partial_run(small_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """The picker's starting choice and its refusal (A11): the picker opens with ``previous`` before and ``latest`` after
    chosen; choosing a partial run shows one ``error:`` line naming it and saying it is partial, compares
    nothing and saves nothing."""
    folder = _copy(small_world, tmp_path)
    assert cli("sweep", "small.toml", "--yes", "--max-mde", "1", "--max-rollouts", "5", cwd=folder).code == 3
    names = {r["run_id"]: r for r in doc(cli("runs", "--json", cwd=folder))["runs"]}
    (partial,) = [r["run_name"] for r in names.values() if r["status"] == "partial"]
    a_name, b_name = small_world[1]["names"][small_world[1]["a"]], small_world[1]["names"][small_world[1]["b"]]

    async def scenario(s: Session) -> tuple[Grid, Grid]:
        await s.press("c")
        picker = await s.wait_title("compare")
        await s.focus_row(lambda row: partial in row)
        await s.press("space")
        refused = await s.wait(lambda g: g.message.startswith("error:"), what="the refusal")
        await s.press("q")
        return picker, refused

    _, (picker, refused) = drive(scenario, cwd=folder, size=(120, 40))
    assert any(says(line, "before") and says(line, a_name) for line in picker.rows) and any(says(line, "after") and says(line, b_name) for line in picker.rows), picker.text()
    assert partial in refused.message and "partial" in refused.message.replace(partial, ""), refused.message
    assert saved_id(folder / "prove-runs") == []


def test_pf6_home_in_a_folder_with_no_store_yet_is_its_empty_state(tmp_path: Path) -> None:
    """Reading A25, the first time a stranger opens the app (``01-home``'s empty state): no ``--store``
    given and no store in the folder yet: home says ``ok`` and that there are no runs, names
    ``poisson-prove init --example`` and offers the sweep key; no error. A store named by ``--store``
    that does not exist is ``runs``'s refusal (the next test)."""
    folder = tmp_path / "fresh"
    folder.mkdir()

    async def scenario(s: Session) -> Grid:
        g = await s.wait_title("home")
        await s.press("q")
        return g

    rc, g = drive(scenario, cwd=folder, size=(80, 24))
    assert rc == 0 and not g.message.startswith("error:"), g.message
    word, _ = split_first_line(g.body[0][2:])
    assert word == "ok" and says(_first_block(g), "no runs"), g.text()
    assert says(g.text(), "poisson-prove init --example") and re.search(r"\bs sweep\b", g.keybar), g.text()
    assert not (folder / "prove-runs").exists()


@pytest.mark.parametrize("case", ["missing store", "newer format"])
def test_pf6_a_store_the_core_refuses_is_runs_error_line_inside_the_app(case: str, small_world: tuple[Path, dict[str, Any]], spy: Spy, tmp_path: Path) -> None:
    """Reading A11 for the store: no store at the path given, and a store whose descriptor names a
    newer major format: the message line is ``runs``'s ``error:`` line on that store, its ``next``
    commands are on the screen, and ``q`` exits 0."""
    folder = _copy(small_world, tmp_path)
    store = "prove-runz" if case == "missing store" else None
    if case == "newer format":
        cli("ui", cwd=folder)
        descriptor = folder / "prove-runs" / ".poisson" / "store.json"
        data = json.loads(descriptor.read_text(encoding="utf-8"))
        descriptor.write_text(json.dumps({**data, "format": "poisson.store/2"}), encoding="utf-8")
    plain = cli(*(["--store", store] if store else []), "runs", cwd=folder)
    assert plain.code == 1
    (error,) = plain.errors()

    async def scenario(s: Session) -> Grid:
        g = await s.wait(lambda g: g.message.startswith("error:"), what="the refusal")
        await s.press("q")
        return g

    rc, g = drive(scenario, cwd=folder, store=store, size=(120, 40))
    assert rc == 0 and _shows_error(g, error), (g.message, error)
    for command in plain.nexts():
        assert says(g.text(), command), command


# ---------- PF6.12 no network, no key, writes only through the core ----------


def test_pf6_12_a_tour_of_every_screen_makes_no_network_call_reads_no_key_and_writes_only_through_the_core(
    qs_world: tuple[Path, dict[str, Any]], spy: Spy, opener: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _empty_home: Path
) -> None:
    """Every screen visited, a comparison made, a sweep declined, with every network connection and
    name lookup refused and recorded by an audit hook (a Unix socket is no network), and the planted keys set: no network attempt, no browser opened, no
    planted key's value on any screen or in any file written (A13); the store's files outside
    ``.poisson/`` and the folder's ``prove.toml`` byte for byte as they were; ``HOME`` gains files only
    under ``.cache/poisson-prove/``."""
    folder = _copy(qs_world, tmp_path)
    store_before = listing(folder / "prove-runs", outside=(".poisson",))
    folder_before = {k: v for k, v in listing(folder).items() if not k.startswith("prove-runs/")}
    home_before = listing(_empty_home)

    async def scenario(s: Session) -> list[str]:
        texts = [g.text() for g in await _tour(s, saved=False)]
        for _ in range(8):
            if s.grid().title() == "home":
                break
            await s.press("escape")
            await s.settle()
        await s.press("s")
        await s.wait_text("[y/N]")
        texts.append(s.grid().text())
        await s.press("n")
        await s.settle()
        await s.press("q")
        if s.app.is_running:
            await s.press("q")
        return texts

    with network_attempts() as attempts:
        rc, texts = drive(scenario, cwd=folder, size=(120, 40))
    assert rc == 0 and attempts == [] and opener == []
    assert listing(folder / "prove-runs", outside=(".poisson",)) == store_before
    assert {k: v for k, v in listing(folder).items() if not k.startswith("prove-runs/")} == folder_before
    new_home = set(listing(_empty_home)) - set(home_before)
    assert all(p.startswith(".cache/") and (p.startswith(".cache/poisson-prove") or p == ".cache/") for p in new_home), sorted(new_home)
    written = [p for p in (folder / "prove-runs" / ".poisson").rglob("*") if p.is_file()] + [p for p in _empty_home.rglob("*") if p.is_file()]
    for value in PLANTED_KEYS.values():
        assert not any(value in t for t in texts)
        assert not [p for p in written if value.encode() in p.read_bytes()], value
    assert spy.results("compare") and saved_id(folder / "prove-runs")


# ---------- PF6.13 a window too small ----------


@pytest.mark.parametrize("size", [(79, 24), (80, 23), (72, 20)], ids=["79x24", "80x23", "72x20"])
def test_pf6_13_below_80_by_24_the_app_names_the_size_it_needs_and_keeps_running(size: tuple[int, int], small_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Reading A15: below 80 × 24 the screen holds one line naming the window's size and the size the
    app needs, with ``q quit``, and the app keeps running; made 80 × 24, home is drawn; made small again,
    the line is back; ``q`` exits 0."""
    folder = _copy(small_world, tmp_path)
    w, h = size
    line = f"the window is {w} × {h}; the app needs at least 80 × 24"

    async def scenario(s: Session) -> None:
        g = await s.settle()
        assert [r.strip() for r in g.rows if r.strip() and "q quit" not in r] == [line], g.text()
        assert any("q quit" in r for r in g.rows) and s.app.is_running
        await s.pilot.resize_terminal(80, 24)
        await s.wait_title("home")
        await s.pilot.resize_terminal(w, h)
        g = await s.wait(lambda g: line in g.text(), what="the size line")
        await s.press("q")

    assert _rc(drive(scenario, cwd=folder, size=size)) == 0


# ---------- PF6.14 snapshots ----------

#: The snapshots: (size, the way from home), on the 0.0.1 quickstart pair (A12). At most eight.
SNAPSHOT_SCREENS: dict[str, tuple[str, tuple[str, ...]]] = {
    "home-80x24": ("80x24", ()),
    "home-120x40": ("120x40", ()),
    "comparison-80x24": ("80x24", ("comparison",)),
    "comparison-120x40": ("120x40", ("comparison",)),
    "conditions-120x40": ("120x40", ("conditions",)),
    "condition-120x40": ("120x40", ("condition",)),
    "could-not-detect-80x24": ("80x24", ("could not detect",)),
    "help-80x24": ("80x24", ("help",)),
}


def _snapshot_text(g: Grid, cid: str, keep: set[str]) -> str:
    return normalise("\n".join(g.rows), comparison=cid, keep=keep) + "\n\n" + "\n".join(g.masks) + "\n"


@pytest.mark.parametrize("name", list(SNAPSHOT_SCREENS))
def test_pf6_14_snapshot(name: str, old_world: tuple[Path, dict[str, Any]], request: pytest.FixtureRequest, tmp_path: Path) -> None:
    """One screen of the 0.0.1 quickstart pair, whole, rows and colour roles, against its snapshot;
    rewritten only by the documented command and reviewed in the pull request."""
    folder = _copy(old_world, tmp_path)
    size, path = SNAPSHOT_SCREENS[name]

    async def scenario(s: Session) -> Grid:
        if not path:
            return await s.settle()
        return await reach(s, path[0], saved=True)

    _, g = drive(scenario, cwd=folder, size=SIZES[size])
    text = _snapshot_text(g, old_world[1]["comparison"], run_times(folder / "prove-runs"))
    snapshot = SNAPSHOTS / f"{name}.txt"
    if request.config.getoption("--update-snapshots"):
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(text, encoding="utf-8")
        return
    assert snapshot.is_file(), f"no snapshot {snapshot.relative_to(ROOT)}; write it with: {SNAPSHOT_COMMAND}"
    assert text == snapshot.read_text(encoding="utf-8"), f"{name} differs from {snapshot.relative_to(ROOT)}; if the change is meant, rewrite it with: {SNAPSHOT_COMMAND}"


def test_pf6_14_the_snapshots_are_few_and_written_only_by_the_documented_command() -> None:
    """At most eight, exactly the screens above, each a grid of the screen's size with its mask, and
    ``CONTRIBUTING.md`` names the one command that rewrites them."""
    assert len(SNAPSHOT_SCREENS) <= 8
    assert SNAPSHOTS.is_dir() and sorted(p.name for p in SNAPSHOTS.iterdir()) == sorted(f"{n}.txt" for n in SNAPSHOT_SCREENS)
    for name, (size, _) in SNAPSHOT_SCREENS.items():
        w, h = SIZES[size]
        rows, masks = (SNAPSHOTS / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n").split("\n\n", 1)
        assert [len(r) for r in rows.split("\n")] == [w] * h or len(rows.split("\n")) == h, name
        assert len(masks.split("\n")) == h and set("".join(masks.split("\n"))) <= set(" BDGYRV"), name
    contributing = ROOT / "CONTRIBUTING.md"
    assert contributing.is_file() and SNAPSHOT_COMMAND in contributing.read_text(encoding="utf-8")


# ---------- PF6.15 Textual missing ----------


def test_pf6_15_without_textual_no_arguments_on_a_terminal_is_one_error_and_every_verb_still_runs(small_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """Reading A16: Textual unimportable: no verb on a terminal prints one ``error:`` line naming the
    terminal app and saying it cannot start, then ``  next: poisson-prove --help``, nothing on stdout,
    exit 1; the verbs print what they print with Textual installed."""
    folder = _copy(small_world, tmp_path)
    home = tmp_path / "home2"
    home.mkdir()
    no_textual = blocker(tmp_path / "no-textual", "textual")
    run = run_pty([], home=home, cwd=folder, paths=(no_textual,), cols=80, rows=24, stdout="pty", stderr="own", timeout=60)
    assert run.code == 1, (run.code, run.err)
    assert strip_escapes(run.out).strip() == "", run.out
    lines = strip_escapes(run.err).splitlines()
    assert len(lines) == 2 and lines[1] == "  next: poisson-prove --help", lines
    assert lines[0].startswith("error: ") and says(lines[0], "app") and says(lines[0], "cannot start"), lines[0]
    for argv in (["runs"], ["diff"], ["--help"], ["sweep", "small.toml", "--dry-run", "--max-mde", "1"]):
        with_it = prove(argv, home=home, cwd=folder)
        without = prove(argv, home=home, cwd=folder, paths=(no_textual,))
        assert (without.code, without.out, without.err) == (with_it.code, with_it.out, with_it.err), argv


async def _key_v(s: Session, w: dict[str, Any]) -> None:
    await reach(s, "conditions", saved=True)
    await s.press("v")
    await s.wait_title("comparison")


async def _key_l(s: Session, w: dict[str, Any]) -> None:
    a, b = w["names"][w["a"]], w["names"][w["b"]]
    await reach(s, "compare")
    await s.focus_row(lambda row: w["b"] in row)
    await s.press("space")
    g = await s.settle()
    assert _detail(g.text(), "before") and says(_detail(g.text(), "before")[0], b), g.text()
    await s.press("l")
    g = await s.settle()
    assert says(_detail(g.text(), "before")[0], a) and says(_detail(g.text(), "after")[0], b), g.text()


async def _key_e_condition(s: Session, w: dict[str, Any]) -> None:
    g = await reach(s, "condition", saved=True)
    first = g.body[0]
    events = [e for e in ("timeout", "violated") if e in first]
    assert len(events) == 1, first
    await s.press("e")
    g = await s.settle()
    assert ({"timeout", "violated"} - set(events)).pop() in g.body[0], (first, g.body[0])


async def _key_e_episodes(s: Session, w: dict[str, Any]) -> None:
    g = await reach(s, "episodes", run_row=lambda row: True)
    first = g.body[0]
    await s.press("e")
    g = await s.settle()
    assert g.title() == "episodes" and g.body[0] != first, (first, g.body[0])


async def _key_g(s: Session, w: dict[str, Any]) -> None:
    g = await reach(s, "run")
    assert not says(g.text(), "planned"), g.text()
    await s.press("g")
    g = await s.settle()
    assert says(g.text(), "event log") and says(g.text(), "planned"), g.text()


async def _key_filter(s: Session, w: dict[str, Any]) -> None:
    await reach(s, "runs")
    await s.press("/", *w["a"][-4:])
    g = await s.settle()
    assert w["a"] in g.text() and w["b"] not in g.text(), g.text()
    await s.press("escape")
    g = await s.settle()
    assert g.title() == "runs" and w["a"] in g.text() and w["b"] in g.text(), g.text()


async def _key_y_command(s: Session, w: dict[str, Any]) -> None:
    await reach(s, "run")
    await s.focus_row(lambda row: "refund" in row and "0.55" in row)  # a condition with timeouts
    await s.press("enter")
    await s.wait_title("episodes")
    await s.wait(lambda g: "rollout" in g.text(), what="the reproduce lines")
    clipboard = w["clipboard"]
    await s.press("y")
    g = await s.settle()
    assert clipboard, "nothing was copied"
    copied = clipboard[-1]
    assert "rollout" in copied and "seed=" in copied, copied
    assert squash(copied) in squash(g.text()), (copied, g.text())


async def _key_c_runs(s: Session, w: dict[str, Any]) -> None:
    await reach(s, "runs")
    await s.focus_row(lambda row: w["a"] in row)
    await s.press("c")
    g = await s.wait_title("compare")
    assert says(_detail(g.text(), "after")[0], w["names"][w["a"]]), g.text()


async def _links_follow(s: Session, w: dict[str, Any]) -> None:
    g = await reach(s, "comparison", saved=True)
    first = re.findall(r"comparisons/\S+?-(\w+)\.html", g.text())
    assert len(set(first)) == 1, first
    await s.press("down")
    g = await s.settle()
    second = re.findall(r"comparisons/\S+?-(\w+)\.html", g.text())
    assert len(set(second)) == 1 and set(second) != set(first), (first, second)


#: (the key, the size, what it does): the design's screen letters and the shared keys,
#: each shown doing what its screen's page says, on the quickstart as this build sweeps it.
KEY_CASES: dict[str, tuple[tuple[int, int], Callable[[Session, dict[str, Any]], Awaitable[None]]]] = {
    "v back to the verdict": ((120, 40), _key_v),
    "l previous and latest": ((120, 40), _key_l),
    "e the other event at 80": ((80, 24), _key_e_condition),
    "e the next event of the episodes": ((80, 24), _key_e_episodes),
    "g the event log at 80": ((80, 24), _key_g),
    "/ filters and esc clears": ((120, 40), _key_filter),
    "y copies the reproduce lines whole": ((80, 24), _key_y_command),
    "c on runs takes the focused run as after": ((120, 40), _key_c_runs),
    "the chart links follow the focused event at 80": ((80, 24), _links_follow),
}


@pytest.mark.parametrize("case", list(KEY_CASES))
def test_pf6_each_screens_own_keys_do_what_the_design_says(
    case: str, qs_world: tuple[Path, dict[str, Any]], clipboard: list[str], tmp_path: Path
) -> None:
    """The keys: ``v`` from the conditions back to the verdict; ``l`` in the picker
    puts ``previous`` and ``latest`` back; ``e`` shows a condition's other event at 80 columns and the
    episodes of the next event; ``g`` shows the run's event log at 80; ``/`` filters a table and ``Esc``
    clears the filter, staying on the screen; ``y`` copies a command whole, as the screen shows it, never
    cut; ``c`` on the runs screen takes the focused run as ``after``; the verdict's chart links are the
    focused event's at 80 and follow the focus."""
    folder = _copy(qs_world, tmp_path)
    size, scenario = KEY_CASES[case]

    async def run(s: Session) -> None:
        await scenario(s, {**qs_world[1], "clipboard": clipboard})
        await s.press("q")

    assert _rc(drive(run, cwd=folder, size=size)) == 0


def test_pf6_help_lists_every_key_and_every_screen(small_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """The help screen (``11-help``) at 120 × 40: every shared key of the look file's table, every
    screen's own letter and the screens, with Esc back to where it was opened."""
    folder = _copy(small_world, tmp_path)

    async def scenario(s: Session) -> str:
        await reach(s, "help")
        text = await s.read_through()
        await s.press("escape")
        await s.wait_title("home")
        return text

    _, text = drive(scenario, cwd=folder, size=(120, 40))
    # A key is listed when it is in the first cell of a row: the key column, before two spaces.
    cells = [m.group(1).split() for m in (re.match(r"^\s+(\S+(?: \S+)*?)(?:\s{2,}|$)", row) for row in text.splitlines()) if m]
    for key in ("↑ ↓", "PgUp", "PgDn", "Home", "End", "enter", "esc", "tab", "/", "y", "?", "q", "ctrl-c",
                "s", "c", "r", "t", "d", "v", "e", "g", "p", "l", "space"):
        words = key.split()
        assert any(cell[i:i + len(words)] == words for cell in cells for i in range(len(cell))), (key, cells[:30])
    for screen in ("home", "runs", "run", "sweep", "compare", "comparison", "conditions", "condition", "episodes", "could not detect"):
        assert says(text, screen), screen


def test_pf6_a_0_0_1_run_says_its_events_were_not_recorded(old_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """The run screen's old state (the design's ``03-run``): a 0.0.1 run says its events
    were not recorded, in the words every static view uses; its design limit is whatever the run view
    carries for it (computed at read time, PF4.4), held by the facts test."""
    folder = _copy(old_world, tmp_path)
    async def scenario(s: Session) -> str:
        await reach(s, "run", run_row=lambda row: QS_B in row)  # the id column shows at 120
        return await s.read_through()

    _, text = drive(scenario, cwd=folder, size=BIG)
    assert says(text, "events were not recorded"), text[:800]
