"""M7: render diff results as Markdown, standalone SVG, and a single-file HTML receipt.

Three public entry points share one private panel builder: ``build_report`` (one
``DiffResult``), ``build_multi_report`` (a ``MultiDiffResult``: one panel per event on a
shared colour bound, headline and trade line first, and -- handed M14's ``TreeResult`` -- the
layered report's four sections before the figure), and ``build_survival_report`` (one run,
one rate panel per event from an M5 cell table). M7 computes no statistics. Every number it
prints is a field on the diff result, on the tree, on the cell table, on the curve it is
handed, or on the ``RunManifest``, or is a span count the caller read from a run's stored
envelopes and handed in. One private formatting helper does every float-to-string
conversion; that helper is the whole defence for byte determinism and for the no ``-0.0`` rule.

Sign convention: ``delta = rate_b - rate_a``; negative is *safer* only when ``event`` names
a failure. The event is printed in the provenance and the legend so a reader can check.
"""

from __future__ import annotations

import html as _html
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Literal
from xml.sax.saxutils import escape as _xml_escape

import pandas as pd

from poisson_prove import __version__, _look
from poisson_prove._compat import old_writer_line, version_as_recorded
from poisson_prove.diff import _CENSORED, _PAIRED_METHODS, DiffResult, EventDiff, MultiDiffResult
from poisson_prove.store import RunManifest
from poisson_prove.survival import CIFCurve, KMCurve

if TYPE_CHECKING:
    from poisson_prove.steps import DeclarationCheck
    from poisson_prove.tree import Bound, Leaves, RootResult, TreeResult

Theme = Literal["dark", "light"]

NEUTRAL_FILL: dict[Theme, str] = {"dark": "#1F1F22", "light": "#EDEDEA"}
ABSENT_FILL: dict[Theme, str] = {"dark": "#141416", "light": "#F7F7F4"}
SATURATED_FILL: dict[Theme, str] = {"dark": "#2A2A2E", "light": "#E3E3DF"}

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
_HONESTY_NONE = "No unchanged cells; every cell moved significantly."
_SATURATION_LEGEND = "both 0% / both 100%"
_SMALL_N = 16  # the survival coverage line counts cells below this
_TRADE_STYLE = f".trade{{fill:{_FAILED}}}"

# The two causes only a grid can have, beside M6's five: a coordinate in the axis product no
# row exists for, and one that more than one non-comparable coverage row maps to. Written
# once here; M6 writes the other five.
_GRID_CAUSES = ("unsampled", "multiple")
_UNSAMPLED, _MULTIPLE = _GRID_CAUSES

Mode = Literal["diff", "rate"]


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
    if _look.active():
        if kind in ("int", "seed"):
            return _look.fmt_count(value) if kind == "int" else str(int(value))
        if kind in ("pp1", "pp0"):
            return _look.fmt_rate(value)
        if kind == "sig3":
            return _look.fmt_p(value)
    if kind in ("int", "seed"):
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


def _pp() -> str:
    """The unit after a rate the library prints in points; nothing under the look, where the
    number is a fraction."""
    return "" if _look.active() else "pp"


def _h(label: str) -> str:
    """A table header for a column in points: ``label (pp)``, or the bare label under the look."""
    return label if _look.active() else f"{label} (pp)"


def _in_pp() -> str:
    return "as fractions" if _look.active() else "in pp"


def _unit() -> str:
    return "fraction" if _look.active() else "pp"


def _detail(text: str) -> str:
    """A refusal's detail, written by the tree in the library's forms, respelled under the look."""
    return _look.reprint(text) if _look.active() else text


def _plain(make: Callable[[], str]) -> str:
    """``make()`` rendered in the library's forms whatever the caller is inside."""
    with _look.library():
        return make()


def _wrap_like(now: str, base: str, budget: int) -> list[str]:
    """``now`` wrapped exactly where ``base`` wraps: the same words line for line, so a text
    respelled under the look keeps the geometry the library's rendering has. Falls back to
    wrapping ``now`` on its own when the two do not share their words."""
    base_lines = _wrap(base, budget)
    if now == base:
        return base_lines
    base_words, now_words = base.split(" "), now.split(" ")
    if len(base_words) != len(now_words) or any(len(w) > budget for w in base_words):
        return _wrap(now, budget)
    lines: list[str] = []
    k = 0
    for line in base_lines:
        n = len(line.split(" "))
        lines.append(" ".join(now_words[k : k + n]))
        k += n
    return lines


def _no_negative_zero(s: str) -> str:
    if s.startswith("-") and float(s) == 0.0:
        return s[1:]
    return s


# ---------- colour ----------


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(format(int(round(min(255.0, max(0.0, c)))), "02X") for c in rgb)


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _hex_to_rgb(a), _hex_to_rgb(b)
    return _rgb_to_hex(
        (ra[0] + (rb[0] - ra[0]) * t, ra[1] + (rb[1] - ra[1]) * t, ra[2] + (rb[2] - ra[2]) * t)
    )


def _ramp_stops(theme: Theme) -> list[str]:
    """Nine stops, neutral at the centre, piecewise-linear in sRGB toward the two extremes.

    Not perceptually uniform: the stops are straight lines in sRGB from NEUTRAL_FILL to the
    survived and failed colours, so RGB distance from neutral grows linearly with |delta|.
    """
    neutral = NEUTRAL_FILL[theme]
    left = [_mix(neutral, _SURVIVED, t) for t in (1.0, 0.75, 0.5, 0.25)]
    right = [_mix(neutral, _FAILED, t) for t in (0.25, 0.5, 0.75, 1.0)]
    return [*left, neutral, *right]


def _sequential_stops(theme: Theme) -> tuple[str, ...]:
    """Nine stops from NEUTRAL_FILL (rate 0) to the failed colour (rate 1), linear in sRGB."""
    return tuple(_mix(NEUTRAL_FILL[theme], _FAILED, i / 8) for i in range(9))


SEQUENTIAL_RAMP: dict[Theme, tuple[str, ...]] = {
    "dark": _sequential_stops("dark"),
    "light": _sequential_stops("light"),
}


def _along(stops: Sequence[str], pos: float) -> str:
    """Piecewise-linear colour at ``pos`` in [0, len(stops) - 1]."""
    lo = min(len(stops) - 2, int(pos))
    return _mix(stops[lo], stops[lo + 1], pos - lo)


def _fill(ratio: float, significant: bool, theme: Theme) -> str:
    """Pure function of (delta / bound, significance, theme)."""
    r = max(-1.0, min(1.0, ratio))
    if not significant:
        r *= _NONSIG_SCALE
    if r == 0.0:
        return NEUTRAL_FILL[theme]
    return _along(_ramp_stops(theme), (r + 1.0) * 4.0)


def _rate_fill(rate: float, theme: Theme) -> str:
    r = max(0.0, min(1.0, rate))
    return _along(SEQUENTIAL_RAMP[theme], r * 8.0)


def _is_saturated(c: Cell) -> bool:
    """Saturation is detected on the rates, not on delta: both arms at 0% or both at 100%."""
    return c.present and c.rate_a == c.rate_b and c.rate_a in (0.0, 1.0)


def _cell_fill(c: Cell, bound: float, theme: Theme, mode: Mode) -> str:
    if not c.present:
        return ABSENT_FILL[theme]
    if mode == "rate":
        return _rate_fill(c.rate_a, theme)
    if _is_saturated(c):
        return SATURATED_FILL[theme]
    return _fill(c.delta / bound, c.verdict != "unchanged", theme)


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
    hole_cause: str | None = None
    #: S24's interval on this cell's delta, joined by ``(event, config_hash)`` in
    #: ``build_multi_report``. Appended and defaulted because ``_absent`` builds a ``Cell``
    #: positionally; ``None`` on a censored row and on every single-event report.
    ci_lo: float | None = None
    ci_hi: float | None = None
    ci_basis: str | None = None


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
    forest: Literal["auto", "always", "never"] = "auto"


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
    n_present: int
    _bound: float = field(default=0.05, repr=False, compare=False)
    #: ``honesty`` in the library's forms, whatever forms the report was built under; the
    #: figure wraps its lines where the library's would.
    _honesty_plain: str = field(default="", repr=False, compare=False)
    _event: str = field(default="", repr=False, compare=False)
    _methods: tuple[DiffResult, ...] = field(default=(), repr=False, compare=False)
    _survival: tuple[tuple[Cell, float, float], ...] | None = field(
        default=None, repr=False, compare=False
    )
    _trades: frozenset[str] = field(default=frozenset(), repr=False, compare=False)
    _tiebreak: bool = field(default=False, repr=False, compare=False)
    _mode: Mode = field(default="diff", repr=False, compare=False)
    _forest: bool = field(default=False, repr=False, compare=False)
    _horizon: float = field(default=0.0, repr=False, compare=False)
    _intervals: bool = field(default=False, repr=False, compare=False)

    def to_markdown(self) -> str:
        return _render_markdown(self)

    def to_svg(self) -> str:
        return _render_svg(self)

    def to_html(self) -> str:
        return _render_html(self)


@dataclass(frozen=True)
class MultiReport:
    spec: ReportSpec
    events: tuple[str, ...]
    panels: Mapping[str, Report]
    headline: str
    trade_line: str | None
    inference_line: str | None
    bound: float
    provenance: dict[str, object]
    _method_rows: tuple[tuple[str, ...], ...] = field(default=(), repr=False, compare=False)
    tree: TreeResult | None = None
    #: The flat family's interval facts, one formatter (``_interval_lines``) for every surface:
    #: ``report.md``, the receipt, the page's honesty band, the payload and ``diff`` stdout.
    interval_lines: tuple[str, ...] = ()
    #: M6's answer to whether the two events are exact complements, carried so the page and the
    #: payload can say so as data; ``trade_line`` already says it as words.
    complement: tuple[str, ...] | None = None

    def to_markdown(self) -> str:
        return _render_multi_markdown(self)

    def to_svg(self) -> str:
        return _render_stacked_svg(self.spec, self.events, self.panels, _multi_header(self))

    def to_html(self) -> str:
        return _render_multi_html(self)


@dataclass(frozen=True)
class SurvivalReport:
    spec: ReportSpec
    events: tuple[str, ...]
    panels: Mapping[str, Report]
    provenance: dict[str, object]

    def to_markdown(self) -> str:
        return _render_survival_markdown(self)

    def to_svg(self) -> str:
        return _render_stacked_svg(self.spec, self.events, self.panels, [])

    def to_html(self) -> str:
        return _render_survival_html(self)


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


def _rows_of(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [dict(r) for r in frame.to_dict(orient="records")]


def _axes(
    rows: list[dict[str, Any]], spec: ReportSpec
) -> tuple[list[dict[str, Any]], tuple[object, ...], tuple[object, ...]]:
    all_keys: dict[str, None] = {}
    for r in rows:
        for k in r["config"]:
            all_keys.setdefault(str(k), None)
    keys = sorted(all_keys)
    for k in spec.fixed:
        if k not in all_keys:
            raise AxisError(f"--fix names unknown config key {k!r}; known keys: {keys}")
    if spec.x_axis not in all_keys:
        raise AxisError(f"--x {spec.x_axis!r} is not a config key; known keys: {keys}")
    if spec.y_axis is not None and spec.y_axis not in all_keys:
        raise AxisError(f"--y {spec.y_axis!r} is not a config key; known keys: {keys}")
    if spec.y_axis == spec.x_axis:
        raise AxisError(f"--x and --y are both {spec.x_axis!r}")
    if spec.x_axis in spec.fixed or (spec.y_axis is not None and spec.y_axis in spec.fixed):
        raise AxisError("an axis cannot also be pinned with --fix")

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
            f"{len(varying)} free axes {varying}; pin {unpinned} with --fix KEY=VALUE or name "
            f"them with --x/--y"
        )
    x_values = _ordered([r["config"].get(spec.x_axis) for r in kept])
    y_values = _ordered([r["config"].get(spec.y_axis) for r in kept]) if spec.y_axis else ()
    return kept, x_values, y_values


def _diff_cell(coords: tuple[object, ...], r: dict[str, Any]) -> Cell:
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


_Holes = Mapping[tuple[object, ...], tuple[str | None, str]]


def _absent(coords: tuple[object, ...], holes: _Holes | None = None) -> Cell:
    """A grid coordinate with no comparable cell.

    ``holes`` maps coordinates to the coverage row that explains them. Without it -- a
    single-event report, or a ``MultiDiffResult`` whose ``coverage`` is ``None`` -- the cause
    is *not recorded*, which is ``None`` and never ``"unsampled"``.
    """
    if holes is None:
        return Cell(coords, None, False, 0, 0, 0.0, 0.0, 0.0, 1.0, 1.0, "absent", 0.0)
    config_hash, cause = holes.get(coords, (None, _UNSAMPLED))
    return Cell(coords, config_hash, False, 0, 0, 0.0, 0.0, 0.0, 1.0, 1.0, "absent", 0.0, cause)


def _hole_map(
    multi: MultiDiffResult, spec: ReportSpec
) -> dict[tuple[object, ...], tuple[str | None, str]] | None:
    """Coordinates -> (config_hash, cause) for the non-comparable coverage rows this slice keeps.

    ``spec.fixed`` is applied exactly as ``_axes`` applies it, or a ``--fix`` would attach the
    wrong cell's cause to a hole. Two rows on one coordinate are ``"multiple"`` with no hash,
    never the ``AxisError`` ``_grid`` raises for two *present* cells: a report that rendered
    yesterday must still render.
    """
    if multi.coverage is None:
        return None
    by_coords: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for row in multi.coverage.to_dict(orient="records"):
        if row["comparable"]:
            continue
        config = row["config"]
        if not all(config.get(k) == v for k, v in spec.fixed.items()):
            continue
        coords: tuple[object, ...] = (config.get(spec.x_axis),)
        if spec.y_axis is not None:
            coords = coords + (config.get(spec.y_axis),)
        by_coords.setdefault(coords, []).append(row)
    return {
        coords: (
            (str(rows[0]["config_hash"]), str(rows[0]["cause"]))
            if len(rows) == 1
            else (None, _MULTIPLE)
        )
        for coords, rows in by_coords.items()
    }


def _grid(
    rows: list[dict[str, Any]],
    spec: ReportSpec,
    to_cell: Callable[[tuple[object, ...], dict[str, Any]], Cell],
    holes: _Holes | None = None,
) -> tuple[tuple[Cell, ...], tuple[object, ...], tuple[object, ...]]:
    kept, x_values, y_values = _axes(rows, spec)
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
            cells.append(to_cell(coords, row) if row is not None else _absent(coords, holes))
    return tuple(cells), x_values, y_values


# ---------- the panel builder ----------


def _validate_spec(spec: ReportSpec) -> None:
    if spec.theme not in ("dark", "light"):
        raise ReportError(f"theme must be 'dark' or 'light', got {spec.theme!r}")
    if spec.forest not in ("auto", "always", "never"):
        raise ReportError(f"forest must be 'auto', 'always' or 'never', got {spec.forest!r}")


def _bound_for(cells: Sequence[Cell], color_max: float | None) -> float:
    if color_max is not None:
        if color_max <= 0:
            raise ReportError(f"color_max must be positive, got {color_max}")
        return float(color_max)
    biggest = max((abs(c.delta) for c in cells if c.present), default=0.0)
    steps = int(biggest * 20)
    if steps < biggest * 20:
        steps += 1
    return max(steps, 1) / 20


def _axes_of(spec: ReportSpec) -> list[str]:
    return [spec.x_axis] + ([spec.y_axis] if spec.y_axis is not None else [])


def _coord_text(spec: ReportSpec, cell: Cell) -> str:
    return ", ".join(
        f"{axis}={_fmt(v, 'coord')}" for axis, v in zip(_axes_of(spec), cell.coords, strict=True)
    )


def _honesty(
    present: Sequence[Cell],
    spec: ReportSpec,
    *,
    n_worse: int,
    max_mde: float,
    max_mde_unchanged: float,
    max_mde_unchanged_cell: str | None,
) -> str:
    """Two lines: the worst-powered *unchanged* cell (what "0 worse" rests on), then the
    worst-powered cell overall. Both values are M6 fields; M7 only names a cell attaining them."""
    unchanged = [c for c in present if c.verdict == "unchanged"]
    if math.isnan(max_mde_unchanged) or not unchanged:
        first = _HONESTY_NONE
    else:
        named = [c for c in unchanged if c.config_hash == max_mde_unchanged_cell]
        if not named:
            named = [c for c in unchanged if c.mde == max_mde_unchanged]
        if not named:
            named = [max(unchanged, key=lambda c: c.mde)]
        cell = named[0]
        first = (
            f"Worst-powered unchanged cell ({_coord_text(spec, cell)}, n={_fmt(cell.n_a, 'int')}/"
            f"{_fmt(cell.n_b, 'int')}) can only detect a "
            f"{_fmt(max_mde_unchanged, 'pp0')}{_pp()} rise. "
            f'"{n_worse} worse" is an honest claim only above that.'
        )
    attaining = [c for c in present if c.mde == max_mde]
    overall = attaining[0] if attaining else max(present, key=lambda c: c.mde)
    second = (
        f"Worst-powered cell overall: {_fmt(max_mde, 'pp0')}{_pp()} "
        f"({_coord_text(spec, overall)})."
    )
    return first + "\n" + second


def _coverage(present: Sequence[Cell]) -> str:
    ns = [c.n_a for c in present]
    small = sum(n < _SMALL_N for n in ns)
    return (
        f"n={_fmt(min(ns), 'int')}..{_fmt(max(ns), 'int')} per cell, "
        f"{_fmt(small, 'int')} cells with n < {_SMALL_N}"
    )


def _build_panel(
    rows: list[dict[str, Any]],
    spec: ReportSpec,
    *,
    mode: Mode,
    event: str,
    bound: float | None,
    headline_of: Callable[[Sequence[Cell], int, int, int], str],
    honesty_of: Callable[[Sequence[Cell], int], str],
    provenance: dict[str, object],
    methods: tuple[DiffResult, ...] = (),
    trades: frozenset[str] = frozenset(),
    tiebreak: bool = False,
    horizon: float = 0.0,
    curves: Mapping[str, tuple[KMCurve, KMCurve]] | None = None,
    grid: tuple[tuple[Cell, ...], tuple[object, ...], tuple[object, ...]] | None = None,
    intervals: bool = False,
) -> Report:
    """The one grid -> Report path. ``bound`` is injected (shared across a multi report) or
    derived from this panel's own cells; ``mode`` picks the diverging or the sequential ramp."""
    if grid is None:
        grid = _grid(rows, spec, _diff_cell if mode == "diff" else _rate_cell)
    cells_t, x_values, y_values = grid
    present = [c for c in cells_t if c.present]
    if not present:
        raise AxisError("no present cells to report")
    n_safer = sum(c.verdict == "safer" for c in present)
    n_worse = sum(c.verdict == "worse" for c in present)
    n_unchanged = sum(c.verdict == "unchanged" for c in present)
    n_absent = len(cells_t) - len(present)
    forest = (
        mode == "diff"
        and spec.y_axis is None
        and (
            spec.forest == "always"
            or (spec.forest == "auto" and not all(_is_number(v) for v in x_values))
        )
    )
    survival: tuple[tuple[Cell, float, float], ...] | None = None
    if curves is not None:
        rows_s = []
        for c in _worst(present, spec.top_n, mode=mode, tiebreak=tiebreak):
            pair = curves.get(c.config_hash or "")
            if pair is not None:
                rows_s.append((c, pair[0].at(horizon), pair[1].at(horizon)))
        survival = tuple(rows_s)
    return Report(
        spec=spec,
        cells=cells_t,
        x_values=x_values,
        y_values=y_values,
        headline=headline_of(present, n_safer, n_worse, n_unchanged),
        honesty=honesty_of(present, n_worse),
        _honesty_plain=_plain(lambda: honesty_of(present, n_worse)),
        provenance=provenance,
        n_safer=n_safer,
        n_worse=n_worse,
        n_unchanged=n_unchanged,
        n_absent=n_absent,
        n_present=len(present),
        _bound=bound if bound is not None else _bound_for(cells_t, spec.color_max),
        _event=event,
        _methods=methods,
        _survival=survival,
        _trades=trades,
        _tiebreak=tiebreak,
        _mode=mode,
        _forest=forest,
        _horizon=horizon,
        _intervals=intervals,
    )


#: Section 3.4's other branch, when nothing was rejected. The MDE lines are already above it.
#: **Moved here from ``cli.py`` by P-1**, text unchanged but for the trailing newline, which the
#: caller adds: every surface now reads one formatter and none of them rewords it.
_NO_INTERVAL_LINE = (
    "intervals: none (nothing significant; the MDE lines above are the honest bound)"
)

_INTERVAL_COLUMN = "interval (pp)"


def _interval_column() -> str:
    return _h("interval")


def _interval_lines(multi: MultiDiffResult) -> tuple[str, ...]:
    """S24's three interval facts, or the one ``R == 0`` line, unindented and unstyled.

    **One formatter.** ``diff`` stdout, ``report.md``, ``receipt.html``, the page's honesty band
    and the payload all print these strings; ``cli._interval_block`` indents the second and third
    by two spaces, which is layout. A second spelling anywhere would be a second derivation of a
    printed number.

    **The arithmetic is shown and none of it is done here.** ``q``, ``n_rejected``, ``n_tests``,
    ``alpha_star``, ``interval_level`` and both counts are fields; this reads and formats them.
    That includes the percentage: ``interval_level * 100`` would be a second derivation,
    indistinguishable to any robust rule from recovering ``alpha*`` as ``1 - interval_level``.
    The ``%`` spec renders it with no arithmetic, and ``:g`` on ``alpha*`` keeps a level like
    4.2e-05 -- 1200 cells and one rejection -- from printing as ``0.0000``.
    """
    if multi.intervals is None or multi.interval_level is None or multi.alpha_star is None:
        return (_NO_INTERVAL_LINE,)
    constructed = [b for b in multi.intervals["basis"] if b != _CENSORED]
    basis = constructed[0] if constructed else _CENSORED
    if _look.active():
        return (
            f"intervals: {multi.interval_level:.1%} (alpha* = {_look.fmt_p(multi.alpha_star)} = "
            f"q x {_look.fmt_count(multi.n_rejected)} / {_look.fmt_count(multi.n_tests)} over "
            f"the flat BH family), basis {basis}",
            f"interval excludes zero, verdict unchanged: "
            f"{_look.fmt_count(multi.n_interval_only)} cells",
            f"verdict significant, interval covers zero: "
            f"{_look.fmt_count(multi.n_verdict_only)} cells",
        )
    return (
        f"intervals: {multi.interval_level:.4%} (alpha* = {multi.alpha_star:g} = "
        f"q x {multi.n_rejected} / {multi.n_tests} over the flat BH family), basis {basis}",
        f"interval excludes zero, verdict unchanged: {multi.n_interval_only} cells",
        f"verdict significant, interval covers zero: {multi.n_verdict_only} cells",
    )


def _interval_text(cell: Cell) -> str:
    """One worst-cells row's interval, in points. A row whose endpoints are ``None`` -- ADR-050's
    censored basis, or a cell with no interval row -- prints ``censored`` rather than a bracket
    around nothing."""
    lo, hi = cell.ci_lo, cell.ci_hi
    if lo is None or hi is None or lo != lo or hi != hi:
        return _CENSORED
    return f"[{_fmt(lo, 'pp1')}, {_fmt(hi, 'pp1')}]"


def _interval_index(multi: MultiDiffResult, event: str) -> dict[str, tuple[Any, Any, str]]:
    """This event's interval rows by ``config_hash``.

    Keyed per event and never across events: two events' intervals on the same cell are different
    numbers, and a join on ``config_hash`` alone would print one event's interval on the other's
    row.
    """
    if multi.intervals is None:
        return {}
    frame = multi.intervals
    return {
        str(record["config_hash"]): (record["ci_lo"], record["ci_hi"], str(record["basis"]))
        for record in frame.loc[frame["event"] == event].to_dict(orient="records")
    }


def _interval_cell(
    index: Mapping[str, tuple[Any, Any, str]],
) -> Callable[[tuple[object, ...], dict[str, Any]], Cell]:
    """``_diff_cell`` with this event's interval attached, for ``_grid``."""

    def make(coords: tuple[object, ...], r: dict[str, Any]) -> Cell:
        cell = _diff_cell(coords, r)
        found = index.get(str(r["config_hash"]))
        if found is None:
            return cell
        return replace(cell, ci_lo=found[0], ci_hi=found[1], ci_basis=found[2])

    return make


def _worst(
    present: Sequence[Cell], top_n: int, *, mode: Mode = "diff", tiebreak: bool = False
) -> list[Cell]:
    if mode == "rate":
        ordered = sorted(present, key=lambda c: (-c.rate_a, c.config_hash or ""))
    elif tiebreak:
        ordered = sorted(present, key=lambda c: (-c.delta, c.q, c.mde, c.config_hash or ""))
    else:
        ordered = sorted(present, key=lambda c: (-c.delta, c.config_hash or ""))
    return ordered[: max(0, min(top_n, len(ordered)))]


# ---------- build: single event ----------


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


def _single_headline(diff: DiffResult) -> Callable[[Sequence[Cell], int, int, int], str]:
    def headline(present: Sequence[Cell], n_safer: int, n_worse: int, n_unchanged: int) -> str:
        return (
            f"{n_safer} of {len(present)} cells safer, {n_worse} worse "
            f"({diff.method}, BH q<{_fmt(diff.q, 'sig3')}, "
            f"{'paired' if diff.method in _PAIRED_METHODS else 'unpaired'})."
        )

    return headline


def _diff_honesty(
    spec: ReportSpec,
    *,
    max_mde: float,
    max_mde_unchanged: float,
    max_mde_unchanged_cell: str | None,
) -> Callable[[Sequence[Cell], int], str]:
    def honesty(present: Sequence[Cell], n_worse: int) -> str:
        return _honesty(
            present, spec, n_worse=n_worse, max_mde=max_mde,
            max_mde_unchanged=max_mde_unchanged, max_mde_unchanged_cell=max_mde_unchanged_cell,
        )

    return honesty


def _version_shown(manifests: tuple[RunManifest, ...] | None) -> str:
    """The version the provenance block gives: this build's, unless every run the output is
    over was written by an earlier version of Prove under its old name and recorded the same
    version, in which case that version as the runs recorded it, so the output says who wrote
    them. A run written under the old name beside one written by this build keeps this build's
    version and says nothing of the old name."""
    if not manifests:
        return __version__
    recorded = {(m.poisson_prove_version, m.written_by) for m in manifests}
    if len(recorded) != 1:
        return __version__
    (version, written_by) = recorded.pop()
    if written_by is None:
        return __version__
    return version_as_recorded(version)


def _run_identity(
    provenance: dict[str, object], manifests: tuple[RunManifest, RunManifest] | None
) -> None:
    if manifests is not None:
        provenance["run_id_a"] = manifests[0].run_id
        provenance["run_id_b"] = manifests[1].run_id
        provenance["run_salt"] = manifests[0].run_salt


def _observation_cap(manifest: RunManifest) -> dict[str, int | str] | None:
    """The byte limits a run recorded for what it captured, as it recorded them.

    Every ``*_bytes`` entry of ``environment["capture"]``, under whatever name the build that
    wrote the run gave it, or None when the run recorded none. Echoed and never translated: a
    limit written before the per-value cut bounded a different thing than one written after it,
    and only the name says which, so no name is spelled here.

    A number, or the one word a run may record in a byte field: ADR-096 made *keep every value
    whole* a declarable state, and ``none`` is how a run records it. Every other string is
    dropped, as it always was -- ``_UNKNOWN_READING`` below turns a missing entry into ``not
    recorded``, and a run that declared nothing and a run that declared *whole* must not print
    the same line.
    """
    capture = manifest.environment.get("capture")
    if not isinstance(capture, Mapping):
        return None
    limits: dict[str, int | str] = {
        str(key): value
        for key, value in sorted(capture.items(), key=lambda entry: str(entry[0]))
        if str(key).endswith("_bytes")
        and (value == "none" or (isinstance(value, int) and not isinstance(value, bool)))
    }
    return limits or None


def _cuts_counted(manifest: RunManifest) -> bool:
    """Whether a count of spans stamped as cut can say anything about this run.

    A capture record that carries no per-value limit belongs to a run written before the
    per-value cut: its spans hold no stamp, so a count over them is a false zero. A run with no
    capture record at all is countable: a rollout's own trace is stamped whenever it is cut, and
    one written earlier was never cut.
    """
    capture = manifest.environment.get("capture")
    return not isinstance(capture, Mapping) or "max_observation_bytes" in capture


def _run_observations(
    provenance: dict[str, object],
    manifests: tuple[RunManifest, RunManifest] | None,
    observations: tuple[tuple[int, int], tuple[int, int]] | None,
) -> None:
    """The observation cut per run: what each run recorded, then what its envelopes hold.

    ``observations`` is ``(spans, spans stamped as cut)`` per run, counted by the caller from the
    stored envelopes; this module counts nothing. Both blocks need the manifests, because the
    limit comes from them and so does whether a count is one this module will print.
    """
    if manifests is None:
        return
    for side, manifest in zip(("a", "b"), manifests, strict=True):
        provenance[f"observation_cap_{side}"] = _observation_cap(manifest)
    if observations is None:
        return
    for name, at in (("trace_spans", 0), ("observation_cut_spans", 1)):
        for side, manifest, counts in zip(("a", "b"), manifests, observations, strict=True):
            provenance[f"{name}_{side}"] = counts[at] if _cuts_counted(manifest) else None


def _run_observation(
    provenance: dict[str, object],
    manifest: RunManifest | None,
    observations: tuple[int, int] | None,
) -> None:
    """``_run_observations`` for the one run of a survival report; the keys carry no side."""
    if manifest is None:
        return
    provenance["observation_cap"] = _observation_cap(manifest)
    if observations is not None:
        counted = _cuts_counted(manifest)
        provenance["trace_spans"] = observations[0] if counted else None
        provenance["observation_cut_spans"] = observations[1] if counted else None


def _run_declarations(
    provenance: dict[str, object],
    declarations: tuple[DeclarationCheck | None, DeclarationCheck | None] | None,
) -> None:
    """A10's eight keys per run, suffixed ``_a`` / ``_b`` like the identity and observation
    blocks -- and only for a run that declared. A run with no declaration gains no key: not
    ``None``, not ``[]``. The keys are conditionally present (W8), which is what keeps every
    frozen output over a declaration-free run byte-identical; and a pair where one side declared
    says so by carrying that side's keys alone. ``declarations`` is what the caller computed
    with ``steps.declaration_check``; this module counts nothing.
    """
    if declarations is None:
        return
    blocks = [None if check is None else check.provenance() for check in declarations]
    for key in next((list(block) for block in blocks if block is not None), []):
        for side, block in zip(("a", "b"), blocks, strict=True):
            if block is not None:
                provenance[f"{key}_{side}"] = block[key]


def _run_declaration(provenance: dict[str, object], check: DeclarationCheck | None) -> None:
    """``_run_declarations`` for the one run of a survival report; the keys carry no side."""
    if check is not None:
        provenance.update(check.provenance())


def build_report(
    diff: DiffResult,
    spec: ReportSpec,
    curves: Mapping[str, tuple[KMCurve, KMCurve]] | None = None,
    manifests: tuple[RunManifest, RunManifest] | None = None,
    observations: tuple[tuple[int, int], tuple[int, int]] | None = None,
    *,
    declarations: tuple[DeclarationCheck | None, DeclarationCheck | None] | None = None,
) -> Report:
    """Build a report.

    curves maps config_hash -> (curve_a, curve_b) for the optional survival panel; manifests
    supply run identity and each run's recorded byte limit for the provenance block and are never
    invented when absent; observations, given with the manifests, adds each run's span count and
    how many of those spans were stamped as cut; declarations, one ``DeclarationCheck`` or
    ``None`` per run, adds the eight declared-expectation lines for each run that declared (A10).
    """
    _validate_spec(spec)
    for label, other in spec.comparison.items():
        _check_comparison(diff, label, other)
    rows = _rows_of(diff.cells)
    grid = _grid(rows, spec, _diff_cell)
    provenance: dict[str, object] = {
        "event": diff.event,
        "t_unit": diff.t_unit,
        "horizon": diff.horizon,
        "method": diff.method,
        "seed_identity_match": diff.seed_identity_match,
        "unpaired_analysis": diff.unpaired_analysis,
        "q": diff.q,
        "n_not_comparable": diff.n_not_comparable,
        "dropped_a": diff.dropped_a,
        "dropped_b": diff.dropped_b,
        "episodes_censored_at_horizon": diff.truncated,
        "n_absent": sum(not c.present for c in grid[0]),
        "poisson_prove_version": _version_shown(manifests),
    }
    _run_identity(provenance, manifests)
    _run_observations(provenance, manifests, observations)
    _run_declarations(provenance, declarations)
    if spec.generated_at is not None:
        provenance["generated_at"] = spec.generated_at
    return _build_panel(
        rows,
        spec,
        mode="diff",
        event=diff.event,
        bound=None,
        headline_of=_single_headline(diff),
        honesty_of=_diff_honesty(
            spec, max_mde=diff.max_mde, max_mde_unchanged=diff.max_mde_unchanged,
            max_mde_unchanged_cell=diff.max_mde_unchanged_cell,
        ),
        provenance=provenance,
        methods=(diff, *spec.comparison.values()),
        horizon=diff.horizon,
        curves=curves,
        grid=grid,
    )


# ---------- build: multi event ----------


def _caption(event: str, n_safer: int, n_worse: int) -> str:
    return f"{event}: {_fmt(n_safer, 'int')} safer, {_fmt(n_worse, 'int')} worse"


def _method_label(method: str) -> str:
    return f"{method} (cause-specific)" if method == "logrank_bh" else method


def _multi_method_rows(
    multi: MultiDiffResult, comparison: Mapping[str, Any]
) -> tuple[tuple[str, ...], ...]:
    """Method table rows: the primary's per-event rows, then every comparison's, each labelled
    from the result's own ``method``. Only rendered when ``comparison`` is given."""
    if not comparison:
        return ()
    rows: list[tuple[str, ...]] = []

    def add_multi(m: MultiDiffResult) -> None:
        for e in m.events:
            ev = m.by_event[e]
            rows.append((
                f"{_method_label(m.method)} · {e}",
                "paired" if m.method in _PAIRED_METHODS else "unpaired",
                _fmt(ev.n_safer, "int"),
                _fmt(ev.n_worse, "int"),
                _fmt(ev.n_unchanged, "int"),
                f"{_fmt(ev.max_mde, 'pp0')}{_pp()}",
                _fmt(m.q, "sig3"),
            ))

    add_multi(multi)
    for other in comparison.values():
        if isinstance(other, MultiDiffResult):
            add_multi(other)
        else:
            rows.append(tuple(_method_row(other)))
    return tuple(rows)


def _check_tree(multi: MultiDiffResult, tree: TreeResult) -> None:
    """A tree is rendered beside the diff it was grown from or not at all, I18's shape one object
    over: its events and its cell count must be the family's. Checked before anything is built.

    A28 appends two clauses and rewords none, because the two it follows exist to *name* what
    differs and a digest can name nothing (spec A28 section 10 Q4). The **agreement digest**
    closes C16: two pairs over the same events with the same cell count and the same config
    grid, differing only in what happened, pass the arity clause and are refused here. The
    **knob clause** follows it because the digest is scheme-blind and q-blind by construction
    (section 3.3), so a ``mcnemar_bh`` tree would otherwise render happily beside a
    ``fisher_bh`` diff. ``agreement_digest`` is imported inside the function: ``tree.py``
    imports ``diff``, ``executor`` and ``store`` and not ``report``, so a module-level import
    would not be a cycle today, but it would be M7 depending on M14 -- and W20 pins that
    ``report.py`` imports ``poisson_prove.tree`` under ``TYPE_CHECKING`` only.
    """
    from poisson_prove.tree import agreement_digest

    if tuple(tree.root.events) != tuple(multi.events):
        raise ComparisonMismatch(
            f"the tree is over events {list(tree.root.events)}; the diff is over "
            f"{list(multi.events)}"
        )
    if tree.root.n_cells * len(tree.root.events) != multi.n_tests:
        raise ComparisonMismatch(
            f"the tree is over {tree.root.n_cells} cells x {len(tree.root.events)} events; the "
            f"diff is over {multi.n_tests} tests"
        )
    if tree.agreement != agreement_digest(multi):
        raise ComparisonMismatch(
            "the tree's agreement digest is not this diff's; the tree was grown from a "
            "different pair with the same family shape, so nothing above can be named"
        )
    if tree.root.method != multi.method or tree.root.q != multi.q:
        raise ComparisonMismatch(
            f"the tree was grown under {tree.root.method} at q = {tree.root.q:g}; this diff is "
            f"{multi.method} at q = {multi.q:g}"
        )


def build_multi_report(
    multi: MultiDiffResult,
    spec: ReportSpec,
    *,
    manifests: tuple[RunManifest, RunManifest] | None = None,
    tree: TreeResult | None = None,
    observations: tuple[tuple[int, int], tuple[int, int]] | None = None,
    declarations: tuple[DeclarationCheck | None, DeclarationCheck | None] | None = None,
) -> MultiReport:
    """One panel per event on a shared colour bound; headline and trade line come first.

    ``declarations`` -- one ``DeclarationCheck`` or ``None`` per run, computed by the caller --
    adds the eight declared-expectation lines to the provenance block for each run that
    declared, and nothing for one that did not (A10).

    With ``tree`` the markdown and the receipt also carry the layered report -- the omnibus, the
    fault lines, the cells and the bound -- between the headline block and the figure. The SVG
    never changes, and without a tree every byte is what it was. A tree grown on another pair
    is refused before anything is built.

    ``manifests`` add each run's identity and recorded byte limit to the provenance block, and
    ``observations`` -- ``(spans, spans stamped as cut)`` per run, counted by the caller -- adds
    the counts beside them, ``None`` for a run whose spans cannot be counted.
    """
    _validate_spec(spec)
    if tree is not None:
        _check_tree(multi, tree)
    order = tuple(
        sorted(
            multi.events,
            key=lambda e: (-multi.by_event[e].n_worse, -multi.by_event[e].n_safer, e),
        )
    )
    rows_by_event = {e: _rows_of(multi.by_event[e].cells) for e in order}
    # One hole map for every panel: each event's cells carry the same ``common``, so the grid
    # and its holes are identical across panels.
    holes = _hole_map(multi, spec)
    # ADR-032: the join is by ``(event, config_hash)``, one index per event, because two events'
    # intervals on the same cell are different numbers.
    grids = {
        e: _grid(rows_by_event[e], spec, _interval_cell(_interval_index(multi, e)), holes)
        for e in order
    }
    all_cells = [c for e in order for c in grids[e][0]]
    bound = _bound_for(all_cells, spec.color_max)
    trades = frozenset(str(h) for h in multi.trades["config_hash"])
    provenance: dict[str, object] = {
        "events": list(multi.events),
        "inferred": multi.inferred,
        "non_event": multi.non_event,
        "n_tests": multi.n_tests,
        "method": multi.method,
        "seed_identity_match": multi.seed_identity_match,
        "unpaired_analysis": multi.unpaired_analysis,
        "q": multi.q,
        "t_unit": multi.t_unit,
        "horizon": multi.horizon,
        "n_not_comparable": multi.n_not_comparable,
        "dropped_a": multi.dropped_a,
        "dropped_b": multi.dropped_b,
        "episodes_censored_at_horizon": multi.truncated,
        "n_absent": sum(not c.present for c in all_cells),
        "poisson_prove_version": _version_shown(manifests),
    }
    _run_identity(provenance, manifests)
    _run_observations(provenance, manifests, observations)
    _run_declarations(provenance, declarations)
    if spec.generated_at is not None:
        provenance["generated_at"] = spec.generated_at

    panels: dict[str, Report] = {}
    for e in order:
        ev: EventDiff = multi.by_event[e]

        def headline(
            present: Sequence[Cell], n_safer: int, n_worse: int, n_unchanged: int, e: str = e
        ) -> str:
            return _caption(e, n_safer, n_worse)

        panels[e] = _build_panel(
            rows_by_event[e],
            replace(spec, title=e, comparison={}),
            mode="diff",
            event=e,
            bound=bound,
            headline_of=headline,
            honesty_of=_diff_honesty(
                spec, max_mde=ev.max_mde, max_mde_unchanged=ev.max_mde_unchanged,
                max_mde_unchanged_cell=ev.max_mde_unchanged_cell,
            ),
            provenance=provenance,
            trades=trades,
            tiebreak=True,
            horizon=multi.horizon,
            grid=grids[e],
            intervals=multi.intervals is not None,
        )
    return MultiReport(
        spec=spec,
        events=order,
        panels=panels,
        headline=multi.headline(),
        trade_line=multi.trade_line(),
        inference_line=multi.to_markdown().splitlines()[0] if multi.inferred else None,
        bound=bound,
        provenance=provenance,
        _method_rows=_multi_method_rows(multi, spec.comparison),
        tree=tree,
        interval_lines=_interval_lines(multi),
        complement=multi.complementary_events(),
    )


# ---------- build: single-run survival ----------


def _rate_cell(coords: tuple[object, ...], r: dict[str, Any]) -> Cell:
    # A cell with no observed episodes -- every rollout errored, or every one censored out --
    # is a hole, not a measured zero. It takes the same path as a grid coordinate with no row.
    if int(r["n"]) == 0:
        return _absent(coords)
    nan = float("nan")
    return Cell(
        coords=coords,
        config_hash=str(r["config_hash"]),
        present=True,
        n_a=int(r["n"]),
        n_b=0,
        rate_a=float(r["_rate"]),
        rate_b=nan,
        delta=nan,
        p=nan,
        q=nan,
        verdict="",
        mde=nan,
    )


def _cif_at(curve: object, event: str, horizon: float) -> float:
    """F_k(horizon) from the cell table's curve: a CIF curve directly, a KM curve as 1 - S.

    An event that is not one of the curve's competing outcomes never occurred in the run, so
    its incidence is zero; the report stays permissive and draws an empty panel.
    """
    if isinstance(curve, CIFCurve):
        return curve.at(event, horizon) if event in curve.cif else 0.0
    if isinstance(curve, KMCurve):
        return 1.0 - curve.at(horizon)
    raise ReportError(f"cell table curve must be a CIFCurve or KMCurve, got {type(curve).__name__}")


def build_survival_report(
    cells: pd.DataFrame,
    spec: ReportSpec,
    *,
    events: Sequence[str],
    horizon: float,
    manifest: RunManifest | None = None,
    observations: tuple[int, int] | None = None,
    declarations: DeclarationCheck | None = None,
) -> SurvivalReport:
    """cells = M5 cell_table output; one rate panel per event, F_k(horizon) from its curve.

    ``manifest`` adds the run's identity and recorded byte limit to the provenance block, and
    ``observations`` -- ``(spans, spans stamped as cut)``, counted by the caller -- the counts.
    ``declarations``, the run's ``DeclarationCheck``, adds the eight declared-expectation lines
    when the run declared, and nothing when it did not (A10).
    """
    _validate_spec(spec)
    event_list = tuple(dict.fromkeys(str(e) for e in events))
    if not event_list:
        raise ReportError("events must name at least one outcome")
    for col in ("config_hash", "config", "n", "curve"):
        if col not in cells.columns:
            raise ReportError(f"cells lacks column {col!r}; pass cell_table() output")
    base_rows = _rows_of(cells)
    provenance: dict[str, object] = {
        "events": list(event_list),
        "horizon": float(horizon),
        "n_cells": len(base_rows),
        "poisson_prove_version": _version_shown(None if manifest is None else (manifest,)),
    }
    if manifest is not None:
        provenance["run_id"] = manifest.run_id
        provenance["run_salt"] = manifest.run_salt
        provenance["t_unit"] = manifest.t_unit
    _run_observation(provenance, manifest, observations)
    _run_declaration(provenance, declarations)
    if spec.generated_at is not None:
        provenance["generated_at"] = spec.generated_at

    panels: dict[str, Report] = {}
    for e in event_list:
        rows = [dict(r, _rate=_cif_at(r["curve"], e, horizon)) for r in base_rows]

        def headline(
            present: Sequence[Cell], n_safer: int, n_worse: int, n_unchanged: int, e: str = e
        ) -> str:
            return f"{e}: cumulative incidence at horizon {_fmt(horizon, 'num')} ({_unit()})"

        panels[e] = _build_panel(
            rows,
            replace(spec, title=e, comparison={}),
            mode="rate",
            event=e,
            bound=1.0,
            headline_of=headline,
            honesty_of=lambda present, n_worse: _coverage(present),
            provenance=provenance,
            horizon=float(horizon),
        )
    return SurvivalReport(spec=spec, events=event_list, panels=panels, provenance=provenance)


# ---------- text helpers ----------


def _truncate(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    if len(text) <= budget:
        return text
    if budget == 1:
        return "…"
    return text[: budget - 1] + "…"


def _wrap(text: str, budget: int) -> list[str]:
    """``text`` broken on spaces into lines of at most ``budget`` characters, longest first,
    never splitting a word shorter than the budget and hard-splitting one that is longer.
    Returns ``[""]`` for empty text, so a caller's line count is never zero."""
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        while len(word) > budget:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:budget])
            word = word[budget:]
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= budget:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _wrap_budget(width: int, x: int, font: int) -> int:
    """How many glyphs of ``font`` fit from ``x`` to 24 px short of the right edge."""
    return max(8, int((width - x - 24) / (_CHAR_EM * font)))


def _running_text(out: list[str], x: int, y: int, lines: list[str], step: int, attrs: str) -> int:
    """Emit ``lines`` as one ``<text>`` per line, ``step`` px apart; returns the ``y`` after the
    last."""
    for k, line in enumerate(lines):
        mark = ' data-wrap="1"' if k else ""
        out.append(f'<text x="{x}" y="{y + step * k}"{attrs}{mark}>{_xml_escape(line)}</text>')
    return y + step * len(lines)


def _attr(value: str) -> str:
    return _xml_escape(value, {'"': "&quot;"})


def _coords_text(cell: Cell) -> list[str]:
    return [_fmt(v, "coord") for v in cell.coords]


# ---------- SVG: panel bodies ----------


def _svg_body(rep: Report) -> tuple[list[str], int, int]:
    """The panel's elements (canvas rect first) and its (width, height). A standalone SVG wraps
    these in ``<svg>``; a stacked report lifts them into ``<g data-panel>`` unchanged."""
    if rep._forest:
        return _forest_body(rep)
    return _grid_body(rep)


def _notch(x: int, y: int, w: int, h: int) -> str:
    """Diagonal notches in two corners: the trade marker."""
    n = max(2, min(5, w // 3, h // 3))
    return (
        f'<path d="M{x},{y}h{n}v{n}z M{x + w},{y + h}h-{n}v-{n}z"/>'
    )


def _legend_caption(rep: Report) -> str:
    if rep._mode == "rate":
        return (
            f"F(horizon) = cumulative incidence at horizon {_fmt(rep._horizon, 'num')} {_in_pp()}; "
            f"event={rep._event}; blank = no data"
        )
    caption = (
        f"delta = rate_b - rate_a {_in_pp()}; event={rep._event}; negative is safer only if the "
        f"event "
        f"is a failure; corner square = significant; blank = no data"
    )
    if rep._trades:
        caption += "; corner notches = trade (safer in one event, worse in another)"
    return caption


def _honesty_lines(rep: Report, budget: int) -> list[list[str]]:
    """The honesty block's lines wrapped where the library's rendering wraps them."""
    plain = rep._honesty_plain.splitlines() if rep._honesty_plain else []
    lines = rep.honesty.splitlines()
    if len(plain) != len(lines):
        plain = lines
    return [_wrap_like(line, base, budget) for line, base in zip(lines, plain, strict=True)]


def _grid_body(rep: Report) -> tuple[list[str], int, int]:
    theme = rep.spec.theme
    cols = max(1, len(rep.x_values))
    rows = max(1, len(rep.y_values)) if rep.spec.y_axis is not None else 1
    cell_w = max(4, min(40, int(880 / cols)))
    cell_h = max(4, min(28, int(560 / rows)))
    font = 11
    left = 96 if rep.spec.y_axis is not None else 24
    width = left + cols * cell_w + 24
    title_lines = _wrap(rep.spec.title, _wrap_budget(width, left, font + 2))
    headline_lines = _wrap(rep.headline, _wrap_budget(width, left, font))
    caption_lines = _wrap_like(
        _legend_caption(rep),
        _plain(lambda: _legend_caption(rep)),
        _wrap_budget(width, left, font - 2),
    )
    honesty_lines = _honesty_lines(rep, _wrap_budget(width, left, font - 2))
    top = 52 + 18 * (len(title_lines) - 1) + 12 * (len(headline_lines) - 1)
    bottom = (
        112 + 12 * (len(caption_lines) - 1) + 12 * sum(len(lines) - 1 for lines in honesty_lines)
    )
    height = top + rows * cell_h + bottom
    label_budget = int(cell_w / (_CHAR_EM * (font - 2)))
    show_cell_labels = cell_w >= 34 and cell_h >= 14
    x_label_budget = max(1, int(cell_w / (_CHAR_EM * (font - 2))))
    y_label_budget = max(1, int((left - 8) / (_CHAR_EM * (font - 2))))
    present = [c for c in rep.cells if c.present]

    out: list[str] = []
    out.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{_CANVAS[theme]}"/>')
    y_next = _running_text(
        out, left, 20, title_lines, 18, f' fill="{_TEXT[theme]}" font-size="{font + 2}"'
    )
    _running_text(out, left, y_next, headline_lines, 12, f' fill="{_MUTED[theme]}"')

    out.append(f'<g stroke="{_GRID_STROKE[theme]}" stroke-width="1">')
    glyph = 4
    for j in range(rows):
        for i in range(cols):
            c = rep.cells[j * cols + i]
            x = left + i * cell_w
            y = top + j * cell_h
            data_cell = c.config_hash if c.present and c.config_hash is not None else "absent"
            markers = ""
            if rep._mode == "diff" and _is_saturated(c):
                markers += ' data-sat="1"'
            if c.present and c.config_hash in rep._trades:
                markers += ' data-trade="1"'
            out.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" '
                f'fill="{_cell_fill(c, rep._bound, theme, rep._mode)}" '
                f'data-cell="{_attr(data_cell)}"{markers}/>'
            )
    out.append("</g>")

    if rep._mode == "diff":
        out.append(f'<g fill="{_GLYPH[theme]}">')
        for j in range(rows):
            for i in range(cols):
                c = rep.cells[j * cols + i]
                if c.present and c.verdict in ("safer", "worse"):
                    x = left + i * cell_w + cell_w - glyph - 1
                    y = top + j * cell_h + 1
                    out.append(
                        f'<rect x="{x}" y="{y}" width="{glyph}" height="{glyph}" data-sig="1"/>'
                    )
        out.append("</g>")

    if rep._trades:
        out.append(f'<g fill="{_GLYPH[theme]}">')
        for j in range(rows):
            for i in range(cols):
                c = rep.cells[j * cols + i]
                if c.present and c.config_hash in rep._trades:
                    out.append(_notch(left + i * cell_w, top + j * cell_h, cell_w, cell_h))
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
                value = c.rate_a if rep._mode == "rate" else c.delta
                label = _fmt(value, "pp1")
                if not _look.active():
                    label = _truncate(label, label_budget)
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

    ly = top + rows * cell_h + 44
    lx = left
    out.append(f'<g font-size="{font - 2}">')
    swatches: list[tuple[str, str]] = []
    if rep._mode == "rate":
        for k, ratio in enumerate((0.0, 0.25, 0.5, 0.75, 1.0)):
            label = "0.0" if k == 0 else ("100.0" if k == 4 else "")
            swatches.append((_rate_fill(ratio, theme), label))
    else:
        # Legend: data-driven, so a side with no cells on it draws no swatch.
        has_neg = any(c.delta < 0 for c in present)
        has_pos = any(c.delta > 0 for c in present)
        if has_neg:
            swatches += [
                (_fill(-1.0, True, theme), f"-{_fmt(rep._bound, 'pp1')}"),
                (_fill(-0.5, True, theme), ""),
            ]
        swatches.append((_fill(0.0, True, theme), "0.0"))
        if has_pos:
            swatches += [
                (_fill(0.5, True, theme), ""),
                (_fill(1.0, True, theme), f"+{_fmt(rep._bound, 'pp1')}"),
            ]
        if any(_is_saturated(c) for c in present):
            swatches.append((SATURATED_FILL[theme], _SATURATION_LEGEND))
    for k, (fill, label) in enumerate(swatches):
        sx = lx + k * 46
        out.append(f'<rect x="{sx}" y="{ly}" width="40" height="10" fill="{fill}"/>')
        if label:
            out.append(
                f'<text x="{sx}" y="{ly + 22}" fill="{_MUTED[theme]}">{_xml_escape(label)}</text>'
            )
    y_next = _running_text(out, lx, ly + 36, caption_lines, 12, f' fill="{_MUTED[theme]}"')
    y_next = y_next + 4
    for lines in honesty_lines:
        y_next = _running_text(out, lx, y_next, lines, 12, f' fill="{_TEXT[theme]}"')
    out.append("</g>")
    return out, width, height


def _forest_body(rep: Report) -> tuple[list[str], int, int]:
    """One row per category: a point at delta on the shared bound, a faint bracket of
    half-width MDE on the same scale (M6's field, not an interval estimate), the significance
    glyph, and n_a/n_b at the row end. Geometry is emitted as plain numbers so the point and
    bracket are exact on the scale."""
    theme = rep.spec.theme
    font = 11
    row_h = 18
    left = 120
    axis_w = 480
    right = 140
    n_rows = len(rep.cells)
    width = left + axis_w + right
    title_lines = _wrap(rep.spec.title, _wrap_budget(width, left, font + 2))
    headline_lines = _wrap(rep.headline, _wrap_budget(width, left, font))
    def caption_text() -> str:
        text = (
            f"point = delta (rate_b - rate_a, {_unit()}) on the shared scale; bracket = ±MDE, "
            f"the minimum detectable effect from M6, not an interval estimate; "
            f"event={rep._event}; corner square = significant"
        )
        if rep._trades:
            text += "; row notches = trade"
        return text

    caption_lines = _wrap_like(
        caption_text(), _plain(caption_text), _wrap_budget(width, left, font - 2)
    )
    honesty_lines = _honesty_lines(rep, _wrap_budget(width, left, font - 2))
    top = 52 + 18 * (len(title_lines) - 1) + 12 * (len(headline_lines) - 1)
    bottom = (
        112 + 12 * (len(caption_lines) - 1) + 12 * sum(len(lines) - 1 for lines in honesty_lines)
    )
    height = top + n_rows * row_h + bottom
    x0 = left + axis_w / 2
    scale = (axis_w / 2) / rep._bound
    label_budget = max(1, int((left - 8) / (_CHAR_EM * (font - 2))))

    out: list[str] = []
    out.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{_CANVAS[theme]}"/>')
    y_next = _running_text(
        out, left, 20, title_lines, 18, f' fill="{_TEXT[theme]}" font-size="{font + 2}"'
    )
    _running_text(out, left, y_next, headline_lines, 12, f' fill="{_MUTED[theme]}"')
    out.append(
        f'<line x1="{_fmt(x0, "num")}" y1="{top}" x2="{_fmt(x0, "num")}" '
        f'y2="{top + n_rows * row_h}" stroke="{_MUTED[theme]}" stroke-width="1"/>'
    )
    glyph = 4
    for i, c in enumerate(rep.cells):
        y = top + i * row_h
        cy = y + row_h / 2
        data_cell = c.config_hash if c.present and c.config_hash is not None else "absent"
        markers = ' data-trade="1"' if c.present and c.config_hash in rep._trades else ""
        out.append(f'<g data-cell="{_attr(data_cell)}"{markers}>')
        out.append(
            f'<text x="{left - 6}" y="{_fmt(cy + (font - 2) / 2 - 1, "num")}" text-anchor="end" '
            f'fill="{_MUTED[theme]}" font-size="{font - 2}">'
            f'{_xml_escape(_truncate(_fmt(c.coords[0], "coord"), label_budget))}</text>'
        )
        if not c.present:
            out.append("</g>")
            continue
        px = x0 + c.delta * scale
        half = c.mde * scale
        out.append(
            f'<rect x="{_fmt(px - half, "num")}" y="{_fmt(cy - 3, "num")}" '
            f'width="{_fmt(2 * half, "num")}" height="6" fill="{_MUTED[theme]}" '
            f'fill-opacity="0.35" data-mde="1"/>'
        )
        out.append(
            f'<circle cx="{_fmt(px, "num")}" cy="{_fmt(cy, "num")}" r="4" '
            f'fill="{_cell_fill(c, rep._bound, theme, rep._mode)}" data-point="1"/>'
        )
        if c.verdict in ("safer", "worse"):
            out.append(
                f'<rect x="{left + axis_w + 8}" y="{_fmt(cy - glyph / 2, "num")}" width="{glyph}" '
                f'height="{glyph}" fill="{_GLYPH[theme]}" data-sig="1"/>'
            )
        if c.config_hash in rep._trades:
            out.append(f'<g fill="{_GLYPH[theme]}">{_notch(left, y, axis_w, row_h)}</g>')
        out.append(
            f'<text x="{left + axis_w + 20}" y="{_fmt(cy + (font - 2) / 2 - 1, "num")}" '
            f'fill="{_TEXT[theme]}" font-size="{font - 2}">'
            f'{_fmt(c.n_a, "int")}/{_fmt(c.n_b, "int")}</text>'
        )
        out.append("</g>")

    axis_y = top + n_rows * row_h + 14
    out.append(f'<g fill="{_MUTED[theme]}" font-size="{font - 2}">')
    out.append(
        f'<text x="{left}" y="{axis_y}">-{_xml_escape(_fmt(rep._bound, "pp1"))}</text>'
    )
    out.append(f'<text x="{_fmt(x0, "num")}" y="{axis_y}" text-anchor="middle">0.0</text>')
    out.append(
        f'<text x="{left + axis_w}" y="{axis_y}" text-anchor="end">'
        f'+{_xml_escape(_fmt(rep._bound, "pp1"))}</text>'
    )
    out.append(f'<text x="{left}" y="{axis_y + 16}">{_xml_escape(rep.spec.x_axis)} (rows)</text>')
    out.append("</g>")

    ly = top + n_rows * row_h + 44
    out.append(f'<g font-size="{font - 2}">')
    y_next = _running_text(out, left, ly + 36, caption_lines, 12, f' fill="{_MUTED[theme]}"')
    y_next = y_next + 4
    for lines in honesty_lines:
        y_next = _running_text(out, left, y_next, lines, 12, f' fill="{_TEXT[theme]}"')
    out.append("</g>")
    return out, width, height


def _svg_start(width: int, height: int, font: int = 11) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="{_FONT}" font-size="{font}">'
    )


def _render_svg(rep: Report) -> str:
    body, width, height = _svg_body(rep)
    return "\n".join([_svg_start(width, height), *body, "</svg>"]) + "\n"


def _multi_header(rep: MultiReport) -> list[tuple[str, str]]:
    """(text, kind) lines under the title: kind is "muted", "text" or "trade"."""
    lines: list[tuple[str, str]] = []
    if rep.inference_line is not None:
        lines.append((rep.inference_line, "muted"))
    lines.extend((line, "text") for line in rep.headline.splitlines())
    if rep.trade_line is not None:
        lines.append((rep.trade_line, "trade"))
    return lines


def _render_stacked_svg(
    spec: ReportSpec,
    events: Sequence[str],
    panels: Mapping[str, Report],
    header: list[tuple[str, str]],
) -> str:
    """All panels in one root <svg>: each panel's standalone body is lifted unchanged into a
    <g data-panel> with a translate, so subtrees match the panel's own to_svg()."""
    theme = spec.theme
    font = 11
    bodies = [(_svg_body(panels[e]), e) for e in events]
    width = max([w for (_, w, _), _ in bodies], default=200)
    title_lines = _wrap(spec.title, _wrap_budget(width, 24, font + 2))
    wrapped = [
        (line, kind, ' data-wrap="1"' if k else "")
        for text, kind in header
        for k, line in enumerate(_wrap(text, _wrap_budget(width, 24, font)))
    ]
    header_h = 36 + 18 * (len(title_lines) - 1) + 16 * len(wrapped)
    height = header_h + sum(h for (_, _, h), _ in bodies)
    out = [_svg_start(width, height, font)]
    out.append(f"<style>{_TRADE_STYLE}</style>")
    out.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{_CANVAS[theme]}"/>')
    y_next = _running_text(
        out, 24, 20, title_lines, 18, f' fill="{_TEXT[theme]}" font-size="{font + 2}"'
    )
    for k, (line, kind, mark) in enumerate(wrapped):
        y = y_next + 16 * k
        if kind == "trade":
            out.append(f'<text x="24" y="{y}" class="trade"{mark}>{_xml_escape(line)}</text>')
        else:
            colour = _MUTED[theme] if kind == "muted" else _TEXT[theme]
            out.append(f'<text x="24" y="{y}" fill="{colour}"{mark}>{_xml_escape(line)}</text>')
    offset = header_h
    for (body, _, h), e in bodies:
        out.append(f'<g data-panel="{_attr(e)}" transform="translate(0 {offset})">')
        out.extend(body)
        out.append("</g>")
        offset += h
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------- Markdown ----------


def _worst_table_rows(rep: Report) -> list[list[str]]:
    present = [c for c in rep.cells if c.present]
    rows = []
    for c in _worst(present, rep.spec.top_n, mode=rep._mode, tiebreak=rep._tiebreak):
        if rep._mode == "rate":
            rows.append([*_coords_text(c), _fmt(c.n_a, "int"), _fmt(c.rate_a, "pp1")])
            continue
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
                f"{_fmt(c.mde, 'pp0')}{_pp()}",
            ]
        )
        if rep._intervals:
            rows[-1].append(_interval_text(c))
    return rows


_WORST_HEADER_TAIL = [
    "n (a/b)", "rate_a (pp)", "rate_b (pp)", "delta (pp)", "p", "q", "verdict", "MDE",
]
_RATE_HEADER_TAIL = ["n", "F at horizon (pp)"]


def _worst_header_tail() -> list[str]:
    return ["n (a/b)", _h("rate_a"), _h("rate_b"), _h("delta"), "p", "q", "verdict", "MDE"]


def _rate_header_tail() -> list[str]:
    return ["n", _h("F at horizon")]
_METHOD_HEADER = ["method", "pairing", "safer", "worse", "unchanged", "max MDE", "q"]


def _worst_header(rep: Report) -> list[str]:
    if rep._mode == "rate":
        return _axes_of(rep.spec) + _rate_header_tail()
    # When ``R == 0`` M6 built no intervals and there is no column: a column that does not
    # exist cannot be read (the fault-lines table's rule, one table over).
    tail = [*_worst_header_tail(), _interval_column()] if rep._intervals else _worst_header_tail()
    return _axes_of(rep.spec) + tail


def _method_row(d: DiffResult) -> list[str]:
    return [
        _method_label(d.method),
        "paired" if d.method in _PAIRED_METHODS else "unpaired",
        _fmt(d.n_safer, "int"),
        _fmt(d.n_worse, "int"),
        _fmt(d.n_unchanged, "int"),
        f"{_fmt(d.max_mde, 'pp0')}{_pp()}",
        _fmt(d.q, "sig3"),
    ]


def _method_rows(rep: Report) -> list[list[str]]:
    return [_method_row(d) for d in rep._methods]


def _md_table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


#: What a provenance value of None reads as, by key prefix. The generic reading is ``none``, which
#: on these keys would say "no cap" and "none cut", the opposite of the fact: the run did not
#: record a limit, or its spans cannot be counted.
_UNKNOWN_READING = (
    ("observation_cap", "not recorded"),
    ("trace_spans", "not counted"),
    ("observation_cut_spans", "not counted"),
)


#: How a provenance key reads on the page when its words are not the key's own.
_PROVENANCE_LABELS = {"poisson_prove_version": "Prove version"}


def _provenance_lines(provenance: Mapping[str, object]) -> list[str]:
    lines = []
    for key, value in provenance.items():
        if key == "q":
            shown = _fmt(value, "sig3")
        elif key == "horizon":
            shown = _fmt(value, "num")
        elif isinstance(value, bool):
            shown = "true" if value else "false"
        elif isinstance(value, int):
            shown = _fmt(value, "int")
        elif isinstance(value, (list, tuple)):
            # An empty list reads ``none``: "nothing was missed" is a finding (A10).
            shown = ", ".join(str(v) for v in value) if value else "none"
        elif isinstance(value, Mapping):
            shown = ", ".join(f"{name}={entry}" for name, entry in value.items())
        elif value is None:
            shown = next(
                (word for prefix, word in _UNKNOWN_READING if key.startswith(prefix)), "none"
            )
        else:
            shown = str(value)
        lines.append(f"- {_PROVENANCE_LABELS.get(key, key.replace('_', ' '))}: {shown}")
        if key == "poisson_prove_version":
            writer = old_writer_line(shown)
            if writer is not None:
                lines.append(f"- {writer}")
    return lines


def _survival_rows(rep: Report) -> list[list[str]]:
    assert rep._survival is not None
    return [
        [*_coords_text(c), _fmt(sa, "pp1"), _fmt(sb, "pp1")] for c, sa, sb in rep._survival
    ]


def _honesty_heading(rep: Report) -> str:
    return "## Coverage" if rep._mode == "rate" else "## Honesty"


def _render_markdown(rep: Report) -> str:
    axes = _axes_of(rep.spec)
    parts = [
        f"# {rep.spec.title}",
        "",
        rep.headline,
        "",
        "![heatmap](heatmap.svg)" if rep._mode == "rate" else "![delta heatmap](heatmap.svg)",
        "",
        "## Worst cells",
        "",
        _md_table(_worst_header(rep), _worst_table_rows(rep)),
        "",
    ]
    if rep._methods:
        parts += ["## Methods", "", _md_table(_METHOD_HEADER, _method_rows(rep)), ""]
    parts += [_honesty_heading(rep), "", rep.honesty, ""]
    if rep._survival is not None:
        parts += [
            "## Survival at horizon",
            "",
            _md_table(axes + [_h("S_a at horizon"), _h("S_b at horizon")], _survival_rows(rep)),
            "",
        ]
    parts += [
        f"> {_EPISTEMIC_FENCE}",
        "",
        "## Provenance",
        "",
        *_provenance_lines(rep.provenance),
        "",
    ]
    return "\n".join(parts)


def _render_multi_markdown(rep: MultiReport) -> str:
    parts = [f"# {rep.spec.title}", ""]
    if rep.inference_line is not None:
        parts += [rep.inference_line, ""]
    parts += [rep.headline, ""]
    if rep.trade_line is not None:
        parts += [rep.trade_line, ""]
    if rep.tree is not None:
        parts += _tree_markdown(rep.tree)
    parts += ["![delta heatmaps](heatmap.svg)", ""]
    for e in rep.events:
        panel = rep.panels[e]
        parts += [
            f"## {panel.headline}",
            "",
            _md_table(_worst_header(panel), _worst_table_rows(panel)),
            "",
            panel.honesty,
            "",
        ]
    # ADR-060: the flat family's intervals sit in the honesty band, after the last panel's
    # honesty text and never beside a leaf row. The tree's *Cells* section is above the figure
    # and two sections away.
    parts += ["## Intervals", ""]
    for line in rep.interval_lines:
        parts += [line, ""]
    if rep._method_rows:
        parts += ["## Methods", "", _md_table(_METHOD_HEADER, rep._method_rows), ""]
    parts += [
        f"> {_EPISTEMIC_FENCE}",
        "",
        "## Provenance",
        "",
        *_provenance_lines(rep.provenance),
        "",
    ]
    return "\n".join(parts)


def _render_survival_markdown(rep: SurvivalReport) -> str:
    parts = [f"# {rep.spec.title}", "", "![heatmaps](heatmap.svg)", ""]
    for e in rep.events:
        panel = rep.panels[e]
        parts += [
            f"## {e}",
            "",
            panel.headline,
            "",
            _md_table(_worst_header(panel), _worst_table_rows(panel)),
            "",
            panel.honesty,
            "",
        ]
    parts += [
        f"> {_EPISTEMIC_FENCE}",
        "",
        "## Provenance",
        "",
        *_provenance_lines(rep.provenance),
        "",
    ]
    return "\n".join(parts)


# ---------- the layered report: four sections from a TreeResult ----------

#: What an untested level prints, by the reason's name (draft ADR-073). The keys are M14's three
#: P4.3 reasons and its two P4.2 reasons, ``root_not_rejected`` serving both levels. Precedence is
#: M14's and nothing here orders or re-derives it: a level's ``reason`` is looked up, never
#: inferred from what rejected. ``{configured}`` is the one number an untested reason carries, put
#: in after ``_fmt`` has formatted it.
_NOT_TESTED: dict[str, str] = {
    "depth": "depth {configured} configured",
    "root_not_rejected": "the root did not reject",
    "no_group_rejected": "no group rejected",
    "one_group": "one group is the whole family restated",
}

#: What the leaf row's MDE column means, said once on the page as S27 section 3.1 promised: free
#: text with no number in it.
_LEAF_MDE_MEANING = (
    "MDE is the smallest detectable increase from arm A's rate, capped at the headroom, "
    "so on a cell at ceiling it reads the headroom and is not a power number."
)

#: The bound's assumption, beside the number rather than in a footnote: the condition the source
#: states is one this tree's construction does not give.
_BOUND_ASSUMPTION = (
    "Yekutieli (2008) Corollary A.2 assumes each p-value is independent of its ancestors; this "
    "tree's group and root statistics aggregate their own cells, so that assumption is not "
    "established here."
)

#: One item of a tree section: a line, or a table as ``(header, rows)``.
_TreeItem = str | tuple[list[str], list[list[str]]]


def _tree_markdown(tree: TreeResult) -> list[str]:
    """The four sections as markdown parts for ``_render_multi_markdown`` to extend with: each
    heading, then each line or table, every one followed by a blank line.

    This function and ``_tree_html`` are the roots of the closure the S28 oracle's R11 reads
    (draft ADR-075). Every function either reaches, ``_fmt`` and M7's three table and line
    helpers excepted, does no arithmetic and formats no number itself; a rendering function
    added later joins the closure through these two or is unguarded.
    """
    parts: list[str] = []
    for heading, items in _tree_sections(tree):
        parts.extend([f"## {heading}", ""])
        for item in items:
            parts.extend([item if isinstance(item, str) else _md_table(*item), ""])
    return parts


def _tree_html(tree: TreeResult) -> list[str]:
    """The same four sections as receipt elements, one per line: an ``<h2>``, then a ``<p>`` per
    line through ``_html_lines`` and a table per table through ``_html_table``, escaped like
    every other element of the receipt and carrying no style of their own."""
    parts: list[str] = []
    for heading, items in _tree_sections(tree):
        parts.append(f"<h2>{_html.escape(heading)}</h2>")
        for item in items:
            parts.append(
                f"<p>{_html_lines(item)}</p>" if isinstance(item, str) else _html_table(*item)
            )
    return parts


def _tree_sections(tree: TreeResult) -> list[tuple[str, list[_TreeItem]]]:
    """The layered report as four headed sections, in the order a reader acts on them. Every
    number is a field of the tree through ``_fmt`` under the kind S28 section 3.6 assigns;
    nothing here computes, sorts or ranks."""
    return [
        ("Omnibus", _omnibus_items(tree.root)),
        ("Fault lines", _fault_lines_items(tree)),
        ("Cells", _cells_items(tree.leaves, tree.bound)),
        ("Bound", _bound_items(tree.bound)),
    ]


def _omnibus_items(root: RootResult) -> list[_TreeItem]:
    """The root's own headline, verbatim; how the omnibus was drawn; one row per event in the
    root's order; the informative line, whose complement is a field."""
    rows = [
        [
            event,
            _fmt(root.location[event], "pp1"),
            _fmt(root.p_location[event], "sig3"),
            _fmt(root.dispersion[event], "pp1"),
            _fmt(root.p_dispersion[event], "sig3"),
        ]
        for event in root.events
    ]
    return [
        _detail(root.headline()),
        f"min-p of location and dispersion; {_fmt(root.n_permutations, 'int')} within-cell "
        f"permutations, {root.scheme}, seed {_fmt(root.seed, 'seed')}",
        f"p floor {_fmt(root.p_floor, 'sig3')}: the smallest p "
        f"{_fmt(root.n_permutations, 'int')} permutations can express; a p at the floor is a "
        "bound, not a measurement",
        (["event", _h("mean delta"), "p", _h("rms delta"), "p"], rows),
        f"informative cells: {_fmt(root.n_informative_cells, 'int')} of "
        f"{_fmt(root.n_cells, 'int')}; {_fmt(root.n_uninformative_cells, 'int')} unchanged by "
        "every exchange",
    ]


def _fault_lines_items(tree: TreeResult) -> list[_TreeItem]:
    """Level 2: the grouping and the shape it was admitted on; every refused key in chain order
    with its detail verbatim, which already carries the value a reader would paste back; the
    null and what tested it, or why nothing did; one row per group in label order, never
    ordered by result. The discordant column exists only under pair swap and the p, q and
    verdict columns only when the level was tested: a column that does not exist cannot be read.
    """
    grouping, fault = tree.grouping, tree.fault_lines
    items: list[_TreeItem] = [
        f"grouping {grouping.key} ({grouping.resolved_by}), {_fmt(grouping.n_groups, 'int')} "
        f"groups; cells per group min {_fmt(grouping.size_min, 'int')} / median "
        f"{_fmt(grouping.size_median, 'num')} / max {_fmt(grouping.size_max, 'int')}; "
        f"{_fmt(fault.n_degenerate_groups, 'int')} degenerate; "
        f"{_fmt(grouping.n_resolvable_groups, 'int')} of {_fmt(grouping.n_groups, 'int')} "
        f"groups resolve {_fmt(grouping.max_group_mde, 'pp0')}{_pp()} at alpha "
        f"{_fmt(grouping.alpha_floor, 'sig3')}"
    ]
    for refusal in grouping.refused:
        items.append(
            f"refused {refusal.key} ({refusal.rung}): {refusal.reason}; {_detail(refusal.detail)} "
            f"next: {refusal.next_rung}"
        )
    if fault.tested:
        items.append(
            f'"{fault.null}" tested by BH across {_fmt(fault.n_groups, "int")} groups at q '
            f'{_fmt(fault.q, "sig3")}: {_fmt(fault.n_rejected_groups, "int")} rejected'
        )
        # C33 (b): a group p is drawn from the same permutations the root was, so it has the
        # same floor. Only where a level was tested -- there is no floor under a p nobody drew.
        items.append(
            f"group p floor {_fmt(tree.root.p_floor, 'sig3')}: the same "
            f"{_fmt(tree.root.n_permutations, 'int')} permutations; a group p at the floor is a "
            "bound, not a measurement"
        )
    else:
        items.append(f'"{fault.null}" not tested: {_not_tested(fault.reason, tree.bound)}')
    pair_swap = tree.root.scheme == "pair_swap"
    header = [
        grouping.key,
        "cells",
        "informative",
        "unchanged by every exchange",
        "units (a/b)",
        _h("group MDE"),
    ]
    if pair_swap:
        header.append("discordant pairs")
    if fault.tested:
        header.extend(["p", "q", "verdict"])
    rows: list[list[str]] = []
    for group in fault.groups:
        row = [
            group.label,
            _fmt(group.n_cells, "int"),
            _fmt(group.n_informative_cells, "int"),
            _fmt(group.n_uninformative_cells, "int"),
            f"{_fmt(group.n_a, 'int')}/{_fmt(group.n_b, 'int')}",
            f"{_fmt(group.mde, 'pp1')}{_pp()}",
        ]
        if pair_swap:
            row.append(_fmt(group.n_discordant, "int"))
        if fault.tested:
            row.extend(
                [
                    _fmt(group.p_group, "sig3"),
                    _fmt(group.q_group, "sig3"),
                    "rejected" if group.rejects else "not rejected",
                ]
            )
        rows.append(row)
    items.append((header, rows))
    return items


def _cells_items(leaves: Leaves, bound: Bound) -> list[_TreeItem]:
    """Level 3: the null and what tested it, or the one reason nothing did and nothing else; what
    the MDE column means; then per family, in the tree's order, its line and under it one row
    per rejected cell in the family's own order. Every key of a cell's config is named, not the
    figure's axes: the tree is over the whole family and ``--fix`` slices only the figure."""
    if not leaves.tested:
        return [f"not tested: {_not_tested(leaves.reason, bound)}"]
    items: list[_TreeItem] = [
        f'"{leaves.null}" tested by BH within each of {_fmt(leaves.n_families, "int")} '
        f'rejecting groups at q {_fmt(leaves.q, "sig3")}: {_fmt(leaves.n_rejected, "int")} of '
        f'{_fmt(leaves.n_tests, "int")} rejected'
    ]
    if leaves.families:
        items.append(_LEAF_MDE_MEANING)
    for family in leaves.families:
        items.append(
            f"{family.key}={family.label}: {_fmt(family.n_tests, 'int')} tests, "
            f"{_fmt(family.n_rejected, 'int')} rejected; cell MDE median "
            f"{_fmt(family.mde_median, 'pp0')}{_pp()} / max {_fmt(family.mde_max, 'pp0')}{_pp()}"
        )
        rows = [
            [
                _config_text(leaf.config),
                leaf.event,
                _fmt(leaf.delta, "pp1"),
                _fmt(leaf.q_within, "sig3"),
                f"{_fmt(leaf.mde, 'pp0')}{_pp()}",
            ]
            for leaf in family.cells
            if leaf.rejects
        ]
        if rows:
            items.append((["cell", "event", _h("delta"), "q", "MDE"], rows))
    return items


def _config_text(config: Mapping[str, Any]) -> str:
    """A cell as ``key=value`` over every key of its config, in the config's own order."""
    return ", ".join(f"{key}={value}" for key, value in config.items())


def _bound_items(bound: Bound) -> list[_TreeItem]:
    """The rule's number with every term of the rule beside it -- the ``2`` and the ``x`` are text
    around four fields -- then the assumption the source's corollary rests on."""
    return [
        f"depth {_fmt(bound.depth, 'int')} ({_fmt(bound.depth_configured, 'int')} configured); "
        f"outer-nodes false discovery rate at most {_fmt(bound.bound, 'sig3')} = "
        f"2 x {_fmt(bound.depth, 'int')} x {_fmt(bound.q, 'sig3')} x "
        f"{_fmt(bound.delta_star, 'sig3')}",
        _BOUND_ASSUMPTION,
    ]


def _not_tested(reason: str | None, bound: Bound) -> str:
    """The sentence an untested level prints, by its reason's name. A reason with no sentence
    here raises rather than printing a string nobody wrote a sentence for."""
    try:
        sentence = _NOT_TESTED[str(reason)]
    except KeyError:
        raise ReportError(f"no sentence for the untested reason {reason!r}") from None
    return sentence.replace("{configured}", _fmt(bound.depth_configured, "int"))


# ---------- HTML ----------


def _html_table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    head = "".join(f"<th>{_html.escape(h)}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{_html.escape(v)}</td>" for v in r) + "</tr>" for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _html_lines(text: str) -> str:
    return "<br>".join(_html.escape(line) for line in text.splitlines())


def _html_style(theme: Theme) -> str:
    """The receipt's whole stylesheet. The body is bounded and its text wraps; the stacked
    SVG sits in a horizontally scrollable figure at full width with its aspect ratio kept;
    print scales the figure to the page instead of scrolling."""
    return (
        "html{background:" + _CANVAS[theme] + "}"
        "body{max-width:1100px;margin:0 auto;padding:24px;box-sizing:border-box;"
        "font-family:" + _FONT + ";font-size:14px;line-height:1.45;"
        f"background:{_CANVAS[theme]};color:{_TEXT[theme]};"
        "overflow-wrap:anywhere;white-space:normal}"
        "h1,h2,p,li,blockquote{white-space:normal;overflow-wrap:anywhere}"
        "table{border-collapse:collapse;margin:12px 0;max-width:100%}"
        f"th,td{{border:1px solid {_MUTED[theme]};padding:4px 8px;text-align:left}}"
        ".figure{width:100%;overflow-x:auto;margin:12px 0}"
        ".figure svg{display:block;width:100%;height:auto;max-width:none}"
        f"blockquote{{border-left:3px solid {_MUTED[theme]};margin:12px 0;padding-left:12px}}"
        f".trade{{color:{_FAILED}}}"
        "@media print{body{max-width:none;background:#FFFFFF;color:#000000}"
        ".figure{overflow:visible;page-break-inside:avoid}"
        ".figure svg{width:100%;height:auto}}"
    )


def _html_figure(svg: str) -> str:
    return f'<div class="figure">{svg.rstrip(chr(10))}</div>'


def _html_head(title: str, theme: Theme) -> list[str]:
    return [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{_html.escape(title)}</title>",
        f"<style>{_html_style(theme)}</style>",
        "</head>",
        "<body>",
        f"<h1>{_html.escape(title)}</h1>",
    ]


def _html_close(provenance: Mapping[str, object]) -> list[str]:
    return [
        f"<blockquote>{_html.escape(_EPISTEMIC_FENCE)}</blockquote>",
        "<h2>Provenance</h2>",
        "<ul>"
        + "".join(f"<li>{_html.escape(line[2:])}</li>" for line in _provenance_lines(provenance))
        + "</ul>",
        "</body>",
        "</html>",
    ]


def _render_html(rep: Report) -> str:
    axes = _axes_of(rep.spec)
    parts = _html_head(rep.spec.title, rep.spec.theme)
    parts += [
        f"<p>{_html.escape(rep.headline)}</p>",
        _html_figure(rep.to_svg()),
        "<h2>Worst cells</h2>",
        _html_table(_worst_header(rep), _worst_table_rows(rep)),
    ]
    if rep._methods:
        parts += ["<h2>Methods</h2>", _html_table(_METHOD_HEADER, _method_rows(rep))]
    parts += [f"<h2>{_honesty_heading(rep)[3:]}</h2>", f"<p>{_html_lines(rep.honesty)}</p>"]
    if rep._survival is not None:
        parts += [
            "<h2>Survival at horizon</h2>",
            _html_table(axes + [_h("S_a at horizon"), _h("S_b at horizon")], _survival_rows(rep)),
        ]
    parts += _html_close(rep.provenance)
    return "\n".join(parts) + "\n"


def _render_multi_html(rep: MultiReport) -> str:
    parts = _html_head(rep.spec.title, rep.spec.theme)
    if rep.inference_line is not None:
        parts.append(f"<p>{_html.escape(rep.inference_line)}</p>")
    parts.append(f"<p>{_html_lines(rep.headline)}</p>")
    if rep.trade_line is not None:
        parts.append(f'<p class="trade">{_html.escape(rep.trade_line)}</p>')
    if rep.tree is not None:
        parts += _tree_html(rep.tree)
    parts.append(_html_figure(rep.to_svg()))
    for e in rep.events:
        panel = rep.panels[e]
        parts += [
            f"<h2>{_html.escape(panel.headline)}</h2>",
            _html_table(_worst_header(panel), _worst_table_rows(panel)),
            f"<p>{_html_lines(panel.honesty)}</p>",
        ]
    parts.append("<h2>Intervals</h2>")
    parts.extend(f"<p>{_html_lines(line)}</p>" for line in rep.interval_lines)
    if rep._method_rows:
        parts += ["<h2>Methods</h2>", _html_table(_METHOD_HEADER, rep._method_rows)]
    parts += _html_close(rep.provenance)
    return "\n".join(parts) + "\n"


def _render_survival_html(rep: SurvivalReport) -> str:
    # The coverage line is printed once per panel, inside the inline SVG; the body does not
    # repeat it.
    parts = _html_head(rep.spec.title, rep.spec.theme)
    parts.append(_html_figure(rep.to_svg()))
    for e in rep.events:
        panel = rep.panels[e]
        parts += [
            f"<h2>{_html.escape(e)}</h2>",
            f"<p>{_html.escape(panel.headline)}</p>",
            _html_table(_worst_header(panel), _worst_table_rows(panel)),
        ]
    parts += _html_close(rep.provenance)
    return "\n".join(parts) + "\n"
