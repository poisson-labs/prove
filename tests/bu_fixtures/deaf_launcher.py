"""A launcher that never reports, never reads its input, and ignores every signal but SIGKILL.

The backstop's test points ``_launcher_argv`` here ($5): ``python -I deaf_launcher.py <state> ...``.
It notes each signal it receives, starts a stand-in heartbeat child in its own process group (as
Burla's heartbeat is, ``_heartbeat.py:16-35``), writes both process ids down, and sleeps. Only a
SIGKILL of its process group ends the two.
"""

import json
import os
import signal
import subprocess
import sys
import time


def main():
    state = sys.argv[1]
    notes = os.path.join(state, "deaf.jsonl")

    def note(entry):
        with open(notes, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def ignore(signum, frame):
        note({"signal": signum, "time": time.time()})

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        signal.signal(sig, ignore)
    heartbeat = subprocess.Popen(
        [sys.executable, "-I", "-S", "-c", "import time\nwhile True:\n    time.sleep(1)\n"]
    )
    note({"pid": os.getpid(), "pgid": os.getpgid(0), "sid": os.getsid(0),
          "heartbeat": heartbeat.pid, "time": time.time()})
    while True:
        time.sleep(0.2)


if __name__ == "__main__":
    main()
