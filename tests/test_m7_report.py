"""Oracle for M7: the report renderer.

Every structural claim about SVG is asserted on the ``xml.etree.ElementTree`` tree, never
on the raw string. Golden tests use the S3 fixture through ``go1_store``; everything else
uses a synthetic ``DiffResult`` factory built directly from M6's ``cells`` columns. All
temp output goes under tmp_path. No network, no clock.

Two things the spec leaves open that this oracle pins, because I7, I11 and I19 are not
checkable without them:

- **Cell identification in SVG.** Every cell ``<rect>`` carries ``data-cell="<config_hash>"``
  for a present cell and ``data-cell="absent"`` for a grid hole. Significance glyphs carry
  ``data-sig="1"`` (spec) and sit geometrically inside their cell's rect, which is how the
  set of significant cells is recovered after attribute stripping.
- **Worst-cells table rows.** Each row is a Markdown pipe row containing, as text, the
  cell's coordinate values and the formatted ``n_a``, ``n_b``, ``rate_a``, ``rate_b``,
  ``delta``, ``p``, ``q``, ``mde`` and ``verdict``. I2(a) requires every numeric field of a
  present cell to be visible somewhere, and with ``top_n >= present`` the table is where.

Reference formatting used by the tests, per the spec's formatting rule: pp values are
``format(x * 100, ".1f")`` (delta, rate) or ``format(x * 100, ".0f")`` (mde) with ``-0.0``
normalised; p/q are ``format(x, ".3g")`` at or above 1e-3 and ``format(x, ".2e")`` below;
zero prints as ``0``.
"""

import hashlib
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from itertools import pairwise
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from proofload.diff import DiffResult, diff
from proofload.report import (
    ABSENT_FILL,
    NEUTRAL_FILL,
    AxisError,
    Cell,
    ComparisonMismatch,
    Report,
    ReportError,
    ReportSpec,
    build_report,
    heatmap,
)
from proofload.store import Store, config_hash
from proofload.survival import cell_table, censor

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_JSON = ROOT / "tests" / "fixtures" / "go1" / "golden.json"
CELL_COLUMNS = [
    "config_hash", "config", "n_a", "n_b", "events_a", "events_b", "rate_a", "rate_b",
    "delta", "stat", "p", "q", "verdict", "mde",
]
STRIP = ("fill", "stroke", "style", "class")
HEADLINE_RE = re.compile(
    r"^(\d+) of (\d+) cells safer, (\d+) worse \((\S+), BH q<([^,]+), (paired|unpaired)\)\.$"
)
HONESTY_RE = re.compile(
    r'Worst-powered cell \((.*), n=(\d+)/(\d+)\) can only detect a (\d+)pp rise\. '
    r'"(\d+) worse" is an honest claim only above that\.'
)
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
HASH_RE = re.compile(r"\b[0-9a-f]{16}\b")


# ---------- reference formatting ----------


def _no_neg_zero(s: str) -> str:
    return s[1:] if s.startswith("-") and float(s) == 0.0 else s


def _pp1(x: float) -> str:
    return _no_neg_zero(format(x * 100, ".1f"))


def _pp0(x: float) -> str:
    return _no_neg_zero(format(x * 100, ".0f"))


def _sig3(x: float) -> str:
    if x == 0:
        return "0"
    return format(x, ".2e") if x < 1e-3 else format(x, ".3g")


# ---------- synthetic DiffResult factory ----------


def make_cell(
    config: dict[str, Any],
    *,
    n_a: int = 32,
    n_b: int = 32,
    rate_a: float = 0.5,
    rate_b: float | None = None,
    delta: float = 0.0,
    p: float = 0.5,
    q: float = 0.5,
    verdict: str = "unchanged",
    mde: float = 0.2,
    stat: float = 1.0,
) -> dict[str, Any]:
    rb = rate_b if rate_b is not None else min(1.0, max(0.0, rate_a + delta))
    return {
        "config_hash": config_hash(config),
        "config": dict(config),
        "n_a": n_a,
        "n_b": n_b,
        "events_a": int(round(rate_a * n_a)),
        "events_b": int(round(rb * n_b)),
        "rate_a": rate_a,
        "rate_b": rb,
        "delta": delta,
        "stat": stat,
        "p": p,
        "q": q,
        "verdict": verdict,
        "mde": mde,
    }


def make_diff(
    cells: list[dict[str, Any]],
    *,
    method: str = "fisher_bh",
    paired: bool = False,
    q: float = 0.05,
    event: str = "fell",
    t_unit: str = "steps",
    horizon: float = 10.0,
    max_mde: float | None = None,
    n_not_comparable: int = 0,
    dropped_a: int = 0,
    dropped_b: int = 0,
    truncated: int = 0,
) -> DiffResult:
    frame = pd.DataFrame.from_records(cells, columns=CELL_COLUMNS)
    frame["config"] = frame["config"].astype(object)
    frame["verdict"] = frame["verdict"].astype(object)
    verdicts = list(frame["verdict"])
    return DiffResult(
        cells=frame,
        method=method,  # type: ignore[arg-type]
        paired=paired,
        q=q,
        event=event,
        t_unit=t_unit,
        horizon=horizon,
        n_safer=verdicts.count("safer"),
        n_worse=verdicts.count("worse"),
        n_unchanged=verdicts.count("unchanged"),
        n_not_comparable=n_not_comparable,
        max_mde=(
            max_mde if max_mde is not None else (float(frame["mde"].max()) if len(frame) else 0.0)
        ),
        dropped_a=dropped_a,
        dropped_b=dropped_b,
        truncated=truncated,
    )


def grid_diff(
    xs: list[Any],
    ys: list[Any],
    *,
    x_key: str = "mu",
    y_key: str = "push",
    delta_fn: Any = None,
    verdict_fn: Any = None,
    extra: dict[str, Any] | None = None,
    skip: set[tuple[Any, Any]] | None = None,
    **diff_kw: Any,
) -> DiffResult:
    cells = []
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            if skip and (x, y) in skip:
                continue
            config = {x_key: x, y_key: y}
            if extra:
                config.update(extra)
            delta = delta_fn(i, j) if delta_fn else 0.0
            verdict = verdict_fn(i, j, delta) if verdict_fn else "unchanged"
            cells.append(make_cell(config, delta=delta, verdict=verdict, mde=0.1 + 0.01 * ((i + j) % 5)))
    return make_diff(cells, **diff_kw)


def two_by_two() -> DiffResult:
    return make_diff(
        [
            make_cell({"mu": 0.1, "push": 10}, delta=-0.3, p=1e-4, q=2e-4, verdict="safer", mde=0.30),
            make_cell({"mu": 0.1, "push": 20}, delta=0.2, p=0.01, q=0.02, verdict="worse", mde=0.25),
            make_cell({"mu": 0.5, "push": 10}, delta=0.0, p=1.0, q=1.0, verdict="unchanged", mde=0.34),
            make_cell({"mu": 0.5, "push": 20}, delta=0.05, p=0.4, q=0.6, verdict="unchanged", mde=0.34),
        ]
    )


def spec2(**kw: Any) -> ReportSpec:
    base: dict[str, Any] = {"title": "t", "x_axis": "mu", "y_axis": "push"}
    base.update(kw)
    return ReportSpec(**base)


def render_all(report: Report) -> tuple[str, str, str]:
    return report.to_markdown(), report.to_svg(), report.to_html()


# ---------- SVG helpers ----------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def svg_root(report: Report) -> ET.Element:
    return ET.fromstring(report.to_svg())


def cell_rects(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if _local(e.tag) == "rect" and "data-cell" in e.attrib]


def glyphs(root: ET.Element) -> list[ET.Element]:
    return [e for e in root.iter() if e.attrib.get("data-sig") == "1"]


def fills_by_hash(report: Report) -> dict[str, str]:
    out = {}
    for r in cell_rects(svg_root(report)):
        if r.attrib["data-cell"] != "absent":
            out[r.attrib["data-cell"]] = r.attrib["fill"]
    return out


def strip_presentation(root: ET.Element) -> ET.Element:
    for e in root.iter():
        for attr in STRIP:
            e.attrib.pop(attr, None)
    return root


def tree_signature(e: ET.Element) -> tuple:
    return (
        _local(e.tag),
        tuple(sorted(e.attrib.items())),
        (e.text or "").strip(),
        tuple(tree_signature(c) for c in e),
    )


def rgb(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_distance(a: str, b: str) -> float:
    return math.dist(rgb(a), rgb(b))


def is_red_family(hexstr: str) -> bool:
    r, g, b = rgb(hexstr)
    return r > g and r > b


def all_fills(root: ET.Element) -> list[str]:
    return [e.attrib["fill"] for e in root.iter() if "fill" in e.attrib and HEX_RE.match(e.attrib["fill"])]


def _bbox(e: ET.Element) -> tuple[float, float, float, float]:
    x, y = float(e.attrib["x"]), float(e.attrib["y"])
    return x, y, x + float(e.attrib["width"]), y + float(e.attrib["height"])


def _inside(inner: ET.Element, outer: ET.Element) -> bool:
    ix0, iy0, ix1, iy1 = _bbox(inner)
    ox0, oy0, ox1, oy1 = _bbox(outer)
    cx, cy = (ix0 + ix1) / 2, (iy0 + iy1) / 2
    return ox0 <= cx <= ox1 and oy0 <= cy <= oy1


# ---------- markdown helpers ----------


def worst_rows(md: str, coords_text: list[str]) -> list[str]:
    rows = []
    for line in md.splitlines():
        if line.startswith("|") and not set(line.strip()) <= set("|-: "):
            if any(tok in line for tok in coords_text):
                rows.append(line)
    return rows


def numbers_in(text: str) -> list[float]:
    cleaned = HASH_RE.sub(" ", text)
    return [float(m) for m in NUMBER_RE.findall(cleaned)]


def present_cells(report: Report) -> list[Cell]:
    return [c for c in report.cells if c.present]


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def golden_frames(go1_store: Store) -> dict[str, Any]:
    a = censor(go1_store.read("go1-v0"), "fell")
    b = censor(go1_store.read("go1-v1"), "fell")
    ma, mb = go1_store.manifest("go1-v0"), go1_store.manifest("go1-v1")
    return {"a": a, "b": b, "ma": ma, "mb": mb}


@pytest.fixture(scope="module")
def golden_diff(golden_frames: dict[str, Any]) -> DiffResult:
    return diff(
        golden_frames["a"], golden_frames["b"], event="fell", method="fisher_bh", q=0.05,
        manifest_a=golden_frames["ma"], manifest_b=golden_frames["mb"],
    )


@pytest.fixture(scope="module")
def golden_report(golden_diff: DiffResult) -> Report:
    return build_report(golden_diff, ReportSpec(title="Go1 v0 -> v1", x_axis="push_pct_bw", y_axis="mu"))


# ---------- I1: determinism across processes ----------

_SUBPROCESS_SCRIPT = """
import hashlib, sys
from pathlib import Path
from proofload.store import Store
from proofload.survival import censor
from proofload.diff import diff
from proofload.report import ReportSpec, build_report
root = Path(sys.argv[1])
store = Store(root / "tests" / "fixtures" / "go1")
a, b = (censor(store.read(r), "fell") for r in ("go1-v0", "go1-v1"))
d = diff(a, b, event="fell", method="fisher_bh", q=0.05,
         manifest_a=store.manifest("go1-v0"), manifest_b=store.manifest("go1-v1"))
rep = build_report(d, ReportSpec(title="Go1 v0 -> v1", x_axis="push_pct_bw", y_axis="mu"))
for text in (rep.to_markdown(), rep.to_svg(), rep.to_html()):
    print(hashlib.sha256(text.encode("utf-8")).hexdigest())
"""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_i1_outputs_are_byte_identical_across_hash_seeds(golden_report: Report, tmp_path: Path) -> None:
    local = [_sha(t) for t in render_all(golden_report)]
    script = tmp_path / "render.py"
    script.write_text(_SUBPROCESS_SCRIPT)
    for seed in ("1", "4242"):
        proc = subprocess.run(
            [sys.executable, str(script), str(ROOT)],
            capture_output=True, text=True, cwd=ROOT,
            env={"PYTHONHASHSEED": seed, "PATH": "", "HOME": str(tmp_path)},
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.split() == local, seed


def test_i1_same_process_repeat_is_identical() -> None:
    d = two_by_two()
    first = render_all(build_report(d, spec2()))
    second = render_all(build_report(d, spec2()))
    assert first == second


# ---------- I2: no computation (scoped) ----------

COORD_WORDS = ["alpha", "beta", "gamma", "delta_", "north", "south"]


def _word_diff(**cell_overrides: Any) -> tuple[DiffResult, list[str]]:
    cells = []
    for x in ("alpha", "beta"):
        for y in ("north", "south"):
            cells.append(
                make_cell(
                    {"row": y, "col": x},
                    rate_a=0.25, delta=0.125, p=0.02, q=0.03, mde=0.15, n_a=30, n_b=31, verdict="unchanged",
                )
            )
    target = cells[0]
    target.update(cell_overrides)
    if "delta" in cell_overrides and "rate_b" not in cell_overrides:
        target["rate_b"] = target["rate_a"] + target["delta"]
    return make_diff(cells), ["alpha", "beta"]


def _svg_text(report: Report) -> str:
    return "\n".join((e.text or "") for e in svg_root(report).iter() if _local(e.tag) == "text")


def _visible(report: Report) -> str:
    return report.to_markdown() + "\n" + _svg_text(report)


@pytest.mark.parametrize(
    "field, value",
    [("n_a", 7), ("n_b", 9), ("rate_a", 0.75), ("rate_b", 0.9), ("delta", -0.4),
     ("p", 0.4), ("q", 0.6), ("mde", 0.45)],
)
def test_i2a_changing_a_numeric_cell_field_changes_the_visible_output(field: str, value: Any) -> None:
    base, _ = _word_diff()
    changed, _ = _word_diff(**{field: value})
    spec = ReportSpec(title="t", x_axis="col", y_axis="row", top_n=10)
    assert _visible(build_report(base, spec)) != _visible(build_report(changed, spec))


def test_i2b_all_zero_diff_prints_only_zeros_in_table_and_honesty() -> None:
    cells = [
        make_cell({"row": y, "col": x}, n_a=0, n_b=0, rate_a=0.0, rate_b=0.0, delta=0.0, p=0.0, q=0.0, mde=0.0, stat=0.0)
        for x in ("alpha", "beta") for y in ("north", "south")
    ]
    d = make_diff(cells, max_mde=0.0)
    assert d.max_mde == 0.0
    report = build_report(d, ReportSpec(title="t", x_axis="col", y_axis="row", top_n=10))
    md = report.to_markdown()
    rows = worst_rows(md, ["alpha", "beta"])
    assert len(rows) == 4
    for row in rows:
        assert all(v == 0.0 for v in numbers_in(row)), row
    honesty_line = next(line for line in md.splitlines() if "Worst-powered cell" in line)
    assert all(v == 0.0 for v in numbers_in(honesty_line)), honesty_line
    assert all(v == 0.0 for v in numbers_in(report.honesty))


# ---------- I3: cell completeness ----------


def test_i3_every_cell_once_and_holes_marked_absent() -> None:
    d = grid_diff([0.1, 0.2, 0.3], [10, 20], skip={(0.2, 20)})
    report = build_report(d, spec2())
    assert len(report.cells) == len(report.x_values) * max(1, len(report.y_values)) == 6
    hashes = [c.config_hash for c in report.cells if c.present]
    assert sorted(hashes) == sorted(d.cells["config_hash"])
    assert len(set(hashes)) == len(hashes) == 5
    absent = [c for c in report.cells if not c.present]
    assert len(absent) == 1 and report.n_absent == 1
    assert absent[0].config_hash is None
    assert absent[0].coords == (0.2, 20)
    assert report.n_safer + report.n_worse + report.n_unchanged == 5


def test_i3_fixed_filters_cells_and_keeps_survivors_once() -> None:
    cells = []
    for x in (1, 2):
        for y in (1, 2):
            for z in ("a", "b"):
                cells.append(make_cell({"x": x, "y": y, "z": z}, delta=0.1 if z == "a" else -0.1))
    d = make_diff(cells)
    report = build_report(d, ReportSpec(title="t", x_axis="x", y_axis="y", fixed={"z": "a"}))
    assert len(report.cells) == 4 and report.n_absent == 0
    assert all(c.present and c.delta == 0.1 for c in report.cells)
    assert sorted(c.config_hash for c in report.cells) == sorted(
        config_hash({"x": x, "y": y, "z": "a"}) for x in (1, 2) for y in (1, 2)
    )


# ---------- I4: count arithmetic + headline ----------


def _parse_headline(report: Report) -> tuple[int, int, int, str, str, str]:
    m = HEADLINE_RE.match(report.headline)
    assert m, report.headline
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4), m.group(5), m.group(6)


def test_i4_counts_and_headline_agree() -> None:
    d = grid_diff(
        [0.1, 0.2, 0.3], [10, 20, 30],
        delta_fn=lambda i, j: (i - 1) * 0.2,
        verdict_fn=lambda i, j, dl: "safer" if dl < 0 else "worse" if dl > 0 else "unchanged",
        skip={(0.3, 30)},
        paired=True,
    )
    report = build_report(d, spec2())
    present = present_cells(report)
    assert report.n_safer + report.n_worse + report.n_unchanged == len(present) == 8
    for verdict, count in (("safer", report.n_safer), ("worse", report.n_worse), ("unchanged", report.n_unchanged)):
        assert count == sum(c.verdict == verdict for c in present)
    safer, n_present, worse, method, q_text, pairing = _parse_headline(report)
    assert (safer, n_present, worse) == (report.n_safer, len(present), report.n_worse)
    assert method == d.method and pairing == "paired"
    assert q_text == _sig3(d.q)
    assert report.headline in report.to_markdown() and report.headline in report.to_html()


# ---------- I5: verdicts copied ----------


def test_i5_verdicts_are_copied_not_recomputed() -> None:
    cells = [
        make_cell({"x": 1, "y": 1}, delta=-0.5, q=0.9, verdict="safer"),
        make_cell({"x": 1, "y": 2}, delta=0.5, q=0.9, verdict="worse"),
        make_cell({"x": 2, "y": 1}, delta=-0.5, q=1e-9, verdict="unchanged"),
        make_cell({"x": 2, "y": 2}, delta=0.0, q=1e-9, verdict="unchanged"),
    ]
    d = make_diff(cells, q=0.05)
    report = build_report(d, ReportSpec(title="t", x_axis="x", y_axis="y"))
    by_hash = {c.config_hash: c for c in report.cells}
    for row in d.cells.itertuples(index=False):
        assert by_hash[row.config_hash].verdict == row.verdict
    assert (report.n_safer, report.n_worse, report.n_unchanged) == (1, 1, 2)


# ---------- I6: sign convention ----------


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_i6_red_family_fill_iff_some_positive_delta(theme: str) -> None:
    negative = grid_diff([0.1, 0.2], [10, 20], delta_fn=lambda i, j: -0.1 * (1 + i + j),
                         verdict_fn=lambda i, j, dl: "safer" if i == 0 else "unchanged")
    positive = grid_diff([0.1, 0.2], [10, 20], delta_fn=lambda i, j: 0.3 if (i, j) == (0, 0) else -0.2,
                         verdict_fn=lambda i, j, dl: "worse" if dl > 0 else "unchanged")
    neg_root = svg_root(build_report(negative, spec2(theme=theme)))
    pos_root = svg_root(build_report(positive, spec2(theme=theme)))
    assert not any(is_red_family(f) for f in all_fills(neg_root))
    assert any(is_red_family(f) for f in all_fills(pos_root))


# ---------- I7: redundant encoding ----------


def test_i7_glyphs_survive_attribute_stripping_and_identify_significant_cells() -> None:
    d = two_by_two()
    report = build_report(d, spec2())
    root = strip_presentation(svg_root(report))
    sig = glyphs(root)
    assert len(sig) == report.n_safer + report.n_worse == 2
    for e in root.iter():
        assert e.attrib.get("data-sig", "1") == "1"
    rects = cell_rects(root)
    recovered = set()
    for g in sig:
        owners = [r for r in rects if _inside(g, r)]
        assert len(owners) == 1, "glyph must sit inside exactly one cell rect"
        recovered.add(owners[0].attrib["data-cell"])
    expected = {c.config_hash for c in report.cells if c.present and c.verdict != "unchanged"}
    assert recovered == expected


# ---------- I8: golden ----------


def test_i8_golden_sixty_zero_full_grid_and_deltas(golden_report: Report) -> None:
    assert golden_report.n_safer == 60 and golden_report.n_worse == 0
    assert golden_report.n_unchanged == 340 and golden_report.n_absent == 0
    assert len(golden_report.cells) == 400 and all(c.present for c in golden_report.cells)
    assert len(golden_report.x_values) == 20 and len(golden_report.y_values) == 20
    assert golden_report.headline.startswith("60 of 400 cells safer, 0 worse (fisher_bh, BH q<0.05, ")
    published = {(c["mu"], c["push_pct_bw"]): c for c in json.loads(GOLDEN_JSON.read_text())["cells"]}
    assert len(published) == 400
    for cell in golden_report.cells:
        push, mu = cell.coords
        pub = published[(mu, push)]
        assert abs(cell.delta - (pub["fell_b"] - pub["fell_a"]) / 32) <= 1e-9, cell.coords
        assert cell.n_a == 32 and cell.n_b == 32


def test_i8_golden_svg_size_is_sane(golden_report: Report) -> None:
    assert len(golden_report.to_svg().encode("utf-8")) < 200_000


# ---------- I9: honesty block ----------


def _check_honesty(report: Report, diff_result: DiffResult) -> None:
    m = HONESTY_RE.search(report.honesty)
    assert m, report.honesty
    coords_text, n_a, n_b, mde_pp, worse = m.groups()
    assert mde_pp == _pp0(diff_result.max_mde)
    assert int(worse) == report.n_worse
    attaining = [c for c in present_cells(report) if c.mde == diff_result.max_mde]
    assert attaining
    printed = dict(part.split("=", 1) for part in coords_text.split(", "))
    axes = [report.spec.x_axis] + ([report.spec.y_axis] if report.spec.y_axis else [])
    assert set(printed) == set(axes)

    def matches(cell: Cell) -> bool:
        for axis, value in zip(axes, cell.coords, strict=True):
            shown = printed[axis]
            try:
                if not math.isclose(float(shown), float(value)):
                    return False
            except (TypeError, ValueError):
                if shown != str(value):
                    return False
        return int(n_a) == cell.n_a and int(n_b) == cell.n_b

    assert any(matches(c) for c in attaining)
    for text in render_all(report):
        assert "Worst-powered cell" in text


def test_i9_honesty_block_on_synthetic_with_ties() -> None:
    d = two_by_two()
    _check_honesty(build_report(d, spec2()), d)


def test_i9_honesty_block_when_nothing_is_significant() -> None:
    d = grid_diff([0.1, 0.2], [10, 20], delta_fn=lambda i, j: 0.01 * (i - j))
    report = build_report(d, spec2())
    assert report.n_safer == report.n_worse == 0
    _check_honesty(report, d)


def test_i9_honesty_block_on_golden(golden_report: Report, golden_diff: DiffResult) -> None:
    _check_honesty(golden_report, golden_diff)


# ---------- I10: SVG hygiene ----------


def _check_svg_hygiene(svg: str) -> None:
    root = ET.fromstring(svg)
    assert _local(root.tag) == "svg"
    assert "viewBox" in root.attrib and len(root.attrib["viewBox"].split()) == 4
    assert not [e for e in root.iter() if _local(e.tag) == "script"]
    for e in root.iter():
        for key, value in e.attrib.items():
            assert not key.endswith("href"), (key, value)
            assert "url(" not in value and "@import" not in value
        assert "url(" not in (e.text or "") and "@import" not in (e.text or "")
    assert "<script" not in svg
    assert svg.lstrip().startswith("<svg") or svg.lstrip().startswith("<?xml")


def test_i10_svg_hygiene_synthetic_and_golden(golden_report: Report) -> None:
    _check_svg_hygiene(build_report(two_by_two(), spec2()).to_svg())
    _check_svg_hygiene(golden_report.to_svg())
    assert heatmap(golden_report) == golden_report.to_svg()


def test_i10_text_is_xml_escaped() -> None:
    d = make_diff([
        make_cell({"kind": "a<b&c", "level": 1}, delta=0.1),
        make_cell({"kind": 'x"y', "level": 1}, delta=-0.1),
        make_cell({"kind": "a<b&c", "level": 2}, delta=0.0),
        make_cell({"kind": 'x"y', "level": 2}, delta=0.05),
    ])
    report = build_report(d, ReportSpec(title="ti<tle & \"quotes\"", x_axis="kind", y_axis="level"))
    svg = report.to_svg()
    root = ET.fromstring(svg)
    texts = [(e.text or "") for e in root.iter() if _local(e.tag) == "text"]
    assert any("a<b&c" in t for t in texts)
    assert "a<b&c" not in svg and "&lt;b&amp;c" in svg
    html = report.to_html()
    assert "<svg" in html and "</svg>" in html
    inline_svg = "<svg" + html.split("<svg", 1)[1].split("</svg>", 1)[0] + "</svg>"
    ET.fromstring(inline_svg)
    assert "a<b&c" not in html


# ---------- I11: colour law ----------


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_i11a_zero_delta_is_neutral_and_holes_are_absent_fill(theme: str) -> None:
    d = grid_diff([0.1, 0.2, 0.3], [10, 20], delta_fn=lambda i, j: 0.0 if (i, j) == (0, 0) else 0.2 * (i - 1),
                  skip={(0.3, 20)})
    report = build_report(d, spec2(theme=theme))
    rects = cell_rects(svg_root(report))
    by_cell = {r.attrib["data-cell"]: r.attrib["fill"] for r in rects}
    zero_hash = config_hash({"mu": 0.1, "push": 10})
    assert by_cell[zero_hash] == NEUTRAL_FILL[theme]
    assert by_cell["absent"] == ABSENT_FILL[theme]
    assert sum(r.attrib["data-cell"] == "absent" for r in rects) == 1
    assert all(HEX_RE.match(f) for f in by_cell.values())


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_i11b_fill_is_a_pure_function_of_ratio_significance_theme(theme: str) -> None:
    d1 = make_diff([
        make_cell({"x": 1, "y": 1}, delta=0.2, verdict="worse"),
        make_cell({"x": 1, "y": 2}, delta=-0.2, verdict="safer"),
        make_cell({"x": 2, "y": 1}, delta=0.2, verdict="unchanged"),
        make_cell({"x": 2, "y": 2}, delta=-0.4, verdict="safer"),
    ])
    d2 = make_diff([
        make_cell({"a": "p", "b": "q"}, delta=0.1, verdict="worse"),
        make_cell({"a": "p", "b": "r"}, delta=-0.1, verdict="safer"),
        make_cell({"a": "s", "b": "q"}, delta=0.1, verdict="unchanged"),
        make_cell({"a": "s", "b": "r"}, delta=-0.2, verdict="safer"),
    ])
    f1 = fills_by_hash(build_report(d1, ReportSpec(title="t", x_axis="x", y_axis="y", theme=theme, color_max=0.4)))
    f2 = fills_by_hash(build_report(d2, ReportSpec(title="t", x_axis="a", y_axis="b", theme=theme, color_max=0.2)))
    pairs = [
        ({"x": 1, "y": 1}, {"a": "p", "b": "q"}),
        ({"x": 1, "y": 2}, {"a": "p", "b": "r"}),
        ({"x": 2, "y": 1}, {"a": "s", "b": "q"}),
        ({"x": 2, "y": 2}, {"a": "s", "b": "r"}),
    ]
    for c1, c2 in pairs:
        assert f1[config_hash(c1)] == f2[config_hash(c2)], (c1, c2)
    assert f1[config_hash({"x": 1, "y": 1})] != f1[config_hash({"x": 2, "y": 1})]


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_i11c_hypothesis_distance_from_neutral_is_monotone(theme: str) -> None:
    @settings(max_examples=40, deadline=None)
    @given(
        deltas=st.lists(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False), min_size=2, max_size=12, unique=True),
        significant=st.booleans(),
    )
    def check(deltas: list[float], significant: bool) -> None:
        verdict_of = (lambda dl: "safer" if dl < 0 else "worse" if dl > 0 else "unchanged") if significant else (lambda dl: "unchanged")
        cells = [make_cell({"k": i, "row": 0}, delta=dl, verdict=verdict_of(dl)) for i, dl in enumerate(deltas)]
        report = build_report(make_diff(cells), ReportSpec(title="t", x_axis="k", theme=theme))
        fills = fills_by_hash(report)
        neutral = NEUTRAL_FILL[theme]
        for side in (lambda dl: dl > 0, lambda dl: dl < 0):
            ordered = sorted((abs(dl), fills[config_hash({"k": i, "row": 0})]) for i, dl in enumerate(deltas) if side(dl))
            dists = [rgb_distance(f, neutral) for _, f in ordered]
            assert all(b >= a - 1e-9 for a, b in pairwise(dists)), (theme, ordered)

    check()


# ---------- I12: theme separation ----------


def test_i12_dark_and_light_trees_identical_after_stripping_presentation(golden_diff: DiffResult) -> None:
    d = two_by_two()
    dark = strip_presentation(svg_root(build_report(d, spec2(theme="dark"))))
    light = strip_presentation(svg_root(build_report(d, spec2(theme="light"))))
    assert tree_signature(dark) == tree_signature(light)
    assert any("data-cell" in e.attrib for e in dark.iter())
    gd = strip_presentation(ET.fromstring(build_report(golden_diff, ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu", theme="dark")).to_svg()))
    gl = strip_presentation(ET.fromstring(build_report(golden_diff, ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu", theme="light")).to_svg()))
    assert tree_signature(gd) == tree_signature(gl)


# ---------- I13: axis arity ----------


def test_i13_two_axes_heatmap_and_one_axis_strip() -> None:
    d2 = grid_diff([0.1, 0.2], [10, 20, 30])
    r2 = build_report(d2, spec2())
    assert len(r2.y_values) == 3 > 1 and len(r2.x_values) == 2 and len(r2.cells) == 6
    d1 = make_diff([make_cell({"mu": v}, delta=0.1 * i) for i, v in enumerate([0.3, 0.1, 0.2])])
    r1 = build_report(d1, ReportSpec(title="t", x_axis="mu"))
    assert r1.y_values == () and len(r1.cells) == 3 == len(r1.x_values)
    assert all(len(c.coords) == 1 for c in r1.cells)
    _check_svg_hygiene(r1.to_svg())
    assert len(cell_rects(svg_root(r1))) == 3


def test_i13_zero_free_axes_raises() -> None:
    d = make_diff([make_cell({"mu": 0.1, "push": 10}, delta=0.1)])
    with pytest.raises(AxisError):
        build_report(d, ReportSpec(title="t", x_axis="mu"))


def test_i13_three_free_axes_raises_naming_keys() -> None:
    cells = [make_cell({"mu": x, "push": y, "z": z}) for x in (1, 2) for y in (1, 2) for z in ("a", "b")]
    d = make_diff(cells)
    with pytest.raises(AxisError) as ei:
        build_report(d, spec2())
    assert "z" in str(ei.value)


@pytest.mark.parametrize("bad", [
    {"x_axis": "nope", "y_axis": "push"},
    {"x_axis": "mu", "y_axis": "nope"},
    {"x_axis": "mu", "y_axis": "push", "fixed": {"nope": 1}},
])
def test_i13_unknown_keys_raise(bad: dict[str, Any]) -> None:
    d = grid_diff([0.1, 0.2], [10, 20])
    with pytest.raises(AxisError) as ei:
        build_report(d, ReportSpec(title="t", **bad))
    assert "nope" in str(ei.value)
    assert issubclass(AxisError, ReportError) and issubclass(ComparisonMismatch, ReportError)


# ---------- I14: ordering ----------


def _shuffled(d: DiffResult, order: list[int]) -> DiffResult:
    frame = d.cells.iloc[order].reset_index(drop=True)
    return DiffResult(**{**{f: getattr(d, f) for f in d.__dataclass_fields__}, "cells": frame})


def test_i14_numeric_and_lexicographic_ordering() -> None:
    numeric = grid_diff([10, 2, 33.5, 1], ["b", "a", "c"])
    r = build_report(numeric, spec2())
    assert r.x_values == (1, 2, 10, 33.5) and r.y_values == ("a", "b", "c")
    strings = grid_diff(["10", "2", "1"], ["x"])
    rs = build_report(strings, spec2())
    assert rs.x_values == ("1", "2", "10")
    mixed = grid_diff(["10", "b", "1"], ["x"])
    rm = build_report(mixed, spec2())
    assert rm.x_values == ("1", "10", "b")


def test_i14_hypothesis_shuffling_input_rows_is_byte_identical() -> None:
    @settings(max_examples=40, deadline=None)
    @given(
        xs=st.one_of(
            st.lists(st.integers(min_value=-50, max_value=50), min_size=2, max_size=5, unique=True),
            st.lists(st.text(alphabet="abcxyz", min_size=1, max_size=3), min_size=2, max_size=5, unique=True),
        ),
        ys=st.lists(st.floats(min_value=0.0, max_value=9.0, allow_nan=False), min_size=1, max_size=4, unique=True),
        seed=st.integers(min_value=0, max_value=10**6),
    )
    def check(xs: list[Any], ys: list[float], seed: int) -> None:
        d = grid_diff(xs, ys, delta_fn=lambda i, j: ((i * 7 + j * 3 + seed) % 11 - 5) / 20)
        n = len(d.cells)
        order = list(range(n))
        for k in range(n - 1, 0, -1):
            swap = (seed * 31 + k * 17) % (k + 1)
            order[k], order[swap] = order[swap], order[k]
        a = build_report(d, spec2())
        b = build_report(_shuffled(d, order), spec2())
        assert render_all(a) == render_all(b)
        assert a.x_values == tuple(sorted(xs)) and a.y_values == tuple(sorted(ys))
        assert [c.config_hash for c in a.cells] == [c.config_hash for c in b.cells]

    check()


# ---------- I15: formatting ----------


def test_i15_hypothesis_table_numbers_match_reference_formats() -> None:
    @settings(max_examples=60, deadline=None)
    @given(
        rate_a=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        delta=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
        p=st.floats(min_value=1e-12, max_value=1.0, allow_nan=False),
        q=st.floats(min_value=1e-12, max_value=1.0, allow_nan=False),
        mde=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        n_a=st.integers(min_value=1, max_value=999),
        n_b=st.integers(min_value=1, max_value=999),
    )
    def check(rate_a: float, delta: float, p: float, q: float, mde: float, n_a: int, n_b: int) -> None:
        rate_b = min(1.0, max(0.0, rate_a + delta))
        cells = [
            make_cell({"col": "alpha", "row": "north"}, rate_a=rate_a, rate_b=rate_b, delta=delta, p=p, q=q, mde=mde, n_a=n_a, n_b=n_b),
            make_cell({"col": "beta", "row": "north"}, delta=0.0, mde=0.0),
        ]
        report = build_report(make_diff(cells), ReportSpec(title="t", x_axis="col", y_axis="row", top_n=5))
        md, svg, html = render_all(report)
        for text in (md, svg, html):
            assert "-0.0" not in text
        rows = worst_rows(md, ["alpha"])
        assert len(rows) == 1
        row = rows[0]
        for expected in (_pp1(rate_a), _pp1(rate_b), _pp1(delta), _pp0(mde), _sig3(p), _sig3(q), str(n_a), str(n_b), "unchanged"):
            assert expected in row, (expected, row)
        if q < 1e-3:
            assert re.search(r"\d\.\d\de-\d\d", row)

    check()


@pytest.mark.parametrize("delta", [-0.0004, -0.00049, 0.0, -0.0])
def test_i15_negative_zero_never_appears(delta: float) -> None:
    cells = [make_cell({"col": "alpha", "row": "north"}, delta=delta, mde=0.004), make_cell({"col": "beta", "row": "north"}, delta=0.1)]
    report = build_report(make_diff(cells), ReportSpec(title="t", x_axis="col", y_axis="row"))
    for text in render_all(report):
        assert "-0.0" not in text and "-0pp" not in text
    row = worst_rows(report.to_markdown(), ["alpha"])[0]
    assert "0.0" in row and "-0.0" not in row


def test_i15_round_half_even_and_scientific_threshold() -> None:
    cells = [
        make_cell({"col": "alpha", "row": "north"}, delta=0.00125, p=0.00099, q=0.001, mde=0.125),
        make_cell({"col": "beta", "row": "north"}, delta=0.00135, p=0.5, q=0.0005, mde=0.135),
    ]
    report = build_report(make_diff(cells), ReportSpec(title="t", x_axis="col", y_axis="row"))
    md = report.to_markdown()
    alpha = worst_rows(md, ["alpha"])[0]
    beta = worst_rows(md, ["beta"])[0]
    assert _pp1(0.00125) in alpha and _pp0(0.125) in alpha
    assert _sig3(0.00099) in alpha and "e-" in _sig3(0.00099)
    assert _sig3(0.001) in alpha and "e" not in _sig3(0.001)
    assert _pp1(0.00135) in beta and _sig3(0.0005) in beta


# ---------- I16: purity ----------


def test_i16_module_touches_no_filesystem_clock_network_or_rng() -> None:
    import proofload.report as report_module

    source = Path(report_module.__file__).read_text()
    for banned in ("import os", "from os", "import time", "from time", "import datetime", "from datetime",
                   "import random", "from random", "import socket", "import requests", "import httpx",
                   "import urllib", "import pathlib", "from pathlib", "import scipy", "from scipy",
                   "import matplotlib", "import plotly", "import seaborn", "import altair", "open("):
        assert banned not in source, banned


def test_i16_generated_at_and_manifests_are_omitted_not_invented(golden_diff: DiffResult, golden_frames: dict[str, Any]) -> None:
    spec = ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu")
    bare = build_report(golden_diff, spec)
    assert "generated_at" not in bare.provenance and "run_id_a" not in bare.provenance
    assert "generated_at" not in bare.to_markdown().lower().replace(" ", "_")
    stamped = build_report(golden_diff, ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu", generated_at="2026-09-03T00:00:00Z"))
    assert stamped.provenance["generated_at"] == "2026-09-03T00:00:00Z"
    assert "2026-09-03T00:00:00Z" in stamped.to_markdown() and "2026-09-03T00:00:00Z" in stamped.to_html()
    with_runs = build_report(golden_diff, spec, manifests=(golden_frames["ma"], golden_frames["mb"]))
    assert with_runs.provenance["run_id_a"] == "go1-v0" and with_runs.provenance["run_id_b"] == "go1-v1"
    assert with_runs.provenance["run_salt"] == golden_frames["ma"].run_salt
    assert "go1-v0" in with_runs.to_markdown() and "go1-v0" not in bare.to_markdown()
    for key in ("event", "t_unit", "horizon", "method", "paired", "q", "n_not_comparable", "dropped_a", "dropped_b", "truncated", "n_absent", "proofload_version"):
        assert key in bare.provenance, key
    assert bare.provenance["event"] == "fell" and bare.provenance["n_absent"] == 0


# ---------- I17: survival optionality ----------


def _single_insertion(without: str, with_: str) -> bool:
    if without == with_:
        return True
    if len(with_) < len(without):
        return False
    prefix = 0
    while prefix < len(without) and without[prefix] == with_[prefix]:
        prefix += 1
    suffix = 0
    while suffix < len(without) - prefix and without[-1 - suffix] == with_[-1 - suffix]:
        suffix += 1
    return prefix + suffix == len(without)


def test_i17_curves_add_one_contiguous_section_and_change_nothing_else(golden_frames: dict[str, Any], golden_diff: DiffResult) -> None:
    ta = cell_table(golden_frames["a"], "fell")
    tb = cell_table(golden_frames["b"], "fell")
    curves = {h: (ca, cb) for h, ca, cb in zip(ta["config_hash"], ta["curve"], tb["curve"], strict=True)}
    spec = ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu")
    without = build_report(golden_diff, spec)
    with_ = build_report(golden_diff, spec, curves=curves)
    assert with_.to_svg() == without.to_svg()
    assert with_.cells == without.cells and with_.headline == without.headline
    for a, b in ((without.to_markdown(), with_.to_markdown()), (without.to_html(), with_.to_html())):
        assert len(b) > len(a)
        assert _single_insertion(a, b)


# ---------- I18: comparison table ----------


def test_i18_rows_labelled_by_method_attribute_not_mapping_key(golden_frames: dict[str, Any], golden_diff: DiffResult) -> None:
    kw = {"event": "fell", "q": 0.05, "manifest_a": golden_frames["ma"], "manifest_b": golden_frames["mb"]}
    mcnemar = diff(golden_frames["a"], golden_frames["b"], method="mcnemar_bh", **kw)
    logrank = diff(golden_frames["a"], golden_frames["b"], method="logrank_bh", **kw)
    report = build_report(golden_diff, ReportSpec(
        title="g", x_axis="push_pct_bw", y_axis="mu",
        comparison={"paired": mcnemar, "logrank_bh": logrank, "fisher_bh": mcnemar},
    ))
    md = report.to_markdown()
    rows = [line for line in md.splitlines() if line.startswith("|") and ("mcnemar_bh" in line or "logrank_bh" in line)]
    assert sum("mcnemar_bh" in r for r in rows) == 2
    assert sum("logrank_bh" in r for r in rows) == 1
    for r in rows:
        if "mcnemar_bh" in r:
            assert f"{mcnemar.n_safer}" in r
        if "logrank_bh" in r:
            assert f"{logrank.n_safer}" in r
    assert not any(line.startswith("| paired") for line in md.splitlines())


def test_i18_mismatching_comparison_raises(golden_frames: dict[str, Any], golden_diff: DiffResult) -> None:
    a, b = golden_frames["a"], golden_frames["b"]
    kw = {"q": 0.05, "manifest_a": golden_frames["ma"], "manifest_b": golden_frames["mb"]}
    spec = ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu")
    truncated_b = b.copy()
    truncated_b["horizon"] = 3.0
    truncated_b.loc[truncated_b["t"] > 3.0, "observed"] = False
    truncated_b.loc[truncated_b["t"] > 3.0, "t"] = 3.0
    other_horizon = diff(a, truncated_b, event="fell", method="logrank_bh", **kw)
    assert other_horizon.horizon != golden_diff.horizon
    with pytest.raises(ComparisonMismatch):
        build_report(golden_diff, ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu", comparison={"x": other_horizon}))
    other_event = diff(a, b, event="survived", method="fisher_bh", **kw)
    with pytest.raises(ComparisonMismatch):
        build_report(golden_diff, ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu", comparison={"x": other_event}))
    fewer = diff(a[a["replicate_index"] < 16], b, event="fell", method="fisher_bh", **kw)
    with pytest.raises(ComparisonMismatch):
        build_report(golden_diff, ReportSpec(title="g", x_axis="push_pct_bw", y_axis="mu", comparison={"x": fewer}))
    agreeing = diff(a, b, event="fell", method="mcnemar_bh", **kw)
    ok = build_report(golden_diff, ReportSpec(title=spec.title, x_axis=spec.x_axis, y_axis=spec.y_axis, comparison={"x": agreeing}))
    assert "mcnemar_bh" in ok.to_markdown()


# ---------- I19: worst-cells table ----------


def _table_order(md: str, coord_words: list[str]) -> list[str]:
    order = []
    for row in worst_rows(md, coord_words):
        for w in coord_words:
            if w in row:
                order.append(w)
                break
    return order


def test_i19_worst_cells_rows_count_sort_and_tiebreak() -> None:
    words = ["alpha", "beta", "gamma", "delta_", "epsilon", "zeta"]
    deltas = [0.2, -0.1, 0.2, 0.05, 0.2, -0.3]
    cells = [make_cell({"col": w, "row": "north"}, delta=dl, p=0.1 * (i + 1), q=0.2 * (i + 1) / 6, mde=0.1 + 0.05 * i, n_a=10 + i, n_b=20 + i)
             for i, (w, dl) in enumerate(zip(words, deltas, strict=True))]
    d = make_diff(cells)
    for top_n in (3, 6, 10):
        report = build_report(d, ReportSpec(title="t", x_axis="col", y_axis="row", top_n=top_n))
        present = present_cells(report)
        expected = sorted(present, key=lambda c: (-c.delta, c.config_hash))[: min(top_n, len(present))]
        by_word = {c.coords[0]: c for c in present}
        md = report.to_markdown()
        order = _table_order(md, words)
        assert order == [c.coords[0] for c in expected]
        for row, cell in zip(worst_rows(md, words), expected, strict=True):
            for expected_text in (_pp1(cell.rate_a), _pp1(cell.rate_b), _pp1(cell.delta), _sig3(cell.p), _sig3(cell.q), _pp0(cell.mde), str(cell.n_a), str(cell.n_b), cell.verdict):
                assert expected_text in row, (expected_text, row)
            assert cell is by_word[cell.coords[0]]


def test_i19_absent_cells_never_appear_in_table() -> None:
    d = grid_diff(["alpha", "beta", "gamma"], ["north", "south"], x_key="col", y_key="row", skip={("gamma", "south")}, delta_fn=lambda i, j: 0.1 * i)
    report = build_report(d, ReportSpec(title="t", x_axis="col", y_axis="row", top_n=10))
    rows = worst_rows(report.to_markdown(), ["alpha", "beta", "gamma"])
    assert len(rows) == 5 == len(present_cells(report))


# ---------- I20: scale guard ----------


def test_i20_three_thousand_cells_render_in_all_formats() -> None:
    xs = list(range(60))
    ys = list(range(50))
    d = grid_diff(xs, ys, x_key="x", y_key="y",
                  delta_fn=lambda i, j: ((i * j) % 21 - 10) / 20,
                  verdict_fn=lambda i, j, dl: "safer" if dl < -0.3 else "worse" if dl > 0.3 else "unchanged")
    report = build_report(d, ReportSpec(title="big", x_axis="x", y_axis="y"))
    assert len(report.cells) == 3000 and report.n_absent == 0
    assert report.n_safer + report.n_worse + report.n_unchanged == 3000
    assert report.n_safer == int((d.cells["verdict"] == "safer").sum())
    md, svg, html = render_all(report)
    root = ET.fromstring(svg)
    assert len(cell_rects(root)) == 3000
    assert len(glyphs(root)) == report.n_safer + report.n_worse
    _check_svg_hygiene(svg)
    assert report.headline in md and report.headline in html
    pipe_rows = [line for line in md.splitlines() if line.startswith("|")]
    assert len(pipe_rows) < 100
