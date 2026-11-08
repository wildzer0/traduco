import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "make_big_project", Path(__file__).resolve().parents[1] / "make-big-project.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod  # dataclasses look their module up here
spec.loader.exec_module(mod)


def test_the_project_is_valid_and_the_same_every_time(tmp_path: Path) -> None:
    from app.core.trace import requirements
    from app.core.workspace.manifest import load_project
    from app.core.workspace.tree import build_tree

    a, b = tmp_path / "a", tmp_path / "b"
    first = mod.build(a, 30, seed=1)
    mod.build(b, 30, seed=1)
    assert sorted(p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file()) == sorted(
        p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file()
    )
    assert all(
        (a / p.relative_to(a)).read_text() == (b / p.relative_to(a)).read_text()
        for p in a.rglob("*.md")
    )

    def sections(nodes: list) -> int:  # type: ignore[type-arg]
        return sum(1 if n.kind == "section" else sections(n.children) for n in nodes)

    assert sections(build_tree(a)) == first["sections"] >= 30 - 5
    project = load_project(a)
    assert (project.lingua_sorgente, project.lingua_ufficiale) == ("it", "en")
    assert (a / "template" / "manuale.docx").is_file()
    found = requirements.scan(a)
    assert found["requirements"] and not [p for p in found["problems"] if p["kind"] == "undefined"]


def test_the_text_has_what_makes_a_model_struggle(tmp_path: Path) -> None:
    mod.build(tmp_path, 40, seed=3)
    text = "\n".join(p.read_text() for p in sorted((tmp_path / "capitoli").rglob("*.md")))
    for needle in (
        "pompa di mandata",
        "**ACME Pump**",
        "m³/h",
        "| Parametro |",
        "[^1]",
        "`",
        "{{codice_documento}}",
        "```mermaid",
        "SP-REQ-",
    ):
        assert needle in text, needle
    assert (
        text.count("Al termine dell'operazione registrare") > 1
    )  # repeated on purpose: the memory
    glossary = (tmp_path / "glossario.yaml").read_text()
    assert "discharge pump" in glossary and "non_tradurre: true" in glossary


def test_a_bigger_request_gives_a_bigger_project(tmp_path: Path) -> None:
    small = mod.build(tmp_path / "s", 20, seed=1)
    large = mod.build(tmp_path / "l", 110, seed=1)
    assert large["sections"] > 4 * small["sections"] and large["words"] > 4 * small["words"]
