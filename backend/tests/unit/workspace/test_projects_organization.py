import json
from pathlib import Path

import pytest

from app.core.workspace import ops, organization, registry
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project, save_project
from app.core.workspace.sections import read_section, write_section


def make(ws: Path, name: str, author: str = "") -> str:
    project_id = registry.create_in_workspaces(ws, name, "it", "en")
    if author:
        root = ws / project_id
        p = load_project(root)
        p.metadati["autore"] = author
        save_project(root, p)
    return project_id


def test_folders_nest_and_names_are_unique_per_level(tmp_path: Path) -> None:
    clients = organization.create_folder(tmp_path, "Clienti")
    acme = organization.create_folder(tmp_path, "ACME", clients.id)
    organization.create_folder(tmp_path, "ACME")  # same name, different level: fine
    with pytest.raises(WorkspaceError, match="already a folder"):
        organization.create_folder(tmp_path, "acme", clients.id)
    org = organization.load(tmp_path)
    assert org.path(acme.id) == ["Clienti", "ACME"] and org.depth(acme.id) == 2
    for bad in ("", "a/b", "x" * 100):
        with pytest.raises(WorkspaceError):
            organization.create_folder(tmp_path, bad)


def test_a_folder_cannot_go_inside_itself_or_too_deep(tmp_path: Path) -> None:
    a = organization.create_folder(tmp_path, "A")
    b = organization.create_folder(tmp_path, "B", a.id)
    with pytest.raises(WorkspaceError, match="inside itself"):
        organization.update_folder(tmp_path, a.id, parent=b.id, move=True)
    with pytest.raises(WorkspaceError, match="inside itself"):
        organization.update_folder(tmp_path, a.id, parent=a.id, move=True)
    parent = None
    with pytest.raises(WorkspaceError, match="nested"):
        for n in range(20):
            parent = organization.create_folder(tmp_path, f"L{n}", parent).id
    moved = organization.update_folder(tmp_path, b.id, parent=None, move=True, name="B2")
    assert moved.genitore is None and moved.nome == "B2"


def test_deleting_a_folder_never_loses_a_project(tmp_path: Path) -> None:
    outer = organization.create_folder(tmp_path, "Esterna")
    inner = organization.create_folder(tmp_path, "Interna", outer.id)
    project = make(tmp_path, "Manuale")
    organization.set_project_folder(tmp_path, project, inner.id)
    organization.delete_folder(tmp_path, inner.id)  # its project goes up to "Esterna"
    assert organization.load(tmp_path).projects == {project: outer.id}
    organization.delete_folder(tmp_path, outer.id)  # and then to the top level
    assert organization.load(tmp_path).projects == {}
    assert [p.id for p in registry.list_projects(tmp_path)] == [project]


def test_a_damaged_organization_file_hides_nothing(tmp_path: Path) -> None:
    project = make(tmp_path, "Manuale")
    (tmp_path / organization.FILE).write_text("cartelle: [unclosed", encoding="utf-8")
    assert [p.id for p in registry.list_projects(tmp_path)] == [project]
    (tmp_path / organization.FILE).write_text(
        "cartelle: [{id: f-1, nome: A, genitore: f-gone}]\nprogetti: {manuale: f-gone}\n",
        encoding="utf-8",
    )
    assert organization.load(tmp_path).folders == [] and organization.load(tmp_path).projects == {}


def test_the_list_says_where_a_project_is_who_wrote_it_and_what_issue_it_is_at(
    tmp_path: Path,
) -> None:
    folder = organization.create_folder(tmp_path, "Clienti")
    project = make(tmp_path, "Manuale pompa", author="Mario Rossi")
    organization.set_project_folder(tmp_path, project, folder.id)
    root = tmp_path / project
    chapter = ops.create_chapter(root, "Intro")
    section = ops.create_section(root, chapter, "Scopo")
    write_section(root, section, "# Scopo\n\nTesto.\n", read_section(root, section)[1])
    issues = root / ".traduco" / "emissioni"
    for rev, at in (("1", "2026-11-01T10:00:00"), ("2", "2026-11-05T10:00:00")):
        (issues / rev).mkdir(parents=True)
        (issues / rev / "meta.json").write_text(
            json.dumps({"rev": rev, "data": f"2026-11-0{rev}", "created_at": at}), encoding="utf-8"
        )
    [info] = registry.list_projects(tmp_path)
    assert (info.cartella, info.percorso) == (folder.id, ["Clienti"])
    assert (
        info.autore == "Mario Rossi"
        and info.emissione == "2"
        and info.emissione_data == "2026-11-02"
    )
    assert info.sezioni == 1 and info.lingue == ["en"] and info.ultima_modifica.startswith("20")


def test_without_a_frozen_issue_the_revision_table_is_used(tmp_path: Path) -> None:
    project = make(tmp_path, "Manuale")
    root = tmp_path / project
    p = load_project(root)
    from datetime import date

    from app.core.workspace.manifest import Revision

    p.revisioni.append(Revision(rev="03", data=date(2026, 9, 1), descrizione="x"))
    save_project(root, p)
    assert registry.list_projects(tmp_path)[0].emissione == "03"


def test_a_copy_keeps_the_work_but_not_the_caches_and_goes_in_the_same_folder(
    tmp_path: Path,
) -> None:
    folder = organization.create_folder(tmp_path, "Clienti")
    original = make(tmp_path, "Manuale")
    organization.set_project_folder(tmp_path, original, folder.id)
    root = tmp_path / original
    chapter = ops.create_chapter(root, "Intro")
    section = ops.create_section(root, chapter, "Scopo")
    write_section(root, section, "# Scopo\n\nTesto.\n", read_section(root, section)[1])
    for rel in (
        ".traduco/segmenti/en/a.json",
        ".traduco/cache/x.png",
        ".traduco/cestino/old.md",
        "build/o.docx",
        ".traduco/tm.sqlite",
    ):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(b"x")
    copy_id = registry.duplicate_project(tmp_path, original)
    assert copy_id != original and load_project(tmp_path / copy_id).nome == "Manuale (copia)"
    copy = tmp_path / copy_id
    assert (copy / section).read_text() == "# Scopo\n\nTesto.\n"
    assert (copy / ".traduco/segmenti/en/a.json").is_file() and (
        copy / ".traduco/tm.sqlite"
    ).is_file()
    assert not (copy / ".traduco/cache").exists() and not (copy / ".traduco/cestino").exists()
    assert not (copy / "build").exists()
    assert organization.load(tmp_path).projects[copy_id] == folder.id
    named = registry.duplicate_project(tmp_path, original, "Versione per il cliente")
    assert load_project(tmp_path / named).nome == "Versione per il cliente" and named != copy_id
    assert load_project(root).nome == "Manuale"  # the original is untouched


def test_deleting_moves_to_the_trash_and_it_can_come_back(tmp_path: Path) -> None:
    folder = organization.create_folder(tmp_path, "Clienti")
    project = make(tmp_path, "Manuale")
    organization.set_project_folder(tmp_path, project, folder.id)
    entry = registry.trash_project(tmp_path, project)
    assert registry.list_projects(tmp_path) == [] and not (tmp_path / project).exists()
    assert organization.load(tmp_path).projects == {}
    [item] = registry.list_trash(tmp_path)
    assert item["name"] == entry and item["id"] == project and item["nome"] == "Manuale"
    make(tmp_path, "Manuale")  # the name is taken again meanwhile
    restored = registry.restore_project(tmp_path, entry)
    assert restored != project and load_project(tmp_path / restored).nome == "Manuale"
    assert registry.list_trash(tmp_path) == []
    other = registry.trash_project(tmp_path, restored)
    registry.purge_trash(tmp_path, other)
    assert registry.list_trash(tmp_path) == []
    for bad in ("../x", "nonsense", "20260101T000000Z-../../etc"):
        with pytest.raises(WorkspaceError):
            registry.restore_project(tmp_path, bad)


def test_a_model_keeps_titles_glossary_and_settings_but_no_text_or_history(
    tmp_path: Path,
) -> None:
    original = make(tmp_path, "Manuale")
    root = tmp_path / original
    chapter = ops.create_chapter(root, "Intro")
    section = ops.create_section(root, chapter, "Scopo")
    write_section(
        root,
        section,
        "---\ntitle: Scopo\ntono: formale\n---\n\nTesto.\n",
        read_section(root, section)[1],
    )
    (root / "glossario.yaml").write_text(
        "- sorgente: pompa\n  destinazione: pump\n", encoding="utf-8"
    )
    (root / ".traduco").mkdir(exist_ok=True)
    (root / ".traduco" / "tm.sqlite").write_bytes(b"x")

    model = registry.duplicate_project(tmp_path, original, "Modello", structure_only=True)

    copy = tmp_path / model
    text = (copy / section).read_text(encoding="utf-8")
    assert "title: Scopo" in text and "tono: formale" in text and "Testo." not in text
    assert "pompa" in (copy / "glossario.yaml").read_text(encoding="utf-8")
    assert not (copy / ".traduco").exists()
    assert "Testo." in (root / section).read_text(encoding="utf-8")  # the original is untouched
