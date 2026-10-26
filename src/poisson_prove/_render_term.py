"""The command line's lines on a terminal: plain's own wrapping, and pretty's look over it.

Off a terminal the command line prints its plain lines as they are, one line per fact. On a
terminal each stream it writes goes through a :class:`Terminal`, told what each line is (a verdict
line, a ``label  value`` detail line, a command to copy, a ``note:`` or ``error:`` line, body text,
a table, the live progress) by the face that wrote it, never by reading the text back:

- a line longer than the terminal wraps at spaces with a hanging indent (the value's column for a
  detail line, the sentence's for a verdict line); a command to copy is never broken;
- pretty (section 5.5's switch, decided by the face) adds the four meanings' colours through a
  :class:`Styler`, folds a table wider than the terminal into one record per row, prints a
  condition as its axes instead of its JSON, and removes the progress line when the work ends.

No third-party library: the pretty styler, which needs Rich, is ``_render_pretty``'s. Nothing here
computes a number; every cell and sentence arrives formatted by the shared look (``_look``).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Protocol

from poisson_prove import _look

__all__: list[str] = []

#: Section 5.5's four meanings: green, the command did what was asked; yellow, it stopped short or
#: cannot say; red, an error or a failed check. A verdict that is neither is a result, bold.
GREEN = ("ok", "done", "passed", "under cap")
YELLOW = ("stopped", "too small to tell", "no significant change")
RED = ("failed", "at cap")


def meaning_of(word: str) -> str:
    """The style a verdict word is drawn in: ``green``, ``yellow``, ``red`` or ``bold``."""
    if word in GREEN:
        return "green"
    if word in YELLOW:
        return "yellow"
    if word in RED:
        return "red"
    return "bold"


class Styler(Protocol):
    """Draws a piece of text in one of the look's styles (``green``, ``yellow``, ``red``, ``bold``,
    ``dim``) and says what clears a live line."""

    def style(self, text: str, meaning: str) -> str: ...

    def clear_line(self) -> str: ...


class _Plain:
    def style(self, text: str, meaning: str) -> str:
        return text

    def clear_line(self) -> str:
        return "\r"


#: A markdown table's row as the report writes it.
_TABLE_ROW = re.compile(r"^\|.*\|$")
_RULE_ROW = re.compile(r"^\|(?:\s*:?-+:?\s*\|)+$")
_NUMBER = re.compile(r"^[+\-]?[\d,]*\.?\d+(?:e[+\-]?\d+)?%?$|^[+\-]?\d[\d,]*$")


def is_table_line(line: str) -> bool:
    """Whether ``line`` is a row of a markdown table (the report's tables)."""
    return _TABLE_ROW.match(line) is not None


def wrap(line: str, width: int, hang: int) -> list[str]:
    """``line`` broken at spaces so no row is wider than ``width``, each row after the first
    indented by ``hang``; a word longer than a row is left whole."""
    if len(line) <= width:
        return [line]
    hang = hang if hang < width // 2 else min(4, width // 4)
    rows: list[str] = []
    rest, floor = line, 0
    while len(rest) > width:
        cut = rest.rfind(" ", floor + 1, width + 1)
        if cut <= floor:
            break
        rows.append(rest[:cut].rstrip())
        rest = " " * hang + rest[cut:].lstrip(" ")
        floor = hang
    rows.append(rest)
    return rows


def _axes(cell: str) -> str:
    """A condition's JSON cell as its axes, ``task_id refund · tool_fail_rate 0.55``, each value as
    rule 10 prints it."""
    try:
        config = json.loads(cell)
    except ValueError:
        return cell
    if not isinstance(config, dict):
        return cell
    return _look.condition_words(config)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


class Terminal:
    """One stream on a terminal of ``width`` columns: what each kind of line looks like there."""

    def __init__(self, width: int, styler: Styler | None = None) -> None:
        self.width = max(20, width)
        self.styler: Styler = styler or _Plain()
        self.pretty = styler is not None

    def _paint(self, rows: list[str], spans: Sequence[tuple[int, int, str]]) -> str:
        """``rows`` with ``spans`` (start, end, style; on the first row) drawn, each row ended."""
        if not self.pretty:
            return "".join(row + "\n" for row in rows)
        first = rows[0]
        out, at = [], 0
        for start, end, meaning in sorted(spans):
            end = min(end, len(first))
            if start < at or start >= end:
                continue
            out.append(first[at:start])
            out.append(self.styler.style(first[start:end], meaning))
            at = end
        out.append(first[at:])
        return "".join(out) + "\n" + "".join(row + "\n" for row in rows[1:])

    def verdict(self, word: str, sentence: str) -> str:
        """A verdict line, ``word  sentence``: the word in its meaning's style."""
        rows = wrap(f"{word}  {sentence}", self.width, len(word) + 2)
        return self._paint(rows, [(0, len(word), meaning_of(word))])

    def detail(self, label: str, value: str) -> str:
        """An indented ``label  value`` line, the label dim, wrapped under the value."""
        lead = f"  {label}  "
        rows = wrap(lead + value, self.width, len(lead))
        return self._paint(rows, [(2, 2 + len(label), "dim")])

    def command(self, line: str, label: str = "") -> str:
        """A line carrying a command or code to copy (``  next: …``, a reproduce line): never
        broken; its label, if any, dim."""
        at = line.find(label) if label else -1
        return self._paint([line], [(at, at + len(label), "dim")] if at >= 0 else [])

    def note(self, text: str) -> str:
        return self._paint(wrap(f"note: {text}", self.width, 6), [(0, 5, "yellow")])

    def error(self, text: str) -> str:
        return self._paint(wrap(f"error: {text}", self.width, 7), [(0, 6, "red")])

    def text(self, line: str) -> str:
        """Body text: wrapped under its own indent, two deeper."""
        lead = len(line) - len(line.lstrip(" "))
        return self._paint(wrap(line, self.width, lead + 2), [])

    def table(
        self,
        rows: Sequence[Sequence[str]],
        numeric: frozenset[int] = frozenset(),
        *,
        key: int | None = None,
        indent: int = 0,
    ) -> str:
        """A table, its first row the header. Plain prints it as the command lays it out, each line
        wrapped like body text; pretty aligns it with a dim header when it fits the terminal and
        folds it into one record per row, led by its ``key`` cell, when it does not."""
        widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]

        right = numeric if self.pretty else frozenset()  # plain keeps the pipe's layout

        def laid(row: Sequence[str]) -> str:
            cells = [
                c.rjust(w) if i in right else c.ljust(w)
                for i, (c, w) in enumerate(zip(row, widths, strict=True))
            ]
            return (" " * indent + "  ".join(cells)).rstrip()

        lines = [laid(r) for r in rows]
        if not self.pretty:
            return "".join(self.text(line) for line in lines)
        if max(len(line) for line in lines) <= self.width:
            head = lines[0]
            return self._paint([head], [(indent, len(head), "dim")]) + "".join(
                line + "\n" for line in lines[1:]
            )
        return self._fold(rows, indent, key)

    def _fold(self, rows: Sequence[Sequence[str]], indent: int, key: int | None) -> str:
        """A table too wide for the terminal, one record per row (item 27): the row's ``key``
        cell (else its ``config`` cell, else its first), then every other cell as ``column value``,
        the column dim, as many whole pieces to a row as fit."""
        header, body = list(rows[0]), rows[1:]
        if key is None:
            key = header.index("config") if "config" in header else 0
        lead = " " * (indent + 4)
        out = []
        spans: list[tuple[int, int, str]]
        for row in body:
            out.append(" " * indent + row[key] + "\n")
            line, spans = lead, []
            for i, (column, cell) in enumerate(zip(header, row, strict=True)):
                if i == key or cell == "":
                    continue
                piece = f"{column} {cell}"
                if line != lead and len(line) + 2 + len(piece) > self.width:
                    out.append(self._paint([line], spans))
                    line, spans = lead, []
                if line != lead:
                    line += "  "
                if len(line) + len(piece) > self.width:  # a piece wider than a row: wrapped alone
                    parts = wrap(line + piece, self.width, len(lead))
                    out.append(self._paint(parts, [(len(line), len(line) + len(column), "dim")]))
                    line, spans = lead, []
                    continue
                spans.append((len(line), len(line) + len(column), "dim"))
                line += piece
            if line != lead:
                out.append(self._paint([line], spans))
        return "".join(out)

    def markdown_table(self, lines: Sequence[str]) -> str:
        """A report's markdown table (``| a | b |`` rows under a ``|---|`` rule). Plain prints its
        lines as they are, wrapped; pretty prints its rows as a table, a condition by its axes."""
        if not self.pretty:
            return "".join(self.text(line) for line in lines)
        rows = [_cells(line) for line in lines if not _RULE_ROW.match(line)]
        if not rows or len({len(r) for r in rows}) != 1:
            return "".join(self.text(line) for line in lines)
        rows = [[_axes(c) if c.startswith("{") else c for c in row] for row in rows]
        numeric = frozenset(
            i
            for i in range(len(rows[0]))
            if len(rows) > 1 and all(_NUMBER.match(r[i]) or r[i] in ("", "-") for r in rows[1:])
        )
        return self.table(rows, numeric)

    def progress(self, text: str) -> str:
        """The live progress line, drawn over itself."""
        return self.styler.clear_line() + (self.styler.style(text, "dim") if self.pretty else text)

    def progress_end(self) -> str:
        """What ends the progress line when the work ends: plain leaves the last count on its line;
        pretty removes it."""
        return self.styler.clear_line() if self.pretty else "\n"
