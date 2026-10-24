"""S21 oracle: error visibility downstream (Action List B.6), from section 4 of the S21 spec.

Invariants E1-E27 map one test function each (several map more). Nothing here is built when
this file is written: ``RunTally``, ``Store.tally``, ``COVERAGE_COLUMNS``, ``Cell.hole_cause``
and ``proofload.viewpair/3`` are reached through module attributes inside the tests, so
collection never touches them.

What is asserted where:

- **The public surface first.** ``RunTally`` values, coverage frames, ``Cell`` fields, the
  structure, the page, and the CLI's exit code and streams. Five clauses reach a private name
  because the spec pins the name itself and nothing rendered carries it: E3 (the two store
  markers against ``executor._TIMEOUT_ERROR`` and ``executor_modal._INFRA_PREFIX``, so they
  cannot drift), E12 (``diff._CAUSES`` and ``report._GRID_CAUSES``, the vocabulary written
  once), E16 (``report._fmt`` -- a formatted string can only be checked against the formatter,
  the V16 rule) and E17 (``report._coord_text`` for a grid hole's coords). E22 reads the source
  through ``proofload.__file__`` and imports nothing.
- **Go1 is the zero case** (E4, E14, E15, E21, E23, E24): no errored rows, no holes, both
  tallies ``(12800, 12800, 0, 0, 0, 0)``. E14's three digests were minted on the bare tree at
  ``b10a146`` with ``report go1-v0 go1-v1 --event fell --x mu --y push_pct_bw`` and committed
  before the build exists: a hash, never a diff of two renders.
- **The synthetic pair** (E6-E13, E17, E20, E24-E26) is built in ``tmp_path`` the way
  ``test_m13_viewer.py``'s ``write_run`` builds one, restated here. Over a categorical
  ``task`` and a numeric ``level`` it holds every case section 6 lists, plus a ``variant`` key
  that is constant on every comparable cell so that two non-comparable cells can share a grid
  coordinate, a ``ghost`` task no comparable cell carries (an off-grid hole without a
  ``--fix``, given errored rows so that E26 counts it), a bool and a list in every config (``config_text``'s scalar and non-scalar
  cases), and errors cycling through ``timeout`` / ``infra: RuntimeError('x')`` / ``boom`` so
  all four tally buckets are non-zero in both arms.

Literals the spec leaves to the oracle, pinned here rather than buried in a test:

- ``HOLES_HEADING``: the section's ``<h2>`` text is ``Holes``.
- ``ZERO_HOLES_TEXT``: the zero-holes paragraph reads ``0 holes``.
- ``HOLE_OPTION_LABEL``: a hole's ``<option>`` is labelled by ``coords``, else ``config_hash``.
- ``DRILL_LABELS``: the drill-down rows are ``rows (a/b)`` and ``no outcome (a/b)`` and follow
  ``n (a/b)``; the script's ``order`` list, which carries keys and not labels, gains the four
  cell keys ``rows_a, rows_b, no_outcome_a, no_outcome_b`` right after ``n_a, n_b``.
- ``coverage_block``: ``MultiDiffResult.to_markdown()`` is UNCHANGED (A20 in the M6 oracle
  requires a diff with errored rows to render identically to one without); the ``diff``
  verb's text output appends the block instead, after the markdown and after the
  ``--methods all`` table, the way ``_method_table`` already is: the exact ``coverage:``
  line, a ``## coverage`` heading and the table over ``COVERAGE_COLUMNS`` in ``_md_cell``
  style, a comparable row's cause printed ``None``.
- ``NONE_TEXT``: the Holes table prints ``none`` for a null coords or hash.
- R8's Go1 row literal is ``"0"``: Go1 has no errored rows.

Named non-observables, carried over from S20: the page's JavaScript is not executed; the
picker's holes optgroup and the holes block are pinned as markup; what selecting a hole shows
is not asserted.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import itertools
import json
import re
import shutil
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from html import unescape as html_unescape
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import poisson_prove
import poisson_prove.cli as cli
import poisson_prove.diff as diff_module
import poisson_prove.executor as executor
import poisson_prove.executor_modal as executor_modal
import poisson_prove.report as report_module
import poisson_prove.store as store_module
from poisson_prove.diff import DiffResult, MultiDiffResult, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import MultiReport, ReportSpec, build_multi_report, build_report
from poisson_prove.store import EpisodeRecord, RunManifest, SchemaMismatch, Store, StoreError, config_hash
from poisson_prove.tree import TreeResult
from poisson_prove.tree import tree as grow_tree

ROOT = Path(__file__).resolve().parents[1]
GO1_ROOT = ROOT / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"
GO1_EVENTS = ("fell", "survived")
GO1_X, GO1_Y = "push_pct_bw", "mu"
GO1_TITLE = "Go1 pair"
GO1_ROWS = 12_800
GO1_TALLY = (12_800, 12_800, 0, 0, 0, 0)

# E14: minted on the bare tree at b10a146 (2026-09-06) by
#   proofload --store tests/fixtures/go1 report go1-v0 go1-v1 --event fell --x mu --y push_pct_bw
# PF3 (Q17, spec sections 4.4 and 14; rule R1): Go1's runs share a salt, so the default is now the paired
# test; the E14 facts and the heatmap are the unpaired test's, named.
E14_ARGV = ("report", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--method", "fisher_bh")
# PF4 (PF4.3, PF4.15, PF4.20): the three E14 digests (report.md, heatmap.svg, receipt.html) are no longer
# asserted: the share table, the detection-limit notes and the direction words change all three files.
# E14 checks the facts they guarded instead. An event of unknown kind prints in direction words, so the
# library's own ``safer`` (the rate fell) and ``worse`` (it rose) read ``lower`` and ``higher``.
E14_DIRECTION = {"safer": "lower", "worse": "higher", "unchanged": "unchanged"}

# LS retrofit, 2026-09-22 (local serve pass, Phase A): /5 retires with the ``summary`` key.
SCHEMA = "poisson-prove.viewpair/7"
RETIRED_SCHEMA = "proofload.viewpair/3"
HOST = "127.0.0.1"

TALLY_FIELDS = ("rows", "with_outcome", "no_outcome", "timed_out", "infra", "other")
TIMEOUT_MARK = "timeout"
INFRA_MARK = "infra: "
COVERAGE_COLUMNS = (
    "config_hash", "config", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b", "comparable",
    "cause",
)
CAUSES = ("only_a", "only_b", "no_outcome_both", "no_outcome_a", "no_outcome_b")
GRID_CAUSES = ("unsampled", "multiple")
ALL_CAUSES = CAUSES + GRID_CAUSES
MULTI_FIELDS = (
    "events", "by_event", "method", "seed_identity_match", "unpaired_analysis", "q", "t_unit", "horizon", "n_tests",
    "n_not_comparable", "dropped_a", "dropped_b", "truncated", "trades", "inferred", "non_event",
)
#: Retrofitted 2026-09-20 (truncation surfacing): ``truncated`` -- the horizon count -- is
#: ``episodes_censored_at_horizon`` in its slot, and a report built with manifests and the counts the CLI hands
#: the builders (this file's ``built()`` does) carries each run's recorded byte limit, its span count and its count
#: of spans stamped as cut after ``run_salt``.
PROVENANCE_KEYS = (
    "events", "inferred", "non_event", "n_tests", "method", "seed_identity_match", "unpaired_analysis", "q", "t_unit", "horizon",
    "n_not_comparable", "dropped_a", "dropped_b", "episodes_censored_at_horizon", "n_absent", "poisson_prove_version",
    "run_id_a", "run_id_b", "run_salt", "observation_cap_a", "observation_cap_b", "trace_spans_a", "trace_spans_b",
    "observation_cut_spans_a", "observation_cut_spans_b",
)

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
CELL_KEYS = (
    "coords", "config_hash", "n_a", "n_b", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b",
    "events_a", "events_b", "rate_a", "rate_b", "delta", "stat", "p", "q", "mde", "verdict",
    "config", "config_text", "text",
)
# PF4 (PF4.3, PF4.13 to PF4.15): every page cell also carries its direction, the direction and
# detection-limit notes, its matched pairs and both arms' shares.
PF4_CELL_KEYS = (
    "direction", "direction_note", "pairs", "mde_note", "share_a", "share_b", "share_a_differs",
    "share_b_differs",
)
# LS retrofit, 2026-09-22 (local serve pass, Phase A): ``where`` after ``coords``; ``coords`` keeps its meaning (spec LS section 3.1 (c)).
HOLE_KEYS = (
    "coords", "where", "config_hash", "cause", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b",
    "config", "config_text",
)
COVERAGE_CELL_KEYS = ("rows_a", "rows_b", "no_outcome_a", "no_outcome_b")
FLOAT_KINDS = {
    "rate_a": "pp1", "rate_b": "pp1", "delta": "pp1", "stat": "sig3", "p": "sig3", "q": "sig3",
    "mde": "pp0",
}
FORBIDDEN_KEYS = {"episode", "seed", "replicate_index", "trace", "meta"}
#: E16's one carve-out, by path (spec S29 section 0.3): the permutation seed M14's frozen
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
DELETED_UNVERIFIED: tuple[tuple[str, str], ...] = (
    (
        "errored_rows_per_cell",
        "n_a and n_b count rows with a non-null outcome. A cell that ran 32 replicates and "
        "errored 20 is indistinguishable here from one that ran 12. The MDE reflects the "
        "smaller n; nothing on this page says why it is small.",
    ),
    (
        "hole_cause",
        "A hole is a cell with no comparable data. Whether it was never sampled, was sampled "
        "and wholly errored, or exists in one run only is not recoverable from this diff.",
    ),
    (
        "run_error_totals",
        "rows_stored is every row in the store, errored rows included. How many errored is "
        "counted at run time and not persisted, so this page cannot separate them.",
    ),
)

IDENTITY_HEADER = ["field", "A (baseline)", "B (candidate)"]
IDENTITY_ROWS = ("with_outcome", "no_outcome", "timed_out", "infra", "other")
DRILL_LABELS = ("n (a/b)", "rows (a/b)", "no outcome (a/b)")
ORDER_KEYS_AFTER_N = ("rows_a", "rows_b", "no_outcome_a", "no_outcome_b")
HOLES_HEADING = "Holes"
# LS retrofit, 2026-09-22 (local serve pass, Phase A, found by the shim run): ``coords`` is ``where`` in the header and the column prints the hole's ``where`` (spec LS D12).
HOLES_HEADER = ["where", "cause", "config_hash", "rows (a/b)", "no outcome (a/b)"]
ZERO_HOLES_TEXT = "0 holes"
HOLES_OPTGROUP = "holes"
HOLES_ID = "prove-holes"
INDEX_ID = "prove-cells"
HOLE_MESSAGE = "No comparable data for this cell."
NONE_TEXT = "none"
# PF2 (spec section 4.3/5.3): runs prints these nine columns, newest first.
RUNS_HEADER = ("#", "name", "id", "status", "backend", "target", "rows", "rows without an outcome", "created")
PUBLIC_STORE_METHODS = {
    "create_run", "manifest", "mark_complete", "runs", "append", "read", "missing", "count",
    "tally",
}
PUBLIC_STORE_SYMBOLS = {
    "StoreError", "SchemaMismatch", "DuplicateEpisode", "MetaNotSerializable", "InvalidConfig",
    "RunManifest", "EpisodeRecord", "Store", "config_hash", "RunTally",
}
ASSEMBLY_HELPERS = {"_fmt", "_coord_text", "_worst_header", "_worst_table_rows", "_EPISTEMIC_FENCE"}
RENDER_HELPERS = {"_html_style", "_html_table", "_provenance_lines"}

POISON = "not json"
TMP_PART = "part-99999.parquet.tmp"

# The E1 store: k_ok outcome rows, k_t timeouts, k_i infra, k_o other.
K_OK, K_T, K_I, K_O = 5, 3, 2, 4
COUNTED, EMPTY, SCHEMA_TWO = "counted", "empty", "schema-two"
ERRORS = ("timeout", "infra: RuntimeError('x')", "boom")

# The synthetic pair. (task, level, variant) -> (rows with an outcome, errored rows).
SYN_A, SYN_B = "syn-a", "syn-b"
SYN_SALT = "s21-oracle"
SYN_EVENTS = ("fail", "ok")
SYN_X, SYN_Y = "task", "level"
HORIZON = 10.0
N = 8
P, Q = "p", "q"
A_CELLS: dict[tuple[str, float, str], tuple[int, int]] = {
    ("base", 1.0, P): (N, 0), ("base", 2.0, P): (N, 0),
    ("only-a", 1.0, P): (N, 0), ("only-a", 2.0, P): (N, 0),
    ("only-b", 1.0, P): (N, 0),
    ("err-a", 1.0, P): (N, 0), ("err-a", 2.0, P): (0, N),
    ("err-b", 1.0, P): (N, 0), ("err-b", 2.0, P): (N, 0),
    ("err-both", 1.0, P): (N, 0), ("err-both", 2.0, P): (0, N),
    ("err-a-only", 1.0, P): (N, 0), ("err-a-only", 2.0, P): (0, N),
    ("err-b-only", 1.0, P): (N, 0),
    ("mixed", 1.0, P): (6, 2), ("mixed", 2.0, P): (7, 1),
    ("unsampled", 1.0, P): (N, 0),
    ("multi", 1.0, P): (N, 0), ("multi", 2.0, P): (N, 0),
    ("ghost", 1.0, P): (6, 2),
}
B_CELLS: dict[tuple[str, float, str], tuple[int, int]] = {
    ("base", 1.0, P): (N, 0), ("base", 2.0, P): (N, 0),
    ("only-a", 1.0, P): (N, 0),
    ("only-b", 1.0, P): (N, 0), ("only-b", 2.0, P): (N, 0),
    ("err-a", 1.0, P): (N, 0), ("err-a", 2.0, P): (N, 0),
    ("err-b", 1.0, P): (N, 0), ("err-b", 2.0, P): (0, N),
    ("err-both", 1.0, P): (N, 0), ("err-both", 2.0, P): (0, N),
    ("err-a-only", 1.0, P): (N, 0),
    ("err-b-only", 1.0, P): (N, 0), ("err-b-only", 2.0, P): (0, N),
    ("mixed", 1.0, P): (5, 3), ("mixed", 2.0, P): (6, 2),
    ("unsampled", 1.0, P): (N, 0),
    ("multi", 1.0, P): (N, 0), ("multi", 2.0, Q): (N, 0),
}
# Section 0.3's cause for every non-comparable coverage row of the pair, by (task, level, variant).
EXPECTED_CAUSES: dict[tuple[str, float, str], str] = {
    ("only-a", 2.0, P): "only_a",
    ("only-b", 2.0, P): "only_b",
    ("err-a", 2.0, P): "no_outcome_a",
    ("err-b", 2.0, P): "no_outcome_b",
    ("err-both", 2.0, P): "no_outcome_both",
    ("err-a-only", 2.0, P): "only_a",
    ("err-b-only", 2.0, P): "only_b",
    ("multi", 2.0, P): "only_a",
    ("multi", 2.0, Q): "only_b",
    ("ghost", 1.0, P): "only_a",
}
# The grid holes of the pair's report by coordinates, with the expected (config_hash, cause).
EXPECTED_GRID_HOLES: dict[tuple[str, float], tuple[tuple[str, float, str] | None, str]] = {
    ("only-a", 2.0): (("only-a", 2.0, P), "only_a"),
    ("only-b", 2.0): (("only-b", 2.0, P), "only_b"),
    ("err-a", 2.0): (("err-a", 2.0, P), "no_outcome_a"),
    ("err-b", 2.0): (("err-b", 2.0, P), "no_outcome_b"),
    ("err-both", 2.0): (("err-both", 2.0, P), "no_outcome_both"),
    ("err-a-only", 2.0): (("err-a-only", 2.0, P), "only_a"),
    ("err-b-only", 2.0): (("err-b-only", 2.0, P), "only_b"),
    ("unsampled", 2.0): (None, "unsampled"),
    ("multi", 2.0): (None, "multiple"),
}
OFF_GRID = (("ghost", 1.0, P), ("multi", 2.0, P), ("multi", 2.0, Q))
COMPARABLE_WITH_ERRORS = ("mixed", 1.0, P)

HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
TIMES_100_RE = re.compile(r"\*\s*100\b")
FLOAT_SPEC_RE = re.compile(r":\.\d")
FLOAT_TOKEN_RE = re.compile(r"(?<![\w.])-?\d+\.\d+(?:[eE][-+]?\d+)?|(?<![\w.])-?\d+[eE][-+]?\d+")
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)
SCRIPT_RE = re.compile(r"<script\b.*?</script>", re.S)
STYLE_RE = re.compile(r"<style\b.*?</style>", re.S)
DETAILS_RE = re.compile(r"<details\b.*?</details>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
ORDER_RE = re.compile(r"var order = \[(.*?)\];", re.S)
VOID_TAGS = {"br", "meta", "img", "hr", "input", "link", "col", "area", "base", "wbr"}


# ---------- harness ----------


def viewer() -> Any:
    import poisson_prove.viewer as module

    return module


def viewer_source() -> str:
    return (Path(poisson_prove.__file__).resolve().parent / "viewer.py").read_text()


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def run_cli(argv: Sequence[str]) -> Result:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


DIFF_VERDICT_WORDS = frozenset({
    "worse", "safer", "trade", "no significant change", "too small to tell", "mixed", "higher", "lower",
})


def run_names(root: Path) -> dict[str, str]:
    """PF2 (spec section 4.3/5.3): every run has a name; ``runs --json`` maps each id to it."""
    r = run_cli(["--store", str(root), "runs", "--json"])
    assert r.code == 0, r.text
    return {entry["run_id"]: entry["run_name"] for entry in json.loads(r.out)["runs"]}


def after_verdict_block(out: str, name_a: str, name_b: str) -> str:
    """PF2 (spec section 4.3/5.3): ``diff`` prints a verdict block first -- the verdict line, then
    ``  method``, ``  before <name A>``, ``  after <name B>`` (and any ``  trade`` lines) -- then one
    blank line, then the text as before. Check the block's shape and return what follows it."""
    block, sep, rest = out.partition("\n\n")
    assert sep, out
    lines = block.split("\n")
    assert lines[0].split("  ")[0] in DIFF_VERDICT_WORDS, out
    assert [line.split("  ")[1] for line in lines[1:4]] == ["method", "before", "after"], out
    assert lines[2] == f"  before  {name_a}" and lines[3] == f"  after  {name_b}", out
    assert all(line.startswith("  trade  ") for line in lines[4:]), out
    return rest


def tripwire_serve(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def trip(*args: Any, **kwargs: Any) -> None:
        calls.append("serve_page")
        raise AssertionError("serve_page was called; something was about to bind")

    monkeypatch.setattr(viewer(), "serve_page", trip)
    monkeypatch.setattr(cli, "serve_page", trip, raising=False)
    return calls


def strict_loads(text: str) -> Any:
    def fail(token: str) -> Any:
        raise ValueError(f"non-JSON constant {token!r}")

    return json.loads(text, parse_constant=fail)


def walk_keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from walk_keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_keys(v)


def walk_key_paths(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Every dict key at every depth as ``(dotted path, key)``; a list index is not part of the path."""
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


def excised(page: str, *patterns: re.Pattern[str]) -> str:
    for pattern in patterns:
        page = pattern.sub("", page)
    return page


def visible_text(page: str) -> str:
    return html_unescape(TAG_RE.sub(" ", excised(page, SVG_RE, SCRIPT_RE, STYLE_RE, DETAILS_RE)))


def key_of(event: str, config_hash: str) -> str:
    return f"{event} {config_hash}"


def is_scalar(value: Any) -> bool:
    return isinstance(value, (bool, int, float, str))


# ---------- a small DOM ----------


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

    def script_json(self, block_id: str) -> str:
        scripts = self.find("script", id=block_id)
        assert len(scripts) == 1, (block_id, len(scripts))
        return scripts[0].text


def parse_html(text: str) -> Dom:
    dom = Dom()
    dom.feed(text)
    dom.close()
    return dom


def descendants(node: Node, tag: str) -> list[Node]:
    out = []
    for child in node.children:
        if child.tag == tag:
            out.append(child)
        out.extend(descendants(child, tag))
    return out


def table_header(table: Node) -> list[str]:
    return [th.deep_text() for th in descendants(table, "th")]


def table_rows(table: Node) -> list[list[str]]:
    rows = [[td.deep_text() for td in descendants(tr, "td")] for tr in descendants(table, "tr")]
    return [r for r in rows if r]


def table_with_header(dom: Dom, header: Sequence[str]) -> Node:
    tables = [t for t in dom.find("table") if table_header(t) == list(header)]
    assert len(tables) == 1, (list(header), len(tables))
    return tables[0]


def h2_named(dom: Dom, text: str) -> Node:
    found = [n for n in dom.find("h2") if n.deep_text() == text]
    assert len(found) == 1, (text, len(found))
    return found[0]


def nodes_between(dom: Dom, start: int, stop: int) -> list[Node]:
    return [n for n in dom.nodes if start < n.index < stop]


# ---------- ast helpers (restated; never imported across test modules) ----------


def module_functions(tree: ast.Module) -> dict[str, ast.AST]:
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}


def closure(tree: ast.Module, name: str) -> list[ast.AST]:
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
    """The S20 walk, verbatim, AugAssign trap included: ``+=`` anywhere in the closure errors
    the test rather than failing it, which is stricter than the spec's letter and is its intent."""
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


def store_imports(body: Sequence[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for node in body:
        if isinstance(node, ast.ImportFrom) and node.module == "poisson_prove.store":
            names.update(alias.name for alias in node.names)
    return names


def type_checking_body(tree: ast.Module) -> list[ast.stmt]:
    blocks = [
        n for n in tree.body
        if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "TYPE_CHECKING"
    ]
    assert len(blocks) == 1, len(blocks)
    return blocks[0].body


# ---------- store builders ----------


def syn_config(task: str, level: float, variant: str) -> dict[str, Any]:
    return {"task": task, "level": level, "variant": variant, "flag": True, "tags": ["t1"]}


def hash_of(key: tuple[str, float, str]) -> str:
    return config_hash(syn_config(*key))


def syn_manifest(run_id: str, note: str = "built by test_s21_errors") -> RunManifest:
    return RunManifest(
        run_id=run_id,
        target_id="synthetic@v0",
        t_unit="steps",
        run_salt=SYN_SALT,
        axis_types={"task": "categorical", "level": "continuous"},
        backend="synthetic",
        environment={"note": note},
    )


def seed_of(config: Mapping[str, Any], replicate_index: int) -> int:
    """A stored seed that is a function of ``(config, replicate_index)`` and never of the cell's
    position in its dict. **C49's fourth fixture, found by P-1 Session A and fixed in its
    retrofit** (the spec's section 7.3 names three): ``write_run`` seeded ``1000 * index + k`` by
    dict position, and the synthetic pair's two arms enumerate different cell sets (``only_a`` and
    ``only_b`` holes are the point of the pair), so the same ``(config_hash, replicate_index)``
    carried a different seed in the two arms -- 16 of 99 matched rows disagreed, measured on the
    P-1 prototype, and ``diff --methods all`` (E12) refused under ``mcnemar_bh``. Green before and
    after on the bare tree (nothing reads a stored seed there), so its green is not evidence."""
    return 1000 * (int(config_hash(config)[:6], 16) % 100_000) + replicate_index


def write_run(
    store: Store,
    run_id: str,
    cells: dict[tuple[str, float, str], tuple[int, int]],
    *,
    fail_share: int,
) -> None:
    """A complete synthetic run: per cell ``n_ok`` rows with an outcome (``n_ok // fail_share``
    end in ``fail`` at t=3, the rest in ``ok`` at the horizon) then ``n_err`` errored rows whose
    errors cycle through ``ERRORS``. Replicate indices run 0.. over both kinds."""
    store.create_run(syn_manifest(run_id))
    records = []
    for (task, level, variant), (n_ok, n_err) in cells.items():
        config = syn_config(task, level, variant)
        fails = n_ok // fail_share
        for k in range(n_ok):
            episode = (
                Episode(outcome="fail", t=3.0, horizon=HORIZON)
                if k < fails
                else Episode(outcome="ok", t=HORIZON, horizon=HORIZON)
            )
            records.append(
                EpisodeRecord.from_episode(
                    episode, run_id=run_id, config=config, seed=seed_of(config, k),
                    replicate_index=k, wall_time=0.0,
                )
            )
        for j in range(n_err):
            records.append(
                EpisodeRecord.errored(
                    run_id=run_id, config=config, seed=seed_of(config, n_ok + j),
                    replicate_index=n_ok + j, error=ERRORS[j % len(ERRORS)], wall_time=0.0,
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


def errored_run(store: Store, run_id: str, errors: Sequence[str], outcomes: int) -> None:
    """One run of ``outcomes`` rows with an outcome and one errored row per entry of ``errors``,
    every row in its own cell."""
    store.create_run(syn_manifest(run_id))
    records = []
    for k in range(outcomes):
        records.append(
            EpisodeRecord.from_episode(
                Episode(outcome="ok", t=HORIZON, horizon=HORIZON), run_id=run_id,
                config={"cell": float(k)}, seed=k, replicate_index=0, wall_time=0.0,
            )
        )
    for k, error in enumerate(errors):
        records.append(
            EpisodeRecord.errored(
                run_id=run_id, config={"cell": float(outcomes + k)}, seed=outcomes + k,
                replicate_index=0, error=error, wall_time=0.0,
            )
        )
    store.append(run_id, records)
    store.mark_complete(run_id)


def poison_parts(run_dir: Path) -> int:
    """The R5 pattern restated and widened: every ``meta`` AND every ``config`` cell of every
    part becomes a string that is not JSON, each part keeping its own schema."""
    poisoned = 0
    for part in sorted((run_dir / "episodes").glob("part-*.parquet")):
        table = pq.read_table(part)
        for column in ("meta", "config"):
            index = table.schema.get_field_index(column)
            table = table.set_column(
                index, table.schema.field(index), pa.array([POISON] * table.num_rows, pa.string())
            )
        pq.write_table(table, part)
        poisoned += table.num_rows
    return poisoned


def write_foreign_row(root: Path, run_id: str) -> None:
    """A row with a null outcome AND a null error, which ``EpisodeRecord`` refuses, written into
    a new part directly with pyarrow under the existing part's own schema."""
    parts = sorted((root / run_id / "episodes").glob("part-*.parquet"))
    schema = pq.read_table(parts[0]).schema
    row = {
        "run_id": run_id, "config_hash": "f" * 16, "config": "{}", "seed": 0,
        "replicate_index": 1, "outcome": None, "t": None, "horizon": None, "confidence": None,
        "meta": "{}", "error": None, "wall_time": 0.0, "backend_meta": "{}",
    }
    pq.write_table(
        pa.Table.from_pylist([row], schema=schema), parts[0].parent / "part-00001.parquet"
    )


@dataclass(frozen=True)
class Built:
    root: Path
    store: Store
    a: str
    b: str
    spec: ReportSpec
    events: tuple[str, ...]
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


def built(root: Path, a: str, b: str, spec: ReportSpec, events: Sequence[str]) -> Built:
    """S29 (``proofload.viewpair/3``) makes M14's tree a required input to assembly, so the
    fixture grows it on the frames it already reads, at M14's defaults, and passes ``tree=``."""
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
    return Built(root, store, a, b, spec, tuple(events), multi, report, nested, structure, viewer().render_html(structure))


def coverage_of(b: Built) -> pd.DataFrame:
    frame = b.multi.coverage
    assert frame is not None
    return frame


def coverage_row(b: Built, key: tuple[str, float, str]) -> dict[str, Any]:
    frame = coverage_of(b)
    hits = frame[frame["config_hash"] == hash_of(key)]
    assert len(hits) == 1, (key, len(hits))
    return dict(hits.iloc[0])


def grid_holes(b: Built, event: str | None = None) -> list[Any]:
    panel = b.report.panels[event if event is not None else b.report.events[0]]
    return [c for c in panel.cells if not c.present]


def grid_hashes(b: Built) -> set[str]:
    return {
        str(c.config_hash)
        for panel in b.report.panels.values()
        for c in panel.cells
        if c.config_hash is not None
    }


def off_grid_hashes(b: Built) -> list[str]:
    frame = coverage_of(b)
    on_grid = grid_hashes(b)
    return sorted(str(h) for h in frame.loc[~frame["comparable"], "config_hash"] if str(h) not in on_grid)


def valid_hashes(frame: pd.DataFrame) -> set[str]:
    return set(frame.loc[frame["outcome"].notna(), "config_hash"].astype(str))


def direct_counts(frame: pd.DataFrame, h: str) -> tuple[int, int]:
    mine = frame["config_hash"].astype(str) == h
    return int(mine.sum()), int((mine & frame["outcome"].isna()).sum())


def hand_built_multi(multi: MultiDiffResult) -> MultiDiffResult:
    """The M7 oracle's ``make_multi`` shape: every existing field by keyword, ``coverage`` never
    named."""
    return MultiDiffResult(**{name: getattr(multi, name) for name in MULTI_FIELDS})


def hand_built_diff(multi: MultiDiffResult, event: str) -> DiffResult:
    ev = multi.by_event[event]
    return DiffResult(
        cells=ev.cells, method=multi.method, seed_identity_match=multi.seed_identity_match,
        unpaired_analysis=multi.unpaired_analysis, q=multi.q, event=event,
        t_unit=multi.t_unit, horizon=multi.horizon, n_safer=ev.n_safer, n_worse=ev.n_worse,
        n_unchanged=ev.n_unchanged, n_not_comparable=multi.n_not_comparable, max_mde=ev.max_mde,
        dropped_a=multi.dropped_a, dropped_b=multi.dropped_b, truncated=multi.truncated,
        max_mde_unchanged=ev.max_mde_unchanged, max_mde_unchanged_cell=ev.max_mde_unchanged_cell,
    )


def coverage_line(frame: pd.DataFrame) -> str:
    holes = frame[~frame["comparable"]]
    counts = {c: int((holes["cause"] == c).sum()) for c in CAUSES}
    return (
        f"coverage: holes={len(holes)} (only_a={counts['only_a']}, only_b={counts['only_b']}, "
        f"no_outcome_a={counts['no_outcome_a']}, no_outcome_b={counts['no_outcome_b']}, "
        f"no_outcome_both={counts['no_outcome_both']}), "
        f"no_outcome a={int(frame['no_outcome_a'].sum())} b={int(frame['no_outcome_b'].sum())}"
    )


def md_cell(value: Any) -> str:
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def coverage_block(frame: pd.DataFrame) -> str:
    """What ``diff``'s text output appends after the markdown: the summary line, one blank
    line, ``## coverage``, one blank line, the table over ``COVERAGE_COLUMNS``."""
    header = "| " + " | ".join(COVERAGE_COLUMNS) + " |"
    rule = "|" + "|".join("---" for _ in COVERAGE_COLUMNS) + "|"
    rows = [
        "| " + " | ".join(md_cell(row[c]) for c in COVERAGE_COLUMNS) + " |"
        for row in frame.to_dict(orient="records")
    ]
    return "\n".join([coverage_line(frame), "", "## coverage", "", header, rule, *rows]) + "\n"


# The command line prints its text, report.md, receipt.html and the heatmap's labels under rule 10
# (spec section 5.4), which PF1 changes; the library renderers it calls do not change. So a
# digest or an exact comparison over what the command line printed or wrote is replaced by two
# checks: the library's rendering still gives the frozen digest or text, and the printed text
# carries the same numbers, verdicts and cells as that rendering, each number equal to the
# library's or to its percentage points read as a fraction, within the coarser of the two printed
# precisions, and every config hash cut to 12 hex characters (a 12-hex token is a hash, not a
# number).
RENDERED_NUMBER = re.compile(r"(?<![\w.])(?![0-9a-f]{12}\b)[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?(?:pp|%)?(?![\w]|\.\d)")


def rendered_value(token: str) -> tuple[float, float]:
    """A printed number and half a unit of its last printed digit."""
    text = token.replace(",", "").removesuffix("pp").removesuffix("%")
    m = re.fullmatch(r"[-+]?\d+(?:\.(\d+))?(?:[eE]([-+]?\d+))?", text)
    assert m, token
    return float(text), 0.5 * 10.0 ** (int(m.group(2) or 0) - len(m.group(1) or ""))


def same_number(library: str, written: str) -> bool:
    a, half_a = rendered_value(library)
    w, half_w = rendered_value(written)
    return abs(w - a) <= max(half_a, half_w) + 1e-12 or abs(w - a / 100) <= max(half_a / 100, half_w) + 1e-12


class RenderedUnits(HTMLParser):
    """The text nodes of an HTML or SVG file in order, each marked when it is a table cell, and
    every start tag with its attributes (the geometry)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.units: list[tuple[bool, str]] = []
        self.tags: list[tuple[str, list[tuple[str, str | None]]]] = []
        self.open: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, attrs))
        self.open.append(tag)

    def handle_endtag(self, tag: str) -> None:
        while self.open and self.open.pop() != tag:
            pass

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.units.append((bool(self.open) and self.open[-1] == "td", data))


def rendered_units(text: str, name: str) -> tuple[list[tuple[bool, str]], list[Any]]:
    if not name.endswith(".md"):
        parser = RenderedUnits()
        parser.feed(text)
        return parser.units, parser.tags
    lines = text.splitlines()
    units: list[tuple[bool, str]] = []
    for i, line in enumerate(lines):
        header = i + 1 < len(lines) and lines[i + 1].startswith("|---")
        if line.startswith("|") and not header and not line.startswith("|---"):
            units += [(True, cell) for cell in line.strip("|").split(" | ")]
        else:
            units.append((False, line))
    return units, []


def rendered_problems(library: str, written: str, name: str) -> list[Any]:
    """Where ``written`` does not carry ``library``'s facts: the same tags and attributes, the same
    lines or text nodes, the same numbers in each, and the same words in each table cell that
    holds no number (the verdicts, events and labels)."""
    lib_units, lib_tags = rendered_units(library, name)
    out_units, out_tags = rendered_units(written, name)
    problems: list[Any] = [] if lib_tags == out_tags else ["the tags or their attributes differ"]
    if len(lib_units) != len(out_units):
        return [*problems, f"{len(lib_units)} lines or text nodes, not {len(out_units)}"]
    for (cell, a), (_, w) in zip(lib_units, out_units, strict=True):
        na, nw = RENDERED_NUMBER.findall(a), RENDERED_NUMBER.findall(w)
        numbers_agree = len(na) == len(nw) and all(same_number(x, y) for x, y in zip(na, nw, strict=True))
        if not numbers_agree or (cell and not na and a.strip() != w.strip()):
            problems.append((a, w))
    return problems


def shortened(text: str) -> str:
    """``text`` with every 16-hex config hash cut to its first 12 characters, as the command line
    prints a hash in text (spec section 5.4, rule 10)."""
    return re.sub(r"\b([0-9a-f]{12})[0-9a-f]{4}\b", r"\1", text)


def diff_argv(root: Path, *extra: str) -> list[str]:
    argv = ["--store", str(root), "diff", SYN_A, SYN_B]
    for e in SYN_EVENTS:
        argv += ["--event", e]
    return argv + list(extra)


def selected_cell(b: Built) -> dict[str, Any]:
    dom = parse_html(b.page)
    chosen = [o.attrs["value"] for o in dom.find("option") if "selected" in o.attrs]
    assert len(chosen) == 1, chosen
    cells = {
        key_of(p["event"], c["config_hash"]): c for p in b.structure["panels"] for c in p["cells"]
    }
    return cells[chosen[0]]


def serve_argv(b: Built, *extra: str) -> list[str]:
    argv = ["--store", str(b.root), "serve", b.a, b.b]
    for e in b.events:
        argv += ["--event", e]
    argv += ["--x", b.spec.x_axis]
    if b.spec.y_axis is not None:
        argv += ["--y", b.spec.y_axis]
    for k, v in b.spec.fixed.items():
        argv += ["--fix", f"{k}={json.dumps(v)}"]
    return argv + list(extra)


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def syn_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("syn-store")
    store = Store(root)
    write_run(store, SYN_A, A_CELLS, fail_share=2)
    write_run(store, SYN_B, B_CELLS, fail_share=4)
    return root


@pytest.fixture(scope="module")
def syn_multi(syn_root: Path) -> MultiDiffResult:
    """M6's result alone, for the M6/M10 clauses that need no report or structure."""
    store = Store(syn_root)
    ma, mb = store.manifest(SYN_A), store.manifest(SYN_B)
    return multi_diff(store.read(SYN_A), store.read(SYN_B), events=list(SYN_EVENTS), manifest_a=ma, manifest_b=mb)


@pytest.fixture(scope="module")
def syn(syn_root: Path) -> Built:
    return built(syn_root, SYN_A, SYN_B, ReportSpec(title="syn", x_axis=SYN_X, y_axis=SYN_Y), SYN_EVENTS)


@pytest.fixture(scope="module")
def syn_fixed(syn_root: Path) -> Built:
    spec = ReportSpec(title="syn fixed", x_axis=SYN_X, y_axis=SYN_Y, fixed={"variant": P})
    return built(syn_root, SYN_A, SYN_B, spec, SYN_EVENTS)


@pytest.fixture(scope="module")
def go1(go1_store: Store) -> Built:
    return built(GO1_ROOT, GO1_A, GO1_B, ReportSpec(title=GO1_TITLE, x_axis=GO1_X, y_axis=GO1_Y), GO1_EVENTS)


@pytest.fixture(scope="module")
def builts(go1: Built, syn: Built) -> tuple[Built, Built]:
    return go1, syn


@pytest.fixture(scope="module")
def tally_store(tmp_path_factory: pytest.TempPathFactory) -> Store:
    store = Store(tmp_path_factory.mktemp("tally-store"))
    errored_run(store, COUNTED, [TIMEOUT_MARK] * K_T + [ERRORS[1]] * K_I + ["boom"] * K_O, K_OK)
    store.create_run(syn_manifest(EMPTY))
    store.create_run(replace(syn_manifest(SCHEMA_TWO), schema_version=2))
    return store


@pytest.fixture(scope="module")
def poisoned_root(tmp_path_factory: pytest.TempPathFactory, syn_root: Path) -> Path:
    root = tmp_path_factory.mktemp("poisoned-store")
    shutil.copytree(syn_root / SYN_A, root / SYN_A)
    assert poison_parts(root / SYN_A) == Store(syn_root).count(SYN_A)
    return root


@pytest.fixture(scope="module")
def foreign_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("foreign-store")
    errored_run(Store(root), "foreign", [], 1)
    write_foreign_row(root, "foreign")
    return root


@pytest.fixture(scope="module")
def three_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("three-store")
    errored_run(Store(root), "three", list(ERRORS), 2)
    return root


@pytest.fixture(scope="module")
def every_store(
    go1_store: Store, syn_root: Path, tally_store: Store, poisoned_root: Path,
    foreign_root: Path, three_root: Path,
) -> list[tuple[Store, str]]:
    return [
        (go1_store, GO1_A), (go1_store, GO1_B),
        (Store(syn_root), SYN_A), (Store(syn_root), SYN_B),
        (tally_store, COUNTED), (tally_store, EMPTY),
        (Store(poisoned_root), SYN_A),
        (Store(foreign_root), "foreign"), (Store(three_root), "three"),
    ]


@dataclass(frozen=True)
class Served:
    result: Result
    calls: list[str]


def serve_json(argv: Sequence[str]) -> Served:
    with pytest.MonkeyPatch.context() as mp:
        calls = tripwire_serve(mp)
        return Served(run_cli(argv), calls)


@pytest.fixture(scope="module")
def go1_serve_json(go1: Built) -> Served:
    return serve_json(serve_argv(go1, "--title", GO1_TITLE, "--json"))


@pytest.fixture(scope="module")
def syn_serve_json(syn: Built) -> Served:
    # PF3 (Q17, spec sections 4.4 and 14; rule R1): the synthetic pair's manifests carry one salt, so the
    # default is now the paired test; the structure E24 compares with is the unpaired test's, named.
    return serve_json(serve_argv(syn, "--title", "syn", "--json", "--method", "fisher_bh"))


# ---------- E1-E5: RunTally and Store.tally ----------


def test_e1_tally_counts_the_four_buckets_and_the_two_sums_hold(tally_store: Store) -> None:
    t = tally_store.tally(COUNTED)
    assert t.rows == t.with_outcome + t.no_outcome
    assert t.no_outcome == t.timed_out + t.infra + t.other
    assert (t.with_outcome, t.timed_out, t.infra, t.other) == (K_OK, K_T, K_I, K_O)
    assert t.rows == K_OK + K_T + K_I + K_O


def test_e1_the_empty_run_is_six_zeros(tally_store: Store) -> None:
    assert tally_store.tally(EMPTY).to_dict() == dict.fromkeys(TALLY_FIELDS, 0)


def test_e1_an_unknown_run_raises_store_error(tally_store: Store) -> None:
    with pytest.raises(StoreError):
        tally_store.tally("no-such-run")


def test_e1_schema_version_two_raises_schema_mismatch_from_tally_and_nothing_from_count(tally_store: Store) -> None:
    with pytest.raises(SchemaMismatch):
        tally_store.tally(SCHEMA_TWO)
    assert tally_store.count(SCHEMA_TWO) == 0


def test_e2_tally_is_identical_on_the_config_and_meta_poisoned_copy(syn_root: Path, poisoned_root: Path) -> None:
    clean = Store(syn_root).tally(SYN_A)
    assert clean.no_outcome > 0
    assert Store(poisoned_root).tally(SYN_A) == clean


def test_e2_the_poisoned_copy_raises_on_both_reads(poisoned_root: Path) -> None:
    store = Store(poisoned_root)
    with pytest.raises(ValueError):
        store.read(SYN_A)
    with pytest.raises(ValueError):
        store.read(SYN_A, meta=False)


def test_e2_a_tmp_part_changes_neither_tally_nor_count(syn_root: Path, tmp_path: Path) -> None:
    shutil.copytree(syn_root / SYN_A, tmp_path / SYN_A)
    store = Store(tmp_path)
    before = (store.tally(SYN_A), store.count(SYN_A))
    (tmp_path / SYN_A / "episodes" / TMP_PART).write_bytes(b"half written")
    assert (store.tally(SYN_A), store.count(SYN_A)) == before


def test_e3_the_store_markers_equal_the_executors_constants() -> None:
    assert store_module._TIMEOUT_MARK == executor._TIMEOUT_ERROR == TIMEOUT_MARK
    assert store_module._INFRA_MARK == executor_modal._INFRA_PREFIX == INFRA_MARK


def test_e3_a_timeout_prefixed_error_is_other_not_timed_out(tmp_path: Path) -> None:
    store = Store(tmp_path)
    errored_run(store, "prefixed", ["timeout: slow"], 0)
    t = store.tally("prefixed")
    assert (t.timed_out, t.other, t.no_outcome) == (0, 1, 1)


def test_e3_a_null_outcome_null_error_row_is_no_outcome_and_other(foreign_root: Path) -> None:
    t = Store(foreign_root).tally("foreign")
    assert t.to_dict() == {
        "rows": 2, "with_outcome": 1, "no_outcome": 1, "timed_out": 0, "infra": 0, "other": 1,
    }


def test_e4_go1_both_arms_tally_12800_with_outcome_and_no_errored_rows(go1_store: Store) -> None:
    for run_id in (GO1_A, GO1_B):
        assert dataclasses.astuple(go1_store.tally(run_id)) == GO1_TALLY, run_id


def test_e4_tally_rows_equals_count_in_every_store_the_oracle_builds(every_store: list[tuple[Store, str]]) -> None:
    assert len(every_store) == 9
    for store, run_id in every_store:
        assert store.tally(run_id).rows == store.count(run_id), run_id


def test_e5_to_dict_has_exactly_the_six_keys_in_order(tally_store: Store) -> None:
    t = tally_store.tally(COUNTED)
    assert tuple(t.to_dict()) == TALLY_FIELDS
    assert t.to_dict() == {name: getattr(t, name) for name in TALLY_FIELDS}
    assert all(type(v) is int for v in t.to_dict().values())


def test_e5_run_tally_is_a_frozen_dataclass_of_the_six_fields() -> None:
    run_tally = store_module.RunTally
    assert tuple(f.name for f in dataclasses.fields(run_tally)) == TALLY_FIELDS
    assert run_tally.__dataclass_params__.frozen


def test_e5_the_public_surface_gains_exactly_tally_and_run_tally() -> None:
    methods = {
        name for name, _ in inspect.getmembers(Store, inspect.isfunction)
        if not name.startswith("_")
    }
    assert methods == PUBLIC_STORE_METHODS
    public = {
        name
        for name, obj in vars(store_module).items()
        if not name.startswith("_") and getattr(obj, "__module__", None) == store_module.__name__
    }
    assert public == PUBLIC_STORE_SYMBOLS
    assert list(inspect.signature(Store.tally).parameters) == ["self", "run_id"]


# ---------- E6-E12, E27: the coverage frame ----------


def test_e6_coverage_has_the_columns_and_one_row_per_hash_in_the_union_sorted(syn: Built) -> None:
    frame = coverage_of(syn)
    assert list(frame.columns) == list(COVERAGE_COLUMNS) == list(diff_module.COVERAGE_COLUMNS)
    a, b = syn.store.read(SYN_A), syn.store.read(SYN_B)
    union = set(a["config_hash"].astype(str)) | set(b["config_hash"].astype(str))
    assert list(frame["config_hash"]) == sorted(union)


def test_e6_the_seven_cases_carry_the_named_causes(syn: Built) -> None:
    cases = {
        ("only-a", 2.0, P): "only_a",
        ("only-b", 2.0, P): "only_b",
        ("err-a", 2.0, P): "no_outcome_a",
        ("err-b", 2.0, P): "no_outcome_b",
        ("err-both", 2.0, P): "no_outcome_both",
        ("err-a-only", 2.0, P): "only_a",
    }
    for key, cause in cases.items():
        assert coverage_row(syn, key)["cause"] == cause, key
    mixed = coverage_row(syn, COMPARABLE_WITH_ERRORS)
    assert mixed["cause"] is None and bool(mixed["comparable"])
    assert mixed["no_outcome_a"] > 0 and mixed["no_outcome_b"] > 0


def test_e6_every_count_equals_a_direct_count_on_the_raw_frame(syn: Built) -> None:
    frame = coverage_of(syn)
    a, b = syn.store.read(SYN_A), syn.store.read(SYN_B)
    for row in frame.to_dict(orient="records"):
        h = str(row["config_hash"])
        assert (row["rows_a"], row["no_outcome_a"]) == direct_counts(a, h), h
        assert (row["rows_b"], row["no_outcome_b"]) == direct_counts(b, h), h
        source = a if row["rows_a"] > 0 else b
        assert row["config"] == source.loc[source["config_hash"] == h, "config"].iloc[0], h


def test_e7_comparable_rows_are_every_events_cells_and_carry_no_cause(syn: Built) -> None:
    frame = coverage_of(syn)
    comparable = frame[frame["comparable"]]
    for event in syn.multi.events:
        assert comparable["config_hash"].tolist() == syn.multi.by_event[event].cells["config_hash"].tolist(), event
    assert all(c is None for c in comparable["cause"])
    holes = frame[~frame["comparable"]]
    assert len(holes) == len(EXPECTED_CAUSES)
    assert all(c in CAUSES for c in holes["cause"])


def test_e8_coverage_is_built_from_the_raw_frames_so_errored_both_is_visible(syn: Built) -> None:
    both = hash_of(("err-both", 2.0, P))
    a, b = syn.store.read(SYN_A), syn.store.read(SYN_B)
    assert both not in valid_hashes(a) and both not in valid_hashes(b)
    row = coverage_row(syn, ("err-both", 2.0, P))
    assert row["cause"] == "no_outcome_both"
    assert (row["rows_a"], row["no_outcome_a"], row["rows_b"], row["no_outcome_b"]) == (N, N, N, N)


def test_e9_n_equals_rows_minus_no_outcome_for_every_comparable_hash(syn: Built) -> None:
    frame = coverage_of(syn).set_index("config_hash")
    for event in syn.multi.events:
        cells = syn.multi.by_event[event].cells
        assert len(cells)
        for row in cells.to_dict(orient="records"):
            cov = frame.loc[str(row["config_hash"])]
            assert row["n_a"] == cov["rows_a"] - cov["no_outcome_a"], (event, row["config_hash"])
            assert row["n_b"] == cov["rows_b"] - cov["no_outcome_b"], (event, row["config_hash"])


def test_e9_truncation_re_censors_rows_and_changes_no_coverage_count(syn: Built) -> None:
    a, b = syn.store.read(SYN_A), syn.store.read(SYN_B)
    shorter = b.copy()
    shorter.loc[shorter["horizon"].notna(), "horizon"] = HORIZON / 2
    ma, mb = syn.store.manifest(SYN_A), syn.store.manifest(SYN_B)
    result = multi_diff(a, shorter, events=list(SYN_EVENTS), manifest_a=ma, manifest_b=mb)
    assert result.truncated > 0
    frame = result.coverage
    assert frame is not None
    pd.testing.assert_frame_equal(
        frame[list(COVERAGE_CELL_KEYS)], coverage_of(syn)[list(COVERAGE_CELL_KEYS)]
    )
    indexed = frame.set_index("config_hash")
    for event in result.events:
        for row in result.by_event[event].cells.to_dict(orient="records"):
            cov = indexed.loc[str(row["config_hash"])]
            assert row["n_a"] == cov["rows_a"] - cov["no_outcome_a"], (event, row["config_hash"])
            assert row["n_b"] == cov["rows_b"] - cov["no_outcome_b"], (event, row["config_hash"])


def test_e10_the_column_sums_are_the_frame_totals(syn: Built) -> None:
    frame = coverage_of(syn)
    a, b = syn.store.read(SYN_A), syn.store.read(SYN_B)
    assert int(frame["rows_a"].sum()) == len(a)
    assert int(frame["rows_b"].sum()) == len(b)
    assert int(frame["no_outcome_a"].sum()) == int(a["outcome"].isna().sum())
    assert int(frame["no_outcome_b"].sum()) == int(b["outcome"].isna().sum())


def test_e10_through_the_cli_the_sums_are_the_store_tallies(syn: Built) -> None:
    # --json replaces --format json on diff (spec section 5.6).
    r = run_cli(diff_argv(syn.root, "--method", "fisher_bh", "--json"))
    assert r.code == 0, r.text
    records = json.loads(r.out)["coverage"]
    assert records
    ta, tb = syn.store.tally(SYN_A), syn.store.tally(SYN_B)
    assert sum(rec["rows_a"] for rec in records) == ta.rows
    assert sum(rec["no_outcome_a"] for rec in records) == ta.no_outcome
    assert sum(rec["rows_b"] for rec in records) == tb.rows
    assert sum(rec["no_outcome_b"] for rec in records) == tb.no_outcome


def test_e11_dropped_counts_are_the_cause_algebra_exactly(syn: Built) -> None:
    frame = coverage_of(syn)
    cause = frame["cause"]
    with_a = frame["no_outcome_a"] < frame["rows_a"]
    with_b = frame["no_outcome_b"] < frame["rows_b"]
    assert syn.multi.dropped_a == int((cause == "no_outcome_b").sum()) + int(((cause == "only_a") & with_a).sum())
    assert syn.multi.dropped_b == int((cause == "no_outcome_a").sum()) + int(((cause == "only_b") & with_b).sum())
    assert syn.multi.n_not_comparable == syn.multi.dropped_a + syn.multi.dropped_b
    unseen_today = int((cause == "no_outcome_both").sum()) + int(((cause == "only_a") & ~with_a).sum()) + int(((cause == "only_b") & ~with_b).sum())
    assert int((~frame["comparable"]).sum()) - syn.multi.n_not_comparable == unseen_today
    assert unseen_today == 3


def test_e12_the_cause_vocabulary_is_written_once_in_each_module() -> None:
    assert diff_module._CAUSES == CAUSES
    assert report_module._GRID_CAUSES == GRID_CAUSES


def test_e12_every_cause_anywhere_is_drawn_from_the_seven(syn: Built, syn_fixed: Built, go1: Built) -> None:
    for b in (syn, syn_fixed, go1):
        assert all(c is None or c in CAUSES for c in coverage_of(b)["cause"])
        assert all(
            c.hole_cause is None or c.hole_cause in ALL_CAUSES
            for panel in b.report.panels.values()
            for c in panel.cells
        )
        assert all(h["cause"] in ALL_CAUSES for h in b.structure["holes"])


def test_e12_a_hand_built_result_has_no_coverage_and_to_json_carries_null_or_records(syn: Built) -> None:
    bare = hand_built_multi(syn.multi)
    assert bare.coverage is None
    assert bare.to_json()["coverage"] is None
    records = syn.multi.to_json()["coverage"]
    frame = coverage_of(syn)
    assert len(records) == len(frame)
    for rec, row in zip(records, frame.to_dict(orient="records")):
        assert tuple(rec) == COVERAGE_COLUMNS
        if rec["comparable"]:
            assert rec["cause"] is None
        else:
            assert rec["cause"] == row["cause"]
        assert rec["config_hash"] == row["config_hash"]
        assert all(type(rec[k]) is int for k in COVERAGE_CELL_KEYS)
        assert type(rec["comparable"]) is bool
    json.dumps(syn.multi.to_json(), allow_nan=False)


def test_e12_to_markdown_is_unchanged_and_diff_text_appends_the_coverage_block(syn_root: Path, syn_multi: MultiDiffResult) -> None:
    """S21's property: ``to_markdown()`` carries no coverage, and ``diff``'s text output appends
    the coverage block after the markdown and after the ``--methods all`` table.

    **Narrowed 2026-09-07, from whole-stream equality to a prefix and an ordering.** The two
    assertions below read ``r.out == md + "\n" + block`` and ``every.out.endswith(...)``, which
    pinned not just this block's content and position but *everything that follows it* -- and
    so this packet owned, by accident, every later packet's right to add to the same stream.
    S24's interval block appends after coverage per its section 3.4 and was refused by that,
    with nothing wrong on either side.

    What S21 owns is the block's exact content and its position relative to what precedes it:
    immediately after the markdown with the single-method invocation, and after the method table
    under ``--methods all``. Both are still asserted exactly. What follows the block is not
    S21's to say. The whole-stream form was the only such site in the suite -- ``test_m4_read``
    compares two runs of the same command and is unaffected.
    """
    frame = syn_multi.coverage
    assert frame is not None
    md = syn_multi.to_markdown()
    assert md == hand_built_multi(syn_multi).to_markdown()
    assert "coverage" not in md
    block = coverage_block(frame)
    # The command line prints the markdown and the block under rule 10 (spec section 5.4): each
    # printed line carries the library line's numbers and table cells, hashes at 12 hex.
    md_n, block_n = len(md.splitlines()), len(block.splitlines())
    r = run_cli(diff_argv(syn_root, "--method", "fisher_bh"))
    assert r.code == 0, r.text
    # PF2 (spec section 4.3/5.3): diff's stdout opens with the verdict block naming both runs; the
    # text as before follows the first blank line, and the prefix and ordering are read there.
    names = run_names(syn_root)
    body = after_verdict_block(r.out, names[SYN_A], names[SYN_B])
    head = "".join(body.splitlines(keepends=True)[: md_n + 1 + block_n])
    assert rendered_problems(shortened(md + "\n" + block), head, "diff.md") == [], r.out
    # PF3 (Q17, spec sections 4.4 and 14; rule R1): the synthetic pair's manifests carry one salt, so the
    # default is now the paired test; the markdown --methods all prints first is the unpaired test's, named.
    every = run_cli(diff_argv(syn_root, "--methods", "all", "--method", "fisher_bh"))
    assert every.code == 0, every.text
    lines = after_verdict_block(every.out, names[SYN_A], names[SYN_B]).splitlines(keepends=True)
    assert rendered_problems(shortened(md), "".join(lines[:md_n]), "diff.md") == [], every.out
    # > and not >=: the method table sits between the markdown and the block, so the block
    # cannot begin where the markdown ends.
    at = next(i for i, line in enumerate(lines) if line.startswith("coverage: "))
    assert at > start + md_n, every.out
    assert rendered_problems(shortened(block), "".join(lines[at : at + block_n]), "diff.md") == [], every.out
    assert every.out.count("## coverage") == 1
    mixed = frame[frame["config_hash"] == hash_of(COMPARABLE_WITH_ERRORS)].iloc[0]
    assert "| " + " | ".join(md_cell(mixed[c]) if c != "cause" else "None" for c in COVERAGE_COLUMNS) + " |" in block
    assert "no_outcome_both |" in block


def test_e27_a_only_and_wholly_errored_is_only_a(syn: Built) -> None:
    row = coverage_row(syn, ("err-a-only", 2.0, P))
    assert (row["rows_a"], row["no_outcome_a"], row["rows_b"]) == (N, N, 0)
    assert row["cause"] == "only_a"


def test_e27_b_only_and_wholly_errored_is_only_b(syn: Built) -> None:
    row = coverage_row(syn, ("err-b-only", 2.0, P))
    assert (row["rows_a"], row["rows_b"], row["no_outcome_b"]) == (0, N, N)
    assert row["cause"] == "only_b"


def test_e27_both_arms_none_with_outcome_is_no_outcome_both(syn: Built) -> None:
    row = coverage_row(syn, ("err-both", 2.0, P))
    assert (row["rows_a"], row["no_outcome_a"], row["rows_b"], row["no_outcome_b"]) == (N, N, N, N)
    assert row["cause"] == "no_outcome_both"


# ---------- E13-E14: M7 attaches the cause and changes no byte ----------


def test_e13_grid_holes_carry_the_cause_and_the_hash_of_their_one_row(syn: Built) -> None:
    holes = {c.coords: c for c in grid_holes(syn)}
    assert set(holes) == set(EXPECTED_GRID_HOLES)
    for coords, (key, cause) in EXPECTED_GRID_HOLES.items():
        cell = holes[coords]
        assert cell.hole_cause == cause, coords
        assert cell.config_hash == (None if key is None else hash_of(key)), coords
        assert not cell.present


def test_e13_present_cells_have_no_hole_cause_and_every_panel_shares_the_grid(syn: Built, go1: Built) -> None:
    for b in (syn, go1):
        first = {c.coords: (c.config_hash, c.hole_cause) for c in grid_holes(b)}
        for event, panel in b.report.panels.items():
            assert all(c.hole_cause is None for c in panel.cells if c.present), event
            assert {c.coords: (c.config_hash, c.hole_cause) for c in panel.cells if not c.present} == first, event


def test_e13_a_result_without_coverage_and_a_single_event_report_leave_hole_cause_none(syn: Built) -> None:
    ma, mb = syn.store.manifest(SYN_A), syn.store.manifest(SYN_B)
    bare = build_multi_report(replace(syn.multi, coverage=None), syn.spec, manifests=(ma, mb))
    for panel in bare.panels.values():
        assert panel.n_absent == len(EXPECTED_GRID_HOLES)
        assert all(c.hole_cause is None and c.config_hash is None for c in panel.cells if not c.present)
    single = build_report(hand_built_diff(syn.multi, SYN_EVENTS[0]), syn.spec, manifests=(ma, mb))
    assert single.n_absent == len(EXPECTED_GRID_HOLES)
    assert all(c.hole_cause is None and c.config_hash is None for c in single.cells if not c.present)


def as_0_0_1_wrote_it(text: str) -> str:
    """PF0 (Q4, section 2.3): the one field the rename changes in a rendered report, receipt or page
    is the version in its provenance list. First assert it is there as the rename writes it -- one
    ``Prove version:`` entry and no ``proofload version:`` -- then put it back as 0.0.1 wrote it and
    drop any separate ``written by proofload`` entry, so the frozen digest still guards every other
    byte."""
    found = re.findall(r"(?m)^- Prove version: [^\n]*$", text) + re.findall(r"<li>Prove version: [^<]*</li>", text)
    assert len(found) == 1 and "proofload version:" not in text, found
    text = re.sub(r"(?m)^- Prove version: [^\n]*$", "- proofload version: 0.0.1", text)
    text = re.sub(r"<li>Prove version: [^<]*</li>", "<li>proofload version: 0.0.1</li>", text)
    text = re.sub(r"(?m)^- [^\n]*written by proofload[^\n]*\n", "", text)
    return re.sub(r"<li>[^<]*written by proofload[^<]*</li>", "", text)


def e14_multi() -> MultiDiffResult:
    """The E14 argv's ``multi``."""
    store = Store(GO1_ROOT)
    return multi_diff(
        store.read(GO1_A, meta=False), store.read(GO1_B, meta=False), events=["fell"],
        manifest_a=store.manifest(GO1_A), manifest_b=store.manifest(GO1_B),
    )


def e14_builder_texts(multi: MultiDiffResult) -> dict[str, str]:
    """The E14 argv's ``multi`` and spec, rendered by the M7 builder with no tree, the way
    ``_report_pair`` builds them: the dark-theme report's markdown and the light-theme receipt."""
    store = Store(GO1_ROOT)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    spec = ReportSpec(title=f"{GO1_A} vs {GO1_B}: fell", x_axis="mu", y_axis="push_pct_bw")
    report = build_multi_report(multi, spec, manifests=(ma, mb))
    receipt = build_multi_report(multi, replace(spec, theme="light"), manifests=(ma, mb))
    return {"report.md": report.to_markdown(), "receipt.html": receipt.to_html(), "heatmap.svg": report.to_svg()}


def test_e14_the_go1_report_reproduces_the_three_digests_minted_on_the_bare_tree(tmp_path: Path) -> None:
    """Narrowed for S28 (draft ADR-074, spec S28 section 3.8): ``report`` on a pair now renders the
    layered report into ``report.md`` and ``receipt.html``, so those two files through the CLI
    are S28's to pin. The surface S21 owned is the tree-less M7 builder, which reproduces both
    digests bit for bit (S28 section 0.2), so the two markdown and HTML pins move to
    ``build_multi_report(multi, spec, manifests=...)`` with no tree; ``heatmap.svg`` never
    changes (S28 section 3.3) and stays pinned through the CLI. Narrowed, not deleted."""
    out = tmp_path / "report"
    r = run_cli(["--store", str(GO1_ROOT), *E14_ARGV, "--out", str(out)])
    assert r.code == 0, r.text
    multi = e14_multi()
    texts = e14_builder_texts(multi)
    # The heatmap's labels are printed under rule 10 by the command line (spec section 5.4): the
    # frozen digest now holds over the builder's own SVG, and the written file carries its cells,
    # geometry and numbers.
    # PF2 (spec section 4.3/5.3): the default title names the two runs by name instead of by id;
    # the builder's SVG with only its title moved to the names is what the command writes.
    names = run_names(GO1_ROOT)
    old_title, new_title = f"{GO1_A} vs {GO1_B}: fell", f"{names[GO1_A]} vs {names[GO1_B]}: fell"
    written = (out / "heatmap.svg").read_text(encoding="utf-8")
    assert new_title in written and old_title not in written
    assert texts["heatmap.svg"].count(old_title) >= 1
    assert rendered_problems(texts["heatmap.svg"].replace(old_title, new_title), written, "heatmap.svg") == []
    for name in ("report.md", "receipt.html"):
        as_0_0_1_wrote_it(texts[name])
    # PF4 (PF4.3, PF4.15, PF4.20): the three digests are replaced by the facts they guarded. First
    # S21's own: attaching the coverage moves no byte of any of the three files.
    assert e14_builder_texts(replace(multi, coverage=None)) == texts
    # The headline counts, from the library's cells (the bare tree's report printed 60 safer and
    # 0 worse on this pair), in the report, the receipt and the heatmap.
    fell = multi.by_event["fell"]
    cells = fell.cells
    n_lower, n_higher = int((cells["verdict"] == "safer").sum()), int((cells["verdict"] == "worse").sum())
    assert (n_lower, n_higher) == (60, 0)
    headline = f"fell: {n_lower} lower, {n_higher} higher"
    assert headline in texts["report.md"].splitlines() and f"## {headline}" in texts["report.md"].splitlines()
    assert f"<h2>{headline}</h2>" in texts["receipt.html"]
    assert f">{headline}</text>" in texts["heatmap.svg"]
    # The worst-powered unchanged condition and its limit (34pp on Go1, the figure the bare tree's
    # report printed), on its line in all three files.
    worst = cells.set_index("config_hash").loc[fell.max_mde_unchanged_cell]
    assert round(100 * fell.max_mde_unchanged) == 34
    config = ", ".join(f"{k}={v:g}" for k, v in sorted(worst["config"].items()))
    worst_line = f"Worst-powered unchanged cell ({config}, n={worst['n_a']}/{worst['n_b']}) can only detect a 34pp rise."
    for name, text in texts.items():
        assert worst_line in text, name
    # Every row of the report's cell table is a cell of the diff, with its counts, rates in points,
    # p, q and verdict.
    md_lines = texts["report.md"].splitlines()
    first = next(i for i, line in enumerate(md_lines) if line.startswith("| "))
    rows = list(itertools.takewhile(lambda line: line.startswith("|"), md_lines[first:]))
    header = [c.strip() for c in rows[0].strip("|").split("|")]
    assert header[:9] == ["mu", "push_pct_bw", "n (a/b)", "rate_a (pp)", "rate_b (pp)", "delta (pp)", "p", "q", "verdict"], header
    table = [dict(zip(header, (c.strip() for c in row.strip("|").split("|")), strict=True)) for row in rows[1:]]
    table = [row for row in table if set(row["mu"]) - set("-:")]
    assert table
    for row in table:
        (cell,) = [c for c in cells.to_dict(orient="records") if c["config"] == {"mu": float(row["mu"]), "push_pct_bw": float(row["push_pct_bw"])}]
        assert row["n (a/b)"] == f"{cell['n_a']}/{cell['n_b']}", row
        for column, key in (("rate_a (pp)", "rate_a"), ("rate_b (pp)", "rate_b"), ("delta (pp)", "delta")):
            assert abs(float(row[column]) - 100 * cell[key]) <= 0.05 + 1e-9, (row, column, cell[key])
        for column in ("p", "q"):
            decimals = len(row[column].partition(".")[2])
            assert abs(float(row[column]) - cell[column]) <= 0.5 * 10.0**-decimals + 1e-12, (row, column, cell[column])
        assert row["verdict"] == E14_DIRECTION[cell["verdict"]], (row, cell["verdict"])


def test_e14_the_synthetic_report_is_byte_identical_with_coverage_replaced_by_none(syn: Built) -> None:
    ma, mb = syn.store.manifest(SYN_A), syn.store.manifest(SYN_B)
    counts = (counts_of(syn.store, SYN_A), counts_of(syn.store, SYN_B))  # the fixture's own build is handed them
    bare = build_multi_report(replace(syn.multi, coverage=None), syn.spec, manifests=(ma, mb), observations=counts)
    assert syn.report.to_svg() == bare.to_svg()
    assert syn.report.to_markdown() == bare.to_markdown()
    assert syn.report.to_html() == bare.to_html()


def test_e14_every_absent_rect_still_says_absent_and_provenance_gains_no_key(syn: Built) -> None:
    svg = syn.report.to_svg()
    absent = sum(panel.n_absent for panel in syn.report.panels.values())
    assert absent == len(EXPECTED_GRID_HOLES) * len(syn.report.events)
    assert svg.count('data-cell="absent"') == absent
    frame = coverage_of(syn)
    for h in frame.loc[~frame["comparable"], "config_hash"]:
        assert f'data-cell="{h}"' not in svg, h
    assert tuple(syn.report.provenance) == PROVENANCE_KEYS


# ---------- E15-E18: the structure ----------


def test_e15_schema_is_viewpair_4_and_the_top_level_keys_are_the_thirteen(builts: tuple[Built, Built]) -> None:
    for b in builts:
        assert b.structure["schema"] == SCHEMA == viewer().SCHEMA
        assert tuple(b.structure) == TOP_LEVEL_KEYS


def test_e15_each_arm_has_fifteen_keys_and_its_tally_from_the_store(builts: tuple[Built, Built]) -> None:
    for b in builts:
        for key, run_id in (("a", b.a), ("b", b.b)):
            arm = b.structure["pair"][key]
            assert tuple(arm) == ARM_KEYS, (run_id, tuple(arm))
            assert arm["tally"] == b.store.tally(run_id).to_dict()
            assert arm["tally"]["rows"] == arm["rows_stored"] == b.store.count(run_id)


def test_e15_render_html_refuses_the_retired_schema_naming_both_values(go1: Built) -> None:
    structure = json.loads(json.dumps(go1.structure, allow_nan=False))
    structure["schema"] = RETIRED_SCHEMA
    with pytest.raises(viewer().ViewerError) as info:
        viewer().render_html(structure)
    assert RETIRED_SCHEMA in str(info.value) and SCHEMA in str(info.value)


def test_e16_cell_keys_are_the_twenty_one_in_order(builts: tuple[Built, Built]) -> None:
    for b in builts:
        for panel in b.structure["panels"]:
            assert panel["cells"]
            for cell in panel["cells"]:
                # PF4 (PF4.3, PF4.13 to PF4.15): the twenty-one keep their order, and the cell gains
                # the PF4 keys; where the new keys sit among them is not pinned.
                assert tuple(k for k in cell if k in CELL_KEYS) == CELL_KEYS, tuple(cell)
                assert set(cell) == set(CELL_KEYS) | set(PF4_CELL_KEYS), set(cell) ^ (set(CELL_KEYS) | set(PF4_CELL_KEYS))


def test_e16_rows_and_no_outcome_are_ints_equal_to_the_coverage_row(builts: tuple[Built, Built]) -> None:
    for b in builts:
        frame = coverage_of(b).set_index("config_hash")
        for panel in b.structure["panels"]:
            for cell in panel["cells"]:
                cov = frame.loc[cell["config_hash"]]
                for name in COVERAGE_CELL_KEYS:
                    assert type(cell[name]) is int and cell[name] == int(cov[name]), (cell["config_hash"], name)
                assert not set(COVERAGE_CELL_KEYS) & set(cell["text"])


def test_e16_config_text_is_fmt_coord_of_each_scalar_and_null_for_the_rest(syn: Built) -> None:
    from poisson_prove.report import _fmt

    seen_non_scalar = seen_bool = False
    for panel in syn.structure["panels"]:
        for cell in panel["cells"]:
            config, text = cell["config"], cell["config_text"]
            assert list(text) == list(config)
            for k, v in config.items():
                if is_scalar(v):
                    assert text[k] == _fmt(v, "coord"), (k, v)
                    seen_bool = seen_bool or isinstance(v, bool)
                else:
                    assert text[k] is None, (k, v)
                    seen_non_scalar = True
    assert seen_non_scalar and seen_bool


def test_e16_text_keys_are_still_the_seven_floats_and_forbidden_keys_appear_nowhere(builts: tuple[Built, Built]) -> None:
    for b in builts:
        for panel in b.structure["panels"]:
            for cell in panel["cells"]:
                assert set(cell["text"]) == set(FLOAT_KINDS)
        # Narrowed for S29 (spec S29 section 0.3, draft ADR-074), exactly as M13's V24: the structure
        # walk carves out the one path ``tree.root.seed``, M14's name for the permutation seed; the
        # page-index walk is not narrowed, because the tree's regions add nothing to the index.
        hits = {path for path, key in walk_key_paths(b.structure) if key in FORBIDDEN_KEYS}
        assert hits <= {SEED_CARVE_OUT}, hits
        assert not FORBIDDEN_KEYS & set(walk_keys(strict_loads(parse_html(b.page).script_json(INDEX_ID))))


def test_e17_holes_are_the_grid_holes_in_grid_order_then_off_grid_rows_by_hash(syn: Built) -> None:
    from poisson_prove.report import _coord_text

    holes = syn.structure["holes"]
    grid = grid_holes(syn)
    n_absent = syn.structure["panels"][0]["n_absent"]
    assert len(grid) == n_absent == len(EXPECTED_GRID_HOLES)
    assert [h["coords"] for h in holes[:n_absent]] == [_coord_text(syn.spec, c) for c in grid]
    assert [h["config_hash"] for h in holes[:n_absent]] == [c.config_hash for c in grid]
    off_grid = off_grid_hashes(syn)
    assert off_grid == sorted(hash_of(k) for k in OFF_GRID)
    assert [h["config_hash"] for h in holes[n_absent:]] == off_grid
    assert all(h["coords"] is None for h in holes[n_absent:])
    assert len(holes) == n_absent + len(off_grid)


def test_e17_each_hole_has_the_nine_keys_in_order_and_no_text(syn: Built) -> None:
    for hole in syn.structure["holes"]:
        assert tuple(hole) == HOLE_KEYS, tuple(hole)


def test_e17_unsampled_and_multiple_holes_are_blank_with_four_zero_counts(syn: Built) -> None:
    blank = [h for h in syn.structure["holes"] if h["cause"] in GRID_CAUSES]
    assert sorted(h["cause"] for h in blank) == sorted(GRID_CAUSES)
    for hole in blank:
        assert hole["config_hash"] is None and hole["config"] is None and hole["config_text"] is None
        assert [hole[k] for k in COVERAGE_CELL_KEYS] == [0, 0, 0, 0]
        assert hole["coords"] is not None


def test_e17_every_other_hole_carries_its_coverage_row(syn: Built) -> None:
    from poisson_prove.report import _fmt

    frame = coverage_of(syn).set_index("config_hash")
    others = [h for h in syn.structure["holes"] if h["cause"] not in GRID_CAUSES]
    assert len(others) == len(EXPECTED_CAUSES)
    for hole in others:
        cov = frame.loc[hole["config_hash"]]
        assert hole["cause"] == cov["cause"]
        assert [hole[k] for k in COVERAGE_CELL_KEYS] == [int(cov[k]) for k in COVERAGE_CELL_KEYS]
        assert hole["config"] == cov["config"]
        assert hole["config_text"] == {k: _fmt(v, "coord") if is_scalar(v) else None for k, v in cov["config"].items()}


def test_e17_a_fix_that_excludes_a_row_puts_it_off_grid_with_null_coords(syn_fixed: Built) -> None:
    holes = syn_fixed.structure["holes"]
    excluded = hash_of(("multi", 2.0, Q))
    off = [h for h in holes if h["config_hash"] == excluded]
    assert len(off) == 1 and off[0]["coords"] is None and off[0]["cause"] == "only_b"
    multi = [h for h in holes if h["coords"] is not None and h["coords"].startswith("task=multi,")]
    assert len(multi) == 1
    assert (multi[0]["cause"], multi[0]["config_hash"]) == ("only_a", hash_of(("multi", 2.0, P)))
    assert len(holes) == syn_fixed.structure["panels"][0]["n_absent"] + len(off_grid_hashes(syn_fixed))


def test_e17_holes_is_carried_once_and_go1_has_none(go1: Built) -> None:
    assert go1.structure["holes"] == []
    assert all(panel["n_absent"] == 0 for panel in go1.structure["panels"])
    assert "holes" not in set(walk_keys(go1.structure["panels"]))


def test_e18_unverified_is_exactly_the_four_entries_in_order(builts: tuple[Built, Built]) -> None:
    for b in builts:
        entries = b.structure["unverified"]
        assert [(e["id"], e["statement"], e["blocked_by"]) for e in entries] == list(UNVERIFIED)
        assert all(tuple(e) == ("id", "statement", "blocked_by") for e in entries)


def test_e18_the_three_deleted_entries_appear_nowhere(builts: tuple[Built, Built]) -> None:
    for b in builts:
        ids = {e["id"] for e in b.structure["unverified"]}
        strings = list(walk_strings(b.structure))
        page = html_unescape(b.page)
        for name, statement in DELETED_UNVERIFIED:
            assert name not in ids, name
            assert not any(statement in s for s in strings), name
            assert statement not in page, name


# ---------- E19-E21: the page ----------


def test_e19_the_identity_table_carries_the_five_tally_rows_after_rows_stored_outside_details(builts: tuple[Built, Built]) -> None:
    for b in builts:
        dom = parse_html(b.page)
        table = table_with_header(dom, IDENTITY_HEADER)
        assert not table.inside("details")
        rows = table_rows(table)
        labels = [r[0] for r in rows]
        at = labels.index("rows_stored")
        assert tuple(labels[at + 1 : at + 6]) == IDENTITY_ROWS
        pair = b.structure["pair"]
        for name in IDENTITY_ROWS:
            row = rows[labels.index(name)]
            assert row == [name, str(pair["a"]["tally"][name]), str(pair["b"]["tally"][name])], name


def test_e19_the_drill_down_and_the_script_order_carry_rows_and_no_outcome_after_n(syn: Built) -> None:
    dom = parse_html(syn.page)
    drill = dom.find("div", id="pl-cell")
    assert len(drill) == 1
    rows = table_rows(descendants(drill[0], "table")[0])
    labels = [r[0] for r in rows]
    at = labels.index(DRILL_LABELS[0])
    assert tuple(labels[at : at + 3]) == DRILL_LABELS
    cell = selected_cell(syn)
    assert rows[at + 1][1] == f"{cell['rows_a']}/{cell['rows_b']}"
    assert rows[at + 2][1] == f"{cell['no_outcome_a']}/{cell['no_outcome_b']}"
    m = ORDER_RE.search(syn.page)
    assert m, "no order list in the script"
    order = json.loads("[" + m.group(1) + "]")
    n_at = order.index("n_b")
    assert order[n_at - 1] == "n_a"
    assert tuple(order[n_at + 1 : n_at + 5]) == ORDER_KEYS_AFTER_N


def test_e19_the_initial_drill_down_prints_every_config_text_string_of_the_selected_cell(builts: tuple[Built, Built]) -> None:
    for b in builts:
        dom = parse_html(b.page)
        drill = dom.find("div", id="pl-cell")[0]
        values = [r[1] for r in table_rows(descendants(drill, "table")[0])]
        cell = selected_cell(b)
        printed = [v for v in cell["config_text"].values() if isinstance(v, str)]
        assert printed
        for text in printed:
            assert text in values, text


def test_e20_the_picker_ends_with_a_holes_optgroup_of_one_option_per_hole(builts: tuple[Built, Built]) -> None:
    for b in builts:
        dom = parse_html(b.page)
        selects = dom.find("select")
        assert len(selects) == 1
        groups = [g for g in selects[0].children if g.tag == "optgroup"]
        assert [g.attrs.get("label") for g in groups[:-1]] == [p["event"] for p in b.structure["panels"]]
        assert groups[-1].attrs.get("label") == HOLES_OPTGROUP
        options = [o for o in groups[-1].children if o.tag == "option"]
        holes = b.structure["holes"]
        assert [o.attrs.get("value") for o in options] == [f"hole:{i}" for i in range(len(holes))]
        assert [o.deep_text() for o in options] == [
            h["coords"] if h["coords"] is not None else h["config_hash"] for h in holes
        ]


def test_e20_the_holes_block_parses_strictly_and_equals_the_structure(builts: tuple[Built, Built]) -> None:
    for b in builts:
        block = parse_html(b.page).script_json(HOLES_ID)
        for ch in "<>&":
            assert ch not in block, ch
        assert strict_loads(block) == b.structure["holes"]
        assert b.page.count(f'id="{HOLES_ID}"') == 1


def test_e20_the_cell_index_has_no_hole_entry_and_the_hole_message_appears_once(syn: Built) -> None:
    index = strict_loads(parse_html(syn.page).script_json(INDEX_ID))
    present = {key_of(p["event"], c["config_hash"]) for p in syn.structure["panels"] for c in p["cells"]}
    assert set(index) == present
    assert not any(k.endswith("absent") or k.startswith("hole:") for k in index)
    assert syn.structure["holes"]
    assert 'data-cell="absent"' in syn.page
    assert html_unescape(syn.page).count(HOLE_MESSAGE) == 1


def test_e21_the_holes_section_sits_between_the_drill_down_and_the_worst_tables(builts: tuple[Built, Built]) -> None:
    for b in builts:
        dom = parse_html(b.page)
        heading = h2_named(dom, HOLES_HEADING)
        drill = dom.find("div", id="pl-cell")[0]
        header = b.structure["panels"][0]["worst_header"]
        worst = min(t.index for t in dom.find("table") if table_header(t) == header)
        assert drill.index < heading.index < worst


def test_e21_with_holes_the_section_is_a_table_of_the_five_headers_and_one_row_per_hole(syn: Built) -> None:
    dom = parse_html(syn.page)
    heading = h2_named(dom, HOLES_HEADING)
    following = [n for n in dom.nodes if n.index > heading.index and n.tag in ("table", "h2")]
    assert following[0].tag == "table"
    assert table_header(following[0]) == HOLES_HEADER
    expected = [
        [
            h["where"],
            h["cause"],
            h["config_hash"] if h["config_hash"] is not None else NONE_TEXT,
            f"{h['rows_a']}/{h['rows_b']}",
            f"{h['no_outcome_a']}/{h['no_outcome_b']}",
        ]
        for h in syn.structure["holes"]
    ]
    assert table_rows(following[0]) == expected
    # LS retrofit, 2026-09-22: an off-grid hole is in the fixture (``coords`` None) and its row no
    # longer prints ``none`` -- ``where`` names its config on the report's axes (spec LS D12).
    assert any(h["coords"] is None for h in syn.structure["holes"]) and any(r[2] == NONE_TEXT for r in expected)
    assert not any(r[0] == NONE_TEXT for r in expected)
    assert HOLE_MESSAGE not in following[0].deep_text()


def test_e21_with_no_holes_the_section_is_a_paragraph_saying_zero_and_no_table(go1: Built) -> None:
    dom = parse_html(go1.page)
    heading = h2_named(dom, HOLES_HEADING)
    next_h2 = min(n.index for n in dom.find("h2") if n.index > heading.index)
    between = nodes_between(dom, heading.index, next_h2)
    assert [n.tag for n in between if n.tag in ("table", "p")] == ["p"]
    paragraph = next(n for n in between if n.tag == "p")
    assert paragraph.deep_text() == ZERO_HOLES_TEXT


# ---------- E22-E23: it renders, it does not compute ----------


def test_e22_build_structure_still_applies_exactly_the_created_at_subtraction() -> None:
    tree = ast.parse(viewer_source())
    nodes = closure(tree, "build_structure")
    assert nodes
    arithmetic = arithmetic_nodes(nodes)
    assert len(arithmetic) == 1, [ast.dump(n) for n in arithmetic]
    only = arithmetic[0]
    assert isinstance(only, ast.BinOp) and isinstance(only.op, ast.Sub), ast.dump(only)
    assert only in total_seconds_operands(nodes), ast.dump(only)


def test_e22_render_html_applies_no_arithmetic() -> None:
    tree = ast.parse(viewer_source())
    nodes = closure(tree, "render_html")
    assert nodes
    assert arithmetic_nodes(nodes) == [], [ast.dump(n) for n in arithmetic_nodes(nodes)]


def test_e22_viewer_has_no_format_no_float_spec_no_times_100_and_no_hex_colour() -> None:
    src = viewer_source()
    assert not HEX_RE.search(src), HEX_RE.search(src)
    assert not TIMES_100_RE.search(src)
    assert not FLOAT_SPEC_RE.search(src)
    assert format_calls(ast.parse(src)) == [], format_calls(ast.parse(src))
    assert "toFixed(" not in src and "toPrecision(" not in src
    assert src.count(HOST) == 1


def test_e22_the_import_partition_is_unchanged_and_run_tally_is_under_type_checking() -> None:
    tree = ast.parse(viewer_source())
    assert report_import_names(tree) == ASSEMBLY_HELPERS | RENDER_HELPERS
    build = referenced_names(closure(tree, "build_structure"))
    render = referenced_names(closure(tree, "render_html"))
    assert build & (ASSEMBLY_HELPERS | RENDER_HELPERS) == ASSEMBLY_HELPERS, build
    assert render & (ASSEMBLY_HELPERS | RENDER_HELPERS) == RENDER_HELPERS, render
    assert "RunTally" in store_imports(type_checking_body(tree))
    assert "RunTally" not in store_imports(tree.body)


def test_e23_the_page_prints_no_float_except_through_the_structures_strings(builts: tuple[Built, Built]) -> None:
    from poisson_prove.report import _provenance_lines

    for b in builts:
        allowed = list(walk_strings(b.structure)) + _provenance_lines(b.structure["diff"])
        allowed.append(str(b.structure["pair"]["created_at_gap_s"]))
        stray = [
            tok for tok in FLOAT_TOKEN_RE.findall(visible_text(b.page))
            if not any(tok in s for s in allowed)
        ]
        assert stray == [], stray


def test_e23_two_builds_are_equal_and_the_structure_and_holes_are_json_strict(builts: tuple[Built, Built]) -> None:
    for b in builts:
        again = built(b.root, b.a, b.b, b.spec, b.events)
        assert again.structure == b.structure
        assert again.page == b.page
        json.dumps(b.structure["holes"], allow_nan=False)
        json.dumps(b.structure, allow_nan=False)


# ---------- E24-E26: the CLI ----------


def test_e24_serve_json_on_go1_prints_the_thirteen_keys_both_tallies_and_no_holes_binding_nothing(go1_serve_json: Served, go1_store: Store) -> None:
    r = go1_serve_json.result
    assert r.code == 0, r.err
    assert go1_serve_json.calls == []
    parsed = strict_loads(r.out)
    # serve --json adds verdict and sentence after schema (spec section 5.6).
    assert tuple(parsed)[:3] == ("schema", "verdict", "sentence"), tuple(parsed)
    # PF3 (spec section 4.4, R3): serve --json also adds method and method_chosen right after sentence.
    assert tuple(k for k in parsed if k not in ("verdict", "sentence")) == ("schema", "method", "method_chosen") + TOP_LEVEL_KEYS[1:]
    assert parsed["schema"] == SCHEMA
    assert parsed["pair"]["a"]["tally"] == go1_store.tally(GO1_A).to_dict() == dict(zip(TALLY_FIELDS, GO1_TALLY))
    assert parsed["pair"]["b"]["tally"] == go1_store.tally(GO1_B).to_dict() == dict(zip(TALLY_FIELDS, GO1_TALLY))
    assert parsed["holes"] == []


def test_e24_serve_json_on_the_synthetic_pair_has_holes_with_the_seven_causes(syn_serve_json: Served, syn: Built) -> None:
    r = syn_serve_json.result
    assert r.code == 0, r.err
    assert syn_serve_json.calls == []
    parsed = strict_loads(r.out)
    assert parsed["holes"]
    assert all(h["cause"] in ALL_CAUSES for h in parsed["holes"])
    assert {h["cause"] for h in parsed["holes"]} == set(ALL_CAUSES)
    # serve --json adds verdict and sentence after schema (spec section 5.6).
    assert tuple(parsed)[:3] == ("schema", "verdict", "sentence"), tuple(parsed)
    # PF3 (spec section 4.4, R3): serve --json also adds method and method_chosen right after sentence;
    # the library's structure has neither, so they are dropped here as verdict and sentence are.
    assert tuple(parsed)[3:5] == ("method", "method_chosen"), tuple(parsed)
    parsed = {k: v for k, v in parsed.items() if k not in ("verdict", "sentence", "method", "method_chosen")}
    # PF2 (spec section 4.3/5.3): serve --json carries run_name beside every run_id; each is the
    # run's name, and with them taken out the structure is the library's as before.
    seen: list[tuple[str, str]] = []
    parsed = without_run_names(parsed, seen)
    names = run_names(syn.root)
    assert sorted(seen) == sorted((rid, names[rid]) for rid in (SYN_A, SYN_B)), seen
    assert parsed == json.loads(json.dumps(syn.structure, allow_nan=False))


def without_run_names(node: Any, seen: list[tuple[str, str]]) -> Any:
    """Drop every ``run_name`` that sits beside a ``run_id``, recording the (id, name) pairs; a
    ``run_name`` without a ``run_id`` beside it is left in place, so the comparison still sees it."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "run_name" and "run_id" in node:
                seen.append((node["run_id"], v))
                continue
            out[k] = without_run_names(v, seen)
        return out
    if isinstance(node, list):
        return [without_run_names(v, seen) for v in node]
    return node


def runs_table(r: Result) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    """PF2 (spec section 4.3/5.3): ``runs`` prints ``ok  N runs in <store>``, a blank line, then a
    table whose cells are padded to their column and joined by two spaces; names and the header
    ``rows without an outcome`` hold single spaces, so a row is cut at the header's column starts."""
    assert r.lines[0].startswith("ok  "), r.out
    header_line = r.lines[1]
    starts = [m.start() for m in re.finditer(r"\S+(?: \S+)*", header_line)]
    header = tuple(header_line[a:b].strip() for a, b in zip(starts, [*starts[1:], None], strict=True))
    rows = [
        dict(zip(header, (line[a:b].strip() for a, b in zip(starts, [*starts[1:], None], strict=True)), strict=True))
        for line in r.lines[2:]
    ]
    return header, rows


def test_e25_runs_prints_seven_columns_and_the_seventh_is_the_stores_no_outcome(syn_root: Path, three_root: Path) -> None:
    for root in (syn_root, three_root, GO1_ROOT):
        store = Store(root)
        r = run_cli(["--store", str(root), "runs"])
        assert r.code == 0, r.text
        # PF2 (spec section 4.3/5.3): the table's columns are now #, name, id, status, backend,
        # target, rows, rows without an outcome, created, newest first; the store's no_outcome
        # count is the "rows without an outcome" column and the row count the "rows" column.
        header, rows = runs_table(r)
        assert header == RUNS_HEADER
        assert header[7] == "rows without an outcome"
        names = run_names(root)
        assert sorted(row["id"] for row in rows) == sorted(store.runs())
        newest_first = sorted(store.runs(), key=lambda rid: store.manifest(rid).created_at, reverse=True)
        assert [row["id"] for row in rows] == newest_first
        for row in rows:
            assert row["name"] == names[row["id"]], row
            assert row["status"] == store.manifest(row["id"]).status, row
            # Counts carry thousands separators in text (spec section 5.4, rule 10).
            assert row["rows without an outcome"] == f"{store.tally(row['id']).no_outcome:,}", row
            assert row["rows"] == f"{store.count(row['id']):,}", row


def test_e25_a_run_of_three_errored_rows_prints_three(three_root: Path) -> None:
    r = run_cli(["--store", str(three_root), "runs"])
    assert r.code == 0, r.text
    # PF2 (spec section 4.3/5.3): the run is found by its id column in the new table.
    _, rows = runs_table(r)
    assert len(rows) == 1
    fields = rows[0]
    assert fields["id"] == "three"
    assert fields["rows without an outcome"] == "3"
    assert fields["rows"] == "5"


def test_e26_every_errored_row_is_on_the_page_exactly_once(syn_serve_json: Served, syn_root: Path) -> None:
    parsed = strict_loads(syn_serve_json.result.out)
    store = Store(syn_root)
    cells = parsed["panels"][0]["cells"]
    holes = parsed["holes"]
    for arm, run_id in (("a", SYN_A), ("b", SYN_B)):
        in_cells = sum(c[f"no_outcome_{arm}"] for c in cells)
        in_holes = sum(h[f"no_outcome_{arm}"] for h in holes)
        assert in_cells > 0 and in_holes > 0, arm
        assert store.tally(run_id).no_outcome == in_cells + in_holes, arm
