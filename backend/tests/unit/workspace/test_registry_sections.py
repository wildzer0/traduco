import shutil
from pathlib import Path

import pytest

from app.core.workspace import ops
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import create_project
from app.core.workspace.registry import create_in_workspaces, list_projects, project_root
from app.core.workspace.sections import ConflictError, read_section, write_section

EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "progetto-esempio"


# --- registry --------------------------------------------------------------------------------


def test_lists_only_folders_with_a_manifest(tmp_path: Path) -> None:
    create_project(tmp_path / "uno", "Uno", "it", "en")
    (tmp_path / "vuota").mkdir()
    (tmp_path / "file.txt").write_text("x")
    (tmp_path / ".nascosta").mkdir()
    assert [(p.id, p.nome) for p in list_projects(tmp_path)] == [("uno", "Uno")]


def test_missing_workspaces_dir_lists_nothing(tmp_path: Path) -> None:
    assert list_projects(tmp_path / "nope") == []


def test_broken_manifest_does_not_break_the_list(tmp_path: Path) -> None:
    create_project(tmp_path / "ok", "Ok", "it", "en")
    (tmp_path / "rotto").mkdir()
    (tmp_path / "rotto" / "progetto.yaml").write_text("nome: [unclosed")
    assert [p.id for p in list_projects(tmp_path)] == ["ok"]


def test_create_generates_unique_ids(tmp_path: Path) -> None:
    a = create_in_workspaces(tmp_path, "Manuale X", "it", "en")
    b = create_in_workspaces(tmp_path, "Manuale X", "it", "en")
    assert (a, b) == ("manuale-x", "manuale-x-2")


def test_create_from_example_copies_content_without_runtime_artifacts(tmp_path: Path) -> None:
    (tmp_path / "ex").mkdir()
    shutil.copytree(EXAMPLE, tmp_path / "ex" / "progetto-esempio")
    (tmp_path / "ex" / "progetto-esempio" / ".traduco").mkdir()
    (tmp_path / "ex" / "progetto-esempio" / ".traduco" / "tm.sqlite").write_text("x")
    pid = create_in_workspaces(
        tmp_path / "ws", None, "it", "en", example=tmp_path / "ex" / "progetto-esempio"
    )
    root = tmp_path / "ws" / pid
    assert pid == "progetto-esempio"
    assert (root / "capitoli/01-introduzione/01-scopo.md").is_file()
    assert not (root / ".traduco").exists()


@pytest.mark.parametrize("bad", ["", "..", "a/b", "a\\b", ".hidden", "x" * 200, "con spazio"])
def test_project_root_rejects_bad_ids(tmp_path: Path, bad: str) -> None:
    with pytest.raises(WorkspaceError) as exc:
        project_root(tmp_path, bad)
    assert exc.value.code in {"invalid_path", "not_found"}


def test_project_root_requires_manifest(tmp_path: Path) -> None:
    (tmp_path / "vuota").mkdir()
    with pytest.raises(WorkspaceError) as exc:
        project_root(tmp_path, "vuota")
    assert exc.value.code == "not_found"
    create_project(tmp_path / "ok", "Ok", "it", "en")
    assert project_root(tmp_path, "ok") == tmp_path / "ok"


# --- sections --------------------------------------------------------------------------------


@pytest.fixture
def section(tmp_path: Path) -> tuple[Path, str]:
    root = create_project(tmp_path / "p", "P", "it", "en")
    return root, ops.create_section(root, ops.create_chapter(root, "A"), "S")


def test_read_returns_content_and_hash(section: tuple[Path, str]) -> None:
    root, rel = section
    text, digest = read_section(root, rel)
    assert text.startswith("---\ntitle: S") and digest.startswith("sha256:")
    assert read_section(root, rel)[1] == digest


def test_write_with_matching_hash_updates_and_returns_new_hash(section: tuple[Path, str]) -> None:
    root, rel = section
    _, h0 = read_section(root, rel)
    h1 = write_section(root, rel, "# Nuovo\n", h0)
    assert h1 != h0 and read_section(root, rel) == ("# Nuovo\n", h1)


def test_write_with_stale_hash_conflicts_and_keeps_disk_content(section: tuple[Path, str]) -> None:
    root, rel = section
    _, h0 = read_section(root, rel)
    (root / rel).write_text("modificato fuori dall'app\n", encoding="utf-8")
    with pytest.raises(ConflictError) as exc:
        write_section(root, rel, "mia versione\n", h0)
    assert exc.value.current_hash == read_section(root, rel)[1]
    assert (root / rel).read_text(encoding="utf-8") == "modificato fuori dall'app\n"


def test_unicode_and_newlines_are_preserved(section: tuple[Path, str]) -> None:
    root, rel = section
    _, h = read_section(root, rel)
    content = "Perché «così» è — ok ✓\r\nriga\n"
    write_section(root, rel, content, h)
    assert (root / rel).read_bytes() == content.encode("utf-8")


def test_only_markdown_sections_are_accessible(section: tuple[Path, str]) -> None:
    root, _ = section
    (root / "capitoli/01-a/note.txt").write_text("x")
    for bad in ("capitoli/01-a/note.txt", "capitoli/01-a", "progetto.yaml"):
        with pytest.raises(WorkspaceError):
            read_section(root, bad)


def test_non_utf8_file_is_reported(section: tuple[Path, str]) -> None:
    root, rel = section
    (root / rel).write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(WorkspaceError) as exc:
        read_section(root, rel)
    assert exc.value.code == "unreadable"
