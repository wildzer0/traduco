from pathlib import Path

import pytest

from app.core.importer import apply
from app.core.importer.align import align, plain
from app.core.segmentation.segmenter import segment
from app.core.workspace.errors import WorkspaceError


def test_plain_ignores_markdown_fields_and_quotes() -> None:
    assert plain("**Codice** {{c}} “x”", {"c": "D-1"}) == 'codice d-1 "x"'


def test_modified_added_and_deleted_are_told_apart() -> None:
    exported = ["cover", "uno due tre", "quattro", "cinque sei", "end"]
    found = ["cover", "uno due tre!", "nuovo paragrafo", "cinque sei", "end"]
    kinds = [(c.kind, c.old, c.new) for c in align(exported, found)]
    assert ("modified", 1, 1) in kinds
    assert any(k == "added" or k == "modified" for k, _, _ in kinds)


def test_template_parts_at_the_edges_are_ignored() -> None:
    assert align(["a", "b", "c"], ["x", "b", "c", "y"]) == []


def test_a_rewritten_paragraph_stays_one_modification() -> None:
    changes = align(["a", "testo originale lungo", "c"], ["a", "tutt'altro", "c"])
    assert [(c.kind, c.old, c.new) for c in changes] == [("modified", 1, 1)]


@pytest.fixture
def section(tmp_path: Path) -> tuple[Path, str]:
    rel = "capitoli/01-a/01-s.md"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    path.write_text("# S\n\nPrimo.\n\n- uno\n- due\n\nUltimo.\n", encoding="utf-8")
    return tmp_path, rel


def keys(root: Path, rel: str) -> dict[str, str]:
    return {k: s.source for k, s in segment((root / rel).read_text()).by_key().items()}


def test_apply_modified_replaces_one_segment(section: tuple[Path, str]) -> None:
    root, rel = section
    key = next(k for k, v in keys(root, rel).items() if v == "Primo.")
    assert apply.apply_modified(root, "en", rel, key, "Primo, rivisto.", None) is True
    assert "Primo, rivisto." in (root / rel).read_text() and "Ultimo." in (root / rel).read_text()


def test_apply_added_after_a_list_item_keeps_the_list(section: tuple[Path, str]) -> None:
    root, rel = section
    key = next(k for k, v in keys(root, rel).items() if v == "uno")
    apply.apply_added(root, "en", rel, key, "uno e mezzo", None)
    assert "- uno\n- uno e mezzo\n- due" in (root / rel).read_text()


def test_apply_deleted_removes_the_paragraph_cleanly(section: tuple[Path, str]) -> None:
    root, rel = section
    key = next(k for k, v in keys(root, rel).items() if v == "Primo.")
    apply.apply_deleted(root, rel, key)
    text = (root / rel).read_text()
    assert "Primo." not in text and "\n\n\n" not in text


def test_a_heading_of_the_template_cannot_be_applied(section: tuple[Path, str]) -> None:
    root, rel = section
    with pytest.raises(WorkspaceError):
        apply.apply_modified(root, "en", rel, "p:999", "x", None)
