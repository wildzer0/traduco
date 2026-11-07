from pathlib import Path

from app.core.trace import requirements
from app.core.workspace import ops
from app.core.workspace.manifest import create_project
from app.core.workspace.sections import read_section, write_section


def put(root: Path, rel: str, text: str) -> None:
    write_section(root, rel, text, read_section(root, rel)[1])


def test_definitions_references_and_problems(tmp_path: Path) -> None:
    root = create_project(tmp_path / "p", "Spec", "en", "it")
    chapter = ops.create_chapter(root, "Reqs")
    a = ops.create_section(root, chapter, "Functional")
    b = ops.create_section(root, chapter, "Design")
    put(
        root,
        a,
        "# Functional\n\n**FOO-REQ-00001** The system shall start.\n\n"
        "FOO-REQ-00002 The system shall stop, see FOO-REQ-00001.\n\n"
        "FOO-REQ-00002 Duplicate definition.\n\nFOO-REQ-00003 Never used.\n",
    )
    put(root, b, "# Design\n\nThe boot module covers FOO-REQ-00001 and FOO-REQ-00099.\n")
    found = requirements.scan(root)
    by_id = {r["id"]: r for r in found["requirements"]}
    assert set(by_id) == {"FOO-REQ-00001", "FOO-REQ-00002", "FOO-REQ-00003"}
    assert {r["path"] for r in by_id["FOO-REQ-00001"]["referenced_by"]} == {a, b}
    problems = {(p["kind"], p["id"]) for p in found["problems"]}
    assert problems == {
        ("duplicate", "FOO-REQ-00002"),
        ("undefined", "FOO-REQ-00099"),
        ("unreferenced", "FOO-REQ-00002"),
        ("unreferenced", "FOO-REQ-00003"),
    }


def test_plain_numbers_and_versions_are_not_identifiers(tmp_path: Path) -> None:
    root = create_project(tmp_path / "p", "Spec", "en", "it")
    rel = ops.create_section(root, ops.create_chapter(root, "C"), "S")
    put(root, rel, "# S\n\nSee RFC-2119 and ISO-9001 or version V-1.2 in 2026-11-07.\n")
    assert requirements.scan(root) == {"requirements": [], "problems": []}
