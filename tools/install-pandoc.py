#!/usr/bin/env python3
"""Install the pinned Pandoc into ``.runtime/pandoc`` (development and CI).

Version, URL and SHA-256 come from ``launcher/manifest.toml``, the pin shared with the launcher
and the Docker image. The download is checked before anything is unpacked.

    python3 tools/install-pandoc.py
"""

from __future__ import annotations

import hashlib
import platform
import shutil
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / ".runtime" / "pandoc"


def platform_key() -> str:
    system = {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}[platform.system()]
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64"
    return f"{system}-{arch}"


def main() -> int:
    manifest = tomllib.loads((ROOT / "launcher" / "manifest.toml").read_text(encoding="utf-8"))
    pandoc = manifest["pandoc"]
    entry = pandoc["platforms"][platform_key()]
    binary = DEST / ("pandoc.exe" if platform.system() == "Windows" else "bin/pandoc")
    marker = DEST / ".version"
    if binary.is_file() and marker.is_file() and marker.read_text().strip() == pandoc["version"]:
        print(f"Pandoc {pandoc['version']} already installed: {binary}")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / Path(entry["url"]).name
        print(f"downloading {entry['url']}")
        with urllib.request.urlopen(entry["url"], timeout=120) as response:  # noqa: S310 - pinned https URL
            archive.write_bytes(response.read())
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            print(f"checksum mismatch: expected {entry['sha256']}, got {digest}", file=sys.stderr)
            return 1
        unpacked = Path(tmp) / "unpacked"
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                z.extractall(unpacked)
        else:
            with tarfile.open(archive) as tar:
                tar.extractall(unpacked, filter="data")
        (top,) = [p for p in unpacked.iterdir() if p.is_dir()]
        if DEST.exists():
            shutil.rmtree(DEST)
        shutil.move(str(top), str(DEST))
    if platform.system() != "Windows":
        binary.chmod(0o755)
    marker.write_text(pandoc["version"], encoding="utf-8")
    print(f"installed {binary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
