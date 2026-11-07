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


# A LibreOffice Basic macro, installed in a throw-away profile. A plain `--convert-to` leaves the
# table of contents as Word saved it (a hint text); loading the file in the office, updating every
# index and field and then storing it gives the PDF/ODT a real table of contents.
_MACRO = """\
Sub ConvertUpdating(sIn As String, sOut As String, sFilter As String)
  Dim aLoad(0) As New com.sun.star.beans.PropertyValue
  aLoad(0).Name = "Hidden"
  aLoad(0).Value = True
  Dim oDoc As Object
  oDoc = StarDesktop.loadComponentFromURL(sIn, "_blank", 0, aLoad())
  Dim oIndexes As Object
  oIndexes = oDoc.getDocumentIndexes()
  Dim i As Integer
  For i = 0 To oIndexes.getCount() - 1
    oIndexes.getByIndex(i).update()
  Next i
  oDoc.getTextFields().refresh()
  For i = 0 To oIndexes.getCount() - 1
    oIndexes.getByIndex(i).update()
  Next i
  Dim aStore(0) As New com.sun.star.beans.PropertyValue
  aStore(0).Name = "FilterName"
  aStore(0).Value = sFilter
  oDoc.storeToURL(sOut, aStore())
  oDoc.close(True)
End Sub
"""
_XLC = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<library:libraries xmlns:library="http://openoffice.org/2000/library" '
    'xmlns:xlink="http://www.w3.org/1999/xlink">'
    '<library:library library:name="Standard" xlink:href="$(USER)/basic/Standard/script.xlb/" '
    'xlink:type="simple" library:link="false"/></library:libraries>\n'
)
_DOCTYPE = (
    '<!DOCTYPE library:library PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" '
    '"library.dtd">\n'
)
_XLB = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    + _DOCTYPE
    + '<library:library xmlns:library="http://openoffice.org/2000/library" library:name="Standard" '
    'library:readonly="false" library:passwordprotected="false">'
    '<library:element library:name="Module1"/></library:library>\n'
)
_DLB = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    + _DOCTYPE
    + '<library:library xmlns:library="http://openoffice.org/2000/library" library:name="Standard" '
    'library:readonly="false" library:passwordprotected="false"/>\n'
)
_MODULE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" '
    '"module.dtd">\n'
    '<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" '
    'script:language="StarBasic">'
    + _MACRO.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    + "</script:module>\n"
)
FILTERS = {"pdf": "writer_pdf_Export", "odt": "writer8"}


def _install_macro(profile: Path) -> None:
    basic = profile / "user" / "basic"
    (basic / "Standard").mkdir(parents=True)
    (basic / "script.xlc").write_text(_XLC, encoding="utf-8")
    (basic / "Standard" / "script.xlb").write_text(_XLB, encoding="utf-8")
    (basic / "Standard" / "dialog.xlb").write_text(_DLB, encoding="utf-8")
    (basic / "Standard" / "Module1.xba").write_text(_MODULE, encoding="utf-8")


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise ExportError("office_failed", "LibreOffice took too long and was stopped.") from exc


#: What the last conversions did, for diagnosing a LibreOffice that ignores the macro (see tests).
DIAGNOSTICS: list[str] = []


def _macro_calls(docx: Path, produced: Path, fmt: str) -> list[str]:
    """The ways a `macro:` URL can carry the three arguments; LibreOffice versions differ."""
    arguments = [docx.resolve().as_uri(), produced.resolve().as_uri(), FILTERS[fmt]]
    quoted = ",".join(f'"{a}"' for a in arguments)
    plain = ",".join(arguments)
    return [
        f"macro:///Standard.Module1.ConvertUpdating({quoted})",
        f"macro:///Standard.Module1.ConvertUpdating({plain})",
    ]


def convert(docx: Path, fmt: str, outdir: Path, *, update_fields: bool = True) -> Path:
    """Convert to ``pdf`` or ``odt``; returns the file. Runs with a throw-away profile.

    With ``update_fields`` the table of contents and the fields are refreshed first (macro above);
    if the macro cannot run on this installation the plain conversion is used instead.
    """
    soffice = find_soffice()
    if soffice is None:
        raise ExportError(
            "office_missing", "LibreOffice was not found: PDF and ODT export need it."
        )
    outdir.mkdir(parents=True, exist_ok=True)
    produced = outdir / f"{docx.stem}.{fmt}"
    produced.unlink(missing_ok=True)
    base = [str(soffice), "--headless", "--norestore", "--nolockcheck"]
    result: subprocess.CompletedProcess[str] | None = None
    if update_fields and fmt in FILTERS:
        for call in _macro_calls(docx, produced, fmt):
            with tempfile.TemporaryDirectory(prefix="traduco-lo-") as profile:
                _install_macro(Path(profile))
                result = _run([*base, f"-env:UserInstallation={Path(profile).as_uri()}", call])
            DIAGNOSTICS.append(
                f"macro {call[-60:]!r}: exit {result.returncode}, file {produced.is_file()}, "
                f"stderr {result.stderr.strip()[:200]!r}, stdout {result.stdout.strip()[:200]!r}"
            )
            if produced.is_file():
                break
    if not produced.is_file():
        with tempfile.TemporaryDirectory(prefix="traduco-lo-") as profile:
            result = _run(
                [
                    *base,
                    f"-env:UserInstallation={Path(profile).as_uri()}",
                    "--convert-to",
                    fmt,
                    "--outdir",
                    str(outdir),
                    str(docx),
                ]  # fmt: skip
            )
        DIAGNOSTICS.append(f"plain conversion used: exit {result.returncode}")
    if result is None or result.returncode != 0 or not produced.is_file():
        raise ExportError(
            "office_failed",
            "LibreOffice could not convert the file: "
            + (result.stderr.strip()[:300] if result else ""),
        )
    return produced
