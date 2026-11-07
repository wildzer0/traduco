"""Review comments anchored to a segment (RF-83), kept beside the document, not in its text.

``.traduco/commenti/<section path without .md>.json`` holds the threads. A thread remembers the
segment's key, the hash of its source and an excerpt; when the text near it changes the anchor is
found again by key, then by hash, then by the most similar segment, and is *lost* only when none
is close enough.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.core.segmentation.segmenter import segment
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_text
from app.core.workspace.sections import read_section

SIMILAR = 0.6
EXCERPT = 200


def _file(root: Path, rel: str) -> Path:
    read_section(root, rel)  # validates the path and that it is a section
    return root / ".traduco" / "commenti" / (str(Path(rel).with_suffix("")) + ".json")


def _load(root: Path, rel: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(_file(root, rel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _save(root: Path, rel: str, threads: list[dict[str, Any]]) -> None:
    atomic_write_text(_file(root, rel), json.dumps(threads, ensure_ascii=False, indent=2) + "\n")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def locate(thread: dict[str, Any], segments: dict[str, Any]) -> str | None:
    """The key of the segment the thread belongs to now, or None when it cannot be found."""
    anchor = thread["anchor"]
    here = segments.get(anchor["key"])
    if here is not None and here.hash == anchor["hash"]:
        return str(anchor["key"])
    by_hash = [k for k, s in segments.items() if s.hash == anchor["hash"]]
    if len(by_hash) == 1:
        return by_hash[0]
    best, best_key = 0.0, None
    for key, seg in segments.items():
        ratio = SequenceMatcher(None, anchor["excerpt"], seg.source[:EXCERPT]).ratio()
        if ratio > best:
            best, best_key = ratio, key
    return best_key if best >= SIMILAR else None


def threads(root: Path, rel: str) -> list[dict[str, Any]]:
    """The threads with their anchor resolved: ``key`` (None when lost) and the segment's text."""
    segments = segment(read_section(root, rel)[0]).by_key()
    out = []
    for thread in _load(root, rel):
        key = locate(thread, segments)
        out.append(
            {
                **thread,
                "key": key,
                "lost": key is None,
                "source": segments[key].source if key else thread["anchor"]["excerpt"],
            }
        )
    return out


def counts(root: Path, rel: str) -> dict[str, int]:
    rows = _load(root, rel)
    return {
        "open": sum(1 for t in rows if t["status"] == "open"),
        "resolved": sum(1 for t in rows if t["status"] == "resolved"),
    }


def add_thread(root: Path, rel: str, key: str, author: str, text: str) -> dict[str, Any]:
    seg = segment(read_section(root, rel)[0]).by_key().get(key)
    if seg is None:
        raise WorkspaceError("not_found", f"no segment {key} in {rel}")
    if not text.strip():
        raise WorkspaceError("invalid_state", "a comment cannot be empty")
    thread = {
        "id": uuid.uuid4().hex[:12],
        "status": "open",
        "anchor": {"key": key, "hash": seg.hash, "excerpt": seg.source[:EXCERPT]},
        "messages": [{"author": author, "at": _now(), "text": text.strip()}],
    }
    rows = _load(root, rel)
    rows.append(thread)
    _save(root, rel, rows)
    return thread


def _find(rows: list[dict[str, Any]], thread_id: str) -> dict[str, Any]:
    for row in rows:
        if row["id"] == thread_id:
            return row
    raise WorkspaceError("not_found", "comment thread not found")


def reply(root: Path, rel: str, thread_id: str, author: str, text: str) -> dict[str, Any]:
    if not text.strip():
        raise WorkspaceError("invalid_state", "a comment cannot be empty")
    rows = _load(root, rel)
    thread = _find(rows, thread_id)
    thread["messages"].append({"author": author, "at": _now(), "text": text.strip()})
    _save(root, rel, rows)
    return thread


def set_status(root: Path, rel: str, thread_id: str, status: str) -> dict[str, Any]:
    if status not in ("open", "resolved"):
        raise WorkspaceError("invalid_state", "status must be open or resolved")
    rows = _load(root, rel)
    thread = _find(rows, thread_id)
    thread["status"] = status
    _save(root, rel, rows)
    return thread


def remove(root: Path, rel: str, thread_id: str) -> None:
    rows = _load(root, rel)
    _find(rows, thread_id)
    _save(root, rel, [t for t in rows if t["id"] != thread_id])
