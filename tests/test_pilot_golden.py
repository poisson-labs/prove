"""S18 -- the golden suite pilot: the oracle for P1-P13, amended by S22 and carrying Q1-Q13.

**S22 adds ``api_error``**, a fifth outcome for *the agent could not reach the model*, told
apart from ``crashed`` (*the agent's own code could not continue*). Written from "Proofload
-- Spec S22 Pilot api_error Outcome" section 4; P1, P2, P3, P8, P9 and P12 were amended for
it first, in their own commit.

**Three modules of core are imported here that the pilot may not import**:
``proofload.diff.multi_diff`` and ``proofload.survival.competing_set`` for Q10, and
``proofload.cli`` for Q9's ``inspect``. That is a *test* importing core, not the pilot
importing core; P12 is not weakened by it, and the two tests that check the pilot's own
import list (``test_p12_golden_pilot_imports_only_*`` and
``test_p12_nothing_under_src_proofload_names_*``) read the pilot tree, never this file.
The spec's section 6 names the first two; ``cli`` is the third, and Q9 is stated over
``inspect``, which is a CLI verb and exists nowhere else.

Written from "Proofload -- Spec S18 Golden Suite Pilot (Phase 3.5)" section 4. Session B
builds ``examples/golden_pilot/`` against this file and does not edit it. Nothing under
``src/`` changes (P12); if a test here can only pass with a core change, that is a finding to
report, not a change to make.

No network, no API key, no model, no sleep in the tests themselves. The whole file skips
without ``openai``; the one instrumentor test skips without
``opentelemetry-instrumentation-openai-v2`` and, when it runs, installs capture in a child
forked from this process (``isolated``, the M3 capture oracle's helper verbatim in behaviour),
so the pytest process never installs a provider and OpenTelemetry is imported inside test
bodies only (M12's T27 purges ``opentelemetry*`` earlier in the suite). The candidate code the
sandbox runs is fixture code of ours under ``tests/fixtures/golden_pilot/``, never a model's,
which is why the tests may set the boundary variable themselves (section 3, P13).

**How the tests reach the pilot.** ``golden_pilot`` is imported from ``examples/`` -- the
directory named by ``GOLDEN_PILOT_ROOT`` when set, else ``<repo>/examples/golden_pilot``
resolved from ``proofload.__file__`` -- and every test that reads the pilot's tree resolves
its paths from that root, so a shadow tree can point the oracle at itself. The spec-fixed
paths are the eleven files of section 2; a test that needs one that does not exist yet fails
on the path, honestly, until Session B.

**Conventions this oracle fixes where the spec is silent, recorded so they are not
re-litigated. Session B builds to these.**

- **The transport.** ``golden_pilot.agent.client_factory`` is a module-level callable
  ``() -> openai.OpenAI`` that ``rollout`` and ``rollout_patched`` call once per episode, read
  from the module at call time (never bound at import), so a test can replace it. The default
  builds ``openai.OpenAI()`` from ``OPENAI_BASE_URL`` / ``OPENAI_API_KEY``. The tests replace
  it with a client over ``httpx.MockTransport`` (``http_client=``, ``max_retries=0`` so the
  SDK's own retries never hide the agent's), and point ``OPENAI_BASE_URL`` at the local
  discard port, so a build that bypasses the factory fails at once without touching the
  network. The model name is read from ``GOLDEN_PILOT_MODEL`` at call time and sent as the
  request's ``model``; the tests set it to ``fake-model``.
- **The scripted model** answers by ``(task_id, seed)``: ``seed`` is the request's own
  ``seed`` field, ``task_id`` is recovered from the conversation (the message that carries the
  golden's prompt carries ``def <entry_point>(``), and the turn is the number of
  ``assistant`` messages already in the request. The script is therefore stateless -- the
  same fake answers the same request the same way twice (P5, P10) -- and a request beyond the
  script, or to any path but ``chat/completions``, gets HTTP 404 so the agent crashes visibly.
  A scripted 5xx is returned for every attempt at that turn.
- **The reply convention.** A model turn is one fenced ```` ```json ```` block holding an
  object with exactly two keys: ``tool`` (``run_tests`` or ``submit``) and ``code`` (the
  complete candidate source: the golden's prompt followed by the body). A reply with no such
  block is unparseable. The candidate handed to ``sandbox.run_tests`` is that complete
  source; ``run_tests(candidate, golden)`` takes a ``suite.Golden``.
- **Retries and backoff.** "Retried three times" is four requests: the attempt and three
  retries, then ``api_error`` with ``meta["retries"] == 3`` -- ``crashed`` before S22, and
  section 3 of that spec is where it moved. The delays are the module-level tuple
  ``golden_pilot.agent.BACKOFF_S`` of three seconds values, read at call time; the
  tests set it to zeros. ``meta["tokens"]`` sums ``prompt_tokens`` / ``completion_tokens``
  over the replies the episode received.
- **The sandbox knobs.** ``golden_pilot.sandbox.WALL_CLOCK_S`` is ``10.0`` and is read at
  call time; the hang tests lower it to ``1.0`` and the candidate sleeps 30 s. The memory
  limit is best effort: on this macOS ``resource.setrlimit`` refuses every finite value of
  ``RLIMIT_AS`` / ``RLIMIT_DATA`` / ``RLIMIT_RSS`` with ``ValueError`` (measured before this
  file was written), so the sandbox must swallow that error, the allocation test skips on
  darwin, and the limit must sit below the 8 GiB the fixture asks for. The Modal image is
  Linux, where the limit bites. ``TestResult`` has ``passed: bool`` and ``reason: str``.
- **The suite.** ``suite.load(path=None)`` reads a ``.jsonl`` or ``.jsonl.gz`` in the
  HumanEval shape; ``None`` means ``GOLDEN_PILOT_SUITE`` from the environment, else
  ``suite/HumanEval.jsonl.gz`` beside the module. The tests set ``GOLDEN_PILOT_SUITE`` to the
  three-golden fixture, which is how the agent finds a golden by ``cfg["task_id"]``.
  ``Golden`` has the five HumanEval fields. ``make_toml.py --suite PATH --out DIR`` writes
  ``DIR/pilot.toml`` and ``DIR/smoke.toml`` deterministically, and runs without the boundary
  variable (the key holder runs it on a laptop). Only ``golden_pilot.agent`` refuses to
  import without the boundary; ``suite``, ``sandbox``, ``numbers`` and ``make_toml`` do not.
- **The pinned instrumentor entry-point name is ``openai``** -- read from
  ``entry_points(group="opentelemetry_instrumentor")`` in a scratch venv with
  ``opentelemetry-instrumentation-openai-v2`` 2.4b0 and ``openai`` 1.109.1:
  ``openai = opentelemetry.instrumentation.openai_v2:OpenAIInstrumentor``. P8 pins it on
  ``pilot.toml``'s ``[capture].instrument``.
- **Stamps (P7).** "Both stamps on every span" is asserted on the captured llm spans. On the
  S15 surface the stamper is an OpenTelemetry ``SpanProcessor`` and the rollout's own
  ``record()`` spans never pass through it, and the rollout cannot stamp them itself (it is
  never told the run id or the episode id, and P12 forbids the private import that would
  find them); ``_merge_capture`` merges the two traces without stamping. That fact is pinned
  in one test of its own; spec section 3 was amended to this reading after Session A.
  P12 (amended the same day) admits ``proofload.store.Store`` for ``numbers.py``'s CLI entry.
- **``numbers.numbers(store, run_id, *, paired_with=None)``** returns one dict. The three
  numbers, the kind histogram (all seven ``KINDS`` keys, zeros included) and the shares are
  over the ok rows' stored traces. ``contract`` counts ok rows that decode as an ``Episode``
  with ``outcome in OUTCOMES``, ``0 <= t <= horizon``, the manifest's ``t_unit`` equal to
  ``tool_calls``, a ``meta["trace"]`` that decodes with ``truncated is None`` and both stamps
  on every llm span. ``errored.by_error`` is keyed by the error text's last line, so a
  traceback keys as ``RuntimeError: boom`` and S16's row as ``timeout``. ``zero_n`` counts
  ``(cell, event)`` holes over the run's distinct configs and the four failure events, cells
  keyed by ``config_hash``. ``pairing`` matches ok rows of the two runs on
  ``(task_id, temperature, seed)``, strata keyed by ``str(temperature)``, and is ``None``
  without ``paired_with``. The exact key set is in ``test_p9_*``. ``Store.read`` hands back a
  pandas frame, which spells a null ``t``, ``confidence`` or ``error`` as ``NaN``; a reader
  that passes those straight to ``Episode.from_dict`` fails every row (the shim did).
- **The refusal** in ``rollout_patched`` is a ``submit`` tool span (kind ``tool``) that costs
  one ``t``; the result appended to the conversation after a ``run_tests`` call is a message
  of at most 500 characters (P6, as written: the whole appended message, not only the reason).

**A24 -- openai 2, W1-W8.** "Proofload -- Spec A22 pandas 3 Port" section 4's ``W`` block. The
packet moves ``[agent]``, ``[all]`` and the pilot's ``requirements.txt`` from ``openai<2`` to
``openai>=2.20,<3``: no openai 2.x ever shipped ``httpx2``, the instrumentor's hard import of
``httpx`` bites at openai **3**, and the pin was wrong by one major version. This file is A24's
oracle; there is no separate A24 test file (spec section 11).

**This oracle's claim spans two environments, and Session A can only reach one of them**
(Master Action List section 18 standing rule 15). The cells are the *installed* SDK, because
that is what the packet ranges over:

- **openai 1.109.1** -- the venv on Session A's commit. Every one of W1-W8 is asserted here.
- **openai 2.x** -- reachable only after Session B's ``pip install -e '.[dev,agent]'``. Every
  one of W1-W8 is asserted there too.

Eight invariants, eight ids, both cells: **8 + 8 = 16 over two cells against the oracle's own
8**, so no invariant is cell-specific and none is asserted in one cell only. What differs is
which of them the **bare** tree satisfies, and that difference is the classified red set below.
**The gap, named rather than resolved by dropping anything:** W6 and W7 are *asserted* in both
cells but Session A can only *measure* the openai 1.109.1 one, because measuring the other
means performing the reinstall that is Session B's first act. Spec section 10 Q5 -- "has the
instrumentor's ``responses`` gap closed?" -- is therefore answered here for openai 1.109.1
only (**it has not**: zero spans, measured 2026-09-13), and its openai 2 half is owed by
Session B, from this same clause, before it touches a source file.

**A24 is a retrofit packet** (standing rule 12). On Session A's commit, before the build and
before the venv is reinstalled, the classified red set is **W1, W2 and W3** -- three, not the
five spec section 7.3 predicted. W6 and W7 are green here, and are named below with W4, W5 and
W8 as **green before and after**, so their green is not read as evidence the build did
anything. Section 7.3 reasoned about W6 and W7 only from *is the instrumentor installed*
(red if yes, skipped if no) and never from *what the clause asserts*; both are preservation
clauses of exactly W8's kind -- W6 pins the measured equality of the instrumentor's attribute
set across openai 1.109.1 and 2.54.0 (spec section 3.7), and W7 pins an absence measured on
1.109.1 that section 10 Q5 asks to be re-measured on 2. Filing either as a red would halt
Session B on a test that passes, which section 7.3 says of W8 in as many words.

- **Red (a source edit clears two; an install clears one).** **W1** -- the pilot's
  ``requirements.txt`` still says ``openai<2``; cleared by Session B editing the file.
  **W2** -- ``pyproject.toml`` still pins ``openai<2`` in ``[agent]`` and ``[all]``; cleared
  the same way. **W3** -- **environmental**: it reads ``importlib.metadata.version("openai")``
  and is a statement about the machine, not about the repo. **No source edit can clear it**;
  it clears when the venv is reinstalled, and a builder who goes looking for the file that
  makes it green will not find one (spec section 10 Q6).
- **Green before and after.** **W4**, **W5** -- unchanged from ``101028c``; they exist to stop
  the bump moving the request path. **W6**, **W7** -- measured green on openai 1.109.1, see
  above. **W8** -- the error path, the only clause that measures it: ``agent.py:174`` catches
  ``openai.APIError`` and ``:176`` formats ``type(exc).__name__``, and
  ``RateLimitError`` -> ``APIStatusError`` -> ``APIError`` is what makes that base-class catch
  reach a 429 at all. Its value is on the far side of the reinstall: S22's whole ``api_error``
  classification, and before it S18's addendum-1 filter on
  ``crash_reason.startswith("API error")``, rest on that hierarchy surviving to openai 2.

**Two tests are renamed by the amendment**, because their old names assert the opposite of
what they now say and a stale name is what gets re-litigated:
``test_p11_requirements_pin_openai_below_2_and_name_the_instrumentor_and_proofload`` ->
``test_w1_requirements_pin_openai_2_and_name_the_instrumentor_and_proofload``, and
``test_p11_the_installed_openai_is_below_2`` -> ``test_w3_the_installed_openai_is_major_2``.
Session B reproduces the red set under the **new** ids.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import importlib.metadata
import io
import json
import math
import multiprocessing
import os
import re
import subprocess
import sys
import time
import tomllib
import traceback
import types
from collections.abc import Callable, Iterator, Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

import proofload
from proofload import cli
from proofload.diff import multi_diff
from proofload.episode import Episode
from proofload.executor import plan, run_local
from proofload.sampler import SweepSpec
from proofload.store import EpisodeRecord, RunManifest, Store, config_hash
from proofload.survival import competing_set
from proofload.trace import KINDS, Span, Trace

openai = pytest.importorskip("openai", reason="the pilot's agent speaks through the openai SDK")
httpx = pytest.importorskip("httpx", reason="the scripted model is an httpx.MockTransport")

MODULE = __name__
HERE = Path(__file__).resolve().parent
PACKAGE = Path(proofload.__file__).resolve().parent  # the tree under test; a shadow tree under PYTHONPATH
REPO = PACKAGE.parents[1]
FIXTURES = HERE / "fixtures" / "golden_pilot"
MINI_SUITE = FIXTURES / "mini_suite.jsonl"
WRONG: dict[str, str] = json.loads((FIXTURES / "wrong_solutions.json").read_text())
BAD: dict[str, str] = json.loads((FIXTURES / "bad_candidates.json").read_text())
ROOT = Path(os.environ.get("GOLDEN_PILOT_ROOT") or REPO / "examples" / "golden_pilot").resolve()
REAL_SUITE = ROOT / "suite" / "HumanEval.jsonl.gz"
FORK_AVAILABLE = "fork" in multiprocessing.get_all_start_methods()
needs_fork = pytest.mark.skipif(not FORK_AVAILABLE, reason="capture installs in a forked child")

if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))  # `import golden_pilot` from examples/ (or the shadow tree)

OUTCOMES = ("passed", "failed_assertion", "timed_out", "crashed", "api_error")
FORBIDDEN_OUTCOMES = ("timeout", "error", "")
T_UNIT = "tool_calls"
HORIZON = 6
FAILURE_EVENTS = ("failed_assertion", "timed_out", "crashed", "api_error")
MODEL = "fake-model"
DISCARD_URL = "http://127.0.0.1:9/v1"  # the discard port: a bypassed transport is refused locally
INSTRUMENTOR = "openai"  # pinned from entry_points(group="opentelemetry_instrumentor"), see the docstring
RUN_ID_KEY = "proofload.run_id"
EPISODE_KEY = "proofload.episode"
BOUNDARY_VAR = "GOLDEN_PILOT_BOUNDARY"
BOUNDARY_VALUE = "container"
ENV_LINE = "ENV GOLDEN_PILOT_BOUNDARY=container"
SUITE_VAR = "GOLDEN_PILOT_SUITE"
MODEL_VAR = "GOLDEN_PILOT_MODEL"
ALLOWED_IMPORTS = frozenset({"Episode", "record", "collect", "step", "Trace", "Store"})  # Store: numbers.py's CLI entry (P12, amended)
ALLOWED_MODULES = frozenset({"proofload", "proofload.episode", "proofload.trace", "proofload.store"})
PILOT_FILES = (
    "README.md", "requirements.txt", "fetch_suite.py", "suite.py", "sandbox.py", "agent.py",
    "numbers.py", "pilot.toml", "smoke.toml", "make_toml.py", "Dockerfile",
)
REASON_CAP = 500
WALL_CLOCK_S = 10.0
FAST_WALL_CLOCK_S = 1.0
HANG_SLACK_S = 8.0  # interpreter start, the kill and the join, on top of the wall clock; an upper bound only
HANG_SLEEP_S = 30.0  # what the fixture candidate sleeps; only the wall clock ends it
CONTENT_KEYS = ("gen_ai.input.messages", "gen_ai.output.messages")
CONTENT_PREFIXES = ("gen_ai.prompt", "gen_ai.completion")
SALT = "golden-pilot-oracle-salt"
EPOCH = 1_756_900_000_000_000_000
STEP_NS = 10_000_000

# S17's measure of "what S17 left them": every public name each module defines itself, and
# the __all__ lists, copied verbatim from tests/test_m3_crash_trace.py.
TRACE_EXPORTS = [
    # A7 (spec section 7.1): four mints; A8a (spec section 7.1 group 3): three constants --
    # ALIAS_MAP_VERSION, GATE, OUTCOME_BY -- in trace.py's own order: constants, classes,
    # functions, each sorted. 25 names; FAULT_KEY / FAULT_POSITION_KEY are not A8a's (section 10 Q3).
    "ALIAS_MAP_VERSION", "ATTRIBUTE_ALIASES", "DROP_REASONS", "GATE", "KINDS", "LOGPROBS_KEY",
    "OBSERVATION_KEYS", "OTEL_KIND_MAP", "OTEL_SEMCONV_VERSION", "OUTCOME_BY", "SCHEMA", "SOURCES",
    "Collector", "Span", "SpanHandle", "Trace", "TraceValidationError",
    "assemble", "collect", "from_litellm", "from_otel", "merge", "record", "split", "step",
]
OTEL_EXPORTS = ["EPISODE_KEY", "RUN_ID_KEY", "EpisodeStamper", "episode"]
MODAL_EXPORTS = [
    "CostGuard", "ImageSpec", "Job", "Mapper", "ModalBackendError", "ModalNotInstalled",
    "ModalOptions", "ModalTarget", "Result", "estimate_cost", "preflight_modal", "run_modal",
    "run_with_mapper", "worker_batch",
]
PUBLIC_CAPTURE = frozenset({"CaptureSpec", "CaptureStatus", "install", "Recorder", "capture"})
EXECUTOR_PUBLIC = frozenset({
    "ExecutorError", "NotResumable", "Pair", "PairMismatch", "Plan", "RunSummary",
    "derive_seed", "new_run_id", "new_run_salt", "plan", "preflight", "run_local",
    # S23: the power gate. DEFAULT_MAX_MDE is a constant and not a defined object, so it
    # does not reach _defined(); these three do.
    "UnderpoweredDesign", "check_power", "preflight_mde",
})
MODAL_PUBLIC = frozenset({
    "CostGuard", "ImageSpec", "ModalBackendError", "ModalNotInstalled", "ModalOptions",
    "ModalTarget", "estimate_cost", "preflight_modal", "run_modal", "run_with_mapper",
    "worker_batch",
})
INIT_PUBLIC = frozenset({"Episode", "EpisodeValidationError", "Rollout", "record"})


# ---------- the mini-suite ----------


@dataclasses.dataclass(frozen=True)
class Row:
    """One HumanEval problem exactly as the fixture stores it."""

    task_id: str
    prompt: str
    entry_point: str
    canonical_solution: str
    test: str


GOLDENS: tuple[Row, ...] = tuple(
    Row(**json.loads(line)) for line in MINI_SUITE.read_text(encoding="utf-8").splitlines() if line.strip()
)
BY_ID: dict[str, Row] = {g.task_id: g for g in GOLDENS}
HE0, HE2, HE3 = "HumanEval/0", "HumanEval/2", "HumanEval/3"
BAD_TASK = BAD["_task_id"]


def canonical(task_id: str) -> str:
    """The complete correct candidate: the prompt followed by the canonical body."""
    return BY_ID[task_id].prompt + BY_ID[task_id].canonical_solution


def wrong(task_id: str) -> str:
    return BY_ID[task_id].prompt + WRONG[task_id]


def bad(name: str) -> str:
    return BY_ID[BAD_TASK].prompt + BAD[name]


def task_of(messages: Sequence[Mapping[str, Any]]) -> str | None:
    """Which mini-suite golden a conversation is about: its prompt carries ``def <entry>(``."""
    text = "\n".join(str(m.get("content")) for m in messages if isinstance(m, Mapping))
    for golden in GOLDENS:
        if f"def {golden.entry_point}(" in text:
            return golden.task_id
    return None


# ---------- the scripted model ----------


@dataclasses.dataclass(frozen=True)
class Reply:
    kind: str  # "tool" | "garbage" | "status"
    tool: str | None = None
    code: str | None = None
    text: str | None = None
    status: int = 200


def tool_reply(tool: str, code: str) -> Reply:
    return Reply("tool", tool=tool, code=code)


GARBAGE = Reply("garbage", text="I believe the function is correct as written, so nothing more is needed here.")
FIVE_HUNDRED = Reply("status", status=500)
#: W8. The 429 sits beside the 500 because the only API failure this project ever measured at
#: scale was a 429 -- ``insufficient_quota``, the S18 abort, 2,048 rows -- and the SDK raises a
#: *different* ``APIError`` subclass for it than for the 500 the oracle already scripts.
FOUR_TWENTY_NINE = Reply("status", status=429)


def fenced(tool: str, code: str) -> str:
    return (
        "Calling a tool.\n\n```json\n"
        + json.dumps({"tool": tool, "code": code})
        + "\n```\n"
    )


def prompt_tokens(turn: int) -> int:
    return 100 + turn


def completion_tokens(turn: int) -> int:
    return 10 + turn


@dataclasses.dataclass(frozen=True)
class Request:
    method: str
    path: str
    body: bytes
    task_id: str | None
    seed: Any
    turn: int

    @property
    def json(self) -> dict[str, Any]:
        return dict(json.loads(self.body))


ALL_REQUESTS: list[Request] = []  # every request any scripted model in this process saw (P11)

Script = Mapping[tuple[str, int | None], Sequence[Reply]]


class ScriptedModel:
    """``httpx.MockTransport`` scripted by ``(task_id, seed)``; ``seed=None`` is a wildcard.

    Stateless by construction: the turn is read off the request, so two identical episodes
    get identical replies. Records every request it sees.
    """

    def __init__(self, script: Script) -> None:
        self.script: dict[tuple[str, int | None], tuple[Reply, ...]] = {
            key: tuple(replies) for key, replies in script.items()
        }
        self.requests: list[Request] = []
        self.transport = httpx.MockTransport(self.handle)

    def client(self) -> Any:
        """The ``client_factory`` the tests install on ``golden_pilot.agent``."""
        return openai.OpenAI(
            api_key="oracle-key-never-sent",
            base_url=DISCARD_URL,
            http_client=httpx.Client(transport=self.transport),
            max_retries=0,
        )

    def handle(self, request: Any) -> Any:
        body = bytes(request.content)
        try:
            data = json.loads(body) if body else {}
        except ValueError:
            data = {}
        messages = data.get("messages") if isinstance(data, Mapping) else None
        messages = messages if isinstance(messages, list) else []
        task_id = task_of(messages)
        seed = data.get("seed") if isinstance(data, Mapping) else None
        turn = sum(1 for m in messages if isinstance(m, Mapping) and m.get("role") == "assistant")
        seen = Request(request.method, request.url.path, body, task_id, seed, turn)
        self.requests.append(seen)
        ALL_REQUESTS.append(seen)
        if not request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                404, json={"error": {"message": f"the oracle scripts chat completions only, not {request.url.path}"}}
            )
        replies = self.script.get((task_id, seed)) if task_id is not None else None
        if replies is None and task_id is not None:
            replies = self.script.get((task_id, None))
        if replies is None or turn >= len(replies):
            return httpx.Response(
                404, json={"error": {"message": f"no scripted reply for {(task_id, seed)!r} at turn {turn}"}}
            )
        reply = replies[turn]
        if reply.kind == "status":
            return httpx.Response(
                reply.status, json={"error": {"message": "scripted upstream failure", "type": "server_error"}}
            )
        content = reply.text if reply.kind == "garbage" else fenced(str(reply.tool), str(reply.code))
        return httpx.Response(
            200,
            json={
                "id": f"chatcmpl-oracle-{turn}",
                "object": "chat.completion",
                "created": 0,
                "model": data.get("model") if isinstance(data, Mapping) else MODEL,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens(turn),
                    "completion_tokens": completion_tokens(turn),
                    "total_tokens": prompt_tokens(turn) + completion_tokens(turn),
                },
            },
        )


def steps(*calls: tuple[str, str]) -> tuple[Reply, ...]:
    return tuple(tool_reply(tool, code) for tool, code in calls)


# ---------- fixtures: the environment, the modules, the episodes ----------


@pytest.fixture
def pilot_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The boundary, the fixture suite, the model name, and a local URL no build can reach."""
    monkeypatch.setenv(BOUNDARY_VAR, BOUNDARY_VALUE)
    monkeypatch.setenv(SUITE_VAR, str(MINI_SUITE))
    monkeypatch.setenv(MODEL_VAR, MODEL)
    monkeypatch.setenv("OPENAI_API_KEY", "oracle-key-never-sent")
    monkeypatch.setenv("OPENAI_BASE_URL", DISCARD_URL)


@pytest.fixture
def sandbox(pilot_env: None) -> Any:
    return importlib.import_module("golden_pilot.sandbox")


@pytest.fixture
def suite(pilot_env: None) -> Any:
    return importlib.import_module("golden_pilot.suite")


@pytest.fixture
def agent(pilot_env: None, monkeypatch: pytest.MonkeyPatch) -> Any:
    module = importlib.import_module("golden_pilot.agent")
    monkeypatch.setattr(module, "BACKOFF_S", (0.0, 0.0, 0.0))
    return module


@pytest.fixture
def fast_sandbox(sandbox: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(sandbox, "WALL_CLOCK_S", FAST_WALL_CLOCK_S)
    return sandbox


def golden_of(suite: Any, task_id: str) -> Any:
    return suite.Golden(**dataclasses.asdict(BY_ID[task_id]))


@dataclasses.dataclass
class Run:
    episode: Any
    requests: list[Request]
    wall_s: float


def drive(
    agent: Any,
    monkeypatch: pytest.MonkeyPatch,
    script: Script,
    *,
    task_id: str,
    seed: int,
    temperature: float = 0.0,
    patched: bool = False,
    model: ScriptedModel | None = None,
) -> Run:
    """One episode through ``rollout`` (or ``rollout_patched``) against a scripted model."""
    model = ScriptedModel(script) if model is None else model
    monkeypatch.setattr(agent, "client_factory", model.client)
    fn = agent.rollout_patched if patched else agent.rollout
    start = len(model.requests)
    t0 = time.perf_counter()
    episode = fn({"task_id": task_id, "temperature": temperature}, seed)
    return Run(episode, model.requests[start:], time.perf_counter() - t0)


def scenario(name: str) -> tuple[str, int, tuple[Reply, ...]]:
    """The P1/P2 scripts, each keyed to its own (task_id, seed)."""
    table: dict[str, tuple[str, int, tuple[Reply, ...]]] = {
        "passed": (HE0, 22, steps(("submit", canonical(HE0)))),
        "passed_after_tests": (HE3, 23, steps(("run_tests", canonical(HE3)), ("submit", canonical(HE3)))),
        "failed_assertion": (HE3, 24, steps(("submit", wrong(HE3)))),
        "failed_after_tests": (HE2, 25, steps(("run_tests", wrong(HE2)), ("submit", wrong(HE2)))),
        "timed_out": (HE0, 21, steps(*(("run_tests", wrong(HE0)),) * HORIZON)),
        "api_error": (HE2, 11, (FIVE_HUNDRED,)),
        "rate_limited": (HE2, 16, (FOUR_TWENTY_NINE,)),  # W8
        "garbage": (HE2, 12, (GARBAGE, GARBAGE)),
        "api_error_after_two_calls": (HE2, 13, (*steps(("run_tests", canonical(HE2)), ("run_tests", canonical(HE2))), FIVE_HUNDRED)),
        "crash_after_two_calls": (HE2, 14, (*steps(("run_tests", canonical(HE2)), ("run_tests", canonical(HE2))), GARBAGE, GARBAGE)),
        "api_error_at_repair_turn": (HE2, 15, (GARBAGE, FIVE_HUNDRED)),
        "hang": (BAD_TASK, 31, steps(("run_tests", bad("hangs")), ("submit", canonical(BAD_TASK)))),
    }
    return table[name]


def play(agent: Any, monkeypatch: pytest.MonkeyPatch, name: str, *, patched: bool = False) -> Run:
    task_id, seed, replies = scenario(name)
    return drive(agent, monkeypatch, {(task_id, seed): replies}, task_id=task_id, seed=seed, patched=patched)


def text_of(message: Mapping[str, Any]) -> str:
    content = message.get("content")
    return content if isinstance(content, str) else json.dumps(content)


def trace_of(episode: Any) -> Trace:
    return Trace.from_dict(episode.meta["trace"])


def tool_spans(trace: Trace) -> list[Span]:
    return [s for s in trace.ordered() if s.kind == "tool"]


def _defined(module: Any) -> set[str]:
    """The public names a module defines itself: S17's measure of its surface."""
    return {
        name
        for name, obj in vars(module).items()
        if not name.startswith("_") and getattr(obj, "__module__", None) == module.__name__
    }


def pilot_python_files() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts and p.is_file()
    )


def subprocess_env(**extra: str) -> dict[str, str]:
    """A child environment with the pilot importable and the boundary variable removed."""
    env = {k: v for k, v in os.environ.items() if k != BOUNDARY_VAR}
    paths = [str(ROOT.parent), str(PACKAGE.parent), env.get("PYTHONPATH", "")]
    env["PYTHONPATH"] = os.pathsep.join(p for p in paths if p)
    env.update(extra)
    return env


# ---------- helpers: isolation (the M3 capture oracle's, verbatim in behaviour) ----------


def _child_entry(conn: Any, fn: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        outcome: tuple[str, Any] = ("ok", fn(*args))
    except BaseException:  # noqa: BLE001 - the child must always report
        outcome = ("error", traceback.format_exc())
    try:
        conn.send(outcome)
    finally:
        conn.close()


def isolated(fn: Callable[..., Any], *args: Any, timeout: float = 120.0) -> Any:
    """Run ``fn(*args)`` in a child process and return its (JSON-native) result."""
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


def _isnull(value: Any) -> bool:
    """pandas spells an all-None column as NaN: read the store the way the S15 oracle does."""
    return value is None or (isinstance(value, float) and math.isnan(value))


def capture_toml(path: Path) -> Path:
    lines = [
        f'target_id = "golden-pilot/{MODEL}@v0"',
        f't_unit = "{T_UNIT}"',
        "replicates = 1",
        "",
        "[axes.task_id]",
        'type = "categorical"',
        f"values = {json.dumps([g.task_id for g in GOLDENS])}",
        "",
        "[axes.temperature]",
        'type = "continuous"',
        "values = [0.0]",
        "",
        "[capture]",
        f'instrument = ["{INSTRUMENTOR}"]',
        "content = false",
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def child_capture_run(store_root: str, toml_path: str) -> dict[str, Any]:
    """Everything that installs a provider: the real instrumentor named in ``[capture]``,
    ``run_local`` in-process (no episode timeout, so nothing forks again), the store read back."""
    os.environ[BOUNDARY_VAR] = BOUNDARY_VALUE
    os.environ[SUITE_VAR] = str(MINI_SUITE)
    os.environ[MODEL_VAR] = MODEL
    os.environ["OPENAI_API_KEY"] = "oracle-key-never-sent"
    os.environ["OPENAI_BASE_URL"] = DISCARD_URL
    agent = importlib.import_module("golden_pilot.agent")
    agent.BACKOFF_S = (0.0, 0.0, 0.0)
    script: dict[tuple[str, int | None], tuple[Reply, ...]] = {
        (g.task_id, None): steps(("run_tests", canonical(g.task_id)), ("submit", canonical(g.task_id)))
        for g in GOLDENS
    }
    model = ScriptedModel(script)
    agent.client_factory = model.client
    store = Store(store_root)
    p = plan(SweepSpec.load(toml_path), store, run_salt=SALT, import_path="golden_pilot.agent:rollout")
    summary = run_local(p, agent.rollout, store, episode_timeout=None)
    df = store.read(p.run_id)
    rows = [
        {
            "task_id": str(row.config["task_id"]),
            "seed": int(row.seed),
            "outcome": row.outcome,
            "t": row.t,
            "error": None if _isnull(row.error) else str(row.error),
            "meta": dict(row.meta),
            "config_hash": str(row.config_hash),
            "replicate_index": int(row.replicate_index),
        }
        for row in df.itertuples()
    ]
    return {
        "run_id": p.run_id,
        "summary": dataclasses.asdict(summary),
        "rows": rows,
        "capture": store.manifest(p.run_id).environment.get("capture"),
        "requests": [[q.task_id, q.seed, q.path] for q in model.requests],
    }


#: W6, W7. The probe's base URL, deliberately **portless**. The attribute set W6 pins is the
#: *instrumentor's*; ``server.port`` is the base URL's. A probe pointed at ``DISCARD_URL``
#: measures ten attributes, nine of them the instrumentor's and the tenth the oracle's own
#: choice of port. ``.invalid`` is reserved (RFC 2606) and never resolves, so a bypassed
#: transport fails here as loudly as it does at the discard port.
PROBE_URL = "http://discard.invalid/v1"

#: W6. The nine measured on instrumentor 2.4b0 against openai 1.109.1 **and** 2.54.0 (spec
#: section 3.7), from one *bare* ``chat.completions.create``. The pilot's own call passes
#: ``max_tokens``, ``seed`` and ``temperature``, each of which adds a ``gen_ai.request.*`` key;
#: the probe passes none of them, so what is pinned is the set the instrumentor derives and not
#: the set the caller happened to ask for.
INSTRUMENTOR_ATTRIBUTES = [
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.request.model",
    "gen_ai.response.finish_reasons",
    "gen_ai.response.id",
    "gen_ai.response.model",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "server.address",
]


def probe_transport() -> Any:
    """A transport answering both verbs. ``responses`` succeeds rather than 404s, so W7
    measures the instrumentor's silence on a call that *worked*: an instrumented call that
    raises would still emit a span, and a 404 would let W7 pass for the wrong reason."""

    def handle(request: Any) -> Any:
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-probe-0",
                    "object": "chat.completion",
                    "created": 0,
                    "model": MODEL,
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "one turn"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
                },
            )
        if request.url.path.endswith("/responses"):
            return httpx.Response(
                200,
                json={
                    "id": "resp-probe-0",
                    "object": "response",
                    "created_at": 0,
                    "model": MODEL,
                    "status": "completed",
                    "output": [],
                    "parallel_tool_calls": False,
                    "tool_choice": "auto",
                    "tools": [],
                },
            )
        return httpx.Response(404, json={"error": {"message": f"the probe scripts two verbs, not {request.url.path}"}})

    return httpx.MockTransport(handle)


def child_instrumented_spans(verb: str) -> list[dict[str, Any]]:
    """One instrumented call through ``probe_transport``, and the spans it finished.

    Child-only, like every other capture path in this file: the pytest process never installs a
    provider and never imports ``opentelemetry`` at module level (M12's T27 purges
    ``opentelemetry*`` earlier in the suite)."""
    from opentelemetry import trace as ot_trace
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    ot_trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    client = openai.OpenAI(
        api_key="oracle-key-never-sent",
        base_url=PROBE_URL,
        http_client=httpx.Client(transport=probe_transport()),
        max_retries=0,
    )
    if verb == "chat":
        client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": "one turn"}])
    else:
        client.responses.create(model=MODEL, input="one turn")
    return [{"name": span.name, "attributes": sorted(span.attributes or {})} for span in exporter.get_finished_spans()]


def instrumentor_or_skip() -> None:
    """W6, W7's gate. A **skip is not a green**: without the instrumentor these two say nothing,
    which is why spec section 7.3 names skipped and red as the two states it expected. Spec
    section 10 Q6's point, one clause over: an absent instrumentor and a wrong openai must not
    look the same in the red set, so W3 fails on the version and these two skip on the import."""
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    pytest.importorskip(
        "opentelemetry.instrumentation.openai_v2",
        reason="the instrumentor tests need opentelemetry-instrumentation-openai-v2",
    )
    if not FORK_AVAILABLE:
        pytest.skip("the instrumentor installs a global provider, so it installs in a child")


@pytest.fixture(scope="module")
def capture_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """One run under real autoinstrumentation, shared by the two P7 tests that read it."""
    pytest.importorskip("opentelemetry.sdk", reason="capture lives behind the [agent] extra")
    pytest.importorskip(
        "opentelemetry.instrumentation.openai_v2",
        reason="the instrumentor test needs opentelemetry-instrumentation-openai-v2",
    )
    names = {ep.name for ep in importlib.metadata.entry_points(group="opentelemetry_instrumentor")}
    if INSTRUMENTOR not in names:
        pytest.skip(f"no {INSTRUMENTOR!r} entry point in the opentelemetry_instrumentor group: {sorted(names)}")
    if not FORK_AVAILABLE:
        pytest.skip("capture installs in a forked child")
    root = tmp_path_factory.mktemp("capture")
    toml = capture_toml(root / "sweep.toml")
    return isolated(child_capture_run, str(root / "store"), str(toml))


# ---------- P1: the contract ----------


def test_p1_outcomes_is_exactly_the_five_names_in_the_spec_order(agent: Any) -> None:
    assert agent.OUTCOMES == OUTCOMES
    assert isinstance(agent.OUTCOMES, tuple)


def test_p1_t_unit_and_horizon_are_the_spec_constants(agent: Any) -> None:
    assert agent.T_UNIT == T_UNIT
    assert agent.HORIZON == HORIZON


@pytest.mark.parametrize(
    "name",
    ["passed", "passed_after_tests", "failed_assertion", "failed_after_tests", "timed_out", "api_error", "garbage", "api_error_after_two_calls", "crash_after_two_calls"],
)
def test_p1_every_scripted_path_returns_an_episode_inside_the_contract(agent: Any, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    task_id, _, _ = scenario(name)
    run = play(agent, monkeypatch, name)
    episode = run.episode
    assert isinstance(episode, Episode), type(episode)
    assert episode.outcome in OUTCOMES, episode.outcome
    assert 0 <= episode.t <= HORIZON and float(episode.t).is_integer(), episode.t
    assert episode.horizon == HORIZON
    assert {"task_id", "crash_reason", "retries", "tokens", "trace"} <= set(episode.meta), sorted(episode.meta)
    assert episode.meta["task_id"] == task_id
    assert set(episode.meta["tokens"]) == {"in", "out"}, episode.meta["tokens"]
    assert isinstance(episode.meta["retries"], int) and episode.meta["retries"] >= 0


def test_p1_a_candidate_that_hangs_never_raises_out_of_the_rollout(agent: Any, fast_sandbox: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "hang")
    assert isinstance(run.episode, Episode)
    assert run.episode.outcome == "passed" and run.episode.t == 2, run.episode
    assert run.wall_s < FAST_WALL_CLOCK_S + HANG_SLACK_S, run.wall_s


# ---------- P2: outcome semantics ----------


def test_p2_a_submitted_canonical_solution_is_passed(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "passed")
    assert run.episode.outcome == "passed" and run.episode.t == 1, run.episode
    assert run.episode.meta["crash_reason"] is None and run.episode.meta["retries"] == 0
    assert len(run.requests) == 1
    assert run.episode.meta["tokens"] == {"in": prompt_tokens(0), "out": completion_tokens(0)}


def test_p2_a_submitted_wrong_solution_is_failed_assertion(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "failed_assertion")
    assert run.episode.outcome == "failed_assertion" and run.episode.t == 1, run.episode
    assert run.episode.meta["crash_reason"] is None
    run2 = play(agent, monkeypatch, "failed_after_tests")
    assert run2.episode.outcome == "failed_assertion" and run2.episode.t == 2, run2.episode


def test_p2_horizon_run_tests_turns_with_no_submit_is_timed_out_at_horizon(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "timed_out")
    assert run.episode.outcome == "timed_out" and run.episode.t == HORIZON, run.episode
    assert len(run.requests) == HORIZON, [q.turn for q in run.requests]  # the budget, not one more
    assert run.episode.meta["crash_reason"] is None


def test_p2_three_5xx_replies_are_an_api_error_naming_it_with_three_retries(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "api_error")
    assert run.episode.outcome == "api_error" and run.episode.t == 0, run.episode
    assert run.episode.meta["retries"] == 3
    assert len(run.requests) == 4, [q.turn for q in run.requests]  # the attempt and three retries
    reason = run.episode.meta["crash_reason"]
    assert isinstance(reason, str) and ("500" in reason or "InternalServerError" in reason), reason
    assert run.episode.meta["tokens"] == {"in": 0, "out": 0}


def test_w8_a_scripted_429_is_an_api_error_after_three_retries_naming_the_rate_limit(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A24 W8. Green before and after, and the only clause of the packet that measures the
    error path at all: W6 measures the success path and W7 an absence. ``agent.py:174`` catches
    ``openai.APIError``, the SDK base class, and ``:176`` formats ``type(exc).__name__`` into
    ``meta["crash_reason"]`` -- so S22's whole ``api_error`` classification, and before it S18's
    addendum-1 filter on ``crash_reason.startswith("API error")``, rest on
    ``RateLimitError`` -> ``APIStatusError`` -> ``APIError`` surviving the bump to openai 2. The
    429 is scripted rather than the 500 because a 429 is a *different* ``APIError`` subclass,
    and because the only API failure this project measured at scale was one."""
    run = play(agent, monkeypatch, "rate_limited")
    assert run.episode.outcome == "api_error" and run.episode.t == 0, run.episode
    assert run.episode.meta["retries"] == 3
    assert len(run.requests) == 4, [q.turn for q in run.requests]  # the attempt and three retries
    reason = run.episode.meta["crash_reason"]
    assert isinstance(reason, str) and reason.startswith("API error after 3 retries: RateLimitError: "), reason
    assert "429" in reason, reason
    caught = [
        ast.unparse(node.type)
        for node in ast.walk(parsed(ROOT / "agent.py"))
        if isinstance(node, ast.ExceptHandler) and node.type is not None
    ]
    assert "openai.APIError" in caught, caught
    assert openai.APIError in openai.RateLimitError.__mro__, openai.RateLimitError.__mro__


def test_p2_two_unparseable_replies_crash_naming_the_parse_failure(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "garbage")
    assert run.episode.outcome == "crashed" and run.episode.t == 0, run.episode
    assert len(run.requests) == 2, [q.turn for q in run.requests]  # the reply and its one repair turn
    reason = run.episode.meta["crash_reason"]
    assert isinstance(reason, str) and "pars" in reason.lower(), reason
    assert run.episode.meta["retries"] == 0
    assert run.episode.meta["tokens"] == {"in": prompt_tokens(0) + prompt_tokens(1), "out": completion_tokens(0) + completion_tokens(1)}


def test_p2_tokens_are_summed_over_the_episode(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "passed_after_tests")
    assert run.episode.outcome == "passed" and run.episode.t == 2
    assert run.episode.meta["tokens"] == {"in": prompt_tokens(0) + prompt_tokens(1), "out": completion_tokens(0) + completion_tokens(1)}


# ---------- P3: what t counts ----------


def test_p3_t_counts_tool_calls_with_the_terminating_submit_included(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    assert play(agent, monkeypatch, "passed").episode.t == 1
    assert play(agent, monkeypatch, "passed_after_tests").episode.t == 2
    assert play(agent, monkeypatch, "failed_after_tests").episode.t == 2
    assert play(agent, monkeypatch, "timed_out").episode.t == HORIZON


def test_p3_an_api_error_episode_counts_the_calls_made_before_the_failure(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "api_error_after_two_calls")
    assert run.episode.outcome == "api_error" and run.episode.t == 2, run.episode
    assert run.episode.meta["retries"] == 3
    assert len(run.requests) == 2 + 4, [q.turn for q in run.requests]
    assert run.episode.meta["tokens"] == {"in": prompt_tokens(0) + prompt_tokens(1), "out": completion_tokens(0) + completion_tokens(1)}
    assert len(tool_spans(trace_of(run.episode))) == 2


def test_p3_a_crashed_episode_counts_the_calls_made_before_the_parse_failure(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # S22 moved the 5xx script above to ``api_error``, which would have left P3 with no
    # ``crashed`` episode that made a tool call first. This is that episode: two run_tests
    # turns, then a reply and its repair turn that neither parse.
    run = play(agent, monkeypatch, "crash_after_two_calls")
    assert run.episode.outcome == "crashed" and run.episode.t == 2, run.episode
    assert run.episode.meta["retries"] == 0
    assert len(run.requests) == 2 + 2, [q.turn for q in run.requests]
    assert len(tool_spans(trace_of(run.episode))) == 2


# ---------- P4: the sandbox inside the boundary ----------


@pytest.mark.parametrize("task_id", [g.task_id for g in GOLDENS])
def test_p4_the_canonical_solution_of_every_mini_suite_golden_passes(sandbox: Any, suite: Any, task_id: str) -> None:
    result = sandbox.run_tests(canonical(task_id), golden_of(suite, task_id))
    assert result.passed is True, result
    assert isinstance(result.reason, str)


@pytest.mark.parametrize("name", ["assertion", "raises", "socket", "long_reason"])
def test_p4_a_bad_candidate_fails_with_a_reason_and_never_raises_into_the_caller(sandbox: Any, suite: Any, name: str) -> None:
    t0 = time.perf_counter()
    result = sandbox.run_tests(bad(name), golden_of(suite, BAD_TASK))
    assert result.passed is False, result
    assert isinstance(result.reason, str) and result.reason.strip(), result
    assert time.perf_counter() - t0 < WALL_CLOCK_S


def test_p4_the_wrong_solution_of_every_golden_fails_its_assertions(sandbox: Any, suite: Any) -> None:
    for golden in GOLDENS:
        result = sandbox.run_tests(wrong(golden.task_id), golden_of(suite, golden.task_id))
        assert result.passed is False and result.reason.strip(), (golden.task_id, result)


def test_p4_a_sleeping_candidate_is_cut_by_the_wall_clock_in_bounded_time(fast_sandbox: Any, suite: Any) -> None:
    t0 = time.perf_counter()
    result = fast_sandbox.run_tests(bad("hangs"), golden_of(suite, BAD_TASK))
    elapsed = time.perf_counter() - t0
    assert result.passed is False and result.reason.strip(), result
    assert elapsed < FAST_WALL_CLOCK_S + HANG_SLACK_S, elapsed
    assert elapsed < HANG_SLEEP_S / 2  # the wall clock ended it, not the candidate's own sleep


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="macOS refuses every finite RLIMIT_AS/DATA/RSS via setrlimit (measured); the limit bites on the Linux image",
)
def test_p4_an_allocating_candidate_is_cut_by_the_memory_limit(sandbox: Any, suite: Any) -> None:
    t0 = time.perf_counter()
    result = sandbox.run_tests(bad("allocates"), golden_of(suite, BAD_TASK))
    assert result.passed is False and result.reason.strip(), result
    assert time.perf_counter() - t0 < WALL_CLOCK_S


def test_p4_the_wall_clock_default_is_ten_seconds(sandbox: Any) -> None:
    assert sandbox.WALL_CLOCK_S == WALL_CLOCK_S


# ---------- P5: determinism ----------


P5_SCRIPT: Script = {(HE0, 41): steps(("run_tests", wrong(HE0)), ("submit", canonical(HE0))), (HE0, 42): steps(("run_tests", wrong(HE0)), ("submit", canonical(HE0)))}


def test_p5_two_rollouts_of_one_cfg_and_seed_send_byte_identical_requests_in_order(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedModel(P5_SCRIPT)
    first = drive(agent, monkeypatch, P5_SCRIPT, task_id=HE0, seed=41, temperature=0.7, model=model)
    second = drive(agent, monkeypatch, P5_SCRIPT, task_id=HE0, seed=41, temperature=0.7, model=model)
    assert first.episode.outcome == second.episode.outcome == "passed" and first.episode.t == 2
    assert len(first.requests) == len(second.requests) == 2
    assert [q.body for q in first.requests] == [q.body for q in second.requests]
    assert first.episode.to_dict()["meta"]["tokens"] == second.episode.to_dict()["meta"]["tokens"]


def test_p5_every_request_carries_the_cfg_temperature_the_seed_the_model_and_a_fixed_max_tokens(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = drive(agent, monkeypatch, P5_SCRIPT, task_id=HE0, seed=41, temperature=0.7)
    bodies = [q.json for q in run.requests]
    assert len(bodies) == 2
    for body in bodies:
        assert body["temperature"] == 0.7, body
        assert body["seed"] == 41, body
        assert body["model"] == MODEL, body
        assert isinstance(body.get("max_tokens"), int) and body["max_tokens"] > 0, body
    assert bodies[0]["max_tokens"] == bodies[1]["max_tokens"]
    assert bodies[0]["messages"] == bodies[1]["messages"][: len(bodies[0]["messages"])]  # the conversation grows, never rewrites


def test_p5_a_different_seed_changes_the_seed_field_and_nothing_else_in_the_first_request(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    a = drive(agent, monkeypatch, P5_SCRIPT, task_id=HE0, seed=41, temperature=0.7)
    b = drive(agent, monkeypatch, P5_SCRIPT, task_id=HE0, seed=42, temperature=0.7)
    first_a, first_b = a.requests[0].json, b.requests[0].json
    assert a.requests[0].body != b.requests[0].body
    assert first_a.pop("seed") == 41 and first_b.pop("seed") == 42
    assert first_a == first_b


# ---------- P6: failure text is truncated before it reaches the model ----------


def test_p6_the_run_tests_result_appended_to_the_conversation_is_at_most_500_characters(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    script = {(BAD_TASK, 51): steps(("run_tests", bad("long_reason")), ("submit", canonical(BAD_TASK)))}
    run = drive(agent, monkeypatch, script, task_id=BAD_TASK, seed=51)
    assert run.episode.outcome == "passed" and run.episode.t == 2, run.episode
    messages = run.requests[1].json["messages"]
    roles = [m.get("role") for m in messages]
    assert "assistant" in roles, roles
    appended = messages[roles.index("assistant") + 1 :]
    assert appended, messages
    for message in appended:
        assert len(text_of(message)) <= REASON_CAP, (len(text_of(message)), text_of(message)[:80])


def test_p6_the_sandbox_reason_is_truncated_to_500_characters(sandbox: Any, suite: Any) -> None:
    result = sandbox.run_tests(bad("long_reason"), golden_of(suite, BAD_TASK))
    assert result.passed is False
    assert 0 < len(result.reason) <= REASON_CAP, len(result.reason)


# ---------- P7: the trace ----------


def test_p7_the_episode_trace_has_an_agent_root_and_tool_spans_with_relative_paths(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = drive(agent, monkeypatch, P5_SCRIPT, task_id=HE0, seed=41, temperature=0.7)
    trace = trace_of(run.episode)
    assert trace.truncated is None and trace.source == "record", (trace.truncated, trace.source)
    roots = trace.roots()
    assert len(roots) == 1 and roots[0].kind == "agent" and roots[0].name == "golden", roots
    root = roots[0]
    tools = tool_spans(trace)
    assert [s.name for s in tools] == ["run_tests", "submit"]
    assert len(tools) == run.episode.t
    for span in tools:
        assert span.parent_id == root.span_id, span
        assert span.end_ns is not None, span
    for span in trace.spans:
        assert span.code is not None, span  # a record() span always carries its code location
        path = str(span.code["filepath"])
        assert not path.startswith("/") and not re.match(r"^[A-Za-z]:\\", path), path
        assert path.startswith("golden_pilot/"), path
    assert all(s.kind in ("agent", "tool") for s in trace.spans), [s.kind for s in trace.spans]


@needs_fork
def test_p7_with_the_instrumentor_every_row_holds_one_stamped_codeless_llm_span_per_model_call(capture_run: dict[str, Any]) -> None:
    r = capture_run
    assert r["summary"]["n_ok"] == len(GOLDENS) and r["summary"]["n_errored"] == 0, r["summary"]
    assert r["capture"] is not None and r["capture"]["active"] is True, r["capture"]
    assert INSTRUMENTOR in r["capture"]["instrumented"], r["capture"]
    calls_by_task: dict[str, int] = {}
    for task_id, _, path in r["requests"]:
        assert path.endswith("/chat/completions"), path
        calls_by_task[task_id] = calls_by_task.get(task_id, 0) + 1
    assert len(r["rows"]) == len(GOLDENS)
    for row in r["rows"]:
        assert row["error"] is None and row["outcome"] == "passed" and row["t"] == 2, row
        trace = Trace.from_dict(row["meta"]["trace"])
        assert trace.source == "mixed" and trace.truncated is None, (trace.source, trace.truncated)
        llm = [s for s in trace.spans if s.kind == "llm"]
        assert len(llm) == calls_by_task[row["task_id"]] == 2, (row["task_id"], len(llm), calls_by_task)
        episode_id = f"{row['config_hash']}:{row['replicate_index']}"
        for span in llm:
            assert span.attrs.get(RUN_ID_KEY) == r["run_id"], (span.name, span.attrs)
            assert span.attrs.get(EPISODE_KEY) == episode_id, (span.name, span.attrs)
            assert span.code is None, span
            assert not any(k in CONTENT_KEYS or k.startswith(CONTENT_PREFIXES) for k in span.attrs), sorted(span.attrs)
        own = [s for s in trace.spans if s.kind != "llm"]
        assert [s.kind for s in trace.ordered() if s.kind != "llm"] == ["agent", "tool", "tool"], own
        for span in own:
            assert span.code is not None and str(span.code["filepath"]).startswith("golden_pilot/"), span


@needs_fork
def test_p7_the_rollouts_own_record_spans_carry_no_stamps_on_the_s15_surface(capture_run: dict[str, Any]) -> None:
    """Measured, not specified: ``EpisodeStamper`` is a SpanProcessor and a ``record()`` span
    never passes through it, and the rollout is never told the run id or the episode id, so
    the stored merged trace has the stamps on the captured spans only. P7's "both stamps on
    every span" is read as every *captured* span. Should the spec want the record spans
    stamped too, the change is a stamping pass in ``executor._merge_capture`` (core, which
    section 6 forbids this session) and exactly this test moves."""
    for row in capture_run["rows"]:
        trace = Trace.from_dict(row["meta"]["trace"])
        for span in trace.spans:
            if span.kind != "llm":
                assert RUN_ID_KEY not in span.attrs and EPISODE_KEY not in span.attrs, (span.name, span.attrs)


# ---------- P8: names, the suite, the sweep files ----------


def test_p8_no_outcome_is_timeout_error_or_empty(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in FORBIDDEN_OUTCOMES:
        assert name not in agent.OUTCOMES
    # S22 re-check of the name list. ``api_error`` *contains* ``error``, so the exclusion
    # has to be of the whole name: a guard spelled as a substring test would reject the
    # fifth outcome. The two readings are pinned apart, and which outcome separates them.
    assert set(agent.OUTCOMES) & set(FORBIDDEN_OUTCOMES) == set(), agent.OUTCOMES
    substring_hits = [o for o in agent.OUTCOMES if any(f and f in o for f in FORBIDDEN_OUTCOMES)]
    assert substring_hits == ["api_error"], substring_hits
    seen = set()
    for name in ("passed", "failed_assertion", "timed_out", "api_error", "garbage"):
        outcome = play(agent, monkeypatch, name).episode.outcome
        assert outcome not in FORBIDDEN_OUTCOMES and outcome in OUTCOMES, (name, outcome)
        seen.add(outcome)
    assert seen == set(OUTCOMES), sorted(seen ^ set(OUTCOMES))  # the five scripts reach the five names


def test_p8_the_mini_suite_loads_with_unique_ids_stable_across_two_loads(suite: Any) -> None:
    first = suite.load(MINI_SUITE)
    second = suite.load(MINI_SUITE)
    assert isinstance(first, tuple) and len(first) == len(GOLDENS) == 3
    ids = [g.task_id for g in first]
    assert ids == [g.task_id for g in second] == [g.task_id for g in GOLDENS]
    assert len(set(ids)) == len(ids)
    for golden, row in zip(first, GOLDENS):
        assert (golden.task_id, golden.prompt, golden.entry_point, golden.canonical_solution, golden.test) == dataclasses.astuple(row)
    assert suite.load() == first  # None means GOLDEN_PILOT_SUITE, which pilot_env points at the fixture


def test_p8_the_real_suite_when_present_has_164_goldens_with_stable_unique_ids(suite: Any) -> None:
    if not REAL_SUITE.is_file():
        pytest.skip(f"the real suite is not fetched: {REAL_SUITE}")
    first = suite.load(REAL_SUITE)
    second = suite.load(REAL_SUITE)
    ids = [g.task_id for g in first]
    assert len(ids) == 164 and len(set(ids)) == 164
    assert ids == [g.task_id for g in second]
    assert all(re.fullmatch(r"HumanEval/\d+", i) for i in ids), ids[:3]


def make_toml(out: Path, suite_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "make_toml.py"), "--suite", str(suite_path), "--out", str(out)],
        capture_output=True, text=True, timeout=120, env=subprocess_env(), cwd=str(REPO),
    )


def axis_values(spec: SweepSpec, axis: str) -> list[Any]:
    seen: list[Any] = []
    for cfg in spec.configs:
        if cfg[axis] not in seen:
            seen.append(cfg[axis])
    return seen


def modal_table(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return dict(tomllib.load(fh))


def assert_pilot_shape(spec: SweepSpec, *, replicates: int, task_ids: Sequence[str], raw: Mapping[str, Any]) -> None:
    assert spec.t_unit == T_UNIT and spec.replicates == replicates
    assert re.fullmatch(r"golden-pilot/.+@v0", spec.target_id), spec.target_id
    assert spec.axis_types == {"task_id": "categorical", "temperature": "continuous"}, spec.axis_types
    assert axis_values(spec, "task_id") == list(task_ids)
    assert axis_values(spec, "temperature") == [0.0, 0.7]
    assert spec.capture is not None, "no [capture] table"
    assert tuple(spec.capture.instrument) == (INSTRUMENTOR,) and spec.capture.content is False, spec.capture
    modal = raw["modal"]
    assert modal["episode_timeout"] == 120.0, modal
    assert modal["concurrency"] == 16 and modal["batch_size"] == 64 and modal["infra_retries"] == 2, modal
    assert modal["image"]["dockerfile"] == "examples/golden_pilot/Dockerfile", modal["image"]
    assert modal["image"]["local_packages"] == ["golden_pilot"], modal["image"]


def test_p8_make_toml_writes_the_task_axis_from_the_suite_and_is_deterministic(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    for out in (first, second):
        done = make_toml(out, MINI_SUITE)
        assert done.returncode == 0, done.stderr
        assert (out / "pilot.toml").is_file() and (out / "smoke.toml").is_file(), sorted(p.name for p in out.iterdir())
    assert (first / "pilot.toml").read_bytes() == (second / "pilot.toml").read_bytes()
    assert (first / "smoke.toml").read_bytes() == (second / "smoke.toml").read_bytes()
    ids = [g.task_id for g in GOLDENS]
    pilot = SweepSpec.load(first / "pilot.toml")
    assert_pilot_shape(pilot, replicates=32, task_ids=ids, raw=modal_table(first / "pilot.toml"))
    smoke = SweepSpec.load(first / "smoke.toml")
    assert_pilot_shape(smoke, replicates=2, task_ids=ids[:5], raw=modal_table(first / "smoke.toml"))


def test_p8_make_toml_over_the_real_suite_reproduces_the_committed_task_axis(tmp_path: Path) -> None:
    if not REAL_SUITE.is_file():
        pytest.skip(f"the real suite is not fetched: {REAL_SUITE}")
    done = make_toml(tmp_path, REAL_SUITE)
    assert done.returncode == 0, done.stderr
    for name in ("pilot.toml", "smoke.toml"):
        generated, committed = SweepSpec.load(tmp_path / name), SweepSpec.load(ROOT / name)
        assert axis_values(generated, "task_id") == axis_values(committed, "task_id"), name


def test_p8_pilot_toml_parses_as_the_spec_sweep() -> None:
    path = ROOT / "pilot.toml"
    assert path.is_file(), path
    spec = SweepSpec.load(path)
    ids = axis_values(spec, "task_id")
    assert len(ids) == 164 and len(set(ids)) == 164, len(ids)
    assert all(re.fullmatch(r"HumanEval/\d+", i) for i in ids), ids[:3]
    assert_pilot_shape(spec, replicates=32, task_ids=ids, raw=modal_table(path))
    assert spec.total_rollouts() == 164 * 2 * 32 == 10_496
    assert spec.retain_traces_for is None  # every row keeps its trace: numbers.py reads them all


def test_p8_smoke_toml_has_the_same_shape_over_five_tasks_at_two_replicates() -> None:
    path = ROOT / "smoke.toml"
    assert path.is_file(), path
    smoke = SweepSpec.load(path)
    pilot = SweepSpec.load(ROOT / "pilot.toml")
    ids = axis_values(smoke, "task_id")
    assert len(ids) == 5 and ids == axis_values(pilot, "task_id")[:5], ids
    assert_pilot_shape(smoke, replicates=2, task_ids=ids, raw=modal_table(path))
    assert smoke.total_rollouts() == 5 * 2 * 2 == 20
    assert smoke.target_id == pilot.target_id


# ---------- P9: numbers.py on a hand-built store ----------

RUN_A = "pilot-A"
RUN_A2 = "pilot-Aprime"
TARGET_ID = f"golden-pilot/{MODEL}@v0"
AXIS_TYPES: dict[str, Any] = {"task_id": "categorical", "temperature": "continuous"}
CELLS: dict[str, dict[str, Any]] = {
    "c0": {"task_id": HE0, "temperature": 0.0},
    "c1": {"task_id": HE2, "temperature": 0.0},
    "c2": {"task_id": HE0, "temperature": 0.7},
    "c3": {"task_id": HE2, "temperature": 0.7},
}
CELL_HASH = {name: config_hash(cfg) for name, cfg in CELLS.items()}
CRASH_LAST_LINE = "RuntimeError: boom"
CRASH_TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "golden_pilot/agent.py", line 3, in rollout\n'
    '    raise RuntimeError("boom")\n'
    f"{CRASH_LAST_LINE}\n"
)
DICT_ERROR = "rollout returned dict, expected Episode"
TIMEOUT_ERROR = "timeout"
RELATIVE_CODE = {"filepath": "golden_pilot/agent.py", "function": "rollout", "lineno": 10}


class Ids:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"{self.n:016x}"


def stamps(run_id: str, cell: str, k: int) -> dict[str, str]:
    return {RUN_ID_KEY: run_id, EPISODE_KEY: f"{CELL_HASH[cell]}:{k}"}


def episode_trace(
    run_id: str, cell: str, k: int, *, tools: int, llms: int, other: int = 0, dropped: int = 0, unstamped_llm: bool = False
) -> dict[str, Any]:
    """An ok row's merged trace: one ``agent`` root, ``tools`` tool spans (run_tests then
    submit last), ``llms`` llm spans, ``other`` spans of kind ``other``; every span stamped
    unless ``unstamped_llm`` strips the stamps from the first llm span."""
    ids = Ids()
    attrs = stamps(run_id, cell, k)
    root_id = ids()
    n = tools + llms + other
    spans = [Span(root_id, None, "agent", "golden", EPOCH, EPOCH + (n + 2) * STEP_NS, code=RELATIVE_CODE, attrs=attrs)]
    clock = EPOCH + STEP_NS
    for i in range(tools):
        name = "submit" if i == tools - 1 and tools > 1 else "run_tests"
        spans.append(Span(ids(), root_id, "tool", name, clock, clock + STEP_NS, code=RELATIVE_CODE, attrs=attrs))
        clock += STEP_NS
    for i in range(llms):
        llm_attrs = {} if (unstamped_llm and i == 0) else attrs
        spans.append(Span(ids(), root_id, "llm", f"chat {MODEL}", clock, clock + STEP_NS, tokens={"in": 100, "out": 10}, attrs=llm_attrs))
        clock += STEP_NS
    for _ in range(other):
        spans.append(Span(ids(), root_id, "other", "something.unmapped", clock, clock + STEP_NS, attrs=attrs))
        clock += STEP_NS
    return Trace(spans=tuple(spans), source="mixed", dropped=dropped).to_dict()


def timeout_trace(run_id: str, cell: str, k: int) -> dict[str, Any]:
    """S16's shape: the root and a tool still open at the kill, one llm span closed, cut."""
    ids = Ids()
    attrs = stamps(run_id, cell, k)
    root_id = ids()
    spans = (
        Span(root_id, None, "agent", "golden", EPOCH, None, code=RELATIVE_CODE, attrs=attrs),
        Span(ids(), root_id, "llm", f"chat {MODEL}", EPOCH + STEP_NS, EPOCH + 2 * STEP_NS, attrs=attrs),
        Span(ids(), root_id, "tool", "run_tests", EPOCH + 3 * STEP_NS, None, code=RELATIVE_CODE, attrs=attrs),
    )
    return Trace(spans=spans, source="mixed", truncated=TIMEOUT_ERROR).to_dict()


def crash_trace(run_id: str, cell: str, k: int) -> dict[str, Any]:
    """S17's shape: complete, the failing tool span marked and the root it unwound through."""
    ids = Ids()
    attrs = stamps(run_id, cell, k)
    root_id = ids()
    spans = (
        Span(root_id, None, "agent", "golden", EPOCH, EPOCH + 4 * STEP_NS, error=CRASH_LAST_LINE, code=RELATIVE_CODE, attrs=attrs),
        Span(ids(), root_id, "llm", f"chat {MODEL}", EPOCH + STEP_NS, EPOCH + 2 * STEP_NS, attrs=attrs),
        Span(ids(), root_id, "tool", "run_tests", EPOCH + 3 * STEP_NS, EPOCH + 4 * STEP_NS, error=CRASH_LAST_LINE, code=RELATIVE_CODE, attrs=attrs),
    )
    return Trace(spans=spans, source="mixed").to_dict()


def ok_row(run_id: str, cell: str, k: int, seed: int, outcome: str, t: float, trace: dict[str, Any] | None) -> EpisodeRecord:
    meta: dict[str, Any] = {"task_id": CELLS[cell]["task_id"], "crash_reason": None, "retries": 0, "tokens": {"in": 0, "out": 0}}
    if trace is not None:
        meta["trace"] = trace
    return EpisodeRecord(
        run_id=run_id, config_hash=CELL_HASH[cell], config=dict(CELLS[cell]), seed=seed, replicate_index=k,
        outcome=outcome, t=float(t), horizon=float(HORIZON), confidence=None, meta=meta, error=None,
        wall_time=1.0, backend_meta={"i": k},
    )


def errored_row(run_id: str, cell: str, k: int, seed: int, error: str, trace: dict[str, Any] | None) -> EpisodeRecord:
    return EpisodeRecord.errored(
        run_id=run_id, config=dict(CELLS[cell]), seed=seed, replicate_index=k, error=error, wall_time=1.0,
        backend_meta={"i": k}, meta=None if trace is None else {"trace": trace},
    )


def rows_a() -> list[EpisodeRecord]:
    """Run A: 11 ok rows and 3 errored rows, laid out so every number below is hand arithmetic.

    ok rows (cell, k, seed, outcome, t, tools, llms, other, dropped):
      c0  0    0  passed            2  2 2           <- c0 is the cell with zero failure events
      c0  1    1  passed            2  2 2
      c0  2    2  passed            1  1 1
      c1  0 1000  failed_assertion  3  3 3
      c1  1 1001  passed            2  2 2
      c2  0 2000  timed_out         6  6 6  +1 other, dropped 1
      c2  1 2001  passed            2  2 2
      c2  2 2002  crashed           1  1 2
      c2  3 2003  passed            7  7 7           <- VIOLATION: t > horizon
      c3  2 3002  "timeout"         6  6 6  +1 other, dropped 2   <- VIOLATION: S16's collision as an outcome
      c3  3 3003  passed            2  2 2  first llm span unstamped   <- VIOLATION: a stamp missing
    errored rows: c1 k2 seed 1002 "timeout" with a truncated trace; c3 k0 seed 3000 a traceback
    with a complete marked trace; c3 k1 seed 3001 "rollout returned dict, expected Episode"
    with no trace.
    """
    a = RUN_A
    return [
        ok_row(a, "c0", 0, 0, "passed", 2, episode_trace(a, "c0", 0, tools=2, llms=2)),
        ok_row(a, "c0", 1, 1, "passed", 2, episode_trace(a, "c0", 1, tools=2, llms=2)),
        ok_row(a, "c0", 2, 2, "passed", 1, episode_trace(a, "c0", 2, tools=1, llms=1)),
        ok_row(a, "c1", 0, 1000, "failed_assertion", 3, episode_trace(a, "c1", 0, tools=3, llms=3)),
        ok_row(a, "c1", 1, 1001, "passed", 2, episode_trace(a, "c1", 1, tools=2, llms=2)),
        errored_row(a, "c1", 2, 1002, TIMEOUT_ERROR, timeout_trace(a, "c1", 2)),
        ok_row(a, "c2", 0, 2000, "timed_out", 6, episode_trace(a, "c2", 0, tools=6, llms=6, other=1, dropped=1)),
        ok_row(a, "c2", 1, 2001, "passed", 2, episode_trace(a, "c2", 1, tools=2, llms=2)),
        ok_row(a, "c2", 2, 2002, "crashed", 1, episode_trace(a, "c2", 2, tools=1, llms=2)),
        ok_row(a, "c2", 3, 2003, "passed", 7, episode_trace(a, "c2", 3, tools=7, llms=7)),
        errored_row(a, "c3", 0, 3000, CRASH_TRACEBACK, crash_trace(a, "c3", 0)),
        errored_row(a, "c3", 1, 3001, DICT_ERROR, None),
        ok_row(a, "c3", 2, 3002, "timeout", 6, episode_trace(a, "c3", 2, tools=6, llms=6, other=1, dropped=2)),
        ok_row(a, "c3", 3, 3003, "passed", 2, episode_trace(a, "c3", 3, tools=2, llms=2, unstamped_llm=True)),
    ]


def rows_a2() -> list[EpisodeRecord]:
    """Run A': the same triples with a few outcomes changed, one extra triple A never ran
    (c0 k3), and one at a triple A errored on (c1 k2), neither of which may pair."""
    b = RUN_A2
    small = episode_trace(b, "c0", 0, tools=1, llms=1)
    return [
        ok_row(b, "c0", 0, 0, "passed", 1, small),
        ok_row(b, "c0", 1, 1, "passed", 1, small),
        ok_row(b, "c0", 2, 2, "passed", 1, small),
        ok_row(b, "c0", 3, 3, "passed", 1, small),
        ok_row(b, "c1", 0, 1000, "failed_assertion", 1, small),
        ok_row(b, "c1", 1, 1001, "failed_assertion", 1, small),
        ok_row(b, "c1", 2, 1002, "passed", 1, small),
        ok_row(b, "c2", 0, 2000, "timed_out", 6, small),
        ok_row(b, "c2", 1, 2001, "passed", 1, small),
        ok_row(b, "c2", 2, 2002, "passed", 1, small),
        ok_row(b, "c2", 3, 2003, "passed", 1, small),
        ok_row(b, "c3", 2, 3002, "timed_out", 6, small),
        ok_row(b, "c3", 3, 3003, "passed", 1, small),
    ]


@pytest.fixture(scope="module")
def pilot_store(tmp_path_factory: pytest.TempPathFactory) -> Store:
    store = Store(tmp_path_factory.mktemp("pilot-store"))
    for run_id in (RUN_A, RUN_A2):
        store.create_run(
            RunManifest(run_id=run_id, target_id=TARGET_ID, t_unit=T_UNIT, run_salt="paired-salt", axis_types=AXIS_TYPES, backend="local", environment={})
        )
    assert store.append(RUN_A, rows_a()) == 14
    assert store.append(RUN_A2, rows_a2()) == 13
    return store


@pytest.fixture(scope="module")
def numbers_module() -> Any:
    return importlib.import_module("golden_pilot.numbers")


@pytest.fixture(scope="module")
def numbers_a(numbers_module: Any, pilot_store: Store) -> dict[str, Any]:
    out = numbers_module.numbers(pilot_store, RUN_A, paired_with=RUN_A2)
    assert isinstance(out, dict)
    return out


def approx(fraction: Fraction) -> Any:
    return pytest.approx(float(fraction), abs=1e-12)


def test_p9_the_three_numbers_and_the_kind_histogram(numbers_a: dict[str, Any]) -> None:
    n = numbers_a
    assert n["run_id"] == RUN_A
    assert (n["rows"], n["ok_rows"], n["errored_rows"]) == (14, 11, 3)
    # spans per ok row: 5 5 3 | 7 5 | 14 5 4 15 | 14 5  (root + tools + llms + other)
    assert n["spans"] == 5 + 5 + 3 + 7 + 5 + 14 + 5 + 4 + 15 + 14 + 5 == 82
    assert n["dropped"] == 1 + 2 == 3
    assert n["kinds"] == {"llm": 35, "tool": 34, "retrieval": 0, "db": 0, "http": 0, "agent": 11, "other": 2}
    assert set(n["kinds"]) == set(KINDS)
    assert sum(n["kinds"].values()) == n["spans"]
    assert n["other_share"] == approx(Fraction(2, 82))
    assert n["tool_share"] == approx(Fraction(34, 82))


def test_p9_contract_survival_counts_the_three_violations(numbers_a: dict[str, Any]) -> None:
    contract = numbers_a["contract"]
    # 11 ok rows; t > horizon (c2 k3), outcome "timeout" (c3 k2), an unstamped llm span (c3 k3)
    assert (contract["rows"], contract["survived"], contract["failed"]) == (11, 8, 3), contract


def test_p9_the_errored_row_rate_split_by_text_and_by_trace_presence(numbers_a: dict[str, Any]) -> None:
    errored = numbers_a["errored"]
    assert errored["rows"] == 3
    assert errored["rate"] == approx(Fraction(3, 14))
    assert errored["by_error"] == {TIMEOUT_ERROR: 1, CRASH_LAST_LINE: 1, DICT_ERROR: 1}, errored["by_error"]
    assert (errored["with_trace"], errored["without_trace"]) == (2, 1), errored


def test_p9_zero_n_holes_over_cells_and_the_four_failure_events(numbers_a: dict[str, Any]) -> None:
    zero_n = numbers_a["zero_n"]
    assert zero_n["cells"] == 4
    assert list(zero_n["events"]) == list(FAILURE_EVENTS)
    # Recomputed by hand over the four events of S22, from the ok-row outcomes rows_a()
    # spells: c0 {passed}, c1 {failed_assertion, passed}, c2 {timed_out, passed, crashed},
    # c3 {"timeout", passed}. No cell produced an api_error, so every cell holes on it.
    # c0: 4 holes; c1: 3; c2: 2; c3: "timeout" is not an event -> 4.  4 + 3 + 2 + 4 = 13,
    # and cells x events - holes = 4 x 4 - 13 = 3, the three (cell, event) pairs seen.
    expected = {
        (CELL_HASH["c0"], "failed_assertion"), (CELL_HASH["c0"], "timed_out"), (CELL_HASH["c0"], "crashed"), (CELL_HASH["c0"], "api_error"),
        (CELL_HASH["c1"], "timed_out"), (CELL_HASH["c1"], "crashed"), (CELL_HASH["c1"], "api_error"),
        (CELL_HASH["c2"], "failed_assertion"), (CELL_HASH["c2"], "api_error"),
        (CELL_HASH["c3"], "failed_assertion"), (CELL_HASH["c3"], "timed_out"), (CELL_HASH["c3"], "crashed"), (CELL_HASH["c3"], "api_error"),
    }
    assert len(expected) == 4 * len(FAILURE_EVENTS) - 3 == 13
    holes = {(str(cell), str(event)) for cell, event in zero_n["holes"]}
    assert holes == expected and zero_n["count"] == 13 == len(zero_n["holes"]), sorted(holes ^ expected)


def test_p9_pairing_agreement_and_kappa_against_the_second_run(numbers_a: dict[str, Any]) -> None:
    pairing = numbers_a["pairing"]
    assert pairing["paired_with"] == RUN_A2
    assert pairing["triples"] == 11  # A's 11 ok rows; A' extra c0 k3 and errored-in-A c1 k2 never pair
    # temperature 0.0, five triples: seeds 0 1 2 agree, 1000 agrees, 1001 differs -> 4/5
    # temperature 0.7, six triples: 2000 2001 2003 3003 agree, 2002 and 3002 differ -> 4/6
    assert pairing["agreement"]["by_temperature"]["0.0"] == approx(Fraction(4, 5))
    assert pairing["agreement"]["by_temperature"]["0.7"] == approx(Fraction(4, 6))
    assert pairing["agreement"]["all"] == approx(Fraction(8, 11))
    # Cohen's kappa = (p_o - p_e) / (1 - p_e), p_e = sum over labels of pA * pA'
    # 0.0: A passed 4/5 fa 1/5; A' passed 3/5 fa 2/5; p_e = 12/25 + 2/25 = 14/25; p_o = 4/5
    kappa_00 = (Fraction(4, 5) - Fraction(14, 25)) / (1 - Fraction(14, 25))
    assert kappa_00 == Fraction(6, 11)
    # 0.7: A timed_out 1/6 passed 3/6 crashed 1/6 "timeout" 1/6; A' timed_out 2/6 passed 4/6
    #      p_e = 2/36 + 12/36 = 14/36; p_o = 4/6
    kappa_07 = (Fraction(4, 6) - Fraction(14, 36)) / (1 - Fraction(14, 36))
    assert kappa_07 == Fraction(5, 11)
    # all: A passed 7 fa 1 timed_out 1 crashed 1 "timeout" 1 of 11; A' passed 7 fa 2 timed_out 2
    #      p_e = (49 + 2 + 2) / 121 = 53/121; p_o = 8/11 = 88/121
    kappa_all = (Fraction(88, 121) - Fraction(53, 121)) / (1 - Fraction(53, 121))
    assert kappa_all == Fraction(35, 68)
    assert pairing["kappa"]["by_temperature"]["0.0"] == approx(kappa_00)
    assert pairing["kappa"]["by_temperature"]["0.7"] == approx(kappa_07)
    assert pairing["kappa"]["all"] == approx(kappa_all)


def test_p9_without_paired_with_the_pairing_block_is_none_and_the_rest_is_unchanged(numbers_module: Any, pilot_store: Store, numbers_a: dict[str, Any]) -> None:
    alone = numbers_module.numbers(pilot_store, RUN_A)
    assert alone["pairing"] is None
    for key in ("run_id", "rows", "ok_rows", "errored_rows", "spans", "dropped", "kinds", "other_share", "tool_share", "contract", "errored", "zero_n"):
        assert alone[key] == numbers_a[key], key


def test_p9_the_numbers_dict_has_exactly_the_pinned_keys(numbers_a: dict[str, Any]) -> None:
    assert set(numbers_a) == {
        "run_id", "rows", "ok_rows", "errored_rows", "spans", "dropped", "kinds", "other_share", "tool_share",
        "contract", "errored", "zero_n", "pairing",
    }, sorted(numbers_a)
    assert set(numbers_a["contract"]) >= {"rows", "survived", "failed"}
    assert set(numbers_a["errored"]) >= {"rows", "rate", "by_error", "with_trace", "without_trace"}
    assert set(numbers_a["zero_n"]) >= {"cells", "events", "count", "holes"}
    assert set(numbers_a["pairing"]) >= {"paired_with", "triples", "agreement", "kappa"}
    json.dumps(numbers_a)  # the devlog record: JSON-native throughout


# ---------- P10: the patch ----------

P10_SUBMIT_FIRST: Script = {(HE3, 61): steps(("submit", canonical(HE3)), ("run_tests", canonical(HE3)), ("submit", canonical(HE3)))}
P10_TESTS_FIRST: Script = {(HE3, 62): steps(("run_tests", canonical(HE3)), ("submit", canonical(HE3)))}


def test_p10_rollout_patched_refuses_a_submit_no_run_tests_preceded_and_spends_one_call_on_it(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    patched = drive(agent, monkeypatch, P10_SUBMIT_FIRST, task_id=HE3, seed=61, patched=True)
    assert patched.episode.outcome == "passed", patched.episode
    assert patched.episode.t == 3, patched.episode.t  # the refusal, the run_tests, the accepted submit
    assert len(patched.requests) == 3, [q.turn for q in patched.requests]
    tools = tool_spans(trace_of(patched.episode))
    assert [s.name for s in tools] == ["submit", "run_tests", "submit"], tools
    plain = drive(agent, monkeypatch, P10_SUBMIT_FIRST, task_id=HE3, seed=61, patched=False)
    assert plain.episode.outcome == "passed" and plain.episode.t == 1, plain.episode


def test_p10_rollout_patched_matches_rollout_byte_for_byte_up_to_the_refused_turn(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedModel(P10_SUBMIT_FIRST)
    plain = drive(agent, monkeypatch, P10_SUBMIT_FIRST, task_id=HE3, seed=61, patched=False, model=model)
    patched = drive(agent, monkeypatch, P10_SUBMIT_FIRST, task_id=HE3, seed=61, patched=True, model=model)
    assert plain.requests[0].body == patched.requests[0].body
    assert len(plain.requests) == 1 and len(patched.requests) == 3
    # After the refusal the conversation diverges by exactly the refusal exchange.
    second = patched.requests[1].json["messages"]
    first = patched.requests[0].json["messages"]
    assert second[: len(first)] == first and len(second) > len(first)


def test_p10_rollout_patched_accepts_submit_after_run_tests_and_is_otherwise_identical(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedModel(P10_TESTS_FIRST)
    plain = drive(agent, monkeypatch, P10_TESTS_FIRST, task_id=HE3, seed=62, patched=False, model=model)
    patched = drive(agent, monkeypatch, P10_TESTS_FIRST, task_id=HE3, seed=62, patched=True, model=model)
    assert plain.episode.outcome == patched.episode.outcome == "passed"
    assert plain.episode.t == patched.episode.t == 2
    assert [q.body for q in plain.requests] == [q.body for q in patched.requests]
    assert plain.episode.to_dict()["meta"]["tokens"] == patched.episode.to_dict()["meta"]["tokens"]


# ---------- P11 / A24 W1-W7: chat completions only, openai 2 ----------


def test_w1_requirements_pin_openai_2_and_name_the_instrumentor_and_proofload() -> None:
    """A24 W1, amending P11's first clause. **Red on Session A's commit**: the file still says
    ``openai<2``. The boundary moved by one major version and not by a whole ecosystem -- no
    openai 2.x ever shipped ``httpx2`` (1.109.1, 2.0.0, 2.9.0, 2.20.0 and 2.54.0 all require
    ``httpx<1``), and the instrumentor's hard ``from httpx import URL`` bites at openai 3.0.0.
    So 2.54.0 is admitted, 3.0.0 is not, and 1.109.1 -- the version the original pin was read
    against -- is now excluded rather than required."""
    from packaging.requirements import Requirement
    from packaging.version import Version

    path = ROOT / "requirements.txt"
    assert path.is_file(), path
    lines = [ln.strip() for ln in path.read_text().splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    by_name: dict[str, Any] = {}
    for line in lines:
        try:
            req = Requirement(line)
        except Exception:  # noqa: BLE001 - an editable/path line is not a PEP 508 requirement
            continue
        by_name[req.name.lower()] = req
    assert "openai" in by_name, lines
    openai_spec = by_name["openai"].specifier
    assert str(openai_spec), "openai is unpinned"
    assert Version("2.20.0") in openai_spec and Version("2.54.0") in openai_spec, str(openai_spec)
    assert Version("1.109.1") not in openai_spec, str(openai_spec)
    assert Version("3.0.0") not in openai_spec, str(openai_spec)
    assert "opentelemetry-instrumentation-openai-v2" in by_name, sorted(by_name)
    assert any("proofload" in line for line in lines), lines


def test_w2_pyproject_agent_and_all_carry_openai_2_and_leave_litellm_unbounded() -> None:
    """A24 W2. **Red on Session A's commit**: both extras still say ``openai<2``. ``litellm``
    stays unbounded, as C12 left it -- the floor here is litellm 1.100.1's own ``openai>=2.20``,
    which is above verifiers 0.3.1's ``>=2.9.0``, so one number satisfies both and litellm needs
    no bound of its own."""
    from packaging.requirements import Requirement
    from packaging.version import Version

    extras = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["optional-dependencies"]
    for name in ("agent", "all"):
        by_name = {Requirement(d).name.lower(): Requirement(d) for d in extras[name]}
        assert "openai" in by_name, (name, sorted(by_name))
        spec = by_name["openai"].specifier
        assert Version("2.20.0") in spec, (name, str(spec))
        assert Version("3.0.0") not in spec, (name, str(spec))
        assert "litellm" in by_name, (name, sorted(by_name))
        assert not str(by_name["litellm"].specifier), (name, str(by_name["litellm"].specifier))


def test_w3_the_installed_openai_is_major_2() -> None:
    """A24 W3, amending P11's second clause. **Red on Session A's commit, and no source edit
    clears it** -- it is a statement about the machine, not about the repo, and it goes green
    when the venv is reinstalled. It is kept in that uncomfortable shape because the pin it
    guards is a claim about what is *installed* beside the instrumentor, which no file-reading
    test can make (spec section 10 Q6). It fails on the **version**; W6 and W7 skip on the
    **import**, so an absent instrumentor and a wrong SDK never look the same in the red set."""
    from packaging.version import Version

    installed = Version(importlib.metadata.version("openai"))
    assert installed.major == 2, installed


def test_w6_one_scripted_chat_completion_emits_one_span_with_the_nine_attributes() -> None:
    """A24 W6. **Green before and after** -- it pins the measured *equality* of the
    instrumentor's span across openai 1.109.1 and 2.54.0 (spec section 3.7), so a later
    instrumentor bump that changes the attribute set is caught here and not in a stored trace.
    Measured green on 1.109.1, 2026-09-13; its openai 2 half is Session B's, after the
    reinstall."""
    instrumentor_or_skip()
    spans = isolated(child_instrumented_spans, "chat")
    assert len(spans) == 1, spans
    assert spans[0]["name"] == f"chat {MODEL}", spans[0]["name"]
    assert spans[0]["attributes"] == INSTRUMENTOR_ATTRIBUTES, spans[0]["attributes"]


def test_w7_a_scripted_responses_call_emits_no_span_at_all() -> None:
    """A24 W7, and spec section 10 Q5's measurement. **Green before and after**: the gap the
    pilot's comment names, measured against openai 1.109.1 on 2026-09-04 and re-measured here
    2026-09-13 -- still zero. Q5's other half is openai 2, which only the reinstall reaches, so
    Session B owes that measurement from this clause. **If the gap has closed, this test is
    inverted and the pilot's comment and README gap 1 are amended -- not deleted.**"""
    instrumentor_or_skip()
    assert isolated(child_instrumented_spans, "responses") == [], "the instrumentor now traces responses"


def test_p11_the_requests_of_a_full_episode_go_to_chat_completions_only(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = drive(agent, monkeypatch, P5_SCRIPT, task_id=HE0, seed=41, temperature=0.7)
    assert run.requests, "no request reached the transport"
    for q in run.requests:
        assert q.method == "POST" and q.path.endswith("/chat/completions"), (q.method, q.path)
        assert "/responses" not in q.path and "/embeddings" not in q.path, q.path


# ---------- P12: core is untouched, the pilot imports five names ----------


def test_p12_the_pilot_tree_has_the_eleven_files_of_section_2() -> None:
    missing = [name for name in PILOT_FILES if not (ROOT / name).is_file()]
    assert not missing, (ROOT, missing)


def test_p12_core_public_surfaces_are_what_s17_left_them() -> None:
    pytest.importorskip("opentelemetry.sdk", reason="proofload.otel imports the SDK")
    import proofload.capture as capture_module
    import proofload.executor as executor_module
    import proofload.executor_modal as modal_module
    import proofload.otel as otel_module
    import proofload.trace as trace_module

    top = {n for n, v in vars(proofload).items() if not n.startswith("_") and not isinstance(v, types.ModuleType)}
    assert top == INIT_PUBLIC, sorted(top ^ INIT_PUBLIC)
    assert _defined(executor_module) == EXECUTOR_PUBLIC, sorted(_defined(executor_module) ^ EXECUTOR_PUBLIC)
    assert _defined(modal_module) == MODAL_PUBLIC, sorted(_defined(modal_module) ^ MODAL_PUBLIC)
    assert list(modal_module.__all__) == MODAL_EXPORTS, modal_module.__all__
    assert set(capture_module.__all__) == PUBLIC_CAPTURE and _defined(capture_module) == PUBLIC_CAPTURE
    assert list(trace_module.__all__) == TRACE_EXPORTS, trace_module.__all__
    assert list(otel_module.__all__) == OTEL_EXPORTS, otel_module.__all__


def _imports(path: Path) -> Iterator[tuple[str, str | None, list[str]]]:
    """``("import", module, [])`` and ``("from", module, names)`` for every import in a file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield "import", alias.name, []
        elif isinstance(node, ast.ImportFrom):
            yield "from", node.module, [alias.name for alias in node.names]


def test_p12_nothing_under_src_proofload_imports_examples() -> None:
    files = sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)
    assert files
    for path in files:
        for _, module, _names in _imports(path):
            top = (module or "").split(".")[0]
            assert top not in ("examples", "golden_pilot"), (path, module)
        assert "golden_pilot" not in path.read_text(encoding="utf-8"), path


def test_p12_nothing_under_src_proofload_names_the_pilots_api_error_outcome() -> None:
    """Q8, first half. ``api_error`` is a pilot outcome and core never learns the name.

    A source scan and not an ``ast`` walk, deliberately: the invariant is about the
    *string*, so a mention in a docstring, a comment or a hard-coded branch is a violation
    on the same footing as an identifier. Core stays a tool that reads whatever outcome a
    target emits; the moment it spells one of the pilot's, it has a favourite.
    """
    files = sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)
    assert files
    offenders = [str(p) for p in files if "api_error" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders


def test_p12_golden_pilot_imports_only_episode_record_collect_step_trace_and_store_from_proofload() -> None:
    files = pilot_python_files()
    assert files, ROOT
    used: set[str] = set()
    for path in files:
        for kind, module, names in _imports(path):
            top = (module or "").split(".")[0]
            if top != "proofload":
                continue
            assert kind == "from", (path, module)  # a bare `import proofload` would reach anything
            assert module in ALLOWED_MODULES, (path, module)
            assert "*" not in names, (path, module)
            unexpected = set(names) - ALLOWED_IMPORTS
            assert not unexpected, (path, module, sorted(unexpected))
            used.update(names)
    assert used <= ALLOWED_IMPORTS, sorted(used)
    assert "Episode" in used and "record" in used and "collect" in used, sorted(used)


def test_p12_the_wheel_and_the_extras_are_unchanged() -> None:
    with (REPO / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)
    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/proofload"]
    assert set(pyproject["project"]["optional-dependencies"]) == {"modal", "agent", "viz", "all", "dev"}
    assert "openai" not in str(pyproject["project"]["dependencies"])


# ---------- P13: the boundary ----------


def import_agent(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", "import golden_pilot.agent"],
        env=env, capture_output=True, text=True, timeout=120, cwd=str(REPO),
    )


@pytest.mark.parametrize("value", [None, "local", "Container", ""])
def test_p13_importing_the_agent_without_the_boundary_raises_naming_the_variable_and_the_dockerfile(value: str | None) -> None:
    env = subprocess_env() if value is None else subprocess_env(**{BOUNDARY_VAR: value})
    done = import_agent(env)
    assert done.returncode != 0, (value, done.stdout, done.stderr)
    last = done.stderr.rstrip().splitlines()[-1] if done.stderr.strip() else ""
    assert last.startswith("RuntimeError"), (value, done.stderr)
    assert BOUNDARY_VAR in done.stderr and "Dockerfile" in done.stderr, (value, done.stderr)


def test_p13_with_the_boundary_set_the_import_succeeds() -> None:
    done = import_agent(subprocess_env(**{BOUNDARY_VAR: BOUNDARY_VALUE}))
    assert done.returncode == 0, done.stderr


def test_p13_only_the_agent_module_refuses_without_the_boundary() -> None:
    done = subprocess.run(
        [sys.executable, "-c", "import golden_pilot.suite, golden_pilot.sandbox, golden_pilot.numbers"],
        env=subprocess_env(), capture_output=True, text=True, timeout=120, cwd=str(REPO),
    )
    assert done.returncode == 0, done.stderr


def test_p13_in_process_the_fixture_sets_the_boundary_and_the_agent_imports(agent: Any) -> None:
    assert os.environ[BOUNDARY_VAR] == BOUNDARY_VALUE
    assert callable(agent.rollout) and callable(agent.rollout_patched)


ASSIGNMENT_PATTERNS = (
    re.compile(r"^\s*(export\s+|ENV\s+|set\s+)?" + BOUNDARY_VAR + r"\s*="),  # shell, Dockerfile, TOML, .env at line start
    re.compile(r"(?:^|[\s`'\"(;&|])(?:export|set)\s+" + BOUNDARY_VAR + r"\s*="),  # `export X=...` anywhere, a README included
    re.compile(r"(?:^|[\s`'\"(;&|])(?:-e|--env)[\s=]+" + BOUNDARY_VAR + r"="),  # docker run -e
    re.compile(BOUNDARY_VAR + r"=\S+\s+\S*(?:proofload|python|pytest)\b"),  # the env-prefix form: `X=container proofload sweep ...`
    re.compile(r"environ\s*\[\s*['\"]" + BOUNDARY_VAR + r"['\"]\s*\]\s*=(?!=)"),  # os.environ[...] =
    re.compile(r"(?:setdefault|putenv)\(\s*['\"]" + BOUNDARY_VAR + r"['\"]"),
    re.compile(r"['\"]" + BOUNDARY_VAR + r"['\"]\s*:\s*['\"]"),  # a dict literal handed to environ.update / env=
)


def assignments_in(root: Path, *, skip: Sequence[Path] = ()) -> list[tuple[Path, int, str]]:
    found: list[tuple[Path, int, str]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if "__pycache__" in path.parts or path in skip or path.suffix in (".gz", ".parquet", ".pyc"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if BOUNDARY_VAR in line and any(p.search(line) for p in ASSIGNMENT_PATTERNS):
                found.append((path, i, line.strip()))
    return found


def test_p13_the_dockerfile_sets_the_boundary_and_nothing_else_under_the_pilot_or_src_assigns_it() -> None:
    dockerfile = ROOT / "Dockerfile"
    assert dockerfile.is_file(), dockerfile
    lines = [ln.strip() for ln in dockerfile.read_text().splitlines()]
    assert lines.count(ENV_LINE) == 1, [ln for ln in lines if BOUNDARY_VAR in ln]
    assert [ln for ln in lines if BOUNDARY_VAR in ln and not ln.startswith("#")] == [ENV_LINE]
    assert assignments_in(ROOT, skip=(dockerfile,)) == []
    assert assignments_in(PACKAGE) == []


def test_p13_the_agent_reads_the_boundary_from_the_environment_at_import() -> None:
    source = (ROOT / "agent.py").read_text(encoding="utf-8")
    assert BOUNDARY_VAR in source and "Dockerfile" in source and "RuntimeError" in source


# ---------- S22: Q1-Q13, `api_error` as a first-class pilot outcome ----------
#
# One plain assertion per invariant. The seven S12 oracle defects all lived inside clever
# helpers, so this block repeats itself where a helper would have been shorter.

API_TEXT_MARKERS = ("api error", "apierror", "infra:")  # what an API-error message can contain
VOCABULARY = ("OUTCOMES", "FAILURE_EVENTS", "T_UNIT", "HORIZON")
AGENT_IMPORTS = {"OUTCOMES", "T_UNIT", "HORIZON"}  # spec S22 section 2
NUMBERS_IMPORTS = {"OUTCOMES", "FAILURE_EVENTS", "T_UNIT"}


@pytest.fixture
def pilot_package(pilot_env: None) -> Any:
    return importlib.import_module("golden_pilot")


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def parents_of(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Every node's parent. Q6 and Q13 ask what a name is *used as*, which needs the parent."""
    out: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[child] = node
    return out


def assigned_names(tree: ast.AST) -> set[str]:
    """Every name this module binds by assignment, at any depth."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            for sub in ast.walk(target):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    return names


def relative_imports(tree: ast.AST) -> set[str]:
    """The names a module pulls in with ``from . import ...``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None:
            names.update(alias.name for alias in node.names)
    return names


def string_constants_compared(tree: ast.AST) -> list[str]:
    """Every string literal this module compares, tests membership of, or prefix-matches.

    The three shapes a text discriminator can take: ``x == "..."`` / ``x in ("...",)``
    (``ast.Compare``), ``x.startswith("...")`` and its family, and ``re.match("...", x)``.
    """
    found: list[str] = []
    text_methods = {
        "startswith", "endswith", "removeprefix", "removesuffix", "find", "index",
        "count", "split", "partition",
    }
    regex_calls = {"match", "search", "fullmatch", "findall", "sub", "compile"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for operand in [node.left, *node.comparators]:
                found.extend(
                    sub.value for sub in ast.walk(operand)
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in text_methods | regex_calls:
                for arg in node.args:
                    found.extend(
                        sub.value for sub in ast.walk(arg)
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                    )
    return found


def api_text_literals(tree: ast.AST) -> list[str]:
    """Those of them that read like an API-error message: the Addendum 1 filter's shape."""
    return [
        text
        for text in string_constants_compared(tree)
        if any(marker in text.lower() for marker in API_TEXT_MARKERS)
    ]


# ---------- Q1, Q2: one definition of the vocabulary ----------


def test_q1_the_five_outcomes_live_in_one_place_and_both_consumers_import_that_place(
    pilot_package: Any, agent: Any, numbers_module: Any
) -> None:
    """Identity, not equality: an equal re-spelled copy in ``numbers.py`` must fail here.

    Two modules that each spell ``("passed", ...)`` compile two distinct tuple objects, so
    ``is`` separates the import from the copy where ``==`` cannot. It does not separate them
    for ``T_UNIT`` or ``HORIZON``: CPython interns the string and caches the small int, so
    ``is`` on those is vacuously true for a re-spelled copy too. The next test carries them.
    """
    assert pilot_package.OUTCOMES == OUTCOMES
    assert isinstance(pilot_package.OUTCOMES, tuple)
    assert agent.OUTCOMES is pilot_package.OUTCOMES
    assert numbers_module.OUTCOMES is pilot_package.OUTCOMES
    assert numbers_module.FAILURE_EVENTS is pilot_package.FAILURE_EVENTS
    assert agent.T_UNIT == pilot_package.T_UNIT == T_UNIT
    assert numbers_module.T_UNIT == pilot_package.T_UNIT
    assert agent.HORIZON == pilot_package.HORIZON == HORIZON


def test_q1_neither_consumer_assigns_a_vocabulary_name_and_both_import_it_from_the_package() -> None:
    """The half of Q1 that identity cannot carry, for the interned ``T_UNIT`` and ``HORIZON``.

    The rule stated in prose, so a later reader does not have to reconstruct it from the
    ``ast`` walk: **the package defines the vocabulary and nobody else binds those names.**
    ``agent.py`` and ``numbers.py`` each reach it with ``from . import ...`` and neither
    assigns ``OUTCOMES``, ``FAILURE_EVENTS``, ``T_UNIT`` or ``HORIZON`` anywhere.
    """
    package = parsed(ROOT / "__init__.py")
    assert set(VOCABULARY) <= assigned_names(package), sorted(assigned_names(package))

    agent_tree = parsed(ROOT / "agent.py")
    assert set(VOCABULARY) & assigned_names(agent_tree) == set(), sorted(assigned_names(agent_tree) & set(VOCABULARY))
    assert AGENT_IMPORTS <= relative_imports(agent_tree), sorted(relative_imports(agent_tree))

    numbers_tree = parsed(ROOT / "numbers.py")
    assert set(VOCABULARY) & assigned_names(numbers_tree) == set(), sorted(assigned_names(numbers_tree) & set(VOCABULARY))
    assert NUMBERS_IMPORTS <= relative_imports(numbers_tree), sorted(relative_imports(numbers_tree))


def test_q2_failure_events_is_every_outcome_but_passed_in_the_outcome_order(pilot_package: Any) -> None:
    assert set(pilot_package.FAILURE_EVENTS) == set(pilot_package.OUTCOMES) - {"passed"}
    assert pilot_package.FAILURE_EVENTS == tuple(o for o in pilot_package.OUTCOMES if o != "passed")
    assert pilot_package.FAILURE_EVENTS == FAILURE_EVENTS


def test_q2_failure_events_is_derived_from_outcomes_and_not_spelled_out() -> None:
    """The rule in prose: **``FAILURE_EVENTS`` is computed from ``OUTCOMES``, never written.**

    An equal four-tuple of literals satisfies the test above and is exactly the mutant --
    it is a third spelling of the vocabulary, and a sixth outcome lands in it or not by
    whoever remembers. So the assignment's right-hand side must mention ``OUTCOMES`` and
    must contain no outcome name as a literal.
    """
    package = parsed(ROOT / "__init__.py")
    values = [
        node.value
        for node in ast.walk(package)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(isinstance(t, ast.Name) and t.id == "FAILURE_EVENTS" for t in ast.walk(node) if isinstance(t, ast.Name))
        and node.value is not None
    ]
    assert len(values) == 1, values
    value = values[0]
    mentions = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}
    assert "OUTCOMES" in mentions, sorted(mentions)
    literals = [
        n.value for n in ast.walk(value)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in OUTCOMES
    ]
    assert literals == ["passed"], literals  # the one name it may spell is the one it removes


# ---------- Q3, Q4: the two boundaries ----------


def test_q3_a_5xx_that_survives_every_retry_at_the_ordinary_turn_is_an_api_error(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run = play(agent, monkeypatch, "api_error")
    assert run.episode.outcome == "api_error", run.episode
    assert run.episode.meta["retries"] == 3
    assert len(run.requests) == 4, [q.turn for q in run.requests]  # the attempt and three retries
    reason = run.episode.meta["crash_reason"]
    assert isinstance(reason, str) and ("500" in reason or "InternalServerError" in reason), reason


def test_q3_a_5xx_that_survives_every_retry_at_the_repair_turn_is_an_api_error_too(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The second of the two ``content is None`` sites, tested apart from the first.

    The mutant this exists for moves only the ordinary turn and leaves the repair turn
    ``crashed``. The episode below reaches the repair turn on an unparseable reply and then
    cannot reach the model at all: the same failure, one turn later.
    """
    run = play(agent, monkeypatch, "api_error_at_repair_turn")
    assert run.episode.outcome == "api_error", run.episode
    assert run.episode.meta["retries"] == 3
    assert len(run.requests) == 1 + 4, [q.turn for q in run.requests]  # the garbage reply, then the repair turn's four
    reason = run.episode.meta["crash_reason"]
    assert isinstance(reason, str) and ("500" in reason or "InternalServerError" in reason), reason


def test_q4_two_unparseable_replies_are_crashed_and_never_an_api_error(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """The model was reached twice and replied unusably twice; the failure is the agent's.

    ``_PARSE_FAILURE`` is private to ``agent.py`` and the spec states its name but not its
    text, so this pins the property that matters instead of the string: the reason is one
    fixed constant -- the same on two different parse-failure episodes, at different turn
    counts -- and it is not the API-error text.
    """
    run = play(agent, monkeypatch, "garbage")
    assert run.episode.outcome == "crashed", run.episode
    assert run.episode.meta["retries"] == 0
    later = play(agent, monkeypatch, "crash_after_two_calls")
    assert later.episode.outcome == "crashed", later.episode
    reason, other = run.episode.meta["crash_reason"], later.episode.meta["crash_reason"]
    assert isinstance(reason, str) and reason == other, (reason, other)
    assert "pars" in reason.lower(), reason
    assert not any(marker in reason.lower() for marker in API_TEXT_MARKERS), reason


# ---------- Q5: `retries` is not the discriminator ----------


class FlakyModel:
    """A scripted model whose turn ``n`` 5xxs its first ``flaky[n]`` attempts, then answers.

    ``ScriptedModel`` is stateless on purpose (P5, P10): every request at a turn gets that
    turn's one reply, which cannot express "fail twice, then succeed". Q5 needs exactly that,
    so this one counts attempts per turn. It delegates to a ``ScriptedModel`` for the reply
    and for the recording, so its requests still reach ``ALL_REQUESTS`` and P11's last test.
    Nothing but Q5 uses it.
    """

    def __init__(self, script: Script, flaky: Mapping[int, int]) -> None:
        self.inner = ScriptedModel(script)
        self.flaky = dict(flaky)
        self.attempts: dict[int, int] = {}
        self.transport = httpx.MockTransport(self.handle)

    @property
    def requests(self) -> list[Request]:
        return self.inner.requests

    def client(self) -> Any:
        return openai.OpenAI(
            api_key="oracle-key-never-sent",
            base_url=DISCARD_URL,
            http_client=httpx.Client(transport=self.transport),
            max_retries=0,
        )

    def handle(self, request: Any) -> Any:
        body = bytes(request.content)
        try:
            data = json.loads(body) if body else {}
        except ValueError:
            data = {}
        messages = data.get("messages") if isinstance(data, Mapping) else None
        messages = messages if isinstance(messages, list) else []
        turn = sum(1 for m in messages if isinstance(m, Mapping) and m.get("role") == "assistant")
        response = self.inner.handle(request)  # records the request whatever we answer with
        seen = self.attempts.get(turn, 0)
        self.attempts[turn] = seen + 1
        if seen < self.flaky.get(turn, 0):
            return httpx.Response(500, json={"error": {"message": "scripted upstream failure", "type": "server_error"}})
        return response


def test_q5_two_retries_then_a_parse_failure_is_crashed_with_two_retries(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """``meta["retries"] == 2`` and the outcome is ``crashed``: retries do not decide.

    Turn 0 5xxs twice, succeeds on the third attempt and spends a tool call. Turns 1 and 2
    are unparseable. A build that read the API case off a non-zero ``retries`` calls this
    ``api_error``; the model was reached three times, so it is ``crashed``.
    """
    script: Script = {(HE2, 41): (*steps(("run_tests", canonical(HE2))), GARBAGE, GARBAGE)}
    model = FlakyModel(script, {0: 2})
    monkeypatch.setattr(agent, "client_factory", model.client)
    episode = agent.rollout({"task_id": HE2, "temperature": 0.0}, 41)
    assert episode.outcome == "crashed", episode
    assert episode.meta["retries"] == 2, episode.meta["retries"]
    assert episode.t == 1, episode.t
    assert len(model.requests) == 3 + 1 + 1, [q.turn for q in model.requests]


def test_q5_two_successful_retries_then_an_exhausted_turn_is_an_api_error_with_five_retries(agent: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """``meta["retries"] == 5`` and the outcome is ``api_error``: the same number, told apart.

    Turn 0 5xxs twice and then succeeds; turn 1 exhausts the attempt and all three backoffs.
    Read off ``retries`` the two Q5 episodes are indistinguishable in kind -- both non-zero,
    neither three -- and ``outcome`` is the only thing that separates them.
    """
    script: Script = {(HE2, 42): (*steps(("run_tests", canonical(HE2))), FIVE_HUNDRED)}
    model = FlakyModel(script, {0: 2})
    monkeypatch.setattr(agent, "client_factory", model.client)
    episode = agent.rollout({"task_id": HE2, "temperature": 0.0}, 42)
    assert episode.outcome == "api_error", episode
    assert episode.meta["retries"] == 5, episode.meta["retries"]
    assert episode.t == 1, episode.t
    assert len(model.requests) == 3 + 4, [q.turn for q in model.requests]


# ---------- Q6: `crash_reason` is not the discriminator either ----------


def test_q6_agent_py_writes_crash_reason_and_carries_it_and_never_reads_its_text() -> None:
    """The rule in prose, because the ``ast`` walk below is not self-explaining.

    **``crash_reason`` is written and it is carried, and that is all.** Every occurrence of
    the name in ``agent.py`` is either an assignment target or a value inside a dict display
    -- the ``meta`` dict. It is never the object of an attribute access, never an argument to
    a call, never an operand of a comparison or a membership test. The outcome label is the
    discriminator now (spec S22 section 3), and an ADR that says where a value is built means
    a test fails when it is built elsewhere.

    ``ast``, never a substring scan: ``"crash_reason" in source`` cannot tell an assignment
    from a ``.startswith`` and would have to be either blind or wrong.
    """
    tree = parsed(ROOT / "agent.py")
    parents = parents_of(tree)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Name) and node.id == "crash_reason"):
            continue
        if isinstance(node.ctx, ast.Store):
            continue
        parent = parents.get(node)
        where = f"line {node.lineno}, inside {type(parent).__name__}"
        assert isinstance(node.ctx, ast.Load), where
        assert isinstance(parent, ast.Dict) and any(v is node for v in parent.values), where


def test_q6_agent_py_compares_no_string_that_reads_like_an_api_error_message() -> None:
    """The other half: nothing in the module prefix-matches or compares API-error text.

    A discriminator does not need the variable -- ``error.startswith("API error")`` reads the
    same fact off a different name. This looks for the literal instead of for the variable.
    """
    tree = parsed(ROOT / "agent.py")
    assert api_text_literals(tree) == [], api_text_literals(tree)


# ---------- Q7: `t` is unchanged, and nothing raises ----------


@pytest.mark.parametrize("name", ["api_error", "api_error_at_repair_turn", "api_error_after_two_calls"])
def test_q7_an_api_error_episode_counts_the_calls_it_made_and_keeps_the_horizon(agent: Any, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    run = play(agent, monkeypatch, name)
    episode = run.episode
    assert isinstance(episode, Episode), type(episode)
    assert episode.outcome == "api_error", episode
    assert 0 <= episode.t <= HORIZON and float(episode.t).is_integer(), episode.t
    assert episode.horizon == HORIZON
    assert episode.meta["task_id"] == scenario(name)[0]


def test_q7_the_rollout_still_returns_an_episode_for_a_5xx_a_garbage_reply_and_a_hang(agent: Any, fast_sandbox: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    for name, expected in (("api_error", "api_error"), ("garbage", "crashed"), ("hang", "passed")):
        run = play(agent, monkeypatch, name)
        assert isinstance(run.episode, Episode), (name, type(run.episode))
        assert run.episode.outcome == expected, (name, run.episode.outcome)
        assert run.episode.horizon == HORIZON, name


def test_q7_the_outcome_is_none_fallback_is_still_crashed_and_is_pinned_statically() -> None:
    """The rule in prose: **the loop exiting with no outcome set is our bug, not the API's.**

    ``_loop`` is ``while outcome is None``, so every exit either sets an outcome or breaks
    having set one: the ``Episode(outcome=... else "crashed")`` default is unreachable by
    construction, and routing it to ``api_error`` changes nothing any script can observe.
    That leaves one instrument. This reads the default off the ``Episode`` call itself and
    fails if the fallback names the new outcome -- the only way this mutant can be caught, and
    the reason it is written as a static check rather than as a scripted episode.
    """
    tree = parsed(ROOT / "agent.py")
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Episode"
    ]
    assert len(calls) == 1, calls
    outcome_arg = [kw.value for kw in calls[0].keywords if kw.arg == "outcome"]
    assert len(outcome_arg) == 1, calls[0].keywords
    literals = {
        n.value for n in ast.walk(outcome_arg[0])
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    assert literals == {"crashed"}, literals


# ---------- Q9: no collision with the executor's error strings ----------

RUN_Q9 = "pilot-q9"
INFRA_API_ERROR = "infra: API error after 3 retries: APIConnectionError: connection reset"


@pytest.fixture(scope="module")
def q9_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One cell: an ``api_error`` ok row, a ``passed`` ok row, and two errored rows -- one of
    which carries API-error text in its *error* string. That row is the trap: it is Proofload
    failing to observe, it has no outcome, and ``--event api_error`` must not reach it."""
    root = tmp_path_factory.mktemp("pilot-q9-store")
    store = Store(root)
    store.create_run(
        RunManifest(run_id=RUN_Q9, target_id=TARGET_ID, t_unit=T_UNIT, run_salt="q9-salt", axis_types=AXIS_TYPES, backend="local", environment={})
    )
    rows = [
        ok_row(RUN_Q9, "c0", 0, 900, "api_error", 1, episode_trace(RUN_Q9, "c0", 0, tools=1, llms=1)),
        ok_row(RUN_Q9, "c0", 1, 901, "passed", 2, episode_trace(RUN_Q9, "c0", 1, tools=2, llms=2)),
        errored_row(RUN_Q9, "c0", 2, 902, INFRA_API_ERROR, None),
        errored_row(RUN_Q9, "c0", 3, 903, TIMEOUT_ERROR, None),
    ]
    assert store.append(RUN_Q9, rows) == 4
    return root


def test_q9_no_outcome_collides_with_the_executors_error_strings(agent: Any) -> None:
    for name in FORBIDDEN_OUTCOMES:
        assert name not in agent.OUTCOMES
    assert "api_error" not in FORBIDDEN_OUTCOMES
    assert not any(o.startswith("infra: ") for o in agent.OUTCOMES), agent.OUTCOMES


def inspected(root: Path, event: str) -> str:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(["--store", str(root), "inspect", RUN_Q9, "--event", event], stdout=out, stderr=err)
    assert code == 0, (code, out.getvalue(), err.getvalue())
    return out.getvalue()


def test_q9_inspect_on_the_new_event_selects_the_outcome_rows_and_no_errored_row(q9_root: Path) -> None:
    """``inspect --event NAME`` reads outcomes and errors under one flag (M10), and the store
    here holds an errored row whose *error* spells API-error text. Selection is by the whole
    string, so it does not match, and an errored row is never counted as an episode that
    reached a terminal outcome. The errored rows are reachable, under their own strings.
    """
    text = inspected(q9_root, "api_error")
    assert [line for line in text.splitlines() if line.startswith("seed: ")] == ["seed: 900"], text
    assert "error:" not in text and "outcome: -" not in text, text  # the errored row's shape
    assert INFRA_API_ERROR not in text, text

    still_errored = inspected(q9_root, TIMEOUT_ERROR)
    assert [line for line in still_errored.splitlines() if line.startswith("seed: ")] == ["seed: 903"], still_errored
    assert "outcome: -" in still_errored and f"error: {TIMEOUT_ERROR}" in still_errored, still_errored

    infra = inspected(q9_root, INFRA_API_ERROR)
    assert [line for line in infra.splitlines() if line.startswith("seed: ")] == ["seed: 902"], infra


# ---------- Q10: the CIF correction, measured ----------

RUN_PRE = "pilot-pre-s22"
RUN_POST = "pilot-post-s22"
Q10_HORIZON = 6.0
#: Per cell, the episodes as (outcome, t); ``API`` is the one an S18 agent labelled ``crashed``
#: and an S22 agent labels ``api_error``. c0 has API failures and no true crash, c1 has both,
#: c2 has neither -- the three cases Q10 distinguishes.
Q10_LAYOUT: dict[str, list[tuple[str, float]]] = {
    "c0": [("passed", 3), ("API", 2), ("failed_assertion", 4), ("API", 5), ("passed", 6)],
    "c1": [("crashed", 1), ("API", 3), ("passed", 2), ("timed_out", 6)],
    "c2": [("passed", 2), ("crashed", 3), ("failed_assertion", 1), ("timed_out", 6)],
}
Q10_WITH_API = ("c0", "c1")
Q10_WITHOUT_API = ("c2",)


def q10_rows(run_id: str, api_label: str) -> list[EpisodeRecord]:
    """The same episodes twice, differing only in what the API failures are called."""
    out = []
    for cell, episodes in Q10_LAYOUT.items():
        for k, (outcome, t) in enumerate(episodes):
            out.append(
                EpisodeRecord(
                    run_id=run_id, config_hash=CELL_HASH[cell], config=dict(CELLS[cell]),
                    seed=5000 + k, replicate_index=k,
                    outcome=api_label if outcome == "API" else outcome,
                    t=float(t), horizon=Q10_HORIZON, confidence=None, meta={}, error=None,
                    wall_time=1.0, backend_meta={},
                )
            )
    return out


@pytest.fixture(scope="module")
def q10_frames(tmp_path_factory: pytest.TempPathFactory) -> tuple[Any, Any]:
    store = Store(tmp_path_factory.mktemp("pilot-q10-store"))
    for run_id, label in ((RUN_PRE, "crashed"), (RUN_POST, "api_error")):
        store.create_run(
            RunManifest(run_id=run_id, target_id=TARGET_ID, t_unit=T_UNIT, run_salt="q10-salt", axis_types=AXIS_TYPES, backend="local", environment={})
        )
        assert store.append(run_id, q10_rows(run_id, label)) == sum(len(v) for v in Q10_LAYOUT.values())
    return store.read(RUN_PRE), store.read(RUN_POST)


def test_q10_the_competing_set_gains_the_new_name_and_nothing_else(q10_frames: tuple[Any, Any]) -> None:
    pre, post = q10_frames
    assert competing_set(pre) == ("crashed", "failed_assertion", "passed", "timed_out")
    assert competing_set(post) == ("api_error", "crashed", "failed_assertion", "passed", "timed_out")
    assert len(competing_set(pre)) == 4 and len(competing_set(post)) == 5


def test_q10_the_crashed_cif_stops_absorbing_the_api_failures_by_exactly_their_own_cif(q10_frames: tuple[Any, Any]) -> None:
    """The correction, in the numbers, over the same episodes under the two labellings.

    Aalen-Johansen's cause-``k`` incidence is a sum of ``S(t-) * d_k(t) / n(t)``. Relabelling
    moves mass between causes and touches neither ``S`` nor ``n``, so the ``crashed``
    incidence has to fall by exactly the ``api_error`` incidence -- in a cell that had an API
    failure -- and not move at all in a cell that had none. Both frames are diffed against
    themselves, which is how a cumulative incidence is read out of ``multi_diff``: ``rate_a``
    is the estimate at the horizon and the comparison is beside the point here.

    The drop is compared with a tolerance and the no-change case with ``==``. The second is a
    bit-identical computation and must be exact; the first is a sum re-associated across two
    causes, where real-arithmetic equality does not oblige floating point to agree bitwise.
    """
    pre, post = q10_frames
    before = {str(r.config_hash): float(r.rate_a) for r in multi_diff(pre, pre, events=("crashed",)).by_event["crashed"].cells.itertuples()}
    after = multi_diff(post, post, events=("crashed", "api_error"))
    crashed = {str(r.config_hash): float(r.rate_a) for r in after.by_event["crashed"].cells.itertuples()}
    api = {str(r.config_hash): float(r.rate_a) for r in after.by_event["api_error"].cells.itertuples()}

    for cell in Q10_WITH_API:
        h = CELL_HASH[cell]
        assert api[h] > 0.0, (cell, api[h])
        assert crashed[h] < before[h], (cell, crashed[h], before[h])
        assert before[h] - crashed[h] == pytest.approx(api[h], abs=1e-12), (cell, before[h], crashed[h], api[h])
    for cell in Q10_WITHOUT_API:
        h = CELL_HASH[cell]
        assert api[h] == 0.0, (cell, api[h])
        assert crashed[h] == before[h], (cell, crashed[h], before[h])


# ---------- Q11: numbers.py over all five outcomes ----------

RUN_Q11 = "pilot-q11"
RUN_Q11B = "pilot-q11-prime"


def q11_rows() -> list[EpisodeRecord]:
    """Two cells, every outcome once, ``api_error`` twice, and one errored row.

    ok rows (cell, k, seed, outcome, t, tools, llms):
      c0 0 700 passed            2  2 2
      c0 1 701 failed_assertion  3  3 3
      c0 2 702 api_error         1  1 1
      c1 0 710 timed_out         6  6 6
      c1 1 711 crashed           0  0 1
      c1 2 712 api_error         0  0 1
    errored: c1 k3 seed 713, "timeout", with a truncated trace.
    """
    a = RUN_Q11
    return [
        ok_row(a, "c0", 0, 700, "passed", 2, episode_trace(a, "c0", 0, tools=2, llms=2)),
        ok_row(a, "c0", 1, 701, "failed_assertion", 3, episode_trace(a, "c0", 1, tools=3, llms=3)),
        ok_row(a, "c0", 2, 702, "api_error", 1, episode_trace(a, "c0", 2, tools=1, llms=1)),
        ok_row(a, "c1", 0, 710, "timed_out", 6, episode_trace(a, "c1", 0, tools=6, llms=6)),
        ok_row(a, "c1", 1, 711, "crashed", 0, episode_trace(a, "c1", 1, tools=0, llms=1)),
        ok_row(a, "c1", 2, 712, "api_error", 0, episode_trace(a, "c1", 2, tools=0, llms=1)),
        errored_row(a, "c1", 3, 713, TIMEOUT_ERROR, timeout_trace(a, "c1", 3)),
    ]


def q11_rows_prime() -> list[EpisodeRecord]:
    """The same six triples, one outcome changed: c0 k2 is ``passed`` where A was ``api_error``."""
    b = RUN_Q11B
    small = episode_trace(b, "c0", 0, tools=1, llms=1)
    return [
        ok_row(b, "c0", 0, 700, "passed", 1, small),
        ok_row(b, "c0", 1, 701, "failed_assertion", 1, small),
        ok_row(b, "c0", 2, 702, "passed", 1, small),
        ok_row(b, "c1", 0, 710, "timed_out", 1, small),
        ok_row(b, "c1", 1, 711, "crashed", 1, small),
        ok_row(b, "c1", 2, 712, "api_error", 1, small),
    ]


@pytest.fixture(scope="module")
def q11_numbers(numbers_module: Any, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    store = Store(tmp_path_factory.mktemp("pilot-q11-store"))
    for run_id, rows in ((RUN_Q11, q11_rows()), (RUN_Q11B, q11_rows_prime())):
        store.create_run(
            RunManifest(run_id=run_id, target_id=TARGET_ID, t_unit=T_UNIT, run_salt="q11-salt", axis_types=AXIS_TYPES, backend="local", environment={})
        )
        assert store.append(run_id, rows) == len(rows)
    out = numbers_module.numbers(store, RUN_Q11, paired_with=RUN_Q11B)
    assert isinstance(out, dict)
    return out


def test_q11_contract_survival_counts_an_api_error_row_as_surviving(q11_numbers: dict[str, Any]) -> None:
    """The mutant: ``numbers.py`` keeping a four-name ``OUTCOMES`` of its own. Every row here
    is well-formed, so anything but a clean sweep means the two ``api_error`` rows failed the
    ``outcome in OUTCOMES`` clause."""
    contract = q11_numbers["contract"]
    assert (contract["rows"], contract["survived"], contract["failed"]) == (6, 6, 0), contract
    assert contract["without_llm_spans"] == 0, contract


def test_q11_zero_n_is_over_the_four_failure_events(q11_numbers: dict[str, Any]) -> None:
    zero_n = q11_numbers["zero_n"]
    assert zero_n["cells"] == 2
    assert list(zero_n["events"]) == list(FAILURE_EVENTS) == ["failed_assertion", "timed_out", "crashed", "api_error"]
    # c0 produced failed_assertion and api_error -> holes on timed_out, crashed.
    # c1 produced timed_out, crashed and api_error -> holes on failed_assertion.
    expected = {
        (CELL_HASH["c0"], "timed_out"), (CELL_HASH["c0"], "crashed"),
        (CELL_HASH["c1"], "failed_assertion"),
    }
    holes = {(str(cell), str(event)) for cell, event in zero_n["holes"]}
    assert holes == expected, sorted(holes ^ expected)
    assert zero_n["count"] == 3 == 2 * len(FAILURE_EVENTS) - 5, zero_n["count"]


def test_q11_the_errored_split_span_census_and_kind_histogram_are_unchanged_in_shape(q11_numbers: dict[str, Any]) -> None:
    n = q11_numbers
    assert (n["rows"], n["ok_rows"], n["errored_rows"]) == (7, 6, 1)
    # spans per ok row: 5 7 3 | 13 2 2  (root + tools + llms)
    assert n["spans"] == 5 + 7 + 3 + 13 + 2 + 2 == 32
    assert n["dropped"] == 0
    assert n["kinds"] == {"llm": 14, "tool": 12, "retrieval": 0, "db": 0, "http": 0, "agent": 6, "other": 0}
    assert set(n["kinds"]) == set(KINDS) and sum(n["kinds"].values()) == n["spans"]
    assert n["other_share"] == 0.0
    assert n["tool_share"] == approx(Fraction(12, 32))
    assert n["errored"] == {
        "rows": 1, "rate": approx(Fraction(1, 7)), "by_error": {TIMEOUT_ERROR: 1},
        "with_trace": 1, "without_trace": 0,
    }, n["errored"]


def test_q11_agreement_and_kappa_are_unchanged_in_shape_over_five_labels(q11_numbers: dict[str, Any]) -> None:
    pairing = q11_numbers["pairing"]
    assert pairing["paired_with"] == RUN_Q11B
    assert pairing["triples"] == 6
    # Six shared triples, all at temperature 0.0 except c1's, which CELLS puts at 0.0 as well;
    # c0 k2 is the one disagreement (api_error vs passed) -> 5/6.
    assert pairing["agreement"]["all"] == approx(Fraction(5, 6))
    # A: passed 1, failed_assertion 1, api_error 2, timed_out 1, crashed 1
    # A': passed 2, failed_assertion 1, timed_out 1, crashed 1, api_error 1
    # p_e = (1*2 + 1*1 + 2*1 + 1*1 + 1*1) / 36 = 7/36; p_o = 30/36
    kappa = (Fraction(30, 36) - Fraction(7, 36)) / (1 - Fraction(7, 36))
    assert kappa == Fraction(23, 29)
    assert pairing["kappa"]["all"] == approx(kappa)
    assert set(pairing) >= {"paired_with", "triples", "agreement", "kappa"}
    assert set(pairing["agreement"]) == {"all", "by_temperature"}
    assert set(pairing["kappa"]) == {"all", "by_temperature"}


# ---------- Q12: the README says it ----------

FENCE_SENTENCE = "A nonzero api_error CIF is a fact about the run and never a finding about the agent."
TESTING_VERBS = ("diff", "report", "check")


def readme_sections() -> dict[str, str]:
    """``## `` headings to their bodies, keyed by the heading text."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    heading = ""
    for line in text.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            sections[heading] = ""
        elif heading:
            sections[heading] += line + "\n"
    return sections


def section(prefix: str) -> str:
    matches = [body for head, body in readme_sections().items() if head.startswith(prefix)]
    assert len(matches) == 1, (prefix, sorted(readme_sections()))
    return matches[0]


def flattened(text: str) -> str:
    """Backticks and emphasis markers dropped, whitespace collapsed: the prose, not the markup.

    ``_`` is left alone deliberately -- stripping it would turn ``api_error`` into ``apierror``
    and the pin would stop being about the name.
    """
    return " ".join(text.replace("`", "").replace("*", "").split())


def readme_commands() -> list[str]:
    """The ``proofload`` commands in section 3's fenced block, continuations joined."""
    body = section("3.")
    inside = False
    joined: list[str] = []
    pending = ""
    for line in body.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            continue
        pending += " " + line.strip().removesuffix("\\").strip()
        if not line.rstrip().endswith("\\"):
            joined.append(" ".join(pending.split()))
            pending = ""
    return [c for c in joined if c.startswith("proofload ")]


def test_q12_section_1s_confirmation_line_names_all_five_outcomes() -> None:
    body = flattened(section("1."))
    assert "outcome should be one of" in body, body[-400:]
    clause = body.split("outcome should be one of", 1)[1]
    for name in OUTCOMES:
        assert name in clause[: clause.index("numbers.py")], (name, clause[:300])


def test_q12_each_of_the_four_testing_commands_names_the_new_event() -> None:
    """Deliberately a text pin, and the README's correctness is what is under test.

    Section 3's commands were wrong about ``--method`` for weeks and an outside reader
    concluded from them that the tool assumes independence, because nothing tested them. A
    later edit that trips this test is amended to the new correct text under Session A
    authority. It is never reverted, and this pin is never loosened to stop it firing.
    """
    commands = [c for c in readme_commands() if c.split()[1] in TESTING_VERBS]
    assert len(commands) == 4, commands
    for command in commands:
        for event in FAILURE_EVENTS:
            assert f"--event {event}" in command, (event, command)


def test_q12_the_readme_carries_the_interpretive_fence_verbatim() -> None:
    assert flattened(FENCE_SENTENCE) in flattened((ROOT / "README.md").read_text(encoding="utf-8"))


# ---------- Q13: the Addendum 1 filter is gone, and never arrives ----------


def test_q13_no_pilot_module_branches_on_a_crash_reason_prefix_or_on_api_error_text() -> None:
    """The rule in prose: **the label is the discriminator and the text is not.**

    S18's pre-registration excluded API-error crashes by matching a ``crash_reason`` prefix.
    That stopgap is retired by this packet, not kept, and nothing under the pilot implements
    it after it: no module compares, prefix-matches or regexes a string that reads like an
    API-error message. Two definitions of one condition drift, which is the whole reason the
    label exists.
    """
    files = pilot_python_files()
    assert files, ROOT
    offenders = {str(path): api_text_literals(parsed(path)) for path in files}
    assert not {k: v for k, v in offenders.items() if v}, {k: v for k, v in offenders.items() if v}


def test_q13_numbers_py_does_not_mention_crash_reason_at_all() -> None:
    tree = parsed(ROOT / "numbers.py")
    names = [n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "crash_reason"]
    literals = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value == "crash_reason"
    ]
    attributes = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "crash_reason"]
    assert (names, literals, attributes) == ([], [], []), (names, literals, attributes)


# ---------- P11, last: every request this process ever sent ----------


def test_p11_every_request_any_scripted_model_saw_went_to_chat_completions_and_none_to_responses() -> None:
    assert len(ALL_REQUESTS) >= 2, "the agent tests before this one sent nothing"
    for q in ALL_REQUESTS:
        assert q.path.endswith("/chat/completions"), q.path
        assert "/responses" not in q.path, q.path
