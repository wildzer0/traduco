"""Two-column export: the source on the left, the translation on the right (RF-64).

Each section becomes one table with a row per segment, so a reviewer who reads only one of the
two languages can follow the other. Inline formatting, links and images stay (they are Markdown in
a cell); what cannot live in a table cell - code blocks, tables, diagrams - is left out and the
export says so.
"""

from __future__ import annotations

from typing import Any

from app.core.segmentation.segmenter import segment

SKIPPED = {"table_cell", "table_header", "footnote", "title"}


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "\\|").split())


def _wrap(kind: str, text: str) -> str:
    if kind == "heading":
        return f"**{text}**"
    if kind == "list_item":
        return f"• {text}"
    if kind == "quote":
        return f"“{text}”"
    return text


def build_body(source_text: str, targets: dict[str, str], src_lang: str, tgt_lang: str) -> str:
    """The Markdown table of one section; ``targets`` maps a segment key to its translation."""
    lines = [f"| {src_lang} | {tgt_lang} |", "| --- | --- |"]
    for seg in segment(source_text).segments:
        if seg.kind in SKIPPED:
            continue
        left = _cell(_wrap(seg.kind, seg.source))
        translated = targets.get(seg.key, "")
        right = _cell(_wrap(seg.kind, translated)) if translated else "…"
        lines.append(f"| {left} | {right} |")
    return "\n".join(lines) + "\n"


def targets_of(view: dict[str, Any]) -> dict[str, str]:
    return {row["key"]: row["target"] for row in view["segments"] if row.get("target")}
