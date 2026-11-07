"""Idempotent launcher steps. Each step is skipped when its inputs are unchanged."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from launcher import hardware, ollama
from launcher.downloads import download, install_archive
from launcher.manifest import Manifest
from launcher.model import ModelState
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
    llm: Llm | None = None


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


# --- step 1: preliminary checks --------------------------------------------------------------


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


# --- step 2: backend dependencies ------------------------------------------------------------


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


# --- steps 3 and 4: portable Node.js and frontend build --------------------------------------


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


# --- --reset ---------------------------------------------------------------------------------


def reset_runtime(ctx: Context) -> None:
    """Remove what the launcher installed. Keeps uv, its Python and the launcher venv (in use)."""
    p = ctx.paths
    for target in (p.node, p.downloads, p.runtime / "corepack", p.dist, p.frontend / "node_modules",
                   p.backend / ".venv"):  # fmt: skip
        shutil.rmtree(target, ignore_errors=True)
    p.state_file.unlink(missing_ok=True)
    ctx.state.data.clear()


# --- step: portable Pandoc -------------------------------------------------------------------


def ensure_pandoc(ctx: Context) -> bool:
    """Install the pinned Pandoc into ``.runtime/pandoc``; False if it is already there."""
    art = ctx.manifest.artifact("pandoc", platform_key())
    if ctx.paths.pandoc_bin.exists() and ctx.state.get("pandoc") == art.version:
        return False
    archive = ctx.paths.downloads / art.url.rsplit("/", 1)[1]
    update, close = ctx.ui.progress(f"Pandoc {art.version}")
    try:
        download(art.url, archive, art.sha256, offline=ctx.offline, progress=update)
    finally:
        close()
    install_archive(archive, ctx.paths.pandoc)
    if sys.platform != "win32":
        ctx.paths.pandoc_bin.chmod(0o755)
    ctx.state.set("pandoc", art.version)
    return True


# --- step: LibreOffice (detection only) ------------------------------------------------------


def find_libreoffice() -> Path | None:
    """LibreOffice is never installed by the launcher (docs/02): it is only looked for."""
    for name in ("soffice", "libreoffice"):
        if found := shutil.which(name):
            return Path(found)
    candidates: list[Path] = []
    if sys.platform == "win32":
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            if base := os.environ.get(var):
                candidates.append(Path(base) / "LibreOffice" / "program" / "soffice.exe")
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"))
    return next((c for c in candidates if c.is_file()), None)


# --- steps: hardware, Ollama and the model ---------------------------------------------------


@dataclass
class Llm:
    """What the launcher decided about the language model."""

    model: str | None = None
    size_gb: float = 0.0
    host: str | None = None  # Ollama's address when the launcher manages it
    base_url: str | None = None  # OpenAI-style URL handed to the backend
    external: bool = False  # the user already configured a server: the launcher leaves it alone
    server: subprocess.Popen[bytes] | None = None  # an Ollama started by the launcher
    pull: bool = False
    note: str = ""  # why there is no model (for the interface)


def saved_settings(workspace: Path) -> dict[str, str]:
    """``llm_base_url`` / ``llm_model`` the user saved in the app (``.traduco/settings.yaml``)."""
    found: dict[str, str] = {}
    try:
        text = (workspace / ".traduco" / "settings.yaml").read_text(encoding="utf-8")
    except OSError:
        return found
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in ("llm_base_url", "llm_model"):
            found[key.strip()] = value.strip().strip("'\"")
    return found


def configured_endpoint(workspace: Path) -> tuple[str | None, str | None]:
    saved = saved_settings(workspace)
    url = saved.get("llm_base_url") or os.environ.get("TRADUCO_LLM_BASE_URL")
    model = saved.get("llm_model") or os.environ.get("TRADUCO_LLM_MODEL")
    return url, model


def setup_llm(ctx: Context, requested_model: str | None, assume_yes: bool) -> Llm:
    """Steps 5-7: choose the model, start or install Ollama, check the model is there."""
    ui, m = ctx.ui, ctx.manifest
    workspace = ctx.workspace or Path.home() / "Traduco"
    host = os.environ.get("TRADUCO_OLLAMA_HOST", m.ollama_host)
    url, saved_model = configured_endpoint(workspace)

    # a server the user already configured and that answers is used as it is
    default_url = f"{host.rstrip('/')}/v1"
    if url and url.rstrip("/") != default_url and ollama.endpoint_answers(url):
        ui.info(ui.t("ollama.external", url=url))
        ui.skip(2)  # the Ollama and model steps do not apply
        return Llm(model=saved_model, base_url=url, external=True)

    hw = hardware.detect()
    chosen, why = hardware.choose_model(hw, m)
    tag, reason = chosen.tag, why
    size = chosen.size_gb
    if requested_model:
        tag, reason, size = requested_model, "requested", _size_of(m, requested_model)
    elif saved_model:
        tag, reason, size = saved_model, "saved", _size_of(m, saved_model)
    ctx.log.write(f"hardware {hw}, model {tag} ({reason})")
    gpu = (
        ui.t("hardware.gpu", name=hw.gpu_name, gb=f"{hw.gpu_gb:.0f}")
        if hw.gpu_name
        else ui.t("hardware.nogpu")
    )
    ui.info(ui.t("hardware.found", ram=f"{hw.ram_gb:.0f}", gpu=gpu))
    ui.info(ui.t("model.chosen", model=tag, why=ui.t(f"model.why.{reason}")))

    ui.step("step.ollama")
    llm = Llm(model=tag, size_gb=size, host=host, base_url=f"{host.rstrip('/')}/v1")
    if ollama.is_up(host):
        ui.info(ui.t("ollama.running"))
    else:
        binary = ollama.find_binary()
        if binary is None:
            binary = _offer_install(ctx, assume_yes)
        if binary is None:
            ui.skip(1)
            return Llm(model=tag, note="unavailable")
        ui.info(ui.t("ollama.starting"))
        models_dir = ctx.paths.ollama_models if ctx.paths.ollama_models.is_dir() else None
        log = (ctx.paths.logs / "ollama.log").open("ab")
        llm.server = ollama.start_server(binary, host, log, models_dir)
        try:
            ollama.wait_until_up(host, llm.server)
        except LauncherError:
            ollama.stop_server(llm.server)
            raise

    ui.step("step.model")
    if ollama.has_model(host, tag):
        ui.info(ui.t("model.have", model=tag))
        return llm
    if ctx.offline:
        if llm.server:
            ollama.stop_server(llm.server)
        raise LauncherError("E012", name=f"{tag} (Ollama)")
    need = size
    have = shutil.disk_usage(ctx.paths.root).free / GB
    if have < need:
        llm.note = "no_space"
        err = LauncherError("E043", model=tag, need=f"{need:g}", have=f"{have:.1f}")
        message, fix = err.render(ui.lang)
        ui.info(f"{message} {fix}")
        ModelState(ctx.paths.model_state).write("error", tag, error=message)
        return llm
    llm.pull = True
    return llm


def _size_of(manifest: Manifest, tag: str) -> float:
    for kind in ("small", "default", "large"):
        known = manifest.model(kind)
        if known.tag == tag:
            return known.size_gb
    return 8.0  # unknown tag: a typical size, only used for the disk check


def _offer_install(ctx: Context, assume_yes: bool) -> Path | None:
    """Ollama is missing: with the user's consent install it. Returns its binary, or None."""
    ui = ctx.ui
    if ctx.offline:
        ui.info(ui.t("ollama.offline"))
        return None
    if ctx.state.get("ollama_declined") == "1" and not ctx.update and not assume_yes:
        ui.info(ui.t("ollama.declined"))
        return None
    command = ollama.install_command()
    if command is None:
        ui.info(ui.t("ollama.nocommand"))
        return None
    if not ui.confirm("ollama.ask", "ollama.prompt", assume_yes, command=" ".join(command)):
        ctx.state.set("ollama_declined", "1")
        ui.info(ui.t("ollama.declined"))
        return None
    ollama.install(command)
    binary = ollama.find_binary()
    if binary is None:
        raise LauncherError("E040", what="the installer finished but ollama was not found")
    ctx.state.set("ollama_declined", "0")
    return binary
