"""Spelling and grammar of the source language with LanguageTool (RF-16, optional)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import Root
from app.config import Settings, get_settings
from app.core.segmentation.segmenter import segment
from app.core.spellcheck import languagetool
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project
from app.core.workspace.sections import read_section

router = APIRouter(tags=["spellcheck"])
MAX_SEGMENTS = 400
SKIPPED = {"title", "table_header", "table_cell"}


class SpellBody(BaseModel):
    path: str


@router.post("/projects/{project_id}/spellcheck")
async def spellcheck(
    root: Root, body: SpellBody, settings: Annotated[Settings, Depends(get_settings)]
) -> dict[str, Any]:
    if not settings.languagetool_url:
        raise WorkspaceError(
            "invalid_state", "LanguageTool is not set up: see TRADUCO_LANGUAGETOOL_URL"
        )
    project = load_project(root)
    text, _ = read_section(root, body.path)
    issues: list[dict[str, Any]] = []
    for seg in segment(text).segments[:MAX_SEGMENTS]:
        if seg.kind in SKIPPED:
            continue
        for match in await languagetool.check(
            settings.languagetool_url, project.lingua_sorgente, seg.source
        ):
            end = match["offset"] + match["length"]
            issues.append(
                {
                    **match,
                    "key": seg.key,
                    "context": seg.source,
                    "word": seg.source[match["offset"] : end],
                }
            )
    return {"language": project.lingua_sorgente, "issues": issues}
