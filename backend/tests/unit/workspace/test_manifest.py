from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.workspace.manifest import (
    MANIFEST_NAME,
    Project,
    create_project,
    load_project,
    save_project,
)

EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "progetto-esempio"


def test_loads_the_example_project() -> None:
    p = load_project(EXAMPLE)
    assert p.nome == "Manuale impianto di pompaggio"
    assert (p.lingua_sorgente, p.lingua_ufficiale) == ("it", "en")
    assert p.metadati["codice_documento"] == "DOC-2026-014"
    assert p.metadati["revisione"] == "02"
    assert p.revisioni[1].data == date(2026, 11, 7)


def test_same_source_and_official_language_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Project(nome="x", lingua_sorgente="it", lingua_ufficiale="it")


def test_invalid_language_code_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Project(nome="x", lingua_sorgente="Italiano", lingua_ufficiale="en")


def test_additional_language_cannot_repeat_source_or_official() -> None:
    with pytest.raises(ValidationError):
        Project(
            nome="x",
            lingua_sorgente="it",
            lingua_ufficiale="en",
            lingue_aggiuntive=[{"codice": "en"}],
        )


def test_save_and_reload_round_trip(tmp_path: Path) -> None:
    original = load_project(EXAMPLE)
    save_project(tmp_path, original)
    assert load_project(tmp_path) == original
    text = (tmp_path / MANIFEST_NAME).read_text(encoding="utf-8")
    assert 'revisione: "02"' in text or "revisione: '02'" in text  # not turned into a number
    assert not list(tmp_path.glob("*.tmp"))


def test_unknown_keys_are_preserved(tmp_path: Path) -> None:
    (tmp_path / MANIFEST_NAME).write_text(
        "nome: A\nlingua_sorgente: it\nlingua_ufficiale: en\ncustom: 42\n", encoding="utf-8"
    )
    project = load_project(tmp_path)
    save_project(tmp_path, project)
    assert "custom: 42" in (tmp_path / MANIFEST_NAME).read_text(encoding="utf-8")


def test_missing_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_project(tmp_path)


def test_create_project_layout(tmp_path: Path) -> None:
    root = create_project(tmp_path / "nuovo", "Nuovo", "it", "en")
    assert (root / MANIFEST_NAME).is_file()
    assert (root / "capitoli").is_dir()
    assert (root / "glossario.yaml").read_text(encoding="utf-8").strip() == "[]"
    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert ".traduco/cache/" in ignore and "build/" in ignore
    assert load_project(root).nome == "Nuovo"


def test_create_project_refuses_existing_project(tmp_path: Path) -> None:
    create_project(tmp_path / "p", "A", "it", "en")
    with pytest.raises(FileExistsError):
        create_project(tmp_path / "p", "B", "it", "en")
