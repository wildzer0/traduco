"""Create a company template from a few choices instead of a Word file (RF-55).

The wizard starts from Pandoc's own ``reference.docx`` (so every style the export needs exists under
the id the style mapping expects) and applies the choices of four steps: look, cover, header and
footer, summary. The result is an ordinary ``.docx`` with the usual ``{{CONTENUTO}}`` markers; it can
be opened and refined in Word afterwards.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Literal

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.section import WD_ORIENT
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor
from docx.styles.style import BaseStyle, ParagraphStyle
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.workspace.assets import detect_extension
from app.core.workspace.errors import WorkspaceError

W = nsdecls("w")
COVER_FIELDS = ("codice_documento", "revisione", "data", "cliente", "autore")
LABELS = {
    "it": {
        "codice_documento": "Codice documento", "revisione": "Revisione", "data": "Data",
        "cliente": "Cliente", "autore": "Autore", "toc": "Indice", "revisions": "Storia delle revisioni",
        "page": "Pagina", "of": "di",
    },
    "en": {
        "codice_documento": "Document code", "revisione": "Revision", "data": "Date",
        "cliente": "Client", "autore": "Author", "toc": "Contents", "revisions": "Revision history",
        "page": "Page", "of": "of",
    },
}  # fmt: skip
FONTS = (
    "Calibri",
    "Arial",
    "Times New Roman",
    "Cambria",
    "Georgia",
    "Verdana",
    "Tahoma",
    "Liberation Sans",
)
MAX_LOGO_BYTES = 2 * 1024 * 1024
_COLOR = re.compile(r"^[0-9A-Fa-f]{6}$")


class WizardOptions(BaseModel):
    """The choices of the four steps (docs/03-ui.md, "Crea template")."""

    model_config = ConfigDict(extra="forbid")

    # step 1: look
    page: Literal["A4", "Letter"] = "A4"
    font_body: str = "Calibri"
    font_heading: str = "Calibri"
    size_body: float = Field(default=11, ge=8, le=16)
    color: str = "1F4E79"
    margin_cm: float = Field(default=2.5, ge=1.0, le=5.0)
    # step 2: cover
    cover: bool = True
    cover_fields: list[str] = Field(
        default_factory=lambda: ["codice_documento", "revisione", "data"]
    )
    # step 3: header and footer
    header_text: str = "{{codice_documento}} – {{nome}}"
    footer_text: str = ""
    page_numbers: bool = True
    logo_in_header: bool = True
    # step 4: contents
    toc: bool = True
    revisions: bool = True
    language: Literal["it", "en"] = "it"

    @field_validator("font_body", "font_heading")
    @classmethod
    def _font(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9 .\-]{1,40}", value):
            raise ValueError("invalid font name")
        return value

    @field_validator("color")
    @classmethod
    def _color(cls, value: str) -> str:
        value = value.lstrip("#")
        if not _COLOR.match(value):
            raise ValueError("colour must be six hexadecimal digits")
        return value.upper()

    @field_validator("cover_fields")
    @classmethod
    def _fields(cls, value: list[str]) -> list[str]:
        unknown = [v for v in value if v not in COVER_FIELDS]
        if unknown:
            raise ValueError(f"unknown cover fields: {', '.join(unknown)}")
        return value


# --- building blocks ---------------------------------------------------------------------------------


def _style(doc: DocumentObject, name: str) -> ParagraphStyle | None:
    try:
        style = doc.styles[name]
    except KeyError:
        return None
    return style if isinstance(style, ParagraphStyle) else None


def _any_style(doc: DocumentObject, name: str) -> BaseStyle | None:
    try:
        style: BaseStyle = doc.styles[name]
    except KeyError:
        return None
    return style


def _set_fonts(style: ParagraphStyle, name: str) -> None:
    """Set the font and drop the theme attributes, which Word would prefer over the name."""
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = parse_xml(f"<w:rFonts {W}/>")
        rpr.insert(0, fonts)
    for attribute in list(fonts.attrib):
        if attribute.endswith("Theme"):
            del fonts.attrib[attribute]
    for attribute in ("ascii", "hAnsi", "cs", "eastAsia"):
        fonts.set(qn(f"w:{attribute}"), name)


def _look(doc: DocumentObject, o: WizardOptions) -> None:
    rgb = RGBColor.from_string(o.color)
    for name in (
        "Normal",
        "Body Text",
        "First Paragraph",
        "Compact",
        "Block Text",
        "Table Caption",
        "Image Caption",
    ):
        if style := _style(doc, name):
            _set_fonts(style, o.font_body)
            style.font.size = Pt(o.size_body)
    for level, size in zip(range(1, 7), (20, 16, 14, 12, 11, 11), strict=True):
        if style := _style(doc, f"Heading {level}"):
            _set_fonts(style, o.font_heading)
            style.font.size = Pt(size)
            style.font.bold = True
            style.font.color.rgb = rgb
    for name in ("Title", "Subtitle"):
        if style := _style(doc, name):
            _set_fonts(style, o.font_heading)
            style.font.color.rgb = rgb
    code = _style(doc, "Source Code")
    if code is None:  # Pandoc's reference has no paragraph style for code blocks
        code = doc.styles.add_style("Source Code", WD_STYLE_TYPE.PARAGRAPH)
        code.base_style = _style(doc, "Normal")
        code.element.get_or_add_pPr().append(
            parse_xml(f'<w:shd {W} w:val="clear" w:color="auto" w:fill="F2F2F2"/>')
        )
        code.paragraph_format.space_after = Pt(0)
    _set_fonts(code, "Consolas")
    code.font.size = Pt(max(8, o.size_body - 1.5))
    if style := _style(doc, "Image Caption"):
        style.font.italic = True
        style.font.size = Pt(max(8, o.size_body - 2))
        style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    table = _any_style(doc, "Table")
    if table is not None:
        element = table.element
        for child in element.findall(qn("w:tblPr")):
            element.remove(child)
        for child in element.findall(qn("w:tblStylePr")):
            element.remove(child)
        borders = "".join(
            f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
            for side in ("top", "left", "bottom", "right", "insideH", "insideV")
        )
        element.append(
            parse_xml(
                f"<w:tblPr {W}><w:tblBorders>{borders}</w:tblBorders><w:tblCellMar>"
                '<w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            )
        )
        element.append(
            parse_xml(
                f'<w:tblStylePr {W} w:type="firstRow"><w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>'
                f'<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="{o.color}"/></w:tcPr></w:tblStylePr>'
            )
        )


def _page(doc: DocumentObject, o: WizardOptions) -> None:
    section = doc.sections[0]
    if o.page == "A4":
        section.page_width, section.page_height = Cm(21), Cm(29.7)
    else:
        section.page_width, section.page_height = Cm(21.59), Cm(27.94)
    section.orientation = WD_ORIENT.PORTRAIT
    section.left_margin = section.right_margin = Cm(o.margin_cm)
    section.top_margin = Cm(o.margin_cm + 0.3)
    section.bottom_margin = Cm(o.margin_cm)
    section.header_distance = section.footer_distance = Cm(1.2)
    section.different_first_page_header_footer = o.cover


def _field(paragraph: object, instruction: str, cached: str) -> None:
    from docx.text.paragraph import Paragraph

    assert isinstance(paragraph, Paragraph)
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
        elif text == instruction:
            run._r.append(
                parse_xml(f'<w:instrText {W} xml:space="preserve"> {instruction} </w:instrText>')
            )
        else:
            run.text = cached


def _header_footer(doc: DocumentObject, o: WizardOptions, logo: bytes | None) -> None:
    labels = LABELS[o.language]
    section = doc.sections[0]
    header = section.header.paragraphs[0]
    if logo is not None and o.logo_in_header:
        header.add_run().add_picture(io.BytesIO(logo), height=Cm(0.9))
        header.add_run("   ")
    header.add_run(o.header_text)
    footer = section.footer.paragraphs[0]
    if o.footer_text:
        footer.add_run(o.footer_text)
    if o.page_numbers:
        if o.footer_text:
            footer.add_run("    ")
        footer.add_run(f"{labels['page']} ")
        _field(footer, "PAGE", "1")
        footer.add_run(f" {labels['of']} ")
        _field(footer, "NUMPAGES", "1")
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT if o.page_numbers and not o.footer_text else None


def _body(doc: DocumentObject, o: WizardOptions, logo: bytes | None) -> None:
    labels = LABELS[o.language]
    body = doc.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    if o.cover:
        if logo is not None:
            paragraph = doc.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.add_run().add_picture(io.BytesIO(logo), width=Cm(6))
        title = doc.add_paragraph("{{nome}}", style="Title")
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title.paragraph_format.space_before = Pt(120)
        for name in o.cover_fields:
            line = doc.add_paragraph(f"{labels[name]}: {{{{{name}}}}}", style="Body Text")
            line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    if o.toc:
        doc.add_paragraph(labels["toc"], style="TOC Heading")
        doc.add_paragraph("{{SOMMARIO}}", style="Body Text")
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    if o.revisions:
        doc.add_paragraph(labels["revisions"], style="TOC Heading")
        doc.add_paragraph("{{REVISIONI}}", style="Body Text")
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    doc.add_paragraph("{{CONTENUTO}}", style="Body Text")


def check_logo(data: bytes | None) -> bytes | None:
    """The uploaded logo must be a PNG or JPEG of reasonable size; anything else is refused."""
    if not data:
        return None
    if len(data) > MAX_LOGO_BYTES:
        raise WorkspaceError("too_large", "the logo is larger than 2 MB")
    if detect_extension(data) not in (".png", ".jpg"):
        raise WorkspaceError("invalid_image", "the logo must be a PNG or JPEG image")
    return data


def build_template(
    options: WizardOptions, reference: Path, output: Path, logo: bytes | None = None
) -> Path:
    """Write the template for ``options`` to ``output``, starting from Pandoc's reference.docx."""
    logo = check_logo(logo)
    doc = Document(str(reference))
    _look(doc, options)
    _page(doc, options)
    _body(doc, options, logo)
    _header_footer(doc, options, logo)
    doc.core_properties.title = "Template"
    doc.core_properties.author = "Traduco"
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output))
    return output
