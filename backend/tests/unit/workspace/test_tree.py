from pathlib import Path

from app.core.workspace.tree import Node, build_tree, humanize

EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "progetto-esempio"


def flat(nodes: list[Node], depth: int = 0) -> list[tuple[int, str, str, str]]:
    out: list[tuple[int, str, str, str]] = []
    for n in nodes:
        out.append((depth, n.kind, n.name, n.title))
        out += flat(n.children, depth + 1)
    return out


def test_example_tree() -> None:
    assert flat(build_tree(EXAMPLE)) == [
        (0, "chapter", "01-introduzione", "Introduzione"),
        (1, "section", "01-scopo.md", "Scopo del documento"),
        (1, "section", "02-ambito.md", "Ambito di applicazione"),
        (0, "chapter", "02-installazione", "Installazione"),
        (1, "section", "01-requisiti.md", "Requisiti"),
        (1, "chapter", "02-procedura", "Procedura"),
        (2, "section", "01-montaggio.md", "Montaggio"),
        (1, "section", "03-collaudo.md", "Collaudo"),
    ]


def test_paths_are_posix_relative_to_project() -> None:
    first = build_tree(EXAMPLE)[0]
    assert first.path == "capitoli/01-introduzione"
    assert first.children[0].path == "capitoli/01-introduzione/01-scopo.md"


def make(root: Path, rel: str, text: str = "") -> None:
    f = root / "capitoli" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def test_title_precedence_front_matter_then_heading_then_filename(tmp_path: Path) -> None:
    make(tmp_path, "01-a/01-x.md", "---\ntitle: Dal front matter\n---\n# Heading\n")
    make(tmp_path, "01-a/02-y.md", "Intro\n\n# Dal titolo\n")
    make(tmp_path, "01-a/03-z-file_name.md", "senza titoli\n")
    titles = [n.title for n in build_tree(tmp_path)[0].children]
    assert titles == ["Dal front matter", "Dal titolo", "Z file name"]


def test_heading_inside_code_fence_is_ignored(tmp_path: Path) -> None:
    make(tmp_path, "01-a/01-x.md", "```bash\n# commento\n```\n")
    assert build_tree(tmp_path)[0].children[0].title == "X"


def test_broken_front_matter_does_not_break_the_tree(tmp_path: Path) -> None:
    make(tmp_path, "01-a/01-x.md", "---\ntitle: [oops\n---\n# Titolo valido\n")
    assert build_tree(tmp_path)[0].children[0].title == "Titolo valido"


def test_ignores_img_hidden_and_underscore_entries(tmp_path: Path) -> None:
    make(tmp_path, "01-a/01-x.md", "")
    make(tmp_path, "01-a/img/pic.png", "")
    make(tmp_path, "01-a/_bozza.md", "")
    make(tmp_path, "01-a/.nascosto.md", "")
    make(tmp_path, "01-a/note.txt", "")
    make(tmp_path, "_archivio/01-x.md", "")
    make(tmp_path, "radice.md", "")
    names = flat(build_tree(tmp_path))
    assert [n[2] for n in names] == ["01-a", "01-x.md"]


def test_chapter_title_from_capitolo_yaml(tmp_path: Path) -> None:
    make(tmp_path, "01-a/_capitolo.yaml", "title: Titolo capitolo\n")
    make(tmp_path, "01-a/01-x.md", "")
    assert build_tree(tmp_path)[0].title == "Titolo capitolo"


def test_depth_is_limited_to_two_sublevels(tmp_path: Path) -> None:
    make(tmp_path, "01-a/01-b/01-c/01-d/01-deep.md", "")
    make(tmp_path, "01-a/01-b/01-c/01-ok.md", "")
    names = [n[2] for n in flat(build_tree(tmp_path))]
    assert "01-ok.md" in names and "01-deep.md" not in names and "01-d" not in names


def test_unprefixed_entries_sort_after_prefixed(tmp_path: Path) -> None:
    make(tmp_path, "01-a/zeta.md", "")
    make(tmp_path, "01-a/02-b.md", "")
    make(tmp_path, "01-a/01-a.md", "")
    assert [n.name for n in build_tree(tmp_path)[0].children] == ["01-a.md", "02-b.md", "zeta.md"]


def test_missing_capitoli_folder_gives_empty_tree(tmp_path: Path) -> None:
    assert build_tree(tmp_path) == []


def test_humanize() -> None:
    assert humanize("02-procedura-di_montaggio.md") == "Procedura di montaggio"
    assert humanize("README") == "README"


def test_a_folder_that_vanishes_while_reading_is_skipped(tmp_path: Path) -> None:
    """Reordering renames folders while GET /tree may be walking them (seen in the e2e logs)."""
    from app.core.workspace.tree import _children

    assert _children(tmp_path / "capitoli" / "02-gone", tmp_path, 2) == []
