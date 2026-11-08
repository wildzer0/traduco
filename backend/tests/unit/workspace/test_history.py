"""Earlier versions of a section."""

from pathlib import Path

import pytest

from app.core.workspace import history
from app.core.workspace.errors import WorkspaceError

REL = "capitoli/01-a/01-s.md"


def test_one_version_per_burst_of_edits(tmp_path: Path) -> None:
    clock = [1_000_000.0]
    assert history.snapshot(tmp_path, REL, b"uno\n", now=lambda: clock[0])
    clock[0] += 60  # a minute later: still the same burst
    assert not history.snapshot(tmp_path, REL, b"due\n", now=lambda: clock[0])
    clock[0] += 600
    assert history.snapshot(tmp_path, REL, b"tre\n", now=lambda: clock[0])
    versions = history.list_versions(tmp_path, REL)
    assert len(versions) == 2
    assert history.read_version(tmp_path, REL, str(versions[0]["id"])) == "tre\n"
    assert history.read_version(tmp_path, REL, str(versions[1]["id"])) == "uno\n"


def test_empty_and_repeated_text_is_not_kept_and_the_list_is_bounded(tmp_path: Path) -> None:
    assert not history.snapshot(tmp_path, REL, b"  \n")
    t = [2_000_000.0]
    for n in range(history.KEEP + 5):
        t[0] += 1000
        history.snapshot(tmp_path, REL, f"v{n}\n".encode(), now=lambda: t[0])
    assert len(history.list_versions(tmp_path, REL)) == history.KEEP
    t[0] += 1000
    newest = history.list_versions(tmp_path, REL)[0]
    assert not history.snapshot(
        tmp_path, REL, f"v{history.KEEP + 4}\n".encode(), now=lambda: t[0]
    ), newest


def test_a_bad_version_id_is_refused(tmp_path: Path) -> None:
    for bad in ("../../x", "nope", "20260101000000-zzzzzzzz"):
        with pytest.raises(WorkspaceError):
            history.read_version(tmp_path, REL, bad)
