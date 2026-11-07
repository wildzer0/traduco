from pathlib import Path

from app.core.translation import glossary
from app.core.translation.glossary import Entry

ENTRIES = [
    Entry(sorgente="offerta", destinazione={"en": "proposal"}, vietati={"en": ["offer"]}),
    Entry(sorgente="ACME Pump", non_tradurre=True),
    Entry(sorgente="collaudo", destinazione={"en": "acceptance test"}),
]


def test_roundtrip_keeps_sorgente_first_and_omits_defaults(tmp_path: Path) -> None:
    glossary.save(tmp_path, ENTRIES)
    text = (tmp_path / "glossario.yaml").read_text()
    assert text.startswith("- sorgente: offerta\n")
    assert "non_tradurre: false" not in text and "note:" not in text
    assert glossary.load(tmp_path) == ENTRIES


def test_empty_glossary(tmp_path: Path) -> None:
    assert glossary.load(tmp_path) == []
    glossary.save(tmp_path, [])
    assert (tmp_path / "glossario.yaml").read_text() == "[]\n"
    assert glossary.load(tmp_path) == []


def test_relevant_matches_words_case_insensitive_with_plural() -> None:
    got = glossary.relevant(ENTRIES, "Le Offerte per il collaudo, non il collaudatore.")
    assert [e.sorgente for e in got] == ["offerta", "collaudo"]
    assert glossary.relevant(ENTRIES, "L'offertorio") == []


def test_violations_cover_imposed_forbidden_and_untranslatable() -> None:
    assert (
        glossary.violations(ENTRIES, "ACME Pump sends the proposal for the acceptance tests", "en")
        == []
    )
    bad = glossary.violations(ENTRIES, "The offer from ACME pump", "en")
    assert 'use "proposal" for "offerta"' in bad
    assert any('"offer" is forbidden' in b for b in bad)
    assert any("acceptance test" in b for b in glossary.violations(ENTRIES, "The testing", "en"))
    assert glossary.violations(ENTRIES[1:2], "The ACME pump", "en") == []  # case-insensitive
    assert glossary.violations(ENTRIES[1:2], "The Acme Pomp", "en") == [
        '"ACME Pump" must be kept unchanged'
    ]


def test_prompt_rules() -> None:
    text = glossary.prompt_rules(ENTRIES, "en")
    assert 'Translate "offerta" as "proposal". Never use: offer.' in text
    assert 'Keep "ACME Pump" unchanged.' in text


def test_do_not_translate_list() -> None:
    assert glossary.do_not_translate(ENTRIES) == ("ACME Pump",)
