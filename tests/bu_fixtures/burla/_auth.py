"""A fake of 1.8.4's ``burla/_auth.py``: where per-account state lives, and which account this is.

- ``STATE_ROOT`` (``_auth.py:25-27``): ``user_data_dir("burla", "burla")/clusters`` in 1.8.4; here
  ``clusters`` under the fake's state folder, so nothing outside a test's own folder is touched.
- ``detect_cloud()`` (``_auth.py:92-181``) returns ``(cloud, project_id, region)``. The cloud is
  ``BURLA_CLOUD``, else the only cloud CLI on ``PATH`` (``_cloud_select.py:43-60``); for AWS the
  project is ``aws-<account>``, the account as ``aws sts get-caller-identity`` reports it. The fake
  reads the account from the fake ``aws``'s own state file beside it on ``PATH`` and does not run
  it, so the fake ``aws`` records only Prove's own calls.
- ``read_saved_cluster_token(project_id)`` (``_auth.py:268``): the token file's text, or None.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from burla import _fake


class LocalHeadError(Exception):
    pass


STATE_ROOT = Path(_fake.state_dir()) / "clusters" if os.environ.get(_fake.STATE_VAR) else Path("/nonexistent")


def _cloud() -> str:
    chosen = os.environ.get("BURLA_CLOUD", "").strip().lower()
    if chosen:
        return chosen
    found = [name for name in ("aws", "az", "gcloud") if shutil.which(name)]
    if len(found) != 1:
        raise LocalHeadError("fake burla: no single cloud CLI on PATH and BURLA_CLOUD is unset")
    return {"aws": "aws", "az": "azure", "gcloud": "gcp"}[found[0]]


def detect_cloud() -> tuple[str, str, str | None]:
    cloud = _cloud()
    if cloud != "aws":
        raise LocalHeadError(f"fake burla: only AWS is faked, not {cloud}")
    executable = shutil.which("aws")
    if not executable:
        raise LocalHeadError(
            "AWS is selected, but the aws CLI is not installed. "
            "Install it or run `burla config set cloud gcp`."
        )
    try:
        state = json.loads((Path(executable).parent / "aws-state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LocalHeadError(f"fake burla: the fake aws has no state: {exc}") from exc
    if state.get("signed_in") is not True:
        raise LocalHeadError("AWS is selected, but its credentials are not active.")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    return "aws", f"aws-{state['account']}", region


def read_saved_cluster_token(project_id: str) -> str | None:
    token = STATE_ROOT / project_id / "cluster_token"
    return token.read_text(encoding="utf-8").strip() if token.exists() else None
