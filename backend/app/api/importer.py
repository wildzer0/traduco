"""Import a revised Word file: follow the job, decide on each proposal (RF-65, RF-66)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.audit import note
from app.api.deps import Root
from app.core.importer.service import ImportManager
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project

router = APIRouter(tags=["import"])
MAX_BYTES = 50 * 1024 * 1024


def get_manager(request: Request) -> ImportManager:
    manager: ImportManager = request.app.state.imports
    return manager


Manager = Annotated[ImportManager, Depends(get_manager)]


@router.post("/projects/{project_id}/import", status_code=202)
async def start_import(
    root: Root, manager: Manager, request: Request, filename: str = "revised.docx"
) -> dict[str, Any]:
    data = await request.body()
    if not data:
        raise WorkspaceError("invalid_template", "the file is empty")
    if len(data) > MAX_BYTES:
        raise WorkspaceError("invalid_template", "the file is larger than 50 MB")
    return manager.start(root, load_project(root), data, filename).public()


@router.get("/projects/{project_id}/import/{job_id}")
def import_status(root: Root, manager: Manager, job_id: str) -> dict[str, Any]:
    job = manager.get(root, job_id)
    if job is None:
        raise WorkspaceError("not_found", "import not found")
    return job.public()


class Decision(BaseModel):
    action: Literal["accept", "reject"]
    source: str | None = None


@router.post("/projects/{project_id}/import/{job_id}/proposals/{proposal_id}")
def decide(
    request: Request, root: Root, manager: Manager, job_id: str, proposal_id: str, body: Decision
) -> dict[str, Any]:
    done = manager.decide(root, load_project(root), job_id, proposal_id, body.action, body.source)
    note(request, root.name, f"import.{body.action}", proposal_id, job_id)
    return dict(done.__dict__)
