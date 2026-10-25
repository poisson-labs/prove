"""PF4, completeness: the frozen tests of what a user reads, and the contract tests (the code suite).

Written from the front-door spec's section 8 (8.2 to 8.5, 8.10) and its invariants PF4.1b to PF4.51
as they are read on a screen or in a file: ``diff``, ``check``, ``report`` and ``serve`` (text and
``--json``), ``report.md``, ``receipt.html``, the page and its Summary, ``paired``, ``sweep``'s plan,
and what a sweep records. PF4 Session A froze PF4.1 to PF4.21 (2026-10-20); the statistics re-freeze of
2026-10-24 adds PF4.22 to PF4.51 and moves what Taylor's rulings of that day on Argon's methodology
review change. ``tests/test_pf4_stats.py`` holds the numbers underneath (the math suite) and
``tests/test_pf4_calibration.py`` the simulations. The build is written against this file and does
not edit it.

**What this file can rely on.** PF4 is built on ``main`` with PF0 to PF3 and PF9 merged: run names
(PF2), the paired default and the method lines (PF3). These tests name runs by id, always pass
``--method`` unless the default is the point, and read the verdict word from ``--json`` and from the
first stdout line. Each surface is reached through the command line in process, with ``HOME`` pointed
at an empty folder.

**Readings, named here** (each is a yes/no in the re-freeze's log, ``log/pf4/refreeze.md``).

- Session A's, ruled 2026-10-24: the comparison's word is ``verdict`` in ``diff --json``,
  ``comparison_verdict`` in ``report --json``, ``summary.verdict`` on the page, and ``report.md``'s
  first line after the title; ``diff --json`` carries ``threshold`` and ``threshold_source``
  (``recorded``, ``smaller``, ``default``); a kind is ``--event NAME:failure|success`` or the
  declaration's ``failures``/``successes``; the single-run ``report --json`` carries ``by_event`` with
  each cell's ``config``, ``share``, ``incidence`` and ``share_differs``, and ``design_mde``;
  ``poisson_prove.stats.WILSON_LEVEL`` is read when a surface computes; PF4.11's "any ``--json``" is
  every comparing verb's, ``runs``', ``paired``'s and ``sweep``'s, and ``inspect`` keeps the import
  path; ``check`` prints no cell table.
- Re-freeze readings: shares count by the common horizon and the single-run report's by the
  horizon it reads, so no share differs from its rate in a store 0.1.0 writes (R3, R4); the verdict
  block's detail lines are found by their label, ``  <label>  `` (``method``, ``comparison`` on
  ``check``, ``threshold``, ``before``, ``after``, ``trade``, ``verdict rule``, ``flagged only``, ``fragility``, ``peeking``, ``errors``,
  ``competing``), and a text surface's line is pinned only by its facts: the number, the run's name,
  the binding words of the spec (PF4.35, PF4.41, PF4.42, PF4.45: ``Benjamini``, ``Hochberg``, ``Holm``,
  ``false discovery rate``, ``family-wise``, ``cause-specific hazard``, ``peeking``, ``errored``,
  ``fragility``, ``unconditional``, ``Miettinen-Nurminen``, ``Tango``, ``simultaneous``, ``Bonferroni``,
  ``false coverage``, ``Benjamini-Yekutieli``), matched without regard to case, hyphens or dashes
  (``_says``, reading R30); the page carries the same facts in ``summary`` (``verdict``,
  ``verdict_limit``, ``fragility``, ``peeking``, ``errors_differ``) and each panel's ``flag_rule``;
  the read record is ``~/.cache/poisson-prove/compared.jsonl`` (R6); a case id is
  ``Episode.meta["case_id"]``, which the store copies into its ``case_id`` column (R5); ``--max-mde 1`` admits any design (R17); PF4.32's patched constant
  is ``poisson_prove.stats.POWER``, read when a surface computes, as ``WILSON_LEVEL`` is.

**Lanes.** The code suite. The tests that sweep take a few seconds each; the gate's paired design at
194 replicates sweeps 1,746 rollouts and is marked ``slow``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
import warnings
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from poisson_prove import cli
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash

import lattice
from test_pf4_stats import _ref_fisher_limits
from conftest import writable_copy

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
# PF12 (spec section 18.2, Q59): report and serve save into the store they read, so these tests read a
# per-process copy of the committed fixture (conftest.writable_copy); the committed folder is never written.
OLD = writable_copy(TESTS / "fixtures" / "stores-0.0.1")
OLD_RUNS: dict[str, str] = json.loads((OLD / "runs.json").read_text(encoding="utf-8"))

A_ID = "20261020T100000Z-aaaa"
B_ID = "20261020T100100Z-bbbb"
SALT = "pf4-shared-salt"
HORIZON = 10.0
Q = 0.05
#: Rule 3's verdict line: a lowercase word or phrase, two spaces, then the sentence.
FIRST_LINE = re.compile(r"^([a-z][a-z ]*?)  \S")
JUDGEMENT = re.compile(r"\b(safer|worse)\b", re.IGNORECASE)
KNOWN_WORDS = {"trade", "worse", "safer", "too small to tell", "no significant change"}
DIRECTION_WORDS = {"mixed", "higher", "lower", "too small to tell", "no significant change"}
NOTES = {"no room", "none detectable", "cannot be flagged", "no matched pairs"}


# ---------- the command line, in process ----------


@dataclass
class Result:
    code: int
    out: str
    err: str


@pytest.fixture(autouse=True)
def _empty_home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[-\u2010-\u2015]", " ", text.lower()).split())


def _says(text: str, words: str) -> bool:
    """A binding phrase, whatever its case and whichever hyphen or dash joins its words (reading R30)."""
    return _norm(words) in _norm(text)


def _cli(root: Path | str, *argv: str) -> Result:
    """The command line with ``--store`` as given: a ``Path`` is passed whole, a ``str`` as typed."""
    out, err = StringIO(), StringIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        code = cli.main(["--store", str(root), *argv], stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def _json(result: Result) -> dict[str, Any]:
    assert result.code in (0, 4), (result.code, result.err)
    doc = json.loads(result.out)
    assert isinstance(doc, dict)
    return doc


def _first_word(text: str) -> str:
    first = text.splitlines()[0] if text else ""
    m = FIRST_LINE.match(first)
    assert m, first
    return m.group(1)


def _block(text: str) -> list[str]:
    """The verdict block: the verdict line and its detail lines, up to the first blank line."""
    return text.split("\n\n", 1)[0].splitlines()


def _detail(text: str, label: str) -> list[str]:
    """The values of a verdict block's detail lines with this label."""
    prefix = f"  {label}  "
    return [line[len(prefix):] for line in _block(text) if line.startswith(prefix)]


def _strings(node: Any) -> list[str]:
    """Every string value in a JSON document, keys left out."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in _strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in _strings(value)]
    return []


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _page_text(page: dict[str, Any]) -> str:
    from poisson_prove.viewer import render_html

    return _strip_tags(render_html({k: v for k, v in page.items() if k not in ("verdict", "sentence", "next", "method", "method_chosen")}))


# ---------- stores, built by hand ----------


def _arm(k: int, n: int, *, start: float = 1.0, step: float = 0.1, event: str = "fell") -> list[tuple[int, str | None, float]]:
    """``n`` runs of which the first ``k`` ended in ``event``, at ``start``, ``start + step``, ...; the
    rest end ``ok`` at the horizon."""
    return [(i, event, start + step * i) if i < k else (i, "ok", HORIZON) for i in range(n)]


def _write_run(
    root: Path,
    run_id: str,
    cells: dict[str, list[tuple[int, str | None, float]]],
    *,
    salt: str = SALT,
    environment: dict[str, Any] | None = None,
    declared: dict[str, Any] | None = None,
    created_at: str = "2026-10-20T10:00:00Z",
    horizon: float = HORIZON,
    meta: dict[str, dict[str, Any]] | None = None,
    complete: bool = True,
) -> None:
    store = Store(root)
    store.create_run(
        RunManifest(
            run_id=run_id,
            target_id="pf4-target",
            t_unit="steps",
            run_salt=salt,
            axis_types={"cell": "categorical"},
            backend="local",
            environment={"max_mde_accepted": 0.2} if environment is None else dict(environment),
            created_at=created_at,
        )
    )
    records = []
    for name, rows in cells.items():
        for rep, outcome, t in rows:
            common = dict(run_id=run_id, config_hash=config_hash({"cell": name}), config={"cell": name}, seed=1000 + rep,
                          replicate_index=rep, t=t, horizon=horizon, confidence=None,
                          meta=dict((meta or {}).get(name, {})), wall_time=0.01, backend_meta={})
            if outcome is None:
                records.append(EpisodeRecord(outcome=None, error="ValueError: the rollout raised",
                                             **{**common, "t": None, "horizon": None}))
            else:
                records.append(EpisodeRecord(outcome=outcome, error=None, **common))
    store.append(run_id, records)
    if complete:
        store.mark_complete(run_id)
    if declared is not None:
        path = root / run_id / "manifest.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["declared"] = {"steps": [], "gates": [], **declared}
        path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")


def _pair(
    root: Path,
    a: dict[str, list[tuple[int, str | None, float]]],
    b: dict[str, list[tuple[int, str | None, float]]],
    **kw: Any,
) -> Path:
    env_a = kw.pop("environment_a", None)
    env_b = kw.pop("environment_b", None)
    decl_a = kw.pop("declared_a", None)
    decl_b = kw.pop("declared_b", None)
    meta_a = kw.pop("meta_a", None)
    meta_b = kw.pop("meta_b", None)
    _write_run(root, A_ID, a, environment=env_a, declared=decl_a, meta=meta_a, created_at="2026-10-20T10:00:00Z", **kw)
    _write_run(root, B_ID, b, environment=env_b, declared=decl_b, meta=meta_b, created_at="2026-10-20T10:01:00Z", **kw)
    return root


#: Six conditions, 40 runs an arm: one whose rate rose significantly ("up"), one where it fell
#: ("down"), one unchanged, one whose baseline fell in every run, one at 38 of 40 where no rise is
#: detectable, and one at zero.
STANDARD_A = {
    "up": _arm(4, 40), "down": _arm(30, 40), "same": _arm(10, 40),
    "top": _arm(40, 40), "near_top": _arm(38, 40), "zero": _arm(0, 40),
}
STANDARD_B = {
    "up": _arm(30, 40), "down": _arm(4, 40), "same": _arm(10, 40),
    "top": _arm(40, 40), "near_top": _arm(38, 40), "zero": _arm(0, 40),
}


@pytest.fixture(scope="module")
def standard(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _pair(tmp_path_factory.mktemp("standard") / "prove-runs", STANDARD_A, STANDARD_B)


def _hash(name: str) -> str:
    return config_hash({"cell": name})


def _cells_of(doc: dict[str, Any], event: str = "fell") -> dict[str, dict[str, Any]]:
    cells = doc["by_event"][event]["cells"]
    return {str(c["config_hash"]): c for c in cells}


def _row(text: str, name: str) -> str:
    """The one text line of a cell table that carries this condition's short hash."""
    short = _hash(name)[:12]
    lines = [line for line in text.splitlines() if short in line and line.startswith("|")]
    assert len(lines) >= 1, (name, short)
    return lines[0]


def _column(text: str, name: str, column: str) -> str:
    """One cell of a text cell table: the row carrying this condition's short hash, the column
    found by the nearest header above it whose name starts with ``column``."""
    lines = text.splitlines()
    short = _hash(name)[:12]
    for i, line in enumerate(lines):
        if short in line and line.startswith("|"):
            for header in reversed(lines[:i]):
                if header.startswith("| config_hash"):
                    names = [h.strip() for h in header.strip("|").split("|")]
                    values = [v.strip() for v in line.strip("|").split("|")]
                    (index,) = [j for j, h in enumerate(names) if h == column or h.startswith(column + " ")]
                    return values[index]
    raise AssertionError((name, column))


def _statsmodels_wilson(k: int, n: int, level: float) -> tuple[float, float]:
    """statsmodels documents ``proportion_confint(count, nobs, alpha, method="wilson")``; the level
    is ``1 - alpha``."""
    from statsmodels.stats.proportion import proportion_confint

    lo, hi = proportion_confint(k, n, alpha=1.0 - level, method="wilson")
    return float(lo), float(hi)


def _assert_share(obj: Any, k: int, n: int, level: float = 0.95) -> None:
    assert isinstance(obj, dict), obj
    assert set(obj) >= {"value", "lo", "hi", "level", "method"}, sorted(obj)
    assert obj["method"] == "wilson"
    assert obj["level"] == level
    assert abs(obj["value"] - k / n) <= 1e-12
    lo, hi = _statsmodels_wilson(k, n, level)
    assert abs(obj["lo"] - lo) <= 1e-12, (obj, lo)
    assert abs(obj["hi"] - hi) <= 1e-12, (obj, hi)


def _interval_text(k: int, n: int, level: float = 0.95) -> str:
    lo, hi = _statsmodels_wilson(k, n, level)
    return f"{k / n:.3f} [{lo:.3f}, {hi:.3f}]"


def _surfaces(root: Path, tmp: Path, *event_args: str, method: str = "fisher_bh") -> dict[str, Any]:
    """Every surface that shows a comparison's verdict, for one pair: text and JSON of diff and
    check (``--fail-on any``, which needs no kind), the written report.md and receipt.html, the page
    and its structure."""
    ev = [a for e in event_args for a in ("--event", e)]
    out = tmp / f"r-{uuid.uuid4().hex[:8]}"
    report = _cli(root, "report", A_ID, B_ID, *ev, "--method", method, "--x", "cell", "--out", str(out))
    assert report.code == 0, report.err
    page = _json(_cli(root, "serve", A_ID, B_ID, *ev, "--method", method, "--x", "cell", "--json"))
    return {
        "diff": _cli(root, "diff", A_ID, B_ID, *ev, "--method", method),
        "diff --json": _json(_cli(root, "diff", A_ID, B_ID, *ev, "--method", method, "--json")),
        "check": _cli(root, "check", A_ID, B_ID, *ev, "--method", method, "--fail-on", "any"),
        "check --json": _json(_cli(root, "check", A_ID, B_ID, *ev, "--method", method, "--fail-on", "any", "--json")),
        "report --json": _json(_cli(root, "report", A_ID, B_ID, *ev, "--method", method, "--x", "cell",
                                    "--out", str(tmp / f"j-{uuid.uuid4().hex[:8]}"), "--json")),
        "report.md": (out / "report.md").read_text(encoding="utf-8"),
        "receipt.html": _strip_tags((out / "receipt.html").read_text(encoding="utf-8")),
        "page": page,
        "page text": _page_text(page),
    }


def _texts(s: dict[str, Any]) -> dict[str, str]:
    return {"diff": s["diff"].out, "check": s["check"].out, "report.md": s["report.md"], "receipt.html": s["receipt.html"],
            "page": s["page text"]}


# ---------- PF4.1b: every saved Wilson interval records its level ----------


def test_pf4_1b_diff_json_carries_both_arms_shares_with_their_level(standard: Path) -> None:
    doc = _json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    cells = _cells_of(doc)
    assert len(cells) == 6
    for name in STANDARD_A:
        c = cells[_hash(name)]
        _assert_share(c["share_a"], sum(o == "fell" for _, o, _ in STANDARD_A[name]), 40)
        _assert_share(c["share_b"], sum(o == "fell" for _, o, _ in STANDARD_B[name]), 40)


def test_pf4_1b_check_json_carries_the_same_shares(standard: Path) -> None:
    doc = _json(_cli(standard, "check", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh", "--json"))
    cells = _cells_of(doc)
    assert len(cells) == 6
    for c in cells.values():
        _assert_share(c["share_a"], int(c["events_a"]), int(c["n_a"]))
        _assert_share(c["share_b"], int(c["events_b"]), int(c["n_b"]))


def test_pf4_1b_the_two_run_report_json_carries_the_shares(standard: Path, tmp_path: Path) -> None:
    doc = _json(_cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh",
                     "--x", "cell", "--out", str(tmp_path / "r"), "--json"))
    cells = _cells_of(doc)
    assert len(cells) == 6
    for c in cells.values():
        _assert_share(c["share_a"], int(c["events_a"]), int(c["n_a"]))
        _assert_share(c["share_b"], int(c["events_b"]), int(c["n_b"]))


def test_pf4_1b_the_page_structure_carries_the_shares(standard: Path) -> None:
    doc = _json(_cli(standard, "serve", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh",
                     "--x", "cell", "--json"))
    (panel,) = doc["panels"]
    assert len(panel["cells"]) == 6
    for c in panel["cells"]:
        _assert_share(c["share_a"], int(c["events_a"]), int(c["n_a"]))
        _assert_share(c["share_b"], int(c["events_b"]), int(c["n_b"]))


def test_pf4_1b_the_single_run_report_json_carries_each_conditions_share(standard: Path, tmp_path: Path) -> None:
    doc = _json(_cli(standard, "report", A_ID, "--event", "fell", "--x", "cell",
                     "--out", str(tmp_path / "r"), "--json"))
    cells = doc["by_event"]["fell"]["cells"]
    assert len(cells) == 6
    for c in cells:
        name = c["config"]["cell"]
        k = sum(1 for _, o, _ in STANDARD_A[name] if o == "fell")
        _assert_share(c["share"], k, len(STANDARD_A[name]))


def test_pf4_1b_no_saved_wilson_interval_lacks_a_level(standard: Path, tmp_path: Path) -> None:
    """Every object anywhere in the four documents that has a Wilson ``method`` has a ``level``."""
    docs = [
        _json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json")),
        _json(_cli(standard, "serve", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--json")),
        _json(_cli(standard, "report", A_ID, "--event", "fell", "--x", "cell", "--out", str(tmp_path / "s"), "--json")),
        _json(_cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
                   "--out", str(tmp_path / "p"), "--json")),
    ]
    found = 0

    def walk(node: Any) -> None:
        nonlocal found
        if isinstance(node, dict):
            if node.get("method") == "wilson":
                found += 1
                assert isinstance(node.get("level"), float) and 0 < node["level"] < 1, node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for doc in docs:
        walk(doc)
    assert found >= 6 * 2 * 3 + 6

    def flat(node: Any) -> None:
        if isinstance(node, dict):
            if "event_rate_lo" in node:
                assert "event_rate_level" in node, sorted(node)
            assert not any(re.fullmatch(r"share_[ab]_(lo|hi)", str(k)) for k in node), sorted(node)
            for value in node.values():
                flat(value)
        elif isinstance(node, list):
            for value in node:
                flat(value)

    for doc in docs:
        flat(doc)


# ---------- PF4.1c: every label comes from the recorded level ----------


def test_pf4_1c_with_the_level_patched_to_90_every_surface_says_90_and_none_95(
    standard: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import poisson_prove.stats as stats_module
    from poisson_prove.viewer import render_html

    monkeypatch.setattr(stats_module, "WILSON_LEVEL", 0.90)
    single = _cli(standard, "report", A_ID, "--event", "fell", "--x", "cell", "--out", str(tmp_path / "single"))
    assert single.code == 0, single.err
    two = _cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
               "--out", str(tmp_path / "two"))
    assert two.code == 0, two.err
    diff_text = _cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh")
    assert diff_text.code == 0, diff_text.err
    check_text = _cli(standard, "check", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh")
    page = _json(_cli(standard, "serve", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--json"))
    structure = {k: v for k, v in page.items() if k not in ("verdict", "sentence", "next")}
    html = render_html(structure)
    surfaces = {
        "single report.md": (tmp_path / "single" / "report.md").read_text(encoding="utf-8"),
        "single receipt.html": _strip_tags((tmp_path / "single" / "receipt.html").read_text(encoding="utf-8")),
        "two report.md": (tmp_path / "two" / "report.md").read_text(encoding="utf-8"),
        "two receipt.html": _strip_tags((tmp_path / "two" / "receipt.html").read_text(encoding="utf-8")),
        "diff": diff_text.out,
        "page": _strip_tags(html),
        "page structure": json.dumps(page["panels"]),
    }
    for name, text in surfaces.items():
        assert "90%" in text, name
        assert "95%" not in text, name
    assert "95%" not in check_text.out + check_text.err
    for c in page["panels"][0]["cells"]:
        assert c["share_a"]["level"] == 0.90 and c["share_b"]["level"] == 0.90
    assert "95%" not in json.dumps(page["summary"])


def test_pf4_1c_the_rendering_code_holds_no_95_percent_and_no_1_96() -> None:
    """The label is built from the recorded level and the quantile from the level; neither is
    typed into a renderer. Passes on today's code, which prints no Wilson label at all; it fails a
    build that hard-codes either."""
    package = SRC / "poisson_prove"
    files = [package / f"{name}.py" for name in ("report", "viewer", "plain", "cli", "_look")]
    # PF5 (spec section 17): the core is a package now, so the scan reads src/ recursively.
    files += [path for path in sorted(package.rglob("*.py"))
              if path not in files and re.search(r"^\s*(import|from) rich\b", path.read_text(encoding="utf-8"), re.M)]
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "95%" not in text, path.name
        assert not re.search(r"(?<![\d.])1\.96(?!\d)", text), path.name


# ---------- PF4.2 and PF4.37: shares on the window the tests read ----------


def test_pf4_2_the_single_run_report_prints_each_share_with_its_interval_and_the_incidence(
    standard: Path, tmp_path: Path
) -> None:
    result = _cli(standard, "report", A_ID, "--event", "fell", "--x", "cell", "--out", str(tmp_path / "r"))
    assert result.code == 0, result.err
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert "95%" in md and "Wilson" in md and "incidence" in md
    for name, rows in STANDARD_A.items():
        k = sum(1 for _, o, _ in rows if o == "fell")
        assert _interval_text(k, len(rows)) in md, name


def test_pf4_37_the_single_run_reports_share_counts_by_the_horizon_it_reads(standard: Path, tmp_path: Path) -> None:
    """Reading R3, which reverses PF4 Session A's yes/no 10 here too: at ``--horizon 2`` a condition's
    share counts the falls by step 2, as its incidence does, so the two agree and nothing is marked."""
    doc = _json(_cli(standard, "report", A_ID, "--event", "fell", "--x", "cell", "--horizon", "2",
                     "--out", str(tmp_path / "r"), "--json"))
    cells = {c["config"]["cell"]: c for c in doc["by_event"]["fell"]["cells"]}
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    for name, rows in STANDARD_A.items():
        by_two = sum(1 for _, o, t in rows if o == "fell" and t <= 2.0)
        c = cells[name]
        _assert_share(c["share"], by_two, 40)
        assert c["share_differs"] is False, name
        assert abs(c["incidence"] - by_two / 40) <= 1e-12, (name, c["incidence"])
        lines = [line for line in md.splitlines() if _interval_text(by_two, 40) in line and name in line]
        assert lines and "*" not in lines[0], (name, lines[:1])


def test_pf4_37_a_two_run_share_counts_by_the_common_horizon_and_is_never_marked(tmp_path: Path) -> None:
    """A ran to step 10 and B to step 5, so the comparison's horizon is 5. In 'late' half of A's runs fell
    after step 5: by then A had none, so its share is 0 of 40, the rate the test compares, and no mark.
    PF4 Session A's W17 counted the stored outcomes here (0.500); ruling 2 of 2026-10-24 reverses it."""
    root = tmp_path / "prove-runs"
    a = {"late": [(i, "fell", 6.0 + 0.1 * i) if i < 20 else (i, "ok", 10.0) for i in range(40)],
         "early": [(i, "fell", 1.0 + 0.1 * i) if i < 20 else (i, "ok", 10.0) for i in range(40)]}
    b = {"late": [(i, "ok", 5.0) for i in range(40)],
         "early": [(i, "fell", 1.0 + 0.1 * i) if i < 20 else (i, "ok", 5.0) for i in range(40)]}
    _write_run(root, A_ID, a, created_at="2026-10-20T10:00:00Z")
    _write_run(root, B_ID, b, created_at="2026-10-20T10:01:00Z", horizon=5.0)
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    cells = _cells_of(doc)
    late, early = cells[_hash("late")], cells[_hash("early")]
    assert late["rate_a"] == 0.0 and late["events_a"] == 0
    _assert_share(late["share_a"], 0, 40)
    _assert_share(early["share_a"], 20, 40)
    for c in (late, early):
        assert c["share_a_differs"] is False and c["share_b_differs"] is False
    text = _cli(root, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh").out
    assert "*" not in _row(text, "late") and "*" not in _row(text, "early")


# ---------- PF4.3: per-arm shares beside the rates ----------


def test_pf4_3_diffs_text_table_prints_both_shares_beside_the_rates_labelled_by_the_level(standard: Path) -> None:
    result = _cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh")
    assert result.code == 0, result.err
    assert "95%" in result.out
    for name in STANDARD_A:
        row = _row(result.out, name)
        ka = sum(1 for _, o, _ in STANDARD_A[name] if o == "fell")
        kb = sum(1 for _, o, _ in STANDARD_B[name] if o == "fell")
        assert _interval_text(ka, 40) in row, (name, row)
        assert _interval_text(kb, 40) in row, (name, row)


def test_pf4_3_the_two_run_report_prints_the_shares_and_the_caption_says_they_are_not_adjusted(standard: Path, tmp_path: Path) -> None:
    diff_text = _cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh").out
    result = _cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
                  "--out", str(tmp_path / "r"))
    assert result.code == 0, result.err
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert _interval_text(30, 40) in md and _interval_text(4, 40) in md and "95%" in md
    for text in (diff_text, md):
        assert "not adjusted" in text


# ---------- PF4.4 and PF4.30: the design's limit, recorded and printed ----------


def _ref_gate(n: int, rows: int, threshold: float) -> tuple[float, str, float]:
    """The gate's worst base rate on a 0.005 grid among those with room for the threshold, the way the
    change goes there, and the limit that way at that base rate (Fisher, level q / rows), from the
    stats file's references."""
    import numpy as np

    from test_pf4_stats import _ref_fisher_power, _ref_limit

    level = Q / rows
    worst = (2.0, 0.0, "rise")
    for base in np.round(np.arange(0.0, 1.0 + 1e-9, 0.005), 3):
        for way in ("rise", "fall"):
            if (way == "rise" and base > 1 - threshold + 1e-9) or (way == "fall" and base < threshold - 1e-9):
                continue
            power = float(_ref_fisher_power(float(base), n, n, level, np.array([threshold]), way == "rise")[0])
            # Ties (within 1e-12) go to the lower base rate, a rise before a fall (PF4.30).
            if power < worst[0] - 1e-12:
                worst = (power, float(base), way)
    _, base, way = worst
    room = 1 - base if way == "rise" else base
    limit = _ref_limit(lambda g: _ref_fisher_power(base, n, n, level, g, way == "rise"), room)
    assert limit is not None
    return base, way, limit


SMALL_SPEC = """\
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = 30

[axes.task_id]
type = "categorical"
values = ["search", "refund"]
"""


@pytest.fixture(scope="module")
def swept(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    work = tmp_path_factory.mktemp("swept")
    spec = work / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    root = work / "prove-runs"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", str(work))
        result = _cli(root, "sweep", str(spec), "--target", "poisson_prove.examples.mock_agent:rollout",
                      "--max-mde", "0.5", "--yes")
    assert result.code == 0, result.err
    (run,) = Store(root).runs()
    return root, run


def _assert_design(design: dict[str, Any], *, n: int, conditions: int, events: int, threshold: float) -> None:
    rows = conditions * events
    base, way, limit = _ref_gate(n, rows, threshold)
    assert design["base_rate"] == base, (design["base_rate"], base)
    assert design["direction"] == way, (design["direction"], way)
    assert abs(design["mde"] - limit) <= 1e-4 + 1e-12, (design["mde"], limit)
    assert (design["test"], design["family"], design["conditions"], design["events"]) == ("fisher", rows, conditions, events)
    assert abs(design["level"] - Q / rows) <= 1e-15 and design["q"] == Q and design["power"] == 0.8
    assert design["flaggable"] is True


def test_pf4_4_a_new_run_records_the_gates_design_limit(swept: tuple[Path, str]) -> None:
    root, run = swept
    env = Store(root).manifest(run).environment
    _assert_design(env["design_mde"], n=30, conditions=2, events=1, threshold=0.5)


def test_pf4_4_the_single_run_report_prints_the_recorded_design_limit(swept: tuple[Path, str], tmp_path: Path) -> None:
    root, run = swept
    doc = _json(_cli(root, "report", run, "--event", "completed", "--x", "task_id", "--out", str(tmp_path / "r"), "--json"))
    _assert_design(doc["design_mde"], n=30, conditions=2, events=1, threshold=0.5)
    assert doc["design_mde"]["computed_at_read_time"] is False
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert f"{doc['design_mde']['mde']:.3f}" in md.split("##")[0]


def test_pf4_4_a_0_0_1_runs_design_limit_is_computed_at_read_time_and_says_so(tmp_path: Path) -> None:
    import shutil

    root = tmp_path / "old"
    shutil.copytree(OLD / "store", root)
    run = OLD_RUNS["quickstart_before"]
    doc = _json(_cli(root, "report", run, "--event", "violated", "--x", "task_id", "--y", "tool_fail_rate",
                     "--out", str(tmp_path / "r"), "--json"))
    # The run recorded 100 replicates over 9 conditions and declared no outcome: one event, 9 rows.
    _assert_design(doc["design_mde"], n=100, conditions=9, events=1, threshold=0.2)
    assert doc["design_mde"]["computed_at_read_time"] is True
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert f"{doc['design_mde']['mde']:.3f}" in md.split("##")[0] and "read time" in md


@pytest.mark.parametrize("replicates,passes", [(100, False), (194, True)])
def test_pf4_30_the_quickstarts_design_passes_the_gate_at_194_and_is_refused_at_100(replicates: int, passes: bool, tmp_path: Path) -> None:
    """The packaged quickstart's design, its two failures declared (9 conditions by 2 events, 18 rows),
    at the default 0.20: Fisher's worst base rate 0.4 with a limit of 0.1991 at 194 (E21, E22); 100 is
    refused with the 194 that passes both tests offered first. (Fisher alone passes from fewer: the
    quickstart's 194 is the paired test's, Q56.)"""
    from conftest import PACKAGED_QUICKSTART

    spec = tmp_path / "prove.toml"
    text = PACKAGED_QUICKSTART.read_text(encoding="utf-8")
    spec.write_text(re.sub(r"(?m)^replicates = \d+$", f"replicates = {replicates}", text), encoding="utf-8")
    result = _cli(tmp_path / "prove-runs", "sweep", str(spec), "--dry-run", "--json")
    if passes:
        plan = _json(result)
        design = plan["design_mde"]
        assert (design["family"], design["conditions"], design["events"], design["test"]) == (18, 9, 2, "fisher")
        assert design["base_rate"] == 0.4 and abs(design["mde"] - 0.1991) <= 1e-4 + 1e-12, design
    else:
        assert result.code == 1, (result.code, result.err)
        nexts = [line for line in result.err.splitlines() if line.startswith("  next:")]
        assert re.search(r"--replicates \d+", nexts[0]), nexts
        assert any("--max-mde" in line for line in nexts), nexts


@pytest.mark.slow
def test_pf4_30_paired_with_an_earlier_run_the_gate_asks_the_paired_test_and_194_passes(tmp_path: Path) -> None:
    """Under ``--pair-with`` the gate's test is the paired test with independent arms, its pairs the
    earlier run's replicates: at 194 its worst base rate is 0.4 for a rise, the tie with a fall from 0.6
    going to the lower base rate (limit 0.1998, E21), and at 193 it is refused (0.7984)."""
    from conftest import PACKAGED_QUICKSTART

    root = tmp_path / "prove-runs"
    spec = tmp_path / "prove.toml"
    spec.write_text(PACKAGED_QUICKSTART.read_text(encoding="utf-8"), encoding="utf-8")
    first = _cli(root, "sweep", str(spec), "--yes")
    assert first.code == 0, first.err
    (earlier,) = Store(root).runs()
    plan = _json(_cli(root, "sweep", str(spec), "--target", "poisson_prove.examples.mock_agent:rollout_patched",
                      "--pair-with", earlier, "--dry-run", "--json"))
    design = plan["design_mde"]
    assert design["test"] == "mcnemar" and design["base_rate"] == 0.4 and abs(design["mde"] - 0.1998) <= 1e-4 + 1e-12, design
    lowered = tmp_path / "lowered.toml"
    lowered.write_text(re.sub(r"(?m)^replicates = \d+$", "replicates = 193", spec.read_text(encoding="utf-8")), encoding="utf-8")
    refused = _cli(root, "sweep", str(lowered), "--target", "poisson_prove.examples.mock_agent:rollout_patched",
                   "--pair-with", earlier, "--dry-run")
    assert refused.code == 1, refused.err


# ---------- PF4.5 and PF4.29: one verdict rule on every surface ----------


def _verdicts(root: Path, tmp: Path, *events: str) -> dict[str, str]:
    """The comparison's verdict word on every surface that carries it."""
    event_args = [a for e in events for a in ("--event", e)]
    diff_json = _json(_cli(root, "diff", A_ID, B_ID, *event_args, "--method", "fisher_bh", "--json"))
    diff_text = _cli(root, "diff", A_ID, B_ID, *event_args, "--method", "fisher_bh")
    assert diff_text.code == 0, diff_text.err
    report_json = _json(_cli(root, "report", A_ID, B_ID, *event_args, "--method", "fisher_bh", "--x", "cell",
                             "--out", str(tmp / "rj"), "--json"))
    report_md = _cli(root, "report", A_ID, B_ID, *event_args, "--method", "fisher_bh", "--x", "cell",
                     "--out", str(tmp / "rm"))
    assert report_md.code == 0, report_md.err
    md_lines = (tmp / "rm" / "report.md").read_text(encoding="utf-8").splitlines()
    assert md_lines[0].startswith("# ") and md_lines[1] == ""
    page = _json(_cli(root, "serve", A_ID, B_ID, *event_args, "--method", "fisher_bh", "--x", "cell", "--json"))
    return {
        "diff --json": diff_json["verdict"],
        "diff": _first_word(diff_text.out),
        "report --json": report_json["comparison_verdict"],
        "report.md": _first_word(md_lines[2]),
        "page summary": page["summary"]["verdict"],
    }


def _one_word(words: dict[str, str]) -> str:
    assert len(set(words.values())) == 1, words
    return next(iter(words.values()))


def _rows_of_8_4() -> list[tuple[str, dict[str, Any], dict[str, Any], str]]:
    """One constructed pair per row of section 8.4's table and PF4.29's edges, the event declared a
    failure on the command line. 200 runs give an unchanged condition a limit near 0.1 both ways; 20,
    one near 0.5."""
    return [
        ("trade", {"w": _arm(4, 40), "s": _arm(30, 40)}, {"w": _arm(30, 40), "s": _arm(4, 40)}, "trade"),
        ("worse", {"w": _arm(4, 40), "u": _arm(5, 200)}, {"w": _arm(30, 40), "u": _arm(5, 200)}, "worse"),
        ("safer", {"s": _arm(30, 40), "u": _arm(5, 200)}, {"s": _arm(4, 40), "u": _arm(5, 200)}, "safer"),
        ("too small", {"u": _arm(10, 20), "v": _arm(10, 20)}, {"u": _arm(10, 20), "v": _arm(10, 20)}, "too small to tell"),
        ("no change", {"u": _arm(20, 200), "v": _arm(5, 200)}, {"u": _arm(20, 200), "v": _arm(5, 200)}, "no significant change"),
        # PF4.29: a condition that can tell a rise of 0.20 from 0.70 at 120 runs but not a fall: too small.
        ("only up", {"u": _arm(84, 120), "v": _arm(84, 120)}, {"u": _arm(84, 120), "v": _arm(84, 120)}, "too small to tell"),
        # No room downward at T: from 0.05 a fall of 0.20 has no room, so only the rise is asked.
        ("no room down", {"u": _arm(10, 200), "v": _arm(10, 200)}, {"u": _arm(10, 200), "v": _arm(10, 200)}, "no significant change"),
        # Every condition cannot be flagged at all: too small, whatever the threshold.
        ("cannot flag", {"u": _arm(1, 3), "v": _arm(1, 3)}, {"u": _arm(1, 3), "v": _arm(1, 3)}, "too small to tell"),
    ]


ROW_IDS = ["trade", "worse", "safer", "too-small", "no-change", "only-up", "no-room-down", "cannot-flag"]


@pytest.mark.parametrize("row", range(len(ROW_IDS)), ids=ROW_IDS)
def test_pf4_5_every_surface_gives_the_same_word_by_section_8_4s_table(row: int, tmp_path: Path) -> None:
    name, a, b, word = _rows_of_8_4()[row]
    root = _pair(tmp_path / "prove-runs", a, b)
    assert _one_word(_verdicts(root, tmp_path, "fell:failure")) == word, name


def test_pf4_29_the_question_reads_each_direction_with_room_and_t_above_both_rooms(tmp_path: Path) -> None:
    """The constructions the rows above rest on, against the stats file's references: 'only up' (0.7 at 120
    runs, two rows) can tell a rise of 0.20 and not a fall; with T at 0.6 a condition at 0.5 is asked
    about 0.5."""
    up, down = _ref_fisher_limits(84, 120, 120, Q / 2)
    assert up is not None and down is not None and up <= 0.20 < down, (up, down)
    root = _pair(tmp_path / "prove-runs", {"u": _arm(100, 200)}, {"u": _arm(100, 200)},
                 environment_a={"max_mde_accepted": 0.6}, environment_b={"max_mde_accepted": 0.6})
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh", "--json"))
    assert doc["verdict"] == "no significant change" and doc["threshold"] == 0.6


def test_pf4_5_a_condition_that_trades_two_events_counts_as_both(tmp_path: Path) -> None:
    """One condition: 'fell' falls and 'stuck' rises, both significantly; nothing else moves."""
    a_rows = [(i, "fell", 1.0 + 0.01 * i) if i < 30 else (i, "stuck", 2.0) if i < 34 else (i, "ok", HORIZON)
              for i in range(60)]
    b_rows = [(i, "fell", 1.0 + 0.01 * i) if i < 4 else (i, "stuck", 2.0) if i < 34 else (i, "ok", HORIZON)
              for i in range(60)]
    quiet = [(i, "ok", HORIZON) for i in range(60)]
    root = _pair(tmp_path / "prove-runs", {"c": a_rows, "quiet": quiet}, {"c": b_rows, "quiet": quiet})
    assert _one_word(_verdicts(root, tmp_path, "fell:failure", "stuck:failure")) == "trade"


#: Every unchanged condition at 60 runs and a rate of 0.5: a limit between 0.20 and 0.30 both ways.
MID = {"u": _arm(30, 60), "v": _arm(30, 60)}


@pytest.mark.parametrize(
    "env_a,env_b,word,threshold,source",
    [
        ({"max_mde_accepted": 0.30}, {"max_mde_accepted": 0.30}, "no significant change", 0.30, "recorded"),
        ({"max_mde_accepted": 0.30}, {"max_mde_accepted": 0.20}, "too small to tell", 0.20, "smaller"),
        ({"max_mde_accepted": 0.20}, {"max_mde_accepted": 0.30}, "too small to tell", 0.20, "smaller"),
        ({}, {}, "too small to tell", 0.20, "default"),
    ],
    ids=["both-recorded", "different-a-larger", "different-b-larger", "none-recorded"],
)
def test_pf4_5_the_threshold_is_the_recorded_one_the_smaller_of_two_or_the_default(
    env_a: dict[str, Any], env_b: dict[str, Any], word: str, threshold: float, source: str, tmp_path: Path
) -> None:
    rise, fall = _ref_fisher_limits(30, 60, 60, Q / 2)
    assert rise is not None and fall is not None and 0.20 < max(rise, fall) <= 0.30  # the construction
    root = _pair(tmp_path / "prove-runs", MID, MID, environment_a=env_a, environment_b=env_b)
    assert _one_word(_verdicts(root, tmp_path, "fell:failure")) == word
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh", "--json"))
    assert doc["threshold"] == threshold and doc["threshold_source"] == source
    text = _cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh").out
    (line,) = _detail(text, "threshold")
    assert f"{threshold:.3f}" in line and source in line, line


def test_pf4_5_the_page_summarys_50_point_rule_is_gone(tmp_path: Path) -> None:
    root = _pair(tmp_path / "prove-runs", MID, MID, environment_a={}, environment_b={})
    page = _json(_cli(root, "serve", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh",
                      "--x", "cell", "--json"))
    assert page["summary"]["verdict"] == "too small to tell"
    (entry,) = page["summary"]["events"]
    assert entry["limit"]["label"] == "too small to tell"


def test_pf4_50_the_threshold_line_sits_under_the_nothing_moved_words_only(standard: Path, tmp_path: Path) -> None:
    """PF2 Session B's yes/no 1: test_e12 moves for it."""
    moved = _cli(standard, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh")
    assert _first_word(moved.out) == "trade" and _detail(moved.out, "threshold") == []
    root = _pair(tmp_path / "prove-runs", MID, MID)
    still = _cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh")
    block = _block(still.out)
    assert len(_detail(still.out, "threshold")) == 1
    labels = [line.split("  ")[1] for line in block[1:] if line.startswith("  ")]
    assert labels.index("method") < labels.index("threshold") < labels.index("before"), labels

# ---------- PF4.6: no trace grouping offered ----------


@pytest.mark.parametrize("grouping", ["kind", "step_kind"])
@pytest.mark.parametrize("verb", ["diff", "report", "serve"])
def test_pf4_6_by_kind_is_refused_as_an_unknown_grouping_listing_the_supported_ones(
    verb: str, grouping: str, standard: Path, tmp_path: Path
) -> None:
    argv = [verb, A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--by", grouping]
    if verb in ("report", "serve"):
        argv += ["--x", "cell"]
    if verb == "report":
        argv += ["--out", str(tmp_path / "r")]
    if verb == "serve":
        argv += ["--json"]  # a build that accepted the grouping would otherwise bind and wait
    result = _cli(standard, *argv)
    assert result.code == 1, (result.code, result.err)
    assert result.out == ""
    lines = result.err.splitlines()
    errors = [line for line in lines if line.startswith("error: ")]
    assert len(errors) == 1, lines
    assert all(line.startswith(("error: ", "  next:", "note: ")) for line in lines), lines
    assert re.search(rf"\b{grouping}\b", errors[0]), errors[0]
    assert re.search(r"\bcell\b", result.err)  # the one axis both runs declare is among the supported groupings
    assert not re.search(r"Phase \d", result.err)
    assert not (tmp_path / "r").exists()


@pytest.mark.parametrize("verb", ["diff", "report", "serve"])
def test_pf4_6_no_help_names_a_phase_or_offers_a_trace_grouping(verb: str, tmp_path: Path) -> None:
    result = _cli(tmp_path, verb, "--help")
    assert result.code == 0
    assert not re.search(r"Phase \d", result.out)
    assert "step_kind" not in result.out


# ---------- PF4.7: no comparable condition is a refusal ----------


@pytest.mark.parametrize("verb", ["diff", "diff --json", "check", "report", "serve"])
def test_pf4_7_a_pair_with_no_comparable_condition_is_refused_naming_the_holes(verb: str, tmp_path: Path) -> None:
    """PF4 Session A's yes/no 13, ruled 2026-10-24: every comparing verb refuses, not only diff."""
    a = {"c1": _arm(4, 20), "c2": _arm(4, 20), "c3": _arm(4, 20)}
    b = {"d1": _arm(4, 20), "d2": _arm(4, 20)}
    root = _pair(tmp_path / "prove-runs", a, b)
    name, *extra = verb.split()
    argv = [name, A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", *extra]
    if name in ("report", "serve"):
        argv += ["--x", "cell"]
    if name == "report":
        argv += ["--out", str(tmp_path / "r")]
    if name == "serve":
        argv += ["--json"]  # a build that did not refuse would otherwise bind and wait
    if name == "check":
        argv += ["--fail-on", "any"]
    result = _cli(root, *argv)
    assert result.code == 1, (result.code, result.out, result.err)
    assert result.out == ""
    lines = result.err.splitlines()
    errors = [line for line in lines if line.startswith("error: ")]
    assert len(errors) == 1, lines
    assert all(line.startswith(("error: ", "  next:", "note: ")) for line in lines), lines
    assert re.search(r"\b3\b", errors[0]) and re.search(r"\b2\b", errors[0]), errors[0]
    assert any(line.startswith("  next:") for line in lines)
    assert not (tmp_path / "r").exists()


# ---------- PF4.8: --methods all --json keeps the primary method's omnibus and tree ----------


def test_pf4_8_methods_all_json_carries_the_primary_methods_omnibus_and_tree(standard: Path) -> None:
    single = _json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    every = _json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh",
                       "--methods", "all", "--json"))
    for method in ("fisher_bh", "mcnemar_bh", "logrank_bh"):
        assert method in every, sorted(every)
    assert every["omnibus"] == single["omnibus"]
    assert every["tree"] == single["tree"]


# ---------- PF4.9: paired names what is not recorded once, in plain words ----------

PAIRED_SALT = "9f4a1c62d08e5b37"
REQUEST_SPAN = "scorer.request"
MODEL_PIN = "scorer-1.13.0"


def _paired_store(root: Path, sweeps: tuple[str, ...]) -> None:
    from poisson_prove.episode import Episode
    from poisson_prove.executor import derive_seed
    from poisson_prove.trace import Span, Trace

    store = Store(root)
    epoch = 1_790_000_000_000_000_000
    for s_index, sweep in enumerate(sweeps):
        for a_index, arm in enumerate(("a", "b")):
            run_id = f"{sweep}-{arm}"
            store.create_run(RunManifest(
                run_id=run_id, target_id="scorer@v1", t_unit="steps", run_salt=PAIRED_SALT,
                axis_types={"item": "categorical", "cut": "categorical"}, backend="local",
                environment={"python": "3.11.7", "platform": "test",
                             "capture": {"content": True, "max_observation_bytes": "none"}},
            ))
            records = []
            for i in range(8):
                config = {"item": f"i{i:03d}", "cut": "c60"}
                value = "0.05" if (arm == "b" and i < 3) else "0.95"
                start = epoch + s_index * 86_400_000_000_000 + i * 2_000_000_000 + a_index * 60_000_000_000
                body = (f'{{"model": "{MODEL_PIN}", "state": "state of i{i:03d}", "temperature": 0.30, '
                        '"max_tokens": 64}')
                span = Span(span_id="0000000000000001", parent_id=None, kind="http", name=REQUEST_SPAN,
                            start_ns=start, end_ns=start + 400_000_000, input=body,
                            output='{"answers": {"q1": {"score": 0.62}}}', tokens={"in": 400, "out": 12},
                            attrs={"url.full": "https://api.example.test/v1/evaluate", "http.request.method": "POST"})
                meta = {"trace": Trace(spans=(span,), source="record").to_dict(), "answers": {"q1": {"score": value}}}
                outcome = "acted" if float(value) >= 0.5 else "declined"
                records.append(EpisodeRecord.from_episode(
                    Episode(outcome=outcome, t=1.0, horizon=10.0, meta=meta), run_id=run_id, config=config,
                    seed=derive_seed(PAIRED_SALT, config_hash(config), 0), replicate_index=0, wall_time=0.1,
                ))
            store.append(run_id, records)
            store.mark_complete(run_id)


def _paired_declaration(path: Path, sweeps: tuple[str, ...]) -> Path:
    lines = [
        'value_key = "answers.q1.score"', 'cluster_key = "item"', 'stratum_key = "cut"',
        f'request_span = "{REQUEST_SPAN}"', 'model_key = "model"', f'model_pin = "{MODEL_PIN}"',
        'exemptions = ["x-request-id"]', 'headers = "not_recorded"', 'retries = "not_recorded"',
        "bootstrap_b = 200", "bootstrap_seed = 20260922",
        "", "[[cuts]]", 'name = "c60"', "threshold = 0.60", 'comparison = "ge"',
    ]
    for s in sweeps:
        lines += ["", "[[sweeps]]", f'name = "{s}"', f'a = "{s}-a"', f'b = "{s}-b"']
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("sweeps", [("S1",), ("S1", "S2")], ids=["one-sweep", "two-sweeps"])
def test_pf4_9_paired_names_what_is_not_recorded_once_in_plain_words(sweeps: tuple[str, ...], tmp_path: Path) -> None:
    root = tmp_path / "store"
    _paired_store(root, sweeps)
    decl = _paired_declaration(tmp_path / "decl.toml", sweeps)
    result = _cli(root, "paired", "--declaration", str(decl), "--out", str(tmp_path / "out"))
    assert result.code == 0, result.err
    lines = (result.out + result.err).splitlines()
    named = [line for line in lines if "harness" in line.lower() or "client" in line.lower()]
    assert len(named) == 1, lines
    assert "harness" in named[0] and "client" in named[0] and "not recorded" in named[0].lower()
    assert not any("harness_digest" in line or "client_version" in line for line in lines), lines


# ---------- PF4.10: content off strips OpenInference's prompt content on llm spans ----------

_CAPTURE_CHILD = r"""
import json, sys
from opentelemetry import trace
from poisson_prove.capture import CaptureSpec, capture, install
content = sys.argv[1] == "on"
install(CaptureSpec(content=content, max_observation_bytes=8192))
tracer = trace.get_tracer("pf4.oracle", "0.1.0")
with capture("pf4-run", "cfg:1") as recorder:
    for name, attrs in json.loads(sys.argv[2]):
        with tracer.start_as_current_span(name) as span:
            for key, value in attrs.items():
                span.set_attribute(key, value)
print(json.dumps(recorder.to_meta()))
"""

SPANS = [
    ("llm call", {"openinference.span.kind": "LLM", "input.value": "the prompt", "output.value": "the answer"}),
    ("chat model", {"gen_ai.operation.name": "chat", "input.value": "prompt two", "output.value": "answer two"}),
    ("lookup", {"openinference.span.kind": "TOOL", "input.value": "tool args", "output.value": "tool result"}),
]


def _captured(content: str) -> list[dict[str, Any]]:
    pytest.importorskip("opentelemetry.sdk")
    from poisson_prove.trace import Trace

    env = dict(os.environ, PYTHONPATH=str(SRC))
    proc = subprocess.run(
        [sys.executable, "-c", _CAPTURE_CHILD, content, json.dumps(SPANS)],
        capture_output=True, text=True, env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    trace = Trace.from_dict(json.loads(proc.stdout.strip().splitlines()[-1]))
    return [{"name": s.name, "kind": s.kind, "attrs": dict(s.attrs)} for s in trace.spans]


def test_pf4_10_content_off_strips_input_and_output_value_on_llm_spans_only() -> None:
    spans = {s["name"]: s for s in _captured("off")}
    for name in ("llm call", "chat model"):
        assert spans[name]["kind"] == "llm", spans[name]
        assert "input.value" not in spans[name]["attrs"], spans[name]
        assert "output.value" not in spans[name]["attrs"], spans[name]
    assert spans["lookup"]["kind"] == "tool"
    assert spans["lookup"]["attrs"]["input.value"] == "tool args"
    assert spans["lookup"]["attrs"]["output.value"] == "tool result"


def test_pf4_10_content_on_keeps_them() -> None:
    spans = {s["name"]: s for s in _captured("on")}
    assert spans["llm call"]["attrs"]["input.value"] == "the prompt"
    assert spans["chat model"]["attrs"]["output.value"] == "answer two"


# ---------- PF4.11: no path or machine string in what a user would share ----------


def test_pf4_11_no_output_carries_the_store_path_the_platform_the_python_build_or_the_import_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    marker = str(uuid.uuid4())
    home = tmp_path / f"home-{marker}"
    work = home / "work" / marker
    root = work / "prove-runs"
    shutil.copytree(OLD / "store", root)
    monkeypatch.setenv("HOME", str(home))
    # The user works in that folder and names the store and the output folders as typed there.
    monkeypatch.chdir(work)
    a, b = OLD_RUNS["quickstart_before"], OLD_RUNS["quickstart_after"]
    manifest = json.loads((root / a / "manifest.json").read_text(encoding="utf-8"))
    secrets = [str(root), str(home), marker, manifest["environment"]["platform"],
               manifest["environment"]["python"], manifest["environment"]["import_path"]]
    ev = ["--event", "violated", "--method", "fisher_bh"]
    texts: dict[str, str] = {}
    for name, argv in {
        "diff --json": ["diff", a, b, *ev, "--json"],
        "check --json": ["check", a, b, "--event", "violated:failure", "--method", "fisher_bh", "--json"],
        "serve --json": ["serve", a, b, *ev, "--x", "task_id", "--y", "tool_fail_rate", "--json"],
        "report --json": ["report", a, b, *ev, "--x", "task_id", "--y", "tool_fail_rate", "--out", "r", "--json"],
        "single report --json": ["report", a, "--event", "violated", "--x", "task_id", "--y", "tool_fail_rate",
                                 "--out", "s", "--json"],
        "runs --json": ["runs", "--json"],
    }.items():
        result = _cli("prove-runs", *argv)
        assert result.code in (0, 4), (name, result.err)
        texts[name] = result.out
    for folder in ("r", "s"):
        for file in ("report.md", "receipt.html"):
            texts[f"{folder}/{file}"] = (work / folder / file).read_text(encoding="utf-8")
    # PF4 Session A's yes/no 15 and the independent read's finding 4, ruled 2026-10-24: paired --json and
    # sweep --json are in "any --json" too. sweep's plan names the target as it was typed (PF3's frozen
    # plan.target), so the import path is the one fact its scan leaves out (reading R19).
    spec = work / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    swept = _cli("prove-runs", "sweep", "spec.toml", "--target", "poisson_prove.examples.mock_agent:rollout",
                 "--max-mde", "0.5", "--yes", "--json")
    assert swept.code == 0, swept.err
    paired_root = work / "paired-store"
    _paired_store(paired_root, ("S1",))
    _paired_declaration(work / "decl.toml", ("S1",))
    paired = _cli("paired-store", "paired", "--declaration", "decl.toml", "--json")
    assert paired.code == 0, paired.err
    texts["paired --json"] = paired.out
    from poisson_prove.viewer import render_html

    page = json.loads(texts["serve --json"])
    assert "store_root" not in page["pair"]  # removed from the page structure, relative or not
    texts["page"] = render_html({k: v for k, v in page.items() if k not in ("verdict", "sentence", "next")})
    for name, text in texts.items():
        for secret in secrets:
            assert secret not in text, (name, secret)
    (new_run,) = set(Store(root).runs()) - set(OLD_RUNS.values())
    own = Store(root).manifest(new_run).environment
    for secret in [*secrets[:3], own["platform"], own["python"]]:
        assert secret not in swept.out, ("sweep --json", secret)
    # The page shows the run's Python version and nothing more of the build.
    assert "3.11.7" in texts["page"]


# ---------- PF4.13 and PF4.14 on the surface ----------


def test_pf4_13_diff_json_carries_the_direction_and_its_timing_note_under_logrank(tmp_path: Path) -> None:
    a = {"c": [(i, "fell", 8.0 + 0.05 * i) for i in range(32)]}
    b = {"c": [(i, "fell", 1.0 + 0.05 * i) for i in range(32)]}
    root = _pair(tmp_path / "prove-runs", a, b, salt="unshared")
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "logrank_bh", "--json"))
    (cell,) = doc["by_event"]["fell"]["cells"]
    assert cell["delta"] == 0.0 and cell["direction"] == "higher" and cell["verdict"] == "worse"
    # The independent read's finding 6: the note says which way the timing went.
    assert isinstance(cell["direction_note"], str) and "sooner" in cell["direction_note"]
    assert doc["by_event"]["fell"]["n_worse"] == 1


def test_pf4_14_diff_json_carries_the_matched_difference_and_the_pair_count_under_the_paired_test(tmp_path: Path) -> None:
    a = [(i, "fell" if i < 4 else "ok", HORIZON if i >= 4 else 1.0) for i in range(20)]
    a += [(20 + j, "fell", 1.0) for j in range(12)]
    b = [(i, "fell" if i < 12 else "ok", HORIZON if i >= 12 else 1.0) for i in range(20)]
    b += [(40 + j, "ok", HORIZON) for j in range(12)]
    root = _pair(tmp_path / "prove-runs", {"c": a}, {"c": b})
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "mcnemar_bh", "--json"))
    (cell,) = doc["by_event"]["fell"]["cells"]
    assert cell["pairs"] == 20 and abs(cell["delta"] - 8 / 20) <= 1e-12
    assert cell["direction"] == "higher" and cell["verdict"] == "worse"
    assert abs(cell["rate_a"] - 0.5) <= 1e-12 and abs(cell["rate_b"] - 0.375) <= 1e-12


# ---------- PF4.22, PF4.27, PF4.32: the limits on every surface ----------


LIMIT_KEYS = ("mde_rise", "mde_fall", "mde", "mde_rise_note", "mde_fall_note", "mde_note", "mde_test", "mde_basis",
              "mde_level", "mde_family", "mde_power", "mde_anchor", "p_min", "flaggable", "mde_moves_with",
              "mde_rise_verdict", "mde_fall_verdict")


def test_pf4_22_every_surface_gives_the_same_limits_as_the_one_family(standard: Path, tmp_path: Path) -> None:
    """The contract: diff, check, report and serve carry each condition's limits as the library
    computes them, key for key."""
    from poisson_prove.diff import multi_diff

    store = Store(standard)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        library = multi_diff(store.read(A_ID, meta=False), store.read(B_ID, meta=False), events=["fell"], method="fisher_bh",
                             manifest_a=store.manifest(A_ID), manifest_b=store.manifest(B_ID)).to_json()
    want = _cells_of(library)
    page = _json(_cli(standard, "serve", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--json"))
    docs = {
        "diff": _cells_of(_json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))),
        "check": _cells_of(_json(_cli(standard, "check", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh",
                                      "--fail-on", "any", "--json"))),
        "report": _cells_of(_json(_cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh",
                                       "--x", "cell", "--out", str(tmp_path / "r"), "--json"))),
        "serve": {str(c["config_hash"]): c for c in page["panels"][0]["cells"]},
    }
    for surface, cells in docs.items():
        assert sorted(cells) == sorted(want), surface
        for h, c in cells.items():
            for key in LIMIT_KEYS:
                assert c[key] == want[h][key], (surface, h, key, c[key], want[h][key])


def test_pf4_27_a_null_limit_prints_its_reason_and_no_number(standard: Path, tmp_path: Path) -> None:
    """Amends PF4.15 (Q54 = yes): the condition at 40 of 40 has no rise ('no room') and a fall, which is
    its limit; at 38 of 40 a rise has room and none is detectable, so its one number is null."""
    doc = _json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    cells = _cells_of(doc)
    top, near = cells[_hash("top")], cells[_hash("near_top")]
    assert top["mde_rise"] is None and top["mde_rise_note"] == "no room"
    assert isinstance(top["mde_fall"], float) and top["mde"] == top["mde_fall"] and top["mde_note"] is None
    assert near["mde_rise"] is None and near["mde_rise_note"] == "none detectable"
    assert near["mde"] is None and near["mde_note"] == "none detectable"
    for c in cells.values():
        for way in ("rise", "fall"):
            assert (c[f"mde_{way}"] is None) is (c[f"mde_{way}_note"] in NOTES), (c["config_hash"], way)
    numbers = [c["mde"] for c in cells.values() if c["mde"] is not None]
    assert doc["by_event"]["fell"]["max_mde"] == max(numbers)
    text = _cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh").out
    top_text, near_text = _column(text, "top", "mde"), _column(text, "near_top", "mde")
    assert f"{top['mde_fall']:.3f}" in top_text and "no room" in top_text, top_text
    assert "none detectable" in near_text and "rise" in near_text, near_text
    rise_part = near_text.split("rise", 1)[1].split(",", 1)[0]
    assert not re.search(r"\d", rise_part), near_text  # no number for the null way
    if near["mde_fall"] is not None:
        assert f"{near['mde_fall']:.3f}" in near_text, near_text
    _cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--out", str(tmp_path / "r"))
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert "no room" in md and "none detectable" in md and "ceiling" not in md


def test_pf4_27_the_honesty_line_that_names_an_undetectable_condition_says_so(tmp_path: Path) -> None:
    a = {"w": _arm(4, 40), "s": _arm(30, 40), "near": _arm(38, 40)}
    b = {"w": _arm(30, 40), "s": _arm(4, 40), "near": _arm(38, 40)}
    root = _pair(tmp_path / "prove-runs", a, b)
    _cli(root, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--out", str(tmp_path / "r"))
    page = _json(_cli(root, "serve", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--json"))
    (entry,) = page["summary"]["events"]
    assert "none detectable" in entry["limit"]["line"]
    (panel,) = page["panels"]
    assert "none detectable" in panel["honesty"]
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert [line for line in md.splitlines() if "none detectable" in line and not line.startswith("|")], md


def test_pf4_32_every_surface_names_the_limits_test_level_family_and_power_from_the_one_setting(
    standard: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``poisson_prove.stats.POWER`` patched to 0.9, every surface that prints a limit says "9 times
    in 10" and none says "4 times in 5"; each names Fisher, the level and the family."""
    import poisson_prove.stats as stats_module

    import shutil

    monkeypatch.setattr(stats_module, "POWER", 0.9)
    s = _surfaces(standard, tmp_path, "fell")
    old = tmp_path / "old"
    shutil.copytree(OLD / "store", old)
    single = tmp_path / "single"
    assert _cli(old, "report", OLD_RUNS["quickstart_before"], "--event", "violated", "--x", "task_id", "--y", "tool_fail_rate",
                "--out", str(single)).code == 0
    single_md = (single / "report.md").read_text(encoding="utf-8")
    assert "9 times in 10" in single_md and "4 times in 5" not in single_md and "over 9 tests" in single_md
    for name, text in _texts(s).items():
        if name == "check":
            continue  # check prints no cell table (Session A's yes/no 14)
        assert "9 times in 10" in text and "4 times in 5" not in text, name
        assert "Fisher" in text and "over 6 tests" in text, name
    for c in s["diff --json"]["by_event"]["fell"]["cells"]:
        assert c["mde_power"] == 0.9

# ---------- PF4.17: the limit sentence counts the conditions not compared ----------


def test_pf4_17_when_every_compared_condition_moved_the_lines_count_what_was_not_compared(tmp_path: Path) -> None:
    a = {"c1": _arm(4, 40), "c2": _arm(30, 40), "c3": _arm(5, 40), "c4": _arm(5, 40), "c5": _arm(5, 40),
         "c6": _arm(5, 40)}
    b = {"c1": _arm(30, 40), "c2": _arm(4, 40)}
    root = _pair(tmp_path / "prove-runs", a, b)
    page = _json(_cli(root, "serve", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--json"))
    (entry,) = page["summary"]["events"]
    line = entry["limit"]["line"]
    assert re.search(r"\b2\b", line) and re.search(r"\b4\b", line), line
    assert not re.search(r"\bevery (condition|cell)\b", line, re.IGNORECASE), line
    result = _cli(root, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
                  "--out", str(tmp_path / "r"))
    assert result.code == 0, result.err
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert not re.search(r"\bevery (condition|cell) moved\b", md, re.IGNORECASE)
    counted = [ln for ln in md.splitlines() if "compared" in ln and re.search(r"\b2\b", ln) and re.search(r"\b4\b", ln)]
    assert counted, md


# ---------- PF4.20: verdict words name the direction; safer and worse need a kind ----------


def test_pf4_20_without_a_kind_every_word_names_the_direction_and_none_judges(standard: Path, tmp_path: Path) -> None:
    from poisson_prove.viewer import render_html

    doc = _json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    assert doc["verdict"] == "mixed"
    ev = doc["by_event"]["fell"]
    assert ev["kind"] is None
    assert ev["n_higher"] == 1 and ev["n_lower"] == 1
    assert ev["n_safer"] is None and ev["n_worse"] is None
    cells = _cells_of(doc)
    assert cells[_hash("up")]["verdict"] == "higher" and cells[_hash("up")]["direction"] == "higher"
    assert cells[_hash("down")]["verdict"] == "lower" and cells[_hash("down")]["direction"] == "lower"
    assert cells[_hash("same")]["verdict"] == "unchanged"
    assert not any(JUDGEMENT.search(s) for s in _strings(doc)), [s for s in _strings(doc) if JUDGEMENT.search(s)]
    diff_text = _cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh")
    assert _first_word(diff_text.out) == "mixed"
    _cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
         "--out", str(tmp_path / "r"))
    page = _json(_cli(standard, "serve", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--json"))
    check_text = _cli(standard, "check", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--fail-on", "higher")
    assert check_text.code == 4, check_text.err
    surfaces = {
        "diff": diff_text.out + diff_text.err,
        "check": check_text.out + check_text.err,
        "report.md": (tmp_path / "r" / "report.md").read_text(encoding="utf-8"),
        "receipt.html": _strip_tags((tmp_path / "r" / "receipt.html").read_text(encoding="utf-8")),
        # Values only: a key such as ``n_safer`` names a field, as it does in diff --json.
        "page summary": "\n".join(_strings(page["summary"])),
        "page strings": "\n".join(_strings(page)),
        "page": _strip_tags(render_html({k: v for k, v in page.items() if k not in ("verdict", "sentence", "next")})),
    }
    for name, text in surfaces.items():
        hits = sorted({m.group(0) for m in JUDGEMENT.finditer(text)})
        assert not hits, (name, hits)


def test_pf4_20_the_comparison_object_itself_reads_in_direction_words_without_a_kind() -> None:
    """Ruled 2026-10-24 (the independent read's yes/no 1): no split between the library and the
    screen. The lattice pair under log-rank, ``tripped`` with no kind: 27 conditions fell and 12 rose
    (lifelines' log-rank over the stored times gives the same, ``lattice.logrank``), as direction words
    on the object itself; the safer and worse counts are null; the default worse-gate is refused and
    ``check("higher")`` fails on the 12 rises."""
    from poisson_prove.diff import DiffError, multi_diff

    pair = Store(lattice.root())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = multi_diff(pair.read(lattice.RUN_A, meta=False), pair.read(lattice.RUN_B, meta=False),
                            events=[lattice.EVENT], method="logrank_bh",
                            manifest_a=pair.manifest(lattice.RUN_A), manifest_b=pair.manifest(lattice.RUN_B))
    ev = result.by_event[lattice.EVENT]
    assert ev.kind is None and ev.n_safer is None and ev.n_worse is None
    assert set(ev.cells["verdict"]) <= {"higher", "lower", "unchanged"}
    assert (ev.n_lower, ev.n_higher) == lattice.directions(lattice.logrank()) == (27, 12)
    assert ev.n_lower + ev.n_higher == 39
    assert list(ev.cells["verdict"]) == list(ev.cells["direction"])
    assert len(result.trades) == 0 and result.comparison_verdict() == "mixed"
    with pytest.raises(DiffError):
        result.check()
    assert result.check("higher") is False and result.check("any") is False


def test_pf4_20_a_failure_kind_given_on_the_command_line_gives_safer_and_worse(standard: Path) -> None:
    doc = _json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh", "--json"))
    assert doc["verdict"] == "trade"
    ev = doc["by_event"]["fell"]
    assert ev["kind"] == "failure"
    assert (ev["n_safer"], ev["n_worse"], ev["n_higher"], ev["n_lower"]) == (1, 1, 1, 1)
    cells = _cells_of(doc)
    assert cells[_hash("up")]["verdict"] == "worse" and cells[_hash("up")]["direction"] == "higher"
    assert cells[_hash("down")]["verdict"] == "safer" and cells[_hash("down")]["direction"] == "lower"


SOLVED_A = {"c": [(i, "solved" if i < 6 else "failed", 1.0) for i in range(32)]}
SOLVED_B = {"c": [(i, "solved" if i < 26 else "failed", 1.0) for i in range(32)]}


@pytest.fixture(scope="module")
def solved(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The re-check's success event (README section 10): B solves 26 of 32 where A solved 6."""
    return _pair(tmp_path_factory.mktemp("solved") / "prove-runs", SOLVED_A, SOLVED_B)


def test_pf4_20_a_success_event_that_rose_is_safer_and_never_worse(solved: Path) -> None:
    from scipy.stats import fisher_exact

    doc = _json(_cli(solved, "diff", A_ID, B_ID, "--event", "solved:success", "--method", "fisher_bh", "--json"))
    (cell,) = doc["by_event"]["solved"]["cells"]
    # scipy documents ``fisher_exact(table)`` on [[a, b], [c, d]] with rows the two samples.
    assert abs(cell["p"] - float(fisher_exact([[6, 26], [26, 6]])[1])) <= 1e-12
    assert cell["direction"] == "higher"
    assert cell["verdict"] == "safer"
    assert doc["verdict"] == "safer"
    ev = doc["by_event"]["solved"]
    assert (ev["kind"], ev["n_safer"], ev["n_worse"]) == ("success", 1, 0)
    passed = _cli(solved, "check", A_ID, B_ID, "--event", "solved:success", "--method", "fisher_bh")
    assert passed.code == 0, (passed.out, passed.err)
    assert _first_word(passed.out) == "passed"
    as_failure = _cli(solved, "check", A_ID, B_ID, "--event", "solved:failure", "--method", "fisher_bh")
    assert as_failure.code == 4
    assert _first_word(as_failure.out) == "failed"
    # The independent read's finding 2: the report, the receipt and the page say safer too, never worse.
    # A report needs an axis that varies, so the pair gains a quiet second condition.
    quiet = [(i, "failed", 1.0) for i in range(32)]
    two = _pair(solved.parent / f"two-{uuid.uuid4().hex[:6]}", {**SOLVED_A, "d": quiet}, {**SOLVED_B, "d": quiet})
    out = solved.parent / f"success-{uuid.uuid4().hex[:6]}"
    assert _cli(two, "report", A_ID, B_ID, "--event", "solved:success", "--method", "fisher_bh", "--x", "cell",
                "--out", str(out)).code == 0
    page = _json(_cli(two, "serve", A_ID, B_ID, "--event", "solved:success", "--method", "fisher_bh", "--x", "cell", "--json"))
    assert page["summary"]["verdict"] == "safer"
    for name, text in {"report.md": (out / "report.md").read_text(encoding="utf-8"),
                       "receipt.html": _strip_tags((out / "receipt.html").read_text(encoding="utf-8")),
                       "page": _page_text(page)}.items():
        # The rise is counted safer; "0 worse" is a count, never a judgement of the rise.
        assert re.search(r"\b1 safer\b", text) and not re.search(r"\b[1-9]\d* worse\b", text), name


def test_pf4_20_check_fail_on_worse_without_a_kind_is_refused_naming_both_ways_out(solved: Path) -> None:
    result = _cli(solved, "check", A_ID, B_ID, "--event", "solved", "--method", "fisher_bh")
    assert result.code == 1, (result.code, result.out, result.err)
    assert result.out == ""
    lines = result.err.splitlines()
    assert len([line for line in lines if line.startswith("error: ")]) == 1, lines
    nexts = [line for line in lines if line.startswith("  next:")]
    assert any("--fail-on higher" in line for line in nexts), nexts
    assert any("solved:failure" in line or "solved:success" in line for line in nexts), nexts
    explicit = _cli(solved, "check", A_ID, B_ID, "--event", "solved", "--method", "fisher_bh", "--fail-on", "worse")
    assert explicit.code == 1


def test_pf4_20_check_fail_on_higher_and_lower_gate_on_the_direction(solved: Path) -> None:
    higher = _cli(solved, "check", A_ID, B_ID, "--event", "solved", "--method", "fisher_bh", "--fail-on", "higher")
    assert higher.code == 4 and _first_word(higher.out) == "failed"
    lower = _cli(solved, "check", A_ID, B_ID, "--event", "solved", "--method", "fisher_bh", "--fail-on", "lower")
    assert lower.code == 0 and _first_word(lower.out) == "passed"
    doc = _json(_cli(solved, "check", A_ID, B_ID, "--event", "solved", "--method", "fisher_bh",
                     "--fail-on", "lower", "--json"))
    assert doc["passed"] is True and doc["fail_on"] == "lower"


def _declared(failures: tuple[str, ...] = (), successes: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"outcomes": ["fell", "ok"], "failures": list(failures), "successes": list(successes)}


def test_pf4_20_a_kind_the_runs_declare_gives_the_words_without_the_command_line(tmp_path: Path) -> None:
    root = _pair(tmp_path / "prove-runs", STANDARD_A, STANDARD_B,
                 declared_a=_declared(failures=["fell"]), declared_b=_declared(failures=["fell"]))
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    assert doc["verdict"] == "trade"
    assert doc["by_event"]["fell"]["kind"] == "failure"


def test_pf4_20_a_kind_declared_by_one_run_only_is_used(tmp_path: Path) -> None:
    root = _pair(tmp_path / "prove-runs", STANDARD_A, STANDARD_B,
                 declared_b=_declared(failures=["fell"]))
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    assert doc["by_event"]["fell"]["kind"] == "failure"


def test_pf4_20_a_command_line_kind_that_contradicts_a_declaration_is_refused(tmp_path: Path) -> None:
    root = _pair(tmp_path / "prove-runs", STANDARD_A, STANDARD_B,
                 declared_a=_declared(failures=["fell"]), declared_b=_declared(failures=["fell"]))
    agreeing = _cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh")
    assert agreeing.code == 0, agreeing.err
    result = _cli(root, "diff", A_ID, B_ID, "--event", "fell:success", "--method", "fisher_bh")
    assert result.code == 1, (result.code, result.err)
    assert result.out == ""
    assert len([line for line in result.err.splitlines() if line.startswith("error: ")]) == 1
    assert "fell" in result.err


def test_pf4_20_two_runs_declaring_opposite_kinds_are_refused(tmp_path: Path) -> None:
    root = _pair(tmp_path / "prove-runs", STANDARD_A, STANDARD_B,
                 declared_a=_declared(failures=["fell"]), declared_b=_declared(successes=["fell"]))
    for verb in ("diff", "check"):
        result = _cli(root, verb, A_ID, B_ID, "--event", "fell", "--method", "fisher_bh")
        assert result.code == 1, (verb, result.code, result.err)
        assert result.out == ""


DECLARE_SPEC = SMALL_SPEC + '\n[declare]\noutcomes = ["completed", "violated", "timeout"]\n'


def test_pf4_20_a_sweep_spec_declares_failures_and_successes_and_the_manifest_records_them(tmp_path: Path) -> None:
    spec = tmp_path / "spec.toml"
    spec.write_text(DECLARE_SPEC + 'failures = ["violated", "timeout"]\nsuccesses = ["completed"]\n', encoding="utf-8")
    root = tmp_path / "prove-runs"
    result = _cli(root, "sweep", str(spec), "--target", "poisson_prove.examples.mock_agent:rollout",
                  "--max-mde", "0.5", "--yes")
    assert result.code == 0, result.err
    (run,) = Store(root).runs()
    stored = json.loads((root / run / "manifest.json").read_text(encoding="utf-8"))["declared"]
    assert sorted(stored["failures"]) == ["timeout", "violated"]
    assert stored["successes"] == ["completed"]


@pytest.mark.parametrize(
    "extra,named",
    [('failures = ["violated"]\nsuccesses = ["violated"]\n', "violated"), ('failures = ["fell"]\n', "fell")],
    ids=["one-name-in-both", "a-failure-not-among-the-outcomes"],
)
def test_pf4_20_a_declaration_that_contradicts_itself_is_refused_before_the_sweep(
    extra: str, named: str, tmp_path: Path
) -> None:
    spec = tmp_path / "spec.toml"
    spec.write_text(DECLARE_SPEC + extra, encoding="utf-8")
    root = tmp_path / "prove-runs"
    result = _cli(root, "sweep", str(spec), "--target", "poisson_prove.examples.mock_agent:rollout",
                  "--max-mde", "0.5", "--yes")
    assert result.code == 1, (result.code, result.err)
    assert named in result.err
    assert Store(root).runs() == []


def test_pf4_20_a_0_0_1_pair_reads_in_direction_words(tmp_path: Path) -> None:
    import shutil

    root = tmp_path / "old"
    shutil.copytree(OLD / "store", root)
    a, b = OLD_RUNS["quickstart_before"], OLD_RUNS["quickstart_after"]
    doc = _json(_cli(root, "diff", a, b, "--event", "violated", "--event", "timeout", "--method", "fisher_bh", "--json"))
    assert doc["verdict"] in DIRECTION_WORDS
    for event in ("violated", "timeout"):
        assert doc["by_event"][event]["kind"] is None
        assert {c["verdict"] for c in doc["by_event"][event]["cells"]} <= {"higher", "lower", "unchanged"}
    declared = _json(_cli(root, "diff", a, b, "--event", "violated:failure", "--event", "timeout:failure",
                          "--method", "fisher_bh", "--json"))
    assert declared["verdict"] in KNOWN_WORDS


def test_pf4_20_when_one_event_has_a_kind_and_another_does_not_the_comparison_reads_in_direction_words(
    tmp_path: Path,
) -> None:
    import shutil

    root = tmp_path / "old"
    shutil.copytree(OLD / "store", root)
    a, b = OLD_RUNS["quickstart_before"], OLD_RUNS["quickstart_after"]
    doc = _json(_cli(root, "diff", a, b, "--event", "violated:failure", "--event", "timeout",
                     "--method", "fisher_bh", "--json"))
    assert doc["verdict"] in {"mixed", "higher", "lower"}, doc["verdict"]
    assert doc["by_event"]["violated"]["kind"] == "failure"
    assert doc["by_event"]["timeout"]["kind"] is None
    assert {c["verdict"] for c in doc["by_event"]["timeout"]["cells"]} <= {"higher", "lower", "unchanged"}
    assert doc["by_event"]["timeout"]["n_safer"] is None


@pytest.mark.parametrize("row", range(5), ids=["mixed", "higher", "lower", "too-small", "no-change"])
def test_pf4_20_without_a_kind_the_comparison_word_is_a_direction_word(row: int, tmp_path: Path) -> None:
    name, a, b, known = _rows_of_8_4()[row]
    expected = {"trade": "mixed", "worse": "higher", "safer": "lower"}.get(known, known)
    root = _pair(tmp_path / "prove-runs", a, b)
    assert _one_word(_verdicts(root, tmp_path, "fell")) == expected, name


# ---------- PF4.34, PF4.35: the word counts Holm's rows; every surface names both rules ----------


def _argon_pair(root: Path, **kw: Any) -> Path:
    """Nine conditions fell far, twenty did not move, one rose by a step-up margin (0 to 7 of 40): the
    rise is flagged by Benjamini-Hochberg and does not count at the family-wise level."""
    a = {f"down{i}": _arm(30, 40) for i in range(9)}
    b = {f"down{i}": _arm(2, 40) for i in range(9)}
    for i in range(20):
        a[f"same{i:02d}"] = b[f"same{i:02d}"] = _arm(5, 40)
    a["up"], b["up"] = _arm(0, 40), _arm(7, 40)
    return _pair(root, a, b, **kw)


@pytest.mark.parametrize("event,word", [("fell:failure", "safer"), ("fell", "lower")], ids=["failure", "no-kind"])
def test_pf4_34_a_step_up_flag_does_not_turn_the_word_into_a_trade_on_any_surface(event: str, word: str, tmp_path: Path) -> None:
    root = _argon_pair(tmp_path / "prove-runs")
    assert _one_word(_verdicts(root, tmp_path, event)) == word
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", event, "--method", "fisher_bh", "--json"))
    assert doc["n_flagged_only"] == 1
    up = _cells_of(doc)[_hash("up")]
    assert up["q"] < Q and up["holm"] is False and up["direction"] == "higher"
    text = _cli(root, "diff", A_ID, B_ID, "--event", event, "--method", "fisher_bh").out
    (line,) = _detail(text, "flagged only")
    assert re.search(r"(?<![\d.])1(?![\d.])", line) and _says(line, "family-wise"), line


@pytest.mark.parametrize("fail_on,code", [("higher", 0), ("lower", 4), ("any", 4)])
def test_pf4_34_check_fails_on_the_rows_that_count_not_the_flags(fail_on: str, code: int, tmp_path: Path) -> None:
    """Reading R2: on Argon's pair the rise is flagged and does not count, the nine falls count. check
    gates on the rows that count, so ``--fail-on higher`` passes."""
    root = _argon_pair(tmp_path / "prove-runs")
    result = _cli(root, "check", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--fail-on", fail_on)
    assert result.code == code, (fail_on, result.code, result.err)
    assert _first_word(result.out) == ("passed" if code == 0 else "failed")


def test_pf4_35_every_surface_names_the_flags_rule_and_the_verdicts(standard: Path, tmp_path: Path) -> None:
    s = _surfaces(standard, tmp_path, "fell:failure")
    for name, text in _texts(s).items():
        for words in ("Benjamini", "Hochberg", "false discovery rate", "Holm", "family-wise"):
            assert _says(text, words), (name, words)
    for name in ("diff --json", "check --json", "report --json"):
        doc = s[name]
        assert (doc["flag_rule"], doc["verdict_rule"]) == ("benjamini-hochberg", "holm"), name
        ev = doc["by_event"]["fell"]
        assert (ev["n_holm_higher"], ev["n_holm_lower"], ev["n_holm_safer"], ev["n_holm_worse"]) == (1, 1, 1, 1), name
        for c in ev["cells"]:
            assert isinstance(c["q_holm"], float) and isinstance(c["holm"], bool), name
    assert s["page"]["panels"][0]["flag_rule"] == "benjamini-hochberg" and s["page"]["summary"]["verdict_rule"] == "holm"


# ---------- PF4.38: one case per condition ----------


@pytest.mark.parametrize("verb", ["diff", "check", "report", "serve"])
def test_pf4_38_a_comparison_whose_condition_ran_several_cases_is_refused_on_every_verb(verb: str, tmp_path: Path) -> None:
    rows = _arm(5, 20)
    root = tmp_path / "prove-runs"
    _write_run(root, A_ID, {"c": rows, "d": rows}, meta={"c": {"case_id": "t1"}, "d": {"case_id": "t2"}})
    _write_run(root, B_ID, {"c": rows, "d": rows}, meta={"c": {"case_id": "t3"}, "d": {"case_id": "t2"}},
               created_at="2026-10-20T10:01:00Z")
    # Reading R5: the store copies each rollout's case id into its own column, read without decoding meta.
    assert {str(v) for v in Store(root).read(B_ID, meta=False)["case_id"]} == {"t3", "t2"}
    argv = [verb, A_ID, B_ID, "--event", "fell", "--method", "fisher_bh"]
    argv += {"report": ["--x", "cell", "--out", str(tmp_path / "r")], "serve": ["--x", "cell", "--json"],
             "check": ["--fail-on", "any"]}.get(verb, [])
    result = _cli(root, *argv)
    assert result.code == 1 and result.out == "", (result.code, result.err)
    errors = [line for line in result.err.splitlines() if line.startswith("error: ")]
    nexts = [line for line in result.err.splitlines() if line.startswith("  next:")]
    assert len(errors) == 1 and "cell c" in errors[0], errors
    assert re.search(r"\b2\b", errors[0]) and "t1" in errors[0] and "t3" in errors[0], errors[0]
    assert any("axis" in line for line in nexts) and any("your-own-agent" in line for line in nexts), nexts
    one_case = tmp_path / "one"
    _write_run(one_case, A_ID, {"c": rows}, meta={"c": {"case_id": "t1"}})
    _write_run(one_case, B_ID, {"c": rows}, meta={"c": {"case_id": "t1"}}, created_at="2026-10-20T10:01:00Z")
    assert _cli(one_case, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh").code == 0


# ---------- PF4.39: resume records peeking, and every surface says so ----------


def _sweep(cwd: Path, *argv: str) -> Result:
    result = _cli(cwd / "prove-runs", "sweep", *argv, "--yes")
    return result


def test_pf4_39_a_partial_run_compared_then_resumed_carries_the_peeking_caveat_on_every_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    spec = cwd / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    target = ["--target", "poisson_prove.examples.mock_agent:rollout", "--max-mde", "0.5"]
    assert _sweep(cwd, str(spec), *target).code == 0
    stopped = _sweep(cwd, str(spec), *target, "--max-rollouts", "30")
    assert stopped.code == 3, stopped.err
    store = Store(cwd / "prove-runs")
    (partial,) = [r for r in store.runs() if store.manifest(r).status == "partial"]
    (first,) = [r for r in store.runs() if r != partial]
    names = {r["run_id"]: r["run_name"] for r in _json(_cli(cwd / "prove-runs", "runs", "--json"))["runs"]}

    def listing() -> list[tuple[str, int]]:
        return sorted((str(p.relative_to(cwd)), p.stat().st_size) for p in (cwd / "prove-runs").rglob("*") if p.is_file())

    before = listing()
    early = _json(_cli(cwd / "prove-runs", "diff", first, partial, "--event", "completed", "--method", "fisher_bh", "--json"))
    assert listing() == before  # the read record is not in the store
    assert [(p["run_id"], p["reason"]) for p in early["peeking"]] == [(partial, "partial")]
    record = Path(os.environ["HOME"]) / ".cache" / "poisson-prove" / "compared.jsonl"
    lines = [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()]
    assert {line["run_id"] for line in lines} == {first, partial}
    spec.write_text(SMALL_SPEC.replace("replicates = 30", "replicates = 40"), encoding="utf-8")
    resumed = _sweep(cwd, str(spec), "--resume", partial)
    assert resumed.code == 0, resumed.err
    (entry,) = store.manifest(partial).environment["resumes"]
    assert entry["after_comparison"] is True and entry["episodes_before"] == 30 and entry["episodes_after"] == 80
    assert (entry["replicates_before"], entry["replicates_after"]) == (30, 40) and isinstance(entry["at"], str)
    out = cwd / "r"
    assert _cli(cwd / "prove-runs", "report", first, partial, "--event", "completed", "--method", "fisher_bh",
                "--x", "task_id", "--out", str(out)).code == 0
    page = _json(_cli(cwd / "prove-runs", "serve", first, partial, "--event", "completed", "--method", "fisher_bh",
                      "--x", "task_id", "--json"))
    surfaces = {
        "diff": _cli(cwd / "prove-runs", "diff", first, partial, "--event", "completed", "--method", "fisher_bh").out,
        "check": _cli(cwd / "prove-runs", "check", first, partial, "--event", "completed", "--method", "fisher_bh",
                      "--fail-on", "any").out,
        "report.md": (out / "report.md").read_text(encoding="utf-8"),
        "receipt.html": _strip_tags((out / "receipt.html").read_text(encoding="utf-8")),
        "page": _page_text(page),
    }
    for name, text in surfaces.items():
        lines_with = [line for line in text.splitlines() if "peeking" in line.lower()]
        assert lines_with and any(names[partial] in line for line in lines_with), (name, lines_with)
    for name in ("diff", "check"):
        assert any(names[partial] in v for v in _detail(surfaces[name], "peeking")), name
    assert [(p["run_id"], p["reason"]) for p in page["summary"]["peeking"]] == [(partial, "resumed after a comparison")]


def test_pf4_39_a_resume_with_no_comparison_before_it_is_recorded_without_a_caveat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "work"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    spec = cwd / "spec.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    target = ["--target", "poisson_prove.examples.mock_agent:rollout", "--max-mde", "0.5"]
    assert _sweep(cwd, str(spec), *target).code == 0
    assert _sweep(cwd, str(spec), *target, "--max-rollouts", "30").code == 3
    store = Store(cwd / "prove-runs")
    (partial,) = [r for r in store.runs() if store.manifest(r).status == "partial"]
    (first,) = [r for r in store.runs() if r != partial]
    assert _sweep(cwd, str(spec), "--resume", partial).code == 0
    (entry,) = store.manifest(partial).environment["resumes"]
    assert entry["after_comparison"] is False and (entry["episodes_before"], entry["episodes_after"]) == (30, 60)
    doc = _json(_cli(cwd / "prove-runs", "diff", first, partial, "--event", "completed", "--method", "fisher_bh", "--json"))
    assert doc["peeking"] == []
    assert _detail(_cli(cwd / "prove-runs", "diff", first, partial, "--event", "completed", "--method", "fisher_bh").out, "peeking") == []


# ---------- PF4.40: "no significant change" always carries its limit ----------


def test_pf4_40_no_significant_change_prints_its_limit_on_the_same_line_everywhere(tmp_path: Path) -> None:
    root = _pair(tmp_path / "prove-runs", MID, MID, environment_a={"max_mde_accepted": 0.3}, environment_b={"max_mde_accepted": 0.3})
    s = _surfaces(root, tmp_path, "fell:failure")
    limit = s["diff --json"]["verdict_limit"]
    rise, fall = _ref_fisher_limits(30, 60, 60, Q / 2)
    assert rise is not None and fall is not None and abs(limit - max(rise, fall)) <= 1e-4 + 1e-12
    assert s["diff --json"]["verdict"] == "no significant change"
    # Reading R34: check's word is passed or failed, so its block names the comparison's word.
    (compared,) = _detail(s["check"].out, "comparison")
    assert compared.startswith("no significant change"), compared
    for name, text in _texts(s).items():
        lines = [line for line in text.splitlines() if "no significant change" in line]
        assert lines, name
        for line in lines:
            assert f"{limit:.3f}" in line, (name, line)
    assert s["page"]["summary"]["verdict_limit"] == limit and s["report --json"]["verdict_limit"] == limit


# ---------- PF4.41: log-rank names the cause-specific hazard ----------


def test_pf4_41_logrank_is_labelled_the_cause_specific_hazard_and_a_shifted_competitor_is_noted(tmp_path: Path) -> None:
    def arm(fell: int, stuck: int, n: int) -> list[tuple[int, str | None, float]]:
        return [(i, "fell", 3.0) if i < fell else (i, "stuck", 2.0) if i < fell + stuck else (i, "ok", HORIZON) for i in range(n)]

    root = _pair(tmp_path / "prove-runs", {"c": arm(10, 5, 60), "quiet": arm(10, 5, 60)},
                 {"c": arm(10, 25, 60), "quiet": arm(10, 5, 60)}, salt="unshared")
    s = _surfaces(root, tmp_path, "fell", method="logrank_bh")
    for name, text in _texts(s).items():
        assert _says(text, "cause-specific hazard"), name
    # In the method line and the headline themselves, not only in a note.
    assert _says(s["diff --json"]["headline"], "cause-specific hazard"), s["diff --json"]["headline"]
    (method,) = _detail(s["diff"].out, "method")
    headline = next(line for line in s["diff"].out.splitlines() if line.startswith("(aalen_johansen + logrank_bh"))
    assert _says(headline, "cause-specific hazard"), headline
    assert "log-rank" in method or "logrank" in method, method
    c = _cells_of(s["diff --json"])[_hash("c")]
    assert c["competing_shift"] == ["ok", "stuck"]
    assert _cells_of(s["diff --json"])[_hash("quiet")]["competing_shift"] == []
    (line,) = _detail(s["diff"].out, "competing")
    assert "stuck" in line, line
    for name in ("report.md", "page"):
        assert "stuck" in _texts(s)[name], name


# ---------- PF4.42: the interval on the change, on every row and every surface ----------


@pytest.mark.parametrize("method,name", [("fisher_bh", "Miettinen-Nurminen"), ("mcnemar_bh", "Tango")])
def test_pf4_42_every_comparison_carries_an_interval_on_each_change_labelled_with_its_level(method: str, name: str, standard: Path, tmp_path: Path) -> None:
    s = _surfaces(standard, tmp_path, "fell", method=method)
    doc = s["diff --json"]
    m, r = doc["n_tests"], doc["n_rejected"]
    level = 1 - Q * max(r, 1) / m
    assert abs(doc["interval_level"] - level) <= 1e-15 and len(doc["intervals"]) == m
    for c in doc["by_event"]["fell"]["cells"]:
        assert c["ci_method"] == name.lower() and abs(c["ci_level"] - level) <= 1e-15
        assert c["ci_lo"] <= c["delta"] <= c["ci_hi"]
    label = f"{level * 100:.3f}".rstrip("0").rstrip(".") + "%"  # a percentage to at most three decimals
    for surface, text in _texts(s).items():
        if surface == "check":
            continue
        assert label in text and _says(text, name), (surface, label)
        assert _says(text, "Benjamini-Yekutieli" if r else "Bonferroni"), surface
    same = _cells_of(doc)[_hash("same")]
    row = _row(s["diff"].out, "same")
    assert f"{same['ci_lo']:.3f}" in row and f"{same['ci_hi']:.3f}" in row, row


def test_pf4_42_with_nothing_flagged_the_intervals_are_simultaneous(tmp_path: Path) -> None:
    root = _pair(tmp_path / "prove-runs", MID, MID)
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    assert doc["n_rejected"] == 0 and doc["interval_rule"] == "bonferroni"
    assert abs(doc["interval_level"] - (1 - Q / 2)) <= 1e-15 and len(doc["intervals"]) == 2
    text = _cli(root, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh").out
    assert _says(text, "simultaneous") and _says(text, "Bonferroni")


# ---------- PF4.44: fragility on every surface that shows the word ----------


def test_pf4_44_every_surface_that_shows_the_word_shows_how_many_outcomes_would_change_it(standard: Path, tmp_path: Path) -> None:
    s = _surfaces(standard, tmp_path, "fell:failure")
    doc = s["diff --json"]
    fragility = doc["fragility"]
    assert isinstance(fragility, int) and fragility >= 1 and len(doc["fragility_flips"]) == fragility
    for flip in doc["fragility_flips"]:
        assert set(flip) >= {"config_hash", "event", "run", "replicate_index", "to"}
    for name in ("check --json", "report --json"):
        assert s[name]["fragility"] == fragility and s[name]["fragility_flips"] == doc["fragility_flips"], name
    assert s["page"]["summary"]["fragility"] == fragility
    for name, text in _texts(s).items():
        lines = [line for line in text.splitlines() if "fragility" in line.lower()]
        assert any(re.search(rf"(?<![\d.]){fragility}(?![\d.])", line) for line in lines), (name, lines)
    for name in ("diff", "check"):
        assert len(_detail(s[name].out, "fragility")) == 1, name


# ---------- PF4.45: the group limit says it is unconditional ----------


def test_pf4_45_the_group_limit_is_labelled_unconditional_where_it_is_printed(tmp_path: Path) -> None:
    """On the lattice pair's fault lines (grouped by ``load``): the JSON says how the group limit's
    power is read, and the report's fault-lines section says the root and the group both reject."""
    pair = lattice.root()
    out = tmp_path / "r"
    doc = _json(_cli(pair, "diff", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--method", "fisher_bh", "--json"))
    assert doc["tree"]["fault_lines"]["mde_basis"] == "unconditional"
    assert doc["tree"]["fault_lines"]["tested"] is True
    assert _cli(pair, "report", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--method", "fisher_bh",
                "--x", lattice.X, "--y", lattice.Y, "--out", str(out)).code == 0
    section = (out / "report.md").read_text(encoding="utf-8").split("## Fault lines", 1)[1].split("\n## ", 1)[0]
    assert _says(section, "unconditional")


# ---------- PF4.46: errored episodes that differ between the runs ----------


def test_pf4_46_a_warning_names_the_conditions_whose_errors_differ_on_every_surface(tmp_path: Path) -> None:
    a = {"c": _arm(5, 40), "d": _arm(5, 40)}
    b = {"c": _arm(5, 30) + [(30 + i, None, 1.0) for i in range(10)], "d": _arm(5, 40)}
    root = _pair(tmp_path / "prove-runs", a, b)
    s = _surfaces(root, tmp_path, "fell")
    (entry,) = s["diff --json"]["errors_differ"]
    assert entry["config_hash"] == _hash("c") and (entry["errored_a"], entry["errored_b"]) == (0, 10)
    assert entry["rows_a"] == 40 and entry["rows_b"] == 40
    for name, text in _texts(s).items():
        assert "errored" in text, name
    assert len(_detail(s["diff"].out, "errors")) == 1
    assert s["page"]["summary"]["errors_differ"] == s["diff --json"]["errors_differ"]


# ---------- PF4.47: the keys of outcomes that move together ----------


def test_pf4_47_complementary_rows_name_each_other_in_every_json(tmp_path: Path) -> None:
    root = _pair(tmp_path / "prove-runs", {"c": _arm(12, 60)}, {"c": _arm(12, 60)})
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell", "--event", "ok", "--method", "fisher_bh", "--json"))
    fell, ok = _cells_of(doc, "fell")[_hash("c")], _cells_of(doc, "ok")[_hash("c")]
    assert (fell["mde_moves_with"], ok["mde_moves_with"]) == ("ok", "fell")
    assert abs(fell["mde_level"] - 2 * Q / 2) <= 1e-15
    for c in (fell, ok):
        assert isinstance(c["mde_rise_verdict"], float) and isinstance(c["mde_fall_verdict"], float)


# ---------- PF4.49: --max-mde 1 admits a design that can detect nothing ----------


def test_pf4_49_a_design_that_cannot_flag_is_refused_below_1_and_admitted_at_1_with_a_note(tmp_path: Path) -> None:
    spec = tmp_path / "spec.toml"
    spec.write_text(SMALL_SPEC.replace("replicates = 30", "replicates = 2"), encoding="utf-8")
    target = ["--target", "poisson_prove.examples.mock_agent:rollout"]
    refused = _cli(tmp_path / "prove-runs", "sweep", str(spec), *target, "--max-mde", "0.99", "--yes")
    assert refused.code == 1, refused.err
    errors = [line for line in refused.err.splitlines() if line.startswith("error: ")]
    assert len(errors) == 1 and "flagged" in errors[0], errors
    nexts = [line for line in refused.err.splitlines() if line.startswith("  next:")]
    assert re.search(r"--replicates \d+", nexts[0]), nexts
    assert not any(re.search(r"--max-mde (?!0\.99\b)", line) for line in nexts), nexts  # no --max-mde offer
    admitted = _cli(tmp_path / "prove-runs", "sweep", str(spec), *target, "--max-mde", "1", "--yes")
    assert admitted.code == 0, admitted.err
    notes = [line for line in admitted.err.splitlines() if line.startswith("note: ")]
    assert any("flagged" in line for line in notes), notes
    (run,) = Store(tmp_path / "prove-runs").runs()
    assert Store(tmp_path / "prove-runs").manifest(run).environment["design_mde"]["flaggable"] is False
    over = _cli(tmp_path / "prove-runs", "sweep", str(spec), *target, "--max-mde", "1.01", "--yes")
    assert over.code in (1, 2) and Store(tmp_path / "prove-runs").runs() == [run]
