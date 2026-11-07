#!/usr/bin/env python3
"""Build the offline package (RF-78): a ZIP that starts without any network.

    uv run --project backend python tools/bundle-offline.py --os linux|windows [--with-model TAG]

It runs on the system it is built for (Python, wheels and Pandoc are platform specific; CI builds
both). Steps: let the launcher install everything (``--prepare-only``), then copy the program, the
frontend build and ``.runtime/{uv,python,uv-cache,pandoc}`` into a ZIP. With ``--with-model`` the
files of an Ollama model from ``~/.ollama/models`` are added; the launcher uses them when it starts
Ollama itself (``OLLAMA_MODELS``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_KEEP = ("uv", "python", "uv-cache", "pandoc")
TOP_FILES = ("start.sh", "start.cmd", "README.md", "LICENSE", "NOTICE", "CHANGELOG.md")
SKIP_DIRS = {
    "__pycache__",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "tests",
    "node_modules",
}


def _copy_tree(src: Path, dst: Path) -> None:
    def ignore(_dir: str, names: list[str]) -> set[str]:
        return {n for n in names if n in SKIP_DIRS or n.endswith(".pyc")}

    shutil.copytree(src, dst, ignore=ignore, symlinks=False)


def ollama_model_files(models_dir: Path, tag: str) -> list[Path]:
    """Manifest and blobs of ``tag`` (``gemma4:e4b``) inside an Ollama ``models`` folder."""
    name, _, version = tag.partition(":")
    manifest = (
        models_dir / "manifests" / "registry.ollama.ai" / "library" / name / (version or "latest")
    )
    if not manifest.is_file():
        raise SystemExit(f"model {tag} not found in {models_dir} (run `ollama pull {tag}` first)")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    digests = [data["config"]["digest"], *(layer["digest"] for layer in data["layers"])]
    blobs = [models_dir / "blobs" / d.replace(":", "-") for d in digests]
    missing = [b.name for b in blobs if not b.is_file()]
    if missing:
        raise SystemExit(f"incomplete model files: {', '.join(missing)}")
    return [manifest, *blobs]


def stage(
    root: Path,
    out: Path,
    uv: Path,
    state: dict[str, str],
    model_files: tuple[Path, Path, list[Path]] | None = None,
) -> None:
    """Copy what a user needs into ``out`` (an empty folder). Pure file work, no network."""
    for name in TOP_FILES:
        if (root / name).is_file():
            shutil.copy2(root / name, out / name)
    _copy_tree(root / "launcher", out / "launcher")
    backend = out / "backend"
    backend.mkdir()
    _copy_tree(root / "backend" / "app", backend / "app")
    for name in ("pyproject.toml", "uv.lock", ".python-version"):
        shutil.copy2(root / "backend" / name, backend / name)
    dist = root / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("frontend/dist is missing: run the launcher first (--prepare-only)")
    shutil.copytree(dist, out / "frontend" / "dist")
    if (root / "examples").is_dir():
        _copy_tree(root / "examples", out / "examples")
    runtime = out / ".runtime"
    runtime.mkdir()
    for name in RUNTIME_KEEP:
        source = root / ".runtime" / name
        if source.is_dir():
            shutil.copytree(source, runtime / name, symlinks=True)
    (runtime / "uv").mkdir(exist_ok=True)
    shutil.copy2(uv, runtime / "uv" / uv.name)
    # what the launcher must believe is installed; venvs are rebuilt from the cache at first start
    keep = {k: v for k, v in state.items() if k == "pandoc"}
    (runtime / "state.json").write_text(json.dumps(keep, indent=2), encoding="utf-8")
    if model_files:
        models_dir, _tag, files = model_files
        for f in files:
            target = runtime / "ollama-models" / f.relative_to(models_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)


def make_zip(folder: Path, destination: Path, prefix: str) -> str:
    """Zip ``folder``; symlinks (uv's Python has some) are stored as links, modes are kept."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(folder.rglob("*")):
            name = f"{prefix}/{path.relative_to(folder).as_posix()}"
            if path.is_symlink():
                info = zipfile.ZipInfo(name)
                info.create_system = 3  # Unix: the mode below is meaningful
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                z.writestr(info, os.readlink(path))
            elif path.is_file():
                info = zipfile.ZipInfo.from_file(path, name)
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_name(destination.name + ".sha256").write_text(
        f"{digest}  {destination.name}\n"
    )
    return digest


def fill_cache(uv: Path) -> None:
    """Make sure every wheel of the backend and of the launcher is in ``.runtime/uv-cache``.

    The offline start recreates both virtual environments from this cache without the network.
    Throw-away environments are used: only the cache matters.
    """
    for project in ("backend", "launcher"):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **os.environ,
                "UV_CACHE_DIR": str(ROOT / ".runtime" / "uv-cache"),
                "UV_PYTHON_INSTALL_DIR": str(ROOT / ".runtime" / "python"),
                "UV_PROJECT_ENVIRONMENT": str(Path(tmp) / "venv"),
            }
            subprocess.run(
                [str(uv), "sync", "--frozen", "--no-dev", "--project", str(ROOT / project)],
                env=env, cwd=ROOT, check=True,
            )  # fmt: skip


def prepare() -> None:
    # start.cmd (not bootstrap.ps1 directly) because it fixes PSModulePath for PowerShell 5.1
    script = ["cmd", "/c", "start.cmd"] if sys.platform == "win32" else ["./start.sh"]
    subprocess.run(
        [*script, "--prepare-only", "--no-browser"], cwd=ROOT, check=True, stdin=subprocess.DEVNULL
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--os", required=True, choices=["linux", "windows"])
    parser.add_argument(
        "--with-model", metavar="TAG", help="include this Ollama model (needs ~/.ollama/models)"
    )
    parser.add_argument("--models-dir", type=Path, default=Path.home() / ".ollama" / "models")
    parser.add_argument("--out", type=Path, default=ROOT / "build")
    parser.add_argument(
        "--skip-prepare", action="store_true", help="the launcher has already installed everything"
    )
    args = parser.parse_args()
    here = (
        "windows"
        if sys.platform == "win32"
        else "linux"
        if sys.platform.startswith("linux")
        else sys.platform
    )
    if here != args.os:
        raise SystemExit(
            f"build the {args.os} package on {args.os} (this is {here}); the CI builds both"
        )
    if not args.skip_prepare:
        prepare()
    uv = Path(os.environ.get("TRADUCO_UV") or shutil.which("uv") or "")
    local_uv = ROOT / ".runtime" / "uv" / ("uv.exe" if here == "windows" else "uv")
    uv = local_uv if local_uv.is_file() else uv
    if not uv.is_file():
        raise SystemExit("uv not found")
    fill_cache(uv)
    state_file = ROOT / ".runtime" / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
    model = None
    if args.with_model:
        model = (
            args.models_dir,
            args.with_model,
            ollama_model_files(args.models_dir, args.with_model),
        )
    match = re.search(r"^## \[(\d+\.\d+\.\d+)\]", (ROOT / "CHANGELOG.md").read_text(), re.MULTILINE)
    version = match.group(1) if match else "dev"
    name = f"traduco-{version}-{args.os}-offline"
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / name
        staging.mkdir()
        stage(ROOT, staging, uv, state, model)
        digest = make_zip(staging, args.out / f"{name}.zip", "traduco")
    print(f"{args.out / (name + '.zip')}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
