from pathlib import Path

import pytest

from app.core.translation import tm
from app.core.workspace.errors import WorkspaceError


def test_an_empty_memory_finds_nothing(tmp_path: Path) -> None:
    assert tm.exact(tmp_path, "it", "en", "Ciao") is None
    assert tm.similar(tmp_path, "it", "en", "Ciao") == []
    assert tm.count(tmp_path) == 0 and not (tmp_path / ".traduco").exists()


def test_exact_match_ignores_white_space_but_not_the_language_pair(tmp_path: Path) -> None:
    tm.remember(tmp_path, "it", "en", "La pompa  parte.", "The pump starts.", "manual")
    assert tm.exact(tmp_path, "it", "en", "La pompa parte.\n").target == "The pump starts."  # type: ignore[union-attr]
    assert tm.exact(tmp_path, "it", "de", "La pompa parte.") is None
    assert tm.exact(tmp_path, "it", "en", "la pompa parte.") is None  # case matters for "exact"


def test_the_newest_translation_of_a_source_wins(tmp_path: Path) -> None:
    tm.remember(tmp_path, "it", "en", "Avvia.", "Start.", "mt")
    tm.remember(tmp_path, "it", "en", "Avvia.", "Launch.", "manual")
    assert tm.count(tmp_path) == 1
    assert tm.exact(tmp_path, "it", "en", "Avvia.").target == "Launch."  # type: ignore[union-attr]


def test_similar_sources_are_suggested_best_first(tmp_path: Path) -> None:
    tm.remember(
        tmp_path,
        "it",
        "en",
        "Il sistema avvia la pompa principale.",
        "The system starts the main pump.",
        "manual",
    )
    tm.remember(
        tmp_path,
        "it",
        "en",
        "Il sistema avvia la pompa di riserva.",
        "The system starts the spare pump.",
        "manual",
    )
    tm.remember(
        tmp_path, "it", "en", "Tutt'altro argomento del manuale.", "Something else.", "manual"
    )
    found = tm.similar(tmp_path, "it", "en", "Il sistema avvia la pompa principale!")
    assert [m.target for m in found][0] == "The system starts the main pump."
    assert all(0.75 <= m.score <= 1 for m in found) and len(found) == 2
    assert tm.similar(tmp_path, "it", "en", "Il sistema avvia la pompa principale.")[0].score == 1.0
    assert tm.similar(tmp_path, "it", "en", "Completamente diverso") == []


def test_tmx_round_trip(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    tm.remember(a, "it", "en", "Ciao & benvenuto <tutti>", "Hello & welcome <all>", "manual")
    tm.remember(a, "it", "de", "Ciao", "Hallo", "manual")
    data = tm.export_tmx(a, "it")
    assert b"<tmx" in data and b'srclang="it"' in data and b"&amp;" in data
    assert tm.import_tmx(b, data) == 2
    assert tm.exact(b, "it", "en", "Ciao & benvenuto <tutti>").target == "Hello & welcome <all>"  # type: ignore[union-attr]
    assert tm.exact(b, "it", "de", "Ciao").origin == "tmx"  # type: ignore[union-attr]


def test_a_hostile_or_wrong_file_is_refused(tmp_path: Path) -> None:
    evil = (
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        b'<tmx version="1.4"><body><tu><tuv xml:lang="it"><seg>Testo &e;</seg></tuv>'
        b'<tuv xml:lang="en"><seg>Text &e;</seg></tuv></tu></body></tmx>'
    )
    tm.import_tmx(tmp_path, evil)  # the entity is not expanded: no file is read
    assert b"root:" not in tm.export_tmx(tmp_path, "it")
    with pytest.raises(WorkspaceError):
        tm.import_tmx(tmp_path, b"not xml")
    with pytest.raises(WorkspaceError):
        tm.import_tmx(tmp_path, b"<html/>")
