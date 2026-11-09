"""C3 of 0.3.0, Remote backends: the cluster's life, what Prove owns, and every way a sweep ends.

The frozen tests for L1 to L14 (Remote Backends Spec §6 and §15 C3; RB-17 to RB-23, RB-33), and
the three items Pair 1 left to this pair: K6 (the cloud half of #12's closed pipe), K7's cloud
half (SIGTERM and SIGHUP are an interrupt) and E5's cluster stop (#11's early stop on a cloud
account). C3-K, the contract with the installed software, is ``test_rb_cloud_contract.py``.

On the fakes of ``rb_cloud_support.py``: a fake coordinator process per head, the cluster
software's management CLI over the fake's cluster, the job's fake ``remote_parallel_map`` over
local fake workers, which reaches no node unless the coordinator Prove names is alive and a node
is ready. The tests that signal Prove run it as its own process and session
(``prove_with_fakes.py``) and signal its process group the way a terminal's Ctrl-C does.

**What the tests fix that the invariants leave open:**

- The ownership record is ``$XDG_STATE_HOME/poisson-prove/cloud/aws-<account>.json``, JSON, with
  ``state`` (``starting``, ``running``, ``stopping``, ``stopped``) and ``last_alive`` (Unix
  seconds) among its keys; every write lands by ``os.replace``/``os.rename`` onto it, and the
  states it passes through on a done sweep are, in order, ``starting``, ``running``, ``stopping``,
  ``stopped``.
- The heartbeat's interval is ``executor_cloud._ALIVE_S`` (30 s) and the stop's poll limit
  ``executor_cloud._STOP_POLL_S`` (120 s); the tests shorten both. The backstop's intervals are
  0.2.1's ``_BACKSTOP_S`` and ``_KILL_GRACE_S``.
- Prove starts the processes it owns in sessions of their own, so a terminal's Ctrl-C reaches
  Prove alone and Prove decides what each child does.
- The settings update carries exactly §6.2's seven fields when ``disk_gb`` is given (the
  software's default disk is kept when it is not).
- A refusal after the coordinator started (nodes or a job listed before Prove asked, §6.1) is one
  ``error:`` line, exit 1; Prove's own coordinator is stopped, no stop is sent to the nodes, and the
  ledger's open line has a close.
- The lost run's upper bound (§6.6) is ``nodes × usd_per_node_hour × ((last_alive − start) / 60 +
  max(idle_minutes, 3) + boot_minutes) / 60``: the larger of §6.5's two bounds, the nodes'
  idle stop and the software's three-minute orphan rule (yes/no). The note names the run as
  ``runs`` does.
- A stop that cannot be confirmed says how many nodes were still listed and after how long, and
  exits 3 (§6.4).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rb_cloud_support import (
    ACCOUNT,
    FIXTURES,
    FORBIDDEN_ROUTES,
    MACHINE,
    PRICE,
    REGION,
    SETTINGS_FIELDS,
    CloudWorld,
    Pool,
    alive,
    cloud_module,
    cloud_table,
    this_minor,
    wait_for,
    world,
)

DEAF = FIXTURES / "deaf_launcher.py"
DONE_ORDER = ["coordinator start", "status", "settings update", "cluster start", "job", "cluster stop",
              "status", "coordinator stop"]
NOTE_SECOND = ("note: stopping the cluster; press Ctrl-C again to leave it, and the nodes will stop "
               "themselves within 5 min")


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
    """A world whose job holds its second batch until signalled, on workers of its own."""
    with world(tmp_path, monkeypatch, fresh_pool) as made:
        yield made
        assert_no_forbidden_route(made)


def assert_no_forbidden_route(w: CloudWorld) -> None:
    """L11, in every test of this file: none of the routes Prove must never call."""
    bad = [r for r in w.routes() if any(r.startswith(f) or f in r for f in FORBIDDEN_ROUTES)]
    assert bad == [], bad


def timeline(w: CloudWorld) -> list[str]:
    """L1's sequence: the progress line's status polls while ``cluster start`` is in flight are left
    out, and the polls after ``cluster stop`` (§6.2 step 10, "status polled until off") count as
    one. Any other status call counts each time."""
    entries = w._lines(w.state / "management.jsonl")  # noqa: SLF001
    start_t = next((e["time"] for e in entries if e["route"] == "POST /v1/management/cluster/start"), None)
    start_end = next((e["time"] for e in entries
                      if e["route"] == "POST /v1/management/cluster/start answered"), None)
    out: list[str] = []
    for (t, name) in sorted(_events(w)):
        if name == "status" and start_t is not None and start_end is not None and start_t < t < start_end:
            continue
        if name == "status" and out[-2:] == ["cluster stop", "status"]:
            continue
        out.append(name)
    return out


def _events(w: CloudWorld) -> list[tuple[float, str]]:
    names = {
        "head start": "coordinator start", "head stop": "coordinator stop",
        "GET /v1/management/cluster": "status", "PATCH /v1/management/settings": "settings update",
        "POST /v1/management/cluster/start": "cluster start", "POST /v1/management/cluster/stop": "cluster stop",
    }
    events = [(e["time"], names.get(e["route"], e["route"])) for e in w.management()]
    return events + [(e["time"], "job") for e in w.jobs()]


def result_lines(out: str) -> list[str]:
    """Stdout from the result's verdict line on (``--yes`` prints the plan above it)."""
    lines = out.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith(("done  ", "stopped  ")))
    return lines[first:]


def ended_clean(w: CloudWorld) -> list[str]:
    """L2: no node listed, no coordinator alive, the record ``stopped``."""
    problems = []
    if w.listed_nodes():
        problems.append(f"nodes still listed: {w.listed_nodes()}")
    if w.alive_heads():
        problems.append(f"a coordinator is alive: {w.alive_heads()}")
    record = w.record()
    if record is not None and record.get("state") != "stopped":
        problems.append(f"the record reads {record.get('state')!r}")
    # §17.4: no process of the cluster software Prove started is left on this machine.
    left = sorted({e["pid"] for e in w._lines(w.state / "management.jsonl")  # noqa: SLF001
                   if isinstance(e.get("pid"), int) and alive(e["pid"])})
    if left:
        problems.append(f"processes of the cluster software still alive: {left}")
    return problems


def count(w: CloudWorld, name: str) -> int:
    return [n for _, n in _events(w)].count(name)


def _head_url(w: CloudWorld) -> str:
    urls = {e.get("head") for e in w.management() if e.get("head")}
    assert len(urls) == 1, urls
    return str(next(iter(urls)))


# ---------- L1: a done sweep's calls ----------


def test_l1_a_done_sweep_calls_exactly_this_in_this_order(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(disk_gb=40, idle_minutes=4))
    done = w.sweep()
    assert done.code == 0, done
    assert timeline(w) == DONE_ORDER, timeline(w)
    (update,) = [e for e in w.management() if e["route"] == "PATCH /v1/management/settings"]
    assert update["body"] == {
        "region": REGION, "machine_type": MACHINE, "quantity": 1, "image": f"python:{this_minor()}",
        "disk_gb": 40, "inactivity_timeout_seconds": 240, "max_vcpus": 8,
    }, update["body"]
    url = _head_url(w)
    assert all(job["env"]["BURLA_CLUSTER_DASHBOARD_URL"] == url for job in w.jobs()), w.jobs()
    assert ended_clean(w) == [], done


def test_l1_without_disk_gb_the_softwares_default_disk_is_kept(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 0, done
    (update,) = [e for e in w.management() if e["route"] == "PATCH /v1/management/settings"]
    assert set(update["body"]) == SETTINGS_FIELDS - {"disk_gb"}, update["body"]
    assert update["body"]["inactivity_timeout_seconds"] == 120, update["body"]


def test_l1_every_management_call_goes_to_the_coordinator_prove_started(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    assert w.sweep().code == 0
    (head,) = w.heads()
    assert head["sid"] == head["pid"], "the coordinator runs in a session of its own"
    calls = [e for e in w.management() if e["route"].startswith(("GET", "POST", "PATCH"))]
    assert calls and all(e["head"] == _head_url(w) for e in calls), calls


# ---------- L2, L3, E5: every ending stops what Prove started ----------


IN_PROCESS_ENDINGS = ["done", "refused-after-start", "step-5", "step-6", "step-7", "step-8", "step-9",
                      "early-stop", "spend-stop", "backstop"]


def _set_up_ending(w: CloudWorld, ending: str) -> tuple[str, dict[str, Any], int]:
    """Script ``ending``; return the target, the table and the exit code it ends with."""
    table = cloud_table()
    target = "bu_targets.cloud:quick"
    code = 0
    if ending == "refused-after-start":
        w.script_cluster(jobs=1)
        code = 1
    elif ending == "step-5":
        w.script_cluster(head_fails="HEAD_UNREACHABLE: the head did not become ready")
        code = 1
    elif ending == "step-6":
        w.script_cluster(status_fails={"code": "TRANSPORT_ERROR", "message": "connection reset", "times": 1})
        code = 1
    elif ending == "step-7":
        w.script_cluster(settings_fails={"code": "PROVIDER_ERROR", "message": "settings refused"})
        code = 1
    elif ending == "step-8":
        table["nodes"] = 3
        w.script_cluster(start_fails_after={"nodes": 2, "message": "503: {'title': 'INSUFFICIENT_INSTANCE_CAPACITY: m7i.2xlarge'}"})
        code = 3
    elif ending == "step-9":
        w.script_job(default={"refuse": "NoCompatibleNodes"})
        code = 3
    elif ending == "early-stop":
        target = "bu_targets.cloud:raises"
        code = 3
    elif ending in ("spend-stop", "backstop"):
        target = "bu_targets.cloud:slow"
        table.update(stop_cost=0.01575, max_cost=0.02, est_seconds_per_episode=0.01)
        code = 3
        if ending == "backstop":
            w.set_constant("_BACKSTOP_S", 0.5)
            w.set_constant("_KILL_GRACE_S", 0.5)
            w.mp.setattr(cloud_module(), "_launcher_argv",
                         lambda: [sys.executable, "-I", str(DEAF), str(w.state)])
    return target, table, code


@pytest.mark.parametrize("ending", IN_PROCESS_ENDINGS)
def test_l2_every_ending_leaves_no_node_no_coordinator_and_the_record_stopped(w: CloudWorld, ending: str) -> None:
    target, table, code = _set_up_ending(w, ending)
    w.write_spec(table=table, cells=("a", "b"), replicates=4)
    done = w.sweep(target=target)
    assert done.code == code, done
    assert ended_clean(w) == [], (ending, done)
    if ending != "step-5":
        assert count(w, "coordinator start") == 1 and count(w, "coordinator stop") == 1, timeline(w)
    if ending not in ("step-5", "refused-after-start"):
        assert count(w, "cluster stop") == 1, timeline(w)
    lines = w.ledger()
    assert [e["event"] for e in lines] == ["open", "close"], lines
    assert "Traceback" not in done.err, done


def test_l3_a_start_that_fails_after_booting_some_nodes_stops_them_and_exits_3(w: CloudWorld) -> None:
    _, table, _ = _set_up_ending(w, "step-8")
    w.write_spec(table=table)
    done = w.sweep()
    assert done.code == 3, done
    names = [n for _, n in sorted(_events(w))]
    assert names.index("cluster stop") > names.index("cluster start"), names
    assert "job" not in names, names
    assert w.listed_nodes() == [], w.cluster()
    assert ended_clean(w) == [], done


def test_l3_a_start_that_boots_no_node_still_stops_and_exits_1(w: CloudWorld) -> None:
    w.script_cluster(start_fails_after={"nodes": 0, "message": "503: {'title': 'UnauthorizedOperation'}"})
    w.write_spec(table=cloud_table(nodes=2))
    done = w.sweep()
    assert done.code == 1, done
    assert count(w, "cluster stop") == 1, timeline(w)
    assert ended_clean(w) == [], done


def test_e5_an_early_stop_on_a_cloud_account_stops_the_cluster_before_exit_and_closes_stopped(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(), cells=("a", "b"), replicates=4)
    done = w.sweep(target="bu_targets.cloud:raises")
    assert done.code == 3, done
    assert result_lines(done.out)[0].startswith("stopped  every rollout of the first batch had no outcome"), done
    names = timeline(w)
    assert names[-3:] == ["cluster stop", "status", "coordinator stop"], names
    assert w.ledger()[-1]["event"] == "close" and w.ledger()[-1]["ended"] == "stopped", w.ledger()
    assert ended_clean(w) == [], done


# ---------- real processes: Ctrl-C, SIGTERM, SIGHUP, closed pipes ----------


def hold_spec(w: CloudWorld, **over: Any) -> Path:
    marker = w.root / "held.marker"
    w.write_spec(table=cloud_table(**over), cells=("fast", "hold"), replicates=2,
                 axes={"marker": [str(marker)]})
    return marker


def start_held(w: CloudWorld, *args: str, stdout: Any = subprocess.PIPE,
               stderr: Any = subprocess.PIPE, **over: Any) -> subprocess.Popen[bytes]:
    marker = hold_spec(w, **over)
    proc = w.spawn(*args, stdout=stdout, stderr=stderr)
    wait_for(lambda: marker.exists() or proc.poll() is not None, 120, "the job to hold")
    assert proc.poll() is None, proc.communicate(timeout=10)
    return proc


def finish(proc: subprocess.Popen[bytes], within: float = 120) -> tuple[int, str, str]:
    out, err = proc.communicate(timeout=within)
    return proc.returncode, (out or b"").decode("utf-8", "replace"), (err or b"").decode("utf-8", "replace")


def the_run(w: CloudWorld) -> str:
    (run,) = [p.name for p in w.store.iterdir() if p.is_dir() and not p.name.startswith(".")]
    return run


def interrupted_run(w: CloudWorld) -> list[str]:
    problems = []
    run = the_run(w)
    events = w.events(run)
    if not events or events[-1].get("kind", events[-1].get("event")) != "interrupted":
        problems.append(f"the event log ends {events[-1] if events else None}")
    if w.manifest(run)["status"] != "partial":
        problems.append(f"the manifest reads {w.manifest(run)['status']}")
    return problems


@pytest.mark.parametrize("how", ["sigint", "sigterm", "sighup"])
def test_l2_k7_an_interrupt_during_the_job_stops_the_cluster_and_exits_130(held: CloudWorld, how: str) -> None:
    proc = start_held(held)
    if how == "sigint":
        os.killpg(proc.pid, signal.SIGINT)
    else:
        os.kill(proc.pid, signal.SIGTERM if how == "sigterm" else signal.SIGHUP)
    code, out, err = finish(proc)
    assert code == 130, (how, out, err)
    assert "Traceback" not in err, err
    (stopped,) = [line for line in out.splitlines() if line.startswith("stopped  interrupted: ")]
    assert stopped.endswith("; the cluster was stopped"), stopped
    assert interrupted_run(held) == [], (how, err)
    assert count(held, "cluster stop") == 1, timeline(held)
    assert ended_clean(held) == [], (how, err)
    assert held.ledger()[-1]["ended"] == "cancelled", held.ledger()


@pytest.mark.parametrize("case", ["plain", "plain-stderr-closed", "json", "json-stderr-closed"])
def test_k6_ctrl_c_with_stdout_closed_on_a_cloud_sweep_stops_the_cluster_once(held: CloudWorld, case: str) -> None:
    args = ("--json",) if case.startswith("json") else ()
    proc = start_held(held, *args)
    assert proc.stdout is not None and proc.stderr is not None
    proc.stdout.close()
    if case.endswith("stderr-closed"):
        proc.stderr.close()
    os.killpg(proc.pid, signal.SIGINT)
    proc.wait(timeout=120)
    err = "" if case.endswith("stderr-closed") else proc.stderr.read().decode("utf-8", "replace")
    assert proc.returncode == 130, (case, err)
    assert "Traceback" not in err and "Exception ignored" not in err, err
    assert interrupted_run(held) == [], (case, err)
    assert count(held, "cluster stop") == 1, timeline(held)
    assert ended_clean(held) == [], (case, err)


def test_l2_ctrl_c_during_the_boot_stops_the_booting_nodes(held: CloudWorld) -> None:
    held.script_cluster(start_hangs=True)
    hold_spec(held, nodes=2)
    proc = held.spawn()
    wait_for(lambda: any(n["status"] == "BOOTING" for n in held.cluster()["nodes"]), 120, "the boot")
    os.killpg(proc.pid, signal.SIGINT)
    code, out, err = finish(proc)
    assert code == 130, (out, err)
    assert "job" not in timeline(held), timeline(held)
    assert count(held, "cluster stop") == 1, timeline(held)
    assert ended_clean(held) == [], err
    assert "Traceback" not in err, err


def test_l4_a_second_ctrl_c_during_the_stop_notes_once_and_the_stop_completes(held: CloudWorld) -> None:
    held.script_cluster(stop_s=3)
    proc = start_held(held, idle_minutes=5)
    os.killpg(proc.pid, signal.SIGINT)
    wait_for(lambda: count(held, "cluster stop") == 1, 60, "the stop to begin")
    time.sleep(0.3)
    os.killpg(proc.pid, signal.SIGINT)
    code, out, err = finish(proc)
    assert code == 130, err
    assert err.splitlines().count(NOTE_SECOND) == 1, err
    assert ended_clean(held) == [], err


def test_l4_a_third_ctrl_c_leaves_at_once_with_the_record_stopping(held: CloudWorld) -> None:
    held.script_cluster(stop_s=20)
    proc = start_held(held, idle_minutes=5)
    os.killpg(proc.pid, signal.SIGINT)
    wait_for(lambda: count(held, "cluster stop") == 1, 60, "the stop to begin")
    time.sleep(0.3)
    os.killpg(proc.pid, signal.SIGINT)
    time.sleep(0.3)
    t0 = time.time()
    os.killpg(proc.pid, signal.SIGINT)
    proc.wait(timeout=30)
    assert time.time() - t0 < 5, "the third Ctrl-C did not leave at once"
    assert proc.returncode == 130
    record = held.record()
    assert record is not None and record["state"] == "stopping", record


# ---------- L5, L6: what Prove did not start ----------


def test_l5_a_coordinator_no_record_names_is_refused_and_never_touched(w: CloudWorld) -> None:
    pid = w.start_foreign_head()
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert done.errors == [
        f"error: a cluster coordinator Prove did not start is running for this AWS account (process {pid}); "
        "Prove does not change or stop what it did not start"
    ], done
    assert [r for r in w.routes() if r != "GET /version"] == [], w.routes()
    assert w.head_signals() == [] and alive(pid), w.head_signals()
    assert w.ledger() == [] and w.records() == {}, (w.ledger(), w.records())


@pytest.mark.parametrize("found", ["nodes", "jobs"])
def test_l6_nodes_or_jobs_before_prove_asked_are_refused_and_left_alone(w: CloudWorld, found: str) -> None:
    w.script_cluster(**({"preexisting": [{"status": "READY"}]} if found == "nodes" else {"jobs": 1}))
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert len(done.errors) == 1, done
    assert count(w, "cluster stop") == 0 and count(w, "cluster start") == 0, timeline(w)
    assert count(w, "coordinator stop") == 1 and w.alive_heads() == [], timeline(w)
    if found == "nodes":
        assert len(w.listed_nodes()) == 1, "the nodes Prove did not start were stopped"
    assert [e["event"] for e in w.ledger()] == ["open", "close"], w.ledger()
    assert w.runs() == [], w.runs()


# ---------- L7, L8: the record ----------


@contextlib.contextmanager
def record_writes(w: CloudWorld) -> Iterator[dict[str, Any]]:
    """Every rename onto the record (with the state it carried) and every open of the record itself
    for writing, seen by an audit hook in this process."""
    path = str(w.xdg / "poisson-prove" / "cloud" / f"aws-{ACCOUNT}.json")
    seen: dict[str, Any] = {"renames": [], "direct": []}
    busy = [False]
    on = [True]

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if not on[0] or busy[0]:
            return
        if event == "os.rename" and os.fsdecode(args[1]) == path:
            busy[0] = True
            try:
                with open(os.fsdecode(args[0]), encoding="utf-8") as fh:
                    seen["renames"].append((time.time(), json.load(fh)))
            finally:
                busy[0] = False
        elif event == "open" and isinstance(args[0], (str, bytes, os.PathLike)) and os.fsdecode(args[0]) == path:
            mode = args[1] if isinstance(args[1], str) else ""
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            if any(c in mode for c in "wax+") or flags & (os.O_WRONLY | os.O_RDWR):
                seen["direct"].append(mode or flags)

    sys.addaudithook(hook)
    try:
        yield seen
    finally:
        on[0] = False


def test_l7_the_record_is_written_by_rename_before_the_coordinator_and_before_each_state(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    with record_writes(w) as seen:
        done = w.sweep()
    assert done.code == 0, done
    assert seen["direct"] == [], "the record was opened for writing in place"
    states = [r["state"] for _, r in seen["renames"]]
    squeezed = [s for i, s in enumerate(states) if i == 0 or states[i - 1] != s]
    assert squeezed == ["starting", "running", "stopping", "stopped"], states
    (start,) = [e for e in w.management() if e["route"] == "head start"]
    assert start["snapshots"][f"aws-{ACCOUNT}.json"]["state"] == "starting", start["snapshots"]
    first_rename = seen["renames"][0][0]
    assert first_rename < start["time"], "the record was written after the coordinator was asked for"


def test_l7_a_kill_mid_job_leaves_a_parseable_record(held: CloudWorld) -> None:
    proc = start_held(held)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=30)
    record = held.record()
    assert record is not None and record["state"] == "running", record


def test_l8_the_heartbeat_interval_is_30_seconds() -> None:
    assert cloud_module()._ALIVE_S == 30.0  # noqa: SLF001
    assert cloud_module()._STOP_POLL_S == 120.0  # noqa: SLF001


def test_l8_last_alive_advances_at_the_interval_while_the_job_runs(w: CloudWorld) -> None:
    w.set_constant("_ALIVE_S", 0.2)
    w.write_spec(table=cloud_table(), cells=("a", "b", "c", "d"), replicates=4)
    with record_writes(w) as seen:
        done = w.sweep(target="bu_targets.cloud:slow")
    assert done.code == 0, done
    beats = sorted({r["last_alive"] for _, r in seen["renames"] if r["state"] == "running"})
    assert len(beats) >= 5, beats
    gaps = [b - a for a, b in zip(beats, beats[1:], strict=False)]
    assert max(gaps) < 1.0, gaps


# ---------- L9: the next sweep finds what was left ----------


def _upper_bound(w: CloudWorld, run_open: dict[str, Any], last_alive: float, *, idle: float, boot: float,
                 nodes: int = 1) -> float:
    minutes = (last_alive - run_open["start"]) / 60 + max(idle, 3.0) + boot
    return nodes * PRICE * minutes / 60


def _and_stop(cleanup: Any, pool: Pool) -> Any:
    def both() -> None:
        try:
            cleanup()
        finally:
            pool.stop()

    return both


NOTE = re.compile(
    r'^note: the cluster from the sweep of "(?P<name>[^"]+)" had not stopped; Prove stopped it '
    r"\(up since (?P<since>\d\d:\d\dZ), charged \$(?P<charge>[0-9.]+) to the ledger as an upper bound\)$"
)


@pytest.mark.parametrize("coordinator", ["alive", "gone"])
def test_l9_a_sweep_that_died_is_found_stopped_and_closed_lost_by_the_next(held: CloudWorld, coordinator: str) -> None:
    proc = start_held(held, boot_minutes=0.5)
    first_run = the_run(held)
    first_name = next(r["run_name"] for r in held.runs() if r["run_id"] == first_run)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=30)
    record = held.record()
    assert record is not None and record["state"] == "running", record
    last_alive = float(record["last_alive"])
    (old_head,) = held.alive_heads()
    old_url = json.loads((held.state / "clusters" / f"aws-{ACCOUNT}" / "head.json").read_text())["url"]
    # The killed sweep's workers hold its batch; the next sweep runs on workers of its own.
    second_pool = Pool(2)
    held.use_pool(second_pool)
    held.mp.setattr(held, "cleanup", _and_stop(held.cleanup, second_pool))
    if coordinator == "gone":
        os.kill(old_head, signal.SIGKILL)
        wait_for(lambda: not alive(old_head), 10, "the coordinator to die")
    assert len(held.listed_nodes()) == 1
    t_before = time.time()
    # The lost run's open line counts its whole stop until it is closed: the cap leaves room for it.
    held.write_spec(table=cloud_table(max_cost=20.0))
    done = held.sweep()
    assert done.code == 0, done
    after = [n for t, n in sorted(_events(held)) if t > t_before]
    if coordinator == "alive":
        assert after[:3] == ["cluster stop", "status", "coordinator stop"], after
        stop = next(e for e in held.management() if e["time"] > t_before
                    and e["route"] == "POST /v1/management/cluster/stop")
        assert stop["head"] == old_url, stop
    else:
        assert after[:5] == ["coordinator start", "status", "cluster stop", "status", "coordinator stop"], after
    assert after[-len(DONE_ORDER):] == DONE_ORDER, after
    run_open = next(e for e in held.ledger() if e["event"] == "open" and e["run_id"] == first_run)
    (lost,) = [e for e in held.ledger() if e["event"] == "close" and e["run_id"] == first_run]
    assert lost["ended"] == "lost", lost
    expected = _upper_bound(held, run_open, last_alive, idle=2, boot=0.5)
    assert lost["charge"] == pytest.approx(expected, rel=1e-6), (lost, expected)
    notes = [line for line in done.err.splitlines() if line.startswith("note: the cluster from")]
    assert len(notes) == 1, done.err
    match = NOTE.match(notes[0])
    assert match, notes[0]
    assert match["name"] == first_name, (match["name"], first_name)
    assert match["since"] == datetime.fromtimestamp(run_open["start"], UTC).strftime("%H:%MZ"), notes[0]
    assert float(match["charge"]) == pytest.approx(expected, rel=0.06), (notes[0], expected)
    assert ended_clean(held) == [], done
    assert held.listed_nodes() == []


def test_l9_a_stopped_record_is_left_alone(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    assert w.sweep().code == 0
    first = len(w.management())
    done = w.sweep()
    assert done.code == 0, done
    assert [n for _, n in sorted(_events(w))][-len(DONE_ORDER):] == DONE_ORDER
    assert len([e for e in w.management()[first:] if e["route"] == "head start"]) == 1
    assert not [line for line in done.err.splitlines() if line.startswith("note: the cluster from")], done.err


# ---------- L10: nothing before the question's yes ----------


@pytest.mark.parametrize("how", ["dry-run", "refused-at-plan", "no"])
def test_l10_nothing_starts_before_a_yes(w: CloudWorld, how: str) -> None:
    table = cloud_table(stop_cost=0.001, max_cost=0.001) if how == "refused-at-plan" else cloud_table()
    w.write_spec(table=table)
    if how == "no":
        done = w.run("sweep", "prove.toml", "--target", "bu_targets.cloud:quick", "--backend", "cloud",
                     "--max-mde", "1", stdin="n\n")
    else:
        done = w.sweep(*(["--dry-run"] if how == "dry-run" else []))
    assert done.code == (0 if how == "dry-run" else 1), done
    assert w.routes() == [] and w.heads() == [], w.routes()
    assert w.records() == {} and w.ledger() == [], (w.records(), w.ledger())


# ---------- L11, L12: what Prove sends and how it starts the software ----------


def test_l11_the_settings_update_never_carries_another_field(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(disk_gb=30, max_vcpus=16, nodes=2, idle_minutes=60))
    assert w.sweep().code == 0
    for update in [e for e in w.management() if e["route"] == "PATCH /v1/management/settings"]:
        assert set(update["body"]) <= SETTINGS_FIELDS, update["body"]
        assert update["body"]["inactivity_timeout_seconds"] == 3600 and update["body"]["max_vcpus"] == 16


def test_l12_the_coordinator_runs_with_telemetry_off_the_cloud_and_region_and_never_private(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BURLA_PRIVATE", "True")
    w.write_spec(table=cloud_table())
    assert w.sweep().code == 0
    (head,) = w.heads()
    env = head["env"]
    assert env.get("DISABLE_BURLA_TELEMETRY") == "True", env
    assert env.get("BURLA_CLOUD") == "aws" and env.get("AWS_REGION") == REGION, env
    assert "BURLA_PRIVATE" not in env, env
    for job in w.jobs():
        assert job["env"]["DISABLE_BURLA_TELEMETRY"] == "True", job["env"]
        assert job["env"]["BURLA_CLUSTER_DASHBOARD_URL"] == _head_url(w), job["env"]


# ---------- L13: the ledger around the cluster ----------


def test_l13_the_ledger_opens_before_the_coordinator_and_closes_after_the_stop(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    assert w.sweep().code == 0
    (start,) = [e for e in w.management() if e["route"] == "head start"]
    opened = [json.loads(line) for line in start["snapshots"]["ledger"].splitlines() if line.strip()]
    assert [e["event"] for e in opened] == ["open"], opened
    assert {"provider", "region", "machine_type", "account"} <= set(opened[0]), opened[0]
    assert opened[0]["account"] == "6030…4933" and ACCOUNT not in json.dumps(w.ledger()), opened[0]
    stop_answered = max(e["time"] for e in w.answers() if e["route"].startswith("POST /v1/management/cluster/stop"))
    close = w.ledger()[-1]
    assert close["event"] == "close" and close["end"] >= stop_answered, (close, stop_answered)


@pytest.mark.parametrize("how", ["stop-answers-an-error", "nodes-still-listed"])
def test_l13_a_failed_stop_closes_error_leaves_the_record_stopping_and_exits_3(w: CloudWorld, how: str) -> None:
    if how == "stop-answers-an-error":
        w.script_cluster(stop_fails={"code": "PROVIDER_ERROR", "message": "terminate refused"})
    else:
        w.script_cluster(stop_leaves=1)
        w.set_constant("_STOP_POLL_S", 1.0)
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 3, done
    assert re.fullmatch(
        rf"error: the nodes may still be running in {REGION}; Prove could not confirm they stopped "
        r"\(1 listed after .+\)", done.errors[-1]), done
    assert done.nexts[-1] == "next: poisson-prove where", done
    assert w.ledger()[-1]["ended"] == "error", w.ledger()
    record = w.record()
    assert record is not None and record["state"] == "stopping", record


# ---------- L14: one sweep per account at a time ----------


def test_l14_a_second_sweep_on_the_account_is_refused_while_the_first_runs(held: CloudWorld) -> None:
    proc = start_held(held)
    try:
        before = len(held.management())
        heads = len(held.heads())
        held.write_spec(table=cloud_table(ledger="ledger2.jsonl"))
        done = held.sweep()
        assert done.code == 1, done
        assert done.errors == [
            f"error: another sweep is running on this AWS account from this machine (process {proc.pid})"
        ], done
        assert len(held.management()) == before and len(held.heads()) == heads
    finally:
        os.killpg(proc.pid, signal.SIGINT)
        finish(proc)
    assert ended_clean(held) == []
