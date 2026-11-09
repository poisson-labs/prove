"""The cloud backend's coordinator launcher: a script run as ``python -I <this file> VERB ...``.

It imports the standard library and, inside each verb, the cluster software (Burla 1.8.4, whose
private functions are the only way to start its coordinator without opening its dashboard), so
neither that import nor what it reads from the environment happens in Prove's own process. It
answers with one JSON object on its last line of stdout. Verbs:

- ``probe PROVIDER REGION``: whether the software imports here and at which version, and whether
  the cloud's SDK resolves credentials in this same interpreter (``crt`` when botocore's ``crt``
  extra is missing for a session made by ``aws login``). Nothing of a credential is printed:
  only whether one was found.
- ``find PROVIDER ACCOUNT``: the account's recorded coordinator, its URL and pid, and whether it
  is alive.
- ``start PROVIDER ACCOUNT``: start (or reuse) the account's coordinator; its URL, pid and log.
- ``stop PROVIDER ACCOUNT PID``: stop the coordinator the software recorded, if it is still the
  process ``PID``.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _out(doc: dict[str, Any]) -> None:
    print(json.dumps(doc), flush=True)


def _project(provider: str, account: str) -> str:
    """The software's own name for an account's state folder."""
    return f"{provider}-{account}"


def probe(provider: str, region: str) -> None:
    doc: dict[str, Any] = {"software": None, "missing": False, "credentials": None}
    try:
        import burla
    except ImportError:
        doc["missing"] = True
        _out(doc)
        return
    doc["software"] = getattr(burla, "__version__", None)
    if provider == "aws":
        try:
            import boto3  # type: ignore[import-untyped, unused-ignore]

            credentials = boto3.Session(region_name=region).get_credentials()
            doc["credentials"] = "ok" if credentials is not None else "none"
        except ImportError:
            doc["credentials"] = "no-sdk"
        except Exception as exc:  # noqa: BLE001 - only its kind leaves this process
            text = f"{type(exc).__name__} {exc}"
            missing = "MissingDependency" in text or "botocore[crt]" in text
            doc["credentials"] = "crt" if missing else "error"
    _out(doc)


def find(provider: str, account: str) -> None:
    from burla._local_head import _head_state_dir, _pid_alive

    path = _head_state_dir(_project(provider, account)) / "head.json"
    if not path.exists():
        _out({})
        return
    head = json.loads(path.read_text())
    pid = head.get("head_pid")
    _out({"url": head.get("url"), "pid": pid, "alive": bool(_pid_alive(pid))})


def start(provider: str, account: str) -> None:
    from burla._local_head import _head_state_dir, ensure_local_head

    try:
        url = ensure_local_head()
    except Exception as exc:  # noqa: BLE001 - reported to Prove, which words it
        text = str(exc)
        unreachable = "HEAD_UNREACHABLE" in text or "not become ready" in text
        code = "HEAD_UNREACHABLE" if unreachable else type(exc).__name__
        _out({"error": True, "code": code, "message": text})
        return
    folder = _head_state_dir(_project(provider, account))
    head = json.loads((folder / "head.json").read_text())
    _out({"url": url, "pid": head.get("head_pid"), "log": str(folder / "head.log")})


def stop(provider: str, account: str, pid: str) -> None:
    from burla._local_head import _head_state_dir, _pid_alive, _stop_recorded_head

    folder = _head_state_dir(_project(provider, account))
    path = folder / "head.json"
    if path.exists():
        _stop_recorded_head(path, int(pid))
    _out({"stopped": not _pid_alive(int(pid)), "log": str(folder / "head.log")})


if __name__ == "__main__":
    verb, arguments = sys.argv[1], sys.argv[2:]
    if verb == "probe":
        probe(*arguments)
    elif verb == "find":
        find(*arguments)
    elif verb == "start":
        start(*arguments)
    elif verb == "stop":
        stop(*arguments)
    else:
        raise SystemExit(f"unknown verb: {verb}")
