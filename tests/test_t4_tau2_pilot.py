"""T.4 run prep: the guardrail, the patched factory, the family rule and the junk-cell shape.

Five things are pinned here, and each is pinned because something about it was found wrong or
untested while the prep ran.

* **The guardrail and its hash.** The arm is fixed before it runs, so the text and its sha256
  are constants a later session can check a stored run against. A change to either is a new arm.
* **The patched factory.** ``build_agent`` calls a factory with **seven** keyword arguments,
  not the five the pre-registration lists -- ``task``, ``audio_native_config`` and
  ``audio_taps_dir`` all ride along -- so the factory is tested against that call shape, and
  the unpatched path is tested to be byte-identical to τ²'s own.
* **The family rule.** §2.3's rule is the pre-registered thing; the table of task ids beside it
  was read by hand and is wrong on ten of the fifty tasks. The rule is pinned here and the
  table is not.
* **The junk cells.** The design declares three wholly-errored cells per arm and asserts from a
  source read that they never reach the tree. A read is not a measurement (MAL §18 rule 14):
  this runs a real sweep pair through ``multi_diff`` and reads the coverage.
* **K8's field.** ``n_not_comparable`` counts cells present in one arm only, and is **0** here;
  the junk cells land in ``coverage`` as ``no_outcome_both``. K8 keyed on the wrong name would
  pass on a broken run and fail on a correct one.

The τ²-facing tests need the benchmark, which is not installed outside the image; they are
skipped at *function* level with the reason printed, never at module level, so the count moves
visibly when the environment changes (MAL §18 rule 13).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))

from tau2_pilot import budget as budget_module  # noqa: E402,F401
from tau2_pilot import guardrail as g  # noqa: E402
from tau2_pilot import synthetic  # noqa: E402

T4_TOML = EXAMPLES / "tau2_pilot" / "t4.toml"

#: The guardrail as pre-registered, and its digest. Both are the arm's identity: a test that
#: recomputed the hash from the constant would pin nothing at all.
GUARDRAIL_SHA256 = "fce8dcd12119b7e6c2ea288e14a60c4cd9dcc1bca0f8bbaffb0847e5cfc85156"


# ---------- the guardrail ----------


def test_guardrail_hash_is_the_pre_registered_one() -> None:
    assert g.GUARDRAIL_SHA256 == GUARDRAIL_SHA256
    assert len(g.GUARDRAIL.encode("utf-8")) == 421


def test_guardrail_names_every_write_tool_and_no_other_tool() -> None:
    """The paragraph's list and the sweep file's partition read the same set."""
    named = {tool for tool in g.WRITE_TOOLS if tool in g.GUARDRAIL}
    assert named == g.WRITE_TOOLS
    for read_tool in ("get_reservation_details", "search_direct_flight", "calculate"):
        assert read_tool not in g.GUARDRAIL


def test_append_guardrail_puts_it_after_the_policy() -> None:
    patched = g.append_guardrail("<policy>\nAIRLINE POLICY\n</policy>")
    assert patched.startswith("<policy>\nAIRLINE POLICY\n</policy>")
    assert patched.endswith(g.GUARDRAIL)
    assert patched.index("</policy>") < patched.index("Before you call any tool")


# ---------- the factory, against build_agent's real call shape ----------


class _StubLLMAgent:
    """``LLMAgent``'s shape where the patch touches it: the four-arg constructor and a
    ``system_prompt`` **property**. A plain attribute would let a broken subclass pass."""

    def __init__(self, tools, domain_policy, llm=None, llm_args=None):  # type: ignore[no-untyped-def]
        self.tools = tools
        self.domain_policy = domain_policy
        self.llm = llm
        self.llm_args = llm_args

    @property
    def system_prompt(self) -> str:
        return f"<instructions>\nINSTRUCTION\n</instructions>\n<policy>\n{self.domain_policy}\n</policy>"


def _build_agent_kwargs() -> dict[str, object]:
    """Exactly what ``tau2.runner.build.build_agent`` passes a factory, read at the pin."""
    return {
        "llm": "openai/gpt-4.1-mini-2025-04-14",
        "llm_args": {"temperature": 0.0},
        "task": object(),
        "audio_native_config": None,
        "audio_taps_dir": None,
    }


def test_factory_applies_the_paragraph() -> None:
    agent = g.guardrail_factory(
        _StubLLMAgent, ["tool"], "AIRLINE POLICY", **_build_agent_kwargs()
    )
    assert isinstance(agent, _StubLLMAgent)
    assert g.GUARDRAIL in agent.system_prompt
    assert agent.system_prompt == g.append_guardrail(
        _StubLLMAgent.system_prompt.fget(agent)  # type: ignore[attr-defined]
    )


def test_factory_survives_build_agents_seventh_keyword() -> None:
    """``audio_taps_dir`` is passed on every path and is absent from the pre-registration's
    list of the factory's arguments. A factory that named its parameters would raise here."""
    kwargs = _build_agent_kwargs()
    assert "audio_taps_dir" in kwargs
    g.guardrail_factory(_StubLLMAgent, ["tool"], "P", **kwargs)


def test_the_unpatched_path_is_unchanged() -> None:
    """Arm A's agent is τ²'s own object with τ²'s own prompt: constructing the patched class
    must not have touched the base class, and the base must still produce the bare prompt."""
    plain = _StubLLMAgent(["tool"], "AIRLINE POLICY")
    before = plain.system_prompt
    g.guardrail_factory(_StubLLMAgent, ["tool"], "AIRLINE POLICY", **_build_agent_kwargs())
    assert plain.system_prompt == before
    assert g.GUARDRAIL not in plain.system_prompt
    assert _StubLLMAgent(["tool"], "P").system_prompt.endswith("</policy>")


def test_the_patched_agent_is_a_subclass_and_keeps_the_base_constructor() -> None:
    cls = g.guardrail_agent_class(_StubLLMAgent)
    assert issubclass(cls, _StubLLMAgent) and cls is not _StubLLMAgent
    agent = cls(tools=["t"], domain_policy="P", llm="m", llm_args={"temperature": 0.0})
    assert agent.llm == "m" and agent.llm_args == {"temperature": 0.0}
    assert isinstance(type(agent).system_prompt, property)


# ---------- the family rule ----------


def _sweep_script():  # type: ignore[no-untyped-def]
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import tau2_t4_sweep

    return tau2_t4_sweep


def test_family_rule_is_total_over_the_three_families() -> None:
    script = _sweep_script()
    cases = [
        ([], "no_write"),
        (["get_reservation_details", "search_direct_flight"], "no_write"),
        (["update_reservation_baggages"], "modify_in_place"),
        (["get_user_details", "update_reservation_passengers"], "modify_in_place"),
        (["book_reservation"], "cancel_or_book"),
        (["update_reservation_flights", "cancel_reservation"], "cancel_or_book"),
        (["send_certificate"], "cancel_or_book"),
    ]
    for actions, expected in cases:
        task = {"evaluation_criteria": {"actions": [{"name": n} for n in actions]}}
        assert script.family_of(task) == expected, actions
    assert script.family_of({}) == "no_write"
    assert script.family_of({"evaluation_criteria": None}) == "no_write"


def test_n_is_the_least_count_the_resolver_admits() -> None:
    """§4.4's derivation, run rather than quoted, at both the hand table's binding family size
    and the one the rule actually produces."""
    script = _sweep_script()
    assert script.least_admitted_replicates(13)[0] == 40
    assert script.least_admitted_replicates(12)[0] == 44


def test_committed_sweep_file_is_what_the_rule_produces() -> None:
    """The header's own numbers, checked against the file's scenarios. This is the half of
    ``--check`` that does not need a τ² checkout: that the 53 configs are 50 real cells over the
    three families plus the three the required axis grid adds, and that N is the admitted one."""
    from proofload.sampler import SweepSpec

    spec = SweepSpec.load(T4_TOML)
    assert spec.replicates == 44
    assert len(spec.configs) == 53
    junk = [cfg for cfg in spec.configs if "task_id" not in cfg]
    assert len(junk) == 3
    assert {cfg["task_family"] for cfg in junk} == set(_sweep_script().FAMILIES)
    real = [cfg for cfg in spec.configs if "task_id" in cfg]
    assert len(real) == 50
    assert {cfg["task_id"] for cfg in real} == {str(i) for i in range(50)}
    counts = {family: 0 for family in _sweep_script().FAMILIES}
    for cfg in real:
        counts[cfg["task_family"]] += 1
    assert counts == {"no_write": 24, "modify_in_place": 14, "cancel_or_book": 12}
    # task_family first, so the tree's axis rung resolves on it without --by.
    assert next(iter(spec.axis_types)) == "task_family"


def test_sweep_file_asks_for_content_capture() -> None:
    from proofload.sampler import SweepSpec

    capture = SweepSpec.load(T4_TOML).capture
    assert capture is not None
    assert capture.instrument == ("openai",)
    assert capture.content is True
    assert capture.max_span_bytes == 8192


# ---------- the junk cells, measured rather than read ----------


@pytest.fixture(scope="module")
def d0_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[object, object]:
    """One D0 pair over the committed sweep file's shape at a small N, on the local backend."""
    import dataclasses

    from proofload.executor import plan, run_local
    from proofload.sampler import SweepSpec
    from proofload.store import Store

    spec = dataclasses.replace(SweepSpec.load(T4_TOML), replicates=2)
    store = Store(tmp_path_factory.mktemp("d0"))
    plan_a = plan(spec, store, run_salt="00" * 8)
    run_local(plan_a, synthetic.rollout, store, batch_size=8)
    plan_b = plan(spec, store, pair_with=plan_a.run_id)
    run_local(plan_b, synthetic.rollout_patched, store, batch_size=8)
    return store, (plan_a.run_id, plan_b.run_id)


def test_junk_cells_error_out_at_three_per_replicate(d0_pair) -> None:  # type: ignore[no-untyped-def]
    store, (a, b) = d0_pair
    for run_id in (a, b):
        frame = store.read(run_id)
        assert len(frame) == 53 * 2
        assert int(frame["outcome"].isna().sum()) == 3 * 2


def test_junk_cells_never_reach_the_tree(d0_pair) -> None:  # type: ignore[no-untyped-def]
    """K8, measured. The three appear in ``coverage`` as ``no_outcome_both`` and in
    ``n_not_comparable`` as **nothing**: that field counts cells one arm ran and the other did
    not, and both arms ran these."""
    from proofload.diff import multi_diff

    store, (a, b) = d0_pair
    result = multi_diff(
        store.read(a),
        store.read(b),
        events=("unsolved",),
        method="mcnemar_bh",
        manifest_a=store.manifest(a),
        manifest_b=store.manifest(b),
    )
    assert result.n_tests == 50
    assert result.n_not_comparable == 0
    coverage = result.coverage
    assert coverage is not None
    holes = coverage[~coverage["comparable"].astype(bool)]
    assert len(holes) == 3
    assert set(holes["cause"]) == {"no_outcome_both"}
    configs = [cfg if isinstance(cfg, dict) else json.loads(cfg) for cfg in holes["config"]]
    assert all("task_id" not in cfg for cfg in configs)
    assert {cfg["task_family"] for cfg in configs} == set(_sweep_script().FAMILIES)
    # They have rows in both arms -- which is why "rows in both" is not the comparability test.
    assert set(holes["rows_a"]) == {2} and set(holes["rows_b"]) == {2}


# ---------- the spend guard ----------


def test_episode_budget_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(budget_module.BUDGET_VAR, raising=False)
    assert budget_module.episode_budget() == budget_module.DEFAULT_EPISODE_BUDGET_USD
    monkeypatch.setenv(budget_module.BUDGET_VAR, "0.5")
    assert budget_module.episode_budget() == 0.5
    for bad in ("", "  ", "not-a-number", "0", "-1"):
        monkeypatch.setenv(budget_module.BUDGET_VAR, bad)
        assert budget_module.episode_budget() == budget_module.DEFAULT_EPISODE_BUDGET_USD


def test_the_ceiling_clears_the_worst_episode_measured() -> None:
    """$0.0246 is the most expensive of the twenty smoke episodes, by ``meta.cost_tau2``. A
    ceiling under it would kill legitimate episodes; K5 would then discard the arm, loudly, for
    a reason that is ours and not the substrate's."""
    assert budget_module.DEFAULT_EPISODE_BUDGET_USD > 0.0246 * 2


@pytest.mark.skipif(
    __import__("importlib.util", fromlist=["util"]).find_spec("litellm") is None,
    reason="litellm is not installed; the budget guard is only assertable where litellm is",
)
def test_litellms_own_budget_is_inert_until_the_guard_supplies_the_accounting() -> None:
    """The measurement the guard exists because of, pinned so a litellm upgrade cannot undo it
    silently: with ``max_budget`` set and no accounting, τ²'s call shape leaves
    ``_current_cost`` at zero and the pre-call check never fires. litellm adds a call's cost
    only when the result ``isinstance(result, dict) and "content" in result``, and τ² gets
    ``ModelResponse`` objects whose agent turns are tool calls with ``content=None``."""
    import litellm

    from tests.helpers_t4 import mock_openai_server

    saved = (litellm.callbacks, litellm.max_budget, litellm._current_cost)
    try:
        litellm.callbacks = []
        litellm.max_budget = 0.01
        litellm._current_cost = 0.0
        with mock_openai_server() as base_url:
            for _ in range(4):
                litellm.completion(
                    model="openai/gpt-4.1-mini-2025-04-14",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.0,
                    api_base=base_url,
                    api_key="sk-not-a-real-key",
                )
        assert litellm._current_cost == 0.0, (
            "litellm now accounts for this call shape itself; the guard's own accounting would "
            "double count and DEFAULT_EPISODE_BUDGET_USD must be re-derived"
        )
    finally:
        litellm.callbacks, litellm.max_budget, litellm._current_cost = saved


# ---------- τ² conformance: only assertable where the benchmark is installed ----------

_HAS_TAU2 = __import__("importlib.util", fromlist=["util"]).find_spec("tau2") is not None
_NO_TAU2 = "tau2 is not installed outside the image; this pins the attachment points"


@pytest.mark.skipif(not _HAS_TAU2, reason=_NO_TAU2)
def test_tau2_still_offers_the_attachment_points_the_patch_uses() -> None:
    """Every assumption ``rollout_patched`` makes about τ², at whatever commit is installed.

    The pin is ``2174a603f6d014ef94473ffa95957f6ce27100db``; this fails on a re-pin that moves
    any of them, which is the point -- §2.2 asserts these from a source read and a read goes
    stale silently.
    """
    import inspect

    from tau2.agent.llm_agent import LLMAgent
    from tau2.data_model.simulation import TextRunConfig
    from tau2.registry import registry
    from tau2.runner import build

    assert callable(registry.register_agent_factory)
    assert callable(registry.get_agent_factory)
    # The agent name is a free string; a Literal or an enum here would refuse a registered name.
    assert TextRunConfig.model_fields["agent"].annotation is str
    assert isinstance(LLMAgent.system_prompt, property)
    source = inspect.getsource(build.build_agent)
    for keyword in (
        "tools=",
        "domain_policy=",
        "llm=",
        "llm_args=",
        "task=",
        "audio_native_config=",
        "audio_taps_dir=",
    ):
        assert keyword in source, f"build_agent no longer passes {keyword}"


@pytest.mark.skipif(not _HAS_TAU2, reason=_NO_TAU2)
def test_tau2_stores_no_system_message_so_the_proof_has_to_be_ours() -> None:
    """K7 says to read "the system message of every stored conversation". There is none:
    ``SimulationRun.messages`` is the orchestrator's trajectory and carries no ``SystemMessage``,
    and the model has no field for one. ``rollout._prompt_proof`` is why K7 is still readable."""
    from tau2.data_model.simulation import SimulationRun

    fields = set(SimulationRun.model_fields)
    assert "system_prompt" not in fields
    assert not any("system" in name for name in fields)


@pytest.mark.skipif(
    __import__("importlib.util", fromlist=["util"]).find_spec("litellm") is None,
    reason="litellm is not installed; the budget guard is only assertable where litellm is",
)
def test_reset_zeroes_the_accumulator_between_episodes() -> None:
    """Modal reuses containers, so ``batch_size = 1`` is one episode *at a time*, not one
    episode ever. Without this the ceiling is a per-container running total and the third or
    fourth episode of every warm container is refused for a reason that is ours."""
    import litellm

    saved = litellm._current_cost
    try:
        litellm._current_cost = 0.5
        budget_module.reset()
        assert litellm._current_cost == 0.0
        assert budget_module.spent() == 0.0
    finally:
        litellm._current_cost = saved


def test_the_patched_class_is_built_once_per_base() -> None:
    """A container serves many episodes; a fresh type per episode would leave one behind each
    time and make ``type(agent)`` differ between two episodes of the same arm."""
    first = g.guardrail_agent_class(_StubLLMAgent)
    assert g.guardrail_agent_class(_StubLLMAgent) is first
    a = g.guardrail_factory(_StubLLMAgent, ["t"], "P", **_build_agent_kwargs())
    b = g.guardrail_factory(_StubLLMAgent, ["t"], "P", **_build_agent_kwargs())
    assert type(a) is type(b) is first
