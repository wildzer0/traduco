from __future__ import annotations

import re
from pathlib import Path

import pytest

from launcher.manifest import load_manifest

MANIFEST = load_manifest(Path(__file__).resolve().parents[1] / "manifest.toml")
PLATFORMS = ["linux-x64", "linux-arm64", "darwin-x64", "darwin-arm64", "windows-x64"]


@pytest.mark.parametrize("component", ["node", "pandoc"])
@pytest.mark.parametrize("platform", PLATFORMS)
def test_every_platform_has_https_url_and_sha256(component: str, platform: str) -> None:
    art = MANIFEST.artifact(component, platform)
    assert art.url.startswith("https://")
    assert re.fullmatch(r"[0-9a-f]{64}", art.sha256)
    assert art.version in art.url


def test_node_is_24_lts_and_pandoc_at_least_3_5() -> None:
    assert MANIFEST.artifact("node", "linux-x64").version.startswith("24.")
    major, minor, *_ = (int(x) for x in MANIFEST.artifact("pandoc", "linux-x64").version.split("."))
    assert (major, minor) >= (3, 5)


def test_unknown_platform_raises() -> None:
    with pytest.raises(KeyError):
        MANIFEST.artifact("node", "plan9-x64")


def test_port_range_and_disk() -> None:
    assert MANIFEST.port_range == (8000, 8100)
    assert MANIFEST.min_free_gb > 0


def test_models_have_tags_and_sizes() -> None:
    sizes = [MANIFEST.model(k).size_gb for k in ("small", "default", "large")]
    assert sizes == sorted(sizes) and all(s > 0 for s in sizes)
    assert all(MANIFEST.model(k).tag.startswith("gemma4:") for k in ("small", "default", "large"))
    assert MANIFEST.ollama_host == "http://127.0.0.1:11434"
