"""Translation memory: suggestions for a segment, TMX export and import (RF-29)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.api.deps import Root
from app.core.segmentation.segmenter import segment
from app.core.translation import tm
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project
from app.core.workspace.sections import read_section

router = APIRouter(tags=["memory"])


@router.get("/projects/{project_id}/tm")
def summary(root: Root) -> dict[str, int]:
    return {"units": tm.count(root)}


@router.get("/projects/{project_id}/tm/suggest")
def suggest(root: Root, path: str, key: str) -> dict[str, Any]:
    """Memory entries for the source of one segment: exact first, then similar ones."""
    project = load_project(root)
    seg = segment(read_section(root, path)[0]).by_key().get(key)
    if seg is None:
        raise WorkspaceError("not_found", f"segment not found: {key}")
    found = tm.similar(root, project.lingua_sorgente, project.lingua_ufficiale, seg.source)
    return {"matches": [m.public() for m in found]}


@router.get("/projects/{project_id}/tm/export")
def export(root: Root) -> Response:
    project = load_project(root)
    return Response(
        tm.export_tmx(root, project.lingua_sorgente),
        media_type="application/x-tmx+xml",
        headers={"Content-Disposition": 'attachment; filename="memoria.tmx"'},
    )


@router.post("/projects/{project_id}/tm/import")
async def import_(root: Root, request: Request) -> dict[str, int]:
    data = await request.body()
    return {"added": tm.import_tmx(root, data)}
