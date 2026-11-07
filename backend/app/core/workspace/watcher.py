"""Translate raw file-system changes into the events sent to the browser (RF-15, ADR-001)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from watchfiles import Change

from app.core.workspace.fsio import sha256_bytes
from app.core.workspace.tree import CHAPTERS_DIR

PROJECT_FILES = {"progetto.yaml": "project.changed", "glossario.yaml": "glossary.changed"}
_CHANGE_NAMES = {Change.added: "added", Change.modified: "modified", Change.deleted: "deleted"}


def is_relevant(root: Path, path: Path) -> bool:
    """Only project content matters: hidden/temp entries and ``build/`` are skipped."""
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    if not parts or any(p.startswith(".") for p in parts):
        return False
    return parts[0] == CHAPTERS_DIR or (len(parts) == 1 and parts[0] in PROJECT_FILES)


def describe_changes(root: Path, changes: set[tuple[Change, str]]) -> list[dict[str, Any]]:
    """One event per changed path; sections carry their new hash (clients ignore own saves)."""
    events: list[dict[str, Any]] = []
    for change, raw in sorted(changes, key=lambda c: c[1]):
        path = Path(raw)
        if not is_relevant(root, path):
            continue
        rel = path.relative_to(root).as_posix()
        kind = _CHANGE_NAMES[change]
        digest: str | None = None
        if kind != "deleted" and path.suffix.lower() == ".md":
            try:
                digest = sha256_bytes(path.read_bytes())
            except OSError:  # removed again before we could read it
                kind = "deleted"
        elif kind != "deleted" and not path.exists():
            kind = "deleted"
        event_type = PROJECT_FILES.get(rel, "file.changed")
        events.append({"type": event_type, "path": rel, "change": kind, "hash": digest})
    return events
