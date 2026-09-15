"""A local OpenAI-shaped server for the T.4 budget test. No network, no key, no spend.

Kept beside the test rather than inside it because two things want it: the test that pins
litellm's inert budget accounting, and any later session re-measuring the capture path's span
shape without paying a provider for the privilege.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer

#: One assistant turn that is a tool call -- the shape τ²'s agent actually produces, and the
#: reason litellm's own accounting misses it: ``content`` is ``None``.
_RESPONSE = {
    "id": "chatcmpl-t4-mock",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-4.1-mini-2025-04-14",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_reservation_details",
                            "arguments": '{"reservation_id": "ABC123"}',
                        },
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {"prompt_tokens": 54046, "completion_tokens": 1023, "total_tokens": 55069},
}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's spelling
        self.rfile.read(int(self.headers.get("content-length", 0) or 0))
        body = json.dumps(_RESPONSE).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Silent: the test's output is the measurement, not the server's access log."""


@contextmanager
def mock_openai_server() -> Iterator[str]:
    """Yield an ``api_base`` serving one canned chat completion on every POST."""
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
