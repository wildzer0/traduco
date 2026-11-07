"""Export jobs: collect the sections, make sure they are translated, build the DOCX (RF-60).

A job runs in the background; the client polls it for progress and downloads the file when done.
The text of every export is also kept in ``.traduco/export/<timestamp>/`` (combined Markdown and
the map of section anchors) so that a revised copy can be imported later (M5).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import tempfile
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from app.core.export import combine as combine_mod
from app.core.export import compose as compose_mod
from app.core.export.errors import ExportError
from app.core.export.pandoc import default_reference_doc, find_pandoc, run_pandoc
from app.core.templates.analyze import analyze, propose_mapping
from app.core.templates.mapping import Mapping, load_mapping, template_path
from app.core.translation import store
from app.core.translation.llm_client import LlmError
from app.core.translation.service import PRIORITY_EDIT, TranslationService
from app.core.translation.translator import Context, translate
from app.core.workspace import frontmatter
from app.core.workspace.fsio import atomic_write_text, sha256_text
from app.core.workspace.manifest import Project
from app.core.workspace.ordering import slugify
from app.core.workspace.tree import Node, build_tree

Scope = Literal["section", "chapter", "project"]
Language = Literal["ufficiale", "sorgente"]
WAIT_SECONDS = 300.0
DATE_FORMATS = {"it": "%d/%m/%Y", "de": "%d.%m.%Y", "fr": "%d/%m/%Y", "es": "%d/%m/%Y"}


@dataclass(frozen=True)
class ExportRequest:
    scope: Scope = "project"
    path: str | None = None
    language: Language = "ufficiale"
    template: str | None = None


@dataclass
class ExportJob:
    id: str
    state: str = "running"  # running | done | failed
    progress: int = 0
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
    file: Path | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "progress": self.progress,
            "message": self.message,
            "warnings": self.warnings,
            "error": self.error,
            "filename": self.file.name if self.file else None,
        }


def format_value(value: Any, language: str) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime(DATE_FORMATS.get(language, "%Y-%m-%d"))
    return str(value)


class ExportManager:
    def __init__(
        self,
        translation: TranslationService,
        *,
        pandoc: Path | None = None,
        publish: Callable[[Path, dict[str, Any]], None] | None = None,
    ) -> None:
        self._translation = translation
        self._pandoc = pandoc
        self._publish = publish
        self._jobs: dict[str, ExportJob] = {}
        self._tasks: set[asyncio.Task[None]] = set()

    def get(self, job_id: str) -> ExportJob | None:
        return self._jobs.get(job_id)

    def start(self, root: Path, project: Project, request: ExportRequest) -> ExportJob:
        job = ExportJob(uuid.uuid4().hex)
        self._jobs[job.id] = job
        if len(self._jobs) > 50:  # keep the most recent ones
            for old in list(self._jobs)[:-50]:
                del self._jobs[old]
        task = asyncio.create_task(self._run(job, root, project, request))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        for task in list(self._tasks):
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # -- the job ---------------------------------------------------------------------------
    def _step(self, job: ExportJob, progress: int, message: str, root: Path) -> None:
        job.progress, job.message = progress, message
        if self._publish:
            self._publish(root, {"type": "export.progress", "job": job.id, "progress": progress})

    async def _run(self, job: ExportJob, root: Path, project: Project, req: ExportRequest) -> None:
        try:
            job.file = await self._build(job, root, project, req)
            job.state, job.progress, job.message = "done", 100, ""
        except ExportError as exc:
            job.state, job.error = (
                "failed",
                {"code": exc.code, "message": exc.message, "details": exc.details},
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # a bug must not leave the job running forever
            job.state, job.error = (
                "failed",
                {"code": "export_failed", "message": f"{type(exc).__name__}: {exc}", "details": {}},
            )
        if self._publish:
            self._publish(
                root,
                {
                    "type": "export.progress",
                    "job": job.id,
                    "progress": job.progress,
                    "state": job.state,
                },
            )

    async def _build(
        self, job: ExportJob, root: Path, project: Project, req: ExportRequest
    ) -> Path:
        official = req.language == "ufficiale"
        lang = project.lingua_ufficiale if official else project.lingua_sorgente
        self._step(job, 3, "collect", root)
        nodes = _select(build_tree(root), req)
        sections = [n for n, _ in nodes if n.kind == "section"]
        if not sections:
            raise ExportError("nothing_to_export", "There is no section to export.")

        if official:
            await self._ensure_translated(job, root, project, sections)
        client = self._translation._client(*self._translation._config_for(project))

        self._step(job, 55, "titles", root)
        items: list[combine_mod.Item] = []
        for node, depth in nodes:
            if node.kind == "chapter":
                title = await self._chapter_title(client, root, project, node.title, official, job)
                items.append(combine_mod.Item("chapter", node.path, title, depth))
                continue
            text = (root / node.path).read_text(encoding="utf-8")
            if official:
                text = self._translation.translation(root, project, node.path, text)["markdown"]
            doc = frontmatter.parse(text)
            title = str(doc.meta.get("title") or node.title)
            items.append(combine_mod.Item("section", node.path, title, depth, doc.body))

        self._step(job, 65, "fields", root)
        fields = await self._fields(client, project, lang, official, job)
        revisions = [
            compose_mod.Revision(
                r.rev,
                format_value(r.data, lang),
                await self._maybe(client, project, "descrizione", r.descrizione, official, job),
            )
            for r in project.revisioni
        ]

        self._step(job, 75, "document", root)
        combined = combine_mod.combine(root, items)
        job.warnings.extend(combined.warnings)
        output = await asyncio.to_thread(
            self._render, root, project, req, combined, fields, revisions, lang, job
        )
        self._step(job, 95, "snapshot", root)
        self._snapshot(root, req, combined, output)
        return output

    def _render(
        self,
        root: Path,
        project: Project,
        req: ExportRequest,
        combined: combine_mod.Combined,
        fields: dict[str, str | None],
        revisions: list[compose_mod.Revision],
        lang: str,
        job: ExportJob,
    ) -> Path:
        pandoc = find_pandoc(self._pandoc)
        name = req.template or project.template_predefinito
        if name is None:
            available = (
                sorted(p.stem for p in (root / "template").glob("*.docx"))
                if (root / "template").is_dir()
                else []
            )
            name = available[0] if len(available) == 1 else None
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        output = root / "build" / f"{slugify(project.nome) or 'documento'}-{lang}-{stamp}.docx"
        with tempfile.TemporaryDirectory(prefix="traduco-export-") as tmp:
            work = Path(tmp)
            for asset, source in combined.assets.items():
                (work / asset).write_bytes(source.read_bytes())
            markdown = work / "document.md"
            markdown.write_text(combined.markdown, encoding="utf-8")
            body = work / "body.docx"
            if name is None:
                job.warnings.append("no template: Pandoc's default styles are used")
                reference = default_reference_doc(pandoc, work / "reference.docx")
                run_pandoc(pandoc, markdown, body, reference_doc=reference, resource_dir=work)
                result = compose_mod.finish_plain(body, output, fields=fields, allow_missing=True)
            else:
                template = template_path(root, name)
                if not template.is_file():
                    raise ExportError("template_missing", f"Template not found: {name}")
                mapping: Mapping = load_mapping(root, name) or propose_mapping(analyze(template))
                run_pandoc(pandoc, markdown, body, reference_doc=template, resource_dir=work)
                result = compose_mod.compose(
                    template,
                    body,
                    output,
                    mapping=mapping,
                    fields=fields,
                    revisions=revisions,
                    language=lang,
                )
        job.warnings.extend(result.warnings)
        return output

    # -- translation of what the segments do not cover ------------------------------------------
    async def _ensure_translated(
        self, job: ExportJob, root: Path, project: Project, sections: list[Node]
    ) -> None:
        for node in sections:
            text = (root / node.path).read_text(encoding="utf-8")
            stored = store.load(root, project.lingua_ufficiale, node.path)
            if stored is None or stored.source_file_hash != sha256_text(text):
                self._translation.sync(root, project, node.path, text, PRIORITY_EDIT)
        deadline = asyncio.get_running_loop().time() + WAIT_SECONDS
        while True:
            waiting = self._waiting(root, project, sections)
            self._step(
                job, 5 + int(45 * (1 - min(1.0, waiting / max(1, self._total)))), "translate", root
            )
            if waiting == 0:
                return
            if self._translation._online is False and self._translation.queue.pending() == 0:
                break
            if asyncio.get_running_loop().time() > deadline:
                break
            await asyncio.sleep(0.4)
        left = self._waiting(root, project, sections)
        if left:
            job.warnings.append(
                f"{left} segments are not translated yet: the source text is used for them"
            )

    _total = 1

    def _waiting(self, root: Path, project: Project, sections: list[Node]) -> int:
        count = 0
        for node in sections:
            stored = store.load(root, project.lingua_ufficiale, node.path)
            if stored is not None:
                count += sum(1 for s in stored.segments if s.status == "queued")
        self._total = max(self._total, count)
        return count

    async def _translate(self, client: Any, project: Project, text: str, job: ExportJob) -> str:
        if not text.strip():
            return text
        ctx = Context(project.lingua_sorgente, project.lingua_ufficiale, project.tono)
        try:
            outcome = await translate(client, text, ctx)
        except LlmError:
            job.warnings.append(
                "the model is unreachable: some titles and fields are not translated"
            )
            return text
        return outcome.target if outcome.ok or outcome.target else text

    async def _chapter_title(
        self, client: Any, root: Path, project: Project, title: str, official: bool, job: ExportJob
    ) -> str:
        if not official:
            return title
        cache_path = root / ".traduco" / "cache" / f"titles-{project.lingua_ufficiale}.json"
        try:
            cache: dict[str, str] = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
        key = sha256_text(title)
        if key not in cache:
            translated = await self._translate(client, project, title, job)
            if translated != title:
                cache[key] = translated
                atomic_write_text(
                    cache_path,
                    json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                )
            return translated
        return cache[key]

    async def _maybe(
        self, client: Any, project: Project, key: str, value: str, official: bool, job: ExportJob
    ) -> str:
        if official and key in project.metadati_da_tradurre:
            return await self._translate(client, project, value, job)
        return value

    async def _fields(
        self, client: Any, project: Project, lang: str, official: bool, job: ExportJob
    ) -> dict[str, str | None]:
        raw: dict[str, Any] = {"nome": project.nome, **project.metadati}
        fields: dict[str, str | None] = {}
        for key, value in raw.items():
            text = format_value(value, lang)
            fields[key] = await self._maybe(client, project, key, text, official, job)
        fields["lingua"] = lang
        fields.setdefault("data_esportazione", format_value(date.today(), lang))
        return fields

    # -- snapshot ------------------------------------------------------------------------------
    def _snapshot(
        self, root: Path, req: ExportRequest, combined: combine_mod.Combined, output: Path
    ) -> None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        folder = root / ".traduco" / "export" / stamp
        atomic_write_text(folder / "combined.md", combined.markdown)
        atomic_write_text(
            folder / "map.json",
            json.dumps(
                {
                    "scope": req.scope,
                    "path": req.path,
                    "language": req.language,
                    "file": output.name,
                    "anchors": combined.anchors,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )  # fmt: skip


def _select(tree: list[Node], req: ExportRequest) -> list[tuple[Node, int]]:
    """(node, depth) in reading order for the scope. Section depth = level of its chapter."""
    out: list[tuple[Node, int]] = []

    def walk(nodes: list[Node], depth: int) -> None:
        for node in nodes:
            if node.kind == "chapter":
                out.append((node, depth))
                walk(node.children, depth + 1)
            else:
                out.append((node, depth - 1))

    if req.scope == "project":
        walk(tree, 1)
        return out

    def find(nodes: list[Node]) -> Node | None:
        for node in nodes:
            if node.path == req.path:
                return node
            if (inner := find(node.children)) is not None:
                return inner
        return None

    target = find(tree)
    if target is None:
        raise ExportError("not_found", f"Nothing to export at {req.path}")
    if req.scope == "section":
        if target.kind != "section":
            raise ExportError("invalid_scope", "The path is not a section.")
        return [(target, 0)]
    if target.kind != "chapter":
        raise ExportError("invalid_scope", "The path is not a chapter.")
    out.append((target, 1))
    walk(target.children, 2)
    return out
