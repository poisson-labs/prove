"""Fixture targets for Prove's Burla backend tests. A package, so the bundle can carry it.

Imported in an isolated interpreter (a fake worker, the rehearsal's worker view, a batch's own
interpreter), it arms the network tripwire first: any socket but a Unix one raises. The pytest
process is never isolated, so it never arms one there, where other test files serve on a local
socket.
"""

import socket
import sys


def _arm_tripwire() -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network tripwire: a network connection was attempted")

    def connect(self: socket.socket, address: object) -> None:
        if self.family != socket.AF_UNIX:
            refuse()
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: object) -> int:
        if self.family != socket.AF_UNIX:
            refuse()
        return real_connect_ex(self, address)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.create_connection = refuse  # type: ignore[assignment]
    socket.getaddrinfo = refuse  # type: ignore[assignment]


if sys.flags.isolated:
    _arm_tripwire()
