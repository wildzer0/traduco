"""Rendered Mermaid diagrams, cached by the hash of their code (ADR-012).

The browser renders the diagram (mermaid.js) and uploads SVG + PNG; the export uses the PNG.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from pathlib import Path
from typing import Literal

from app.core.workspace.assets import detect_extension
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_bytes

CACHE_DIR = ".traduco/cache/diagrams"
MAX_BYTES = 2 * 1024 * 1024
_HASH = re.compile(r"^[0-9a-f]{64}$")


def diagram_hash(code: str) -> str:
    """Cache key of a diagram: SHA-256 of its source, exactly as written."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _check_hash(digest: str) -> str:
    if not _HASH.match(digest):
        raise WorkspaceError("invalid_path", "invalid diagram hash")
    return digest


def decode_png(data: str) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WorkspaceError("invalid_image", "the PNG is not valid base64") from exc


def save_diagram(root: Path, digest: str, svg: str, png: bytes) -> None:
    _check_hash(digest)
    svg_bytes = svg.encode("utf-8")
    if len(svg_bytes) > MAX_BYTES or len(png) > MAX_BYTES:
        raise WorkspaceError("too_large", "diagram image too large")
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise WorkspaceError("invalid_image", "the diagram PNG is not a PNG file")
    if detect_extension(svg_bytes) != ".svg":
        raise WorkspaceError("invalid_image", "the diagram SVG is not a safe SVG")
    folder = root / CACHE_DIR
    atomic_write_bytes(folder / f"{digest}.png", png)
    atomic_write_bytes(folder / f"{digest}.svg", svg_bytes)


def read_diagram(root: Path, digest: str, fmt: Literal["svg", "png"]) -> Path:
    _check_hash(digest)
    path = root / CACHE_DIR / f"{digest}.{fmt}"
    if not path.is_file():
        raise WorkspaceError("not_found", "diagram not rendered yet")
    return path
