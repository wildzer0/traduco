"""The audit log is append-only and filterable."""

from datetime import UTC, datetime
from pathlib import Path

from app.core.team.audit import AuditLog


def test_entries_are_kept_with_the_author_newest_first(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.sqlite", clock=lambda: datetime(2026, 11, 8, 10, 0, tzinfo=UTC))
    log.record("u1", "Bruno", "manuale", "segment.approve", "capitoli/a.md#p:0", "en")
    log.record("u2", "Anna", "manuale", "export", "project", "docx")
    log.record("u1", "Bruno", "altro", "segment.approve", "x.md#p:1")
    rows = log.entries()
    assert [r.action for r in rows] == ["segment.approve", "export", "segment.approve"]
    assert rows[0].name == "Bruno" and rows[0].at == "2026-11-08T10:00:00+00:00"
    assert [r.name for r in log.entries(project="manuale")] == ["Anna", "Bruno"]
    assert [r.target for r in log.entries(action="segment.approve", limit=1)] == ["x.md#p:1"]


def test_the_log_survives_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "a.sqlite"
    first = AuditLog(path)
    first.record("u", "N", "p", "export")
    first.close()
    assert len(AuditLog(path).entries()) == 1
