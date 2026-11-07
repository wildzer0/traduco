import os
from pathlib import Path

import pytest

from app.core.workspace import ops
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.frontmatter import parse
from app.core.workspace.manifest import create_project
from app.core.workspace.tree import Node, build_tree


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return create_project(tmp_path / "p", "Prova", "it", "en")


def names(nodes: list[Node]) -> list[str]:
    out: list[str] = []
    for n in nodes:
        out.append(n.name)
        out += [f"  {c}" for c in names(n.children)]
    return out


def code_of(exc: pytest.ExceptionInfo[WorkspaceError]) -> str:
    return exc.value.code


# --- create ----------------------------------------------------------------------------------


def test_create_chapters_and_sections_get_sequential_prefixes(root: Path) -> None:
    a = ops.create_chapter(root, "Introduzione")
    b = ops.create_chapter(root, "Più dettagli")
    s1 = ops.create_section(root, a, "Scopo del documento")
    s2 = ops.create_section(root, a, "Ambito")
    assert (a, b) == ("capitoli/01-introduzione", "capitoli/02-piu-dettagli")
    assert (s1, s2) == (
        "capitoli/01-introduzione/01-scopo-del-documento.md",
        "capitoli/01-introduzione/02-ambito.md",
    )
    assert parse((root / s1).read_text(encoding="utf-8")).meta["title"] == "Scopo del documento"
    assert [n.title for n in build_tree(root)] == ["Introduzione", "Più dettagli"]


def test_new_item_goes_after_the_highest_prefix_even_with_gaps(root: Path) -> None:
    ops.create_chapter(root, "A")
    (root / "capitoli" / "07-x").mkdir()
    assert ops.create_chapter(root, "B") == "capitoli/08-b"


def test_subchapters_up_to_two_levels(root: Path) -> None:
    a = ops.create_chapter(root, "A")
    b = ops.create_chapter(root, "B", parent=a)
    c = ops.create_chapter(root, "C", parent=b)
    assert c == "capitoli/01-a/01-b/01-c"
    with pytest.raises(WorkspaceError) as exc:
        ops.create_chapter(root, "D", parent=c)
    assert code_of(exc) == "depth_exceeded"


def test_sections_need_a_chapter(root: Path) -> None:
    with pytest.raises(WorkspaceError) as exc:
        ops.create_section(root, None, "Orfana")
    assert code_of(exc) == "invalid_path"


def test_create_in_missing_parent(root: Path) -> None:
    with pytest.raises(WorkspaceError) as exc:
        ops.create_section(root, "capitoli/09-nope", "X")
    assert code_of(exc) == "not_found"


# --- path safety -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "../progetto.yaml",
        "/etc/passwd",
        "capitoli/../progetto.yaml",
        "progetto.yaml",
        "",
        "capitoli/.hidden",
    ],
)
def test_paths_outside_the_chapters_tree_are_rejected(root: Path, bad: str) -> None:
    ops.create_chapter(root, "A")
    with pytest.raises(WorkspaceError) as exc:
        ops.delete(root, bad)
    assert code_of(exc) in {"invalid_path", "not_found"}
    assert (root / "progetto.yaml").exists()


def test_symlink_escape_is_rejected(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("x")
    os.symlink(outside, root / "capitoli" / "01-link")
    with pytest.raises(WorkspaceError):
        ops.delete(root, "capitoli/01-link/secret.md")
    assert (outside / "secret.md").exists()


# --- rename ----------------------------------------------------------------------------------


def test_rename_section_keeps_prefix_updates_title_and_body(root: Path) -> None:
    ch = ops.create_chapter(root, "A")
    sec = ops.create_section(root, ch, "Vecchio")
    path = root / sec
    path.write_text(path.read_text(encoding="utf-8") + "\nCorpo **intatto**.\n", encoding="utf-8")
    new = ops.rename(root, sec, "Nuovo titolo")
    assert new == {sec: "capitoli/01-a/01-nuovo-titolo.md"}
    doc = parse((root / new[sec]).read_text(encoding="utf-8"))
    assert doc.meta["title"] == "Nuovo titolo" and doc.body.endswith("Corpo **intatto**.\n")
    assert not (root / sec).exists()


def test_rename_section_without_front_matter_adds_title(root: Path) -> None:
    ch = ops.create_chapter(root, "A")
    (root / ch / "01-x.md").write_text("# Titolo\n\nTesto\n", encoding="utf-8")
    new = ops.rename(root, f"{ch}/01-x.md", "Altro")
    text = (root / new[f"{ch}/01-x.md"]).read_text(encoding="utf-8")
    assert text == "---\ntitle: Altro\n---\n# Titolo\n\nTesto\n"


def test_rename_chapter_moves_folder_and_updates_title(root: Path) -> None:
    ch = ops.create_chapter(root, "A")
    ops.create_section(root, ch, "S")
    new = ops.rename(root, ch, "Capitolo Uno")
    assert new == {ch: "capitoli/01-capitolo-uno"}
    assert build_tree(root)[0].title == "Capitolo Uno"
    assert build_tree(root)[0].children[0].title == "S"


def test_rename_to_same_slug_only_changes_title(root: Path) -> None:
    ch = ops.create_chapter(root, "Alfa")
    assert ops.rename(root, ch, "ALFA") == {}
    assert build_tree(root)[0].title == "ALFA"


def test_rename_collision(root: Path) -> None:
    ch = ops.create_chapter(root, "A")
    (root / ch / "01-x.md").write_text("", encoding="utf-8")
    (root / ch / "01-y.md").write_text("", encoding="utf-8")  # same prefix, hand made
    with pytest.raises(WorkspaceError) as exc:
        ops.rename(root, f"{ch}/01-y.md", "x")
    assert code_of(exc) == "exists"


# --- reorder ---------------------------------------------------------------------------------


def test_reorder_renumbers_files_and_contents_follow(root: Path) -> None:
    ch = ops.create_chapter(root, "A")
    for t in ("Uno", "Due", "Tre"):
        ops.create_section(root, ch, t)
    mapping = ops.reorder(root, ch, ["03-tre.md", "01-uno.md", "02-due.md"])
    assert mapping == {
        f"{ch}/03-tre.md": f"{ch}/01-tre.md",
        f"{ch}/01-uno.md": f"{ch}/02-uno.md",
        f"{ch}/02-due.md": f"{ch}/03-due.md",
    }
    assert [n.title for n in build_tree(root)[0].children] == ["Tre", "Uno", "Due"]
    assert not list((root / ch).glob(".traduco-tmp-*"))


def test_reorder_chapters_at_top_level_carries_images(root: Path) -> None:
    a, b = ops.create_chapter(root, "A"), ops.create_chapter(root, "B")
    (root / a / "img").mkdir()
    (root / a / "img" / "p.png").write_bytes(b"png")
    ops.reorder(root, None, ["02-b", "01-a"])
    assert (root / "capitoli" / "02-a" / "img" / "p.png").read_bytes() == b"png"
    assert (root / b).exists() is False and (root / "capitoli" / "01-b").is_dir()


def test_reorder_requires_exactly_the_current_siblings(root: Path) -> None:
    ch = ops.create_chapter(root, "A")
    ops.create_section(root, ch, "Uno")
    ops.create_section(root, ch, "Due")
    for bad in (
        ["01-uno.md"],
        ["01-uno.md", "02-due.md", "03-extra.md"],
        ["01-uno.md", "01-uno.md"],
    ):
        with pytest.raises(WorkspaceError) as exc:
            ops.reorder(root, ch, bad)
        assert code_of(exc) == "invalid_order"


def test_reorder_ignores_non_content_entries(root: Path) -> None:
    ch = ops.create_chapter(root, "A")
    ops.create_section(root, ch, "Uno")
    (root / ch / "img").mkdir()
    ops.reorder(root, ch, ["01-uno.md"])
    assert (root / ch / "_capitolo.yaml").exists() and (root / ch / "img").is_dir()


# --- move ------------------------------------------------------------------------------------


def test_move_section_to_another_chapter_at_index(root: Path) -> None:
    a, b = ops.create_chapter(root, "A"), ops.create_chapter(root, "B")
    s = ops.create_section(root, a, "Mobile")
    ops.create_section(root, b, "Primo")
    ops.create_section(root, b, "Secondo")
    new = ops.move(root, s, parent=b, index=1).path
    assert new == "capitoli/02-b/02-mobile.md"
    assert [n.title for n in build_tree(root)[1].children] == ["Primo", "Mobile", "Secondo"]
    assert build_tree(root)[0].children == []


def test_move_to_the_end_when_index_is_none(root: Path) -> None:
    a, b = ops.create_chapter(root, "A"), ops.create_chapter(root, "B")
    s = ops.create_section(root, a, "Mobile")
    ops.create_section(root, b, "Primo")
    assert ops.move(root, s, parent=b).path == "capitoli/02-b/02-mobile.md"


def test_move_within_same_parent_is_a_reorder(root: Path) -> None:
    a = ops.create_chapter(root, "A")
    ops.create_section(root, a, "Uno")
    s2 = ops.create_section(root, a, "Due")
    assert ops.move(root, s2, parent=a, index=0).path == f"{a}/01-due.md"
    assert [n.title for n in build_tree(root)[0].children] == ["Due", "Uno"]


def test_move_chapter_to_top_level_and_into_another(root: Path) -> None:
    a, b = ops.create_chapter(root, "A"), ops.create_chapter(root, "B")
    sub = ops.create_chapter(root, "Sub", parent=a)
    top = ops.move(root, sub, parent=None).path
    assert top == "capitoli/03-sub"
    assert ops.move(root, top, parent=b).path == "capitoli/02-b/01-sub"


def test_cannot_move_a_chapter_into_itself_or_its_descendants(root: Path) -> None:
    a = ops.create_chapter(root, "A")
    sub = ops.create_chapter(root, "Sub", parent=a)
    for target in (a, sub):
        with pytest.raises(WorkspaceError) as exc:
            ops.move(root, a, parent=target)
        assert code_of(exc) == "invalid_move"


def test_move_respects_depth_limit(root: Path) -> None:
    a = ops.create_chapter(root, "A")
    b = ops.create_chapter(root, "B", parent=a)
    c = ops.create_chapter(root, "C", parent=b)
    x = ops.create_chapter(root, "X")
    ops.create_chapter(root, "Y", parent=x)  # X has depth 2
    with pytest.raises(WorkspaceError) as exc:
        ops.move(root, x, parent=c)
    assert code_of(exc) == "depth_exceeded"


def test_sections_cannot_move_to_top_level(root: Path) -> None:
    a = ops.create_chapter(root, "A")
    s = ops.create_section(root, a, "S")
    with pytest.raises(WorkspaceError) as exc:
        ops.move(root, s, parent=None)
    assert code_of(exc) == "invalid_move"


def test_failed_move_leaves_everything_in_place(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = ops.create_chapter(root, "A"), ops.create_chapter(root, "B")
    s = ops.create_section(root, a, "S")
    ops.create_section(root, b, "T")

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("boom")

    monkeypatch.setattr(ops, "apply_renames", boom)
    with pytest.raises(OSError):
        ops.move(root, s, parent=b, index=0)
    monkeypatch.undo()
    assert (root / s).exists()
    assert [n.name for n in build_tree(root)[1].children] == ["01-t.md"]


# --- delete ----------------------------------------------------------------------------------


def test_delete_moves_to_trash_keeping_relative_path(root: Path) -> None:
    ch = ops.create_chapter(root, "A")
    s = ops.create_section(root, ch, "S")
    trashed = ops.delete(root, ch)
    assert not (root / ch).exists()
    assert trashed.startswith(".traduco/cestino/")
    assert (root / trashed / ch / "01-s.md").is_file()
    assert s


def test_delete_missing_node(root: Path) -> None:
    with pytest.raises(WorkspaceError) as exc:
        ops.delete(root, "capitoli/01-nope")
    assert code_of(exc) == "not_found"


def test_two_deletes_of_same_name_do_not_collide(root: Path) -> None:
    for _ in range(2):
        ch = ops.create_chapter(root, "Stesso")
        ops.delete(root, ch)
    entries = list((root / ".traduco" / "cestino").iterdir())
    assert len(entries) == 2


def test_move_reports_every_renamed_path_so_clients_can_follow(root: Path) -> None:
    a, b = ops.create_chapter(root, "A"), ops.create_chapter(root, "B")
    s = ops.create_section(root, a, "Mobile")
    first = ops.create_section(root, b, "Primo")
    moved = ops.move(root, s, parent=b, index=0)
    assert moved.renamed == {s: "capitoli/02-b/01-mobile.md", first: "capitoli/02-b/02-primo.md"}
    same = ops.move(root, "capitoli/02-b/02-primo.md", parent=b, index=0)
    assert same.renamed == {
        "capitoli/02-b/02-primo.md": "capitoli/02-b/01-primo.md",
        "capitoli/02-b/01-mobile.md": "capitoli/02-b/02-mobile.md",
    }
