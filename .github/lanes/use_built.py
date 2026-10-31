"""A pytest plugin: the packaging and hygiene tests read the release's own archives.

    PROVE_DIST=dist pytest -p use_built tests/test_pf7_packaging.py tests/test_pf8_public_hygiene.py

Those tests build a wheel and an sdist from the checkout once per run (``build_archives``). Under
this plugin each module's ``build_archives`` still runs, so the folder holds the tree it was built
from, and then the archives it built are replaced by the files in ``$PROVE_DIST``: the tests check
exactly the files the release workflow publishes.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


def pytest_collection_modifyitems(session: Any, config: Any, items: list[Any]) -> None:
    dist = Path(os.environ["PROVE_DIST"]).resolve()
    for module in {item.module for item in items if getattr(item, "module", None)}:
        original = getattr(module, "build_archives", None)
        if original is None or getattr(original, "_swapped", False):
            continue

        def swapped(folder: Path, _original: Any = original) -> None:
            _original(folder)
            for built in (folder / "dist").iterdir():
                built.unlink()
            for given in dist.iterdir():
                shutil.copy2(given, folder / "dist" / given.name)

        swapped._swapped = True  # type: ignore[attr-defined]
        module.build_archives = swapped
