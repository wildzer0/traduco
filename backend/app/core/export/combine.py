"""Join the sections of a project into one Markdown document for Pandoc (docs/02, "Export DOCX").

What it takes care of:
- one heading per chapter and per section, at a level that follows the nesting, with the headings
  written inside each section shifted below it;
- images copied under neutral names (no spaces, no paths outside the project) and remote images
  left out, so Pandoc never touches the network;
- Mermaid blocks replaced by the PNG rendered by the browser (an export stops if one is missing);
- links to other sections turned into anchors, footnote labels made unique per section.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path

from markdown_it import MarkdownIt

from app.core.export.errors import ExportError
from app.core.workspace import attachments
from app.core.workspace.diagrams import CACHE_DIR, diagram_hash
from app.core.workspace.errors import WorkspaceError

_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)((?:\s+"[^"]*")?)\)')
_LINK = re.compile(r"(?<!!)\]\(([^)\s#]+\.md)(#[^)\s]*)?\)")
_FOOTNOTE = re.compile(r"\[\^([^\]\s]+)\]")
_ATTACHED = re.compile(r"(?<!!)\[([^\]]*)\]\(allegati/([^)\s]+)\)")
_REMOTE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
MAX_LEVEL = 6


@dataclass(frozen=True)
class Item:
    """A chapter (no body) or a section of the document, in reading order."""

    kind: str  # "chapter" | "section"
    path: str
    title: str
    depth: int  # chapters: nesting level (1 = top). sections: level of the chapter holding them
    body: str = ""


@dataclass
class Combined:
    markdown: str
    assets: dict[str, Path] = field(default_factory=dict)  # name in the work folder -> source file
    warnings: list[str] = field(default_factory=list)
    anchors: dict[str, str] = field(default_factory=dict)  # item path -> anchor id


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _text_before(lines: list[str], index: int) -> bool:
    """Is there anything but blank lines and HTML comments above line ``index``?"""
    above = "\n".join(lines[:index])
    return bool(re.sub(r"<!--.*?-->", "", above, flags=re.DOTALL).strip())


def _separate_tables(body: str) -> str:
    """A blank line before every top-level table.

    The editor's Markdown parser accepts a table that follows a paragraph directly, Pandoc does
    not: it would turn the table into loose text with the cells scattered in the document.
    """
    tokens = MarkdownIt("commonmark").enable("table").parse(body)
    starts = {
        t.map[0] for t in tokens if t.type == "table_open" and t.level == 0 and t.map is not None
    }
    if not starts:
        return body
    lines = body.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        if i in starts and out and out[-1].strip():
            out.append("")
        out.append(line)
    return "\n".join(out)


def _heading_edits(body: str, level: int, title: str) -> str:
    """Shift the headings of a section under a heading of ``level``.

    A first heading, of any level, that repeats the section title and opens the text is dropped (the
    title is written by the caller).
    """
    tokens = MarkdownIt("commonmark").parse(body)
    lines = body.split("\n")
    dropped = False
    edits: dict[int, str | None] = {}
    for i, token in enumerate(tokens):
        if token.type != "heading_open" or token.map is None:
            continue
        k = int(token.tag[1])
        start, end = token.map
        content = tokens[i + 1].content
        if not dropped and _norm(content) == _norm(title) and not _text_before(lines, start):
            dropped = True
            replacement: str | None = None
        else:
            replacement = "#" * min(MAX_LEVEL, level + (k - 1 if k > 1 else 1)) + " " + content
        edits[start] = replacement
        edits.update({n: None for n in range(start + 1, end)})
    result = [edits.get(n, line) for n, line in enumerate(body.split("\n"))]
    return "\n".join(line for line in result if line is not None).lstrip("\n")


class _Rewriter:
    """Rewrites the images, links and footnote labels of one section."""

    def __init__(self, root: Path, item: Item, combined: Combined, counter: list[int]) -> None:
        self.root = root
        self.item = item
        self.combined = combined
        self.counter = counter  # shared by all sections: unique names in the work folder
        self.base = posixpath.dirname(item.path)
        self.suffix = "s" + combined.anchors[item.path].split("-")[1]

    def _warn(self, text: str) -> None:
        self.combined.warnings.append(f"{self.item.path}: {text}")

    def _add_asset(self, source: Path, prefix: str) -> str:
        self.counter[0] += 1
        name = f"{prefix}-{self.counter[0]}{source.suffix.lower()}"
        self.combined.assets[name] = source
        return name

    def csv_table(self, alt: str, url: str) -> str:
        """``![title](allegati/data.csv)`` becomes the table of the file, its title above it."""
        name = url.removeprefix(f"{attachments.ATTACHMENTS_DIR}/")
        try:
            table = attachments.markdown_table(
                attachments.read_table(attachments.attachment_file(self.root, name))
            )
        except WorkspaceError:
            table = ""
        if not table:
            self._warn(f"table file not found or empty ({url})")
            return alt
        return f"\n\n{f'*{alt}*' + chr(10) + chr(10) if alt else ''}{table}\n\n"

    def image(self, m: re.Match[str]) -> str:
        alt, url = m.group(1), m.group(2)
        if url.startswith(f"{attachments.ATTACHMENTS_DIR}/") and url.lower().endswith(".csv"):
            return self.csv_table(alt, url)
        if _REMOTE.match(url):
            self._warn(f"remote image left out ({url})")
            return alt
        source = (self.root / self.base / url).resolve()
        try:
            source.relative_to(self.root.resolve())
        except ValueError:
            self._warn(f"image outside the project ({url})")
            return alt
        if not source.is_file():
            self._warn(f"image not found ({url})")
            return alt
        return f"![{alt}]({self._add_asset(source, 'img')})"

    def link(self, m: re.Match[str]) -> str:
        target = posixpath.normpath(posixpath.join(self.base, m.group(1)))
        if target in self.combined.anchors:
            return f"](#{self.combined.anchors[target]})"
        self._warn(f"link to a section not in the export ({m.group(1)})")
        return f"]({m.group(1)})"

    def text(self, line: str) -> str:
        line = _IMAGE.sub(self.image, line)
        line = _ATTACHED.sub(lambda m: f"{m.group(1) or m.group(2)} ({m.group(2)})", line)
        line = _LINK.sub(self.link, line)
        return _FOOTNOTE.sub(lambda m: f"[^{self.suffix}-{m.group(1)}]", line)

    def diagram(self, code: str) -> str | None:
        png = self.root / CACHE_DIR / f"{diagram_hash(code)}.png"
        return f"![]({self._add_asset(png, 'diagram')})" if png.is_file() else None


def combine(root: Path, items: list[Item]) -> Combined:
    """Build the single Markdown document. Raises :class:`ExportError` if a diagram is missing."""
    prefix = {"chapter": "ch", "section": "sec"}
    combined = Combined(markdown="")
    combined.anchors = {item.path: f"{prefix[item.kind]}-{n}" for n, item in enumerate(items, 1)}
    parts: list[str] = []
    missing: list[dict[str, str]] = []
    counter = [0]

    for item in items:
        level = min(MAX_LEVEL, item.depth if item.kind == "chapter" else item.depth + 1)
        parts.append(f"{'#' * level} {item.title} {{#{combined.anchors[item.path]}}}\n")
        if item.kind == "chapter":
            continue
        body = _separate_tables(_heading_edits(item.body, level, item.title))
        rewriter = _Rewriter(root, item, combined, counter)
        verbatim: set[int] = set()
        replaced: dict[int, str | None] = {}
        for token in MarkdownIt("commonmark").parse(body):
            if token.type not in ("fence", "code_block") or token.map is None:
                continue
            start, end = token.map
            verbatim.update(range(start, end))
            if token.type == "fence" and token.info.strip() == "mermaid":
                image = rewriter.diagram(token.content)
                if image is None:
                    missing.append(
                        {
                            "section": item.path,
                            "line": str(start + 1),
                            "hash": diagram_hash(token.content),
                            "code": token.content,
                        }
                    )
                replaced[start] = image or ""
                replaced.update({n: None for n in range(start + 1, end)})
        lines: list[str] = []
        for i, line in enumerate(body.split("\n")):
            if i in replaced:
                if (text := replaced[i]) is not None:
                    lines.append(text)
            else:
                lines.append(line if i in verbatim else rewriter.text(line))
        parts.append("\n".join(lines).strip("\n") + "\n")

    if missing:
        raise ExportError(
            "diagram_missing",
            "Some diagrams have not been drawn yet: the editor draws them and the export "
            "starts again by itself.",
            {"diagrams": missing},
        )
    combined.markdown = "\n".join(parts)
    return combined
