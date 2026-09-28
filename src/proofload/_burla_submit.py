"""The Burla backend's launcher: a script run as ``python -I <this file>``, in its own session.

Names only. It imports the standard library and, inside ``main()``, ``burla``; the build is
Session B's, against ``tests/test_bu_burla_backend.py`` and the vault's *Prove -- Spec Burla
Backend*.
"""

import sys
from typing import Any


def _purge(keep: str) -> None:
    raise NotImplementedError("_purge")


def _materialise(bundle: bytes, sha256: str) -> str:
    raise NotImplementedError("_materialise")


def _bootstrap(
    k: int,
    jobs: list[Any],
    import_path: str,
    episode_timeout: float | None,
    capture: dict[str, Any] | None,
    chaos: dict[str, Any] | None,
) -> tuple[int, list[Any] | None, str | None]:
    raise NotImplementedError("_bootstrap")


def main() -> int:
    raise NotImplementedError("main")


if __name__ == "__main__":
    sys.exit(main())
