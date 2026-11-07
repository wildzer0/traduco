from pathlib import Path

import pytest

from app.core.emissions import changes, comments, compare, store
from app.core.workspace import ops
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import create_project, load_project
from app.core.workspace.sections import read_section, write_section


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = create_project(tmp_path / "p", "Manuale", "it", "en")
    chapter = ops.create_chapter(root, "Intro")
    ops.create_section(root, chapter, "Scopo")
    return root


def section(root: Path) -> str:
    return next(e.path for e in store.current_entries(root) if e.kind == "section")


def official(path: str, text: str) -> str:
    return text.replace("Ciao", "Hello")


def freeze(root: Path, rev: str) -> dict:  # type: ignore[type-arg]
    from datetime import date

    return store.create(root, load_project(root), rev, date(2026, 11, 7), "desc", official)


def edit(root: Path, rel: str, text: str) -> None:
    write_section(root, rel, text, read_section(root, rel)[1])


def test_word_diff_marks_only_what_changed() -> None:
    ops_ = compare.word_diff("La pompa è rossa.", "La pompa è blu e grande.")
    assert [o["op"] for o in ops_] == ["equal", "del", "ins", "equal"]
    assert "rossa" in ops_[1]["text"] and "blu" in ops_[2]["text"]
    assert "".join(o["text"] for o in ops_ if o["op"] != "ins") == "La pompa è rossa."


def test_an_issue_freezes_both_languages_and_joins_the_revision_table(project: Path) -> None:
    rel = section(project)
    edit(project, rel, "# Scopo\n\nCiao mondo.\n")
    data = freeze(project, "01")
    assert store.text_of(project, "01", "sorgente", rel) == "# Scopo\n\nCiao mondo.\n"
    assert "Hello mondo" in (store.text_of(project, "01", "ufficiale", rel) or "")
    assert [i["rev"] for i in store.list_issues(project)] == ["01"] and data["rev"] == "01"
    assert [r.rev for r in load_project(project).revisioni] == ["01"]
    with pytest.raises(WorkspaceError, match="already exists"):
        freeze(project, "01")
    with pytest.raises(WorkspaceError):
        freeze(project, "../x")


def test_comparing_an_issue_with_the_draft(project: Path) -> None:
    rel = section(project)
    edit(project, rel, "# Scopo\n\nUno due tre.\n")
    freeze(project, "01")
    edit(project, rel, "# Scopo\n\nUno quattro tre.\n")
    chapter = rel.rsplit("/", 1)[0]
    new = ops.create_section(project, chapter, "Nuova")
    result = compare.compare(
        compare.load_side(project, "01", "sorgente", official),
        compare.load_side(project, None, "sorgente", official),
    )
    by_path = {s["path"]: s for s in result["sections"]}
    assert by_path[rel]["status"] == "modified" and by_path[rel]["words_added"] == 1
    assert by_path[new]["status"] == "added"
    same = compare.compare(
        compare.load_side(project, "01", "sorgente", official),
        compare.load_side(project, "01", "sorgente", official),
    )
    assert same["sections"] == [] and same["unchanged"] == 1


@pytest.mark.asyncio
async def test_the_change_table_has_one_row_per_changed_section() -> None:
    compared = {
        "sections": [
            {"path": "a.md", "title": "A", "status": "modified", "words_added": 3,
             "words_removed": 1, "ops": [{"op": "ins", "text": "nuovo"}]},
            {"path": "b.md", "title": "B", "status": "added", "words_added": 9,
             "words_removed": 0, "ops": []},
        ]
    }  # fmt: skip

    class Model:
        async def chat(self, messages: object, **kw: object) -> str:
            return " Aggiunto un requisito. "

    rows = await changes.summarise(Model(), compared, "it")  # type: ignore[arg-type]
    assert [r["summary"] for r in rows] == ["Aggiunto un requisito.", "Sezione aggiunta"]
    offline = await changes.summarise(None, compared, "it")
    assert offline[0]["summary"].startswith("Modificata (3 parole aggiunte")
    assert changes.describe(rows) == "A: Aggiunto un requisito; B: Sezione aggiunta"


def test_restoring_a_section_brings_back_the_old_text(project: Path) -> None:
    rel = section(project)
    edit(project, rel, "# Scopo\n\nVecchio.\n")
    freeze(project, "01")
    edit(project, rel, "# Scopo\n\nNuovo.\n")
    store.restore_section(project, "01", rel)
    assert "Vecchio." in read_section(project, rel)[0]


def segment_key(root: Path, rel: str, word: str) -> str:
    from app.core.segmentation.segmenter import segment

    found = segment(read_section(root, rel)[0]).by_key().items()
    return next(k for k, s in found if word in s.source)


def test_a_comment_follows_its_segment_when_the_text_around_it_changes(project: Path) -> None:
    rel = section(project)
    sentence = "Il sistema deve avviarsi entro dieci secondi."
    edit(project, rel, f"# Scopo\n\nPrimo paragrafo.\n\n{sentence}\n")
    thread = comments.add_thread(
        project, rel, segment_key(project, rel, "dieci"), "Anna", "Quanti secondi, davvero?"
    )
    # text added before it renumbers the keys
    edit(project, rel, f"# Scopo\n\nNuova introduzione.\n\nPrimo paragrafo.\n\n{sentence}\n")
    [found] = comments.threads(project, rel)
    assert found["id"] == thread["id"] and not found["lost"] and "dieci" in found["source"]
    # the commented sentence is lightly edited: still found by similarity
    edit(
        project,
        rel,
        "# Scopo\n\nPrimo paragrafo.\n\nIl sistema deve avviarsi entro quindici secondi.\n",
    )
    [found] = comments.threads(project, rel)
    assert not found["lost"] and "quindici" in found["source"]
    # gone completely
    edit(project, rel, "# Scopo\n\nSolo questo resta qui.\n")
    assert comments.threads(project, rel)[0]["lost"]


def test_threads_have_replies_and_a_status(project: Path) -> None:
    rel = section(project)
    key = segment_key(project, rel, "")
    t = comments.add_thread(project, rel, key, "Anna", "Controllare")
    comments.reply(project, rel, t["id"], "Bruno", "Fatto")
    comments.set_status(project, rel, t["id"], "resolved")
    assert comments.counts(project, rel) == {"open": 0, "resolved": 1}
    assert len(comments.threads(project, rel)[0]["messages"]) == 2
    with pytest.raises(WorkspaceError):
        comments.add_thread(project, rel, key, "Anna", "  ")
    comments.remove(project, rel, t["id"])
    assert comments.threads(project, rel) == []
