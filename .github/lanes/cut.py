"""A pytest plugin: run one part of what the marker expression selected, cut by test.

pytest -p cut --cut INDEX/TOTAL -m EXPRESSION tests
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest


def part(ids: Sequence[str], index: int, total: int) -> list[str]:
    if total < 1 or not 1 <= index <= total:
        raise ValueError(f"part {index} of {total}")
    return [test for i, test in enumerate(ids) if i % total == index - 1]


def pytest_addoption(parser: Any) -> None:
    parser.addoption("--cut", default=None)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    value = config.getoption("--cut")
    if value is None:
        return
    try:
        index, total = (int(x) for x in value.split("/"))
        kept = set(part([item.nodeid for item in items], index, total))
    except ValueError as error:
        raise pytest.UsageError(f"--cut {value}: {error}") from None
    config.hook.pytest_deselected(items=[item for item in items if item.nodeid not in kept])
    items[:] = [item for item in items if item.nodeid in kept]
