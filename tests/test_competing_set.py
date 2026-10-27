"""S13.1 -- the competing set: frozen tests for the S13.1 invariants.

The rule: the Aalen-Johansen competing set is every terminal outcome present in either run;
``events`` selects which CIFs are compared, not which outcomes are absorbing. It holds in
``multi_diff`` and in the single-run report path alike, and this file makes it a test.

Plain assertions over shared helpers: there is one frame builder, one run writer and one CLI
runner here; everything else is written out at the assertion.

Reading notes:

- ``competing_set`` is reached module-qualified as ``survival.competing_set``; every other
  symbol is imported directly. ``import poisson_prove.cli as cli`` lets a test wrap a name the
  CLI looks up on its module.
- H3, H4 and H10 drive ``poisson_prove.cli.main`` and read the report objects the CLI built, by
  wrapping ``cli.build_survival_report`` / ``cli.build_multi_report`` (the name must be bound in
  ``cli``). The wrappers call the real builders, so the files are still written. Reading the
  rendered Markdown instead would not work: ``_fmt(..., "pp1")`` rounds every rate to a tenth
  of a percentage point, and H4 is a 1e-12 comparison.
- Each ``report`` invocation builds two report objects when the theme is dark -- the report
  and the light-themed receipt -- so the tests read index 0, the one the CLI renders.
- H4, the single-run report and the pair report agreeing on ``rate_a`` for every cell, is the
  most direct check of the rule, so it is first in the file.
- H3's cell is 5 completed and 5 violated rows. The completions end at t=1 and the violations
  at t=3: with the competing set the violated CIF at the horizon is 0.5, and with
  ``events=["violated"]`` alone the completions are censored out of the risk set and it reads
  1.0. A cell whose competing rows end *after* the events does not discriminate -- both sets
  give 0.5 -- which is why the times are pinned here.
- H13 drives the two entry points H2 and H3 do not: the single-run report's ``--json`` and a
  saved comparison's incidence curves, each on cells whose completions end before the events,
  so the competing set and the reported event alone give different numbers.

An unknown event name is refused by the CLI, where every typo originates (H6), and
``multi_diff`` is permissive (H9). Two readings the invariants leave to the test:

- H6's message. H6 requires exit 1, the offending name and the outcomes present; the worked
  example shows the shape with the verb name substituted. Asserted by containment, not as an
  exact string, so the wording is free.
- H9's "zero-count `EventDiff`". Read as the event counts, not the cell count -- see the
  docstring of ``test_h9_absent_event_gets_a_zero_count_event_diff``. The M6 tests force this
  reading; an EventDiff with no cells would fail ``test_a9_counts_add_up_property``.

Not asserted here:

- H12's third clause, that the suite totals of the other test files are unchanged. A test
  cannot assert the totals of the suite that contains it. The two fixture clauses are mapped
  below.
- "``build_survival_report`` remains permissive". The invariants pin only ``multi_diff`` (H9),
  and since H13 routes ``cell_table`` through ``competing_set`` an absent event is not a key on
  the cell table's ``CIFCurve``, so ``_cif_at`` raises ``SurvivalError`` there rather than
  returning zero. That path is unreachable from the CLI, which refuses first, and what
  "permissive" should mean at that boundary is not stated.
"""

from __future__ import annotations

import html as html_lib
import inspect
import json
import math
import re
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
from conftest import quickstart_design
from test_m6_multi import reference_record

import lattice

# The packaged spec's design at 100 replicates, the count this file's numbers are for.
QUICKSTART = quickstart_design()
# PF4.30, PF4.48a: the quickstart design at 100 replicates with nothing declared has a
# detection limit (0.262 at base rate 0.400) above the default accepted change of 0.20, so its
# sweep is refused; every sweep of it in this file accepts 0.3, the smallest round value above
# the limit.
QUICKSTART_MAX_MDE = ("--max-mde", "0.3")

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

# A typo of ``violated``, and the outcomes the mock-agent pair actually produces.
ABSENT = "voilated"
MOCK_OUTCOMES = ("completed", "timeout", "violated")

# H3's cell: 5 completed ending at t=1, 5 violated ending at t=3.
COMPLETED_T = 1.0
VIOLATED_T = 3.0
TIMEOUT_T = 5.0

# H12 is "golden untouched": four files (the single-event diff record and the report's
# Markdown, heatmap and receipt), each checked by the facts it holds, on what the code writes
# for the lattice pair, against the lattice's references.
H12_FILES = ("diff_regression.json", "heatmap.svg", "receipt.html", "report.md")
H12_TITLE = "lattice before -> after"
LATTICE_EVENT = lattice.EVENT
LATTICE_CELLS = 72
LATTICE_SAFER, LATTICE_WORSE = 22, 0
LATTICE_Q, LATTICE_POWER = 0.05, 0.8
# The reference cells carry no ``stat``; these are the keys every reference cell holds.
LATTICE_CELL_KEYS = [
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
    # A sweep no longer ends with a run_id line (its end is a verdict line), so
    # the new run is the one the store gained.
    before = set(Store(root).runs())
    code, out, err = run_cli(
        ["--store", str(root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", target, "--yes", *extra]
    )
    assert code == 0, out + err
    added = set(Store(root).runs()) - before
    assert len(added) == 1, (added, out)
    return added.pop()


def verdict_lines(text: str) -> list[str]:
    """Lines that begin with check's verdict words."""
    return [line for line in text.splitlines() if line.startswith(("passed  ", "failed  "))]


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
    """The two quickstart runs under ``QUICKSTART_SALT``: outcomes completed, timeout, violated.
    Never mutated by a test."""
    root = tmp_path_factory.mktemp("competing-set-store")
    a = sweep(root, ROLLOUT, "--salt", QUICKSTART_SALT)
    b = sweep(root, PATCHED, "--pair-with", a)
    return root, a, b


# ---------- H4: cross-form agreement ----------


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


# ---------- H3: the single-run path uses the full set (the 5/5 cell) ----------


def _five_five_rows() -> list[tuple[dict[str, Any], str | None, float | None]]:
    """H3's cell: 5 completed ending at t=1, 5 violated ending at t=3, plus a second cell
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
    # A refusal exits 1, and check's verdict is a passed or failed line, so none is printed.
    assert code == 1, out + err
    assert "Traceback" not in out + err, out + err
    assert ABSENT in out + err, out + err
    for present in MOCK_OUTCOMES:
        assert present in out + err, (present, out + err)
    assert verb in out + err, out + err
    assert verdict_lines(out + err) == [], out + err
    if verb == "report":
        # The check runs before any work: a refused report leaves no output directory behind.
        out_dir = tmp_path / "out"
        assert not out_dir.exists() or not any(out_dir.iterdir()), sorted(out_dir.iterdir())


@pytest.mark.parametrize("verb", ["diff", "report"])
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
    # A refusal exits 1.
    assert code == 1, out + err
    assert ABSENT in out + err, out + err


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
    # A refusal exits 1.
    assert code == 1, out + err
    assert "timeout" in out + err, out + err
    for present in ("completed", "violated"):
        assert present in out + err, (present, out + err)


# ---------- H8: check still passes on a real event ----------


def test_h8_check_still_passes_on_a_known_event(mock_pair: tuple[Path, str, str]) -> None:
    root, a, b = mock_pair
    # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and these runs
    # declare none; --fail-on higher is the same gate ("fail when the rate rose").
    code, out, err = run_cli(
        ["--store", str(root), "check", a, b, "--event", "violated", "--fail-on", "higher"]
    )
    assert code == 0, out + err
    assert "Traceback" not in out + err, out + err
    # check's verdict is the first stdout line, passed or failed.
    assert out.startswith("passed  "), out
    assert "violated" in out, out


def test_h8_check_still_fails_cleanly_on_two_known_events(mock_pair: tuple[Path, str, str]) -> None:
    """The other half of "unchanged": on this pair ``timeout`` genuinely regresses, so the
    two-event gate fails. A known event still reaches a verdict rather than a refusal."""
    root, a, b = mock_pair
    # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and these runs
    # declare none; --fail-on higher is the same gate ("fail when the rate rose").
    code, out, err = run_cli(
        ["--store", str(root), "check", a, b, "--event", "violated", "--event", "timeout",
         "--fail-on", "higher"]
    )
    # A failed check exits 4 and says failed on its first stdout line.
    assert code == 4, out + err
    assert "Traceback" not in out + err, out + err
    assert out.startswith("failed  "), out


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
    """"Zero-count" is the event counts, not the cell count. The M6 tests assert
    ``n_safer + n_worse + n_unchanged == len(cells) == len(common)`` for every requested event
    (tests/test_m6_multi.py:730-741), and ``test_a15_check_on_synthetic_cases`` asserts on a
    result for ``violated`` over a pair containing none -- so an absent event keeps one
    unchanged cell per common config hash and zeroes the numerators rather than emptying the
    frame."""
    a, b = _absent_event_pair()
    event = multi_diff(a, b, events=[ABSENT]).by_event[ABSENT]
    # PF4.20 (the library follows the screen): the event has no kind, so n_safer and n_worse
    # are null and its zero counts are the direction counts.
    assert (event.n_safer, event.n_worse) == (None, None)
    assert (event.n_lower, event.n_higher) == (0, 0)
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
        # PF4.20 (the library follows the screen): no kind, so the zero counts are n_lower and
        # n_higher, and n_safer and n_worse are null.
        assert (event.n_safer, event.n_worse) == (None, None)
        assert (event.n_lower, event.n_higher) == (0, 0)
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


def test_h10_all_errored_cell_is_a_hole_and_not_a_measured_zero_in_the_single_run_report(
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
    report = survival_reports[0]
    panel = report.panels["violated"]

    # The panel: the hole is absent, and only the three measured cells are present.
    by_coords = {c.coords: c for c in panel.cells}
    assert set(by_coords) == {("alpha", "one"), ("alpha", "two"), ("beta", "one"), ("beta", "two")}
    dead = by_coords[HOLE]
    assert dead.present is False, dead
    assert panel.n_absent == 1, panel.n_absent
    assert sum(1 for c in panel.cells if c.present) == 3
    assert panel.n_unchanged == 0, panel.n_unchanged
    measured = {c.coords: c.rate_a for c in panel.cells if c.present}
    assert HOLE not in measured, measured
    assert set(measured) == set(MEASURED), measured
    for coords, expected in MEASURED.items():
        assert abs(measured[coords] - expected) <= TOL, (coords, measured[coords], expected)

    # The worst-cells table: no row for the hole. The honest zero is still listed, so the hole is
    # dropped for being a hole, not for reading 0.
    markdown = report.to_markdown()
    rows = table_rows(markdown)
    assert rows, markdown
    assert [row for row in rows if row.startswith("| beta | two |")] == [], rows
    assert [row for row in rows if row.startswith("| alpha | two |")] != [], rows

    # The heatmap: the hole is the one absent rect, in the absent fill, with no number painted in
    # its square, while the honest zero keeps its number and a ramp fill.
    svg = panel.to_svg()
    absent_rects = [line for line in svg.splitlines() if 'data-cell="absent"' in line]
    assert len(absent_rects) == 1, svg
    assert f'fill="{ABSENT_FILL["dark"]}"' in absent_rects[0], absent_rects[0]
    rects = cell_rects(svg)
    assert len(rects) == len(panel.cells) == 4, (len(rects), len(panel.cells))
    rect_at = {c.coords: rect for c, rect in zip(panel.cells, rects, strict=True)}
    assert label_inside(svg, rect_at[HOLE]) == [], label_inside(svg, rect_at[HOLE])
    assert rect_at[HOLE]["fill"] == ABSENT_FILL["dark"], rect_at[HOLE]
    assert label_inside(svg, rect_at[TRUE_ZERO]) == ["0.0"], label_inside(svg, rect_at[TRUE_ZERO])
    assert rect_at[TRUE_ZERO]["fill"] != ABSENT_FILL["dark"], rect_at[TRUE_ZERO]


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


# ---------- H12: golden untouched ----------


def _lattice_diff(store: Store) -> Any:
    return diff(
        censor(store.read(lattice.RUN_A), LATTICE_EVENT),
        censor(store.read(lattice.RUN_B), LATTICE_EVENT),
        event=LATTICE_EVENT,
        method="fisher_bh",
        q=LATTICE_Q,
        power=LATTICE_POWER,
        manifest_a=store.manifest(lattice.RUN_A),
        manifest_b=store.manifest(lattice.RUN_B),
    )


@pytest.fixture(scope="module")
def h12_written(lattice_store: Store, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """What the code writes for the lattice pair, as H12's four files: the single-event
    fisher_bh diff's JSON and the report (dark theme, ``x=load``, ``y=gain``)."""
    out = tmp_path_factory.mktemp("h12")
    result = _lattice_diff(lattice_store)
    report = report_module.build_report(
        result, report_module.ReportSpec(title=H12_TITLE, x_axis=lattice.Y, y_axis=lattice.X, theme="dark")
    )
    (out / "diff_regression.json").write_text(json.dumps(result.to_json(), indent=2), encoding="utf-8")
    (out / "report.md").write_text(report.to_markdown(), encoding="utf-8")
    (out / "heatmap.svg").write_text(report.to_svg(), encoding="utf-8")
    (out / "receipt.html").write_text(report.to_html(), encoding="utf-8")
    return out


def _coords(cell: dict[str, Any]) -> tuple[float, float]:
    """``(load, gain)`` of a reference cell, from the design."""
    by_hash = {lattice.config_hash(c.config): c for c in lattice.design_cells()}
    c = by_hash[cell["config_hash"]]
    return c.load, c.gain


def _coord_text(cell: dict[str, Any]) -> str:
    load, gain = _coords(cell)
    return f"load={load:g}, gain={gain:g}"


def _headline(record: dict[str, Any]) -> str:
    return f"{record['n_safer']} of {record['n_cells']} cells safer, {record['n_worse']} worse"


def _pp1(value: float) -> str:
    """A share in percentage points to one decimal, as the report prints it (no negative zero)."""
    text = f"{100.0 * value:.1f}"
    return "0.0" if text == "-0.0" else text


def _pp0(value: float) -> int:
    return round(100.0 * value)


def _worst_ten(record: dict[str, Any]) -> list[dict[str, Any]]:
    """The single-event report's worst cells: delta descending, then the condition's key."""
    return sorted(record["cells"], key=lambda c: (-c["delta"], c["config_hash"]))[:10]


def _assert_worst_rows(rows: list[list[str]], record: dict[str, Any]) -> None:
    worst = _worst_ten(record)
    assert len(rows) == len(worst) == 10
    for row, cell in zip(rows, worst, strict=True):
        load, gain = _coords(cell)
        assert len(row) == 10, row
        assert (float(row[0]), float(row[1])) == (load, gain), (row, cell["config_hash"])
        assert row[2] == f"{cell['n_a']}/{cell['n_b']}", row
        assert row[3:6] == [_pp1(cell["rate_a"]), _pp1(cell["rate_b"]), _pp1(cell["delta"])], row
        assert float(row[6]) == float(f"{cell['p']:.3g}"), (row, cell["p"])
        assert float(row[7]) == float(f"{cell['q']:.3g}"), (row, cell["q"])
        assert row[8] == cell["verdict"], row
        if cell["mde"] is None:
            assert row[9].startswith("no room") and not re.search(r"\d+pp", row[9]), row
        else:
            assert row[9] == f"{_pp0(cell['mde'])}pp", (row, cell["mde"])
    # The two largest changes tie (+2 trips each), so the key orders them.
    assert worst[0]["delta"] == worst[1]["delta"] > 0 and worst[0]["config_hash"] < worst[1]["config_hash"]


def _methods_row(record: dict[str, Any]) -> list[str]:
    return ["fisher_bh", "unpaired", str(record["n_safer"]), str(record["n_worse"]),
            str(record["n_unchanged"]), f"{_pp0(record['max_mde'])}pp", "0.05"]


def _honesty(record: dict[str, Any]) -> tuple[str, str]:
    with_limit = [c for c in record["cells"] if c["mde"] is not None]
    unchanged = [c for c in with_limit if c["verdict"] == "unchanged"]
    top_unchanged = max(unchanged, key=lambda c: c["mde"])
    top = max(with_limit, key=lambda c: c["mde"])
    first = (f"Worst-powered unchanged cell ({_coord_text(top_unchanged)}, n={top_unchanged['n_a']}/"
             f"{top_unchanged['n_b']}) can only detect a {_pp0(top_unchanged['mde'])}pp rise. "
             f'"{record["n_worse"]} worse" is an honest claim only above that.')
    return first, f"Worst-powered cell overall: {_pp0(top['mde'])}pp ({_coord_text(top)})."


def _md_table(lines: list[str], header: str) -> list[list[str]]:
    start = lines.index(header)
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line[1:-1].split("|")])
    return rows


_WORST_HEADER = "| load | gain | n (a/b) | rate_a (pp) | rate_b (pp) | delta (pp) | p | q | verdict | MDE |"
_METHODS_HEADER = "| method | pairing | safer | worse | unchanged | max MDE | q |"
_SVG = "{http://www.w3.org/2000/svg}"


def _check_diff_json(text: str, record: dict[str, Any]) -> None:
    js = json.loads(text)
    for field in ("n_safer", "n_worse", "n_unchanged", "n_not_comparable", "dropped_a", "dropped_b",
                  "truncated", "max_mde", "horizon", "t_unit", "method", "event"):
        assert js[field] == record[field], field
    assert js["q"] == record["q_threshold"]
    assert js["seed_identity_match"] is record["paired"] is True and js["unpaired_analysis"] is True
    assert (js["n_safer"], js["n_worse"], len(js["cells"])) == (LATTICE_SAFER, LATTICE_WORSE, LATTICE_CELLS)
    cells = {c["config_hash"]: c for c in js["cells"]}
    assert [c["config_hash"] for c in js["cells"]] == [c["config_hash"] for c in record["cells"]]
    for ref in record["cells"]:
        ours = cells[ref["config_hash"]]
        for key in LATTICE_CELL_KEYS:
            if key == "mde" and ref["mde"] is None:
                assert ours["mde"] is None or math.isnan(ours["mde"]), ref["config_hash"]
            else:
                assert ours[key] == ref[key], (ref["config_hash"], key, ours[key], ref[key])


def _check_report_md(text: str, record: dict[str, Any]) -> None:
    lines = text.splitlines()
    assert lines[0] == f"# {H12_TITLE}"
    assert lines[2] == f"{_headline(record)} (fisher_bh, BH q<0.05, unpaired)."
    assert _headline(record) == "22 of 72 cells safer, 0 worse"
    _assert_worst_rows(_md_table(lines, _WORST_HEADER), record)
    assert _md_table(lines, _METHODS_HEADER) == [_methods_row(record)]
    first, second = _honesty(record)
    assert first in lines and second in lines
    assert first.startswith("Worst-powered unchanged cell (load=30, gain=1, n=32/32) can only detect a 34pp rise.")
    for line in ("- event: tripped", "- t unit: seconds", "- horizon: 5", "- method: fisher_bh",
                 "- seed identity match: true", "- unpaired analysis: true", "- q: 0.05",
                 "- n not comparable: 0", "- dropped a: 0", "- dropped b: 0",
                 "- episodes censored at horizon: 0", "- n absent: 0"):
        assert line in lines, line


def _check_heatmap(text: str, record: dict[str, Any]) -> None:
    root = ET.fromstring(text)
    by_hash = {c["config_hash"]: c for c in record["cells"]}
    rects = [r for r in root.iter(f"{_SVG}rect") if "data-cell" in r.attrib]
    assert sorted(r.attrib["data-cell"] for r in rects) == sorted(by_hash)
    xs = sorted({float(r.attrib["x"]) for r in rects})
    ys = sorted({float(r.attrib["y"]) for r in rects})
    assert len(xs) == len(lattice.LOAD) and len(ys) == len(lattice.GAIN)
    texts = [(float(t.attrib["x"]), float(t.attrib["y"]), t.text or "") for t in root.iter(f"{_SVG}text")]
    sig = [(float(r.attrib["x"]), float(r.attrib["y"])) for r in root.iter(f"{_SVG}rect") if "data-sig" in r.attrib]
    flagged, saturated = set(), set()
    for r in rects:
        cell = by_hash[r.attrib["data-cell"]]
        load, gain = _coords(cell)
        x, y, w, h = (float(r.attrib[k]) for k in ("x", "y", "width", "height"))
        # The grid: load runs along x, gain down y, both ascending.
        assert (xs.index(x), ys.index(y)) == (lattice.LOAD.index(load), lattice.GAIN.index(gain)), cell
        labels = [t for tx, ty, t in texts if tx == x + w / 2 and y < ty < y + h]
        assert len(labels) == 1, (cell["config_hash"], labels)
        assert labels[0] == _pp1(cell["delta"]), (labels, cell)
        if any(x <= sx < x + w and y <= sy < y + h for sx, sy in sig):
            flagged.add(cell["config_hash"])
        if r.attrib.get("data-sat") == "1":
            saturated.add(cell["config_hash"])
    assert len(sig) == len(flagged)
    assert flagged == {c["config_hash"] for c in record["cells"] if c["verdict"] != "unchanged"}
    assert len(flagged) == LATTICE_SAFER + LATTICE_WORSE
    both_extreme = {c["config_hash"] for c in record["cells"]
                    if c["events_a"] == c["events_b"] and c["events_a"] in (0, c["n_a"])}
    assert saturated == both_extreme and len(saturated) == 37
    strings = [t for _, _, t in texts]
    assert strings[0] == H12_TITLE and strings[1] == _headline(record)
    # The axis ticks: one per column under the grid, one per row left of it, in the design's order.
    w, h = float(rects[0].attrib["width"]), float(rects[0].attrib["height"])
    load_ticks = [(tx, t) for tx, ty, t in texts if tx in {x + w / 2 for x in xs} and ys[-1] + h < ty < ys[-1] + 2 * h]
    assert [float(t) for _, t in sorted(load_ticks)] == list(lattice.LOAD)
    gain_ticks = [(ty, t) for tx, ty, t in texts if tx < xs[0] and any(y < ty < y + h for y in ys)]
    assert [float(t) for _, t in sorted(gain_ticks)] == list(lattice.GAIN)
    first, second = _honesty(record)
    assert first + " " + second in " ".join(strings)


def _check_receipt(text: str, record: dict[str, Any], svg: str) -> None:
    assert f"<title>{html_lib.escape(H12_TITLE)}</title>" in text
    assert f"<h1>{html_lib.escape(H12_TITLE)}</h1>" in text
    assert f"<p>{html_lib.escape(_headline(record))} (fisher_bh, BH q&lt;0.05, unpaired).</p>" in text
    figure = re.search(r'<div class="figure">(<svg.*?</svg>)</div>', text, re.S)
    assert figure is not None and figure.group(1) == svg.strip()
    _check_heatmap(figure.group(1), record)
    bodies = re.findall(r"<tbody>(.*?)</tbody>", text, re.S)
    tables = [[[html_lib.unescape(c) for c in re.findall(r"<td>(.*?)</td>", tr)] for tr in re.findall(r"<tr>(.*?)</tr>", b)]
              for b in bodies]
    _assert_worst_rows(tables[0], record)
    assert tables[1] == [_methods_row(record)]
    first, second = _honesty(record)
    plain = html_lib.unescape(re.sub(r"<[^>]+>", "", text))
    assert first in plain and second in plain


@pytest.mark.parametrize("name", H12_FILES, ids=lambda name: name)
def test_h12_regression_facts_hold_on_what_the_build_writes(name: str, h12_written: Path) -> None:
    """Each of H12's files checked by the facts it holds, on what the code writes, against the
    lattice's reference record (``test_m6_multi.reference_record``): the headline counts,
    the cell set and every cell's values, the worst cells, the methods row, the honesty sentences,
    the grid and its marks."""
    path = h12_written / name
    assert path.is_file(), path
    text = path.read_text(encoding="utf-8")
    record = reference_record()
    if name == "diff_regression.json":
        _check_diff_json(text, record)
    elif name == "report.md":
        _check_report_md(text, record)
    elif name == "heatmap.svg":
        _check_heatmap(text, record)
    else:
        _check_receipt(text, record, (h12_written / "heatmap.svg").read_text(encoding="utf-8"))


# ---------- H13: the two remaining entry points use the full set ----------


def test_h13_single_run_report_json_absorbs_the_non_event_rather_than_censoring_it(tmp_path: Path) -> None:
    """``report RUN --json`` prints each condition's incidence from the run's own cell table. On
    H3's cell (5 completed at t=1, 5 violated at t=3) the violated incidence over the
    competing set is 0.5, the share of episodes that ended in it; censoring the completions
    (the reported event alone) gives 1.0 there and 1.0 on the 8/2 cell, not 0.2."""
    root = tmp_path / "store"
    write_run(root, "s13-blocker", _five_five_rows())
    code, out, err = run_cli(
        ["--store", str(root), "report", "s13-blocker", "--event", "violated",
         "--x", "task", "--out", str(tmp_path / "out"), "--json"]
    )
    assert code == 0, out + err
    doc = json.loads(out)
    cells = {c["config"]["task"]: c for c in doc["by_event"]["violated"]["cells"]}
    assert set(cells) == {"blocker", "other"}, cells
    expected = {"blocker": (10, 5, 0.5), "other": (10, 2, 0.2)}
    for task, (n, k, share) in expected.items():
        cell = cells[task]
        assert (cell["n"], cell["n_events"]) == (n, k), cell
        assert abs(cell["incidence"] - share) <= TOL, cell
        assert cell["share_differs"] is False, cell


def test_h13_saved_comparison_incidence_curves_absorb_the_non_event_rather_than_censoring_it(
    tmp_path: Path,
) -> None:
    """A saved comparison carries each condition's cumulative incidence per run
    (``charts/<condition hash>/incidence-<event>.json``). Before: 5 completed at t=1 and 5
    violated at t=3; after: 8 completed at t=1 and 2 violated at t=3. Over the competing set the
    violated curves step to 0.5 and 0.2 at t=3; censoring the completions (the reported event
    alone) would put both at 1.0."""
    root = tmp_path / "store"
    config = {"task": "blocker", "level": "one"}
    write_run(root, "before", [(config, "completed", COMPLETED_T)] * 5 + [(config, "violated", VIOLATED_T)] * 5)
    write_run(root, "after", [(config, "completed", COMPLETED_T)] * 8 + [(config, "violated", VIOLATED_T)] * 2)
    code, out, err = run_cli(
        ["--store", str(root), "diff", "before", "after", "--event", "violated", "--method", "fisher_bh", "--save"]
    )
    assert code == 0, out + err
    (chart,) = (root / ".poisson" / "artifacts" / "comparison").glob(
        f"*/charts/{config_hash(config)}/incidence-violated.json"
    )
    data = json.loads(chart.read_text(encoding="utf-8"))
    assert data["columns"] == ["t", "before", "after"], data
    rows = data["rows"]
    assert rows[0] == [0.0, 0.0, 0.0], rows
    at_event = [row for row in rows if row[0] == VIOLATED_T]
    assert len(at_event) == 1, rows
    for row in (at_event[0], rows[-1]):
        assert abs(row[1] - 0.5) <= TOL and abs(row[2] - 0.2) <= TOL, rows
