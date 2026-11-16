"""0.3.1, prove#4: ``sweep --note TEXT`` records what changed, and every face that shows a
comparison's before and after shows each run's note. The frozen tests.

There is no spec for 0.3.1; the invariants below are written from the issue, and each choice it
leaves open is named below as a reading, each one put to a ruling.
The issue's second sentence, "capture the target commit automatically", is later and out of scope
here.

**Readings, named here** (where the issue leaves a choice, the one this file makes; each one a
yes/no).

- R1 Where it is stored: the run's ``manifest.json``, a top-level key ``note`` holding the text,
  written when the run is opened, absent when the sweep was given no note. The artifact format's
  1.2: an optional key a reader that does not know it ignores. A stored ``note`` that is not a
  non-blank string (another writer's) reads as no note. (yes/nos 4, 5)
- R2 What a note may be: one line of 1 to 200 characters after the ends are trimmed, any
  character but a control character or a line or paragraph separator (a tab is refused too). A
  note that is not is refused before the run folder exists, as an unfit ``--name`` is: exit 1, one
  ``error:`` line naming ``--note``, nothing on stdout. (yes/no 6)
- R3 A resume: the run keeps the note it was opened with; ``--resume`` with ``--note`` is refused,
  exit 1, the run untouched. (yes/no 7)
- R4 Where it shows, as a line or a field of its own beside each run, so that the output of a run
  with no note is what it is today:
  - ``diff`` and ``check``: in the verdict block, ``  before note  <note>`` directly after
    ``  before  <name>``, and ``  after note  <note>`` directly after ``  after  <name>``; their
    ``--json`` document (and so ``report``'s pair document and the saved ``comparison.json``)
    carries ``note_a`` and ``note_b``, each only for a run that has a note.
  - ``report`` of a pair: ``report.md`` has ``before note  <note>`` directly after its ``before``
    line and ``after note  <note>`` after its ``after`` line; ``receipt.html`` shows both notes.
    ``report`` of one run: ``report.md`` has a line ``note  <note>``; ``--json`` carries ``note``.
  - ``runs``: a last column ``note`` when any run listed has one (a run without one shows ``-``),
    no such column when none has; ``--json`` carries ``note`` on each run that has one.
  - ``inspect``: ``  note  <note>`` directly after its first line; ``--json`` carries ``note``.
  - The core's views, which the dashboard and the terminal app render: the runs view's
    ``runs[*].note``, the run view's ``note``, the comparison view's ``before.note`` and
    ``after.note``, each only for a run that has a note. The dashboard's runs list, run page
    and comparison page show them, as text, never as markup (``receipt.html`` too); the app's run screen shows the
    run's note, and its verdict screen each run's note directly under that run, as ``diff`` does.
  A run with no note prints exactly what it prints today, in text and in JSON: every key above
  is absent for it (the page and app snapshots and the pinned JSON documents hold that).
  (yes/nos 8 and 9)
- R5 The docs: ``docs/artifact-format.md`` names ``note`` with the manifest's keys and as the
  format's 1.2; ``docs/commands/sweep.md`` gives ``--note``, its limit and what a resume does.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| N1 ``sweep --note`` writes ``note`` into the new manifest; no note, no key | ``test_n1_*`` |
| N2 an unfit note is refused before the run folder exists | ``test_n2_*`` |
| N3 a resume keeps the note; ``--resume --note`` is refused | ``test_n3_*`` |
| N4 ``diff`` and ``check``, text and ``--json`` | ``test_n4_*`` |
| N5 ``report``, a pair and one run | ``test_n5_*`` |
| N6 ``runs``, text and ``--json`` | ``test_n6_*`` |
| N7 ``inspect``, text and ``--json``; the note before the run's declaration lines | ``test_n7_*`` |
| N8 the core's views and the dashboard's pages, as text | ``test_n8_*`` |
| N9 the terminal app | ``test_n9_*`` |
| N10 a stored note that is not one reads as none | ``test_n10_*`` |
| N11 the docs | ``test_n11_*`` |
"""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from poisson_prove.trace import Declaration

ROOT = Path(__file__).resolve().parents[1]
MOCK = "poisson_prove.examples.mock_agent"
BASE_NOTE = "baseline: the shipped prompt"
RETRY_NOTE = "retry each tool call once — ünïcode ✓"
UNSET: Any = object()

SPEC = """\
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = 20

[axes.task_id]
type = "categorical"
values = ["search", "refund"]
"""
LOOSE = ("--max-mde", "0.99")


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


@pytest.fixture(autouse=True)
def _empty_home_and_no_store_variables(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    monkeypatch.setenv("COLUMNS", "200")


def cli(*argv: str | Path) -> Result:
    from poisson_prove import cli as module

    out, err = StringIO(), StringIO()
    code = module.main([str(a) for a in argv], stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def at(store: Path, *argv: str | Path) -> Result:
    return cli("--store", store, *argv)


def strict_json(text: str) -> Any:
    def refuse(token: str) -> Any:
        raise ValueError(f"not strict JSON: {token}")

    return json.loads(text, parse_constant=refuse)


def ok_json(r: Result) -> dict[str, Any]:
    assert r.code in (0, 4), r
    doc = strict_json(r.out)
    assert isinstance(doc, dict)
    return doc


def manifest_of(store: Path, run_id: str) -> dict[str, Any]:
    return json.loads((store / run_id / "manifest.json").read_text(encoding="utf-8"))


def run_ids(store: Path) -> set[str]:
    return {p.name for p in store.iterdir() if (p / "manifest.json").is_file()} if store.is_dir() else set()


def listing(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()} if root.exists() else {}


def assert_refusal(r: Result, *facts: str) -> None:
    """As PF1.2 has it: exit 1, one ``error:`` line then only ``next:`` lines, nothing on stdout."""
    assert r.code == 1, r
    assert r.out == "", r.out
    lines = [line for line in r.err.splitlines() if not line.startswith("note: ")]
    assert lines and lines[0].startswith("error: "), r.err
    assert all(line.startswith("  next: ") for line in lines[1:]), r.err
    for fact in facts:
        assert fact in lines[0], (fact, r.err)


def visible_text(markup: str) -> str:
    markup = re.sub(r"<(style|script)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    return html.unescape(" ".join(" ".join(re.findall(r">([^<]+)<", markup)).split()))


def norm(text: str) -> str:
    return " ".join(text.split())


# ---------- stores built by hand, as a sweep with --note would leave them ----------

BASE_ID, RETRY_ID, PLAIN_ID = "20261115T100000Z-b001", "20261115T110000Z-b002", "20261115T090000Z-b000"


def write_run(
    root: Path, run_id: str, *, created_at: str, name: str, violated: tuple[int, int], note: Any = UNSET, declared: dict[str, Any] | None = None
) -> None:
    """A complete run of two conditions (``cell`` a and b), 40 episodes each; ``violated`` is how
    many of each ended ``violated``, the rest ``completed``. ``note`` goes into the manifest as
    ``note`` exactly as given (a sweep writes only a string); left out, the manifest has no key."""
    store = Store(root)
    store.create_run(RunManifest(
        run_id=run_id, target_id="mock-agent", t_unit="steps", run_salt=f"salt-{run_id}",
        axis_types={"cell": "categorical"}, backend="local", environment={}, created_at=created_at, name=name,
        declared=None if declared is None else Declaration.from_dict(declared),
    ))
    records = []
    for cell, k in zip(("a", "b"), violated, strict=True):
        config = {"cell": cell}
        for i in range(40):
            records.append(EpisodeRecord(
                run_id=run_id, config_hash=config_hash(config), config=config, seed=1000 + i, replicate_index=i,
                outcome="violated" if i < k else "completed", t=1.0 + i / 10, horizon=10.0, confidence=None,
                meta={}, error=None, wall_time=0.01, backend_meta={},
            ))
    store.append(run_id, records)
    store.mark_complete(run_id)
    if note is not UNSET:
        path = root / run_id / "manifest.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["note"] = note
        path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def noted_store(root: Path, *, base_note: Any = BASE_NOTE, retry_note: Any = RETRY_NOTE) -> Path:
    """Three runs: ``plain`` (no note, oldest), ``base`` and ``retry`` (newest), noted."""
    write_run(root, PLAIN_ID, created_at="2026-11-15T09:00:00Z", name="plain", violated=(5, 20))
    write_run(root, BASE_ID, created_at="2026-11-15T10:00:00Z", name="base", violated=(5, 20), note=base_note)
    write_run(root, RETRY_ID, created_at="2026-11-15T11:00:00Z", name="retry", violated=(4, 5), note=retry_note)
    return root


@pytest.fixture(scope="module")
def noted(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return noted_store(tmp_path_factory.mktemp("noted") / "store")


def copied(noted: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "store"
    shutil.copytree(noted, dest)
    return dest


def detail_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("  ") and not line.startswith("   ")]


# ---------- N1 sweep --note ----------


@pytest.fixture(scope="module")
def spec(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("spec") / "spec.toml"
    path.write_text(SPEC, encoding="utf-8")
    return path


def test_n1_sweep_note_is_written_into_the_new_manifest_trimmed(spec: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--note", "  prompt v2: a shorter system prompt  ", "--yes", *LOOSE)
    assert r.code == 0, r
    (run_id,) = run_ids(store)
    assert manifest_of(store, run_id)["note"] == "prompt v2: a shorter system prompt"


@pytest.mark.parametrize("note", ["n" * 200, "ünïcode, emoji ✓ and <angle> & \"quotes\"", "-starts with a dash"], ids=["200 characters", "any printable", "a leading dash"])
def test_n1_a_fit_note_is_stored_as_given(note: str, spec: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", f"--note={note}", "--yes", *LOOSE)
    assert r.code == 0, r
    (run_id,) = run_ids(store)
    assert manifest_of(store, run_id)["note"] == note


def test_n1_a_sweep_without_note_writes_no_note_key(spec: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--yes", *LOOSE)
    assert r.code == 0, r
    (run_id,) = run_ids(store)
    assert "note" not in manifest_of(store, run_id)


def test_n1_sweep_help_names_note() -> None:
    r = cli("sweep", "--help")
    assert r.code == 0 and "--note" in r.out, r


# ---------- N2 refusals ----------

UNFIT = {
    "empty": "",
    "blank": "   ",
    "201 characters": "n" * 201,
    "two lines": "two\nlines",
    "a carriage return": "one\rtwo",
    "a tab": "tab\tinside",
    "a control character": "bell\x07",
    "a line separator": "one two",
    "a paragraph separator": "one two",
}


@pytest.mark.parametrize("case", list(UNFIT))
def test_n2_an_unfit_note_is_refused_before_the_run_folder_exists(case: str, spec: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    write_run(store, PLAIN_ID, created_at="2026-11-15T09:00:00Z", name="plain", violated=(5, 20))
    before = listing(store)
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", f"--note={UNFIT[case]}", "--yes", *LOOSE)
    assert_refusal(r, "--note")
    if case == "201 characters":
        assert "200" in r.err.splitlines()[0], r.err
    assert listing(store) == before


def test_n2_the_refusal_comes_before_the_plan_and_with_json_too(spec: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--note=two\nlines", "--json", "--yes", *LOOSE)
    assert_refusal(r, "--note")
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--note=", "--dry-run", *LOOSE)
    assert_refusal(r, "--note")
    assert not store.exists() or run_ids(store) == set()


# ---------- N3 a resume ----------


def test_n3_a_resume_keeps_the_note_the_run_was_opened_with(spec: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--note", "first segment", "--max-rollouts", "3", "--yes", *LOOSE)
    assert r.code == 3, r  # stopped short at --max-rollouts: the run is partial
    (run_id,) = run_ids(store)
    assert manifest_of(store, run_id)["status"] == "partial"
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--resume", run_id, "--yes", *LOOSE)
    assert r.code == 0, r
    after = manifest_of(store, run_id)
    assert after["status"] == "complete" and after["note"] == "first segment"


def test_n3_resume_with_note_is_refused_and_the_run_is_untouched(spec: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--note", "first segment", "--max-rollouts", "3", "--yes", *LOOSE)
    assert r.code == 3, r  # stopped short at --max-rollouts: the run is partial
    (run_id,) = run_ids(store)
    before = listing(store)
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--resume", run_id, "--note", "second segment", "--yes", *LOOSE)
    assert_refusal(r, "--note")
    assert "resume" in r.err.splitlines()[0], r.err
    assert listing(store) == before


def test_n3_resume_with_note_is_refused_for_a_run_without_one_too(spec: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--max-rollouts", "3", "--yes", *LOOSE)
    assert r.code == 3, r  # stopped short at --max-rollouts: the run is partial
    (run_id,) = run_ids(store)
    before = listing(store)
    r = at(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--resume", run_id, "--note", "added later", "--yes", *LOOSE)
    assert_refusal(r, "--note")
    assert listing(store) == before


# ---------- N4 diff and check ----------


#: ``check --fail-on worse`` (its default) needs to know the event is a failure.
EVENT = {"diff": "violated", "check": "violated:failure"}


def _block_order(text: str) -> list[str]:
    """The verdict block's detail lines, label and value, up to the first blank line."""
    lines = text.splitlines()
    out = []
    for line in lines[1:]:
        if not line.strip():
            break
        out.append(line)
    return out


@pytest.mark.parametrize("verb", ["diff", "check"])
def test_n4_each_note_sits_under_its_runs_line_in_the_verdict_block(verb: str, noted: Path) -> None:
    r = at(noted, verb, "base", "retry", "--event", EVENT[verb])
    assert r.code in (0, 4), r
    block = _block_order(r.out)
    i = block.index("  before  base")
    assert block[i + 1] == f"  before note  {BASE_NOTE}", block
    j = block.index("  after  retry")
    assert block[j + 1] == f"  after note  {RETRY_NOTE}", block


@pytest.mark.parametrize("verb", ["diff", "check"])
def test_n4_a_run_without_a_note_has_no_note_line(verb: str, noted: Path) -> None:
    r = at(noted, verb, "plain", "retry", "--event", EVENT[verb])
    assert r.code in (0, 4), r
    block = _block_order(r.out)
    assert not any(line.startswith("  before note") for line in block), block
    assert block[block.index("  after  retry") + 1] == f"  after note  {RETRY_NOTE}", block
    r = at(noted, verb, "plain", "base", "--event", EVENT[verb])
    assert r.code in (0, 4), r
    block = _block_order(r.out)
    assert not any(line.startswith("  before note") for line in block), block
    assert block[block.index("  after  base") + 1] == f"  after note  {BASE_NOTE}", block


def test_n4_two_runs_without_notes_print_exactly_what_they_did(noted: Path, tmp_path: Path) -> None:
    """The same pair, stored without the notes, prints the same diff but for the two note lines."""
    bare = noted_store(tmp_path / "bare", base_note=UNSET, retry_note=UNSET)
    with_notes = at(noted, "diff", "base", "retry", "--event", "violated")
    without = at(bare, "diff", "base", "retry", "--event", "violated")
    assert without.code == with_notes.code
    kept = [line for line in with_notes.out.splitlines() if not line.startswith(("  before note  ", "  after note  "))]
    assert kept == without.out.splitlines()
    assert len(kept) == len(with_notes.out.splitlines()) - 2
    assert not any(line.startswith(("  before note", "  after note")) for line in without.out.splitlines())


@pytest.mark.parametrize("verb", ["diff", "check"])
def test_n4_json_carries_note_a_and_note_b(verb: str, noted: Path) -> None:
    doc = ok_json(at(noted, verb, "base", "retry", "--event", EVENT[verb], "--json"))
    assert doc["note_a"] == BASE_NOTE and doc["note_b"] == RETRY_NOTE
    doc = ok_json(at(noted, verb, "plain", "retry", "--event", EVENT[verb], "--json"))
    assert "note_a" not in doc and doc["note_b"] == RETRY_NOTE


def test_n4_the_saved_comparison_carries_the_notes(noted: Path, tmp_path: Path) -> None:
    store = copied(noted, tmp_path)
    doc = ok_json(at(store, "diff", "base", "retry", "--event", "violated", "--save", "--json"))
    saved = store / doc["saved"]
    result = json.loads((saved / "comparison.json").read_text(encoding="utf-8"))
    assert result["note_a"] == BASE_NOTE and result["note_b"] == RETRY_NOTE


# ---------- N5 report ----------


def test_n5_a_pair_report_shows_each_note_under_its_run(noted: Path, tmp_path: Path) -> None:
    store = copied(noted, tmp_path)
    out = tmp_path / "out"
    r = at(store, "report", "base", "retry", "--x", "cell", "--event", "violated", "--out", out)
    assert r.code == 0, r
    lines = (out / "report.md").read_text(encoding="utf-8").splitlines()
    i = next(k for k, line in enumerate(lines) if line.startswith("before  base"))
    assert lines[i + 1] == f"before note  {BASE_NOTE}", lines[i : i + 3]
    j = next(k for k, line in enumerate(lines) if line.startswith("after  retry"))
    assert lines[j + 1] == f"after note  {RETRY_NOTE}", lines[j : j + 3]
    receipt = visible_text((out / "receipt.html").read_text(encoding="utf-8"))
    assert BASE_NOTE in receipt and RETRY_NOTE in receipt


def test_n5_a_pair_reports_json_carries_the_notes(noted: Path, tmp_path: Path) -> None:
    store = copied(noted, tmp_path)
    doc = ok_json(at(store, "report", "base", "retry", "--x", "cell", "--event", "violated", "--out", tmp_path / "out", "--json"))
    assert doc["note_a"] == BASE_NOTE and doc["note_b"] == RETRY_NOTE


def test_n5_a_one_run_report_shows_its_note(noted: Path, tmp_path: Path) -> None:
    store = copied(noted, tmp_path)
    out = tmp_path / "out"
    r = at(store, "report", "retry", "--x", "cell", "--event", "violated", "--out", out)
    assert r.code == 0, r
    lines = (out / "report.md").read_text(encoding="utf-8").splitlines()
    assert f"note  {RETRY_NOTE}" in lines
    doc = ok_json(at(store, "report", "retry", "--x", "cell", "--event", "violated", "--out", tmp_path / "out2", "--json"))
    assert doc["note"] == RETRY_NOTE
    doc = ok_json(at(store, "report", "plain", "--x", "cell", "--event", "violated", "--out", tmp_path / "out3", "--json"))
    assert "note" not in doc
    lines = (tmp_path / "out3" / "report.md").read_text(encoding="utf-8").splitlines()
    assert not any(line.startswith("note  ") for line in lines)


# ---------- N6 runs ----------


def test_n6_runs_prints_a_last_note_column_when_a_run_has_a_note(noted: Path) -> None:
    r = at(noted, "--plain", "runs")
    assert r.code == 0, r
    lines = r.out.splitlines()
    header = next(line for line in lines if line.startswith("#  name"))
    assert header.rstrip().endswith("note"), header
    rows = {name: next(line for line in lines if re.match(rf"^(\d+|-)?\s+{name}\s", line)) for name in ("base", "retry", "plain")}
    assert rows["base"].rstrip().endswith(BASE_NOTE)
    assert rows["retry"].rstrip().endswith(RETRY_NOTE)
    assert rows["plain"].rstrip().endswith("-")
    start = header.index("note")
    assert rows["base"][start:].rstrip() == BASE_NOTE


def test_n6_runs_has_no_note_column_when_no_run_has_a_note(tmp_path: Path) -> None:
    bare = noted_store(tmp_path / "bare", base_note=UNSET, retry_note=UNSET)
    r = at(bare, "--plain", "runs")
    assert r.code == 0, r
    header = next(line for line in r.out.splitlines() if line.startswith("#  name"))
    assert header.rstrip().endswith("created"), header
    assert "note" not in header


def test_n6_runs_json_carries_note_on_each_run_that_has_one(noted: Path) -> None:
    doc = ok_json(at(noted, "runs", "--json"))
    by_id = {entry["run_id"]: entry for entry in doc["runs"]}
    assert by_id[BASE_ID]["note"] == BASE_NOTE
    assert by_id[RETRY_ID]["note"] == RETRY_NOTE
    assert "note" not in by_id[PLAIN_ID]


# ---------- N7 inspect ----------


def test_n7_inspect_gives_the_note_under_its_first_line(noted: Path) -> None:
    r = at(noted, "inspect", "retry", "--event", "violated", "--limit", "1")
    assert r.code == 0, r
    lines = r.out.splitlines()
    assert lines[0].startswith("ok  ") and lines[1] == f"  note  {RETRY_NOTE}", lines[:3]
    r = at(noted, "inspect", "plain", "--event", "violated", "--limit", "1")
    assert r.code == 0, r
    assert not r.out.splitlines()[1].startswith("  note  ")


def test_n7_the_note_comes_before_the_runs_declaration_lines(tmp_path: Path) -> None:
    """A run that declared its outcomes has ``inspect`` print what it declared under the first
    line; the note still comes directly after the first line, before those."""
    store = tmp_path / "store"
    declared = {"steps": [], "outcomes": ["violated", "completed"], "gates": [], "failures": ["violated"]}
    write_run(store, RETRY_ID, created_at="2026-11-15T11:00:00Z", name="retry", violated=(4, 5), note=RETRY_NOTE, declared=declared)
    write_run(store, PLAIN_ID, created_at="2026-11-15T09:00:00Z", name="plain", violated=(4, 5), declared=declared)
    bare = at(store, "inspect", "plain", "--event", "violated", "--limit", "1").out.splitlines()
    assert bare[1].strip(), "the declared run prints no line under the first: this test needs one that does"
    lines = at(store, "inspect", "retry", "--event", "violated", "--limit", "1").out.splitlines()
    assert lines[1] == f"  note  {RETRY_NOTE}", lines[:4]
    assert lines[2:4] == bare[1:3], (lines[:5], bare[:4])


def test_n7_inspect_json_carries_the_note(noted: Path) -> None:
    assert ok_json(at(noted, "inspect", "retry", "--event", "violated", "--limit", "1", "--json"))["note"] == RETRY_NOTE
    assert "note" not in ok_json(at(noted, "inspect", "plain", "--event", "violated", "--limit", "1", "--json"))


# ---------- N8 the core's views and the dashboard ----------


def view_document(store: Path, address: str) -> dict[str, Any]:
    from poisson_prove import core

    raw = core.view(core.open_store(store), address).to_json()
    doc = json.loads(raw) if isinstance(raw, (str, bytes)) else json.loads(json.dumps(raw))
    assert isinstance(doc, dict)
    return doc


def saved_comparison(store: Path) -> str:
    doc = ok_json(at(store, "diff", "base", "retry", "--event", "violated", "--save", "--json"))
    return Path(doc["saved"]).name


def test_n8_the_runs_and_run_views_carry_the_note(noted: Path, tmp_path: Path) -> None:
    store = copied(noted, tmp_path)
    runs = {r["run_id"]: r for r in view_document(store, "index.html")["runs"]}
    assert runs[BASE_ID]["note"] == BASE_NOTE and runs[RETRY_ID]["note"] == RETRY_NOTE and "note" not in runs[PLAIN_ID]
    assert view_document(store, f"runs/{RETRY_ID}.html")["note"] == RETRY_NOTE
    assert "note" not in view_document(store, f"runs/{PLAIN_ID}.html")


def test_n8_the_comparison_view_carries_both_notes(noted: Path, tmp_path: Path) -> None:
    store = copied(noted, tmp_path)
    cid = saved_comparison(store)
    doc = view_document(store, f"comparisons/{cid}.html")
    assert doc["before"]["note"] == BASE_NOTE and doc["after"]["note"] == RETRY_NOTE


def test_n8_the_dashboards_run_and_comparison_pages_show_the_notes(noted: Path, tmp_path: Path) -> None:
    store = copied(noted, tmp_path)
    cid = saved_comparison(store)
    r = at(store, "ui")
    assert r.code == 0, r
    ui = store / ".poisson" / "ui"
    run_page = visible_text((ui / "runs" / f"{RETRY_ID}.html").read_text(encoding="utf-8"))
    assert RETRY_NOTE in run_page
    comparison_page = visible_text((ui / "comparisons" / f"{cid}.html").read_text(encoding="utf-8"))
    assert BASE_NOTE in comparison_page and RETRY_NOTE in comparison_page
    assert comparison_page.index(BASE_NOTE) < comparison_page.index(RETRY_NOTE)


MARKUP_NOTE = '<script>alert("n")</script> <b>bold</b> & "quoted"'


def test_n8_a_note_is_shown_as_text_never_as_markup(tmp_path: Path) -> None:
    store = noted_store(tmp_path / "store", retry_note=MARKUP_NOTE)
    cid = saved_comparison(store)
    assert at(store, "ui").code == 0
    out = tmp_path / "out"
    assert at(store, "report", "base", "retry", "--x", "cell", "--event", "violated", "--out", out).code == 0
    ui = store / ".poisson" / "ui"
    for page in (ui / "runs" / f"{RETRY_ID}.html", ui / "comparisons" / f"{cid}.html", ui / "index.html", out / "receipt.html"):
        source = page.read_text(encoding="utf-8")
        assert "<script>alert" not in source and "<b>bold</b>" not in source, page.name
        assert MARKUP_NOTE in visible_text(source), page.name


# ---------- N9 the terminal app ----------


BIG = (160, 60)


def test_n9_the_apps_run_screen_shows_the_runs_note(noted: Path, tmp_path: Path) -> None:
    pytest.importorskip("textual")
    from pf6_support import drive, says

    store = copied(noted, tmp_path)

    async def scenario(s: Any) -> str:
        await s.wait_title("home")
        await s.press("r")
        await s.wait_title("runs")
        await s.focus_row(lambda row: " retry " in f" {row} ")
        await s.press("enter")
        await s.wait_title("run")
        return str(await s.read_through())

    _, text = drive(scenario, cwd=store.parent, store=store.name, size=BIG)  # a short header: the title stays
    shown = bool(says(text, RETRY_NOTE))
    assert shown, f"the run screen does not show the note:\n{text[:1500]}"


def test_n9_the_apps_verdict_screen_shows_each_note_under_its_run_as_diff_does(noted: Path, tmp_path: Path) -> None:
    """The verdict block in ``diff``'s order (the app's own reading of PF6): ``before``, then
    ``before note``, then ``after``, then ``after note``."""
    pytest.importorskip("textual")
    from pf6_support import drive, says

    store = copied(noted, tmp_path)

    async def scenario(s: Any) -> str:
        await s.wait_title("home")
        await s.press("c")
        await s.wait_title("compare")
        await s.press("enter")
        # The verdict screen once its result is in (its header also carries the store's path).
        await s.wait(lambda g: g.header.startswith("poisson-prove · comparison") and says(g.text(), "fragility"), what="the verdict")
        await s.settle()
        return str(await s.read_through())

    _, text = drive(scenario, cwd=store.parent, store=store.name, size=BIG)  # a short header: the title stays
    labels = [m.group(1) for m in re.finditer(r"^\s+(before note|after note|before|after)\s{2,}\S", text, re.M)]
    assert labels[:4] == ["before", "before note", "after", "after note"], text[:2000]
    shown = bool(says(text, BASE_NOTE)) and bool(says(text, RETRY_NOTE))
    assert shown, f"the verdict screen does not show both notes:\n{text[:1500]}"


# ---------- N10 a stored note that is not one ----------


@pytest.mark.parametrize("stored", [42, ["a list"], {"a": "map"}, "", "   ", None], ids=["a number", "a list", "a map", "empty", "blank", "null"])
def test_n10_a_stored_note_that_is_not_a_note_reads_as_none(stored: Any, tmp_path: Path) -> None:
    store = noted_store(tmp_path / "store", retry_note=stored)
    r = at(store, "diff", "base", "retry", "--event", "violated")
    assert r.code in (0, 4), r
    assert "  after note" not in r.out
    assert "note_b" not in ok_json(at(store, "diff", "base", "retry", "--event", "violated", "--json"))
    assert "note" not in {e["run_id"]: e for e in ok_json(at(store, "runs", "--json"))["runs"]}[RETRY_ID]
    assert "note" not in ok_json(at(store, "inspect", "retry", "--event", "violated", "--limit", "1", "--json"))
    assert "note" not in view_document(store, f"runs/{RETRY_ID}.html")


# ---------- N11 the docs ----------


def test_n11_the_artifact_format_names_the_note_as_the_formats_1_2() -> None:
    text = (ROOT / "docs" / "artifact-format.md").read_text(encoding="utf-8")
    manifest = text[text.index("### `manifest.json`") : text.index("### `events.jsonl`")]
    keys = manifest[: manifest.index("```")]  # the paragraphs that list the keys, before the example
    assert "`note`" in keys, keys
    assert re.search(r"`note`[^\n]*\(the format's 1\.2\)|\(the format's 1\.2\)[^\n]*`note`", norm_keep_lines(manifest)), manifest


def norm_keep_lines(text: str) -> str:
    """Paragraphs joined into one line each, so a fact wrapped across lines reads as one."""
    return "\n".join(" ".join(p.split()) for p in text.split("\n\n"))


def test_n11_the_sweep_page_gives_note_its_limit_and_what_a_resume_does() -> None:
    """Its own entry under Options, not the help block (which the docs check keeps equal to
    ``--help``)."""
    text = (ROOT / "docs" / "commands" / "sweep.md").read_text(encoding="utf-8")
    options = text[text.index("## Options") :]
    options = options[: options.index("\n## ", 1)]
    m = re.search(r"^- `--note[^`]*`(.*?)(?=^- `|\Z)", options, re.S | re.M)
    assert m, "docs/commands/sweep.md's Options does not give --note"
    entry = " ".join(m.group(1).split())
    assert "200" in entry, entry
    assert "resume" in entry, entry
