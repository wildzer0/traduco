"""The audit log of team mode: helper used by the endpoints and the admin's list."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from starlette.requests import HTTPConnection

from app.core.team import guard
from app.core.team.audit import AuditLog

router = APIRouter(tags=["team"])


def audit_of(conn: HTTPConnection) -> AuditLog:
    state = conn.app.state
    if getattr(state, "audit", None) is None:
        state.audit = AuditLog(guard.settings_of(conn).workspaces_path / ".traduco-audit.sqlite")
    log: AuditLog = state.audit
    return log


def note(
    conn: HTTPConnection, project: str, action: str, target: str = "", detail: str = ""
) -> None:
    """Record who did ``action``. Desktop mode has no identity, so nothing is recorded."""
    user = guard.current_user(conn)
    if user is not None:
        audit_of(conn).record(user.sub, user.label, project, action, target, detail)


@router.get("/audit")
def list_audit(
    request: Request, project: str | None = None, action: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    return [e.public() for e in audit_of(request).entries(project, action, limit)]
