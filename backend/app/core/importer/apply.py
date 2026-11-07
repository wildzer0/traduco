"""Apply an accepted proposal to the project files (RF-66); never runs without the author's OK.

For a modified or added segment in the official language the client's wording is kept: the stored
translation is *seeded* before the file is written (new source hash, the client's text, origin
``import``, locked), so the normal synchronisation finds nothing left to translate.
"""

from __future__ import annotations

from pathlib import Path

from app.core.segmentation.assembler import assemble
from app.core.segmentation.segmenter import segment
from app.core.translation import store
from app.core.translation.store import SegmentFile, StoredSegment
from app.core.workspace import ops
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import sha256_text
from app.core.workspace.sections import read_section, write_section

EDITABLE = {"heading", "paragraph", "list_item", "quote", "footnote", "title"}
INSERTABLE = {"paragraph", "heading", "list_item", "quote"}
REMOVABLE = {"heading", "paragraph", "list_item", "quote", "footnote"}


def _seed(
    root: Path,
    lang: str,
    rel: str,
    key: str,
    kind: str,
    source_hash: str,
    target: str,
    file_hash: str,
) -> None:
    """Record the client's text for a segment whose source is about to change."""

    def go(file: SegmentFile) -> None:
        file.source_file_hash = file_hash
        seg = file.get(key)
        if seg is None:
            seg = StoredSegment(key, source_hash, kind)
            file.segments.append(seg)
        seg.source_hash = source_hash
        seg.target = target
        seg.origin = "import"
        seg.status = "translated"
        seg.locked = True
        seg.pending_target = None
        seg.reason = ""
        seg.updated_at = store.now()

    store.update(root, lang, rel, go)


def apply_modified(
    root: Path, lang: str, rel: str, key: str, source: str, target: str | None
) -> bool:
    """Replace the source of ``key``. With ``target`` the client's translation is adopted.

    Returns True when the section still needs a synchronisation (nothing was seeded).
    """
    text, digest = read_section(root, rel)
    doc = segment(text)
    seg = doc.by_key().get(key)
    if seg is None or seg.kind not in EDITABLE:
        raise WorkspaceError("not_applicable", f"this part cannot be edited from here: {key}")
    updated = assemble(doc, {key: source})
    after = segment(updated).by_key().get(key)
    if after is None:
        raise WorkspaceError("invalid_state", "the new text does not stay a single segment")
    seeded = False
    if target is not None:
        _seed(root, lang, rel, key, seg.kind, after.hash, target, sha256_text(updated))
        seeded = store.load(root, lang, rel) is not None
    write_section(root, rel, updated, digest)
    return not seeded


def apply_added(
    root: Path, lang: str, rel: str, after_key: str | None, source: str, target: str | None
) -> bool:
    """Insert a new paragraph (or list item, or quote line) after ``after_key``."""
    text, digest = read_section(root, rel)
    doc = segment(text)
    lines = text.split("\n")
    if after_key is None:
        body_start = 0
        for index, line in enumerate(lines):
            if index > 0 and line.strip() == "---" and lines[0].strip() == "---":
                body_start = index + 1
                break
        new_lines, at = ["", source], body_start
        prefix = ""
    else:
        anchor = doc.by_key().get(after_key)
        if anchor is None or anchor.kind not in INSERTABLE:
            raise WorkspaceError("not_applicable", f"nothing can be added after {after_key}")
        prefix = anchor.prefixes[0] if anchor.kind in ("list_item", "quote") else ""
        if anchor.kind == "list_item":
            prefix = "- " if prefix.strip()[:1].isdigit() else prefix
        at = anchor.end
        new_lines = [prefix + source] if anchor.kind in ("list_item", "quote") else ["", source]
    lines[at:at] = new_lines
    updated = "\n".join(lines)
    seeded = False
    if target is not None:
        where = at + len(new_lines) - 1  # line of the new text in the updated file
        inserted = next((x for x in segment(updated).segments if x.line == where), None)
        if inserted is not None:
            # any unused key will do: the synchronisation finds the segment again by its hash
            _seed(
                root, lang, rel, "x:900000", inserted.kind, inserted.hash, target,
                sha256_text(updated),
            )  # fmt: skip
            seeded = store.load(root, lang, rel) is not None
    write_section(root, rel, updated, digest)
    return not seeded


def apply_deleted(root: Path, rel: str, key: str) -> None:
    text, digest = read_section(root, rel)
    doc = segment(text)
    seg = doc.by_key().get(key)
    if seg is None or seg.kind not in REMOVABLE:
        raise WorkspaceError("not_applicable", f"this part cannot be removed from here: {key}")
    lines = text.split("\n")
    del lines[seg.line : seg.end]
    # do not leave two blank lines where the paragraph was
    if (
        seg.line < len(lines)
        and seg.line > 0
        and not lines[seg.line].strip()
        and not lines[seg.line - 1].strip()
    ):
        del lines[seg.line]
    write_section(root, rel, "\n".join(lines), digest)


def apply_chapter_title(root: Path, path: str, title: str) -> dict[str, str]:
    """Rename a chapter (its folder follows the new title)."""
    return ops.rename(root, path, title)
