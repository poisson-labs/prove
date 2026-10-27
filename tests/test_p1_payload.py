"""P-1 frozen tests: invariants Y1 to Y22 of the P-1 payload shape, written
before ``seed_identity_match``, ``unpaired_analysis``, ``_seed_identity``, ``RootResult.p_floor``,
the ``intervals`` payload key, the interval column, the floor lines, the ``seed_identity_basis``
statement and ``render_html``'s intervals refusal exist, against ``a626cd3`` -- the A8a
build, the commit the measurements were taken on.

**The decisions this file is built to:** D1-D6 are settled and
not reopened. Seed identity is the salt plus the stored seed on every matched row,
and A23/A26's two manifest fields join the same predicate later; Y1-Y6 are written against the pairing
rule as it stands. ``check`` prints no permutation p, and Y17's last clause asserts
it prints none. ``RootResult.p_floor`` is a design constant of the permutation
count, not a statistic; Y21 guards the reading. Leaning, not settled: the page's interval
paragraph sits before the bound, the column is last, after ``MDE``, and there is no drill-down row.

**Two cells, and no invariant is cell-specific -- a result, not an assumption** (D7 binds one
cell; this file reports two because both were asked for). pandas 2.3.3 and pandas 3.0.5, A22's recipe: every test here is asserted in both
cells, and the map is the whole file twice: **24 + 24 = 48 ids over the two cells against
this file's own 24.**

**The classified red set on the update commit with this file added, measured
on two pristine ``git archive`` copies of ``a626cd3`` carrying the update and this file, before any
source edit, venvs from the repo venv's freeze closure differing in exactly pandas, collection
verified 1983 = 1983 = 1983 at ``a626cd3`` and then 2007 = 2007 = 2007 = 2007 (both cells, the shim, the
repo) with the update and this file, baselines 1978 passed / 5 skipped / 0 failed in both cells at
``a626cd3``: 204 failed / 1798 passed / 5 skipped, identical test by test in both cells.** The 204:
the **22** tests here that are not Y3's unchanged-manifest-sentence test and Y22 (every one for its expected cause -- the two fields,
``_seed_identity``'s refusals and warning, the headline token, the provenance keys, the thirteenth
key, the column, the floor field and its lines, the refusal, the ``unverified`` id, the ``p_floor``
assignment site do not exist yet; Y19's schema-comment clause is the one that stays red on a shim
without the comment); and **182** update reds by file -- ``test_m7_report.py`` 46 (the ``make_diff``
builder's two keywords reach 44, I4's token, I16's key tuple), ``test_m7_multi.py`` 42 (both builders,
B1's mapped record, B15), ``test_m6_multi.py`` 18, ``test_m6_diff.py`` 12 (``SUMMARY_FIELDS``, the
reads, I13 renamed, I15's tokens), ``test_s29_viewer.py`` 9 (W1 x2, W3, W4, W5, W9 x2, W11, W17; W20's
digest test is green until the build and W20's sweep is green before and after), ``test_s24_interval.py`` 9,
``test_s21_errors.py`` 8, ``test_s28_report.py`` 8 (R2 x2, R4 x2, R13 through R4's kind-table helper,
R19's check and serve digests, R21 x2), ``test_s25_root.py`` 7, ``test_s26_fault_lines.py`` 7,
``test_s27_leaves.py`` 6, ``test_m10_cli.py`` 4 (I9 x2 -- the ``--methods all`` column's ``paired`` was
hidden inside ``unpaired`` as a substring on the prototype -- I10, I20), ``test_m13_viewer.py`` 2 (V31,
V33), ``test_a28_agreement.py`` 1 (G9; G18 amended per record, green before and after; G20 green until
the build), ``test_a7_storage.py`` 1 (P7-10's verb digests), ``test_m11a_chaos.py`` 1 and
``test_unpaired_warning.py`` 1 (U9 inverted). Against the predicted count of about 174 update reds
(187 minus the eight fixture-seed tests minus the five source-digest clauses), the measured 182
reconciles exactly: of the eight fixture-seed tests only three go green (I6 x2, O21) and five stay red
as ordinary renames (I6's statsmodels test, I13, I18[mcnemar_bh], R21 x2); of the five source-digest
clauses only three *tests* go green (G20, F28, L20) while R19 and W20 stay red on their check and
serve digests; V36 and W3 are green before and after beside O11 (V36 reads the column count off the
header, W3 checks ``text`` against the kind table in the direction the table now satisfies); and four
movers the prototype hid or reached through a helper are new -- I9's column and I15's tokens (their
``paired`` sat inside ``unpaired`` as a substring), R13 and R4's second test (the kind table). 187 - 3
- 3 - 3 + 4 = 182. **Nothing else is
red.** The pandas 3 cell adds nothing: no P-1 field reaches disk. The copies skip 5 where the repo
skips 3, the two extra being a real-suite pair whose data file is gitignored.

**What was measured before the build at ``a626cd3``, so the frozen file rests on runs and not on reads.** (1)
Three fixtures pair by dict position: ``test_s28_report.py``'s ``overlap``
pair matches 24 rows and **24 of 24 disagree** (the predicted "16 of 48" is O21's figure, not this
pair's); ``test_s25_root.py``'s O21 pair matches 48 and **16 of 48 disagree**; ``test_m6_diff.py``'s
``_one_cell`` has no ``seed`` column. (2) **A fourth fixture the spec does not name**:
``test_s21_errors.py``'s synthetic pair matches 128 raw rows and **16 disagree** (99 analysed rows
under ``--methods all``, which is where E12 refused on the prototype). All four are made honest in
the update commit by a seed that is a function of ``(config, replicate_index)``; after the fix
every pair matches with 0 disagreeing, measured. (3) A stored pair's ``heatmap.svg`` **does** move under
D1: its subtitle is the headline's second line, so ``paired)`` became ``unpaired)`` in the SVG too;
the expectation that "the SVG's bytes do not move" is wrong and every E14 carrier's SVG digest is
re-minted. (4) ``tree.py`` narrowed at ``("RootResult", "_root")`` digests to ``83ec3494...`` on the
bare tree, the predicted figure, and the two regions are 228-303 and 853-890 of 2192.

**Green-before-and-after, named so its green is not read as evidence**: Y3's
missing-manifest test (the sentence is ``a626cd3``'s, byte for byte), Y22 (no store write, the E-family
guard restated), Y6's claim (the statistic never followed provenance; the twin construction is U8's,
C12's and O6's -- the test itself is red until the build only because it reads the renamed field), Y21's honesty and
build-closure clauses (the strings are pinned to ``a626cd3``'s bytes and the closure's one ``Sub``
is W20's rule), and the four fixture-seed edits in the update (nothing on the bare tree reads a
stored seed).

**Mutation list for the build** (twenty-one rows; the pass runs in the mutation harness after the
build). The sole-catch claims this file is written to
carry: mutant 2 (seeds compared positionally over all rows) by Y5's partial-overlap variant alone;
mutant 3 (zero matched rows read as a match) by Y1's zero-overlap draws alone; mutant 13
(``alpha*`` printed ``.4f``) by Y12's small-alpha family alone; mutant 15 (``p_floor = 1 / B``) by
Y16's exact equality on the generated lattice pair alone; mutant 17 (``render_html`` tolerating a missing ``intervals``) by
Y15 alone; mutant 21 (intervals joined by ``config_hash`` alone) by Y14's two-event pair alone,
whose endpoints differ across events on the same cell by construction. **One survivor predicted in
advance and not mutated here**: the seed check run over the raw frames instead of the analysed
ones -- no fixture here carries an errored row whose seed disagrees while every analysed row agrees,
and this file does not mint one; the build names it as the survivor.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import html as html_mod
import json
import os
import re
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import lattice
import poisson_prove.cli as cli
import poisson_prove.diff as diff_mod
import poisson_prove.viewer as viewer_mod
from poisson_prove.diff import DiffResult, MultiDiffResult, NotPairable, UnpairedAnalysis, diff, multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import ReportSpec, build_multi_report, build_report
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from poisson_prove.survival import censor
from poisson_prove.tree import omnibus, tree
from poisson_prove.viewer import SCHEMA, ViewerError, build_structure, render_html

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "poisson_prove"
DIFF_SOURCE, REPORT_SOURCE, TREE_SOURCE, VIEWER_SOURCE, CLI_SOURCE = (SRC / f"{n}.py" for n in ("diff", "report", "tree", "viewer", "cli"))
#: The generated lattice pair (``tests/lattice.py``): two runs of one design that share a salt.
LATTICE_ROOT = lattice.root()
LATTICE_A, LATTICE_B = lattice.RUN_A, lattice.RUN_B
EVENT, X, Y = lattice.EVENT, lattice.X, lattice.Y

# ---------- the literals, verbatim ----------

#: ``_PAIRED_METHODS`` stays private and is the one predicate every pairing token reads.
PAIRED_METHODS = ("mcnemar_bh",)
METHODS = ("fisher_bh", "mcnemar_bh", "logrank_bh")
#: Y7. Both key-set literals, ``seed_identity_match`` and ``unpaired_analysis`` in ``paired``'s slot.
SUMMARY_FIELDS = (
    "method", "seed_identity_match", "unpaired_analysis", "q", "event", "t_unit", "horizon", "n_safer",
    "n_worse", "n_unchanged", "n_not_comparable", "max_mde", "dropped_a", "dropped_b", "truncated",
    "max_mde_unchanged", "max_mde_unchanged_cell",
)
MULTI_SUMMARY_FIELDS = (
    "method", "seed_identity_match", "unpaired_analysis", "q", "t_unit", "horizon", "n_tests",
    "n_not_comparable", "dropped_a", "dropped_b", "truncated", "inferred", "non_event",
)
#: Y9. ``build_multi_report``'s provenance keys in order; S21's tuple with the two keys in ``paired``'s slot.
#: **Updated 2026-09-20 (truncation surfacing):** ``truncated`` -- the horizon count -- is
#: ``episodes_censored_at_horizon`` in its slot, and the run-identity block is followed by each run's
#: recorded byte limit, its span count and its count of spans stamped as cut, as the CLI passes them.
MULTI_PROVENANCE_KEYS = (
    "events", "inferred", "non_event", "n_tests", "method", "seed_identity_match", "unpaired_analysis",
    "q", "t_unit", "horizon", "n_not_comparable", "dropped_a", "dropped_b", "episodes_censored_at_horizon", "n_absent",
    "poisson_prove_version", "run_id_a", "run_id_b", "run_salt",
    "observation_cap_a", "observation_cap_b", "trace_spans_a", "trace_spans_b",
    "observation_cut_spans_a", "observation_cut_spans_b",
)
#: Y10. The page's thirteen root keys, ``intervals`` after ``panels``, and the ten interval keys.
#: LS update: fourteen, ``summary`` eighth.
TOP_LEVEL_KEYS = (
    "schema", "pair", "diff", "holes", "view", "headline", "trade_line", "summary", "fence", "panels",
    "intervals", "tree", "unverified", "heatmap_svg",
)
INTERVALS_KEYS = ("family", "q", "n_tests", "n_rejected", "level", "alpha_star", "n_interval_only", "n_verdict_only", "lines", "rows")
INTERVAL_ROW_KEYS = ("event", "config_hash", "ci_lo", "ci_hi", "basis", "text")
#: Y20. The ``unverified`` ids in order and the statement that replaces ``paired_basis``.
UNVERIFIED_IDS = ("outcome_labels", "status_basis", "created_at_meaning", "seed_identity_basis")
SEED_IDENTITY_BASIS = (
    "seed_identity_match is true when both manifests carry the same run_salt and every row this "
    "comparison matched stores the same seed in both arms at the same (config_hash, replicate_index). "
    "It compares the seeds that were stored, not what the target did with them."
)
#: Y3. The pairing refusal table: the first two byte-identical to ``a626cd3``'s, three new.
REFUSAL_MANIFESTS = "mcnemar_bh needs both manifests to establish pairing"
REFUSAL_SALT = "mcnemar_bh needs matching run_salt; got {a!r} vs {b!r}"
REFUSAL_NO_SEED = "mcnemar_bh needs the stored seed to establish pairing; frame {frame} has no seed column"
REFUSAL_NO_MATCH = "mcnemar_bh needs matched rows; no (config_hash, replicate_index) is present in both runs"
REFUSAL_SEEDS_DIFFER = (
    "mcnemar_bh needs matched rows to share their seed; {k} of {n} rows matched at the same "
    "(config_hash, replicate_index) carry different seeds"
)
#: Y4. The pairing warning, one line, fields in braces.
WARNING = (
    "{method} compares two runs that share their seeds as independent samples: both manifests carry "
    "run_salt {salt!r}, and each of the {n} rows this comparison matched across its cells stores the "
    "same seed in both arms at the same (config_hash, replicate_index); the cells one arm ran and the "
    "other did not are in coverage. Pass method='mcnemar_bh' to test that correspondence; whether it "
    "buys power depends on how far the two arms agree episode by episode."
)
#: Y8. The lattice under ``fisher_bh``, ``--event tripped``: the headline on every surface.
# PF4 (PF4.20): ``tripped`` has no declared kind, so the headline counts read in direction words
# ("N lower, M higher"). The counts are the reference's (``lattice.fisher``: 22 conditions lower,
# 0 higher, over the design's 72), which Y8 asserts beside the literal.
LATTICE_LOWER, LATTICE_HIGHER, LATTICE_TESTS = 22, 0, 72
LATTICE_HEADLINE = "tripped: 22 lower, 0 higher\n(aalen_johansen + fisher_bh, BH q<0.05 over 72 tests, unpaired)"
LATTICE_SINGLE_HEADLINE = "22 of 72 cells safer, 0 worse (fisher_bh, BH q<0.05, unpaired)."
#: Y7. ``to_markdown()``'s parameter line on the lattice starts with these tokens.
LATTICE_PARAMETER_LINE_PREFIX = "method=fisher_bh, seed_identity_match=True, unpaired_analysis=True, q=0.05, t_unit=seconds, horizon=5.0, n_tests=72, "
#: Y11. The three interval lines on the lattice's ``tripped``, and the ``R == 0`` line. The
#: first line's level and ``alpha*`` are ``1 - q R / M`` and ``q R / M`` at the reference's R = 22 and
#: M = 72 (Y11 recomputes them); the 3 conditions whose interval excludes zero while the verdict is
#: unchanged are Prove's count, measured on main's unchanged ``src/`` (05cd1e8).
LATTICE_INTERVAL_LINES = (
    "intervals: 98.4722% (alpha* = 0.0152778 = q x 22 / 72 over the flat BH family), basis score_rd",
    "interval excludes zero, verdict unchanged: 3 cells",
    "verdict significant, interval covers zero: 0 cells",
)
NO_INTERVAL_LINE = "intervals: none (nothing significant; the MDE lines above are the honest bound)"
FAMILY_TOKEN = "over the flat BH family"
INTERVAL_COLUMN = "interval (pp)"
#: Y17. The floor lines, fields in braces; the CLI spells the floor ``:g`` and the count bare,
#: M7 and the page spell them ``sig3`` and ``int``.
# The command line prints p_floor under rule 10: the caller formats it with fmt_p10.
CLI_FLOOR_LINE = "  p floor {p_floor}: the smallest p {n_permutations} permutations can express; a p at the floor is a bound, not a measurement"
CLI_GROUP_FLOOR_LINE = "  group p floor {p_floor}: the same {n_permutations} permutations; a group p at the floor is a bound, not a measurement"
M7_FLOOR_LINE = "p floor {p_floor}: the smallest p {n_permutations} permutations can express; a p at the floor is a bound, not a measurement"
M7_GROUP_FLOOR_LINE = "group p floor {p_floor}: the same {n_permutations} permutations; a group p at the floor is a bound, not a measurement"
#: Y15. The renderer's intervals refusal, and the ``tree`` refusal it is modelled on (``viewer.py`` at ``a626cd3``).
#: LS update: the refusal interpolates ``SCHEMA`` (LS8).
NO_INTERVALS_REFUSAL = (
    "this structure carries no intervals; it was assembled before the flat family's intervals joined "
    "poisson-prove.viewpair/7 and is not a page this renderer will draw"
)
NO_TREE_REFUSAL = (
    "this structure carries no tree; a page whose honesty block cannot state the bound is not a page "
    "this renderer will draw, and the two ship together or not at all"
)
#: Y13. S29's ``<h2>`` sequence, unchanged by P-1; LS update: ``Summary`` first, ``Run pair`` thirteenth.
H2_SEQUENCE = (
    "Summary", "Events", "Omnibus", "Result", "Honesty", "Not verified", "Fault lines", "Cells", "Heatmap", "Cell",
    "Holes", "Worst cells", "Run pair", "Provenance",
)
#: Y21. Every panel honesty string at ``a626cd3``, byte for byte, measured on the bare tree for the
#: two minted pairs (no second honesty block and no rewording, D6).
# PF4 (PF4.17, PF4.20): Y21 reads each panel's honesty through honesty_as_a626cd3, which puts PF4's
# two rewordings back after asserting them, so these literals stay a626cd3's bytes.
# Since the PF4 re-freeze Y21 reads only each entry's length here (one string per panel); the facts
# of every honesty string are assert_honesty_facts'. The lattice was never run at a626cd3, so its
# entry is its one panel's honesty as main's unchanged src/ (05cd1e8) prints it, standing for the count.
LATTICE_HONESTY = (
    'Worst-powered unchanged cell (gain=0.4, load=30, n=32/32) can only detect a 50pp fall. '
    '"0 higher" is an honest claim only above that.\nWorst-powered cell overall: 50pp (gain=0.6, load=20).',
)
HONESTY_AT_A626CD3 = {
    "lattice": LATTICE_HONESTY,
    "k2": (
        "No unchanged cells; every cell moved significantly.\nWorst-powered cell overall: 28pp (task=t0, temp=0).",
        'Worst-powered unchanged cell (task=t5, temp=0, n=32/32) can only detect a 28pp rise. "0 worse" is an honest '
        "claim only above that.\nWorst-powered cell overall: 28pp (task=t0, temp=0).",
    ),
    "same": (
        'Worst-powered unchanged cell (task=t0, temp=0, n=8/8) can only detect a 64pp rise. "0 worse" is an honest '
        "claim only above that.\nWorst-powered cell overall: 64pp (task=t0, temp=0).",
    ),
}
HONESTY_NONE_AT_A626CD3 = "No unchanged cells; every cell moved significantly."
#: Y16. The lattice at the default 4000 permutations: ``p_omnibus == p_floor == 1/4001`` exactly
#: (measured on main's unchanged ``src/``).
DEFAULT_PERMUTATIONS = 4000
#: W20's two regexes, restated (Y12).
FLOAT_SPEC_RE = re.compile(r":\.\d")
INTERVAL_TOKEN_RE = re.compile(r"\[-?\d+\.\d, -?\d+\.\d\]")
PAIRED_TOKEN_RE = re.compile(r"\bpaired\b")
HORIZON, EVENT_T = 10.0, 3.0
SALT = "p1-oracle-salt"
OTHER_SALT = "p1-oracle-other-salt"


# ---------- helpers: the CLI, the store, the frames ----------


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def run_serve(argv: Sequence[str]) -> tuple[int, str, str, list[str]]:
    """``main`` with ``serve_page`` replaced by a tripwire that records and raises (V5's shape)."""
    calls: list[str] = []

    def trip(*args: Any, **kwargs: Any) -> None:
        calls.append("serve_page")
        raise AssertionError("serve_page was called; something was about to bind")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cli, "serve_page", trip)
        try:
            code, out, err = run_cli(argv)
        except AssertionError:
            return -1, "", "", calls
    return code, out, err, calls


def quiet(fn: Callable[[], Any]) -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpairedAnalysis)
        return fn()


def caught(fn: Callable[[], Any]) -> list[warnings.WarningMessage]:
    with warnings.catch_warnings(record=True) as records:
        warnings.simplefilter("always")
        fn()
    return [r for r in records if r.category is UnpairedAnalysis]


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest(run_id: str, salt: str, axis_types: Mapping[str, str] | None = None) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types or {"task": "categorical", "temp": "continuous"}), backend="synthetic",  # type: ignore[arg-type]
        environment={"note": "built by test_p1_payload"},
    )


def seed_of(config: Mapping[str, Any], replicate_index: int) -> int:
    """A stored seed that is a function of ``(config, replicate_index)``, never of a position."""
    return 1000 * (int(config_hash(config)[:6], 16) % 100_000) + replicate_index


def write_run(
    store: Store, run_id: str, *, salt: str, cells: Mapping[tuple[tuple[str, Any], ...], Sequence[str]],
    seeds: Callable[[Mapping[str, Any], int], int] = seed_of, axis_types: Mapping[str, str] | None = None,
) -> None:
    """A complete run, one episode per outcome, seeds from ``seeds(config, replicate_index)``."""
    store.create_run(manifest(run_id, salt, axis_types))
    records = []
    for key, outcomes in cells.items():
        config = dict(key)
        for k, outcome in enumerate(outcomes):
            t = HORIZON if outcome == "ok" else EVENT_T
            records.append(EpisodeRecord.from_episode(
                Episode(outcome=outcome, t=t, horizon=HORIZON), run_id=run_id, config=config, seed=seeds(config, k),
                replicate_index=k, wall_time=0.0,
            ))
    store.append(run_id, records)
    store.mark_complete(run_id)


def raw_frame(run_id: str, cells: Mapping[str, Sequence[str]], *, seeds: Callable[[Mapping[str, Any], int], int] | None, replicate_start: int = 0) -> pd.DataFrame:
    """An in-memory frame with the columns ``Store.read(meta=False)`` returns; ``seeds=None`` omits the column."""
    rows: list[dict[str, Any]] = []
    for task, outcomes in cells.items():
        config = {"task": task}
        for k, outcome in enumerate(outcomes):
            rep = replicate_start + k
            row: dict[str, Any] = {
                "run_id": run_id, "config_hash": config_hash(config), "config": config, "replicate_index": rep,
                "outcome": outcome, "t": HORIZON if outcome == "ok" else EVENT_T, "horizon": HORIZON,
                "confidence": float("nan"), "error": None, "wall_time": 0.0,
            }
            if seeds is not None:
                row["seed"] = seeds(config, rep)
            rows.append(row)
    frame = pd.DataFrame.from_records(rows)
    for column in ("config", "outcome", "error"):
        frame[column] = frame[column].astype(object)
    return frame


def read_pair(root: Path, a: str, b: str) -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    store = Store(root)
    return store.read(a, meta=False), store.read(b, meta=False), store.manifest(a), store.manifest(b)


def stored_multi(root: Path, a: str, b: str, *, events: Sequence[str] = ("fail",), method: str = "fisher_bh") -> MultiDiffResult:
    fa, fb, ma, mb = read_pair(root, a, b)
    return quiet(lambda: multi_diff(fa, fb, events=list(events), method=method, manifest_a=ma, manifest_b=mb))


def cells_of(n_cells: int, *, n: int, fails: Callable[[int], int], names: Sequence[str] | None = None) -> dict[tuple[tuple[str, Any], ...], list[str]]:
    labels = list(names) if names is not None else [f"t{i}" for i in range(n_cells)]
    return {(("task", label), ("temp", 0.0)): ["fail"] * fails(i) + ["ok"] * (n - fails(i)) for i, label in enumerate(labels)}


# ---------- helpers: a built pair on every surface ----------


@dataclasses.dataclass(frozen=True)
class Built:
    name: str
    multi: MultiDiffResult
    tree: Any
    report: Any
    structure: dict[str, Any]
    page: str
    md: str
    html: str


_BUILT: dict[tuple[Any, ...], Built] = {}


def build_pair(name: str, root: Path, a: str, b: str, *, events: Sequence[str], x: str, y: str | None = None, method: str = "fisher_bh", **knobs: Any) -> Built:
    """``build_multi_report`` with the tree, ``build_structure`` and ``render_html`` on a stored pair,
    the way ``serve`` reaches them; cached by name and knobs."""
    key = (name, tuple(sorted(knobs.items())))
    if key not in _BUILT:
        store = Store(root)
        fa, fb, ma, mb = read_pair(root, a, b)
        multi = quiet(lambda: multi_diff(fa, fb, events=list(events), method=method, manifest_a=ma, manifest_b=mb))
        grown = tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, **knobs)
        spec = ReportSpec(title=f"{a} vs {b}: {', '.join(events)}", x_axis=x, y_axis=y)
        # Updated 2026-09-20: the CLI hands the builders each run's span counts, read from its
        # envelopes. Every store this file builds or reads carries no trace, so the counts are (0, 0).
        counts = ((0, 0), (0, 0))
        report = build_multi_report(multi, spec, manifests=(ma, mb), tree=grown, observations=counts)
        light = build_multi_report(multi, replace(spec, theme="light"), manifests=(ma, mb), tree=grown, observations=counts)
        structure = build_structure(
            report, multi, tree=grown, manifest_a=ma, manifest_b=mb, rows_a=store.count(a), rows_b=store.count(b),
            tally_a=store.tally(a), tally_b=store.tally(b), store_root=str(root),
        )
        _BUILT[key] = Built(name, multi, grown, report, structure, render_html(structure), report.to_markdown(), light.to_html())
    return _BUILT[key]


def h2_lines(page: str) -> list[tuple[int, str]]:
    return [(i, m.group(1)) for i, line in enumerate(page.splitlines()) if (m := re.fullmatch(r"\s*<h2>(.*?)</h2>\s*", line))]


def region_lines(page: str, heading: str) -> list[str]:
    """The page's lines from ``<h2>heading</h2>`` (exclusive) to the next ``<h2>`` (exclusive)."""
    lines = page.splitlines()
    marks = h2_lines(page)
    starts = [i for i, h in marks if h == heading]
    assert len(starts) == 1, (heading, starts)
    after = [i for i, _ in marks if i > starts[0]]
    end = after[0] if after else len(lines)
    return lines[starts[0] + 1 : end]


def md_sections(md: str) -> dict[str, list[str]]:
    """``report.md`` split at its ``## `` headings: heading -> the non-empty lines under it."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in md.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out.setdefault(current, [])
        elif current is not None and line.strip() and not line.startswith("> "):
            out[current].append(line)
    return out


def html_sections(html: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in html.splitlines():
        m = re.search(r"<h2>(.*?)</h2>", line)
        if m:
            current = html_mod.unescape(m.group(1))
            out.setdefault(current, [])
            rest = line[m.end():].strip()
            if rest:
                out[current].append(rest)
        elif current is not None and line.strip():
            out[current].append(line)
    return out


def paragraphs(lines: Sequence[str]) -> list[str]:
    return [html_mod.unescape(m.group(1)) for line in lines if (m := re.fullmatch(r"\s*<p>(.*?)</p>\s*", line))]


def md_tables(lines: Sequence[str], header: Sequence[str]) -> list[list[list[str]]]:
    """The rows of every markdown table whose header row is ``header``, in document order."""
    head = "| " + " | ".join(header) + " |"
    tables = []
    for at, line in enumerate(lines):
        if line != head:
            continue
        rows = []
        for row in lines[at + 2 :]:
            if not row.startswith("|"):
                break
            rows.append([c.strip() for c in row.strip().strip("|").split("|")])
        tables.append(rows)
    return tables


def html_tables(html: str) -> list[tuple[list[str], list[list[str]]]]:
    tables = []
    for table in re.findall(r"<table>(.*?)</table>", html, re.S):
        header = [html_mod.unescape(h) for h in re.findall(r"<th>(.*?)</th>", table, re.S)]
        rows = [[html_mod.unescape(c) for c in re.findall(r"<td>(.*?)</td>", tr, re.S)] for tr in re.findall(r"<tr>(.*?)</tr>", table, re.S)]
        tables.append((header, [r for r in rows if r]))
    return tables


def fmt_sig3(value: float) -> str:
    x = float(value)
    return "0" if x == 0 else (format(x, ".2e") if abs(x) < 1e-3 else format(x, ".3g"))


def fmt_p10(value: float) -> str:
    """A p-value as the command line prints it: three decimals, or one decimal in the mantissa
    below 0.001 (rule 10)."""
    x = float(value)
    return format(x, ".3f") if x >= 1e-3 else format(x, ".1e")


PRINTED_NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?%?(?![\w]|\.\d)")


def printed_value(token: str) -> tuple[float, float]:
    """A printed number and half a unit of its last printed digit."""
    text = token.replace(",", "").removesuffix("%")
    m = re.fullmatch(r"[-+]?\d+(?:\.(\d+))?(?:[eE]([-+]?\d+))?", text)
    assert m, token
    return float(text), 0.5 * 10.0 ** (int(m.group(2) or 0) - len(m.group(1) or ""))


def same_numbers(library: str, printed: str) -> bool:
    """The command line reprints the library's numbers under rule 10: the same
    numbers in the same order, each equal within the coarser of the two printed precisions."""
    a_tokens, p_tokens = PRINTED_NUMBER.findall(library), PRINTED_NUMBER.findall(printed)
    if len(a_tokens) != len(p_tokens):
        return False
    for a_token, p_token in zip(a_tokens, p_tokens, strict=True):
        (a, half_a), (b, half_b) = printed_value(a_token), printed_value(p_token)
        if abs(a - b) > max(half_a, half_b) + 1e-12:
            return False
    return True


def fmt_pp1(value: float) -> str:
    text = format(float(value) * 100, ".1f")
    return "0.0" if text == "-0.0" else text


def interval_text(lo: Any, hi: Any) -> str:
    if lo is None or hi is None or (isinstance(lo, float) and lo != lo) or (isinstance(hi, float) and hi != hi):
        return "censored"
    return f"[{fmt_pp1(lo)}, {fmt_pp1(hi)}]"


def honesty_as_a626cd3(honesty: str, n_compared: int) -> str:
    """PF4 (PF4.17, PF4.20): a panel's honesty with PF4's two rewordings put back as a626cd3 wrote
    them, each first asserted in PF4's form. No event here declares a kind, so the claim the bound
    guards counts rises ("N higher" where it read "N worse"); a panel with no unchanged condition
    counts its compared conditions instead of saying every cell moved."""
    lines = honesty.splitlines()
    if "can only detect" in lines[0]:
        assert re.search(r'"\d+ higher" is an honest claim', lines[0]) and not re.search(r'"\d+ worse"', lines[0]), lines[0]
        lines[0] = re.sub(r'"(\d+) higher" is an honest claim', r'"\1 worse" is an honest claim', lines[0])
    else:
        assert lines[0] != HONESTY_NONE_AT_A626CD3 and str(n_compared) in re.findall(r"\d+", lines[0]), lines[0]
        lines[0] = HONESTY_NONE_AT_A626CD3
    return "\n".join(lines)


def without_text(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: without_text(v) for k, v in value.items() if k != "text"}
    if isinstance(value, list):
        return [without_text(v) for v in value]
    return value


# ---------- helpers: ast (restated; never imported across test modules) ----------


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def resolve_region(module: ast.Module, qualified: str) -> ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef:
    node: ast.AST = module
    definition: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None = None
    for segment in qualified.split("."):
        matches = [c for c in ast.iter_child_nodes(node) if isinstance(c, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and c.name == segment]
        assert len(matches) == 1, (qualified, segment, len(matches))
        definition = matches[0]
        node = definition
    assert definition is not None
    return definition


def names_in(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def module_functions(module: ast.Module) -> dict[str, ast.AST]:
    return {n.name: n for n in module.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}


def closure(module: ast.Module, name: str) -> list[ast.AST]:
    functions = module_functions(module)
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


ARITHMETIC = (ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.MatMult)


def is_non_numeric(node: ast.AST) -> bool:
    return isinstance(node, ast.JoinedStr | ast.List | ast.ListComp | ast.Tuple) or (isinstance(node, ast.Constant) and isinstance(node.value, str))


def arithmetic_nodes(nodes: Sequence[ast.AST]) -> list[ast.AST]:
    out: list[ast.AST] = []
    for fn in nodes:
        for node in ast.walk(fn):
            if isinstance(node, ast.BinOp):
                if isinstance(node.op, ARITHMETIC) or (isinstance(node.op, ast.Add) and not (is_non_numeric(node.left) or is_non_numeric(node.right))):
                    out.append(node)
            elif isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add | ARITHMETIC):
                out.append(node)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and not isinstance(node.operand, ast.Constant):
                out.append(node)
    return out


def format_calls(module: ast.AST) -> list[int]:
    return [
        n.lineno for n in ast.walk(module)
        if isinstance(n, ast.Call) and ((isinstance(n.func, ast.Name) and n.func.id == "format") or (isinstance(n.func, ast.Attribute) and n.func.attr == "format"))
    ]


def operand_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Attribute):
        return {node.attr}
    if isinstance(node, ast.Name):
        return {node.id}
    return set()


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One store holding every pair this file mints through the public ``Store`` API:
    C18's seed-disjoint pair and its two variants, the partial-overlap pair, the
    salt-differing twin, a two-event pair whose intervals vary across events, an ``R == 0`` pair,
    and the small-alpha family."""
    root = tmp_path_factory.mktemp("p1-store")
    store = Store(root)
    base = cells_of(4, n=8, fails=lambda i: i)
    moved = cells_of(4, n=8, fails=lambda i: min(8, i + 3))
    # C18's pair: same salt, every matched row's seed differs (arm b's are offset by one).
    write_run(store, "c18-a", salt=SALT, cells=base)
    write_run(store, "c18-b", salt=SALT, cells=moved, seeds=lambda c, k: seed_of(c, k) + 1)
    # The same frames with the seeds made equal, and with exactly one matched row's seed differing.
    write_run(store, "c18-b-equal", salt=SALT, cells=moved)
    first = config_hash({"task": "t0", "temp": 0.0})
    write_run(store, "c18-b-one", salt=SALT, cells=moved, seeds=lambda c, k: seed_of(c, k) + (5 if config_hash(c) == first and k == 0 else 0))
    # Y6's twin: the equal-seed frames under another salt.
    write_run(store, "c18-b-twin", salt=OTHER_SALT, cells=moved)
    # The partial-overlap pair: cells t0..t2 in a, t1..t3 in b (dropped_a = dropped_b = 1); seeds equal
    # on the matched keys, and the unmatched cells sit at different positions with different seeds, so
    # a positional comparison over all rows disagrees while the keyed comparison does not (mutant 2).
    write_run(store, "over-a", salt=SALT, cells=cells_of(3, n=8, fails=lambda i: i, names=["t0", "t1", "t2"]))
    write_run(store, "over-b", salt=SALT, cells=cells_of(3, n=8, fails=lambda i: 3, names=["t1", "t2", "t3"]))
    # Two events whose intervals differ across events on the same cell (mutant 21): arm b raises
    # ``fail`` a lot and ``crash`` a little in every cell, by different amounts per cell.
    two_a = {(("task", f"t{i}"), ("temp", 0.0)): ["fail"] * 2 + ["crash"] * 2 + ["ok"] * 28 for i in range(6)}
    two_b = {(("task", f"t{i}"), ("temp", 0.0)): ["fail"] * (14 + i) + ["crash"] * (4 + i) + ["ok"] * (14 - 2 * i) for i in range(6)}
    write_run(store, "k2-a", salt=SALT, cells=two_a)
    write_run(store, "k2-b", salt=SALT, cells=two_b)
    # ``R == 0``: identical arms.
    write_run(store, "same-a", salt=SALT, cells=cells_of(4, n=8, fails=lambda i: 2))
    write_run(store, "same-b", salt=SALT, cells=cells_of(4, n=8, fails=lambda i: 2))
    # The small-alpha family: 1200 cells, one rejection, so ``alpha* = q x 1 / 1200 < 1e-4`` (Y12).
    axes = {"cell": "continuous"}
    alpha_a = {(("cell", float(i)),): (["ok"] * 32 if i == 0 else ["ok"] * 2) for i in range(1200)}
    alpha_b = {(("cell", float(i)),): (["fail"] * 32 if i == 0 else ["ok"] * 2) for i in range(1200)}
    write_run(store, "alpha-a", salt=SALT, cells=alpha_a, axis_types=axes)
    write_run(store, "alpha-b", salt=SALT, cells=alpha_b, axis_types=axes)
    return root


@pytest.fixture(scope="module")
def lattice_pair() -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    return read_pair(LATTICE_ROOT, LATTICE_A, LATTICE_B)


@pytest.fixture(scope="module")
def lattice_built() -> Built:
    """The lattice's ``tripped`` at the default knobs: the tree at 4000 permutations, grown once."""
    return build_pair("lattice", LATTICE_ROOT, LATTICE_A, LATTICE_B, events=(EVENT,), x=X, y=Y)


@pytest.fixture(scope="module")
def lattice_cli(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The lattice's ``tripped`` through every verb, the tree at 300 permutations so the CLI's trees are cheap:
    ``diff``, ``diff --format json``, ``diff --methods all``, ``report`` (files), ``check`` and
    ``serve --json``."""
    out_dir = tmp_path_factory.mktemp("p1-lattice-cli") / "report"
    base = ["--store", str(LATTICE_ROOT)]
    knobs = ["--permutations", "300", "--seed", "0"]
    # PF3: the lattice's runs share a salt, so the default is now the
    # paired test; every number this file pins on the CLI is the unpaired test's, named.
    fisher = ["--method", "fisher_bh"]
    results: dict[str, Any] = {}
    for name, argv in (
        ("diff", ["diff", LATTICE_A, LATTICE_B, "--event", EVENT, *fisher, *knobs]),
        # --json replaces --format json on diff.
        ("diff json", ["diff", LATTICE_A, LATTICE_B, "--event", EVENT, "--json", *fisher, *knobs]),
        ("diff methods all", ["diff", LATTICE_A, LATTICE_B, "--event", EVENT, "--methods", "all", *knobs]),
        ("report", ["report", LATTICE_A, LATTICE_B, "--event", EVENT, "--x", X, "--y", Y, "--out", str(out_dir), *fisher, *knobs]),
        # PF4 (PF4.20): the default --fail-on worse is refused on an event of unknown kind; --fail-on
        # higher is the same gate on the lattice's tripped (fail when the rate rose).
        ("check", ["check", LATTICE_A, LATTICE_B, "--event", EVENT, "--fail-on", "higher", *fisher]),
    ):
        code, out, err = quiet(lambda argv=argv: run_cli([*base, *argv]))
        assert code == 0, (name, code, err)
        results[name] = out
    code, out, err, calls = quiet(lambda: run_serve([*base, "serve", LATTICE_A, LATTICE_B, "--event", EVENT, "--x", X, "--y", Y, "--json", *fisher, *knobs]))
    assert code == 0 and calls == [], (code, err, calls)
    results["serve json"] = json.loads(out)
    results["report.md"] = (out_dir / "report.md").read_text(encoding="utf-8")
    results["receipt.html"] = (out_dir / "receipt.html").read_text(encoding="utf-8")
    return results


@pytest.fixture(scope="module")
def k2(synth_root: Path) -> Built:
    return build_pair("k2", synth_root, "k2-a", "k2-b", events=("fail", "crash"), x="task", y="temp", n_permutations=300, seed=0)


@pytest.fixture(scope="module")
def same(synth_root: Path) -> Built:
    return build_pair("same", synth_root, "same-a", "same-b", events=("fail",), x="task", y="temp", n_permutations=300, seed=0)


@pytest.fixture(scope="module")
def alpha(synth_root: Path) -> Built:
    return build_pair("alpha", synth_root, "alpha-a", "alpha-b", events=("fail",), x="cell", n_permutations=50, seed=0)


# ---------- Y1-Y3: the predicate, by hypothesis ----------


@dataclasses.dataclass(frozen=True)
class Draw:
    salt_equal: bool
    seed_a: bool
    seed_b: bool
    overlap: str
    one_differs: bool
    n: int

    def frames(self) -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
        cells_a = {"u": ["fail"] * 1 + ["ok"] * (self.n - 1), "v": ["ok"] * self.n}
        cells_b = {"u": ["fail"] * (self.n - 1) + ["ok"] * 1, "v": ["fail"] * 1 + ["ok"] * (self.n - 1)}
        start = {"full": 0, "partial": 1, "none": self.n}[self.overlap]
        u = config_hash({"task": "u"})

        def seeds_b(config: Mapping[str, Any], rep: int) -> int:
            return seed_of(config, rep) + (9 if self.one_differs and config_hash(config) == u and rep == start else 0)

        a = raw_frame("d-a", cells_a, seeds=seed_of if self.seed_a else None)
        b = raw_frame("d-b", cells_b, seeds=seeds_b if self.seed_b else None, replicate_start=start)
        return a, b, manifest("d-a", SALT), manifest("d-b", SALT if self.salt_equal else OTHER_SALT)

    @property
    def n_matched(self) -> int:
        return 2 * {"full": self.n, "partial": self.n - 1, "none": 0}[self.overlap]

    @property
    def expected(self) -> bool:
        return self.salt_equal and self.seed_a and self.seed_b and self.n_matched > 0 and not self.one_differs


draws = st.builds(
    Draw, salt_equal=st.booleans(), seed_a=st.booleans(), seed_b=st.booleans(),
    overlap=st.sampled_from(("full", "partial", "none")), one_differs=st.booleans(), n=st.integers(min_value=2, max_value=6),
)
HYPOTHESIS = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])


@given(draw=draws)
@HYPOTHESIS
def test_y1_seed_identity_match_is_the_salt_plus_the_stored_seed_on_every_matched_row_on_both_entry_points(draw: Draw) -> None:
    """The pairing predicate's four clauses, drawn over salt equality x seed column present (each arm) x
    overlap (none / partial / full, by replicate set) x seed agreement (all / one differs). The
    zero-overlap draws are the sole catch for mutant 3; the no-seed draws catch mutant 4; the
    ``diff()`` half catches mutant 20."""
    a, b, ma, mb = draw.frames()
    multi = quiet(lambda: multi_diff(a, b, events=["fail"], method="fisher_bh", manifest_a=ma, manifest_b=mb))
    assert multi.seed_identity_match is draw.expected, draw
    single = quiet(lambda: diff(censor(a, "fail"), censor(b, "fail"), event="fail", method="fisher_bh", manifest_a=ma, manifest_b=mb))
    assert single.seed_identity_match is draw.expected, draw


@given(draw=draws, method=st.sampled_from(METHODS))
@HYPOTHESIS
def test_y2_unpaired_analysis_is_seed_identity_and_the_method_is_not_a_paired_one_on_every_result(draw: Draw, method: str) -> None:
    """``unpaired_analysis == seed_identity_match and method not in _PAIRED_METHODS`` on every result
    either entry point returns; ``mcnemar_bh`` returns only when the predicate holds (Y3 has the
    refusals). Mutant 5."""
    a, b, ma, mb = draw.frames()
    if method in PAIRED_METHODS and not draw.expected:
        with pytest.raises(NotPairable):
            quiet(lambda: multi_diff(a, b, events=["fail"], method=method, manifest_a=ma, manifest_b=mb))  # type: ignore[arg-type]
        return
    for result in (
        quiet(lambda: multi_diff(a, b, events=["fail"], method=method, manifest_a=ma, manifest_b=mb)),  # type: ignore[arg-type]
        quiet(lambda: diff(censor(a, "fail"), censor(b, "fail"), event="fail", method=method, manifest_a=ma, manifest_b=mb)),  # type: ignore[arg-type]
    ):
        assert result.seed_identity_match is draw.expected, (draw, method)
        assert result.unpaired_analysis is (draw.expected and method not in PAIRED_METHODS), (draw, method)


def first_refusal(draw: Draw) -> str | None:
    """The refusal table, in order: the first clause the draw fails."""
    if not draw.salt_equal:
        return REFUSAL_SALT.format(a=SALT, b=OTHER_SALT)
    if not draw.seed_a:
        return REFUSAL_NO_SEED.format(frame="a")
    if not draw.seed_b:
        return REFUSAL_NO_SEED.format(frame="b")
    if draw.n_matched == 0:
        return REFUSAL_NO_MATCH
    if draw.one_differs:
        return REFUSAL_SEEDS_DIFFER.format(k=1, n=draw.n_matched)
    return None


@given(draw=draws)
@HYPOTHESIS
def test_y3_mcnemar_refuses_iff_the_predicate_is_false_with_the_first_failing_clauses_sentence(draw: Draw) -> None:
    """Each refusal is its own sentence, byte for byte: the salt-mismatch sentence is ``a626cd3``'s,
    the three seed-level ones are new, and the seeds-differ sentence carries both counts.
    Mutant 8."""
    a, b, ma, mb = draw.frames()
    expected = first_refusal(draw)
    if expected is None:
        assert quiet(lambda: multi_diff(a, b, events=["fail"], method="mcnemar_bh", manifest_a=ma, manifest_b=mb)).seed_identity_match is True
        return
    with pytest.raises(NotPairable) as info:
        quiet(lambda: multi_diff(a, b, events=["fail"], method="mcnemar_bh", manifest_a=ma, manifest_b=mb))
    assert str(info.value) == expected, (draw, str(info.value))


def test_y3_the_missing_manifest_sentence_is_unchanged_and_fires_before_any_frame_work(synth_root: Path) -> None:
    fa, fb, _, _ = read_pair(synth_root, "c18-a", "c18-b")
    with pytest.raises(NotPairable) as info:
        multi_diff(fa, fb, events=["fail"], method="mcnemar_bh")
    assert str(info.value) == REFUSAL_MANIFESTS
    with pytest.raises(NotPairable) as info:
        diff(censor(fa, "fail"), censor(fb, "fail"), event="fail", method="mcnemar_bh")
    assert str(info.value) == REFUSAL_MANIFESTS


# ---------- Y4, Y5: the warning and C18's pair ----------


def test_y4_the_warning_is_raised_once_per_diff_iff_unpaired_analysis_with_the_verbatim_message_at_the_callers_line(synth_root: Path) -> None:
    """Mutant 9. The message is the warning's one line with the method, the salt's ``repr`` and the
    matched-row count filled in; ``filename`` is this file (U11's clause, restated)."""
    fa, fb, ma, mb = read_pair(synth_root, "c18-a", "c18-b-equal")
    for method, entry in (("fisher_bh", "multi"), ("logrank_bh", "multi"), ("fisher_bh", "single")):
        if entry == "multi":
            records = caught(lambda m=method: multi_diff(fa, fb, events=["fail"], method=m, manifest_a=ma, manifest_b=mb))  # type: ignore[arg-type]
        else:
            records = caught(lambda m=method: diff(censor(fa, "fail"), censor(fb, "fail"), event="fail", method=m, manifest_a=ma, manifest_b=mb))  # type: ignore[arg-type]
        assert len(records) == 1, (method, entry, [str(r.message) for r in records])
        assert str(records[0].message) == WARNING.format(method=method, salt=SALT, n=32), str(records[0].message)
        assert records[0].filename == __file__, records[0].filename
    assert caught(lambda: multi_diff(fa, fb, events=["fail"], method="mcnemar_bh", manifest_a=ma, manifest_b=mb)) == []
    fa2, fb2, ma2, mb2 = read_pair(synth_root, "c18-a", "c18-b")
    assert caught(lambda: multi_diff(fa2, fb2, events=["fail"], method="fisher_bh", manifest_a=ma2, manifest_b=mb2)) == []


def test_y5_c18s_pair_seeds_disjoint_is_not_an_identity_the_same_frames_with_equal_seeds_are_and_partial_overlap_matches_on_the_matched_keys(synth_root: Path) -> None:
    """C18's pair, minted through ``Store``: sole catch for mutant 2 (seeds
    compared outside the matched keys) through the partial-overlap variant, whose unmatched cells
    sit at different positions with different seeds."""
    fa, fb, ma, mb = read_pair(synth_root, "c18-a", "c18-b")
    disjoint = stored_multi(synth_root, "c18-a", "c18-b")
    assert (disjoint.seed_identity_match, disjoint.unpaired_analysis) == (False, False)
    assert caught(lambda: multi_diff(fa, fb, events=["fail"], method="fisher_bh", manifest_a=ma, manifest_b=mb)) == []
    with pytest.raises(NotPairable) as info:
        multi_diff(fa, fb, events=["fail"], method="mcnemar_bh", manifest_a=ma, manifest_b=mb)
    assert str(info.value) == REFUSAL_SEEDS_DIFFER.format(k=32, n=32)
    equal = stored_multi(synth_root, "c18-a", "c18-b-equal")
    assert (equal.seed_identity_match, equal.unpaired_analysis) == (True, True)
    fa, fb, ma, mb = read_pair(synth_root, "c18-a", "c18-b-equal")
    assert len(caught(lambda: multi_diff(fa, fb, events=["fail"], method="fisher_bh", manifest_a=ma, manifest_b=mb))) == 1
    paired = multi_diff(fa, fb, events=["fail"], method="mcnemar_bh", manifest_a=ma, manifest_b=mb)
    assert (paired.seed_identity_match, paired.unpaired_analysis, paired.method) == (True, False, "mcnemar_bh")
    one = stored_multi(synth_root, "c18-a", "c18-b-one")
    assert (one.seed_identity_match, one.unpaired_analysis) == (False, False)
    fa, fb, ma, mb = read_pair(synth_root, "c18-a", "c18-b-one")
    with pytest.raises(NotPairable) as info:
        multi_diff(fa, fb, events=["fail"], method="mcnemar_bh", manifest_a=ma, manifest_b=mb)
    assert str(info.value) == REFUSAL_SEEDS_DIFFER.format(k=1, n=32)
    over = stored_multi(synth_root, "over-a", "over-b")
    assert (over.seed_identity_match, over.unpaired_analysis, over.dropped_a, over.dropped_b) == (True, True, 1, 1)
    fa, fb, _, _ = read_pair(synth_root, "over-a", "over-b")
    assert list(fa["seed"]) != list(fb["seed"]) and len(fa) == len(fb)


# ---------- Y6: the statistic never follows provenance ----------


def test_y6_the_statistic_never_follows_provenance_on_a_pair_and_its_salt_differing_twin(synth_root: Path) -> None:
    """U8, C12 and O6 restated over the renamed field; green before and after by design."""
    for method in ("fisher_bh", "logrank_bh"):
        one = stored_multi(synth_root, "c18-a", "c18-b-equal", method=method)
        twin = stored_multi(synth_root, "c18-a", "c18-b-twin", method=method)
        assert one.seed_identity_match is True and twin.seed_identity_match is False
        for event in one.events:
            pd.testing.assert_frame_equal(one.by_event[event].cells, twin.by_event[event].cells)
        if one.intervals is None:
            assert twin.intervals is None
        else:
            pd.testing.assert_frame_equal(one.intervals, twin.intervals)
        assert (one.interval_level, one.alpha_star) == (twin.interval_level, twin.alpha_star)
        fa, fb, _, _ = read_pair(synth_root, "c18-a", "c18-b-equal")
        root_one = omnibus(fa, fb, one, n_permutations=50, seed=1).to_json()
        root_twin = omnibus(fa, fb, twin, n_permutations=50, seed=1).to_json()
        assert root_one == root_twin


# ---------- Y7-Y9: the name is gone, the headline states the request, the provenance dict ----------


def test_y7_no_field_is_named_paired_and_the_key_set_literals_carry_the_two_keys_in_its_slot(lattice_pair: Any, lattice_cli: dict[str, Any]) -> None:
    for cls in (DiffResult, MultiDiffResult):
        names = [f.name for f in dataclasses.fields(cls)]
        assert "paired" not in names and names.index("unpaired_analysis") == names.index("seed_identity_match") + 1 == names.index("method") + 2, names
    assert diff_mod.SUMMARY_FIELDS == SUMMARY_FIELDS
    assert diff_mod._MULTI_SUMMARY_FIELDS == MULTI_SUMMARY_FIELDS
    a, b, ma, mb = lattice_pair
    multi = quiet(lambda: multi_diff(a, b, events=[EVENT], method="fisher_bh", manifest_a=ma, manifest_b=mb))
    payload = multi.to_json()
    assert [k for k in payload if k in MULTI_SUMMARY_FIELDS] == list(MULTI_SUMMARY_FIELDS) and "paired" not in payload
    single = quiet(lambda: diff(censor(a, EVENT), censor(b, EVENT), event=EVENT, method="fisher_bh", manifest_a=ma, manifest_b=mb))
    single_payload = single.to_json()
    assert [k for k in single_payload if k in SUMMARY_FIELDS] == list(SUMMARY_FIELDS) and "paired" not in single_payload
    parameter_line = next(line for line in multi.to_markdown().splitlines() if line.startswith("method="))
    assert LATTICE_PARAMETER_LINE_PREFIX.endswith(f", n_tests={lattice.CELLS}, ")
    assert parameter_line.startswith(LATTICE_PARAMETER_LINE_PREFIX) and "paired=" not in parameter_line, parameter_line
    assert "seed_identity_match=True" in single.to_markdown() and "unpaired_analysis=True" in single.to_markdown() and "paired=" not in single.to_markdown()
    cli_json = json.loads(lattice_cli["diff json"])
    assert cli_json["seed_identity_match"] is True and cli_json["unpaired_analysis"] is True and "paired" not in cli_json


def test_y8_the_headline_states_the_requested_methods_pairing_on_every_surface_and_never_reads_the_identity(synth_root: Path, lattice_built: Built, lattice_cli: dict[str, Any]) -> None:
    """Mutant 6 is the defect restored; the AST clause is its sole catch on any fixture where the
    identity and the request coincide."""
    fa, fb, ma, mb = read_pair(synth_root, "c18-a", "c18-b-equal")
    for method in METHODS:
        multi = quiet(lambda m=method: multi_diff(fa, fb, events=["fail"], method=m, manifest_a=ma, manifest_b=mb))  # type: ignore[arg-type]
        token = "paired" if method in PAIRED_METHODS else "unpaired"
        assert multi.headline().endswith(f", {token})"), (method, multi.headline())
        single = quiet(lambda m=method: diff(censor(fa, "fail"), censor(fb, "fail"), event="fail", method=m, manifest_a=ma, manifest_b=mb))  # type: ignore[arg-type]
        assert build_report(single, ReportSpec(title="p1", x_axis="task", y_axis="temp")).headline.endswith(f"({method}, BH q<0.05, {token}).")
        rows = build_multi_report(multi, ReportSpec(title="p1", x_axis="task", y_axis="temp", comparison={method: single}))._method_rows
        assert rows and all(row[1] == token for row in rows), (method, rows)
    table = [line for line in lattice_cli["diff methods all"].splitlines() if line.startswith("| ") and EVENT in line]
    assert table and {tuple(c.strip() for c in line.strip("|").split("|"))[:3] for line in table} == {
        ("fisher_bh", EVENT, "unpaired"), ("mcnemar_bh", EVENT, "paired"), ("logrank_bh", EVENT, "unpaired")
    }, table
    assert "| method | event | pairing |" in lattice_cli["diff methods all"]
    # the reference: scipy's Fisher test per condition and one BH family over the design's conditions
    assert lattice.directions(lattice.fisher(EVENT)) == (LATTICE_LOWER, LATTICE_HIGHER) == (22, 0) and lattice.CELLS == LATTICE_TESTS == 72
    assert LATTICE_HEADLINE.splitlines()[0] == f"{EVENT}: {LATTICE_LOWER} lower, {LATTICE_HIGHER} higher" and f"over {LATTICE_TESTS} tests" in LATTICE_HEADLINE
    assert LATTICE_SINGLE_HEADLINE.startswith(f"{LATTICE_LOWER} of {LATTICE_TESTS} cells safer, {LATTICE_HIGHER} worse ")
    assert lattice_built.multi.headline() == LATTICE_HEADLINE
    # PF2: diff's verdict block comes first; the report after its blank line
    # starts with the headline as before.
    assert lattice_cli["diff"].partition("\n\n")[2].startswith(LATTICE_HEADLINE.splitlines()[0]) and LATTICE_HEADLINE in lattice_cli["diff"]
    # check's verdict is now its first stdout line, passed or failed.
    assert lattice_cli["check"].startswith("passed  ") and LATTICE_HEADLINE in lattice_cli["check"], lattice_cli["check"]
    assert LATTICE_HEADLINE in lattice_cli["report"] and LATTICE_HEADLINE in lattice_cli["report.md"] and LATTICE_HEADLINE in lattice_built.md
    assert html_mod.escape(LATTICE_HEADLINE.splitlines()[1]) in lattice_cli["receipt.html"]
    assert lattice_cli["serve json"]["headline"] == LATTICE_HEADLINE == lattice_built.structure["headline"]
    a, b, ma, mb = read_pair(LATTICE_ROOT, LATTICE_A, LATTICE_B)
    single = quiet(lambda: diff(censor(a, EVENT), censor(b, EVENT), event=EVENT, method="fisher_bh", manifest_a=ma, manifest_b=mb))
    assert build_report(single, ReportSpec(title="p1", x_axis=X, y_axis=Y)).headline == LATTICE_SINGLE_HEADLINE
    forbidden = {"seed_identity_match", "unpaired_analysis"}
    diff_ast, report_ast, cli_ast = parsed(DIFF_SOURCE), parsed(REPORT_SOURCE), parsed(CLI_SOURCE)
    for module, qualified in ((diff_ast, "MultiDiffResult.headline"), (report_ast, "_single_headline"), (report_ast, "_multi_method_rows"), (report_ast, "_method_row"), (cli_ast, "_method_table")):
        assert not (names_in(resolve_region(module, qualified)) & forbidden), qualified


def test_y9_the_provenance_dict_carries_the_two_keys_in_paireds_slot_on_both_builders_and_every_rendering(lattice_built: Built, lattice_cli: dict[str, Any], synth_root: Path) -> None:
    """Mutant 7."""
    provenance = lattice_built.report.provenance
    assert tuple(provenance) == MULTI_PROVENANCE_KEYS, tuple(provenance)
    assert provenance["seed_identity_match"] is True and provenance["unpaired_analysis"] is True
    assert lattice_built.structure["diff"] == provenance == lattice_cli["serve json"]["diff"]
    for text in (lattice_built.md, lattice_cli["report.md"]):
        lines = text.splitlines()
        at = lines.index("- seed identity match: true")
        assert lines[at + 1] == "- unpaired analysis: true" and lines[at - 1] == "- method: fisher_bh", lines[at - 1 : at + 2]
        assert "- paired:" not in text
    for html in (lattice_built.html, lattice_cli["receipt.html"]):
        assert "<li>seed identity match: true</li><li>unpaired analysis: true</li>" in html and "<li>paired:" not in html
    fa, fb, ma, mb = read_pair(synth_root, "c18-a", "c18-b-equal")
    single = quiet(lambda: diff(censor(fa, "fail"), censor(fb, "fail"), event="fail", method="fisher_bh", manifest_a=ma, manifest_b=mb))
    keys = list(build_report(single, ReportSpec(title="p1", x_axis="task", y_axis="temp"), manifests=(ma, mb)).provenance)
    assert "paired" not in keys and keys[keys.index("method") + 1 : keys.index("method") + 3] == ["seed_identity_match", "unpaired_analysis"], keys


# ---------- Y10-Y15: intervals ----------


def test_y10_the_payload_root_is_thirteen_keys_and_intervals_is_m6s_fields_lines_and_rows_in_m6s_order(lattice_built: Built, lattice_cli: dict[str, Any], k2: Built, same: Built) -> None:
    """Mutant 18."""
    # serve --json adds verdict and sentence after schema.
    # PF3: serve --json also adds method and method_chosen right after sentence.
    assert tuple(k for k in lattice_cli["serve json"] if k not in ("verdict", "sentence")) == ("schema", "method", "method_chosen") + TOP_LEVEL_KEYS[1:]
    for built in (lattice_built, k2, same):
        structure, multi = built.structure, built.multi
        assert tuple(structure) == TOP_LEVEL_KEYS, (built.name, tuple(structure))
        intervals = structure["intervals"]
        assert tuple(intervals) == INTERVALS_KEYS, (built.name, tuple(intervals))
        assert intervals["family"] == "flat"
        assert (intervals["q"], intervals["n_tests"], intervals["n_rejected"]) == (multi.q, multi.n_tests, multi.n_rejected)
        assert (intervals["n_interval_only"], intervals["n_verdict_only"]) == (multi.n_interval_only, multi.n_verdict_only)
        assert (intervals["level"], intervals["alpha_star"]) == (multi.interval_level, multi.alpha_star)
        assert intervals["lines"] == list(built.report.interval_lines)
        if multi.intervals is None:
            assert built.name == "same" and intervals["level"] is None and intervals["alpha_star"] is None and intervals["rows"] == []
            continue
        assert intervals["level"] is not None and intervals["alpha_star"] is not None
        records = multi.intervals.to_dict(orient="records")
        assert len(intervals["rows"]) == len(records)
        for row, record in zip(intervals["rows"], records, strict=True):
            assert tuple(row) == INTERVAL_ROW_KEYS, tuple(row)
            assert (row["event"], row["config_hash"], row["basis"]) == (str(record["event"]), str(record["config_hash"]), str(record["basis"]))
            for end in ("ci_lo", "ci_hi"):
                if record[end] is None or record[end] != record[end]:
                    assert row[end] is None and end not in row["text"], (built.name, row)
                else:
                    assert row[end] == float(record[end]) and row["text"][end] == fmt_pp1(record[end]), (built.name, row)
    assert json.loads(json.dumps(lattice_built.structure, allow_nan=False))["intervals"] == lattice_cli["serve json"]["intervals"]


#: PF4 re-freeze: the closed list of reasons a direction has no limit (PF4.27).
LIMIT_NOTES = {"no room", "none detectable", "cannot be flagged", "no matched pairs"}
S24_INTERVAL_LINE = re.compile(
    r"^intervals: ([0-9.]+)% \(alpha\* = ([0-9.eE+-]+) = q x (\d+) / (\d+) over the flat BH family\), basis (\w+)$"
)


def assert_zero_r_interval_lines(built: Built) -> None:
    """PF4.42 on a pair where nothing was flagged: the interval lines are printed at
    the simultaneous level 1 - q / M, ``alpha*`` is q / M, the arithmetic the line prints is true
    (q times max(R, 1) over M), and the two disagreement counts are the result's."""
    multi = built.multi
    lines = list(built.report.interval_lines)
    assert multi.n_rejected == 0 and NO_INTERVAL_LINE not in lines, (built.name, lines)
    match = S24_INTERVAL_LINE.match(lines[0])
    assert match, lines
    level, alpha_star, k, m, _ = match.groups()
    assert abs(float(level) / 100 - (1 - multi.q / multi.n_tests)) <= 5e-7, level
    assert abs(float(alpha_star) - multi.q / multi.n_tests) <= 1e-9, alpha_star
    assert int(m) == multi.n_tests and int(k) == max(multi.n_rejected, 1), lines[0]
    assert lines[1:] == [
        f"interval excludes zero, verdict unchanged: {multi.n_interval_only} cells",
        f"verdict significant, interval covers zero: {multi.n_verdict_only} cells",
    ], lines


def _ref_cell_limit(row: Any) -> tuple[float | None, float | None, float | None]:
    """A condition's limit under Fisher at its row's level, from the stats file's references: the
    larger of the two ways, or the one way with room, else None (PF4.22, PF4.27); then each way's."""
    from test_pf4_stats import _ref_fisher_limits

    rise, fall = _ref_fisher_limits(int(row["events_a"]), int(row["n_a"]), int(row["n_b"]), float(row["mde_level"]))
    if rise is not None and fall is not None:
        return max(rise, fall), rise, fall
    if rise is not None and row["events_a"] == 0:
        return rise, rise, fall
    if fall is not None and row["events_a"] == row["n_a"]:
        return fall, rise, fall
    return None, rise, fall


def assert_honesty_facts(built: Built, panel: Mapping[str, Any]) -> None:
    """A panel's honesty, by its facts (PF4.22, PF4.27): no number for a null limit; the worst-powered
    unchanged condition, its limit in points and the way it goes, and the count of rises the bound
    guards; or, when no unchanged condition has a limit, one of them named with its reason; then the
    worst-powered condition overall, every number from the references."""
    assert built.multi.method == "fisher_bh", built.multi.method
    ev = built.multi.by_event[panel["event"]]
    records = ev.cells.to_dict(orient="records")
    for row in records:
        assert abs(row["mde_level"] - built.multi.q / built.multi.n_tests) <= 1e-15, (built.name, row["mde_level"])
    limits = {row["config_hash"]: _ref_cell_limit(row) for row in records}
    texts = {c["config_hash"]: ", ".join(f"{k}={v}" for k, v in c["config_text"].items()) for c in panel["cells"]}
    honesty = panel["honesty"]
    first, second = honesty.splitlines()
    assert not re.search(r"\bnan", honesty, re.IGNORECASE), (built.name, honesty)
    unchanged = [row for row in records if row["direction"] == "unchanged"]
    numbers = {row["config_hash"]: limits[row["config_hash"]][0] for row in unchanged if limits[row["config_hash"]][0] is not None}
    if not unchanged:
        assert honesty_as_a626cd3(first, panel["n_present"]) == HONESTY_NONE_AT_A626CD3, (built.name, first)
    elif numbers:
        worst = max(numbers.values())
        found = re.fullmatch(r'Worst-powered unchanged cell \((.*), n=(\d+)/(\d+)\) can only detect a (\d+)pp (rise|fall)\. '
                             r'"(\d+) higher" is an honest claim only above that\.', first)
        assert found, (built.name, first)
        named = [h for h, text in texts.items() if text == found.group(1) and h in numbers]
        assert named and all(abs(numbers[h] - worst) <= 1e-12 for h in named), (built.name, first, worst)
        _, rise, _ = limits[named[0]]
        way = "rise" if rise is not None and abs(rise - worst) <= 1e-12 else "fall"
        assert (int(found.group(4)), found.group(5), int(found.group(6))) == (round(100 * worst), way, ev.n_higher), (built.name, first, worst, way)
    else:
        found = re.fullmatch(r"Least sensitive unchanged condition \((.*), n=(\d+)/(\d+)\) has no limit: (.+)\.", first)
        assert found and found.group(4) in LIMIT_NOTES, (built.name, first)
        assert any(texts.get(row["config_hash"]) == found.group(1) for row in unchanged), (built.name, first)
    overall = {h: v for h, (v, _, _) in limits.items() if v is not None}
    if overall:
        top = max(overall.values())
        found = re.fullmatch(r"Worst-powered cell overall: (\d+)pp \((.*)\)\.", second)
        assert found and int(found.group(1)) == round(100 * top), (built.name, second, top)
        assert any(texts.get(h) == found.group(2) and abs(v - top) <= 1e-12 for h, v in overall.items()), (built.name, second)
    else:
        assert not re.search(r"\d+pp", second), (built.name, second)


def test_y11_one_formatter_the_same_strings_on_every_surface_and_diffs_block_is_byte_identical(lattice_built: Built, lattice_cli: dict[str, Any], same: Built, synth_root: Path) -> None:
    # PF4 re-freeze (PF4.42): intervals always, so the R == 0 pair prints the interval
    # lines too, at the simultaneous level 1 - q / M; their facts are checked by
    # assert_zero_r_interval_lines and the one-formatter property over every surface as before.
    assert_zero_r_interval_lines(same)
    # the lattice's first line from the reference: R conditions flagged by the flat BH family over M
    lower, higher = lattice.directions(lattice.fisher(EVENT))
    r, m = lower + higher, lattice.CELLS
    assert (r, m) == (22, 72) and LATTICE_INTERVAL_LINES[0] == (
        f"intervals: {100 * (1 - 0.05 * r / m):.4f}% (alpha* = {0.05 * r / m:g} = q x {r} / {m} over the flat BH family), basis score_rd"
    )
    for built, expected in ((lattice_built, list(LATTICE_INTERVAL_LINES)), (same, list(same.report.interval_lines))):
        assert list(built.report.interval_lines) == expected == built.structure["intervals"]["lines"], built.name
        assert md_sections(built.md)["Intervals"] == expected, built.name
        assert paragraphs(html_sections(built.html)["Intervals"]) == expected, built.name
        honesty = paragraphs(region_lines(built.page, "Honesty"))
        assert honesty[-2].split("<br>") == expected, (built.name, honesty[-2])
    # diff prints the same block with its numbers under rule 10: the first line
    # unindented after a blank line, the rest indented, each carrying the library line's numbers.
    diff_lines = lattice_cli["diff"].splitlines()
    at = next(i for i, line in enumerate(diff_lines) if line.startswith("intervals: "))
    block = diff_lines[at : at + len(LATTICE_INTERVAL_LINES)]
    assert diff_lines[at - 1] == "" and all(line.startswith("  ") for line in block[1:]), lattice_cli["diff"]
    assert all(same_numbers(lib, line) for lib, line in zip(LATTICE_INTERVAL_LINES, block, strict=True)), block
    code, out, err = quiet(lambda: run_cli(["--store", str(synth_root), "diff", "same-a", "same-b", "--event", "fail", "--permutations", "50"]))
    assert code == 0, err
    # PF4 re-freeze (PF4.42): no no-interval line; the R == 0 pair's block is printed like the lattice's,
    # each line carrying the library line's numbers.
    assert NO_INTERVAL_LINE not in out, out
    same_lines = list(same.report.interval_lines)
    lines = out.splitlines()
    at = next(i for i, line in enumerate(lines) if line.startswith("intervals: "))
    block = lines[at : at + len(same_lines)]
    assert lines[at - 1] == "" and all(line.startswith("  ") for line in block[1:]), out
    assert all(same_numbers(lib, line) for lib, line in zip(same_lines, block, strict=True)), block


def test_y12_the_family_is_named_no_renderer_does_arithmetic_on_the_interval_fields_and_a_small_alpha_prints_in_g_form(lattice_built: Built, alpha: Built) -> None:
    """Mutants 12, 13, 14; 13 has one catch, the small-alpha family."""
    for built in (lattice_built, alpha):
        first = built.report.interval_lines[0]
        assert FAMILY_TOKEN in first, (built.name, first)
        assert FAMILY_TOKEN in md_sections(built.md)["Intervals"][0] and FAMILY_TOKEN in paragraphs(html_sections(built.html)["Intervals"])[0]
        assert FAMILY_TOKEN in paragraphs(region_lines(built.page, "Honesty"))[-2]
    fields = {"interval_level", "alpha_star", "n_rejected", "n_tests"}
    for source in (REPORT_SOURCE, CLI_SOURCE, VIEWER_SOURCE):
        module = parsed(source)
        for fn in module_functions(module).values():
            for node in ast.walk(fn):
                if isinstance(node, ast.BinOp) and ((operand_names(node.left) | operand_names(node.right)) & fields):
                    raise AssertionError((source.name, getattr(fn, "name", "?"), node.lineno))
    viewer_source = VIEWER_SOURCE.read_text(encoding="utf-8")
    assert format_calls(parsed(VIEWER_SOURCE)) == [] and not FLOAT_SPEC_RE.search(viewer_source)
    assert alpha.multi.n_rejected == 1 and alpha.multi.n_tests == 1200 and alpha.multi.alpha_star is not None and alpha.multi.alpha_star < 1e-4
    first = alpha.report.interval_lines[0]
    assert f"alpha* = {alpha.multi.alpha_star:g} = q x 1 / 1200" in first and "0.0000" not in first, first
    assert "e-05" in first, first


def test_y13_adr_060s_placement_by_position_on_every_surface_and_the_h2_sequence_is_unchanged(lattice_built: Built, k2: Built, same: Built) -> None:
    """Mutants 10, 11."""
    for built in (lattice_built, k2, same):
        page, panels = built.page, built.structure["panels"]
        assert [h for _, h in h2_lines(page)] == list(H2_SEQUENCE), (built.name, [h for _, h in h2_lines(page)])
        honesty = region_lines(page, "Honesty")
        assert "outer-nodes" in honesty[-1] and honesty[-2].startswith("<p>") and honesty[-3].startswith("<p>") and honesty[-4] == f"<h3>{html_mod.escape(panels[-1]['event'])}</h3>", (built.name, honesty[-4:])
        assert html_mod.escape(built.report.interval_lines[0]) in honesty[-2]
        assert len(honesty) == 2 * len(panels) + 2, (built.name, len(honesty))
        for heading in ("Cells", "Bound"):
            body = "\n".join(md_sections(built.md).get(heading, []))
            assert "interval" not in body and "alpha*" not in body and not INTERVAL_TOKEN_RE.search(body), (built.name, heading)
            assert "interval" not in "\n".join(html_sections(built.html).get(heading, [])).lower()
        for line in region_lines(page, "Cells") + [honesty[-1]]:
            assert "interval" not in line.lower() and "alpha*" not in line and not INTERVAL_TOKEN_RE.search(line), (built.name, line[:100])
        md_lines = [line for line in built.md.splitlines() if line.strip()]
        at = md_lines.index("## Intervals")
        assert md_lines[at - 1] == panels[-1]["honesty"].splitlines()[-1], (built.name, md_lines[at - 1])
        after = md_lines[at + 1 + len(built.report.interval_lines)]
        # PF4 (PF4.3): the two-run report now prints the per-arm shares, as their own section after
        # the intervals; the intervals block still ends where it did.
        assert after in ("## Methods", "## Shares") or after.startswith("> "), (built.name, after)
        html_lines = [line for line in built.html.splitlines() if line.strip()]
        at = html_lines.index("<h2>Intervals</h2>")
        assert html_lines[at - 1] == f"<p>{'<br>'.join(html_mod.escape(hl) for hl in panels[-1]['honesty'].splitlines())}</p>", (built.name, html_lines[at - 1])
        after = html_lines[at + 1 + len(built.report.interval_lines)]
        # PF4 (PF4.3): as in report.md, the shares section may follow the intervals block.
        assert after in ("<h2>Methods</h2>", "<h2>Shares</h2>") or after.startswith("<blockquote>"), (built.name, after)


def test_y14_the_worst_cells_column_is_the_interval_per_event_and_cell_on_every_surface_and_absent_when_r_is_zero(lattice_built: Built, k2: Built, same: Built, lattice_pair: Any) -> None:
    """The two-event pair is the sole catch for mutant 21: its endpoints differ across events on the
    same cell, so a join on ``config_hash`` alone puts one event's interval on the other's row."""
    # PF4 re-freeze (PF4.42): the R == 0 pair carries the interval column too, so it joins the loop.
    for built in (lattice_built, k2, same):
        by_key = {(str(r["event"]), str(r["config_hash"])): r for r in built.multi.intervals.to_dict(orient="records")}
        tables = html_tables(built.html)
        for index, panel in enumerate(built.structure["panels"]):
            header, rows = panel["worst_header"], panel["worst_rows"]
            assert header[-1] == INTERVAL_COLUMN and header[-2] == "MDE", (built.name, header)
            assert len(panel["worst_hashes"]) == len(rows)
            for row, hash_ in zip(rows, panel["worst_hashes"], strict=True):
                record = by_key[(panel["event"], hash_)]
                assert row[-1] == interval_text(record["ci_lo"], record["ci_hi"]), (built.name, panel["event"], row[-1])
                assert row[-1] == "censored" or INTERVAL_TOKEN_RE.fullmatch(row[-1]), row[-1]
            assert md_tables(built.md.splitlines(), header)[index] == rows, (built.name, panel["event"])
            assert (header, rows) in tables, (built.name, panel["event"])
            assert (header, rows) in html_tables(built.page), (built.name, panel["event"])
        two_events = {k[0] for k in by_key}
        if built is k2:
            assert len(two_events) == 2
            cells = {k[1] for k in by_key}
            assert all(interval_text(by_key[("fail", c)]["ci_lo"], by_key[("fail", c)]["ci_hi"]) != interval_text(by_key[("crash", c)]["ci_lo"], by_key[("crash", c)]["ci_hi"]) for c in cells)
    # PF4 re-freeze (PF4.42): no surface drops the column or prints the no-interval line on R == 0.
    for panel in same.structure["panels"]:
        assert panel["worst_header"][-1] == INTERVAL_COLUMN and all(len(row) == len(panel["worst_header"]) for row in panel["worst_rows"])
    assert same.structure["intervals"]["lines"] != [NO_INTERVAL_LINE]
    assert INTERVAL_COLUMN in same.md and INTERVAL_COLUMN in same.html and INTERVAL_COLUMN in same.page
    a, b, ma, mb = lattice_pair
    single = quiet(lambda: diff(censor(a, EVENT), censor(b, EVENT), event=EVENT, method="fisher_bh", manifest_a=ma, manifest_b=mb))
    single_report = build_report(single, ReportSpec(title="p1", x_axis=X, y_axis=Y))
    assert INTERVAL_COLUMN not in single_report.to_markdown() and INTERVAL_COLUMN not in single_report.to_html()


def test_y15_render_html_refuses_a_viewpair_4_structure_without_intervals_before_rendering_and_the_tree_refusal_still_fires(lattice_built: Built) -> None:
    """Sole catch for mutant 17."""
    structure = json.loads(json.dumps(lattice_built.structure, allow_nan=False))
    assert structure["schema"] == SCHEMA
    stale = {k: v for k, v in structure.items() if k != "intervals"}
    with pytest.raises(ViewerError) as info:
        render_html(stale)
    assert str(info.value) == NO_INTERVALS_REFUSAL
    treeless = {k: v for k, v in structure.items() if k != "tree"}
    with pytest.raises(ViewerError) as info:
        render_html(treeless)
    assert str(info.value) == NO_TREE_REFUSAL
    assert isinstance(render_html(structure), str)


# ---------- Y16-Y18: the floor ----------


@given(n_permutations=st.integers(min_value=1, max_value=50), seed=st.integers(min_value=0, max_value=10**6))
@HYPOTHESIS
def test_y16_p_floor_is_one_over_b_plus_one_sits_after_n_permutations_and_bounds_every_permutation_p(synth_root: Path, n_permutations: int, seed: int) -> None:
    fa, fb, _, _ = read_pair(synth_root, "c18-a", "c18-b-equal")
    multi = stored_multi(synth_root, "c18-a", "c18-b-equal")
    root = omnibus(fa, fb, multi, n_permutations=n_permutations, seed=seed)
    assert root.p_floor == 1 / (n_permutations + 1)
    payload = root.to_json()
    keys = list(payload)
    assert keys[keys.index("n_permutations") + 1] == "p_floor" and payload["p_floor"] == root.p_floor
    for p in (root.p_omnibus, *root.p_location.values(), *root.p_dispersion.values()):
        assert p >= root.p_floor, (p, root.p_floor)


def test_y16_on_the_lattice_at_the_default_b_p_omnibus_equals_p_floor_exactly(lattice_built: Built) -> None:
    """Sole catch for mutant 15 (``1 / B``): ``>=`` alone passes it."""
    root = lattice_built.tree.root
    assert root.n_permutations == DEFAULT_PERMUTATIONS
    assert root.p_floor == 1 / (DEFAULT_PERMUTATIONS + 1) == root.p_omnibus
    fields = [f.name for f in dataclasses.fields(type(root))]
    assert fields[fields.index("n_permutations") + 1] == "p_floor"
    fault = lattice_built.tree.fault_lines
    assert fault.tested
    for group in fault.groups:
        for p in (group.p_location, group.p_dispersion, group.p_group):
            if isinstance(p, Mapping):
                assert all(v >= root.p_floor for v in p.values()), (group.label, p)
            elif p is not None:
                assert p >= root.p_floor, (group.label, p)


def test_y17_the_floor_line_follows_the_method_line_and_the_group_floor_line_follows_the_null_line_iff_tested_and_check_prints_none(lattice_built: Built, lattice_cli: dict[str, Any], same: Built) -> None:
    """Mutant 16, and ``check`` printing no permutation p: no ``p =``, no ``p floor`` and no
    ``not a measurement``."""
    root_lattice = lattice_built.tree.root
    cli_root = lattice_cli["serve json"]["tree"]["root"]
    assert cli_root["n_permutations"] == 300
    diff_lines = lattice_cli["diff"].splitlines()
    at = next(i for i, line in enumerate(diff_lines) if line.startswith("  min-p of location and dispersion; 300 within-cell permutations"))
    assert diff_lines[at + 1] == CLI_FLOOR_LINE.format(p_floor=fmt_p10(cli_root["p_floor"]), n_permutations=300), diff_lines[at + 1]
    null = next(i for i, line in enumerate(diff_lines) if "tested by BH across" in line)
    assert diff_lines[null + 1] == CLI_GROUP_FLOOR_LINE.format(p_floor=fmt_p10(cli_root["p_floor"]), n_permutations=300), diff_lines[null + 1]
    # 1/301 printed under rule 10.
    assert diff_lines[at + 1].startswith(f"  p floor {fmt_p10(1 / 301)}:") and diff_lines[null + 1].startswith(f"  group p floor {fmt_p10(1 / 301)}:")
    for built, root in ((lattice_built, root_lattice.to_json()),):
        floor = M7_FLOOR_LINE.format(p_floor=fmt_sig3(root["p_floor"]), n_permutations=root["n_permutations"])
        group_floor = M7_GROUP_FLOOR_LINE.format(p_floor=fmt_sig3(root["p_floor"]), n_permutations=root["n_permutations"])
        assert floor.startswith("p floor 2.50e-04: the smallest p 4000 permutations")
        omnibus_md = md_sections(built.md)["Omnibus"]
        assert omnibus_md[2] == floor and omnibus_md[1].startswith("min-p of location and dispersion; 4000 within-cell permutations"), omnibus_md[:3]
        fault_md = md_sections(built.md)["Fault lines"]
        null_at = next(i for i, line in enumerate(fault_md) if "tested by BH across" in line)
        assert fault_md[null_at + 1] == group_floor, fault_md[null_at : null_at + 2]
        omnibus_html = paragraphs(html_sections(built.html)["Omnibus"])
        assert omnibus_html[2] == floor and omnibus_html[1].startswith("min-p of location"), omnibus_html[:3]
        fault_html = paragraphs(html_sections(built.html)["Fault lines"])
        null_at = next(i for i, line in enumerate(fault_html) if "tested by BH across" in line)
        assert fault_html[null_at + 1] == group_floor
        text = built.structure["tree"]["root"]["text"]
        assert text["p_floor"] == fmt_sig3(root["p_floor"]) == "2.50e-04"
        omnibus_page = paragraphs(region_lines(built.page, "Omnibus"))
        assert omnibus_page[2] == M7_FLOOR_LINE.format(p_floor=text["p_floor"], n_permutations=root["n_permutations"]), omnibus_page[:3]
        fault_page = paragraphs(region_lines(built.page, "Fault lines"))
        null_at = next(i for i, line in enumerate(fault_page) if "tested by BH across" in line)
        assert fault_page[null_at + 1] == M7_GROUP_FLOOR_LINE.format(p_floor=text["p_floor"], n_permutations=root["n_permutations"])
    report_md = lattice_cli["report.md"]
    # The command line writes report.md under rule 10.
    assert M7_FLOOR_LINE.format(p_floor=fmt_p10(1 / 301), n_permutations=300) in report_md and M7_GROUP_FLOOR_LINE.format(p_floor=fmt_p10(1 / 301), n_permutations=300) in report_md
    assert not same.tree.fault_lines.tested
    for text in (same.md, same.html, same.page):
        assert "group p floor" not in text and text.count("not a measurement") == 1, same.name
    assert "p floor" in md_sections(same.md)["Omnibus"][2]
    check = lattice_cli["check"]
    assert "p =" not in check and "p floor" not in check and "not a measurement" not in check, check
    # check's verdict is now its first stdout line, passed or failed.
    assert check.startswith("passed  ") and LATTICE_HEADLINE in check, check


def test_y18_the_kind_table_names_p_floor_as_sig3_and_w2s_round_trip_holds_with_the_new_key(lattice_built: Built, k2: Built, same: Built) -> None:
    assert viewer_mod._TREE_KINDS["root"]["p_floor"] == "sig3"
    for built in (lattice_built, k2, same):
        # PF4 (PF4.12): a condition with no detection limit has mde NaN, which the strict-JSON
        # structure writes as null; the round trip reads NaN as null to compare like with like.
        round_trip = json.loads(json.dumps(built.tree.to_json()), parse_constant=lambda _: None)
        assert without_text(built.structure["tree"]) == round_trip, built.name
        assert built.structure["tree"]["root"]["text"]["p_floor"] == fmt_sig3(built.tree.root.p_floor), built.name


# ---------- Y19, Y20: the version and the unverified block ----------


def test_y19_the_schema_is_viewpair_4_no_source_names_viewpair_3_and_the_schema_comment_names_p1_beside_a28() -> None:
    """The grep clause is C34's whole close."""
    # LS update: the grep is widened from ``/3`` alone to every retired version, because ``/4``
    # sat in a user-visible refusal for two rounds of changes while this clause looked for ``/3``.
    assert viewer_mod.SCHEMA == "poisson-prove.viewpair/7"
    retired = tuple(f"proofload.viewpair/{n}" for n in (2, 3, 4, 5, 6))
    # PF5: the core is a package now, so the grep reads src/ recursively.
    hits = sorted(path.name for path in SRC.rglob("*.py") if any(r in path.read_text(encoding="utf-8") for r in retired))
    assert hits == [], hits
    # PF8: the comment above ``SCHEMA`` named the two changes
    # that moved it; the plain-words pass rewrites every comment in src/ to say why in plain words, so
    # what a comment says is no longer pinned. The schema and the retired versions above still are.


def test_y20_the_unverified_ids_and_the_seed_identity_basis_statement_are_the_literals_and_nothing_says_paired(lattice_built: Built, k2: Built) -> None:
    """Mutant 19."""
    for built in (lattice_built, k2):
        entries = built.structure["unverified"]
        assert [e["id"] for e in entries] == list(UNVERIFIED_IDS), built.name
        last = entries[-1]
        assert (last["id"], last["statement"], last["blocked_by"]) == ("seed_identity_basis", SEED_IDENTITY_BASIS, None)
        for entry in entries:
            assert not PAIRED_TOKEN_RE.search(entry["id"]) and not PAIRED_TOKEN_RE.search(entry["statement"]), entry["id"]
        assert SEED_IDENTITY_BASIS in html_mod.unescape(built.page)
    assert [name for name, _, _ in viewer_mod._UNVERIFIED] == list(UNVERIFIED_IDS)


# ---------- Y21, Y22: the prohibitions ----------


def test_y21_no_new_statistic_no_second_honesty_block_and_p_floor_is_assigned_at_one_site_inside_root(lattice_built: Built, lattice_cli: dict[str, Any], k2: Built, same: Built) -> None:
    """The honesty and closure clauses are green before and after by design; the assignment-site
    clause is the guard on reading ``p_floor`` as a design constant, not a statistic."""
    # PF4 re-freeze (PF4.22, PF4.27): the honesty's limits are the exact limits at q / M, both
    # directions, so a626cd3's numbers (and the conditions that attain them) move, and a condition
    # with no limit is named with its reason instead of a number. The literals give way to the facts
    # they held, checked against the stats file's references; the wording a626cd3 pinned is kept.
    assert [p["honesty"] for p in lattice_built.structure["panels"]] == [p["honesty"] for p in lattice_cli["serve json"]["panels"]]
    for built in (lattice_built, k2, same):
        assert len(built.structure["panels"]) == len(HONESTY_AT_A626CD3[built.name]), built.name
        for panel in built.structure["panels"]:
            assert_honesty_facts(built, panel)
        for panel in built.structure["panels"]:
            assert "interval" not in panel["honesty"] and "alpha*" not in panel["honesty"], (built.name, panel["honesty"])
            assert built.md.count(panel["honesty"].splitlines()[0]) == 1, built.name
    module = parsed(VIEWER_SOURCE)
    arithmetic = arithmetic_nodes(closure(module, "build_structure"))
    assert len(arithmetic) == 1 and isinstance(arithmetic[0], ast.BinOp) and isinstance(arithmetic[0].op, ast.Sub), [ast.dump(n)[:60] for n in arithmetic]
    assert arithmetic_nodes(closure(module, "render_html")) == []
    sites = []
    for path in sorted(SRC.rglob("*.py")):  # PF5: the core is a package now, so the scan reads src/ recursively.
        for node in ast.walk(parsed(path)):
            if isinstance(node, ast.keyword) and node.arg == "p_floor":
                sites.append((path.name, node.lineno))
            elif isinstance(node, ast.Assign | ast.AugAssign) or (isinstance(node, ast.AnnAssign) and node.value is not None):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any((isinstance(t, ast.Name) and t.id == "p_floor") or (isinstance(t, ast.Attribute) and t.attr == "p_floor") for t in targets):
                    sites.append((path.name, node.lineno))
    root = resolve_region(parsed(TREE_SOURCE), "_root")
    assert len(sites) == 1 and sites[0][0] == "tree.py" and root.lineno <= sites[0][1] <= (root.end_lineno or 0), sites


def test_y22_serve_and_serve_json_on_the_lattice_write_nothing_to_the_store_the_cwd_or_the_temp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The E-family guard restated over the new payload; green before and after by design."""

    def snapshot(root: Path) -> dict[str, str]:
        return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}

    monkeypatch.chdir(tmp_path)
    before_store, before_cwd = snapshot(LATTICE_ROOT), snapshot(tmp_path)
    argv = ["--store", str(LATTICE_ROOT), "serve", LATTICE_A, LATTICE_B, "--event", EVENT, "--x", X, "--y", Y, "--permutations", "50"]
    code, out, err, calls = quiet(lambda: run_serve([*argv, "--json"]))
    assert code == 0 and calls == [] and out.startswith('{\n  "schema": '), err
    code, out, err, calls = quiet(lambda: run_serve(argv))
    assert calls == ["serve_page"] and out == "", (code, out[:80])
    # PF12: serve saves the comparison it shows under the store's
    # ``.poisson/``; nothing else in the store, the working folder or the temp folder is written.
    def stored(listing: dict[str, str]) -> dict[str, str]:
        return {k: v for k, v in listing.items() if not k.startswith(".poisson")}

    assert stored(snapshot(LATTICE_ROOT)) == stored(before_store) and snapshot(tmp_path) == before_cwd
    assert sorted(os.listdir(tmp_path)) == sorted(before_cwd) or before_cwd == {}
