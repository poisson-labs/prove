"""A fake of boto3's session, as far as Prove's cloud readiness probe may go: no network, no file.

``boto3.Session(profile_name=None, region_name=None)`` and ``boto3.session.Session`` the same;
``Session.region_name``; ``Session.get_credentials()``, which resolves the default chain and
returns a credentials object, ``None`` when nothing is configured, or raises botocore's
``MissingDependencyException`` when the session was made by ``aws login`` and ``botocore[crt]``
is absent. The state folder's ``sdk.json`` says which: ``{"credentials": "ok" | "none" | "crt"}``,
and the planted values the credentials object carries (``access_key``, ``secret_key``, ``token``)
so a test can show none of them leaves the probe. Every call is recorded in ``sdk.jsonl``.
"""

import json
import os
import time

from botocore.exceptions import MissingDependencyException

__version__ = "1.42.39"


def _state():
    folder = os.environ.get("BU_FAKE_BURLA_STATE", "")
    try:
        with open(os.path.join(folder, "sdk.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"credentials": "ok"}


def _record(what, **entry):
    folder = os.environ.get("BU_FAKE_BURLA_STATE", "")
    if not folder:
        return
    with open(os.path.join(folder, "sdk.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"call": what, "time": time.time(), "pid": os.getpid(), **entry}) + "\n")


class Credentials:
    method = "login"

    def __init__(self, access_key, secret_key, token):
        self.access_key = access_key
        self.secret_key = secret_key
        self.token = token

    def get_frozen_credentials(self):
        _record("get_frozen_credentials")
        return self


class Session:
    def __init__(self, profile_name=None, region_name=None, **kwargs):
        self.profile_name = profile_name
        self.region_name = region_name or os.environ.get("AWS_REGION") or os.environ.get(
            "AWS_DEFAULT_REGION")
        _record("Session", profile_name=profile_name, region_name=region_name)

    def get_credentials(self):
        state = _state()
        _record("get_credentials")
        kind = state.get("credentials", "ok")
        if kind == "crt":
            raise MissingDependencyException(
                msg='Using the login credential provider requires an additional dependency. '
                'You will need to pip install "botocore[crt]" before proceeding.'
            )
        if kind == "none":
            return None
        planted = state.get("planted", {})
        return Credentials(planted.get("access_key", "AKIAFAKEFAKEFAKE0000"),
                           planted.get("secret_key", "fake-secret"),
                           planted.get("token", "fake-token"))

    def client(self, *args, **kwargs):
        _record("client", args=list(args))
        raise RuntimeError("fake boto3: Prove's probe makes no client and no call")


class _SessionModule:
    Session = Session


session = _SessionModule()
