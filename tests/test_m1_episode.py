import pytest
from dataclasses import FrozenInstanceError
from hypothesis import given, strategies as st
from momus import Episode, EpisodeValidationError
# ---- unit: construction ----
def test_minimal_valid():
    e = Episode(outcome="fell", t=37, horizon=200)
    assert e.outcome == "fell" and e.t == 37.0 and e.horizon == 200.0
    assert e.confidence is None and dict(e.meta) == {}
def test_full_valid():
    e = Episode(outcome="violation", t=12.5, horizon=50, confidence=0.83,
                meta={"trace": ["a", "b"]})
    assert e.confidence == 0.83 and e.meta["trace"] == ["a", "b"]
def test_t_equals_horizon_is_valid():
    Episode(outcome="survived", t=200, horizon=200)
# ---- unit: rejections (I1–I5) ----
@pytest.mark.parametrize("outcome", ["", None, 3])
def test_rejects_bad_outcome(outcome):
    with pytest.raises(EpisodeValidationError):
        Episode(outcome=outcome, t=1, horizon=10)
def test_rejects_negative_t():
    with pytest.raises(EpisodeValidationError):
        Episode(outcome="x", t=-1, horizon=10)
@pytest.mark.parametrize("horizon", [0, -5])
def test_rejects_nonpositive_horizon(horizon):
    with pytest.raises(EpisodeValidationError):
        Episode(outcome="x", t=0, horizon=horizon)
def test_rejects_t_past_horizon():
    with pytest.raises(EpisodeValidationError):
        Episode(outcome="x", t=11, horizon=10)
@pytest.mark.parametrize("c", [-0.01, 1.01, float("nan")])
def test_rejects_confidence_out_of_range(c):
    with pytest.raises(EpisodeValidationError):
        Episode(outcome="x", t=1, horizon=10, confidence=c)
# ---- unit: immutability + identity (I6, I8, I9, I11) ----
def test_frozen():
    e = Episode(outcome="x", t=1, horizon=10)
    with pytest.raises(FrozenInstanceError):
        e.t = 5
def test_equality():
    a = Episode(outcome="x", t=1, horizon=10, meta={"k": 1})
    b = Episode(outcome="x", t=1, horizon=10, meta={"k": 1})
    assert a == b
def test_not_hashable():
    with pytest.raises(TypeError):
        hash(Episode(outcome="x", t=1, horizon=10))
def test_default_meta_not_shared():
    a, b = Episode(outcome="x", t=1, horizon=10), Episode(outcome="x", t=1, horizon=10)
    assert a.meta is not b.meta
def test_meta_mutability_leak():
    d = {"trace": ["a"], "k": 1}
    e = Episode(outcome="x", t=1, horizon=10, meta=d)
    d["trace"].append("b")
    d["k"] = 2
    assert e.meta["trace"] == ["a"] and e.meta["k"] == 1
def test_meta_not_writable_from_episode():
    e = Episode(outcome="x", t=1, horizon=10, meta={"k": 1})
    with pytest.raises(TypeError):
        e.meta["k"] = 2
# ---- unit: serialization (I7, I10) ----
def test_int_stored_as_float():
    e = Episode(outcome="x", t=3, horizon=10)
    assert isinstance(e.t, float) and isinstance(e.horizon, float)
def test_to_dict_exact_keys():
    d = Episode(outcome="x", t=1, horizon=10).to_dict()
    assert set(d) == {"outcome", "t", "horizon", "confidence", "meta"}
# ---- property: round-trip (I7) ----
meta_st = st.dictionaries(
    st.text(min_size=1, max_size=8),
    st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False),
              st.text(max_size=8), st.booleans()),
    max_size=4,
)
@given(
    outcome=st.text(min_size=1, max_size=16),
    horizon=st.floats(min_value=1e-6, max_value=1e6, allow_nan=False),
    frac=st.floats(min_value=0, max_value=1, allow_nan=False),
    confidence=st.one_of(st.none(), st.floats(min_value=0, max_value=1, allow_nan=False)),
    meta=meta_st,
)
def test_roundtrip(outcome, horizon, frac, confidence, meta):
    e = Episode(outcome=outcome, t=horizon * frac, horizon=horizon,
                confidence=confidence, meta=meta)
    assert Episode.from_dict(e.to_dict()) == e
