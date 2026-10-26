"""The terminal app's screens: what each shows of the core object it renders (section 19).

Each builder takes the document of one core object (a view's ``to_json()``, the sweep's plan, a
comparison the store could not save) and lays it out for one width as the design draws it: the
verdict line first, then its ``label  value`` detail lines in the command's order, then the one
table, then a second block (an event log, links). Every fact the object carries is on its screen
: a field the design gives a place has it, and a field it does not is listed under ``also
recorded`` in plain words, as the static UI's pages do. Numbers, times and conditions are spelled
by the shared look (``_look``); nothing here computes a statistic, a verdict or a limit.

The app (``_cli_app``) draws a :class:`Page` in its six bands and handles the keys.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from poisson_prove import _look
from poisson_prove._render_term import meaning_of

__all__: list[str] = []

COMMAND = "poisson-prove"
#: The width at which a screen shows its wide layout (the design's 120-column drawings).
WIDE = 120


# ---------- what a screen is made of ----------


@dataclass
class Line:
    """One line of a screen's body: its text (from column 1), its styled spans (``green``,
    ``yellow``, ``red``, ``bold``, ``dim``), and what it does: a link opens a page of the static UI
    (``link`` is its address inside the UI), ``copy`` is what ``y`` copies, ``opens`` what Enter on
    a table row does. ``code`` marks a command or code line, never cut (it wraps at spaces only)."""

    text: str
    spans: list[tuple[int, int, str]] = field(default_factory=list)
    link: str | None = None
    copy: str | None = None
    opens: Callable[[], None] | None = None
    code: bool = False
    #: The column a wrapped line continues at; ``None``: under a ``label  value`` line's value.
    hang: int | None = None
    #: What a table row stands for (a run, an episode, an event), for the screen's own keys.
    data: Any = None


@dataclass
class Page:
    """One screen: its title and subject, the lines above its table (they never scroll), the
    table's header and rows (the focus moves over them), and the lines below; its keys for the key
    bar; the message line. ``layout`` (re)builds the lines for a width; ``on_key`` takes the
    screen's own letters."""

    title: str
    subject: str = ""
    top: list[Line] = field(default_factory=list)
    header: Line | None = None
    rows: list[Line] = field(default_factory=list)
    bottom: list[Line] = field(default_factory=list)
    keys: list[tuple[str, str]] = field(default_factory=list)
    message: str = ""
    #: The message is the screen's own state (a refusal), kept until the screen is left.
    keep_message: bool = False
    focus: int = 0
    in_links: bool = False
    offset: int = 0
    #: The second block's lines with no room above the table, shown by ``m``.
    more: list[Line] = field(default_factory=list)
    #: A second block shown only behind a key at this width (the run's event log at 80 columns).
    second: list[Line] = field(default_factory=list)
    show_more: bool = False
    show_second: bool = False
    #: Help: the rows are text the keys scroll, and nothing has the focus.
    scroll_only: bool = False
    #: The lines below the table keep their rows (the verdict's chart links at 80 columns).
    keep_bottom: bool = False
    layout: Callable[[int], None] | None = None
    #: The width ``layout`` last laid the page out for.
    laid_width: int = 0
    on_key: Callable[[str], bool] | None = None
    on_focus: Callable[[], None] | None = None
    #: The filter (``/``) on the table's rows: being typed, and its text.
    filtering: bool = False
    filter: str = ""
    #: The focus the table or the links had when ``Tab`` moved it to the other.
    other_focus: int = 0
    #: The document the screen renders.
    view: dict[str, Any] | None = None

    def links(self) -> list[Line]:
        return [line for line in [*self.top, *self.bottom] if line.link]

    def visible_rows(self) -> list[Line]:
        """The table's rows as shown: those the filter (``/``) matches."""
        if not self.filter:
            return self.rows
        needle = self.filter.lower()
        return [r for r in self.rows if needle in r.text.lower()]

    def table_row(self) -> Line | None:
        """The table row the focus is on, or was on before ``Tab`` moved it to the links: the row
        the links follow."""
        rows = self.visible_rows()
        if not rows:
            return None
        return rows[min(self.other_focus if self.in_links else self.focus, len(rows) - 1)]

    def focused_row(self) -> Line | None:
        """The table row with the focus, when a row has it."""
        rows = self.visible_rows()
        if not rows or self.in_links:
            return None
        return rows[min(self.focus, len(rows) - 1)]


def verdict_line(word: str, sentence: str) -> Line:
    """``  word  sentence``, the word in its meaning's style (section 5.5)."""
    return Line(f"  {word}  {sentence}", [(2, 2 + len(word), meaning_of(word))])


@dataclass
class Detail:
    label: str
    value: str
    link: str | None = None
    code: bool = False


def block(details: Sequence[Detail | None]) -> list[Line]:
    """``label  value`` lines, the labels dim and padded to one column."""
    shown = [d for d in details if d is not None]
    if not shown:
        return []
    width = max(len(d.label) for d in shown)
    out = []
    for d in shown:
        text = f"  {d.label.ljust(width)}  {d.value}"
        copy = d.value if d.code and d.link is None else None
        out.append(
            Line(
                text,
                [(2, 2 + len(d.label), "dim")],
                link=d.link,
                copy=copy,
                code=d.code or d.link is not None,
                hang=width + 4,
            )
        )
    return out


def wrap_line(line: Line, w: int, focused: bool) -> list[tuple[Line, bool]]:
    """A body line on rows of ``w``: a ``label  value`` line wraps under its value; a command or
    code line that does not fit starts at column 1 on the rows below its label, broken only at
    spaces; other text wraps two deeper than it starts."""
    if len(line.text) <= w:
        return [(line, focused)]
    m = re.match(r"^(  \S(?:[^ ]| (?! ))*  +)", line.text)
    if line.code:
        label = m.group(1).rstrip() if m else ""
        rest = line.text[len(m.group(1)) :] if m else line.text.lstrip(" ")
        rows = [Line(label, line.spans, line.link, line.copy, line.opens, True)] if label else []
        chunk = ""
        for word in rest.split(" "):
            if chunk and len(chunk) + 1 + len(word) > w:
                rows.append(Line(chunk, [], line.link, line.copy, line.opens, True))
                chunk = word
            else:
                chunk = f"{chunk} {word}" if chunk else word
        rows.append(Line(chunk, [], line.link, line.copy, line.opens, True))
        return [(r, focused) for r in rows]
    if line.hang is not None and line.hang < w // 2:
        hang = line.hang
    elif m and len(m.group(1)) < w // 2:
        hang = len(m.group(1))
    else:
        hang = len(line.text) - len(line.text.lstrip(" ")) + 2
    parts, rest, first = [], line.text, True
    while len(rest) > w:
        cut = rest.rfind(" ", hang + 1, w + 1)
        if cut <= hang:
            cut = w
        parts.append(
            Line(rest[:cut].rstrip(), line.spans if first else [], line.link, line.copy, line.opens)
        )
        rest = " " * hang + rest[cut:].lstrip(" ")
        first = False
    parts.append(Line(rest, [], line.link, line.copy, line.opens))
    return [(p, focused) for p in parts]


def code_line(text: str) -> Line:
    return Line(f"  {text}", code=True, copy=text)


def text_line(text: str, style: str = "") -> Line:
    line = f"  {text}"
    return Line(line, [(2, len(line), style)] if style else [])


BLANK = Line("")


# ---------- the look's words for a view's values ----------


def rate(value: Any) -> str:
    return "none" if value is None else _look.fmt_rate(value)


def pv(value: Any) -> str:
    return "none" if value is None else _look.fmt_p(value)


def count(value: Any) -> str:
    return "none" if value is None else _look.fmt_count(value)


def num(value: Any) -> str:
    return "none" if value is None else _look.fmt_num(value)


def signed(value: Any) -> str:
    return _look.fmt_signed(value)


def level(value: Any) -> str:
    return "none" if value is None else _look.level_label(float(value))


def interval(value: Any, lo: Any, hi: Any) -> str:
    return f"{rate(value)} [{rate(lo)}, {rate(hi)}]"


def limit(value: Any, note: Any) -> str:
    """A detection limit to three decimals, or its reason when it has none."""
    return rate(value) if value is not None else str(note or "none")


def axes_of(config: Mapping[str, Any]) -> str:
    return " · ".join(str(k) for k in config)


def values_of(config: Mapping[str, Any]) -> str:
    """A condition's values alone, ``refund · 0.55``, for a table whose header names the axes."""
    words = _look.condition_words(config).split(" · ")
    return " · ".join(w.split(" ", 1)[1] if " " in w else w for w in words)


def condition(config: Mapping[str, Any]) -> str:
    return _look.condition_words(config)


def short(name: str) -> str:
    """A comparison's name, ``<before> → <after>``, with the words both runs' names start with
    written once: ``mock-agent 2026-10-23 a → b``."""
    before, sep, after = name.partition(" → ")
    if not sep:
        return name
    a, b = before.split(" "), after.split(" ")
    shared = 0
    while shared < min(len(a), len(b)) - 1 and a[shared] == b[shared]:
        shared += 1
    return f"{before} → {' '.join(b[shared:])}" if shared else name


def when(value: Any) -> str:
    return _look.fmt_time(value, minute=True)


def words_of(key: str) -> str:
    return key.replace("_", " ")


def value_words(value: Any) -> str:
    """A value with no place of its own, in plain words."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return _look.fmt_num(value)
    if isinstance(value, Mapping):
        return " · ".join(f"{words_of(str(k))} {value_words(v)}" for k, v in value.items())
    if isinstance(value, list):
        return " · ".join(value_words(v) for v in value) if value else "none"
    return _look.fmt_time(value)


#: The UI's own addresses and drawings: shown by their links, never as text (section 16.1).
_NOT_TEXT = ("schema", "view", "address", "svg")


def also_recorded(doc: Mapping[str, Any], known: set[str]) -> list[Line]:
    """The document's fields the screen's design gives no place, in plain words."""
    rest = [
        Detail(words_of(k), value_words(v))
        for k, v in doc.items()
        if k not in known and k not in _NOT_TEXT and not k.endswith("address")
    ]
    return [BLANK, text_line("also recorded", "dim"), *block(rest)] if rest else []


_TESTS = {"mcnemar": "McNemar", "fisher": "Fisher"}


def _plural(n: Any, word: str) -> str:
    return f"{count(n)} {word}{'' if n == 1 else 's'}"


def design_lines(design: Mapping[str, Any] | None, sentence: str | None) -> list[Detail]:
    """Section 8.10's design limit: its sentence, then the facts it rests on."""
    if not isinstance(design, Mapping):
        return [Detail("design", sentence)] if sentence else []
    out = [Detail("design", sentence)] if sentence else []
    test = _TESTS.get(str(design.get("test")), str(design.get("test")))
    facts = [
        f"{rate(design.get('mde'))} for a {design.get('direction')} from "
        f"{rate(design.get('base_rate'))}",
        f"{test} at the level {pv(design.get('level'))} per test",
        f"q {num(design.get('q'))} over a family of {count(design.get('family'))}"
        f" ({count(design.get('conditions'))} conditions × "
        f"{_plural(design.get('events'), 'event')})",
        f"power {rate(design.get('power'))}",
    ]
    if design.get("flaggable") is False:
        facts.append("no lone condition can be flagged")
    if design.get("computed_at_read_time"):
        facts.append("computed now: the run did not record it")
    out.append(Detail("" if sentence else "design", "; ".join(facts)))
    return out


# ---------- tables ----------


@dataclass
class Column:
    name: str
    right: bool = False
    #: Dropped when the window is narrow, the highest first; ``None``: never dropped.
    drop: int | None = None
    #: Shown only at the wide layout (``WIDE`` columns and up).
    wide: bool = False
    #: A name, cut in the middle with ``…`` when the table is too wide; its whole form is on the
    #: screen the row opens.
    cut: bool = False
    #: The style a cell's first word is drawn in, from the cell (a verdict's meaning).
    style: Callable[[str], str] | None = None


def lay_table(
    columns: Sequence[Column], cells: Sequence[Sequence[str]], width: int
) -> tuple[Line, list[Line]]:
    """The header and rows of a table laid out for ``width``. The columns keep one order; those
    marked ``wide`` show only at the wide layout, and below it the ``drop`` columns go, highest
    first, until the table fits. Still too wide, a name column (``cut``) is cut in the middle
    with ``…``, the widest first, then the columns close to one space apart and the names are cut
    further; a condition, a number or a note is never cut."""
    keep = [i for i, c in enumerate(columns) if not (c.wide and width < WIDE)]
    ws = {i: max([len(columns[i].name)] + [len(r[i]) for r in cells]) for i in range(len(columns))}
    gap = 2

    def total() -> int:
        return 2 + sum(ws[i] for i in keep) + gap * (len(keep) - 1)

    if width < WIDE:
        droppable = sorted(
            (i for i in keep if columns[i].drop is not None), key=lambda i: -(columns[i].drop or 0)
        )
        for i in droppable:
            if total() <= width:
                break
            keep.remove(i)
    for closer in (False, True):
        if closer and total() > width:
            gap = 1
        cuttable = [i for i in keep if columns[i].cut]
        while total() > width and cuttable:  # a character at a time from the widest name
            i = max(cuttable, key=lambda i: ws[i])
            if ws[i] <= max(12, len(columns[i].name)):
                cuttable.remove(i)
                continue
            ws[i] -= 1

    def cut(text: str, w: int) -> str:
        if len(text) <= w:
            return text
        head = (w - 1) // 2
        return text[:head] + "…" + text[len(text) - (w - 1 - head) :]

    def laid(values: Sequence[str], styled: bool) -> Line:
        parts, spans, at = [], [], 2
        for i in keep:
            cell = cut(values[i], ws[i]) if columns[i].cut else values[i]
            shown = cell.rjust(ws[i]) if columns[i].right else cell.ljust(ws[i])
            style = columns[i].style
            if styled and style is not None and cell.strip():
                word = cell.split(",", 1)[0].strip()
                start = at + shown.index(word)
                spans.append((start, start + len(word), style(word)))
            parts.append(shown)
            at += len(shown) + gap
        return Line(("  " + (" " * gap).join(parts)).rstrip(), [s for s in spans if s[2]])

    head = laid([c.name for c in columns], False)
    head.spans = [(2, len(head.text), "dim")]
    return head, [laid(r, True) for r in cells]


def verdict_style(word: str) -> str:
    """A verdict word's style in a table cell: its meaning's colour, or bold for a result
    (section 5.5); a run's status yellow when it stopped short."""
    if word == "partial":
        return "yellow"
    if word in ("complete", ""):
        return ""
    return meaning_of(word)


# ---------- keys ----------

MOVE = ("↑↓", "move")
OPEN = ("enter", "open")
BACK = ("esc", "back")


# ---------- the screens ----------


class Screens:
    """The builders; the app gives them its store and its moves (open a screen, go back)."""

    store: Any
    shown: str

    # what the app provides
    def push(self, page: Page) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    def replace(self, page: Page) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    def pop(self) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    def width(self) -> int:  # pragma: no cover - the app's
        raise NotImplementedError

    def ui_page(self, address: str) -> bool:  # pragma: no cover - the app's
        """Whether the UI's page at ``address`` exists, the UI refreshed first."""
        raise NotImplementedError

    def open_run(self, run_id: str) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    def open_episodes(
        self, run_id: str, event: str, condition_hash: str, address: str | None
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    def open_saved(self, cid: str) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    def open_compare(self, after: str | None = None) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    def open_sweep(self) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    # ---------- home ----------

    def home_page(self, doc: dict[str, Any]) -> Page:
        page = Page(
            "home",
            view=doc,
            keys=[
                MOVE,
                OPEN,
                ("tab", "links"),
                ("s", "sweep"),
                ("c", "compare"),
                ("r", "runs"),
                ("y", "copy"),
            ],
        )

        def layout(width: int) -> None:
            page.top = [verdict_line(doc["verdict"], doc["sentence"]), BLANK]
            latest, compared = doc.get("latest_run"), doc.get("latest_comparison")
            details: list[Detail | None] = []
            if isinstance(latest, Mapping):
                paired = (
                    f', paired with "{latest["paired_with"]}"' if latest.get("paired_with") else ""
                )
                details.append(Detail("latest", f"{latest['name']} ({latest['status']}{paired})"))
            if isinstance(compared, Mapping):
                limit_words = (
                    f", limit {rate(compared['limit'])}"
                    if compared.get("limit") is not None
                    else ""
                )
                details.append(
                    Detail(
                        "compared", f"{short(compared['name'])}: {compared['verdict']}{limit_words}"
                    )
                )
            details += [Detail("next", c, code=True) for c in doc.get("next", [])]
            if doc.get("n_runs") and self.ui_page(str(doc.get("ui", "index.html"))):
                details.append(Detail("dashboard", str(doc["ui"]), link=str(doc["ui"])))
            page.top += block(details)
            items = list(doc.get("items", []))
            page.bottom = also_recorded(doc, _HOME_KNOWN)
            if not items:
                page.header, page.rows = None, []
                return
            page.top.append(BLANK)
            cells = [
                [
                    str(i["kind"]),
                    short(str(i["name"])),
                    str(i["result"])
                    + (f", limit {rate(i['limit'])}" if i.get("limit") is not None else ""),
                    "" if i.get("rows") is None else count(i["rows"]),
                    str(i["id"]),
                    when(i["created"]),
                ]
                for i in items
            ]
            columns = [
                Column("kind"),
                Column("name", cut=True),
                Column("result", style=verdict_style),
                Column("rows", right=True),
                Column("id", wide=True),
                Column("created"),
            ]
            page.header, page.rows = lay_table(columns, cells, width)
            for line, item in zip(page.rows, items, strict=True):
                if item["kind"] == "comparison":
                    line.opens = lambda item=item: self.open_saved(str(item["id"]))
                else:
                    line.opens = lambda item=item: self.open_run(str(item["id"]))

        page.layout = layout

        def keys(ch: str) -> bool:
            if ch == "r":
                self.push(self.runs_page())
            elif ch == "c":
                self.open_compare()
            elif ch == "s":
                self.open_sweep()
            else:
                return False
            return True

        page.on_key = keys
        return page

    # ---------- runs ----------

    def runs_view(self) -> dict[str, Any]:
        from poisson_prove import core

        return dict(core.view(self.store, "index.html").to_json())

    def runs_page(self) -> Page:
        from poisson_prove import core

        page = Page("runs", keys=[MOVE, OPEN, BACK, ("/", "filter"), ("c", "compare")])
        try:
            doc = self.runs_view()
        except core.Refusal as exc:
            return self.refused(page, exc)
        page.view = doc
        runs = list(doc["runs"])

        def layout(width: int) -> None:
            page.top = [verdict_line(doc["verdict"], doc["sentence"]), BLANK]
            if not runs:
                first = str(doc.get("first_run", "")).splitlines()
                page.top += block([Detail("next", c, code=True) for c in first])
            cells = [_run_cells(r, with_outcome=True) for r in runs]
            page.header, page.rows = lay_table(_RUN_COLUMNS, cells, width) if runs else (None, [])
            for line, r in zip(page.rows, runs, strict=True):
                line.data = r
                line.opens = lambda r=r: self.open_run(str(r["run_id"]))
            page.bottom = []
            comparisons = list(doc.get("comparisons", []))
            if comparisons:
                page.bottom = [BLANK, text_line("saved comparisons", "dim")]
                page.bottom += block(
                    [
                        Detail(
                            "compared",
                            f"{short(str(c['name']))}: {c['verdict']}, by {c['method']}, saved "
                            f"{when(c['saved_at'])} "
                            f"({_look.fmt_hash(c['id'])})",
                        )
                        for c in comparisons
                    ]
                )
            elif doc.get("no_comparison"):
                page.bottom = [BLANK, *block([Detail("compared", str(doc["no_comparison"]))])]
            page.bottom += also_recorded(doc, _RUNS_KNOWN)

        page.layout = layout

        def keys(ch: str) -> bool:
            if ch == "s":
                self.open_sweep()
                return True
            if ch != "c":
                return False
            row = page.focused_row()
            self.open_compare(after=str(row.data["run_id"]) if row is not None else None)
            return True

        page.on_key = keys
        return page

    def refused(self, page: Page, exc: Any) -> Page:
        """A refusal on the screen: the command's ``error:`` line on the message line,
        its ``next`` commands, and the whole sentence when the window cannot hold it."""
        sentence = str(exc)
        page.message = f"error: {sentence}"
        page.keep_message = True
        page.view = None
        nexts = list(getattr(exc, "next", []) or [])
        notes = list(getattr(exc, "notes", []) or [])

        def layout(width: int) -> None:
            page.top = block([Detail("note", str(n)) for n in notes])
            if len(page.message) > width:
                page.top += [*block([Detail("error", sentence)]), BLANK]
            page.top += block([Detail("next", c, code=True) for c in nexts])
            page.header, page.rows, page.bottom = None, [], []

        page.layout = layout
        return page

    # ---------- run ----------

    def run_page(self, doc: dict[str, Any]) -> Page:
        page = Page(
            "run",
            str(doc["name"]),
            view=doc,
            keys=[MOVE, OPEN, BACK, ("g", "event log"), ("tab", "link"), ("y", "copy")],
        )
        cells = list(doc.get("cells", []))
        outcomes = list(doc.get("outcomes") or [])
        for c in cells:
            outcomes += [o for o in c["shares"] if o not in outcomes]
        declared = doc.get("declared")
        failures = list(declared.get("failures") or []) if isinstance(declared, Mapping) else []

        def layout(width: int) -> None:
            page.top = [verdict_line(doc["verdict"], doc["sentence"]), BLANK]
            details: list[Detail | None] = [
                Detail("id", str(doc["run_id"])),
                Detail(
                    "status",
                    f"{doc['status']}: {count(doc['done'])} of {count(doc['total'])} rollouts, "
                    f"created {_look.fmt_time(doc['created_at'])}",
                ),
                Detail("target", f"{doc['target']}, backend {doc['backend']}"),
                Detail(
                    "paired with",
                    f'"{doc["paired_with_name"]}" (shared seeds)'
                    if doc.get("paired_with_name")
                    else "not recorded"
                    if doc.get("paired_with") is None
                    else str(doc["paired_with"]),
                ),
                Detail(
                    "outcomes",
                    " · ".join(outcomes)
                    + (
                        f"; failures declared: {', '.join(failures)}"
                        if failures
                        else "; no failure declared"
                    ),
                ),
                *design_lines(doc.get("design_mde"), doc.get("design")),
            ]
            address = str(doc.get("address", ""))
            if address and self.ui_page(address):
                details.append(Detail("page", address, link=address))
            # what the design's run screen does not draw comes last: at 80 columns it is the
            # first to go behind ``m``
            axes = " × ".join(f"{k} {v}" for k, v in (doc.get("axes") or {}).items())
            details += [
                Detail(
                    "conditions",
                    f"{count(doc['conditions'])} ({axes}), {count(doc.get('replicates'))} "
                    "replicates each",
                ),
                Detail(
                    "t", f"in {words_of(str(doc.get('t_unit')))}, horizon {num(doc.get('horizon'))}"
                ),
                *[
                    Detail(
                        "compared",
                        f"{short(str(c['name']))}: {c['verdict']} ({_look.fmt_hash(c['id'])})",
                    )
                    for c in doc.get("comparisons") or []
                ],
            ]
            page.top += block(details)
            page.top.append(BLANK)
            shown = (
                outcomes
                if width >= WIDE
                else (failures or [o for o in outcomes if o != _commonest(cells)])[:2]
            )
            lvl = next(
                (
                    s["level"]
                    for c in cells
                    for s in c["shares"].values()
                    if s.get("level") is not None
                ),
                None,
            )
            tag = f" [{level(lvl)}]" if lvl is not None else ""
            columns = [
                Column(axes_of(cells[0]["config"]) if cells else "condition"),
                Column("episodes", right=True, wide=True),
            ]
            columns += [Column(f"{o}{tag}") for o in shown]
            rows = []
            for c in cells:
                row = [values_of(c["config"]), count(c["n"])]
                for o in shown:
                    s = c["shares"].get(o)
                    row.append(interval(s["value"], s["lo"], s["hi"]) if s else "none")
                rows.append(row)
            page.header, page.rows = lay_table(columns, rows, width) if cells else (None, [])
            first = next((o for o in failures if o in outcomes), None) or _not_commonest(
                cells, outcomes
            )
            for line, c in zip(page.rows, cells, strict=True):
                share = c["shares"].get(first, {}) if first else {}
                line.opens = lambda c=c, share=share: self.open_episodes(
                    str(doc["run_id"]), str(first), str(c["condition_hash"]), share.get("address")
                )
            page.bottom = []
            if doc.get("shares_rule"):
                page.bottom.append(text_line(str(doc["shares_rule"]), "dim"))
            log = [BLANK, text_line("event log", "dim")]
            events = doc.get("events")
            if isinstance(events, list):
                kinds = max((len(str(e["kind"])) for e in events), default=0)
                for e in events:
                    detail = " · ".join(
                        f"{words_of(str(k))} {value_words(v)}"
                        for k, v in (e.get("detail") or {}).items()
                    )
                    when_, kind = _look.fmt_clock(e["at"]), str(e["kind"]).ljust(kinds)
                    log.append(Line(f"  {when_}  {kind}  {detail}".rstrip()))
            else:
                log += block([Detail("events", str(doc.get("events_note") or "not recorded"))])
            if width >= WIDE:
                page.bottom += log
                page.second = []
            else:  # behind ``g`` at 80 columns, shown in place of the table
                page.second = log
            page.bottom += also_recorded(doc, _RUN_KNOWN)

        page.layout = layout

        def keys(ch: str) -> bool:
            if ch != "g":
                return False
            page.show_second = not page.show_second and bool(page.second)
            return True

        page.on_key = keys
        return page

    # ---------- episodes ----------

    def episodes_page(
        self,
        doc: dict[str, Any],
        reproduce: Mapping[str, Any] | None,
        next_event: Callable[[], None],
    ) -> Page:
        page = Page(
            "episodes",
            str(doc.get("run", doc.get("run_name", ""))),
            view=doc,
            keys=[MOVE, BACK, ("/", "filter"), ("e", "next event"), ("y", "copy")],
        )
        episodes = list(doc.get("episodes", []))
        #: The reproduce lines ``inspect`` prints, for the focused episode (the app shows the
        #: import line too, since it is local).
        code = [
            Line("  # reproduce one episode", [(2, 25, "dim")]),
            Line("", code=True),
            Line("", code=True),
        ]

        def follow() -> None:
            row = page.focused_row()
            if reproduce is None or row is None:
                return
            e = row.data
            config = e.get("config") or doc.get("condition") or {}
            lines = [
                f"from {reproduce['module']} import {reproduce['function']}",
                f"{reproduce['function']}({json.dumps(config, sort_keys=True)}, seed={e['seed']})",
            ]
            for line, text in zip(code[1:], lines, strict=True):
                line.text, line.copy = f"  {text}", "\n".join(lines)

        def layout(width: int) -> None:
            page.top = [verdict_line(doc["verdict"], doc["sentence"]), BLANK]
            where = doc.get("condition")
            if isinstance(where, Mapping):
                place = condition(where)
            else:
                first = next((e.get("config") for e in episodes if e.get("config")), None)
                place = (
                    f"{condition(first)} ({_look.fmt_hash(where)})"
                    if first
                    else _look.fmt_hash(where)
                )
            details: list[Detail | None] = [
                Detail("condition", place),
                Detail("run", f"{doc.get('run', doc.get('run_name'))} ({doc.get('run_id')})"),
                Detail("event", str(doc.get("event"))),
            ]
            comparisons = doc.get("comparisons")
            if isinstance(comparisons, list):
                details += [
                    Detail("compared in", f"comparison {_look.fmt_hash(c['id'])}")
                    for c in comparisons
                ]
            if "total" in doc:
                shown_to = int(doc.get("offset", 0)) + len(episodes)
                more = f"; more from {count(doc['next'])}" if doc.get("next") else ""
                details.append(
                    Detail(
                        "rows",
                        f"{count(doc.get('offset', 0) + 1 if episodes else 0)} to "
                        f"{count(shown_to)} of {count(doc['total'])}{more}",
                    )
                )
            address = str(doc.get("address", ""))
            if address and self.ui_page(address):
                details.append(Detail("page", address, link=address))
            page.top += block(details)
            page.top.append(BLANK)
            if reproduce is not None and episodes:
                page.top += [*code, BLANK]  # filled for the focused row below
            cells = [
                [
                    count(e["replicate_index"]),
                    str(e["seed"]),
                    str(e.get("outcome") or "none"),
                    num(e.get("t")),
                ]
                for e in episodes
            ]
            columns = [
                Column("replicate", right=True),
                Column("seed", right=True),
                Column("outcome"),
                Column("t", right=True),
            ]
            page.header, page.rows = lay_table(columns, cells, width)  # the columns, rows or none
            for line, e in zip(page.rows, episodes, strict=True):
                line.data = e
                if e.get("error"):
                    line.text += f"  error: {e['error']}"
            follow()
            page.bottom = []
            if doc.get("empty") and not episodes:
                page.bottom.append(text_line(str(doc["empty"])))
            if isinstance(doc.get("reproduce"), str):
                page.bottom.append(text_line(str(doc["reproduce"]), "dim"))
            page.bottom += also_recorded(doc, _EPISODES_KNOWN)

        page.layout = layout
        page.on_focus = follow

        def keys(ch: str) -> bool:
            if ch == "e":
                next_event()
                return True
            return False

        page.on_key = keys
        return page

    # ---------- compare ----------

    def compare_page(
        self, doc: dict[str, Any], chosen: dict[str, str | None], on_compare: Callable[[], None]
    ) -> Page:
        page = Page(
            "compare",
            "pick two runs",
            view=doc,
            keys=[
                MOVE,
                ("enter", "compare"),
                BACK,
                ("space", "choose"),
                ("l", "previous and latest"),
            ],
        )
        runs = list(doc.get("runs", []))
        names = {str(r["run_id"]): str(r["name"]) for r in runs}
        complete = [str(r["run_id"]) for r in runs if r["status"] == "complete"]
        turn = ["before"]

        def latest() -> None:
            chosen["after"] = complete[0] if complete else None
            chosen["before"] = complete[1] if len(complete) > 1 else None
            turn[0] = "before"

        if "after" not in chosen:
            latest()

        def layout(width: int) -> None:
            page.top = block(
                [
                    Detail("before", names.get(chosen.get("before") or "", "none chosen")),
                    Detail("after", names.get(chosen.get("after") or "", "none chosen")),
                ]
            )
            if len(complete) < 2:
                page.top += block(
                    [
                        Detail("compare", "a comparison takes two complete runs"),
                        Detail("next", f"{COMMAND} sweep", code=True),
                    ]
                )
            page.top.append(BLANK)
            mark = {chosen.get("before"): "before", chosen.get("after"): "after"}
            cells = [
                [mark.get(str(r["run_id"]), ""), *_run_cells(r, with_outcome=False)] for r in runs
            ]
            page.header, page.rows = (
                lay_table(
                    [Column(""), *[c for c in _RUN_COLUMNS if c.name != "no outcome"]], cells, width
                )
                if runs
                else (None, [])
            )
            for line, r in zip(page.rows, runs, strict=True):
                line.data, line.opens = r, on_compare
            page.bottom = []

        page.layout = layout

        def keys(ch: str) -> bool:
            if ch == "l":
                latest()
            elif ch == " ":
                row = page.focused_row()
                if row is None:
                    return True
                r = row.data
                other = "after" if turn[0] == "before" else "before"
                if r["status"] != "complete":
                    page.message = (
                        f'error: "{r["name"]}" is {r["status"]}; a comparison takes complete runs'
                    )
                    return True
                if chosen.get(other) == str(r["run_id"]):
                    # a run is never compared with itself: choose the other again
                    chosen[other] = None
                chosen[turn[0]] = str(r["run_id"])
                turn[0] = other
            else:
                return False
            layout(self.width())
            return True

        page.on_key = keys
        return page

    # ---------- the verdict and the conditions (the comparison view's two halves) ----------

    def verdict_page(self, doc: dict[str, Any], *, saved: bool) -> Page:
        """The verdict screen: a saved comparison's view, or the comparison itself when it could not
        be saved (section 18.2)."""
        name = str(doc.get("name") or "")
        page = Page(
            "comparison",
            short(name),
            view=doc,
            keys=[
                MOVE,
                OPEN,
                BACK,
                ("t", "conditions"),
                ("d", "could not detect"),
                ("tab", "links"),
                ("y", "copy"),
            ],
        )
        events = _events_of(doc)
        charts = [c for c in doc.get("charts", []) if saved]

        def layout(width: int) -> None:
            page.top = [
                verdict_line(doc["verdict"], doc["sentence"]),
                BLANK,
                *block(_verdict_block(doc, saved=saved)),
            ]
            page.top.append(BLANK)
            kinds = {e["kind"] is not None for e in events}
            columns = [Column("event"), Column("kind")]
            keys_ = []
            if True in kinds:
                columns += [Column("worse", right=True), Column("safer", right=True)]
                keys_ += ["n_worse", "n_safer"]
            if False in kinds:
                columns += [Column("higher", right=True), Column("lower", right=True)]
                keys_ += ["n_higher", "n_lower"]
            columns.append(Column("unchanged", right=True))
            keys_.append("n_unchanged")
            if saved:  # the could-not-tell count is the saved comparison's (section 8.10)
                columns.append(Column("could not tell", right=True))
                keys_.append("n_could_not_tell")
            columns.append(Column("conditions", right=True, wide=True))
            keys_.append("n_conditions")
            cells = [
                [
                    str(e["name"]),
                    str(e["kind"] or "not declared"),
                    *[count(e.get(k)) for k in keys_],
                ]
                for e in events
            ]
            page.header, page.rows = lay_table(columns, cells, width) if events else (None, [])
            for line, e in zip(page.rows, events, strict=True):
                line.data = e
                line.opens = lambda: self.push(self.conditions_page(doc, saved=saved))
            draw_links(width)

        def draw_links(width: int) -> None:
            page.bottom = [BLANK]
            notes = [f"{e['name']}: {e['kind_note']}" for e in events if e.get("kind_note")]
            if notes:
                page.bottom += block([Detail("kinds", " · ".join(notes))])
            if not saved:
                page.bottom += block([Detail("charts", "not built: the comparison was not saved")])
            elif charts and self.ui_page(str(charts[0]["address"])):
                row = page.table_row()
                focused = str(row.data["name"]) if row is not None and width < WIDE else None
                page.bottom += block(
                    [
                        Detail(
                            f"{c['event']} {c['kind']}" if focused is None else str(c["kind"]),
                            str(c["address"]),
                            link=str(c["address"]),
                        )
                        for c in charts
                        if focused is None or c["event"] == focused
                    ]
                )
            if (
                saved
            ):  # a comparison that was not saved is diff's document: its report holds the rest
                page.bottom += also_recorded(doc, _COMPARISON_KNOWN)

        page.layout = layout
        page.on_focus = lambda: draw_links(self.width())
        page.keep_bottom = True

        def keys(ch: str) -> bool:
            if ch == "t":
                self.push(self.conditions_page(doc, saved=saved))
            elif ch == "d":
                if not saved:
                    page.message = (
                        "note: what it could not detect is a page of the saved comparison, and "
                        "this one was not saved"
                    )
                    return True
                self.open_could_not_detect(str(doc["id"]))
            else:
                return False
            return True

        page.on_key = keys
        return page

    def open_could_not_detect(self, cid: str) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    def open_condition(self, cid: str, address: str) -> None:  # pragma: no cover - the app's
        raise NotImplementedError

    def conditions_page(self, doc: dict[str, Any], *, saved: bool) -> Page:
        page = Page(
            "conditions",
            short(str(doc.get("name") or "")),
            view=doc,
            keys=[MOVE, OPEN, BACK, ("/", "filter"), ("v", "verdict")],
        )
        rows = _rows_of(doc)

        def layout(width: int) -> None:
            first = rows[0]["config"] if rows else {}
            page.top = [verdict_line(doc["verdict"], doc["sentence"]), BLANK]
            page.top += block(
                [
                    Detail(
                        "condition",
                        f"{axes_of(first)}; before and after are each run's share of episodes "
                        "ending in the event",
                    ),
                    None
                    if width >= WIDE
                    else Detail(
                        "limit",
                        "the larger of the row's two limits, rise and fall; both are on the "
                        "condition's screen",
                    ),
                ]
            )
            page.top.append(BLANK)
            wide = width >= WIDE
            columns = [
                Column("condition"),
                Column("event"),
                Column("before [95%]" if wide else "before", right=True),
                Column("after", right=True),
                Column("change", right=True),
                Column("p", right=True, wide=True),
                Column("q", right=True),
                Column("verdict", style=verdict_style),
            ]
            columns += [Column("rise"), Column("fall")] if wide else [Column("limit")]
            cells = []
            for r in rows:
                before = (
                    interval(r["share_a"], r.get("share_a_lo"), r.get("share_a_hi"))
                    if wide
                    else rate(r["share_a"])
                )
                row = [
                    values_of(r["config"]),
                    str(r["event"]),
                    before,
                    rate(r["share_b"]),
                    signed(r["delta"]),
                    pv(r["p"]),
                    pv(r["q"]),
                    str(r["verdict"]),
                ]
                if wide:
                    row += [
                        limit(r["mde_rise"], r.get("mde_rise_note")),
                        limit(r["mde_fall"], r.get("mde_fall_note")),
                    ]
                else:
                    both = [x for x in (r["mde_rise"], r["mde_fall"]) if x is not None]
                    row.append(
                        rate(max(both))
                        if both
                        else str(r.get("mde_rise_note") or r.get("mde_fall_note") or "none")
                    )
                cells.append(row)
            page.header, page.rows = lay_table(columns, cells, width) if rows else (None, [])
            for line, r in zip(page.rows, rows, strict=True):
                if saved and r.get("address"):
                    line.opens = lambda r=r: self.open_condition(
                        str(doc["id"]), str(r["address"]).split("#")[0]
                    )
                else:
                    line.opens = lambda: setattr(
                        page,
                        "message",
                        "note: a condition's screen is a page of the saved comparison, and this "
                        "one was not saved",
                    )
            page.bottom = [BLANK]
            if doc.get("rows_rule"):
                page.bottom.append(text_line(str(doc["rows_rule"]), "dim"))

        page.layout = layout

        def keys(ch: str) -> bool:
            if ch != "v":
                return False
            self.pop()
            return True

        page.on_key = keys
        return page

    # ---------- a condition ----------

    def condition_page(self, doc: dict[str, Any]) -> Page:
        config = doc.get("condition") or {}
        page = Page(
            "condition",
            condition(config),
            view=doc,
            keys=[MOVE, OPEN, BACK, ("e", "other event"), ("tab", "links"), ("y", "copy")],
        )
        blocks = list(doc.get("events", []))
        shown = [0]

        def event_block(b: Mapping[str, Any]) -> list[Line]:
            sa, sb = b["share_a"], b["share_b"]
            ci, test = b.get("ci") or {}, b.get("test") or {}
            k, n = b.get("k") or {}, b.get("n") or {}
            pairs = (
                f"{count(test['n01'])} pairs had {b['event']} only after, {count(test['n10'])} "
                "only before"
                if test.get("n01") is not None
                else "its discordant pairs are not in the saved comparison"
            )
            lines = [verdict_line(str(b["verdict"]), str(b["sentence"]))]
            kind = (
                f"declared a {b['kind']}"
                if b.get("kind")
                else str(b.get("kind_note") or "its kind not declared")
            )
            stat = f", statistic {num(test['stat'])}" if test.get("stat") is not None else ""
            can = "can" if b.get("flaggable") else "cannot"
            lines += block(
                [
                    Detail(
                        "before",
                        f"{interval(sa['value'], sa['lo'], sa['hi'])}, {count(k.get('a'))} of "
                        f"{count(n.get('a'))} episodes",
                    ),
                    Detail(
                        "after",
                        f"{interval(sb['value'], sb['lo'], sb['hi'])}, {count(k.get('b'))} of "
                        f"{count(n.get('b'))} episodes",
                    ),
                    Detail(
                        "",
                        f"{level(sa.get('level'))} {str(sa.get('method', '')).capitalize()} "
                        "interval on each run's share, per condition, not adjusted",
                    ),
                    Detail(
                        "change",
                        f"{signed(b['delta'])} [{signed(ci.get('lo'))}, {signed(ci.get('hi'))}], "
                        f"{level(ci.get('level'))} interval ({ci.get('basis')})",
                    ),
                    Detail(
                        "test",
                        f"{test.get('name')}: {pairs}; p {pv(test.get('p'))}, q "
                        f"{pv(test.get('q'))}, Holm's p {pv(test.get('q_holm'))}{stat}",
                    ),
                    Detail("rise", _limit_words(b, "rise")),
                    Detail(
                        "fall", f"{limit(b.get('mde_fall'), b.get('mde_fall_note'))}, the same way"
                    ),
                    Detail(
                        "event",
                        f"{b['event']}, {kind}; the smallest possible p is {pv(b.get('p_min'))}, "
                        f"so a flag {can} be raised",
                    ),
                ]
            )
            if b.get("competing"):
                lines += block([Detail("competing", value_words(b["competing"]))])
            extra = {key: v for key, v in b.items() if key not in _BLOCK_KNOWN}
            lines += block(
                [
                    Detail(words_of(key), value_words(v))
                    for key, v in extra.items()
                    if not key.endswith("address")
                ]
            )
            return lines

        page.keep_bottom = True

        def layout(width: int) -> None:
            chosen = blocks if width >= WIDE or not blocks else [blocks[shown[0] % len(blocks)]]
            page.top = []
            for b in chosen:
                page.top += [*event_block(b), BLANK]
            page.top += block(
                [
                    Detail(
                        "compared",
                        f"{short(str((doc.get('comparison') or {}).get('name', '')))} "
                        f"({_look.fmt_hash((doc.get('comparison') or {}).get('id', ''))})",
                    ),
                    *[Detail("rule", str(r)) for r in doc.get("rules") or []],
                ]
            )
            page.top.append(BLANK)
            page.rows = []
            for b in chosen:
                for i, ep in enumerate(b.get("episodes", [])):
                    side = "before" if i == 0 else "after"
                    k = (b.get("k") or {}).get("a" if i == 0 else "b")
                    run = f"{ep['run']} ({ep['run_id']})" if width >= WIDE else str(ep["run"])
                    line = Line(f"  episodes  {side:<6}  {count(k)} ended in {b['event']}  {run}")
                    line.opens = lambda ep=ep, b=b: self.open_episodes(
                        str(ep["run_id"]),
                        str(b["event"]),
                        str(doc.get("condition_hash", "")),
                        ep.get("address"),
                    )
                    page.rows.append(line)
            page.header = None
            page.bottom = [BLANK]
            links = [c for b in chosen for c in b.get("charts", [])]
            if links and self.ui_page(str(links[0]["address"])):
                page.bottom += block(
                    [Detail("chart", str(c["address"]), link=str(c["address"])) for c in links]
                )
            page.bottom += also_recorded(doc, _CONDITION_KNOWN)

        page.layout = layout

        def keys(ch: str) -> bool:
            if ch != "e":
                return False
            shown[0] += 1
            layout(self.width())
            return True

        page.on_key = keys
        return page

    # ---------- could not detect ----------

    def could_not_detect_page(self, doc: dict[str, Any]) -> Page:
        page = Page(
            "could not detect",
            short(str((doc.get("comparison") or {}).get("name", ""))),
            view=doc,
            keys=[MOVE, OPEN, BACK, ("/", "filter"), ("tab", "link"), ("y", "copy")],
        )
        rows = list(doc.get("rows", []))
        cid = str((doc.get("comparison") or {}).get("id", ""))

        def layout(width: int) -> None:
            # the table first: the chart link above it follows its focused row
            first = rows[0]["config"] if rows else {}
            columns = [
                Column(axes_of(first) if first else "condition"),
                Column("event"),
                Column("before", right=True),
                Column("rise"),
                Column("fall"),
                Column("could tell"),
            ]
            cells = [
                [
                    values_of(r["config"]),
                    str(r["event"]),
                    rate(r["share_a"]),
                    limit(r["mde_rise"], r.get("mde_rise_note")),
                    limit(r["mde_fall"], r.get("mde_fall_note")),
                    "yes" if r.get("could_tell") else "no",
                ]
                for r in rows
            ]
            page.header, page.rows = lay_table(columns, cells, width) if rows else (None, [])
            for line, r in zip(page.rows, rows, strict=True):
                line.data = r
                line.opens = lambda r=r: self.open_condition(cid, str(r["address"]).split("#")[0])
            page.top = [verdict_line(doc["verdict"], doc["sentence"]), BLANK]
            threshold = doc.get("threshold") or {}
            details: list[Detail | None] = [
                Detail("asked", str(doc.get("question"))),
                Detail("answer", str(doc.get("answer"))),
                Detail("threshold", f"{rate(threshold.get('value'))} ({threshold.get('source')})"),
                Detail("flaggable", str(doc.get("flaggable"))),
            ]
            for key in ("together_needed", "replicates_for_lone_flag", "gate_replicates"):
                if doc.get(key) is not None:
                    details.append(Detail(words_of(key), value_words(doc[key])))
            details += design_lines(doc.get("design_mde"), doc.get("design"))
            details += [Detail(str(f["label"]), str(f["text"])) for f in doc.get("facts") or []]
            charts = list(doc.get("charts", []))
            if charts and self.ui_page(str(charts[0]["address"])):
                row = page.table_row()
                focused = str(row.data["event"]) if row is not None else None
                pick = [c for c in charts if c["event"] == focused] or charts[:1]
                details += [
                    Detail("chart", str(c["address"]), link=str(c["address"])) for c in pick
                ]
            page.top += block(details)
            page.top.append(BLANK)
            page.bottom = [BLANK]
            if not rows:
                page.bottom += [text_line("no condition is unchanged, so nothing is asked")]
            if doc.get("limits_rule"):
                page.bottom.append(text_line(str(doc["limits_rule"]), "dim"))
            page.bottom += also_recorded(doc, _CND_KNOWN)

        page.layout = layout
        page.on_focus = lambda: layout(self.width())
        return page

    # ---------- the sweep ----------

    def plan_lines(self, plan: Any) -> list[Line]:
        """The plan as ``sweep --dry-run`` prints it, then the facts of its document."""
        doc = dict(plan.to_json())
        lines = [verdict_line("plan", str(plan.sentence)), BLANK]
        lines += [Line(f"  {line}") for line in plan.lines]
        if plan.design_line:
            lines.append(Line(str(plan.design_line)))
        details: list[Detail | None] = []
        if doc.get("run_name"):
            details.append(Detail("run", f"{doc['run_name']} ({doc.get('run_id')})"))
        details += design_lines(doc.get("design_mde"), None)
        inner = doc.get("plan") or {}
        details.append(
            Detail(
                "to run",
                f"{count(inner.get('rollouts'))} rollouts; {count(inner.get('cells'))} conditions, "
                f"{count(inner.get('replicates'))} replicates each",
            )
        )
        lines += [BLANK, *block(details)]
        rest = {k: v for k, v in doc.items() if k not in _PLAN_KNOWN}
        lines += block([Detail(words_of(k), value_words(v)) for k, v in rest.items()])
        return lines

    # ---------- help ----------

    def help_page(self) -> Page:
        page = Page("help", keys=[MOVE, BACK, ("q", "quit")], scroll_only=True)
        shared = [
            ("↑ ↓", "move the focus one row"),
            ("PgUp PgDn Home End", "move it a page, or to the first or last row"),
            ("enter", "open the focused row's screen, or its link in the browser"),
            ("esc", "back, with the focus where it was"),
            ("tab", "move the focus between the links and the table"),
            ("/", "filter the table's rows by text; esc clears it"),
            ("y", "copy the focused link's file:// address, or the focused command or code"),
            ("m", "the lines the window has no room for, when a screen says so"),
            ("?", "this help"),
            ("q", "quit (exit 0); during a question, no"),
            ("ctrl-c", "quit (exit 130); in a sweep, stop and keep what is done"),
        ]
        own = [
            ("s", "home, runs", "sweep the spec in this folder (prove.toml)"),
            ("c", "home, runs", "compare two runs"),
            ("r", "home", "the runs"),
            ("d", "comparison", "what it could not detect"),
            ("t", "comparison", "its conditions"),
            ("v", "conditions", "back to the verdict"),
            ("e", "condition, episodes", "the next event"),
            ("g", "run", "its event log, when the window has no room for it"),
            ("space", "compare", "choose a run as before, then after"),
            ("l", "compare", "previous and latest"),
            ("p", "sweep, when refused", "plan again with the replicates the refusal names"),
        ]

        def layout(width: int) -> None:
            lines = [text_line("keys on every screen", "dim")]
            lines += [Line(f"  {k:<20}{w}", [(2, 2 + len(k), "bold")], hang=22) for k, w in shared]
            lines.append(text_line("keys of one screen", "dim"))
            lines += [
                Line(f"  {k:<20}{s:<26}{w}", [(2, 2 + len(k), "bold")], hang=48) for k, s, w in own
            ]
            lines.append(text_line("screens", "dim"))
            lines.append(
                text_line(
                    "home · runs · run · sweep · compare · comparison · conditions · condition · "
                    "episodes · could not detect"
                )
            )
            lines.append(
                text_line(
                    "every screen is a page of the dashboard too, except home, sweep and compare: "
                    f"{COMMAND} ui --open"
                )
            )
            page.rows = [row for line in lines for row, _ in wrap_line(line, width, False)]
            page.top, page.header, page.bottom = [], None, []

        page.layout = layout
        return page


# ---------- what each screen knows of its document ----------

_HOME_KNOWN = {
    "verdict",
    "sentence",
    "store",
    "n_runs",
    "n_comparisons",
    "latest_run",
    "latest_comparison",
    "next",
    "ui",
    "items",
}
_RUNS_KNOWN = {"verdict", "sentence", "store", "runs", "comparisons", "first_run", "no_comparison"}
_RUN_KNOWN = {
    "verdict",
    "sentence",
    "name",
    "run_id",
    "status",
    "done",
    "total",
    "created_at",
    "target",
    "backend",
    "t_unit",
    "horizon",
    "paired_with",
    "paired_with_name",
    "conditions",
    "axes",
    "replicates",
    "outcomes",
    "declared",
    "design_mde",
    "design",
    "comparisons",
    "cells",
    "events",
    "events_note",
    "shares_rule",
}
_EPISODES_KNOWN = {
    "verdict",
    "sentence",
    "run",
    "run_name",
    "run_id",
    "event",
    "condition",
    "condition_hash",
    "comparisons",
    "episodes",
    "reproduce",
    "empty",
    "offset",
    "total",
    "next",
}
_COMPARISON_KNOWN = {
    "verdict",
    "sentence",
    "id",
    "name",
    "method",
    "before",
    "after",
    "threshold",
    "family",
    "saved_at",
    "facts",
    "events",
    "trades",
    "rows_rule",
    "rows",
    "charts",
    "could_not_detect",
}
_CONDITION_KNOWN = {
    "condition",
    "condition_hash",
    "comparison",
    "before",
    "after",
    "rules",
    "events",
}
_BLOCK_KNOWN = {
    "event",
    "kind",
    "verdict",
    "sentence",
    "share_a",
    "share_b",
    "k",
    "n",
    "delta",
    "ci",
    "test",
    "mde_rise",
    "mde_fall",
    "mde_rise_note",
    "mde_fall_note",
    "mde_test",
    "mde_level",
    "mde_family",
    "mde_power",
    "mde_anchor",
    "p_min",
    "flaggable",
    "episodes",
    "charts",
    "competing",
    "kind_note",
}
_CND_KNOWN = {
    "verdict",
    "sentence",
    "comparison",
    "question",
    "threshold",
    "n_unchanged",
    "n_could_not_tell",
    "answer",
    "flaggable",
    "p_min",
    "level",
    "family",
    "design_mde",
    "design",
    "limits_rule",
    "rows",
    "charts",
    "together_needed",
    "replicates_for_lone_flag",
    "gate_replicates",
    "facts",
}
_PLAN_KNOWN = {"schema", "verdict", "sentence", "run_id", "run_name", "plan", "design_mde", "next"}


_RUN_COLUMNS = [
    Column("#", right=True),
    Column("name", cut=True),
    Column("id", drop=3),
    Column("status", style=verdict_style),
    Column("backend", drop=2),
    Column("target", drop=1, cut=True),
    Column("rows", right=True),
    Column("no outcome", right=True),
    Column("created"),
]


def _run_cells(r: Mapping[str, Any], *, with_outcome: bool) -> list[str]:
    cells = [
        "–" if r.get("number") is None else str(r["number"]),  # a partial run has no number
        str(r["name"]),
        str(r["run_id"]),
        str(r["status"]),
        str(r["backend"]),
        str(r["target"]),
        count(r["rows"]),
    ]
    if with_outcome:
        cells.append(count(r["rows_without_outcome"]))
    cells.append(when(r["created_at"]))
    return cells


def _commonest(cells: Sequence[Mapping[str, Any]]) -> str | None:
    totals: dict[str, int] = {}
    for c in cells:
        for o, s in c["shares"].items():
            totals[o] = totals.get(o, 0) + int(s.get("k") or 0)
    return max(totals, key=lambda o: totals[o]) if totals else None


def _not_commonest(cells: Sequence[Mapping[str, Any]], outcomes: Sequence[str]) -> str | None:
    """A run that declares no failure opens the episodes of its first outcome that is
    not its commonest."""
    commonest = _commonest(cells)
    return next((o for o in outcomes if o != commonest), commonest)


def _limit_words(b: Mapping[str, Any], side: str) -> str:
    value = limit(b.get(f"mde_{side}"), b.get(f"mde_{side}_note"))
    test = _TESTS.get(str(b.get("mde_test")), str(b.get("mde_test")))
    return (
        f"{value}: the smallest {side} one condition alone would be flagged for, power "
        f"{rate(b.get('mde_power'))}, "
        f"from the {b.get('mde_anchor')} ({test}, level {pv(b.get('mde_level'))} over "
        f"{count(b.get('mde_family'))} tests)"
    )


def _verdict_block(doc: Mapping[str, Any], *, saved: bool) -> list[Detail]:
    """``diff``'s verdict block, in ``diff``'s order: the method, the threshold when the words say
    nothing moved, the two runs, a line per traded condition, then the facts the save recorded
    (the rules, the limits, the intervals, the fragility, peeking, errors); then what the app adds:
    the family, the save, and the way to what it could not detect."""
    if not saved:
        return [Detail(str(label), str(text)) for label, text in doc.get("_detail", [])] + [
            Detail("saved", "not saved: the store cannot be written")
        ]
    method = doc.get("method") or {}
    facts = list(doc.get("facts") or [])
    early = [f for f in facts if f["label"] in ("comparison", "threshold")]
    late = [f for f in facts if f["label"] not in ("comparison", "threshold")]
    out = [
        Detail(
            "method", str(method.get("line") or f"{method.get('words')}, {method.get('chosen')}")
        )
    ]
    out += [Detail(str(f["label"]), str(f["text"])) for f in early]
    out += [
        *[Detail(side, _run_words(doc.get(side) or {})) for side in ("before", "after")],
    ]
    for t in doc.get("trades") or []:
        moved = [f"{e} fell" for e in t.get("safer") or []] + [
            f"{e} rose" for e in t.get("worse") or []
        ]
        out.append(Detail("trade", f"{condition(t.get('config') or {})}: {', '.join(moved)}"))
    out += [Detail(str(f["label"]), str(f["text"])) for f in late]
    if not early:
        threshold = doc.get("threshold") or {}
        out.append(
            Detail("threshold", f"{rate(threshold.get('value'))} ({threshold.get('source')})")
        )
    family = doc.get("family") or {}
    out.append(
        Detail(
            "tests",
            f"{count(family.get('tests'))} in one pass ({count(family.get('conditions'))} "
            "conditions × "
            f"{count(family.get('events'))} events), q {num(family.get('q'))}",
        )
    )
    out.append(
        Detail("saved", f"comparison {_look.fmt_hash(doc.get('id'))}, {when(doc.get('saved_at'))}")
    )
    cnd = doc.get("could_not_detect") or {}
    if cnd:
        out.append(
            Detail(
                "could not tell",
                f"{count(cnd.get('n_could_not_tell'))} unchanged conditions; d shows what it could "
                "not detect",
            )
        )
    return out


def _run_words(run: Mapping[str, Any]) -> str:
    """One run of a comparison: its name, then its id and status."""
    return f"{run.get('name')} ({run.get('run_id')}, {run.get('status')})"


def _events_of(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The per-event counts: the view's, or those of a comparison that was not saved."""
    if (
        "events" in doc
        and isinstance(doc["events"], list)
        and doc["events"]
        and isinstance(doc["events"][0], Mapping)
    ):
        return [dict(e) for e in doc["events"]]
    out = []
    for name, ev in (doc.get("by_event") or {}).items():
        out.append(
            {
                "name": name,
                "kind": ev.get("kind"),
                "n_worse": ev.get("n_worse"),
                "n_safer": ev.get("n_safer"),
                "n_higher": ev.get("n_higher"),
                "n_lower": ev.get("n_lower"),
                "n_unchanged": ev.get("n_unchanged"),
                "n_conditions": len(ev.get("cells") or []),
            }
        )
    return out


def _rows_of(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The (condition, event) rows: the view's, or those of a comparison that was not saved."""
    if isinstance(doc.get("rows"), list):
        return [dict(r) for r in doc["rows"]]
    out = []
    for name, ev in (doc.get("by_event") or {}).items():
        for c in ev.get("cells") or []:
            sa, sb = c.get("share_a") or {}, c.get("share_b") or {}
            out.append(
                {
                    "event": name,
                    "config": c.get("config") or {},
                    "share_a": sa.get("value"),
                    "share_a_lo": sa.get("lo"),
                    "share_a_hi": sa.get("hi"),
                    "share_b": sb.get("value"),
                    "delta": c.get("delta"),
                    "p": c.get("p"),
                    "q": c.get("q"),
                    "verdict": c.get("verdict"),
                    "mde_rise": c.get("mde_rise"),
                    "mde_fall": c.get("mde_fall"),
                    "mde_rise_note": c.get("mde_rise_note"),
                    "mde_fall_note": c.get("mde_fall_note"),
                }
            )
    return out
