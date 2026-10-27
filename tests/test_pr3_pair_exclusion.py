"""A replicate set with an errored arm past the declared pair keeps its pair.

Read together, PR61 and PR63 say two different things about
one broken replicate set. PR63 is the k-metrics' rule: a set is eligible for ``agree@j`` and
``MS@j`` only when all ``k`` of its calls returned, and a set with fewer is excluded whole,
never analysed at the ``j`` its calls reached. PR61 is the pair analysis' rule: the declared
pair, arms ``a`` and ``b``, carries the whole of the pair analysis, and arms ``3..k`` move no byte of
it. So a set whose error sits in arm ``3..k`` is out of the k-metrics and its declared pair is
in the 2x2, because both of the pair's own arms returned.

Dropping such a set from both is the failure these tests catch: one item whose fifth call was an
HTTP 529 while its declared pair returned 0.62 and 0.64, both acting under ``p > c`` at a cut of
0.60, would leave the 2x2 one pair short. The store below is that set's shape in miniature: six items in one sweep, ``k = 5``, a ``gt`` cut at 0.60, one set with arm 5 errored
and its pair at 0.62 and 0.64.

The store helpers are ``tests/test_pr3_replicates.py``'s, imported and not copied, so this file
reads stored rows exactly as those tests do. Every test name starts ``test_prN_``.
"""

import dataclasses
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import test_pr3_replicates as R
from poisson_prove import paired

GT = ((R.CUT, R.THRESHOLD, "gt"),)
ERROR = "HTTP 529: <none>"
BROKEN = f"{R.CUT}-i005"


def rows_with_error_on(label: str) -> list[R.KRow]:
    """Six items. The first two flip in the declared pair, one each way; two are concordant at
    0; one is concordant at 1 on ``HI``; the sixth is the broken set, its pair at 0.62 and 0.64,
    both above the 0.60 cut, and its ``label`` arm errored."""
    rows = R.k_rows(6, lambda i: [(1, 0, 1, 1, 1), (0, 1, 1, 1, 1), (1, 1, 1, 1, 1),
                                  (0, 0, 0, 0, 0), (0, 0, 0, 0, 0), (1, 1, 1, 1, 1)][i])
    rows[5] = dataclasses.replace(
        rows[5], values=("0.62", "0.64", R.HI, R.HI, R.HI), error={label: ERROR},
    )
    return rows


def run(tmp_path: Path, label: str) -> tuple[Any, Any, Any]:
    decl = R.declaration(cuts=GT)
    assertion = paired.assert_pairs(R.make_k_store(tmp_path, rows_with_error_on(label)), decl)
    (cut,) = paired.analyse(assertion).cuts
    (replicate,) = paired.replicates(assertion)
    return assertion, cut, replicate


def two_by_two(cut: Any) -> tuple[int, int, int, int, int]:
    (s,) = cut.per_sweep
    return int(s["n11"]), int(s["n10"]), int(s["n01"]), int(s["n00"]), int(s["n"])


@pytest.mark.parametrize("label", ["5", "4", "3"])
def test_pr61_an_errored_arm_past_the_pair_keeps_the_declared_pair_in_the_pair_analysis(
    tmp_path: Path, label: str
) -> None:
    """The broken set's pair is concordant at 1, so it lands in ``n11``: 2 there, not 1, and
    six pairs, not five. Every pair statistic moves with it."""
    _, cut, _ = run(tmp_path, label)
    assert two_by_two(cut) == (2, 1, 1, 2, 6)
    assert cut.pooled["n"] == {"items": 6, "sweeps": 1}
    assert cut.pooled["flip_rate"]["estimate"] == pytest.approx(2 / 6)
    assert cut.ties == {"a": 0, "b": 0}
    # No declared pair is ineligible, so the pair analysis' ineligibility rate is zero (PR22).
    assert cut.pooled["ineligibility_rate"] == 0.0


@pytest.mark.parametrize("label", ["5", "4", "3"])
def test_pr63_the_same_set_is_still_excluded_whole_from_the_k_metrics(
    tmp_path: Path, label: str
) -> None:
    """All k, or none: five sets are eligible for ``agree@j`` and ``MS@j``, the broken one is
    in ``excluded`` with its cause and the arm that failed, and ``agree@2`` is read on the five
    whole sets only (two flip of five)."""
    assertion, _, replicate = run(tmp_path, label)
    (row,) = assertion.excluded.to_dict("records")
    assert (row["cluster"], row["cause"], row["arm"], row["detail"]) == (
        BROKEN, "errored", label, ERROR,
    )
    assert replicate.counts["eligible_sets"] == {"S1": 5}
    assert replicate.counts["items"] == 5
    assert replicate.counts["excluded_by_arm"][label] == 1
    assert replicate.agree["primary"]["j2"]["estimate"] == pytest.approx(3 / 5)
    assert replicate.agree["primary"]["j5"]["estimate"] == pytest.approx(3 / 5)


@pytest.mark.parametrize("label", ["a", "b"])
def test_pr61_an_errored_arm_inside_the_pair_still_drops_the_pair(
    tmp_path: Path, label: str
) -> None:
    """The other side of the line: when the error is in arm ``a`` or ``b`` the declared pair
    did not return, and it is out of the 2x2 as PR19 has it."""
    assertion, cut, replicate = run(tmp_path, label)
    assert two_by_two(cut) == (1, 1, 1, 2, 5)
    assert cut.pooled["ineligibility_rate"] == pytest.approx(1 / 6)
    assert BROKEN not in set(assertion.pairs["cluster"])
    assert replicate.counts["eligible_sets"] == {"S1": 5}


def test_pr61_the_broken_sets_pair_values_are_the_stored_literals(tmp_path: Path) -> None:
    """The pair is read as ``Decimal`` from the stored literal, as every other pair is (PR23);
    0.62 and 0.64 are both above the cut under ``gt``."""
    assertion, _, _ = run(tmp_path, "5")
    kept = assertion.pairs[assertion.pairs["cluster"] == BROKEN]
    assert len(kept) == 1
    assert (kept.iloc[0]["value_a"], kept.iloc[0]["value_b"]) == (Decimal("0.62"), Decimal("0.64"))


def test_pr61_padding_arms_three_to_k_never_rounds_a_stamp_through_a_float(tmp_path: Path) -> None:
    """The kept set carries ``None`` for the stamps of arms 3 to 5. A frame column holding a
    ``None`` beside whole numbers is float64, and ``EPOCH + 500_000`` does not survive a float
    (it reads ``...499968``), so every stamp on ``pairs`` is a whole ``int`` equal to the stored
    one, and the padded ones are ``None``."""
    assertion, _, _ = run(tmp_path, "5")
    frame = assertion.pairs
    whole = frame[frame["cluster"] != BROKEN]
    for label in R.labels(R.K):
        assert [(type(v), v) for v in whole[f"start_ns_{label}"]] == [(int, R.EPOCH)] * 5, label
        assert [(type(v), v) for v in whole[f"end_ns_{label}"]] == [(int, R.EPOCH + 500_000)] * 5, label
    kept = frame[frame["cluster"] == BROKEN].iloc[0]
    assert (kept["start_ns_a"], kept["end_ns_a"]) == (R.EPOCH, R.EPOCH + 500_000)
    assert (kept["start_ns_b"], kept["end_ns_b"]) == (R.EPOCH, R.EPOCH + 500_000)
    assert all(kept[f"{edge}_ns_{label}"] is None for edge in ("start", "end") for label in ("3", "4", "5"))
