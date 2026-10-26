"""S27 -- the leaves and the bound: the oracle for L1-L24.

Written from "Proofload -- Spec S27 Layered Report P4.3 Leaves and the Bound" section 4 and
"Handoff P4.3", against ``6fd3b9c`` (2026-09-08). Session B adds four dataclasses, two fields on
``TreeResult`` with no defaults, the leaf pass, the bound function, ``depth`` on ``tree`` and
``MIN_FAMILY_GROUPS`` at three sites to ``src/proofload/tree.py``, and one flag, two blocks and
two keys inside ``"tree"`` to ``src/proofload/cli.py``, against this file, and does not edit it.

**``proofload.tree``'s new names are imported inside each test body**, the way the S25 and S26
oracles reached the module before it existed: this file collects on the bare tree, its own tests
fail there, and every other test in the repo still reports. The static tests read the source as
text; the pins on P4.2's build (L12, L13, L20) and the static guards (L11, L14's static clause)
are green on the bare tree by design.

**No test in this file carries the ``calibration`` marker, and none may.** Level 3 draws
nothing: a leaf's ``p`` is the flat family's own per-cell test read from ``cells``, and BH
within a family is arithmetic on those numbers, so every Level 3 wiring error is caught
deterministically (L2-L7, L21-L23) and there is no rejection rate to hold in a band. Spec
section 0.4's outer-nodes FDR on a known mixture is a step-zero script
(``log/phase4-p43-step-zero-slow.py``, twenty-four minutes), not a lane.

**Step zero, re-derived before a test was written** (``scratchpad/s27_step_zero.py``, 30 s
against the bare tree; every number below is that script's). The grep report is in Handoff
P4.3's *Session A's grep report* section, not here.

1. **The multi-event pair could not be sized as spec section 6 writes it.** Eight ``task``
   groups of two cells at N=32 are 64 units per arm per group, and ``mde_two_proportion(0.5, 64,
   64, alpha=q/8)`` is **0.2981**, above 0.20: ``task`` is refused and the grouping falls to
   ``temp``. The 0.1396 the spec quotes is the imported pair's eight groups of *320* units. Sized
   here at **N=128** (256 units per arm, group MDE 0.1557 at q/8, admitted with no override) with
   the moved cells scaled by four: arm a ``fail x16 + ok x112``, arm b ``fail x80 + ok x48``.
   Under both schemes the root and ``t0`` sit at the floor (``q_group`` 0.0020), ``t0`` is the
   only rejecting group, and its family is exactly ``2 x 2``: the two ``fail`` rows at p
   1.08e-19 (McNemar) / 4.82e-17 (Fisher) reject, the two ``crash`` rows sit at p 1 with
   ``events_a == events_b == 0``.
2. **"``crash`` present in neither arm of any cell" cannot pass ``main()``.** The CLI's event
   guard refuses an ``--event`` absent from *both* frames (H6), so the stored pair carries
   ``crash`` at one replicate in four of every cell *outside* ``t0``, identical across arms.
   ``t0``'s family is byte-identical with and without it (measured, both schemes); the in-memory
   fixture L22 asserts on keeps the spec's literal shape and the store carries the variant, and
   L22 asserts that ``crash`` occurs in neither arm of either ``t0`` cell.
3. **The gate fixture's margin**, forty ``grp`` x six ``cell`` at N=64 with eight discordant
   pairs one way in ``g00 c0``, ``mcnemar_bh``, B=4000: ``grp`` admitted (group MDE 0.1449 at
   q/40); root p 0.0070 / 0.0067 / 0.0072 on seeds 0-2; ``g00``'s ``q_group`` **0.2799 /
   0.2699 / 0.2899**, not rejected; the moved leaf's ``q_within`` **0.046875** exact (``6 x
   2^(1-8)``). A group rejection needs the count of draws reaching the observed statistic
   below ``q/40 * (B+1) - 1 = 4.00125`` -- **at most four**, not "fewer than four" as section
   0.7 rounds it -- and the count was 27 / 26 / 28 where 30.26 are expected. No seed is near
   0.15. Under ``fisher_bh`` the root sits at p 0.98 and the level is untested, so the fixture
   is McNemar-only and says so.
4. **The lattice's leaf counts** (``tests/lattice.py``, re-measured on the unchanged build)
   reproduce from ``cells`` and the partition: by ``load`` the three rejecting groups ``10.0``,
   ``20.0``, ``30.0`` give (10, 11, 1) = 22 under Fisher and (10, 11, 8) = 29 under McNemar,
   the flat 22 / 27 inside them (equal under Fisher, strictly inside under McNemar); by
   ``gain`` under Fisher the conditions ``gain = 0.2``, ``0.3`` and ``1.0`` at ``load = 30``
   are rejected leaves the flat family does not reject, and ``gain = 1.2, load = 20`` is
   rejected by the flat family and not in its family of six, whose group rejects; under
   McNemar the nested 28 by ``gain`` strictly contain the flat 27, and ``1.2`` rejects as a group
   with no flat-flagged condition inside it (its family is present with 0 rejected). The nine
   floor groups by
   ``gain`` (``0.1``-``0.8`` and ``1.0``) contribute (3, 3, 3, 2, 2, 2, 2, 2, 3) under Fisher and
   (3, 3, 3, 3, 3, 3, 2, 3, 3) under McNemar; ``0.9`` and ``1.2`` are pinned only through the
   recompute (``1.2`` rejects off the floor), and ``1.1`` does not reject. One family over the
   union of the rejecting groups' cells reads 25 / 30 (``load``) and 23 / 27 (``gain``), never
   the per-group set. ``load = 20.0``'s eleven rejected leaves have an unsorted
   ``q_within`` sequence. Under the whole grid ``q_within`` is ``cells.q`` bit for bit under
   all three methods.
5. **The collision scan** (spec section 0.8, re-run at ``6fd3b9c``). Attributes inside an
   ``ast.BinOp`` in ``cli.py``: ``dumps`` (994, 1274), **``event`` (1318)**, ``headline``
   (769), ``join``, ``replace`` (904), ``rstrip`` (1401), ``splitlines`` (768),
   ``to_markdown`` (768), ``values`` (998). Bare names: ``cells`` (1401, F21's collision),
   ``col``, ``cols``, ``coverage``, ``df``, ``done``, ``header``, ``lines``, ``multi``, ``n``,
   ``name``, ``ns``, ``others``, ``out_dir``, ``payload``, ``primary``, ``record``,
   ``structure``, ``total``, ``trade``, plus type and helper names. **``event`` at
   ``cli.py:1318`` is the only P4.3 field name the scan reaches as an attribute**, so it is
   unguarded, with the other string fields (``config_hash``, ``label``, ``key``, ``group``,
   ``reason``, ``null``, ``discoveries``), as ``P43_STRING_FIELDS`` records; every numeric and
   container field of the nine structures is guarded as an attribute; the P4.3 bare names
   that collide with nothing are guarded as names. No ``Compare`` in ``cli.py`` names
   ``depth`` and no constant 1.44 / 0.432 / 0.288 / 0.144 exists in either file today. **The
   gap for an L11 sole catch is narrower than spec section 7 says**: ``cli.py`` carries a third
   older arithmetic guard, S24's C19, whose six names include ``n_rejected``, so a mutant on
   ``family.n_rejected`` (Handoff P4.3's 28d) is caught by C19 beside L11; the names L11 alone
   owns are ``depth``, ``depth_configured``, ``delta_star``, ``bound``, ``q_within``,
   ``n_families``, ``mde_median``, ``mde_max``, and ``n_tests`` / ``rejected`` / ``cells`` /
   ``families`` / ``leaves`` as attributes of a P4.3 object (mutation table, rows 28c-28h).

**Spec text this oracle could not use as written, each resolved here and reported.**

- Section 6's multi-event pair at N=32 (item 1) and its ``crash`` posture through the CLI
  (item 2).
- Section 0.7's "fewer than four of the 4000 draws" is "at most four" (item 3); the fixture's
  precondition is asserted as ``q_group >= 0.15``, section 6's number.
- L9's "exactly one ``BinOp`` chain producing the bound" is read as: the function that reads
  ``DELTA_STAR`` contains exactly one top-level ``BinOp`` (one whose parent is not a
  ``BinOp``) and that chain reaches ``DELTA_STAR``. The depth reduction is itself a ``BinOp``,
  so it lives in another function (the third reader of ``MIN_FAMILY_GROUPS``) or in ``tree``.
- L10(b)'s "``Bound`` has exactly the six fields" is exact; ``CellResult``, ``CellFamily`` and
  ``Leaves`` are asserted as supersets of section 2's lists, S26's convention for a later
  packet's addition, and every field name of all four is checked for the forbidden substrings.
- L13's "the block's ``refused`` line names all four" needs a stored pair where one manifest
  declares an axis the other does not; the lattice's store is generated as it is, so the synthetic
  store carries ``axes-b-task-only`` (the moved frame declaring ``task`` alone) and ``--by
  temp`` against ``axes-a`` produces the ``not_shared`` row at the requested rung.
- L20's "untouched (``git diff --exit-code tests/``)" is pinned as the sha256 of the two frozen
  oracles' bytes at ``6fd3b9c``, F28's form for ``diff.py``, which a scratch copy without
  ``.git`` can check; ``tree``'s signature is pinned by parameter names, kinds and defaults so
  the new keyword is the only change.

**Conventions this oracle fixes where the spec is silent. Session B builds to these.**

- A family line is a line of the ``cells:`` block indented by exactly two spaces; a leaf line
  is indented by four or more (section 3.8's example). Family lines come in ``families``
  order and each family's leaf lines follow its own line, in ``cells`` order.
- On an untested level the ``cells:`` block is its head line alone; the head says ``not
  tested`` and, for ``"depth"``, carries ``depth_configured`` under ``:g``; for the other two
  reasons the words ``root`` and ``group`` respectively are on the line. Wording is otherwise
  free.
- A config value on a leaf line may render as ``str(value)`` or under ``:g``; either form of
  every value is accepted as a config token, and a leaf line's numeric tokens are exactly
  ``delta``, ``q_within``, ``mde`` under ``:g`` plus those.
- The family line's count is checked as the token ``n_rejected`` under ``:g`` beside the word
  ``rejected``; O18's verdict words are not required on a family line.
- Under the one-group collapse the family's ``key`` is ``whole_grid`` and its ``label`` is
  ``all`` -- ``Grouping.key`` and ``Grouping.labels[0]``, the same two fields a
  ``CellFamily`` carries for every other group.
- L10(a) masks, before it looks, the requested key, every group label, every config value and
  every event name (user data), and reads the rest case-insensitively.

**Named non-observables.** A leaf's ``delta`` read from ``units.delta`` instead of
``cells.delta`` (Handoff P4.3 mutant 2): the two coincide on every input any builder in this
suite can make, because ``multi_diff`` censors only at the horizon, so no fixture separates
them and L2's bit-equality pins the ``cells`` one without being able to prove the source read
it. A second ``multi_diff`` call in the leaf pass on the same frames (mutant 30): same bytes.
The bound's assumption (spec section 0.3): a property of the source, not of any output.
"""
from __future__ import annotations

import ast
import functools
import dataclasses
import hashlib
import importlib
import inspect
import json
import math
import re
import time
import warnings
from collections.abc import Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import poisson_prove
from poisson_prove import cli
from poisson_prove import diff as diff_mod
from poisson_prove.diff import multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import ReportSpec, build_multi_report
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash
from conftest import code_of

import lattice

PACKAGE = Path(poisson_prove.__file__).resolve().parent
REPO = PACKAGE.parents[1]
#: The generated pair (``tests/lattice.py``) every lattice test below reads.
LATTICE_ROOT = lattice.root()
LATTICE_A, LATTICE_B = lattice.RUN_A, lattice.RUN_B
# PF2 (spec section 4.3): every run has a name (target id up to its first "/", the UTC date of
# created_at, a letter); serve names the lattice's runs by these.
LATTICE_NAME_A, LATTICE_NAME_B = lattice.NAME_A, lattice.NAME_B
EVENT, X, Y = lattice.EVENT, lattice.X, lattice.Y
TREE_SOURCE = PACKAGE / "tree.py"
CLI_SOURCE = PACKAGE / "cli.py"
DIFF_SOURCE = PACKAGE / "diff.py"
METHODS = ("fisher_bh", "mcnemar_bh", "logrank_bh")
TWO_SCHEMES = ("mcnemar_bh", "fisher_bh")

#: Spec section 2, this file's literals (L1). Never read back from the module.
EXPECTED_DEFAULT_DEPTH = 3
EXPECTED_DEPTHS = (2, 3)
EXPECTED_DELTA_STAR = 1.44
EXPECTED_BOUND_DISCOVERIES = "outer_nodes"
EXPECTED_MIN_FAMILY_GROUPS = 2
EXPECTED_MIN_RESOLVABLE_GROUPS = 2
EXPECTED_CELL_NULL = "this cell did not change"
EXPECTED_LEAVES_NOT_TESTED_REASONS = ("depth", "root_not_rejected", "no_group_rejected")
EXPECTED_WHOLE_GRID = "grid"
EXPECTED_WHOLE_GRID_KEY = "whole_grid"
EXPECTED_WHOLE_GRID_LABEL = "all"
Q = 0.05
#: PF4 re-freeze (PF4.45): a group's limit is its cells' own unconditional limit, so the default does
#: not admit the lattice's ``gain``, the gate fixture's ``grp`` or the multi-event pair's ``task``; the
#: fixtures that test those levels accept this value, which admits every group whose limit is below
#: it (the range check refuses 1).
ADMITTING_MAX_GROUP_MDE = 0.99
#: L8: the bound is recomputed from the constants and compared to this.
BOUND_TOLERANCE = 1e-15
#: L9: the constant and the three numbers it produces at q 0.05, forbidden as literals.
FORBIDDEN_BOUND_CONSTANTS = (1.44, 0.432, 0.288, 0.144)

GOLDEN_PERMUTATIONS = 4000
GOLDEN_SEED = 0
#: O13's cost pin, extended by F30 and here by L14 and L24.
REFUSAL_PERMUTATIONS = 10**6
REFUSAL_BUDGET_SECONDS = 10.0

#: L10(a). O19's nine phrases, F19's nine additions, and this packet's six; case-insensitive.
FORBIDDEN_VOCABULARY = (
    "given the root", "given that", "conditional on", "leaf", "fdr", "broke", "where it broke",
    "failed at", "step",
    "broken", "failed in", "where it", "culprit", "root cause", "power stays high", "high power",
    "well powered", "same shift",
    "given the group", "given a group", "given that the group", "reliable", "controlled at q", "at level q",
)
#: L10(b). F19's six plus this packet's four, on field names and JSON keys under ``leaves`` / ``bound``.
FORBIDDEN_FIELD_SUBSTRINGS = ("interval", "level", "leaf", "broke", "where", "step", "given", "conditional", "rate", "fdr")

#: The fields of the four new structures and of ``TreeResult`` (spec section 2), as literals.
CELL_RESULT_FIELDS = ("config_hash", "config", "event", "group", "n_a", "n_b", "events_a", "events_b", "delta", "p", "q_within", "rejects", "mde")
CELL_FAMILY_FIELDS = ("label", "key", "n_tests", "n_rejected", "rejected", "mde_median", "mde_max", "cells")
LEAVES_FIELDS = ("tested", "reason", "null", "q", "n_families", "n_tests", "n_rejected", "families")
BOUND_FIELDS = ("depth_configured", "depth", "q", "delta_star", "bound", "discoveries")
TREE_RESULT_FIELDS = ("root", "grouping", "fault_lines", "leaves", "bound", "agreement")
#: S26's five structures, restated (L11 guards every one of their fields as an attribute, as F21 does).
REFUSAL_FIELDS = ("key", "rung", "reason", "detail", "next_rung", "n_groups", "n_resolvable_groups", "offered_max_group_mde")
GROUPING_FIELDS = (
    "key", "resolved_by", "requested", "labels", "groups", "n_groups", "group_sizes", "size_min", "size_median",
    "size_max", "alpha_floor", "max_group_mde", "group_mde", "n_resolvable_groups", "refused",
)
GROUP_RESULT_FIELDS = (
    "label", "key", "cells", "n_cells", "n_informative_cells", "n_uninformative_cells", "n_discordant", "n_a", "n_b",
    "mde", "degenerate", "location", "dispersion", "p_location", "p_dispersion", "p_group", "q_group", "rejects",
)
FAULT_LINES_FIELDS = ("tested", "reason", "null", "q", "n_groups", "n_degenerate_groups", "n_rejected_groups", "rejected_groups", "groups")
#: O17's thirteen root fields, restated.
ROOT_GUARDED_FIELDS = (
    "location", "dispersion", "p_location", "p_dispersion", "p_omnibus", "rejects", "n_cells",
    "n_informative_cells", "n_discordant", "n_permutations", "seed", "scheme", "units",
)
#: L11, ADR-072's form. The string fields of the four P4.3 structures are not guarded as
#: attributes: ``event`` sits inside a ``BinOp`` at ``cli.py:1318`` (step zero item 5), and a
#: string is not a target of the arithmetic the guard forbids. ``label``, ``key``, ``reason`` and
#: ``null`` are guarded anyway through S26's sets, where they are fields of other structures.
P43_STRING_FIELDS = frozenset({"event", "config_hash", "label", "key", "group", "reason", "null", "discoveries"})
P43_GUARDED_ATTRIBUTES = (
    set(CELL_RESULT_FIELDS) | set(CELL_FAMILY_FIELDS) | set(LEAVES_FIELDS) | set(BOUND_FIELDS) | {"leaves", "bound"}
) - P43_STRING_FIELDS
CLI_GUARDED_ATTRIBUTES = (
    set(ROOT_GUARDED_FIELDS) | {"n_uninformative_cells"} | set(REFUSAL_FIELDS) | set(GROUPING_FIELDS)
    | set(GROUP_RESULT_FIELDS) | set(FAULT_LINES_FIELDS) | set(TREE_RESULT_FIELDS) | P43_GUARDED_ATTRIBUTES
)
#: F21's bare-name set, plus the P4.3 names that collide with nothing in ``cli.py`` at ``6fd3b9c``.
CLI_GUARDED_NAMES = set(ROOT_GUARDED_FIELDS) | {
    "n_uninformative_cells", "n_groups", "n_resolvable_groups", "offered_max_group_mde", "resolved_by", "next_rung",
    "group_sizes", "size_min", "size_median", "size_max", "alpha_floor", "max_group_mde", "group_mde", "refused",
    "n_informative_cells", "p_group", "q_group", "n_degenerate_groups", "n_rejected_groups", "rejected_groups",
    "fault_lines", "grouping", "degenerate", "requested",
    "depth", "depth_configured", "delta_star", "q_within", "n_families", "families", "leaves", "mde_median", "mde_max", "discoveries",
}
#: Step zero item 5: what already sits inside a ``BinOp`` in ``cli.py`` at ``6fd3b9c``. The guard's
#: attribute set must be disjoint from the first and its bare-name set from the second.
COLLIDING_ATTRIBUTES_AT_BASE = frozenset({"dumps", "event", "headline", "join", "replace", "rstrip", "splitlines", "to_markdown", "values"})
COLLIDING_NAMES_AT_BASE = frozenset({
    "cells", "col", "cols", "coverage", "df", "done", "header", "lines", "multi", "n", "name", "ns", "others",
    "out_dir", "payload", "primary", "record", "structure", "total", "trade",
})
EVENT_COLLISION_LINE = 1318

#: L20. F28's omnibus digest was taken over the study pair's omnibus; on the lattice it is replaced by
#: the facts it guarded, recomputed from ``lattice.counts`` (``lattice_omnibus_facts`` below).
#: **A28's retrofit, 2026-09-13 -- both ``diff.py`` exclusions retired** (ADR-077's standing duty).
#: A27's ``_pairing`` (minted ``101028c``) and A22's ``_coverage`` (minted ``4b3c6ae``) both named
#: ``A28`` as their retiring packet; both owners have landed and A28 rewrites every carrier (five literals, one per file:
#: ``test_a28_agreement.py``, ``test_s26_fault_lines.py``, ``test_s27_leaves.py``, ``test_s28_report.py``,
#: ``test_s29_viewer.py``; "four" is ``FORMER_CARRIERS``, the set A28 sweeps beside itself -- LS retrofit, 2026-09-22 (local serve pass, Phase A)), so
#: the value below is a read off the shipped file at ``38e8df9`` (byte-identical at ``03d7ed2``),
#: never a prediction: the whole-file sha256. The record constant, its cover loop and the span
#: clause went with it; the sweep now finds ``test_s29_viewer.py`` alone.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): diff.py gains complementary_events and trade_line()'s complement branch (spec LS section 3.6); the whole-file sha256 of the built file. The same value in all five carriers. Read through this test's own measurement on the built tree, not predicted.
# Re-minted 2026-09-26 (A10 declared expectations, phase two, off the build at 662ceff): diff.py gains DeclaredSetMismatch(DiffError) and its refusal in diff() and multi_diff(), just before _pairing (spec A10 W9; ADR-084 stands, _pairing is untouched); the whole-file sha256 of the built file. The same value in all five carriers. Read through this test's own measurement on the built tree, not predicted.
# PF0 (Q4): no longer asserted. The rename changes diff.py, and no digest of a file this module
# changes can be frozen honestly before its build exists (front-door spec section 14).
DIFF_PY_SHA256 = "7344a99a0fa9263957f72257354988e29e600a4a152109ea0821db45ae96043b"
# PF4 (PF4.3, PF4.13 to PF4.15, PF4.20): MULTI_JSON_SHA256 is no longer asserted. PF4 adds
# columns to every cell and changes its limits and words, so the multi_diff test checks the facts
# the digest guarded instead (LATTICE_DIRECTION_COUNTS and the lattice's references below).
# PF3 (Q17, spec sections 4.4 and 14; rule R1): the lattice's runs share a salt, so the default is the
# paired test; check's gate here is the flat family's unpaired test, named.
# PF4 (PF4.20): the lattice's tripped has no kind, so the default --fail-on worse is refused;
# --fail-on higher is the same gate on it (fail when the rate rose).
CHECK_ARGV = ("check", LATTICE_A, LATTICE_B, "--event", EVENT, "--method", "fisher_bh", "--fail-on", "higher")
# CHECK_STDOUT_SHA256 removed: the command line's new look changes check's stdout, and its test
# checks the facts the digest guarded instead (front-door spec section 14).
CHECK_EXIT = 0
# PF3 (Q17, spec sections 4.4 and 14; rule R1): the structure's facts are the unpaired test's, named.
SERVE_ARGV = ("serve", LATTICE_A, LATTICE_B, "--event", EVENT, "--x", X, "--y", Y, "--json", "--method", "fisher_bh")
# PF4 (PF4.3, PF4.11, PF4.17, PF4.20): SERVE_STRUCTURE_SHA256 is no longer asserted; the serve
# test checks the facts the digest guarded instead.
#: S24's column digests and the coverage digest (``PAIR_QCOLUMN_SHA256``, ``PAIR_DELTA_SHA256``,
#: ``COVERAGE_SHA256`` and the log-rank q column's) were taken over the study pair; on the
#: lattice each is replaced by the facts it guarded, checked against ``lattice.fisher`` /
#: ``lattice.logrank`` / ``lattice.bh`` and the design, in the forms they hashed
#: (``test_l20_the_s24_columns_and_the_coverage_are_the_references`` below).
# PF3 (Q17, spec sections 4.4 and 14; rule R1): the E14 facts and the heatmap are the unpaired test's, named.
E14_ARGV = ("report", LATTICE_A, LATTICE_B, "--event", EVENT, "--x", X, "--y", Y, "--method", "fisher_bh")
#: PF4: what the multi, E14 and serve checks hold the lattice's ``tripped`` to, per method:
#: ``(lower, higher)``, the literal each reference gives (``lattice.directions`` over
#: ``lattice.fisher``, ``lattice.mcnemar``, ``lattice.logrank``), asserted beside the reference.
LATTICE_DIRECTION_COUNTS = {"fisher_bh": (22, 0), "mcnemar_bh": (27, 0), "logrank_bh": (27, 12)}
LATTICE_REFERENCES = {"fisher_bh": lattice.fisher, "mcnemar_bh": lattice.mcnemar, "logrank_bh": lattice.logrank}
#: The interval level and alpha* the report prints over the flat Fisher family: alpha* is
#: ``q x 22 / 72`` (recomputed beside it), the per-row level ``1 - alpha*``, printed under ``:g``
#: on the alpha* line and to three decimals on the line about each condition's change.
LATTICE_INTERVAL_LEVEL_TEXT, LATTICE_ALPHA_STAR_TEXT, LATTICE_ON_CHANGE_LEVEL_TEXT = "98.4722", "0.0152778", "98.472"
#: The per-cell columns the study pair's frozen Fisher record carried; on the lattice they are
#: checked against ``lattice.counts`` / ``lattice.fisher`` (the design, never Prove).
ARM_KEYS = ("n_a", "n_b", "events_a", "events_b", "rate_a", "rate_b", "delta")
#: Keys that belong to the layered report's tree; none may appear outside ``tree`` on the page.
#: (``bound`` is not among them: the page's ``view`` carries its own forest ``bound`` setting.)
TREE_ONLY_KEYS = ("omnibus", "fault_lines", "leaves")
#: The two frozen oracles' bytes: L20's "untouched", in a form a scratch copy can check. Minted at
#: ``6fd3b9c``; re-minted by S28's retrofit commit, which narrowed both files' E14 clause, and again
#: by S29's, which narrowed both files' ``serve --json`` digest to the tree-less projection (draft ADR-074);
#: and again by A27's, which narrowed ``test_s26_fault_lines.py``'s own ``DIFF_PY_SHA256`` to exclude
#: ``diff.py::_pairing``; and again by A22's retrofit, which added ``diff.py::_coverage`` to the same
#: record; and again by A28's retrofit, which retired both exclusions from that file and left its
#: ``DIFF_PY_SHA256`` whole-file. Re-minted **after** that edit, off the shipped file -- a read, not a prediction,
#: which is why ADR-077 does not narrow an oracle-pins-oracle digest. ``test_s25_root.py`` is untouched and
#: nothing pins this file, so the cascade is one literal deep and terminates here (measured).
# Re-minted 2026-09-20 (truncation surfacing): both files moved -- their E14 and serve digests, and the dated notes above them --
# so both values do, read off the two files as they stand and not predicted. Nothing pins this file, so the cascade ends here.
# Re-minted 2026-09-22 (PR-2 Session B's retrofit of O16, ruled: two default_rng sites, tree.py _draw and paired.py
# _cluster_bootstrap, ADR-058 widened to one stream per estimator): only ``test_s25_root.py`` moved, read off the
# shipped file and not predicted; ``test_s26_fault_lines.py`` is untouched. Nothing pins this file, so the cascade ends here.
# Re-minted 2026-09-25 (local serve pass, Phase C, last): both files moved. ``test_s25_root.py`` by Phase C's re-mint of O23's
# ``SERVE_STRUCTURE_SHA256`` and its dated note; ``test_s26_fault_lines.py`` by Phase A's retrofit (the "five literals" comment
# on ``DIFF_PY_SHA256``) and by Phase C's re-mint of its ``DIFF_PY_SHA256`` and ``SERVE_STRUCTURE_SHA256``. Read off the two
# files as they stand after every other re-mint, not predicted. Nothing pins this file, so the cascade ends here.
# Re-minted 2026-09-26 (A10 declared expectations, phase two, last): only ``test_s26_fault_lines.py`` moved, by this
# re-mint of its ``DIFF_PY_SHA256`` (off the build at 662ceff) and the dated note above it; ``test_s25_root.py`` is untouched.
# Read off the file as it stands after every other re-mint, not predicted. Nothing pins this file, so the cascade ends here.
# Re-minted by PF0 Session A: both files as its freeze commit moved them (the rename, Q4, and the
# version field put back before their fixture digests). Read off the two files after every other move.
# Re-minted for the command line's new look (front-door spec sections 5.2 to 5.6 and 14): both files
# moved their CLI assertions. Read off the two files after every other move, not predicted.
# Re-minted again for run names (front-door spec sections 4.3 and 5.3): both files moved their
# serve --json digests to compare with the names put back to ids. Read off the two files after
# every other move, not predicted.
# Re-minted again for the paired default (front-door spec sections 4.4 and 14, Q17): both files name
# --method fisher_bh on their fixture commands and drop method and method_chosen from serve --json.
# Read off the two files after every other move, not predicted.
# PF4: re-minted after PF4's moves of both files (their fixture multi, E14, check and serve tests, O9's
# omnibus under PF4.18, and in test_s26_fault_lines.py the trace groupings, the fault-line golden,
# --methods all --json and the no-comparable-cell refusal), and again at PF4's statistics re-freeze.
# Read off the two files as they stand after every other move, not predicted; these are test files,
# not output PF4 changes.
# PF5: re-minted after PF5's move of test_s25_root.py (o16 reads src/ recursively, since the core is
# a package); test_s26_fault_lines.py is untouched. Read off the file after every other move.
# Re-minted when both files moved off the committed study fixture onto the generated lattice pair
# (tests/lattice.py). Read off the two files after every other move.
# Re-minted again for public hygiene (front-door spec sections 9.2 and 14, Q37): test_s26_fault_lines.py no
# longer pins an internal phase in a refusal's detail. Read off the two files after every other move, not
# predicted. The re-minted serve --json digests of both files were unwound when the committed study fixture
# left the tests (ruling of 2026-10-25); the generated fixture that replaces it comes with main.
# Re-minted again for public hygiene (Q38): the plain-words pass edits the docstrings and comments of frozen test
# files, so the pin is over each file's code with those taken out (``conftest.code_of``) and still moves the moment
# an assertion does. Read off the two files after every other move, not predicted.
FROZEN_ORACLE_SHA256 = {
    "tests/test_s25_root.py": "1b13d84c1097f616c43db318c3d40caef964379f566b341a4cb7e22292037894",
    "tests/test_s26_fault_lines.py": "b3e636b28244360e3f2eda35e23602bfad8c1c8d544b12af52d1f385cbb524ef",
}
#: L20: the two signatures that must not move, as ``str(inspect.signature(...))`` at ``6fd3b9c``.
OMNIBUS_SIGNATURE = "(a: 'pd.DataFrame', b: 'pd.DataFrame', multi: 'MultiDiffResult', *, n_permutations: 'int' = 4000, seed: 'int' = 0) -> 'RootResult'"
RESOLVE_GROUPING_SIGNATURE = (
    "(requested: 'str | None', *, manifest_a: 'RunManifest', manifest_b: 'RunManifest', units: 'pd.DataFrame', "
    "q: 'float', max_group_mde: 'float | None' = None, frames: 'tuple[pd.DataFrame, pd.DataFrame] | None' = None) -> 'Grouping'"
)
#: ``tree``'s parameters at ``6fd3b9c`` plus the one this packet adds: (name, kind, default).
TREE_PARAMETERS = (
    ("a", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty), ("b", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty),
    ("multi", "POSITIONAL_OR_KEYWORD", inspect.Parameter.empty), ("manifest_a", "KEYWORD_ONLY", inspect.Parameter.empty),
    ("manifest_b", "KEYWORD_ONLY", inspect.Parameter.empty), ("by", "KEYWORD_ONLY", None), ("n_permutations", "KEYWORD_ONLY", 4000),
    ("seed", "KEYWORD_ONLY", 0), ("max_group_mde", "KEYWORD_ONLY", None), ("depth", "KEYWORD_ONLY", 3),
)

#: The lattice's labels and counts (step zero item 4), re-measured on the unchanged build.
#: ``str(value)`` of the config floats.
LATTICE_LOAD_REJECTED = ("10.0", "20.0", "30.0")
LATTICE_LOAD_NOT_REJECTED = ("40.0", "50.0", "100.0")
LATTICE_LOAD_LEAVES = {"fisher_bh": (10, 11, 1), "mcnemar_bh": (10, 11, 8)}
LATTICE_LOAD_UNION = {"fisher_bh": 25, "mcnemar_bh": 30}
#: A family whose rejected leaves' ``q_within`` is neither ascending nor descending in hash order
#: under both schemes (``load`` 10.0 is the other), and how many it rejects.
LATTICE_LOAD_UNSORTED_FAMILY, LATTICE_LOAD_UNSORTED_REJECTED = "20.0", 11
#: The ``gain`` groups at the permutation floor under both schemes (``1.2`` rejects off it under
#: both, ``0.9`` under Fisher; ``1.1`` does not reject).
LATTICE_GAIN_AT_FLOOR = ("0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "1.0")
LATTICE_GAIN_FLOOR_LEAVES = {"fisher_bh": (3, 3, 3, 2, 2, 2, 2, 2, 3), "mcnemar_bh": (3, 3, 3, 3, 3, 3, 2, 3, 3)}
#: Under Fisher by ``gain``: three conditions rejected as leaves that the flat family does not
#: reject, and one the flat family rejects that its own group's family does not, named by key.
LATTICE_GAIN_NESTED_ONLY_FISHER = {
    lattice.config_hash({X: gain, Y: 30.0}): str(gain) for gain in (0.2, 0.3, 1.0)
}
LATTICE_GAIN_FLAT_ONLY_FISHER = (lattice.config_hash({X: 1.2, Y: 20.0}), "1.2")
LATTICE_FLAT_REJECTIONS = {"fisher_bh": 22, "mcnemar_bh": 27}


#: Synthetic vocabularies. Non-events end at the horizon; events end at ``EVENT_T``.
NON_EVENTS = frozenset({"ok", "x", "z"})
EVENT_T = 2.0
HORIZON = 5.0
AXES_SALT, BH_SALT, SALT, OTHER_SALT = "s26-axes-salt", "s26-bh-salt", "s26-salt", "s26-other-salt"
AXES_TYPES_TASK_FIRST = {"task": "categorical", "temp": "continuous"}
AXES_TYPES_TASK_ONLY = {"task": "categorical"}
BH_TYPES = {"grp": "categorical", "cell": "categorical"}
N_TASKS, AXES_N, AXES_MOVED_CELLS, AXES_MOVED_PAIRS = 164, 8, 20, 2
#: L21: no leaf p in ``temp = 0.0`` is below this before any correction (0.5 McNemar, 0.4667 Fisher).
AXES_MIN_LEAF_P = 0.46
#: The gate fixture (spec section 0.7, step zero item 3).
GATE_GROUPS, GATE_CELLS, GATE_N, GATE_DISCORDANT = 40, 6, 64, 8
GATE_TYPES = {"grp": "categorical", "cell": "categorical"}
GATE_LEAF_Q_WITHIN = 0.046875
GATE_MIN_Q_GROUP = 0.15
#: The multi-event pair (spec section 6, step zero items 1 and 2).
ME_N, ME_TASKS, ME_TEMPS, ME_EVENTS = 128, 8, (0.0, 0.7), ("fail", "crash")
ME_TYPES = {"task": "categorical", "temp": "continuous"}


# ---------- data builders: construction only, no assertions and no decisions ----------


def tree() -> Any:
    """``proofload.tree``, imported at call time (see the module docstring)."""
    return importlib.import_module("poisson_prove.tree")


def lattice_frames() -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    store = Store(LATTICE_ROOT)
    return store.read(LATTICE_A, meta=False), store.read(LATTICE_B, meta=False), store.manifest(LATTICE_A), store.manifest(LATTICE_B)


def quiet_multi_diff(a: pd.DataFrame, b: pd.DataFrame, ma: RunManifest, mb: RunManifest, *, events: Sequence[str], method: str, q: float = Q) -> Any:
    """``multi_diff`` with the unpaired-analysis warning silenced; no test below is about it."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return multi_diff(a, b, events=list(events), method=method, q=q, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]


def manifest(run_id: str, salt: str, axis_types: Mapping[str, str]) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types), backend="synthetic", environment={"note": "built by test_s27_leaves"},  # type: ignore[arg-type]
    )


def reordered(m: RunManifest, axis_types: Mapping[str, str]) -> RunManifest:
    """The same manifest with ``axis_types`` rebuilt (S26 section 6, restated)."""
    return RunManifest(**{**m.to_dict(), "axis_types": dict(axis_types)})


def raw_frame(run_id: str, cells: Mapping[tuple[tuple[str, Any], ...], Sequence[str]], *, horizon: float = HORIZON) -> pd.DataFrame:
    """An in-memory frame with the eleven columns ``Store.read(meta=False)`` returns, over
    multi-key configs (S26's ``raw_frame``, restated)."""
    rows: list[dict[str, Any]] = []
    for index, (key, outcomes) in enumerate(cells.items()):
        config = dict(key)
        for k, outcome in enumerate(outcomes):
            rows.append({
                "run_id": run_id, "config_hash": config_hash(config), "config": config, "seed": 1000 * index + k,
                "replicate_index": k, "outcome": outcome, "t": horizon if outcome in NON_EVENTS else EVENT_T,
                "horizon": horizon, "confidence": math.nan, "error": None, "wall_time": 0.0,
            })
    frame = pd.DataFrame.from_records(rows)
    for column in ("config", "outcome", "error"):
        frame[column] = frame[column].astype(object)
    return frame


def write_run(store: Store, run_id: str, *, salt: str, axis_types: Mapping[str, str], cells: Mapping[tuple[tuple[str, Any], ...], Sequence[str]]) -> None:
    """A complete synthetic run over multi-key configs, one episode per outcome (S26's, restated)."""
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
    """S26 section 6's axes pair: 164 ``task`` x 2 ``temp`` at N=8, every cell all ``ok``; when
    ``moved``, the first twenty cells of ``temp = 0.0`` carry ``fail`` at replicates 0 and 1."""
    cells = {}
    for i in range(N_TASKS):
        for temp in (0.0, 0.7):
            outcomes = ["ok"] * AXES_N
            if moved and temp == 0.0 and i < AXES_MOVED_CELLS:
                outcomes = ["fail"] * AXES_MOVED_PAIRS + ["ok"] * (AXES_N - AXES_MOVED_PAIRS)
            cells[(("task", f"t{i:03d}"), ("temp", temp))] = outcomes
    return cells


def bh_cells(weak_cells: int, extra_fails: int) -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """S26 section 0.7's BH pair: twenty ``grp`` x ten ``cell`` at N=32, ``fail x4 + ok x28`` in
    both arms; ``g00``'s first ``weak_cells`` cells carry ``extra_fails`` more ``fail`` in arm b."""
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


def discordant_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """S26 section 0.4's frames: one cell, arm a ``fail`` for i < 20, arm b ``fail`` for i >= 20."""
    key = (("task", "d"),)
    return {key: ["fail"] * 20 + ["ok"] * 12}, {key: ["ok"] * 20 + ["fail"] * 12}


def one_value_cells(moved: bool) -> dict[Any, list[str]]:
    """Four cells over ``task`` with ``temp`` at the single value 0.0, N=8 (S26 F9's pair)."""
    return {(("task", f"t{i}"), ("temp", 0.0)): (["fail"] * 8 if moved else ["ok"] * 8) for i in range(4)}


def three_outcome_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """S25's six cells of 32 over ``x``, ``y``, ``z``, restated."""
    a = {(("task", f"c{i}"),): ["x"] * 4 + ["y"] * 4 + ["z"] * 24 for i in range(6)}
    b = {(("task", f"c{i}"),): ["x"] * 4 + ["y"] * 20 + ["z"] * 8 for i in range(6)}
    return a, b


def gate_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """Spec section 0.7's gate fixture: forty ``grp`` x six ``cell`` at N=64, ``fail x4 + ok x60``
    in both arms, and ``g00 c0`` with ``fail`` at replicates 4-11 in arm b (eight discordant
    pairs one way)."""
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
    """Spec section 6's one-task-moved shape, sized at ``ME_N`` (module docstring, step zero
    item 1): eight ``task`` x two ``temp``; ``t0``'s two cells moved in ``fail`` (arm a ``fail
    x16 + ok x112``, arm b ``fail x80 + ok x48``); the other seven tasks identical across arms
    on a mixed base. With ``crash_elsewhere`` those seven carry ``crash`` at one replicate in
    four, identical across arms, so the CLI's event guard admits ``--event crash`` (item 2);
    ``t0`` never carries it either way."""
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


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(argv, stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def without_notes(err: str) -> str:
    """Stderr with the ``note:`` lines removed. Prove's own warning (``UnpairedAnalysis``, on two
    runs sharing a salt) now reaches the CLI's stderr as one ``note:`` line (spec section 5.4)."""
    return "".join(line for line in err.splitlines(keepends=True) if not line.startswith("note: "))


def block_lines(out: str, head: str) -> list[str]:
    """The line starting with ``head`` and every following line indented by two spaces, as a list;
    ``[]`` when there is no such line. Found by index, never by the tail of stdout."""
    lines = out.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(head)]
    if not starts:
        return []
    end = starts[0] + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    return lines[starts[0] : end]


def omnibus_block(out: str) -> list[str]:
    return block_lines(out, "omnibus: ")


def fault_lines_block(out: str) -> list[str]:
    return block_lines(out, "fault lines:")


def cells_block(out: str) -> list[str]:
    return block_lines(out, "cells:")


def bound_block(out: str) -> list[str]:
    return block_lines(out, "bound:")


def block_start(out: str, block: list[str]) -> int:
    return out.splitlines().index(block[0])


def family_lines(block: list[str]) -> list[str]:
    """The ``cells:`` block's lines indented by exactly two spaces (module docstring)."""
    return [line for line in block[1:] if line.startswith("  ") and not line.startswith("    ")]


def leaf_lines(block: list[str]) -> list[str]:
    """The ``cells:`` block's lines indented by four or more spaces."""
    return [line for line in block[1:] if line.startswith("    ")]


def heads(out: str, head: str) -> int:
    """How many lines of ``out`` start with ``head`` -- never ``out.count``, because the omnibus
    block's informative line contains ``cells:`` mid-line."""
    return sum(1 for line in out.splitlines() if line.startswith(head))


def numeric_tokens(line: str) -> list[str]:
    """Every whitespace-, ``=``-, ``,``-, ``:``-, ``;``-, ``(``-, ``)``- or ``/``-separated token
    that parses as a number, verbatim (S26's helper). A comma before three digits is a thousands
    separator inside a count (spec section 5.4, rule 10), so ``1,312`` is one token."""
    out = []
    for token in re.split(r"[\s=:;()/]+|,(?!\d{3}(?!\d))", line):
        try:
            float(token.replace(",", ""))
        except ValueError:
            continue
        out.append(token)
    return out


def g(value: Any) -> str:
    return f"{value:g}"


# The blocks' numbers as the command line prints them under rule 10 (spec section 5.4), which
# replaces ``:g``: counts with thousands separators, a rate, delta or MDE to three decimals, and a
# p, q or alpha to three decimals or in ``2.3e-08`` form below 0.001. A config value is not
# reformatted.


def count(value: Any) -> str:
    return f"{int(value):,}" if float(value).is_integer() else f"{value:,}"


def fraction(value: Any) -> str:
    return f"{value:.3f}"


def rule_10_p(value: Any) -> str:
    return f"{value:.3f}" if value >= 0.001 else f"{value:.1e}"


def config_tokens(config: Mapping[str, Any]) -> set[str]:
    """Every rendering a config value may take on a leaf line (module docstring)."""
    out: set[str] = set()
    for value in config.values():
        out.add(str(value))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out.add(g(value))
    return out


def json_bytes(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)


def without(payload: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in keys}


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def walk_keys(payload: Any, *, skip: Sequence[str] = ("config", "groups")) -> list[str]:
    """Every mapping key at any depth of a JSON payload, except the keys of mappings that carry
    user data: a ``config`` dict's keys are the run's axis names and ``groups``' keys are labels."""
    found: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            found.append(str(key))
            if key not in skip:
                found.extend(walk_keys(value, skip=skip))
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            found.extend(walk_keys(value, skip=skip))
    return found


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def enclosing_functions(module: ast.Module) -> dict[ast.AST, str]:
    """Every node mapped to the name of the ``def`` it sits inside (O16's helper, restated)."""
    out: dict[ast.AST, str] = {}

    def walk(node: ast.AST, name: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else name
            if inner is not None:
                out[child] = inner
            walk(child, inner)

    walk(module, None)
    return out


def parents(module: ast.Module) -> dict[ast.AST, ast.AST]:
    out: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(module):
        for child in ast.iter_child_nodes(node):
            out[child] = node
    return out


def mentioned_in(node: ast.AST) -> set[str]:
    """Every attribute name and bare name inside ``node``'s subtree, the O17 / F8 form."""
    return {child.attr if isinstance(child, ast.Attribute) else child.id for child in ast.walk(node) if isinstance(child, (ast.Attribute, ast.Name))}


def grown(a: pd.DataFrame, b: pd.DataFrame, multi: Any, ma: RunManifest, mb: RunManifest, **knobs: Any) -> Any:
    """``tree.tree`` on a pair, the way every test below reaches it."""
    return tree().tree(a, b, multi, manifest_a=ma, manifest_b=mb, **knobs)


def store_tree(root: Path, a: str, b: str, *, events: Sequence[str], method: str, **knobs: Any) -> tuple[Any, Any]:
    """``(multi, tree)`` on a stored pair, the way the CLI reaches them."""
    store = Store(root)
    fa, fb = store.read(a, meta=False), store.read(b, meta=False)
    multi = quiet_multi_diff(fa, fb, store.manifest(a), store.manifest(b), events=events, method=method)
    return multi, grown(fa, fb, multi, store.manifest(a), store.manifest(b), **knobs)


# ---------- the shared recompute: the family from ``cells`` and the partition ----------


def family_rows(multi: Any, result: Any, label: str) -> pd.DataFrame:
    """Spec section 3.1-3.2 in this file's own words: one row per ``(cell, event)`` of the group,
    cells in sorted-hash order and events in ``root.events`` order under each hash, every field
    read from ``multi.by_event[event].cells`` and nothing recomputed; ``q_within`` is ``diff.bh``
    over the family's ``p`` in that order, ``rejects`` the strict comparison against ``q``."""
    rows: list[dict[str, Any]] = []
    for h in sorted(result.grouping.groups[label]):
        for event in result.root.events:
            cells = multi.by_event[event].cells
            match = cells[cells["config_hash"].astype(str) == h]
            assert len(match) == 1, (label, h, event, len(match))
            row = match.iloc[0]
            rows.append({
                "config_hash": h, "event": event, "config": row["config"], "n_a": int(row["n_a"]), "n_b": int(row["n_b"]),
                "events_a": int(row["events_a"]), "events_b": int(row["events_b"]), "delta": float(row["delta"]),
                "p": float(row["p"]), "flat_q": float(row["q"]), "mde": float(row["mde"]),
            })
    frame = pd.DataFrame(rows)
    frame["q_within"] = diff_mod.bh(frame["p"].to_numpy(dtype=np.float64), multi.q)
    frame["rejects"] = frame["q_within"] < multi.q
    return frame


def flat_pairs(multi: Any) -> set[tuple[str, str]]:
    """The flat BH family's rejected ``(config_hash, event)`` pairs, recomputed from ``cells.q``."""
    out: set[tuple[str, str]] = set()
    for event in multi.events:
        cells = multi.by_event[event].cells
        out |= {(str(h), event) for h in cells.loc[cells["q"] < multi.q, "config_hash"]}
    return out


def nested_pairs(result: Any) -> set[tuple[str, str]]:
    return {(leaf.config_hash, leaf.event) for family in result.leaves.families for leaf in family.cells if leaf.rejects}


def union_pairs(multi: Any, result: Any) -> set[tuple[str, str]]:
    """The builder's shortcut L3 forbids: one BH family over every rejecting group's cells."""
    frames = [family_rows(multi, result, label) for label in result.fault_lines.rejected_groups]
    if not frames:
        return set()
    pooled = pd.concat(frames, ignore_index=True)
    q_union = diff_mod.bh(pooled["p"].to_numpy(dtype=np.float64), multi.q)
    return {(h, e) for h, e, q_ in zip(pooled["config_hash"], pooled["event"], q_union, strict=True) if q_ < multi.q}


def expected_rejecting(result: Any) -> tuple[str, ...]:
    """Which groups' families Level 3 owes, from the surface: the rejected groups when Level 2
    was tested, the one group when the grouping collapsed under a rejecting root, else none."""
    if result.fault_lines.tested:
        return tuple(result.fault_lines.rejected_groups)
    if result.root.rejects and result.grouping.n_groups < EXPECTED_MIN_FAMILY_GROUPS:
        return tuple(result.grouping.labels)
    return ()


def expected_depth(depth_configured: int, result: Any) -> int:
    return depth_configured - (1 if result.grouping.n_groups < EXPECTED_MIN_FAMILY_GROUPS else 0)


def expected_bound(depth: int, q: float) -> float:
    return 2 * depth * q * EXPECTED_DELTA_STAR


def assert_family_recomputed(name: str, multi: Any, result: Any, family: Any) -> None:
    """L2 and L3 on one family: every leaf is the flat family's row bit for bit, in row order,
    and the family's correction and counts are the recompute's."""
    q = multi.q
    frame = family_rows(multi, result, family.label)
    assert family.key == result.grouping.key, (name, family.label, family.key)
    assert family.n_tests == len(family.cells) == len(frame) == len(result.grouping.groups[family.label]) * len(result.root.events), (name, family.label)
    for leaf, (_, row) in zip(family.cells, frame.iterrows(), strict=True):
        assert (leaf.config_hash, leaf.event, leaf.group) == (row["config_hash"], row["event"], family.label), (name, leaf)
        assert leaf.config_hash in result.grouping.groups[family.label] and leaf.event in result.root.events, (name, leaf)
        assert dict(leaf.config) == dict(row["config"]), (name, leaf.config_hash)
        assert (leaf.n_a, leaf.n_b, leaf.events_a, leaf.events_b) == (row["n_a"], row["n_b"], row["events_a"], row["events_b"]), (name, leaf.config_hash)
        # PF4 (PF4.15): a leaf whose baseline had the event in every run has no limit (NaN), equal to
        # its row's NaN; every other limit is the row's, bit for bit.
        same_mde = leaf.mde == row["mde"] or (math.isnan(leaf.mde) and math.isnan(row["mde"]))
        assert leaf.p == row["p"] and leaf.delta == row["delta"] and same_mde, (name, leaf.config_hash, leaf.event)
        assert leaf.q_within == row["q_within"], (name, leaf.config_hash, leaf.event, leaf.q_within, row["q_within"])
        assert type(leaf.rejects) is bool and leaf.rejects == (leaf.q_within < q) == bool(row["rejects"]), (name, leaf.config_hash, leaf.event)
    rejected = tuple((leaf.config_hash, leaf.event) for leaf in family.cells if leaf.rejects)
    assert family.rejected == rejected and family.n_rejected == len(rejected), (name, family.label)
    # PF4 (PF4.15): a condition with no limit is left out of every maximum over conditions, so the
    # family's maximum and median are over the leaves that have one; with none, both are NaN.
    mdes = [leaf.mde for leaf in family.cells if not math.isnan(leaf.mde)]
    if mdes:
        assert family.mde_max == max(mdes) and abs(family.mde_median - float(np.median(mdes))) <= 1e-12, (name, family.label, family.mde_max, family.mde_median)
    else:
        assert math.isnan(family.mde_max) and math.isnan(family.mde_median), (name, family.label)


def assert_leaves_consistent(name: str, multi: Any, result: Any, depth_configured: int) -> None:
    """L4, L5 and L8 on one tree: the gate and the reasons from the surface, the families under
    exactly the rejecting groups, the sums, and the bound recomputed from the constants."""
    leaves, bound = result.leaves, result.bound
    if depth_configured < EXPECTED_DEFAULT_DEPTH:
        expected_reason: str | None = "depth"
    elif not result.root.rejects:
        expected_reason = "root_not_rejected"
    elif result.grouping.n_groups < EXPECTED_MIN_FAMILY_GROUPS:
        expected_reason = None
    elif result.fault_lines.n_rejected_groups == 0:
        expected_reason = "no_group_rejected"
    else:
        expected_reason = None
    assert (leaves.tested, leaves.reason) == (expected_reason is None, expected_reason), (name, leaves.tested, leaves.reason)
    rejecting = expected_rejecting(result) if leaves.tested else ()
    assert tuple(family.label for family in leaves.families) == rejecting, (name, [f.label for f in leaves.families], rejecting)
    assert leaves.n_families == len(leaves.families), name
    assert leaves.n_tests == sum(f.n_tests for f in leaves.families) and leaves.n_rejected == sum(f.n_rejected for f in leaves.families), name
    if not leaves.tested:
        assert (leaves.n_families, leaves.n_tests, leaves.n_rejected, leaves.families) == (0, 0, 0, ()), name
    for family in leaves.families:
        assert_family_recomputed(name, multi, result, family)
    assert bound.depth_configured == depth_configured and bound.depth == expected_depth(depth_configured, result), (name, bound)
    assert bound.q == result.root.q and abs(bound.bound - expected_bound(bound.depth, bound.q)) <= BOUND_TOLERANCE, (name, bound)


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


# ---------- fixtures ----------


@pytest.fixture(scope="module")
def pair(lattice_trees: Any) -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    """The lattice pair's two frames and manifests (``conftest.SharedTrees.frames``)."""
    return lattice_trees.frames()


@pytest.fixture(scope="module")
def gain_trees(lattice_trees: Any) -> dict[str, tuple[Any, Any]]:
    """``(multi, tree)`` per method on the lattice at ``events=("tripped",)``, the golden knobs,
    the default depth, no ``by``: the axis rung's resolution, ``gain``. The lattice has one event
    and cannot show ``K > 1``; every non-rejecting group would reject zero leaves, so it catches
    the gate mutant by structure only. Shared across the session (``lattice_trees``)."""
    out = {}
    for method in METHODS:
        # PF4 re-freeze (PF4.45): at the default gain is refused as underpowered, so the golden
        # gain tree is grown at ADMITTING_MAX_GROUP_MDE, where gain resolves.
        out[method] = (
            lattice_trees.multi((EVENT,), method),
            lattice_trees.tree((EVENT,), method, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, max_group_mde=ADMITTING_MAX_GROUP_MDE),
        )
    return out


@pytest.fixture(scope="module")
def load_trees(lattice_trees: Any) -> dict[str, tuple[Any, Any]]:
    """The lattice by ``load`` (requested), both schemes: three rejecting groups at the floor, so
    the leaf set is deterministic (L7), and three groups that do not reject (L4)."""
    return {
        method: (lattice_trees.multi((EVENT,), method), lattice_trees.tree((EVENT,), method, by=Y, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
        for method in TWO_SCHEMES
    }


@pytest.fixture(scope="module")
def axes() -> dict[str, Any]:
    """The axes pair in memory (S26 section 6). ``temp = 0.0`` rejects at the floor under both
    schemes with no leaf below p 0.46: it can show a moved group with nothing nameable inside
    it (L21) and cannot show a rejected leaf."""
    return {
        "a": raw_frame("axes-a", axes_cells(False)),
        "b": raw_frame("axes-b", axes_cells(True)),
        "ma": manifest("axes-a", AXES_SALT, AXES_TYPES_TASK_FIRST),
        "mb": manifest("axes-b", AXES_SALT, AXES_TYPES_TASK_FIRST),
    }


@pytest.fixture(scope="module")
def axes_trees(axes: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    out = {}
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(axes["a"], axes["b"], axes["ma"], axes["mb"], events=("fail",), method=method)
        out[method] = (multi, grown(axes["a"], axes["b"], multi, axes["ma"], axes["mb"], n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def identical_trees(axes: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    """The axes shape with both arms the moved frame: ``temp`` resolves to two groups and the
    root does not reject (p 1 under both schemes). The ``root_not_rejected`` fixture for a
    grouping that did not collapse (L5, L8)."""
    twin = raw_frame("same-b", axes_cells(True))
    out = {}
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(axes["b"], twin, axes["ma"], axes["mb"], events=("fail",), method=method)
        out[method] = (multi, grown(axes["b"], twin, multi, axes["ma"], axes["mb"], n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def bh_trees() -> dict[str, tuple[Any, Any]]:
    """S26's BH pair under ``mcnemar_bh``: the root rejects (p 0.0075), twenty groups are tested,
    none rejects (``g00`` at ``q_group`` 0.15). The ``no_group_rejected`` fixture (L5); every
    would-be leaf under ``g00`` sits at p 1, so it cannot show the gate's printed difference."""
    cells_a, cells_b = bh_cells(8, 1)
    a, b = raw_frame("bh-a", cells_a), raw_frame("bh-b", cells_b)
    ma, mb = manifest("bh-a", BH_SALT, BH_TYPES), manifest("bh-b", BH_SALT, BH_TYPES)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="mcnemar_bh")
    return {"mcnemar_bh": (multi, grown(a, b, multi, ma, mb, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))}


@pytest.fixture(scope="module")
def discordant_trees() -> dict[str, tuple[Any, Any]]:
    """S26 section 0.4's one cell: its only axis refuses as ``one_group``, the grouping collapses
    to the whole grid, and the root does not reject under either scheme (p 0.22 / 0.08). Root
    first: the ``root_not_rejected`` fixture under a collapsed grouping (L5)."""
    cells_a, cells_b = discordant_cells()
    a, b = raw_frame("disc-a", cells_a), raw_frame("disc-b", cells_b)
    ma, mb = manifest("disc-a", SALT, {"task": "categorical"}), manifest("disc-b", SALT, {"task": "categorical"})
    out = {}
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method=method)
        out[method] = (multi, grown(a, b, multi, ma, mb, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def gate_trees() -> dict[str, tuple[Any, Any]]:
    """The gate fixture (module docstring, step zero item 3), ``mcnemar_bh`` only: the root
    rejects, ``g00`` does not (``q_group`` 0.28 at seed 0), and ``g00`` holds a leaf whose
    ``q_within`` within its family of six would be 0.046875. The one fixture on which a builder
    who ignores the gate prints a leaf (L4). Under ``fisher_bh`` the root sits at p 0.98, so
    the fixture cannot show an arm-label gate and does not claim to."""
    cells_a, cells_b = gate_cells()
    a, b = raw_frame("gate-a", cells_a), raw_frame("gate-b", cells_b)
    ma, mb = manifest("gate-a", SALT, GATE_TYPES), manifest("gate-b", SALT, GATE_TYPES)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="mcnemar_bh")
    # PF4 re-freeze (PF4.45): at the default grp is refused as underpowered now, so the gate tree
    # is grown at ADMITTING_MAX_GROUP_MDE, where grp resolves as it did.
    return {"mcnemar_bh": (multi, grown(a, b, multi, ma, mb, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, max_group_mde=ADMITTING_MAX_GROUP_MDE))}


@pytest.fixture(scope="module")
def multi_event() -> dict[str, Any]:
    """The multi-event pair in memory, spec section 6's literal posture: ``crash`` in neither arm
    of any cell. ``task`` is admitted, the root and ``t0`` reject under both schemes, and
    ``t0``'s family is ``2 x 2`` (L22). The only fixture that can show ``K > 1``."""
    cells_a, cells_b = multi_event_cells(False)
    a, b = raw_frame("me-a", cells_a), raw_frame("me-b", cells_b)
    ma, mb = manifest("me-a", SALT, ME_TYPES), manifest("me-b", SALT, ME_TYPES)
    trees = {}
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(a, b, ma, mb, events=ME_EVENTS, method=method)
        # PF4 re-freeze (PF4.45): at the default task is refused as underpowered now and temp
        # resolves, so the tree is grown at ADMITTING_MAX_GROUP_MDE, where task resolves as it did.
        trees[method] = (multi, grown(a, b, multi, ma, mb, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, max_group_mde=ADMITTING_MAX_GROUP_MDE))
    return {"a": a, "b": b, "ma": ma, "mb": mb, "trees": trees}


@pytest.fixture(scope="module")
def three_outcome() -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    cells_a, cells_b = three_outcome_cells()
    return raw_frame("tri-a", cells_a), raw_frame("tri-b", cells_b), manifest("tri-a", SALT, {"task": "categorical"}), manifest("tri-b", SALT, {"task": "categorical"})


@pytest.fixture(scope="module")
def three_outcome_grid(three_outcome: Any) -> dict[str, tuple[Any, Any]]:
    """S25's three-outcome pair, two events, ``by="grid"``: the one-group collapse under a
    rejecting root with ``K = 2`` (L6), where the family is the flat family of twelve."""
    a, b, ma, mb = three_outcome
    out = {}
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(a, b, ma, mb, events=("x", "y"), method=method)
        out[method] = (multi, grown(a, b, multi, ma, mb, by=EXPECTED_WHOLE_GRID, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def every_tree(gain_trees: Any, load_trees: Any, axes_trees: Any, identical_trees: Any, bh_trees: Any, discordant_trees: Any, gate_trees: Any, multi_event: Any, three_outcome_grid: Any) -> list[tuple[str, Any, Any]]:
    """Every ``(name, multi, tree)`` this module builds at the golden knobs and the default depth,
    for the invariants that hold on every fixture (L1-L4, L8, L23)."""
    out: list[tuple[str, Any, Any]] = []
    groups = (
        ("lattice", gain_trees), ("lattice-load", load_trees), ("axes", axes_trees), ("identical", identical_trees), ("bh", bh_trees),
        ("discordant", discordant_trees), ("gate", gate_trees), ("multi-event", multi_event["trees"]), ("three-outcome-grid", three_outcome_grid),
    )
    for prefix, group in groups:
        out.extend((f"{prefix}/{name}", multi, result) for name, (multi, result) in group.items())
    return out


@pytest.fixture(scope="module")
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One store holding the axes pair (``axes-a`` / ``axes-b``), the identical pair of the same
    shape (``same-a`` / ``same-b``), the moved frame declaring ``task`` alone
    (``axes-b-task-only``, L13), the multi-event pair with ``crash`` carried outside ``t0``
    (``me-a`` / ``me-b``, module docstring item 2) and the empty family (``empty-a`` /
    ``empty-b``)."""
    root = tmp_path_factory.mktemp("s27-synth")
    store = Store(root)
    write_run(store, "axes-a", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(False))
    write_run(store, "axes-b", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    write_run(store, "same-a", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    write_run(store, "same-b", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    write_run(store, "axes-b-task-only", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_ONLY, cells=axes_cells(True))
    me_a, me_b = multi_event_cells(True)
    write_run(store, "me-a", salt=SALT, axis_types=ME_TYPES, cells=me_a)
    write_run(store, "me-b", salt=SALT, axis_types=ME_TYPES, cells=me_b)
    write_run(store, "empty-a", salt=SALT, axis_types={"task": "categorical"}, cells={(("task", "only-a"),): ["fail"] * 4 + ["ok"] * 4})
    write_run(store, "empty-b", salt=OTHER_SALT, axis_types={"task": "categorical"}, cells={(("task", "only-b"),): ["fail"] * 4 + ["ok"] * 4})
    return root


# ---------- hypothesis: small two-key pairs, both schemes, both depths ----------


@st.composite
def small_two_key_pairs(draw: st.DrawFn) -> tuple[dict[Any, list[str]], dict[Any, list[str]], str, int, int]:
    """S26's strategy, restated: ``2..4`` values on each of two keys ``x`` and ``y``, ``4..12``
    replicates, two outcomes, both schemes, ``B`` in ``5..40``. With ``max_group_mde = 0.75``
    the first axis resolves."""
    n_x, n_y = draw(st.integers(min_value=2, max_value=4)), draw(st.integers(min_value=2, max_value=4))
    n_reps = draw(st.integers(min_value=4, max_value=12))
    keys = [(("x", i), ("y", j)) for i in range(n_x) for j in range(n_y)]
    cells_a = {k: draw(st.lists(st.sampled_from(("ok", "fail")), min_size=n_reps, max_size=n_reps)) for k in keys}
    cells_b = {k: draw(st.lists(st.sampled_from(("ok", "fail")), min_size=n_reps, max_size=n_reps)) for k in keys}
    return cells_a, cells_b, draw(st.sampled_from(TWO_SCHEMES)), draw(st.integers(min_value=5, max_value=40)), draw(st.integers(min_value=0, max_value=10**6))


PROPERTY_SETTINGS = settings(deadline=None, max_examples=30, suppress_health_check=[HealthCheck.too_slow])
PROPERTY_TYPES = {"x": "continuous", "y": "continuous"}
PROPERTY_MAX_GROUP_MDE = 0.75


def property_tree(case: Any, depth: int) -> Any:
    cells_a, cells_b, method, permutations, seed = case
    a, b = raw_frame("p-a", cells_a), raw_frame("p-b", cells_b)
    ma, mb = manifest("p-a", SALT, PROPERTY_TYPES), manifest("p-b", SALT, PROPERTY_TYPES)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method=method)
    return multi, grown(a, b, multi, ma, mb, n_permutations=permutations, seed=seed, max_group_mde=PROPERTY_MAX_GROUP_MDE, depth=depth)


# ---------- L1: the literals ----------


def structure_as_ids_named_it(structure: dict[str, Any], events: str) -> dict[str, Any]:
    """PF2 (spec section 4.3): ``serve --json`` on the lattice moves in two places only: ``run_name`` beside
    each arm's ``run_id``, and the default title, which names the runs by name (``view.title`` and
    the figure's title line). First assert each is there as PF2 writes it and nowhere else the
    digest reads, then put the structure back as it was before names (no ``run_name``, the title by
    id) so the frozen digest still guards everything else."""
    arms = {}
    for role, run_id, name in (("a", LATTICE_A, LATTICE_NAME_A), ("b", LATTICE_B, LATTICE_NAME_B)):
        arm = structure["pair"][role]
        keys = list(arm)
        assert (arm["run_id"], arm.get("run_name")) == (run_id, name), arm
        assert keys.index("run_name") == keys.index("run_id") + 1, keys
        arms[role] = {k: v for k, v in arm.items() if k != "run_name"}
    named, by_id = f"{LATTICE_NAME_A} vs {LATTICE_NAME_B}: {events}", f"{LATTICE_A} vs {LATTICE_B}: {events}"
    assert structure["view"]["title"] == named, structure["view"]["title"]
    line = f'font-size="13">{named}</text>'
    assert structure["heatmap_svg"].count(line) == 1, structure["heatmap_svg"][:600]
    return {
        **structure,
        "pair": {**structure["pair"], **arms},
        "view": {**structure["view"], "title": by_id},
        "heatmap_svg": structure["heatmap_svg"].replace(line, f'font-size="13">{by_id}</text>'),
    }


def structure_as_0_0_1_wrote_it(structure: dict[str, Any]) -> dict[str, Any]:
    """PF0 (Q4, section 2.3): the rename moves one key of the page structure, the version, in both
    arms (``poisson_prove_version``) and in the provenance block, whose value also says when the runs
    were written by 0.0.1. First assert the new key is there and the old one is not, then put both
    back as 0.0.1 wrote them before the frozen digest is taken, so the digest still guards everything
    else."""
    for arm in ("a", "b"):
        assert "poisson_prove_version" in structure["pair"][arm] and "proofload_version" not in structure["pair"][arm], arm
    assert "poisson_prove_version" in structure["diff"] and "proofload_version" not in structure["diff"]
    arms = {
        arm: {("proofload_version" if key == "poisson_prove_version" else key): value for key, value in structure["pair"][arm].items()}
        for arm in ("a", "b")
    }
    diff = {key: value for key, value in structure["diff"].items() if key != "poisson_prove_version"}
    return {**structure, "pair": {**structure["pair"], **arms}, "diff": {**diff, "proofload_version": "0.0.1"}}


def test_l1_the_module_constants_are_the_spec_literals() -> None:
    """Asserted against this file's literals, never against the module's own (standing rule 1).
    ``MIN_FAMILY_GROUPS`` and ``MIN_RESOLVABLE_GROUPS`` are two names for two quantities that
    happen to be 2 (spec section 3.9)."""
    t = tree()
    assert t.DEFAULT_DEPTH == EXPECTED_DEFAULT_DEPTH and type(t.DEFAULT_DEPTH) is int
    assert t.DEPTHS == EXPECTED_DEPTHS
    assert t.DELTA_STAR == EXPECTED_DELTA_STAR and type(t.DELTA_STAR) is float
    assert t.BOUND_DISCOVERIES == EXPECTED_BOUND_DISCOVERIES
    assert t.MIN_FAMILY_GROUPS == EXPECTED_MIN_FAMILY_GROUPS and type(t.MIN_FAMILY_GROUPS) is int
    assert t.MIN_RESOLVABLE_GROUPS == EXPECTED_MIN_RESOLVABLE_GROUPS and "MIN_FAMILY_GROUPS" in vars(t) and "MIN_RESOLVABLE_GROUPS" in vars(t)
    assert t.CELL_NULL == EXPECTED_CELL_NULL
    assert t.LEAVES_NOT_TESTED_REASONS == EXPECTED_LEAVES_NOT_TESTED_REASONS


def test_l1_every_reason_and_every_bound_on_every_fixture_is_drawn_from_the_literals(every_tree: Any) -> None:
    for name, _, result in every_tree:
        leaves, bound = result.leaves, result.bound
        assert leaves.reason is None or leaves.reason in EXPECTED_LEAVES_NOT_TESTED_REASONS, (name, leaves.reason)
        assert (leaves.reason is None) == leaves.tested, (name, leaves.tested, leaves.reason)
        assert leaves.null == EXPECTED_CELL_NULL and leaves.q == result.root.q, name
        assert (bound.discoveries, bound.delta_star) == (EXPECTED_BOUND_DISCOVERIES, EXPECTED_DELTA_STAR), (name, bound)
        assert bound.depth_configured == EXPECTED_DEFAULT_DEPTH and bound.depth in EXPECTED_DEPTHS + (1,), (name, bound)


# ---------- L2, L3: the leaf is the flat family's row, corrected within its family ----------


def test_l2_and_l3_every_family_is_recomputed_from_cells_and_the_partition_on_every_fixture(every_tree: Any) -> None:
    """**The leaf is the flat family's row, re-corrected.** ``p``, ``delta``, ``mde`` bit-equal
    to the row of ``multi.by_event[event].cells`` with that hash, the counts equal, the config
    equal; ``q_within`` is ``diff.bh`` over the family's ``p`` in row order, elementwise; the
    counts, the rejected tuple and the two MDEs are the recompute's. A builder who recomputes a
    Fisher p, reads ``cells.q`` into ``p``, pools families, corrects over informative leaves
    only or applies no correction fails here. The lattice under all three methods, the axes pair, the
    multi-event pair and the collapsed pairs."""
    for name, multi, result in every_tree:
        assert_leaves_consistent(name, multi, result, EXPECTED_DEFAULT_DEPTH)


@PROPERTY_SETTINGS
@given(case=small_two_key_pairs(), depth=st.sampled_from(EXPECTED_DEPTHS))
def test_l2_l3_and_l8_hold_over_small_two_key_pairs_at_both_depths(case: Any, depth: int) -> None:
    """Every rejecting group's family recomputed from ``cells``, the reasons in order, and the
    bound from the constants, over both schemes and both depths."""
    multi, result = property_tree(case, depth)
    assert_leaves_consistent(f"property/{case[2]}/depth={depth}", multi, result, depth)


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_l3_lattice_per_group_families_differ_from_one_family_over_the_union(gain_trees: Any, load_trees: Any, method: str) -> None:
    """Spec section 0.6: on every lattice axis the per-group rejected set is not the set one BH
    family over the union of the rejecting groups' cells would give -- 22 / 29 against 25 / 30 by
    ``load``, and 24 / 28 against 23 / 27 by ``gain``. The hand-built fixtures cannot separate the two;
    the lattice can. The test computes both and says so."""
    for by, (multi, result) in ((Y, load_trees[method]), (X, gain_trees[method])):
        nested, union = nested_pairs(result), union_pairs(multi, result)
        assert nested != union, (by, method, len(nested), len(union))
        if by == Y:
            assert (len(nested), len(union)) == (sum(LATTICE_LOAD_LEAVES[method]), LATTICE_LOAD_UNION[method]), (method, len(nested), len(union))


# ---------- L4: leaves only under a rejecting group ----------


def test_l4_families_exist_under_exactly_the_rejecting_groups_on_every_fixture(every_tree: Any) -> None:
    """When Level 2 was tested the family labels are ``rejected_groups`` in order; no leaf carries
    a hash outside its group's partition; when neither Level 2 nor the collapse tested anything
    there is no family."""
    for name, _, result in every_tree:
        labels = tuple(family.label for family in result.leaves.families)
        if result.fault_lines.tested:
            assert labels == result.fault_lines.rejected_groups, (name, labels)
        elif result.leaves.tested:
            assert result.fault_lines.reason == "one_group" and labels == (EXPECTED_WHOLE_GRID_LABEL,), (name, labels)
        else:
            assert labels == (), (name, labels)
        for family in result.leaves.families:
            members = set(result.grouping.groups[family.label])
            assert {leaf.config_hash for leaf in family.cells} == members, (name, family.label)


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_l4_lattice_by_load_has_no_family_above_30(load_trees: Any, method: str) -> None:
    _, result = load_trees[method]
    labels = {family.label for family in result.leaves.families}
    assert labels == set(LATTICE_LOAD_REJECTED) and not labels & set(LATTICE_LOAD_NOT_REJECTED), sorted(labels)


def test_l4_the_gate_fixture_holds_a_leaf_that_would_reject_and_prints_none(gate_trees: Any) -> None:
    """The one fixture where the printed set differs (spec section 0.7). The root rejects, forty
    groups are tested, none rejects, and BH within ``g00`` alone -- computed here from ``cells``
    -- would reject the moved cell at ``q_within`` 0.046875. The level is untested with the
    right reason, and no family, no ``CellResult`` and no ``q_within`` exists. McNemar only."""
    multi, result = gate_trees["mcnemar_bh"]
    grouping, fault_lines, leaves = result.grouping, result.fault_lines, result.leaves
    # PF4 re-freeze (PF4.45): g00's limit is its cells' own and is admitted at the value the fixture
    # accepts, where it was at most the default 0.20.
    assert (grouping.key, grouping.n_groups) == ("grp", GATE_GROUPS) and grouping.group_mde[0] <= grouping.max_group_mde, grouping
    assert result.root.rejects is True and result.root.p_omnibus < Q, result.root.p_omnibus
    g00 = fault_lines.groups[0]
    assert fault_lines.tested is True and g00.label == "g00" and g00.q_group >= GATE_MIN_Q_GROUP and g00.rejects is False, (g00.p_group, g00.q_group)
    assert fault_lines.n_rejected_groups == 0 and fault_lines.rejected_groups == ()
    would_be = family_rows(multi, result, "g00")
    moved = would_be.loc[would_be["p"].idxmin()]
    assert len(would_be) == GATE_CELLS and moved["q_within"] == GATE_LEAF_Q_WITHIN and moved["q_within"] < Q, moved["q_within"]
    assert (leaves.tested, leaves.reason, leaves.families, leaves.n_families, leaves.n_tests, leaves.n_rejected) == (False, "no_group_rejected", (), 0, 0, 0)
    assert result.to_json()["leaves"]["families"] == []


# ---------- L5: reasons and precedence ----------


def test_l5_depth_two_reads_depth_whatever_the_root_did(lattice_trees: Any, axes: dict[str, Any], identical_trees: Any) -> None:
    """The procedure's configuration before the root: the lattice (root rejects, groups reject) and the
    identical pair (root does not reject) both read ``"depth"`` at ``depth=2``, with every count
    zero and no family."""
    twin = raw_frame("same-b", axes_cells(True))
    multi_same, _ = identical_trees["fisher_bh"]
    at_depth_two = lattice_trees.tree((EVENT,), "fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, depth=2)
    for name, result in (
        ("lattice", at_depth_two),
        ("identical", grown(axes["b"], twin, multi_same, axes["ma"], axes["mb"], n_permutations=500, seed=GOLDEN_SEED, depth=2)),
    ):
        leaves = result.leaves
        assert (leaves.tested, leaves.reason, leaves.families, leaves.n_families, leaves.n_tests, leaves.n_rejected) == (False, "depth", (), 0, 0, 0), (name, leaves)
        assert result.bound.depth_configured == 2, name
    assert at_depth_two.root.rejects is True


def test_l5_the_root_before_the_level_on_the_identical_pair_the_bh_pair_and_the_discordant_cell(identical_trees: Any, bh_trees: Any, discordant_trees: Any) -> None:
    """``depth=3``: the identical pair reads ``root_not_rejected`` under both schemes; the BH
    pair (root rejects, twenty groups tested, none rejected) reads ``no_group_rejected``; the
    discordant cell (grouping collapsed, root not rejected) reads ``root_not_rejected`` -- root
    first, the precedence P4.2's oracle fixed, extended by one."""
    for method, (_, result) in identical_trees.items():
        assert result.root.rejects is False and result.grouping.n_groups == 2, method
        assert (result.leaves.tested, result.leaves.reason, result.leaves.families) == (False, "root_not_rejected", ()), method
    _, bh = bh_trees["mcnemar_bh"]
    assert bh.root.rejects is True and bh.fault_lines.tested is True and bh.fault_lines.n_rejected_groups == 0
    assert (bh.leaves.tested, bh.leaves.reason, bh.leaves.families) == (False, "no_group_rejected", ())
    for method, (_, result) in discordant_trees.items():
        assert result.root.rejects is False and result.grouping.key == EXPECTED_WHOLE_GRID_KEY and result.fault_lines.reason == "root_not_rejected", method
        assert (result.leaves.tested, result.leaves.reason, result.leaves.families) == (False, "root_not_rejected", ()), method


# ---------- L6: the one-group collapse is the flat family ----------


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_l6_by_grid_at_depth_three_is_the_flat_family_bit_for_bit(lattice_trees: Any, three_outcome_grid: Any, method: str) -> None:
    """S25 section A's flat set = grid set on the public surface (22 = 22 under Fisher, 27 = 27
    under McNemar on the lattice): under ``by="grid"`` Level 2 is not a level,
    the leaves are one family labelled ``all`` over every common cell x event, ``q_within`` is
    ``cells.q`` bit for bit on every row of every event, the rejected set is the flat set and
    the bound is a two-level bound. The lattice (one event) and the three-outcome pair (two events)."""
    multi = lattice_trees.multi((EVENT,), method)
    grid = lattice_trees.tree((EVENT,), method, by=EXPECTED_WHOLE_GRID, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, depth=3)
    cases = [("lattice", multi, grid), ("three-outcome", *three_outcome_grid[method])]
    for name, multi_, result in cases:
        grouping, fault_lines, leaves, bound = result.grouping, result.fault_lines, result.leaves, result.bound
        assert (grouping.key, grouping.n_groups, grouping.labels) == (EXPECTED_WHOLE_GRID_KEY, 1, (EXPECTED_WHOLE_GRID_LABEL,)), (name, grouping.key)
        assert result.root.rejects is True and (fault_lines.tested, fault_lines.reason) == (False, "one_group"), name
        assert (leaves.tested, leaves.reason, leaves.n_families) == (True, None, 1), (name, leaves.reason)
        family = leaves.families[0]
        assert (family.label, family.key) == (EXPECTED_WHOLE_GRID_LABEL, EXPECTED_WHOLE_GRID_KEY), (name, family.label, family.key)
        frame = family_rows(multi_, result, EXPECTED_WHOLE_GRID_LABEL)
        assert np.array_equal(np.array([leaf.q_within for leaf in family.cells]), frame["flat_q"].to_numpy()), name
        assert nested_pairs(result) == flat_pairs(multi_) and leaves.n_rejected == family.n_rejected == multi_.n_rejected, (name, leaves.n_rejected, multi_.n_rejected)
        assert (bound.depth_configured, bound.depth) == (3, 2) and abs(bound.bound - expected_bound(2, multi_.q)) <= BOUND_TOLERANCE, (name, bound)
    assert cases[0][2].leaves.n_rejected == sum(lattice.directions(LATTICE_REFERENCES[method](EVENT))) == LATTICE_FLAT_REJECTIONS[method]


def test_l6_by_grid_at_depth_two_reads_depth_and_a_one_level_bound(lattice_trees: Any) -> None:
    multi = lattice_trees.multi((EVENT,), "fisher_bh")
    result = lattice_trees.tree((EVENT,), "fisher_bh", by=EXPECTED_WHOLE_GRID, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, depth=2)
    assert (result.leaves.tested, result.leaves.reason, result.leaves.families) == (False, "depth", ())
    assert (result.bound.depth_configured, result.bound.depth) == (2, 1) and abs(result.bound.bound - expected_bound(1, multi.q)) <= BOUND_TOLERANCE, result.bound


# ---------- L7: golden, the lattice ----------


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_l7_golden_lattice_by_load_rejects_the_pinned_leaf_counts_and_contains_the_flat_set(load_trees: Any, method: str) -> None:
    """Three families in label order with exactly the pinned ``n_rejected`` under each scheme
    (22 / 29), and the flat set (22 / 27, the references' counts) inside them: equal to it under
    Fisher, strictly inside under McNemar. The three groups sit at the floor, so the set is not
    Monte Carlo."""
    multi, result = load_trees[method]
    families = result.leaves.families
    assert tuple(family.label for family in families) == LATTICE_LOAD_REJECTED, [f.label for f in families]
    assert tuple(family.n_rejected for family in families) == LATTICE_LOAD_LEAVES[method], [f.n_rejected for f in families]
    assert result.leaves.n_rejected == sum(LATTICE_LOAD_LEAVES[method])
    flat, nested = flat_pairs(multi), nested_pairs(result)
    assert len(flat) == sum(lattice.directions(LATTICE_REFERENCES[method](EVENT))) == LATTICE_FLAT_REJECTIONS[method], len(flat)
    assert flat <= nested, (len(flat), len(nested))
    assert (flat == nested) if method == "fisher_bh" else (flat < nested), (method, len(flat), len(nested))


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_l7_golden_lattice_by_gain_pins_the_floor_groups_and_the_four_named_cells(gain_trees: Any, method: str) -> None:
    """The nine floor groups' counts are deterministic and pinned; ``0.9`` and ``1.2`` are off the
    floor and pinned only through L3's recompute. Under Fisher three cells the flat family did
    not reject are rejected leaves and one it did (``gain = 1.2, load = 20``) is not -- the row
    must not copy the flat verdict or the flat ``q``. Under McNemar the nested set strictly
    contains the flat set."""
    multi, result = gain_trees[method]
    by_label = {family.label: family for family in result.leaves.families}
    assert tuple(by_label[label].n_rejected for label in LATTICE_GAIN_AT_FLOOR) == LATTICE_GAIN_FLOOR_LEAVES[method], [by_label[label].n_rejected for label in LATTICE_GAIN_AT_FLOOR]
    nested, flat = nested_pairs(result), flat_pairs(multi)
    leaf_by_hash = {leaf.config_hash: leaf for family in result.leaves.families for leaf in family.cells}
    cells = multi.by_event[EVENT].cells.set_index(multi.by_event[EVENT].cells["config_hash"].astype(str))
    if method == "fisher_bh":
        for h, label in LATTICE_GAIN_NESTED_ONLY_FISHER.items():
            leaf = leaf_by_hash[h]
            assert leaf.group == label and leaf.rejects is True and (h, EVENT) not in flat and cells.loc[h, "q"] >= Q, (h, leaf.q_within, cells.loc[h, "q"])
        h, label = LATTICE_GAIN_FLAT_ONLY_FISHER
        leaf = leaf_by_hash[h]
        assert leaf.group == label and (h, EVENT) in flat and cells.loc[h, "q"] < Q, (h, cells.loc[h, "q"])
        assert leaf.rejects is False and leaf.q_within >= Q and leaf.p == cells.loc[h, "p"], (h, leaf.q_within, leaf.p)
        assert nested - flat == {(h, EVENT) for h in LATTICE_GAIN_NESTED_ONLY_FISHER} and flat - nested == {(LATTICE_GAIN_FLAT_ONLY_FISHER[0], EVENT)}
    else:
        assert flat < nested, (len(flat), len(nested))
    assert len(flat) == sum(lattice.directions(LATTICE_REFERENCES[method](EVENT))) == LATTICE_FLAT_REJECTIONS[method]


# ---------- L8: the bound, recomputed; configured, not reached ----------


def test_l8_depth_two_and_three_on_the_lattice_read_0288_and_0432_recomputed(lattice_trees: Any, gain_trees: Any) -> None:
    multi, three = gain_trees["fisher_bh"]
    two = lattice_trees.tree((EVENT,), "fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, depth=2)
    for result, depth, printed in ((two, 2, 0.288), (three, 3, 0.432)):
        bound = result.bound
        assert (bound.depth_configured, bound.depth, bound.q) == (depth, depth, multi.q), bound
        assert abs(bound.bound - expected_bound(depth, multi.q)) <= BOUND_TOLERANCE and abs(bound.bound - printed) <= 1e-12, bound


def test_l8_bound_and_depth_are_byte_identical_across_seed_twin_and_verdict(lattice_trees: Any, gain_trees: Any, axes: dict[str, Any], axes_trees: Any, identical_trees: Any, bh_trees: Any) -> None:
    """Nothing after the draw touches ``depth`` or ``bound``: seed 0 and seed 1; the axes pair
    and its unmoved twin (F7's fixture); the identical pair (root not rejected) and the axes
    pair (root rejected); the BH pair (root rejected, no group rejected) and the lattice (groups
    rejected) -- all at configured depth 3 with at least two groups. A builder who reads
    ``depth`` off what was reached prints 0.144 on the identical pair and 0.288 on the BH pair
    and fails here alone."""
    multi, seed_zero = gain_trees["fisher_bh"]
    # PF4 re-freeze (PF4.45): grown at the value gain_trees grows at, where gain resolves.
    seed_one = lattice_trees.tree((EVENT,), "fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED + 1, max_group_mde=ADMITTING_MAX_GROUP_MDE)
    twin = raw_frame("axes-b", axes_cells(False))
    multi_twin = quiet_multi_diff(axes["a"], twin, axes["ma"], axes["mb"], events=("fail",), method="mcnemar_bh")
    unmoved = grown(axes["a"], twin, multi_twin, axes["ma"], axes["mb"], n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    _, moved = axes_trees["mcnemar_bh"]
    _, identical = identical_trees["mcnemar_bh"]
    _, bh = bh_trees["mcnemar_bh"]
    assert unmoved.root.rejects is False and moved.root.rejects is True and identical.root.rejects is False and bh.fault_lines.n_rejected_groups == 0 and seed_zero.fault_lines.n_rejected_groups > 0
    references = [json_bytes(result.bound.to_json()) for result in (seed_zero, seed_one, unmoved, moved, identical, bh)]
    assert len(set(references)) == 1, references
    assert seed_zero.bound.depth == 3 and abs(seed_zero.bound.bound - expected_bound(3, multi.q)) <= BOUND_TOLERANCE


# ---------- L9: minted once ----------


def test_l9_delta_star_is_typed_once_and_the_bound_is_minted_in_one_function() -> None:
    """**The rule, in prose.** ADR-062: ``DELTA_STAR`` is assigned once, at module level in
    ``tree.py``; the name is read inside exactly one function, and that function holds exactly
    one top-level ``BinOp`` chain, which reaches ``DELTA_STAR`` (module docstring); no constant
    1.44, 0.432, 0.288 or 0.144 exists anywhere in ``tree.py`` outside that assignment, and none
    in ``cli.py``, which also assigns no name ``DELTA_STAR``."""
    module = parsed(TREE_SOURCE)
    enclosing = enclosing_functions(module)
    parent = parents(module)
    definitions = [
        node for node in module.body
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and any(isinstance(t, ast.Name) and t.id == "DELTA_STAR" for t in (node.targets if isinstance(node, ast.Assign) else [node.target]))
    ]
    assert len(definitions) == 1, [getattr(d, "lineno", None) for d in definitions]
    allowed = {id(node) for node in ast.walk(definitions[0]) if isinstance(node, ast.Constant)}
    stray = [(node.lineno, node.value) for node in ast.walk(module) if isinstance(node, ast.Constant) and isinstance(node.value, float) and node.value in FORBIDDEN_BOUND_CONSTANTS and id(node) not in allowed]
    assert stray == [], stray
    readers = {enclosing.get(node, "<module>") for node in ast.walk(module) if isinstance(node, ast.Name) and node.id == "DELTA_STAR" and isinstance(node.ctx, ast.Load)}
    assert len(readers) == 1 and "<module>" not in readers, readers
    function = next(node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == next(iter(readers)))
    chains = [node for node in ast.walk(function) if isinstance(node, ast.BinOp) and not isinstance(parent.get(node), ast.BinOp)]
    assert len(chains) == 1 and "DELTA_STAR" in mentioned_in(chains[0]), (function.name, [c.lineno for c in chains])
    cli_module = parsed(CLI_SOURCE)
    cli_stray = [(node.lineno, node.value) for node in ast.walk(cli_module) if isinstance(node, ast.Constant) and isinstance(node.value, float) and node.value in FORBIDDEN_BOUND_CONSTANTS]
    cli_defined = [node.lineno for node in ast.walk(cli_module) if isinstance(node, (ast.Assign, ast.AnnAssign)) and any(isinstance(t, ast.Name) and t.id == "DELTA_STAR" for t in (node.targets if isinstance(node, ast.Assign) else [node.target]))]
    assert cli_stray == [] and cli_defined == [], (cli_stray, cli_defined)


#: L9: the names under which a function compares a partition's cardinality. The depth function
#: is private and unnamed, so the no-literal rule is applied to every ``Compare`` in ``tree.py``
#: that mentions one of these, as well as to every ``Compare`` inside a reader of the constant.
CARDINALITY_NAMES = frozenset({"n_groups", "labels", "groups", "group_sizes", "partition", "sizes"})


def test_l9_min_family_groups_is_read_at_three_sites_with_no_literal_beside_it() -> None:
    """**The rule, in prose.** ADR-021's shape (spec section 3.9): one constant, three readers.
    The name ``MIN_FAMILY_GROUPS`` is loaded inside at least three functions of ``tree.py``,
    ``_consider`` and ``_fault_lines`` among them; and no ``ast.Compare`` that sits inside a
    function reading it, or that mentions a partition-cardinality name anywhere in ``tree.py``
    (``CARDINALITY_NAMES``, because the depth function has no pinned name), has an integer
    constant operand of 1 or 2 -- the literal ``> 1`` and ``< 2`` this packet replaces."""
    module = parsed(TREE_SOURCE)
    enclosing = enclosing_functions(module)
    readers = {enclosing.get(node, "<module>") for node in ast.walk(module) if isinstance(node, ast.Name) and node.id == "MIN_FAMILY_GROUPS" and isinstance(node.ctx, ast.Load)}
    assert len(readers - {"<module>"}) >= 3 and {"_consider", "_fault_lines"} <= readers, readers
    offenders: list[tuple[str, int]] = []
    for function in ast.walk(module):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Compare) or not (function.name in readers or mentioned_in(node) & CARDINALITY_NAMES):
                continue
            for operand in (node.left, *node.comparators):
                if isinstance(operand, ast.Constant) and type(operand.value) is int and operand.value in (1, 2):
                    offenders.append((function.name, node.lineno))
    assert offenders == [], offenders


# ---------- L10: no conditional claim, checkable ----------


def masked(text: str, result: Any, requested: str | None) -> str:
    """User data out before the vocabulary check (spec section 8 trap 11): the requested key,
    every group label, every config value and every event name."""
    out = text
    for piece in [requested or "", *result.grouping.labels, *result.root.events]:
        if piece:
            out = out.replace(piece, "")
    for family in result.leaves.families:
        for leaf in family.cells:
            for value in leaf.config.values():
                out = out.replace(str(value), "")
    return out.lower()


def test_l10_no_reason_and_no_block_line_uses_the_conditional_vocabulary(every_tree: Any, synth_root: Path) -> None:
    """The tempting sentence -- "given the group rejected, these cells are reliable at q" -- is
    false (spec section 3.6) and cannot be printed. Every ``Leaves.reason`` on every fixture;
    every line of the ``cells:`` and ``bound:`` blocks on the axes pair, the identical pair and
    the multi-event pair, with and without ``--depth 2`` and ``--by grid``, masked first. The
    ``cells:`` block quotes ``CELL_NULL`` when tested; the ``bound:`` block says ``outer-nodes``
    and never ``fdr``."""
    for name, _, result in every_tree:
        reason = (result.leaves.reason or "").lower()
        for phrase in FORBIDDEN_VOCABULARY:
            assert phrase not in reason, (name, phrase, reason)
    for a, b, events in (("axes-a", "axes-b", ("fail",)), ("same-a", "same-b", ("fail",)), ("me-a", "me-b", ME_EVENTS)):
        for extra in ((), ("--depth", "2"), ("--by", "grid")):
            argv = ["--store", str(synth_root), "diff", a, b]
            for event in events:
                argv += ["--event", event]
            knobs: dict[str, Any] = {"depth": int(extra[1])} if extra[:1] == ("--depth",) else ({"by": extra[1]} if extra else {})
            _, result = store_tree(synth_root, a, b, events=events, method="fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, **knobs)
            code, out, err = run_cli(argv + list(extra))
            # A shared salt now adds one note line on stderr (spec section 5.4).
            assert code == 0 and without_notes(err) == "", (a, extra, out, err)
            cells, bound = cells_block(out), bound_block(out)
            assert cells and bound, (a, extra, out)
            if result.leaves.tested:
                assert f'"{EXPECTED_CELL_NULL}"' in cells[0], cells[0]
            assert "outer-nodes" in "\n".join(bound) and "fdr" not in "\n".join(bound).lower(), bound
            text = masked("\n".join(cells + bound), result, extra[1] if extra[:1] == ("--by",) else None)
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in text, (a, extra, phrase, cells, bound)


def test_l10_no_field_name_and_no_json_key_carries_the_conditional_structure(every_tree: Any) -> None:
    """A per-family rate or level is where the conditional claim would live as a number, and it
    cannot exist: no field of the four structures and no key at any depth under ``"leaves"``
    or ``"bound"`` contains a forbidden substring (``config`` keys skipped, as F19); no key under
    ``"leaves"`` contains ``bound``; ``Bound`` has exactly section 2's six fields; the other
    three carry at least section 2's."""
    t = tree()
    for cls, expected in ((t.CellResult, CELL_RESULT_FIELDS), (t.CellFamily, CELL_FAMILY_FIELDS), (t.Leaves, LEAVES_FIELDS), (t.Bound, BOUND_FIELDS), (t.TreeResult, TREE_RESULT_FIELDS)):
        names = [field.name for field in dataclasses.fields(cls)]
        assert set(names) >= set(expected), (cls.__name__, sorted(set(expected) - set(names)))
        for name in names:
            assert not any(bad in name.lower() for bad in FORBIDDEN_FIELD_SUBSTRINGS), (cls.__name__, name)
    assert [field.name for field in dataclasses.fields(t.Bound)] == list(BOUND_FIELDS)
    for name, _, result in every_tree:
        payload = result.to_json()
        assert set(payload) == set(TREE_RESULT_FIELDS), (name, sorted(payload))
        for key in walk_keys(payload["leaves"]):
            assert not any(bad in key.lower() for bad in FORBIDDEN_FIELD_SUBSTRINGS) and "bound" not in key.lower(), (name, key)
        for key in walk_keys(payload["bound"]):
            assert not any(bad in key.lower() for bad in FORBIDDEN_FIELD_SUBSTRINGS), (name, key)
        assert set(payload["bound"]) == set(BOUND_FIELDS), (name, sorted(payload["bound"]))


# ---------- L11: the CLI does no arithmetic on any tree field ----------


def test_l11_the_cli_does_no_arithmetic_on_any_tree_field() -> None:
    """**The rule, in prose.** ``cli.py`` reads a field and prints it; it may ask whether one is
    ``None``; it may not do arithmetic on one. Any ``BinOp`` whose subtree reaches, as an
    attribute, one of O17's thirteen, ``n_uninformative_cells``, any field of S26's five
    structures or any numeric or container field of the four P4.3 structures, or, as a bare
    name, one of F21's names or the P4.3 names that collide with nothing, fails. The string
    fields are unguarded as attributes because ``event`` sits inside a ``BinOp`` at
    ``cli.py:1318`` (step zero item 5); the guard's literal is checked against that measured
    collision set first, so a mis-written guard is red for its own reason and not the tree's.
    ADR-072's form; the superset of O17, F21 and, on ``n_rejected``, S24's C19 (module
    docstring, step zero item 5)."""
    assert not (CLI_GUARDED_ATTRIBUTES & COLLIDING_ATTRIBUTES_AT_BASE), sorted(CLI_GUARDED_ATTRIBUTES & COLLIDING_ATTRIBUTES_AT_BASE)
    assert not (CLI_GUARDED_NAMES & COLLIDING_NAMES_AT_BASE), sorted(CLI_GUARDED_NAMES & COLLIDING_NAMES_AT_BASE)
    assert "event" in P43_STRING_FIELDS and "event" not in CLI_GUARDED_ATTRIBUTES and EVENT_COLLISION_LINE == 1318
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(parsed(CLI_SOURCE)):
        if not isinstance(node, ast.BinOp):
            continue
        attributes = {child.attr for child in ast.walk(node) if isinstance(child, ast.Attribute)}
        names = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
        hit = (attributes & CLI_GUARDED_ATTRIBUTES) | (names & CLI_GUARDED_NAMES)
        if hit:
            offenders.append((node.lineno, sorted(hit)[0]))
    assert offenders == [], offenders


# ---------- L12, L13: P4.2's build, pinned ----------


def test_l12_refusal_fields_on_the_reasons_that_are_not_underpowered_as_built(pair: Any, gain_trees: Any) -> None:
    """``n_groups`` is present wherever a partition was built (1 for ``one_group``) and ``None``
    where none was (``unsupported``, ``not_shared``); the power rule's two findings are present
    only for ``underpowered``. A builder who offers an override on ``one_group``, or computes a
    partition for a ``not_shared`` key, fails alone."""
    a, b = raw_frame("one-a", one_value_cells(False)), raw_frame("one-b", one_value_cells(True))
    ma, mb = manifest("one-a", SALT, AXES_TYPES_TASK_FIRST), manifest("one-b", SALT, AXES_TYPES_TASK_FIRST)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="mcnemar_bh")
    one_group = [r for r in grown(a, b, multi, ma, mb, n_permutations=50, seed=GOLDEN_SEED).grouping.refused if r.reason == "one_group"]
    assert [(r.key, r.n_groups, r.n_resolvable_groups, r.offered_max_group_mde) for r in one_group] == [("temp", 1, None, None)]
    ga, gb, gma, gmb = pair
    lattice_multi, _ = gain_trees["mcnemar_bh"]
    load_first = reordered(gma, {Y: "continuous", X: "continuous"})
    b_only_gain = reordered(gmb, {X: "continuous"})
    # PF4 re-freeze (PF4.45): at the default gain would be refused too; at a value that admits it the
    # not_shared row is the only one.
    not_shared = grown(ga, gb, lattice_multi, load_first, b_only_gain, n_permutations=50, seed=GOLDEN_SEED, max_group_mde=ADMITTING_MAX_GROUP_MDE).grouping.refused
    assert [(r.key, r.rung, r.reason, r.n_groups, r.n_resolvable_groups, r.offered_max_group_mde) for r in not_shared] == [(Y, "axis", "not_shared", None, None, None)]
    # PF4 (PF4.6): "kind" is no longer a trace grouping refused as unsupported; it is an unknown
    # grouping, raised before any partition or permutation, so it leaves no refusal row at all.
    with pytest.raises(tree().UnknownGrouping):
        grown(ga, gb, lattice_multi, gma, gmb, by="kind", n_permutations=50, seed=GOLDEN_SEED)


def test_l13_a_requested_axis_declared_in_one_manifest_only_is_not_shared_and_resolution_continues(pair: Any, gain_trees: Any, synth_root: Path) -> None:
    """The name is known to one run and the pair cannot group by it: ``not_shared`` at the
    ``requested`` rung, next the trace rung, then the axis rung resolves ``gain``; never
    ``UnknownGrouping``, which ``by="pressure"`` (declared by neither) still raises. Through the
    CLI on the synthetic store (``axes-a`` declares ``task, temp``; ``axes-b-task-only`` declares
    ``task``): ``--by temp`` produces the row and the block's ``refused`` line names all four."""
    a, b, ma, mb = pair
    multi, _ = gain_trees["fisher_bh"]
    b_only_gain = reordered(mb, {X: "continuous"})
    # PF4 re-freeze (PF4.45): the axis rung resolves gain at a value that admits it (the default
    # refuses it).
    grouping = grown(a, b, multi, ma, b_only_gain, by=Y, n_permutations=50, seed=GOLDEN_SEED, max_group_mde=ADMITTING_MAX_GROUP_MDE).grouping
    rows = [(r.key, r.rung, r.reason, r.next_rung, r.n_groups, r.n_resolvable_groups, r.offered_max_group_mde) for r in grouping.refused]
    assert rows == [(Y, "requested", "not_shared", "trace", None, None, None)], rows
    assert (grouping.resolved_by, grouping.key, grouping.requested) == ("axis", X, Y)
    with pytest.raises(tree().UnknownGrouping):
        grown(a, b, multi, ma, b_only_gain, by="pressure", n_permutations=50, seed=GOLDEN_SEED)
    _, stored = store_tree(synth_root, "axes-a", "axes-b-task-only", events=("fail",), method="fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, by="temp")
    refusal = stored.grouping.refused[0]
    assert (refusal.key, refusal.rung, refusal.reason, refusal.next_rung) == ("temp", "requested", "not_shared", "trace")
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b-task-only", "--event", "fail", "--by", "temp"])
    # A shared salt now adds one note line on stderr (spec section 5.4).
    assert code == 0 and without_notes(err) == "", (out, err)
    line = fault_lines_block(out)[1]
    assert "refused" in line and all(piece in line for piece in ("temp", "requested", "not_shared", "trace")), line


# ---------- L14, L24: --depth is validated before any draw; refusals before drawing ----------


@pytest.mark.parametrize("depth", (1, 4, "3", 3.0, True), ids=repr)
def test_l14_a_depth_outside_depths_is_refused_from_tree_before_any_draw(pair: Any, gain_trees: Any, depth: Any) -> None:
    """O13's pin extended: at ``n_permutations = 10**6`` a refusal that validates first returns in
    milliseconds. ``"3"``, ``3.0`` and ``True`` are refused rather than coerced."""
    a, b, ma, mb = pair
    multi, _ = gain_trees["fisher_bh"]
    started = time.perf_counter()
    with pytest.raises(tree().TreeError):
        grown(a, b, multi, ma, mb, n_permutations=REFUSAL_PERMUTATIONS, seed=GOLDEN_SEED, depth=depth)
    assert time.perf_counter() - started < REFUSAL_BUDGET_SECONDS


def test_l14_the_cli_refuses_depth_one_and_four_and_passes_two_and_three(synth_root: Path) -> None:
    """argparse ``choices`` is the parser's own refusal, exit 2 with no traceback on either
    stream; ``--depth 2`` and ``--depth 3`` reach the call and the JSON carries the argument."""
    for value in ("1", "4"):
        code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--depth", value])
        assert code == 2 and "Traceback" not in out + err and "error" in err, (value, out, err)
    for value in ("2", "3"):
        # --json replaces --format json (spec section 5.6).
        code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--depth", value, "--json"])
        # A shared salt now adds one note line on stderr (spec section 5.4).
        assert code == 0 and without_notes(err) == "", (value, out, err)
        assert json.loads(out)["tree"]["bound"]["depth_configured"] == int(value), value


def test_l14_the_range_check_lives_in_tree_py_and_not_in_cli_py() -> None:
    """**The rule, in prose.** The CLI parses an int and decides nothing (spec section 8 trap 13,
    F8's form): no ``ast.Compare`` in ``cli.py`` whose subtree names ``depth``, as an attribute
    or a bare name; ``tree.py``'s check is what the runtime tests above reach."""
    offenders = [node.lineno for node in ast.walk(parsed(CLI_SOURCE)) if isinstance(node, ast.Compare) and "depth" in mentioned_in(node)]
    assert offenders == [], offenders


@pytest.mark.parametrize("case", ("depth-4", "unknown-by", "bad-override", "different-pair"))
def test_l24_refusals_fire_before_any_permutation_is_drawn(pair: Any, gain_trees: Any, case: str) -> None:
    """F30's pin plus the new knob: each refuses from ``tree()`` in under ten seconds at
    ``n_permutations = 10**6``."""
    a, b, ma, mb = pair
    multi, _ = gain_trees["fisher_bh"]
    frames, knobs = (a, b), {"n_permutations": REFUSAL_PERMUTATIONS, "seed": GOLDEN_SEED}
    if case == "depth-4":
        knobs["depth"] = 4
    elif case == "unknown-by":
        knobs["by"] = "nonsense"
    elif case == "bad-override":
        knobs["max_group_mde"] = 2.0
    else:
        frames = (a, a)
    started = time.perf_counter()
    with pytest.raises(tree().TreeError):
        grown(frames[0], frames[1], multi, ma, mb, **knobs)
    assert time.perf_counter() - started < REFUSAL_BUDGET_SECONDS


# ---------- L15: depth changes nothing above Level 3 ----------


def test_l15_depth_changes_nothing_above_level_three(pair: Any, lattice_trees: Any, gain_trees: Any) -> None:
    """One draw, three levels: ``depth=2`` and ``depth=3`` on the lattice by ``gain`` at the same seed give
    byte-identical ``root``, ``grouping`` and ``fault_lines`` payloads, and the tree's root is
    still ``omnibus`` at either depth (F11 restated at ``depth=2``)."""
    a, b, _, _ = pair
    multi, three = gain_trees["fisher_bh"]
    # PF4 re-freeze (PF4.45): grown at the value gain_trees grows at, where gain resolves.
    two = lattice_trees.tree((EVENT,), "fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED, depth=2, max_group_mde=ADMITTING_MAX_GROUP_MDE)
    for key in ("root", "grouping", "fault_lines"):
        assert json_bytes(two.to_json()[key]) == json_bytes(three.to_json()[key]), key
    root = tree().omnibus(a, b, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    assert json_bytes(two.root.to_json()) == json_bytes(root.to_json()) == json_bytes(three.root.to_json())
    pd.testing.assert_frame_equal(two.root.units, root.units)


# ---------- L16: the CLI blocks ----------


CLI_PAIRS = (("axes-a", "axes-b", ("fail",)), ("same-a", "same-b", ("fail",)), ("me-a", "me-b", ME_EVENTS))


def cli_pair(synth_root: Path, a: str, b: str, events: Sequence[str], *extra: str, **knobs: Any) -> tuple[Any, Any, str]:
    """The stored pair through ``main()`` beside the same tree built here with the CLI's knobs."""
    multi, result = store_tree(synth_root, a, b, events=events, method="fisher_bh", **{"n_permutations": GOLDEN_PERMUTATIONS, "seed": GOLDEN_SEED, **knobs})
    # PF3 (Q17, spec sections 4.4 and 14; rule R1): the synthetic pairs share a salt, so the default is now the
    # paired test; the tree built beside the CLI is the unpaired test's, so the CLI names it.
    argv = ["--store", str(synth_root), "diff", a, b, "--method", "fisher_bh"]
    for event in events:
        argv += ["--event", event]
    code, out, err = run_cli(argv + list(extra))
    # A shared salt now adds one note line on stderr (spec section 5.4).
    assert code == 0 and without_notes(err) == "", (a, b, extra, out, err)
    return multi, result, out


def test_l16_the_cells_block_follows_the_fault_lines_block_and_the_bound_block_follows_it(synth_root: Path) -> None:
    """By index, never ``endswith``; each block is its head line plus the indented lines after
    it, and the next block starts after the previous one ends. Neither is pinned as the tail."""
    for a, b, events in CLI_PAIRS:
        _, _, out = cli_pair(synth_root, a, b, events)
        omnibus, fault, cells, bound = omnibus_block(out), fault_lines_block(out), cells_block(out), bound_block(out)
        assert omnibus and fault and cells and bound, (a, out)
        assert block_start(out, fault) >= block_start(out, omnibus) + len(omnibus), (a, "omnibus", "fault lines")
        assert block_start(out, cells) >= block_start(out, fault) + len(fault), (a, "fault lines", "cells")
        assert block_start(out, bound) >= block_start(out, cells) + len(cells), (a, "cells", "bound")
        assert heads(out, "cells:") == 1 and heads(out, "bound:") == 1, a


def test_l16_the_cells_head_line_carries_the_fields_when_tested_and_the_form_when_not(synth_root: Path) -> None:
    """Tested (the axes pair, the multi-event pair): ``n_families``, ``n_tests``, ``n_rejected``
    and ``q`` under rule 10 (``:g`` before it) and the quoted null. Not tested (the identical pair): the block is
    one line saying ``not tested`` with the reason's word (module docstring)."""
    for a, b, events in CLI_PAIRS:
        _, result, out = cli_pair(synth_root, a, b, events)
        leaves, block = result.leaves, cells_block(out)
        head, tokens = block[0], numeric_tokens(block[0])
        if leaves.tested:
            assert f'"{EXPECTED_CELL_NULL}"' in head, head
            # Counts and q print under rule 10 (spec section 5.4), not ``:g``.
            for field, render in (("n_families", count), ("n_tests", count), ("n_rejected", count), ("q", rule_10_p)):
                assert render(getattr(leaves, field)) in tokens, (a, field, head)
        else:
            assert leaves.reason == "root_not_rejected" and len(block) == 1 and "not tested" in head and "root" in head, (a, block)


def test_l16_one_family_line_per_family_in_order_carrying_the_counts_and_the_mdes(synth_root: Path) -> None:
    for a, b, events in CLI_PAIRS:
        _, result, out = cli_pair(synth_root, a, b, events)
        lines = family_lines(cells_block(out))
        assert len(lines) == result.leaves.n_families, (a, lines)
        for family, line in zip(result.leaves.families, lines, strict=True):
            tokens = numeric_tokens(line)
            assert family.label in line and "rejected" in line, (a, family.label, line)
            # Counts and MDEs print under rule 10 (spec section 5.4), not ``:g``.
            for field, render in (("n_tests", count), ("n_rejected", count), ("mde_median", fraction), ("mde_max", fraction)):
                # PF4 re-freeze (PF4.27): a null limit prints no number.
                if field.startswith("mde") and is_null(getattr(family, field)):
                    assert "nan" not in tokens, (a, family.label, field, line)
                    continue
                assert render(getattr(family, field)) in tokens, (a, family.label, field, line)


def test_l16_one_line_per_rejected_leaf_carrying_the_config_the_event_and_three_numbers(synth_root: Path) -> None:
    """Under its family line, indented at least four spaces, in ``cells`` order: every
    ``key=value`` of the config, the event, and ``delta``, ``q_within``, ``mde`` under rule 10 --
    and no other number, which is what keeps a flat ``q``, a ``p`` or an interval off the block.
    A leaf with ``rejects is False`` has no line: the axes pair prints none, the multi-event
    pair prints two ``fail`` lines and no ``crash`` line."""
    for a, b, events in CLI_PAIRS:
        _, result, out = cli_pair(synth_root, a, b, events)
        block = cells_block(out)
        rejected = [leaf for family in result.leaves.families for leaf in family.cells if leaf.rejects]
        lines = leaf_lines(block)
        assert len(lines) == len(rejected) == result.leaves.n_rejected, (a, len(lines), len(rejected))
        for leaf, line in zip(rejected, lines, strict=True):
            for key, value in leaf.config.items():
                assert f"{key}={value}" in line or (isinstance(value, (int, float)) and f"{key}={g(value)}" in line), (a, key, value, line)
            assert leaf.event in line, (a, leaf.event, line)
            tokens = numeric_tokens(line)
            # delta and MDE print to three decimals and q under rule 10 (spec section 5.4), not ``:g``.
            printed = {"delta": fraction(leaf.delta), "q_within": rule_10_p(leaf.q_within), "mde": fraction(leaf.mde)}
            for field, rendered in printed.items():
                assert rendered in tokens, (a, field, line)
            allowed = set(printed.values()) | config_tokens(leaf.config)
            assert set(tokens) <= allowed, (a, line, sorted(set(tokens) - allowed))
        if a == "me-a":
            assert len(lines) == 2 and all("fail" in line and "crash" not in line for line in lines), lines
        if a == "axes-a":
            assert lines == [] and result.leaves.n_families == 1, block


def test_l16_the_bound_head_line_carries_the_five_fields_and_the_set(synth_root: Path) -> None:
    for a, b, events in CLI_PAIRS:
        _, result, out = cli_pair(synth_root, a, b, events)
        head = bound_block(out)[0]
        tokens = numeric_tokens(head)
        # The depths are counts, the bound a rate to three decimals and q a p-value under rule 10
        # (spec section 5.4). delta_star is a constant rule 10 does not name: ``:g`` or three decimals.
        bound = result.bound
        for field, rendered in (("depth", {count(bound.depth)}), ("depth_configured", {count(bound.depth_configured)}), ("bound", {fraction(bound.bound)}), ("q", {rule_10_p(bound.q)}), ("delta_star", {g(bound.delta_star), fraction(bound.delta_star)})):
            assert rendered & set(tokens), (a, field, head)
        assert "outer-nodes" in head, head


def test_l16_depth_two_prints_not_tested_depth_two_and_still_the_bound(synth_root: Path) -> None:
    _, result, out = cli_pair(synth_root, "axes-a", "axes-b", ("fail",), "--depth", "2", depth=2)
    block, bound = cells_block(out), bound_block(out)
    assert result.leaves.reason == "depth" and len(block) == 1 and "not tested" in block[0] and g(2) in numeric_tokens(block[0]), block
    # The bound is a rate, printed to three decimals under rule 10 (spec section 5.4).
    assert bound and (result.bound.depth_configured, result.bound.depth) == (2, 2) and fraction(result.bound.bound) in numeric_tokens(bound[0]), bound


def test_l16_the_json_carries_leaves_and_bound_equal_to_to_json_after_a_round_trip(synth_root: Path) -> None:
    for a, b, events, extra, knobs in (
        ("me-a", "me-b", ME_EVENTS, (), {}),
        ("axes-a", "axes-b", ("fail",), ("--depth", "2", "--permutations", "300", "--seed", "3"), {"depth": 2, "n_permutations": 300, "seed": 3}),
    ):
        # --json replaces --format json (spec section 5.6).
        _, result, out = cli_pair(synth_root, a, b, events, "--json", *extra, **knobs)
        payload = json.loads(out)
        assert payload["tree"]["leaves"] == json.loads(json.dumps(result.leaves.to_json())), a
        assert payload["tree"]["bound"] == json.loads(json.dumps(result.bound.to_json())), a
        assert payload["tree"] == json.loads(json.dumps(result.to_json())), a


# ---------- L17, L18: --methods all, and no comparable cell ----------


def test_l17_methods_all_text_prints_the_four_blocks_once_each_after_the_table() -> None:
    """Draft ADR-070 extended: the table, then the primary's omnibus, fault-lines, ``cells:`` and
    ``bound:`` blocks, each once, found by line index. ``--permutations 200``: a test about the
    shape of the stream, not the omnibus."""
    code, out, err = run_cli(["--store", str(LATTICE_ROOT), "diff", LATTICE_A, LATTICE_B, "--event", EVENT, "--methods", "all", "--permutations", "200"])
    # A shared salt now adds one note line on stderr (spec section 5.4).
    assert code == 0 and without_notes(err) == "", (out, err)
    lines = out.splitlines()
    first = {head: next(i for i, line in enumerate(lines) if line.startswith(head)) for head in ("| method |", "omnibus: ", "fault lines:", "cells:", "bound:")}
    assert first["| method |"] < first["omnibus: "] < first["fault lines:"] < first["cells:"] < first["bound:"], first
    assert all(heads(out, head) == 1 for head in ("omnibus: ", "fault lines:", "cells:", "bound:")), out
    assert cells_block(out) and bound_block(out), out


def test_l17_methods_all_json_keeps_exactly_the_three_method_keys_and_carries_no_tree() -> None:
    """``test_i9_diff_methods_all_json_keys`` and F22 pin the same set; a ``"tree"`` key beside
    three method objects fails all three."""
    # --json replaces --format json (spec section 5.6).
    code, out, err = run_cli(["--store", str(LATTICE_ROOT), "diff", LATTICE_A, LATTICE_B, "--event", EVENT, "--methods", "all", "--json", "--permutations", "200"])
    # A shared salt now adds one note line on stderr (spec section 5.4).
    assert code == 0 and without_notes(err) == "", (out, err)
    payload = json.loads(out)
    # --json adds schema, verdict, sentence, next and any key ending _note around the keys it
    # keeps (spec section 5.6).
    envelope = {"schema", "verdict", "sentence", "next"} | {k for k in payload if k.endswith("_note")}
    # PF4 (PF4.8, section 8.5): the payload now carries the primary method's omnibus and tree (with
    # its leaves and bound) beside the three method keys, and section 8.4's threshold and its
    # source; omnibus and tree are the objects the single-method --json prints for the same knobs.
    pf4_keys = {"omnibus", "tree", "threshold", "threshold_source"}
    assert set(payload) - envelope - pf4_keys == set(METHODS), sorted(payload)
    assert {"omnibus", "tree"} <= set(payload) and {"leaves", "bound"} <= set(payload["tree"]), sorted(payload)
    code, single_out, err = run_cli(["--store", str(LATTICE_ROOT), "diff", LATTICE_A, LATTICE_B, "--event", EVENT, "--json", "--permutations", "200"])
    assert code == 0 and without_notes(err) == "", (single_out, err)
    single = json.loads(single_out)
    assert payload["omnibus"] == single["omnibus"] and payload["tree"] == single["tree"]
    # The leaves and the bound are the tree's only: no method's object carries them.
    for method in METHODS:
        assert "leaves" not in walk_keys(payload[method]) and "bound" not in walk_keys(payload[method]), method


def test_l18_no_comparable_cell_prints_neither_block_emits_neither_key_and_the_api_refuses(synth_root: Path) -> None:
    """F23 restated and extended: the bound prints only when the tree ran."""
    # PF4 (PF4.7, section 8.5): a pair with no comparable condition is refused, exit 1, with one
    # error line naming the holes (one condition only in each run here) and a next line; nothing
    # reaches stdout, so no block is printed and no JSON key is emitted, in text and --json.
    for extra in ((), ("--json",)):
        code, out, err = run_cli(["--store", str(synth_root), "diff", "empty-a", "empty-b", "--event", "fail", *extra])
        assert code == 1 and out == "", (extra, out, err)
        lines = err.splitlines()
        errors = [line for line in lines if line.startswith("error: ")]
        assert len(errors) == 1 and re.search(r"\b1\b", errors[0]), lines
        assert all(line.startswith(("error: ", "  next:", "note: ")) for line in lines), lines
        assert any(line.startswith("  next:") for line in lines), lines
        assert heads(err, "cells:") == 0 and heads(err, "bound:") == 0 and heads(err, "omnibus: ") == 0, err
    store = Store(synth_root)
    a, b = store.read("empty-a", meta=False), store.read("empty-b", meta=False)
    multi = quiet_multi_diff(a, b, store.manifest("empty-a"), store.manifest("empty-b"), events=("fail",), method="fisher_bh")
    assert multi.n_tests == 0
    with pytest.raises(tree().TreeError):
        grown(a, b, multi, store.manifest("empty-a"), store.manifest("empty-b"), n_permutations=50, seed=GOLDEN_SEED, depth=3)


# ---------- L19: determinism, and what a seed may move ----------


def test_l19_the_same_inputs_give_identical_json_bytes_twice_in_one_process(pair: Any) -> None:
    a, b, ma, mb = pair
    multi = quiet_multi_diff(a, b, ma, mb, events=(EVENT,), method="fisher_bh")
    first = grown(a, b, multi, ma, mb, n_permutations=200, seed=7)
    second = grown(a, b, multi, ma, mb, n_permutations=200, seed=7)
    assert json_bytes(first.to_json()) == json_bytes(second.to_json())


def test_l19_a_different_seed_leaves_the_bound_and_moves_leaves_only_through_membership(lattice_trees: Any, gain_trees: Any) -> None:
    """Level 3 draws nothing: a different seed on the lattice by ``gain`` leaves ``bound`` byte-identical
    and can move ``leaves`` only by which groups reject; every family present under both seeds
    is byte-identical. A builder who seeds the leaf pass fails alone."""
    _, base = gain_trees["fisher_bh"]
    # PF4 re-freeze (PF4.45): grown at the value gain_trees grows at, where gain resolves.
    other = lattice_trees.tree((EVENT,), "fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED + 1, max_group_mde=ADMITTING_MAX_GROUP_MDE)
    one, two = base.to_json(), other.to_json()
    assert one["root"]["seed"] != two["root"]["seed"]
    assert json_bytes(one["bound"]) == json_bytes(two["bound"])
    assert without(one["leaves"], ("families", "n_families", "n_tests", "n_rejected")) == without(two["leaves"], ("families", "n_families", "n_tests", "n_rejected"))
    families_one = {family["label"]: family for family in one["leaves"]["families"]}
    families_two = {family["label"]: family for family in two["leaves"]["families"]}
    assert set(families_one) == set(one["fault_lines"]["rejected_groups"]) and set(families_two) == set(two["fault_lines"]["rejected_groups"])
    shared = set(families_one) & set(families_two)
    assert shared, (sorted(families_one), sorted(families_two))
    for label in shared:
        assert json_bytes(families_one[label]) == json_bytes(families_two[label]), label


# ---------- L20: nothing else moves ----------


def nested_keys(payload: Any) -> set[str]:
    """Every mapping key at any depth of a JSON payload."""
    if isinstance(payload, Mapping):
        return set(payload) | {k for v in payload.values() for k in nested_keys(v)}
    if isinstance(payload, list):
        return {k for v in payload for k in nested_keys(v)}
    return set()


def direction_word(n_lower: int, n_higher: int) -> str:
    """PF4.20's comparison word for an event of unknown kind when something moved."""
    return "mixed" if n_lower and n_higher else ("higher" if n_higher else "lower")


def mcnemar_reference(a: pd.DataFrame, b: pd.DataFrame, event: str) -> dict[str, float]:
    """PF4 (PF4.14): each cell's exact McNemar p from its matched pairs, by statsmodels' documented
    ``mcnemar(table, exact=True)`` with ``table = [[n11, n10], [n01, n00]]`` (rows: arm A with and
    without the event; columns: arm B); a cell with no discordant pair has p 1."""
    from statsmodels.stats.contingency_tables import mcnemar

    keys = ["config_hash", "replicate_index"]
    pairs = a[[*keys, "outcome"]].merge(b[[*keys, "outcome"]], on=keys, suffixes=("_a", "_b"))
    out: dict[str, float] = {}
    for cell_hash, group in pairs.groupby("config_hash"):
        ea = (group["outcome_a"] == event).to_numpy()
        eb = (group["outcome_b"] == event).to_numpy()
        table = [[int((ea & eb).sum()), int((ea & ~eb).sum())], [int((~ea & eb).sum()), int((~ea & ~eb).sum())]]
        discordant = table[0][1] + table[1][0]
        out[str(cell_hash)] = 1.0 if discordant == 0 else float(mcnemar(table, exact=True).pvalue)
    return out


#: PF4 re-freeze (PF4.22, PF4.48): limits are multiples of this grid step.
LIMIT_GRID_STEP = 1e-4


def is_null(value: Any) -> bool:
    """A null limit as JSON (None) or as the frame (NaN) carries it."""
    return value is None or (isinstance(value, float) and math.isnan(value))


@functools.cache
def reference_fisher_limits(events_a: int, n_a: int, n_b: int, level: float) -> tuple[float | None, float | None]:
    """PF4 re-freeze (PF4.23): the stats file's independent Fisher enumeration, rise then fall.
    Imported here, not at module level, so this file still collects where the stats file cannot."""
    from test_pf4_stats import _ref_fisher_limits

    return _ref_fisher_limits(events_a, n_a, n_b, level)


def reference_mde(events_a: int, n_a: int, n_b: int, level: float) -> float | None:
    """Section 8.10's ``mde`` rule over the reference's two limits: the larger of two numbers, the
    number beside a direction with no room, and null otherwise."""
    rise, fall = reference_fisher_limits(events_a, n_a, n_b, level)
    if rise is not None and fall is not None:
        return max(rise, fall)
    if rise is not None and events_a == 0:
        return rise
    if fall is not None and events_a == n_a:
        return fall
    return None


def assert_the_limits_follow_the_rule(cell: Mapping[str, Any], row: Mapping[str, Any], level: float, method: str) -> None:
    """PF4 re-freeze (PF4.22, PF4.23, PF4.27, section 8.10, Q54): the JSON carries the frame's limits;
    a baseline with the event in every run has no rise (``no room``) and its fall is computed; ``mde``
    follows section 8.10's rule, with a note when it is null, and a number is a positive grid value;
    under Fisher both limits are the stats file's reference at the lone-change level ``q / M``."""
    what = (method, cell["config_hash"])
    for key in ("mde", "mde_rise", "mde_fall"):
        assert is_null(cell[key]) == is_null(row[key]), (what, key)
        assert is_null(cell[key]) or cell[key] == row[key], (what, key)
    rise, fall = cell["mde_rise"], cell["mde_fall"]
    if cell["events_a"] == cell["n_a"]:
        assert is_null(rise) and cell["mde_rise_note"] == "no room", what
    if not is_null(rise) and not is_null(fall):
        want = max(rise, fall)
    elif not is_null(rise) and cell["mde_fall_note"] == "no room":
        want = rise
    elif not is_null(fall) and cell["mde_rise_note"] == "no room":
        want = fall
    else:
        want = None
    if want is None:
        assert is_null(cell["mde"]) and cell["mde_note"], (what, cell["mde"], cell["mde_note"])
    else:
        assert cell["mde"] == want and cell["mde"] >= LIMIT_GRID_STEP - 1e-12, (what, cell["mde"], want)
    if method == "fisher_bh":
        assert abs(cell["mde_level"] - level) <= 1e-15, what
        for got, ref in zip((rise, fall), reference_fisher_limits(cell["events_a"], cell["n_a"], cell["n_b"], level), strict=True):
            assert (ref is None and is_null(got)) or (ref is not None and not is_null(got) and abs(got - ref) <= LIMIT_GRID_STEP + 1e-12), (what, got, ref)


def lattice_worst_unchanged(multi: Any) -> tuple[set[str], int]:
    """PF4 re-freeze (PF4.22, PF4.23): the lattice's worst-powered unchanged condition under Fisher,
    from the stats file's reference: every unchanged condition whose recomputed ``mde`` is the
    largest (they may tie), written as the report writes a condition, and that limit in whole points."""
    level = multi.q / multi.n_tests
    limits = {}
    for row in multi.by_event[EVENT].cells.to_dict(orient="records"):
        if row["direction"] != "unchanged":
            continue
        value = reference_mde(int(row["events_a"]), int(row["n_a"]), int(row["n_b"]), level)
        if value is not None:
            limits[f"{X}={row['config'][X]:g}, {Y}={row['config'][Y]:g}"] = value
    worst = max(limits.values())
    return {where for where, value in limits.items() if abs(value - worst) <= LIMIT_GRID_STEP + 1e-12}, round(100 * worst)


def assert_lattice_multi_json_carries_the_facts(multi: Any, method: str, a: pd.DataFrame, b: pd.DataFrame) -> None:
    """PF4: the facts the ``to_json()`` digest guarded, with no digest over bytes PF4 changes.

    Every cell's counts, rates and delta equal the frame's and the design's (``lattice.counts``); p
    and q equal the frame's and the method's reference (``lattice.fisher`` / ``lattice.mcnemar``
    exactly, ``lattice.logrank`` to 1e-12 relative), McNemar's p also statsmodels' exact test and its BH q,
    and the q column is BH over the p column. A condition whose baseline had the event in every run
    has no rise and its fall computed, and every limit follows section 8.10's rule at ``q / M``,
    Fisher's recomputed from the stats file's reference (PF4.22, PF4.27). Each cell's JSON verdict
    is its direction (tripped has no kind, PF4.20) and the reference's; a cell moves exactly when it
    is rejected, in the direction of its delta except under log-rank (PF4.13); and the counts are
    the reference's (``LATTICE_DIRECTION_COUNTS``)."""
    from statsmodels.stats.multitest import multipletests

    payload = json.loads(json.dumps(multi.to_json(), sort_keys=True))
    assert (payload["method"], payload["n_tests"], payload["events"]) == (method, lattice.CELLS, [EVENT]), method
    event = payload["by_event"][EVENT]
    reference = LATTICE_REFERENCES[method](EVENT)
    n_lower, n_higher = LATTICE_DIRECTION_COUNTS[method]
    assert lattice.directions(reference) == (n_lower, n_higher), (method, lattice.directions(reference))
    assert (event["kind"], event["n_safer"], event["n_worse"]) == (None, None, None), method
    assert (event["n_lower"], event["n_higher"], event["n_unchanged"]) == (n_lower, n_higher, lattice.CELLS - n_lower - n_higher), method
    design = {r["config_hash"]: r for r in lattice.counts(EVENT)}
    rows = multi.by_event[EVENT].cells.to_dict(orient="records")
    assert [c["config_hash"] for c in event["cells"]] == [r["config_hash"] for r in rows], method
    assert set(design) == set(reference) == {r["config_hash"] for r in rows}, method
    reference_p = mcnemar_reference(a, b, EVENT) if method == "mcnemar_bh" else {}
    for cell, row in zip(event["cells"], rows, strict=True):
        h = cell["config_hash"]
        ref, counted = reference[h], design[h]
        assert cell["config"] == row["config"] == counted["config"], (method, h)
        expected = {
            "n_a": counted["n_a"], "n_b": counted["n_b"], "events_a": counted["events_a"], "events_b": counted["events_b"],
            "rate_a": counted["events_a"] / counted["n_a"], "rate_b": counted["events_b"] / counted["n_b"], "delta": ref["delta"],
        }
        for key in ARM_KEYS:
            assert cell[key] == row[key] == expected[key], (method, h, key)
        # The sign of a zero change is the reference's (the digest's ``.17g`` form kept it).
        assert repr(float(cell["delta"])) == repr(float(row["delta"])) == repr(float(ref["delta"])), (method, h, cell["delta"])
        assert (cell["p"], cell["q"]) == (row["p"], row["q"]), (method, h)
        if method == "logrank_bh":
            assert cell["p"] == pytest.approx(ref["p"], rel=1e-12, abs=0) and cell["q"] == pytest.approx(ref["q"], rel=1e-12, abs=0), (h, cell["p"], cell["q"])
        else:
            assert (cell["p"], cell["q"]) == (ref["p"], ref["q"]), (method, h)
        if method == "mcnemar_bh":
            assert abs(cell["p"] - reference_p[h]) <= 1e-12, (h, cell["p"])
            assert cell["pairs"] == counted["n_a"] == counted["n_b"], h
        # PF4 re-freeze (PF4.22, PF4.23, PF4.27): each limit is the exact test's at q / M both ways,
        # a 100% baseline has its fall computed, and Fisher's are recomputed from the stats file's reference.
        assert_the_limits_follow_the_rule(cell, row, multi.q / multi.n_tests, method)
        rejected = cell["q"] < multi.q
        assert cell["verdict"] == cell["direction"] == row["direction"] == ref["direction"], (method, h)
        assert (cell["direction"] != "unchanged") == rejected, (method, h)
        if rejected and method != "logrank_bh":
            assert cell["direction"] == ("higher" if cell["delta"] > 0 else "lower"), (method, h)
    directions = [c["direction"] for c in event["cells"]]
    assert (directions.count("lower"), directions.count("higher")) == (n_lower, n_higher), method
    assert np.array_equal(np.array([r["q"] for r in rows]), lattice.bh([r["p"] for r in rows])), method
    if method == "mcnemar_bh":
        bh = multipletests([reference_p[r["config_hash"]] for r in rows], method="fdr_bh")[1]
        assert max(abs(r["q"] - float(x)) for r, x in zip(rows, bh, strict=True)) <= 1e-12


def interval_texts() -> tuple[str, str, str]:
    """The interval level and alpha* over the flat Fisher family, recomputed: alpha* is
    ``q x R / M`` over the reference's rejections, printed under ``:g``; the level is ``1 -
    alpha*`` under ``:g`` and to three decimals."""
    n_lower, n_higher = lattice.directions(lattice.fisher(EVENT))
    alpha = Q * (n_lower + n_higher) / lattice.CELLS
    return f"{100 * (1 - alpha):g}", f"{alpha:g}", f"{100 * (1 - alpha):.3f}"


def assert_e14_builder_carries_the_result(multi: Any, report: Any, receipt: Any) -> None:
    """PF4: the facts the E14 digests guarded in the tree-less builder's report.md, receipt and
    heatmap: each file's one version entry; the headline counts in direction words (tripped has no
    kind, PF4.20) at the reference's 22 lower / 0 higher; the worst-powered unchanged condition and
    its limit, recomputed; the interval level and alpha*, recomputed; no layered block (the root
    reaches no other verb); and every row of the cell table is a cell of the diff with its counts,
    rates, p, q and direction."""
    md, html, svg = report.to_markdown(), receipt.to_html(), report.to_svg()
    as_0_0_1_wrote_it(md)
    as_0_0_1_wrote_it(html)
    tripped = multi.by_event[EVENT]
    cells = tripped.cells
    n_lower, n_higher = LATTICE_DIRECTION_COUNTS["fisher_bh"]
    assert (tripped.n_lower, tripped.n_higher) == (n_lower, n_higher) == lattice.directions(lattice.fisher(EVENT))
    headline = f"{EVENT}: {n_lower} lower, {n_higher} higher"
    md_lines = md.splitlines()
    assert headline in md_lines and f"## {headline}" in md_lines, md_lines[:12]
    assert f"<h2>{headline}</h2>" in html
    assert f">{headline}</text>" in svg
    # PF4 re-freeze (PF4.22, PF4.23): the worst-powered unchanged condition and its limit are
    # recomputed from the stats file's reference (if they tie, the line names one of them).
    wheres, points = lattice_worst_unchanged(multi)
    assert round(100 * tripped.max_mde_unchanged) == points
    for name, text in (("report.md", md), ("receipt.html", html), ("heatmap.svg", svg)):
        honesty = [line for line in text.splitlines() if "Worst-powered unchanged cell" in line]
        assert honesty and any(f"({where}," in honesty[0] for where in wheres) and f"{points}pp" in honesty[0], (name, honesty)
        assert "safer" not in text and "worse" not in text, name
    # PF4 re-freeze (PF4.42): the verdict's section adds its own "intervals: " line, the interval on
    # the change at the same level; the line that names alpha* is the one this pinned.
    level, alpha, on_change_level = interval_texts()
    assert (level, alpha, on_change_level) == (LATTICE_INTERVAL_LEVEL_TEXT, LATTICE_ALPHA_STAR_TEXT, LATTICE_ON_CHANGE_LEVEL_TEXT)
    (intervals,) = [line for line in md_lines if line.startswith("intervals: ") and "alpha*" in line]
    assert f"{level}%" in intervals and f"alpha* = {alpha}" in intervals, intervals
    (on_change,) = [line for line in md_lines if line.startswith("intervals: ") and "alpha*" not in line]
    assert f"{on_change_level}%" in on_change and "miettinen-nurminen" in on_change.lower().replace("–", "-"), on_change
    for name, text in (("report.md", md), ("receipt.html", html)):
        assert "omnibus" not in text.lower() and "fault lines" not in text.lower(), name
    first = next(i for i, line in enumerate(md_lines) if line.startswith(f"| {X} |"))
    table = []
    for line in md_lines[first:]:
        if not line.startswith("|"):
            break
        table.append([c.strip() for c in line.strip("|").split("|")])
    header, rows = table[0], [row for row in table[2:]]
    assert header[:9] == [X, Y, "n (a/b)", "rate_a (pp)", "rate_b (pp)", "delta (pp)", "p", "q", "verdict"], header
    assert rows
    records = cells.to_dict(orient="records")
    for values in rows:
        row = dict(zip(header, values, strict=True))
        (cell,) = [c for c in records if c["config"] == {X: float(row[X]), Y: float(row[Y])}]
        assert row["n (a/b)"] == f"{cell['n_a']}/{cell['n_b']}", row
        for column, key in (("rate_a (pp)", "rate_a"), ("rate_b (pp)", "rate_b"), ("delta (pp)", "delta")):
            assert abs(float(row[column]) - 100 * cell[key]) <= 0.05 + 1e-9, (row, column)
        for column in ("p", "q"):
            decimals = len(row[column].partition(".")[2])
            assert abs(float(row[column]) - cell[column]) <= 0.5 * 10.0**-decimals + 1e-12, (row, column)
        assert row["verdict"] == cell["direction"], row


def assert_lattice_page_carries_the_diff(structure: Mapping[str, Any], multi: Any, ma: RunManifest, mb: RunManifest, rows: tuple[int, int]) -> None:
    """PF4: the facts the serve structure digest guarded, on the page minus its tree: both arms
    from their manifests (no store path, platform or import path, PF4.11); the diff's parameters;
    one panel whose counts are the reference's and whose 72 cells carry the diff's numbers with
    their direction (PF4.20) and limit (PF4.15); the worst-powered unchanged condition; the
    Summary's comparison word, decided by PF4.20 from those counts; the headline; and no key of the
    layered tree outside ``tree``."""
    assert "store_root" not in structure["pair"]
    for arm, manifest, n_rows in (("a", ma, rows[0]), ("b", mb, rows[1])):
        side = structure["pair"][arm]
        assert (side["run_id"], side["target_id"], side["run_salt"], side["t_unit"]) == (
            manifest.run_id, manifest.target_id, manifest.run_salt, manifest.t_unit,
        ), arm
        assert side["axis_types"] == dict(manifest.axis_types) and side["rows_stored"] == n_rows == lattice.ROWS, arm
        assert not {"platform", "import_path"} & set(side["environment"]), arm
    diff = structure["diff"]
    assert (diff["method"], diff["n_tests"], diff["q"], diff["horizon"], diff["events"]) == (multi.method, multi.n_tests, multi.q, multi.horizon, [EVENT])
    (panel,) = structure["panels"]
    n_lower, n_higher = LATTICE_DIRECTION_COUNTS[multi.method]
    assert (panel["event"], panel["kind"], panel["n_safer"], panel["n_worse"]) == (EVENT, None, None, None)
    assert (panel["n_lower"], panel["n_higher"], panel["n_unchanged"]) == (n_lower, n_higher, multi.n_tests - n_lower - n_higher)
    by_hash = {r["config_hash"]: r for r in multi.by_event[EVENT].cells.to_dict(orient="records")}
    assert len(panel["cells"]) == len(by_hash) == multi.n_tests == lattice.CELLS
    assert {c["config_hash"] for c in panel["cells"]} == set(by_hash)
    for cell in panel["cells"]:
        row = by_hash[cell["config_hash"]]
        for key in ("n_a", "n_b", "events_a", "events_b", "rate_a", "rate_b", "delta", "p", "q"):
            assert cell[key] == row[key], (cell["config_hash"], key)
        assert cell["verdict"] == cell["direction"] == row["direction"], cell["config_hash"]
        # PF4 re-freeze (PF4.27, Q54): a 100% baseline's limit is its fall, and a null limit is
        # null on the page with its note, as in the diff.
        assert is_null(cell["mde"]) == is_null(row["mde"]), cell["config_hash"]
        assert (is_null(row["mde"]) and cell["mde_note"]) or cell["mde"] == row["mde"], cell["config_hash"]
    # PF4 re-freeze (PF4.22, PF4.23): the worst-powered unchanged condition, recomputed.
    wheres, points = lattice_worst_unchanged(multi)
    assert panel["mde_unchanged"]["where"] in wheres and round(100 * panel["mde_unchanged"]["value"]) == points
    assert structure["summary"]["verdict"] == direction_word(n_lower, n_higher)
    assert structure["headline"] == multi.headline()
    assert not set(TREE_ONLY_KEYS) & nested_keys({k: v for k, v in structure.items() if k != "tree"})


@pytest.mark.parametrize("method", METHODS)
def test_l20_multi_diff_on_the_lattice_is_byte_identical_to_the_bare_tree(pair: Any, lattice_trees: Any, method: str) -> None:
    a, b, _, _ = pair
    multi = lattice_trees.multi((EVENT,), method)
    # PF4 (PF4.3, PF4.13 to PF4.15, PF4.20): the digest is replaced by the facts it guarded, each
    # checked against a value known outside the build (the design and the lattice's references).
    assert_lattice_multi_json_carries_the_facts(multi, method, a, b)


#: ``pair.coverage``'s columns, in order: what its records carry.
COVERAGE_COLUMNS = ["config_hash", "config", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b", "comparable", "cause"]


def column_text(result: Any, column: str) -> str:
    """A column of a comparison in the canonical form S24's column digests hashed: per event in
    ``result.events`` order, ``event:`` and the column's values in row order under ``.17g``, comma
    joined, the events joined by ``|``. Compared as text, never hashed: ``.17g`` round-trips a float
    and keeps the sign of a zero, so equal text is equal events, order, length, bits and signs."""
    return "|".join(f"{e}:" + ",".join(f"{v:.17g}" for v in result.by_event[e].cells[column]) for e in result.events)


def reference_column_text(values: Mapping[str, Sequence[float]]) -> str:
    """``column_text``'s form written from reference values, events in the mapping's order."""
    return "|".join(f"{e}:" + ",".join(f"{v:.17g}" for v in column) for e, column in values.items())


def assert_s24_columns_are_the_references(pair: Any, tripped_logrank: Any) -> None:
    """The facts S24's three column digests and its coverage digest guarded, in the forms they hashed.
    Over both outcomes under Fisher: the events are ``(tripped, held)`` and the family is 144; every
    event's rows are the 72 conditions in sorted-hash order; the ``p`` and ``delta`` columns are
    ``lattice.fisher``'s as ``column_text`` (bits and the sign of every zero), ``held``'s delta
    ``tripped``'s negated numerically; the ``q`` column is ``lattice.bh`` over the one family of 144
    ``p``, as text. Under log-rank on ``tripped``: one event, 72 tests, sorted-hash rows, the ``q``
    column ``lattice.bh`` over its ``p`` as text and ``lattice.logrank``'s to 1e-12 relative, with the
    reference's directions. The coverage, serialised as its digest serialised it
    (``to_json(orient="records")``), is the design's 72 conditions, each 32 rows a run, all comparable."""
    import numpy as np

    both = (lattice.EVENT, lattice.OTHER)
    design = {r["config_hash"]: r for r in lattice.counts(lattice.EVENT)}
    hashes = sorted(design)
    assert tuple(pair.events) == both and pair.n_tests == 2 * lattice.CELLS, (pair.events, pair.n_tests)
    references = {event: lattice.fisher(event) for event in both}
    for event in both:
        assert list(pair.by_event[event].cells["config_hash"].astype(str)) == hashes, event
    for column in ("p", "delta"):
        assert column_text(pair, column) == reference_column_text({e: [references[e][h][column] for h in hashes] for e in both}), column
    assert np.array_equal(pair.by_event[lattice.OTHER].cells["delta"].to_numpy(), -pair.by_event[lattice.EVENT].cells["delta"].to_numpy())
    qs = lattice.bh([references[e][h]["p"] for e in both for h in hashes])
    assert column_text(pair, "q") == reference_column_text({e: qs[i * lattice.CELLS : (i + 1) * lattice.CELLS] for i, e in enumerate(both)})
    reference = lattice.logrank(lattice.EVENT)
    cells = tripped_logrank.by_event[lattice.EVENT].cells
    assert tuple(tripped_logrank.events) == (lattice.EVENT,) and tripped_logrank.n_tests == lattice.CELLS
    assert list(cells["config_hash"].astype(str)) == hashes
    assert column_text(tripped_logrank, "q") == reference_column_text({lattice.EVENT: lattice.bh(cells["p"].to_numpy())})
    assert cells["q"].to_numpy() == pytest.approx(np.array([reference[h]["q"] for h in hashes]), rel=1e-12, abs=0)
    assert list(cells["direction"]) == [reference[h]["direction"] for h in hashes]
    assert lattice.directions(reference) == (27, 12)
    assert list(pair.coverage.columns) == COVERAGE_COLUMNS
    expected = [
        {"config_hash": h, "config": design[h]["config"], "rows_a": lattice.N, "rows_b": lattice.N, "no_outcome_a": 0,
         "no_outcome_b": 0, "comparable": True, "cause": None}
        for h in hashes
    ]
    assert pair.coverage.to_json(orient="records") == json.dumps(expected, separators=(",", ":"))


def test_l20_the_s24_columns_and_the_coverage_are_the_references(lattice_trees: Any) -> None:
    """The facts S24's three column digests and its coverage digest guarded, in the forms they
    hashed, against the lattice's references (``assert_s24_columns_are_the_references``)."""
    assert_s24_columns_are_the_references(lattice_trees.multi((EVENT, lattice.OTHER), "fisher_bh"), lattice_trees.multi((EVENT,), "logrank_bh"))


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


def e14_builder(lattice_trees: Any) -> tuple[Any, Any, Any]:
    """The E14 argv's ``multi`` and spec, rendered by the M7 builder with no tree, the way
    ``_report_pair`` builds them: the multi, the dark-theme report and the light-theme receipt."""
    _, _, ma, mb = lattice_trees.frames()
    multi = lattice_trees.multi((EVENT,), "fisher_bh")
    title = f"{LATTICE_A} vs {LATTICE_B}: {EVENT}"
    report = build_multi_report(
        multi, ReportSpec(title=title, x_axis=X, y_axis=Y), manifests=(ma, mb)
    )
    receipt = build_multi_report(
        multi, ReportSpec(title=title, x_axis=X, y_axis=Y, theme="light"),
        manifests=(ma, mb),
    )
    return multi, report, receipt


def assert_cli_heatmap_is_the_builders_under_rule_10(cli_svg: str, builder_svg: str, cells: pd.DataFrame) -> None:
    """The command line's ``heatmap.svg`` against the builder's, whose bytes keep the frozen digest.

    Rule 10 (spec section 5.4) reformats only the text in the file, so every element and attribute
    is the builder's. Each cell's label is its delta to three decimals, read from ``cells``; a text
    the builder prints as a percentage-point number is that number as a fraction; every other text
    that changed keeps its ``key=value`` facts and its counts; and the notes the builder writes in
    percentage points carry the worst-powered MDEs to three decimals.
    """
    def bare(svg: str) -> str:
        return re.sub(r">[^<]*<", "><", svg)

    assert bare(cli_svg) == bare(builder_svg)
    ids = re.findall(r'data-cell="([0-9a-f]+)"', cli_svg)
    label_group = cli_svg.split('<g fill="#E6E6E6" font-size="9" text-anchor="middle">', 1)[1].split("</g>", 1)[0]
    labels = re.findall(r">([^<]*)</text>", label_group)
    delta = dict(zip(cells["config_hash"], cells["delta"]))
    assert len(ids) == len(labels) == len(delta), (len(ids), len(labels), len(delta))
    for short, label in zip(ids, labels):
        (full,) = [h for h in delta if h.startswith(short)]
        assert label == f"{delta[full]:.3f}", (short, label, delta[full])
    number = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")
    texts = list(zip(re.findall(r">([^<]*)</text>", builder_svg), re.findall(r">([^<]*)</text>", cli_svg)))
    for old, new in texts:
        if old == new:
            continue
        if number.fullmatch(old):
            assert number.fullmatch(new) and abs(float(new) - float(old) / 100) <= 1e-3, (old, new)
            continue
        for fact in re.findall(r"\w+=[^\s,;)]+", old):
            assert fact in new, (fact, new)
        for count in re.findall(r"(?<![\d.])\d+(?![\d.%]|pp)", old):
            assert f"{int(count):,}" in new, (count, new)
    notes = [new for old, new in texts if re.search(r"\d+pp", old)]
    assert notes, texts
    for mde in (cells["mde"].max(), cells.loc[cells["verdict"] == "unchanged", "mde"].max()):
        assert any(f"{mde:.3f}" in note for note in notes), (mde, notes)


def test_l20_the_lattice_report_carries_the_facts_s21s_three_digests_guarded(lattice_trees: Any, tmp_path: Path) -> None:
    """Narrowed for S28 (draft ADR-074, spec S28 section 3.8): ``report`` on a pair now renders the
    layered report into ``report.md`` and ``receipt.html``, so those two files through the CLI
    are S28's to pin. The surface S21 owned is the tree-less M7 builder, so the markdown and HTML
    checks move to ``build_multi_report(multi, spec, manifests=...)`` with no tree; ``heatmap.svg``
    never changes (S28 section 3.3) and stays checked through the CLI. Narrowed, not deleted.

    Moved for rule 10 (spec section 5.4): the command line now prints the heatmap's text as
    fractions, so the file the command line writes is checked against the builder's heatmap fact
    by fact. On the lattice the three digests are the facts they guarded (PF4)."""
    out = tmp_path / "report"
    code, text, _ = run_cli(["--store", str(LATTICE_ROOT), *E14_ARGV, "--out", str(out)])
    assert code == 0, text
    # PF4 (PF4.3, PF4.15, PF4.20): the three digests are replaced by the facts they guarded.
    multi, report, receipt = e14_builder(lattice_trees)
    assert_e14_builder_carries_the_result(multi, report, receipt)
    # The command line's heatmap is the builder's with its text under rule 10 (spec section 5.4),
    # checked by its facts rather than a new digest.
    assert_cli_heatmap_is_the_builders_under_rule_10(
        (out / "heatmap.svg").read_text(encoding="utf-8"), report.to_svg(), multi.by_event[EVENT].cells
    )


def test_l20_check_and_serve_on_the_lattice_print_the_same_bytes_and_structure(lattice_trees: Any) -> None:
    code, out, err = run_cli(["--store", str(LATTICE_ROOT), *CHECK_ARGV])
    # A shared salt now adds one note line on stderr (spec section 5.4).
    assert code == CHECK_EXIT and without_notes(err) == "", (code, err)
    # The verdict line now comes first, so the stdout digest is replaced by the facts it guarded
    # (spec sections 5.3 and 14): passed, the gated event, the flat family's counts and its size.
    multi = lattice_trees.multi((EVENT,), "fisher_bh")
    verdicts = multi.by_event[EVENT].cells["verdict"]
    first = out.splitlines()[0]
    assert first.startswith("passed  ") and EVENT in first, out
    # PF4 (PF4.20): tripped has no kind, so the counts read in direction words; the lattice's 22
    # and 0 are the Fisher reference's (LATTICE_DIRECTION_COUNTS).
    # PF4 re-freeze (PF4.20, no split between the library and the screen): the library's verdict
    # column holds the direction words too, where it held safer and worse.
    n_lower, n_higher = int((verdicts == "lower").sum()), int((verdicts == "higher").sum())
    assert (n_lower, n_higher) == LATTICE_DIRECTION_COUNTS["fisher_bh"] == lattice.directions(lattice.fisher(EVENT))
    assert f"{n_lower:,} lower, {n_higher:,} higher" in out, out
    assert f"{multi.n_tests:,} tests" in out, out
    # PF4 re-freeze (PF4.34, PF4.40, reading R34): check's block names the comparison's own word on
    # its comparison line, read from Holm's rows.
    holm = multi.to_json()["by_event"][EVENT]
    (comparison,) = [line for line in out.splitlines() if line.startswith("  comparison  ")]
    assert comparison.split()[1] == direction_word(holm["n_holm_lower"], holm["n_holm_higher"]), comparison
    code, out, err = run_cli(["--store", str(LATTICE_ROOT), *SERVE_ARGV])
    # A shared salt now adds one note line on stderr (spec section 5.4).
    assert code == 0 and without_notes(err) == "", err
    # serve --json now leads with a verdict and a sentence beside the structure (spec section 5.6).
    # PF3 (spec section 4.4, PF3.6b; rule R3): serve --json now names the method at the top level after the
    # sentence; dropped beside the verdict and the sentence.
    structure = {k: v for k, v in json.loads(out).items() if k not in ("verdict", "sentence", "method", "method_chosen")}
    # PF4 (PF4.11, section 8.5): the page no longer carries the store path at all.
    assert "store_root" not in structure["pair"]
    # PF2 (spec section 4.3): run_name beside each arm's run_id and the title by name are asserted,
    # then put back as before names.
    structure = structure_as_ids_named_it(structure, EVENT)
    # PF0's version-field check still holds on the page.
    structure_as_0_0_1_wrote_it(structure)
    # PF4 (PF4.3, PF4.11, PF4.17, PF4.20): the digest is replaced by the facts it guarded; the tree
    # still travels under its own key only.
    assert "tree" in structure
    ga, gb, gma, gmb = lattice_trees.frames()
    assert_lattice_page_carries_the_diff(structure, multi, gma, gmb, (len(ga), len(gb)))


def lattice_omnibus_facts(method: str, scheme: str) -> dict[str, Any]:
    """F28's omnibus payload minus its p-driven keys, written from the design and never from Prove:
    one unit per condition in sorted-hash order with its counts and ``events_b / n_b - events_a /
    n_a``; the location and dispersion the mean and root mean square of those deltas; a condition
    informative under ``arm_label`` when its pooled outcomes are not all one; the draw's knobs."""
    rows = sorted(lattice.counts(EVENT), key=lambda r: r["config_hash"])
    deltas = np.array([[r["events_b"] / r["n_b"] - r["events_a"] / r["n_a"] + 0.0] for r in rows])
    informative = sum(0 < r["events_a"] + r["events_b"] < r["n_a"] + r["n_b"] for r in rows)
    return {
        "events": [EVENT], "method": method, "scheme": scheme, "q": Q, "n_cells": lattice.CELLS,
        "n_informative_cells": informative, "n_uninformative_cells": lattice.CELLS - informative, "n_discordant": None,
        "n_permutations": GOLDEN_PERMUTATIONS, "p_floor": 1 / (GOLDEN_PERMUTATIONS + 1), "seed": GOLDEN_SEED,
        "units": [
            {"event": EVENT, "config_hash": r["config_hash"], "config": r["config"], "n_a": r["n_a"], "n_b": r["n_b"],
             "events_a": r["events_a"], "events_b": r["events_b"], "delta": float(d)}
            for r, (d,) in zip(rows, deltas, strict=True)
        ],
        "location": {EVENT: float(deltas.sum(axis=0)[0] / len(rows))},
        "dispersion": {EVENT: float(np.sqrt((deltas * deltas).sum(axis=0)[0] / len(rows)))},
    }


def test_l20_omnibus_on_the_lattice_minus_the_p_driven_keys_is_the_payload_written_from_the_design(pair: Any, gain_trees: Any) -> None:
    """F28's digest over the study pair's omnibus is replaced by the facts it guarded: the
    standalone omnibus and the tree's root, minus the p-driven keys, serialised as the digest
    serialised them (``json.dumps(sort_keys=True)``), are each exactly the payload written from the
    design (``lattice_omnibus_facts``), with 35 informative conditions and 37 not."""
    a, b, _, _ = pair
    multi, result = gain_trees["fisher_bh"]
    p_driven = ("p_location", "p_dispersion", "p_omnibus", "rejects", "headline")
    standalone = tree().omnibus(a, b, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED).to_json()
    expected = lattice_omnibus_facts("fisher_bh", "arm_label")
    assert (expected["n_informative_cells"], expected["n_uninformative_cells"]) == (35, 37)
    assert json_bytes(without(standalone, p_driven)) == json_bytes(expected)
    assert json_bytes(without(result.root.to_json(), p_driven)) == json_bytes(expected)


def test_l20_diff_py_and_the_two_frozen_oracles_are_byte_untouched() -> None:
    """``git diff --exit-code tests/`` and ``git diff --exit-code cd5f177 -- src/proofload/diff.py``
    are Session B's acceptance; the same facts as digests, which a scratch copy without
    ``.git`` can check (module docstring)."""
    # PF0 (Q4): the diff.py digest is no longer asserted; the rename changes diff.py.
    for relative, digest in FROZEN_ORACLE_SHA256.items():
        assert hashlib.sha256(code_of((REPO / relative).read_text(encoding="utf-8")).encode("utf-8")).hexdigest() == digest, relative


def test_l20_omnibus_and_resolve_grouping_keep_their_signatures_and_tree_gains_only_depth() -> None:
    t = tree()
    assert str(inspect.signature(t.omnibus)) == OMNIBUS_SIGNATURE
    assert str(inspect.signature(t.resolve_grouping)) == RESOLVE_GROUPING_SIGNATURE
    assert tuple((p.name, p.kind.name, p.default) for p in inspect.signature(t.tree).parameters.values()) == TREE_PARAMETERS


# ---------- L21: a moved group with nothing nameable inside it ----------


def test_l21_the_axes_pair_holds_a_moved_group_with_nothing_nameable_inside_it(axes_trees: Any, synth_root: Path) -> None:
    """Spec section 0.1's motivating case, committed as the axes pair: ``temp = 0.0`` rejects under both schemes, its
    family of 164 rejects nothing (min leaf p at least 0.46, recomputed from ``cells``), the
    family is present with its zero, and ``temp = 0.7`` has no family. Through the CLI under
    both methods the family line reads ``0 rejected``. A builder who drops an empty family, or
    prints the group as rejected on the cells block without its zero, fails alone."""
    for method, (multi, result) in axes_trees.items():
        leaves = result.leaves
        assert result.fault_lines.rejected_groups == ("0.0",) and leaves.tested is True and leaves.n_families == 1, (method, leaves.n_families)
        family = leaves.families[0]
        assert (family.label, family.n_tests, family.n_rejected, family.rejected) == ("0.0", N_TASKS, 0, ()), (method, family.label, family.n_tests, family.n_rejected)
        assert family_rows(multi, result, "0.0")["p"].min() >= AXES_MIN_LEAF_P, method
        assert not any(family.label == "0.7" for family in leaves.families), method
    for method in TWO_SCHEMES:
        code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--method", method])
        # A shared salt now adds one note line on stderr (spec section 5.4).
        assert code == 0 and without_notes(err) == "", (method, out, err)
        lines = family_lines(cells_block(out))
        assert len(lines) == 1 and "0.0" in lines[0] and "rejected" in lines[0], (method, lines)
        tokens = numeric_tokens(lines[0])
        # Counts print with separators under rule 10 (spec section 5.4).
        assert count(N_TASKS) in tokens and count(0) in tokens, (method, lines[0])
        assert leaf_lines(cells_block(out)) == [], (method, cells_block(out))


# ---------- L22: the family is cells x events ----------


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_l22_the_family_is_cells_times_events_on_the_multi_event_pair(multi_event: dict[str, Any], method: str) -> None:
    """``t0``'s family has ``n_tests == 2 x 2``: the two ``fail`` rows reject, the two ``crash``
    rows sit at p 1 with ``events_a == events_b == 0`` and do not, ``rejected`` carries both
    ``(config_hash, "fail")`` pairs in row order, and ``Leaves.n_tests`` counts events. The lattice has
    one event and cannot show ``K > 1``; this pair can. ``crash`` occurs in neither arm of
    either ``t0`` cell (asserted from the frames)."""
    multi, result = multi_event["trees"][method]
    grouping, leaves = result.grouping, result.leaves
    assert (grouping.key, grouping.n_groups, result.root.rejects, result.fault_lines.rejected_groups) == ("task", ME_TASKS, True, ("t0",)), (method, grouping.key, result.fault_lines.rejected_groups)
    assert tuple(result.root.events) == ME_EVENTS and leaves.n_families == 1
    family = leaves.families[0]
    hashes = sorted(grouping.groups["t0"])
    assert len(hashes) == 2 and family.n_tests == leaves.n_tests == 2 * 2 == len(family.cells), (method, family.n_tests)
    assert [(leaf.config_hash, leaf.event) for leaf in family.cells] == [(h, e) for h in hashes for e in ME_EVENTS]
    for leaf in family.cells:
        if leaf.event == "fail":
            assert leaf.rejects is True and leaf.q_within < Q, (method, leaf)
        else:
            assert leaf.rejects is False and leaf.p == 1.0 and (leaf.events_a, leaf.events_b) == (0, 0), (method, leaf)
    assert family.rejected == tuple((h, "fail") for h in hashes) and family.n_rejected == leaves.n_rejected == 2
    for frame in (multi_event["a"], multi_event["b"]):
        assert not (frame["config_hash"].astype(str).isin(hashes) & (frame["outcome"] == "crash")).any(), method


# ---------- L23: order ----------


def test_l23_families_and_cells_are_in_row_order_on_every_fixture(every_tree: Any) -> None:
    """Families in ``rejected_groups`` order; within a family ``cells`` in ``sorted(config_hash)``
    order with events in ``root.events`` order under each hash; never by result."""
    for name, _, result in every_tree:
        if result.fault_lines.tested:
            assert tuple(family.label for family in result.leaves.families) == result.fault_lines.rejected_groups, name
        for family in result.leaves.families:
            expected = [(h, e) for h in sorted(result.grouping.groups[family.label]) for e in result.root.events]
            assert [(leaf.config_hash, leaf.event) for leaf in family.cells] == expected, (name, family.label)


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_l23_lattice_load_20_has_eleven_rejected_leaves_whose_q_within_is_not_sorted_and_the_block_follows_the_json(load_trees: Any, method: str) -> None:
    """A builder who sorts by ``q_within`` or ``delta`` fails alone: the family's eleven
    rejected leaves are in hash order, their ``q_within`` sequence is not sorted, and the block's
    leaf lines under that family follow the JSON order."""
    _, result = load_trees[method]
    family = next(f for f in result.leaves.families if f.label == LATTICE_LOAD_UNSORTED_FAMILY)
    rejected = [leaf for leaf in family.cells if leaf.rejects]
    sequence = [leaf.q_within for leaf in rejected]
    assert len(rejected) == LATTICE_LOAD_UNSORTED_REJECTED and sequence != sorted(sequence) and sequence != sorted(sequence, reverse=True), sequence
    code, out, err = run_cli(["--store", str(LATTICE_ROOT), "diff", LATTICE_A, LATTICE_B, "--event", EVENT, "--method", method, "--by", Y])
    # A shared salt now adds one note line on stderr (spec section 5.4).
    assert code == 0 and without_notes(err) == "", (out, err)
    block = cells_block(out)
    families = [line for line in block[1:] if line.startswith("  ") and not line.startswith("    ")]
    start = block.index(next(line for line in families if f"={LATTICE_LOAD_UNSORTED_FAMILY}" in line))
    following = block[start + 1 :]
    end = next((i for i, line in enumerate(following) if not line.startswith("    ")), len(following))
    # delta and MDE print to three decimals and q under rule 10 (spec section 5.4), not ``:g``.
    # PF4 re-freeze (PF4.27): a leaf whose limit is null prints no number for it.
    printed = [(fraction(leaf.delta), rule_10_p(leaf.q_within), *(() if is_null(leaf.mde) else (fraction(leaf.mde),))) for leaf in rejected]
    assert all("nan" not in numeric_tokens(line) for line in following[:end]), following[:end]
    seen = [tuple(token for token in numeric_tokens(line) if token in {t for triple in printed for t in triple}) for line in following[:end]]
    assert len(seen) == len(printed), (len(seen), len(printed))
    for triple, tokens in zip(printed, seen, strict=True):
        assert set(triple) <= set(tokens), (triple, tokens)


def test_l20_the_exclusion_record_is_one_constant_per_narrowed_file_with_every_adr_077_field() -> None:
    """ADR-077's retirement duty, as the mechanical check the entry defines.

    Step 1 is the grep for ``_PY_EXCLUDED`` under ``tests/``, one hit per live exclusion because
    the record is a module constant named for the file it narrows. **Counted over files, not
    lines**, and that is an amendment ADR-077 is owed rather than a reading of it: the entry says
    ``grep -rn`` returns two after A27, which is wrong twice over -- it holds only for a one-line
    record, and A27 narrows four carriers rather than two. Six fields make it a multi-line literal,
    so ``grep -rn`` returns many and ``grep -rl`` returns the files the entry means. Measured at
    ``101028c``: **0** files against twelve ``_PY_SHA256`` lines over six clauses in four files;
    **four** after A27, every carrier of ``DIFF_PY_SHA256``. Asserting the file list here is what
    makes a fifth exclusion, minted anywhere in ``tests/`` without a re-freeze packet behind it,
    fail rather than accumulate -- Q1's named failure mode is exclusions piling up unretired.
    A27's own retirement sweep discharges empty: nothing carried an exclusion at ``101028c``, so
    there was no orphan to file.

    **A22's retrofit, 2026-09-13.** The file list is unchanged: A22 adds a second *region* to an
    existing record constant, not a fifth carrier. The per-record assertions now pin ``owner`` and
    ``minted_at`` per entry rather than one shared literal, because ``_coverage`` is minted at
    ``4b3c6ae`` and ``_pairing`` at ``101028c``. Two live regions on one file is ADR-077's
    *adjacent* case and not its refused *overlapping* one, so the spans are asserted disjoint here
    rather than assumed. Neither exclusion is retirable yet: both name ``A28`` as their retiring
    packet, and A22 is not it.

    **A28's retrofit, 2026-09-13 -- both exclusions retired.** ``_pairing`` (A27, ``101028c``) and
    ``_coverage`` (A22, ``4b3c6ae``) both named ``A28``; both owners have landed and A28 rewrites
    every carrier, so ``DIFF_PY_SHA256`` is the whole-file value again, read off the shipped file,
    and this file carries no record. What stays is the sweep, asserted from a file that carries no
    exclusion -- which is what makes a fifth one turn four clauses red -- and it finds
    ``test_s29_viewer.py`` alone, the carrier of A28's own ``report.py::_check_tree`` exclusion.
    **Counted over module-level constants named ``*_PY_EXCLUDED``, by AST and not by text**,
    because the text grep the entry describes counts this docstring and the sweep line itself
    once the record is gone (measured: it returned all four carriers after retirement).
    """
    hits = sorted(path.name for path in sorted((REPO / "tests").glob("test_*.py")) if excluded_constants(path))
    assert hits == ["test_s29_viewer.py"], hits
