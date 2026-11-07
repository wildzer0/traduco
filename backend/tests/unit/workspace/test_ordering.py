from pathlib import Path

import pytest

from app.core.workspace import ordering
from app.core.workspace.ordering import (
    apply_renames,
    format_name,
    plan_renumber,
    slugify,
    sort_key,
    split_prefix,
)


def test_split_prefix() -> None:
    assert split_prefix("01-scopo.md") == (1, "scopo.md")
    assert split_prefix("123-big") == (123, "big")
    assert split_prefix("scopo.md") == (None, "scopo.md")
    assert split_prefix("1-x") == (None, "1-x")  # prefix needs at least two digits


def test_sort_key_orders_by_prefix_then_unprefixed_by_name() -> None:
    names = ["10-j.md", "02-b.md", "zeta.md", "01-a.md", "Alfa.md"]
    assert sorted(names, key=sort_key) == ["01-a.md", "02-b.md", "10-j.md", "Alfa.md", "zeta.md"]


def test_numeric_not_lexicographic_with_wider_prefix() -> None:
    assert sorted(["100-c", "99-b", "02-a"], key=sort_key) == ["02-a", "99-b", "100-c"]


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Scopo del documento", "scopo-del-documento"),
        ("  Più  città!  ", "piu-citta"),
        ("C++ / Rust", "c-rust"),
        ("???", "senza-titolo"),
        ("", "senza-titolo"),
    ],
)
def test_slugify(title: str, slug: str) -> None:
    assert slugify(title) == slug


def test_format_name() -> None:
    assert format_name(3, "scopo.md") == "03-scopo.md"
    assert format_name(3, "x", width=3) == "003-x"


def test_plan_renumber_only_changed_entries() -> None:
    plan = plan_renumber(["02-b.md", "01-a.md", "03-c.md"])
    assert plan == {"02-b.md": "01-b.md", "01-a.md": "02-a.md"}


def test_plan_renumber_adds_prefix_to_unprefixed_and_widens() -> None:
    plan = plan_renumber([f"{i:02d}-x{i}" for i in range(1, 100)] + ["extra"])
    assert plan["01-x1"] == "001-x1" and plan["extra"] == "100-extra"


def test_plan_renumber_noop() -> None:
    assert plan_renumber(["01-a", "02-b"]) == {}


def test_apply_renames_handles_swaps(tmp_path: Path) -> None:
    (tmp_path / "01-a.md").write_text("A")
    (tmp_path / "02-b.md").write_text("B")
    apply_renames(tmp_path, {"01-a.md": "02-a.md", "02-b.md": "01-b.md"})
    assert (tmp_path / "02-a.md").read_text() == "A"
    assert (tmp_path / "01-b.md").read_text() == "B"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["01-b.md", "02-a.md"]


def test_apply_renames_moves_directories(tmp_path: Path) -> None:
    (tmp_path / "01-cap").mkdir()
    (tmp_path / "01-cap" / "f.md").write_text("x")
    apply_renames(tmp_path, {"01-cap": "02-cap"})
    assert (tmp_path / "02-cap" / "f.md").read_text() == "x"


def test_apply_renames_rolls_back_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for n in ("01-a", "02-b", "03-c"):
        (tmp_path / f"{n}.md").write_text(n)
    real = Path.rename
    calls = {"n": 0}

    def flaky(self: Path, target: Path) -> Path:
        calls["n"] += 1
        if calls["n"] == 5:  # fails during the second phase
            raise OSError("disk error")
        return real(self, target)

    monkeypatch.setattr(Path, "rename", flaky)
    with pytest.raises(OSError):
        apply_renames(tmp_path, {"01-a.md": "02-a.md", "02-b.md": "03-b.md", "03-c.md": "01-c.md"})
    monkeypatch.undo()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["01-a.md", "02-b.md", "03-c.md"]
    assert (tmp_path / "02-b.md").read_text() == "02-b"


def test_apply_renames_refuses_to_overwrite_untouched_file(tmp_path: Path) -> None:
    (tmp_path / "01-a.md").write_text("A")
    (tmp_path / "02-x.md").write_text("X")
    with pytest.raises(FileExistsError):
        apply_renames(tmp_path, {"01-a.md": "02-x.md"})
    assert (tmp_path / "01-a.md").read_text() == "A"
    assert ordering  # module imported for coverage of public API
