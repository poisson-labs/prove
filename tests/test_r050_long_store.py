"""0.5.0: a store path too long for the app's header is cut in the middle, and the app never hangs.

The header holds the tool's name, ``·``, the screen's title, its subject and, at the right edge,
the store as the user gave it (``docs/cli-look.md``, band 1). Up to 0.4.0 a store longer than the
room left there pushed the header's spans out of the row: past twice the window's width the dim
span at the right edge started before column 0, and Textual's search for the line a span starts on
never ended, so the app sat at full CPU on its first screen. From 0.5.0 a store too long for the
room the title leaves is cut in the middle with ``…``, as a name too long for its column is, and
the screen the header sits on prints it whole.

| invariant | tests |
|---|---|
| L1 the app opens on a long store, at any size, with the cut store at the header's right edge | ``test_l1_*`` |
| L2 the opening screen's header: the same cut, and no span before column 0 | ``test_l2_*`` |
| L3 a store that fits is shown whole, as before | ``test_l3_*`` |

The app runs in a child process with a time limit, so a header that hangs it fails the test
instead of stopping the suite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
TITLE = "poisson-prove · home"
SIZES = [(80, 24), (120, 40), (160, 40)]


def room(w: int, title: str = TITLE) -> int:
    """The columns the header leaves for the store: the title, two spaces, the store."""
    return w - len(title) - 2


def cut(text: str, w: int) -> str:
    head = (w - 1) // 2
    return text[:head] + "…" + text[len(text) - (w - 1 - head) :]


def store_of(length: int) -> str:
    """A relative store path exactly ``length`` characters long, in folders of 40 characters."""
    parts, left = [], length - len("store")
    while left > 0:
        n = min(40, left - 1) if left > 1 else 0
        parts.append("d" * n)
        left -= n + 1
    path = "/".join(parts + ["store"])
    assert len(path) == length, (length, len(path))
    return path


CHILD = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pf6_support import drive

async def screen(session):
    return await session.settle()

out = []
for store, w, h in json.loads(sys.argv[2]):
    Path(store).mkdir(parents=True, exist_ok=True)
    code, grid = drive(screen, cwd=Path.cwd(), store=store, size=(w, h))
    out.append({"rows": grid.rows, "masks": grid.masks})
print(json.dumps(out))
"""


def open_app(cases: list[tuple[str, int, int]], cwd: Path) -> list[dict[str, list[str]]]:
    env = {k: v for k, v in os.environ.items() if k not in ("NO_COLOR", "POISSON_PROVE_STORE", "PROOFLOAD_STORE")}
    try:
        done = subprocess.run(
            [sys.executable, "-c", CHILD, str(TESTS), json.dumps(cases)],
            cwd=cwd, env=env, capture_output=True, text=True, timeout=180,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"the app did not draw its first screen within 180 s for stores of {[len(c[0]) for c in cases]} characters")
    assert done.returncode == 0, done.stderr
    return list(json.loads(done.stdout.strip().splitlines()[-1]))


def whole_in_body(rows: list[str], store: str) -> bool:
    """The store, printed whole in the body, wrapped at the window's edge with nothing inserted."""
    return store in "".join(row.strip() for row in rows[2:-3])


@pytest.mark.parametrize("size", SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
def test_l1_the_app_opens_on_a_long_store_with_the_store_cut_in_the_middle(size: tuple[int, int], tmp_path: Path) -> None:
    """One character over the room, twice the window and one, and three times the window: the app
    draws home, the header is the tool's name in bold, the title, and the store cut in the middle
    with ``…`` to fill the room, dim, ending at the right edge; the body prints the store whole."""
    w, h = size
    lengths = [room(w) + 1, 2 * w + 1, 3 * w]
    stores = [store_of(n) for n in lengths]
    grids = open_app([(s, w, h) for s in stores], tmp_path)
    for store, grid in zip(stores, grids):
        header, mask = grid["rows"][0], grid["masks"][0]
        shown = cut(store, room(w))
        assert header == f"{TITLE}  {shown}", (len(store), header)
        assert len(header) == w
        assert mask[:13] == "B" * 13, (len(store), mask)
        assert mask[w - len(shown):] == "D" * len(shown), (len(store), mask)
        assert whole_in_body(grid["rows"], store), (len(store), grid["rows"])


@pytest.mark.parametrize("size", SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
@pytest.mark.parametrize("over", [1, 2, 3], ids=["room+1", "twice+1", "thrice"])
def test_l2_the_opening_screen_cuts_a_long_store_and_starts_no_span_before_the_row(
    size: tuple[int, int], over: int
) -> None:
    """The banner's screen, which a person sees first: its header is the tool's name and the store
    cut to the room the name leaves, and none of its styled spans starts before column 0."""
    from poisson_prove._cli_app import ProveApp

    w, h = size
    left = w - len("poisson-prove") - 2
    store = store_of({1: left + 1, 2: 2 * w + 1, 3: 3 * w}[over])
    text = ProveApp(store=store)._draw_opening(w, h)
    header = text.plain.splitlines()[0]
    assert header == f"poisson-prove  {cut(store, left)}", header
    assert all(span.start >= 0 for span in text.spans), [(s.start, s.end) for s in text.spans if s.start < 0]


@pytest.mark.parametrize("size", SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
def test_l3_a_store_that_fits_is_shown_whole(size: tuple[int, int], tmp_path: Path) -> None:
    """A store exactly as long as the room, and a short one: the header ends with it whole, as in 0.4.0."""
    w, h = size
    stores = [store_of(room(w)), "prove-runs"]
    grids = open_app([(s, w, h) for s in stores], tmp_path)
    for store, grid in zip(stores, grids):
        header = grid["rows"][0]
        assert header.startswith(TITLE), header
        assert header.endswith(store) and "…" not in header, header
        assert len(header) == w
