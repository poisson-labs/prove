"""What the cloud itself holds after the cluster's stop: rulings 2, 3 and 4 of the Prove 0.3.0
AWS check (2026-11-12).

The check found two things the cluster software's own status does not show. A Ctrl-C during the
boot reached 1.8.4's ``cluster stop`` while one RunInstances was in flight: the status said
``off``, the node launched a second later, never reached a coordinator, had no watchdog and ran
until it was terminated by hand (case c). And instances still shutting down count against the
account's vCPU quota, so a sweep started right after another's stop was refused by EC2 while the
quota itself fitted, and Prove said the quota was too small and that 4 nodes stopped when one had
started (case a, finding 2). The rulings:

- **AWS2.** Prove's stop (spec §6.2 step 10) also waits, up to 120 s, until no instance its sweep
  launched is pending, running or shutting down in the cloud, read with a read-only
  ``aws ec2 describe-instances`` filtered by the ``burla-cluster-node`` tag, the launch time since
  the record's ``started_at``.
- **AWS3.** EC2's ``VcpuLimitExceeded`` at the start (§7.4) names the likelier cause when the
  account's quota itself fits the cluster; and the ``stopped  N nodes, up …`` line counts the
  nodes that started, not the nodes asked for.
- **AWS4.** After the cluster software reports ``off``, Prove terminates with the AWS CLI any
  instance tagged ``burla-cluster-node`` launched since the record's ``started_at`` that is not yet
  terminated, and says so in one ``note:`` line; bare ``where`` and the next cloud sweep do the
  same for the last record's window (its ``started_at`` to its ``stopped_at``).

On the fakes of ``rb_cloud_support.py``: the fake AWS CLI answers ``ec2 describe-instances`` and
``ec2 terminate-instances`` over the fake cluster's nodes (``bu_fixtures/fake_ec2.py``), and the
fake cluster scripts the two behaviours of the check: ``launch_in_flight`` (case c's node) and
``shutdown_s`` with ``quota_vcpus`` (finding 2).

**What the tests fix that the rulings left open** (each a yes/no of the fix session's log):

- The cloud is read after the coordinator is stopped, so no launch of the software's can follow
  the read; and only when the sweep asked for nodes (no read when the start never reached
  ``cluster start``, nor when foreign nodes were found and left alone).
- A sweep that asked for nodes keeps ``booted_at``, ``region`` and, once stopped, ``stopped_at`` in
  its record; ``where`` and the next sweep read the window from them.
- Instances still shutting down when the 120 s end are not an error (they no longer bill); one
  still pending or running is: the stop could not be confirmed (§6.4's error), exit 3.
- When the cloud cannot be read the sweep's result stands, with one note, and the stopped line
  counts what the software listed.
- The notes' words, pinned below.

The AWS rerun of 2026-11-12 found two more, both at a start AWS refused before any instance
launched (an organization's service control policy, put in place by the account's spend limit),
both ruled yes the same day:

- **R1.** A start failure exits 1 when the cloud shows no instance launched for the sweep, as §6.3
  and §7.4 say, though 1.8.4's status still lists the refused nodes as booting; the ledger keeps
  charging its allowances. When the cloud cannot be read, the software's count stands.
- **R2.** When the software's ``UnauthorizedOperation`` text names a service control policy, Prove
  says a policy on the account (such as a spend limit) does not allow starting instances, with
  ``next: check the account's spend limit, or ask its administrator``, not the sign-in line.
"""

from __future__ import annotations

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
    MACHINE,
    PRICE,
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
    _events,
    assert_no_forbidden_route,
    ended_clean,
    finish,
    hold_spec,
    start_held,
    the_run,
)

DESCRIBE = ["ec2", "describe-instances", "--region", REGION, "--filters",
            "Name=tag:burla-cluster-node,Values=true", "--output", "json"]
TERMINATED = re.compile(
    r"^note: the cluster software stopped, but (?P<n>\d+) nodes? it launched for (?P<whose>this sweep|"
    r'the sweep of "[^"]+") (?:was|were) still running in ' + re.escape(REGION)
    + r"; Prove terminated (?:it|them) with the AWS CLI \((?P<ids>i-[0-9a-f]+(?:, i-[0-9a-f]+)*)\)$"
)
UNREAD = re.compile(
    r"^note: Prove could not read this AWS account's instances in " + re.escape(REGION)
    + r", so it could not check that every node launched for (?:this sweep|the sweep of \"[^\"]+\") "
    r"has stopped(?:; poisson-prove where checks again)?$"
)
IN_USE = (f"error: your AWS account's vCPU quota in {REGION} is in use (the last cluster may still be "
          "stopping); try again in a minute, lower nodes, or ask AWS for more")
TOO_SMALL = (f"error: your AWS account's vCPU quota in {REGION} is too small for 1 × {MACHINE}; lower "
             "nodes, or ask AWS for more")
UNCONFIRMED = re.compile(
    rf"^error: the nodes may still be running in {REGION}; Prove could not confirm they stopped "
    r"\((?P<listed>\d+) listed after .+\)$"
)
VCPU_MESSAGE = ("503: {'title': 'An error occurred (VcpuLimitExceeded) when calling the RunInstances "
                "operation: You have requested more vCPU capacity than your current vCPU limit of 40 "
                "allows'}")


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
        made.set_constant("_CLOUD_POLL_S", 0.1)
        yield made
        assert_no_forbidden_route(made)
        assert _only_reads_and_terminates(made) == []


@pytest.fixture
def held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fresh_pool: Pool) -> Iterator[CloudWorld]:
    with world(tmp_path, monkeypatch, fresh_pool) as made:
        made.set_constant("_CLOUD_POLL_S", 0.1)
        yield made
        assert_no_forbidden_route(made)
        assert _only_reads_and_terminates(made) == []


def _only_reads_and_terminates(w: CloudWorld) -> list[str]:
    """In every test here: the cloud is asked only to describe the tagged instances of the sweep's
    region and to terminate instances it showed; each call in a session of its own."""
    problems = []
    for call in w.aws_calls():
        argv = call["argv"]
        if argv[:1] != ["ec2"]:
            continue
        if call["sid"] != call["pid"] or call["sid"] == os.getsid(0):
            problems.append(f"not in a session of its own: {argv}")
        if argv == DESCRIBE:
            continue
        if argv[:4] == ["ec2", "terminate-instances", "--region", REGION] and argv[4] == "--instance-ids" \
                and argv[-2:] == ["--output", "json"] and all(i.startswith("i-") for i in argv[5:-2]):
            continue
        problems.append(f"an EC2 call that is neither: {argv}")
    return problems


def terminations(w: CloudWorld) -> list[list[str]]:
    """The instance ids of each terminate-instances call, in order."""
    return [argv[5:-2] for argv in w.ec2_calls() if argv[1] == "terminate-instances"]


def describes(w: CloudWorld) -> list[dict[str, Any]]:
    return [c for c in w.aws_calls() if c["argv"] == DESCRIBE]


def notes(err: str, pattern: re.Pattern[str]) -> list[re.Match[str]]:
    return [m for m in (pattern.match(line) for line in err.splitlines()) if m]


def stopped_lines(err: str) -> list[str]:
    return [line for line in err.splitlines() if re.match(r"^stopped  \d+ nodes?, up ", line)]


def route_time(w: CloudWorld, route: str, *, after: float = 0.0) -> float:
    return min(e["time"] for e in w.management() if e["route"] == route and e["time"] > after)


# ---------- AWS2: the stop waits for the cloud ----------


def test_aws2_the_wait_is_up_to_120_seconds() -> None:
    assert cloud_module()._CLOUD_WAIT_S == 120.0  # noqa: SLF001


def test_aws2_the_stop_returns_once_the_sweeps_instances_are_terminated(w: CloudWorld) -> None:
    w.script_cluster(shutdown_s=1.5)
    w.write_spec(table=cloud_table(nodes=2))
    done = w.sweep()
    assert done.code == 0, done
    assert w.not_terminated() == [], w.instances()
    assert len(w.instances()) == 2, w.instances()
    assert len(describes(w)) >= 2, "the stop did not read the cloud again while the nodes shut down"
    assert terminations(w) == [], "nothing was left for Prove to terminate"
    assert not notes(done.err, TERMINATED), done.err
    record = w.record()
    assert record is not None and record["state"] == "stopped", record
    stop = route_time(w, "POST /v1/management/cluster/stop")
    assert float(record["stopped_at"]) >= stop + 1.5 - 0.2, (record, stop)
    assert ended_clean(w) == [], done


def test_aws2_the_cloud_is_read_after_the_coordinator_stops_and_never_before_the_nodes(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(nodes=2))
    done = w.sweep()
    assert done.code == 0, done
    names = [n for _, n in sorted(_events(w))]
    assert names[-len(DONE_ORDER):] == DONE_ORDER, names
    reads = describes(w)
    assert reads, "the stop did not read the cloud"
    head_stop = route_time(w, "head stop")
    assert all(c["time"] > head_stop for c in reads), "the cloud was read before the coordinator stopped"
    close = next(e for e in w.ledger() if e["event"] == "close")
    assert all(c["time"] < close["end"] + 1 for c in reads)


def test_aws2_back_to_back_sweeps_fit_a_quota_that_holds_one_cluster(w: CloudWorld) -> None:
    """Finding 2: a quota of 24 vCPUs holds one cluster of 2 × m7i.2xlarge (16), not two; the first
    cluster's instances shut down for a while after the software's stop."""
    w.aws_state(quota=24)
    w.script_cluster(shutdown_s=6, quota_vcpus=24)
    w.write_spec(table=cloud_table(nodes=2))
    first = w.sweep()
    assert first.code == 0, first
    second = w.sweep()
    assert second.code == 0, second
    assert second.errors == [], second
    assert len(w.instances()) == 4 and w.not_terminated() == [], w.instances()


def test_aws2_instances_still_shutting_down_at_the_limit_end_the_wait_without_an_error(w: CloudWorld) -> None:
    w.set_constant("_CLOUD_WAIT_S", 1.0)
    w.script_cluster(shutdown_s=60)
    w.write_spec(table=cloud_table(nodes=2))
    t0 = time.time()
    done = w.sweep()
    assert done.code == 0, done
    assert time.time() - t0 < 30, "the wait did not end at its limit"
    assert {i["state"] for i in w.instances()} == {"shutting-down"}, w.instances()
    assert done.errors == [] and terminations(w) == [], done
    record = w.record()
    assert record is not None and record["state"] == "stopped", record


@pytest.mark.parametrize("ending", ["coordinator-failed", "foreign-nodes"])
def test_aws2_no_cloud_call_when_the_sweep_asked_for_no_node(w: CloudWorld, ending: str) -> None:
    if ending == "coordinator-failed":
        w.script_cluster(head_fails="HEAD_UNREACHABLE: the head did not become ready")
    else:
        w.script_cluster(preexisting=[{"status": "READY"}])
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert w.ec2_calls() == [], w.ec2_calls()
    if ending == "foreign-nodes":
        assert [i["state"] for i in w.instances()] == ["running"], "a node Prove did not start was touched"
    # Nor do bare where and the next sweep look at a window in which no node was asked for.
    assert w.run("where").code == 0
    assert w.ec2_calls() == [], w.ec2_calls()


# ---------- AWS3: the quota's line and the count of nodes that started ----------


def test_aws3_vcpu_limit_with_a_quota_that_fits_says_it_is_in_use(w: CloudWorld) -> None:
    w.script_cluster(start_fails_after={"nodes": 0, "message": VCPU_MESSAGE})
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert done.errors == [IN_USE], done
    assert done.nexts == [], done


def test_aws3_vcpu_limit_with_a_quota_not_read_says_it_is_too_small(w: CloudWorld) -> None:
    w.aws_state(quota="denied")
    w.script_cluster(start_fails_after={"nodes": 0, "message": VCPU_MESSAGE})
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert done.errors == [TOO_SMALL], done


def test_aws3_finding_2_the_quota_held_by_the_last_cluster_and_one_node_started(w: CloudWorld) -> None:
    """Case a's second sweep, as the check saw it when the stop did not wait: one node launched,
    the next refused by EC2 while the first cluster's instances were shutting down."""
    w.aws_state(quota=24)
    w.script_cluster(shutdown_s=60, quota_vcpus=24)
    w.write_spec(table=cloud_table(nodes=2))
    w.set_constant("_CLOUD_WAIT_S", 0.0)
    assert w.sweep().code == 0
    done = w.sweep()
    assert done.code == 3, done
    assert done.errors == [IN_USE], done
    (line,) = stopped_lines(done.err)
    assert line.startswith("stopped  1 node, up "), done.err


def test_aws3_the_stopped_line_counts_the_nodes_that_started(w: CloudWorld) -> None:
    w.script_cluster(start_fails_after={"nodes": 1, "message": "503: {'title': 'INSUFFICIENT_INSTANCE_CAPACITY'}"})
    w.write_spec(table=cloud_table(nodes=3))
    done = w.sweep()
    assert done.code == 3, done
    (line,) = stopped_lines(done.err)
    assert line.startswith("stopped  1 node, up "), done.err


def test_aws3_unread_cloud_counts_what_the_software_listed_and_says_so_once(w: CloudWorld) -> None:
    w.aws_state(ec2_denied=["describe-instances"])
    w.write_spec(table=cloud_table(nodes=2))
    done = w.sweep()
    assert done.code == 0, done
    (line,) = stopped_lines(done.err)
    assert line.startswith("stopped  2 nodes, up "), done.err
    assert len(notes(done.err, UNREAD)) == 1, done.err
    assert notes(done.err, UNREAD)[0].group(0).endswith("this sweep has stopped; poisson-prove where checks again"), done.err
    record = w.record()
    assert record is not None and record["state"] == "stopped", record
    assert ended_clean(w) == [], done


# ---------- AWS4: what the software missed is terminated ----------


def test_aws4_case_c_ctrl_c_during_the_boot_with_a_launch_in_flight(held: CloudWorld) -> None:
    held.script_cluster(start_hangs=True, launch_in_flight={"nodes": 1})
    hold_spec(held, nodes=2)
    proc = held.spawn()
    wait_for(lambda: sum(n["status"] == "BOOTING" for n in held.cluster()["nodes"]) == 2
             or proc.poll() is not None, 120, "the boot")
    os.killpg(proc.pid, signal.SIGINT)
    code, out, err = finish(proc)
    assert code == 130, (out, err)
    assert "Traceback" not in err, err
    (orphan,) = [n for n in held.cluster()["nodes"] if n["status"] in ("ORPHAN", "TERMINATED")]
    assert terminations(held) == [[orphan["id"]]], held.ec2_calls()
    assert held.not_terminated() == [], held.instances()
    (note,) = notes(err, TERMINATED)
    assert note["n"] == "1" and note["whose"] == "this sweep" and note["ids"] == orphan["id"], err
    assert "was still running" in note.group(0) and "terminated it with" in note.group(0), err
    (line,) = stopped_lines(err)
    assert line.startswith("stopped  2 nodes, up "), err
    assert ended_clean(held) == [], err
    assert held.ledger()[-1]["ended"] == "cancelled", held.ledger()


def test_aws4_case_c_when_the_terminate_is_refused_the_stop_is_not_confirmed(held: CloudWorld) -> None:
    held.set_constant("_CLOUD_WAIT_S", 1.0)
    held.aws_state(ec2_denied=["terminate-instances"])
    held.script_cluster(start_hangs=True, launch_in_flight={"nodes": 1})
    hold_spec(held, nodes=2)
    proc = held.spawn()
    wait_for(lambda: sum(n["status"] == "BOOTING" for n in held.cluster()["nodes"]) == 2
             or proc.poll() is not None, 120, "the boot")
    os.killpg(proc.pid, signal.SIGINT)
    code, out, err = finish(proc)
    assert code == 3, (out, err)
    errors = [line for line in err.splitlines() if line.startswith("error:")]
    assert len(errors) == 1 and (m := UNCONFIRMED.match(errors[0])) and m["listed"] == "1", err
    assert "next: poisson-prove where" in out + err, (out, err)
    record = held.record()
    assert record is not None and record["state"] == "stopping", record
    assert held.ledger()[-1]["ended"] == "error", held.ledger()
    # The next where, allowed to terminate, finishes the job.
    held.aws_state(ec2_denied=[])
    done = held.run("where")
    assert done.code == 0, done
    assert held.not_terminated() == [], held.instances()
    assert len(notes(done.err, TERMINATED)) == 1, done.err
    record = held.record()
    assert record is not None and record["state"] == "stopped", record


@pytest.mark.parametrize("by", ["where", "next-sweep"])
def test_aws4_a_node_the_stop_did_not_see_is_terminated_by_bare_where_or_the_next_sweep(
    w: CloudWorld, by: str
) -> None:
    """The node of case c, seen by the cloud only after Prove's own read (DescribeInstances is
    eventually consistent): the last record's window still holds it."""
    w.write_spec(table=cloud_table(nodes=2))
    first = w.sweep()
    assert first.code == 0, first
    record = w.record()
    assert record is not None
    name = next(r["run_name"] for r in w.runs() if r["run_id"] == record["run_id"])
    late = w.add_instance(launched_at=float(record["stopped_at"]) - 0.01)
    before = time.time()
    done = w.run("where") if by == "where" else w.sweep()
    assert done.code == 0, done
    assert terminations(w) == [[late]], w.ec2_calls()
    assert w.not_terminated() == [], w.instances()
    (note,) = notes(done.err, TERMINATED)
    assert note["whose"] == f'the sweep of "{name}"' and note["ids"] == late, done.err
    if by == "next-sweep":
        terminate = next(c for c in w.aws_calls() if c["argv"][1:2] == ["terminate-instances"])
        assert terminate["time"] < route_time(w, "head start", after=before), \
            "the next sweep started its coordinator before it terminated the last sweep's node"


def test_aws4_the_last_records_window_leaves_what_was_launched_outside_it(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    assert w.sweep().code == 0
    record = w.record()
    assert record is not None
    earlier = w.add_instance(launched_at=float(record["started_at"]) - 60)
    later = w.add_instance(launched_at=time.time() + 0.5)
    time.sleep(0.6)
    done = w.run("where")
    assert done.code == 0, done
    assert terminations(w) == [], w.ec2_calls()
    assert {i["id"] for i in w.not_terminated()} == {earlier, later}, w.instances()
    assert not notes(done.err, TERMINATED), done.err


def test_aws4_where_says_when_the_terminate_is_refused_and_exits_3(w: CloudWorld) -> None:
    w.set_constant("_CLOUD_WAIT_S", 1.0)
    w.write_spec(table=cloud_table())
    assert w.sweep().code == 0
    record = w.record()
    assert record is not None
    late = w.add_instance(launched_at=float(record["stopped_at"]) - 0.01)
    w.aws_state(ec2_denied=["terminate-instances"])
    done = w.run("where")
    assert done.code == 3, done
    assert len(done.errors) == 1 and (m := UNCONFIRMED.match(done.errors[0])) and m["listed"] == "1", done
    assert [i["id"] for i in w.not_terminated()] == [late], w.instances()
    w.aws_state(ec2_denied=[])
    assert w.run("where").code == 0
    assert w.not_terminated() == [], w.instances()


def test_aws4_a_sweep_that_died_is_stopped_and_its_missed_node_terminated(held: CloudWorld) -> None:
    """Case f's path with case c's node: Prove and the coordinator killed mid-job, a node of the
    sweep the software never listed; bare where stops the leftover, then terminates the node."""
    proc = start_held(held, nodes=1)
    record = held.record()
    assert record is not None and record["state"] == "running", record
    late = held.add_instance(launched_at=float(record["booted_at"]) + 0.01)
    os.kill(proc.pid, signal.SIGKILL)
    proc.wait(timeout=30)
    for head in held.alive_heads():
        os.kill(head, signal.SIGKILL)
        wait_for(lambda head=head: not alive(head), 10, "the coordinator to die")
    run = the_run(held)
    name = next(r["run_name"] for r in held.runs() if r["run_id"] == run)
    done = held.run("where")
    assert done.code == 0, done
    left = [line for line in done.err.splitlines() if line.startswith("note: the cluster from the sweep of")]
    assert len(left) == 1, done.err
    (note,) = notes(done.err, TERMINATED)
    assert note["whose"] == f'the sweep of "{name}"' and note["ids"] == late, done.err
    assert held.not_terminated() == [], held.instances()
    record = held.record()
    assert record is not None and record["state"] == "stopped", record


def test_aws4_the_record_keeps_the_window(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    t0 = time.time()
    assert w.sweep().code == 0
    record = w.record()
    assert record is not None
    assert record["region"] == REGION, record
    assert t0 <= float(record["started_at"]) <= float(record["booted_at"]) <= float(record["stopped_at"]) <= time.time()
    (instance,) = w.instances()
    assert float(record["booted_at"]) <= instance["launched_at"] <= float(record["stopped_at"])
    assert f"aws-{ACCOUNT}.json" in w.records()


# ---------- R1 and R2 of the AWS rerun: a start AWS refused before any instance launched ----------

#: 1.8.4's ``PROVIDER_ERROR`` text in the rerun's blocked attempt (22:52Z), the ids changed.
REFUSED_BY_POLICY = (
    "An error occurred (UnauthorizedOperation) when calling the RunInstances operation: You are not "
    f"authorized to perform this operation. User: arn:aws:sts::{ACCOUNT}:assumed-role/AccountFullAccessRole/"
    "a448f408 is not authorized to perform: ec2:RunInstances on resource: "
    f"arn:aws:ec2:{REGION}:{ACCOUNT}:instance/* with an explicit deny in a service control policy: "
    "arn:aws:organizations::111122223333:policy/o-exampleorg1/service_control_policy/p-example1. "
    "Encoded authorization failure message: <encoded>"
)
REFUSED_BY_SIGN_IN = (
    "An error occurred (UnauthorizedOperation) when calling the RunInstances operation: You are not "
    f"authorized to perform this operation. User: arn:aws:iam::{ACCOUNT}:user/reader is not authorized "
    f"to perform: ec2:RunInstances on resource: arn:aws:ec2:{REGION}:{ACCOUNT}:instance/* because no "
    "identity-based policy allows the ec2:RunInstances action. Encoded authorization failure message: "
    "<encoded>"
)
POLICY = (f"error: a policy on this AWS account (such as a spend limit) does not allow starting "
          f"instances in {REGION}")
POLICY_NEXT = "next: check the account's spend limit, or ask its administrator"
SIGN_IN = f"error: your AWS sign-in is not allowed to start instances in {REGION}"


def test_r1_a_start_refused_before_any_instance_launched_exits_1_though_the_software_lists_nodes(w: CloudWorld) -> None:
    """The rerun's blocked attempt: EC2 refused every RunInstances, 1.8.4's status after the
    refusal still said booting (3 of 4), and Prove exited 3 with ``stopped  0 nodes``."""
    w.script_cluster(start_fails_after={"nodes": 0, "listed": 3, "message": REFUSED_BY_SIGN_IN})
    w.write_spec(table=cloud_table(nodes=4))
    done = w.sweep()
    assert done.code == 1, done
    assert done.errors == [SIGN_IN], done
    assert "no rollout was stored" not in done.out + done.err, done
    (line,) = stopped_lines(done.err)
    assert line.startswith("stopped  0 nodes, up "), done.err
    assert w.instances() == [], w.instances()
    assert len(describes(w)) >= 1, "the cloud was not read"
    assert terminations(w) == [], "there was nothing to terminate"
    names = [n for _, n in sorted(_events(w))]
    assert names.count("cluster stop") == 1, names
    # The ledger still charges the allowances, as designed: no node is not no charge.
    close = w.ledger()[-1]
    assert close["event"] == "close" and close["ended"] == "error", w.ledger()
    assert close["charge"] >= 4 * PRICE * 2 / 60, close
    record = w.record()
    assert record is not None and record["state"] == "stopped", record
    assert ended_clean(w) == [], done


def test_r1_when_the_cloud_cannot_be_read_the_softwares_count_stands_and_exits_3(w: CloudWorld) -> None:
    w.aws_state(ec2_denied=["describe-instances"])
    w.script_cluster(start_fails_after={"nodes": 0, "listed": 3, "message": REFUSED_BY_SIGN_IN})
    w.write_spec(table=cloud_table(nodes=4))
    done = w.sweep()
    assert done.code == 3, done
    assert done.errors == [SIGN_IN], done
    assert len(notes(done.err, UNREAD)) == 1, done.err


def test_r1_a_start_that_launched_one_instance_before_the_refusal_still_exits_3(w: CloudWorld) -> None:
    w.script_cluster(start_fails_after={"nodes": 1, "listed": 2, "message": REFUSED_BY_SIGN_IN})
    w.write_spec(table=cloud_table(nodes=4))
    done = w.sweep()
    assert done.code == 3, done
    (line,) = stopped_lines(done.err)
    assert line.startswith("stopped  1 node, up "), done.err
    assert w.not_terminated() == [], w.instances()


def test_r2_a_service_control_policy_deny_reads_as_a_policy_on_the_account(w: CloudWorld) -> None:
    w.script_cluster(start_fails_after={"nodes": 0, "listed": 3, "message": REFUSED_BY_POLICY})
    w.write_spec(table=cloud_table(nodes=4))
    done = w.sweep()
    assert done.code == 1, done
    assert done.errors == [POLICY], done
    assert done.nexts == [POLICY_NEXT], done
    assert "sign-in" not in done.out + done.err, done
    assert "aws login" not in done.out + done.err, done
    assert ended_clean(w) == [], done


def test_r2_any_other_unauthorized_operation_keeps_the_sign_in_line(w: CloudWorld) -> None:
    w.script_cluster(start_fails_after={"nodes": 0, "message": REFUSED_BY_SIGN_IN})
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert done.errors == [SIGN_IN], done
    assert done.nexts == [], done
