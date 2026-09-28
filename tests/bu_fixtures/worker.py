"""A fake Burla worker: one long-lived interpreter that serves calls one after another.

Started as ``python -I -S worker.py <socket> <site-packages>`` with an empty environment and a
fresh temporary folder as its working directory. That is the worker's view (W2): the standard
library, plus the venv's ``site-packages`` folder appended here *without* processing a single
``.pth`` file, so the index-installed distributions a node gets are importable and an editable
install is not. No host project folder is on the path (W3); ``-I`` keeps this script's own
folder off it too.

It mirrors ``node_service/worker_server.py`` at 1.8.1: the process makes itself a session
leader (``:421-424``) and outlives every job (``:427-486``). A job's first message resets it,
which unloads only what Burla itself shipped for the last job (``:444-451``) -- nothing, for a
launcher that ships nothing -- and the second loads the cloudpickled function (``:403-418``).
Each input is then unpickled and handed to the loaded function as one argument (``:470-477``);
the reply is its cloudpickled return value, or the exception it raised.

Each input served is appended to the job's ``served.jsonl`` with this process's id. The network
tripwire is armed before anything is loaded, so any socket but the Unix one it listens on
raises.
"""

import json
import os
import pickle
import socket
import struct
import sys
import time
import traceback


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


def _exactly(conn, n):
    chunks = []
    while n:
        chunk = conn.recv(min(n, 1 << 20))
        if not chunk:
            raise EOFError
        chunks.append(chunk)
        n -= len(chunk)
    return b"".join(chunks)


def _recv(conn):
    (size,) = struct.unpack(">Q", _exactly(conn, 8))
    return pickle.loads(_exactly(conn, size))


def _send(conn, message):
    data = pickle.dumps(message)
    conn.sendall(struct.pack(">Q", len(data)) + data)


def _serve(conn, cloudpickle):
    loaded = None
    served, call_no = None, None
    while True:
        try:
            message = _recv(conn)
        except EOFError:
            return
        command = message[0]
        if command == "reset":
            loaded = None
            _send(conn, ("ok",))
        elif command == "load":
            _, fn_bytes, served, call_no = message
            loaded = cloudpickle.loads(fn_bytes)
            _send(conn, ("ok",))
        elif command == "call":
            _, index, arg_bytes = message
            started = time.time()
            try:
                value = loaded(cloudpickle.loads(arg_bytes))
                reply = ("ok", cloudpickle.dumps(value), os.getpid())
            except BaseException as exc:  # noqa: BLE001 - returned to the caller, as Burla does
                try:
                    pickled = cloudpickle.dumps(exc)
                except Exception:  # noqa: BLE001
                    pickled = pickle.dumps(RuntimeError(repr(exc)))
                reply = ("error", pickled, traceback.format_exc(), os.getpid())
            if served:
                with open(served, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"call": call_no, "index": index, "worker": os.getpid(),
                                         "start": started, "end": time.time(),
                                         "kind": reply[0]}) + "\n")
            _send(conn, reply)


def main():
    path, site_packages = sys.argv[1], sys.argv[2]
    sys.path.append(site_packages)
    _arm_tripwire()
    import cloudpickle

    os.setsid()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen(8)
    with open(path + ".ready", "w", encoding="utf-8") as fh:
        fh.write(str(os.getpid()))
    while True:
        conn, _ = listener.accept()
        try:
            _serve(conn, cloudpickle)
        except (OSError, EOFError):
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    main()
