"""The gate's shard table: which test files each shard of the code suite runs.

    python .github/lanes/shards.py SHARD [--total N]

Reads the table from ``$SHARDS`` (the gate workflow's ``env``) and prints the pytest paths of one
shard, one per line. The table is one entry per shard: a name, a colon, and the test files it
runs, continued on indented lines. The numbered entries are the gate's test shards, and one of
them is the word ``rest``: every test file no other entry names, so a new test file runs there
with no change to the table. ``backends`` is the Burla and Modal fakes, which run in a job of
their own only when backend code changes (``backends_lane.py``), so ``rest`` leaves them out.
With ``--total N`` it also checks that the numbered shards are exactly ``1`` to ``N``, the shards
the workflow's matrix runs.

A file named twice, a name that is not a test file, no ``rest``, no ``backends``, or numbered
shards that are not ``1`` to ``N`` is an error: every test file of the suite runs in exactly one
shard or in the backends job.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REST = "rest"
BACKENDS = "backends"


def parse(text: str) -> dict[str, list[str]]:
    """``{name: [file, ...]}`` in table order."""
    table: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        if not line.strip():
            continue
        head = re.match(r"(\w+):(.*)", line)
        if head and not line[0].isspace():
            current = head.group(1)
            if current in table:
                raise ValueError(f"shard {current} is in the table twice")
            table[current] = head.group(2).split()
        elif current is None:
            raise ValueError(f"a line before the first shard: {line.strip()}")
        else:
            table[current] += line.split()
    return table


def problems(table: dict[str, list[str]], tests: list[str], total: int | None = None) -> list[str]:
    """What is wrong with ``table`` over the test files ``tests``; empty when nothing is."""
    out = []
    numbered = [name for name in table if name.isdigit()]
    if sorted(int(name) for name in numbered) != list(range(1, len(numbered) + 1)):
        out.append(f"the numbered shards are {numbered}, not 1 to {len(numbered)}")
    if total is not None and len(numbered) != total:
        out.append(f"the table has {len(numbered)} shards and the matrix runs {total}")
    rests = [name for name in numbered if table[name] == [REST]]
    if len(rests) != 1:
        out.append(f"{len(rests)} shards are {REST}; exactly one must be")
    if not table.get(BACKENDS):
        out.append(f"no {BACKENDS} entry")
    others = sorted(set(table) - set(numbered) - {BACKENDS})
    if others:
        out.append(f"entries that are neither numbered nor {BACKENDS}: {others}")
    seen: dict[str, str] = {}
    for name, files in table.items():
        if name in rests:
            continue
        for path in files:
            if path in seen:
                out.append(f"{path} is in {seen[path]} and {name}")
            seen[path] = name
            if path not in tests:
                out.append(f"{path} ({name}) is not a test file")
    return out


def paths(table: dict[str, list[str]], name: str, tests: list[str]) -> list[str]:
    """The pytest paths entry ``name`` runs."""
    if table[name] == [REST]:
        named = {path for files in table.values() for path in files if path != REST}
        return [path for path in tests if path not in named]
    return list(table[name])


def test_files() -> list[str]:
    return sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_*.py"))


def main(argv: list[str]) -> int:
    name = argv[0]
    total = int(argv[2]) if argv[1:2] == ["--total"] else None
    table, tests = parse(os.environ["SHARDS"]), test_files()
    wrong = problems(table, tests, total)
    if name not in table:
        wrong.append(f"the table has no entry {name}")
    if wrong:
        print("\n".join(wrong), file=sys.stderr)
        return 1
    print("\n".join(paths(table, name, tests)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
