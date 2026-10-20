"""M11a -- the injection seam: one declared fault, keyed on (logical step, attempt).

The seam sits on the transport, below the target's own code. ``install()`` wraps
``httpx.Client.send`` and ``httpx.AsyncClient.send``; ``injecting(spec, seed)`` scopes one
episode; ``position(name, attempt)`` is the target's own declaration of where it is.
Everything the applier does is Prove's -- the vocabulary it addresses is
``poisson_prove.chaos_catalog``'s, which carries the attribution.

**Three properties this module exists to hold.**

*Firing is a keyed variate, never a stream.* ``u = _variate(seed, step_name, attempt)`` and
the fault applies iff ``u < rate``. There is no counter, no shared RNG and no global call
index, so the set of injected positions is a pure function of ``(seed, position)``: nested
across rate levels, identical across two arms that differ only in the fault name, and
unmoved by a patch that changes how many calls the target makes.

*Nothing is injected outside a ``position()``.* A call the target did not place inside one
is passed through and recorded with ``position=None``. There is no fallback to a call
index: inferring an ordinal is what re-keys every fault the moment the call sequence moves.

*A fault that did not apply is fatal, not a no-op.* An unknown fault name and a faulted arm
whose process has not loaded a client are refused before the run exists; a ``target_path``
that does not resolve, a mutation that changes nothing and a streaming request at an
injectable position are refused inside the episode. An injection that silently does nothing
produces a null result that reads as a measurement.

**Core, and what that costs.** This module ships in core, so it may not import a network
client and may not read the clock outside ``trace.py``. It reaches the client through
``sys.modules["httpx"]`` -- the one the target already loaded, which is resolved before
``install()`` on both execution paths -- and the clock through ``trace._span_clock()``.
"""

from __future__ import annotations

import contextlib
import contextvars
import copy
import hashlib
import json
import random
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from poisson_prove import chaos_catalog
from poisson_prove.trace import _span_clock

__all__ = [
    "ChaosError",
    "ChaosSpec",
    "ChaosStatus",
    "FaultRecord",
    "fault_names",
    "injecting",
    "install",
    "position",
]

#: A6 section 3.13's two reserved span attributes. A8a mints the public constants with the
#: rest of the span vocabulary and its step zero re-points these two literals at them; until
#: then they live here, module-private, once each in the whole of ``src/``.
_FAULT_KEY = "poisson_prove.fault"
_FAULT_POSITION_KEY = "poisson_prove.fault.position"

_NONE = "none"
_CHAT_PATH = "/chat/completions"
_HOOK_NAMES = ("sync", "async")
_API_ERROR_TEMPLATE = "[API ERROR] HTTP {code}: AgentFault injected server error."
_DROP_CONTENT = "[TIMEOUT] Connection dropped. The server did not respond."
_DEFAULT_TRUNCATE_RATIO = 0.5
_CORRUPT_RATIO = 5
_CORRUPT_LOW = 0x2600
_CORRUPT_HIGH = 0x26FF


class ChaosError(RuntimeError):
    """The run cannot be executed under the injection it declared. Always fatal."""


@dataclass(frozen=True)
class ChaosSpec:
    """The ``[chaos]`` table of the sweep file, as the executor carries it."""

    fault: str = _NONE
    rate: float = 1.0
    steps: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChaosStatus:
    """What ``install()`` did. Recorded on the manifest; never a reason to continue."""

    requested: bool
    fault: str
    rate: float
    steps: tuple[str, ...]
    engine_version: str | None


@dataclass(frozen=True)
class FaultRecord:
    """One intercepted chat completion, in the seam's own shape."""

    call_index: int
    position: str | None
    fault: str | None
    applied: bool
    start_ns: int
    end_ns: int
    model: str
    request_messages: Any
    request_tools: tuple[str, ...]
    response: Mapping[str, Any]
    delay_ms: float


@dataclass
class _Block:
    """One episode's injection state: what was asked, at which seed, and what was refused."""

    spec: ChaosSpec
    seed: int
    records: list[FaultRecord]
    refusal: ChaosError | None = None


@dataclass(frozen=True)
class _Decision:
    """What the seam will do with one intercepted call, decided before the transport."""

    block: _Block
    position: str | None
    step_name: str | None
    attempt: int
    inject: bool


#: The episode block is a module global rather than a context variable on purpose: a target
#: that dispatches its own calls to a thread pool must still be injected, and a worker thread
#: starts from an empty context. The *position* is context-local, so the pool's threads do
#: not inherit the caller's position -- which is the asymmetry M11a-13 pins.
_BLOCK: _Block | None = None

_POSITION: contextvars.ContextVar[tuple[str, int] | None] = contextvars.ContextVar(
    "poisson_prove_chaos_position", default=None
)

_STATUS: ChaosStatus | None = None
_ORIGINALS: tuple[Any, Any] | None = None
_HOOKS: tuple[str, ...] = ()


# ---------- the vocabulary ----------


def fault_names() -> tuple[str, ...]:
    """Every catalogue name, sorted, plus ``"none"``. Total: nothing here can fail."""
    return (*sorted(chaos_catalog.CATALOG), _NONE)


def _entries_for(name: str) -> tuple[Any, ...]:
    entry = chaos_catalog.CATALOG[name]
    return (entry,) if isinstance(entry, chaos_catalog.FaultEntry) else tuple(entry)


def _installed_hooks() -> tuple[str, ...]:
    """Which transport hooks this process carries. Private: the manifest reads it, nothing else."""
    return _HOOKS


# ---------- the keying ----------


def _variate(seed: int, step_name: str, attempt: int) -> float:
    """The firing variate: a pure function of the episode seed and the position, in [0, 1)."""
    digest = hashlib.sha256(f"{seed}:{step_name}:{attempt}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _content_seed(seed: int, step_name: str, attempt: int, fault: str) -> int:
    """The seed of the one action that consumes randomness, masked to the store's int64."""
    digest = hashlib.sha256(f"{seed}:{step_name}:{attempt}:{fault}".encode()).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


@contextlib.contextmanager
def position(name: str, attempt: int = 1) -> Iterator[None]:
    """Declare the logical position every call inside this block is keyed on.

    Context-local, so two ``asyncio`` tasks each running their own step never see each
    other's value, and the previous position is restored on the way out -- including when
    the block raises. ``attempt`` is 1-based.
    """
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ChaosError(f"position() attempt is 1-based and must be an int >= 1, got {attempt!r}")
    token = _POSITION.set((str(name), attempt))
    try:
        yield
    finally:
        _POSITION.reset(token)


# ---------- the applier ----------


def _tokens(path: str | None) -> list[str | int]:
    """A ``$.a[0].b`` target path as a list of dict keys and list indices."""
    if path is None or path == "$":
        return []
    text = path[2:] if path.startswith("$.") else path
    tokens: list[str | int] = []
    for part in text.split("."):
        name, bracket, rest = part.partition("[")
        if name:
            tokens.append(name)
        while bracket:
            index, _, rest = rest.partition("]")
            tokens.append(int(index))
            _, bracket, rest = rest.partition("[")
    return tokens


def _resolve(body: Any, tokens: Sequence[str | int], path: str | None) -> Any:
    node = body
    for token in tokens:
        try:
            node = node[token]
        except (KeyError, IndexError, TypeError) as exc:
            raise ChaosError(
                f"the fault's target_path {path!r} does not resolve against the response body; "
                "a fault addressing a path that is not there has not been applied"
            ) from exc
    return node


def _set_at(body: Any, tokens: Sequence[str | int], value: Any, path: str | None) -> None:
    """Replace what is at ``tokens``. The leaf must already exist -- creating one would be
    the silent pass this seam refuses, wearing a write."""
    _resolve(body, tokens, path)
    parent = _resolve(body, tokens[:-1], path)
    parent[tokens[-1]] = value


def _cut(value: Any, ratio: float) -> Any:
    if isinstance(value, (str, list)):
        return value[: max(1, int(len(value) * ratio))]
    return value


def _truncate(current: Any, raw_ratio: Any, arguments: bool) -> Any:
    ratio = (
        float(raw_ratio)
        if isinstance(raw_ratio, (int, float))
        and not isinstance(raw_ratio, bool)
        and 0.0 < raw_ratio < 1.0
        else _DEFAULT_TRUNCATE_RATIO
    )
    if arguments and isinstance(current, str):
        parsed = json.loads(current)
        return json.dumps({key: _cut(value, ratio) for key, value in parsed.items()})
    return _cut(current, ratio)


def _corrupt_text(text: Any, mode: Any, rng: random.Random) -> Any:
    if not isinstance(text, str) or not text:
        return text
    if mode == "mojibake":
        return text.encode("utf-8").decode("latin-1")
    if mode == "broken_json":
        return text[: len(text) // 2] + "\x00\x00"
    chars = list(text)
    count = min(len(chars), max(1, len(chars) // _CORRUPT_RATIO))
    for index in rng.sample(range(len(chars)), count):
        chars[index] = chr(rng.randint(_CORRUPT_LOW, _CORRUPT_HIGH))
    return "".join(chars)


def _corrupt(current: Any, mode: Any, arguments: bool, content_seed: int) -> Any:
    rng = random.Random(content_seed)
    if arguments and isinstance(current, str):
        parsed = json.loads(current)
        return json.dumps(
            {key: _corrupt_text(value, mode, rng) for key, value in parsed.items()}
        )
    return _corrupt_text(current, mode, rng)


def _mutate(entry: Any, body: Any, content_seed: int) -> None:
    tokens = _tokens(entry.target_path)
    path = entry.target_path
    arguments = bool(tokens) and tokens[-1] == "arguments"
    if entry.action == "set":
        _set_at(body, tokens, copy.deepcopy(entry.value), path)
    elif entry.action == "truncate":
        current = _resolve(body, tokens, path)
        _set_at(body, tokens, _truncate(current, entry.value, arguments), path)
        if bool(tokens) and tokens[-1] == "content":
            # A real truncation sets finish_reason, and targets branch on it.
            _set_at(body, [*tokens[:-2], "finish_reason"], "length", path)
    elif entry.action == "corrupt":
        current = _resolve(body, tokens, path)
        _set_at(body, tokens, _corrupt(current, entry.value, arguments, content_seed), path)
    elif entry.action == "error":
        # The path is honoured rather than hardcoded: an action that ignores one of its own
        # fields is the silent-pass hazard wearing a different hat.
        _set_at(body, tokens, _API_ERROR_TEMPLATE.format(code=entry.value), path)
    elif entry.action == "drop":
        _resolve(body, tokens, path)  # the call the fault names must be there to be dropped
        content, calls = chaos_catalog.CONTENT_PATH, chaos_catalog.TOOL_CALLS_PATH
        _set_at(body, _tokens(content), _DROP_CONTENT, content)
        _set_at(body, _tokens(calls), [], calls)
    else:
        raise ChaosError(
            f"the catalogue entry {entry.name!r} names an unknown action {entry.action!r}"
        )


def _apply(fault: str, body: Any, content_seed: int) -> tuple[Any, float]:
    """Mutate a copy of ``body``, and verify that the payload actually changed.

    A ``delay``-only scenario changes nothing by definition and is the one exemption; every
    other scenario that leaves the body byte-identical is refused, because a ``FaultRecord``
    claiming a fault applied when none did is the null result this seam exists to prevent.
    """
    mutated = copy.deepcopy(body)
    delay_ms = 0.0
    last_path: str | None = None
    for entry in _entries_for(fault):
        if entry.action == "delay":
            delay_ms += float(entry.value or 0)
            continue
        last_path = entry.target_path
        _mutate(entry, mutated, content_seed)
    if last_path is not None and mutated == body:
        raise ChaosError(
            f"the fault {fault!r} at target_path {last_path!r} changed nothing: a mutation "
            "that leaves the payload identical is a null result, not a measurement"
        )
    return mutated, delay_ms


# ---------- the hooks ----------


def _refuse(block: _Block, error: ChaosError) -> ChaosError:
    """Record the refusal so ``injecting()`` re-raises it, whatever the target does with it.

    An SDK between the seam and the target wraps whatever ``send`` raises in a connection
    error of its own, so the caller's exception type is not the seam's to choose. The block
    keeps the original and raises it on the way out.
    """
    if block.refusal is None:
        block.refusal = error
    return error


def _request_body(request: Any) -> dict[str, Any]:
    try:
        content = request.content
    except Exception:  # noqa: BLE001 - a request the seam cannot read is a request it passes
        return {}
    if not content:
        return {}
    try:
        parsed = json.loads(content)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _decide(request: Any) -> _Decision | None:
    """What to do with one call, before the transport is reached. ``None`` is pass-through."""
    block = _BLOCK
    if block is None or _CHAT_PATH not in str(request.url):
        return None
    current = _POSITION.get()
    if current is None:
        return _Decision(block, None, None, 0, False)
    step_name, attempt = current
    rendered = f"{step_name}:{attempt}"
    spec = block.spec
    inject = (
        spec.fault != _NONE
        and (not spec.steps or step_name in spec.steps)
        and _variate(block.seed, step_name, attempt) < spec.rate
    )
    if inject and _request_body(request).get("stream") is True:
        raise _refuse(
            block,
            ChaosError(
                f"a streaming request at the injectable position {rendered!r} is refused: "
                "rewriting it to stream=False would change the target's own control flow"
            ),
        )
    return _Decision(block, rendered, step_name, attempt, inject)


def _stamp(fault: str, rendered: str) -> None:
    """Write the two reserved attributes onto whatever span the injected call is inside."""
    try:
        from opentelemetry import trace as otel_trace
    except Exception:  # noqa: BLE001 - no OTel in this process is not a reason to fail a run
        return
    try:
        span = otel_trace.get_current_span()
        if span is not None and span.is_recording():
            span.set_attribute(_FAULT_KEY, fault)
            span.set_attribute(_FAULT_POSITION_KEY, rendered)
    except Exception:  # noqa: BLE001 - the carrier never errors the episode it rides
        return


def _observed(body: Any, status: int) -> dict[str, Any]:
    """The pre-injection view of one response, in the shape M11b maps."""
    message: Any = {}
    finish = None
    if isinstance(body, dict):
        choices = body.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            finish = choices[0].get("finish_reason")
    return {
        "content": message.get("content") if isinstance(message, dict) else None,
        "tool_calls": message.get("tool_calls") if isinstance(message, dict) else None,
        "finish_reason": finish,
        "usage": body.get("usage") if isinstance(body, dict) else None,
        "http_status": status,
    }


def _rebuild(httpx_module: Any, response: Any, body: Any) -> Any:
    """The injected response: the original envelope, a new payload.

    Every header the provider sent is kept -- rate-limit and request-id headers are absent
    exactly where a reader wants them -- and only ``content-length`` is replaced.
    """
    headers = [
        (key, value)
        for key, value in response.headers.multi_items()
        if key.lower() != "content-length"
    ]
    return httpx_module.Response(
        response.status_code,
        content=json.dumps(body).encode("utf-8"),
        headers=headers,
        request=response.request,
    )


def _finish(
    httpx_module: Any,
    decision: _Decision,
    request: Any,
    response: Any,
    start_ns: int,
    end_ns: int,
) -> Any:
    block = decision.block
    request_body = _request_body(request)
    tools = tuple(
        str(tool.get("function", {}).get("name", ""))
        for tool in request_body.get("tools") or []
        if isinstance(tool, dict)
    )
    try:
        original = response.json()
    except ValueError:
        original = None
    fault: str | None = None
    applied = False
    delay_ms = 0.0
    out = response
    if decision.inject and not isinstance(original, dict):
        raise _refuse(
            block,
            ChaosError(
                f"the response at the injectable position {decision.position!r} carries no "
                "JSON body the vocabulary can address, so the fault was not applied"
            ),
        )
    if decision.inject:
        name = block.spec.fault
        assert decision.step_name is not None and decision.position is not None
        seed = _content_seed(block.seed, decision.step_name, decision.attempt, name)
        try:
            mutated, delay_ms = _apply(name, original, seed)
        except ChaosError as error:
            raise _refuse(block, error) from None
        out = _rebuild(httpx_module, response, mutated)
        _stamp(name, decision.position)
        fault, applied = name, True
    block.records.append(
        FaultRecord(
            call_index=len(block.records),
            position=decision.position,
            fault=fault,
            applied=applied,
            start_ns=start_ns,
            end_ns=end_ns,
            model=str(request_body.get("model", "")),
            request_messages=request_body.get("messages"),
            request_tools=tools,
            response=_observed(original, response.status_code),
            delay_ms=delay_ms,
        )
    )
    return out


def _install_hooks(httpx_module: Any) -> None:
    global _ORIGINALS, _HOOKS
    original_sync = httpx_module.Client.send
    original_async = httpx_module.AsyncClient.send

    def sync_send(self: Any, request: Any, **kwargs: Any) -> Any:
        decision = _decide(request)
        if decision is None:
            return original_sync(self, request, **kwargs)
        start_ns, mono_start = _span_clock()
        response = original_sync(self, request, **kwargs)
        _, mono_end = _span_clock()
        end_ns = start_ns + (mono_end - mono_start)
        return _finish(httpx_module, decision, request, response, start_ns, end_ns)

    async def async_send(self: Any, request: Any, **kwargs: Any) -> Any:
        decision = _decide(request)
        if decision is None:
            return await original_async(self, request, **kwargs)
        start_ns, mono_start = _span_clock()
        response = await original_async(self, request, **kwargs)
        _, mono_end = _span_clock()
        end_ns = start_ns + (mono_end - mono_start)
        return _finish(httpx_module, decision, request, response, start_ns, end_ns)

    httpx_module.Client.send = sync_send
    httpx_module.AsyncClient.send = async_send
    _ORIGINALS = (original_sync, original_async)
    _HOOKS = _HOOK_NAMES


def _uninstall() -> None:
    """Restore both ``send`` methods to the exact objects ``install()`` captured.

    Private, and nothing in a run calls it: it exists so the suite can assert the patch is
    removable, which is the failure worth fearing -- a teardown that clears state and leaves
    every later client in the process routed through a wrapper nobody asked for.
    """
    global _STATUS, _ORIGINALS, _HOOKS
    httpx_module = sys.modules.get("httpx")
    if _ORIGINALS is not None and httpx_module is not None:
        httpx_module.Client.send, httpx_module.AsyncClient.send = _ORIGINALS
    _STATUS, _ORIGINALS, _HOOKS = None, None, ()


def install(spec: ChaosSpec) -> ChaosStatus:
    """Arm the seam for this process. Once per process, memoized.

    Raises rather than degrades: an unknown fault name, and a faulted arm whose process has
    not loaded a client by the time this is called, are both refused here -- before the run
    exists. A capture that silently does nothing costs observability; an injection that
    silently does nothing turns the faulted arm into a second control arm.
    """
    global _STATUS
    if _STATUS is not None:
        return _STATUS
    if spec.fault not in fault_names():
        raise ChaosError(
            f"[chaos].fault {spec.fault!r} is not a fault this build implements; "
            f"the names are {', '.join(fault_names())}. Reach for [chaos].rate and "
            "[chaos].steps rather than a strategy name"
        )
    if spec.fault != _NONE:
        httpx_module = sys.modules.get("httpx")
        if httpx_module is None:
            raise ChaosError(
                "a faulted arm needs the client its target already loaded, and httpx is not "
                "in sys.modules: this process makes no LLM call the seam can reach, so the "
                "arm would run as a second control arm"
            )
        _install_hooks(httpx_module)
    _STATUS = ChaosStatus(
        requested=True,
        fault=spec.fault,
        rate=spec.rate,
        steps=tuple(spec.steps),
        engine_version=None if spec.fault == _NONE else chaos_catalog.ENGINE_VERSION,
    )
    return _STATUS


@contextlib.contextmanager
def injecting(spec: ChaosSpec, seed: int) -> Iterator[list[FaultRecord]]:
    """One episode. Yields the list the hooks append to; it is complete on exit.

    A refusal decided inside the block is re-raised here rather than left to whatever the
    target's SDK made of it, so a run that could not apply the fault it declared fails as
    one rather than as an episode error.
    """
    global _BLOCK
    block = _Block(spec=spec, seed=seed, records=[])
    previous, _BLOCK = _BLOCK, block
    try:
        yield block.records
    finally:
        _BLOCK = previous
    if block.refusal is not None:
        raise block.refusal
