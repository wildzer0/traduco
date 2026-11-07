"""Translation endpoints: segments of a section, bulk retranslation, model status."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import Root
from app.core.translation import glossary as glossary_mod
from app.core.translation.service import PRIORITY_OPEN, SegmentActions, TranslationService
from app.core.translation.store import load as load_segments
from app.core.workspace import frontmatter
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import sha256_text
from app.core.workspace.manifest import load_project
from app.core.workspace.ops import resolve_node
from app.core.workspace.sections import read_section, write_section
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


# --- glossary ------------------------------------------------------------------------------


@router.get("/projects/{project_id}/glossary")
def get_glossary(root: Root) -> list[dict[str, Any]]:
    return [e.model_dump() for e in glossary_mod.load(root)]


@router.put("/projects/{project_id}/glossary")
def put_glossary(root: Root, entries: list[glossary_mod.Entry]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    for e in entries:
        key = e.sorgente.casefold()
        if key in seen:
            raise WorkspaceError("exists", f"duplicate glossary term: {e.sorgente}")
        seen.add(key)
    glossary_mod.save(root, entries)
    return [e.model_dump() for e in glossary_mod.load(root)]


# --- segments ------------------------------------------------------------------------------


class SegmentPut(BaseModel):
    """One change: a manual ``target``, a ``locked`` flag, or an ``action``."""

    target: str | None = None
    locked: bool | None = None
    action: Literal["approve", "accept", "dismiss", "retranslate", "diverge"] | None = None


class Instruct(BaseModel):
    instruction: str = Field(min_length=1, max_length=500)
    alternatives: bool = False


class ApplySource(BaseModel):
    text: str = Field(min_length=1)


def _row(
    service: TranslationService, root: Any, project: Any, path: str, key: str
) -> dict[str, Any]:
    text, _ = read_section(root, path)
    for row in service.translation(root, project, path, text)["segments"]:
        if row["key"] == key:
            return dict(row)
    raise WorkspaceError("not_found", f"segment not found: {key}")


@router.put("/projects/{project_id}/segments/{key}")
def put_segment(
    root: Root, service: Service, key: str, body: SegmentPut, path: str = Query(...)
) -> dict[str, Any]:
    project = load_project(root)
    actions = SegmentActions(service)
    given = [v for v in (body.target, body.locked, body.action) if v is not None]
    if len(given) != 1:
        raise WorkspaceError("invalid_path", "send exactly one of target, locked, action")
    if body.target is not None:
        actions.edit(root, project, path, key, body.target)
    elif body.locked is not None:
        actions.lock(root, project, path, key, body.locked)
    elif body.action == "approve":
        actions.approve(root, project, path, key)
    elif body.action == "accept":
        actions.accept_pending(root, project, path, key)
    elif body.action == "dismiss":
        actions.dismiss_pending(root, project, path, key)
    elif body.action == "diverge":
        actions.mark_diverged(root, project, path, key)
    elif body.action == "retranslate":
        actions.retranslate(root, project, path, key)
    return _row(service, root, project, path, key)


@router.post("/projects/{project_id}/segments/{key}/instruct")
async def instruct(
    root: Root, service: Service, key: str, body: Instruct, path: str = Query(...)
) -> dict[str, list[str]]:
    proposals = await SegmentActions(service).revise(
        root, load_project(root), path, key, body.instruction, body.alternatives
    )
    return {"proposals": proposals}


@router.post("/projects/{project_id}/segments/{key}/back-translate")
async def back_translate(
    root: Root, service: Service, key: str, path: str = Query(...)
) -> dict[str, str]:
    text = await SegmentActions(service).back_translate(root, load_project(root), path, key)
    return {"text": text}


@router.post("/projects/{project_id}/segments/{key}/apply-source")
def apply_source(
    root: Root, service: Service, key: str, body: ApplySource, path: str = Query(...)
) -> dict[str, Any]:
    project = load_project(root)
    SegmentActions(service).apply_source(root, project, path, key, body.text)
    return _row(service, root, project, path, key)


@router.get("/projects/{project_id}/review")
def review(root: Root, service: Service) -> dict[str, Any]:
    rows = service.review(root, load_project(root))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"segments": rows, "counts": counts}


# --- per-section settings (tone, context note) ----------------------------------------------


class SectionMeta(BaseModel):
    """``tono`` and ``contesto`` of the section front matter; ``null`` removes the key."""

    tono: Literal["formale", "neutro", "informale"] | None = None
    contesto: str | None = None


@router.patch("/projects/{project_id}/sections/meta")
def patch_section_meta(root: Root, body: SectionMeta, path: str = Query(...)) -> dict[str, Any]:
    text, digest = read_section(root, path)
    doc = frontmatter.parse(text)
    for key, value in (("tono", body.tono), ("contesto", (body.contesto or "").strip() or None)):
        if value is None:
            doc.meta.pop(key, None)
        else:
            doc.meta[key] = value
    write_section(root, path, frontmatter.render(doc), digest)
    return {"tono": doc.meta.get("tono"), "contesto": doc.meta.get("contesto", "")}
