"""Images pasted or dropped into the editor go to the chapter's ``img/`` folder (RF-06)."""

from __future__ import annotations

import re
import time
from pathlib import Path

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_bytes, sha256_bytes
from app.core.workspace.ops import resolve_node
from app.core.workspace.ordering import slugify
from app.core.workspace.tree import IMAGES_DIR

MAX_IMAGE_BYTES = 20 * 1024 * 1024
_SVG_ACTIVE = re.compile(rb"<\s*script|\bon[a-z]+\s*=|javascript:|<\s*foreignObject", re.IGNORECASE)


def detect_extension(data: bytes) -> str | None:
    """Image type from the content (never from the client-supplied name)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    head = data[:2048].lstrip().lower()
    if (
        head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:4096].lower())
    ) and not _SVG_ACTIVE.search(data):
        return ".svg"
    return None


def save_image(root: Path, section_rel: str, filename: str, data: bytes) -> str:
    """Store ``data`` next to the section; returns the project-relative path of the image.

    Identical content already stored under the same name is reused instead of duplicated.
    """
    section = resolve_node(root, section_rel)
    if not section.is_file():
        raise WorkspaceError("invalid_path", f"not a section: {section_rel}")
    if len(data) > MAX_IMAGE_BYTES:
        raise WorkspaceError("too_large", f"images are limited to {MAX_IMAGE_BYTES // 2**20} MB")
    ext = detect_extension(data)
    if ext is None:
        raise WorkspaceError("invalid_image", "unsupported or unsafe image content")

    stem = slugify(Path(filename).stem) if Path(filename).stem.strip() else ""
    if not stem or stem == "senza-titolo":
        stem = time.strftime("img-%Y%m%d-%H%M%S")
    folder = section.parent / IMAGES_DIR
    digest = sha256_bytes(data)
    candidate, n = folder / f"{stem}{ext}", 1
    while candidate.exists():
        if sha256_bytes(candidate.read_bytes()) == digest:
            return candidate.relative_to(root).as_posix()
        n += 1
        candidate = folder / f"{stem}-{n}{ext}"
    atomic_write_bytes(candidate, data)
    return candidate.relative_to(root).as_posix()
