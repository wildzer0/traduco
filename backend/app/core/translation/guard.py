"""Keep instruction-driven rewrites to *rewriting* (RF-87, RF-89).

The author may ask for a different tone, a shorter or simpler wording, a term changed... but not for
new content: a technical document must not get a recipe because the instruction box accepted
free text. A small local model cannot be trusted to refuse by itself, so the prompt asks it to
answer with a marker *and* the answer is checked here, whatever the model says:

* it may not grow much beyond the text it rewrites;
* it may not add paragraphs, list items or headings the text did not have;
* when it is longer, most of its words must come from the text (or its original).

Nothing here judges the quality of the writing; it only rejects what is plainly not a rewrite.
"""

from __future__ import annotations

import re

REFUSAL = "[[REFUSED]]"
OFF_TOPIC = "off_topic"  # the ``reason`` of an Outcome that was rejected by this module
MAX_GROWTH = 1.8
NOVELTY_FROM = 1.25  # the vocabulary check applies to answers this much longer than the text
MAX_NOVEL_SHARE = 0.7
MIN_LENGTH = 20  # shorter texts are exempt from the length and vocabulary checks

_WORD = re.compile(r"\w{4,}", re.UNICODE)
_BLOCK_START = re.compile(r"^\s*(?:[-*+•]\s|\d+[.)]\s|#{1,6}\s|>\s)", re.MULTILINE)


def is_refusal(reply: str) -> bool:
    return reply.strip().startswith(REFUSAL)


def _paragraphs(text: str) -> int:
    return len([p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()])


def _blocks(text: str) -> int:
    return len(_BLOCK_START.findall(text))


def violation(before: str, after: str, *, known: str = "") -> str | None:
    """Why ``after`` is not a rewrite of ``before`` (``known`` adds words that may be reused)."""
    if _paragraphs(after) > _paragraphs(before) or _blocks(after) > _blocks(before):
        return "it added paragraphs, list items or headings the text did not have"
    if len(before) < MIN_LENGTH:
        return None
    ratio = len(after) / len(before)
    if ratio > MAX_GROWTH:
        return "it is much longer than the text: add nothing, only rewrite"
    if ratio > NOVELTY_FROM:
        used = set(_WORD.findall(after.lower()))
        if used:
            have = set(_WORD.findall(f"{before} {known}".lower()))
            if len(used - have) / len(used) > MAX_NOVEL_SHARE:
                return "it introduces content that is not in the text: add nothing, only rewrite"
    return None
