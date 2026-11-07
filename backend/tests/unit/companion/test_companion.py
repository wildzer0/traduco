import json
from pathlib import Path
from typing import Any

from app.core.companion import check, rules
from app.core.companion.improve import AssistContext, improve
from app.core.segmentation.segmenter import segment
from app.core.translation.glossary import Entry


class Scripted:
    model = "scripted"

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages: list[dict[str, str]], **kw: Any) -> str:
        self.calls.append(messages)
        return self.replies.pop(0) if self.replies else "[]"


CTX = AssistContext("it", "formale", "Scopo", "tecnici", "descrivi il sistema")
TEXT = "Il sistema e' composto da una pompa **principale** e da `un filtro`."


async def test_improve_returns_a_proposal_and_keeps_markup() -> None:
    llm = Scripted("Il sistema è composto da una pompa ⟦2⟧principale⟦/2⟧ e da ⟦1⟧.")
    out = await improve(llm, TEXT, "correct", CTX)
    assert (
        out.ok
        and out.target == "Il sistema è composto da una pompa **principale** e da `un filtro`."
    )
    system, user = llm.calls[0][0]["content"], llm.calls[0][1]["content"]
    assert "Italian" in system and "formal" in system
    assert "tecnici" in system and "descrivi il sistema" in system  # note and skeleton guide
    assert "Correct spelling" in user and "⟦1⟧" in user and "`un filtro`" not in user


async def test_improve_actions_have_distinct_instructions() -> None:
    seen = set()
    for action in ("correct", "rephrase", "concise", "simple", "formale", "neutro", "informale"):
        llm = Scripted("Va bene così, nessun problema qui.")
        await improve(llm, "Va bene così, nessun problema.", action, CTX)
        seen.add(llm.calls[0][1]["content"].split("\n")[0])
    assert len(seen) == 7


async def test_a_free_instruction_is_added() -> None:
    llm = Scripted("Testo breve ma valido qui.")
    await improve(llm, "Testo breve ma valido.", "rephrase", CTX, instruction="usa il passivo")
    assert "usa il passivo" in llm.calls[0][1]["content"]


async def test_broken_placeholders_get_one_corrective_retry_then_fail() -> None:
    llm = Scripted("Pompa e filtro.", "Pompa e filtro ancora.")
    out = await improve(llm, TEXT, "concise", CTX)
    assert not out.ok and "placeholders" in out.reason
    assert "rejected" in llm.calls[1][1]["content"]


async def test_dropping_a_controlled_term_is_rejected() -> None:
    ctx = AssistContext(
        "it", glossary=(Entry(sorgente="pompa di mandata", destinazione={"en": "x"}),)
    )
    text = "La pompa di mandata alimenta il circuito principale."
    llm = Scripted(
        "Il dispositivo alimenta il circuito principale.",
        "La pompa di mandata alimenta il circuito.",
    )
    out = await improve(llm, text, "rephrase", ctx)
    assert out.ok and "pompa di mandata" in out.target and out.attempts == 2
    assert "Controlled terms" in llm.calls[0][0]["content"]


async def test_implausible_length_is_rejected() -> None:
    llm = Scripted("Ok.", "Ok.")
    out = await improve(
        llm, "Questa è una frase di lunghezza sufficiente per il controllo.", "concise", CTX
    )
    assert not out.ok and "length" in out.reason


# --- requirement rules -------------------------------------------------------------------------


def findings(text: str, lang: str = "en") -> list[tuple[str, str]]:
    return [
        (f.category, f.message)
        for f in rules.check_requirements(list(segment(text).segments), lang)
    ]


def test_one_prescription_per_sentence() -> None:
    got = findings("The pump shall start and the valve shall close.\n")
    assert any("More than one prescription" in m for _, m in got)
    assert findings("The pump shall start. The valve shall close.\n") == []


def test_weak_verbs_and_vague_words() -> None:
    got = findings("The system should respond quickly.\n")
    assert ("requirement", "Weak verb in a requirement: use a single mandatory verb.") in got
    assert any(c == "vague" and "quickly" in m for c, m in got)
    assert findings("The system shall respond within 2 s.\n") == []


def test_italian_rules() -> None:
    got = findings("Il sistema dovrebbe rispondere in modo adeguato.\n", "it")
    assert any("Verbo debole" in m for _, m in got) and any("«adeguato»" in m for _, m in got)
    assert any(
        "Più di una prescrizione" in m
        for _, m in findings("La pompa deve partire e la valvola deve chiudersi.\n", "it")
    )


def test_headings_are_not_checked() -> None:
    assert findings("# Quickly as possible\n") == []


# --- section check -----------------------------------------------------------------------------

DOC = "# Titolo\n\nQuesto paragrafo contiene un errore di ortografia evidente qui.\n\nBreve.\n"


async def test_check_collects_model_issues_and_validates_fixes() -> None:
    reply = json.dumps(
        [
            {
                "category": "grammar",
                "message": "Errore di ortografia",
                "suggestion": "Questo paragrafo non contiene errori di ortografia evidenti.",
            },
            {"category": "weird-category", "message": "Frase poco chiara", "suggestion": ""},
        ]
    )
    llm = Scripted(reply)
    doc = segment(DOC)
    items = await check.check_section(llm, doc, AssistContext("it"))
    assert [i.category for i in items] == ["grammar", "style"]  # unknown category becomes "style"
    assert items[0].key == "p:0" and items[0].suggestion.startswith("Questo paragrafo non")
    assert len(llm.calls) == 1  # "Breve." and the heading are too short to review


async def test_unreadable_model_output_means_no_remarks() -> None:
    assert check.parse_issues("Sure! Here are the problems: none") == []
    assert check.parse_issues('```json\n[{"message": "x"}]\n```')[0]["message"] == "x"
    assert check.parse_issues('[{"category": 1}]') == []


async def test_a_suggestion_that_breaks_placeholders_is_dropped_but_the_remark_stays() -> None:
    doc = segment("Premi **Invio** per continuare con la procedura di avvio.\n")
    llm = Scripted(
        json.dumps(
            [{"category": "clarity", "message": "Poco chiaro", "suggestion": "Premi Invio."}]
        )
    )
    items = await check.check_section(llm, doc, AssistContext("it"))
    assert len(items) == 1 and items[0].suggestion == ""


async def test_requirement_rules_are_optional_and_the_guide_is_checked() -> None:
    text = "Il sistema dovrebbe funzionare in modo adeguato in ogni condizione prevista.\n"
    doc = segment(text)
    plain = await check.check_section(Scripted("[]", "[]"), doc, AssistContext("it"))
    assert plain == []
    ctx = AssistContext("it", section_title="Scopo", guide="limiti di applicazione")
    llm = Scripted(
        "[]", json.dumps([{"category": "coverage", "message": "Mancano i limiti di applicazione"}])
    )
    items = await check.check_section(llm, doc, ctx, requirement_rules=True)
    origins = {i.origin for i in items}
    assert origins == {"rule", "guide"}
    assert "limiti di applicazione" in llm.calls[-1][0]["content"]


def test_suggestions_are_stored_and_expire_when_the_segment_changes(tmp_path: Path) -> None:
    doc = segment(DOC)
    item = check.Suggestion(
        "abc", "p:0", doc.by_key()["p:0"].hash, "grammar", "msg", "fix", "model"
    )
    check.save(tmp_path, "capitoli/01-a/01-s.md", DOC, [item])
    assert [i.id for i in check.load(tmp_path, "capitoli/01-a/01-s.md", doc)] == ["abc"]
    changed = segment(DOC.replace("errore", "refuso"))
    assert check.load(tmp_path, "capitoli/01-a/01-s.md", changed) == []
    check.set_status(tmp_path, "capitoli/01-a/01-s.md", doc, "abc", "dismissed")
    assert check.load(tmp_path, "capitoli/01-a/01-s.md", doc)[0].status == "dismissed"
