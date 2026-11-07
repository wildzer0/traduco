"""Static checks on the thin bootstrap scripts (docs/02-architettura.md: < 40 lines each)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", ["start.sh", "start.cmd"])
def test_bootstrap_scripts_are_thin(name: str) -> None:
    assert len((ROOT / name).read_text().splitlines()) < 40


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_start_sh_has_valid_syntax_and_is_executable() -> None:
    subprocess.run(["bash", "-n", str(ROOT / "start.sh")], check=True)
    assert (ROOT / "start.sh").stat().st_mode & 0o111


@pytest.mark.parametrize("name", ["start.sh", "start.cmd", "launcher/bootstrap.ps1"])
def test_scripts_are_ascii_and_pin_uv(name: str) -> None:
    text = (ROOT / name).read_bytes().decode("ascii")  # non-ASCII breaks Windows code pages
    if name != "start.cmd":
        assert "0.13.4" in text


def test_start_cmd_is_crlf_via_gitattributes() -> None:
    assert "*.cmd text eol=crlf" in (ROOT / ".gitattributes").read_text()


def test_uv_version_is_consistent_between_scripts() -> None:
    assert 'UV_VERSION="0.13.4"' in (ROOT / "start.sh").read_text()
    assert "$UvVersion = '0.13.4'" in (ROOT / "launcher/bootstrap.ps1").read_text()
