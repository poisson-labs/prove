"""The Burla backend: a sweep on a small fixed cluster in the user's own cloud, through Burla.

Names only. The build is Session B's, against ``tests/test_bu_burla_backend.py`` and the vault's
*Prove -- Spec Burla Backend*.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from proofload.executor import ExecutorError, Plan, RunSummary
from proofload.executor_modal import Job, Result
from proofload.store import Store

__all__ = [
    "BurlaBackendError",
    "BurlaCostGuard",
    "BurlaNotInstalled",
    "BurlaOptions",
    "BurlaSpendStop",
    "estimate_burla_cost",
    "preflight_burla",
    "run_burla",
]

#: After the stop's deadline, how long the launcher has to report before the parent sends it
#: SIGINT, and how long after that before its whole process group is killed.
_BACKSTOP_S = 60.0
_KILL_GRACE_S = 30.0


class BurlaBackendError(ExecutorError):
    """The Burla backend cannot run as requested."""


class BurlaNotInstalled(BurlaBackendError):
    """``burla==1.8.1`` is not importable by the launcher."""


class BurlaCostGuard(BurlaBackendError):
    """Refused before anything starts: the ledger total plus the estimate is over the cap."""


class BurlaSpendStop(BurlaBackendError):
    """The stop fired mid-run; the run is partial and resumable."""


@dataclass(frozen=True)
class BurlaOptions:
    """The ``[burla]`` table."""

    @classmethod
    def from_sweep_file(cls, path: Path) -> BurlaOptions:
        raise NotImplementedError("BurlaOptions.from_sweep_file")


def estimate_burla_cost(p: Plan, options: BurlaOptions) -> float:
    raise NotImplementedError("estimate_burla_cost")


def preflight_burla(p: Plan, import_path: str, options: BurlaOptions) -> str:
    raise NotImplementedError("preflight_burla")


def run_burla(
    p: Plan,
    import_path: str,
    store: Store,
    *,
    options: BurlaOptions,
    on_progress: Callable[[int, int], None] | None = None,
) -> RunSummary:
    raise NotImplementedError("run_burla")


@dataclass(frozen=True)
class _Bundle:
    """The gzip'd tar the workers unpack, and what the manifest records about it."""


def _build_bundle(packages: Sequence[str]) -> _Bundle:
    raise NotImplementedError("_build_bundle")


class _Ledger:
    """One JSON-lines spend ledger per step."""

    def __init__(self, path: Path) -> None:
        raise NotImplementedError("_Ledger")

    def total(self) -> float:
        raise NotImplementedError("_Ledger.total")

    def unclosed(self) -> list[str]:
        raise NotImplementedError("_Ledger.unclosed")


def _rehearse(p: Plan, import_path: str, bundle: _Bundle, options: BurlaOptions) -> Any:
    raise NotImplementedError("_rehearse")


def _launcher_argv() -> list[str]:
    raise NotImplementedError("_launcher_argv")


class _BurlaMapper:
    """A ``Mapper`` over the launcher."""

    def __call__(
        self, batches: Sequence[Sequence[Job]]
    ) -> Iterator[tuple[int, list[Result] | BaseException]]:
        raise NotImplementedError("_BurlaMapper")
