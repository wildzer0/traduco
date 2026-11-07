from pathlib import Path

import pytest

from app.core.skeleton import generate
from app.core.skeleton.check import check, create_missing
from app.core.skeleton.model import SkeletonError, parse_skeleton
from app.core.workspace import ops
from app.core.workspace.manifest import create_project
from app.core.workspace.sections import read_section, write_section
from app.core.workspace.tree import Node, build_tree

TEXT = """\
nome: Mini
nodi:
  - id: intro
    titolo: { it: Introduzione, en: Introduction }
    nodi:
      - id: scopo
        titolo: Scopo
        guida: Spiega lo scopo.
      - id: ambito
        titolo: Ambito
        obbligatorio: false
  - id: req
    titolo: Requisiti
    nodi:
      - id: funz
        titolo: Funzionali
"""
ECSS = Path(__file__).resolve().parents[4] / "examples" / "scheletri" / "ecss-e-st-10-06c.yaml"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    create_project(tmp_path, "P", "it", "en")
    return tmp_path


def shape(root: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def walk(nodes: list[Node]) -> None:
        for n in nodes:
            out.append((n.kind, n.path))
            walk(n.children)

    walk(build_tree(root))
    return out


def test_bundled_ecss_example_is_valid() -> None:
    sk = parse_skeleton(ECSS.read_text(encoding="utf-8"))
    assert len(sk.walk()) > 10


def test_creates_the_expected_structure(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    paths = generate.apply_skeleton(project, sk, "it")
    assert shape(project) == [
        ("chapter", "capitoli/01-introduzione"),
        ("section", "capitoli/01-introduzione/01-scopo.md"),
        ("section", "capitoli/01-introduzione/02-ambito.md"),
        ("chapter", "capitoli/02-requisiti"),
        ("section", "capitoli/02-requisiti/01-funzionali.md"),
    ]
    assert paths["scopo"] == "capitoli/01-introduzione/01-scopo.md"
    text, _ = read_section(project, paths["scopo"])
    assert "scheletro: scopo" in text and "<!-- Guida: Spiega lo scopo. -->" in text


def test_title_uses_the_requested_language() -> None:
    sk = parse_skeleton(TEXT)
    assert sk.nodi[0].title("en") == "Introduction" and sk.nodi[0].title("de") == "Introduzione"


def test_fresh_project_conforms_except_empty_sections(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    generate.apply_skeleton(project, sk, "it")
    report = check(project, sk, "it")
    status = {i.id: i.status for i in report.items}
    # sections only have the guide comment: mandatory ones are still empty
    assert status["scopo"] == "empty" and status["funz"] == "empty"
    assert status["intro"] == "ok" and status["ambito"] == "ok"  # optional: empty is fine
    assert not report.conform


def test_writing_content_makes_it_conform(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    paths = generate.apply_skeleton(project, sk, "it")
    for key in ("scopo", "funz"):
        text, h = read_section(project, paths[key])
        write_section(project, paths[key], text + "\nTesto vero.\n", h)
    assert check(project, sk, "it").conform


def test_deleting_a_mandatory_section_reports_it_missing(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    paths = generate.apply_skeleton(project, sk, "it")
    ops.delete(project, paths["scopo"])
    report = check(project, sk, "it")
    item = next(i for i in report.items if i.id == "scopo")
    assert item.status == "missing" and item.path is None and item.mandatory


def test_rename_keeps_conformity_because_the_id_is_in_the_file(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    paths = generate.apply_skeleton(project, sk, "it")
    ops.rename(project, paths["scopo"], "Finalità")
    item = next(i for i in check(project, sk, "it").items if i.id == "scopo")
    assert item.status != "missing" and item.path is not None


def test_extra_and_order(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    paths = generate.apply_skeleton(project, sk, "it")
    ops.create_section(project, "capitoli/01-introduzione", "Mia nota")
    ops.reorder(
        project, "capitoli/01-introduzione", ["02-ambito.md", "01-scopo.md", "03-mia-nota.md"]
    )
    report = check(project, sk, "it")
    assert report.extra == ["capitoli/01-introduzione/03-mia-nota.md"]
    states = {i.id: i.status for i in report.items}
    assert "out_of_order" in (states["scopo"], states["ambito"])
    del paths


def test_moving_a_section_to_another_chapter_is_misplaced(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    paths = generate.apply_skeleton(project, sk, "it")
    ops.move(project, paths["scopo"], "capitoli/02-requisiti")
    assert {i.id: i.status for i in check(project, sk, "it").items}["scopo"] == "misplaced"


def test_create_missing_restores_nodes_in_order(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    generate.apply_skeleton(project, sk, "it")
    ops.delete(project, "capitoli/01-introduzione/01-scopo.md")
    created = create_missing(project, sk, "it")
    assert len(created) == 1
    assert [p for k, p in shape(project) if k == "section"][0].endswith("scopo.md")
    assert next(i for i in check(project, sk, "it").items if i.id == "scopo").status != "missing"


def test_create_missing_skips_optional_unless_asked(project: Path) -> None:
    sk = parse_skeleton(TEXT)
    generate.apply_skeleton(project, sk, "it")
    ops.delete(project, "capitoli/01-introduzione/02-ambito.md")
    assert create_missing(project, sk, "it") == []
    assert len(create_missing(project, sk, "it", include_optional=True)) == 1


@pytest.mark.parametrize(
    ("text", "line", "fragment"),
    [
        ("nome: X\nnodi:\n  - id: a\n    titolo: A\n    nodi: [\n", None, ""),  # YAML syntax
        ("nome: X\nnodi: []\n", 2, "nodi"),
        ("nodi:\n  - id: a\n", 1, "nome"),
        (
            "nome: X\nnodi:\n  - id: a\n    titolo: A\n    nodi:\n"
            "      - id: a\n        titolo: B\n",
            6,
            "duplicato",
        ),
        ("nome: X\nnodi:\n  - id: a\n    titolo: A\n", 3, "primo livello"),
        (
            "nome: X\nnodi:\n  - id: 'a b'\n    titolo: A\n    nodi:\n      - {id: c, titolo: C}\n",
            3,
            "id non valido",
        ),
        (
            "nome: X\nnodi:\n  - id: a\n    titolo: A\n    colore: rosso\n"
            "    nodi: [{id: b, titolo: B}]\n",
            5,
            "colore",
        ),
        ("- a\n- b\n", 1, "mappa"),
    ],
)
def test_invalid_files_report_line_and_reason(text: str, line: int | None, fragment: str) -> None:
    with pytest.raises(SkeletonError) as info:
        parse_skeleton(text)
    if line is not None:
        assert info.value.line == line, str(info.value)
    assert fragment in info.value.reason


def test_too_many_levels() -> None:
    text = (
        "nome: X\nnodi:\n  - id: a\n    titolo: A\n    nodi:\n      - id: b\n        titolo: B\n"
        "        nodi:\n          - id: c\n            titolo: C\n            nodi:\n"
        "              - id: d\n                titolo: D\n                nodi:\n"
        "                  - {id: e, titolo: E}\n"
    )
    with pytest.raises(SkeletonError, match="livelli"):
        parse_skeleton(text)
