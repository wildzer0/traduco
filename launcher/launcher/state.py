"""Persistent launcher state (``.runtime/state.json``) and input hashing for idempotent steps."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path


def hash_files(paths: Iterable[Path]) -> str:
    """Stable digest of file names and contents; missing files are ignored."""
    h = hashlib.sha256()
    for p in sorted(set(paths)):
        if p.is_file():
            h.update(p.as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def hash_tree(root: Path, ignore: tuple[str, ...] = ("node_modules", "dist", ".vite")) -> str:
    files = [
        p
        for p in root.rglob("*")
        if p.is_file() and not any(part in ignore for part in p.relative_to(root).parts)
    ]
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()


class State:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, str] = {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data = {str(k): str(v) for k, v in loaded.items()}
        except (OSError, ValueError):
            pass

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)
