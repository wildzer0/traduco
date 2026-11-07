from datetime import date
from pathlib import Path

import pytest

from app.core.snippets import model
from app.core.workspace.errors import WorkspaceError

FILE = """\
contatori:
  REQ: { prefisso: "FOO-REQ-", cifre: 5 }
  TC: { prefisso: "TC-", cifre: 3, inizio: 10 }
snippet:
  - alias: req
    descrizione: Nuovo requisito
    testo: "**{{contatore:REQ}}** Il sistema ${1:deve} ${2:fare}. {{codice_documento}}"
  - alias: test
    testo: "{{contatore:TC}} / {{contatore:REQ}} / {{data}} / {{titolo}} / {{progetto}}"
"""


def go(root: Path, alias: str) -> str:
    return model.expand(
        root,
        alias,
        title="Scopo",
        project="Manuale",
        today=date(2026, 11, 7),
        language_date="07/11/2026",
    )


def test_counters_advance_once_per_use_and_survive_a_restart(tmp_path: Path) -> None:
    model.save_raw(tmp_path, FILE)
    assert go(tmp_path, "req").startswith("**FOO-REQ-00001**")
    assert go(tmp_path, "req").startswith("**FOO-REQ-00002**")
    # a new process only has the files
    assert [c["next"] for c in model.counters(tmp_path)] == ["FOO-REQ-00003", "TC-010"]
    assert go(tmp_path, "test") == "TC-010 / FOO-REQ-00003 / 07/11/2026 / Scopo / Manuale"


def test_tab_stops_and_template_fields_are_left_alone(tmp_path: Path) -> None:
    model.save_raw(tmp_path, FILE)
    text = go(tmp_path, "req")
    assert "${1:deve} ${2:fare}" in text and text.endswith("{{codice_documento}}")


@pytest.mark.parametrize(
    "bad",
    [
        "snippet: [{alias: 'a b', testo: x}]",
        "snippet: [{alias: a, testo: x}, {alias: a, testo: y}]",
        "snippet: [{alias: a, testo: '{{contatore:NOPE}}'}]",
        "contatori: {X: {cifre: 99}}",
        "snippet: [{alias: a, testo: x, extra: 1}]",
        "snippet: [",
    ],
)
def test_an_invalid_file_is_refused_and_not_saved(tmp_path: Path, bad: str) -> None:
    with pytest.raises(WorkspaceError):
        model.save_raw(tmp_path, bad)
    assert not (tmp_path / "snippet.yaml").exists()


def test_unknown_alias_and_empty_project(tmp_path: Path) -> None:
    assert model.load(tmp_path).snippet == []
    with pytest.raises(WorkspaceError, match="not found"):
        go(tmp_path, "nope")
