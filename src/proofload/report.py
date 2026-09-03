"""M7: render a DiffResult as Markdown, a standalone SVG heatmap, and a single-file HTML receipt.

M7 computes no statistics. Every number it prints is a field on the ``DiffResult``, on the
``KMCurve`` pair it is optionally handed, or on the ``RunManifest`` pair. One private
formatting helper does every float-to-string conversion; that helper is the whole defence
for byte determinism and for the no ``-0.0`` rule.

Sign convention: ``delta = rate_b - rate_a``; negative is *safer* only when ``event`` names
a failure. The event is printed in the provenance and the legend so a reader can check.
"""

from __future__ import annotations

import html as _html
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal
from xml.sax.saxutils import escape as _xml_escape

from proofload import __version__
from proofload.diff import DiffResult
from proofload.store import RunManifest
from proofload.survival import KMCurve

Theme = Literal["dark", "light"]

NEUTRAL_FILL: dict[Theme, str] = {"dark": "#1F1F22", "light": "#EDEDEA"}
ABSENT_FILL: dict[Theme, str] = {"dark": "#141416", "light": "#F7F7F4"}

_EPISTEMIC_FENCE = (
    "This is empirical evidence under a stated test envelope, not formal verification. "
    "Cells outside the envelope were not tested; cells inside it were tested at the stated "
    "replicate count and can only detect effects at or above the reported MDE."
)

_SURVIVED = "#3ECF8E"
_FAILED = "#FF4D4D"
_CANVAS: dict[Theme, str] = {"dark": "#0E0E10", "light": "#FFFFFF"}
_TEXT: dict[Theme, str] = {"dark": "#E6E6E6", "light": "#1A1A1A"}
_MUTED: dict[Theme, str] = {"dark": "#8A8A90", "light": "#6B6B70"}
_GLYPH: dict[Theme, str] = {"dark": "#FFFFFF", "light": "#000000"}
_GRID_STROKE: dict[Theme, str] = {"dark": "#0E0E10", "light": "#FFFFFF"}
_NONSIG_SCALE = 0.45  # non-significant cells sit this far along the ramp toward neutral
_FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
_CHAR_EM = 0.6  # assumed advance of a mono glyph, in em


class ReportError(Exception):
    """The report cannot be built as requested."""


class AxisError(ReportError):
    """0 or more than 2 free axes, or an unknown key in the spec."""


class ComparisonMismatch(ReportError):
    """A comparison diff is not over the same data as the primary."""


# ---------- formatting: the single helper ----------


def _fmt(value: Any, kind: str) -> str:
    """Every float-to-string conversion in this module goes through here.

    kinds: "pp1" (fraction -> percentage points, 1 dp), "pp0" (0 dp), "sig3" (3 s.f.,
    scientific below 1e-3), "int", "coord" (an axis value), "num" (a plain number).
    Round-half-even is Python's own ``format``; ``-0.0`` and ``-0`` are normalised.
    """
    if kind == "int":
        return str(int(value))
    if kind == "pp1":
        return _no_negative_zero(format(float(value) * 100, ".1f"))
    if kind == "pp0":
        return _no_negative_zero(format(float(value) * 100, ".0f"))
    if kind == "sig3":
        x = float(value)
        if x == 0:
            return "0"
        return format(x, ".2e") if abs(x) < 1e-3 else format(x, ".3g")
    if kind == "num":
        return _no_negative_zero(format(float(value), ".10g"))
    if kind == "coord":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, int):
            return str(value)
        return _no_negative_zero(format(value, ".10g"))
    raise ReportError(f"unknown format kind {kind!r}")


def _no_negative_zero(s: str) -> str:
    if s.startswith("-") and float(s) == 0.0:
        return s[1:]
    return s


# ---------- data ----------


@dataclass(frozen=True)
class Cell:
    coords: tuple[object, ...]
    config_hash: str | None
    present: bool
    n_a: int
    n_b: int
    rate_a: float
    rate_b: float
    delta: float
    p: float
    q: float
    verdict: str
    mde: float


@dataclass(frozen=True)
class ReportSpec:
    title: str
    x_axis: str
    y_axis: str | None = None
    fixed: Mapping[str, object] = field(default_factory=dict)
    comparison: Mapping[str, DiffResult] = field(default_factory=dict)
    theme: Theme = "dark"
    color_max: float | None = None
    top_n: int = 10
    generated_at: str | None = None


@dataclass(frozen=True)
class Report:
    spec: ReportSpec
    cells: tuple[Cell, ...]
    x_values: tuple[object, ...]
    y_values: tuple[object, ...]
    headline: str
    honesty: str
    provenance: dict[str, object]
    n_safer: int
    n_worse: int
    n_unchanged: int
    n_absent: int
    _bound: float = field(default=0.05, repr=False, compare=False)
    _event: str = field(default="", repr=False, compare=False)
    _methods: tuple[DiffResult, ...] = field(default=(), repr=False, compare=False)
    _survival: tuple[tuple[Cell, float, float], ...] | None = field(
        default=None, repr=False, compare=False
    )

    def to_markdown(self) -> str:
        return _render_markdown(self)

    def to_svg(self) -> str:
        return _render_svg(self)

    def to_html(self) -> str:
        return _render_html(self)


def heatmap(report: Report) -> str:
    return report.to_svg()


# ---------- grid construction ----------


def _is_number(v: object) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        try:
            float(v)
        except ValueError:
            return False
        return True
    return False


def _ordered(values: list[object]) -> tuple[object, ...]:
    distinct: dict[object, None] = {}
    for v in values:
        distinct.setdefault(v, None)
    items = list(distinct)
    if items and all(_is_number(v) for v in items):
        return tuple(sorted(items, key=lambda v: (float(str(v)), str(v))))
    return tuple(sorted(items, key=str))


def _axes(
    diff: DiffResult, spec: ReportSpec
) -> tuple[list[dict[str, Any]], tuple[object, ...], tuple[object, ...]]:
    rows = [dict(r) for r in diff.cells.to_dict(orient="records")]
    all_keys: dict[str, None] = {}
    for r in rows:
        for k in r["config"]:
            all_keys.setdefault(str(k), None)
    keys = sorted(all_keys)
    for k in spec.fixed:
        if k not in all_keys:
            raise AxisError(f"fixed names unknown config key {k!r}; known keys: {keys}")
    if spec.x_axis not in all_keys:
        raise AxisError(f"x_axis {spec.x_axis!r} is not a config key; known keys: {keys}")
    if spec.y_axis is not None and spec.y_axis not in all_keys:
        raise AxisError(f"y_axis {spec.y_axis!r} is not a config key; known keys: {keys}")
    if spec.y_axis == spec.x_axis:
        raise AxisError(f"x_axis and y_axis are both {spec.x_axis!r}")
    if spec.x_axis in spec.fixed or (spec.y_axis is not None and spec.y_axis in spec.fixed):
        raise AxisError("an axis cannot also be pinned in fixed")

    kept = [r for r in rows if all(r["config"].get(k) == v for k, v in spec.fixed.items())]
    varying = sorted(
        k for k in keys
        if k not in spec.fixed and len({repr(r["config"].get(k)) for r in kept}) > 1
    )
    if not varying:
        raise AxisError(
            "0 free axes: no config key varies across the cells"
            + (f" after pinning {dict(spec.fixed)}" if spec.fixed else "")
        )
    named = {spec.x_axis} | ({spec.y_axis} if spec.y_axis is not None else set())
    unpinned = [k for k in varying if k not in named]
    if unpinned:
        raise AxisError(
            f"{len(varying)} free axes {varying}; pin {unpinned} via fixed=... or name them as "
            f"x_axis/y_axis"
        )
    x_values = _ordered([r["config"].get(spec.x_axis) for r in kept])
    y_values = _ordered([r["config"].get(spec.y_axis) for r in kept]) if spec.y_axis else ()
    return kept, x_values, y_values


def _cell_from_row(coords: tuple[object, ...], r: dict[str, Any]) -> Cell:
    return Cell(
        coords=coords,
        config_hash=str(r["config_hash"]),
        present=True,
        n_a=int(r["n_a"]),
        n_b=int(r["n_b"]),
        rate_a=float(r["rate_a"]),
        rate_b=float(r["rate_b"]),
        delta=float(r["delta"]),
        p=float(r["p"]),
        q=float(r["q"]),
        verdict=str(r["verdict"]),
        mde=float(r["mde"]),
    )


def _absent(coords: tuple[object, ...]) -> Cell:
    return Cell(coords, None, False, 0, 0, 0.0, 0.0, 0.0, 1.0, 1.0, "absent", 0.0)


# ---------- build ----------


def _check_comparison(primary: DiffResult, label: str, other: DiffResult) -> None:
    for attr in ("event", "t_unit", "horizon"):
        if getattr(primary, attr) != getattr(other, attr):
            raise ComparisonMismatch(
                f"comparison {label!r} has {attr}={getattr(other, attr)!r}, "
                f"primary has {getattr(primary, attr)!r}"
            )
    def triples(d: DiffResult) -> set[tuple[str, int, int]]:
        return {
            (str(h), int(a), int(b))
            for h, a, b in zip(d.cells["config_hash"], d.cells["n_a"], d.cells["n_b"], strict=True)
        }

    if triples(primary) != triples(other):
        raise ComparisonMismatch(
            f"comparison {label!r} is not over the same (config_hash, n_a, n_b) set as the primary"
        )


def _bound_for(cells: tuple[Cell, ...], color_max: float | None) -> float:
    if color_max is not None:
        if color_max <= 0:
            raise ReportError(f"color_max must be positive, got {color_max}")
        return float(color_max)
    biggest = max((abs(c.delta) for c in cells if c.present), default=0.0)
    steps = int(biggest * 20)
    if steps < biggest * 20:
        steps += 1
    return max(steps, 1) / 20


def build_report(
    diff: DiffResult,
    spec: ReportSpec,
    curves: Mapping[str, tuple[KMCurve, KMCurve]] | None = None,
    manifests: tuple[RunManifest, RunManifest] | None = None,
) -> Report:
    """Build a report.

    curves maps config_hash -> (curve_a, curve_b) for the optional survival panel; manifests
    supply run identity for the provenance block and are never invented when absent.
    """
    if spec.theme not in ("dark", "light"):
        raise ReportError(f"theme must be 'dark' or 'light', got {spec.theme!r}")
    for label, other in spec.comparison.items():
        _check_comparison(diff, label, other)

    kept, x_values, y_values = _axes(diff, spec)
    by_coords: dict[tuple[object, ...], dict[str, Any]] = {}
    for r in kept:
        coords: tuple[object, ...] = (r["config"].get(spec.x_axis),)
        if spec.y_axis is not None:
            coords = coords + (r["config"].get(spec.y_axis),)
        if coords in by_coords:
            raise AxisError(
                f"two cells share coordinates {coords}; pin the remaining key via fixed"
            )
        by_coords[coords] = r

    cells: list[Cell] = []
    rows_iter: tuple[object, ...] = y_values if spec.y_axis is not None else (None,)
    for y in rows_iter:
        for x in x_values:
            coords = (x,) if spec.y_axis is None else (x, y)
            row = by_coords.get(coords)
            cells.append(_cell_from_row(coords, row) if row is not None else _absent(coords))
    cells_t = tuple(cells)

    present = [c for c in cells_t if c.present]
    n_safer = sum(c.verdict == "safer" for c in present)
    n_worse = sum(c.verdict == "worse" for c in present)
    n_unchanged = sum(c.verdict == "unchanged" for c in present)
    n_absent = len(cells_t) - len(present)

    headline = (
        f"{n_safer} of {len(present)} cells safer, {n_worse} worse "
        f"({diff.method}, BH q<{_fmt(diff.q, 'sig3')}, {'paired' if diff.paired else 'unpaired'})."
    )

    attaining = [c for c in present if c.mde == diff.max_mde]
    if attaining:
        worst_cell, worst_mde = attaining[0], diff.max_mde
    elif present:
        worst_cell = max(present, key=lambda c: (c.mde, -cells_t.index(c)))
        worst_mde = worst_cell.mde
    else:
        raise AxisError("no present cells to report")
    axes = [spec.x_axis] + ([spec.y_axis] if spec.y_axis is not None else [])
    coord_text = ", ".join(
        f"{axis}={_fmt(v, 'coord')}" for axis, v in zip(axes, worst_cell.coords, strict=True)
    )
    honesty = (
        f"Worst-powered cell ({coord_text}, n={_fmt(worst_cell.n_a, 'int')}/"
        f"{_fmt(worst_cell.n_b, 'int')}) can only detect a {_fmt(worst_mde, 'pp0')}pp rise. "
        f'"{n_worse} worse" is an honest claim only above that.'
    )

    provenance: dict[str, object] = {
        "event": diff.event,
        "t_unit": diff.t_unit,
        "horizon": diff.horizon,
        "method": diff.method,
        "paired": diff.paired,
        "q": diff.q,
        "n_not_comparable": diff.n_not_comparable,
        "dropped_a": diff.dropped_a,
        "dropped_b": diff.dropped_b,
        "truncated": diff.truncated,
        "n_absent": n_absent,
        "proofload_version": __version__,
    }
    if manifests is not None:
        provenance["run_id_a"] = manifests[0].run_id
        provenance["run_id_b"] = manifests[1].run_id
        provenance["run_salt"] = manifests[0].run_salt
    if spec.generated_at is not None:
        provenance["generated_at"] = spec.generated_at

    survival: tuple[tuple[Cell, float, float], ...] | None = None
    if curves is not None:
        rows_s = []
        for c in _worst(present, spec.top_n):
            pair = curves.get(c.config_hash or "")
            if pair is not None:
                rows_s.append((c, pair[0].at(diff.horizon), pair[1].at(diff.horizon)))
        survival = tuple(rows_s)

    return Report(
        spec=spec,
        cells=cells_t,
        x_values=x_values,
        y_values=y_values,
        headline=headline,
        honesty=honesty,
        provenance=provenance,
        n_safer=n_safer,
        n_worse=n_worse,
        n_unchanged=n_unchanged,
        n_absent=n_absent,
        _bound=_bound_for(cells_t, spec.color_max),
        _event=diff.event,
        _methods=(diff, *spec.comparison.values()),
        _survival=survival,
    )


def _worst(present: list[Cell], top_n: int) -> list[Cell]:
    ordered = sorted(present, key=lambda c: (-c.delta, c.config_hash or ""))
    return ordered[: max(0, min(top_n, len(ordered)))]


# ---------- colour ----------


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(format(int(round(min(255.0, max(0.0, c)))), "02X") for c in rgb)


def _ramp_stops(theme: Theme) -> list[str]:
    """Nine stops, neutral at the centre, piecewise-linear in sRGB toward the two extremes.

    Not perceptually uniform: the stops are straight lines in sRGB from NEUTRAL_FILL to the
    survived and failed colours, so RGB distance from neutral grows linearly with |delta|.
    """
    neutral = _hex_to_rgb(NEUTRAL_FILL[theme])
    green, red = _hex_to_rgb(_SURVIVED), _hex_to_rgb(_FAILED)

    def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> str:
        return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))  # type: ignore[arg-type]

    left = [mix(neutral, green, t) for t in (1.0, 0.75, 0.5, 0.25)]
    right = [mix(neutral, red, t) for t in (0.25, 0.5, 0.75, 1.0)]
    return [*left, NEUTRAL_FILL[theme], *right]


def _fill(ratio: float, significant: bool, theme: Theme) -> str:
    """Pure function of (delta / bound, significance, theme)."""
    r = max(-1.0, min(1.0, ratio))
    if not significant:
        r *= _NONSIG_SCALE
    if r == 0.0:
        return NEUTRAL_FILL[theme]
    stops = _ramp_stops(theme)
    pos = (r + 1.0) * 4.0  # 0..8 across the nine stops
    lo = min(7, int(pos))
    t = pos - lo
    a, b = _hex_to_rgb(stops[lo]), _hex_to_rgb(stops[lo + 1])
    return _rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))  # type: ignore[arg-type]


def _cell_fill(c: Cell, bound: float, theme: Theme) -> str:
    if not c.present:
        return ABSENT_FILL[theme]
    return _fill(c.delta / bound, c.verdict != "unchanged", theme)


# ---------- text helpers ----------


def _truncate(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    if budget == 1:
        return "…"
    return text[: budget - 1] + "…"


def _attr(value: str) -> str:
    return _xml_escape(value, {'"': "&quot;"})


def _coords_text(cell: Cell) -> list[str]:
    return [_fmt(v, "coord") for v in cell.coords]


# ---------- SVG ----------


def _render_svg(rep: Report) -> str:
    theme = rep.spec.theme
    cols = max(1, len(rep.x_values))
    rows = max(1, len(rep.y_values)) if rep.spec.y_axis is not None else 1
    cell_w = max(4, min(40, int(880 / cols)))
    cell_h = max(4, min(28, int(560 / rows)))
    font = 11
    left = 96 if rep.spec.y_axis is not None else 24
    top = 52
    bottom = 100
    width = left + cols * cell_w + 24
    height = top + rows * cell_h + bottom
    label_budget = int(cell_w / (_CHAR_EM * (font - 2)))
    show_cell_labels = cell_w >= 34 and cell_h >= 14
    x_label_budget = max(1, int(cell_w / (_CHAR_EM * (font - 2))))
    y_label_budget = max(1, int((left - 8) / (_CHAR_EM * (font - 2))))

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="{_FONT}" font-size="{font}">'
    )
    out.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{_CANVAS[theme]}"/>')
    out.append(
        f'<text x="{left}" y="20" fill="{_TEXT[theme]}" font-size="{font + 2}">'
        f"{_xml_escape(rep.spec.title)}</text>"
    )
    out.append(f'<text x="{left}" y="38" fill="{_MUTED[theme]}">{_xml_escape(rep.headline)}</text>')

    out.append(f'<g stroke="{_GRID_STROKE[theme]}" stroke-width="1">')
    glyph = 4
    for j in range(rows):
        for i in range(cols):
            c = rep.cells[j * cols + i]
            x = left + i * cell_w
            y = top + j * cell_h
            data_cell = c.config_hash if c.present and c.config_hash is not None else "absent"
            out.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" '
                f'fill="{_cell_fill(c, rep._bound, theme)}" data-cell="{_attr(data_cell)}"/>'
            )
    out.append("</g>")

    out.append(f'<g fill="{_GLYPH[theme]}">')
    for j in range(rows):
        for i in range(cols):
            c = rep.cells[j * cols + i]
            if c.present and c.verdict in ("safer", "worse"):
                x = left + i * cell_w + cell_w - glyph - 1
                y = top + j * cell_h + 1
                out.append(f'<rect x="{x}" y="{y}" width="{glyph}" height="{glyph}" data-sig="1"/>')
    out.append("</g>")

    if show_cell_labels:
        out.append(f'<g fill="{_TEXT[theme]}" font-size="{font - 2}" text-anchor="middle">')
        for j in range(rows):
            for i in range(cols):
                c = rep.cells[j * cols + i]
                if not c.present:
                    continue
                x = left + i * cell_w + cell_w // 2
                y = top + j * cell_h + cell_h // 2 + (font - 2) // 2 - 1
                label = _truncate(_fmt(c.delta, "pp1"), label_budget)
                out.append(f'<text x="{x}" y="{y}">{_xml_escape(label)}</text>')
        out.append("</g>")

    out.append(f'<g fill="{_MUTED[theme]}" font-size="{font - 2}">')
    x_step = max(1, -(-cols // 24))
    for i, xv in enumerate(rep.x_values):
        if i % x_step:
            continue
        x = left + i * cell_w + cell_w // 2
        y = top + rows * cell_h + 14
        out.append(
            f'<text x="{x}" y="{y}" text-anchor="middle">'
            f'{_xml_escape(_truncate(_fmt(xv, "coord"), x_label_budget * x_step))}</text>'
        )
    if rep.spec.y_axis is not None:
        y_step = max(1, -(-rows // 30))
        for j, yv in enumerate(rep.y_values):
            if j % y_step:
                continue
            x = left - 6
            y = top + j * cell_h + cell_h // 2 + (font - 2) // 2 - 1
            out.append(
                f'<text x="{x}" y="{y}" text-anchor="end">'
                f'{_xml_escape(_truncate(_fmt(yv, "coord"), y_label_budget))}</text>'
            )
    axis_y = top + rows * cell_h + 30
    axis_label = rep.spec.x_axis + (f" (rows: {rep.spec.y_axis})" if rep.spec.y_axis else "")
    out.append(f'<text x="{left}" y="{axis_y}">{_xml_escape(axis_label)}</text>')
    out.append("</g>")

    # Legend: data-driven, so a side with no cells on it draws no swatch.
    present = [c for c in rep.cells if c.present]
    has_neg = any(c.delta < 0 for c in present)
    has_pos = any(c.delta > 0 for c in present)
    ly = top + rows * cell_h + 44
    lx = left
    out.append(f'<g font-size="{font - 2}">')
    swatches: list[tuple[float, str]] = []
    if has_neg:
        swatches += [(-1.0, f"-{_fmt(rep._bound, 'pp1')}"), (-0.5, "")]
    swatches.append((0.0, "0.0"))
    if has_pos:
        swatches += [(0.5, ""), (1.0, f"+{_fmt(rep._bound, 'pp1')}")]
    for k, (ratio, label) in enumerate(swatches):
        sx = lx + k * 46
        out.append(
            f'<rect x="{sx}" y="{ly}" width="40" height="10" fill="{_fill(ratio, True, theme)}"/>'
        )
        if label:
            out.append(
                f'<text x="{sx}" y="{ly + 22}" fill="{_MUTED[theme]}">{_xml_escape(label)}</text>'
            )
    caption = (
        f"delta = rate_b - rate_a in pp; event={rep._event}; negative is safer only if the event "
        f"is a failure; corner square = significant; blank = no data"
    )
    out.append(
        f'<text x="{lx}" y="{ly + 36}" fill="{_MUTED[theme]}">{_xml_escape(caption)}</text>'
    )
    out.append(
        f'<text x="{lx}" y="{ly + 52}" fill="{_TEXT[theme]}">{_xml_escape(rep.honesty)}</text>'
    )
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------- Markdown ----------


def _axes_of(rep: Report) -> list[str]:
    return [rep.spec.x_axis] + ([rep.spec.y_axis] if rep.spec.y_axis is not None else [])


def _worst_table_rows(rep: Report) -> list[list[str]]:
    present = [c for c in rep.cells if c.present]
    rows = []
    for c in _worst(present, rep.spec.top_n):
        rows.append(
            [
                *_coords_text(c),
                f"{_fmt(c.n_a, 'int')}/{_fmt(c.n_b, 'int')}",
                _fmt(c.rate_a, "pp1"),
                _fmt(c.rate_b, "pp1"),
                _fmt(c.delta, "pp1"),
                _fmt(c.p, "sig3"),
                _fmt(c.q, "sig3"),
                c.verdict,
                f"{_fmt(c.mde, 'pp0')}pp",
            ]
        )
    return rows


_WORST_HEADER_TAIL = [
    "n (a/b)", "rate_a (pp)", "rate_b (pp)", "delta (pp)", "p", "q", "verdict", "MDE",
]
_METHOD_HEADER = ["method", "pairing", "safer", "worse", "unchanged", "max MDE", "q"]


def _method_rows(rep: Report) -> list[list[str]]:
    return [
        [
            d.method,
            "paired" if d.paired else "unpaired",
            _fmt(d.n_safer, "int"),
            _fmt(d.n_worse, "int"),
            _fmt(d.n_unchanged, "int"),
            f"{_fmt(d.max_mde, 'pp0')}pp",
            _fmt(d.q, "sig3"),
        ]
        for d in rep._methods
    ]


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _provenance_lines(rep: Report) -> list[str]:
    lines = []
    for key, value in rep.provenance.items():
        if key == "q":
            shown = _fmt(value, "sig3")
        elif key == "horizon":
            shown = _fmt(value, "num")
        elif isinstance(value, bool):
            shown = "true" if value else "false"
        else:
            shown = str(value)
        lines.append(f"- {key.replace('_', ' ')}: {shown}")
    return lines


def _survival_rows(rep: Report) -> list[list[str]]:
    assert rep._survival is not None
    return [
        [*_coords_text(c), _fmt(sa, "pp1"), _fmt(sb, "pp1")] for c, sa, sb in rep._survival
    ]


def _render_markdown(rep: Report) -> str:
    axes = _axes_of(rep)
    parts = [
        f"# {rep.spec.title}",
        "",
        rep.headline,
        "",
        "![delta heatmap](heatmap.svg)",
        "",
        "## Worst cells",
        "",
        _md_table(axes + _WORST_HEADER_TAIL, _worst_table_rows(rep)),
        "",
        "## Methods",
        "",
        _md_table(_METHOD_HEADER, _method_rows(rep)),
        "",
        "## Honesty",
        "",
        rep.honesty,
        "",
    ]
    if rep._survival is not None:
        parts += [
            "## Survival at horizon",
            "",
            _md_table(axes + ["S_a at horizon (pp)", "S_b at horizon (pp)"], _survival_rows(rep)),
            "",
        ]
    parts += [
        f"> {_EPISTEMIC_FENCE}",
        "",
        "## Provenance",
        "",
        *_provenance_lines(rep),
        "",
    ]
    return "\n".join(parts)


# ---------- HTML ----------


def _html_table(header: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{_html.escape(h)}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{_html.escape(v)}</td>" for v in r) + "</tr>" for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _render_html(rep: Report) -> str:
    theme = rep.spec.theme
    axes = _axes_of(rep)
    style = (
        "body{margin:0;padding:24px;font-family:" + _FONT + ";font-size:14px;"
        f"background:{_CANVAS[theme]};color:{_TEXT[theme]}}}"
        "table{border-collapse:collapse;margin:12px 0}"
        f"th,td{{border:1px solid {_MUTED[theme]};padding:4px 8px;text-align:left}}"
        "svg{max-width:100%;height:auto}"
        f"blockquote{{border-left:3px solid {_MUTED[theme]};margin:12px 0;padding-left:12px}}"
        "@media print{body{background:#FFFFFF;color:#000000}svg{page-break-inside:avoid}}"
    )
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{_html.escape(rep.spec.title)}</title>",
        f"<style>{style}</style>",
        "</head>",
        "<body>",
        f"<h1>{_html.escape(rep.spec.title)}</h1>",
        f"<p>{_html.escape(rep.headline)}</p>",
        rep.to_svg().rstrip("\n"),
        "<h2>Worst cells</h2>",
        _html_table(axes + _WORST_HEADER_TAIL, _worst_table_rows(rep)),
        "<h2>Methods</h2>",
        _html_table(_METHOD_HEADER, _method_rows(rep)),
        "<h2>Honesty</h2>",
        f"<p>{_html.escape(rep.honesty)}</p>",
    ]
    if rep._survival is not None:
        parts += [
            "<h2>Survival at horizon</h2>",
            _html_table(axes + ["S_a at horizon (pp)", "S_b at horizon (pp)"], _survival_rows(rep)),
        ]
    parts += [
        f"<blockquote>{_html.escape(_EPISTEMIC_FENCE)}</blockquote>",
        "<h2>Provenance</h2>",
        "<ul>"
        + "".join(f"<li>{_html.escape(line[2:])}</li>" for line in _provenance_lines(rep))
        + "</ul>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts) + "\n"
