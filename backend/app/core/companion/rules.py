"""Deterministic checks for requirement statements (RF-88, RF-84): no model, no surprises.

Checked per sentence: one prescription only, weak modal verbs, vague words. They are opt-in
because ordinary prose would trigger them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.segmentation.models import Segment

_STRONG = {
    "en": r"\b(shall|must)\b",
    "it": r"\b(deve|devono|dovr[àa]|dovranno|deve essere|devono essere)\b",
}
_WEAK = {
    "en": r"\b(should|may|might|could|will|ought)\b",
    "it": r"\b(dovrebbe|dovrebbero|potrebbe|potrebbero|pu[òo]|possono|sar[àa]|saranno)\b",
}
_VAGUE = {
    "en": [
        "adequate", "appropriate", "sufficient", "as needed", "if possible", "where possible",
        "where applicable", "as appropriate", "etc", "and/or", "user-friendly", "fast",
        "quickly", "easy", "flexible", "minimal", "maximum possible",
    ],
    "it": [
        "adeguato", "adeguata", "adeguati", "appropriato", "appropriata", "sufficiente",
        "se necessario", "se possibile", "ove possibile", "ove applicabile", "ecc", "e/o",
        "semplice da usare", "veloce", "rapido", "rapidamente", "flessibile", "opportuno",
        "il più possibile",
    ],
}  # fmt: skip
_SENTENCE = re.compile(r"(?<=[.!?;])\s+|\n+")
_REQ_ID = re.compile(r"^\s*#?[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+")


@dataclass(frozen=True)
class Finding:
    key: str
    category: str
    message: str


def _lang(code: str) -> str:
    return code if code in _STRONG else "en"


def check_requirements(segments: list[Segment], language: str) -> list[Finding]:
    """Findings for paragraphs, list items and cells; headings and the title are skipped."""
    lang = _lang(language)
    strong = re.compile(_STRONG[lang], re.IGNORECASE)
    weak = re.compile(_WEAK[lang], re.IGNORECASE)
    vague = [(w, re.compile(rf"(?<!\w){re.escape(w)}(?!\w)", re.IGNORECASE)) for w in _VAGUE[lang]]
    found: list[Finding] = []
    for seg in segments:
        if (
            seg.kind in ("title", "heading", "table_header")
            or _REQ_ID.match(seg.source)
            and len(seg.source.split()) == 1
        ):
            continue
        flagged: set[str] = set()
        for sentence in _SENTENCE.split(seg.source):
            if len(strong.findall(sentence)) > 1:
                found.append(
                    Finding(
                        seg.key,
                        "requirement",
                        "More than one prescription in a sentence: split it.",
                    )
                )
            if weak.search(sentence) and not strong.search(sentence):
                found.append(
                    Finding(
                        seg.key,
                        "requirement",
                        "Weak verb in a requirement: use a single mandatory verb.",
                    )
                )
            for word, pattern in vague:
                if pattern.search(sentence) and word not in flagged:
                    flagged.add(word)
                    found.append(
                        Finding(seg.key, "vague", f'Vague wording: "{word}" cannot be verified.')
                    )
    return found
