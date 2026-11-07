"""Per-section segment files: ``.traduco/segmenti/<lang>/<section path without .md>.json``."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.workspace.fsio import atomic_write_text

_lock = threading.Lock()


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class StoredSegment:
    key: str
    source_hash: str
    kind: str
    target: str = ""
    origin: str = "mt"
    status: str = "queued"
    locked: bool = False
    pending_target: str | None = None
    model: str = ""
    prompt_version: str = ""
    updated_at: str = ""
    reason: str = ""


@dataclass
class SegmentFile:
    source_file_hash: str
    segments: list[StoredSegment]

    def get(self, key: str) -> StoredSegment | None:
        return next((s for s in self.segments if s.key == key), None)


def segment_path(root: Path, lang: str, rel: str) -> Path:
    return root / ".traduco" / "segmenti" / lang / (str(Path(rel).with_suffix("")) + ".json")


def load(root: Path, lang: str, rel: str) -> SegmentFile | None:
    path = segment_path(root, lang, rel)
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        segments = [StoredSegment(**s) for s in data["segments"]]
        return SegmentFile(str(data["source_file_hash"]), segments)
    except (OSError, ValueError, KeyError, TypeError):
        return None  # missing or damaged: it is only a cache of the model's work


def save(root: Path, lang: str, rel: str, file: SegmentFile) -> None:
    payload = {
        "source_file_hash": file.source_file_hash,
        "segments": [asdict(s) for s in file.segments],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(segment_path(root, lang, rel), text)


def update(root: Path, lang: str, rel: str, mutate: Any) -> SegmentFile | None:
    """Read-modify-write under a lock; ``mutate(file)`` edits the loaded file in place."""
    with _lock:
        file = load(root, lang, rel)
        if file is None:
            return None
        mutate(file)
        save(root, lang, rel, file)
        return file
