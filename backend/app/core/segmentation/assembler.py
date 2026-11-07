"""Rebuild a Markdown file with the translated text of its segments."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

from .models import Segment, SegmentedDocument
from .segmenter import split_row

_PLAIN_TITLE = re.compile(r"[^\s#:'\"\[\]{}&*!|>%@`,\-?][^#]*")


def _continuation(first: str) -> str:
    """Prefix for the extra lines of a text whose first line has prefix ``first``."""
    return re.sub(r"[^>\s]", " ", first)


def _escape_cell(text: str) -> str:
    text = " ".join(text.split("\n"))
    return re.sub(r"(?<!\\)\|", r"\\|", text)


def _title(text: str) -> str:
    text = " ".join(text.split())
    return (
        text
        if _PLAIN_TITLE.fullmatch(text) and ": " not in text
        else json.dumps(text, ensure_ascii=False)
    )


def _replace_block(lines: list[str], seg: Segment, target: str) -> None:
    prefixes = seg.prefixes
    cont = prefixes[1] if len(prefixes) > 1 else _continuation(prefixes[0])
    new: list[str] = []
    parts = target.split("\n")
    for i, part in enumerate(parts):
        prefix = prefixes[0] if i == 0 else (prefixes[i] if i < len(prefixes) else cont)
        new.append(prefix + part)
    new[-1] += seg.suffix
    lines[seg.line : seg.end] = new


def _replace_cell(lines: list[str], seg: Segment, target: str) -> None:
    line = lines[seg.line]
    spans = split_row(line)
    assert seg.cell is not None
    a, b = spans[seg.cell]
    while a < b and line[a] in " \t":
        a += 1
    while b > a and line[b - 1] in " \t":
        b -= 1
    lines[seg.line] = line[:a] + _escape_cell(target) + line[b:]


def assemble(doc: SegmentedDocument, targets: Mapping[str, str]) -> str:
    """Return ``doc.text`` with each segment's source replaced by ``targets[key]`` if present."""
    lines = doc.text.split("\n")
    for seg in sorted(doc.segments, key=lambda s: (s.line, s.cell or 0), reverse=True):
        target = targets.get(seg.key)
        if target is None or target == seg.source:
            continue
        if seg.kind == "title":
            lines[seg.line] = "title: " + _title(target)
        elif seg.cell is not None:
            _replace_cell(lines, seg, target)
        else:
            _replace_block(lines, seg, target)
    return "\n".join(lines)
