"""M10 multi-event CLI frozen tests: the CLI reporting more than one event.

Every test drives ``poisson_prove.cli.main(argv, stdout=, stderr=, stdin=)`` in-process with
``StringIO`` streams, as the S10 frozen tests do. Stores live under ``tmp_path``; the generated
lattice pair (``tests/lattice.py``) is read in place and only ``--out`` directories are written.

One plain assertion per invariant. The two mock-agent runs are swept once per module under
the S12 salt, so the pair infers ``violated, timeout`` with ``completed`` as the non-event,
has worse cells in ``timeout`` only, and carries a trade line; that is the pair C2, C4, C5,
C7 and C9-C13 read. C6 does not rely on it: its pair is synthetic, with the worse cell
found by searching counts.

Reading notes:

- C11 asserts the flag reaches ``ReportSpec.forest`` by wrapping ``cli.build_multi_report``
  (the name must be bound in ``cli``, as ``run_modal`` is for I7) and reading the spec it is
  handed; the wrapper calls the real function, so the files are still written.
- C12 attributes stylesheet rules to elements with a small selector matcher (tag, ``.class``,
  ``#id``, descendant combinators); inline ``style=`` attributes count too; ``@media`` blocks
  are ignored, so the assertions are about the screen stylesheet.
- C14's monkeypatched ``run_modal`` drives ``executor_modal.run_with_mapper`` with an
  in-process mapper carrying ``import_path``, which is how the Modal backend records the
  field on a real run; the manifest is therefore the modal backend's own, not one the test
  writes.

Deliberately not tested:

- The fixture's count as ``n_safer`` at the top level of ``diff``'s JSON. ``MultiDiffResult.to_json()``
  carries per-event counts under ``by_event`` and the CLI prints ``to_json()``; a top-level
  ``n_safer`` would need a one-event branch the multi-event output does not have. I9 asserts the count
  where ``to_json()`` puts it.
- Inference failing on too many outcomes (C3). Seven distinct outcomes infer six events, which
  ``infer_events`` allows (S11 A13 pins the six-event ceiling as inclusive), so a seven-outcome
  frame does not fail inference.
- ``report RUN`` with ``--event`` omitted. Nothing fixes where a single run's event
  set comes from, so every single-run test passes ``--event`` explicitly.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.stats import fisher_exact

import poisson_prove.cli as cli
import poisson_prove.report as report_module
from poisson_prove.diff import bh
from poisson_prove.episode import Episode
from poisson_prove.executor_modal import Job, ModalOptions, ModalTarget, run_with_mapper, worker_batch
from poisson_prove.store import EpisodeRecord, RunManifest, Store
import lattice
from conftest import quickstart_design

LATTICE_ROOT = lattice.root()
# PF3: the one copy is the packaged spec; this is its design at
# 100 replicates.
QUICKSTART = quickstart_design()
# PF4.30, PF4.48a: the quickstart design at 100 replicates with nothing
# declared has a detection limit (0.262 at base rate 0.400) above the default accepted change of 0.20,
# so its sweep is refused; every sweep of it in this file accepts 0.3, the smallest round value
# above the limit.
QUICKSTART_MAX_MDE = ("--max-mde", "0.3")

MOCK_MODULE = "poisson_prove.examples.mock_agent"
ROLLOUT = f"{MOCK_MODULE}:rollout"
PATCHED = f"{MOCK_MODULE}:rollout_patched"
QUICKSTART_SALT = "0000000000000015"

REPORT_FILES = {"report.md", "heatmap.svg", "receipt.html"}
MOCK_EVENTS = {"violated", "timeout"}
NON_EVENT = "completed"
#: The inference line's marker, a line prefix and never a substring: report.md's Provenance prints ``- inferred: false``, which a bare ``inferred: `` would match.
INFERENCE_MARKER = "inferred: no event was given, so "
# PF4 (PF4.20): the lattice's runs declare no kind for tripped, so its counts read in direction
# words: 22 conditions fell and none rose, as scipy's Fisher with one BH family gives
# (``lattice.fisher``; C1 checks the reference against the literal).
LATTICE_HEADLINE = "tripped: 22 lower, 0 higher"
FALLBACK_IMPORT = "from your_module import rollout"
REAL_IMPORT = f"from {MOCK_MODULE} import rollout"
SNIPPET_MARKER = "# reproduce one episode"

Q = 0.05
N = 32
HORIZON = 10.0
N_FILLERS = 6

HONESTY_FIRST_RE = re.compile(
    r'^Worst-powered unchanged cell \((.*), n=(\d+)/(\d+)\) can only detect a (\d\.\d{3}) (?:rise|fall)\. '
    r'"(\d+) higher" is an honest claim only above that\.$'
)  # PF4 (PF4.20): the claim names the rise in direction words for an event of unknown kind.
# PF4.27, PF4.32: the limit named is the condition's own, a rise or a fall.
HONESTY_NONE = "No unchanged cells; every cell moved significantly."
HONESTY_OVERALL_RE = re.compile(r"^Worst-powered cell overall: (\d\.\d{3}) \((.*)\)\.$")
COMPOUND_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9-]*|\*)?((?:[.#][\w-]+)*)$")
VOID_TAGS = {"br", "meta", "img", "hr", "input", "link", "col", "area", "base", "wbr"}


# ---------- harness ----------


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


def run_ids(store: Path) -> set[str]:
    return set(Store(store).runs())


def run_id_of(r: Result, store: Path, before: set[str]) -> str:
    # A sweep ends with a verdict line, not a run id, so the
    # new run is the one run id the store gained during the sweep.
    assert r.lines, r.text
    added = run_ids(store) - before
    assert len(added) == 1, (sorted(added), r.text)
    return added.pop()


def sweep(store: Path, target: str, *extra: str) -> str:
    before = run_ids(store)
    r = run_cli(["--store", str(store), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", target, "--yes", *extra])
    assert r.code == 0, r.text
    return run_id_of(r, store, before)


def svg_panels(path: Path) -> list[str]:
    root = ET.fromstring(path.read_text())
    return [e.attrib["data-panel"] for e in root.iter() if "data-panel" in e.attrib]


def panel_kind(path: Path) -> str:
    """'forest' when cells are ``<g data-cell>`` rows, 'strip' when they are ``<rect data-cell>``
    on one row, 'heatmap' when the rects span several rows."""
    root = ET.fromstring(path.read_text())
    groups = [e for e in root.iter() if e.tag.endswith("g") and "data-cell" in e.attrib]
    rects = [e for e in root.iter() if e.tag.endswith("rect") and "data-cell" in e.attrib]
    if groups and not rects:
        return "forest"
    assert rects and not groups, "a panel is either rows or rects"
    return "strip" if len({r.attrib["y"] for r in rects}) == 1 else "heatmap"


def table_rows(md: str) -> list[str]:
    """Every Markdown table row (header and data rows alike) in document order."""
    return [line for line in md.splitlines() if line.startswith("|")]


def write_two_event_run(
    store: Store,
    run_id: str,
    *,
    salt: str,
    cells: dict[str, tuple[int, int]],
    environment: dict[str, Any] | None = None,
) -> None:
    """A complete synthetic run over outcomes violated / timeout / completed: one cell per label,
    ``cells[label] = (violated, timeout)`` of ``N`` rows, the rest completed. Events sit at
    t=3, completions at the horizon, so the cumulative incidence at the horizon is the count."""
    store.create_run(
        RunManifest(
            run_id=run_id,
            target_id="synthetic@v0",
            t_unit="steps",
            run_salt=salt,
            axis_types={"cell": "categorical"},
            backend="synthetic",
            environment={} if environment is None else environment,
        )
    )
    records = []
    for index, (label, (violated, timeout)) in enumerate(cells.items()):
        for k in range(N):
            if k < violated:
                episode = Episode(outcome="violated", t=3.0, horizon=HORIZON)
            elif k < violated + timeout:
                episode = Episode(outcome="timeout", t=3.0, horizon=HORIZON)
            else:
                episode = Episode(outcome=NON_EVENT, t=HORIZON, horizon=HORIZON)
            records.append(
                EpisodeRecord.from_episode(
                    episode,
                    run_id=run_id,
                    config={"cell": label},
                    seed=1000 * index + k,
                    replicate_index=k,
                    wall_time=0.0,
                )
            )
    store.append(run_id, records)
    store.mark_complete(run_id)


def worse_counts(q: float = Q, *, n: int = N, n_fillers: int = N_FILLERS) -> tuple[int, int]:
    """Smallest swing (lo -> hi) of one event in one cell that is significantly worse after BH
    over the whole two-event family: that cell plus ``n_fillers`` identical-arm cells, two tests
    each, every other p-value 1. Searched, not hand-picked, with the two calls the
    code makes (``fisher_exact`` and ``bh``)."""
    family = 2 * (n_fillers + 1)
    for gap in range(1, n + 1):
        for lo in range(0, n - gap + 1):
            hi = lo + gap
            p = float(fisher_exact([[lo, n - lo], [hi, n - hi]], alternative="two-sided")[1])
            if bh(np.array([p, *[1.0] * (family - 1)]), q)[0] < q:
                return lo, hi
    raise AssertionError(f"no significantly worse swing for q={q}, n={n}")


# ---------- receipt.html: a small DOM and a small CSS matcher for C12 ----------


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None
    children: list[Node] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(self.texts)

    def ancestors(self) -> list[Node]:
        out, node = [], self.parent
        while node is not None:
            out.append(node)
            node = node.parent
        return out

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())


class Dom(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, None)
        self.current = self.root
        self.nodes: list[Node] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: v or "" for k, v in attrs}, self.current)
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


def parse_html(text: str) -> Dom:
    dom = Dom()
    dom.feed(text)
    dom.close()
    return dom


def strip_at_blocks(css: str) -> str:
    """Drop every ``@...{...}`` block (the print media query among them); screen rules remain."""
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


def css_rules(css: str) -> list[tuple[list[str], dict[str, str]]]:
    rules = []
    for block in strip_at_blocks(css).split("}"):
        if "{" not in block:
            continue
        selectors, _, body = block.partition("{")
        rules.append(([s.strip() for s in selectors.split(",") if s.strip()], declarations(body)))
    return rules


def declarations(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in body.split(";"):
        prop, sep, value = item.partition(":")
        if sep:
            out[prop.strip().lower()] = value.strip().lower()
    return out


def compound_matches(node: Node, compound: str) -> bool:
    m = COMPOUND_RE.match(compound)
    if m is None:
        return False
    tag, qualifiers = m.group(1), m.group(2)
    if tag not in (None, "", "*") and tag.lower() != node.tag:
        return False
    for kind, name in re.findall(r"([.#])([\w-]+)", qualifiers):
        if kind == "." and name not in node.classes():
            return False
        if kind == "#" and node.attrs.get("id") != name:
            return False
    return True


def selector_matches(node: Node, selector: str) -> bool:
    """Descendant semantics for whitespace and ``>`` alike; anything else does not match."""
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


def inside_svg(node: Node) -> bool:
    return any(a.tag == "svg" for a in node.ancestors())


def body_nodes_containing(dom: Dom, needle: str) -> list[Node]:
    return [n for n in dom.nodes if needle in n.text and not inside_svg(n) and n.tag != "svg"]


def wraps(node: Node, rules: list[tuple[list[str], dict[str, str]]]) -> bool:
    for n in (node, *node.ancestors()):
        s = styles_of(n, rules)
        if s.get("white-space") == "nowrap":
            return False
        if s.get("overflow") == "hidden" or s.get("overflow-x") == "hidden":
            return False
    return True


# ---------- fixtures ----------


@dataclass(frozen=True)
class MockPair:
    root: Path
    a: str  # rollout, salt QUICKSTART_SALT
    b: str  # rollout_patched, --pair-with a

    @property
    def store(self) -> Store:
        return Store(self.root)


@pytest.fixture(scope="module")
def pair(tmp_path_factory: pytest.TempPathFactory) -> MockPair:
    """The two quickstart runs under the S12 salt. Never mutated by a test."""
    root = tmp_path_factory.mktemp("mock-store")
    a = sweep(root, ROLLOUT, "--salt", QUICKSTART_SALT)
    b = sweep(root, PATCHED, "--pair-with", a)
    return MockPair(root=root, a=a, b=b)


@pytest.fixture
def store_root(tmp_path: Path) -> Path:
    return tmp_path / "store"


@pytest.fixture
def worse_pair(tmp_path: Path) -> Path:
    """Two paired synthetic runs: ``violated`` rises significantly in cell x and nowhere else;
    ``timeout`` is identical in both arms everywhere."""
    lo, hi = worse_counts()
    store = Store(tmp_path / "syn")
    cells_a = {"x": (lo, 4), **{f"f{i}": (4, 4) for i in range(N_FILLERS)}}
    cells_b = {"x": (hi, 4), **{f"f{i}": (4, 4) for i in range(N_FILLERS)}}
    write_two_event_run(store, "syn-a", salt="syn", cells=cells_a)
    write_two_event_run(store, "syn-b", salt="syn", cells=cells_b)
    return tmp_path / "syn"


@pytest.fixture
def captured_forest(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Wrap ``cli.build_multi_report`` so the ``ReportSpec.forest`` it is handed is recorded."""
    seen: list[str] = []
    original = report_module.build_multi_report

    def wrapper(multi: Any, spec: Any, **kwargs: Any) -> Any:
        seen.append(spec.forest)
        return original(multi, spec, **kwargs)

    monkeypatch.setattr(cli, "build_multi_report", wrapper)
    return seen


class LocalMapper:
    """Runs every batch through ``worker_batch`` in-process, carrying ``import_path`` the way the
    Modal mapper does so ``run_with_mapper`` records it in the manifest."""

    def __init__(self, import_path: str) -> None:
        self.import_path = import_path

    def __call__(self, batches: Sequence[Sequence[Job]]) -> Iterator[tuple[int, Any]]:
        for k, jobs in enumerate(batches):
            yield k, worker_batch([tuple(job) for job in jobs], self.import_path, None)  # type: ignore[misc]


def fake_run_modal(
    p: Any,
    target: ModalTarget,
    store: Store,
    *,
    options: ModalOptions | None = None,
    on_progress: Any = None,
) -> Any:
    return run_with_mapper(
        p,
        LocalMapper(target.import_path),
        store,
        options=ModalOptions() if options is None else options,
        image=target.image,
        on_progress=on_progress,
    )


@pytest.fixture
def modal_in_process(monkeypatch: pytest.MonkeyPatch) -> None:
    # A missing modal package is refused before the plan, so modal must import here.
    monkeypatch.setitem(sys.modules, "modal", importlib.util.module_from_spec(importlib.machinery.ModuleSpec("modal", None)))
    # PF5 (PF5.7): the face runs no backend; the core calls the Modal runner, so
    # the stand-in replaces it where it is defined, which the core reads when it runs a plan.
    monkeypatch.setattr(importlib.import_module("poisson_prove.executor_modal"), "run_modal", fake_run_modal)


# ---------- argv builders ----------


def lattice_argv(verb: str, *extra: str) -> list[str]:
    return ["--store", str(LATTICE_ROOT), verb, lattice.RUN_A, lattice.RUN_B, *extra]


def pair_argv(pair: MockPair, verb: str, *extra: str) -> list[str]:
    return ["--store", str(pair.root), verb, pair.a, pair.b, *extra]


def report_argv(pair: MockPair, out: Path, *extra: str) -> list[str]:
    return pair_argv(pair, "report", "--x", "tool_fail_rate", "--y", "task_id", "--out", str(out), *extra)


def run_report_argv(pair: MockPair, out: Path, *extra: str) -> list[str]:
    return [
        "--store", str(pair.root), "report", pair.a, "--event", "violated", "--event", "timeout",
        "--x", "tool_fail_rate", "--y", "task_id", "--out", str(out), *extra,
    ]


# ---------- C1: single-event diff output is unchanged ----------


def test_c1_single_event_diff_headline_reads_twenty_two_lower_zero_higher_fisher() -> None:
    # PF3: the lattice's runs share a salt, so the default is the paired
    # test; these numbers are the unpaired test's, named.
    r = run_cli(lattice_argv("diff", "--event", lattice.EVENT, "--method", "fisher_bh"))
    assert r.code == 0, r.text
    lower, higher = lattice.directions(lattice.fisher(lattice.EVENT, Q))
    assert (lower, higher) == (22, 0)
    assert LATTICE_HEADLINE == f"{lattice.EVENT}: {lower} lower, {higher} higher"
    assert LATTICE_HEADLINE in r.lines, r.out
    assert "fisher_bh" in r.out, r.out
    assert not [line for line in r.out.splitlines() if line.startswith(INFERENCE_MARKER)], r.out


# ---------- C2: inference ----------


def test_c2_no_event_prints_inference_line_first_then_a_headline_naming_both_events(pair: MockPair) -> None:
    r = run_cli(pair_argv(pair, "diff"))
    assert r.code == 0, r.text
    # PF2: diff opens with a verdict block that ends at the first blank
    # line; the inference line is the first line of the report after it.
    verdict, _, report = r.out.partition("\n\n")
    assert verdict and not verdict.startswith(INFERENCE_MARKER), r.out
    report_lines = [line for line in report.splitlines() if line.strip()]
    first = report_lines[0]
    assert first.startswith(INFERENCE_MARKER), r.out
    assert NON_EVENT in first, first
    assert "violated" in first and "timeout" in first, first
    headline = [line for line in report_lines[1:] if "violated:" in line and "timeout:" in line]
    assert headline, r.out
    # PF4 (PF4.20): neither event's kind is known, so the headline counts in lower/higher.
    assert "lower" in headline[0] and "higher" in headline[0], headline[0]


def test_c2_explicit_event_prints_one_event_and_no_inference_line(pair: MockPair) -> None:
    r = run_cli(pair_argv(pair, "diff", "--event", "violated"))
    assert r.code == 0, r.text
    assert not [line for line in r.out.splitlines() if line.startswith(INFERENCE_MARKER)], r.out
    assert any(line.startswith("violated:") for line in r.lines), r.out
    assert "timeout:" not in r.out, r.out


# ---------- C3: inference failure — not tested, see module docstring ----------


# ---------- C4: --event repeatable ----------


def test_c4_repeated_events_equal_inference_with_inferred_false(pair: MockPair) -> None:
    # diff's JSON form is --json.
    inferred = run_cli(pair_argv(pair, "diff", "--json"))
    explicit = run_cli(pair_argv(pair, "diff", "--event", "violated", "--event", "timeout", "--json"))
    assert inferred.code == 0 and explicit.code == 0, inferred.text + explicit.text
    i, e = json.loads(inferred.out), json.loads(explicit.out)
    assert i["inferred"] is True and i["non_event"] == NON_EVENT
    assert e["inferred"] is False and e["non_event"] is None
    assert set(i["events"]) == set(e["events"]) == MOCK_EVENTS
    assert e["by_event"] == i["by_event"]
    assert e["headline"] == i["headline"]
    assert e["trade_line"] == i["trade_line"]
    assert e["n_tests"] == i["n_tests"]


def test_c4_repeated_events_print_no_inference_line(pair: MockPair) -> None:
    r = run_cli(pair_argv(pair, "diff", "--event", "violated", "--event", "timeout"))
    assert r.code == 0, r.text
    assert not [line for line in r.out.splitlines() if line.startswith(INFERENCE_MARKER)], r.out
    assert any("violated:" in line and "timeout:" in line for line in r.lines), r.out


# ---------- C5: check refuses inference ----------


def test_c5_check_without_event_exits_one_and_lists_the_events_the_runs_carry(pair: MockPair) -> None:
    r = run_cli(pair_argv(pair, "check"))
    # A refusal exits 1.
    assert_clean_refusal(r, 1)
    assert "requires --event" in r.err, r.text
    assert "violated" in r.err and "timeout" in r.err, r.err
    # check's verdict is a first line starting passed or failed; none is printed.
    assert not [line for line in r.text.splitlines() if line.startswith(("passed", "failed"))], r.text


# ---------- C6: check gate over several events ----------


def test_c6_check_fails_when_any_named_event_has_a_worse_cell(worse_pair: Path) -> None:
    # PF3: the hand-built pair's two manifests carry one salt, so the
    # default is the paired test; the worse cell this gate fails on is the unpaired test's, named.
    # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and these runs
    # declare none; --fail-on higher is the same gate ("fail when the rate rose").
    r = run_cli(
        ["--store", str(worse_pair), "check", "syn-a", "syn-b", "--event", "violated", "--event", "timeout",
         "--method", "fisher_bh", "--fail-on", "higher"]
    )
    # A failed check exits 4 and says failed on its first line.
    assert_clean_refusal(r, 4)
    assert r.lines[0].startswith("failed") and not [x for x in r.lines if x.startswith("passed")], r.out


def test_c6_check_on_the_worse_event_alone_fails(worse_pair: Path) -> None:
    # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and these runs
    # declare none; --fail-on higher is the same gate ("fail when the rate rose").
    r = run_cli(["--store", str(worse_pair), "check", "syn-a", "syn-b", "--event", "violated", "--fail-on", "higher"])
    # A failed check exits 4 and says failed on its first line.
    assert_clean_refusal(r, 4)
    assert r.lines[0].startswith("failed") and not [x for x in r.lines if x.startswith("passed")], r.out
    # PF4 (PF4.20): with the kind unknown the count reads 0 lower, 1 higher.
    assert "violated: 0 lower, 1 higher" in r.out, r.out


def test_c6_check_on_the_untouched_event_alone_passes(worse_pair: Path) -> None:
    # PF4 (PF4.20): check's default gate is refused on an event of unknown kind, and these runs
    # declare none; --fail-on higher is the same gate ("fail when the rate rose").
    r = run_cli(["--store", str(worse_pair), "check", "syn-a", "syn-b", "--event", "timeout", "--fail-on", "higher"])
    assert r.code == 0, r.text
    # A passed check says passed on its first line.
    assert r.lines[0].startswith("passed") and not [x for x in r.lines if x.startswith("failed")], r.out
    # PF4 (PF4.20): with the kind unknown the count reads 0 lower, 0 higher.
    assert "timeout: 0 lower, 0 higher" in r.out, r.out


# ---------- C7: report A B file set ----------


def test_c7_one_event_report_writes_three_files_and_one_panel(pair: MockPair, tmp_path: Path) -> None:
    out = tmp_path / "one"
    r = run_cli(report_argv(pair, out, "--event", "violated"))
    assert r.code == 0, r.text
    assert {p.name for p in out.iterdir()} == REPORT_FILES
    assert svg_panels(out / "heatmap.svg") == ["violated"]
    for name in REPORT_FILES:
        assert name in r.out, name


def test_c7_inferred_report_writes_the_same_three_files_and_one_panel_per_event(pair: MockPair, tmp_path: Path) -> None:
    out = tmp_path / "multi"
    r = run_cli(report_argv(pair, out))
    assert r.code == 0, r.text
    assert {p.name for p in out.iterdir()} == REPORT_FILES
    panels = svg_panels(out / "heatmap.svg")
    assert len(panels) == 2 and set(panels) == MOCK_EVENTS, panels
    for name in REPORT_FILES:
        assert name in r.out, name


# ---------- C8: report goes through the multi path ----------


def lattice_report(tmp_path: Path) -> str:
    # PF3: the lattice's runs share a salt, so the default is the paired
    # test; the report C8 reads is the unpaired test's, named.
    out = tmp_path / "lattice-report"
    r = run_cli(lattice_argv("report", "--event", lattice.EVENT, "--x", lattice.Y, "--y", lattice.X, "--out", str(out), "--method", "fisher_bh"))
    assert r.code == 0, r.text
    return (out / "report.md").read_text()


def test_c8_single_event_report_has_the_two_line_honesty_block(tmp_path: Path) -> None:
    lines = lattice_report(tmp_path).splitlines()
    firsts = [i for i, line in enumerate(lines) if HONESTY_FIRST_RE.match(line) or line == HONESTY_NONE]
    assert len(firsts) == 1, lines
    assert HONESTY_OVERALL_RE.match(lines[firsts[0] + 1]), lines[firsts[0] : firsts[0] + 2]


def test_c8_single_event_worst_cells_use_the_multi_tiebreak(tmp_path: Path) -> None:
    # diff's JSON form is --json.
    # PF3: the lattice's runs share a salt, so the default is the paired
    # test; the cells ordered here are the unpaired test's, named.
    j = run_cli(lattice_argv("diff", "--event", lattice.EVENT, "--json", "--method", "fisher_bh"))
    assert j.code == 0, j.text
    cells = json.loads(j.out)["by_event"][lattice.EVENT]["cells"]
    # PF4 (PF4.12, PF4.15): a cell at a 100% baseline has no detection limit (mde null); the
    # tiebreak ascends mde, best-powered first, so a cell that can detect nothing sorts last.
    ordered = sorted(
        cells,
        key=lambda c: (-c["delta"], c["q"], math.inf if c["mde"] is None else c["mde"], c["config_hash"]),
    )
    expected = [(float(c["config"][lattice.Y]), float(c["config"][lattice.X])) for c in ordered[:10]]
    plain = sorted(cells, key=lambda c: (-c["delta"], c["config_hash"]))
    assert [c["config_hash"] for c in plain[:10]] != [c["config_hash"] for c in ordered[:10]], (
        "the lattice's top ten must distinguish the tiebreak from the S8 order"
    )

    lines = lattice_report(tmp_path).splitlines()
    heading = lines.index(f"## {LATTICE_HEADLINE}")
    rows = [line for line in lines[heading:] if line.startswith("|")][2:12]
    assert len(rows) == 10, rows
    printed = [(float(row.split("|")[1]), float(row.split("|")[2])) for row in rows]
    assert printed == expected


# ---------- C9: report RUN ----------


def test_c9_single_run_report_writes_three_files_with_one_panel_per_event(pair: MockPair, tmp_path: Path) -> None:
    out = tmp_path / "run-report"
    r = run_cli(run_report_argv(pair, out))
    assert r.code == 0, r.text
    assert {p.name for p in out.iterdir()} == REPORT_FILES
    panels = svg_panels(out / "heatmap.svg")
    assert len(panels) == 2 and set(panels) == MOCK_EVENTS, panels
    md = (out / "report.md").read_text()
    assert not re.search(r"\bdelta\b", md), md
    # PF4.30, PF4.48a: the header's design limit names the test's level
    # ("q 0.05 over 9 tests"); no other line of a single-run report carries a q.
    design = [line for line in md.splitlines() if line.startswith("design limit ")]
    assert len(design) == 1, md
    assert not [line for line in md.splitlines() if line not in design and re.search(r"\bq\b", line)], md
    assert not re.search(r"\bsafer\b", md), md
    for name in REPORT_FILES:
        assert name in r.out, name


def test_c9_single_run_report_defaults_to_a_prove_report_folder_for_one_run(pair: MockPair, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = run_cli([
        "--store", str(pair.root), "report", pair.a, "--event", "violated",
        "--x", "tool_fail_rate", "--y", "task_id",
    ])
    assert r.code == 0, r.text
    (out,) = [p for p in tmp_path.iterdir() if p.name.startswith("prove-report-")]
    assert "-vs-" not in out.name and out.is_dir(), sorted(p.name for p in tmp_path.iterdir())
    assert {p.name for p in out.iterdir()} == REPORT_FILES


@pytest.mark.parametrize(
    "flag",
    [("--method", "fisher_bh"), ("--methods", "all"), ("--q", "0.05")],
    ids=["method", "methods", "q"],
)
def test_c9_diff_only_flags_are_refused_by_name_on_a_single_run(pair: MockPair, tmp_path: Path, flag: tuple[str, str]) -> None:
    out = tmp_path / "refused"
    r = run_cli(run_report_argv(pair, out, *flag))
    # A refusal exits 1.
    assert_clean_refusal(r, 1)
    assert flag[0] in r.err, r.text
    assert not out.exists() or not any(out.iterdir())


# ---------- C10: --horizon ----------


def test_c10_default_horizon_is_the_frame_max_t_and_appears_in_provenance(pair: MockPair, tmp_path: Path) -> None:
    t_max = float(pair.store.read(pair.a)["t"].max())
    assert t_max == 20.0, t_max
    r = run_cli(run_report_argv(pair, tmp_path / "h-default"))
    assert r.code == 0, r.text
    md = (tmp_path / "h-default" / "report.md").read_text()
    assert "- horizon: 20\n" in md, md


def test_c10_horizon_below_the_frame_max_changes_a_rate(pair: MockPair, tmp_path: Path) -> None:
    base = run_cli(run_report_argv(pair, tmp_path / "h-default"))
    low = run_cli(run_report_argv(pair, tmp_path / "h-3", "--horizon", "3"))
    assert base.code == 0 and low.code == 0, base.text + low.text
    md_base = (tmp_path / "h-default" / "report.md").read_text()
    md_low = (tmp_path / "h-3" / "report.md").read_text()
    assert table_rows(md_low) != table_rows(md_base)
    assert "- horizon: 3\n" in md_low, md_low


def test_c10_horizon_above_the_frame_max_is_accepted_and_changes_no_rate(pair: MockPair, tmp_path: Path) -> None:
    base = run_cli(run_report_argv(pair, tmp_path / "h-default"))
    high = run_cli(run_report_argv(pair, tmp_path / "h-100", "--horizon", "100"))
    assert base.code == 0 and high.code == 0, base.text + high.text
    md_base = (tmp_path / "h-default" / "report.md").read_text()
    md_high = (tmp_path / "h-100" / "report.md").read_text()
    assert table_rows(md_high) == table_rows(md_base)
    assert "- horizon: 100\n" in md_high, md_high


# ---------- C11: --forest ----------


def single_axis_argv(pair: MockPair, out: Path, axis: str, *extra: str) -> list[str]:
    fix = 'task_id="search"' if axis == "tool_fail_rate" else "tool_fail_rate=0.3"
    return pair_argv(pair, "report", "--event", "violated", "--x", axis, "--fix", fix, "--out", str(out), *extra)


def test_c11_forest_always_renders_a_forest_on_a_numeric_axis(pair: MockPair, tmp_path: Path, captured_forest: list[str]) -> None:
    out = tmp_path / "always"
    r = run_cli(single_axis_argv(pair, out, "tool_fail_rate", "--forest", "always"))
    assert r.code == 0, r.text
    assert panel_kind(out / "heatmap.svg") == "forest"
    assert captured_forest and all(f == "always" for f in captured_forest), captured_forest


def test_c11_forest_never_renders_a_strip_on_a_categorical_axis(pair: MockPair, tmp_path: Path, captured_forest: list[str]) -> None:
    out = tmp_path / "never"
    r = run_cli(single_axis_argv(pair, out, "task_id", "--forest", "never"))
    assert r.code == 0, r.text
    assert panel_kind(out / "heatmap.svg") == "strip"
    assert captured_forest and all(f == "never" for f in captured_forest), captured_forest


def test_c11_forest_auto_picks_forest_for_a_categorical_axis(pair: MockPair, tmp_path: Path, captured_forest: list[str]) -> None:
    out = tmp_path / "auto-cat"
    r = run_cli(single_axis_argv(pair, out, "task_id"))
    assert r.code == 0, r.text
    assert panel_kind(out / "heatmap.svg") == "forest"
    assert captured_forest and all(f == "auto" for f in captured_forest), captured_forest


def test_c11_forest_auto_picks_a_strip_for_a_numeric_axis(pair: MockPair, tmp_path: Path, captured_forest: list[str]) -> None:
    out = tmp_path / "auto-num"
    r = run_cli(single_axis_argv(pair, out, "tool_fail_rate", "--forest", "auto"))
    assert r.code == 0, r.text
    assert panel_kind(out / "heatmap.svg") == "strip"
    assert captured_forest and all(f == "auto" for f in captured_forest), captured_forest


# ---------- C12: receipt fits ----------


def test_c12_receipt_has_a_bounded_body_a_scrolling_svg_and_wrapping_text(pair: MockPair, tmp_path: Path) -> None:
    out = tmp_path / "receipt"
    r = run_cli(report_argv(pair, out))
    assert r.code == 0, r.text
    # diff's JSON form is --json.
    j = run_cli(pair_argv(pair, "diff", "--json"))
    assert j.code == 0, j.text
    data = json.loads(j.out)
    headline_first = data["headline"].splitlines()[0]
    trade = data["trade_line"]
    assert trade is not None, "the S12 pair carries a trade line"

    dom = parse_html((out / "receipt.html").read_text())
    styles = [n for n in dom.nodes if n.tag == "style" and not inside_svg(n)]
    assert styles, "receipt.html must carry an inline stylesheet"
    rules = css_rules("\n".join(n.text for n in styles))
    assert rules, "the inline stylesheet must contain rules"

    headline_nodes = body_nodes_containing(dom, headline_first)
    trade_nodes = body_nodes_containing(dom, trade)
    honesty_nodes = body_nodes_containing(dom, "Worst-powered")
    assert headline_nodes and trade_nodes and honesty_nodes

    headline = headline_nodes[-1]
    assert any("max-width" in styles_of(a, rules) for a in headline.ancestors()), (
        "no ancestor of the headline carries a max-width rule"
    )

    svgs = [n for n in dom.nodes if n.tag == "svg" and not inside_svg(n)]
    assert svgs, "receipt.html must inline the stacked SVG"
    scroll = {"auto", "scroll"}
    for svg in svgs:
        containers = [a for a in svg.ancestors() if a.tag not in ("html", "body", "#document")]
        assert any(
            styles_of(a, rules).get("overflow-x") in scroll or styles_of(a, rules).get("overflow") in scroll
            for a in containers
        ), "no container of the SVG scrolls horizontally"

    for node in (*headline_nodes, *trade_nodes, *honesty_nodes):
        assert wraps(node, rules), (node.tag, node.attrs, node.text[:60])


# ---------- C13: local manifest import path ----------


def test_c13_local_sweep_records_the_target_as_import_path(pair: MockPair) -> None:
    manifest = pair.store.manifest(pair.a)
    assert manifest.backend == "local"
    assert manifest.environment["import_path"] == ROLLOUT


def test_c13_inspect_on_a_local_run_prints_the_real_import(pair: MockPair) -> None:
    r = run_cli(["--store", str(pair.root), "inspect", pair.a, "--event", "violated", "--limit", "1"])
    assert r.code == 0, r.text
    assert SNIPPET_MARKER in r.out, r.out
    assert REAL_IMPORT in r.lines, r.out
    assert "your_module" not in r.out, r.out


# ---------- C14: modal parity ----------


def test_c14_modal_run_records_the_same_import_path_and_inspects_the_same(store_root: Path, modal_in_process: None) -> None:
    before = run_ids(store_root)
    modal = run_cli([
        "--store", str(store_root), "sweep", str(QUICKSTART), *QUICKSTART_MAX_MDE, "--target", ROLLOUT,
        "--backend", "modal", "--yes",
    ])
    assert modal.code == 0, modal.text
    modal_id = run_id_of(modal, store_root, before)
    local_id = sweep(store_root, ROLLOUT)
    store = Store(store_root)
    mm, ml = store.manifest(modal_id), store.manifest(local_id)
    assert mm.backend == "modal" and ml.backend == "local"
    assert mm.environment["import_path"] == ROLLOUT
    assert ml.environment["import_path"] == ROLLOUT
    assert mm.environment["import_path"] == ml.environment["import_path"]

    r = run_cli(["--store", str(store_root), "inspect", modal_id, "--event", "violated", "--limit", "1"])
    assert r.code == 0, r.text
    assert REAL_IMPORT in r.lines, r.out
    assert "your_module" not in r.out, r.out


# ---------- C15: old runs still inspect ----------


def test_c15_manifest_without_import_path_prints_the_fallback_snippet(tmp_path: Path) -> None:
    store = Store(tmp_path / "old")
    write_two_event_run(store, "old-run", salt="old", cells={"c": (5, 2)})
    assert "import_path" not in store.manifest("old-run").environment
    r = run_cli(["--store", str(tmp_path / "old"), "inspect", "old-run", "--event", "violated"])
    assert r.code == 0, r.text
    assert "Traceback" not in r.text and not r.err.strip(), r.text
    assert SNIPPET_MARKER in r.out, r.out
    assert FALLBACK_IMPORT in r.lines, r.out


# ---------- C16: exit codes; a usage error is 2, a refusal 1 ----------


def test_c16_report_with_three_positionals_is_a_two_naming_both_forms(pair: MockPair, tmp_path: Path) -> None:
    out = tmp_path / "three"
    r = run_cli([
        "--store", str(pair.root), "report", pair.a, pair.b, pair.a,
        "--x", "tool_fail_rate", "--y", "task_id", "--out", str(out),
    ])
    assert_clean_refusal(r, 2)
    assert r.err.strip(), "expected a message on stderr"
    assert not out.exists() or not any(out.iterdir())


def test_c16_unknown_run_exits_one_without_a_traceback(pair: MockPair) -> None:
    r = run_cli(["--store", str(pair.root), "diff", pair.a, "no-such-run"])
    # A refusal exits 1.
    assert_clean_refusal(r, 1)
    assert "no-such-run" in r.text, r.text
