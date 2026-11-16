"""0.4.0, prove#4: a stored note that ``sweep --note`` would have refused reads as no note.

``sweep`` trims a note and refuses one
that is then empty, over 200 characters, on more than one line, or holding a control character.
A manifest another writer made can hold such a ``note`` all the same. A reader takes it by the
rule ``sweep`` writes by: trimmed, and no note at all when ``sweep`` would have refused it, the
way a stored ``name`` that is unfit already reads as none. So no face prints a line break, a
tab or a terminal escape sequence a note carried in.

Every test here holds a store whose newest run, ``retry``, has an unfit ``note`` in its manifest
against the same store written with no note on ``retry``: each face of N4 to N9, in text and
under ``--json``, shows the one exactly as it shows the other.

| invariant | tests |
|---|---|
| U1 the manifest reads without a note | ``test_u1_*`` |
| U2 ``diff`` and ``check``, text, ``--json`` and the saved comparison (N4) | ``test_u2_*`` |
| U3 ``report``, a pair and one run (N5) | ``test_u3_*`` |
| U4 ``runs``, text and ``--json`` (N6) | ``test_u4_*`` |
| U5 ``inspect``, text and ``--json`` (N7) | ``test_u5_*`` |
| U6 the core's views and the dashboard's pages (N8) | ``test_u6_*`` |
| U7 the terminal app (N9) | ``test_u7_*`` |
| U8 a fit note stored with space round it reads trimmed | ``test_u8_*`` |
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_r031_note import (
    BASE_ID,
    BASE_NOTE,
    EVENT,
    PLAIN_ID,
    RETRY_ID,
    UNSET,
    _block_order,
    at,
    noted_store,
    ok_json,
    saved_comparison,
    view_document,
    visible_text,
)

from poisson_prove.store import Store

#: A word every unfit note below holds and nothing else Prove prints does.
MARK = "zqxmark"

STORED_UNFIT = {
    "201 characters": MARK + "n" * (201 - len(MARK)),
    "201 characters between spaces": "   " + MARK + "n" * (201 - len(MARK)) + "  ",
    "two lines": f"{MARK} one\ntwo",
    "a carriage return": f"{MARK} one\rtwo",
    "a tab": f"{MARK} tab\tinside",
    "a bell": f"{MARK} bell\x07 rung",
    "a line separator": f"{MARK} one two",
    "a paragraph separator": f"{MARK} one two",
    "a terminal escape sequence": f"\x1b[31m{MARK} in red\x1b[0m",
    "a one-character escape sequence": f"{MARK} \x9b31m in red",
}


@pytest.fixture(autouse=True)
def _empty_home_and_no_store_variables(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    monkeypatch.setenv("COLUMNS", "200")


@pytest.fixture(scope="module", params=list(STORED_UNFIT))
def unfit(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """``plain`` with no note, ``base`` with its note, ``retry`` with an unfit one."""
    return noted_store(tmp_path_factory.mktemp("unfit") / "store", retry_note=STORED_UNFIT[request.param])


@pytest.fixture(scope="module")
def unnoted(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The same three runs, ``retry`` written with no note at all."""
    return noted_store(tmp_path_factory.mktemp("unnoted") / "store", retry_note=UNSET)


def copied(store: Path, tmp_path: Path, name: str = "store") -> Path:
    dest = tmp_path / name / "store"
    shutil.copytree(store, dest)
    return dest


def clean(text: str) -> None:
    """Nothing of the unfit note is in ``text``: not its words, not an escape character."""
    assert MARK not in text, text[:600]
    assert "\x1b[31m" not in text and "\x9b" not in text and "\x07" not in text, repr(text[:600])


# ---------- U1 the manifest ----------


def test_u1_the_manifest_reads_without_a_note(unfit: Path) -> None:
    assert json.loads((unfit / RETRY_ID / "manifest.json").read_text(encoding="utf-8"))["note"]
    manifest = Store(unfit).manifest(RETRY_ID)
    assert manifest.note is None
    assert "note" not in manifest.to_dict()
    assert Store(unfit).manifest(BASE_ID).note == BASE_NOTE


# ---------- U2 diff and check (N4) ----------


@pytest.mark.parametrize("verb", ["diff", "check"])
def test_u2_the_verdict_block_has_no_line_for_an_unfit_note(verb: str, unfit: Path, unnoted: Path) -> None:
    r = at(unfit, verb, "base", "retry", "--event", EVENT[verb])
    assert r.code in (0, 4), r
    clean(r.out + r.err)
    block = _block_order(r.out)
    assert block[block.index("  before  base") + 1] == f"  before note  {BASE_NOTE}", block
    assert not any(line.startswith("  after note") for line in block), block
    same = at(unnoted, verb, "base", "retry", "--event", EVENT[verb])
    assert (r.code, r.out) == (same.code, same.out)


@pytest.mark.parametrize("verb", ["diff", "check"])
def test_u2_json_has_no_key_for_an_unfit_note(verb: str, unfit: Path, unnoted: Path) -> None:
    r = at(unfit, verb, "base", "retry", "--event", EVENT[verb], "--json")
    clean(r.out + r.err)
    doc = ok_json(r)
    assert doc["note_a"] == BASE_NOTE and "note_b" not in doc
    assert doc == ok_json(at(unnoted, verb, "base", "retry", "--event", EVENT[verb], "--json"))
    doc = ok_json(at(unfit, verb, "retry", "base", "--event", EVENT[verb], "--json"))
    assert "note_a" not in doc and doc["note_b"] == BASE_NOTE


def test_u2_the_saved_comparison_has_no_key_for_an_unfit_note(unfit: Path, tmp_path: Path) -> None:
    store = copied(unfit, tmp_path)
    doc = ok_json(at(store, "diff", "base", "retry", "--event", "violated", "--save", "--json"))
    text = (store / doc["saved"] / "comparison.json").read_text(encoding="utf-8")
    clean(text)
    result = json.loads(text)
    assert result["note_a"] == BASE_NOTE and "note_b" not in result


# ---------- U3 report (N5) ----------


def test_u3_a_pair_report_has_no_line_for_an_unfit_note(unfit: Path, tmp_path: Path) -> None:
    store = copied(unfit, tmp_path)
    out = tmp_path / "out"
    r = at(store, "report", "base", "retry", "--x", "cell", "--event", "violated", "--out", out)
    assert r.code == 0, r
    clean(r.out + r.err)
    report = (out / "report.md").read_text(encoding="utf-8")
    clean(report)
    lines = report.splitlines()
    assert f"before note  {BASE_NOTE}" in lines
    assert not any(line.startswith("after note") for line in lines), lines[:12]
    receipt = (out / "receipt.html").read_text(encoding="utf-8")
    clean(receipt)
    assert BASE_NOTE in visible_text(receipt)


def test_u3_a_pair_reports_json_has_no_key_for_an_unfit_note(unfit: Path, tmp_path: Path) -> None:
    store = copied(unfit, tmp_path)
    r = at(store, "report", "base", "retry", "--x", "cell", "--event", "violated", "--out", tmp_path / "out", "--json")
    clean(r.out + r.err)
    doc = ok_json(r)
    assert doc["note_a"] == BASE_NOTE and "note_b" not in doc


def test_u3_a_one_run_report_has_no_line_for_an_unfit_note(unfit: Path, tmp_path: Path) -> None:
    store = copied(unfit, tmp_path)
    out = tmp_path / "out"
    r = at(store, "report", "retry", "--x", "cell", "--event", "violated", "--out", out)
    assert r.code == 0, r
    clean(r.out + r.err)
    report = (out / "report.md").read_text(encoding="utf-8")
    clean(report)
    assert not any(line.startswith("note  ") for line in report.splitlines())
    clean((out / "receipt.html").read_text(encoding="utf-8"))
    r = at(store, "report", "retry", "--x", "cell", "--event", "violated", "--out", tmp_path / "out2", "--json")
    clean(r.out + r.err)
    assert "note" not in ok_json(r)


# ---------- U4 runs (N6) ----------


def test_u4_runs_shows_a_dash_for_an_unfit_note(unfit: Path, unnoted: Path) -> None:
    r = at(unfit, "--plain", "runs")
    assert r.code == 0, r
    clean(r.out + r.err)
    lines = r.out.splitlines()
    header = next(line for line in lines if line.startswith("#  name"))
    assert header.rstrip().endswith("note"), header
    rows = {name: next(line for line in lines if re.match(rf"^(\d+|-)?\s+{name}\s", line)) for name in ("base", "retry")}
    assert rows["base"].rstrip().endswith(BASE_NOTE)
    assert rows["retry"].rstrip().endswith("-")
    # The first line names the store's folder: the two listings are compared with it taken out.
    assert r.out.replace(str(unfit), "STORE") == at(unnoted, "--plain", "runs").out.replace(str(unnoted), "STORE")


def test_u4_runs_has_no_note_column_when_the_only_note_is_unfit(unfit: Path, tmp_path: Path) -> None:
    stored = json.loads((unfit / RETRY_ID / "manifest.json").read_text(encoding="utf-8"))["note"]
    store = noted_store(tmp_path / "store", base_note=UNSET, retry_note=stored)
    r = at(store, "--plain", "runs")
    assert r.code == 0, r
    clean(r.out + r.err)
    header = next(line for line in r.out.splitlines() if line.startswith("#  name"))
    assert header.rstrip().endswith("created"), header
    assert "note" not in header


def test_u4_runs_json_has_no_key_for_an_unfit_note(unfit: Path, unnoted: Path) -> None:
    r = at(unfit, "runs", "--json")
    clean(r.out + r.err)
    by_id = {entry["run_id"]: entry for entry in ok_json(r)["runs"]}
    assert by_id[BASE_ID]["note"] == BASE_NOTE
    assert "note" not in by_id[RETRY_ID] and "note" not in by_id[PLAIN_ID]
    same = {entry["run_id"]: entry for entry in ok_json(at(unnoted, "runs", "--json"))["runs"]}
    assert by_id[RETRY_ID] == same[RETRY_ID]


# ---------- U5 inspect (N7) ----------


def test_u5_inspect_has_no_line_for_an_unfit_note(unfit: Path, unnoted: Path) -> None:
    r = at(unfit, "inspect", "retry", "--event", "violated", "--limit", "1")
    assert r.code == 0, r
    clean(r.out + r.err)
    assert not any(line.startswith("  note  ") for line in r.out.splitlines())
    assert r.out == at(unnoted, "inspect", "retry", "--event", "violated", "--limit", "1").out


def test_u5_inspect_json_has_no_key_for_an_unfit_note(unfit: Path, unnoted: Path) -> None:
    r = at(unfit, "inspect", "retry", "--event", "violated", "--limit", "1", "--json")
    clean(r.out + r.err)
    doc = ok_json(r)
    assert "note" not in doc
    assert doc == ok_json(at(unnoted, "inspect", "retry", "--event", "violated", "--limit", "1", "--json"))


# ---------- U6 the core's views and the dashboard (N8) ----------


def test_u6_the_runs_and_run_views_have_no_key_for_an_unfit_note(unfit: Path, tmp_path: Path) -> None:
    store = copied(unfit, tmp_path)
    runs = {r["run_id"]: r for r in view_document(store, "index.html")["runs"]}
    assert runs[BASE_ID]["note"] == BASE_NOTE and "note" not in runs[RETRY_ID]
    run = view_document(store, f"runs/{RETRY_ID}.html")
    assert "note" not in run
    clean(json.dumps(run, ensure_ascii=False))


def test_u6_the_comparison_view_has_no_key_for_an_unfit_note(unfit: Path, tmp_path: Path) -> None:
    store = copied(unfit, tmp_path)
    doc = view_document(store, f"comparisons/{saved_comparison(store)}.html")
    assert doc["before"]["note"] == BASE_NOTE and "note" not in doc["after"]
    clean(json.dumps(doc, ensure_ascii=False))


def test_u6_no_page_of_the_dashboard_shows_an_unfit_note(unfit: Path, tmp_path: Path) -> None:
    store = copied(unfit, tmp_path)
    cid = saved_comparison(store)
    r = at(store, "ui")
    assert r.code == 0, r
    ui = store / ".poisson" / "ui"
    pages = (ui / "index.html", ui / "runs" / f"{RETRY_ID}.html", ui / "comparisons" / f"{cid}.html")
    for page in pages:
        clean(page.read_text(encoding="utf-8"))
    assert BASE_NOTE in visible_text(pages[2].read_text(encoding="utf-8"))
    for page in sorted(ui.rglob("*")):
        if page.is_file() and page.suffix in (".html", ".json", ".js"):
            clean(page.read_text(encoding="utf-8"))


# ---------- U7 the terminal app (N9) ----------


BIG = (160, 60)


def test_u7_the_apps_run_screen_shows_no_unfit_note(unfit: Path, unnoted: Path, tmp_path: Path) -> None:
    pytest.importorskip("textual")
    from pf6_support import drive, says

    async def scenario(s: Any) -> str:
        await s.wait_title("home")
        await s.press("r")
        await s.wait_title("runs")
        await s.focus_row(lambda row: " retry " in f" {row} ")
        await s.press("enter")
        await s.wait_title("run")
        return str(await s.read_through())

    store = copied(unfit, tmp_path)
    _, text = drive(scenario, cwd=store.parent, store=store.name, size=BIG)
    clean(text)
    assert not says(text, MARK), text[:1500]
    twin = copied(unnoted, tmp_path, "unnoted")
    _, same = drive(scenario, cwd=twin.parent, store=twin.name, size=BIG)
    assert text == same


def test_u7_the_apps_verdict_screen_shows_no_unfit_note(unfit: Path, tmp_path: Path) -> None:
    pytest.importorskip("textual")
    from pf6_support import drive, says

    async def scenario(s: Any) -> str:
        await s.wait_title("home")
        await s.press("c")
        await s.wait_title("compare")
        await s.press("enter")
        await s.wait(lambda g: g.header.startswith("poisson-prove · comparison") and says(g.text(), "fragility"), what="the verdict")
        await s.settle()
        return str(await s.read_through())

    store = copied(unfit, tmp_path)
    _, text = drive(scenario, cwd=store.parent, store=store.name, size=BIG)
    clean(text)
    assert not says(text, MARK), text[:1500]
    labels = [m.group(1) for m in re.finditer(r"^\s+(before note|after note|before|after)\s{2,}\S", text, re.M)]
    assert labels[:3] == ["before", "before note", "after"] and "after note" not in labels, text[:2000]
    assert says(text, BASE_NOTE), text[:1500]


# ---------- U8 a fit note stored with space round it ----------


def test_u8_a_fit_note_stored_with_space_round_it_reads_trimmed(tmp_path: Path) -> None:
    """``sweep`` trims before it stores, so a reader trims too: the line break another writer
    left at a note's end is not shown, and the note is."""
    store = noted_store(tmp_path / "store", retry_note="  retry each call once \n")
    assert Store(store).manifest(RETRY_ID).note == "retry each call once"
    r = at(store, "diff", "base", "retry", "--event", "violated")
    assert r.code in (0, 4), r
    block = _block_order(r.out)
    assert block[block.index("  after  retry") + 1] == "  after note  retry each call once", block
    assert ok_json(at(store, "diff", "base", "retry", "--event", "violated", "--json"))["note_b"] == "retry each call once"
    longest = noted_store(tmp_path / "longest", retry_note=" " + "n" * 200 + " ")
    assert Store(longest).manifest(RETRY_ID).note == "n" * 200
