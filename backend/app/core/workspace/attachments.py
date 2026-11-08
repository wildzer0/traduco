"""Files attached to a project live in ``allegati/``; a CSV can be shown as a table."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_bytes, sha256_bytes
from app.core.workspace.ordering import slugify

ATTACHMENTS_DIR = "allegati"
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
MAX_TABLE_ROWS = 2000
MAX_TABLE_COLUMNS = 40
#: files a browser or the system would run: never stored
FORBIDDEN = {
    ".exe", ".bat", ".cmd", ".com", ".msi", ".sh", ".js", ".mjs", ".vbs", ".ps1", ".jar",
    ".html", ".htm", ".xhtml", ".svg", ".scr", ".lnk", ".dll", ".so", ".app",
}  # fmt: skip


def folder(root: Path) -> Path:
    return root / ATTACHMENTS_DIR


def safe_name(filename: str) -> str:
    """A file name without folders or odd characters, extension kept (lower case)."""
    path = Path(filename.replace("\\", "/").rsplit("/", 1)[-1])
    ext = re.sub(r"[^a-z0-9.]", "", path.suffix.lower())
    stem = slugify(path.stem) if path.stem.strip() else ""
    return f"{stem if stem and stem != 'senza-titolo' else 'allegato'}{ext}"


def save_attachment(root: Path, filename: str, data: bytes) -> str:
    """Store ``data``; returns the path relative to the project (``allegati/nome.ext``)."""
    if not data:
        raise WorkspaceError("invalid_path", "the file is empty")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise WorkspaceError("too_large", "attachments are limited to 50 MB")
    name = safe_name(filename)
    if Path(name).suffix in FORBIDDEN:
        raise WorkspaceError("invalid_path", "this kind of file cannot be attached")
    target = folder(root)
    digest = sha256_bytes(data)
    candidate, n = target / name, 1
    while candidate.exists():
        if sha256_bytes(candidate.read_bytes()) == digest:
            return candidate.relative_to(root).as_posix()
        n += 1
        candidate = target / f"{Path(name).stem}-{n}{Path(name).suffix}"
    atomic_write_bytes(candidate, data)
    return candidate.relative_to(root).as_posix()


def list_attachments(root: Path) -> list[dict[str, object]]:
    base = folder(root)
    if not base.is_dir():
        return []
    return [
        {"name": f.name, "path": f"{ATTACHMENTS_DIR}/{f.name}", "size": f.stat().st_size}
        for f in sorted(base.iterdir())
        if f.is_file() and not f.name.startswith(".")
    ]


def attachment_file(root: Path, name: str) -> Path:
    if "/" in name or "\\" in name or name.startswith("."):
        raise WorkspaceError("invalid_path", "invalid attachment name")
    file = folder(root) / name
    if not file.is_file():
        raise WorkspaceError("not_found", f"attachment not found: {name}")
    return file


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def read_table(file: Path) -> list[list[str]]:
    """The rows of a CSV file (first row = header). Delimiter and encoding are guessed."""
    if file.suffix.lower() != ".csv":
        raise WorkspaceError("invalid_path", "not a CSV file")
    text = _decode(file.read_bytes())
    sample = text[:4096]
    try:
        dialect: type[csv.Dialect] | csv.Dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [
        [cell.strip() for cell in row[:MAX_TABLE_COLUMNS]]
        for row in csv.reader(io.StringIO(text), dialect)
        if any(cell.strip() for cell in row)
    ][: MAX_TABLE_ROWS + 1]
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


def markdown_table(rows: list[list[str]]) -> str:
    """A pipe table; the first row is the header."""
    if not rows or not rows[0]:
        return ""

    def cell(text: str) -> str:
        return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")

    head, *body = rows
    lines = [
        "| " + " | ".join(cell(c) for c in head) + " |",
        "|" + "|".join("---" for _ in head) + "|",
        *("| " + " | ".join(cell(c) for c in r) + " |" for r in body),
    ]
    return "\n".join(lines)
