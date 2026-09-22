"""LS -- the local serve pass: the oracle for LS1-LS20 and the ruled LS21.

**Frozen 2026-09-22.** Taylor approved the invariant-to-test table, the mutant-to-test table and the
conventions below (seven yes); the freeze is this docstring and nothing else. The mutation pass was
re-run control-first after the freeze; its table is the handoff's. Session B builds against this
file and does not edit it.

Written from "Prove -- Spec Local Serve Pass" section 4 against ``f7af030`` (2026-09-22), on the
retrofit commit that moves the schema pins to ``proofload.viewpair/6``, the top-level key tuple to
fourteen with ``summary`` eighth, ``PANEL_KEYS`` to fifteen, ``HOLE_KEYS`` to ten, the ``<h2>``
sequence to ``Summary`` first and ``Run pair`` thirteenth, and the Go1 two-event trade line to the
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
``.work/serve-pass-1/step-zero/`` in the worktree, filed in the vault under
``log/prove-serve-pass-1/step-zero/``). The four reproductions hold: (3) on the Go1 page every one
of 400 present cells has its centre under a label ``<text>`` drawn after its rect, and no
``pointer-events:none`` selector ends in ``text``; (4) on the two-event Go1 figure exactly two
``<text>`` runs pass the 920 px box, both legend captions, at 1,176 and 1,198 px, and a 143-char
``--title`` runs to 1,139 px -- *and on every builder-made pair whose box is 200 to 440 px wide the
honesty lines, the panel headline, the stacked headline's second line and the legend swatch labels
pass it too* (see the LS2 convention below); (5) a three-hole partial pair prints ``none`` in the
``where`` column of both off-grid rows, each of which carries its whole ``config``; (6) all four
integer conditions hold on the two-event Go1 pair in all 400 cells and both arms, the deltas cancel
in every cell, and every other pair measured (Go1 ``fell`` alone, the multi-event pair, the golden
pilot and tau2-airline in the workspace store) fails condition 1 or 4. (7) ``max_mde_unchanged`` is
a fraction in [0, 1] on every pair and ``_fmt(value, "pp0")`` is character for character the number
the honesty line prints, on all thirteen panels that have one. (8) ``MULTI_JSON_SHA256``'s fixture
is ``events=("fell",)`` and ``to_json()`` has 25 keys, none named ``complementary_events``. (1) The
section 7.1 greps: ``TOP_LEVEL_KEYS`` has **six** copies (``test_s29_viewer.py``,
``test_m13_viewer.py``, ``test_p1_payload.py``, ``test_s21_errors.py``, ``test_a28_agreement.py``,
``test_cut_surfacing.py``), not the three section 0.2 counts; all six are retrofitted. (2)
``origin/main`` is ``a1caa17``, four commits past ``f7af030`` (the PR-1 merge); this packet stays
on ``f7af030`` as instructed and the line numbers in the spec were read there.

**Conventions this oracle fixes where the spec is silent or disagrees with itself. Session B builds
to these; each was put to Taylor and ruled on 2026-09-22 (seven yes).**

- **The Summary region is one ``<p>`` per sentence, one element per line, no table, no list, no
  attribute, no ``<details>``**, in this order: the partial line (if any), the complement line (if
  any), then per event in ``panels`` order the counts line, each ``worse`` row's line, the limit
  line, and last the pointer. Every ``<p>`` is one ``line`` value of ``summary`` through
  ``html.escape``, so LS20's two directions are one equality.
- **The event name is spelled bare** in the counts and row sentences: ``fell: 0 of 400 conditions
  ...``. The spec writes the field in backticks in section 3.4, which this oracle reads as the spec's
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
  ``(safer, worse)`` the pair ``trade_line()`` picks. On Go1 the two readings coincide.
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
  -- and, ruled 2026-09-22, the honesty lines, each identified by content through this oracle's
  restatement of ``_wrap`` and its budget. The spec's clause reads "every ``<text>``"; measured at
  step zero, that cannot hold on a box 200 px wide, whose legend swatch *rects* sit at a fixed 46 px
  pitch and already leave it; the swatch labels are the named exception.
- **A wrapped text is drawn as one ``<text>`` per line, the continuation lines carrying
  ``data-wrap="1"`` and the first line not**, so M7's oracle (retrofitted) can read a wrapped
  text back as one, and so a reader of the SVG can tell a wrapped line from a new text.
- **The tree refusal is left as it was.** Section 3.8 item 1 gives it "the same treatment for
  symmetry", but it carries no version literal to interpolate, and P-1's Y15 pins its text; LS8
  asserts it names no version, and the intervals refusal alone interpolates ``SCHEMA``.
- **LS3's rect clause is "byte-identical up to the top growth"**: ``x``, ``width``, ``height``,
  ``fill`` and the four ``data-`` attributes of every grid and glyph rect are the dispatch commit's,
  and ``y`` is the dispatch commit's plus exactly the growth of ``top`` (``18`` per extra title
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
  region's trade or complement ``<p>`` (D10 changes it on the two-event Go1 pair), and the ``Cell``
  region's holes JSON block (D12 adds ``where`` to every hole). Everything else in the eight regions
  is pinned byte for byte, on the bare tree, and must survive the build.
- **LS21, from the ruling of 2026-09-21 that lifted D16's hold on the word "unpaired":** the word
  and the Python warning stay exactly as they are, and one plain line is printed beside the word --
  in the ``Result`` block, the ``<p>`` right after the headline -- iff the payload's
  ``diff.unpaired_analysis`` is true (the runs share their seeds and the test ignores that). It rides
  the payload as ``summary.pairing.line`` (``None`` otherwise), third key of ``summary`` after
  ``complement``, and is the one ``line`` of ``summary`` that is read in ``Result`` rather than in
  the Summary region, so LS20's equality leaves it out. The wording is the Go1 pairing report's
  suggested sentence, verbatim. Not a spec invariant: the ruling came after the spec was written.

**Fixture limits, stated before anything is asserted on a fixture.** Every S29 pair is complete,
so LS15 rests on this oracle's own partial pair (three holes, ``part-a`` never marked complete,
both orders). No stored pair was taken at ``--q`` above 0.05, so the unlabelled row and the ``q``
boundaries are exercised on a hand-built panel (LS10) and only the labels the real payloads reach
are re-asserted on them. The two-event Go1 pair is the only complementary fixture; the
non-complementary trade line is reached through a builder-made pair (``trade-a``/``trade-b``)
whose one all-``fail``/all-``crash`` cell is a trade and whose ``ok`` rows break condition 4.
Go1's run ids are short, so the wrapped title needs ``--title``.

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

import proofload
from proofload import cli
from proofload import diff as diff_mod
from proofload.diff import multi_diff
from proofload.episode import Episode
from proofload.report import _fmt
from proofload.store import EpisodeRecord, RunManifest, Store

PACKAGE = Path(proofload.__file__).resolve().parent
REPO = PACKAGE.parents[1]
SRC = PACKAGE
VIEWER_SOURCE = PACKAGE / "viewer.py"
REPORT_SOURCE = PACKAGE / "report.py"
DIFF_SOURCE = PACKAGE / "diff.py"
PLAIN_SOURCE = PACKAGE / "plain.py"
README = REPO / "README.md"
SERVE_DOC = REPO / "docs" / "reading-a-serve-page.md"
GO1_ROOT = REPO / "tests" / "fixtures" / "go1"
GO1_A, GO1_B = "go1-v0", "go1-v1"

# ---------- spec sections 2, 3.2, 3.3, 3.5: the literals ----------

#: LS7, LS8. The schema, and the four ``render_html`` refuses by name.
SCHEMA = "proofload.viewpair/6"
RETIRED_SCHEMAS = tuple(f"proofload.viewpair/{n}" for n in (2, 3, 4, 5))
#: LS7. Fourteen top-level keys, ``summary`` eighth.
TOP_LEVEL_KEYS = (
    "schema", "pair", "diff", "holes", "view", "headline", "trade_line", "summary", "fence", "panels",
    "intervals", "tree", "unverified", "heatmap_svg",
)
#: LS7. Fifteen panel keys, ``mde_unchanged`` after ``honesty``; the cell keys unchanged; ten hole keys.
PANEL_KEYS = (
    "event", "caption", "honesty", "mde_unchanged", "n_safer", "n_worse", "n_unchanged", "n_absent",
    "n_present", "x_values", "y_values", "cells", "worst_header", "worst_rows", "worst_hashes",
)
MDE_UNCHANGED_KEYS = ("value", "text", "where")
CELL_KEYS = (
    "coords", "config_hash", "n_a", "n_b", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b",
    "events_a", "events_b", "rate_a", "rate_b", "delta", "stat", "p", "q", "mde", "verdict",
    "config", "config_text", "text",
)
HOLE_KEYS = (
    "coords", "where", "config_hash", "cause", "rows_a", "rows_b", "no_outcome_a", "no_outcome_b",
    "config", "config_text",
)
#: LS7. The ``summary`` object (section 3.3), its event entry, a ``worse`` row and the limit.
SUMMARY_KEYS = ("partial", "complement", "pairing", "events", "pointer")
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
#: oracle's LS16 convention adds).
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
LEGEND_TAIL = "corner notches = trade (safer in one event, worse in another)"
#: The honesty lines join the wrap set: D9 named four texts, step zero measured the honesty lines
#: past the box on every narrow pair, and Taylor ruled on 2026-09-22 that they wrap too (a fifth
#: text, at the caption's 12 px pitch).
WRAPPED_HONESTY = True

# ---------- section 3.4: the words, verbatim ----------

COUNTS_LINE = "{event}: {n_worse} of {n_present} conditions got worse, {n_safer} got safer, and {n_unchanged} show no significant change at q = {q}."
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
GO1_COMPLEMENT_LINE = COMPLEMENT_LINE.format(e1="fell", e2="survived", n=400, k=60, worse="survived", safer="fell")
TRADE_LINE = "Trade: {safer} fell in {n} {cells} where {worse} rose."
HOLES_SUMMARY = "{n} holes: {g} on the grid, {o} off it (a condition whose axis value no comparable condition has, so it is on no heatmap)."
HONESTY_NONE = "No unchanged cells; every cell moved significantly."
HONESTY_RE = re.compile(r"can only detect a (\d+)pp rise")
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
    import proofload.viewer as module

    return module


def plain() -> Any:
    import proofload.plain as module

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
    if method != "fisher_bh":
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
    out: list[str] = []
    if s["partial"] is not None:
        out.append(s["partial"]["line"])
    if s["complement"] is not None and s["complement"]["line"] is not None:
        out.append(s["complement"]["line"])
    for entry in s["events"]:
        out.append(entry["line"])
        out.extend(row["line"] for row in entry["worse"])
        out.append(entry["limit"]["line"])
    out.append(s["pointer"])
    return out


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


def legend_caption(event: str, trades: bool) -> str:
    caption = (
        f"delta = rate_b - rate_a in pp; event={event}; negative is safer only if the event "
        f"is a failure; corner square = significant; blank = no data"
    )
    return caption + ("; " + LEGEND_TAIL if trades else "")


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
            "caption": wrap(legend_caption(event, trades), budget(width, left, FONT - 2)),
            "honesty": [wrap(text, budget(width, left, FONT - 2)) if WRAPPED_HONESTY else [text] for text in str(entry["honesty"]).splitlines()],
        }
    return {"width": width, "title": title, "header": header, "panels": panels}


# ---------- fixtures ----------


def build_synth_store(root: Path) -> None:
    """Every builder-made pair: S29's nine, this oracle's partial pair and its traded pair."""
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
        pair("go1", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw"),
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
    ]


@pytest.fixture(scope="module")
def go1(every_pair: list[Pair]) -> Pair:
    return every_pair[0]


@pytest.fixture(scope="module")
def go1_two(every_pair: list[Pair]) -> Pair:
    return every_pair[1]


@pytest.fixture(scope="module")
def titled() -> Pair:
    return pair("go1-titled", GO1_ROOT, GO1_A, GO1_B, ("fell",), "mu", "push_pct_bw", title=LONG_TITLE)


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
BARE_WIDTH: dict[str, float] = {
    "go1": 920.0,
    "go1-two-events": 920.0,
    "axes": 200.0,
    "identical": 200.0,
    "bh": 920.0,
    "gate": 1000.0,
    "multi-event": 440.0,
    "one-value": 280.0,
    "three-key": 280.0,
    "vocab": 200.0,
    "hostile": 200.0,
    "go1-titled": 920.0,
    "partial": 200.0,
    "partial-b": 200.0,
    "traded": 240.0
}
BARE_PANEL_HEIGHT: dict[str, dict[str, float]] = {
    "go1": {
        "fell": 724.0
    },
    "go1-two-events": {
        "survived": 724.0,
        "fell": 724.0
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
    "go1-titled": {
        "fell": 724.0
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
    "go1": {
        "fell": "f48e11830554bd5f97f92dc6bc49e12c7475e9c9a7ef4628a31aab1ea1d30b5f"
    },
    "go1-two-events": {
        "survived": "9740278db673dc19a40ed2c68df9dd430ce2c47ee929b5c5a0bfe2adda3fb74f",
        "fell": "79fff5af38ef2e0e698ce44d8f9b13267312d7ab680022edeaaf2fcdc55e433b"
    },
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
    "go1-titled": {
        "fell": "f48e11830554bd5f97f92dc6bc49e12c7475e9c9a7ef4628a31aab1ea1d30b5f"
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
    "go1": {
        "Result": "9748bfbc69f4068cf628a9f5f5a66c47c3293ec97116977c195ccc699edc868a",
        "Honesty": "9a4412a78ee7dbbb434f6de4ab822aa5ce5bc7c8ba5069ce8de964c8c58ee351",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "2b194936fc7b65518d9c93f1742a20d4d7e9d6161fa181a5856d1e2207563f68",
        "Cells": "fd47e6d33f11f20de37c1d2537ec5b9c9a64c5219f7dd83c457df21fd108181a",
        "Cell": "3c9552661fdef461213d8c34c5f315cd883b754f1a514922af7a9b2093e64cbd",
        "Worst cells": "23751fae229af1c168556629889eec9e2c0be4aca3d8b8a45503ee33ba435df7",
        "Provenance": "3a2d56839e494e55f3923c6c58ee985e41fab7d946f2a78c76a0d585ff94a25b"
    },
    "go1-two-events": {
        "Result": "021ad1a7dac83577b3aa0b74c9065cb2d65c2ec2706ecd1437830a8b62270729",
        "Honesty": "2a4c0951c1c9c6e889085e7b8c65f7b45ab8486811f0519dd694179e68ad326c",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "2b194936fc7b65518d9c93f1742a20d4d7e9d6161fa181a5856d1e2207563f68",
        "Cells": "a8c6bc537f0450fb09671ba48e7ca5a9b1d6b4f51810d5cb7d3e7346fe6b8ea7",
        "Cell": "96984a7ea4942ee243035a20243e93d2a7f402a6202bc2912a60bf99b4dde36e",
        "Worst cells": "0d8359e3ee3bc3f4383d096dccb689b45b946e7300ecc9848808fbf9d83af07d",
        "Provenance": "598da0192f1d2367e612c448871ba55d77a9797eee89c7496ae203a0ee5298fb"
    },
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
    "go1-titled": {
        "Result": "9748bfbc69f4068cf628a9f5f5a66c47c3293ec97116977c195ccc699edc868a",
        "Honesty": "9a4412a78ee7dbbb434f6de4ab822aa5ce5bc7c8ba5069ce8de964c8c58ee351",
        "Not verified": "668a554e7d778e41010a143f5868e5a648e3bfeea6a39b358a89bdaafd3ff681",
        "Fault lines": "2b194936fc7b65518d9c93f1742a20d4d7e9d6161fa181a5856d1e2207563f68",
        "Cells": "fd47e6d33f11f20de37c1d2537ec5b9c9a64c5219f7dd83c457df21fd108181a",
        "Cell": "3c9552661fdef461213d8c34c5f315cd883b754f1a514922af7a9b2093e64cbd",
        "Worst cells": "23751fae229af1c168556629889eec9e2c0be4aca3d8b8a45503ee33ba435df7",
        "Provenance": "3a2d56839e494e55f3923c6c58ee985e41fab7d946f2a78c76a0d585ff94a25b"
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


def normalised_region(page: str, heading: str) -> str:
    lines = region_lines(page, heading)
    if heading == "Result":
        lines = [line for line in lines if not (line.startswith("<p>Trade:") or "are complements here" in line or "Compared as two separate samples" in line)]
    if heading == "Cell":
        lines = [line for line in lines if not line.startswith('<script type="application/json" id="proofload-holes">')]
    text = "\n".join(lines)
    for tail in (*RETIRED_TAILS, *NEW_TAILS):
        text = text.replace(html_mod.escape(tail), "")
    return text.replace(html_mod.escape(MDE_MEANING_BARE), html_mod.escape(MDE_MEANING_PLAIN))


# ---------- LS1: no cell swallows its own click ----------


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
    from proofload.report import _html_style

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
                for k, line in enumerate(lines):
                    hits = [t for t in texts if t.content == line and t.font == font and t.x == x]
                    assert hits, (p.name, kind, line[:70], [c[:40] for c in contents if c.startswith(line[:12])])
                    for t in hits:
                        assert right_edge(t) <= width, (p.name, kind, line[:70], right_edge(t), width)
                        assert t.wrap == (k > 0), (p.name, kind, k, line[:70])
            assert not any(t.content.endswith("…") and t.anchor == "start" and t.font in (FONT + 2, FONT) for t in texts), (p.name, "a title or headline was truncated")


def test_ls2_the_legend_captions_last_six_words_are_present_on_the_traded_pairs(go1_two: Pair, traded: Pair) -> None:
    """Sole catch for a fix that truncates the caption with an ellipsis; a widened box is LS3's."""
    for p in (go1_two, traded):
        assert len(p.multi.trades) > 0, p.name
        texts, _, _ = svg_texts(p.structure["heatmap_svg"])
        joined = " ".join(t.content for t in texts)
        assert LEGEND_TAIL in joined, (p.name, joined[-300:])
        assert not any(t.content.endswith("…") and "corner" in t.content for t in texts), p.name


def test_ls2_the_same_wrap_reaches_the_reports_figure_and_the_receipt(tmp_path: Path) -> None:
    """``report`` draws the figure with the same builders: its ``heatmap.svg`` and the receipt's
    inline figure carry the wrapped caption on the two-event Go1 pair."""
    out = tmp_path / "rep"
    code, _, err = run_cli(["--store", str(GO1_ROOT), "report", GO1_A, GO1_B, "--event", "fell", "--event", "survived", "--x", "push_pct_bw", "--y", "mu", "--out", str(out)])
    assert code == 0, err[-400:]
    for name in ("heatmap.svg", "receipt.html"):
        text = (out / name).read_text(encoding="utf-8")
        svg = text if name.endswith(".svg") else re.search(r"(<svg.*?</svg>)", text, re.S).group(1)  # type: ignore[union-attr]
        texts, width, _ = svg_texts(svg)
        assert LEGEND_TAIL in " ".join(t.content for t in texts), name
        assert all(right_edge(t) <= width for t in texts if t.font == FONT - 2 and t.content.startswith("delta = ")), name
    md = (out / "report.md").read_text(encoding="utf-8")
    assert GO1_COMPLEMENT_LINE in md and RETIRED_TRADE_TAIL not in md


# ---------- LS3: the figure grows and the grid does not move ----------


def test_ls3_the_box_grows_by_the_extra_lines_and_by_nothing_else(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        layout = expected_layout(p)
        _, width, height = svg_texts(p.structure["heatmap_svg"])
        assert width == BARE_WIDTH[p.name], (p.name, width)
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


def test_ls4_a_pair_with_no_holes_keeps_the_one_line_form(go1: Pair) -> None:
    assert go1.structure["holes"] == []
    assert region_lines(go1.page, "Holes") == [NO_HOLES_LINE]


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
        assert tuple(s) == TOP_LEVEL_KEYS and s["schema"] == SCHEMA, (p.name, tuple(s))
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


def test_ls8_render_html_refuses_every_retired_version_by_name(go1: Pair) -> None:
    for retired in RETIRED_SCHEMAS:
        with pytest.raises(viewer().ViewerError) as info:
            viewer().render_html({**go1.structure, "schema": retired})
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
        for path in SRC.glob("*.py"):
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
        for sentence in summary_sentences(p.structure):
            for token in NUMBER_RE.findall(sentence):
                assert any(token in value for value in allowed), (p.name, token, sentence[:120])


# ---------- LS10, LS11: the two thresholds, on a hand-built panel ----------


def synthetic_cell(k: int, q: float, p_value: float, delta: float = 0.281, verdict: str = "worse", mde: float = 0.2) -> dict[str, Any]:
    return {
        "coords": f"mu={k}, push_pct_bw=30", "config_hash": f"{k:016x}", "n_a": 32, "n_b": 32, "rows_a": 32, "rows_b": 32,
        "no_outcome_a": 0, "no_outcome_b": 0, "events_a": 4, "events_b": 13, "rate_a": 0.125, "rate_b": 0.125 + delta, "delta": delta,
        "stat": 0.25, "p": p_value, "q": q, "mde": mde, "verdict": verdict, "config": {"mu": k, "push_pct_bw": 30},
        "config_text": {"mu": str(k), "push_pct_bw": "30"},
        "text": {"rate_a": "12.5", "rate_b": _fmt(0.125 + delta, "pp1"), "delta": _fmt(delta, "pp1"), "stat": "0.25", "p": _fmt(p_value, "sig3"), "q": _fmt(q, "sig3"), "mde": _fmt(mde, "pp0")},
    }


def synthetic_panel(cells: list[dict[str, Any]], mde_unchanged: float | None, where: str | None = "mu=9, push_pct_bw=30") -> dict[str, Any]:
    worse = sum(c["verdict"] == "worse" for c in cells)
    safer = sum(c["verdict"] == "safer" for c in cells)
    if mde_unchanged is None:
        honesty = HONESTY_NONE + "\nWorst-powered cell overall: 20pp (mu=0, push_pct_bw=30)."
        block = {"value": None, "text": None, "where": None}
    else:
        honesty = f'Worst-powered unchanged cell ({where}, n=32/32) can only detect a {_fmt(mde_unchanged, "pp0")}pp rise. "{worse} worse" is an honest claim only above that.\nWorst-powered cell overall: 20pp (mu=0, push_pct_bw=30).'
        block = {"value": mde_unchanged, "text": _fmt(mde_unchanged, "pp0"), "where": where}
    return {
        "event": "fell", "caption": f"fell: {safer} safer, {worse} worse", "honesty": honesty, "mde_unchanged": block,
        "n_safer": safer, "n_worse": worse, "n_unchanged": len(cells) - safer - worse, "n_absent": 0, "n_present": len(cells),
        "x_values": [str(c["config"]["mu"]) for c in cells], "y_values": ["30"], "cells": cells, "worst_header": [], "worst_rows": [], "worst_hashes": [c["config_hash"] for c in cells],
    }


VIEW = {"title": "t", "x_axis": "mu", "y_axis": "push_pct_bw", "fixed": {}, "theme": "dark", "top_n": 10, "forest": "auto", "bound": 0.3, "sign_convention": "delta = rate_b - rate_a"}
PAIR_OBJ = {"store_root": "<store>", "created_at_gap_s": 0.0, "a": {"role": "baseline", "run_id": "a", "status": "complete"}, "b": {"role": "candidate", "run_id": "b", "status": "complete"}}
DIFF_OBJ = {"events": ["fell"], "q": 0.25, "n_tests": 7, "seed_identity_match": True, "unpaired_analysis": True}
Q_LADDER = ((0.0005, "very sure"), (0.001, "sure"), (0.005, "sure"), (0.01, "fairly sure"), (0.02, "fairly sure"), (0.05, None), (0.2, None))
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
        fields = dict(where=cell["coords"], event="fell", before="12.5", after=cell["text"]["rate_b"], change=cell["text"]["delta"], q=cell["text"]["q"])
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
            worse = sorted((c for c in panel["cells"] if c["verdict"] == "worse"), key=lambda c: (-c["delta"], c["q"], c["mde"], c["config_hash"]))
            assert [row["config_hash"] for row in entry["worse"]] == [c["config_hash"] for c in worse[: p.structure["view"]["top_n"]]], (p.name, entry["event"])
            for row in entry["worse"]:
                cell = cells[row["config_hash"]]
                assert row["confidence"] == label_for(cell["q"]), (p.name, row)
                assert (row["where"], row["before"], row["after"], row["change"], row["q"]) == (cell["coords"], cell["text"]["rate_a"], cell["text"]["rate_b"], cell["text"]["delta"], cell["text"]["q"])
                seen.add(row["confidence"])
            assert entry["line"] == COUNTS_LINE.format(event=entry["event"], n_worse=panel["n_worse"], n_present=panel["n_present"], n_safer=panel["n_safer"], n_unchanged=panel["n_unchanged"], q=p.structure["diff"]["q"]), entry["line"]
    assert "very sure" in seen, seen


def test_ls11_too_small_to_tell_is_a_function_of_mde_unchanged_alone_at_0_50() -> None:
    cells = [synthetic_cell(0, 1e-5, 1e-6), synthetic_cell(9, 0.9, 0.9, delta=0.0, verdict="unchanged", mde=0.5)]
    for value, labelled in ((0.49, False), (0.50, True), (0.51, True), (0.999, True), (0.0, False)):
        limit = summary_of([synthetic_panel(cells, value)])["events"][0]["limit"]
        fields = dict(where="mu=9, push_pct_bw=30", n_a=32, n_b=32, mde=_fmt(value, "pp0"))
        assert limit["mde"] == _fmt(value, "pp0") and limit["where"] == "mu=9, push_pct_bw=30", limit
        if labelled:
            assert limit["label"] == "too small to tell" and limit["line"] == LIMIT_LINE_LABELLED.format(**fields), limit
        else:
            assert limit["label"] is None and limit["line"] == LIMIT_LINE.format(**fields), limit
    limit = summary_of([synthetic_panel(cells, None)])["events"][0]["limit"]
    assert limit == {"label": None, "mde": None, "where": None, "line": LIMIT_LINE_NONE}, limit


def test_ls11_the_limit_never_attaches_to_a_worse_row() -> None:
    cells = [synthetic_cell(0, 1e-5, 1e-6, mde=0.9), synthetic_cell(9, 0.9, 0.9, delta=0.0, verdict="unchanged", mde=0.6)]
    entry = summary_of([synthetic_panel(cells, 0.6)])["events"][0]
    assert entry["limit"]["label"] == "too small to tell"
    assert entry["worse"] and all(row["confidence"] == "very sure" for row in entry["worse"])
    for row in entry["worse"]:
        assert "too small" not in row["line"].lower(), row
        assert not set(row) & {"label", "mde", "limit"}, row


def test_ls11_the_panels_mde_unchanged_is_the_honesty_number_character_for_character_on_every_fixture(all_pairs: list[Pair]) -> None:
    seen = set()
    for p in all_pairs:
        for panel, entry in zip(p.structure["panels"], p.structure["summary"]["events"], strict=True):
            block = panel["mde_unchanged"]
            first = str(panel["honesty"]).splitlines()[0]
            if first == HONESTY_NONE:
                assert block == {"value": None, "text": None, "where": None}, (p.name, block)
                assert entry["limit"] == {"label": None, "mde": None, "where": None, "line": LIMIT_LINE_NONE}, (p.name, entry["limit"])
                seen.add("nan")
                continue
            m = HONESTY_RE.search(first)
            assert m is not None and block["text"] == m.group(1) == _fmt(block["value"], "pp0"), (p.name, first, block)
            assert 0.0 <= block["value"] <= 1.0
            assert f"({block['where']}, n=" in first, (p.name, first, block["where"])
            cell = next(c for c in panel["cells"] if c["coords"] == block["where"])
            assert cell["verdict"] == "unchanged"
            labelled = block["value"] >= TOO_SMALL_TO_TELL
            fields = dict(where=block["where"], n_a=cell["n_a"], n_b=cell["n_b"], mde=block["text"])
            assert entry["limit"] == {"label": "too small to tell" if labelled else None, "mde": block["text"], "where": block["where"], "line": (LIMIT_LINE_LABELLED if labelled else LIMIT_LINE).format(**fields)}, (p.name, entry["limit"])
            seen.add("labelled" if labelled else "bare")
    assert seen == {"nan", "labelled", "bare"}, seen


def test_ls11_no_module_parses_the_honesty_prose_for_the_number() -> None:
    """Sole catch for a build that keeps the dashboard's text pattern."""
    pattern = re.compile(r"honesty[^\n]*\.(split|find|index|search|match|findall)\(|re\.\w+\([^\n]*honesty")
    for path in SRC.glob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert not pattern.search(line), (path.name, i, line.strip())


# ---------- LS12: the plain register never decides ----------


def test_ls12_no_deciding_word_no_forbidden_vocabulary_and_no_question_in_the_summary(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        texts = [*summary_sentences(p.structure), *walk_strings(p.structure["summary"]), region_text(p.page, "Summary")]
        for text in texts:
            low = masked(text, p.structure)
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


def test_ls13_the_two_event_go1_pair_is_reported_once_and_never_as_a_trade(go1_two: Pair) -> None:
    assert go1_two.multi.complementary_events() == ("fell", "survived")
    assert go1_two.multi.trade_line() == GO1_COMPLEMENT_LINE
    assert go1_two.structure["trade_line"] == GO1_COMPLEMENT_LINE
    assert go1_two.structure["summary"]["complement"] == {"events": ["fell", "survived"], "line": GO1_COMPLEMENT_LINE}
    assert go1_two.structure["summary"]["complement"]["line"] == go1_two.structure["trade_line"]
    # Ruling 6 (2026-09-22): the sentence has one source. ``plain.py`` carries ``trade_line`` and
    # composes no complement sentence of its own.
    assert "complements here" not in PLAIN_SOURCE.read_text(encoding="utf-8")
    assert "trade_line" in inspect.signature(plain().build_summary).parameters
    lines = summary_lines(go1_two.page)
    assert lines[0] == GO1_COMPLEMENT_LINE, lines[0]
    assert [e["event"] for e in go1_two.structure["summary"]["events"]] == ["survived", "fell"]
    for entry, panel in zip(go1_two.structure["summary"]["events"], go1_two.structure["panels"], strict=True):
        assert str(panel["n_worse"]) in entry["line"] and str(panel["n_safer"]) in entry["line"]
    assert GO1_COMPLEMENT_LINE in region_text(go1_two.page, "Result")
    for path in SRC.glob("*.py"):
        assert RETIRED_TRADE_TAIL not in path.read_text(encoding="utf-8"), path.name


def test_ls13_every_other_fixture_is_not_complementary_and_its_trade_line_is_what_it_was(every_pair: list[Pair], titled: Pair, partial: Pair) -> None:
    for p in [*every_pair[:1], *every_pair[2:], titled, partial]:
        assert p.multi.complementary_events() is None, p.name
        assert p.multi.trade_line() is None and p.structure["trade_line"] is None, p.name
        assert p.structure["summary"]["complement"] is None, p.name


def test_ls13_the_non_complementary_trade_line_counts_the_co_occurrence_and_names_no_cause(traded: Pair) -> None:
    m = traded.multi
    assert m.complementary_events() is None and len(m.trades) == 2
    assert m.trade_line() == TRADE_LINE.format(safer="fail", n=2, cells="cells", worse="crash"), m.trade_line()
    assert traded.structure["trade_line"] == m.trade_line() and traded.structure["summary"]["complement"] is None
    assert RETIRED_TRADE_TAIL not in m.trade_line() and "patch" not in m.trade_line()


def test_ls14_the_complement_test_is_exact_integer_and_conservative(go1_two: Pair) -> None:
    src = source_of(DIFF_SOURCE, "complementary_events")
    tree = ast.parse(src)
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert names & {"n_a", "n_b", "events_a", "events_b", "config_hash"} == {"n_a", "n_b", "events_a", "events_b", "config_hash"}, names
    assert not names & {"rate_a", "rate_b", "delta", "isclose", "allclose"}, names
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, float) for n in ast.walk(tree)), src
    assert not any(isinstance(n, ast.Call) and getattr(n.func, "attr", getattr(n.func, "id", "")) in ("isclose", "allclose", "abs", "float") for n in ast.walk(tree)), src
    store = Store(GO1_ROOT)
    fa, fb = store.read(GO1_A, meta=False), store.read(GO1_B, meta=False)
    ma, mb = store.manifest(GO1_A), store.manifest(GO1_B)
    censored = fa.copy()
    censored.loc[censored.index[0], "outcome"] = "neither"
    assert quiet_multi_diff(censored, fb, ma, mb, events=("fell", "survived")).complementary_events() is None
    assert quiet_multi_diff(fa, fb, ma, mb, events=("fell", "survived", "neither")).complementary_events() is None
    m = go1_two.multi
    e2 = m.events[1]
    fewer = replace(m.by_event[e2], cells=m.by_event[e2].cells.iloc[1:].reset_index(drop=True))
    assert replace(m, by_event={**m.by_event, e2: fewer}).complementary_events() is None
    assert m.complementary_events() == ("fell", "survived")


# ---------- LS15: a partial run says so first ----------


def test_ls15_a_partial_arm_is_named_first_in_the_summary_from_either_side(partial: Pair, partial_b: Pair, go1: Pair) -> None:
    for p, role in ((partial, "baseline"), (partial_b, "candidate")):
        arm = p.structure["pair"]["a" if role == "baseline" else "b"]
        assert arm["status"] == "partial" and arm["run_id"] == PARTIAL_A
        line = PARTIAL_LINE.format(run_id=PARTIAL_A, role=role)
        assert p.structure["summary"]["partial"] == {"runs": [PARTIAL_A], "line": line}, p.structure["summary"]["partial"]
        assert summary_lines(p.page)[0] == line, summary_lines(p.page)[0]
        header, rows = table_of(region_lines(p.page, "Run pair")[0])
        status = next(r for r in rows if r[0] == "status")
        assert status == ["status", "partial", "complete"] if role == "baseline" else ["status", "complete", "partial"]
    assert go1.structure["summary"]["partial"] is None
    assert not any("recorded status" in line for line in summary_lines(go1.page))
    header, rows = table_of(region_lines(go1.page, "Run pair")[0])
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
    ("--x", "mu", "--y", "nope"),
    ("--x", "mu"),
    ("--x", "mu", "--y", "push_pct_bw", "--fix", "nope=1"),
    ("--x", "mu", "--y", "push_pct_bw", "--fix", "mu=0.1"),
    ("--x", "mu", "--y", "mu"),
    ("--x", "mu", "--y", "push_pct_bw", "--fix", "broken"),
)


def test_ls17_no_refusal_reachable_from_serve_names_a_python_parameter(go1: Pair) -> None:
    for tail in BAD_ARGV:
        code, out, err, calls = run_serve(["--store", str(GO1_ROOT), "serve", GO1_A, GO1_B, "--event", "fell", *tail, "--json"])
        assert code == 2 and calls == [] and out == "", (tail, code, err[-300:])
        low = err.lower()
        for spelling in ("x_axis", "y_axis", "fixed=", "fixed ", "spec."):
            assert spelling not in low, (tail, err)
        if "pin" in low or "not a config key" in low or "unknown config key" in low:
            assert "--x" in err or "--y" in err or "--fix" in err, (tail, err)
    code, out, err, calls = run_serve(["--store", str(GO1_ROOT), "serve", GO1_A, GO1_B, "--event", "fell", "--json"])
    assert code == 2 and "--x AXIS" in err, err


# ---------- LS18: the docs ----------


def test_ls18_the_readme_has_a_serve_section_and_the_docs_page_names_the_fourteen_headings_in_order() -> None:
    readme = README.read_text(encoding="utf-8")
    heading = next((line for line in readme.splitlines() if line.startswith("#") and "serve" in line.lower()), None)
    assert heading is not None, "no serve heading in README"
    assert re.search(r"^\s*proofload\b.*\bserve\b.*--event\b.*--x\b", readme, re.M), "no runnable serve command in README"
    assert "docs/reading-a-serve-page.md" in readme
    assert re.search(r"^- \[[^\]]+\]\(docs/reading-a-serve-page\.md\)", readme, re.M), "the docs list does not link the page"
    assert "Pre-release" in readme
    assert SERVE_DOC.exists()
    doc = SERVE_DOC.read_text(encoding="utf-8")
    positions = [next((m.start() for m in re.finditer(rf"^#+ {re.escape(h)}\s*$", doc, re.M)), -1) for h in H2_SEQUENCE]
    assert all(pos >= 0 for pos in positions), [h for h, pos in zip(H2_SEQUENCE, positions, strict=True) if pos < 0]
    assert positions == sorted(positions), list(zip(H2_SEQUENCE, positions, strict=True))


# ---------- LS19: the expert register is complete and reachable ----------


def test_ls19_every_dispatch_heading_is_still_on_the_page_and_the_untouched_regions_keep_their_bytes(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        assert set(h2_sequence(p.page)) == DISPATCH_H2, p.name
        for heading in UNTOUCHED_REGIONS:
            assert sha(normalised_region(p.page, heading)) == REGION_SHA256[p.name][heading], (p.name, heading)


def test_ls19_the_summary_introduces_no_number_the_statistics_view_does_not_carry(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        lines = p.page.splitlines()
        marks = h2_lines(p.page)
        rest = html_mod.unescape("\n".join(lines[: marks[0][0]] + lines[marks[1][0] :]))
        for sentence in summary_sentences(p.structure):
            for token in NUMBER_RE.findall(sentence):
                assert token in rest or token in THRESHOLD_SPELLINGS, (p.name, token, sentence[:120])


# ---------- LS20: serve --json is the one source ----------


def test_ls20_every_sentence_in_the_summary_region_is_a_line_of_summary_and_the_reverse(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        assert summary_lines(p.page) == summary_sentences(p.structure), p.name


def test_ls20_the_page_renders_from_a_round_tripped_structure_with_no_report_diff_or_tree_in_scope(go1_two: Pair) -> None:
    text = json.dumps(go1_two.structure, allow_nan=False)
    again = viewer().render_html(strict_loads(text))
    assert again == go1_two.page
    render = source_of(VIEWER_SOURCE, "render_html")
    whole = VIEWER_SOURCE.read_text(encoding="utf-8")
    for fragment in ("conditions got worse", "How sure", "Too small to tell", "recorded status", "complements here", "Every number above", "separate samples"):
        assert fragment not in whole, fragment
    assert "summary" in render
