"""A stand-in OpenID Connect provider: discovery, keys, authorize (PKCE) and token endpoints.

It signs real RS256 tokens, so the code under test verifies signatures, issuer, audience, expiry
and nonce exactly as it would against Keycloak.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KID = "test-key"


class FakeIdp:
    def __init__(self, client_id: str = "traduco") -> None:
        self.client_id = client_id
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.users: dict[str, dict[str, Any]] = {}
        self.codes: dict[str, dict[str, str]] = {}
        self.roles_in = "id"  # "id": in the ID token; "access": only in the access token
        self.break_nonce = False
        self.break_issuer = False
        self.server: HTTPServer | None = None
        self.url = ""

    # -- tokens --------------------------------------------------------------------------------
    def _pem(self) -> bytes:
        return self.key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    def token(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self._pem(), algorithm="RS256", headers={"kid": KID})

    def jwks(self) -> dict[str, Any]:
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        return {"keys": [{**jwk, "kid": KID, "use": "sig", "alg": "RS256"}]}

    def tokens_for(self, code: str, verifier: str) -> dict[str, Any] | None:
        pending = self.codes.pop(code, None)
        if pending is None:
            return None
        digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
        if digest.decode() != pending["challenge"]:
            return None
        user = self.users[pending["user"]]
        now = int(time.time())
        base = {
            "iss": self.url + ("/other" if self.break_issuer else ""), "sub": user["sub"],
            "iat": now, "exp": now + 300, "name": user.get("name", ""), "email": user.get("email", ""),
        }  # fmt: skip
        id_claims = {
            **base,
            "aud": self.client_id,
            "nonce": "wrong" if self.break_nonce else pending["nonce"],
        }
        access_claims = {**base, "aud": "account"}
        if self.roles_in == "id":
            id_claims["roles"] = user["roles"]
        else:
            access_claims["realm_access"] = {"roles": user["roles"]}
        return {"id_token": self.token(id_claims), "access_token": self.token(access_claims)}

    # -- the browser leg -------------------------------------------------------------------------
    def authorize(self, location: str, who: str) -> str:
        """What the provider does after a successful login: the address to go back to."""
        query = parse_qs(urlparse(location).query)
        code = secrets.token_urlsafe(16)
        self.codes[code] = {
            "challenge": query["code_challenge"][0], "nonce": query["nonce"][0], "user": who,
        }  # fmt: skip
        return f"{query['redirect_uri'][0]}?{urlencode({'code': code, 'state': query['state'][0]})}"

    # -- the server --------------------------------------------------------------------------
    def start(self) -> None:
        idp = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a: object) -> None:
                pass

            def _json(self, body: Any, status: int = 200) -> None:
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                if self.path.endswith("/.well-known/openid-configuration"):
                    self._json(
                        {
                            "issuer": idp.url,
                            "authorization_endpoint": f"{idp.url}/authorize",
                            "token_endpoint": f"{idp.url}/token",
                            "jwks_uri": f"{idp.url}/jwks",
                        }  # fmt: skip
                    )
                elif self.path == "/jwks":
                    self._json(idp.jwks())
                else:
                    self._json({}, 404)

            def do_POST(self) -> None:
                form = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
                tokens = idp.tokens_for(
                    form.get("code", [""])[0], form.get("code_verifier", [""])[0]
                )
                self._json(tokens or {"error": "invalid_grant"}, 200 if tokens else 400)

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
