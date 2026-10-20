"""PF4, completeness: the frozen tests of what a user reads.

Written from the front-door spec's section 8 (8.2 to 8.5) and its invariants PF4.1b to PF4.20 as
they are read on a screen or in a file: ``diff``, ``check``, ``report`` and ``serve`` (text and
``--json``), ``report.md``, ``receipt.html``, the page and its Summary, ``paired``, and what a sweep
records. ``tests/test_pf4_stats.py`` holds the numbers underneath. The build is written against
this file and does not edit it.

**What this file can rely on, and what it cannot.** Other modules are built in parallel from the
same base. These tests name runs by their ids (run names are PF2's), always pass ``--method``
(the paired default is PF3's), and read the verdict word from ``--json`` and from the first stdout
line (the line's form is PF1's and PF2's; the word is PF4's). Each surface is reached through the
command line in process, with ``HOME`` pointed at an empty folder.

**Readings, named here** (each is a yes/no in the session log).

- The comparison's verdict word is carried as ``verdict`` in ``diff --json``, as
  ``comparison_verdict`` in ``report --json`` (whose own ``verdict`` is the verb's ``ok``), as
  ``verdict`` in the page Summary (``summary.verdict`` in ``serve --json``), and in ``report.md``
  as the first line after the title and its blank line, in the ``word  sentence`` form ``diff``
  prints. ``diff --json`` also carries ``threshold`` and ``threshold_source`` (``recorded``,
  ``smaller`` or ``default``) for section 8.4's threshold.
- An event's kind on the command line is ``--event NAME:failure`` or ``--event NAME:success``; in a
  run it is the declaration's ``failures`` and ``successes`` lists, which the manifest stores under
  ``declared``.
- The single-run ``report --json`` carries ``by_event``, one entry per event, whose ``cells`` each
  hold ``config``, ``share`` (the interval object), ``incidence`` (the cumulative incidence at the
  horizon) and ``share_differs``; and ``design_mde``, an object with ``mde``, ``base_rate`` and
  ``computed_at_read_time``. A sweep records its design MDE in ``manifest.environment["design_mde"]``
  (where ``max_mde_accepted`` already lives) as ``{"mde", "base_rate"}``.
- PF4.1c's patched constant is ``poisson_prove.stats.WILSON_LEVEL``, read when a surface computes,
  so patching the module attribute moves every surface.
- A share counts the runs whose stored outcome is the event, over the runs with an outcome, so
  a run's share counts events after a shorter partner's horizon that its rate at the common
  horizon does not; each cell carries ``share_a_differs`` and ``share_b_differs``, and the text
  row marks a differing share with ``*``. The same mark is used in the single-run report.
- Binding words, pinned as words: ``ceiling`` and ``none detectable`` for a condition with no
  detection limit, ``not adjusted`` in the share caption, ``read time`` for a design MDE computed
  from an old run, and ``Wilson``, ``incidence`` and the level label in the single-run header.
- ``diff``'s first stdout line is PF2's verdict line (PF2.9); PF4 gives it its word. The tests
  that read the word there (``_first_word``) assume PF4 is built on PF2's tip, as the builds
  stack; built alone, PF4 writes that line itself.
- PF4.11 reads "any ``--json``" as every comparison verb's (``diff``, ``check``, ``report``,
  ``serve``) and ``runs --json``; ``inspect``'s reproduce line keeps the target's import path,
  because reproducing the episode is what it is for.

**Lanes.** The tests that sweep (PF4.4, PF4.20's declaration) and the capture subprocess (PF4.10)
take a few seconds each; the rest run in process on hand-built stores.
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
from poisson_prove.diff import mde_two_proportion
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = Path(__file__).resolve().parent
OLD = TESTS / "fixtures" / "stores-0.0.1"
OLD_RUNS: dict[str, str] = json.loads((OLD / "runs.json").read_text(encoding="utf-8"))

A_ID = "20261020T100000Z-aaaa"
B_ID = "20261020T100100Z-bbbb"
SALT = "pf4-shared-salt"
HORIZON = 10.0
#: Rule 3's verdict line: a lowercase word or phrase, two spaces, then the sentence.
FIRST_LINE = re.compile(r"^([a-z][a-z ]*?)  \S")
JUDGEMENT = re.compile(r"\b(safer|worse)\b", re.IGNORECASE)
KNOWN_WORDS = {"trade", "worse", "safer", "too small to tell", "no significant change"}
DIRECTION_WORDS = {"mixed", "higher", "lower", "too small to tell", "no significant change"}


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


def _strings(node: Any) -> list[str]:
    """Every string value in a JSON document, keys left out."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for value in node.values() for s in _strings(value)]
    if isinstance(node, list):
        return [s for value in node for s in _strings(value)]
    return []


# ---------- stores, built by hand ----------


def _arm(k: int, n: int, *, start: float = 1.0, step: float = 0.1) -> list[tuple[int, str, float]]:
    """``n`` runs of which the first ``k`` fell, at ``start``, ``start + step``, ...; the rest end
    ``ok`` at the horizon."""
    return [(i, "fell", start + step * i) if i < k else (i, "ok", HORIZON) for i in range(n)]


def _write_run(
    root: Path,
    run_id: str,
    cells: dict[str, list[tuple[int, str, float]]],
    *,
    salt: str = SALT,
    environment: dict[str, Any] | None = None,
    declared: dict[str, Any] | None = None,
    created_at: str = "2026-10-20T10:00:00Z",
    horizon: float = HORIZON,
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
    records = [
        EpisodeRecord(
            run_id=run_id,
            config_hash=config_hash({"cell": name}),
            config={"cell": name},
            seed=1000 + rep,
            replicate_index=rep,
            outcome=outcome,
            t=t,
            horizon=horizon,
            confidence=None,
            meta={},
            error=None,
            wall_time=0.01,
            backend_meta={},
        )
        for name, rows in cells.items()
        for rep, outcome, t in rows
    ]
    store.append(run_id, records)
    store.mark_complete(run_id)
    if declared is not None:
        # The stored form of a declaration, written as the manifest keeps it.
        path = root / run_id / "manifest.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["declared"] = {"steps": [], "gates": [], **declared}
        path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")


def _pair(
    root: Path,
    a: dict[str, list[tuple[int, str, float]]],
    b: dict[str, list[tuple[int, str, float]]],
    **kw: Any,
) -> Path:
    env_a = kw.pop("environment_a", None)
    env_b = kw.pop("environment_b", None)
    decl_a = kw.pop("declared_a", None)
    decl_b = kw.pop("declared_b", None)
    _write_run(root, A_ID, a, environment=env_a, declared=decl_a, created_at="2026-10-20T10:00:00Z", **kw)
    _write_run(root, B_ID, b, environment=env_b, declared=decl_b, created_at="2026-10-20T10:01:00Z", **kw)
    return root


#: Six conditions, 40 runs an arm: one whose rate rose significantly ("up"), one where it fell
#: ("down"), one unchanged, one whose
#: baseline fell in every run, one at 38 of 40 where no rise is detectable, and one at zero.
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
    found by the nearest header above it."""
    lines = text.splitlines()
    short = _hash(name)[:12]
    for i, line in enumerate(lines):
        if short in line and line.startswith("|"):
            for header in reversed(lines[:i]):
                if header.startswith("| config_hash"):
                    names = [h.strip() for h in header.strip("|").split("|")]
                    values = [v.strip() for v in line.strip("|").split("|")]
                    return values[names.index(column)]
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


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


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
    files += [path for path in sorted(package.glob("*.py"))
              if path not in files and re.search(r"^\s*(import|from) rich\b", path.read_text(encoding="utf-8"), re.M)]
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "95%" not in text, path.name
        assert not re.search(r"(?<![\d.])1\.96(?!\d)", text), path.name


# ---------- PF4.2: the single-run report shows the share, its interval and the incidence ----------


def test_pf4_2_the_single_run_report_prints_each_share_with_its_interval_and_the_incidence(
    standard: Path, tmp_path: Path
) -> None:
    result = _cli(standard, "report", A_ID, "--event", "fell", "--x", "cell", "--out", str(tmp_path / "r"))
    assert result.code == 0, result.err
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert "95%" in md
    assert "Wilson" in md
    assert "incidence" in md
    for name, rows in STANDARD_A.items():
        k = sum(1 for _, o, _ in rows if o == "fell")
        assert _interval_text(k, len(rows)) in md, name


def test_pf4_2_a_condition_whose_share_is_not_its_incidence_is_marked_and_explained(
    standard: Path, tmp_path: Path
) -> None:
    """At ``--horizon 2`` the incidence counts only falls by step 2, while the share counts every
    fall the run recorded; three of the six conditions fall after step 2."""
    doc = _json(_cli(standard, "report", A_ID, "--event", "fell", "--x", "cell", "--horizon", "2",
                     "--out", str(tmp_path / "r"), "--json"))
    cells = {c["config"]["cell"]: c for c in doc["by_event"]["fell"]["cells"]}
    expected = {"down": 11 / 40, "top": 11 / 40, "near_top": 11 / 40}
    for name, c in cells.items():
        if name in expected:
            assert c["share_differs"] is True, name
            assert abs(c["incidence"] - expected[name]) <= 1e-12, (name, c["incidence"])
        else:
            assert c["share_differs"] is False, name
            assert abs(c["incidence"] - c["share"]["value"]) <= 1e-12, name
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    for name in cells:
        k = sum(1 for _, o, _ in STANDARD_A[name] if o == "fell")
        rows = [line for line in md.splitlines() if _interval_text(k, 40) in line and name in line]
        assert rows, name
        assert ("*" in rows[0]) is (name in expected), (name, rows[0])
    plain = _json(_cli(standard, "report", A_ID, "--event", "fell", "--x", "cell",
                       "--out", str(tmp_path / "s"), "--json"))
    assert not any(c["share_differs"] for c in plain["by_event"]["fell"]["cells"])


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


def test_pf4_3_the_two_run_report_prints_the_shares(standard: Path, tmp_path: Path) -> None:
    result = _cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
                  "--out", str(tmp_path / "r"))
    assert result.code == 0, result.err
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert _interval_text(30, 40) in md and _interval_text(4, 40) in md
    assert "95%" in md


def test_pf4_3_the_caption_says_the_intervals_are_per_condition_and_not_adjusted(standard: Path, tmp_path: Path) -> None:
    diff_text = _cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh").out
    _cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
         "--out", str(tmp_path / "r"))
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    for text in (diff_text, md):
        assert "not adjusted" in text


def test_pf4_3_a_share_that_is_not_its_rate_is_marked_beside_the_rate(tmp_path: Path) -> None:
    """A ran to step 10 and B to step 5, so the comparison's horizon is 5. In 'late' half of A's
    runs fell after step 5: A's rate at the horizon is 0 while its share of runs that ended in the
    event is 0.500. In 'early' every fall is by step 5 and the two agree."""
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
    assert late["rate_a"] == 0.0
    _assert_share(late["share_a"], 20, 40)
    assert late["share_a_differs"] is True and late["share_b_differs"] is False
    assert early["share_a_differs"] is False and early["share_b_differs"] is False
    text = _cli(root, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh").out
    assert "*" in _row(text, "late") and "*" not in _row(text, "early")


# ---------- PF4.4: the design MDE is recorded and printed ----------


def _statsmodels_design_mde(n: int) -> float:
    """The smallest rise from a base rate of 0.5 detectable with ``n`` runs an arm at q = 0.05 and
    power 0.8, by bisection on statsmodels' documented ``power_proportions_2indep(diff, prop2,
    nobs1, ratio)``."""
    from statsmodels.stats.proportion import power_proportions_2indep

    lo, hi = 0.0, 0.5
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        power = power_proportions_2indep(mid, 0.5, n, ratio=1.0, alpha=0.05, return_results=False)
        if power >= 0.8:
            hi = mid
        else:
            lo = mid
    return hi

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


def test_pf4_4_a_new_run_records_its_design_mde_and_base_rate(swept: tuple[Path, str]) -> None:
    root, run = swept
    env = Store(root).manifest(run).environment
    assert env["design_mde"]["base_rate"] == 0.5
    assert abs(env["design_mde"]["mde"] - _statsmodels_design_mde(30)) <= 1e-7


def test_pf4_4_the_single_run_report_prints_the_recorded_design_mde(swept: tuple[Path, str], tmp_path: Path) -> None:
    root, run = swept
    doc = _json(_cli(root, "report", run, "--event", "completed", "--x", "task_id",
                     "--out", str(tmp_path / "r"), "--json"))
    expected = _statsmodels_design_mde(30)
    assert abs(doc["design_mde"]["mde"] - expected) <= 1e-7
    assert doc["design_mde"]["base_rate"] == 0.5
    assert doc["design_mde"]["computed_at_read_time"] is False
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert f"{expected:.3f}" in md.split("##")[0]


def test_pf4_4_a_0_0_1_runs_design_mde_is_computed_at_read_time_and_says_so(tmp_path: Path) -> None:
    import shutil

    root = tmp_path / "old"
    shutil.copytree(OLD / "store", root)
    run = OLD_RUNS["quickstart_before"]
    doc = _json(_cli(root, "report", run, "--event", "violated", "--x", "task_id", "--y", "tool_fail_rate",
                     "--out", str(tmp_path / "r"), "--json"))
    expected = _statsmodels_design_mde(100)  # the run recorded 100 replicates
    assert abs(doc["design_mde"]["mde"] - expected) <= 1e-7
    assert doc["design_mde"]["computed_at_read_time"] is True
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert f"{expected:.3f}" in md.split("##")[0]
    assert "read time" in md


# ---------- PF4.5: one verdict rule on every surface ----------


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


#: One constructed pair per row of section 8.4's table, the event declared a failure on the
#: command line. n = 200 gives every unchanged condition a limit near 0.09; n = 20 one near 0.4.
def _rows_of_8_4() -> list[tuple[str, dict[str, Any], dict[str, Any], str]]:
    return [
        ("trade", {"w": _arm(4, 40), "s": _arm(30, 40)}, {"w": _arm(30, 40), "s": _arm(4, 40)}, "trade"),
        ("worse", {"w": _arm(4, 40), "u": _arm(5, 200)}, {"w": _arm(30, 40), "u": _arm(5, 200)}, "worse"),
        ("safer", {"s": _arm(30, 40), "u": _arm(5, 200)}, {"s": _arm(4, 40), "u": _arm(5, 200)}, "safer"),
        ("too small", {"u": _arm(10, 20), "v": _arm(10, 20)}, {"u": _arm(10, 20), "v": _arm(10, 20)},
         "too small to tell"),
        ("no change", {"u": _arm(20, 200), "v": _arm(5, 200)}, {"u": _arm(20, 200), "v": _arm(5, 200)},
         "no significant change"),
    ]


@pytest.mark.parametrize("row", range(5), ids=["trade", "worse", "safer", "too-small", "no-change"])
def test_pf4_5_every_surface_gives_the_same_word_by_section_8_4s_table(row: int, tmp_path: Path) -> None:
    name, a, b, word = _rows_of_8_4()[row]
    root = _pair(tmp_path / "prove-runs", a, b)
    assert _one_word(_verdicts(root, tmp_path, "fell:failure")) == word, name


def test_pf4_5_a_condition_that_trades_two_events_counts_as_both(tmp_path: Path) -> None:
    """One condition: 'fell' falls and 'stuck' rises, both significantly; nothing else moves."""
    a_rows = [(i, "fell", 1.0 + 0.01 * i) if i < 30 else (i, "stuck", 2.0) if i < 34 else (i, "ok", HORIZON)
              for i in range(60)]
    b_rows = [(i, "fell", 1.0 + 0.01 * i) if i < 4 else (i, "stuck", 2.0) if i < 34 else (i, "ok", HORIZON)
              for i in range(60)]
    quiet = [(i, "ok", HORIZON) for i in range(60)]
    root = _pair(tmp_path / "prove-runs", {"c": a_rows, "quiet": quiet}, {"c": b_rows, "quiet": quiet})
    assert _one_word(_verdicts(root, tmp_path, "fell:failure", "stuck:failure")) == "trade"


#: Every unchanged condition at n = 60 and a rate of 0.5: a limit between 0.20 and 0.30.
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
    assert 0.20 < mde_two_proportion(0.5, 60, 60) < 0.30  # the construction these rows rest on
    root = _pair(tmp_path / "prove-runs", MID, MID, environment_a=env_a, environment_b=env_b)
    assert _one_word(_verdicts(root, tmp_path, "fell:failure")) == word
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh", "--json"))
    assert doc["threshold"] == threshold
    assert doc["threshold_source"] == source
    text = _cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh").out
    block = text.split("\n\n")[0]
    assert f"{threshold:.3f}" in block, block


def test_pf4_5_the_page_summarys_50_point_rule_is_gone(tmp_path: Path) -> None:
    """A largest unchanged limit near 0.25, under the old page rule's 0.50 and above the default
    0.20: the page says too small to tell, as every other surface does."""
    root = _pair(tmp_path / "prove-runs", MID, MID, environment_a={}, environment_b={})
    page = _json(_cli(root, "serve", A_ID, B_ID, "--event", "fell:failure", "--method", "fisher_bh",
                      "--x", "cell", "--json"))
    assert page["summary"]["verdict"] == "too small to tell"
    (entry,) = page["summary"]["events"]
    assert entry["limit"]["label"] == "too small to tell"


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


def test_pf4_7_diff_on_a_pair_with_no_comparable_condition_is_refused_naming_the_holes(tmp_path: Path) -> None:
    a = {"c1": _arm(4, 20), "c2": _arm(4, 20), "c3": _arm(4, 20)}
    b = {"d1": _arm(4, 20), "d2": _arm(4, 20)}
    root = _pair(tmp_path / "prove-runs", a, b)
    for argv in (["diff"], ["diff", "--json"]):
        result = _cli(root, argv[0], A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", *argv[1:])
        assert result.code == 1, (result.code, result.out, result.err)
        assert result.out == ""
        lines = result.err.splitlines()
        errors = [line for line in lines if line.startswith("error: ")]
        assert len(errors) == 1, lines
        assert all(line.startswith(("error: ", "  next:", "note: ")) for line in lines), lines
        assert re.search(r"\b3\b", errors[0]) and re.search(r"\b2\b", errors[0]), errors[0]
        assert any(line.startswith("  next:") for line in lines)


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
    from poisson_prove.viewer import render_html

    page = json.loads(texts["serve --json"])
    assert "store_root" not in page["pair"]  # removed from the page structure, relative or not
    texts["page"] = render_html({k: v for k, v in page.items() if k not in ("verdict", "sentence", "next")})
    for name, text in texts.items():
        for secret in secrets:
            assert secret not in text, (name, secret)
    # The page shows the run's Python version and nothing more of the build.
    assert "3.11.7" in texts["page"]


# ---------- PF4.13 and PF4.14 on the surface ----------


def test_pf4_13_diff_json_carries_the_direction_and_its_timing_note_under_logrank(tmp_path: Path) -> None:
    a = {"c": [(i, "fell", 8.0 + 0.05 * i) for i in range(32)]}
    b = {"c": [(i, "fell", 1.0 + 0.05 * i) for i in range(32)]}
    root = _pair(tmp_path / "prove-runs", a, b, salt="unshared")
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "logrank_bh", "--json"))
    (cell,) = doc["by_event"]["fell"]["cells"]
    assert cell["delta"] == 0.0
    assert cell["direction"] == "higher"
    assert cell["verdict"] == "worse"
    assert isinstance(cell["direction_note"], str) and cell["direction_note"]
    assert doc["by_event"]["fell"]["n_worse"] == 1


def test_pf4_14_diff_json_carries_the_matched_difference_and_the_pair_count_under_the_paired_test(tmp_path: Path) -> None:
    a = [(i, "fell" if i < 4 else "ok", HORIZON if i >= 4 else 1.0) for i in range(20)]
    a += [(20 + j, "fell", 1.0) for j in range(12)]
    b = [(i, "fell" if i < 12 else "ok", HORIZON if i >= 12 else 1.0) for i in range(20)]
    b += [(40 + j, "ok", HORIZON) for j in range(12)]
    root = _pair(tmp_path / "prove-runs", {"c": a}, {"c": b})
    doc = _json(_cli(root, "diff", A_ID, B_ID, "--event", "fell:failure", "--method", "mcnemar_bh", "--json"))
    (cell,) = doc["by_event"]["fell"]["cells"]
    assert cell["pairs"] == 20
    assert abs(cell["delta"] - 8 / 20) <= 1e-12
    assert cell["direction"] == "higher"
    assert cell["verdict"] == "worse"
    assert abs(cell["rate_a"] - 0.5) <= 1e-12 and abs(cell["rate_b"] - 0.375) <= 1e-12


# ---------- PF4.15 on the surface ----------

POWER_TARGET = 0.8


def test_pf4_15_json_gives_no_limit_at_ceiling_and_says_when_none_is_detectable(standard: Path) -> None:
    from statsmodels.stats.proportion import power_proportions_2indep

    # The construction: at 38 of 40 even a rise to 40 of 40 has power well under 0.8.
    assert power_proportions_2indep(0.05, 0.95, 40, ratio=1.0, alpha=0.05, return_results=False) < POWER_TARGET
    doc = _json(_cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--json"))
    cells = _cells_of(doc)
    ceiling = cells[_hash("top")]
    assert ceiling["mde"] is None
    assert isinstance(ceiling.get("mde_note"), str) and ceiling["mde_note"]
    near = cells[_hash("near_top")]
    assert abs(near["mde"] - (1.0 - 38 / 40)) <= 1e-9
    assert isinstance(near.get("mde_note"), str) and near["mde_note"]
    assert near["mde_note"] != ceiling["mde_note"]
    for name in ("up", "down", "same", "zero"):
        assert cells[_hash(name)].get("mde_note") is None, name
    numbers = [c["mde"] for c in cells.values() if c["mde"] is not None]
    ev = doc["by_event"]["fell"]
    assert ev["max_mde"] == max(numbers)
    unchanged = [c["mde"] for c in cells.values()
                 if c["mde"] is not None and c["direction"] == "unchanged"]
    assert ev["max_mde_unchanged"] == max(unchanged)


def test_pf4_15_text_prints_no_limit_at_ceiling_and_says_none_is_detectable_instead_of_the_headroom(
    standard: Path, tmp_path: Path
) -> None:
    diff_text = _cli(standard, "diff", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh").out
    top = _column(diff_text, "top", "mde")
    assert "ceiling" in top and not re.search(r"\d", top), top
    near = _column(diff_text, "near_top", "mde")
    assert "none detectable" in near, near
    _cli(standard, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
         "--out", str(tmp_path / "r"))
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    assert "ceiling" in md
    assert "none detectable" in md


def test_pf4_15_the_honesty_line_that_names_an_undetectable_condition_says_so(tmp_path: Path) -> None:
    """The only unchanged condition is the one where no rise is detectable."""
    a = {"w": _arm(4, 40), "s": _arm(30, 40), "near": _arm(38, 40)}
    b = {"w": _arm(30, 40), "s": _arm(4, 40), "near": _arm(38, 40)}
    root = _pair(tmp_path / "prove-runs", a, b)
    _cli(root, "report", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell",
         "--out", str(tmp_path / "r"))
    page = _json(_cli(root, "serve", A_ID, B_ID, "--event", "fell", "--method", "fisher_bh", "--x", "cell", "--json"))
    (entry,) = page["summary"]["events"]
    assert "none detectable" in entry["limit"]["line"]
    (panel,) = page["panels"]
    assert "none detectable" in panel["honesty"]
    md = (tmp_path / "r" / "report.md").read_text(encoding="utf-8")
    honesty = [line for line in md.splitlines() if "none detectable" in line and not line.startswith("|")]
    assert honesty, md


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
