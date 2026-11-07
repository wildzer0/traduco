from __future__ import annotations

import hashlib
import io
import sys
import tarfile
from pathlib import Path

import pytest

from launcher import steps
from launcher.manifest import Artifact
from launcher.ui import LauncherError
from tests.conftest import Behaviour
from tests.test_steps import make_ctx


def fake_pandoc_archive() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        body = b"#!/bin/sh\necho pandoc 3.13\n"
        info = tarfile.TarInfo("pandoc-3.13/bin/pandoc")
        info.size, info.mode = len(body), 0o755
        tar.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


@pytest.mark.skipif(sys.platform == "win32", reason="archive layout differs on Windows")
def test_portable_pandoc_is_downloaded_verified_and_installed_once(
    tmp_path: Path, server: tuple[str, Behaviour], monkeypatch: pytest.MonkeyPatch
) -> None:
    url, behaviour = server
    behaviour.payload = fake_pandoc_archive()
    digest = hashlib.sha256(behaviour.payload).hexdigest()
    ctx = make_ctx(tmp_path)
    monkeypatch.setattr(
        type(ctx.manifest),
        "artifact",
        lambda self, c, p: Artifact("3.13", url + "/pandoc-3.13.tar.gz", digest),
    )
    assert steps.ensure_pandoc(ctx) is True
    assert ctx.paths.pandoc_bin.is_file() and ctx.paths.pandoc_bin.stat().st_mode & 0o111
    assert steps.ensure_pandoc(ctx) is False  # second start: nothing to do
    assert len(behaviour.requests) == 1


def test_a_corrupt_pandoc_download_is_refused(
    tmp_path: Path, server: tuple[str, Behaviour], monkeypatch: pytest.MonkeyPatch
) -> None:
    url, behaviour = server
    behaviour.payload = b"not the archive"
    ctx = make_ctx(tmp_path)
    monkeypatch.setattr(
        type(ctx.manifest),
        "artifact",
        lambda self, c, p: Artifact("3.13", url + "/p.tar.gz", "0" * 64),
    )
    with pytest.raises(LauncherError) as info:
        steps.ensure_pandoc(ctx)
    assert info.value.code == "E011" and not ctx.paths.pandoc_bin.exists()


def test_offline_mode_does_not_download_pandoc(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path, offline=True)
    with pytest.raises(LauncherError) as info:
        steps.ensure_pandoc(ctx)
    assert info.value.code == "E012"


def test_libreoffice_is_found_on_the_path_or_in_standard_places(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        steps.shutil, "which", lambda name: "/usr/bin/soffice" if name == "soffice" else None
    )
    assert steps.find_libreoffice() == Path("/usr/bin/soffice")
    monkeypatch.setattr(steps.shutil, "which", lambda name: None)
    monkeypatch.setattr(steps.sys, "platform", "win32")
    program = tmp_path / "LibreOffice" / "program"
    program.mkdir(parents=True)
    (program / "soffice.exe").write_text("")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    assert steps.find_libreoffice() == program / "soffice.exe"
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "nowhere"))
    assert steps.find_libreoffice() is None


def test_the_backend_is_told_where_everything_is(tmp_path: Path) -> None:
    from launcher.run import backend_env

    ctx = make_ctx(tmp_path)
    ctx.paths.pandoc_bin.parent.mkdir(parents=True)
    ctx.paths.pandoc_bin.write_text("")
    ctx.llm = steps.Llm(
        model="gemma4:e4b", host="http://127.0.0.1:11434", base_url="http://127.0.0.1:11434/v1"
    )
    env = backend_env(ctx, tmp_path / "ws", Path("/usr/bin/soffice"))
    assert env["TRADUCO_PANDOC"] == str(ctx.paths.pandoc_bin)
    assert env["TRADUCO_SOFFICE"] == "/usr/bin/soffice"
    assert env["TRADUCO_RUNTIME_DIR"] == str(ctx.paths.runtime)
    assert (
        env["TRADUCO_LLM_BASE_URL"] == "http://127.0.0.1:11434/v1"
        and env["TRADUCO_LLM_MODEL"] == "gemma4:e4b"
    )
    ctx.llm = steps.Llm(model="x", base_url="http://other/v1", external=True)
    assert "TRADUCO_LLM_BASE_URL" not in backend_env(
        ctx, tmp_path / "ws", None
    )  # the user's own setting wins
