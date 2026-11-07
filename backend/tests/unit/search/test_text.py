from pathlib import Path

from app.core.search import text
from app.core.translation import store
from app.core.workspace import ops
from app.core.workspace.manifest import create_project
from app.core.workspace.sections import read_section, write_section


def project(tmp_path: Path) -> tuple[Path, str]:
    root = create_project(tmp_path / "p", "Manuale", "it", "en")
    rel = ops.create_section(root, ops.create_chapter(root, "Intro"), "Scopo")
    write_section(
        root,
        rel,
        "# Scopo\n\nLa qualità del sistema è verificata.\n\nLa pompa parte subito.\n",
        read_section(root, rel)[1],
    )
    return root, rel


def test_finds_text_without_caring_for_case_or_accents(tmp_path: Path) -> None:
    root, rel = project(tmp_path)
    [hit] = text.search(root, "QUALITA", "en")
    assert hit["path"] == rel and hit["field"] == "source" and hit["match"] == "qualità"
    assert hit["before"].endswith("La ") and hit["after"].startswith(" del sistema")


def test_translations_are_searched_too(tmp_path: Path) -> None:
    root, rel = project(tmp_path)

    stored = store.SegmentFile(
        source_file_hash="x",
        segments=[store.StoredSegment("p:1", "h", "paragraph", target="The pump starts at once.")],
    )
    store.save(root, "en", rel, stored)
    [hit] = text.search(root, "pump", "en")
    assert hit["field"] == "translation" and hit["key"] == "p:1"


def test_short_queries_and_the_limit(tmp_path: Path) -> None:
    root, _ = project(tmp_path)
    assert text.search(root, "a", "en") == []
    assert len(text.search(root, "la ", "en", limit=1)) == 1
