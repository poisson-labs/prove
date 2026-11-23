"""First run, module M6: what a design costs, which axes the setup skill writes, and what a
comparison leaves out. The frozen tests for invariants C1 to C13, A1 to A8 and L1 to L5 (First Run
Spec section 12; M6-1 to M6-28 as ruled 2026-11-22).

What M6 promises, in one line: the plan never prints ``$0 (local)``, and prices the agent's own
calls only by a figure the person declares under ``[cost]``; the setup skill writes the cases and
only the axes the person asked for; and ``diff`` and ``report`` name the outcomes a comparison
leaves out. No test here calls a model, a coding agent, Modal, a cloud account or any paid
service: everything runs on the packaged mock, on rollouts the test writes (some returning a
trace with ``llm`` spans and tokens), on the demo, and on the fakes of the Modal and cloud tests.

**Readings, named here** (each a point read one way and lettered).

- (a) Facts are pinned, not sentences. "The cost phrase" of a plan is three things: what follows
  the last ``replicates on WHERE, `` of the verdict line, the ``Cost:`` line less its label, and
  ``--json``'s ``sentence`` and ``plan.cost``. On this machine with no ``[cost]`` each holds the
  words ``not priced`` and no dollar sign, and the ``Cost:`` line and ``plan.cost`` name
  ``[cost]`` (the verdict line is the short form and need not).
- (b) The ``--json`` ``cost`` object is a key of the document beside ``plan``: ``plan.cost`` is
  0.4.0's string and keeps its type under the 2026-11-20 promise. Its keys are
  ``compute_usd``, ``agent_usd_per_rollout``, ``agent_usd``, ``agent_basis``, ``total_usd`` and
  ``cap_usd``. On this machine ``compute_usd`` is 0 (this machine adds nothing), so
  ``total_usd`` is the agent's figure when one is declared and null when none is.
- (c) "The rate as the spec writes it": a figure written as plain decimals is printed back digit
  for digit after a dollar sign (``$0.0274``), though the look's rule 10 would cut a dollar amount
  below $0.10 to two significant digits. The product is spelled the look's way, after ``~``.
- (d) The declared phrase names the spec file by its name, whatever it is called.
- (e) "The rollouts this command will run": the spec's conditions times its replicates, or
  ``--replicates`` as typed; at most ``--max-rollouts`` as typed; on ``--resume`` those not yet
  stored. A paired sweep's cost line is the first sweep's.
- (f) A refusal for the cap: exit 1, one ``error:`` line, stdout empty or the plan and nothing
  after it, no store folder, the rollout never called. On this machine its ``next:`` lines are one
  command, the sweep as typed with ``--max-cost`` set to the smallest whole-cent cap that admits
  the estimate, and one line that is not a command and names fewer conditions.
- (g) On Modal and the cloud "the compute part" of a cost line is its text up to where the agent's
  part starts. With nothing declared it is followed by the cap's ``compute only`` (when a cap is
  set) and the ``not priced`` clause; with a figure declared it is followed by `` + `` and the
  agent's part, and by `` = ~$SUM`` exactly when the compute part is a figure. The compute part of
  a spec's line is the same text whether or not the spec declares ``[cost]``. That the compute
  part is 0.4.0's is held, for the cloud, by ``test_rb_cloud_look.py`` (changed by this module to
  compare it as a prefix) and for Modal by the frozen Modal tests, unchanged.
- (h) The trial's lines: ``model calls``, ``tokens`` and ``at a sweep's size`` are detail lines of
  the ``ok`` result, in that order, straight after ``t``. A trace is "one Prove cannot read" when
  ``meta["trace"]`` is not a trace document. Whether a trace with no ``llm`` span gets an
  ``at a sweep's size`` line is the build's.
- (i) ``left_out`` and the ``left out:`` clause list names in sorted order, which is the order a
  run's manifest holds its declared outcomes in. The key is present when the list is not empty;
  elsewhere it is absent or empty.
- (j) A report of one run prints its own ``inferred:`` line (``the run declared``); it names the
  outcomes left out the same way.
- (k) L3 is read on one pair: the comparison with no event named equals, key for key, the
  comparison with the same events named by ``--event``, but for ``inferred`` and ``left_out``.
  That its numbers are 0.4.0's is held by the frozen ``diff`` tests, unchanged.
- (l) The skill is pinned by structure, as K7 pins it. "The item" for the axes not added is the
  numbered item of "Hand over" straight after the one that opens ``Each axis``. The cost item is
  the one line of the confirm list that names the replicates and their cost; its six parts are
  found in order on that line.
- (m) A6, the scripted run: the stand-in for a coding agent is told what the code shows (the
  cases, what could vary, whether a model is called) and reads from the written skill what to do
  with it: which axes to write, whether to write ``[cost]``, and what the hand-over lists. A skill
  that still said "two or three axes" would have it write the model axis.
- (n) ``init --agent``'s one more line is a detail line after the ``prompt`` line; its label is
  the build's.
- (o) The docs and the CHANGELOG are pinned by facts. No page of the docs, the README or the
  example prints ``$0 (local)``; the CHANGELOG may, to say it is gone. Every cost phrase a page
  shows, on any backend, says what the agent's own calls come to.
- (p) Left to the build, and pinned nowhere here: what ``sweep --try`` does with ``--max-cost``;
  how a remote line words a rollout declared to cost nothing; whether a plan refused for its cap
  on Modal with no compute estimate names the declared spend; and what the ``planned`` line of a
  run's event log records of the cost, beyond that it does not say ``$0 (local)``.

**Seams with other modules.** The trial call, its exit codes and that it stores nothing are M4's
(K1 to K6). The skill's seven steps and shared text are PF11's and M4's. The plan's size lines
are M2's. The demo's files are M3's. The cloud and Modal fakes are 0.3.0's. The terminal app's
sweep screen is PF6's.

**Suite.** The code suite. Commands that import the person's code run as child processes.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| C1 no ``$0 (local)``; ``not priced`` and no dollar sign | ``test_c1_*`` |
| C2 ``[cost]`` read strictly | ``test_c2_*`` |
| C3 the declared estimate | ``test_c3_*`` |
| C4 ``$0`` only by declaration | ``test_c4_*`` |
| C5 compute untouched, the agent's part appended | ``test_c5_*`` |
| C6 ``--max-cost``, case by case | ``test_c6_*`` |
| C7 the trial's count | ``test_c7_*`` |
| C8 no dollars from tokens | ``test_c8_*`` |
| C9 the trial's ``cost`` line | ``test_c9_*`` |
| C10 ``--json`` | ``test_c10_*`` |
| C11 the packaged specs | ``test_c11_*`` |
| C12 nothing else moves | ``test_c12_*`` |
| C13 the app | ``test_c13_*`` |
| A1 to A5, A8 the skill's text | ``test_a1_*`` to ``test_a5_*``, ``test_a8_*`` |
| A6 the scripted run | ``test_a6_*`` |
| A7 ``init --agent``'s line | ``test_a7_*`` |
| L1 the hand-over's item | ``test_l1_*`` |
| L2 the ``inferred:`` line and ``left_out`` | ``test_l2_*``, and ``test_defaults_refusals_and_faces.py`` (changed) |
| L3 the comparison itself | ``test_l3_*`` |
| L4 ``diff --event NAME`` on an outcome left out | ``test_l4_*`` |
| L5 ``check`` | ``test_l5_*`` |
| section 12.5: the docs and the CHANGELOG | ``test_the_docs_*``, ``test_no_page_*``, ``test_every_cost_phrase_*``, ``test_the_0_5_0_*`` |
"""

from __future__ import annotations

import json
import math
import re
import shlex
import tomllib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import test_frs_m4_try as m4
import test_pf11_setup_agent as pf11
from pf6_support import Session, drive
from poisson_prove import _look
from rb_cloud_support import CloudWorld, Pool, cloud_table, world
from test_pf9_backends import make_findable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
COMMAND = "poisson-prove"
MOCK = "poisson_prove.examples.mock_agent"

#: A spec of the packaged mock: two conditions by 200 replicates, 400 rollouts.
SPEC = f"""\
target = "{MOCK}:rollout"
target_id = "priced"
t_unit = "tool_calls"
replicates = 200

[axes.task_id]
type = "categorical"
values = ["search", "checkout"]

[declare]
failures = ["timeout", "violated"]
"""
ROLLOUTS = 400


def cost_table(usd: str, basis: str | None = None) -> str:
    return f"\n[cost]\nusd_per_rollout = {usd}\n" + ("" if basis is None else f"basis = {json.dumps(basis)}\n")


@pytest.fixture(autouse=True)
def _empty_home_and_no_store_variables(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)


def folder_with(base: Path, spec: str, name: str = "prove.toml") -> Path:
    repo = base / "repo"
    repo.mkdir(parents=True)
    (repo / name).write_text(spec, encoding="utf-8")
    return repo


def sweep(repo: Path, *argv: str) -> pf11.Result:
    """``poisson-prove sweep ARGV`` in this process, in ``repo``, its store inside it. Only for the
    packaged mock, which is none of the person's code."""
    return pf11.run(repo, "--store", str(repo / "runs"), "sweep", *argv)


def cost_line(out: str) -> str:
    (line,) = [line.strip()[len("Cost: "):] for line in out.splitlines() if line.strip().startswith("Cost: ")]
    return line


def headline_cost(first: str) -> str:
    """What the plan's verdict line says of the cost: what follows where the sweep runs."""
    found = re.search(r" replicates on [^,]+, (.*)$", first)
    assert found and first.startswith("plan  "), first
    return found.group(1)


def approx(text: str, dollars: float) -> bool:
    """``text`` gives ``dollars`` as the look spells an estimate: ``~$2.43``."""
    return f"~{_look.fmt_dollars(dollars)}" in text


def zero_dollars(text: str) -> bool:
    """``text`` holds a bare ``$0``: not ``$0.0016``."""
    return re.search(r"\$0(?![\d.])", text) is not None


def document(out: str) -> dict[str, Any]:
    doc = json.loads(out, parse_constant=lambda word: pytest.fail(f"{word} in a strict JSON document"))
    assert isinstance(doc, dict) and doc["schema"] == "poisson-prove.sweep/1", out[:200]
    return doc


COST_KEYS = {"compute_usd", "agent_usd_per_rollout", "agent_usd", "agent_basis", "total_usd", "cap_usd"}


def is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


# ---------- C1 no "$0 (local)" ----------


@pytest.mark.parametrize("form", ["text", "--json"])
def test_c1_a_plan_on_this_machine_with_no_cost_table_says_not_priced_and_gives_no_dollar_figure(form: str, tmp_path: Path) -> None:
    repo = folder_with(tmp_path, SPEC)
    r = sweep(repo, "--dry-run", *(() if form == "text" else ("--json",)))
    assert r.code == 0, r
    assert "(local)" not in r.out, r.out
    if form == "text":
        phrases = [headline_cost(r.out.splitlines()[0]), cost_line(r.out)]
        full = [cost_line(r.out)]
    else:
        doc = document(r.out)
        phrases = [headline_cost("plan  " + doc["sentence"]), doc["plan"]["cost"], *(line for line in doc["plan"]["lines"] if line.startswith("Cost: "))]
        full = phrases[1:]
        assert len(full) == 2, doc["plan"]["lines"]
    for phrase in phrases:
        assert "not priced" in phrase and "$" not in phrase, phrase
    for phrase in full:
        assert "[cost]" in phrase, phrase


# ---------- C2 [cost] is read strictly ----------

LONG = "x" * 201
#: The table's text, and the key the refusal names.
C2_REFUSED: dict[str, tuple[str, str]] = {
    "a key the table does not have": ("[cost]\nusd_per_rollout = 0.01\nusd_per_run = 0.01\n", "usd_per_run"),
    "a cap key (M6-12)": ("[cost]\nusd_per_rollout = 0.01\nmax_cost = 5\n", "max_cost"),
    "no usd_per_rollout": ('[cost]\nbasis = "measured"\n', "usd_per_rollout"),
    "a negative figure": ("[cost]\nusd_per_rollout = -0.01\n", "usd_per_rollout"),
    "true": ("[cost]\nusd_per_rollout = true\n", "usd_per_rollout"),
    "a figure in quotes": ('[cost]\nusd_per_rollout = "0.01"\n', "usd_per_rollout"),
    "inf": ("[cost]\nusd_per_rollout = inf\n", "usd_per_rollout"),
    "nan": ("[cost]\nusd_per_rollout = nan\n", "usd_per_rollout"),
    "a price per axis value (M6-10)": ("[cost.usd_per_rollout]\nsmall = 0.001\nlarge = 0.02\n", "usd_per_rollout"),
    "an empty basis": ('[cost]\nusd_per_rollout = 0.01\nbasis = ""\n', "basis"),
    "a basis of 201 characters": (f'[cost]\nusd_per_rollout = 0.01\nbasis = "{LONG}"\n', "basis"),
    "a basis of two lines": ('[cost]\nusd_per_rollout = 0.01\nbasis = "measured\\non Tuesday"\n', "basis"),
    "a basis that is not text": ("[cost]\nusd_per_rollout = 0.01\nbasis = 3\n", "basis"),
    "cost is not a table": ("cost = 0.01\n", "cost"),
}


@pytest.mark.parametrize("case", list(C2_REFUSED))
def test_c2_a_cost_table_outside_its_two_keys_is_refused_before_anything_runs_naming_the_key(case: str, tmp_path: Path) -> None:
    table, key = C2_REFUSED[case]
    spec = SPEC.replace("\n[axes.task_id]", f"\n{table}\n[axes.task_id]") if case == "cost is not a table" else SPEC + "\n" + table
    repo = folder_with(tmp_path, spec)
    r = sweep(repo, "--yes")
    assert r.code == 1, r
    assert r.out == "", r.out
    (error,) = [line for line in r.err.splitlines() if line.startswith("error: ")]
    assert re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", error), (key, error)
    assert "Traceback" not in r.err, r.err
    assert not (repo / "runs").exists(), "a refused spec left a store folder"


C2_READ = {
    "0": ("0", None), "0.0": ("0.0", None), "a whole number": ("2", None), "a small figure": ("0.0016", None),
    "a basis of 200 characters": ("0.01", "y" * 200), "a basis of one character": ("0.01", "m"),
}


@pytest.mark.parametrize("case", list(C2_READ))
def test_c2_a_figure_at_or_above_0_and_a_one_line_basis_are_read(case: str, tmp_path: Path) -> None:
    usd, basis = C2_READ[case]
    repo = folder_with(tmp_path, SPEC + cost_table(usd, basis))
    r = sweep(repo, "--dry-run", "--json")
    assert r.code == 0, r
    cost = document(r.out)["cost"]
    assert cost["agent_usd_per_rollout"] == float(usd) and cost["agent_basis"] == basis, cost


# ---------- C3 the declared estimate ----------

BASIS = "costliest conversation measured, 2026-11-21"
#: The rate as written, the basis, what is typed, the spec's name, and the rollouts the command will run.
C3_CASES: dict[str, tuple[str, str | None, tuple[str, ...], str, int]] = {
    "the spec as written": ("0.0016", None, (), "prove.toml", ROLLOUTS),
    "three significant digits, given back as written": ("0.0274", None, (), "prove.toml", ROLLOUTS),
    "a basis": ("0.0016", BASIS, (), "prove.toml", ROLLOUTS),
    "--replicates typed": ("0.0016", None, ("--replicates", "250"), "prove.toml", 500),
    "--max-rollouts typed": ("0.0016", None, ("--max-rollouts", "120"), "prove.toml", 120),
    "a spec of another name": ("0.0016", None, (), "airline.toml", ROLLOUTS),
    "a figure above a dollar": ("2", None, (), "prove.toml", ROLLOUTS),
}


@pytest.mark.parametrize("case", list(C3_CASES))
def test_c3_the_plan_multiplies_the_declared_figure_by_the_rollouts_this_command_will_run(case: str, tmp_path: Path) -> None:
    written, basis, typed, name, rollouts = C3_CASES[case]
    repo = folder_with(tmp_path, SPEC + cost_table(written, basis), name)
    argv = (*(() if name == "prove.toml" else (name,)), "--dry-run", *typed)
    r = sweep(repo, *argv)
    assert r.code == 0, r
    product = rollouts * float(written)
    line, first = cost_line(r.out), r.out.splitlines()[0]
    # The product, the count, the rate as the spec writes it, whose figure it is, and the basis.
    assert approx(line, product) and approx(headline_cost(first), product), (line, first)
    assert re.search(rf"(?<![\d,]){rollouts:,} rollouts\b", line), line
    assert re.search(rf"\${re.escape(written)}(?![\d.])", line), line
    assert f"declared in {name}" in line, line
    assert (basis in line) if basis is not None else (BASIS not in line), line
    assert "not priced" not in line and "(local)" not in r.out, line
    doc = document(sweep(repo, *argv, "--json").out)
    assert doc["cost"]["agent_usd"] == pytest.approx(product) and doc["cost"]["total_usd"] == pytest.approx(product), doc["cost"]
    assert approx(doc["plan"]["cost"], product) and approx(doc["sentence"], product), doc


def test_c3_on_resume_the_estimate_counts_the_rollouts_left_and_a_paired_sweep_is_priced_as_the_first(tmp_path: Path) -> None:
    repo = folder_with(tmp_path, SPEC + cost_table("0.0016"))
    first = cost_line(sweep(repo, "--dry-run").out)
    part = sweep(repo, "--yes", "--max-rollouts", "100")
    assert part.code == 3, part
    left = sweep(repo, "--resume", "--dry-run")
    assert left.code == 0, left
    line = cost_line(left.out)
    assert re.search(r"(?<![\d,])300 rollouts\b", line) and approx(line, 300 * 0.0016), line
    done = sweep(repo, "--resume", "--yes")
    assert done.code == 0, done
    paired = sweep(repo, "--pair-with", "latest", "--dry-run")
    assert paired.code == 0, paired
    assert cost_line(paired.out) == first, (cost_line(paired.out), first)


# ---------- C4 $0 only by declaration ----------


def test_c4_a_plan_reads_dollar_zero_exactly_when_the_spec_declares_that_a_rollout_costs_nothing(tmp_path: Path) -> None:
    free = folder_with(tmp_path / "free", SPEC + cost_table("0"))
    r = sweep(free, "--dry-run")
    assert r.code == 0, r
    first, line = r.out.splitlines()[0], cost_line(r.out)
    assert headline_cost(first) == "$0", first
    assert line.startswith("$0") and "declares" in line and "prove.toml" in line and "not priced" not in line, line
    cost = document(sweep(free, "--dry-run", "--json").out)["cost"]
    assert (cost["agent_usd_per_rollout"], cost["agent_usd"], cost["total_usd"]) == (0, 0, 0), cost
    # A figure above nothing, however small, does not read $0.
    small = folder_with(tmp_path / "small", SPEC + cost_table("0.000001"))
    r = sweep(small, "--dry-run")
    assert r.code == 0, r
    assert not zero_dollars(headline_cost(r.out.splitlines()[0])) and not zero_dollars(cost_line(r.out)), r.out


# ---------- C5 Modal and the cloud: compute untouched, the agent's part appended ----------

MODAL_IMAGE = '\n[modal.image]\npython = "3.11"\n'
MODAL_COMPUTE = re.compile(r"^(~\$[\d,.]+ \(best-effort, [^()]*compute, not model tokens\)|unknown \(no estimate; [^()]*compute, not model tokens\))")


def modal_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spec: str, *argv: str) -> pf11.Result:
    """A plan on Modal with nothing of Modal's to call: a package of that name that holds nothing."""
    make_findable(monkeypatch, tmp_path, "modal", "99.0")
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    (repo / "prove.toml").write_text(spec, encoding="utf-8")
    return sweep(repo, "--backend", "modal", *argv)


@pytest.mark.parametrize("estimate", ["an estimate", "no estimate"])
def test_c5_on_modal_the_compute_part_is_as_it_was_and_the_agents_part_follows_it(estimate: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    typed = ("--est-seconds", "30") if estimate == "an estimate" else ()
    bare = modal_plan(tmp_path / "bare", monkeypatch, SPEC + MODAL_IMAGE, "--dry-run", *typed)
    assert bare.code == 0, bare
    plain = cost_line(bare.out)
    found = MODAL_COMPUTE.match(plain)
    assert found, plain
    compute = found.group(1)
    more = plain[len(compute):]
    assert "not priced" in more and "[cost]" in more and "$" not in more and "compute only" not in more, plain

    priced = modal_plan(tmp_path / "priced", monkeypatch, SPEC + cost_table("0.0016", BASIS) + MODAL_IMAGE, "--dry-run", *typed, "--json")
    assert priced.code == 0, priced
    doc = document(priced.out)
    (line,) = [line[len("Cost: "):] for line in doc["plan"]["lines"] if line.startswith("Cost: ")]
    assert line.startswith(compute), (line, compute)
    more = line[len(compute):]
    agent = ROLLOUTS * 0.0016
    assert approx(more, agent) and "400 rollouts" in more and "$0.0016" in more and "declared in prove.toml" in more and BASIS in more, line
    cost = doc["cost"]
    assert cost["agent_usd"] == pytest.approx(agent), cost
    if estimate == "an estimate":
        assert is_number(cost["compute_usd"]) and cost["compute_usd"] > 0, cost
        assert cost["total_usd"] == pytest.approx(cost["compute_usd"] + agent), cost
        assert more.rstrip().endswith(f"= ~{_look.fmt_dollars(cost['total_usd'])}"), line
    else:
        # No compute figure: the two parts side by side, and no sum.
        assert cost["compute_usd"] is None and cost["total_usd"] is None, cost
        assert " = " not in more, line


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    with world(tmp_path, monkeypatch, pool) as made:
        yield made


def test_c5_on_the_cloud_the_compute_part_is_as_it_was_and_the_agents_part_follows_it(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    bare = w.sweep("--dry-run")
    assert bare.code == 0, bare
    plain = cost_line(bare.out)
    compute = plain[: plain.index("cap $5.00") + len("cap $5.00")]
    assert re.match(r"^~\$[\d.]+ this run \(.*\) · ledger ledger\.jsonl \$0 so far · stop \$5\.00 · cap \$5\.00$", compute), compute

    w.write_spec(table=cloud_table(), extra=cost_table("0.25", BASIS))
    priced = w.sweep("--dry-run", "--json")
    assert priced.code == 0, priced
    doc = json.loads(priced.out)
    (line,) = [line[len("Cost: "):] for line in doc["plan"]["lines"] if line.startswith("Cost: ")]
    assert line.startswith(compute), (line, compute)
    more = line[len(compute):]
    cost = doc["cost"]
    assert cost["compute_usd"] == pytest.approx(doc["plan"]["cloud"]["estimate"]), cost
    assert cost["agent_usd"] == pytest.approx(4 * 0.25) and cost["total_usd"] == pytest.approx(cost["compute_usd"] + 1.0), cost
    assert approx(more, 1.0) and "4 rollouts" in more and "$0.25" in more and "declared in prove.toml" in more and BASIS in more, line
    assert more.rstrip().endswith(f"= ~{_look.fmt_dollars(cost['total_usd'])}"), line
    assert "compute only" not in line and "not priced" not in line, line


# ---------- C6 --max-cost ----------

#: A rollout that counts its calls, as M4's does, in a file outside the folder.
COUNTED = m4.WRAPPER
COUNTED_SPEC = m4.SPEC


def counted(base: Path, table: str) -> Path:
    return m4.counted(base, spec=COUNTED_SPEC + table)


def test_c6a_on_this_machine_an_estimate_over_the_cap_is_refused_and_its_next_passes_when_followed(tmp_path: Path) -> None:
    """C6 (a), reading f. 800 rollouts at $0.02743 are $21.944, so the smallest cap that admits
    them is $21.95. The spec has another name and is typed, so the ``next:`` must carry it."""
    repo = counted(tmp_path, cost_table("0.02743"))
    (repo / "prove.toml").rename(repo / "bot.toml")
    typed = ("bot.toml", "--yes", "--max-cost", "5")
    child = pf11.run_child(repo, tmp_path / "over", "sweep", *typed, extra={"M4_CALLS": str(tmp_path / "calls.jsonl")})
    assert child.code == 1, child.result
    (error,) = m4.error_lines(child.err)
    for fact in ("~$21.94", "800 rollouts", "$0.02743", "declared in bot.toml", "--max-cost", "$5.00"):
        assert fact in error, (fact, error)
    assert m4.verdicts(child.out) in ([], ["plan"]) and "[y/N]" not in child.err, (child.out, child.err)
    assert m4.calls(tmp_path) == [], "a sweep refused for its cap called the rollout"
    assert not (repo / "prove-runs").exists() and not (repo / ".poisson").exists(), "a sweep refused for its cap left a store"
    commands = [n for n in child.result.nexts if n.startswith(f"{COMMAND} ")]
    others = [n for n in child.result.nexts if not n.startswith(f"{COMMAND} ")]
    assert len(commands) == 1 and len(others) == 1 and "fewer conditions" in others[0], child.result.nexts
    words = shlex.split(commands[0])
    assert sorted(words) == sorted([COMMAND, "sweep", "bot.toml", "--yes", "--max-cost", "21.95"]), commands[0]
    # Followed, as the check: it passes, and the line carries the cap.
    followed = pf11.run_child(repo, tmp_path / "followed", *[w for w in words[1:] if w != "--yes"], "--dry-run")
    assert followed.code == 0, followed.result
    assert "cap $21.95" in cost_line(followed.out), followed.out
    # A cap of the estimate cut to the cent is still under it.
    under = pf11.run_child(repo, tmp_path / "under", "sweep", "bot.toml", "--dry-run", "--max-cost", "21.94")
    assert under.code == 1 and "--max-cost 21.95" in " ".join(under.result.nexts), under.result


def test_c6b_on_this_machine_an_estimate_at_the_cap_passes_and_the_line_carries_the_cap(tmp_path: Path) -> None:
    """C6 (b): 400 rollouts at $0.0125 are $5.00, which a cap of $5 admits."""
    repo = folder_with(tmp_path, SPEC + cost_table("0.0125"))
    r = sweep(repo, "--dry-run", "--max-cost", "5")
    assert r.code == 0, r
    line = cost_line(r.out)
    assert approx(line, 5.0) and "cap $5.00" in line and "compute only" not in line, line
    assert document(sweep(repo, "--dry-run", "--max-cost", "5", "--json").out)["cost"]["cap_usd"] == 5.0
    # With no cap typed the line names none.
    assert "cap" not in cost_line(sweep(repo, "--dry-run").out)
    assert document(sweep(repo, "--dry-run", "--json").out)["cost"]["cap_usd"] is None


def test_c6c_on_this_machine_with_no_cost_table_the_cap_is_refused_naming_cost(tmp_path: Path) -> None:
    repo = folder_with(tmp_path, SPEC)
    r = sweep(repo, "--yes", "--max-cost", "5")
    assert r.code == 1, r
    (error,) = [line for line in r.err.splitlines() if line.startswith("error: ")]
    assert "--max-cost" in error and "[cost]" in error and "not priced" in error, error
    assert "modal" not in error.lower(), error
    assert not (repo / "runs").exists()


def test_c6d_on_modal_the_cap_holds_the_compute_estimate_plus_the_declared_spend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C6 (d): the declared calls are $0.64; the cap is set from the plan's own compute figure."""
    spec = SPEC + cost_table("0.0016") + MODAL_IMAGE
    doc = document(modal_plan(tmp_path, monkeypatch, spec, "--dry-run", "--est-seconds", "30", "--json").out)
    compute, total = doc["cost"]["compute_usd"], doc["cost"]["total_usd"]
    assert total == pytest.approx(compute + 0.64), doc["cost"]
    # A cap the compute alone would pass, and the two together do not.
    between = f"{compute + 0.32:.2f}"
    over = modal_plan(tmp_path, monkeypatch, spec, "--yes", "--est-seconds", "30", "--max-cost", between)
    assert over.code == 1, over
    (error,) = [line for line in over.err.splitlines() if line.startswith("error: ")]
    for fact in (f"~{_look.fmt_dollars(compute)}", "~$0.64", "declared in prove.toml", _look.fmt_dollars(float(between))):
        assert fact in error, (fact, error)
    assert not (tmp_path / "repo" / "runs").exists(), "a sweep refused for its cap opened a store"
    # A cap at the sum admits it, and the line names the cap with no "compute only".
    admits = f"{math.ceil(total * 100) / 100:.2f}"
    passed = modal_plan(tmp_path, monkeypatch, spec, "--dry-run", "--est-seconds", "30", "--max-cost", admits)
    assert passed.code == 0, passed
    line = cost_line(passed.out)
    assert f"cap ${admits}" in line and "compute only" not in line, line
    assert document(modal_plan(tmp_path, monkeypatch, spec, "--dry-run", "--est-seconds", "30", "--max-cost", admits, "--json").out)["cost"]["cap_usd"] == float(admits)


def test_c6d_on_the_cloud_the_cap_holds_compute_the_declared_spend_and_the_ledger_and_refuses_before_anything_starts(w: CloudWorld) -> None:
    """C6 (d): compute here is about two cents, the declared calls $1.00, and the ledger holds
    $2.00 from an earlier run."""
    ledger = w.root / "ledger.jsonl"
    ledger.write_text(json.dumps({"event": "open", "run_id": "earlier", "stop_cost": 5.0}) + "\n"
                      + json.dumps({"event": "close", "run_id": "earlier", "charge": 2.0}) + "\n", encoding="utf-8")
    earlier = ledger.read_text(encoding="utf-8")
    # Compute and the ledger pass a $2.50 cap; the declared dollar puts it over.
    w.write_spec(table=cloud_table(stop_cost=0.4, max_cost=2.5))
    assert w.sweep("--dry-run").code == 0
    w.write_spec(table=cloud_table(stop_cost=0.4, max_cost=2.5), extra=cost_table("0.25"))
    over = w.sweep()
    assert over.code == 1, over
    (error,) = over.errors
    for fact in ("~$1.00", "4 rollouts", "$0.25", "declared in prove.toml", "$2.00", "$2.50"):
        assert fact in error, (fact, error)
    assert re.search(r"\$0\.0\d+", error), error  # the compute estimate, the third part
    assert w.management() == [] and w.heads() == [] and w.jobs() == [], "a sweep refused for its cap reached the cluster"
    assert ledger.read_text(encoding="utf-8") == earlier, "a refused sweep wrote a ledger line"
    assert w.runs() == []


def test_c6d_on_the_cloud_a_sweep_under_the_cap_runs_and_the_ledger_and_the_stop_stay_compute_only(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table(stop_cost=3.0, max_cost=4.0), extra=cost_table("0.25"))
    plan = json.loads(w.sweep("--dry-run", "--json").out)
    assert plan["cost"]["cap_usd"] == 4.0 and plan["cost"]["total_usd"] == pytest.approx(plan["cost"]["compute_usd"] + 1.0), plan["cost"]
    done = w.sweep()
    assert done.code == 0, done
    (opened,) = [entry for entry in w.ledger() if entry["event"] == "open"]
    # The ledger's own estimate is compute alone, and the stop and the cap are what the spec set.
    assert opened["estimate"] == pytest.approx(plan["cost"]["compute_usd"]), opened
    assert (opened["stop_cost"], opened["max_cost"]) == (3.0, 4.0), opened
    assert "usd_per_rollout" not in json.dumps(w.ledger()), w.ledger()


def test_c6e_on_modal_with_no_cost_table_the_cap_holds_compute_as_before_and_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = SPEC + MODAL_IMAGE
    compute = document(modal_plan(tmp_path, monkeypatch, spec, "--dry-run", "--est-seconds", "30", "--json").out)["cost"]["compute_usd"]
    admits = f"{math.ceil(compute * 100) / 100 + 1:.2f}"
    passed = modal_plan(tmp_path, monkeypatch, spec, "--dry-run", "--est-seconds", "30", "--max-cost", admits)
    assert passed.code == 0, passed
    line = cost_line(passed.out)
    assert re.search(rf"cap \${re.escape(admits)} \(compute only\)", line) and "not priced" in line, line
    # With no cap, nothing is said of one.
    assert "compute only" not in cost_line(modal_plan(tmp_path, monkeypatch, spec, "--dry-run", "--est-seconds", "30").out)
    # Over the cap it is refused as it was, and the refusal says nothing of the agent's calls.
    over = modal_plan(tmp_path, monkeypatch, spec, "--yes", "--est-seconds", "30", "--max-cost", "0.01")
    assert over.code == 1, over
    (error,) = [line for line in over.err.splitlines() if line.startswith("error: ")]
    assert "$0.01" in error and "your agent" not in error, error


# ---------- C7 the trial's count ----------

TRACED = """\
import json, os

from poisson_prove import Episode, record
from poisson_prove.trace import collect


def rollout(cfg, seed):
    with collect() as collected:
        {spans}
    meta = {{"case_id": cfg["ticket"]}}
    {meta}
    return Episode(outcome="resolved", t=7, horizon=20, meta=meta)
"""
SEVEN_CALLS = """for at in range(7):
            with record("llm", "ask") as span:
                if at < 5:
                    span.tokens = {"input": 100 + at, "output": 10}
        with record("tool", "lookup"):
            pass"""
WITH_TRACE = 'meta["trace"] = collected.trace.to_dict()'


def traced(base: Path, spans: str = SEVEN_CALLS, meta: str = WITH_TRACE, table: str = "") -> Path:
    repo = base / "repo"
    repo.mkdir(parents=True)
    (repo / "prove_rollout.py").write_text(TRACED.format(spans=spans, meta=meta), encoding="utf-8")
    (repo / "prove.toml").write_text(COUNTED_SPEC + table, encoding="utf-8")
    return repo


def tried(repo: Path, base: Path, *argv: str) -> pf11.Child:
    return pf11.run_child(repo, base, "sweep", "--try", "--yes", *argv)


def labels(out: str) -> list[str]:
    """The labels of the detail lines after the ``ok`` line, in order."""
    lines = out.splitlines()
    at = next(i for i, line in enumerate(lines) if line.startswith("ok  "))
    return [m.group(1) for m in (re.match(r"^  ([a-z][a-z_' ]*?) {2,}\S", line) for line in lines[at + 1:]) if m]


COUNT_LABELS = ("model calls", "tokens", "at a sweep's size")


def test_c7_the_llm_spans_of_the_trace_the_call_returned_are_counted_with_their_tokens_and_at_the_sweeps_size(tmp_path: Path) -> None:
    """Seven ``llm`` spans, five of them with tokens (510 in, 50 out), and one tool span. The spec
    is 4 conditions by 200 replicates: 800 rollouts, 5,600 model calls."""
    repo = traced(tmp_path)
    before = pf11.snapshot(repo)
    child = tried(repo, tmp_path)
    assert child.code == 0, child.result
    (calls,) = pf11.detail(child.out, "model calls")
    assert re.match(r"^7\b", calls) and "llm" in calls, calls
    (tokens,) = pf11.detail(child.out, "tokens")
    assert re.search(r"\b510 in\b", tokens) and re.search(r"\b50 out\b", tokens) and re.search(r"\b5 of 7\b", tokens), tokens
    (size,) = pf11.detail(child.out, "at a sweep's size")
    assert re.search(r"(?<![\d,])800 rollouts\b", size) and re.search(r"(?<![\d,])5,600 model calls\b", size), size
    found = labels(child.out)
    at = found.index("t")
    assert found[at + 1:at + 4] == list(COUNT_LABELS), found
    # K2 holds with a trace in hand: nothing is written to remember the count.
    assert pf11.snapshot(repo) == before and m4.files_under(child.home) == [], "the trial left a file"
    trial = document(tried(repo, tmp_path / "json", "--json").out)["try"]
    assert trial["model_calls"] == 7 and trial["tokens"] == {"input": 510, "output": 50, "calls_with_tokens": 5}, trial


#: The spans the rollout records, what it puts in ``meta``, and what the ``model calls`` line says.
C7_UNCOUNTED: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "no trace": ("pass", "pass", ("not counted", "no trace")),
    "a trace Prove cannot read": ("pass", 'meta["trace"] = {"spans": "seven"}', ("not counted",)),
    "a trace that is text": ("pass", 'meta["trace"] = "seven model calls"', ("not counted",)),
}


@pytest.mark.parametrize("case", list(C7_UNCOUNTED))
def test_c7_with_no_trace_it_can_read_the_trial_says_not_counted_and_is_still_a_good_call(case: str, tmp_path: Path) -> None:
    spans, meta, facts = C7_UNCOUNTED[case]
    child = tried(traced(tmp_path, spans, meta), tmp_path)
    assert child.code == 0 and m4.verdicts(child.out) == ["try", "ok"], child.result
    (calls,) = pf11.detail(child.out, "model calls")
    for fact in facts:
        assert fact in calls, (fact, calls)
    assert pf11.detail(child.out, "tokens") == [] and pf11.detail(child.out, "at a sweep's size") == [], child.out
    trial = document(tried(traced(tmp_path / "json", spans, meta), tmp_path / "json", "--json").out)["try"]
    assert trial["model_calls"] is None and trial["tokens"] is None, trial


def test_c7_a_trace_with_no_llm_span_says_none_and_llm_spans_with_no_tokens_get_no_tokens_line(tmp_path: Path) -> None:
    none = tried(traced(tmp_path / "none", 'with record("tool", "lookup"):\n            pass'), tmp_path / "none")
    assert none.code == 0, none.result
    (calls,) = pf11.detail(none.out, "model calls")
    assert re.match(r"^none\b", calls) and "not counted" not in calls, calls
    assert pf11.detail(none.out, "tokens") == [], none.out
    bare = 'for at in range(3):\n            with record("llm", "ask"):\n                pass'
    untold = tried(traced(tmp_path / "untold", bare), tmp_path / "untold")
    assert untold.code == 0, untold.result
    (calls,) = pf11.detail(untold.out, "model calls")
    assert re.match(r"^3\b", calls), calls
    assert pf11.detail(untold.out, "tokens") == [] and len(pf11.detail(untold.out, "at a sweep's size")) == 1, untold.out
    trial = document(tried(traced(tmp_path / "json", bare), tmp_path / "json", "--json").out)["try"]
    assert trial["model_calls"] == 3 and trial["tokens"] is None, trial


def test_c7_the_trial_does_not_apply_the_specs_capture_table(tmp_path: Path) -> None:
    """M6-7 (no), M4B-3: a spec with ``[capture]`` is tried as it is, so a rollout that returns no
    trace is not counted."""
    repo = traced(tmp_path, "pass", "pass", "\n[capture]\ninstrument = []\nmax_observation_bytes = 4096\n")
    child = tried(repo, tmp_path)
    assert child.code == 0, child.result
    (calls,) = pf11.detail(child.out, "model calls")
    assert "not counted" in calls and "no trace" in calls, calls


# ---------- C8 no dollars from tokens ----------


def test_c8_with_tokens_in_the_trace_and_no_cost_table_no_line_gives_dollars(tmp_path: Path) -> None:
    repo = traced(tmp_path)
    child = tried(repo, tmp_path)
    assert child.code == 0 and len(pf11.detail(child.out, "tokens")) == 1, child.result
    assert "$" not in child.out, child.out
    plan = pf11.run_child(repo, tmp_path / "plan", "sweep", "--dry-run")
    assert plan.code == 0 and "$" not in cost_line(plan.out) and "$" not in headline_cost(plan.out.splitlines()[0]), plan.out


def test_c8_the_package_holds_no_price_of_a_model_provider() -> None:
    """M6-5: no file of the package prices a token. The cloud's node prices are its only table."""
    per_token = re.compile(r"per[_ ](?:million|1[kK]|1_?000(?:_?000)?)[_ ]tokens|usd_per_(?:input_|output_)?token|\$/(?:M|1[kK]) ?tok", re.I)
    held = [str(p.relative_to(SRC)) for p in sorted(SRC.rglob("*.py")) if per_token.search(p.read_text(encoding="utf-8"))]
    assert held == [], held
    assert sorted(p.name for p in (SRC / "poisson_prove").glob("_prices*.py")) == ["_prices_cloud.py"]


# ---------- C9 the trial's cost line ----------

C9_CASES: dict[str, tuple[str, Callable[[str], bool]]] = {
    "nothing declared": ("", lambda line: "your agent's own calls" in line and "$" not in line and "declare" not in line),
    "a figure declared": (cost_table("0.0016"), lambda line: "$0.0016" in line and "declares" in line and "prove.toml" in line),
    "0 declared": (cost_table("0"), lambda line: line.startswith("nothing") and "declares" in line and "prove.toml" in line and not re.search(r"\$\d", line)),
}


@pytest.mark.parametrize("case", list(C9_CASES))
def test_c9_the_trials_cost_line_follows_what_the_spec_declares(case: str, tmp_path: Path) -> None:
    table, right = C9_CASES[case]
    child = tried(traced(tmp_path, table=table), tmp_path)
    assert child.code == 0, child.result
    (line,) = pf11.detail(child.out, "cost")
    assert right(line) and "stores nothing" in line, line


# ---------- C10 --json ----------

#: The keys 0.4.0's plan document has, at its top and under ``plan``.
PLAN_DOC = ["schema", "verdict", "sentence", "run_id", "run_name", "plan", "design_mde", "design_paired", "next"]
PLAN_KEYS = ["rollouts", "cells", "replicates", "backend", "target", "cost", "lines"]


@pytest.mark.parametrize("declared", ["nothing", "a figure"])
def test_c10_the_plans_document_gains_a_cost_object_and_keeps_every_key_it_had(declared: str, tmp_path: Path) -> None:
    repo = folder_with(tmp_path, SPEC + ("" if declared == "nothing" else cost_table("0.0016", BASIS)))
    doc = document(sweep(repo, "--dry-run", "--json").out)
    assert sorted(doc) == sorted([*PLAN_DOC, "cost"]), sorted(doc)
    assert list(doc)[:3] == PLAN_DOC[:3] and list(doc)[-1] == "next", list(doc)
    assert list(doc["plan"]) == PLAN_KEYS and isinstance(doc["plan"]["cost"], str), doc["plan"]
    assert (doc["plan"]["rollouts"], doc["plan"]["cells"], doc["plan"]["replicates"], doc["plan"]["backend"]) == (400, 2, 200, "local"), doc["plan"]
    cost = doc["cost"]
    assert set(cost) == COST_KEYS, sorted(cost)
    assert cost["compute_usd"] == 0 and cost["cap_usd"] is None, cost
    if declared == "nothing":
        assert (cost["agent_usd_per_rollout"], cost["agent_usd"], cost["agent_basis"], cost["total_usd"]) == (None, None, None, None), cost
    else:
        assert cost["agent_usd_per_rollout"] == 0.0016 and cost["agent_basis"] == BASIS, cost
        assert is_number(cost["agent_usd"]) and is_number(cost["total_usd"]), cost


def test_c10_the_trys_object_gains_model_calls_and_tokens_and_keeps_every_key_it_had(tmp_path: Path) -> None:
    trial = document(tried(traced(tmp_path), tmp_path, "--json").out)["try"]
    assert set(trial) == m4.TRY_KEYS | {"model_calls", "tokens"}, sorted(trial)
    assert type(trial["model_calls"]) is int and set(trial["tokens"]) == {"input", "output", "calls_with_tokens"}, trial
    assert all(type(value) is int for value in trial["tokens"].values()), trial["tokens"]
    # The trace the rollout returned is still in meta, whole.
    assert len(trial["meta"]["trace"]["spans"]) == 8, trial["meta"]


# ---------- C11 the packaged specs ----------

C11_CASES = {
    "the example": (("init", "--example"), "examples/quickstart.toml", "mock-agent"),
    "the demo": (("init", "--demo", "--with-setup"), "demo/prove.toml", "support-bot"),
}


@pytest.mark.parametrize("case", list(C11_CASES))
def test_c11_the_packaged_spec_declares_that_a_rollout_costs_nothing_and_its_plan_reads_dollar_zero(case: str, tmp_path: Path) -> None:
    argv, shipped, target_id = C11_CASES[case]
    packaged = (SRC / "poisson_prove" / shipped).read_bytes()
    assert tomllib.loads(packaged.decode("utf-8"))["cost"] == {"usd_per_rollout": 0}
    repo = tmp_path / "repo"
    repo.mkdir()
    assert pf11.run(repo, *argv).code == 0
    assert (repo / "prove.toml").read_bytes() == packaged
    plan = pf11.run_child(repo, tmp_path / "plan", "sweep", "--dry-run")
    assert plan.code == 0, plan.result
    first, line = plan.out.splitlines()[0], cost_line(plan.out)
    assert target_id in first and headline_cost(first) == "$0", first
    assert line.startswith("$0") and "declares" in line and "prove.toml" in line, line


# ---------- C12 nothing else moves ----------


def run_folder(repo: Path) -> Path:
    (found,) = [p.parent for p in (repo / "runs").rglob("manifest.json")]
    return found


def test_c12_a_sweep_of_a_spec_with_a_cost_table_stores_what_it_stored_and_pairs_with_one_without(tmp_path: Path) -> None:
    """The manifest holds nothing of the declared figure (M6-14, no) and the format is as it was;
    the done block has the lines it had; and a spec that gains ``[cost]`` is still the same
    sweep, so its runs pair with the runs made before the table was added."""
    told = "measured on a Tuesday afternoon"
    plain = folder_with(tmp_path / "plain", SPEC)
    priced = folder_with(tmp_path / "priced", SPEC + cost_table("0.0016", told))
    without, with_table = sweep(plain, "--yes", "--salt", "m6"), sweep(priced, "--yes", "--salt", "m6")
    assert without.code == 0 and with_table.code == 0, (without, with_table)

    def result_labels(out: str) -> list[str]:
        lines = out.splitlines()
        at = next(i for i, line in enumerate(lines) if line.startswith("done  "))
        return [re.match(r"^  (\S[^:]*?)(?:  |: )", line).group(1) for line in lines[at + 1:] if line.startswith("  ")]  # type: ignore[union-attr]

    assert result_labels(with_table.out) == result_labels(without.out), with_table.out
    theirs, mine = (json.loads((run_folder(repo) / "manifest.json").read_text(encoding="utf-8")) for repo in (plain, priced))
    text = json.dumps(mine)
    assert "usd_per_rollout" not in text and told not in text and "0.0016" not in text, text
    assert "(local)" not in "".join(p.read_text(encoding="utf-8") for p in run_folder(priced).glob("*.json*")), "a stored file still says $0 (local)"
    assert sorted(mine) == sorted(theirs) and sorted(mine["environment"]) == sorted(theirs["environment"]), sorted(mine)
    assert mine["schema_version"] == theirs["schema_version"], mine["schema_version"]
    # The same sweep: the spec without the table, then with it, on the same seeds.
    (plain / "prove.toml").write_text(SPEC + cost_table("0.0016"), encoding="utf-8")
    paired = sweep(plain, "--yes", "--pair-with", "latest")
    assert paired.code == 0 and "paired with" in paired.out, paired


def test_c12_pricing_a_plan_opens_no_network_and_writes_nothing(tmp_path: Path) -> None:
    repo = counted(tmp_path, cost_table("0.0016", BASIS))
    before = pf11.snapshot(repo)
    child = pf11.run_child(repo, tmp_path / "plan", "sweep", "--dry-run", "--max-cost", "5")
    assert child.code == 0, child.result
    assert child.attempts == [], child.attempts
    assert pf11.snapshot(repo) == before and m4.files_under(child.home) == []


# ---------- C13 the terminal app ----------

C13_CASES = {
    "nothing declared": ("", ("not priced", "[cost]")),
    "a figure declared": (cost_table("0.0274", BASIS), ("~$10.96", "400 rollouts", "$0.0274", "declared in prove.toml")),
}


@pytest.mark.parametrize("case", list(C13_CASES))
def test_c13_the_apps_plan_page_shows_the_cost_phrase_with_its_question_on_an_80_by_24_screen(case: str, tmp_path: Path) -> None:
    table, facts = C13_CASES[case]
    repo = folder_with(tmp_path, SPEC + table)

    async def scenario(s: Session) -> tuple[str, str]:
        await s.wait_title("home")
        await s.press("s")
        await s.wait_title("sweep")
        asked = await s.wait_text("[y/N]")
        on_screen = asked.text()
        await s.press("m")
        more = (await s.settle()).text()
        await s.press("n")
        await s.settle()
        await s.press("q")
        if s.app.is_running:
            await s.press("q")
        return on_screen, more

    rc, (on_screen, more) = drive(scenario, cwd=repo, size=(80, 24))
    assert rc == 0
    # The cost phrase and the question are on the one screen, before any key.
    first = " ".join(on_screen.split())
    assert "[y/N]" in first, on_screen
    for fact in facts:
        assert fact in first, (fact, on_screen)
    # Nowhere on the page is the old phrase, or the declared rate cut to the look's two digits.
    whole = first + " " + " ".join(more.split())
    assert "(local)" not in whole and not re.search(r"(?<![\d.])0\.027(?!\d)", whole), whole


# ---------- A1 to A5, A8: the skill's text ----------


def step_3(body: str) -> str:
    return pf11.steps_of(body)[2].text


def sentences(text: str) -> list[str]:
    return [" ".join(s.split()) for s in re.split(r"(?<=[.:;])\s+", text) if s.strip()]


def test_a1_step_3_writes_the_cases_axis_an_axis_for_what_the_person_asked_to_compare_and_no_other(tmp_path: Path) -> None:
    text = " ".join(step_3(m4.skill_body(tmp_path)).split())
    assert not re.search(r"two or three ax[ei]s", text, re.I) and not re.search(r"two to four values", text, re.I), text
    assert re.search(r"one axis whose values are the case ids", text), text
    assert re.search(r"axis for each thing the person asked to compare", text) and re.search(r"values they named", text), text
    assert re.search(r"\bno other ax[ei]s\b", text, re.I), text


def test_a2_the_skill_says_never_an_axis_over_the_model_the_provider_or_a_billed_setting_unless_asked(tmp_path: Path) -> None:
    body = m4.skill_body(tmp_path)
    held = sentences(step_3(body)) + sentences(pf11.section(body, "## Rules"))
    found = [s for s in held if re.search(r"\bnever\b", s, re.I) and re.search(r"\bax[ei]s\b", s)
             and all(re.search(rf"\b{word}\b", s) for word in ("model", "provider", "billed")) and re.search(r"\bunless\b.*\basked\b", s)]
    assert len(found) == 1, held


def not_added_item(body: str) -> str:
    """The item of "Hand over" for the axes the skill did not add: the one after the axes of
    ``prove.toml`` (reading l)."""
    items = m4.hand_over_items(body)
    (at,) = [i for i, item in enumerate(items) if re.match(r"Each axis\b", item)]
    return items[at + 1]


def test_a3_the_hand_over_lists_up_to_three_axes_it_did_not_add_each_with_its_values_its_factor_and_how_to_add_it(tmp_path: Path) -> None:
    body = m4.skill_body(tmp_path)
    item = " ".join(not_added_item(body).split())
    assert re.match(r"Axes I did not add\b", item, re.I), item
    assert re.search(r"\bup to three\b", item), item
    assert re.search(r"\bthe values\b", item) and re.search(r"\bfactor\b", item) and re.search(r"\bmultipl\w+ the rollouts\b", item), item
    # How to add one: ask again naming it, or add its table and run the check.
    assert re.search(r"\bask again\b", item) and "`[axes.NAME]`" in item and "`poisson-prove sweep --dry-run`" in item, item
    assert re.search(r'say "none"', item), item
    # It is one of seven items: the two that open the hand-over, the axes, this one, and the three after.
    assert len(m4.hand_over_items(body)) == 7


COST_PARTS = (
    r"plan's headline",
    r"rollouts of one sweep and of the loop\b.*?\btwo sweeps\b",
    r'model calls one rollout makes\b.*?"none: this agent calls no model"',
    r"`model calls` and `tokens` lines as printed",
    r"\"Prove's plan does not price your agent's own calls unless `prove\.toml` declares `\[cost\]`\"",
    r"how to declare it\b.*?`usd_per_rollout`",
)


def test_a4_the_confirm_lists_cost_item_has_its_six_parts_in_order_and_gives_no_dollar_figure_of_its_own(tmp_path: Path) -> None:
    hand_over = pf11.section(m4.skill_body(tmp_path), "## Hand over")
    tail = hand_over.split("What the person must confirm:", 1)[1]
    (item,) = [line for line in tail.splitlines() if line.startswith("- ") and "replicates" in line and "cost" in line]
    at = 0
    for part in COST_PARTS:
        found = re.compile(part).search(item, at)
        assert found, (part, item[at:])
        at = found.end()
    assert re.search(r"\bno dollar figure of your own\b", item), item
    assert not re.search(r"\$\d", item), item


def test_a5_the_skill_writes_cost_only_for_an_agent_that_calls_no_model_and_only_as_0(tmp_path: Path) -> None:
    body = m4.skill_body(tmp_path)
    text = " ".join(step_3(body).split())
    found = re.search(r"[^.]*calls no model[^.]*`\[cost\]`[^.]*`usd_per_rollout = 0`", text)
    assert found, text
    assert re.search(r"\bnever write another figure\b", text[found.end():]), text
    assert re.search(r"agent that calls a model\b[^.;]*\bno `\[cost\]` table", text), text
    # No other figure anywhere in the skill, and the files it writes are the two it wrote.
    assert set(re.findall(r"usd_per_rollout\s*=\s*(\S+?)[`.,;\s]", body)) <= {"0"}, body
    listed = [line.split("`")[1] for line in pf11.section(body, "## Files you write").splitlines() if line.startswith("- `")]
    assert listed == pf11.WRITES, listed


STEPS = ["Find the agent's entry point", "Write the rollout wrapper", "Write the sweep spec", "Declare the outcomes",
         "Run the check", "Call it once", "Hand over"]
QUESTION = '"Next I call your agent once, on one real case, at your agent\'s own cost (its model calls for one case). May I?"'


def test_a8_the_seven_steps_their_order_and_step_6s_question_are_as_they_were(tmp_path: Path) -> None:
    steps = pf11.steps_of(m4.skill_body(tmp_path))
    assert [s.title for s in steps] == STEPS, [s.title for s in steps]
    assert QUESTION in steps[5].text, steps[5].text


# ---------- A6 the scripted run ----------

AGENT = '''\
"""A support agent with a model setting and a temperature setting. (A stand-in: it calls nothing.)"""

import random

MODELS = ("small-1", "large-1")
MODEL = "small-1"
TEMPERATURE = 0.0
CASES = {"refund": 0.9, "password": 0.8, "shipping": 0.7}


def answer(case, *, model=MODEL, temperature=TEMPERATURE, seed=0):
    rng = random.Random(f"{case}|{model}|{temperature}|{seed}")
    return "resolved" if rng.random() < CASES[case] - 0.2 * temperature else "unresolved"
'''
AGENT_WRAPPER = '''\
from bot.agent import MODEL, TEMPERATURE, answer
from poisson_prove import Episode


def rollout(cfg, seed):
    outcome = answer(cfg["case"], model=cfg.get("model", MODEL), temperature=cfg.get("temperature", TEMPERATURE), seed=seed)
    return Episode(outcome=outcome, t=1, horizon=4, meta={"case_id": cfg["case"]})
'''
AGENT_HEAD = 'target = "prove_rollout:rollout"\ntarget_id = "support"\nt_unit = "model_calls"\nreplicates = 20\n'
AGENT_DECLARE = '\n[declare]\noutcomes = ["resolved", "unresolved"]\nfailures = ["unresolved"]\nsuccesses = ["resolved"]\n'


@dataclass(frozen=True)
class Shown:
    """What the code shows a coding agent, as the stand-in is told it."""

    case_axis: str
    cases: tuple[Any, ...]
    #: what else the code shows could vary, with the values each would take
    varies: dict[str, tuple[Any, ...]]
    calls_model: bool
    head: str
    declare: str
    wrapper: str


@dataclass
class SetUp:
    first: str
    spec: dict[str, Any]
    #: (name, values, factor) for each axis the hand-over lists as not added
    not_added: list[tuple[str, tuple[Any, ...], int]]
    #: the plan's headline, as the check printed it
    headline: str
    ran: list[tuple[str, pf11.Child]] = field(default_factory=list)


def toml_values(values: tuple[Any, ...]) -> str:
    return "[" + ", ".join(json.dumps(v) for v in values) + "]"


def set_up(repo: Path, base: Path, shown: Shown, prompt: str, asked: dict[str, tuple[Any, ...]] | None = None) -> SetUp:
    """A coding agent's stand-in, following the written skill in ``repo`` for a person who gave it
    ``prompt`` and says yes to the one call. ``asked`` is what the prompt asks to compare beyond
    the skill's own prompt, as a reader takes it from the person's words. What it writes into
    ``prove.toml`` and lists in the hand-over it decides from the skill's text (reading m)."""
    body = pf11.split_frontmatter((repo / pf11.FOUR[0]).read_text(encoding="utf-8"))[1]
    steps = pf11.steps_of(body)
    assert [s.number for s in steps] == [1, 2, 3, 4, 5, 6, 7], steps
    three = " ".join(steps[2].text.split())
    asked = dict(asked or {})
    assert all(re.search(rf"\b{name}\b", prompt[len(pf11.PROMPT):]) for name in asked), (prompt, asked)
    # Step 3: the cases, what was asked, and whatever else the skill tells it to add.
    axes: dict[str, tuple[Any, ...]] = {shown.case_axis: shown.cases, **asked}
    if not re.search(r"\bno other ax[ei]s\b", three, re.I):
        many = re.search(r"\b(two or three|two|three) ax[ei]s\b", three)
        for name in list(shown.varies)[: 3 if many and "three" in many.group(1) else 2]:
            axes.setdefault(name, shown.varies[name])
    spec = shown.head + "".join(
        f'\n[axes.{name}]\ntype = "{"continuous" if all(isinstance(v, float) for v in values) else "categorical"}"\nvalues = {toml_values(values)}\n'
        for name, values in axes.items())
    spec += shown.declare
    if not shown.calls_model and re.search(r"calls no model[^.]*`\[cost\]`[^.]*`usd_per_rollout = 0`", three):
        spec += "\n[cost]\nusd_per_rollout = 0\n"
    (repo / "prove_rollout.py").write_text(shown.wrapper, encoding="utf-8")
    (repo / "prove.toml").write_text(spec, encoding="utf-8")
    # Steps 5 and 6: the check until it passes, then the one call.
    (check,) = [c for s, c in pf11.commands(body, "bash") if s == "## The check"]
    (call,) = [line for f in pf11.fences("## Steps\n" + steps[5].text) if f.lang == "bash" for line in f.lines]
    ran: list[tuple[str, pf11.Child]] = []

    def run(command: str) -> pf11.Child:
        child = pf11.run_child(repo, base / f"run-{len(ran)}", *shlex.split(command)[1:])
        ran.append((command, child))
        return child

    last = run(check)
    while last.code != 0:
        assert len(ran) <= 3, [(c, child.err) for c, child in ran]
        offered = pf11.replicates_offered(last.result)
        (repo / "prove.toml").write_text(pf11.with_replicates((repo / "prove.toml").read_text(encoding="utf-8"), offered), encoding="utf-8")
        last = run(check)
    headline = last.out.splitlines()[0]
    called = run(call)
    if called.code == 0:
        (returned,) = re.findall(r'returned "([^"]+)"', called.out)
        first = f'ready: the check passed and one real call returned "{returned}"'
    else:
        first = f"not ready: {called.result.error}"
    # Step 7: the hand-over's item for the axes it did not add, when the skill has one.
    items = m4.hand_over_items(body)
    listed: list[tuple[str, tuple[Any, ...], int]] = []
    if any(re.match(r"Axes I did not add\b", item, re.I) for item in items):
        listed = [(name, values, len(values)) for name, values in shown.varies.items() if name not in axes][:3]
    return SetUp(first, tomllib.loads((repo / "prove.toml").read_text(encoding="utf-8")), listed, headline, ran)


def agent_repo(base: Path) -> tuple[Path, Shown]:
    repo = base / "repo"
    (repo / "bot").mkdir(parents=True)
    (repo / "bot" / "agent.py").write_text(AGENT, encoding="utf-8")
    assert pf11.run(repo, "init", "--agent").code == 0
    shown = Shown("case", ("refund", "password", "shipping"), {"model": ("small-1", "large-1"), "temperature": (0.0, 0.7)},
                  calls_model=True, head=AGENT_HEAD, declare=AGENT_DECLARE, wrapper=AGENT_WRAPPER)
    return repo, shown


def test_a6_on_an_agent_with_a_model_and_a_temperature_setting_the_stand_in_writes_the_cases_alone_and_lists_the_two(tmp_path: Path) -> None:
    repo, shown = agent_repo(tmp_path)
    before = pf11.snapshot(repo)
    done = set_up(repo, tmp_path / "runs", shown, pf11.PROMPT)
    assert list(done.spec["axes"]) == ["case"] and done.spec["axes"]["case"]["values"] == list(shown.cases), done.spec["axes"]
    assert [(name, factor) for name, _, factor in done.not_added] == [("model", 2), ("temperature", 2)], done.not_added
    # The agent calls a model, so the skill wrote no [cost], and the plan says so.
    assert "cost" not in done.spec, done.spec
    assert "not priced" in done.headline and "$" not in done.headline and re.search(r"\b3 cells\b", done.headline), done.headline
    assert done.first.startswith("ready: "), done.first
    assert pf11.added(before, pf11.snapshot(repo), repo) == sorted(pf11.WRITES)


def test_a6_asked_to_compare_temperature_the_stand_in_writes_the_cases_and_temperature_and_still_no_model_axis(tmp_path: Path) -> None:
    repo, shown = agent_repo(tmp_path)
    done = set_up(repo, tmp_path / "runs", shown, pf11.PROMPT + " Also compare temperature 0 and 0.7.", {"temperature": (0.0, 0.7)})
    assert list(done.spec["axes"]) == ["case", "temperature"] and done.spec["axes"]["temperature"]["values"] == [0.0, 0.7], done.spec["axes"]
    assert "model" not in done.spec["axes"], done.spec["axes"]
    assert [(name, factor) for name, _, factor in done.not_added] == [("model", 2)], done.not_added
    assert re.search(r"\b6 cells\b", done.headline) and done.first.startswith("ready: "), (done.headline, done.first)


def test_a6_on_the_demo_the_stand_in_writes_cost_reaches_ready_and_the_plan_reads_dollar_zero(tmp_path: Path) -> None:
    repo, wrapper, spec = m4.demo_repo(tmp_path)
    written = tomllib.loads(spec)
    declare = "\n[declare]\n" + "".join(f"{key} = {json.dumps(written['declare'][key])}\n" for key in ("outcomes", "failures", "successes"))
    head = "".join(f"{key} = {json.dumps(written[key])}\n" for key in ("target", "target_id", "t_unit", "replicates"))
    assert wrapper.count('temperature=cfg["temperature"]') == 1, wrapper
    shown = Shown("ticket", tuple(written["axes"]["ticket"]["values"]), {"temperature": tuple(written["axes"]["temperature"]["values"])},
                  calls_model=False, head=head, declare=declare,
                  wrapper=wrapper.replace('temperature=cfg["temperature"]', 'temperature=cfg.get("temperature", 0.0)'))
    done = set_up(repo, tmp_path / "runs", shown, pf11.PROMPT)
    assert re.fullmatch(r'ready: the check passed and one real call returned "(resolved|unresolved|timeout)"', done.first), done.first
    assert done.spec["cost"] == {"usd_per_rollout": 0} and list(done.spec["axes"]) == ["ticket"], done.spec
    assert headline_cost(done.headline) == "$0", done.headline
    assert not any(child.attempts for _, child in done.ran), [child.attempts for _, child in done.ran]


# ---------- A7 init --agent's one more line ----------


def test_a7_init_agent_prints_one_more_detail_line_on_how_to_ask_for_more_than_the_cases(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    r = pf11.run(repo, "init", "--agent")
    assert r.code == 0 and r.err == "", r
    out = r.out.splitlines()
    at = out.index(f"  prompt  {pf11.PROMPT}")
    assert out[at + 2].startswith("  next: ") and len(out) == at + 3, out[at:]
    found = re.match(r"^  [a-z][a-z ]*? {2,}(\S.*)$", out[at + 1])
    assert found, out[at + 1]
    more = found.group(1)
    assert "cases" in more and "prompt" in more and "your own words" in more and "compare" in more, more
    # The prompt itself is the one the files hold, and --json's is the same.
    assert (repo / pf11.FOUR[1]).read_text(encoding="utf-8") == pf11.PROMPT + "\n"
    again = tmp_path / "again"
    again.mkdir()
    assert json.loads(pf11.run(again, "init", "--agent", "--json").out)["prompt"] == pf11.PROMPT


# ---------- L1 the hand-over says what the comparison leaves out ----------


def test_l1_after_the_loop_the_hand_over_names_the_outcomes_diff_compares_and_leaves_out_with_a_block_for_each_left_out(tmp_path: Path) -> None:
    body = m4.skill_body(tmp_path)
    hand_over = pf11.section(body, "## Hand over")
    person = [command for section, command in pf11.commands(body, "text") if section == "## Hand over"]
    words = [shlex.split(command)[1:] for command in person]
    assert words[-2] == ["diff"] and words[-1][:2] == ["diff", "--event"] and len(words[-1]) == 3, person
    after = " ".join(hand_over[hand_over.index(person[-2]) + len(person[-2]):].split())
    until = after.index(person[-1])
    said = after[:until]
    assert "`[declare]`" in said and re.search(r"\bcompares\b", said) and re.search(r"\bleaves out\b", said), said
    assert re.search(r"\bfailure\b", said) and re.search(r"\bsuccess\b", said) and re.search(r"\bneither\b", said), said
    assert re.search(r"\bone block for each\b", said), said
    assert '"every declared outcome is compared"' in after[until:] and re.search(r"\bno such block\b", after[until:]), after[until:]
    # The loop is still the person's to run: said after the last block.
    assert re.search(r"\b(?:do not|never) run\b", hand_over[hand_over.rindex("```"):], re.I)


# ---------- L2 to L5: diff, report and check ----------

OUTCOMES = """\
import random

from poisson_prove import Episode


def rollout(cfg, seed):
    draw = random.Random(f"{{cfg['ticket']}}|{{seed}}").random()
    outcome = "resolved" if draw < {resolved} else "unresolved" if draw < 0.75 else "timeout" if draw < 0.85 else "blocked"
    return Episode(outcome=outcome, t=3, horizon=20, meta={{"case_id": cfg["ticket"]}})
"""
PAIR_SPEC = """\
target = "prove_rollout:rollout"
target_id = "tickets"
t_unit = "steps"
replicates = 60

[axes.ticket]
type = "categorical"
values = ["refund", "password"]
"""
DECLARED = {
    "two declared neither": '\n[declare]\noutcomes = ["resolved", "unresolved", "timeout", "escalated", "blocked"]\nfailures = ["unresolved", "timeout"]\nsuccesses = ["resolved"]\n',
    "every outcome a failure or a success": '\n[declare]\noutcomes = ["resolved", "unresolved", "timeout", "blocked"]\nfailures = ["unresolved", "timeout", "blocked"]\nsuccesses = ["resolved"]\n',
    "failures alone, no list of outcomes": '\n[declare]\nfailures = ["unresolved"]\n',
    "nothing declared": "",
}
TODAYS = "inferred: no event was given, so the event set is {events}, the failures and successes the runs declared"


@pytest.fixture(scope="module")
def pairs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """For each declaration, a folder holding two paired sweeps of a rollout whose endings are
    resolved, unresolved, timeout and blocked (escalated is declared and never returned)."""
    made: dict[str, Path] = {}
    for at, (name, declare) in enumerate(DECLARED.items()):
        base = tmp_path_factory.mktemp(f"pair-{at}")
        repo = base / "repo"
        repo.mkdir()
        (repo / "prove.toml").write_text(PAIR_SPEC + declare, encoding="utf-8")
        (repo / "prove_rollout.py").write_text(OUTCOMES.format(resolved="0.55"), encoding="utf-8")
        before = pf11.run_child(repo, base / "before", "sweep", "--yes", "--max-mde", "1", timeout=300)
        assert before.code == 0, before.result
        (repo / "prove_rollout.py").write_text(OUTCOMES.format(resolved="0.35"), encoding="utf-8")
        after = pf11.run_child(repo, base / "after", "sweep", "--yes", "--max-mde", "1", "--pair-with", "latest", timeout=300)
        assert after.code == 0, after.result
        made[name] = repo
    return made


def diffed(repo: Path, base: Path, *argv: str) -> pf11.Child:
    return pf11.run_child(repo, base, "diff", *argv)


def inferred_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("inferred: ")]


#: The declaration, the events the comparison infers, and the outcomes it leaves out.
L2_CASES = {
    "two declared neither": ("timeout, unresolved, resolved", ["blocked", "escalated"]),
    "failures alone, no list of outcomes": ("unresolved", ["blocked", "resolved", "timeout"]),
}


@pytest.mark.parametrize("case", list(L2_CASES))
def test_l2_with_no_event_named_the_inferred_line_and_left_out_name_the_outcomes_the_runs_declare_or_hold_that_are_not_compared(
    case: str, pairs: dict[str, Path], tmp_path: Path
) -> None:
    events, left = L2_CASES[case]
    child = diffed(pairs[case], tmp_path)
    assert child.code == 0, child.result
    (line,) = inferred_lines(child.out)
    todays = TODAYS.format(events=events)
    assert line.startswith(todays), line
    more = line[len(todays):]
    assert re.search(rf"\bleft out: {re.escape(', '.join(left))}\b", more) and "--event" in more, line
    # Those and no others: no outcome that is compared is named among them.
    assert not [name for name in events.split(", ") if re.search(rf"\b{name}\b", more)], line
    doc = json.loads(diffed(pairs[case], tmp_path / "json", "--json").out)
    assert doc["left_out"] == left and doc["inferred"] is True and doc["events"] == events.split(", "), (doc.get("left_out"), doc["events"])


def test_l2_when_every_outcome_is_compared_the_line_is_as_it_was_byte_for_byte(pairs: dict[str, Path], tmp_path: Path) -> None:
    repo = pairs["every outcome a failure or a success"]
    child = diffed(repo, tmp_path)
    assert child.code == 0, child.result
    assert inferred_lines(child.out) == [TODAYS.format(events="blocked, timeout, unresolved, resolved")], child.out
    assert json.loads(diffed(repo, tmp_path / "json", "--json").out).get("left_out") in (None, []), "nothing was left out"


def test_l2_with_an_event_named_or_with_no_kind_declared_nothing_is_said_to_be_left_out(pairs: dict[str, Path], tmp_path: Path) -> None:
    named = diffed(pairs["two declared neither"], tmp_path / "named", "--event", "timeout")
    assert named.code == 0 and inferred_lines(named.out) == [] and "left out" not in named.out, named.result
    assert json.loads(diffed(pairs["two declared neither"], tmp_path / "named-json", "--event", "timeout", "--json").out).get("left_out") in (None, [])
    # No failure and no success declared: the other form stands, naming the outcome it sets aside.
    other = diffed(pairs["nothing declared"], tmp_path / "other")
    assert other.code == 0, other.result
    (line,) = inferred_lines(other.out)
    assert "the most frequent outcome" in line and "left out" not in line, line
    assert json.loads(diffed(pairs["nothing declared"], tmp_path / "other-json", "--json").out).get("left_out") in (None, [])


def test_l2_report_prints_the_line_diff_prints_and_a_report_of_one_run_names_what_it_left_out(pairs: dict[str, Path], tmp_path: Path) -> None:
    repo = pairs["two declared neither"]
    (line,) = inferred_lines(diffed(repo, tmp_path / "diff").out)
    out = tmp_path / "report"
    two = pf11.run_child(repo, tmp_path / "two", "report", "--x", "ticket", "--out", str(out))
    assert two.code == 0, two.result
    assert line in (out / "report.md").read_text(encoding="utf-8").splitlines(), (out / "report.md").read_text(encoding="utf-8")[:600]
    assert "left out: blocked, escalated" in (out / "receipt.html").read_text(encoding="utf-8")
    one = pf11.run_child(repo, tmp_path / "one", "report", "latest", "--x", "ticket", "--out", str(tmp_path / "single"))
    assert one.code == 0, one.result
    (own,) = inferred_lines(one.out + (tmp_path / "single" / "report.md").read_text(encoding="utf-8"))[:1]
    assert re.search(r"\bleft out: blocked, escalated\b", own) and "--event" in own, own


def test_l3_naming_what_was_left_out_changes_nothing_else_of_the_comparison(pairs: dict[str, Path], tmp_path: Path) -> None:
    """Reading k: the comparison with no event named is, key for key, the one with its events
    named, but for the two keys that say the events were inferred."""
    repo = pairs["two declared neither"]
    inferred = diffed(repo, tmp_path / "inferred", "--json")
    named = diffed(repo, tmp_path / "named", "--json", "--event", "timeout", "--event", "unresolved", "--event", "resolved")
    assert (inferred.code, named.code) == (0, 0), (inferred.result, named.result)
    ours, theirs = json.loads(inferred.out), json.loads(named.out)
    for doc in (ours, theirs):
        doc.pop("inferred"), doc.pop("left_out", None), doc.pop("next", None)
    assert sorted(ours) == sorted(theirs)
    differ = [key for key in ours if ours[key] != theirs[key]]
    assert differ == [], differ
    assert set(ours["by_event"]) == {"timeout", "unresolved", "resolved"}, "an outcome left out was compared"


def test_l4_diff_event_on_an_outcome_the_line_named_compares_it_in_the_kindless_words(pairs: dict[str, Path], tmp_path: Path) -> None:
    repo = pairs["two declared neither"]
    child = diffed(repo, tmp_path, "--event", "blocked")
    assert child.code == 0, child.result
    first = child.out.splitlines()[0]
    assert re.match(r"^(higher|lower|mixed|no significant change|too small to tell)  ", first), first
    assert re.search(r"\bblocked: \d+ lower, \d+ higher\b", first) and not re.search(r"\b(safer|worse)\b", first), first
    doc = json.loads(diffed(repo, tmp_path / "json", "--event", "blocked", "--json").out)
    assert doc["events"] == ["blocked"] and doc["by_event"]["blocked"]["kind"] is None, doc["by_event"]["blocked"].get("kind")


def test_l5_check_says_nothing_of_outcomes_left_out(pairs: dict[str, Path], tmp_path: Path) -> None:
    repo = pairs["two declared neither"]
    text = pf11.run_child(repo, tmp_path / "text", "check", "--event", "timeout")
    as_json = pf11.run_child(repo, tmp_path / "json", "check", "--event", "timeout", "--json")
    assert text.code == as_json.code and text.code in (0, 4), (text.result, as_json.result)
    assert "left out" not in text.out + text.err and "left_out" not in as_json.out, (text.out, as_json.out)
    assert inferred_lines(text.out) == [], text.out


# ---------- section 12.5: the docs and the CHANGELOG ----------


def page(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


PAGES = sorted([*(str(p.relative_to(ROOT)) for p in (ROOT / "docs").rglob("*.md")), "README.md", "examples/your-first-real-agent/README.md"])


def test_no_page_of_the_docs_the_readme_or_the_example_prints_dollar_zero_local() -> None:
    """C1, reading o: 30 places in 10 pages of the docs and one in the example's README printed it
    at 26d4999, and the docs check, which compares a line's first word, would pass them stale."""
    held = {path: page(path).count("(local)") for path in PAGES if "$0 (local)" in page(path)}
    assert held == {}, held


def cost_phrases_of(text: str) -> list[tuple[str, str]]:
    """Every cost phrase a page shows: of a plan's verdict line (or the ``sentence`` of its JSON),
    and of a ``Cost:`` line; each with the line it is on."""
    found = []
    for line in text.splitlines():
        plan = re.search(r"(?:^plan  |\"sentence\": \")[\d,]+ rollouts of [^\n]*? replicates on [^,]+, (.*?)\"?,?$", line)
        cost = re.match(r"^\s*\"?Cost: (.*?)\"?,?$", line)
        if plan or cost:
            found.append(((plan or cost).group(1), line))  # type: ignore[union-attr]
    return found


def test_every_cost_phrase_a_page_shows_is_one_the_plan_prints() -> None:
    """A cost phrase a page shows says what the agent's own calls come to: ``$0`` with its
    declaration, a declared figure, or the ``not priced`` words, on every backend; and a page
    that shows the example's or the demo's plan on this machine shows ``$0``."""
    wrong, shown = [], 0
    for path in PAGES:
        for phrase, line in cost_phrases_of(page(path)):
            shown += 1
            agent = "not priced" in phrase or "your agent's own calls" in phrase
            free = phrase == "$0" or (phrase.startswith("$0 (") and "declares" in phrase)
            packaged = re.search(r" of (mock-agent|support-bot): [^,]* x 194 replicates on local, ", line)
            if "(local)" in phrase or not (agent or free) or (packaged and not free):
                wrong.append((path, line))
    assert wrong == [], wrong
    assert shown >= 30, f"the pages show {shown} cost phrases, fewer than they did"


DOCS_CASES: dict[str, Callable[[], list[str]]] = {
    # What the plan prices and what it does not; [cost]; the cap on every backend; the trial's lines; --json.
    "docs/commands/sweep.md": lambda: m4.missing(
        page("docs/commands/sweep.md"), re.compile(r"`\[cost\]`[^.]*\bnot priced\b|\bnot priced\b[^.]*`\[cost\]`"), "usd_per_rollout", "`compute only`", "every backend",
        "model calls", "tokens", "at a sweep's size", "not counted", "compute_usd", "agent_usd_per_rollout", "agent_usd", "agent_basis",
        "total_usd", "cap_usd", "model_calls")
    + m4.missing(m4.part(page("docs/commands/sweep.md"), "Exit codes"), "--max-cost", "`[cost]`"),
    # The [cost] section: its two keys, the costliest condition, 0, from tokens to a figure, what the cap holds.
    "docs/sweep-spec.md": lambda: m4.missing(
        m4.part(page("docs/sweep-spec.md"), "`[cost]`"), "usd_per_rollout", "basis", "costliest", "usd_per_rollout = 0", "tokens",
        re.compile(r"\bupper bound\b"), "max_cost", "compute"),
    "docs/backends.md": lambda: m4.missing(page("docs/backends.md"), "not priced", "`[cost]`", "`compute only`", "max_cost"),
    # Step 3, how to ask for more, the two new items and the cost item, the demo's [cost], what diff leaves out.
    "docs/setup-with-your-agent.md": lambda: m4.missing(
        page("docs/setup-with-your-agent.md"), "Also compare temperature 0 and 0.7", "in your own words", re.compile(r"axes I did not add", re.I),
        re.compile(r"\bfactor\b"), "`[cost]`", "usd_per_rollout = 0", re.compile(r"does not price your agent's own calls"),
        "diff --event", re.compile(r"\bleaves? out\b"), re.compile(r"\bbilled\b")),
    "docs/commands/diff.md": lambda: m4.missing(page("docs/commands/diff.md"), re.compile(r"`inferred:` line[^.]*\bleft out\b"), "`left_out`", "--event"),
    "docs/commands/report.md": lambda: m4.missing(page("docs/commands/report.md"), re.compile(r"`inferred:` line[^.]*\bleft out\b"), "--event"),
    "docs/defining-outcomes.md": lambda: m4.missing(page("docs/defining-outcomes.md"), "left out", "--event", "inferred:", re.compile(r"\bneither\b")),
    "docs/concepts/traces.md": lambda: m4.missing(page("docs/concepts/traces.md"), re.compile(r"sweep --try`?[^.]*`llm` spans"), "tokens", "model calls"),
    # The quickstart: the declaration behind its $0, and what its diff leaves out.
    "docs/quickstart.md": lambda: m4.missing(page("docs/quickstart.md"), "`[cost]`", "usd_per_rollout = 0", "left out: completed", "--event"),
    "docs/recipes/first-look.md": lambda: m4.missing(page("docs/recipes/first-look.md"), "left out: completed"),
    "docs/recipes/a-model-change-with-cost.md": lambda: m4.missing(
        page("docs/recipes/a-model-change-with-cost.md"), "`[cost]`", "usd_per_rollout", re.compile(r"\bcostlier\b"), re.compile(r"\bask\w*\b")),
    "docs/commands/init.md": lambda: m4.missing(page("docs/commands/init.md"), "in your own words", "`[cost]`", "usd_per_rollout = 0"),
    "examples/your-first-real-agent/README.md": lambda: m4.missing(page("examples/your-first-real-agent/README.md"), "not priced"),
    "README.md": lambda: m4.missing(m4.part(page("README.md"), "Let your coding agent set it up"), re.compile(r"\byour cases\b"), re.compile(r"\bask\w*\b"))
    + m4.missing(page("README.md"), re.compile(r"\bcompute cost\b"), "`[cost]`"),
}


@pytest.mark.parametrize("case", list(DOCS_CASES))
def test_the_docs_say_what_the_plan_prices_which_axes_the_skill_writes_and_what_diff_leaves_out(case: str) -> None:
    """Section 12.5, by facts (reading o)."""
    assert DOCS_CASES[case]() == [], case


def test_the_0_5_0_entry_has_the_cost_line_the_cap_the_trials_count_the_skills_axes_and_what_diff_leaves_out() -> None:
    """Section 12.5: under ``## 0.5.0`` four Changed items and one Added item."""
    text = page("CHANGELOG.md")
    entry = text.split("\n## 0.5.0", 1)[1].split("\n## ", 1)[0]

    def items(heading: str) -> list[str]:
        block = entry.split(f"\n### {heading}\n", 1)[1].split("\n### ", 1)[0]
        return [" ".join(item.split()) for item in re.split(r"(?m)^- ", block) if item.strip()]

    def one(heading: str, *facts: str) -> str:
        found = [item for item in items(heading) if all(fact in item for fact in facts[:1])]
        assert len(found) == 1, (facts[0], items(heading))
        assert m4.missing(found[0], *facts) == [], found[0]
        return found[0]

    cost = one("Changed", "$0 (local)", "not priced", "`[cost]`", "usd_per_rollout", "usd_per_rollout = 0", "example", "demo")
    # Measured: Prove 0.4.0 refuses a spec that has a [cost] table, and the entry says so.
    assert re.search(r"\b0\.4\.0\b[^.]*\brefuses?\b|\brefuse[sd]?\b[^.]*\b0\.4\.0\b", cost), cost
    one("Changed", "`--max-cost` holds", "every backend", "this machine", "`[cost]`", "compute")
    one("Added", "model calls", "sweep --try", "tokens", "trace", "sweep's size")
    one("Changed", "one axis", "skill", "cases", "asked", "multiply", "leaves out")
    one("Changed", "`left_out`", "diff", "report", "inferred:", "left out")
