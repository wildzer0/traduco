"""The export against templates that are built very differently from the main fixture."""

from collections.abc import Callable
from pathlib import Path

import pytest
from docx import Document
from docx.oxml.ns import qn

from app.core.export.errors import ExportError
from app.core.templates.analyze import analyze, check_mapping, propose_mapping
from tests.support import template_variants as variants
from tests.unit.export.test_pipeline import all_text, build


def make(factory: Callable[[Path], Path], tmp: Path) -> Path:
    return factory(tmp / f"{factory.__name__}.docx")


def test_a_plain_word_document_works_as_a_template(
    project: Path, pandoc_bin: Path, tmp_path: Path
) -> None:
    template = make(variants.plain_word, tmp_path)
    doc = Document(str(build(project, pandoc_bin, template, tmp_path)))
    text = all_text(doc)
    assert (
        "{{" not in text
        and "Manuale impianto" in text
        and "Codice: DOC-2026-014 — Revisione 02" in text
    )
    styles = {p.style.style_id for p in doc.paragraphs if p.style is not None}
    assert {
        "Heading1",
        "Heading2",
    } <= styles  # the built-in heading styles were mapped to themselves
    assert any(p.text == "Scopo del documento" for p in doc.paragraphs)


def test_cover_in_a_table_revisions_in_a_cell_and_several_sections(
    project: Path,
    pandoc_bin: Path,
    tmp_path: Path,
) -> None:
    template = make(variants.table_cover_and_sections, tmp_path)
    out = build(project, pandoc_bin, template, tmp_path)
    doc = Document(str(out))
    text = all_text(doc)
    assert "{{" not in text
    cover = doc.tables[0]
    assert (
        cover.cell(0, 1).text == "Manuale impianto"
        and cover.cell(1, 1).text == "DOC-2026-014 rev. 02"
    )
    nested = cover.cell(2, 1).tables[0]  # the revisions table, inside the cover cell
    assert nested.cell(1, 2).text == "Prima emissione"
    assert cover.cell(2, 1)._tc[-1].tag == qn("w:p")  # a cell must end with a paragraph
    assert "Allegato A — ACME Ltd" in text
    assert len(doc.sections) == 3 and (doc.sections[2].page_width or 0) > (
        doc.sections[2].page_height or 0
    )  # landscape kept
    # the body sits between the cover and the annex
    order = [p.text for p in doc.paragraphs]
    assert order.index("Scopo del documento") < order.index("Allegato A — ACME Ltd")


def test_content_controls_and_a_marker_broken_into_pieces(
    project: Path, pandoc_bin: Path, tmp_path: Path
) -> None:
    template = make(variants.content_controls_and_split_markers, tmp_path)
    assert analyze(template).has_content  # "{{ CONTE" "NUTO }}" is found by the analysis too
    doc = Document(str(build(project, pandoc_bin, template, tmp_path)))
    text = "".join(t.text or "" for t in doc.element.body.iter(qn("w:t")))
    assert "Manuale impianto" in text  # the field inside the content control
    assert "Scopo del documento" in text and "CONTE" not in text


def test_a_content_marker_inside_a_table_is_refused_with_a_clear_message(
    project: Path,
    pandoc_bin: Path,
    tmp_path: Path,
) -> None:
    template = make(variants.content_in_a_table, tmp_path)
    with pytest.raises(ExportError) as info:
        build(project, pandoc_bin, template, tmp_path)
    assert info.value.code == "template_invalid" and "normal paragraph" in info.value.message


def test_a_template_without_the_content_marker_is_reported_at_upload_time(tmp_path: Path) -> None:
    template = make(variants.without_content_marker, tmp_path)
    analysis = analyze(template)
    assert not analysis.has_content
    assert "the template has no {{CONTENUTO}} placeholder" in check_mapping(
        propose_mapping(analysis), analysis
    )
