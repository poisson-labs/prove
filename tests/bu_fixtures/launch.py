"""Start Prove's launcher with the fake of Burla 1.8.1 first on its path.

The tests point ``executor_burla._launcher_argv`` here:

    python -I launch.py <state> <mode> <path to _burla_submit.py> [whatever the mapper appends]

It arms the network tripwire, names the fake's state folder in this process's environment
(``BU_FAKE_BURLA_STATE``, so the fake and nothing else reads it), then runs the launcher script
as ``__main__`` with the mapper's own arguments, exactly as ``python -I <script>`` would.

``mode`` is ``fake`` (the fake is importable as ``burla``) or ``absent`` (``burla`` cannot be
imported at all, even when the real client is installed in the venv). A snapshot of the ledger
named in the state folder's ``ledger.path``, if any, is taken as the launcher starts ($6).
"""

import importlib.abc
import os
import runpy
import shutil
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
        if fullname == "burla" or fullname.startswith("burla."):
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


def _snapshot_ledger(state):
    try:
        with open(os.path.join(state, "ledger.path"), encoding="utf-8") as fh:
            ledger = fh.read().strip()
    except FileNotFoundError:
        return
    stamp = f"{time.time():.6f}-{os.getpid()}"
    target = os.path.join(state, f"ledger-at-launch-{stamp}")
    if os.path.exists(ledger):
        shutil.copyfile(ledger, target)
    else:
        open(target, "wb").close()


def main():
    state, mode, submit = sys.argv[1], sys.argv[2], sys.argv[3]
    _arm_tripwire()
    os.environ["BU_FAKE_BURLA_STATE"] = state
    with open(os.path.join(state, "launchers.txt"), "a", encoding="utf-8") as fh:
        fh.write(f"{os.getpid()} {os.getpgid(0)} {os.getsid(0)} {time.time():.6f}\n")
    _snapshot_ledger(state)
    if mode == "fake":
        sys.path.insert(0, HERE)
    elif mode == "absent":
        sys.meta_path.insert(0, _NoBurla())
    else:
        raise SystemExit(f"launch.py: unknown mode {mode!r}")
    sys.argv = [submit, *sys.argv[4:]]
    runpy.run_path(submit, run_name="__main__")


if __name__ == "__main__":
    main()
