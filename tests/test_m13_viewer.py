"""M13 viewer frozen tests.

Invariants V1-V40 map one test function each (several map more); V10 is withdrawn with
``--port`` and its number is retired. ``poisson_prove.viewer`` is imported lazily through
``viewer()``, so collection never touches it.

What is asserted where:

- **Rendered output first.** Every invariant that can be checked on the page, the ``--json``
  structure, or the CLI's exit code and streams is checked there. V16 builds its expectations
  from M7's number forms written from their rule (``m7_form``), never from ``report.py``; V20
  reads the provenance list off M7's public markdown, because the page shows the items with no
  marker of what was dropped. V36 and V39 build
  their expectations from M7's *public* ``to_html()`` receipt (its worst-cell tables and its
  fence blockquote) rather than from ``_worst_header``/``_worst_table_rows``/``_EPISTEMIC_FENCE``.
- **Servers.** Every server test binds ``127.0.0.1:0`` in a ``threading.Thread(daemon=True)``,
  waits on an Event set from ``on_bind`` (no fixed-duration sleep), talks to it with
  ``http.client``, and stops it with ``shutdown()`` then ``server_close()`` in a ``finally``.
  ``shutdown()`` runs on a helper thread with a join timeout, so a server whose
  ``serve_forever`` never started cannot hang the suite.
- **Non-finite floats.** Fisher's odds ratio is ``inf`` or ``nan`` in 76 of the generated
  lattice pair's 144 cells (its zero and ceiling conditions, over both events). V37 runs on that
  pair; V29 and V33 depend on the null-for-non-finite rule.

Two literals the frozen tests fix, recorded here rather than buried in a test:

- V25's hole message. V25 names "the no-comparable-data message string" without fixing
  it, and the ``hole_cause`` statement itself contains "no comparable data", so the phrase
  cannot be what is counted. ``HOLE_MESSAGE`` is the sentence these frozen tests pin.
- V36's initial selection. The page's JavaScript is the named non-observable, so the
  initially-selected cell is pinned as the ``<option selected>`` of the picker.

Also recorded: the six ``unverified`` statements are the unverified table's cells with their
Markdown code spans (backticks) removed, and the event line's wording is pinned to the
literal ``given by --event, not inferred``.

V41 pins the environment inside one closed ``<details>``: a page that rendered it anywhere else
would pass every other test.
"""

from __future__ import annotations

import datetime as dt
import http.client
import http.server
import inspect
import io
import json
import math
import os
import re
import socketserver
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from html import unescape as html_unescape
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

import lattice
import poisson_prove.cli as cli
from poisson_prove.diff import MultiDiffResult, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import MultiReport, ReportSpec, build_multi_report
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.tree import TreeResult
from poisson_prove.tree import tree as grow_tree
from conftest import quickstart_design

ROOT = Path(__file__).resolve().parents[1]
#: The generated lattice pair (``tests/lattice.py``), built once per machine and checked on use.
LATTICE_ROOT = lattice.root()
# PF3: the one copy is the packaged spec; this is its design at
# 100 replicates.
QUICKSTART = quickstart_design()

MOCK_MODULE = "poisson_prove.examples.mock_agent"
ROLLOUT = f"{MOCK_MODULE}:rollout"
PATCHED = f"{MOCK_MODULE}:rollout_patched"
V22B_SALT = "00112233445566778899aabbccddeeff"

# LS: /5 retires with the ``summary`` key.
SCHEMA = "poisson-prove.viewpair/7"
HOST = "127.0.0.1"
LATTICE_A, LATTICE_B = lattice.RUN_A, lattice.RUN_B
# PF2: every run has a name (target id up to its first "/", the UTC date of
# created_at, a letter); outputs name the lattice runs by these.
LATTICE_NAME_A, LATTICE_NAME_B = lattice.NAME_A, lattice.NAME_B
LATTICE_EVENTS = (lattice.EVENT, lattice.OTHER)
#: The page's x is the admitted knob (six groups) and its y the knob refused by default.
LATTICE_X, LATTICE_Y = lattice.Y, lattice.X
LATTICE_TITLE = "Lattice pair"
LATTICE_GAP_S = lattice.CREATED_GAP_S
LATTICE_ROWS = lattice.ROWS

CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
    "img-src data:; form-action 'none'; base-uri 'none'"
)
CONTENT_TYPE = "text/html; charset=utf-8"
ARM_KEYS = (
    "role", "run_id", "target_id", "backend", "status", "created_at", "run_salt", "t_unit",
    "poisson_prove_version", "schema_version", "retain_traces_for", "axis_types", "environment",
    "rows_stored", "tally",
)
VIEW_KEYS = ("title", "x_axis", "y_axis", "fixed", "theme", "top_n", "forest", "bound", "sign_convention")
# LS: ``mde_unchanged`` after ``honesty``.
# PF4 (PF4.20, PF4.3): each panel carries the event's ``kind`` beside ``n_safer`` and ``n_worse``
# (null when the kind is not known) and ``n_higher`` / ``n_lower`` after them, then the label of its
# per-condition share interval (``share_label``, the share caption's level and method) and the
# threshold its nothing-moved word is read against (``threshold``, the page's own copy).
# PF4.34 to PF4.47: each panel carries ``flag_rule`` after ``kind``; the order is the viewer's.
PANEL_KEYS = (
    "event", "caption", "honesty", "mde_unchanged", "kind", "flag_rule", "n_safer", "n_worse", "n_higher", "n_lower",
    "share_label", "threshold", "n_unchanged", "n_absent", "n_present",
    "x_values", "y_values", "cells", "worst_header", "worst_rows", "worst_hashes",
)
FLOAT_KINDS = {
    "rate_a": "pp1", "rate_b": "pp1", "delta": "pp1", "stat": "sig3", "p": "sig3", "q": "sig3",
    "mde": "pp0",
}
INT_FIELDS = ("n_a", "n_b", "events_a", "events_b")
SIGN_CONVENTION = "delta = rate_b - rate_a"
FORBIDDEN_KEYS = {"episode", "seed", "replicate_index", "trace", "meta"}
#: V24's one carve-out, by path (S29): the permutation seed M14's
#: ``RootResult.to_json()`` names ``seed``, carried verbatim under ``tree``.
SEED_CARVE_OUT = "tree.root.seed"
UNVERIFIED: tuple[tuple[str, str, str | None], ...] = (
    (
        "outcome_labels",
        "with_outcome and no_outcome count rows by whether the executor stored an outcome. A "
        "row whose outcome is a label such as crashed is a row with an outcome: nothing on "
        "this page reads what an outcome means, and a run every one of whose episodes ended "
        "in the same label shows no_outcome 0.",
        "B.1",
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
        "seed_identity_basis",
        "seed_identity_match is true when both manifests carry the same run_salt and every row "
        "this comparison matched stores the same seed in both arms at the same (config_hash, "
        "replicate_index). It compares the seeds that were stored, not what the target did with "
        "them.",
        None,
    ),
)
HOLE_MESSAGE = "No comparable data for this cell."
EVENT_LINE_LITERAL = "given by --event, not inferred"
INDEX_ID = "prove-cells"

FLOAT_TOKEN_RE = re.compile(r"(?<![\w.])-?\d+\.\d+(?:[eE][-+]?\d+)?|(?<![\w.])-?\d+[eE][-+]?\d+")
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)
INDEX_RE = re.compile(rf'<script[^>]*id="{INDEX_ID}"[^>]*>.*?</script>', re.S)
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.S)
STYLE_RE = re.compile(r"<style\b.*?</style>", re.S)
DETAILS_RE = re.compile(r"<details\b.*?</details>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
COMPOUND_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9-]*|\*)?((?:[.#][\w-]+|\[[^\]]+\])*)$")
QUALIFIER_RE = re.compile(r"([.#])([\w-]+)|\[([\w-]+)(?:=\"?([^\"\]]*)\"?)?\]")
VOID_TAGS = {"br", "meta", "img", "hr", "input", "link", "col", "area", "base", "wbr"}

HOSTILE = "".join(["<", "/script><img src=x onerror=", chr(34), "alert(1)", chr(34), ">&", chr(34)])

BIND_TIMEOUT_S = 15.0
STOP_TIMEOUT_S = 15.0
REQUEST_TIMEOUT_S = 15.0


# ---------- harness ----------


def viewer() -> Any:
    """``poisson_prove.viewer``, imported on demand so collection does not depend on it."""
    import poisson_prove.viewer as module

    return module


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str

    @property
    def text(self) -> str:
        return self.out + self.err

    @property
    def lines(self) -> list[str]:
        return [line for line in self.out.splitlines() if line.strip()]


def run_cli(argv: Sequence[str], stdin: StringIO | None = None) -> Result:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO() if stdin is None else stdin)
    return Result(code, out.getvalue(), err.getvalue())


def assert_clean_refusal(r: Result, code: int) -> None:
    assert r.code == code, r.text
    assert "Traceback" not in r.text, r.text


def run_id_of(root: Path, before: set[str]) -> str:
    """The one run a sweep added to the store. A sweep ends with a verdict line, not a ``run_id:``
    line, so the id is read from the store."""
    added = set(Store(root).runs()) - before
    assert len(added) == 1, added
    return added.pop()


def without_notes(err: str) -> str:
    """Stderr with the ``note:`` lines dropped: Prove's own warnings reach the CLI's stderr as
    one ``note:`` line each."""
    return "".join(line for line in err.splitlines(keepends=True) if not line.startswith("note: "))


def assert_error_then_next(err: str) -> None:
    """A refusal is one ``error:`` line, then only ``  next:`` lines."""
    lines = without_notes(err).splitlines()
    assert lines and lines[0].startswith("error: "), err
    assert all(line.startswith("  next: ") for line in lines[1:]), err


def serving_line(port: int) -> str:
    """PF2: serve's verdict line, which replaced the bare URL line."""
    return f'ok  serving "{LATTICE_NAME_A}" against "{LATTICE_NAME_B}" at http://{HOST}:{port}/ (Ctrl-C stops)'


def lattice_argv(*extra: str) -> list[str]:
    return ["--store", str(LATTICE_ROOT), "serve", LATTICE_A, LATTICE_B, *extra]


def lattice_full_argv(*extra: str) -> list[str]:
    return lattice_argv(
        "--event", LATTICE_EVENTS[0], "--event", LATTICE_EVENTS[1], "--x", LATTICE_X, "--y", LATTICE_Y,
        "--title", LATTICE_TITLE, *extra,
    )


def tripwire_serve(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace ``serve_page`` wherever the CLI could reach it with a function that raises."""
    calls: list[str] = []

    def trip(*args: Any, **kwargs: Any) -> None:
        calls.append("serve_page")
        raise AssertionError("serve_page was called; something was about to bind")

    monkeypatch.setattr(viewer(), "serve_page", trip)
    monkeypatch.setattr(cli, "serve_page", trip, raising=False)
    return calls


def stop_server(server: Any, thread: threading.Thread | None) -> None:
    """``shutdown()`` on a helper thread with a timeout, then ``server_close()``, then join.
    A ``shutdown()`` on a server whose ``serve_forever`` never ran would block forever."""
    stopper = threading.Thread(target=server.shutdown, daemon=True)
    stopper.start()
    stopper.join(STOP_TIMEOUT_S)
    server.server_close()
    if thread is not None:
        thread.join(STOP_TIMEOUT_S)


@contextmanager
def served(page: str) -> Iterator[Any]:
    """``serve_page(page)`` on a daemon thread; yields the bound server from ``on_bind``."""
    holder: list[Any] = []
    failure: list[BaseException] = []
    bound = threading.Event()

    def on_bind(server: Any) -> None:
        holder.append(server)
        bound.set()

    def run() -> None:
        try:
            viewer().serve_page(page, on_bind=on_bind)
        except BaseException as exc:  # noqa: BLE001 - reported to the test, never swallowed
            failure.append(exc)
        finally:
            bound.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    bound.wait(BIND_TIMEOUT_S)
    if not holder:
        raise RuntimeError(f"serve_page never called on_bind; failure={failure!r}")
    try:
        yield holder[0]
    finally:
        stop_server(holder[0], thread)


@dataclass
class CliServed:
    server: Any
    out: StringIO
    err: StringIO
    out_at_bind: str
    codes: list[int]
    thread: threading.Thread


@contextmanager
def cli_served(monkeypatch: pytest.MonkeyPatch, argv: Sequence[str]) -> Iterator[CliServed]:
    """``cli.main(argv)`` on a daemon thread with the real ``serve_page`` wrapped so the test
    holds the server the CLI's ``on_bind`` was handed."""
    module = viewer()
    real = module.serve_page
    holder: list[Any] = []
    snapshots: list[str] = []
    codes: list[int] = []
    bound = threading.Event()
    out, err = StringIO(), StringIO()

    def wrapped(page: str, *, on_bind: Any) -> None:
        def hook(server: Any) -> None:
            snapshots.append(out.getvalue())
            holder.append(server)
            on_bind(server)
            bound.set()

        return real(page, on_bind=hook)

    monkeypatch.setattr(module, "serve_page", wrapped)
    monkeypatch.setattr(cli, "serve_page", wrapped, raising=False)

    def run() -> None:
        try:
            codes.append(cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO()))
        finally:
            bound.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    bound.wait(BIND_TIMEOUT_S)
    if not holder:
        raise RuntimeError(f"serve never bound: codes={codes} err={err.getvalue()!r}")
    try:
        yield CliServed(holder[0], out, err, snapshots[0], codes, thread)
    finally:
        stop_server(holder[0], thread)


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes


def get(server: Any, path: str, method: str = "GET") -> Response:
    conn = http.client.HTTPConnection(HOST, server.server_address[1], timeout=REQUEST_TIMEOUT_S)
    try:
        conn.request(method, path)
        r = conn.getresponse()
        body = r.read()
        return Response(r.status, {k.lower(): v for k, v in r.getheaders()}, body)
    finally:
        conn.close()


def try_get(server: Any, path: str) -> Response | None:
    """A request the server may drop mid-handshake; ``None`` when no response came back."""
    try:
        return get(server, path)
    except (http.client.HTTPException, OSError):
        return None


# ---------- a small DOM and a small CSS matcher ----------


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None
    index: int
    children: list[Node] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(self.texts)

    def deep_text(self) -> str:
        return self.text + "".join(c.deep_text() for c in self.children)

    def ancestors(self) -> list[Node]:
        out, node = [], self.parent
        while node is not None:
            out.append(node)
            node = node.parent
        return out

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def inside(self, tag: str) -> bool:
        return any(a.tag == tag for a in self.ancestors())


class Dom(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, None, -1)
        self.current = self.root
        self.nodes: list[Node] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: v or "" for k, v in attrs}, self.current, len(self.nodes))
        self.current.children.append(node)
        self.nodes.append(node)
        if tag not in VOID_TAGS:
            self.current = node

    def handle_endtag(self, tag: str) -> None:
        node: Node | None = self.current
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.current = node.parent

    def handle_data(self, data: str) -> None:
        self.current.texts.append(data)

    def find(self, tag: str, **attrs: str) -> list[Node]:
        return [
            n for n in self.nodes
            if n.tag == tag and all(n.attrs.get(k) == v for k, v in attrs.items())
        ]

    def first_svg(self) -> Node:
        svgs = self.find("svg")
        assert svgs, "no <svg> in the page"
        return svgs[0]

    def html_style(self) -> str:
        """The page's own stylesheet: every <style> that is not inside the SVG."""
        return "".join(n.text for n in self.find("style") if not n.inside("svg"))

    def index_json(self) -> str:
        scripts = self.find("script", id=INDEX_ID)
        assert len(scripts) == 1, len(scripts)
        return scripts[0].text


def parse_html(text: str) -> Dom:
    dom = Dom()
    dom.feed(text)
    dom.close()
    return dom


def body_nodes_containing(dom: Dom, needle: str) -> list[Node]:
    return [n for n in dom.nodes if needle in n.text and not n.inside("svg") and n.tag != "svg"]


def strip_at_blocks(css: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(css):
        if css[i] != "@":
            out.append(css[i])
            i += 1
            continue
        j = css.index("{", i) + 1
        depth = 1
        while depth and j < len(css):
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        i = j
    return "".join(out)


def declarations(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in body.split(";"):
        prop, sep, value = item.partition(":")
        if sep:
            out[prop.strip().lower()] = value.strip().lower()
    return out


def css_rules(css: str) -> list[tuple[list[str], dict[str, str]]]:
    rules = []
    for block in strip_at_blocks(css).split("}"):
        if "{" not in block:
            continue
        selectors, _, body = block.partition("{")
        rules.append(([s.strip() for s in selectors.split(",") if s.strip()], declarations(body)))
    return rules


def compound_matches(node: Node, compound: str) -> bool:
    m = COMPOUND_RE.match(compound)
    if m is None:
        return False
    tag, qualifiers = m.group(1), m.group(2)
    if tag not in (None, "", "*") and tag.lower() != node.tag:
        return False
    for kind, name, attr, value in QUALIFIER_RE.findall(qualifiers):
        if kind == "." and name not in node.classes():
            return False
        if kind == "#" and node.attrs.get("id") != name:
            return False
        if attr and attr not in node.attrs:
            return False
        if attr and value and node.attrs.get(attr) != value:
            return False
    return True


def selector_matches(node: Node, selector: str) -> bool:
    compounds = [c for c in re.split(r"\s*>\s*|\s+", selector.strip()) if c]
    if not compounds or not compound_matches(node, compounds[-1]):
        return False
    ancestors = node.ancestors()
    for compound in reversed(compounds[:-1]):
        while ancestors and not compound_matches(ancestors[0], compound):
            ancestors.pop(0)
        if not ancestors:
            return False
        ancestors.pop(0)
    return True


def styles_of(node: Node, rules: list[tuple[list[str], dict[str, str]]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for selectors, decls in rules:
        if any(selector_matches(node, s) for s in selectors):
            out.update(decls)
    out.update(declarations(node.attrs.get("style", "")))
    return out


# ---------- structure helpers ----------


def walk_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from walk_keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_keys(v)


def walk_key_paths(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Every dict key at every depth as ``(dotted path, key)``. A list index is not part of the
    path, so a key under ``tree.root.units[i].config`` reads ``tree.root.units.config.<key>``."""
    if isinstance(value, dict):
        for k, v in value.items():
            here = f"{path}.{k}" if path else str(k)
            yield here, str(k)
            yield from walk_key_paths(v, here)
    elif isinstance(value, list):
        for v in value:
            yield from walk_key_paths(v, path)


def walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for v in value.values():
            yield from walk_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_strings(v)
    elif isinstance(value, str):
        yield value


def strict_loads(text: str) -> Any:
    def fail(token: str) -> Any:
        raise ValueError(f"non-JSON constant {token!r}")

    return json.loads(text, parse_constant=fail)


def index_of(page: str) -> dict[str, Any]:
    return strict_loads(parse_html(page).index_json())


def excised(page: str, *patterns: re.Pattern[str]) -> str:
    for pattern in patterns:
        page = pattern.sub("", page)
    return page


def visible_text(page: str) -> str:
    """The page with the SVG, every script and style, and the environment <details> cut out
    and tags stripped: what the renderer itself prints."""
    return html_unescape(TAG_RE.sub(" ", excised(page, SVG_RE, SCRIPT_RE, STYLE_RE, DETAILS_RE)))


def key_of(event: str, config_hash: str) -> str:
    return f"{event} {config_hash}"


def panel_by_event(structure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["event"]: p for p in structure["panels"]}


def m6_rows(multi: MultiDiffResult, event: str) -> dict[str, dict[str, Any]]:
    frame = multi.by_event[event].cells
    return {str(r["config_hash"]): r for r in frame.to_dict(orient="records")}


def no_negative_zero(text: str) -> str:
    return text[1:] if text.startswith("-") and float(text) == 0.0 else text


def m7_form(value: float, kind: str) -> str:
    """M7's number forms, written from their rule and never read from ``report.py``: ``pp1`` and
    ``pp0`` a fraction in points to one and to no decimals, ``sig3`` three significant figures
    (``0`` at zero, scientific below 0.001); a negative zero reads as zero, a non-finite value as
    ``inf``, ``-inf`` or ``nan``."""
    if kind == "pp1":
        return no_negative_zero(f"{value * 100:.1f}")
    if kind == "pp0":
        return no_negative_zero(f"{value * 100:.0f}")
    assert kind == "sig3", kind
    return "0" if value == 0 else (f"{value:.2e}" if abs(value) < 1e-3 else f"{value:.3g}")


def markdown_provenance(report: MultiReport) -> list[str]:
    """The report's provenance list as its public markdown prints it: the ``- `` lines under
    ``## Provenance``."""
    lines = report.to_markdown().splitlines()
    start = lines.index("## Provenance") + 2
    out = []
    for line in lines[start:]:
        if not line.startswith("- "):
            break
        out.append(line)
    assert out, lines[start - 2 : start + 2]
    return out


def tree_snapshot(root: Path) -> dict[str, int]:
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): p.stat().st_mtime_ns for p in root.rglob("*")}


def receipt_tables(report: MultiReport) -> list[tuple[list[str], list[list[str]]]]:
    """M7's own worst-cell tables from the public receipt, one per panel in ``events`` order,
    as (header, rows) of unescaped strings."""
    dom = parse_html(report.to_html())
    tables = []
    for table in dom.find("table"):
        header = [th.deep_text() for th in table_cells(table, "th")]
        rows = [[td.deep_text() for td in table_cells(tr, "td")] for tr in descendants(table, "tr")]
        tables.append((header, [r for r in rows if r]))
    return tables[: len(report.events)]


def descendants(node: Node, tag: str) -> list[Node]:
    out = []
    for child in node.children:
        if child.tag == tag:
            out.append(child)
        out.extend(descendants(child, tag))
    return out


def table_cells(node: Node, tag: str) -> list[Node]:
    return descendants(node, tag)


def receipt_fence(report: MultiReport) -> str:
    quotes = parse_html(report.to_html()).find("blockquote")
    assert len(quotes) == 1, len(quotes)
    return quotes[0].deep_text()


# ---------- store builders ----------


def write_run(
    store: Store,
    run_id: str,
    *,
    salt: str,
    cells: dict[tuple[str, int], int],
    n: int = 8,
    horizon: float = 10.0,
) -> None:
    """A complete synthetic run over a categorical ``task`` and a numeric ``level``:
    ``cells[(task, level)]`` of ``n`` rows end in ``fail`` at t=3, the rest in ``ok`` at the
    horizon. A (task, level) pair both runs lack is a hole in M7's grid."""
    manifest = RunManifest(
        run_id=run_id,
        target_id="synthetic@v0",
        t_unit="steps",
        run_salt=salt,
        axis_types={"task": "categorical", "level": "continuous"},
        backend="synthetic",
        environment={"note": "built by test_m13_viewer"},
    )
    store.create_run(manifest)
    records = []
    for index, ((task, level), fails) in enumerate(cells.items()):
        for k in range(n):
            episode = (
                Episode(outcome="fail", t=3.0, horizon=horizon)
                if k < fails
                else Episode(outcome="ok", t=horizon, horizon=horizon)
            )
            records.append(
                EpisodeRecord.from_episode(
                    episode,
                    run_id=run_id,
                    config={"task": task, "level": level},
                    seed=1000 * index + k,
                    replicate_index=k,
                    wall_time=0.0,
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


@dataclass(frozen=True)
class Built:
    store: Store
    a: str
    b: str
    multi: MultiDiffResult
    report: MultiReport
    tree: TreeResult
    structure: dict[str, Any]
    page: str


def counts_of(store: Store, run: str) -> tuple[int, int]:
    """``(spans, spans stamped as cut)`` over a run's stored envelopes: the count the CLI hands the builders.
    Added with truncation surfacing; restated here and never imported from another test module."""
    spans = [s for e in store.read(run, meta=False, trace="envelope")["trace"] if isinstance(e, dict) for s in e.get("spans", [])]
    return len(spans), sum(1 for s in spans if s.get("truncated") == "observation")


def build_pair(root: Path, a: str, b: str, spec: ReportSpec, events: Sequence[str]) -> Built:
    """S29: M14's tree is a required input to assembly, so the
    fixture grows it on the frames it already reads, at M14's defaults, and passes ``tree=``.
    The tree is the family's, never the ``--fix`` slice's, as the structure's tree
    is too."""
    store = Store(root)
    ma, mb = store.manifest(a), store.manifest(b)
    fa, fb = store.read(a), store.read(b)
    multi = multi_diff(fa, fb, events=list(events), manifest_a=ma, manifest_b=mb)
    nested = grow_tree(fa, fb, multi, manifest_a=ma, manifest_b=mb)
    report = build_multi_report(multi, spec, manifests=(ma, mb), observations=(counts_of(store, a), counts_of(store, b)))
    structure = viewer().build_structure(
        report, multi, tree=nested, manifest_a=ma, manifest_b=mb,
        rows_a=store.count(a), rows_b=store.count(b),
        tally_a=store.tally(a), tally_b=store.tally(b), store_root=str(root),
    )
    return Built(store, a, b, multi, report, nested, structure, viewer().render_html(structure))


# ---------- fixtures ----------


def lattice_spec(**overrides: Any) -> ReportSpec:
    base: dict[str, Any] = {"title": LATTICE_TITLE, "x_axis": LATTICE_X, "y_axis": LATTICE_Y}
    base.update(overrides)
    return ReportSpec(**base)


@pytest.fixture(scope="module")
def lattice_built(lattice_store: Store) -> Built:
    """The lattice pair over both events: the two-panel page every keying invariant needs."""
    return build_pair(LATTICE_ROOT, LATTICE_A, LATTICE_B, lattice_spec(), LATTICE_EVENTS)


@pytest.fixture(scope="module")
def lattice_dom(lattice_built: Built) -> Dom:
    return parse_html(lattice_built.page)


@pytest.fixture(scope="module")
def lattice_serve_json(lattice_store: Store) -> Result:
    """``serve --json`` on the lattice pair, both events, with ``serve_page`` tripwired."""
    with pytest.MonkeyPatch.context() as mp:
        tripwire_serve(mp)
        # PF3: the lattice's runs share a salt, so the default is the
        # paired test; V22 and V33 compare with the unpaired test's numbers, named.
        return run_cli(lattice_full_argv("--method", "fisher_bh", "--json"))


@pytest.fixture(scope="module")
def lattice_serve_json_one_event(lattice_store: Store) -> Result:
    with pytest.MonkeyPatch.context() as mp:
        tripwire_serve(mp)
        # PF3: V22 compares with diff's unpaired numbers, named.
        return run_cli(lattice_argv("--event", lattice.EVENT, "--x", LATTICE_X, "--y", LATTICE_Y, "--title", LATTICE_TITLE, "--method", "fisher_bh", "--json"))


@dataclass(frozen=True)
class MockPair:
    root: Path
    a: str
    b: str


#: PF4.30: the quickstart's design at 100 replicates with nothing
#: declared has a lone-change limit of 0.262 at base 0.400, which the default 0.20 refuses; 0.3 is
#: the smallest round value above it, and what these sweeps accept.
QUICKSTART_MAX_MDE = ("--max-mde", "0.3")


@pytest.fixture(scope="module")
def mock_pair(tmp_path_factory: pytest.TempPathFactory) -> MockPair:
    """The quickstart pair under the V22b salt: three outcomes, so the BH family changes with
    the event set. Rates are the mock's own; nothing is tuned."""
    root = tmp_path_factory.mktemp("mock-store")
    first = run_cli(["--store", str(root), "sweep", str(QUICKSTART), "--target", ROLLOUT, "--salt", V22B_SALT, "--yes",
                     *QUICKSTART_MAX_MDE])
    assert first.code == 0, first.text
    a = run_id_of(root, set())
    second = run_cli(["--store", str(root), "sweep", str(QUICKSTART), "--target", PATCHED, "--pair-with", a, "--yes",
                      *QUICKSTART_MAX_MDE])
    assert second.code == 0, second.text
    return MockPair(root, a, run_id_of(root, {a}))


def mock_serve_json(pair: MockPair, *events: str) -> Result:
    argv = ["--store", str(pair.root), "serve", pair.a, pair.b]
    for e in events:
        argv += ["--event", e]
    argv += ["--x", "tool_fail_rate", "--y", "task_id", "--json"]
    with pytest.MonkeyPatch.context() as mp:
        tripwire_serve(mp)
        return run_cli(argv)


@pytest.fixture(scope="module")
def hostile(tmp_path_factory: pytest.TempPathFactory) -> Built:
    """A 2x2 grid whose ``task`` values include a hostile string; the (plain, 2) cell is
    sampled in neither run, so the grid has a hole. Serves V25 and V28."""
    root = tmp_path_factory.mktemp("hostile-store")
    store = Store(root)
    write_run(store, "h-a", salt="h", cells={(HOSTILE, 1): 6, (HOSTILE, 2): 5, ("plain", 1): 4})
    write_run(store, "h-b", salt="h", cells={(HOSTILE, 1): 2, (HOSTILE, 2): 1, ("plain", 1): 4})
    spec = ReportSpec(title="hostile", x_axis="task", y_axis="level")
    return build_pair(root, "h-a", "h-b", spec, ["fail"])


# ---------- V1-V5: refusals, and nothing binds ----------


def test_v1_missing_event_exits_one_names_serve_and_lists_the_axes_and_events_the_runs_carry(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(lattice_argv("--x", LATTICE_X))
    # A refusal exits 1 and is one error line plus next lines; its facts stay in stderr.
    assert_clean_refusal(r, 1)
    assert_error_then_next(r.err)
    # PF2: the refusal and its next line name the two runs by name, not id.
    for fact in ("serve", "--event", LATTICE_NAME_A, LATTICE_NAME_B, lattice.X, lattice.Y, lattice.EVENT, lattice.OTHER):
        assert fact in r.err, (fact, r.err)


def test_v2_unknown_event_exits_one_with_the_known_events_sentence_and_the_verb(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(lattice_argv("--event", "nope", "--x", LATTICE_X))
    # A refusal exits 1.
    assert_clean_refusal(r, 1)
    assert 'serve: event "nope" does not appear in either run. Present: held, tripped.' in r.err, r.err


@pytest.mark.parametrize("runs", [(LATTICE_A,), (LATTICE_A, LATTICE_B, LATTICE_A)])
def test_v3_wrong_arity_exits_two_naming_the_two_run_form_and_no_single_run_mode(monkeypatch: pytest.MonkeyPatch, runs: tuple[str, ...]) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(["--store", str(LATTICE_ROOT), "serve", *runs, "--event", lattice.EVENT, "--x", LATTICE_X])
    assert_clean_refusal(r, 2)
    assert re.search(r"\bserve\b", r.err), r.err
    assert re.search(r"\bA B\b", r.err), r.err
    for offer in ("survival", "one run id", "RUN "):
        assert offer not in r.err, r.err


def test_v4_missing_x_lists_the_axes_and_events_the_runs_carry(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(lattice_argv("--event", lattice.EVENT))
    # A refusal exits 1 and is one error line plus next lines; its facts stay in stderr.
    assert_clean_refusal(r, 1)
    assert_error_then_next(r.err)
    # PF2: the refusal and its next line name the two runs by name, not id.
    for fact in ("serve", "--x", LATTICE_NAME_A, LATTICE_NAME_B, lattice.X, lattice.Y, lattice.EVENT, lattice.OTHER):
        assert fact in r.err, (fact, r.err)


def test_v4_unknown_x_exits_one_through_axis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(lattice_argv("--event", lattice.EVENT, "--x", "nope"))
    # A refusal exits 1, and an error shows no Python repr, so the value is checked bare.
    assert_clean_refusal(r, 1)
    assert "nope" in r.err and "config key" in r.err, r.err


# Each with its exit code: a refusal exits 1, a wrong command line (the run count) exits 2.
REFUSALS = [
    (lattice_argv("--x", LATTICE_X), 1),
    (lattice_argv("--event", "nope", "--x", LATTICE_X), 1),
    (["--store", str(LATTICE_ROOT), "serve", LATTICE_A, "--event", lattice.EVENT, "--x", LATTICE_X], 2),
    (["--store", str(LATTICE_ROOT), "serve", LATTICE_A, LATTICE_B, LATTICE_A, "--event", lattice.EVENT, "--x", LATTICE_X], 2),
    (lattice_argv("--event", lattice.EVENT), 1),
    (lattice_argv("--event", lattice.EVENT, "--x", "nope"), 1),
]


@pytest.mark.parametrize(("argv", "code"), REFUSALS, ids=["no-event", "unknown-event", "one-run", "three-runs", "no-x", "unknown-x"])
def test_v5_every_refusal_exits_with_its_code_without_calling_serve_page(monkeypatch: pytest.MonkeyPatch, argv: list[str], code: int) -> None:
    calls = tripwire_serve(monkeypatch)
    r = run_cli(argv)
    assert r.code == code, r.text
    assert calls == [], calls


def test_v5_json_exits_zero_without_calling_serve_page(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = tripwire_serve(monkeypatch)
    r = run_cli(lattice_full_argv("--json"))
    assert r.code == 0, r.err
    assert calls == [], calls


# ---------- V6-V9: the server ----------


def test_v6_the_server_binds_loopback(lattice_built: Built) -> None:
    with served(lattice_built.page) as server:
        assert server.server_address[0] == HOST, server.server_address


def test_v7_get_root_returns_the_page_with_the_four_headers(lattice_built: Built) -> None:
    with served(lattice_built.page) as server:
        r = get(server, "/")
    assert r.status == 200
    assert r.headers["content-type"] == CONTENT_TYPE, r.headers
    assert int(r.headers["content-length"]) == len(r.body), r.headers
    assert r.headers["cache-control"] == "no-store", r.headers
    assert r.headers["content-security-policy"] == CSP, r.headers


@pytest.mark.parametrize("path", ["/anything-else", "/../x", "/index.html"])
def test_v8_other_paths_are_404(lattice_built: Built, path: str) -> None:
    with served(lattice_built.page) as server:
        r = get(server, path)
    assert r.status == 404, (path, r.status)


def test_v8_post_is_501(lattice_built: Built) -> None:
    with served(lattice_built.page) as server:
        r = get(server, "/", method="POST")
    assert r.status == 501, r.status


def test_v8_no_file_is_opened_per_request(lattice_built: Built, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    real_open = io.open

    def recording_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    with served(lattice_built.page) as server:
        monkeypatch.setattr("builtins.open", recording_open)
        monkeypatch.setattr(io, "open", recording_open)
        first = get(server, "/")
        second = get(server, "/index.html")
        monkeypatch.undo()
    assert (first.status, second.status) == (200, 404)
    assert opened == [], opened


def test_v9_three_gets_return_the_identical_rendered_page(lattice_built: Built) -> None:
    with served(lattice_built.page) as server:
        bodies = [get(server, "/").body for _ in range(3)]
    expected = viewer().render_html(lattice_built.structure).encode("utf-8")
    assert bodies[0] == bodies[1] == bodies[2]
    assert bodies[0] == expected


# ---------- V11-V12: silence and no writes ----------


def test_v11_serving_including_a_raising_request_writes_only_the_url_line(lattice_built: Built, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    real_send_response = http.server.BaseHTTPRequestHandler.send_response

    def send_response(self: Any, code: int, message: str | None = None) -> None:
        if self.path == "/raise":
            raise RuntimeError("injected inside do_GET")
        real_send_response(self, code, message)

    monkeypatch.setattr(http.server.BaseHTTPRequestHandler, "send_response", send_response)
    capfd.readouterr()
    with cli_served(monkeypatch, lattice_full_argv()) as run:
        statuses = [get(run.server, "/").status for _ in range(3)]
        dropped = try_get(run.server, "/raise")
        missed = get(run.server, "/missing").status
    real_out, real_err = capfd.readouterr()
    assert statuses == [200, 200, 200] and missed == 404
    assert dropped is None or dropped.status >= 500, dropped
    # PF2: the first stdout line is serve's verdict line, which names both runs
    # and carries the URL; PF12: then the one line naming what it saved.
    lines = run.out.getvalue().splitlines()
    assert lines[0] == serving_line(run.server.server_address[1]) and len(lines) == 2, run.out.getvalue()
    assert re.fullmatch(r"  saved  comparison [0-9a-f]{12}", lines[1]), run.out.getvalue()
    # The unpaired-analysis warning on the lattice pair is a note line on stderr.
    assert without_notes(run.err.getvalue()) == "", run.err.getvalue()
    assert (real_out, real_err) == ("", ""), (real_out, real_err)


def test_v12_assembling_rendering_and_serving_touch_no_file(lattice_built: Built, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    monkeypatch.chdir(tmp_path)
    # PF2: report's default folder is named by the runs' names; both
    # the folder named by ids and the one named by names must stay absent.
    def slugged(name: str) -> str:
        return name.lower().replace(" ", "-").replace("/", "-")

    default_dir = tmp_path / f"prove-report-{LATTICE_A}-vs-{LATTICE_B}"
    named_dir = tmp_path / f"prove-report-{slugged(LATTICE_NAME_A)}-vs-{slugged(LATTICE_NAME_B)}"
    # PF12: serve saves the comparison it shows under the store's
    # ``.poisson/``; nothing else in the store, and nothing in the working folder, is touched.
    def store_files() -> dict[str, int]:
        return {k: v for k, v in tree_snapshot(LATTICE_ROOT).items() if not k.startswith(".poisson")}

    before = (store_files(), tree_snapshot(tmp_path), tree_snapshot(default_dir), tree_snapshot(named_dir))
    with cli_served(monkeypatch, lattice_full_argv()) as run:
        assert get(run.server, "/").status == 200
    after = (store_files(), tree_snapshot(tmp_path), tree_snapshot(default_dir), tree_snapshot(named_dir))
    assert after == before
    assert not default_dir.exists() and not named_dir.exists()


# ---------- V13: nothing outbound ----------


def test_v13_the_renderers_own_markup_references_nothing_external(lattice_built: Built) -> None:
    own = excised(lattice_built.page, SVG_RE, INDEX_RE).lower()
    for needle in ("href=", "src=", "@import", "url("):
        assert needle not in own, needle


# ---------- V16: it renders, it does not compute ----------


def test_v16_every_text_entry_is_m7s_formatting_of_the_raw_value(lattice_built: Built) -> None:
    for panel in lattice_built.structure["panels"]:
        rows = m6_rows(lattice_built.multi, panel["event"])
        assert panel["cells"], panel["event"]
        for cell in panel["cells"]:
            row = rows[cell["config_hash"]]
            for name, kind in FLOAT_KINDS.items():
                raw = float(row[name])
                assert cell["text"][name] == m7_form(raw, kind), (panel["event"], cell["config_hash"], name)
                if math.isfinite(raw):
                    assert cell[name] == raw, (name, cell[name], raw)
                else:
                    assert cell[name] is None, (name, cell[name], raw)


def test_v16_integer_fields_have_no_text_entry_and_match_m6(lattice_built: Built) -> None:
    for panel in lattice_built.structure["panels"]:
        rows = m6_rows(lattice_built.multi, panel["event"])
        for cell in panel["cells"]:
            assert set(cell["text"]) == set(FLOAT_KINDS), cell["text"].keys()
            for name in INT_FIELDS:
                assert isinstance(cell[name], int) and cell[name] == int(rows[cell["config_hash"]][name]), name


def test_v16_the_page_prints_no_float_except_through_m7s_strings(lattice_built: Built) -> None:
    # ``config_text`` values (viewpair/2) are structure strings and are already walked.
    assert lattice_built.structure["diff"] == lattice_built.report.provenance
    allowed = list(walk_strings(lattice_built.structure)) + markdown_provenance(lattice_built.report)
    allowed.append(str(lattice_built.structure["pair"]["created_at_gap_s"]))
    stray = [
        tok for tok in FLOAT_TOKEN_RE.findall(visible_text(lattice_built.page))
        if not any(tok in s for s in allowed)
    ]
    assert stray == [], stray


# ---------- V18-V21: the page carries M7's output verbatim ----------


def test_v18_heatmap_svg_is_m7s_and_the_page_embeds_it_verbatim(lattice_built: Built) -> None:
    expected = lattice_built.report.to_svg()
    assert lattice_built.structure["heatmap_svg"] == expected
    m = SVG_RE.search(lattice_built.page)
    assert m, "no <svg> in the page"
    assert m.group(0) == expected.rstrip("\n")
    assert ET.tostring(ET.fromstring(m.group(0))) == ET.tostring(ET.fromstring(expected.rstrip("\n")))


def test_v19_honesty_appears_unescaped_above_the_svg_and_uncollapsed(lattice_built: Built, lattice_dom: Dom) -> None:
    unescaped = html_unescape(lattice_built.page)
    svg_at = lattice_dom.first_svg().index
    rules = css_rules(lattice_dom.html_style())
    for panel, event in zip(lattice_built.structure["panels"], lattice_built.report.events, strict=True):
        # PF4 (PF4.20): the lattice declares no event kind, so the page names the honesty line's count in
        # direction words (the count of rises, "higher"); the library's panel keeps its old encoding.
        ev = lattice_built.multi.by_event[event]
        assert ev.kind is None
        library = lattice_built.report.panels[event].honesty
        # The library does not count a kindless event's rises as worse (n_worse is None, n_higher
        # carries the count), and the report's own honesty line names that count in direction
        # words too, as the page does.
        assert ev.n_worse is None
        assert f'"{ev.n_higher} higher"' in library and f'"{ev.n_higher} worse"' not in library
        honesty = library
        assert panel["honesty"] == honesty
        lines = honesty.splitlines()
        assert '"' in honesty, "the honesty text has no double quote to escape"
        # PF4.22: a limit is the larger of the two directions, so the lattice's two
        # complementary events have the same limits and their honesty lines can share a line of
        # text; each line is found after the line before it, which keeps the order pinned.
        positions = []
        for line in lines:
            positions.append(unescaped.find(line, positions[-1] + 1 if positions else 0))
        assert all(p >= 0 for p in positions), (event, positions)
        assert positions == sorted(positions), positions
        nodes = [n for n in body_nodes_containing(lattice_dom, lines[0]) if lines[1] in n.deep_text()]
        assert nodes, event
        node = nodes[0]
        assert node.index < svg_at, (node.index, svg_at)
        assert not node.inside("details")
        for n in (node, *node.ancestors()):
            assert "hidden" not in n.attrs, n.tag
            styles = styles_of(n, rules)
            assert styles.get("display") != "none", n.tag
            assert "max-height" not in styles, n.tag


def test_v20_provenance_items_are_m7s_lines_in_order_and_diff_is_the_provenance_dict(lattice_built: Built, lattice_dom: Dom) -> None:
    expected = [line[2:] for line in markdown_provenance(lattice_built.report)]
    lists = [[li.deep_text() for li in descendants(ul, "li")] for ul in lattice_dom.find("ul") + lattice_dom.find("ol")]
    assert expected in lists, lists
    assert lattice_built.structure["diff"] == lattice_built.report.provenance
    assert list(lattice_built.structure["diff"]) == list(lattice_built.report.provenance)


def test_v21_the_event_line_names_every_event_first_and_says_the_set_was_given(lattice_built: Built) -> None:
    unescaped = html_unescape(lattice_built.page)
    first_honesty = min(unescaped.find(p["honesty"].splitlines()[0]) for p in lattice_built.structure["panels"])
    assert first_honesty > 0
    region = unescaped[:first_honesty]
    assert "<svg" not in region
    for event in LATTICE_EVENTS:
        assert re.search(rf"\b{event}\b", region), event
    assert EVENT_LINE_LITERAL in region, region[-800:]
    assert lattice_built.report.inference_line is None
    assert lattice_built.structure["diff"]["inferred"] is False


# ---------- V22-V22b: the BH family is the event set ----------


def q_by_cell(payload: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {
        (event, str(cell["config_hash"])): float(cell["q"])
        for event, ev in payload["by_event"].items()
        for cell in ev["cells"]
    }


def structure_q(structure: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {(p["event"], c["config_hash"]): c["q"] for p in structure["panels"] for c in p["cells"]}


@pytest.mark.parametrize("events", [(lattice.EVENT,), (lattice.EVENT, lattice.OTHER)], ids=["one-event", "two-events"])
def test_v22_n_tests_and_every_q_equal_diff_format_json(lattice_serve_json: Result, lattice_serve_json_one_event: Result, events: tuple[str, ...]) -> None:
    served_json = lattice_serve_json if len(events) == 2 else lattice_serve_json_one_event
    assert served_json.code == 0, served_json.err
    argv = ["--store", str(LATTICE_ROOT), "diff", LATTICE_A, LATTICE_B]
    for e in events:
        argv += ["--event", e]
    # --json replaces --format json on diff.
    argv += ["--method", "fisher_bh", "--json"]
    diffed = run_cli(argv)
    assert diffed.code == 0, diffed.err
    payload = json.loads(diffed.out)
    structure = strict_loads(served_json.out)
    assert structure["diff"]["n_tests"] == payload["n_tests"]
    assert structure_q(structure) == q_by_cell(payload)


def test_v22b_the_family_depends_on_the_event_set_on_the_mock_pair(mock_pair: MockPair) -> None:
    one = mock_serve_json(mock_pair, "violated")
    two = mock_serve_json(mock_pair, "violated", "timeout")
    assert one.code == 0 and two.code == 0, one.err + two.err
    s1, s2 = strict_loads(one.out), strict_loads(two.out)
    # the quickstart grid is 9 cells (S23), so one event is 9 tests and two events are 18
    assert (s1["diff"]["n_tests"], s2["diff"]["n_tests"]) == (9, 18)
    q1, q2 = structure_q(s1), structure_q(s2)
    shared = [k for k in q1 if k in q2]
    assert len(shared) == 9, len(shared)
    assert max(abs(q1[k] - q2[k]) for k in shared) > 1e-9


# ---------- V23-V28: cells, keys, holes, the picker, escaping ----------


def present_hashes(report: MultiReport, event: str) -> list[str]:
    return [str(c.config_hash) for c in report.panels[event].cells if c.present]


def test_v23_panel_cells_are_the_present_grid_cells_in_m7_order_and_equal_m6_without_fix(lattice_built: Built) -> None:
    assert [p["event"] for p in lattice_built.structure["panels"]] == list(lattice_built.report.events)
    for panel in lattice_built.structure["panels"]:
        hashes = [c["config_hash"] for c in panel["cells"]]
        assert hashes == present_hashes(lattice_built.report, panel["event"])
        assert sorted(hashes) == sorted(m6_rows(lattice_built.multi, panel["event"]))


def test_v23_a_fix_slices_the_grid_against_m7_and_not_m6(lattice_built: Built, lattice_store: Store) -> None:
    gain = lattice_store.read(LATTICE_A)["config"].iloc[0][lattice.X]
    sliced = build_pair(LATTICE_ROOT, LATTICE_A, LATTICE_B, lattice_spec(y_axis=None, fixed={lattice.X: gain}), LATTICE_EVENTS)
    for panel in sliced.structure["panels"]:
        hashes = [c["config_hash"] for c in panel["cells"]]
        assert hashes == present_hashes(sliced.report, panel["event"])
        assert hashes
        assert len(hashes) < len(m6_rows(sliced.multi, panel["event"]))


def test_v24_no_episode_level_key_anywhere(lattice_built: Built) -> None:
    for panel in lattice_built.structure["panels"]:
        for cell in panel["cells"]:
            assert set(cell["text"]) == set(FLOAT_KINDS)
    # S29: the structure carries
    # M14's ``TreeResult.to_json()`` verbatim, and ``RootResult`` names the permutation seed
    # ``seed``: a knob a reader pastes back with ``--seed``, not a replicate's seed, and renaming
    # it in the structure would make the structure a lossy copy of the tree. The
    # structure walk therefore carves out that one path, by path and not by name: ``seed`` stays
    # forbidden at every other path, the other four names stay forbidden everywhere, and a user
    # config axis named ``seed`` still trips this clause under ``tree.root.units.config`` exactly
    # as it does under ``panels.cells.config``. The page-index walk has no carve-out: the
    # tree's regions add nothing to the picker's index, and this is the clause that says so.
    hits = {path for path, key in walk_key_paths(lattice_built.structure) if key in FORBIDDEN_KEYS}
    assert hits <= {SEED_CARVE_OUT}, hits
    assert not FORBIDDEN_KEYS & set(walk_keys(index_of(lattice_built.page)))


def test_v25_holes_have_no_index_entry_and_the_hole_message_appears_once(hostile: Built) -> None:
    index = index_of(hostile.page)
    assert not any(k.endswith("absent") for k in index), list(index)
    present = {key_of(p["event"], c["config_hash"]) for p in hostile.structure["panels"] for c in p["cells"]}
    assert set(index) == present
    assert any(not c.present for p in hostile.report.panels.values() for c in p.cells), "no hole in the fixture"
    assert 'data-cell="absent"' in hostile.page
    assert html_unescape(hostile.page).count(HOLE_MESSAGE) == 1


def test_v27_the_select_lists_every_cell_grouped_by_event_in_grid_order(lattice_built: Built, lattice_dom: Dom) -> None:
    selects = lattice_dom.find("select")
    assert len(selects) == 1, len(selects)
    groups = [g for g in selects[0].children if g.tag == "optgroup"]
    assert [g.attrs.get("label") for g in groups] == [*lattice_built.report.events, "holes"]
    index = index_of(lattice_built.page)
    for group, panel in zip(groups[:-1], lattice_built.structure["panels"], strict=True):
        values = [o.attrs.get("value") for o in group.children if o.tag == "option"]
        assert values == [key_of(panel["event"], c["config_hash"]) for c in panel["cells"]]
        assert all(v in index for v in values)


def test_v28_a_hostile_config_value_renders_as_text(hostile: Built) -> None:
    dom = parse_html(hostile.page)
    block = dom.index_json()
    for ch in "<>&":
        assert ch not in block, ch
    assert "</script>" not in block
    index = strict_loads(block)
    assert any(c["config"]["task"] == HOSTILE for c in index.values())
    assert not any("onerror" in n.attrs for n in dom.nodes)
    assert dom.find("img") == []
    assert any(HOSTILE in n.text for n in dom.nodes if n.tag not in ("script", "style"))


# ---------- V29-V33: determinism, the verb, the blocks, identity, --json ----------


def test_v29_two_builds_are_equal_and_two_renders_identical_with_no_timestamp(lattice_built: Built, lattice_store: Store) -> None:
    again = build_pair(LATTICE_ROOT, LATTICE_A, LATTICE_B, lattice_spec(), LATTICE_EVENTS)
    assert again.structure == lattice_built.structure
    assert viewer().render_html(lattice_built.structure) == lattice_built.page == again.page
    assert lattice_built.report.spec.generated_at is None
    assert "generated_at" not in lattice_built.structure["diff"]
    dump = json.dumps(lattice_built.structure, allow_nan=False)
    today = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
    for text in (dump, lattice_built.page):
        assert today not in text
        assert dt.date.today().isoformat() not in text
        assert not UUID_RE.search(text)


def test_v30_help_lists_serve() -> None:
    top = run_cli(["--help"])
    assert top.code == 0 and re.search(r"\bserve\b", top.out), top.out


def test_v31_the_four_unverified_entries_in_order_rendered_uncollapsed_above_the_svg(lattice_built: Built, lattice_dom: Dom) -> None:
    entries = lattice_built.structure["unverified"]
    assert [(e["id"], e["statement"], e["blocked_by"]) for e in entries] == list(UNVERIFIED)
    assert all(tuple(e) == ("id", "statement", "blocked_by") for e in entries)
    unescaped = html_unescape(lattice_built.page)
    svg_at = lattice_dom.first_svg().index
    for _, statement, _ in UNVERIFIED:
        assert statement in unescaped, statement
        nodes = body_nodes_containing(lattice_dom, statement)
        assert nodes, statement
        assert nodes[0].index < svg_at
        assert not nodes[0].inside("details")


def manifest_values(m: RunManifest) -> dict[str, Any]:
    d = m.to_dict()
    return {k: d[k] for k in ARM_KEYS if k in d}


def test_v32_both_arms_carry_the_manifest_the_row_count_and_the_role(lattice_built: Built, lattice_store: Store) -> None:
    pair = lattice_built.structure["pair"]
    for key, run_id, role in (("a", LATTICE_A, "baseline"), ("b", LATTICE_B, "candidate")):
        arm = pair[key]
        assert tuple(arm) == ARM_KEYS, tuple(arm)
        expected = manifest_values(lattice_store.manifest(run_id))
        assert {k: arm[k] for k in expected} == expected
        assert arm["rows_stored"] == lattice_store.count(run_id) == LATTICE_ROWS == 2_304
        assert arm["role"] == role
    assert lattice_built.structure["view"]["sign_convention"] == SIGN_CONVENTION
    # PF4 (PF4.11): the pair does not carry the store's path.
    assert "store_root" not in pair and str(LATTICE_ROOT) not in json.dumps(lattice_built.structure)
    assert pair["a"]["run_salt"] == pair["b"]["run_salt"] == lattice_built.structure["diff"]["run_salt"]


def test_v32_the_page_shows_both_identities(lattice_built: Built) -> None:
    unescaped = html_unescape(lattice_built.page)
    for key in ("a", "b"):
        arm = lattice_built.structure["pair"][key]
        for name in ("target_id", "status", "created_at", "run_salt", "run_id"):
            assert arm[name] in unescaped, (key, name)
    assert "baseline" in unescaped and "candidate" in unescaped
    # The lattice's gap, 0.25, is also a run of digits in its created_at stamps (and a share in the
    # cell index), so the number alone proves nothing: the page prints the gap's own sentence, with
    # the structure's number, as one element of its own, once.
    gap = lattice_built.structure["pair"]["created_at_gap_s"]
    assert gap == LATTICE_GAP_S == 0.25
    assert lattice_built.page.splitlines().count(f"<p>created_at gap, B minus A: {gap} seconds.</p>") == 1


def test_v32_created_at_gap_is_the_signed_difference_and_the_lattice_measures_0_25(lattice_built: Built, lattice_store: Store) -> None:
    a, b = lattice_store.manifest(LATTICE_A), lattice_store.manifest(LATTICE_B)
    expected = (dt.datetime.fromisoformat(b.created_at) - dt.datetime.fromisoformat(a.created_at)).total_seconds()
    assert lattice_built.structure["pair"]["created_at_gap_s"] == expected == LATTICE_GAP_S == 0.25


def test_v32_created_at_gap_is_null_when_a_timestamp_does_not_parse(lattice_built: Built, lattice_store: Store) -> None:
    from dataclasses import replace

    ma, mb = lattice_store.manifest(LATTICE_A), lattice_store.manifest(LATTICE_B)
    broken = replace(ma, created_at="not a timestamp")
    structure = viewer().build_structure(
        lattice_built.report, lattice_built.multi, tree=lattice_built.tree, manifest_a=broken, manifest_b=mb,
        rows_a=LATTICE_ROWS, rows_b=LATTICE_ROWS,
        tally_a=lattice_store.tally(LATTICE_A), tally_b=lattice_store.tally(LATTICE_B), store_root=str(LATTICE_ROOT),
    )
    assert structure["pair"]["created_at_gap_s"] is None
    assert structure["pair"]["a"]["created_at"] == "not a timestamp"


def test_v32_each_arm_carries_its_own_salt(lattice_built: Built, lattice_store: Store) -> None:
    # The lattice's arms share a salt, so a structure that copied A's salt into B would pass on the
    # fixture alone; give B a salt of its own and read both back.
    from dataclasses import replace

    ma, mb = lattice_store.manifest(LATTICE_A), lattice_store.manifest(LATTICE_B)
    other = replace(mb, run_salt="candidate-only-salt")
    structure = viewer().build_structure(
        lattice_built.report, lattice_built.multi, tree=lattice_built.tree, manifest_a=ma, manifest_b=other,
        rows_a=LATTICE_ROWS, rows_b=LATTICE_ROWS,
        tally_a=lattice_store.tally(LATTICE_A), tally_b=lattice_store.tally(LATTICE_B), store_root=str(LATTICE_ROOT),
    )
    assert structure["pair"]["a"]["run_salt"] == ma.run_salt
    assert structure["pair"]["b"]["run_salt"] == "candidate-only-salt"
    assert structure["diff"]["run_salt"] == ma.run_salt
    assert "candidate-only-salt" in html_unescape(viewer().render_html(structure))


def test_v32_the_renderer_prints_the_gap_it_is_given(lattice_built: Built) -> None:
    structure = json.loads(json.dumps(lattice_built.structure, allow_nan=False))
    original = html_unescape(viewer().render_html(structure))
    structure["pair"]["created_at_gap_s"] = 4242.5
    page = html_unescape(viewer().render_html(structure))
    assert "4242.5" in page
    # The lattice's gap, 0.25, is also a share some conditions print (and a run of digits inside its
    # timestamps), so "the real gap is printed nowhere" is read where a gap can be printed: every
    # line that moved printed the real gap and now prints the given one in its place, nothing else
    # moved, and no line that speaks of the gap still carries the real gap as a number.
    gap = str(LATTICE_GAP_S)
    token = re.compile(rf"(?<![\d.]){re.escape(gap)}(?!\d)")
    before, after = original.splitlines(), page.splitlines()
    assert len(before) == len(after)
    moved = [(o, m) for o, m in zip(before, after, strict=True) if o != m]
    assert moved and all(token.search(o) and m == token.sub("4242.5", o) for o, m in moved), moved
    assert not [line for line in after if token.search(line) and "gap" in line.lower()]


def test_v33_json_prints_the_structure_indented_and_strict_and_binds_nothing(lattice_built: Built, lattice_serve_json: Result) -> None:
    r = lattice_serve_json
    assert r.code == 0, r.err
    assert r.out.startswith('{\n  "schema": ')
    parsed = strict_loads(r.out)
    # serve --json wraps the structure with verdict and sentence after schema.
    # PF3: and with method and method_chosen right after sentence, which the
    # library's structure does not carry; they are set aside with verdict and sentence.
    assert tuple(parsed)[:5] == ("schema", "verdict", "sentence", "method", "method_chosen"), tuple(parsed)
    parsed = {k: v for k, v in parsed.items() if k not in ("verdict", "sentence", "method", "method_chosen")}
    # PF2: serve --json carries run_name beside each arm's run_id; with it set
    # aside the structure is the library's, and the names sit where they belong.
    assert {role: (parsed["pair"][role]["run_id"], parsed["pair"][role].get("run_name")) for role in ("a", "b")} == {
        "a": (LATTICE_A, LATTICE_NAME_A), "b": (LATTICE_B, LATTICE_NAME_B)
    }, parsed["pair"]
    for role in ("a", "b"):
        arm = parsed["pair"][role]
        assert tuple(arm).index("run_name") == tuple(arm).index("run_id") + 1, tuple(arm)
        del arm["run_name"]
    assert parsed == json.loads(json.dumps(lattice_built.structure, allow_nan=False))
    assert parsed["schema"] == SCHEMA


# ---------- V34-V36: n_present, the round trip, the worst tables ----------


def test_v34_n_present_counts_the_present_cells_of_the_full_grid(lattice_built: Built) -> None:
    for event in lattice_built.report.events:
        panel = lattice_built.report.panels[event]
        assert panel.n_present == sum(c.present for c in panel.cells)
        assert panel.n_present + panel.n_absent == len(panel.cells)
    for entry in lattice_built.structure["panels"]:
        assert tuple(entry) == PANEL_KEYS, tuple(entry)
        assert entry["n_present"] == lattice_built.report.panels[entry["event"]].n_present
        assert entry["n_present"] == len(entry["cells"])


def test_v35_render_html_takes_one_parameter_and_renders_a_round_tripped_structure_identically(lattice_built: Built, tmp_path: Path) -> None:
    assert len(inspect.signature(viewer().render_html).parameters) == 1
    structure_path = tmp_path / "structure.json"
    page_path = tmp_path / "page.html"
    structure_path.write_text(json.dumps(lattice_built.structure, allow_nan=False))
    # A fresh interpreter holds no MultiReport, Report, DiffResult or DataFrame: the only
    # thing render_html can read is the JSON it is handed.
    script = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from poisson_prove.viewer import render_html\n"
        "structure = json.loads(Path(sys.argv[1]).read_text())\n"
        "Path(sys.argv[2]).write_text(render_html(structure), encoding='utf-8')\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", script, str(structure_path), str(page_path)],
        capture_output=True, text=True, env={**os.environ},
    )
    assert r.returncode == 0, r.stderr
    assert page_path.read_text(encoding="utf-8") == lattice_built.page


def test_v36_worst_tables_are_m7s_and_the_first_worst_cell_is_selected(lattice_built: Built, lattice_dom: Dom) -> None:
    receipt = receipt_tables(lattice_built.report)
    for panel, (header, rows) in zip(lattice_built.structure["panels"], receipt, strict=True):
        assert panel["worst_header"] == header
        assert panel["worst_rows"] == rows
        # The flat panel's worst table gains a trailing ``interval (pp)`` column when M6 built intervals.
        axes = len(header) - (9 if header[-1] == "interval (pp)" else 8)
        by_coords = {c["coords"]: c["config_hash"] for c in panel["cells"]}
        expected_hashes = [
            by_coords[", ".join(f"{axis}={value}" for axis, value in zip(header[:axes], row[:axes], strict=True))]
            for row in rows
        ]
        assert panel["worst_hashes"] == expected_hashes
        rendered = [
            ([th.deep_text() for th in descendants(t, "th")], [[td.deep_text() for td in descendants(tr, "td")] for tr in descendants(t, "tr") if descendants(tr, "td")])
            for t in lattice_dom.find("table")
        ]
        assert (header, rows) in rendered
    first = lattice_built.structure["panels"][0]
    selected = [o for o in lattice_dom.find("option") if "selected" in o.attrs]
    assert [o.attrs.get("value") for o in selected] == [key_of(first["event"], first["worst_hashes"][0])]


# ---------- V37-V41: non-finite floats, the URL line, the page's text, the environment ----------


def test_v37_non_finite_stats_are_null_in_the_structure_and_the_dump_parses_strictly(lattice_built: Built, lattice_serve_json: Result) -> None:
    non_finite = sum(
        not math.isfinite(float(v)) for e in lattice_built.multi.events for v in lattice_built.multi.by_event[e].cells["stat"]
    )
    assert non_finite > 0, "the fixture has no non-finite stat; the invariant is not exercised"
    # the reference: the sample odds ratio (a d) / (b c) of each condition's 2x2 table, from the
    # design's counts, is inf or nan exactly when b c is 0 (the zero and ceiling conditions)
    reference = sum(
        (r["n_a"] - r["events_a"]) * r["events_b"] == 0
        for event in LATTICE_EVENTS for r in lattice.counts(event)
    )
    assert non_finite == reference == 76, (non_finite, reference)
    nulls = sum(c["stat"] is None for p in lattice_built.structure["panels"] for c in p["cells"])
    assert nulls == non_finite
    for panel in lattice_built.structure["panels"]:
        for cell in panel["cells"]:
            if cell["stat"] is None:
                assert cell["text"]["stat"] in ("inf", "-inf", "nan"), cell["text"]["stat"]
    assert lattice_serve_json.code == 0
    strict_loads(lattice_serve_json.out)
    strict_loads(parse_html(lattice_built.page).index_json())


def test_v38_the_url_line_carries_the_bound_port_and_is_written_after_on_bind(lattice_built: Built, monkeypatch: pytest.MonkeyPatch) -> None:
    with cli_served(monkeypatch, lattice_full_argv()) as run:
        port = run.server.server_address[1]
        assert isinstance(run.server, socketserver.BaseServer)
        assert run.out_at_bind == ""
        # PF2: the URL line is serve's verdict line naming both runs;
        # PF12: the line naming the saved comparison follows it.
        lines = run.out.getvalue().splitlines()
        assert lines[0] == serving_line(port) and len(lines) == 2 and re.fullmatch(r"  saved  comparison [0-9a-f]{12}", lines[1]), lines
        assert get(run.server, "/").status == 200
    assert run.codes == [0], run.codes
    # The unpaired-analysis warning on the lattice pair is a note line on stderr.
    assert without_notes(run.err.getvalue()) == ""


def test_v38_keyboard_interrupt_exits_zero_closes_the_socket_and_prints_no_traceback(lattice_built: Built, monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupted(self: Any, poll_interval: float = 0.5) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(socketserver.BaseServer, "serve_forever", interrupted)
    module = viewer()
    real = module.serve_page
    holder: list[Any] = []

    def wrapped(page: str, *, on_bind: Any) -> None:
        def hook(server: Any) -> None:
            holder.append(server)
            on_bind(server)

        return real(page, on_bind=hook)

    monkeypatch.setattr(module, "serve_page", wrapped)
    monkeypatch.setattr(cli, "serve_page", wrapped, raising=False)
    r = run_cli(lattice_full_argv())
    # Ctrl-C exits 130 and adds one stopped line after the URL line; the unpaired-analysis warning is a note line
    #.
    assert r.code == 130, r.text
    assert "Traceback" not in r.text and without_notes(r.err) == "", r.text
    lines = r.out.splitlines()
    # PF2: the URL line is serve's verdict line naming both runs.
    assert holder and lines[0] == serving_line(holder[0].server_address[1]), r.out
    # PF12: the saved comparison's line comes between the two, and once serve
    # has saved, its stopped line does not say nothing was written.
    assert len(lines) == 3 and re.fullmatch(r"  saved  comparison [0-9a-f]{12}", lines[1]) and lines[2].startswith("stopped  interrupted"), r.out
    assert "nothing was written" not in lines[2], r.out
    assert holder[0].socket.fileno() == -1


def test_v38_bind_failure_is_a_viewer_error_and_exit_one(lattice_built: Built, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(self: Any) -> None:
        raise OSError(98, "address in use (injected)")

    monkeypatch.setattr(http.server.HTTPServer, "server_bind", refuse)
    with pytest.raises(viewer().ViewerError):
        viewer().serve_page(lattice_built.page, on_bind=lambda server: None)
    r = run_cli(lattice_full_argv())
    # A refusal exits 1; the unpaired-analysis warning may come first as a note line.
    assert_clean_refusal(r, 1)
    assert r.out == "" and without_notes(r.err).startswith("error:"), r.text


def test_v39_fence_headline_captions_and_worst_rows_are_on_the_page(lattice_built: Built) -> None:
    unescaped = html_unescape(lattice_built.page)
    assert lattice_built.structure["fence"] == receipt_fence(lattice_built.report)
    assert lattice_built.structure["fence"] in unescaped
    assert lattice_built.structure["headline"] == lattice_built.report.headline
    for line in lattice_built.structure["headline"].splitlines():
        assert line in unescaped, line
    for panel, event in zip(lattice_built.structure["panels"], lattice_built.report.events, strict=True):
        # PF4 (PF4.20): the lattice declares no event kind, so the caption counts falls and rises in
        # direction words ("N lower, M higher") rather than the library panel's safer/worse.
        ev = lattice_built.multi.by_event[event]
        assert ev.kind is None
        assert panel["caption"] == f"{event}: {ev.n_lower} lower, {ev.n_higher} higher"
        assert panel["caption"] in unescaped
        for row in panel["worst_rows"]:
            for value in row:
                assert value in unescaped, value


def test_v39_trade_line_appears_when_present_and_leaves_no_empty_element_when_null(lattice_built: Built, lattice_dom: Dom) -> None:
    # The lattice's two events are complements, so every condition where tripped fell is one where held rose
    # and the pair carries a trade line: the non-null case is the fixture itself.
    trade = lattice_built.structure["trade_line"]
    assert trade is not None and trade == lattice_built.report.trade_line
    # M7 also draws the trade line inside the SVG header; the page must carry it outside too.
    holder = [n for n in lattice_dom.nodes if trade in n.text and not n.inside("svg")]
    assert holder, "the trade line is not the direct text of one element outside the SVG"
    without = json.loads(json.dumps(lattice_built.structure, allow_nan=False))
    without["trade_line"] = None
    # LS: the Summary carries the same sentence as ``summary.complement.line`` on this pair, so
    # a structure without the trade line is one without the complement too.
    without["summary"]["complement"] = None
    page = viewer().render_html(without)
    dom = parse_html(page)
    assert not [n for n in dom.nodes if trade in n.text and not n.inside("svg")]
    empties = [n for n in dom.nodes if n.tag == holder[0].tag and not n.children and not n.text.strip()]
    assert empties == [], [(n.tag, n.attrs) for n in empties]
    outside = [n for n in dom.nodes if not n.inside("svg") and n.tag != "svg"]
    assert not any("trade" in n.classes() or "trade" in n.attrs.get("id", "") for n in outside)


def test_v41_environment_renders_inside_one_closed_details_and_nowhere_else(lattice_built: Built, lattice_dom: Dom) -> None:
    details = [n for n in lattice_dom.find("details") if not n.inside("svg")]
    assert len(details) == 1, len(details)
    assert "open" not in details[0].attrs, details[0].attrs
    inside = details[0].deep_text()
    outside = html_unescape(excised(lattice_built.page, DETAILS_RE))
    sentinels = []
    for key in ("a", "b"):
        environment = lattice_built.structure["pair"][key]["environment"]
        for value in walk_strings(environment):
            assert value in inside, (key, value)
        # The one string each arm's environment does not share with the other's: both arms are
        # drawn, each its own.
        sentinel = environment["run"]
        assert sentinel not in outside, (key, sentinel)
        sentinels.append(sentinel)
    assert sentinels == [lattice.ENVIRONMENT_RUN[lattice.RUN_A], lattice.ENVIRONMENT_RUN[lattice.RUN_B]]
    assert sentinels[0] != sentinels[1] and not any(s in o for s, o in zip(sentinels, reversed(sentinels)))
