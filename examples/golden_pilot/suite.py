"""The golden suite: HumanEval as a tuple of :class:`Golden`.

``load()`` reads one JSONL file in the HumanEval shape -- ``task_id``, ``prompt``,
``entry_point``, ``canonical_solution``, ``test``, one object per line -- plain or gzipped.
``fetch_suite.py`` puts the real one at ``suite/HumanEval.jsonl.gz``; nothing here fetches.

Escape hatch (spec section 3): MBPP-sanitized is a drop-in -- same five fields, same loader,
and ``make_toml.py`` regenerates the ``task_id`` axis from whatever this returns.
"""

from __future__ import annotations

import gzip
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import IO, Any

#: The HumanEval fields, in the order the JSONL carries them.
FIELDS = ("task_id", "prompt", "entry_point", "canonical_solution", "test")

#: Where ``fetch_suite.py`` writes, and what ``load(None)`` reads without the environment.
DEFAULT_SUITE = Path(__file__).resolve().parent / "suite" / "HumanEval.jsonl.gz"

#: Overrides ``DEFAULT_SUITE`` for ``load(None)``. The oracle points it at its mini-suite.
SUITE_VAR = "GOLDEN_PILOT_SUITE"


class SuiteError(ValueError):
    """Raised when a suite file is missing, unreadable, or not in the HumanEval shape."""


@dataclass(frozen=True)
class Golden:
    """One problem: a prompt to complete, an entry point, a reference body, and a check."""

    task_id: str
    prompt: str
    entry_point: str
    canonical_solution: str
    test: str


def suite_path(path: str | Path | None = None) -> Path:
    """The file ``load(path)`` will read. ``None`` means the environment, else the default."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(SUITE_VAR) or DEFAULT_SUITE)


def _open(file: Path) -> IO[str]:
    if file.suffix == ".gz":
        return gzip.open(file, "rt", encoding="utf-8")
    return file.open("rt", encoding="utf-8")


def _rows(file: Path) -> Iterator[dict[str, Any]]:
    with _open(file) as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise SuiteError(f"{file}:{number} is not JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise SuiteError(f"{file}:{number} is not a JSON object")
            missing = [name for name in FIELDS if name not in row]
            if missing:
                raise SuiteError(f"{file}:{number} is missing {', '.join(missing)}")
            yield row


@lru_cache(maxsize=8)
def _load_resolved(key: str) -> tuple[Golden, ...]:
    """Keyed by the resolved path, so one gzip read serves a whole Modal batch.

    A batch is 64 episodes and an arm is 10,496; re-reading and re-decompressing the suite per
    episode would be the loop's largest avoidable cost. Goldens are frozen and the tuple is
    shared, so the cache hands out no mutable state. Keying on the resolved path (not on the
    ``None`` argument) keeps a changed ``GOLDEN_PILOT_SUITE`` a different entry.
    """
    file = Path(key)
    if not file.is_file():
        raise SuiteError(f"no suite at {file}; run fetch_suite.py once, or set {SUITE_VAR}")
    goldens = tuple(Golden(**{name: row[name] for name in FIELDS}) for row in _rows(file))
    if not goldens:
        raise SuiteError(f"{file} holds no problems")
    ids = [golden.task_id for golden in goldens]
    if len(set(ids)) != len(ids):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        raise SuiteError(f"{file} repeats task_id(s): {', '.join(duplicates)}")
    return goldens


def load(path: str | Path | None = None) -> tuple[Golden, ...]:
    """Every problem in file order. Ids are unique and stable across loads."""
    return _load_resolved(str(suite_path(path).resolve()))


def by_id(task_id: str, path: str | Path | None = None) -> Golden:
    """The one problem the sweep's ``task_id`` axis names."""
    for golden in load(path):
        if golden.task_id == task_id:
            return golden
    raise SuiteError(f"no golden with task_id {task_id!r} in {suite_path(path)}")
