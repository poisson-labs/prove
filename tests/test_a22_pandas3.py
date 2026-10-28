"""Invariants V1-V15 of the pandas 3 port: every nullable string column of the store reads a stored
null back as ``None``, the diff's coverage frame rebuilds its ``cause`` column from the records list, and the
dependency parser reads PEP 508 names.

**This file runs under two pandas versions and the invariant set does not partition between
them.** The port's claim is a range -- *a stored null reads back as* ``None`` *on every pandas
this package supports* -- and a single run proves one point in it. Every invariant here is
asserted under both:

- **pandas 2.3.3.** The store normalisation and the coverage rebuild are identities here
  (measured), so the read-path and coverage tests check the port's "no-op on pandas 2" claim:
  it is asserted rather than assumed. V14 and V15 do not depend on the pandas version.
- **pandas 3.0.5.** V1, V2, V3, V7, V9 and V11 catch an unported read as well, because
  ``pyarrow.Table.to_pandas`` gives a ``str`` column with ``NaN`` for null and
  ``DataFrame.from_records`` replaces a mixed column's ``None`` before an ``astype(object)``
  guard in ``diff.py`` ever runs.

Ten tests, one per invariant for ten of the fifteen (V1 holds V5's columns, V13 is gone, and V8, V10
and V12 have none here), in both versions: 10 + 10 = 20 ids over the two runs against the file's own
10, because no invariant is version-specific. An invariant
that could only be asserted under one pandas would be named here with the version it is missing
from; there is none.

**The two fixtures have opposite rules and that is the trap this file exists to avoid.** A
column read from Arrow is ``str`` dtype on pandas 3 whatever its null pattern, so the
two-record store below exposes the read-path defect with a single null row. A column built by
``DataFrame.from_records`` is ``object`` when the **whole** column is ``None``, so an all-holes
or all-comparable coverage frame hides the diff defect completely -- a pair whose coverage has no
holes lets an unported build pass V9. ``mixed_pair`` therefore carries comparable cells
**and** one hole of each of the five causes, and that is not optional.

Fixture limits, stated rather than left to be rediscovered:

- ``two_records`` says nothing about the coverage frame; its frames never reach the coverage rebuild.
- ``mixed_pair`` says nothing about the store's own null columns beyond what it reads back;
  its coverage rows come from the raw frames, not from ``censor()``.
- Nothing here measures a live provider or a Modal run.

Every reference to a name under test sits **inside** a test function, never at module level, so
``--collect-only`` gives an exact count even when one is missing.
"""

from __future__ import annotations

import json
import tomllib
import warnings
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from packaging.requirements import Requirement
from packaging.version import Version

import poisson_prove.diff as diff_mod
from poisson_prove.episode import Episode
from poisson_prove.store import EpisodeRecord, RunManifest, Store, config_hash

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

#: The two-record store. One errored row -- ``outcome`` null, ``error`` set, and the three
#: nullable floats null with it, which ``EpisodeRecord.__post_init__`` requires -- and one row
#: with an outcome, whose ``error`` is the null in the other column. Both nullable string
#: columns therefore carry a null and a string in the same frame.
RUN = "a22"
ERRORED_CONFIG: dict[str, Any] = {"f": 0.1}
OUTCOME_CONFIG: dict[str, Any] = {"f": 0.9}
ERROR_TEXT = "boom"
OUTCOME_TEXT = "fell"
NULLABLE_FLOAT_COLUMNS = ("t", "horizon", "confidence")
POISON = "not json"

#: The mixed pair. ``(outcome rows in A, errored rows in A, outcome rows in B, errored in B)``
#: per cell, built so the coverage frame carries comparable rows beside one hole of each of
#: the five values its ``cause`` column can take. ``mixed`` is comparable **and** has errored rows in both
#: arms, which is the row a build that confuses "has errored rows" with "is a hole" gets wrong.
PAIR_A, PAIR_B = "cov-a", "cov-b"
PAIR_SALT = "a22-coverage"
PAIR_HORIZON = 10.0
N = 8
PAIR_CELLS: dict[str, tuple[int, int, int, int]] = {
    "base": (N, 0, N, 0),
    "mixed": (6, 2, 5, 3),
    "only-a": (N, 0, 0, 0),
    "only-b": (0, 0, N, 0),
    "err-a": (0, N, N, 0),
    "err-b": (N, 0, 0, N),
    "err-both": (0, N, 0, N),
}
EXPECTED_COMPARABLE = 2
EXPECTED_HOLES = 5
#: The five hole causes, one per hole cell above.
HOLE_CAUSES = ("only_a", "only_b", "no_outcome_a", "no_outcome_b", "no_outcome_both")

#: The dependency parser's negative. A naive parser, ``d.split("[")[0].split(">")[0].split("=")[0]``
#: plus ``.strip().lower()``, strips neither ``<`` nor ``~=`` nor ``!=``, and ``pandas>=2,<3``
#: survives it only because ``>`` happens to come first. Four of these five come out with an
#: operator attached under it.
SYNTHETIC_REQUIREMENTS = ["pandas<3", "numpy~=2.0", "scipy!=1.0", "pyarrow[compute]>=1", "pandas >= 2"]
CORE_NAMES = {"numpy", "pandas", "scipy", "pyarrow"}
PANDAS_ADMITS = ("3.0.5", "2.3.3")


# ---------- fixtures: data construction only, never an assertion ----------


@pytest.fixture
def two_records(tmp_path: Path) -> Store:
    """One errored row and one row with an outcome, through the store's own writer."""
    store = Store(tmp_path / "store")
    store.create_run(
        RunManifest(
            run_id=RUN, target_id="policy@abc123", t_unit="steps", run_salt="a22-test",
            axis_types={"f": "continuous"}, backend="local", environment={"python": "3.11"},
        )
    )
    store.append(
        RUN,
        [
            EpisodeRecord.errored(
                run_id=RUN, config=ERRORED_CONFIG, seed=1, replicate_index=0,
                error=ERROR_TEXT, wall_time=0.1,
            ),
            EpisodeRecord.from_episode(
                Episode(outcome=OUTCOME_TEXT, t=3.0, horizon=PAIR_HORIZON, confidence=0.5, meta={"k": 1}),
                run_id=RUN, config=OUTCOME_CONFIG, seed=2, replicate_index=0, wall_time=0.1,
            ),
        ],
    )
    return store


@pytest.fixture
def mixed_pair(tmp_path: Path) -> Any:
    """Two runs whose coverage frame has comparable rows and all five hole causes."""
    store = Store(tmp_path / "pair")
    for run_id, index in ((PAIR_A, 0), (PAIR_B, 2)):
        store.create_run(
            RunManifest(
                run_id=run_id, target_id="synthetic@v0", t_unit="steps", run_salt=PAIR_SALT,
                axis_types={"task": "categorical"}, backend="synthetic", environment={},
            )
        )
        records = []
        for task, counts in PAIR_CELLS.items():
            with_outcome, errored = counts[index], counts[index + 1]
            config = {"task": task}
            for k in range(with_outcome):
                records.append(
                    EpisodeRecord.from_episode(
                        Episode(outcome="fell" if k % 2 == 0 else "survived", t=3.0, horizon=PAIR_HORIZON, meta={}),
                        run_id=run_id, config=config, seed=k, replicate_index=k, wall_time=0.1,
                    )
                )
            for k in range(with_outcome, with_outcome + errored):
                records.append(
                    EpisodeRecord.errored(
                        run_id=run_id, config=config, seed=k, replicate_index=k,
                        error=ERROR_TEXT, wall_time=0.1,
                    )
                )
        if records:
            store.append(run_id, records)
        store.mark_complete(run_id)
    with warnings.catch_warnings():  # the unpaired-analysis warning; no test here is about it
        warnings.simplefilter("ignore", diff_mod.UnpairedAnalysis)
        return diff_mod.multi_diff(
            store.read(PAIR_A), store.read(PAIR_B), events=("fell",), method="fisher_bh",
            manifest_a=store.manifest(PAIR_A), manifest_b=store.manifest(PAIR_B),
        )


# ---------- V1-V7: the read path ----------


def test_v1_a_stored_null_reads_back_as_none_in_every_nullable_string_column(two_records: Store, tmp_path: Path) -> None:
    """``is None``, not ``pd.isna``. Under pandas 3 an unported ``to_pandas`` gives a ``str``
    column whose null is ``NaN``, on which ``row.outcome is not None`` is true and wrong -- the
    trap ``trace`` and ``trace_obs`` meet twice over. The columns are read off the stored file's
    own schema: every nullable ``string`` field that a read shows as a column (``trace`` shows under
    ``trace="envelope"``; ``trace_obs`` shows as no column) is null in at least one stored row and
    reads back ``None`` there, so a field added to the format and not to the read path fails here:
    a test of the new field spelled naturally passes on a NaN."""
    frame = two_records.read(RUN)
    by_hash = {str(h): i for i, h in enumerate(frame["config_hash"])}
    errored, with_outcome = by_hash[config_hash(ERRORED_CONFIG)], by_hash[config_hash(OUTCOME_CONFIG)]
    assert frame.loc[errored, "outcome"] is None
    assert frame.loc[with_outcome, "error"] is None
    assert frame.loc[errored, "error"] == ERROR_TEXT
    assert frame.loc[with_outcome, "outcome"] == OUTCOME_TEXT
    (part,) = (tmp_path / "store" / RUN / "episodes").glob("part-*.parquet")
    table = pq.read_table(part)
    nullable = {f.name for f in table.schema if f.nullable and f.type == pa.string()}
    assert {"outcome", "error", "trace", "trace_obs"} <= nullable, nullable
    read_null = set()
    for read in (frame, two_records.read(RUN, trace="envelope")):
        rows = {str(h): i for i, h in enumerate(read["config_hash"])}
        for stored in table.to_pylist():
            for column in nullable & set(read.columns):
                if stored[column] is None:
                    assert read.loc[rows[stored["config_hash"]], column] is None, column
                    read_null.add(column)
    assert read_null == nullable - {"trace_obs"}, nullable - read_null


def test_v2_the_projection_and_the_keys_mask_each_keep_the_none(two_records: Store) -> None:
    """The projection and the ``keys=`` mask each rebuild the frame; a normalisation applied
    before either is undone by it, which is why the port sits after the sort and the reset."""
    projected = two_records.read(RUN, meta=False)
    by_hash = {str(h): i for i, h in enumerate(projected["config_hash"])}
    assert projected.loc[by_hash[config_hash(ERRORED_CONFIG)], "outcome"] is None
    assert projected.loc[by_hash[config_hash(OUTCOME_CONFIG)], "error"] is None
    masked = two_records.read(RUN, keys=[(config_hash(ERRORED_CONFIG), 0)])
    assert len(masked) == 1
    assert masked.loc[0, "outcome"] is None
    assert masked.loc[0, "error"] == ERROR_TEXT


def test_v3_the_two_nullable_string_columns_are_object_dtype_on_every_frame_shape(two_records: Store, tmp_path: Path) -> None:
    """Three shapes, because ``pyarrow`` gives ``str`` on pandas 3 for all three: the populated
    frame, a run with no parts at all, and the empty-``keys`` short circuit that never reaches
    the reader."""
    populated = two_records.read(RUN)
    assert (populated["outcome"].dtype, populated["error"].dtype) == (object, object)
    empty_store = Store(tmp_path / "empty")
    empty_store.create_run(
        RunManifest(
            run_id="none", target_id="policy@abc123", t_unit="steps", run_salt="a22-test",
            axis_types={"f": "continuous"}, backend="local", environment={},
        )
    )
    no_parts = empty_store.read("none")
    assert len(no_parts) == 0
    assert (no_parts["outcome"].dtype, no_parts["error"].dtype) == (object, object)
    no_keys = two_records.read(RUN, keys=[])
    assert len(no_keys) == 0
    assert (no_keys["outcome"].dtype, no_keys["error"].dtype) == (object, object)


def test_v4_the_three_nullable_float_columns_read_back_nan_and_not_none(two_records: Store) -> None:
    """The negative that stops a build from finishing the job on the floats.
    ``t``, ``horizon`` and ``confidence`` are NaN on pandas 2 and on pandas 3 alike; three
    frozen tests already spell them ``pd.isna`` and the port does not move them."""
    frame = two_records.read(RUN)
    by_hash = {str(h): i for i, h in enumerate(frame["config_hash"])}
    errored = by_hash[config_hash(ERRORED_CONFIG)]
    for column in NULLABLE_FLOAT_COLUMNS:
        value = frame.loc[errored, column]
        assert pd.isna(value) and value is not None, column


def test_v6_tally_succeeds_on_a_store_whose_meta_is_not_json_and_read_raises(tmp_path: Path) -> None:
    """``tally`` and the store's lookup of the keys resume skips read through ``to_pylist``, never
    ``to_pandas``, so the port cannot reach them and resume is untouched. A build that normalises
    by routing either through the frame fails here, not in the field."""
    store = Store(tmp_path / "poison")
    store.create_run(
        RunManifest(
            run_id=RUN, target_id="policy@abc123", t_unit="steps", run_salt="a22-test",
            axis_types={"f": "continuous"}, backend="local", environment={},
        )
    )
    store.append(
        RUN,
        [
            EpisodeRecord.from_episode(
                Episode(outcome=OUTCOME_TEXT, t=1.0, horizon=PAIR_HORIZON, meta={"k": 1}),
                run_id=RUN, config=ERRORED_CONFIG, seed=0, replicate_index=0, wall_time=0.1,
            )
        ],
    )
    part = next((tmp_path / "poison" / RUN / "episodes").glob("part-*.parquet"))
    table = pq.read_table(part)
    index = table.schema.get_field_index("meta")
    table = table.set_column(index, table.schema.field(index), pa.array([POISON] * table.num_rows, pa.string()))
    pq.write_table(table, part)
    assert store.tally(RUN).rows == 1
    assert store.tally(RUN).with_outcome == 1
    with pytest.raises(ValueError):
        store.read(RUN)


def test_v7_a_retained_run_strips_the_unretained_rows_trace_and_its_error_is_none(tmp_path: Path) -> None:
    """The retention path and the null path meet on one row: ``append`` pops ``trace`` out of
    ``meta`` for an outcome ``retain_traces_for`` does not name, and the same row's ``error`` is
    the null the read path has to bring back."""
    store = Store(tmp_path / "retain")
    store.create_run(
        RunManifest(
            run_id=RUN, target_id="policy@abc123", t_unit="steps", run_salt="a22-test",
            axis_types={"f": "continuous"}, backend="local", environment={},
            retain_traces_for=("survived",),
        )
    )
    store.append(
        RUN,
        [
            EpisodeRecord.from_episode(
                Episode(outcome=OUTCOME_TEXT, t=1.0, horizon=PAIR_HORIZON, meta={"trace": {"spans": [1]}, "k": 1}),
                run_id=RUN, config=ERRORED_CONFIG, seed=0, replicate_index=0, wall_time=0.1,
            )
        ],
    )
    row = store.read(RUN).loc[0]
    assert "trace" not in row["meta"]
    assert row["meta"] == {"k": 1}
    assert row["error"] is None


# ---------- V9, V11: the coverage frame and what is printed ----------


def test_v9_coverage_cause_is_none_on_every_comparable_row_and_a_named_cause_on_every_hole(mixed_pair: Any) -> None:
    """An all-comparable or all-holes coverage frame cannot express this: ``from_records`` keeps
    ``None`` when the whole column is ``None``, measured, so a pair with no holes passes on an
    unported build. The fixture carries both, and all five causes."""
    coverage = mixed_pair.coverage
    comparable = coverage[coverage["comparable"]]
    holes = coverage[~coverage["comparable"]]
    assert (len(comparable), len(holes)) == (EXPECTED_COMPARABLE, EXPECTED_HOLES)
    assert all(cause is None for cause in comparable["cause"])
    assert sorted(holes["cause"]) == sorted(HOLE_CAUSES)
    assert coverage["cause"].dtype == object


def test_v11_the_diff_json_payload_dumps_with_allow_nan_false(mixed_pair: Any) -> None:
    """``diff --json`` dumps at ``cli.py:1122`` with ``allow_nan`` at its default, so an
    unported build under pandas 3 writes a bare ``NaN`` token and the artifact is not valid
    JSON. This pins that closed without changing the call."""
    payload = mixed_pair.to_json()
    assert json.dumps(payload, allow_nan=False)
    assert sum(record["cause"] is None for record in payload["coverage"]) == EXPECTED_COMPARABLE


# ---------- V14-V15: the declared dependencies ----------


def test_v14_the_real_core_dependencies_are_the_four_math_names_and_packaging_is_in_dev() -> None:
    """The core dependencies as ``pyproject.toml`` declares them. ``packaging`` is declared
    rather than leaned on through pytest."""
    data = tomllib.loads(PYPROJECT.read_text())
    # Rich and Textual are core too, and threadpoolctl, which caps a worker's BLAS threads (PF10);
    # the math names are still all there.
    assert {Requirement(d).name.lower() for d in data["project"]["dependencies"]} == CORE_NAMES | {"rich", "textual", "threadpoolctl"}
    assert "packaging" in {Requirement(d).name.lower() for d in data["project"]["optional-dependencies"]["dev"]}


def test_v15_the_core_pandas_specifier_admits_3_0_5_and_2_3_3() -> None:
    """The cap is gone and the floor is not. A build that lifts ``<3`` by deleting the whole
    specifier passes the first half and fails the second."""
    data = tomllib.loads(PYPROJECT.read_text())
    specifiers = {Requirement(d).name.lower(): Requirement(d).specifier for d in data["project"]["dependencies"]}
    assert all(Version(v) in specifiers["pandas"] for v in PANDAS_ADMITS)
    assert Version("1.5.3") not in specifiers["pandas"]
