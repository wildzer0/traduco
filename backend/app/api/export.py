"""Export jobs: start, follow the progress, download (RF-60)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import Root
from app.core.export.errors import ExportError
from app.core.export.service import ExportManager, ExportRequest, Format, Language, Scope
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project

router = APIRouter(tags=["export"])
MEDIA = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".html": "text/html; charset=utf-8",
    ".epub": "application/epub+zip",
    ".md": "text/markdown; charset=utf-8",
    ".zip": "application/zip",
}


def get_manager(request: Request) -> ExportManager:
    manager: ExportManager = request.app.state.exports
    return manager


Manager = Annotated[ExportManager, Depends(get_manager)]


class ExportBody(BaseModel):
    scope: Scope = "project"
    path: str | None = None
    language: Language = "ufficiale"
    template: str | None = None
    format: Format = "docx"


@router.post("/projects/{project_id}/export", status_code=202)
async def start_export(root: Root, manager: Manager, body: ExportBody) -> dict[str, Any]:
    if body.scope != "project" and not body.path:
        raise WorkspaceError("invalid_path", "path is required for a section or a chapter")
    job = manager.start(root, load_project(root), ExportRequest(**body.model_dump()))
    return job.public()


def _job(manager: ExportManager, root: Any, job_id: str) -> Any:
    job = manager.get(job_id)
    if job is None:
        raise WorkspaceError("not_found", "export not found")
    return job


@router.get("/projects/{project_id}/export/{job_id}")
def export_status(root: Root, manager: Manager, job_id: str) -> dict[str, Any]:
    return dict(_job(manager, root, job_id).public())


@router.get("/projects/{project_id}/export/{job_id}/download")
def download(root: Root, manager: Manager, job_id: str) -> FileResponse:
    job = _job(manager, root, job_id)
    if job.state != "done" or job.file is None or not job.file.is_file():
        raise ExportError("not_ready", "the export is not finished")
    return FileResponse(
        job.file,
        media_type=MEDIA.get(job.file.suffix, "application/octet-stream"),
        filename=job.file.name,
    )
