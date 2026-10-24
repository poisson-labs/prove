import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from poisson_prove.store import Store

FIXTURES = Path(__file__).resolve().parent / "fixtures"
#: PF9.4 (spec section 13.1): every module that drives a remote backend offline runs with network
#: sockets blocked in the pytest process (the interpreters the Burla and Modal fakes start arm
#: their own tripwire). ``test_pf9_backends`` checks that no such module is left out.
NETWORK_BLOCKED_MODULES = frozenset({
    "test_a10_declared", "test_bu_burla_backend", "test_m10_cli", "test_m10_multi", "test_m11a_chaos",
    "test_m3_capture", "test_m3_crash_trace", "test_m3_modal", "test_m3_modal_launch",
    "test_m3_timeout_trace", "test_mc_modal_chaos", "test_pf1_look", "test_pf9_backends",
    "test_pr1_pair_assertion", "test_s23_power",
})
#: A module that drives a backend but must serve on a local socket, with its reason.
NETWORK_EXEMPT_MODULES = {
    "test_pf0_name": "test_pf0_12 serves the comparison page on a loopback socket and reads it back",
}


class NetworkBlocked(OSError):
    """A network connection or name lookup was attempted in a module that runs offline."""


def network_blocked_for(module: str) -> bool:
    return module.rsplit(".", 1)[-1] in NETWORK_BLOCKED_MODULES


@pytest.fixture(autouse=True)
def blocked_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """In a guarded module: every socket other than a Unix one refuses to connect or send, and every
    name lookup refuses, with ``NetworkBlocked``; each attempt is recorded, and a test that made one
    fails at teardown even if the code under test swallowed the error. Elsewhere: nothing."""
    attempts: list[str] = []
    if not network_blocked_for(request.module.__name__):
        yield attempts
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def refuse(what: str) -> NetworkBlocked:
        attempts.append(what)
        return NetworkBlocked(f"network blocked in an offline backend test: {what}")

    def connect(self: socket.socket, address: Any) -> None:
        if self.family != socket.AF_UNIX:
            raise refuse(f"connect {address!r}")
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        if self.family != socket.AF_UNIX:
            raise refuse(f"connect_ex {address!r}")
        return real_connect_ex(self, address)

    def create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        raise refuse(f"create_connection {address!r}")

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> list[Any]:
        raise refuse(f"getaddrinfo {host!r}")

    def lookup(host: Any) -> Any:
        raise refuse(f"name lookup {host!r}")

    real_sendto = socket.socket.sendto

    def sendto(self: socket.socket, data: Any, *args: Any) -> int:
        if self.family != socket.AF_UNIX:
            raise refuse(f"sendto {args[-1]!r}")
        return real_sendto(self, data, *args)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(socket, "gethostbyname", lookup)
    monkeypatch.setattr(socket, "gethostbyname_ex", lookup)
    monkeypatch.setattr(socket.socket, "sendto", sendto)
    yield attempts
    assert attempts == [], f"network attempted in an offline backend test: {attempts}"


@pytest.fixture(scope="session")
def go1_store() -> Store:
    """The committed Go1 golden fixture at tests/fixtures/go1 (built by S3 Session B)."""
    return Store(FIXTURES / "go1")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Remove the bundle folders the Burla tests' fake workers unpacked and could not remove.

    A worker process holds its folder for its life and removes it at exit or when another bundle
    replaces it (``proofload._burla_submit``), but the fake pool ends its workers with SIGKILL, so
    the last pool's folders outlive them. Their temporary directory is what an interpreter with an
    empty environment gets, which is not this process's. Only a folder whose owner is gone is
    removed: a live worker of any other session still holds its lock.
    """
    import subprocess
    import sys

    from poisson_prove._burla_submit import _PREFIX, _reap

    probe = subprocess.run(
        [sys.executable, "-I", "-S", "-c", "import tempfile; print(tempfile.gettempdir())"],
        env={}, capture_output=True, text=True, timeout=60,
    )
    tmp = probe.stdout.strip()
    if probe.returncode == 0 and tmp and any(
        entry.name.startswith(_PREFIX) for entry in Path(tmp).iterdir()
    ):
        _reap(tmp, None)
