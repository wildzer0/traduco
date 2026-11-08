"""The login check in front of every route when the server runs in team mode."""

from __future__ import annotations

from fastapi import HTTPException
from starlette.requests import HTTPConnection

from app.config import Settings, get_settings

from . import policy, session
from .identity import User

PUBLIC = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/callback",
    "/api/auth/logout",
    "/api/me",  # answers "nobody" instead of an error, so the page knows to send people to log in
}


def settings_of(conn: HTTPConnection) -> Settings:
    return conn.app.dependency_overrides.get(get_settings, get_settings)()  # type: ignore[no-any-return]


def user_of(conn: HTTPConnection) -> User | None:
    """The user of the session cookie, if it is valid."""
    return session.user_from_token(
        conn.cookies.get(session.COOKIE), settings_of(conn).session_secret
    )


API_PREFIX = "/api"


def route_template(conn: HTTPConnection) -> str:
    """The full path template of the matched route (``/api/projects/{project_id}/files``).

    Starlette reports a route's path relative to the router it was included in, so the ``/api``
    prefix, which every router gets in ``create_app``, is put back. Anything that is not under
    ``/api`` (the built frontend) is not a route of ours.
    """
    path = conn.url.path
    if not path.startswith(API_PREFIX + "/") and path != API_PREFIX:
        return path
    route = conn.scope.get("route")
    relative = getattr(route, "path", None)
    if relative is None:
        return path  # no route matched: a 404 is coming, nothing to protect
    return str(relative) if str(relative).startswith(API_PREFIX) else API_PREFIX + str(relative)


async def authorize(conn: HTTPConnection) -> None:
    """Global dependency: nothing in desktop mode; in team mode login + permission per route."""
    settings = settings_of(conn)
    if settings.mode != "team":
        conn.state.user = None
        return
    template = route_template(conn)
    if template in PUBLIC or not template.startswith(API_PREFIX):
        conn.state.user = user_of(conn)
        return
    user = user_of(conn)
    if user is None:
        raise HTTPException(status_code=401, detail="log in first")
    needed = policy.required(getattr(conn, "method", "WS"), template)
    if not user.can(needed):
        raise HTTPException(status_code=403, detail=f"this needs the permission: {needed}")
    conn.state.user = user


def require(conn: HTTPConnection, permission: str) -> None:
    """A finer check inside an endpoint (for example approving a translation)."""
    if settings_of(conn).mode != "team":
        return
    user: User | None = getattr(conn.state, "user", None)
    if user is None or not user.can(permission):
        raise HTTPException(status_code=403, detail=f"this needs the permission: {permission}")


def current_user(conn: HTTPConnection) -> User | None:
    user: User | None = getattr(conn.state, "user", None)
    return user
