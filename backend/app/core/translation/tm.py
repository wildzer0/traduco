"""Translation memory (RF-29): approved translations reused for the same source, suggested for a
similar one. One SQLite file per project (``.traduco/tm.sqlite``, outside Git), exportable as TMX.

A unit is keyed by the language pair and the source text with its white space normalised, so the
same sentence in two sections is one unit. The newest translation of a source wins.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from lxml import etree

from app.core.workspace.errors import WorkspaceError

FILE = ".traduco/tm.sqlite"
MIN_SIMILARITY = 0.75
MAX_IMPORT_BYTES = 50 * 1024 * 1024
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS units (
    src_lang TEXT NOT NULL,
    tgt_lang TEXT NOT NULL,
    source_norm TEXT NOT NULL,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    origin TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (src_lang, tgt_lang, source_norm)
)
"""


def normalise(text: str) -> str:
    return " ".join(text.split())


@dataclass(frozen=True)
class Match:
    source: str
    target: str
    score: float  # 1.0 = exact
    origin: str

    def public(self) -> dict[str, Any]:
        return {**asdict(self), "score": round(self.score, 3)}


def _connect(root: Path) -> sqlite3.Connection:
    path = root / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.execute(_SCHEMA)
    return db


def remember(
    root: Path, src_lang: str, tgt_lang: str, source: str, target: str, origin: str
) -> None:
    """Store (or replace) the translation of ``source``; empty texts are not worth keeping."""
    if not normalise(source) or not normalise(target):
        return
    with closing(_connect(root)) as db, db:
        db.execute(
            "INSERT INTO units VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(src_lang, tgt_lang, source_norm) DO UPDATE SET "
            "source=excluded.source, target=excluded.target, origin=excluded.origin, "
            "updated_at=excluded.updated_at",
            (
                src_lang, tgt_lang, normalise(source), source, target, origin,
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )  # fmt: skip


def exact(root: Path, src_lang: str, tgt_lang: str, source: str) -> Match | None:
    if not (root / FILE).is_file():
        return None
    with closing(_connect(root)) as db:
        row = db.execute(
            "SELECT source, target, origin FROM units "
            "WHERE src_lang=? AND tgt_lang=? AND source_norm=?",
            (src_lang, tgt_lang, normalise(source)),
        ).fetchone()
    return Match(row[0], row[1], 1.0, row[2]) if row else None


def similar(
    root: Path,
    src_lang: str,
    tgt_lang: str,
    source: str,
    *,
    minimum: float = MIN_SIMILARITY,
    limit: int = 3,
) -> list[Match]:
    """Exact match first, then the closest sources by character similarity (case ignored)."""
    if not (root / FILE).is_file():
        return []
    wanted = normalise(source)
    low, high = (
        int(len(wanted) * (2 * minimum - 1)),
        int(len(wanted) / max(0.01, 2 * minimum - 1)) + 1,
    )
    with closing(_connect(root)) as db:
        rows = db.execute(
            "SELECT source, target, origin, source_norm FROM units "
            "WHERE src_lang=? AND tgt_lang=? AND length(source_norm) BETWEEN ? AND ?",
            (src_lang, tgt_lang, low, high),
        ).fetchall()
    folded = wanted.casefold()
    found: list[Match] = []
    for src, tgt, origin, norm in rows:
        if norm == wanted:
            found.append(Match(src, tgt, 1.0, origin))
            continue
        matcher = SequenceMatcher(None, folded, norm.casefold(), autojunk=False)
        if matcher.real_quick_ratio() < minimum or matcher.quick_ratio() < minimum:
            continue
        score = matcher.ratio()
        if score >= minimum:
            found.append(Match(src, tgt, score, origin))
    return sorted(found, key=lambda m: -m.score)[:limit]


def count(root: Path) -> int:
    if not (root / FILE).is_file():
        return 0
    with closing(_connect(root)) as db:
        return int(db.execute("SELECT COUNT(*) FROM units").fetchone()[0])


# --- TMX 1.4 -----------------------------------------------------------------------------------


def export_tmx(root: Path, src_lang: str) -> bytes:
    """Every unit as TMX 1.4b, readable by the usual CAT tools."""
    tmx = etree.Element("tmx", version="1.4")
    etree.SubElement(
        tmx, "header", creationtool="Traduco", creationtoolversion="1", segtype="paragraph",
        adminlang="en", srclang=src_lang, datatype="plaintext", **{"o-tmf": "Traduco"},
    )  # fmt: skip
    body = etree.SubElement(tmx, "body")
    if (root / FILE).is_file():
        with closing(_connect(root)) as db:
            rows = db.execute(
                "SELECT src_lang, tgt_lang, source, target, updated_at FROM units "
                "ORDER BY src_lang, tgt_lang, source_norm"
            ).fetchall()
        for s_lang, t_lang, source, target, updated in rows:
            tu = etree.SubElement(body, "tu", creationdate=_tmx_date(updated))
            for lang, text in ((s_lang, source), (t_lang, target)):
                tuv = etree.SubElement(tu, "tuv", {_XML_LANG: lang})
                etree.SubElement(tuv, "seg").text = text
    return bytes(etree.tostring(tmx, xml_declaration=True, encoding="UTF-8", pretty_print=True))


def _tmx_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y%m%dT%H%M%SZ")
    except ValueError:
        return "19700101T000000Z"


def import_tmx(root: Path, data: bytes) -> int:
    """Add the units of a TMX file (text of each ``<seg>``); returns how many were stored."""
    if len(data) > MAX_IMPORT_BYTES:
        raise WorkspaceError("too_large", "the TMX file is larger than 50 MB")
    parser = etree.XMLParser(
        resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
    )
    try:
        tree = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as exc:
        raise WorkspaceError("invalid_template", f"this is not a valid TMX file: {exc}") from exc
    if tree.tag != "tmx":
        raise WorkspaceError("invalid_template", "this is not a TMX file")
    header = tree.find("header")
    declared = ((header.get("srclang") if header is not None else "") or "").split("-")[0].lower()
    added = 0
    for tu in tree.iter("tu"):
        variants: dict[str, str] = {}
        for tuv in tu.findall("tuv"):
            lang = (tuv.get(_XML_LANG) or tuv.get("lang") or "").split("-")[0].lower()
            seg = tuv.find("seg")
            if lang and seg is not None:
                variants[lang] = "".join(seg.itertext())
        if len(variants) < 2:
            continue
        src_lang = declared if declared in variants else next(iter(variants))
        for lang, text in variants.items():
            if lang != src_lang:
                remember(root, src_lang, lang, variants[src_lang], text, "tmx")
                added += 1
    return added
