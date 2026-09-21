"""S29 -- the viewer: the oracle for W1-W20.

Written from "Proofload -- Spec S29 Layered Report P4.4b The Viewer" section 4 and "Handoff
P4.4b", against ``94152ec`` (2026-09-11), the retrofit commit that moved the M13 and S21 pins to
``proofload.viewpair/3``, narrowed six ``serve --json`` digests to the tree-less projection and
carved ``tree.root.seed`` out of two forbidden-key walks by path.
Session B changes ``src/proofload/viewer.py`` (the schema, the required ``tree=``, the ``text``
decoration, ``_TREE_KINDS``, the four regions, the bound paragraph, the reason mapping) and
``src/proofload/cli.py`` (``serve``'s call to the helper S28 minted, the frames bound instead of
discarded, the one ``_diff_tree`` call) against this file, and does not edit it.

**``proofload.viewer``'s changed signature and schema are reached inside test bodies** through
``viewer()`` and the pair builder: this file collects on the bare tree, its own tests fail there,
and every other test in the repo still reports. The static tests read the source as text through
``proofload.__file__``, never ``Path.cwd()``, so a shim run under ``PYTHONPATH`` reads the shim.

**No test in this file carries the ``calibration`` marker, and none may.** The renderer draws
nothing: every number it prints is a field of a ``TreeResult`` M14 already computed, formatted
once at assembly by M7's ``_fmt``, so every assembly or rendering error is caught
deterministically and there is no rejection rate to hold in a band.

**Step zero, six items, measured at ``f4e2845`` before a test was written**
(``scratchpad/s29/step_zero.py``, ``collision_scan.py``, ``mint.py``). The grep report, over
both dimensions, is in Handoff P4.4b's *Session A's grep report* section, not here.

1. **The grep found six files and seven clauses, not the handoff's five and five.** Dimension
   (a), the schema, key-set and flag-set pins: ``test_m13_viewer.py`` and
   ``test_s21_errors.py``. Dimension (b), every test that drives ``serve`` through ``main()``:
   those two, ``test_s25_root.py`` O23, ``test_s26_fault_lines.py`` F28, ``test_s27_leaves.py``
   L20 -- and ``test_s28_report.py`` R19, which restates O23's digest and was written after
   Handoff P4.4b counted five. The seventh clause is S21's E16, which restates V24's
   forbidden-keys walk over the whole structure: green on the bare tree, invisible to a grep
   for the literals, red on the shim's first run of the S21 fixtures, and narrowed by path as
   V24 was. The negatives hold: ``test_m10_cli.py``, ``test_s24_interval.py`` and
   ``tests/live/`` drive ``serve`` nowhere, and ``test_m10_multi.py``'s ``go1_argv`` is
   ``diff``/``report``/``check``.
2. **The collision scan, re-run at HEAD.** ``viewer.py``: no attribute and no bare name inside a
   ``BinOp`` is a tree field name; the attributes are ``join`` (in ``render_html``), ``x_axis``
   and ``y_axis`` (in ``_axes``), the bare names ``first``, ``second`` (``_gap_seconds``),
   ``float`` (``_finite``), ``parts`` (``render_html``), ``spec`` (``_axes``), ``str``
   (``_config_text``, ``_hole``). **Counting rule:** attributing every ``BinOp`` to its
   innermost enclosing ``FunctionDef`` gives six functions in ``viewer.py`` (``_axes``,
   ``_config_text``, ``_finite``, ``_gap_seconds``, ``_hole``, ``render_html``), 39 in
   ``report.py`` and 23 in ``cli.py``; counting the module body as one more scope, as
   ``log/phase4-p44-collision-scan.py`` does, gives 7 / 40 / 24. Spec section 0.5's seven is the
   second rule; Handoff P4.4a's 37 / 6 / 22 was the first rule at ``aed3f11``, and S28's build
   moved ``report.py`` and ``cli.py`` since (``_check_tree`` now holds ``root``, ``events``,
   ``n_cells`` and the bare name ``tree`` inside a ``BinOp``; ``_report_pair`` holds one).
   Neither number is asserted here; ``viewer.py``'s empty collision set is what V17 rests on.
3. **The ``seed`` collision, against the shape.** ``"seed"`` appears in exactly one ``to_json``
   body in ``tree.py``, ``RootResult``'s; on every fixture the tree JSON carries one key named
   ``seed`` and one forbidden name, both at ``tree.root.seed``. V24 is two clauses; the retrofit
   narrowed the structure walk by path and left the page-index walk as frozen.
4. **The vocabulary, on today's page.** The 24 phrases are O19's nine, F19's nine and L10's
   six. On the ``/2`` page of every fixture ``where it`` reaches the *Not verified* region alone
   (inside ``elsewhere it``, pinned by V31 and by S21's ``UNVERIFIED``); ``step`` reaches *Run
   pair* and *Provenance* on every builder-made pair (``t_unit`` ``steps``) and nowhere on Go1
   (``seconds``); no string of any fixture's tree carries a phrase. The scope of W19 -- the three
   new regions, the bound paragraph and the tree's strings -- excludes all of them.
5. **The kind table.** 27 (object, field) rows over eight objects; every field exists on the
   dataclass it is attributed to. This oracle's literal adds one row the spec's table lacks
   (below, *config on the leaf row*).
6. **The fixtures that gain a tree.** ``test_m13_viewer.py``: ``build_pair`` (called for
   ``go1``, ``hostile``, the V23 ``--fix`` slice and the V29 rebuild) and V32's two direct
   ``build_structure`` calls, which reuse ``go1.report`` and ``go1.multi`` and so take
   ``go1.tree``; ``test_s21_errors.py``: ``built()`` (``syn``, ``syn_fixed``, ``go1``, the E-
   determinism rebuild). Each reads both frames inline; the retrofit binds them and grows the
   tree once. A tree grown on ``meta=True`` frames is byte-identical to one grown on the CLI's
   ``meta=False`` frames (measured). Go1's tree costs about 1.1 s (fell) and 1.3 s (both
   events); every builder-made pair under half a second.

**Conventions this oracle fixes where the spec is silent. Session B builds to these.**

- **One element per line.** The page is ``"\\n".join(parts)`` and every part of the three new
  regions is one line: ``<h2>Omnibus</h2>``, ``<h2>Fault lines</h2>`` and ``<h2>Cells</h2>``
  with no attributes, then a ``<p>`` through ``_lines_html`` per line and a ``_html_table`` per
  table, carrying no ``id``, ``class``, ``style`` or ``data-`` attribute and no script. A region
  runs from its ``<h2>`` line to the next ``<h2>`` line. The bound paragraph is one ``<p>``
  through ``_lines_html`` of two lines -- the rule line, then the assumption line -- and is the
  last line of the *Honesty* region, after the last panel's paragraph.
- **Region contents, in order.** Omnibus: ``root.headline`` verbatim; a method line carrying
  ``scheme``, ``n_permutations`` and ``seed``; one table (``event``, ``mean delta (pp)``, ``p``,
  ``rms delta (pp)``, ``p``) with one row per event in ``root.events`` order; the informative
  line. Fault lines: the head line naming ``key (resolved_by)`` and the other eight fields; one
  line per ``Refusal`` carrying ``key``, ``rung``, ``reason``, ``detail`` verbatim and
  ``next_rung``; the null line; one table whose rows are ``[label, n_cells,
  n_informative_cells, n_uninformative_cells, "n_a/n_b", mde + "pp"]`` plus ``n_discordant`` iff
  ``root.scheme == "pair_swap"`` plus ``[p_group, q_group, verdict]`` iff the level was tested,
  the verdict cell exactly ``rejected`` or ``not rejected``. Cells: the head line; when any
  family exists the MDE-meaning sentence (``increase`` and ``headroom`` in it, no number); per
  family in ``families`` order a line carrying ``key=label`` and the four counts, then iff
  ``n_rejected > 0`` a table whose rows are ``[config, event, delta, q_within, mde + "pp"]`` for
  the rejected leaves in ``cells`` order. **``pp`` is text beside the number.**
- **Config on the leaf row, and the one row this oracle adds to the kind table.** A leaf row's
  first cell is ``key=value`` over every key of ``config`` in the config's own order, joined by
  a comma and a space, where the value is ``text["config"][key]`` when that is a string and
  ``_scalar_text(value)`` otherwise -- exactly how ``_cell_rows`` prints a cell's config from
  ``config_text``. So each leaf's ``text`` carries, beside ``delta``, ``q_within`` and ``mde``,
  a ``config`` mapping over the config's keys whose values are ``_fmt(value, "coord")`` for a
  scalar and ``None`` for anything else -- ``_config_text``'s rule. **Why:** M13's frozen V16
  requires every float token on the page to be a substring of some structure string, and on
  Go1's default page S28's ``str(value)`` spelling (``push_pct_bw=10.0``) puts nine tokens on
  the page that no structure string carries (measured: ``10.0``, ``20.0``, ..., ``110.0``); the
  same value already prints as ``10`` in the drill-down. The page therefore spells a config
  value as the rest of the page does, formatted once at assembly, and the receipt's ``10.0`` is
  S28's spelling. Recorded as spec text not usable as written, below.
- **The untested forms.** The fault-lines null line reads ``not tested`` and either ``the root
  did not reject`` or ``one group is the whole family restated``; the cells head reads ``not
  tested`` and exactly one of: ``depth`` with ``depth_configured`` and without ``root``; ``the
  root did not reject``; ``no group rejected``. Nothing else follows an untested cells head.
- **``_TREE_KINDS`` is a ``dict[str, dict[str, str]]``** keyed by the object's dotted path in
  the tree JSON with list indices dropped (``root``, ``grouping``, ``fault_lines``,
  ``fault_lines.groups``, ``leaves``, ``leaves.families``, ``leaves.families.cells``,
  ``bound``), each value the field-to-kind mapping; ``TREE_KINDS`` below is the literal.
- **The reason mapping** is a module-level ``dict`` literal with exactly the four string keys
  ``depth``, ``root_not_rejected``, ``no_group_rejected``, ``one_group``, and ``render_html``
  raises ``ViewerError`` on a ``FaultLines.reason`` or ``Leaves.reason`` it does not carry.
- **The token rule (W7).** Every numeric token of the three regions and the bound paragraph --
  split on whitespace, ``=``, ``,``, ``:``, ``;``, ``(``, ``)``, ``/``, ``|``, a trailing ``pp``
  stripped -- is a ``text`` string of the tree, the ``str`` of an ``int`` field of the tree, a
  numeric token of a string the tree carries (``headline``, ``detail``, a label, a config
  value), an event name, the requested key, or the rule's ``2``. The assumption line is skipped:
  it is free text under W19 and carries a citation year.
- **W11's help clause is per flag**: each of the five flags' ``(invocation, help)`` entry, with
  argparse's wrapping collapsed, is equal under ``serve --help`` and ``diff --help``; the group
  headings the helper prints are not compared.
- **The mismatch check (W16)** refuses a tree whose ``root.events`` is not ``multi.events`` or
  whose ``root.n_cells`` is not the flat family's cell count, naming the mismatch.

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
- **A28's retrofit, 2026-09-13.** ``SCHEMA`` moves to ``proofload.viewpair/4`` and ``/3`` joins
  the retired set (W12); the tree key set gains ``agreement`` (W12); both ``diff.py`` exclusions
  are retired and ``DIFF_PY_SHA256`` is whole-file again; ``REPORT_PY_SHA256`` is narrowed at
  ``_check_tree`` and ``REPORT_PY_EXCLUDED`` minted, owner A28, ``retire_at`` empty;
  ``TREE_PY_SHA256`` stays whole-file under spec A28 section 10 Q2 (b) and ADR-078, red from
  Session B's build until a second Session A commit re-mints it off the shipped bytes; W16's
  same-events acceptance is re-grown under another ``seed`` rather than another method, because
  section 10 Q5 (b) makes a ``mcnemar_bh`` tree beside a ``fisher_bh`` diff a refusal. The
  sweep counts module-level ``*_PY_EXCLUDED`` constants by AST, not by text. The classified red
  set is in Handoff A28.
- **P-1's retrofit, 2026-09-17 (P-1 section 7.2, 7.4).** The payload root is thirteen keys,
  ``intervals`` after ``panels``; ``_TREE_KINDS["root"]`` gains ``p_floor``; the honesty band is
  ``2n + 2`` lines with the flat family's interval paragraph before the bound (W5); the fault-lines
  block gains the group floor line after the null line iff the level was tested (W9, W11);
  ``TREE_PY_SHA256`` is **narrowed** at ``("RootResult", "_root")`` and ``TREE_PY_EXCLUDED`` minted,
  owner P-1 -- ADR-077's clean case, measured identical on the bare tree and on P-1's prototype;
  ``DIFF_PY_SHA256`` and ``REPORT_PY_SHA256`` stay as A28 left them, green on Session A's commit and
  red from Session B's build until Session A's post-build commit re-mints both whole-file and
  retires ``REPORT_PY_EXCLUDED`` (ADR-078); ``SERVE_STRUCTURE_SHA256``, ``TREE_LESS_KEYS_SHA256``,
  ``GO1_PAGE_2_SHA256``, ``CHECK_STDOUT_SHA256`` and the E14 markdown and receipt digests are
  re-minted off P-1 Session A's shadow shim, built to P-1 section 3's verbatim strings. The
  classified red set is in ``tests/test_p1_payload.py``'s module docstring.

**Spec text this oracle could not use as written, each resolved here and reported.**

- Section 3.7's and the handoff's "the whole suite is green on that commit alone" cannot hold
  for a retrofit that moves pins to values only the build produces; ``85fea8f``, the ``/2``
  precedent, was red the same way. The retrofit commit is red on exactly the moved pins and the
  fixtures that pass ``tree=``, green everywhere else, and the classified red set is the check
  (handoff, *Session A's grep report*).
- Section 3.3 row 6 puts the MDE-meaning sentence in the bound paragraph; W10 and mutant 24 put
  it in *Cells*. It prints once, in *Cells*, as S28's receipt does; the bound paragraph is the
  rule line and the assumption line.
- W4's "the page rendered at ``aed3f11`` from the ``/2`` structure" has no renderer after the
  build. It is pinned as the sha256 of the ``/2`` page on Go1 (``store_root`` normalised),
  minted on the bare tree at ``f4e2845``, against the ``/3`` page with the three regions and
  the bound line excised by index; on every pair the excised page is identical across two
  trees of the same pair; and the tree-less keys (``panels``, ``holes``, ``unverified``,
  ``heatmap_svg``, ``diff``, ``view``) digest per pair to values minted the same way (W17's
  second clause, the same property).
- W20's ``git diff --exit-code aed3f11 -- report.py`` is S28's build commit's ``report.py`` now
  that S28 shipped first; both files are pinned as sha256 of their bytes at ``f4e2845``, which a
  scratch copy without ``.git`` can check.
- Section 0.7's hostile pair is ``test_m13_viewer.py``'s ``hostile`` fixture, whose root does
  not reject (measured: three cells, both axes underpowered, ``root_not_rejected``), so no
  hostile value reaches the tree's regions there. W14 uses a two-cell pair whose ``task`` values
  are M13's ``HOSTILE`` string and S28's table-closing string, arm b moved, so both leaves
  reject and both values reach *Cells*.
- W2's "the only key named ``seed`` at any depth" is a property of the fixtures, not of the
  structure: a user config axis named ``seed`` would land under ``tree.root.units.config`` and
  under every leaf's ``config``, an exposure ``panels[].cells[].config`` already has at
  ``f4e2845`` and V24 already catches. No fixture has such an axis.
- W3's non-finite clause has no fixture: no tree float is non-finite on any pair, so the rule is
  asserted by putting ``nan`` into a copy of Go1's ``RootResult.location`` before assembly.
- W1's "``serve --help`` lists exactly sixteen flags" is read over the option entries, not over
  every ``--word`` in the help text: the helper S28 minted says "the constant sweep's
  ``--max-mde`` uses" in ``--max-group-mde``'s help, so a whole-text flag regex reads seventeen.
  M13's frozen V30 read the whole text and was red on the shim for that reason; the retrofit
  narrows its extraction to option entries, which is the property V30 always meant.

**Fixture limits, stated before anything is asserted on a fixture.** Go1 cannot show a refusal
or a hostile value; the axes pair cannot show a rejected leaf; the identical pair cannot show
anything tested below the root; the BH and gate pairs are reached only with ``--by grp`` under
McNemar and neither can show a rejected leaf (without ``--by`` both resolve to ``cell``, a
different tree); the multi-event pair is the only ``K = 2`` whose events are not complements;
the quickstart pair cannot show a refusal; the hostile pair and the vocabulary pair collapse to
the whole grid, so their group labels never carry a value; the S18 pair is not a fixture.

**Named non-observables.** A second ``tree()`` call in ``_cmd_serve`` on the same frames and
knobs: the same bytes. A ``text`` entry produced by a private copy of ``_fmt`` that agrees with
it on every fixture: V17's ``format(`` and ``:.`` clauses, restated in W20, are the guard.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import html as html_mod
import inspect
import json
import math
import re
import warnings
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from html.parser import HTMLParser
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
from proofload.report import MultiReport, ReportSpec, build_multi_report
from proofload.store import EpisodeRecord, RunManifest, Store
from proofload.tree import tree as grow_tree

PACKAGE = Path(proofload.__file__).resolve().parent
REPO = PACKAGE.parents[1]
VIEWER_SOURCE = PACKAGE / "viewer.py"
CLI_SOURCE = PACKAGE / "cli.py"
TREE_SOURCE = PACKAGE / "tree.py"
REPORT_SOURCE = PACKAGE / "report.py"
DIFF_SOURCE = PACKAGE / "diff.py"
GO1_ROOT = REPO / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"
QUICKSTART = REPO / "examples" / "quickstart.toml"
MOCK_MODULE = "proofload.examples.mock_agent"
ROLLOUT = f"{MOCK_MODULE}:rollout"
PATCHED = f"{MOCK_MODULE}:rollout_patched"
QUICKSTART_SALT = "0000000000000015"

# ---------- spec sections 2, 3.1, 3.2, 3.3: the literals ----------

#: W1. The schema, the one W17's tree-less projection is minted at, and the two ``render_html`` refuses.
SCHEMA = "proofload.viewpair/5"
RETIRED_SCHEMA = "proofload.viewpair/2"
RETIRED_SCHEMAS = (RETIRED_SCHEMA, "proofload.viewpair/3", "proofload.viewpair/4")
#: W1. The twelve top-level keys, in order (section 3.1).
TOP_LEVEL_KEYS = (
    "schema", "pair", "diff", "holes", "view", "headline", "trade_line", "fence", "panels",
    "intervals", "tree", "unverified", "heatmap_svg",
)
#: The keys the tree does not touch (W4, W13, W17).
TREE_LESS_KEYS = ("panels", "holes", "unverified", "heatmap_svg", "diff", "view")
#: W1. ``serve``'s sixteen flags: M13 section 2's eleven plus the five tree flags.
SERVE_FLAGS = frozenset({
    "--event", "--x", "--y", "--fix", "--method", "--q", "--theme", "--top-n", "--forest", "--title", "--json",
    "--permutations", "--seed", "--by", "--max-group-mde", "--depth",
})
TREE_FLAGS = ("--permutations", "--seed", "--by", "--max-group-mde", "--depth")
#: W1. ``build_structure``'s parameters after this packet: (name, kind, required, annotation).
BUILD_STRUCTURE_PARAMETERS = (
    ("report", "POSITIONAL_OR_KEYWORD", True, "MultiReport"), ("multi", "POSITIONAL_OR_KEYWORD", True, "MultiDiffResult"),
    ("tree", "KEYWORD_ONLY", True, "TreeResult"), ("manifest_a", "KEYWORD_ONLY", True, "RunManifest"),
    ("manifest_b", "KEYWORD_ONLY", True, "RunManifest"), ("rows_a", "KEYWORD_ONLY", True, "int"),
    ("rows_b", "KEYWORD_ONLY", True, "int"), ("tally_a", "KEYWORD_ONLY", True, "RunTally"),
    ("tally_b", "KEYWORD_ONLY", True, "RunTally"), ("store_root", "KEYWORD_ONLY", True, "str"),
)
RENDER_HTML_SIGNATURE = "(structure: 'Mapping[str, Any]') -> 'str'"
SERVE_PAGE_SIGNATURE = "(page: 'str', *, on_bind: 'Callable[[HTTPServer], None]') -> 'None'"
#: W1, W6. The reason mapping's keys (S28 R1's four), and the three tuples no renderer names.
REASONS = frozenset({"depth", "root_not_rejected", "no_group_rejected", "one_group"})
REASON_TUPLE_NAMES = ("LEAVES_NOT_TESTED_REASONS", "NOT_TESTED_REASONS", "REFUSAL_REASONS")
#: W1, W3. The kind table (section 3.2) as this oracle's literal, keyed by the object's dotted
#: path with list indices dropped, plus the ``config`` row the module docstring explains.
TREE_KINDS: dict[str, dict[str, str]] = {
    "root": {"p_floor": "sig3", "p_omnibus": "sig3", "p_location": "sig3", "p_dispersion": "sig3", "q": "sig3", "location": "pp1", "dispersion": "pp1"},
    "grouping": {"alpha_floor": "sig3", "max_group_mde": "pp0", "size_median": "num", "group_mde": "pp1"},
    "fault_lines": {"q": "sig3"},
    "fault_lines.groups": {"mde": "pp1", "location": "pp1", "dispersion": "pp1", "p_location": "sig3", "p_dispersion": "sig3", "p_group": "sig3", "q_group": "sig3"},
    "leaves": {"q": "sig3"},
    "leaves.families": {"mde_median": "pp0", "mde_max": "pp0"},
    "leaves.families.cells": {"delta": "pp1", "q_within": "sig3", "mde": "pp0", "config": "coord"},
    "bound": {"bound": "sig3", "q": "sig3", "delta_star": "sig3"},
}
SCALAR = (bool, int, float, str)
#: W5. The ``<h2>`` sequence of the page, in document order.
H2_SEQUENCE = (
    "Run pair", "Events", "Omnibus", "Result", "Honesty", "Not verified", "Fault lines", "Cells", "Heatmap", "Cell",
    "Holes", "Worst cells", "Provenance",
)
NEW_REGIONS = ("Omnibus", "Fault lines", "Cells")
#: The three nulls, quoted verbatim on the page (W19).
ROOT_NULL = "no cell changed"
GROUP_NULL = "no cell in the group changed"
CELL_NULL = "this cell did not change"
#: W19. O19's nine phrases, F19's nine additions and L10's six; case-insensitive substrings.
FORBIDDEN_VOCABULARY = (
    "given the root", "given that", "conditional on", "leaf", "fdr", "broke", "where it broke", "failed at", "step",
    "broken", "failed in", "where it", "culprit", "root cause", "power stays high", "high power", "well powered", "same shift",
    "given the group", "given a group", "given that the group", "reliable", "controlled at q", "at level q",
)
#: W7. The one numeric literal the rule line carries as text: the ``2`` of ``2 x depth x q x delta*``.
BOUND_RULE_LITERAL = "2"
#: W20. M13's import partition (V35), restated.
ASSEMBLY_HELPERS = frozenset({"_fmt", "_coord_text", "_worst_header", "_worst_table_rows", "_EPISTEMIC_FENCE"})
RENDER_HELPERS = frozenset({"_html_style", "_html_table", "_provenance_lines"})

#: W17, W20. S25's O23 digest restated as narrowed: ``serve --json`` on Go1 with ``tree`` removed
#: and ``schema`` set to ``/2``, ``store_root`` normalised.
SERVE_ARGV = ("serve", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--json")
# Re-minted 2026-09-20 (truncation surfacing): the structure's ``diff`` object renames the horizon key in place and gains six keys, and the
# schema is /5 before this projection sets it back to /2. Each value is the baseline's plus that change.
SERVE_STRUCTURE_SHA256 = "aae3498e0d90462f21963011b17f21cdd88083ad2bacb4d78b2702b2594bc9f7"
#: W4, W17. Minted on the bare tree at f4e2845 through ``serve --json`` on each pair's argv below
#: (``scratchpad/s29/mint.py``): the six tree-less keys, ``json.dumps(sort_keys=True)``, sha256.
# Re-minted 2026-09-20 (truncation surfacing): only the ``diff`` key of the six moves (the horizon key renamed in place, six keys appended); the
# other five are byte-equal to the baseline's for every pair below.
TREE_LESS_KEYS_SHA256 = {
    "go1": "6b0fdadb914c9f9d3864d8df78623746420771ba35492ff1573352143188a22b",
    "go1-two-events": "d9c96f6d48c8c951ef89c522712004cf1490d75b324715196cbded897474d9e1",
    "axes": "65981a36e4065d16a6025ddea9e907fcd1125af3b6e2c1defca35aa1a7e4417f",
    "identical": "41242b890f4614357e0970c4e69a11ff2c6722bbd36e73d7c1a72abf7c171094",
    "bh": "205de903e5f1fd2e5af036b9bc9efbed82c1213bc2ea57558ef9e84d2328bf11",
    "gate": "7afa731c9eb7433c0a206c4a872233f7bf30cf24477e48e23e56868d3cf89460",
    "multi-event": "ef44cac46bc8288337d802a362ffc6cbc4adb3527502355f116a28972d789fe3",
    "one-value": "00ba86ac27ca7cd307c8eca8ea6dbaf22c1584584f44dadbdfc07aff1b5014a6",
    "three-key": "0f5923272f7b47b7de751bc064fa9d995d9412203d0ca6b2a0311a295f8728e8",
    "vocab": "612ee7e405d7930971025aeadd4ba843d2a909c9575b344158ae68f5e5716379",
    "hostile": "7e812761e9bcb85b61fa6cfd01ea667b72638e96541e5dba138b388a78986194",
}
#: W4. The ``/2`` page on Go1, ``str(GO1_ROOT)`` replaced by ``<store>``, sha256, minted on the bare
#: tree at f4e2845 from the structure ``serve --json`` printed.
# Re-minted 2026-09-20 (truncation surfacing): the page's provenance list gains the horizon rename and six observation items; each value is the
# baseline page's plus that change, byte for byte.
GO1_PAGE_2_SHA256 = {
    "go1": "f8cd5c394a74bc3d4d2bb3ec662dbfa414aec27ee6c29b301859771a34d5937f",
    "go1-two-events": "aaf677acb5c9f0a2b9780e2e1d9068f9fcd40ea49f3bd0e68d360a63bd6c3d29",
}
#: W20. ``diff.py`` whole again. **A28's retrofit, 2026-09-13 -- both exclusions retired** (ADR-077's
#: standing duty). A27's ``_pairing`` (minted ``101028c``) and A22's ``_coverage`` (minted
#: ``4b3c6ae``) both named ``A28`` as their retiring packet; both owners have landed and A28 rewrites
#: all four carriers, so the value is a read off the shipped file at ``38e8df9`` (byte-identical at
#: ``03d7ed2``): the whole-file sha256, never a prediction. Bytes, so a scratch copy without ``.git``
#: can check.
DIFF_PY_SHA256 = "d5ca27cade592886f1f5c236d43e1aaf1632a16a2be0975f7b5a9c5f440fdfd7"
#: W20, **narrowed by P-1 Session A under ADR-077 (P-1 section 7.4, the clean case)**: ``tree.py``'s
#: bytes outside ``RootResult`` and ``_root``, minted at ``a626cd3`` and measured identical on the
#: P-1 prototype, because P-1's one ``tree.py`` edit -- the ``p_floor`` field, its ``to_json`` key and
#: its single assignment site -- sits inside those two definitions. Green on Session A's commit and
#: on the build; red on an edit anywhere else in the file. A28's whole-file ``7f9a4f08...`` (A28
#: section 10 Q2 (b)) is replaced by this narrowed value and re-minted by nobody. A28's history
#: stays in the module docstring.
TREE_PY_SHA256 = "83ec34949bf21026cd26a8f39f749740851f4ebf994146dccf7c23aeb7919b43"
#: ADR-077's record for the two regions (P-1 section 7.4): ``cover`` is the P-1 oracle's Y16 and
#: Y18 tests, asserted to exist through the resolver; ``retire_at`` is empty because no queued
#: packet re-freezes W20 after P-1; ``lines`` are the two spans over the file's lines at mint
#: (ADR-077 Q2, lean (b)).
TREE_PY_EXCLUDED: tuple[dict[str, Any], ...] = (
    {
        "region": ("RootResult", "_root"),
        "owner": "P-1",
        "cover": ("tests/test_p1_payload.py", ("test_y16_p_floor_is_one_over_b_plus_one_sits_after_n_permutations_and_bounds_every_permutation_p", "test_y16_on_go1_at_the_default_b_p_omnibus_equals_p_floor_exactly", "test_y18_the_kind_table_names_p_floor_as_sig3_and_w2s_round_trip_holds_with_the_new_key")),
        "minted_at": "a626cd3",
        "blind_spot": (
            "The two excluded regions also hold RootResult.headline(), to_json()'s eighteen existing "
            "keys and the seventeen keyword arguments _root already passes, so this digest no longer "
            "sees a key renamed, the headline reworded or rejects recomputed inside them. S25's "
            "O-family, F28_OMNIBUS_SHA256 (re-minted by P-1 to cover the new field) and P-1's Y16 are "
            "what catch those."
        ),
        "retire_at": "",
        "lines": "228-303, 853-890 of 2192",
    },
)
#: W20. ``report.py`` whole again. **P-1's post-build commit, 2026-09-18 -- A28's exclusion
#: retired** (ADR-077's standing duty, step 3 under ADR-078). A28's ``report.py::_check_tree``
#: narrowing (minted ``38e8df9``, ``retire_at`` empty) was retirable -- A28 is done -- and P-1 is
#: the first re-freeze to reach this carrier, so the record and its cover loop go with it. P-1's
#: own edits to this file cannot be narrowed the way A28's were: three of its regions
#: (``_interval_lines``, ``_interval_text``, ``_NO_INTERVAL_LINE``) do not exist on the pinned
#: commit and the import line at the top moves. So this is the whole-file sha256 of the built
#: ``report.py``, read off the shipped file and never a prediction. No ``REPORT_PY_EXCLUDED`` is
#: minted; ``TREE_PY_EXCLUDED`` above is now the file's only exclusion record.
# Re-minted 2026-09-20 (truncation surfacing): report.py gains the observation block of the provenance list.
#: CD Session A, 2026-09-20: `report.py` moves in CD Session B -- `_observation_cap` must let the
#: string "none" through (CD9, and D9's "no change to them" does not hold for it). This literal and
#: `test_fr_first_run.py`'s `UNTOUCHED_FILE_SHA256["report.py"]` are the two carriers, both owed to
#: CD's post-build re-mint. Correct at `1f5491b`; not re-minted here.
# CD Session B, 2026-09-21: re-minted off the built `report.py` at `234513c`. CD's D9 moves
# exactly one function, `_observation_cap`, which now lets the declared word `none` through;
# `test_cd_cap_declaration.py` pins the rest of the file by a digest that excludes it. The
# other carrier is `test_fr_first_run.py`'s `UNTOUCHED_FILE_SHA256["report.py"]`, re-minted in
# the same commit. Before this packet: `5cfdf03b...`.
REPORT_PY_SHA256 = "4369c1114ba7f2881f3972831101dda30c72ad27f2727d31ba7342959468e746"
CHECK_ARGV = ("check", GO1_A, GO1_B, "--event", "fell")
CHECK_STDOUT_SHA256 = "dc3d8acc89864cdb69eda671d931c492e3e81c1d74eb1393b37d789f8c2d3417"
CHECK_EXIT = 0
#: W20. S21's E14 digests as S28's retrofit left them: the SVG through the CLI, the markdown and
#: the light receipt through the tree-less builder.
E14_ARGV = ("report", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw")
# Re-minted 2026-09-20 (truncation surfacing): report.md and receipt.html take the horizon rename and the two observation-cap lines
# (the builder is handed manifests and no counts); heatmap.svg is unchanged. Each value is the baseline's plus that change, byte for byte.
E14_SHA256 = {
    "report.md": "39c6dde2db4de96337b13a667d37e080d86664e03ce7593e7714fdeb777154d8",
    "heatmap.svg": "2e0dfe4e27314d30f1514104a60d0a566a75f4c032fa1b25f92b779f70c324de",
    "receipt.html": "705aae536623bf35a91a31dd4c3c7967532ce9698cd9fe1de4a01158f39ca379",
}

#: W9, W10, W18. Golden Go1 (S26 F13, S27 L7, S28 R18).
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
GOLDEN_PERMUTATIONS = 4000
GOLDEN_SEED = 0
Q = 0.05
FLAG_VALUES = {"--by": "temp", "--max-group-mde": "0.6", "--depth": "2", "--permutations": "300", "--seed": "3"}

# ---------- the store builders (S27's, restated) ----------

NON_EVENTS = frozenset({"ok", "x", "z", "plain"})
EVENT_T = 2.0
HORIZON = 5.0
SALT = "s29-salt"
OTHER_SALT = "s29-other-salt"
AXES_SALT = "s26-axes-salt"
BH_SALT = "s26-bh-salt"
AXES_TYPES_TASK_FIRST = {"task": "categorical", "temp": "continuous"}
BH_TYPES = {"grp": "categorical", "cell": "categorical"}
GATE_TYPES = {"grp": "categorical", "cell": "categorical"}
ME_TYPES = {"task": "categorical", "temp": "continuous"}
THREE_KEY_TYPES = {"task": "categorical", "temp": "continuous", "model": "categorical"}
THREE_KEY_MODELS = ("m1", "m2")
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
#: W19's pair: two task values that are forbidden phrases, so the mask is what keeps the check
#: green. W14's: M13's hostile string and S28's table-closing string.
VOCABULARY_VALUES = ("given the root", "where it broke")
HOSTILE = "".join(["<", "/script><img src=x onerror=", chr(34), "alert(1)", chr(34), ">&", chr(34)])
HOSTILE_TABLE = "".join(["<", "/table><script>alert(1)</script>&", chr(34)])
HOSTILE_VALUES = (HOSTILE, HOSTILE_TABLE)
#: A27's BH-shaped hostile pair, the one fixture R17 and W14 share, restated byte-identically in
#: ``tests/test_s28_report.py`` so the two oracles cannot disagree about what an admitted grouping
#: is. The grouping key ``task`` takes the two hostile strings as its values and ``cell`` supplies
#: the cells inside each group, so the axis rung reaches ``task`` and the power rule **admits** it
#: instead of refusing it ``underpowered`` and collapsing to ``whole_grid`` -- which is what the
#: two-cell hostile and vocabulary pairs do, and why no group label has ever carried a hostile
#: value (section 6's amendment; mutant 31b). Measured at ``101028c``: two groups of eight cells at
#: N=32 is 256 units per arm per group, whose group MDE is 0.1347 against the 0.20 default at the
#: two-group floor alpha = q/2 = 0.025, so both groups resolve. 128 units per arm would read 0.1883
#: and still admit; the margin is taken so a later power-rule change cannot quietly return this
#: fixture to the collapse it exists to escape, and ``HOSTILE_GROUP_ADMITTED`` below is what makes
#: such a return loud rather than quiet. Arm b is moved in every cell of both groups, by different
#: amounts, so both groups reject, each becomes a family, and both values reach a group label, a
#: family line and a leaf config cell.
HOSTILE_GROUP_TYPES = {"task": "categorical", "cell": "categorical"}
HOSTILE_GROUP_CELLS = 8
HOSTILE_GROUP_N = 32
HOSTILE_GROUP_BASE = 2
HOSTILE_GROUP_EXTRA = (14, 8)
#: A27. The admitted grouping as both oracles read it: (key, resolved_by, n_groups,
#: n_resolvable_groups). ``whole_grid`` in either of the first two is the collapse this fixture
#: exists to avoid, and asserting this tuple is what stops the guard below going vacuous.
HOSTILE_GROUP_ADMITTED = ("task", "axis", 2, 2)
#: A27. What the admitted axis makes testable, measured at ``101028c``: both groups rejected, one
#: family per group, every leaf rejected.
HOSTILE_GROUP_REJECTED_GROUPS = 2
HOSTILE_GROUP_FAMILIES = 2
HOSTILE_GROUP_TESTS = 16
HOSTILE_GROUP_REJECTED = 16

BIND_TIMEOUT_S = 15.0


def viewer() -> Any:
    """``proofload.viewer``, imported on demand so the changed surface is reached inside bodies."""
    import proofload.viewer as module

    return module


def fmt(value: Any, kind: str) -> str:
    """M7's one formatter, reached the way V16 reaches it."""
    from proofload.report import _fmt

    return _fmt(value, kind)


def quiet_multi_diff(a: pd.DataFrame, b: pd.DataFrame, ma: RunManifest, mb: RunManifest, *, events: Sequence[str], method: str, q: float = Q) -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return multi_diff(a, b, events=list(events), method=method, q=q, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]


def manifest(run_id: str, salt: str, axis_types: Mapping[str, str]) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types), backend="synthetic", environment={"note": "built by s29 step zero"},  # type: ignore[arg-type]
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


def three_key_cells(moved: bool) -> dict[Any, list[str]]:
    """The fixed-third-key pair: four ``task`` x one ``temp`` x two ``model`` at N=8, arm b moved
    in every replicate. ``--fix model=m1`` slices the figure while the tree is over all eight
    cells, so a leaf outside the slice is still a leaf and every row carries ``model=``."""
    return {
        (("task", f"t{i}"), ("temp", 0.0), ("model", m)): (["fail"] * 8 if moved else ["ok"] * 8)
        for i in range(4)
        for m in THREE_KEY_MODELS
    }


def two_value_cells(values: Sequence[str], moved: bool) -> dict[Any, list[str]]:
    """Two cells, one ``task`` value each, at N=8; arm b moved in every replicate so the root
    rejects, the grouping collapses and both leaves are named."""
    return {(("task", v), ("temp", 0.0)): (["fail"] * 8 if moved else ["ok"] * 8) for v in values}


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


# ---------- the CLI, tripwired ----------


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def run_serve(argv: Sequence[str]) -> tuple[int, str, str, list[str]]:
    """``main(argv)`` with ``serve_page`` replaced, wherever the CLI could reach it, by a function
    that records the call and raises: V5's tripwire. Returns the streams and the calls."""
    calls: list[str] = []

    def trip(*args: Any, **kwargs: Any) -> None:
        calls.append("serve_page")
        raise AssertionError("serve_page was called; something was about to bind")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(viewer(), "serve_page", trip)
        mp.setattr(cli, "serve_page", trip, raising=False)
        code, out, err = run_cli(argv)
    return code, out, err, calls


def strict_loads(text: str) -> Any:
    def fail(token: str) -> Any:
        raise ValueError(f"non-JSON constant {token!r}")

    return json.loads(text, parse_constant=fail)


# ---------- trees and pairs, cached ----------

_TREES: dict[tuple[Any, ...], tuple[Any, Any]] = {}


def store_tree(root: Path, a: str, b: str, *, events: Sequence[str], method: str = "fisher_bh", **knobs: Any) -> tuple[Any, Any]:
    """``(multi, tree)`` on a stored pair the way the CLI reaches them: the frames read with
    ``meta=False``, ``multi_diff`` at the CLI's default ``q``, ``tree`` at M14's defaults unless
    a knob is given."""
    key = (str(root), a, b, tuple(events), method, tuple(sorted(knobs.items())))
    if key not in _TREES:
        store = Store(root)
        fa, fb = store.read(a, meta=False), store.read(b, meta=False)
        ma, mb = store.manifest(a), store.manifest(b)
        multi = quiet_multi_diff(fa, fb, ma, mb, events=events, method=method)
        _TREES[key] = (multi, grow_tree(fa, fb, multi, manifest_a=ma, manifest_b=mb, **knobs))
    return _TREES[key]


def counts_of(store: Store, run: str) -> tuple[int, int]:
    """``(spans, spans stamped as cut)`` over a run's stored envelopes: the count the CLI hands the builders.
    Added 2026-09-20 (truncation surfacing); restated here and never imported from another test module."""
    spans = [s for e in store.read(run, meta=False, trace="envelope")["trace"] if isinstance(e, dict) for s in e.get("spans", [])]
    return len(spans), sum(1 for s in spans if s.get("truncated") == "observation")


@dataclass(frozen=True)
class Pair:
    name: str
    root: Path
    a: str
    b: str
    events: tuple[str, ...]
    x: str
    y: str | None
    fixed: dict[str, Any]
    method: str
    knobs: dict[str, Any]
    requested: str | None
    multi: Any
    tree: Any
    structure: dict[str, Any]
    page: str

    @property
    def report(self) -> MultiReport:
        store = Store(self.root)
        ma, mb = store.manifest(self.a), store.manifest(self.b)
        spec = ReportSpec(title=f"{self.a} vs {self.b}: {', '.join(self.events)}", x_axis=self.x, y_axis=self.y, fixed=self.fixed)
        return build_multi_report(self.multi, spec, manifests=(ma, mb), observations=(counts_of(store, self.a), counts_of(store, self.b)))


KNOB_FLAGS = {"by": "--by", "depth": "--depth", "n_permutations": "--permutations", "seed": "--seed", "max_group_mde": "--max-group-mde"}
_PAIRS: dict[str, Pair] = {}


def serve_argv(root: Path, a: str, b: str, events: Sequence[str], x: str, y: str | None, fixed: Mapping[str, Any], method: str, knobs: Mapping[str, Any]) -> list[str]:
    argv = ["--store", str(root), "serve", a, b]
    for e in events:
        argv += ["--event", e]
    argv += ["--x", x]
    if y is not None:
        argv += ["--y", y]
    for k, v in fixed.items():
        argv += ["--fix", f"{k}={json.dumps(v)}"]
    if method != "fisher_bh":
        argv += ["--method", method]
    for k, v in knobs.items():
        argv += [KNOB_FLAGS[k], str(v)]
    return argv + ["--json"]


def pair(name: str, root: Path, a: str, b: str, events: Sequence[str], x: str, y: str | None = None, *, fixed: Mapping[str, Any] | None = None, method: str = "fisher_bh", **knobs: Any) -> Pair:
    """One pair through ``serve --json`` (tripwired, exit 0, empty stderr), its page from
    ``render_html``, and the oracle's own tree on the same frames and knobs; cached by name."""
    if name not in _PAIRS:
        fixed = dict(fixed or {})
        code, out, err, calls = run_serve(serve_argv(root, a, b, events, x, y, fixed, method, knobs))
        assert code == 0 and err == "" and calls == [], (name, code, err[-400:], calls)
        structure = strict_loads(out)
        multi, result = store_tree(root, a, b, events=events, method=method, **knobs)
        _PAIRS[name] = Pair(
            name, root, a, b, tuple(events), x, y, fixed, method, dict(knobs), knobs.get("by"),
            multi, result, structure, viewer().render_html(structure),
        )
    return _PAIRS[name]


# ---------- the page, by line and by region ----------

H2_RE = re.compile(r"^<h2>(.*)</h2>$")
TAG_RE = re.compile(r"<[^>]+>")
TD_RE = re.compile(r"<td>(.*?)</td>", re.S)
TH_RE = re.compile(r"<th>(.*?)</th>", re.S)
TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
TOKEN_SPLIT = re.compile(r"[\s=,:;()/|]+")
ATTRIBUTE_RE = re.compile(r"\b(id|class|style|data-[a-z]+)=")


def h2_lines(page: str) -> list[tuple[int, str]]:
    return [(i, m.group(1)) for i, line in enumerate(page.splitlines()) if (m := H2_RE.match(line))]


def h2_sequence(page: str) -> list[str]:
    return [heading for _, heading in h2_lines(page)]


def region_lines(page: str, heading: str) -> list[str]:
    """The lines from ``<h2>heading</h2>`` (exclusive) to the next ``<h2>`` (exclusive)."""
    lines = page.splitlines()
    marks = h2_lines(page)
    starts = [i for i, h in marks if h == heading]
    assert len(starts) == 1, (heading, starts)
    start = starts[0]
    after = [i for i, _ in marks if i > start]
    end = after[0] if after else len(lines)
    return lines[start + 1 : end]


def unescape(fragment: str) -> str:
    return html_mod.unescape(TAG_RE.sub("", fragment))


def p_lines(line: str) -> list[str]:
    assert line.startswith("<p>") and line.endswith("</p>"), line[:80]
    return [unescape(part) for part in line[3:-4].split("<br>")]


def table_of(line: str) -> tuple[list[str], list[list[str]]]:
    assert line.startswith("<table>") and line.endswith("</table>") and "<thead>" in line and "<tbody>" in line, line[:80]
    header = [unescape(h) for h in TH_RE.findall(line)]
    rows = [[unescape(c) for c in TD_RE.findall(tr)] for tr in TR_RE.findall(line)]
    return header, [r for r in rows if r]


def items(lines: Sequence[str]) -> list[tuple[Any, ...]]:
    """Each region line as ``("line", text)`` per ``<br>``-separated line of a ``<p>``, or
    ``("table", header, rows)``; anything else is a defect of the region."""
    out: list[tuple[Any, ...]] = []
    for line in lines:
        assert not ATTRIBUTE_RE.search(line) and "<script" not in line, line[:80]
        if line.startswith("<table>"):
            out.append(("table", *table_of(line)))
        else:
            out.extend(("line", text) for text in p_lines(line))
    return out


def lines_of(its: Sequence[tuple[Any, ...]]) -> list[str]:
    return [it[1] for it in its if it[0] == "line"]


def tables_of(its: Sequence[tuple[Any, ...]]) -> list[tuple[list[str], list[list[str]]]]:
    return [(it[1], it[2]) for it in its if it[0] == "table"]


def region(p: Pair, heading: str) -> list[tuple[Any, ...]]:
    return items(region_lines(p.page, heading))


def region_text(its: Sequence[tuple[Any, ...]]) -> str:
    parts = []
    for it in its:
        if it[0] == "line":
            parts.append(it[1])
        else:
            parts.extend(it[1])
            parts.extend(c for row in it[2] for c in row)
    return "\n".join(parts)


def bound_line(page: str) -> str:
    """The bound paragraph: the one line of the *Honesty* region carrying ``outer-nodes``."""
    found = [line for line in region_lines(page, "Honesty") if "outer-nodes" in line]
    assert len(found) == 1, found
    return found[0]


def bound_lines(page: str) -> list[str]:
    return p_lines(bound_line(page))


def excised(page: str) -> str:
    """The page with the three new regions (heading line to next ``<h2>``) and the bound line
    removed, by index and never by the tail (W4)."""
    lines = page.splitlines()
    marks = h2_lines(page)
    drop: set[int] = set()
    for k, (i, heading) in enumerate(marks):
        if heading in NEW_REGIONS:
            end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
            drop.update(range(i, end))
    honesty = [i for i, h in marks if h == "Honesty"]
    if honesty:
        start = honesty[0]
        after = [i for i, _ in marks if i > start]
        end = after[0] if after else len(lines)
        drop.update(i for i in range(start + 1, end) if "outer-nodes" in lines[i])
    return "\n".join(line for i, line in enumerate(lines) if i not in drop) + "\n"


# ---------- a small DOM, restated from M13 (never imported) ----------


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None
    index: int
    children: list[Node] = dataclasses.field(default_factory=list)
    texts: list[str] = dataclasses.field(default_factory=list)

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


VOID_TAGS = {"br", "meta", "img", "hr", "input", "link", "col", "area", "base", "wbr"}


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
        return [n for n in self.nodes if n.tag == tag and all(n.attrs.get(k) == v for k, v in attrs.items())]


def parse_html(text: str) -> Dom:
    dom = Dom()
    dom.feed(text)
    dom.close()
    return dom


# ---------- tokens, walks and masks ----------


def numeric_tokens(text: str) -> list[str]:
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


def has(text: str, token: str) -> bool:
    return token in numeric_tokens(text)


def walk_key_paths(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
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


def walk_ints(value: Any) -> Iterator[int]:
    if isinstance(value, dict):
        for v in value.values():
            yield from walk_ints(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_ints(v)
    elif isinstance(value, int) and not isinstance(value, bool):
        yield value


def text_strings(value: Any) -> Iterator[str]:
    """Every string under a key named ``text`` at any depth."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k == "text":
                yield from walk_strings(v)
            else:
                yield from text_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from text_strings(v)


def without_text(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: without_text(v) for k, v in value.items() if k != "text"}
    if isinstance(value, list):
        return [without_text(v) for v in value]
    return value


def diff_paths(a: Any, b: Any, path: str = "") -> list[str]:
    """Every dotted path (list indices dropped) at which two JSON values differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in set(a) | set(b):
            here = f"{path}.{k}" if path else str(k)
            if k not in a or k not in b:
                out.append(here)
            else:
                out.extend(diff_paths(a[k], b[k], here))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [path]
        return [p for x, y in zip(a, b, strict=True) for p in diff_paths(x, y, path)]
    return [] if a == b else [path]


def user_data(p: Pair) -> list[str]:
    t = p.structure["tree"]
    pieces = [p.requested or "", *t["root"]["events"], *t["grouping"]["labels"]]
    for family in t["leaves"]["families"]:
        pieces.append(family["label"])
        for leaf in family["cells"]:
            pieces.extend(str(v) for v in leaf["config"].values())
            pieces.extend(v for v in leaf["text"]["config"].values() if isinstance(v, str))
    return [x for x in pieces if x]


def masked(text: str, p: Pair) -> str:
    out = text
    for piece in sorted(set(user_data(p)), key=len, reverse=True):
        out = out.replace(piece, "")
    return out.lower()


def new_region_text(p: Pair) -> str:
    """The visible text of the three new regions and the bound paragraph."""
    parts = [region_text(region(p, h)) for h in NEW_REGIONS]
    parts.extend(bound_lines(p.page))
    return "\n".join(parts)


def expected_tokens(p: Pair) -> tuple[set[str], set[str]]:
    """W7's two sets. ``allowed``: every ``text`` string of the tree, the ``str`` of every int
    under it, the numeric tokens of every string it carries, the event names, the requested key
    and the rule's ``2``. ``required``: the fields section 3.3 prints, given what was tested."""
    t = p.structure["tree"]
    root, grouping, fault, leaves, bound = t["root"], t["grouping"], t["fault_lines"], t["leaves"], t["bound"]
    allowed: set[str] = set(text_strings(t))
    allowed.update(str(i) for i in walk_ints(t))
    for s in walk_strings(t):
        allowed.update(numeric_tokens(s))
    allowed.update(numeric_tokens(" ".join(user_data(p))))
    allowed.add(BOUND_RULE_LITERAL)
    required: set[str] = set()
    for e in root["events"]:
        for f in ("location", "p_location", "dispersion", "p_dispersion"):
            required.add(root["text"][f][e])
    required.update(str(getattr(p.tree.root, f)) for f in ("n_cells", "n_informative_cells", "n_uninformative_cells", "n_permutations", "seed"))
    required.update(str(grouping[f]) for f in ("n_groups", "size_min", "size_max", "n_resolvable_groups"))
    required.update(grouping["text"][f] for f in ("size_median", "max_group_mde", "alpha_floor"))
    required.add(str(fault["n_degenerate_groups"]))
    if fault["tested"]:
        required.update({fault["text"]["q"], str(fault["n_rejected_groups"]), str(fault["n_groups"])})
    for group in fault["groups"]:
        required.update(str(group[f]) for f in ("n_cells", "n_informative_cells", "n_uninformative_cells", "n_a", "n_b"))
        required.add(group["text"]["mde"])
        if root["scheme"] == "pair_swap":
            required.add(str(group["n_discordant"]))
        if fault["tested"]:
            required.update({group["text"]["p_group"], group["text"]["q_group"]})
    if leaves["tested"]:
        required.update({leaves["text"]["q"], str(leaves["n_families"]), str(leaves["n_tests"]), str(leaves["n_rejected"])})
    else:
        if leaves["reason"] == "depth":
            required.add(str(bound["depth_configured"]))
    for family in leaves["families"]:
        required.update({str(family["n_tests"]), str(family["n_rejected"]), family["text"]["mde_median"], family["text"]["mde_max"]})
        for leaf in family["cells"]:
            if leaf["rejects"]:
                required.update({leaf["text"]["delta"], leaf["text"]["q_within"], leaf["text"]["mde"]})
    required.update({str(bound["depth"]), str(bound["depth_configured"]), bound["text"]["bound"], bound["text"]["q"], bound["text"]["delta_star"]})
    return allowed, required


def tokens_of(its: Sequence[tuple[Any, ...]]) -> list[str]:
    return numeric_tokens(region_text(its))


def config_cell(leaf: Mapping[str, Any]) -> str:
    """A leaf's cell as the module docstring fixes it: ``key=value`` over every key, the value
    from ``text.config`` when it is a string and ``_scalar_text`` otherwise."""
    from proofload.viewer import _scalar_text

    shown = leaf["text"]["config"]
    return ", ".join(f"{k}={shown[k] if isinstance(shown.get(k), str) else _scalar_text(v)}" for k, v in leaf["config"].items())


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_bytes(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)


def tree_less_digest(structure: Mapping[str, Any]) -> str:
    return sha256_of_text(json_bytes({k: structure[k] for k in TREE_LESS_KEYS}))


# ---------- ast helpers (restated; never imported across test modules) ----------


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def module_functions(module: ast.Module) -> dict[str, ast.AST]:
    return {n.name: n for n in module.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)}


def closure(module: ast.Module, name: str) -> list[ast.AST]:
    """The function plus every module-level function it reaches by name, transitively (V17's)."""
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


# ---------- ADR-077: the retirement sweep (A28, restated) ----------


def excluded_constants(path: Path) -> list[str]:
    """Module-level constants named ``*_PY_EXCLUDED`` -- ADR-077's step-1 sweep as an AST read.

    A text grep for the suffix counts a file from its prose and from the sweep line itself once
    its record is gone; a name on a module-level assignment is what "the record is a module
    constant named for the file it narrows" means. Restated rather than imported.
    """
    names: list[str] = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target: ast.expr | None = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        else:
            target = None
        if isinstance(target, ast.Name) and target.id.endswith("_PY_EXCLUDED"):
            names.append(target.id)
    return names


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


def referenced_names(nodes: Sequence[ast.AST]) -> set[str]:
    return {n.id for fn in nodes for n in ast.walk(fn) if isinstance(n, ast.Name)}


ARITHMETIC = (ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.MatMult)


def is_non_numeric(node: ast.AST) -> bool:
    return isinstance(node, ast.JoinedStr | ast.List | ast.ListComp | ast.Tuple) or (isinstance(node, ast.Constant) and isinstance(node.value, str))


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


def total_seconds_operands(nodes: Sequence[ast.AST]) -> list[ast.AST]:
    return [n.func.value for fn in nodes for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "total_seconds"]


def format_calls(module: ast.AST) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and ((isinstance(node.func, ast.Name) and node.func.id == "format") or (isinstance(node.func, ast.Attribute) and node.func.attr == "format"))
    ]


def json_dumps_calls(nodes: Sequence[ast.AST]) -> list[ast.Call]:
    return [
        n
        for fn in nodes
        for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "dumps" and isinstance(n.func.value, ast.Name) and n.func.value.id == "json"
    ]


def report_import_names(module: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "proofload.report":
            names.update(alias.name for alias in node.names)
    return names


def module_body_imports_of(module: ast.Module, dotted: str) -> list[int]:
    """Line numbers of module-body imports of ``dotted`` (a ``TYPE_CHECKING`` block is not the module body)."""
    return [n.lineno for n in module.body if isinstance(n, ast.ImportFrom) and n.module == dotted] + [
        n.lineno for n in module.body if isinstance(n, ast.Import) and any(a.name == dotted for a in n.names)
    ]


def mentioned(module: ast.Module) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.ImportFrom | ast.Import):
            out.update(alias.name for alias in node.names)
    return out


def string_dicts(module: ast.Module) -> list[tuple[str, set[str]]]:
    """Every module-level ``dict`` literal with all-string keys, as ``(bound name, key set)``."""
    out = []
    for node in module.body:
        target, value = None, None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        if target is not None and isinstance(value, ast.Dict) and value.keys and all(isinstance(k, ast.Constant) and isinstance(k.value, str) for k in value.keys):
            out.append((target, {k.value for k in value.keys}))  # type: ignore[union-attr]
    return out


FLOAT_SPEC_RE = re.compile(r":\.\d")
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")


def help_entries(text: str) -> dict[str, tuple[str, str]]:
    """Every option of an argparse help text as ``flag -> (invocation, help)``, whitespace
    collapsed; an entry starts at two spaces and a dash, its help continues on deeper lines."""
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
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One store holding every builder-made pair of section 0.7: the axes pair, the identical
    pair, the BH pair, the gate fixture, the multi-event pair (``crash`` carried outside ``t0``
    so the CLI admits the event), the one-value pair, the empty family, the fixed-third-key
    pair, the vocabulary pair and the hostile pair."""
    root = tmp_path_factory.mktemp("s29-synth")
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
    write_run(store, "hostile-a", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=two_value_cells(HOSTILE_VALUES, False))
    write_run(store, "hostile-b", salt=SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=two_value_cells(HOSTILE_VALUES, True))
    hg_a, hg_b = hostile_group_cells()
    write_run(store, "hgroup-a", salt=SALT, axis_types=HOSTILE_GROUP_TYPES, cells=hg_a)
    write_run(store, "hgroup-b", salt=SALT, axis_types=HOSTILE_GROUP_TYPES, cells=hg_b)
    return root


@pytest.fixture(scope="module")
def quickstart(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """The two quickstart runs of the mock agent under the S12 salt: ``t_unit`` ``tool_calls``,
    a trade line under two events."""
    root = tmp_path_factory.mktemp("s29-quickstart")

    def sweep(target: str, *extra: str) -> str:
        code, out, err = run_cli(["--store", str(root), "sweep", str(QUICKSTART), "--target", target, "--yes", *extra])
        assert code == 0, out + err
        last = out.strip().splitlines()[-1]
        assert last.startswith("run_id: "), out
        return last.split("run_id: ", 1)[1]

    a = sweep(ROLLOUT, "--salt", QUICKSTART_SALT)
    b = sweep(PATCHED, "--pair-with", a)
    return root, a, b


@pytest.fixture(scope="module")
def go1() -> Pair:
    return pair("go1", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw")


@pytest.fixture(scope="module")
def every_pair(synth_root: Path, quickstart: tuple[Path, str, str]) -> list[Pair]:
    """Every section 0.7 pair through ``serve --json`` with no tree flag but the ``--by grp`` the
    BH and gate pairs need (section 6), beside the tree the API grows on the same frames."""
    qroot, qa, qb = quickstart
    return [
        pair("go1", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw"),
        pair("go1-mcnemar", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", method="mcnemar_bh"),
        pair("go1-two-events", GO1_ROOT, GO1_A, GO1_B, ("fell", "survived"), "push_pct_bw", "mu"),
        pair("axes", synth_root, "axes-a", "axes-b", ("fail",), "temp", "task"),
        pair("identical", synth_root, "same-a", "same-b", ("fail",), "temp", "task"),
        pair("bh", synth_root, "bh-a", "bh-b", ("fail",), "grp", "cell", method="mcnemar_bh", by="grp"),
        pair("gate", synth_root, "gate-a", "gate-b", ("fail",), "grp", "cell", method="mcnemar_bh", by="grp"),
        pair("multi-event", synth_root, "me-a", "me-b", ("fail", "crash"), "task", "temp"),
        pair("one-value", synth_root, "ov-a", "ov-b", ("fail",), "task", "temp"),
        pair("three-key", synth_root, "three-a", "three-b", ("fail",), "task", "temp", fixed={"model": "m1"}),
        pair("vocab", synth_root, "vocab-a", "vocab-b", ("fail",), "task", "temp"),
        pair("hostile", synth_root, "hostile-a", "hostile-b", ("fail",), "task", "temp"),
        pair("quickstart", qroot, qa, qb, ("violated",), "tool_fail_rate", "task_id"),
        pair("quickstart-2", qroot, qa, qb, ("violated", "timeout"), "tool_fail_rate", "task_id"),
    ]


def by_name(pairs: Sequence[Pair]) -> dict[str, Pair]:
    return {p.name: p for p in pairs}


# ---------- W1: literals ----------


def test_w1_the_schema_the_thirteen_keys_and_the_signatures_are_the_literals(go1: Pair) -> None:
    """``viewer.SCHEMA``; the thirteen keys in order (P-1's ``intervals`` after ``panels``) on ``--json`` and on ``build_structure``'s
    return; ``build_structure`` takes ``tree`` as a required keyword between ``multi`` and
    ``manifest_a`` and its other parameters are unchanged; ``render_html`` and ``serve_page``
    keep their signatures."""
    m = viewer()
    assert m.SCHEMA == SCHEMA
    assert go1.structure["schema"] == SCHEMA and tuple(go1.structure) == TOP_LEVEL_KEYS, tuple(go1.structure)
    store = Store(GO1_ROOT)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    built = m.build_structure(
        go1.report, go1.multi, tree=go1.tree, manifest_a=ma, manifest_b=mb, rows_a=store.count(GO1_A), rows_b=store.count(GO1_B),
        tally_a=store.tally(GO1_A), tally_b=store.tally(GO1_B), store_root=str(GO1_ROOT),
    )
    assert tuple(built) == TOP_LEVEL_KEYS and built["schema"] == SCHEMA
    params = tuple((p.name, p.kind.name, p.default is inspect.Parameter.empty, p.annotation) for p in inspect.signature(m.build_structure).parameters.values())
    assert params == BUILD_STRUCTURE_PARAMETERS, params
    assert str(inspect.signature(m.render_html)) == RENDER_HTML_SIGNATURE
    assert str(inspect.signature(m.serve_page)) == SERVE_PAGE_SIGNATURE


def test_w1_the_reason_mapping_keys_and_the_kind_table_are_the_literals() -> None:
    """Exactly one module-level string-keyed ``dict`` literal in ``viewer.py`` has the four reason
    keys, and ``_TREE_KINDS`` equals this file's table (the module docstring says why it has one
    row the spec's lacks)."""
    module = parsed(VIEWER_SOURCE)
    mappings = [name for name, keys in string_dicts(module) if keys == set(REASONS)]
    assert len(mappings) == 1, mappings
    assert viewer()._TREE_KINDS == TREE_KINDS, viewer()._TREE_KINDS


def test_w1_serve_help_lists_exactly_the_sixteen_flags_and_no_port() -> None:
    """The flags are the option entries ``--help`` lists, not every ``--word`` in its text: the
    tree helper's help for ``--max-group-mde`` names ``--max-mde`` in prose (module docstring)."""
    code, out, err = run_cli(["serve", "--help"])
    assert code == 0, err
    flags = set(help_entries(out)) - {"-h"}
    assert flags == set(SERVE_FLAGS), flags ^ set(SERVE_FLAGS)
    assert "--port" not in out and "--max-mde" in out


# ---------- W2: the tree rides verbatim ----------


def test_w2_the_tree_with_every_text_removed_is_to_json_after_a_round_trip_and_seed_is_the_one_carved_path(every_pair: list[Pair]) -> None:
    """Strip every key named ``text`` at every depth of ``structure["tree"]`` and compare to
    ``json.loads(json.dumps(tree.to_json()))`` exactly: a renamed, reordered or dropped field
    fails here and nowhere else. ``tree.root.seed`` is the knob and is the only key named ``seed``
    at any depth -- on these fixtures (module docstring: an axis named ``seed`` would put a second
    one under ``config``, the exposure V24 already has)."""
    for p in every_pair:
        stripped = without_text(p.structure["tree"])
        expected = json.loads(json.dumps(p.tree.to_json()))
        assert stripped == expected, (p.name, diff_paths(stripped, expected)[:10])
        assert list(stripped) == list(expected), (p.name, list(stripped))
        seeds = [path for path, key in walk_key_paths(p.structure) if key == "seed"]
        assert seeds == ["tree.root.seed"], (p.name, seeds)
        assert p.structure["tree"]["root"]["seed"] == p.knobs.get("seed", GOLDEN_SEED)


# ---------- W3: text exactly where the page prints ----------


def expected_text_value(raw: Any, kind: str) -> Any:
    if kind == "coord":
        return {str(k): (fmt(v, "coord") if isinstance(v, SCALAR) else None) for k, v in raw.items()}
    if isinstance(raw, dict):
        return {k: fmt(v, kind) for k, v in raw.items()}
    if isinstance(raw, list):
        return [fmt(v, kind) for v in raw]
    return fmt(raw, kind)


def check_text(raw: Any, got: Any, path: str, name: str) -> None:
    """Walk the oracle's ``to_json()`` and the structure's tree in parallel, visiting the keys both
    carry: at every object the kind table names, ``text``'s key set is exactly the printed floats
    that are not ``None`` (plus ``config`` on a leaf) and each value is ``_fmt(raw, kind)``, a
    mapping or list field mapped over the same keys; every other object has no ``text``; a
    non-finite raw float is ``None``. Whether every key is carried, in order, is W2's clause and
    not this one's, so a renamed or dropped field fails W2 alone."""
    if isinstance(raw, dict):
        assert isinstance(got, dict), (name, path)
        kinds = TREE_KINDS.get(path)
        if kinds is None:
            assert "text" not in got, (name, path)
        else:
            assert "text" in got, (name, path)
            expected_keys = {f for f in kinds if raw.get(f) is not None}
            assert set(got["text"]) == expected_keys, (name, path, set(got["text"]) ^ expected_keys)
            for f, kind in kinds.items():
                if raw.get(f) is not None:
                    assert got["text"][f] == expected_text_value(raw[f], kind), (name, path, f)
        for k, v in raw.items():
            if k not in got:
                continue
            child = f"{path}.{k}" if path else str(k)
            if isinstance(v, (dict, list)):
                check_text(v, got[k], child, name)
            elif isinstance(v, float):
                assert got[k] == (v if math.isfinite(v) else None), (name, child, got[k], v)
    elif isinstance(raw, list):
        assert isinstance(got, list) and len(got) == len(raw), (name, path)
        for r, g in zip(raw, got, strict=True):
            if isinstance(r, (dict, list)):
                check_text(r, g, path, name)


def test_w3_text_sits_on_every_object_the_kind_table_names_and_nowhere_else(every_pair: list[Pair]) -> None:
    for p in every_pair:
        check_text(p.tree.to_json(), p.structure["tree"], "", p.name)
        assert all("text" not in unit for unit in p.structure["tree"]["root"].get("units", [])), p.name
        assert p.structure["tree"]["root"]["text"]["location"].keys() == set(p.tree.root.events), p.name


def test_w3_a_non_finite_tree_float_is_null_with_fmts_spelling_kept_in_text(go1: Pair) -> None:
    """No tree float is non-finite on any fixture, so the rule is asserted by putting ``nan`` into
    a copy of Go1's ``RootResult.location`` before assembly; the dump still parses strictly."""
    event = go1.tree.root.events[0]
    poisoned = replace(go1.tree, root=replace(go1.tree.root, location={**go1.tree.root.location, event: math.nan}))
    store = Store(GO1_ROOT)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    structure = viewer().build_structure(
        go1.report, go1.multi, tree=poisoned, manifest_a=ma, manifest_b=mb, rows_a=store.count(GO1_A), rows_b=store.count(GO1_B),
        tally_a=store.tally(GO1_A), tally_b=store.tally(GO1_B), store_root=str(GO1_ROOT),
    )
    root = structure["tree"]["root"]
    assert root["location"][event] is None
    assert root["text"]["location"][event] == fmt(math.nan, "pp1")
    strict_loads(json.dumps(structure, allow_nan=False))


# ---------- W4 and W17: the old regions and the old pins ----------


def test_w4_excising_the_three_regions_and_the_bound_line_gives_the_2_page_on_go1(every_pair: list[Pair]) -> None:
    """The ``/3`` page with the three new regions (by their ``<h2>`` lines) and the bound line
    excised, ``str(GO1_ROOT)`` normalised, digests to the ``/2`` page minted on the bare tree."""
    pairs = by_name(every_pair)
    for name, digest in GO1_PAGE_2_SHA256.items():
        page = excised(pairs[name].page).replace(str(GO1_ROOT), "<store>")
        assert sha256_of_text(page) == digest, name


def test_w4_the_excised_page_and_the_tree_less_keys_do_not_read_the_tree(every_pair: list[Pair], synth_root: Path) -> None:
    """On every pair the excised page is identical between the default tree and a second tree of
    the same pair (``--seed 1``), and the six tree-less keys are equal between the two structures."""
    for p in every_pair:
        if p.name in ("go1-mcnemar", "quickstart", "quickstart-2"):
            continue
        again = pair(f"{p.name}-seed1", p.root, p.a, p.b, p.events, p.x, p.y, fixed=p.fixed, method=p.method, **{**p.knobs, "seed": 1})
        assert excised(again.page) == excised(p.page), p.name
        for key in TREE_LESS_KEYS:
            assert again.structure[key] == p.structure[key], (p.name, key)
        assert again.structure["tree"]["root"]["seed"] == 1


def test_w17_the_narrowed_o23_and_the_tree_less_keys_digest_to_the_values_minted_on_the_bare_tree(every_pair: list[Pair]) -> None:
    """S25's O23 as narrowed: ``serve --json`` on Go1 with ``tree`` removed and ``schema`` set to
    ``/2``, ``store_root`` normalised, digests to S25's literal. And on every pair the six keys
    the tree does not touch digest to the values minted at f4e2845 (quickstart excluded: its run
    ids are minted per run)."""
    code, out, err, calls = run_serve(["--store", str(GO1_ROOT), *SERVE_ARGV])
    assert code == 0 and err == "" and calls == [], err
    structure = strict_loads(out)
    assert "tree" in structure
    tree_less = {**{k: v for k, v in structure.items() if k != "tree"}, "schema": RETIRED_SCHEMA}
    normalised = json.dumps({**tree_less, "pair": {**tree_less["pair"], "store_root": "<store>"}}, sort_keys=True)
    assert sha256_of_text(normalised) == SERVE_STRUCTURE_SHA256
    pairs = by_name(every_pair)
    for name, digest in TREE_LESS_KEYS_SHA256.items():
        assert tree_less_digest(pairs[name].structure) == digest, name


# ---------- W5: order of the document ----------


def test_w5_the_h2_sequence_and_the_bound_paragraphs_position(every_pair: list[Pair]) -> None:
    """The ``<h2>`` sequence is exactly the thirteen in order; the bound ``<p>`` is the last line of
    *Honesty*, after the last panel's ``<h3>``, its paragraph and (P-1, ADR-060) the flat family's
    one interval paragraph, before the first ``<svg>``, outside ``<details>``, with no hidden
    ancestor; *Fault lines* and *Cells* precede the ``<svg>``. **Amended by P-1 Session A**: the
    honesty band is ``2n + 2`` lines, the interval ``<p>`` sits immediately before the bound
    ``<p>`` (P-1 section 10 Q4, before) and carries the first interval line."""
    for p in every_pair:
        assert h2_sequence(p.page) == list(H2_SEQUENCE), (p.name, h2_sequence(p.page))
        honesty = region_lines(p.page, "Honesty")
        assert honesty[-1] == bound_line(p.page), (p.name, honesty[-1][:80])
        panels = p.structure["panels"]
        assert len(honesty) == 2 * len(panels) + 2, (p.name, len(honesty))
        assert honesty[-2].startswith("<p>") and html_mod.escape(p.structure["intervals"]["lines"][0]) in honesty[-2], (p.name, honesty[-2][:120])
        assert honesty[-3].startswith("<p>") and honesty[-4] == f"<h3>{html_mod.escape(panels[-1]['event'])}</h3>", (p.name, honesty[-4:])
        assert len(bound_lines(p.page)) == 2, (p.name, bound_lines(p.page))
        dom = parse_html(p.page)
        svg = dom.find("svg")[0].index
        bound_nodes = [n for n in dom.find("p") if "outer-nodes" in n.text and not n.inside("svg")]
        assert len(bound_nodes) == 1, p.name
        node = bound_nodes[0]
        assert node.index < svg and not node.inside("details"), p.name
        for n in (node, *node.ancestors()):
            assert "hidden" not in n.attrs and "display:none" not in n.attrs.get("style", "").replace(" ", ""), (p.name, n.tag)
        lines = p.page.splitlines()
        first_svg_line = next(i for i, line in enumerate(lines) if "<svg" in line)
        marks = dict((h, i) for i, h in h2_lines(p.page))
        assert marks["Omnibus"] < marks["Result"] < marks["Honesty"] < marks["Fault lines"] < marks["Cells"] < first_svg_line, p.name


# ---------- W6: reasons on the page, in M14's precedence ----------


def cells_head(p: Pair) -> str:
    return lines_of(region(p, "Cells"))[0]


def fault_null_line(p: Pair) -> str:
    lines = lines_of(region(p, "Fault lines"))
    return lines[1 + len(p.tree.grouping.refused)]


def test_w6_the_reasons_read_in_m14s_precedence_on_the_identical_bh_and_grid_fixtures(every_pair: list[Pair], synth_root: Path) -> None:
    """Identical pair at ``--depth 3``: both untested sentences read the root; at ``--depth 2``:
    *Cells* reads the ``depth`` form; Go1 at ``--depth 2``: ``depth``; BH pair by ``grp`` under
    McNemar: ``no group rejected``; ``--by grid`` on Go1: the one-group sentence and a family
    ``whole_grid=all``."""
    pairs = by_name(every_pair)
    p = pairs["identical"]
    assert p.tree.fault_lines.reason == p.tree.leaves.reason == "root_not_rejected"
    assert "not tested" in fault_null_line(p) and "the root did not reject" in fault_null_line(p), fault_null_line(p)
    assert "not tested" in cells_head(p) and "the root did not reject" in cells_head(p), cells_head(p)
    p = pair("identical-depth2", synth_root, "same-a", "same-b", ("fail",), "temp", "task", depth=2)
    assert p.tree.leaves.reason == "depth" and not p.tree.root.rejects
    head = cells_head(p)
    assert "not tested" in head and "depth" in head and has(head, "2") and "root" not in head, head
    p = pair("go1-depth2", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", depth=2)
    assert p.tree.leaves.reason == "depth" and "depth" in cells_head(p) and has(cells_head(p), "2"), cells_head(p)
    p = pairs["bh"]
    assert p.tree.leaves.reason == "no_group_rejected" and "no group rejected" in cells_head(p), cells_head(p)
    p = pairs["gate"]
    assert p.tree.leaves.reason == "no_group_rejected" and "no group rejected" in cells_head(p), cells_head(p)
    p = pair("go1-grid", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", by="grid")
    assert p.tree.fault_lines.reason == "one_group"
    assert "not tested" in fault_null_line(p) and "one group is the whole family restated" in fault_null_line(p), fault_null_line(p)
    from proofload.tree import WHOLE_GRID_KEY, WHOLE_GRID_LABEL

    assert f"{WHOLE_GRID_KEY}={WHOLE_GRID_LABEL}" in lines_of(region(p, "Cells"))[2], lines_of(region(p, "Cells"))


def test_w6_viewer_names_none_of_the_reason_tuples_and_an_unknown_reason_raises_viewer_error(every_pair: list[Pair]) -> None:
    """The second-reader rule: ``viewer.py`` names none of M14's three reason tuples; ``render_html``
    on a structure whose ``leaves.reason`` or ``fault_lines.reason`` is ``nonsense`` raises
    ``ViewerError`` rather than printing a sentence nobody wrote."""
    names = mentioned(parsed(VIEWER_SOURCE))
    assert not (names & set(REASON_TUPLE_NAMES)), sorted(names & set(REASON_TUPLE_NAMES))
    p = by_name(every_pair)["identical"]
    for level in ("leaves", "fault_lines"):
        structure = json.loads(json.dumps(p.structure, allow_nan=False))
        structure["tree"][level]["tested"] = False
        structure["tree"][level]["reason"] = "nonsense"
        with pytest.raises(viewer().ViewerError):
            viewer().render_html(structure)


# ---------- W7: every number is a text entry ----------


def test_w7_every_numeric_token_of_the_three_regions_and_the_bound_paragraph_is_a_text_entry_and_every_printed_field_is_there(every_pair: list[Pair]) -> None:
    """The token rule (module docstring), rebuilt from the structure and never from a printed
    number: every token is allowed, every required field is printed, no leaf ``p``, no flat
    ``q`` column, no colour bound and no unit reaches the regions. The assumption line is skipped."""
    for p in every_pair:
        allowed, required = expected_tokens(p)
        tokens: list[str] = []
        for heading in NEW_REGIONS:
            tokens.extend(tokens_of(region(p, heading)))
        rule, _assumption = bound_lines(p.page)
        tokens.extend(numeric_tokens(rule))
        stray = [t for t in tokens if t not in allowed]
        assert stray == [], (p.name, stray[:10])
        missing = required - set(tokens)
        assert missing == set(), (p.name, sorted(missing)[:10])
        # No leaf ``p`` under sig3 unless it coincides with an allowed token, and no unit record.
        leaves = [leaf for family in p.tree.leaves.families for leaf in family.cells if leaf.rejects]
        for leaf in leaves:
            token = fmt(leaf.p, "sig3")
            assert token in allowed or token not in tokens, (p.name, token)
        cells_tables = tables_of(region(p, "Cells"))
        assert all(len(header) == 5 for header, _ in cells_tables), (p.name, [h for h, _ in cells_tables])
        assert not any("units" in line.lower() and "unit" in line.lower() and "delta" in line.lower() for line in lines_of(region(p, "Omnibus"))), p.name


# ---------- W8: the omnibus region ----------


def assert_omnibus(p: Pair) -> None:
    root = p.structure["tree"]["root"]
    its = region(p, "Omnibus")
    lines, tables = lines_of(its), tables_of(its)
    assert lines[0] == root["headline"] == p.tree.root.headline(), (p.name, lines[0])
    assert p.tree.root.scheme in lines[1] and has(lines[1], str(p.tree.root.n_permutations)) and has(lines[1], str(p.tree.root.seed)), (p.name, lines[1])
    assert len(tables) == 1, (p.name, len(tables))
    header, rows = tables[0]
    assert len(header) == 5 and [row[0] for row in rows] == root["events"], (p.name, header, rows)
    for row, event in zip(rows, root["events"], strict=True):
        text = root["text"]
        assert row[1:] == [text["location"][event], text["p_location"][event], text["dispersion"][event], text["p_dispersion"][event]], (p.name, row)
    assert any(has(line, str(root["n_informative_cells"])) and has(line, str(root["n_cells"])) and has(line, str(root["n_uninformative_cells"])) for line in lines[2:]), (p.name, lines)
    assert lines.index(next(line for line in lines[2:] if has(line, str(root["n_uninformative_cells"])))) == len(lines) - 1, (p.name, lines)


def test_w8_the_omnibus_prints_the_headline_verbatim_the_method_line_one_row_per_event_and_the_informative_line(every_pair: list[Pair]) -> None:
    for p in every_pair:
        assert_omnibus(p)
    pairs = by_name(every_pair)
    assert not pairs["identical"].tree.root.rejects and "is not rejected" in lines_of(region(pairs["identical"], "Omnibus"))[0]
    first = lines_of(region(pairs["go1"], "Omnibus"))[0]
    assert pairs["go1"].tree.root.rejects and "is rejected" in first and f'"{ROOT_NULL}"' in first


# ---------- W9: the fault-lines region ----------


def group_row_width(p: Pair) -> int:
    return 6 + (1 if p.tree.root.scheme == "pair_swap" else 0) + (3 if p.tree.fault_lines.tested else 0)


def assert_fault_lines(p: Pair) -> None:
    t = p.structure["tree"]
    grouping, fault, root = t["grouping"], t["fault_lines"], t["root"]
    its = region(p, "Fault lines")
    lines, tables = lines_of(its), tables_of(its)
    head = lines[0]
    assert f"{grouping['key']} ({grouping['resolved_by']})" in head, (p.name, head)
    for token in (str(grouping["n_groups"]), str(grouping["size_min"]), grouping["text"]["size_median"], str(grouping["size_max"]), str(fault["n_degenerate_groups"]), str(grouping["n_resolvable_groups"]), grouping["text"]["max_group_mde"], grouping["text"]["alpha_floor"]):
        assert has(head, token), (p.name, head, token)
    refusals = lines[1 : 1 + len(grouping["refused"])]
    assert len(refusals) == len(grouping["refused"]), (p.name, lines)
    for line, refusal in zip(refusals, grouping["refused"], strict=True):
        for piece in (refusal["key"], refusal["rung"], refusal["reason"], refusal["detail"], refusal["next_rung"]):
            assert piece in line, (p.name, piece, line)
    null = lines[1 + len(grouping["refused"])]
    assert f'"{fault["null"]}"' in null and fault["null"] == GROUP_NULL, (p.name, null)
    if fault["tested"]:
        assert "tested by BH across" in null and has(null, str(fault["n_groups"])) and has(null, fault["text"]["q"]) and has(null, str(fault["n_rejected_groups"])) and "rejected" in null, (p.name, null)
    elif fault["reason"] == "root_not_rejected":
        assert "not tested" in null and "the root did not reject" in null, (p.name, null)
    else:
        assert fault["reason"] == "one_group" and "not tested" in null and "one group is the whole family restated" in null, (p.name, null)
    if fault["tested"]:
        # P-1 (C33 (b)): the group floor line follows the null line iff the level was tested.
        floor = lines[2 + len(grouping["refused"])]
        assert floor.startswith("group p floor ") and root["text"]["p_floor"] in floor and has(floor, str(root["n_permutations"])) and "not a measurement" in floor, (p.name, floor)
    assert len(lines) == (3 if fault["tested"] else 2) + len(grouping["refused"]), (p.name, lines)
    assert len(tables) == 1, (p.name, len(tables))
    header, rows = tables[0]
    width = group_row_width(p)
    assert len(header) == width, (p.name, header, width)
    assert [row[0] for row in rows] == grouping["labels"], (p.name, [row[0] for row in rows][:5])
    for row, group in zip(rows, fault["groups"], strict=True):
        assert len(row) == width and row[0] == group["label"], (p.name, row)
        assert row[1:4] == [str(group["n_cells"]), str(group["n_informative_cells"]), str(group["n_uninformative_cells"])], (p.name, row)
        assert row[4] == f"{group['n_a']}/{group['n_b']}", (p.name, row)
        assert row[5] == f"{group['text']['mde']}pp", (p.name, row)
        rest = row[6:]
        if root["scheme"] == "pair_swap":
            assert rest[0] == str(group["n_discordant"]), (p.name, row)
            rest = rest[1:]
        if fault["tested"]:
            assert rest == [group["text"]["p_group"], group["text"]["q_group"], "rejected" if group["rejects"] else "not rejected"], (p.name, row)
        else:
            assert rest == [], (p.name, row)


def test_w9_the_fault_lines_print_the_head_the_chain_the_null_and_one_row_per_group_in_labels_order(every_pair: list[Pair]) -> None:
    for p in every_pair:
        assert_fault_lines(p)


def test_w9_on_go1_by_mu_the_row_for_0_95_is_the_nineteenth_the_one_value_pair_has_two_refusal_lines_and_by_kind_names_trace(every_pair: list[Pair]) -> None:
    pairs = by_name(every_pair)
    p = pairs["go1"]
    header, rows = tables_of(region(p, "Fault lines"))[0]
    assert p.tree.grouping.key == "mu" and len(rows) == GO1_MU_GROUPS
    assert rows[18][0] == GO1_MU_NINETEENTH_LABEL and rows[18][-1] == "not rejected", rows[18]
    assert sum(row[-1] == "rejected" for row in rows) == GO1_MU_REJECTED
    p = pairs["identical"]
    header, rows = tables_of(region(p, "Fault lines"))[0]
    assert not p.tree.fault_lines.tested and len(header) == 6 and all(len(row) == 6 for row in rows), header
    p = pairs["one-value"]
    assert [x.reason for x in p.tree.grouping.refused] == ["underpowered", "one_group"]
    lines = lines_of(region(p, "Fault lines"))
    assert "underpowered" in lines[1] and "one_group" in lines[2], lines[:3]
    p = pairs["axes"]
    refused = [x for x in p.tree.grouping.refused if x.key == "task"]
    assert len(refused) == 1 and refused[0].reason == "underpowered" and refused[0].offered_max_group_mde is not None
    assert refused[0].detail in lines_of(region(p, "Fault lines"))[1]
    p = pair("go1-kind", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", by="kind")
    assert [(x.key, x.rung, x.reason) for x in p.tree.grouping.refused] == [("kind", "trace", "unsupported")]
    line = lines_of(region(p, "Fault lines"))[1]
    assert "kind" in line and "trace" in line and "unsupported" in line, line
    assert_fault_lines(p)


# ---------- W10: the cells region ----------


def assert_cells(p: Pair) -> None:
    t = p.structure["tree"]
    leaves, bound = t["leaves"], t["bound"]
    its = region(p, "Cells")
    lines, tables = lines_of(its), tables_of(its)
    head = lines[0]
    if leaves["tested"]:
        assert f'"{leaves["null"]}"' in head and leaves["null"] == CELL_NULL and "tested by BH" in head, (p.name, head)
        for token in (str(leaves["n_families"]), str(leaves["n_tests"]), str(leaves["n_rejected"]), leaves["text"]["q"]):
            assert has(head, token), (p.name, head, token)
    else:
        assert "not tested" in head, (p.name, head)
        forms = {
            "depth": "depth" in head and has(head, str(bound["depth_configured"])) and "root" not in head,
            "root_not_rejected": "the root did not reject" in head,
            "no_group_rejected": "no group rejected" in head,
        }
        assert [k for k, v in forms.items() if v] == [leaves["reason"]], (p.name, head, leaves["reason"])
        assert lines[1:] == [] and tables == [], (p.name, lines, len(tables))
        return
    assert leaves["families"], p.name
    meaning = lines[1]
    assert "increase" in meaning.lower() and "headroom" in meaning.lower() and numeric_tokens(meaning) == [], (p.name, meaning)
    family_lines = lines[2:]
    assert len(family_lines) == len(leaves["families"]), (p.name, family_lines)
    expected_tables = [f for f in leaves["families"] if f["n_rejected"] > 0]
    assert len(tables) == len(expected_tables), (p.name, len(tables), len(expected_tables))
    table_iter = iter(tables)
    for line, family in zip(family_lines, leaves["families"], strict=True):
        assert f"{family['key']}={family['label']}" in line, (p.name, line)
        for token in (str(family["n_tests"]), str(family["n_rejected"]), family["text"]["mde_median"], family["text"]["mde_max"]):
            assert has(line, token), (p.name, line, token)
        assert re.search(rf"\b{family['n_rejected']} rejected\b", line), (p.name, line)
        if family["n_rejected"] == 0:
            continue
        header, rows = next(table_iter)
        assert len(header) == 5, (p.name, header)
        rejected = [c for c in family["cells"] if c["rejects"]]
        assert len(rows) == len(rejected) == family["n_rejected"], (p.name, family["label"], len(rows), family["n_rejected"])
        for row, leaf in zip(rows, rejected, strict=True):
            assert row == [config_cell(leaf), leaf["event"], leaf["text"]["delta"], leaf["text"]["q_within"], f"{leaf['text']['mde']}pp"], (p.name, row, leaf["config"])


def test_w10_the_cells_region_prints_the_head_the_meaning_sentence_one_family_line_per_family_and_one_row_per_rejected_leaf(every_pair: list[Pair]) -> None:
    for p in every_pair:
        assert_cells(p)


def test_w10_the_axes_pair_prints_0_rejected_and_no_table_go1_by_push_keeps_cells_order_the_multi_event_pair_two_fail_rows_and_every_config_key(every_pair: list[Pair]) -> None:
    pairs = by_name(every_pair)
    p = pairs["axes"]
    assert p.tree.leaves.tested and len(p.tree.leaves.families) == 1 and p.tree.leaves.n_rejected == 0
    its = region(p, "Cells")
    assert tables_of(its) == [] and len(lines_of(its)) == 3, lines_of(its)
    assert has(lines_of(its)[2], "0") and "rejected" in lines_of(its)[2]
    p = pair("go1-push", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", by="push_pct_bw")
    assert_cells(p)
    families = {f["label"]: f for f in p.structure["tree"]["leaves"]["families"]}
    seventy = families[GO1_PUSH_UNSORTED_FAMILY]
    rejected = [c for c in seventy["cells"] if c["rejects"]]
    assert len(rejected) == 13
    q_tokens = [c["text"]["q_within"] for c in rejected]
    assert q_tokens != sorted(q_tokens, key=float), q_tokens
    index = [f for f in p.structure["tree"]["leaves"]["families"] if f["n_rejected"] > 0].index(seventy)
    header, rows = tables_of(region(p, "Cells"))[index]
    assert [row[3] for row in rows] == q_tokens, rows
    p = pairs["multi-event"]
    assert [f.label for f in p.tree.leaves.families] == ["t0"] and p.tree.root.events == ("fail", "crash")
    header, rows = tables_of(region(p, "Cells"))[0]
    assert [row[1] for row in rows] == ["fail", "fail"], rows
    p = pairs["three-key"]
    assert p.tree.leaves.tested and p.tree.leaves.n_rejected == 8
    rows = [row for _, rows in tables_of(region(p, "Cells")) for row in rows]
    assert len(rows) == 8 and all("model=" in row[0] and "temp=" in row[0] and "task=" in row[0] for row in rows), rows
    assert {m for row in rows for m in THREE_KEY_MODELS if f"model={m}" in row[0]} == set(THREE_KEY_MODELS), rows
    assert len(p.structure["panels"][0]["cells"]) == 4, p.name


# ---------- W11: the five flags reach the call and refusals bind nothing ----------


def test_w11_the_five_flags_reach_the_call_on_the_axes_pair(synth_root: Path) -> None:
    p = pair("axes-flags", synth_root, "axes-a", "axes-b", ("fail",), "temp", "task", by="temp", max_group_mde=0.6, depth=2, n_permutations=300, seed=3)
    t = p.structure["tree"]
    assert t["grouping"]["requested"] == "temp" and t["grouping"]["resolved_by"] == "requested"
    assert t["bound"]["depth_configured"] == 2 and t["bound"]["depth"] == 2
    assert t["root"]["n_permutations"] == 300 and t["root"]["seed"] == 3
    assert t["grouping"]["max_group_mde"] == 0.6
    assert_fault_lines(p)
    assert_cells(p)
    assert_omnibus(p)
    method_line = lines_of(region(p, "Omnibus"))[1]
    assert has(method_line, "300") and has(method_line, "3") and not has(method_line, str(GOLDEN_PERMUTATIONS)), method_line
    assert has(bound_lines(p.page)[0], "2")


def test_w11_out_of_range_depths_and_refused_knobs_exit_2_with_error_on_stderr_and_serve_page_never_called(synth_root: Path) -> None:
    base = ["--store", str(synth_root), "serve", "axes-a", "axes-b", "--event", "fail", "--x", "temp", "--y", "task"]
    for extra in (["--depth", "1"], ["--depth", "4"], ["--by", "nonsense"], ["--max-group-mde", "2"]):
        for tail in ([], ["--json"]):
            code, out, err, calls = run_serve([*base, *extra, *tail])
            assert code == 2, (extra, tail, code, out[:200], err[-300:])
            assert "error:" in err and "Traceback" not in out + err, (extra, err[-300:])
            assert calls == [], (extra, calls)
            assert out == "", (extra, out[:100])


def test_w11_serve_help_carries_diffs_help_text_for_each_of_the_five_flags() -> None:
    code, serve_help, err = run_cli(["serve", "--help"])
    assert code == 0 and err == "", err
    code, diff_help, err = run_cli(["diff", "--help"])
    assert code == 0 and err == "", err
    serve_entries, diff_entries = help_entries(serve_help), help_entries(diff_help)
    for flag in TREE_FLAGS:
        assert flag in serve_entries, (flag, sorted(serve_entries))
        assert flag in diff_entries, (flag, sorted(diff_entries))
        assert serve_entries[flag] == diff_entries[flag], (flag, serve_entries[flag], diff_entries[flag])


# ---------- W12: a structure never lacks the tree ----------


def test_w12_build_structure_without_tree_is_a_type_error_and_render_html_refuses_a_structure_without_one(go1: Pair) -> None:
    m = viewer()
    store = Store(GO1_ROOT)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    with pytest.raises(TypeError):
        m.build_structure(
            go1.report, go1.multi, manifest_a=ma, manifest_b=mb, rows_a=store.count(GO1_A), rows_b=store.count(GO1_B),
            tally_a=store.tally(GO1_A), tally_b=store.tally(GO1_B), store_root=str(GO1_ROOT),
        )
    for retired_schema in RETIRED_SCHEMAS:
        retired = {k: v for k, v in json.loads(json.dumps(go1.structure, allow_nan=False)).items() if k != "tree"}
        retired["schema"] = retired_schema
        with pytest.raises(m.ViewerError) as info:
            m.render_html(retired)
        assert retired_schema in str(info.value) and SCHEMA in str(info.value), retired_schema
    headless = {k: v for k, v in json.loads(json.dumps(go1.structure, allow_nan=False)).items() if k != "tree"}
    with pytest.raises(m.ViewerError) as info:
        m.render_html(headless)
    assert "tree" in str(info.value)


def test_w12_every_pairs_serve_json_carries_the_tree_with_no_flag(every_pair: list[Pair]) -> None:
    for p in every_pair:
        assert "tree" in p.structure and set(p.structure["tree"]) == {"root", "grouping", "fault_lines", "leaves", "bound", "agreement"}, p.name
        assert p.structure["tree"]["bound"]["bound"] > 0, p.name


# ---------- W13: determinism, and what a seed may move ----------

#: The paths a different seed may move (S27 L19, S26 F27): the seed, the root's p-driven fields,
#: everything under the two tested levels, and the ``text`` twins of each. ``grouping`` is shape
#: only (F7) and ``bound`` is byte-identical across seeds (L8).
SEED_MAY_MOVE = ("tree.root.seed", "tree.root.p_location", "tree.root.p_dispersion", "tree.root.p_omnibus", "tree.root.rejects", "tree.root.headline", "tree.root.text", "tree.fault_lines", "tree.leaves")


def test_w13_two_builds_are_equal_two_renders_identical_and_a_seed_moves_only_what_l19_and_f27_allow(go1: Pair) -> None:
    store = Store(GO1_ROOT)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    kwargs = dict(manifest_a=ma, manifest_b=mb, rows_a=store.count(GO1_A), rows_b=store.count(GO1_B), tally_a=store.tally(GO1_A), tally_b=store.tally(GO1_B), store_root=str(GO1_ROOT))
    first = viewer().build_structure(go1.report, go1.multi, tree=go1.tree, **kwargs)
    second = viewer().build_structure(go1.report, go1.multi, tree=go1.tree, **kwargs)
    assert first == second
    assert viewer().render_html(first) == viewer().render_html(second) == go1.page
    seeded = pair("go1-seed1", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", seed=1)
    moved = diff_paths(seeded.structure, go1.structure)
    assert moved, "seed 1 moved nothing on Go1"
    stray = [path for path in moved if not any(path == prefix or path.startswith(prefix + ".") for prefix in SEED_MAY_MOVE)]
    assert stray == [], stray[:10]
    assert seeded.structure["tree"]["grouping"] == go1.structure["tree"]["grouping"]
    assert seeded.structure["tree"]["bound"] == go1.structure["tree"]["bound"]


# ---------- W14: hostile values are escaped ----------


def test_w14_hostile_task_values_render_as_text_in_the_cells_region_and_ride_verbatim_in_the_structure(every_pair: list[Pair]) -> None:
    p = by_name(every_pair)["hostile"]
    assert p.tree.leaves.tested and p.tree.leaves.n_rejected == 2
    dom = parse_html(p.page)
    scripts = dom.find("script")
    assert len(scripts) == 3 and all(n.attrs.get("id") in ("proofload-cells", "proofload-holes", None) for n in scripts), [n.attrs for n in scripts]
    assert not any("onerror" in n.attrs for n in dom.nodes)
    assert dom.find("img") == []
    lines = p.page.splitlines()
    for heading in NEW_REGIONS:
        for line in region_lines(p.page, heading):
            assert "<script" not in line and "<img" not in line and "</table><script>" not in line, line[:80]
    rows = [row for _, rows in tables_of(region(p, "Cells")) for row in rows]
    for value in HOSTILE_VALUES:
        assert any(value in row[0] for row in rows), (value, rows)
    configs = [c["config"]["task"] for f in p.structure["tree"]["leaves"]["families"] for c in f["cells"]]
    assert set(configs) == set(HOSTILE_VALUES), configs
    assert sum(line.count("<table>") for line in lines) == sum(line.count("</table>") for line in lines)


def test_w14_a_hostile_value_in_a_group_label_renders_as_text_on_a_pair_whose_grouping_admits_the_axis(synth_root: Path) -> None:
    """Section 3.2's 2026-09-12 invariant, the one A27 gives a fixture and a test.

    The first assertion is the precondition and is not decoration: on every other pair in this
    oracle the grouping collapses to ``whole_grid`` and the one label reads ``all``, which is why
    mutant 31b survived S29. If a later power-rule change returns this fixture to the collapse,
    that assertion fails here rather than the guard below passing over a label that carries
    nothing. The round-trip clauses alone do not separate an escaped cell from a raw one -- an
    unescaped ``</table><script>...`` is also what ``html.unescape`` returns -- so the parsed-DOM
    and table-balance clauses are what carry the safety claim, and the round-trip carries the
    correctness one: the value the page shows is the value the structure holds.
    """
    p = pair("hostile-group", synth_root, "hgroup-a", "hgroup-b", ("fail",), "cell", "task")
    grouping = p.structure["tree"]["grouping"]
    assert (grouping["key"], grouping["resolved_by"], grouping["n_groups"], grouping["n_resolvable_groups"]) == HOSTILE_GROUP_ADMITTED
    assert grouping["labels"] == list(HOSTILE_VALUES)
    assert p.structure["tree"]["fault_lines"]["n_rejected_groups"] == HOSTILE_GROUP_REJECTED_GROUPS
    assert (p.tree.leaves.n_families, p.tree.leaves.n_tests, p.tree.leaves.n_rejected) == (HOSTILE_GROUP_FAMILIES, HOSTILE_GROUP_TESTS, HOSTILE_GROUP_REJECTED)
    label_cells = [row[0] for _, rows in tables_of(region(p, "Fault lines")) for row in rows]
    assert label_cells == list(HOSTILE_VALUES), label_cells
    family_lines = [line for line in lines_of(region(p, "Cells")) if line.startswith("task=")]
    assert [line.startswith(f"task={value}: ") for line, value in zip(family_lines, HOSTILE_VALUES, strict=True)] == [True, True], family_lines
    dom = parse_html(p.page)
    scripts = dom.find("script")
    assert len(scripts) == 3 and all(n.attrs.get("id") in ("proofload-cells", "proofload-holes", None) for n in scripts), [n.attrs for n in scripts]
    assert not any("onerror" in n.attrs for n in dom.nodes)
    assert dom.find("img") == []
    guarded = region_lines(p.page, "Fault lines") + region_lines(p.page, "Cells")
    assert sum(line.count("<table>") for line in guarded) == sum(line.count("</table>") for line in guarded) == HOSTILE_GROUP_FAMILIES + 1


# ---------- W15: strict JSON ----------


def test_w15_the_dump_parses_strictly_with_the_tree_and_every_serialiser_passes_allow_nan_false(go1: Pair) -> None:
    code, out, err, calls = run_serve(["--store", str(GO1_ROOT), *SERVE_ARGV])
    assert code == 0 and calls == [], err
    parsed_out = strict_loads(out)
    assert "tree" in parsed_out and out.startswith('{\n  "schema": ')
    strict_loads(json.dumps(go1.structure, allow_nan=False))
    viewer_tree = parsed(VIEWER_SOURCE)
    cli_tree = parsed(CLI_SOURCE)
    calls_ = json_dumps_calls([viewer_tree]) + json_dumps_calls(closure(cli_tree, "_cmd_serve"))
    assert len(calls_) >= 2, len(calls_)
    for call in calls_:
        flags = {kw.arg: getattr(kw.value, "value", None) for kw in call.keywords}
        assert flags.get("allow_nan") is False, (call.lineno, flags)


# ---------- W16: a tree from another pair is refused ----------


def test_w16_a_tree_from_another_pair_is_refused_with_viewer_error_naming_the_events_or_the_cell_count(go1: Pair, synth_root: Path) -> None:
    m = viewer()
    _, axes_tree = store_tree(synth_root, "axes-a", "axes-b", events=("fail",))
    store = Store(GO1_ROOT)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    kwargs = dict(manifest_a=ma, manifest_b=mb, rows_a=store.count(GO1_A), rows_b=store.count(GO1_B), tally_a=store.tally(GO1_A), tally_b=store.tally(GO1_B), store_root=str(GO1_ROOT))
    with pytest.raises(m.ViewerError) as info:
        m.build_structure(go1.report, go1.multi, tree=axes_tree, **kwargs)
    message = str(info.value).lower()
    assert "event" in message or "cell" in message, message
    # A28: re-grown under another seed rather than another method -- section 10 Q5 (b) makes a
    # mcnemar_bh tree beside a fisher_bh diff a refusal, and the point here is that the same events
    # and the same cells are accepted whatever knob the digest ignores.
    _, same_events = store_tree(GO1_ROOT, GO1_A, GO1_B, events=("fell",), seed=7)
    assert m.build_structure(go1.report, go1.multi, tree=same_events, **kwargs)["tree"]["root"]["seed"] == 7


def test_w16_a_tree_whose_cells_are_another_pairs_is_refused_at_the_same_arity_and_the_message_names_a_cell(every_pair: list[Pair]) -> None:
    """Section 4 W16's second clause, amended 2026-09-12: the ``(event, config_hash)`` multiset,
    not the arity. The crossed pair is this oracle's own vocabulary and hostile pairs -- same one
    event, two cells each, different ``task`` values and so different hashes -- measured at
    ``101028c`` as **accepted** by the arity clause, which is the hole. The second assertion is
    what keeps the first from passing for the wrong reason: the arity is equal, so a refusal here
    cannot be the old clause firing."""
    m = viewer()
    pairs = by_name(every_pair)
    vocab, hostile = pairs["vocab"], pairs["hostile"]
    store = Store(vocab.root)
    kwargs = dict(manifest_a=store.manifest(vocab.a), manifest_b=store.manifest(vocab.b), rows_a=store.count(vocab.a), rows_b=store.count(vocab.b), tally_a=store.tally(vocab.a), tally_b=store.tally(vocab.b), store_root=str(vocab.root))
    assert tuple(hostile.tree.root.events) == tuple(vocab.multi.events)
    assert len(hostile.tree.root.units) == vocab.multi.n_tests == len(vocab.tree.root.units)
    with pytest.raises(m.ViewerError) as info:
        m.build_structure(vocab.report, vocab.multi, tree=hostile.tree, **kwargs)
    message = str(info.value)
    absent = sorted(set(hostile.tree.root.units["config_hash"]) - set(vocab.tree.root.units["config_hash"]))
    assert any(h in message for h in absent), (message, absent)
    assert m.build_structure(vocab.report, vocab.multi, tree=vocab.tree, **kwargs)["tree"]["grouping"]["labels"] == ["all"]


# ---------- W18: golden, Go1 ----------


def test_w18_go1_renders_twenty_group_rows_nineteen_rejected_nineteen_families_and_the_golden_leaf_counts(every_pair: list[Pair]) -> None:
    pairs = by_name(every_pair)
    fisher = pairs["go1"]
    header, rows = tables_of(region(fisher, "Fault lines"))[0]
    assert len(rows) == GO1_MU_GROUPS and sum(row[-1] == "rejected" for row in rows) == GO1_MU_REJECTED
    cells = region(fisher, "Cells")
    assert len(lines_of(cells)) == 2 + GO1_MU_REJECTED
    assert sum(len(rows) for _, rows in tables_of(cells)) == GO1_FISHER_LEAVES
    assert has(bound_lines(fisher.page)[0], BOUND_AT_DEPTH_3)
    mcnemar = pairs["go1-mcnemar"]
    assert mcnemar.tree.root.scheme == "pair_swap"
    assert sum(len(rows) for _, rows in tables_of(region(mcnemar, "Cells"))) == GO1_MCNEMAR_LEAVES
    grid = pair("go1-grid", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", by="grid")
    cells = region(grid, "Cells")
    assert len(lines_of(cells)) == 3 and "whole_grid=all" in lines_of(cells)[2]
    assert sum(len(rows) for _, rows in tables_of(cells)) == GO1_GRID_LEAVES
    assert has(bound_lines(grid.page)[0], BOUND_AT_DEPTH_2)
    push = pair("go1-push", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", by="push_pct_bw")
    family_lines = lines_of(region(push, "Cells"))[2:]
    counts = tuple(int(re.search(r"(\d+) rejected", line).group(1)) for line in family_lines)  # type: ignore[union-attr]
    assert counts == GO1_PUSH_FAMILIES and tuple(f.n_rejected for f in push.tree.leaves.families) == GO1_PUSH_FAMILIES, counts


# ---------- W19: vocabulary ----------


def test_w19_no_line_of_the_three_regions_or_the_bound_paragraph_and_no_tree_string_uses_the_forbidden_vocabulary_after_masking(every_pair: list[Pair]) -> None:
    for p in every_pair:
        for text in walk_strings(p.structure["tree"]):
            low = masked(text, p)
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in low, (p.name, phrase, text[:80])
        joined = masked(new_region_text(p), p)
        for phrase in FORBIDDEN_VOCABULARY:
            assert phrase not in joined, (p.name, phrase)
        assert f'"{ROOT_NULL}"' in region_text(region(p, "Omnibus")), p.name
        assert f'"{GROUP_NULL}"' in region_text(region(p, "Fault lines")), p.name
        if p.tree.leaves.tested:
            assert f'"{CELL_NULL}"' in region_text(region(p, "Cells")), p.name
        rule, assumption = bound_lines(p.page)
        assert "outer-nodes" in rule and "false discovery rate" in rule and "fdr" not in (rule + assumption).lower(), (p.name, rule)
        for token in (str(p.structure["tree"]["bound"]["depth"]), str(p.structure["tree"]["bound"]["depth_configured"]), p.structure["tree"]["bound"]["text"]["bound"], p.structure["tree"]["bound"]["text"]["q"], p.structure["tree"]["bound"]["text"]["delta_star"]):
            assert has(rule, token), (p.name, rule, token)
        assert any(word in assumption.lower() for word in ("assum", "independen")), (p.name, assumption)


def test_w19_the_vocabulary_pair_renders_green_under_the_mask_and_red_without_it(every_pair: list[Pair]) -> None:
    """The proof that the mask is applied: a pair whose ``task`` values are ``given the root`` and
    ``where it broke`` renders both values into the leaf rows; the masked check is green and the
    unmasked scan finds both phrases. A test whose mask is missing is red here."""
    p = by_name(every_pair)["vocab"]
    assert p.tree.root.rejects and p.tree.leaves.tested and p.tree.leaves.n_rejected == 2
    text = new_region_text(p)
    unmasked = text.lower()
    assert all(v in unmasked for v in VOCABULARY_VALUES), text[:200]
    low = masked(text, p)
    for phrase in FORBIDDEN_VOCABULARY:
        assert phrase not in low, phrase
    assert any(phrase in unmasked for phrase in FORBIDDEN_VOCABULARY)


# ---------- W20: nothing else moves ----------


def e14_builder_digests() -> dict[str, str]:
    """S21's E14 as S28's retrofit left it: the tree-less builder's markdown and light receipt."""
    store = Store(GO1_ROOT)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    multi = quiet_multi_diff(store.read(GO1_A, meta=False), store.read(GO1_B, meta=False), ma, mb, events=("fell",), method="fisher_bh")
    spec = ReportSpec(title=f"{GO1_A} vs {GO1_B}: fell", x_axis="mu", y_axis="push_pct_bw")
    report = build_multi_report(multi, spec, manifests=(ma, mb))
    receipt = build_multi_report(multi, replace(spec, theme="light"), manifests=(ma, mb))
    return {"report.md": sha256_of_text(report.to_markdown()), "receipt.html": sha256_of_text(receipt.to_html())}


def test_w20_diff_py_whole_report_py_outside_check_tree_tree_py_outside_root_result_and_root_check_and_the_e14_family_are_unchanged(tmp_path: Path) -> None:
    assert hashlib.sha256(DIFF_SOURCE.read_bytes()).hexdigest() == DIFF_PY_SHA256
    assert hashlib.sha256(REPORT_SOURCE.read_bytes()).hexdigest() == REPORT_PY_SHA256
    assert digest_excluding(TREE_SOURCE, [q for record in TREE_PY_EXCLUDED for q in record["region"]]) == TREE_PY_SHA256
    assert hashlib.sha256(TREE_SOURCE.read_bytes()).hexdigest() != TREE_PY_SHA256
    for record in TREE_PY_EXCLUDED:
        cover = REPO / record["cover"][0]
        assert cover.exists(), record["cover"]
        for test_id in record["cover"][1]:
            resolve_region(ast.parse(cover.read_bytes()), test_id)
    code, out, err = run_cli(["--store", str(GO1_ROOT), *CHECK_ARGV])
    assert code == CHECK_EXIT and err == "" and sha256_of_text(out) == CHECK_STDOUT_SHA256, (code, err)
    out_dir = tmp_path / "report"
    code, out, err = run_cli(["--store", str(GO1_ROOT), *E14_ARGV, "--out", str(out_dir)])
    assert code == 0, out + err
    assert hashlib.sha256((out_dir / "heatmap.svg").read_bytes()).hexdigest() == E14_SHA256["heatmap.svg"]
    for name, digest in e14_builder_digests().items():
        assert digest == E14_SHA256[name], name


def test_w20_the_viewers_import_partition_and_v17s_closure_clauses_are_unchanged() -> None:
    """V35 restated: ``from proofload.report`` imports exactly the eight names, split between the
    two closures by set equality; ``proofload.tree`` is imported only under ``TYPE_CHECKING``;
    ``render_html``'s closure applies no arithmetic and formats nothing; ``build_structure``'s
    applies exactly the ``created_at`` subtraction (so the ``text`` decoration is ``_fmt`` calls
    and dict construction, never arithmetic)."""
    module = parsed(VIEWER_SOURCE)
    source = VIEWER_SOURCE.read_text(encoding="utf-8")
    assert report_import_names(module) == ASSEMBLY_HELPERS | RENDER_HELPERS
    build = referenced_names(closure(module, "build_structure"))
    render = referenced_names(closure(module, "render_html"))
    assert build & (ASSEMBLY_HELPERS | RENDER_HELPERS) == ASSEMBLY_HELPERS, build
    assert render & (ASSEMBLY_HELPERS | RENDER_HELPERS) == RENDER_HELPERS, render
    for name in ("MultiReport", "Report", "DiffResult", "DataFrame", "TreeResult", "multi", "report"):
        assert name not in render, name
    assert module_body_imports_of(module, "proofload.tree") == [], module_body_imports_of(module, "proofload.tree")
    assert arithmetic_nodes(closure(module, "render_html")) == [], [ast.dump(n)[:60] for n in arithmetic_nodes(closure(module, "render_html"))]
    build_nodes = closure(module, "build_structure")
    arithmetic = arithmetic_nodes(build_nodes)
    assert len(arithmetic) == 1 and isinstance(arithmetic[0], ast.BinOp) and isinstance(arithmetic[0].op, ast.Sub), [ast.dump(n)[:60] for n in arithmetic]
    assert arithmetic[0] in total_seconds_operands(build_nodes)
    assert format_calls(module) == [] and not FLOAT_SPEC_RE.search(source) and not HEX_RE.search(source)


def test_w20_the_exclusion_record_is_one_constant_per_narrowed_file_with_every_adr_077_field() -> None:
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

    **A28's retrofit, 2026-09-13 -- both ``diff.py`` exclusions retired, one ``report.py`` exclusion
    minted.** ``_pairing`` and ``_coverage`` both named ``A28``; both owners have landed and A28
    rewrites every carrier, so ``DIFF_PY_SHA256`` is whole-file again. ``REPORT_PY_EXCLUDED`` is
    this packet's own, owner A28, ``retire_at`` empty (spec A28 D5), seven fields -- the entry's six
    plus ``lines`` (ADR-077 Q2, lean (b)). The sweep now finds this file alone, **counted over
    module-level constants named ``*_PY_EXCLUDED`` by AST and not by text**, because the text grep
    the entry describes counts the three former carriers from their docstrings and sweep lines
    once their records are gone (measured). ``TREE_PY_EXCLUDED`` is not minted (section 10 Q2 (b)).

    **P-1's retrofit, 2026-09-17: ``TREE_PY_EXCLUDED`` minted beside ``REPORT_PY_EXCLUDED``** (P-1
    section 7.4). Still one file, now two record constants on it, so the sweep asserts the pair by
    name; the per-record assertions are per record (owner A28 at ``38e8df9``; owner P-1 at
    ``a626cd3``), and ``lines`` may carry two spans because ADR-077 Q2 (b)'s form lists every span
    the record excludes. ``REPORT_PY_EXCLUDED`` is retirable -- A28 is done and P-1 is the first
    re-freeze to reach its carrier -- and P-1 section 7.4 retires it in Session A's post-build
    commit, when ``REPORT_PY_SHA256`` becomes whole-file off the built ``report.py``; until then it
    stays, so this sweep will move once more.
    """
    hits = sorted(path.name for path in sorted((REPO / "tests").glob("test_*.py")) if excluded_constants(path))
    assert hits == ["test_s29_viewer.py"], hits
    # Module order: ``TREE_PY_EXCLUDED`` sits beside ``TREE_PY_SHA256``, which precedes the report pair.
    assert excluded_constants(REPO / "tests" / "test_s29_viewer.py") == ["TREE_PY_EXCLUDED"]
    for constant, owner, minted_at in ((TREE_PY_EXCLUDED, "P-1", "a626cd3"),):
        for record in constant:
            assert set(record) == {"region", "owner", "cover", "minted_at", "blind_spot", "retire_at", "lines"}, sorted(record)
            assert record["owner"] == owner and record["minted_at"] == minted_at and record["retire_at"] == ""
            assert len(record["blind_spot"].split()) >= 20, record["region"]
            assert re.fullmatch(r"\d+-\d+(, \d+-\d+)* of \d+", record["lines"]), record["lines"]
    assert [record["region"] for record in TREE_PY_EXCLUDED] == [("RootResult", "_root")]
    for source, constant in ((TREE_SOURCE, TREE_PY_EXCLUDED),):
        spans = sorted(
            (node.lineno, node.end_lineno)
            for node in (resolve_region(ast.parse(source.read_bytes()), q) for record in constant for q in record["region"])
        )
        assert all(earlier[1] < later[0] for earlier, later in zip(spans, spans[1:])), spans
