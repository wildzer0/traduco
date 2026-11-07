"""Requirement identifiers and the references between them (RF-84).

A requirement is *defined* where a paragraph, list item, heading or table cell starts with an
identifier (``FOO-REQ-00042``, optionally in bold or brackets); every other mention of an
identifier is a *reference*. No special syntax: what the authors already write is what is checked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.segmentation.segmenter import segment
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.sections import read_section
from app.core.workspace.tree import build_tree

# groups of capitals/digits joined by dashes, ending in 3+ digits: FOO-REQ-00042
ID = re.compile(
    r"(?<![A-Za-z0-9_-])([A-Z][A-Z0-9]{1,15}(?:-[A-Z][A-Z0-9]{0,15})*-\d{3,})(?![A-Za-z0-9_-])"
)
_START = re.compile(r"^[\s*_\[#>(`]*" + ID.pattern)


@dataclass
class Requirement:
    id: str
    path: str
    key: str
    text: str
    referenced_by: list[dict[str, str]] = field(default_factory=list)


def _sections(root: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def visit(nodes: list[Any]) -> None:
        for node in nodes:
            if node.kind == "section":
                out.append((node.path, node.title))
            visit(node.children)

    visit(build_tree(root))
    return out


def scan(root: Path) -> dict[str, Any]:
    """Definitions, references and the problems found (duplicates, dangling references, unused)."""
    defined: dict[str, list[Requirement]] = {}
    mentions: list[tuple[str, str, str, str]] = []  # (id, path, key, section title)
    for path, title in _sections(root):
        try:
            text = read_section(root, path)[0]
        except WorkspaceError:
            continue
        for seg in segment(text).segments:
            if seg.kind == "title":
                continue
            start = _START.match(seg.source)
            first = start.group(1) if start else None
            if first:
                defined.setdefault(first, []).append(Requirement(first, path, seg.key, seg.source))
            skipped = False
            for match in ID.finditer(seg.source):
                if first and not skipped and match.start(1) == start.start(1):  # type: ignore[union-attr]
                    skipped = True  # the defining occurrence itself
                    continue
                mentions.append((match.group(1), path, seg.key, title))
    problems: list[dict[str, str]] = []
    # a mention is only "undefined" inside a family the project really uses (FOO-REQ-...), so
    # standards and other codes (ISO-9001, RFC-2119) are left alone
    families = {rid.rsplit("-", 1)[0] for rid in defined}
    for rid, items in defined.items():
        for extra in items[1:]:
            problems.append({"kind": "duplicate", "id": rid, "path": extra.path, "key": extra.key})
    for rid, path, key, _ in mentions:
        if rid in defined:
            defined[rid][0].referenced_by.append({"path": path, "key": key})
        elif rid.rsplit("-", 1)[0] in families:
            problems.append({"kind": "undefined", "id": rid, "path": path, "key": key})
    # a reference from a requirement to itself, or two mentions in one segment, count once
    for items in defined.values():
        first = items[0]
        seen: set[tuple[str, str]] = set()
        unique = []
        for ref in first.referenced_by:
            marker = (ref["path"], ref["key"])
            if marker not in seen and marker != (first.path, first.key):
                seen.add(marker)
                unique.append(ref)
        first.referenced_by = unique
        if not unique:
            problems.append(
                {"kind": "unreferenced", "id": first.id, "path": first.path, "key": first.key}
            )
    requirements = [r for items in defined.values() for r in items[:1]]
    return {
        "requirements": [r.__dict__ for r in requirements],
        "problems": sorted(problems, key=lambda p: (p["kind"], p["id"])),
    }
