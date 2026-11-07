"""Project skeleton: bundled list, set/replace, conformity report, creation of missing nodes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import Root
from app.config import Settings, get_settings
from app.core.skeleton import check as conformity
from app.core.skeleton import generate
from app.core.skeleton.files import list_bundled
from app.core.skeleton.model import SKELETON_FILE, parse_skeleton
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_text
from app.core.workspace.manifest import load_project

router = APIRouter(tags=["skeleton"])


class SkeletonPut(BaseModel):
    testo: str


class CreateMissing(BaseModel):
    include_optional: bool = False


@router.get("/skeletons")
def bundled(settings: Annotated[Settings, Depends(get_settings)]) -> list[dict[str, str]]:
    return [asdict(s) for s in list_bundled(settings.skeletons_dir)]


def _loaded(root: Any) -> Any:
    loaded = generate.load(root)
    if loaded is None:
        raise WorkspaceError("not_found", "this project has no skeleton")
    return loaded[0]


@router.get("/projects/{project_id}/skeleton")
def get_skeleton(root: Root) -> dict[str, Any]:
    loaded = generate.load(root)
    if loaded is None:
        return {"present": False}
    skeleton, text = loaded
    return {"present": True, "nome": skeleton.nome, "testo": text}


@router.put("/projects/{project_id}/skeleton")
def put_skeleton(root: Root, body: SkeletonPut) -> dict[str, Any]:
    skeleton = parse_skeleton(body.testo)
    atomic_write_text(root / SKELETON_FILE, body.testo)
    return {"present": True, "nome": skeleton.nome}


@router.get("/projects/{project_id}/skeleton/check")
def check_skeleton(root: Root) -> dict[str, Any]:
    skeleton = _loaded(root)
    report = conformity.check(root, skeleton, load_project(root).lingua_sorgente)
    return {
        "conform": report.conform,
        "items": [asdict(i) for i in report.items],
        "extra": report.extra,
    }


@router.post("/projects/{project_id}/skeleton/create-missing")
def create_missing(root: Root, body: CreateMissing) -> dict[str, Any]:
    skeleton = _loaded(root)
    created = conformity.create_missing(
        root, skeleton, load_project(root).lingua_sorgente, body.include_optional
    )
    return {"created": created}
