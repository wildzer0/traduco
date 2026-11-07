"""Search the text of the project (command palette, Ctrl+Shift+F)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import Root
from app.core.search import text
from app.core.workspace.manifest import load_project

router = APIRouter(tags=["search"])


@router.get("/projects/{project_id}/search")
def search(
    root: Root, q: str = Query(max_length=200), limit: int = Query(50, ge=1, le=200)
) -> dict[str, Any]:
    project = load_project(root)
    return {"query": q, "hits": text.search(root, q, project.lingua_ufficiale, limit=limit)}
