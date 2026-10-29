"""A test marked ``backend`` runs with the network open; every other test keeps it blocked.

``conftest.py``'s guard blocks network sockets and name lookups in every test. A test marked
``backend`` calls a real Modal or Burla account by its mark's own definition, so under that guard
it could never pass. Here a child pytest loads this suite's ``conftest.py`` and runs two probes that
each look up ``localhost`` (loopback, so the check needs no network of its own): the one marked
``backend`` must pass, and the unmarked one must be refused as before.
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBES = '''\
import socket

import pytest


@pytest.mark.backend
def test_marked_backend():
    socket.getaddrinfo("localhost", 80)


def test_unmarked():
    socket.getaddrinfo("localhost", 80)
'''


def test_a_backend_test_reaches_the_network_and_an_unmarked_one_does_not(tmp_path: Path) -> None:
    probes = tmp_path / "test_probes.py"
    probes.write_text(PROBES, encoding="utf-8")
    junit = tmp_path / "junit.xml"
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "tests"), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "conftest",
         "-c", str(ROOT / "pyproject.toml"), "--rootdir", str(tmp_path), "--basetemp", str(tmp_path / "bt"),
         "--junitxml", str(junit), str(probes)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600,
    )
    assert junit.exists(), done.stdout[-3000:] + done.stderr[-3000:]
    outcomes = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        failed = [child.tag for child in case if child.tag in ("failure", "error")]
        outcomes.setdefault(case.get("name"), []).extend(failed)
    assert outcomes.get("test_marked_backend") == [], (outcomes, done.stdout[-3000:])
    assert outcomes.get("test_unmarked"), (outcomes, done.stdout[-3000:])
    assert "NetworkBlocked" in done.stdout, done.stdout[-3000:]
