"""Split a Markdown section into translatable segments (ADR-006).

Translatable: titles, paragraphs, list items, table cells, footnotes, quotes and the front matter
``title``. Code, Mermaid, raw HTML and everything else stay in the file untouched. Image alt text
and link text are part of the paragraph they appear in.
"""

from __future__ import annotations

import re
from collections import Counter

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.footnote import footnote_plugin

from app.core.workspace.frontmatter import split_raw

from .models import Segment, SegmentedDocument

_TITLE = re.compile(r"^title:[ \t]*(?P<value>.+?)[ \t]*$")


def _parser() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": True}).enable("table").use(footnote_plugin)


def split_row(line: str) -> list[tuple[int, int]]:
    """Spans (start, end) of the cell contents of a table row, honouring ``\\|`` escapes."""
    row = line.rstrip()
    first = len(row) - len(row.lstrip())
    start = first + 1 if row[first : first + 1] == "|" else first
    spans: list[tuple[int, int]] = []
    pos = start
    for j in range(start, len(row)):
        if row[j] == "|" and (j == 0 or row[j - 1] != "\\"):
            spans.append((pos, j))
            pos = j + 1
    if pos < len(row):
        spans.append((pos, len(row)))
    return spans


def _trim(line: str, span: tuple[int, int]) -> tuple[int, int]:
    a, b = span
    while a < b and line[a] in " \t":
        a += 1
    while b > a and line[b - 1] in " \t":
        b -= 1
    return a, b


def _line_parts(line: str, content: str) -> tuple[str, str] | None:
    """Split a source line into (prefix, text) given the inline content line."""
    body = line.rstrip()
    wanted = content.rstrip()
    if not body.endswith(wanted):
        return None
    cut = len(body) - len(wanted)
    return line[:cut], line[cut:]


def _block_segment(
    key: str, kind: str, token: Token, lines: list[str], content: str
) -> Segment | None:
    assert token.map is not None
    start, end = token.map
    content_lines = content.split("\n")
    if len(content_lines) != end - start:
        return None
    prefixes: list[str] = []
    texts: list[str] = []
    suffix = ""
    for index, (src, cont) in enumerate(zip(lines[start:end], content_lines, strict=True)):
        parts = _line_parts(src, cont)
        if parts is None:
            return None
        prefix, text = parts
        if index == len(content_lines) - 1:
            keep = text.rstrip()
            suffix = text[len(keep) :]
            text = keep
        prefixes.append(prefix)
        texts.append(text)
    source = "\n".join(texts)
    if not source.strip():
        return None
    return Segment(key, kind, source, start, end, tuple(prefixes), suffix)


def segment(text: str) -> SegmentedDocument:
    """Segment a whole file (front matter included). Keys are ``kind:ordinal``."""
    head, body = split_raw(text)
    offset = head.count("\n")
    lines = text.split("\n")
    counters: Counter[str] = Counter()
    found: list[Segment] = []

    def add(prefix: str, kind: str, token: Token, content: str) -> None:
        key = f"{prefix}:{counters[prefix]}"
        seg = _block_segment(key, kind, token, lines, content)
        counters[prefix] += 1
        if seg is not None:
            found.append(seg)

    if head:
        for i, raw in enumerate(head.split("\n")[1:-2], start=1):
            match = _TITLE.match(raw)
            if match:
                value = match.group("value")
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                if value and not value.startswith(("|", ">", "&", "*", "[", "{")):
                    found.append(Segment("fm:title", "title", value, i, i + 1))
                break

    tokens = _parser().parse(body)
    # shift body line numbers to whole-file line numbers
    for token in tokens:
        if token.map:
            token.map = [token.map[0] + offset, token.map[1] + offset]

    stack: list[str] = []
    tables = -1
    row = -1
    col = -1
    for token in tokens:
        kind = token.type
        if kind.endswith("_open"):
            stack.append(kind[: -len("_open")])
        elif kind.endswith("_close") and stack:
            stack.pop()
        if kind == "table_open":
            tables += 1
            row = -1
        elif kind == "tr_open":
            row += 1
            col = -1
        elif kind in ("th_open", "td_open"):
            col += 1
        if kind != "inline" or token.map is None:
            continue
        parent = stack[-1] if stack else ""
        if parent == "heading":
            add("h", "heading", token, token.content)
        elif parent in ("th", "td"):
            _cell(found, lines, token, tables, row, col, parent)
        elif parent == "paragraph":
            context = [s for s in stack if s in ("list_item", "blockquote", "footnote")]
            inner = context[-1] if context else ""
            if inner == "footnote":
                add("fn", "footnote", token, token.content)
            elif inner == "list_item":
                add("li", "list_item", token, token.content)
            elif inner == "blockquote":
                add("q", "quote", token, token.content)
            else:
                add("p", "paragraph", token, token.content)
    return SegmentedDocument(text, tuple(sorted(found, key=lambda s: (s.line, s.cell or 0))))


def _cell(
    found: list[Segment],
    lines: list[str],
    token: Token,
    table: int,
    row: int,
    col: int,
    parent: str,
) -> None:
    assert token.map is not None
    line = lines[token.map[0]]
    spans = split_row(line)
    if col >= len(spans):
        return
    a, b = _trim(line, spans[col])
    content = line[a:b]
    if not content.strip():
        return
    if parent == "th":
        key, kind = f"th:{table}:{col}", "table_header"
    else:
        key, kind = f"td:{table}:{row - 1}:{col}", "table_cell"
    found.append(Segment(key, kind, content, token.map[0], token.map[0] + 1, cell=col))
