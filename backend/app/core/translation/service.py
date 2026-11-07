"""Orchestration: keep the stored translation of a section in step with its source.

``sync`` reconciles the segments of the saved text with the stored ones and queues what needs the
model. Jobs run through :class:`TranslationQueue`; the editor never waits for them. When the
model is unreachable the queue pauses and a monitor resumes it once the server answers (RF-20).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.segmentation.assembler import assemble
from app.core.segmentation.models import SegmentedDocument
from app.core.segmentation.reconcile import reconcile
from app.core.segmentation.segmenter import segment
from app.core.workspace import frontmatter
from app.core.workspace.fsio import sha256_text
from app.core.workspace.manifest import Project

from . import store
from .llm_client import LlmClient, LlmError, LlmUnavailable
from .queue import TranslationQueue
from .store import SegmentFile, StoredSegment
from .translator import PROMPT_VERSION, Context, Outcome, translate

Emit = Callable[[Path, dict[str, Any]], None]
PRIORITY_EDIT, PRIORITY_VISIBLE, PRIORITY_OPEN, PRIORITY_BULK = 1, 2, 3, 4
MONITOR_SECONDS = 3.0


@dataclass(frozen=True)
class Job:
    root: Path
    rel: str
    lang: str
    key: str
    source_hash: str
    source: str
    priority: int
    ctx: Context
    base_url: str
    model: str


@dataclass(frozen=True)
class LlmConfig:
    base_url: str
    model: str
    api_key: str = ""


def _job_id(root: Path, lang: str, rel: str, key: str) -> str:
    return f"{root}|{lang}|{rel}|{key}"


class TranslationService:
    def __init__(
        self,
        config: LlmConfig,
        emit: Emit,
        *,
        concurrency: int = 2,
        monitor_seconds: float = MONITOR_SECONDS,
        client_factory: Callable[[LlmConfig], LlmClient] | None = None,
    ) -> None:
        self.config = config
        self._emit = emit
        self._monitor_seconds = monitor_seconds
        self._factory = client_factory or (
            lambda c: LlmClient(c.base_url, c.model, c.api_key, timeout=60.0)
        )
        self._clients: dict[tuple[str, str], LlmClient] = {}
        self.queue: TranslationQueue[Job] = TranslationQueue(self._run, concurrency)
        self._online: bool | None = None
        self._monitor: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._roots: set[Path] = set()

    # -- lifecycle ---------------------------------------------------------------------------
    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.queue.start()

    async def close(self) -> None:
        if self._monitor:
            self._monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor
        await self.queue.stop()
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

    def _client(self, base_url: str, model: str) -> LlmClient:
        key = (base_url, model)
        if key not in self._clients:
            self._clients[key] = self._factory(LlmConfig(base_url, model, self.config.api_key))
        return self._clients[key]

    def _config_for(self, project: Project) -> tuple[str, str]:
        model = (project.llm.modello if project.llm and project.llm.modello else None) or (
            self.config.model
        )
        return self.config.base_url, model

    # -- status ------------------------------------------------------------------------------
    async def status(self, project: Project | None = None) -> dict[str, Any]:
        base_url, model = (
            self._config_for(project)
            if project
            else (
                self.config.base_url,
                self.config.model,
            )
        )
        try:
            models = await self._client(base_url, model).models()
        except LlmError as exc:
            self._set_online(False, model, str(exc))
            return {"online": False, "model": model, "models": [], "error": str(exc)}
        self._set_online(True, model)
        return {
            "online": True,
            "model": model,
            "models": models,
            "model_available": model in models,
            "pending": self.queue.pending(),
        }

    def _set_online(self, online: bool, model: str, error: str = "") -> None:
        if self._online == online:
            return
        self._online = online
        self._broadcast({"type": "llm.status", "online": online, "model": model, "error": error})

    def _broadcast(self, event: dict[str, Any]) -> None:
        for root in self._roots:
            self._emit(root, event)

    # -- sync --------------------------------------------------------------------------------
    def schedule_sync(self, root: Path, project: Project, rel: str, text: str) -> None:
        """Thread-safe entry point for the file-save handler (runs on the event loop)."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(lambda: self.sync(root, project, rel, text, PRIORITY_EDIT))

    def sync(
        self,
        root: Path,
        project: Project,
        rel: str,
        text: str,
        priority: int = PRIORITY_EDIT,
        *,
        force: bool = False,
    ) -> SegmentFile | None:
        """Reconcile ``text`` with the stored translation and queue the segments that need work."""
        self._roots.add(root)
        lang = project.lingua_ufficiale
        try:
            meta = frontmatter.parse(text).meta
        except frontmatter.FrontMatterError:
            meta = {}
        if meta.get("traduci") is False:
            return None
        doc = segment(text)
        previous = store.load(root, lang, rel)
        old = previous.segments if previous else []
        match = reconcile([(s.key, s.source_hash) for s in old], list(doc.segments))
        by_key = {s.key: s for s in old}
        base_url, model = self._config_for(project)
        section_title = _section_title(doc, meta)
        note = str(meta.get("contesto") or "")
        tone = str(meta.get("tono") or project.tono)

        segments: list[StoredSegment] = []
        todo: list[tuple[StoredSegment, int]] = []
        for seg in doc.segments:
            m = match.get(seg.key)
            kept = by_key.get(m.old_key) if m else None
            if kept is None:
                new = StoredSegment(seg.key, seg.hash, seg.kind, status="queued")
                todo.append((new, PRIORITY_EDIT))
                segments.append(new)
                continue
            current = StoredSegment(**{**kept.__dict__, "key": seg.key, "kind": seg.kind})
            segments.append(current)
            if m is not None and not m.exact:
                current.source_hash = seg.hash
                if current.locked:
                    current.status = "needs_review"
                    current.reason = "source changed"
                else:
                    current.status = "queued"
                todo.append((current, PRIORITY_EDIT))
            elif force and not current.locked:
                current.status = "queued"
                todo.append((current, priority))
            elif current.status == "queued":
                todo.append((current, PRIORITY_OPEN))
        result = SegmentFile(sha256_text(text), segments)
        store.save(root, lang, rel, result)

        # drop jobs for segments that no longer exist
        live = {s.key for s in segments}
        for stale in (s for s in old if s.key not in live):
            self.queue.cancel(_job_id(root, lang, rel, stale.key))

        sources = doc.by_key()
        for stored, prio in todo:
            seg = sources[stored.key]
            ctx = Context(
                project.lingua_sorgente,
                lang,
                tone,
                section_title,
                note,
                *_previous(doc, segments, stored.key),
            )
            job = Job(root, rel, lang, stored.key, seg.hash, seg.source, prio, ctx, base_url, model)
            self.queue.submit(_job_id(root, lang, rel, stored.key), prio, job)
            self._emit(
                root, {"type": "segment.queued", "path": rel, "lang": lang, "key": stored.key}
            )
        self._emit(root, {"type": "job.progress", "pending": self.queue.pending()})
        return result

    # -- jobs --------------------------------------------------------------------------------
    async def _run(self, job_id: str, job: Job) -> None:
        client = self._client(job.base_url, job.model)
        try:
            outcome = await translate(client, job.source, job.ctx)
        except LlmUnavailable as exc:
            self._set_online(False, job.model, str(exc))
            self.queue.pause(True)
            self.queue.submit(job_id, job.priority, job)
            self._start_monitor(job.base_url, job.model)
            return
        except LlmError as exc:
            self._record(job, None, f"model error: {exc}")
            return
        self._set_online(True, job.model)
        self._record(job, outcome, "")

    def _record(self, job: Job, outcome: Outcome | None, error: str) -> None:
        def mutate(file: SegmentFile) -> None:
            seg = file.get(job.key)
            if seg is None or seg.source_hash != job.source_hash:
                return  # superseded by a newer edit: ignore this answer
            seg.model = job.model
            seg.prompt_version = PROMPT_VERSION
            seg.updated_at = store.now()
            if outcome is None or not outcome.ok:
                reason = error or (outcome.reason if outcome else "")
                if seg.locked:
                    seg.status = "needs_review"
                    seg.reason = reason
                    return
                if outcome is not None and outcome.target:
                    seg.target = outcome.target
                seg.status = "needs_review"
                seg.reason = reason
            elif seg.locked:
                seg.pending_target = outcome.target
                seg.status = "needs_review"
                seg.reason = "source changed"
            else:
                seg.target = outcome.target
                seg.origin = "mt"
                seg.status = "translated"
                seg.reason = ""

        file = store.update(job.root, job.lang, job.rel, mutate)
        if file is None:
            return
        seg = file.get(job.key)
        if seg is not None and seg.source_hash == job.source_hash:
            self._emit(
                job.root,
                {
                    "type": "segment.updated",
                    "path": job.rel,
                    "lang": job.lang,
                    "key": job.key,
                    "status": seg.status,
                },
            )
        self._emit(job.root, {"type": "job.progress", "pending": max(0, self.queue.pending() - 1)})

    def _start_monitor(self, base_url: str, model: str) -> None:
        if self._monitor and not self._monitor.done():
            return

        async def watch() -> None:
            client = self._client(base_url, model)
            while True:
                await asyncio.sleep(self._monitor_seconds)
                try:
                    await client.models()
                except LlmError:
                    continue
                self._set_online(True, model)
                self.queue.pause(False)
                return

        self._monitor = asyncio.create_task(watch())

    # -- reading -----------------------------------------------------------------------------
    def translation(self, root: Path, project: Project, rel: str, text: str) -> dict[str, Any]:
        """Segments of ``rel`` with their translation, plus the assembled target Markdown."""
        lang = project.lingua_ufficiale
        doc = segment(text)
        stored = store.load(root, lang, rel)
        known = {s.key: s for s in stored.segments} if stored else {}
        offset = len(frontmatter.split_raw(text)[0].splitlines())
        targets: dict[str, str] = {}
        rows: list[dict[str, Any]] = []
        for seg in doc.segments:
            st = known.get(seg.key)
            fresh = st is not None and st.source_hash == seg.hash
            if st is not None and st.target and (fresh or st.locked):
                targets[seg.key] = st.target
            status = st.status if st is not None else "queued"
            if st is not None and not fresh and not st.locked:
                status = "queued"
            rows.append(
                {
                    "key": seg.key,
                    "kind": seg.kind,
                    "line": None if seg.kind == "title" else seg.line - offset,
                    "end": None if seg.kind == "title" else seg.end - offset,
                    "source": seg.source,
                    "target": targets.get(seg.key, ""),
                    "status": status,
                    "locked": bool(st and st.locked),
                    "reason": st.reason if st else "",
                    "pending_target": st.pending_target if st else None,
                }
            )
        return {
            "path": rel,
            "lang": lang,
            "markdown": assemble(doc, targets),
            "segments": rows,
            "pending": sum(1 for r in rows if r["status"] == "queued"),
        }

    def retranslate(self, root: Path, project: Project, rels: list[str]) -> int:
        count = 0
        for rel in rels:
            try:
                text = (root / rel).read_text(encoding="utf-8")
            except OSError:
                continue
            result = self.sync(root, project, rel, text, PRIORITY_BULK, force=True)
            count += sum(1 for s in result.segments if s.status == "queued") if result else 0
        return count


def _section_title(doc: SegmentedDocument, meta: dict[str, Any]) -> str:
    if meta.get("title"):
        return str(meta["title"])
    return next((s.source for s in doc.segments if s.kind == "heading"), "")


def _previous(doc: SegmentedDocument, stored: list[StoredSegment], key: str) -> tuple[str, str]:
    """Source and translation of the nearest earlier translated segment, for consistency."""
    order = [s.key for s in doc.segments]
    index = order.index(key)
    sources = doc.by_key()
    known = {s.key: s for s in stored}
    for earlier in reversed(order[:index]):
        st = known.get(earlier)
        if st is not None and st.target and st.status in ("translated", "approved"):
            return sources[earlier].source, st.target
    return "", ""
