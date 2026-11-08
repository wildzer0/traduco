#!/usr/bin/env python3
"""A tiny login server to try Traduco's team mode without Keycloak (development only!).

It lets you pick who you are from a list: there are no passwords. Never use it on a real server.

    cd backend && uv run python ../tools/dev-idp.py     # listens on http://127.0.0.1:9100
    # in another terminal, from the repository root:
    TRADUCO_MODE=team TRADUCO_OIDC_ISSUER=http://127.0.0.1:9100 TRADUCO_OIDC_CLIENT_SECRET=x \\
    TRADUCO_SESSION_SECRET=$(openssl rand -hex 32) ./start.sh

Open http://localhost:8000 as one user and http://127.0.0.1:8000 (or a private window) as another.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from tests.support.fake_idp import FakeIdp  # noqa: E402

USERS = {
    "carla": {"sub": "u-carla", "name": "Carla (amministratrice)", "roles": ["admin"]},
    "anna": {"sub": "u-anna", "name": "Anna (autrice)", "roles": ["author"]},
    "elena": {"sub": "u-elena", "name": "Elena (autrice)", "roles": ["author"]},
    "bruno": {"sub": "u-bruno", "name": "Bruno (revisore)", "roles": ["reviewer"]},
}


def serve(port: int) -> None:
    idp = FakeIdp()
    idp.users = dict(USERS)
    idp.url = f"http://127.0.0.1:{port}"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a: object) -> None:
            pass

        def _send(self, body: bytes, kind: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, body: Any, status: int = 200) -> None:
            self._send(json.dumps(body).encode(), "application/json", status)

        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path.endswith("/.well-known/openid-configuration"):
                self._json(
                    {
                        "issuer": idp.url,
                        "authorization_endpoint": f"{idp.url}/authorize",
                        "token_endpoint": f"{idp.url}/token",
                        "jwks_uri": f"{idp.url}/jwks",
                    }
                )
            elif url.path == "/jwks":
                self._json(idp.jwks())
            elif url.path == "/authorize":
                query = html.escape(url.query, quote=True)
                rows = "".join(
                    f'<li><a href="/pick?who={who}&amp;{query}">{html.escape(u["name"])}</a></li>'
                    for who, u in USERS.items()
                )
                page = f"<h1>Traduco - accesso di prova</h1><p>Chi sei?</p><ul>{rows}</ul>"
                self._send(page.encode(), "text/html; charset=utf-8")
            elif url.path == "/pick":
                query = parse_qs(url.query)
                back = idp.authorize(f"/authorize?{url.query}", query["who"][0])
                self.send_response(302)
                self.send_header("Location", back)
                self.end_headers()
            else:
                self._json({}, 404)

        def do_POST(self) -> None:
            form = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            tokens = idp.tokens_for(form.get("code", [""])[0], form.get("code_verifier", [""])[0])
            self._json(tokens or {"error": "invalid_grant"}, 200 if tokens else 400)

    print(f"Accesso di prova su {idp.url} (nessuna password: solo per sviluppo)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=9100)
    serve(parser.parse_args().port)
