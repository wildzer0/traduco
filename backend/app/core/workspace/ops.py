"""Structure operations on chapters and sections: create, rename, reorder, move, delete."""

from __future__ import annotations

import io
import time
import uuid
from pathlib import Path

from ruamel.yaml import YAML

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.frontmatter import Document, parse, render
from app.core.workspace.fsio import atomic_write_text
from app.core.workspace.ordering import (
    apply_renames,
    format_name,
    plan_renumber,
    prefix_of,
    slugify,
    sort_key,
    split_prefix,
)
from app.core.workspace.tree import CHAPTER_META, CHAPTERS_DIR, IMAGES_DIR, MAX_DEPTH

TRASH_DIR = ".traduco/cestino"


# --- path handling ---------------------------------------------------------------------------


def _check_parts(rel: str) -> tuple[str, ...]:
    if not rel or rel.startswith("/") or "\\" in rel or ":" in rel:
        raise WorkspaceError("invalid_path", f"invalid path: {rel!r}")
    parts = tuple(rel.split("/"))
    if any(p in ("", ".", "..") or p.startswith((".", "_")) or p == IMAGES_DIR for p in parts):
        raise WorkspaceError("invalid_path", f"invalid path: {rel!r}")
    if parts[0] != CHAPTERS_DIR:
        raise WorkspaceError("invalid_path", f"path must be inside {CHAPTERS_DIR}/: {rel!r}")
    return parts


def _inside_chapters(root: Path, path: Path) -> bool:
    chapters = (root / CHAPTERS_DIR).resolve()
    return chapters in path.resolve().parents


def resolve_node(root: Path, rel: str) -> Path:
    """Absolute path of an existing chapter or section; rejects anything outside ``capitoli/``."""
    parts = _check_parts(rel)
    if len(parts) < 2:
        raise WorkspaceError("invalid_path", "the root folder is not a node")
    path = root.joinpath(*parts)
    if not path.exists() and not path.is_symlink():
        raise WorkspaceError("not_found", f"not found: {rel}")
    if not _inside_chapters(root, path):
        raise WorkspaceError("invalid_path", f"path escapes the project: {rel!r}")
    return path


def resolve_parent(root: Path, parent: str | None) -> tuple[Path, int]:
    """Directory that holds children, and the level of the chapters created in it (1 = top)."""
    if parent is None:
        (root / CHAPTERS_DIR).mkdir(exist_ok=True)
        return root / CHAPTERS_DIR, 1
    path = resolve_node(root, parent)
    if not path.is_dir():
        raise WorkspaceError("invalid_path", f"not a chapter: {parent}")
    return path, len(parent.split("/"))


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_content(entry: Path, top_level: bool) -> bool:
    if entry.name.startswith((".", "_")):
        return False
    if entry.is_dir():
        return entry.name != IMAGES_DIR
    return not top_level and entry.suffix.lower() == ".md"


def siblings(directory: Path, top_level: bool = False) -> list[str]:
    return sorted((e.name for e in directory.iterdir() if _is_content(e, top_level)), key=sort_key)


def _next_name(directory: Path, base: str) -> str:
    numbers = [n for name in siblings(directory) if (n := split_prefix(name)[0]) is not None]
    number = max(numbers, default=0) + 1
    return format_name(number, base, max(2, len(str(number))))


def height(chapter: Path) -> int:
    """Number of directory levels in a chapter subtree (a chapter without sub-chapters is 1)."""
    sub = [e for e in chapter.iterdir() if e.is_dir() and _is_content(e, False)]
    return 1 + max((height(e) for e in sub), default=0)


# --- YAML metadata ---------------------------------------------------------------------------


def _write_chapter_title(chapter: Path, title: str) -> None:
    meta_path = chapter / CHAPTER_META
    yaml = YAML()
    yaml.allow_unicode = True
    data = yaml.load(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
    if not isinstance(data, dict):
        data = {}
    data["title"] = title
    out = io.StringIO()
    yaml.dump(data, out)
    atomic_write_text(meta_path, out.getvalue())


# --- create ----------------------------------------------------------------------------------


def create_chapter(root: Path, title: str, parent: str | None = None) -> str:
    directory, level = resolve_parent(root, parent)
    if level > MAX_DEPTH:
        raise WorkspaceError("depth_exceeded", f"chapters nest at most {MAX_DEPTH} levels")
    target = directory / _next_name(directory, slugify(title))
    try:
        target.mkdir()
    except FileExistsError as exc:
        raise WorkspaceError("exists", f"already exists: {target.name}") from exc
    _write_chapter_title(target, title)
    return _rel(root, target)


def create_section(root: Path, chapter: str | None, title: str) -> str:
    if chapter is None:
        raise WorkspaceError("invalid_path", "a section must belong to a chapter")
    directory, _ = resolve_parent(root, chapter)
    target = directory / _next_name(directory, slugify(title) + ".md")
    if target.exists():
        raise WorkspaceError("exists", f"already exists: {target.name}")
    atomic_write_text(target, render(Document({"title": title}, "")))
    return _rel(root, target)


# --- rename ----------------------------------------------------------------------------------


def rename(root: Path, rel: str, title: str) -> dict[str, str]:
    """Set a new title and rename the file/folder after it, keeping the numeric prefix."""
    node = resolve_node(root, rel)
    suffix = "" if node.is_dir() else ".md"
    new_name = prefix_of(node.name) + slugify(title) + suffix
    target = node.with_name(new_name)
    if new_name != node.name and (target.exists() or target.is_symlink()):
        raise WorkspaceError("exists", f"already exists: {new_name}")
    if node.is_dir():
        _write_chapter_title(node, title)
    else:
        doc = parse(node.read_text(encoding="utf-8"))
        doc.meta["title"] = title
        atomic_write_text(node, render(doc))
    if new_name == node.name:
        return {}
    node.rename(target)
    return {rel: _rel(root, target)}


# --- reorder and move ------------------------------------------------------------------------


def _mapping(root: Path, directory: Path, plan: dict[str, str]) -> dict[str, str]:
    base = _rel(root, directory)
    return {f"{base}/{old}": f"{base}/{new}" for old, new in plan.items()}


def reorder(root: Path, parent: str | None, ordered: list[str]) -> dict[str, str]:
    """Give siblings the order in ``ordered`` by renumbering their prefixes."""
    directory, _ = resolve_parent(root, parent)
    current = siblings(directory, top_level=parent is None)
    if len(set(ordered)) != len(ordered) or sorted(ordered) != sorted(current):
        raise WorkspaceError("invalid_order", "the new order must list every sibling exactly once")
    plan = plan_renumber(ordered)
    apply_renames(directory, plan)
    return _mapping(root, directory, plan)


def _unique_name(directory: Path, name: str) -> str:
    if not (directory / name).exists():
        return name
    stem, dot, ext = name.partition(".")
    for n in range(2, 1000):
        candidate = f"{stem}-{n}{dot}{ext}"
        if not (directory / candidate).exists():
            return candidate
    raise WorkspaceError("exists", f"cannot find a free name for {name}")


def move(root: Path, rel: str, parent: str | None, index: int | None = None) -> str:
    """Move a node under ``parent`` at ``index`` (end if ``None``); returns its new path."""
    node = resolve_node(root, rel)
    dest, level = resolve_parent(root, parent)
    if not node.is_dir() and parent is None:
        raise WorkspaceError("invalid_move", "a section cannot be moved to the top level")
    if node.is_dir():
        real = node.resolve()
        if dest.resolve() == real or real in dest.resolve().parents:
            raise WorkspaceError("invalid_move", "cannot move a chapter into itself")
        if level - 1 + height(node) > MAX_DEPTH:
            raise WorkspaceError("depth_exceeded", f"chapters nest at most {MAX_DEPTH} levels")

    top = parent is None
    if node.parent.resolve() == dest.resolve():
        order = [n for n in siblings(dest, top) if n != node.name]
        order.insert(len(order) if index is None else max(0, min(index, len(order))), node.name)
        mapping = reorder(root, parent, order)
        return mapping.get(rel, rel)

    moved_name = _unique_name(dest, split_prefix(node.name)[1])
    moved = dest / moved_name
    original = node
    node.rename(moved)
    try:
        order = [n for n in siblings(dest, top) if n != moved_name]
        order.insert(len(order) if index is None else max(0, min(index, len(order))), moved_name)
        plan = plan_renumber(order)
        apply_renames(dest, plan)
    except BaseException:
        moved.rename(original)
        raise
    return _rel(root, dest / plan.get(moved_name, moved_name))


# --- delete ----------------------------------------------------------------------------------


def delete(root: Path, rel: str) -> str:
    """Move a node to ``.traduco/cestino/<stamp>/<original path>``; returns the trash folder."""
    node = resolve_node(root, rel)
    stamp = f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    target = root / TRASH_DIR / stamp / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    node.rename(target)
    return f"{TRASH_DIR}/{stamp}"
