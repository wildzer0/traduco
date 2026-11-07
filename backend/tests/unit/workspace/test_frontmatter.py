import pytest

from app.core.workspace.frontmatter import FrontMatterError, parse, render

SAMPLE = """---
title: Scopo del documento
tono: neutro                  # facoltativo
contesto: Pubblico di tecnici.
traduci: true
---

# Scopo

Testo.
"""


def test_parse_extracts_meta_and_body() -> None:
    doc = parse(SAMPLE)
    assert doc.meta["title"] == "Scopo del documento"
    assert doc.meta["traduci"] is True
    assert doc.body == "\n# Scopo\n\nTesto.\n"


def test_round_trip_preserves_text_and_comments() -> None:
    assert render(parse(SAMPLE)) == SAMPLE


def test_no_front_matter() -> None:
    text = "# Solo titolo\n\nCorpo\n"
    doc = parse(text)
    assert doc.meta == {} and doc.body == text
    assert render(doc) == text


def test_horizontal_rule_is_not_front_matter() -> None:
    text = "Intro\n\n---\n\nAltro\n"
    assert parse(text).meta == {}
    assert render(parse(text)) == text


def test_unterminated_front_matter_is_plain_body() -> None:
    text = "---\ntitle: x\nnessuna chiusura\n"
    doc = parse(text)
    assert doc.meta == {} and doc.body == text


def test_empty_front_matter() -> None:
    doc = parse("---\n---\nCorpo\n")
    assert doc.meta == {} and doc.body == "Corpo\n"


def test_crlf_input_is_supported() -> None:
    doc = parse("---\r\ntitle: A\r\n---\r\nCorpo\r\n")
    assert doc.meta["title"] == "A"


def test_invalid_yaml_raises() -> None:
    with pytest.raises(FrontMatterError):
        parse("---\ntitle: [unclosed\n---\nx\n")


def test_non_mapping_front_matter_raises() -> None:
    with pytest.raises(FrontMatterError):
        parse("---\n- a\n- b\n---\nx\n")


def test_updating_meta_keeps_other_keys_and_order() -> None:
    doc = parse(SAMPLE)
    doc.meta["title"] = "Nuovo"
    out = render(doc)
    assert out.startswith("---\ntitle: Nuovo\ntono: neutro")
    assert "# facoltativo" in out and out.endswith("Testo.\n")


def test_adding_front_matter_to_plain_file() -> None:
    doc = parse("Corpo\n")
    doc.meta["title"] = "T"
    assert render(doc) == "---\ntitle: T\n---\nCorpo\n"
