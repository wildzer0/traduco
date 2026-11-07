import importlib.util
import json
import stat
import sys
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "bundle_offline", Path(__file__).resolve().parents[1] / "bundle-offline.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fake_repo(root: Path) -> Path:
    files = {
        "start.sh": "#!/bin/sh\n",
        "start.cmd": "@echo off\n",
        "README.md": "r",
        "CHANGELOG.md": "## [0.6.0]\n",
        "launcher/launcher/__main__.py": "x",
        "launcher/pyproject.toml": "p",
        "launcher/.venv/lib/x.py": "venv",
        "launcher/tests/test_x.py": "t",
        "launcher/launcher/__pycache__/a.pyc": "c",
        "backend/app/main.py": "m",
        "backend/tests/test_y.py": "t",
        "backend/.venv/bin/python": "v",
        "backend/pyproject.toml": "p",
        "backend/uv.lock": "l",
        "backend/.python-version": "3.12\n",
        "frontend/dist/index.html": "<html>",
        "frontend/dist/assets/a.js": "js",
        "frontend/src/a.ts": "src",
        "frontend/node_modules/x/y.js": "nm",
        "examples/progetto-esempio/progetto.yaml": "nome: x\n",
        ".runtime/uv/uv": "uvbin",
        ".runtime/python/cpython/bin/python3": "py",
        ".runtime/uv-cache/wheel": "w",
        ".runtime/pandoc/bin/pandoc": "pd",
        ".runtime/logs/launcher.log": "log",
        ".runtime/node/bin/node": "node",
        ".runtime/downloads/big.tar": "dl",
        ".runtime/launcher-venv/pyvenv.cfg": "cfg",
        "docs/04-piano.md": "plan",
        ".github/workflows/ci.yml": "ci",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return root


def test_the_package_carries_what_is_needed_and_nothing_else(tmp_path: Path) -> None:
    repo = fake_repo(tmp_path / "repo")
    out = tmp_path / "out"
    out.mkdir()
    mod.stage(
        repo,
        out,
        repo / ".runtime" / "uv" / "uv",
        {"pandoc": "3.13", "backend": "digest", "node": "24"},
    )
    names = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert {
        "start.sh",
        "start.cmd",
        "backend/app/main.py",
        "backend/uv.lock",
        "frontend/dist/index.html",
        "launcher/launcher/__main__.py",
        "examples/progetto-esempio/progetto.yaml",
        ".runtime/uv/uv",
        ".runtime/python/cpython/bin/python3",
        ".runtime/uv-cache/wheel",
        ".runtime/pandoc/bin/pandoc",
    } <= names
    for unwanted in (
        "backend/tests/test_y.py",
        "backend/.venv/bin/python",
        "launcher/.venv/lib/x.py",
        "launcher/tests/test_x.py",
        "frontend/src/a.ts",
        "frontend/node_modules/x/y.js",
        ".runtime/logs/launcher.log",
        ".runtime/node/bin/node",
        ".runtime/downloads/big.tar",
        ".runtime/launcher-venv/pyvenv.cfg",
        "docs/04-piano.md",
        ".github/workflows/ci.yml",
    ):
        assert unwanted not in names, unwanted
    assert not any(n.endswith(".pyc") for n in names)
    # only the facts the launcher cannot rebuild are kept in its state
    assert json.loads((out / ".runtime" / "state.json").read_text()) == {"pandoc": "3.13"}


def test_without_a_frontend_build_it_refuses(tmp_path: Path) -> None:
    repo = fake_repo(tmp_path / "repo")
    (repo / "frontend" / "dist" / "index.html").unlink()
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(SystemExit, match="frontend/dist"):
        mod.stage(repo, out, repo / ".runtime" / "uv" / "uv", {})


def test_model_files_are_taken_from_the_manifest(tmp_path: Path) -> None:
    models = tmp_path / "models"
    manifest = models / "manifests" / "registry.ollama.ai" / "library" / "gemma4" / "e4b"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "config": {"digest": "sha256:aaa"},
                "layers": [{"digest": "sha256:bbb"}, {"digest": "sha256:ccc"}],
            }
        )
    )
    (models / "blobs").mkdir()
    for d in ("aaa", "bbb", "ccc", "unrelated"):
        (models / "blobs" / f"sha256-{d}").write_text(d)
    files = mod.ollama_model_files(models, "gemma4:e4b")
    assert [f.name for f in files] == ["e4b", "sha256-aaa", "sha256-bbb", "sha256-ccc"]
    (models / "blobs" / "sha256-ccc").unlink()
    with pytest.raises(SystemExit, match="incomplete"):
        mod.ollama_model_files(models, "gemma4:e4b")
    with pytest.raises(SystemExit, match="not found"):
        mod.ollama_model_files(models, "other:1")


def test_model_files_land_where_the_launcher_looks(tmp_path: Path) -> None:
    repo = fake_repo(tmp_path / "repo")
    models = tmp_path / "models"
    (models / "blobs").mkdir(parents=True)
    blob = models / "blobs" / "sha256-aaa"
    blob.write_text("weights")
    out = tmp_path / "out"
    out.mkdir()
    mod.stage(repo, out, repo / ".runtime" / "uv" / "uv", {}, (models, "m", [blob]))
    assert (out / ".runtime" / "ollama-models" / "blobs" / "sha256-aaa").read_text() == "weights"


def test_zip_keeps_the_executable_bit_and_writes_a_checksum(tmp_path: Path) -> None:
    folder = tmp_path / "pkg"
    folder.mkdir()
    script = folder / "start.sh"
    script.write_text("#!/bin/sh\n")
    script.chmod(0o755)
    destination = tmp_path / "out" / "t.zip"
    digest = mod.make_zip(folder, destination, "traduco")
    with zipfile.ZipFile(destination) as z:
        info = z.getinfo("traduco/start.sh")
        assert (info.external_attr >> 16) & 0o111
    assert (tmp_path / "out" / "t.zip.sha256").read_text().startswith(digest)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlinks_are_stored_as_links_not_followed(tmp_path: Path) -> None:
    folder = tmp_path / "pkg"
    (folder / "real").mkdir(parents=True)
    (folder / "real" / "python").write_text("py")
    (folder / "cpython-3.12").symlink_to("real")
    mod.make_zip(folder, tmp_path / "t.zip", "traduco")
    with zipfile.ZipFile(tmp_path / "t.zip") as z:
        info = z.getinfo("traduco/cpython-3.12")
        assert stat.S_ISLNK(info.external_attr >> 16) and z.read(info) == b"real"
