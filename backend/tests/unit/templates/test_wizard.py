from pathlib import Path

import pytest
from docx import Document
from docx.oxml.ns import qn

from app.core.export.pandoc import default_reference_doc
from app.core.templates.analyze import analyze, check_mapping, propose_mapping
from app.core.templates.wizard import WizardOptions, build_template
from app.core.workspace.errors import WorkspaceError
from tests.support.template_factory import logo_png


@pytest.fixture
def reference(pandoc_bin: Path, tmp_path: Path) -> Path:
    return default_reference_doc(pandoc_bin, tmp_path / "reference.docx")


def texts(doc) -> str:  # type: ignore[no-untyped-def]
    return "\n".join(t.text or "" for t in doc.element.body.iter(qn("w:t")))


def test_defaults_give_a_usable_template(reference: Path, tmp_path: Path) -> None:
    out = build_template(WizardOptions(), reference, tmp_path / "t.docx")
    analysis = analyze(out)
    assert analysis.has_content and analysis.has_toc and analysis.has_revisions
    assert {"nome", "codice_documento", "revisione", "data"} <= set(analysis.fields)
    mapping = propose_mapping(analysis)
    assert check_mapping(mapping, analysis) == []
    assert mapping.stili["titolo_1"] == "Heading1" and mapping.stili["tabella"] == "Table"
    assert mapping.stili["codice"] == "SourceCode" and mapping.stili["didascalia"] == "ImageCaption"


def test_the_look_choices_are_applied(reference: Path, tmp_path: Path) -> None:
    options = WizardOptions(
        font_body="Georgia",
        font_heading="Arial",
        size_body=12,
        color="#c00000",
        margin_cm=3,
        page="Letter",
    )
    doc = Document(str(build_template(options, reference, tmp_path / "t.docx")))
    assert doc.styles["Normal"].font.name == "Georgia" and doc.styles["Normal"].font.size.pt == 12
    h1 = doc.styles["Heading 1"]
    assert h1.font.name == "Arial" and str(h1.font.color.rgb) == "C00000"
    fonts = h1.element.rPr.find(qn("w:rFonts"))
    assert not [
        a for a in fonts.attrib if a.endswith("Theme")
    ]  # a theme font would win over the name in Word
    section = doc.sections[0]
    assert section.left_margin is not None and section.page_width is not None
    assert abs(section.left_margin.cm - 3) < 0.01 and abs(section.page_width.cm - 21.59) < 0.01


def test_cover_header_and_footer_follow_the_choices(reference: Path, tmp_path: Path) -> None:
    logo = logo_png(tmp_path / "logo.png").read_bytes()
    options = WizardOptions(
        cover_fields=["cliente", "autore"],
        header_text="{{codice_documento}} rev. {{revisione}}",
        footer_text="Riservato",
        language="en",
    )
    doc = Document(str(build_template(options, reference, tmp_path / "t.docx", logo)))
    body = texts(doc)
    assert "Client: {{cliente}}" in body and "Author: {{autore}}" in body and "Date:" not in body
    header = "".join(t.text or "" for t in doc.sections[0].header._element.iter(qn("w:t")))
    footer = doc.sections[0].footer._element.xml
    assert "{{codice_documento}} rev. {{revisione}}" in header
    assert "Riservato" in footer and "PAGE" in footer and "NUMPAGES" in footer and "Page " in footer
    assert doc.sections[0].different_first_page_header_footer  # no header on the cover
    assert len(doc.inline_shapes) == 1  # the logo on the cover (body shapes only)
    assert "<w:drawing" in doc.sections[0].header._element.xml  # and the one in the header


def test_without_cover_toc_and_revisions(reference: Path, tmp_path: Path) -> None:
    options = WizardOptions(cover=False, toc=False, revisions=False, page_numbers=False)
    out = build_template(options, reference, tmp_path / "t.docx")
    analysis = analyze(out)
    assert analysis.has_content and not analysis.has_toc and not analysis.has_revisions
    assert not Document(str(out)).sections[0].different_first_page_header_footer


def test_bad_choices_are_refused() -> None:
    for bad in (
        {"color": "red"},
        {"font_body": "Arial; DROP"},
        {"cover_fields": ["segreto"]},
        {"size_body": 3},
        {"inventato": 1},
    ):
        with pytest.raises(ValueError):
            WizardOptions(**bad)


def test_a_logo_must_be_a_small_png_or_jpeg(reference: Path, tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="PNG or JPEG"):
        build_template(WizardOptions(), reference, tmp_path / "t.docx", b"<svg onload='x'/>")
    with pytest.raises(WorkspaceError, match="2 MB"):
        build_template(
            WizardOptions(),
            reference,
            tmp_path / "t.docx",
            b"\x89PNG\r\n\x1a\n" + b"0" * (3 * 1024 * 1024),
        )


def test_the_exported_document_uses_the_wizard_template(
    reference: Path, pandoc_bin: Path, tmp_path: Path
) -> None:
    """End to end: wizard -> export pipeline (combine, Pandoc, compose) -> no marker left."""
    from tests.unit.export.test_pipeline import all_text, build  # noqa: F401

    project = tmp_path / "proj"
    (project / "capitoli/01-intro/img").mkdir(parents=True)
    logo_png(project / "capitoli/01-intro/img/schema.png", 300, 120)
    template = build_template(
        WizardOptions(cover_fields=["codice_documento", "revisione", "data", "autore", "cliente"]),
        reference,
        tmp_path / "w.docx",
        logo_png(tmp_path / "l.png").read_bytes(),
    )
    doc = Document(str(build(project, pandoc_bin, template, tmp_path)))
    text = all_text(doc)
    assert (
        "{{" not in text and "Manuale impianto" in text and "Codice documento: DOC-2026-014" in text
    )
    assert any(p.style is not None and p.style.style_id == "Heading1" for p in doc.paragraphs)
