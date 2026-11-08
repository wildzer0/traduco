"""Read the text of a revised ``.docx`` with Word's tracked changes taken into account.

The reader works on the document XML instead of converting to Markdown: tables stay cell by cell,
and insertions/deletions are resolved exactly (an insertion counts as text, a deletion does not,
a move counts at its destination). The result is a list of units in reading order that can be
lined up with the units recorded when the document was exported.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

_SKIP_CONTAINERS = {qn("w:del"), qn("w:moveFrom")}
_TRACKED = {qn("w:ins"), qn("w:moveTo"), qn("w:del"), qn("w:moveFrom")}
AUTHOR = qn("w:author")
_SPACES = {qn("w:tab"), qn("w:br"), qn("w:noBreakHyphen")}


@dataclass
class DocUnit:
    kind: str  # paragraph | cell | footnote
    text: str
    style: str = ""
    authors: set[str] = field(default_factory=set)
    tracked: bool = False  # the text was changed with Word's change tracking


def _paragraph(p: Any) -> tuple[str, set[str], bool]:
    """(text after the tracked changes, authors of the changes, any change?) of a ``w:p``."""
    parts: list[str] = []
    authors: set[str] = set()
    tracked = False
    for element in p.iter():
        if element.tag in _TRACKED:
            tracked = True
            if element.get(AUTHOR):
                authors.add(str(element.get(AUTHOR)))
        skipped = any(a.tag in _SKIP_CONTAINERS for a in element.iterancestors())
        if element.tag == qn("w:t") and not skipped:
            parts.append(element.text or "")
        elif element.tag in _SPACES and not skipped and element.get(qn("w:type")) != "page":
            parts.append(" ")
    return "".join(parts).strip(), authors, tracked


def _style(p: Any) -> str:
    style = p.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    return str(style.get(qn("w:val"))) if style is not None else ""


def _toc_edges(p: Any) -> tuple[bool, bool]:
    """(starts, ends) a table of contents field: its entries are not text of the document."""
    starts = any(i.text and i.text.strip().startswith("TOC") for i in p.iter(qn("w:instrText")))
    ends = any(f.get(qn("w:fldCharType")) == "end" for f in p.iter(qn("w:fldChar")))
    return starts, ends


def _blocks(container: Any) -> list[DocUnit]:
    units: list[DocUnit] = []
    in_toc = False
    for child in container:
        if child.tag == qn("w:p"):
            starts, ends = _toc_edges(child)
            if starts:
                in_toc = True
            if in_toc:
                if ends:
                    in_toc = False
                continue
            text, authors, tracked = _paragraph(child)
            if text:
                units.append(DocUnit("paragraph", text, _style(child), authors, tracked))
        elif child.tag == qn("w:tbl"):
            for cell in child.iter(qn("w:tc")):
                texts, authors, tracked = [], set(), False
                for p in cell.findall(qn("w:p")):
                    text, a, t = _paragraph(p)
                    if text:
                        texts.append(text)
                    authors |= a
                    tracked = tracked or t
                if texts:
                    units.append(DocUnit("cell", " ".join(texts), "", authors, tracked))
        elif child.tag == qn("w:sdt"):
            content = child.find(qn("w:sdtContent"))
            if content is not None:
                units.extend(_blocks(content))
    return units


def _footnotes(path: Path) -> list[DocUnit]:
    try:
        with zipfile.ZipFile(path) as z:
            data = z.read("word/footnotes.xml")
    except (KeyError, zipfile.BadZipFile):
        return []
    root = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    units: list[DocUnit] = []
    for note in root.findall(qn("w:footnote")):
        if note.get(qn("w:type")) in ("separator", "continuationSeparator", "continuationNotice"):
            continue
        texts: list[str] = []
        authors: set[str] = set()
        tracked = False
        for p in note.findall(qn("w:p")):
            text, a, t = _paragraph(p)
            if text:
                texts.append(text)
            authors |= a
            tracked = tracked or t
        if texts:
            units.append(DocUnit("footnote", " ".join(texts), "", authors, tracked))
    return units


def read_units(path: Path) -> list[DocUnit]:
    """Body units in reading order, then the footnotes (kept together, as Word stores them)."""
    doc = Document(str(path))
    return [*_blocks(doc.element.body), *_footnotes(path)]


def export_identifier(path: Path) -> str | None:
    """The id of the export this file came from (set in its document properties), if any."""
    identifier = Document(str(path)).core_properties.identifier
    return identifier or None
