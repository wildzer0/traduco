import base64
from pathlib import Path

import pytest

from app.core.workspace.diagrams import diagram_hash, read_diagram, save_diagram
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import create_project

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><text>A</text></svg>'
HASH = "a" * 64


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return create_project(tmp_path / "p", "P", "it", "en")


def test_hash_is_stable_and_depends_on_theme_neutral_code_only() -> None:
    code = "flowchart LR\n  A --> B"
    assert diagram_hash(code) == diagram_hash(code)
    assert diagram_hash(code) != diagram_hash(code + " ")
    assert len(diagram_hash(code)) == 64


def test_save_and_read_both_formats(root: Path) -> None:
    save_diagram(root, HASH, SVG, PNG)
    assert (root / ".traduco/cache/diagrams" / f"{HASH}.svg").read_text(encoding="utf-8") == SVG
    assert read_diagram(root, HASH, "png").read_bytes() == PNG
    assert read_diagram(root, HASH, "svg").suffix == ".svg"


def test_save_is_idempotent_and_overwrites(root: Path) -> None:
    save_diagram(root, HASH, SVG, PNG)
    save_diagram(root, HASH, SVG.replace("A", "B"), PNG + b"1")
    assert "B" in read_diagram(root, HASH, "svg").read_text(encoding="utf-8")


@pytest.mark.parametrize("bad", ["", "abc", "../" + "a" * 61, "A" * 64, "g" * 64, "a" * 65])
def test_invalid_hashes_are_rejected(root: Path, bad: str) -> None:
    with pytest.raises(WorkspaceError) as exc:
        save_diagram(root, bad, SVG, PNG)
    assert exc.value.code == "invalid_path"
    with pytest.raises(WorkspaceError):
        read_diagram(root, bad, "svg")


def test_png_must_be_a_png(root: Path) -> None:
    with pytest.raises(WorkspaceError) as exc:
        save_diagram(root, HASH, SVG, b"not a png")
    assert exc.value.code == "invalid_image"
    assert not (root / ".traduco/cache").exists()


@pytest.mark.parametrize(
    "svg",
    [
        "<html></html>",
        '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg" onload="x()"></svg>',
    ],
)
def test_unsafe_or_non_svg_content_is_rejected(root: Path, svg: str) -> None:
    with pytest.raises(WorkspaceError) as exc:
        save_diagram(root, HASH, svg, PNG)
    assert exc.value.code == "invalid_image"


def test_size_limit(root: Path) -> None:
    with pytest.raises(WorkspaceError) as exc:
        save_diagram(root, HASH, SVG + " " * (3 * 1024 * 1024), PNG)
    assert exc.value.code == "too_large"


def test_missing_diagram(root: Path) -> None:
    with pytest.raises(WorkspaceError) as exc:
        read_diagram(root, HASH, "png")
    assert exc.value.code == "not_found"


def test_png_roundtrips_through_base64_helper() -> None:
    from app.core.workspace.diagrams import decode_png

    assert decode_png(base64.b64encode(PNG).decode()) == PNG
    with pytest.raises(WorkspaceError):
        decode_png("%%%not base64%%%")
