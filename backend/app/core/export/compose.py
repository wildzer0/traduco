"""Pour the Pandoc body into the company template and fill in its fields (ADR-004).

1. The paragraph holding ``{{CONTENUTO}}`` is replaced by the body (``docxcompose`` carries over
   styles, numbering, images and footnotes).
2. Pandoc's own styles are exchanged for the template's styles chosen in the mapping.
3. ``{{SOMMARIO}}`` becomes a table of contents field, ``{{REVISIONI}}`` the revisions table.
4. Every ``{{field}}`` in body, headers, footers and text boxes is replaced, even when Word split it
   over several runs; fields with no value stop the export unless the mapping allows them.
5. ``w:updateFields`` makes Word refresh numbers and the table of contents when the file is opened.
"""

from __future__ import annotations

from collections.abc import Iterator
from collections.abc import Mapping as MappingType
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docxcompose.composer import Composer

from app.core.export.errors import ExportError
from app.core.templates.analyze import PLACEHOLDER, RESERVED, paragraph_text
from app.core.templates.mapping import Mapping

W = nsdecls("w")
PANDOC_PARAGRAPH_ROLES = {
    "Heading1": "titolo_1", "Heading2": "titolo_2", "Heading3": "titolo_3",
    "Heading4": "titolo_4", "Heading5": "titolo_5", "Heading6": "titolo_6",
    "BodyText": "corpo", "FirstParagraph": "corpo", "BlockText": "citazione",
    "SourceCode": "codice", "ImageCaption": "didascalia",
}  # fmt: skip
CAPTION_LABEL = {"it": "Figura", "en": "Figure", "de": "Abbildung", "fr": "Figure", "es": "Figura"}
TOC_HINT = {
    "it": "Aggiorna il campo (tasto destro) per generare il sommario.",
    "en": "Update the field (right click) to build the table of contents.",
}
REVISION_HEAD = {
    "it": ("Rev.", "Data", "Descrizione"),
    "en": ("Rev.", "Date", "Description"),
}
# w:settings children that must come after w:updateFields (CT_Settings sequence)
_AFTER_UPDATE_FIELDS = (
    "hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
    "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
    "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown",
    "smartTagType", "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags", "decimalSymbol",
    "listSeparator",
)  # fmt: skip


@dataclass(frozen=True)
class Revision:
    rev: str
    date: str
    description: str


@dataclass
class ComposeResult:
    warnings: list[str] = field(default_factory=list)


# --- text replacement ------------------------------------------------------------------------


def _text_runs(p: Any) -> list[Any]:
    return [r for r in p.iter(qn("w:r")) if r.find(qn("w:t")) is not None]


def _run_text(run: Any) -> str:
    return "".join(t.text or "" for t in run.findall(qn("w:t")))


def _set_run_text(run: Any, text: str) -> None:
    first, *rest = run.findall(qn("w:t"))
    first.text = text
    first.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for extra in rest:
        run.remove(extra)


def replace_in_paragraph(p: Any, values: MappingType[str, str | None]) -> set[str]:
    """Replace ``{{name}}`` for the names in ``values``; returns the names it could not resolve.

    The text of the runs is joined, matches are found in the joined text and written back into the
    run where the match starts; the rest of the match is cut out of the following runs.
    """
    runs = _text_runs(p)
    texts = [_run_text(r) for r in runs]
    full = "".join(texts)
    if "{{" not in full:
        return set()
    starts = [0]
    for t in texts:
        starts.append(starts[-1] + len(t))
    unresolved: set[str] = set()
    for match in reversed(list(PLACEHOLDER.finditer(full))):
        name = match.group(1)
        if name not in values:
            unresolved.add(name)
            continue
        replacement = (values[name] or "").replace("\n", " ")
        begin, end = match.span()
        for i, run_text in enumerate(texts):
            lo, hi = starts[i], starts[i + 1]
            if hi <= begin or lo >= end:
                continue
            cut_from, cut_to = max(begin, lo) - lo, min(end, hi) - lo
            insert = replacement if lo <= begin < hi else ""
            texts[i] = run_text[:cut_from] + insert + run_text[cut_to:]
    for run, text in zip(runs, texts, strict=True):
        _set_run_text(run, text)
    return unresolved


def _all_paragraphs(doc: DocumentObject) -> Iterator[Any]:
    """Paragraphs of the body, the headers and footers, and of the text boxes inside them."""
    roots = [doc.element.body]
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    for rel in doc.part.rels.values():
        if rel.reltype in (RT.HEADER, RT.FOOTER):
            roots.append(rel.target_part.element)
    for root in roots:
        yield from root.iter(qn("w:p"))


# --- structure ---------------------------------------------------------------------------------


def _set_style(p: Any, style_id: str) -> None:
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        ppr = parse_xml(f"<w:pPr {W}/>")
        p.insert(0, ppr)
    style = ppr.find(qn("w:pStyle"))
    if style is None:
        style = parse_xml(f'<w:pStyle {W} w:val="{style_id}"/>')
        ppr.insert(0, style)
    style.set(qn("w:val"), style_id)


def _style_has_numbering(doc: DocumentObject, style_id: str) -> bool:
    style = doc.styles.element.find(f"{qn('w:style')}[@{qn('w:styleId')}='{style_id}']")
    return style is not None and style.find(f"{qn('w:pPr')}/{qn('w:numPr')}") is not None


def _list_kinds(body_doc: DocumentObject) -> dict[str, str]:
    """numId -> "bullet" | "ordered" from the numbering definitions Pandoc wrote."""
    try:
        numbering = body_doc.part.numbering_part.element
    except (KeyError, NotImplementedError):
        return {}
    formats: dict[str, str] = {}
    for abstract in numbering.findall(qn("w:abstractNum")):
        level = abstract.find(qn("w:lvl"))
        fmt = level.find(qn("w:numFmt")) if level is not None else None
        formats[str(abstract.get(qn("w:abstractNumId")))] = (
            "bullet" if fmt is not None and fmt.get(qn("w:val")) == "bullet" else "ordered"
        )
    kinds: dict[str, str] = {}
    for num in numbering.findall(qn("w:num")):
        ref = num.find(qn("w:abstractNumId"))
        if ref is not None:
            kinds[str(num.get(qn("w:numId")))] = formats.get(ref.get(qn("w:val")), "ordered")
    return kinds


def apply_styles(body_doc: DocumentObject, template: DocumentObject, mapping: Mapping) -> list[str]:
    """Swap Pandoc's styles for the template's, according to ``mapping``. Returns warnings."""
    warnings: list[str] = []
    styles = mapping.stili
    kinds = _list_kinds(body_doc)
    unmapped: set[str] = set()
    for p in body_doc.element.body.iter(qn("w:p")):
        ppr = p.find(qn("w:pPr"))
        style = ppr.find(qn("w:pStyle")) if ppr is not None else None
        current = style.get(qn("w:val")) if style is not None else None
        num = ppr.find(qn("w:numPr")) if ppr is not None else None
        in_table = any(a.tag == qn("w:tc") for a in p.iterancestors())
        if num is not None and not in_table:
            num_id = num.find(qn("w:numId"))
            role = (
                "elenco_puntato"
                if kinds.get(num_id.get(qn("w:val")) if num_id is not None else "") == "bullet"
                else "elenco_numerato"
            )
            target = styles.get(role)
            if target:
                _set_style(p, target)
            else:
                unmapped.add(role)
            continue
        mapped_role = PANDOC_PARAGRAPH_ROLES.get(current or "")
        if mapped_role is None or in_table:
            continue
        role = mapped_role
        target = styles.get(role)
        if target:
            _set_style(p, target)
        else:
            unmapped.add(role)
    table_style = styles.get("tabella")
    for tbl in body_doc.element.body.iter(qn("w:tbl")):
        style = tbl.find(f"{qn('w:tblPr')}/{qn('w:tblStyle')}")
        if style is not None and table_style:
            style.set(qn("w:val"), table_style)
        elif style is not None:
            unmapped.add("tabella")
    for role in sorted(unmapped):
        warnings.append(f"no style mapped for {role}: Pandoc's default is used")
    return warnings


def use_style_numbering(doc: DocumentObject, mapping: Mapping) -> None:
    """List paragraphs of a style that defines its own numbering lose Pandoc's direct numbering.

    Done after the body is inside the template: ``docxcompose`` needs the direct numbering while
    it merges the two documents.
    """
    own = {
        style_id
        for role in ("elenco_puntato", "elenco_numerato")
        if (style_id := mapping.stili.get(role)) and _style_has_numbering(doc, style_id)
    }
    for p in doc.element.body.iter(qn("w:p")):
        style = p.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
        num = p.find(f"{qn('w:pPr')}/{qn('w:numPr')}")
        if style is None or num is None or style.get(qn("w:val")) not in own:
            continue
        num_id = num.find(qn("w:numId"))
        if num_id is not None:
            num.remove(num_id)
        level = num.find(qn("w:ilvl"))
        if level is None or level.get(qn("w:val")) == "0":
            num.getparent().remove(num)


def number_figures(body_doc: DocumentObject, language: str) -> None:
    """Prefix figure captions with "Figure <SEQ>" so Word keeps them numbered (RF-62)."""
    label = CAPTION_LABEL.get(language, "Figure")
    for p in body_doc.element.body.iter(qn("w:p")):
        style = p.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
        if style is None or style.get(qn("w:val")) != "ImageCaption":
            continue
        number = sum(1 for _ in p.itersiblings(preceding=True) if _is_caption(_)) + 1
        runs = _field_runs(f"SEQ {label} \\* ARABIC", str(number))
        prefix = [parse_xml(f'<w:r {W}><w:t xml:space="preserve">{label} </w:t></w:r>'), *runs,
                  parse_xml(f'<w:r {W}><w:t xml:space="preserve"> – </w:t></w:r>')]  # fmt: skip
        anchor = p.find(qn("w:pPr"))
        index = list(p).index(anchor) + 1 if anchor is not None else 0
        for offset, run in enumerate(prefix):
            p.insert(index + offset, run)


def _is_caption(p: Any) -> bool:
    style = p.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    return style is not None and style.get(qn("w:val")) == "ImageCaption"


def _field_runs(instruction: str, cached: str) -> list[Any]:
    return [
        parse_xml(f'<w:r {W}><w:fldChar w:fldCharType="begin"/></w:r>'),
        parse_xml(
            f'<w:r {W}><w:instrText xml:space="preserve"> {instruction} </w:instrText></w:r>'
        ),
        parse_xml(f'<w:r {W}><w:fldChar w:fldCharType="separate"/></w:r>'),
        parse_xml(f'<w:r {W}><w:t xml:space="preserve">{cached}</w:t></w:r>'),
        parse_xml(f'<w:r {W}><w:fldChar w:fldCharType="end"/></w:r>'),
    ]


# --- markers -----------------------------------------------------------------------------------


def _marker_paragraph(doc: DocumentObject, name: str) -> Any | None:
    token = "{{" + name + "}}"
    for p in doc.element.body.iter(qn("w:p")):
        if token.replace(" ", "") in paragraph_text(p).replace(" ", ""):
            return p
    return None


def _clear(p: Any) -> None:
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)


def _build_toc(p: Any, language: str) -> None:
    _clear(p)
    runs = _field_runs('TOC \\o "1-3" \\h \\z \\u', TOC_HINT.get(language, TOC_HINT["en"]))
    for run in runs:
        p.append(run)


def _build_revisions(
    doc: DocumentObject, p: Any, revisions: list[Revision], style: str | None, language: str
) -> None:
    head = REVISION_HEAD.get(language, REVISION_HEAD["en"])
    table = doc.add_table(rows=1 + len(revisions), cols=3)
    if style:
        tbl_pr = table._tbl.tblPr
        existing = tbl_pr.find(qn("w:tblStyle"))
        if existing is None:
            existing = parse_xml(f'<w:tblStyle {W} w:val="{style}"/>')
            tbl_pr.insert(0, existing)
        existing.set(qn("w:val"), style)
    for i, text in enumerate(head):
        table.cell(0, i).text = text
    for row, rev in enumerate(revisions, 1):
        for i, text in enumerate((rev.rev, rev.date, rev.description)):
            table.cell(row, i).text = text
    p.addprevious(table._tbl)
    p.getparent().remove(p)


def _enable_update_fields(doc: DocumentObject) -> None:
    settings = doc.settings.element
    if settings.find(qn("w:updateFields")) is not None:
        return
    element = parse_xml(f'<w:updateFields {W} w:val="true"/>')
    for child in settings:
        if child.tag.split("}")[1] in _AFTER_UPDATE_FIELDS:
            child.addprevious(element)
            return
    settings.append(element)


# --- entry point -------------------------------------------------------------------------------


def compose(
    template: Path,
    body: Path,
    output: Path,
    *,
    mapping: Mapping,
    fields: MappingType[str, str | None],
    revisions: list[Revision],
    language: str,
) -> ComposeResult:
    """Write ``output``: the template with the body at ``{{CONTENUTO}}`` and every field filled."""
    result = ComposeResult()
    master = Document(str(template))
    body_doc = Document(str(body))

    marker = _marker_paragraph(master, "CONTENUTO")
    if marker is None:
        raise ExportError("template_invalid", "The template has no {{CONTENUTO}} placeholder.")
    if marker.getparent() is not master.element.body:
        raise ExportError(
            "template_invalid",
            "{{CONTENUTO}} must be in a normal paragraph, not in a table or a text box.",
        )

    number_figures(body_doc, language)  # before the styles change: it looks for Pandoc's caption
    result.warnings.extend(apply_styles(body_doc, master, mapping))

    index = list(master.element.body).index(marker)
    master.element.body.remove(marker)
    Composer(master).insert(index, body_doc)
    use_style_numbering(master, mapping)

    if (toc := _marker_paragraph(master, "SOMMARIO")) is not None:
        _build_toc(toc, language)
    if (rev := _marker_paragraph(master, "REVISIONI")) is not None:
        _build_revisions(master, rev, revisions, mapping.stili.get("tabella"), language)

    values: dict[str, str | None] = {k: v for k, v in fields.items() if k not in RESERVED}
    missing: set[str] = set()
    for p in _all_paragraphs(master):
        missing |= replace_in_paragraph(p, values)
    if missing:
        if not mapping.campi_mancanti_ammessi:
            raise ExportError(
                "missing_fields",
                "The template or the text uses fields that have no value: "
                + ", ".join(sorted(missing)),
                {"fields": sorted(missing)},
            )
        result.warnings.append("fields left empty: " + ", ".join(sorted(missing)))
        blank = dict.fromkeys(missing, "")
        for p in _all_paragraphs(master):
            replace_in_paragraph(p, blank)

    _enable_update_fields(master)
    output.parent.mkdir(parents=True, exist_ok=True)
    master.save(str(output))
    return result


def finish_plain(
    body: Path,
    output: Path,
    *,
    fields: MappingType[str, str | None],
    allow_missing: bool,
) -> ComposeResult:
    """Export without a template: Pandoc's document with the text's ``{{fields}}`` filled."""
    result = ComposeResult()
    doc = Document(str(body))
    values = {k: v for k, v in fields.items() if k not in RESERVED}
    missing: set[str] = set()
    for p in _all_paragraphs(doc):
        missing |= replace_in_paragraph(p, values)
    if missing:
        if not allow_missing:
            raise ExportError(
                "missing_fields",
                "The text uses fields that have no value: " + ", ".join(sorted(missing)),
                {"fields": sorted(missing)},
            )
        result.warnings.append("fields left empty: " + ", ".join(sorted(missing)))
        for p in _all_paragraphs(doc):
            replace_in_paragraph(p, dict.fromkeys(missing, ""))
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output))
    return result
