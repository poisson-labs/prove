"""M11a -- the injection seam, the keying and the carrier: the frozen tests for M11a-1 to M11a-33.

Written for the injection adapter (D1
reversed: no ``agentchaos-sdk`` dependency, the hook and the applier are M11's own, the fault
vocabulary is copied under MIT with attribution), against ``7b61bf5``. The code adds
``src/poisson_prove/chaos.py``, ``src/poisson_prove/chaos_catalog.py``, ``NOTICE``, the ``[chaos]``
table in ``sampler.py``, ``chaos_call`` on ``executor._call_in_process``, ``chaos`` on
``executor_modal.worker_batch``, ``environment["chaos"]`` and ``backend_meta["chaos"]`` against
this file and does not edit it. ``poisson_prove.chaos`` and ``poisson_prove.chaos_catalog`` are
imported **inside** test bodies and inside the forked children only, so this file collects on
the bare tree and its own tests fail there.

**Isolation.** ``chaos.install()`` is once per process and memoized, and it
patches ``httpx.Client.send`` and ``httpx.AsyncClient.send`` for the life of the process. Every
test that installs therefore runs in a child forked from the pytest process (``isolated``, the
M3 capture frozen tests' shape) and reads JSON-native results back through a pipe; the pytest process
never installs, so the in-process tests can assert the two ``send`` objects were left alone.
Only ``_variate``, ``_content_seed``, ``position()``'s refusal, the dataclass shapes and the
static scans run in-process.

**Fixtures, and what each cannot express**:

- ``ScriptedTransport`` -- an ``httpx.MockTransport`` handler returning one fixed chat
  completion whose body carries **both** ``content`` and ``tool_calls`` (so every catalogue
  path resolves), non-ASCII content (so ``mojibake`` corruption changes it), and string-valued
  JSON tool arguments (so ``truncate`` and ``corrupt`` on ``function.arguments`` change them).
  It records every request it saw and every response object it made, which is what the
  identity and "never rewritten" clauses read. A second body, ``plain``, carries no
  ``tool_calls`` and is the D16 fixture for an unresolvable path; a third, ``empty``, carries
  ``content == ""`` so ``llm_empty_single`` resolves and changes nothing, D16's other half. It cannot express a real provider: no streaming chunk
  boundaries, no rate limiter, no connection reset; the streaming clause is asserted as "the
  request body's ``stream`` was never rewritten", never as "the stream behaved".
- ``chaos_rollout`` / ``chaos_otel_rollout`` -- the two-step keyless target, **in this file
  rather than under ``examples/``** so that the build cannot shape the fixture the frozen tests are
  read against. Each drives a real ``openai.OpenAI`` over the scripted transport at two declared
  positions (``plan``, ``solve``) and reports ``fell`` when anything it received differs from
  the script. Nothing it does is a source of a published number.
- The shipped mock agent makes no HTTP call and is not a fixture here; nothing that needs a
  key is run.

**Conventions these frozen tests fix where the design is silent. The code follows these.**

- ``poisson_prove.chaos_catalog.CATALOG`` is the one name the frozen tests read from the catalogue
  module: a mapping from fault name to the entries of that scenario, in order. A single-fault
  name may hold one entry or a one-tuple; a compound name holds a tuple. ``fault_names()`` and
  ``install()`` read it at call time, so the D19(b) test can reach the ``error`` action -- which
  no shipped entry uses -- by extending the mapping in a forked child.
- The hooks read the ``ChaosSpec`` of the enclosing ``injecting(spec, seed)`` block: which
  fault, which rate, which steps. ``install(spec)`` validates the name and decides whether hooks
  exist at all (the ``none`` arm installs none); a process that installed a real fault may run
  ``injecting()`` blocks under any name in ``fault_names()``.
- ``worker_batch``'s keyword-only ``chaos`` dict carries the three ``ChaosSpec`` fields as
  JSON-native values (``steps`` a list); ``backend_meta["chaos"]`` and ``environment["chaos"]``
  are the same six-key record.
- ``FaultRecord.position`` is rendered exactly as the span attribute is, ``f"{step}:{attempt}"``;
  the record is a dataclass and ``dataclasses.asdict`` is how the children ship it.
- On the ``none`` arm ``environment["chaos"]["hooks"]`` is ``[]`` and ``engine_version`` is
  ``None`` ("installs no hook"); on a faulted arm ``hooks == ["sync", "async"]``.
  The ``engine_version`` literal is not pinned (the design gives it only as an example).
- ``delay`` entries are pinned with ``target_path`` ``"$"`` or ``None`` and their millisecond
  ``value``; whether the hook sleeps is not pinned, only ``FaultRecord.delay_ms``.

**Where the frozen tests pin something narrower than the invariant's sentence, measured:**

- M11a-5 says the refused episode leaves ``store.manifest(run_id)`` raising ``StoreError``.
  ``run_local`` writes the manifest at ``executor.py:806`` before the first episode runs, and a
  D16 refusal is decided per call, inside the episode; so the frozen test pins what can hold --
  ``run_local`` raises ``ChaosError`` naming the path, the run holds no episode row and is never
  marked complete -- and leaves whether the run directory is removed open.
- M11a-25 and M11a-26 say every applied fault changes the body. ``compound_slow_response`` is
  the one delay-only scenario in the vocabulary and cannot change a body; for it the frozen test
  pins ``FaultRecord.delay_ms == 5000`` on the applied record instead.
- M11a-29 says ``corrupt`` differs across seeds. ``llm_corrupt_single`` is ``mojibake``, which
  is defined as ``orig.encode("utf-8").decode("latin-1")`` -- deterministic -- so only
  ``tool_corrupt_single`` (``unicode`` mode) is asserted to differ; ``llm_corrupt_single`` is
  asserted identical, with the reason.

**Cells.** These frozen tests do not span two cells. The previous revision's M11a-5
asserted ``install()`` raises when the ``chaos`` extra is absent, and that extra no longer
exists under D1; the only environment-shaped claim left is D1's "no new dependency at any
tier", which ``test_m11a_23b`` asserts by blocking ``httpx``, ``openai`` and ``opentelemetry``
in a subprocess and importing the seam -- a simulated core cell, not a second venv. Without
``openai`` this whole file skips at module level and asserts nothing, deliberately: the seam
cannot be observed without an HTTP client. One cell: the repo venv's closure (pandas 2.3.3,
openai 1.109.1, httpx 0.28.1); every test id is asserted in it once.

**Three guards the tree already holds, which a ``chaos.py`` that imports ``httpx`` cannot
satisfy and the code works around.** Under D1 ``chaos.py`` is core, and
``test_s0_scaffold.py::test_no_network_imports_in_core`` and
``test_m13_viewer.py::test_v14_no_core_module_imports_a_network_client_by_dotted_path`` ban
any ``import httpx`` in ``src/poisson_prove`` at any nesting level (an AST walk, not a substring);
``test_m12_trace.py::test_t17_no_module_outside_trace_py_reads_the_span_clock`` bans
``time.time_ns()`` outside ``trace.py``, and ``FaultRecord`` carries ``start_ns``/``end_ns``.
Measured on these frozen tests' shadow shim: a shim that imported ``httpx`` inside ``install()`` and
read ``time.time_ns()`` turned all three red on the whole suite; one that reaches the client
through ``sys.modules["httpx"]`` (the client the target already loaded) and reads
``trace._span_clock()`` passes all three and this file. A faulted arm whose process has not
loaded ``httpx`` by ``install()`` has no LLM client to inject into and is refused with
``ChaosError`` before the manifest exists (M11a-33); the
``none`` arm still installs.

**The classified red set, measured on this commit.** Pristine
``git clone`` of ``7b61bf5`` at a UUID-free path, venv built from the repo venv's ``pip
freeze`` with ``--no-deps``, collection 1846 = the repo's 1846; the copy lacks the gitignored
downloaded data file so it skips 5 where the repo skips 3.
Bare-tree baseline: **4 failed / 1837 passed / 5 skipped** -- the four are A22's own
classified reds on pandas 2.3.3 (``test_a22_pandas3.py`` V5, V12, V14, V15), whose build has
not landed. With this file and the amendments below, 1887 collected: **48 failed / 1834 passed
/ 5 skipped**, and nothing outside the following is red.

- ``tests/test_m11a_chaos.py``: all 41, because ``poisson_prove.chaos`` and
  ``poisson_prove.chaos_catalog`` do not exist -- 11 as ``ModuleNotFoundError`` in the test body,
  21 as the same error reported by a forked child (``Failed: isolated child_* failed``), one as
  the same error in a subprocess (M11a-33), and 8 by the assertion the missing build leaves unmet (``SamplerError`` not raised, the signatures
  still four-wide, no ``chaos`` key on the manifest, no ``NOTICE``, the literal counted zero
  times, the paired run's outcomes ``None``).
- ``tests/test_m3_crash_trace.py::test_k8_the_transport_aliases_and_signatures_are_untouched``,
  ``tests/test_m3_timeout_trace.py::test_e12_the_transport_aliases_and_episode_are_untouched``,
  ``tests/test_m3_capture.py::test_c8_worker_batch_keeps_three_positional_parameters_and_adds_only_capture``:
  the four amended assertions (``chaos`` on ``worker_batch``,
  ``chaos_call`` on ``_call_in_process``), one test id each.
- ``tests/test_a22_pandas3.py`` V5, V12, V14, V15: A22's, present on the bare tree, not this
  file's.

**A fifth frozen site, not listed before.** ``test_m3_crash_trace.py:111``
``S16_ORACLE_SHA256`` is a byte digest of ``test_m3_timeout_trace.py``; amending E12 moves it,
so this commit re-mints that literal off the amended file (``256298e6...``) and
``test_k8_the_s16_oracle_is_byte_identical`` is green before and after.

**Green-before-and-after clauses, named so their green is not read as evidence:**
``"chaos" not in SweepSpec.load(...).to_dict()`` (M11a-2), a run without a ``[chaos]`` table
carrying no ``environment["chaos"]`` (M11a-21) and no ``backend_meta["chaos"]`` (M11a-22),
neither fault key in ``trace._LIFTED_KEYS`` (M11a-15), ``agentchaos`` absent from
``pyproject.toml`` and the extras set exact (M11a-23). Each sits inside a test whose other
clauses are red on the bare tree, so no test id is green by construction.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import copy
import dataclasses
import hashlib
import importlib
import inspect
import json
import multiprocessing
import os
import subprocess
import sys
import time
import tomllib
import traceback
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import poisson_prove
import poisson_prove.executor as executor
import poisson_prove.trace as trace_module
from poisson_prove.diff import diff
from poisson_prove.episode import Episode
from poisson_prove.executor import derive_seed, plan, run_local
from poisson_prove.executor_modal import Job, ModalOptions, run_with_mapper, worker_batch
from poisson_prove.sampler import SamplerError, SweepSpec
from poisson_prove.store import Store, StoreError
from poisson_prove.survival import censor
from poisson_prove.trace import Trace

openai = pytest.importorskip("openai", reason="the injection oracle drives the openai SDK over a scripted transport")

MODULE = __name__
PACKAGE = Path(poisson_prove.__file__).resolve().parent  # the tree under test; a shadow tree under PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
CHAOS_MODULE = "poisson_prove.chaos"
CATALOG_MODULE = "poisson_prove.chaos_catalog"
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()

PUBLIC_SURFACE = ["ChaosError", "ChaosSpec", "ChaosStatus", "FaultRecord", "fault_names", "injecting", "install", "position"]
SPEC_FIELDS = ("fault", "rate", "steps")
STATUS_FIELDS = ("requested", "fault", "rate", "steps", "engine_version")
RECORD_FIELDS = (
    "call_index", "position", "fault", "applied", "start_ns", "end_ns", "model",
    "request_messages", "request_tools", "response", "delay_ms",
)
ENTRY_FIELDS = ("name", "intercept", "action", "target_path", "value")
MANIFEST_KEYS = frozenset({"requested", "fault", "rate", "steps", "engine_version", "hooks"})
# PF9: the [burla] extra joins the set. PF7: the [viz] extra goes.
EXTRAS = {"modal", "agent", "all", "dev", "burla"}
FAULT_KEY = "poisson_prove.fault"
FAULT_POSITION_KEY = "poisson_prove.fault.position"
ATTRIBUTION = ("AgentChaos", "github.com/floritange/AgentChaos", "MIT", "0.1.0")
SPLIT_FAMILY = ("split", "rsplit", "partition", "rpartition")

CONTENT_PATH = "$.choices[0].message.content"
TOOL_CALLS_PATH = "$.choices[0].message.tool_calls"
FIRST_CALL_PATH = "$.choices[0].message.tool_calls[0]"
ARGUMENTS_PATH = "$.choices[0].message.tool_calls[0].function.arguments"
FINISH_PATH = "$.choices[0].finish_reason"
API_ERROR_TEMPLATE = "[API ERROR] HTTP {code}: AgentFault injected server error."
DROP_CONTENT = "[TIMEOUT] Connection dropped. The server did not respond."

#: The vocabulary, transcribed from ``agentchaos/fault_config.py:19``-``:284`` of the installed
#: 0.1.0 wheel: name -> ((intercept, action, target_path, value), ...). The twelve ``*_single``
#: names and the eight compound scenarios minus ``compound_stale_cache``.
#: ``delay`` entries carry their FaultSpec default path ``"$"``; ``drop`` carries no value.
VOCABULARY: dict[str, tuple[tuple[str, str, str | None, Any], ...]] = {
    "llm_error_single": (("response", "set", CONTENT_PATH, "[API ERROR] HTTP 500: Internal Server Error. The server encountered an unexpected condition."),),
    "llm_timeout_single": (("response", "set", CONTENT_PATH, "[TIMEOUT] The request timed out. The server did not respond within the expected time."),),
    "llm_empty_single": (("response", "set", CONTENT_PATH, ""),),
    "llm_truncate_single": (("response", "truncate", CONTENT_PATH, 0.3),),
    "llm_corrupt_single": (("response", "corrupt", CONTENT_PATH, "mojibake"),),
    "llm_schema_single": (("response", "set", CONTENT_PATH, '{"error": "content_policy_violation", "message": "This response has been filtered."}'),),
    "tool_error_single": (("response", "set", ARGUMENTS_PATH, "{}"),),
    "tool_timeout_single": (("response", "drop", FIRST_CALL_PATH, None),),
    "tool_empty_single": (("response", "set", TOOL_CALLS_PATH, []),),
    "tool_truncate_single": (("response", "truncate", ARGUMENTS_PATH, 0.3),),
    "tool_corrupt_single": (("response", "corrupt", ARGUMENTS_PATH, "unicode"),),
    "tool_schema_single": (("response", "set", ARGUMENTS_PATH, '{"wrong_param": "unexpected_value"}'),),
    "compound_api_degradation": (
        ("response", "delay", "$", 3000),
        ("response", "set", CONTENT_PATH, "[SERVICE UNAVAILABLE] HTTP 503: The server is temporarily unable to handle the request."),
    ),
    "compound_content_filter": (
        ("response", "set", TOOL_CALLS_PATH, []),
        ("response", "set", CONTENT_PATH, "[CONTENT FILTERED] This response has been blocked by the content safety filter."),
        ("response", "set", FINISH_PATH, "content_filter"),
    ),
    "compound_max_tokens": (
        ("response", "truncate", CONTENT_PATH, 0.5),
        ("response", "set", FINISH_PATH, "length"),
    ),
    "compound_proxy_html": (
        ("response", "set", CONTENT_PATH, "<!DOCTYPE html>\n<html><head><title>502 Bad Gateway</title></head>\n<body><center><h1>502 Bad Gateway</h1></center><hr><center>nginx/1.24.0</center></body></html>"),
    ),
    "compound_stale_data": (("response", "set", ARGUMENTS_PATH, '{"city": "Pyongyang"}'),),
    "compound_wrong_entity": (("response", "set", ARGUMENTS_PATH, '{"city": "Springfield"}'),),
    "compound_slow_response": (("response", "delay", "$", 5000),),
}
FAULT_NAMES = frozenset(VOCABULARY) | {"none"}
DELAY_ONLY = {"compound_slow_response": 5000.0}
SEEDED_NAMES = {"tool_corrupt_single"}  # the one ``unicode``-mode corrupt; ``mojibake`` is deterministic
INSTALL_FAULT = "llm_error_single"

# ---------- the scripted wire ----------

BASE_URL = "http://oracle.invalid/v1"
CHAT_PATH = "/chat/completions"
OTHER_PATH = "/embeddings"
MODEL = "oracle-model"
MESSAGES = [{"role": "user", "content": "solve the task"}]
TOOLS = [{"type": "function", "function": {"name": "run_tests", "parameters": {"type": "object", "properties": {}}}}]
CONTENT = "Voilà: the café résumé is naïve — jalapeño über straße, done."  # non-ASCII, 61 chars
ARGUMENTS = '{"code": "print(\\"solved\\")", "path": "solution.py"}'
RESPONSE_HEADERS = {"x-request-id": "req-oracle-1", "x-ratelimit-remaining-requests": "99", "openai-processing-ms": "12"}
COMPLETION: dict[str, Any] = {
    "id": "chatcmpl-oracle",
    "object": "chat.completion",
    "created": 1,
    "model": MODEL,
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": CONTENT,
                "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "run_tests", "arguments": ARGUMENTS}}],
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
}
COMPLETION_PLAIN: dict[str, Any] = {
    **COMPLETION,
    "choices": [{"index": 0, "message": {"role": "assistant", "content": CONTENT}, "finish_reason": "stop"}],
}
EMBEDDING: dict[str, Any] = {
    "object": "list",
    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
    "model": "oracle-embed",
    "usage": {"prompt_tokens": 1, "total_tokens": 1},
}
COMPLETION_EMPTY: dict[str, Any] = {
    **COMPLETION,
    "choices": [{**COMPLETION["choices"][0], "message": {**COMPLETION["choices"][0]["message"], "content": ""}}],
}
BODIES: dict[str, dict[str, Any]] = {"tools": COMPLETION, "plain": COMPLETION_PLAIN, "empty": COMPLETION_EMPTY}
HORIZON = 10.0
STEPS = ("plan", "solve")
SALT = "m11a-oracle-salt"
TARGET_ID = "chaos-oracle@v0"
POSITION = ("plan", 1)
MIXED_SEED = 7
MIXED_POSITIONS = [
    ("plan", 1), ("plan", 2), ("solve", 1), ("solve", 2), ("solve", 3), ("verify", 1),
    ("verify", 2), ("submit", 1), ("a:b", 1), ("retry", 1), ("retry", 2), ("retry", 3),
]


def _request(stream: bool = False) -> dict[str, Any]:
    return {"model": MODEL, "messages": MESSAGES, "tools": TOOLS, "stream": stream}


class ScriptedTransport:
    """The handler behind ``httpx.MockTransport``: one scripted body, every request and every
    response object remembered."""

    def __init__(self, body_key: str = "tools", status: int = 200) -> None:
        self.body_key = body_key
        self.status = status
        self.seen: list[dict[str, Any]] = []
        self.made: list[httpx.Response] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content) if request.content else None
        self.seen.append({"url": str(request.url), "body": payload})
        body = BODIES[self.body_key] if CHAT_PATH in str(request.url) else EMBEDDING
        response = httpx.Response(self.status, json=body, headers=dict(RESPONSE_HEADERS))
        self.made.append(response)
        return response


def _sync_client(transport: ScriptedTransport) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(transport), base_url=BASE_URL)


def _openai(client: httpx.Client) -> Any:
    return openai.OpenAI(api_key="oracle", base_url=BASE_URL, max_retries=0, http_client=client)


# ---------- reference constants ----------


def reference_variate(seed: int, step_name: str, attempt: int) -> float:
    digest = hashlib.sha256(f"{seed}:{step_name}:{attempt}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def reference_content_seed(seed: int, step_name: str, attempt: int, fault: str) -> int:
    digest = hashlib.sha256(f"{seed}:{step_name}:{attempt}:{fault}".encode()).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def reference_fired(seed: int, positions: Sequence[tuple[str, int]], rate: float) -> set[tuple[str, int]]:
    return {p for p in positions if reference_variate(seed, *p) < rate}


# ---------- helpers: JSON-native shipping, sweep files, jobs ----------


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def _exc_dict(exc: BaseException) -> dict[str, Any]:
    chain: list[str] = []
    messages: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(chain) < 8:
        chain.append(type(current).__name__)
        messages.append(str(current))
        current = current.__cause__ or current.__context__
    return {"type": type(exc).__name__, "message": str(exc), "chain": chain, "messages": messages}


def _records(records: Any) -> list[dict[str, Any]]:
    return [] if records is None else [_jsonable(r) for r in records]


def _kw(spec_kwargs: dict[str, Any] | None) -> dict[str, Any]:
    kwargs = dict(spec_kwargs or {})
    if "steps" in kwargs:
        kwargs["steps"] = tuple(kwargs["steps"])
    return kwargs


def _json_or_none(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def sweep_toml(
    *,
    chaos: dict[str, Any] | None,
    capture: dict[str, Any] | None = None,
    replicates: int = 2,
    bodies: Sequence[str] = ("tools",),
    target_id: str = TARGET_ID,
    t_unit: str = "steps",
) -> str:
    """A sweep file; ``chaos`` is the ``[chaos]`` table, or absent."""
    lines = [f'target_id = "{target_id}"', f't_unit = "{t_unit}"', f"replicates = {replicates}", ""]
    lines += ["[axes.body]", 'type = "categorical"', f"values = {json.dumps(list(bodies))}", ""]
    if capture is not None:
        # CD (D1): a [capture] table declares its cap; 8192 is what the dataclass used to supply.
        if "max_observation_bytes" not in capture and "max_span_bytes" not in capture:
            capture = {**capture, "max_observation_bytes": 8192}
        lines.append("[capture]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in capture.items()]
        lines.append("")
    if chaos is not None:
        lines.append("[chaos]")
        lines += [f"{key} = {json.dumps(value)}" for key, value in chaos.items()]
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def jobs_of(p: Any) -> list[Job]:
    return [(dict(pair.config), pair.seed, i, pair.config_hash, pair.replicate_index) for i, pair in enumerate(p.pairs)]


def _resolve(import_path: str) -> Any:
    module_name, attr = import_path.split(":", 1)
    return getattr(importlib.import_module(module_name), attr)


def _string_constants(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _docstring_span(path: Path) -> tuple[int, int]:
    """The 1-based line range of the module docstring, or (0, 0) when there is none."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        node = tree.body[0]
        return node.lineno, node.end_lineno or node.lineno
    return 0, 0


def _entries(value: Any) -> tuple[Any, ...]:
    return (value,) if dataclasses.is_dataclass(value) else tuple(value)


def _norm(value: Any) -> Any:
    return list(value) if isinstance(value, (list, tuple)) else value


# ---------- module-level rollouts (addressed by import path from the children) ----------


def _client_for(cfg: dict[str, Any]) -> Any:
    transport = ScriptedTransport(str(cfg.get("body", "tools")))
    return _openai(_sync_client(transport))


def _episode(cfg: dict[str, Any], observed: list[dict[str, Any]]) -> Episode:
    expected_arguments = ARGUMENTS if cfg.get("body", "tools") == "tools" else None
    injected = any(
        o["content"] != CONTENT or o["finish"] != "stop" or o["arguments"] != expected_arguments for o in observed
    )
    return Episode(
        outcome="fell" if injected else "survived",
        t=1.0 if injected else HORIZON,
        horizon=HORIZON,
        meta={"observed": observed},
    )


def _observe(completion: Any) -> dict[str, Any]:
    choice = completion.choices[0]
    calls = choice.message.tool_calls
    return {
        "content": choice.message.content,
        "finish": choice.finish_reason,
        "arguments": calls[0].function.arguments if calls else None,
    }


def chaos_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    """Two declared positions, one chat completion each, over the scripted transport."""
    chaos = importlib.import_module(CHAOS_MODULE)
    client = _client_for(cfg)
    observed = []
    for name in STEPS:
        with chaos.position(name, 1):
            completion = client.chat.completions.create(model=MODEL, messages=MESSAGES, tools=TOOLS)
        observed.append(_observe(completion))
    return _episode(cfg, observed)


def chaos_otel_rollout(cfg: dict[str, Any], seed: int) -> Episode:
    """The same target with each call inside a span of its own, opened through the OTel API."""
    from opentelemetry import trace as otel_trace

    chaos = importlib.import_module(CHAOS_MODULE)
    tracer = otel_trace.get_tracer("oracle.chaos", "0.1.0")
    client = _client_for(cfg)
    observed = []
    for name in STEPS:
        with chaos.position(name, 1), tracer.start_as_current_span(f"chat {name}"):
            completion = client.chat.completions.create(model=MODEL, messages=MESSAGES, tools=TOOLS)
        observed.append(_observe(completion))
    return _episode(cfg, observed)


# ---------- the children: everything that installs runs here ----------


def _child_entry(conn: Any, fn: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        outcome: tuple[str, Any] = ("ok", fn(*args))
    except BaseException:  # noqa: BLE001 - the child must always report
        outcome = ("error", traceback.format_exc())
    try:
        conn.send(outcome)
    finally:
        conn.close()


def isolated(fn: Callable[..., Any], *args: Any, timeout: float = 240.0) -> Any:
    """Run ``fn(*args)`` in a child process and return its result (the M3 capture frozen tests' shape)."""
    ctx = multiprocessing.get_context("fork" if FORK_AVAILABLE else "spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_child_entry, args=(child_conn, fn, args))
    proc.start()
    child_conn.close()
    deadline = time.perf_counter() + timeout
    outcome: tuple[str, Any] | None = None
    try:
        while outcome is None:
            if parent_conn.poll(0.05):
                outcome = parent_conn.recv()
            elif not proc.is_alive():
                outcome = ("error", f"child exited with code {proc.exitcode} before reporting")
            elif time.perf_counter() > deadline:
                outcome = ("error", f"child produced nothing within {timeout}s")
    finally:
        parent_conn.close()
        if proc.is_alive():
            proc.terminate()
        proc.join(10.0)
    kind, payload = outcome
    if kind != "ok":
        pytest.fail(f"isolated {fn.__name__} failed:\n{payload}")
    return payload


def _send(call: dict[str, Any], transport: ScriptedTransport, sync_client: httpx.Client, oai: Any) -> httpx.Response | None:
    via = call.get("via", "httpx")
    path = call.get("path", CHAT_PATH)
    stream = bool(call.get("stream", False))
    body = _request(stream) if path == CHAT_PATH else {"model": "oracle-embed", "input": "x"}
    if via == "httpx":
        return sync_client.post(path, json=body)
    if via == "httpx-async":

        async def go_httpx() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport), base_url=BASE_URL) as ac:
                return await ac.post(path, json=body)

        return asyncio.run(go_httpx())
    if via == "openai":
        if stream:
            oai.chat.completions.create(model=MODEL, messages=MESSAGES, tools=TOOLS, stream=True)
            return None
        return oai.chat.completions.with_raw_response.create(model=MODEL, messages=MESSAGES, tools=TOOLS).http_response
    if via == "openai-async":

        async def go_openai() -> httpx.Response:
            async with httpx.AsyncClient(transport=httpx.MockTransport(transport), base_url=BASE_URL) as ac:
                aoai = openai.AsyncOpenAI(api_key="oracle", base_url=BASE_URL, max_retries=0, http_client=ac)
                raw = await aoai.chat.completions.with_raw_response.create(model=MODEL, messages=MESSAGES, tools=TOOLS)
                return raw.http_response

        return asyncio.run(go_openai())
    raise ValueError(via)


def _perform(chaos: Any, call: dict[str, Any], transport: ScriptedTransport, sync_client: httpx.Client, oai: Any) -> dict[str, Any]:
    position = call.get("position")
    before = len(transport.made)
    out: dict[str, Any] = {"error": None, "status": None, "headers": None, "json": None, "identity": None, "returned": None}
    cm = chaos.position(position[0], position[1]) if position is not None else contextlib.nullcontext()
    try:
        with cm:
            response = _send(call, transport, sync_client, oai)
    except Exception as exc:  # noqa: BLE001 - shipped to the parent, which decides
        out["error"] = _exc_dict(exc)
    else:
        if response is None:
            out["returned"] = "stream"
        else:
            out.update(
                status=response.status_code,
                headers=dict(response.headers),
                json=_json_or_none(response),
                identity=len(transport.made) > before and response is transport.made[-1],
            )
    out["reached_transport"] = len(transport.made) > before
    out["transport_json"] = transport.made[-1].json() if len(transport.made) > before else None
    return out


def child_episode(
    spec_kwargs: dict[str, Any],
    seed: int,
    calls: list[dict[str, Any]],
    body_key: str = "tools",
    install_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """``install()``, then one ``injecting(spec, seed)`` block performing ``calls`` in order."""
    chaos = importlib.import_module(CHAOS_MODULE)
    transport = ScriptedTransport(body_key)
    status = chaos.install(chaos.ChaosSpec(**_kw(spec_kwargs if install_kwargs is None else install_kwargs)))
    sync_client = _sync_client(transport)
    oai = _openai(sync_client)
    observed: list[dict[str, Any]] = []
    records_ref: Any = None
    block_error: dict[str, Any] | None = None
    try:
        with chaos.injecting(chaos.ChaosSpec(**_kw(spec_kwargs)), seed) as records:
            records_ref = records
            for call in calls:
                observed.append(_perform(chaos, call, transport, sync_client, oai))
    except Exception as exc:  # noqa: BLE001 - shipped to the parent, which decides
        block_error = _exc_dict(exc)
    return {
        "status": _jsonable(status),
        "records": _records(records_ref),
        "observed": observed,
        "seen": transport.seen,
        "block_error": block_error,
        "fault_names": list(chaos.fault_names()),
    }


def child_vocabulary(names: list[str], seed: int, extra_before: int = 0, body_key: str = "tools") -> dict[str, Any]:
    """One ``injecting()`` block per name; a sync and an async ``httpx`` call at ``POSITION``."""
    chaos = importlib.import_module(CHAOS_MODULE)
    transport = ScriptedTransport(body_key)
    chaos.install(chaos.ChaosSpec(fault=INSTALL_FAULT))
    pristine = copy.deepcopy(BODIES[body_key])
    sync_client = _sync_client(transport)
    by_name: dict[str, dict[str, Any]] = {}
    for name in names:
        per: dict[str, Any] = {}
        with chaos.injecting(chaos.ChaosSpec(fault=name), seed) as records:
            for _ in range(extra_before):
                sync_client.post(CHAT_PATH, json=_request())
            for via in ("httpx", "httpx-async"):
                per[via] = _perform(chaos, {"via": via, "position": list(POSITION)}, transport, sync_client, None)
        per["records"] = _records(records)
        by_name[name] = per
    return {
        "by_name": by_name,
        "scripted_unmutated": BODIES[body_key] == pristine,
        "fault_names": list(chaos.fault_names()),
    }


def child_none_arm() -> dict[str, Any]:
    chaos = importlib.import_module(CHAOS_MODULE)
    sync_before, async_before = httpx.Client.send, httpx.AsyncClient.send
    status = chaos.install(chaos.ChaosSpec())
    second = chaos.install(chaos.ChaosSpec())
    transport = ScriptedTransport()
    client = _sync_client(transport)
    with chaos.position("plan", 1):
        response = client.post(CHAT_PATH, json=_request())
    return {
        "status": _jsonable(status),
        "second": _jsonable(second),
        "sync_untouched": httpx.Client.send is sync_before,
        "async_untouched": httpx.AsyncClient.send is async_before,
        "agentchaos_loaded": any(n.split(".")[0] == "agentchaos" for n in sys.modules),
        "identity": response is transport.made[-1],
        "json": response.json(),
    }


def child_unknown_fault() -> dict[str, Any]:
    chaos = importlib.import_module(CHAOS_MODULE)
    sync_before, async_before = httpx.Client.send, httpx.AsyncClient.send
    try:
        chaos.install(chaos.ChaosSpec(fault="not_a_fault"))
    except Exception as exc:  # noqa: BLE001 - shipped to the parent, which decides
        error: dict[str, Any] | None = _exc_dict(exc)
    else:
        error = None
    return {
        "error": error,
        "sync_untouched": httpx.Client.send is sync_before,
        "async_untouched": httpx.AsyncClient.send is async_before,
    }


def child_uninstall() -> dict[str, Any]:
    chaos = importlib.import_module(CHAOS_MODULE)
    sync_before, async_before = httpx.Client.send, httpx.AsyncClient.send
    chaos.install(chaos.ChaosSpec(fault=INSTALL_FAULT))
    patched = (httpx.Client.send is not sync_before, httpx.AsyncClient.send is not async_before)
    chaos._uninstall()
    restored = (httpx.Client.send is sync_before, httpx.AsyncClient.send is async_before)
    transport = ScriptedTransport()
    client = _sync_client(transport)
    with chaos.position("plan", 1):
        response = client.post(CHAT_PATH, json=_request())
    return {
        "patched": list(patched),
        "restored": list(restored),
        "identity": response is transport.made[-1],
        "json": response.json(),
    }


def child_outside_block() -> dict[str, Any]:
    chaos = importlib.import_module(CHAOS_MODULE)
    chaos.install(chaos.ChaosSpec(fault=INSTALL_FAULT))
    transport = ScriptedTransport()
    client = _sync_client(transport)
    with chaos.position("plan", 1):
        before = client.post(CHAT_PATH, json=_request())
    before_identity = before is transport.made[-1]
    with chaos.injecting(chaos.ChaosSpec(fault=INSTALL_FAULT), 1) as records:
        with chaos.position("plan", 1):
            inside = client.post(CHAT_PATH, json=_request())
        inside_identity = inside is transport.made[-1]
        n_inside = len(records)
    with chaos.position("plan", 1):
        after = client.post(CHAT_PATH, json=_request())
    return {
        "before_identity": before_identity,
        "before_json": before.json(),
        "inside_identity": inside_identity,
        "inside_json": inside.json(),
        "after_identity": after is transport.made[-1],
        "after_json": after.json(),
        "n_inside": n_inside,
        "n_after": len(records),
        "records": _records(records),
    }


def child_threads() -> dict[str, Any]:
    chaos = importlib.import_module(CHAOS_MODULE)
    chaos.install(chaos.ChaosSpec(fault=INSTALL_FAULT))
    transport = ScriptedTransport()
    client = _sync_client(transport)

    def call_at(name: str) -> str:
        with chaos.position(name, 1):
            client.post(CHAT_PATH, json=_request())
        return name

    zero_error: dict[str, Any] | None = None
    with chaos.injecting(chaos.ChaosSpec(fault=INSTALL_FAULT), 5) as records:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(call_at, ["alpha", "beta"]))
        n_threaded = len(records)
        with chaos.position("caller", 1), ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(client.post, CHAT_PATH, json=_request()).result()
        try:
            with chaos.position("a", attempt=0):
                pass
        except Exception as exc:  # noqa: BLE001 - shipped to the parent, which decides
            zero_error = _exc_dict(exc)
    return {"records": _records(records), "n_threaded": n_threaded, "zero_error": zero_error}


def child_both_hooks() -> dict[str, Any]:
    chaos = importlib.import_module(CHAOS_MODULE)
    chaos.install(chaos.ChaosSpec(fault=INSTALL_FAULT))
    transport = ScriptedTransport()
    sync_client = _sync_client(transport)
    oai = _openai(sync_client)

    async def go() -> str | None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport), base_url=BASE_URL) as ac:
            aoai = openai.AsyncOpenAI(api_key="oracle", base_url=BASE_URL, max_retries=0, http_client=ac)
            completion = await aoai.chat.completions.create(model=MODEL, messages=MESSAGES, tools=TOOLS)
            return completion.choices[0].message.content

    with chaos.injecting(chaos.ChaosSpec(fault=INSTALL_FAULT), 9) as records:
        with chaos.position("plan", 1):
            sync_content = oai.chat.completions.create(model=MODEL, messages=MESSAGES, tools=TOOLS).choices[0].message.content
            async_content = asyncio.run(go())
    return {"sync_content": sync_content, "async_content": async_content, "records": _records(records)}


def child_error_override(seed: int) -> dict[str, Any]:
    """Reach the ``error`` action, which no shipped entry uses, by extending the catalogue."""
    chaos = importlib.import_module(CHAOS_MODULE)
    catalog = importlib.import_module(CATALOG_MODULE)
    template = catalog.CATALOG["llm_error_single"]
    entry_type = type(_entries(template)[0])
    entry = entry_type(name="oracle_error_tool", intercept="response", action="error", target_path=ARGUMENTS_PATH, value=418)
    extended = dict(catalog.CATALOG)
    extended["oracle_error_tool"] = entry if dataclasses.is_dataclass(template) else (entry,)
    catalog.CATALOG = extended
    listed = "oracle_error_tool" in chaos.fault_names()
    chaos.install(chaos.ChaosSpec(fault="oracle_error_tool"))
    transport = ScriptedTransport()
    client = _sync_client(transport)
    with chaos.injecting(chaos.ChaosSpec(fault="oracle_error_tool"), seed) as records:
        observed = _perform(chaos, {"position": list(POSITION)}, transport, client, None)
    return {"listed": listed, "observed": observed, "records": _records(records)}


def child_run_local(store_root: str, toml_path: str, target: str, salt: str) -> dict[str, Any]:
    store = Store(store_root)
    p: Any = None
    try:
        p = plan(SweepSpec.load(toml_path), store, run_salt=salt, import_path=target)
        summary = run_local(p, _resolve(target), store)
    except Exception as exc:  # noqa: BLE001 - shipped to the parent, which decides
        return {"run_id": None if p is None else p.run_id, "summary": None, "error": _exc_dict(exc)}
    return {"run_id": p.run_id, "summary": dataclasses.asdict(summary), "error": None}


def child_worker_batch(jobs: list[Job], import_path: str, episode_timeout: float | None, chaos: dict[str, Any] | None) -> dict[str, Any]:
    results = worker_batch(jobs, import_path, episode_timeout, chaos=chaos)
    return {"results": _jsonable(results)}


def child_run_with_mapper(store_root: str, toml_path: str, target: str, salt: str) -> dict[str, Any]:
    spec = SweepSpec.load(toml_path)
    store = Store(store_root)
    payload = None if spec.chaos is None else {"fault": spec.chaos.fault, "rate": spec.chaos.rate, "steps": list(spec.chaos.steps)}

    def mapper(batches: Sequence[Sequence[Job]]) -> Iterator[tuple[int, list[Any]]]:
        for index, jobs in enumerate(batches):
            yield index, worker_batch(list(jobs), target, None, chaos=payload)

    p = plan(spec, store, backend="modal", run_salt=salt, import_path=target)
    summary = run_with_mapper(p, mapper, store, options=ModalOptions(batch_size=4))
    return {"run_id": p.run_id, "summary": dataclasses.asdict(summary)}


# ---------- M11a-1, M11a-14 (surface): the dataclasses and the public names ----------


def test_m11a_1_chaosspec_has_the_three_fields_and_the_none_default() -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    assert tuple(f.name for f in dataclasses.fields(chaos.ChaosSpec)) == SPEC_FIELDS
    assert dataclasses.astuple(chaos.ChaosSpec()) == ("none", 1.0, ())
    with pytest.raises(dataclasses.FrozenInstanceError):
        chaos.ChaosSpec().fault = "x"  # type: ignore[misc]


def test_m11a_1b_the_public_surface_is_exactly_section_2s_eight_names() -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    defined = {name for name, obj in vars(chaos).items() if not name.startswith("_") and getattr(obj, "__module__", None) == chaos.__name__}
    assert list(chaos.__all__) == PUBLIC_SURFACE, chaos.__all__
    assert defined == set(PUBLIC_SURFACE), sorted(defined ^ set(PUBLIC_SURFACE))
    assert issubclass(chaos.ChaosError, RuntimeError)
    assert tuple(f.name for f in dataclasses.fields(chaos.ChaosStatus)) == STATUS_FIELDS
    assert tuple(f.name for f in dataclasses.fields(chaos.FaultRecord)) == RECORD_FIELDS
    assert (PACKAGE / "chaos.py").is_file() and (PACKAGE / "chaos_catalog.py").is_file()


# ---------- M11a-2, M11a-3: the [chaos] table ----------


def test_m11a_2_the_chaos_table_refuses_by_field_name_and_stays_out_of_to_dict(tmp_path: Path) -> None:
    for table, field in [
        ({"fault": "llm_error_single", "bogus": 1}, "bogus"),
        ({"fault": "llm_error_single", "rate": 1.5}, "rate"),
        ({"fault": "llm_error_single", "rate": -0.1}, "rate"),
        ({"fault": "llm_error_single", "steps": "solve"}, "steps"),
        ({"fault": ""}, "fault"),
    ]:
        path = write(tmp_path / f"{field}.toml", sweep_toml(chaos=table))
        with pytest.raises(SamplerError) as info:
            SweepSpec.load(path)
        assert field in str(info.value), (table, str(info.value))
    good = SweepSpec.load(write(tmp_path / "good.toml", sweep_toml(chaos={"fault": "llm_error_single", "rate": 0.25, "steps": ["solve"]})))
    assert "chaos" not in good.to_dict()  # green-before-and-after on its own


def test_m11a_3_the_table_changes_no_cell_and_no_seed(tmp_path: Path) -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    with_table = SweepSpec.load(write(tmp_path / "with.toml", sweep_toml(chaos={"fault": "llm_error_single", "rate": 0.25, "steps": ["solve"]}, bodies=("tools", "plain"))))
    without = SweepSpec.load(write(tmp_path / "without.toml", sweep_toml(chaos=None, bodies=("tools", "plain"))))
    assert with_table.chaos == chaos.ChaosSpec(fault="llm_error_single", rate=0.25, steps=("solve",))  # the field exists before it is compared
    assert without.chaos is None
    assert list(with_table.configs) == list(without.configs)
    assert with_table.cells() == without.cells()
    assert [derive_seed("s", h, k) for h in with_table.cells() for k in range(3)] == [derive_seed("s", h, k) for h in without.cells() for k in range(3)]


# ---------- M11a-4, M11a-6: install on the none arm and on an unknown name ----------


def test_m11a_4_the_none_arm_installs_no_hook_and_imports_no_engine() -> None:
    r = isolated(child_none_arm)
    assert r["status"] == {"requested": True, "fault": "none", "rate": 1.0, "steps": [], "engine_version": None}, r["status"]
    assert r["second"] == r["status"], "install() is memoized once per process"
    assert r["sync_untouched"] and r["async_untouched"], r
    assert r["agentchaos_loaded"] is False
    assert r["identity"] is True and r["json"] == COMPLETION


def test_m11a_6_an_unknown_fault_is_refused_by_name_before_any_run_exists(tmp_path: Path) -> None:
    r = isolated(child_unknown_fault)
    assert r["error"] is not None and r["error"]["type"] == "ChaosError", r
    assert "not_a_fault" in r["error"]["message"]
    assert r["sync_untouched"] and r["async_untouched"], r
    store_root = tmp_path / "store"
    toml = write(tmp_path / "sweep.toml", sweep_toml(chaos={"fault": "not_a_fault"}, replicates=1))
    run = isolated(child_run_local, str(store_root), str(toml), f"{MODULE}:chaos_rollout", SALT)
    assert run["error"] is not None and run["error"]["type"] == "ChaosError", run
    assert "not_a_fault" in run["error"]["message"]
    assert run["run_id"] is not None
    with pytest.raises(StoreError):
        Store(store_root).manifest(run["run_id"])


# ---------- M11a-5: a fault that cannot be applied is fatal (D16) ----------


def test_m11a_5_an_unresolvable_target_path_is_fatal_not_a_pass(tmp_path: Path) -> None:
    r = isolated(child_episode, {"fault": "tool_error_single"}, 3, [{"position": ["plan", 1]}], "plain")
    error = r["observed"][0]["error"]
    assert error is not None and "ChaosError" in error["chain"], r["observed"][0]
    assert any(ARGUMENTS_PATH in m for m in error["messages"]), error
    assert r["observed"][0]["json"] is None
    unchanged = isolated(child_episode, {"fault": "llm_empty_single"}, 3, [{"position": ["plan", 1]}], "empty")
    error = unchanged["observed"][0]["error"]  # the path resolves and the payload does not change: the other half of D16
    assert error is not None and "ChaosError" in error["chain"], unchanged["observed"][0]
    assert not [rec for rec in unchanged["records"] if rec["applied"]], unchanged["records"]
    store_root = tmp_path / "store"
    toml = write(tmp_path / "sweep.toml", sweep_toml(chaos={"fault": "tool_error_single"}, replicates=1, bodies=("plain",)))
    run = isolated(child_run_local, str(store_root), str(toml), f"{MODULE}:chaos_rollout", SALT)
    assert run["error"] is not None and run["error"]["type"] == "ChaosError", run
    assert ARGUMENTS_PATH in run["error"]["message"], run["error"]
    store = Store(store_root)
    run_id = run["run_id"]
    assert run_id is not None
    if run_id in store.runs():  # the manifest precedes the first call (executor.py:806); the run is no measurement
        assert store.manifest(run_id).status == "partial"
        assert len(store.read(run_id)) == 0


# ---------- M11a-7, M11a-8: the variate ----------

TRIPLES = [(i * 7919 + 3, ["plan", "solve", "verify", "a:b", "ünïcode"][i % 5], 1 + i % 4) for i in range(100)]


def test_m11a_7_the_variate_is_a_pure_function_of_its_triple_across_interpreters() -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    here = [chaos._variate(seed, name, attempt) for seed, name, attempt in TRIPLES]
    assert all(0.0 <= u < 1.0 for u in here)
    assert here == [reference_variate(seed, name, attempt) for seed, name, attempt in TRIPLES]
    code = (
        "import json, sys\n"
        "from poisson_prove.chaos import _variate\n"
        "print(json.dumps([_variate(s, n, a) for s, n, a in json.loads(sys.argv[1])]))\n"
    )
    env = {**os.environ, "PYTHONHASHSEED": "271828"}
    r = subprocess.run([sys.executable, "-c", code, json.dumps(TRIPLES)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == here


def test_m11a_8_nesting_over_ten_thousand_positions() -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    positions = [(f"step{s}", a) for s in range(100) for a in range(1, 101)]
    seed = 20260913
    fired = {r: {p for p in positions if chaos._variate(seed, *p) < r} for r in (0.0, 0.25, 0.5, 0.75, 1.0)}
    assert fired[0.0] == set()
    assert fired[1.0] == set(positions)
    assert fired[0.25] <= fired[0.5] <= fired[0.75]
    assert 0 < len(fired[0.25]) < len(fired[0.5]) < len(fired[0.75]) < len(positions)


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=(1 << 62) - 1),
    steps=st.lists(st.text(min_size=1, max_size=8), min_size=1, max_size=12, unique=True),
    lo=st.floats(min_value=0.0, max_value=1.0),
    hi=st.floats(min_value=0.0, max_value=1.0),
)
def test_m11a_8b_nesting_holds_for_every_seed_and_every_pair_of_rates(seed: int, steps: list[str], lo: float, hi: float) -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    lo, hi = min(lo, hi), max(lo, hi)
    positions = [(s, a) for s in steps for a in (1, 2, 3)]
    assert {p for p in positions if chaos._variate(seed, *p) < lo} <= {p for p in positions if chaos._variate(seed, *p) < hi}


# ---------- M11a-9, M11a-11, M11a-26: keying, arm identity, a recorded fault is a real one ----------


def _mixed_calls(extra_before: int = 0) -> list[dict[str, Any]]:
    return [{"position": None} for _ in range(extra_before)] + [{"position": list(p)} for p in MIXED_POSITIONS]


def _applied_positions(r: dict[str, Any]) -> list[str]:
    return [rec["position"] for rec in r["records"] if rec["applied"]]


def _timeless(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rec.items() if k not in ("start_ns", "end_ns")}


def _body(r: dict[str, Any], name: str) -> str:
    return json.dumps(r["by_name"][name]["httpx"]["json"], sort_keys=True)


def test_m11a_9_no_call_index_dependence() -> None:
    spec = {"fault": "llm_error_single", "rate": 0.5}
    plain = isolated(child_episode, spec, MIXED_SEED, _mixed_calls())
    padded = isolated(child_episode, spec, MIXED_SEED, _mixed_calls(extra_before=3))
    assert plain["block_error"] is None and padded["block_error"] is None, (plain["block_error"], padded["block_error"])
    expected = sorted(f"{s}:{a}" for s, a in reference_fired(MIXED_SEED, MIXED_POSITIONS, 0.5))
    assert 0 < len(expected) < len(MIXED_POSITIONS)
    assert sorted(_applied_positions(plain)) == expected
    assert sorted(_applied_positions(padded)) == expected
    assert [o["json"] for o in plain["observed"]] == [o["json"] for o in padded["observed"][3:]]
    assert [rec["applied"] for rec in padded["records"][:3]] == [False, False, False]


def test_m11a_11_two_blocks_agree_field_for_field_and_two_faults_share_positions() -> None:
    spec = {"fault": "tool_corrupt_single", "rate": 0.5}
    first = isolated(child_episode, spec, MIXED_SEED, _mixed_calls())
    second = isolated(child_episode, spec, MIXED_SEED, _mixed_calls())
    assert [_timeless(r) for r in first["records"]] == [_timeless(r) for r in second["records"]]
    assert [o["json"] for o in first["observed"]] == [o["json"] for o in second["observed"]]
    assert 0 < len(_applied_positions(first)) < len(MIXED_POSITIONS)
    other = isolated(child_episode, {"fault": "llm_timeout_single", "rate": 0.5}, MIXED_SEED, _mixed_calls())
    assert _applied_positions(other) == _applied_positions(first)
    assert [o["json"] for o in other["observed"]] != [o["json"] for o in first["observed"]]


def test_m11a_26_a_recorded_fault_is_a_real_one() -> None:
    calls = _mixed_calls(extra_before=2)
    r = isolated(child_episode, {"fault": "llm_error_single", "rate": 0.5}, MIXED_SEED, calls)
    assert r["block_error"] is None, r["block_error"]
    assert len(r["records"]) == len(calls) == len(r["observed"])
    for rec, obs in zip(r["records"], r["observed"], strict=True):
        assert obs["error"] is None, obs
        if rec["applied"]:
            assert obs["json"] != obs["transport_json"], rec
            assert rec["fault"] == "llm_error_single" and rec["position"] is not None
        else:
            assert obs["json"] == obs["transport_json"] == COMPLETION, rec
            assert rec["fault"] is None
    assert any(rec["applied"] for rec in r["records"]) and not all(rec["applied"] for rec in r["records"])


# ---------- M11a-10: the catalogue holds no decision ----------


def test_m11a_10_every_entry_is_frozen_with_exactly_five_fields_and_no_counter() -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    catalog = importlib.import_module(CATALOG_MODULE)
    names = tuple(chaos.fault_names())
    assert isinstance(names, tuple) and all(isinstance(n, str) for n in names)
    assert len(names) == len(set(names))
    assert set(names) == FAULT_NAMES, sorted(set(names) ^ FAULT_NAMES)
    assert [n for n in names if n != "none"] == sorted(n for n in names if n != "none")
    assert set(catalog.CATALOG) == set(VOCABULARY), sorted(set(catalog.CATALOG) ^ set(VOCABULARY))
    for name in sorted(VOCABULARY):
        entries = _entries(catalog.CATALOG[name])
        assert len(entries) == len(VOCABULARY[name]), name
        for entry in entries:
            assert dataclasses.is_dataclass(entry) and entry.__dataclass_params__.frozen, (name, entry)
            assert tuple(f.name for f in dataclasses.fields(entry)) == ENTRY_FIELDS, (name, entry)
            assert entry.name == name
            with pytest.raises(dataclasses.FrozenInstanceError):
                entry.value = "mutated"  # type: ignore[misc]
            for forbidden in ("probability", "max_count", "min_count", "_count"):
                assert not hasattr(entry, forbidden), (name, forbidden)


def test_m11a_10b_the_vocabulary_is_theirs_name_path_and_literal() -> None:
    catalog = importlib.import_module(CATALOG_MODULE)
    for name, expected in VOCABULARY.items():
        actual = [(e.intercept, e.action, e.target_path, _norm(e.value)) for e in _entries(catalog.CATALOG[name])]
        for (intercept, action, path, value), (x_intercept, x_action, x_path, x_value) in zip(actual, expected, strict=True):
            assert intercept == x_intercept and action == x_action, (name, actual)
            if action == "delay":
                assert path in ("$", None) and value == x_value, (name, actual)
            elif action == "drop":
                assert path == x_path and value in (None, x_value), (name, actual)
            else:
                assert path == x_path and value == _norm(x_value), (name, actual)


# ---------- M11a-12, M11a-13: position ----------


def test_m11a_12_no_position_no_injection() -> None:
    r = isolated(child_episode, {"fault": "llm_error_single"}, 3, [{"position": None}])
    assert r["block_error"] is None, r["block_error"]
    assert len(r["records"]) == 1
    rec = r["records"][0]
    assert rec["position"] is None and rec["fault"] is None and rec["applied"] is False, rec
    assert r["observed"][0]["identity"] is True and r["observed"][0]["json"] == COMPLETION


def test_m11a_13_position_is_context_local_and_one_based() -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    with pytest.raises(chaos.ChaosError):
        with chaos.position("a", attempt=0):
            pass
    r = isolated(child_threads)
    assert r["zero_error"] is not None and r["zero_error"]["type"] == "ChaosError", r["zero_error"]
    threaded = r["records"][: r["n_threaded"]]
    assert sorted(rec["position"] for rec in threaded) == ["alpha:1", "beta:1"], threaded
    assert all(rec["applied"] for rec in threaded)
    uncopied = r["records"][r["n_threaded"] :]
    assert len(uncopied) == 1 and uncopied[0]["position"] is None and uncopied[0]["applied"] is False, uncopied


# ---------- M11a-14, M11a-16: the carrier literals, never parsed ----------


def test_m11a_14_each_reserved_literal_appears_exactly_once_in_src() -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    files = sorted(PACKAGE.rglob("*.py"))
    counts = {FAULT_KEY: 0, FAULT_POSITION_KEY: 0}
    for path in files:
        for value in _string_constants(path):
            if value in counts:
                counts[value] += 1
    assert counts == {FAULT_KEY: 1, FAULT_POSITION_KEY: 1}, counts
    assert not {"FAULT_KEY", "FAULT_POSITION_KEY", "_FAULT_KEY", "_FAULT_POSITION_KEY"} & set(chaos.__all__), chaos.__all__


def test_m11a_16_the_position_round_trips_and_is_never_parsed() -> None:
    r = isolated(child_episode, {"fault": "llm_error_single"}, 3, [{"position": ["a:b", 2]}])
    assert r["block_error"] is None, r["block_error"]
    assert [rec["position"] for rec in r["records"]] == ["a:b:2"], r["records"]
    assert r["records"][0]["applied"] is True
    tree = ast.parse((PACKAGE / "chaos.py").read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        first = node.args[0] if node.args else None
        literal = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None
        if isinstance(node.func, ast.Attribute) and node.func.attr in SPLIT_FAMILY and literal == ":":
            offenders.append((node.lineno, node.func.attr))
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "re" and literal is not None and ":" in literal:
            offenders.append((node.lineno, f"re.{node.func.attr}"))
    assert offenders == [], offenders


# ---------- M11a-15: the carrier on the captured span ----------


def test_m11a_15_the_captured_span_carries_the_fault_and_its_position(tmp_path: Path) -> None:
    pytest.importorskip("opentelemetry.sdk", reason="the carrier is asserted on a captured span")
    store_root = tmp_path / "store"
    toml = write(tmp_path / "sweep.toml", sweep_toml(chaos={"fault": "llm_error_single", "steps": ["solve"]}, capture={"instrument": []}, replicates=2))
    run = isolated(child_run_local, str(store_root), str(toml), f"{MODULE}:chaos_otel_rollout", SALT)
    assert run["error"] is None, run["error"]
    store = Store(store_root)
    assert store.manifest(run["run_id"]).environment["capture"]["active"] is True, "capture was not on"
    df = store.read(run["run_id"])
    assert len(df) == 2 and df["error"].isna().all(), df
    for row in df.itertuples():
        spans = {span.name: span for span in Trace.from_dict(row.meta["trace"]).spans}
        assert set(spans) == {"chat plan", "chat solve"}, sorted(spans)
        assert spans["chat solve"].attrs[FAULT_KEY] == "llm_error_single"
        assert spans["chat solve"].attrs[FAULT_POSITION_KEY] == "solve:1"
        assert FAULT_KEY not in spans["chat plan"].attrs and FAULT_POSITION_KEY not in spans["chat plan"].attrs
        assert row.meta["observed"][1]["content"] != CONTENT and row.meta["observed"][0]["content"] == CONTENT
    assert FAULT_KEY not in trace_module._LIFTED_KEYS and FAULT_POSITION_KEY not in trace_module._LIFTED_KEYS  # green-before-and-after


# ---------- M11a-17, M11a-18: both hooks, and they agree ----------


def test_m11a_17_both_hooks_inject_at_the_same_position() -> None:
    r = isolated(child_both_hooks)
    assert r["sync_content"] == r["async_content"] == VOCABULARY["llm_error_single"][0][3], r
    assert [rec["applied"] for rec in r["records"]] == [True, True], r["records"]
    assert [rec["position"] for rec in r["records"]] == ["plan:1", "plan:1"]


def test_m11a_18_the_two_hooks_produce_the_same_mutated_body_for_every_name() -> None:
    r = isolated(child_vocabulary, sorted(FAULT_NAMES), 3)
    assert set(r["fault_names"]) == FAULT_NAMES
    for name in sorted(FAULT_NAMES):
        sync, async_ = r["by_name"][name]["httpx"], r["by_name"][name]["httpx-async"]
        assert sync["error"] is None and async_["error"] is None, (name, sync["error"], async_["error"])
        assert json.dumps(sync["json"], sort_keys=True) == json.dumps(async_["json"], sort_keys=True), name


# ---------- M11a-19, M11a-20: pass-through outside the seam ----------


def test_m11a_19_non_llm_traffic_is_untouched() -> None:
    r = isolated(child_episode, {"fault": "llm_error_single"}, 3, [{"position": ["plan", 1], "path": OTHER_PATH}])
    assert r["block_error"] is None, r["block_error"]
    obs = r["observed"][0]
    assert obs["error"] is None and obs["identity"] is True and obs["json"] == EMBEDDING, obs
    assert {k: v for k, v in obs["headers"].items() if k in RESPONSE_HEADERS} == RESPONSE_HEADERS
    assert r["records"] == []


def test_m11a_20_both_hooks_pass_through_outside_an_injecting_block() -> None:
    r = isolated(child_outside_block)
    assert r["before_identity"] is True and r["before_json"] == COMPLETION, r
    assert r["inside_identity"] is False and r["inside_json"] != COMPLETION, r
    assert r["after_identity"] is True and r["after_json"] == COMPLETION, r
    assert r["n_inside"] == r["n_after"] == 1 and r["records"][0]["applied"] is True


# ---------- M11a-21, M11a-22: the manifest record, both backends ----------


def test_m11a_21_the_manifest_carries_the_six_key_record_only_when_asked(tmp_path: Path) -> None:
    target = f"{MODULE}:chaos_rollout"
    faulted = write(tmp_path / "faulted.toml", sweep_toml(chaos={"fault": "llm_error_single", "rate": 0.25, "steps": ["solve"]}))
    control = write(tmp_path / "control.toml", sweep_toml(chaos={"fault": "none"}))
    bare = write(tmp_path / "bare.toml", sweep_toml(chaos=None))
    store = Store(tmp_path / "store")
    runs = {name: isolated(child_run_local, str(tmp_path / "store"), str(path), target, SALT) for name, path in [("faulted", faulted), ("control", control), ("bare", bare)]}
    for name, run in runs.items():
        assert run["error"] is None, (name, run["error"])
    record = store.manifest(runs["faulted"]["run_id"]).environment["chaos"]
    assert set(record) == MANIFEST_KEYS, record
    assert record["requested"] is True and record["fault"] == "llm_error_single" and record["rate"] == 0.25 and record["steps"] == ["solve"]
    assert isinstance(record["engine_version"], str) and record["engine_version"]
    assert record["hooks"] == ["sync", "async"]
    none_record = store.manifest(runs["control"]["run_id"]).environment["chaos"]
    assert set(none_record) == MANIFEST_KEYS and none_record["requested"] is True and none_record["fault"] == "none"
    assert none_record["engine_version"] is None and none_record["hooks"] == []
    assert "chaos" not in store.manifest(runs["bare"]["run_id"]).environment  # green-before-and-after on its own


@pytest.mark.parametrize(
    "episode_timeout",
    [None, pytest.param(30.0, marks=pytest.mark.skipif(not FORK_AVAILABLE, reason="needs fork"))],
    ids=["no-timeout", "fork"],
)
def test_m11a_22_backend_meta_carries_the_record_on_every_ok_result_of_a_chaos_run(tmp_path: Path, episode_timeout: float | None) -> None:
    target = f"{MODULE}:chaos_rollout"
    spec = SweepSpec.load(write(tmp_path / "sweep.toml", sweep_toml(chaos={"fault": "llm_error_single", "rate": 1.0, "steps": ["solve"]}, replicates=3)))
    jobs = jobs_of(plan(spec, Store(tmp_path / "plan-store"), run_salt=SALT))
    payload = {"fault": "llm_error_single", "rate": 1.0, "steps": ["solve"]}
    r = isolated(child_worker_batch, jobs, target, episode_timeout, payload)
    assert len(r["results"]) == len(jobs) == 3
    for result in r["results"]:
        assert isinstance(result, dict) and "error" not in result, result
        record = result["backend_meta"]["chaos"]
        assert set(record) == MANIFEST_KEYS and record["fault"] == "llm_error_single" and record["steps"] == ["solve"], record
        assert result["outcome"] == "fell", result
    control = isolated(child_worker_batch, jobs, target, episode_timeout, None)
    for result in control["results"]:
        assert isinstance(result, dict) and "chaos" not in result["backend_meta"], result  # green-before-and-after on its own
        assert result["outcome"] == "survived", result


def test_m11a_22b_the_mapper_driven_modal_run_records_chaos_on_the_manifest_and_every_row(tmp_path: Path) -> None:
    target = f"{MODULE}:chaos_rollout"
    toml = write(tmp_path / "sweep.toml", sweep_toml(chaos={"fault": "llm_error_single", "rate": 1.0}, replicates=3))
    r = isolated(child_run_with_mapper, str(tmp_path / "store"), str(toml), target, SALT)
    store = Store(tmp_path / "store")
    manifest = store.manifest(r["run_id"])
    assert manifest.backend == "modal" and set(manifest.environment["chaos"]) == MANIFEST_KEYS, manifest.environment
    df = store.read(r["run_id"])
    assert len(df) == 3 and df["error"].isna().all()
    for row in df.itertuples():
        assert set(row.backend_meta["chaos"]) == MANIFEST_KEYS, row.backend_meta
        assert row.outcome == "fell"


# ---------- M11a-23: nothing of theirs but the words (D1) ----------


def test_m11a_23_agentchaos_is_named_only_in_the_catalogue_docstring_and_is_no_dependency() -> None:
    catalog_path = PACKAGE / "chaos_catalog.py"
    assert catalog_path.is_file(), catalog_path
    start, end = _docstring_span(catalog_path)
    assert start > 0, "chaos_catalog.py has no module docstring"
    hits: list[tuple[str, int]] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "agentchaos" in line:
                hits.append((path.name, lineno))
        assert "agentchaos" not in _imported_roots(path), path
    assert hits and all(name == "chaos_catalog.py" and start <= lineno <= end for name, lineno in hits), hits
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "agentchaos" not in pyproject_text.lower()
    data = tomllib.loads(pyproject_text)
    assert set(data["project"]["optional-dependencies"]) == EXTRAS  # green-before-and-after on its own
    assert not any("agentchaos" in dep.lower() for dep in data["project"]["dependencies"])


def test_m11a_23b_the_seam_imports_with_no_client_library_present() -> None:
    code = (
        "import sys\n"
        "for name in ('httpx', 'openai', 'opentelemetry', 'agentchaos', 'loguru'):\n"
        "    sys.modules[name] = None\n"
        "import poisson_prove.chaos, poisson_prove.chaos_catalog, poisson_prove.executor, poisson_prove.executor_modal, poisson_prove.sampler\n"
        "import json\n"
        "print(json.dumps(sorted(poisson_prove.chaos.fault_names())))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert set(json.loads(r.stdout)) == FAULT_NAMES


def _blocked_client_run(script: str) -> dict[str, Any]:
    """Run ``script`` in a fresh interpreter with ``httpx`` and ``openai`` unimportable."""
    code = (
        "import json, sys, traceback\n"
        "for name in ('httpx', 'openai'):\n"
        "    sys.modules[name] = None\n"
        "out = {}\n"
        "try:\n" + "".join(f"    {line}\n" for line in script.splitlines()) +
        "except Exception as exc:\n"
        "    out['raised'] = type(exc).__name__\n"
        "    out['message'] = str(exc)\n"
        "print(json.dumps(out))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_m11a_33_a_faulted_arm_refuses_when_no_client_is_loaded(tmp_path: Path) -> None:
    faulted = _blocked_client_run(
        "from poisson_prove.chaos import ChaosSpec, install\n"
        "install(ChaosSpec(fault='llm_error_single'))\n"
        "out['raised'] = None\n"
    )
    assert faulted["raised"] == "ChaosError", faulted
    assert "httpx" in faulted["message"], faulted
    control = _blocked_client_run(
        "import dataclasses\n"
        "from poisson_prove.chaos import ChaosSpec, install\n"
        "out.update(dataclasses.asdict(install(ChaosSpec())))\n"
    )
    assert control == {"requested": True, "fault": "none", "rate": 1.0, "steps": [], "engine_version": None}, control
    store_root = tmp_path / "store"
    toml = write(tmp_path / "sweep.toml", sweep_toml(chaos={"fault": "llm_error_single"}, replicates=1))
    run = _blocked_client_run(
        "from poisson_prove.episode import Episode\n"
        "from poisson_prove.executor import plan, run_local\n"
        "from poisson_prove.sampler import SweepSpec\n"
        "from poisson_prove.store import Store\n"
        f"store = Store({str(store_root)!r})\n"
        f"p = plan(SweepSpec.load({str(toml)!r}), store, run_salt={SALT!r})\n"
        "run_local(p, lambda cfg, seed: Episode(outcome='survived', t=1.0, horizon=1.0), store)\n"
        "out['raised'] = None\n"
    )
    assert run["raised"] == "ChaosError" and "httpx" in run["message"], run
    assert Store(store_root).runs() == []


# ---------- M11a-24: the paired run ----------


def test_m11a_24_two_arms_from_one_sweep_file_pair_under_diff(tmp_path: Path) -> None:
    target = f"{MODULE}:chaos_rollout"
    store_root = tmp_path / "store"
    control = write(tmp_path / "control.toml", sweep_toml(chaos={"fault": "none"}, replicates=3, bodies=("tools", "plain")))
    faulted = write(tmp_path / "faulted.toml", sweep_toml(chaos={"fault": "llm_error_single"}, replicates=3, bodies=("tools", "plain")))
    a = isolated(child_run_local, str(store_root), str(control), target, SALT)
    b = isolated(child_run_local, str(store_root), str(faulted), target, SALT)
    assert a["error"] is None and b["error"] is None, (a["error"], b["error"])
    store = Store(store_root)
    frame_a, frame_b = store.read(a["run_id"]), store.read(b["run_id"])
    assert set(frame_a["config_hash"]) == set(frame_b["config_hash"]) and len(frame_a) == len(frame_b) == 6
    seeds_a = {(r.config_hash, r.replicate_index): r.seed for r in frame_a.itertuples()}
    seeds_b = {(r.config_hash, r.replicate_index): r.seed for r in frame_b.itertuples()}
    assert seeds_a == seeds_b
    assert set(frame_a["outcome"]) == {"survived"} and set(frame_b["outcome"]) == {"fell"}
    manifest_a, manifest_b = store.manifest(a["run_id"]), store.manifest(b["run_id"])
    assert manifest_a.run_salt == manifest_b.run_salt == SALT
    result = diff(censor(frame_a, "fell"), censor(frame_b, "fell"), event="fell", method="mcnemar_bh", manifest_a=manifest_a, manifest_b=manifest_b)
    assert result.seed_identity_match is True and result.dropped_a == 0 and result.dropped_b == 0, result.to_markdown()


# ---------- M11a-25, M11a-29, M11a-30: the applier ----------


def test_m11a_25_every_fault_changes_the_body_and_never_the_input() -> None:
    r = isolated(child_vocabulary, sorted(VOCABULARY), 3)
    assert r["scripted_unmutated"] is True
    for name in sorted(VOCABULARY):
        per = r["by_name"][name]
        sync = per["httpx"]
        assert sync["error"] is None, (name, sync["error"])
        assert sync["transport_json"] == COMPLETION, name  # the transport's own object was never edited in place
        applied = [rec for rec in per["records"] if rec["applied"]]
        assert len(applied) == 2 and all(rec["fault"] == name for rec in applied), (name, per["records"])
        if name in DELAY_ONLY:
            assert json.dumps(sync["json"], sort_keys=True) == json.dumps(COMPLETION, sort_keys=True), name
            assert all(float(rec["delay_ms"]) == DELAY_ONLY[name] for rec in applied), (name, applied)
        else:
            assert json.dumps(sync["json"], sort_keys=True) != json.dumps(COMPLETION, sort_keys=True), name


def test_m11a_29_five_actions_are_pure_and_one_is_seeded() -> None:
    chaos = importlib.import_module(CHAOS_MODULE)
    assert chaos._content_seed(11, "plan", 1, "tool_corrupt_single") == reference_content_seed(11, "plan", 1, "tool_corrupt_single")
    names = sorted(VOCABULARY)
    seed_one = isolated(child_vocabulary, names, 1)
    seed_two = isolated(child_vocabulary, names, 2)
    again = isolated(child_vocabulary, names, 1)
    padded = isolated(child_vocabulary, names, 1, 3)
    for name in names:
        assert _body(seed_one, name) == _body(again, name), name
        assert _body(seed_one, name) == _body(padded, name), name
        if name in SEEDED_NAMES:
            assert _body(seed_one, name) != _body(seed_two, name), name
        else:
            assert _body(seed_one, name) == _body(seed_two, name), name  # llm_corrupt_single is mojibake: deterministic


def test_m11a_30a_truncate_sets_finish_reason_on_content_and_leaves_it_on_arguments() -> None:
    r = isolated(child_vocabulary, ["llm_truncate_single", "tool_truncate_single"], 3)
    content_cut = r["by_name"]["llm_truncate_single"]["httpx"]["json"]["choices"][0]
    assert content_cut["finish_reason"] == "length"
    assert content_cut["message"]["content"] == CONTENT[: max(1, int(len(CONTENT) * 0.3))]
    arguments_cut = r["by_name"]["tool_truncate_single"]["httpx"]["json"]["choices"][0]
    assert arguments_cut["finish_reason"] == "stop"
    assert arguments_cut["message"]["content"] == CONTENT
    original = json.loads(ARGUMENTS)
    assert json.loads(arguments_cut["message"]["tool_calls"][0]["function"]["arguments"]) == {k: v[: max(1, int(len(v) * 0.3))] for k, v in original.items()}


def test_m11a_30b_error_honours_its_target_path() -> None:
    r = isolated(child_error_override, 3)
    assert r["listed"] is True, "fault_names() did not read the extended catalogue"
    obs = r["observed"]
    assert obs["error"] is None, obs["error"]
    choice = obs["json"]["choices"][0]
    assert choice["message"]["content"] == CONTENT
    assert choice["message"]["tool_calls"][0]["function"]["arguments"] == API_ERROR_TEMPLATE.format(code=418)
    assert [rec["applied"] for rec in r["records"]] == [True]


# ---------- M11a-27, M11a-28: the envelope ----------


def test_m11a_27_the_envelope_survives_an_injection() -> None:
    r = isolated(child_episode, {"fault": "llm_error_single"}, 3, [{"position": ["plan", 1]}, {"position": None}])
    assert r["block_error"] is None, r["block_error"]
    injected, passed = r["observed"]
    assert injected["error"] is None and injected["json"] != COMPLETION, injected
    assert injected["status"] == 200
    kept = {k: v for k, v in injected["headers"].items() if k != "content-length"}
    assert kept == {**RESPONSE_HEADERS, "content-type": "application/json"}, injected["headers"]
    assert "content-length" in injected["headers"]
    assert passed["identity"] is True and passed["json"] == COMPLETION


def test_m11a_28_streaming_is_refused_never_rewritten() -> None:
    calls = [
        {"position": ["plan", 1], "stream": True},
        {"position": None, "stream": True},
        {"position": ["solve", 1], "stream": True, "via": "openai"},
    ]
    r = isolated(child_episode, {"fault": "llm_error_single"}, 3, calls)
    refused, passed, via_sdk = r["observed"]
    assert refused["error"] is not None and "ChaosError" in refused["error"]["chain"], refused
    assert any("plan:1" in m for m in refused["error"]["messages"]), refused["error"]
    assert refused["reached_transport"] is False
    assert passed["error"] is None and passed["identity"] is True and passed["json"] == COMPLETION, passed
    assert via_sdk["error"] is not None and "ChaosError" in via_sdk["error"]["chain"], via_sdk
    assert via_sdk["reached_transport"] is False
    assert all(body["body"]["stream"] is True for body in r["seen"]), r["seen"]
    assert [rec["position"] for rec in r["records"]] == [None], r["records"]


# ---------- M11a-31, M11a-32: removable, and attributed ----------


def test_m11a_31_the_patch_is_removable_by_identity() -> None:
    r = isolated(child_uninstall)
    assert r["patched"] == [True, True], r
    assert r["restored"] == [True, True], r
    assert r["identity"] is True and r["json"] == COMPLETION


def test_m11a_32_attribution_ships_in_the_docstring_and_in_notice() -> None:
    catalog_path = PACKAGE / "chaos_catalog.py"
    docstring = ast.get_docstring(ast.parse(catalog_path.read_text(encoding="utf-8"))) or ""
    for needle in ATTRIBUTION:
        assert needle in docstring, needle
    notice = ROOT / "NOTICE"
    assert notice.is_file(), notice
    text = notice.read_text(encoding="utf-8")
    for needle in ATTRIBUTION:
        assert needle in text, needle
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packaged = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert any(catalog_path.is_relative_to(ROOT / p) for p in packaged), (catalog_path, packaged)


# ---------- the executor signatures the update moved ----------


def test_m11a_0_chaos_rides_beside_capture_on_both_funnels() -> None:
    params = list(inspect.signature(worker_batch).parameters.values())
    assert [p.name for p in params] == ["jobs", "import_path", "episode_timeout", "capture", "chaos"]
    assert params[4].kind is params[4].KEYWORD_ONLY and params[4].default is None
    call = list(inspect.signature(executor._call_in_process).parameters.values())
    assert [p.name for p in call] == ["rollout", "config", "seed", "capture_call", "chaos_call"]
    assert call[4].default is None and call[3].default is None
