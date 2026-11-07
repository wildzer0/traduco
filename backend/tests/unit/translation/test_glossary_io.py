import pytest

from app.core.translation import glossary_io as gio
from app.core.translation.glossary import Entry
from app.core.workspace.errors import WorkspaceError

ENTRIES = [
    Entry(
        sorgente="offerta",
        destinazione={"en": "proposal", "de": "Angebot"},
        vietati={"en": ["offer", "bid"]},
        note="Termine contrattuale",
    ),
    Entry(sorgente="Traduco", non_tradurre=True),
]


def same(a: list[Entry], b: list[Entry]) -> bool:
    return [e.model_dump() for e in a] == [e.model_dump() for e in b]


def test_csv_round_trip_keeps_everything() -> None:
    data = gio.export_csv(ENTRIES)
    assert data.startswith(b"\xef\xbb\xbf") and b"sorgente,lingua" in data
    assert same(gio.import_csv(data), ENTRIES)


def test_csv_from_a_spreadsheet_with_semicolons() -> None:
    text = "sorgente;lingua;destinazione;vietati;non_tradurre;note\nrevisione;en;revision;;0;\n"
    [entry] = gio.import_csv(text.encode("utf-8"))
    assert entry.sorgente == "revisione" and entry.destinazione == {"en": "revision"}


def test_csv_without_the_source_column_is_refused() -> None:
    with pytest.raises(WorkspaceError, match="sorgente"):
        gio.import_csv(b"term,translation\na,b\n")


def test_tbx_round_trip_keeps_translations_forbidden_terms_and_flags() -> None:
    data = gio.export_tbx(ENTRIES, "it")
    assert b"<martif" in data and b"forbidden-term-admn-sts" in data
    assert same(gio.import_tbx(data, "it"), ENTRIES)


def test_a_hostile_or_wrong_tbx_is_refused() -> None:
    evil = (
        b'<?xml version="1.0"?><!DOCTYPE m [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        b'<martif xml:lang="it"><text><body><termEntry><langSet xml:lang="it"><tig>'
        b"<term>x &e;</term></tig></langSet></termEntry></body></text></martif>"
    )
    for entry in gio.import_tbx(evil, "it"):
        assert "root:" not in entry.sorgente
    with pytest.raises(WorkspaceError):
        gio.import_tbx(b"junk", "it")
    with pytest.raises(WorkspaceError):
        gio.import_tbx(b"<tmx/>", "it")


def test_importing_merges_and_never_overwrites_what_the_author_wrote() -> None:
    mine = [Entry(sorgente="offerta", destinazione={"en": "tender"}, note="mia nota")]
    theirs = [
        Entry(
            sorgente="Offerta",
            destinazione={"en": "proposal", "de": "Angebot"},
            vietati={"en": ["offer"]},
            note="altra",
        ),
        Entry(sorgente="nuovo", destinazione={"en": "new"}),
    ]
    merged = gio.merge(mine, theirs)
    assert [e.sorgente for e in merged] == ["offerta", "nuovo"]
    assert merged[0].destinazione == {"en": "tender", "de": "Angebot"}
    assert merged[0].vietati == {"en": ["offer"]} and merged[0].note == "mia nota"
