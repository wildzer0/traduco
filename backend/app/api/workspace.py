"""The list of projects as the home page shows it: folders, projects, copies, trash."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.audit import note
from app.api.deps import Root
from app.config import Settings, get_settings
from app.core.workspace import organization, registry
from app.core.workspace.errors import WorkspaceError

router = APIRouter(tags=["workspace"])
Config = Annotated[Settings, Depends(get_settings)]


def _folders(settings: Settings) -> list[dict[str, Any]]:
    org = organization.load(settings.workspaces_path)
    return [{**asdict(f), "percorso": org.path(f.id)} for f in org.folders]


@router.get("/workspace")
def workspace(settings: Config) -> dict[str, Any]:
    """Everything the home page needs in one request."""
    return {
        "folders": _folders(settings),
        "projects": [asdict(p) for p in registry.list_projects(settings.workspaces_path)],
    }


class FolderBody(BaseModel):
    nome: str = Field(min_length=1, max_length=organization.MAX_NAME)
    genitore: str | None = None


class FolderPatch(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=organization.MAX_NAME)
    genitore: str | None = None
    sposta: bool = False  # true: put it under ``genitore`` (null = top level)


@router.post("/folders", status_code=201)
def create_folder(body: FolderBody, settings: Config) -> dict[str, Any]:
    folder = organization.create_folder(settings.workspaces_path, body.nome, body.genitore)
    return asdict(folder)


@router.patch("/folders/{folder_id}")
def update_folder(folder_id: str, body: FolderPatch, settings: Config) -> dict[str, Any]:
    folder = organization.update_folder(
        settings.workspaces_path, folder_id, name=body.nome, parent=body.genitore, move=body.sposta
    )
    return asdict(folder)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: str, settings: Config) -> None:
    organization.delete_folder(settings.workspaces_path, folder_id)


class FolderOfProject(BaseModel):
    cartella: str | None = None


@router.put("/projects/{project_id}/folder")
def set_folder(root: Root, body: FolderOfProject, settings: Config) -> dict[str, Any]:
    organization.set_project_folder(settings.workspaces_path, root.name, body.cartella)
    return {"id": root.name, "cartella": body.cartella}


class Duplicate(BaseModel):
    nome: str | None = Field(default=None, max_length=120)


@router.post("/projects/{project_id}/duplicate", status_code=201)
def duplicate(request: Request, root: Root, body: Duplicate, settings: Config) -> dict[str, Any]:
    new_id = registry.duplicate_project(settings.workspaces_path, root.name, body.nome)
    note(request, root.name, "project.duplicate", new_id)
    info = registry.project_info(
        settings.workspaces_path / new_id, organization.load(settings.workspaces_path)
    )
    if info is None:
        raise WorkspaceError("unreadable", "the copy cannot be read")
    return asdict(info)


@router.delete("/projects/{project_id}", status_code=200)
def delete_project(request: Request, root: Root, settings: Config) -> dict[str, str]:
    """Move the project to the trash (it can be restored)."""
    trashed = registry.trash_project(settings.workspaces_path, root.name)
    note(request, root.name, "project.delete", trashed)
    return {"trash": trashed}


@router.get("/trash")
def trash(settings: Config) -> list[dict[str, str]]:
    return registry.list_trash(settings.workspaces_path)


@router.post("/trash/{name}/restore", status_code=201)
def restore(name: str, settings: Config) -> dict[str, str]:
    return {"id": registry.restore_project(settings.workspaces_path, name)}


@router.delete("/trash/{name}", status_code=204)
def purge(name: str, settings: Config) -> None:
    registry.purge_trash(settings.workspaces_path, name)
