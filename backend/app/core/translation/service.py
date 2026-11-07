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
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import sha256_text
from app.core.workspace.manifest import Project
from app.core.workspace.sections import read_section, write_section
from app.core.workspace.tree import Node, build_tree

from . import glossary as glossary_mod
from . import guard, store, tm
from .llm_client import LlmClient, LlmError, LlmUnavailable
from .queue import TranslationQueue
from .store import SegmentFile, StoredSegment
from .translator import PROMPT_VERSION, Context, Outcome, revise, translate

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
        self._raw_emit = emit
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
        self._gate: Callable[[], bool] = lambda: False

    def _emit(self, root: Path, event: dict[str, Any]) -> None:
        """Publish an event; endpoints run in threads, the hub's queues belong to the event loop."""
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if self._loop is None or running is self._loop:
            self._raw_emit(root, event)
        else:
            self._loop.call_soon_threadsafe(self._raw_emit, root, event)

    def set_gate(self, blocked: Callable[[], bool]) -> None:
        """While ``blocked()`` is true (model still downloading) jobs wait, as when offline."""
        self._gate = blocked

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

    async def reconfigure(self, config: LlmConfig) -> None:
        """Use another endpoint or model from now on; queued jobs and the offline monitor follow."""
        old = list(self._clients.values())
        self.config = config
        self._clients.clear()
        self._online = None
        if self._monitor and not self._monitor.done():
            self._monitor.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor
        self._monitor = None
        self.queue.pause(False)  # paused jobs try the new endpoint at once
        for client in old:
            await client.aclose()

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
        force: bool = False,
    ) -> SegmentFile | None:
        """Bring every target language up to date; the official one first and at full priority.

        Additional languages (RF-21b, RF-21c) are queued at the lowest priority, so they never
        make the official translation wait.
        """
        result = self._sync_one(root, project, rel, text, priority, force)
        for code in project.target_languages[1:]:
            self._sync_one(
                root, project.for_language(code), rel, text, priority, force, PRIORITY_BULK
            )
        return result

    def _sync_one(
        self,
        root: Path,
        project: Project,
        rel: str,
        text: str,
        priority: int = PRIORITY_EDIT,
        force: bool = False,
        floor: int = 0,
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

        segments: list[StoredSegment] = []
        todo: list[tuple[StoredSegment, int]] = []
        for seg in doc.segments:
            m = match.get(seg.key)
            kept = by_key.get(m.old_key) if m else None
            if kept is None:
                new = StoredSegment(seg.key, seg.hash, seg.kind, status="queued")
                if not force and self._reuse(root, project, new, seg.source):
                    segments.append(new)
                    continue
                todo.append((new, max(PRIORITY_EDIT, floor)))
                segments.append(new)
                continue
            current = StoredSegment(**{**kept.__dict__, "key": seg.key, "kind": seg.kind})
            segments.append(current)
            if m is not None and not m.exact:
                current.source_hash = seg.hash
                if current.locked:
                    current.status = "needs_review"
                    current.reason = "source changed"
                elif self._reuse(root, project, current, seg.source):
                    continue  # the new wording is already in the memory
                else:
                    current.status = "queued"
                todo.append((current, max(PRIORITY_EDIT, floor)))
            elif force and not current.locked:
                current.status = "queued"
                todo.append((current, max(priority, floor)))
            elif current.status == "queued":
                todo.append((current, max(PRIORITY_OPEN, floor)))
        result = SegmentFile(sha256_text(text), segments)
        store.save(root, lang, rel, result)

        # drop jobs for segments that no longer exist
        live = {s.key for s in segments}
        for stale in (s for s in old if s.key not in live):
            self.queue.cancel(_job_id(root, lang, rel, stale.key))

        entries = self._glossary(root)
        for stored, prio in todo:
            job = self._make_job(root, project, rel, doc, segments, stored.key, prio, meta, entries)
            self.queue.submit(_job_id(root, lang, rel, stored.key), prio, job)
            self._emit(
                root, {"type": "segment.queued", "path": rel, "lang": lang, "key": stored.key}
            )
        self._emit(root, {"type": "job.progress", "pending": self.queue.pending()})
        return result

    @staticmethod
    def _reuse(root: Path, project: Project, seg: StoredSegment, source: str) -> bool:
        """Fill ``seg`` from the translation memory when this exact source is already there."""
        hit = tm.exact(root, project.lingua_sorgente, project.lingua_ufficiale, source)
        if hit is None:
            return False
        seg.target, seg.origin, seg.status, seg.reason = hit.target, "tm", "translated", ""
        return True

    def _make_job(
        self,
        root: Path,
        project: Project,
        rel: str,
        doc: SegmentedDocument,
        stored: list[StoredSegment],
        key: str,
        priority: int,
        meta: dict[str, Any] | None = None,
        entries: list[glossary_mod.Entry] | None = None,
    ) -> Job:
        seg = doc.by_key()[key]
        ctx = self._context(root, project, doc, stored, key, meta, entries)
        # the endpoint is resolved when the job runs, so a changed setting also applies to queued
        # jobs; only a per-project model override is fixed here
        override = project.llm.modello if project.llm and project.llm.modello else ""
        return Job(
            root, rel, project.lingua_ufficiale, key, seg.hash, seg.source, priority, ctx,
            "", override,
        )  # fmt: skip

    def _context(
        self,
        root: Path,
        project: Project,
        doc: SegmentedDocument,
        stored: list[StoredSegment],
        key: str,
        meta: dict[str, Any] | None = None,
        entries: list[glossary_mod.Entry] | None = None,
    ) -> Context:
        if meta is None:
            try:
                meta = frontmatter.parse(doc.text).meta
            except frontmatter.FrontMatterError:
                meta = {}
        if entries is None:
            entries = self._glossary(root)
        seg = doc.by_key()[key]
        return Context(
            project.lingua_sorgente,
            project.lingua_ufficiale,
            str(meta.get("tono") or project.tono),
            _section_title(doc, meta),
            str(meta.get("contesto") or ""),
            *_previous(doc, stored, key),
            non_translate=glossary_mod.do_not_translate(entries),
            glossary=tuple(glossary_mod.relevant(entries, seg.source)),
        )

    @staticmethod
    def _glossary(root: Path) -> list[glossary_mod.Entry]:
        try:
            return glossary_mod.load(root)
        except (WorkspaceError, ValueError):
            return []  # a broken glossary must not stop the translation

    # -- jobs --------------------------------------------------------------------------------
    async def _run(self, job_id: str, job: Job) -> None:
        base_url, model = self.config.base_url, job.model or self.config.model
        client = self._client(base_url, model)
        if self._gate():
            self._set_online(False, model, "the model is being downloaded")
            self.queue.pause(True)
            self.queue.submit(job_id, job.priority, job)
            self._start_monitor(base_url, model)
            return
        try:
            outcome = await translate(client, job.source, job.ctx)
        except LlmUnavailable as exc:
            self._set_online(False, model, str(exc))
            self.queue.pause(True)
            self.queue.submit(job_id, job.priority, job)
            self._start_monitor(base_url, model)
            return
        except LlmError as exc:
            self._record(job, None, f"model error: {exc}")
            return
        self._set_online(True, model)
        self._record(job, outcome, "")

    def _record(self, job: Job, outcome: Outcome | None, error: str) -> None:
        def mutate(file: SegmentFile) -> None:
            seg = file.get(job.key)
            if seg is None or seg.source_hash != job.source_hash:
                return  # superseded by a newer edit: ignore this answer
            seg.model = job.model or self.config.model
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
                if self._gate():
                    continue
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
        try:
            meta = frontmatter.parse(text).meta
        except frontmatter.FrontMatterError:
            meta = {}
        return {
            "path": rel,
            "lang": lang,
            "tone": meta.get("tono") or None,
            "project_tone": project.tono,
            "note": str(meta.get("contesto") or ""),
            "markdown": assemble(doc, targets),
            "segments": rows,
            "pending": sum(1 for r in rows if r["status"] == "queued"),
        }

    def review(self, root: Path, project: Project) -> list[dict[str, Any]]:
        """Every translated segment of the project, for the review mode (docs/03-ui.md)."""
        rows: list[dict[str, Any]] = []

        def visit(nodes: list[Node]) -> None:
            for node in nodes:
                if node.kind == "chapter":
                    visit(node.children)
                    continue
                try:
                    text = (root / node.path).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                view = self.translation(root, project, node.path, text)
                for row in view["segments"]:
                    if row["status"] == "queued" and not row["target"]:
                        continue
                    rows.append({**row, "path": node.path, "section": node.title})

        visit(build_tree(root))
        return rows

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


# --- author actions on one segment (RF-23, 24, 26, 28) --------------------------------------


def _queue(seg: StoredSegment) -> None:
    seg.status = "queued"
    seg.reason = ""


def refusal(reason: str) -> WorkspaceError:
    """A rewrite that was not accepted: off-topic requests get a code the interface can explain."""
    if reason == guard.OFF_TOPIC:
        return WorkspaceError(
            "off_topic",
            "The instruction asks for something other than rewriting this text, "
            "so nothing was changed. Edit the text by hand to add content.",
        )
    return WorkspaceError("model_refused", reason)


class SegmentActions:
    """Edits made by the author. They never wait for the model, except ``revise``."""

    def __init__(self, service: TranslationService) -> None:
        self.service = service

    def _change(
        self,
        root: Path,
        project: Project,
        rel: str,
        key: str,
        mutate: Callable[[StoredSegment], None],
    ) -> StoredSegment:
        lang = project.lingua_ufficiale
        changed: list[StoredSegment] = []

        def apply(file: SegmentFile) -> None:
            seg = file.get(key)
            if seg is None:
                raise WorkspaceError("not_found", f"segment not found: {key}")
            mutate(seg)
            seg.updated_at = store.now()
            changed.append(seg)

        if store.update(root, lang, rel, apply) is None:
            raise WorkspaceError("not_found", f"no translation yet for {rel}")
        self.service._emit(
            root,
            {"type": "segment.updated", "path": rel, "lang": lang, "key": key,
             "status": changed[0].status},
        )  # fmt: skip
        return changed[0]

    def edit(self, root: Path, project: Project, rel: str, key: str, target: str) -> StoredSegment:
        def go(seg: StoredSegment) -> None:
            seg.target = target
            seg.origin = "manual"
            seg.locked = True
            seg.status = "translated"
            seg.pending_target = None
            seg.reason = ""

        row = self._change(root, project, rel, key, go)
        self._remember(root, project, rel, key, row, "manual")
        return row

    def _remember(
        self, root: Path, project: Project, rel: str, key: str, row: StoredSegment, origin: str
    ) -> None:
        """Keep an approved or hand-written translation in the memory (never a stale one)."""
        seg = segment(read_section(root, rel)[0]).by_key().get(key)
        if seg is not None and seg.hash == row.source_hash and row.target:
            tm.remember(
                root,
                project.lingua_sorgente,
                project.lingua_ufficiale,
                seg.source,
                row.target,
                origin,
            )

    def lock(self, root: Path, project: Project, rel: str, key: str, locked: bool) -> StoredSegment:
        def go(seg: StoredSegment) -> None:
            seg.locked = locked

        return self._change(root, project, rel, key, go)

    def approve(self, root: Path, project: Project, rel: str, key: str) -> StoredSegment:
        def go(seg: StoredSegment) -> None:
            if not seg.target:
                raise WorkspaceError("invalid_state", "nothing to approve yet")
            seg.status = "approved"
            seg.reason = ""

        row = self._change(root, project, rel, key, go)
        self._remember(root, project, rel, key, row, "approved")
        return row

    def accept_pending(self, root: Path, project: Project, rel: str, key: str) -> StoredSegment:
        def go(seg: StoredSegment) -> None:
            if seg.pending_target is None:
                raise WorkspaceError("invalid_state", "there is no proposal to accept")
            seg.target = seg.pending_target
            seg.pending_target = None
            seg.origin = "mt"
            seg.status = "translated"
            seg.reason = ""

        return self._change(root, project, rel, key, go)

    def dismiss_pending(self, root: Path, project: Project, rel: str, key: str) -> StoredSegment:
        def go(seg: StoredSegment) -> None:
            seg.pending_target = None
            seg.status = "translated"
            seg.reason = ""

        return self._change(root, project, rel, key, go)

    def mark_diverged(self, root: Path, project: Project, rel: str, key: str) -> StoredSegment:
        def go(seg: StoredSegment) -> None:
            seg.status = "diverged"

        return self._change(root, project, rel, key, go)

    def apply_source(
        self, root: Path, project: Project, rel: str, key: str, new_source: str
    ) -> None:
        """Rewrite the *source* of one segment (the translation was edited directly, RF-24).

        The segment keeps its translation: it is marked as matching the new source before the
        file is written, so the change is not taken for an edit that needs retranslation.
        """
        lang = project.lingua_ufficiale
        text, digest = read_section(root, rel)
        doc = segment(text)
        if key not in doc.by_key():
            raise WorkspaceError("not_found", f"segment not found: {key}")
        updated = assemble(doc, {key: new_source})
        new_seg = segment(updated).by_key().get(key)
        if new_seg is None:
            raise WorkspaceError("invalid_state", "the new text does not stay a single segment")

        def go(seg: StoredSegment) -> None:
            seg.source_hash = new_seg.hash
            seg.status = "translated"
            seg.reason = ""

        self._change(root, project, rel, key, go)

        def fix_hash(file: SegmentFile) -> None:
            file.source_file_hash = sha256_text(updated)

        store.update(root, lang, rel, fix_hash)
        write_section(root, rel, updated, digest)

    def retranslate(self, root: Path, project: Project, rel: str, key: str) -> None:
        """Translate one segment again now. A locked one only receives a proposal."""
        svc = self.service
        text = (root / rel).read_text(encoding="utf-8")
        svc.sync(root, project, rel, text, PRIORITY_EDIT)  # make sure the store is current
        lang = project.lingua_ufficiale
        file = store.load(root, lang, rel)
        seg = file.get(key) if file else None
        if file is None or seg is None:
            raise WorkspaceError("not_found", f"segment not found: {key}")
        if not seg.locked:
            self._change(root, project, rel, key, _queue)
        job = svc._make_job(root, project, rel, segment(text), file.segments, key, PRIORITY_EDIT)
        svc.queue.submit(_job_id(root, lang, rel, key), PRIORITY_EDIT, job)

    async def back_translate(self, root: Path, project: Project, rel: str, key: str) -> str:
        """Source-language proposal for a translation edited directly by the author (RF-24)."""
        stored = store.load(root, project.lingua_ufficiale, rel)
        current = stored.get(key) if stored else None
        if current is None or not current.target:
            raise WorkspaceError("not_found", f"segment not translated yet: {key}")
        svc = self.service
        client = svc._client(*svc._config_for(project))
        ctx = Context(project.lingua_ufficiale, project.lingua_sorgente, project.tono)
        outcome = await translate(client, current.target, ctx)
        if not outcome.ok:
            raise WorkspaceError("model_refused", outcome.reason)
        return outcome.target

    async def revise(
        self,
        root: Path,
        project: Project,
        rel: str,
        key: str,
        instruction: str,
        alternatives: bool = False,
    ) -> list[str]:
        """Propose a rewritten translation, never saved (``alternatives``: up to 3 variants)."""
        text = (root / rel).read_text(encoding="utf-8")
        doc = segment(text)
        source = doc.by_key().get(key)
        stored = store.load(root, project.lingua_ufficiale, rel)
        current = stored.get(key) if stored else None
        if source is None or current is None or not current.target:
            raise WorkspaceError("not_found", f"segment not translated yet: {key}")
        svc = self.service
        base_url, model = svc._config_for(project)
        client = svc._client(base_url, model)
        ctx = svc._context(root, project, doc, stored.segments if stored else [], key)
        if not alternatives:
            outcome = await revise(client, source.source, current.target, instruction, ctx)
            if not outcome.ok:
                raise refusal(outcome.reason)
            return [outcome.target]
        variants = [
            "Give a clearly different wording from the obvious one.",
            "Prefer a more concise wording.",
            "Prefer a more natural, idiomatic wording.",
        ]
        results = await asyncio.gather(
            *(
                revise(client, source.source, current.target, instruction, ctx,
                       variant=v, temperature=0.8)
                for v in variants
            )
        )  # fmt: skip
        seen: list[str] = []
        for r in results:
            if r.ok and r.target not in seen and r.target != current.target:
                seen.append(r.target)
        return seen
