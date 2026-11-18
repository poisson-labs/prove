"""First run M3 -- ``init --demo``: an interrupt before any file is in place (section 4.3).

Added by the build session beside the frozen ``test_frs_m3_demo.py``, which pins an interrupt at
the second file. This is the case before it: Ctrl-C as the first file would be moved into place.
The command then says that nothing was written, so nothing may be left: no file, no file written
aside, and no folder that ``--repo`` made.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from test_pf11_setup_agent import run, snapshot


@pytest.mark.parametrize("repo_is_there", [False, True], ids=["--repo is missing", "--repo is there"])
def test_an_interrupt_before_the_first_file_leaves_nothing(repo_is_there: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "here"
    cwd.mkdir()
    repo = tmp_path / "new" / "deeper"
    if repo_is_there:
        repo.mkdir(parents=True)
    before = snapshot(tmp_path)

    def interrupted(*args: Any, **kwargs: Any) -> Any:
        raise KeyboardInterrupt

    with monkeypatch.context() as patched:
        patched.setattr(os, "replace", interrupted)
        patched.setattr(os, "rename", interrupted)
        stopped = run(cwd, "init", "--demo", "--with-setup", "--repo", repo)
    assert stopped.code == 130, stopped
    assert "nothing was written" in stopped.out, stopped
    assert snapshot(tmp_path) == before
