"""Translate one segment: protect, prompt, validate, retry once, restore."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.core.segmentation.protect import PlaceholderError, Protected, protect, restore

from . import glossary as glossary_mod
from . import guard, prompts

PROMPT_VERSION = "translate@2"
LANGUAGES = {
    "it": "Italian", "en": "English", "de": "German", "fr": "French", "es": "Spanish",
    "pt": "Portuguese", "nl": "Dutch", "pl": "Polish", "sv": "Swedish", "ro": "Romanian",
    "cs": "Czech", "ja": "Japanese", "zh": "Chinese", "ru": "Russian",
}  # fmt: skip
TONES = {
    "formale": "formal and professional (formal address where the language has one).",
    "neutro": "neutral and impersonal, as in technical documentation.",
    "informale": "informal and friendly (informal address where the language has one).",
}  # fmt: skip
LENGTH_RANGE = (0.5, 2.5)
MIN_CHARS_FOR_LENGTH_CHECK = 24


class Chat(Protocol):
    model: str

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = ...,
        max_tokens: int | None = ...,
    ) -> str: ...


@dataclass(frozen=True)
class Context:
    source_language: str
    target_language: str
    tone: str = "formale"
    section_title: str = ""
    note: str = ""
    previous_source: str = ""
    previous_target: str = ""
    non_translate: tuple[str, ...] = ()
    glossary: tuple[glossary_mod.Entry, ...] = ()


@dataclass(frozen=True)
class Outcome:
    target: str
    ok: bool
    reason: str = ""
    model: str = ""
    prompt_version: str = PROMPT_VERSION
    attempts: int = field(default=1)


def has_translatable_text(protected: Protected) -> bool:
    plain = re.sub(r"⟦/?\d+⟧", "", protected.text)
    return re.search(r"[^\W\d_]", plain) is not None


def build_messages(
    ctx: Context, protected: Protected, correction: str = ""
) -> list[dict[str, str]]:
    rules = glossary_mod.prompt_rules(list(ctx.glossary), ctx.target_language)
    extra = f"\n- Glossary (mandatory):\n{rules}" if rules else ""
    system = prompts.load("translate", 2).format(
        source_language=LANGUAGES.get(ctx.source_language, ctx.source_language),
        target_language=LANGUAGES.get(ctx.target_language, ctx.target_language),
        tone_instruction=TONES.get(ctx.tone, TONES["neutro"]),
        extra_rules=extra,
    )
    lines: list[str] = []
    if ctx.section_title:
        lines.append(f"Section title (context only, do not translate here): {ctx.section_title}")
    if ctx.note:
        lines.append(f"Note from the author: {ctx.note}")
    if ctx.previous_source and ctx.previous_target:
        lines.append(
            "Previous segment, for consistency (do not repeat it):\n"
            f"{ctx.previous_source}\n=> {ctx.previous_target}"
        )
    if correction:
        lines.append(f"IMPORTANT: {correction}")
    lines.append(f"<source>{protected.text}</source>")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(lines)}]


def _missing_pairs(reply: str, protected: Protected) -> list[int]:
    """Pairs of which the answer has neither the opening nor the closing marker."""
    return [n for n in protected.pairs if f"⟦{n}⟧" not in reply and f"⟦/{n}⟧" not in reply]


_LEAD_IN = re.compile(r"^(\s*)(.+?[.:!?])(?=\s|$)", re.DOTALL)


def _repair(reply: str, protected: Protected, ctx: Context) -> str | None:
    """Put back markers that a model dropped, in the three cases where the place is certain.

    * around a glossary term it replaced: ``⟦1⟧messa in servizio⟦/1⟧`` -> "commissioning" comes back
      bare, and its imposed translation occurs once in the answer;
    * around a lead-in ("**Attenzione.** …"): the pair opens the segment and its text ends in
      punctuation, so the first sentence of the answer is wrapped;
    * around the whole segment.
    """
    text = reply
    for n in _missing_pairs(reply, protected):
        inner = re.search(rf"⟦{n}⟧(.*?)⟦/{n}⟧", protected.text, re.DOTALL)
        if inner is None:
            continue
        body = inner.group(1).strip()
        for e in ctx.glossary:
            imposed = e.destinazione.get(ctx.target_language)
            if not imposed or not glossary_mod.matches_term(e.sorgente, body):
                continue
            found = list(glossary_mod.term_pattern(imposed).finditer(text))
            if len(found) == 1:
                a, b = found[0].span()
                text = f"{text[:a]}⟦{n}⟧{text[a:b]}⟦/{n}⟧{text[b:]}"
                break
        else:
            if protected.text.strip() == f"⟦{n}⟧{inner.group(1)}⟦/{n}⟧":
                text = f"⟦{n}⟧{text.strip()}⟦/{n}⟧"  # the whole segment
            elif protected.text.lstrip().startswith(f"⟦{n}⟧") and body[-1:] in ".:!?":
                lead = _LEAD_IN.match(text)
                if lead and "⟦" not in lead.group(2):
                    start = lead.start(2)
                    text = f"{text[:start]}⟦{n}⟧{lead.group(2)}⟦/{n}⟧{text[lead.end(2) :]}"
    return text if text != reply else None


def _degraded(reply: str, protected: Protected) -> str | None:
    """The answer with the formatting it lost simply left out, when everything else is right."""
    missing = _missing_pairs(reply, protected)
    if not missing:
        return None
    bare = Protected(
        protected.text,
        protected.atoms,
        {n: marks for n, marks in protected.pairs.items() if n not in missing},
    )
    try:
        return restore(reply, bare)
    except PlaceholderError:
        return None


def restore_or_repair(reply: str, protected: Protected, ctx: Context) -> str:
    """``restore`` the answer; if its markers are damaged try :func:`_repair` once."""
    try:
        return restore(reply, protected)
    except PlaceholderError:
        fixed = _repair(reply, protected, ctx)
        if fixed is None:
            raise
        return restore(fixed, protected)


def _clean(reply: str) -> str:
    text = reply.strip()
    match = re.fullmatch(r"<source>(.*)</source>", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    return text


async def translate(client: Chat, source: str, ctx: Context) -> Outcome:
    """Translate ``source``; never raises for a bad answer (returns ``ok=False`` with a reason).

    Connection problems propagate as :class:`LlmUnavailable` so the caller can retry later.
    """
    protected = protect(source, ctx.non_translate)
    if not has_translatable_text(protected):
        return Outcome(source, True, model=client.model)
    correction = ""
    reason = ""
    best = ""
    for attempt in (1, 2):
        reply = _clean(
            await client.chat(
                build_messages(ctx, protected, correction),
                temperature=0.2,
                max_tokens=max(256, 3 * len(source)),
            )
        )
        try:
            restored = restore_or_repair(reply, protected, ctx)
        except PlaceholderError as exc:
            reason = f"placeholders: {exc}"
            best = _degraded(reply, protected) or best
            if best and attempt == 2:
                reason = f"placeholders: formatting lost ({exc})"
            correction = (
                "Your previous answer broke the placeholders (" + str(exc) + "). "
                "Copy every ⟦n⟧ marker exactly once, keeping pairs ⟦n⟧…⟦/n⟧ around the same words."
            )
            continue
        best = restored
        low, high = LENGTH_RANGE
        ratio = len(restored) / max(1, len(source))
        if len(source) >= MIN_CHARS_FOR_LENGTH_CHECK and not low <= ratio <= high:
            reason = f"implausible length ({ratio:.1f}x the source)"
            correction = (
                "Your previous answer had a very different length. "
                "Translate everything and add nothing."
            )
            continue
        if not restored.strip():
            reason = "empty translation"
            continue
        problems = glossary_mod.violations(list(ctx.glossary), restored, ctx.target_language)
        if problems:
            reason = "glossary: " + "; ".join(problems)
            correction = (
                "Your previous answer broke the glossary: " + "; ".join(problems) + ". "
                "Translate again following the glossary exactly."
            )
            continue
        return Outcome(restored, True, model=client.model, attempts=attempt)
    return Outcome(best, False, reason, model=client.model, attempts=2)


def build_revise_messages(
    ctx: Context,
    original: str,
    protected: Protected,
    instruction: str,
    variant: str = "",
) -> list[dict[str, str]]:
    rules = glossary_mod.prompt_rules(list(ctx.glossary), ctx.target_language)
    system = prompts.load("revise", 2).format(
        source_language=LANGUAGES.get(ctx.source_language, ctx.source_language),
        target_language=LANGUAGES.get(ctx.target_language, ctx.target_language),
        tone_instruction=TONES.get(ctx.tone, TONES["neutro"]),
        extra_rules=f"\n- Glossary (mandatory):\n{rules}" if rules else "",
    )
    parts = [f"<original>{original}</original>", f"Instruction: {instruction}"]
    if variant:
        parts.append(variant)
    parts.append(f"<source>{protected.text}</source>")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


async def revise(
    client: Chat,
    original: str,
    current: str,
    instruction: str,
    ctx: Context,
    *,
    variant: str = "",
    temperature: float = 0.2,
) -> Outcome:
    """Rewrite an existing translation following ``instruction`` (RF-26). Nothing is saved here."""
    protected = protect(current, ctx.non_translate)
    reason = ""
    for attempt in (1, 2):
        extra = "" if attempt == 1 else f"IMPORTANT: {reason}. Fix this."
        messages = build_revise_messages(ctx, original, protected, instruction, variant or extra)
        reply = _clean(
            await client.chat(
                messages, temperature=temperature, max_tokens=max(256, 3 * len(current))
            )
        )
        if guard.is_refusal(reply):
            return Outcome(current, False, guard.OFF_TOPIC, model=client.model, attempts=attempt)
        try:
            restored = restore_or_repair(reply, protected, ctx)
        except PlaceholderError as exc:
            reason = f"your answer broke the placeholders ({exc})"
            continue
        if why := guard.violation(current, restored, known=original):
            reason = f"your answer was not a rewrite: {why}"
            continue
        problems = glossary_mod.violations(list(ctx.glossary), restored, ctx.target_language)
        if problems:
            reason = "your answer broke the glossary: " + "; ".join(problems)
            continue
        if not restored.strip():
            reason = "your answer was empty"
            continue
        return Outcome(restored, True, model=client.model, attempts=attempt)
    if "not a rewrite" in reason:
        reason = guard.OFF_TOPIC  # twice: the instruction is asking for something else
    return Outcome(current, False, reason, model=client.model, attempts=2)


Status = Literal["queued", "translated", "needs_review", "approved", "diverged"]
