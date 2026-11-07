from app.core.segmentation.protect import protect
from app.core.translation.glossary import Entry
from app.core.translation.translator import Context, build_messages, translate

CTX = Context("it", "en", tone="formale", section_title="Scopo", note="tecnici")


class Scripted:
    model = "scripted"

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages, *, temperature=0.2, max_tokens=None):  # type: ignore[no-untyped-def]
        self.calls.append(messages)
        return self.replies.pop(0)


async def test_translates_and_restores_markup() -> None:
    llm = Scripted("Press ⟦2⟧Enter⟦/2⟧ to run ⟦1⟧.")
    out = await translate(llm, "Premi **Invio** per eseguire `make`.", CTX)
    assert out.ok and out.target == "Press **Enter** to run `make`."
    assert out.model == "scripted" and out.attempts == 1


async def test_prompt_carries_tone_context_and_previous_segment() -> None:
    ctx = Context("it", "de", "informale", "Scopo", "tecnici", "Ciao.", "Hallo.")
    msgs = build_messages(ctx, protect("Testo."))
    system, user = msgs[0]["content"], msgs[1]["content"]
    assert "Italian" in system and "German" in system and "informal" in system
    assert "Scopo" in user and "tecnici" in user and "Ciao." in user and "Hallo." in user
    assert user.endswith("<source>Testo.</source>")


async def test_retries_once_with_correction_when_placeholders_break() -> None:
    llm = Scripted("Press Enter.", "Press ⟦1⟧Enter⟦/1⟧.")
    out = await translate(llm, "Premi **Invio**.", CTX)
    assert out.ok and out.attempts == 2 and out.target == "Press **Enter**."
    assert "broke the placeholders" in llm.calls[1][1]["content"]


async def test_gives_up_with_a_reason() -> None:
    llm = Scripted("nope", "still nope")
    out = await translate(llm, "Premi **Invio**.", CTX)
    assert not out.ok and "placeholders" in out.reason


async def test_implausible_length_is_flagged_but_kept() -> None:
    src = "Questo paragrafo è abbastanza lungo da essere controllato."
    llm = Scripted("ok", "ok")
    out = await translate(llm, src, CTX)
    assert not out.ok and "length" in out.reason and out.target == "ok"


async def test_text_without_words_skips_the_model() -> None:
    llm = Scripted()
    out = await translate(llm, "`code` {{campo}} 42", CTX)
    assert out.ok and out.target == "`code` {{campo}} 42" and not llm.calls


async def test_answer_wrapped_in_source_tags_is_unwrapped() -> None:
    llm = Scripted("<source>Hello world.</source>")
    assert (await translate(llm, "Ciao mondo.", CTX)).target == "Hello world."


GLOSSARY = (Entry(sorgente="offerta", destinazione={"en": "proposal"}, vietati={"en": ["offer"]}),)
GCTX = Context("it", "en", glossary=GLOSSARY)


async def test_glossary_violation_triggers_a_corrective_retry() -> None:
    llm = Scripted("Send the offer today.", "Send the proposal today.")
    out = await translate(llm, "Invia l'offerta oggi.", GCTX)
    assert out.ok and out.target == "Send the proposal today." and out.attempts == 2
    assert 'Translate "offerta" as "proposal"' in llm.calls[0][0]["content"]
    assert "broke the glossary" in llm.calls[1][1]["content"]


async def test_persistent_glossary_violation_ends_in_review_with_reason() -> None:
    llm = Scripted("Send the offer today.", "Send the offer now.")
    out = await translate(llm, "Invia l'offerta oggi.", GCTX)
    assert not out.ok and out.reason.startswith("glossary:") and "proposal" in out.reason
    assert out.target == "Send the offer now."  # best effort stays visible


async def test_untranslatable_term_is_protected_by_a_placeholder() -> None:
    ctx = Context(
        "it",
        "en",
        non_translate=("ACME Pump",),
        glossary=(Entry(sorgente="ACME Pump", non_tradurre=True),),
    )
    llm = Scripted("The ⟦1⟧ is ready for the test.")
    out = await translate(llm, "La ACME Pump è pronta per il test.", ctx)
    assert out.ok and out.target == "The ACME Pump is ready for the test."
