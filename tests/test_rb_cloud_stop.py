"""The cluster's stop, where the first build of 0.3.0's cloud backend went past its frozen tests.

Pair 2's build added behaviour no test pinned (its yes/no 5, ruled yes: each stands, and each gets
a test here). One test or more per behaviour, on the fakes of ``rb_cloud_support.py``:

- **S1, one signal handler from before the record to after the stop.** Ctrl-C, SIGTERM or SIGHUP
  is an interrupt from the moment the ownership record is written, the coordinator's start
  included; and from the first press on, no later press interrupts the way to the stop: a second
  press that lands while the job is still being cancelled is the stop's one note, and the stop
  completes.
- **S2, the coordinator of a start that failed or was interrupted is stopped.** The cluster
  software starts its coordinator, records it, and only then waits for it; a start that fails or
  is interrupted in that wait leaves the process running (1.8.4 ``_local_head.py:808-834``). It
  is Prove's own, so Prove stops it, and the next sweep is not refused as finding a coordinator
  Prove did not start.
- **S3, what an earlier sweep left is called stopped only when it is.** A leftover whose stop
  cannot be confirmed refuses the new sweep, exit 1, with the line of a stop that could not be
  confirmed and ``next: poisson-prove where``; nothing of the new sweep is recorded or started, the
  record stays as it was, and no ledger line is closed ``lost``. The sweep after, when the stop
  can be confirmed, finishes it.
- **S4, a record ``stopping`` whose process is alive is another sweep**: the second sweep is
  refused as while the first runs, and nothing is called.
- **S5, a coordinator that will not stop** leaves the record ``stopping`` with one note; the next
  cloud sweep stops it.
- **S6, the coordinator's own log is copied beside the record when it stops**, and the record's
  coordinator entry carries its port.
- **S7, the AWS CLI's calls each run in a session of their own with a 120 s limit**; a sign-in
  call that does not answer reads as not signed in, and a quota call that does not answer as a
  quota not read (one note, the plan goes on).

**What the tests fix that the build left open:**

- The three sentences the build chose (ruled, its yes/no 6) are pinned word for word: the note
  ``the cluster software Prove started on this machine did not stop (process N); the next cloud
  sweep stops it``; the leftover note's ending ``its ledger line was closed when it ended``; and
  nothing else of the stopped verdict.
- The limit of one AWS CLI call is ``_where_checks._CLI_S`` (120 s); the tests shorten it.
- The copied log is ``aws-<account>.head.log`` beside the record.
- **S8, a finding of this pair:** the coordinator's start fails with the software's own text, not
  with a code. 1.8.4 says ``Burla's local service never became ready (see .../head.log).``,
  ``Burla's local service failed to start:`` and ``Burla could not establish its relay tunnel
  through ...`` (``_local_head.py:984-1011``, ``:1104-1122``). The first two are §7.4's "the cluster
  software did not start on this machine; the details are in <log>", the third its "the cluster
  could not open its connection to this machine; ..."; none is an unexpected failure, and the
  software's text stays in the log. A contract test reads the three texts from the installed pin.
"""

from __future__ import annotations

import importlib.util
import os
import re
import signal
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from rb_cloud_support import (
    ACCOUNT,
    PIN,
    REGION,
    CloudWorld,
    Pool,
    alive,
    cloud_module,
    cloud_table,
    wait_for,
    world,
)
from test_rb_cloud_life import (
    DONE_ORDER,
    NOTE_SECOND,
    assert_no_forbidden_route,
    count,
    ended_clean,
    finish,
    hold_spec,
    interrupted_run,
    start_held,
    timeline,
)

NOT_STOPPED = re.compile(
    r"^note: the cluster software Prove started on this machine did not stop \(process (?P<pid>\d+)\); "
    r"the next cloud sweep stops it$"
)
LEFT_CLOSED = re.compile(
    r'^note: the cluster from the sweep of "[^"]+" had not stopped; Prove stopped it '
    r"\(up since \d\d:\d\dZ, its ledger line was closed when it ended\)$"
)
UNCONFIRMED = re.compile(
    rf"^error: the nodes may still be running in {REGION}; Prove could not confirm they stopped "
    r"\((?P<listed>\d+) listed after .+\)$"
)
NOT_STARTED = re.compile(r"^error: the cluster software did not start on this machine; the details are in (?P<log>\S+)$")
NO_CONNECTION = ("error: the cluster could not open its connection to this machine; check this machine's "
                 "network and run the sweep again")
#: 1.8.4's own words when its coordinator does not start, as ``ensure_local_head`` raises them.
NEVER_READY = "Burla's local service never became ready (see {log})."
FAILED_TO_START = "Burla's local service failed to start:\nOSError: [Errno 48] address already in use"
NO_RELAY = ("Burla could not establish its relay tunnel through relay.burla.dev:443 using wss.\n"
            "connect to server error: dial tcp: i/o timeout")


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def fresh_pool() -> Any:
    own = Pool(2)
    yield own
    own.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    with world(tmp_path, monkeypatch, pool) as made:
        yield made
        assert_no_forbidden_route(made)


@pytest.fixture
def held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_pool: Pool) -> Iterator[CloudWorld]:
    with world(tmp_path, monkeypatch, fresh_pool) as made:
        yield made
        assert_no_forbidden_route(made)


def state(w: CloudWorld) -> str | None:
    record = w.record()
    return None if record is None else record.get("state")


def stop_notes(text: str) -> list[str]:
    return [line for line in text.splitlines() if NOT_STOPPED.match(line)]


def head_log(w: CloudWorld) -> Path:
    return w.xdg / "poisson-prove" / "cloud" / f"aws-{ACCOUNT}.head.log"


# ---------- S1: one handler, from the record to the end of the stop ----------


@pytest.mark.parametrize("how", ["sigint", "sigterm", "sighup"])
def test_s1_s2_an_interrupt_while_the_coordinator_starts_stops_it_and_exits_130(held: CloudWorld, how: str) -> None:
    """The record is written, the ledger opened, and the software is waiting for the coordinator it
    just started: an interrupt there ends 130 with that coordinator stopped, the record ``stopped``
    and the ledger's line closed ``cancelled``; no node was asked for."""
    held.script_cluster(head_start_s=60)
    hold_spec(held)
    proc = held.spawn()
    wait_for(lambda: bool(held.alive_heads()) or proc.poll() is not None, 120, "the coordinator to begin")
    assert proc.poll() is None, finish(proc)
    (head,) = held.alive_heads()
    assert state(held) == "starting", held.record()
    time.sleep(0.3)
    if how == "sigint":
        os.killpg(proc.pid, signal.SIGINT)
    else:
        os.kill(proc.pid, signal.SIGTERM if how == "sigterm" else signal.SIGHUP)
    code, out, err = finish(proc)
    assert code == 130, (how, out, err)
    assert "Traceback" not in err, err
    assert not alive(head), "the coordinator the interrupted start began is still running"
    assert ended_clean(held) == [], (how, err)
    assert count(held, "cluster start") == 0 and count(held, "job") == 0, timeline(held)
    assert [e["event"] for e in held.ledger()] == ["open", "close"], held.ledger()
    assert held.ledger()[-1]["ended"] == "cancelled", held.ledger()
    # It was Prove's own: the next sweep starts fresh, and is not refused as finding another's.
    held.script_cluster()
    held.write_spec(table=cloud_table(max_cost=20.0))
    done = held.sweep()
    assert done.code == 0, done
    assert timeline(held)[-len(DONE_ORDER):] == DONE_ORDER, timeline(held)


@pytest.mark.parametrize("second", ["sigint", "sigterm"])
def test_s1_a_second_press_before_the_stop_begins_cannot_interrupt_the_way_to_it(held: CloudWorld, second: str) -> None:
    """The job takes two seconds to come back from its cancel. A second press in that time, after
    the first and before the cluster's stop has begun, is the one note; the stop then runs to its
    end. (Two handlers, one until the stop and one inside it, leave Python's default between
    them: a SIGTERM there ends the process with the nodes up.)"""
    held.script_job(default={"cancel_s": 2.0})
    proc = start_held(held, idle_minutes=5)
    os.killpg(proc.pid, signal.SIGINT)
    time.sleep(0.6)
    assert count(held, "cluster stop") == 0, "the stop began before the second press; the job's cancel was not slow"
    if second == "sigint":
        os.killpg(proc.pid, signal.SIGINT)
    else:
        os.kill(proc.pid, signal.SIGTERM)
    code, out, err = finish(proc)
    assert code == 130, (out, err)
    assert "Traceback" not in err, err
    assert err.splitlines().count(NOTE_SECOND) == 1, err
    assert count(held, "cluster stop") == 1, timeline(held)
    assert ended_clean(held) == [], err
    assert interrupted_run(held) == [], err
    assert held.ledger()[-1]["ended"] == "cancelled", held.ledger()


def test_s1_presses_through_the_whole_stop_leave_only_at_the_third(held: CloudWorld) -> None:
    """The count of presses is one count from the first to the last: with the job's cancel slow and
    the cluster's stop slow, a press in each is the note and then the leave, exit 130 with the
    record ``stopping``. Neither window starts the count again."""
    held.script_job(default={"cancel_s": 2.0})
    held.script_cluster(stop_s=20)
    proc = start_held(held, idle_minutes=5)
    os.killpg(proc.pid, signal.SIGINT)
    time.sleep(0.6)
    os.killpg(proc.pid, signal.SIGINT)
    wait_for(lambda: count(held, "cluster stop") == 1, 60, "the stop to begin")
    time.sleep(0.3)
    t0 = time.time()
    os.killpg(proc.pid, signal.SIGINT)
    code, out, err = finish(proc, within=30)
    assert time.time() - t0 < 5, "the third press did not leave at once"
    assert code == 130, (out, err)
    assert err.splitlines().count(NOTE_SECOND) == 1, err
    assert state(held) == "stopping", held.record()


# ---------- S2: the coordinator of a start that failed ----------


@pytest.mark.parametrize("why", ["never-ready", "no-relay"])
def test_s2_a_coordinator_begun_by_a_start_that_failed_is_stopped(w: CloudWorld, why: str) -> None:
    text = NEVER_READY.format(log=w.state / "clusters" / f"aws-{ACCOUNT}" / "head.log") if why == "never-ready" else NO_RELAY
    w.script_cluster(head_fails_after_start=text)
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert len(done.errors) == 1, done
    (head,) = w.heads()
    assert not alive(head["pid"]), "the coordinator the failed start began is still running"
    assert count(w, "coordinator stop") == 1, timeline(w)
    assert state(w) == "stopped", w.record()
    assert [e["event"] for e in w.ledger()] == ["open", "close"], w.ledger()
    assert w.runs() == [], w.runs()
    # The next sweep is not refused as finding a coordinator Prove did not start.
    w.script_cluster()
    again = w.sweep()
    assert again.code == 0, again
    assert timeline(w)[-len(DONE_ORDER):] == DONE_ORDER, timeline(w)


def test_s2_s5_a_coordinator_of_a_failed_start_that_will_not_stop_is_not_called_stopped(w: CloudWorld) -> None:
    """Both faults at once: the start fails after the coordinator began, and the coordinator then
    will not stop. The record is not ``stopped``, the one note says so, and the next cloud sweep
    stops it."""
    w.script_cluster(head_fails_after_start=NO_RELAY, head_stop_fails=True)
    w.write_spec(table=cloud_table(max_cost=20.0))
    done = w.sweep()
    assert done.code == 1, done
    (head,) = w.alive_heads()
    (note,) = stop_notes(done.err)
    assert int(NOT_STOPPED.match(note)["pid"]) == head, (note, head)  # type: ignore[index]
    assert state(w) == "stopping", w.record()
    assert [e["event"] for e in w.ledger()] == ["open", "close"], w.ledger()
    w.script_cluster()
    again = w.sweep()
    assert again.code == 0, again
    assert not alive(head), "the next cloud sweep did not stop the coordinator that was left"
    assert ended_clean(w) == [], again


# ---------- S8: the coordinator's start failures, in the software's own words ----------


@pytest.mark.parametrize("why", ["never-ready", "failed-to-start"])
def test_s8_a_coordinator_that_does_not_start_names_the_log_and_keeps_the_softwares_words_there(w: CloudWorld, why: str) -> None:
    software_log = w.state / "clusters" / f"aws-{ACCOUNT}" / "head.log"
    text = NEVER_READY.format(log=software_log) if why == "never-ready" else FAILED_TO_START
    w.script_cluster(head_fails_after_start=text)
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    (error,) = done.errors
    match = NOT_STARTED.match(error)
    assert match, done
    assert done.nexts == [], done
    shown = done.out + done.err
    assert "local service" not in shown and "Burla" not in shown.replace("Burla's relay", ""), done
    assert "local service" in Path(match["log"]).read_text(encoding="utf-8"), match["log"]


def test_s8_a_relay_that_does_not_open_at_the_coordinators_start_is_the_connection_line(w: CloudWorld) -> None:
    w.script_cluster(head_fails_after_start=NO_RELAY)
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert done.errors == [NO_CONNECTION], done
    assert "relay tunnel" not in done.out + done.err and "relay.burla.dev" not in done.out + done.err, done
    log = w.xdg / "poisson-prove" / "cloud" / f"aws-{ACCOUNT}.log"
    assert "relay tunnel" in log.read_text(encoding="utf-8"), log


def test_s8_the_pin_says_these_words_when_its_coordinator_does_not_start() -> None:
    """The contract: read from the installed pin's ``_local_head.py``, no process started. Skipped
    where the cloud extra is not installed at the pin, as the rest of the contract is."""
    spec = importlib.util.find_spec("burla")
    if spec is None or spec.origin is None:
        pytest.skip("the cloud extra is not installed")
    from importlib import metadata

    if metadata.version("burla") != PIN:
        pytest.skip(f"the cluster software is installed at {metadata.version('burla')}, not the pin {PIN}")
    source = (Path(spec.origin).parent / "_local_head.py").read_text(encoding="utf-8")
    for words in ("Burla's local service never became ready", "Burla's local service failed to start",
                  "Burla could not establish its relay tunnel through"):
        assert words in source, words
    wait = source.split("def _wait_for_head_ready(", 1)[1].split("\ndef ", 1)[0]
    assert "HEAD_UNREACHABLE" not in wait and "not become ready" not in wait, "the start fails with a code after all"
    # Recorded before the wait, and nothing in the wait's failure stops the process (S2).
    start = source.split("head_state_path.write_text(json.dumps(head_state))", 1)
    assert len(start) == 2 and "_wait_for_head_ready(" in start[1].split("\ndef ", 1)[0], "the record no longer comes first"


# ---------- S3: a leftover whose stop cannot be confirmed ----------


def _leave_stopping(w: CloudWorld) -> str:
    """A sweep whose stop left a node listed: exit 3, the record ``stopping``, the ledger closed
    ``error``. Returns its run id."""
    w.script_cluster(stop_leaves=1)
    w.set_constant("_STOP_POLL_S", 1.0)
    w.write_spec(table=cloud_table(max_cost=20.0))
    done = w.sweep()
    assert done.code == 3 and state(w) == "stopping", done
    assert w.ledger()[-1]["ended"] == "error", w.ledger()
    return str(w.record()["run_id"])  # type: ignore[index]


@pytest.mark.parametrize("fault", ["nodes-still-listed", "stop-answers-an-error"])
def test_s3_an_unconfirmed_leftover_refuses_the_new_sweep_and_is_left_as_it_was(w: CloudWorld, fault: str) -> None:
    first_run = _leave_stopping(w)
    before = w.record()
    ledger_before = w.ledger()
    runs_before = [r["run_id"] for r in w.runs()]
    if fault == "stop-answers-an-error":
        w.script_cluster(stop_fails={"code": "PROVIDER_ERROR", "message": "terminate refused"}, stop_leaves=1)
    done = w.sweep()
    assert done.code == 1, done
    (error,) = done.errors
    match = UNCONFIRMED.match(error)
    assert match, done
    if fault == "nodes-still-listed":
        assert match["listed"] == "1", error
    assert done.nexts == ["next: poisson-prove where"], done
    assert "Traceback" not in done.err and "unexpected failure" not in done.err, done
    after = w.record()
    assert after is not None and before is not None
    assert after["state"] == "stopping" and after["run_id"] == first_run, after
    assert w.ledger() == ledger_before, "the refused sweep wrote to the ledger"
    assert not [e for e in w.ledger() if e.get("ended") == "lost"], w.ledger()
    assert [r["run_id"] for r in w.runs()] == runs_before, "the refused sweep stored a run"
    assert len(w.listed_nodes()) == 1, w.cluster()


def test_s3_the_sweep_after_finishes_the_leftover_and_says_its_line_was_already_closed(w: CloudWorld) -> None:
    first_run = _leave_stopping(w)
    assert w.sweep().code == 1
    w.script_cluster()
    t_before = time.time()
    done = w.sweep()
    assert done.code == 0, done
    notes = [line for line in done.err.splitlines() if line.startswith("note: the cluster from")]
    assert len(notes) == 1 and LEFT_CLOSED.match(notes[0]), done.err
    closes = [e for e in w.ledger() if e["event"] == "close" and e["run_id"] == first_run]
    assert [e["ended"] for e in closes] == ["error"], "the line the dead sweep closed was closed again"
    after = [e for e in w.management() if e["time"] > t_before]
    names = [e["route"] for e in after]
    assert names.index("POST /v1/management/cluster/stop") < names.index("PATCH /v1/management/settings"), names
    assert ended_clean(w) == [], done
    assert timeline(w)[-len(DONE_ORDER):] == DONE_ORDER, timeline(w)


def test_s3_a_killed_sweeps_ledger_line_is_not_closed_lost_while_its_stop_is_unconfirmed(held: CloudWorld) -> None:
    """The leftover of a sweep that died (its ledger line still open): while its nodes cannot be
    confirmed stopped, no charge is written for it."""
    proc = start_held(held)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=30)
    assert state(held) == "running"
    second = Pool(2)
    try:
        held.use_pool(second)
        held.script_cluster(stop_leaves=1)
        held.set_constant("_STOP_POLL_S", 1.0)
        held.write_spec(table=cloud_table(max_cost=20.0))
        done = held.sweep()
        assert done.code == 1, done
        (error,) = done.errors
        assert UNCONFIRMED.match(error), done
        assert [e["event"] for e in held.ledger()] == ["open"], held.ledger()
        assert state(held) == "running", held.record()
        # Once the stop can be confirmed, the line is closed lost, once.
        held.script_cluster()
        again = held.sweep()
        assert again.code == 0, again
        assert [e.get("ended") for e in held.ledger() if e["event"] == "close"][0] == "lost", held.ledger()
        assert ended_clean(held) == [], again
    finally:
        second.stop()


# ---------- S4: a record stopping, its process alive ----------


def test_s4_a_stopping_record_of_a_live_process_is_another_sweep(held: CloudWorld) -> None:
    held.script_cluster(stop_s=30)
    proc = start_held(held, idle_minutes=5)
    os.killpg(proc.pid, signal.SIGINT)
    wait_for(lambda: state(held) == "stopping" and count(held, "cluster stop") == 1, 60, "the stop to begin")
    try:
        before = len(held.management())
        heads = len(held.heads())
        ledger_before = held.ledger()
        held.write_spec(table=cloud_table(ledger="ledger2.jsonl"))
        done = held.sweep()
        assert done.code == 1, done
        assert done.errors == [
            f"error: another sweep is running on this AWS account from this machine (process {proc.pid})"
        ], done
        assert len(held.management()) == before and len(held.heads()) == heads, timeline(held)
        assert held.ledger() == ledger_before and held.ledger("ledger2.jsonl") == []
        assert state(held) == "stopping", held.record()
    finally:
        os.killpg(proc.pid, signal.SIGINT)
        os.killpg(proc.pid, signal.SIGINT)
        finish(proc)


# ---------- S5: a coordinator that will not stop ----------


def test_s5_a_coordinator_that_will_not_stop_leaves_the_record_stopping_with_one_note(w: CloudWorld) -> None:
    w.script_cluster(head_stop_fails=True)
    w.write_spec(table=cloud_table(max_cost=20.0))
    done = w.sweep()
    assert done.code == 0, done
    (head,) = w.alive_heads()
    (note,) = stop_notes(done.err)
    assert int(NOT_STOPPED.match(note)["pid"]) == head, (note, head)  # type: ignore[index]
    assert state(w) == "stopping", w.record()
    assert w.listed_nodes() == [], "the nodes were stopped: only the coordinator is left"
    assert [e["event"] for e in w.ledger()] == ["open", "close"] and w.ledger()[-1]["ended"] == "complete", w.ledger()
    assert "PermissionError" not in done.out + done.err and "Traceback" not in done.err, done
    # The next cloud sweep stops it, says the line was closed, and runs.
    w.script_cluster()
    again = w.sweep()
    assert again.code == 0, again
    assert not alive(head), "the next cloud sweep did not stop the coordinator that was left"
    notes = [line for line in again.err.splitlines() if line.startswith("note: the cluster from")]
    assert len(notes) == 1 and LEFT_CLOSED.match(notes[0]), again.err
    assert stop_notes(again.err) == [], again.err
    assert ended_clean(w) == [], again


def test_s5_while_it_will_not_stop_the_next_sweep_is_refused_not_run_under_it(w: CloudWorld) -> None:
    w.script_cluster(head_stop_fails=True)
    w.write_spec(table=cloud_table(max_cost=20.0))
    assert w.sweep().code == 0
    started = count(w, "cluster start")
    done = w.sweep()
    assert done.code == 1, done
    (error,) = done.errors
    assert UNCONFIRMED.match(error), done
    assert done.nexts == ["next: poisson-prove where"], done
    assert count(w, "cluster start") == started, "a cluster was started beside a coordinator that would not stop"
    assert state(w) == "stopping", w.record()


# ---------- S6: the coordinator's log, and its port ----------


def test_s6_the_coordinators_log_is_copied_beside_the_record_and_the_record_carries_its_port(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 0, done
    (head,) = w.heads()
    kept = head_log(w)
    assert kept.is_file(), sorted(p.name for p in kept.parent.iterdir())
    assert f"fake head {head['pid']} for aws-{ACCOUNT} started" in kept.read_text(encoding="utf-8"), kept.read_text(encoding="utf-8")
    record = w.record()
    assert record is not None
    coordinator = record["coordinator"]
    (url,) = {e["head"] for e in w.management() if e.get("head")}
    assert coordinator["pid"] == head["pid"] and coordinator["url"] == url, coordinator
    assert coordinator["port"] == int(url.rsplit(":", 1)[1]), coordinator


def test_s6_the_log_is_the_coordinator_of_this_sweep_after_each_stop(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    assert w.sweep().code == 0
    assert w.sweep().code == 0
    first, second = sorted(w.heads(), key=lambda h: h["started"])
    text = head_log(w).read_text(encoding="utf-8")
    assert f"fake head {second['pid']} " in text, text


# ---------- S7: the AWS CLI's calls ----------


def test_s7_the_limit_of_one_call_is_120_seconds() -> None:
    from poisson_prove import _where_checks

    assert _where_checks._CLI_S == 120.0  # noqa: SLF001


def test_s7_each_call_runs_in_a_session_of_its_own(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    calls = w.aws_calls()
    assert len(calls) == 2, calls
    for call in calls:
        assert call["sid"] == call["pid"] and call["sid"] != os.getsid(0), call


def _short_limit(w: CloudWorld, seconds: float = 6.0) -> None:
    from poisson_prove import _where_checks

    w.mp.setattr(_where_checks, "_CLI_S", seconds)


def _call_ended(w: CloudWorld, service: str) -> bool:
    (call,) = [c for c in w.aws_calls() if c["argv"][0] == service]
    return not alive(call["pid"])


def test_s7_a_sign_in_call_that_does_not_answer_reads_as_not_signed_in(w: CloudWorld) -> None:
    _short_limit(w)
    w.aws_state(hangs=["sts"])
    w.write_spec(table=cloud_table())
    t0 = time.time()
    done = w.sweep("--dry-run")
    assert time.time() - t0 < 60, "the limit did not end the call"
    assert done.code == 1, done
    assert done.errors == ["error: this machine is not signed in to AWS"], done
    assert done.nexts == ["next: aws login"], done
    assert [c["argv"][0] for c in w.aws_calls()] == ["sts"], w.aws_calls()
    wait_for(lambda: _call_ended(w, "sts"), 10, "the call that did not answer to be ended")
    assert w.routes() == [] and w.records() == {} and w.ledger() == [], (w.routes(), w.records())


def test_s7_a_quota_call_that_does_not_answer_is_one_note_and_the_plan_goes_on(w: CloudWorld) -> None:
    _short_limit(w)
    w.aws_state(hangs=["service-quotas"])
    w.write_spec(table=cloud_table())
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    quota = [n for n in done.notes if "quota" in n]
    assert len(quota) == 1 and "could not be read" in quota[0], done.notes
    assert done.out.startswith("plan  "), done
    wait_for(lambda: _call_ended(w, "service-quotas"), 10, "the call that did not answer to be ended")


def test_s7_the_limit_is_the_one_the_calls_are_given(w: CloudWorld) -> None:
    """With the limit long, a call that answers late is still read: the limit, not a shorter one
    of the build's own, is what ends a call."""
    from poisson_prove import _where_checks

    assert cloud_module() is not None
    w.mp.setattr(_where_checks, "_CLI_S", 30.0)
    w.aws_state(answers_after=2.0)
    w.write_spec(table=cloud_table())
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    assert not [n for n in done.notes if "quota" in n], done.notes
