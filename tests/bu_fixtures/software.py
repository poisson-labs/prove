"""Run a script or module of Prove's with the fake of Burla 1.8.4 and the fake cloud SDK first on
the path, in a process the network tripwire guards.

The tests point the cloud backend's three seams here (``executor_cloud._launcher_argv``,
``_head_argv`` and ``_cli_argv``):

    python -I software.py <state> <mode> <script.py> [args...]
    python -I software.py <state> <mode> -m <module> [args...]

``mode`` is ``fake`` (the fake ``burla``, ``boto3`` and ``botocore`` are importable) or ``absent``
(``burla`` cannot be imported at all, even when the real one is installed: the cloud extra is
missing). Each start is appended to ``software.jsonl`` in the state folder (its arguments, pid,
process group, session and time), and everything the script writes to stdout is also copied to
``software-out.txt``, so a test can read what a probe reported.
"""

import importlib.abc
import json
import os
import runpy
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def _arm_tripwire():
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def refuse(*_args, **_kwargs):
        raise RuntimeError("network tripwire: a network connection was attempted")

    def connect(self, address):
        if self.family != socket.AF_UNIX:
            refuse()
        return real_connect(self, address)

    def connect_ex(self, address):
        if self.family != socket.AF_UNIX:
            refuse()
        return real_connect_ex(self, address)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.create_connection = refuse
    socket.getaddrinfo = refuse


class _NoBurla(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] in ("burla", "main_service", "node_service"):
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


class _Tee:
    def __init__(self, stream, path):
        self.stream = stream
        self.path = path

    def write(self, text):
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(text)
        return self.stream.write(text)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def main():
    state, mode, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    _arm_tripwire()
    os.environ["BU_FAKE_BURLA_STATE"] = state
    with open(os.path.join(state, "software.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"argv": rest, "pid": os.getpid(), "pgid": os.getpgid(0),
                             "sid": os.getsid(0), "time": time.time()}) + "\n")
    if mode == "fake":
        sys.path[:0] = [HERE, os.path.join(HERE, "sdk")]
    elif mode == "absent":
        sys.meta_path.insert(0, _NoBurla())
        sys.path[:0] = [os.path.join(HERE, "sdk")]
    else:
        raise SystemExit(f"software.py: unknown mode {mode!r}")
    sys.stdout = _Tee(sys.stdout, os.path.join(state, "software-out.txt"))
    if rest[0] == "-m":
        sys.argv = [rest[1], *rest[2:]]
        runpy.run_module(rest[1], run_name="__main__", alter_sys=True)
    else:
        sys.argv = rest
        runpy.run_path(rest[0], run_name="__main__")


if __name__ == "__main__":
    main()
