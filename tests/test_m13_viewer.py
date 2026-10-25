"""M13 viewer oracle, generated from section 4 of the M13 spec before the viewer is built.

Invariants V1-V40 map one test function each (several map more); V10 is withdrawn with
``--port`` and its number is retired. ``proofload.viewer`` does not exist when this file is
written, so it is imported lazily through ``viewer()``; collection never touches it.

What is asserted where:

- **Rendered output first.** Every invariant that can be checked on the page, the ``--json``
  structure, or the CLI's exit code and streams is checked there. Two invariants build their
  expectations from M7's private helpers because the rendered form is lossy: V16 (``_fmt`` --
  comparing a formatted string to a hand-typed literal re-types the formatter, the defect V17
  bans) and V20 (``_provenance_lines`` -- the page shows the items with no marker of what was
  dropped). V17 is a source grep with no rendered form and imports nothing. V36 and V39 build
  their expectations from M7's *public* ``to_html()`` receipt (its worst-cell tables and its
  fence blockquote) rather than from ``_worst_header``/``_worst_table_rows``/``_EPISTEMIC_FENCE``.
- **Servers.** Every server test binds ``127.0.0.1:0`` in a ``threading.Thread(daemon=True)``,
  waits on an Event set from ``on_bind`` (no fixed-duration sleep), talks to it with
  ``http.client``, and stops it with ``shutdown()`` then ``server_close()`` in a ``finally``.
  ``shutdown()`` runs on a helper thread with a join timeout, so a server whose
  ``serve_forever`` never started cannot hang the suite.
- **Tree reads.** V6, V14, V17 and V35 resolve ``viewer.py`` through ``proofload.__file__``,
  never ``Path.cwd()``, so the shadow-shim run under ``PYTHONPATH`` reads the shim.
- **Non-finite floats.** Fisher's odds ratio is ``inf`` or ``nan`` in 569 of the Go1 pair's
  800 cells. V37 runs on that pair; V29 and V33 depend on the null-for-non-finite rule.

Two literals the spec leaves to the oracle, recorded here rather than buried in a test:

- V25's hole message. The spec says "the no-comparable-data message string" without fixing
  it, and the ``hole_cause`` statement itself contains "no comparable data", so the phrase
  cannot be what is counted. ``HOLE_MESSAGE`` is the sentence this oracle pins.
- V36's initial selection. The page's JavaScript is the named non-observable, so the
  initially-selected cell is pinned as the ``<option selected>`` of the picker.

Also recorded: the six ``unverified`` statements are the spec's table cells with their
Markdown code spans (backticks) removed, and the event line's wording is pinned to the
literal ``given by --event, not inferred`` (section 3.4, fixed at close-out).

V41 (environment inside a closed ``<details>``) was added at close-out after the mutation
pass rendered it outside and nothing caught it.
"""

from __future__ import annotations

import ast
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

import poisson_prove
import poisson_prove.cli as cli
from poisson_prove.diff import MultiDiffResult, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import MultiReport, ReportSpec, build_multi_report
from poisson_prove.store import EpisodeRecord, RunManifest, Store
from poisson_prove.tree import TreeResult
from poisson_prove.tree import tree as grow_tree
from conftest import quickstart_design

ROOT = Path(__file__).resolve().parents[1]
GO1_ROOT = ROOT / "tests" / "fixtures" / "go1"
# PF3 (spec sections 8.8 and 14): the one copy is the packaged spec; this is its design at
# the 100 replicates this file was frozen at.
QUICKSTART = quickstart_design()
S0_TEST_SOURCE = Path(__file__).resolve().parent / "test_s0_scaffold.py"
TESTS_DIR = Path(__file__).resolve().parent

MOCK_MODULE = "poisson_prove.examples.mock_agent"
ROLLOUT = f"{MOCK_MODULE}:rollout"
PATCHED = f"{MOCK_MODULE}:rollout_patched"
V22B_SALT = "00112233445566778899aabbccddeeff"

# LS retrofit, 2026-09-22 (local serve pass, Phase A): /5 retires with the ``summary`` key.
SCHEMA = "poisson-prove.viewpair/7"
RETIRED_SCHEMA = "proofload.viewpair/3"
HOST = "127.0.0.1"
GO1_A, GO1_B = "go1-v0", "go1-v1"
# PF2 (spec section 4.3): every run has a name (target id up to its first "/", the UTC date of
# created_at, a letter); outputs name the Go1 runs by these.
GO1_NAME_A = "go1-g2-converged@20260813T155006Z 2026-09-03 a"
GO1_NAME_B = "go1-g2-v1@20260818T230622Z-v1 2026-09-03 a"
GO1_EVENTS = ("fell", "survived")
GO1_X, GO1_Y = "push_pct_bw", "mu"
GO1_TITLE = "Go1 pair"
GO1_GAP_S = 0.112099
GO1_ROWS = 12_800

CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
    "img-src data:; form-action 'none'; base-uri 'none'"
)
CONTENT_TYPE = "text/html; charset=utf-8"
# LS retrofit, 2026-09-22 (local serve pass, Phase A): ``summary`` eighth.
TOP_LEVEL_KEYS = (
    "schema", "pair", "diff", "holes", "view", "headline", "trade_line", "summary", "fence", "panels",
    "intervals", "tree", "unverified", "heatmap_svg",
)
ARM_KEYS = (
    "role", "run_id", "target_id", "backend", "status", "created_at", "run_salt", "t_unit",
    "poisson_prove_version", "schema_version", "retain_traces_for", "axis_types", "environment",
    "rows_stored", "tally",
)
VIEW_KEYS = ("title", "x_axis", "y_axis", "fixed", "theme", "top_n", "forest", "bound", "sign_convention")
# LS retrofit, 2026-09-22 (local serve pass, Phase A): ``mde_unchanged`` after ``honesty`` (spec LS D4, section 3.5).
# PF4 (PF4.20, PF4.3): each panel carries the event's ``kind`` beside ``n_safer`` and ``n_worse``
# (null when the kind is not known) and ``n_higher`` / ``n_lower`` after them, then the label of its
# per-condition share interval (``share_label``, the share caption's level and method) and the
# threshold section 8.4 reads its nothing-moved word against (``threshold``, the page's own copy).
# PF4 re-freeze (PF4.34 to PF4.47): each panel gains ``flag_rule`` after ``kind``; the order is the build's.
PANEL_KEYS = (
    "event", "caption", "honesty", "mde_unchanged", "kind", "flag_rule", "n_safer", "n_worse", "n_higher", "n_lower",
    "share_label", "threshold", "n_unchanged", "n_absent", "n_present",
    "x_values", "y_values", "cells", "worst_header", "worst_rows", "worst_hashes",
)
# PF4 (PF4.13, PF4.14, PF4.15, PF4.3): each cell gains ``direction``, ``direction_note``, ``pairs``
# and ``mde_note`` after ``verdict``, then each arm's share object and whether it differs from the
# arm's rate.
CELL_KEYS = (
    "coords", "config_hash", "n_a", "n_b", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b",
    "events_a", "events_b", "rate_a", "rate_b", "delta", "stat", "p", "q", "mde", "verdict",
    "direction", "direction_note", "pairs", "mde_note",
    # PF4 re-freeze (PF4.34 to PF4.47): each cell gains Holm's q and flag, the limit keys, the
    # competing shift and the interval, after mde_note; the order is the build's.
    "q_holm", "holm", "mde_rise", "mde_fall", "mde_rise_note", "mde_fall_note", "mde_test", "mde_basis",
    "mde_level", "mde_family", "mde_power", "mde_anchor", "mde_hr", "p_min", "flaggable", "mde_moves_with",
    "mde_rise_verdict", "mde_fall_verdict", "competing_shift", "ci_lo", "ci_hi", "ci_level", "ci_method",
    "share_a", "share_b", "share_a_differs", "share_b_differs",
    "config", "config_text", "text",
)
FLOAT_KINDS = {
    "rate_a": "pp1", "rate_b": "pp1", "delta": "pp1", "stat": "sig3", "p": "sig3", "q": "sig3",
    "mde": "pp0",
}
INT_FIELDS = ("n_a", "n_b", "events_a", "events_b")
SIGN_CONVENTION = "delta = rate_b - rate_a"
FORBIDDEN_KEYS = {"episode", "seed", "replicate_index", "trace", "meta"}
SERVE_FLAGS = {
    "--event", "--x", "--y", "--fix", "--method", "--q", "--theme", "--top-n", "--forest",
    "--title", "--json",
    "--permutations", "--seed", "--by", "--max-group-mde", "--depth",
    # Every verb also takes the tool's own options after it (spec section 5.4).
    "--store", "--plain", "--debug",
}
#: V24's one carve-out, by path (spec S29 section 0.3): the permutation seed M14's frozen
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

CLIENT_BAN = {"urllib", "requests", "httpx", "socket"}
SERVER_ALLOWANCE = "http.server"
ASSEMBLY_HELPERS = {"_fmt", "_coord_text", "_worst_header", "_worst_table_rows", "_EPISTEMIC_FENCE"}
RENDER_HELPERS = {"_html_style", "_html_table", "_provenance_lines"}
FENCE_PHRASES = (
    "not formal verification", "under a stated test envelope", "were not tested",
    "at or above the reported MDE",
)
PINNED_REPORT_TYPES = {"Report", "MultiReport", "ReportSpec", "Cell", "SurvivalReport"}

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
TIMES_100_RE = re.compile(r"\*\s*100\b")
FLOAT_SPEC_RE = re.compile(r":\.\d")
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
    """``proofload.viewer``, imported on demand so collection does not depend on it."""
    import poisson_prove.viewer as module

    return module


def viewer_source() -> str:
    return (Path(poisson_prove.__file__).resolve().parent / "viewer.py").read_text()


def core_modules() -> list[Path]:
    return sorted(Path(poisson_prove.__file__).resolve().parent.rglob("*.py"))


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
    """The one run a sweep added to the store. A sweep no longer ends with a ``run_id:`` line; it
    ends with a verdict line (spec section 5.3), so the id is read from the store."""
    added = set(Store(root).runs()) - before
    assert len(added) == 1, added
    return added.pop()


def without_notes(err: str) -> str:
    """Stderr with the ``note:`` lines dropped: Prove's own warnings now reach the CLI's stderr as
    one ``note:`` line each (spec section 5.4)."""
    return "".join(line for line in err.splitlines(keepends=True) if not line.startswith("note: "))


def assert_error_then_next(err: str) -> None:
    """A refusal is one ``error:`` line, then only ``  next:`` lines (spec section 5.4)."""
    lines = without_notes(err).splitlines()
    assert lines and lines[0].startswith("error: "), err
    assert all(line.startswith("  next: ") for line in lines[1:]), err


def serving_line(port: int) -> str:
    """PF2 (spec section 5.3): serve's verdict line, which replaced the bare URL line."""
    return f'ok  serving "{GO1_NAME_A}" against "{GO1_NAME_B}" at http://{HOST}:{port}/ (Ctrl-C stops)'


def go1_argv(*extra: str) -> list[str]:
    return ["--store", str(GO1_ROOT), "serve", GO1_A, GO1_B, *extra]


def go1_full_argv(*extra: str) -> list[str]:
    return go1_argv(
        "--event", GO1_EVENTS[0], "--event", GO1_EVENTS[1], "--x", GO1_X, "--y", GO1_Y,
        "--title", GO1_TITLE, *extra,
    )


def option_flags(help_text: str) -> set[str]:
    """The long flags an argparse help text lists as option entries: a line indented by exactly
    two spaces that begins with ``--``. The prose of a help string is not read."""
    return {m.group(1) for line in help_text.splitlines() if (m := re.match(r"^  (--[a-z][a-z-]*)", line))}


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


def last_compound_tag(selector: str) -> str | None:
    compounds = [c for c in re.split(r"\s*>\s*|\s+", selector.strip()) if c]
    m = COMPOUND_RE.match(compounds[-1]) if compounds else None
    return m.group(1) if m else None


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


# ---------- ast helpers (restated; never imported across test modules) ----------


def imported_modules(source: str) -> set[str]:
    """Every module name an ``import`` or ``from ... import`` names, as a FULL dotted path.
    ``from http import server`` yields ``http.server``: the dotted name exists only when
    ``node.module`` is joined with each alias, which is what a substring grep and a
    top-level-only walk both miss."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def names_server(names: set[str]) -> bool:
    return any(n == SERVER_ALLOWANCE or n.startswith(SERVER_ALLOWANCE + ".") for n in names)


def network_violations(py: Path) -> list[str]:
    names = imported_modules(py.read_text())
    bad = sorted(n for n in names if n.split(".")[0] in CLIENT_BAN)
    if names_server(names) and py.name != "viewer.py":
        bad.extend(sorted(n for n in names if n == SERVER_ALLOWANCE or n.startswith(SERVER_ALLOWANCE + ".")))
    return bad


def module_functions(tree: ast.Module) -> dict[str, ast.AST]:
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}


def closure(tree: ast.Module, name: str) -> list[ast.AST]:
    """The function plus every module-level function it reaches by name, transitively."""
    functions = module_functions(tree)
    seen: dict[str, ast.AST] = {}
    todo = [name]
    while todo:
        current = todo.pop()
        if current in seen or current not in functions:
            continue
        seen[current] = functions[current]
        for node in ast.walk(functions[current]):
            if isinstance(node, ast.Name) and node.id in functions and node.id not in seen:
                todo.append(node.id)
    return list(seen.values())


def referenced_names(nodes: Sequence[ast.AST]) -> set[str]:
    return {n.id for fn in nodes for n in ast.walk(fn) if isinstance(n, ast.Name)}


ARITHMETIC = (ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.MatMult)


def is_non_numeric(node: ast.AST) -> bool:
    return isinstance(node, ast.JoinedStr | ast.List | ast.ListComp | ast.Tuple) or (
        isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def arithmetic_nodes(nodes: Sequence[ast.AST]) -> list[ast.AST]:
    """Arithmetic between two values: ``-``, ``*``, ``/``, ``//``, ``%``, ``**``, an
    augmented assignment with any of those, and ``+`` unless one side is a string literal,
    f-string, list or tuple."""
    out: list[ast.AST] = []
    for fn in nodes:
        for node in ast.walk(fn):
            if isinstance(node, ast.BinOp):
                if isinstance(node.op, ARITHMETIC):
                    out.append(node)
                elif isinstance(node.op, ast.Add) and not (is_non_numeric(node.left) or is_non_numeric(node.right)):
                    out.append(node)
            elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add | ARITHMETIC):
                out.append(node)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and not isinstance(node.operand, ast.Constant):
                out.append(node)
    return out


def total_seconds_operands(nodes: Sequence[ast.AST]) -> list[ast.AST]:
    return [
        n.func.value
        for fn in nodes
        for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "total_seconds"
    ]


def format_calls(tree: ast.Module) -> list[int]:
    """Line numbers of every ``format(...)`` and ``.format(...)`` call. A substring grep is
    wrong here: ``datetime.fromisoformat(`` contains ``format(`` and is not a formatter."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "format")
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "format")
        )
    ]


def report_import_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "poisson_prove.report":
            names.update(alias.name for alias in node.names)
    return names


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
    Added 2026-09-20 (truncation surfacing); restated here and never imported from another test module."""
    spans = [s for e in store.read(run, meta=False, trace="envelope")["trace"] if isinstance(e, dict) for s in e.get("spans", [])]
    return len(spans), sum(1 for s in spans if s.get("truncated") == "observation")


def build_pair(root: Path, a: str, b: str, spec: ReportSpec, events: Sequence[str]) -> Built:
    """S29 (``proofload.viewpair/3``) makes M14's tree a required input to assembly, so the
    fixture grows it on the frames it already reads, at M14's defaults, and passes ``tree=``.
    The tree is the family's, never the ``--fix`` slice's, which is what the spec says of the
    structure too."""
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


def go1_spec(**overrides: Any) -> ReportSpec:
    base: dict[str, Any] = {"title": GO1_TITLE, "x_axis": GO1_X, "y_axis": GO1_Y}
    base.update(overrides)
    return ReportSpec(**base)


@pytest.fixture(scope="module")
def go1(go1_store: Store) -> Built:
    """The Go1 pair over both events: the two-panel page every keying invariant needs."""
    return build_pair(GO1_ROOT, GO1_A, GO1_B, go1_spec(), GO1_EVENTS)


@pytest.fixture(scope="module")
def go1_dom(go1: Built) -> Dom:
    return parse_html(go1.page)


@pytest.fixture(scope="module")
def go1_serve_json(go1_store: Store) -> Result:
    """``serve --json`` on the Go1 pair, both events, with ``serve_page`` tripwired."""
    with pytest.MonkeyPatch.context() as mp:
        tripwire_serve(mp)
        # PF3 (Q17, spec sections 4.4 and 14; R1): Go1's runs share a salt, so the default is now the
        # paired test; V22 and V33 compare with the unpaired test's numbers, named.
        return run_cli(go1_full_argv("--method", "fisher_bh", "--json"))


@pytest.fixture(scope="module")
def go1_serve_json_one_event(go1_store: Store) -> Result:
    with pytest.MonkeyPatch.context() as mp:
        tripwire_serve(mp)
        # PF3 (Q17, spec sections 4.4 and 14; R1): V22 compares with diff's unpaired numbers, named.
        return run_cli(go1_argv("--event", "fell", "--x", GO1_X, "--y", GO1_Y, "--title", GO1_TITLE, "--method", "fisher_bh", "--json"))


@dataclass(frozen=True)
class MockPair:
    root: Path
    a: str
    b: str


#: PF4 re-freeze (PF4.30, reading R33): the quickstart's design at 100 replicates with nothing
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


def test_v1_missing_event_exits_two_names_serve_and_lists_the_axes_and_events_the_runs_carry(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(go1_argv("--x", GO1_X))
    # A refusal exits 1 and is one error line plus next lines; its facts stay in stderr (spec section 5.4).
    assert_clean_refusal(r, 1)
    assert_error_then_next(r.err)
    # PF2 (spec section 4.3): the refusal and its next line name the two runs by name, not id.
    for fact in ("serve", "--event", GO1_NAME_A, GO1_NAME_B, "mu", "push_pct_bw", "fell", "survived"):
        assert fact in r.err, (fact, r.err)


def test_v2_unknown_event_exits_two_with_the_known_events_sentence_and_the_verb(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(go1_argv("--event", "nope", "--x", GO1_X))
    # A refusal exits 1 (spec section 5.2).
    assert_clean_refusal(r, 1)
    assert 'serve: event "nope" does not appear in either run. Present: fell, survived.' in r.err, r.err


@pytest.mark.parametrize("runs", [(GO1_A,), (GO1_A, GO1_B, GO1_A)])
def test_v3_wrong_arity_exits_two_naming_the_two_run_form_and_no_single_run_mode(monkeypatch: pytest.MonkeyPatch, runs: tuple[str, ...]) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(["--store", str(GO1_ROOT), "serve", *runs, "--event", "fell", "--x", GO1_X])
    assert_clean_refusal(r, 2)
    assert re.search(r"\bserve\b", r.err), r.err
    assert re.search(r"\bA B\b", r.err), r.err
    for offer in ("survival", "one run id", "RUN "):
        assert offer not in r.err, r.err


def test_v4_missing_x_lists_the_axes_and_events_the_runs_carry(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(go1_argv("--event", "fell"))
    # A refusal exits 1 and is one error line plus next lines; its facts stay in stderr (spec section 5.4).
    assert_clean_refusal(r, 1)
    assert_error_then_next(r.err)
    # PF2 (spec section 4.3): the refusal and its next line name the two runs by name, not id.
    for fact in ("serve", "--x", GO1_NAME_A, GO1_NAME_B, "mu", "push_pct_bw", "fell", "survived"):
        assert fact in r.err, (fact, r.err)


def test_v4_unknown_x_exits_two_through_axis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    tripwire_serve(monkeypatch)
    r = run_cli(go1_argv("--event", "fell", "--x", "nope"))
    # A refusal exits 1, and an error shows no Python repr, so the value is checked bare (spec section 5.4).
    assert_clean_refusal(r, 1)
    assert "nope" in r.err and "config key" in r.err, r.err


# Each with its exit code: a refusal exits 1, a wrong command line (the run count) exits 2 (spec section 5.2).
REFUSALS = [
    (go1_argv("--x", GO1_X), 1),
    (go1_argv("--event", "nope", "--x", GO1_X), 1),
    (["--store", str(GO1_ROOT), "serve", GO1_A, "--event", "fell", "--x", GO1_X], 2),
    (["--store", str(GO1_ROOT), "serve", GO1_A, GO1_B, GO1_A, "--event", "fell", "--x", GO1_X], 2),
    (go1_argv("--event", "fell"), 1),
    (go1_argv("--event", "fell", "--x", "nope"), 1),
]


@pytest.mark.parametrize(("argv", "code"), REFUSALS, ids=["no-event", "unknown-event", "one-run", "three-runs", "no-x", "unknown-x"])
def test_v5_every_refusal_exits_two_without_calling_serve_page(monkeypatch: pytest.MonkeyPatch, argv: list[str], code: int) -> None:
    calls = tripwire_serve(monkeypatch)
    r = run_cli(argv)
    assert r.code == code, r.text
    assert calls == [], calls


def test_v5_json_exits_zero_without_calling_serve_page(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = tripwire_serve(monkeypatch)
    r = run_cli(go1_full_argv("--json"))
    assert r.code == 0, r.err
    assert calls == [], calls


# ---------- V6-V9: the server ----------


def test_v6_viewer_names_loopback_once_and_binds_it(go1: Built) -> None:
    src = viewer_source()
    assert src.count(HOST) == 1, src.count(HOST)
    assert "0.0.0.0" not in src
    assert "::" not in src
    with served(go1.page) as server:
        assert server.server_address[0] == HOST, server.server_address


def test_v7_get_root_returns_the_page_with_the_four_headers(go1: Built) -> None:
    with served(go1.page) as server:
        r = get(server, "/")
    assert r.status == 200
    assert r.headers["content-type"] == CONTENT_TYPE, r.headers
    assert int(r.headers["content-length"]) == len(r.body), r.headers
    assert r.headers["cache-control"] == "no-store", r.headers
    assert r.headers["content-security-policy"] == CSP, r.headers


@pytest.mark.parametrize("path", ["/anything-else", "/../x", "/index.html"])
def test_v8_other_paths_are_404(go1: Built, path: str) -> None:
    with served(go1.page) as server:
        r = get(server, path)
    assert r.status == 404, (path, r.status)


def test_v8_post_is_501(go1: Built) -> None:
    with served(go1.page) as server:
        r = get(server, "/", method="POST")
    assert r.status == 501, r.status


def test_v8_no_file_is_opened_per_request(go1: Built, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    real_open = io.open

    def recording_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(file))
        return real_open(file, *args, **kwargs)

    with served(go1.page) as server:
        monkeypatch.setattr("builtins.open", recording_open)
        monkeypatch.setattr(io, "open", recording_open)
        first = get(server, "/")
        second = get(server, "/index.html")
        monkeypatch.undo()
    assert (first.status, second.status) == (200, 404)
    assert opened == [], opened


def test_v9_three_gets_return_the_identical_rendered_page(go1: Built) -> None:
    with served(go1.page) as server:
        bodies = [get(server, "/").body for _ in range(3)]
    expected = viewer().render_html(go1.structure).encode("utf-8")
    assert bodies[0] == bodies[1] == bodies[2]
    assert bodies[0] == expected


# ---------- V11-V12: silence and no writes ----------


def test_v11_serving_including_a_raising_request_writes_only_the_url_line(go1: Built, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    real_send_response = http.server.BaseHTTPRequestHandler.send_response

    def send_response(self: Any, code: int, message: str | None = None) -> None:
        if self.path == "/raise":
            raise RuntimeError("injected inside do_GET")
        real_send_response(self, code, message)

    monkeypatch.setattr(http.server.BaseHTTPRequestHandler, "send_response", send_response)
    capfd.readouterr()
    with cli_served(monkeypatch, go1_full_argv()) as run:
        statuses = [get(run.server, "/").status for _ in range(3)]
        dropped = try_get(run.server, "/raise")
        missed = get(run.server, "/missing").status
    real_out, real_err = capfd.readouterr()
    assert statuses == [200, 200, 200] and missed == 404
    assert dropped is None or dropped.status >= 500, dropped
    # PF2 (spec section 5.3): the only stdout line is serve's verdict line, which names both runs
    # and carries the URL.
    assert run.out.getvalue() == serving_line(run.server.server_address[1]) + "\n", run.out.getvalue()
    # The unpaired-analysis warning on Go1 is now a note line on stderr (spec section 5.4).
    assert without_notes(run.err.getvalue()) == "", run.err.getvalue()
    assert (real_out, real_err) == ("", ""), (real_out, real_err)


def test_v12_assembling_rendering_and_serving_touch_no_file(go1: Built, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)
    monkeypatch.chdir(tmp_path)
    # PF2 (spec section 2.3, Q11): report's default folder is named by the runs' names now; both
    # the folder named by ids and the one named by names must stay absent.
    def slugged(name: str) -> str:
        return name.lower().replace(" ", "-").replace("/", "-")

    default_dir = tmp_path / f"prove-report-{GO1_A}-vs-{GO1_B}"
    named_dir = tmp_path / f"prove-report-{slugged(GO1_NAME_A)}-vs-{slugged(GO1_NAME_B)}"
    before = (tree_snapshot(GO1_ROOT), tree_snapshot(tmp_path), tree_snapshot(default_dir), tree_snapshot(named_dir))
    with cli_served(monkeypatch, go1_full_argv()) as run:
        assert get(run.server, "/").status == 200
    after = (tree_snapshot(GO1_ROOT), tree_snapshot(tmp_path), tree_snapshot(default_dir), tree_snapshot(named_dir))
    assert after == before
    assert not default_dir.exists() and not named_dir.exists()


# ---------- V13-V15: nothing outbound ----------


def test_v13_the_renderers_own_markup_references_nothing_external(go1: Built) -> None:
    own = excised(go1.page, SVG_RE, INDEX_RE).lower()
    for needle in ("href=", "src=", "@import", "url("):
        assert needle not in own, needle


def test_v14_no_core_module_imports_a_network_client_by_dotted_path() -> None:
    modules = core_modules()
    assert modules
    for py in modules:
        names = imported_modules(py.read_text())
        assert not {n for n in names if n.split(".")[0] in CLIENT_BAN}, py


def test_v14_only_viewer_names_http_server() -> None:
    naming = {py.name for py in core_modules() if names_server(imported_modules(py.read_text()))}
    assert naming == {"viewer.py"}, naming


def test_v14_viewer_has_no_client_call() -> None:
    src = viewer_source()
    for needle in ("connect(", "urlopen", "webbrowser"):
        assert needle not in src, needle


def test_v15_s0_states_the_commitment_in_prose() -> None:
    tree = ast.parse(S0_TEST_SOURCE.read_text())
    docs = {n.name: ast.get_docstring(n) or "" for n in tree.body if isinstance(n, ast.FunctionDef)}
    doc = " ".join(docs.get("test_no_network_imports_in_core", "").split())
    for phrase in ("opens no outbound connection", "not an outbound connection", "http.server", "viewer.py"):
        assert phrase in doc, phrase


def test_v15_socketserver_does_not_trip_the_client_ban(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch.py"
    scratch.write_text("import socketserver\n")
    assert network_violations(scratch) == []


def test_v15_from_http_import_server_trips_outside_viewer(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch.py"
    scratch.write_text("from http import server\n")
    assert network_violations(scratch) == [SERVER_ALLOWANCE]
    as_viewer = tmp_path / "viewer.py"
    as_viewer.write_text("from http import server\n")
    assert network_violations(as_viewer) == []


# ---------- V16-V17: it renders, it does not compute ----------


def test_v16_every_text_entry_is_m7s_formatting_of_the_raw_value(go1: Built) -> None:
    from poisson_prove.report import _fmt

    for panel in go1.structure["panels"]:
        rows = m6_rows(go1.multi, panel["event"])
        assert panel["cells"], panel["event"]
        for cell in panel["cells"]:
            row = rows[cell["config_hash"]]
            for name, kind in FLOAT_KINDS.items():
                raw = float(row[name])
                assert cell["text"][name] == _fmt(raw, kind), (panel["event"], cell["config_hash"], name)
                if math.isfinite(raw):
                    assert cell[name] == raw, (name, cell[name], raw)
                else:
                    assert cell[name] is None, (name, cell[name], raw)


def test_v16_integer_fields_have_no_text_entry_and_match_m6(go1: Built) -> None:
    for panel in go1.structure["panels"]:
        rows = m6_rows(go1.multi, panel["event"])
        for cell in panel["cells"]:
            assert set(cell["text"]) == set(FLOAT_KINDS), cell["text"].keys()
            for name in INT_FIELDS:
                assert isinstance(cell[name], int) and cell[name] == int(rows[cell["config_hash"]][name]), name


def test_v16_the_page_prints_no_float_except_through_m7s_strings(go1: Built) -> None:
    from poisson_prove.report import _provenance_lines

    # ``config_text`` values (viewpair/2) are structure strings and are already walked.
    allowed = list(walk_strings(go1.structure)) + _provenance_lines(go1.structure["diff"])
    allowed.append(str(go1.structure["pair"]["created_at_gap_s"]))
    stray = [
        tok for tok in FLOAT_TOKEN_RE.findall(visible_text(go1.page))
        if not any(tok in s for s in allowed)
    ]
    assert stray == [], stray


def test_v17_viewer_has_no_colour_no_float_format_and_no_fence() -> None:
    src = viewer_source()
    assert not HEX_RE.search(src), HEX_RE.search(src)
    assert not TIMES_100_RE.search(src)
    assert not FLOAT_SPEC_RE.search(src)
    assert format_calls(ast.parse(src)) == [], format_calls(ast.parse(src))
    assert "toFixed(" not in src and "toPrecision(" not in src
    for phrase in FENCE_PHRASES:
        assert phrase not in src, phrase


def test_v17_build_structure_applies_exactly_the_created_at_subtraction() -> None:
    tree = ast.parse(viewer_source())
    nodes = closure(tree, "build_structure")
    assert nodes, "no build_structure"
    arithmetic = arithmetic_nodes(nodes)
    assert len(arithmetic) == 1, [ast.dump(n) for n in arithmetic]
    only = arithmetic[0]
    assert isinstance(only, ast.BinOp) and isinstance(only.op, ast.Sub), ast.dump(only)
    assert only in total_seconds_operands(nodes), ast.dump(only)


def test_v17_render_html_applies_no_arithmetic() -> None:
    tree = ast.parse(viewer_source())
    nodes = closure(tree, "render_html")
    assert nodes, "no render_html"
    assert arithmetic_nodes(nodes) == [], [ast.dump(n) for n in arithmetic_nodes(nodes)]


# ---------- V18-V21: the page carries M7's output verbatim ----------


def test_v18_heatmap_svg_is_m7s_and_the_page_embeds_it_verbatim(go1: Built) -> None:
    expected = go1.report.to_svg()
    assert go1.structure["heatmap_svg"] == expected
    m = SVG_RE.search(go1.page)
    assert m, "no <svg> in the page"
    assert m.group(0) == expected.rstrip("\n")
    assert ET.tostring(ET.fromstring(m.group(0))) == ET.tostring(ET.fromstring(expected.rstrip("\n")))


def test_v19_honesty_appears_unescaped_above_the_svg_and_uncollapsed(go1: Built, go1_dom: Dom) -> None:
    unescaped = html_unescape(go1.page)
    svg_at = go1_dom.first_svg().index
    rules = css_rules(go1_dom.html_style())
    for panel, event in zip(go1.structure["panels"], go1.report.events, strict=True):
        # PF4 (PF4.20): Go1 declares no event kind, so the page names the honesty line's count in
        # direction words (the count of rises, "higher"); the library's panel keeps its old encoding.
        ev = go1.multi.by_event[event]
        assert ev.kind is None
        library = go1.report.panels[event].honesty
        # PF4 re-freeze (PF4.20, kindless events): the library no longer counts a kindless event's
        # rises as worse (n_worse is None, n_higher carries the count); the report's honesty line keeps
        # its old encoding, the count of rises, which is n_higher.
        assert ev.n_worse is None
        assert f'"{ev.n_higher} worse"' in library
        honesty = library.replace(f'"{ev.n_higher} worse"', f'"{ev.n_higher} higher"')
        assert panel["honesty"] == honesty
        lines = honesty.splitlines()
        assert '"' in honesty, "the honesty text has no double quote to escape"
        # PF4 re-freeze (PF4.22): a limit is the larger of the two directions, so Go1's two
        # complementary events have the same limits and their honesty lines can share a line of
        # text; each line is found after the line before it, which keeps the order pinned.
        positions = []
        for line in lines:
            positions.append(unescaped.find(line, positions[-1] + 1 if positions else 0))
        assert all(p >= 0 for p in positions), (event, positions)
        assert positions == sorted(positions), positions
        nodes = [n for n in body_nodes_containing(go1_dom, lines[0]) if lines[1] in n.deep_text()]
        assert nodes, event
        node = nodes[0]
        assert node.index < svg_at, (node.index, svg_at)
        assert not node.inside("details")
        for n in (node, *node.ancestors()):
            assert "hidden" not in n.attrs, n.tag
            styles = styles_of(n, rules)
            assert styles.get("display") != "none", n.tag
            assert "max-height" not in styles, n.tag


def test_v20_provenance_items_are_m7s_lines_in_order_and_diff_is_the_provenance_dict(go1: Built, go1_dom: Dom) -> None:
    from poisson_prove.report import _provenance_lines

    expected = [line[2:] for line in _provenance_lines(go1.report.provenance)]
    lists = [[li.deep_text() for li in descendants(ul, "li")] for ul in go1_dom.find("ul") + go1_dom.find("ol")]
    assert expected in lists, lists
    assert go1.structure["diff"] == go1.report.provenance
    assert list(go1.structure["diff"]) == list(go1.report.provenance)


def test_v21_the_event_line_names_every_event_first_and_says_the_set_was_given(go1: Built) -> None:
    unescaped = html_unescape(go1.page)
    first_honesty = min(unescaped.find(p["honesty"].splitlines()[0]) for p in go1.structure["panels"])
    assert first_honesty > 0
    region = unescaped[:first_honesty]
    assert "<svg" not in region
    for event in GO1_EVENTS:
        assert re.search(rf"\b{event}\b", region), event
    assert EVENT_LINE_LITERAL in region, region[-800:]
    assert go1.report.inference_line is None
    assert go1.structure["diff"]["inferred"] is False


# ---------- V22-V22b: the BH family is the event set ----------


def q_by_cell(payload: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {
        (event, str(cell["config_hash"])): float(cell["q"])
        for event, ev in payload["by_event"].items()
        for cell in ev["cells"]
    }


def structure_q(structure: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {(p["event"], c["config_hash"]): c["q"] for p in structure["panels"] for c in p["cells"]}


@pytest.mark.parametrize("events", [("fell",), ("fell", "survived")], ids=["one-event", "two-events"])
def test_v22_n_tests_and_every_q_equal_diff_format_json(go1_serve_json: Result, go1_serve_json_one_event: Result, events: tuple[str, ...]) -> None:
    served_json = go1_serve_json if len(events) == 2 else go1_serve_json_one_event
    assert served_json.code == 0, served_json.err
    argv = ["--store", str(GO1_ROOT), "diff", GO1_A, GO1_B]
    for e in events:
        argv += ["--event", e]
    # --json replaces --format json on diff (spec section 5.6).
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


def test_v23_panel_cells_are_the_present_grid_cells_in_m7_order_and_equal_m6_without_fix(go1: Built) -> None:
    assert [p["event"] for p in go1.structure["panels"]] == list(go1.report.events)
    for panel in go1.structure["panels"]:
        hashes = [c["config_hash"] for c in panel["cells"]]
        assert hashes == present_hashes(go1.report, panel["event"])
        assert sorted(hashes) == sorted(m6_rows(go1.multi, panel["event"]))


def test_v23_a_fix_slices_the_grid_against_m7_and_not_m6(go1: Built, go1_store: Store) -> None:
    mu = go1_store.read(GO1_A)["config"].iloc[0]["mu"]
    sliced = build_pair(GO1_ROOT, GO1_A, GO1_B, go1_spec(y_axis=None, fixed={"mu": mu}), GO1_EVENTS)
    for panel in sliced.structure["panels"]:
        hashes = [c["config_hash"] for c in panel["cells"]]
        assert hashes == present_hashes(sliced.report, panel["event"])
        assert hashes
        assert len(hashes) < len(m6_rows(sliced.multi, panel["event"]))


def test_v24_cell_keys_are_the_twenty_one_and_no_episode_level_key_anywhere(go1: Built) -> None:
    for panel in go1.structure["panels"]:
        for cell in panel["cells"]:
            assert tuple(cell) == CELL_KEYS, tuple(cell)
            assert set(cell["text"]) == set(FLOAT_KINDS)
    # Narrowed for S29 (spec S29 section 0.3, draft ADR-074). ``proofload.viewpair/3`` carries
    # M14's ``TreeResult.to_json()`` verbatim, and ``RootResult`` names the permutation seed
    # ``seed``: a knob a reader pastes back with ``--seed``, not a replicate's seed, and renaming
    # it in the structure would make the structure a lossy copy of the tree (ADR-033). The
    # structure walk therefore carves out that one path, by path and not by name: ``seed`` stays
    # forbidden at every other path, the other four names stay forbidden everywhere, and a user
    # config axis named ``seed`` still trips this clause under ``tree.root.units.config`` exactly
    # as it does under ``panels.cells.config`` today. The page-index walk is not narrowed: the
    # tree's regions add nothing to the picker's index, and this is the clause that says so.
    hits = {path for path, key in walk_key_paths(go1.structure) if key in FORBIDDEN_KEYS}
    assert hits <= {SEED_CARVE_OUT}, hits
    assert not FORBIDDEN_KEYS & set(walk_keys(index_of(go1.page)))


def test_v25_holes_have_no_index_entry_and_the_hole_message_appears_once(hostile: Built) -> None:
    index = index_of(hostile.page)
    assert not any(k.endswith("absent") for k in index), list(index)
    present = {key_of(p["event"], c["config_hash"]) for p in hostile.structure["panels"] for c in p["cells"]}
    assert set(index) == present
    assert any(not c.present for p in hostile.report.panels.values() for c in p.cells), "no hole in the fixture"
    assert 'data-cell="absent"' in hostile.page
    assert html_unescape(hostile.page).count(HOLE_MESSAGE) == 1


def test_v26_pointer_events_none_covers_the_glyph_the_notch_and_the_figures_text_and_nothing_else(go1_dom: Dom) -> None:
    """LS retrofit, 2026-09-22 (local serve pass, Phase A): the inert set gains the figure's ``<text>`` (spec LS D8, LS1) -- a cell's own
    label swallowed the click. The ``data-cell`` clause is re-asserted verbatim."""
    rules = css_rules(go1_dom.html_style())
    inert = [s for selectors, decls in rules if decls.get("pointer-events") == "none" for s in selectors]
    assert inert, rules
    assert any("[data-sig]" in s for s in inert), inert
    assert any(last_compound_tag(s) == "path" for s in inert), inert
    assert any(last_compound_tag(s) == "text" for s in inert), inert
    assert not any("data-cell" in s or "data-mde" in s for s in inert), inert
    cells = [n for n in go1_dom.nodes if "data-cell" in n.attrs]
    assert cells
    for node in cells:
        assert styles_of(node, rules).get("pointer-events") != "none", node.attrs


def test_v27_the_select_lists_every_cell_grouped_by_event_in_grid_order(go1: Built, go1_dom: Dom) -> None:
    selects = go1_dom.find("select")
    assert len(selects) == 1, len(selects)
    groups = [g for g in selects[0].children if g.tag == "optgroup"]
    assert [g.attrs.get("label") for g in groups] == [*go1.report.events, "holes"]
    index = index_of(go1.page)
    for group, panel in zip(groups[:-1], go1.structure["panels"], strict=True):
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


def test_v29_two_builds_are_equal_and_two_renders_identical_with_no_timestamp(go1: Built, go1_store: Store) -> None:
    again = build_pair(GO1_ROOT, GO1_A, GO1_B, go1_spec(), GO1_EVENTS)
    assert again.structure == go1.structure
    assert viewer().render_html(go1.structure) == go1.page == again.page
    assert go1.report.spec.generated_at is None
    assert "generated_at" not in go1.structure["diff"]
    dump = json.dumps(go1.structure, allow_nan=False)
    today = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
    for text in (dump, go1.page):
        assert today not in text
        assert dt.date.today().isoformat() not in text
        assert not UUID_RE.search(text)


def test_v30_help_lists_serve_and_serve_help_lists_exactly_the_sixteen_flags() -> None:
    top = run_cli(["--help"])
    assert top.code == 0 and re.search(r"\bserve\b", top.out), top.out
    assert "serve" in cli._VERBS
    r = run_cli(["serve", "--help"])
    assert r.code == 0, r.text
    # Narrowed for S29: the flags are the option entries the help lists, read off the lines that
    # begin an entry, not every ``--word`` in the text -- the tree helper's help for
    # ``--max-group-mde`` names ``--max-mde`` in prose, which is not a flag of ``serve``.
    flags = option_flags(r.out)
    assert flags == SERVE_FLAGS, flags ^ SERVE_FLAGS
    assert "--port" not in r.out


def test_v31_the_four_unverified_entries_in_order_rendered_uncollapsed_above_the_svg(go1: Built, go1_dom: Dom) -> None:
    entries = go1.structure["unverified"]
    assert [(e["id"], e["statement"], e["blocked_by"]) for e in entries] == list(UNVERIFIED)
    assert all(tuple(e) == ("id", "statement", "blocked_by") for e in entries)
    unescaped = html_unescape(go1.page)
    svg_at = go1_dom.first_svg().index
    for _, statement, _ in UNVERIFIED:
        assert statement in unescaped, statement
        nodes = body_nodes_containing(go1_dom, statement)
        assert nodes, statement
        assert nodes[0].index < svg_at
        assert not nodes[0].inside("details")


def manifest_values(m: RunManifest) -> dict[str, Any]:
    d = m.to_dict()
    return {k: d[k] for k in ARM_KEYS if k in d}


def test_v32_both_arms_carry_the_manifest_the_row_count_and_the_role(go1: Built, go1_store: Store) -> None:
    pair = go1.structure["pair"]
    for key, run_id, role in (("a", GO1_A, "baseline"), ("b", GO1_B, "candidate")):
        arm = pair[key]
        assert tuple(arm) == ARM_KEYS, tuple(arm)
        expected = manifest_values(go1_store.manifest(run_id))
        assert {k: arm[k] for k in expected} == expected
        assert arm["rows_stored"] == go1_store.count(run_id) == GO1_ROWS
        assert arm["role"] == role
    assert go1.structure["view"]["sign_convention"] == SIGN_CONVENTION
    # PF4 (PF4.11): the pair no longer carries the store's path.
    assert "store_root" not in pair and str(GO1_ROOT) not in json.dumps(go1.structure)
    assert pair["a"]["run_salt"] == pair["b"]["run_salt"] == go1.structure["diff"]["run_salt"]


def test_v32_the_page_shows_both_identities(go1: Built) -> None:
    unescaped = html_unescape(go1.page)
    for key in ("a", "b"):
        arm = go1.structure["pair"][key]
        for name in ("target_id", "status", "created_at", "run_salt", "run_id"):
            assert arm[name] in unescaped, (key, name)
    assert "baseline" in unescaped and "candidate" in unescaped
    assert str(go1.structure["pair"]["created_at_gap_s"]) in unescaped


def test_v32_created_at_gap_is_the_signed_difference_and_go1_measures_0_112099(go1: Built, go1_store: Store) -> None:
    a, b = go1_store.manifest(GO1_A), go1_store.manifest(GO1_B)
    expected = (dt.datetime.fromisoformat(b.created_at) - dt.datetime.fromisoformat(a.created_at)).total_seconds()
    assert go1.structure["pair"]["created_at_gap_s"] == expected == GO1_GAP_S


def test_v32_created_at_gap_is_null_when_a_timestamp_does_not_parse(go1: Built, go1_store: Store) -> None:
    from dataclasses import replace

    ma, mb = go1_store.manifest(GO1_A), go1_store.manifest(GO1_B)
    broken = replace(ma, created_at="not a timestamp")
    structure = viewer().build_structure(
        go1.report, go1.multi, tree=go1.tree, manifest_a=broken, manifest_b=mb,
        rows_a=GO1_ROWS, rows_b=GO1_ROWS,
        tally_a=go1_store.tally(GO1_A), tally_b=go1_store.tally(GO1_B), store_root=str(GO1_ROOT),
    )
    assert structure["pair"]["created_at_gap_s"] is None
    assert structure["pair"]["a"]["created_at"] == "not a timestamp"


def test_v32_each_arm_carries_its_own_salt(go1: Built, go1_store: Store) -> None:
    # Go1's arms share a salt, so a structure that copied A's salt into B would pass on the
    # fixture alone; give B a salt of its own and read both back.
    from dataclasses import replace

    ma, mb = go1_store.manifest(GO1_A), go1_store.manifest(GO1_B)
    other = replace(mb, run_salt="candidate-only-salt")
    structure = viewer().build_structure(
        go1.report, go1.multi, tree=go1.tree, manifest_a=ma, manifest_b=other,
        rows_a=GO1_ROWS, rows_b=GO1_ROWS,
        tally_a=go1_store.tally(GO1_A), tally_b=go1_store.tally(GO1_B), store_root=str(GO1_ROOT),
    )
    assert structure["pair"]["a"]["run_salt"] == ma.run_salt
    assert structure["pair"]["b"]["run_salt"] == "candidate-only-salt"
    assert structure["diff"]["run_salt"] == ma.run_salt
    assert "candidate-only-salt" in html_unescape(viewer().render_html(structure))


def test_v32_the_renderer_prints_the_gap_it_is_given(go1: Built) -> None:
    structure = json.loads(json.dumps(go1.structure, allow_nan=False))
    structure["pair"]["created_at_gap_s"] = 4242.5
    page = html_unescape(viewer().render_html(structure))
    assert "4242.5" in page
    assert str(GO1_GAP_S) not in page


def test_v33_json_prints_the_structure_indented_and_strict_and_binds_nothing(go1: Built, go1_serve_json: Result) -> None:
    r = go1_serve_json
    assert r.code == 0, r.err
    assert r.out.startswith('{\n  "schema": ')
    parsed = strict_loads(r.out)
    # serve --json wraps the structure with verdict and sentence after schema (spec section 5.6).
    # PF3 (spec section 4.4, R3): and with method and method_chosen right after sentence, which the
    # library's structure does not carry; they are set aside with verdict and sentence.
    assert tuple(parsed)[:5] == ("schema", "verdict", "sentence", "method", "method_chosen"), tuple(parsed)
    parsed = {k: v for k, v in parsed.items() if k not in ("verdict", "sentence", "method", "method_chosen")}
    # PF2 (spec section 4.3): serve --json carries run_name beside each arm's run_id; with it set
    # aside the structure is the library's, and the names sit where they belong.
    assert {role: (parsed["pair"][role]["run_id"], parsed["pair"][role].get("run_name")) for role in ("a", "b")} == {
        "a": (GO1_A, GO1_NAME_A), "b": (GO1_B, GO1_NAME_B)
    }, parsed["pair"]
    for role in ("a", "b"):
        arm = parsed["pair"][role]
        assert tuple(arm).index("run_name") == tuple(arm).index("run_id") + 1, tuple(arm)
        del arm["run_name"]
    assert parsed == json.loads(json.dumps(go1.structure, allow_nan=False))
    assert parsed["schema"] == SCHEMA
    assert tuple(parsed) == TOP_LEVEL_KEYS, tuple(parsed)
    assert tuple(go1.structure) == TOP_LEVEL_KEYS


# ---------- V34-V36: n_present, the rendering split, the worst tables ----------


def test_v34_n_present_counts_the_present_cells_of_the_full_grid(go1: Built) -> None:
    for event in go1.report.events:
        panel = go1.report.panels[event]
        assert panel.n_present == sum(c.present for c in panel.cells)
        assert panel.n_present + panel.n_absent == len(panel.cells)
    for entry in go1.structure["panels"]:
        assert tuple(entry) == PANEL_KEYS, tuple(entry)
        assert entry["n_present"] == go1.report.panels[entry["event"]].n_present
        assert entry["n_present"] == len(entry["cells"])


def test_v34_no_test_constructs_report_positionally_or_pins_its_fields() -> None:
    offenders = []
    for py in sorted(TESTS_DIR.glob("test_*.py")):
        for node in ast.walk(ast.parse(py.read_text())):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "Report" and node.args:
                offenders.append((py.name, node.lineno, "positional Report()"))
            is_fields = (isinstance(func, ast.Name) and func.id == "fields") or (
                isinstance(func, ast.Attribute) and func.attr == "fields"
            )
            if is_fields and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id in PINNED_REPORT_TYPES:
                offenders.append((py.name, node.lineno, f"fields({node.args[0].id})"))
    assert offenders == [], offenders


def test_v35_render_html_takes_one_parameter_and_renders_a_round_tripped_structure_identically(go1: Built, tmp_path: Path) -> None:
    assert len(inspect.signature(viewer().render_html).parameters) == 1
    structure_path = tmp_path / "structure.json"
    page_path = tmp_path / "page.html"
    structure_path.write_text(json.dumps(go1.structure, allow_nan=False))
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
    assert page_path.read_text(encoding="utf-8") == go1.page


def test_v35_the_report_imports_split_between_assembly_and_rendering() -> None:
    tree = ast.parse(viewer_source())
    assert report_import_names(tree) == ASSEMBLY_HELPERS | RENDER_HELPERS
    build = referenced_names(closure(tree, "build_structure"))
    render = referenced_names(closure(tree, "render_html"))
    assert build & (ASSEMBLY_HELPERS | RENDER_HELPERS) == ASSEMBLY_HELPERS, build
    assert render & (ASSEMBLY_HELPERS | RENDER_HELPERS) == RENDER_HELPERS, render
    for name in ("MultiReport", "Report", "DiffResult", "DataFrame", "multi", "report"):
        assert name not in render, name


def test_v36_worst_tables_are_m7s_and_the_first_worst_cell_is_selected(go1: Built, go1_dom: Dom) -> None:
    receipt = receipt_tables(go1.report)
    for panel, (header, rows) in zip(go1.structure["panels"], receipt, strict=True):
        assert panel["worst_header"] == header
        assert panel["worst_rows"] == rows
        # P-1: the flat panel's worst table gains a trailing ``interval (pp)`` column when M6 built intervals.
        axes = len(header) - (9 if header[-1] == "interval (pp)" else 8)
        by_coords = {c["coords"]: c["config_hash"] for c in panel["cells"]}
        expected_hashes = [
            by_coords[", ".join(f"{axis}={value}" for axis, value in zip(header[:axes], row[:axes], strict=True))]
            for row in rows
        ]
        assert panel["worst_hashes"] == expected_hashes
        rendered = [
            ([th.deep_text() for th in descendants(t, "th")], [[td.deep_text() for td in descendants(tr, "td")] for tr in descendants(t, "tr") if descendants(tr, "td")])
            for t in go1_dom.find("table")
        ]
        assert (header, rows) in rendered
    first = go1.structure["panels"][0]
    selected = [o for o in go1_dom.find("option") if "selected" in o.attrs]
    assert [o.attrs.get("value") for o in selected] == [key_of(first["event"], first["worst_hashes"][0])]


# ---------- V37-V40: non-finite floats, the URL line, the page's text, the schema ----------


def test_v37_non_finite_stats_are_null_in_the_structure_and_the_dump_parses_strictly(go1: Built, go1_serve_json: Result) -> None:
    non_finite = sum(
        not math.isfinite(float(v)) for e in go1.multi.events for v in go1.multi.by_event[e].cells["stat"]
    )
    assert non_finite > 0, "the fixture has no non-finite stat; the invariant is not exercised"
    nulls = sum(c["stat"] is None for p in go1.structure["panels"] for c in p["cells"])
    assert nulls == non_finite
    for panel in go1.structure["panels"]:
        for cell in panel["cells"]:
            if cell["stat"] is None:
                assert cell["text"]["stat"] in ("inf", "-inf", "nan"), cell["text"]["stat"]
    assert go1_serve_json.code == 0
    strict_loads(go1_serve_json.out)
    strict_loads(parse_html(go1.page).index_json())
    with pytest.raises(ValueError):
        json.dumps(go1.structure | {"probe": math.inf}, allow_nan=False)


def json_dumps_calls(nodes: Sequence[ast.AST]) -> list[ast.Call]:
    return [
        n
        for fn in nodes
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "dumps"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "json"
    ]


def test_v37_both_serializers_pass_allow_nan_false() -> None:
    # With the null rule intact there is no non-finite value left to reject, so the setting
    # has no rendered form; it is the loud-failure guard V37 names, read from the source.
    viewer_tree = ast.parse(viewer_source())
    cli_tree = ast.parse((Path(poisson_prove.__file__).resolve().parent / "cli.py").read_text())
    calls = json_dumps_calls(closure(viewer_tree, "render_html")) + json_dumps_calls(closure(cli_tree, "_cmd_serve"))
    assert len(calls) >= 2, len(calls)
    for call in calls:
        flags = {kw.arg: getattr(kw.value, "value", None) for kw in call.keywords}
        assert flags.get("allow_nan") is False, (call.lineno, flags)


def test_v38_the_url_line_carries_the_bound_port_and_is_written_after_on_bind(go1: Built, monkeypatch: pytest.MonkeyPatch) -> None:
    with cli_served(monkeypatch, go1_full_argv()) as run:
        port = run.server.server_address[1]
        assert isinstance(run.server, socketserver.BaseServer)
        assert run.out_at_bind == ""
        # PF2 (spec section 5.3): the URL line is now serve's verdict line naming both runs.
        assert run.out.getvalue() == serving_line(port) + "\n"
        assert get(run.server, "/").status == 200
    assert run.codes == [0], run.codes
    # The unpaired-analysis warning on Go1 is now a note line on stderr (spec section 5.4).
    assert without_notes(run.err.getvalue()) == ""


def test_v38_keyboard_interrupt_exits_zero_closes_the_socket_and_prints_no_traceback(go1: Built, monkeypatch: pytest.MonkeyPatch) -> None:
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
    r = run_cli(go1_full_argv())
    # Ctrl-C exits 130 and adds one stopped line after the URL line; the Go1 warning is a note line
    # (spec sections 5.2 and 5.4).
    assert r.code == 130, r.text
    assert "Traceback" not in r.text and without_notes(r.err) == "", r.text
    lines = r.out.splitlines()
    # PF2 (spec section 5.3): the URL line is now serve's verdict line naming both runs.
    assert holder and lines[0] == serving_line(holder[0].server_address[1]), r.out
    assert len(lines) == 2 and lines[1].startswith("stopped  "), r.out
    assert holder[0].socket.fileno() == -1


def test_v38_bind_failure_is_a_viewer_error_and_exit_two(go1: Built, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(self: Any) -> None:
        raise OSError(98, "address in use (injected)")

    monkeypatch.setattr(http.server.HTTPServer, "server_bind", refuse)
    with pytest.raises(viewer().ViewerError):
        viewer().serve_page(go1.page, on_bind=lambda server: None)
    r = run_cli(go1_full_argv())
    # A refusal exits 1; the Go1 warning may come first as a note line (spec sections 5.2 and 5.4).
    assert_clean_refusal(r, 1)
    assert r.out == "" and without_notes(r.err).startswith("error:"), r.text


def test_v39_fence_headline_captions_and_worst_rows_are_on_the_page(go1: Built) -> None:
    unescaped = html_unescape(go1.page)
    assert go1.structure["fence"] == receipt_fence(go1.report)
    assert go1.structure["fence"] in unescaped
    assert go1.structure["headline"] == go1.report.headline
    for line in go1.structure["headline"].splitlines():
        assert line in unescaped, line
    for panel, event in zip(go1.structure["panels"], go1.report.events, strict=True):
        # PF4 (PF4.20): Go1 declares no event kind, so the caption counts falls and rises in
        # direction words ("N lower, M higher") rather than the library panel's safer/worse.
        ev = go1.multi.by_event[event]
        assert ev.kind is None
        assert panel["caption"] == f"{event}: {ev.n_lower} lower, {ev.n_higher} higher"
        assert panel["caption"] in unescaped
        for row in panel["worst_rows"]:
            for value in row:
                assert value in unescaped, value


def test_v39_trade_line_appears_when_present_and_leaves_no_empty_element_when_null(go1: Built, go1_dom: Dom) -> None:
    # Go1's two events are complements, so every safer fell cell is a worse survived cell
    # and the pair carries a trade line: the non-null case is the fixture itself.
    trade = go1.structure["trade_line"]
    assert trade is not None and trade == go1.report.trade_line
    # M7 also draws the trade line inside the SVG header; the page must carry it outside too.
    holder = [n for n in go1_dom.nodes if trade in n.text and not n.inside("svg")]
    assert holder, "the trade line is not the direct text of one element outside the SVG"
    without = json.loads(json.dumps(go1.structure, allow_nan=False))
    without["trade_line"] = None
    # LS retrofit, 2026-09-22 (local serve pass, Phase A, found by the shim run): the Summary carries the same sentence as
    # ``summary.complement.line`` on this pair (spec LS section 3.6), so a structure without the
    # trade line is one without the complement too.
    without["summary"]["complement"] = None
    page = viewer().render_html(without)
    dom = parse_html(page)
    assert not [n for n in dom.nodes if trade in n.text and not n.inside("svg")]
    empties = [n for n in dom.nodes if n.tag == holder[0].tag and not n.children and not n.text.strip()]
    assert empties == [], [(n.tag, n.attrs) for n in empties]
    outside = [n for n in dom.nodes if not n.inside("svg") and n.tag != "svg"]
    assert not any("trade" in n.classes() or "trade" in n.attrs.get("id", "") for n in outside)


def test_v41_environment_renders_inside_one_closed_details_and_nowhere_else(go1: Built, go1_dom: Dom) -> None:
    details = [n for n in go1_dom.find("details") if not n.inside("svg")]
    assert len(details) == 1, len(details)
    assert "open" not in details[0].attrs, details[0].attrs
    inside = details[0].deep_text()
    outside = html_unescape(excised(go1.page, DETAILS_RE))
    for key in ("a", "b"):
        environment = go1.structure["pair"][key]["environment"]
        for value in walk_strings(environment):
            assert value in inside, (key, value)
        sentinel = environment["source_manifest"]
        assert sentinel not in outside, (key, sentinel)


def test_v40_an_unknown_schema_is_refused_naming_both_values(go1: Built) -> None:
    structure = json.loads(json.dumps(go1.structure, allow_nan=False))
    structure["schema"] = RETIRED_SCHEMA
    with pytest.raises(viewer().ViewerError) as info:
        viewer().render_html(structure)
    assert RETIRED_SCHEMA in str(info.value)
    assert SCHEMA in str(info.value)
