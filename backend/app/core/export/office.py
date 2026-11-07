"""LibreOffice, only as an external program (ADR-008, ADR-005): convert a DOCX to PDF or ODT."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from app.core.export.errors import ExportError

TIMEOUT_SECONDS = 180


def _standard_locations() -> list[Path]:
    if sys.platform == "win32":
        bases = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")]
        return [Path(b) / "LibreOffice" / "program" / "soffice.exe" for b in bases if b]
    if sys.platform == "darwin":
        return [Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")]
    return []


def find_soffice() -> Path | None:
    """LibreOffice: ``$TRADUCO_SOFFICE``, ``soffice`` on PATH, then the standard install places.

    ``None`` when it is not installed; it is never installed by Traduco (docs/02).
    """
    configured = os.environ.get("TRADUCO_SOFFICE")
    if configured and Path(configured).is_file():
        return Path(configured)
    for name in ("soffice", "libreoffice"):
        if found := shutil.which(name):
            return Path(found)
    return next((p for p in _standard_locations() if p.is_file()), None)


def convert(docx: Path, fmt: str, outdir: Path) -> Path:
    """Convert with a throw-away profile, so runs never clash with each other or the user's own."""
    soffice = find_soffice()
    if soffice is None:
        raise ExportError(
            "office_missing", "LibreOffice was not found: PDF and ODT export need it."
        )
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="traduco-lo-") as profile:
        args = [
            str(soffice), "--headless", "--norestore", "--nolockcheck",
            f"-env:UserInstallation={Path(profile).as_uri()}",
            "--convert-to", fmt, "--outdir", str(outdir), str(docx),
        ]  # fmt: skip
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise ExportError(
                "office_failed", "LibreOffice took too long and was stopped."
            ) from exc
    produced = outdir / f"{docx.stem}.{fmt.split(':')[0]}"
    if result.returncode != 0 or not produced.is_file():
        raise ExportError(
            "office_failed",
            f"LibreOffice could not convert the file: {result.stderr.strip()[:300]}",
        )
    return produced
