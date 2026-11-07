"""Priority job queue with replacement of superseded requests (docs/02, "Motore di traduzione").

Priorities (lower runs first): 1 segment being edited, 2 visible segments, 3 rest of the open
file, 4 bulk retranslation. Submitting a job whose id is already queued replaces it; if the same
id is *running* with a different payload the running call is cancelled and the new one queued.
"""

from __future__ import annotations

import asyncio
import contextlib
import heapq
import itertools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

P = TypeVar("P")


@dataclass(order=True)
class _Entry[P]:
    priority: int
    seq: int
    job_id: str = field(compare=False)
    payload: P = field(compare=False)


class TranslationQueue[P]:
    def __init__(self, handler: Callable[[str, P], Awaitable[None]], concurrency: int = 2) -> None:
        self._handler = handler
        self._concurrency = concurrency
        self._heap: list[_Entry[P]] = []
        self._queued: dict[str, _Entry[P]] = {}
        self._running: dict[str, tuple[asyncio.Task[None], P]] = {}
        self._seq = itertools.count()
        self._wake = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()
        self._workers: list[asyncio.Task[None]] = []
        self._paused = False

    # -- control -----------------------------------------------------------------------------
    def start(self) -> None:
        if not self._workers:
            self._workers = [asyncio.create_task(self._work()) for _ in range(self._concurrency)]

    async def stop(self) -> None:
        for task in [*self._workers, *(t for t, _ in self._running.values())]:
            task.cancel()
        for task in [*self._workers, *(t for t, _ in self._running.values())]:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._workers.clear()
        self._running.clear()

    def pause(self, paused: bool) -> None:
        self._paused = paused
        if not paused:
            self._wake.set()

    async def join(self) -> None:
        """Wait until nothing is queued or running."""
        await self._idle.wait()

    # -- jobs --------------------------------------------------------------------------------
    def submit(self, job_id: str, priority: int, payload: P) -> None:
        running = self._running.get(job_id)
        if running is not None and running[1] != payload:
            running[0].cancel()
        self._queued.pop(job_id, None)  # a stale heap entry is skipped when popped
        entry = _Entry(priority, next(self._seq), job_id, payload)
        self._queued[job_id] = entry
        heapq.heappush(self._heap, entry)
        self._idle.clear()
        self._wake.set()

    def cancel(self, job_id: str) -> None:
        self._queued.pop(job_id, None)
        running = self._running.get(job_id)
        if running is not None:
            running[0].cancel()
        self._update_idle()

    def cancel_prefix(self, prefix: str) -> None:
        for job_id in [j for j in (*self._queued, *self._running) if j.startswith(prefix)]:
            self.cancel(job_id)

    def pending(self) -> int:
        return len(self._queued) + len(self._running)

    # -- internals ---------------------------------------------------------------------------
    def _pop(self) -> _Entry[P] | None:
        while self._heap:
            entry = heapq.heappop(self._heap)
            if self._queued.get(entry.job_id) is entry and entry.job_id not in self._running:
                del self._queued[entry.job_id]
                return entry
            if self._queued.get(entry.job_id) is entry:  # same id still running: try later
                heapq.heappush(self._heap, entry)
                return None
        return None

    def _update_idle(self) -> None:
        if not self._queued and not self._running:
            self._idle.set()

    async def _work(self) -> None:
        while True:
            entry = None if self._paused else self._pop()
            if entry is None:
                self._wake.clear()
                if not self._paused and self._heap and self._running:
                    # an entry waits for its running twin: poll shortly
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(self._wake.wait(), 0.05)
                else:
                    await self._wake.wait()
                continue
            task = asyncio.current_task()
            assert task is not None
            self._running[entry.job_id] = (task, entry.payload)
            try:
                await self._handler(entry.job_id, entry.payload)
            except asyncio.CancelledError:
                if not self._workers:  # shutting down
                    raise
                # only the job was cancelled: keep this worker alive
                current = asyncio.current_task()
                if current is not None:
                    current.uncancel()
            except Exception:  # noqa: BLE001 - one failing job must not kill the worker
                pass
            finally:
                self._running.pop(entry.job_id, None)
                self._update_idle()
                self._wake.set()
