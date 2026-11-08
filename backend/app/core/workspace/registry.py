"""The set of projects under the workspaces folder (``~/Traduco`` by default)."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ruamel.yaml.error import YAMLError

from app.core.workspace import organization
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import MANIFEST_NAME, create_project, load_project, save_project
from app.core.workspace.ordering import slugify

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


TRASH = ".cestino"
_TRASH_NAME = re.compile(r"^\d{8}T\d{6}Z-[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class ProjectInfo:
    id: str
    nome: str
    lingua_sorgente: str
    lingua_ufficiale: str
    cartella: str | None = None  # id of the folder it is in
    percorso: list[str] = field(default_factory=list)  # names of that folder and its parents
    autore: str = ""
    emissione: str = ""  # number of the latest issue (or of the last revision in the table)
    emissione_data: str = ""
    ultima_modifica: str = ""  # ISO 8601, UTC
    sezioni: int = 0
    lingue: list[str] = field(default_factory=list)  # target languages, the official one first


def _last_issue(root: Path, revisions: list[tuple[str, str]]) -> tuple[str, str]:
    """(number, date) of the latest frozen issue, else of the last row of the revision table."""
    best: tuple[str, str, str] | None = None
    for meta in sorted((root / ".traduco" / "emissioni").glob("*/meta.json")):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            found = (str(data.get("created_at", "")), str(data["rev"]), str(data.get("data", "")))
        except (OSError, ValueError, KeyError):
            continue
        if best is None or found > best:
            best = found
    if best is not None:
        return best[1], best[2]
    return revisions[-1] if revisions else ("", "")


def _activity(root: Path) -> tuple[str, int]:
    """(latest modification as ISO time, number of sections) of the project's own files."""
    newest, sections = 0.0, 0
    for name in (MANIFEST_NAME, "glossario.yaml", "snippet.yaml"):
        try:
            newest = max(newest, (root / name).stat().st_mtime)
        except OSError:
            continue
    for path in (root / "capitoli").rglob("*"):
        try:
            if path.suffix in (".md", ".yaml") or path.is_dir():
                newest = max(newest, path.stat().st_mtime)
            if path.suffix == ".md":
                sections += 1
        except OSError:
            continue
    when = datetime.fromtimestamp(newest, UTC).isoformat(timespec="seconds") if newest else ""
    return when, sections


def project_info(entry: Path, org: organization.Organization) -> ProjectInfo | None:
    try:
        p = load_project(entry)
    except (YAMLError, ValueError, OSError):
        return None  # a broken manifest must not hide the other projects
    folder = org.projects.get(entry.name)
    when, sections = _activity(entry)
    revisions = [(r.rev, r.data.isoformat()) for r in p.revisioni]
    issue, issue_date = _last_issue(entry, revisions)
    return ProjectInfo(
        entry.name, p.nome, p.lingua_sorgente, p.lingua_ufficiale,
        cartella=folder, percorso=org.path(folder) if folder else [],
        autore=str(p.metadati.get("autore", "") or ""), emissione=issue, emissione_data=issue_date,
        ultima_modifica=when, sezioni=sections, lingue=p.target_languages,
    )  # fmt: skip


def list_projects(workspaces: Path) -> list[ProjectInfo]:
    if not workspaces.is_dir():
        return []
    org = organization.load(workspaces)
    found: list[ProjectInfo] = []
    for entry in sorted(workspaces.iterdir(), key=lambda p: p.name.lower()):
        if not _ID.match(entry.name) or not (entry / MANIFEST_NAME).is_file():
            continue
        info = project_info(entry, org)
        if info is not None:
            found.append(info)
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


def duplicate_project(workspaces: Path, project_id: str, nome: str | None = None) -> str:
    """Copy a project - text, translations, memory, issues - under a new name; returns its id.

    The copy starts clean of what is only a cache (rendered diagrams, the section trash, built
    documents) and goes in the same folder as the original.
    """
    source = project_root(workspaces, project_id)
    project = load_project(source)
    new_name = (nome or f"{project.nome} (copia)").strip()
    if not new_name:
        raise WorkspaceError("invalid_name", "the copy needs a name")
    new_id = _free_id(workspaces, slugify(new_name))
    target = workspaces / new_id

    def skip(directory: str, names: list[str]) -> set[str]:
        here = Path(directory)
        if here == source:
            return {n for n in names if n in ("build", ".git")}
        if here == source / ".traduco":
            return {n for n in names if n in ("cache", "cestino")}
        return set()

    shutil.copytree(source, target, ignore=skip)
    copy = load_project(target)
    copy.nome = new_name
    save_project(target, copy)
    folder = organization.load(workspaces).projects.get(project_id)
    if folder:
        organization.set_project_folder(workspaces, new_id, folder)
    return new_id


def _trash(workspaces: Path) -> Path:
    return workspaces / TRASH


def trash_project(workspaces: Path, project_id: str) -> str:
    """Take a project out of the list without destroying it; returns its name in the trash."""
    root = project_root(workspaces, project_id)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-{project_id}"
    _trash(workspaces).mkdir(parents=True, exist_ok=True)
    shutil.move(str(root), str(_trash(workspaces) / name))
    organization.forget_project(workspaces, project_id)
    return name


def list_trash(workspaces: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    base = _trash(workspaces)
    if not base.is_dir():
        return entries
    for entry in sorted(base.iterdir(), reverse=True):
        if not _TRASH_NAME.match(entry.name) or not (entry / MANIFEST_NAME).is_file():
            continue
        try:
            nome = load_project(entry).nome
        except (YAMLError, ValueError, OSError):
            nome = entry.name
        stamp, _, original = entry.name.partition("-")
        deleted = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        entries.append(
            {"name": entry.name, "id": original, "nome": nome, "deleted_at": deleted.isoformat()}
        )
    return entries


def _trash_entry(workspaces: Path, name: str) -> Path:
    if not _TRASH_NAME.match(name):
        raise WorkspaceError("invalid_path", f"invalid trash entry: {name!r}")
    entry = _trash(workspaces) / name
    if not (entry / MANIFEST_NAME).is_file():
        raise WorkspaceError("not_found", f"not in the trash: {name}")
    return entry


def restore_project(workspaces: Path, name: str) -> str:
    entry = _trash_entry(workspaces, name)
    new_id = _free_id(workspaces, name.partition("-")[2])
    shutil.move(str(entry), str(workspaces / new_id))
    return new_id


def purge_trash(workspaces: Path, name: str) -> None:
    shutil.rmtree(_trash_entry(workspaces, name))
