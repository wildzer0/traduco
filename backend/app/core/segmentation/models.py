"""Data model of the segmentation pipeline (docs/02-architettura.md)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Segment:
    """One translatable unit and where it sits in the source document.

    ``line``/``end`` are 0-based line numbers of the *whole file* (front matter included).
    ``prefixes`` hold, for each source line, the container markup before the text (``- ``,
    ``> ``, ``[^1]: ``, indentation); ``suffix`` is the trailing whitespace after the last line.
    A table cell is located by ``line`` and ``cell``; the front matter title by ``kind == "title"``.
    """

    key: str
    kind: str
    source: str
    line: int
    end: int
    prefixes: tuple[str, ...] = ()
    suffix: str = ""
    cell: int | None = None
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hash", hash_text(self.source))


@dataclass(frozen=True)
class SegmentedDocument:
    text: str
    segments: tuple[Segment, ...]

    def by_key(self) -> dict[str, Segment]:
        return {s.key: s for s in self.segments}
