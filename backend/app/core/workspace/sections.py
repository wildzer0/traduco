"""Read and write section files with optimistic concurrency (hash compare-and-swap)."""

from __future__ import annotations

import threading
from pathlib import Path

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_bytes, sha256_bytes
from app.core.workspace.ops import resolve_node

_write_lock = threading.Lock()  # makes check-then-write atomic within this process


class ConflictError(Exception):
    """The file changed on disk since the client read it."""

    def __init__(self, current_hash: str) -> None:
        super().__init__("the file was modified since it was read")
        self.current_hash = current_hash


def _section_path(root: Path, rel: str) -> Path:
    path = resolve_node(root, rel)
    if not path.is_file() or path.suffix.lower() != ".md":
        raise WorkspaceError("invalid_path", f"not a section: {rel}")
    return path


def read_section(root: Path, rel: str) -> tuple[str, str]:
    """Return ``(content, hash)``; the hash covers the exact bytes on disk."""
    data = _section_path(root, rel).read_bytes()
    try:
        return data.decode("utf-8"), sha256_bytes(data)
    except UnicodeDecodeError as exc:
        raise WorkspaceError("unreadable", f"{rel} is not valid UTF-8") from exc


def write_section(root: Path, rel: str, content: str, expected_hash: str) -> str:
    """Write ``content`` only if the file still has ``expected_hash``; returns the new hash."""
    path = _section_path(root, rel)
    payload = content.encode("utf-8")
    with _write_lock:
        current = sha256_bytes(path.read_bytes())
        if current != expected_hash:
            raise ConflictError(current)
        atomic_write_bytes(path, payload)
    return sha256_bytes(payload)
