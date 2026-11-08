"""Attachments and CSV tables."""

from pathlib import Path

import pytest

from app.core.workspace.attachments import (
    attachment_file,
    list_attachments,
    markdown_table,
    read_table,
    save_attachment,
)
from app.core.workspace.errors import WorkspaceError


def test_a_file_is_stored_once_and_listed(tmp_path: Path) -> None:
    first = save_attachment(tmp_path, "Manuale Utente.PDF", b"%PDF-1")
    again = save_attachment(tmp_path, "Manuale Utente.PDF", b"%PDF-1")
    other = save_attachment(tmp_path, "Manuale Utente.PDF", b"%PDF-2")
    assert first == again == "allegati/manuale-utente.pdf"
    assert other == "allegati/manuale-utente-2.pdf"
    assert [a["name"] for a in list_attachments(tmp_path)] == [
        "manuale-utente-2.pdf",
        "manuale-utente.pdf",
    ]


def test_folders_in_the_name_and_dangerous_files_are_refused(tmp_path: Path) -> None:
    assert save_attachment(tmp_path, "../../etc/dati.csv", b"a,b") == "allegati/dati.csv"
    for bad in ("run.exe", "page.html", "x.svg", "s.js"):
        with pytest.raises(WorkspaceError):
            save_attachment(tmp_path, bad, b"x")
    with pytest.raises(WorkspaceError):
        attachment_file(tmp_path, "../progetto.yaml")


def test_a_csv_becomes_a_table_whatever_its_delimiter_and_encoding(tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_bytes(
        "Nome;Portata\nPompa 1;120 m³/h\nPompa|2;8,5\n".encode("cp1252")
    )
    rows = read_table(tmp_path / "a.csv")
    assert rows == [["Nome", "Portata"], ["Pompa 1", "120 m³/h"], ["Pompa|2", "8,5"]]
    assert markdown_table(rows).splitlines() == [
        "| Nome | Portata |",
        "|---|---|",
        "| Pompa 1 | 120 m³/h |",
        "| Pompa\\|2 | 8,5 |",
    ]


def test_short_rows_are_padded_and_blank_lines_ignored(tmp_path: Path) -> None:
    (tmp_path / "b.csv").write_text("a,b,c\n\n1,2\n", encoding="utf-8")
    assert read_table(tmp_path / "b.csv") == [["a", "b", "c"], ["1", "2", ""]]
