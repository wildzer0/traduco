from pathlib import Path

from watchfiles import Change

from app.core.workspace import ops
from app.core.workspace.fsio import sha256_bytes
from app.core.workspace.manifest import create_project
from app.core.workspace.watcher import describe_changes, is_relevant


def setup(tmp_path: Path) -> tuple[Path, str]:
    root = create_project(tmp_path / "p", "P", "it", "en")
    return root, ops.create_section(root, ops.create_chapter(root, "A"), "S")


def test_relevance_filter(tmp_path: Path) -> None:
    root, sec = setup(tmp_path)
    assert is_relevant(root, root / sec)
    assert is_relevant(root, root / "capitoli/01-a/_capitolo.yaml")
    assert is_relevant(root, root / "progetto.yaml")
    assert is_relevant(root, root / "glossario.yaml")
    assert is_relevant(root, root / "capitoli/01-a/img/p.png")
    assert not is_relevant(root, root / ".traduco/tm.sqlite")
    assert not is_relevant(root, root / "capitoli/01-a/.01-s.md.abc123.tmp")  # atomic write temp
    assert not is_relevant(root, root / "capitoli/01-a/.traduco-tmp-xx-0")  # renumbering temp
    assert not is_relevant(root, root / ".git/HEAD")
    assert not is_relevant(root, root / "build/out.docx")
    assert not is_relevant(root, root / "README.md")


def test_modified_section_carries_current_hash(tmp_path: Path) -> None:
    root, sec = setup(tmp_path)
    (root / sec).write_text("nuovo\n", encoding="utf-8")
    events = describe_changes(root, {(Change.modified, str(root / sec))})
    assert events == [
        {
            "type": "file.changed",
            "path": sec,
            "change": "modified",
            "hash": sha256_bytes(b"nuovo\n"),
        }
    ]


def test_deleted_and_added(tmp_path: Path) -> None:
    root, sec = setup(tmp_path)
    gone = root / sec
    gone.unlink()
    new = root / "capitoli/01-a/02-x.md"
    new.write_text("x", encoding="utf-8")
    events = describe_changes(root, {(Change.deleted, str(gone)), (Change.added, str(new))})
    assert [(e["path"], e["change"], e["hash"] is None) for e in events] == [
        (sec, "deleted", True),
        ("capitoli/01-a/02-x.md", "added", False),
    ]


def test_non_section_files_have_no_hash_and_project_manifest_has_its_own_event(
    tmp_path: Path,
) -> None:
    root, _ = setup(tmp_path)
    img = root / "capitoli/01-a/img/p.png"
    img.parent.mkdir()
    img.write_bytes(b"x")
    events = describe_changes(
        root, {(Change.added, str(img)), (Change.modified, str(root / "progetto.yaml"))}
    )
    by_path = {e["path"]: e for e in events}
    assert by_path["capitoli/01-a/img/p.png"]["hash"] is None
    assert by_path["progetto.yaml"]["type"] == "project.changed"


def test_file_vanishing_between_event_and_hashing_is_reported_as_deleted(tmp_path: Path) -> None:
    root, sec = setup(tmp_path)
    (root / sec).unlink()
    events = describe_changes(root, {(Change.modified, str(root / sec))})
    assert events[0]["change"] == "deleted" and events[0]["hash"] is None


def test_events_are_sorted_for_stable_output(tmp_path: Path) -> None:
    root, sec = setup(tmp_path)
    b = root / "capitoli/01-a/02-b.md"
    b.write_text("b", encoding="utf-8")
    events = describe_changes(root, {(Change.modified, str(b)), (Change.modified, str(root / sec))})
    assert [e["path"] for e in events] == sorted(e["path"] for e in events)
