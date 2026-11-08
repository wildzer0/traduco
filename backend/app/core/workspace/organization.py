"""Folders for projects (nested), kept in one file next to them.

``<workspaces>/.traduco-cartelle.yaml`` holds the folders and which folder each project is in.
Projects stay where they are on disk, flat, so their ids, their URLs and their Git repositories
never change when somebody tidies the list. Moving a project into a folder is only a line in this
file; deleting a folder never deletes a project (its contents go up one level).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_text

FILE = ".traduco-cartelle.yaml"
MAX_DEPTH = 8
MAX_NAME = 80


@dataclass
class Folder:
    id: str
    nome: str
    genitore: str | None = None


@dataclass
class Organization:
    folders: list[Folder]
    projects: dict[str, str]  # project id -> folder id

    def folder(self, folder_id: str) -> Folder:
        for f in self.folders:
            if f.id == folder_id:
                return f
        raise WorkspaceError("not_found", f"folder not found: {folder_id}")

    def depth(self, folder_id: str | None) -> int:
        depth, seen = 0, set()
        while folder_id is not None and folder_id not in seen:
            seen.add(folder_id)
            depth += 1
            folder_id = self.folder(folder_id).genitore
        return depth

    def path(self, folder_id: str | None) -> list[str]:
        """Names from the top folder down to ``folder_id``."""
        names: list[str] = []
        seen: set[str] = set()
        while folder_id is not None and folder_id not in seen:
            seen.add(folder_id)
            f = self.folder(folder_id)
            names.append(f.nome)
            folder_id = f.genitore
        return list(reversed(names))

    def descendants(self, folder_id: str) -> set[str]:
        found: set[str] = set()
        todo = [folder_id]
        while todo:
            current = todo.pop()
            for f in self.folders:
                if f.genitore == current and f.id not in found:
                    found.add(f.id)
                    todo.append(f.id)
        return found


def _yaml() -> YAML:
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.allow_unicode = True
    return yaml


def load(workspaces: Path) -> Organization:
    path = workspaces / FILE
    try:
        data: Any = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
    except (OSError, YAMLError, UnicodeDecodeError):
        return Organization([], {})
    if not isinstance(data, dict):
        return Organization([], {})
    folders: list[Folder] = []
    for item in data.get("cartelle") or []:
        if isinstance(item, dict) and item.get("id") and item.get("nome"):
            folders.append(Folder(str(item["id"]), str(item["nome"]), item.get("genitore")))
    known = {f.id for f in folders}
    folders = [f for f in folders if f.genitore is None or f.genitore in known]  # no orphans
    known = {f.id for f in folders}
    assigned = {str(k): str(v) for k, v in (data.get("progetti") or {}).items() if str(v) in known}
    return Organization(folders, assigned)


def save(workspaces: Path, org: Organization) -> None:
    data = {
        "cartelle": [
            {"id": f.id, "nome": f.nome, **({"genitore": f.genitore} if f.genitore else {})}
            for f in org.folders
        ],
        "progetti": dict(sorted(org.projects.items())),
    }
    import io

    out = io.StringIO()
    _yaml().dump(data, out)
    workspaces.mkdir(parents=True, exist_ok=True)
    atomic_write_text(workspaces / FILE, out.getvalue())


def _clean(name: str) -> str:
    name = " ".join(name.split())
    if not name or len(name) > MAX_NAME:
        raise WorkspaceError("invalid_name", f"a folder name is 1 to {MAX_NAME} characters")
    if "/" in name or "\\" in name:
        raise WorkspaceError("invalid_name", "a folder name cannot contain / or \\")
    return name


def _check_unique(
    org: Organization, name: str, parent: str | None, ignore: str | None = None
) -> None:
    for f in org.folders:
        if f.genitore == parent and f.id != ignore and f.nome.casefold() == name.casefold():
            raise WorkspaceError("exists", f'there is already a folder called "{name}" here')


def create_folder(workspaces: Path, name: str, parent: str | None = None) -> Folder:
    org = load(workspaces)
    name = _clean(name)
    if parent is not None:
        org.folder(parent)
    if org.depth(parent) >= MAX_DEPTH:
        raise WorkspaceError("depth_exceeded", f"folders can be nested {MAX_DEPTH} levels")
    _check_unique(org, name, parent)
    folder = Folder(f"f-{secrets.token_hex(3)}", name, parent)
    org.folders.append(folder)
    save(workspaces, org)
    return folder


def update_folder(
    workspaces: Path,
    folder_id: str,
    *,
    name: str | None = None,
    parent: str | None = None,
    move: bool = False,
) -> Folder:
    """Rename a folder and/or, with ``move``, put it under ``parent`` (None = the top level)."""
    org = load(workspaces)
    folder = org.folder(folder_id)
    new_name = _clean(name) if name is not None else folder.nome
    new_parent = parent if move else folder.genitore
    if new_parent is not None:
        org.folder(new_parent)
        if new_parent == folder_id or new_parent in org.descendants(folder_id):
            raise WorkspaceError("invalid_move", "a folder cannot go inside itself")
        if org.depth(new_parent) + 1 + _height(org, folder_id) > MAX_DEPTH:
            raise WorkspaceError("depth_exceeded", f"folders can be nested {MAX_DEPTH} levels")
    _check_unique(org, new_name, new_parent, ignore=folder_id)
    folder.nome, folder.genitore = new_name, new_parent
    save(workspaces, org)
    return folder


def _height(org: Organization, folder_id: str) -> int:
    below = [f.id for f in org.folders if f.genitore == folder_id]
    return 0 if not below else 1 + max(_height(org, b) for b in below)


def delete_folder(workspaces: Path, folder_id: str) -> None:
    """Remove the folder; its projects and sub-folders move up to its parent."""
    org = load(workspaces)
    folder = org.folder(folder_id)
    for f in org.folders:
        if f.genitore == folder_id:
            _check_unique(org, f.nome, folder.genitore, ignore=f.id)
            f.genitore = folder.genitore
    for project, where in list(org.projects.items()):
        if where == folder_id:
            if folder.genitore is None:
                del org.projects[project]
            else:
                org.projects[project] = folder.genitore
    org.folders = [f for f in org.folders if f.id != folder_id]
    save(workspaces, org)


def set_project_folder(workspaces: Path, project_id: str, folder_id: str | None) -> None:
    org = load(workspaces)
    if folder_id is None:
        org.projects.pop(project_id, None)
    else:
        org.folder(folder_id)
        org.projects[project_id] = folder_id
    save(workspaces, org)


def forget_project(workspaces: Path, project_id: str) -> None:
    org = load(workspaces)
    if org.projects.pop(project_id, None) is not None:
        save(workspaces, org)
