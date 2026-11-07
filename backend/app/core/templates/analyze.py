"""Read a company ``.docx`` template: styles, ``{{fields}}`` and where the content goes (RF-51).

Word splits text into runs for no visible reason (spell checking, edits), so a field such as
``{{codice_documento}}`` may be spread over three runs: placeholders are searched in the joined
text of each paragraph. Headers, footers and text boxes are searched as well.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentObject
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn

from app.core.templates.mapping import CONTENT, ROLES, Mapping

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
RESERVED = {"CONTENUTO", "REVISIONI", "SOMMARIO"}
MAX_TEMPLATE_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class StyleInfo:
    id: str
    name: str
    kind: str  # paragraph | table | character | numbering
    custom: bool
    outline_level: int | None = None
    has_numbering: bool = False
    based_on: str | None = None


@dataclass(frozen=True)
class Found:
    name: str
    where: str  # body | header | footer | textbox
    count: int = 1


@dataclass
class Analysis:
    styles: list[StyleInfo]
    placeholders: list[Found]
    fields: list[str] = field(default_factory=list)  # {{campo}} names, without the reserved ones
    has_content: bool = False
    has_revisions: bool = False
    has_toc: bool = False
    content_where: str | None = None

    def style_ids(self, kind: str | None = None) -> set[str]:
        return {s.id for s in self.styles if kind is None or s.kind == kind}


def paragraph_text(p: Any) -> str:
    """Text of a ``w:p`` element: all its ``w:t``, in order, joined across runs."""
    return "".join(t.text or "" for t in p.iter(qn("w:t")))


def _where(p: Any, default: str) -> str:
    return "textbox" if any(a.tag == qn("w:txbxContent") for a in p.iterancestors()) else default


def _parts(doc: DocumentObject) -> list[tuple[str, Any]]:
    """(location, root element) for the body and every header / footer part."""
    parts: list[tuple[str, Any]] = [("body", doc.element.body)]
    for rel in doc.part.rels.values():
        if rel.reltype == RT.HEADER:
            parts.append(("header", rel.target_part.element))
        elif rel.reltype == RT.FOOTER:
            parts.append(("footer", rel.target_part.element))
    return parts


def _style_info(style: Any) -> StyleInfo:
    ppr = style.element.find(qn("w:pPr"))
    outline = None
    numbered = False
    if ppr is not None:
        level = ppr.find(qn("w:outlineLvl"))
        if level is not None:
            outline = int(level.get(qn("w:val")) or 0)
        numbered = ppr.find(qn("w:numPr")) is not None
    based = style.element.find(qn("w:basedOn"))
    kind = {1: "paragraph", 2: "character", 3: "table", 4: "numbering"}.get(
        int(style.type), "paragraph"
    )
    return StyleInfo(
        id=style.style_id,
        name=style.name,
        kind=kind,
        custom=bool(style.element.get(qn("w:customStyle"))),
        outline_level=outline,
        has_numbering=numbered,
        based_on=based.get(qn("w:val")) if based is not None else None,
    )


def analyze(path: Path) -> Analysis:
    doc = Document(str(path))
    styles = [_style_info(s) for s in doc.styles if s.style_id]
    counts: dict[tuple[str, str], int] = {}
    toc_field = False
    for where, root in _parts(doc):
        for p in root.iter(qn("w:p")):
            text = paragraph_text(p)
            for match in PLACEHOLDER.finditer(text):
                key = (match.group(1), _where(p, where))
                counts[key] = counts.get(key, 0) + 1
            if any("TOC" in (i.text or "") for i in p.iter(qn("w:instrText"))):
                toc_field = True
    found = [Found(name, where, n) for (name, where), n in sorted(counts.items())]
    names = {f.name for f in found}
    content = [f for f in found if f.name == "CONTENUTO"]
    return Analysis(
        styles=styles,
        placeholders=found,
        fields=sorted(names - RESERVED),
        has_content="CONTENUTO" in names,
        has_revisions="REVISIONI" in names,
        has_toc="SOMMARIO" in names or toc_field,
        content_where=content[0].where if content else None,
    )


# --- proposing a mapping -------------------------------------------------------------------------


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _score(style: StyleInfo, patterns: list[tuple[str, int]], *, level: int | None = None) -> int:
    ident, name = _norm(style.id), _norm(style.name)
    best = 0
    for pattern, weight in patterns:
        if re.search(pattern, name) or re.search(pattern, ident):
            best = max(best, weight)
    if best == 0:
        return 0
    if style.custom:
        best += 3  # a company-specific style is more likely what the documents use
    if level is not None and style.outline_level == level - 1:
        best += 2
    if level is not None and style.has_numbering:
        best += 1
    return best


def propose_mapping(analysis: Analysis) -> Mapping:
    """Best guess of the style for each role; roles with no candidate are left out."""
    paragraphs = [s for s in analysis.styles if s.kind == "paragraph"]
    tables = [s for s in analysis.styles if s.kind == "table"]
    chosen: dict[str, str] = {}

    def pick(
        role: str,
        candidates: list[StyleInfo],
        patterns: list[tuple[str, int]],
        level: int | None = None,
    ) -> None:
        scored = [(_score(s, patterns, level=level), s) for s in candidates]
        scored = [(n, s) for n, s in scored if n > 0]
        if scored:
            chosen[role] = max(scored, key=lambda item: item[0])[1].id

    for n in range(1, 7):
        pick(f"titolo_{n}", paragraphs, [(rf"(heading|titolo|intestazione){n}$", 10)], level=n)
    pick(
        "corpo",
        paragraphs,
        [(r"(corpo|bodytext|testocorpo)", 10), (r"^(normal|normale)$", 5), (r"^testo", 4)],
    )
    pick("didascalia", paragraphs, [(r"(didascalia|caption|legenda)", 10)])
    pick(
        "elenco_puntato", paragraphs, [(r"(elenco|list)(puntato|bullet)", 10), (r"^listbullet", 8)]
    )
    pick(
        "elenco_numerato",
        paragraphs,
        [(r"(elenco|list)(numerato|number)", 10), (r"^listnumber", 8)],
    )
    pick("citazione", paragraphs, [(r"(citazione|quote|blocktext)", 10)])
    pick("codice", paragraphs, [(r"(codice|sourcecode|code|preformat)", 10)])
    pick("tabella", [t for t in tables if _norm(t.id) not in ("tablenormal", "normaltable")],
         [(r"(tabella|table)", 6), (r"grid", 3)])  # fmt: skip
    return Mapping(contenuto=CONTENT, stili={r: chosen[r] for r in ROLES if r in chosen})


def check_mapping(mapping: Mapping, analysis: Analysis) -> list[str]:
    """Problems that would make an export fail or look wrong; empty when the mapping is usable."""
    problems: list[str] = []
    paragraph_ids = analysis.style_ids("paragraph")
    table_ids = analysis.style_ids("table")
    for role, style_id in mapping.stili.items():
        if role not in ROLES:
            problems.append(f"unknown role: {role}")
        elif role == "tabella" and style_id not in table_ids:
            problems.append(f"table style not found in the template: {style_id}")
        elif role != "tabella" and style_id not in paragraph_ids:
            problems.append(f"paragraph style not found in the template: {style_id}")
    if not analysis.has_content:
        problems.append("the template has no {{CONTENUTO}} placeholder")
    return problems
