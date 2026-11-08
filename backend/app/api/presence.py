"""Presence and section locks in team mode (RF-93). Desktop mode has one user: nothing to do."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.requests import HTTPConnection

from app.api.deps import Root  # noqa: F401  (validates the project id like every project route)
from app.core.team import guard
from app.core.team.coordination import Coordination, MemoryCoordination
from app.core.team.identity import User

router = APIRouter(tags=["team"])


class Beat(BaseModel):
    path: str | None = None  # the section the person has open
    edit: bool = False  # they want to edit it: take the lock if nobody has it


def coordination_of(conn: HTTPConnection) -> Coordination:
    state = conn.app.state
    if getattr(state, "coordination", None) is None:
        state.coordination = MemoryCoordination()
    coordination: Coordination = state.coordination
    return coordination


def lock_write(request: Request, project_id: str, path: str) -> None:
    """Called before a section is written: refuse (423) if someone else is editing it."""
    user: User | None = guard.current_user(request)
    if user is not None:
        coordination_of(request).check_write(project_id, user, path)


def _view(request: Request, project_id: str, me: User) -> dict[str, Any]:
    seats = coordination_of(request).seats(project_id)
    return {
        "me": me.sub,
        "people": [
            {"sub": s.sub, "name": s.name, "path": s.path, "editing": s.editing} for s in seats
        ],
    }


@router.post("/projects/{project_id}/presence")
def heartbeat(request: Request, project_id: str, body: Beat) -> dict[str, Any]:
    user = guard.current_user(request)
    if user is None:  # desktop mode
        return {"me": "", "people": []}
    coordination_of(request).heartbeat(
        project_id, user, body.path, body.edit and user.can("edit_source")
    )
    return _view(request, project_id, user)


@router.get("/projects/{project_id}/presence")
def presence(request: Request, project_id: str) -> dict[str, Any]:
    user = guard.current_user(request)
    if user is None:
        return {"me": "", "people": []}
    return _view(request, project_id, user)
