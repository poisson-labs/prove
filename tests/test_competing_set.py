"""S13.1 competing-set hardening oracle, generated from section 4 of the S13.1 spec before
any of M5, M6, M7 or M10 is amended.

ADR-021: the Aalen-Johansen competing set is every terminal outcome present in either run;
``events`` selects which CIFs are compared, not which outcomes are absorbing. S11 hit this in
``multi_diff`` and S13 hit it again in the single-run report path. This file makes the rule a
test rather than a review step.

Plain assertions over shared helpers, per S12's lesson: that oracle needed seven fixes and all
seven were inside clever helpers. There is one frame builder, one run writer and one CLI
runner here; everything else is written out at the assertion.

Reading notes for Session B:

- ``competing_set`` is reached module-qualified as ``survival.competing_set``, so this file
  still collects before S13.1 builds it. Every symbol that exists today is imported directly.
  ``import proofload.cli as cli`` is the S10 and S12 idiom; this extends it to the new name.
- H3, H4 and H10 drive ``proofload.cli.main`` and read the report objects the CLI built, by
  wrapping ``cli.build_survival_report`` / ``cli.build_multi_report`` (the S12 C11 idiom; the
  name must be bound in ``cli``). The wrappers call the real builders, so the files are still
  written. Reading the rendered Markdown instead would not work: ``_fmt(..., "pp1")`` rounds
  every rate to a tenth of a percentage point, and H4 is a 1e-12 comparison.
- Each ``report`` invocation builds two report objects when the theme is dark -- the report
  and the light-themed receipt -- so the tests read index 0, the one the CLI renders.
- H4 is the test that would have caught the S13 blocker, so it is first in the file.
- H3's cell is the exact 5-completed / 5-violated cell from the S13 report. The completions
  end at t=1 and the violations at t=3: with the competing set the violated CIF at the horizon
  is 0.5, and with ``events=["violated"]`` alone the completions are censored out of the risk
  set and it reads 1.0. A cell whose competing rows end *after* the events does not
  discriminate -- both sets give 0.5 -- which is why the times are pinned here.
- H13 reads ``src/`` with ``ast``. "A competing-set construction" is taken to mean an event-set
  argument reaching ``aalen_johansen`` or ``cell_table`` from anywhere other than
  ``competing_set``; the one forwarding call inside ``cell_table`` itself is the plumbing that
  carries a caller's set, not a second construction, and is named as such in the test.

H6 and H9 were rewritten by the spec author after the first pass of this oracle reported
that the original pair could not both hold. The tests below are written against the revised
§2/§3-D3/§4: validation moved into the CLI, where every typo originates, and ``multi_diff``
was pinned permissive instead. Two readings the revised text still leaves to the test:

- H6's message. §4 requires exit 2, the offending name and the outcomes present; D3 shows the
  shape with the verb name substituted. Asserted by containment, not as an exact string, so
  the wording stays the implementer's.
- H9's "zero-count `EventDiff`". Read as the event counts, not the cell count -- see the
  docstring of ``test_h9_absent_event_gets_a_zero_count_event_diff``. The frozen M6 oracle
  forces this reading; an EventDiff with no cells would fail ``test_a9_counts_add_up_property``.

Still not mapped, and reported rather than adapted:

- H12's third clause, "suite totals for every prior oracle unchanged". A test cannot assert
  the totals of the suite that contains it; that clause is the acceptance command's job. The
  two fixture clauses are mapped below.
- §2's "``build_survival_report`` remains permissive" is not separately asserted. §4 pins only
  ``multi_diff`` (H9), and once H13 routes ``cell_table`` through ``competing_set`` an absent
  event is no longer a key on the cell table's ``CIFCurve``, so ``_cif_at`` raises
  ``SurvivalError`` there rather than returning zero. That path is unreachable from the CLI,
  which now refuses first, and what "permissive" should mean at that boundary is not stated.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import xml.etree.ElementTree as ET
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import poisson_prove.cli as cli
import poisson_prove.report as report_module
import poisson_prove.survival as survival
from poisson_prove.diff import diff, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import ABSENT_FILL, MultiReport, SurvivalReport
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from poisson_prove.survival import censor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "poisson_prove"
QUICKSTART = ROOT / "examples" / "quickstart.toml"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "go1"
REGRESSION_JSON = FIXTURE_DIR / "diff_regression.json"
REGRESSION_DIR = FIXTURE_DIR / "report_regression"

MOCK_MODULE = "poisson_prove.examples.mock_agent"
ROLLOUT = f"{MOCK_MODULE}:rollout"
PATCHED = f"{MOCK_MODULE}:rollout_patched"
QUICKSTART_SALT = "0000000000000015"

M4_COLUMNS = [
    "run_id",
    "config_hash",
    "config",
    "seed",
    "replicate_index",
    "outcome",
    "t",
    "horizon",
    "confidence",
    "meta",
    "error",
    "wall_time",
    "backend_meta",
]

HORIZON = 10.0
TOL = 1e-12

# The S13 typo, and the outcomes the mock-agent pair actually produces.
ABSENT = "voilated"
MOCK_OUTCOMES = ("completed", "timeout", "violated")

# The S13 blocker's cell: 5 completed ending at t=1, 5 violated ending at t=3.
COMPLETED_T = 1.0
VIOLATED_T = 3.0
TIMEOUT_T = 5.0

# Frozen fixtures, as committed before this session. H12 is "golden untouched".
FROZEN_SHA256 = {
    REGRESSION_JSON: "ea9a19d98490f71544933057dbea62c4c83c3bfbc9e47b98f593798981c0cc5d",
    REGRESSION_DIR / "report.md": "1755f5bd313e39a9da3b99980607b45d76dd16608d1d8a80a624bddc2af2d217",
    REGRESSION_DIR / "heatmap.svg": "77df396e6e5cbe4423fe147c57735f33a4c4c5580b00f8e37314d1918fc5288f",
    REGRESSION_DIR / "receipt.html": "4d0d64320de7be8549c673137d731b3529569f7452d9799983a87393f66cba00",
}

GO1_EVENT = "fell"
GO1_CELLS = 400
GO1_SAFER, GO1_WORSE = 60, 0
GO1_Q, GO1_POWER = 0.05, 0.8
# The frozen cells carry no ``stat``; these are exactly the keys S8 wrote.
GO1_CELL_KEYS = [
    "config_hash",
    "n_a",
    "n_b",
    "events_a",
    "events_b",
    "rate_a",
    "rate_b",
    "delta",
    "p",
    "q",
    "verdict",
    "mde",
]
GO1_INT_KEYS = {"n_a", "n_b", "events_a", "events_b"}
GO1_STR_KEYS = {"config_hash", "verdict"}

# A parameter carrying a competing set would have to be named for one. H5 rejects any name
# but ``events`` that reads like an outcome set.
OVERRIDE_HINTS = ("event", "outcome", "competing", "risk")


# ---------- helpers ----------


def frame(rows: list[tuple[dict[str, Any], str | None, float | None]]) -> pd.DataFrame:
    """A Store.read()-shaped frame from (config, outcome, t) triples.

    ``outcome=None`` is an errored row: M4 requires t and horizon to be None on those.
    """
    records = []
    counters: dict[str, int] = {}
    for config, outcome, t in rows:
        h = config_hash(config)
        rep = counters.get(h, 0)
        counters[h] = rep + 1
        errored = outcome is None
        records.append(
            {
                "run_id": "r",
                "config_hash": h,
                "config": dict(config),
                "seed": 1000 + rep,
                "replicate_index": rep,
                "outcome": outcome,
                "t": None if errored else t,
                "horizon": None if errored else HORIZON,
                "confidence": None,
                "meta": {},
                "error": "boom" if errored else None,
                "wall_time": 0.0,
                "backend_meta": {},
            }
        )
    df = pd.DataFrame.from_records(records, columns=M4_COLUMNS)
    df["t"] = df["t"].astype(float)
    df["horizon"] = df["horizon"].astype(float)
    return df.sort_values(["config_hash", "replicate_index"]).reset_index(drop=True)


def write_run(
    root: Path,
    run_id: str,
    rows: list[tuple[dict[str, Any], str | None, float | None]],
    *,
    salt: str = "s13-1",
) -> None:
    """Write the same (config, outcome, t) triples to a real store, for the CLI-driven tests."""
    store = Store(root)
    store.create_run(
        RunManifest(
            run_id=run_id,
            target_id="synthetic@v0",
            t_unit="steps",
            run_salt=salt,
            axis_types={"task": "categorical", "level": "categorical"},
            backend="synthetic",
            environment={},
        )
    )
    records = []
    counters: dict[str, int] = {}
    for config, outcome, t in rows:
        h = config_hash(config)
        rep = counters.get(h, 0)
        counters[h] = rep + 1
        if outcome is None:
            records.append(
                EpisodeRecord.errored(
                    run_id=run_id,
                    config=dict(config),
                    seed=1000 + rep,
                    replicate_index=rep,
                    error="boom",
                    wall_time=0.0,
                )
            )
        else:
            records.append(
                EpisodeRecord.from_episode(
                    Episode(outcome=outcome, t=float(t), horizon=HORIZON),
                    run_id=run_id,
                    config=dict(config),
                    seed=1000 + rep,
                    replicate_index=rep,
                    wall_time=0.0,
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def sweep(root: Path, target: str, *extra: str) -> str:
    code, out, err = run_cli(
        ["--store", str(root), "sweep", str(QUICKSTART), "--target", target, "--yes", *extra]
    )
    assert code == 0, out + err
    last = out.strip().splitlines()[-1]
    assert last.startswith("run_id: "), out
    return last.split("run_id: ", 1)[1]


def rates_by_hash(panel: Any) -> dict[str, float]:
    return {c.config_hash: c.rate_a for c in panel.cells if c.present}


def table_rows(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("|")]


def cell_rects(svg: str) -> list[dict[str, str]]:
    """Every grid rect, in document order: the same order as ``Report.cells``."""
    root = ET.fromstring(svg)
    return [e.attrib for e in root.iter() if e.tag.endswith("rect") and "data-cell" in e.attrib]


def label_inside(svg: str, rect: dict[str, str]) -> list[str]:
    """The text drawn inside a rect -- the number painted in that cell, if any.

    Geometry, not layout constants: a cell's label is centred in its own rect (report.py emits
    it at the rect's midpoint), while the axis ticks, the axis name and the legend all sit below
    the last row and the y ticks sit left of the first column.
    """
    x, y = float(rect["x"]), float(rect["y"])
    w, h = float(rect["width"]), float(rect["height"])
    root = ET.fromstring(svg)
    inside = []
    for element in root.iter():
        if not element.tag.endswith("text") or "x" not in element.attrib:
            continue
        tx, ty = float(element.attrib["x"]), float(element.attrib["y"])
        if x <= tx <= x + w and y <= ty <= y + h:
            inside.append("".join(element.itertext()))
    return inside


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> tuple[list[SurvivalReport], list[MultiReport]]:
    """Record the reports the CLI builds. The wrappers call the real builders, so the CLI still
    writes its files; index 0 is the report the CLI renders, index 1 the light receipt."""
    survival_reports: list[SurvivalReport] = []
    multi_reports: list[MultiReport] = []
    real_survival = report_module.build_survival_report
    real_multi = report_module.build_multi_report

    def survival_wrapper(*args: Any, **kwargs: Any) -> SurvivalReport:
        built = real_survival(*args, **kwargs)
        survival_reports.append(built)
        return built

    def multi_wrapper(*args: Any, **kwargs: Any) -> MultiReport:
        built = real_multi(*args, **kwargs)
        multi_reports.append(built)
        return built

    monkeypatch.setattr(cli, "build_survival_report", survival_wrapper)
    monkeypatch.setattr(cli, "build_multi_report", multi_wrapper)
    return survival_reports, multi_reports


@pytest.fixture(scope="module")
def mock_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """The two quickstart runs under the S12 salt: outcomes completed, timeout, violated.
    Never mutated by a test."""
    root = tmp_path_factory.mktemp("competing-set-store")
    a = sweep(root, ROLLOUT, "--salt", QUICKSTART_SALT)
    b = sweep(root, PATCHED, "--pair-with", a)
    return root, a, b


# ---------- H4: cross-form agreement, the property the S13 blocker violated ----------


@pytest.mark.parametrize(
    "events",
    [["violated"], ["completed", "timeout", "violated"]],
    ids=["one-event", "all-events"],
)
def test_h4_report_run_and_report_pair_agree_on_rate_a_for_every_cell(
    mock_pair: tuple[Path, str, str],
    captured: tuple[list[SurvivalReport], list[MultiReport]],
    tmp_path: Path,
    events: list[str],
) -> None:
    root, a, b = mock_pair
    survival_reports, multi_reports = captured
    event_flags = [flag for e in events for flag in ("--event", e)]

    code, out, err = run_cli(
        ["--store", str(root), "report", a, *event_flags,
         "--x", "tool_fail_rate", "--y", "task_id", "--out", str(tmp_path / "single")]
    )
    assert code == 0, out + err
    single = survival_reports[0]

    code, out, err = run_cli(
        ["--store", str(root), "report", a, b, *event_flags,
         "--x", "tool_fail_rate", "--y", "task_id", "--out", str(tmp_path / "pair")]
    )
    assert code == 0, out + err
    pair = multi_reports[0]

    assert set(single.panels) == set(events) and set(pair.panels) == set(events)
    for e in events:
        from_run = rates_by_hash(single.panels[e])
        from_pair = rates_by_hash(pair.panels[e])
        assert set(from_run) == set(from_pair), e
        assert from_run, e
        for h in sorted(from_run):
            assert abs(from_run[h] - from_pair[h]) <= TOL, (e, h, from_run[h], from_pair[h])


# ---------- H1: one constructor ----------


def test_h1_competing_set_returns_sorted_deduplicated_outcomes_across_frames() -> None:
    a = frame([({"task": "x"}, "violated", VIOLATED_T), ({"task": "x"}, "completed", COMPLETED_T)])
    b = frame([({"task": "x"}, "timeout", TIMEOUT_T), ({"task": "x"}, "violated", VIOLATED_T)])
    assert survival.competing_set(a, b) == ("completed", "timeout", "violated")
    assert survival.competing_set(a) == ("completed", "violated")
    assert survival.competing_set(b) == ("timeout", "violated")


def test_h1_competing_set_ignores_empty_frames() -> None:
    a = frame([({"task": "x"}, "violated", VIOLATED_T), ({"task": "x"}, "completed", COMPLETED_T)])
    empty = a.iloc[0:0]
    assert len(empty) == 0
    assert survival.competing_set(empty) == ()
    assert survival.competing_set(a, empty) == ("completed", "violated")
    assert survival.competing_set(empty, a) == ("completed", "violated")


def test_h1_competing_set_ignores_a_frame_of_all_null_outcomes() -> None:
    a = frame([({"task": "x"}, "violated", VIOLATED_T), ({"task": "x"}, "completed", COMPLETED_T)])
    errored = frame([({"task": "y"}, None, None), ({"task": "y"}, None, None)])
    assert errored["outcome"].isna().all()
    assert survival.competing_set(errored) == ()
    assert survival.competing_set(a, errored) == ("completed", "violated")


def test_h1_competing_set_deduplicates_repeated_outcomes() -> None:
    a = frame([({"task": "x"}, "violated", VIOLATED_T)] * 5)
    b = frame([({"task": "y"}, "violated", VIOLATED_T)] * 3)
    assert survival.competing_set(a, b) == ("violated",)


# ---------- H2: multi_diff uses the full set ----------


def _three_outcome_run(cells: dict[str, tuple[int, int, int]]) -> pd.DataFrame:
    """One cell per label; (completed, violated, timeout) counts. The competing rows end at
    t=1, before the violations at t=3, so censoring them instead of absorbing them changes the
    violated CIF."""
    rows: list[tuple[dict[str, Any], str | None, float | None]] = []
    for label, (n_completed, n_violated, n_timeout) in cells.items():
        config = {"task": label, "level": "one"}
        rows += [(config, "completed", COMPLETED_T)] * n_completed
        rows += [(config, "violated", VIOLATED_T)] * n_violated
        rows += [(config, "timeout", TIMEOUT_T)] * n_timeout
    return frame(rows)


def test_h2_multi_diff_rate_a_is_the_same_for_one_event_and_for_every_event() -> None:
    a = _three_outcome_run({"x": (4, 3, 3), "y": (6, 2, 2)})
    b = _three_outcome_run({"x": (3, 4, 3), "y": (5, 3, 2)})
    one = multi_diff(a, b, events=["violated"])
    every = multi_diff(a, b, events=["violated", "timeout", "completed"])
    one_cells = one.by_event["violated"].cells
    every_cells = every.by_event["violated"].cells
    assert list(one_cells["config_hash"]) == list(every_cells["config_hash"])
    for h, r_one, r_every in zip(
        one_cells["config_hash"], one_cells["rate_a"], every_cells["rate_a"], strict=True
    ):
        assert abs(float(r_one) - float(r_every)) <= TOL, (h, r_one, r_every)


def test_h2_multi_diff_absorbs_the_non_event_rather_than_censoring_it() -> None:
    """The number itself: 4 completed at t=1, 3 violated at t=3, 3 timeout at t=5 gives a
    violated CIF of 0.3 over the competing set. Censoring the completions gives 0.5."""
    a = _three_outcome_run({"x": (4, 3, 3), "y": (6, 2, 2)})
    b = _three_outcome_run({"x": (4, 3, 3), "y": (6, 2, 2)})
    result = multi_diff(a, b, events=["violated"])
    cells = result.by_event["violated"].cells
    rate = dict(zip(cells["config_hash"], cells["rate_a"], strict=True))
    assert abs(rate[config_hash({"task": "x", "level": "one"})] - 0.3) <= TOL, rate
    assert abs(rate[config_hash({"task": "y", "level": "one"})] - 0.2) <= TOL, rate


# ---------- H3: the single-run path uses the full set (the S13 5/5 cell) ----------


def _five_five_rows() -> list[tuple[dict[str, Any], str | None, float | None]]:
    """The S13 cell: 5 completed ending at t=1, 5 violated ending at t=3, plus a second cell
    so the report has a varying axis."""
    rows: list[tuple[dict[str, Any], str | None, float | None]] = []
    blocker = {"task": "blocker", "level": "one"}
    rows += [(blocker, "completed", COMPLETED_T)] * 5
    rows += [(blocker, "violated", VIOLATED_T)] * 5
    other = {"task": "other", "level": "one"}
    rows += [(other, "completed", COMPLETED_T)] * 8
    rows += [(other, "violated", VIOLATED_T)] * 2
    return rows


def test_h3_five_completed_five_violated_cell_reports_half_not_all(
    captured: tuple[list[SurvivalReport], list[MultiReport]], tmp_path: Path
) -> None:
    root = tmp_path / "store"
    write_run(root, "s13-blocker", _five_five_rows())
    survival_reports, _ = captured
    code, out, err = run_cli(
        ["--store", str(root), "report", "s13-blocker", "--event", "violated",
         "--x", "task", "--out", str(tmp_path / "out")]
    )
    assert code == 0, out + err
    panel = survival_reports[0].panels["violated"]
    rate = {c.coords[0]: c.rate_a for c in panel.cells if c.present}
    assert abs(rate["blocker"] - 0.5) <= TOL, rate
    assert abs(rate["other"] - 0.2) <= TOL, rate


def test_h3_single_run_rate_a_is_the_same_for_one_event_and_for_every_event(
    captured: tuple[list[SurvivalReport], list[MultiReport]], tmp_path: Path
) -> None:
    root = tmp_path / "store"
    write_run(root, "s13-blocker", _five_five_rows())
    survival_reports, _ = captured

    code, out, err = run_cli(
        ["--store", str(root), "report", "s13-blocker", "--event", "violated",
         "--x", "task", "--out", str(tmp_path / "one")]
    )
    assert code == 0, out + err
    one = survival_reports[0]

    survival_reports.clear()
    code, out, err = run_cli(
        ["--store", str(root), "report", "s13-blocker", "--event", "violated",
         "--event", "completed", "--x", "task", "--out", str(tmp_path / "every")]
    )
    assert code == 0, out + err
    every = survival_reports[0]

    from_one = {c.coords[0]: c.rate_a for c in one.panels["violated"].cells if c.present}
    from_every = {c.coords[0]: c.rate_a for c in every.panels["violated"].cells if c.present}
    assert set(from_one) == set(from_every)
    for coord in sorted(from_one):
        assert abs(from_one[coord] - from_every[coord]) <= TOL, coord


# ---------- H5: no caller-supplied competing set ----------


def test_h5_multi_diff_exposes_no_competing_set_override() -> None:
    params = inspect.signature(multi_diff).parameters
    assert "events" in params, sorted(params)
    overrides = [
        name
        for name in params
        if name != "events" and any(hint in name.lower() for hint in OVERRIDE_HINTS)
    ]
    assert overrides == [], overrides


def test_h5_build_survival_report_exposes_no_competing_set_override() -> None:
    params = inspect.signature(report_module.build_survival_report).parameters
    assert "events" in params, sorted(params)
    overrides = [
        name
        for name in params
        if name != "events" and any(hint in name.lower() for hint in OVERRIDE_HINTS)
    ]
    assert overrides == [], overrides


# ---------- H6: the CLI validates event names, in all three verbs ----------


@pytest.mark.parametrize("verb", ["diff", "check", "report"])
def test_h6_every_verb_refuses_an_event_absent_from_the_runs(
    mock_pair: tuple[Path, str, str], tmp_path: Path, verb: str
) -> None:
    root, a, b = mock_pair
    argv = ["--store", str(root), verb, a, b, "--event", ABSENT]
    if verb == "report":
        argv += ["--x", "tool_fail_rate", "--y", "task_id", "--out", str(tmp_path / "out")]
    code, out, err = run_cli(argv)
    assert code == 2, out + err
    assert "Traceback" not in out + err, out + err
    assert ABSENT in out + err, out + err
    for present in MOCK_OUTCOMES:
        assert present in out + err, (present, out + err)
    assert verb in out + err, out + err


@pytest.mark.parametrize("verb", ["diff", "check", "report"])
def test_h6_every_verb_still_accepts_a_known_event(
    mock_pair: tuple[Path, str, str], tmp_path: Path, verb: str
) -> None:
    """The control for the refusal above: the same argv with the name spelled correctly gets
    through, so the refusal is about the name and not about the flag."""
    root, a, b = mock_pair
    argv = ["--store", str(root), verb, a, b, "--event", "violated"]
    if verb == "report":
        argv += ["--x", "tool_fail_rate", "--y", "task_id", "--out", str(tmp_path / "out")]
    code, out, err = run_cli(argv)
    assert code == 0, out + err


def test_h6_refuses_when_only_one_of_several_events_is_absent(
    mock_pair: tuple[Path, str, str],
) -> None:
    """"any --event name absent from it" -- a known companion does not license the typo."""
    root, a, b = mock_pair
    code, out, err = run_cli(
        ["--store", str(root), "diff", a, b, "--event", "violated", "--event", ABSENT]
    )
    assert code == 2, out + err
    assert ABSENT in out + err, out + err


def test_h6_report_refuses_before_it_writes_anything(
    mock_pair: tuple[Path, str, str], tmp_path: Path
) -> None:
    """D3: the check runs before any work. A refused report leaves no output directory behind."""
    root, a, b = mock_pair
    out_dir = tmp_path / "out"
    code, out, err = run_cli(
        ["--store", str(root), "report", a, b, "--event", ABSENT,
         "--x", "tool_fail_rate", "--y", "task_id", "--out", str(out_dir)]
    )
    assert code == 2, out + err
    assert not out_dir.exists() or not any(out_dir.iterdir()), sorted(out_dir.iterdir())


def _two_outcome_rows(with_timeout: bool) -> list[tuple[dict[str, Any], str | None, float | None]]:
    """Two cells of completed/violated; ``with_timeout`` adds a third outcome to one of them."""
    rows: list[tuple[dict[str, Any], str | None, float | None]] = []
    for label, n_violated in (("x", 5), ("y", 2)):
        config = {"task": label, "level": "one"}
        rows += [(config, "completed", COMPLETED_T)] * (10 - n_violated)
        rows += [(config, "violated", VIOLATED_T)] * n_violated
        if with_timeout:
            rows += [(config, "timeout", TIMEOUT_T)] * 3
    return rows


def test_h6_single_run_report_validates_against_the_run_it_loaded(tmp_path: Path) -> None:
    """"the frames they loaded" -- an outcome only the second run produced is in the pair's
    competing set and not in the single run's, and the two forms differ accordingly."""
    root = tmp_path / "store"
    write_run(root, "run-a", _two_outcome_rows(with_timeout=False))
    write_run(root, "run-b", _two_outcome_rows(with_timeout=True))

    code, out, err = run_cli(
        ["--store", str(root), "report", "run-a", "run-b", "--event", "timeout",
         "--x", "task", "--out", str(tmp_path / "pair")]
    )
    assert code == 0, out + err

    code, out, err = run_cli(
        ["--store", str(root), "report", "run-a", "--event", "timeout",
         "--x", "task", "--out", str(tmp_path / "single")]
    )
    assert code == 2, out + err
    assert "timeout" in out + err, out + err
    for present in ("completed", "violated"):
        assert present in out + err, (present, out + err)


# ---------- H7: check refuses an unknown event ----------


def test_h7_check_refuses_an_event_absent_from_both_runs(
    mock_pair: tuple[Path, str, str],
) -> None:
    root, a, b = mock_pair
    code, out, err = run_cli(["--store", str(root), "check", a, b, "--event", "voilated"])
    assert code == 2, out + err
    assert "Traceback" not in out + err, out + err
    assert "voilated" in out + err, out + err
    for present in ("completed", "timeout", "violated"):
        assert present in out + err, (present, out + err)


def test_h7_check_prints_no_verdict_when_it_refuses(mock_pair: tuple[Path, str, str]) -> None:
    root, a, b = mock_pair
    code, out, err = run_cli(["--store", str(root), "check", a, b, "--event", "voilated"])
    assert code == 2, out + err
    assert "PASS" not in out + err, out + err
    assert "FAIL" not in out + err, out + err


# ---------- H8: check still passes on a real event ----------


def test_h8_check_still_passes_on_a_known_event(mock_pair: tuple[Path, str, str]) -> None:
    root, a, b = mock_pair
    code, out, err = run_cli(["--store", str(root), "check", a, b, "--event", "violated"])
    assert code == 0, out + err
    assert "Traceback" not in out + err, out + err
    assert "PASS" in out, out
    assert "violated" in out, out


def test_h8_check_still_fails_cleanly_on_two_known_events(mock_pair: tuple[Path, str, str]) -> None:
    """The other half of "unchanged": on this pair ``timeout`` genuinely regresses, so the
    two-event gate fails. A known event still reaches a verdict rather than a refusal."""
    root, a, b = mock_pair
    code, out, err = run_cli(
        ["--store", str(root), "check", a, b, "--event", "violated", "--event", "timeout"]
    )
    assert code == 1, out + err
    assert "Traceback" not in out + err, out + err
    assert "FAIL" in out, out


# ---------- H9: multi_diff stays permissive ----------


def _absent_event_pair() -> tuple[pd.DataFrame, pd.DataFrame]:
    return (
        _three_outcome_run({"x": (4, 3, 3), "y": (6, 2, 2)}),
        _three_outcome_run({"x": (3, 4, 3), "y": (5, 3, 2)}),
    )


def test_h9_multi_diff_does_not_raise_on_an_event_absent_from_the_data() -> None:
    a, b = _absent_event_pair()
    result = multi_diff(a, b, events=[ABSENT])
    assert result.events == (ABSENT,)
    assert ABSENT in result.by_event


def test_h9_absent_event_gets_a_zero_count_event_diff() -> None:
    """"Zero-count" is the event counts, not the cell count. The frozen M6 oracle asserts
    ``n_safer + n_worse + n_unchanged == len(cells) == len(common)`` for every requested event
    (tests/test_m6_multi.py:730-741), and ``test_a15_check_on_synthetic_cases`` asserts on a
    result for ``violated`` over a pair containing none -- so an absent event keeps one
    unchanged cell per common config hash and zeroes the numerators rather than emptying the
    frame."""
    a, b = _absent_event_pair()
    event = multi_diff(a, b, events=[ABSENT]).by_event[ABSENT]
    assert (event.n_safer, event.n_worse) == (0, 0)
    assert len(event.cells) == 2
    assert event.n_unchanged == len(event.cells)
    assert list(event.cells["events_a"]) == [0, 0]
    assert list(event.cells["events_b"]) == [0, 0]
    assert list(event.cells["rate_a"]) == [0.0, 0.0]
    assert list(event.cells["rate_b"]) == [0.0, 0.0]
    assert list(event.cells["delta"]) == [0.0, 0.0]
    assert list(event.cells["verdict"]) == ["unchanged", "unchanged"]
    # n_a / n_b stay the real cell sizes: the episodes were observed, the event was not.
    assert list(event.cells["n_a"]) == [10, 10]
    assert list(event.cells["n_b"]) == [10, 10]


def test_h9_an_absent_event_does_not_disturb_a_present_one() -> None:
    """Requesting the typo alongside a real event leaves that event's CIFs untouched. Only the
    rates are compared: ``q`` is a property of the BH family, which grew by two tests."""
    a, b = _absent_event_pair()
    alone = multi_diff(a, b, events=["violated"]).by_event["violated"].cells
    beside = multi_diff(a, b, events=["violated", ABSENT]).by_event["violated"].cells
    assert list(alone["config_hash"]) == list(beside["config_hash"])
    for column in ("rate_a", "rate_b", "delta"):
        for h, one, two in zip(alone["config_hash"], alone[column], beside[column], strict=True):
            assert abs(float(one) - float(two)) <= TOL, (h, column, one, two)


def test_h9_multi_diff_stays_permissive_when_every_requested_event_is_absent() -> None:
    """The case the CLI now refuses outright, pinned at the library boundary: nothing raises,
    and the result is honestly empty of events rather than empty of cells."""
    a, b = _absent_event_pair()
    result = multi_diff(a, b, events=[ABSENT, "alsonotthere"])
    assert result.events == (ABSENT, "alsonotthere")
    for name in result.events:
        event = result.by_event[name]
        assert (event.n_safer, event.n_worse) == (0, 0)
        assert len(event.cells) == 2
        assert list(event.cells["events_a"]) == [0, 0]


# ---------- H10 / H11: a zero-n cell is a hole, not a measured zero ----------


HOLE = ("beta", "two")  # every episode errored: n = 0 after censoring
TRUE_ZERO = ("alpha", "two")  # ten completed episodes, no violation: an honest measured 0.0
MEASURED = {("alpha", "one"): 0.4, ("beta", "one"): 0.4, TRUE_ZERO: 0.0}


def _errored_cell_rows() -> list[tuple[dict[str, Any], str | None, float | None]]:
    """A 2x2 grid holding both cases H11 has to tell apart: one cell whose episodes all errored,
    and one whose violated rate is an honest zero. The grid is two-dimensional so the errored
    cell's coordinates still exist on both axes once its row is gone from a diff."""
    rows: list[tuple[dict[str, Any], str | None, float | None]] = []
    for task in ("alpha", "beta"):
        for level in ("one", "two"):
            config = {"task": task, "level": level}
            if (task, level) == HOLE:
                rows += [(config, None, None)] * 10
            elif (task, level) == TRUE_ZERO:
                rows += [(config, "completed", COMPLETED_T)] * 10
            else:
                rows += [(config, "completed", COMPLETED_T)] * 6
                rows += [(config, "violated", VIOLATED_T)] * 4
    return rows


def test_h10_all_errored_cell_is_absent_from_the_single_run_panel(
    captured: tuple[list[SurvivalReport], list[MultiReport]], tmp_path: Path
) -> None:
    root = tmp_path / "store"
    write_run(root, "holes", _errored_cell_rows())
    survival_reports, _ = captured
    code, out, err = run_cli(
        ["--store", str(root), "report", "holes", "--event", "violated",
         "--x", "task", "--y", "level", "--out", str(tmp_path / "out")]
    )
    assert code == 0, out + err
    panel = survival_reports[0].panels["violated"]
    by_coords = {c.coords: c for c in panel.cells}
    assert set(by_coords) == {("alpha", "one"), ("alpha", "two"), ("beta", "one"), ("beta", "two")}
    dead = by_coords[HOLE]
    assert dead.present is False, dead
    assert panel.n_absent == 1, panel.n_absent
    assert sum(1 for c in panel.cells if c.present) == 3
    assert panel.n_unchanged == 0, panel.n_unchanged


def test_h10_all_errored_cell_is_drawn_with_absent_fill(
    captured: tuple[list[SurvivalReport], list[MultiReport]], tmp_path: Path
) -> None:
    root = tmp_path / "store"
    write_run(root, "holes", _errored_cell_rows())
    survival_reports, _ = captured
    code, out, err = run_cli(
        ["--store", str(root), "report", "holes", "--event", "violated",
         "--x", "task", "--y", "level", "--theme", "dark", "--out", str(tmp_path / "out")]
    )
    assert code == 0, out + err
    svg = survival_reports[0].panels["violated"].to_svg()
    absent_rects = [line for line in svg.splitlines() if 'data-cell="absent"' in line]
    assert len(absent_rects) == 1, svg
    assert f'fill="{ABSENT_FILL["dark"]}"' in absent_rects[0], absent_rects[0]


def test_h10_all_errored_cell_is_absent_from_the_diff_panel(
    captured: tuple[list[SurvivalReport], list[MultiReport]], tmp_path: Path
) -> None:
    root = tmp_path / "store"
    write_run(root, "holes-a", _errored_cell_rows())
    write_run(root, "holes-b", _errored_cell_rows())
    _, multi_reports = captured
    code, out, err = run_cli(
        ["--store", str(root), "report", "holes-a", "holes-b", "--event", "violated",
         "--x", "task", "--y", "level", "--out", str(tmp_path / "out")]
    )
    assert code == 0, out + err
    panel = multi_reports[0].panels["violated"]
    by_coords = {c.coords: c for c in panel.cells}
    dead = by_coords[HOLE]
    assert dead.present is False, dead
    assert panel.n_absent == 1, panel.n_absent
    assert panel.n_unchanged == 3, panel.n_unchanged


def test_h11_all_errored_cell_reports_no_rate_in_the_worst_cells_table(
    captured: tuple[list[SurvivalReport], list[MultiReport]], tmp_path: Path
) -> None:
    root = tmp_path / "store"
    write_run(root, "holes", _errored_cell_rows())
    survival_reports, _ = captured
    code, out, err = run_cli(
        ["--store", str(root), "report", "holes", "--event", "violated",
         "--x", "task", "--y", "level", "--out", str(tmp_path / "out")]
    )
    assert code == 0, out + err
    markdown = survival_reports[0].to_markdown()
    rows = table_rows(markdown)
    assert rows, markdown
    assert [row for row in rows if row.startswith("| beta | two |")] == [], rows
    # The honest zero is still listed, so the hole is dropped for being a hole, not for reading 0.
    assert [row for row in rows if row.startswith("| alpha | two |")] != [], rows


def test_h11_all_errored_cell_carries_no_measured_rate_on_its_cell(
    captured: tuple[list[SurvivalReport], list[MultiReport]], tmp_path: Path
) -> None:
    root = tmp_path / "store"
    write_run(root, "holes", _errored_cell_rows())
    survival_reports, _ = captured
    code, out, err = run_cli(
        ["--store", str(root), "report", "holes", "--event", "violated",
         "--x", "task", "--y", "level", "--out", str(tmp_path / "out")]
    )
    assert code == 0, out + err
    panel = survival_reports[0].panels["violated"]
    dead = next(c for c in panel.cells if c.coords == HOLE)
    assert dead.present is False, dead
    measured = {c.coords: c.rate_a for c in panel.cells if c.present}
    assert HOLE not in measured, measured
    assert set(measured) == set(MEASURED), measured
    for coords, expected in MEASURED.items():
        assert abs(measured[coords] - expected) <= TOL, (coords, measured[coords], expected)


def test_h11_zero_n_cell_has_no_number_painted_in_its_square(
    captured: tuple[list[SurvivalReport], list[MultiReport]], tmp_path: Path
) -> None:
    """The surface the worst-cells table does not cover: the rate drawn inside the heatmap
    square. Today the hole is painted "0.0" in the same place, and in the first stop of the
    sequential ramp, as the honest zero beside it -- a reader cannot tell them apart."""
    root = tmp_path / "store"
    write_run(root, "holes", _errored_cell_rows())
    survival_reports, _ = captured
    code, out, err = run_cli(
        ["--store", str(root), "report", "holes", "--event", "violated",
         "--x", "task", "--y", "level", "--theme", "dark", "--out", str(tmp_path / "out")]
    )
    assert code == 0, out + err
    panel = survival_reports[0].panels["violated"]
    svg = panel.to_svg()
    rects = cell_rects(svg)
    assert len(rects) == len(panel.cells) == 4, (len(rects), len(panel.cells))
    by_coords = {c.coords: rect for c, rect in zip(panel.cells, rects, strict=True)}
    assert label_inside(svg, by_coords[HOLE]) == [], label_inside(svg, by_coords[HOLE])
    assert by_coords[HOLE]["fill"] == ABSENT_FILL["dark"], by_coords[HOLE]
    # The honest zero keeps its number, so the hole is blank for being a hole, not for reading 0.
    assert label_inside(svg, by_coords[TRUE_ZERO]) == ["0.0"], label_inside(svg, by_coords[TRUE_ZERO])
    assert by_coords[TRUE_ZERO]["fill"] != ABSENT_FILL["dark"], by_coords[TRUE_ZERO]


# ---------- H12: golden untouched ----------


@pytest.mark.parametrize("path", sorted(FROZEN_SHA256, key=str), ids=lambda p: p.name)
def test_h12_frozen_regression_fixtures_are_byte_identical(path: Path) -> None:
    assert path.is_file(), path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == FROZEN_SHA256[path], path


def test_h12_go1_single_event_diff_still_reproduces_the_frozen_cells(go1_store: Store) -> None:
    frozen = json.loads(REGRESSION_JSON.read_text())
    raw_a = go1_store.read("go1-v0")
    raw_b = go1_store.read("go1-v1")
    result = diff(
        censor(raw_a, GO1_EVENT),
        censor(raw_b, GO1_EVENT),
        event=GO1_EVENT,
        method="fisher_bh",
        q=GO1_Q,
        power=GO1_POWER,
        manifest_a=go1_store.manifest("go1-v0"),
        manifest_b=go1_store.manifest("go1-v1"),
    )
    assert result.n_safer == frozen["n_safer"] == GO1_SAFER
    assert result.n_worse == frozen["n_worse"] == GO1_WORSE
    assert len(result.cells) == frozen["n_cells"] == GO1_CELLS
    by_hash = {c["config_hash"]: c for c in frozen["cells"]}
    assert set(result.cells["config_hash"]) == set(by_hash)
    for row in result.cells.itertuples(index=False):
        reference = by_hash[row.config_hash]
        for key in GO1_CELL_KEYS:
            ours = getattr(row, key)
            if key in GO1_INT_KEYS:
                assert int(ours) == reference[key], (row.config_hash, key)
            elif key in GO1_STR_KEYS:
                assert str(ours) == reference[key], (row.config_hash, key)
            else:
                assert float(ours) == reference[key], (row.config_hash, key)


# ---------- H13: ADR-021 is enforced in src/, not documented ----------


def _modules() -> list[tuple[Path, ast.Module]]:
    return [(p, ast.parse(p.read_text(encoding="utf-8"))) for p in sorted(SRC.rglob("*.py"))]


def _owners(tree: ast.Module) -> dict[ast.AST, str]:
    """Every node mapped to the innermost function containing it, so a call is attributed once
    and a name bound in one function is not read as binding it in another."""
    owner: dict[ast.AST, str] = {}

    def walk(node: ast.AST, name: str) -> None:
        for child in ast.iter_child_nodes(node):
            child_name = (
                child.name
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                else name
            )
            owner[child] = child_name
            walk(child, child_name)

    walk(tree, "<module>")
    return owner


def _called_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _unwrap(node: ast.expr) -> ast.expr:
    """list(x) / tuple(x) / sorted(x) around a competing set is still that competing set."""
    while isinstance(node, ast.Call) and _called_name(node) in ("list", "tuple", "sorted"):
        if len(node.args) != 1:
            break
        node = node.args[0]
    return node


def _is_competing_set_call(node: ast.expr) -> bool:
    node = _unwrap(node)
    return isinstance(node, ast.Call) and _called_name(node) == "competing_set"


def _bound_names(tree: ast.Module, owner: dict[ast.AST, str]) -> dict[str, set[str]]:
    """Per function, the local names assigned from a ``competing_set(...)`` call."""
    bound: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value, targets = node.value, list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, [node.target]
        else:
            continue
        if not _is_competing_set_call(value):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                bound.setdefault(owner.get(node, "<module>"), set()).add(target.id)
    return bound


def _traces_to_competing_set(arg: ast.expr, bound: set[str]) -> bool:
    arg = _unwrap(arg)
    if _is_competing_set_call(arg):
        return True
    return isinstance(arg, ast.Name) and arg.id in bound


def test_h13_competing_set_is_defined_exactly_once_in_src() -> None:
    definitions = [
        (path.name, node.name)
        for path, tree in _modules()
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "competing_set"
    ]
    assert definitions == [("survival.py", "competing_set")], definitions


def test_h13_every_cell_table_call_site_passes_a_competing_set() -> None:
    """``cell_table(..., method="aj")`` with no ``events=`` falls back to ``[event]`` -- the
    subset that produced both blockers -- so a call site that omits it fails here too."""
    sites = []
    for path, tree in _modules():
        owner = _owners(tree)
        bound = _bound_names(tree, owner)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _called_name(node) == "cell_table"):
                continue
            scope = owner.get(node, "<module>")
            events = [kw.value for kw in node.keywords if kw.arg == "events"]
            ok = len(events) == 1 and _traces_to_competing_set(events[0], bound.get(scope, set()))
            sites.append((f"{path.name}:{scope}:{node.lineno}", ok))
    assert sites, "no cell_table call site found in src/"
    assert [site for site, ok in sites if not ok] == [], sites


def test_h13_every_aalen_johansen_call_site_passes_a_competing_set() -> None:
    """The one call inside ``cell_table`` forwards the set its caller supplied -- that is the
    plumbing that carries a competing set, not a second construction of one -- so it is named
    here rather than traced."""
    forwarding = ("survival.py", "cell_table")
    sites = []
    for path, tree in _modules():
        owner = _owners(tree)
        bound = _bound_names(tree, owner)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _called_name(node) == "aalen_johansen"):
                continue
            scope = owner.get(node, "<module>")
            if (path.name, scope) == forwarding:
                continue
            args = [*node.args, *(kw.value for kw in node.keywords if kw.arg == "events")]
            ok = len(args) >= 3 and _traces_to_competing_set(args[2], bound.get(scope, set()))
            sites.append((f"{path.name}:{scope}:{node.lineno}", ok))
    assert sites, "no aalen_johansen call site found in src/ outside cell_table"
    assert [site for site, ok in sites if not ok] == [], sites
