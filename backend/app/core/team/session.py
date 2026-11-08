"""Signed session cookies for team mode: no session store, any process can check one."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from .identity import User

COOKIE = "traduco_session"
OIDC_COOKIE = "traduco_oidc"  # the short-lived state of a login in progress


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(payload: dict[str, Any], secret: str, ttl_seconds: int) -> str:
    body = {**payload, "exp": int(time.time()) + ttl_seconds}
    raw = _b64(json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode())
    mac = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
    return f"{raw}.{_b64(mac)}"


def verify(token: str | None, secret: str) -> dict[str, Any] | None:
    """The payload of a token we signed and that has not expired; otherwise ``None``."""
    if not token or "." not in token or not secret:
        return None
    raw, _, mac = token.partition(".")
    expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(_unb64(mac), expected):
            return None
        body = json.loads(_unb64(raw))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(body, dict) or int(body.get("exp", 0)) < time.time():
        return None
    return body


def session_token(user: User, secret: str, hours: int) -> str:
    return sign(
        {"sub": user.sub, "name": user.name, "email": user.email, "roles": list(user.roles)},
        secret,
        hours * 3600,
    )


def user_from_token(token: str | None, secret: str) -> User | None:
    body = verify(token, secret)
    if body is None or not body.get("sub"):
        return None
    return User(
        str(body["sub"]), str(body.get("name", "")), str(body.get("email", "")),
        tuple(str(r) for r in body.get("roles", [])),
    )  # fmt: skip
