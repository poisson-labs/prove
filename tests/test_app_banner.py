"""The terminal app's banner: on a terminal, the app opens on the banner, then home.

The banner is the other Poisson Labs tools' shape (the tool's twelve-cell mark, "poisson labs", the
tool's name and version) inside the app's frame. Home follows on its own, sooner on any key; ``q``
on the banner quits. These run the app in a pseudo-terminal, as a person opens it: a headless run
(Textual's test driver) has no one to show a banner to and opens on home.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pf6_support import Step, copy_world, run_pty, strip_escapes

from poisson_prove import __version__, _banner


def _folder(old_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    return copy_world(old_world[0], tmp_path / "w"), home


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
@pytest.mark.parametrize("no_color", [None, "1"])
def test_the_app_opens_on_the_banner_then_home_on_its_own(
    size: tuple[int, int], no_color: str | None, old_world: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    folder, home = _folder(old_world, tmp_path)
    cols, rows = size
    steps = (Step(b"", until=("poisson labs", "q quit")), Step(b"q", until=("poisson-prove · home", "saved comparison", "q quit")))
    run = run_pty([], home=home, cwd=folder, cols=cols, rows=rows, steps=steps, timeout=90, NO_COLOR=no_color)
    assert run.code == 0, run.err[-500:]
    banner, shown_home = run.seen
    assert banner[0].startswith("poisson-prove ") and banner[0].rstrip().endswith("prove-runs"), banner[0]
    assert "poisson-prove · " not in banner[0], banner[0]
    assert set(banner[1]) == {"─"} and set(banner[-2]) == {"─"}, (banner[1], banner[-2])
    first = next(i for i, row in enumerate(banner) if _banner.MARK.rstrip() in row)
    assert banner[first].strip() == f"{_banner.MARK}{_banner.GAP}{_banner.NAME}".strip(), banner[first]
    assert banner[first + 1].split() == ["prove", __version__], banner[first + 1]
    assert banner[first + 1].index("prove") == banner[first].index(_banner.NAME)
    assert all(len(row.rstrip()) <= cols for row in banner)
    assert 2 < first and first + 1 < rows - 3  # inside the body, clear of the frame's bands
    assert shown_home[0].startswith("poisson-prove · home"), shown_home[0]
    assert shown_home[2].startswith("  ok  "), shown_home[2]  # home's body opens with its verdict line


def test_q_on_the_banner_quits_before_home(old_world: tuple[Path, dict[str, Any]], tmp_path: Path) -> None:
    folder, home = _folder(old_world, tmp_path)
    run = run_pty([], home=home, cwd=folder, cols=80, rows=24, steps=(Step(b"q", until=("poisson labs", "q quit")),), timeout=90)
    assert run.code == 0, run.err[-500:]
    assert "poisson-prove · home" not in strip_escapes(run.out)
