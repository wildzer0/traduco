"""Who is working where: section locks and presence (RF-93, ADR-046).

A lock is a *soft* one: it expires on its own a little after the editor's last heartbeat, so a
closed laptop never blocks a section for long. The service is behind a small interface so the
team deployment can keep it in Valkey (shared by several workers) while one process keeps it in
memory.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.core.workspace.errors import WorkspaceError

from .identity import User

TTL_SECONDS = 45.0


@dataclass(frozen=True)
class Seat:
    """One person in a project: who, in which section (``None`` = only looking at the project)."""

    sub: str
    name: str
    path: str | None
    editing: bool  # holds the lock of ``path``


class Coordination(Protocol):
    def heartbeat(self, project: str, user: User, path: str | None, edit: bool) -> Seat: ...
    def check_write(self, project: str, user: User, path: str) -> None: ...
    def holder(self, project: str, path: str) -> str | None: ...
    def seats(self, project: str) -> list[Seat]: ...
    def release(self, project: str, user: User) -> None: ...


@dataclass
class _Entry:
    name: str
    path: str | None
    editing: bool
    seen: float


class MemoryCoordination:
    """Everything in this process; the clock can be replaced in tests."""

    def __init__(self, ttl: float = TTL_SECONDS, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._seats: dict[str, dict[str, _Entry]] = {}

    def _alive(self, project: str) -> dict[str, _Entry]:
        now = self._clock()
        seats = self._seats.setdefault(project, {})
        for sub in [s for s, e in seats.items() if now - e.seen > self._ttl]:
            del seats[sub]
        return seats

    def _owner(self, seats: dict[str, _Entry], path: str, excluding: str = "") -> str | None:
        for sub, entry in seats.items():
            if sub != excluding and entry.editing and entry.path == path:
                return sub
        return None

    def heartbeat(self, project: str, user: User, path: str | None, edit: bool) -> Seat:
        """Record that ``user`` is in ``path``; with ``edit`` take its lock if nobody has it."""
        with self._lock:
            seats = self._alive(project)
            editing = bool(edit and path and self._owner(seats, path, user.sub) is None)
            seats[user.sub] = _Entry(user.label, path, editing, self._clock())
            return Seat(user.sub, user.label, path, editing)

    def check_write(self, project: str, user: User, path: str) -> None:
        """Take the lock of ``path`` for ``user`` or fail with 423 if someone else has it."""
        with self._lock:
            seats = self._alive(project)
            owner = self._owner(seats, path, user.sub)
            if owner is not None:
                raise WorkspaceError("locked", f"{seats[owner].name} is editing this section")
            seats[user.sub] = _Entry(user.label, path, True, self._clock())

    def holder(self, project: str, path: str) -> str | None:
        with self._lock:
            seats = self._alive(project)
            owner = self._owner(seats, path)
            return seats[owner].name if owner else None

    def seats(self, project: str) -> list[Seat]:
        with self._lock:
            return [Seat(sub, e.name, e.path, e.editing) for sub, e in self._alive(project).items()]

    def release(self, project: str, user: User) -> None:
        with self._lock:
            self._alive(project).pop(user.sub, None)
