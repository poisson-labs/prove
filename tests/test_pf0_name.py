"""PF0, the name: the frozen tests for the rename from ``proofload`` to Poisson Prove.

Written from the front-door spec's section 2 and its invariants PF0.1 to PF0.13. The build is
written against this file and does not edit it.

What the rename promises, in one line: new names everywhere, old names read forever. A build of
this branch installs one package, ``poisson_prove``, and one command, ``poisson-prove``; it writes
``poisson-prove.*`` schema strings, ``poisson_prove.*`` span keys and ``poisson_prove_version``;
and every store ``proofload`` 0.0.1 wrote is read by every verb with nothing in it rewritten.

**The 0.0.1 stores.** ``tests/fixtures/stores-0.0.1/`` holds seven runs written by clean installs
of two 0.0.1 wheels (its README and ``build/`` say how): the quickstart pair, a run with a
timed-out and a crashed episode, a run whose captured observation was cut, a run under a declared
fault, a run from the Modal backend's offline stand-in, and a run in the layout before the trace
was split into two columns. ``SHA256SUMS`` is every file's digest as written. ``recorded/`` is
what 0.0.1 printed for the quickstart pair with each method named.

**Lanes.** Every test here is in the fast lane: none takes over ten seconds of setup and call
except PF0.2's, which is the only test of its invariant.

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF0.1 the wheel, its one package and its one script | ``test_pf0_1_*`` |
| PF0.2 ``python -m poisson_prove`` is the command | ``test_pf0_2_*`` |
| PF0.3 every schema string written is the new one | ``test_pf0_3_*`` |
| PF0.4 span keys use ``poisson_prove.``; old keys lift; the new key wins | ``test_pf0_4_*`` |
| PF0.5 the old name is spelled in one module only | ``test_pf0_5_*``, with the readers of PF0.4, PF0.6, PF0.8 and PF0.9 |
| PF0.6 every read verb reads the 0.0.1 stores and rewrites nothing | ``test_pf0_6_*`` |
| PF0.7 the 0.0.1 quickstart pair gives what 0.0.1 gave, method named | ``test_pf0_7_*`` |
| PF0.8 ``POISSON_PROVE_STORE``; ``PROOFLOAD_STORE`` alone is noted, not read | ``test_pf0_8_*`` |
| PF0.9 the default store is ``./prove-runs``; an old default store alone is refused | ``test_pf0_9_*`` |
| PF0.10 default output folders | ``test_pf0_10_*`` |
| PF0.11 install hints | ``test_pf0_11_*`` |
| PF0.12 an old run's provenance on the report, the receipt and the page | ``test_pf0_12_*`` |
| PF0.13 the Go1 golden numbers | the existing Go1 tests, moved for the names only |
"""

from __future__ import annotations

import ast
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "poisson_prove"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stores-0.0.1"
STORE = FIXTURE / "store"
RECORDED = FIXTURE / "recorded"
RUNS: dict[str, str] = json.loads((FIXTURE / "runs.json").read_text(encoding="utf-8"))
QA, QB = RUNS["quickstart_before"], RUNS["quickstart_after"]
MOCK = "poisson_prove.examples.mock_agent"
SCRIPT = Path(sys.executable).parent / "poisson-prove"

#: The eleven span keys Prove writes, documents or stamps (section 2.3).
SPAN_KEYS = (
    "attempt", "episode", "error_type", "fault", "gate", "logprobs", "outcome", "outcome_by",
    "run_id", "step_name", "truncated",
)
#: Every verb that reads or writes a store.
STORE_VERBS = ("sweep", "diff", "check", "report", "paired", "serve", "inspect", "runs")

SMALL_SPEC = """\
target_id = "mock-agent"
t_unit = "tool_calls"
replicates = 20

[axes.task_id]
type = "categorical"
values = ["search", "refund"]

[axes.tool_fail_rate]
type = "continuous"
values = [0.3, 0.55]
"""

#: A paired-replay declaration whose one sweep is the 0.0.1 quickstart pair. It parses; the runs
#: it names carry no request spans, so ``paired`` refuses them, which is all the store tests need.
QUICKSTART_DECLARATION = f"""\
value_key = "answers.q1.score"
cluster_key = "task_id"
stratum_key = "tool_fail_rate"
request_span = "scorer.request"
model_key = "model"
model_pin = "scorer-1"
exemptions = []
headers = "not_recorded"
retries = "not_recorded"
bootstrap_b = 200
bootstrap_seed = 1

[[cuts]]
name = "c60"
threshold = 0.60
comparison = "ge"

[[sweeps]]
name = "S1"
a = "{QA}"
b = "{QB}"
"""


@dataclass(frozen=True)
class Result:
    code: int
    out: str
    err: str


def run_cli(argv: list[str]) -> Result:
    """``poisson-prove ARGV`` in this process, reading the environment and cwd as they are."""
    from poisson_prove import cli

    out, err = StringIO(), StringIO()
    code = cli.main(list(argv), stdout=out, stderr=err, stdin=StringIO())
    return Result(code, out.getvalue(), err.getvalue())


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PROOFLOAD_STORE", "POISSON_PROVE_STORE")}
    env.update(COLUMNS="100", **extra)
    return env


def tree_digest(root: Path) -> dict[str, str]:
    """Every file under ``root``, by relative path, with its sha256."""
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def run_ids(store: Path) -> set[str]:
    return {p.name for p in store.iterdir() if (p / "manifest.json").is_file()} if store.is_dir() else set()


def copy_runs(dest: Path, *names: str) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copytree(STORE / name, dest / name)
    return dest


@pytest.fixture(autouse=True)
def _no_store_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROOFLOAD_STORE", raising=False)
    monkeypatch.delenv("POISSON_PROVE_STORE", raising=False)


@pytest.fixture(scope="module")
def new_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str, str]:
    """A pair written by this build: the mock agent, then the patched one paired with it."""
    base = tmp_path_factory.mktemp("new-pair")
    spec = base / "small.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    store = base / "store"
    env_before = {k: os.environ.pop(k) for k in ("PROOFLOAD_STORE", "POISSON_PROVE_STORE") if k in os.environ}
    try:
        first = run_cli(["--store", str(store), "sweep", str(spec), "--target", f"{MOCK}:rollout", "--max-mde", "0.99", "--yes"])
        assert first.code == 0, first
        (a,) = run_ids(store)
        second = run_cli(["--store", str(store), "sweep", str(spec), "--target", f"{MOCK}:rollout_patched", "--pair-with", a, "--max-mde", "0.99", "--yes"])
        assert second.code == 0, second
        (b,) = run_ids(store) - {a}
    finally:
        os.environ.update(env_before)
    return store, a, b


# ---------- PF0.1 the wheel ----------


def test_pf0_1_the_wheel_is_poisson_prove_and_installs_one_package_and_one_script(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "the wheel is built with uv"
    env = clean_env(UV_PYTHON_PREFERENCE="only-system", UV_PYTHON_DOWNLOADS="never")
    dist = tmp_path / "dist"
    built = subprocess.run([uv, "build", "--wheel", "--out-dir", str(dist), str(ROOT)], env=env, capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("*.whl")
    assert re.fullmatch(r"poisson_prove-[^-]+-py3-none-any\.whl", wheel.name), wheel.name

    venv = tmp_path / "venv"
    made = subprocess.run([uv, "venv", "--python", sys.executable, str(venv)], env=env, capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    python = venv / "bin" / "python"
    purelib = Path(subprocess.run([str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], capture_output=True, text=True, check=True).stdout.strip())
    site_before, bin_before = set(os.listdir(purelib)), set(os.listdir(venv / "bin"))
    installed = subprocess.run([uv, "pip", "install", "--python", str(python), "--no-deps", str(wheel)], env=env, capture_output=True, text=True, timeout=120)
    assert installed.returncode == 0, installed.stderr

    added_site = set(os.listdir(purelib)) - site_before
    added_bin = set(os.listdir(venv / "bin")) - bin_before
    (dist_info,) = [name for name in added_site if name.endswith(".dist-info")]
    assert added_site == {"poisson_prove", dist_info}, added_site
    assert re.fullmatch(r"poisson_prove-[^-]+\.dist-info", dist_info), dist_info
    assert added_bin == {"poisson-prove"}, added_bin

    metadata = (purelib / dist_info / "METADATA").read_text(encoding="utf-8")
    assert re.search(r"^Name: poisson-prove$", metadata, re.MULTILINE), metadata[:300]
    record = (purelib / dist_info / "RECORD").read_text(encoding="utf-8")
    assert "proofload" not in record.lower(), [line for line in record.splitlines() if "proofload" in line.lower()]
    entry_points = (purelib / dist_info / "entry_points.txt").read_text(encoding="utf-8")
    scripts = re.search(r"\[console_scripts\]\n((?:.+\n?)*)", entry_points)
    assert scripts is not None, entry_points
    assert [line.split("=")[0].strip() for line in scripts.group(1).splitlines() if line.strip()] == ["poisson-prove"], entry_points

    gone = subprocess.run([str(python), "-I", "-c", "import proofload"], capture_output=True, text=True)
    assert gone.returncode != 0 and "ModuleNotFoundError" in gone.stderr, gone


# ---------- PF0.2 python -m poisson_prove ----------


def test_pf0_2_python_dash_m_gives_the_commands_stdout_stderr_and_exit_code(tmp_path: Path) -> None:
    assert SCRIPT.is_file(), f"no console script at {SCRIPT}; install this checkout"
    cwd = tmp_path / "cwd"
    copy_runs(cwd / "prove-runs", QA, QB)
    corpus: list[list[str]] = [
        [],
        ["--version"],
        ["--help"],
        *[[verb, "--help"] for verb in STORE_VERBS],
        ["runs"],
        ["--store", str(STORE), "runs"],
        ["diff", QA, QB],
        ["check", QA, QB, "--event", "violated"],
        ["inspect", QA, "--event", "violated", "--limit", "3"],
        ["serve", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--json"],
        ["no-such-verb"],
        ["diff", QA, "no-such-run"],
        ["inspect", QA],
    ]
    env = clean_env()

    def both(argv: list[str]) -> tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]]:
        script = subprocess.run([str(SCRIPT), *argv], cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        module = subprocess.run([sys.executable, "-m", "poisson_prove", *argv], cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        return script, module

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(both, corpus))
    for argv, (script, module) in zip(corpus, results, strict=True):
        assert (module.returncode, module.stdout, module.stderr) == (script.returncode, script.stdout, script.stderr), argv


# ---------- PF0.3 schema strings ----------


def test_pf0_3_new_rows_carry_poisson_prove_trace_1_and_nothing_names_proofload(new_pair: tuple[Path, str, str]) -> None:
    store, a, _ = new_pair
    parts = sorted((store / a).rglob("*.parquet"))
    assert parts, a
    schemas: set[str] = set()
    for part in parts:
        for row in pq.read_table(part).to_pylist():
            assert row["trace"] is not None, row
            schemas.add(json.loads(row["trace"])["schema"])
            text = json.dumps(row, default=str).lower()
            assert "proofload" not in text, text[:300]
    assert schemas == {"poisson-prove.trace/1"}, schemas


def test_pf0_3_a_new_manifest_records_poisson_prove_version_and_never_names_proofload(new_pair: tuple[Path, str, str]) -> None:
    store, a, b = new_pair
    for run in (a, b):
        text = (store / run / "manifest.json").read_text(encoding="utf-8")
        manifest = json.loads(text)
        assert isinstance(manifest["poisson_prove_version"], str) and manifest["poisson_prove_version"], manifest
        assert "proofload_version" not in manifest, manifest
        assert "proofload" not in text.lower(), text


def test_pf0_3_serve_json_is_poisson_prove_viewpair_7(new_pair: tuple[Path, str, str]) -> None:
    store, a, b = new_pair
    r = run_cli(["--store", str(store), "serve", a, b, "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--json"])
    assert r.code == 0, r
    assert json.loads(r.out)["schema"] == "poisson-prove.viewpair/7"
    assert "proofload" not in r.out.lower()


def test_pf0_3_the_agreement_digest_is_built_over_poisson_prove_agreement_1() -> None:
    from poisson_prove import tree

    assert tree.AGREEMENT_SCHEMA == "poisson-prove.agreement/1"


@pytest.fixture(scope="module")
def chaos_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """A run with ``[capture]`` and ``[chaos]``, swept by this build in a fresh interpreter, so
    the provider capture installs is never this process's."""
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    pytest.importorskip("openai", reason="the fault is declared on an OpenAI chat completion")
    base = tmp_path_factory.mktemp("chaos-run")
    (base / "pf0_chaos_target.py").write_text(CHAOS_TARGET, encoding="utf-8")
    (base / "chaos.toml").write_text(CHAOS_SPEC, encoding="utf-8")
    store = base / "store"
    r = subprocess.run(
        [sys.executable, "-m", "poisson_prove", "--store", str(store), "sweep", str(base / "chaos.toml"),
         "--target", "pf0_chaos_target:rollout", "--max-mde", "0.99", "--yes"],
        cwd=base, env=clean_env(PYTHONPATH=str(base)), capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, r.stderr
    (run,) = run_ids(store)
    return store, run


CHAOS_SPEC = """\
target_id = "pf0-chaos"
t_unit = "steps"
replicates = 3

[axes.prompt]
type = "categorical"
values = ["short", "long"]

[capture]
max_observation_bytes = 8192

[chaos]
fault = "tool_corrupt_single"
rate = 1.0
"""

CHAOS_TARGET = '''\
import httpx
import openai
from opentelemetry import trace as otel_trace

from poisson_prove import chaos
from poisson_prove.episode import Episode

BASE = "http://pf0.invalid/v1"
COMPLETION = {
    "id": "chatcmpl-pf0", "object": "chat.completion", "created": 1700000000, "model": "pf0-model",
    "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": "calling lookup",
        "tool_calls": [{"id": "call_1", "type": "function",
                        "function": {"name": "lookup", "arguments": '{"order": "A-1"}'}}]}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
}
TOOLS = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object", "properties": {"order": {"type": "string"}}}}}]


def _respond(request):
    return httpx.Response(200, json=COMPLETION)


def rollout(cfg, seed):
    client = openai.OpenAI(api_key="pf0", base_url=BASE, max_retries=0,
                           http_client=httpx.Client(transport=httpx.MockTransport(_respond), base_url=BASE))
    tracer = otel_trace.get_tracer("pf0")
    for name in ("plan", "solve"):
        with chaos.position(name, 1), tracer.start_as_current_span(f"chat {name}") as span:
            span.set_attribute("gen_ai.operation.name", "chat")
            client.chat.completions.create(model="pf0-model", messages=[{"role": "user", "content": name}], tools=TOOLS)
    return Episode(outcome="completed", t=2.0, horizon=10.0)
'''


def test_pf0_3_a_chaos_run_records_the_catalogue_as_poisson_prove_chaos_catalog_1(chaos_run: tuple[Path, str]) -> None:
    store, run = chaos_run
    manifest = json.loads((store / run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["environment"]["chaos"]["engine_version"] == "poisson-prove.chaos-catalog/1", manifest["environment"]["chaos"]


# ---------- PF0.4 span keys ----------


def test_pf0_4_the_span_key_constants_use_the_poisson_prove_prefix() -> None:
    from poisson_prove import trace

    assert trace.SCHEMA == "poisson-prove.trace/1"
    assert trace.LOGPROBS_KEY == "poisson_prove.logprobs"
    assert trace.TRUNCATED_KEY == "poisson_prove.truncated"


def test_pf0_4_the_stamper_keys_use_the_poisson_prove_prefix() -> None:
    pytest.importorskip("opentelemetry.sdk", reason="the stamper lives behind the [agent] extra")
    from poisson_prove import otel

    assert otel.RUN_ID_KEY == "poisson_prove.run_id"
    assert otel.EPISODE_KEY == "poisson_prove.episode"


def test_pf0_4_every_span_key_a_capture_and_chaos_run_stores_uses_the_new_prefix(chaos_run: tuple[Path, str]) -> None:
    store, run = chaos_run
    keys: set[str] = set()
    for part in sorted((store / run).rglob("*.parquet")):
        for row in pq.read_table(part).to_pylist():
            envelope = json.loads(row["trace"])
            for span in envelope["spans"]:
                keys |= set(span.get("attrs") or {})
    assert {"poisson_prove.run_id", "poisson_prove.episode", "poisson_prove.fault"} <= keys, sorted(keys)
    assert not [k for k in keys if k.startswith("proofload.")], sorted(keys)


def otlp_span(attributes: dict[str, Any]) -> dict[str, Any]:
    def value(v: Any) -> dict[str, Any]:
        return {"intValue": str(v)} if isinstance(v, int) else {"stringValue": v}

    return {
        "traceId": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a", "spanId": "0000000000000001", "name": "execute_tool lookup",
        "kind": 1, "startTimeUnixNano": "1756900000000000000", "endTimeUnixNano": "1756900000500000000",
        "attributes": [
            {"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}},
            *({"key": k, "value": value(v)} for k, v in attributes.items()),
        ],
        "status": {"code": "STATUS_CODE_UNSET"},
    }


LIFTED = {"step_name": "lookup-order", "outcome": "violated", "outcome_by": "code", "attempt": 2, "gate": "emitted"}


def test_pf0_4_from_otel_lifts_proofload_keys_to_the_same_trace_as_poisson_prove_keys() -> None:
    from poisson_prove.trace import from_otel

    old = from_otel([otlp_span({f"proofload.{k}": v for k, v in LIFTED.items()})])
    new = from_otel([otlp_span({f"poisson_prove.{k}": v for k, v in LIFTED.items()})])
    assert old == new
    (span,) = new.spans
    assert (span.step_name, span.outcome, span.outcome_by, span.attempt, span.gate) == tuple(LIFTED.values()), span


def test_pf0_4_with_both_prefixes_on_one_span_the_new_keys_value_is_used() -> None:
    from poisson_prove.trace import from_otel

    other = {"step_name": "old-step", "outcome": "completed", "outcome_by": "human", "attempt": 5, "gate": "declared"}
    both = {**{f"proofload.{k}": v for k, v in other.items()}, **{f"poisson_prove.{k}": v for k, v in LIFTED.items()}}
    (span,) = from_otel([otlp_span(both)]).spans
    assert (span.step_name, span.outcome, span.outcome_by, span.attempt, span.gate) == tuple(LIFTED.values()), span


def test_pf0_4_the_docs_name_only_the_new_span_key_prefix() -> None:
    pages = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    hits = [
        f"{page.relative_to(ROOT)}: proofload.{key}"
        for page in pages
        for key in SPAN_KEYS
        if re.search(rf"\bproofload\.{key}\b", page.read_text(encoding="utf-8"))
    ]
    assert hits == [], hits


# ---------- PF0.5 one module spells the old name ----------


def string_constants(path: Path) -> tuple[list[str], list[str]]:
    """``path``'s string literals, split into docstrings and every other string."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstring_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                docstring_nodes.add(id(body[0].value))
    docs: list[str] = []
    others: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            (docs if id(node) in docstring_nodes else others).append(node.value)
    return docs, others


OLD = re.compile(r"proofload|m11-catalog", re.IGNORECASE)


def test_pf0_5_the_old_strings_are_spelled_in_poisson_prove_compat_and_nowhere_else_in_src() -> None:
    compat = SRC / "_compat.py"
    assert compat.is_file(), compat
    spelled = {
        str(path.relative_to(SRC)): sorted({s for s in string_constants(path)[1] if OLD.search(s)})
        for path in sorted(SRC.rglob("*.py"))
    }
    outside = {name: found for name, found in spelled.items() if found and name != "_compat.py"}
    assert outside == {}, outside
    held = " ".join(spelled["_compat.py"])
    for old in ("proofload.trace/1", "proofload_version", "m11-catalog/1", "PROOFLOAD_STORE", "proofload-runs"):
        assert old in held, (old, spelled["_compat.py"])


def test_pf0_5_no_docstring_outside_the_compat_module_names_the_old_name() -> None:
    assert (SRC / "__init__.py").is_file(), SRC
    hits = {
        str(path.relative_to(SRC)): [d[:80] for d in string_constants(path)[0] if OLD.search(d)]
        for path in sorted(SRC.rglob("*.py"))
        if path.name != "_compat.py"
    }
    assert {name: found for name, found in hits.items() if found} == {}


# ---------- PF0.6 the 0.0.1 stores are read, never rewritten ----------


def test_pf0_6_the_committed_fixture_is_intact() -> None:
    """The precondition of every byte check below: the files are the ones the build wrote."""
    sums = {}
    for line in (FIXTURE / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        sums[name.removeprefix("store/")] = digest
    assert tree_digest(STORE) == sums
    assert run_ids(STORE) == set(RUNS.values())


#: Per fixture run, the invocations a read verb applies to. Each exits 0 on 0.0.1 itself. Not
#: listed, with the reason: ``inspect`` without ``--event`` (a refusal by design: it lists the
#: events instead), the single-run report of the chaos run without ``--event`` (its one outcome
#: leaves no event to infer, so ``--event completed`` is named), and ``paired`` (no run here
#: carries the request spans a declaration needs; ``paired`` refuses every one).
SINGLE_RUN_READS: dict[str, list[list[str]]] = {
    "quickstart_before": [["report", "{run}", "--x", "task_id", "--y", "tool_fail_rate", "--out", "{out}"]],
    "quickstart_after": [["report", "{run}", "--x", "task_id", "--y", "tool_fail_rate", "--out", "{out}"]],
    "timeout_and_crash": [["report", "{run}", "--x", "role", "--out", "{out}"]],
    "capture_cut": [["report", "{run}", "--x", "result_bytes", "--out", "{out}"]],
    "chaos": [["report", "{run}", "--x", "prompt", "--event", "completed", "--out", "{out}"]],
    "modal": [["report", "{run}", "--x", "task_id", "--out", "{out}"]],
    "pre_split": [["report", "{run}", "--x", "task_id", "--y", "tool_fail_rate", "--out", "{out}"]],
}


@pytest.mark.parametrize("role", sorted(SINGLE_RUN_READS))
def test_pf0_6_every_read_verb_exits_0_on_each_0_0_1_run_and_no_stored_byte_moves(role: str, tmp_path: Path) -> None:
    run = RUNS[role]
    before = tree_digest(STORE)
    invocations = [
        ["runs"],
        *[["inspect", "{run}", "--event", event, "--limit", "3"] for event in ("completed", "timeout", "violated")],
        *SINGLE_RUN_READS[role],
    ]
    for i, template in enumerate(invocations):
        argv = [arg.format(run=run, out=tmp_path / f"out-{i}") for arg in template]
        r = run_cli(["--store", str(STORE), *argv])
        assert r.code == 0, (argv, r)
    assert tree_digest(STORE) == before


def test_pf0_6_every_pair_verb_exits_0_on_the_0_0_1_quickstart_pair_and_no_stored_byte_moves(tmp_path: Path) -> None:
    before = tree_digest(STORE)
    invocations = [
        ["diff", QA, QB],
        ["check", QA, QB, "--event", "violated"],
        ["report", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(tmp_path / "report")],
        ["serve", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--event", "timeout", "--json"],
    ]
    for argv in invocations:
        r = run_cli(["--store", str(STORE), *argv])
        assert r.code == 0, (argv, r)
    assert tree_digest(STORE) == before


def test_pf0_6_runs_lists_every_0_0_1_run() -> None:
    r = run_cli(["--store", str(STORE), "runs"])
    assert r.code == 0, r
    for run in RUNS.values():
        assert run in r.out, (run, r.out)


def test_pf0_6_an_old_manifest_is_read_with_the_version_it_recorded_under_the_new_key(tmp_path: Path) -> None:
    """Section 2.3: a manifest with either key reads, and the manifest exposes one field. The copy's
    recorded version is one no build of Prove can be, so the running version cannot stand in for it."""
    from poisson_prove.store import Store

    store = copy_runs(tmp_path / "store", QA)
    path = store / QA / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["proofload_version"] == "0.0.1" and "poisson_prove_version" not in manifest
    manifest["proofload_version"] = "0.0.1rc7"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    read = Store(store).manifest(QA).to_dict()
    assert read["poisson_prove_version"] == "0.0.1rc7", read
    assert "proofload_version" not in read, read


# ---------- PF0.7 like for like on the 0.0.1 quickstart pair ----------

METHODS = ("fisher_bh", "mcnemar_bh")
CELL_FIELDS = ("config", "n_a", "n_b", "events_a", "events_b", "rate_a", "rate_b", "delta", "stat", "p", "q", "verdict", "mde")
GROUP_FIELDS = ("key", "cells", "n_a", "n_b", "location", "dispersion", "p_location", "p_dispersion", "p_group", "q_group", "rejects")
ROOT_FIELDS = ("p_omnibus", "p_location", "p_dispersion", "rejects")
BOUND_FIELDS = ("depth_configured", "depth", "q", "delta_star", "bound", "discoveries")


def same(got: Any, want: Any) -> bool:
    """Equal, where a NaN 0.0.1 wrote (a statistic with no value) equals a NaN read back."""
    return bool(got == want or (isinstance(want, float) and want != want and isinstance(got, float) and got != got))


def recorded(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((RECORDED / name).read_text(encoding="utf-8"))
    return data


def assert_same_tree(got: dict[str, Any], want: dict[str, Any]) -> None:
    for field in ROOT_FIELDS:
        assert got["root"][field] == want["root"][field], field
    assert got["fault_lines"]["rejected_groups"] == want["fault_lines"]["rejected_groups"]
    got_groups = {g["label"]: g for g in got["fault_lines"]["groups"]}
    assert sorted(got_groups) == sorted(g["label"] for g in want["fault_lines"]["groups"])
    for group in want["fault_lines"]["groups"]:
        for field in GROUP_FIELDS:
            assert got_groups[group["label"]][field] == group[field], (group["label"], field)
    for field in BOUND_FIELDS:
        assert got["bound"][field] == want["bound"][field], field


@pytest.mark.parametrize("method", METHODS)
def test_pf0_7_diff_json_on_the_0_0_1_pair_gives_0_0_1s_cells_omnibus_fault_lines_and_bound(method: str) -> None:
    r = run_cli(["--store", str(STORE), "diff", QA, QB, "--method", method, "--format", "json"])
    assert r.code == 0, r
    got, want = json.loads(r.out), recorded(f"diff-{method}.json")
    assert got["method"] == want["method"] == method
    assert sorted(got["by_event"]) == sorted(want["by_event"])
    for event, block in want["by_event"].items():
        got_cells = {c["config_hash"]: c for c in got["by_event"][event]["cells"]}
        assert sorted(got_cells) == sorted(c["config_hash"] for c in block["cells"]), event
        for cell in block["cells"]:
            for field in CELL_FIELDS:
                assert same(got_cells[cell["config_hash"]][field], cell[field]), (event, cell["config_hash"], field)
    assert got["omnibus"]["p_omnibus"] == want["omnibus"]["p_omnibus"]
    assert_same_tree(got["tree"], want["tree"])


@pytest.mark.parametrize("method", METHODS)
def test_pf0_7_serve_json_on_the_0_0_1_pair_gives_0_0_1s_cells_omnibus_fault_lines_and_bound(method: str) -> None:
    r = run_cli(["--store", str(STORE), "serve", QA, QB, "--event", "timeout", "--event", "violated",
                 "--x", "task_id", "--y", "tool_fail_rate", "--method", method, "--json"])
    assert r.code == 0, r
    got, want = json.loads(r.out), recorded(f"serve-{method}.json")
    got_panels = {p["event"]: p for p in got["panels"]}
    assert sorted(got_panels) == sorted(p["event"] for p in want["panels"])
    for panel in want["panels"]:
        got_cells = {c["config_hash"]: c for c in got_panels[panel["event"]]["cells"]}
        assert sorted(got_cells) == sorted(c["config_hash"] for c in panel["cells"]), panel["event"]
        for cell in panel["cells"]:
            for field in CELL_FIELDS:
                assert same(got_cells[cell["config_hash"]][field], cell[field]), (panel["event"], cell["config_hash"], field)
    assert_same_tree(got["tree"], want["tree"])


def table_data_rows(markdown: str) -> list[str]:
    """Every markdown table row that is neither a header nor the separator under one."""
    lines = markdown.splitlines()

    def separator(line: str) -> bool:
        return line.startswith("|") and set(line) <= set("|-: ")

    return [
        line for i, line in enumerate(lines)
        if line.startswith("|") and not separator(line) and not (i + 1 < len(lines) and separator(lines[i + 1]))
    ]


def section(markdown: str, heading: str) -> str:
    start = markdown.index(f"\n{heading}\n")
    end = markdown.find("\n## ", start + 1)
    return markdown[start: end if end >= 0 else None]


@pytest.mark.parametrize("method", METHODS)
def test_pf0_7_report_on_the_0_0_1_pair_gives_0_0_1s_tables_and_bound(method: str, tmp_path: Path) -> None:
    out = tmp_path / "report"
    r = run_cli(["--store", str(STORE), "report", QA, QB, "--event", "timeout", "--event", "violated",
                 "--x", "task_id", "--y", "tool_fail_rate", "--method", method, "--out", str(out)])
    assert r.code == 0, r
    got = (out / "report.md").read_text(encoding="utf-8")
    want = (RECORDED / f"report-{method}" / "report.md").read_text(encoding="utf-8")
    assert table_data_rows(got) == table_data_rows(want)
    number = r"-?\d+(?:\.\d+)?"
    assert re.findall(number, section(got, "## Bound")) == re.findall(number, section(want, "## Bound"))


# ---------- PF0.8 the store variable ----------


def write_inputs(base: Path) -> dict[str, Path]:
    base.mkdir(parents=True, exist_ok=True)
    spec = base / "small.toml"
    spec.write_text(SMALL_SPEC, encoding="utf-8")
    declaration = base / "declaration.toml"
    declaration.write_text(QUICKSTART_DECLARATION, encoding="utf-8")
    return {"spec": spec, "declaration": declaration}


def verb_argv(verb: str, inputs: dict[str, Path], out: Path) -> list[str]:
    """One invocation per verb that would succeed on a store holding the quickstart pair,
    except ``paired``, which refuses those runs after reading the store."""
    return {
        "sweep": ["sweep", str(inputs["spec"]), "--target", f"{MOCK}:rollout", "--max-mde", "0.99", "--yes"],
        "diff": ["diff", QA, QB],
        "check": ["check", QA, QB, "--event", "violated"],
        "report": ["report", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(out)],
        "paired": ["paired", "--declaration", str(inputs["declaration"]), "--out", str(out)],
        "serve": ["serve", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--json"],
        "inspect": ["inspect", QA, "--event", "violated", "--limit", "3"],
        "runs": ["runs"],
    }[verb]


def test_pf0_8_poisson_prove_store_names_the_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = copy_runs(tmp_path / "elsewhere", QA, QB)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("POISSON_PROVE_STORE", str(store))
    r = run_cli(["runs"])
    assert r.code == 0, r
    assert QA in r.out and QB in r.out, r.out
    assert list(cwd.iterdir()) == []


@pytest.mark.parametrize("verb", STORE_VERBS)
def test_pf0_8_proofload_store_set_alone_is_not_read_and_every_verb_notes_it(verb: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "cwd"
    copy_runs(cwd / "prove-runs", QA, QB)
    old = copy_runs(tmp_path / "old-variable-store", RUNS["modal"])
    inputs = write_inputs(tmp_path / "inputs")
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("PROOFLOAD_STORE", str(old))
    old_before = tree_digest(old)
    r = run_cli(verb_argv(verb, inputs, tmp_path / "out"))
    notes = [line for line in r.err.splitlines() if "PROOFLOAD_STORE" in line]
    assert len(notes) == 1, r
    assert notes[0].startswith("note: ") and "POISSON_PROVE_STORE" in notes[0], notes
    assert "PROOFLOAD_STORE" not in r.out, r.out
    if verb == "runs":
        assert r.code == 0, r
        assert QA in r.out and QB in r.out and RUNS["modal"] not in r.out, r.out
    assert tree_digest(old) == old_before


@pytest.mark.parametrize("verb", STORE_VERBS)
def test_pf0_8_with_both_variables_set_the_new_one_names_the_store_and_nothing_is_noted(verb: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = copy_runs(tmp_path / "new-variable-store", QA, QB)
    old = copy_runs(tmp_path / "old-variable-store", RUNS["modal"])
    inputs = write_inputs(tmp_path / "inputs")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("PROOFLOAD_STORE", str(old))
    monkeypatch.setenv("POISSON_PROVE_STORE", str(store))
    r = run_cli(verb_argv(verb, inputs, tmp_path / "out"))
    assert "PROOFLOAD_STORE" not in r.out + r.err, r
    if verb == "runs":
        assert r.code == 0, r
        assert QA in r.out and QB in r.out and RUNS["modal"] not in r.out, r.out


# ---------- PF0.9 the default store ----------


@pytest.mark.parametrize("verb", STORE_VERBS)
def test_pf0_9_with_only_proofload_runs_present_every_store_verb_refuses_and_creates_nothing(verb: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "cwd"
    copy_runs(cwd / "proofload-runs", QA, QB)
    inputs = write_inputs(tmp_path / "inputs")
    monkeypatch.chdir(cwd)
    argv = verb_argv(verb, inputs, tmp_path / "out")
    if verb in ("report", "paired"):
        argv = argv[: argv.index("--out")]  # the default folder, which would land in cwd
    before = tree_digest(cwd)
    r = run_cli(argv)
    assert r.code == 1, r
    assert r.out == "", r.out
    lines = r.err.splitlines()
    assert len(lines) == 3, lines
    assert lines[0].startswith("error: ") and "prove-runs" in lines[0] and "proofload-runs" in lines[0], lines
    assert lines[1] == "  next: mv proofload-runs prove-runs", lines
    assert lines[2].startswith("  next: poisson-prove ") and "--store proofload-runs" in lines[2], lines
    assert tree_digest(cwd) == before
    assert sorted(p.name for p in cwd.iterdir()) == ["proofload-runs"]
    assert not (tmp_path / "out").exists()


def test_pf0_9_the_default_store_is_prove_runs_and_an_old_one_beside_it_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "cwd"
    copy_runs(cwd / "prove-runs", QA, QB)
    copy_runs(cwd / "proofload-runs", RUNS["modal"])
    monkeypatch.chdir(cwd)
    r = run_cli(["runs"])
    assert r.code == 0, r
    assert QA in r.out and QB in r.out and RUNS["modal"] not in r.out, r.out


def test_pf0_9_a_store_named_on_the_command_line_is_read_even_when_only_proofload_runs_is_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "cwd"
    copy_runs(cwd / "proofload-runs", QA, QB)
    monkeypatch.chdir(cwd)
    r = run_cli(["--store", "proofload-runs", "runs"])
    assert r.code == 0, r
    assert QA in r.out and QB in r.out, r.out


def test_pf0_9_sweep_with_no_store_anywhere_writes_into_prove_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = write_inputs(tmp_path / "inputs")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    r = run_cli(verb_argv("sweep", inputs, tmp_path / "out"))
    assert r.code == 0, r
    assert sorted(p.name for p in cwd.iterdir()) == ["prove-runs"]
    assert len(run_ids(cwd / "prove-runs")) == 1


# ---------- PF0.10 default output folders ----------


def slugged(name: str) -> bool:
    return name == name.lower() and " " not in name and "/" not in name and "proofload" not in name


def test_pf0_10_a_pair_reports_into_prove_report_a_vs_b(new_pair: tuple[Path, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, a, b = new_pair
    monkeypatch.chdir(tmp_path)
    r = run_cli(["--store", str(store), "report", a, b, "--x", "task_id", "--y", "tool_fail_rate"])
    assert r.code == 0, r
    (folder,) = list(tmp_path.iterdir())
    match = re.fullmatch(r"prove-report-(.+)-vs-(.+)", folder.name)
    assert match is not None and slugged(folder.name), folder.name
    assert (folder / "report.md").is_file()


def test_pf0_10_a_single_run_reports_into_prove_report_run(new_pair: tuple[Path, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, a, _ = new_pair
    monkeypatch.chdir(tmp_path)
    r = run_cli(["--store", str(store), "report", a, "--x", "task_id", "--y", "tool_fail_rate"])
    assert r.code == 0, r
    (folder,) = list(tmp_path.iterdir())
    assert folder.name.startswith("prove-report-") and "-vs-" not in folder.name and slugged(folder.name), folder.name
    assert (folder / "report.md").is_file()


PAIRED_DECLARATION = """\
value_key = "answers.q1.score"
cluster_key = "item"
stratum_key = "cut"
request_span = "scorer.request"
model_key = "model"
model_pin = "scorer-1.13.0"
exemptions = ["x-request-id"]
headers = "not_recorded"
retries = "not_recorded"
bootstrap_b = 200
bootstrap_seed = 20260922

[[cuts]]
name = "c60"
threshold = 0.60
comparison = "ge"

[[sweeps]]
name = "S1"
a = "S1-a"
b = "S1-b"
"""


def write_paired_store(root: Path) -> None:
    """Two runs replaying one request per item: the first three items flip between the arms."""
    from poisson_prove.episode import Episode
    from poisson_prove.store import EpisodeRecord, RunManifest, Store
    from poisson_prove.trace import Span, Trace

    store = Store(root)
    epoch, second = 1_790_000_000_000_000_000, 1_000_000_000
    for arm_index, arm in enumerate(("a", "b")):
        run_id = f"S1-{arm}"
        store.create_run(RunManifest(
            run_id=run_id, target_id="scorer@v1", t_unit="steps", run_salt="9f4a1c62d08e5b37",
            axis_types={"item": "categorical", "cut": "categorical"}, backend="local",
            environment={"python": "3.11.7", "platform": "test", "capture": {"content": True, "max_observation_bytes": "none"}},
        ))
        records = []
        for i in range(8):
            value = "0.05" if (arm == "b" and i < 3) else "0.95"
            start = epoch + i * 2 * second + arm_index * 60 * second
            span = Span(
                span_id="0000000000000001", parent_id=None, kind="http", name="scorer.request",
                start_ns=start, end_ns=start + 400_000_000,
                input=f'{{"model": "scorer-1.13.0", "state": "state of item {i}", "temperature": 0.30, "max_tokens": 64}}',
                output='{"answers": {"q1": {"score": 0.62}}}', tokens={"in": 400, "out": 12},
                attrs={"url.full": "https://api.example.test/v1/evaluate", "http.request.method": "POST"},
            )
            episode = Episode(
                outcome="acted" if value == "0.95" else "declined", t=1.0, horizon=10.0,
                meta={"trace": Trace(spans=(span,), source="record").to_dict(), "answers": {"q1": {"score": value}}},
            )
            records.append(EpisodeRecord.from_episode(
                episode, run_id=run_id, config={"item": f"c60-i{i:03d}", "cut": "c60"}, seed=1000 + i,
                replicate_index=0, wall_time=0.1,
            ))
        store.append(run_id, records)
        store.mark_complete(run_id)


def test_pf0_10_paired_writes_into_prove_paired_and_a_digest_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tmp_path / "store"
    write_paired_store(store)
    declaration = tmp_path / "declaration.toml"
    declaration.write_text(PAIRED_DECLARATION, encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    r = run_cli(["--store", str(store), "paired", "--declaration", str(declaration)])
    assert r.code == 0, r
    (folder,) = list(cwd.iterdir())
    assert re.fullmatch(r"prove-paired-[0-9a-f]+", folder.name), folder.name
    assert (folder / "pair_assertion.json").is_file()


# ---------- PF0.11 install hints ----------


def test_pf0_11_the_modal_backend_without_modal_names_poisson_prove_with_its_extra_in_quotes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = write_inputs(tmp_path / "inputs")
    monkeypatch.setitem(sys.modules, "modal", None)
    r = run_cli(["--store", str(tmp_path / "store"), "sweep", str(inputs["spec"]), "--target", f"{MOCK}:rollout",
                 "--backend", "modal", "--max-mde", "0.99", "--yes"])
    assert r.code != 0, r
    assert 'pip install "poisson-prove[modal]"' in r.err, r.err


def test_pf0_11_every_install_hint_in_src_that_names_prove_is_the_quoted_distribution_with_an_extra() -> None:
    hints = sorted({
        s for path in sorted(SRC.rglob("*.py")) for s in string_constants(path)[1] if "pip install" in s
    })
    naming_prove = [h for h in hints if "burla==" not in h]
    assert naming_prove, hints
    for hint in naming_prove:
        assert re.search(r'pip install "poisson-prove\[[a-z]+\]"', hint), hint


# ---------- PF0.12 an old run's provenance ----------


def mentions_old_writer(text: str) -> bool:
    return any("proofload" in line.lower() and "0.0.1" in line for line in text.splitlines())


def test_pf0_12_the_report_and_receipt_of_an_old_pair_say_it_was_written_by_proofload_0_0_1(tmp_path: Path) -> None:
    out = tmp_path / "report"
    r = run_cli(["--store", str(STORE), "report", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(out)])
    assert r.code == 0, r
    assert mentions_old_writer((out / "report.md").read_text(encoding="utf-8"))
    receipt = html.unescape(re.sub(r"<[^>]+>", "\n", (out / "receipt.html").read_text(encoding="utf-8")))
    assert mentions_old_writer(receipt)


def test_pf0_12_the_report_and_receipt_of_a_new_pair_never_name_proofload(new_pair: tuple[Path, str, str], tmp_path: Path) -> None:
    store, a, b = new_pair
    out = tmp_path / "report"
    r = run_cli(["--store", str(store), "report", a, b, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(out)])
    assert r.code == 0, r
    for name in ("report.md", "receipt.html"):
        assert "proofload" not in (out / name).read_text(encoding="utf-8").lower(), name


def served_page(store: Path, a: str, b: str) -> str:
    """The page ``serve`` holds for ``a`` against ``b``, fetched once over loopback."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "poisson_prove", "--store", str(store), "serve", a, b, "--x", "task_id", "--y", "tool_fail_rate",
         "--event", "violated"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=clean_env(),
    )
    try:
        assert proc.stdout is not None
        first = proc.stdout.readline()
        url = re.search(r"http://127\.0\.0\.1:\d+/", first)
        assert url is not None, first
        with urllib.request.urlopen(url.group(0), timeout=60) as response:
            return str(response.read().decode("utf-8"))
    finally:
        proc.terminate()
        proc.wait(timeout=60)


def test_pf0_12_the_page_of_an_old_pair_says_it_was_written_by_proofload_0_0_1() -> None:
    page = served_page(STORE, QA, QB)
    assert mentions_old_writer(html.unescape(re.sub(r"<[^>]+>", "\n", page)))


def test_pf0_12_the_page_of_a_new_pair_never_names_proofload(new_pair: tuple[Path, str, str]) -> None:
    store, a, b = new_pair
    assert "proofload" not in served_page(store, a, b).lower()
