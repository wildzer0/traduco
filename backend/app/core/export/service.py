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
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from app.core.export import bilingual, office, web
from app.core.export import combine as combine_mod
from app.core.export import compose as compose_mod
from app.core.export.errors import ExportError
from app.core.export.pandoc import default_reference_doc, find_pandoc, run_pandoc
from app.core.importer.snapshot import Part, build_units
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
Language = str  # "ufficiale", "sorgente" or the code of an additional language
Format = Literal["docx", "pdf", "odt", "html", "epub", "md"]
WEB_FORMATS = ("html", "epub", "md")
WAIT_SECONDS = 300.0
DATE_FORMATS = {"it": "%d/%m/%Y", "de": "%d.%m.%Y", "fr": "%d/%m/%Y", "es": "%d/%m/%Y"}


@dataclass(frozen=True)
class ExportRequest:
    scope: Scope = "project"
    path: str | None = None
    language: Language = "ufficiale"
    template: str | None = None
    format: Format = "docx"


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


_PATTERN_TOKENS = (("yyyy", "%Y"), ("yy", "%y"), ("MM", "%m"), ("dd", "%d"))


def date_pattern(pattern: str) -> str:
    """``dd.MM.yyyy`` (as written in progetto.yaml) -> a ``strftime`` format."""
    for token, code in _PATTERN_TOKENS:
        pattern = pattern.replace(token, code)
    return pattern


def format_value(value: Any, language: str, pattern: str | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        fmt = date_pattern(pattern) if pattern else DATE_FORMATS.get(language, "%Y-%m-%d")
        return value.strftime(fmt)
    return str(value)


def _pattern(project: Project) -> str | None:
    value = getattr(project, "formato_date", None)
    return str(value) if value else None


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
        if req.language not in (
            "ufficiale",
            "sorgente",
            "bilingue",
        ):  # an additional language (RF-21b)
            try:
                project = project.for_language(req.language)
            except ValueError as exc:
                raise ExportError(
                    "invalid_language", f"Language not configured: {req.language}"
                ) from exc
            req = replace(req, language="ufficiale")  # from here on it is "the target language"
        two_columns = req.language == "bilingue"  # source | translation (RF-64)
        official = req.language in ("ufficiale", "bilingue")
        lang = project.lingua_ufficiale if official else project.lingua_sorgente
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")  # also names the snapshot
        parts: list[Part] = []
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
                parts.append(Part("chapter", node.path, title))
                continue
            source_text = (root / node.path).read_text(encoding="utf-8")
            text = source_text
            view: dict[str, Any] = {}
            if official:
                view = self._translation.translation(root, project, node.path, text)
                text = view["markdown"]
            doc = frontmatter.parse(text)
            title = str(doc.meta.get("title") or node.title)
            body = doc.body
            if two_columns:
                body = bilingual.build_body(
                    source_text, bilingual.targets_of(view), project.lingua_sorgente, lang
                )
            items.append(combine_mod.Item("section", node.path, title, depth, body))
            parts.append(Part("section", node.path, title, text, source_text))

        self._step(job, 65, "fields", root)
        fields = await self._fields(client, project, lang, official, job)
        revisions = [
            compose_mod.Revision(
                r.rev,
                format_value(r.data, lang, _pattern(project)),
                await self._maybe(client, project, "descrizione", r.descrizione, official, job),
            )
            for r in project.revisioni
        ]

        self._step(job, 75, "document", root)
        combined = combine_mod.combine(root, items)
        job.warnings.extend(combined.warnings)
        if two_columns:
            job.warnings.append(
                "Two columns: code blocks, tables and diagrams are not in the bilingual document."
            )
        output = await asyncio.to_thread(
            self._render, root, project, req, combined, fields, revisions, lang, job, stamp
        )
        if req.format in WEB_FORMATS:
            return output  # nothing to import back from these: no snapshot, no conversion
        if not two_columns:  # a table of pairs is not something a reviewer sends back to import
            self._step(job, 95, "snapshot", root)
            self._snapshot(root, req, combined, output, build_units(parts), fields, lang, stamp)
        if req.format != "docx":
            self._step(job, 97, "convert", root)
            output = await asyncio.to_thread(office.convert, output, req.format, output.parent)
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
        stamp: str,
    ) -> Path:
        pandoc = find_pandoc(self._pandoc)
        name = self._choose_template(root, project, req, job)
        # (``stamp`` names the snapshot and goes into the document: the file name has its own)
        file_stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        base = f"{slugify(project.nome) or 'documento'}-{lang}-{file_stamp}"
        output = root / "build" / f"{base}.docx"
        with tempfile.TemporaryDirectory(prefix="traduco-export-") as tmp:
            work = Path(tmp)
            for asset, source in combined.assets.items():
                (work / asset).write_bytes(source.read_bytes())
            if req.format in WEB_FORMATS:
                return self._render_web(
                    pandoc, project, req, combined, work, output.with_name(base), lang
                )
            markdown = work / "document.md"
            markdown.write_text(combined.markdown, encoding="utf-8")
            body = work / "body.docx"
            if name is None:
                job.warnings.append("no template: Pandoc's default styles are used")
                reference = default_reference_doc(pandoc, work / "reference.docx")
                run_pandoc(pandoc, markdown, body, reference_doc=reference, resource_dir=work)
                result = compose_mod.finish_plain(
                    body, output, fields=fields, allow_missing=True, identifier=stamp
                )
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
                    identifier=stamp,
                )
        job.warnings.extend(result.warnings)
        return output

    @staticmethod
    def _render_web(
        pandoc: Path,
        project: Project,
        req: ExportRequest,
        combined: combine_mod.Combined,
        work: Path,
        target: Path,
        lang: str,
    ) -> Path:
        """HTML, EPUB and Markdown need no template, fields or revision table (RF-85)."""
        target.parent.mkdir(parents=True, exist_ok=True)
        if req.format == "md":
            return web.build_markdown(combined, work, target)
        output = target.with_suffix(f".{req.format}")
        build = web.build_html if req.format == "html" else web.build_epub
        build(pandoc, combined, work, output, project.nome, lang)
        return output

    @staticmethod
    def _choose_template(
        root: Path, project: Project, req: ExportRequest, job: ExportJob
    ) -> str | None:
        """The template to use; one asked for by name must exist, a missing default is not fatal.

        A project can name a default that is not there (made by an older version, file deleted by
        hand): the export then uses the only template present, or none, and says so.
        """
        folder = root / "template"
        available = sorted(p.stem for p in folder.glob("*.docx")) if folder.is_dir() else []
        if req.template:
            if req.template not in available:
                raise ExportError("template_missing", f'Template not found: "{req.template}".')
            return req.template
        wanted = project.template_predefinito
        if wanted and wanted in available:
            return wanted
        if wanted:
            job.warnings.append(
                f'The default template "{wanted}" is not in the project\'s template folder'
                + (f'; using "{available[0]}" instead.' if len(available) == 1 else ".")
            )
        return available[0] if len(available) == 1 else None

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
                count += sum(
                    1
                    for s in stored.segments
                    if s.status == "queued" and s.reason != "awaiting_pivot"
                )
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
            text = format_value(value, lang, _pattern(project))
            fields[key] = await self._maybe(client, project, key, text, official, job)
        fields["lingua"] = lang
        fields.setdefault("data_esportazione", format_value(date.today(), lang, _pattern(project)))
        return fields

    # -- snapshot ------------------------------------------------------------------------------
    def _snapshot(
        self,
        root: Path,
        req: ExportRequest,
        combined: combine_mod.Combined,
        output: Path,
        units: list[dict[str, Any]],
        fields: dict[str, str | None],
        lang: str,
        stamp: str,
    ) -> None:
        folder = root / ".traduco" / "export" / stamp
        atomic_write_text(folder / "combined.md", combined.markdown)
        atomic_write_text(
            folder / "map.json",
            json.dumps(
                {
                    "id": stamp,
                    "scope": req.scope,
                    "path": req.path,
                    "language": req.language,
                    "lang": lang,
                    "file": output.name,
                    "anchors": combined.anchors,
                    "fields": fields,
                    "units": units,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


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
