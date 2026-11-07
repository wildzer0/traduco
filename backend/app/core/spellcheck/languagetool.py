"""Spelling and grammar of the source text with a self-hosted LanguageTool (RF-16, optional).

Off unless the author sets ``TRADUCO_LANGUAGETOOL_URL`` to *their own* server (the compose profile
``languagetool`` starts one next to the app). Nothing is sent anywhere else. The text goes to
LanguageTool as annotated data - words as text, Markdown syntax as markup - so code, links and
fields are not flagged and every offset refers to the segment exactly as it is written.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.workspace.errors import WorkspaceError

TIMEOUT = 20.0
# LanguageTool wants a variant for some languages
VARIANTS = {"en": "en-US", "de": "de-DE", "pt": "pt-PT", "nl": "nl", "ca": "ca-ES", "sv": "sv"}
_MARKUP = re.compile(
    r"`[^`]*`|!?\[|\]\([^)]*\)|\]\[[^\]]*\]|\[\^[^\]]+\]|\{\{[^}]*\}\}|</?[A-Za-z][^>]*>"
    r"|\*\*|__|~~|\*|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])|https?://\S+"
)


def annotate(source: str) -> list[dict[str, str]]:
    """The source as LanguageTool's ``annotation`` list: ``{"text"}`` and ``{"markup"}`` pieces."""
    parts: list[dict[str, str]] = []
    pos = 0
    for m in _MARKUP.finditer(source):
        if m.start() > pos:
            parts.append({"text": source[pos : m.start()]})
        parts.append({"markup": m.group(0)})
        pos = m.end()
    if pos < len(source):
        parts.append({"text": source[pos:]})
    return parts


def _base(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise WorkspaceError("invalid_state", "TRADUCO_LANGUAGETOOL_URL must be an http(s) address")
    return url.rstrip("/")


async def available(url: str) -> bool:
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            return (await client.get(f"{_base(url)}/v2/languages")).status_code == 200
    except (httpx.HTTPError, WorkspaceError):
        return False


async def check(url: str, language: str, source: str) -> list[dict[str, Any]]:
    """Issues in one segment: offset, length, message, rule and the suggested replacements."""
    if not source.strip():
        return []
    data = {
        "language": VARIANTS.get(language, language),
        "data": json.dumps({"annotation": annotate(source)}, ensure_ascii=False),
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f"{_base(url)}/v2/check", data=data)
    except httpx.HTTPError as exc:
        raise WorkspaceError("model_refused", f"LanguageTool is not reachable: {exc}") from exc
    if response.status_code != 200:
        raise WorkspaceError(
            "model_refused", f"LanguageTool refused the text: {response.text.strip()[:200]}"
        )
    found = []
    for match in response.json().get("matches", []):
        found.append(
            {
                "offset": int(match["offset"]),
                "length": int(match["length"]),
                "message": str(match.get("message", "")),
                "rule": str(match.get("rule", {}).get("id", "")),
                "category": str(match.get("rule", {}).get("issueType", "")),
                "replacements": [r["value"] for r in match.get("replacements", [])[:5]],
            }
        )
    return found
