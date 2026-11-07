"""Per-project event hub: one file watcher per project, fanned out to WebSocket clients."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any

from watchfiles import awatch

from app.core.workspace.watcher import describe_changes

DEBOUNCE_MS = 300


class EventHub:
    def __init__(self) -> None:
        self._queues: dict[Path, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._tasks: dict[Path, asyncio.Task[None]] = {}

    def subscribe(self, root: Path) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._queues.setdefault(root, set()).add(queue)
        if root not in self._tasks:
            self._tasks[root] = asyncio.create_task(self._watch(root))
        return queue

    async def unsubscribe(self, root: Path, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subscribers = self._queues.get(root, set())
        subscribers.discard(queue)
        if not subscribers:
            self._queues.pop(root, None)
            task = self._tasks.pop(root, None)
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    def publish(self, root: Path, event: dict[str, Any]) -> None:
        for queue in self._queues.get(root, ()):
            with contextlib.suppress(asyncio.QueueFull):  # a stuck client must not block the others
                queue.put_nowait(event)

    async def _watch(self, root: Path) -> None:
        async for changes in awatch(
            root, debounce=DEBOUNCE_MS, recursive=True, ignore_permission_denied=True
        ):
            for event in describe_changes(root, changes):
                self.publish(root, event)

    async def close(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        for task in list(self._tasks.values()):
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        self._queues.clear()
