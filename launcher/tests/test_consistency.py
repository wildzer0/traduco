"""Pinned versions and hashes must agree across manifest, Dockerfile, CI and bootstrap scripts."""

from __future__ import annotations

import re
from pathlib import Path

from launcher.manifest import load_manifest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = load_manifest(ROOT / "launcher" / "manifest.toml")
DOCKERFILE = (ROOT / "backend" / "Dockerfile").read_text()


def test_dockerfile_pandoc_matches_manifest() -> None:
    amd, arm = MANIFEST.artifact("pandoc", "linux-x64"), MANIFEST.artifact("pandoc", "linux-arm64")
    assert f"ARG PANDOC_VERSION={amd.version}" in DOCKERFILE
    assert f"ARG PANDOC_SHA256_AMD64={amd.sha256}" in DOCKERFILE
    assert f"ARG PANDOC_SHA256_ARM64={arm.sha256}" in DOCKERFILE


def test_node_major_agrees_everywhere() -> None:
    major = MANIFEST.artifact("node", "linux-x64").version.split(".")[0]
    assert f"FROM node:{major}-slim" in DOCKERFILE
    assert f'node-version: "{major}"' in (ROOT / ".github/workflows/ci.yml").read_text()
    assert (ROOT / "frontend" / ".nvmrc").read_text().strip() == major
    assert f'">={major} <{int(major) + 1}"' in (ROOT / "frontend" / "package.json").read_text()


def test_uv_version_agrees_with_ci_and_docker() -> None:
    uv = re.search(r'UV_VERSION="([\d.]+)"', (ROOT / "start.sh").read_text())
    assert uv
    assert f'UV_VERSION: "{uv[1]}"' in (ROOT / ".github/workflows/ci.yml").read_text()
    assert f"ghcr.io/astral-sh/uv:{uv[1]}" in DOCKERFILE


def test_python_version_agrees() -> None:
    for sub in ("backend", "launcher"):
        assert (ROOT / sub / ".python-version").read_text().strip() == "3.12"
    assert "python:3.12" in DOCKERFILE
