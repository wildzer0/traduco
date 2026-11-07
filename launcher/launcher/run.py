"""Start the backend, wait for ``/api/health``, open the browser, stop cleanly on Ctrl+C."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from launcher import ollama
from launcher.model import Downloader, ModelState
from launcher.paths import clean_env
from launcher.steps import Context
from launcher.ui import LauncherError

HEALTH_TIMEOUT = 60.0


def wait_for_health(
    base_url: str,
    proc: subprocess.Popen[bytes] | None,
    timeout: float = HEALTH_TIMEOUT,
    interval: float = 0.25,
) -> None:
    """Poll ``/api/health``. Proxies are bypassed: this is a loopback request."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc is not None and proc.poll() is not None:
            raise LauncherError("E030")
        try:
            with opener.open(f"{base_url}/api/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(interval)
    raise LauncherError("E031", seconds=int(timeout))


def stop(proc: subprocess.Popen[bytes], grace: float = 10.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def backend_env(ctx: Context, workspace: Path, office: Path | None) -> dict[str, str]:
    """Environment of the backend: where things are, and which model server to use."""
    p = ctx.paths
    env = clean_env()
    env["TRADUCO_FRONTEND_DIST"] = str(p.dist)
    env["TRADUCO_WORKSPACES_DIR"] = str(workspace)
    env["TRADUCO_RUNTIME_DIR"] = str(p.runtime)
    if p.pandoc_bin.exists():
        env["TRADUCO_PANDOC"] = str(p.pandoc_bin)
    if office is not None:
        env["TRADUCO_SOFFICE"] = str(office)
    llm = ctx.llm
    if llm is not None and not llm.external and llm.base_url and llm.model:
        env["TRADUCO_LLM_BASE_URL"] = llm.base_url
        env["TRADUCO_LLM_MODEL"] = llm.model
    return env


def serve(ctx: Context, port: int, open_browser: bool, office: Path | None = None) -> int:
    p = ctx.paths
    workspace = ctx.workspace or Path.home() / "Traduco"
    workspace.mkdir(parents=True, exist_ok=True)
    env = backend_env(ctx, workspace, office)
    cmd = [str(p.backend_python), "-m", "uvicorn", "app.main:app",
           "--host", "127.0.0.1", "--port", str(port)]  # fmt: skip
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0  # type: ignore[attr-defined]
    ctx.log.write(f"$ {' '.join(cmd)}")
    llm = ctx.llm
    state = ModelState(p.model_state)
    downloader: Downloader | None = None
    if llm is None or llm.external:
        state.write(
            "ready" if llm and llm.model else "unavailable", llm.model if llm and llm.model else ""
        )
    elif llm.note == "unavailable":
        state.write("unavailable", llm.model or "")
    elif llm.pull and llm.host and llm.model:
        downloader = Downloader(llm.host, llm.model, llm.size_gb, state, ctx.ui)
    elif llm.note != "no_space":
        state.write("ready", llm.model or "")
    with (p.logs / "backend.log").open("ab") as backend_log:
        proc = subprocess.Popen(  # noqa: S603
            cmd, cwd=p.backend, env=env, stdout=backend_log, stderr=subprocess.STDOUT,
            creationflags=flags,
        )  # fmt: skip
        url = f"http://127.0.0.1:{port}"
        try:
            wait_for_health(url, proc)
            ctx.ui.info(ctx.ui.t("ready", url=url))
            if downloader is not None:
                downloader.start()
            if open_browser:
                webbrowser.open(url)
            proc.wait()
            return proc.returncode or 0
        except KeyboardInterrupt:
            ctx.ui.info(ctx.ui.t("stopping"))
            return 0
        finally:
            if downloader is not None:
                downloader.stop()
            stop(proc)
            if llm is not None and llm.server is not None:
                ollama.stop_server(llm.server)  # only an Ollama the launcher started itself
