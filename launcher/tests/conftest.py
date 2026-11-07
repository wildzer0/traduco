from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest


@dataclass
class Behaviour:
    payload: bytes = b""
    fail_first: int = 0  # answer HTTP 500 this many times first
    drop_first: bool = False  # first response is cut in half, then the socket closes
    support_range: bool = True
    status_override: int | None = None
    requests: list[dict[str, str]] = field(default_factory=list)


def _handler(b: Behaviour) -> type[BaseHTTPRequestHandler]:
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_: object) -> None:
            pass

        def do_GET(self) -> None:
            b.requests.append(dict(self.headers.items()))
            if b.status_override:
                self.send_response(b.status_override)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if b.fail_first > 0:
                b.fail_first -= 1
                self.send_response(500)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            data, start, status = b.payload, 0, 200
            rng = self.headers.get("Range")
            if rng and b.support_range:
                start = int(rng.split("=")[1].rstrip("-"))
                data, status = b.payload[start:], 206
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            if status == 206:
                self.send_header(
                    "Content-Range", f"bytes {start}-{len(b.payload) - 1}/{len(b.payload)}"
                )
            self.end_headers()
            if b.drop_first:
                b.drop_first = False
                self.wfile.write(data[: len(data) // 2])
                self.wfile.flush()
                self.close_connection = True
                return
            self.wfile.write(data)

    return H


@pytest.fixture
def server() -> Iterator[tuple[str, Behaviour]]:
    behaviour = Behaviour()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler(behaviour))
    Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/file.bin", behaviour
    httpd.shutdown()
    httpd.server_close()


class FakeOllama:
    """A stand-in for Ollama's HTTP API: version, tags, the NDJSON pull, and the /v1 models list."""

    def __init__(self) -> None:
        self.models: list[str] = []
        self.pull_events: list[dict[str, object]] = [
            {"status": "pulling manifest"},
            {"status": "pulling abc", "total": 1000, "completed": 250},
            {"status": "pulling abc", "total": 1000, "completed": 1000},
            {"status": "success"},
        ]
        self.pulled: list[str] = []
        self.url = ""
        self.httpd: ThreadingHTTPServer | None = None


@pytest.fixture
def fake_ollama() -> Iterator[FakeOllama]:
    import json

    fake = FakeOllama()

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_: object) -> None:
            pass

        def _json(self, body: object) -> None:
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/api/version":
                self._json({"version": "0.0-test"})
            elif self.path == "/api/tags":
                self._json({"models": [{"name": m} for m in fake.models]})
            elif self.path == "/v1/models":
                self._json({"data": [{"id": m} for m in fake.models]})
            else:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            fake.pulled.append(str(body.get("model")))
            payload = b"".join(json.dumps(e).encode() + b"\n" for e in fake.pull_events)
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            if all("error" not in e for e in fake.pull_events):
                fake.models.append(str(body.get("model")))

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
    fake.httpd = httpd
    fake.url = f"http://127.0.0.1:{httpd.server_address[1]}"
    Thread(target=httpd.serve_forever, daemon=True).start()
    yield fake
    httpd.shutdown()
    httpd.server_close()
