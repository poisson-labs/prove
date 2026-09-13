"""S28 -- the report: the oracle for R1-R20.

Written from "Proofload -- Spec S28 Layered Report P4.4a The Report" section 4 and "Handoff
P4.4a", against ``3c472c9`` (2026-09-11), the retrofit commit that narrowed the E14 family in
five frozen oracles. Session B adds ``tree`` to ``MultiReport``, the ``tree=`` keyword on
``build_multi_report``, the four sections behind one ``if`` in each renderer, the reason
mapping and the formatting to ``src/proofload/report.py``, and the tree-flag helper, the five
flags on ``report``, the one ``_diff_tree`` call and the five names on ``_DIFF_ONLY_FLAGS`` to
``src/proofload/cli.py``, against this file, and does not edit it.

**``proofload.report``'s new keyword and field are reached inside test bodies** (``report_module``,
``built``): this file collects on the bare tree, its own tests fail there, and every other test
in the repo still reports. The static tests read the source as text.

**No test in this file carries the ``calibration`` marker, and none may.** The renderer draws
nothing: every number it prints is a field of a ``TreeResult`` M14 already computed, and the
tree is grown once per fixture at the golden knobs, so every rendering error is caught
deterministically and there is no rejection rate to hold in a band.

**Step zero, six items, measured at ``d5094a1`` before a test was written**
(``scratchpad/s28/step_zero.py`` and ``step_zero.log``). The grep report, over both dimensions,
is in Handoff P4.4a's *Session A's grep report* section, not here.

1. **The grep report** established the retrofit at five files (test_s21_errors.py E14,
   test_s24_interval.py C14, test_s25_root.py, test_s26_fault_lines.py F28, test_s27_leaves.py
   L20) and no sixth; the whole suite was green on the retrofit commit alone (1744 passed, 3
   skipped). The second dimension -- every test driving ``report`` on a pair through ``main()``
   -- is 36 sites in six files (37 invocations); every one keeps its assertion, because each
   asserts an exit code, a file set, the flat family's lines or a panel's shape, none of which
   the four sections touch, and the refusals it pins fire before the tree or, for the two M7
   axis errors, after a tree that writes nothing.
2. **The unmeasured pairs, none of which refuses.** ``holes-a``/``holes-b`` (test_competing_set
   H10): 3 tests, the root at p 1, ``level`` and ``task`` both refused ``underpowered``, the
   whole grid, ``root_not_rejected`` at both levels, depth 2 of 3, bound 0.288, exit 0.
   ``run-a``/``run-b`` at ``--event timeout`` (the site at line 617): 2 tests, root p 0.054,
   ``level`` refused ``one_group`` and ``task`` ``underpowered``, the whole grid, exit 0. The
   H6 mock pair: ``task_id`` (axis) with three groups all rejecting under one, three and the
   two inferred events -- 6 of 9, 14 of 27 and 8 of 18 leaves rejected -- exit 0; the absent
   event still exits 2 before any tree and writes nothing. test_m4_read R5's twins: the root
   rejects, ``x`` refused ``underpowered``, the whole grid, one leaf of two rejected, 0.288.
3. **The E14 measurement, re-run at HEAD.** ``build_multi_report(multi, spec, manifests=...)``
   with no tree on the E14 argv reproduces all three of S21's digests bit for bit -- markdown
   ``cc1157e3``, SVG ``3954321e``, light receipt ``974fa0a9`` -- and the CLI's three files
   still do. The dark-theme receipt differs from the light one, which is why the light build
   is the receipt's.
4. **The collision scan, re-run at HEAD** (spec section 0.4, cited by attribute and enclosing
   function, never by line). ``report.py``: the attributes ``delta`` inside a ``BinOp`` in
   ``_cell_fill`` and in ``_forest_body``, ``mde`` in ``_forest_body``; the bare names ``bound``
   in ``_cell_fill`` and ``config`` in ``_hole_map``. ``viewer.py``: none. ``cli.py``: the
   attributes ``event`` in ``_cmd_inspect`` and ``headline`` in ``_write_summary``, the bare
   name ``cells`` in ``_cmd_runs``. **Counting rule for "functions containing any ``BinOp``":**
   walking every ``FunctionDef`` and counting those whose subtree holds a ``BinOp`` reads 37 /
   6 / 22 for ``report.py`` / ``viewer.py`` / ``cli.py``; the log script's 38 / 7 / 23 counts
   the module body as a function. Neither number is asserted; the collision set is.
5. **The vocabulary collision set** (spec section 0.3): the 24 phrases confirmed as O19's nine,
   F19's nine and L10's six. ``step`` reaches ``report.md``, ``receipt.html`` and the viewer
   page of every builder-made pair through ``t unit: steps`` in the provenance and the
   identity block (the builders' ``t_unit``; the quickstart's is ``tool_calls`` and Go1's
   ``seconds``); ``where it`` reaches the viewer page alone, inside ``elsewhere it`` in the
   ``status_basis`` sentence V31 pins. Neither reaches the four sections, which is why R10 is
   scoped to them and to the tree's own strings and masks user data first.
6. **The kind table** (spec section 3.6): 21 rows naming 49 fields; every field exists on the
   structure it is attributed to (R4's static clause repeats the check).

**Conventions this oracle fixes where the spec is silent. Session B builds to these.**

- **The two roots of the tree-rendering closure are ``_tree_markdown(rep)`` and
  ``_tree_html(rep)``**, each returning the list of parts the renderer extends with; the
  closure is every module-level function either reaches by name, transitively, **never
  entering ``_fmt``, ``_md_table``, ``_html_table`` or ``_html_lines``** (R11's docstring says
  why). V17's arithmetic rule counts every augmented assignment, so the closure builds lists
  with ``append`` and ``extend``, never ``+=``.
- **Markdown layout.** ``## Omnibus`` and a blank line, then each item -- a line or a
  ``_md_table`` -- followed by a blank line, the same for the other three headings, and the
  figure line right after the bound section's last blank. **Receipt layout.** One element per
  line: ``<h2>Omnibus</h2>`` (no attributes), a ``<p>`` through ``_html_lines`` per line, a
  ``_html_table`` per table, then the figure ``div``.
- **Section contents, in order.** Omnibus: ``root.headline()`` verbatim; a method line
  carrying ``scheme``, ``n_permutations`` and ``seed``; one table whose rows are ``[event,
  location[e], p_location[e], dispersion[e], p_dispersion[e]]`` in ``root.events`` order; the
  informative line. Fault lines: the head line naming ``key (resolved_by)`` and the other
  eight fields; one line per ``Refusal`` carrying ``key``, ``rung``, ``reason``, ``detail``
  verbatim and ``next_rung``; the null line; one table whose rows are ``[label, n_cells,
  n_informative_cells, n_uninformative_cells, "n_a/n_b", mde]`` plus ``n_discordant`` iff the
  scheme is ``pair_swap`` plus ``[p_group, q_group, verdict]`` iff the level was tested, the
  verdict cell exactly ``rejected`` or ``not rejected``. Cells: the head; when any family
  exists the MDE-meaning sentence (``increase`` and ``headroom`` in it, no number); per family
  in ``families`` order a line carrying ``key=label`` and the four counts, then iff
  ``n_rejected > 0`` a table whose rows are ``[config, event, delta, q_within, mde]`` for the
  rejected leaves in ``cells`` order, ``config`` as ``key=value`` over every key in the
  config's own order, ``str(value)``, joined by a comma and a space. Bound: exactly two lines,
  the rule line and the assumption line.
- **The untested forms.** The fault-lines null line reads ``not tested`` and either ``the root
  did not reject`` or ``one group is the whole family restated``; the cells head reads ``not
  tested`` and exactly one of: ``depth`` with ``depth_configured`` and without ``root``; ``the
  root did not reject``; ``no group rejected``. Nothing else follows an untested cells head.
- **``pp`` is text beside the number**: ``20pp``, ``10.7pp``, ``34pp`` on the MDE fields; a
  delta prints as ``37.5`` under a header that says ``(pp)``.
- **Identity is R5-R8's, the kind is R4's.** A numeric cell or token is matched to its field
  under *any* of M7's kinds (``renders``), so a correct field under a wrong kind passes the
  section invariant and fails R4 alone (mutant 35); a wrong field fails the section invariant.
- **R4's allowed set** is every ``_fmt(field, kind)`` of the kind table, every count under
  ``int``, the numeric tokens of every label, config value, event name and requested key, the
  tokens of the verbatim ``headline()`` and ``detail`` strings, and the rule's ``2``. **The
  assumption line is the one line R4 skips**: it is free text under R10 and carries a citation
  year; a number smuggled onto it is R11's to catch.
- **The single-run refusal names each flag as typed**, ``--max-group-mde`` with dashes, with the
  existing diff-only sentence.
- **The namespace fill in ``_report_pair`` names the three knobs as strings**, never as
  attributes inside a comparison: S27's frozen L14 forbids any ``ast.Compare`` in ``cli.py``
  whose subtree names ``depth``, so ``if knobs.depth is None`` is red on the frozen suite
  (Session A's first control found it). The shim iterates ``(name, constant)`` pairs with
  ``getattr`` and ``setattr``; any form that keeps ``depth`` out of every ``Compare`` is
  admissible.
- **The empty family's refusal is unchanged**: exit 2 at M7's axis check (``not a config key``
  on stderr), so the tree is computed only when ``multi.n_tests > 0``.
- **The source-scan guards Session B builds under**, each a static read of ``src/`` that no
  runtime test can see past. On ``cli.py``: S27's L14 (no ``ast.Compare`` whose subtree names
  ``depth``); S27's L11, the superset of O17, F21 and S24's C19 (no ``BinOp`` whose subtree
  reaches a guarded tree field as an attribute or a guarded name as a bare name -- the five
  added lines read no tree field, so a loop over string constants is the safe shape); S24's
  C18 and M10's I21 (no ``numpy``, ``scipy`` or extras import). On ``report.py``: this
  oracle's R11 as widened (the closure of the two roots under V17's arithmetic rule, which
  counts every ``+=`` and unary minus; no ``format(``, ``.format(`` or ``round(`` call; no
  f-string format spec of any kind; no ``* 100``; no hex colour literal; none of ``1.44``,
  ``0.432``, ``0.288``, ``0.144`` as text in the closure's source; and, module-wide, none of
  M14's six constant names and no float constant equal to a bound literal); R12 (no name or
  attribute equal to a reason-tuple name; exactly one module-level string-keyed ``dict``
  literal with the four reason keys -- a second one is a finding); R1 (``build_multi_report``'s
  signature as the literal, and the module's bound public names unchanged, so every new
  module-level name is private); M7's B19 (no ``numpy`` or ``scipy`` import text). Across the
  core modules: M13's V14 (no network-client import). Session A's first control was red on
  L14 alone, which is why the list is here rather than in a footnote.
- **R2's with-tree digests were minted on Session A's shim**, whose rendered E14 sections are
  pasted verbatim into Handoff P4.4a's *Session A's mutation table* section as the appendix
  *The minted bytes*; the templates above reproduce them.

**A27's re-freeze, 2026-09-12 — what this pass added and what it stopped guarding.**

- **The BH-shaped hostile pair** (``hgroup-a``/``hgroup-b``) is this packet's one new fixture and
  is built identically in both re-frozen oracles, deliberately: built twice with different shapes
  it would give the two files two different power shapes to measure one guard against, and the two
  oracles would then disagree about what an admitted grouping is. Its constants and its measured
  shape are restated in both files and asserted in both, never imported.
- **The hostile-label guard is new coverage over already-correct behaviour**, so it is green
  before and after (standing rule 12's category). What makes it non-vacuous is measured rather
  than argued: mutant 31b -- the group label emitted unescaped in the fault-lines table -- was
  applied on a copy and is caught by this guard **alone** in this file, every other test in the
  file surviving it. The round-trip clauses are not what catch it: ``model()``/``table_of``
  unescape, so a raw cell also equals the value. The source-text and table-count clauses are.
- **``diff.py`` is no longer pinned whole** (ADR-077). One region is excluded, ``_pairing``,
  recorded in ``DIFF_PY_EXCLUDED`` with the entry's six fields including what it stopped guarding.
  The region is **this packet's own** -- C18's message restatement lives in it -- and it is not in
  ADR-077's plan for A27, which has A27 narrowing at ``_coverage`` for A22 on the stated basis that
  *A27's build does not touch ``diff.py``*. C18's message fix makes that false, measured: a copy
  carrying the restatement moves the whole-file digest, and a ``_coverage``-only exclusion does not
  hold across it. ``_coverage`` is **not** minted here. It moves to A22's Session A, where the
  exclusion and the ``tests/test_a22_pandas3.py`` cover it names land in one commit, which is
  ADR-077's own escape hatch for a packet that does touch the file -- and which keeps the
  cover-exists assertion below unconditional, rather than carving a named exception into the cover
  rule on the first packet to use it.
- **A22's retrofit, 2026-09-13: the second region landed as planned above.**
  ``diff.py::_coverage`` is now a live exclusion beside ``_pairing`` in this same record, owned
  by A22, minted at ``4b3c6ae``, covered by ``tests/test_a22_pandas3.py``'s V9-V12, retiring at
  ``A28``. ``DIFF_PY_SHA256`` is re-minted over the file with both regions removed -- a read off
  the shipped file, not a prediction -- and the two spans are measured disjoint (``_pairing``
  814-874, ``_coverage`` 908-946), which is ADR-077's permitted *adjacent* case.
- **All four carriers of this digest are narrowed here, not two.** Measured on a copy carrying the
  restatement: every one of the four ``DIFF_PY_SHA256`` clauses goes red on the message change, so
  narrowing only the two oracles this packet re-freezes would leave ``test_s26_fault_lines.py``
  (F28) and ``test_s27_leaves.py`` (L20) red from this build until A22. The handoff excluded those
  two to avoid S27's ``FROZEN_ORACLE_SHA256`` cascade; the cascade is one literal, read off a file
  this packet itself wrote, and costs no red. A27 narrows all four and re-mints that literal after
  the ``s26`` edit.

**Spec text this oracle could not use as written, each resolved here and reported.**

- R1's "no other public name is added" is measured as the names bound at module level by a
  ``def``, ``class`` or assignment, imports excluded: a typing import is a module attribute
  too, and the spec means the module's own surface.
- R11's "the two private functions" are unnamed in the spec; this oracle names them and the
  four excluded helpers (above). ``_fmt`` cannot be inside a closure that forbids ``* 100`` and
  ``format(``: it is the formatter.
- R12's unknown-reason clause is asserted on ``Leaves.reason`` and ``FaultLines.reason``;
  ``Refusal.reason`` is printed as its own string on the refusal line (R6), not through the
  mapping, whose four keys are the untested reasons.
- R15's "the twin stores of test_m4_read.py R5" is restated as the same pair written to two
  roots rendering identical files; R5 itself now runs the report-pair verb with the tree on its
  poisoned twin (grep report, dimension b).
- R14's "the stdout summary is byte-identical to today's" is pinned as the flat headline plus
  the three paths, built from ``multi.headline()``, which is what ``_write_summary`` prints.
- R4's "every numeric token is a field" admits the verbatim ``headline()`` (``:g`` under R5),
  the verbatim ``detail`` (a string field) and the rule's literal ``2``, and skips the
  assumption line (above).
- R13's "help text equal to ``diff --help``'s" is compared per flag after argparse's own
  wrapping is collapsed, invocation and help both.

**Named non-observables.** A second ``tree()`` call in ``_report_pair`` on the same frames and
knobs (mutant 32): the same bytes. R16's "before any string is built": a source property; the
oracle sees the raise at ``build_multi_report`` and no page.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import html as html_mod
import importlib
import inspect
import json
import math
import re
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import proofload
from proofload import cli
from proofload import diff as diff_mod
from proofload.diff import multi_diff
from proofload.episode import Episode
from proofload.store import EpisodeRecord, RunManifest, Store

PACKAGE = Path(proofload.__file__).resolve().parent
REPO = PACKAGE.parents[1]
REPORT_SOURCE = PACKAGE / "report.py"
DIFF_SOURCE = PACKAGE / "diff.py"
GO1_ROOT = REPO / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"
REGRESSION_DIR = GO1_ROOT / "report_regression"
QUICKSTART = REPO / "examples" / "quickstart.toml"
MOCK_MODULE = "proofload.examples.mock_agent"
ROLLOUT = f"{MOCK_MODULE}:rollout"
PATCHED = f"{MOCK_MODULE}:rollout_patched"
QUICKSTART_SALT = "0000000000000015"

# ---------- spec section 2, 3.2, 3.6: the literals ----------

#: R1. The four headings, markdown and HTML, in order.
HEADINGS = ("Omnibus", "Fault lines", "Cells", "Bound")
MD_HEADINGS = tuple(f"## {h}" for h in HEADINGS)
HTML_HEADINGS = tuple(f"<h2>{h}</h2>" for h in HEADINGS)
#: The line the four sections sit before, in each renderer (M7's own literals, unchanged).
MD_FIGURE = "![delta heatmaps](heatmap.svg)"
HTML_FIGURE_PREFIX = '<div class="figure">'
#: R1. The reason mapping's keys: the three P4.3 reasons and the two P4.2 reasons, four distinct.
REASONS = ("depth", "root_not_rejected", "no_group_rejected", "one_group")
#: R11, R12. Names of ``proofload.tree`` that ``report.py`` must never name.
FORBIDDEN_TREE_NAMES = (
    "DELTA_STAR", "DEFAULT_DEPTH", "DEPTHS", "LEAVES_NOT_TESTED_REASONS", "NOT_TESTED_REASONS", "REFUSAL_REASONS",
)
REASON_TUPLE_NAMES = ("LEAVES_NOT_TESTED_REASONS", "NOT_TESTED_REASONS", "REFUSAL_REASONS")
FORBIDDEN_BOUND_CONSTANTS = (1.44, 0.432, 0.288, 0.144)
#: R11. The two private roots of the tree-rendering closure (module docstring) and the four M7
#: helpers the closure excludes: the formatter, whose ``* 100`` and ``format(`` are the point,
#: and the three frozen table and line renderers.
TREE_ROOTS = ("_tree_markdown", "_tree_html")
CLOSURE_EXCLUDED = ("_fmt", "_md_table", "_html_table", "_html_lines")
#: R1. ``build_multi_report``'s signature after this packet, and the module's public names
#: at the base commit: every name bound at module level by a ``def``, ``class`` or assignment
#: that does not start with an underscore (imports excluded).
BUILD_MULTI_REPORT_SIGNATURE = (
    "(multi: 'MultiDiffResult', spec: 'ReportSpec', *, manifests: 'tuple[RunManifest, RunManifest] | None' = None, "
    "tree: 'TreeResult | None' = None) -> 'MultiReport'"
)
PUBLIC_NAMES_AT_BASE = (
    "ABSENT_FILL", "AxisError", "Cell", "ComparisonMismatch", "Mode", "MultiReport", "NEUTRAL_FILL", "Report",
    "ReportError", "ReportSpec", "SATURATED_FILL", "SEQUENTIAL_RAMP", "SurvivalReport", "Theme", "build_multi_report",
    "build_report", "build_survival_report", "heatmap",
)
#: The three nulls, quoted verbatim on the page (spec section 3.7).
ROOT_NULL = "no cell changed"
GROUP_NULL = "no cell in the group changed"
CELL_NULL = "this cell did not change"
#: R10. O19's nine phrases, F19's nine additions and L10's six; case-insensitive substrings.
FORBIDDEN_VOCABULARY = (
    "given the root", "given that", "conditional on", "leaf", "fdr", "broke", "where it broke",
    "failed at", "step",
    "broken", "failed in", "where it", "culprit", "root cause", "power stays high", "high power",
    "well powered", "same shift",
    "given the group", "given a group", "given that the group", "reliable", "controlled at q", "at level q",
)
#: R4, spec section 3.6: the kind table, this oracle's literal. ``(structure, field, kind)``;
#: mapping-valued fields (``location[e]`` and the like) are read per event of ``root.events``.
KIND_TABLE = (
    ("RootResult", "p_omnibus", "sig3"), ("RootResult", "p_location", "sig3"), ("RootResult", "p_dispersion", "sig3"),
    ("RootResult", "q", "sig3"), ("RootResult", "location", "pp1"), ("RootResult", "dispersion", "pp1"),
    ("RootResult", "n_cells", "int"), ("RootResult", "n_informative_cells", "int"), ("RootResult", "n_uninformative_cells", "int"),
    ("RootResult", "n_permutations", "int"), ("RootResult", "seed", "int"), ("RootResult", "n_discordant", "int"),
    ("Grouping", "alpha_floor", "sig3"), ("Grouping", "max_group_mde", "pp0"), ("Grouping", "size_min", "int"),
    ("Grouping", "size_max", "int"), ("Grouping", "n_groups", "int"), ("Grouping", "n_resolvable_groups", "int"),
    ("Grouping", "size_median", "num"),
    ("GroupResult", "mde", "pp1"), ("GroupResult", "location", "pp1"), ("GroupResult", "dispersion", "pp1"),
    ("GroupResult", "p_location", "sig3"), ("GroupResult", "p_dispersion", "sig3"), ("GroupResult", "p_group", "sig3"),
    ("GroupResult", "q_group", "sig3"), ("GroupResult", "n_cells", "int"), ("GroupResult", "n_informative_cells", "int"),
    ("GroupResult", "n_uninformative_cells", "int"), ("GroupResult", "n_a", "int"), ("GroupResult", "n_b", "int"),
    ("GroupResult", "n_discordant", "int"),
    ("FaultLines", "q", "sig3"), ("Leaves", "q", "sig3"),
    ("CellResult", "delta", "pp1"), ("CellResult", "q_within", "sig3"), ("CellResult", "mde", "pp0"),
    ("CellFamily", "mde_median", "pp0"), ("CellFamily", "mde_max", "pp0"),
    ("CellFamily", "n_tests", "int"), ("CellFamily", "n_rejected", "int"),
    ("Leaves", "n_tests", "int"), ("Leaves", "n_rejected", "int"), ("Leaves", "n_families", "int"),
    ("Bound", "bound", "sig3"), ("Bound", "q", "sig3"), ("Bound", "delta_star", "sig3"),
    ("Bound", "depth", "int"), ("Bound", "depth_configured", "int"),
)
KINDS = ("sig3", "pp1", "pp0", "num", "int")
#: The one numeric literal the bound line carries as text: the ``2`` of Yekutieli's rule,
#: ``2 x depth x q x delta*`` (spec section 3.2's sample line, ``cli.py``'s block before it).
BOUND_RULE_LITERAL = "2"

#: R2. S21's three E14 digests, restated (tree-less builder for two, the CLI for the SVG).
E14_ARGV = ("report", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw")
E14_SHA256 = {
    "report.md": "cc1157e3ec709f6ebc55409a77bb3207c73c864e659c0d7e82f3394aafdc57cb",
    "heatmap.svg": "3954321ec392b4438e02b295b117000088c1886c2eba225f8d7997a2cac374eb",
    "receipt.html": "974fa0a9b4ef1f81afceac39ff81f3ffe2423ae0a1d5cd84409e7e251dc15ad3",
}
#: R2, second clause: the CLI's ``report.md`` and ``receipt.html`` on the E14 argv **with** the
#: tree at the default knobs, minted on Session A's shim (module docstring).
E14_WITH_TREE_SHA256 = {
    "report.md": "ef0a396302370d11010695a7b80b3848e1e68f6e6481b74bb88a3f0db209c555",
    "receipt.html": "c12b4f503ae8eccf6be413d71655e160ff0aac8cdcddcc6e3edf9e5aa944a8cd",
}
#: R19, narrowed by A27 under ADR-077. S27 L20's other digests, restated rather than imported so
#: two frozen oracles do not couple -- and ``diff.py`` is no longer pinned whole: the digest below
#: is over the file with the AST regions named in ``DIFF_PY_EXCLUDED`` removed, whole lines, so the
#: clause keeps its original meaning -- *the builder touched nothing but the region its spec put in
#: scope* -- across a packet that moves the region, instead of being re-minted over bytes nobody can
#: read off anything that exists. Minted at ``101028c``; measured identical on a copy carrying A22
#: section 2's replacement and A27's own message restatement, and red on an edit anywhere else.
DIFF_PY_SHA256 = "105f1aa6b6e499d935227c1dca0ed8e1ead7204bb159c00a7aa02d12fa71f675"
#: **A22's retrofit, 2026-09-13 -- a second live region, ``diff.py::_coverage``** (ADR-077). The
#: digest above is over the file with **both** excluded regions removed, re-minted at ``4b3c6ae``
#: off the shipped file: a read, not a prediction. ADR-077 permits two exclusions on one file when
#: they are adjacent rather than overlapping, and these are -- measured at ``4b3c6ae``, ``_pairing``
#: is lines 814-874 and ``_coverage`` 908-946, disjoint, and the clause below asserts the
#: disjointness rather than assuming it. ``_coverage`` is A22's own: it carries the ``cause``
#: rebuild that makes a stored null survive pandas 3 in the printed coverage block, and its cover
#: lands in the same commit. Measured: ``105f1aa6...`` on the bare tree and on a copy carrying A22
#: section 2's replacement, identical, while the ``_pairing``-only digest moves ``21b34aa7...`` ->
#: ``b4a82174...`` and the whole file moves ``0438c2f5...`` -> ``d2b0ef59...``; a comment appended
#: outside both regions is still caught.
#: ADR-077's record, one per pinned file, one entry per excluded region, six fields beside the
#: digest because a narrowed guard that does not say what it stopped guarding is a weaker guard
#: dressed as a better one. ``region`` is the qualified name resolved against the pinned file's own
#: AST at call time -- exactly one definition or the clause refuses, never a line span, so a region
#: that grows or shrinks moves its boundary with it and decorators stay guarded. ``cover`` is the
#: oracle file and test ids that carry the region behaviourally, asserted to exist through the same
#: resolver so deleting a cover turns this clause red rather than leaving a silent hole.
DIFF_PY_EXCLUDED: tuple[dict[str, Any], ...] = (
    {
        "region": ("_pairing",),
        "owner": "A27",
        "cover": ("tests/test_s28_report.py", ("test_r21_the_unpaired_warning_states_the_cells_it_matched_and_names_coverage", "test_r21_paired_is_still_salt_equality_and_mcnemar_still_refuses_and_runs_where_it_did")),
        "minted_at": "101028c",
        "blind_spot": (
            "The excluded region also holds the three things C18 keeps out of this packet -- "
            "paired's salt equality, the NotPairable raises and the t_unit guard -- so the digest "
            "no longer sees them move. The cover is R21's pair rather than its message clause "
            "alone, for that reason; nothing else in this oracle would notice."
        ),
        "retire_at": "A28",
    },
    {
        "region": ("_coverage",),
        "owner": "A22",
        "cover": ("tests/test_a22_pandas3.py", ("test_v9_coverage_cause_is_none_on_every_comparable_row_and_a_named_cause_on_every_hole", "test_v10_the_coverage_block_prints_none_and_never_nan", "test_v11_the_diff_json_payload_dumps_with_allow_nan_false", "test_v12_no_astype_is_applied_to_the_cause_column_in_diff_py")),
        "minted_at": "4b3c6ae",
        "blind_spot": (
            "On pandas 2 the excluded region's only live guard is V12, the source-structural one: "
            "V9-V11 are green before and after there, because a from_records column keeps None on "
            "pandas 2 whatever its null pattern. COVERAGE_SHA256, the output digest over this very "
            "frame carried at five sites, cannot see the change at all -- measured e02aae9a... on "
            "the bare tree and on a copy carrying A22 section 2's replacement, under pandas 2.3.3 "
            "and 3.0.5 alike, because to_json(orient='records') renders None and NaN in an object "
            "column as the same null. Nothing in this oracle would notice either."
        ),
        "retire_at": "A28",
    },
)
F28_OMNIBUS_SHA256 = "03e7984ba22978e20386197f836fb60e0d32032a5b17a8bce400483e3e87296e"
CHECK_ARGV = ("check", GO1_A, GO1_B, "--event", "fell")
CHECK_STDOUT_SHA256 = "d8409ba0180546e115453f6d799a248b3528a49fd716179d90e98da4bf14e3b1"
CHECK_EXIT = 0
SERVE_ARGV = ("serve", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--json")
SERVE_STRUCTURE_SHA256 = "f58750a091af8da170f2f89484ae4076f5951c8ace2852bcf882e8b70ddc837d"
#: S29's narrowing (spec S29 section 3.7, draft ADR-074): ``serve --json`` now prints
#: ``proofload.viewpair/3``, which carries M14's tree under one new top-level key. The digest above
#: was minted on the bare tree, so it is taken over the structure with ``tree`` removed and
#: ``schema`` set back to this literal; on the bare tree that projection is the identity.
TREE_LESS_SCHEMA = "proofload.viewpair/2"
PAIR_QCOLUMN_SHA256 = "1e8e75a1679a92ba553d45d4b4fcdfd946d0e77939fec7ae7c214270e77719f9"
PAIR_DELTA_SHA256 = "0b46042d58b4ce9d8ff7cadfef1a0e20637d66e43de58c08f710e2021d3b35bf"
COVERAGE_SHA256 = "e02aae9ac0d0f902d5fdb9d36340e3a7a72c1a7d6d86b0e5a75fffda95dee5fa"
FELL_LOGRANK_QCOLUMN_SHA256 = "175f731751711047063b840dacb61c3a9e8ac86ccd937d0043d4986283821e53"
#: R19. The M7 regression fixtures, byte for byte (test_competing_set.py's FROZEN_SHA256, restated).
REGRESSION_SHA256 = {
    "report.md": "1755f5bd313e39a9da3b99980607b45d76dd16608d1d8a80a624bddc2af2d217",
    "heatmap.svg": "77df396e6e5cbe4423fe147c57735f33a4c4c5580b00f8e37314d1918fc5288f",
    "receipt.html": "4d0d64320de7be8549c673137d731b3529569f7452d9799983a87393f66cba00",
}
OMNIBUS_SIGNATURE = "(a: 'pd.DataFrame', b: 'pd.DataFrame', multi: 'MultiDiffResult', *, n_permutations: 'int' = 4000, seed: 'int' = 0) -> 'RootResult'"
RESOLVE_GROUPING_SIGNATURE = (
    "(requested: 'str | None', *, manifest_a: 'RunManifest', manifest_b: 'RunManifest', units: 'pd.DataFrame', "
    "q: 'float', max_group_mde: 'float | None' = None, frames: 'tuple[pd.DataFrame, pd.DataFrame] | None' = None) -> 'Grouping'"
)
TREE_PARAMETERS = (
    ("a", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty), ("b", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty),
    ("multi", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty), ("manifest_a", "KEYWORD_ONLY", inspect.Parameter.empty),
    ("manifest_b", "KEYWORD_ONLY", inspect.Parameter.empty), ("by", "KEYWORD_ONLY", None), ("n_permutations", "KEYWORD_ONLY", 4000),
    ("seed", "KEYWORD_ONLY", 0), ("max_group_mde", "KEYWORD_ONLY", None), ("depth", "KEYWORD_ONLY", 3),
)

#: R18. Go1 goldens (spec section 0.7; S27 L7 restated as rendered rows).
GO1_MU_GROUPS = 20
GO1_MU_REJECTED = 19
GO1_MU_NINETEENTH_LABEL = "0.95"
GO1_FISHER_LEAVES = 62
GO1_MCNEMAR_LEAVES = 60
GO1_PUSH_FAMILIES = (2, 2, 2, 2, 3, 7, 13, 13, 13, 9, 2, 0)
GO1_PUSH_UNSORTED_FAMILY = "70.0"
GO1_GRID_LEAVES = 60
BOUND_AT_DEPTH_2 = "0.288"
BOUND_AT_DEPTH_3 = "0.432"
#: R13. The five tree flags, and the values that reach the call on the axes pair.
TREE_FLAGS = ("--permutations", "--seed", "--by", "--max-group-mde", "--depth")
FLAG_VALUES = {"--permutations": "300", "--seed": "3", "--by": "temp", "--max-group-mde": "0.6", "--depth": "2"}
GOLDEN_PERMUTATIONS = 4000
GOLDEN_SEED = 0
Q = 0.05

# ---------- the frozen S27 builders, restated ----------

NON_EVENTS = frozenset({"ok", "x", "z", "plain"})
EVENT_T = 2.0
HORIZON = 5.0
SALT = "s27-salt"
OTHER_SALT = "s27-other-salt"
AXES_SALT = "s26-axes-salt"
BH_SALT = "s26-bh-salt"
AXES_TYPES_TASK_FIRST = {"task": "categorical", "temp": "continuous"}
BH_TYPES = {"grp": "categorical", "cell": "categorical"}
GATE_TYPES = {"grp": "categorical", "cell": "categorical"}
ME_TYPES = {"task": "categorical", "temp": "continuous"}
ME_EVENTS = ("fail", "crash")
N_TASKS = 164
AXES_N = 8
AXES_MOVED_CELLS = 20
AXES_MOVED_PAIRS = 2
GATE_GROUPS = 40
GATE_CELLS = 6
GATE_N = 64
GATE_DISCORDANT = 8
ME_N = 128
ME_TASKS = 8
ME_TEMPS = (0.0, 0.7)
#: R10's synthetic pair: two task values that are forbidden phrases, so the mask is what keeps
#: the check green. R17's: a closing table tag, a script element and ``&"``.
VOCABULARY_VALUES = ("given the root", "where it broke")
HOSTILE_VALUE = "".join(["<", "/table><script>alert(1)</script>&", chr(34)])
PLAIN_VALUE = "plain-task"
#: A27. M13's hostile string beside R17's own, and the BH-shaped hostile pair both oracles share.
#: The pair's ``task`` values are these two, and ``HOSTILE_VALUES`` is the same tuple of the same
#: two strings as ``tests/test_s29_viewer.py``'s, restated rather than imported so two frozen
#: oracles do not couple. The grouping key ``task`` takes them as its values and ``cell`` supplies
#: the cells inside each group, so the axis rung reaches ``task`` and the power rule **admits** it
#: instead of refusing it ``underpowered`` and collapsing to ``whole_grid`` -- which is what R17's
#: own two-cell pair does, and why no group label in either oracle has ever carried a hostile
#: value. Measured at ``101028c``: two groups of eight cells at N=32 is 256 units per arm per
#: group, whose group MDE is 0.1347 against the 0.20 default at the two-group floor
#: alpha = q/2 = 0.025, so both groups resolve. 128 units per arm would read 0.1883 and still
#: admit; the margin is taken so a later power-rule change cannot quietly return this fixture to
#: the collapse it exists to escape, and ``HOSTILE_GROUP_ADMITTED`` is what makes such a return
#: loud. Arm b is moved in every cell of both groups, by different amounts, so both groups reject,
#: each becomes a family, and both values reach a group label, a family line and a leaf config cell.
HOSTILE_IMG = "".join(["<", "/script><img src=x onerror=", chr(34), "alert(1)", chr(34), ">&", chr(34)])
HOSTILE_VALUES = (HOSTILE_IMG, HOSTILE_VALUE)
HOSTILE_GROUP_TYPES = {"task": "categorical", "cell": "categorical"}
HOSTILE_GROUP_CELLS = 8
HOSTILE_GROUP_N = 32
HOSTILE_GROUP_BASE = 2
HOSTILE_GROUP_EXTRA = (14, 8)
#: A27. The admitted grouping as both oracles read it: (key, resolved_by, n_groups,
#: n_resolvable_groups). ``whole_grid`` in either of the first two is the collapse this fixture
#: exists to avoid, and asserting this tuple is what stops R17's label guard going vacuous.
HOSTILE_GROUP_ADMITTED = ("task", "axis", 2, 2)
#: A27. What the admitted axis makes testable, measured at ``101028c``.
HOSTILE_GROUP_REJECTED_GROUPS = 2
HOSTILE_GROUP_FAMILIES = 2
HOSTILE_GROUP_TESTS = 16
HOSTILE_GROUP_REJECTED = 16


def tree() -> Any:
    """``proofload.tree``, imported at call time."""
    return importlib.import_module("proofload.tree")


def report_module() -> Any:
    """``proofload.report``, imported at call time: the new keyword and field are reached inside
    test bodies, so this file collects on the bare tree and its own tests fail there."""
    return importlib.import_module("proofload.report")


def quiet_multi_diff(a: pd.DataFrame, b: pd.DataFrame, ma: RunManifest, mb: RunManifest, *, events: Sequence[str], method: str, q: float = Q) -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return multi_diff(a, b, events=list(events), method=method, q=q, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]


def manifest(run_id: str, salt: str, axis_types: Mapping[str, str]) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types), backend="synthetic", environment={"note": "built by test_s28_report"},  # type: ignore[arg-type]
    )


def write_run(store: Store, run_id: str, *, salt: str, axis_types: Mapping[str, str], cells: Mapping[tuple[tuple[str, Any], ...], Sequence[str]]) -> None:
    """A complete synthetic run over multi-key configs, one episode per outcome (S27's, restated)."""
    store.create_run(manifest(run_id, salt, axis_types))
    records = []
    for index, (key, outcomes) in enumerate(cells.items()):
        for k, outcome in enumerate(outcomes):
            t = HORIZON if outcome in NON_EVENTS else EVENT_T
            records.append(EpisodeRecord.from_episode(
                Episode(outcome=outcome, t=t, horizon=HORIZON), run_id=run_id, config=dict(key), seed=1000 * index + k,
                replicate_index=k, wall_time=0.0,
            ))
    store.append(run_id, records)
    store.mark_complete(run_id)


def axes_cells(moved: bool) -> dict[tuple[tuple[str, Any], ...], list[str]]:
    cells = {}
    for i in range(N_TASKS):
        for temp in (0.0, 0.7):
            outcomes = ["ok"] * AXES_N
            if moved and temp == 0.0 and i < AXES_MOVED_CELLS:
                outcomes = ["fail"] * AXES_MOVED_PAIRS + ["ok"] * (AXES_N - AXES_MOVED_PAIRS)
            cells[(("task", f"t{i:03d}"), ("temp", temp))] = outcomes
    return cells


def bh_cells(weak_cells: int, extra_fails: int) -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    a, b = {}, {}
    for g_ in range(20):
        for c in range(10):
            key = (("grp", f"g{g_:02d}"), ("cell", f"c{c}"))
            base = ["fail"] * 4 + ["ok"] * 28
            a[key], b[key] = list(base), list(base)
            if g_ == 0 and c < weak_cells:
                for r in range(4, 4 + extra_fails):
                    b[key][r] = "fail"
    return a, b


def gate_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    a, b = {}, {}
    for g_ in range(GATE_GROUPS):
        for c in range(GATE_CELLS):
            key = (("grp", f"g{g_:02d}"), ("cell", f"c{c}"))
            base = ["fail"] * 4 + ["ok"] * (GATE_N - 4)
            a[key], b[key] = list(base), list(base)
            if g_ == 0 and c == 0:
                for r in range(4, 4 + GATE_DISCORDANT):
                    b[key][r] = "fail"
    return a, b


def multi_event_cells(crash_elsewhere: bool) -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    a, b = {}, {}
    k = ME_N // 32
    for t in range(ME_TASKS):
        for temp in ME_TEMPS:
            key = (("task", f"t{t}"), ("temp", temp))
            if t == 0:
                a[key] = ["fail"] * (4 * k) + ["ok"] * (28 * k)
                b[key] = ["fail"] * (20 * k) + ["ok"] * (12 * k)
            else:
                base = ["fail"] * (4 * k) + (["crash"] * k if crash_elsewhere else ["ok"] * k) + ["ok"] * (27 * k)
                a[key], b[key] = list(base), list(base)
    return a, b


def one_value_cells(moved: bool) -> dict[Any, list[str]]:
    return {(("task", f"t{i}"), ("temp", 0.0)): (["fail"] * 8 if moved else ["ok"] * 8) for i in range(4)}


THREE_KEY_TYPES = {"task": "categorical", "temp": "continuous", "model": "categorical"}
THREE_KEY_MODELS = ("m1", "m2")


def three_key_cells(moved: bool) -> dict[Any, list[str]]:
    """R7's fixed-third-key pair: four ``task`` x one ``temp`` x two ``model`` at N=8, arm b
    moved in every replicate. ``report --x task --y temp --fix model=m1`` slices the figure to
    ``m1`` while the tree is over all eight cells, so a leaf row outside the slice is still a
    leaf and every row carries ``model=``."""
    return {
        (("task", f"t{i}"), ("temp", 0.0), ("model", m)): (["fail"] * 8 if moved else ["ok"] * 8)
        for i in range(4)
        for m in THREE_KEY_MODELS
    }


def two_value_cells(values: Sequence[str], moved: bool) -> dict[Any, list[str]]:
    """R10's and R17's two-cell pairs: one ``task`` value per cell at N=8, arm b moved in every
    replicate so the root rejects, the grouping collapses and both leaves are named."""
    return {(("task", v), ("temp", 0.0)): (["fail"] * 8 if moved else ["ok"] * 8) for v in values}


def overlap_cells(shift: int) -> dict[Any, list[str]]:
    """C18's partially-overlapping pair: the same salt and a ``task`` set shifted by one, which is
    what a sweep-file edit that moves an axis value produces. Three cells are matched, one is in
    arm a alone and one in arm b alone, so ``coverage`` lists cells with no counterpart while the
    pair is still ``paired`` -- the page the warning's old sentence contradicted."""
    return {
        (("task", f"t{i}"), ("temp", 0.0)): (["fail"] * 2 + ["ok"] * 6 if shift else ["ok"] * 8)
        for i in range(shift, shift + 4)
    }


def hostile_group_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """A27's BH-shaped hostile pair: ``task`` takes the two hostile values and is the grouping,
    ``cell`` supplies eight cells inside each group at N=32. Arm b is moved in every cell of both
    groups, by a different amount per group, so the root rejects, the axis is admitted rather than
    refused underpowered, both groups reject and every leaf rejects."""
    a: dict[Any, list[str]] = {}
    b: dict[Any, list[str]] = {}
    for index, value in enumerate(HOSTILE_VALUES):
        for c in range(HOSTILE_GROUP_CELLS):
            key = (("task", value), ("cell", f"c{c}"))
            row = ["fail"] * HOSTILE_GROUP_BASE + ["ok"] * (HOSTILE_GROUP_N - HOSTILE_GROUP_BASE)
            a[key], b[key] = list(row), list(row)
            for r in range(HOSTILE_GROUP_BASE, HOSTILE_GROUP_BASE + HOSTILE_GROUP_EXTRA[index]):
                b[key][r] = "fail"
    return a, b


# ---------- the CLI, cached per argv ----------


@dataclass(frozen=True)
class Rendered:
    code: int
    out: str
    err: str
    out_dir: Path

    @property
    def text(self) -> str:
        return self.out + self.err

    def file(self, name: str) -> str:
        return (self.out_dir / name).read_text(encoding="utf-8")

    @property
    def md(self) -> str:
        return self.file("report.md")

    @property
    def html(self) -> str:
        return self.file("receipt.html")

    @property
    def svg(self) -> str:
        return self.file("heatmap.svg")


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


_RENDERED: dict[tuple[str, ...], Rendered] = {}


def rendered(outs: Path, root: Path, *argv: str) -> Rendered:
    """``report`` through ``main()`` on ``root``, written under ``outs``; one run per distinct argv."""
    key = (str(root), *argv)
    if key not in _RENDERED:
        out_dir = outs / f"r{len(_RENDERED):03d}"
        code, out, err = run_cli(["--store", str(root), "report", *argv, "--out", str(out_dir)])
        _RENDERED[key] = Rendered(code, out, err, out_dir)
    return _RENDERED[key]


def ok(outs: Path, root: Path, *argv: str) -> Rendered:
    r = rendered(outs, root, *argv)
    assert r.code == 0 and r.err == "", (argv, r.text)
    return r


# ---------- trees, cached per knobs ----------


_TREES: dict[tuple[Any, ...], tuple[Any, Any]] = {}


def store_tree(root: Path, a: str, b: str, *, events: Sequence[str], method: str = "fisher_bh", **knobs: Any) -> tuple[Any, Any]:
    """``(multi, tree)`` on a stored pair the way the CLI reaches them: the frames read with
    ``meta=False``, ``multi_diff`` at the CLI's default ``q``, ``tree`` at M14's defaults unless a
    knob is given."""
    key = (str(root), a, b, tuple(events), method, tuple(sorted(knobs.items())))
    if key not in _TREES:
        store = Store(root)
        fa, fb = store.read(a, meta=False), store.read(b, meta=False)
        ma, mb = store.manifest(a), store.manifest(b)
        multi = quiet_multi_diff(fa, fb, ma, mb, events=events, method=method)
        _TREES[key] = (multi, tree().tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, **knobs))
    return _TREES[key]


def spec_for(a: str, b: str, events: Sequence[str], x: str, y: str | None, **extra: Any) -> Any:
    return report_module().ReportSpec(title=f"{a} vs {b}: {', '.join(events)}", x_axis=x, y_axis=y, **extra)


def built(root: Path, a: str, b: str, *, events: Sequence[str], x: str, y: str | None, with_tree: bool, method: str = "fisher_bh", theme: str = "dark", **knobs: Any) -> Any:
    """``build_multi_report`` on a stored pair, with the tree at ``knobs`` or with none."""
    multi, result = store_tree(root, a, b, events=events, method=method, **knobs)
    store = Store(root)
    manifests = (store.manifest(a), store.manifest(b))
    spec = spec_for(a, b, events, x, y, theme=theme)
    if with_tree:
        return report_module().build_multi_report(multi, spec, manifests=manifests, tree=result)
    return report_module().build_multi_report(multi, spec, manifests=manifests)


# ---------- the four sections, by index ----------


def md_bounds(md: str) -> tuple[int, int]:
    """``(start, end)`` line indices: the ``## Omnibus`` line and the figure line."""
    lines = md.splitlines()
    starts = [i for i, line in enumerate(lines) if line == MD_HEADINGS[0]]
    figures = [i for i, line in enumerate(lines) if line == MD_FIGURE]
    assert len(figures) == 1, figures
    assert len(starts) == 1, starts
    assert starts[0] < figures[0], (starts, figures)
    return starts[0], figures[0]


def html_bounds(html: str) -> tuple[int, int]:
    lines = html.splitlines()
    starts = [i for i, line in enumerate(lines) if line == HTML_HEADINGS[0]]
    figures = [i for i, line in enumerate(lines) if line.startswith(HTML_FIGURE_PREFIX)]
    assert len(figures) == 1, figures
    assert len(starts) == 1, starts
    assert starts[0] < figures[0], (starts, figures)
    return starts[0], figures[0]


def excised(text: str, bounds: tuple[int, int]) -> str:
    lines = text.splitlines(keepends=True)
    start, end = bounds
    return "".join(lines[:start] + lines[end:])


def section_lines(text: str, kind: str) -> dict[str, list[str]]:
    """The raw lines of each of the four sections, heading excluded, blank lines dropped;
    asserts the four headings appear once each, in order, inside the bounds."""
    headings = MD_HEADINGS if kind == "md" else HTML_HEADINGS
    lines = text.splitlines()
    start, end = md_bounds(text) if kind == "md" else html_bounds(text)
    span = lines[start:end]
    positions = [[i for i, line in enumerate(span) if line == h] for h in headings]
    assert all(len(p) == 1 for p in positions), positions
    order = [p[0] for p in positions]
    assert order == sorted(order) and order[0] == 0, order
    out: dict[str, list[str]] = {}
    for name, i, j in zip(HEADINGS, order, [*order[1:], len(span)], strict=True):
        out[name] = [line for line in span[i + 1 : j] if line.strip()]
    for line in lines[:start] + lines[end:]:
        assert line not in headings, line
    return out


TD_RE = re.compile(r"<td>(.*?)</td>", re.S)
TH_RE = re.compile(r"<th>(.*?)</th>", re.S)
TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
TAG_RE = re.compile(r"<[^>]+>")


def md_cells(line: str) -> list[str]:
    assert line.startswith("|") and line.endswith("|"), line
    return [c.strip() for c in line[1:-1].split("|")]


def model(lines: list[str], kind: str) -> list[tuple[Any, ...]]:
    """A section as items: ``("line", text)`` for a paragraph, ``("table", header, rows)`` for a
    table. Markdown: consecutive ``|`` lines are one table, the second being the separator.
    HTML: one element per line, ``<p>`` a paragraph (``<br>`` a line break inside it, unescaped)
    and ``<table>`` a table with a ``<thead>`` and a ``<tbody>``."""
    items: list[tuple[Any, ...]] = []
    if kind == "md":
        i = 0
        while i < len(lines):
            if lines[i].startswith("|"):
                j = i
                while j < len(lines) and lines[j].startswith("|"):
                    j += 1
                block = lines[i:j]
                assert len(block) >= 2 and all(set(c) <= set("-") and c for c in md_cells(block[1])), block[:2]
                items.append(("table", md_cells(block[0]), [md_cells(r) for r in block[2:]]))
                i = j
            else:
                items.append(("line", lines[i]))
                i += 1
        return items
    for line in lines:
        if line.startswith("<table>"):
            assert line.startswith("<table><thead>") and "<tbody>" in line and line.endswith("</tbody></table>"), line[:80]
            head, body = line.split("<tbody>", 1)
            header = [html_mod.unescape(h) for h in TH_RE.findall(head)]
            rows = [[html_mod.unescape(c) for c in TD_RE.findall(tr)] for tr in TR_RE.findall(body)]
            items.append(("table", header, rows))
        else:
            assert line.startswith("<p>") and line.endswith("</p>"), line[:80]
            items.append(("line", html_mod.unescape(TAG_RE.sub("\n", line[3:-4])).replace("\n", " ").strip()))
    return items


def sections(text: str, kind: str) -> dict[str, list[tuple[Any, ...]]]:
    return {name: model(lines, kind) for name, lines in section_lines(text, kind).items()}


def lines_of(items: Sequence[tuple[Any, ...]]) -> list[str]:
    return [item[1] for item in items if item[0] == "line"]


def tables_of(items: Sequence[tuple[Any, ...]]) -> list[tuple[list[str], list[list[str]]]]:
    return [(item[1], item[2]) for item in items if item[0] == "table"]


def section_text(items: Sequence[tuple[Any, ...]]) -> str:
    parts = []
    for item in items:
        if item[0] == "line":
            parts.append(item[1])
        else:
            parts.append(" | ".join(item[1]))
            parts.extend(" | ".join(r) for r in item[2])
    return "\n".join(parts)


# ---------- tokens and the kind table ----------


TOKEN_SPLIT = re.compile(r"[\s=,:;()/|]+")


def numeric_tokens(text: str) -> list[str]:
    """Every whitespace-, ``=``-, ``,``-, ``:``-, ``;``-, ``(``-, ``)``-, ``/``- or ``|``-separated
    token that parses as a number, verbatim, a trailing ``pp`` stripped first (the kind table's
    suffix is text beside the number)."""
    out = []
    for token in TOKEN_SPLIT.split(text):
        if token.endswith("pp"):
            token = token[:-2]
        try:
            float(token)
        except ValueError:
            continue
        out.append(token)
    return out


def fmt(value: Any, kind: str) -> str:
    """M7's one formatter, reached the way S21's oracle reaches it."""
    from proofload.report import _fmt

    return _fmt(value, kind)


def renders(cell: str, value: Any) -> bool:
    """``cell`` is ``value`` under one of M7's kinds: the field-identity check of R5-R8, which
    leaves the *kind* to R4 (module docstring)."""
    token = cell[:-2] if cell.endswith("pp") else cell
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer() and abs(value) < 1e15):
        return token == fmt(int(value), "int") or token in {fmt(value, k) for k in ("sig3", "pp1", "pp0", "num")}
    return token in {fmt(value, k) for k in ("sig3", "pp1", "pp0", "num")}


def has(text: str, value: Any) -> bool:
    return any(renders(tok, value) for tok in TOKEN_SPLIT.split(text))


def user_data(result: Any, requested: str | None) -> list[str]:
    pieces = [requested or "", *result.root.events, *result.grouping.labels]
    for family in result.leaves.families:
        pieces.append(family.label)
        for leaf in family.cells:
            pieces.extend(str(v) for v in leaf.config.values())
    return [p for p in pieces if p]


def masked(text: str, result: Any, requested: str | None) -> str:
    out = text
    for piece in sorted(set(user_data(result, requested)), key=len, reverse=True):
        out = out.replace(piece, "")
    return out.lower()


def expected_tokens(result: Any, *, requested: str | None = None) -> tuple[set[str], set[str]]:
    """R4's two sets, rebuilt from the tree and the kind table: ``allowed`` -- every ``_fmt(field,
    kind)`` the table assigns, every count under ``int``, the numeric tokens of every user-data
    string, of the verbatim ``headline()`` and ``detail`` strings, and the rule's ``2``; and
    ``required`` -- the fields spec section 3.2's layout prints, given what was tested."""
    root, grouping, fault, leaves, bound = result.root, result.grouping, result.fault_lines, result.leaves, result.bound
    allowed: set[str] = set()
    required: set[str] = set()

    def add(obj: Any, name: str, kind: str, *, need: bool) -> None:
        value = getattr(obj, name)
        if value is None:
            return
        if isinstance(value, Mapping):
            for event in root.events:
                token = fmt(value[event], kind)
                allowed.add(token)
                if need:
                    required.add(token)
            return
        token = fmt(value, kind)
        allowed.add(token)
        if need:
            required.add(token)

    by_structure: dict[str, list[tuple[str, str]]] = {}
    for structure, name, kind in KIND_TABLE:
        by_structure.setdefault(structure, []).append((name, kind))
    layout_root = {"location", "dispersion", "p_location", "p_dispersion", "n_cells", "n_informative_cells", "n_uninformative_cells", "n_permutations", "seed"}
    for name, kind in by_structure["RootResult"]:
        add(root, name, kind, need=name in layout_root)
    for name, kind in by_structure["Grouping"]:
        add(grouping, name, kind, need=True)
    for group in fault.groups:
        for name, kind in by_structure["GroupResult"]:
            need = name in {"n_cells", "n_informative_cells", "n_uninformative_cells", "n_a", "n_b", "mde", "n_discordant"} or (
                fault.tested and name in {"p_group", "q_group"}
            )
            add(group, name, kind, need=need)
    add(fault, "q", "sig3", need=fault.tested)
    for name in ("n_groups", "n_degenerate_groups", "n_rejected_groups"):
        add(fault, name, "int", need=name != "n_groups" or True)
    add(leaves, "q", "sig3", need=leaves.tested)
    for name in ("n_families", "n_tests", "n_rejected"):
        add(leaves, name, "int", need=leaves.tested)
    for family in leaves.families:
        for name, kind in by_structure["CellFamily"]:
            add(family, name, kind, need=True)
        for leaf in family.cells:
            for name, kind in by_structure["CellResult"]:
                add(leaf, name, kind, need=leaf.rejects)
    for name, kind in by_structure["Bound"]:
        add(bound, name, kind, need=True)
    if leaves.reason == "depth":
        required.add(fmt(bound.depth_configured, "int"))
    verbatim = [root.headline(), *(r.detail for r in grouping.refused), *user_data(result, requested)]
    for text in verbatim:
        allowed.update(numeric_tokens(text))
        allowed.update(t for t in TOKEN_SPLIT.split(text) if t)
    allowed.add(BOUND_RULE_LITERAL)
    return allowed, required


def tokens_of(items: Sequence[tuple[Any, ...]], *, skip_last_line: bool = False) -> list[str]:
    out: list[str] = []
    lines = [item for item in items if item[0] == "line"]
    last = lines[-1] if (skip_last_line and lines) else None
    for item in items:
        if item is last:
            continue
        if item[0] == "line":
            out.extend(numeric_tokens(item[1]))
        else:
            for row in [item[1], *item[2]]:
                for cell in row:
                    out.extend(numeric_tokens(cell))
    return out


def g(value: Any) -> str:
    return f"{value:g}"


def config_text(config: Mapping[str, Any]) -> str:
    """A leaf's cell as ``key=value`` over every key of ``config``, in the config's own order,
    ``str(value)``, joined by a comma and a space (module docstring)."""
    return ", ".join(f"{k}={v}" for k, v in config.items())


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_column(result: Any, column: str) -> str:
    return sha256_of_text("|".join(f"{e}:" + ",".join(f"{v:.17g}" for v in result.by_event[e].cells[column]) for e in result.events))


def json_bytes(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)


def without(payload: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in keys}


# ---------- ast helpers (V17's, restated) ----------


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def module_functions(module: ast.Module) -> dict[str, ast.AST]:
    return {n.name: n for n in module.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}


def resolve_region(tree: ast.Module, qualified: str) -> ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef:
    """ADR-077's boundary: a qualified name resolved against the pinned file's own AST.

    Walks the module's direct children for the first segment and that node's children for the
    next, and refuses on anything but exactly one match -- ADR-072's collision discipline moved
    from names to definitions. Restated rather than imported, as the frozen oracles' digests are.
    """
    node: ast.AST = tree
    definition: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | None = None
    for segment in qualified.split("."):
        matches = [
            child
            for child in ast.iter_child_nodes(node)
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and child.name == segment
        ]
        assert len(matches) == 1, (qualified, segment, len(matches))
        definition = matches[0]
        node = definition
    assert definition is not None, qualified
    return definition


def digest_excluding(path: Path, regions: Sequence[str]) -> str:
    """The file's sha256 with each region's ``lineno``..``end_lineno`` removed, whole lines.

    ``lineno`` is the ``def`` line and a decorator sits above it, so decorators stay guarded and
    one added or changed is caught.
    """
    source = path.read_bytes()
    spans = [(n.lineno, n.end_lineno) for n in (resolve_region(ast.parse(source), q) for q in regions)]
    kept = [
        line
        for index, line in enumerate(source.decode().splitlines(keepends=True), start=1)
        if not any(low <= index <= high for low, high in spans)
    ]
    return hashlib.sha256("".join(kept).encode()).hexdigest()


def closure(module: ast.Module, roots: Sequence[str], excluded: Sequence[str]) -> list[ast.AST]:
    """The named functions plus every module-level function they reach by name, transitively,
    never entering ``excluded``."""
    functions = module_functions(module)
    seen: dict[str, ast.AST] = {}
    todo = list(roots)
    while todo:
        current = todo.pop()
        if current in seen or current not in functions or current in excluded:
            continue
        seen[current] = functions[current]
        for node in ast.walk(functions[current]):
            if isinstance(node, ast.Name) and node.id in functions and node.id not in seen:
                todo.append(node.id)
    return list(seen.values())


ARITHMETIC = (ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.MatMult)


def is_non_numeric(node: ast.AST) -> bool:
    return isinstance(node, ast.JoinedStr | ast.List | ast.ListComp | ast.Tuple) or (
        isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def arithmetic_nodes(nodes: Sequence[ast.AST]) -> list[ast.AST]:
    """V17's rule: ``-``, ``*``, ``/``, ``//``, ``%``, ``**``, an augmented assignment with any of
    those or ``+``, a unary minus on a non-constant, and ``+`` unless one side is a string
    literal, f-string, list or tuple."""
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


def format_calls(nodes: Sequence[ast.AST]) -> list[int]:
    """Every ``format(...)``, ``.format(...)`` and ``round(...)`` call."""
    return [
        node.lineno
        for fn in nodes
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in ("format", "round"))
            or (isinstance(node.func, ast.Attribute) and node.func.attr == "format")
        )
    ]


def format_specs(nodes: Sequence[ast.AST]) -> list[int]:
    """Every f-string field carrying a format spec (``{x:.1f}``, ``{x:g}``, any at all)."""
    return [
        node.lineno
        for fn in nodes
        for node in ast.walk(fn)
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None
    ]


HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
#: The bound's four literals as text: a bound typed inside an f-string is a string constant,
#: which the ``ast.Constant`` clause cannot see (mutant 6 in the preview pass).
BOUND_LITERAL_RE = re.compile(r"(?<![\d.])(1\.44|0\.432|0\.288|0\.144)(?![\d])")
TIMES_100_RE = re.compile(r"\*\s*100\b")
FLOAT_SPEC_RE = re.compile(r":\.\d")


def source_of(module_source: str, nodes: Sequence[ast.AST]) -> str:
    return "\n".join(ast.get_source_segment(module_source, n) or "" for n in nodes)


def mentioned(module: ast.Module) -> set[str]:
    out = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            out.update(alias.name for alias in node.names)
    return out


def constants(module: ast.Module) -> list[Any]:
    return [n.value for n in ast.walk(module) if isinstance(n, ast.Constant)]


def bound_names(module: ast.Module) -> set[str]:
    """Every name bound at module level by a ``def``, a ``class``, an assignment or an annotated
    assignment: the module's own names, imports excluded."""
    out: set[str] = set()
    for node in module.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            out.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.add(node.target.id)
    return out


def string_dicts(module: ast.Module) -> list[tuple[str, set[str]]]:
    """Module-level ``NAME = {...}`` literals whose keys are all string constants."""
    out = []
    for node in module.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(value, ast.Dict):
            keys = value.keys
            if keys and all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in keys):
                out.append((target.id, {k.value for k in keys}))  # type: ignore[union-attr]
    return out


# ---------- help text ----------


def help_entries(text: str) -> dict[str, tuple[str, str]]:
    """Every option of an argparse help text as ``flag -> (invocation, help)``, whitespace
    collapsed; an entry starts at two spaces and a dash, its help continues on deeper-indented
    lines."""
    entries: dict[str, tuple[str, list[str]]] = {}
    current: str | None = None
    for line in text.splitlines():
        m = re.match(r"^  (-\S.*?)(?:\s{2,}(.*))?$", line)
        if m and not line.startswith("   "):
            invocation = m.group(1).strip()
            flag = invocation.split()[0].rstrip(",")
            entries[flag] = (invocation, [m.group(2).strip()] if m.group(2) else [])
            current = flag
        elif current is not None and line.startswith("    ") and line.strip():
            entries[current][1].append(line.strip())
        else:
            current = None
    return {flag: (inv, " ".join(" ".join(parts).split())) for flag, (inv, parts) in entries.items()}


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def outs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("s28-reports")


@pytest.fixture(scope="module")
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One store holding every builder-made pair of spec section 0.7 plus this oracle's two
    synthetic pairs: the axes pair, the identical pair, the BH pair, the gate fixture, the
    multi-event pair (``crash`` carried outside ``t0`` so the CLI admits the event), the one-value
    pair, the empty family, the fixed-third-key pair, the vocabulary pair and the hostile pair."""
    root = tmp_path_factory.mktemp("s28-synth")
    store = Store(root)
    write_run(store, "axes-a", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(False))
    write_run(store, "axes-b", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    write_run(store, "same-a", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    write_run(store, "same-b", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    ba, bb = bh_cells(8, 1)
    write_run(store, "bh-a", salt=BH_SALT, axis_types=BH_TYPES, cells=ba)
    write_run(store, "bh-b", salt=BH_SALT, axis_types=BH_TYPES, cells=bb)
    ga, gb = gate_cells()
    write_run(store, "gate-a", salt=SALT, axis_types=GATE_TYPES, cells=ga)
    write_run(store, "gate-b", salt=SALT, axis_types=GATE_TYPES, cells=gb)
    me_a, me_b = multi_event_cells(True)
    write_run(store, "me-a", salt=SALT, axis_types=ME_TYPES, cells=me_a)
    write_run(store, "me-b", salt=SALT, axis_types=ME_TYPES, cells=me_b)
    write_run(store, "ov-a", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=one_value_cells(False))
    write_run(store, "ov-b", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=one_value_cells(True))
    write_run(store, "empty-a", salt=SALT, axis_types={"task": "categorical"}, cells={(("task", "only-a"),): ["fail"] * 4 + ["ok"] * 4})
    write_run(store, "empty-b", salt=OTHER_SALT, axis_types={"task": "categorical"}, cells={(("task", "only-b"),): ["fail"] * 4 + ["ok"] * 4})
    write_run(store, "three-a", salt=SALT, axis_types=THREE_KEY_TYPES, cells=three_key_cells(False))
    write_run(store, "three-b", salt=SALT, axis_types=THREE_KEY_TYPES, cells=three_key_cells(True))
    write_run(store, "vocab-a", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=two_value_cells(VOCABULARY_VALUES, False))
    write_run(store, "vocab-b", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=two_value_cells(VOCABULARY_VALUES, True))
    write_run(store, "hostile-a", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=two_value_cells((HOSTILE_VALUE, PLAIN_VALUE), False))
    write_run(store, "hostile-b", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=two_value_cells((HOSTILE_VALUE, PLAIN_VALUE), True))
    write_run(store, "overlap-a", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=overlap_cells(0))
    write_run(store, "overlap-b", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=overlap_cells(1))
    hg_a, hg_b = hostile_group_cells()
    write_run(store, "hgroup-a", salt=SALT, axis_types=HOSTILE_GROUP_TYPES, cells=hg_a)
    write_run(store, "hgroup-b", salt=SALT, axis_types=HOSTILE_GROUP_TYPES, cells=hg_b)
    return root


@pytest.fixture(scope="module")
def quickstart(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """The two quickstart runs of the mock agent under the S12 salt, as ``test_m10_multi.py``
    makes them: ``t_unit`` ``tool_calls``, a trade line under two events."""
    root = tmp_path_factory.mktemp("s28-quickstart")

    def sweep(target: str, *extra: str) -> str:
        code, out, err = run_cli(["--store", str(root), "sweep", str(QUICKSTART), "--target", target, "--yes", *extra])
        assert code == 0, out + err
        last = out.strip().splitlines()[-1]
        assert last.startswith("run_id: "), out
        return last.split("run_id: ", 1)[1]

    a = sweep(ROLLOUT, "--salt", QUICKSTART_SALT)
    b = sweep(PATCHED, "--pair-with", a)
    return root, a, b


#: Every section 0.7 pair the CLI reaches, as ``(name, run a, run b, event flags, axis flags,
#: extra flags, requested key)``; Go1 and the quickstart pair are added by the fixtures.
def synth_pairs(root: Path) -> list[tuple[str, Path, str, str, tuple[str, ...], tuple[str, ...], tuple[str, ...], str | None]]:
    return [
        ("axes", root, "axes-a", "axes-b", ("--event", "fail"), ("--x", "temp", "--y", "task"), (), None),
        ("identical", root, "same-a", "same-b", ("--event", "fail"), ("--x", "temp", "--y", "task"), (), None),
        ("bh", root, "bh-a", "bh-b", ("--event", "fail"), ("--x", "grp", "--y", "cell"), ("--method", "mcnemar_bh", "--by", "grp"), "grp"),
        ("gate", root, "gate-a", "gate-b", ("--event", "fail"), ("--x", "grp", "--y", "cell"), ("--method", "mcnemar_bh", "--by", "grp"), "grp"),
        ("multi-event", root, "me-a", "me-b", ("--event", "fail", "--event", "crash"), ("--x", "task", "--y", "temp"), (), None),
        ("one-value", root, "ov-a", "ov-b", ("--event", "fail"), ("--x", "task", "--y", "temp"), (), None),
    ]


def knobs_of(extra: Sequence[str]) -> dict[str, Any]:
    """The ``tree`` keywords a CLI argv's extra flags imply."""
    out: dict[str, Any] = {}
    flags = list(extra)
    for i, flag in enumerate(flags):
        if flag == "--by":
            out["by"] = flags[i + 1]
        elif flag == "--depth":
            out["depth"] = int(flags[i + 1])
        elif flag == "--permutations":
            out["n_permutations"] = int(flags[i + 1])
        elif flag == "--seed":
            out["seed"] = int(flags[i + 1])
        elif flag == "--max-group-mde":
            out["max_group_mde"] = float(flags[i + 1])
    return out


def method_of(extra: Sequence[str]) -> str:
    flags = list(extra)
    return flags[flags.index("--method") + 1] if "--method" in flags else "fisher_bh"


def events_of(event_flags: Sequence[str]) -> tuple[str, ...]:
    return tuple(event_flags[i + 1] for i, f in enumerate(event_flags) if f == "--event")


@pytest.fixture(scope="module")
def every_pair(outs: Path, synth_root: Path, quickstart: tuple[Path, str, str]) -> list[tuple[str, Rendered, Any, str | None]]:
    """Every section 0.7 pair rendered through ``main()`` with no tree flag, beside the tree the
    API grows on the same frames and knobs: ``(name, rendered, tree, requested)``."""
    qroot, qa, qb = quickstart
    rows = [
        ("go1", GO1_ROOT, GO1_A, GO1_B, ("--event", "fell"), ("--x", "mu", "--y", "push_pct_bw"), (), None),
        *synth_pairs(synth_root),
        ("quickstart", qroot, qa, qb, ("--event", "violated"), ("--x", "tool_fail_rate", "--y", "task_id"), (), None),
        ("quickstart-2", qroot, qa, qb, ("--event", "violated", "--event", "timeout"), ("--x", "tool_fail_rate", "--y", "task_id"), (), None),
    ]
    out = []
    for name, root, a, b, ev, axes, extra, requested in rows:
        r = ok(outs, root, a, b, *ev, *axes, *extra)
        _, result = store_tree(root, a, b, events=events_of(ev), method=method_of(extra), **knobs_of(extra))
        out.append((name, r, result, requested))
    return out


# ---------- R1: literals ----------


def test_r1_the_headings_the_field_the_keyword_the_reasons_and_the_public_names_are_the_literals() -> None:
    """The four headings are ``## Omnibus``, ``## Fault lines``, ``## Cells``, ``## Bound`` (and
    the same four words in ``<h2>`` on the receipt); ``MultiReport`` has a field ``tree``
    defaulting to ``None``; ``build_multi_report`` accepts ``tree`` as a keyword defaulting to
    ``None`` and its other parameters are unchanged (``inspect.signature`` against this file's
    literal); the reason mapping is a module-level ``dict`` literal whose keys are exactly the
    four; every kind the table names is one ``_fmt`` accepts; no public name beyond the base
    commit's is added to ``proofload.report``."""
    m = report_module()
    fields = {f.name: f for f in dataclasses.fields(m.MultiReport)}
    assert "tree" in fields and fields["tree"].default is None, sorted(fields)
    assert str(inspect.signature(m.build_multi_report)) == BUILD_MULTI_REPORT_SIGNATURE
    module = parsed(REPORT_SOURCE)
    mappings = [name for name, keys in string_dicts(module) if keys == set(REASONS)]
    assert len(mappings) == 1, (mappings, string_dicts(module))
    for kind in KINDS:
        assert fmt(0.5, kind) if kind != "int" else fmt(1, kind)
    public = {n for n in bound_names(module) if not n.startswith("_")}
    assert public == set(PUBLIC_NAMES_AT_BASE), sorted(public ^ set(PUBLIC_NAMES_AT_BASE))
    assert HEADINGS == ("Omnibus", "Fault lines", "Cells", "Bound") and MD_HEADINGS[0] == "## Omnibus" and HTML_HEADINGS[3] == "<h2>Bound</h2>"


def test_r1_the_four_headings_render_as_the_literals_in_both_renderers(every_pair: Any) -> None:
    for name, r, _, _ in every_pair:
        md_lines, html_lines = r.md.splitlines(), r.html.splitlines()
        assert [h for h in md_lines if h in MD_HEADINGS] == list(MD_HEADINGS), name
        assert [h for h in html_lines if h in HTML_HEADINGS] == list(HTML_HEADINGS), name


# ---------- R2: the tree-less bytes do not move; the with-tree bytes are pinned here ----------


def test_r2_the_tree_less_builder_reproduces_s21s_three_digests_and_the_svg_still_does_through_the_cli(outs: Path) -> None:
    """The first clause points one way: ``build_multi_report`` with no tree on the E14 argv's
    ``multi`` and spec renders S21's bytes -- markdown, SVG, light receipt -- bit for bit, and
    the CLI's ``heatmap.svg`` still digests to S21's literal (spec section 3.3: the SVG never
    changes). A builder who touches the SVG, the panel honesty or the worst-cells table fails
    here alone."""
    report = built(GO1_ROOT, GO1_A, GO1_B, events=("fell",), x="mu", y="push_pct_bw", with_tree=False)
    light = built(GO1_ROOT, GO1_A, GO1_B, events=("fell",), x="mu", y="push_pct_bw", with_tree=False, theme="light")
    assert sha256_of_text(report.to_markdown()) == E14_SHA256["report.md"]
    assert sha256_of_text(report.to_svg()) == E14_SHA256["heatmap.svg"]
    assert sha256_of_text(light.to_html()) == E14_SHA256["receipt.html"]
    r = ok(outs, GO1_ROOT, *E14_ARGV[1:])
    assert sha256_of_text(r.svg) == E14_SHA256["heatmap.svg"]


def test_r2_the_clis_report_and_receipt_with_the_tree_digest_to_the_values_minted_on_the_shim(outs: Path) -> None:
    """The second clause points the other way: the CLI's ``report.md`` and ``receipt.html`` on
    the E14 argv, the tree at the default knobs, digest to the values this oracle minted on
    Session A's shim, which Session B reproduces (module docstring: the section templates)."""
    r = ok(outs, GO1_ROOT, *E14_ARGV[1:])
    assert sha256_of_text(r.md) == E14_WITH_TREE_SHA256["report.md"]
    assert sha256_of_text(r.html) == E14_WITH_TREE_SHA256["receipt.html"]


# ---------- R3: the addition is additive ----------


def test_r3_excising_the_four_sections_by_index_gives_the_tree_less_render_on_every_pair(every_pair: Any, synth_root: Path) -> None:
    """On every fixture, the markdown with the lines from ``## Omnibus`` up to the line before the
    figure removed equals the tree-less markdown byte for byte; the receipt with the lines from
    ``<h2>Omnibus</h2>`` up to the figure ``div`` removed equals the tree-less receipt; the four
    headings appear once each, in order, inside that span and nowhere else. Found by index,
    never by the tail."""
    for name, r, _, _ in every_pair:
        tree_less = _tree_less_for(name, synth_root)
        assert excised(r.md, md_bounds(r.md)) == tree_less.to_markdown(), name
        assert excised(r.html, html_bounds(r.html)) == tree_less.to_html(), name
        sections(r.md, "md")
        sections(r.html, "html")


_TREE_LESS_ARGS = {
    "go1": (GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", "fisher_bh"),
    "axes": (None, "axes-a", "axes-b", ("fail",), "temp", "task", "fisher_bh"),
    "identical": (None, "same-a", "same-b", ("fail",), "temp", "task", "fisher_bh"),
    "bh": (None, "bh-a", "bh-b", ("fail",), "grp", "cell", "mcnemar_bh"),
    "gate": (None, "gate-a", "gate-b", ("fail",), "grp", "cell", "mcnemar_bh"),
    "multi-event": (None, "me-a", "me-b", ("fail", "crash"), "task", "temp", "fisher_bh"),
    "one-value": (None, "ov-a", "ov-b", ("fail",), "task", "temp", "fisher_bh"),
}
_QUICKSTART_TREE_LESS: dict[str, Any] = {}


def _tree_less_for(name: str, synth_root: Path) -> Any:
    if name.startswith("quickstart"):
        return _QUICKSTART_TREE_LESS[name]
    root, a, b, events, x, y, method = _TREE_LESS_ARGS[name]
    return built(root or synth_root, a, b, events=events, x=x, y=y, with_tree=False, method=method, theme="light")


@pytest.fixture(scope="module", autouse=True)
def _quickstart_tree_less(quickstart: tuple[Path, str, str]) -> None:
    root, a, b = quickstart
    _QUICKSTART_TREE_LESS["quickstart"] = built(root, a, b, events=("violated",), x="tool_fail_rate", y="task_id", with_tree=False, theme="light")
    _QUICKSTART_TREE_LESS["quickstart-2"] = built(root, a, b, events=("violated", "timeout"), x="tool_fail_rate", y="task_id", with_tree=False, theme="light")


def test_r3_the_receipts_stylesheet_and_everything_outside_the_span_is_the_tree_less_renders(every_pair: Any) -> None:
    """The light receipt's ``<style>`` and every line outside the span are bytes the tree-less
    render already produced (R20's "no style of their own" from the other side)."""
    for name, r, _, _ in every_pair:
        start, end = html_bounds(r.html)
        lines = r.html.splitlines()
        assert any(line.startswith("<style>") for line in lines[:start]), name
        assert not any("<style" in line for line in lines[start:end]), name


# ---------- R4: every number is a field, formatted once ----------


def test_r4_every_numeric_token_in_the_four_sections_is_a_field_under_the_kind_table_and_every_layout_field_is_printed(every_pair: Any) -> None:
    """The token rule. For each fixture the expected set is rebuilt from the ``TreeResult`` and
    the kind table -- never read back from the page -- and every numeric token of the four
    sections, on both surfaces, is in it: ``_fmt(field, kind)`` under the kind section 3.6
    assigns, the ``int`` of a count, a numeric token of a config value, a label, an event name,
    the verbatim ``headline()`` or a verbatim ``detail``, or the rule's ``2``. The bound
    section's assumption line, free text that carries a citation, is the one line skipped
    (module docstring). Then every field the layout names is present. A second formatter, a
    flat ``q``, a ``p`` alone, an interval, a colour bound, or ``delta`` under ``:g`` or
    ``sig3`` fails here."""
    for name, r, result, requested in every_pair:
        allowed, required = expected_tokens(result, requested=requested)
        for kind, text in (("md", r.md), ("html", r.html)):
            secs = sections(text, kind)
            found: set[str] = set()
            for heading, items in secs.items():
                toks = tokens_of(items, skip_last_line=heading == "Bound")
                stray = [t for t in toks if t not in allowed]
                assert stray == [], (name, kind, heading, stray)
                found.update(toks)
            missing = sorted(required - found)
            assert missing == [], (name, kind, missing)


def test_r4_the_kind_table_names_only_fields_that_exist_and_prints_delta_in_points(every_pair: Any) -> None:
    """Every field the table attributes to a structure exists on it (the table is stated in two
    specs, S28 and S29, and a field that does not exist is caught here or on the page); and on
    Go1 a rejected leaf's delta prints in points at one decimal, not the fraction ``diff`` prints."""
    t = tree()
    for structure, field, _ in KIND_TABLE:
        assert field in {f.name for f in dataclasses.fields(getattr(t, structure))}, (structure, field)
    go1 = next(row for row in every_pair if row[0] == "go1")
    _, r, result, _ = go1
    leaf = next(c for f in result.leaves.families for c in f.cells if c.rejects)
    cells = sections(r.md, "md")["Cells"]
    rows = [row for _, rows in tables_of(cells) for row in rows]
    assert any(row[2] == fmt(leaf.delta, "pp1") for row in rows), (fmt(leaf.delta, "pp1"), rows[:3])
    assert not any(row[2] == g(leaf.delta) for row in rows if row[1] == leaf.event and row[0] == config_text(leaf.config))


# ---------- R5: the omnibus section ----------


def omnibus_items(r: Rendered, kind: str) -> list[tuple[Any, ...]]:
    return sections(r.md if kind == "md" else r.html, kind)["Omnibus"]


def test_r5_the_omnibus_prints_the_headline_verbatim_the_method_line_one_row_per_event_and_the_informative_line(every_pair: Any) -> None:
    """First line ``root.headline()`` verbatim; a line carrying ``scheme``, ``n_permutations``
    and ``seed``; one table with one row per event in ``root.events`` order whose cells are the
    event, ``location[e]``, ``p_location[e]``, ``dispersion[e]``, ``p_dispersion[e]`` (identity
    under any M7 kind; the kind is R4's); a line carrying ``n_informative_cells``, ``n_cells``
    and ``n_uninformative_cells``. Both surfaces."""
    for name, r, result, _ in every_pair:
        root = result.root
        for kind in ("md", "html"):
            items = omnibus_items(r, kind)
            lines, tables = lines_of(items), tables_of(items)
            assert lines[0] == root.headline(), (name, kind, lines[0])
            assert any(root.scheme in line and has(line, root.n_permutations) and has(line, root.seed) for line in lines[1:]), (name, kind, lines)
            assert len(tables) == 1, (name, kind, len(tables))
            header, rows = tables[0]
            assert len(header) == 5 and [row[0] for row in rows] == list(root.events), (name, kind, header, rows)
            for row, event in zip(rows, root.events, strict=True):
                assert len(row) == 5, (name, kind, row)
                for cell, value in zip(row[1:], (root.location[event], root.p_location[event], root.dispersion[event], root.p_dispersion[event]), strict=True):
                    assert renders(cell, value), (name, kind, event, cell, value)
            assert any(
                has(line, root.n_informative_cells) and has(line, root.n_cells) and has(line, root.n_uninformative_cells) for line in lines[1:]
            ), (name, kind, lines)


def test_r5_the_identical_pair_reads_is_not_rejected_and_go1_reads_is_rejected(every_pair: Any) -> None:
    by_name = {name: (r, result) for name, r, result, _ in every_pair}
    r, result = by_name["identical"]
    assert not result.root.rejects
    assert "is not rejected" in lines_of(omnibus_items(r, "md"))[0]
    r, result = by_name["go1"]
    assert result.root.rejects
    first = lines_of(omnibus_items(r, "md"))[0]
    assert "is rejected" in first and f'"{ROOT_NULL}"' in first


# ---------- R6: the fault-lines section ----------


def fault_items(r: Rendered, kind: str) -> list[tuple[Any, ...]]:
    return sections(r.md if kind == "md" else r.html, kind)["Fault lines"]


def group_row_width(result: Any) -> int:
    return 6 + (1 if result.root.scheme == "pair_swap" else 0) + (3 if result.fault_lines.tested else 0)


def assert_fault_lines(name: str, kind: str, items: Sequence[tuple[Any, ...]], result: Any) -> None:
    grouping, fault, root = result.grouping, result.fault_lines, result.root
    lines, tables = lines_of(items), tables_of(items)
    head = lines[0]
    assert f"{grouping.key} ({grouping.resolved_by})" in head, (name, kind, head)
    for value in (grouping.n_groups, grouping.size_min, grouping.size_median, grouping.size_max, fault.n_degenerate_groups, grouping.n_resolvable_groups, grouping.max_group_mde, grouping.alpha_floor):
        assert has(head, value), (name, kind, head, value)
    refusals = lines[1 : 1 + len(grouping.refused)]
    assert len(refusals) == len(grouping.refused), (name, kind, lines)
    for line, refusal in zip(refusals, grouping.refused, strict=True):
        for piece in (refusal.key, refusal.rung, refusal.reason, refusal.detail, refusal.next_rung):
            assert piece in line, (name, kind, piece, line)
    null = lines[1 + len(grouping.refused)]
    assert f'"{GROUP_NULL}"' in null, (name, kind, null)
    if fault.tested:
        assert "tested by BH across" in null and has(null, fault.n_groups) and has(null, fault.q) and has(null, fault.n_rejected_groups) and "rejected" in null, (name, kind, null)
    elif fault.reason == "root_not_rejected":
        assert "not tested" in null and "the root did not reject" in null, (name, kind, null)
    else:
        assert fault.reason == "one_group" and "not tested" in null and "one group is the whole family restated" in null, (name, kind, null)
    assert len(tables) == 1, (name, kind, len(tables))
    header, rows = tables[0]
    width = group_row_width(result)
    assert len(header) == width, (name, kind, header, width)
    assert [row[0] for row in rows] == list(grouping.labels), (name, kind, [row[0] for row in rows][:5])
    for row, group in zip(rows, fault.groups, strict=True):
        assert len(row) == width and row[0] == group.label, (name, kind, row)
        for cell, value in zip(row[1:4], (group.n_cells, group.n_informative_cells, group.n_uninformative_cells), strict=True):
            assert cell == fmt(value, "int"), (name, kind, row, cell, value)
        assert row[4] == f"{fmt(group.n_a, 'int')}/{fmt(group.n_b, 'int')}", (name, kind, row)
        assert renders(row[5], group.mde), (name, kind, row)
        rest = row[6:]
        if root.scheme == "pair_swap":
            assert rest[0] == fmt(group.n_discordant, "int"), (name, kind, row)
            rest = rest[1:]
        if fault.tested:
            assert renders(rest[0], group.p_group) and renders(rest[1], group.q_group), (name, kind, row)
            assert rest[2] == ("rejected" if group.rejects else "not rejected"), (name, kind, row)
        else:
            assert rest == [], (name, kind, row)


def test_r6_the_fault_lines_print_the_head_the_chain_the_null_and_one_row_per_group_in_labels_order(every_pair: Any) -> None:
    """The head line's ten fields; one refusal line per ``Refusal`` in chain order carrying
    ``key``, ``rung``, ``reason``, ``detail`` verbatim and ``next_rung``; the null line; one row
    per group in ``labels`` order with the columns of the module docstring, the discordant
    column iff ``pair_swap`` and the ``p``, ``q``, verdict columns iff the level was tested."""
    for name, r, result, _ in every_pair:
        for kind in ("md", "html"):
            assert_fault_lines(name, kind, fault_items(r, kind), result)


def test_r6_on_go1_by_mu_the_row_for_0_95_is_the_nineteenth_of_twenty_and_not_rejected(every_pair: Any) -> None:
    """A sort by verdict moves it; ``labels`` order keeps it. And no ``p`` column exists on the
    identical pair, where the level was not tested."""
    by_name = {name: (r, result) for name, r, result, _ in every_pair}
    r, result = by_name["go1"]
    header, rows = tables_of(fault_items(r, "md"))[0]
    assert len(rows) == GO1_MU_GROUPS and result.grouping.key == "mu"
    assert rows[18][0] == GO1_MU_NINETEENTH_LABEL and rows[18][-1] == "not rejected", rows[18]
    assert sum(row[-1] == "rejected" for row in rows) == GO1_MU_REJECTED
    r, result = by_name["identical"]
    header, rows = tables_of(fault_items(r, "md"))[0]
    assert not result.fault_lines.tested and len(header) == 6 and all(len(row) == 6 for row in rows), header


def test_r6_the_axes_pair_carries_the_override_inside_detail_the_one_value_pair_two_refusals_and_by_kind_an_unsupported_line(every_pair: Any, outs: Path) -> None:
    by_name = {name: (r, result) for name, r, result, _ in every_pair}
    r, result = by_name["axes"]
    refused = [x for x in result.grouping.refused if x.key == "task"]
    assert len(refused) == 1 and refused[0].reason == "underpowered" and refused[0].offered_max_group_mde is not None
    line = lines_of(fault_items(r, "md"))[1]
    assert refused[0].detail in line and g(refused[0].offered_max_group_mde) in refused[0].detail, (line, refused[0].detail)
    r, result = by_name["one-value"]
    assert [x.reason for x in result.grouping.refused] == ["underpowered", "one_group"], result.grouping.refused
    lines = lines_of(fault_items(r, "md"))
    assert "underpowered" in lines[1] and "one_group" in lines[2], lines[:3]
    r = ok(outs, GO1_ROOT, GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--by", "kind")
    _, result = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",), by="kind")
    assert [(x.key, x.rung, x.reason) for x in result.grouping.refused] == [("kind", "trace", "unsupported")]
    line = lines_of(fault_items(r, "md"))[1]
    assert "kind" in line and "trace" in line and "unsupported" in line, line
    assert_fault_lines("go1-kind", "md", fault_items(r, "md"), result)


# ---------- R7: the cells section ----------


def cells_items(r: Rendered, kind: str) -> list[tuple[Any, ...]]:
    return sections(r.md if kind == "md" else r.html, kind)["Cells"]


def assert_cells(name: str, kind: str, items: Sequence[tuple[Any, ...]], result: Any) -> None:
    leaves, bound = result.leaves, result.bound
    lines, tables = lines_of(items), tables_of(items)
    head = lines[0]
    if leaves.tested:
        assert f'"{CELL_NULL}"' in head and "tested by BH" in head, (name, kind, head)
        for value in (leaves.n_families, leaves.n_tests, leaves.n_rejected, leaves.q):
            assert has(head, value), (name, kind, head, value)
    else:
        assert "not tested" in head, (name, kind, head)
        forms = {
            "depth": "depth" in head and has(head, bound.depth_configured),
            "root_not_rejected": "the root did not reject" in head,
            "no_group_rejected": "no group rejected" in head,
        }
        assert [k for k, v in forms.items() if v] == [leaves.reason], (name, kind, head, leaves.reason)
        assert lines[1:] == [] and tables == [], (name, kind, lines, len(tables))
        return
    assert leaves.families, (name, kind)
    meaning = lines[1]
    assert "increase" in meaning.lower() and "headroom" in meaning.lower() and numeric_tokens(meaning) == [], (name, kind, meaning)
    family_lines = lines[2:]
    assert len(family_lines) == len(leaves.families), (name, kind, family_lines)
    expected_tables = [f for f in leaves.families if f.n_rejected > 0]
    assert len(tables) == len(expected_tables), (name, kind, len(tables), len(expected_tables))
    table_iter = iter(tables)
    for line, family in zip(family_lines, leaves.families, strict=True):
        assert f"{family.key}={family.label}" in line, (name, kind, line)
        for value in (family.n_tests, family.n_rejected, family.mde_median, family.mde_max):
            assert has(line, value), (name, kind, line, value)
        if family.n_rejected == 0:
            continue
        header, rows = next(table_iter)
        assert len(header) == 5, (name, kind, header)
        rejected = [c for c in family.cells if c.rejects]
        assert len(rows) == len(rejected) == family.n_rejected, (name, kind, family.label, len(rows), family.n_rejected)
        for row, leaf in zip(rows, rejected, strict=True):
            assert len(row) == 5 and row[0] == config_text(leaf.config) and row[1] == leaf.event, (name, kind, row, leaf.config)
            for cell, value in zip(row[2:], (leaf.delta, leaf.q_within, leaf.mde), strict=True):
                assert renders(cell, value), (name, kind, row, cell, value)


def test_r7_the_cells_section_prints_the_head_the_meaning_sentence_one_family_line_per_family_and_one_row_per_rejected_leaf(every_pair: Any) -> None:
    """The head with ``n_families``, ``n_tests``, ``n_rejected``, ``q`` and the quoted null when
    tested, or exactly one of the three untested forms and nothing else; the MDE-meaning
    sentence, with no number, when any family exists; one family line per family in
    ``families`` order carrying ``key=label``, ``n_tests``, ``n_rejected``, ``mde_median``,
    ``mde_max``; under it, iff ``n_rejected > 0``, one row per rejected leaf in ``cells`` order
    carrying every ``key=value`` of ``config``, ``event``, ``delta``, ``q_within``, ``mde``; no
    row for a leaf with ``rejects`` False. Both surfaces."""
    for name, r, result, _ in every_pair:
        for kind in ("md", "html"):
            assert_cells(name, kind, cells_items(r, kind), result)


def test_r7_the_axes_pair_prints_one_family_line_reading_0_rejected_and_no_table(every_pair: Any) -> None:
    by_name = {name: (r, result) for name, r, result, _ in every_pair}
    r, result = by_name["axes"]
    assert result.leaves.tested and len(result.leaves.families) == 1 and result.leaves.n_rejected == 0
    items = cells_items(r, "md")
    assert tables_of(items) == [] and len(lines_of(items)) == 3, lines_of(items)
    assert has(lines_of(items)[2], 0) and "rejected" in lines_of(items)[2]


def test_r7_on_go1_by_push_family_70_follows_cells_order_and_its_q_tokens_are_not_sorted(outs: Path) -> None:
    r = ok(outs, GO1_ROOT, GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--by", "push_pct_bw")
    _, result = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",), by="push_pct_bw")
    assert_cells("go1-push", "md", cells_items(r, "md"), result)
    families = {f.label: f for f in result.leaves.families}
    seventy = families[GO1_PUSH_UNSORTED_FAMILY]
    rejected = [c for c in seventy.cells if c.rejects]
    assert len(rejected) == 13
    q_tokens = [fmt(c.q_within, "sig3") for c in rejected]
    assert q_tokens != sorted(q_tokens, key=float), q_tokens
    tables = tables_of(cells_items(r, "md"))
    index = [f for f in result.leaves.families if f.n_rejected > 0].index(seventy)
    header, rows = tables[index]
    assert [row[3] for row in rows] == q_tokens, rows
    assert [f.n_rejected for f in result.leaves.families] == list(GO1_PUSH_FAMILIES)


def test_r7_on_a_pair_with_a_fixed_third_key_every_leaf_row_carries_every_config_key(outs: Path, synth_root: Path) -> None:
    """The tree is the family's and ``--fix`` slices only the figure: with ``model`` fixed to
    ``m1`` on the page, the leaf rows carry ``model=m1`` and ``model=m2`` alike, every key of
    each config. A builder who prints only the grid's two axes fails here alone."""
    r = ok(outs, synth_root, "three-a", "three-b", "--event", "fail", "--x", "task", "--y", "temp", "--fix", 'model="m1"')
    _, result = store_tree(synth_root, "three-a", "three-b", events=("fail",))
    assert result.leaves.tested and result.leaves.n_rejected == 8, (result.leaves.tested, result.leaves.n_rejected)
    for kind in ("md", "html"):
        assert_cells("three-key", kind, cells_items(r, kind), result)
        rows = [row for _, rows in tables_of(cells_items(r, kind)) for row in rows]
        assert len(rows) == 8 and all("model=" in row[0] and "temp=" in row[0] and "task=" in row[0] for row in rows), rows
        assert {m for row in rows for m in THREE_KEY_MODELS if f"model={m}" in row[0]} == set(THREE_KEY_MODELS), rows


def test_r7_on_the_multi_event_pair_family_t0_has_two_fail_rows_and_no_crash_row(every_pair: Any) -> None:
    by_name = {name: (r, result) for name, r, result, _ in every_pair}
    r, result = by_name["multi-event"]
    assert [f.label for f in result.leaves.families] == ["t0"] and result.root.events == ("fail", "crash")
    header, rows = tables_of(cells_items(r, "md"))[0]
    assert [row[1] for row in rows] == ["fail", "fail"], rows


# ---------- R8: the bound section ----------


def bound_items(r: Rendered, kind: str) -> list[tuple[Any, ...]]:
    return sections(r.md if kind == "md" else r.html, kind)["Bound"]


def assert_bound(name: str, kind: str, items: Sequence[tuple[Any, ...]], result: Any) -> None:
    bound = result.bound
    lines, tables = lines_of(items), tables_of(items)
    assert tables == [] and len(lines) == 2, (name, kind, lines)
    rule, assumption = lines
    for value in (bound.depth, bound.depth_configured, bound.bound, bound.q, bound.delta_star):
        assert has(rule, value), (name, kind, rule, value)
    assert "outer-nodes" in rule and "false discovery rate" in rule, (name, kind, rule)
    assert assumption, (name, kind)
    assert any(word in assumption.lower() for word in ("assum", "independen")), (name, kind, assumption)


def test_r8_the_bound_section_prints_the_rule_line_and_the_assumption_line_on_every_pair(every_pair: Any) -> None:
    """``depth``, ``depth_configured``, ``bound``, ``q``, ``delta_star``, the words
    ``outer-nodes`` and ``false discovery rate``, then the assumption line; both print on the
    identical pair, where nothing rejected."""
    for name, r, result, _ in every_pair:
        for kind in ("md", "html"):
            assert_bound(name, kind, bound_items(r, kind), result)
    by_name = {name: (r, result) for name, r, result, _ in every_pair}
    r, result = by_name["identical"]
    assert not result.root.rejects and len(lines_of(bound_items(r, "md"))) == 2


def test_r8_go1_at_depth_2_prints_0_288_with_the_depth_form_and_by_grid_prints_0_288_at_depth_2_of_3(outs: Path) -> None:
    r = ok(outs, GO1_ROOT, GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--depth", "2")
    _, result = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",), depth=2)
    rule = lines_of(bound_items(r, "md"))[0]
    assert BOUND_AT_DEPTH_2 in rule and fmt(result.bound.bound, "sig3") == BOUND_AT_DEPTH_2, rule
    assert result.leaves.reason == "depth" and "not tested" in lines_of(cells_items(r, "md"))[0] and "depth" in lines_of(cells_items(r, "md"))[0]
    assert_bound("go1-d2", "md", bound_items(r, "md"), result)
    r = ok(outs, GO1_ROOT, GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--by", "grid")
    _, result = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",), by="grid")
    rule = lines_of(bound_items(r, "md"))[0]
    assert (result.bound.depth, result.bound.depth_configured) == (2, 3) and BOUND_AT_DEPTH_2 in rule, rule
    assert_bound("go1-grid", "md", bound_items(r, "md"), result)
    default = ok(outs, GO1_ROOT, *E14_ARGV[1:])
    assert BOUND_AT_DEPTH_3 in lines_of(bound_items(default, "md"))[0]


# ---------- R9: reasons on the rendered surface, in M14's precedence ----------


def test_r9_the_reasons_read_in_m14s_precedence_on_the_identical_bh_and_grid_fixtures(every_pair: Any, outs: Path, synth_root: Path) -> None:
    """Identical pair at ``--depth 3``: fault lines and cells both read the root sentence; at
    ``--depth 2``: cells read the ``depth`` form (configuration before root); Go1 at ``--depth
    2``: ``depth``; BH pair by ``grp`` under McNemar: ``no group rejected``; Go1 ``--by grid``:
    the one-group sentence on the fault lines and a family ``whole_grid=all`` on the cells."""
    by_name = {name: (r, result) for name, r, result, _ in every_pair}
    r, result = by_name["identical"]
    assert result.fault_lines.reason == result.leaves.reason == "root_not_rejected"
    assert "the root did not reject" in lines_of(fault_items(r, "md"))[1 + len(result.grouping.refused)]
    assert "the root did not reject" in lines_of(cells_items(r, "md"))[0]
    r = ok(outs, synth_root, "same-a", "same-b", "--event", "fail", "--x", "temp", "--y", "task", "--depth", "2")
    _, result = store_tree(synth_root, "same-a", "same-b", events=("fail",), depth=2)
    assert result.leaves.reason == "depth" and not result.root.rejects
    head = lines_of(cells_items(r, "md"))[0]
    assert "depth" in head and has(head, 2) and "root" not in head, head
    r, result = by_name["bh"]
    assert result.leaves.reason == "no_group_rejected"
    assert "no group rejected" in lines_of(cells_items(r, "md"))[0]
    r, result = by_name["gate"]
    assert result.leaves.reason == "no_group_rejected" and "no group rejected" in lines_of(cells_items(r, "md"))[0]
    r = ok(outs, GO1_ROOT, GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--by", "grid")
    _, result = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",), by="grid")
    assert result.fault_lines.reason == "one_group"
    assert "one group is the whole family restated" in lines_of(fault_items(r, "md"))[1]
    assert f"{tree().WHOLE_GRID_KEY}={tree().WHOLE_GRID_LABEL}" in lines_of(cells_items(r, "md"))[2]


# ---------- R10: vocabulary ----------


def tree_strings(result: Any) -> list[str]:
    root, grouping, fault, leaves, bound = result.root, result.grouping, result.fault_lines, result.leaves, result.bound
    out = [root.headline(), root.scheme, grouping.key, grouping.resolved_by, grouping.requested or "", fault.reason or "", fault.null, leaves.reason or "", leaves.null, bound.discoveries]
    for refusal in grouping.refused:
        out.extend((refusal.key, refusal.rung, refusal.reason, refusal.detail, refusal.next_rung))
    out.extend(group.label for group in fault.groups)
    for family in leaves.families:
        out.extend((family.label, family.key))
        out.extend(c.event for c in family.cells)
    return out


def test_r10_no_section_line_and_no_tree_string_uses_the_forbidden_vocabulary_after_masking(every_pair: Any) -> None:
    """The requested key, every group label, every config value and every event name are
    masked first (they are user data); then the 24 phrases, case-insensitively, over every
    line and cell of the four sections on both surfaces and over every string the tree
    carries. The omnibus quotes the root null, the fault lines the group null, the cells the
    cell null when tested; the bound section contains ``outer-nodes`` and not ``fdr``."""
    for name, r, result, requested in every_pair:
        for text in tree_strings(result):
            low = masked(text, result, requested)
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in low, (name, phrase, text)
        for kind, page in (("md", r.md), ("html", r.html)):
            secs = sections(page, kind)
            joined = masked("\n".join(section_text(items) for items in secs.values()), result, requested)
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in joined, (name, kind, phrase)
            assert f'"{ROOT_NULL}"' in section_text(secs["Omnibus"]), (name, kind)
            assert f'"{GROUP_NULL}"' in section_text(secs["Fault lines"]), (name, kind)
            if result.leaves.tested:
                assert f'"{CELL_NULL}"' in section_text(secs["Cells"]), (name, kind)
            bound_text = section_text(secs["Bound"]).lower()
            assert "outer-nodes" in bound_text and "fdr" not in bound_text, (name, kind)


def test_r10_the_vocabulary_pair_renders_green_under_the_mask_and_red_without_it(outs: Path, synth_root: Path) -> None:
    """The proof that the mask is applied: a pair whose ``task`` values are ``given the root``
    and ``where it broke`` renders both values into the leaf rows; the masked check is green
    and the unmasked scan finds both phrases. A test whose mask is missing is red here."""
    r = ok(outs, synth_root, "vocab-a", "vocab-b", "--event", "fail", "--x", "task", "--y", "temp")
    _, result = store_tree(synth_root, "vocab-a", "vocab-b", events=("fail",))
    assert result.root.rejects and result.leaves.tested and result.leaves.n_rejected == 2, (result.root.rejects, result.leaves.n_rejected)
    for kind, page in (("md", r.md), ("html", r.html)):
        text = "\n".join(section_text(items) for items in sections(page, kind).values())
        unmasked = text.lower()
        assert all(v in unmasked for v in VOCABULARY_VALUES), (kind, text[:200])
        low = masked(text, result, None)
        for phrase in FORBIDDEN_VOCABULARY:
            assert phrase not in low, (kind, phrase)
        assert any(phrase in unmasked for phrase in FORBIDDEN_VOCABULARY)


# ---------- R11: the tree-rendering closure computes nothing ----------


def test_r11_the_closure_of_the_two_tree_renderers_has_no_arithmetic_no_formatter_no_spec_and_no_colour() -> None:
    """**The rule, in prose.** The closure of ``_tree_markdown`` and ``_tree_html`` -- the two
    functions plus every module-level function either reaches by name, transitively, never
    entering ``_fmt``, ``_md_table``, ``_html_table`` or ``_html_lines`` -- contains no
    arithmetic node under V17's rule (``-``, ``*``, ``/``, ``//``, ``%``, ``**``, any ``+=``, a
    unary minus, and ``+`` between two non-string operands), no ``format(``, ``.format(`` or
    ``round(`` call, no f-string field with a format spec of any kind, no ``* 100`` and no hex
    colour literal and none of the four bound literals as text in its source. The closure form,
    not ADR-072's file-wide form: ``report.py``'s
    geometry multiplies ``delta`` in ``_cell_fill`` and ``delta`` and ``mde`` in ``_forest_body``
    (the measured collision set, module docstring), and those are the two fields the leaf row
    prints, so a file-wide guard is red on the bare tree or excludes the names that matter most
    (spec section 0.4, draft ADR-075). ``_fmt`` is excluded because its ``* 100`` and ``format(``
    are the formatter itself; the three table and line helpers because they are M7's frozen
    renderers whose bytes the tree-less digests (R2) already pin."""
    module = parsed(REPORT_SOURCE)
    source = REPORT_SOURCE.read_text(encoding="utf-8")
    functions = module_functions(module)
    for root in TREE_ROOTS:
        assert root in functions, (root, sorted(n for n in functions if n.startswith("_tree")))
    nodes = closure(module, TREE_ROOTS, CLOSURE_EXCLUDED)
    assert {n.name for n in nodes} >= set(TREE_ROOTS)  # type: ignore[attr-defined]
    assert arithmetic_nodes(nodes) == [], [(n.lineno, ast.dump(n)[:60]) for n in arithmetic_nodes(nodes)]
    assert format_calls(nodes) == [], format_calls(nodes)
    assert format_specs(nodes) == [], format_specs(nodes)
    segment = source_of(source, nodes)
    assert not TIMES_100_RE.search(segment) and not FLOAT_SPEC_RE.search(segment) and not HEX_RE.search(segment)
    assert not BOUND_LITERAL_RE.search(segment), BOUND_LITERAL_RE.search(segment)


def test_r11_report_py_names_none_of_m14s_constants_and_carries_none_of_the_bound_literals() -> None:
    module = parsed(REPORT_SOURCE)
    names = mentioned(module)
    assert not (names & set(FORBIDDEN_TREE_NAMES)), sorted(names & set(FORBIDDEN_TREE_NAMES))
    found = [c for c in constants(module) if isinstance(c, float) and any(math.isclose(c, x, rel_tol=0, abs_tol=1e-12) for x in FORBIDDEN_BOUND_CONSTANTS)]
    assert found == [], found


# ---------- R12: no second reader of the reason tuples ----------


def test_r12_report_py_never_names_a_reason_tuple_and_the_mapping_is_a_literal_dict_of_the_four() -> None:
    module = parsed(REPORT_SOURCE)
    names = mentioned(module)
    assert not (names & set(REASON_TUPLE_NAMES)), sorted(names & set(REASON_TUPLE_NAMES))
    mappings = [name for name, keys in string_dicts(module) if keys == set(REASONS)]
    assert len(mappings) == 1, mappings


def test_r12_an_unknown_reason_raises_report_error_rather_than_printing(synth_root: Path) -> None:
    """``Leaves.reason`` and ``FaultLines.reason`` set to ``nonsense`` on the identical pair's
    tree: building or rendering raises ``ReportError`` and prints no page."""
    m = report_module()
    store = Store(synth_root)
    multi, result = store_tree(synth_root, "same-a", "same-b", events=("fail",))
    manifests = (store.manifest("same-a"), store.manifest("same-b"))
    spec = spec_for("same-a", "same-b", ("fail",), "temp", "task")
    for field in ("leaves", "fault_lines"):
        bad = dataclasses.replace(result, **{field: dataclasses.replace(getattr(result, field), reason="nonsense")})
        with pytest.raises(m.ReportError):
            rep = m.build_multi_report(multi, spec, manifests=manifests, tree=bad)
            rep.to_markdown()
        with pytest.raises(m.ReportError):
            rep = m.build_multi_report(multi, spec, manifests=manifests, tree=bad)
            rep.to_html()


# ---------- R13: the five flags reach the call ----------


def test_r13_report_help_lists_the_five_flags_with_diffs_help_text_for_each() -> None:
    code, report_help, err = run_cli(["report", "--help"])
    assert code == 0 and err == "", err
    code, diff_help, err = run_cli(["diff", "--help"])
    assert code == 0 and err == "", err
    report_entries, diff_entries = help_entries(report_help), help_entries(diff_help)
    for flag in TREE_FLAGS:
        assert flag in report_entries, (flag, sorted(report_entries))
        assert flag in diff_entries, (flag, sorted(diff_entries))
        assert report_entries[flag] == diff_entries[flag], (flag, report_entries[flag], diff_entries[flag])


def test_r13_the_five_flags_reach_the_call_on_the_axes_pair(outs: Path, synth_root: Path) -> None:
    r = ok(outs, synth_root, "axes-a", "axes-b", "--event", "fail", "--x", "temp", "--y", "task", "--by", "temp", "--max-group-mde", "0.6", "--depth", "2", "--permutations", "300", "--seed", "3")
    _, result = store_tree(synth_root, "axes-a", "axes-b", events=("fail",), by="temp", max_group_mde=0.6, depth=2, n_permutations=300, seed=3)
    assert result.grouping.key == "temp" and result.grouping.resolved_by == "requested"
    assert "temp (requested)" in lines_of(fault_items(r, "md"))[0]
    method_line = lines_of(omnibus_items(r, "md"))[1]
    assert has(method_line, 300) and has(method_line, 3) and not has(method_line, GOLDEN_PERMUTATIONS), method_line
    assert has(lines_of(bound_items(r, "md"))[0], 2) and result.bound.depth == 2
    assert_fault_lines("axes-flags", "md", fault_items(r, "md"), result)
    assert_cells("axes-flags", "md", cells_items(r, "md"), result)
    assert_bound("axes-flags", "md", bound_items(r, "md"), result)
    allowed, _ = expected_tokens(result, requested="temp")
    for heading, items in sections(r.md, "md").items():
        stray = [t for t in tokens_of(items, skip_last_line=heading == "Bound") if t not in allowed]
        assert stray == [], (heading, stray)


def test_r13_out_of_range_depths_and_refused_knobs_exit_2_with_error_on_stderr_and_no_file(tmp_path: Path, synth_root: Path) -> None:
    base = ["--store", str(synth_root), "report", "axes-a", "axes-b", "--event", "fail", "--x", "temp", "--y", "task"]
    for i, extra in enumerate((["--depth", "1"], ["--depth", "4"], ["--by", "nonsense"], ["--max-group-mde", "2"])):
        out = tmp_path / f"refused-{i}"
        code, stdout, stderr = run_cli([*base, *extra, "--out", str(out)])
        assert code == 2, (extra, code, stdout, stderr)
        assert "error:" in stderr and "Traceback" not in stdout + stderr, (extra, stderr)
        assert not out.exists() or not any(out.iterdir()), (extra, sorted(out.iterdir()))


def test_r13_the_single_run_form_refuses_each_of_the_five_as_a_diff_only_flag(tmp_path: Path, synth_root: Path) -> None:
    for i, flag in enumerate(TREE_FLAGS):
        out = tmp_path / f"single-{i}"
        code, stdout, stderr = run_cli(["--store", str(synth_root), "report", "axes-a", "--event", "fail", "--x", "temp", "--y", "task", flag, FLAG_VALUES[flag], "--out", str(out)])
        assert code == 2, (flag, code, stdout, stderr)
        assert flag in stderr and "diff-only flag" in stderr and "Traceback" not in stdout + stderr, (flag, stderr)
        assert not out.exists() or not any(out.iterdir()), flag


# ---------- R14: a pair's report always carries the tree ----------


def test_r14_every_pair_carries_the_four_sections_with_no_flag_and_the_empty_family_still_exits_2(every_pair: Any, tmp_path: Path, synth_root: Path) -> None:
    for name, r, _, _ in every_pair:
        assert all(h in r.md.splitlines() for h in MD_HEADINGS) and all(h in r.html.splitlines() for h in HTML_HEADINGS), name
    out = tmp_path / "empty"
    code, stdout, stderr = run_cli(["--store", str(synth_root), "report", "empty-a", "empty-b", "--event", "fail", "--x", "task", "--out", str(out)])
    assert code == 2 and "error:" in stderr and "Traceback" not in stdout + stderr, (code, stdout, stderr)
    assert not out.exists() or not any(out.iterdir())


def test_r14_under_methods_all_the_sections_appear_once_and_the_omnibus_names_the_primarys_scheme(outs: Path) -> None:
    r = ok(outs, GO1_ROOT, *E14_ARGV[1:], "--methods", "all")
    _, result = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",))
    assert result.root.scheme == "arm_label"
    secs = sections(r.md, "md")
    assert result.root.scheme in lines_of(secs["Omnibus"])[1] and "pair_swap" not in section_text(secs["Omnibus"])
    assert r.md.count("## Methods") == 1
    assert_fault_lines("go1-all", "md", secs["Fault lines"], result)


def test_r14_the_single_run_report_writes_none_of_the_four_headings_and_go1s_stdout_is_todays(outs: Path, synth_root: Path) -> None:
    single = rendered(outs, synth_root, "axes-b", "--event", "fail", "--x", "temp", "--y", "task")
    assert single.code == 0, single.text
    assert not any(h in single.md.splitlines() for h in MD_HEADINGS) and not any(h in single.html.splitlines() for h in HTML_HEADINGS)
    r = ok(outs, GO1_ROOT, *E14_ARGV[1:])
    multi, _ = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",))
    expected = multi.headline() + "\n" + "".join(f"{r.out_dir / name}\n" for name in ("report.md", "heatmap.svg", "receipt.html"))
    assert r.out == expected, (r.out, expected)


# ---------- R15: determinism ----------


def test_r15_identical_arguments_and_twin_stores_write_byte_identical_files(tmp_path: Path, synth_root: Path) -> None:
    """Two runs with identical arguments are byte-identical (I12 with the tree); the same pair
    written to two roots renders the same three files, so nothing in the sections echoes a
    store path (R5 of ``test_m4_read.py`` runs the same verb on its poisoned twin)."""
    digests = []
    for k in range(2):
        out = tmp_path / f"twice-{k}"
        code, stdout, stderr = run_cli(["--store", str(synth_root), "report", "me-a", "me-b", "--event", "fail", "--event", "crash", "--x", "task", "--y", "temp", "--methods", "all", "--out", str(out)])
        assert code == 0, stdout + stderr
        digests.append({name: sha256_of_text((out / name).read_text()) for name in ("report.md", "heatmap.svg", "receipt.html")})
    assert digests[0] == digests[1]
    twins = []
    for k in range(2):
        root = tmp_path / f"twin-{k}"
        store = Store(root)
        write_run(store, "ov-a", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=one_value_cells(False))
        write_run(store, "ov-b", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=one_value_cells(True))
        out = tmp_path / f"twin-out-{k}"
        code, stdout, stderr = run_cli(["--store", str(root), "report", "ov-a", "ov-b", "--event", "fail", "--x", "task", "--y", "temp", "--out", str(out)])
        assert code == 0, stdout + stderr
        twins.append({name: sha256_of_text((out / name).read_text()) for name in ("report.md", "heatmap.svg", "receipt.html")})
    assert twins[0] == twins[1]


def test_r15_a_different_seed_on_go1_changes_only_what_the_second_tree_feeds(outs: Path) -> None:
    """The sections of the ``--seed 7`` run equal the sections rendered from the API's seed-7
    tree; everything outside them equals the default run's."""
    base = ok(outs, GO1_ROOT, *E14_ARGV[1:])
    seeded = ok(outs, GO1_ROOT, *E14_ARGV[1:], "--seed", "7")
    assert excised(seeded.md, md_bounds(seeded.md)) == excised(base.md, md_bounds(base.md))
    assert excised(seeded.html, html_bounds(seeded.html)) == excised(base.html, html_bounds(base.html))
    api = built(GO1_ROOT, GO1_A, GO1_B, events=("fell",), x="mu", y="push_pct_bw", with_tree=True, seed=7, theme="light")
    api_md, api_html = api.to_markdown(), api.to_html()
    assert section_lines(seeded.md, "md") == section_lines(api_md, "md")
    assert section_lines(seeded.html, "html") == section_lines(api_html, "html")
    assert section_lines(seeded.md, "md") != section_lines(base.md, "md")


# ---------- R16: a tree from another pair is refused ----------


def test_r16_a_tree_from_another_pair_is_refused_with_comparison_mismatch_naming_events_or_cells(synth_root: Path) -> None:
    m = report_module()
    store = Store(GO1_ROOT)
    go1_multi, go1_tree = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",))
    _, axes_tree = store_tree(synth_root, "axes-a", "axes-b", events=("fail",))
    manifests = (store.manifest(GO1_A), store.manifest(GO1_B))
    spec = spec_for(GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw")
    with pytest.raises(m.ComparisonMismatch) as info:
        m.build_multi_report(go1_multi, spec, manifests=manifests, tree=axes_tree)
    message = str(info.value).lower()
    assert "event" in message or "cell" in message, message
    assert isinstance(info.value, m.ReportError)
    same = m.build_multi_report(go1_multi, spec, manifests=manifests, tree=go1_tree)
    assert same.tree is go1_tree


# ---------- R17: hostile values are escaped ----------


def test_r17_a_hostile_task_value_renders_as_text_on_the_receipt_and_verbatim_in_the_markdown(outs: Path, synth_root: Path) -> None:
    r = ok(outs, synth_root, "hostile-a", "hostile-b", "--event", "fail", "--x", "task", "--y", "temp")
    _, result = store_tree(synth_root, "hostile-a", "hostile-b", events=("fail",))
    assert result.leaves.tested and result.leaves.n_rejected == 2
    start, end = html_bounds(r.html)
    span = "\n".join(r.html.splitlines()[start:end])
    assert "<script" not in span and "</table><script>" not in span
    n_tables = sum(len(tables_of(items)) for items in sections(r.html, "html").values())
    assert span.count("<table>") == span.count("</table>") == n_tables, (span.count("<table>"), span.count("</table>"), n_tables)
    cells_rows = [row for _, rows in tables_of(sections(r.html, "html")["Cells"]) for row in rows]
    assert any(HOSTILE_VALUE in row[0] for row in cells_rows), cells_rows
    md_rows = [row for _, rows in tables_of(sections(r.md, "md")["Cells"]) for row in rows]
    assert any(row[0] == config_text({"task": HOSTILE_VALUE, "temp": 0.0}) for row in md_rows), md_rows


def test_r17_a_hostile_value_in_a_group_label_renders_as_text_on_a_pair_whose_grouping_admits_the_axis(outs: Path, synth_root: Path) -> None:
    """S29 section 3.2's 2026-09-12 invariant, on this module's surface; A27 gives it the fixture.

    The first assertion is the precondition and is not decoration: on R17's own two-cell pair the
    grouping collapses to ``whole_grid`` and the one label reads ``all``, which is why no group
    label in either oracle has ever carried a hostile value. If a later power-rule change returns
    this fixture to the collapse, that assertion fails here rather than the clauses below passing
    over a label that carries nothing.

    ``model()`` unescapes, so a cell equal to the raw value is the round-trip and not the absence
    of escaping; what separates an escaped cell from a raw one is the source text, and the two
    hostile strings are chosen so one substring settles each: a raw ``HOSTILE_VALUE`` puts
    ``<script`` in the span and a raw ``HOSTILE_IMG`` puts ``<img`` and an unquoted ``onerror="``
    there, while the escaped spellings carry ``&lt;script``, ``&lt;img`` and ``onerror=&quot;``.
    The table counts are the third: a raw ``</table>`` closes a table the renderer did not open.
    """
    r = ok(outs, synth_root, "hgroup-a", "hgroup-b", "--event", "fail", "--x", "cell", "--y", "task")
    _, result = store_tree(synth_root, "hgroup-a", "hgroup-b", events=("fail",))
    grouping = result.grouping
    assert (grouping.key, grouping.resolved_by, grouping.n_groups, grouping.n_resolvable_groups) == HOSTILE_GROUP_ADMITTED
    assert list(grouping.labels) == list(HOSTILE_VALUES)
    assert result.fault_lines.n_rejected_groups == HOSTILE_GROUP_REJECTED_GROUPS
    assert (result.leaves.n_families, result.leaves.n_tests, result.leaves.n_rejected) == (HOSTILE_GROUP_FAMILIES, HOSTILE_GROUP_TESTS, HOSTILE_GROUP_REJECTED)
    html_sections = sections(r.html, "html")
    span = "\n".join(line for name in ("Fault lines", "Cells") for line in section_lines(r.html, "html")[name])
    assert "<script" not in span and "<img" not in span and 'onerror="' not in span
    n_tables = len(tables_of(html_sections["Fault lines"])) + len(tables_of(html_sections["Cells"]))
    assert span.count("<table>") == span.count("</table>") == n_tables == HOSTILE_GROUP_FAMILIES + 1
    label_cells = [row[0] for _, rows in tables_of(html_sections["Fault lines"]) for row in rows]
    assert label_cells == list(HOSTILE_VALUES), label_cells
    family_lines = [line for line in lines_of(html_sections["Cells"]) if line.startswith("task=")]
    assert [line.startswith(f"task={value}: ") for line, value in zip(family_lines, HOSTILE_VALUES, strict=True)] == [True, True], family_lines


def test_r17_the_markdown_carries_a_hostile_group_label_verbatim_and_keeps_its_column_count(outs: Path, synth_root: Path) -> None:
    """R17's markdown half, and it is a **correctness** claim rather than a safety one.

    ``_md_table`` does not escape, so the value rides into the receipt's markdown verbatim and the
    guarantee the receipt can offer there is exactly that: what the structure holds is what the
    file says. A pipe in a label would split the row into extra columns -- it would break the
    table, not execute anything -- so the column-count clause below is what that failure mode
    looks like, and it says what it means only because neither hostile value carries a pipe, which
    is asserted first rather than assumed.
    """
    r = ok(outs, synth_root, "hgroup-a", "hgroup-b", "--event", "fail", "--x", "cell", "--y", "task")
    assert not any("|" in value for value in HOSTILE_VALUES)
    header, rows = tables_of(sections(r.md, "md")["Fault lines"])[0]
    assert [row[0] for row in rows] == list(HOSTILE_VALUES), [row[0] for row in rows]
    assert [len(row) for row in rows] == [len(header)] * HOSTILE_GROUP_REJECTED_GROUPS
    assert all(value in r.md for value in HOSTILE_VALUES)


# ---------- R21: C18's unpaired-analysis message ----------


def test_r21_the_unpaired_warning_states_the_cells_it_matched_and_names_coverage(synth_root: Path) -> None:
    """C18's message half, and only the message half.

    The warning is raised in ``diff._pairing``, which runs **before any cell exists**, so the
    restated sentence cannot carry a count and this clause does not ask for one. What it asks for
    is that the claim's subject stops being every episode: the pair below is ``paired`` with two
    cells that have no counterpart at all, measured, and ``coverage`` on the same page lists them,
    so a sentence promising a counterpart for every episode is contradicted by the page it is
    printed beside. The restatement scopes the correspondence to the cells the comparison matched
    and names ``coverage`` as where the rest are, which is reachable without a count.

    The numbers are asserted unchanged in the same breath: this packet changes what the warning
    says, never when a method is permitted to run.
    """
    store = Store(synth_root)
    fa, fb = store.read("overlap-a", meta=False), store.read("overlap-b", meta=False)
    ma, mb = store.manifest("overlap-a"), store.manifest("overlap-b")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = multi_diff(fa, fb, events=["fail"], method="fisher_bh", q=Q, manifest_a=ma, manifest_b=mb)
    assert (result.paired, result.dropped_a, result.dropped_b, result.n_tests) == (True, 1, 1, 3)
    assert int((~result.coverage["comparable"]).sum()) == 2 and sorted(set(result.coverage.loc[~result.coverage["comparable"], "cause"])) == ["only_a", "only_b"]
    raised = [w for w in caught if w.category is diff_mod.UnpairedAnalysis]
    assert len(raised) == 1, [w.category for w in caught]
    message = str(raised[0].message)
    assert "every episode" not in message, message
    assert "matched" in message and "coverage" in message and "cells" in message, message
    assert ma.run_salt in message and "mcnemar_bh" in message, message


def test_r21_paired_is_still_salt_equality_and_mcnemar_still_refuses_and_runs_where_it_did(synth_root: Path) -> None:
    """The three things C18 keeps for its own packet, pinned here as **unchanged**.

    They are in scope for this oracle and out of scope for this build, which is not a contradiction
    but the point: ``DIFF_PY_EXCLUDED``'s ``_pairing`` region stops the byte digest seeing them
    move, so the cover has to. ``paired`` stays salt equality even where the salt is the only
    evidence and the rows disagree; ``mcnemar_bh`` still refuses on differing salts and still runs
    on equal ones; a ``t_unit`` mismatch still raises before either question is asked.
    """
    store = Store(synth_root)
    fa, fb = store.read("overlap-a", meta=False), store.read("overlap-b", meta=False)
    ma, mb = store.manifest("overlap-a"), store.manifest("overlap-b")
    ea, eb = store.read("empty-a", meta=False), store.read("empty-b", meta=False)
    mea, meb = store.manifest("empty-a"), store.manifest("empty-b")
    assert ma.run_salt == mb.run_salt and mea.run_salt != meb.run_salt
    assert quiet_multi_diff(fa, fb, ma, mb, events=("fail",), method="fisher_bh").paired is True
    assert quiet_multi_diff(ea, eb, mea, meb, events=("fail",), method="fisher_bh").paired is False
    assert quiet_multi_diff(fa, fb, ma, mb, events=("fail",), method="mcnemar_bh").paired is True
    with pytest.raises(diff_mod.NotPairable):
        multi_diff(ea, eb, events=["fail"], method="mcnemar_bh", q=Q, manifest_a=mea, manifest_b=meb)
    with pytest.raises(diff_mod.UnitMismatch):
        multi_diff(fa, fb, events=["fail"], method="fisher_bh", q=Q, manifest_a=ma, manifest_b=dataclasses.replace(mb, t_unit="tool_calls"))


# ---------- R18: golden, Go1 ----------


def test_r18_go1_renders_twenty_group_rows_nineteen_rejected_nineteen_families_and_the_golden_leaf_counts(outs: Path) -> None:
    fisher = ok(outs, GO1_ROOT, *E14_ARGV[1:])
    header, rows = tables_of(fault_items(fisher, "md"))[0]
    assert len(rows) == GO1_MU_GROUPS and sum(row[-1] == "rejected" for row in rows) == GO1_MU_REJECTED
    cells = cells_items(fisher, "md")
    assert len(lines_of(cells)) == 2 + GO1_MU_REJECTED
    assert sum(len(rows) for _, rows in tables_of(cells)) == GO1_FISHER_LEAVES
    mcnemar = ok(outs, GO1_ROOT, *E14_ARGV[1:], "--method", "mcnemar_bh")
    _, result = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",), method="mcnemar_bh")
    assert result.root.scheme == "pair_swap"
    assert sum(len(rows) for _, rows in tables_of(cells_items(mcnemar, "md"))) == GO1_MCNEMAR_LEAVES
    assert_fault_lines("go1-mcnemar", "md", fault_items(mcnemar, "md"), result)
    grid = ok(outs, GO1_ROOT, *E14_ARGV[1:], "--by", "grid")
    cells = cells_items(grid, "md")
    assert len(lines_of(cells)) == 3 and f"{tree().WHOLE_GRID_KEY}={tree().WHOLE_GRID_LABEL}" in lines_of(cells)[2]
    assert sum(len(rows) for _, rows in tables_of(cells)) == GO1_GRID_LEAVES
    assert BOUND_AT_DEPTH_2 in lines_of(bound_items(grid, "md"))[0]


# ---------- R19: nothing else moves ----------


def test_r19_diff_outside_the_excluded_regions_check_serve_the_column_digests_the_fixtures_and_the_signatures_are_unchanged() -> None:
    assert digest_excluding(DIFF_SOURCE, [q for record in DIFF_PY_EXCLUDED for q in record["region"]]) == DIFF_PY_SHA256
    assert hashlib.sha256(DIFF_SOURCE.read_bytes()).hexdigest() != DIFF_PY_SHA256
    for record in DIFF_PY_EXCLUDED:
        cover = REPO / record["cover"][0]
        assert cover.exists(), record["cover"]
        for test_id in record["cover"][1]:
            resolve_region(ast.parse(cover.read_bytes()), test_id)
    code, out, err = run_cli(["--store", str(GO1_ROOT), *CHECK_ARGV])
    assert code == CHECK_EXIT and err == "" and sha256_of_text(out) == CHECK_STDOUT_SHA256, (code, err)
    code, out, err = run_cli(["--store", str(GO1_ROOT), *SERVE_ARGV])
    assert code == 0 and err == "", err
    structure = json.loads(out)
    tree_less = {**{k: v for k, v in structure.items() if k != "tree"}, "schema": TREE_LESS_SCHEMA}
    normalised = json.dumps({**tree_less, "pair": {**tree_less["pair"], "store_root": "<store>"}}, sort_keys=True)
    assert sha256_of_text(normalised) == SERVE_STRUCTURE_SHA256
    store = Store(GO1_ROOT)
    a, b, ma, mb = store.read(GO1_A, meta=False), store.read(GO1_B, meta=False), store.manifest(GO1_A), store.manifest(GO1_B)
    pair = quiet_multi_diff(a, b, ma, mb, events=("fell", "survived"), method="fisher_bh")
    fell_logrank = quiet_multi_diff(a, b, ma, mb, events=("fell",), method="logrank_bh")
    assert sha256_of_column(pair, "q") == PAIR_QCOLUMN_SHA256
    assert sha256_of_column(pair, "delta") == PAIR_DELTA_SHA256
    assert sha256_of_column(fell_logrank, "q") == FELL_LOGRANK_QCOLUMN_SHA256
    assert sha256_of_text(pair.coverage.to_json(orient="records")) == COVERAGE_SHA256
    for name, digest in REGRESSION_SHA256.items():
        assert hashlib.sha256((REGRESSION_DIR / name).read_bytes()).hexdigest() == digest, name
    t = tree()
    multi, result = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",))
    p_driven = ("p_location", "p_dispersion", "p_omnibus", "rejects", "headline")
    assert sha256_of_text(json_bytes(without(result.root.to_json(), p_driven))) == F28_OMNIBUS_SHA256
    assert str(inspect.signature(t.omnibus)) == OMNIBUS_SIGNATURE
    assert str(inspect.signature(t.resolve_grouping)) == RESOLVE_GROUPING_SIGNATURE
    assert tuple((p.name, p.kind.name, p.default) for p in inspect.signature(t.tree).parameters.values()) == TREE_PARAMETERS


# ---------- R20: the receipt's shape ----------


def test_r20_the_four_h2s_sit_after_the_headline_and_before_the_figure_every_table_has_a_thead_and_the_sections_set_no_style(every_pair: Any) -> None:
    for name, r, _result, _ in every_pair:
        lines = r.html.splitlines()
        start, end = html_bounds(r.html)
        before = lines[:start]
        assert before[-1].startswith("<p"), (name, before[-1][:60])
        assert any(line.startswith("<p>") for line in before), name
        span = lines[start:end]
        for line in span:
            assert "style=" not in line and "class=" not in line and not HEX_RE.search(line), (name, line[:80])
            if line.startswith("<table>"):
                assert "<thead>" in line and "<tbody>" in line and line.count("<table>") == 1, (name, line[:80])
        assert lines[end].startswith(HTML_FIGURE_PREFIX), name


def test_r20_the_quickstart_receipt_carries_the_trade_line_before_the_sections_and_inlines_the_svg(every_pair: Any) -> None:
    by_name = {name: (r, result) for name, r, result, _ in every_pair}
    r, _ = by_name["quickstart-2"]
    lines = r.html.splitlines()
    start, end = html_bounds(r.html)
    assert lines[start - 1].startswith('<p class="trade">'), lines[start - 1][:60]
    assert "<svg" in "\n".join(lines[end:]) and "<style>" in "\n".join(lines[:start])


def test_r19_the_exclusion_record_is_one_constant_per_narrowed_file_with_every_adr_077_field() -> None:
    """ADR-077's retirement duty, as the mechanical check the entry defines.

    Step 1 is the grep for ``_PY_EXCLUDED`` under ``tests/``, one hit per live exclusion because
    the record is a module constant named for the file it narrows. **Counted over files, not
    lines**, and that is an amendment ADR-077 is owed rather than a reading of it: the entry says
    ``grep -rn`` returns two after A27, which is wrong twice over -- it holds only for a one-line
    record, and A27 narrows four carriers rather than two. Six fields make it a multi-line literal,
    so ``grep -rn`` returns many and ``grep -rl`` returns the files the entry means. Measured at
    ``101028c``: **0** files against twelve ``_PY_SHA256`` lines over six clauses in four files;
    **four** after A27, every carrier of ``DIFF_PY_SHA256``. Asserting the file list here is what
    makes a fifth exclusion, minted anywhere in ``tests/``
    without a re-freeze packet behind it, fail rather than accumulate -- Q1's named failure mode is
    exclusions piling up unretired. A27's own retirement sweep discharges empty: nothing carried
    an exclusion at ``101028c``, so there was no orphan to file.

    **A22's retrofit, 2026-09-13.** The file list is unchanged: A22 adds a second *region* to an
    existing record constant, not a fifth carrier. The per-record assertions now pin ``owner`` and
    ``minted_at`` per entry rather than one shared literal, because ``_coverage`` is minted at
    ``4b3c6ae`` and ``_pairing`` at ``101028c``. Two live regions on one file is ADR-077's
    *adjacent* case and not its refused *overlapping* one, so the spans are asserted disjoint here
    rather than assumed. Neither exclusion is retirable yet: both name ``A28`` as their retiring
    packet, and A22 is not it.
    """
    hits = sorted(path.name for path in sorted((REPO / "tests").glob("test_*.py")) if "_PY_EXCLUDED" in path.read_text(encoding="utf-8"))
    assert hits == ["test_s26_fault_lines.py", "test_s27_leaves.py", "test_s28_report.py", "test_s29_viewer.py"], hits
    for record in DIFF_PY_EXCLUDED:
        assert set(record) == {"region", "owner", "cover", "minted_at", "blind_spot", "retire_at"}, sorted(record)
        assert record["retire_at"] == "A28"
        assert len(record["blind_spot"].split()) >= 20, record["region"]
    assert [(record["region"], record["owner"], record["minted_at"]) for record in DIFF_PY_EXCLUDED] == [
        (("_pairing",), "A27", "101028c"),
        (("_coverage",), "A22", "4b3c6ae"),
    ]
    spans = sorted(
        (node.lineno, node.end_lineno)
        for node in (resolve_region(ast.parse(DIFF_SOURCE.read_bytes()), q) for record in DIFF_PY_EXCLUDED for q in record["region"])
    )
    assert all(earlier[1] < later[0] for earlier, later in zip(spans, spans[1:])), spans
