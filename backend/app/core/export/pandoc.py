"""Run Pandoc as an external program (ADR-008: never linked, only invoked)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from app.core.export.errors import ExportError

# commonmark + the extensions Traduco's Markdown uses (tables, footnotes, heading ids). Raw HTML and
# raw OpenXML are switched off: a section must never be able to inject markup into the Word file.
INPUT_FORMAT = "commonmark_x-raw_html-raw_attribute-smart+implicit_figures"
TIMEOUT_SECONDS = 180


def find_pandoc(configured: Path | None = None) -> Path:
    """Pandoc to use: the configured one, ``$TRADUCO_PANDOC``, the launcher's copy, then PATH."""
    candidates: list[Path | None] = [configured]
    if env := os.environ.get("TRADUCO_PANDOC"):
        candidates.append(Path(env))
    repo = Path(__file__).resolve().parents[4]
    candidates.append(repo / ".runtime" / "pandoc" / "bin" / "pandoc")
    candidates.append(repo / ".runtime" / "pandoc" / "pandoc.exe")
    if on_path := shutil.which("pandoc"):
        candidates.append(Path(on_path))
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise ExportError(
        "pandoc_missing",
        "Pandoc was not found. Install Pandoc 3.x or set TRADUCO_PANDOC to its path.",
    )


def run_pandoc(
    pandoc: Path,
    markdown: Path,
    output: Path,
    *,
    reference_doc: Path | None,
    resource_dir: Path,
) -> None:
    args = [
        str(pandoc),
        "--from", INPUT_FORMAT,
        "--to", "docx",
        "--wrap=none",
        f"--resource-path={resource_dir}",
        "--output", str(output),
    ]  # fmt: skip
    if reference_doc is not None:
        args.append(f"--reference-doc={reference_doc}")
    args.append(str(markdown))
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=resource_dir,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExportError("pandoc_failed", "Pandoc took too long and was stopped.") from exc
    if result.returncode != 0:
        raise ExportError("pandoc_failed", f"Pandoc failed: {result.stderr.strip()[:500]}")


def default_reference_doc(pandoc: Path, target: Path) -> Path:
    """Pandoc's own reference.docx, used when the project has no template."""
    result = subprocess.run(
        [str(pandoc), "--print-default-data-file", "reference.docx"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise ExportError("pandoc_failed", "Pandoc could not provide its default template.")
    target.write_bytes(result.stdout)
    return target
