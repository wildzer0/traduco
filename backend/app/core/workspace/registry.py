"""The set of projects under the workspaces folder (``~/Traduco`` by default)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml.error import YAMLError

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import MANIFEST_NAME, create_project, load_project
from app.core.workspace.ordering import slugify

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


@dataclass(frozen=True)
class ProjectInfo:
    id: str
    nome: str
    lingua_sorgente: str
    lingua_ufficiale: str


def list_projects(workspaces: Path) -> list[ProjectInfo]:
    if not workspaces.is_dir():
        return []
    found: list[ProjectInfo] = []
    for entry in sorted(workspaces.iterdir(), key=lambda p: p.name.lower()):
        if not _ID.match(entry.name) or not (entry / MANIFEST_NAME).is_file():
            continue
        try:
            p = load_project(entry)
        except (YAMLError, ValueError, OSError):
            continue  # a broken manifest must not hide the other projects
        found.append(ProjectInfo(entry.name, p.nome, p.lingua_sorgente, p.lingua_ufficiale))
    return found


def project_root(workspaces: Path, project_id: str) -> Path:
    """Resolve a project id to its folder; it can never address anything outside ``workspaces``."""
    if not _ID.match(project_id) or ".." in project_id:
        raise WorkspaceError("invalid_path", f"invalid project id: {project_id!r}")
    root = workspaces / project_id
    if not (root / MANIFEST_NAME).is_file():
        raise WorkspaceError("not_found", f"project not found: {project_id}")
    return root


def _free_id(workspaces: Path, base: str) -> str:
    candidate, n = base, 1
    while (workspaces / candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def create_in_workspaces(
    workspaces: Path,
    nome: str | None,
    sorgente: str,
    ufficiale: str,
    example: Path | None = None,
) -> str:
    """Create a project (empty, or a copy of ``example``) and return its id."""
    workspaces.mkdir(parents=True, exist_ok=True)
    if example is not None:
        project_id = _free_id(workspaces, slugify(nome or example.name))
        shutil.copytree(example, workspaces / project_id, ignore=shutil.ignore_patterns(".traduco"))
        return project_id
    if not nome:
        raise WorkspaceError("invalid_path", "a project name is required")
    project_id = _free_id(workspaces, slugify(nome))
    create_project(workspaces / project_id, nome, sorgente, ufficiale)
    return project_id
