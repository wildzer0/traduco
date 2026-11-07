"""Idempotent launcher steps. Each step is skipped when its inputs are unchanged."""

from __future__ import annotations

import os
import shutil
import socket
import sys
from dataclasses import dataclass
from pathlib import Path

from launcher.downloads import download, install_archive
from launcher.manifest import Manifest
from launcher.paths import Paths, clean_env, platform_key
from launcher.proc import Log, run_logged
from launcher.state import State, hash_files, hash_tree
from launcher.ui import UI, LauncherError

GB = 1024**3
FRONTEND_IGNORE = ("node_modules", "dist", ".vite", "test-results", "playwright-report")


@dataclass
class Context:
    paths: Paths
    manifest: Manifest
    state: State
    ui: UI
    log: Log
    offline: bool = False
    update: bool = False
    port: int | None = None
    workspace: Path | None = None


def uv_executable() -> str:
    for candidate in (os.environ.get("TRADUCO_UV"), os.environ.get("UV"), shutil.which("uv")):
        if candidate:
            return candidate
    raise LauncherError("E020", what="uv not found")


def child_env(ctx: Context) -> dict[str, str]:
    env = clean_env()
    env.setdefault("UV_PYTHON_INSTALL_DIR", str(ctx.paths.runtime / "python"))
    env.setdefault("UV_CACHE_DIR", str(ctx.paths.runtime / "uv-cache"))
    # The bootstrap points this at the launcher's own venv; the backend needs its own.
    env["UV_PROJECT_ENVIRONMENT"] = str(ctx.paths.backend / ".venv")
    return env


# --- step 1: preliminary checks -------------------------------------------------------------


def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if os.name != "nt":  # like uvicorn: a port in TIME_WAIT after a restart is still usable
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def select_port(requested: int | None, port_range: tuple[int, int]) -> int:
    if requested is not None:
        if not is_port_free(requested):
            raise LauncherError("E003", port=requested)
        return requested
    lo, hi = port_range
    for port in range(lo, hi + 1):
        if is_port_free(port):
            return port
    raise LauncherError("E004", lo=lo, hi=hi)


def needs_install(ctx: Context) -> bool:
    return not ctx.paths.backend_python.exists() or not (
        ctx.paths.dist.exists() or ctx.paths.node.exists()
    )


def check_disk(ctx: Context) -> None:
    need = ctx.manifest.min_free_gb
    have = shutil.disk_usage(ctx.paths.root).free / GB
    if have < need:
        raise LauncherError("E002", need=f"{need:g}", have=f"{have:.1f}")


def preflight(ctx: Context) -> int:
    """Check OS/architecture, disk space and pick the port. Returns the port to use."""
    try:
        key = platform_key()
    except KeyError as exc:
        import platform

        raise LauncherError("E001", platform=f"{sys.platform}/{platform.machine()}") from exc
    ctx.log.write(f"platform {key}, python {sys.version.split()[0]}")
    if needs_install(ctx):
        check_disk(ctx)
    port = select_port(ctx.port, ctx.manifest.port_range)
    ctx.log.write(f"port {port}")
    return port


# --- step 2: backend dependencies -----------------------------------------------------------


def backend_sync(ctx: Context) -> bool:
    """Install backend dependencies with uv. Returns False when already up to date."""
    p = ctx.paths
    digest = hash_files(
        [p.backend / "pyproject.toml", p.backend / "uv.lock", p.backend / ".python-version"]
    )
    if not ctx.update and ctx.state.get("backend") == digest and p.backend_python.exists():
        return False
    cmd = [
        uv_executable(),
        "sync",
        "--frozen",
        "--no-dev",
        "--inexact",
        "--project",
        str(p.backend),
    ]
    if ctx.offline:
        cmd.append("--offline")
    result = run_logged(cmd, cwd=p.root, env=child_env(ctx), log=ctx.log)
    if result.returncode != 0:
        raise LauncherError("E020", what="uv sync")
    ctx.state.set("backend", digest)
    return True


# --- steps 3 and 4: portable Node.js and frontend build -------------------------------------


def frontend_digest(ctx: Context) -> str:
    return hash_tree(ctx.paths.frontend, ignore=FRONTEND_IGNORE)


def frontend_needs_build(ctx: Context) -> bool:
    """Source checkouts are rebuilt when sources change; release packages ship ``dist``."""
    p = ctx.paths
    if not (p.frontend / "src").is_dir():
        return not (p.dist / "index.html").is_file()
    if ctx.update or not (p.dist / "index.html").is_file():
        return True
    return ctx.state.get("frontend") != frontend_digest(ctx)


def ensure_node(ctx: Context) -> bool:
    """Install the portable Node.js pinned in the manifest. Returns False if already there."""
    art = ctx.manifest.artifact("node", platform_key())
    node_exe = ctx.paths.node_bin / ("node.exe" if sys.platform == "win32" else "node")
    if node_exe.exists() and ctx.state.get("node") == art.version:
        return False
    archive = ctx.paths.downloads / art.url.rsplit("/", 1)[1]
    update, close = ctx.ui.progress(f"Node.js {art.version}")
    try:
        download(art.url, archive, art.sha256, offline=ctx.offline, progress=update)
    finally:
        close()
    install_archive(archive, ctx.paths.node)
    ctx.state.set("node", art.version)
    return True


def node_env(ctx: Context) -> dict[str, str]:
    env = child_env(ctx)
    env["PATH"] = f"{ctx.paths.node_bin}{os.pathsep}{env.get('PATH', '')}"
    env["COREPACK_HOME"] = str(ctx.paths.runtime / "corepack")
    env["COREPACK_ENABLE_DOWNLOAD_PROMPT"] = "0"
    env["CI"] = "true"
    return env


def build_frontend(ctx: Context) -> None:
    p = ctx.paths
    env = node_env(ctx)
    corepack = shutil.which("corepack", path=str(p.node_bin))
    if corepack is None:
        raise LauncherError("E021")
    install = [corepack, "pnpm", "install", "--frozen-lockfile"]
    if ctx.offline:
        install.append("--offline")
    for cmd in (install, [corepack, "pnpm", "build"]):
        if run_logged(cmd, cwd=p.frontend, env=env, log=ctx.log).returncode != 0:
            raise LauncherError("E021")
    ctx.state.set("frontend", frontend_digest(ctx))


# --- --reset ----------------------------------------------------------------------------------


def reset_runtime(ctx: Context) -> None:
    """Remove what the launcher installed. Keeps uv, its Python and the launcher venv (in use)."""
    p = ctx.paths
    for target in (p.node, p.downloads, p.runtime / "corepack", p.dist, p.frontend / "node_modules",
                   p.backend / ".venv"):  # fmt: skip
        shutil.rmtree(target, ignore_errors=True)
    p.state_file.unlink(missing_ok=True)
    ctx.state.data.clear()
