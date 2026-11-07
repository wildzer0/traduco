"""Search the text of a project: sections in the source language and their translations.

Plain, case- and accent-insensitive substring search over the segments. A project is a few
hundred small files: there is no index to keep in step, the files stay the only source of truth.
"""

from __future__ import annotations

import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.segmentation.segmenter import segment
from app.core.translation import store
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.sections import read_section
from app.core.workspace.tree import Node, build_tree

MIN_QUERY = 2
CONTEXT = 50


def fold(text: str) -> str:
    """Lower case without accents: ``Qualità`` matches ``qualita``."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass(frozen=True)
class Hit:
    path: str
    title: str
    key: str
    field: str  # source | translation
    before: str
    match: str
    after: str


def _snippet(text: str, start: int, length: int) -> tuple[str, str, str]:
    lo, hi = max(0, start - CONTEXT), min(len(text), start + length + CONTEXT)
    return (
        ("…" if lo else "") + text[lo:start],
        text[start : start + length],
        text[start + length : hi] + ("…" if hi < len(text) else ""),
    )


def _find(folded_text: str, text: str, needle: str) -> tuple[int, int] | None:
    """Position of ``needle`` in the original text (folding can change lengths)."""
    at = folded_text.find(needle)
    if at < 0:
        return None
    if len(folded_text) == len(text):
        return at, len(needle)
    # accents expanded or merged: fall back to a char-by-char scan of the original
    for start in range(len(text)):
        if fold(text[start : start + len(needle) + 2]).startswith(needle):
            for end in range(start + 1, min(len(text), start + len(needle) + 3) + 1):
                if fold(text[start:end]) == needle:
                    return start, end - start
    return at, len(needle)


def _sections(nodes: list[Node]) -> list[Node]:
    out: list[Node] = []
    for node in nodes:
        if node.kind == "section":
            out.append(node)
        out.extend(_sections(node.children))
    return out


def search(root: Path, query: str, official: str, *, limit: int = 50) -> list[dict[str, Any]]:
    needle = fold(query.strip())
    if len(needle) < MIN_QUERY:
        return []
    hits: list[Hit] = []
    for node in _sections(build_tree(root)):
        try:
            text, _ = read_section(root, node.path)
        except WorkspaceError:
            continue
        stored = store.load(root, official, node.path)
        targets = {s.key: s.target for s in stored.segments if s.target} if stored else {}
        for seg in segment(text).segments:
            for field, value in (("source", seg.source), ("translation", targets.get(seg.key, ""))):
                if not value:
                    continue
                found = _find(fold(value), value, needle)
                if found is None:
                    continue
                before, match, after = _snippet(value, *found)
                hits.append(Hit(node.path, node.title, seg.key, field, before, match, after))
                if len(hits) >= limit:
                    return [asdict(h) for h in hits]
    return [asdict(h) for h in hits]
