"""PF12, the artifact format: what every run and saved comparison writes into the store (the code suite).

Written from what the store holds and how a comparison is saved, the invariants PF12.1 to PF12.5
and PF12.12, the shared artifact format (``docs/artifact-format.md``) and the test standard.
``tests/test_pf12_ui.py`` holds PF12.6 to PF12.11 and PF12.13, the static UI.

**What this file reads.** The files a command writes into the store (``.poisson/store.json``,
``.poisson/artifacts/<kind>/<id>/``, each run's ``events.jsonl``), what the commands print (text and
``--json``), and, for PF12.3's "equal to the core's result", the core through its boundary
(``pf12_support.core``: the seam with PF5). Statistics are PF4's: this file never pins a number a comparison computes, only that the artifact carries the
number the comparison printed. The quickstart's counts are never pinned; its verdict word is
``mixed`` (its events are not declared) and its shape is what is pinned.

**Readings** (where the invariants leave a choice, the one this file makes).

- A save prints ``  saved  comparison <id>`` (``  saved  check <id>`` for ``check --save``) as
  the last detail line of the command's first block (after ``report``'s ``wrote`` lines; after
  ``serve``'s line with the address, once it is bound), the id as rule 10 prints a hash in text, its
  first 12 hex; its ``--json`` carries ``saved``, the store-relative folder with the whole id
  (``.poisson/artifacts/comparison/<id>``), before ``next``; without a save neither appears, so the
  plain commands' output is unchanged.
- ``serve --json`` saves the comparison as ``serve`` does: ``--json`` changes how the page is
  printed, not what the command does. Its document is the page structure (``poisson-prove.viewpair/7``),
  whose keys stay as they are: it gains no ``saved`` key, and the save shows in the store.
- An unwritable store: exactly one ``note: the comparison was not saved: <the system's words>``
  line, the words carrying ``os.strerror`` of the error; stdout and the exit code are what the same
  command prints on a writable store, less the ``saved`` line. The same sentence for a check.
- The store descriptor is written by every command that writes into the store (``sweep`` and its
  resume, a save, ``ui`` and every refresh); a command that writes nothing creates nothing.
- ``writers`` gains one entry per tool and major.minor version (``version`` the full version,
  ``first_write`` its time); an existing descriptor's other keys, ``created_by`` and ``created_at``
  included, are kept as they are, unknown keys too.
- The id: the first 16 hex of the sha256 of the canonical JSON (sorted keys, no spaces, UTF-8
  unescaped) of ``{"kind", "tool", "tool_version": "<major>.<minor>", "inputs", "settings"}``,
  ``settings`` being the descriptor's less ``method_chosen``.
- ``settings`` holds exactly the result-changing settings plus ``method_chosen`` (``default`` or
  ``named``): the method as resolved; ``events`` as ``{"name", "kind"}`` sorted by name, the kind
  ``failure``, ``success`` or null; ``q``; ``power``; the comparison's horizon; the ``--by`` asked for
  (null when none: the result records how the tree resolved it), ``depth``, ``permutations``,
  ``seed`` and ``max_group_mde`` (which decides which groups resolve, so it changes the result:
  on the two-axis pair ``--max-group-mde 0.5`` moves the grouping from the whole grid to ``rate``); a check runs no tree and has
  ``fail_on`` instead of the tree's five. ``report``'s and ``serve``'s picture flags (``--x``,
  ``--y``, ``--fix``, ``--theme``, ``--top-n``, ``--forest``, ``--title``, ``--methods``) are not
  settings.
- Saving a comparison whose id exists writes nothing: the first folder stays byte for byte,
  ``created_at`` and ``method_chosen`` included, and the command prints the same ``saved`` line.
- ``files`` lists every file of the folder but ``artifact.json`` itself (which cannot hold its
  own digest); a chart's data is a JSON file listed with role ``table`` and schema
  ``poisson-prove.chart/1``, named by the chart's ``data``.
- The table's metrics, from each condition's row of the result: per arm ``n``, ``events``,
  ``rate``, ``share``, ``share_lo``, ``share_hi``; for the pair (arm ``both``) ``delta``, ``stat``,
  ``p``, ``q``, ``q_holm``, ``ci_lo``, ``ci_hi``, ``mde_rise``, ``mde_fall``, ``mde_rise_verdict``,
  ``mde_fall_verdict``, ``p_min``. ``condition`` is the config's canonical JSON. A level is set on the
  shares and their bounds (the Wilson level), the interval's bounds (its level) and the two limits
  (``mde_level``), and null elsewhere; a null value carries a note, the limits' own notes where the
  row has them. More metrics may follow; each is documented (PF12.12).
- A comparison's charts are ``charts/{heatmap,differences,limits}-<event>.svg`` and
  ``charts/<condition hash>/incidence-<event>.svg``, each with its ``.json`` beside it
  (``{"schema", "kind", "event", "condition", "columns", "rows"}``); a comparison over one axis draws
  its heatmap as one row.
- A saved check holds ``check.json`` (``poisson-prove.check/1``, the core's check result) and
  ``conditions.parquet``, and no charts.
- A newer major: ``store.json``'s refuses every command on that store, exit 1, one ``error:``
  line naming both format strings (``poisson.store/2``, ``poisson.store/1``) and ``  next: pip
  install -U poisson-prove``, with nothing on stdout: ``sweep`` checks the store before it plans, so
  this refusal is not one of rule 7's three that keep a plan on screen; an artifact's or an event
  line's refuses ``ui`` the same way.
- An interrupted save: Ctrl-C leaves no artifact and no folder at all; a killed process may leave
  a temporary folder, never one named as an id, and no reader lists it.
- A sweep stopped by ``--max-rollouts`` ends its segment with ``interrupted``; ``progress``
  counts satisfy ``kept + errored == done <= total``; "once just before ``finished`` or
  ``interrupted``" is the event immediately before it (no ``note`` between them).
- Only a run a 0.1.0 sweep starts or resumes has ``events.jsonl``; a run written through the
  ``Store`` alone, like every 0.0.1 run, has none.
- Markers: every PF12 test is in the code suite; the browser check and the wheel's bytes are
  marked ``slow``, like every browser and wheel build.
- ``jsonschema`` (the format's schemas) and ``playwright`` (the browser check) are in ``[dev]``.
- Frozen tests that run ``report`` or ``serve`` read a per-process copy of the generated lattice
  store and the committed 0.0.1 fixture (``conftest.writable_copy``), so no test writes into either; a copy of a
  committed store made for a shared world leaves out any ``.poisson/`` (``copy_fixture``).
- ``serve`` saves, so neither its help nor its Ctrl-C line says nothing was written: the help
  says it saves, and the stopped line says it was interrupted without that clause.
- ``docs/artifact-format.md`` names, in backticks, every key at every depth of every JSON file
  Prove writes under the format (``store.json``, ``artifact.json``, the event lines, ``comparison.json``,
  ``check.json``, the charts' data) and every table column and metric.
- The resumed 0.0.1 run's ``events.jsonl`` starts at ``resumed``, as PF12.1 says.

**Suite.** The code suite, every test. The stores the tests read are built once per session
(``pf12_support.shared_world``); one test sweeps a small spec of its own, and PF12.2 a slowed one.
"""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pf12_support import (
    ARM_METRICS, ARTIFACT_ID, ARTIFACT_SCHEMA, BOTH_METRICS, BYTE_STEPS, CHECK_SETTINGS, COMPARISON_SETTINGS,
    EVENT_GRAMMAR, EVENT_LETTERS, EVENT_SCHEMA, ISO_UTC, LEVELLED, LOOSE, MOCK, OLD, PROGRESS_KEYS, QS_A, QS_B,
    ROOT, SHA256, SHARE_METRICS, SMALL_SPEC, SRC, STORE_SCHEMA, TABLE_COLUMNS, TESTS, Result, as_document, says,
    canonical, cli, copy_store, core, doc,
    expected_id, listing, read_only, saved_id, validate,
)


@pytest.fixture(autouse=True)
def _empty_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    for name in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)


def _store(world: tuple[Path, dict[str, Any]]) -> Path:
    return Path(world[1]["store"])


def _folder(store: Path, kind: str, artifact_id: str) -> Path:
    return store / ".poisson" / "artifacts" / kind / artifact_id


def _descriptor(store: Path, kind: str, artifact_id: str) -> dict[str, Any]:
    return json.loads((_folder(store, kind, artifact_id) / "artifact.json").read_text(encoding="utf-8"))


def _result_of(store: Path, kind: str, artifact_id: str) -> dict[str, Any]:
    return json.loads((_folder(store, kind, artifact_id) / f"{kind}.json").read_text(encoding="utf-8"))


#: Every saved artifact the shared stores hold: (world, label, kind, the pair's arguments).
SAVED = [("stats", name) for name in ("trade", "nothing", "tiny", "peeking", "errors", "logrank", "grid")] + [("old", "quickstart"), ("stats", "check")]


def _saved(name: str, old_world: Any, stats_world: Any) -> tuple[Path, str, str]:
    """(store, kind, id) of one saved artifact of the shared stores."""
    if name == "quickstart":
        return _store(old_world), "comparison", old_world[1]["comparison"]
    if name == "check":
        return _store(stats_world), "check", stats_world[1]["check"]["id"]
    return _store(stats_world), "comparison", stats_world[1]["pairs"][name]["comparison"]


def _runs_of(name: str, stats_world: Any) -> list[str]:
    """The two runs an artifact of the shared stores compared, before then after."""
    if name == "quickstart":
        return [QS_A, QS_B]
    pair = stats_world[1]["pairs"]["trade" if name == "check" else name]
    return [pair["a"], pair["b"]]


# ---------- PF12.1 the store descriptor, and 0.0.1's bytes ----------


def _sweep_small(store: Path, work: Path) -> Result:
    work.mkdir(parents=True, exist_ok=True)
    spec = work / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    return cli(store, "sweep", spec, "--target", f"{MOCK}:rollout", "--yes", *LOOSE, cwd=work)


def _versions() -> tuple[str, str, str]:
    """This Prove's version, one with the same major.minor and another patch, one with another minor."""
    from poisson_prove import __version__

    major, minor, patch = (int(re.match(r"\d+", part).group(0)) for part in __version__.split(".")[:3])  # type: ignore[union-attr]
    return __version__, f"{major}.{minor}.{patch + 7}", f"{major}.{minor + 1}.0"


@pytest.mark.parametrize("before", ["none", "another tool", "this version", "same minor", "other minor"])
def test_pf12_1_the_first_write_creates_the_store_descriptor_and_a_later_writer_only_appends_its_entry(before: str, tmp_path: Path) -> None:
    """``.poisson/store.json`` is ``poisson.store/1`` (its first key ``format``); a writer adds one
    ``writers`` entry per tool and major.minor version and changes nothing else."""
    from poisson_prove import __version__

    store = tmp_path / "prove-runs"
    descriptor = store / ".poisson" / "store.json"
    this, same_minor, other_minor = _versions()
    seeded = {
        "another tool": {"tool": "poisson-trace", "version": "0.4.0"},
        "this version": {"tool": "poisson-prove", "version": this},
        "same minor": {"tool": "poisson-prove", "version": same_minor},
        "other minor": {"tool": "poisson-prove", "version": other_minor},
    }.get(before)
    if seeded is not None:
        descriptor.parent.mkdir(parents=True)
        descriptor.write_text(json.dumps({
            "format": "poisson.store/1",
            "created_by": dict(seeded),
            "created_at": "2026-10-01T00:00:00Z",
            "writers": [{**seeded, "first_write": "2026-10-01T00:00:00Z", "a_writers_own_key": [1, 2]}],
            "a_key_from_a_later_minor": {"kept": True},
        }, indent=2), encoding="utf-8")
    seeded_text = descriptor.read_text(encoding="utf-8") if seeded is not None else None
    assert _sweep_small(store, tmp_path / "work").code == 0
    got = json.loads(descriptor.read_text(encoding="utf-8"))
    validate(got, STORE_SCHEMA)
    assert next(iter(got)) == "format"
    mine = [w for w in got["writers"] if w["tool"] == "poisson-prove" and w["version"].split(".")[:2] == __version__.split(".")[:2]]
    assert len(mine) == 1, got["writers"]
    if seeded is None:
        assert got["created_by"] == {"tool": "poisson-prove", "version": __version__}, got
        assert ISO_UTC.match(got["created_at"]) and got["writers"] == [{"tool": "poisson-prove", "version": __version__, "first_write": got["writers"][0]["first_write"]}]
    elif before in ("this version", "same minor"):
        assert descriptor.read_text(encoding="utf-8") == seeded_text  # nothing to add: the file is untouched
    else:
        old = json.loads(seeded_text or "{}")
        assert {k: v for k, v in got.items() if k != "writers"} == {k: v for k, v in old.items() if k != "writers"}
        assert got["writers"][:1] == old["writers"]
        assert got["writers"][1:] == [{"tool": "poisson-prove", "version": __version__, "first_write": got["writers"][1]["first_write"]}]
    # A second write by the same version adds nothing.
    text = descriptor.read_text(encoding="utf-8")
    assert _sweep_small(store, tmp_path / "work").code == 0
    assert descriptor.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("step", BYTE_STEPS)
def test_pf12_1_every_writing_verb_leaves_every_0_0_1_file_as_it_was(step: str, bytes_world: tuple[Path, dict[str, Any]]) -> None:
    """Over the 0.0.1 store, each writing verb in turn adds files only under ``.poisson/`` and in new
    run folders, and every file that was there keeps its sha256 (PF0.6's byte check, extended), the
    UI's derived pages excepted; the first of them writes the store descriptor."""
    facts = bytes_world[1]
    result = facts["results"][step]
    assert result["code"] in (0, 4), (step, result)
    steps = list(BYTE_STEPS)
    before = facts["before"] if steps.index(step) == 0 else facts["after"][steps[steps.index(step) - 1]]
    after = facts["after"][step]
    original_runs = {path.split("/", 1)[0] for path in facts["before"]}
    # The UI's pages are derived and rebuilt by every writing verb; everything else is only added to.
    changed = [p for p, digest in before.items() if after.get(p) != digest and not p.startswith(".poisson/ui/")]
    assert changed == [], (step, changed)
    for added in sorted(set(after) - set(before)):
        top = added.split("/", 1)[0]
        assert top == ".poisson" or (top not in original_runs and f"{top}/manifest.json" in after), (step, added)
    assert ".poisson/store.json" in after
    # The 0.0.1 store's own files are still the fixture's, byte for byte.
    sums = dict(line.split("  ", 1)[::-1] for line in (OLD / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if line)
    for path, digest in sums.items():
        relative = path.removeprefix("store/").removeprefix("./")
        assert after.get(relative) == digest, (step, path)


def test_pf12_1_the_one_exception_resuming_a_0_0_1_partial_run_changes_its_manifest_and_starts_its_events_at_resumed(resume_world: tuple[Path, dict[str, Any]]) -> None:
    """``sweep --resume`` of a 0.0.1 partial run updates that run's manifest (its status, and the resume
    PF4.39 records), as 0.0.1 did, adds episode parts and an ``events.jsonl`` that starts at ``resumed``,
    and changes nothing else."""
    facts = resume_world[1]
    assert facts["result"]["code"] == 0, facts["result"]
    store = _store(resume_world)
    before, after = facts["before"], facts["after"]
    manifest = f"{QS_A}/manifest.json"
    changed = sorted(p for p, digest in before.items() if after.get(p) != digest)
    assert changed == [manifest], changed
    assert json.loads((store / manifest).read_text(encoding="utf-8"))["status"] == "complete"
    added = sorted(set(after) - set(before))
    assert f"{QS_A}/events.jsonl" in added
    assert all(p.startswith(f"{QS_A}/episodes/") or p.startswith(".poisson/") or p == f"{QS_A}/events.jsonl" for p in added), added
    kinds = [json.loads(line)["kind"] for line in (store / QS_A / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds[0] == "resumed" and kinds[-1] == "finished", kinds


def test_pf12_readers_ignore_the_poisson_folder(old_world: tuple[Path, dict[str, Any]]) -> None:
    """``runs``, the resolver and the public ``Store`` read the same runs once the store
    holds ``.poisson/`` (its descriptor, a saved comparison and the UI) as before."""
    from poisson_prove.store import Store

    store = _store(old_world)
    assert (store / ".poisson" / "store.json").is_file() and (store / ".poisson" / "ui" / "index.html").is_file()
    now = doc(cli(store, "runs", "--json"))
    before = old_world[1]["runs_before"]
    assert [(r["run_id"], r["run_name"]) for r in now["runs"]] == [(r["run_id"], r["run_name"]) for r in before["runs"]]
    assert sorted(Store(store).runs()) == sorted(r["run_id"] for r in before["runs"])
    latest = doc(cli(store, "diff", "--json"))
    assert [latest["verdict"], latest["sentence"], latest["next"]] == old_world[1]["latest_before"]


# ---------- PF12.2 events.jsonl ----------

#: A rollout of the mock agent slowed to a quarter of a second, so a sweep of the small spec's
#: twelve rollouts takes about three seconds and reports progress more than twice.
SLOW_ROLLOUT = """\
import time

from poisson_prove.examples import mock_agent


def rollout(cfg, seed):
    time.sleep(0.25)
    return mock_agent.rollout(cfg, seed)
"""


@pytest.fixture(scope="module")
def slow_world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    """One complete run of the small spec, swept with the slowed rollout."""
    work = tmp_path_factory.mktemp("slow") / "work"
    work.mkdir()
    (work / "pf12_slow.py").write_text(SLOW_ROLLOUT, encoding="utf-8")
    spec = work / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    store = work / "prove-runs"
    old = sys.path[:]
    sys.path.insert(0, str(work))
    sys.modules.pop("pf12_slow", None)
    try:
        swept = cli(store, "sweep", spec, "--target", "pf12_slow:rollout", "--yes", *LOOSE, cwd=work)
    finally:
        sys.path[:] = old
        sys.modules.pop("pf12_slow", None)
    assert swept.code == 0, swept.err
    (run,) = [p.name for p in store.iterdir() if (p / "manifest.json").is_file()]
    return work, {"store": str(store), "runs": {"slow": run}}


def _seconds(at: str) -> float:
    """An event's ``at`` (``YYYY-MM-DDTHH:MM:SS.ffffffZ``) as seconds since the epoch."""
    from datetime import datetime

    return datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp()


@pytest.mark.parametrize("which", ["complete", "resumed", "paired", "errored", "slow"])
def test_pf12_2_every_new_run_writes_its_events_in_section_17_2s_order(which: str, request: pytest.FixtureRequest) -> None:
    """Each line is one ``poisson.run-event/1`` object (``schema`` first, then ``at``, ``kind``,
    ``detail``) in the grammar ``planned started (progress|note)* (finished|interrupted)``, a resume
    adding ``resumed (progress|note)* (finished|interrupted)``; times never go back; ``progress``
    comes at most once a second plus once just before the segment ends, with counts that add up;
    a stopped run's lines stay as they were when the resume appends (append, never rewrite). The
    slowed run reports progress three times or more, so its pace is measured."""
    world = request.getfixturevalue("slow_world" if which == "slow" else "sweep_world")
    facts = world[1]
    run = facts["runs"][which]
    text = (_store(world) / run / "events.jsonl").read_text(encoding="utf-8")
    assert text.endswith("\n")
    events = [json.loads(line) for line in text.splitlines()]
    for event in events:
        validate(event, EVENT_SCHEMA)
        assert list(event)[:4] == ["schema", "at", "kind", "detail"], list(event)
    # A tool's own kinds (``<tool>.<kind>``) are allowed and outside the grammar (Format 4.2).
    letters = "".join(EVENT_LETTERS.get(e["kind"], "?") for e in events if "." not in e["kind"])
    events = [e for e in events if "." not in e["kind"]]
    assert EVENT_GRAMMAR.match(letters), letters
    times = [e["at"] for e in events]
    assert times == sorted(times), times
    segments = re.findall(r"[PR]S?[gn]*[FI]", letters)
    position = 0
    for segment in segments:
        span = events[position:position + len(segment)]
        position += len(segment)
        progress = [e for e in span if e["kind"] == "progress"]
        assert progress and span[-2]["kind"] == "progress", segment  # one just before the end
        for e in progress:
            counts = e["detail"]
            assert all(isinstance(counts[k], int) and counts[k] >= 0 for k in PROGRESS_KEYS), counts
            assert counts["kept"] + counts["errored"] == counts["done"] <= counts["total"], counts
        paced = [_seconds(e["at"]) for e in progress[:-1]]
        if which == "slow":
            assert len(paced) >= 2, [e["at"] for e in progress]
        # At most once a second; the hundredth allows for the clock the time is read from.
        gaps = [later - earlier for earlier, later in zip(paced, paced[1:])]
        assert all(gap >= 0.99 for gap in gaps), [e["at"] for e in progress]
    last = events[-1]
    assert last["kind"] == "finished", letters
    if which == "resumed":
        stopped = facts["events_when_stopped"]
        assert text.startswith(stopped) and stopped.splitlines()[-1].find('"interrupted"') >= 0, stopped[-200:]
        assert letters.count("R") == 1 and letters.index("I") < letters.index("R")
    else:
        assert "R" not in letters and "I" not in letters, letters
    final = [e for e in events if e["kind"] == "progress"][-1]["detail"]
    assert final["done"] == final["total"], final
    if which == "errored":
        assert final["errored"] == final["done"] and final["kept"] == 0, final


def test_pf12_2_a_reader_given_events_cut_mid_line_reads_every_whole_line(sweep_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    """A run still writing, or one that died, leaves a partial last line: the run's view and its page
    show every whole line's event, in order, and nothing of the cut one. The cut
    falls anywhere in the last line (Hypothesis picks where); the page is built once, at one cut."""
    from hypothesis import HealthCheck, given, settings, strategies as st

    store = copy_store(_store(sweep_world), tmp_path / "prove-runs")
    run = sweep_world[1]["runs"]["complete"]
    path = store / run / "events.jsonl"
    whole = path.read_text(encoding="utf-8")
    kinds = [json.loads(line)["kind"] for line in whole.splitlines()]
    extra = json.dumps({"schema": "poisson.run-event/1", "at": "2026-10-24T23:59:59Z", "kind": "note", "detail": {"sentence": "a line that was being written"}})

    def shown(view: dict[str, Any]) -> list[list[str]]:
        return [[str(item.get("kind")) for item in found] for found in _lists_of_dicts(view) if all("kind" in item for item in found)]

    @settings(max_examples=12, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(cut=st.integers(min_value=1, max_value=len(extra) - 1))
    def reads_whole_lines(cut: int) -> None:
        path.write_text(whole + extra[:cut], encoding="utf-8")
        from pf12_support import view_document

        view = view_document(store, f"runs/{run}.html")
        assert kinds in shown(view), (cut, shown(view))
        assert not any(found == [*kinds, "note"] for found in shown(view))

    reads_whole_lines()
    path.write_text(whole + extra[: len(extra) - 2], encoding="utf-8")  # the sentence is in the cut line
    built = cli(store, "ui")
    assert built.code == 0, built.err
    page = (store / ".poisson" / "ui" / "runs" / f"{run}.html").read_text(encoding="utf-8")
    assert "a line that was being written" not in page


def _lists_of_dicts(node: Any) -> list[list[dict[str, Any]]]:
    """Every list of objects anywhere in a JSON document."""
    found: list[list[dict[str, Any]]] = []
    if isinstance(node, dict):
        for value in node.values():
            found += _lists_of_dicts(value)
    elif isinstance(node, list):
        if node and all(isinstance(item, dict) for item in node):
            found.append(node)
        for value in node:
            found += _lists_of_dicts(value)
    return found


def test_pf12_2_runs_written_without_a_sweep_have_no_event_log(stats_world: tuple[Path, dict[str, Any]], old_world: tuple[Path, dict[str, Any]]) -> None:
    """Only a run a 0.1.0 sweep starts or resumes writes ``events.jsonl``: no 0.0.1 run gains
    one by being read, compared or shown, and a run written through the ``Store`` has none."""
    for store in (_store(stats_world), _store(old_world)):
        for manifest in store.glob("*/manifest.json"):
            assert not (manifest.parent / "events.jsonl").exists(), manifest.parent


# ---------- PF12.3 a saved comparison ----------


@pytest.mark.parametrize("name", [n for _, n in SAVED])
def test_pf12_3_the_descriptor_is_valid_and_lists_every_file_with_its_digest(name: str, old_world: Any, stats_world: Any) -> None:
    """``artifact.json`` is ``poisson.artifact/1`` (first key ``format``), its id the folder's name and
    the format's digest, its settings the result-changing ones, its summary the result's word
    and sentence; ``files`` lists every other file in the folder with its role, media type, schema and
    sha256, the charts each with their data beside them, a check none."""
    store, kind, artifact_id = _saved(name, old_world, stats_world)
    folder = _folder(store, kind, artifact_id)
    descriptor = _descriptor(store, kind, artifact_id)
    validate(descriptor, ARTIFACT_SCHEMA)
    assert next(iter(descriptor)) == "format"
    from poisson_prove import __version__

    assert (descriptor["kind"], descriptor["id"], descriptor["tool_version"]) == (kind, artifact_id, __version__)
    assert expected_id(descriptor) == artifact_id
    assert set(descriptor["settings"]) == (CHECK_SETTINGS if kind == "check" else COMPARISON_SETTINGS), sorted(descriptor["settings"])
    result = _result_of(store, kind, artifact_id)
    assert (descriptor["summary"]["verdict"], descriptor["summary"]["sentence"]) == (result["verdict"], result["sentence"])
    assert descriptor["inputs"]["runs"] == _runs_of(name, stats_world), descriptor["inputs"]
    settings = descriptor["settings"]
    assert (settings["method"], settings["q"], settings["horizon"]) == (result["method"], result["q"], result["horizon"]), settings
    assert settings["method_chosen"] == result["method_chosen"], settings
    assert [e["name"] for e in settings["events"]] == sorted(result["by_event"]), settings["events"]
    assert [e["kind"] for e in settings["events"]] == [result["by_event"][e]["kind"] for e in sorted(result["by_event"])], settings["events"]
    from poisson_prove import stats

    assert settings["power"] == stats.POWER
    if kind == "check":
        assert settings["fail_on"] == result["fail_on"]
    on_disk = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    listed = sorted(entry["path"] for entry in descriptor["files"])
    assert listed == [p for p in on_disk if p != "artifact.json"], (listed, on_disk)
    by_path = {entry["path"]: entry for entry in descriptor["files"]}
    for entry in descriptor["files"]:
        assert SHA256.match(entry["sha256"]) and entry["sha256"] == __import__("hashlib").sha256((folder / entry["path"]).read_bytes()).hexdigest(), entry
    assert by_path[f"{kind}.json"] == {**by_path[f"{kind}.json"], "role": "result", "media_type": "application/json", "schema": f"poisson-prove.{kind}/1"}
    assert by_path["conditions.parquet"] == {**by_path["conditions.parquet"], "role": "table", "media_type": "application/vnd.apache.parquet", "schema": "poisson.table/1"}
    charts = {p: e for p, e in by_path.items() if e["role"] == "chart"}
    if kind == "check":
        assert charts == {}, sorted(charts)
        return
    events = [e["name"] for e in descriptor["settings"]["events"]]
    hashes = sorted({str(c["config_hash"]) for e in result["by_event"].values() for c in e["cells"]})
    expected = {f"charts/{chart}-{event}.svg" for chart in ("heatmap", "differences", "limits") for event in events}
    expected |= {f"charts/{h}/incidence-{event}.svg" for h in hashes for event in events}
    assert set(charts) == expected, sorted(set(charts) ^ expected)
    for path, entry in charts.items():
        assert entry["media_type"] == "image/svg+xml" and entry["data"] == path[: -len(".svg")] + ".json", entry
        data = by_path[entry["data"]]
        assert (data["role"], data["media_type"], data["schema"]) == ("table", "application/json", "poisson-prove.chart/1"), data
        chart = json.loads((folder / entry["data"]).read_text(encoding="utf-8"))
        assert list(chart)[:1] == ["schema"] and chart["schema"] == "poisson-prove.chart/1"
        assert {"kind", "event", "condition", "columns", "rows"} <= set(chart), sorted(chart)
        assert all(len(row) == len(chart["columns"]) for row in chart["rows"]) and chart["rows"], path


def _without(document: dict[str, Any], *keys: str) -> dict[str, Any]:
    return {k: v for k, v in document.items() if k not in keys}


#: The envelope keys a verb's ``--json`` puts around the core's document.
ENVELOPE = ("schema", "saved")


@pytest.mark.parametrize("verb", ["diff --save", "report", "serve --json", "check --save", "the core"])
def test_pf12_3_the_saved_result_is_the_cores_result_and_what_the_verb_prints_as_json(verb: str, stats_world: Any, old_world: Any, tmp_path: Path) -> None:
    """``comparison.json`` is the core's ``Comparison``, the same object ``diff --json`` prints inside
    its envelope, whichever verb saved it (and ``check.json`` the core's check result, the object
    ``check --json`` prints): the same keys and values but the envelope's."""
    if verb == "the core":
        shared = _store(old_world)
        saved = _result_of(shared, "comparison", old_world[1]["comparison"])
        c = core()
        comparison = c.compare(c.open_store(shared), QS_A, QS_B)
        assert as_document(comparison) == saved
        assert saved["schema"] == "poisson-prove.comparison/1" and saved["verdict"] == "mixed"
        # PF5.11 through PF12 (PF5's reading a): two faces on one store see each other's saves. The
        # core lists what the command line saved, and saving the same result through the core is
        # that artifact (S10: an ArtifactRef's document carries its ``id`` and ``kind``).
        store = copy_store(shared, tmp_path / "prove-runs")
        opened = c.open_store(store)
        listed = [as_document(ref) for ref in c.artifacts(opened, kind="comparison")]
        assert [(d["id"], d["kind"]) for d in listed] == [(old_world[1]["comparison"], "comparison")], listed
        ref = as_document(c.save(opened, c.compare(opened, QS_A, QS_B)))
        assert (ref["id"], ref["kind"]) == (old_world[1]["comparison"], "comparison"), ref
        assert sorted(p.name for p in (store / ".poisson" / "artifacts" / "comparison").iterdir()) == [old_world[1]["comparison"]]
        return
    pair = stats_world[1]["pairs"]["grid"]
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    shutil.rmtree(store / ".poisson" / "artifacts")
    a, b, argv = pair["a"], pair["b"], pair["argv"]
    runs = {
        "diff --save": (["diff", a, b, *argv, "--save"], ["diff", a, b, *argv, "--json"], "comparison"),
        "report": (["report", a, b, *argv, "--x", "task", "--y", "rate", "--out", str(tmp_path / "r")], ["diff", a, b, *argv, "--json"], "comparison"),
        "serve --json": (["serve", a, b, *argv, "--x", "task", "--y", "rate", "--json"], ["diff", a, b, *argv, "--json"], "comparison"),
        "check --save": (["check", a, b, *argv, "--save"], ["check", a, b, *argv, "--json"], "check"),
    }
    save_argv, json_argv, kind = runs[verb]
    saving = cli(store, *save_argv, cwd=tmp_path)
    assert saving.code in (0, 4), saving.err
    (artifact_id,) = [p.name for p in (store / ".poisson" / "artifacts" / kind).iterdir()]
    saved = _result_of(store, kind, artifact_id)
    printed = doc(cli(store, *json_argv))
    assert saved["schema"] == f"poisson-prove.{kind}/1" and printed["schema"] == f"poisson-prove.{'diff' if kind == 'comparison' else 'check'}/1"
    assert _without(saved, *ENVELOPE) == _without(printed, *ENVELOPE)


def test_pf12_3_the_table_is_long_form_with_the_formats_key_columns_and_every_rows_numbers(old_world: Any, stats_world: Any) -> None:
    """``conditions.parquet`` (``poisson.table/1``) has the format's nine key columns first, in order and
    of their types; one row per (event, condition, arm, metric); every metric of the table for every row of
    the result, its value the result's own number, its level where the metric has one, and a note
    beside every null value."""
    for name in [n for _, n in SAVED]:
        store, kind, artifact_id = _saved(name, old_world, stats_world)
        table = pq.read_table(_folder(store, kind, artifact_id) / "conditions.parquet")
        assert [(f.name, str(f.type)) for f in table.schema][: len(TABLE_COLUMNS)] == list(TABLE_COLUMNS), (name, table.schema)
        rows = table.to_pylist()
        assert {r["artifact_id"] for r in rows} == {artifact_id}
        keys = [(r["event"], r["condition_hash"], r["arm"], r["metric"]) for r in rows]
        assert len(keys) == len(set(keys)), name
        got = {(r["event"], r["condition_hash"], r["arm"], r["metric"]): r for r in rows}
        result = _result_of(store, kind, artifact_id)
        for event, entry in result["by_event"].items():
            for cell in entry["cells"]:
                h = str(cell["config_hash"])
                for metric, field in ARM_METRICS.items():
                    for side in ("a", "b"):
                        row = got[(event, h, side, metric)]
                        assert row["value"] == cell[f"{field}_{side}"] and row["level"] is None, (name, row)
                for side in ("a", "b"):
                    share = cell[f"share_{side}"]
                    for metric, part in zip(SHARE_METRICS, ("value", "lo", "hi"), strict=True):
                        row = got[(event, h, side, metric)]
                        assert (row["value"], row["level"]) == (share[part], share["level"]), (name, row)
                for metric in BOTH_METRICS:
                    row = got[(event, h, "both", metric)]
                    assert row["condition"] == canonical(cell["config"]), row
                    assert row["value"] == cell[metric], (name, metric, row, cell[metric])
                    level = LEVELLED.get(metric)
                    # A null value of a metric with a level keeps the level it was sought at.
                    assert row["level"] == (cell[level] if level else None), (name, row)
                    if row["value"] is None:
                        assert row["note"], (name, row)
                        if metric in ("mde_rise", "mde_fall"):
                            assert row["note"] == cell[f"{metric}_note"], (name, row)


@pytest.mark.parametrize("change", [
    "nothing", "the default named", "q", "method", "events", "permutations", "seed", "by", "depth", "max_group_mde", "the picture's flags", "fail_on",
])
def test_pf12_3_the_id_is_the_digest_of_the_inputs_and_the_result_changing_settings(change: str, stats_world: Any, tmp_path: Path) -> None:
    """Saving twice is one artifact; asking for the same result another way (the default method named,
    a picture flag of ``report``) is the same id, the first descriptor kept; a setting that
    changes the result gives another id, and the new descriptor records it."""
    pair = stats_world[1]["pairs"]["grid"]
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    shutil.rmtree(store / ".poisson" / "artifacts")
    a, b = pair["a"], pair["b"]
    kind = "check" if change == "fail_on" else "comparison"
    base = ["check", a, b, "--event", "fell:failure", "--save"] if kind == "check" else ["diff", a, b, "--event", "fell:failure", "--save"]
    first = cli(store, *base)
    first_id = saved_id(first, kind, store)
    folder = _folder(store, kind, first_id)
    first_bytes = listing(folder)
    other = {
        "nothing": base,
        "the default named": [*base, "--method", "fisher_bh"],
        "q": [*base, "--q", "0.1"],
        "method": [*base, "--method", "logrank_bh"],
        "events": ["diff", a, b, "--event", "fell:failure", "--event", "ok:success", "--save"],
        "permutations": [*base, "--permutations", "499"],
        "seed": [*base, "--seed", "7"],
        "by": [*base, "--by", "rate"],
        "depth": [*base, "--depth", "2"],
        "max_group_mde": [*base, "--max-group-mde", "0.5"],
        "the picture's flags": ["report", a, b, "--event", "fell:failure", "--x", "task", "--y", "rate", "--theme", "light", "--top-n", "3", "--title", "t", "--out", str(tmp_path / "r")],
        "fail_on": [*base, "--fail-on", "any"],
    }[change]
    second = cli(store, *other, cwd=tmp_path)
    assert second.code in (0, 4), second.err
    second_id = saved_id(second, kind, store)
    same = change in ("nothing", "the default named", "the picture's flags")
    assert (second_id == first_id) is same, (change, first_id, second_id)
    assert listing(folder) == first_bytes  # the first folder is never rewritten
    folders = sorted(p.name for p in (store / ".poisson" / "artifacts" / kind).iterdir())
    assert folders == sorted({first_id, second_id}), folders
    descriptor = _descriptor(store, kind, second_id)
    assert expected_id(descriptor) == second_id
    settings = descriptor["settings"]
    if same:
        assert settings["method_chosen"] == "default"
        return
    recorded = {
        "q": ("q", 0.1), "method": ("method", "logrank_bh"), "permutations": ("permutations", 499), "seed": ("seed", 7),
        "by": ("by", "rate"), "depth": ("depth", 2), "max_group_mde": ("max_group_mde", 0.5), "fail_on": ("fail_on", "any"),
        "events": ("events", [{"name": "fell", "kind": "failure"}, {"name": "ok", "kind": "success"}]),
    }[change]
    assert settings[recorded[0]] == recorded[1], settings
    assert settings["method_chosen"] == ("named" if change == "method" else "default")


def _patched_save(store: Path, how: str, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` in a fresh interpreter whose first rename into ``.poisson/artifacts/`` either
    raises ``KeyboardInterrupt`` (Ctrl-C) or ends the process on the spot (a kill): a save renames its
    temporary folder into place last, so either lands while the save is under way; later renames
    (a clean-up putting things back) go through."""
    script = f"""
import os, sys
real_replace, real_rename = os.replace, os.rename
fired = []
def guard(real):
    def move(src, dst, *a, **k):
        if not fired and os.sep + os.path.join('.poisson', 'artifacts') + os.sep in os.fspath(dst):
            fired.append(dst)
            if {how!r} == 'killed':
                os._exit(70)
            raise KeyboardInterrupt
        return real(src, dst, *a, **k)
    return move
os.replace, os.rename = guard(real_replace), guard(real_rename)
from poisson_prove import cli
sys.exit(cli.main(sys.argv[1:]))
"""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(SRC), str(TESTS)])}
    return subprocess.run([sys.executable, "-c", script, "--store", str(store), *argv], capture_output=True, text=True, env=env, timeout=300)


@pytest.mark.parametrize("how", ["ctrl-c", "killed"])
def test_pf12_3_an_interrupted_save_leaves_no_artifact(how: str, stats_world: Any, tmp_path: Path) -> None:
    """A save writes into a temporary folder renamed into place last: interrupted, it leaves no artifact
    — after Ctrl-C nothing at all, after a kill no folder named as an id — no reader lists one, and
    the next save of the same comparison succeeds."""
    pair = stats_world[1]["pairs"]["trade"]
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    shutil.rmtree(store / ".poisson" / "artifacts")
    argv = ["diff", pair["a"], pair["b"], *pair["argv"], "--save"]
    stopped = _patched_save(store, how, argv)
    assert stopped.returncode == (130 if how == "ctrl-c" else 70), (stopped.returncode, stopped.stderr)
    kinds = store / ".poisson" / "artifacts"
    left = sorted(p.relative_to(kinds).as_posix() for p in kinds.rglob("*")) if kinds.exists() else []
    if how == "ctrl-c":
        assert [p for p in left if p.count("/") >= 1] == [], left
    assert not any(ARTIFACT_ID.match(p.split("/")[1]) for p in left if p.count("/") >= 1), left
    c = core()
    assert list(c.artifacts(c.open_store(store), kind="comparison")) == []
    again = cli(store, *argv)
    assert again.code == 0, again.err
    assert (_folder(store, "comparison", saved_id(again, "comparison", store)) / "artifact.json").is_file()


def test_pf12_3_two_processes_saving_the_same_comparison_at_once_leave_one_artifact(stats_world: Any, tmp_path: Path) -> None:
    """Saving the same comparison twice is one artifact also when two commands save it at once (two
    faces on one store, PF5.11; two test workers on one fixture): the second to rename finds the
    folder there, and that is a save, not a failure. Both print the same ``saved`` line and no note,
    and nothing else is left in the folder."""
    pair = stats_world[1]["pairs"]["trade"]
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    shutil.rmtree(store / ".poisson" / "artifacts")
    argv = ["diff", pair["a"], pair["b"], *pair["argv"], "--save"]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(SRC), str(TESTS)])}
    second = [sys.executable, "-c", "import sys; from poisson_prove import cli; sys.exit(cli.main(sys.argv[1:]))", "--store", str(store), *argv]
    script = f"""
import os, subprocess, sys, json
real_replace, real_rename = os.replace, os.rename
fired = []
def guard(real):
    def move(src, dst, *a, **k):
        if not fired and os.sep + os.path.join('.poisson', 'artifacts') + os.sep in os.fspath(dst):
            fired.append(dst)
            # The second save runs to its end while this one waits to rename; a build that holds a
            # lock across the rename makes it wait instead, so it is given a minute, then this one
            # renames and the second is waited for after.
            child = subprocess.Popen({second!r}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                pass
            pending.append(child)
        return real(src, dst, *a, **k)
    return move
os.replace, os.rename = guard(real_replace), guard(real_rename)
pending = []
from poisson_prove import cli
code = cli.main(sys.argv[1:])
for child in pending:
    out, err = child.communicate(timeout=600)
    with open({str(tmp_path / "second.json")!r}, "w") as f:
        json.dump({{"code": child.returncode, "out": out, "err": err}}, f)
sys.exit(code)
"""
    first = subprocess.run([sys.executable, "-c", script, "--store", str(store), *argv], capture_output=True, text=True, env=env, timeout=900)
    other = json.loads((tmp_path / "second.json").read_text(encoding="utf-8"))
    assert (first.returncode, other["code"]) == (0, 0), (first.stderr, other["err"])
    lines = [line for line in first.stdout.splitlines() if line.startswith("  saved  ")]
    assert lines and lines == [line for line in other["out"].splitlines() if line.startswith("  saved  ")], (first.stdout, other["out"])
    assert not any("not saved" in line for line in (first.stderr + other["err"]).splitlines())
    left = sorted(p.name for p in (store / ".poisson" / "artifacts" / "comparison").iterdir())
    assert len(left) == 1 and ARTIFACT_ID.match(left[0]) and left[0].startswith(lines[0].split()[-1]), left
    validate(_descriptor(store, "comparison", left[0]), ARTIFACT_SCHEMA)


# ---------- PF12.4 versions ----------


def test_pf12_4_readers_accept_the_current_major_and_ignore_unknown_keys_and_kinds(sweep_world: Any, stats_world: Any, tmp_path: Path) -> None:
    """A store whose descriptor, artifacts, event lines and table carry keys, kinds and columns this
    Prove does not know (a later minor's, or another tool's): every reader goes on, and shows what it
    knows."""
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    for run in sweep_world[1]["runs"].values():
        shutil.copytree(_store(sweep_world) / run, store / run)
    descriptor = store / ".poisson" / "store.json"
    doc_ = json.loads(descriptor.read_text(encoding="utf-8"))
    doc_["from_a_later_minor"] = {"anything": [1, 2]}
    doc_["writers"][0]["extra"] = True
    descriptor.write_text(json.dumps(doc_), encoding="utf-8")
    trade = stats_world[1]["pairs"]["trade"]["comparison"]
    art = _folder(store, "comparison", trade) / "artifact.json"
    a_doc = json.loads(art.read_text(encoding="utf-8"))
    a_doc["from_a_later_minor"] = "kept"
    a_doc["settings"]["a_later_setting"] = 1
    a_doc["files"][0]["extra"] = "kept"
    art.write_text(json.dumps(a_doc), encoding="utf-8")
    table_path = _folder(store, "comparison", trade) / "conditions.parquet"
    table = pq.read_table(table_path)
    pq.write_table(table.append_column("a_later_column", pa.array(["x"] * table.num_rows)), table_path)
    run = sweep_world[1]["runs"]["complete"]
    events = store / run / "events.jsonl"
    lines = events.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["a_later_key"] = {"x": 1}
    lines[0] = json.dumps(first)
    lines.insert(2, json.dumps({"schema": "poisson.run-event/1", "at": json.loads(lines[1])["at"], "kind": "poisson-trace.checkpoint", "detail": {"t": 1}}))
    events.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for argv in (["runs"], ["ui"], ["diff", stats_world[1]["pairs"]["trade"]["a"], stats_world[1]["pairs"]["trade"]["b"], *stats_world[1]["pairs"]["trade"]["argv"], "--save"]):
        r = cli(store, *argv)
        assert r.code == 0, (argv, r.err)
        assert "error:" not in r.err, r.err
    assert (store / ".poisson" / "ui" / "comparisons" / f"{trade}.html").is_file()
    from pf12_support import view_document

    view = view_document(store, f"runs/{run}.html")
    kinds = [[str(i.get("kind")) for i in found] for found in _lists_of_dicts(view) if all("kind" in i for i in found)]
    known = [json.loads(line)["kind"] for line in lines if not json.loads(line)["kind"].startswith("poisson-trace.")]
    assert known in kinds, kinds


@pytest.mark.parametrize("where, verb", [
    *[("store.json", v) for v in ("runs", "diff", "check", "report", "serve", "inspect", "ui", "sweep")],
    ("artifact.json", "ui"), ("events.jsonl", "ui"),
])
def test_pf12_4_a_newer_major_is_refused_in_one_error_line_naming_both_versions(where: str, verb: str, stats_world: Any, sweep_world: Any, tmp_path: Path) -> None:
    """A file in a newer major than this Prove reads is refused: exit 1, nothing on stdout, one
    ``error:`` line naming both versions, then ``  next: pip install -U poisson-prove``."""
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    pair = stats_world[1]["pairs"]["trade"]
    run = sweep_world[1]["runs"]["complete"]
    shutil.copytree(_store(sweep_world) / run, store / run)
    if where == "store.json":
        path, newer, known = store / ".poisson" / "store.json", "poisson.store/2", "poisson.store/1"
        key = "format"
    elif where == "artifact.json":
        path, newer, known = _folder(store, "comparison", pair["comparison"]) / "artifact.json", "poisson.artifact/2", "poisson.artifact/1"
        key = "format"
    else:
        path, newer, known = store / run / "events.jsonl", "poisson.run-event/2", "poisson.run-event/1"
        key = "schema"
    if where == "events.jsonl":
        lines = path.read_text(encoding="utf-8").splitlines()
        last = json.loads(lines[-1])
        last[key] = newer
        lines[-1] = json.dumps(last)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        document = json.loads(path.read_text(encoding="utf-8"))
        document[key] = newer
        path.write_text(json.dumps(document), encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    (work / "spec.toml").write_text(SMALL_SPEC, encoding="utf-8")
    argv = {
        "runs": ["runs"], "ui": ["ui"], "inspect": ["inspect", pair["a"], "--event", "fell"],
        "diff": ["diff", pair["a"], pair["b"], *pair["argv"]],
        "check": ["check", pair["a"], pair["b"], *pair["argv"]],
        "report": ["report", pair["a"], pair["b"], *pair["argv"], "--x", "cell", "--out", str(work / "r")],
        "serve": ["serve", pair["a"], pair["b"], *pair["argv"], "--x", "cell", "--json"],
        "sweep": ["sweep", str(work / "spec.toml"), "--target", f"{MOCK}:rollout", "--yes", *LOOSE],
    }[verb]
    before = listing(store)
    r = cli(store, *argv, cwd=work)
    assert r.code == 1, (r.code, r.out, r.err)
    assert r.out == "", r.out
    lines = r.err.splitlines()
    assert lines[0].startswith("error: ") and newer in lines[0] and known in lines[0], lines
    assert all(line.startswith("  next: ") for line in lines[1:]) and "  next: pip install -U poisson-prove" in lines, lines
    assert listing(store) == before  # refused: nothing written


# ---------- PF12.5 which commands save ----------


@pytest.mark.parametrize("verb, saves", [
    ("diff", False), ("diff --json", False), ("diff --save", True), ("diff --save --json", True),
    ("check", False), ("check --save", True), ("check --save --json", True),
    ("report", True), ("report --json", True), ("serve --json", True),
])
def test_pf12_5_report_and_serve_save_and_diff_and_check_only_with_save(verb: str, saves: bool, stats_world: Any, tmp_path: Path) -> None:
    """``report`` and ``serve`` save the comparison they show, ``diff`` and ``check`` only with
    ``--save``; a save says so on one ``  saved  <kind> <id>`` detail line, the last of the first block,
    or in ``--json`` as ``saved``, the store-relative folder; without a save the output is the
    command's own, and nothing is written into the store."""
    pair = stats_world[1]["pairs"]["trade"]
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    shutil.rmtree(store / ".poisson" / "artifacts")
    a, b, ev = pair["a"], pair["b"], pair["argv"]
    words = verb.split()
    name = words[0]
    tail = words[1:]
    argv = {
        "diff": ["diff", a, b, *ev], "check": ["check", a, b, *ev],
        "report": ["report", a, b, *ev, "--x", "cell", "--out", str(tmp_path / "r")],
        "serve": ["serve", a, b, *ev, "--x", "cell"],
    }[name] + tail
    kind = "check" if name == "check" else "comparison"
    plain = cli(store, *[w for w in argv if w != "--save"], cwd=tmp_path) if name in ("diff", "check") else None
    if plain is not None and "--save" in argv:
        shutil.rmtree(store / ".poisson" / "artifacts", ignore_errors=True)
    before = listing(store)
    r = cli(store, *argv, cwd=tmp_path)
    assert r.code in (0, 4), r.err
    folders = sorted((store / ".poisson" / "artifacts" / kind).iterdir()) if (store / ".poisson" / "artifacts" / kind).exists() else []
    assert len(folders) == (1 if saves else 0), folders
    as_json = "--json" in tail
    if as_json:
        printed = doc(r)
        assert list(printed)[-1] == "next" or name == "serve", list(printed)[-3:]
        if saves and name != "serve":
            assert printed["saved"] == f".poisson/artifacts/{kind}/{folders[0].name}", printed.get("saved")
        else:
            assert "saved" not in printed  # serve --json is the page structure, its keys unchanged
    else:
        lines = [line for line in r.out.splitlines() if line.startswith("  saved  ")]
        if saves:
            first = r.out.split("\n\n", 1)[0].splitlines()
            assert first[-1] == f"  saved  {kind} {folders[0].name[:12]}" and lines == [first[-1]], first
        else:
            assert lines == []
    if not saves:
        assert listing(store) == before  # a command that does not save writes nothing
    if plain is not None:
        # The save adds its one line, or its one key, and changes nothing else the command prints.
        if as_json:
            assert {k: v for k, v in doc(r).items() if k != "saved"} == doc(plain)
        else:
            assert [line for line in r.out.splitlines() if not line.startswith("  saved  ")] == plain.out.splitlines()
        assert (r.code, r.err) == (plain.code, plain.err)


@pytest.mark.parametrize("verb", ["diff --save", "check --save", "report", "serve --json", "diff", "check", "runs", "inspect"])
def test_pf12_5_an_unwritable_store_gives_the_note_and_the_commands_own_exit_code(verb: str, stats_world: Any, tmp_path: Path) -> None:
    """A store that cannot be written to does not stop a command that saves: one ``note: the comparison
    was not saved: <the system's words>`` and the command goes on, with what it prints on a writable
    store less the ``saved`` line, and its exit code. A command that does not save works on it
    with no note at all."""
    pair = stats_world[1]["pairs"]["trade"]
    a, b, ev = pair["a"], pair["b"], pair["argv"]
    writable = copy_store(_store(stats_world), tmp_path / "w" / "prove-runs")
    locked = copy_store(_store(stats_world), tmp_path / "l" / "prove-runs")
    for root in (writable, locked):
        shutil.rmtree(root / ".poisson" / "artifacts")
    argv = {
        "diff --save": ["diff", a, b, *ev, "--save"], "check --save": ["check", a, b, *ev, "--save"],
        "report": ["report", a, b, *ev, "--x", "cell", "--out", "r"], "serve --json": ["serve", a, b, *ev, "--x", "cell", "--json"],
        "diff": ["diff", a, b, *ev], "check": ["check", a, b, *ev], "runs": ["runs"], "inspect": ["inspect", a, "--event", "fell"],
    }[verb]
    # Each store is named as typed, relative to its folder, so the two print the same words.
    expected = cli("prove-runs", *argv, cwd=writable.parent)
    with read_only(locked):
        got = cli("prove-runs", *argv, cwd=locked.parent)
    assert got.code == expected.code, (got.code, expected.code, got.err)
    saves = verb in ("diff --save", "check --save", "report", "serve --json")
    if verb == "serve --json":
        assert _without(doc(got), "saved") == _without(doc(expected), "saved") and "saved" not in doc(got)
    else:
        assert got.out == "\n".join(line for line in expected.out.split("\n") if not line.startswith("  saved  ")), (got.out, expected.out)
    notes = [line for line in got.err.splitlines() if line not in expected.err.splitlines()]
    if saves:
        assert len(notes) == 1 and notes[0].startswith("note: the comparison was not saved: "), got.err
        assert os.strerror(errno.EACCES) in notes[0], notes
    else:
        assert notes == [], got.err


@pytest.mark.parametrize("verb", ["diff --save", "check --save", "report", "serve --json"])
def test_pf12_5_a_comparison_refused_for_its_cases_saves_nothing(verb: str, stats_world: Any, tmp_path: Path) -> None:
    """PF4.38: a condition whose episodes ran more than one case is refused by every comparing verb; a
    refusal spends and writes nothing, so no artifact, no descriptor change and no page is added."""
    store = copy_store(_store(stats_world), tmp_path / "prove-runs")
    a, b = stats_world[1]["cases"]["a"], stats_world[1]["cases"]["b"]
    ev = ["--event", "fell:failure", "--method", "fisher_bh"]
    argv = {
        "diff --save": ["diff", a, b, *ev, "--save"], "check --save": ["check", a, b, *ev, "--save"],
        "report": ["report", a, b, *ev, "--x", "cell", "--out", str(tmp_path / "r")], "serve --json": ["serve", a, b, *ev, "--x", "cell", "--json"],
    }[verb]
    before = listing(store)
    r = cli(store, *argv)
    assert r.code == 1 and r.out == "", (r.code, r.out)
    assert r.err.splitlines()[0].startswith("error: "), r.err
    assert listing(store) == before
    assert not (tmp_path / "r").exists()


def test_pf12_5_the_help_says_which_commands_save() -> None:
    """The help: ``report`` and ``serve`` say they save the comparison they show and do
    not say nothing is written; ``diff`` and ``check`` offer ``--save``; ``ui`` says it builds the
    dashboard and offers ``--open``."""
    texts = {verb: cli(None, verb, "--help") for verb in ("report", "serve", "diff", "check", "ui")}
    for verb, r in texts.items():
        assert r.code == 0, (verb, r.err)
    for verb in ("report", "serve"):
        assert says(texts[verb].out, "save") and not says(texts[verb].out, "nothing is written"), (verb, texts[verb].out[:400])
    for verb in ("diff", "check"):
        assert "--save" in texts[verb].out, verb
    assert "--open" in texts["ui"].out and says(texts["ui"].out, "dashboard"), texts["ui"].out[:400]


# ---------- PF12.12 the format's documentation ----------

DOC = ROOT / "docs" / "artifact-format.md"


def _keys(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(str(key))
            found |= _keys(value)
    elif isinstance(node, list):
        for value in node:
            found |= _keys(value)
    return found


def _documented(text: str) -> set[str]:
    return set(re.findall(r"`([^`\n]+)`", text))


def _data_words(store: Path) -> set[str]:
    """The user's own names that a saved result uses as keys: the events (``by_event`` and the
    per-event statistic maps), the axes (every ``config``) and the tree's group labels. They are the
    data, not the format, so the format's documentation does not list them."""
    words: set[str] = set()
    for path in (store / ".poisson" / "artifacts").rglob("*.json"):
        if path.name not in ("comparison.json", "check.json"):
            continue
        result = json.loads(path.read_text(encoding="utf-8"))
        words |= set(result.get("by_event") or {})
        words |= {k for e in (result.get("by_event") or {}).values() for c in e["cells"] for k in c["config"]}
        words |= set(((result.get("tree") or {}).get("grouping") or {}).get("groups") or {})
    for manifest in store.glob("*/manifest.json"):
        words |= set(json.loads(manifest.read_text(encoding="utf-8")).get("axis_types") or {})
    return words


def test_pf12_12_the_format_doc_lists_every_file_key_column_and_metric_prove_writes(old_world: Any, stats_world: Any, sweep_world: Any) -> None:
    """``docs/artifact-format.md`` names, each in backticks, every file Prove writes under the format,
    every key at every depth of each of its JSON files, every table column and metric, and every schema
    string; nothing Prove writes is undocumented."""
    assert DOC.is_file(), DOC
    text = DOC.read_text(encoding="utf-8")
    named = _documented(text)
    written: dict[str, set[str]] = {}
    data: set[str] = set()
    for store in (_store(old_world), _store(stats_world), _store(sweep_world)):
        data |= _data_words(store)
        written.setdefault("store.json", set()).update(_keys(json.loads((store / ".poisson" / "store.json").read_text(encoding="utf-8"))))
        for path in (store / ".poisson" / "artifacts").rglob("*.json"):
            written.setdefault(path.name if path.parent.name != "charts" and "charts" not in path.parts else "chart data", set()).update(_keys(json.loads(path.read_text(encoding="utf-8"))))
        for path in (store / ".poisson" / "artifacts").rglob("conditions.parquet"):
            table = pq.read_table(path)
            written.setdefault("table columns", set()).update(table.column_names)
            written.setdefault("table metrics", set()).update(str(m) for m in table.column("metric").to_pylist())
            written.setdefault("table notes", set()).update(str(n) for n in table.column("note").to_pylist() if n is not None)
        for path in store.glob("*/events.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                written.setdefault("event kinds", set()).add(event["kind"])
                written.setdefault("event keys", set()).update(_keys(event))
    files = {"store.json", "artifact.json", "comparison.json", "check.json", "conditions.parquet", "events.jsonl", "manifest.json"}
    schemas = {"poisson.store/1", "poisson.artifact/1", "poisson.run-event/1", "poisson.table/1", "poisson-prove.comparison/1", "poisson-prove.check/1", "poisson-prove.chart/1"}
    charts = {"charts/heatmap-<event>.svg", "charts/differences-<event>.svg", "charts/limits-<event>.svg", "charts/<condition hash>/incidence-<event>.svg"}
    missing = {"files": sorted(files - named), "schemas": sorted(schemas - named), "charts": sorted(charts - named)}
    missing |= {where: sorted(keys - named - (data if where not in ("table metrics", "table notes", "event kinds") else set())) for where, keys in written.items()}
    assert not any(missing.values()), {k: v for k, v in missing.items() if v}


def test_pf12_12_the_format_doc_maps_each_kind_to_an_mlflow_run_and_a_wandb_run() -> None:
    """The format doc's export section: a table whose header names MLflow and W&B, with a row for the run record,
    its event log, a comparison, a check and a chart, each with a mapping in both columns."""
    assert DOC.is_file(), DOC
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in DOC.read_text(encoding="utf-8").splitlines() if line.strip().startswith("|")]
    headers = [i for i, row in enumerate(rows) if "MLflow" in row and "W&B" in row]
    assert headers, "no table names MLflow and W&B"
    header = rows[headers[0]]
    body = [row for row in rows[headers[0] + 2:] if len(row) == len(header)]
    m, w = header.index("MLflow"), header.index("W&B")
    for kind in ("run record", "events.jsonl", "comparison", "check", "chart"):
        found = [row for row in body if kind in row[0]]
        assert found and found[0][m] and found[0][w], (kind, body)
