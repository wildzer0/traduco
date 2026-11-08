"""Company templates of a project: upload, analysis, style mapping, default (RF-50..52, RF-56)."""

from __future__ import annotations

import base64
import binascii
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import Root
from app.config import Settings, get_settings
from app.core.export.pandoc import default_reference_doc, find_pandoc
from app.core.templates import store
from app.core.templates.analyze import MAX_TEMPLATE_BYTES, Analysis
from app.core.templates.mapping import ROLES, Mapping
from app.core.templates.wizard import FONTS, WizardOptions
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project

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


@router.get("/projects/{project_id}/toc")
def toc_enabled(root: Root) -> dict[str, bool]:
    """Does the default template have a table of contents? Then the sidebar numbers the outline."""
    name = load_project(root).template_predefinito
    if not name:
        return {"enabled": False}
    try:
        return {"enabled": store.describe(root, name)[0].has_toc}
    except (WorkspaceError, OSError, ValueError):
        return {"enabled": False}


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


class WizardBody(BaseModel):
    nome: str = Field(default="template", min_length=1, max_length=60)
    opzioni: WizardOptions = Field(default_factory=WizardOptions)
    logo_base64: str | None = None


@router.get("/template-wizard/fonts")
def wizard_fonts() -> list[str]:
    return list(FONTS)


@router.post("/projects/{project_id}/templates/wizard", status_code=201)
def create_with_wizard(root: Root, body: WizardBody) -> dict[str, Any]:
    """Create a template from the wizard's four steps (RF-55)."""
    try:
        logo = base64.b64decode(body.logo_base64, validate=True) if body.logo_base64 else None
    except (binascii.Error, ValueError) as exc:
        raise WorkspaceError("invalid_image", "the logo is not valid base64") from exc
    with tempfile.TemporaryDirectory(prefix="traduco-wizard-") as tmp:
        reference = default_reference_doc(find_pandoc(), Path(tmp) / "reference.docx")
        name = store.create_from_wizard(root, body.nome, body.opzioni, logo, reference)
    return _detail(name, *store.describe(root, name))


@router.post("/projects/{project_id}/templates/example", status_code=201)
def add_example_template(
    root: Root, settings: Annotated[Settings, Depends(get_settings)]
) -> dict[str, Any]:
    """Add the sample company template to the project (to try the export, or to start from)."""
    example = settings.example_project
    if example is None:
        raise WorkspaceError("not_found", "the example template is not available")
    name = store.add_example(root, example / "template")
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
