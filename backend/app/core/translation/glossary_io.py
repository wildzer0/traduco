"""Glossary import and export as CSV and TBX (RF-44).

CSV has one row per entry and language: ``sorgente,lingua,destinazione,vietati,non_tradurre,note``
(``vietati`` separated by ``|``). TBX is the usual termbase exchange format (a TBX-Basic subset:
one ``termEntry`` per term, one ``langSet`` per language, forbidden terms flagged). Importing
*merges* into the existing glossary: a term that is already there keeps what it has and gains
what the file adds, so nothing the author wrote is lost.
"""

from __future__ import annotations

import csv
import io

from lxml import etree

from app.core.workspace.errors import WorkspaceError

from .glossary import Entry

COLUMNS = ["sorgente", "lingua", "destinazione", "vietati", "non_tradurre", "note"]
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_FORBIDDEN = "forbidden-term-admn-sts"
MAX_BYTES = 10 * 1024 * 1024


def merge(existing: list[Entry], incoming: list[Entry]) -> list[Entry]:
    """Add ``incoming`` to ``existing``; for a known term the file fills in, never overwrites."""
    by_term = {e.sorgente.casefold(): e for e in existing}
    merged = list(existing)
    for new in incoming:
        old = by_term.get(new.sorgente.casefold())
        if old is None:
            merged.append(new)
            by_term[new.sorgente.casefold()] = new
            continue
        for lang, text in new.destinazione.items():
            old.destinazione.setdefault(lang, text)
        for lang, words in new.vietati.items():
            have = old.vietati.setdefault(lang, [])
            have.extend(w for w in words if w not in have)
        old.non_tradurre = old.non_tradurre or new.non_tradurre
        old.note = old.note or new.note
    return merged


# --- CSV ---------------------------------------------------------------------------------------


def export_csv(entries: list[Entry]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for e in entries:
        langs = sorted(set(e.destinazione) | set(e.vietati)) or [""]
        for lang in langs:
            writer.writerow(
                [
                    e.sorgente, lang, e.destinazione.get(lang, ""),
                    "|".join(e.vietati.get(lang, [])), "1" if e.non_tradurre else "0", e.note,
                ]
            )  # fmt: skip
    return b"\xef\xbb\xbf" + out.getvalue().encode("utf-8")  # BOM: Excel reads it as UTF-8


def import_csv(data: bytes) -> list[Entry]:
    if len(data) > MAX_BYTES:
        raise WorkspaceError("too_large", "the file is larger than 10 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise WorkspaceError("invalid_template", "the CSV file is not UTF-8 text") from exc
    first = text.splitlines()[0] if text.strip() else ""
    delimiter = max(",;\t", key=first.count) if first else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames or "sorgente" not in [f.strip().lower() for f in reader.fieldnames]:
        raise WorkspaceError("invalid_template", 'the CSV needs a header with a "sorgente" column')
    entries: dict[str, Entry] = {}
    for row in reader:
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        term = r.get("sorgente", "")
        if not term:
            continue
        entry = entries.setdefault(term.casefold(), Entry(sorgente=term))
        lang = r.get("lingua", "")
        if lang and r.get("destinazione"):
            entry.destinazione[lang] = r["destinazione"]
        if lang and r.get("vietati"):
            entry.vietati[lang] = [w.strip() for w in r["vietati"].split("|") if w.strip()]
        entry.non_tradurre = entry.non_tradurre or r.get("non_tradurre", "").lower() in (
            "1",
            "true",
            "si",
            "sì",
            "yes",
        )
        entry.note = entry.note or r.get("note", "")
    return list(entries.values())


# --- TBX ---------------------------------------------------------------------------------------


def export_tbx(entries: list[Entry], source_lang: str) -> bytes:
    root = etree.Element("martif", type="TBX-Basic", **{_XML_LANG: source_lang})
    etree.SubElement(etree.SubElement(root, "martifHeader"), "fileDesc")
    body = etree.SubElement(etree.SubElement(root, "text"), "body")
    for e in entries:
        entry = etree.SubElement(body, "termEntry")
        if e.non_tradurre:
            etree.SubElement(entry, "descrip", type="doNotTranslate").text = "true"
        if e.note:
            etree.SubElement(entry, "note").text = e.note
        src = etree.SubElement(etree.SubElement(entry, "langSet", {_XML_LANG: source_lang}), "tig")
        etree.SubElement(src, "term").text = e.sorgente
        for lang in sorted(set(e.destinazione) | set(e.vietati)):
            tig_parent = etree.SubElement(entry, "langSet", {_XML_LANG: lang})
            if lang in e.destinazione:
                tig = etree.SubElement(tig_parent, "tig")
                etree.SubElement(tig, "term").text = e.destinazione[lang]
            for word in e.vietati.get(lang, []):
                tig = etree.SubElement(tig_parent, "tig")
                etree.SubElement(tig, "term").text = word
                etree.SubElement(tig, "termNote", type="administrativeStatus").text = _FORBIDDEN
    return bytes(etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def import_tbx(data: bytes, source_lang: str) -> list[Entry]:
    if len(data) > MAX_BYTES:
        raise WorkspaceError("too_large", "the file is larger than 10 MB")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as exc:
        raise WorkspaceError("invalid_template", f"this is not a valid TBX file: {exc}") from exc
    if root.tag != "martif":
        raise WorkspaceError("invalid_template", "this is not a TBX file")
    declared = (root.get(_XML_LANG) or source_lang).split("-")[0].lower()
    entries: list[Entry] = []
    for term_entry in root.iter("termEntry"):
        sets: dict[str, list[tuple[str, bool]]] = {}
        for lang_set in term_entry.findall("langSet"):
            lang = (lang_set.get(_XML_LANG) or "").split("-")[0].lower()
            for tig in list(lang_set.iter("tig")) + list(lang_set.iter("ntig")):
                term = tig.find("term")
                if lang and term is not None and (term.text or "").strip():
                    forbidden = any(
                        _FORBIDDEN in "".join(n.itertext()) for n in tig.iter("termNote")
                    )
                    sets.setdefault(lang, []).append(((term.text or "").strip(), forbidden))
        source = next((t for t, bad in sets.get(declared, []) if not bad), None)
        if source is None:
            continue
        entry = Entry(sorgente=source)
        for lang, terms in sets.items():
            if lang == declared:
                continue
            allowed = [t for t, bad in terms if not bad]
            if allowed:
                entry.destinazione[lang] = allowed[0]
            banned = [t for t, bad in terms if bad]
            if banned:
                entry.vietati[lang] = banned
        entry.non_tradurre = any(
            (d.text or "").strip().lower() == "true"
            for d in term_entry.findall("descrip")
            if d.get("type") == "doNotTranslate"
        )
        note = term_entry.find("note")
        entry.note = (note.text or "").strip() if note is not None else ""
        entries.append(entry)
    return entries
