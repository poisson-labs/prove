"""FR oracle: invariants FR1 to FR20 of [[Proofload - Spec First Run Fixes]] section 4, written before the
store check, the missing-flags refusal, the inference line's new wording and the parser edit exist, against
``f9b881f`` -- main's HEAD on 2026-09-18: P-1's landed build (``fe7b50f``) plus A8b Session A's frozen
oracle (``73a8ccb``, ``f9b881f``), which A8b Session B had not built when this was frozen.

**The register, built to as ruled 2026-09-17 (spec sections 0 and 10).** D1 (a missing store refuses at exit
2 on every verb that reads it, an empty one on every such verb but ``runs``, which exits 0 and says so on
stderr), D5 bound by D14 (E3 reaches ``report``, ``serve``, ``check`` and ``inspect``, and ``check`` never
passes on a missing argument), D7 (the ``Inferred events for this pair`` suggestion is retired) and D13
(every template pinned verbatim, Taylor reviewing the wording in Session A's mapping table) are Taylor's and
not reopened; FR19 and FR20 are his additions at the same ruling. Q1 to Q4 are closed. The three section 3.1
templates are pinned in each source form (``--store``, ``$PROOFLOAD_STORE``, the default), the seven section
3.2 Go1 literals and the section 3.3 lines byte for byte, as literals and never as a template the build
shares.

**Two cells, and no invariant is cell-specific -- a result, not an assumption** (Master Action List section
18 standing rule 15; spec section 7 binds one cell, this oracle reports two because the dispatch asked for
both). pandas 2.3.3 and pandas 3.0.5: every test here is asserted in both cells, nothing here reads a stored
null, and the map is the whole file twice: **106 + 106 = 212 ids over the two cells against the oracle's own
106.** The ids by invariant: FR1 3, FR2 1, FR3 1, FR4 7, FR5 4, FR6 3, FR7 3, FR8 3, FR9 6, FR10 5, FR11 7,
FR12 17, FR13 10, FR14 7, FR15 1, FR16 6, FR17 6, FR18 2, FR19 9, FR20 5.

**Step zero, measured at ``f9b881f`` (spec section 7.4), and what it moved.** (1) The section 7.1 greps:
the first returns 26 lines in four files and the fifth five carriers, as at ``a626cd3``; the fourth gains one
line, ``test_p1_payload.py`` Y22's ``monkeypatch.chdir``, which drives ``serve`` on Go1 with an explicit
``--store``, ``--event`` and ``--x`` and moves nothing; A8b re-minted the pin on ``test_m3_timeout_trace.py``,
a file this packet does not touch. The twenty-one frozen movers are the spec's, at new line numbers: ``test_m6_multi.py`` +5,
``test_m7_multi.py`` +14 and +15, ``test_m13_viewer.py`` +2, and I17 +1; ``test_m10_multi.py`` did not move
(section 12 lists it among P-1's edits and P-1 did not touch it) and neither did I2. (2) Nothing the spec
predicted about the inference path moved: ``infer_events`` and the inference branch of
``MultiDiffResult.to_markdown`` are byte-identical to ``a626cd3``'s (the branch is ``diff.py`` lines 700-704,
the method 698-750), Go1 infers ``survived`` over ``fell`` on the pair and on ``go1-v0`` alone (8029 / 4771
and 6753 / 6047), and the mock pair infers ``violated, timeout`` over ``completed``. **What no longer holds:**
the base is not green -- spec sections 7.3 and 9 assume a green dispatch commit, and ``f9b881f`` carries A8b's
frozen oracle against a tree that does not build it yet (63 failed and 2 errors, identical in both cells:
53 in ``test_a8b_cut_and_cap.py``, 4 in ``test_m3_capture.py``, one each in ``test_a8a_span_schema.py``,
``test_m3_crash_trace.py``, ``test_m3_timeout_trace.py`` and ``test_pilot_golden.py``, and two failures and
two errors in ``test_t4_tau2_pilot.py``); section 12's "P-1 will edit" is done, ``to_markdown``'s parameter
line and ``headline``'s pairing token are in the tree with ``_write_summary``'s code unedited, so the two
packets no longer collide; section 3.3's line lengths are 108 and 122 characters against 54 and 68 today,
not 107, 120, 55 and 68; and the Go1 verbs without a paired method now emit P-1's ``UnpairedAnalysis``
warning through the warnings machinery, never into the CLI's own stderr stream, which is what every
assertion here reads. (3) P-1 filed the whole-file route: ``ec05b676...`` in all five carriers of the
``diff.py`` digest, no live exclusion record, so D12 stands. (4) The digests below were read off
``f9b881f``: ``diff.py`` outside ``MultiDiffResult.to_markdown`` (the qualified-name resolver's lines 698
to 750) ``6413b54a...``, and ``report.py``, ``viewer.py``, ``store.py`` and ``tree.py`` whole-file.
``store.py`` is byte-identical to ``a626cd3``'s: P-1 touched ``cli.py``, ``diff.py``, ``report.py``,
``tree.py`` and ``viewer.py`` only, and A8b's build (``trace``, ``capture``, ``sampler``, ``executor``,
``executor_modal``) touches none of the five files this oracle pins. (5) ``Store.runs()`` and
``Store.manifest()`` are unchanged. (6) The shadow shim -- a scratch build of section 3 -- turns every test
here green and leaves exactly group D red.

**Where this oracle reads the spec differently, each with its hatch.** (a) FR20's explicit-event clause
carries its positive control in the same test, as FR20's own text says, so it is *red* on the bare tree;
section 7.2 predicts it green before and after, and it cannot be both -- a negative with no control is the
vacuous shape section 7.1's group E4-b exists to prevent. The tie clause is FR20's one green half. (b) FR11's
two cross-checks read both lists off live output (E3's, and the error a wrong ``--x`` or ``--event``
provokes); comparing E3's list to a constant would have been green on the bare tree and pinned nothing. (c)
FR1 gives every invocation its own missing root, so FR6 is the sole catch for the mutant that creates the
root, as the spec's row says. (d) FR4 also pins the empty-store templates (E and E-runs) in each source form,
and a set-but-empty ``$PROOFLOAD_STORE`` as *not* the source: ``_store_root`` reads it as unset and section
3.1 says "set and non-empty". (e) FR10 pins the third ``timeout`` case section 3.2's bullet states and FR10's
text does not: a run whose ``timeout`` is already an outcome lists it once. (f) FR12's order matrix adds the
empty store to its store row. (g) FR13's "nothing else moves" is two green tests (the flag sets, and the five
tree flags' help against ``diff``'s), beside V30, W1, R13 and W11. (h) FR18's import clause is a subset test,
so it holds before the build as well: ``shlex`` may arrive and nothing else may. (i) FR5's Go1 verb digests
stay with A7's P7-10, which this file does not restate. (j) Not pinned: section 3.3's line lengths, and the
``inspect`` wrong-``--event`` neighbour that section 5 names as out of scope.

**Standing rule 12 -- the classified red set on the retrofit commit with this file added, measured on two
pristine ``git archive`` copies of ``f9b881f`` carrying the retrofit and this file, venvs from the repo venv's
freeze closure differing in exactly pandas, collection verified 2071 = 2071 = 2071 at ``f9b881f`` (both
baseline cells and the repo) and 2177 = 2177 = 2177 = 2177 = 2177 with the retrofit and this file (both
red-set cells, both shim-control cells, and the clone at the tip), baselines 63 failed / 2001 passed / 5
skipped / 2 errors in both cells at ``f9b881f``: 151 failed / 2019 passed / 5 skipped / 2 errors, identical
test by test in both cells.** The 153 red are the base's 65 and **88 of this packet's**: **82** of this
file's 106 tests, each red for its expected cause (the store check, the missing-flags refusal, the parser and
the new wording do not exist yet), and the six frozen tests V1 and V4 (renamed, amended to section 3.2's
``serve --x mu`` and ``serve --event fell`` literals), A14, B9, B17 and C2 (``:504``), each for the new
wording. **Nothing else is red beyond the base's 65, and none of the base's 65 turned green.** Group D (F28,
L20, R19, W20, G20) is green on the retrofit commit and red once the build edits ``diff.py``; nothing in this
commit touches it. The shim control -- the same copies with the shim built -- is 68 failed / 2102 passed / 5
skipped / 2 errors in both cells, identical test by test: the base's 65 and group D's five, nothing else.

**Green before and after, named so its green is not read as evidence** (standing rule 12; count them out of
coverage): FR5's four tests, FR6's ``sweep`` half, FR12's ``check`` unknown-run id (today's ``check`` loads
the pair before it refuses), FR13's four "nothing else moves" ids, FR17's six, FR18's two, FR19's exit,
stdout and tripwire half (four ids) and its gate-pair controls (green by construction: they pin the
fixtures, not the build), and FR20's tie clause -- 24 of the 106 on the bare tree. **The five frozen tests
carrying section 7.1's group E1 edit (I2 x3, I17 x2) and the four group E4-b negatives that are not also
E4-a are green before and after by construction**; the negatives are non-vacuous only because FR16 asserts
the marker matches real inferred output in the same test.

**Mutation list for Session B** (spec section 7.5's twenty-nine rows and eight this oracle added, measured
on the shim control with one interpreter per row, each row applying exact replacements that fail loudly when
a target is missing; control clean; **all 37 caught by this file alone**). The owners, by oracle test: 1
``exists()`` for ``is_dir()``: FR1's file-root pair alone. 2 and 3 missing and empty collapsed, and an empty
store keeping ``unknown run``: FR2, FR4's empty-source trio, FR7's empty hint, FR12's empty-store row. 4 and
5 ``runs`` on an empty store exiting 2, and its note on stdout: FR3, FR4's trio, FR6's empty-root test, FR7's
empty hint (with I17 x2 in the frozen amendment). 6 the source clause always the default: twenty ids across
FR1, FR2, FR3, FR4, FR7 and FR12. 7 env over flag in the clause: FR4's flag id alone. 8 the note on every
``runs``: FR5's two ``runs`` ids. 9 the check creating the root: FR6's missing-root test, and
incidentally FR1's file-root pair because ``mkdir`` raises on a file; **row 37 is the pure spelling, and FR6
alone catches it**. 10 the check gating ``sweep``: FR6's sweep test, and fifteen fixture errors because the
mock pair's own sweep is refused. 11 ``shlex.quote`` dropped: FR7 alone (three ids). 12 axes from
``axis_types``: FR11's disagreement pair and the property. 13 events as the inferred set: twenty-five ids in
FR8 to FR12 and FR19. 14 ``serve --x`` left argparse-required: FR9 (four of six), FR12, FR13. 15 E3 after
``_run_diffs``: FR12's tripwire, FR19's tripwire half x4, the FR11 property. 16 E3 before ``manifest``:
FR12's unknown-run row alone (three ids). 17 ``inspect`` omitting ``timeout``: FR10's timeout id and
FR11's single-run property. 18 ``check``'s reason clause dropped: FR10, FR12's tripwire. 19 the retired
suggestion kept: FR9 x6, FR10, FR12. 20 ``to_markdown`` keeping the parenthetical while ``_write_summary``
prints the new line: FR14's five surfaces and its API pair, FR16 x6. 21 the single-run copy left: FR15 and
FR20 x4. 22 the line on explicit events: FR16's ``diff`` pair. 23 a module-level ``_inference_line``: FR17's
region digest, FR18's names. 24 ``to_json`` gaining a key: FR17's keys and region digest. 25 and 26 ``check``
listing then exiting 0, or then gating on the inferred set: FR19's exit half x4 (the PASS pair and the FAIL
pair both leave 2), FR10, FR11, FR12. 27 the listing on stdout: FR19 both halves x8. 28 events joined with
``and``: FR20's mock id alone. 29 the line after the summary line: FR15, FR20 x4. The eight extras: 30 the
``--out`` refusal ahead of E3: FR12's non-empty-out pair; 31 E3 ahead of the arity refusal: FR12's report
arity id alone; 32 a set-but-empty ``$PROOFLOAD_STORE`` named as the source: FR4's empty-env id alone; 33 axes
from the first run only and 36 events from the first run only: the FR11 property alone each; 34 the hint's
verb always ``runs``: seventeen ids in FR1, FR2, FR4, FR7 and FR12; 35 ``--store`` after the verb in the
create line: thirteen ids in FR1, FR4, FR7 and FR12; 37 above. Session B re-applies every row against the
build and reports where each lands; a row that needs both files (20) is two edits.
"""

from __future__ import annotations

import ast
import hashlib
import re
import shlex
import tempfile
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import proofload.cli as cli
from proofload.diff import MultiDiffResult, UnpairedAnalysis, infer_events, multi_diff
from proofload.episode import Episode
from proofload.store import EpisodeRecord, RunManifest, Store, config_hash
from proofload.survival import competing_set

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "proofload"
GO1_ROOT = ROOT / "tests" / "fixtures" / "go1"
QUICKSTART = ROOT / "examples" / "quickstart.toml"
ROLLOUT = "proofload.examples.mock_agent:rollout"
PATCHED = "proofload.examples.mock_agent:rollout_patched"
QUICKSTART_SALT = "0000000000000015"
GO1_A, GO1_B = "go1-v0", "go1-v1"
GO1_X, GO1_Y = "mu", "push_pct_bw"
HORIZON = 10.0

# ---------- the pinned words (spec section 3), verbatim ----------

FROM_FLAG = "it came from --store"
FROM_ENV = "it came from $PROOFLOAD_STORE"
FROM_DEFAULT = "it is the default, since neither --store nor $PROOFLOAD_STORE is set"
SOURCES = (FROM_FLAG, FROM_ENV, FROM_DEFAULT)
SWEEP_TAIL = "sweep SPEC.toml --target pkg.module:rollout"
RUNS_HEADER = "run_id  status  backend  target_id  t_unit  rows  no_outcome\n"


def missing_message(root: str, source: str, verb: str) -> str:
    """Section 3.1, M: a path with no directory at it, on a verb that reads the store."""
    return (
        f"error: no store at {root}. No directory exists at that path; {source}.\n"
        f"  to create one there: proofload --store {shlex.quote(root)} {SWEEP_TAIL}\n"
        f"  to read another store: proofload --store PATH {verb}, with --store before the verb\n"
    )


def empty_message(root: str, source: str, verb: str) -> str:
    """Section 3.1, E: a directory holding no manifest.json, on a verb that reads the store."""
    return (
        f"error: no runs in {root}. No directory under it holds a manifest.json; {source}.\n"
        f"  to write the first run there: proofload --store {shlex.quote(root)} {SWEEP_TAIL}\n"
        f"  to read another store: proofload --store PATH {verb}, with --store before the verb\n"
    )


def empty_runs_note(root: str, source: str) -> str:
    """Section 3.1, E-runs: stderr of ``runs`` on an empty store, exit 0, no ``error: `` prefix."""
    return (
        f"no runs in {root}. No directory under it holds a manifest.json; {source}.\n"
        f"  to write the first run there: proofload --store {shlex.quote(root)} {SWEEP_TAIL}\n"
    )


GATE_REASON = "a gate whose meaning changes when a new outcome appears is not a gate"
PICTURE_REASON = "a picture whose meaning changes when a new outcome appears is worse than a table with the same defect"

# Section 3.2's seven Go1 literals: (argv after ``--store tests/fixtures/go1``, stderr).
E3_GO1: dict[str, tuple[list[str], str]] = {
    "report pair, no --x": (
        ["report", GO1_A, GO1_B, "--y", GO1_Y],
        "error: report requires --x AXIS, which was not given. go1-v0 and go1-v1 carry:\n"
        "  axes: mu, push_pct_bw\n"
        "  events: fell, survived\n",
    ),
    "report single run, no --x": (
        ["report", GO1_A],
        "error: report requires --x AXIS, which was not given. go1-v0 carries:\n"
        "  axes: mu, push_pct_bw\n"
        "  events: fell, survived\n",
    ),
    "serve, neither": (
        ["serve", GO1_A, GO1_B],
        f"error: serve requires --x AXIS and --event NAME, and neither was given; {PICTURE_REASON}. go1-v0 and go1-v1 carry:\n"
        "  axes: mu, push_pct_bw\n"
        "  events: fell, survived\n",
    ),
    "serve, no --event": (
        ["serve", GO1_A, GO1_B, "--x", GO1_X],
        f"error: serve requires --event NAME, which was not given; {PICTURE_REASON}. go1-v0 and go1-v1 carry:\n"
        "  axes: mu, push_pct_bw\n"
        "  events: fell, survived\n",
    ),
    "serve, no --x": (
        ["serve", GO1_A, GO1_B, "--event", "fell"],
        "error: serve requires --x AXIS, which was not given. go1-v0 and go1-v1 carry:\n"
        "  axes: mu, push_pct_bw\n"
        "  events: fell, survived\n",
    ),
    "check, no --event": (
        ["check", GO1_A, GO1_B],
        f"error: check requires --event NAME, which was not given; {GATE_REASON}. go1-v0 and go1-v1 carry:\n"
        "  events: fell, survived\n",
    ),
    "inspect, no --event": (
        ["inspect", GO1_A],
        "error: inspect requires --event NAME, which was not given. go1-v0 carries:\n"
        "  events: fell, survived\n",
    ),
}
SERVE_ROWS = ("serve, neither", "serve, no --event", "serve, no --x")

# Section 3.3: the marker every negative assertion uses (a line prefix), and its Go1 and A14 lines.
MARKER = "inferred: no event was given, so "
GO1_LINE = "inferred: no event was given, so the event set is survived; the non-event is fell, the most frequent outcome"
A14_LINE = "inferred: no event was given, so the event set is violated, timeout; the non-event is completed, the most frequent outcome"


def inference_line(events: Sequence[str], non_event: str) -> str:
    return f"inferred: no event was given, so the event set is {', '.join(events)}; the non-event is {non_event}, the most frequent outcome"


# Existing shipped sentences that section 3.2.1's order matrix pins as they are.
REPORT_FORMS = "report A B --x AXIS [...]  (two run ids: diff report) or report RUN --x AXIS [...]  (one run id: survival report)"
SERVE_FORM = "serve A B --event NAME --x AXIS [...]  (two run ids, always: a diff view)"

# Minted at f9b881f, the commit this oracle was frozen against (FR17, FR18). Named for what they
# pin: none of the names below ends in the suffix the exclusion-record sweeps count.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): diff.py outside MultiDiffResult.to_markdown gains complementary_events and trade_line()'s complement branch; to_markdown itself is byte-identical to the bare tree's, checked. Read through this test's own measurement on the built tree, not predicted.
# Re-minted 2026-09-26 (A10 declared expectations, phase two, off the build at 662ceff): diff.py outside MultiDiffResult.to_markdown: diff.py gains DeclaredSetMismatch(DiffError) and its refusal in diff() and multi_diff(), just before _pairing (spec A10 W9; ADR-084 stands, _pairing is untouched); to_markdown itself is byte-identical to the bare tree's, checked. Read through this test's own measurement on the built tree, not predicted.
DIFF_OUTSIDE_TO_MARKDOWN_SHA256 = "0e1fa8a53987fbe8d2ac9b8fe32b4909341f7da9ffdeb3960972f19c497dcc87"
# Re-minted 2026-09-20 (truncation surfacing): report.py and viewer.py move, because that packet edits both; store.py and tree.py do not.
# Re-minted again 2026-09-20 (stored-trace read): store.py moves, because that packet edits it; report.py, viewer.py and tree.py do not.
# CD Session B, 2026-09-21: re-minted off the built `report.py` at `234513c`. D9's "no change to
# them" did not survive D3's "none" -- `_observation_cap`'s `isinstance(value, int)` filter drops
# the string -- so that one function lets the word through and nothing else in the file moved,
# which `test_cd_cap_declaration.py`'s digest over the file OUTSIDE `_observation_cap` is what
# pins. This literal and `test_s29_viewer.py`'s `REPORT_PY_SHA256` are the two carriers and moved
# together. The value before this packet was `5cfdf03b...`, correct from the surfacing packet
# through `46c5ac0`.
# Re-minted 2026-09-25 (local serve pass, Phase C, off the build at 173c25d): report.py is the build's (the wrap, the complement, mde_unchanged, LS16's Cells sentence); the whole-file sha256 of the built file. store.py and tree.py do not move. viewer.py is the build's (_LAYOUT's inert rule, the summary key, SCHEMA /6 and both refusals, the page order, the holes block, the unverified tail); the whole-file sha256 of the built file. Read through this test's own measurement on the built tree, not predicted.
# Re-minted 2026-09-26 (A10 declared expectations, phase two, off the build at 662ceff): store.py gains RunManifest.declared, its thirteenth field, in to_dict() and from_dict() (spec A10 W4); report.py gains DeclarationCheck under TYPE_CHECKING, _run_declarations and _run_declaration, the declarations keyword on the three builders, and _provenance_lines printing an empty list as none (spec A10 W8); the whole-file sha256 of each built file. viewer.py and tree.py do not move. Read through this test's own measurement on the built tree, not predicted.
UNTOUCHED_FILE_SHA256 = {
    "report.py": "06775d22522d897f8bf7c6086739e301ceb92baf5c0b9d9a806afecaa2962e61",
    "viewer.py": "6ed29eb6e77244d7b9d41de3004d08d89cb25f8af9e3cdfd98ba8f0ac22918ba",
    "store.py": "957c537786c3ef4e5b95abebec03af86bcaa99e8191c6856005f77cfe4159e51",
    "tree.py": "c0c011a3d194964a16f634d5450354645bb9132e0f47be192070a8daef9a8f3e",
}
MULTI_JSON_KEYS = [
    "alpha_star", "by_event", "coverage", "dropped_a", "dropped_b", "events", "headline", "horizon", "inferred",
    "interval_level", "intervals", "method", "n_interval_only", "n_not_comparable", "n_rejected", "n_tests",
    "n_verdict_only", "non_event", "q", "seed_identity_match", "t_unit", "trade_line", "trades", "truncated",
    "unpaired_analysis",
]
# A10 (spec section 7.1 group 5, W9 and ruling 3 of 2026-09-25): DeclaredSetMismatch is the one
# module-level name diff.py gains; the check itself sits in diff() and multi_diff(), before _pairing.
DIFF_MODULE_NAMES = frozenset(
    "CELLS_COLUMNS COVERAGE_COLUMNS DeclaredSetMismatch DiffError DiffResult EventDiff EventInferenceError INTERVAL_BASES "
    "INTERVAL_COLUMNS "
    "Method MultiDiffResult NotPairable SUMMARY_FIELDS UnitMismatch UnknownEvent UnpairedAnalysis _BASIS_BY_METHOD "
    "_CAUSES _CENSORED _CIF_EQUALITY_TOLERANCE _EVENT_SUMMARY_FIELDS _INVERSION_STEPS _MAX_EVENTS _METHODS "
    "_MULTI_SUMMARY_FIELDS _NO_OUTCOME_A _NO_OUTCOME_B _NO_OUTCOME_BOTH _ONLY_A _ONLY_B _PAIRED_METHODS _RAW_REQUIRED "
    "_REQUIRED _ROOT_RTOL _SCORE_RD _SCORE_RD_PAIRED _TRADES_COLUMNS _build_intervals _cause _coverage _discordant "
    "_endpoint _fisher _frame_horizon _indicator_frame _logrank _maximise _mcnemar _md_cell _nan_to_none _native "
    "_outcome_counts _pairing _power_two_proportion _require_alpha _require_arm _require_pairs _seed_identity _truncate "
    "_truncate_raw _unchanged_mde _validate_frame _validate_raw bh diff infer_events interval_rd interval_rd_paired "
    "mde_two_proportion multi_diff score_p_rd score_p_rd_paired".split()
)
# Re-minted 2026-09-20 (truncation surfacing): cli.py also imports report._observation_cap, for the limit ``inspect`` prints beside a cut.
# Re-minted 2026-09-26 (A10): cli.py calls steps.declaration_check beside _observation_counts and prints ``inspect``'s declaration block through report._provenance_lines.
CLI_IMPORTS = frozenset(
    {
        ("__future__", "annotations"), ("_typeshed", "SupportsWrite"), ("argparse", None), ("collections", "Counter"),
        ("collections.abc", "Callable"), ("collections.abc", "Mapping"), ("collections.abc", "Sequence"),
        ("dataclasses", None), ("dataclasses", "dataclass"), ("json", None), ("os", None), ("pandas", None),
        ("pathlib", "Path"), ("proofload", "__version__"), ("proofload._resolve", "resolve"),
        ("proofload.diff", "COVERAGE_COLUMNS"), ("proofload.diff", "DiffError"), ("proofload.diff", "EventInferenceError"),
        ("proofload.diff", "Method"), ("proofload.diff", "MultiDiffResult"), ("proofload.diff", "UnknownEvent"),
        ("proofload.diff", "_CAUSES"), ("proofload.diff", "_PAIRED_METHODS"), ("proofload.diff", "_md_cell"),
        ("proofload.diff", "infer_events"), ("proofload.diff", "multi_diff"), ("proofload.executor", "ExecutorError"),
        ("proofload.executor", "Plan"), ("proofload.executor", "RunSummary"), ("proofload.executor", "check_power"),
        ("proofload.executor", "plan"), ("proofload.executor", "preflight"), ("proofload.executor", "run_local"),
        ("proofload.executor_modal", "ImageSpec"), ("proofload.executor_modal", "ModalOptions"),
        ("proofload.executor_modal", "ModalTarget"), ("proofload.executor_modal", "preflight_modal"),
        ("proofload.executor_modal", "run_modal"),
        ("proofload.executor_burla", "BurlaOptions"), ("proofload.executor_burla", "preflight_burla"), ("proofload.executor_burla", "run_burla"),
        ("proofload.paired", "Declaration"), ("proofload.paired", "PairedError"), ("proofload.paired", "_Bundle"),
        ("proofload.paired", "_artifact_text"), ("proofload.paired", "_bundle"), ("proofload.paired", "_cost_block"),
        ("proofload.paired", "_fold_html"), ("proofload.paired", "_fold_markdown"), ("proofload.paired", "cost"),
        ("proofload.report", "MultiReport"), ("proofload.report", "ReportError"),
        ("proofload.report", "ReportSpec"), ("proofload.report", "SurvivalReport"), ("proofload.report", "_interval_lines"), ("proofload.report", "_observation_cap"),
        ("proofload.report", "_provenance_lines"), ("proofload.report", "build_multi_report"), ("proofload.report", "build_survival_report"),
        ("proofload.sampler", "SamplerError"), ("proofload.sampler", "SweepSpec"), ("proofload.steps", "declaration_check"), ("proofload.store", "RunManifest"),
        ("proofload.store", "Store"), ("proofload.store", "StoreError"), ("proofload.survival", "SurvivalError"),
        ("proofload.survival", "cell_table"), ("proofload.survival", "competing_set"), ("proofload.trace", "Trace"),
        ("proofload.trace", "TraceValidationError"), ("proofload.tree", "Bound"), ("proofload.tree", "CellFamily"),
        ("proofload.tree", "CellResult"), ("proofload.tree", "DEFAULT_DEPTH"), ("proofload.tree", "DEFAULT_MAX_GROUP_MDE"),
        ("proofload.tree", "DEFAULT_PERMUTATIONS"), ("proofload.tree", "DEFAULT_SEED"), ("proofload.tree", "DEPTHS"),
        ("proofload.tree", "FaultLines"), ("proofload.tree", "GroupResult"), ("proofload.tree", "Grouping"),
        ("proofload.tree", "Leaves"), ("proofload.tree", "RootResult"), ("proofload.tree", "TASK_FAMILY_KEYS"),
        ("proofload.tree", "TRACE_GROUPINGS"), ("proofload.tree", "TreeResult"), ("proofload.tree", "WHOLE_GRID"),
        ("proofload.tree", "tree"), ("proofload.viewer", "ViewerError"), ("proofload.viewer", "_HOST"),
        ("proofload.viewer", "build_structure"), ("proofload.viewer", "render_html"), ("proofload.viewer", "serve_page"),
        ("sys", None), ("tomllib", None), ("traceback", None), ("typing", "Any"), ("typing", "NoReturn"),
        ("typing", "TYPE_CHECKING"), ("typing", "TextIO"), ("typing", "cast"),
    }
)

#: Every name ``cli`` binds that E3, E1 or the gate could reach for work; armed by ``arm_tripwires``.
WORK_NAMES = ("multi_diff", "tree", "build_multi_report", "build_survival_report", "build_structure", "serve_page")


# ---------- harness ----------


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


def run_cli(argv: Sequence[str]) -> Result:
    """Drive ``cli.main`` in-process. The seed-identity warning is a library warning that goes to
    the real stderr and never into ``err``; it is silenced so a run's own stderr is what is read."""
    out, err = StringIO(), StringIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpairedAnalysis)
        code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def arm_tripwires(monkeypatch: pytest.MonkeyPatch, *names: str) -> list[str]:
    """Replace each named binding of ``cli`` with a function that records the call and raises."""
    calls: list[str] = []
    for name in names:

        def trip(*args: Any, _name: str = name, **kwargs: Any) -> Any:
            calls.append(_name)
            raise AssertionError(f"{_name} was called")

        monkeypatch.setattr(cli, name, trip)
    return calls


def arm_gate_tripwire(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """``MultiDiffResult.check`` and ``cli.multi_diff`` both raise: the gate can never run."""
    calls: list[str] = arm_tripwires(monkeypatch, "multi_diff")

    def trip_check(self: MultiDiffResult, *args: Any, **kwargs: Any) -> bool:
        calls.append("MultiDiffResult.check")
        raise AssertionError("the gate was reached")

    monkeypatch.setattr(MultiDiffResult, "check", trip_check)
    return calls


def listing(root: Path) -> list[str]:
    """Everything under ``root``, as relative paths: the store's directory listing."""
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def command_from(err: str, label: str) -> list[str]:
    """The shell command a hint line offers: the line naming ``label``, split at its first ``: ``,
    read back the way a shell would read it."""
    lines = [line for line in err.splitlines() if line.strip().startswith(f"{label}: ")]
    assert len(lines) == 1, (label, err)
    _, _, tail = lines[0].strip().partition(": ")
    return shlex.split(tail)


# ---------- synthetic stores, written through the store's own writer ----------


def manifest(run_id: str, *, salt: str = "syn", axis_types: Mapping[str, str] | None = None) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types or {"cell": "categorical"}), backend="synthetic",  # type: ignore[arg-type]
        environment={},
    )


def seed_of(config: Mapping[str, Any], replicate_index: int) -> int:
    """A stored seed that is a function of ``(config, replicate_index)`` and of nothing else."""
    return 1000 * (int(config_hash(config)[:6], 16) % 100_000) + replicate_index


NON_EVENTS = {"ok", "survived", "completed"}


def write_run(
    store: Store, run_id: str, cells: Sequence[tuple[Mapping[str, Any], Mapping[str, int], Mapping[str, int]]],
    *, salt: str = "syn", axis_types: Mapping[str, str] | None = None,
) -> None:
    """A complete run. Per cell ``(config, {outcome: rows}, {error: rows})``: outcome rows first, then
    errored rows, replicate indices running over both. Events sit at t=3, non-events at the horizon."""
    store.create_run(manifest(run_id, salt=salt, axis_types=axis_types))
    records = []
    for config, outcomes, errors in cells:
        k = 0
        for name, n in outcomes.items():
            for _ in range(n):
                t = HORIZON if name in NON_EVENTS else 3.0
                records.append(EpisodeRecord.from_episode(
                    Episode(outcome=name, t=t, horizon=HORIZON), run_id=run_id, config=dict(config),
                    seed=seed_of(config, k), replicate_index=k, wall_time=0.0,
                ))
                k += 1
        for error, n in errors.items():
            for _ in range(n):
                records.append(EpisodeRecord.errored(
                    run_id=run_id, config=dict(config), seed=seed_of(config, k), replicate_index=k, error=error, wall_time=0.0,
                ))
                k += 1
    store.append(run_id, records)
    store.mark_complete(run_id)


def fell_run(store: Store, run_id: str, fell_per_cell: Mapping[float, int], *, n: int = 32) -> None:
    """One cell per ``x``; ``fell_per_cell[x]`` of ``n`` rows fell and the rest survived."""
    write_run(
        store, run_id, [({"x": x}, {"fell": f, "survived": n - f}, {}) for x, f in fell_per_cell.items()],
        axis_types={"x": "continuous"},
    )


def one_run_store(tmp_path: Path) -> Path:
    root = tmp_path / "one-run"
    fell_run(Store(root), "only", {1.0: 4})
    return root


# ---------- fixtures ----------


@dataclass(frozen=True)
class MockPair:
    root: Path
    a: str
    b: str


@pytest.fixture(scope="module")
def mock_pair(tmp_path_factory: pytest.TempPathFactory) -> MockPair:
    """The two quickstart runs under the S12 salt: three outcomes, ``completed`` the non-event."""
    root = tmp_path_factory.mktemp("mock-store")
    first = run_cli(["--store", str(root), "sweep", str(QUICKSTART), "--target", ROLLOUT, "--salt", QUICKSTART_SALT, "--yes"])
    assert first.code == 0, first.err
    a = first.out.splitlines()[-1].removeprefix("run_id: ")
    second = run_cli(["--store", str(root), "sweep", str(QUICKSTART), "--target", PATCHED, "--pair-with", a, "--yes"])
    assert second.code == 0, second.err
    return MockPair(root, a, second.out.splitlines()[-1].removeprefix("run_id: "))


def mock_e3(pair: MockPair) -> tuple[list[str], str]:
    """The mock pair's ``report`` without ``--x``: its axes, and events read ``completed, timeout, violated``."""
    return (
        ["--store", str(pair.root), "report", pair.a, pair.b, "--y", "task_id"],
        f"error: report requires --x AXIS, which was not given. {pair.a} and {pair.b} carry:\n"
        "  axes: task_id, tool_fail_rate\n"
        "  events: completed, timeout, violated\n",
    )


# ---------- FR1 to FR7: E1, the store ----------


def read_argvs(store: str, out: Path) -> dict[str, list[str]]:
    """Every store-reading invocation, with every other argument valid for Go1."""
    s = ["--store", store]
    o = ["--out", str(out)]
    return {
        "runs": [*s, "runs"],
        "diff": [*s, "diff", GO1_A, GO1_B, "--event", "fell"],
        "report pair": [*s, "report", GO1_A, GO1_B, "--event", "fell", "--x", GO1_X, "--y", GO1_Y, *o],
        "report single run": [*s, "report", GO1_A, "--event", "fell", "--x", GO1_X, "--y", GO1_Y, *o],
        "check": [*s, "check", GO1_A, GO1_B, "--event", "fell"],
        "serve": [*s, "serve", GO1_A, GO1_B, "--event", "fell", "--x", GO1_X],
        "serve --json": [*s, "serve", GO1_A, GO1_B, "--event", "fell", "--x", GO1_X, "--json"],
        "inspect": [*s, "inspect", GO1_A, "--event", "fell"],
    }


def verb_of(label: str) -> str:
    return label.split()[0]


def test_fr1_a_missing_store_refuses_on_every_verb_that_reads_it(tmp_path: Path) -> None:
    """One fresh root per invocation, so a verb that made the root could not change what the next one sees."""
    for index, label in enumerate(read_argvs("", tmp_path)):
        root = str(tmp_path / f"nowhere-{index}")
        r = run_cli(read_argvs(root, tmp_path / "out")[label])
        assert r.code == 2, (label, r)
        assert r.out == "", (label, r.out)
        assert r.err == missing_message(root, FROM_FLAG, verb_of(label)), (label, r.err)
        assert "Traceback" not in r.err, label


@pytest.mark.parametrize("verb", ["runs", "diff"])
def test_fr1_a_regular_file_is_not_a_store_so_is_dir_and_not_exists(tmp_path: Path, verb: str) -> None:
    """A file at the root passes ``exists()`` and fails ``is_dir()``; only the second is the spec's test."""
    root = tmp_path / "a-file"
    root.write_text("not a store\n")
    r = run_cli(read_argvs(str(root), tmp_path / "out")[verb])
    assert r.code == 2, r
    assert r.out == "" and r.err == missing_message(str(root), FROM_FLAG, verb), r


def make_empty_root(tmp_path: Path) -> Path:
    """An existing directory holding one stray file and one subdirectory, and no manifest.json."""
    root = tmp_path / "empty"
    (root / "subdir").mkdir(parents=True)
    (root / "stray.txt").write_text("nothing here\n")
    (root / "subdir" / "notes.txt").write_text("nor here\n")
    return root


def test_fr2_an_empty_store_refuses_on_every_read_verb_but_runs(tmp_path: Path) -> None:
    root = make_empty_root(tmp_path)
    for label, argv in read_argvs(str(root), tmp_path / "out").items():
        if label == "runs":
            continue
        r = run_cli(argv)
        assert r.code == 2, (label, r)
        assert r.out == "", (label, r.out)
        assert r.err == empty_message(str(root), FROM_FLAG, verb_of(label)), (label, r.err)
        assert "unknown run" not in r.err, label


def test_fr3_runs_on_an_empty_store_exits_zero_says_so_on_stderr_and_keeps_its_stdout(tmp_path: Path) -> None:
    root = make_empty_root(tmp_path)
    r = run_cli(["--store", str(root), "runs"])
    assert r.code == 0, r
    assert r.out == f"store: {root}\n" + RUNS_HEADER, r.out
    assert r.err == empty_runs_note(str(root), FROM_FLAG), r.err


@pytest.mark.parametrize("how", ["flag", "env", "default", "empty env"])
def test_fr4_the_source_clause_is_the_resolution_that_happened_and_only_that_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    flag, env = tmp_path / "flag-root", tmp_path / "env-root"
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    if how == "flag":
        monkeypatch.setenv("PROOFLOAD_STORE", str(env))
        argv, root, source = ["--store", str(flag), "runs"], str(flag), FROM_FLAG
    elif how == "env":
        monkeypatch.setenv("PROOFLOAD_STORE", str(env))
        argv, root, source = ["runs"], str(env), FROM_ENV
    elif how == "default":
        argv, root, source = ["runs"], "proofload-runs", FROM_DEFAULT
    else:
        monkeypatch.setenv("PROOFLOAD_STORE", "")
        argv, root, source = ["runs"], "proofload-runs", FROM_DEFAULT
    r = run_cli(argv)
    assert r.code == 2 and r.out == "", r
    assert r.err == missing_message(root, source, "runs"), r.err
    assert [clause for clause in SOURCES if clause in r.err] == [source], r.err
    if how == "flag":
        assert str(env) not in r.err


@pytest.mark.parametrize("how", ["flag", "env", "default"])
def test_fr4_the_empty_store_messages_name_the_same_three_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    """E on a read verb and E-runs on ``runs``, each in each source form: FR4's clause for the two templates
    its own runs (on a missing root) cannot reach."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    if how == "flag":
        root, source, flags = tmp_path / "flag-root", FROM_FLAG, ["--store", str(tmp_path / "flag-root")]
    elif how == "env":
        root, source, flags = tmp_path / "env-root", FROM_ENV, []
        monkeypatch.setenv("PROOFLOAD_STORE", str(root))
    else:
        root, source, flags = tmp_path / "proofload-runs", FROM_DEFAULT, []
    root.mkdir()
    shown = str(root) if how != "default" else "proofload-runs"
    read = run_cli([*flags, "diff", GO1_A, GO1_B, "--event", "fell"])
    assert read.code == 2 and read.out == "" and read.err == empty_message(shown, source, "diff"), read
    listed_runs = run_cli([*flags, "runs"])
    assert listed_runs.code == 0 and listed_runs.err == empty_runs_note(shown, source), listed_runs
    assert [clause for clause in SOURCES if clause in read.err] == [source] == [clause for clause in SOURCES if clause in listed_runs.err]


@pytest.mark.parametrize("which", ["runs on go1", "runs on a one-run store", "inspect on go1"])
def test_fr5_a_populated_store_is_silent_on_stderr(tmp_path: Path, which: str) -> None:
    """Green before and after: the fence around FR1 to FR3, and no evidence the build did anything."""
    argv = {
        "runs on go1": ["--store", str(GO1_ROOT), "runs"],
        "runs on a one-run store": ["--store", str(one_run_store(tmp_path)), "runs"],
        "inspect on go1": ["--store", str(GO1_ROOT), "inspect", GO1_A, "--event", "fell", "--limit", "1"],
    }[which]
    r = run_cli(argv)
    assert r.code == 0 and r.err == "", r


def test_fr5_an_unknown_run_in_a_populated_store_keeps_its_message() -> None:
    """Green before and after. A7's Go1 verb digests (P7-10) carry the rest of FR5's clause."""
    r = run_cli(["--store", str(GO1_ROOT), "diff", GO1_A, "no-such-run", "--event", "fell"])
    assert r.code == 2 and r.out == "" and r.err == "error: unknown run: 'no-such-run'\n", r


def test_fr6_refusing_never_creates_the_missing_root(tmp_path: Path) -> None:
    root = tmp_path / "must-stay-absent"
    for label, argv in read_argvs(str(root), tmp_path / "out").items():
        r = run_cli(argv)
        assert r.code == 2, (label, r)
        assert not root.exists(), label
    assert listing(tmp_path) == [], listing(tmp_path)


def test_fr6_refusing_and_listing_never_touch_an_empty_root(tmp_path: Path) -> None:
    root = make_empty_root(tmp_path)
    before = listing(root)
    for label, argv in read_argvs(str(root), tmp_path / "out").items():
        r = run_cli(argv)
        assert r.code == (0 if label == "runs" else 2), (label, r)
        assert r.err != "", label
        assert listing(root) == before, label
    assert listing(tmp_path) == ["empty", *[f"empty/{p}" for p in before]], listing(tmp_path)


def test_fr6_sweep_is_never_gated_and_creates_the_store(tmp_path: Path) -> None:
    """Green before and after: ``sweep`` is the verb that makes a store, so no check may precede it."""
    for root in (tmp_path / "missing-root", make_empty_root(tmp_path)):
        r = run_cli(["--store", str(root), "sweep", str(QUICKSTART), "--target", ROLLOUT, "--yes"])
        assert r.code == 0, r
        assert len(Store(root).runs()) == 1, root


@pytest.mark.parametrize("name", ["with a space", "it's $HOME"])
def test_fr7_the_create_line_is_a_command_that_survives_a_shell(tmp_path: Path, name: str) -> None:
    root = tmp_path / name
    r = run_cli(["--store", str(root), "diff", GO1_A, GO1_B, "--event", "fell"])
    assert r.code == 2, r
    assert command_from(r.err, "to create one there") == ["proofload", "--store", str(root), "sweep", "SPEC.toml", "--target", "pkg.module:rollout"], r.err
    assert r.err == missing_message(str(root), FROM_FLAG, "diff"), r.err


def test_fr7_the_empty_store_hint_lines_are_commands_that_survive_a_shell(tmp_path: Path) -> None:
    root = tmp_path / "an empty store"
    root.mkdir()
    expected = ["proofload", "--store", str(root), "sweep", "SPEC.toml", "--target", "pkg.module:rollout"]
    read = run_cli(["--store", str(root), "check", GO1_A, GO1_B, "--event", "fell"])
    assert read.code == 2 and command_from(read.err, "to write the first run there") == expected, read.err
    listed = run_cli(["--store", str(root), "runs"])
    assert listed.code == 0 and command_from(listed.err, "to write the first run there") == expected, listed.err
    assert read.err == empty_message(str(root), FROM_FLAG, "check") and listed.err == empty_runs_note(str(root), FROM_FLAG)


# ---------- FR8 to FR13: E3, the missing flag ----------


def go1_argv(label: str, *extra: str) -> list[str]:
    return ["--store", str(GO1_ROOT), *E3_GO1[label][0], *extra]


@pytest.mark.parametrize("label", ["report pair, no --x", "report single run, no --x"])
def test_fr8_report_without_x_lists_the_axes_and_events_instead_of_failing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, label: str) -> None:
    monkeypatch.chdir(tmp_path)
    r = run_cli(go1_argv(label))
    assert r.code == 2 and r.out == "", r
    assert r.err == E3_GO1[label][1], r.err
    assert "usage:" not in r.err
    assert listing(tmp_path) == [], "the default --out directory was created"


def test_fr8_report_without_x_lists_on_the_mock_pair_too(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mock_pair: MockPair) -> None:
    monkeypatch.chdir(tmp_path)
    argv, expected = mock_e3(mock_pair)
    r = run_cli(argv)
    assert r.code == 2 and r.out == "" and r.err == expected, r
    assert "usage:" not in r.err
    assert listing(tmp_path) == []


@pytest.mark.parametrize("as_json", [False, True], ids=["plain", "json"])
@pytest.mark.parametrize("label", SERVE_ROWS)
def test_fr9_serve_without_x_or_event_lists_instead_of_failing(monkeypatch: pytest.MonkeyPatch, label: str, as_json: bool) -> None:
    calls = arm_tripwires(monkeypatch, "serve_page")
    r = run_cli(go1_argv(label, *(["--json"] if as_json else [])))
    assert r.code == 2 and r.out == "", r
    assert r.err == E3_GO1[label][1], r.err
    assert calls == []


@pytest.mark.parametrize("label", ["check, no --event", "inspect, no --event"])
def test_fr10_check_and_inspect_without_event_list_and_never_suggest(label: str) -> None:
    r = run_cli(go1_argv(label))
    assert r.code == 2 and r.out == "", r
    assert r.err == E3_GO1[label][1], r.err
    assert "Inferred events" not in r.err and "Inferred events" not in r.out


TIMEOUT_CELLS = [({"cell": "c0"}, {"fell": 4, "ok": 6}, {"timeout": 3})]
QUIET_CELLS = [({"cell": "c0"}, {"fell": 4, "ok": 6}, {})]
OUTCOME_TIMEOUT_CELLS = [({"cell": "c0"}, {"fell": 4, "timeout": 6}, {"timeout": 3})]


@pytest.mark.parametrize(
    ("cells", "events"),
    [(TIMEOUT_CELLS, "fell, ok, timeout"), (QUIET_CELLS, "fell, ok"), (OUTCOME_TIMEOUT_CELLS, "fell, timeout")],
    ids=["timed-out rows and timeout is not an outcome", "no timed-out rows", "timed-out rows and timeout is already an outcome"],
)
def test_fr10_inspect_adds_timeout_only_when_rows_timed_out_and_it_is_not_already_an_outcome(tmp_path: Path, cells: list[Any], events: str) -> None:
    write_run(Store(tmp_path), "t1", cells)
    r = run_cli(["--store", str(tmp_path), "inspect", "t1"])
    assert r.code == 2 and r.out == "", r
    assert r.err == f"error: inspect requires --event NAME, which was not given. t1 carries:\n  events: {events}\n", r.err


# FR11: the listed vocabulary is the stored vocabulary.

KEYS = ("a", "b", "c", "d")
LABELS = ("fell", "ok", "late", "slow")
ERRORS = ("timeout", "boom")
PROPERTY = settings(max_examples=60, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])


@st.composite
def run_specs(draw: st.DrawFn) -> list[tuple[dict[str, Any], str]]:
    """The rows of one run: a config over 1-4 of the four keys, and an outcome label or an error."""
    keys = draw(st.lists(st.sampled_from(KEYS), min_size=1, max_size=4, unique=True))
    labels = draw(st.lists(st.sampled_from(LABELS), min_size=1, max_size=4, unique=True))
    rows = draw(st.lists(st.tuples(st.sampled_from([0, 1]), st.sampled_from([*labels, *[f"!{e}" for e in ERRORS]])), min_size=1, max_size=8))
    return [({key: value for key in keys}, name) for value, name in rows]


def write_spec(store: Store, run_id: str, rows: Sequence[tuple[dict[str, Any], str]], *, axis_types: Mapping[str, str] | None = None) -> None:
    store.create_run(manifest(run_id, axis_types=axis_types))
    seen: dict[str, int] = {}
    records = []
    for config, name in rows:
        h = config_hash(config)
        k = seen[h] = seen.get(h, -1) + 1
        if name.startswith("!"):
            records.append(EpisodeRecord.errored(run_id=run_id, config=config, seed=seed_of(config, k), replicate_index=k, error=name[1:], wall_time=0.0))
        else:
            records.append(EpisodeRecord.from_episode(
                Episode(outcome=name, t=3.0, horizon=HORIZON), run_id=run_id, config=config, seed=seed_of(config, k), replicate_index=k, wall_time=0.0,
            ))
    store.append(run_id, records)
    store.mark_complete(run_id)


def listed(err: str, label: str) -> str:
    lines = [line for line in err.splitlines() if line.startswith(f"  {label}: ")]
    assert len(lines) == 1, (label, err)
    return lines[0].removeprefix(f"  {label}: ")


@PROPERTY
@given(a=run_specs(), b=run_specs())
def test_fr11_the_listed_axes_and_events_are_the_stored_ones(a: list[Any], b: list[Any]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(tmp)
        write_spec(store, "ra", a)
        write_spec(store, "rb", b)
        fa, fb = store.read("ra", meta=False), store.read("rb", meta=False)
        axes = sorted({str(k) for frame in (fa, fb) for config in frame["config"] for k in config})
        events = list(competing_set(fa, fb))
        for verb, argv in (("report", ["report", "ra", "rb"]), ("check", ["check", "ra", "rb"])):
            r = run_cli(["--store", tmp, *argv])
            assert r.code == 2 and r.out == "", (verb, r)
            assert listed(r.err, "events") == (", ".join(events) or "none stored"), (verb, r.err)
            if verb == "report":
                assert listed(r.err, "axes") == ", ".join(axes), r.err
            else:
                assert "  axes:" not in r.err


@PROPERTY
@given(a=run_specs())
def test_fr11_the_listed_events_of_a_single_run_are_its_outcomes_and_timeout_only_when_a_row_timed_out(a: list[Any]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(tmp)
        write_spec(store, "ra", a)
        frame = store.read("ra", meta=False)
        events = set(competing_set(frame)) | ({"timeout"} if store.tally("ra").timed_out else set())
        r = run_cli(["--store", tmp, "inspect", "ra"])
        assert r.code == 2 and r.out == "", r
        assert listed(r.err, "events") == (", ".join(sorted(events)) or "none stored"), r.err


def known_keys_of(err: str) -> list[str]:
    match = re.search(r"known keys: (\[.*\])", err)
    assert match, err
    return list(ast.literal_eval(match.group(1)))


def present_of(err: str) -> str:
    match = re.search(r"Present: (.*)\.$", err.strip())
    assert match, err
    return match.group(1)


def pair_of(which: str, request: pytest.FixtureRequest) -> tuple[list[str], str, str, str]:
    """``--store``, both run ids and a known event, for Go1 or for the mock pair."""
    if which == "go1":
        return ["--store", str(GO1_ROOT)], GO1_A, GO1_B, "fell"
    pair: MockPair = request.getfixturevalue("mock_pair")
    return ["--store", str(pair.root)], pair.a, pair.b, "violated"


@pytest.mark.parametrize("which", ["go1", "mock"])
def test_fr11_the_listed_axes_equal_the_known_keys_the_axis_error_prints(which: str, request: pytest.FixtureRequest) -> None:
    """Both lists are read off live output: E3's ``axes:`` line, and the ``known keys`` of the error a wrong ``--x``
    provokes. The two agree wherever every config is compared."""
    store, a, b, event = pair_of(which, request)
    listing_run = run_cli([*store, "report", a, b])
    assert listing_run.code == 2, listing_run
    wrong = run_cli([*store, "serve", a, b, "--event", event, "--x", "nope", "--permutations", "50"])
    assert wrong.code == 2, wrong
    assert ", ".join(known_keys_of(wrong.err)) == listed(listing_run.err, "axes")


@pytest.mark.parametrize("which", ["go1", "mock"])
def test_fr11_the_listed_events_equal_the_present_list_the_unknown_event_error_prints(which: str, request: pytest.FixtureRequest) -> None:
    store, a, b, _ = pair_of(which, request)
    listing_run = run_cli([*store, "check", a, b])
    assert listing_run.code == 2, listing_run
    wrong = run_cli([*store, "check", a, b, "--event", "nope"])
    assert wrong.code == 2, wrong
    assert present_of(wrong.err) == listed(listing_run.err, "events")


def test_fr11_the_axes_are_the_config_keys_and_never_the_manifests_axis_types(tmp_path: Path) -> None:
    """The one fixture that tells D8 from its mutant: no store ``sweep`` writes can disagree with itself."""
    store = Store(tmp_path)
    for run_id in ("dis-a", "dis-b"):
        write_run(
            store, run_id, [({"real_a": 0, "real_b": 1}, {"fell": 2, "ok": 3}, {})],
            axis_types={"declared_only": "categorical"},
        )
    r = run_cli(["--store", str(tmp_path), "report", "dis-a", "dis-b"])
    assert r.code == 2 and r.out == "", r
    assert r.err == (
        "error: report requires --x AXIS, which was not given. dis-a and dis-b carry:\n"
        "  axes: real_a, real_b\n"
        "  events: fell, ok\n"
    ), r.err


def e3_cases(pair: MockPair) -> list[tuple[str, list[str], str]]:
    cases = [(label, ["--store", str(GO1_ROOT), *argv], err) for label, (argv, err) in E3_GO1.items()]
    argv, err = mock_e3(pair)
    return [*cases, ("mock report pair, no --x", argv, err)]


def test_fr12_the_listing_does_no_work(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mock_pair: MockPair) -> None:
    monkeypatch.chdir(tmp_path)
    calls = arm_tripwires(monkeypatch, *WORK_NAMES)
    for label, argv, expected in e3_cases(mock_pair):
        r = run_cli(argv)
        assert r.code == 2 and r.out == "" and r.err == expected, (label, r)
    assert calls == [], calls
    assert listing(tmp_path) == []


@pytest.mark.parametrize("label", ["report pair, no --x", "report single run, no --x"])
def test_fr12_a_non_empty_out_does_not_pre_empt_the_listing(tmp_path: Path, label: str) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("already here\n")
    r = run_cli(go1_argv(label, "--out", str(out)))
    assert r.code == 2 and r.out == "" and r.err == E3_GO1[label][1], r
    assert "--out" not in r.err
    assert listing(out) == ["keep.txt"]


ARITY = {
    "report": ("error: report takes one or two run ids, got 3: " + REPORT_FORMS + "\n", ["report", GO1_A, GO1_B, GO1_A]),
    "serve": ("error: serve takes two run ids, got 1: " + SERVE_FORM + "\n", ["serve", GO1_A]),
}
BARE = {"report": ["report", GO1_A, GO1_B], "serve": ["serve", GO1_A, GO1_B], "check": ["check", GO1_A, GO1_B], "inspect": ["inspect", GO1_A]}
BARE_UNKNOWN = {"report": ["report", GO1_A, "no-such-run"], "serve": ["serve", GO1_A, "no-such-run"], "check": ["check", GO1_A, "no-such-run"], "inspect": ["inspect", "no-such-run"]}


@pytest.mark.parametrize("verb", ["report", "serve", "check", "inspect"])
def test_fr12_a_missing_store_outranks_a_missing_flag(tmp_path: Path, verb: str) -> None:
    root = str(tmp_path / "nowhere")
    r = run_cli(["--store", root, *BARE[verb]])
    assert r.code == 2 and r.out == "" and r.err == missing_message(root, FROM_FLAG, verb), r


@pytest.mark.parametrize("verb", ["report", "serve", "check", "inspect"])
def test_fr12_an_empty_store_outranks_a_missing_flag(tmp_path: Path, verb: str) -> None:
    root = make_empty_root(tmp_path)
    r = run_cli(["--store", str(root), *BARE[verb]])
    assert r.code == 2 and r.out == "" and r.err == empty_message(str(root), FROM_FLAG, verb), r


@pytest.mark.parametrize("verb", ["report", "serve"])
def test_fr12_a_wrong_arity_outranks_a_missing_flag(verb: str) -> None:
    message, argv = ARITY[verb]
    r = run_cli(["--store", str(GO1_ROOT), *argv])
    assert r.code == 2 and r.out == "" and r.err == message, r


@pytest.mark.parametrize("verb", ["report", "serve", "check", "inspect"])
def test_fr12_an_unknown_run_outranks_a_missing_flag(verb: str) -> None:
    r = run_cli(["--store", str(GO1_ROOT), *BARE_UNKNOWN[verb]])
    assert r.code == 2 and r.out == "" and r.err == "error: unknown run: 'no-such-run'\n", r


# FR13: the parser.


def help_text(verb: str) -> str:
    r = run_cli([verb, "--help"])
    assert r.code == 0, r
    return r.out


def usage_of(text: str) -> str:
    block = text.split("\n\n", 1)[0]
    assert block.startswith("usage:"), block
    return " ".join(block.split())


def help_entries(text: str) -> dict[str, str]:
    """Each long option's help entry, its wrapped lines joined and its spacing collapsed."""
    entries: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        head = re.match(r"^  (--[a-z][a-z-]*)", line)
        if head:
            current = head.group(1)
            entries[current] = [line.strip()]
        elif current is not None and line.startswith("    "):
            entries[current].append(line.strip())
        else:
            current = None
    return {flag: " ".join(" ".join(parts).split()) for flag, parts in entries.items()}


@pytest.mark.parametrize(("verb", "token"), [("report", "[--x AXIS]"), ("serve", "[--x AXIS]"), ("inspect", "[--event NAME]")])
def test_fr13_the_usage_line_no_longer_requires_the_flag(verb: str, token: str) -> None:
    assert token in usage_of(help_text(verb)), usage_of(help_text(verb))


@pytest.mark.parametrize(("verb", "flag"), [("report", "--x"), ("serve", "--x"), ("inspect", "--event")])
def test_fr13_the_help_says_what_omitting_the_flag_does(verb: str, flag: str) -> None:
    assert "omitted: lists" in help_entries(help_text(verb))[flag], help_entries(help_text(verb))[flag]


FLAG_SETS = {
    "report": {
        "--event", "--method", "--q", "--methods", "--permutations", "--seed", "--by", "--max-group-mde", "--depth",
        "--x", "--y", "--fix", "--horizon", "--theme", "--top-n", "--forest", "--out", "--title", "--force",
        "--paired",
    },
    "serve": {
        "--event", "--method", "--q", "--permutations", "--seed", "--by", "--max-group-mde", "--depth",
        "--x", "--y", "--fix", "--theme", "--top-n", "--forest", "--title", "--json",
    },
    "inspect": {"--event", "--where", "--limit"},
}


@pytest.mark.parametrize("verb", ["report", "serve", "inspect"])
def test_fr13_no_flag_is_added_or_removed(verb: str) -> None:
    """Green before and after (with V30 and W1): the parser edit removes ``required`` and nothing else."""
    flags = set(help_entries(help_text(verb))) - {"--help"}
    assert flags == FLAG_SETS[verb], flags ^ FLAG_SETS[verb]


def test_fr13_the_five_tree_flags_keep_diffs_help_on_report_and_serve() -> None:
    """Green before and after (with R13 and W11)."""
    diff_help = help_entries(help_text("diff"))
    for verb in ("report", "serve"):
        entries = help_entries(help_text(verb))
        for flag in ("--permutations", "--seed", "--by", "--max-group-mde", "--depth"):
            assert entries[flag] == diff_help[flag], (verb, flag)


# ---------- FR14 to FR17: E4, the inference line ----------


def go1_multi(events: Sequence[str] | None) -> MultiDiffResult:
    store = Store(GO1_ROOT)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnpairedAnalysis)
        return multi_diff(
            store.read(GO1_A, meta=False), store.read(GO1_B, meta=False),
            events=events, manifest_a=store.manifest(GO1_A), manifest_b=store.manifest(GO1_B),
        )


def a14_multi(events: Sequence[str] | None) -> MultiDiffResult:
    """A14's frames: two cells of 32 rows, ``completed`` the most frequent outcome, events ``violated, timeout``."""
    a = [({"cell": "c1"}, {"completed": 20, "violated": 8, "timeout": 4}, {}), ({"cell": "c2"}, {"completed": 24, "violated": 6, "timeout": 2}, {})]
    b = [({"cell": "c1"}, {"completed": 16, "violated": 12, "timeout": 4}, {}), ({"cell": "c2"}, {"completed": 24, "violated": 6, "timeout": 2}, {})]
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(tmp)
        write_run(store, "a", a, salt="salt-a")
        write_run(store, "b", b, salt="salt-b")
        return multi_diff(
            store.read("a", meta=False), store.read("b", meta=False), events=events,
            manifest_a=store.manifest("a"), manifest_b=store.manifest("b"),
        )


@pytest.fixture(scope="module")
def go1_inferred() -> MultiDiffResult:
    return go1_multi(None)


@dataclass(frozen=True)
class Ran:
    result: Result
    out_dir: Path


@pytest.fixture(scope="module")
def go1_ran(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Ran]:
    """Go1's verbs on the pair and on one run, each run once: inferred, one event, two events."""
    base = tmp_path_factory.mktemp("go1-ran")
    store = ["--store", str(GO1_ROOT)]
    knobs = ["--permutations", "50"]
    events = {"inferred": [], "fell": ["--event", "fell"], "both": ["--event", "fell", "--event", "survived"]}
    ran: dict[str, Ran] = {}
    for kind, extra in events.items():
        for verb in ("diff", "report", "single", "check"):
            if (verb == "check" and kind == "inferred") or (verb == "single" and kind != "inferred"):
                continue
            out = base / f"{verb}-{kind}"
            argv = {
                "diff": ["diff", GO1_A, GO1_B, *extra, *knobs],
                "report": ["report", GO1_A, GO1_B, *extra, "--x", GO1_X, "--y", GO1_Y, *knobs, "--out", str(out)],
                "single": ["report", GO1_A, *extra, "--x", GO1_X, "--y", GO1_Y, "--out", str(out)],
                "check": ["check", GO1_A, GO1_B, *extra],
            }[verb]
            r = run_cli([*store, *argv])
            assert r.code in ((0, 1) if verb == "check" else (0,)), (verb, kind, r)  # a gate that ran passes or fails
            ran[f"{verb} {kind}"] = Ran(r, out)
    return ran


def first_line(r: Result) -> str:
    return r.out.splitlines()[0]


@pytest.mark.parametrize("which", ["go1", "a14"])
def test_fr14_to_markdown_opens_with_the_plain_line_and_it_carries_no_parenthesis(which: str, go1_inferred: MultiDiffResult) -> None:
    multi = go1_inferred if which == "go1" else a14_multi(None)
    assert multi.inferred
    line = multi.to_markdown().splitlines()[0]
    assert line == inference_line(multi.events, str(multi.non_event)), line
    assert "(" not in line and ")" not in line, line
    assert line == (GO1_LINE if which == "go1" else A14_LINE), line


def svg_texts(path: Path) -> list[str]:
    return ["".join(el.itertext()) for el in ET.fromstring(path.read_text()).iter() if el.tag.endswith("text")]


class ParagraphTexts(HTMLParser):
    """The text of every element of a page, keyed by the innermost open tag."""

    VOID = {"br", "meta", "img", "hr", "input", "link", "col", "area", "base", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.chunks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        while self.stack and self.stack.pop() != tag:
            pass

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.chunks.append((self.stack[-1] if self.stack else "", data.strip()))


def html_chunks(path: Path) -> list[tuple[str, str]]:
    parser = ParagraphTexts()
    parser.feed(path.read_text())
    parser.close()
    return parser.chunks


def marked_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(MARKER)]


def test_fr14_the_plain_line_is_line_one_of_diff_stdout(go1_ran: dict[str, Ran]) -> None:
    assert first_line(go1_ran["diff inferred"].result) == GO1_LINE


def test_fr14_the_plain_line_is_line_one_of_report_stdout(go1_ran: dict[str, Ran]) -> None:
    assert first_line(go1_ran["report inferred"].result) == GO1_LINE


def test_fr14_the_plain_line_is_in_report_md(go1_ran: dict[str, Ran]) -> None:
    assert marked_lines((go1_ran["report inferred"].out_dir / "report.md").read_text()) == [GO1_LINE]


def test_fr14_the_plain_line_is_the_muted_header_of_heatmap_svg(go1_ran: dict[str, Ran]) -> None:
    texts = svg_texts(go1_ran["report inferred"].out_dir / "heatmap.svg")
    assert [t for t in texts if t.startswith(MARKER)] == [GO1_LINE], texts[:6]


def test_fr14_the_plain_line_is_a_paragraph_of_receipt_html(go1_ran: dict[str, Ran]) -> None:
    chunks = html_chunks(go1_ran["report inferred"].out_dir / "receipt.html")
    assert [text for tag, text in chunks if tag == "p" and text.startswith(MARKER)] == [GO1_LINE]


def test_fr15_the_single_run_report_says_the_same_thing_as_the_pair(go1_ran: dict[str, Ran]) -> None:
    single, pair = go1_ran["single inferred"].result, go1_ran["report inferred"].result
    assert first_line(single) == GO1_LINE == first_line(pair)


def texts_of(ran: Ran) -> dict[str, list[str]]:
    """Every text a report writes, as lines: ``report.md``, the SVG's ``<text>`` and the page's chunks."""
    return {
        "report.md": (ran.out_dir / "report.md").read_text().splitlines(),
        "heatmap.svg": svg_texts(ran.out_dir / "heatmap.svg"),
        "receipt.html": [text for _, text in html_chunks(ran.out_dir / "receipt.html")],
    }


@pytest.mark.parametrize("kind", ["fell", "both"])
@pytest.mark.parametrize("verb", ["diff", "report", "check"])
def test_fr16_given_events_print_no_inference_line_and_the_marker_matches_where_it_should(go1_ran: dict[str, Ran], verb: str, kind: str) -> None:
    given = go1_ran[f"{verb} {kind}"]
    assert marked_lines(given.result.out) == [], given.result.out
    if verb == "report":
        for name, lines in texts_of(given).items():
            assert [line for line in lines if line.startswith(MARKER)] == [], name
    # The positive control, on real output: the same pair without --event, same verb (check never infers).
    control = go1_ran["diff inferred" if verb == "check" else f"{verb} inferred"]
    assert first_line(control.result).startswith(MARKER)
    if verb == "report":
        for name, lines in texts_of(control).items():
            found = [line for line in lines if line.startswith(MARKER)]
            assert found and set(found) == {GO1_LINE}, (name, found)


def test_fr17_to_json_carries_the_same_keys_and_the_same_inference_fields(go1_inferred: MultiDiffResult) -> None:
    inferred, explicit = go1_inferred.to_json(), go1_multi(["fell"]).to_json()
    assert sorted(inferred) == MULTI_JSON_KEYS == sorted(explicit)
    assert (inferred["inferred"], inferred["non_event"], inferred["events"]) == (True, "fell", ["survived"])
    assert (explicit["inferred"], explicit["non_event"], explicit["events"]) == (False, None, ["fell"])


def test_fr17_infer_events_returns_what_it_returned(go1_inferred: MultiDiffResult) -> None:
    store = Store(GO1_ROOT)
    a, b = store.read(GO1_A, meta=False), store.read(GO1_B, meta=False)
    assert infer_events(a, b) == (("survived",), "fell") == infer_events(a, a.iloc[0:0])
    assert (go1_inferred.events, go1_inferred.non_event) == (("survived",), "fell")
    multi = a14_multi(None)
    assert (multi.events, multi.non_event) == (("violated", "timeout"), "completed")


@pytest.mark.parametrize(("kind", "line"), [("inferred", "- inferred: true"), ("fell", "- inferred: false")])
def test_fr17_report_md_provenance_still_prints_inferred(go1_ran: dict[str, Ran], kind: str, line: str) -> None:
    md = (go1_ran[f"report {kind}"].out_dir / "report.md").read_text().splitlines()
    assert line in md, [m for m in md if "inferred" in m]


# The resolver and the digest are restated, never imported (ADR-077's shape).


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


def digest_excluding(path: Path, regions: Sequence[str]) -> str:
    """The file's sha256 with each region's ``lineno`` to ``end_lineno`` removed, whole lines; the ``def``
    line is the region's first, so a decorator above it stays guarded."""
    source = path.read_bytes()
    spans = [(n.lineno, n.end_lineno or 0) for n in (resolve_region(ast.parse(source), q) for q in regions)]
    kept = [line for i, line in enumerate(source.decode().splitlines(keepends=True), start=1) if not any(lo <= i <= hi for lo, hi in spans)]
    return hashlib.sha256("".join(kept).encode()).hexdigest()


def test_fr17_diff_py_outside_the_one_method_is_the_dispatch_commits() -> None:
    """Green before and after, red on any edit to ``diff.py`` outside ``MultiDiffResult.to_markdown``. The
    region is ``("MultiDiffResult", "to_markdown")`` and not the bare function: ``DiffResult`` has one too."""
    assert digest_excluding(PACKAGE / "diff.py", ["MultiDiffResult.to_markdown"]) == DIFF_OUTSIDE_TO_MARKDOWN_SHA256


def test_fr17_report_viewer_store_and_tree_are_byte_untouched() -> None:
    """Green before and after: the inference line reaches every surface through ``diff.py`` alone."""
    assert {name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() for name in UNTOUCHED_FILE_SHA256} == UNTOUCHED_FILE_SHA256


# FR18: no new surface.


def module_level_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def imports_of(path: Path) -> set[tuple[str | None, str | None]]:
    found: set[tuple[str | None, str | None]] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update((alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.update((node.module, alias.name) for alias in node.names)
    return found


def test_fr18_all_is_main_and_diff_py_gains_no_module_level_name() -> None:
    """Green before and after: D11's template lives inside the one method, so no helper name is added."""
    assert cli.__all__ == ["main"]
    assert module_level_names(PACKAGE / "diff.py") == DIFF_MODULE_NAMES, module_level_names(PACKAGE / "diff.py") ^ DIFF_MODULE_NAMES


def test_fr18_cli_py_imports_gain_shlex_and_nothing_else() -> None:
    """Green before and after (L3, U14, I21 and the four BinOp guards carry the rest of FR18): ``shlex`` may
    arrive, and no other import may."""
    now = imports_of(PACKAGE / "cli.py")
    assert now - CLI_IMPORTS <= {("shlex", None)}, now - CLI_IMPORTS
    assert CLI_IMPORTS - now == set(), CLI_IMPORTS - now


# ---------- FR19: check never passes on a missing argument ----------

CHECK_VARIANTS: list[tuple[str, ...]] = [
    (), ("--fail-on", "worse"), ("--fail-on", "any"), ("--method", "fisher_bh"), ("--method", "mcnemar_bh"),
    ("--method", "logrank_bh"), ("--q", "0.5"), ("--fail-on", "any", "--method", "mcnemar_bh", "--q", "0.5"),
]


@dataclass(frozen=True)
class GatePair:
    root: Path
    a: str
    b: str
    events: str

    def argv(self, *extra: str) -> list[str]:
        return ["--store", str(self.root), "check", self.a, self.b, *extra]


@pytest.fixture(scope="module")
def gate_pairs(tmp_path_factory: pytest.TempPathFactory, mock_pair: MockPair) -> dict[str, GatePair]:
    """Go1, the mock pair, and two synthetic pairs: one whose gate PASSes on ``--event fell`` (no cell worse),
    one whose gate FAILs on it (one cell worse, I14's shape). Same salt and seeds, so all four are pairable."""
    root = tmp_path_factory.mktemp("gate-pairs")
    store = Store(root)
    fell_run(store, "pass-a", {1.0: 10, 2.0: 20})
    fell_run(store, "pass-b", {1.0: 10, 2.0: 20})
    fell_run(store, "fail-a", {1.0: 0, 2.0: 8})
    fell_run(store, "fail-b", {1.0: 24, 2.0: 8})
    return {
        "go1": GatePair(GO1_ROOT, GO1_A, GO1_B, "fell, survived"),
        "mock": GatePair(mock_pair.root, mock_pair.a, mock_pair.b, "completed, timeout, violated"),
        "pass": GatePair(root, "pass-a", "pass-b", "fell, survived"),
        "fail": GatePair(root, "fail-a", "fail-b", "fell, survived"),
    }


def test_fr19_the_gate_pairs_pass_and_fail_when_the_gate_runs(gate_pairs: dict[str, GatePair]) -> None:
    """Green before and after: the controls that make FR19's crossing mean something. Were ``check`` to run
    its gate on these pairs, one would exit 0 and one would exit 1, and a listing that fell through to the
    gate would show it."""
    assert run_cli(gate_pairs["pass"].argv("--event", "fell")).code == 0
    assert run_cli(gate_pairs["fail"].argv("--event", "fell")).code == 1
    assert run_cli(gate_pairs["go1"].argv("--event", "fell")).code == 0
    store = Store(gate_pairs["fail"].root)
    events, non_event = infer_events(store.read("fail-a", meta=False), store.read("fail-b", meta=False))
    assert (events, non_event) == (("fell",), "survived"), "the FAIL pair infers fell, so a gate run on the inferred set FAILs too"
    store = Store(gate_pairs["pass"].root)
    assert infer_events(store.read("pass-a", meta=False), store.read("pass-b", meta=False)) == (("fell",), "survived")


@pytest.mark.parametrize("name", ["go1", "mock", "pass", "fail"])
def test_fr19_check_that_lists_puts_the_list_on_stderr_and_none_of_it_on_stdout(gate_pairs: dict[str, GatePair], name: str) -> None:
    """The red half: the listing itself, on stderr, for every crossing."""
    pair = gate_pairs[name]
    for extra in CHECK_VARIANTS:
        r = run_cli(pair.argv(*extra))
        assert f"  events: {pair.events}" in r.err.splitlines(), (extra, r.err)
        assert "  events:" not in r.out and "PASS" not in r.out and "FAIL" not in r.out, (extra, r.out)


@pytest.mark.parametrize("name", ["go1", "mock", "pass", "fail"])
def test_fr19_check_that_lists_exits_two_never_zero_or_one_and_never_reaches_the_gate(
    gate_pairs: dict[str, GatePair], monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """The green half (today's refusal already has every clause): exit 2, and separately not 0 and not 1
    (1 is a FAIL, a gate that ran); stdout empty, no PASS, FAIL or headline; and the result is identical with
    ``MultiDiffResult.check`` and ``cli.multi_diff`` raising."""
    pair = gate_pairs[name]
    plain = [run_cli(pair.argv(*extra)) for extra in CHECK_VARIANTS]
    calls = arm_gate_tripwire(monkeypatch)
    armed = [run_cli(pair.argv(*extra)) for extra in CHECK_VARIANTS]
    assert calls == [], calls
    assert armed == plain
    for extra, r in zip(CHECK_VARIANTS, plain, strict=True):
        assert r.code == 2, (extra, r)
        assert r.code != 0, (extra, "a listing must never pass")
        assert r.code != 1, (extra, "1 is a FAIL: the gate ran")
        assert r.out == "", (extra, r.out)
        assert r.err != "", extra


# ---------- FR20: the single-run report's own inference line ----------


def single_run_argv(root: Path, run: str, out: Path, *extra: str, x: str = GO1_X, y: str = GO1_Y) -> list[str]:
    return ["--store", str(root), "report", run, "--x", x, "--y", y, "--out", str(out), *extra]


@pytest.mark.parametrize("which", ["go1", "mock"])
def test_fr20_the_single_run_line_is_the_plain_template_and_precedes_the_summary_line(tmp_path: Path, mock_pair: MockPair, which: str) -> None:
    if which == "go1":
        root, run, argv = GO1_ROOT, GO1_A, single_run_argv(GO1_ROOT, GO1_A, tmp_path / "out")
    else:
        root, run = mock_pair.root, mock_pair.a
        argv = single_run_argv(root, run, tmp_path / "out", x="tool_fail_rate", y="task_id")
    frame = Store(root).read(run, meta=False)
    events, non_event = infer_events(frame, frame.iloc[0:0])
    r = run_cli(argv)
    assert r.code == 0, r
    lines = r.out.splitlines()
    assert lines[0] == inference_line(events, non_event), lines[:2]
    assert "(" not in lines[0] and ")" not in lines[0], lines[0]
    assert lines[1].startswith(f"{run}: survival report over {', '.join(events)} at horizon "), lines[:2]
    assert lines[0] == (GO1_LINE if which == "go1" else A14_LINE)


@pytest.mark.parametrize("kind", ["one event", "repeated events"])
def test_fr20_a_single_run_with_given_events_prints_no_inference_line(tmp_path: Path, mock_pair: MockPair, kind: str) -> None:
    """Green before and after, with its positive control in the same test: the same run's inferred line."""
    given = ["--event", "violated"] if kind == "one event" else ["--event", "violated", "--event", "timeout"]

    def argv(*extra: str) -> list[str]:
        return single_run_argv(mock_pair.root, mock_pair.a, tmp_path / f"out-{len(extra)}", *extra, x="tool_fail_rate", y="task_id")

    control = run_cli(argv())
    assert control.code == 0 and control.out.splitlines()[0].startswith(MARKER), control.out
    explicit = run_cli(argv(*given))
    assert explicit.code == 0, explicit
    assert marked_lines(explicit.out) == [], explicit.out


def test_fr20_a_tie_on_a_single_run_refuses_byte_for_byte_as_before_with_nothing_ahead_of_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Green before and after: the refusal (``_report_run``) and its exact words are not this packet's to move."""
    monkeypatch.chdir(tmp_path)
    write_run(Store(tmp_path / "store"), "tie", [({"cell": "c"}, {"fell": 16, "survived": 16}, {})])
    r = run_cli(["--store", str(tmp_path / "store"), "report", "tie", "--x", "cell"])
    assert r.code == 2 and r.out == "", r
    assert r.err == (
        "error: cannot infer the event set: most frequent outcome is tied between ['fell', 'survived'] at 16 rows each; "
        "outcome counts: {'fell': 16, 'survived': 16}; pass events= explicitly; outcome counts: fell=16, survived=16; "
        "pass --event NAME (repeatable)\n"
    ), r.err
    assert listing(tmp_path) == ["store", *[f"store/{p}" for p in listing(tmp_path / "store")]]

