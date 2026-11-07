"""Section check: model review of every segment plus optional requirement rules (RF-88)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.companion import rules
from app.core.companion.improve import AssistContext
from app.core.segmentation.models import Segment, SegmentedDocument
from app.core.segmentation.protect import PlaceholderError, protect, restore
from app.core.translation import prompts
from app.core.translation.translator import LANGUAGES, Chat, _clean
from app.core.workspace.fsio import atomic_write_text, sha256_text

PROMPT_VERSION = "check@1"
CATEGORIES = {"grammar", "clarity", "ambiguity", "style", "terminology"}
MIN_CHARS = 25  # shorter segments (headings, labels) are not worth a model call
MAX_PER_SEGMENT = 3


@dataclass
class Suggestion:
    id: str
    key: str
    source_hash: str
    category: str
    message: str
    suggestion: str
    origin: str  # "model" | "rule" | "guide"
    status: str = "open"  # "open" | "dismissed" | "applied"


def _id(key: str, source_hash: str, message: str) -> str:
    return hashlib.sha256(f"{key}|{source_hash}|{message}".encode()).hexdigest()[:12]


def parse_issues(reply: str) -> list[dict[str, Any]]:
    """The JSON array in a model reply; anything unreadable counts as "no problems"."""
    text = _clean(reply)
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return []
    return [d for d in data if isinstance(d, dict) and isinstance(d.get("message"), str)]


async def _check_segment(client: Chat, seg: Segment, ctx: AssistContext) -> list[Suggestion]:
    protected = protect(seg.source)
    extra = ""
    if ctx.glossary:
        extra += "\n- Controlled terms (never flag them, never change them): " + ", ".join(
            e.sorgente for e in ctx.glossary
        )
    system = prompts.load("check", 1).format(
        language=LANGUAGES.get(ctx.language, ctx.language), extra_rules=extra
    )
    reply = await client.chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"<source>{protected.text}</source>"},
        ],
        temperature=0.1,
        max_tokens=max(512, 4 * len(seg.source)),
    )
    out: list[Suggestion] = []
    for issue in parse_issues(reply)[:MAX_PER_SEGMENT]:
        category = str(issue.get("category", "style")).lower()
        message = str(issue["message"]).strip()
        suggestion = str(issue.get("suggestion") or "").strip()
        if suggestion:
            try:
                suggestion = restore(suggestion, protected)
            except PlaceholderError:
                suggestion = ""  # an unsafe fix is dropped, the remark stays
        if suggestion == seg.source:
            suggestion = ""
        if message:
            out.append(
                Suggestion(
                    _id(seg.key, seg.hash, message),
                    seg.key,
                    seg.hash,
                    category if category in CATEGORIES else "style",
                    message,
                    suggestion,
                    "model",
                )  # fmt: skip
            )
    return out


async def check_guide(client: Chat, doc: SegmentedDocument, ctx: AssistContext) -> list[Suggestion]:
    """Does the section say what its skeleton guide asks for? Remarks hang on the first segment."""
    body = "\n\n".join(s.source for s in doc.segments if s.kind != "title")
    anchor = next((s for s in doc.segments if s.kind != "title"), None)
    if anchor is None or len(body) < 40 or not ctx.guide:
        return []
    system = prompts.load("guide", 1).format(
        title=ctx.section_title or "?",
        guide=ctx.guide,
        language=LANGUAGES.get(ctx.language, ctx.language),
    )
    reply = await client.chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"<source>{body[:6000]}</source>"},
        ],
        temperature=0.1,
        max_tokens=1024,
    )
    return [
        Suggestion(
            _id(anchor.key, anchor.hash, str(i["message"])),
            anchor.key,
            anchor.hash,
            "coverage",
            str(i["message"]).strip(),
            "",
            "guide",
        )  # fmt: skip
        for i in parse_issues(reply)[:5]
    ]


async def check_section(
    client: Chat,
    doc: SegmentedDocument,
    ctx: AssistContext,
    *,
    requirement_rules: bool = False,
    concurrency: int = 2,
) -> list[Suggestion]:
    """Review every segment; segments are independent so two run at a time."""
    semaphore = asyncio.Semaphore(concurrency)
    by_key = doc.by_key()
    candidates = [s for s in doc.segments if s.kind != "title" and len(s.source) >= MIN_CHARS]

    async def one(seg: Segment) -> list[Suggestion]:
        async with semaphore:
            return await _check_segment(client, seg, ctx)

    results = await asyncio.gather(*(one(s) for s in candidates), check_guide(client, doc, ctx))
    found = [item for chunk in results for item in chunk]
    if requirement_rules:
        for f in rules.check_requirements(list(doc.segments), ctx.language):
            seg = by_key[f.key]
            found.append(
                Suggestion(
                    _id(f.key, seg.hash, f.message),
                    f.key,
                    seg.hash,
                    f.category,
                    f.message,
                    "",
                    "rule",
                )
            )
    order = {s.key: i for i, s in enumerate(doc.segments)}
    return sorted(found, key=lambda s: (order.get(s.key, 0), s.origin))


# --- persistence: .traduco/cache/suggestions/<section>.json (git-ignored, ADR-030) ---------------


def _path(root: Path, rel: str) -> Path:
    return root / ".traduco" / "cache" / "suggestions" / (str(Path(rel).with_suffix("")) + ".json")


def save(root: Path, rel: str, text: str, items: list[Suggestion]) -> None:
    payload = {"source_file_hash": sha256_text(text), "items": [asdict(i) for i in items]}
    atomic_write_text(_path(root, rel), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load(root: Path, rel: str, doc: SegmentedDocument) -> list[Suggestion]:
    """Stored suggestions that still apply: the segment exists and has not changed since."""
    try:
        data = json.loads(_path(root, rel).read_text(encoding="utf-8"))
        items = [Suggestion(**i) for i in data["items"]]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    by_key = doc.by_key()
    return [i for i in items if i.key in by_key and by_key[i.key].hash == i.source_hash]


def set_status(
    root: Path, rel: str, doc: SegmentedDocument, suggestion_id: str, status: str
) -> None:
    items = load(root, rel, doc)
    for i in items:
        if i.id == suggestion_id:
            i.status = status
    save(root, rel, doc.text, items)


GUIDE_NOTE = re.compile(r"<!--\s*Guida:\s*(.*?)\s*-->", re.DOTALL)
