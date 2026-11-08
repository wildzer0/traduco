"""Who approved, exported or changed what, and when (RF-94, ADR-046).

An append-only SQLite table next to the workspaces. Nothing here updates or deletes a row.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    id: int
    at: str  # ISO 8601, UTC
    user: str  # the identity provider's stable id
    name: str
    project: str
    action: str  # segment.approve | export | import.accept | issue.create | project.delete ...
    target: str  # the section, issue or file concerned
    detail: str

    def public(self) -> dict[str, object]:
        return asdict(self)


class AuditLog:
    def __init__(
        self, path: Path, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._clock = clock
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " at TEXT NOT NULL, user TEXT NOT NULL, name TEXT NOT NULL, project TEXT NOT NULL,"
                " action TEXT NOT NULL, target TEXT NOT NULL, detail TEXT NOT NULL)"
            )
            self._db.execute("CREATE INDEX IF NOT EXISTS audit_project ON audit (project, id)")

    def record(
        self, user: str, name: str, project: str, action: str, target: str = "", detail: str = ""
    ) -> None:
        at = self._clock().isoformat(timespec="seconds")
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO audit (at, user, name, project, action, target, detail)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (at, user, name, project, action, target, detail),
            )

    def entries(
        self, project: str | None = None, action: str | None = None, limit: int = 200
    ) -> list[Entry]:
        """Newest first."""
        where, args = [], []
        if project:
            where.append("project = ?")
            args.append(project)
        if action:
            where.append("action = ?")
            args.append(action)
        sql = "SELECT id, at, user, name, project, action, target, detail FROM audit"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        with self._lock:
            rows = self._db.execute(sql, (*args, max(1, min(limit, 1000)))).fetchall()
        return [Entry(*row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._db.close()
