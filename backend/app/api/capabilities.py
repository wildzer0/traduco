"""``/api/capabilities``: what this installation can do, for the interface (RF-74, RF-79).

The launcher writes the progress of the model download to ``$TRADUCO_RUNTIME_DIR/model.json``;
Pandoc and LibreOffice are looked for the same way the export looks for them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.export import office
from app.core.export.errors import ExportError
from app.core.export.pandoc import find_pandoc

router = APIRouter(tags=["capabilities"])


def model_download() -> dict[str, Any]:
    """State of the model download: none | unavailable | downloading | ready | error."""
    runtime = os.environ.get("TRADUCO_RUNTIME_DIR")
    if not runtime:
        return {"state": "none"}
    try:
        data = json.loads((Path(runtime) / "model.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "none"}
    if not isinstance(data, dict):
        return {"state": "none"}
    return {
        "state": str(data.get("state", "none")),
        "model": str(data.get("model", "")),
        "completed": int(data.get("completed") or 0),
        "total": int(data["total"]) if data.get("total") else None,
        "error": str(data.get("error", "")),
    }


@router.get("/capabilities")
def capabilities() -> dict[str, Any]:
    try:
        find_pandoc()
        pandoc = True
    except ExportError:
        pandoc = False
    has_office = office.find_soffice() is not None
    formats = ["docx"] if pandoc else []
    if pandoc and has_office:
        formats += ["pdf", "odt"]
    return {
        "pandoc": {"available": pandoc},
        "libreoffice": {"available": has_office},
        "formats": formats,
        "model": model_download(),
    }
