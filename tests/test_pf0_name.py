"""PF0, the name: the frozen tests for the rename from ``proofload`` to Poisson Prove.

Its invariants are PF0.1 to PF0.13. The code is written against this file, which is not edited
to fit it.

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

**The built wheel.** PF0.1 and PF0.2 share one module fixture: the wheel built from this checkout and
installed into a throwaway virtual environment of its own, first alone (PF0.1 reads what it adds)
and then with its dependencies (PF0.2 runs the command it installed). Nothing falls back to the
environment the suite runs in, and nothing skips: the point is that the command exists.

**Lanes.** Every test here is in the fast lane (ten seconds of setup and call, measured on the
runner, decides it; PF10 declares the ``slow`` marker).

**Invariant-to-test map**

| invariant | tests |
|---|---|
| PF0.1 the wheel, its one package and its one script | ``test_pf0_1_*`` |
| PF0.2 ``python -m poisson_prove`` is the command | ``test_pf0_2_*`` |
| PF0.3 every schema string written is the new one | ``test_pf0_3_*`` |
| PF0.4 span keys use ``poisson_prove.``; old keys lift; the new key wins | ``test_pf0_4_*`` |
| PF0.5 the old name is spelled in one module only, and every reader goes through it | ``test_pf0_5_*``: two literal checks and one behaviour check with that module made to fail |
| PF0.6 every read verb reads the 0.0.1 stores and rewrites nothing | ``test_pf0_6_*`` |
| PF0.7 the 0.0.1 quickstart pair gives what 0.0.1 gave, method named | ``test_pf0_7_*`` |
| PF0.8 ``POISSON_PROVE_STORE``; ``PROOFLOAD_STORE`` alone is noted, not read | ``test_pf0_8_*`` |
| PF0.9 the default store is ``./prove-runs``; an old default store alone is refused | ``test_pf0_9_*`` |
| PF0.10 default output folders | ``test_pf0_10_*`` |
| PF0.11 install hints | ``test_pf0_11_*`` |
| PF0.12 an old run's provenance on the report, the receipt and the page | ``test_pf0_12_*`` |
| PF0.13 the fixture pair's numbers | the existing fixture-pair tests (now on the generated lattice pair, ``tests/lattice.py``), moved for the names only |
"""

from __future__ import annotations

import ast
import functools
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
from test_pf4_stats import _ref_fisher_limits, _ref_limit, _ref_paired_power
from conftest import writable_copy

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "poisson_prove"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stores-0.0.1"
# PF12: report and serve save into the store they read, so these tests read a
# per-process copy of the committed fixture (conftest.writable_copy); the committed folder is never written.
STORE = writable_copy(FIXTURE / "store")
RECORDED = FIXTURE / "recorded"
RUNS: dict[str, str] = json.loads((FIXTURE / "runs.json").read_text(encoding="utf-8"))
QA, QB = RUNS["quickstart_before"], RUNS["quickstart_after"]
MOCK = "poisson_prove.examples.mock_agent"
#: The store variable's note, word for word.
STORE_VARIABLE_NOTE = "note: PROOFLOAD_STORE is set and no longer read; Prove reads POISSON_PROVE_STORE"

#: The eleven span keys Prove writes, documents or stamps.
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


# ---------- PF0.1 and PF0.2: the wheel, installed where nothing else is ----------


@dataclass(frozen=True)
class Installed:
    wheel: Path
    venv: Path
    purelib: Path
    added_site: frozenset[str]
    added_bin: frozenset[str]

    @property
    def python(self) -> Path:
        return self.venv / "bin" / "python"

    @property
    def command(self) -> Path:
        return self.venv / "bin" / "poisson-prove"


def install_env() -> dict[str, str]:
    env = {k: v for k, v in clean_env().items() if k not in ("PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME")}
    env.update(UV_PYTHON_PREFERENCE="only-system", UV_PYTHON_DOWNLOADS="never")
    return env


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Installed:
    """The wheel built from this checkout, installed into a virtual environment of its own: first
    alone, to see exactly what it adds, then with its dependencies, so its command runs."""
    uv = shutil.which("uv")
    assert uv is not None, "the wheel is built and installed with uv"
    base = tmp_path_factory.mktemp("installed")
    env = install_env()
    built = subprocess.run([uv, "build", "--wheel", "--out-dir", str(base / "dist"), str(ROOT)], env=env, capture_output=True, text=True, timeout=600)
    assert built.returncode == 0, built.stderr
    (wheel,) = (base / "dist").glob("*.whl")
    venv = base / "venv"
    made = subprocess.run([uv, "venv", "--python", sys.executable, str(venv)], env=env, capture_output=True, text=True, timeout=300)
    assert made.returncode == 0, made.stderr
    python = venv / "bin" / "python"
    purelib = Path(subprocess.run([str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"], capture_output=True, text=True, check=True).stdout.strip())
    site_before, bin_before = set(os.listdir(purelib)), set(os.listdir(venv / "bin"))
    alone = subprocess.run([uv, "pip", "install", "--python", str(python), "--no-deps", str(wheel)], env=env, capture_output=True, text=True, timeout=300)
    assert alone.returncode == 0, alone.stderr
    added_site = frozenset(set(os.listdir(purelib)) - site_before)
    added_bin = frozenset(set(os.listdir(venv / "bin")) - bin_before)
    with_deps = subprocess.run([uv, "pip", "install", "--python", str(python), str(wheel)], env=env, capture_output=True, text=True, timeout=900)
    assert with_deps.returncode == 0, with_deps.stderr
    return Installed(wheel, venv, purelib, added_site, added_bin)


def test_pf0_1_the_wheel_is_poisson_prove_and_installs_one_package_and_one_script(installed: Installed) -> None:
    assert re.fullmatch(r"poisson_prove-[^-]+-py3-none-any\.whl", installed.wheel.name), installed.wheel.name
    (dist_info,) = [name for name in installed.added_site if name.endswith(".dist-info")]
    assert installed.added_site == {"poisson_prove", dist_info}, installed.added_site
    assert re.fullmatch(r"poisson_prove-[^-]+\.dist-info", dist_info), dist_info
    assert installed.added_bin == {"poisson-prove"}, installed.added_bin

    metadata = (installed.purelib / dist_info / "METADATA").read_text(encoding="utf-8")
    assert re.search(r"^Name: poisson-prove$", metadata, re.MULTILINE), metadata[:300]
    record = (installed.purelib / dist_info / "RECORD").read_text(encoding="utf-8")
    assert "proofload" not in record.lower(), [line for line in record.splitlines() if "proofload" in line.lower()]
    entry_points = (installed.purelib / dist_info / "entry_points.txt").read_text(encoding="utf-8")
    scripts = re.search(r"\[console_scripts\]\n((?:.+\n?)*)", entry_points)
    assert scripts is not None, entry_points
    assert [line.split("=")[0].strip() for line in scripts.group(1).splitlines() if line.strip()] == ["poisson-prove"], entry_points

    gone = subprocess.run([str(installed.python), "-I", "-c", "import proofload"], capture_output=True, text=True, env=install_env())
    assert gone.returncode != 0 and "ModuleNotFoundError" in gone.stderr, gone


def test_pf0_2_python_dash_m_gives_the_installed_commands_stdout_stderr_and_exit_code(installed: Installed, tmp_path: Path) -> None:
    """The command the wheel installed, against ``python -m poisson_prove`` in the same environment."""
    assert installed.command.is_file(), installed.command
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
    env = install_env()

    def both(argv: list[str]) -> tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]]:
        command = subprocess.run([str(installed.command), *argv], cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        module = subprocess.run([str(installed.python), "-m", "poisson_prove", *argv], cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        return command, module

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(both, corpus))
    for argv, (command, module) in zip(corpus, results, strict=True):
        assert (module.returncode, module.stdout, module.stderr) == (command.returncode, command.stdout, command.stderr), argv
    version = results[1][0]
    assert version.returncode == 0 and version.stdout.startswith("poisson-prove "), version


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


#: The schema string the agreement form is hashed behind, and the one the 0.0.1 builds used.
AGREEMENT_SCHEMA = "poisson-prove.agreement/1"
OLD_AGREEMENT_SCHEMA = "proofload.agreement/1"


def lattice_agreement(event: str, schema: str) -> str:
    """The lattice pair's agreement digest for ``event`` in A28's canonical form,
    written here from the design's counts (``lattice.counts``) and not from ``tree.py``: one line
    per cell, ``[event, config_hash, n_a, n_b, events_a, events_b]``, sorted, the pair
    ``[schema, lines]`` as compact ASCII JSON, sha256, lowercase hex."""
    import hashlib

    import lattice

    lines = sorted(
        [event, r["config_hash"], int(r["n_a"]), int(r["n_b"]), int(r["events_a"]), int(r["events_b"])]
        for r in lattice.counts(event)
    )
    return hashlib.sha256(json.dumps([schema, lines], separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def test_pf0_3_the_agreement_digest_diff_prints_is_built_over_poisson_prove_agreement_1() -> None:
    import lattice

    # --json replaces --format json on diff.
    r = run_cli(["--store", str(lattice.root()), "diff", lattice.RUN_A, lattice.RUN_B, "--event", lattice.EVENT, "--json"])
    assert r.code == 0, r
    printed = json.loads(r.out)["tree"]["agreement"]
    assert printed == lattice_agreement(lattice.EVENT, AGREEMENT_SCHEMA)
    assert printed != lattice_agreement(lattice.EVENT, OLD_AGREEMENT_SCHEMA)


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
    # PF4 re-freeze (PF4.49): no lone condition of this 3-replicate design can be
    # flagged, which any accepted change below 1 refuses; --max-mde 1 admits it as 0.99 did.
    r = subprocess.run(
        [sys.executable, "-m", "poisson_prove", "--store", str(store), "sweep", str(base / "chaos.toml"),
         "--target", "pf0_chaos_target:rollout", "--max-mde", "1", "--yes"],
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
max_observation_bytes = 64
content = true

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
            span.set_attribute("gen_ai.tool.call.result", "r" * 400)
            client.chat.completions.create(model="pf0-model", messages=[{"role": "user", "content": name}], tools=TOOLS)
    return Episode(outcome="completed", t=2.0, horizon=10.0)
'''


def test_pf0_3_a_chaos_run_records_the_catalogue_as_poisson_prove_chaos_catalog_1(chaos_run: tuple[Path, str]) -> None:
    store, run = chaos_run
    manifest = json.loads((store / run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["environment"]["chaos"]["engine_version"] == "poisson-prove.chaos-catalog/1", manifest["environment"]["chaos"]


# ---------- PF0.4 span keys ----------


def test_pf0_4_every_span_key_a_capture_and_chaos_run_stores_uses_the_new_prefix(chaos_run: tuple[Path, str]) -> None:
    """What Prove stamps (the routing keys, the fault) and writes (the cut's wrapper around an
    observation over the cap), read off the stored rows of a run this build swept."""
    store, run = chaos_run
    keys: set[str] = set()
    observations = ""
    for part in sorted((store / run).rglob("*.parquet")):
        for row in pq.read_table(part).to_pylist():
            envelope = json.loads(row["trace"])
            for span in envelope["spans"]:
                keys |= set(span.get("attrs") or {})
            observations += row["trace_obs"] or ""
    assert {"poisson_prove.run_id", "poisson_prove.episode", "poisson_prove.fault"} <= keys, sorted(keys)
    assert not [k for k in keys if k.startswith("proofload.")], sorted(keys)
    assert '"poisson_prove.truncated"' in observations and "proofload" not in observations, observations[:300]


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


#: One value per span key (the eleven of ``SPAN_KEYS``). The first five become span fields; the
#: other six stay attributes, under the new prefix.
FIELD_KEYS: dict[str, Any] = {"step_name": "lookup-order", "outcome": "violated", "outcome_by": "code", "attempt": 2, "gate": "emitted"}
ATTR_KEYS: dict[str, Any] = {
    "episode": "c0ffee:0", "error_type": "TimeoutError", "fault": "llm_empty_single",
    "logprobs": "[-0.25, -1.5]", "run_id": "run-pf0", "truncated": "observation",
}
#: Another value for every key, carried under the old prefix beside the new one.
OTHER_VALUES: dict[str, Any] = {
    "step_name": "old-step", "outcome": "completed", "outcome_by": "human", "attempt": 5, "gate": "declared",
    "episode": "old:9", "error_type": "OldError", "fault": "llm_error_single", "logprobs": "[-9.0]",
    "run_id": "run-old", "truncated": "old",
}


def fields_of(span: Any) -> tuple[Any, ...]:
    return (span.step_name, span.outcome, span.outcome_by, span.attempt, span.gate)


def test_pf0_4_from_otel_lifts_proofload_keys_to_the_same_trace_as_poisson_prove_keys() -> None:
    """All eleven keys: the five that become fields, and the six that stay attributes under the new
    prefix, so a span carrying the old keys and one carrying the new give one trace."""
    from poisson_prove.trace import from_otel

    assert sorted({*FIELD_KEYS, *ATTR_KEYS}) == sorted(SPAN_KEYS) == sorted(OTHER_VALUES)
    values = {**FIELD_KEYS, **ATTR_KEYS}
    old = from_otel([otlp_span({f"proofload.{k}": v for k, v in values.items()})])
    new = from_otel([otlp_span({f"poisson_prove.{k}": v for k, v in values.items()})])
    assert old == new
    (span,) = new.spans
    assert fields_of(span) == tuple(FIELD_KEYS.values()), span
    for key, value in ATTR_KEYS.items():
        assert span.attrs[f"poisson_prove.{key}"] == value, (key, dict(span.attrs))
    assert not [k for k in span.attrs if k.startswith("proofload.")], dict(span.attrs)


def test_pf0_4_with_both_prefixes_on_one_span_the_new_keys_value_is_used() -> None:
    """All eleven keys, each carried under both prefixes with different values: the new value is
    the one read, and the old key is not kept."""
    from poisson_prove.trace import from_otel

    both = {
        **{f"proofload.{k}": v for k, v in OTHER_VALUES.items()},
        **{f"poisson_prove.{k}": v for k, v in {**FIELD_KEYS, **ATTR_KEYS}.items()},
    }
    (span,) = from_otel([otlp_span(both)]).spans
    assert fields_of(span) == tuple(FIELD_KEYS.values()), span
    for key, value in ATTR_KEYS.items():
        assert span.attrs[f"poisson_prove.{key}"] == value, (key, dict(span.attrs))
    assert not [k for k in span.attrs if k.startswith("proofload.")], dict(span.attrs)


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


#: Run in a fresh interpreter, so the package is imported once with the compatibility module as the
#: probe leaves it. ``poisson_prove._compat`` is loaded from its file first and made to fail one of
#: two ways: ``raise`` replaces every function in it with one that raises and spoils every string it
#: holds that spells the old name; ``spoil`` rewrites its source so every string literal spelling the
#: old name, function bodies included, is spoiled, and its functions run on as written, knowing no
#: old string. Then the package is imported against that module. Each probe reads one kind of old
#: string through the public surface twice: with the old string there, and with it absent.
COMPAT_PROBE = r"""
import ast, importlib.util, io, json, os, re, shutil, sys, types

args = json.loads(sys.argv[1])
OLD = re.compile(r"proofload|m11-catalog", re.IGNORECASE)


class Sabotaged(Exception):
    pass


def spoil(value):
    if isinstance(value, str):
        return "<spoiled>" if OLD.search(value) else value
    if isinstance(value, (tuple, list, set, frozenset)):
        return type(value)(spoil(v) for v in value)
    if isinstance(value, dict):
        return {spoil(k): spoil(v) for k, v in value.items()}
    return value


class Spoiler(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, str) and OLD.search(node.value):
            return ast.copy_location(ast.Constant("<spoiled>"), node)
        return node


compat_path = os.path.join(args["src"], "_compat.py")
if args["sabotage"] == "spoil":
    compat = types.ModuleType("poisson_prove._compat")
    compat.__file__ = compat_path
    tree = ast.fix_missing_locations(Spoiler().visit(ast.parse(open(compat_path, encoding="utf-8").read())))
    sys.modules["poisson_prove._compat"] = compat
    exec(compile(tree, compat_path, "exec"), compat.__dict__)
if args["sabotage"] == "raise":
    spec = importlib.util.spec_from_file_location("poisson_prove._compat", compat_path)
    compat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compat)
    for name, value in list(vars(compat).items()):
        if name.startswith("__") or isinstance(value, (types.ModuleType, type)):
            continue
        if isinstance(value, types.FunctionType):
            def broken(*a, _name=name, **k):
                raise Sabotaged(_name)
            setattr(compat, name, broken)
        else:
            setattr(compat, name, spoil(value))
    sys.modules["poisson_prove._compat"] = compat

import pyarrow.parquet as pq
from poisson_prove import cli
from poisson_prove.store import Store
from poisson_prove.trace import Trace, from_otel

work = args["work"]


def attempt(read):
    try:
        return ["read", read()]
    except Exception as exc:
        return ["failed", type(exc).__name__]


def run(argv, cwd, variables):
    here = os.getcwd()
    saved = {k: os.environ.pop(k) for k in ("PROOFLOAD_STORE", "POISSON_PROVE_STORE") if k in os.environ}
    os.environ.update(variables)
    os.chdir(cwd)
    try:
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(argv, stdout=out, stderr=err, stdin=io.StringIO())
        return [code, out.getvalue(), err.getvalue()]
    finally:
        os.chdir(here)
        for k in variables:
            os.environ.pop(k, None)
        os.environ.update(saved)


def copy(run_id, dest):
    shutil.copytree(os.path.join(args["store"], run_id), os.path.join(dest, run_id))
    return os.path.join(dest, run_id)


def edit_manifest(run_dir, change):
    path = os.path.join(run_dir, "manifest.json")
    manifest = json.load(open(path, encoding="utf-8"))
    change(manifest)
    open(path, "w", encoding="utf-8").write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


observed = {}

# A trace stored under the old schema string, and the same trace under a schema nobody reads.
part = sorted(os.listdir(os.path.join(args["store"], args["qa"], "episodes")))[0]
stored = json.loads(pq.read_table(os.path.join(args["store"], args["qa"], "episodes", part)).to_pylist()[0]["trace"])
observed["trace schema"] = {
    "with": attempt(lambda: len(Trace.from_dict(stored).spans)),
    "without": attempt(lambda: len(Trace.from_dict({**stored, "schema": "unknown.trace/1"}).spans)),
}

# The version an old manifest recorded under the old key, and the same manifest with no version key.
def version(dest, change):
    edit_manifest(copy(args["qa"], dest), change)
    return lambda: Store(dest).manifest(args["qa"]).to_dict()["poisson_prove_version"]
observed["manifest version key"] = {
    "with": attempt(version(os.path.join(work, "with-version"), lambda m: m.__setitem__("proofload_version", "0.0.1rc7"))),
    "without": attempt(version(os.path.join(work, "without-version"), lambda m: m.pop("proofload_version"))),
}

# Span keys under the old prefix, and the same span without them.
def span(extra):
    return {
        "traceId": "5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a", "spanId": "0000000000000001", "name": "execute_tool lookup",
        "kind": 1, "startTimeUnixNano": "1756900000000000000", "endTimeUnixNano": "1756900000500000000",
        "attributes": [{"key": "gen_ai.operation.name", "value": {"stringValue": "execute_tool"}}, *extra],
        "status": {"code": "STATUS_CODE_UNSET"},
    }
def lifted(raw):
    def read():
        (one,) = from_otel([raw]).spans
        return [one.step_name, one.attrs.get("poisson_prove.run_id")]
    return read
old_keys = [
    {"key": "proofload.step_name", "value": {"stringValue": "lookup-order"}},
    {"key": "proofload.run_id", "value": {"stringValue": "run-pf0"}},
]
observed["span keys"] = {"with": attempt(lifted(span(old_keys))), "without": attempt(lifted(span([])))}

# The old store variable, set alone, and no variable set.
noted = os.path.join(work, "noted")
copy(args["qa"], os.path.join(noted, "prove-runs"))
observed["store variable"] = {
    "with": attempt(lambda: run(["runs"], noted, {"PROOFLOAD_STORE": os.path.join(work, "elsewhere")})),
    "without": attempt(lambda: run(["runs"], noted, {})),
}

# The old default store alone in the folder, and an empty folder.
old_default, empty = os.path.join(work, "old-default"), os.path.join(work, "empty")
copy(args["qa"], os.path.join(old_default, "proofload-runs"))
os.makedirs(empty)
# A missing store now exits 1 like the old-store refusal (a refusal exits 1), so each is
# read as its exit code and whether its stderr names the old folder.
def default_store(cwd):
    code, _, err = run(["runs"], cwd, {})
    return [code, "proofload-runs" in err]
observed["old default store"] = {
    "with": attempt(lambda: default_store(old_default)),
    "without": attempt(lambda: default_store(empty)),
}

# Who wrote an old pair, and the same pair with no version recorded.
def writer(store, label):
    def read():
        out = os.path.join(work, "report-" + label)
        code, _, err = run(["--store", store, "report", args["qa"], args["qb"], "--x", "task_id", "--y", "tool_fail_rate", "--out", out], work, {})
        assert code == 0, err
        return "written by proofload 0.0.1" in open(os.path.join(out, "report.md"), encoding="utf-8").read()
    return read
unversioned = os.path.join(work, "unversioned")
for run_id in (args["qa"], args["qb"]):
    edit_manifest(copy(run_id, unversioned), lambda m: m.pop("proofload_version"))
observed["old run's writer"] = {"with": attempt(writer(args["store"], "with")), "without": attempt(writer(unversioned, "without"))}

print(json.dumps(observed))
"""


def probe_compat(work: Path, *, sabotage: str | None) -> dict[str, Any]:
    work.mkdir(parents=True)
    arguments = json.dumps({"src": str(SRC), "store": str(STORE), "qa": QA, "qb": QB, "work": str(work), "sabotage": sabotage})
    done = subprocess.run([sys.executable, "-c", COMPAT_PROBE, arguments], cwd=work, env=clean_env(), capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr
    observed: dict[str, Any] = json.loads(done.stdout.strip().splitlines()[-1])
    return observed


def test_pf0_5_with_the_compat_module_failing_no_reader_recognises_an_old_string(tmp_path: Path) -> None:
    """PF0.5, by behaviour: each reader of an old string goes through
    ``poisson_prove._compat``. Untouched, every reader reads its old string, and reads something
    else when the old string is absent. With that module failing, either way the probe makes it
    fail, an old string makes no difference to any reader: each gives what it gives when the
    string is absent. A reader that recognises an old string on its own, by any spelling and in
    any part, behaves differently and fails this test."""
    fixture_before = tree_digest(STORE)
    readers = probe_compat(tmp_path / "untouched", sabotage=None)
    untouched = {name: reader["with"] for name, reader in readers.items()}
    assert untouched["trace schema"][0] == "read" and untouched["trace schema"][1] > 0, readers
    assert untouched["manifest version key"] == ["read", "0.0.1rc7"], readers
    assert untouched["span keys"] == ["read", ["lookup-order", "run-pf0"]], readers
    assert untouched["store variable"][0] == "read", readers
    code, out, err = untouched["store variable"][1]
    assert code == 0 and STORE_VARIABLE_NOTE in err.splitlines() and out == readers["store variable"]["without"][1][1], readers
    # The old-store refusal exits 1 and names the old folder.
    assert untouched["old default store"] == ["read", [1, True]], readers
    assert untouched["old run's writer"] == ["read", True], readers
    assert {name: reader for name, reader in readers.items() if reader["with"] == reader["without"]} == {}, readers
    for way in ("raise", "spoil"):
        sabotaged = probe_compat(tmp_path / way, sabotage=way)
        assert sorted(sabotaged) == sorted(readers), way
        still_recognised = {name: reader for name, reader in sabotaged.items() if reader["with"] != reader["without"]}
        assert still_recognised == {}, (way, still_recognised)
    # PF12 (PF12.1): the probes' report and serve save under ``.poisson/``;
    # no byte the build wrote moves.
    assert {k: v for k, v in tree_digest(STORE).items() if not k.startswith(".poisson/")} == {
        k: v for k, v in fixture_before.items() if not k.startswith(".poisson/")}


# ---------- PF0.6 the 0.0.1 stores are read, never rewritten ----------


def test_pf0_6_the_committed_fixture_is_intact() -> None:
    """The precondition of every byte check below: the files are the ones the build wrote."""
    sums = {}
    for line in (FIXTURE / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        sums[name.removeprefix("store/")] = digest
    # PF12: the committed folder itself, which no test writes (STORE is its per-process copy).
    assert tree_digest(FIXTURE / "store") == sums
    assert run_ids(FIXTURE / "store") == set(RUNS.values())


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
        # PF4 (PF4.20): a 0.0.1 run records no kind, so check's default --fail-on worse is refused;
        # --fail-on higher is the same gate on a failure event (fail when the rate rose).
        ["check", QA, QB, "--event", "violated", "--fail-on", "higher"],
        ["report", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(tmp_path / "report")],
        ["serve", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--event", "timeout", "--json"],
    ]
    for argv in invocations:
        r = run_cli(["--store", str(STORE), *argv])
        assert r.code == 0, (argv, r)
    # PF12 (PF12.1): report and serve save the comparison they show under
    # ``.poisson/``; no byte the build wrote moves.
    def stored(digest: dict[str, str]) -> dict[str, str]:
        return {k: v for k, v in digest.items() if not k.startswith(".poisson/")}

    assert stored(tree_digest(STORE)) == stored(before)


def test_pf0_6_runs_lists_every_0_0_1_run() -> None:
    r = run_cli(["--store", str(STORE), "runs"])
    assert r.code == 0, r
    for run in RUNS.values():
        assert run in r.out, (run, r.out)


def test_pf0_6_an_old_manifest_is_read_with_the_version_it_recorded_under_the_new_key(tmp_path: Path) -> None:
    """A manifest with either key reads, and the manifest exposes one field. The copy's
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


#: PF4 (PF4.20): a 0.0.1 run records no event kind, so a cell's verdict is now the direction word:
#: 0.0.1's ``safer`` (the rate fell) reads ``lower`` and its ``worse`` (rose) reads ``higher``.
DIRECTION_OF = {"safer": "lower", "worse": "higher", "unchanged": "unchanged"}
#: PF4 (PF4.18): the omnibus and every group p-value are Westfall-Young on one scale, so these
#: three fields move; every other field of the tree is 0.0.1's.
TREE_FIELDS_PF4_MOVES = ("p_omnibus", "p_group", "q_group")


def same(got: Any, want: Any) -> bool:
    """Equal, where a NaN 0.0.1 wrote (a statistic with no value) equals a NaN read back. Strict JSON
    now writes a NaN or an infinity as null, so null equals either."""
    if got is None and isinstance(want, float) and (want != want or want in (float("inf"), float("-inf"))):
        return True
    return bool(got == want or (isinstance(want, float) and want != want and isinstance(got, float) and got != got))


def recorded(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((RECORDED / name).read_text(encoding="utf-8"))
    return data


#: The comparison's false discovery rate, the level of 0.0.1's quickstart pair.
LIMIT_Q = 0.05


@functools.cache
def reference_mde(method: str, events_a: int, n: int, level: float) -> float | None:
    """A condition's detection limit at the lone-change level, from the stats file's references:
    Fisher's exact enumeration under ``fisher_bh``, the paired test's over ``n`` matched pairs under
    ``mcnemar_bh``; ``mde`` is the larger of the two directions, the one that is a number when the
    other has no room, and null otherwise."""
    p_a = events_a / n
    if method == "fisher_bh":
        rise, fall = _ref_fisher_limits(events_a, n, n, level)
    else:
        rise = _ref_limit(lambda g: _ref_paired_power(p_a, n, level, g, True), 1.0 - p_a)
        fall = _ref_limit(lambda g: _ref_paired_power(p_a, n, level, g, False), p_a)
    if rise is not None and fall is not None:
        return max(rise, fall)
    if rise is not None and p_a == 0.0:
        return rise
    if fall is not None and p_a == 1.0:
        return fall
    return None


def assert_same_cell(got: dict[str, Any], want: dict[str, Any], method: str, where: tuple[str, str],
                     rows: int) -> None:
    """0.0.1's cell, field by field, with the fields PF4 moves read as PF4 writes them; ``rows`` is
    the number of rows the comparison tests."""
    for field in CELL_FIELDS:
        if field == "mde":
            # PF4 re-freeze (PF4.22 to PF4.24): the limit is the exact power definition at the
            # lone-change level q / M, both directions, so 0.0.1's normal-approximation number moves;
            # it is recomputed here from the stats file's references.
            want_mde = reference_mde(method, got["events_a"], got["pairs"] if method == "mcnemar_bh" else got["n_a"],
                                     LIMIT_Q / rows)
            if want_mde is None:
                assert got[field] is None, (*where, field, got[field])
            else:
                assert got[field] is not None and abs(got[field] - want_mde) <= 1e-4 + 1e-12, (*where, field, got[field], want_mde)
        elif field == "verdict":
            # PF4 (PF4.20): the direction word in place of 0.0.1's safer/worse; the cell's
            # direction says the same.
            assert got[field] == got["direction"] == DIRECTION_OF[want[field]], (*where, field)
        elif field == "delta" and method == "mcnemar_bh":
            # PF4 (PF4.14): delta is the matched-pair difference (n01 - n10) / pairs. Every run of
            # this pair is matched, so n01 - n10 is events_b - events_a and the value is 0.0.1's
            # horizon difference up to floating-point order.
            assert got["pairs"] == got["n_a"] == got["n_b"], (*where, got["pairs"])
            assert abs(got[field] - (got["events_b"] - got["events_a"]) / got["pairs"]) < 1e-12, (*where, field)
            assert abs(got[field] - want[field]) < 1e-12, (*where, field)
        else:
            assert same(got[field], want[field]), (*where, field)


def benjamini_hochberg(p: list[float]) -> list[float]:
    """BH-adjusted q-values, computed here: q_(i) = min over j >= i of m * p_(j) / j, capped at 1."""
    order = sorted(range(len(p)), key=lambda i: p[i])
    q = [0.0] * len(p)
    running = 1.0
    for rank in range(len(p), 0, -1):
        i = order[rank - 1]
        running = min(running, len(p) * p[i] / rank)
        q[i] = running
    return q


def assert_same_tree(got: dict[str, Any], want: dict[str, Any]) -> None:
    for field in ROOT_FIELDS:
        if field in TREE_FIELDS_PF4_MOVES:
            continue
        assert got["root"][field] == want["root"][field], field
    # PF4 (PF4.18): the root's p is the min-p over its statistics on one scale, which is never
    # below the smallest of their own p-values; whether it rejects is 0.0.1's (above).
    root = got["root"]
    assert min([*root["p_location"].values(), *root["p_dispersion"].values()]) <= root["p_omnibus"] <= 1.0, root
    assert got["fault_lines"]["rejected_groups"] == want["fault_lines"]["rejected_groups"]
    got_groups = {g["label"]: g for g in got["fault_lines"]["groups"]}
    assert sorted(got_groups) == sorted(g["label"] for g in want["fault_lines"]["groups"])
    for group in want["fault_lines"]["groups"]:
        for field in GROUP_FIELDS:
            if field in TREE_FIELDS_PF4_MOVES:
                continue
            assert got_groups[group["label"]][field] == group[field], (group["label"], field)
    # PF4 (PF4.18): each group's p is a min-p on one scale as the root's is, and its q is the
    # Benjamini-Hochberg adjustment of those p-values, computed here.
    labels = sorted(got_groups)
    for label in labels:
        g = got_groups[label]
        assert min([*g["p_location"].values(), *g["p_dispersion"].values()]) <= g["p_group"] <= 1.0, (label, g["p_group"])
    q = benjamini_hochberg([got_groups[label]["p_group"] for label in labels])
    for label, q_value in zip(labels, q, strict=True):
        assert abs(got_groups[label]["q_group"] - q_value) < 1e-12, (label, got_groups[label]["q_group"], q_value)
    for field in BOUND_FIELDS:
        assert got["bound"][field] == want["bound"][field], field


@pytest.mark.parametrize("method", METHODS)
def test_pf0_7_diff_json_on_the_0_0_1_pair_gives_0_0_1s_cells_omnibus_fault_lines_and_bound(method: str) -> None:
    # --json replaces --format json on diff.
    r = run_cli(["--store", str(STORE), "diff", QA, QB, "--method", method, "--json"])
    assert r.code == 0, r
    got, want = json.loads(r.out), recorded(f"diff-{method}.json")
    assert got["method"] == want["method"] == method
    assert sorted(got["by_event"]) == sorted(want["by_event"])
    rows = sum(len(block["cells"]) for block in got["by_event"].values())
    for event, block in want["by_event"].items():
        got_cells = {c["config_hash"]: c for c in got["by_event"][event]["cells"]}
        assert sorted(got_cells) == sorted(c["config_hash"] for c in block["cells"]), event
        for cell in block["cells"]:
            assert_same_cell(got_cells[cell["config_hash"]], cell, method, (event, cell["config_hash"]), rows)
    # PF4 (PF4.18): the omnibus p moves with the tree's root, which it is.
    assert got["omnibus"]["p_omnibus"] == got["tree"]["root"]["p_omnibus"]
    assert_same_tree(got["tree"], want["tree"])


@pytest.mark.parametrize("method", METHODS)
def test_pf0_7_serve_json_on_the_0_0_1_pair_gives_0_0_1s_cells_omnibus_fault_lines_and_bound(method: str) -> None:
    r = run_cli(["--store", str(STORE), "serve", QA, QB, "--event", "timeout", "--event", "violated",
                 "--x", "task_id", "--y", "tool_fail_rate", "--method", method, "--json"])
    assert r.code == 0, r
    got, want = json.loads(r.out), recorded(f"serve-{method}.json")
    got_panels = {p["event"]: p for p in got["panels"]}
    assert sorted(got_panels) == sorted(p["event"] for p in want["panels"])
    rows = sum(len(panel["cells"]) for panel in got["panels"])
    for panel in want["panels"]:
        got_cells = {c["config_hash"]: c for c in got_panels[panel["event"]]["cells"]}
        assert sorted(got_cells) == sorted(c["config_hash"] for c in panel["cells"]), panel["event"]
        for cell in panel["cells"]:
            assert_same_cell(got_cells[cell["config_hash"]], cell, method, (panel["event"], cell["config_hash"]), rows)
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


#: A number as a report prints it: 0.0.1 printed rates in percentage points (``31.0``, ``17pp``) and
#: p and q in ``:g`` form; the command line now prints them under rule 10, so a number is
#: compared by value.
PRINTED_NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?(?:pp)?(?![\w]|\.\d)")


def printed_value(token: str) -> tuple[float, float]:
    """A printed number and half a unit of its last printed digit."""
    text = token.replace(",", "").removesuffix("pp")
    m = re.fullmatch(r"[-+]?\d+(?:\.(\d+))?(?:[eE]([-+]?\d+))?", text)
    assert m, token
    return float(text), 0.5 * 10.0 ** (int(m.group(2) or 0) - len(m.group(1) or ""))


def same_numbers(got: str, want: str) -> bool:
    """``got`` prints ``want``'s numbers in the same order, each equal to 0.0.1's within the coarser
    of the two printed precisions, or to 0.0.1's percentage points read as a fraction."""
    got_tokens, want_tokens = PRINTED_NUMBER.findall(got), PRINTED_NUMBER.findall(want)
    if len(got_tokens) != len(want_tokens):
        return False
    for g_token, w_token in zip(got_tokens, want_tokens, strict=True):
        (g, half_g), (w, half_w) = printed_value(g_token), printed_value(w_token)
        if abs(g - w) > max(half_g, half_w) + 1e-12 and abs(g - w / 100) > max(half_w / 100, half_g) + 1e-12:
            return False
    return True


def same_row(got: str, want: str) -> bool:
    """The same cells: the same numbers in each, and the same words in each cell with no number."""
    got_cells, want_cells = got.strip("|").split(" | "), want.strip("|").split(" | ")
    return len(got_cells) == len(want_cells) and all(
        same_numbers(g, w) and (PRINTED_NUMBER.search(w) is not None or g.strip() == w.strip())
        for g, w in zip(got_cells, want_cells, strict=True)
    )


def mde_cells(markdown: str) -> list[tuple[str, int, tuple[str, ...]]]:
    """Each data row of a table with an MDE column, in order: the row, the column's index and what the
    row is about, ``("group", label)`` on the fault lines or ``("cell", event, task_id, tool_fail_rate)``."""
    lines = markdown.splitlines()
    out: list[tuple[str, int, tuple[str, ...]]] = []
    heading, header = "", None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            heading, header = line[3:], None
        if not line.startswith("|"):
            header = None
            continue
        if set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split(" | ")]
        if i + 1 < len(lines) and lines[i + 1].startswith("|") and set(lines[i + 1]) <= set("|-: "):
            header = cells
            continue
        if header is None:
            continue
        at = [k for k, name in enumerate(header) if "MDE" in name]
        if not at:
            continue
        if heading == "Fault lines":
            out.append((line, at[0], ("group", cells[0])))
        elif header[0] == "cell":
            config = dict(part.split("=", 1) for part in cells[0].split(", "))
            out.append((line, at[0], ("cell", cells[1], config["task_id"], str(float(config["tool_fail_rate"])))))
        elif header[:2] == ["task_id", "tool_fail_rate"]:
            out.append((line, at[0], ("cell", heading.split(":")[0], cells[0], str(float(cells[1])))))
    return out


def limits_of(comparison: dict[str, Any]) -> dict[tuple[str, ...], float | None]:
    """Every limit a report prints, from the same comparison's JSON."""
    out: dict[tuple[str, ...], float | None] = {
        ("group", g["label"]): g["mde"] for g in comparison["tree"]["fault_lines"]["groups"]}
    for event, block in comparison["by_event"].items():
        for c in block["cells"]:
            out[("cell", event, c["config"]["task_id"], str(float(c["config"]["tool_fail_rate"])))] = c["mde"]
    return out


@pytest.mark.parametrize("method", METHODS)
def test_pf0_7_report_on_the_0_0_1_pair_gives_0_0_1s_tables_and_bound(method: str, tmp_path: Path) -> None:
    out = tmp_path / "report"
    r = run_cli(["--store", str(STORE), "report", QA, QB, "--event", "timeout", "--event", "violated",
                 "--x", "task_id", "--y", "tool_fail_rate", "--method", method, "--out", str(out)])
    assert r.code == 0, r
    got = (out / "report.md").read_text(encoding="utf-8")
    want = (RECORDED / f"report-{method}" / "report.md").read_text(encoding="utf-8")
    # PF4 (PF4.3): report.md gains a Shares section, which 0.0.1 did not print; the rows compared
    # are those of every section 0.0.1 had.
    got = got.replace(section(got, "## Shares"), "")
    # PF4 (PF4.20): a 0.0.1 run records no kind, so a row's verdict is the direction word.
    want = re.sub(r"\b(safer|worse)\b", lambda m: DIRECTION_OF[m.group(1)], want)
    # PF4 (PF4.18): a fault-line row's p and q (its last-but-two and last-but-one cells) are the
    # one-scale values, read from the same comparison's JSON; every other cell is 0.0.1's.
    tree = json.loads(run_cli(["--store", str(STORE), "diff", QA, QB, "--method", method, "--json"]).out)["tree"]
    groups = {g["label"]: g for g in tree["fault_lines"]["groups"]}
    fault_rows = set(table_data_rows(section(got, "## Fault lines")))
    assert len(fault_rows) == len(groups), fault_rows
    # report.md's numbers are printed under rule 10 now: each row and
    # the bound carry 0.0.1's numbers by value.
    got_rows, want_rows = table_data_rows(got), table_data_rows(want)
    assert len(got_rows) == len(want_rows)
    # PF4 re-freeze (PF4.22 to PF4.24, PF4.45): every condition's and every group's limit moves (the
    # exact power at the lone-change level; the group's from each cell's own baseline, unconditional),
    # so each printed MDE is read against the JSON of the same comparison (the same events) and left
    # out of the comparison with 0.0.1's row; every other cell is still 0.0.1's.
    same_comparison = json.loads(run_cli(["--store", str(STORE), "diff", QA, QB, "--event", "timeout", "--event", "violated",
                                          "--method", method, "--json"]).out)
    limits, printed_limits = limits_of(same_comparison), mde_cells(got)
    assert {about for _, _, about in printed_limits} == set(limits), printed_limits
    moved = []
    for g, w in zip(got_rows, want_rows, strict=True):
        is_fault_row = g in fault_rows
        if printed_limits and g == printed_limits[0][0]:
            _, at, about = printed_limits.pop(0)
            g_cells, w_cells = g.strip("|").split(" | "), w.strip("|").split(" | ")
            value, token = limits[about], g_cells[at].strip()
            if value is None:
                assert PRINTED_NUMBER.search(token) is None and token.startswith("none"), (g, value)
            else:
                printed, half = printed_value(token)
                assert abs(printed - value) <= half + 1e-12, (g, value)
            g_cells[at], w_cells[at] = " ", " "
            g, w = "|" + " | ".join(g_cells) + "|", "|" + " | ".join(w_cells) + "|"
        if is_fault_row:
            g_cells, w_cells = g.strip("|").split(" | "), w.strip("|").split(" | ")
            group = groups[g_cells[0].strip()]
            for token, value in ((g_cells[-3], group["p_group"]), (g_cells[-2], group["q_group"])):
                printed, half = printed_value(token.strip())
                assert abs(printed - value) <= half + 1e-12, (g, value)
            g, w = " | ".join(g_cells[:-3] + g_cells[-1:]), " | ".join(w_cells[:-3] + w_cells[-1:])
        if not same_row(g, w):
            moved.append((g, w))
    assert moved == [] and printed_limits == []
    assert same_numbers(section(got, "## Bound"), section(want, "## Bound"))


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
        # PF4 (PF4.20): as in PF0.6, the same gate named for an event of unknown kind.
        "check": ["check", QA, QB, "--event", "violated", "--fail-on", "higher"],
        "report": ["report", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(out)],
        "paired": ["paired", "--declaration", str(inputs["declaration"]), "--out", str(out)],
        "serve": ["serve", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--event", "violated", "--json"],
        "inspect": ["inspect", QA, "--event", "violated", "--limit", "3"],
        "runs": ["runs"],
    }[verb]


@pytest.mark.parametrize("verb", STORE_VERBS)
def test_pf0_8_poisson_prove_store_names_the_store_for_every_verb(verb: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set alone, the new variable is the store every verb reads or writes: each exits 0 on a store
    that holds what it needs, and the working folder, which holds no store, stays empty."""
    store = copy_runs(tmp_path / "elsewhere", QA, QB)
    write_paired_store(store)
    inputs = write_inputs(tmp_path / "inputs")
    (inputs["declaration"]).write_text(PAIRED_DECLARATION, encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("POISSON_PROVE_STORE", str(store))
    before = run_ids(store)
    r = run_cli(verb_argv(verb, inputs, tmp_path / "out"))
    assert r.code == 0, r
    assert list(cwd.iterdir()) == []
    if verb == "runs":
        assert QA in r.out and QB in r.out, r.out
    if verb == "sweep":
        assert len(run_ids(store) - before) == 1


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
    assert notes == [STORE_VARIABLE_NOTE], r
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


#: Two runs whose names need cleaning: capitals and spaces (names are slugged: lowercase,
#: spaces and / to -). A run's id is a folder name, so it cannot carry a slash; a slash reaches a
#: run's name only through a name given to it, which PF2 reads, and PF2 freezes that case. The
#: target carries capitals, a space and a slash for the names PF2 computes from it.
SLUG_RUNS = ("Base Line A", "Cand Two B")
SLUG_TARGET = "Team/Agent X"
# PF2: default report folders are named by run names, slugged, so the
# slug check on capitals and spaces uses names given at sweep time that carry them (and differ
# from the ids, so a folder named by id cannot pass).
SLUG_NAMES = ("Before Fix A", "After Fix B")


def write_mock_pair(
    root: Path, run_ids_: tuple[str, str], target_id: str,
    names: tuple[str, str] | tuple[None, None] = (None, None),
) -> Path:
    """The mock agent and its patched form, stored under the two given run ids on shared seeds."""
    from poisson_prove.examples.mock_agent import rollout, rollout_patched
    from poisson_prove.store import EpisodeRecord, RunManifest, Store

    store = Store(root)
    configs = [{"task_id": t, "tool_fail_rate": r} for t in ("search", "refund") for r in (0.3, 0.55)]
    for run_id, agent, name in zip(run_ids_, (rollout, rollout_patched), names, strict=True):
        store.create_run(RunManifest(
            run_id=run_id, target_id=target_id, t_unit="tool_calls", run_salt="pf0-slug-salt",
            axis_types={"task_id": "categorical", "tool_fail_rate": "continuous"}, backend="local", environment={},
            name=name,  # PF2: the name given at sweep time
        ))
        store.append(run_id, [
            EpisodeRecord.from_episode(agent(cfg, 1000 * i + k), run_id=run_id, config=cfg, seed=1000 * i + k, replicate_index=k, wall_time=0.01)
            for i, cfg in enumerate(configs)
            for k in range(20)
        ])
        store.mark_complete(run_id)
    return root


def test_pf0_10_a_pair_reports_into_prove_report_a_vs_b_slugged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = write_mock_pair(tmp_path / "store", SLUG_RUNS, SLUG_TARGET, SLUG_NAMES)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    r = run_cli(["--store", str(store), "report", *SLUG_RUNS, "--event", "violated", "--x", "task_id", "--y", "tool_fail_rate"])
    assert r.code == 0, r
    # PF2: the folder is named by the run names, not the ids, slugged.
    assert [p.name for p in cwd.iterdir()] == ["prove-report-before-fix-a-vs-after-fix-b"]
    assert (cwd / "prove-report-before-fix-a-vs-after-fix-b" / "report.md").is_file()


def test_pf0_10_a_single_run_reports_into_prove_report_run_slugged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = write_mock_pair(tmp_path / "store", SLUG_RUNS, SLUG_TARGET, SLUG_NAMES)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    r = run_cli(["--store", str(store), "report", SLUG_RUNS[0], "--event", "violated", "--x", "task_id", "--y", "tool_fail_rate"])
    assert r.code == 0, r
    # PF2: the folder is named by the run name, not the id, slugged.
    assert [p.name for p in cwd.iterdir()] == ["prove-report-before-fix-a"]
    assert (cwd / "prove-report-before-fix-a" / "report.md").is_file()


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


def formatted_strings(path: Path) -> list[str]:
    """``path``'s f-strings, each with its replacement fields shown as ``{}``."""
    return [
        "".join(part.value if isinstance(part, ast.Constant) else "{}" for part in node.values)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.JoinedStr)
    ]


def test_pf0_11_every_install_hint_in_src_that_names_prove_is_the_quoted_distribution_with_an_extra() -> None:
    """Over plain strings and f-strings alike. Burla's hint names Burla's own pin and waits for the
    ``[burla]`` extra (PF9 moves it)."""
    hints = sorted({
        s
        for path in sorted(SRC.rglob("*.py"))
        for s in (*string_constants(path)[1], *formatted_strings(path))
        if "pip install" in s
    })
    naming_prove = [h for h in hints if "burla==" not in h and "burla=={}" not in h]
    assert naming_prove, hints
    for hint in naming_prove:
        # PF12 (PF12.4): a file in a newer format than this Prove reads is refused with the upgrade,
        # which names the distribution alone.
        if hint == "pip install -U poisson-prove":
            continue
        assert re.search(r'pip install "poisson-prove\[(?:[a-z]+|\{\})\]"', hint), hint


# ---------- PF0.12 an old run's provenance ----------

#: The words each surface gives: the report and the receipt say
#: who wrote an old run; the page gives Prove's version as the run recorded it.
WRITTEN_BY_0_0_1 = "written by proofload 0.0.1"
PAGE_VERSION_0_0_1 = "Prove version: 0.0.1 (as proofload)"


def text_of(page: str) -> str:
    """An HTML document's text with its tags and runs of white space each read as one space."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def test_pf0_12_the_report_and_receipt_of_an_old_pair_say_written_by_proofload_0_0_1(tmp_path: Path) -> None:
    out = tmp_path / "report"
    r = run_cli(["--store", str(STORE), "report", QA, QB, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(out)])
    assert r.code == 0, r
    report = (out / "report.md").read_text(encoding="utf-8")
    assert WRITTEN_BY_0_0_1 in report and "proofload version:" not in report, report[-1500:]
    receipt = text_of((out / "receipt.html").read_text(encoding="utf-8"))
    assert WRITTEN_BY_0_0_1 in receipt and "proofload version:" not in receipt


def test_pf0_12_the_report_and_receipt_of_a_new_pair_give_prove_version_and_never_name_proofload(new_pair: tuple[Path, str, str], tmp_path: Path) -> None:
    import poisson_prove

    store, a, b = new_pair
    out = tmp_path / "report"
    r = run_cli(["--store", str(store), "report", a, b, "--x", "task_id", "--y", "tool_fail_rate", "--out", str(out)])
    assert r.code == 0, r
    report = (out / "report.md").read_text(encoding="utf-8")
    receipt = (out / "receipt.html").read_text(encoding="utf-8")
    assert f"Prove version: {poisson_prove.__version__}" in report
    assert f"Prove version: {poisson_prove.__version__}" in text_of(receipt)
    for name, text in (("report.md", report), ("receipt.html", receipt)):
        assert "proofload" not in text.lower(), name


def served_page(store: Path, a: str, b: str) -> str:
    """The page ``serve`` holds for ``a`` against ``b``, fetched once over loopback. The address is
    taken from the first stdout line that carries one, whatever comes before it."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "poisson_prove", "--store", str(store), "serve", a, b, "--x", "task_id", "--y", "tool_fail_rate",
         "--event", "violated"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=clean_env(),
    )
    try:
        assert proc.stdout is not None and proc.stderr is not None
        seen: list[str] = []
        url = None
        while url is None and len(seen) < 200:
            line = proc.stdout.readline()
            if not line:
                proc.wait(timeout=60)
                raise AssertionError(f"serve ended before printing its address: {seen!r} {proc.stderr.read()!r}")
            seen.append(line)
            url = re.search(r"http://127\.0\.0\.1:\d+/", line)
        assert url is not None, seen
        with urllib.request.urlopen(url.group(0), timeout=60) as response:
            return str(response.read().decode("utf-8"))
    finally:
        proc.terminate()
        proc.wait(timeout=60)


def test_pf0_12_the_page_of_an_old_pair_gives_prove_version_0_0_1_as_proofload() -> None:
    page = text_of(served_page(STORE, QA, QB))
    assert PAGE_VERSION_0_0_1 in page and "proofload version:" not in page


def test_pf0_12_the_page_of_a_new_pair_gives_prove_version_and_never_names_proofload(new_pair: tuple[Path, str, str]) -> None:
    import poisson_prove

    store, a, b = new_pair
    page = served_page(store, a, b)
    assert f"Prove version: {poisson_prove.__version__}" in text_of(page)
    assert "proofload" not in page.lower()
