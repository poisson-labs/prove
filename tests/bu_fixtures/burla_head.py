"""The fake head (coordinator): a process that serves nothing, for the fake of Burla 1.8.4.

    python -I burla_head.py <state folder> <project>

It arms the network tripwire, writes ``head-<pid>.json`` (its environment's Burla and AWS
variables and its session) and ``head-<pid>.ready`` into the state folder, records every SIGTERM,
SIGINT and SIGHUP it receives in ``head-signals.jsonl``, and leaves on SIGTERM or SIGINT, as
uvicorn does. Started by the fake's ``ensure_local_head``, or by a test that needs a head Prove did
not start.
"""

import json
import os
import signal
import socket
import sys
import time

KEYS = ("BURLA_CLOUD", "BURLA_PRIVATE", "DISABLE_BURLA_TELEMETRY", "AWS_REGION", "AWS_DEFAULT_REGION",
        "DISABLE_BURLA_KEEP_AWAKE")


def _arm_tripwire():
    real_connect = socket.socket.connect

    def connect(self, address):
        if self.family != socket.AF_UNIX:
            raise RuntimeError("network tripwire: a network connection was attempted")
        return real_connect(self, address)

    socket.socket.connect = connect


def main():
    state, project = sys.argv[1], sys.argv[2]
    _arm_tripwire()
    pid = os.getpid()

    def on_signal(signum, _frame):
        with open(os.path.join(state, "head-signals.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"pid": pid, "signal": signum, "time": time.time()}) + "\n")
        if signum in (signal.SIGTERM, signal.SIGINT):
            sys.exit(0)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, on_signal)
    info = {
        "pid": pid,
        "project": project,
        "sid": os.getsid(0),
        "env": {key: os.environ[key] for key in KEYS if key in os.environ},
        "started": time.time(),
    }
    with open(os.path.join(state, f"head-{pid}.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh)
    open(os.path.join(state, f"head-{pid}.ready"), "w").close()
    while True:
        time.sleep(0.5)


if __name__ == "__main__":
    main()
