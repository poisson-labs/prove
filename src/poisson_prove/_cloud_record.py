"""The ownership record of the cloud backend: what Prove started on one cloud account from this
machine, written before it starts it.

``$XDG_STATE_HOME/poisson-prove/cloud/<provider>-<account>.json`` (``~/.local/state`` when the
variable is unset), JSON, replaced whole by a rename on every change so a process killed at any
point leaves one that parses. Beside it go what the cluster software answered Prove
(``<provider>-<account>.log``) and, copied when the coordinator stops, the coordinator's own log
(``<provider>-<account>.head.log``).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any


def state_home() -> Path:
    given = os.environ.get("XDG_STATE_HOME")
    base = Path(given) if given else Path.home() / ".local" / "state"
    return base / "poisson-prove" / "cloud"


class Record:
    def __init__(self, provider: str, account: str) -> None:
        folder = state_home()
        self.path = folder / f"{provider}-{account}.json"
        self.log_path = folder / f"{provider}-{account}.log"
        self.head_log_path = folder / f"{provider}-{account}.head.log"
        self._lock = threading.Lock()

    def read(self) -> dict[str, Any] | None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return loaded if isinstance(loaded, dict) else None

    def write(self, **fields: Any) -> None:
        with self._lock:
            self._write(dict(fields))

    def update(self, **fields: Any) -> None:
        with self._lock:
            current = self.read() or {}
            current.update(fields)
            self._write(current)

    def _write(self, body: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(body, fh, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
