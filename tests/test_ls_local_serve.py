"""LS -- local serve: the frozen tests for LS1-LS21.

The surfaces under test are ``src/poisson_prove/diff.py`` (``complementary_events``,
``trade_line``), ``src/poisson_prove/report.py`` (the figure's text wrapping and the wrapped texts,
``MultiReport.complement``), ``src/poisson_prove/plain.py``, ``src/poisson_prove/viewer.py`` (the
inert rule, the docstring and both refusals, the hole's ``where``, the holes block, the ``summary``
key, the schema, the page order, the unverified tails) and ``src/poisson_prove/cli.py`` (help and two
refusal wordings).

**``poisson_prove.plain`` and the changed surfaces are reached inside test bodies** through ``plain()``
and ``viewer()``, so a break in one of them fails the tests that use it, never the collection, and
every other test in the repo still reports. Source is read through ``poisson_prove.__file__``, never
``Path.cwd()``, so a run under ``PYTHONPATH`` reads the tree it was pointed at.

**Conventions this file fixes where the invariants are silent or disagree with each other.**

- **The Summary region is one ``<p>`` per sentence, one element per line, no table, no list, no
  attribute, no ``<details>``**, in this order: the partial line (if any), the complement line (if
  any), then per event in ``panels`` order the counts line, each ``worse`` row's line, the limit
  line, and last the pointer. Every ``<p>`` is one ``line`` value of ``summary`` through
  ``html.escape``, so LS20's two directions are one equality.
- **The event name is spelled bare** in the counts and row sentences: ``tripped: 0 of 72 conditions
  ...``, with no backticks around it, as the headline spells events.
- **``change`` is the cell's ``text["delta"]`` verbatim**, so a rise reads ``28.1`` and not
  ``+28.1``; verbatim is what LS9 can check.
- **``q`` in the counts sentence is ``str()`` of the ``diff`` object's ``q``** (``0.05``). LS9's
  payload-bound clause accepts it because the tree's ``bound.text.q`` spells the same number; the
  two spellings part below ``q = 0.001`` (``sig3`` goes scientific), which no fixture reaches and is
  named as a non-observable rather than pinned.
- **The unlabelled row's ``0.05`` is fixed text**, the one numeric token of a sentence that is a
  threshold and not a field; LS9 admits the spellings of the module's own thresholds and nothing
  else beyond the payload.
- **The ``worse`` rows are the panel's ``worse`` cells sorted by ``(-delta, q, mde, config_hash)``**
  -- the report's tie-break key for its worst cells -- cut at ``view.top_n``; a sort is not arithmetic.
- **The complement sentence's second clause names the traded pair, not ``events`` order**:
  ``The {k} conditions where {worse} rose are the {k} where {safer} fell``, with
  ``(safer, worse)`` the pair ``trade_line()`` picks. On the two-event lattice pair the two readings coincide.
- **``build_summary`` takes the trade line as a sixth keyword**, so
  ``summary.complement.line`` *is* ``trade_line()`` and ``plain.py`` composes no complement sentence:
  one source for one sentence, on every method.
- **Under complementarity with nothing significant, ``trade_line()`` stays ``None``** (the existing
  first guard runs first) and ``summary.complement`` is ``{"events": [...], "line": None}``: there
  is no traded pair to name. No fixture reaches it.
- **The non-complementary trade line keeps its first sentence and drops its second**:
  ``Trade: {safer} fell in {n} cells where {worse} rose.`` "moved failures" appears nowhere in
  ``src/`` (LS13), and that rule wins over keeping the old line whole.
- **The partial line names each partial run in ``a``, ``b`` order**, one sentence per run joined by
  a space, and ``summary.partial["runs"]`` lists them in that order.
- **LS2 is pinned over five texts**: the four wrapped texts -- the title (stacked and per panel), the
  headline lines (stacked header and panel caption), the trade or complement line, the legend caption
  -- and the honesty lines, each identified by content through this file's restatement of
  the figure's wrapping and its budget. LS2's clause reads "every ``<text>``"; that
  cannot hold on a box 200 px wide, whose legend swatch *rects* sit at a fixed 46 px
  pitch and already leave it; the swatch labels are the named exception.
- **A wrapped text is drawn as one ``<text>`` per line, the continuation lines carrying
  ``data-wrap="1"`` and the first line not**, so the M7 tests can read a wrapped
  text back as one, and so a reader of the SVG can tell a wrapped line from a new text.
- **The tree refusal keeps its wording.** It carries no version literal to interpolate, and
  ``test_p1_payload.py``'s Y15 pins its text; LS8
  asserts it names no version, and the intervals refusal alone interpolates ``SCHEMA``.
- **LS3's rect clause is "unchanged up to the top growth"**: ``x``, ``width``, ``height``,
  ``fill`` and the four ``data-`` attributes of every grid and glyph rect are where the grid
  layout and the colour rule put them before anything wraps, and ``y`` is that value plus exactly
  the growth of ``top`` (``18`` per extra title line, ``12`` per extra headline line). The
  unwrapped rects are recomputed from the lattice design on the lattice pairs and from the
  library's frame on the same runs on the builder-made pairs; "unchanged" holds only where
  nothing above the grid wraps, and a grid that did not move down would be drawn over its own
  title.
- **LS16 holds over the whole page, six tokens.** A public page carries no reference a stranger
  cannot resolve, so the Cells region, on every pair with a rejecting family, spells its MDE
  sentence ``MDE is the smallest detectable increase ...`` (and its twin in ``report.py`` the same).
- **The hole's ``where`` on a grid hole is its ``coords`` string, and on an off-grid hole is
  ``", ".join(f"{axis}={config_text[axis]}")`` over ``x_axis``, ``y_axis`` and the keys of
  ``view.fixed`` in that order**, or ``off grid: <config_hash>`` when the config carries none of them.
  The Holes summary paragraph is the on-grid and off-grid count sentence with the cause counts after it.
- **``mde_unchanged.where``** is the ``coords`` string of the cell the honesty line's three-step search
  names, and ``mde_unchanged.text`` is the value in M7's ``pp0`` form; ``None`` for all three when the
  honesty line is the fixed "no unchanged cells" sentence.
- **LS19 reads the eight regions by their facts**: the ``Result`` region line by line from the
  library's counts (with the pairing line and the trade or complement line), ``Not verified``
  entry by entry from the 0.0.1 store's recorded payload with the new tails, ``Provenance`` item
  by item from the stored runs, and the other five against the payload and the library's frame.
- **LS21, the word "unpaired":** the word and the Python warning stay exactly as they are, and one plain line is printed beside the word --
  in the ``Result`` block, the ``<p>`` right after the headline -- iff the payload's
  ``diff.unpaired_analysis`` is true (the runs share their seeds and the test ignores that). It rides
  the payload as ``summary.pairing.line`` (``None`` otherwise), third key of ``summary`` after
  ``complement``, and is the one ``line`` of ``summary`` that is read in ``Result`` rather than in
  the Summary region, so LS20's equality leaves it out. The wording is a pairing report's
  suggested sentence, verbatim.

**Fixture limits.** Every S29 pair is complete,
so LS15 rests on this file's own partial pair (three holes, ``part-a`` never marked complete,
both orders). No stored pair was taken at ``--q`` above 0.05, so the unlabelled row and the ``q``
boundaries are exercised on a hand-built panel (LS10) and only the labels the real payloads reach
are re-asserted on them. The two-event lattice pair (``tests/lattice.py``) is the only complementary fixture; the
non-complementary trade line is reached through a builder-made pair (``trade-a``/``trade-b``)
whose one all-``fail``/all-``crash`` cell is a trade and whose ``ok`` rows break condition 4.
The lattice's run ids are short, so the wrapped title needs ``--title``.

**Named non-observables.** A ``q`` below 0.001 spelled two ways (above). A wrapped text whose
lines are joined with a different separator than one space: the figure breaks on spaces only.
A sentence composed inside ``render_html`` that equals a ``line`` value character for character:
LS20's equality cannot see it.
"""

from __future__ import annotations

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
from poisson_prove.store import EpisodeRecord, RunManifest, Store

PACKAGE = Path(poisson_prove.__file__).resolve().parent
REPO = PACKAGE.parents[1]
README = REPO / "README.md"
SERVE_DOC = REPO / "docs" / "reading-a-serve-page.md"
#: The generated lattice pair (``tests/lattice.py``), built once per machine and checked on use.
LATTICE_ROOT = lattice.root()
LATTICE_A, LATTICE_B = lattice.RUN_A, lattice.RUN_B

# ---------- the literals ----------

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
# The contract names the share caption, not this key; share_label is the payload's name for it.
# ``threshold`` is the verdict's threshold on the panel, so the Summary reads it as a payload field.
# PF4.34 to PF4.47: each panel carries ``flag_rule`` after ``kind``; the order is the one
# ``viewer.py`` writes.
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
    "direction", "direction_note", "pairs", "n01", "n10", "mde_note",
    # PF4.34 to PF4.47: Holm's q and flag, the limit keys, the competing shift and the
    # interval, after mde_note; the order is the one ``viewer.py`` writes.
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
#: LS7. The ``summary`` object, its event entry, a ``worse`` row and the limit.
# PF4 (PF4.5): the Summary carries the comparison's verdict word, first.
# PF4.34, PF4.35, PF4.40, PF4.44, PF4.46: after the word, the verdict rule, the verdict
# line, the verdict limit, the fragility, peeking, the errored episodes and the verdict block's detail
# lines (``facts``); the order is the one ``viewer.py`` writes.
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
#: LS19. The regions LS leaves as they were but for the two unverified tails (and the one this
#: file's LS16 convention adds), each checked by its facts.
UNTOUCHED_REGIONS = ("Result", "Honesty", "Not verified", "Fault lines", "Cells", "Cell", "Worst cells", "Provenance")
# The page no longer speaks of planned changes: a limit some later version may close says only
# that this version does not check it.
NEW_TAILS = (" (this version does not check it)", " (nothing planned would close this; it is a limit of the instrument)")
#: LS19. The tail each unverified entry's ``blocked_by`` reads as on the page.
TAIL_OF = {"B.1": NEW_TAILS[0], None: NEW_TAILS[1]}
#: LS19. The 0.0.1 store's recorded ``serve --json``, whose ``unverified`` entries are the ones the
#: Not verified region lists, read as data.
RECORDED_SERVE = Path(__file__).resolve().parent / "fixtures" / "stores-0.0.1" / "recorded" / "serve-fisher_bh.json"
#: LS10, LS11. The confidence thresholds and the quantity each applies to.
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
# PF4 (PF4.20): not asserted; on an event of unknown kind the caption reads in direction
# words. LS2 reads the caption off the figure (drawn_legend_caption) and asserts its facts.
LEGEND_TAIL = "corner notches = trade (safer in one event, worse in another)"
#: The honesty lines join the wrap set: besides the four wrapped texts, the honesty lines pass the
#: box on every narrow pair unwrapped, so they wrap too (a fifth
#: text, at the caption's 12 px pitch).
WRAPPED_HONESTY = True

# ---------- the words, verbatim ----------

# PF4.40: the words "no significant change" always carry the verdict limit on their
# line, so the counts line says the conditions "were not flagged".
COUNTS_LINE = "{event}: {n_worse} of {n_present} conditions got worse, {n_safer} got safer, and {n_unchanged} were not flagged at q = {q}."
ROW_LINE = "{where}: {event} was {before}% of trials and is now {after}%, a rise of {change} percentage points. How sure: {label} (q = {q})."
ROW_LINE_UNLABELLED = "{where}: {event} was {before}% of trials and is now {after}%, a rise of {change} percentage points. How sure: no label (q = {q}; the labels start at 0.05)."
LIMIT_LINE_LABELLED = "Too small to tell: the least sensitive condition among those this run did not call a change ({where}, n = {n_a}/{n_b}) could only have seen a rise of {mde}pp or more. Below that, this run cannot tell a change from none."
LIMIT_LINE = "The least sensitive condition among those this run did not call a change ({where}, n = {n_a}/{n_b}) could only have seen a rise of {mde}pp or more."
LIMIT_LINE_NONE = "Every condition moved significantly, so there is no condition left to state a detection limit from."
PARTIAL_LINE = 'Run {run_id} ({role}) recorded status "partial": it stopped before everything it planned had run. What is below compares the conditions both runs have.'
#: LS21: the one plain line beside the word
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
# PF4.27, PF4.32: the limit named is the condition's own, a rise or a fall.
HONESTY_RE = re.compile(r"can only detect a (\d+)pp (?:rise|fall)")
#: PF4.27: the closed list of reasons a limit is null, printed in words.
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
LONG_TITLE = "A title long enough to wrap: the baseline against the candidate, both arms, every condition the two runs share, measured at the baseline commit"


def manifest(run_id: str, salt: str, axis_types: Mapping[str, str]) -> RunManifest:
    return RunManifest(
        run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=salt,
        axis_types=dict(axis_types), backend="synthetic", environment={"note": "built by these tests"},  # type: ignore[arg-type]
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
    # PF3: with no --method the default is the paired test
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
    # PF4.34, PF4.35, PF4.44: the Summary opens with the comparison's verdict line and
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
    """PF4.35, PF4.42, PF4.44, PF4.46: the verdict block's detail lines the Summary
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


def no_negative_zero(text: str) -> str:
    return text[1:] if text.startswith("-") and float(text) == 0.0 else text


def m7_form(value: float, kind: str) -> str:
    """M7's number forms, written from their rule and never read from ``report.py``: ``pp1`` and
    ``pp0`` a fraction in points to one and to no decimals, ``sig3`` three significant figures
    (``0`` at zero, scientific below 0.001), ``num`` a plain number to ten significant figures; a
    negative zero reads as zero."""
    if kind == "num":
        return no_negative_zero(f"{value:.10g}")
    if kind == "pp1":
        return no_negative_zero(f"{value * 100:.1f}")
    if kind == "pp0":
        return no_negative_zero(f"{value * 100:.0f}")
    assert kind == "sig3", kind
    return "0" if value == 0 else (f"{value:.2e}" if abs(value) < 1e-3 else f"{value:.3g}")


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
    """The figure's text wrapping, restated: broken on spaces into lines of at most ``budget``
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
        a["y"] = m7_form(float(a["y"]) - shift, "num")
        rows.append(json.dumps({k: a.get(k) for k in ("x", "y", "width", "height", "fill", "data-cell", "data-sig", "data-trade", "data-sat")}, sort_keys=True))
    return "\n".join(sorted(rows))


def header_lines(p: Pair) -> list[str]:
    """The multi-event figure's header texts, restated: the inference line, the headline's lines, the trade line."""
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
    the pinned unwrapped geometry alone."""
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


# ---------- the pins (LS3): the page before anything wraps ----------

# ---- pins begin ----
#: LS3. Per pair, the stacked figure's width and, per panel, its unwrapped body height. Wrapping
#: does not move the grid sideways.
#: The three lattice pairs' widths and heights are the grid layout's arithmetic on the lattice
#: design's 12 x 6 grid (``lattice_bare_box``, which LS3 asserts they equal). Every pair's rect set
#: is checked by its facts (``lattice_rects`` on the lattice pairs, ``frame_rects`` on the others).
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
# ---- pins end ----


# ---------- the lattice pairs: each region's facts, from the lattice design ----------

#: The three pairs over the generated lattice (``tests/lattice.py``). Their figure and their Result
#: and Provenance regions are checked against the lattice design and the run identities.
LATTICE_PAIRS = ("lattice", "lattice-two-events", "lattice-titled")
#: The builder-made pairs (``build_synth_store``). Their figure and their Result and Provenance
#: regions are checked against the stored runs and the library's frame on the same runs.
BUILDER_PAIRS = ("axes", "identical", "bh", "gate", "multi-event", "one-value", "three-key", "vocab", "hostile", "partial", "partial-b", "traded")
#: The grid body's layout, restated (the report's grid drawing): a cell is at most 40 px wide over 880 px
#: and at most 28 px high over 560 px, the grid starts 96 px in when there is a y axis, 24 px of
#: margin on the right, 52 px of top band and 112 px of bottom band before anything wraps, and the
#: significance glyph is a 4 px square 1 px inside the cell's top right corner.
GRID_LEFT_WITH_Y, GRID_RIGHT, GRID_TOP, GRID_BOTTOM, GLYPH = 96, 24, 52, 112, 4
#: The dark theme's colour rule, restated (the report's cell colouring): a nine-stop ramp from
#: the survived colour through neutral to the failed colour, linear in sRGB, a non-significant
#: change drawn 0.45 of the way toward neutral, both arms at 0% or both at 100% drawn saturated.
DARK_NEUTRAL, DARK_SATURATED, SURVIVED, FAILED, NONSIG_SCALE = "#1F1F22", "#2A2A2E", "#3ECF8E", "#FF4D4D", 0.45
#: A grid position no condition is on is drawn in the dark theme's no-data colour, its
#: ``data-cell`` the word ``absent``.
DARK_ABSENT = "#141416"


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
    """Per (event, condition) of the lattice under the unpaired test: the lattice design's counts, scipy's
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
    place them, from the lattice design alone: one rect per condition at its grid position (``x`` over the
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
        rects.append({"x": str(x), "y": str(y), "width": str(cell_w), "height": str(cell_h), "fill": fill,
                      "data-cell": r["config_hash"], "data-sig": None, "data-trade": "1" if r["config_hash"] in trades else None,
                      "data-sat": "1" if saturated else None})
        if significant:
            rects.append({"x": str(x + cell_w - GLYPH - 1), "y": str(y + 1), "width": str(GLYPH), "height": str(GLYPH),
                          "fill": None, "data-cell": None, "data-sig": "1", "data-trade": None, "data-sat": None})
    return rects


def axis_values(values: Iterator[Any]) -> list[Any]:
    """An axis's values in grid order: ascending, numbers as numbers and text as text."""
    return sorted(set(values))


def frame_rects(p: Pair, event: str) -> list[dict[str, str | None]]:
    """The grid and glyph rects of one panel of a builder-made pair as the layout and the colour
    rule place them, from the library's frame on the same runs: one rect per condition on the
    panel's slice (every condition, or those ``--fix`` pins) at its grid position over the slice's
    sorted axis values, ``data-cell`` its key, its fill from the change over the colour bound (the
    largest change on the slice, up to the next 0.05) and its direction, ``data-sat`` on the
    conditions both arms hold at 0% or 100%, ``data-trade`` on the conditions one event moved
    lower and another higher; a glyph on every condition that moved; and one no-data rect on every
    grid position no condition is on."""
    def on_slice(r: Mapping[str, Any]) -> bool:
        return all(r["config"].get(k) == v for k, v in p.fixed.items())

    frames = {e: [r for r in p.multi.by_event[e].cells.to_dict(orient="records") if on_slice(r)] for e in p.events}
    biggest = max(abs(r["delta"]) for rows in frames.values() for r in rows)
    steps = int(biggest * 20)
    bound = (max(steps + (steps < biggest * 20), 1)) / 20
    assert bound == p.structure["view"]["bound"], (p.name, bound, p.structure["view"]["bound"])
    moved = {(e, r["config_hash"]): r["direction"] for e, rows in frames.items() for r in rows}
    trades = {h for (_, h) in moved if {moved.get((e, h)) for e in p.events} >= {"lower", "higher"}}
    rows = frames[event]
    xs = axis_values(r["config"][p.x] for r in rows)
    ys = axis_values(r["config"][str(p.y)] for r in rows)
    panel = next(e for e in p.structure["panels"] if e["event"] == event)
    assert panel["x_values"] == [v if isinstance(v, str) else m7_form(v, "num") for v in xs], (p.name, panel["x_values"])
    assert panel["y_values"] == [v if isinstance(v, str) else m7_form(v, "num") for v in ys], (p.name, panel["y_values"])
    cell_w, cell_h = max(4, min(40, int(880 / len(xs)))), max(4, min(28, int(560 / len(ys))))
    rects: list[dict[str, str | None]] = []
    for r in rows:
        x = GRID_LEFT_WITH_Y + xs.index(r["config"][p.x]) * cell_w
        y = GRID_TOP + ys.index(r["config"][str(p.y)]) * cell_h
        saturated = r["rate_a"] == r["rate_b"] and r["rate_a"] in (0.0, 1.0)
        significant = r["direction"] != "unchanged"
        fill = DARK_SATURATED if saturated else dark_fill(r["delta"] / bound, significant)
        rects.append({"x": str(x), "y": str(y), "width": str(cell_w), "height": str(cell_h), "fill": fill,
                      "data-cell": r["config_hash"], "data-sig": None, "data-trade": "1" if r["config_hash"] in trades else None,
                      "data-sat": "1" if saturated else None})
        if significant:
            rects.append({"x": str(x + cell_w - GLYPH - 1), "y": str(y + 1), "width": str(GLYPH), "height": str(GLYPH),
                          "fill": None, "data-cell": None, "data-sig": "1", "data-trade": None, "data-sat": None})
    held = {(r["config"][p.x], r["config"][str(p.y)]) for r in rows}
    for i, xv in enumerate(xs):
        for j, yv in enumerate(ys):
            if (xv, yv) not in held:
                rects.append({"x": str(GRID_LEFT_WITH_Y + i * cell_w), "y": str(GRID_TOP + j * cell_h), "width": str(cell_w),
                              "height": str(cell_h), "fill": DARK_ABSENT, "data-cell": "absent", "data-sig": None,
                              "data-trade": None, "data-sat": None})
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
    """A lattice pair's Result or Provenance region, read line by line against the lattice
    design, the run identities and the payload."""
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


def assert_not_verified(p: Pair) -> None:
    """The Not verified region on every pair: the four entries the 0.0.1 store's recorded payload
    carries, in its order, each its id, its statement and the tail its ``blocked_by`` reads as."""
    recorded = json.loads(RECORDED_SERVE.read_text(encoding="utf-8"))["unverified"]
    assert [e["id"] for e in recorded] == ["outcome_labels", "status_basis", "created_at_meaning", "seed_identity_basis"]
    assert p.structure["unverified"] == recorded, p.name
    expected = ["<ul>", *(
        f"<li><strong>{html_mod.escape(e['id'])}</strong> {html_mod.escape(e['statement'] + TAIL_OF[e['blocked_by']])}</li>"
        for e in recorded
    ), "</ul>"]
    assert region_lines(p.page, "Not verified") == expected, (p.name, region_lines(p.page, "Not verified"))


def stored_hashes(p: Pair, run_id: str) -> set[str]:
    return set(Store(p.root).read(run_id, meta=False)["config_hash"])


def assert_builder_region(p: Pair, heading: str) -> None:
    """A builder-made pair's Result or Provenance region, line by line, from the stored runs and
    the library's frame on the same runs."""
    lines = region_lines(p.page, heading)
    frames = {e: p.multi.by_event[e].cells.to_dict(orient="records") for e in p.events}
    unpaired = not p.method.startswith("mcnemar")
    if heading == "Result":
        counts = {e: (sum(r["direction"] == "lower" for r in rows), sum(r["direction"] == "higher" for r in rows)) for e, rows in frames.items()}
        order = sorted(p.events, key=lambda e: (-counts[e][1], -counts[e][0], e))
        assert [panel["event"] for panel in p.structure["panels"]] == order, p.name
        n_tests = sum(len(rows) for rows in frames.values())
        headline = " · ".join(f"{e}: {counts[e][0]} lower, {counts[e][1]} higher" for e in order) + (
            f"\n(aalen_johansen + {p.method}, BH q<0.05 over {n_tests} tests, {'unpaired' if unpaired else 'paired'})"
        )
        assert p.structure["headline"] == headline, (p.name, p.structure["headline"], headline)
        expected = ["<p>" + html_mod.escape(headline).replace("\n", "<br>") + "</p>"]
        if unpaired:
            expected.append(f"<p>{html_mod.escape(PAIRING_LINE)}</p>")
        moved = {(e, r["config_hash"]): r["direction"] for e, rows in frames.items() for r in rows}
        traded = {h for (_, h) in moved if {moved.get((e, h)) for e in p.events} >= {"lower", "higher"}}
        if traded:
            (safer,) = {e for (e, h), d in moved.items() if h in traded and d == "lower"}
            (worse,) = {e for (e, h), d in moved.items() if h in traded and d == "higher"}
            cells = "cell" if len(traded) == 1 else "cells"
            expected.append(f"<p>{html_mod.escape(TRADE_LINE.format(safer=safer, n=len(traded), cells=cells, worse=worse))}</p>")
        assert lines == expected, (p.name, lines)
        return
    if heading == "Provenance":
        store = Store(p.root)
        salt = store.manifest(p.a).run_salt
        assert store.manifest(p.b).run_salt == salt, p.name
        in_a, in_b = stored_hashes(p, p.a), stored_hashes(p, p.b)
        only_a, only_b = in_a - in_b, in_b - in_a
        # A grid position with no condition on it: the slice's axis values crossed, less the
        # conditions both runs hold.
        shown = [r["config"] for r in frames[p.events[0]] if all(r["config"].get(k) == v for k, v in p.fixed.items())]
        grid = len({c[p.x] for c in shown}) * len({c[str(p.y)] for c in shown})
        items = [
            ("events", ", ".join(p.events)), ("inferred", "false"), ("non event", "none"),
            ("n tests", str(sum(len(rows) for rows in frames.values()))), ("method", p.method), ("seed identity match", "true"),
            ("unpaired analysis", "true" if unpaired else "false"), ("q", "0.05"), ("t unit", "steps"), ("horizon", f"{HORIZON:g}"),
            ("n not comparable", str(len(only_a) + len(only_b))), ("dropped a", str(len(only_a))), ("dropped b", str(len(only_b))),
            ("episodes censored at horizon", "0"), ("n absent", str(grid - len(shown))),
            ("Prove version", poisson_prove.__version__), ("run id a", p.a), ("run id b", p.b), ("run salt", salt),
            ("observation cap a", "not recorded"), ("observation cap b", "not recorded"), ("trace spans a", "0"),
            ("trace spans b", "0"), ("observation cut spans a", "0"), ("observation cut spans b", "0"),
        ]
        expected = "<ul>" + "".join(f"<li>{html_mod.escape(f'{k}: {v}')}</li>" for k, v in items) + "</ul>"
        assert lines == [expected, "</body>", "</html>"], (p.name, lines)
        return
    raise AssertionError((p.name, heading))


def assert_page_names(page: str) -> None:
    """PF0: the page's two data blocks are ``prove-cells`` and ``prove-holes``, the arm table's
    version key is ``poisson_prove_version``, and the provenance list has one ``Prove version:``
    entry; none of the three is spelled with the old name."""
    assert 'id="prove-cells"' in page and 'id="prove-holes"' in page and 'getElementById("prove-cells")' in page
    assert "<td>poisson_prove_version</td>" in page and "proofload-cells" not in page and "proofload-holes" not in page
    assert "<td>proofload_version</td>" not in page
    found = re.findall(r"<li>Prove version: [^<]*</li>", page)
    assert len(found) == 1 and "proofload version:" not in page, found


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


# ---------- LS2: no text the figure draws leaves the figure ----------


def wrapped_texts(p: Pair) -> list[tuple[str, list[str], float, float]]:
    """(kind, lines, font, x) for every wrapped text, from the structure and the restated wrap."""
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
                # PF2: the default title names the runs, so a wrapped title can
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
        # direction words and LEGEND_TAIL's safer/worse wording is not asserted. What stays
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
    # PF3: the lattice's runs share a salt, so the default is the
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
            # the pins are the layout's arithmetic on the lattice design's grid (x across, y down)
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


def test_ls3_every_grid_and_glyph_rect_is_unchanged_up_to_the_top_growth(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        layout = expected_layout(p)
        for event, panel in panel_groups(p.structure["heatmap_svg"]):
            entry = layout["panels"][event]
            shift = TITLE_LINE_H * (len(entry["title"]) - 1) + BODY_LINE_H * (len(entry["headline"]) - 1)
            if p.name in LATTICE_PAIRS:
                # the rect set recomputed from the lattice design, the layout and the colour rule
                expected = sorted(json.dumps(r, sort_keys=True) for r in lattice_rects(p, event))
            else:
                # the rect set recomputed from the library's frame, the layout and the colour rule
                assert p.name in BUILDER_PAIRS, p.name
                expected = sorted(json.dumps(r, sort_keys=True) for r in frame_rects(p, event))
            assert rect_set(panel, shift).split("\n") == expected, (p.name, event, shift)


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
        # serve --json adds verdict and sentence after schema.
        # PF3: and method and method_chosen right after sentence.
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


def test_ls7_the_summary_object_has_its_keys_in_order(all_pairs: list[Pair]) -> None:
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


# ---------- LS9: every sentence is bound to a field ----------

def test_ls9_every_numeric_substring_of_every_sentence_is_a_text_value_a_config_value_or_an_integer_field(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        allowed = set(walk_texts(p.structure)) | set(walk_ints(p.structure)) | THRESHOLD_SPELLINGS | {str(p.structure["diff"]["q"])}
        # PF4.35, PF4.42, PF4.44: the verdict block's detail lines are payload fields
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
        "text": {"rate_a": "12.5", "rate_b": m7_form(0.125 + delta, "pp1"), "delta": m7_form(delta, "pp1"), "stat": "0.25", "p": m7_form(p_value, "sig3"), "q": m7_form(q, "sig3"), "mde": m7_form(mde, "pp0")},
    }


def synthetic_panel(cells: list[dict[str, Any]], mde_unchanged: float | None, where: str | None = "gain=9, load=30") -> dict[str, Any]:
    worse = sum(c["verdict"] == "worse" for c in cells)
    safer = sum(c["verdict"] == "safer" for c in cells)
    if mde_unchanged is None:
        honesty = HONESTY_NONE + "\nWorst-powered cell overall: 20pp (gain=0, load=30)."
        block = {"value": None, "text": None, "where": None}
    else:
        honesty = f'Worst-powered unchanged cell ({where}, n=32/32) can only detect a {m7_form(mde_unchanged, "pp0")}pp rise. "{worse} worse" is an honest claim only above that.\nWorst-powered cell overall: 20pp (gain=0, load=30).'
        block = {"value": mde_unchanged, "text": m7_form(mde_unchanged, "pp0"), "where": where}
    # PF4 (PF4.20): the hand-built panel declares its event a failure, so its counts and rows keep
    # the safer/worse words these tests are about; a panel carries its kind and the direction
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
            # PF4.27: a rising condition can have no limit (null with its note); it
            # sorts after every condition with one, as the report's worst-cell tie-break puts it.
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
    # is too small to tell only above it (at or below it is no significant change).
    # The hand-built pair records 0.50 in both arms, so the boundary stays at 0.50 and a limit of
    # exactly 0.50 is not labelled.
    for value, mde, labelled in ((0.49, "49", False), (0.50, "50", False), (0.51, "51", True), (0.999, "100", True), (0.0, "0", False)):
        limit = summary_of([synthetic_panel(cells, value)], pair_obj=THRESHOLD_PAIR)["events"][0]["limit"]
        fields = dict(where="gain=9, load=30", n_a=32, n_b=32, mde=mde)
        assert limit["mde"] == mde and limit["where"] == "gain=9, load=30", limit
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
    when neither run recorded one."""
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
                # PF4.27: an unchanged condition can have no limit; the honesty line
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
            assert m is not None and block["text"] == m.group(1) == m7_form(block["value"], "pp0"), (p.name, first, block)
            assert 0.0 <= block["value"] <= 1.0
            assert f"({block['where']}, n=" in first, (p.name, first, block["where"])
            cell = next(c for c in panel["cells"] if c["coords"] == block["where"])
            assert cell["verdict"] == "unchanged"
            # PF4 (PF4.5, PF4.17): labelled above the runs' recorded threshold, not at 0.50.
            labelled = block["value"] > threshold
            fields = dict(where=block["where"], n_a=cell["n_a"], n_b=cell["n_b"], mde=block["text"])
            assert entry["limit"] == {"label": "too small to tell" if labelled else None, "mde": block["text"], "where": block["where"], "line": (LIMIT_LINE_LABELLED if labelled else LIMIT_LINE).format(**fields)}, (p.name, entry["limit"])
            seen.add("labelled" if labelled else "bare")
    # PF4.27: the fixtures reach the no-limit case too.
    assert seen == {"nan", "labelled", "bare", "none"}, seen


# ---------- LS12: the plain register never decides ----------


def test_ls12_no_deciding_word_no_forbidden_vocabulary_and_no_question_in_the_summary(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        texts = [*summary_sentences(p.structure), *walk_strings(p.structure["summary"]), region_text(p.page, "Summary")]
        for text in texts:
            low = masked(text, p.structure)
            # PF4.35: the Summary shows the comparison's word, so it carries the
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
    # The sentence has one source: ``build_summary`` is handed ``trade_line``.
    assert "trade_line" in inspect.signature(plain().build_summary).parameters
    lines = summary_lines(lattice_two.page)
    # PF4.34, PF4.35: the Summary opens with the verdict line; the complement sentence
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


def test_ls14_the_complement_test_is_conservative(lattice_two: Pair) -> None:
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
        # PF4.34: the Summary opens with the comparison's verdict line; the partial
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


# ---------- LS21: the plain line beside "unpaired" ----------


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
        # A refusal exits 1.
        assert code == 1 and calls == [] and out == "", (tail, code, err[-300:])
        low = err.lower()
        for spelling in ("x_axis", "y_axis", "fixed=", "fixed ", "spec."):
            assert spelling not in low, (tail, err)
        if "pin" in low or "not a config key" in low or "unknown config key" in low:
            assert "--x" in err or "--y" in err or "--fix" in err, (tail, err)
    code, out, err, calls = run_serve(["--store", str(LATTICE_ROOT), "serve", LATTICE_A, LATTICE_B, "--event", lattice.EVENT, "--json"])
    # A refusal exits 1.
    assert code == 1 and "--x AXIS" in err, err


# ---------- LS18: the docs ----------


def test_ls18_the_readme_has_a_serve_section_and_the_docs_page_names_the_fourteen_headings_in_order() -> None:
    # PF7: the README is the release's, its links absolute and its sections
    # the release's set, so the serve section, its command and "Pre-release" move to serve's own page,
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
CELL_INDEX_RE = re.compile(r'(<script type="application/json" id="prove-cells">)(.*)(</script>)')
#: PF4 (PF4.12, PF4.15, PF4.18): the regions whose numbers PF4 moves, not only their words: on the
#: lattice pairs the fault lines' group p and q (Westfall-Young on one scale),
#: and on those pairs and the traded pair (whose t0 fail arm fails every run) the detection limits of the conditions at a
#: 100% baseline with the leaf rows, cell index and worst-cells rows that carry them.
#: PF4.22 to PF4.27, PF4.34 to PF4.47: every pair's detection limits move (the exact
#: power at the lone-change level, both directions, null with a reason), its group limits move
#: (PF4.45), its intervals are always there (PF4.42) and every cell gains the new keys, so on every
#: pair the Honesty, Fault lines, Cells, Cell and Worst cells regions are checked by their facts
#: against the payload and the library's frame (assert_region_facts).
FACT_REGIONS = ("Honesty", "Fault lines", "Cells", "Cell", "Worst cells")


def same_number(got: Any, want: Any) -> bool:
    """A JSON number against the library's float: equal, or null where the library holds NaN."""
    want = float(want)
    return got is None if want != want else got == want


def assert_region_facts(p: Pair, heading: str) -> None:
    """PF4 (PF4.12, PF4.15, PF4.18, PF4.20): a region whose numbers PF4 moved, read against the
    payload and the library's frame on the same pair."""
    lines = region_lines(p.page, heading)
    text = "\n".join(lines)
    assert not JUDGEMENT_RE.search(unescape(text)) and "nan" not in unescape(text).lower().split(), (p.name, heading)
    tree = p.structure["tree"]
    if heading == "Fault lines":
        groups = tree["fault_lines"]["groups"]
        [table] = [table_of(line) for line in lines if line.startswith("<table>")]
        header, rows = table
        assert len(rows) == len(groups), (p.name, len(rows))
        # PF4.45: every pair's group limits move, so each row is read column by
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
            # PF4.45: the group limits use each cell's own baseline and the
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
        # PF4.22, PF4.27, PF4.42: each panel's honesty block is the payload's
        # honesty text, and the intervals line is at 1 - q max(R, 1) / M, with R the flagged rows and
        # M the rows of the comparison.
        # PF4.27: no text prints a number for a null limit, so no "nanpp".
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
            # PF4.22 to PF4.27: the region is read by its facts on every pair,
            # some of whose roots do not reject; then it is one sentence and no table.
            assert len(paragraphs) == 1 and paragraphs[0].startswith("not tested") and not tables, (p.name, paragraphs)
            return
        assert len(paragraphs) == 2 + len(leaves["families"]), (p.name, paragraphs[2 + len(leaves["families"]) :])
        rejecting = [f for f in leaves["families"] if f["n_rejected"] > 0]
        assert len(tables) == len(rejecting), p.name
        for line, family in zip(paragraphs[2:], leaves["families"], strict=True):
            assert line.startswith(f"{family['key']}={family['label']}: {family['n_tests']} tests, {family['n_rejected']} rejected"), (p.name, line)
            # PF4.27: a family whose limits are all null prints no number for them.
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
                    # PF4.27: a null limit is printed as its reason in words.
                    assert any(note in row[4] for note in NOTES) and not NUMBER_RE.search(row[4]), (p.name, row)
                else:
                    assert row[4] == f"{leaf['text']['mde']}pp", (p.name, row)
        return
    records = {(e, str(r["config_hash"])): r for e in p.events for r in p.multi.by_event[e].cells.to_dict(orient="records")}
    if heading == "Cell":
        [line] = [line for line in lines if CELL_INDEX_RE.fullmatch(line)]
        index = json.loads(CELL_INDEX_RE.fullmatch(line).group(2))  # type: ignore[union-attr]
        # Read on every pair: under --fix the index holds the slice the page
        # shows (the panels' cells), each a row of the comparison.
        shown = {(panel["event"], str(c["config_hash"])) for panel in p.structure["panels"] for c in panel["cells"]}
        assert {(key.rsplit(" ", 1)[0], entry["config_hash"]) for key, entry in index.items()} == shown <= set(records), p.name
        for key, entry in index.items():
            record = records[(key.rsplit(" ", 1)[0], entry["config_hash"])]
            for field in ("n_a", "n_b", "events_a", "events_b"):
                assert entry[field] == int(record[field]), (p.name, key, field)
            for field in ("rate_a", "rate_b", "delta", "p", "q", "mde"):
                assert same_number(entry[field], record[field]), (p.name, key, field)
            # PF4.20, kindless events: the library's verdict is the direction word too.
            assert entry["verdict"] == entry["direction"] == str(record["verdict"]), (p.name, key)
            if entry["mde"] is None:
                # PF4 (PF4.15): no detection limit; the entry carries the note that says why. Its
                # ``text`` keeps M7's formatting of the raw value (M13 V16), so the note is what a
                # reader is shown, not the text entry.
                assert isinstance(entry["mde_note"], str) and entry["mde_note"], (p.name, key)
            else:
                assert entry["text"]["mde"] == m7_form(entry["mde"], "pp0"), (p.name, key, entry["text"])
        return
    if heading == "Worst cells":
        tables = [table_of(line) for line in lines if line.startswith("<table>")]
        assert len(tables) == len(p.structure["panels"]), p.name
        for (header, rows), panel in zip(tables, p.structure["panels"], strict=True):
            assert (header, rows) == (panel["worst_header"], panel["worst_rows"]), (p.name, panel["event"])
            verdict, mde = header.index("verdict"), header.index("MDE")
            for row, h in zip(rows, panel["worst_hashes"], strict=True):
                record = records[(panel["event"], h)]
                # PF4.20, kindless events: the library's verdict is the direction word too.
                assert row[verdict] == str(record["verdict"]), (p.name, row)
                if isinstance(record["mde_note"], str):
                    assert not re.search(r"\d+pp", row[mde]), (p.name, row)
                else:
                    assert row[mde] == f"{m7_form(record['mde'], 'pp0')}pp", (p.name, row)
        return
    raise AssertionError((p.name, heading))


def test_ls19_every_heading_is_still_on_the_page_and_the_untouched_regions_carry_their_facts(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        assert set(h2_sequence(p.page)) == DISPATCH_H2, p.name
        assert_page_names(p.page)
        for heading in UNTOUCHED_REGIONS:
            if heading in FACT_REGIONS:
                assert_region_facts(p, heading)
            elif heading == "Not verified":
                assert_not_verified(p)
            elif p.name in LATTICE_PAIRS:
                assert_lattice_region(p, heading)
            else:
                assert_builder_region(p, heading)


def test_ls19_the_summary_introduces_no_number_the_statistics_view_does_not_carry(all_pairs: list[Pair]) -> None:
    for p in all_pairs:
        lines = p.page.splitlines()
        marks = h2_lines(p.page)
        rest = html_mod.unescape("\n".join(lines[: marks[0][0]] + lines[marks[1][0] :]))
        # PF4.44: the verdict block's detail lines carry facts only the verdict block
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
