"""Episode correlation for OpenTelemetry capture — the stamper.

``proofload.run_id`` and ``proofload.episode`` are the two attributes M12 never lifts, so
they arrive in every span's ``attrs`` and are the whole mechanism for attaching captured
spans to a rollout. The onboarding story assumed the executor would set them as a per-episode
*resource* attribute; a 2026-09-04 spike against ``opentelemetry-sdk`` 1.44.0 found that
cannot vary inside one process. ``Resource.attributes`` is immutable, ``TracerProvider.resource``
has no setter, and a second ``set_tracer_provider()`` is refused — it logs "Overriding of
current TracerProvider is not allowed" and keeps the first provider, so every later span
still carries the first resource.

So the two keys are stamped as **span** attributes instead. ``from_otel`` merges resource,
scope and span attributes into ``attrs`` with span attributes winning, so they land in exactly
the same place and the converter is unchanged. The alternative — one process per episode via
``OTEL_RESOURCE_ATTRIBUTES`` — works, but forecloses many episodes per process, and the Modal
map is exactly where that is wanted.

This module imports ``opentelemetry`` and therefore lives behind the ``agent`` extra. Core
never reaches it: ``proofload/__init__.py`` does not import it, and ``proofload.trace`` stays
standard-library-only (T27).

Usage — register the stamper once, then wrap each episode::

    provider.add_span_processor(EpisodeStamper())
    with episode(run_id, f"{config_hash}:{seed}"):
        ...                     # every span started in here carries both keys

A span started outside any ``episode()`` block carries neither key. That is the signal for
*belongs to no rollout*, not a defect to repair.

**Thread pools.** A bare ``ThreadPoolExecutor.submit`` loses the stamp, because a worker
thread does not inherit the caller's context — the same cause, and the same fix, as a
``proofload.trace.record()`` span offloaded the same way. Use
``contextvars.copy_context().run(...)`` to carry the episode into the worker.
"""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator

from opentelemetry.context import Context
from opentelemetry.sdk.trace import Span, SpanProcessor

__all__ = ["EPISODE_KEY", "RUN_ID_KEY", "EpisodeStamper", "episode"]

#: The two attribute keys M12 deliberately never lifts, written in one place.
RUN_ID_KEY = "proofload.run_id"
EPISODE_KEY = "proofload.episode"

_EPISODE: contextvars.ContextVar[tuple[str, str] | None] = contextvars.ContextVar(
    "proofload_otel_episode", default=None
)


@contextlib.contextmanager
def episode(run_id: str, episode_id: str) -> Iterator[None]:
    """Mark every span started inside this block as belonging to one episode.

    Per-context, so two ``asyncio`` tasks each running their own episode never see each
    other's values, and the previous episode is restored on the way out — including when the
    block raises.
    """
    token = _EPISODE.set((run_id, episode_id))
    try:
        yield
    finally:
        _EPISODE.reset(token)


class EpisodeStamper(SpanProcessor):
    """Stamps the current episode onto every span at start.

    ``on_start`` is the only hook that can write: a span is immutable once it has ended.
    Registration order does not matter — every processor's ``on_start`` runs before any
    exporter sees the span on ``on_end``.
    """

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        current = _EPISODE.get()
        if current is None:
            return
        run_id, episode_id = current
        span.set_attribute(RUN_ID_KEY, run_id)
        span.set_attribute(EPISODE_KEY, episode_id)
