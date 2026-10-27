import json
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, strategies as st
from poisson_prove import Episode
from poisson_prove.store import (
    DuplicateEpisode, EpisodeRecord, InvalidConfig, MetaNotSerializable,
    RunManifest, SchemaMismatch, Store, StoreError, config_hash,
)
# ---------- helpers ----------
def _manifest(run_id="r1", **kw) -> RunManifest:
    base = dict(run_id=run_id, target_id="policy@abc123", t_unit="steps",
                run_salt="salt", axis_types={"friction": "continuous"},
                backend="local", environment={"python": "3.11"})
    base.update(kw)
    return RunManifest(**base)
def _rec(run_id="r1", cfg=None, seed=0, rep=0, outcome="fell", t=3.0, horizon=10.0,
         confidence=None, meta=None) -> EpisodeRecord:
    cfg = cfg if cfg is not None else {"friction": 0.5}
    ep = Episode(outcome=outcome, t=t, horizon=horizon, confidence=confidence,
                 meta=meta or {})
    return EpisodeRecord.from_episode(ep, run_id=run_id, config=cfg, seed=seed,
                                      replicate_index=rep, wall_time=0.1)
# ---------- config_hash (I1, I2) ----------
def test_hash_is_16_hex():
    h = config_hash({"a": 1})
    assert len(h) == 16 and all(c in "0123456789abcdef" for c in h)
def test_hash_key_order_invariant():
    assert config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})
def test_hash_nested_order_invariant():
    assert config_hash({"x": {"a": 1, "b": 2}}) == config_hash({"x": {"b": 2, "a": 1}})
def test_hash_int_float_same_cell():
    assert config_hash({"push": 5}) == config_hash({"push": 5.0})
def test_hash_bool_distinct_from_int():
    assert config_hash({"flag": True}) != config_hash({"flag": 1})
def test_hash_numpy_scalars():
    assert config_hash({"a": np.float64(0.5), "b": np.int64(3)}) == config_hash({"a": 0.5, "b": 3})
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_hash_rejects_nonfinite(bad):
    with pytest.raises(InvalidConfig):
        config_hash({"a": bad})
def test_hash_rejects_nested_nonfinite():
    with pytest.raises(InvalidConfig):
        config_hash({"a": {"b": [1.0, float("nan")]}})
@given(st.dictionaries(st.text(min_size=1, max_size=6),
                       st.one_of(st.integers(-1000, 1000),
                                 st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False),
                                 st.text(max_size=6), st.booleans()),
                       min_size=1, max_size=5))
def test_hash_deterministic_under_shuffle(d):
    items = list(d.items())
    shuffled = dict(reversed(items))
    assert config_hash(d) == config_hash(shuffled)
# ---------- RunManifest (I3) ----------
def test_manifest_roundtrip():
    m = _manifest(retain_traces_for=("fell",))
    assert RunManifest.from_dict(m.to_dict()) == m
def test_manifest_defaults():
    m = _manifest()
    assert m.status == "partial" and m.schema_version == 1
    assert m.retain_traces_for is None
    assert m.poisson_prove_version and m.created_at.endswith("Z")
@pytest.mark.parametrize("field", ["target_id", "t_unit"])
def test_manifest_requires(field):
    with pytest.raises(ValueError):
        _manifest(**{field: ""})
# ---------- EpisodeRecord (I4) ----------
def test_record_from_episode_fields():
    r = _rec(confidence=0.7, meta={"k": 1})
    assert r.outcome == "fell" and r.t == 3.0 and r.horizon == 10.0
    assert r.confidence == 0.7 and dict(r.meta) == {"k": 1} and r.error is None
    assert r.config_hash == config_hash({"friction": 0.5})
def test_record_errored():
    r = EpisodeRecord.errored(run_id="r1", config={"a": 1}, seed=1, replicate_index=0,
                              error="Traceback ...", wall_time=0.5)
    assert r.outcome is None and r.t is None and r.horizon is None
    assert r.confidence is None and r.error == "Traceback ..."
def test_record_rejects_both_outcome_and_error():
    with pytest.raises(ValueError):
        EpisodeRecord(run_id="r1", config_hash="0" * 16, config={}, seed=0,
                      replicate_index=0, outcome="fell", t=1.0, horizon=2.0,
                      confidence=None, meta={}, error="boom", wall_time=0.1,
                      backend_meta={})
def test_record_rejects_neither():
    with pytest.raises(ValueError):
        EpisodeRecord(run_id="r1", config_hash="0" * 16, config={}, seed=0,
                      replicate_index=0, outcome=None, t=None, horizon=None,
                      confidence=None, meta={}, error=None, wall_time=0.1,
                      backend_meta={})
# ---------- Store lifecycle (I5, I6, I11, I14) ----------
def test_create_and_manifest(tmp_path):
    s = Store(tmp_path)
    s.create_run(_manifest())
    assert s.runs() == ["r1"]
    assert s.manifest("r1").status == "partial"
def test_create_duplicate_run_raises(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    with pytest.raises(StoreError):
        s.create_run(_manifest())
def test_run_id_no_path_separators(tmp_path):
    s = Store(tmp_path)
    with pytest.raises(StoreError):
        s.create_run(_manifest(run_id="a/b"))
def test_append_creates_new_part_and_leaves_old_untouched(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec(rep=0)])
    parts = sorted((tmp_path / "r1" / "episodes").glob("*.parquet"))
    assert len(parts) == 1
    before = parts[0].read_bytes()
    s.append("r1", [_rec(rep=1)])
    parts2 = sorted((tmp_path / "r1" / "episodes").glob("*.parquet"))
    assert len(parts2) == 2 and parts2[0].read_bytes() == before
def test_append_returns_count(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    assert s.append("r1", [_rec(rep=0), _rec(rep=1)]) == 2
def test_append_duplicate_key_raises_and_writes_nothing(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec(rep=0)])
    with pytest.raises(DuplicateEpisode):
        s.append("r1", [_rec(rep=1), _rec(rep=0)])
    assert len(s.read("r1")) == 1
def test_append_duplicate_within_batch_raises(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    with pytest.raises(DuplicateEpisode):
        s.append("r1", [_rec(rep=0), _rec(rep=0)])
    assert len(s.read("r1")) == 0
def test_mark_complete_then_append_raises(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec()])
    s.mark_complete("r1")
    assert s.manifest("r1").status == "complete"
    with pytest.raises(StoreError):
        s.append("r1", [_rec(rep=1)])
def test_append_to_unknown_run_raises(tmp_path):
    with pytest.raises(StoreError):
        Store(tmp_path).append("nope", [_rec()])
# ---------- read() shape (I9, I13) ----------
# PF4.38: a read frame carries the store's ``case_id`` column at the end.
EXPECTED_COLS = ["run_id", "config_hash", "config", "seed", "replicate_index",
                 "outcome", "t", "horizon", "confidence", "meta", "error",
                 "wall_time", "backend_meta", "case_id"]
def test_read_columns_exact(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec()])
    df = s.read("r1")
    assert list(df.columns) == EXPECTED_COLS
def test_read_decodes_json_columns(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec(cfg={"friction": 0.5, "push": 2}, meta={"trace": [1, 2], "n": {"x": "y"}})])
    row = s.read("r1").iloc[0]
    assert isinstance(row["meta"], dict) and row["meta"]["trace"] == [1, 2]
    assert isinstance(row["config"], dict) and row["config"]["push"] == 2
    assert isinstance(row["backend_meta"], dict)
def test_meta_stored_as_string_on_disk(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec(meta={"k": 1})])
    part = next((tmp_path / "r1" / "episodes").glob("*.parquet"))
    raw = pd.read_parquet(part)
    assert isinstance(raw["meta"].iloc[0], str) and json.loads(raw["meta"].iloc[0]) == {"k": 1}
def test_read_roundtrips_episode_fields(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec(outcome="violated", t=7.5, horizon=40.0, confidence=0.91,
                         meta={"a": [1, "two", 3.0], "b": {"c": True}})])
    row = s.read("r1").iloc[0]
    assert row["outcome"] == "violated" and row["t"] == 7.5 and row["horizon"] == 40.0
    assert row["confidence"] == 0.91
    assert row["meta"] == {"a": [1, "two", 3.0], "b": {"c": True}}
def test_read_sorted_and_concatenated(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec(cfg={"f": 0.9}, rep=1)])
    s.append("r1", [_rec(cfg={"f": 0.1}, rep=0), _rec(cfg={"f": 0.9}, rep=0)])
    df = s.read("r1")
    keys = list(zip(df["config_hash"], df["replicate_index"]))
    assert keys == sorted(keys) and len(df) == 3
def test_read_errored_record_has_null_outcome(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [EpisodeRecord.errored(run_id="r1", config={"a": 1}, seed=0,
                                          replicate_index=0, error="timeout", wall_time=1.0)])
    row = s.read("r1").iloc[0]
    assert pd.isna(row["outcome"]) and pd.isna(row["t"]) and row["error"] == "timeout"
def test_read_empty_run(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    df = s.read("r1")
    assert list(df.columns) == EXPECTED_COLS and len(df) == 0
# ---------- meta serializability (I7) ----------
def test_meta_not_serializable_raises_and_names_key(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    with pytest.raises(MetaNotSerializable) as ei:
        s.append("r1", [_rec(meta={"ok": 1, "bad": {"deep": object()}})])
    assert "bad" in str(ei.value) and "deep" in str(ei.value)
    assert len(s.read("r1")) == 0
def test_meta_numpy_values_are_serializable(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec(meta={"x": np.float64(1.5), "y": np.int32(2)})])
    assert s.read("r1").iloc[0]["meta"] == {"x": 1.5, "y": 2}
# ---------- trace retention (I8) ----------
def test_retention_none_keeps_all(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest(retain_traces_for=None))
    s.append("r1", [_rec(outcome="completed", meta={"trace": ["a"], "k": 1})])
    assert s.read("r1").iloc[0]["meta"] == {"trace": ["a"], "k": 1}
def test_retention_tuple_drops_nonmatching_trace_only(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest(retain_traces_for=("violated",)))
    s.append("r1", [_rec(rep=0, outcome="completed", meta={"trace": ["a"], "k": 1}),
                    _rec(rep=1, outcome="violated", meta={"trace": ["b"], "k": 2})])
    df = s.read("r1").set_index("replicate_index")
    assert df.loc[0, "meta"] == {"k": 1}
    assert df.loc[1, "meta"] == {"trace": ["b"], "k": 2}
def test_retention_errored_record_has_empty_meta(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest(retain_traces_for=("violated",)))
    r = EpisodeRecord.errored(run_id="r1", config={"a": 1}, seed=0, replicate_index=0,
                              error="boom", wall_time=0.1)
    s.append("r1", [r])
    assert s.read("r1").iloc[0]["meta"] == {}
# ---------- resume (I12) ----------
def test_missing_reports_absent_pairs_in_order(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    h1, h2 = config_hash({"f": 0.1}), config_hash({"f": 0.9})
    s.append("r1", [_rec(cfg={"f": 0.1}, rep=0), _rec(cfg={"f": 0.9}, rep=1)])
    expected = [(h1, 0), (h1, 1), (h2, 0), (h2, 1)]
    assert s.missing("r1", expected) == [(h1, 1), (h2, 0)]
def test_missing_on_empty_run_returns_all(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    exp = [(config_hash({"a": 1}), i) for i in range(3)]
    assert s.missing("r1", exp) == exp
# ---------- schema version (I10) ----------
def test_schema_mismatch_raises(tmp_path):
    s = Store(tmp_path); s.create_run(_manifest())
    s.append("r1", [_rec()])
    mpath = tmp_path / "r1" / "manifest.json"
    d = json.loads(mpath.read_text()); d["schema_version"] = 2
    mpath.write_text(json.dumps(d))
    with pytest.raises(SchemaMismatch):
        s.read("r1")
