"""Rewrite source text on request: proofread, rephrase, shorten, simplify, change tone."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.core.segmentation.protect import PlaceholderError, protect, restore
from app.core.translation import glossary as glossary_mod
from app.core.translation import prompts
from app.core.translation.translator import LANGUAGES, TONES, Chat, Outcome, _clean

PROMPT_VERSION = "improve@1"
Action = Literal["correct", "rephrase", "concise", "simple", "formale", "neutro", "informale"]
INSTRUCTIONS: dict[str, str] = {
    "correct": "Correct spelling, grammar and punctuation only. Change nothing else.",
    "rephrase": "Rephrase the text so it reads more naturally and clearly, keeping the register.",
    "concise": "Make the text shorter and more direct without losing any information.",
    "simple": "Use simpler words and shorter sentences so a non-expert reader understands it.",
    "formale": "Rewrite in a formal, professional register.",
    "neutro": "Rewrite in a neutral, impersonal register, as in technical documentation.",
    "informale": "Rewrite in an informal, friendly register.",
}
LENGTH_RANGE = (0.3, 2.5)


@dataclass(frozen=True)
class AssistContext:
    language: str
    tone: str = "formale"
    section_title: str = ""
    note: str = ""
    guide: str = ""
    glossary: tuple[glossary_mod.Entry, ...] = field(default_factory=tuple)


def build_system(ctx: AssistContext) -> str:
    rules: list[str] = []
    terms = [e.sorgente for e in ctx.glossary]
    if terms:
        rules.append(
            "- Controlled terms: keep these exactly as they are written: " + ", ".join(terms) + "."
        )
    if ctx.note:
        rules.append(f"- Note from the author: {ctx.note}")
    if ctx.guide:
        rules.append(f"- This section should cover: {ctx.guide}")
    return prompts.load("improve", 1).format(
        language=LANGUAGES.get(ctx.language, ctx.language),
        tone_instruction=TONES.get(ctx.tone, TONES["neutro"]),
        extra_rules=("\n" + "\n".join(rules)) if rules else "",
    )


async def improve(
    client: Chat,
    text: str,
    action: str,
    ctx: AssistContext,
    *,
    instruction: str = "",
    temperature: float = 0.3,
) -> Outcome:
    """Propose a rewrite of ``text``. Nothing is saved; the caller shows it to the author.

    The proposal is rejected (``ok=False``) if it breaks a placeholder, drops a controlled term,
    is empty or has an implausible length. One corrective retry, like the translator.
    """
    base = INSTRUCTIONS.get(action, "")
    if instruction.strip():
        base = f"{base} {instruction.strip()}".strip()
    if not base:
        return Outcome(text, False, "no instruction")
    protected = protect(text, glossary_mod.do_not_translate(list(ctx.glossary)))
    reason = ""
    for attempt in (1, 2):
        user = f"Instruction: {base}\n\n"
        if attempt == 2:
            user += f"IMPORTANT: your previous answer was rejected because {reason}. Fix this.\n\n"
        user += f"<source>{protected.text}</source>"
        messages = [
            {"role": "system", "content": build_system(ctx)},
            {"role": "user", "content": user},
        ]
        reply = _clean(
            await client.chat(messages, temperature=temperature, max_tokens=max(256, 3 * len(text)))
        )
        try:
            restored = restore(reply, protected)
        except PlaceholderError as exc:
            reason = f"it broke the placeholders ({exc})"
            continue
        if not restored.strip():
            reason = "it was empty"
            continue
        low, high = LENGTH_RANGE
        if len(text) >= 20 and not low <= len(restored) / len(text) <= high:
            reason = "its length was very different from the original"
            continue
        lost = [
            e.sorgente
            for e in glossary_mod.relevant(list(ctx.glossary), text)
            if not glossary_mod.relevant([e], restored)
        ]
        if lost:
            reason = "it dropped the controlled terms: " + ", ".join(lost)
            continue
        return Outcome(
            restored, True, model=client.model, prompt_version=PROMPT_VERSION, attempts=attempt
        )
    return Outcome(
        text, False, reason, model=client.model, prompt_version=PROMPT_VERSION, attempts=2
    )
