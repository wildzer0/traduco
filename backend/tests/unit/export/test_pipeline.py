"""Combine, Pandoc and compose on a realistic company template (M4 acceptance)."""

from collections.abc import Mapping as MappingType
from pathlib import Path

import pytest
from docx import Document
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn

from app.core.export.combine import Item, combine
from app.core.export.compose import Revision, compose
from app.core.export.errors import ExportError
from app.core.export.pandoc import find_pandoc, run_pandoc
from app.core.templates.analyze import analyze, propose_mapping
from app.core.templates.mapping import Mapping
from tests.support.template_factory import logo_png

BODY_A = """# Scopo del documento

Questo documento descrive la **pompa** _ACME Pump_ con codice {{codice_documento}}.[^1]

![Schema generale](img/schema.png)

- primo punto
- secondo punto

1. passo uno
2. passo due

> Attenzione alla pressione.

[^1]: Una nota a piè di pagina.
"""
BODY_B = """## Requisiti

| Parametro | Valore |
| --- | --- |
| Portata | 10 l/s |

```python
print("ciao")
```

Vedi [lo scopo](../01-intro/01-scopo.md) e [il sito](https://example.com).
"""


def items() -> list[Item]:
    return [
        Item("chapter", "capitoli/01-intro", "Introduzione", 1),
        Item("section", "capitoli/01-intro/01-scopo.md", "Scopo del documento", 1, BODY_A),
        Item("chapter", "capitoli/02-inst", "Installazione", 1),
        Item("section", "capitoli/02-inst/01-req.md", "Requisiti", 1, BODY_B),
    ]


FIELDS = {
    "nome": "Manuale impianto",
    "codice_documento": "DOC-2026-014",
    "revisione": "02",
    "data": "07/11/2026",
    "autore": "Mario Rossi",
    "cliente": "ACME Ltd",
}
REVISIONS = [
    Revision("01", "15/09/2026", "Prima emissione"),
    Revision("02", "07/11/2026", "Aggiornato capitolo 2"),
]


def build(
    project: Path,
    pandoc: Path,
    template: Path,
    tmp: Path,
    fields: MappingType[str, str | None] | None = None,
    mapping: Mapping | None = None,
) -> Path:
    combined = combine(project, items())
    work = tmp / "work"
    work.mkdir(exist_ok=True)
    for name, source in combined.assets.items():
        (work / name).write_bytes(source.read_bytes())
    (work / "doc.md").write_text(combined.markdown, encoding="utf-8")
    body = work / "body.docx"
    run_pandoc(pandoc, work / "doc.md", body, reference_doc=template, resource_dir=work)
    out = tmp / "out.docx"
    compose(
        template,
        body,
        out,
        mapping=mapping or propose_mapping(analyze(template)),
        fields=FIELDS if fields is None else fields,
        revisions=REVISIONS,
        language="it",
    )
    return out


def all_text(doc: DocumentObject) -> str:
    texts = ["".join(t.text or "" for t in doc.element.body.iter(qn("w:t")))]
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    for rel in doc.part.rels.values():
        if rel.reltype in (RT.HEADER, RT.FOOTER):
            texts.append("".join(t.text or "" for t in rel.target_part.element.iter(qn("w:t"))))
    return "\n".join(texts)


def style_of(doc: DocumentObject, text: str) -> str | None:
    """Style of the last paragraph with this text (the table of contents lists headings first)."""
    found = None
    for p in doc.paragraphs:
        if p.text.strip().endswith(text) or p.text.strip() == text:
            found = p.style.style_id if p.style is not None else None
    return found


def test_no_placeholder_is_left(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    doc = Document(str(build(project, pandoc_bin, company_template, tmp_path)))
    assert "{{" not in all_text(doc) and "}}" not in all_text(doc)


def test_cover_header_and_fields_come_from_the_template_and_the_metadata(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    doc = Document(str(build(project, pandoc_bin, company_template, tmp_path)))
    text = all_text(doc)
    assert "Manuale impianto" in text and "Codice documento: DOC-2026-014" in text
    assert "Doc. DOC-2026-014 – rev. 02" in text  # the header field was split over three runs
    assert "Cliente: ACME Ltd" in text  # inside a text box
    assert "Pagina" in text  # footer kept
    # the logo of the cover survives, and so does the picture of the body
    assert len(doc.inline_shapes) >= 2


def test_headings_use_the_mapped_styles_in_reading_order(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    doc = Document(str(build(project, pandoc_bin, company_template, tmp_path)))
    assert style_of(doc, "Introduzione") == "AziendaTitolo1"
    assert style_of(doc, "Scopo del documento") == "AziendaTitolo2"
    assert style_of(doc, "Installazione") == "AziendaTitolo1"
    assert style_of(doc, "Requisiti") == "AziendaTitolo2"
    headings = [
        p.text
        for p in doc.paragraphs
        if p.style is not None and p.style.style_id.startswith("AziendaTitolo")
    ]
    assert headings == ["Introduzione", "Scopo del documento", "Installazione", "Requisiti"]


def test_body_paragraphs_quotes_code_and_lists_use_the_template_styles(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    doc = Document(str(build(project, pandoc_bin, company_template, tmp_path)))
    assert style_of(doc, "Attenzione alla pressione.") == "AziendaCitazione"
    assert style_of(doc, 'print("ciao")') == "AziendaCodice"
    assert style_of(doc, "primo punto") == "AziendaElencoPuntato"
    assert style_of(doc, "passo due") == "AziendaElencoNumerato"
    body = next(p for p in doc.paragraphs if p.text.startswith("Questo documento descrive"))
    assert body.style is not None and body.style.style_id == "AziendaCorpo"
    # the list styles bring their own numbering: no direct numbering on the paragraph
    bullet = next(p for p in doc.paragraphs if p.text == "primo punto")
    assert bullet._p.find(f"{qn('w:pPr')}/{qn('w:numPr')}/{qn('w:numId')}") is None


def test_tables_use_the_mapped_table_style(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    doc = Document(str(build(project, pandoc_bin, company_template, tmp_path)))
    styled = [t for t in doc.tables if t.style is not None and t.style.style_id == "AziendaTabella"]
    assert len(styled) == 2  # the data table and the revisions table
    data = next(t for t in styled if t.cell(0, 0).text == "Parametro")
    assert data.cell(1, 1).text == "10 l/s"


def test_figures_have_a_numbered_caption(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    doc = Document(str(build(project, pandoc_bin, company_template, tmp_path)))
    caption = next(p for p in doc.paragraphs if "Schema generale" in p.text)
    assert caption.text.startswith("Figura 1 – ")
    assert caption.style is not None and caption.style.style_id == "AziendaDidascalia"
    assert "SEQ Figura" in caption._p.xml


def test_footnotes_toc_revisions_and_update_fields(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    out = build(project, pandoc_bin, company_template, tmp_path)
    doc = Document(str(out))
    assert "TOC" in doc.element.xml and "\\o" in doc.element.xml
    # the field already lists the headings: readable before Word updates it
    assert [p.text for p in doc.paragraphs].count("Scopo del documento") == 2
    revisions = next(t for t in doc.tables if t.cell(0, 0).text == "Rev.")
    assert [c.text for c in revisions.rows[2].cells] == [
        "02",
        "07/11/2026",
        "Aggiornato capitolo 2",
    ]
    assert doc.settings.element.find(qn("w:updateFields")) is not None
    import zipfile

    with zipfile.ZipFile(out) as z:
        footnotes = z.read("word/footnotes.xml").decode()
    assert "Una nota a piè di pagina." in footnotes


def test_links_to_sections_become_internal_anchors(project: Path) -> None:
    combined = combine(project, items())
    assert "](#sec-2)" in combined.markdown  # ../01-intro/01-scopo.md -> section 2
    assert "https://example.com" in combined.markdown
    assert "{#ch-1}" in combined.markdown and "{#sec-4}" in combined.markdown
    assert "[^s2-1]" in combined.markdown  # footnote labels are unique per section
    assert combined.markdown.count("# Scopo del documento") == 1  # the repeated H1 was dropped


def test_missing_fields_stop_the_export_unless_allowed(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    partial = {k: v for k, v in FIELDS.items() if k != "cliente"}
    with pytest.raises(ExportError) as info:
        build(project, pandoc_bin, company_template, tmp_path, fields=partial)
    assert info.value.code == "missing_fields" and info.value.details["fields"] == ["cliente"]
    lenient = propose_mapping(analyze(company_template)).model_copy(
        update={"campi_mancanti_ammessi": True}
    )
    doc = Document(
        str(build(project, pandoc_bin, company_template, tmp_path, fields=partial, mapping=lenient))
    )
    assert "Cliente: " in all_text(doc) and "{{" not in all_text(doc)


def test_a_missing_diagram_blocks_the_export_with_the_section(project: Path) -> None:
    item = Item(
        "section",
        "capitoli/01-intro/01-scopo.md",
        "Scopo",
        1,
        "```mermaid\nflowchart LR\n  A --> B\n```\n",
    )
    with pytest.raises(ExportError) as info:
        combine(project, [Item("chapter", "capitoli/01-intro", "I", 1), item])
    assert info.value.code == "diagram_missing"
    assert info.value.details["diagrams"][0]["section"] == "capitoli/01-intro/01-scopo.md"


def test_a_rendered_diagram_is_included_as_an_image(
    project: Path, pandoc_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    from app.core.workspace.diagrams import CACHE_DIR, diagram_hash

    code = "flowchart LR\n  A --> B\n"
    cache = project / CACHE_DIR
    cache.mkdir(parents=True)
    logo_png(cache / f"{diagram_hash(code)}.png", 200, 100)
    combined = combine(
        project,
        [
            Item("chapter", "capitoli/01-intro", "I", 1),
            Item("section", "capitoli/01-intro/01-s.md", "S", 1, f"```mermaid\n{code}```\n"),
        ],
    )
    assert "![](diagram-1.png)" in combined.markdown and "mermaid" not in combined.markdown
    assert "diagram-1.png" in combined.assets


def test_remote_images_and_files_outside_the_project_are_left_out(project: Path) -> None:
    body = "![a](https://example.com/x.png)\n\n![b](../../../../etc/passwd.png)\n\n![c](img/nope.png)\n"
    combined = combine(
        project,
        [
            Item("chapter", "capitoli/01-intro", "I", 1),
            Item("section", "capitoli/01-intro/01-s.md", "S", 1, body),
        ],
    )
    assert combined.assets == {}
    assert len(combined.warnings) == 3
    assert "https://example.com/x.png" not in combined.markdown.replace(
        "(https://example.com/x.png)", ""
    )


def test_the_file_opens_in_libreoffice_and_converts_to_pdf(
    project: Path, pandoc_bin: Path, soffice_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    from app.core.export.office import convert

    docx = build(project, pandoc_bin, company_template, tmp_path)
    pdf = convert(docx, "pdf", tmp_path / "pdf")
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 5_000


def test_pdf_and_odt_have_a_real_table_of_contents(
    project: Path, pandoc_bin: Path, soffice_bin: Path, company_template: Path, tmp_path: Path
) -> None:
    """Plain conversion keeps Word's hint text in the TOC; the macro fills it in (M5)."""
    import re
    import zipfile

    from app.core.export.office import convert

    docx = build(project, pandoc_bin, company_template, tmp_path)
    odt = convert(docx, "odt", tmp_path / "odt")
    with zipfile.ZipFile(odt) as z:
        content = z.read("content.xml").decode()
    toc = re.search(r"<text:table-of-content .*?</text:table-of-content>", content, re.DOTALL)
    assert toc, "the table of contents field was not imported as an index"
    body = re.sub(r"<[^>]+>", " ", toc.group(0))
    from app.core.export import office

    diagnostics = "\n".join(office.DIAGNOSTICS)
    assert "Update the field" not in body and "Aggiorna il campo" not in body, diagnostics
    for title in ("Introduzione", "Scopo del documento", "Installazione", "Requisiti"):
        assert re.search(rf"{title}\s+\d+", body), (
            f"{title} is not listed with a page number: {body[:300]}"
        )
    pdf = convert(docx, "pdf", tmp_path / "pdf")
    assert pdf.read_bytes().startswith(b"%PDF")


def test_a_table_right_after_a_paragraph_is_still_a_table(project: Path, tmp_path: Path) -> None:
    body = "Testo\n| A | B |\n|---|---|\n| 1 | 2 |\n\nFine\n"
    combined = combine(project, [Item("section", "capitoli/01-intro/01-a.md", "T", 1, body)])
    md = tmp_path / "t.md"
    md.write_text(combined.markdown, encoding="utf-8")
    out = tmp_path / "t.docx"
    run_pandoc(find_pandoc(), md, out, reference_doc=None, resource_dir=tmp_path)
    tables = Document(str(out)).tables
    assert len(tables) == 1
    assert [c.text for c in tables[0].rows[1].cells] == ["1", "2"]


def test_a_csv_attachment_becomes_a_table_and_other_attachments_a_plain_mention(
    project: Path, tmp_path: Path
) -> None:
    (project / "allegati").mkdir()
    (project / "allegati" / "dati.csv").write_text("Nome;Valore\nA;1\nB;2\n", encoding="utf-8")
    body = "Prima.\n\n![Dati di prova](allegati/dati.csv)\n\nVedi [il manuale](allegati/man.pdf).\n"
    combined = combine(project, [Item("section", "capitoli/01-intro/01-a.md", "T", 1, body)])
    assert "| Nome | Valore |" in combined.markdown and "| B | 2 |" in combined.markdown
    assert "*Dati di prova*" in combined.markdown
    assert (
        "il manuale (man.pdf)" in combined.markdown and "allegati/man.pdf)" not in combined.markdown
    )
    md = tmp_path / "c.md"
    md.write_text(combined.markdown, encoding="utf-8")
    out = tmp_path / "c.docx"
    run_pandoc(find_pandoc(), md, out, reference_doc=None, resource_dir=tmp_path)
    table = Document(str(out)).tables[0]
    assert [c.text for c in table.rows[2].cells] == ["B", "2"]
