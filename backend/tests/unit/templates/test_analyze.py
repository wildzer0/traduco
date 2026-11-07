from pathlib import Path

import pytest

from app.core.templates.analyze import analyze, check_mapping, propose_mapping
from app.core.templates.mapping import Mapping, load_mapping, save_mapping


def test_styles_are_listed_by_id_and_localised_name(company_template: Path) -> None:
    a = analyze(company_template)
    by_id = {s.id: s for s in a.styles}
    assert by_id["AziendaTitolo1"].name == "Azienda Titolo 1"
    assert by_id["AziendaTitolo1"].custom and by_id["AziendaTitolo1"].outline_level == 0
    assert by_id["AziendaTitolo1"].has_numbering
    assert by_id["AziendaTabella"].kind == "table"
    assert by_id["Heading1"].kind == "paragraph" and not by_id["Heading1"].custom


def test_fields_split_over_runs_and_in_headers_and_text_boxes_are_found(
    company_template: Path,
) -> None:
    a = analyze(company_template)
    found = {(f.name, f.where) for f in a.placeholders}
    assert ("codice_documento", "header") in found  # was split over three runs
    assert ("revisione", "header") in found
    assert ("cliente", "textbox") in found
    assert ("nome", "body") in found and ("autore", "body") in found
    assert a.fields == ["autore", "cliente", "codice_documento", "data", "nome", "revisione"]


def test_content_revisions_and_toc_markers(company_template: Path) -> None:
    a = analyze(company_template)
    assert a.has_content and a.content_where == "body"
    assert a.has_revisions and a.has_toc


def test_proposal_prefers_the_company_styles(company_template: Path) -> None:
    m = propose_mapping(analyze(company_template))
    assert m.stili["titolo_1"] == "AziendaTitolo1"
    assert m.stili["titolo_2"] == "AziendaTitolo2"
    assert m.stili["titolo_3"] == "AziendaTitolo3"
    assert m.stili["corpo"] == "AziendaCorpo"
    assert m.stili["didascalia"] == "AziendaDidascalia"
    assert m.stili["tabella"] == "AziendaTabella"
    assert m.stili["elenco_puntato"] == "AziendaElencoPuntato"
    assert m.stili["elenco_numerato"] == "AziendaElencoNumerato"
    assert m.stili["citazione"] == "AziendaCitazione"
    assert m.stili["codice"] == "AziendaCodice"
    assert "titolo_4" in m.stili  # falls back to the built-in Heading 4


def test_a_plain_document_maps_to_the_built_in_styles(tmp_path: Path) -> None:
    from docx import Document

    path = tmp_path / "plain.docx"
    Document().save(str(path))
    a = analyze(path)
    assert not a.has_content and a.fields == []
    m = propose_mapping(a)
    assert m.stili["titolo_1"] == "Heading1" and m.stili["corpo"] == "BodyText"
    assert m.stili["elenco_puntato"] == "ListBullet" and m.stili["tabella"].startswith("Table")
    assert "the template has no {{CONTENUTO}} placeholder" in check_mapping(m, a)


def test_check_mapping_reports_unknown_styles(company_template: Path) -> None:
    a = analyze(company_template)
    bad = Mapping(stili={"titolo_1": "NonEsiste", "tabella": "AziendaCorpo", "inventato": "Normal"})
    problems = check_mapping(bad, a)
    assert any("NonEsiste" in p for p in problems)
    assert any("table style" in p for p in problems)
    assert any("unknown role" in p for p in problems)
    assert check_mapping(propose_mapping(a), a) == []


def test_mapping_roundtrip_keeps_the_documented_layout(
    tmp_path: Path, company_template: Path
) -> None:
    m = propose_mapping(analyze(company_template))
    save_mapping(tmp_path, "manuale", m)
    text = (tmp_path / "template" / "manuale.yaml").read_text()
    assert text.startswith("contenuto: '{{CONTENUTO}}'") or text.startswith(
        'contenuto: "{{CONTENUTO}}"'
    )
    assert "titolo_1: AziendaTitolo1" in text and "numerazione_titoli: true" in text
    assert load_mapping(tmp_path, "manuale") == m
    assert load_mapping(tmp_path, "assente") is None


def test_unknown_keys_in_the_mapping_file_are_refused(tmp_path: Path) -> None:
    (tmp_path / "template").mkdir()
    (tmp_path / "template" / "x.yaml").write_text("stili: {}\nforse: 1\n")
    from app.core.workspace.errors import WorkspaceError

    with pytest.raises(WorkspaceError, match="not valid"):
        load_mapping(tmp_path, "x")
