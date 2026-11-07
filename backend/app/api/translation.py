"""Translation endpoints: segments of a section, bulk retranslation, model status."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.api.deps import Root
from app.core.translation.service import PRIORITY_OPEN, TranslationService
from app.core.translation.store import load as load_segments
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import sha256_text
from app.core.workspace.manifest import load_project
from app.core.workspace.ops import resolve_node
from app.core.workspace.sections import read_section
from app.core.workspace.tree import CHAPTERS_DIR

router = APIRouter(tags=["translation"])


def get_service(request: Request) -> TranslationService:
    service: TranslationService = request.app.state.translation
    return service


Service = Annotated[TranslationService, Depends(get_service)]


class RetranslateBody(BaseModel):
    scope: Literal["section", "chapter", "project"]
    path: str | None = None


@router.get("/projects/{project_id}/translation")
def get_translation(
    root: Root, service: Service, path: str = Query(...), lang: str | None = None
) -> dict[str, Any]:
    project = load_project(root)
    if lang is not None and lang != project.lingua_ufficiale:
        raise WorkspaceError("not_found", f"language not configured yet: {lang}")
    text, _ = read_section(root, path)
    stored = load_segments(root, project.lingua_ufficiale, path)
    if stored is None or stored.source_file_hash != sha256_text(text):
        service.sync(root, project, path, text, PRIORITY_OPEN)
    return service.translation(root, project, path, text)


@router.post("/projects/{project_id}/retranslate")
def retranslate(root: Root, service: Service, body: RetranslateBody) -> dict[str, int]:
    project = load_project(root)
    if body.scope == "project":
        base = root / CHAPTERS_DIR
    else:
        if not body.path:
            raise WorkspaceError("invalid_path", "path is required for this scope")
        base = resolve_node(root, body.path)
    files = [base] if base.is_file() else sorted(base.rglob("*.md"))
    rels = [f.relative_to(root).as_posix() for f in files if f.suffix == ".md"]
    queued = service.retranslate(root, project, rels)
    return {"sections": len(rels), "queued": queued}


@router.get("/llm/status")
async def llm_status(service: Service) -> dict[str, Any]:
    return await service.status()
