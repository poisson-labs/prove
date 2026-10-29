"""The four charts of a saved comparison, as Prove's own SVG, drawn from the data beside them.

Each chart is one SVG: its ``title`` and ``desc`` first, ``role="img"`` naming both, its own
style for light and dark (the look's chart tokens, by value), no script and no reference outside
itself. Direction is shown by position and shape as well as colour: a rise to the right or up and
marked ``▲``, a fall to the left or down and marked ``▼``; the first run is drawn in ``--dim``, the
second in ``--after``. Every mark carries a hover title giving its row's facts. Numbers are
printed by rule 10 (``_look``).
"""

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from typing import Any

from poisson_prove import _look

#: The look file's chart tokens, light and dark (``docs/cli-look.md``, the static UI section).
LIGHT = {
    "bg": "#fcfcfb",
    "surface": "#f4f3ef",
    "rule": "#dddcd6",
    "text": "#0b0b0b",
    "dim": "#5f5e59",
    "rise": "#c4511f",
    "fall": "#2a6fc4",
    "mid": "#e9e8e3",
    "after": "#5444c9",
}
DARK = {
    "bg": "#1a1a19",
    "surface": "#242422",
    "rule": "#3a3a37",
    "text": "#f0efec",
    "dim": "#a8a79f",
    "rise": "#e0703f",
    "fall": "#4f94e8",
    "mid": "#383835",
    "after": "#9085e9",
}
_FONT = "ui-monospace,Menlo,Consolas,monospace"


def _esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def _style(ident: str) -> str:
    def rules(c: Mapping[str, str]) -> str:
        i = f"#{ident}"
        return (
            f"{i} text{{font:11px {_FONT};fill:{c['text']}}}"
            f"{i} .dimt{{fill:{c['dim']}}}{i} .bold{{font-weight:700}}"
            f"{i} .axis{{stroke:{c['rule']};stroke-width:1}}"
            f"{i} .zero{{stroke:{c['dim']};stroke-width:1}}"
            f"{i} .thr{{stroke:{c['text']};stroke-width:1}}"
            f"{i} .rise{{fill:{c['rise']}}}{i} .fall{{fill:{c['fall']}}}"
            f"{i} .rise-line{{stroke:{c['rise']}}}{i} .fall-line{{stroke:{c['fall']}}}"
            f"{i} .rise-text{{fill:{c['rise']}}}{i} .fall-text{{fill:{c['fall']}}}"
            f"{i} .dim-line{{stroke:{c['dim']}}}{i} .dim-fill{{fill:{c['dim']}}}"
            f"{i} .before{{stroke:{c['dim']};fill:none;stroke-width:1.5}}"
            f"{i} .after{{stroke:{c['after']};fill:none;stroke-width:2.5}}"
            f"{i} .after-text{{fill:{c['after']}}}"
            f"{i} .cell{{stroke:{c['rule']};stroke-width:1}}"
            f"{i} .empty{{fill:{c['bg']}}}{i} .halo{{stroke:{c['surface']};stroke-width:2}}"
        )

    return f"<style>{rules(LIGHT)}@media (prefers-color-scheme: dark){{{rules(DARK)}}}</style>"


def _svg(
    ident: str, title: str, desc: str, width: float, height: float, body: Sequence[str]
) -> str:
    t, d = f"{ident}-title", f"{ident}-desc"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" id="{_esc(ident)}" role="img" '
        f'aria-labelledby="{t} {d}" viewBox="0 0 {width:g} {height:g}" width="100%">'
        f'<title id="{t}">{_esc(title)}</title><desc id="{d}">{_esc(desc)}</desc>'
        f"{_style(ident)}{''.join(body)}</svg>"
    )


def _text(
    x: float, y: float, text: str, *, cls: str = "", anchor: str = "start", extra: str = ""
) -> str:
    attrs = f' class="{cls}"' if cls else ""
    anchor_attr = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return f'<text x="{x:.1f}" y="{y:.1f}"{attrs}{anchor_attr}{extra}>{_esc(text)}</text>'


def _f(value: Any) -> str:
    """A rate, change or limit as rule 10 prints it, or its absence."""
    if value is None:
        return "none"
    return _look.fmt_rate(value)


def _signed(value: Any) -> str:
    return _look.fmt_signed(value)


def _p(value: Any) -> str:
    return "none" if value is None else _look.fmt_p(value)


def _scale(lo: float, hi: float, x0: float, x1: float) -> Any:
    span = (hi - lo) or 1.0

    def at(v: float) -> float:
        return x0 + (v - lo) / span * (x1 - x0)

    return at


def _ticks(limit: float) -> tuple[float, list[float]]:
    """A symmetric axis to a round limit at or above ``limit``, with two ticks a side, so the
    labels never crowd each other."""
    limit = max(limit, 0.05)
    for step in (0.05, 0.1, 0.2, 0.25, 0.5, 1.0):
        if limit <= step * 4:
            top = round(math.ceil(limit / step - 1e-9) * step, 3)
            half = round(top / 2, 3)
            return top, [-top, -half, half, top]
    return 1.0, [-1.0, -0.5, 0.5, 1.0]


def _n(d: float) -> str:
    """A coordinate to one decimal."""
    return f"{d:.1f}"


# ---------- the verdict heatmap ----------


def heatmap(chart: Mapping[str, Any]) -> str:
    """The verdict over the conditions: the first axis across, the rest up (lowest at the
    bottom), a flagged cell filled toward the direction's colour, deeper for a larger change."""
    rows: Sequence[Mapping[str, Any]] = chart["cells"]
    x_values: Sequence[Any] = chart["x_values"]
    y_values: Sequence[Any] = chart["y_values"]
    x_axis, y_axis = str(chart["x_axis"]), str(chart["y_axis"])
    by_key = {(c["x"], c["y"]): c for c in rows}
    if not y_axis and len(x_values) > 6:
        # One axis, many conditions: the cells wrap into rows of six, each cell labelled.
        return _heatmap_wrapped(chart, rows)
    cw, ch, x0, y0 = 140, 80, 110 if y_axis else 24, 30
    width = x0 + cw * max(len(x_values), 1) + 12
    height = y0 + ch * max(len(y_values), 1) + 52
    body: list[str] = []
    for i, x in enumerate(x_values):
        body.append(
            _text(x0 + i * cw + cw / 2, y0 - 10, _esc_plain(x), cls="dimt", anchor="middle")
        )
    largest = (
        max((abs(float(c["delta"])) for c in rows if c["delta"] is not None), default=0.0) or 1.0
    )
    for j, y in enumerate(reversed(list(y_values))):
        if y_axis:
            body.append(
                _text(x0 - 10, y0 + j * ch + ch / 2 + 4, _esc_plain(y), cls="dimt", anchor="end")
            )
        for i, x in enumerate(x_values):
            cell = by_key.get((x, y))
            if cell is None:
                continue
            px, py = x0 + i * cw + 1, y0 + j * ch + 1
            delta = cell["delta"]
            flagged = bool(cell["flagged"])
            direction = (
                "rise"
                if delta is not None and delta > 0
                else "fall"
                if delta is not None and delta < 0
                else ""
            )
            tip = (
                f"{cell['condition']}, {chart['event']}: before {_f(cell['before'])}, after "
                f"{_f(cell['after'])}, "
                f"change {_signed(delta)}, q {_p(cell['q'])}, {cell['verdict']}"
            )
            if flagged and direction:
                depth = 0.2 + 0.4 * min(abs(float(delta)) / largest, 1.0)
                body.append(
                    f'<rect class="{direction} cell" x="{px}" y="{py}" width="{cw - 2}" '
                    f'height="{ch - 2}" '
                    f'rx="4" '
                    f'fill-opacity="{depth:.2f}"><title>{_esc(tip)}</title></rect>'
                )
            else:
                body.append(
                    f'<rect class="empty cell" x="{px}" y="{py}" width="{cw - 2}" '
                    f'height="{ch - 2}" '
                    f'rx="4">'
                    f"<title>{_esc(tip)}</title></rect>"
                )
            glyph = "▲" if direction == "rise" else "▼" if direction == "fall" else ""
            body.append(_text(px + 10, py + 22, str(cell["verdict"]), cls="bold"))
            body.append(_text(px + 10, py + 42, f"{glyph} {_signed(delta)}".strip()))
            # On a filled cell the q is in the text colour: dim on the fill would not read.
            body.append(
                _text(
                    px + 10,
                    py + 60,
                    f"q {_p(cell['q'])}",
                    cls="" if flagged and direction else "dimt",
                )
            )
    body.append(
        _text(x0 + cw * len(x_values) / 2, height - 30, x_axis, cls="dimt", anchor="middle")
    )
    if y_axis:
        mid = y0 + ch * len(y_values) / 2
        body.append(
            _text(
                14,
                mid,
                y_axis,
                cls="dimt",
                anchor="middle",
                extra=f' transform="rotate(-90 14 {mid:.1f})"',
            )
        )
    lx = x0
    for label, cls in (
        ("▲ rose, flagged", "rise cell"),
        ("▼ fell, flagged", "fall cell"),
        ("not flagged", "empty cell"),
    ):
        body.append(
            f'<rect class="{cls}" x="{lx}" y="{height - 16}" width="12" height="12" rx="2" '
            f'fill-opacity="0.6">'
            f"<title>{_esc(label)}</title></rect>"
        )
        body.append(_text(lx + 18, height - 6, label))
        lx += 150
    return _svg(chart["id"], chart["title"], chart["desc"], width, height, body)


def _cell_body(
    cell: Mapping[str, Any], px: float, py: float, cw: int, ch: int, largest: float, event: str
) -> list[str]:
    """One heatmap cell: its rect, its word, its change and its q."""
    delta = cell["delta"]
    flagged = bool(cell["flagged"])
    direction = (
        "rise"
        if delta is not None and delta > 0
        else "fall"
        if delta is not None and delta < 0
        else ""
    )
    tip = (
        f"{cell['condition']}, {event}: before {_f(cell['before'])}, after {_f(cell['after'])}, "
        f"change {_signed(delta)}, q {_p(cell['q'])}, {cell['verdict']}"
    )
    out = []
    if flagged and direction:
        depth = 0.2 + 0.4 * min(abs(float(delta)) / largest, 1.0)
        out.append(
            f'<rect class="{direction} cell" x="{_n(px)}" y="{_n(py)}" width="{cw - 2}" '
            f'height="{ch - 2}" rx="4" fill-opacity="{depth:.2f}"><title>{_esc(tip)}</title></rect>'
        )
    else:
        out.append(
            f'<rect class="empty cell" x="{_n(px)}" y="{_n(py)}" width="{cw - 2}" '
            f'height="{ch - 2}" rx="4"><title>{_esc(tip)}</title></rect>'
        )
    glyph = "▲" if direction == "rise" else "▼" if direction == "fall" else ""
    out.append(_text(px + 10, py + 22, str(cell["verdict"]), cls="bold"))
    out.append(_text(px + 10, py + 42, f"{glyph} {_signed(delta)}".strip()))
    # On a filled cell the q is in the text colour: dim on the fill would not read.
    out.append(
        _text(px + 10, py + 60, f"q {_p(cell['q'])}", cls="" if flagged and direction else "dimt")
    )
    return out


def _legend(x0: float, height: float) -> list[str]:
    out = []
    lx = x0
    for label, cls in (
        ("▲ rose, flagged", "rise cell"),
        ("▼ fell, flagged", "fall cell"),
        ("not flagged", "empty cell"),
    ):
        out.append(
            f'<rect class="{cls}" x="{_n(lx)}" y="{height - 16}" width="12" height="12" rx="2" '
            f'fill-opacity="0.6"><title>{_esc(label)}</title></rect>'
        )
        out.append(_text(lx + 18, height - 6, label))
        lx += 150
    return out


def _heatmap_wrapped(chart: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    """A one-axis comparison with many conditions: the cells in rows of six, in the axis's
    order, each labelled with its value above the cell."""
    cw, ch, per_row, x0, y0 = 140, 96, 6, 24, 30
    largest = (
        max((abs(float(c["delta"])) for c in rows if c["delta"] is not None), default=0.0) or 1.0
    )
    lines = (len(rows) + per_row - 1) // per_row
    width = x0 + cw * per_row + 12
    height = y0 + ch * lines + 52
    body: list[str] = []
    for i, cell in enumerate(rows):
        px = x0 + (i % per_row) * cw + 1
        py = y0 + (i // per_row) * ch + 1
        body.append(_text(px + 10, py + 12, _esc_plain(cell["x"]), cls="dimt"))
        body.extend(_cell_body(cell, px, py + 16, cw, ch - 16, largest, str(chart["event"])))
    body.append(
        _text(x0 + cw * per_row / 2, height - 30, str(chart["x_axis"]), cls="dimt", anchor="middle")
    )
    body.extend(_legend(x0, height))
    return _svg(chart["id"], chart["title"], chart["desc"], width, height, body)


def _esc_plain(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _look.fmt_num(value)
    return str(value)


# ---------- per-condition differences ----------


def differences(chart: Mapping[str, Any]) -> str:
    """Each condition's change, after minus before, with its interval at the level the
    comparison recorded; a flagged row in its direction's colour and bold, an unflagged row dim."""
    rows: Sequence[Mapping[str, Any]] = chart["cells"]
    label_w = min(max((len(str(c["condition"])) for c in rows), default=10) * 6.6 + 20, 300)
    rowh, top = 26, 40
    x0 = label_w + 10
    x1 = x0 + 400
    width = x1 + 240
    height = top + rowh * len(rows) + 44
    extent = max(
        (abs(float(v)) for c in rows for v in (c["delta"], c["lo"], c["hi"]) if v is not None),
        default=0.1,
    )
    limit, ticks = _ticks(extent)
    at = _scale(-limit, limit, x0, x1)
    body: list[str] = []
    for t in ticks:
        body.append(
            f'<line class="axis" x1="{_n(at(t))}" x2="{_n(at(t))}" y1="{top - 8}" '
            f'y2="{height - 34}"/>'
        )
        body.append(_text(at(t), height - 20, _signed(t), cls="dimt", anchor="middle"))
    body.append(
        f'<line class="zero" x1="{_n(at(0))}" x2="{_n(at(0))}" y1="{top - 8}" y2="{height - 34}"/>'
    )
    body.append(_text(at(0), height - 20, "0", cls="dimt", anchor="middle"))
    body.append(_text(x0, top - 18, "◀ after lower", cls="dimt"))
    body.append(_text(x1, top - 18, "after higher ▶", cls="dimt", anchor="end"))
    for i, c in enumerate(rows):
        y = top + i * rowh + rowh / 2
        delta = c["delta"]
        flagged = bool(c["flagged"])
        direction = (
            "rise"
            if delta is not None and delta > 0
            else "fall"
            if delta is not None and delta < 0
            else ""
        )
        line_cls = f"{direction}-line" if flagged and direction else "dim-line"
        fill_cls = direction if flagged and direction else "dim-fill"
        glyph = "▲" if direction == "rise" else "▼" if direction == "fall" else ""
        tip = (
            f"{c['condition']}: change {_signed(delta)} [{_signed(c['lo'])}, {_signed(c['hi'])}], "
            f"{chart['level']} interval; q {_p(c['q'])}; {c['verdict']}"
        )
        body.append(
            _text(x0 - 10, y + 4, str(c["condition"]), cls="bold" if flagged else "", anchor="end")
        )
        if c["lo"] is not None and c["hi"] is not None:
            body.append(
                f'<line class="{line_cls}" x1="{_n(at(float(c["lo"])))}" '
                f'x2="{_n(at(float(c["hi"])))}" '
                f'y1="{_n(y)}" y2="{_n(y)}" stroke-width="2" stroke-linecap="round">'
                f"<title>{_esc(tip)}</title></line>"
            )
        if delta is not None:
            body.append(
                f'<circle class="{fill_cls} halo" cx="{_n(at(float(delta)))}" cy="{_n(y)}" '
                f'r="4.5">'
                f"<title>{_esc(tip)}</title></circle>"
            )
        words = f"{glyph} {_signed(delta)} [{_signed(c['lo'])}, {_signed(c['hi'])}]".strip()
        body.append(_text(x1 + 12, y + 4, words, cls="" if flagged else "dimt"))
    body.append(
        _text(
            (x0 + x1) / 2,
            height - 4,
            "change in share, after minus before",
            cls="dimt",
            anchor="middle",
        )
    )
    return _svg(chart["id"], chart["title"], chart["desc"], width, height, body)


# ---------- the limits against the threshold ----------


def limits(chart: Mapping[str, Any]) -> str:
    """The smallest rise ▲ and fall ▼ one condition alone would be flagged for, against the
    threshold, written on its line; the unchanged rows, which the verdict asks about, are bold."""
    rows: Sequence[Mapping[str, Any]] = chart["cells"]
    threshold = float(chart["threshold"])
    label_w = min(max((len(str(c["condition"])) for c in rows), default=10) * 6.6 + 20, 300)
    rowh, top = 26, 40
    x0 = label_w + 10
    x1 = x0 + 500
    width = x1 + 20
    height = top + rowh * len(rows) + 60
    extent = max(
        [threshold, *(abs(float(v)) for c in rows for v in (c["rise"], c["fall"]) if v is not None)]
    )
    limit, ticks = _ticks(extent)
    at = _scale(-limit, limit, x0, x1)
    body: list[str] = []
    for t in ticks:
        body.append(
            f'<line class="axis" x1="{_n(at(t))}" x2="{_n(at(t))}" y1="{top - 8}" '
            f'y2="{height - 40}"/>'
        )
        body.append(_text(at(t), height - 26, _signed(t), cls="dimt", anchor="middle"))
    for sign in (1, -1):
        x = at(sign * threshold)
        body.append(
            f'<line class="thr" x1="{_n(x)}" x2="{_n(x)}" y1="{top - 8}" y2="{height - 40}"/>'
        )
    words = f"threshold {_look.fmt_rate(threshold)}"
    body.append(_text(at(threshold) + 4, top - 14, words))
    body.append(_text(at(-threshold) - 4, top - 14, words, anchor="end"))
    body.append(
        f'<line class="zero" x1="{_n(at(0))}" x2="{_n(at(0))}" y1="{top - 8}" y2="{height - 40}"/>'
    )
    for i, c in enumerate(rows):
        y = top + i * rowh + rowh / 2
        unchanged = c["verdict"] == "unchanged"
        rise = _f(c["rise"]) if c["rise"] is not None else str(c["rise_note"])
        fall = _f(c["fall"]) if c["fall"] is not None else str(c["fall_note"])
        tip = f"{c['condition']}: rise {rise}, fall {fall}; {c['verdict']}"
        if unchanged:
            told = "yes" if c["could_tell"] else "no"
            tip += f"; could tell a change of {_look.fmt_rate(threshold)}: {told}"
        body.append(
            _text(
                x0 - 10,
                y + 4,
                str(c["condition"]),
                cls="bold" if unchanged else "dimt",
                anchor="end",
            )
        )
        for way, sign, glyph in (("rise", 1, "▲"), ("fall", -1, "▼")):
            value = c[way]
            opacity = "1" if unchanged else "0.45"
            if value is None:
                note = str(c[f"{way}_note"] or "none")
                body.append(
                    _text(
                        at(sign * 0.02 * limit / 0.25),
                        y + 4,
                        note,
                        cls="dimt",
                        anchor="start" if sign > 0 else "end",
                    )
                )
                continue
            end = at(sign * float(value))
            body.append(
                f'<line class="{way}-line" x1="{_n(at(0))}" x2="{_n(end)}" y1="{_n(y)}" '
                f'y2="{_n(y)}" '
                f'stroke-width="2" stroke-opacity="{opacity}"><title>{_esc(tip)}</title></line>'
            )
            body.append(
                _text(
                    end,
                    y + 4,
                    glyph,
                    cls=f"{way}-text",
                    anchor="middle",
                    extra=f' fill-opacity="{opacity}"',
                )
            )
    body.append(_text(x0, height - 6, "◀ fall limit ▼", cls="dimt"))
    body.append(_text(x1, height - 6, "▲ rise limit ▶", cls="dimt", anchor="end"))
    return _svg(chart["id"], chart["title"], chart["desc"], width, height, body)


# ---------- cumulative incidence ----------


def incidence(chart: Mapping[str, Any]) -> str:
    """Each run's cumulative incidence of the event in one condition by time: the first run in
    ``--dim``, the second in ``--after``, each labelled where its line ends."""
    points: Sequence[Sequence[float]] = chart["points"]  # [t, before, after]
    horizon = float(chart["horizon"])
    unit = str(chart["unit"])
    width, height, x0, x1, y0, y1 = 560, 260, 56, 470, 20, 220
    top = max([0.1, *(float(p[1]) for p in points), *(float(p[2]) for p in points)])
    step = 0.1 if top <= 0.5 else 0.2
    ymax = math.ceil(top / step - 1e-9) * step
    at_x = _scale(0.0, horizon, x0, x1)
    at_y = _scale(0.0, ymax, y1, y0)
    body: list[str] = []
    k = 0
    while k * step <= ymax + 1e-9:
        v = round(k * step, 3)
        body.append(
            f'<line class="axis" x1="{x0}" x2="{x1}" y1="{_n(at_y(v))}" y2="{_n(at_y(v))}"/>'
        )
        body.append(_text(x0 - 8, at_y(v) + 4, _look.fmt_rate(v), cls="dimt", anchor="end"))
        k += 1
    for t in _time_ticks(horizon):
        body.append(_text(at_x(t), y1 + 16, _look.fmt_num(t), cls="dimt", anchor="middle"))
    body.append(
        f'<line class="thr" x1="{_n(at_x(horizon))}" x2="{_n(at_x(horizon))}" y1="{y0}" y2="{y1}"/>'
    )
    body.append(
        _text(
            at_x(horizon), y0 - 6, f"horizon {_look.fmt_num(horizon)}", cls="dimt", anchor="middle"
        )
    )
    ends: list[float] = []
    for arm, index, cls in (("before", 1, "before"), ("after", 2, "after")):
        d = f"M{_n(at_x(0))},{_n(at_y(0))}"
        last = 0.0
        for p in points:
            t, v = float(p[0]), float(p[index])
            if t <= 0:
                last = v
                d += f" V{_n(at_y(v))}"
                continue
            d += f" H{_n(at_x(min(t, horizon)))} V{_n(at_y(v))}"
            last = v
        d += f" H{_n(at_x(horizon))}"
        tip = f"{arm}: {_look.fmt_rate(last)} at the horizon ({chart['counts'][arm]})"
        body.append(f'<path class="{cls}" d="{d}"><title>{_esc(tip)}</title></path>')
        ends.append(last)
    for (arm, cls), last in zip((("before", "dimt"), ("after", "after-text")), ends, strict=True):
        y = at_y(last) + 4
        if arm == "after" and abs(at_y(ends[0]) - at_y(ends[1])) < 14:
            y = at_y(last) + (14 if ends[1] <= ends[0] else -6)
        body.append(_text(x1 + 8, y, f"{arm} {_look.fmt_rate(last)}", cls=cls))
    body.append(_text((x0 + x1) / 2, height + 18, f"t ({unit})", cls="dimt", anchor="middle"))
    return _svg(chart["id"], chart["title"], chart["desc"], width, height + 26, body)


def _time_ticks(horizon: float) -> list[float]:
    if horizon <= 0:
        return [0.0]
    raw = horizon / 4
    magnitude = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        step = m * magnitude
        if raw <= step:
            break
    ticks = [round(k * step, 6) for k in range(int(horizon / step) + 1)]
    if ticks[-1] < horizon - step * 0.25:
        ticks.append(horizon)
    return ticks
