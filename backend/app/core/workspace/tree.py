"""Chapter/section tree of a project, derived only from the file system (ADR-001)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from app.core.workspace.frontmatter import FrontMatterError, parse
from app.core.workspace.ordering import sort_key, split_prefix

CHAPTERS_DIR = "capitoli"
CHAPTER_META = "_capitolo.yaml"
IMAGES_DIR = "img"
MAX_DEPTH = 3  # a chapter plus two levels of sub-chapters (RF-02)

_HEADING = re.compile(r"^#\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Node:
    kind: Literal["chapter", "section"]
    path: str  # POSIX path relative to the project root
    name: str
    title: str
    children: list[Node] = field(default_factory=list)


def humanize(name: str) -> str:
    """``'02-procedura-di_montaggio.md'`` -> ``'Procedura di montaggio'``."""
    stem = split_prefix(name)[1]
    if stem.lower().endswith(".md"):
        stem = stem[:-3]
    text = re.sub(r"[-_]+", " ", stem).strip()
    return text[:1].upper() + text[1:] if text else name


def _first_heading(body: str) -> str | None:
    in_fence = False
    for line in body.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and (m := _HEADING.match(line)):
            return m[1]
    return None


def section_title(path: Path) -> str:
    """Front matter ``title``, else the first heading, else the file name (RF-04)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return humanize(path.name)
    try:
        doc = parse(text)
    except FrontMatterError:
        return _first_heading(text) or humanize(path.name)
    title = doc.meta.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return _first_heading(doc.body) or humanize(path.name)


def chapter_title(path: Path) -> str:
    meta = path / CHAPTER_META
    if meta.is_file():
        try:
            data = YAML(typ="safe").load(meta.read_text(encoding="utf-8"))
        except (YAMLError, OSError, UnicodeDecodeError):
            data = None
        if isinstance(data, dict) and isinstance(data.get("title"), str) and data["title"].strip():
            return str(data["title"]).strip()
    return humanize(path.name)


def _visible(entry: Path) -> bool:
    return not entry.name.startswith((".", "_"))


def _children(directory: Path, root: Path, depth: int) -> list[Node]:
    nodes: list[Node] = []
    try:
        entries = sorted(
            (e for e in directory.iterdir() if _visible(e)), key=lambda e: sort_key(e.name)
        )
    except OSError:
        # renamed or removed while the tree was being read (drag and drop renumbers folders):
        # the file watcher reports the change and the client reads the tree again
        return nodes
    for entry in entries:
        rel = entry.relative_to(root).as_posix()
        if entry.is_dir():
            if entry.name == IMAGES_DIR or depth > MAX_DEPTH:
                continue
            nodes.append(
                Node(
                    "chapter",
                    rel,
                    entry.name,
                    chapter_title(entry),
                    _children(entry, root, depth + 1),
                )
            )
        elif entry.suffix.lower() == ".md":
            nodes.append(Node("section", rel, entry.name, section_title(entry)))
    return nodes


def build_tree(root: Path) -> list[Node]:
    chapters = root / CHAPTERS_DIR
    if not chapters.is_dir():
        return []
    try:
        top = sorted(
            (e for e in chapters.iterdir() if e.is_dir() and _visible(e)),
            key=lambda e: sort_key(e.name),
        )
    except OSError:
        return []
    return [
        Node(
            "chapter",
            e.relative_to(root).as_posix(),
            e.name,
            chapter_title(e),
            _children(e, root, 2),
        )
        for e in top
        if e.name != IMAGES_DIR
    ]
