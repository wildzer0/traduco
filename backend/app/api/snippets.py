"""Project snippets: list, edit the file, expand one (RF-86)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import Root
from app.core.export.service import format_value
from app.core.snippets import model
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project
from app.core.workspace.sections import read_section
from app.core.workspace.tree import section_title

router = APIRouter(tags=["snippets"])


def _listing(root: Any) -> dict[str, Any]:
    raw = model.read_raw(root)
    try:
        parsed = model.parse(raw)
    except WorkspaceError as exc:
        return {"snippets": [], "counters": [], "raw": raw, "error": exc.message}
    return {
        "snippets": [s.model_dump() for s in parsed.snippet],
        "counters": model.counters(root),
        "raw": raw,
        "error": None,
    }


@router.get("/projects/{project_id}/snippets")
def list_snippets(root: Root) -> dict[str, Any]:
    return _listing(root)


class RawFile(BaseModel):
    text: str


@router.put("/projects/{project_id}/snippets")
def save_snippets(root: Root, body: RawFile) -> dict[str, Any]:
    model.save_raw(root, body.text)
    return _listing(root)


class Expand(BaseModel):
    path: str | None = None


@router.post("/projects/{project_id}/snippets/{alias}/expand")
def expand(root: Root, alias: str, body: Expand) -> dict[str, str]:
    project = load_project(root)
    title = ""
    if body.path:
        read_section(root, body.path)  # validates the path
        title = section_title(root / body.path)
    text = model.expand(
        root,
        alias,
        title=title,
        project=project.nome,
        today=date.today(),
        language_date=format_value(date.today(), project.lingua_sorgente),
    )
    return {"text": text}
