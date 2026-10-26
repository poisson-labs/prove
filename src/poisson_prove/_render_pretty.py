"""Pretty: the command line's look drawn with Rich (section 5.5).

The second rendering of the command line's lines. ``_render_term`` lays out each line on the
terminal; this module draws its styles: the four meanings in the terminal's 16 named colours
(green, yellow, red), bold for a verdict that is a result, dim for secondary text, and nothing
else (no background, no 256 or true colour, no italic or underline). A Prove that cannot import
Rich prints plain and says nothing about it: :func:`styler` returns ``None``.
"""

from __future__ import annotations

import io
from typing import Any

__all__: list[str] = []


class RichStyler:
    """Styles text through one Rich console held to the 16 named colours."""

    def __init__(self) -> None:
        from rich.console import Console

        self._console = Console(
            file=io.StringIO(),
            force_terminal=True,
            color_system="standard",
            no_color=False,
            width=1_000_000,
            highlight=False,
            markup=False,
            emoji=False,
            soft_wrap=True,
            legacy_windows=False,
        )

    def style(self, text: str, meaning: str) -> str:
        from rich.text import Text

        if not text:
            return text
        with self._console.capture() as captured:
            self._console.print(Text(text, style=meaning), end="")
        return captured.get()

    def clear_line(self) -> str:
        """A carriage return and an erase of the line, as Rich's live display clears its own."""
        from rich.control import Control
        from rich.segment import ControlType

        return "\r" + Control((ControlType.ERASE_IN_LINE, 2)).segment.text


def styler() -> Any:
    """The pretty styler, or ``None`` when Rich cannot be imported (the plain rendering then)."""
    try:
        return RichStyler()
    except ImportError:
        return None
