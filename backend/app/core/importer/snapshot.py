"""What an export recorded about its content, so a revised copy can be compared with it.

``.traduco/export/<id>/map.json`` holds, in reading order, one *unit* for each piece of text that
ends up in the Word file: chapter titles, section titles and every segment (paragraphs, list items,
table cells, quotes, footnotes). Units that come from a section carry the section path and the
segment key, which are the same in the source file and in its translation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.segmentation.segmenter import segment
from app.core.workspace.errors import WorkspaceError

from .align import plain


@dataclass(frozen=True)
class Part:
    """A chapter or a section as exported: its text in the exported language and in the source."""

    kind: str  # chapter | section
    path: str
    title: str
    exported: str = ""
    source: str = ""


def build_units(parts: list[Part]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for part in parts:
        if part.kind == "chapter":
            units.append(
                {
                    "section": part.path,
                    "key": None,
                    "kind": "chapter",
                    "text": part.title,
                    "source_hash": None,
                }  # fmt: skip
            )
            continue
        shown = segment(part.exported).by_key()
        origin = segment(part.source).by_key() if part.source else {}
        title_key = "fm:title" if "fm:title" in shown else None
        dropped: str | None = None
        for seg in shown.values():
            if seg.kind == "title":
                continue
            # combine.py drops a first heading that repeats the section title: it is the title
            if seg.kind == "heading" and plain(seg.source) == plain(part.title):
                dropped = seg.key
                title_key = title_key or seg.key
            break
        units.append(
            {
                "section": part.path,
                "key": title_key,
                "kind": "title",
                "text": part.title,
                "source_hash": origin[title_key].hash if title_key in origin else None,
            }  # fmt: skip
        )
        for seg in shown.values():
            if seg.kind == "title" or seg.key == dropped:
                continue
            units.append(
                {
                    "section": part.path,
                    "key": seg.key,
                    "kind": seg.kind,
                    "text": seg.source,
                    "source_hash": origin[seg.key].hash if seg.key in origin else None,
                }  # fmt: skip
            )
    return units


def snapshots_dir(root: Path) -> Path:
    return root / ".traduco" / "export"


def load_snapshot(root: Path, snapshot_id: str | None) -> dict[str, Any]:
    """The snapshot ``snapshot_id`` or, if ``None``, the most recent one that has units."""
    folder = snapshots_dir(root)
    candidates = (
        sorted((p for p in folder.glob("*/map.json")), reverse=True) if folder.is_dir() else []
    )
    for path in candidates:
        if snapshot_id is not None and path.parent.name != snapshot_id:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if "units" in data:
            data["id"] = path.parent.name
            return data  # type: ignore[no-any-return]
        if snapshot_id is not None:
            break
    raise WorkspaceError(
        "no_snapshot",
        "There is no export to compare with: "
        "export the document first, then import the revised copy.",
    )
