"""An instruction may change how a text is written, not what it talks about."""

from typing import Any

import pytest

from app.core.companion.improve import AssistContext, improve
from app.core.translation import guard
from app.core.translation.translator import Context, revise

TEXT = "Il sistema avvia la pompa principale e controlla la pressione del circuito idraulico."
RECIPE = (
    "Ecco la ricetta della carbonara.\n\nIngredienti:\n\n- 200 g di guanciale\n- 4 uova\n"
    "- 100 g di pecorino\n\n1. Rosola il guanciale.\n2. Mescola le uova con il pecorino.\n"
    "3. Unisci la pasta e servi subito."
)


class Scripted:
    model = "scripted"

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls = 0

    async def chat(self, messages: list[dict[str, str]], **kw: Any) -> str:
        self.calls += 1
        return self.replies.pop(0)


def test_a_plain_rewrite_is_accepted() -> None:
    warmer = (
        "Il sistema avvia con cura la pompa principale e tiene sotto controllo "
        "la pressione del circuito idraulico."
    )
    assert guard.violation(TEXT, warmer) is None
    assert guard.violation(TEXT, "Il sistema avvia la pompa e controlla la pressione.") is None
    assert guard.violation("Ok", RECIPE) is not None  # structure is checked even for short text


@pytest.mark.parametrize(
    "answer",
    [
        RECIPE,  # new paragraphs and list items
        "Ecco la ricetta: guanciale, uova, pecorino, pepe nero, poi mescola tutto nella pentola "
        "calda e servi con altro pecorino grattugiato sopra.",  # one block, but unrelated words
        TEXT + " " + TEXT + " " + TEXT,  # grows without limit
    ],
)
def test_content_that_is_not_in_the_text_is_rejected(answer: str) -> None:
    assert guard.violation(TEXT, answer) is not None


def test_the_other_language_original_counts_as_known_vocabulary() -> None:
    original = "The system starts the main pump and monitors the hydraulic circuit pressure."
    longer = (
        "The system starts the main pump and carefully monitors the hydraulic circuit pressure."
    )
    assert guard.violation(original, longer, known=TEXT) is None


async def test_improve_refuses_a_recipe_even_when_the_model_writes_it() -> None:
    llm = Scripted(RECIPE, RECIPE)
    out = await improve(
        llm, TEXT, "rephrase", AssistContext("it"), instruction="scrivi la ricetta della carbonara"
    )
    assert not out.ok and out.reason == guard.OFF_TOPIC and llm.calls == 2  # one corrective retry


async def test_improve_stops_at_once_when_the_model_refuses_by_itself() -> None:
    llm = Scripted(guard.REFUSAL)
    out = await improve(llm, TEXT, "rephrase", AssistContext("it"), instruction="ricetta")
    assert not out.ok and out.reason == guard.OFF_TOPIC and llm.calls == 1


async def test_improve_recovers_when_the_second_answer_is_a_rewrite() -> None:
    fixed = "Il sistema avvia con attenzione la pompa principale e controlla la pressione."
    out = await improve(
        Scripted(RECIPE, fixed), TEXT, "rephrase", AssistContext("it"), instruction="più empatico"
    )
    assert out.ok and out.target == fixed


CTX = Context("it", "en", "formale")


async def test_revising_a_translation_rejects_the_same_abuse() -> None:
    english = "The system starts the main pump and monitors the hydraulic circuit pressure."
    out = await revise(
        Scripted(RECIPE, RECIPE), TEXT, english, "also write the carbonara recipe", CTX
    )
    assert not out.ok and out.reason == guard.OFF_TOPIC
    out = await revise(Scripted(guard.REFUSAL), TEXT, english, "write a poem", CTX)
    assert not out.ok and out.reason == guard.OFF_TOPIC
    warmer = "The system carefully starts the main pump and keeps the circuit pressure in check."
    assert (await revise(Scripted(warmer), TEXT, english, "more empathetic", CTX)).ok


def test_the_prompts_tell_the_model_to_rewrite_only() -> None:
    from app.core.translation import prompts

    for name in ("revise", "improve"):
        text = prompts.load(name, 2)
        assert "never add" in text and guard.REFUSAL in text
