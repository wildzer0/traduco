"""Company templates of a project: upload, analysis, style mapping, default (RF-50..52, RF-56)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.deps import Root
from app.core.templates import store
from app.core.templates.analyze import MAX_TEMPLATE_BYTES, Analysis
from app.core.templates.mapping import ROLES, Mapping
from app.core.workspace.errors import WorkspaceError

router = APIRouter(tags=["templates"])


def _detail(name: str, analysis: Analysis, mapping: Mapping, problems: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "styles": [asdict(s) for s in analysis.styles if s.kind in ("paragraph", "table")],
        "placeholders": [asdict(p) for p in analysis.placeholders],
        "fields": analysis.fields,
        "has_content": analysis.has_content,
        "has_revisions": analysis.has_revisions,
        "has_toc": analysis.has_toc,
        "roles": list(ROLES),
        "mapping": mapping.model_dump(),
        "problems": problems,
    }


@router.get("/projects/{project_id}/templates")
def list_templates(root: Root) -> list[dict[str, Any]]:
    return [asdict(t) for t in store.list_templates(root)]


@router.post("/projects/{project_id}/templates", status_code=201)
async def upload_template(
    root: Root, request: Request, filename: str = Query(...)
) -> dict[str, Any]:
    """Raw ``.docx`` bytes in the body; analysed and saved with a proposed style mapping."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_TEMPLATE_BYTES:
        raise WorkspaceError("too_large", "the template is larger than 50 MB")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_TEMPLATE_BYTES:
            raise WorkspaceError("too_large", "the template is larger than 50 MB")
    name = store.import_template(root, filename, bytes(data))
    return _detail(name, *store.describe(root, name))


@router.get("/projects/{project_id}/templates/{name}")
def get_template(root: Root, name: str) -> dict[str, Any]:
    return _detail(name, *store.describe(root, name))


@router.put("/projects/{project_id}/templates/{name}")
def put_mapping(root: Root, name: str, mapping: Mapping) -> dict[str, Any]:
    store.update_mapping(root, name, mapping)
    return _detail(name, *store.describe(root, name))


@router.put("/projects/{project_id}/templates/{name}/default")
def make_default(root: Root, name: str) -> dict[str, str]:
    store.set_default(root, name)
    return {"default": name}


@router.delete("/projects/{project_id}/templates/{name}", status_code=204)
def delete_template(root: Root, name: str) -> None:
    store.delete_template(root, name)
