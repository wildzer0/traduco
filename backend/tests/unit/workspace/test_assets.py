from pathlib import Path

import pytest

from app.core.workspace import ops
from app.core.workspace.assets import MAX_IMAGE_BYTES, save_image
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import create_project

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16
SVG = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'


@pytest.fixture
def section(tmp_path: Path) -> tuple[Path, str]:
    root = create_project(tmp_path / "p", "P", "it", "en")
    ch = ops.create_chapter(root, "A")
    return root, ops.create_section(root, ch, "S")


@pytest.mark.parametrize(
    ("data", "ext"), [(PNG, ".png"), (JPEG, ".jpg"), (GIF, ".gif"), (WEBP, ".webp"), (SVG, ".svg")]
)
def test_detects_type_from_content_not_from_name(
    section: tuple[Path, str], data: bytes, ext: str
) -> None:
    root, sec = section
    rel = save_image(root, sec, "foto.exe", data)
    assert rel.endswith(ext)
    assert (root / rel).read_bytes() == data


def test_image_lands_in_the_img_folder_of_the_section_chapter(section: tuple[Path, str]) -> None:
    root, sec = section
    assert (
        save_image(root, sec, "Schema Generale.PNG", PNG) == "capitoli/01-a/img/schema-generale.png"
    )


def test_subchapter_sections_use_their_own_img_folder(tmp_path: Path) -> None:
    root = create_project(tmp_path / "p", "P", "it", "en")
    sub = ops.create_chapter(root, "Sub", parent=ops.create_chapter(root, "A"))
    sec = ops.create_section(root, sub, "S")
    assert save_image(root, sec, "x.png", PNG).startswith("capitoli/01-a/01-sub/img/")


def test_name_collisions_get_a_suffix_but_identical_content_is_reused(
    section: tuple[Path, str],
) -> None:
    root, sec = section
    first = save_image(root, sec, "a.png", PNG)
    assert save_image(root, sec, "a.png", PNG) == first
    other = save_image(root, sec, "a.png", PNG + b"different")
    assert other == "capitoli/01-a/img/a-2.png"


def test_pasted_image_without_a_useful_name_gets_a_timestamp_name(
    section: tuple[Path, str],
) -> None:
    root, sec = section
    rel = save_image(root, sec, "", PNG)
    assert Path(rel).name.startswith("img-") and rel.endswith(".png")


@pytest.mark.parametrize(
    "data", [b"", b"just text", b"MZ\x90\x00", b"<html><script>x</script></html>"]
)
def test_non_images_are_rejected(section: tuple[Path, str], data: bytes) -> None:
    root, sec = section
    with pytest.raises(WorkspaceError) as exc:
        save_image(root, sec, "x.png", data)
    assert exc.value.code == "invalid_image"
    assert not (root / "capitoli/01-a/img").exists()


def test_svg_with_script_is_rejected(section: tuple[Path, str]) -> None:
    root, sec = section
    evil = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    with pytest.raises(WorkspaceError) as exc:
        save_image(root, sec, "x.svg", evil)
    assert exc.value.code == "invalid_image"


def test_too_large(section: tuple[Path, str]) -> None:
    root, sec = section
    with pytest.raises(WorkspaceError) as exc:
        save_image(root, sec, "big.png", PNG + b"0" * MAX_IMAGE_BYTES)
    assert exc.value.code == "too_large"


def test_section_must_exist_and_be_a_file(section: tuple[Path, str]) -> None:
    root, _ = section
    with pytest.raises(WorkspaceError):
        save_image(root, "capitoli/01-a/09-nope.md", "x.png", PNG)
    with pytest.raises(WorkspaceError):
        save_image(root, "capitoli/01-a", "x.png", PNG)
