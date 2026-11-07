"""Fake OpenAI-compatible server (standard library only, see ADR-016).

Behaviour of ``POST /v1/chat/completions``: the text of the last ``user`` message (or only the
part wrapped in ``<source>...</source>`` if present) is returned prefixed with ``FAKE_LLM_PREFIX``
(default ``"[EN] "``). The text is echoed verbatim, so placeholders such as ``⟦1⟧`` are preserved.

Modes (env ``FAKE_LLM_MODE`` or per-request header ``X-Fake-Mode``):
  ok                  normal reply
  error               HTTP 500 with an OpenAI-style error body
  slow                normal reply after ``FAKE_LLM_DELAY`` seconds (default 2)
  glossary-violation  reply that also contains ``FAKE_LLM_VIOLATION_TERM`` (default ``offer``)

It also answers the few Ollama endpoints the launcher uses (``/api/version``, ``/api/tags``,
``/api/pull``), so the clean-start CI can run the whole first-start flow without Ollama.
"""

from __future__ import annotations

import json
import os
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MODES = ("ok", "error", "slow", "glossary-violation")
# Models "installed" in the fake Ollama; /api/pull adds the requested one (clean-start CI).
INSTALLED: list[str] = []
MODEL_ID = "fake-model"
_SOURCE_RE = re.compile(r"<source>(.*?)</source>", re.DOTALL)


def extract_source(messages: list[dict[str, Any]]) -> str:
    users = [m for m in messages if m.get("role") == "user"]
    content = str(users[-1].get("content", "")) if users else ""
    match = _SOURCE_RE.search(content)
    return match.group(1).strip() if match else content


def build_reply(text: str, mode: str, prefix: str, violation_term: str) -> str:
    reply = f"{prefix}{text}"
    if mode == "glossary-violation":
        reply = f"{reply} {violation_term}"
    return reply


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # keep test output quiet
        if os.environ.get("FAKE_LLM_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _mode(self) -> str:
        mode = self.headers.get("X-Fake-Mode") or os.environ.get("FAKE_LLM_MODE", "ok")
        return mode if mode in MODES else "ok"

    def do_GET(self) -> None:
        if self.path == "/api/version":
            self._send(200, {"version": "0.0.0-fake"})
        elif self.path == "/api/tags":
            self._send(200, {"models": [{"name": m} for m in INSTALLED]})
        elif self.path in ("/v1/models", "/models"):
            self._send(
                200,
                {
                    "object": "list",
                    "data": [{"id": MODEL_ID, "object": "model", "owned_by": "fake-llm"}],
                },
            )
        elif self.path == "/health":
            self._send(200, {"status": "ok"})
        else:
            self._send(404, {"error": {"message": "not found", "type": "not_found"}})

    def _pull(self) -> None:
        """Ollama's NDJSON pull: a few progress lines, then the model counts as installed."""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            model = str(json.loads(self.rfile.read(length) or b"{}").get("model", ""))
        except ValueError:
            model = ""
        lines = [
            {"status": "pulling manifest"},
            {"status": "pulling blob", "total": 1000, "completed": 400},
            {"status": "pulling blob", "total": 1000, "completed": 1000},
            {"status": "success"},
        ]
        payload = b"".join(json.dumps(line).encode() + b"\n" for line in lines)
        if model and model not in INSTALLED:
            INSTALLED.append(model)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if self.path == "/api/pull":
            self._pull()
            return
        if self.path not in ("/v1/chat/completions", "/chat/completions"):
            self._send(404, {"error": {"message": "not found", "type": "not_found"}})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            messages = payload["messages"]
            if not isinstance(messages, list):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            self._send(400, {"error": {"message": "invalid request", "type": "invalid_request"}})
            return
        mode = self._mode()
        if mode == "error":
            self._send(500, {"error": {"message": "simulated failure", "type": "server_error"}})
            return
        if mode == "slow":
            time.sleep(float(os.environ.get("FAKE_LLM_DELAY", "2")))
        reply = build_reply(
            extract_source(messages),
            mode,
            os.environ.get("FAKE_LLM_PREFIX", "[EN] "),
            os.environ.get("FAKE_LLM_VIOLATION_TERM", "offer"),
        )
        self._send(
            200,
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": payload.get("model", MODEL_ID),
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": reply},
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )


def make_server(host: str = "127.0.0.1", port: int = 11500) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    host = os.environ.get("FAKE_LLM_HOST", "127.0.0.1")
    port = int(os.environ.get("FAKE_LLM_PORT", "11500"))
    server = make_server(host, port)
    mode = os.environ.get("FAKE_LLM_MODE", "ok")
    print(f"fake-llm listening on http://{host}:{port}/v1 (mode={mode})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
