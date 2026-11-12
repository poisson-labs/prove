"""C5 of 0.3.0, Remote backends: the terminal app's "Where sweeps run" page.

The frozen tests for W7 (Remote Backends Spec §3.2, §3.4, §15 C5). W8, a cloud sweep started
from the app, is ``test_rb_where_cluster.py``, with the tests that start the fake coordinator.

The app is driven as its other pages are (``pf6_support``): Textual's pilot, keys in, the screen
read as text; the cloud's readiness is the fakes of ``rb_cloud_support.py``. No test here starts
the cluster software.

**What the tests fix that the invariant leaves open** (each a yes/no of this session):

- The page's title is ``where`` (its header ``poisson-prove · where``); ``w`` opens it from home
  with no run yet (the first-run screen) and from the runs page. It shows the sentence bare
  ``where`` prints and its readiness lines.
- Changing the answer in the app: ``Enter`` asks the terminal's question; a digit answers it;
  each further question shows its default and ``Enter`` takes it. The table is written by
  ``_where.write``, and the page then shows the spec as it now is.
- With no ``prove.toml`` in the folder the page says this machine, and no key on it writes a
  file.
"""

from __future__ import annotations

import io
import time
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pf6_support import Grid, Session, drive, says
from poisson_prove import cli
from rb_cloud_support import MASKED, CloudWorld, Done, Pool, world
from test_rb_cloud_life import assert_no_forbidden_route
from test_rb_where import ALL_FLAGS, CLOUD_PROMPTS, DEFAULT_CLOUD, QUESTION, READY

FIRST_RUN_LINE = "where  this machine (press w to run sweeps on Modal or your cloud account)"
SIZE = (160, 44)


@pytest.fixture(autouse=True)
def _app_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE", "XDG_CACHE_HOME", "NO_COLOR", "CI", "TEXTUAL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fresh_pool() -> Any:
    own = Pool(2)
    yield own
    own.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_pool: Pool) -> Iterator[CloudWorld]:
    monkeypatch.setenv("COLUMNS", "250")
    with world(tmp_path, monkeypatch, fresh_pool) as made:
        # The app is opened as a stranger opens it: no --store, the folder's own ./prove-runs.
        made.store = made.root / "prove-runs"
        yield made
        assert_no_forbidden_route(made)


def run(w: CloudWorld, *args: str) -> Done:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(list(args), stdout=out, stderr=err, stdin=io.StringIO(""))
    return Done(code, out.getvalue(), err.getvalue())


def cloud_spec(w: CloudWorld) -> None:
    assert run(w, "init", "--example").code == 0
    done = run(w, "where", "cloud", *ALL_FLAGS, "--yes")
    assert done.code == 0, done


def in_app(w: CloudWorld, scenario: Any) -> tuple[int | None, Any]:
    return drive(scenario, cwd=w.root, store=None, size=SIZE)


async def leave(s: Session) -> None:
    await s.press("q")
    for _ in range(100):
        if not s.app.is_running:
            return
        await s.pilot.pause(0.05)


async def gone(s: Session, within: float) -> None:
    until = time.monotonic() + within
    while s.app.is_running:
        assert time.monotonic() < until, f"the app was still running after {within} s; the screen:\n{s.grid().text()}"
        await s.pilot.pause(0.1)


def body_text(g: Grid) -> str:
    return "\n".join(row.rstrip() for row in g.rows)


# ---------- W7: the page ----------


def test_w7_the_first_run_screen_carries_the_where_line_before_its_next_lines(w: CloudWorld) -> None:
    async def scenario(s: Session) -> Grid:
        g = await s.wait_title("home")
        await leave(s)
        return g

    rc, g = in_app(w, scenario)
    assert rc == 0, g.text()
    rows = [" ".join(row.split()) for row in g.rows]
    line = " ".join(FIRST_RUN_LINE.split())
    at = [i for i, row in enumerate(rows) if row == line]
    assert len(at) == 1, g.text()
    first_next = next(i for i, row in enumerate(rows) if "poisson-prove init --example" in row)
    assert at[0] < first_next, g.text()
    assert says(g.text(), "no runs"), g.text()


@pytest.mark.parametrize("opened_from", ["the first-run screen", "the runs page"])
def test_w7_w_opens_the_page_and_it_shows_the_answer_and_its_readiness(w: CloudWorld, opened_from: str) -> None:
    cloud_spec(w)
    command = run(w, "where")
    assert command.out.splitlines()[0] == READY, command

    async def scenario(s: Session) -> tuple[Grid, Grid]:
        await s.wait_title("home")
        if opened_from == "the runs page":
            await s.press("r")
            await s.wait_title("runs")
        await s.press("w")
        g = await s.wait_title("where")
        g = await s.wait(lambda g: says(g.text(), "signed in, ready"), 90, "the readiness")
        await s.press("escape")
        back = await s.settle()
        await leave(s)
        return g, back

    rc, (g, back) = in_app(w, scenario)
    assert rc == 0, g.text()
    assert says(g.text(), READY.split("  ", 1)[1]), g.text()
    assert says(g.text(), f"signed in AWS {MASKED}"), g.text()
    assert back.title() == ("runs" if opened_from == "the runs page" else "home"), back.text()
    assert w.routes() == [] and w.heads() == [], "opening the page started the cluster software"


def test_w7_changing_it_asks_the_terminals_questions_writes_through_where_and_rereads_the_spec(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    from poisson_prove import _where

    assert run(w, "init", "--example").code == 0
    before = w.spec.read_bytes()
    writes: list[tuple[str, str]] = []
    real = _where.write

    def spying(spec_path: Any, table: str, *args: Any, **kwargs: Any) -> Any:
        writes.append((str(spec_path), table))
        return real(spec_path, table, *args, **kwargs)

    monkeypatch.setattr(_where, "write", spying)

    async def scenario(s: Session) -> dict[str, Any]:
        seen: dict[str, Any] = {}
        await s.wait_title("home")
        await s.press("w")
        seen["first"] = await s.wait(lambda g: g.title() == "where" and says(g.text(), "this machine"), 60, "the page")
        await s.press("enter")
        seen["question"] = await s.wait(lambda g: says(g.text(), QUESTION), 60, "the question")
        await s.press("3")
        prompts = []
        for prompt in CLOUD_PROMPTS:
            prompts.append(await s.wait(lambda g, p=prompt: says(g.text(), p), 60, prompt))
            await s.press("enter")
        seen["cloud"] = await s.wait(lambda g: says(g.text(), "signed in, ready"), 90, "the page to re-read the spec")
        seen["spec-cloud"] = w.spec.read_bytes()
        seen["writes-cloud"] = len(writes)
        await s.press("enter")
        await s.wait(lambda g: says(g.text(), QUESTION), 60, "the question again")
        await s.press("1")
        seen["local"] = await s.wait(lambda g: says(g.text(), "this machine") and not says(g.text(), "your AWS account"),
                                     60, "this machine again")
        await leave(s)
        return seen

    rc, seen = in_app(w, scenario)
    assert rc == 0, seen
    assert seen["spec-cloud"].startswith(before), "the app changed the spec's own bytes"
    assert tomllib.loads(seen["spec-cloud"].decode())["cloud"] == DEFAULT_CLOUD
    assert says(seen["cloud"].text(), READY.split("  ", 1)[1]), seen["cloud"].text()
    assert seen["writes-cloud"] == 1 and len(writes) == 2, writes
    assert all(Path(path).name == "prove.toml" for path, _ in writes), writes
    assert writes[0][1].lstrip().startswith("[cloud]") and writes[1][1] == "", writes
    assert w.spec.read_bytes() == before, "this machine did not take the table out again"


def test_w7_with_no_spec_in_the_folder_the_page_says_this_machine_and_writes_nothing(w: CloudWorld) -> None:
    async def scenario(s: Session) -> Grid:
        await s.wait_title("home")
        await s.press("w")
        g = await s.wait(lambda g: g.title() == "where" and says(g.text(), "this machine"), 60, "the page")
        for key in ("enter", "3", "enter", "enter", "enter", "enter", "enter"):
            if s.app.is_running:
                await s.press(key)
        await s.settle()
        if s.app.is_running:
            await s.press("escape")
            await leave(s)
        return g

    in_app(w, scenario)
    assert sorted(p.name for p in w.root.iterdir() if p.suffix == ".toml") == [], "the app wrote a spec of its own"
    assert w.aws_calls() == [] or all(c["argv"][0] in ("sts", "service-quotas") for c in w.aws_calls())
