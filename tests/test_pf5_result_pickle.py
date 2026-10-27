"""PF5: a comparison result pickles, and the copy is equal to it, whether or not it was read.

The result builds its document and its
tree when first read, and must still pickle, and round-trip equal, before anything has read it, by
building itself in full when pickled. ``json.dumps`` on an unread result stays unsupported
(``to_json()`` is the document). Added beside the frozen tests, without editing
them.
"""

from __future__ import annotations

import io
import os
import pickle
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

SALT = "5a1f0c3b9e7d2468"
SPEC = """\
target = "poisson_prove.examples.mock_agent:rollout"
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = 20

[axes.task_id]
type = "categorical"
values = ["search", "refund"]

[axes.tool_fail_rate]
type = "continuous"
values = [0.3, 0.55]

[declare]
failures = ["timeout", "violated"]
"""


@contextmanager
def inside(folder: Path) -> Iterator[None]:
    before = os.getcwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(before)


def sweep(folder: Path, *argv: str) -> None:
    from poisson_prove import cli

    out, err = io.StringIO(), io.StringIO()
    with inside(folder):
        code = cli.main(
            ["--store", "prove-runs", "sweep", "spec.toml", "--yes", "--max-mde", "1", *argv],
            stdout=out, stderr=err, stdin=io.StringIO(),
        )
    assert code == 0, (out.getvalue(), err.getvalue())


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Two paired runs of a 2 x 2 design of the keyless mock agent, the patched one second."""
    folder = tmp_path_factory.mktemp("pickle")
    (folder / "spec.toml").write_text(SPEC, encoding="utf-8")
    sweep(folder, "--salt", SALT)
    sweep(
        folder, "--target", "poisson_prove.examples.mock_agent:rollout_patched",
        "--pair-with", "latest",
    )
    return folder / "prove-runs"


@pytest.mark.parametrize("read", [False, True], ids=["unread", "read"])
def test_pf5_a_comparison_and_a_check_pickle_and_round_trip_equal_read_or_not(store: Path, read: bool) -> None:
    from poisson_prove import compare

    results = [
        compare.diff(store),
        compare.check(store, events=["violated"], fail_on="any"),
    ]
    if read:
        for result in results:
            result.to_json()
            _ = (result.rows, result.fragility, result.tree)
    for result in results:
        copy = pickle.loads(pickle.dumps(result))
        assert type(copy) is type(result)
        assert copy == result
    diffed, checked = (pickle.loads(pickle.dumps(r)) for r in results)
    assert diffed.tree is not None and checked.passed == results[1].passed
    # A copy of an unread result and a copy of a read one are the same comparison.
    assert diffed == compare.diff(store)
