"""Export jobs: start, follow the progress, download (RF-60)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.audit import note
from app.api.deps import Root
from app.core.export import preflight
from app.core.export.errors import ExportError
from app.core.export.service import (
    ExportManager,
    ExportRequest,
    Format,
    Language,
    Scope,
    _select,
)
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project
from app.core.workspace.tree import build_tree

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
    draft: Literal["auto", "off"] = "auto"
    language: Language = Field(default="ufficiale", min_length=2, max_length=20)
    template: str | None = None
    format: Format = "docx"


@router.post("/projects/{project_id}/export", status_code=202)
async def start_export(
    request: Request, root: Root, manager: Manager, body: ExportBody
) -> dict[str, Any]:
    if body.scope != "project" and not body.path:
        raise WorkspaceError("invalid_path", "path is required for a section or a chapter")
    job = manager.start(root, load_project(root), ExportRequest(**body.model_dump()))
    note(request, root.name, "export", body.path or body.scope, f"{body.language} {body.format}")
    return job.public()


@router.post("/projects/{project_id}/export/check")
def check_export(request: Request, root: Root, body: ExportBody) -> dict[str, Any]:
    """Problems the export would hide, found beforehand. Never blocks anything."""
    if body.scope != "project" and not body.path:
        raise WorkspaceError("invalid_path", "path is required for a section or a chapter")
    selected = _select(build_tree(root), ExportRequest(**body.model_dump()))
    sections = [n.path for n, _ in selected if n.kind == "section"]
    scope = set(sections)
    findings: list[preflight.Finding] = []
    for rel in sections:
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings += preflight.check_section(root, rel, text, scope)
    if body.language in ("ufficiale", "bilingue"):
        project = load_project(root)
        rows = request.app.state.translation.review(root, project)
        findings += preflight.check_review(rows, scope)
    return {"findings": [f.public() for f in findings]}


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
