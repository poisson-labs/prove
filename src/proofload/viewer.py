"""M13: the viewer. A versioned structure for one run pair, a renderer over it, and a server.

Three halves that never reach back into each other. ``build_structure`` assembles
``proofload.viewpair/1`` -- identity, diff parameters, panels, cells and what could not be
verified -- from M6's result, M7's report and the two ``RunManifest``s. ``render_html`` turns
that structure, and nothing else, into one page. ``serve_page`` holds the page on an ephemeral
loopback port until Ctrl-C.

**It renders, it does not compute.** Every rate, delta, p, q, MDE, verdict, count and colour
bound comes from M6 and M7 already formatted by M7's own ``_fmt``; reading a stored field off a
manifest and printing it is rendering. ``build_structure`` performs exactly one arithmetic
operation, the ``created_at`` gap, computed once here so no consumer recomputes it;
``render_html`` performs none.

**Nothing outbound.** ``http.server`` is a listener on loopback, bound on request, serving one
snapshot taken before the socket exists. No client module is imported, nothing is written, and
the page's own CSP forbids the browser from fetching anything.
"""

from __future__ import annotations

import html as _html
import json
import math
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any

from proofload.report import (
    _EPISTEMIC_FENCE,
    _coord_text,
    _fmt,
    _html_style,
    _html_table,
    _provenance_lines,
    _worst_header,
    _worst_table_rows,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from proofload.diff import MultiDiffResult
    from proofload.report import Cell, MultiReport, Report, ReportSpec
    from proofload.store import RunManifest

__all__ = ["ViewerError", "build_structure", "render_html", "serve_page"]

SCHEMA = "proofload.viewpair/1"

_HOST = "127.0.0.1"
_CONTENT_TYPE = "text/html; charset=utf-8"
_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
    "img-src data:; form-action 'none'; base-uri 'none'"
)

_INDEX_ID = "proofload-cells"
_SIGN_CONVENTION = "delta = rate_b - rate_a"
_EVENT_LINE_TAIL = "given by --event, not inferred"
_HOLE_MESSAGE = "No comparable data for this cell."

# The seven float fields each cell carries raw, and the kind M7 formats each with.
_FLOAT_KINDS: dict[str, str] = {
    "rate_a": "pp1",
    "rate_b": "pp1",
    "delta": "pp1",
    "stat": "sig3",
    "p": "sig3",
    "q": "sig3",
    "mde": "pp0",
}
_INT_FIELDS = ("n_a", "n_b", "events_a", "events_b")

# What this page cannot confirm. Constant across every pair by construction: these are limits
# of the instrument, not facts about two runs. A fact about a particular pair -- a partial
# status, two different targets -- is shown as its own value in the identity block instead.
_UNVERIFIED: tuple[tuple[str, str, str | None], ...] = (
    (
        "errored_rows_per_cell",
        "n_a and n_b count rows with a non-null outcome. A cell that ran 32 replicates and "
        "errored 20 is indistinguishable here from one that ran 12. The MDE reflects the "
        "smaller n; nothing on this page says why it is small.",
        "M6 · B.6",
    ),
    (
        "hole_cause",
        "A hole is a cell with no comparable data. Whether it was never sampled, was sampled "
        "and wholly errored, or exists in one run only is not recoverable from this diff.",
        "M6 · B.6",
    ),
    (
        "run_error_totals",
        "rows_stored is every row in the store, errored rows included. How many errored is "
        "counted at run time and not persisted, so this page cannot separate them.",
        "M3/M4 · B.6",
    ),
    (
        "status_basis",
        "status is what the writing process recorded when it finished. This page does not "
        "re-derive it from the sweep's expected cell count, and for a run imported from "
        "elsewhere it could not.",
        None,
    ),
    (
        "created_at_meaning",
        "created_at is when the run's manifest was opened in this store. For a run imported "
        "from elsewhere that is the import time, not when the experiment ran.",
        None,
    ),
    (
        "paired_basis",
        "paired is true when the two manifests carry the same run_salt. Matching salts do not "
        "prove the two runs consumed their seeds identically.",
        None,
    ),
)

# The identity rows, in the order the two-column block prints them. ``environment`` is not
# here: it is the one open-ended user object on the page and goes inside <details>.
_ARM_SCALARS = (
    "role",
    "run_id",
    "target_id",
    "backend",
    "status",
    "created_at",
    "run_salt",
    "t_unit",
    "proofload_version",
    "schema_version",
    "retain_traces_for",
    "axis_types",
    "rows_stored",
)


class ViewerError(Exception):
    """The structure cannot be assembled or the address cannot be bound."""


# ---------- assembly ----------


def _axes(spec: ReportSpec) -> list[str]:
    return [spec.x_axis] + ([spec.y_axis] if spec.y_axis is not None else [])


def _coords(cell: Cell) -> tuple[str, ...]:
    """The cell's axis values as M7 renders them in a table row, for joining worst rows back."""
    return tuple(_fmt(value, "coord") for value in cell.coords)


def _finite(value: Any) -> float | None:
    """A raw float, or ``None`` when it is not finite.

    Fisher's odds ratio is ``inf`` on a zero cell and ``nan`` on a degenerate table, and both
    are Python-only tokens ``json.dumps`` would emit and no strict reader would accept. The
    number moves to ``text``, which can carry it; the raw slot carries null.
    """
    number = float(value)
    return number if math.isfinite(number) else None


def _gap_seconds(created_a: str, created_b: str) -> float | None:
    """The signed gap between two stored ``created_at`` values, or ``None`` when either is
    unreadable. The viewer is read-only: M4 validates a manifest, this renders what is stored.

    The one arithmetic operation in this half of the module. It lives here rather than in the
    renderer so that the renderer, the ``--json`` consumer and the Phase 7 MCP server read one
    number instead of implementing the subtraction three times.
    """
    try:
        first = datetime.fromisoformat(created_a)
        second = datetime.fromisoformat(created_b)
    except (TypeError, ValueError):
        return None
    return (second - first).total_seconds()


def _arm(manifest: RunManifest, role: str, rows_stored: int) -> dict[str, Any]:
    stored = manifest.to_dict()
    arm: dict[str, Any] = {"role": role}
    for name in (
        "run_id",
        "target_id",
        "backend",
        "status",
        "created_at",
        "run_salt",
        "t_unit",
        "proofload_version",
        "schema_version",
        "retain_traces_for",
        "axis_types",
        "environment",
    ):
        arm[name] = stored[name]
    arm["rows_stored"] = int(rows_stored)
    return arm


def _cell(spec: ReportSpec, cell: Cell, row: dict[str, Any]) -> dict[str, Any]:
    """One present cell: M6's own fields raw, plus M7's rendering of each float.

    Both, never one alone. The raw float is canonical -- a consumer that has to parse ``"37.5"``
    back into a number has lost the units and three significant figures. ``text`` is M7's
    rendering of that same float, so no second formatter exists to drift from it.
    """
    out: dict[str, Any] = {
        "coords": _coord_text(spec, cell),
        "config_hash": str(cell.config_hash),
    }
    for name in _INT_FIELDS:
        out[name] = int(row[name])
    for name in _FLOAT_KINDS:
        out[name] = _finite(row[name])
    out["verdict"] = str(row["verdict"])
    out["config"] = row["config"]
    out["text"] = {name: _fmt(row[name], kind) for name, kind in _FLOAT_KINDS.items()}
    return out


def _panel(
    spec: ReportSpec, event: str, panel: Report, rows: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    present = [c for c in panel.cells if c.present]
    cells = [_cell(spec, c, rows[str(c.config_hash)]) for c in present]
    header = _worst_header(panel)
    worst_rows = _worst_table_rows(panel)
    axes = _axes(spec)
    by_coords = {_coords(c): str(c.config_hash) for c in present}
    return {
        "event": event,
        "caption": panel.headline,
        "honesty": panel.honesty,
        "n_safer": int(panel.n_safer),
        "n_worse": int(panel.n_worse),
        "n_unchanged": int(panel.n_unchanged),
        "n_absent": int(panel.n_absent),
        "n_present": int(panel.n_present),
        "x_values": [_fmt(v, "coord") for v in panel.x_values],
        "y_values": [_fmt(v, "coord") for v in panel.y_values],
        "cells": cells,
        "worst_header": header,
        "worst_rows": worst_rows,
        "worst_hashes": [by_coords[tuple(row[: len(axes)])] for row in worst_rows],
    }


def build_structure(
    report: MultiReport,
    multi: MultiDiffResult,
    *,
    manifest_a: RunManifest,
    manifest_b: RunManifest,
    rows_a: int,
    rows_b: int,
    store_root: str,
) -> dict[str, Any]:
    """The pair as data, per the spec's section 3.2.

    Pure: equal inputs give an equal dict. Reads no file, opens no socket, writes nothing, and
    derives no statistic -- every number here is already a field on M6's result, M7's report or
    a stored manifest. The single exception is ``pair.created_at_gap_s``.
    """
    spec = report.spec
    panels = []
    for event in report.events:
        rows = {
            str(record["config_hash"]): record
            for record in multi.by_event[event].cells.to_dict(orient="records")
        }
        panels.append(_panel(spec, event, report.panels[event], rows))
    return {
        "schema": SCHEMA,
        "pair": {
            "store_root": store_root,
            "created_at_gap_s": _gap_seconds(manifest_a.created_at, manifest_b.created_at),
            "a": _arm(manifest_a, "baseline", rows_a),
            "b": _arm(manifest_b, "candidate", rows_b),
        },
        "diff": dict(report.provenance),
        "view": {
            "title": spec.title,
            "x_axis": spec.x_axis,
            "y_axis": spec.y_axis,
            "fixed": dict(spec.fixed),
            "theme": spec.theme,
            "top_n": int(spec.top_n),
            "forest": spec.forest,
            "bound": float(report.bound),
            "sign_convention": _SIGN_CONVENTION,
        },
        "headline": report.headline,
        "trade_line": report.trade_line,
        "fence": _EPISTEMIC_FENCE,
        "panels": panels,
        "unverified": [
            {"id": name, "statement": statement, "blocked_by": blocked}
            for name, statement, blocked in _UNVERIFIED
        ],
        "heatmap_svg": report.to_svg(),
    }


# ---------- rendering ----------


def _lines_html(text: str) -> str:
    return "<br>".join(_html.escape(line) for line in text.splitlines())


def _scalar_text(value: Any) -> str:
    """A stored manifest value as one line. Nothing is parsed and nothing is derived."""
    if value is None:
        return "none"
    if isinstance(value, dict):
        return ", ".join(f"{key}={item}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _env_rows(value: Any, prefix: str) -> list[list[str]]:
    """``environment`` flattened to dotted key / value rows. Carried verbatim: nothing is read
    out of it, because a local run's shape and an imported run's shape have no key in common."""
    rows: list[list[str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(_env_rows(item, f"{prefix}.{key}" if prefix else str(key)))
        return rows
    if isinstance(value, list):
        for item in value:
            rows.extend(_env_rows(item, prefix))
        return rows
    rows.append([prefix, str(value)])
    return rows


def _identity_html(pair: Mapping[str, Any]) -> list[str]:
    a, b = pair["a"], pair["b"]
    rows = [[name, _scalar_text(a[name]), _scalar_text(b[name])] for name in _ARM_SCALARS]
    gap = pair["created_at_gap_s"]
    parts = [
        "<h2>Run pair</h2>",
        _html_table(["field", "A (baseline)", "B (candidate)"], rows),
        f"<p>created_at gap, B minus A: {_html.escape(_scalar_text(gap))} seconds. "
        f"Store root: {_html.escape(str(pair['store_root']))}.</p>",
        f"<p>Sign convention: {_html.escape(_SIGN_CONVENTION)}.</p>",
        "<details><summary>environment, both arms (the runs' own configuration)</summary>",
    ]
    for key, role in (("a", "A (baseline)"), ("b", "B (candidate)")):
        parts.append(f"<h3>{_html.escape(role)}</h3>")
        parts.append(_html_table(["key", "value"], _env_rows(pair[key]["environment"], "")))
    parts.append("</details>")
    return parts


def _unverified_html(entries: Sequence[Mapping[str, Any]]) -> list[str]:
    """The block naming what the page could not verify. Never collapsible and never below the
    figure: a page that cannot say it is unable to confirm the two runs are comparable renders
    a confidently wrong comparison in silence."""
    items = []
    for entry in entries:
        blocked = entry["blocked_by"]
        tail = (
            f" (closed by {_html.escape(str(blocked))})"
            if blocked is not None
            else " (nothing on the roadmap closes this)"
        )
        items.append(
            f"<li><strong>{_html.escape(str(entry['id']))}</strong> "
            f"{_html.escape(str(entry['statement']))}{tail}</li>"
        )
    return ["<h2>Not verified</h2>", "<ul>", *items, "</ul>"]


def _cell_rows(cell: Mapping[str, Any]) -> list[list[str]]:
    """The drill-down's own table. Every float goes through the structure's ``text``; the raw
    floats and the full config are in the index, where the page's script reads them."""
    text = cell["text"]
    return [
        ["coords", str(cell["coords"])],
        ["config_hash", str(cell["config_hash"])],
        ["n (a/b)", f"{cell['n_a']}/{cell['n_b']}"],
        ["events (a/b)", f"{cell['events_a']}/{cell['events_b']}"],
        ["rate_a (pp)", text["rate_a"]],
        ["rate_b (pp)", text["rate_b"]],
        ["delta (pp)", text["delta"]],
        ["stat", text["stat"]],
        ["p", text["p"]],
        ["q", text["q"]],
        ["MDE (pp)", text["mde"]],
        ["verdict", str(cell["verdict"])],
    ]


def _index_key(event: str, config_hash: str) -> str:
    return f"{event} {config_hash}"


def _script_json(payload: Any) -> str:
    """``json.dumps`` does not escape the less-than character, so a config value carrying a
    closing script tag would close the block. The three markup characters become their
    backslash-u escapes, which JSON reads back as themselves."""
    dump = json.dumps(payload, sort_keys=False, allow_nan=False)
    return dump.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def _picker_html(panels: Sequence[Mapping[str, Any]], selected: str) -> list[str]:
    parts = ['<select id="pl-picker">']
    for panel in panels:
        parts.append(f'<optgroup label="{_html.escape(str(panel["event"]))}">')
        for cell in panel["cells"]:
            key = _index_key(str(panel["event"]), str(cell["config_hash"]))
            mark = " selected" if key == selected else ""
            parts.append(
                f'<option value="{_html.escape(key)}"{mark}>'
                f'{_html.escape(str(cell["coords"]))}</option>'
            )
        parts.append("</optgroup>")
    parts.append("</select>")
    return parts


_SCRIPT = """
(function () {
  var block = document.getElementById("PL_INDEX_ID");
  var target = document.getElementById("pl-cell");
  var picker = document.getElementById("pl-picker");
  var figure = document.getElementById("pl-figure");
  if (!block || !target || !picker) { return; }
  var index = JSON.parse(block.textContent);
  var missing = "PL_HOLE_MESSAGE";
  var order = ["coords", "config_hash", "n_a", "n_b", "events_a", "events_b",
               "rate_a", "rate_b", "delta", "stat", "p", "q", "mde", "verdict"];
  function row(table, label, value) {
    var tr = document.createElement("tr");
    var th = document.createElement("td");
    var td = document.createElement("td");
    th.textContent = label;
    td.textContent = value === null ? "none" : String(value);
    tr.appendChild(th);
    tr.appendChild(td);
    table.appendChild(tr);
  }
  function mark(key) {
    var chosen = document.querySelectorAll("[data-selected]");
    for (var i = 0; i < chosen.length; i++) { chosen[i].removeAttribute("data-selected"); }
    var panels = document.querySelectorAll("[data-panel]");
    for (var p = 0; p < panels.length; p++) {
      var name = panels[p].getAttribute("data-panel");
      var cells = panels[p].querySelectorAll("[data-cell]");
      for (var c = 0; c < cells.length; c++) {
        if (name + " " + cells[c].getAttribute("data-cell") === key) {
          cells[c].setAttribute("data-selected", "1");
        }
      }
    }
  }
  function show(key) {
    while (target.firstChild) { target.removeChild(target.firstChild); }
    var cell = index[key];
    if (!cell) {
      target.textContent = missing;
      mark(key);
      return;
    }
    var table = document.createElement("table");
    for (var i = 0; i < order.length; i++) {
      var name = order[i];
      var shown = cell.text && name in cell.text ? cell.text[name] : cell[name];
      row(table, name, shown);
    }
    var config = cell.config || {};
    for (var key2 in config) {
      if (Object.prototype.hasOwnProperty.call(config, key2)) {
        row(table, "config." + key2, config[key2]);
      }
    }
    target.appendChild(table);
    mark(key);
  }
  picker.addEventListener("change", function () { show(picker.value); });
  if (figure) {
    figure.addEventListener("click", function (ev) {
      var hit = ev.target.closest ? ev.target.closest("[data-cell]") : null;
      var panel = ev.target.closest ? ev.target.closest("[data-panel]") : null;
      if (!hit || !panel) { return; }
      var key = panel.getAttribute("data-panel") + " " + hit.getAttribute("data-cell");
      picker.value = key;
      show(key);
    });
  }
  show(picker.value);
})();
"""

# Layout only: the base sheet is M7's own, and no rule here sets a colour.
#
# ``pointer-events`` is load-bearing and grid-shaped. M7 draws the significance glyph and the
# trade notch in later sibling groups, painted over the cell rect but not descended from it, so
# without this a click on a significant cell resolves to no cell at all -- and those are the
# cells a reader clicks first. ``[data-mde]`` is deliberately absent: it exists only in forest
# mode, where it is a child of ``<g data-cell>`` and is the widest target in the row.
_LAYOUT = (
    "[data-sig],svg path{pointer-events:none}"
    "[data-cell]{cursor:pointer}"
    "[data-selected]{outline:2px solid currentColor;outline-offset:1px}"
    "details{margin:12px 0}"
    "summary{cursor:pointer}"
    "select{max-width:100%;font-family:inherit;font-size:inherit}"
    "#pl-cell table{margin:8px 0}"
)


def render_html(structure: Mapping[str, Any]) -> str:
    """The whole document as one string, from the structure alone.

    Never sees a ``MultiReport``, a ``DiffResult`` or a ``DataFrame``, and derives nothing: the
    ``created_at`` gap it prints was computed once during assembly. The honesty and unverified
    blocks sit above the figure -- a real sweep's heatmap is taller than a screen, so below it
    is below the fold -- and the only collapsible thing on the page is the runs' own
    ``environment``.
    """
    schema = structure.get("schema")
    if schema != SCHEMA:
        raise ViewerError(
            f"unknown structure schema {schema!r}; this renderer reads {SCHEMA!r} only and "
            "does not attempt a best-effort render"
        )
    pair = structure["pair"]
    view = structure["view"]
    diff = structure["diff"]
    panels = structure["panels"]
    title = str(view["title"])

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{_html.escape(title)}</title>",
        f"<style>{_html_style(view['theme'])}{_LAYOUT}</style>",
        "</head>",
        "<body>",
        f"<h1>{_html.escape(title)}</h1>",
    ]
    parts.extend(_identity_html(pair))

    events = ", ".join(str(name) for name in diff["events"])
    parts.append("<h2>Events</h2>")
    parts.append(f"<p>Events: {_html.escape(events)} ({_EVENT_LINE_TAIL}).</p>")

    parts.append("<h2>Result</h2>")
    parts.append(f"<p>{_lines_html(str(structure['headline']))}</p>")
    if structure["trade_line"] is not None:
        parts.append(f"<p>{_html.escape(str(structure['trade_line']))}</p>")

    parts.append("<h2>Honesty</h2>")
    for panel in panels:
        parts.append(f"<h3>{_html.escape(str(panel['event']))}</h3>")
        parts.append(f"<p>{_lines_html(str(panel['honesty']))}</p>")

    parts.extend(_unverified_html(structure["unverified"]))

    svg = str(structure["heatmap_svg"]).rstrip("\n")
    parts.append("<h2>Heatmap</h2>")
    parts.append(f'<div id="pl-figure" class="figure">{svg}</div>')

    index = {}
    for panel in panels:
        for cell in panel["cells"]:
            index[_index_key(str(panel["event"]), str(cell["config_hash"]))] = cell
    first = panels[0]
    selected = _index_key(str(first["event"]), str(first["worst_hashes"][0]))
    parts.append("<h2>Cell</h2>")
    parts.append('<div class="picker">')
    parts.extend(_picker_html(panels, selected))
    parts.append("</div>")
    opened = _html_table(["field", "value"], _cell_rows(index[selected]))
    parts.append(f'<div id="pl-cell">{opened}</div>')
    parts.append(
        f'<script type="application/json" id="{_INDEX_ID}">{_script_json(index)}</script>'
    )
    script = _SCRIPT.replace("PL_INDEX_ID", _INDEX_ID).replace("PL_HOLE_MESSAGE", _HOLE_MESSAGE)
    parts.append(f"<script>{script}</script>")

    parts.append("<h2>Worst cells</h2>")
    for panel in panels:
        parts.append(f"<h3>{_html.escape(str(panel['event']))}</h3>")
        parts.append(_html_table(panel["worst_header"], panel["worst_rows"]))

    parts.append(f"<blockquote>{_html.escape(str(structure['fence']))}</blockquote>")
    parts.append("<h2>Provenance</h2>")
    items = "".join(f"<li>{_html.escape(line[2:])}</li>" for line in _provenance_lines(diff))
    parts.append(f"<ul>{items}</ul>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"


# ---------- the server ----------


class _Server(ThreadingHTTPServer):
    """A loopback listener that says nothing.

    ``handle_error`` matters more than ``log_message``: ``socketserver``'s default prints a
    separator, the client address and a full traceback to the real ``sys.stderr`` on any
    exception inside a handler, which is the loudest stream this process has and the one every
    other verb routes through its given ``_IO``. Both are silenced.
    """

    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        return


def _handler(body: bytes) -> type[BaseHTTPRequestHandler]:
    """One handler class closing over the page bytes.

    The page is a snapshot taken before the socket existed and is never re-read: if the store
    gains rows while the server runs, this page keeps showing what it was built from. That is
    the read-only guarantee working, which is why both arms' ``status`` is on the page.
    """

    class _Page(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server's own dispatch name
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", _CONTENT_TYPE)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", _CSP)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
            return

    return _Page


def serve_page(page: str, *, on_bind: Callable[[HTTPServer], None]) -> None:
    """Bind an ephemeral port on loopback and serve ``page`` at ``GET /`` until Ctrl-C.

    ``on_bind`` gets the bound server, not the port: the CLI wants ``server_address[1]`` for
    its URL line and a test wants ``shutdown()``, and handing back an ``int`` gives the test
    nothing. It is required rather than optional -- an ephemeral port nobody is told about is
    a page nobody can open.
    """
    body = page.encode("utf-8")
    try:
        server = _Server((_HOST, 0), _handler(body))
    except OSError as exc:
        raise ViewerError(f"cannot bind a loopback port: {exc}") from exc
    try:
        on_bind(server)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
