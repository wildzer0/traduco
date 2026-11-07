"""Ollama: find it, start it, install it when the user agrees, pull the model (RF-72..74).

Ollama is only ever talked to over HTTP on loopback (proxies are bypassed on purpose); the pull is
resumable, so a download interrupted by Ctrl+C continues from where it stopped at the next start.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any

from launcher.ui import LauncherError

Progress = Callable[[str, int, int | None], None]
INSTALL_SCRIPT = "curl -fsSL https://ollama.com/install.sh | sh"


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api_get(host: str, path: str, timeout: float = 3.0) -> Any | None:
    """JSON answer of ``GET host+path`` or ``None`` when the server does not answer."""
    try:
        with _opener().open(f"{host.rstrip('/')}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None


def is_up(host: str) -> bool:
    return api_get(host, "/api/version") is not None


def models(host: str) -> list[str]:
    data = api_get(host, "/api/tags") or {}
    return [str(m.get("name", "")) for m in data.get("models", []) if isinstance(m, dict)]


def has_model(host: str, tag: str) -> bool:
    wanted = tag if ":" in tag else f"{tag}:latest"
    return wanted in models(host)


def endpoint_answers(base_url: str) -> bool:
    """Does an OpenAI-compatible server answer at ``base_url`` (``…/v1``)?"""
    return api_get(base_url, "/models") is not None


def pull(
    host: str, tag: str, on_progress: Progress, should_stop: Callable[[], bool] = lambda: False
) -> None:
    """Download ``tag`` through Ollama's API, reporting ``(status, done_bytes, total_bytes)``."""
    request = urllib.request.Request(
        f"{host.rstrip('/')}/api/pull",
        data=json.dumps({"model": tag, "stream": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _opener().open(request, timeout=120) as resp:
            for raw in resp:
                if should_stop():
                    return
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                event = json.loads(line)
                if "error" in event:
                    raise LauncherError("E042", model=tag, reason=str(event["error"]))
                on_progress(
                    str(event.get("status", "")),
                    int(event.get("completed") or 0),
                    int(event["total"]) if event.get("total") else None,
                )
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as exc:
        raise LauncherError("E042", model=tag, reason=str(getattr(exc, "reason", exc))) from exc


# --- finding, starting and installing ------------------------------------------------------------


def standard_locations() -> list[Path]:
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        return [local / "Programs" / "Ollama" / "ollama.exe"]
    if sys.platform == "darwin":
        return [
            Path("/Applications/Ollama.app/Contents/Resources/ollama"),
            Path("/usr/local/bin/ollama"),
            Path("/opt/homebrew/bin/ollama"),
        ]
    return [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]


def find_binary() -> Path | None:
    if found := shutil.which("ollama"):
        return Path(found)
    return next((p for p in standard_locations() if p.is_file()), None)


def server_address(host: str) -> str:
    """``http://127.0.0.1:11434`` -> ``127.0.0.1:11434`` (the form ``OLLAMA_HOST`` takes)."""
    return host.split("://", 1)[-1].rstrip("/")


def start_server(
    binary: Path, host: str, log: IO[bytes], models_dir: Path | None = None
) -> subprocess.Popen[bytes]:
    env = dict(os.environ)
    env["OLLAMA_HOST"] = server_address(host)
    if models_dir is not None:
        env["OLLAMA_MODELS"] = str(models_dir)
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0  # type: ignore[attr-defined]
    return subprocess.Popen(  # noqa: S603
        [str(binary), "serve"], env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags
    )


def wait_until_up(host: str, proc: subprocess.Popen[bytes] | None, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_up(host):
            return
        if proc is not None and proc.poll() is not None:
            raise LauncherError("E041")
        time.sleep(0.5)
    raise LauncherError("E041")


def install_command() -> list[str] | None:
    """The command that installs Ollama on this system, shown to the user before it is run."""
    if sys.platform == "win32":
        if shutil.which("winget"):
            return ["winget", "install", "--id", "Ollama.Ollama", "-e", "--silent",
                    "--accept-source-agreements", "--accept-package-agreements"]  # fmt: skip
        return None
    if sys.platform == "darwin":
        return ["brew", "install", "--cask", "ollama"] if shutil.which("brew") else None
    return ["sh", "-c", INSTALL_SCRIPT] if shutil.which("curl") else None


def install(command: list[str]) -> None:
    """Run the installer in the user's terminal (``sudo`` may ask for a password on Linux)."""
    try:
        result = subprocess.run(command, check=False)
    except OSError as exc:
        raise LauncherError("E040", what=str(exc)) from exc
    if result.returncode != 0:
        raise LauncherError("E040", what=f"exit code {result.returncode}")


def stop_server(proc: subprocess.Popen[bytes], grace: float = 10.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
