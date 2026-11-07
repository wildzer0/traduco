"""Create the folders and files described by a skeleton, tagging each with its node id."""

from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML

from app.core.skeleton.model import SKELETON_FILE, Skeleton, SkeletonNode, parse_skeleton
from app.core.workspace import ops
from app.core.workspace.frontmatter import Document, render
from app.core.workspace.fsio import atomic_write_text
from app.core.workspace.tree import CHAPTER_META

TAG = "scheletro"


def load(root: Path) -> tuple[Skeleton, str] | None:
    """The skeleton stored in the project and its text, or ``None`` if it has none."""
    path = root / SKELETON_FILE
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return parse_skeleton(text), text


def _tag_chapter(root: Path, path: str, node_id: str) -> None:
    meta = root / path / CHAPTER_META
    yaml = YAML()
    yaml.allow_unicode = True
    data = yaml.load(meta.read_text(encoding="utf-8")) if meta.is_file() else None
    if not isinstance(data, dict):
        data = {}
    data[TAG] = node_id
    out = io.StringIO()
    yaml.dump(data, out)
    atomic_write_text(meta, out.getvalue())


def guide_comment(guide: str) -> str:
    text = guide.strip().replace("--", "- -")
    return f"<!-- Guida: {text} -->\n" if text else ""


def create_node(root: Path, node: SkeletonNode, parent_path: str | None, lang: str) -> str:
    """Create one node (not its children) under ``parent_path``; returns its project path."""
    title = node.title(lang)
    if node.nodi or parent_path is None:
        path = ops.create_chapter(root, title, parent_path)
        _tag_chapter(root, path, node.id)
        return path
    path = ops.create_section(root, parent_path, title)
    meta: dict[str, object] = {"title": title, TAG: node.id}
    atomic_write_text(root / path, render(Document(meta, guide_comment(node.guida))))
    return path


def apply_skeleton(root: Path, skeleton: Skeleton, lang: str) -> dict[str, str]:
    """Create every node, in order; returns ``{node id: path}``."""
    created: dict[str, str] = {}

    def visit(nodes: list[SkeletonNode], parent: str | None) -> None:
        for node in nodes:
            created[node.id] = create_node(root, node, parent, lang)
            visit(node.nodi, created[node.id])

    visit(skeleton.nodi, None)
    return created
