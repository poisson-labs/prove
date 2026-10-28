"""The paired test (``mcnemar_bh``) on two runs where some episodes have no match in the other run.

A pair is one replicate of one condition stored in both runs. ``diff`` reads the paired row's change,
its discordant counts, its p-value, its interval and its detection limits off the matched pairs
alone, so the same comparison with the unmatched episodes taken out of both stores prints the same
figures, and its two shares are the matched pairs' shares, whose difference is the change. The
counts of each run's own episodes (``n_a``, ``n_b``) still count every episode.

The fixture: one condition, replicates 0 to 19 in both runs. On those twenty pairs A ended in
``fell`` on 0 to 3 and B on 0 to 11, so 8 pairs had the event in B only, none in A only, 4 in both
and 8 in neither: a rise of 8/20. A also holds twelve replicates of its own that all fell, and B
twelve of its own that did not, so over each run's own episodes A's share is 16/32 and B's 12/32,
a fall.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from poisson_prove import cli
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store

EVENT = "fell"
MATCHED = range(20)
FELL_A, FELL_B = range(4), range(12)
OWN_A, OWN_B = range(20, 32), range(40, 52)
#: The row's figures that are the matched pairs' own: equal with and without the unmatched episodes.
PAIRED_FIELDS = ("pairs", "n01", "n10", "delta", "p", "q", "direction", "verdict", "ci_lo", "ci_hi",
                 "mde_rise", "mde_fall", "mde_rise_note", "mde_fall_note", "mde_test")


def write_run(store: Store, run_id: str, outcomes: dict[int, str]) -> None:
    store.create_run(RunManifest(
        run_id=run_id, target_id="paired-unmatched@v0", t_unit="steps", run_salt="paired-unmatched-salt",
        axis_types={"task": "categorical"}, backend="local", environment={},
    ))
    store.append(run_id, [
        EpisodeRecord.from_episode(
            Episode(outcome=outcome, t=3.0, horizon=10.0, meta={}),
            run_id=run_id, config={"task": "x"}, seed=index, replicate_index=index, wall_time=0.1,
        )
        for index, outcome in outcomes.items()
    ])
    store.mark_complete(run_id)


def paired_row(root: Path, *, unmatched: bool) -> dict[str, Any]:
    """The one condition's row of ``diff --method mcnemar_bh --json`` on the fixture, with or
    without each run's unmatched replicates."""
    a = {i: EVENT if i in FELL_A else "ok" for i in MATCHED}
    b = {i: EVENT if i in FELL_B else "ok" for i in MATCHED}
    if unmatched:
        a |= {i: EVENT for i in OWN_A}
        b |= {i: "ok" for i in OWN_B}
    store = Store(root)
    write_run(store, "run-a", a)
    write_run(store, "run-b", b)
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["--store", str(root), "diff", "run-a", "run-b", "--event", EVENT, "--method", "mcnemar_bh", "--json"],
                    stdout=out, stderr=err, stdin=io.StringIO())
    assert code == 0, err.getvalue()
    doc = json.loads(out.getvalue())
    assert doc["method"] == "mcnemar_bh", doc["method"]
    (row,) = doc["by_event"][EVENT]["cells"]
    return row


def test_with_unmatched_episodes_the_paired_row_is_read_off_the_matched_pairs_alone(tmp_path: Path) -> None:
    full = paired_row(tmp_path / "with-unmatched", unmatched=True)
    matched = paired_row(tmp_path / "matched-only", unmatched=False)
    both_fell = len(set(FELL_A) & set(FELL_B))
    only_b, only_a = len(FELL_B) - both_fell, len(FELL_A) - both_fell
    assert (full["pairs"], full["n01"], full["n10"]) == (len(MATCHED), only_b, only_a) == (20, 8, 0), full
    assert full["delta"] == (only_b - only_a) / len(MATCHED) == 0.4
    assert full["direction"] == "higher"
    # Both shares over the matched pairs, and the change their difference.
    assert matched["share_a"]["value"] == len(FELL_A) / len(MATCHED)
    assert matched["share_b"]["value"] == len(FELL_B) / len(MATCHED)
    assert abs(full["delta"] - (matched["share_b"]["value"] - matched["share_a"]["value"])) <= 1e-12
    assert {k: full[k] for k in PAIRED_FIELDS} == {k: matched[k] for k in PAIRED_FIELDS}
    # Each run's own episodes are still counted as its own.
    assert (full["n_a"], full["n_b"], full["events_a"], full["events_b"]) == (32, 32, 16, 12), full
