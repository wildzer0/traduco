"""Writing companion endpoints: improve a segment, check a section, apply a suggestion."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import Root
from app.core.companion import check as check_mod
from app.core.companion.improve import AssistContext, improve
from app.core.segmentation.assembler import assemble
from app.core.segmentation.segmenter import segment
from app.core.skeleton import generate as skeleton_gen
from app.core.skeleton.model import SkeletonError
from app.core.translation import glossary as glossary_mod
from app.core.translation.llm_client import LlmError
from app.core.translation.service import PRIORITY_EDIT, TranslationService, refusal
from app.core.workspace import frontmatter
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import Project, load_project
from app.core.workspace.sections import read_section, write_section

router = APIRouter(tags=["companion"])


def get_service(request: Request) -> TranslationService:
    service: TranslationService = request.app.state.translation
    return service


Service = Annotated[TranslationService, Depends(get_service)]


class AssistBody(BaseModel):
    path: str
    key: str
    action: Literal["correct", "rephrase", "concise", "simple", "formale", "neutro", "informale"]
    instruction: str = Field(default="", max_length=500)


class ApplyBody(BaseModel):
    path: str
    key: str
    text: str = Field(min_length=1)
    suggestion_id: str | None = None


class CheckBody(BaseModel):
    path: str
    requirements: bool = False


class DismissBody(BaseModel):
    path: str
    suggestion_id: str


def _guide(root: Any, meta: dict[str, Any]) -> str:
    tag = meta.get(skeleton_gen.TAG)
    if not tag:
        return ""
    try:
        loaded = skeleton_gen.load(root)
    except SkeletonError:
        return ""
    if loaded is None:
        return ""
    return next((n.guida for n, _ in loaded[0].walk() if n.id == tag), "")


def _context(root: Any, project: Project, text: str) -> AssistContext:
    try:
        meta = frontmatter.parse(text).meta
    except frontmatter.FrontMatterError:
        meta = {}
    try:
        entries = glossary_mod.load(root)
    except WorkspaceError:
        entries = []
    doc = segment(text)
    title = str(meta.get("title") or "") or next(
        (s.source for s in doc.segments if s.kind == "heading"), ""
    )
    return AssistContext(
        language=project.lingua_sorgente,
        tone=str(meta.get("tono") or project.tono),
        section_title=title,
        note=str(meta.get("contesto") or ""),
        guide=_guide(root, meta),
        glossary=tuple(entries),
    )


def _client(service: TranslationService, project: Project) -> Any:
    return service._client(*service._config_for(project))


@router.post("/projects/{project_id}/assist")
async def assist(root: Root, service: Service, body: AssistBody) -> dict[str, Any]:
    """A proposal for the source text of one segment. Nothing is saved."""
    project = load_project(root)
    text, _ = read_section(root, body.path)
    seg = segment(text).by_key().get(body.key)
    if seg is None:
        raise WorkspaceError("not_found", f"segment not found: {body.key}")
    ctx = _context(root, project, text)
    # glossary entries that matter for this segment only
    ctx = AssistContext(
        ctx.language, ctx.tone, ctx.section_title, ctx.note, ctx.guide,
        tuple(glossary_mod.relevant(list(ctx.glossary), seg.source)),
    )  # fmt: skip
    try:
        outcome = await improve(
            _client(service, project), seg.source, body.action, ctx, instruction=body.instruction
        )
    except LlmError as exc:
        raise WorkspaceError("model_refused", str(exc)) from exc
    if not outcome.ok:
        raise refusal(outcome.reason)
    return {
        "original": seg.source,
        "proposal": outcome.target,
        "changed": outcome.target.strip() != seg.source.strip(),
    }


@router.post("/projects/{project_id}/assist/apply")
def apply(root: Root, service: Service, body: ApplyBody) -> dict[str, Any]:
    """Write an accepted proposal into the section; only that segment is translated again."""
    project = load_project(root)
    text, digest = read_section(root, body.path)
    doc = segment(text)
    if body.key not in doc.by_key():
        raise WorkspaceError("not_found", f"segment not found: {body.key}")
    updated = assemble(doc, {body.key: body.text})
    after = segment(updated).by_key().get(body.key)
    if after is None:
        raise WorkspaceError("invalid_state", "the new text does not stay a single segment")
    write_section(root, body.path, updated, digest)
    service.sync(root, project, body.path, updated, PRIORITY_EDIT)
    if body.suggestion_id:
        check_mod.set_status(root, body.path, segment(updated), body.suggestion_id, "applied")
    return {"path": body.path, "key": body.key}


@router.post("/projects/{project_id}/check")
async def run_check(root: Root, service: Service, body: CheckBody) -> dict[str, Any]:
    project = load_project(root)
    text, _ = read_section(root, body.path)
    doc = segment(text)
    ctx = _context(root, project, text)
    try:
        items = await check_mod.check_section(
            _client(service, project), doc, ctx, requirement_rules=body.requirements
        )
    except LlmError as exc:
        raise WorkspaceError("model_refused", str(exc)) from exc
    check_mod.save(root, body.path, text, items)
    return {"items": [i.__dict__ for i in items]}


@router.get("/projects/{project_id}/check")
def get_check(root: Root, path: str) -> dict[str, Any]:
    text, _ = read_section(root, path)
    items = check_mod.load(root, path, segment(text))
    return {"items": [i.__dict__ for i in items]}


@router.post("/projects/{project_id}/check/dismiss")
def dismiss(root: Root, body: DismissBody) -> dict[str, str]:
    text, _ = read_section(root, body.path)
    check_mod.set_status(root, body.path, segment(text), body.suggestion_id, "dismissed")
    return {"status": "dismissed"}
