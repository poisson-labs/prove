"""LS -- the local serve pass: the frozen tests for LS1-LS20 and the ruled LS21.

**Frozen 2026-09-22.** Approved: the invariant-to-test table, the mutant-to-test table and the
conventions below (seven yes); the freeze is this docstring and nothing else. The mutation pass was
re-run control-first after the freeze; its table is the handoff's. The build works against this
file and does not edit it.

Written from "Prove -- Spec Local Serve Pass" section 4 against ``f7af030`` (2026-09-22), on the
update commit that moves the schema pins to ``proofload.viewpair/6``, the top-level key tuple to
fourteen with ``summary`` eighth, ``PANEL_KEYS`` to fifteen, ``HOLE_KEYS`` to ten, the ``<h2>``
sequence to ``Summary`` first and ``Run pair`` thirteenth, and the two-event complementary pair's trade line to the
complement sentence. Phase B changes ``src/proofload/diff.py`` (``complementary_events``,
``trade_line``), ``src/proofload/report.py`` (``_wrap`` and the four wrapped texts,
``MultiReport.complement``), the new ``src/proofload/plain.py``, ``src/proofload/viewer.py`` (the
inert rule, the docstring and both refusals, the hole's ``where``, the holes block, the ``summary``
key, the schema, the page order, the unverified tails) and ``src/proofload/cli.py`` (help and two
refusal wordings) against this file, and does not edit it. Phase C re-mints every rendered-output
digest the build moves; none is minted here.

**``proofload.plain`` and the changed surfaces are reached inside test bodies** through ``plain()``
and ``viewer()``, so this file collects on the bare tree, its own tests fail there, and every other
test in the repo still reports. Source is read through ``proofload.__file__``, never ``Path.cwd()``,
so a run under ``PYTHONPATH`` reads the tree it was pointed at.

**Step zero, nine items, measured at ``f7af030`` before a test was written** (the log at
``.work/serve-pass-1/step-zero/`` in the worktree, filed in the project's records under
``log/prove-serve-pass-1/step-zero/``). The four reproductions hold: (3) on the then-fixture
pair's page every present cell has its centre under a label ``<text>`` drawn after its rect, and no
``pointer-events:none`` selector ends in ``text``; (4) on that pair's two-event figure exactly two
``<text>`` runs pass the box, both legend captions, and a 143-char ``--title`` runs past it too --
*and on every builder-made pair whose box is 200 to 440 px wide the
honesty lines, the panel headline, the stacked headline's second line and the legend swatch labels
pass it too* (see the LS2 convention below); (5) a three-hole partial pair prints ``none`` in the
``where`` column of both off-grid rows, each of which carries its whole ``config``; (6) all four
integer conditions hold on that two-event pair in every cell and both arms, the deltas cancel
in every cell, and every other pair measured (its one event alone, the multi-event pair, and two
real-suite pairs in the workspace store) fails condition 1 or 4. (7) ``max_mde_unchanged`` is
a fraction in [0, 1] on every pair and ``_fmt(value, "pp0")`` is character for character the number
the honesty line prints, on all thirteen panels that have one. (8) ``MULTI_JSON_SHA256``'s fixture
is a single-event comparison and ``to_json()`` has 25 keys, none named ``complementary_events``. (1) The
section 7.1 greps: ``TOP_LEVEL_KEYS`` has **six** copies (``test_s29_viewer.py``,
``test_m13_viewer.py``, ``test_p1_payload.py``, ``test_s21_errors.py``, ``test_a28_agreement.py``,
``test_cut_surfacing.py``), not the three section 0.2 counts; all six are updated. (2)
``origin/main`` is ``a1caa17``, four commits past ``f7af030`` (the PR-1 merge); this packet stays
on ``f7af030`` as instructed and the line numbers in the spec were read there.

**Conventions this file fixes where the spec is silent or disagrees with itself. The build follows
these; each was put to review and ruled on 2026-09-22 (seven yes).**

- **The Summary region is one ``<p>`` per sentence, one element per line, no table, no list, no
  attribute, no ``<details>``**, in this order: the partial line (if any), the complement line (if
  any), then per event in ``panels`` order the counts line, each ``worse`` row's line, the limit
  line, and last the pointer. Every ``<p>`` is one ``line`` value of ``summary`` through
  ``html.escape``, so LS20's two directions are one equality.
- **The event name is spelled bare** in the counts and row sentences: ``tripped: 0 of 72 conditions
  ...``. The spec writes the field in backticks in section 3.4, which this file reads as the spec's
  own markdown and not as characters the page prints; the headline already spells events bare.
- **``change`` is the cell's ``text["delta"]`` verbatim**, so a rise reads ``28.1`` and not
  ``+28.1``; section 3.3's example shows a plus sign and section 3.3's rule says verbatim, and
  verbatim is what LS9 can check.
- **``q`` in the counts sentence is ``str()`` of the ``diff`` object's ``q``** (``0.05``). LS9's
  payload-bound clause accepts it because the tree's ``bound.text.q`` spells the same number; the
  two spellings part below ``q = 0.001`` (``sig3`` goes scientific), which no fixture reaches and is
  named as a non-observable rather than pinned.
- **The unlabelled row's ``0.05`` is fixed text**, the one numeric token of a sentence that is a
  threshold and not a field; LS9 admits the spellings of the module's own thresholds and nothing
  else beyond the payload.
- **The ``worse`` rows are the panel's ``worse`` cells sorted by ``(-delta, q, mde, config_hash)``**
  -- ``_worst``'s tie-break key -- cut at ``view.top_n``; a sort is not arithmetic.
- **The complement sentence's second clause names the traded pair, not ``events`` order** (ruled
  2026-09-22): ``The {k} conditions where {worse} rose are the {k} where {safer} fell``, with
  ``(safer, worse)`` the pair ``trade_line()`` picks. On the two-event lattice pair the two readings coincide.
- **``build_summary`` takes the trade line as a sixth keyword** (ruled 2026-09-22), so
  ``summary.complement.line`` *is* ``trade_line()`` and ``plain.py`` composes no complement sentence:
  one source for one sentence, on every method.
- **Under complementarity with nothing significant, ``trade_line()`` stays ``None``** (the existing
  first guard runs first) and ``summary.complement`` is ``{"events": [...], "line": None}``: there
  is no traded pair to name. No fixture reaches it.
- **The non-complementary trade line keeps its first sentence and drops its second** (ruled
  2026-09-22): ``Trade: {safer} fell in {n} cells where {worse} rose.`` Section 0.2 says the line is
  unchanged except under complementarity and, two lines on, that "moved failures" appears nowhere
  in ``src/``; only the second can be checked, and D2 is why it wins.
- **The partial line names each partial run in ``a``, ``b`` order**, one sentence per run joined by
  a space, and ``summary.partial["runs"]`` lists them in that order.
- **LS2 is pinned over five texts**: the four D9 wraps -- the title (stacked and per panel), the
  headline lines (stacked header and panel caption), the trade or complement line, the legend caption
  -- and, ruled 2026-09-22, the honesty lines, each identified by content through this file's
  restatement of ``_wrap`` and its budget. The spec's clause reads "every ``<text>``"; measured at
  step zero, that cannot hold on a box 200 px wide, whose legend swatch *rects* sit at a fixed 46 px
  pitch and already leave it; the swatch labels are the named exception.
- **A wrapped text is drawn as one ``<text>`` per line, the continuation lines carrying
  ``data-wrap="1"`` and the first line not**, so M7's frozen file (updated) can read a wrapped
  text back as one, and so a reader of the SVG can tell a wrapped line from a new text.
- **The tree refusal is left as it was.** Section 3.8 item 1 gives it "the same treatment for
  symmetry", but it carries no version literal to interpolate, and P-1's Y15 pins its text; LS8
  asserts it names no version, and the intervals refusal alone interpolates ``SCHEMA``.
- **LS3's rect clause is "byte-identical up to the top growth"**: ``x``, ``width``, ``height``,
  ``fill`` and the four ``data-`` attributes of every grid and glyph rect are the base commit's,
  and ``y`` is the base commit's plus exactly the growth of ``top`` (``18`` per extra title
  line, ``12`` per extra headline line). The spec's "byte-identical" holds only where nothing
  above the grid wraps; on the narrow pairs the headline wraps, and a grid that did not move down
  would be drawn over its own title.
- **LS16 is pinned as written, six tokens over the whole page.** Measured: the Cells region prints
  ``MDE is ADR-018's smallest detectable increase ...`` on every pair with a rejecting family, so
  LS16 and LS19's "byte-identical apart from the two strings section 3.8 names" cannot both hold.
  D14's rule (a public page carries no reference a stranger cannot resolve) is the intent, ruled
  2026-09-22: the build spells that sentence ``MDE is the smallest detectable increase ...`` (and its
  twin in ``report.py`` the same), and LS19's region digests are taken with the bare spelling
  normalised to that one.
- **LS1's "sole catch" is a source clause.** The page's ``<style>`` is ``_html_style(theme)`` plus
  ``_LAYOUT``, so a rule added to the report's stylesheet *does* reach the page and the computed
  style cannot tell the two apart; the spec's "where the page does not read it" is wrong. What
  catches the mutant is that ``pointer-events`` appears in ``viewer._LAYOUT`` and not in
  ``_html_style``.
- **The hole's ``where`` on a grid hole is its ``coords`` string, and on an off-grid hole is
  ``", ".join(f"{axis}={config_text[axis]}")`` over ``x_axis``, ``y_axis`` and the keys of
  ``view.fixed`` in that order**, or ``off grid: <config_hash>`` when the config carries none of them.
  The Holes summary paragraph is the sentence of section 3.1 (c) with the cause counts after it.
- **``mde_unchanged.where``** is the ``coords`` string of the cell ``_honesty``'s three-step search
  names, and ``mde_unchanged.text`` is ``_fmt(value, "pp0")``; ``None`` for all three when the
  honesty line is ``_HONESTY_NONE``.
- **LS19's region digests are normalised at four places the spec did not count**: the two
  unverified tails (section 3.8), the MDE-meaning sentence (the LS16 convention), the ``Result``
  region's trade or complement ``<p>`` (D10 changes it on the two-event complementary pair), and the ``Cell``
  region's holes JSON block (D12 adds ``where`` to every hole). Everything else in the eight regions
  is pinned byte for byte, on the bare tree, and must survive the build.
- **LS21, from the ruling of 2026-09-21 that lifted D16's hold on the word "unpaired":** the word
  and the Python warning stay exactly as they are, and one plain line is printed beside the word --
  in the ``Result`` block, the ``<p>`` right after the headline -- iff the payload's
  ``diff.unpaired_analysis`` is true (the runs share their seeds and the test ignores that). It rides
  the payload as ``summary.pairing.line`` (``None`` otherwise), third key of ``summary`` after
  ``complement``, and is the one ``line`` of ``summary`` that is read in ``Result`` rather than in
  the Summary region, so LS20's equality leaves it out. The wording is an internal pairing report's
  suggested sentence, verbatim. Not a spec invariant: the ruling came after the spec was written.

**Fixture limits, stated before anything is asserted on a fixture.** Every S29 pair is complete,
so LS15 rests on this file's own partial pair (three holes, ``part-a`` never marked complete,
both orders). No stored pair was taken at ``--q`` above 0.05, so the unlabelled row and the ``q``
boundaries are exercised on a hand-built panel (LS10) and only the labels the real payloads reach
are re-asserted on them. The two-event lattice pair (``tests/lattice.py``) is the only complementary fixture; the
non-complementary trade line is reached through a builder-made pair (``trade-a``/``trade-b``)
whose one all-``fail``/all-``crash`` cell is a trade and whose ``ok`` rows break condition 4.
The lattice's run ids are short, so the wrapped title needs ``--title``.

**Named non-observables.** A ``q`` below 0.001 spelled two ways (above). A wrapped text whose
lines are joined with a different separator than one space: ``_wrap`` breaks on spaces only.
A sentence composed inside ``render_html`` that equals a ``line`` value character for character:
LS20's equality cannot see it, and LS9's AST clause is over ``plain.py`` alone.
"""

from __future__ import annotations

import ast
import hashlib
import html as html_mod
import json
import inspect
import re
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import lattice
import poisson_prove
from poisson_prove import cli
from poisson_prove import diff as diff_mod
from poisson_prove.diff import multi_diff
from poisson_prove.episode import Episode
from poisson_prove.report import _fmt
from poisson_prove.store import EpisodeRecord, RunManifest, Store

PACKAGE = Path(poisson_prove.__file__).resolve().parent
REPO = PACKAGE.parents[1]
SRC = PACKAGE
VIEWER_SOURCE = PACKAGE / "viewer.py"
REPORT_SOURCE = PACKAGE / "report.py"
DIFF_SOURCE = PACKAGE / "diff.py"
PLAIN_SOURCE = PACKAGE / "plain.py"
README = REPO / "README.md"
SERVE_DOC = REPO / "docs" / "reading-a-serve-page.md"
#: The generated lattice pair (``tests/lattice.py``), built once per machine and checked on use.
LATTICE_ROOT = lattice.root()
LATTICE_A, LATTICE_B = lattice.RUN_A, lattice.RUN_B

# ---------- spec sections 2, 3.2, 3.3, 3.5: the literals ----------

#: LS7, LS8. The schema, and the four ``render_html`` refuses by name.
SCHEMA = "poisson-prove.viewpair/7"
RETIRED_SCHEMAS = tuple(f"proofload.viewpair/{n}" for n in (2, 3, 4, 5, 6))
#: LS7. Fourteen top-level keys, ``summary`` eighth.
TOP_LEVEL_KEYS = (
    "schema", "pair", "diff", "holes", "view", "headline", "trade_line", "summary", "fence", "panels",
    "intervals", "tree", "unverified", "heatmap_svg",
)
#: LS7. Fifteen panel keys, ``mde_unchanged`` after ``honesty``; the cell keys unchanged; ten hole keys.
# PF4 (PF4.20, PF4.3): a panel carries its event's kind before n_safer and n_worse (null when the
# kind is unknown) and the direction counts n_higher and n_lower after them, then the share label.
# The contract names the share caption, not this key; share_label is the reference build's name.
# ``threshold`` is section 8.4's threshold on the panel, so the Summary reads it as a payload field.
# PF4 re-freeze (PF4.34 to PF4.47): each panel gains ``flag_rule`` after ``kind``; the order is the
# reference build's.
PANEL_KEYS = (
    "event", "caption", "honesty", "mde_unchanged", "kind", "flag_rule", "n_safer", "n_worse", "n_higher", "n_lower",
    "share_label", "threshold", "n_unchanged", "n_absent", "n_present", "x_values", "y_values", "cells",
    "worst_header",
    "worst_rows", "worst_hashes",
)
MDE_UNCHANGED_KEYS = ("value", "text", "where")
# PF4 (PF4.13, PF4.14, PF4.15, PF4.3): every cell gains, after verdict, its direction and the note
# beside it, its matched pairs, the note beside its detection limit, and the two shares with their
# differs flags.
CELL_KEYS = (
    "coords", "config_hash", "n_a", "n_b", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b",
    "events_a", "events_b", "rate_a", "rate_b", "delta", "stat", "p", "q", "mde", "verdict",
    "direction", "direction_note", "pairs", "mde_note",
    # PF4 re-freeze (PF4.34 to PF4.47): Holm's q and flag, the limit keys, the competing shift and the
    # interval, after mde_note; the order is the reference build's.
    "q_holm", "holm", "mde_rise", "mde_fall", "mde_rise_note", "mde_fall_note", "mde_test", "mde_basis",
    "mde_level", "mde_family", "mde_power", "mde_anchor", "mde_hr", "p_min", "flaggable", "mde_moves_with",
    "mde_rise_verdict", "mde_fall_verdict", "competing_shift", "ci_lo", "ci_hi", "ci_level", "ci_method",
    "share_a", "share_b", "share_a_differs",
    "share_b_differs", "config", "config_text", "text",
)
HOLE_KEYS = (
    "coords", "where", "config_hash", "cause", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b",
    "config", "config_text",
)
#: LS7. The ``summary`` object (section 3.3), its event entry, a ``worse`` row and the limit.
# PF4 (PF4.5): the Summary carries the comparison's verdict word, first.
# PF4 re-freeze (PF4.34, PF4.35, PF4.40, PF4.44, PF4.46): after the word, the verdict rule, the verdict
# line, the verdict limit, the fragility, peeking, the errored episodes and the verdict block's detail
# lines (``facts``); the order is the reference build's.
SUMMARY_KEYS = (
    "verdict", "verdict_rule", "verdict_line", "verdict_limit", "fragility", "peeking", "errors_differ", "facts",
    "partial", "complement", "pairing", "events", "pointer",
)
PAIRING_KEYS = ("line",)
EVENT_ENTRY_KEYS = ("event", "line", "worse", "limit")
WORSE_ROW_KEYS = ("where", "config_hash", "before", "after", "change", "confidence", "q", "line")
LIMIT_KEYS = ("label", "mde", "where", "line")
#: LS5. Fourteen ``<h2>``, ``Summary`` first, ``Run pair`` thirteenth.
H2_SEQUENCE = (
    "Summary", "Events", "Omnibus", "Result", "Honesty", "Not verified", "Fault lines", "Cells", "Heatmap", "Cell",
    "Holes", "Worst cells", "Run pair", "Provenance",
)
DISPATCH_H2 = frozenset(H2_SEQUENCE)
#: LS19. The regions that keep their bytes but for the strings section 3.8 names (and the one this
#: file's LS16 convention adds).
UNTOUCHED_REGIONS = ("Result", "Honesty", "Not verified", "Fault lines", "Cells", "Cell", "Worst cells", "Provenance")
RETIRED_TAILS = (" (closed by B.1)", " (nothing on the roadmap closes this)")
NEW_TAILS = (" (a change is planned that would close this)", " (nothing planned would close this; it is a limit of the instrument)")
MDE_MEANING_BARE = "MDE is ADR-018's smallest detectable increase"
MDE_MEANING_PLAIN = "MDE is the smallest detectable increase"
#: LS10, LS11. Section 3.5's thresholds and the quantity each applies to.
CONFIDENCE_THRESHOLDS = ((0.001, "very sure"), (0.01, "sure"), (0.05, "fairly sure"))
TOO_SMALL_TO_TELL = 0.50
LABEL_START = "0.05"
THRESHOLD_SPELLINGS = frozenset({"0.001", "0.01", "0.05"})
#: LS4. The Holes table header after the pass; the one-line form with no holes.
HOLES_HEADER = ["where", "cause", "config_hash", "rows (a/b)", "no outcome (a/b)"]
NO_HOLES_LINE = "<p>0 holes</p>"
OFF_GRID_PREFIX = "off grid: "
#: LS12 (a). The words the plain register never uses, case-insensitive substrings.
DECIDING_WORDS = (
    "do not ship", "don't ship", "ship it", "safe to", "you should", "we recommend", "recommended", "next step",
    "do next", "regressed", "regression", "verdict", "unchanged", "verified", "guaranteed", "proves", "certified",
    "adversarial", "just ", "simply", "easy",
)
#: LS12 (b). S29's ``FORBIDDEN_VOCABULARY`` (W19), restated rather than imported.
FORBIDDEN_VOCABULARY = (
    "given the root", "given that", "conditional on", "leaf", "fdr", "broke", "where it broke", "failed at", "step",
    "broken", "failed in", "where it", "culprit", "root cause", "power stays high", "high power", "well powered", "same shift",
    "given the group", "given a group", "given that the group", "reliable", "controlled at q", "at level q",
)
#: LS16. No internal reference on the page.
BOARD_TOKENS = ("B.1", "roadmap", "ADR-0", "Tranche", "C33", "A18")
UNVERIFIED_BLOCKED_BY = ("B.1", None, None, None)
#: LS13. "moved failures" appears in no file under ``src/``.
RETIRED_TRADE_TAIL = "moved failures"
#: LS1. The inert selector list, and where it lives.
INERT_LAST_TAGS = ("path", "text")
#: LS2, LS3. The figure's geometry, restated: the glyph advance, the four font sizes, the bands.
CHAR_EM = 0.6
FONT = 11
STACKED_TITLE_X = 24
STACKED_HEADER_H = 36
STACKED_LINE_H = 16
TITLE_LINE_H = 18
BODY_LINE_H = 12
MIN_BUDGET = 8
# PF4 (PF4.20): no longer asserted; on an event of unknown kind the caption reads in direction
# words. LS2 reads the caption off the figure (drawn_legend_caption) and asserts its facts.
LEGEND_TAIL = "corner notches = trade (safer in one event, worse in another)"
#: The honesty lines join the wrap set: D9 named four texts, step zero measured the honesty lines
#: past the box on every narrow pair, and it was ruled on 2026-09-22 that they wrap too (a fifth
#: text, at the caption's 12 px pitch).
WRAPPED_HONESTY = True

# ---------- section 3.4: the words, verbatim ----------

# PF4 re-freeze (PF4.40): the words "no significant change" always carry the verdict limit on their
# line, so the counts line says the conditions "were not flagged".
COUNTS_LINE = "{event}: {n_worse} of {n_present} conditions got worse, {n_safer} got safer, and {n_unchanged} were not flagged at q = {q}."
ROW_LINE = "{where}: {event} was {before}% of trials and is now {after}%, a rise of {change} percentage points. How sure: {label} (q = {q})."
ROW_LINE_UNLABELLED = "{where}: {event} was {before}% of trials and is now {after}%, a rise of {change} percentage points. How sure: no label (q = {q}; the labels start at 0.05)."
LIMIT_LINE_LABELLED = "Too small to tell: the least sensitive condition among those this run did not call a change ({where}, n = {n_a}/{n_b}) could only have seen a rise of {mde}pp or more. Below that, this run cannot tell a change from none."
LIMIT_LINE = "The least sensitive condition among those this run did not call a change ({where}, n = {n_a}/{n_b}) could only have seen a rise of {mde}pp or more."
LIMIT_LINE_NONE = "Every condition moved significantly, so there is no condition left to state a detection limit from."
PARTIAL_LINE = 'Run {run_id} ({role}) recorded status "partial": it stopped before everything it planned had run. What is below compares the conditions both runs have.'
#: LS21, the ruling of 2026-09-21 that lifted D16's hold: the one plain line beside the word
#: "unpaired", printed iff the payload's ``diff.unpaired_analysis`` is true.
PAIRING_LINE = "Compared as two separate samples. The runs share their seeds; this test does not use that."
POINTER_LINE = "Every number above is below with the statistics it came from: the omnibus, the honesty block and its bound, the per-condition table, the intervals, and what this comparison could not establish."
COMPLEMENT_LINE = "{e1} and {e2} are complements here: in all {n} conditions every trial recorded exactly one of the two, so each rate is one minus the other and each change is the other's with its sign flipped. The {k} conditions where {worse} rose are the {k} where {safer} fell: one finding, reported twice. Naming one of the two shows it once."
#: The lattice's two outcomes are complements; the 22 conditions where ``held`` rose are the 22 where
#: ``tripped`` fell under the unpaired test over both events (LS13 recomputes the 22 and the 72).
LATTICE_COMPLEMENT_LINE = COMPLEMENT_LINE.format(e1=lattice.EVENT, e2=lattice.OTHER, n=72, k=22, worse=lattice.OTHER, safer=lattice.EVENT)
TRADE_LINE = "Trade: {safer} fell in {n} {cells} where {worse} rose."
HOLES_SUMMARY = "{n} holes: {g} on the grid, {o} off it (a condition whose axis value no comparable condition has, so it is on no heatmap)."
HONESTY_NONE = "No unchanged cells; every cell moved significantly."
# PF4 re-freeze (PF4.27, PF4.32): the limit named is the condition's own, a rise or a fall.
HONESTY_RE = re.compile(r"can only detect a (\d+)pp (?:rise|fall)")
#: PF4 re-freeze (PF4.27): the closed list of reasons a limit is null, printed in words.
NOTES = ("no room", "none detectable", "cannot be flagged", "no matched pairs")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")

# ---------- the store builders (S29's, restated) ----------

NON_EVENTS = frozenset({"ok"})
EVENT_T = 2.0
HORIZON = 5.0
SALT = "s29-salt"
AXES_SALT = "s26-axes-salt"
BH_SALT = "s26-bh-salt"
TASK_TEMP = {"task": "categorical", "temp": "continuous"}
BH_TYPES = {"grp": "categorical", "cell": "categorical"}
THREE_KEY_TYPES = {"task": "categorical", "temp": "continuous", "model": "categorical"}
N_TASKS = 164
AXES_N = 8
GATE_GROUPS, GATE_CELLS, GATE_N, GATE_DISCORDANT = 40, 6, 64, 8
ME_N, ME_TASKS, ME_TEMPS = 128, 8, (0.0, 0.7)
VOCABULARY_VALUES = ("given the root", "where it broke")
HOSTILE = "".join(["<", "/script><img src=x onerror=", chr(34), "alert(1)", chr(34), ">&", chr(34)])
HOSTILE_TABLE = "".join(["<", "/table><script>alert(1)</script>&", chr(34)])
HOSTILE_VALUES = (HOSTILE, HOSTILE_TABLE)
PARTIAL_A, PARTIAL_B = "part-a", "full-b"
TRADE_A, TRADE_B = "trade-a", "trade-b"
LONG_TITLE = "A title long enough to wrap: the baseline against the candidate, both arms, every condition the two runs share, measured at the dispatch commit"


def manifest(run_id: str, salt: str, axis_types: Mapping[str, str]) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types), backend="synthetic", environment={"note": "built by ls step zero"},  # type: ignore[arg-type]
    )


def records_of(run_id: str, cells: Mapping[tuple[tuple[str, Any], ...], Sequence[str]]) -> list[EpisodeRecord]:
    out = []
    for index, (key, outcomes) in enumerate(cells.items()):
        for k, outcome in enumerate(outcomes):
            t = HORIZON if outcome in NON_EVENTS else EVENT_T
            out.append(EpisodeRecord.from_episode(
                Episode(outcome=outcome, t=t, horizon=HORIZON), run_id=run_id, config=dict(key), seed=1000 * index + k,
                replicate_index=k, wall_time=0.0,
            ))
    return out


def write_run(store: Store, run_id: str, *, salt: str, axis_types: Mapping[str, str], cells: Mapping[Any, Sequence[str]], complete: bool = True) -> None:
    store.create_run(manifest(run_id, salt, axis_types))
    store.append(run_id, records_of(run_id, cells))
    if complete:
        store.mark_complete(run_id)


def axes_cells(moved: bool) -> dict[Any, list[str]]:
    cells = {}
    for i in range(N_TASKS):
        for temp in (0.0, 0.7):
            outcomes = ["ok"] * AXES_N
            if moved and temp == 0.0 and i < 20:
                outcomes = ["fail"] * 2 + ["ok"] * (AXES_N - 2)
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


def multi_event_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    a, b = {}, {}
    k = ME_N // 32
    for t in range(ME_TASKS):
        for temp in ME_TEMPS:
            key = (("task", f"t{t}"), ("temp", temp))
            if t == 0:
                a[key] = ["fail"] * (4 * k) + ["ok"] * (28 * k)
                b[key] = ["fail"] * (20 * k) + ["ok"] * (12 * k)
            else:
                base = ["fail"] * (4 * k) + ["crash"] * k + ["ok"] * (27 * k)
                a[key], b[key] = list(base), list(base)
    return a, b


def one_value_cells(moved: bool) -> dict[Any, list[str]]:
    return {(("task", f"t{i}"), ("temp", 0.0)): (["fail"] * 8 if moved else ["ok"] * 8) for i in range(4)}


def three_key_cells(moved: bool) -> dict[Any, list[str]]:
    return {(("task", f"t{i}"), ("temp", 0.0), ("model", m)): (["fail"] * 8 if moved else ["ok"] * 8) for i in range(4) for m in ("m1", "m2")}


def two_value_cells(values: Sequence[str], moved: bool) -> dict[Any, list[str]]:
    return {(("task", v), ("temp", 0.0)): (["fail"] * 8 if moved else ["ok"] * 8) for v in values}


def partial_cells(complete: bool) -> dict[Any, list[str]]:
    """Four ``task`` x two ``temp`` at N=8 when complete; the partial arm lacks ``t3`` at both temps
    (two off-grid holes: no comparable cell carries ``t3``) and ``(t2, 0.7)`` (one grid hole)."""
    cells = {}
    for i in range(4 if complete else 3):
        for temp in (0.0, 0.7):
            if not complete and (i, temp) == (2, 0.7):
                continue
            cells[(("task", f"t{i}"), ("temp", temp))] = ["fail"] * 2 + ["ok"] * 6
    return cells


def trade_cells() -> tuple[dict[Any, list[str]], dict[Any, list[str]]]:
    """Two events that are not complements, with one trade: at ``t0`` arm a is all ``fail`` and arm b
    all ``crash`` (``fail`` safer, ``crash`` worse in the same cell); the other cells carry ``ok``
    rows, so ``events(fail) + events(crash) < n`` and condition 4 fails."""
    a, b = {}, {}
    for t in range(3):
        for temp in (0.0, 0.7):
            key = (("task", f"t{t}"), ("temp", temp))
            if t == 0:
                a[key], b[key] = ["fail"] * 16, ["crash"] * 16
            else:
                base = ["fail"] * 2 + ["crash"] * 2 + ["ok"] * 12
                a[key], b[key] = list(base), list(base)
    return a, b


# ---------- the CLI, tripwired ----------


def run_cli(argv: Sequence[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return code, out.getvalue(), err.getvalue()


def viewer() -> Any:
    import poisson_prove.viewer as module

    return module


def plain() -> Any:
    import poisson_prove.plain as module

    return module


def run_serve(argv: Sequence[str]) -> tuple[int, str, str, list[str]]:
    """``main(argv)`` with ``serve_page`` replaced by a function that records the call and raises."""
    calls: list[str] = []

    def trip(*args: Any, **kwargs: Any) -> None:
        calls.append("serve_page")
        raise AssertionError("serve_page was called; something was about to bind")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(viewer(), "serve_page", trip)
        mp.setattr(cli, "serve_page", trip, raising=False)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
            code, out, err = run_cli(argv)
    return code, out, err, calls


def strict_loads(text: str) -> Any:
    def fail(token: str) -> Any:
        raise ValueError(f"non-JSON constant {token!r}")

    return json.loads(text, parse_constant=fail)


def quiet_multi_diff(a: pd.DataFrame, b: pd.DataFrame, ma: RunManifest, mb: RunManifest, *, events: Sequence[str], method: str = "fisher_bh") -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return multi_diff(a, b, events=list(events), method=method, manifest_a=ma, manifest_b=mb)


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
    title: str | None
    multi: Any
    structure: dict[str, Any]
    page: str


KNOB_FLAGS = {"by": "--by"}
_PAIRS: dict[str, Pair] = {}


def serve_argv(root: Path, a: str, b: str, events: Sequence[str], x: str, y: str | None, fixed: Mapping[str, Any], method: str, knobs: Mapping[str, Any], title: str | None) -> list[str]:
    argv = ["--store", str(root), "serve", a, b]
    for e in events:
        argv += ["--event", e]
    argv += ["--x", x]
    if y is not None:
        argv += ["--y", y]
    for k, v in fixed.items():
        argv += ["--fix", f"{k}={json.dumps(v)}"]
    # PF3 (Q17, spec sections 4.4 and 14; R1): with no --method the default is now the paired test
    # for runs that share a salt (the lattice among them); every pair here is compared with the library's
    # multi_diff under ``method``, so the method is always named.
    argv += ["--method", method]
    for k, v in knobs.items():
        argv += [KNOB_FLAGS[k], str(v)]
    if title is not None:
        argv += ["--title", title]
    return argv + ["--json"]


def pair(name: str, root: Path, a: str, b: str, events: Sequence[str], x: str, y: str | None = None, *, fixed: Mapping[str, Any] | None = None, method: str = "fisher_bh", title: str | None = None, **knobs: Any) -> Pair:
    """One pair through ``serve --json`` (tripwired, exit 0), its page from ``render_html`` over the
    JSON round trip -- so the renderer sees a structure with no report, no diff and no tree object
    in scope (LS20) -- and the diff on the same frames; cached by name."""
    if name not in _PAIRS:
        fixed = dict(fixed or {})
        code, out, err, calls = run_serve(serve_argv(root, a, b, events, x, y, fixed, method, knobs, title))
        assert code == 0 and calls == [], (name, code, err[-400:], calls)
        structure = strict_loads(out)
        store = Store(root)
        multi = quiet_multi_diff(store.read(a, meta=False), store.read(b, meta=False), store.manifest(a), store.manifest(b), events=events, method=method)
        _PAIRS[name] = Pair(name, root, a, b, tuple(events), x, y, fixed, method, title, multi, structure, viewer().render_html(structure))
    return _PAIRS[name]


# ---------- the page, by line and by region ----------

H2_RE = re.compile(r"^<h2>(.*)</h2>$")
TAG_RE = re.compile(r"<[^>]+>")
TD_RE = re.compile(r"<td>(.*?)</td>", re.S)
TH_RE = re.compile(r"<th>(.*?)</th>", re.S)
TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
ATTRIBUTE_RE = re.compile(r"\b(id|class|style|data-[a-z]+)=")


def h2_lines(page: str) -> list[tuple[int, str]]:
    return [(i, m.group(1)) for i, line in enumerate(page.splitlines()) if (m := H2_RE.match(line))]


def h2_sequence(page: str) -> list[str]:
    return [heading for _, heading in h2_lines(page)]


def region_lines(page: str, heading: str) -> list[str]:
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
    assert line.startswith("<table>") and line.endswith("</table>"), line[:80]
    header = [unescape(h) for h in TH_RE.findall(line)]
    rows = [[unescape(c) for c in TD_RE.findall(tr)] for tr in TR_RE.findall(line)]
    return header, [r for r in rows if r]


def region_text(page: str, heading: str) -> str:
    return "\n".join(unescape(line) for line in region_lines(page, heading))


def summary_lines(page: str) -> list[str]:
    """The Summary region as sentences: one ``<p>`` per line, nothing else (the convention above)."""
    out = []
    for line in region_lines(page, "Summary"):
        assert not ATTRIBUTE_RE.search(line) and "<script" not in line and "<table" not in line and "<ul" not in line and "<details" not in line, line[:80]
        parts = p_lines(line)
        assert len(parts) == 1, line[:80]
        out.extend(parts)
    return out


def walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from walk_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_strings(v)


def walk_texts(value: Any, key: str | None = None) -> Iterator[str]:
    """Every string under a ``text`` or ``config_text`` mapping, anywhere in the structure."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k in ("text", "config_text"):
                yield from walk_strings(v)
            else:
                yield from walk_texts(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from walk_texts(v, key)


def walk_ints(value: Any) -> Iterator[str]:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        yield str(value)
    elif isinstance(value, dict):
        for v in value.values():
            yield from walk_ints(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk_ints(v)


def summary_sentences(structure: Mapping[str, Any]) -> list[str]:
    """Every ``line`` value of ``summary`` that is a string, in section order."""
    s = structure["summary"]
    # PF4 re-freeze (PF4.34, PF4.35, PF4.44): the Summary opens with the comparison's verdict line and
    # carries the verdict block's detail lines, ``<label>: <line>``, before the pointer.
    out: list[str] = [s["verdict_line"]] if s.get("verdict_line") is not None else []
    if s["partial"] is not None:
        out.append(s["partial"]["line"])
    if s["complement"] is not None and s["complement"]["line"] is not None:
        out.append(s["complement"]["line"])
    for entry in s["events"]:
        out.append(entry["line"])
        out.extend(row["line"] for row in entry["worse"])
        out.append(entry["limit"]["line"])
    out.extend(verdict_block_lines(structure))
    out.append(s["pointer"])
    return out


def verdict_block_lines(structure: Mapping[str, Any]) -> list[str]:
    """PF4 re-freeze (PF4.35, PF4.42, PF4.44, PF4.46): the verdict block's detail lines the Summary
    carries, ``<label>: <line>``. They are the comparison's facts, carried whole by the payload as
    ``summary.facts``, not sentences the plain register composes from the panels."""
    return [f"{fact['label']}: {fact['line']}" for fact in structure["summary"].get("facts", ())]


def config_values(structure: Mapping[str, Any]) -> list[str]:
    """W19's mask: the pair's own config values, so a value that is a forbidden phrase does not fail
    the scan of a sentence that quotes it."""
    values = set()
    for panel in structure["panels"]:
        for cell in panel["cells"]:
            values.update(v for v in cell["config_text"].values() if isinstance(v, str))
    for hole in structure["holes"]:
        if hole["config_text"]:
            values.update(v for v in hole["config_text"].values() if isinstance(v, str))
    return sorted(values, key=len, reverse=True)


def masked(text: str, structure: Mapping[str, Any]) -> str:
    low = text.lower()
    for value in config_values(structure):
        low = low.replace(value.lower(), " ")
    return low


def label_for(q: float) -> str | None:
    for threshold, label in CONFIDENCE_THRESHOLDS:
        if q < threshold:
            return label
    return None


# ---------- a small DOM with CSS matching (M13's, restated) ----------


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None
    children: list[Node]
    texts: list[str]

    def ancestors(self) -> list[Node]:
        out, node = [], self.parent
        while node is not None:
            out.append(node)
            node = node.parent
        return out

    def inside(self, **attrs: str) -> bool:
        return any(all(a.attrs.get(k) == v for k, v in attrs.items()) for a in self.ancestors())


VOID_TAGS = {"br", "meta", "img", "hr", "input", "link", "col", "area", "base", "wbr"}


class Dom(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, None, [], [])
        self.current = self.root
        self.nodes: list[Node] = []
        self.styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: v or "" for k, v in attrs}, self.current, [], [])
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
        if self.current.tag == "style":
            self.styles.append(data)


def parse_html(text: str) -> Dom:
    dom = Dom()
    dom.feed(text)
    return dom


COMPOUND_RE = re.compile(r"^([a-zA-Z*][\w-]*)?((?:\[[\w-]+(?:=\"?[^\]\"]*\"?)?\]|[.#][\w-]+)*)$")
QUALIFIER_RE = re.compile(r"([.#])([\w-]+)|\[([\w-]+)(?:=\"?([^\]\"]*)\"?)?\]")


def declarations(body: str) -> dict[str, str]:
    out = {}
    for item in body.split(";"):
        if ":" in item:
            k, _, v = item.partition(":")
            out[k.strip()] = v.strip()
    return out


def css_rules(css: str) -> list[tuple[list[str], dict[str, str]]]:
    css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    rules = []
    for block in css.split("}"):
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
        if kind == "." and name not in node.attrs.get("class", "").split():
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


# ---------- the figure ----------


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass(frozen=True)
class Text:
    x: float
    y: float
    font: float
    anchor: str
    content: str
    wrap: bool


def svg_texts(svg: str) -> tuple[list[Text], float, float]:
    root = ET.fromstring(svg)
    parents = {c: p for p in root.iter() for c in p}

    def inherited(el: ET.Element, attr: str, default: str) -> str:
        node: ET.Element | None = el
        while node is not None:
            if attr in node.attrib:
                return node.attrib[attr]
            node = parents.get(node)
        return default

    out = []
    for el in root.iter():
        if local(el.tag) == "text":
            out.append(Text(float(el.attrib["x"]), float(el.attrib["y"]), float(inherited(el, "font-size", str(FONT))), inherited(el, "text-anchor", "start"), el.text or "", el.attrib.get("data-wrap") == "1"))
    return out, float(root.attrib["width"]), float(root.attrib["height"])


def right_edge(t: Text) -> float:
    w = len(t.content) * CHAR_EM * t.font
    return t.x + w if t.anchor == "start" else (t.x + w / 2 if t.anchor == "middle" else t.x)


def wrap(text: str, budget: int) -> list[str]:
    """Section 3.1 (b)'s ``_wrap``, restated: broken on spaces into lines of at most ``budget``
    characters, greedy, a word longer than the budget hard-split; ``[""]`` for empty text."""
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        while len(word) > budget:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:budget])
            word = word[budget:]
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= budget:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def budget(width: float, x: float, font: float) -> int:
    return max(MIN_BUDGET, int((width - x - 24) / (CHAR_EM * font)))


#: PF4 (PF4.20): the legend caption's fixed facts, read off the drawn caption. The unit after the
#: sign convention is the surface's (``in pp`` on the page, ``as fractions`` in the CLI's report).
CAPTION_HEAD = "delta = rate_b - rate_a "
CAPTION_KEYS = ("corner square = significant", "blank = no data")
NOTCHES = "corner notches = "


def drawn_legend_caption(panel: Sequence[ET.Element], left: float) -> str:
    """PF4 (PF4.20): the panel's legend caption as the figure draws it, its first line and the
    ``data-wrap`` continuation lines after it joined with one space. For an event of unknown kind
    the caption reads in direction words, whose wording this test does not pin, so the wrap, the
    box and the continuation mark are checked on the caption the figure carries, and its facts
    (the sign convention, the event, the legend keys, the notches on a traded pair) are asserted
    by the tests that read it."""
    texts = [el for el in panel if local(el.tag) == "text"]
    starts = [i for i, el in enumerate(texts) if (el.text or "").startswith("delta =") and float(el.attrib["x"]) == left]
    assert len(starts) == 1, [el.text for el in texts]
    lines = [texts[starts[0]].text or ""]
    for el in texts[starts[0] + 1 :]:
        if el.attrib.get("data-wrap") != "1":
            break
        lines.append(el.text or "")
    return " ".join(lines)


def panel_groups(svg: str) -> list[tuple[str, list[ET.Element]]]:
    root = ET.fromstring(svg)
    return [(g.attrib["data-panel"], list(g.iter())) for g in root.iter() if local(g.tag) == "g" and "data-panel" in g.attrib]


def panel_left(panel: Sequence[ET.Element]) -> float:
    """The panel's ``left``: the smallest ``x`` of a grid rect."""
    return min(float(r.attrib["x"]) for r in panel if local(r.tag) == "rect" and "data-cell" in r.attrib)


def panel_box(panel: Sequence[ET.Element]) -> tuple[float, float]:
    canvas = next(r for r in panel if local(r.tag) == "rect" and r.attrib.get("x") == "0" and r.attrib.get("y") == "0")
    return float(canvas.attrib["width"]), float(canvas.attrib["height"])


def rect_set(panel: Sequence[ET.Element], shift: float) -> str:
    """The grid and glyph rects, ``y`` shifted back by the top growth, canonicalised and joined."""
    rows = []
    for r in panel:
        if local(r.tag) != "rect" or not ("data-cell" in r.attrib or "data-sig" in r.attrib):
            continue
        a = dict(r.attrib)
        a["y"] = _fmt(float(a["y"]) - shift, "num")
        rows.append(json.dumps({k: a.get(k) for k in ("x", "y", "width", "height", "fill", "data-cell", "data-sig", "data-trade", "data-sat")}, sort_keys=True))
    return "\n".join(sorted(rows))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def header_lines(p: Pair) -> list[str]:
    """``_multi_header``'s texts, restated: the inference line, the headline's lines, the trade line."""
    lines = []
    if p.structure["diff"]["inferred"]:
        lines.append(p.multi.to_markdown().splitlines()[0])
    lines.extend(str(p.structure["headline"]).splitlines())
    if p.structure["trade_line"] is not None:
        lines.append(str(p.structure["trade_line"]))
    return lines


def caption_checked(caption: str, event: str, trades: bool) -> str:
    """PF4 (PF4.20): the drawn caption's facts: the sign convention and the event first, the two
    legend keys, the notches clause iff the pair traded, and no judgement word for an event of
    unknown kind."""
    assert caption.startswith(CAPTION_HEAD) and f"; event={event}; " in caption, caption
    assert all(key in caption for key in CAPTION_KEYS) and (NOTCHES in caption) is trades, caption
    assert not re.search(r"\b(safer|worse)\b", caption), caption
    return caption


def expected_layout(p: Pair) -> dict[str, Any]:
    """Every wrapped text of the figure and the height growth it implies, from the structure and
    the bare-tree pins alone."""
    texts, width, _ = svg_texts(p.structure["heatmap_svg"])
    title = wrap(str(p.structure["view"]["title"]), budget(width, STACKED_TITLE_X, FONT + 2))
    header = [wrap(text, budget(width, STACKED_TITLE_X, FONT)) for text in header_lines(p)]
    trades = len(p.multi.trades) > 0
    panels = {}
    for event, panel in panel_groups(p.structure["heatmap_svg"]):
        left = panel_left(panel)
        entry = next(e for e in p.structure["panels"] if e["event"] == event)
        panels[event] = {
            "left": left,
            "title": wrap(event, budget(width, left, FONT + 2)),
            "headline": wrap(str(entry["caption"]), budget(width, left, FONT)),
            # PF4 (PF4.20): the caption as drawn (drawn_legend_caption), not legend_caption's
            # safer/worse wording, which is not what an event of unknown kind reads.
            "caption": wrap(caption_checked(drawn_legend_caption(panel, left), event, trades), budget(width, left, FONT - 2)),
            "honesty": [wrap(text, budget(width, left, FONT - 2)) if WRAPPED_HONESTY else [text] for text in str(entry["honesty"]).splitlines()],
        }
    return {"width": width, "title": title, "header": header, "panels": panels}


# ---------- fixtures ----------


def build_synth_store(root: Path) -> None:
    """Every builder-made pair: S29's nine, this file's partial pair and its traded pair."""
    store = Store(root)
    write_run(store, "axes-a", salt=AXES_SALT, axis_types=TASK_TEMP, cells=axes_cells(False))
    write_run(store, "axes-b", salt=AXES_SALT, axis_types=TASK_TEMP, cells=axes_cells(True))
    write_run(store, "same-a", salt=AXES_SALT, axis_types=TASK_TEMP, cells=axes_cells(True))
    write_run(store, "same-b", salt=AXES_SALT, axis_types=TASK_TEMP, cells=axes_cells(True))
    ba, bb = bh_cells(8, 1)
    write_run(store, "bh-a", salt=BH_SALT, axis_types=BH_TYPES, cells=ba)
    write_run(store, "bh-b", salt=BH_SALT, axis_types=BH_TYPES, cells=bb)
    ga, gb = gate_cells()
    write_run(store, "gate-a", salt=SALT, axis_types=BH_TYPES, cells=ga)
    write_run(store, "gate-b", salt=SALT, axis_types=BH_TYPES, cells=gb)
    me_a, me_b = multi_event_cells()
    write_run(store, "me-a", salt=SALT, axis_types=TASK_TEMP, cells=me_a)
    write_run(store, "me-b", salt=SALT, axis_types=TASK_TEMP, cells=me_b)
    write_run(store, "ov-a", salt=SALT, axis_types=TASK_TEMP, cells=one_value_cells(False))
    write_run(store, "ov-b", salt=SALT, axis_types=TASK_TEMP, cells=one_value_cells(True))
    write_run(store, "three-a", salt=SALT, axis_types=THREE_KEY_TYPES, cells=three_key_cells(False))
    write_run(store, "three-b", salt=SALT, axis_types=THREE_KEY_TYPES, cells=three_key_cells(True))
    write_run(store, "vocab-a", salt=SALT, axis_types=TASK_TEMP, cells=two_value_cells(VOCABULARY_VALUES, False))
    write_run(store, "vocab-b", salt=SALT, axis_types=TASK_TEMP, cells=two_value_cells(VOCABULARY_VALUES, True))
    write_run(store, "hostile-a", salt=SALT, axis_types=TASK_TEMP, cells=two_value_cells(HOSTILE_VALUES, False))
    write_run(store, "hostile-b", salt=SALT, axis_types=TASK_TEMP, cells=two_value_cells(HOSTILE_VALUES, True))
    write_run(store, PARTIAL_A, salt=SALT, axis_types=TASK_TEMP, cells=partial_cells(False), complete=False)
    write_run(store, PARTIAL_B, salt=SALT, axis_types=TASK_TEMP, cells=partial_cells(True))
    ta, tb = trade_cells()
    write_run(store, TRADE_A, salt=SALT, axis_types=TASK_TEMP, cells=ta)
    write_run(store, TRADE_B, salt=SALT, axis_types=TASK_TEMP, cells=tb)


@pytest.fixture(scope="module")
def synth_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("ls-synth")
    build_synth_store(root)
    return root


@pytest.fixture(scope="module")
def every_pair(synth_root: Path) -> list[Pair]:
    """S29's eleven pairs through ``serve --json``, no tree flag but the ``--by grp`` the BH and gate
    pairs need."""
    return [
        pair("lattice", LATTICE_ROOT, LATTICE_A, LATTICE_B, (lattice.EVENT,), lattice.X, lattice.Y),
        pair("lattice-two-events", LATTICE_ROOT, LATTICE_A, LATTICE_B, (lattice.EVENT, lattice.OTHER), lattice.Y, lattice.X),
        pair("axes", synth_root, "axes-a", "axes-b", ("fail",), "temp", "task"),
        pair("identical", synth_root, "same-a", "same-b", ("fail",), "temp", "task"),
        pair("bh", synth_root, "bh-a", "bh-b", ("fail",), "grp", "cell", method="mcnemar_bh", by="grp"),
        pair("gate", synth_root, "gate-a", "gate-b", ("fail",), "grp", "cell", method="mcnemar_bh", by="grp"),
        pair("multi-event", synth_root, "me-a", "me-b", ("fail", "crash"), "task", "temp"),
        pair("one-value", synth_root, "ov-a", "ov-b", ("fail",), "task", "temp"),
        pair("three-key", synth_root, "three-a", "three-b", ("fail",), "task", "temp", fixed={"model": "m1"}),
        pair("vocab", synth_root, "vocab-a", "vocab-b", ("fail",), "task", "temp"),
        pair("hostile", synth_root, "hostile-a", "hostile-b", ("fail",), "task", "temp"),
    ]


@pytest.fixture(scope="module")
def lattice_one(every_pair: list[Pair]) -> Pair:
    return every_pair[0]


@pytest.fixture(scope="module")
def lattice_two(every_pair: list[Pair]) -> Pair:
    return every_pair[1]


@pytest.fixture(scope="module")
def titled() -> Pair:
    return pair("lattice-titled", LATTICE_ROOT, LATTICE_A, LATTICE_B, (lattice.EVENT,), lattice.X, lattice.Y, title=LONG_TITLE)


@pytest.fixture(scope="module")
def partial(synth_root: Path) -> Pair:
    return pair("partial", synth_root, PARTIAL_A, PARTIAL_B, ("fail",), "temp", "task")


@pytest.fixture(scope="module")
def partial_b(synth_root: Path) -> Pair:
    """The same two runs the other way round: the candidate is the partial one."""
    return pair("partial-b", synth_root, PARTIAL_B, PARTIAL_A, ("fail",), "temp", "task")


@pytest.fixture(scope="module")
def traded(synth_root: Path) -> Pair:
    return pair("traded", synth_root, TRADE_A, TRADE_B, ("fail", "crash"), "task", "temp")


@pytest.fixture(scope="module")
def all_pairs(every_pair: list[Pair], titled: Pair, partial: Pair, partial_b: Pair, traded: Pair) -> list[Pair]:
    return [*every_pair, titled, partial, partial_b, traded]


def by_name(pairs: Sequence[Pair]) -> dict[str, Pair]:
    return {p.name: p for p in pairs}


# ---------- the bare-tree pins (LS3, LS19), minted at 2da9847 ----------

# ---- pins begin: minted on the bare tree at 2da9847 by .work/serve-pass-1/mint_pins.py ----
#: LS3. Per pair, the stacked figure's width and, per panel, its bare-tree body height and the sha256
#: of its grid and glyph rects (``rect_set`` at shift 0). Green before and after: the grid does not
#: move.
#: The three lattice pairs' widths and heights are not minted: they are the grid layout's arithmetic
#: on the design's 12 x 6 grid (``lattice_bare_box``, which LS3 asserts they equal), measured equal on
#: main's unchanged src/ (05cd1e8); their rect sets are checked by their facts (``lattice_rects``).
BARE_WIDTH: dict[str, float] = {
    "lattice": 600.0,
    "lattice-two-events": 360.0,
    "axes": 200.0,
    "identical": 200.0,
    "bh": 920.0,
    "gate": 1000.0,
    "multi-event": 440.0,
    "one-value": 280.0,
    "three-key": 280.0,
    "vocab": 200.0,
    "hostile": 200.0,
    "lattice-titled": 600.0,
    "partial": 200.0,
    "partial-b": 200.0,
    "traded": 240.0
}
BARE_PANEL_HEIGHT: dict[str, dict[str, float]] = {
    "lattice": {
        "tripped": 332.0
    },
    "lattice-two-events": {
        "held": 500.0,
        "tripped": 500.0
    },
    "axes": {
        "fail": 820.0
    },
    "identical": {
        "fail": 820.0
    },
    "bh": {
        "fail": 444.0
    },
    "gate": {
        "fail": 332.0
    },
    "multi-event": {
        "fail": 220.0,
        "crash": 220.0
    },
    "one-value": {
        "fail": 192.0
    },
    "three-key": {
        "fail": 192.0
    },
    "vocab": {
        "fail": 192.0
    },
    "hostile": {
        "fail": 192.0
    },
    "lattice-titled": {
        "tripped": 332.0
    },
    "partial": {
        "fail": 248.0
    },
    "partial-b": {
        "fail": 248.0
    },
    "traded": {
        "crash": 220.0,
        "fail": 220.0
    }
}
RECT_SET_SHA256: dict[str, dict[str, str]] = {
    "axes": {
        "fail": "2e70339ddc493a738427684da54f0ef9fbbd967ba32c7216bacea3677271baf5"
    },
    "identical": {
        "fail": "322015428ac90fe1a41cc09925fc6eddb66de0aec71aa2a8caf47e8d2b99b613"
    },
    "bh": {
        "fail": "6a9a5840c49198ad855b086bb030321de83300a8a4e0720ad44f9b7884cbf552"
    },
    "gate": {
        "fail": "d002f71a71472f5dc6342ddd8f38e9c04e0f2d0524d2198dbfca871e8d258552"
    },
    "multi-event": {
        "fail": "113baa938d51e95632eb766ea9db7c547a959639b370147ea0bea35222c10fec",
        "crash": "1cd85268c74c53a5425dcddc44e111632e230c80cebee85e41f97f9d3afc5a7a"
    },
    "one-value": {
        "fail": "3533c10e18d541a4bb9fe381c3ead4501fc10beb05710fa41bdb75d102f5d0a2"
    },
    "three-key": {
        "fail": "10e914dc7eea9a7734341a0075bd878ddf87c915fbca8d26d315a3d750270cec"
    },
    "vocab": {
        "fail": "0035e625570c0e89560ed5eede39eb6af11440b08a2646f070ae8c5b8711ac10"
    },
    "hostile": {
        "fail": "fd8bd55a4b19d460625ae46be32357bc82491535cec164ddae186318b0881c9c"
    },
    "partial": {
        "fail": "b3a700424e39cfd4c4d59a14ef74120fb27092f437737c8d03b6d063045f2cb2"
    },
    "partial-b": {
        "fail": "b3a700424e39cfd4c4d59a14ef74120fb27092f437737c8d03b6d063045f2cb2"
    },
    "traded": {
        "crash": "e7daf18a09fc20402bf19cfcd292d7c8a8c9fb39b01f7ed53dbc70090926dbbe",
        "fail": "3dc4c27455dafeb2ff359d09ae29740dc9db1ec4fe9552bf734c171458d9ab15"
    }
}
#: LS19. Per pair and region, the sha256 of the region's lines with the retired unverified tails, the
#: new ones, the MDE-meaning sentence's ``ADR-018's``, the trade or complement line and the holes JSON block
#: normalised away (each named in the conventions above). Green before and after.
REGION_SHA256: dict[str, dict[str, str]] = {
    "axes": {
        "Result": "8eaabfe0f29b5642660eeb10e3cc9baed9b44a2f3b66c428edca31c5c53feeb4",
        "Honesty": "e84a5d18112e5a08d56a07ec1dfa4e7240b51742902d1ef649120d267a4d00b3",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "c53ac2d09a955514157bd19edc481268ddde73039d707e1c7a9a619860992d42",
        "Cells": "3c40e73c8f12438a83b54c71518d5a27e343116dea71a5db4060e29e7414b13d",
        "Cell": "6b50964fb7bbf09eb56fc91ce95a3f3df767a32de42ed0250bf19a5118e1ce02",
        "Worst cells": "89e39a8f04a392ac919ce9fefa4a580f4149777475d37326ddc6791b8cc3fec0",
        "Provenance": "25a96a5ff36e9fb2b8efef69621cef26c170be0831a91f0c9df82258d2e2d611"
    },
    "identical": {
        "Result": "8eaabfe0f29b5642660eeb10e3cc9baed9b44a2f3b66c428edca31c5c53feeb4",
        "Honesty": "41e8b3c0340720d7e43752498400f66ddbef7acea90d3127b0388d9cc69c64ea",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "bf766a516d3e648811391324291509487ea4d9b3b54ab6a6b64cfcf2e7b3b2bd",
        "Cells": "c213deff0415997a37d6c3e7a83131e330a6261b13b835e657e649986ad2bbc1",
        "Cell": "49ff30ecf2a451ebb795ee06f3efe54d4965035deb5b0d6493e93295efb8e12f",
        "Worst cells": "362361b98e5cd78245b84ef538d0ca872c3fd26446f6195bdf8490d366fba5f0",
        "Provenance": "c3ab26977e6a75c2e1ffdcc8331e0fd9516e84e04880ec6c4f194a40788b48f8"
    },
    "bh": {
        "Result": "1b986499207f63a76c04007cc19e0b6ac6e17f0ec7ffabb74260d86ad568e4a2",
        "Honesty": "ecc07c71c6fd5c0b0876263cf59ffebeec43ad3665e3263859df3372c929e19c",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "47ddc7259f1c8797a46e593631f45006a91dfc9da9cd3a028163d9e509b2d620",
        "Cells": "5b584fdb05c1c02a9412dc3b29c2d5f1a3fd284ccec6660f3bec2b7bb0d1457c",
        "Cell": "d0a60b85ae4f9443a5a44eebe502d68d439e5a89640658619afb71139db62714",
        "Worst cells": "dfce64c090fce7e67c96599de2b196479fd95edc983707622c80ee9b9a026652",
        "Provenance": "bcc658c4833a62bd53e6e103948cc42bdead04ce1619b5960efe6901bf9439d1"
    },
    "gate": {
        "Result": "785057a8636adc229fc6c694bc36a9289d0861cef8d9510bccd2bd8d428463c2",
        "Honesty": "4fdedbe288dec390f2700e6142db21385fd2622cf78cf38a3ab1b9883f89cc8d",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "fcf925d2daa339120c0fc5096797d9dfcae3d264700b30f0ff44dca7c76f376c",
        "Cells": "5b584fdb05c1c02a9412dc3b29c2d5f1a3fd284ccec6660f3bec2b7bb0d1457c",
        "Cell": "9de14b6364f5f17095d772b6f05d09844faf531ad189004d07b95a1bb4795c4d",
        "Worst cells": "a662553f2f1d44f2882bc4dc771975517df667ecee7212d0067a180ddb8d4ba8",
        "Provenance": "b2e1361e55bb48da686a6336dc144a5040786a8a9a3dc1bbbd8bc7a06a24a05f"
    },
    "multi-event": {
        "Result": "52a2856902fecad01d45701267b56bd052d4d2d7d98e57274b2b50d6ab22abbf",
        "Honesty": "4d4d4c733d97fe13a989e2381090cb70f2b7a431528eba248f0d9bdf0de31485",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "f2295c600622f662770d21e4fa7b8a13f75c94f400497573f8d8f08335055b0d",
        "Cells": "ef2dfeb65f586ae30af05a01ef61f1c1459702fb850ff15e08ef89f71f691e4a",
        "Cell": "636fd9f7d277d93d52836c5a24f567461932fe4533fa52150dfa777255f96870",
        "Worst cells": "19fb4f1e69e3832157f148b83b1dc38d6c3c32551709d9993209cfca132bf2f7",
        "Provenance": "a4af3bafa0a31cee590d0bfd966ea678d625a908845a4209381d28455189da6f"
    },
    "one-value": {
        "Result": "1a3812de2e519c3221077c1883fc2b0a3d9135dafff2d9af529fd843e8135c14",
        "Honesty": "2ef21087b61b7c914b4598c22f576bd97147f61e4577bd5a88aed6902c6a1eac",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "b0f6d63c36cac008ad8196ec378f7d3986a85c7c4e571758cd05ecdf3f684565",
        "Cells": "1be3f951cdaa408e8704389605045cb0021f2ad995229ffdbd1462aa580096db",
        "Cell": "4c1f9776e3499c2beda6a4cbe86fcf8b4f77bb642828c45863353ebe3cd0d840",
        "Worst cells": "071fac09ebe101d9848fb58609230e4e6be100219c74e5bf0165b8596a1646ee",
        "Provenance": "a49c2cd9973cd179028c07a4b2cba44abffe3e5206c241da2ed759b4ca17bfca"
    },
    "three-key": {
        "Result": "2a3b90c3d6a730d3bb34df7221cee88a3ceea3032fd93e9f89c523a0a02731c4",
        "Honesty": "520f9708edccad02028ba0dc025570c82dc48e501d076da92bd9b53cc4a4569a",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "da6d149fcdefc0cf45744de247fdb3d7177b6b946f1f996276822984bb3be05e",
        "Cells": "5cfde57429d3bdded87ee3fb8c3a2b8b6d2f8b6fc21ca04345c6ddc08e24fa31",
        "Cell": "ddb0b6b8340d694eb3a43fb5e60264fd7431f44dfb38bcb23637eeabb3afa983",
        "Worst cells": "21ed782f313f9246995c76835405c4204db58f79cc062ad45066a2a39a08a6bb",
        "Provenance": "8811c630753b05828421ac98d0e2f3dc3075dfc01f4a1108ba8bd872f643bdbc"
    },
    "vocab": {
        "Result": "e7b31766fb7a1c145259924859000f4c67e67f45e72a07a33e5b068f0fe7af2b",
        "Honesty": "104f560124a32d0e6ec843edde43f313abdc2c816f1be6d95f38d71edd71f79c",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "7e23b11a5bdc4cb1d66684694a1474fb8f1937ff612805bd005e4880026cef33",
        "Cells": "5148a27636bbdd2630b772d6916b65eaaed7974638e4f9cf331c635740f1cf5b",
        "Cell": "6dc47ef914752e3a085e151d9454924364bab6e291c065c9823219d549bfe6c1",
        "Worst cells": "5c96f66411336b19d922c328f2aa13ffeb43baa9ce1cbecba581685b25c3ea90",
        "Provenance": "2fda0ac316c96a7261190d4b2661496e1477c09f727db80118e04f9e0bd9d421"
    },
    "hostile": {
        "Result": "e7b31766fb7a1c145259924859000f4c67e67f45e72a07a33e5b068f0fe7af2b",
        "Honesty": "df2abf5c7dd9754e040447ef4823ef707c1ecbdb019f017640e8d994384657c3",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "7e23b11a5bdc4cb1d66684694a1474fb8f1937ff612805bd005e4880026cef33",
        "Cells": "1dd3804a2178cc145d9e4400399db882576035171d09ca85428ff1b0881189d7",
        "Cell": "17bb7c8111a9718a790d5eaecc5d539be5f74c798145d4806d97ae74ac9d380b",
        "Worst cells": "0d73d36d3d99092724b34d930096a8cac383aee59a85cfe34b4e11cdc1f6b6e9",
        "Provenance": "9e9b246c4204602dc7e99fca5a8b52ae842d1abd54baa6d6a158b0938e7174e6"
    },
    "partial": {
        "Result": "c275359e965f3e9ae8621d19388d7e21801b25c4aee07d1838a19af5863aaf1e",
        "Honesty": "ad1984f57b1c9740c1752ca8830032a9dc2c746a3de0b0121e4761e5a4b4a395",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "eb29f0fb8a96a28dc96aa5d82a0b9e586c52c8c553e008918719b892a916923c",
        "Cells": "c213deff0415997a37d6c3e7a83131e330a6261b13b835e657e649986ad2bbc1",
        "Cell": "be5c0348ba217057c8be546aec836bb3d85e6d8ad835d598c2be159e9b517a5c",
        "Worst cells": "4d54cbb2c0637b95dc5f7d51b5da2a9fb86016f935660794ba22da8977a4f746",
        "Provenance": "afb76ec8b793c9a6f575ba067d37f0807e158a95b50a1a9aadb735b36bb17ceb"
    },
    "partial-b": {
        "Result": "c275359e965f3e9ae8621d19388d7e21801b25c4aee07d1838a19af5863aaf1e",
        "Honesty": "ad1984f57b1c9740c1752ca8830032a9dc2c746a3de0b0121e4761e5a4b4a395",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "eb29f0fb8a96a28dc96aa5d82a0b9e586c52c8c553e008918719b892a916923c",
        "Cells": "c213deff0415997a37d6c3e7a83131e330a6261b13b835e657e649986ad2bbc1",
        "Cell": "be5c0348ba217057c8be546aec836bb3d85e6d8ad835d598c2be159e9b517a5c",
        "Worst cells": "4d54cbb2c0637b95dc5f7d51b5da2a9fb86016f935660794ba22da8977a4f746",
        "Provenance": "8b83c1056455c49c67b4debfef71d2b7f58808dfdf5ddff90558c60e0b50c29d"
    },
    "traded": {
        "Result": "936619210f729d33f265595efd16251aa3c71e8add3cef28bc5ae2b2afd77e7d",
        "Honesty": "3b7cfa0aef9d3361dee50621f36f2cc3cbb32166ed7cd1b0caa6c32fa6339940",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "9fd0e417ade585ff4291259e09dff3076fd0874866f25c9446ccbe4e89eb08be",
        "Cells": "bd80db6990bce238cb732ba70a9a74c15d836d9ce6e980b21d3829bb85a7568a",
        "Cell": "163cd7ecb92a22e0cb6f13edf385c646e7d6488e284ff96c64e14971caa51e7f",
        "Worst cells": "6f6629ddc4e93e6e0427be995e34d4c072328c915c5510db375c2f970eced740",
        "Provenance": "03d6bb32a83661c2d8b532f47f7057b2bbd7dde226e062262779bce87852ad6b"
    }
}
# ---- pins end ----


# ---------- the lattice pairs: what the bare-tree digests guarded, from the design ----------

#: The three pairs over the generated lattice (``tests/lattice.py``). Their figure and their Result,
#: Not verified and Provenance regions are checked against the design and the run identities, not
#: against a digest of a page.
LATTICE_PAIRS = ("lattice", "lattice-two-events", "lattice-titled")
#: The grid body's layout, restated (``report._grid_body``): a cell is at most 40 px wide over 880 px
#: and at most 28 px high over 560 px, the grid starts 96 px in when there is a y axis, 24 px of
#: margin on the right, 52 px of top band and 112 px of bottom band before anything wraps, and the
#: significance glyph is a 4 px square 1 px inside the cell's top right corner.
GRID_LEFT_WITH_Y, GRID_RIGHT, GRID_TOP, GRID_BOTTOM, GLYPH = 96, 24, 52, 112, 4
#: The dark theme's colour rule, restated (``report._fill``, ``_cell_fill``): a nine-stop ramp from
#: the survived colour through neutral to the failed colour, linear in sRGB, a non-significant
#: change drawn 0.45 of the way toward neutral, both arms at 0% or both at 100% drawn saturated.
DARK_NEUTRAL, DARK_SATURATED, SURVIVED, FAILED, NONSIG_SCALE = "#1F1F22", "#2A2A2E", "#3ECF8E", "#FF4D4D", 0.45


def lattice_bare_box(cols: int, rows: int) -> tuple[float, float]:
    """A grid panel's width and its height before anything wraps, from the layout above."""
    cell_w, cell_h = max(4, min(40, int(880 / cols))), max(4, min(28, int(560 / rows)))
    return float(GRID_LEFT_WITH_Y + cols * cell_w + GRID_RIGHT), float(GRID_TOP + rows * cell_h + GRID_BOTTOM)


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = (tuple(int(h[k : k + 2], 16) for k in (1, 3, 5)) for h in (a, b))
    return "#" + "".join(format(int(round(min(255.0, max(0.0, x + (y - x) * t)))), "02X") for x, y in zip(ra, rb, strict=True))


def dark_fill(ratio: float, significant: bool) -> str:
    stops = [*(_mix(DARK_NEUTRAL, SURVIVED, t) for t in (1.0, 0.75, 0.5, 0.25)), DARK_NEUTRAL, *(_mix(DARK_NEUTRAL, FAILED, t) for t in (0.25, 0.5, 0.75, 1.0))]
    r = max(-1.0, min(1.0, ratio)) * (1.0 if significant else NONSIG_SCALE)
    if r == 0.0:
        return DARK_NEUTRAL
    pos = (r + 1.0) * 4.0
    lo = min(len(stops) - 2, int(pos))
    return _mix(stops[lo], stops[lo + 1], pos - lo)


def lattice_family(events: Sequence[str], q: float = 0.05) -> dict[tuple[str, str], dict[str, Any]]:
    """Per (event, condition) of the lattice under the unpaired test: the design's counts, scipy's
    Fisher p (``lattice.fisher``) and one BH family over every event's conditions together."""
    rows = [(event, r) for event in events for r in lattice.fisher(event, q).values()]
    qs = lattice.bh([r["p"] for _, r in rows])
    out = {}
    for (event, r), adjusted in zip(rows, qs, strict=True):
        flagged = bool(adjusted < q)
        out[(event, r["config_hash"])] = {**r, "q": float(adjusted), "direction": "unchanged" if not flagged else ("lower" if r["delta"] < 0 else "higher")}
    return out


def lattice_directions(events: Sequence[str]) -> dict[str, tuple[int, int]]:
    family = lattice_family(events)
    return {e: (sum(r["direction"] == "lower" for (ev, _), r in family.items() if ev == e), sum(r["direction"] == "higher" for (ev, _), r in family.items() if ev == e)) for e in events}


def lattice_rects(p: Pair, event: str) -> list[dict[str, str | None]]:
    """The grid and glyph rects of one panel of a lattice pair as the layout and the colour rule
    place them, from the design alone: one rect per condition at its grid position (``x`` over the
    pair's x axis values in order, ``y`` over its y axis values), ``data-cell`` its key, its fill from
    the change over the colour bound and the BH family over the pair's events, ``data-sat`` on the
    conditions both arms hold at 0% or 100%, ``data-trade`` on the conditions one event flagged lower
    and another higher; a glyph on every flagged condition."""
    family = lattice_family(p.events)
    biggest = max(abs(r["delta"]) for r in family.values())
    steps = int(biggest * 20)
    bound = (max(steps + (steps < biggest * 20), 1)) / 20
    assert bound == p.structure["view"]["bound"] == 0.6, (p.name, bound, p.structure["view"]["bound"])
    trades = {h for (_, h) in family if {family[(e, h)]["direction"] for e in p.events} >= {"lower", "higher"}}
    values = {lattice.X: list(lattice.GAIN), lattice.Y: list(lattice.LOAD)}
    xs, ys = values[p.x], values[str(p.y)]
    cell_w, cell_h = max(4, min(40, int(880 / len(xs)))), max(4, min(28, int(560 / len(ys))))
    rects: list[dict[str, str | None]] = []
    for cell in lattice.design_cells():
        r = family[(event, lattice.config_hash(cell.config))]
        i, j = xs.index(cell.config[p.x]), ys.index(cell.config[str(p.y)])
        x, y = GRID_LEFT_WITH_Y + i * cell_w, GRID_TOP + j * cell_h
        saturated = r["events_a"] == r["events_b"] and r["events_a"] in (0, lattice.N)
        significant = r["direction"] != "unchanged"
        fill = DARK_SATURATED if saturated else dark_fill(r["delta"] / bound, significant)
        rects.append({"x": str(x), "y": _fmt(float(y), "num"), "width": str(cell_w), "height": str(cell_h), "fill": fill,
                      "data-cell": r["config_hash"], "data-sig": None, "data-trade": "1" if r["config_hash"] in trades else None,
                      "data-sat": "1" if saturated else None})
        if significant:
            rects.append({"x": str(x + cell_w - GLYPH - 1), "y": _fmt(float(y + 1), "num"), "width": str(GLYPH), "height": str(GLYPH),
                          "fill": None, "data-cell": None, "data-sig": "1", "data-trade": None, "data-sat": None})
    return rects


def lattice_worst_first(events: Sequence[str], q: float = 0.05) -> list[str]:
    """The events in worst-first order under log-rank, from lifelines' test per condition on the
    stored times (``lattice.logrank``) and one BH family over every event's conditions together:
    by the count of conditions flagged higher, then lower, then the name."""
    rows = [(event, r) for event in events for r in lattice.logrank(event, q=1.0).values()]
    qs = lattice.bh([r["p"] for _, r in rows])
    counts = {e: [0, 0] for e in events}
    for (event, r), adjusted in zip(rows, qs, strict=True):
        if adjusted < q:
            assert r["direction"] in ("lower", "higher"), r
            counts[event][r["direction"] == "lower"] += 1
    assert counts == {lattice.EVENT: [12, 25], lattice.OTHER: [0, 0]}, counts
    return sorted(events, key=lambda e: (-counts[e][0], -counts[e][1], e))


def lattice_headline(events: Sequence[str], order: Sequence[str]) -> str:
    """The headline the lattice pair must print, from the reference's counts: each event's flagged
    conditions in direction words (no event declares a kind), in the panels' ``order``."""
    counts = lattice_directions(events)
    assert sorted(order) == sorted(events), (order, events)
    return " · ".join(f"{e}: {counts[e][0]} lower, {counts[e][1]} higher" for e in order) + (
        f"\n(aalen_johansen + fisher_bh, BH q<0.05 over {lattice.CELLS * len(events)} tests, unpaired)"
    )


def assert_lattice_region(p: Pair, heading: str) -> None:
    """What the bare-tree digest of a lattice pair's Result, Not verified or Provenance region
    guarded, read line by line against the design, the run identities and the payload."""
    lines = region_lines(p.page, heading)
    if heading == "Result":
        order = [panel["event"] for panel in p.structure["panels"]]
        assert order == ([lattice.OTHER, lattice.EVENT] if len(p.events) == 2 else [lattice.EVENT]), (p.name, order)
        headline = lattice_headline(p.events, order)
        assert headline == {1: "tripped: 22 lower, 0 higher\n(aalen_johansen + fisher_bh, BH q<0.05 over 72 tests, unpaired)",
                            2: "held: 0 lower, 22 higher · tripped: 22 lower, 0 higher\n(aalen_johansen + fisher_bh, BH q<0.05 over 144 tests, unpaired)"}[len(p.events)]
        assert p.structure["headline"] == headline, (p.name, p.structure["headline"], headline)
        expected = ["<p>" + html_mod.escape(headline).replace("\n", "<br>") + "</p>", f"<p>{html_mod.escape(PAIRING_LINE)}</p>"]
        if len(p.events) == 2:
            expected.append(f"<p>{html_mod.escape(LATTICE_COMPLEMENT_LINE)}</p>")
        assert lines == expected, (p.name, lines)
        return
    if heading == "Not verified":
        # Every pair's region is the same four entries; the builder-made pairs' frozen digest of it
        # is the one shared value, so the lattice pairs are held to it with no digest of their own.
        shared = {REGION_SHA256[name]["Not verified"] for name in REGION_SHA256}
        assert len(shared) == 1, shared
        text = as_before_pf4(normalised_region(page_as_0_0_1_wrote_it(p.page), heading), heading, p)
        assert sha(text) in shared, p.name
        return
    if heading == "Provenance":
        manifest_a, manifest_b = lattice.manifest(lattice.RUN_A), lattice.manifest(lattice.RUN_B)
        version = manifest_a["proofload_version"]
        assert version == manifest_b["proofload_version"] == "0.0.1" and lattice.HORIZON == 5.0
        assert manifest_a["run_salt"] == manifest_b["run_salt"] == lattice.SALT
        items = [
            ("events", ", ".join(p.events)), ("inferred", "false"), ("non event", "none"),
            ("n tests", str(lattice.CELLS * len(p.events))), ("method", "fisher_bh"), ("seed identity match", "true"),
            ("unpaired analysis", "true"), ("q", "0.05"), ("t unit", lattice.T_UNIT), ("horizon", "5"),
            ("n not comparable", "0"), ("dropped a", "0"), ("dropped b", "0"), ("episodes censored at horizon", "0"),
            ("n absent", "0"), ("Prove version", f"{version} (as proofload)"), ("written by proofload " + version, None),
            ("run id a", lattice.RUN_A), ("run id b", lattice.RUN_B), ("run salt", lattice.SALT),
            ("observation cap a", "not recorded"), ("observation cap b", "not recorded"), ("trace spans a", "0"),
            ("trace spans b", "0"), ("observation cut spans a", "0"), ("observation cut spans b", "0"),
        ]
        expected = "<ul>" + "".join(f"<li>{html_mod.escape(k if v is None else f'{k}: {v}')}</li>" for k, v in items) + "</ul>"
        assert lines == [expected, "</body>", "</html>"], (p.name, lines)
        diff = p.structure["diff"]
        assert (diff["events"], diff["n_tests"], diff["run_id_a"], diff["run_id_b"], diff["run_salt"], diff["poisson_prove_version"]) == (
            list(p.events), lattice.CELLS * len(p.events), lattice.RUN_A, lattice.RUN_B, lattice.SALT, f"{version} (as proofload)"
        ), (p.name, diff)
        return
    raise AssertionError((p.name, heading))


def normalised_region(page: str, heading: str) -> str:
    lines = region_lines(page, heading)
    if heading == "Result":
        lines = [line for line in lines if not (line.startswith("<p>Trade:") or "are complements here" in line or "Compared as two separate samples" in line)]
    if heading == "Cell":
        lines = [line for line in lines if not re.match(r'<script type="application/json" id="[\w-]+-holes">', line)]
    text = "\n".join(lines)
    for tail in (*RETIRED_TAILS, *NEW_TAILS):
        text = text.replace(html_mod.escape(tail), "")
    return text.replace(html_mod.escape(MDE_MEANING_BARE), html_mod.escape(MDE_MEANING_PLAIN))


# ---------- LS1: no cell swallows its own click ----------


def page_as_0_0_1_wrote_it(page: str) -> str:
    """PF0 (Q4, section 2.5): the rename changes three things on a page: the version entry of the
    provenance list, the version key in the arm table, and the ids of the page's two data blocks,
    which named the old product. First assert each is there as the rename writes it (the data
    blocks are ``prove-cells`` and ``prove-holes``, ruled 2026-10-14), then put each back as 0.0.1
    wrote it before the frozen digest is taken."""
    assert 'id="prove-cells"' in page and 'id="prove-holes"' in page and 'getElementById("prove-cells")' in page
    assert "<td>poisson_prove_version</td>" in page and "proofload-cells" not in page and "proofload-holes" not in page
    found = re.findall(r"<li>Prove version: [^<]*</li>", page)
    assert len(found) == 1 and "proofload version:" not in page, found
    page = re.sub(r'(id="|getElementById\(")prove-(cells|holes)"', r'\1proofload-\2"', page)
    page = page.replace("<td>poisson_prove_version</td>", "<td>proofload_version</td>")
    page = re.sub(r"<li>Prove version: [^<]*</li>", "<li>proofload version: 0.0.1</li>", page)
    return re.sub(r"<li>[^<]*written by proofload[^<]*</li>", "", page)


def test_ls1_the_inert_selector_list_names_the_figures_text_beside_the_glyph_and_the_path(every_pair: list[Pair]) -> None:
    for p in every_pair:
        dom = parse_html(p.page)
        rules = css_rules("".join(dom.styles))
        inert = [s for selectors, decls in rules if decls.get("pointer-events") == "none" for s in selectors]
        assert inert, (p.name, rules)
        assert any("[data-sig]" in s for s in inert), (p.name, inert)
        for tag in INERT_LAST_TAGS:
            assert any(last_compound_tag(s) == tag for s in inert), (p.name, tag, inert)
        assert not any("data-cell" in s or "data-mde" in s for s in inert), (p.name, inert)


def test_ls1_every_data_cell_node_stays_clickable_and_every_text_inside_the_figure_is_inert(every_pair: list[Pair]) -> None:
    for p in every_pair:
        dom = parse_html(p.page)
        rules = css_rules("".join(dom.styles))
        cells = [n for n in dom.nodes if "data-cell" in n.attrs]
        assert cells, p.name
        for node in cells:
            assert styles_of(node, rules).get("pointer-events") != "none", (p.name, node.attrs)
        texts = [n for n in dom.nodes if n.tag == "text" and n.inside(id="pl-figure")]
        assert texts, p.name
        for node in texts:
            assert styles_of(node, rules).get("pointer-events") == "none", (p.name, node.texts[:1])
        # The page's own tables and paragraphs are untouched: no ``text`` selector without ``svg``.
        for n in dom.nodes:
            if n.tag in ("td", "th", "p", "li") and not n.inside(id="pl-figure"):
                assert styles_of(n, rules).get("pointer-events") != "none", (p.name, n.tag)


def test_ls1_the_rule_lives_in_the_viewers_layout_and_not_in_the_reports_stylesheet() -> None:
    """Sole catch for a build that adds the rule to ``report._html_style``: the page reads both
    sheets, so only the source can tell them apart."""
    from poisson_prove.report import _html_style

    layout = viewer()._LAYOUT
    inert = [rule for rule in layout.split("}") if "pointer-events:none" in rule]
    assert len(inert) == 1, layout
    selectors = [s.strip() for s in inert[0].split("{")[0].split(",")]
    assert any(last_compound_tag(s) == "text" and s.startswith("svg") for s in selectors), selectors
    assert any("[data-sig]" in s for s in selectors) and any(last_compound_tag(s) == "path" for s in selectors), selectors
    assert "pointer-events" not in _html_style("dark") and "pointer-events" not in _html_style("light")


# ---------- LS2: no text the figure draws leaves the figure ----------


def wrapped_texts(p: Pair) -> list[tuple[str, list[str], float, float]]:
    """(kind, lines, font, x) for every text D9 wraps, from the structure and the restated wrap."""
    layout = expected_layout(p)
    out = [("title", layout["title"], FONT + 2.0, float(STACKED_TITLE_X))]
    out.extend((f"header/{i}", lines, float(FONT), float(STACKED_TITLE_X)) for i, lines in enumerate(layout["header"]))
    for event, entry in layout["panels"].items():
        left = float(entry["left"])
        out.append((f"{event}/title", entry["title"], FONT + 2.0, left))
        out.append((f"{event}/headline", entry["headline"], float(FONT), left))
        out.append((f"{event}/caption", entry["caption"], FONT - 2.0, left))
        if WRAPPED_HONESTY:
            out.extend((f"{event}/honesty/{i}", lines, FONT - 2.0, left) for i, lines in enumerate(entry["honesty"]))
    return out


def test_ls2_every_wrapped_text_of_the_figure_is_drawn_whole_and_ends_inside_the_box(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        for source in ("heatmap_svg",):
            texts, width, _ = svg_texts(p.structure[source])
            contents = [t.content for t in texts]
            for kind, lines, font, x in wrapped_texts(p):
                # PF2 (spec section 4.3): the default title names the runs, so a wrapped title can
                # repeat a line (``synthetic@v0`` as its first and third line). A line is therefore
                # read in its place, as the k-th of the wrapped text's lines drawn in order at its
                # font and x, rather than by its content alone.
                same = [t for t in texts if t.font == font and t.x == x]
                starts = [i for i in range(len(same) - len(lines) + 1) if [t.content for t in same[i : i + len(lines)]] == lines]
                for k, line in enumerate(lines):
                    hits = [same[i + k] for i in starts]
                    assert hits, (p.name, kind, line[:70], [c[:40] for c in contents if c.startswith(line[:12])])
                    for t in hits:
                        assert right_edge(t) <= width, (p.name, kind, line[:70], right_edge(t), width)
                        assert t.wrap == (k > 0), (p.name, kind, k, line[:70])
            assert not any(t.content.endswith("…") and t.anchor == "start" and t.font in (FONT + 2, FONT) for t in texts), (p.name, "a title or headline was truncated")


def test_ls2_the_legend_captions_last_six_words_are_present_on_the_traded_pairs(lattice_two: Pair, traded: Pair) -> None:
    """Sole catch for a fix that truncates the caption with an ellipsis; a widened box is LS3's."""
    for p in (lattice_two, traded):
        texts, _, _ = svg_texts(p.structure["heatmap_svg"])
        # PF4 (PF4.20): neither pair declares a kind, so the caption's notches clause reads in
        # direction words and LEGEND_TAIL's safer/worse wording is no longer asserted. What stays
        # is the caption drawn whole: on every panel the notches clause is there, closed, and
        # nothing is cut with an ellipsis.
        for event, panel in panel_groups(p.structure["heatmap_svg"]):
            caption = caption_checked(drawn_legend_caption(panel, panel_left(panel)), event, True)
            tail = caption[caption.index(NOTCHES) :]
            assert tail.endswith(")") and "(" in tail and len(tail.split()) >= 6, (p.name, event, tail)
        assert not any(t.content.endswith("…") and "corner" in t.content for t in texts), p.name


def test_ls2_the_same_wrap_reaches_the_reports_figure_and_the_receipt(tmp_path: Path) -> None:
    """``report`` draws the figure with the same builders: its ``heatmap.svg`` and the receipt's
    inline figure carry the wrapped caption on the two-event lattice pair."""
    out = tmp_path / "rep"
    # PF3 (Q17, spec sections 4.4 and 14; R1): the lattice's runs share a salt, so the default is now the
    # paired test; LATTICE_COMPLEMENT_LINE's 22 is the unpaired test's, named.
    code, _, err = run_cli(["--store", str(LATTICE_ROOT), "report", LATTICE_A, LATTICE_B, "--event", lattice.EVENT, "--event", lattice.OTHER, "--x", lattice.Y, "--y", lattice.X, "--method", "fisher_bh", "--out", str(out)])
    assert code == 0, err[-400:]
    for name in ("heatmap.svg", "receipt.html"):
        text = (out / name).read_text(encoding="utf-8")
        svg = text if name.endswith(".svg") else re.search(r"(<svg.*?</svg>)", text, re.S).group(1)  # type: ignore[union-attr]
        texts, width, _ = svg_texts(svg)
        # PF4 (PF4.20): the notches clause reads in direction words (see the test above); each
        # panel's caption is drawn whole with it, and no caption line leaves the box.
        for event, panel in panel_groups(svg):
            caption = caption_checked(drawn_legend_caption(panel, panel_left(panel)), event, True)
            assert caption[caption.index(NOTCHES) :].endswith(")"), (name, event, caption)
        assert all(right_edge(t) <= width for t in texts if t.font == FONT - 2 and t.content.startswith("delta = ")), name
    md = (out / "report.md").read_text(encoding="utf-8")
    assert LATTICE_COMPLEMENT_LINE in md and RETIRED_TRADE_TAIL not in md


# ---------- LS3: the figure grows and the grid does not move ----------


def test_ls3_the_box_grows_by_the_extra_lines_and_by_nothing_else(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        layout = expected_layout(p)
        _, width, height = svg_texts(p.structure["heatmap_svg"])
        assert width == BARE_WIDTH[p.name], (p.name, width)
        if p.name in LATTICE_PAIRS:
            # the pins are the layout's arithmetic on the design's grid (x across, y down)
            sizes = {lattice.X: len(lattice.GAIN), lattice.Y: len(lattice.LOAD)}
            for panel in p.structure["panels"]:
                assert [float(v) for v in panel["x_values"]] == {lattice.X: list(lattice.GAIN), lattice.Y: list(lattice.LOAD)}[p.x], (p.name, panel["x_values"])
                assert lattice_bare_box(sizes[p.x], sizes[str(p.y)]) == (BARE_WIDTH[p.name], BARE_PANEL_HEIGHT[p.name][panel["event"]]), p.name
        expected_total = STACKED_HEADER_H + TITLE_LINE_H * (len(layout["title"]) - 1) + STACKED_LINE_H * sum(len(lines) for lines in layout["header"])
        for event, panel in panel_groups(p.structure["heatmap_svg"]):
            entry = layout["panels"][event]
            growth = TITLE_LINE_H * (len(entry["title"]) - 1) + BODY_LINE_H * (len(entry["headline"]) - 1) + BODY_LINE_H * (len(entry["caption"]) - 1)
            if WRAPPED_HONESTY:
                growth += BODY_LINE_H * sum(len(lines) - 1 for lines in entry["honesty"])
            w, h = panel_box(panel)
            assert w == width, (p.name, event, w, width)
            assert h == BARE_PANEL_HEIGHT[p.name][event] + growth, (p.name, event, h, BARE_PANEL_HEIGHT[p.name][event], growth)
            expected_total += h
        assert height == expected_total, (p.name, height, expected_total)


def test_ls3_every_grid_and_glyph_rect_is_the_dispatch_commits_up_to_the_top_growth(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        layout = expected_layout(p)
        for event, panel in panel_groups(p.structure["heatmap_svg"]):
            entry = layout["panels"][event]
            shift = TITLE_LINE_H * (len(entry["title"]) - 1) + BODY_LINE_H * (len(entry["headline"]) - 1)
            if p.name in LATTICE_PAIRS:
                # the rect set recomputed from the design, the layout and the colour rule
                expected = sorted(json.dumps(r, sort_keys=True) for r in lattice_rects(p, event))
                assert rect_set(panel, shift).split("\n") == expected, (p.name, event, shift)
                continue
            assert sha(rect_set(panel, shift)) == RECT_SET_SHA256[p.name][event], (p.name, event, shift)


# ---------- LS4: every hole says where it is ----------


def test_ls4_the_holes_block_opens_with_the_counts_and_every_row_says_where_it_is(partial: Pair) -> None:
    holes = partial.structure["holes"]
    assert len(holes) == 3 and sum(h["coords"] is None for h in holes) == 2, holes
    lines = region_lines(partial.page, "Holes")
    assert len(lines) == 2 and lines[0].startswith("<p>") and lines[1].startswith("<table>"), lines
    summary = p_lines(lines[0])[0]
    on_grid = sum(h["coords"] is not None for h in holes)
    causes = {}
    for h in holes:
        causes[h["cause"]] = causes.get(h["cause"], 0) + 1
    expected = HOLES_SUMMARY.format(n=len(holes), g=on_grid, o=len(holes) - on_grid) + " " + ", ".join(f"{cause} {k}" for cause, k in sorted(causes.items()))
    assert summary == expected, summary
    assert sum(causes.values()) == len(holes) == on_grid + (len(holes) - on_grid)
    header, rows = table_of(lines[1])
    assert header == HOLES_HEADER and len(rows) == len(holes)
    for row, hole in zip(rows, holes, strict=True):
        assert row[0] != "none" and row[0] == hole["where"], (row, hole["where"])
        assert row[1:] == [hole["cause"], hole["config_hash"], f"{hole['rows_a']}/{hole['rows_b']}", f"{hole['no_outcome_a']}/{hole['no_outcome_b']}"]
        if hole["coords"] is None:
            assert row[0].startswith(OFF_GRID_PREFIX) or any(f"{axis}=" in row[0] for axis in (partial.x, partial.y)), row[0]
        else:
            assert row[0] == hole["coords"]


def test_ls4_where_is_the_coords_on_the_grid_and_the_config_on_the_reports_axes_off_it(partial: Pair) -> None:
    view = partial.structure["view"]
    axes = [view["x_axis"], *([view["y_axis"]] if view["y_axis"] else []), *view["fixed"]]
    for hole in partial.structure["holes"]:
        assert tuple(hole) == HOLE_KEYS, tuple(hole)
        if hole["coords"] is not None:
            assert hole["where"] == hole["coords"]
            continue
        config_text = hole["config_text"]
        assert config_text is not None
        named = [f"{axis}={config_text[axis]}" for axis in axes if axis in config_text]
        assert hole["where"] == (", ".join(named) if named else OFF_GRID_PREFIX + str(hole["config_hash"])), hole["where"]
        assert named, hole


def test_ls4_a_pair_with_no_holes_keeps_the_one_line_form(lattice_one: Pair) -> None:
    assert lattice_one.structure["holes"] == []
    assert region_lines(lattice_one.page, "Holes") == [NO_HOLES_LINE]


# ---------- LS5, LS6: the page order and the answer at the top ----------


def test_ls5_the_fourteen_h2_in_order_summary_first_and_run_pair_thirteenth(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        assert h2_sequence(p.page) == list(H2_SEQUENCE), (p.name, h2_sequence(p.page))


def test_ls6_the_summary_is_first_never_folded_and_precedes_every_table_figure_and_the_run_pair(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        lines = p.page.splitlines()
        marks = h2_lines(p.page)
        assert marks[0][1] == "Summary", p.name
        start, end = marks[0][0], marks[1][0]
        region = lines[start:end]
        assert not any("<details" in line or "hidden" in line or "<summary" in line for line in region), p.name
        first_table = next(i for i, line in enumerate(lines) if line.startswith("<table"))
        first_svg = next(i for i, line in enumerate(lines) if "<svg" in line)
        run_pair = next(i for i, h in marks if h == "Run pair")
        assert end <= first_table and end <= first_svg and end < run_pair, (p.name, end, first_table, first_svg, run_pair)
        assert summary_lines(p.page), p.name


# ---------- LS7: the keys ----------


def test_ls7_the_fourteen_top_level_keys_the_schema_the_panel_keys_and_the_cell_keys(all_pairs: list[Pair]) -> None:
    assert viewer().SCHEMA == SCHEMA
    for p in all_pairs:
        s = p.structure
        # serve --json adds verdict and sentence after schema (front-door spec section 5.6).
        # PF3 (spec section 4.4, R3): and method and method_chosen right after sentence.
        assert tuple(s)[1:5] == ("verdict", "sentence", "method", "method_chosen"), (p.name, tuple(s))
        keys = tuple(k for k in s if k not in ("verdict", "sentence", "method", "method_chosen"))
        assert keys == TOP_LEVEL_KEYS and s["schema"] == SCHEMA, (p.name, tuple(s))
        for panel in s["panels"]:
            assert tuple(panel) == PANEL_KEYS, (p.name, tuple(panel))
            assert tuple(panel["mde_unchanged"]) == MDE_UNCHANGED_KEYS
            for cell in panel["cells"]:
                assert tuple(cell) == CELL_KEYS, (p.name, tuple(cell))
        for hole in s["holes"]:
            assert tuple(hole) == HOLE_KEYS


def test_ls7_the_summary_object_has_section_3_3s_shape(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        s = p.structure["summary"]
        assert tuple(s) == SUMMARY_KEYS, (p.name, tuple(s))
        assert s["partial"] is None or tuple(s["partial"]) == ("runs", "line")
        assert s["complement"] is None or tuple(s["complement"]) == ("events", "line")
        assert tuple(s["pairing"]) == PAIRING_KEYS and (s["pairing"]["line"] is None or s["pairing"]["line"] == PAIRING_LINE)
        assert [e["event"] for e in s["events"]] == [panel["event"] for panel in p.structure["panels"]]
        for entry in s["events"]:
            assert tuple(entry) == EVENT_ENTRY_KEYS, tuple(entry)
            assert len(entry["worse"]) <= p.structure["view"]["top_n"]
            for row in entry["worse"]:
                assert tuple(row) == WORSE_ROW_KEYS, tuple(row)
            assert tuple(entry["limit"]) == LIMIT_KEYS
        assert s["pointer"] == POINTER_LINE


# ---------- LS8: the version is said once ----------


def test_ls8_render_html_refuses_every_retired_version_by_name(lattice_one: Pair) -> None:
    for retired in RETIRED_SCHEMAS:
        with pytest.raises(viewer().ViewerError) as info:
            viewer().render_html({**lattice_one.structure, "schema": retired})
        assert retired in str(info.value) and SCHEMA in str(info.value), str(info.value)


def source_of(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""


def test_ls8_both_structural_refusals_interpolate_the_constant_and_no_source_names_a_retired_version() -> None:
    render = source_of(VIEWER_SOURCE, "render_html")
    intervals = next(seg for seg in render.split("raise ViewerError(")[1:] if "carries no intervals" in seg).split(")")[0]
    assert "{SCHEMA}" in intervals and "viewpair/" not in intervals, intervals
    tree_refusal = next(seg for seg in render.split("raise ViewerError(")[1:] if "carries no tree" in seg).split(")")[0]
    assert "viewpair/" not in tree_refusal, tree_refusal
    lines = VIEWER_SOURCE.read_text(encoding="utf-8").splitlines()
    at = next(i for i, line in enumerate(lines) if line.startswith("SCHEMA = "))
    start = at
    while start > 0 and lines[start - 1].startswith("#"):
        start -= 1
    outside = "\n".join(lines[:start] + lines[at:])
    for retired in RETIRED_SCHEMAS:
        assert retired not in outside, retired
        for path in SRC.rglob("*.py"):  # PF5 (spec section 17): the core is a package now, so the scan reads src/ recursively.
            if path.name != "viewer.py":
                assert retired not in path.read_text(encoding="utf-8"), (path.name, retired)
    assert f'SCHEMA = "{SCHEMA}"' in lines[at]
    assert SCHEMA in lines[0] or "viewpair/" not in lines[0], lines[0]


# ---------- LS9: every sentence is bound to a field ----------

ARITHMETIC = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Pow, ast.Mod)


def test_ls9_plain_py_computes_nothing_and_takes_the_six_payload_objects() -> None:
    tree = ast.parse(PLAIN_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ARITHMETIC):
            raise AssertionError(ast.dump(node))
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")
            assert name not in ("format", "round", "float", "abs", "sum", "max", "min"), ast.dump(node)
        if isinstance(node, ast.FormattedValue):
            assert node.format_spec is None and node.conversion == -1, ast.dump(node)
        if isinstance(node, ast.AugAssign):
            raise AssertionError(ast.dump(node))
    assert set(plain().__all__) == {"CONFIDENCE_THRESHOLDS", "TOO_SMALL_TO_TELL", "build_summary"}
    params = inspect.signature(plain().build_summary).parameters
    assert list(params) == ["panels", "view", "pair", "diff", "complement", "trade_line"] and all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params.values()), list(params)
    assert plain().CONFIDENCE_THRESHOLDS == CONFIDENCE_THRESHOLDS and plain().TOO_SMALL_TO_TELL == TOO_SMALL_TO_TELL


def test_ls9_every_numeric_substring_of_every_sentence_is_a_text_value_a_config_value_or_an_integer_field(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        allowed = set(walk_texts(p.structure)) | set(walk_ints(p.structure)) | THRESHOLD_SPELLINGS | {str(p.structure["diff"]["q"])}
        # PF4 re-freeze (PF4.35, PF4.42, PF4.44): the verdict block's detail lines are payload fields
        # themselves (summary.facts), so they are bound to a field by being one.
        facts = set(verdict_block_lines(p.structure))
        for sentence in (s for s in summary_sentences(p.structure) if s not in facts):
            for token in NUMBER_RE.findall(sentence):
                assert any(token in value for value in allowed), (p.name, token, sentence[:120])


# ---------- LS10, LS11: the two thresholds, on a hand-built panel ----------


def synthetic_cell(k: int, q: float, p_value: float, delta: float = 0.281, verdict: str = "worse", mde: float = 0.2) -> dict[str, Any]:
    return {
        "coords": f"gain={k}, load=30", "config_hash": f"{k:016x}", "n_a": 32, "n_b": 32, "rows_a": 32, "rows_b": 32,
        "no_outcome_a": 0, "no_outcome_b": 0, "events_a": 4, "events_b": 13, "rate_a": 0.125, "rate_b": 0.125 + delta, "delta": delta,
        "stat": 0.25, "p": p_value, "q": q, "mde": mde, "verdict": verdict, "config": {"gain": k, "load": 30},
        "config_text": {"gain": str(k), "load": "30"},
        "text": {"rate_a": "12.5", "rate_b": _fmt(0.125 + delta, "pp1"), "delta": _fmt(delta, "pp1"), "stat": "0.25", "p": _fmt(p_value, "sig3"), "q": _fmt(q, "sig3"), "mde": _fmt(mde, "pp0")},
    }


def synthetic_panel(cells: list[dict[str, Any]], mde_unchanged: float | None, where: str | None = "gain=9, load=30") -> dict[str, Any]:
    worse = sum(c["verdict"] == "worse" for c in cells)
    safer = sum(c["verdict"] == "safer" for c in cells)
    if mde_unchanged is None:
        honesty = HONESTY_NONE + "\nWorst-powered cell overall: 20pp (gain=0, load=30)."
        block = {"value": None, "text": None, "where": None}
    else:
        honesty = f'Worst-powered unchanged cell ({where}, n=32/32) can only detect a {_fmt(mde_unchanged, "pp0")}pp rise. "{worse} worse" is an honest claim only above that.\nWorst-powered cell overall: 20pp (gain=0, load=30).'
        block = {"value": mde_unchanged, "text": _fmt(mde_unchanged, "pp0"), "where": where}
    # PF4 (PF4.20): the hand-built panel declares its event a failure, so its counts and rows keep
    # the safer/worse words these tests are about; a panel now carries its kind and the direction
    # counts beside n_safer and n_worse (for a failure event, a rise is worse).
    return {
        "event": "tripped", "caption": f"tripped: {safer} safer, {worse} worse", "honesty": honesty, "mde_unchanged": block,
        "kind": "failure", "n_safer": safer, "n_worse": worse, "n_higher": worse, "n_lower": safer,
        "n_unchanged": len(cells) - safer - worse, "n_absent": 0, "n_present": len(cells),
        "x_values": [str(c["config"]["gain"]) for c in cells], "y_values": ["30"], "cells": cells, "worst_header": [], "worst_rows": [], "worst_hashes": [c["config_hash"] for c in cells],
    }


VIEW = {"title": "t", "x_axis": "gain", "y_axis": "load", "fixed": {}, "theme": "dark", "top_n": 10, "forest": "auto", "bound": 0.3, "sign_convention": "delta = rate_b - rate_a"}
PAIR_OBJ = {"store_root": "<store>", "created_at_gap_s": 0.0, "a": {"role": "baseline", "run_id": "a", "status": "complete"}, "b": {"role": "candidate", "run_id": "b", "status": "complete"}}
DIFF_OBJ = {"events": ["tripped"], "q": 0.25, "n_tests": 7, "seed_identity_match": True, "unpaired_analysis": True}
Q_LADDER = ((0.0005, "very sure"), (0.001, "sure"), (0.005, "sure"), (0.01, "fairly sure"), (0.02, "fairly sure"), (0.05, None), (0.2, None))
#: PF4 (PF4.5): the hand-built pair with a recorded threshold of 0.50 in both arms, where the old
#: page rule drew its line, so the threshold tests keep their boundary.
THRESHOLD_PAIR = {
    **PAIR_OBJ,
    "a": {**PAIR_OBJ["a"], "environment": {"max_mde_accepted": TOO_SMALL_TO_TELL}},
    "b": {**PAIR_OBJ["b"], "environment": {"max_mde_accepted": TOO_SMALL_TO_TELL}},
}
#: The one unchanged cell every hand-built panel carries, so its limit has a cell to name.
UNCHANGED_CELL = synthetic_cell(9, 0.9, 0.9, delta=0.0, verdict="unchanged", mde=0.2)


def summary_of(panels: list[dict[str, Any]], *, complement: tuple[str, ...] | None = None, trade_line: str | None = None, pair_obj: dict[str, Any] | None = None, diff_obj: dict[str, Any] | None = None) -> dict[str, Any]:
    return plain().build_summary(panels=panels, view=VIEW, pair=pair_obj or PAIR_OBJ, diff=diff_obj or DIFF_OBJ, complement=complement, trade_line=trade_line)


def test_ls10_the_how_sure_label_is_a_function_of_q_alone_with_the_boundaries_closed_above() -> None:
    cells = [synthetic_cell(k, q, 0.5) for k, (q, _) in enumerate(Q_LADDER)] + [UNCHANGED_CELL]
    entry = summary_of([synthetic_panel(cells, 0.2)])["events"][0]
    rows = {row["config_hash"]: row for row in entry["worse"]}
    assert len(rows) == len(Q_LADDER)
    for cell, (q, label) in zip(cells[: len(Q_LADDER)], Q_LADDER, strict=True):
        row = rows[cell["config_hash"]]
        assert row["confidence"] == label, (q, row)
        assert row["q"] == cell["text"]["q"] and row["before"] == "12.5" and row["after"] == cell["text"]["rate_b"] and row["change"] == cell["text"]["delta"]
        fields = dict(where=cell["coords"], event="tripped", before="12.5", after=cell["text"]["rate_b"], change=cell["text"]["delta"], q=cell["text"]["q"])
        if label is None:
            assert row["line"] == ROW_LINE_UNLABELLED.format(**fields), row["line"]
            assert cell["text"]["q"] in row["line"] and LABEL_START in row["line"]
        else:
            assert row["line"] == ROW_LINE.format(label=label, **fields), row["line"]


def test_ls10_no_label_reads_off_p_mutating_p_alone_changes_no_sentence() -> None:
    """Sole catch for a label on ``p``."""
    base = [synthetic_cell(k, q, 0.5) for k, (q, _) in enumerate(Q_LADDER)] + [UNCHANGED_CELL]
    moved = [{**c, "p": 1e-9, "text": {**c["text"], "p": "1.00e-09"}} for c in base]
    swapped = [{**c, "p": c["q"], "text": {**c["text"], "p": c["text"]["q"]}} for c in base]
    for other in (moved, swapped):
        assert summary_sentences({"summary": summary_of([synthetic_panel(other, 0.2)])}) == summary_sentences({"summary": summary_of([synthetic_panel(base, 0.2)])})
    on_q = [{**c, "q": 0.0005, "text": {**c["text"], "q": "5.00e-04"}} for c in base]
    assert all(row["confidence"] == "very sure" for row in summary_of([synthetic_panel(on_q, 0.2)])["events"][0]["worse"])


def test_ls10_the_labels_on_every_real_worse_row_follow_the_cells_q(all_pairs: list[Pair]) -> None:
    seen = set()
    for p in all_pairs:
        for entry, panel in zip(p.structure["summary"]["events"], p.structure["panels"], strict=True):
            cells = {c["config_hash"]: c for c in panel["cells"]}
            # PF4 (PF4.20): no fixture declares a kind, so the rows are the conditions where the
            # event rose: their verdict reads "higher" where it read "worse", and their direction is
            # "higher" either way.
            # PF4 re-freeze (PF4.27): a rising condition can have no limit (null with its note); it
            # sorts after every condition with one, as _worst's tie-break puts it.
            worse = sorted((c for c in panel["cells"] if c["direction"] == "higher"), key=lambda c: (-c["delta"], c["q"], 2.0 if c["mde"] is None else c["mde"], c["config_hash"]))
            assert [row["config_hash"] for row in entry["worse"]] == [c["config_hash"] for c in worse[: p.structure["view"]["top_n"]]], (p.name, entry["event"])
            for row in entry["worse"]:
                cell = cells[row["config_hash"]]
                assert row["confidence"] == label_for(cell["q"]), (p.name, row)
                assert (row["where"], row["before"], row["after"], row["change"], row["q"]) == (cell["coords"], cell["text"]["rate_a"], cell["text"]["rate_b"], cell["text"]["delta"], cell["text"]["q"])
                seen.add(row["confidence"])
            # PF4 (PF4.20): an event of unknown kind is counted in direction words ("rose in ...
            # fell in ..."), from the panel's n_higher and n_lower; its n_safer and n_worse are null.
            # The counts are the panel's own, so they add up to its conditions.
            assert (panel["kind"], panel["n_safer"], panel["n_worse"]) == (None, None, None), (p.name, entry["event"])
            assert panel["n_higher"] + panel["n_lower"] + panel["n_unchanged"] == panel["n_present"], (p.name, entry["event"], panel["n_higher"], panel["n_lower"], panel["n_unchanged"], panel["n_present"])
            line = entry["line"]
            assert line.startswith(f"{entry['event']}: ") and f"rose in {panel['n_higher']} " in line and f"fell in {panel['n_lower']}" in line, line
            assert NUMBER_RE.findall(line) == [str(panel["n_higher"]), str(panel["n_present"]), str(panel["n_lower"]), str(panel["n_unchanged"]), str(p.structure["diff"]["q"])], line
            assert "worse" not in line and "safer" not in line, line
    assert "very sure" in seen, seen


def test_ls11_too_small_to_tell_is_a_function_of_mde_unchanged_alone_at_0_50() -> None:
    cells = [synthetic_cell(0, 1e-5, 1e-6), synthetic_cell(9, 0.9, 0.9, delta=0.0, verdict="unchanged", mde=0.5)]
    # PF4 (PF4.5, PF4.17): the 50-point rule gives way to the runs' recorded threshold, and a limit
    # is too small to tell only above it (section 8.4; at or below it is no significant change).
    # The hand-built pair records 0.50 in both arms, so the boundary stays at 0.50 and a limit of
    # exactly 0.50 is no longer labelled.
    for value, labelled in ((0.49, False), (0.50, False), (0.51, True), (0.999, True), (0.0, False)):
        limit = summary_of([synthetic_panel(cells, value)], pair_obj=THRESHOLD_PAIR)["events"][0]["limit"]
        fields = dict(where="gain=9, load=30", n_a=32, n_b=32, mde=_fmt(value, "pp0"))
        assert limit["mde"] == _fmt(value, "pp0") and limit["where"] == "gain=9, load=30", limit
        if labelled:
            assert limit["label"] == "too small to tell" and limit["line"] == LIMIT_LINE_LABELLED.format(**fields), limit
        else:
            assert limit["label"] is None and limit["line"] == LIMIT_LINE.format(**fields), limit
    limit = summary_of([synthetic_panel(cells, None)], pair_obj=THRESHOLD_PAIR)["events"][0]["limit"]
    # PF4 (PF4.17): with no unchanged condition the limit line counts the compared conditions (the
    # panel's two) instead of saying that every condition moved.
    assert (limit["label"], limit["mde"], limit["where"]) == (None, None, None), limit
    assert str(len(cells)) in NUMBER_RE.findall(limit["line"]) and limit["line"] != LIMIT_LINE_NONE, limit


def test_ls11_the_limit_never_attaches_to_a_worse_row() -> None:
    cells = [synthetic_cell(0, 1e-5, 1e-6, mde=0.9), synthetic_cell(9, 0.9, 0.9, delta=0.0, verdict="unchanged", mde=0.6)]
    # PF4 (PF4.5): the recorded threshold, 0.50 on the hand-built pair, which 0.6 is above.
    entry = summary_of([synthetic_panel(cells, 0.6)], pair_obj=THRESHOLD_PAIR)["events"][0]
    assert entry["limit"]["label"] == "too small to tell"
    assert entry["worse"] and all(row["confidence"] == "very sure" for row in entry["worse"])
    for row in entry["worse"]:
        assert "too small" not in row["line"].lower(), row
        assert not set(row) & {"label", "mde", "limit"}, row


def recorded_threshold(structure: Mapping[str, Any]) -> float:
    """PF4 (PF4.5, PF4.17): the threshold the Summary's limit is read against, computed here from
    the payload's two arms: the runs' recorded ``max_mde_accepted``, the smaller of the two, 0.20
    when neither run recorded one (front-door spec section 8.4)."""
    recorded = [arm["environment"].get("max_mde_accepted") for arm in (structure["pair"]["a"], structure["pair"]["b"])]
    values = [float(v) for v in recorded if v is not None]
    return min(values) if values else 0.20


def test_ls11_the_panels_mde_unchanged_is_the_honesty_number_character_for_character_on_every_fixture(all_pairs: list[Pair]) -> None:
    seen = set()
    for p in all_pairs:
        threshold = recorded_threshold(p.structure)
        for panel, entry in zip(p.structure["panels"], p.structure["summary"]["events"], strict=True):
            block = panel["mde_unchanged"]
            first = str(panel["honesty"]).splitlines()[0]
            if block["value"] is None and panel["n_unchanged"] > 0:
                # PF4 re-freeze (PF4.27): an unchanged condition can have no limit; the honesty line
                # and the limit line then name the least sensitive one and give the reason in words,
                # never a number for the limit.
                assert block["value"] is None and block["text"] is None, (p.name, block)
                limit = entry["limit"]
                notes = [note for note in NOTES if note in first]
                assert notes and not re.search(r"\d+pp", first) and HONESTY_RE.search(first) is None, (p.name, first)
                assert limit["mde"] is None and limit["where"] is not None and f"({limit['where']}, n" in first, (p.name, limit, first)
                assert notes[0] in limit["line"] and not re.search(r"\d+pp", limit["line"]), (p.name, limit)
                seen.add("none")
                continue
            if block["value"] is None:
                # PF4 (PF4.17): with no unchanged condition the honesty line and the limit line
                # count the compared conditions instead of saying that every cell moved.
                assert block == {"value": None, "text": None, "where": None}, (p.name, block)
                # The count is the panel's conditions or, under --fix, the event's whole comparison.
                compared = {str(panel["n_present"]), str(len(p.multi.by_event[panel["event"]].cells))}
                assert first != HONESTY_NONE and HONESTY_RE.search(first) is None and compared & set(NUMBER_RE.findall(first)), (p.name, first)
                limit = entry["limit"]
                assert (limit["label"], limit["mde"], limit["where"]) == (None, None, None), (p.name, limit)
                assert limit["line"] != LIMIT_LINE_NONE and compared & set(NUMBER_RE.findall(limit["line"])), (p.name, limit)
                seen.add("nan")
                continue
            m = HONESTY_RE.search(first)
            assert m is not None and block["text"] == m.group(1) == _fmt(block["value"], "pp0"), (p.name, first, block)
            assert 0.0 <= block["value"] <= 1.0
            assert f"({block['where']}, n=" in first, (p.name, first, block["where"])
            cell = next(c for c in panel["cells"] if c["coords"] == block["where"])
            assert cell["verdict"] == "unchanged"
            # PF4 (PF4.5, PF4.17): labelled above the runs' recorded threshold, not at 0.50.
            labelled = block["value"] > threshold
            fields = dict(where=block["where"], n_a=cell["n_a"], n_b=cell["n_b"], mde=block["text"])
            assert entry["limit"] == {"label": "too small to tell" if labelled else None, "mde": block["text"], "where": block["where"], "line": (LIMIT_LINE_LABELLED if labelled else LIMIT_LINE).format(**fields)}, (p.name, entry["limit"])
            seen.add("labelled" if labelled else "bare")
    # PF4 re-freeze (PF4.27): the fixtures now reach the no-limit case too.
    assert seen == {"nan", "labelled", "bare", "none"}, seen


def test_ls11_no_module_parses_the_honesty_prose_for_the_number() -> None:
    """Sole catch for a build that keeps the dashboard's text pattern."""
    pattern = re.compile(r"honesty[^\n]*\.(split|find|index|search|match|findall)\(|re\.\w+\([^\n]*honesty")
    for path in SRC.rglob("*.py"):  # PF5 (spec section 17): the core is a package now, so the scan reads src/ recursively.
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert not pattern.search(line), (path.name, i, line.strip())


# ---------- LS12: the plain register never decides ----------


def test_ls12_no_deciding_word_no_forbidden_vocabulary_and_no_question_in_the_summary(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        texts = [*summary_sentences(p.structure), *walk_strings(p.structure["summary"]), region_text(p.page, "Summary")]
        for text in texts:
            low = masked(text, p.structure)
            # PF4 re-freeze (PF4.35): the Summary shows the comparison's word, so it carries the
            # verdict block's ``verdict rule`` line, which says the verdict counts changes at the
            # family-wise level; those two phrases are the one place the word is said.
            low = low.replace("verdict rule", " ").replace("the verdict counts changes", " ")
            for word in DECIDING_WORDS:
                assert word not in low, (p.name, word, text[:120])
            for phrase in FORBIDDEN_VOCABULARY:
                assert phrase not in low, (p.name, phrase, text[:120])
            assert "?" not in text, (p.name, text[:120])


def test_ls12_the_vocabulary_pair_is_green_under_the_mask_and_red_without_it(every_pair: list[Pair]) -> None:
    p = by_name(every_pair)["vocab"]
    rows = [row for entry in p.structure["summary"]["events"] for row in entry["worse"]]
    assert len(rows) == 2, rows
    unmasked = " ".join(row["line"] for row in rows).lower()
    assert all(v in unmasked for v in VOCABULARY_VALUES), unmasked
    assert not any(v in masked(" ".join(row["line"] for row in rows), p.structure) for v in VOCABULARY_VALUES)


# ---------- LS13, LS14: complementary outcomes ----------


def test_ls13_the_two_event_lattice_pair_is_reported_once_and_never_as_a_trade(lattice_two: Pair) -> None:
    # the reference: the 72 conditions, and the 22 the unpaired test flags in each event over the
    # one BH family of both events, tripped lower where held is higher
    counts = lattice_directions((lattice.EVENT, lattice.OTHER))
    assert counts == {lattice.EVENT: (22, 0), lattice.OTHER: (0, 22)} and lattice.CELLS == 72, counts
    assert LATTICE_COMPLEMENT_LINE == COMPLEMENT_LINE.format(
        e1=lattice.EVENT, e2=lattice.OTHER, n=lattice.CELLS, k=counts[lattice.EVENT][0], worse=lattice.OTHER, safer=lattice.EVENT
    )
    assert lattice_two.multi.complementary_events() == (lattice.EVENT, lattice.OTHER)
    assert lattice_two.multi.trade_line() == LATTICE_COMPLEMENT_LINE
    assert lattice_two.structure["trade_line"] == LATTICE_COMPLEMENT_LINE
    assert lattice_two.structure["summary"]["complement"] == {"events": [lattice.EVENT, lattice.OTHER], "line": LATTICE_COMPLEMENT_LINE}
    assert lattice_two.structure["summary"]["complement"]["line"] == lattice_two.structure["trade_line"]
    # Ruling 6 (2026-09-22): the sentence has one source. ``plain.py`` carries ``trade_line`` and
    # composes no complement sentence of its own.
    assert "complements here" not in PLAIN_SOURCE.read_text(encoding="utf-8")
    assert "trade_line" in inspect.signature(plain().build_summary).parameters
    lines = summary_lines(lattice_two.page)
    # PF4 re-freeze (PF4.34, PF4.35): the Summary opens with the verdict line; the complement sentence
    # follows it.
    assert lines[0] == lattice_two.structure["summary"]["verdict_line"] and lines[1] == LATTICE_COMPLEMENT_LINE, lines[:2]
    assert [e["event"] for e in lattice_two.structure["summary"]["events"]] == [lattice.OTHER, lattice.EVENT]
    # The order is the comparison's own, worst first: by the count of rises, then of falls, then the
    # name. Under Fisher it is held (22 rises) first, which is also the alphabetical order, so the
    # order is also read on the same pair under log-rank with the events named held first: there
    # tripped rises in 12 conditions and held in none, so worst first is tripped, held, which is
    # neither the order the events were named in nor the order of their names.
    named = (lattice.OTHER, lattice.EVENT)
    timed = pair("lattice-two-events-logrank", LATTICE_ROOT, LATTICE_A, LATTICE_B, named, lattice.Y, lattice.X, method="logrank_bh")
    expected = lattice_worst_first(named)
    assert expected == [lattice.EVENT, lattice.OTHER] != sorted(named) and expected != list(named), expected
    assert [e["event"] for e in timed.structure["summary"]["events"]] == [panel["event"] for panel in timed.structure["panels"]] == expected
    assert str(timed.structure["headline"]).startswith(f"{lattice.EVENT}: "), timed.structure["headline"]
    for entry, panel in zip(lattice_two.structure["summary"]["events"], lattice_two.structure["panels"], strict=True):
        # PF4 (PF4.20): neither event declares a kind, so the counts are the rises and falls.
        assert str(panel["n_higher"]) in entry["line"] and str(panel["n_lower"]) in entry["line"]
    assert LATTICE_COMPLEMENT_LINE in region_text(lattice_two.page, "Result")
    for path in SRC.rglob("*.py"):  # PF5 (spec section 17): the core is a package now, so the scan reads src/ recursively.
        assert RETIRED_TRADE_TAIL not in path.read_text(encoding="utf-8"), path.name


def test_ls13_every_other_fixture_is_not_complementary_and_its_trade_line_is_what_it_was(every_pair: list[Pair], titled: Pair, partial: Pair) -> None:
    for p in [*every_pair[:1], *every_pair[2:], titled, partial]:
        assert p.multi.complementary_events() is None, p.name
        assert p.multi.trade_line() is None and p.structure["trade_line"] is None, p.name
        assert p.structure["summary"]["complement"] is None, p.name


def test_ls13_the_non_complementary_trade_line_counts_the_co_occurrence_and_names_no_cause(traded: Pair) -> None:
    m = traded.multi
    assert m.complementary_events() is None and len(m.trades) == 2
    line = TRADE_LINE.format(safer="fail", n=2, cells="cells", worse="crash")
    assert m.trade_line() == line, m.trade_line()
    assert traded.structure["trade_line"] == line and traded.structure["summary"]["complement"] is None, traded.structure["trade_line"]
    assert RETIRED_TRADE_TAIL not in line and "patch" not in line


def test_ls14_the_complement_test_is_exact_integer_and_conservative(lattice_two: Pair) -> None:
    src = source_of(DIFF_SOURCE, "complementary_events")
    tree = ast.parse(src)
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert names & {"n_a", "n_b", "events_a", "events_b", "config_hash"} == {"n_a", "n_b", "events_a", "events_b", "config_hash"}, names
    assert not names & {"rate_a", "rate_b", "delta", "isclose", "allclose"}, names
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree)), src
    assert not any(isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) in ("isclose", "allclose", "abs", "float") for n in ast.walk(tree)), src
    store = Store(LATTICE_ROOT)
    fa, fb = store.read(LATTICE_A, meta=False), store.read(LATTICE_B, meta=False)
    ma, mb = store.manifest(LATTICE_A), store.manifest(LATTICE_B)
    censored = fa.copy()
    censored.loc[censored.index[0], "outcome"] = "neither"
    assert quiet_multi_diff(censored, fb, ma, mb, events=(lattice.EVENT, lattice.OTHER)).complementary_events() is None
    assert quiet_multi_diff(fa, fb, ma, mb, events=(lattice.EVENT, lattice.OTHER, "neither")).complementary_events() is None
    m = lattice_two.multi
    e2 = m.events[1]
    fewer = replace(m.by_event[e2], cells=m.by_event[e2].cells.iloc[1:].reset_index(drop=True))
    assert replace(m, by_event={**m.by_event, e2: fewer}).complementary_events() is None
    assert m.complementary_events() == (lattice.EVENT, lattice.OTHER)


# ---------- LS15: a partial run says so first ----------


def test_ls15_a_partial_arm_is_named_first_in_the_summary_from_either_side(partial: Pair, partial_b: Pair, lattice_one: Pair) -> None:
    for p, role in ((partial, "baseline"), (partial_b, "candidate")):
        arm = p.structure["pair"]["a" if role == "baseline" else "b"]
        assert arm["status"] == "partial" and arm["run_id"] == PARTIAL_A
        line = PARTIAL_LINE.format(run_id=PARTIAL_A, role=role)
        assert p.structure["summary"]["partial"] == {"runs": [PARTIAL_A], "line": line}, p.structure["summary"]["partial"]
        # PF4 re-freeze (PF4.34): the Summary opens with the comparison's verdict line; the partial
        # line is the first after it.
        assert summary_lines(p.page)[0] == p.structure["summary"]["verdict_line"], summary_lines(p.page)[0]
        assert summary_lines(p.page)[1] == line, summary_lines(p.page)[1]
        header, rows = table_of(region_lines(p.page, "Run pair")[0])
        status = next(r for r in rows if r[0] == "status")
        assert status == ["status", "partial", "complete"] if role == "baseline" else ["status", "complete", "partial"]
    assert lattice_one.structure["summary"]["partial"] is None
    assert not any("recorded status" in line for line in summary_lines(lattice_one.page))
    header, rows = table_of(region_lines(lattice_one.page, "Run pair")[0])
    assert next(r for r in rows if r[0] == "status") == ["status", "complete", "complete"]


# ---------- LS21: the plain line beside "unpaired" (the ruling of 2026-09-21) ----------


def result_lines(page: str) -> list[str]:
    return [text for line in region_lines(page, "Result") if line.startswith("<p>") for text in p_lines(line)]


def test_ls21_the_unpaired_word_gets_its_plain_line_beside_it_and_only_when_the_seeds_are_shared(all_pairs: list[Pair]) -> None:
    seen = set()
    for p in all_pairs:
        unpaired = bool(p.structure["diff"]["unpaired_analysis"])
        pairing = p.structure["summary"]["pairing"]
        lines = result_lines(p.page)
        headline_lines = str(p.structure["headline"]).splitlines()
        assert lines[: len(headline_lines)] == headline_lines, (p.name, lines[:3])
        if unpaired:
            assert "unpaired" in headline_lines[-1] and p.structure["diff"]["seed_identity_match"] is True, p.name
            assert pairing == {"line": PAIRING_LINE}, (p.name, pairing)
            assert lines[len(headline_lines)] == PAIRING_LINE, (p.name, lines[: len(headline_lines) + 1])
            seen.add("unpaired")
        else:
            assert pairing == {"line": None}, (p.name, pairing)
            seen.add("paired")
        assert html_mod.unescape(p.page).count(PAIRING_LINE) == (1 if unpaired else 0), p.name
        assert PAIRING_LINE not in summary_lines(p.page)
    assert seen == {"unpaired", "paired"}, seen


def test_ls21_the_word_and_the_warning_do_not_move() -> None:
    """D16 as ruled: the word stays and the warning stays; only the line beside the word is new."""
    assert "unpaired" in source_of(DIFF_SOURCE, "headline")
    src = DIFF_SOURCE.read_text(encoding="utf-8")
    assert "class UnpairedAnalysis" in src
    assert PAIRING_LINE not in src and PAIRING_LINE not in VIEWER_SOURCE.read_text(encoding="utf-8")
    assert PAIRING_LINE in PLAIN_SOURCE.read_text(encoding="utf-8")


# ---------- LS16: no internal reference on the page ----------


def test_ls16_no_board_id_on_the_page_while_blocked_by_stays_in_the_payload(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        text = html_mod.unescape(p.page)
        for token in BOARD_TOKENS:
            assert token not in text, (p.name, token)
        assert tuple(e["blocked_by"] for e in p.structure["unverified"]) == UNVERIFIED_BLOCKED_BY, p.name
        assert [e["id"] for e in p.structure["unverified"]] == ["outcome_labels", "status_basis", "created_at_meaning", "seed_identity_basis"]
        lines = region_lines(p.page, "Not verified")
        assert any(html_mod.escape(NEW_TAILS[0]) in line for line in lines) and any(html_mod.escape(NEW_TAILS[1]) in line for line in lines), lines
    assert tuple(blocked for _, _, blocked in viewer()._UNVERIFIED) == UNVERIFIED_BLOCKED_BY


# ---------- LS17: the command line says what it means ----------


def help_entries(text: str) -> dict[str, str]:
    """Each option's help, argparse's wrapping collapsed, keyed by its first long flag."""
    entries: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^  (-\S.*?)(?:\s{2,}(.*))?$", line)
        if m:
            current = m.group(1).split()[0].split(",")[0]
            entries[current] = (m.group(2) or "").strip()
        elif current and line.startswith("    ") and line.strip():
            entries[current] = (entries[current] + " " + line.strip()).strip()
    return entries


def test_ls17_serve_help_marks_event_and_x_required_and_gives_method_theme_and_title_help() -> None:
    code, out, err = run_cli(["serve", "--help"])
    assert code == 0, err
    entries = help_entries(out)
    for flag in ("--event", "--x"):
        assert "required:" in entries[flag], (flag, entries.get(flag))
    for flag in ("--method", "--theme", "--title"):
        assert entries.get(flag), (flag, entries.get(flag))


BAD_ARGV = (
    ("--x", "nope"),
    ("--x", lattice.X, "--y", "nope"),
    ("--x", lattice.X),
    ("--x", lattice.X, "--y", lattice.Y, "--fix", "nope=1"),
    ("--x", lattice.X, "--y", lattice.Y, "--fix", f"{lattice.X}=0.1"),
    ("--x", lattice.X, "--y", lattice.X),
    ("--x", lattice.X, "--y", lattice.Y, "--fix", "broken"),
)


def test_ls17_no_refusal_reachable_from_serve_names_a_python_parameter(lattice_one: Pair) -> None:
    for tail in BAD_ARGV:
        code, out, err, calls = run_serve(["--store", str(LATTICE_ROOT), "serve", LATTICE_A, LATTICE_B, "--event", lattice.EVENT, *tail, "--json"])
        # A refusal exits 1 (front-door spec section 5.2).
        assert code == 1 and calls == [] and out == "", (tail, code, err[-300:])
        low = err.lower()
        for spelling in ("x_axis", "y_axis", "fixed=", "fixed ", "spec."):
            assert spelling not in low, (tail, err)
        if "pin" in low or "not a config key" in low or "unknown config key" in low:
            assert "--x" in err or "--y" in err or "--fix" in err, (tail, err)
    code, out, err, calls = run_serve(["--store", str(LATTICE_ROOT), "serve", LATTICE_A, LATTICE_B, "--event", lattice.EVENT, "--json"])
    # A refusal exits 1 (front-door spec section 5.2).
    assert code == 1 and "--x AXIS" in err, err


# ---------- LS18: the docs ----------


def test_ls18_the_readme_has_a_serve_section_and_the_docs_page_names_the_fourteen_headings_in_order() -> None:
    # PF7 (sections 6.2 and 6.3): the README is the release's, its links absolute and its sections
    # section 6.2's, so the serve section, its command and "Pre-release" move to serve's own page,
    # which the README's Commands line links; the README still links this page.
    readme = README.read_text(encoding="utf-8")
    serve_page = (REPO / "docs" / "commands" / "serve.md").read_text(encoding="utf-8")
    heading = next((line for line in serve_page.splitlines() if line.startswith("#") and "serve" in line.lower()), None)
    assert heading is not None, "no serve heading on its page"
    assert re.search(r"^\s*(?:\$ )?poisson-prove\b.*\bserve\b.*--event\b.*--x\b", serve_page, re.M), "no runnable serve command on its page"
    assert re.search(r"\]\(https://github\.com/poisson-labs/prove/blob/main/docs/reading-a-serve-page\.md\)", readme), "the README does not link the page"
    assert "Pre-release" not in readme
    assert SERVE_DOC.exists()
    doc = SERVE_DOC.read_text(encoding="utf-8")
    positions = [next((m.start() for m in re.finditer(rf"^#+ {re.escape(h)}\s*$", doc, re.M)), -1) for h in H2_SEQUENCE]
    assert all(pos >= 0 for pos in positions), [h for h, pos in zip(H2_SEQUENCE, positions, strict=True) if pos < 0]
    assert positions == sorted(positions), list(zip(H2_SEQUENCE, positions, strict=True))


# ---------- LS19: the expert register is complete and reachable ----------


#: PF4 (PF4.20): a judgement word; no fixture here declares an event kind.
JUDGEMENT_RE = re.compile(r"\b(safer|worse)\b", re.IGNORECASE)
#: PF4 (PF4.20): a reader's direction word put back as the bare tree wrote the verdict (no fixture
#: declares a kind, so the library's worse is a rise and its safer a fall).
BARE_VERDICT = {"higher": "worse", "lower": "safer", "unchanged": "unchanged"}
#: PF4 (PF4.13, PF4.14, PF4.15, PF4.3): the cell fields PF4 adds right after ``verdict``.
PF4_CELL_KEYS = ("direction", "direction_note", "pairs", "mde_note", "share_a", "share_b", "share_a_differs", "share_b_differs")
CELL_INDEX_RE = re.compile(r'(<script type="application/json" id="proofload-cells">)(.*)(</script>)')
#: PF4 (PF4.12, PF4.15, PF4.18): the regions whose numbers PF4 moves, not only their words: on the
#: study pairs (now the lattice pairs) the fault lines' group p and q (Westfall-Young on one scale),
#: and on those pairs and the traded pair (whose t0 fail arm fails every run) the detection limits of the conditions at a
#: 100% baseline with the leaf rows, cell index and worst-cells rows that carry them. Their digests are no longer asserted; assert_region_facts asserts what they guarded.
#: PF4 re-freeze (PF4.22 to PF4.27, PF4.34 to PF4.47): every pair's detection limits move (the exact
#: power at the lone-change level, both directions, null with a reason), its group limits move
#: (PF4.45), its intervals are always there (PF4.42) and every cell gains the new keys, so on every
#: pair the Honesty, Fault lines, Cells, Cell and Worst cells regions are checked by their facts.
PF4_MOVED_REGIONS: dict[str, tuple[str, ...]] = {
    name: ("Honesty", "Fault lines", "Cells", "Cell", "Worst cells") for name in (*REGION_SHA256, *LATTICE_PAIRS)
}


def script_json(payload: Any) -> str:
    """The viewer's ``_script_json``, restated: ``json.dumps`` with the three markup characters
    escaped."""
    dump = json.dumps(payload, sort_keys=False, allow_nan=False)
    return dump.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def as_before_pf4(text: str, heading: str, p: Pair) -> str:
    """PF4 (PF4.3, PF4.13, PF4.14, PF4.15, PF4.17, PF4.20): the words and fields PF4 changes in a
    region the LS pass left untouched, first asserted in PF4's form and then put back as the bare
    tree wrote them, so the frozen digest still guards every other byte. No fixture declares a kind,
    so the headline counts falls as lower and rises as higher, the honesty claim names the rises,
    the verdict column and the cell index carry the direction, and a panel with no unchanged
    condition counts its compared conditions."""
    if heading == "Result":
        lines = text.split("\n")
        pattern = r"(\S+): (\d+) lower, (\d+) higher"
        assert len(re.findall(pattern, lines[0])) == len(p.events) and not JUDGEMENT_RE.search(lines[0]), lines[0]
        lines[0] = re.sub(pattern, r"\1: \2 safer, \3 worse", lines[0])
        return "\n".join(lines)
    if heading == "Honesty":
        lines = text.split("\n")
        panels = iter(p.structure["panels"])
        for i in range(1, len(lines)):
            if not lines[i - 1].startswith("<h3>"):
                continue
            panel = next(panels)
            first, sep, rest = lines[i][3:].partition("<br>")
            if "can only detect" in first:
                assert re.search(r"&quot;\d+ higher&quot; is an honest claim", first) and not re.search(r"&quot;\d+ worse&quot;", first), first
                first = re.sub(r"&quot;(\d+) higher&quot; is an honest claim", r"&quot;\1 worse&quot; is an honest claim", first)
            else:
                compared = {str(panel["n_present"]), str(len(p.multi.by_event[panel["event"]].cells))}
                assert first != HONESTY_NONE and compared & set(NUMBER_RE.findall(first)), first
                first = HONESTY_NONE
            lines[i] = "<p>" + first + sep + rest
        return "\n".join(lines)
    if heading == "Worst cells":
        assert "<td>worse</td>" not in text and "<td>safer</td>" not in text, text[:200]
        return text.replace("<td>higher</td>", "<td>worse</td>").replace("<td>lower</td>", "<td>safer</td>")
    if heading == "Cell":
        out = []
        for line in text.split("\n"):
            if line.startswith('<div id="pl-cell">'):
                for word, bare in BARE_VERDICT.items():
                    line = line.replace(f"<td>verdict</td><td>{word}</td>", f"<td>verdict</td><td>{bare}</td>")
            m = CELL_INDEX_RE.fullmatch(line)
            if m:
                index = json.loads(m.group(2))
                for entry in index.values():
                    keys = list(entry)
                    at = keys.index("verdict") + 1
                    assert tuple(keys[at : at + len(PF4_CELL_KEYS)]) == PF4_CELL_KEYS and entry["direction"] == entry["verdict"], keys
                    for key in PF4_CELL_KEYS:
                        del entry[key]
                    entry["verdict"] = BARE_VERDICT[entry["verdict"]]
                line = m.group(1) + script_json(index) + m.group(3)
            out.append(line)
        return "\n".join(out)
    return text


def same_number(got: Any, want: Any) -> bool:
    """A JSON number against the library's float: equal, or null where the library holds NaN."""
    want = float(want)
    return got is None if want != want else got == want


def assert_region_facts(p: Pair, heading: str) -> None:
    """PF4 (PF4.12, PF4.15, PF4.18, PF4.20): what a moved region's digest guarded, read against the
    payload and the library's frame on the same pair."""
    page = page_as_0_0_1_wrote_it(p.page)
    lines = region_lines(page, heading)
    text = "\n".join(lines)
    assert not JUDGEMENT_RE.search(unescape(text)) and "nan" not in unescape(text).lower().split(), (p.name, heading)
    tree = p.structure["tree"]
    if heading == "Fault lines":
        groups = tree["fault_lines"]["groups"]
        [table] = [table_of(line) for line in lines if line.startswith("<table>")]
        header, rows = table
        assert len(rows) == len(groups), (p.name, len(rows))
        # PF4 re-freeze (PF4.45): every pair's group limits move, so each row is read column by
        # column against its group: the paired test adds the discordant pairs, and an untested
        # family (the root did not reject) prints no p, q or verdict.
        columns = {
            "cells": lambda g: str(g["n_cells"]), "informative": lambda g: str(g["n_informative_cells"]),
            "unchanged by every exchange": lambda g: str(g["n_uninformative_cells"]),
            "units (a/b)": lambda g: f"{g['n_a']}/{g['n_b']}", "group MDE (pp)": lambda g: f"{g['text']['mde']}pp",
            "discordant pairs": lambda g: str(g["n_discordant"]), "p": lambda g: g["text"]["p_group"],
            "q": lambda g: g["text"]["q_group"], "verdict": lambda g: "rejected" if g["rejects"] else "not rejected",
        }
        assert header[0] == tree["grouping"]["key"] and set(header[1:]) <= set(columns), (p.name, header)
        assert ("p" in header) == bool(tree["fault_lines"]["tested"]), (p.name, header)
        for row, g in zip(rows, groups, strict=True):
            expected = [g["label"], *(columns[name](g) for name in header[1:])]
            assert row == expected, (p.name, row, expected)
        if p.events == (lattice.EVENT,):
            # PF4 re-freeze (PF4.45): the group limits use each cell's own baseline and the
            # unconditional power, so the lattice's first declared axis, gain, does not resolve
            # (refused as underpowered) and the tree groups by the next, load: 6 groups, one per
            # load value. What is pinned is the walk and the rejected set as the page prints it.
            grouping = tree["grouping"]
            first, second = list(p.structure["pair"]["a"]["axis_types"])
            assert (first, second) == (lattice.X, lattice.Y), (first, second)
            assert [(r["key"], r["reason"]) for r in grouping["refused"]] == [(first, "underpowered")] == [("gain", "underpowered")], (p.name, grouping["refused"])
            assert grouping["key"] == second == "load" and len(groups) == len(lattice.LOAD) == 6, (p.name, grouping["key"], len(groups))
            assert tree["fault_lines"]["rejected_groups"] == [g["label"] for g in groups if g["rejects"]], p.name
            assert tree["fault_lines"]["n_rejected_groups"] == sum(g["rejects"] for g in groups), p.name
        return
    if heading == "Honesty":
        # PF4 re-freeze (PF4.22, PF4.27, PF4.42): each panel's honesty block is the payload's
        # honesty text, and the intervals line is at 1 - q max(R, 1) / M, with R the flagged rows and
        # M the rows of the comparison.
        # PF4 re-freeze (PF4.27): no text prints a number for a null limit, so no "nanpp".
        assert not re.search(r"\bnan(pp)?\b", unescape(text).lower()), (p.name, heading)
        panels = p.structure["panels"]
        heads = [i for i, line in enumerate(lines) if line.startswith("<h3>")]
        assert [lines[i] for i in heads] == [f"<h3>{html_mod.escape(panel['event'])}</h3>" for panel in panels], p.name
        for i, panel in zip(heads, panels, strict=True):
            assert lines[i + 1] == "<p>" + html_mod.escape(panel["honesty"]).replace("\n", "<br>") + "</p>", (p.name, lines[i + 1][:120])
        rows = sum(len(p.multi.by_event[e].cells) for e in p.events)
        flagged = sum(int((p.multi.by_event[e].cells["verdict"] != "unchanged").sum()) for e in p.events)
        level = 1 - float(p.structure["diff"]["q"]) * max(flagged, 1) / rows
        [intervals] = [line for line in lines if line.startswith("<p>intervals: ")]
        assert intervals.startswith(f"<p>intervals: {100 * level:.4f}% "), (p.name, intervals[:90], level)
        assert any(line.startswith("<p>depth ") for line in lines), p.name
        return
    if heading == "Cells":
        leaves = tree["leaves"]
        paragraphs = [part for line in lines if line.startswith("<p>") for part in p_lines(line)]
        tables = [table_of(line) for line in lines if line.startswith("<table>")]
        if not leaves["tested"]:
            # PF4 re-freeze (PF4.22 to PF4.27): the region is read by its facts on every pair now,
            # some of whose roots do not reject; then it is one sentence and no table.
            assert len(paragraphs) == 1 and paragraphs[0].startswith("not tested") and not tables, (p.name, paragraphs)
            return
        assert len(paragraphs) == 2 + len(leaves["families"]), (p.name, paragraphs[2 + len(leaves["families"]) :])
        rejecting = [f for f in leaves["families"] if f["n_rejected"] > 0]
        assert len(tables) == len(rejecting), p.name
        for line, family in zip(paragraphs[2:], leaves["families"], strict=True):
            assert line.startswith(f"{family['key']}={family['label']}: {family['n_tests']} tests, {family['n_rejected']} rejected"), (p.name, line)
            # PF4 re-freeze (PF4.27): a family whose limits are all null prints no number for them.
            for which in ("median", "max"):
                if family[f"mde_{which}"] is None:
                    assert not re.search(rf"{which} \d", line), (p.name, line)
                else:
                    assert f"{which} {family['text'][f'mde_{which}']}pp" in line, (p.name, line)
        for (_header, rows), family in zip(tables, rejecting, strict=True):
            leaves_here = [c for c in family["cells"] if c["rejects"]]
            assert len(rows) == len(leaves_here), (p.name, family["label"])
            for row, leaf in zip(rows, leaves_here, strict=True):
                assert row[1:4] == [leaf["event"], leaf["text"]["delta"], leaf["text"]["q_within"]], (p.name, row)
                if leaf["mde"] is None:
                    # PF4 re-freeze (PF4.27): a null limit is printed as its reason in words.
                    assert any(note in row[4] for note in NOTES) and not NUMBER_RE.search(row[4]), (p.name, row)
                else:
                    assert row[4] == f"{leaf['text']['mde']}pp", (p.name, row)
        return
    records = {(e, str(r["config_hash"])): r for e in p.events for r in p.multi.by_event[e].cells.to_dict(orient="records")}
    if heading == "Cell":
        [line] = [line for line in lines if CELL_INDEX_RE.fullmatch(line)]
        index = json.loads(CELL_INDEX_RE.fullmatch(line).group(2))  # type: ignore[union-attr]
        # PF4 re-freeze: read on every pair now, so under --fix the index holds the slice the page
        # shows (the panels' cells), each a row of the comparison.
        shown = {(panel["event"], str(c["config_hash"])) for panel in p.structure["panels"] for c in panel["cells"]}
        assert {(key.rsplit(" ", 1)[0], entry["config_hash"]) for key, entry in index.items()} == shown <= set(records), p.name
        for key, entry in index.items():
            record = records[(key.rsplit(" ", 1)[0], entry["config_hash"])]
            for field in ("n_a", "n_b", "events_a", "events_b"):
                assert entry[field] == int(record[field]), (p.name, key, field)
            for field in ("rate_a", "rate_b", "delta", "p", "q", "mde"):
                assert same_number(entry[field], record[field]), (p.name, key, field)
            # PF4 re-freeze (PF4.20, kindless events): the library's verdict is the direction word too.
            assert entry["verdict"] == entry["direction"] == str(record["verdict"]), (p.name, key)
            if entry["mde"] is None:
                # PF4 (PF4.15): no detection limit; the entry carries the note that says why. Its
                # ``text`` keeps M7's formatting of the raw value (M13 V16), so the note is what a
                # reader is shown, not the text entry.
                assert isinstance(entry["mde_note"], str) and entry["mde_note"], (p.name, key)
            else:
                assert entry["text"]["mde"] == _fmt(entry["mde"], "pp0"), (p.name, key, entry["text"])
        return
    if heading == "Worst cells":
        tables = [table_of(line) for line in lines if line.startswith("<table>")]
        assert len(tables) == len(p.structure["panels"]), p.name
        for (header, rows), panel in zip(tables, p.structure["panels"], strict=True):
            assert (header, rows) == (panel["worst_header"], panel["worst_rows"]), (p.name, panel["event"])
            verdict, mde = header.index("verdict"), header.index("MDE")
            for row, h in zip(rows, panel["worst_hashes"], strict=True):
                record = records[(panel["event"], h)]
                # PF4 re-freeze (PF4.20, kindless events): the library's verdict is the direction word too.
                assert row[verdict] == str(record["verdict"]), (p.name, row)
                if isinstance(record["mde_note"], str):
                    assert not re.search(r"\d+pp", row[mde]), (p.name, row)
                else:
                    assert row[mde] == f"{_fmt(record['mde'], 'pp0')}pp", (p.name, row)
        return
    raise AssertionError((p.name, heading))


def test_ls19_every_dispatch_heading_is_still_on_the_page_and_the_untouched_regions_keep_their_bytes(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        assert set(h2_sequence(p.page)) == DISPATCH_H2, p.name
        for heading in UNTOUCHED_REGIONS:
            # PF4: a region whose numbers PF4 moves is checked by its facts; every other region
            # keeps its frozen digest once PF4's words are put back (as_before_pf4).
            if heading in PF4_MOVED_REGIONS.get(p.name, ()):
                assert_region_facts(p, heading)
                continue
            if p.name in LATTICE_PAIRS:
                assert_lattice_region(p, heading)
                continue
            text = as_before_pf4(normalised_region(page_as_0_0_1_wrote_it(p.page), heading), heading, p)
            assert sha(text) == REGION_SHA256[p.name][heading], (p.name, heading)


def test_ls19_the_summary_introduces_no_number_the_statistics_view_does_not_carry(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        lines = p.page.splitlines()
        marks = h2_lines(p.page)
        rest = html_mod.unescape("\n".join(lines[: marks[0][0]] + lines[marks[1][0] :]))
        # PF4 re-freeze (PF4.44): the verdict block's detail lines carry facts only the verdict block
        # shows (the fragility among them), so this clause reads the plain register's sentences.
        facts = set(verdict_block_lines(p.structure))
        for sentence in (s for s in summary_sentences(p.structure) if s not in facts):
            for token in NUMBER_RE.findall(sentence):
                assert token in rest or token in THRESHOLD_SPELLINGS, (p.name, token, sentence[:120])


# ---------- LS20: serve --json is the one source ----------


def test_ls20_every_sentence_in_the_summary_region_is_a_line_of_summary_and_the_reverse(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        assert summary_lines(p.page) == summary_sentences(p.structure), p.name


def test_ls20_the_page_renders_from_a_round_tripped_structure_with_no_report_diff_or_tree_in_scope(lattice_two: Pair) -> None:
    text = json.dumps(lattice_two.structure, allow_nan=False)
    again = viewer().render_html(strict_loads(text))
    assert again == lattice_two.page
    render = source_of(VIEWER_SOURCE, "render_html")
    whole = VIEWER_SOURCE.read_text(encoding="utf-8")
    for fragment in ("conditions got worse", "How sure", "Too small to tell", "recorded status", "complements here", "Every number above", "separate samples"):
        assert fragment not in whole, fragment
    assert "summary" in render
