"""Other kinds of company templates, to check the export does not depend on one lucky layout."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm

W = nsdecls("w")


def plain_word(path: Path) -> Path:
    """What a person gets from "New document" in Word: built-in styles only, nothing custom."""
    doc = Document()
    doc.add_heading("{{nome}}", 0)
    doc.add_paragraph("Codice: {{codice_documento}} — Revisione {{revisione}}")
    doc.add_paragraph("{{SOMMARIO}}")
    doc.add_paragraph("{{CONTENUTO}}")
    doc.save(str(path))
    return path


def table_cover_and_sections(path: Path) -> Path:
    """Cover laid out in a table, revisions inside a table cell, a landscape section after the content."""
    doc = Document()
    cover = doc.add_table(rows=3, cols=2)
    cover.style = "Table Grid"
    cover.cell(0, 0).text = "Documento"
    cover.cell(0, 1).text = "{{nome}}"
    cover.cell(1, 0).text = "Codice"
    cover.cell(1, 1).text = "{{codice_documento}} rev. {{revisione}}"
    cover.cell(2, 0).text = "Revisioni"
    cover.cell(2, 1).text = "{{REVISIONI}}"
    doc.add_section(WD_SECTION.NEW_PAGE)
    doc.add_paragraph("{{CONTENUTO}}")
    landscape = doc.add_section(WD_SECTION.NEW_PAGE)
    landscape.orientation = WD_ORIENT.LANDSCAPE
    landscape.page_width, landscape.page_height = Cm(29.7), Cm(21)
    doc.add_paragraph("Allegato A — {{cliente}}")
    doc.sections[1].header.paragraphs[0].text = "{{codice_documento}} (corpo)"
    doc.save(str(path))
    return path


def content_controls_and_split_markers(path: Path) -> Path:
    """A content control holding a field, and a content marker Word broke into pieces."""
    doc = Document()
    doc.element.body.insert(
        0,
        parse_xml(
            f'<w:sdt {W}><w:sdtPr><w:alias w:val="Titolo"/></w:sdtPr><w:sdtContent>'
            "<w:p><w:r><w:t>{{no</w:t></w:r><w:r><w:t>me}}</w:t></w:r></w:p></w:sdtContent></w:sdt>"
        ),
    )
    paragraph = doc.add_paragraph()
    for piece in ("{{ ", "CONTE", "NUTO", " }}"):
        paragraph.add_run(piece)
    doc.save(str(path))
    return path


def content_in_a_table(path: Path) -> Path:
    doc = Document()
    table = doc.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "{{CONTENUTO}}"
    doc.save(str(path))
    return path


def without_content_marker(path: Path) -> Path:
    doc = Document()
    doc.add_paragraph("{{nome}}")
    doc.save(str(path))
    return path
