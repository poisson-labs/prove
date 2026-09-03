"""Oracle for M2: grid / sobol / scenarios samplers, axis typing, SweepSpec, TOML loader.

Property tests (I1, I2, I3, I5, I6, I7, I15) draw small mixed-type axis dicts with
hypothesis; grids stay under about 200 configs. I10 is the golden: the Go1 TOML from
section 3 is written to tmp_path inside the test, loaded, and its config_hash set is
compared against the committed fixture through the ``go1_store`` fixture. I12
round-trips through ``to_dict()`` and ``json.dumps``.

Conventions the oracle fixes for the implementation session:

- Axis values inside one axis are unique under Python equality, so ``1`` and ``True``
  never share an axis; across configs, value identity is checked by type as well as
  value (``type(v) is type(expected)``), which is how I3 is pinned.
- ``to_dict()`` must expose ``configs``, ``axis_types``, ``replicates``, ``target_id``,
  ``t_unit``, ``retain_traces_for`` and ``duplicates_dropped`` under exactly those
  names; ``build`` accepts every key except ``duplicates_dropped``.
- ``SamplerError`` messages for a missing TOML field must contain the field name.
- ``sobol`` output values are floats; keys equal the bounds keys.
"""

import copy
import json
import math
from itertools import product
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from proofload.sampler import (
    SamplerError,
    SweepSpec,
    grid,
    infer_axis_types,
    preset,
    scenarios,
    sobol,
)
from proofload.store import Store, config_hash

GO1_TOML = """\
target_id = "go1-g2-converged@20260813T155006Z"
t_unit    = "seconds"
replicates = 32

[axes.mu]
type   = "continuous"
values = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
          0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]

[axes.push_pct_bw]
type   = "continuous"
values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0,
          110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0, 200.0]
"""

RATES = (0.0, 0.05, 0.10, 0.20, 0.30)
MAX_GRID = 200

# ---------- strategies ----------

KEYS = st.sampled_from(["a", "b", "c", "d", "mu", "push"])
SCALARS = st.one_of(
    st.integers(min_value=-50, max_value=50),
    st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
    st.text(alphabet="xyz", min_size=1, max_size=3),
    st.booleans(),
    st.none(),
)
NUMERIC = st.one_of(
    st.integers(min_value=-50, max_value=50),
    st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
)


@st.composite
def axes_dicts(draw, max_axes: int = 3, max_values: int = 5):
    """{key: [unique mixed-type values]} with 1..max_axes axes; product <= MAX_GRID."""
    n_axes = draw(st.integers(min_value=1, max_value=max_axes))
    keys = draw(st.lists(KEYS, min_size=n_axes, max_size=n_axes, unique=True))
    axes = {}
    for key in keys:
        axes[key] = draw(st.lists(SCALARS, min_size=1, max_size=max_values, unique=True))
    assume(math.prod(len(v) for v in axes.values()) <= MAX_GRID)
    return axes


@st.composite
def config_lists(draw, min_size: int = 1, max_size: int = 12):
    """Lists of small configs with a shared key pool and mixed value types; keys may be
    missing from some configs, and nested values appear occasionally."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    pool = draw(st.lists(KEYS, min_size=1, max_size=4, unique=True))
    configs = []
    for _ in range(n):
        cfg = {}
        for key in pool:
            if draw(st.booleans()):
                nested = draw(st.booleans())
                if nested:
                    cfg[key] = draw(
                        st.one_of(
                            st.lists(NUMERIC, max_size=3),
                            st.dictionaries(st.sampled_from(["p", "q"]), NUMERIC, max_size=2),
                        )
                    )
                else:
                    cfg[key] = draw(SCALARS)
        configs.append(cfg)
    return configs


# ---------- helpers ----------


def _tagged(value):
    """Value plus its concrete type, so 1, 1.0 and True are told apart."""
    return (type(value).__name__, json.dumps(value, sort_keys=True, default=str))


def _expected_grid(axes):
    keys = list(axes)
    return [dict(zip(keys, combo, strict=True)) for combo in product(*(axes[k] for k in keys))]


def _expected_axis_types(configs):
    keys = {k for c in configs for k in c}
    out = {}
    for key in keys:
        if not all(key in c for c in configs):
            out[key] = "categorical"
            continue
        values = [c[key] for c in configs]
        numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)
        out[key] = "continuous" if numeric else "categorical"
    return out


def _build(configs, **kw):
    base = {"replicates": 2, "target_id": "policy@abc", "t_unit": "steps"}
    base.update(kw)
    return SweepSpec.build(configs, **base)


# ---------- I1: grid size and coverage ----------


@given(axes=axes_dicts())
def test_i1_grid_is_full_cartesian_product(axes) -> None:
    out = grid(axes)
    assert len(out) == math.prod(len(v) for v in axes.values())
    got = [tuple(sorted((k, _tagged(v)) for k, v in c.items())) for c in out]
    want = [tuple(sorted((k, _tagged(v)) for k, v in c.items())) for c in _expected_grid(axes)]
    assert sorted(got) == sorted(want)
    assert len(set(got)) == len(got)


# ---------- I2: order ----------


@given(axes=axes_dicts())
def test_i2_grid_order_last_axis_fastest_and_repeatable(axes) -> None:
    out = grid(axes)
    keys = list(axes)
    sizes = [len(axes[k]) for k in keys]
    for i, cfg in enumerate(out):
        assert list(cfg) == keys
        rem = i
        idx = [0] * len(keys)
        for j in range(len(keys) - 1, -1, -1):
            idx[j] = rem % sizes[j]
            rem //= sizes[j]
        for j, k in enumerate(keys):
            assert cfg[k] == axes[k][idx[j]]
            assert type(cfg[k]) is type(axes[k][idx[j]])
    assert grid(axes) == out


def test_i2_grid_worked_example() -> None:
    out = grid({"x": [1, 2], "y": ["a", "b", "c"]})
    assert out == [
        {"x": 1, "y": "a"},
        {"x": 1, "y": "b"},
        {"x": 1, "y": "c"},
        {"x": 2, "y": "a"},
        {"x": 2, "y": "b"},
        {"x": 2, "y": "c"},
    ]


# ---------- I3: value types ----------


@given(axes=axes_dicts())
def test_i3_grid_preserves_value_types(axes) -> None:
    for cfg in grid(axes):
        for k, v in cfg.items():
            match = [a for a in axes[k] if a == v and type(a) is type(v)]
            assert match, (k, v, type(v))


def test_i3_grid_worked_example_int_float_str_bool() -> None:
    out = grid({"n": [5, 5.0], "s": ["a"], "f": [True]})
    assert type(out[0]["n"]) is int and type(out[1]["n"]) is float
    assert type(out[0]["s"]) is str and type(out[0]["f"]) is bool
    assert out[0]["n"] == 5 and out[1]["n"] == 5.0


# ---------- I4: sobol ----------


def test_i4_sobol_count_bounds_and_determinism() -> None:
    bounds = {"mu": (0.05, 1.0), "push": (10.0, 200.0)}
    a = sobol(bounds, 16, seed=7)
    b = sobol(bounds, 16, seed=7)
    c = sobol(bounds, 16, seed=8)
    assert len(a) == 16
    for cfg in a:
        assert list(cfg) == ["mu", "push"]
        for k, (lo, hi) in bounds.items():
            assert isinstance(cfg[k], float)
            assert lo <= cfg[k] <= hi
    assert a == b
    assert a != c


@pytest.mark.parametrize("n", [6, 0, 3, 12])
def test_i4_sobol_rejects_non_power_of_two(n: int) -> None:
    with pytest.raises(SamplerError):
        sobol({"mu": (0.0, 1.0)}, n, seed=1)


def test_i4_sobol_single_point_and_one_dim() -> None:
    out = sobol({"x": (2.0, 3.0)}, 1, seed=3)
    assert len(out) == 1 and 2.0 <= out[0]["x"] <= 3.0


# ---------- I5: scenarios ----------


@given(configs=config_lists())
def test_i5_scenarios_returns_new_plain_dicts_equal_to_input(configs) -> None:
    snapshot = copy.deepcopy(configs)
    out = scenarios(configs)
    assert isinstance(out, list) and out is not configs
    assert len(out) == len(configs)
    for got, want in zip(out, configs, strict=True):
        assert type(got) is dict
        assert got == want
    assert configs == snapshot


def test_i5_scenarios_accepts_any_mapping_and_iterables() -> None:
    from types import MappingProxyType

    out = scenarios(iter([MappingProxyType({"a": 1}), {"b": "x"}]))
    assert out == [{"a": 1}, {"b": "x"}]
    assert all(type(c) is dict for c in out)


@pytest.mark.parametrize("bad", [[{"a": 1}, 3], [{"a": 1}, [1, 2]], ["a"], [None]])
def test_i5_scenarios_rejects_non_mapping_elements(bad) -> None:
    with pytest.raises(SamplerError):
        scenarios(bad)


@pytest.mark.parametrize(
    "bad",
    [
        [{"a": float("nan")}],
        [{"a": float("inf")}],
        [{"a": {"b": [1.0, -float("inf")]}}],
        [{"ok": 1}, {"a": [float("nan")]}],
    ],
)
def test_i5_scenarios_rejects_nonfinite_anywhere(bad) -> None:
    with pytest.raises(SamplerError):
        scenarios(bad)


# ---------- I6: axis typing ----------


@given(configs=config_lists())
def test_i6_infer_axis_types_property(configs) -> None:
    assert infer_axis_types(configs) == _expected_axis_types(configs)


def test_i6_infer_axis_types_worked_examples() -> None:
    assert infer_axis_types([{"a": 1}, {"a": 2.5}]) == {"a": "continuous"}
    assert infer_axis_types([{"a": 1}, {"a": True}]) == {"a": "categorical"}
    assert infer_axis_types([{"a": True}, {"a": False}]) == {"a": "categorical"}
    assert infer_axis_types([{"a": 1}, {"a": "x"}]) == {"a": "categorical"}
    assert infer_axis_types([{"a": 1}, {"a": None}]) == {"a": "categorical"}
    assert infer_axis_types([{"a": [1, 2]}, {"a": [3]}]) == {"a": "categorical"}
    assert infer_axis_types([{"a": {"b": 1}}]) == {"a": "categorical"}
    assert infer_axis_types([{"a": 1, "b": "x"}, {"a": 2}]) == {
        "a": "continuous",
        "b": "categorical",
    }
    assert infer_axis_types([]) == {}


# ---------- I7: dedup ----------


@st.composite
def configs_with_duplicates(draw):
    pool = [
        {"a": 1},
        {"a": 1.0},
        {"a": True},
        {"a": 2, "b": "x"},
        {"b": "x", "a": 2},
        {"a": 2, "b": "y"},
        {"c": None},
        {"c": [1, 2]},
        {"c": [1.0, 2.0]},
    ]
    picks = draw(st.lists(st.integers(min_value=0, max_value=len(pool) - 1), min_size=1, max_size=16))
    return [copy.deepcopy(pool[i]) for i in picks]


@given(configs=configs_with_duplicates())
def test_i7_build_dedups_by_config_hash_first_wins_order_kept(configs) -> None:
    spec = _build(configs)
    survivors: dict[str, dict] = {}
    for c in configs:
        survivors.setdefault(config_hash(c), c)
    expected = list(survivors.values())
    assert list(spec.configs) == expected
    assert [type(c) for c in spec.configs] == [dict] * len(expected)
    assert spec.duplicates_dropped == len(configs) - len(expected)
    assert len(set(spec.cells())) == len(spec.configs)


def test_i7_int_float_collapse_but_first_representation_kept() -> None:
    spec = _build([{"a": 5.0}, {"a": 5}, {"a": True}])
    assert list(spec.configs) == [{"a": 5.0}, {"a": True}]
    assert type(spec.configs[0]["a"]) is float
    assert spec.duplicates_dropped == 1


# ---------- I8: build validation ----------


@pytest.mark.parametrize("replicates", [0, -1])
def test_i8_build_rejects_replicates_below_one(replicates: int) -> None:
    with pytest.raises(SamplerError):
        _build([{"a": 1}], replicates=replicates)


def test_i8_build_rejects_empty_configs() -> None:
    with pytest.raises(SamplerError):
        _build([])


@pytest.mark.parametrize("field", ["target_id", "t_unit"])
def test_i8_build_rejects_empty_required_strings(field: str) -> None:
    with pytest.raises(SamplerError):
        _build([{"a": 1}], **{field: ""})


def test_i8_build_rejects_axis_type_for_unknown_key() -> None:
    with pytest.raises(SamplerError):
        _build([{"a": 1}, {"a": 2}], axis_types={"a": "continuous", "zzz": "categorical"})


def test_i8_build_accepts_explicit_axis_types_for_present_keys() -> None:
    spec = _build([{"a": 1, "b": "x"}], axis_types={"a": "categorical"})
    assert spec.axis_types["a"] == "categorical"


def test_i8_build_rejects_unhashable_config_values() -> None:
    with pytest.raises(SamplerError):
        _build([{"a": object()}])
    with pytest.raises(SamplerError):
        _build([{"a": float("nan")}])


# ---------- I9: cells and totals ----------


@given(configs=config_lists(), replicates=st.integers(min_value=1, max_value=40))
def test_i9_cells_and_total_rollouts(configs, replicates) -> None:
    spec = _build(configs, replicates=replicates)
    assert spec.cells() == [config_hash(c) for c in spec.configs]
    assert spec.total_rollouts() == len(spec.configs) * replicates
    assert spec.replicates == replicates


# ---------- I10: golden ----------


def test_i10_go1_toml_reproduces_fixture_cells(go1_store: Store, tmp_path: Path) -> None:
    path = tmp_path / "go1.toml"
    path.write_text(GO1_TOML)
    spec = SweepSpec.load(path)
    assert len(spec.configs) == 400
    assert spec.duplicates_dropped == 0
    assert spec.replicates == 32
    assert spec.target_id == "go1-g2-converged@20260813T155006Z"
    assert spec.t_unit == "seconds"
    assert dict(spec.axis_types) == {"mu": "continuous", "push_pct_bw": "continuous"}
    assert spec.retain_traces_for is None
    fixture_hashes = set(go1_store.read("go1-v0")["config_hash"].unique())
    assert set(spec.cells()) == fixture_hashes
    assert spec.total_rollouts() == 12800


def test_i10_load_accepts_str_path_and_matches_grid(tmp_path: Path) -> None:
    path = tmp_path / "go1.toml"
    path.write_text(GO1_TOML)
    spec = SweepSpec.load(str(path))
    mus = [round(0.05 * k, 2) for k in range(1, 21)]
    pushes = [10.0 * k for k in range(1, 21)]
    assert list(spec.configs) == grid({"mu": mus, "push_pct_bw": pushes})


def test_load_appends_scenarios_after_grid(tmp_path: Path) -> None:
    text = (
        'target_id = "t"\nt_unit = "steps"\nreplicates = 3\n'
        '[axes.a]\ntype = "continuous"\nvalues = [1, 2]\n'
        '[axes.b]\ntype = "categorical"\nvalues = ["x"]\n'
        "[[scenarios]]\na = 9\nb = \"hand\"\n"
        "[[scenarios]]\na = 10\n"
    )
    path = tmp_path / "s.toml"
    path.write_text(text)
    spec = SweepSpec.load(path)
    assert list(spec.configs) == [
        {"a": 1, "b": "x"},
        {"a": 2, "b": "x"},
        {"a": 9, "b": "hand"},
        {"a": 10},
    ]
    assert dict(spec.axis_types) == {"a": "continuous", "b": "categorical"}


# ---------- I11: missing fields ----------


def _toml_without(field: str) -> str:
    lines = GO1_TOML.splitlines(keepends=True)
    if field == "axis type":
        return "".join(line for line in lines if not line.startswith('type   = "continuous"'))
    return "".join(line for line in lines if not line.startswith(field))


@pytest.mark.parametrize("field", ["target_id", "t_unit", "replicates", "axis type"])
def test_i11_load_names_missing_field(field: str, tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(_toml_without(field))
    with pytest.raises(SamplerError) as ei:
        SweepSpec.load(path)
    needle = "type" if field == "axis type" else field
    assert needle in str(ei.value)


def test_i11_load_rejects_missing_axes_entirely(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text('target_id = "t"\nt_unit = "s"\nreplicates = 1\n')
    with pytest.raises(SamplerError):
        SweepSpec.load(path)


def test_i11_load_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises((SamplerError, OSError)):
        SweepSpec.load(tmp_path / "nope.toml")


# ---------- I12: to_dict round-trip ----------

ROUND_TRIP_KEYS = {
    "configs",
    "axis_types",
    "replicates",
    "target_id",
    "t_unit",
    "retain_traces_for",
    "duplicates_dropped",
}


def _rebuild(d: dict) -> SweepSpec:
    return SweepSpec.build(**{k: v for k, v in d.items() if k != "duplicates_dropped"})


def test_i12_to_dict_round_trips_and_is_json_serializable() -> None:
    spec = _build(
        [{"a": 1, "b": "x"}, {"a": 2.5, "b": "y"}, {"a": 1, "b": "x"}],
        replicates=4,
        retain_traces_for=["violated", "fell"],
    )
    d = spec.to_dict()
    assert set(d) == ROUND_TRIP_KEYS
    assert isinstance(d["configs"], list) and all(type(c) is dict for c in d["configs"])
    assert d["duplicates_dropped"] == 1
    text = json.dumps(d)
    rebuilt = _rebuild(d)
    assert rebuilt.configs == spec.configs
    assert dict(rebuilt.axis_types) == dict(spec.axis_types)
    assert rebuilt.replicates == spec.replicates
    assert rebuilt.target_id == spec.target_id and rebuilt.t_unit == spec.t_unit
    assert rebuilt.retain_traces_for == spec.retain_traces_for == ("violated", "fell")
    rebuilt_from_json = _rebuild(json.loads(text))
    assert rebuilt_from_json.configs == spec.configs
    assert rebuilt_from_json.retain_traces_for == spec.retain_traces_for
    assert rebuilt_from_json.to_dict() == rebuilt.to_dict()


@given(configs=config_lists(), replicates=st.integers(min_value=1, max_value=8))
def test_i12_round_trip_property_without_duplicates(configs, replicates) -> None:
    spec = _build(configs, replicates=replicates)
    assume(spec.duplicates_dropped == 0)
    d = json.loads(json.dumps(spec.to_dict()))
    assert _rebuild(d) == spec


# ---------- I13: preset ----------


def test_i13_tool_reliability_preset_shape_and_types() -> None:
    tasks = ["book_flight", "cancel", "refund"]
    out = preset("tool-reliability", tasks=tasks)
    assert len(out) == len(tasks) * 5
    assert all(set(c) == {"task_id", "tool_fail_rate"} for c in out)
    assert {c["task_id"] for c in out} == set(tasks)
    assert sorted({c["tool_fail_rate"] for c in out}) == sorted(RATES)
    assert infer_axis_types(out) == {"task_id": "categorical", "tool_fail_rate": "continuous"}
    assert out == grid({"task_id": tasks, "tool_fail_rate": list(RATES)})


def test_i13_tool_reliability_rate_override() -> None:
    out = preset("tool-reliability", tasks=["t1"], tool_fail_rate=[0.5, 0.9])
    assert len(out) == 2
    assert [c["tool_fail_rate"] for c in out] == [0.5, 0.9]


def test_i13_unknown_preset_raises() -> None:
    with pytest.raises(SamplerError):
        preset("no-such-preset", tasks=["t"])  # type: ignore[arg-type]


# ---------- I14: empty grid ----------


def test_i14_grid_rejects_empty_values_and_empty_axes() -> None:
    with pytest.raises(SamplerError):
        grid({"a": []})
    with pytest.raises(SamplerError):
        grid({"a": [1], "b": []})
    with pytest.raises(SamplerError):
        grid({})


# ---------- I15: purity ----------


@given(axes=axes_dicts(), configs=config_lists())
def test_i15_functions_are_pure_and_do_not_mutate_inputs(axes, configs) -> None:
    axes_before, configs_before = copy.deepcopy(axes), copy.deepcopy(configs)
    assert grid(axes) == grid(axes)
    assert scenarios(configs) == scenarios(configs)
    assert infer_axis_types(configs) == infer_axis_types(configs)
    assert _build(configs) == _build(configs)
    assert _build(configs).to_dict() == _build(configs).to_dict()
    assert axes == axes_before and configs == configs_before


def test_i15_sobol_and_preset_are_pure() -> None:
    bounds = {"x": (0.0, 1.0), "y": (-1.0, 1.0)}
    assert sobol(bounds, 8, seed=11) == sobol(bounds, 8, seed=11)
    assert preset("tool-reliability", tasks=["a", "b"]) == preset("tool-reliability", tasks=["a", "b"])
    spec_a = _build(preset("tool-reliability", tasks=["a"]))
    spec_b = _build(preset("tool-reliability", tasks=["a"]))
    assert spec_a == spec_b and spec_a.cells() == spec_b.cells()


def test_i15_spec_configs_are_not_aliased_to_input() -> None:
    src = [{"a": [1, 2]}]
    spec = _build(src)
    src[0]["a"].append(3)
    assert spec.configs[0] == {"a": [1, 2]}
