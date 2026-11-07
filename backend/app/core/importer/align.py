"""Line up the units of a revised document with those recorded when it was exported.

Both sides are reduced to plain, comparable text; ``difflib`` finds what stayed the same and the
changed stretches are paired by similarity. What is left over is "added" or "deleted". Whatever lies
before the first and after the last unit present on both sides (the cover, the table of contents,
the revision table) belongs to the template and is ignored.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

_FIELD = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_REF = re.compile(r"\[\^[^\]]+\]")
_SPAN = re.compile(r"\[([^\]]*)\]\{[^}]*\}")
_ATTR = re.compile(r"\s*\{[#.][^}]*\}\s*$")
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
_CAPTION = re.compile(
    r"^(?:figura|figure|abbildung|fig\.?|tabella|table|tabelle)\s+\d+\s*[–—:.-]\s*"
)
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', " ": " "})
SIMILARITY = 0.5

Kind = Literal["modified", "added", "deleted"]


def plain(text: str, fields: Mapping[str, str | None] | None = None) -> str:
    """Comparable form of a unit: no Markdown syntax, fields filled, quotes straightened."""
    t = text
    if fields:
        t = _FIELD.sub(lambda m: str(fields.get(m.group(1)) or m.group(0)), t)
    t = _IMAGE.sub(r"\1", t)
    t = _LINK.sub(r"\1", t)
    t = _REF.sub("", t)
    t = _SPAN.sub(r"\1", t)
    t = _ATTR.sub("", t)
    t = _ESCAPE.sub(r"\1", t)
    t = re.sub(r"[*_~`]", "", t)
    t = t.translate(_QUOTES)
    t = re.sub(r"\s+", " ", t).strip()
    t = _CAPTION.sub("", t.casefold())
    return t


@dataclass(frozen=True)
class Change:
    kind: Kind
    old: int | None  # index into the exported units (None for added)
    new: int | None  # index into the document units (None for deleted)
    after: int | None = None  # for added: the exported unit it follows


def _pair(
    a: Sequence[str], b: Sequence[str], a0: int, b0: int
) -> list[tuple[int | None, int | None]]:
    """Pair the units of a changed stretch by similarity, keeping their order."""
    pairs: list[tuple[int | None, int | None]] = []
    j = 0
    for i, text in enumerate(a):
        best, best_j = 0.0, -1
        for k in range(j, len(b)):
            ratio = SequenceMatcher(None, text, b[k], autojunk=False).ratio()
            if ratio > best:
                best, best_j = ratio, k
        if best >= SIMILARITY:
            pairs.extend((None, b0 + k) for k in range(j, best_j))
            pairs.append((a0 + i, b0 + best_j))
            j = best_j + 1
        else:
            pairs.append((a0 + i, None))
    pairs.extend((None, b0 + k) for k in range(j, len(b)))
    return pairs


def align(exported: Sequence[str], found: Sequence[str]) -> list[Change]:
    """Changes between two lists of plain texts; template parts at the edges are left out."""
    matcher = SequenceMatcher(None, list(exported), list(found), autojunk=False)
    events: list[tuple[str, int | None, int | None]] = []  # (state, old, new)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            events.extend(("same", i1 + n, j1 + n) for n in range(i2 - i1))
        elif tag == "delete":
            events.extend(("deleted", i, None) for i in range(i1, i2))
        elif tag == "insert":
            events.extend(("added", None, j) for j in range(j1, j2))
        else:
            for old, new in _pair(exported[i1:i2], found[j1:j2], i1, j1):
                state = (
                    "modified"
                    if old is not None and new is not None
                    else ("deleted" if old is not None else "added")
                )
                events.append((state, old, new))
    anchored = [n for n, (state, _, _) in enumerate(events) if state in ("same", "modified")]
    if not anchored:
        return []
    first, last = anchored[0], anchored[-1]
    changes: list[Change] = []
    previous: int | None = None
    for n, (state, old, new) in enumerate(events):
        if old is not None:
            previous = old
        if n < first or n > last or state == "same":
            continue
        if state == "added":
            changes.append(Change("added", None, new, after=previous))
        else:
            changes.append(Change(state, old, new))  # type: ignore[arg-type]
    return changes
