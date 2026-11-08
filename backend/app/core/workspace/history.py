"""Earlier versions of a section: a safety net for "I wish I had not deleted that".

Before a section is overwritten, its previous text is kept in ``.traduco/history/`` - but at most
one copy every few minutes, so a long typing session gives one version, not hundreds. The oldest
versions beyond a limit are dropped. Nothing here is part of the document.
"""

from __future__ import annotations

import calendar
import hashlib
import re
import time
from collections.abc import Callable
from pathlib import Path

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_bytes

HISTORY_DIR = ".traduco/history"
MIN_GAP_SECONDS = 300
KEEP = 40
_NAME = re.compile(r"^\d{14}-[0-9a-f]{8}\.md$")


def _folder(root: Path, rel: str) -> Path:
    return root / HISTORY_DIR / hashlib.sha256(rel.encode()).hexdigest()[:16]


def _versions(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted((f for f in folder.iterdir() if _NAME.match(f.name)), reverse=True)


def snapshot(
    root: Path,
    rel: str,
    previous: bytes,
    now: Callable[[], float] = time.time,
    min_gap: float = MIN_GAP_SECONDS,
) -> bool:
    """Keep ``previous`` as a version unless one was kept recently or it is already the newest."""
    if not previous.strip():
        return False
    folder = _folder(root, rel)
    digest = hashlib.sha256(previous).hexdigest()[:8]
    versions = _versions(folder)
    if versions:
        newest = versions[0]
        if newest.name.endswith(f"-{digest}.md"):
            return False
        kept = calendar.timegm(time.strptime(newest.name[:14], "%Y%m%d%H%M%S"))
        if now() - kept < min_gap:
            return False
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime(now()))
    atomic_write_bytes(folder / f"{stamp}-{digest}.md", previous)
    for old in _versions(folder)[KEEP:]:
        old.unlink(missing_ok=True)
    return True


def list_versions(root: Path, rel: str) -> list[dict[str, object]]:
    """Newest first: id, when (UTC, ISO), size and the first line of text."""
    out: list[dict[str, object]] = []
    for f in _versions(_folder(root, rel)):
        text = f.read_text(encoding="utf-8", errors="replace")
        first = next((ln.strip() for ln in text.splitlines() if ln.strip() and ln[0] != "-"), "")
        n = f.name
        when = f"{n[0:4]}-{n[4:6]}-{n[6:8]}T{n[8:10]}:{n[10:12]}:{n[12:14]}Z"
        out.append({"id": f.name[:-3], "at": when, "size": len(text), "preview": first[:80]})
    return out


def read_version(root: Path, rel: str, version_id: str) -> str:
    name = f"{version_id}.md"
    if not _NAME.match(name):
        raise WorkspaceError("invalid_path", "invalid version")
    file = _folder(root, rel) / name
    if not file.is_file():
        raise WorkspaceError("not_found", "version not found")
    return file.read_text(encoding="utf-8")
