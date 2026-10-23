"""S26 -- the grouping resolver and the fault lines: the oracle for F1-F30.

Written from "Proofload -- Spec S26 Layered Report P4.2 Resolver and Fault Lines" section 4 and
"Handoff P4.2", against ``11502ba`` plus the retrofit commit ``082c87d`` (2026-09-07). Session B
builds ``src/proofload/tree.py`` (the resolver, ``tree``, the four dataclasses) and the two flags,
one block and one key in ``src/proofload/cli.py`` against this file and does not edit it.

**``proofload.tree``'s new names are imported inside each test body**, the way the S25 oracle
reached the module before it existed: this file collects on the bare tree, its own tests fail
there, and every other test in the repo still reports. The static tests read the source as text.

**No test in this file carries the ``calibration`` marker, and none may.** Spec section 0.6,
measured in ``log/phase4-p42-step-zero-slow.py`` (K=200 sharp-null resamples of Go1 by ``mu``,
B=1000): Level 2 is gated on the root, so under the global sharp null the unconditional rate of
any group rejecting is bounded by the root's own rate, which O10 already holds inside
``[0.020, 0.080]``. Measured gated rates: 0.005 with BH and 0.030 with no correction under pair
swap, 0.015 and 0.040 under arm label -- all inside the band, so a band cannot tell a correct
Level 2 from one with no correction at all, and the only column that separates them (ungated, no
correction, 0.60) is unreachable from the public surface. Every Level 2 wiring error is caught
deterministically here (F13-F16), and F24 is the fast twin of the lane's one sole catch (S25 M3b).
Nothing below loops over resamples; a property test over small synthetic pairs is not a lane.

**Step zero, re-derived before a test was written** (``scratchpad/p42_session_a_step_zero.py``,
89 s against the bare tree; every number below is that script's or the spec's script's):

1. **The refusal rule is S23's gate at the family floor, on shape alone.** The step-zero script's
   ``describe_grouping`` computes ``mde_two_proportion(0.5, n_a_g, n_b_g, alpha=q/G)`` from the
   design's per-arm unit counts summed over the group's cells and reads no delta; the constant is
   ``executor.DEFAULT_MAX_MDE`` imported. On both substrates every group is equal-sized, so the
   script's ``power_{min,median,max}_gt_threshold`` rules coincide with "at least two resolve";
   recomputed as that count directly: S18 ``task_id`` 0 of 164 (0.3615, refused), S18
   ``temperature`` 2 of 2 (0.0301), Go1 ``mu`` and ``push_pct_bw`` 20 of 20 (0.1073), under both
   schemes. Exactly one grouping refused, across every axis of both substrates. F7 recomputes the
   rule from ``units`` and the partition; F7's shape test resolves the axes pair and its identical
   twin (same shape, every delta zero) to byte-identical ``Grouping`` JSON, which is what pins
   "admitted before any delta is read".
2. **The rule's failure modes, named so the refusal is not read as more than it is.** It is a
   design-time rule anchored at base rate 0.5 and the sparse alternative ``q/G``. It can admit a
   grouping whose groups are mostly degenerate when N is large (the degenerate count is printed,
   not gated -- ADR-067's hatch); it can refuse a dense alternative that BH's step-up would have
   had power for (the 4 x 4 pair is where ``q/G`` and ``q`` part); and at extreme base rates the
   real power is below the anchor's (S23 section 3's 0.34 against 0.3251). None of those is a
   reason to move it now, and no fixture here claims otherwise.
3. **The axes pair** (164 ``task`` x 2 ``temp``, N=8, every cell all-``ok``; arm b moves twenty
   cells of ``temp = 0.0`` by two matched pairs ``ok -> fail`` at replicates 0 and 1): root at the
   floor and ``temp = 0.0`` at the floor under **both** schemes with no widening; the flat family
   rejects nothing (min raw p 0.5 under McNemar, 0.4667 under Fisher; min q 1); ``temp = 0.7``
   degenerate under both. A mixed base (``fail x2 + ok x6``) was measured too: with two pairs the
   arm-label root sits at p 0.38 and the group at 0.15, because 308 mixed cells contribute
   permutation variance the twenty moved cells must overcome; six pairs would be needed, which is
   not the spec's fixture. The all-``ok`` base keeps the spec's forty discordant pairs and McNemar
   p of 0.5 and is the one on which "the group sees what no leaf can" is literal: no leaf p is
   below 0.46 before any correction. ``task`` refuses at 0.5000 (the cap; offered 0.5000) and
   ``temp`` admits at 0.0600.
4. **The BH pair** under ``mcnemar_bh`` reproduces section 0.7 exactly: root p 0.00749813 and
   ``g00``'s ``p_group`` bit-equal to it (seeds 0-2), the other nineteen at p 1 and degenerate,
   ``q_group = 0.15``, and BH over the one informative group would give 0.0075. **The arm-label
   twin of that shape does not exist**: over w in {2..10} cells and k in {1..16} extra failures no
   combination has the root rejecting while ``g00`` sits in ``(q/20, q)``. The reason is
   structural, not a search miss: under arm label the nineteen mixed groups contribute permutation
   variance to the root's statistic and none to ``g00``'s slice, so ``g00`` is always far more
   extreme than the root (root p 0.98 at eight weak cells against ``g00`` 0.61; root 0.0057 at
   ten cells x twelve against ``g00`` at the floor). F14 is therefore asserted under
   ``mcnemar_bh`` only, as the spec allows, and two unnumbered arm-label guards are added: a
   **strong** variant (ten cells x sixteen: root and ``g00`` at the floor, the nineteen at p 1 and
   informative) for F16's arm-label clause, and a **two-group** variant (``g01`` ten cells x twelve
   strong, ``g00`` eight cells x three weak: root p 0.0017, ``g00`` p 0.0215 -- 8.3 sd above
   ``q/20`` and 12.4 below ``q`` -- ``q_group`` 0.215, not rejected) for "no correction" under arm
   label. Neither can see ``m = informative groups`` (all twenty are informative under arm label);
   Go1 by ``push_pct_bw`` and the McNemar BH pair do.
5. **The discordant cell** (section 0.4's exact frames) reproduces to the digit: ``p_location``
   0.2209, 0.2119, 0.2204, 0.2249, 0.2159 under pair swap against the exact 0.215327 and 0.0785,
   0.0890, 0.0810, 0.0767, 0.0912 under arm label against 0.079341; ``p_dispersion == p_location
   == p_omnibus`` on every seed. Band edges are at least 5.4 sd from the exact value and 6 sd from
   the other scheme's; an exchange regressed to arm label under ``mcnemar_bh`` reads about 0.08
   and fails ``[0.18, 0.26]`` alone.
6. **Go1's Level 2 golden re-derived at B=4000, seed 0**: by ``push_pct_bw`` exactly twelve groups
   reject (``10.0`` ... ``120.0``), all at the floor, ``150.0/170.0/180.0/190.0/200.0`` degenerate,
   ``140.0`` and ``160.0`` with one informative cell each at p 1; by ``mu`` nineteen reject, the
   fifteen ``0.05`` ... ``0.75`` at the floor under both methods (``0.9`` too under Fisher), and
   ``0.95`` at p 0.075 / 0.103. All 60 (55) flat rejections lie inside rejecting groups on both
   axes. BH with ``m = G`` and ``m = informative`` differ on the push axis (five degenerate) and
   coincide on ``mu``, so F14's recompute clause on Go1 push is what catches ``m = informative``.
7. **The F28 digest**, minted on the bare tree: ``omnibus(go1-v0, go1-v1, events=("fell",),
   method="fisher_bh", B=4000, seed=0).to_json()`` minus the five p-driven keys, ``json.dumps``
   with sorted keys, sha256 ``03e7984b...``. ``diff.py``'s bytes are pinned by their own digest
   rather than by a ``git diff``, which a scratch copy without ``.git`` cannot run.

**Spec text this oracle could not use as written, each resolved here and reported.**

- F8's ``max_group_mde = 0.37`` cannot admit ``task`` on the axes pair: at N=8 the group MDE is the
  cap 0.5000 (the spec's own section 6 number); 0.37 is S18's value at N=32. F8 uses the offered
  value pasted back (0.5000, equality passes) and an explicit 0.6.
- F16's "the nineteen have ``p_group == 1.0`` under both" is unsatisfiable on the spec's BH pair
  under ``fisher_bh``: the root sits at p 0.98 there, the level is not tested and every p is
  ``None``. The arm-label clause is asserted on the strong variant, where the root rejects.
- Section 7's property tests say ``max_group_mde = 1.0`` "so the grouping resolves"; F8 refuses
  ``1``. They use 0.75 (every MDE is at most the cap 0.5, so anything above admits everything).
- F21's literal field list includes ``cells``, ``key``, ``label``, ``q``, ``root``, ``null``,
  ``reason`` and other names ``cli.py`` already uses as locals; ``_cmd_runs`` joins a local named
  ``cells`` with ``+`` at ``11502ba``, so the guard as written is red on the bare tree. Here every
  tree field is guarded as an attribute, and the names that cannot collide with a local (O17's
  thirteen, ``n_uninformative_cells`` and the compound tree names) are guarded as bare names too.
- F5 and F19 conflict on ``step_kind``: ``--by step_kind`` must echo its key verbatim (section 8
  trap 14) in a refusal row and on the block, and F19 forbids the substring ``step`` on both. The
  vocabulary check masks the requested key before it looks; a build that echoes the name passes,
  one that writes "failed at step" does not.
- Section 6 says "every leaf in ``temp = 0.0`` has two discordant pairs"; twenty of the 164 do.
- Section 0.2's table reads 0.1750 for the 4 x 4 pair at ``alpha = q``; ``mde_two_proportion``
  gives 0.171705. Section 6's "MDE 0.49" for the imported pair's ``tool_fail_rate`` is 0.4597
  (0.4927 is the 400 x 1 row). Both still separate what they are meant to separate.
- F15 names S25's three-cell identical pair, whose only axis refuses at the cap so the grouping
  collapses to ``whole_grid`` and ``reason`` is ambiguous between the two untested cases. **This
  oracle fixes root-first precedence**: when the root did not reject, ``reason`` is
  ``"root_not_rejected"`` whatever the grouping's cardinality, because the gate is evaluated before
  the level's shape and the more fundamental fact is the one stated. F15's full clause is asserted
  on an identical pair of the axes shape, where ``temp`` resolves to two groups.
- S25 section A's "two decorator lines" on O10 is one line: one function parametrises into both.

**Conventions this oracle fixes where the spec is silent. Session B builds to these.**

- ``next_rung`` is the rung that makes the next attempt: ``"axis"`` when the axis rung refuses one
  axis and another remains, ``"task_family"`` when it refuses its last one, ``"trace"`` after the
  requested rung, ``"axis"`` after the trace stub.
- The verdict word on a tested group line is ``rejected`` / ``not rejected``, O18's convention.
- A refusal's ``detail`` prints the accepted and offered values at four decimals, S23's format; the
  alpha floor at ``:g``, ``:.3g`` or ``:.2e``.
- ``to_json()`` "bytes" means ``json.dumps(payload, sort_keys=True)``.
- F28 pins ``diff.py`` by the sha256 of its bytes, not by ``git diff``.
- Every number on a fault-lines block line is a ``:g`` rendering of a field of the object that
  line describes, or the group's label; the check is on tokens, never on wording.

**Named non-observables.** A weight *inside* ``_statistics`` (ADR-066); ``omnibus`` called a
second time from ``_cmd_diff`` with the same seed (same bytes); a ``--by`` naming an axis declared
in one manifest only (F6 pins "neither", F29 pins the unrequested ``not_shared`` row); the
``detail`` wording of ``one_group`` and ``not_shared`` refusals beyond their fields.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
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
from poisson_prove import executor
from poisson_prove.diff import multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import ReportSpec, build_multi_report
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash

PACKAGE = Path(poisson_prove.__file__).resolve().parent
REPO = PACKAGE.parents[1]
GO1_ROOT = REPO / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"
TREE_SOURCE = PACKAGE / "tree.py"
CLI_SOURCE = PACKAGE / "cli.py"
DIFF_SOURCE = PACKAGE / "diff.py"
METHODS = ("fisher_bh", "mcnemar_bh", "logrank_bh")
TWO_SCHEMES = ("mcnemar_bh", "fisher_bh")

#: Spec section 2, this file's literals (F1). Never read back from the module.
EXPECTED_RUNG_ORDER = ("requested", "trace", "axis", "task_family", "whole_grid")
EXPECTED_TRACE_GROUPINGS = ("kind", "step_kind")
EXPECTED_TASK_FAMILY_KEYS = ("task_family", "task_id", "task")
EXPECTED_WHOLE_GRID = "grid"
EXPECTED_WHOLE_GRID_KEY = "whole_grid"
EXPECTED_REFUSAL_REASONS = ("unsupported", "underpowered", "one_group", "not_shared")
EXPECTED_GROUP_NULL = "no cell in the group changed"
EXPECTED_MIN_RESOLVABLE_GROUPS = 2
EXPECTED_DEFAULT_MAX_GROUP_MDE = 0.20
EXPECTED_NOT_TESTED_REASONS = ("root_not_rejected", "one_group")
Q = 0.05

GOLDEN_PERMUTATIONS = 4000
GOLDEN_SEED = 0
#: O13's cost pin, extended by F6 and F30: a refusal that validates first returns in milliseconds.
REFUSAL_PERMUTATIONS = 10**6
REFUSAL_BUDGET_SECONDS = 10.0

#: Section 4 F24, the S25 amendment's bands; step zero item 5 says why they hold.
DISCORDANT_BANDS = {"mcnemar_bh": (0.18, 0.26), "fisher_bh": (0.05, 0.12)}

#: F27: the keys a different seed may move.
P_DRIVEN_ROOT_KEYS = ("p_location", "p_dispersion", "p_omnibus", "rejects", "headline")
P_DRIVEN_GROUP_KEYS = ("p_location", "p_dispersion", "p_group", "q_group", "rejects")
P_DRIVEN_FAULT_LINE_KEYS = ("n_rejected_groups", "rejected_groups")

#: F19. O19's nine phrases plus this packet's additions, case-insensitive.
FORBIDDEN_VOCABULARY = (
    "given the root", "given that", "conditional on", "leaf", "fdr", "broke", "where it broke",
    "failed at", "step",
    "broken", "failed in", "where it", "culprit", "root cause", "power stays high", "high power",
    "well powered", "same shift",
)
FORBIDDEN_FIELD_SUBSTRINGS = ("interval", "level", "leaf", "broke", "where", "step")

#: The fields of the five structures (spec section 2), as this file's literal (F19, F21).
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
TREE_RESULT_FIELDS = ("root", "grouping", "fault_lines")
#: O17's thirteen root fields, restated.
ROOT_GUARDED_FIELDS = (
    "location", "dispersion", "p_location", "p_dispersion", "p_omnibus", "rejects", "n_cells",
    "n_informative_cells", "n_discordant", "n_permutations", "seed", "scheme", "units",
)
#: F21. Every name is guarded when reached as an attribute; the names that cannot collide with a
#: local variable in ``cli.py`` are guarded as bare names as well (the module docstring says why
#: ``cells``, ``key``, ``q`` and the other short ones are not).
CLI_GUARDED_ATTRIBUTES = set(ROOT_GUARDED_FIELDS) | {"n_uninformative_cells"} | set(REFUSAL_FIELDS) | set(GROUPING_FIELDS) | set(GROUP_RESULT_FIELDS) | set(FAULT_LINES_FIELDS) | set(TREE_RESULT_FIELDS)
CLI_GUARDED_NAMES = set(ROOT_GUARDED_FIELDS) | {
    "n_uninformative_cells", "n_groups", "n_resolvable_groups", "offered_max_group_mde", "resolved_by", "next_rung",
    "group_sizes", "size_min", "size_median", "size_max", "alpha_floor", "max_group_mde", "group_mde", "refused",
    "n_informative_cells", "p_group", "q_group", "n_degenerate_groups", "n_rejected_groups", "rejected_groups",
    "fault_lines", "grouping", "degenerate", "requested",
}
#: The ``:g``-rendered fields the first block line must carry (F20).
FIRST_LINE_NUMERIC_FIELDS = ("n_groups", "size_min", "size_median", "size_max", "n_resolvable_groups", "max_group_mde", "alpha_floor")

#: F28. Minted on the bare tree at 082c87d (11502ba plus the marker retrofit), 2026-09-07:
#: ``omnibus(go1-v0, go1-v1, events=("fell",), method="fisher_bh", B=4000, seed=0).to_json()``
#: with the five p-driven keys removed, ``json.dumps(sort_keys=True)``, sha256.
F28_OMNIBUS_SHA256 = "bb70ad821a933319c9200dee4310ebc117648208675ec6f2556e4386c383232f"
#: ``src/proofload/diff.py``'s bytes, whole, unchanged since cd5f177 (``git diff --exit-code``).
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
#: S25's O14/O23 digests, restated rather than imported so two frozen oracles do not couple.
MULTI_JSON_SHA256 = {
    "fisher_bh": "c284e029ea858e3f50a9ee6ca3b55a1abc61a1b08a1fe213e393939c6e0872b8",
    "mcnemar_bh": "a2ff3e20c8dfd4b8bc5cd0841df723646b28ef991e8b06b29e5e934f6987b9e8",
    "logrank_bh": "45a95393006e732b58b40c0b07df2ae87a380ece95fe47f4165bdfe776cf8c02",
}
CHECK_ARGV = ("check", GO1_A, GO1_B, "--event", "fell")
CHECK_STDOUT_SHA256 = "dc3d8acc89864cdb69eda671d931c492e3e81c1d74eb1393b37d789f8c2d3417"
CHECK_EXIT = 0
SERVE_ARGV = ("serve", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw", "--json")
# Re-minted 2026-09-20 (truncation surfacing): the structure's ``diff`` object renames the horizon key in place and gains six keys, and the
# schema is /5 before this projection sets it back to /2. Each value is the baseline's plus that change.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): the structure gains the summary key and each panel's mde_unchanged (spec LS sections 3.3, 3.5); with schema projected back to /2 nothing else moves, the Go1 figure included. The same value in all five carriers. Read through this test's own measurement on the built tree, not predicted.
SERVE_STRUCTURE_SHA256 = "4dc0e70ec6638d9206648e04d0384532d0fdd7d68d101105a92ae1e94ecead44"
#: S29's narrowing (spec S29 section 3.7, draft ADR-074): ``serve --json`` now prints
#: ``proofload.viewpair/3``, which carries M14's tree under one new top-level key. The digest above
#: was minted on the bare tree, so it is taken over the structure with ``tree`` removed and
#: ``schema`` set back to this literal; on the bare tree that projection is the identity.
TREE_LESS_SCHEMA = "proofload.viewpair/2"
PAIR_QCOLUMN_SHA256 = "1e8e75a1679a92ba553d45d4b4fcdfd946d0e77939fec7ae7c214270e77719f9"
PAIR_DELTA_SHA256 = "0b46042d58b4ce9d8ff7cadfef1a0e20637d66e43de58c08f710e2021d3b35bf"
COVERAGE_SHA256 = "e02aae9ac0d0f902d5fdb9d36340e3a7a72c1a7d6d86b0e5a75fffda95dee5fa"
FELL_LOGRANK_QCOLUMN_SHA256 = "175f731751711047063b840dacb61c3a9e8ac86ccd937d0043d4986283821e53"
E14_ARGV = ("report", GO1_A, GO1_B, "--event", "fell", "--x", "mu", "--y", "push_pct_bw")
# Re-minted 2026-09-20 (truncation surfacing): report.md and receipt.html take the horizon rename and the two observation-cap lines
# (the builder is handed manifests and no counts); heatmap.svg is unchanged. Each value is the baseline's plus that change, byte for byte.
E14_SHA256 = {
    "report.md": "39c6dde2db4de96337b13a667d37e080d86664e03ce7593e7714fdeb777154d8",
    "heatmap.svg": "2e0dfe4e27314d30f1514104a60d0a566a75f4c032fa1b25f92b779f70c324de",
    "receipt.html": "705aae536623bf35a91a31dd4c3c7967532ce9698cd9fe1de4a01158f39ca379",
}

#: Golden labels on Go1 (step zero item 6). ``str(value)`` of the config floats.
GO1_PUSH_REJECTED = tuple(str(float(v)) for v in range(10, 130, 10))
GO1_PUSH_DEGENERATE = ("150.0", "170.0", "180.0", "190.0", "200.0")
GO1_PUSH_ONE_INFORMATIVE = ("140.0", "160.0")
GO1_MU_AT_FLOOR = tuple(str(v) for v in (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75))
GO1_MU_NOT_REJECTED = "0.95"
GO1_FLAT_REJECTIONS = {"fisher_bh": 60, "mcnemar_bh": 55}

#: Synthetic vocabularies. Non-events end at the horizon; events end at ``EVENT_T``.
NON_EVENTS = frozenset({"ok", "x", "z"})
EVENT_T = 2.0
HORIZON = 5.0
AXES_SALT, BH_SALT, SALT, OTHER_SALT = "s26-axes-salt", "s26-bh-salt", "s26-salt", "s26-other-salt"
AXES_TYPES_TASK_FIRST = {"task": "categorical", "temp": "continuous"}
AXES_TYPES_TEMP_FIRST = {"temp": "continuous", "task": "categorical"}
BH_TYPES = {"grp": "categorical", "cell": "categorical"}
N_TASKS, AXES_N, AXES_MOVED_CELLS, AXES_MOVED_PAIRS = 164, 8, 20, 2


# ---------- data builders: construction only, no assertions and no decisions ----------


def tree() -> Any:
    """``proofload.tree``, imported at call time (see the module docstring)."""
    return importlib.import_module("poisson_prove.tree")


def go1_frames() -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    store = Store(GO1_ROOT)
    return store.read(GO1_A, meta=False), store.read(GO1_B, meta=False), store.manifest(GO1_A), store.manifest(GO1_B)


def quiet_multi_diff(a: pd.DataFrame, b: pd.DataFrame, ma: RunManifest, mb: RunManifest, *, events: Sequence[str], method: str, q: float = Q) -> Any:
    """``multi_diff`` with the unpaired-analysis warning silenced; no test below is about it."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return multi_diff(a, b, events=list(events), method=method, q=q, manifest_a=ma, manifest_b=mb)  # type: ignore[arg-type]


def manifest(run_id: str, salt: str, axis_types: Mapping[str, str]) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types), backend="synthetic", environment={"note": "built by test_s26_fault_lines"},  # type: ignore[arg-type]
    )


def reordered(m: RunManifest, axis_types: Mapping[str, str]) -> RunManifest:
    """Section 6: the same manifest with ``axis_types`` rebuilt in another declared order."""
    return RunManifest(**{**m.to_dict(), "axis_types": dict(axis_types)})


def raw_frame(run_id: str, cells: Mapping[tuple[tuple[str, Any], ...], Sequence[str]], *, horizon: float = HORIZON) -> pd.DataFrame:
    """An in-memory frame with the eleven columns ``Store.read(meta=False)`` returns, over
    multi-key configs: ``cells[(("task", "t0"), ("temp", 0.0))]`` is that cell's outcomes in
    replicate order. S25's ``raw_frame`` widened to two-key configs."""
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
    """A complete synthetic run over multi-key configs, one episode per outcome. S25's ``write_run``
    restated and widened the same way as ``raw_frame``."""
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
    """Section 6's axes pair: 164 ``task`` x 2 ``temp`` at N=8, every cell all ``ok``; when
    ``moved``, the first twenty cells of ``temp = 0.0`` carry ``fail`` at replicates 0 and 1."""
    cells = {}
    for i in range(N_TASKS):
        for temp in (0.0, 0.7):
            outcomes = ["ok"] * AXES_N
            if moved and temp == 0.0 and i < AXES_MOVED_CELLS:
                outcomes = ["fail"] * AXES_MOVED_PAIRS + ["ok"] * (AXES_N - AXES_MOVED_PAIRS)
            cells[(("task", f"t{i:03d}"), ("temp", temp))] = outcomes
    return cells


def bh_cells(weak_cells: int, extra_fails: int, strong: tuple[int, int] | None = None) -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """Section 0.7's BH pair: twenty ``grp`` x ten ``cell`` at N=32, ``fail x4 + ok x28`` in both
    arms; ``g00``'s first ``weak_cells`` cells carry ``extra_fails`` more ``fail`` in arm b from
    replicate 4. ``strong=(cells, fails)`` moves ``g01`` the same way (the two-group variant)."""
    a, b = {}, {}
    for g in range(20):
        for c in range(10):
            key = (("grp", f"g{g:02d}"), ("cell", f"c{c}"))
            base = ["fail"] * 4 + ["ok"] * 28
            a[key], b[key] = list(base), list(base)
            if g == 0 and c < weak_cells:
                for r in range(4, 4 + extra_fails):
                    b[key][r] = "fail"
            if strong is not None and g == 1 and c < strong[0]:
                for r in range(4, 4 + strong[1]):
                    b[key][r] = "fail"
    return a, b


def discordant_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """Section 0.4's frames: one cell, arm a ``fail`` for i < 20, arm b ``fail`` for i >= 20."""
    key = (("task", "d"),)
    return {key: ["fail"] * 20 + ["ok"] * 12}, {key: ["ok"] * 20 + ["fail"] * 12}


def four_by_four_cells() -> dict[Any, list[str]]:
    """Sixteen cells over ``x`` x ``y`` at N=32; the rule is shape-only, so any outcomes."""
    return {(("x", i), ("y", j)): ["fail"] * (2 + i) + ["ok"] * (30 - i) for i in range(4) for j in range(4)}


def ragged_cells() -> dict[Any, list[str]]:
    """One categorical axis ``fam`` with sizes 20, 1, 1, 1 at N=32; ``cell`` is an undeclared
    second key that keeps the singleton cells distinct."""
    cells = {(("fam", "A"), ("cell", i)): ["fail"] * 4 + ["ok"] * 28 for i in range(20)}
    for fam in ("B", "C", "D"):
        cells[(("fam", fam), ("cell", 0))] = ["fail"] * 4 + ["ok"] * 28
    return cells


def imported_cells() -> dict[Any, list[str]]:
    """Eighty cells whose configs carry ``task_id`` (eight values x ten) and ``tool_fail_rate``
    (eighty distinct values); the manifests declare only ``tool_fail_rate``."""
    return {(("task_id", f"T{t}"), ("tool_fail_rate", round(0.01 * (10 * t + c), 2))): ["fail"] * 4 + ["ok"] * 28 for t in range(8) for c in range(10)}


def one_value_cells(moved: bool) -> dict[Any, list[str]]:
    """Four cells over ``task`` with ``temp`` at the single value 0.0, N=8."""
    return {(("task", f"t{i}"), ("temp", 0.0)): (["fail"] * 8 if moved else ["ok"] * 8) for i in range(4)}


def three_cell_identical() -> dict[Any, list[str]]:
    """S25's ``same-a``/``same-b``: three cells of eight over ``task`` on one salt."""
    return {(("task", "t0"),): ["fail"] * 2 + ["ok"] * 6, (("task", "t1"),): ["fail"] * 4 + ["ok"] * 4, (("task", "t2"),): ["fail"] * 6 + ["ok"] * 2}


def three_outcome_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """S25's six cells of 32 over ``x``, ``y``, ``z``, restated."""
    a = {(("task", f"c{i}"),): ["x"] * 4 + ["y"] * 4 + ["z"] * 24 for i in range(6)}
    b = {(("task", f"c{i}"),): ["x"] * 4 + ["y"] * 20 + ["z"] * 8 for i in range(6)}
    return a, b


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(argv, stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


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


def fault_lines_block(out: str) -> list[str]:
    return block_lines(out, "fault lines:")


def omnibus_block(out: str) -> list[str]:
    return block_lines(out, "omnibus: ")


def numeric_tokens(line: str) -> list[str]:
    """Every whitespace-, ``=``-, ``,``-, ``:``-, ``;``-, ``(``-, ``)``- or ``/``-separated token
    that parses as a number, verbatim. Wording-free: the block's numbers are checked as tokens."""
    out = []
    for token in re.split(r"[\s=,:;()/]+", line):
        try:
            float(token)
        except ValueError:
            continue
        out.append(token)
    return out


def g(value: Any) -> str:
    return f"{value:g}"


def json_bytes(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True)


def without(payload: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in keys}


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_column(result: Any, column: str) -> str:
    return sha256_of_text("|".join(f"{e}:" + ",".join(f"{v:.17g}" for v in result.by_event[e].cells[column]) for e in result.events))


def flat_rejections(multi: Any, event: str) -> set[str]:
    """The flat BH family's rejected hashes for one event, recomputed from ``cells.q``."""
    cells = multi.by_event[event].cells
    return set(cells.loc[cells["q"] < multi.q, "config_hash"].astype(str))


def group_rows(units: pd.DataFrame, event: str, hashes: Sequence[str]) -> pd.DataFrame:
    return units[(units["event"] == event) & units["config_hash"].astype(str).isin(set(hashes))]


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


def called_name(node: ast.Call) -> str | None:
    func = node.func
    return func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)


class Unreadable:
    """A frame stand-in that fails on any read. F5 hands a pair of these to ``resolve_grouping``
    as ``frames``: the trace rung reads nothing today, so nothing may touch them."""

    def _refuse(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the trace rung read a frame before Phase 6")

    __getattr__ = __getitem__ = __len__ = __iter__ = __bool__ = _refuse


def grown(a: pd.DataFrame, b: pd.DataFrame, multi: Any, ma: RunManifest, mb: RunManifest, **knobs: Any) -> Any:
    """``tree.tree`` on a pair, the way every test below reaches it."""
    return tree().tree(a, b, multi, manifest_a=ma, manifest_b=mb, **knobs)


def second_smallest_rounded_up(mdes: Sequence[float]) -> float:
    """S23's offered-override rule restated (spec S23 section 3, ``_offered_override``): the
    ``MIN_RESOLVABLE_GROUPS``-th smallest group MDE rounded **up** at four decimals, bumped by
    ``1e-4`` when the rounding fell short, so that pasting it admits the grouping."""
    mde = sorted(mdes)[EXPECTED_MIN_RESOLVABLE_GROUPS - 1]
    offered = math.ceil(mde * 1e4) / 1e4
    return offered if offered >= mde else offered + 1e-4


def partition_by(units: pd.DataFrame, key: str, event: str) -> dict[str, list[str]]:
    """The label -> sorted hashes partition a key induces on the root's common cells, built here
    from ``units`` alone so a refused grouping's shape can be recomputed (F7)."""
    rows = units[units["event"] == event]
    out: dict[str, list[str]] = {}
    for h, config in zip(rows["config_hash"].astype(str), rows["config"], strict=True):
        out.setdefault(str(config[key]), []).append(h)
    return {label: sorted(hashes) for label, hashes in out.items()}


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
def go1() -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    return go1_frames()


@pytest.fixture(scope="module")
def go1_trees(go1: Any) -> dict[str, tuple[Any, Any]]:
    """``(multi, tree)`` per method on Go1 at ``events=("fell",)``, the golden knobs, no ``by``:
    the default resolution, which is ``mu`` (arm A declares ``mu`` first)."""
    a, b, ma, mb = go1
    out = {}
    for method in METHODS:
        multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method=method)
        out[method] = (multi, grown(a, b, multi, ma, mb, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def go1_push(go1: Any) -> dict[str, tuple[Any, Any]]:
    """Go1 by ``push_pct_bw`` (requested), both schemes, the golden knobs (F16, F17)."""
    a, b, ma, mb = go1
    out = {}
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method=method)
        out[method] = (multi, grown(a, b, multi, ma, mb, by="push_pct_bw", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def axes() -> dict[str, Any]:
    """The axes pair in memory: frames plus manifests in both declared orders (section 6)."""
    return {
        "a": raw_frame("axes-a", axes_cells(False)),
        "b": raw_frame("axes-b", axes_cells(True)),
        "ma": manifest("axes-a", AXES_SALT, AXES_TYPES_TASK_FIRST),
        "mb": manifest("axes-b", AXES_SALT, AXES_TYPES_TASK_FIRST),
        "ma_temp_first": manifest("axes-a", AXES_SALT, AXES_TYPES_TEMP_FIRST),
        "mb_temp_first": manifest("axes-b", AXES_SALT, AXES_TYPES_TEMP_FIRST),
    }


@pytest.fixture(scope="module")
def axes_trees(axes: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    """``(multi, tree)`` on the axes pair, arm A declaring ``(task, temp)``, both schemes, the
    golden knobs, no ``by``."""
    out = {}
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(axes["a"], axes["b"], axes["ma"], axes["mb"], events=("fail",), method=method)
        out[method] = (multi, grown(axes["a"], axes["b"], multi, axes["ma"], axes["mb"], n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def bh_trees() -> dict[str, tuple[Any, Any]]:
    """Three BH-pair variants (step zero item 4): the spec's shape under ``mcnemar_bh``; the strong
    arm-label variant (ten cells x sixteen); the two-group arm-label variant (``g01`` strong,
    ``g00`` weak). Every one resolves ``grp`` (twenty groups of 320 units per arm, MDE 0.1506)."""
    out = {}
    for name, method, weak, strong in (
        ("mcnemar_bh", "mcnemar_bh", (8, 1), None),
        ("fisher_strong", "fisher_bh", (10, 16), None),
        ("fisher_two_group", "fisher_bh", (8, 3), (10, 12)),
    ):
        cells_a, cells_b = bh_cells(*weak, strong=strong)
        a, b = raw_frame("bh-a", cells_a), raw_frame("bh-b", cells_b)
        ma, mb = manifest("bh-a", BH_SALT, BH_TYPES), manifest("bh-b", BH_SALT, BH_TYPES)
        multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method=method)
        out[name] = (multi, grown(a, b, multi, ma, mb, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def discordant_trees() -> dict[str, tuple[Any, Any]]:
    cells_a, cells_b = discordant_cells()
    a, b = raw_frame("disc-a", cells_a), raw_frame("disc-b", cells_b)
    ma, mb = manifest("disc-a", SALT, {"task": "categorical"}), manifest("disc-b", SALT, {"task": "categorical"})
    out = {}
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method=method)
        out[method] = (multi, grown(a, b, multi, ma, mb, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED))
    return out


@pytest.fixture(scope="module")
def three_outcome() -> tuple[pd.DataFrame, pd.DataFrame, RunManifest, RunManifest]:
    cells_a, cells_b = three_outcome_cells()
    return raw_frame("tri-a", cells_a), raw_frame("tri-b", cells_b), manifest("tri-a", SALT, {"task": "categorical"}), manifest("tri-b", SALT, {"task": "categorical"})


@pytest.fixture(scope="module")
def every_tree(go1_trees: Any, go1_push: Any, axes_trees: Any, bh_trees: Any, discordant_trees: Any) -> list[tuple[str, Any, Any]]:
    """Every ``(name, multi, tree)`` this module builds at the golden knobs, for the invariants
    that hold on every fixture (F1, F2, F7, F12-F14, F16)."""
    out: list[tuple[str, Any, Any]] = []
    for prefix, group in (("go1", go1_trees), ("go1-push", go1_push), ("axes", axes_trees), ("bh", bh_trees), ("discordant", discordant_trees)):
        out.extend((f"{prefix}/{name}", multi, result) for name, (multi, result) in group.items())
    return out


@pytest.fixture(scope="module")
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One store holding the axes pair (``axes-a``/``axes-b``), the identical pair of the same
    shape (``same-a``/``same-b``, both arms the *moved* frame, so the event ``fail`` exists and
    ``diff``'s event guard admits it) and the empty family (``empty-a``/``empty-b``, no common
    cell)."""
    root = tmp_path_factory.mktemp("s26-synth")
    store = Store(root)
    write_run(store, "axes-a", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(False))
    write_run(store, "axes-b", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    write_run(store, "same-a", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    write_run(store, "same-b", salt=AXES_SALT, axis_types=AXES_TYPES_TASK_FIRST, cells=axes_cells(True))
    write_run(store, "empty-a", salt=SALT, axis_types={"task": "categorical"}, cells={(("task", "only-a"),): ["fail"] * 4 + ["ok"] * 4})
    write_run(store, "empty-b", salt=OTHER_SALT, axis_types={"task": "categorical"}, cells={(("task", "only-b"),): ["fail"] * 4 + ["ok"] * 4})
    return root


def store_tree(root: Path, a: str, b: str, *, events: Sequence[str], method: str, **knobs: Any) -> tuple[Any, Any]:
    """``(multi, tree)`` on a stored pair, the way the CLI reaches them."""
    store = Store(root)
    fa, fb = store.read(a, meta=False), store.read(b, meta=False)
    multi = quiet_multi_diff(fa, fb, store.manifest(a), store.manifest(b), events=events, method=method)
    return multi, grown(fa, fb, multi, store.manifest(a), store.manifest(b), **knobs)


# ---------- hypothesis: small two-key pairs, both schemes ----------


@st.composite
def small_two_key_pairs(draw: st.DrawFn) -> tuple[dict[Any, list[str]], dict[Any, list[str]], str, int, int]:
    """``2..4`` values on each of two keys ``x`` and ``y``, ``4..12`` replicates, two outcomes,
    both schemes, ``B`` in ``5..40``. With ``max_group_mde = 0.75`` the first axis resolves."""
    n_x, n_y = draw(st.integers(min_value=2, max_value=4)), draw(st.integers(min_value=2, max_value=4))
    n_reps = draw(st.integers(min_value=4, max_value=12))
    keys = [(("x", i), ("y", j)) for i in range(n_x) for j in range(n_y)]
    cells_a = {k: draw(st.lists(st.sampled_from(("ok", "fail")), min_size=n_reps, max_size=n_reps)) for k in keys}
    cells_b = {k: draw(st.lists(st.sampled_from(("ok", "fail")), min_size=n_reps, max_size=n_reps)) for k in keys}
    return cells_a, cells_b, draw(st.sampled_from(TWO_SCHEMES)), draw(st.integers(min_value=5, max_value=40)), draw(st.integers(min_value=0, max_value=10**6))


PROPERTY_SETTINGS = settings(deadline=None, max_examples=30, suppress_health_check=[HealthCheck.too_slow])
PROPERTY_TYPES = {"x": "continuous", "y": "continuous"}
PROPERTY_MAX_GROUP_MDE = 0.75


def property_tree(case: Any) -> Any:
    cells_a, cells_b, method, permutations, seed = case
    a, b = raw_frame("p-a", cells_a), raw_frame("p-b", cells_b)
    ma, mb = manifest("p-a", SALT, PROPERTY_TYPES), manifest("p-b", SALT, PROPERTY_TYPES)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method=method)
    return multi, grown(a, b, multi, ma, mb, n_permutations=permutations, seed=seed, max_group_mde=PROPERTY_MAX_GROUP_MDE)


# ---------- F1: the literals ----------


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


def test_f1_the_module_constants_are_the_spec_literals() -> None:
    """Asserted against this file's literals, never against the module's own (standing rule 1)."""
    t = tree()
    assert tuple(t.RUNG_ORDER) == EXPECTED_RUNG_ORDER
    assert tuple(t.TRACE_GROUPINGS) == EXPECTED_TRACE_GROUPINGS
    assert tuple(t.TASK_FAMILY_KEYS) == EXPECTED_TASK_FAMILY_KEYS
    assert t.WHOLE_GRID == EXPECTED_WHOLE_GRID
    assert tuple(t.REFUSAL_REASONS) == EXPECTED_REFUSAL_REASONS
    assert t.MIN_RESOLVABLE_GROUPS == EXPECTED_MIN_RESOLVABLE_GROUPS
    assert t.DEFAULT_MAX_GROUP_MDE == executor.DEFAULT_MAX_MDE == EXPECTED_DEFAULT_MAX_GROUP_MDE
    assert t.GROUP_NULL == EXPECTED_GROUP_NULL
    assert issubclass(t.UnknownGrouping, t.TreeError)
    assert issubclass(t.TraceGroupingUnsupported, t.TreeError)


def test_f1_every_rung_and_reason_on_every_fixture_is_drawn_from_the_tuples(every_tree: Any) -> None:
    for name, _, result in every_tree:
        assert result.grouping.resolved_by in EXPECTED_RUNG_ORDER, name
        for refusal in result.grouping.refused:
            assert refusal.rung in EXPECTED_RUNG_ORDER and refusal.next_rung in EXPECTED_RUNG_ORDER, (name, refusal)
            assert refusal.reason in EXPECTED_REFUSAL_REASONS, (name, refusal)
        assert result.fault_lines.null == EXPECTED_GROUP_NULL, name
        assert result.fault_lines.reason is None or result.fault_lines.reason in EXPECTED_NOT_TESTED_REASONS, name
        assert result.fault_lines.q == result.root.q, name


# ---------- F2: resolution without --by ----------


def test_f2_the_axes_pair_resolves_temp_after_refusing_task_in_arm_a_order(axes_trees: Any) -> None:
    """Arm A declares ``(task, temp)``: ``task`` is 164 groups of two cells at N=8, 16 units per
    arm, MDE at ``q/164`` the cap 0.5000 (step zero item 3), refused; ``temp`` is two groups of
    1312 units per arm, MDE 0.0600, admitted. **Go1 cannot show this**: both its axes pass."""
    for method, (_, result) in axes_trees.items():
        grouping = result.grouping
        assert (grouping.key, grouping.resolved_by, grouping.requested) == ("temp", "axis", None), method
        assert len(grouping.refused) == 1, (method, grouping.refused)
        refusal = grouping.refused[0]
        assert (refusal.key, refusal.rung, refusal.reason, refusal.next_rung) == ("task", "axis", "underpowered", "axis"), method
        assert (refusal.n_groups, refusal.n_resolvable_groups) == (N_TASKS, 0), method
        assert (grouping.n_groups, grouping.labels) == (2, ("0.0", "0.7")), method


def test_f2_arm_a_declaring_temp_first_refuses_nothing(axes: dict[str, Any]) -> None:
    multi = quiet_multi_diff(axes["a"], axes["b"], axes["ma_temp_first"], axes["mb_temp_first"], events=("fail",), method="mcnemar_bh")
    result = grown(axes["a"], axes["b"], multi, axes["ma_temp_first"], axes["mb_temp_first"], n_permutations=50, seed=GOLDEN_SEED)
    assert (result.grouping.key, result.grouping.resolved_by, result.grouping.refused) == ("temp", "axis", ())


def test_f2_go1_resolves_mu_with_no_refusal_under_every_method(go1_trees: Any) -> None:
    for method, (_, result) in go1_trees.items():
        grouping = result.grouping
        assert (grouping.key, grouping.resolved_by, grouping.refused, grouping.requested) == ("mu", "axis", (), None), method
        values = sorted({float(c["mu"]) for c in result.root.units["config"]})
        assert grouping.labels == tuple(str(v) for v in values), method
        assert grouping.n_groups == 20 and grouping.group_sizes == (20,) * 20, method


def test_f2_the_groups_partition_the_common_cells_on_every_fixture(every_tree: Any) -> None:
    """Union equals ``set(units.config_hash)``, pairwise disjoint, non-empty, sorted within a
    group, labels sorted numerically where every label parses and lexically otherwise, and the
    sizes recomputed from the partition."""
    for name, _, result in every_tree:
        grouping, units = result.grouping, result.root.units
        common = set(units["config_hash"].astype(str))
        flat = [h for label in grouping.labels for h in grouping.groups[label]]
        assert set(flat) == common and len(flat) == len(common), name
        assert set(grouping.groups) == set(grouping.labels) and len(set(grouping.labels)) == len(grouping.labels), name
        for label in grouping.labels:
            hashes = list(grouping.groups[label])
            assert hashes and hashes == sorted(hashes), (name, label)
            if grouping.key != EXPECTED_WHOLE_GRID_KEY:
                configs = units[units["config_hash"].astype(str).isin(set(hashes))]["config"]
                assert {str(c[grouping.key]) for c in configs} == {label}, (name, label)
        sizes = tuple(len(grouping.groups[label]) for label in grouping.labels)
        assert (grouping.group_sizes, grouping.n_groups) == (sizes, len(sizes)), name
        assert (grouping.size_min, grouping.size_median, grouping.size_max) == (min(sizes), float(np.median(sizes)), max(sizes)), name
        numeric = all(re.fullmatch(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?", label) for label in grouping.labels)
        expected = sorted(grouping.labels, key=float) if numeric else sorted(grouping.labels)
        assert list(grouping.labels) == expected, (name, grouping.labels)


@PROPERTY_SETTINGS
@given(case=small_two_key_pairs())
def test_f2_the_partition_property_holds_over_small_two_key_pairs(case: Any) -> None:
    _, result = property_tree(case)
    grouping, units = result.grouping, result.root.units
    assert grouping.key == "x" and grouping.resolved_by == "axis"
    flat = [h for label in grouping.labels for h in grouping.groups[label]]
    assert set(flat) == set(units["config_hash"].astype(str)) and len(flat) == len(set(flat))
    assert list(grouping.labels) == sorted(grouping.labels, key=float)
    assert grouping.group_sizes == tuple(len(grouping.groups[label]) for label in grouping.labels)


# ---------- F3, F4: requested ----------


def test_f3_a_requested_key_that_passes_reads_requested_on_the_structure(axes: dict[str, Any]) -> None:
    """ADR-043's *including when it is the one requested*: ``resolved_by`` is the rung that
    returned the grouping, and that rung is ``requested``."""
    multi = quiet_multi_diff(axes["a"], axes["b"], axes["ma"], axes["mb"], events=("fail",), method="mcnemar_bh")
    result = grown(axes["a"], axes["b"], multi, axes["ma"], axes["mb"], by="temp", n_permutations=50, seed=GOLDEN_SEED)
    grouping = result.grouping
    assert (grouping.resolved_by, grouping.requested, grouping.key, grouping.refused) == ("requested", "temp", "temp", ())


def test_f3_the_block_and_the_json_carry_the_requested_key(synth_root: Path) -> None:
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--by", "temp"])
    assert code == 0 and err == "", (out, err)
    block = fault_lines_block(out)
    assert block, out
    assert "temp" in block[0] and "requested" in block[0], block[0]
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--by", "temp", "--format", "json"])
    assert code == 0 and err == "", (out, err)
    grouping = json.loads(out)["tree"]["grouping"]
    assert (grouping["resolved_by"], grouping["requested"], grouping["key"]) == ("requested", "temp", "temp")


def test_f4_a_requested_key_that_is_refused_names_what_why_and_what_came_next(axes: dict[str, Any]) -> None:
    """``by="task"`` on the axes pair. The refusal is at the requested rung; the trace rung is
    tried next; the axis rung adds no second row for ``task`` and resolves ``temp``. The offered
    value is recomputed by S23's rounding-up rule from the recomputed group MDEs, and the detail
    carries the four numbers in S23's four-decimal format (module docstring)."""
    multi = quiet_multi_diff(axes["a"], axes["b"], axes["ma"], axes["mb"], events=("fail",), method="mcnemar_bh")
    result = grown(axes["a"], axes["b"], multi, axes["ma"], axes["mb"], by="task", n_permutations=50, seed=GOLDEN_SEED)
    grouping, units = result.grouping, result.root.units
    assert [r.key for r in grouping.refused] == ["task"]
    refusal = grouping.refused[0]
    assert (refusal.key, refusal.rung, refusal.reason, refusal.next_rung) == ("task", "requested", "underpowered", "trace")
    assert (refusal.n_groups, refusal.n_resolvable_groups) == (N_TASKS, 0)
    partition = partition_by(units, "task", "fail")
    mdes = []
    for hashes in partition.values():
        rows = group_rows(units, "fail", hashes)
        mdes.append(diff_mod.mde_two_proportion(0.5, int(rows["n_a"].sum()), int(rows["n_b"].sum()), alpha=multi.q / len(partition)))
    offered = second_smallest_rounded_up(mdes)
    assert refusal.offered_max_group_mde == offered and offered >= sorted(mdes)[1]
    assert str(N_TASKS) in refusal.detail and f"{grouping.max_group_mde:.4f}" in refusal.detail and f"{offered:.4f}" in refusal.detail
    alpha_floor = multi.q / N_TASKS
    assert any(rendering in refusal.detail for rendering in (f"{alpha_floor:g}", f"{alpha_floor:.3g}", f"{alpha_floor:.2e}")), refusal.detail
    assert (grouping.resolved_by, grouping.key, grouping.requested) == ("axis", "temp", "task")


# ---------- F5: the trace stub, and what makes it additive ----------


@pytest.mark.parametrize("name", EXPECTED_TRACE_GROUPINGS)
def test_f5_the_trace_stub_refuses_the_name_at_its_own_rung_and_resolution_continues(go1: Any, name: str) -> None:
    a, b, ma, mb = go1
    multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method="mcnemar_bh")
    result = grown(a, b, multi, ma, mb, by=name, n_permutations=50, seed=GOLDEN_SEED)
    grouping = result.grouping
    assert [r.key for r in grouping.refused] == [name]
    refusal = grouping.refused[0]
    assert (refusal.rung, refusal.reason, refusal.next_rung, refusal.n_groups) == ("trace", "unsupported", "axis", None)
    assert "Phase 5.2" in refusal.detail, refusal.detail
    assert (grouping.resolved_by, grouping.key, grouping.requested) == ("axis", "mu", name)


def test_f5_the_stub_is_additive_nothing_downstream_of_the_refusal_changes_shape(go1: Any, go1_trees: Any) -> None:
    """**The test that fails if the rung were not additive.** Phase 6 replaces one refusal with
    a resolution and nothing else; today, ``--by kind`` must therefore produce a tree identical
    to the unrequested one except for ``requested`` and the one extra row at the front of the
    chain -- the same root bytes, the same fault lines, the same partition, the same MDEs. A stub
    that raised through, that skipped a rung, that changed the resolved grouping, or that needed
    the CLI to special-case its name is not additive and fails here."""
    a, b, ma, mb = go1
    multi, base = go1_trees["fisher_bh"]
    kind = grown(a, b, multi, ma, mb, by="kind", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED).to_json()
    plain = base.to_json()
    assert kind["root"] == plain["root"]
    assert kind["fault_lines"] == plain["fault_lines"]
    assert without(kind["grouping"], ("requested", "refused")) == without(plain["grouping"], ("requested", "refused"))
    assert (kind["grouping"]["requested"], plain["grouping"]["requested"]) == ("kind", None)
    assert kind["grouping"]["refused"][1:] == list(plain["grouping"]["refused"]) == []
    assert (kind["grouping"]["refused"][0]["rung"], kind["grouping"]["refused"][0]["key"]) == ("trace", "kind")


def test_f5_the_trace_rung_reads_no_frame_today_and_its_exception_never_propagates(go1: Any, go1_trees: Any) -> None:
    """``frames`` is what the trace rung will read in Phase 6 and is unread now: a pair of objects
    that fail on any read must pass through untouched, and ``TraceGroupingUnsupported`` is caught
    by the resolver and recorded, never raised to the caller."""
    _, _, ma, mb = go1
    multi, base = go1_trees["fisher_bh"]
    t = tree()
    with_poison = t.resolve_grouping("kind", manifest_a=ma, manifest_b=mb, units=base.root.units, q=multi.q, frames=(Unreadable(), Unreadable()))
    without_frames = t.resolve_grouping("kind", manifest_a=ma, manifest_b=mb, units=base.root.units, q=multi.q)
    assert json_bytes(with_poison.to_json()) == json_bytes(without_frames.to_json())
    assert with_poison.refused[0].reason == "unsupported" and with_poison.key == "mu"


def test_f5_without_by_no_row_of_the_chain_is_at_the_trace_rung(every_tree: Any) -> None:
    for name, _, result in every_tree:
        if result.grouping.requested is None:
            assert all(r.rung != "trace" for r in result.grouping.refused), (name, result.grouping.refused)


# ---------- F6: an unknown name is refused outright ----------


@pytest.mark.parametrize("name", ("nonsense", "push"))
def test_f6_an_unknown_name_raises_unknown_grouping_before_any_permutation_is_drawn(go1: Any, go1_trees: Any, name: str) -> None:
    """ADR-043's hatch. ``push`` is an axis of neither Go1 manifest (they declare ``mu`` and
    ``push_pct_bw``). Pinned by cost, O13's way: at ``n_permutations = 10**6`` a refusal that
    validates first returns in milliseconds. A builder who falls back to the axes rung on an
    unknown name fails here alone."""
    a, b, ma, mb = go1
    multi, _ = go1_trees["fisher_bh"]
    started = time.perf_counter()
    with pytest.raises(tree().UnknownGrouping):
        grown(a, b, multi, ma, mb, by=name, n_permutations=REFUSAL_PERMUTATIONS, seed=GOLDEN_SEED)
    assert time.perf_counter() - started < REFUSAL_BUDGET_SECONDS


def test_f6_the_cli_maps_an_unknown_grouping_to_exit_two_without_a_traceback(synth_root: Path) -> None:
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--by", "nonsense"])
    assert code == 2, (out, err)
    assert "error:" in err and "Traceback" not in out + err, err
    assert "nonsense" in err and "usage:" not in err and "unrecognized" not in err, err


# ---------- F7: the power rule, recomputed ----------


def test_f7_the_group_mde_and_the_resolvable_count_are_recomputed_on_every_fixture(every_tree: Any) -> None:
    """``n_a_g``, ``n_b_g`` summed from ``units`` over each group's cells (identical per event),
    ``mde_two_proportion(0.5, n_a_g, n_b_g, alpha = q / n_groups)`` against ``group_mde`` and
    ``GroupResult.mde`` to ``1e-12``; ``alpha_floor``; ``n_resolvable_groups`` as the count; and
    for every ``underpowered`` refusal whose key the configs carry, the same recomputation on the
    partition that key induces, with the offered value by S23's rule."""
    for name, multi, result in every_tree:
        grouping, units, fault_lines = result.grouping, result.root.units, result.fault_lines
        assert abs(grouping.alpha_floor - multi.q / grouping.n_groups) <= 1e-15, name
        for index, label in enumerate(grouping.labels):
            sums = {e: (int(group_rows(units, e, grouping.groups[label])["n_a"].sum()), int(group_rows(units, e, grouping.groups[label])["n_b"].sum())) for e in result.root.events}
            assert len(set(sums.values())) == 1, (name, label, sums)
            n_a, n_b = sums[result.root.events[0]]
            expected = diff_mod.mde_two_proportion(0.5, n_a, n_b, alpha=multi.q / grouping.n_groups)
            assert abs(grouping.group_mde[index] - expected) <= 1e-12, (name, label)
            group = fault_lines.groups[index]
            assert (group.label, group.key, group.n_a, group.n_b) == (label, grouping.key, n_a, n_b), (name, label)
            assert abs(group.mde - expected) <= 1e-12, (name, label)
        assert grouping.n_resolvable_groups == sum(m <= grouping.max_group_mde for m in grouping.group_mde), name
        assert grouping.n_resolvable_groups >= EXPECTED_MIN_RESOLVABLE_GROUPS or grouping.key == EXPECTED_WHOLE_GRID_KEY, name
        for refusal in grouping.refused:
            if refusal.reason != "underpowered":
                continue
            partition = partition_by(units, refusal.key, result.root.events[0])
            mdes = []
            for hashes in partition.values():
                rows = group_rows(units, result.root.events[0], hashes)
                mdes.append(diff_mod.mde_two_proportion(0.5, int(rows["n_a"].sum()), int(rows["n_b"].sum()), alpha=multi.q / len(partition)))
            assert refusal.n_groups == len(partition), (name, refusal)
            assert refusal.n_resolvable_groups == sum(m <= grouping.max_group_mde for m in mdes) < EXPECTED_MIN_RESOLVABLE_GROUPS, (name, refusal)
            assert refusal.offered_max_group_mde == second_smallest_rounded_up(mdes), (name, refusal)


def test_f7_the_four_by_four_pair_separates_the_floor_from_q_and_equality_passes() -> None:
    """Sixteen cells at N=32, 128 units per arm per group: MDE 0.2032 at ``q/4`` (refused at the
    default) and 0.1717 at ``q`` (would pass) -- the one shape where the two thresholds part. At
    ``max_group_mde`` equal to the recomputed MDE the grouping is admitted (S23 W3's equality).
    ``y`` has the same shape and is refused too, so the default falls to the whole grid."""
    cells = four_by_four_cells()
    a, b = raw_frame("four-a", cells), raw_frame("four-b", cells)
    types = {"x": "continuous", "y": "continuous"}
    ma, mb = manifest("four-a", SALT, types), manifest("four-b", SALT, types)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="mcnemar_bh")
    at_floor = diff_mod.mde_two_proportion(0.5, 128, 128, alpha=multi.q / 4)
    at_q = diff_mod.mde_two_proportion(0.5, 128, 128, alpha=multi.q)
    assert at_q < EXPECTED_DEFAULT_MAX_GROUP_MDE < at_floor, (at_q, at_floor)
    refused = grown(a, b, multi, ma, mb, n_permutations=50, seed=GOLDEN_SEED).grouping
    assert [(r.key, r.reason, r.n_groups, r.n_resolvable_groups) for r in refused.refused] == [("x", "underpowered", 4, 0), ("y", "underpowered", 4, 0)]
    assert (refused.key, refused.resolved_by) == (EXPECTED_WHOLE_GRID_KEY, "whole_grid")
    admitted = grown(a, b, multi, ma, mb, n_permutations=50, seed=GOLDEN_SEED, max_group_mde=at_floor).grouping
    assert (admitted.key, admitted.resolved_by, admitted.refused, admitted.n_resolvable_groups, admitted.max_group_mde) == ("x", "axis", (), 4, at_floor)


def test_f7_the_ragged_pair_has_one_resolvable_group_and_is_refused() -> None:
    """Sizes 20, 1, 1, 1 at N=32 on ``fam``: the big family resolves at ``q/4`` (0.0928) and the
    three singletons do not (0.3780), so exactly one resolves and the grouping is refused --
    "at least two" told from "at least one". Every group on both substrates is equal-sized, so
    only this fixture reaches the aggregation rule."""
    cells = ragged_cells()
    a, b = raw_frame("rag-a", cells), raw_frame("rag-b", cells)
    ma, mb = manifest("rag-a", SALT, {"fam": "categorical"}), manifest("rag-b", SALT, {"fam": "categorical"})
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="mcnemar_bh")
    assert diff_mod.mde_two_proportion(0.5, 640, 640, alpha=multi.q / 4) <= EXPECTED_DEFAULT_MAX_GROUP_MDE < diff_mod.mde_two_proportion(0.5, 32, 32, alpha=multi.q / 4)
    grouping = grown(a, b, multi, ma, mb, n_permutations=50, seed=GOLDEN_SEED).grouping
    assert [(r.key, r.rung, r.reason, r.n_groups, r.n_resolvable_groups) for r in grouping.refused] == [("fam", "axis", "underpowered", 4, 1)]
    assert (grouping.key, grouping.resolved_by) == (EXPECTED_WHOLE_GRID_KEY, "whole_grid")


def test_f7_the_grouping_is_a_function_of_shape_and_reads_no_delta(axes: dict[str, Any], axes_trees: Any) -> None:
    """The axes pair and its identical twin have the same shape and different deltas (forty
    discordant pairs against none): their ``Grouping`` payloads are byte-identical. That is the
    pre-registration discipline in fixture form -- admitted or refused before any delta is read."""
    twin = raw_frame("axes-b", axes_cells(False))
    multi = quiet_multi_diff(axes["a"], twin, axes["ma"], axes["mb"], events=("fail",), method="mcnemar_bh")
    identical = grown(axes["a"], twin, multi, axes["ma"], axes["mb"], n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    _, moved = axes_trees["mcnemar_bh"]
    assert float(moved.root.units["delta"].abs().sum()) > 0 and float(identical.root.units["delta"].abs().sum()) == 0
    assert json_bytes(identical.grouping.to_json()) == json_bytes(moved.grouping.to_json())


# ---------- F8: the override ----------


def test_f8_the_offered_value_pasted_back_admits_the_refused_grouping(axes: dict[str, Any]) -> None:
    """The spec's 0.37 cannot admit ``task`` here (the group MDE is the cap 0.5000 at N=8, the
    spec's own section 6 number; 0.37 is S18's value at N=32 -- module docstring). What is pinned
    is the property 0.37 stood for: the value the refusal offers, pasted back, admits the grouping
    (rounding up, S23's ``_offered_override``), and an explicit larger value admits it without
    ``--by`` and is carried on the structure."""
    multi = quiet_multi_diff(axes["a"], axes["b"], axes["ma"], axes["mb"], events=("fail",), method="mcnemar_bh")
    offered = grown(axes["a"], axes["b"], multi, axes["ma"], axes["mb"], by="task", n_permutations=50, seed=GOLDEN_SEED).grouping.refused[0].offered_max_group_mde
    pasted = grown(axes["a"], axes["b"], multi, axes["ma"], axes["mb"], by="task", n_permutations=50, seed=GOLDEN_SEED, max_group_mde=offered).grouping
    assert (pasted.key, pasted.resolved_by, pasted.refused, pasted.max_group_mde) == ("task", "requested", (), offered)
    explicit = grown(axes["a"], axes["b"], multi, axes["ma"], axes["mb"], n_permutations=50, seed=GOLDEN_SEED, max_group_mde=0.6).grouping
    assert (explicit.key, explicit.resolved_by, explicit.refused, explicit.max_group_mde, explicit.n_resolvable_groups) == ("task", "axis", (), 0.6, N_TASKS)


def test_f8_the_block_and_the_json_carry_the_accepted_value(synth_root: Path) -> None:
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--max-group-mde", "0.6"])
    assert code == 0 and err == "", (out, err)
    block = fault_lines_block(out)
    assert block and g(0.6) in numeric_tokens(block[0]) and "task" in block[0], block[:1]
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--max-group-mde", "0.6", "--format", "json"])
    assert code == 0 and err == "", (out, err)
    grouping = json.loads(out)["tree"]["grouping"]
    assert (grouping["max_group_mde"], grouping["key"], grouping["refused"]) == (0.6, "task", [])


def test_f8_the_offered_value_is_rounded_up_where_nearest_would_refuse() -> None:
    """S23's trap one level down. The axes pair's cap 0.5000 is four-decimal exact, so rounding
    to nearest survives F8 there; the 4 x 4 pair's 0.203231 does not: the refusal offers 0.2033,
    which admits the grouping when pasted back, while 0.2032 refuses it again."""
    cells = four_by_four_cells()
    a, b = raw_frame("four-a", cells), raw_frame("four-b", cells)
    types = {"x": "continuous", "y": "continuous"}
    ma, mb = manifest("four-a", SALT, types), manifest("four-b", SALT, types)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="mcnemar_bh")
    refusal = grown(a, b, multi, ma, mb, n_permutations=50, seed=GOLDEN_SEED).grouping.refused[0]
    mde = diff_mod.mde_two_proportion(0.5, 128, 128, alpha=multi.q / 4)
    assert refusal.key == "x" and refusal.offered_max_group_mde == second_smallest_rounded_up([mde] * 4)
    assert refusal.offered_max_group_mde > mde > round(mde, 4)
    assert grown(a, b, multi, ma, mb, n_permutations=50, seed=GOLDEN_SEED, max_group_mde=refusal.offered_max_group_mde).grouping.key == "x"
    assert grown(a, b, multi, ma, mb, n_permutations=50, seed=GOLDEN_SEED, max_group_mde=round(mde, 4)).grouping.key == EXPECTED_WHOLE_GRID_KEY


@pytest.mark.parametrize("value", (0, 1, -0.1, 1.5, "0.3"), ids=repr)
def test_f8_an_out_of_range_override_is_refused_before_any_draw_from_tree_and_from_resolve_grouping(go1: Any, go1_trees: Any, value: Any) -> None:
    """S23 W6 one level down: ``0 < x < 1``, a non-float refused too, ``TreeError`` from both
    entry points, before a permutation is drawn (O13's cost pin)."""
    a, b, ma, mb = go1
    multi, base = go1_trees["fisher_bh"]
    t = tree()
    started = time.perf_counter()
    with pytest.raises(t.TreeError):
        grown(a, b, multi, ma, mb, n_permutations=REFUSAL_PERMUTATIONS, seed=GOLDEN_SEED, max_group_mde=value)
    with pytest.raises(t.TreeError):
        t.resolve_grouping(None, manifest_a=ma, manifest_b=mb, units=base.root.units, q=multi.q, max_group_mde=value)
    assert time.perf_counter() - started < REFUSAL_BUDGET_SECONDS


@pytest.mark.parametrize("value", ("0", "1", "-0.1", "1.5"))
def test_f8_the_cli_maps_an_out_of_range_override_to_exit_two(synth_root: Path, value: str) -> None:
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--max-group-mde", value])
    assert code == 2, (out, err)
    assert "error:" in err and "Traceback" not in out + err, err
    assert "usage:" not in err and "unrecognized" not in err, err


def test_f8_the_range_check_lives_in_tree_py_and_not_in_cli_py() -> None:
    """**The rule, in prose.** The CLI parses a float and decides nothing statistical (section 8
    trap 13, M6's ``0 < q < 1``, S23's ``check_power``). No ``ast.Compare`` in ``cli.py`` whose
    subtree names ``max_group_mde``; the refusal is ``tree.py``'s and the runtime tests above
    reach it through both entry points."""
    offenders = []
    for node in ast.walk(parsed(CLI_SOURCE)):
        if not isinstance(node, ast.Compare):
            continue
        mentioned = {child.attr if isinstance(child, ast.Attribute) else child.id for child in ast.walk(node) if isinstance(child, (ast.Attribute, ast.Name))}
        if "max_group_mde" in mentioned:
            offenders.append(node.lineno)
    assert offenders == [], offenders


# ---------- F9: one group is not a level ----------


def test_f9_by_grid_on_go1_is_one_group_and_not_a_level(go1: Any) -> None:
    a, b, ma, mb = go1
    multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method="mcnemar_bh")
    result = grown(a, b, multi, ma, mb, by=EXPECTED_WHOLE_GRID, n_permutations=200, seed=GOLDEN_SEED)
    grouping, fault_lines = result.grouping, result.fault_lines
    assert (grouping.key, grouping.resolved_by, grouping.requested, grouping.n_groups, grouping.labels) == (EXPECTED_WHOLE_GRID_KEY, "whole_grid", EXPECTED_WHOLE_GRID, 1, ("all",))
    assert result.root.rejects is True
    assert (fault_lines.tested, fault_lines.reason, fault_lines.n_groups, fault_lines.n_rejected_groups, fault_lines.rejected_groups) == (False, "one_group", 1, 0, ())
    assert len(fault_lines.groups) == 1
    only = fault_lines.groups[0]
    assert (only.p_group, only.q_group, only.rejects, only.p_location, only.p_dispersion) == (None, None, None, None, None)
    assert only.n_cells == result.root.n_cells == len(only.cells) == len(grouping.groups["all"])


def test_f9_the_one_value_pair_refuses_temp_as_one_group_and_falls_to_the_whole_grid() -> None:
    """Four cells over ``task`` with ``temp`` at one value, N=8, arm a all ``ok`` and arm b all
    ``fail`` so the root rejects and the only untested reason left is the level's shape.
    ``task`` refuses at the cap (next: the next axis); ``temp`` refuses as ``one_group`` (next:
    the task-family rung, which contributes no row because ``task`` is already in the chain)."""
    a, b = raw_frame("one-a", one_value_cells(False)), raw_frame("one-b", one_value_cells(True))
    ma, mb = manifest("one-a", SALT, AXES_TYPES_TASK_FIRST), manifest("one-b", SALT, AXES_TYPES_TASK_FIRST)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="mcnemar_bh")
    result = grown(a, b, multi, ma, mb, n_permutations=200, seed=GOLDEN_SEED)
    grouping = result.grouping
    assert [(r.key, r.rung, r.reason, r.next_rung, r.n_groups) for r in grouping.refused] == [("task", "axis", "underpowered", "axis", 4), ("temp", "axis", "one_group", "task_family", 1)]
    assert (grouping.key, grouping.resolved_by, grouping.requested, grouping.n_groups) == (EXPECTED_WHOLE_GRID_KEY, "whole_grid", None, 1)
    assert result.root.rejects is True
    assert (result.fault_lines.tested, result.fault_lines.reason) == (False, "one_group")


# ---------- F10: the task-family rung is reachable ----------


def test_f10_the_imported_shape_pair_reaches_the_task_family_rung() -> None:
    """Configs carry ``task_id`` and ``tool_fail_rate``; the manifests declare only
    ``tool_fail_rate``. The axis rung refuses it (eighty groups of one cell, MDE 0.4597 at
    ``q/80``); the task-family rung reads the configs, finds ``task_id`` (``task_family`` is
    absent) and resolves eight groups of 320 units per arm (0.1396 at ``q/8``). The rung is
    vacuous on every store this project has; this fixture is what keeps it from being dead code."""
    cells = imported_cells()
    a, b = raw_frame("imp-a", cells), raw_frame("imp-b", cells)
    ma, mb = manifest("imp-a", SALT, {"tool_fail_rate": "continuous"}), manifest("imp-b", SALT, {"tool_fail_rate": "continuous"})
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="mcnemar_bh")
    assert diff_mod.mde_two_proportion(0.5, 32, 32, alpha=multi.q / 80) > EXPECTED_DEFAULT_MAX_GROUP_MDE > diff_mod.mde_two_proportion(0.5, 320, 320, alpha=multi.q / 8)
    grouping = grown(a, b, multi, ma, mb, n_permutations=50, seed=GOLDEN_SEED).grouping
    assert [(r.key, r.rung, r.reason, r.next_rung, r.n_groups, r.n_resolvable_groups) for r in grouping.refused] == [("tool_fail_rate", "axis", "underpowered", "task_family", 80, 0)]
    assert (grouping.key, grouping.resolved_by, grouping.n_groups, grouping.group_sizes) == ("task_id", "task_family", 8, (10,) * 8)
    assert grouping.labels == tuple(f"T{t}" for t in range(8))


def test_f10_the_axes_pair_carries_no_task_family_row(axes_trees: Any) -> None:
    """``task`` was refused at the axis rung, so the task-family rung skips it and adds nothing."""
    for method, (_, result) in axes_trees.items():
        assert [r.rung for r in result.grouping.refused] == ["axis"], (method, result.grouping.refused)


# ---------- F11: the root does not move ----------


@pytest.mark.parametrize("method", METHODS)
def test_f11_the_root_inside_the_tree_is_byte_equal_to_omnibus_on_go1(go1: Any, go1_trees: Any, method: str) -> None:
    """One draw (draft ADR-058): ``tree(...).root`` is ``omnibus(...)`` on the same inputs and
    knobs, JSON byte for byte and ``units`` frame for frame."""
    a, b, _, _ = go1
    multi, result = go1_trees[method]
    root = tree().omnibus(a, b, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    assert json_bytes(result.root.to_json()) == json_bytes(root.to_json())
    pd.testing.assert_frame_equal(result.root.units, root.units)


def test_f11_the_root_does_not_move_on_the_synthetic_pairs(axes: dict[str, Any], axes_trees: Any, discordant_trees: Any, three_outcome: Any) -> None:
    t = tree()
    for method, (multi, result) in axes_trees.items():
        root = t.omnibus(axes["a"], axes["b"], multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
        assert json_bytes(result.root.to_json()) == json_bytes(root.to_json()), ("axes", method)
    cells_a, cells_b = discordant_cells()
    da, db = raw_frame("disc-a", cells_a), raw_frame("disc-b", cells_b)
    for method, (multi, result) in discordant_trees.items():
        root = t.omnibus(da, db, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
        assert json_bytes(result.root.to_json()) == json_bytes(root.to_json()), ("discordant", method)
    a, b, ma, mb = three_outcome
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(a, b, ma, mb, events=("x", "y"), method=method)
        result = grown(a, b, multi, ma, mb, n_permutations=500, seed=GOLDEN_SEED)
        root = t.omnibus(a, b, multi, n_permutations=500, seed=GOLDEN_SEED)
        assert json_bytes(result.root.to_json()) == json_bytes(root.to_json()), ("three-outcome", method)
        pd.testing.assert_frame_equal(result.root.units, root.units)


# ---------- F12: group statistics, recomputed ----------


def test_f12_group_statistics_are_recomputed_from_units_and_the_partition_on_every_fixture(every_tree: Any) -> None:
    """A mean over ``C_g`` and an RMS over ``C_g``, from ``units.delta`` on the rows whose hash is
    in the group and whose event matches. A builder who slices the root's *statistics* (a mean
    over ``C``) instead of the deltas fails here alone. Counts: ``n_cells``, the informative and
    uninformative split, the discordant sum under pair swap and ``None`` under arm label."""
    for name, _, result in every_tree:
        grouping, units, root, fault_lines = result.grouping, result.root.units, result.root, result.fault_lines
        assert len(fault_lines.groups) == grouping.n_groups == fault_lines.n_groups, name
        for index, label in enumerate(grouping.labels):
            group = fault_lines.groups[index]
            hashes = list(grouping.groups[label])
            assert (group.label, list(group.cells), group.n_cells) == (label, sorted(hashes), len(hashes)), (name, label)
            assert set(group.location) == set(group.dispersion) == set(root.events), (name, label)
            for event in root.events:
                deltas = group_rows(units, event, hashes)["delta"].to_numpy(dtype=float)
                assert len(deltas) == group.n_cells, (name, label, event)
                assert abs(group.location[event] - float(np.mean(deltas))) <= 1e-12, (name, label, event)
                assert abs(group.dispersion[event] - math.sqrt(float(np.mean(deltas * deltas)))) <= 1e-12, (name, label, event)
            assert group.n_informative_cells + group.n_uninformative_cells == group.n_cells, (name, label)
            assert 0 <= group.n_informative_cells <= group.n_cells, (name, label)
        assert sum(gr.n_informative_cells for gr in fault_lines.groups) == root.n_informative_cells, name
        if root.scheme == "pair_swap":
            assert sum(gr.n_discordant for gr in fault_lines.groups) == root.n_discordant, name
        else:
            assert all(gr.n_discordant is None for gr in fault_lines.groups), name


@PROPERTY_SETTINGS
@given(case=small_two_key_pairs())
def test_f12_and_f13_the_recompute_and_the_p_form_hold_over_small_two_key_pairs(case: Any) -> None:
    multi, result = property_tree(case)
    grouping, units, root, fault_lines = result.grouping, result.root.units, result.root, result.fault_lines
    permutations = root.n_permutations
    for index, label in enumerate(grouping.labels):
        group = fault_lines.groups[index]
        deltas = group_rows(units, "fail", grouping.groups[label])["delta"].to_numpy(dtype=float)
        assert abs(group.location["fail"] - float(np.mean(deltas))) <= 1e-12
        assert abs(group.dispersion["fail"] - math.sqrt(float(np.mean(deltas * deltas)))) <= 1e-12
        if not fault_lines.tested:
            assert (group.p_group, group.q_group, group.rejects, group.p_location, group.p_dispersion) == (None, None, None, None, None)
            continue
        for p in (group.p_group, group.p_location["fail"], group.p_dispersion["fail"]):
            c = round(p * (permutations + 1)) - 1
            assert 0 <= c <= permutations and abs(p - (1 + c) / (permutations + 1)) <= 1e-12, p
    assert fault_lines.tested == (root.rejects and grouping.n_groups >= 2)


# ---------- F13: same draws, from the surface ----------


def test_f13_on_the_bh_pair_the_weak_groups_p_equals_the_roots_bit_for_bit(bh_trees: Any) -> None:
    """Section 0.7: the other nineteen groups contribute exactly zero under every pair-swap
    exchange, so the root statistic is ``g00``'s divided by a constant and the two p-values are
    the same count over the same draws. Measured equal at seeds 0-2 and at four sizes of the weak
    group. A Level 2 that drew its own ``(C_g, W)`` block from the same seed gets different bits
    and fails here alone; O16 does not see it because ``_draw`` is still the one site."""
    multi, result = bh_trees["mcnemar_bh"]
    groups = result.fault_lines.groups
    assert result.root.rejects is True and result.fault_lines.tested is True
    assert groups[0].label == "g00"
    assert groups[0].p_group == result.root.p_omnibus
    assert all(gr.p_group == 1.0 for gr in groups[1:])


def test_f13_every_group_p_has_the_phipson_smyth_form_on_every_tested_fixture(every_tree: Any) -> None:
    """O3's recovery one level down: ``(1 + c) / (B + 1)`` for an integer ``0 <= c <= B`` on
    ``p_group`` and every per-event ``p_location`` and ``p_dispersion``."""
    for name, _, result in every_tree:
        if not result.fault_lines.tested:
            continue
        permutations = result.root.n_permutations
        for group in result.fault_lines.groups:
            for p in (group.p_group, *group.p_location.values(), *group.p_dispersion.values()):
                c = round(p * (permutations + 1)) - 1
                assert 0 <= c <= permutations, (name, group.label, p)
                assert abs(p - (1 + c) / (permutations + 1)) <= 1e-12, (name, group.label, p)
                assert 1.0 / (permutations + 1) <= p <= 1.0, (name, group.label, p)


def test_the_group_p_is_the_calibrated_count_and_not_the_bare_minimum_of_its_p_values() -> None:
    """**Not a numbered invariant: section 8 trap 10 pinned at group level.** On the BH pair every
    weak cell holds one discordant pair, so the group's dispersion is invariant under every
    exchange and its calibrated p coincides with the bare minimum of its two p-values -- F13's
    bit-equality cannot see a builder who takes the minimum. Here S25's six mid-range cells are
    group ``m`` beside six strong cells as group ``s`` under ``fisher_bh`` (arm b on another
    salt, as S25's guard); the root rejects through ``s``, ``m``'s two p-values sit mid-range
    (0.65 and 0.96 at B=1000, seed 0) and its ``p_group`` is the calibrated count, 0.84,
    strictly above the minimum by 0.19. Under pair swap the two extreme sets coincide on so few
    discordant pairs (S25), so the strict half is asserted under arm label only."""
    mid = (6, 3, 6, 3, 6, 4)
    cells_a = {(("grp", "m"), ("cell", f"c{i}")): ["fail"] * 4 + ["ok"] * 28 for i in range(6)}
    cells_b = {(("grp", "m"), ("cell", f"c{i}")): ["fail"] * k + ["ok"] * (32 - k) for i, k in enumerate(mid)}
    for i in range(6):
        cells_a[(("grp", "s"), ("cell", f"c{i}"))] = ["fail"] * 4 + ["ok"] * 28
        cells_b[(("grp", "s"), ("cell", f"c{i}"))] = ["fail"] * 20 + ["ok"] * 12
    a, b = raw_frame("mid-a", cells_a), raw_frame("mid-b", cells_b)
    types = {"grp": "categorical", "cell": "categorical"}
    ma, mb = manifest("mid-a", SALT, types), manifest("mid-b", OTHER_SALT, types)
    multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method="fisher_bh")
    result = grown(a, b, multi, ma, mb, n_permutations=1000, seed=GOLDEN_SEED)
    assert result.root.rejects is True and result.fault_lines.tested is True and result.grouping.key == "grp"
    weak, strong = result.fault_lines.groups[0], result.fault_lines.groups[1]
    assert (weak.label, strong.label) == ("m", "s") and strong.p_group == 1.0 / 1001
    assert 0.2 < weak.p_location["fail"] < 0.99 and 0.2 < weak.p_dispersion["fail"] < 0.99, (weak.p_location, weak.p_dispersion)
    smallest = min(weak.p_location["fail"], weak.p_dispersion["fail"])
    assert weak.p_group >= smallest
    assert weak.p_group > smallest, (weak.p_group, smallest)


# ---------- F14: BH across all groups ----------


def test_f14_on_the_bh_pair_the_raw_p_is_below_q_and_bh_across_all_twenty_does_not_reject(bh_trees: Any) -> None:
    """Section 0.7 under ``mcnemar_bh``: the root rejects, ``g00``'s raw ``p_group`` is below
    ``q``, and BH across twenty groups puts ``q_group`` at ``20 p`` above ``q``. BH over the one
    informative group, and no correction at all, would both reject it; the test says so from the
    same array. **The arm-label twin of this shape does not exist** (module docstring, step zero
    item 4), so F14's fixture clause is asserted under ``mcnemar_bh`` only; the two-group
    arm-label guard below covers "no correction" under arm label."""
    multi, result = bh_trees["mcnemar_bh"]
    fault_lines = result.fault_lines
    ps = np.array([gr.p_group for gr in fault_lines.groups])
    assert result.root.rejects is True and fault_lines.tested is True and fault_lines.n_groups == 20
    assert fault_lines.groups[0].p_group < multi.q
    expected = diff_mod.bh(ps, multi.q)
    assert fault_lines.groups[0].q_group == expected[0]
    assert fault_lines.groups[0].q_group >= multi.q and fault_lines.groups[0].rejects is False
    assert (fault_lines.n_rejected_groups, fault_lines.rejected_groups) == (0, ())
    assert fault_lines.n_degenerate_groups == 19
    assert diff_mod.bh(ps[:1], multi.q)[0] < multi.q


def test_f14_q_group_is_bh_over_all_groups_and_rejects_is_strict_on_every_tested_fixture(every_tree: Any) -> None:
    """``m = G``, degenerate groups included; ``rejects == (q_group < q)``; the rejected labels in
    label order. Where a fixture has degenerate groups (Go1 push, the McNemar BH pair) BH over the
    informative groups alone gives a different ``q_group`` somewhere, and the test says so."""
    for name, multi, result in every_tree:
        fault_lines = result.fault_lines
        if not fault_lines.tested:
            continue
        ps = np.array([gr.p_group for gr in fault_lines.groups])
        expected = diff_mod.bh(ps, multi.q)
        for index, group in enumerate(fault_lines.groups):
            assert group.q_group == expected[index], (name, group.label)
            assert group.rejects == (group.q_group < multi.q) and type(group.rejects) is bool, (name, group.label)
        rejected = tuple(gr.label for gr in fault_lines.groups if gr.rejects)
        assert (fault_lines.n_rejected_groups, fault_lines.rejected_groups) == (len(rejected), rejected), name
        informative = np.array([not gr.degenerate for gr in fault_lines.groups])
        if fault_lines.n_degenerate_groups > 0:
            assert not np.array_equal(diff_mod.bh(ps[informative], multi.q), expected[informative]), name


def test_the_two_group_arm_label_variant_leaves_the_weak_group_unrejected_after_bh(bh_trees: Any) -> None:
    """**Not a numbered invariant: "no correction" under arm label.** The one-group shape has no
    arm-label twin (step zero item 4); with ``g01`` strong the root rejects through it while
    ``g00``'s raw p sits at 0.0215 -- 8.3 sd above ``q/20`` and 12.4 sd below ``q`` at B=4000 --
    so no correction rejects ``g00`` and BH across twenty (``q_group`` 0.215) does not. Every
    group is informative under arm label, so ``m = informative`` is not visible here; Go1 push
    and the McNemar BH pair see it."""
    multi, result = bh_trees["fisher_two_group"]
    fault_lines = result.fault_lines
    floor = 1.0 / (GOLDEN_PERMUTATIONS + 1)
    assert result.root.rejects is True and fault_lines.tested is True and fault_lines.n_degenerate_groups == 0
    weak, strong = fault_lines.groups[0], fault_lines.groups[1]
    assert (weak.label, strong.label) == ("g00", "g01")
    assert strong.p_group == floor and strong.rejects is True
    assert multi.q / 20 < weak.p_group < multi.q, weak.p_group
    ps = np.array([gr.p_group for gr in fault_lines.groups])
    assert weak.q_group == diff_mod.bh(ps, multi.q)[0] >= multi.q and weak.rejects is False
    assert (fault_lines.n_rejected_groups, fault_lines.rejected_groups) == (1, ("g01",))
    assert all(gr.p_group == 1.0 and gr.degenerate is False for gr in fault_lines.groups[2:])


# ---------- F15: the gate ----------


def test_f15_the_identical_pair_is_not_tested_and_says_why_under_both_methods(synth_root: Path) -> None:
    """The axes shape with both arms the moved frame: ``temp`` resolves to two groups, the root
    does not reject, and the level is stated with every p ``None`` and every count present. A
    builder who tests regardless fails here alone. Identical arms are degenerate everywhere
    under pair swap; under arm label the twenty mixed cells of ``temp = 0.0`` stay informative
    (O7's split at group level), so the degenerate count is 2 or 1 by scheme and is asserted."""
    for method in TWO_SCHEMES:
        _, result = store_tree(synth_root, "same-a", "same-b", events=("fail",), method=method, n_permutations=500, seed=GOLDEN_SEED)
        grouping, fault_lines = result.grouping, result.fault_lines
        assert result.root.rejects is False, method
        assert (fault_lines.tested, fault_lines.reason, fault_lines.n_rejected_groups, fault_lines.rejected_groups) == (False, "root_not_rejected", 0, ()), method
        assert (grouping.key, grouping.resolved_by, grouping.group_sizes) == ("temp", "axis", (N_TASKS, N_TASKS)), method
        expected_degenerate = 2 if result.root.scheme == "pair_swap" else 1
        assert fault_lines.n_degenerate_groups == expected_degenerate and len(fault_lines.groups) == 2, method
        assert fault_lines.groups[1].degenerate is True, method
        for group in fault_lines.groups:
            assert (group.p_location, group.p_dispersion, group.p_group, group.q_group, group.rejects) == (None, None, None, None, None), (method, group.label)
            assert isinstance(group.n_informative_cells, int) and isinstance(group.mde, float) and type(group.degenerate) is bool, (method, group.label)
            assert group.location["fail"] == 0.0 and group.dispersion["fail"] == 0.0, (method, group.label)


def test_f15_the_three_cell_identical_pair_states_the_roots_reason_first() -> None:
    """S25's ``same-a``/``same-b`` restated. Its only axis refuses at the cap, so the grouping
    collapses to ``whole_grid``; the root did not reject either. **Root-first precedence**, the
    convention this oracle fixes (module docstring): the reason is the root's."""
    cells = three_cell_identical()
    a, b = raw_frame("same3-a", cells), raw_frame("same3-b", cells)
    ma, mb = manifest("same3-a", SALT, {"task": "categorical"}), manifest("same3-b", SALT, {"task": "categorical"})
    for method in TWO_SCHEMES:
        multi = quiet_multi_diff(a, b, ma, mb, events=("fail",), method=method)
        result = grown(a, b, multi, ma, mb, n_permutations=200, seed=GOLDEN_SEED)
        assert result.root.rejects is False and result.grouping.key == EXPECTED_WHOLE_GRID_KEY, method
        assert (result.fault_lines.tested, result.fault_lines.reason) == (False, "root_not_rejected"), method
        assert result.fault_lines.groups[0].p_group is None, method


def test_f15_the_block_prints_the_grouping_line_and_not_tested_and_no_p(synth_root: Path) -> None:
    """Every numeric token on an untested group line is a ``:g`` rendering of one of that group's
    count or design fields, or its label; a p has nowhere to come from."""
    _, result = store_tree(synth_root, "same-a", "same-b", events=("fail",), method="fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "same-a", "same-b", "--event", "fail"])
    assert code == 0 and err == "", (out, err)
    block = fault_lines_block(out)
    assert block, out
    assert "temp" in block[0] and "axis" in block[0], block[0]
    assert "not tested" in "\n".join(block[1:]), block
    group_lines = block[-result.grouping.n_groups :]
    for group, line in zip(result.fault_lines.groups, group_lines, strict=True):
        assert group.label in line, (group.label, line)
        allowed = {group.label, g(group.n_cells), g(group.n_informative_cells), g(group.n_uninformative_cells), g(group.n_a), g(group.n_b), g(group.mde)}
        if group.n_discordant is not None:
            allowed.add(g(group.n_discordant))
        assert set(numeric_tokens(line)) <= allowed, (line, sorted(set(numeric_tokens(line)) - allowed))


# ---------- F16: degeneracy at group level ----------


def test_f16_degenerate_is_zero_informative_cells_and_a_degenerate_group_never_rejects(every_tree: Any) -> None:
    for name, _, result in every_tree:
        fault_lines = result.fault_lines
        assert fault_lines.n_degenerate_groups == sum(gr.degenerate for gr in fault_lines.groups), name
        for group in fault_lines.groups:
            assert group.degenerate == (group.n_informative_cells == 0) and type(group.degenerate) is bool, (name, group.label)
            if fault_lines.tested and group.degenerate:
                assert group.p_group == 1.0 and group.rejects is False, (name, group.label)


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_f16_go1_by_push_has_five_degenerate_groups_and_two_at_p_one_that_are_not(go1_push: Any, method: str) -> None:
    """O7's split one level up. Push 150/170/180/190/200: every robot fell in both arms in every
    episode, no exchange can move them. Push 140 and 160: one informative cell each, p exactly 1,
    **not** degenerate. **The spec says their delta is exactly zero; it is -1/32** (one
    discordant pair, whose sign flip leaves ``|mean|`` and RMS unchanged, so every permutation
    ties the observed statistic). A builder who flags degeneracy from ``p == 1`` fails on 140 and
    160 alone; one who flags it from ``delta == 0`` is not caught here -- the identical pair
    under arm label (F15) and the strong BH variant (F16 below) catch that one."""
    _, result = go1_push[method]
    fault_lines = result.fault_lines
    by_label = {gr.label: gr for gr in fault_lines.groups}
    assert fault_lines.n_degenerate_groups == 5
    assert tuple(gr.label for gr in fault_lines.groups if gr.degenerate) == GO1_PUSH_DEGENERATE
    for label in GO1_PUSH_ONE_INFORMATIVE:
        group = by_label[label]
        assert (group.n_informative_cells, group.degenerate, group.p_group, group.rejects) == (1, False, 1.0, False), label
        assert group.location["fell"] != 0.0, label
    assert sum(gr.p_group == 1.0 for gr in fault_lines.groups) == 7


def test_f16_the_bh_pairs_nineteen_are_degenerate_under_pair_swap_and_informative_at_p_one_under_arm_label(bh_trees: Any) -> None:
    """Under pair swap the nineteen identical groups are degenerate (no pair differs); under arm
    label their mixed outcomes make every cell informative and the observed statistic is the
    minimum of its own distribution, so p is exactly 1 and ``degenerate`` is ``False``. The
    spec's clause is asserted on the strong variant under ``fisher_bh``, where the root rejects
    (on the spec's shape it does not, and every p is ``None`` -- module docstring)."""
    _, pair_swap = bh_trees["mcnemar_bh"]
    assert pair_swap.fault_lines.n_degenerate_groups == 19 and pair_swap.fault_lines.groups[0].degenerate is False
    assert all(gr.degenerate is True and gr.p_group == 1.0 for gr in pair_swap.fault_lines.groups[1:])
    _, arm_label = bh_trees["fisher_strong"]
    assert arm_label.root.rejects is True and arm_label.fault_lines.tested is True
    assert arm_label.fault_lines.n_degenerate_groups == 0
    assert all(gr.degenerate is False and gr.n_informative_cells == 10 and gr.p_group == 1.0 and gr.rejects is False for gr in arm_label.fault_lines.groups[1:])
    assert arm_label.fault_lines.groups[0].p_group == 1.0 / (GOLDEN_PERMUTATIONS + 1)


# ---------- F17: golden, Go1 ----------


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_f17_golden_go1_by_push_rejects_exactly_the_twelve_groups_up_to_120(go1_push: Any, method: str) -> None:
    """Step zero item 6. Twelve rejecting groups all at the floor; the eight others at p >= 0.13
    or exactly 1, so their ``q_group`` is above ``q`` with room."""
    multi, result = go1_push[method]
    fault_lines = result.fault_lines
    floor = 1.0 / (GOLDEN_PERMUTATIONS + 1)
    assert (result.grouping.requested, result.grouping.resolved_by, result.grouping.key) == ("push_pct_bw", "requested", "push_pct_bw")
    assert result.root.rejects is True and fault_lines.tested is True
    assert (fault_lines.n_rejected_groups, fault_lines.rejected_groups) == (12, GO1_PUSH_REJECTED)
    for group in fault_lines.groups:
        if group.label in GO1_PUSH_REJECTED:
            assert group.p_group == floor and group.rejects is True, group.label
        else:
            assert group.q_group > multi.q and group.rejects is False, group.label


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_f17_golden_go1_by_mu_rejects_the_fifteen_at_the_floor_and_not_095(go1_trees: Any, method: str) -> None:
    """``mu = 0.95`` sits at p 0.075 (Fisher) / 0.103 (McNemar), six Monte Carlo standard
    deviations from ``q`` and still the one row no golden pins to a byte: a range on the count."""
    multi, result = go1_trees[method]
    fault_lines = result.fault_lines
    floor = 1.0 / (GOLDEN_PERMUTATIONS + 1)
    by_label = {gr.label: gr for gr in fault_lines.groups}
    assert result.grouping.resolved_by == "axis" and fault_lines.tested is True
    for label in GO1_MU_AT_FLOOR:
        assert by_label[label].p_group == floor and by_label[label].rejects is True, label
    assert 15 <= fault_lines.n_rejected_groups <= 19
    assert by_label[GO1_MU_NOT_REJECTED].q_group > multi.q and by_label[GO1_MU_NOT_REJECTED].rejects is False


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_f17_every_flat_rejection_lies_inside_a_rejecting_group_on_both_axes(go1_trees: Any, go1_push: Any, method: str) -> None:
    """The 60 (Fisher) / 55 (McNemar) flat rejections, recomputed from ``cells.q``, are a subset
    of the union of the rejecting groups' cells on both axes. **The spec's fixture-limit note is
    wrong in the safe direction**: it says Go1 cannot show a group rejecting with no flat
    rejection inside it, but by ``mu`` the groups 0.7 and 0.8 reject at the floor with none
    inside under both methods (0.85 and 0.9 too under Fisher); the last assertion records that.
    F18's axes pair is still the clean fixture, where no leaf is below 0.46 before correction."""
    multi, by_mu = go1_trees[method]
    _, by_push = go1_push[method]
    rejected = flat_rejections(multi, "fell")
    assert len(rejected) == GO1_FLAT_REJECTIONS[method]
    for result in (by_mu, by_push):
        covered: set[str] = set()
        for label in result.fault_lines.rejected_groups:
            covered |= set(result.grouping.groups[label])
        assert rejected <= covered, (result.grouping.key, rejected - covered)
    empty_but_rejecting = [label for label in by_mu.fault_lines.rejected_groups if not (rejected & set(by_mu.grouping.groups[label]))]
    assert "0.7" in empty_but_rejecting and "0.8" in empty_but_rejecting, empty_but_rejecting


# ---------- F18: the group sees what no leaf can ----------


def test_f18_the_temp_zero_group_rejects_while_the_flat_family_rejects_nothing_inside_it(axes_trees: Any) -> None:
    """The plan's Level 2 claim in fixture form, under both schemes. The leaf side is asserted
    first from ``multi_diff``'s own ``cells``: no rejection anywhere, and no raw p inside
    ``temp = 0.0`` below ``q`` even before correction (0.5 under McNemar, 0.4667 under Fisher).
    ``temp = 0.7`` is identical across arms and all ``ok``: degenerate under both schemes here."""
    floor = 1.0 / (GOLDEN_PERMUTATIONS + 1)
    for method, (multi, result) in axes_trees.items():
        grouping, fault_lines = result.grouping, result.fault_lines
        inside = set(grouping.groups["0.0"])
        cells = multi.by_event["fail"].cells
        assert flat_rejections(multi, "fail") == set(), method
        assert float(cells.loc[cells["config_hash"].astype(str).isin(inside), "p"].min()) >= multi.q, method
        by_label = {gr.label: gr for gr in fault_lines.groups}
        assert result.root.rejects is True and fault_lines.tested is True, method
        assert (by_label["0.0"].p_group, by_label["0.0"].rejects, by_label["0.0"].n_informative_cells) == (floor, True, AXES_MOVED_CELLS), method
        assert (by_label["0.7"].degenerate, by_label["0.7"].p_group, by_label["0.7"].rejects) == (True, 1.0, False), method
        assert (fault_lines.n_rejected_groups, fault_lines.rejected_groups) == (1, ("0.0",)), method


def test_f18_the_block_shows_both_groups_with_their_verdicts(synth_root: Path) -> None:
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail"])
    assert code == 0 and err == "", (out, err)
    block = fault_lines_block(out)
    assert len(block) >= 3, block
    zero, seven = block[-2], block[-1]
    assert "0.0" in zero and "rejected" in zero and "not rejected" not in zero, zero
    assert "0.7" in seven and "not rejected" in seven, seven


# ---------- F19: vocabulary and field names ----------


def test_f19_no_detail_reason_or_block_line_uses_the_second_vocabulary(every_tree: Any, go1: Any, synth_root: Path) -> None:
    """Level 2 says which kind of work moved and never where it broke. O19's nine phrases and this
    packet's additions, case-insensitively, on every ``Refusal.detail``, every ``FaultLines.reason``
    and every line of the captured block, with the requested key masked first (``step_kind`` is a
    grouping name the block must echo verbatim -- module docstring). The block quotes the null."""
    a, b, ma, mb = go1
    multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method="mcnemar_bh")
    stubs = [("stub", multi, grown(a, b, multi, ma, mb, by=name, n_permutations=50, seed=GOLDEN_SEED)) for name in EXPECTED_TRACE_GROUPINGS]
    for name, _, result in [*every_tree, *stubs]:
        requested = result.grouping.requested or ""
        for refusal in result.grouping.refused:
            text = refusal.detail.replace(refusal.key, "").replace(requested, "").lower()
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in text, (name, phrase, refusal.detail)
        reason = (result.fault_lines.reason or "").lower()
        for phrase in FORBIDDEN_VOCABULARY:
            assert phrase not in reason, (name, phrase, reason)
    for extra in ((), ("--by", "step_kind"), ("--by", "kind"), ("--by", "grid")):
        for pair in (("axes-a", "axes-b"), ("same-a", "same-b")):
            code, out, err = run_cli(["--store", str(synth_root), "diff", *pair, "--event", "fail", *extra])
            assert code == 0 and err == "", (pair, extra, out, err)
            block = fault_lines_block(out)
            assert block, (pair, extra, out)
            assert f'"{EXPECTED_GROUP_NULL}"' in "\n".join(block), block
            masked = "\n".join(block).replace(extra[1] if extra else "", "").lower()
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in masked, (pair, extra, phrase, block)


def test_f19_no_field_name_and_no_json_key_contains_the_forbidden_substrings(go1_trees: Any, axes_trees: Any) -> None:
    """``level`` and ``interval`` are draft ADR-060's and P4.3's; ``leaf``, ``broke``, ``where``
    and ``step`` are the second vocabulary. Field sets are asserted as supersets of the spec's
    lists so a later packet's defaulted addition to ``TreeResult`` does not trip a frozen test;
    the JSON walk skips the keys of ``config`` dicts and ``groups`` maps, which are user data."""
    import dataclasses

    t = tree()
    for cls, expected in ((t.Refusal, REFUSAL_FIELDS), (t.Grouping, GROUPING_FIELDS), (t.GroupResult, GROUP_RESULT_FIELDS), (t.FaultLines, FAULT_LINES_FIELDS), (t.TreeResult, TREE_RESULT_FIELDS)):
        names = [field.name for field in dataclasses.fields(cls)]
        assert set(names) >= set(expected), (cls.__name__, sorted(set(expected) - set(names)))
        for name in names:
            assert not any(bad in name.lower() for bad in FORBIDDEN_FIELD_SUBSTRINGS), (cls.__name__, name)
    for group in (go1_trees, axes_trees):
        for method, (_, result) in group.items():
            for key in walk_keys(result.to_json()):
                assert not any(bad in key.lower() for bad in FORBIDDEN_FIELD_SUBSTRINGS), (method, key)


# ---------- F20: the CLI block ----------


def test_f20_the_block_follows_the_omnibus_block_and_its_first_line_carries_the_fields(synth_root: Path) -> None:
    """Section 3.6, through ``main()`` with ``StringIO`` streams. The block is found by index and
    is never the tail of stdout (P4.3 appends after it). Every number on the first line is a
    field under ``:g`` and the key and the rung are named; the wording is free."""
    _, result = store_tree(synth_root, "axes-a", "axes-b", events=("fail",), method="fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail"])
    assert code == 0, (out, err)
    assert err == "", err
    lines = out.splitlines()
    omnibus, block = omnibus_block(out), fault_lines_block(out)
    assert omnibus and block, out
    assert lines.index(block[0]) >= lines.index(omnibus[0]) + len(omnibus), (omnibus, block)
    grouping, fault_lines = result.grouping, result.fault_lines
    first = block[0]
    assert grouping.key in first and grouping.resolved_by in first, first
    tokens = numeric_tokens(first)
    for field in FIRST_LINE_NUMERIC_FIELDS:
        assert g(getattr(grouping, field)) in tokens, (field, g(getattr(grouping, field)), first)
    assert g(fault_lines.n_degenerate_groups) in tokens, first


def test_f20_one_refused_line_per_row_of_the_chain_in_order(synth_root: Path) -> None:
    for extra, expected in ((("--by", "task"), ("task", "requested", "underpowered", "trace")), ((), ("task", "axis", "underpowered", "axis"))):
        _, result = store_tree(synth_root, "axes-a", "axes-b", events=("fail",), method="fisher_bh", n_permutations=50, seed=GOLDEN_SEED, by=extra[1] if extra else None)
        assert [(r.key, r.rung, r.reason, r.next_rung) for r in result.grouping.refused] == [expected], extra
        code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", *extra])
        assert code == 0 and err == "", (extra, out, err)
        block = fault_lines_block(out)
        refused_lines = block[1 : 1 + len(result.grouping.refused)]
        for refusal, line in zip(result.grouping.refused, refused_lines, strict=True):
            assert "refused" in line, (extra, line)
            for piece in (refusal.key, refusal.rung, refusal.reason, refusal.next_rung):
                assert piece in line, (extra, piece, line)


def test_f20_one_group_line_per_group_in_labels_order_carrying_counts_p_q_and_the_verdict(synth_root: Path) -> None:
    _, result = store_tree(synth_root, "axes-a", "axes-b", events=("fail",), method="fisher_bh", n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail"])
    assert code == 0 and err == "", (out, err)
    block = fault_lines_block(out)
    assert result.fault_lines.tested is True
    group_lines = block[-result.grouping.n_groups :]
    for group, line in zip(result.fault_lines.groups, group_lines, strict=True):
        tokens = numeric_tokens(line)
        assert group.label in line, (group.label, line)
        assert g(group.n_cells) in tokens and g(group.n_informative_cells) in tokens, (group.label, line)
        assert g(group.p_group) in tokens and g(group.q_group) in tokens, (group.label, line)
        if group.rejects:
            assert "rejected" in line and "not rejected" not in line, line
        else:
            assert "not rejected" in line, line


def test_f20_by_and_max_group_mde_reach_the_call(synth_root: Path) -> None:
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--by", "temp", "--max-group-mde", "0.37", "--format", "json"])
    assert code == 0 and err == "", (out, err)
    grouping = json.loads(out)["tree"]["grouping"]
    assert (grouping["requested"], grouping["max_group_mde"], grouping["resolved_by"]) == ("temp", 0.37, "requested")


def test_f20_the_json_tree_equals_to_json_after_a_round_trip_and_its_root_equals_the_omnibus_key(synth_root: Path) -> None:
    """``{**multi.to_json(), "omnibus": tree.root.to_json(), "tree": tree.to_json()}`` with the
    CLI composing a mapping and computing nothing: ``payload["tree"]`` equals the payload the
    test computes on the same frames with the same knobs, and the root appears twice, equal --
    the CLI-level form of F11."""
    multi, result = store_tree(synth_root, "axes-a", "axes-b", events=("fail",), method="fisher_bh", n_permutations=300, seed=3)
    code, out, err = run_cli(["--store", str(synth_root), "diff", "axes-a", "axes-b", "--event", "fail", "--format", "json", "--permutations", "300", "--seed", "3"])
    assert code == 0 and err == "", (out, err)
    payload = json.loads(out)
    assert payload["tree"] == json.loads(json.dumps(result.to_json()))
    assert payload["tree"]["root"] == payload["omnibus"]
    assert payload["tree"]["root"]["n_permutations"] == 300 and payload["tree"]["root"]["seed"] == 3
    for key in multi.to_json():
        assert key in payload, key


# ---------- F21: the CLI does no arithmetic on any tree field ----------


def test_f21_the_cli_does_no_arithmetic_on_any_tree_field() -> None:
    """**The rule, in prose.** ``cli.py`` reads a field and prints it; it may ask whether one is
    ``None``; it may not do arithmetic on one. Every field of the five structures, O17's
    thirteen and ``n_uninformative_cells`` (A19 closed) are guarded when reached as an
    attribute; the names that cannot collide with a local in ``cli.py`` are guarded as bare
    names too (the module docstring names the collision on ``cells``). The C19 shape: any
    ``BinOp`` whose subtree names one fails, and ``ast.walk`` of a ``BinOp`` descends into joined
    f-strings, which is not narrowed here either."""
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


# ---------- F22, F23: the two P4.1 resolutions, pinned ----------


def test_f22_methods_all_text_prints_the_table_then_the_primary_omnibus_then_the_fault_lines() -> None:
    """Draft ADR-070. ``--permutations 200``: this test is about the shape of the stream, not
    the omnibus (S25 section A permits fewer permutations for such a test and asks that it say
    so). One omnibus block and one fault-lines block: the primary's."""
    code, out, err = run_cli(["--store", str(GO1_ROOT), "diff", GO1_A, GO1_B, "--event", "fell", "--methods", "all", "--permutations", "200"])
    assert code == 0 and err == "", (out, err)
    assert out.index("| method |") < out.index("omnibus: ") < out.index("fault lines:"), out
    assert out.count("omnibus: ") == 1 and out.count("fault lines:") == 1, out
    assert fault_lines_block(out) and omnibus_block(out), out


def test_f22_methods_all_json_keeps_exactly_the_three_method_keys_and_carries_no_tree() -> None:
    """``test_i9_diff_methods_all_json_keys`` pins the same key set from the M10 side; a builder
    who emits ``"tree"`` beside three method objects fails both."""
    code, out, err = run_cli(["--store", str(GO1_ROOT), "diff", GO1_A, GO1_B, "--event", "fell", "--methods", "all", "--format", "json", "--permutations", "200"])
    assert code == 0 and err == "", (out, err)
    payload = json.loads(out)
    assert set(payload) == set(METHODS), sorted(payload)
    assert "omnibus" not in payload and "tree" not in payload


def test_f23_no_comparable_cell_prints_neither_block_emits_neither_key_and_the_api_refuses(synth_root: Path) -> None:
    """A13 pinned as shipped: exit 0, no root and no fault lines on a pair with no common cell;
    ``tree()`` on that ``multi`` raises ``TreeError`` (O13's refusal, reached from the API only)."""
    code, out, err = run_cli(["--store", str(synth_root), "diff", "empty-a", "empty-b", "--event", "fail"])
    assert code == 0 and err == "", (out, err)
    assert "omnibus:" not in out and "fault lines:" not in out, out
    code, out, err = run_cli(["--store", str(synth_root), "diff", "empty-a", "empty-b", "--event", "fail", "--format", "json"])
    assert code == 0 and err == "", (out, err)
    payload = json.loads(out)
    assert payload["n_tests"] == 0 and "omnibus" not in payload and "tree" not in payload
    store = Store(synth_root)
    a, b = store.read("empty-a", meta=False), store.read("empty-b", meta=False)
    multi = quiet_multi_diff(a, b, store.manifest("empty-a"), store.manifest("empty-b"), events=("fail",), method="fisher_bh")
    assert multi.n_tests == 0
    with pytest.raises(tree().TreeError):
        grown(a, b, multi, store.manifest("empty-a"), store.manifest("empty-b"), n_permutations=50, seed=GOLDEN_SEED)


# ---------- F24: the discordant cell, the deterministic twin of S25 M3b ----------


@pytest.mark.parametrize("method", TWO_SCHEMES)
def test_f24_the_discordant_cell_separates_pair_swap_from_arm_label(discordant_trees: Any, method: str) -> None:
    """**The deterministic twin for the lane's one sole catch.** One cell of 32 with every
    matched pair discordant: under pair swap ``p_location`` is ``2 P(Bin(32, 1/2) <= 12) =
    0.2153`` exactly and under arm label ``2 P(Hyp(64, 32, 32) <= 12) = 0.0793``; measured
    0.2119-0.2249 and 0.0767-0.0912 over five seeds at B=4000 (step zero item 5). The bands are
    at least 5.4 Monte Carlo sd from the exact value and 6 sd from the other scheme's, so an
    exchange regressed to arm label under ``mcnemar_bh`` reads about 0.08 and fails the first
    band alone, in a tenth of a second, with every count and the ``scheme`` field still right.
    On one cell the RMS equals the absolute mean, so the three p-values coincide exactly."""
    multi, result = discordant_trees[method]
    root = result.root
    low, high = DISCORDANT_BANDS[method]
    assert root.n_cells == 1 and float(root.units["delta"].iloc[0]) == -0.25
    assert low <= root.p_location["fail"] <= high, (method, root.p_location)
    assert root.p_dispersion["fail"] == root.p_location["fail"] == root.p_omnibus
    grouping = result.grouping
    assert [(r.key, r.rung, r.reason) for r in grouping.refused] == [("task", "axis", "one_group")]
    assert (grouping.key, grouping.resolved_by, grouping.n_groups) == (EXPECTED_WHOLE_GRID_KEY, "whole_grid", 1)


# ---------- F25, F26: construction-site guards ----------


def test_f25_the_reductions_that_make_a_statistic_live_in_one_function_called_only_with_a_bare_array_or_a_row_slice() -> None:
    """**The rule, in prose** (ADR-066 as this packet fixes it). Calls named ``sqrt``, ``mean`` or
    ``average`` occur in exactly one function of ``tree.py`` and it is ``_statistics``;
    ``_statistics`` is defined once with exactly one parameter; every call to it passes one
    positional argument that is a bare name or a subscript of a bare name -- never a ``BinOp``,
    a ``Call`` or any other expression -- and at least two functions call it, so the guard is
    written against the root's path and the groups' path together.

    **What this does not prove, said plainly**: a weight written *inside* ``_statistics`` is a
    property of the source, checked by reading (S25 M14 / M21, both survive the whole suite by
    construction). What it does is make the drift case fail loudly -- ``_statistics(deltas * w)``
    at a call site, a second RMS rebuilt beside it for the groups, or ``omnibus`` computing its
    reported ``location`` with ``np.mean`` a second time, which is S25 M15's split and is red on
    the bare tree at ``11502ba``."""
    module = parsed(TREE_SOURCE)
    enclosing = enclosing_functions(module)
    reducers = [(node.lineno, enclosing.get(node, "<module>"), called_name(node)) for node in ast.walk(module) if isinstance(node, ast.Call) and called_name(node) in ("sqrt", "mean", "average")]
    assert reducers, "no reduction found at all"
    assert {function for _, function, _ in reducers} == {"_statistics"}, reducers
    definitions = [node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == "_statistics"]
    assert len(definitions) == 1
    signature = definitions[0].args
    assert len(signature.args) == 1 and not signature.posonlyargs and not signature.kwonlyargs and signature.vararg is None and signature.kwarg is None
    calls = [node for node in ast.walk(module) if isinstance(node, ast.Call) and called_name(node) == "_statistics"]
    for call in calls:
        assert len(call.args) == 1 and not call.keywords, (call.lineno, ast.dump(call))
        argument = call.args[0]
        assert isinstance(argument, ast.Name) or (isinstance(argument, ast.Subscript) and isinstance(argument.value, ast.Name)), (call.lineno, ast.dump(argument))
    callers = {enclosing.get(call, "<module>") for call in calls}
    assert len(callers) >= 2, callers


def test_f26_the_threshold_is_imported_from_the_executor_and_never_retyped() -> None:
    """ADR-021's shape: one constant, two readers. ``tree.py`` imports ``DEFAULT_MAX_MDE`` from
    ``proofload.executor``; no float constant ``0.2`` appears in ``tree.py`` or ``cli.py``; the
    module's own name is the executor's object."""
    imported = {alias.name for node in ast.walk(parsed(TREE_SOURCE)) if isinstance(node, ast.ImportFrom) and node.module == "poisson_prove.executor" for alias in node.names}
    assert "DEFAULT_MAX_MDE" in imported, imported
    for path in (TREE_SOURCE, CLI_SOURCE):
        retyped = [(node.lineno, node.value) for node in ast.walk(parsed(path)) if isinstance(node, ast.Constant) and isinstance(node.value, float) and abs(node.value - 0.2) < 1e-12]
        assert retyped == [], (path.name, retyped)
    assert tree().DEFAULT_MAX_GROUP_MDE == executor.DEFAULT_MAX_MDE


# ---------- F27: determinism ----------


def test_f27_the_same_inputs_give_identical_json_bytes_twice_in_one_process(go1: Any) -> None:
    a, b, ma, mb = go1
    multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method="fisher_bh")
    first = grown(a, b, multi, ma, mb, n_permutations=200, seed=7)
    second = grown(a, b, multi, ma, mb, n_permutations=200, seed=7)
    assert json_bytes(first.to_json()) == json_bytes(second.to_json())
    assert set(first.to_json()) == set(TREE_RESULT_FIELDS) or set(first.to_json()) > set(TREE_RESULT_FIELDS)


def test_f27_a_different_seed_moves_only_the_p_driven_fields_on_go1_by_mu(go1: Any, go1_trees: Any) -> None:
    """Never the grouping, the units, the statistics, the counts, ``mde``, ``degenerate`` or
    ``tested`` (stable on Go1 because the root is at the floor under every seed)."""
    a, b, ma, mb = go1
    multi, base = go1_trees["fisher_bh"]
    other = grown(a, b, multi, ma, mb, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED + 1)
    one, two = base.to_json(), other.to_json()
    assert one["root"]["seed"] != two["root"]["seed"]
    assert one["grouping"] == two["grouping"]
    assert without(one["root"], (*P_DRIVEN_ROOT_KEYS, "seed")) == without(two["root"], (*P_DRIVEN_ROOT_KEYS, "seed"))
    assert without(one["fault_lines"], (*P_DRIVEN_FAULT_LINE_KEYS, "groups")) == without(two["fault_lines"], (*P_DRIVEN_FAULT_LINE_KEYS, "groups"))
    assert one["fault_lines"]["tested"] is True and two["fault_lines"]["tested"] is True
    for group_one, group_two in zip(one["fault_lines"]["groups"], two["fault_lines"]["groups"], strict=True):
        assert without(group_one, P_DRIVEN_GROUP_KEYS) == without(group_two, P_DRIVEN_GROUP_KEYS), group_one["label"]


# ---------- F28: nothing else moves ----------


@pytest.mark.parametrize("method", METHODS)
def test_f28_multi_diff_on_go1_is_byte_identical_to_the_bare_tree(go1: Any, method: str) -> None:
    a, b, ma, mb = go1
    multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method=method)
    assert sha256_of_text(json.dumps(multi.to_json(), sort_keys=True)) == MULTI_JSON_SHA256[method], method


def test_f28_the_s24_column_digests_and_the_coverage_digest_are_unchanged(go1: Any) -> None:
    a, b, ma, mb = go1
    pair = quiet_multi_diff(a, b, ma, mb, events=("fell", "survived"), method="fisher_bh")
    fell_logrank = quiet_multi_diff(a, b, ma, mb, events=("fell",), method="logrank_bh")
    assert sha256_of_column(pair, "q") == PAIR_QCOLUMN_SHA256
    assert sha256_of_column(pair, "delta") == PAIR_DELTA_SHA256
    assert sha256_of_column(fell_logrank, "q") == FELL_LOGRANK_QCOLUMN_SHA256
    assert sha256_of_text(pair.coverage.to_json(orient="records")) == COVERAGE_SHA256


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


def e14_builder_digests(go1: Any) -> dict[str, str]:
    """The E14 argv's ``multi`` and spec, rendered by the M7 builder with no tree, the way
    ``_report_pair`` builds them: the dark-theme report's markdown and the light-theme receipt."""
    a, b, ma, mb = go1
    multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method="fisher_bh")
    title = f"{GO1_A} vs {GO1_B}: fell"
    report = build_multi_report(
        multi, ReportSpec(title=title, x_axis="mu", y_axis="push_pct_bw"), manifests=(ma, mb)
    )
    receipt = build_multi_report(
        multi, ReportSpec(title=title, x_axis="mu", y_axis="push_pct_bw", theme="light"),
        manifests=(ma, mb),
    )
    return {
        "report.md": sha256_of_text(as_0_0_1_wrote_it(report.to_markdown())),
        "receipt.html": sha256_of_text(as_0_0_1_wrote_it(receipt.to_html())),
    }


def test_f28_the_go1_report_still_reproduces_the_three_digests_s21_minted(go1: Any, tmp_path: Path) -> None:
    """Narrowed for S28 (draft ADR-074, spec S28 section 3.8): ``report`` on a pair now renders the
    layered report into ``report.md`` and ``receipt.html``, so those two files through the CLI
    are S28's to pin. The surface S21 owned is the tree-less M7 builder, which reproduces both
    digests bit for bit (S28 section 0.2), so the two markdown and HTML pins move to
    ``build_multi_report(multi, spec, manifests=...)`` with no tree; ``heatmap.svg`` never
    changes (S28 section 3.3) and stays pinned through the CLI. Narrowed, not deleted."""
    out = tmp_path / "report"
    code, text, _ = run_cli(["--store", str(GO1_ROOT), *E14_ARGV, "--out", str(out)])
    assert code == 0, text
    assert hashlib.sha256((out / "heatmap.svg").read_bytes()).hexdigest() == E14_SHA256["heatmap.svg"]
    for name, digest in e14_builder_digests(go1).items():
        assert digest == E14_SHA256[name], name


def test_f28_check_on_go1_prints_the_same_bytes_and_exits_the_same() -> None:
    code, out, err = run_cli(["--store", str(GO1_ROOT), *CHECK_ARGV])
    assert code == CHECK_EXIT and err == "", (out, err)
    assert sha256_of_text(out) == CHECK_STDOUT_SHA256


def test_f28_serve_json_on_go1_prints_the_same_structure() -> None:
    code, out, err = run_cli(["--store", str(GO1_ROOT), *SERVE_ARGV])
    assert code == 0 and err == "", err
    structure = json.loads(out)
    tree_less = {**{k: v for k, v in structure.items() if k != "tree"}, "schema": TREE_LESS_SCHEMA}
    normalised = json.dumps(structure_as_0_0_1_wrote_it({**tree_less, "pair": {**tree_less["pair"], "store_root": "<store>"}}), sort_keys=True)
    assert sha256_of_text(normalised) == SERVE_STRUCTURE_SHA256


# PF0 (Q4): test_f28_diff_py_is_byte_untouched removed. It pinned the bytes of src/poisson_prove/diff.py, which the rename
# changes; no digest of a file this module changes can be frozen honestly before its build
# exists (front-door spec section 14).


def test_f28_omnibus_on_go1_minus_the_p_driven_keys_digests_to_the_value_minted_on_the_bare_tree(go1: Any, go1_trees: Any) -> None:
    """How ``omnibus``'s body may be refactored (section 3.4, F25) without its output moving: the
    non-Monte-Carlo payload -- ``units``, the two statistics, every count -- is pinned as bytes;
    no permutation p is (S25 section 0.3). Both the standalone ``omnibus`` and the tree's root."""
    a, b, _, _ = go1
    multi, result = go1_trees["fisher_bh"]
    standalone = tree().omnibus(a, b, multi, n_permutations=GOLDEN_PERMUTATIONS, seed=GOLDEN_SEED).to_json()
    assert sha256_of_text(json_bytes(without(standalone, P_DRIVEN_ROOT_KEYS))) == F28_OMNIBUS_SHA256
    assert sha256_of_text(json_bytes(without(result.root.to_json(), P_DRIVEN_ROOT_KEYS))) == F28_OMNIBUS_SHA256


# ---------- F29: declared order, arm A, intersected ----------


def test_f29_axis_order_is_arm_as_declared_order_intersected_with_arm_b(go1: Any) -> None:
    """Not sorted, not by group count, not arm B's, not the union. Four rebuilds of Go1's
    manifests: A declaring ``(push_pct_bw, mu)`` resolves ``push_pct_bw``; B alone reordered
    changes nothing; B declaring only ``mu`` with A push-first yields a ``not_shared`` row and
    resolves ``mu``; with A mu-first the same B yields no row at all. A builder who reads B's
    order, or the union, fails here alone."""
    a, b, ma, mb = go1
    multi = quiet_multi_diff(a, b, ma, mb, events=("fell",), method="mcnemar_bh")
    push_first = reordered(ma, {"push_pct_bw": "continuous", "mu": "continuous"})
    b_push_first = reordered(mb, {"push_pct_bw": "continuous", "mu": "continuous"})
    b_only_mu = reordered(mb, {"mu": "continuous"})
    swapped = grown(a, b, multi, push_first, mb, n_permutations=50, seed=GOLDEN_SEED).grouping
    assert (swapped.key, swapped.resolved_by, swapped.refused) == ("push_pct_bw", "axis", ())
    b_alone = grown(a, b, multi, ma, b_push_first, n_permutations=50, seed=GOLDEN_SEED).grouping
    assert (b_alone.key, b_alone.refused) == ("mu", ())
    shared = grown(a, b, multi, push_first, b_only_mu, n_permutations=50, seed=GOLDEN_SEED).grouping
    assert [(r.key, r.rung, r.reason, r.next_rung) for r in shared.refused] == [("push_pct_bw", "axis", "not_shared", "axis")]
    assert (shared.key, shared.resolved_by) == ("mu", "axis")
    quiet = grown(a, b, multi, ma, b_only_mu, n_permutations=50, seed=GOLDEN_SEED).grouping
    assert (quiet.key, quiet.refused) == ("mu", ())


def test_f29_arm_a_declaring_fewer_axes_than_arm_b_is_not_widened_by_the_union(axes: dict[str, Any]) -> None:
    """The union reads the same as arm A's order whenever B declares a subset of A, which is
    every case in the test above; here A declares only ``task`` and B declares both, so the
    intersection has one axis and the resolver falls to the whole grid, while a union would
    have resolved ``temp``."""
    task_only = manifest("axes-a", AXES_SALT, {"task": "categorical"})
    multi = quiet_multi_diff(axes["a"], axes["b"], task_only, axes["mb"], events=("fail",), method="mcnemar_bh")
    grouping = grown(axes["a"], axes["b"], multi, task_only, axes["mb"], n_permutations=50, seed=GOLDEN_SEED).grouping
    assert [(r.key, r.rung, r.reason, r.next_rung) for r in grouping.refused] == [("task", "axis", "underpowered", "task_family")]
    assert (grouping.key, grouping.resolved_by) == (EXPECTED_WHOLE_GRID_KEY, "whole_grid")


# ---------- F30: refusals before drawing ----------


@pytest.mark.parametrize("case", ("unknown-by", "bad-override", "different-pair"))
def test_f30_refusals_fire_before_any_permutation_is_drawn(go1: Any, go1_trees: Any, case: str) -> None:
    """O13's pin extended to the new inputs: at ``n_permutations = 10**6`` a refusal that
    validates first returns in milliseconds; one that draws first spends minutes or fails to
    allocate the block. Ten seconds is a thousandfold margin over the honest path."""
    a, b, ma, mb = go1
    multi, _ = go1_trees["fisher_bh"]
    frames, knobs = (a, b), {"n_permutations": REFUSAL_PERMUTATIONS, "seed": GOLDEN_SEED}
    if case == "unknown-by":
        knobs["by"] = "nonsense"
    elif case == "bad-override":
        knobs["max_group_mde"] = 2.0
    else:
        frames = (a, a)
    started = time.perf_counter()
    with pytest.raises(tree().TreeError):
        grown(frames[0], frames[1], multi, ma, mb, **knobs)
    assert time.perf_counter() - started < REFUSAL_BUDGET_SECONDS


def test_f28_the_exclusion_record_is_one_constant_per_narrowed_file_with_every_adr_077_field() -> None:
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
