"""Login with the organisation's identity provider (team mode) and "who am I"."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.team import session
from app.core.team.guard import settings_of, user_of
from app.core.team.oidc import OidcClient, OidcError

log = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["auth"])
LOGIN_SECONDS = 600


def _redirect_uri(request: Request) -> str:
    base = settings_of(request).public_url.rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/auth/callback"


def _safe_next(target: str) -> str:
    """Only a path on this site: no ``//host`` or ``https://…`` (open redirect)."""
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return "/"
    return target


def _client(request: Request) -> OidcClient:
    client: OidcClient | None = getattr(request.app.state, "oidc", None)
    if client is None:
        raise OidcError("team mode is not set up")
    return client


def _cookie_args(request: Request) -> dict[str, Any]:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": request.url.scheme == "https",
        "path": "/",
    }


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    settings = settings_of(request)
    if settings.mode != "team":
        return {"mode": "desktop", "user": None}
    user = user_of(request)
    return {"mode": "team", "user": user.public() if user else None}


@router.get("/auth/login")
async def login(request: Request, next: str = "/") -> Any:
    settings = settings_of(request)
    if settings.mode != "team":
        return RedirectResponse("/")
    try:
        url, remembered = await _client(request).start(_redirect_uri(request), _safe_next(next))
    except OidcError as exc:
        log.warning("login unavailable: %s", exc)
        return JSONResponse({"error": {"code": "login_unavailable", "message": str(exc)}}, 503)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        session.OIDC_COOKIE, session.sign(remembered, settings.session_secret, LOGIN_SECONDS),
        max_age=LOGIN_SECONDS, **_cookie_args(request),
    )  # fmt: skip
    return response


@router.get("/auth/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = "") -> Any:
    settings = settings_of(request)
    remembered = session.verify(request.cookies.get(session.OIDC_COOKIE), settings.session_secret)
    try:
        if error or not code:
            raise OidcError("the identity provider did not confirm the login")
        user = await _client(request).finish(
            code, state, {k: str(v) for k, v in (remembered or {}).items()}, _redirect_uri(request)
        )
    except OidcError as exc:
        log.warning("login refused: %s", exc)  # the browser only shows a line of JSON
        return JSONResponse({"error": {"code": "login_failed", "message": str(exc)}}, 403)
    response = RedirectResponse(
        _safe_next(str((remembered or {}).get("next", "/"))), status_code=302
    )
    token = session.session_token(user, settings.session_secret, settings.session_hours)
    response.set_cookie(
        session.COOKIE, token, max_age=settings.session_hours * 3600, **_cookie_args(request)
    )
    response.delete_cookie(session.OIDC_COOKIE, path="/")
    return response


@router.post("/auth/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(session.COOKIE, path="/")
    return response
