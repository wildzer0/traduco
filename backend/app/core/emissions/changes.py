"""The change table between two issues (RF-81): the model summarises, the author corrects."""

from __future__ import annotations

from typing import Any

from app.core.translation.llm_client import LlmError
from app.core.translation.translator import LANGUAGES, Chat

PROMPT_VERSION = "changes@1"
MAX_CHARS = 1800
SYSTEM = (
    "You write one line of a document revision table. You are given what was removed and what "
    "was added in one section of a technical document. Reply with ONE short sentence in {language} "
    "saying what changed, in plain words, without quoting long passages and without any preface. "
    "Do not mention words, diffs or the tool."
)
FALLBACK = {
    "it": {
        "added": "Sezione aggiunta",
        "removed": "Sezione eliminata",
        "modified": "Modificata ({plus} parole aggiunte, {minus} rimosse)",
    },
    "en": {
        "added": "Section added",
        "removed": "Section removed",
        "modified": "Changed ({plus} words added, {minus} removed)",
    },
}


def fallback(status: str, plus: int, minus: int, language: str) -> str:
    table = FALLBACK.get(language, FALLBACK["en"])
    return table[status].format(plus=plus, minus=minus)


def _excerpt(ops: list[dict[str, str]], kind: str) -> str:
    text = " … ".join(o["text"].strip() for o in ops if o["op"] == kind and o["text"].strip())
    return text[:MAX_CHARS]


async def summarise(
    client: Chat | None, compared: dict[str, Any], language: str
) -> list[dict[str, Any]]:
    """One row per changed section; without a model (or when it fails) a counted fallback."""
    rows: list[dict[str, Any]] = []
    online = client is not None
    for section in compared["sections"]:
        plus, minus = section["words_added"], section["words_removed"]
        summary = fallback(section["status"], plus, minus, language)
        if online and client is not None and section["status"] == "modified":
            user = (
                f"Section: {section['title']}\n\nREMOVED:\n{_excerpt(section['ops'], 'del') or '-'}"
                f"\n\nADDED:\n{_excerpt(section['ops'], 'ins') or '-'}"
            )
            try:
                reply = await client.chat(
                    [
                        {
                            "role": "system",
                            "content": SYSTEM.format(language=LANGUAGES.get(language, language)),
                        },
                        {"role": "user", "content": user},
                    ],
                    temperature=0.2,
                    max_tokens=120,
                )
                text = " ".join(reply.split()).strip(" \"'")
                if text:
                    summary = text
            except LlmError:
                online = False  # do not wait for a dead server once per section
        rows.append(
            {
                "path": section["path"],
                "title": section["title"],
                "status": section["status"],
                "summary": summary,
            }
        )
    return rows


def describe(changes: list[dict[str, Any]]) -> str:
    """The text for the revision table: one clause per section."""
    return "; ".join(f"{c['title']}: {c['summary'].rstrip('.')}" for c in changes if c["summary"])
