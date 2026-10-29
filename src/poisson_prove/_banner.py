"""The terminal app's banner, in the shape of the other Poisson Labs tools' banners: the tool's mark
as one terminal row of twelve cells, "poisson labs" bold beside it, and the tool's name bold with
its version dim beneath. 26 columns by 2 rows.

Prove's mark is four conditions, each run before (dim) and after (solid) a change on the same
seeds: three hold and one moved. It is the mark the site draws for Prove, cell for cell. The look
allows the terminal's own colours only, so the mark is the terminal's foreground with dim, not a
colour of its own.
"""

from __future__ import annotations

from poisson_prove import __version__

MARK = "▆▆ ▆▆ ▃█ ▆▆ "
#: The cells drawn dim: each pair's first, the run before the change.
DIM_CELLS = (0, 3, 6, 9)
NAME = "poisson labs"
TOOL = "prove"
GAP = "  "
WIDTH = len(MARK) + len(GAP) + len(NAME)


def lines() -> list[tuple[str, list[tuple[int, int, str]]]]:
    """The banner's two rows, each its text and its ``(start, end, style)`` spans."""
    first = f"{MARK}{GAP}{NAME}"
    spans = [(i, i + 1, "dim") for i in DIM_CELLS]
    spans.append((len(MARK) + len(GAP), len(first), "bold"))
    indent = len(MARK) + len(GAP)
    second = f"{' ' * indent}{TOOL}  {__version__}"
    return [
        (first, spans),
        (
            second,
            [(indent, indent + len(TOOL), "bold"), (indent + len(TOOL) + 2, len(second), "dim")],
        ),
    ]
