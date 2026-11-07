"""Builds a realistic company Word template for tests and for the example project.

It reproduces what real templates do and what makes them hard to handle: Italian style names with
custom ids, a numbered heading list tied to the styles, a custom table style, a cover with a logo and
fields (one of them inside a text box), a header whose field is split over several runs, a page
number footer, and the ``{{SOMMARIO}}`` / ``{{REVISIONI}}`` / ``{{CONTENUTO}}`` markers.
"""

from __future__ import annotations

import struct
import tempfile
import zlib
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

W = nsdecls("w")


def logo_png(
    path: Path, width: int = 240, height: int = 80, rgb: tuple[int, int, int] = (31, 78, 121)
) -> Path:
    """A plain coloured PNG, made without imaging libraries."""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


def _paragraph_style(
    style_id: str, name: str, based_on: str = "Normal", ppr: str = "", rpr: str = ""
) -> str:
    return (
        f'<w:style {W} w:type="paragraph" w:customStyle="1" w:styleId="{style_id}">'
        f'<w:name w:val="{name}"/><w:basedOn w:val="{based_on}"/><w:qFormat/>'
        f"<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>"
    )


def _numbering(doc: DocumentObject) -> None:
    """Heading outline (1 / 1.1 / 1.1.1) tied to the heading styles, a bullet list and a numbered list."""
    numbering = doc.part.numbering_part.element
    heading_levels = "".join(
        f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="decimal"/>'
        f'<w:pStyle w:val="AziendaTitolo{i + 1}"/><w:lvlText w:val="{".".join(f"%{n + 1}" for n in range(i + 1))}"/>'
        f'<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="{432 + 144 * i}" w:hanging="{432 + 144 * i}"/></w:pPr></w:lvl>'
        for i in range(3)
    )
    abstract = [
        f'<w:abstractNum {W} w:abstractNumId="90"><w:multiLevelType w:val="multilevel"/>{heading_levels}</w:abstractNum>',
        f'<w:abstractNum {W} w:abstractNumId="91"><w:multiLevelType w:val="hybridMultilevel"/>'
        '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:pStyle w:val="AziendaElencoPuntato"/>'
        '<w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="567" w:hanging="283"/></w:pPr></w:lvl></w:abstractNum>',
        f'<w:abstractNum {W} w:abstractNumId="92"><w:multiLevelType w:val="hybridMultilevel"/>'
        '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="AziendaElencoNumerato"/>'
        '<w:lvlText w:val="%1)"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="567" w:hanging="340"/></w:pPr></w:lvl></w:abstractNum>',
    ]
    first_num = numbering.find(qn("w:num"))
    for xml in abstract:
        element = parse_xml(xml)
        if first_num is not None:
            first_num.addprevious(element)
        else:
            numbering.append(element)
    for num_id, abstract_id in ((90, 90), (91, 91), (92, 92)):
        numbering.append(
            parse_xml(
                f'<w:num {W} w:numId="{num_id}"><w:abstractNumId w:val="{abstract_id}"/></w:num>'
            )
        )


def _styles(doc: DocumentObject) -> None:
    styles = doc.styles.element
    colour = '<w:color w:val="1F4E79"/>'
    for level, size in ((1, 32), (2, 28), (3, 24)):
        styles.append(
            parse_xml(
                _paragraph_style(
                    f"AziendaTitolo{level}",
                    f"Azienda Titolo {level}",
                    ppr=(
                        f'<w:keepNext/><w:spacing w:before="{360 - 60 * level}" w:after="120"/>'
                        f'<w:numPr><w:ilvl w:val="{level - 1}"/><w:numId w:val="90"/></w:numPr>'
                        f'<w:outlineLvl w:val="{level - 1}"/>'
                    ),
                    rpr=f'<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/>{colour}<w:sz w:val="{size}"/>',
                )
            )
        )
    for style_id, name, ppr, rpr in (
        (
            "AziendaCorpo",
            "Azienda Corpo",
            '<w:spacing w:after="120" w:line="276" w:lineRule="auto"/><w:jc w:val="both"/>',
            '<w:sz w:val="22"/>',
        ),
        (
            "AziendaDidascalia",
            "Azienda Didascalia",
            '<w:spacing w:before="60" w:after="200"/><w:jc w:val="center"/>',
            '<w:i/><w:sz w:val="18"/>',
        ),
        (
            "AziendaElencoPuntato",
            "Azienda Elenco Puntato",
            '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="91"/></w:numPr><w:spacing w:after="60"/>',
            '<w:sz w:val="22"/>',
        ),
        (
            "AziendaElencoNumerato",
            "Azienda Elenco Numerato",
            '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="92"/></w:numPr><w:spacing w:after="60"/>',
            '<w:sz w:val="22"/>',
        ),
        (
            "AziendaCitazione",
            "Azienda Citazione",
            '<w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="1F4E79"/></w:pBdr><w:ind w:left="567"/>',
            "<w:i/>",
        ),
        (
            "AziendaCodice",
            "Azienda Codice",
            '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/><w:spacing w:after="0"/>',
            '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="19"/>',
        ),
        (
            "AziendaCopertinaTitolo",
            "Azienda Copertina Titolo",
            '<w:spacing w:before="1800" w:after="240"/><w:jc w:val="center"/>',
            f'<w:b/>{colour}<w:sz w:val="56"/>',
        ),
        (
            "AziendaCopertinaDato",
            "Azienda Copertina Dato",
            '<w:spacing w:after="60"/><w:jc w:val="center"/>',
            '<w:sz w:val="26"/>',
        ),
    ):
        styles.append(parse_xml(_paragraph_style(style_id, name, ppr=ppr, rpr=rpr)))
    styles.append(
        parse_xml(
            f'<w:style {W} w:type="table" w:customStyle="1" w:styleId="AziendaTabella">'
            '<w:name w:val="Azienda Tabella"/><w:basedOn w:val="TableNormal"/><w:uiPriority w:val="59"/><w:qFormat/>'
            "<w:tblPr><w:tblBorders>"
            + "".join(
                f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="7F7F7F"/>'
                for side in ("top", "left", "bottom", "right", "insideH", "insideV")
            )
            + '</w:tblBorders><w:tblCellMar><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            '<w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>'
            '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="1F4E79"/></w:tcPr></w:tblStylePr></w:style>'
        )
    )


def _field(paragraph: Paragraph, instruction: str, cached: str = "1") -> None:
    for kind, text in (
        ("begin", None),
        (None, instruction),
        ("separate", None),
        (None, cached),
        ("end", None),
    ):
        run = paragraph.add_run()
        if kind:
            run._r.append(parse_xml(f'<w:fldChar {W} w:fldCharType="{kind}"/>'))
        elif text is instruction:
            run._r.append(
                parse_xml(f'<w:instrText {W} xml:space="preserve"> {instruction} </w:instrText>')
            )
        else:
            run.text = cached


def build_company_template(path: Path) -> Path:
    doc = Document()
    _styles(doc)
    _numbering(doc)
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.5)
    section.top_margin, section.bottom_margin = Cm(2.8), Cm(2.5)
    section.different_first_page_header_footer = True

    # header: the field is deliberately split over runs, as Word does after editing
    header = section.header.paragraphs[0]
    for text in ("Doc. {{codice_", "documento}} – rev. {{rev", "isione}}"):
        header.add_run(text)
    footer = section.footer.paragraphs[0]
    footer.add_run("Pagina ")
    _field(footer, "PAGE")
    footer.add_run(" di ")
    _field(footer, "NUMPAGES", "9")

    body = doc.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)

    with tempfile.TemporaryDirectory() as tmp:
        logo = logo_png(Path(tmp) / "logo.png")
        cover_logo = doc.add_paragraph()
        cover_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cover_logo.add_run().add_picture(str(logo), width=Cm(6))
    doc.add_paragraph("{{nome}}", style="Azienda Copertina Titolo")
    for label, field in (
        ("Codice documento", "codice_documento"),
        ("Revisione", "revisione"),
        ("Data", "data"),
        ("Autore", "autore"),
    ):
        doc.add_paragraph(f"{label}: {{{{{field}}}}}", style="Azienda Copertina Dato")
    # a text box (VML) holding a field, like a stamp on the cover
    box = doc.add_paragraph()
    box._p.append(
        parse_xml(
            f'<w:r {W} xmlns:v="urn:schemas-microsoft-com:vml"><w:pict><v:shape id="stamp" type="#_x0000_t202" '
            'style="width:200pt;height:30pt" stroked="t"><v:textbox><w:txbxContent><w:p><w:r><w:t>Cliente: {{cliente}}</w:t></w:r></w:p>'
            "</w:txbxContent></v:textbox></v:shape></w:pict></w:r>"
        )
    )
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    doc.add_paragraph(
        "Indice", style="Azienda Copertina Titolo"
    ).paragraph_format.space_before = Pt(0)
    doc.add_paragraph("{{SOMMARIO}}", style="Azienda Corpo")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    doc.add_paragraph(
        "Storia delle revisioni", style="Azienda Copertina Titolo"
    ).paragraph_format.space_before = Pt(0)
    doc.add_paragraph("{{REVISIONI}}", style="Azienda Corpo")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    doc.add_paragraph("{{CONTENUTO}}", style="Azienda Corpo")

    doc.core_properties.title = "Template aziendale di prova"
    doc.core_properties.author = "Traduco tests"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path
