"""Issues ("emissioni", RF-80): frozen copies of the document with a number and a date.

An issue lives in ``.traduco/emissioni/<rev>/``: ``meta.json`` (number, date, description, the
tree as it was, the change table), ``sorgente/`` and ``ufficiale/`` with every section's Markdown.
Plain files, so they travel with Git (the folder is not in ``.gitignore``).
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from app.core.workspace import frontmatter
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_text, sha256_text
from app.core.workspace.manifest import Project, Revision, save_project
from app.core.workspace.sections import read_section, write_section
from app.core.workspace.tree import Node, build_tree

FOLDER = ".traduco/emissioni"
_REV = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,19}$")
SIDES = ("sorgente", "ufficiale")


@dataclass(frozen=True)
class Entry:
    """One chapter or section of the tree as it was (``depth`` 1 = a top-level chapter)."""

    kind: str
    path: str
    title: str
    depth: int


def _folder(root: Path, rev: str) -> Path:
    if not _REV.match(rev):
        raise WorkspaceError("invalid_name", "the issue number may use letters, digits . _ - only")
    return root / FOLDER / rev


def _flatten(nodes: list[Node], depth: int = 1) -> list[Entry]:
    out: list[Entry] = []
    for node in nodes:
        out.append(Entry(node.kind, node.path, node.title, depth))
        out.extend(_flatten(node.children, depth + 1))
    return out


def current_entries(root: Path) -> list[Entry]:
    return _flatten(build_tree(root))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def meta(root: Path, rev: str) -> dict[str, Any]:
    try:
        data = json.loads((_folder(root, rev) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkspaceError("not_found", f"issue not found: {rev}") from exc
    return data  # type: ignore[no-any-return]


def list_issues(root: Path) -> list[dict[str, Any]]:
    """Issues, oldest first, without the heavy parts."""
    base = root / FOLDER
    found: list[dict[str, Any]] = []
    if base.is_dir():
        for folder in base.iterdir():
            try:
                data = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            found.append(
                {
                    "rev": data["rev"],
                    "data": data["data"],
                    "descrizione": data.get("descrizione", ""),
                    "created_at": data.get("created_at", ""),
                    "sections": sum(1 for e in data.get("entries", []) if e["kind"] == "section"),
                    "changes": len(data.get("changes", [])),
                }
            )
    return sorted(found, key=lambda i: (i["created_at"], i["rev"]))


def create(
    root: Path,
    project: Project,
    rev: str,
    day: date,
    description: str,
    official_text: Callable[[str, str], str],
    *,
    add_to_revisions: bool = True,
) -> dict[str, Any]:
    """Freeze the project as issue ``rev``; ``official_text(path, source)`` is its translation."""
    folder = _folder(root, rev)
    if folder.exists():
        raise WorkspaceError("exists", f"issue {rev} already exists")
    entries = current_entries(root)
    if not any(e.kind == "section" for e in entries):
        raise WorkspaceError("nothing_to_export", "There is no section to freeze.")
    for entry in entries:
        if entry.kind != "section":
            continue
        text = (root / entry.path).read_text(encoding="utf-8")
        atomic_write_text(folder / "sorgente" / entry.path, text)
        atomic_write_text(folder / "ufficiale" / entry.path, official_text(entry.path, text))
    data = {
        "rev": rev,
        "data": day.isoformat(),
        "descrizione": description,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "lingua_sorgente": project.lingua_sorgente,
        "lingua_ufficiale": project.lingua_ufficiale,
        "entries": [e.__dict__ for e in entries],
        "changes": [],
    }
    _write_json(folder / "meta.json", data)  # last: an interrupted freeze leaves no issue
    if add_to_revisions and all(r.rev != rev for r in project.revisioni):
        project.revisioni.append(Revision(rev=rev, data=day, descrizione=description))
        save_project(root, project)
    return data


def entries_of(root: Path, rev: str | None) -> list[Entry]:
    """The tree of an issue, or of the draft when ``rev`` is None."""
    if rev is None:
        return current_entries(root)
    return [Entry(**e) for e in meta(root, rev)["entries"]]


def text_of(root: Path, rev: str, side: str, path: str) -> str | None:
    if side not in SIDES:
        raise WorkspaceError("invalid_path", "side must be sorgente or ufficiale")
    base = (_folder(root, rev) / side).resolve()
    target = (base / path).resolve()
    if base not in target.parents:
        raise WorkspaceError("invalid_path", path)
    try:
        return target.read_text(encoding="utf-8")
    except OSError:
        return None


def save_changes(root: Path, rev: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
    data = meta(root, rev)
    data["changes"] = changes
    _write_json(_folder(root, rev) / "meta.json", data)
    return data


def restore_section(root: Path, rev: str, path: str) -> str:
    """Put a section back as it was in issue ``rev`` (the author sees it as an ordinary edit)."""
    old = text_of(root, rev, "sorgente", path)
    if old is None:
        raise WorkspaceError("not_found", f"{path} was not in issue {rev}")
    try:
        _, digest = read_section(root, path)
    except WorkspaceError as exc:
        raise WorkspaceError("not_found", f"{path} no longer exists in the project") from exc
    return write_section(root, path, old, digest)


def delete(root: Path, rev: str) -> None:
    folder = _folder(root, rev)
    if not folder.is_dir():
        raise WorkspaceError("not_found", f"issue not found: {rev}")
    shutil.rmtree(folder)


def title_of(text: str, fallback: str) -> str:
    try:
        meta_ = frontmatter.parse(text).meta
    except frontmatter.FrontMatterError:
        return fallback
    value = meta_.get("title")
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def fingerprint(text: str) -> str:
    return sha256_text(text)[:12]
