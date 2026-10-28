"""Start Prove's launcher through ``launch.py``, keeping the bundle each call to the fake ships (W1, P5).

The bundle tests point ``executor_burla._launcher_argv`` here instead of at ``launch.py``:

    python -I keep_bundle.py <state> fake <path to _burla_submit.py> [whatever the mapper appends]

Burla ships the function it is handed by value, with the module globals that function reads; the
bundle is the gzip'd payload among them. Before each call goes on to the fake, every gzip'd
payload the shipped function's globals hold is written to ``<state>/bundle-<n>.tar.gz``, ``n``
counting the payloads this state folder has kept. Nothing else differs from ``launch.py``.
"""

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GZIP_MAGIC = b"\x1f\x8b"


def _keep(state, function_):
    payloads = [
        value
        for value in getattr(function_, "__globals__", {}).values()
        if isinstance(value, bytes) and value.startswith(GZIP_MAGIC)
    ]
    kept = len([name for name in os.listdir(state) if name.startswith("bundle-")])
    for n, payload in enumerate(payloads, kept):
        with open(os.path.join(state, f"bundle-{n:03d}.tar.gz"), "wb") as fh:
            fh.write(payload)


def main():
    state = sys.argv[1]
    os.environ["BU_FAKE_BURLA_STATE"] = state
    sys.path.insert(0, HERE)
    import burla  # the fake: launch.py puts this same folder first on the path

    real = burla.remote_parallel_map

    def remote_parallel_map(function_, inputs, *args, **kwargs):
        _keep(state, function_)
        return real(function_, inputs, *args, **kwargs)

    burla.remote_parallel_map = remote_parallel_map
    launch = os.path.join(HERE, "launch.py")
    sys.argv = [launch, *sys.argv[1:]]
    runpy.run_path(launch, run_name="__main__")


if __name__ == "__main__":
    main()
