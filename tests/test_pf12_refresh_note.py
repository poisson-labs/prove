"""PF12: a save whose page refresh fails says so in one line and leaves the previous pages.

When a write's page refresh fails, the saving command prints one plain line on stderr saying the
pages were not refreshed and to run ``ui``; the previous pages stay as they are.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from conftest import skip_if_still_writable
from pf12_support import OLD, QS_A, QS_B, cli, copy_fixture, saved_id


def _listing(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_pf12_5_a_save_whose_refresh_fails_says_so_once_and_leaves_the_previous_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A store with a dashboard whose ``.poisson/`` cannot take a new tree (the artifacts folder
    still can): the save lands and prints its ``saved`` line, exit 0; stderr gains exactly one
    ``note:`` line saying the dashboard's pages were not refreshed and naming ``ui``; the pages
    stand byte for byte; the next ``ui`` builds them whole."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for name in ("POISSON_PROVE_STORE", "PROOFLOAD_STORE"):
        monkeypatch.delenv(name, raising=False)
    store = copy_fixture(OLD / "store", tmp_path / "prove-runs")
    first = cli(store, "diff", QS_A, QS_B, "--save")
    assert first.code == 0, first.err
    assert cli(store, "ui").code == 0
    ui = store / ".poisson" / "ui"
    previous = _listing(ui)
    comparisons = store / ".poisson" / "artifacts" / "comparison"
    dot = store / ".poisson"
    mode = dot.stat().st_mode
    # The descriptor already lists this version, so the save writes only under artifacts/;
    # the refresh needs a new tree beside ui/, which a read-only .poisson/ refuses.
    dot.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)
    try:
        skip_if_still_writable(dot)
        second = cli(store, "diff", QS_A, QS_B, "--q", "0.1", "--save")
    finally:
        dot.chmod(mode)
    assert second.code == 0, second.err
    assert first.code == 0 and second.out != "" and saved_id(second, "comparison", store)
    notes = [line for line in second.err.splitlines() if line.startswith("note: ")]
    assert len(notes) == 1, second.err
    assert "pages were not refreshed" in notes[0] and "poisson-prove ui" in notes[0], notes
    assert [line for line in second.err.splitlines() if not line.startswith("note: ")] == [], second.err
    assert _listing(ui) == previous
    assert len([p for p in comparisons.iterdir() if (p / "artifact.json").is_file()]) == 2
    rebuilt = cli(store, "ui")
    assert rebuilt.code == 0 and rebuilt.err == "", rebuilt.err
    index = json.loads(cli(store, "ui", "--json").out)["location"]
    assert index.startswith("file:///") and os.path.isfile(ui / "index.html")
    assert _listing(ui) != previous
