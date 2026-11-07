from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from launcher.downloads import download, extract_archive, install_archive, sha256_file
from launcher.ui import LauncherError

DATA = bytes(range(256)) * 2000  # 512000 bytes
DIGEST = hashlib.sha256(DATA).hexdigest()


def fetch(url: str, dest: Path, **kw: object) -> Path:
    return download(url, dest, DIGEST, backoff=0, **kw)  # type: ignore[arg-type]


def test_download_and_verify(server, tmp_path: Path) -> None:
    url, b = server
    b.payload = DATA
    seen: list[tuple[int, int | None]] = []
    dest = fetch(url, tmp_path / "f.bin", progress=lambda d, t: seen.append((d, t)))
    assert sha256_file(dest) == DIGEST
    assert seen[-1] == (len(DATA), len(DATA))
    assert not (tmp_path / "f.bin.part").exists()


def test_cached_file_is_not_downloaded_again(server, tmp_path: Path) -> None:
    url, b = server
    b.payload = DATA
    fetch(url, tmp_path / "f.bin")
    fetch(url, tmp_path / "f.bin")
    assert len(b.requests) == 1


def test_corrupt_cached_file_is_replaced(server, tmp_path: Path) -> None:
    url, b = server
    b.payload = DATA
    (tmp_path / "f.bin").write_bytes(b"garbage")
    assert sha256_file(fetch(url, tmp_path / "f.bin")) == DIGEST


def test_wrong_hash_raises_and_deletes_file(server, tmp_path: Path) -> None:
    url, b = server
    b.payload = b"tampered"
    with pytest.raises(LauncherError) as e:
        fetch(url, tmp_path / "f.bin")
    assert e.value.code == "E011"
    assert list(tmp_path.iterdir()) == []


def test_retries_on_server_errors(server, tmp_path: Path) -> None:
    url, b = server
    b.payload, b.fail_first = DATA, 2
    assert sha256_file(fetch(url, tmp_path / "f.bin")) == DIGEST
    assert len(b.requests) == 3


def test_gives_up_after_three_attempts(server, tmp_path: Path) -> None:
    url, b = server
    b.payload, b.fail_first = DATA, 99
    with pytest.raises(LauncherError) as e:
        fetch(url, tmp_path / "f.bin")
    assert e.value.code == "E010" and len(b.requests) == 3


def test_client_errors_are_not_retried(server, tmp_path: Path) -> None:
    url, b = server
    b.status_override = 404
    with pytest.raises(LauncherError) as e:
        fetch(url, tmp_path / "f.bin")
    assert e.value.code == "E010" and len(b.requests) == 1


def test_resumes_after_dropped_connection(server, tmp_path: Path) -> None:
    url, b = server
    b.payload, b.drop_first = DATA, True
    assert sha256_file(fetch(url, tmp_path / "f.bin")) == DIGEST
    assert "Range" in b.requests[1]


def test_resumes_from_existing_partial_file(server, tmp_path: Path) -> None:
    url, b = server
    b.payload = DATA
    (tmp_path / "f.bin.part").write_bytes(DATA[:1000])
    assert sha256_file(fetch(url, tmp_path / "f.bin")) == DIGEST
    assert b.requests[0]["Range"] == "bytes=1000-"


def test_server_without_range_support_restarts(server, tmp_path: Path) -> None:
    url, b = server
    b.payload, b.support_range = DATA, False
    (tmp_path / "f.bin.part").write_bytes(DATA[:1000])
    assert sha256_file(fetch(url, tmp_path / "f.bin")) == DIGEST


def test_corrupt_partial_file_is_retried_from_scratch(server, tmp_path: Path) -> None:
    url, b = server
    b.payload = DATA
    (tmp_path / "f.bin.part").write_bytes(b"x" * 1000)
    assert sha256_file(fetch(url, tmp_path / "f.bin")) == DIGEST


def test_offline_refuses_to_download_but_uses_cache(server, tmp_path: Path) -> None:
    url, b = server
    b.payload = DATA
    with pytest.raises(LauncherError) as e:
        fetch(url, tmp_path / "f.bin", offline=True)
    assert e.value.code == "E012" and b.requests == []
    (tmp_path / "f.bin").write_bytes(DATA)
    assert fetch(url, tmp_path / "f.bin", offline=True).exists()


def test_proxy_environment_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.request

    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    assert urllib.request.getproxies()["https"] == "http://proxy.example:3128"


def make_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


def test_zip_path_traversal_is_rejected(tmp_path: Path) -> None:
    make_zip(tmp_path / "evil.zip", {"../escape.txt": b"x"})
    with pytest.raises(LauncherError):
        extract_archive(tmp_path / "evil.zip", tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_tar_path_traversal_is_rejected(tmp_path: Path) -> None:
    with tarfile.open(tmp_path / "evil.tar.gz", "w:gz") as tf:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        tf.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(tarfile.TarError):
        extract_archive(tmp_path / "evil.tar.gz", tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_install_archive_strips_single_top_level_folder(tmp_path: Path) -> None:
    make_zip(tmp_path / "n.zip", {"node-v1/bin/node": b"bin", "node-v1/README": b"r"})
    install_archive(tmp_path / "n.zip", tmp_path / "node")
    assert (tmp_path / "node" / "bin" / "node").read_bytes() == b"bin"
    assert not (tmp_path / "node.tmp").exists()


def test_install_archive_replaces_previous_install(tmp_path: Path) -> None:
    (tmp_path / "node").mkdir()
    (tmp_path / "node" / "old").write_text("old")
    make_zip(tmp_path / "n.zip", {"a/new": b"new"})
    install_archive(tmp_path / "n.zip", tmp_path / "node")
    assert (tmp_path / "node" / "new").exists() and not (tmp_path / "node" / "old").exists()
