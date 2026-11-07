"""Structural checks of examples/progetto-esempio (the M0 acceptance fixture)."""

import re
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "progetto-esempio"
SECTIONS = sorted((EXAMPLE / "capitoli").rglob("*.md"))
PREFIX = re.compile(r"^\d{2}-")


def test_two_chapters_five_sections() -> None:
    chapters = [p for p in (EXAMPLE / "capitoli").iterdir() if p.is_dir()]
    assert len(chapters) == 2
    assert len(SECTIONS) == 5


def test_ordering_prefixes_and_depth() -> None:
    for section in SECTIONS:
        parts = section.relative_to(EXAMPLE / "capitoli").parts
        assert len(parts) <= 3, "chapters allow at most 2 sub-levels"
        for part in parts[:-1]:
            assert PREFIX.match(part), part
        assert PREFIX.match(parts[-1]), parts[-1]


@pytest.mark.parametrize("section", SECTIONS, ids=lambda p: p.name)
def test_front_matter_has_title(section: Path) -> None:
    lines = section.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    assert any(line.startswith("title:") for line in lines[1:end])


def test_contains_table_image_diagram_and_protected_items() -> None:
    text = "\n".join(s.read_text(encoding="utf-8") for s in SECTIONS)
    assert re.search(r"^\| --- \|", text, re.MULTILINE), "pipe table"
    assert "```mermaid" in text
    assert "{{codice_documento}}" in text
    assert "https://example.com" in text
    assert "[^1]" in text


def test_referenced_images_exist_and_are_png() -> None:
    refs = 0
    for section in SECTIONS:
        for target in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", section.read_text(encoding="utf-8")):
            image = section.parent / target
            assert image.is_file(), target
            assert image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
            refs += 1
    assert refs >= 1


def test_glossary_has_five_entries_and_a_do_not_translate_one() -> None:
    glossary = (EXAMPLE / "glossario.yaml").read_text(encoding="utf-8")
    assert len(re.findall(r"^- sorgente:", glossary, re.MULTILINE)) == 5
    assert "non_tradurre: true" in glossary


def test_project_manifest_declares_languages() -> None:
    manifest = (EXAMPLE / "progetto.yaml").read_text(encoding="utf-8")
    assert "lingua_sorgente: it" in manifest
    assert "lingua_ufficiale: en" in manifest
