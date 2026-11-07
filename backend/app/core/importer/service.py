"""Import jobs: read the revised file, find what changed, propose it to the author (RF-65, RF-66).

Nothing is applied here. A job produces *proposals*; each one is shown with the current source text,
the same change written back in the source language, and the client's own wording. The author
accepts, edits or rejects each one (:meth:`ImportManager.decide`).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.export.errors import ExportError
from app.core.segmentation.segmenter import segment
from app.core.translation.llm_client import LlmError
from app.core.translation.service import TranslationService
from app.core.translation.translator import Context, translate
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_bytes, atomic_write_text
from app.core.workspace.manifest import Project
from app.core.workspace.sections import read_section

from . import apply as applying
from .align import align, plain
from .docx_text import DocUnit, export_identifier, read_units
from .snapshot import load_snapshot

CONCURRENCY = 2


@dataclass
class Proposal:
    id: str
    kind: str  # modified | added | deleted
    unit_kind: str  # chapter | title | paragraph | list_item | table_cell | …
    section: str  # section path (chapter path for chapter titles)
    section_title: str
    key: str | None
    after_key: str | None
    old: str  # the text as exported
    new: str  # the client's text
    current_source: str
    proposed_source: str
    source_hash: str | None = None  # the segment's source when it was exported
    after_hash: str | None = None
    authors: list[str] = field(default_factory=list)
    tracked: bool = False
    stale: bool = False
    applicable: bool = True
    status: str = "pending"  # pending | accepted | rejected | failed
    note: str = ""


@dataclass
class ImportJob:
    id: str
    state: str = "running"  # running | done | failed
    progress: int = 0
    message: str = ""
    filename: str = ""
    snapshot: str = ""
    language: str = "ufficiale"
    lang: str = ""  # code of the language the exported file was in
    warnings: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
    proposals: list[Proposal] = field(default_factory=list)

    def public(self) -> dict[str, Any]:
        return asdict(self)


def _folder(root: Path) -> Path:
    return root / ".traduco" / "import"


def _save(root: Path, job: ImportJob) -> None:
    atomic_write_text(
        _folder(root) / f"{job.id}.json",
        json.dumps(job.public(), ensure_ascii=False, indent=2) + "\n",
    )


def _load(root: Path, job_id: str) -> ImportJob | None:
    if not job_id.isalnum():
        return None
    try:
        data = json.loads((_folder(root) / f"{job_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    proposals = [Proposal(**p) for p in data.pop("proposals", [])]
    return ImportJob(**data, proposals=proposals)


def _pairs(units: list[dict[str, Any]], docs: list[DocUnit], fields: dict[str, Any]) -> list[Any]:
    return align([plain(u["text"], fields) for u in units], [plain(d.text, fields) for d in docs])


class ImportManager:
    def __init__(
        self,
        translation: TranslationService,
        publish: Callable[[Path, dict[str, Any]], None] | None = None,
    ) -> None:
        self._translation = translation
        self._publish = publish
        self._jobs: dict[str, ImportJob] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def get(self, root: Path, job_id: str) -> ImportJob | None:
        return self._jobs.get(job_id) or _load(root, job_id)

    def start(self, root: Path, project: Project, data: bytes, filename: str) -> ImportJob:
        job = ImportJob(uuid.uuid4().hex, filename=filename)
        self._jobs[job.id] = job
        atomic_write_bytes(_folder(root) / job.id / "revised.docx", data)
        task = asyncio.create_task(self._run(job, root, project))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        for task in list(self._tasks):
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # -- the job -----------------------------------------------------------------------------------
    def _step(self, job: ImportJob, progress: int, message: str, root: Path) -> None:
        job.progress, job.message = progress, message
        if self._publish:
            self._publish(root, {"type": "import.progress", "job": job.id, "progress": progress})

    async def _run(self, job: ImportJob, root: Path, project: Project) -> None:
        try:
            await self._analyse(job, root, project)
            job.state, job.progress, job.message = "done", 100, ""
        except (ExportError, WorkspaceError) as exc:
            job.state, job.error = "failed", {"code": exc.code, "message": exc.message}
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # a damaged file must not leave the job running forever
            job.state = "failed"
            job.error = {"code": "import_failed", "message": f"{type(exc).__name__}: {exc}"}
        _save(root, job)
        if self._publish:
            self._publish(
                root,
                {
                    "type": "import.progress",
                    "job": job.id,
                    "progress": job.progress,
                    "state": job.state,
                },
            )

    async def _analyse(self, job: ImportJob, root: Path, project: Project) -> None:
        docx = _folder(root) / job.id / "revised.docx"
        self._step(job, 5, "read", root)
        try:
            identifier = export_identifier(docx)
            found = await asyncio.to_thread(read_units, docx)
        except Exception as exc:
            raise WorkspaceError(
                "invalid_template", f"this is not a readable Word document: {exc}"
            ) from exc
        try:
            snapshot = load_snapshot(root, identifier)
        except WorkspaceError:
            if identifier is None:
                raise
            snapshot = load_snapshot(root, None)
            job.warnings.append(
                "the export this file came from is gone: the most recent one is used"
            )
        job.snapshot, job.language = snapshot["id"], snapshot["language"]
        job.lang = snapshot.get("lang", "")
        fields: dict[str, Any] = snapshot.get("fields", {})
        units: list[dict[str, Any]] = snapshot["units"]

        self._step(job, 20, "align", root)
        changes: list[tuple[Any, bool]] = []
        for notes in (False, True):
            exported = [u for u in units if (u["kind"] == "footnote") == notes]
            docs = [d for d in found if (d.kind == "footnote") == notes]
            for change in _pairs(exported, docs, fields):
                changes.append(((change, exported, docs), notes))
        titles = {u["section"]: u["text"] for u in units if u["kind"] in ("title", "chapter")}
        currents: dict[str, dict[str, Any]] = {}

        def current(path: str) -> dict[str, Any]:
            if path not in currents:
                try:
                    currents[path] = segment(read_section(root, path)[0]).by_key()
                except WorkspaceError:
                    currents[path] = {}
            return currents[path]

        proposals: list[Proposal] = []
        for (change, exported, docs), _ in changes:
            old = exported[change.old] if change.old is not None else None
            new = docs[change.new] if change.new is not None else None
            anchor = exported[change.after] if change.after is not None else None
            proposals.append(
                self._proposal(len(proposals) + 1, change.kind, old, new, anchor, titles, current)
            )
        await self._write_back(job, root, project, proposals)
        job.proposals = proposals
        self._step(job, 95, "save", root)

    @staticmethod
    def _proposal(
        number: int,
        kind: str,
        old: dict[str, Any] | None,
        new: DocUnit | None,
        anchor: dict[str, Any] | None,
        titles: dict[str, str],
        current: Callable[[str], dict[str, Any]],
    ) -> Proposal:
        base = old or anchor or {}
        section = str(base.get("section") or "")
        unit_kind = str((old or {}).get("kind") or "paragraph")
        key = (old or {}).get("key")
        segment_now = current(section).get(key) if key and unit_kind != "chapter" else None
        stale = bool(
            old
            and old.get("source_hash")
            and segment_now is not None
            and segment_now.hash != old["source_hash"]
        ) or bool(key and unit_kind != "chapter" and segment_now is None)
        applicable = True
        note = ""
        if kind == "modified" and unit_kind in ("table_cell", "table_header"):
            applicable, note = False, "table cell"
        if kind in ("added", "deleted") and (anchor or old or {}).get("kind") in (
            "table_cell",
            "table_header",
            "chapter",
        ):
            applicable, note = False, "table or chapter"
        if kind == "modified" and unit_kind not in ("chapter", "title") and key is None:
            applicable, note = False, "no segment"
        after_key = (anchor or {}).get("key") if kind == "added" else None
        after_hash = (anchor or {}).get("source_hash") if kind == "added" else None
        return Proposal(
            id=f"p{number}",
            kind=kind,
            unit_kind=unit_kind if old else "paragraph",
            section=section,
            section_title=titles.get(section, section),
            key=key,
            after_key=after_key,
            old=(old or {}).get("text", ""),
            new=new.text if new else "",
            current_source=segment_now.source if segment_now is not None else "",
            proposed_source=new.text if new else "",
            source_hash=(old or {}).get("source_hash"),
            after_hash=after_hash,
            authors=sorted(new.authors) if new else [],
            tracked=bool(new and new.tracked),
            stale=stale,
            applicable=applicable,
            note=note,
        )

    async def _write_back(
        self, job: ImportJob, root: Path, project: Project, proposals: list[Proposal]
    ) -> None:
        """Write the client's changes in the source language (the model translates them back)."""
        if job.language != "ufficiale":
            return  # the document was in the source language: the client's text is the proposal
        client = self._translation._client(*self._translation._config_for(project))
        todo = [p for p in proposals if p.kind != "deleted" and p.applicable]
        semaphore = asyncio.Semaphore(CONCURRENCY)
        done = 0

        async def one(p: Proposal) -> None:
            nonlocal done
            async with semaphore:
                ctx = Context(
                    job.lang or project.lingua_ufficiale, project.lingua_sorgente, project.tono
                )
                try:
                    outcome = await translate(client, p.new, ctx)
                    if outcome.ok or outcome.target:
                        p.proposed_source = outcome.target
                    else:
                        p.note = "back-translation failed"
                except LlmError:
                    p.note = "model unreachable: edit the proposal by hand"
                done += 1
                self._step(job, 20 + int(70 * done / max(1, len(todo))), "translate", root)

        await asyncio.gather(*(one(p) for p in todo))

    # -- the author decides -------------------------------------------------------------------
    def decide(
        self,
        root: Path,
        project: Project,
        job_id: str,
        proposal_id: str,
        action: str,
        source: str | None = None,
    ) -> Proposal:
        job = self.get(root, job_id)
        if job is None:
            raise WorkspaceError("not_found", "import not found")
        proposal = next((p for p in job.proposals if p.id == proposal_id), None)
        if proposal is None:
            raise WorkspaceError("not_found", "proposal not found")
        if proposal.status != "pending":
            raise WorkspaceError("invalid_state", f"this proposal was already {proposal.status}")
        if action == "reject":
            proposal.status = "rejected"
        else:
            text = (source if source is not None else proposal.proposed_source).strip()
            if proposal.kind != "deleted" and not text:
                raise WorkspaceError("invalid_state", "the proposed text is empty")
            if not proposal.applicable:
                raise WorkspaceError(
                    "not_applicable", "this change cannot be applied automatically"
                )
            self._apply(root, project, job, proposal, text)
            proposal.status = "accepted"
            proposal.proposed_source = text
        self._jobs[job.id] = job
        _save(root, job)
        return proposal

    def _apply(self, root: Path, project: Project, job: ImportJob, p: Proposal, text: str) -> None:
        official = job.language == "ufficiale"
        lang = job.lang or project.lingua_ufficiale
        target = p.new if official else None
        try:
            if p.unit_kind == "chapter":
                applying.apply_chapter_title(root, p.section, text)
                return
            key = (
                self._resolve(root, p.section, p.key, p.source_hash) if p.kind != "added" else None
            )
            after = (
                self._resolve(root, p.section, p.after_key, p.after_hash) if p.after_key else None
            )
            if p.kind == "modified":
                if key is None:
                    raise WorkspaceError(
                        "not_found", "the source changed since the export: the part is gone"
                    )
                needs_sync = applying.apply_modified(root, lang, p.section, key, text, target)
            elif p.kind == "added":
                if p.after_key and after is None:
                    raise WorkspaceError("not_found", "the source changed since the export")
                needs_sync = applying.apply_added(root, lang, p.section, after, text, target)
            else:
                if key is None:
                    raise WorkspaceError(
                        "not_found", "the source changed since the export: the part is gone"
                    )
                applying.apply_deleted(root, p.section, key)
                needs_sync = True
        except WorkspaceError as exc:
            p.status, p.note = "failed", exc.message
            raise
        # the section changed on disk: the translation catches up (nothing to do if it was seeded)
        content, _ = read_section(root, p.section)
        if needs_sync:
            self._translation.schedule_sync(root, project, p.section, content)

    @staticmethod
    def _resolve(root: Path, section: str, key: str | None, source_hash: str | None) -> str | None:
        """The segment's key now: the same key if it holds the exported text, else found by hash."""
        if key is None:
            return None
        segments = segment(read_section(root, section)[0]).by_key()
        here = segments.get(key)
        if here is not None and (source_hash is None or here.hash == source_hash):
            return key
        if source_hash is not None:
            matches = [k for k, s in segments.items() if s.hash == source_hash]
            if len(matches) == 1:
                return matches[0]
        return None
