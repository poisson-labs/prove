"""C4 of 0.3.0, Remote backends: what the reader sees of a sweep on their cloud account.

The frozen tests for V1 to V5 (Remote Backends Spec §7.4, §8, §9 and §15 C4; RB-9, RB-29, RB-41),
on the fakes of ``rb_cloud_support.py``.

**What the tests fix that the invariants leave open:**

- The plan's lines after its verdict line are, in order, ``target``, ``outcomes``, ``Sweep:``,
  ``Backend:``, ``Account:``, ``Cluster:``, ``Bundle:``, ``Worker view:``, ``Traffic:``, ``Cost:``
  and ``Chaos:`` (the design's line, when there is one, is the plan's own, as for every backend).
  The verdict's sentence and the ``Cost:`` line name the same price and source; the ``Bundle:``
  line is 0.2.1's (its packages, size and digest), which rule 10 cuts to 12 hex characters.
- The bound in the ``Cluster:`` line is ``max(idle_minutes, 3)`` minutes (C3's yes/no).
- Plain progress (stderr not a terminal) prints each of §9's cluster lines once: ``starting``,
  ``ready``, ``stopping``, ``stopped``, with counts and durations by rule 10.
- ``--json``'s result document carries ``cluster``: ``provider``, ``region``, ``machine_type``,
  ``nodes``, ``started``, ``stopped`` (UTC, ``Z``) and ``up_seconds``; the plan's document carries
  ``plan.cloud`` with at least ``provider``, ``region``, ``machine_type``, ``nodes``, ``max_vcpus``,
  ``image``, ``account`` (masked), ``usd_per_node_hour`` and ``price_asof``.
- §7.4's lines are the spec's; the software's own text goes to the cluster software's log under
  Prove's state folder (``$XDG_STATE_HOME/poisson-prove/cloud/``), never to the screen. The
  ``NoNodes``, ``NoCompatibleNodes`` and ``JobStalled`` lines carry no command of the software's.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from pf6_support import run_pty, says, strip_escapes
from poisson_prove import _look
from rb_cloud_support import (
    MACHINE,
    MASKED,
    PRICE,
    PRICE_DATE,
    PROVE,
    REGION,
    TARGETS,
    CloudWorld,
    Pool,
    cloud_table,
    this_minor,
    world,
)

DURATION = r"(?:\d+\.\d s|\d+ min \d+ s|\d+ h \d+ min)"
DOLLARS = r"\$(?:0|\d{1,3}(?:,\d{3})*\.\d\d|0\.0\d+)"
LABELS = ["target", "outcomes", "Sweep:", "Backend:", "Account:", "Cluster:", "Bundle:", "Worker view:",
          "Traffic:", "Cost:", "Chaos:"]
TRAFFIC = ("Traffic: your code, its inputs and its results go between this machine and the nodes through "
           "Burla's relay (the cluster software Prove uses); the store stays on this machine")


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    with world(tmp_path, monkeypatch, pool) as made:
        yield made


def estimate(rollouts: int, *, nodes: int, slots: int, batch: int, est: float, boot: float, idle: float,
             price: float = PRICE) -> float:
    batches = -(-rollouts // batch)
    waves = -(-batches // (nodes * slots))
    return nodes * price * (boot + waves * batch * est / 60 + idle) / 60


def spec_like_the_example(w: CloudWorld) -> None:
    """§8's example's shape: 4 × m7i.2xlarge in us-east-2, stop $2, cap $3, the default allowances."""
    w.aws_state(quota=40)
    w.write_spec(table=cloud_table(nodes=4, ledger="cloud-ledger.jsonl", stop_cost=2.0, max_cost=3.0,
                                   boot_minutes=None, idle_minutes=None, batch_size=None),
                 cells=("a", "b", "c"), replicates=3, axes={"tool": ["x", "y", "z"]})


# ---------- V1: the plan ----------


def plan_lines(out: str) -> list[str]:
    return [line for line in out.splitlines()[1:] if line.strip() and not line.strip().startswith("smallest")]


def test_v1_the_plan_is_the_specs_block_line_for_line(w: CloudWorld) -> None:
    spec_like_the_example(w)
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    first, *_ = done.out.splitlines()
    cost = _look.fmt_dollars(estimate(27, nodes=4, slots=8, batch=256, est=0.01, boot=5.0, idle=5.0))
    source = f"4 × {MACHINE} at ${PRICE}/node-hour, Prove's AWS prices for {REGION} of {PRICE_DATE}"
    assert first == (f"plan  27 rollouts of rb-cloud@v0: 9 cells x 3 replicates on your AWS account, "
                     f"~{cost} this run ({source}) · ledger cloud-ledger.jsonl $0 so far · stop $2.00 · cap $3.00"), first
    lines = [line.strip() for line in plan_lines(done.out)]
    assert [next(lab for lab in LABELS if line.startswith(lab)) for line in lines] == LABELS, lines
    by = {lab: next(line for line in lines if line.startswith(lab)) for lab in LABELS}
    assert by["Sweep:"] == "Sweep: 2 axes · 9 cells · N=3 → 27 rollouts", by["Sweep:"]
    assert by["Backend:"] == "Backend: cloud · AWS · target: rb-cloud@v0 · t_unit: steps", by["Backend:"]
    assert by["Account:"] == f"Account: AWS {MASKED}, signed in with the AWS CLI", by["Account:"]
    assert by["Cluster:"] == (
        f"Cluster: Prove starts 4 × {MACHINE} in {REGION} (8 vCPU each, 32 in all, ceiling 32) running "
        f"python:{this_minor()}, and stops them when the sweep ends · 8 slots each · 32 at once · if this "
        "machine stops first, the nodes stop themselves within 5 min · this machine is kept from idle sleep "
        "while they run"), by["Cluster:"]
    assert re.fullmatch(r"Bundle: poisson_prove \S+, bu_targets .+ · \d+\.\d MB · sha256 [0-9a-f]{12}…",
                        by["Bundle:"]), by["Bundle:"]
    assert by["Worker view:"] == "Worker view: job 0 matches this machine"
    assert by["Traffic:"] == TRAFFIC, by["Traffic:"]
    assert by["Cost:"] == (f"Cost: ~{cost} this run ({source}) · ledger cloud-ledger.jsonl $0 so far · "
                           "stop $2.00 · cap $3.00"), by["Cost:"]
    assert by["Chaos:"] == "Chaos: none"


def test_v1_the_bound_is_the_larger_of_the_idle_stop_and_the_orphan_rule(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(idle_minutes=2))
    done = w.sweep("--dry-run")
    assert "the nodes stop themselves within 3 min" in done.out, done
    w.write_spec(table=cloud_table(idle_minutes=12))
    done = w.sweep("--dry-run")
    assert "the nodes stop themselves within 12 min" in done.out, done


def test_v1_pretty_draws_the_same_facts(w: CloudWorld) -> None:
    spec_like_the_example(w)
    plain = w.sweep("--dry-run")
    assert plain.code == 0, plain
    config = w.config()
    argv = w.argv("sweep", "prove.toml", "--target", "bu_targets.cloud:quick", "--backend", "cloud",
                  "--max-mde", "1", "--dry-run")
    pretty = run_pty([], home=w.home, cwd=w.root, paths=(TARGETS,), cols=240, rows=60,
                     command=[str(PROVE), str(config), *argv])
    assert pretty.code == 0, pretty.err
    screen = strip_escapes(pretty.out)
    for line in [plain.out.splitlines()[0], *plan_lines(plain.out)]:
        label, _, value = line.strip().partition(": ")
        assert says(screen, value or label), (line, screen[-3000:])


# ---------- V2: progress ----------


def test_v2_the_status_behind_the_starting_line_is_asked_every_10_seconds() -> None:
    from rb_cloud_support import cloud_module

    assert cloud_module()._STATUS_S == 10.0  # noqa: SLF001


def test_v2_progress_is_the_cluster_lines_on_stderr_and_none_on_stdout(w: CloudWorld) -> None:
    # Several status polls while the nodes boot: plain still prints the starting line once.
    w.set_constant("_STATUS_S", 0.1)
    w.script_cluster(boot_s=0.4)
    w.write_spec(table=cloud_table(nodes=2))
    done = w.sweep()
    assert done.code == 0, done
    patterns = [
        rf"starting  2 × {re.escape(MACHINE)} in {REGION}  0 of 2 ready · {DURATION}",
        rf"ready  2 nodes · 16 vCPU · {DURATION}",
        r"stopping  the cluster",
        rf"stopped  2 nodes, up {DURATION}",
    ]
    lines = done.err.splitlines()
    found = []
    for pattern in patterns:
        matching = [i for i, line in enumerate(lines) if re.fullmatch(pattern, line)]
        assert len(matching) == 1, (pattern, done.err)
        found.append(matching[0])
    assert found == sorted(found), done.err
    for word in ("starting  ", "ready  ", "stopping  ", "stopped  2 nodes"):
        assert not any(line.startswith(word) for line in done.out.splitlines()), done.out


def test_v2_json_carries_the_cluster_and_the_plans_cloud_object(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(nodes=2))
    plan = w.sweep("--dry-run", "--json")
    assert plan.code == 0, plan
    cloud = json.loads(plan.out)["plan"]["cloud"]
    assert {"provider", "region", "machine_type", "nodes", "max_vcpus", "image", "account",
            "usd_per_node_hour", "price_asof"} <= set(cloud), cloud
    assert (cloud["provider"], cloud["region"], cloud["machine_type"], cloud["nodes"], cloud["account"]) == (
        "aws", REGION, MACHINE, 2, MASKED), cloud
    done = w.sweep("--json")
    assert done.code == 0, done
    cluster = json.loads(done.out)["cluster"]
    assert set(cluster) == {"provider", "region", "machine_type", "nodes", "started", "stopped", "up_seconds"}, cluster
    assert (cluster["provider"], cluster["region"], cluster["machine_type"], cluster["nodes"]) == (
        "aws", REGION, MACHINE, 2), cluster
    for key in ("started", "stopped"):
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", cluster[key]), cluster
    assert isinstance(cluster["up_seconds"], (int, float)) and cluster["up_seconds"] >= 0, cluster


# ---------- V3: the result blocks ----------


def result_lines(out: str) -> list[str]:
    """Stdout from the result's verdict line on (``--yes`` prints the plan above it)."""
    lines = out.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith(("done  ", "stopped  ")))
    return lines[first:]


def cluster_line(out: str) -> str:
    (line,) = [line for line in out.splitlines() if line.startswith("  cluster  ")]
    return line


def test_v3_the_done_block_carries_the_cluster_line(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(nodes=2))
    done = w.sweep()
    assert done.code == 0 and result_lines(done.out)[0].startswith("done  "), done
    line = cluster_line(done.out)
    charge = _look.fmt_dollars(w.ledger()[-1]["charge"])
    assert re.fullmatch(rf"  cluster  2 × {re.escape(MACHINE)} up {DURATION}, stopped \d\d:\d\d:\d\dZ · "
                        rf"ledger {re.escape(charge)}", line), line


def test_v3_the_stopped_block_carries_it_too(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(), cells=("a", "b"), replicates=4)
    done = w.sweep(target="bu_targets.cloud:raises")
    assert done.code == 3 and result_lines(done.out)[0].startswith("stopped  "), done
    charge = _look.fmt_dollars(w.ledger()[-1]["charge"])
    assert re.fullmatch(rf"  cluster  1 × {re.escape(MACHINE)} up {DURATION}, stopped \d\d:\d\d:\d\dZ · "
                        rf"ledger {re.escape(charge)}", cluster_line(done.out)), done.out


# ---------- V4: start-time errors in Prove's words ----------

TOKEN = "raw-provider-text-4f7c1e"
V4 = [
    ("signed-out", f"503: {{'title': 'Not signed in to AWS', 'detail': '{TOKEN}'}}",
     ["error: the cluster could not start: this machine's AWS sign-in has expired or is missing",
      "  next: aws login"]),
    ("crt", f"503: {{'title': 'Not signed in to AWS', 'detail': 'MissingDependencyException: Missing "
            f"Dependency: ... pip install botocore[crt] {TOKEN}'}}",
     ["error: the cloud extra is incomplete: signing in with aws login needs a package it installs",
      '  next: pip install "poisson-prove[cloud]"']),
    ("vcpu", f"503: {{'title': 'An error occurred (VcpuLimitExceeded) when calling the RunInstances "
             f"operation {TOKEN}'}}",
     [f"error: your AWS account's vCPU quota in {REGION} is too small for 1 × {MACHINE}; lower nodes, or "
      "ask AWS for more"]),
    ("capacity", f"503: {{'title': 'INSUFFICIENT_INSTANCE_CAPACITY: us-east-2a currently have no {TOKEN}'}}",
     [f"error: AWS has no {MACHINE} capacity in {REGION} right now; try another machine type or region"]),
    ("unauthorized", f"503: {{'title': 'An error occurred (UnauthorizedOperation) {TOKEN}'}}",
     [f"error: your AWS sign-in is not allowed to start instances in {REGION}"]),
    ("opt-in", f"503: {{'title': 'An error occurred (OptInRequired) {TOKEN}'}}",
     [f"error: your AWS account is not opted in to {REGION}"]),
    ("relay", f"503: {{'title': 'Nodes cannot reach the head at https://x {TOKEN}'}}",
     ["error: the cluster could not open its connection to this machine; check this machine's network and "
      "run the sweep again"]),
]


def _log_holds(w: CloudWorld, token: str) -> bool:
    folder = w.xdg / "poisson-prove" / "cloud"
    return any(token in p.read_text(encoding="utf-8", errors="replace") for p in folder.rglob("*") if p.is_file())


@pytest.mark.parametrize(("case", "message", "lines"), V4, ids=[c[0] for c in V4])
def test_v4_each_start_failure_in_provers_words_and_the_raw_text_only_in_the_log(
    w: CloudWorld, case: str, message: str, lines: list[str]
) -> None:
    w.script_cluster(start_fails_after={"nodes": 0, "message": message})
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    shown = [line for line in done.err.splitlines() if line.startswith(("error:", "  next:"))]
    assert shown == lines, done
    assert TOKEN not in done.out + done.err, done
    assert _log_holds(w, TOKEN), "the software's own text is not in its log"


def test_v4_a_failure_after_a_node_started_exits_3_with_the_same_line(w: CloudWorld) -> None:
    w.script_cluster(start_fails_after={"nodes": 1, "message": f"503: {{'title': 'INSUFFICIENT_INSTANCE_CAPACITY {TOKEN}'}}"})
    w.write_spec(table=cloud_table(nodes=2))
    done = w.sweep()
    assert done.code == 3, done
    assert done.errors[-1] == f"error: AWS has no {MACHINE} capacity in {REGION} right now; try another machine type or region"


def test_v4_the_coordinator_not_starting_names_the_log(w: CloudWorld) -> None:
    w.script_cluster(head_fails=f"HEAD_UNREACHABLE: the head did not become ready {TOKEN}")
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    (error,) = done.errors
    match = re.fullmatch(r"error: the cluster software did not start on this machine; the details are in (\S+)", error)
    assert match, error
    assert Path(match[1]).is_file() and TOKEN in Path(match[1]).read_text(encoding="utf-8"), match[1]
    assert TOKEN not in done.out + done.err


@pytest.mark.parametrize("refusal", ["NoNodes", "NoCompatibleNodes", "JobStalled"])
def test_v4_the_job_refusals_carry_no_command_of_the_softwares(w: CloudWorld, refusal: str) -> None:
    w.script_job(default={"refuse": refusal})
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 3, done
    assert len(done.errors) == 1, done
    assert not re.search("burla", done.err, re.I), done
    assert "Traceback" not in done.err


def test_v4_anything_else_is_the_unexpected_failure_line_naming_the_log(w: CloudWorld) -> None:
    w.script_cluster(start_fails_after={"nodes": 0, "message": f"503: {{'title': 'something new {TOKEN}'}}"})
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code in (1, 3), done
    (error,) = done.errors
    assert re.fullmatch(r"error: an unexpected failure inside poisson-prove \(.+\); the details are in \S+", error), error
    assert TOKEN not in done.out + done.err and _log_holds(w, TOKEN)


# ---------- V5: numbers ----------


def test_v5_numbers_read_by_rule_10(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(nodes=2), cells=tuple(f"c{i}" for i in range(10)), replicates=100)
    plan = w.sweep("--dry-run")
    assert plan.code == 0, plan
    assert " 1,000 rollouts of " in plan.out.splitlines()[0], plan.out
    for money in re.findall(r"\$[0-9][0-9.,]*", plan.out):
        assert re.fullmatch(DOLLARS, money) or money.startswith("$0.4685"), money
    w.write_spec(table=cloud_table(nodes=2))
    done = w.sweep()
    assert done.code == 0, done
    progress = [line for line in done.err.splitlines() if line.startswith(("starting  ", "ready  ", "stopped  "))]
    assert progress and all(re.search(DURATION + "$", line) for line in progress), progress
    assert re.search(r"stopped \d\d:\d\d:\d\dZ", cluster_line(done.out)), done.out
    assert not re.search(r"\d{4,}(?<!,)\d* (?:rollouts|vCPU|nodes)", done.out + done.err), done
