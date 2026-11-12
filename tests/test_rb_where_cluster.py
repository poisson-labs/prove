"""C5 of 0.3.0, Remote backends: a cloud sweep started from the terminal app, and ``where``
finding what an earlier sweep left.

The frozen tests for W8 (Remote Backends Spec §3.2, §15 C5), and for the half of §6.6 and §9
step 2 that belongs to the ``where`` verb: "a leftover is listed and stopped here too", which is
where a failed stop's ``next: poisson-prove where`` sends the reader. Every test here starts the
fake coordinator, so the file runs with the cluster's other lifecycle tests.

The app is driven by Textual's pilot (``pf6_support``) with the cloud backend's seams set in this
process, where the app runs its sweep in a worker thread.

**What the tests fix that the invariants leave open** (each a yes/no of this session):

- **Ctrl-C in the app during a cloud sweep is the command line's Ctrl-C**: the job in flight is
  cancelled at once (not at its next finished batch: nodes bill while it waits), the cluster is
  stopped once, the ledger's line closes ``cancelled``, the run is partial with ``interrupted``
  last, and the app leaves with 130.
- ``where`` with a record not ``stopped`` stops what was left before it says where the spec runs,
  with the note the next sweep would print; when that stop cannot be confirmed it prints the
  line of a stop that could not be confirmed, leaves the record as it was and exits 3.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pf6_support import Grid, Session, says
from rb_cloud_support import MASKED, CloudWorld, Pool, cloud_table, world
from test_rb_cloud_life import DONE_ORDER, assert_no_forbidden_route, count, ended_clean, timeline
from test_rb_cloud_stop import LEFT_CLOSED, UNCONFIRMED, state
from test_rb_where import READY
from test_rb_where_app import cloud_spec, gone, in_app, leave, run


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


# ---------- W8: a cloud sweep from the app ----------


def test_w8_a_sweep_started_from_the_app_calls_the_cluster_exactly_as_the_command_lines(w: CloudWorld) -> None:
    cloud_spec(w)
    plan = run(w, "--store", str(w.store), "sweep", "--dry-run")
    assert plan.code == 0 and "on your AWS account" in plan.out.splitlines()[0], plan

    async def scenario(s: Session) -> tuple[Grid, Grid]:
        await s.wait_title("home")
        await s.press("s")
        asked = await s.wait(lambda g: g.title() == "sweep" and says(g.text(), "[y/N]"), 120, "the plan and its question")
        await s.press("y")
        done = await s.wait(lambda g: any(row.strip().startswith("done ") for row in g.rows), 240, "the sweep to end")
        await leave(s)
        return asked, done

    rc, (asked, done) = in_app(w, scenario)
    assert rc == 0, done.text()
    assert says(asked.text(), "on your AWS account") and says(asked.text(), f"Account: AWS {MASKED}"), asked.text()
    assert timeline(w) == DONE_ORDER, timeline(w)
    assert ended_clean(w) == [], done.text()
    assert [e["event"] for e in w.ledger("cloud-ledger.jsonl")] == ["open", "close"], w.ledger("cloud-ledger.jsonl")
    assert w.ledger("cloud-ledger.jsonl")[-1]["ended"] == "complete"
    assert says(done.text(), "cluster 4 × m7i.2xlarge up"), done.text()
    (run_,) = w.runs()
    assert run_["status"] == "complete" and run_["backend"] == "cloud", run_


def test_w8_ctrl_c_in_the_app_cancels_the_job_stops_the_cluster_and_leaves_130(w: CloudWorld) -> None:
    marker = w.root / "held.marker"
    w.write_spec(table=cloud_table(batch_size=20, max_cost=20.0), cells=("fast", "hold"), replicates=130,
                 axes={"marker": [str(marker)]}, target="bu_targets.cloud:hold")

    async def scenario(s: Session) -> float:
        await s.wait_title("home")
        await s.press("s")
        await s.wait(lambda g: g.title() == "sweep" and says(g.text(), "[y/N]"), 120, "the plan and its question")
        await s.press("y")
        until = time.monotonic() + 180
        while not marker.exists():
            assert time.monotonic() < until and s.app.is_running, f"the job never held:\n{s.grid().text()}"
            await s.pilot.pause(0.1)
        # Wait until nothing more arrives: every batch still in flight is one that holds, so only
        # cancelling the job itself can end the sweep.
        still, last = time.monotonic(), s.grid().text()
        while time.monotonic() - still < 4:
            await s.pilot.pause(0.2)
            now = re.sub(r"\d[\d.]* (?:s|min)\b", "", s.grid().text())
            if now != last:
                still, last = time.monotonic(), now
        pressed = time.monotonic()
        await s.press("ctrl+c")
        try:
            await gone(s, 90)
        except AssertionError:
            # Let the sweep end, so a build that waits for the job fails here and does not hang.
            w.pool.stop()
            raise
        return time.monotonic() - pressed

    rc, took = in_app(w, scenario)
    assert rc == 130, rc
    assert took < 90, f"the app took {took:.0f} s to leave: the job was not cancelled, it was waited for"
    assert count(w, "cluster stop") == 1, timeline(w)
    assert ended_clean(w) == [], timeline(w)
    ledger = w.ledger()
    assert [e["event"] for e in ledger] == ["open", "close"] and ledger[-1]["ended"] == "cancelled", ledger
    (run_,) = w.runs()
    assert run_["status"] == "partial", run_
    events = w.events(run_["run_id"])
    assert events[-1].get("kind", events[-1].get("event")) == "interrupted", events[-1]


def test_w8_ctrl_c_in_the_app_while_batches_still_arrive_ends_the_same_way(w: CloudWorld) -> None:
    """The other moment: batches are still coming back when Ctrl-C is pressed. However the sweep
    notices the press, the ending is the interrupt's: the ledger's line closes ``cancelled``."""
    w.write_spec(table=cloud_table(batch_size=4, max_cost=20.0), cells=("a", "b"), replicates=130,
                 target="bu_targets.cloud:slow")

    async def scenario(s: Session) -> None:
        await s.wait_title("home")
        await s.press("s")
        await s.wait(lambda g: g.title() == "sweep" and says(g.text(), "[y/N]"), 120, "the plan and its question")
        await s.press("y")
        await s.wait(lambda g: bool(re.search(r"\b(?:[4-9]|\d\d) of 260\b", g.text())), 180, "the first batches")
        await s.press("ctrl+c")
        await gone(s, 90)

    rc, _ = in_app(w, scenario)
    assert rc == 130, rc
    assert count(w, "cluster stop") == 1 and ended_clean(w) == [], timeline(w)
    ledger = w.ledger()
    assert [e["event"] for e in ledger] == ["open", "close"] and ledger[-1]["ended"] == "cancelled", ledger
    (run_,) = w.runs()
    assert run_["status"] == "partial", run_


# ---------- §6.6 and §9 step 2: where finds what was left ----------


def _leave_stopping(w: CloudWorld) -> str:
    cloud_spec(w)
    w.script_cluster(stop_leaves=1)
    w.set_constant("_STOP_POLL_S", 1.0)
    done = run(w, "--store", str(w.store), "sweep", "--yes")
    assert done.code == 3 and state(w) == "stopping", done
    assert done.nexts[-1] == "next: poisson-prove where", done
    return str(w.record()["run_id"])  # type: ignore[index]


def test_where_stops_what_an_earlier_sweep_left_and_says_so(w: CloudWorld) -> None:
    _leave_stopping(w)
    w.script_cluster()
    done = run(w, "--store", str(w.store), "where")
    assert done.code == 0, done
    notes = [line for line in done.err.splitlines() if line.startswith("note: the cluster from")]
    assert len(notes) == 1 and LEFT_CLOSED.match(notes[0]), done.err
    assert done.out.splitlines()[0] == READY, done
    assert state(w) == "stopped" and ended_clean(w) == [], w.record()
    assert count(w, "cluster start") == 1, "where started a cluster"
    assert run(w, "--store", str(w.store), "where").err == "", "the leftover was reported twice"


def test_where_that_cannot_confirm_the_stop_says_so_and_leaves_the_record(w: CloudWorld) -> None:
    _leave_stopping(w)
    before = w.record()
    done = run(w, "--store", str(w.store), "where")
    assert done.code == 3, done
    (error,) = done.errors
    match = UNCONFIRMED.match(error)
    assert match and match["listed"] == "1", done
    assert w.record() == before, "the record changed though the stop was not confirmed"
    assert not [e for e in w.ledger("cloud-ledger.jsonl") if e.get("ended") == "lost"]
