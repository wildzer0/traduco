"""The built-in engine: llama.cpp's ``llama-server`` run by the launcher (ADR-041, RF-72).

For people who cannot or do not want to install Ollama. The launcher fetches a pinned
``llama-server`` and a GGUF model (both checked against SHA-256), starts the server on loopback and
hands the backend its OpenAI-style URL, exactly as it does with Ollama. Nothing needs administrator
rights and everything lives in ``.runtime/``.
"""

from __future__ import annotations

import contextlib
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from launcher import downloads
from launcher.hardware import Hardware
from launcher.manifest import BuiltinModel, Manifest
from launcher.model import ModelState
from launcher.paths import Paths, clean_env, platform_key
from launcher.ui import UI, LauncherError

PREFERRED_PORT = 18434
CONTEXT = 8192
READY_TIMEOUT = 900.0  # loading 3-5 GB from a slow disk can take minutes
SERVER = "llama-server.exe" if sys.platform == "win32" else "llama-server"
VERSION_MARK = ".version"


@dataclass(frozen=True)
class Plan:
    """What the launcher decided: which model, on which port."""

    model: BuiltinModel
    port: int

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def openai_url(self) -> str:
        return f"{self.base_url}/v1"


def choose_model(hw: Hardware, manifest: Manifest) -> tuple[BuiltinModel, str]:
    """The small model on CPU (speed matters more than size); the default one with Metal."""
    if hw.gpu_kind == "apple" and hw.ram_gb >= 12:
        return manifest.builtin_model("default"), "builtin_metal"
    return manifest.builtin_model("small"), "builtin_cpu"


def free_port(preferred: int = PREFERRED_PORT) -> int:
    """``preferred`` when it is free, otherwise any free loopback port."""
    for candidate in (preferred, 0):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return int(sock.getsockname()[1])
    raise LauncherError("E050", what="no free port")


def find_server(directory: Path) -> Path | None:
    """The ``llama-server`` executable somewhere under ``directory`` (archives differ in layout)."""
    if not directory.is_dir():
        return None
    return next((p for p in sorted(directory.rglob(SERVER)) if p.is_file()), None)


def ensure_binary(paths: Paths, manifest: Manifest, offline: bool) -> Path:
    try:
        artifact = manifest.artifact("llamacpp", platform_key())
    except KeyError as exc:
        raise LauncherError("E051", platform=sys.platform) from exc
    mark = paths.llamacpp / VERSION_MARK
    have = find_server(paths.llamacpp)
    if have and mark.is_file() and mark.read_text(encoding="utf-8").strip() == artifact.version:
        return have
    archive = downloads.download(
        artifact.url,
        paths.downloads / artifact.url.rsplit("/", 1)[1],
        artifact.sha256,
        offline=offline,
    )
    downloads.install_archive(archive, paths.llamacpp)
    server = find_server(paths.llamacpp)
    if server is None:
        raise LauncherError("E020", what=f"{SERVER} is not in {archive.name}")
    if sys.platform != "win32":
        server.chmod(server.stat().st_mode | 0o111)
    mark.write_text(artifact.version, encoding="utf-8")
    return server


def model_file(paths: Paths, model: BuiltinModel) -> Path:
    return paths.builtin_models / model.file


def is_ready(plan: Plan) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{plan.base_url}/health", timeout=2) as resp:
            return bool(resp.status == 200)
    except (urllib.error.URLError, OSError, TimeoutError):
        return False  # 503 while the model loads is an HTTPError: not ready yet


def start_server(
    binary: Path, weights: Path, plan: Plan, log: IO[bytes]
) -> subprocess.Popen[bytes]:
    cmd = [
        str(binary), "-m", str(weights), "--host", "127.0.0.1", "--port", str(plan.port),
        "--alias", plan.model.name, "-c", str(CONTEXT),
    ]  # fmt: skip
    env = clean_env()
    if sys.platform.startswith("linux"):
        env["LD_LIBRARY_PATH"] = str(binary.parent)  # its own libraries, never the system's
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0  # type: ignore[attr-defined]
    try:
        return subprocess.Popen(  # noqa: S603
            cmd, cwd=binary.parent, env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=flags,
        )  # fmt: skip
    except OSError as exc:
        raise LauncherError("E050", what=str(exc)) from exc


def wait_until_ready(
    plan: Plan, proc: subprocess.Popen[bytes], timeout: float = READY_TIMEOUT
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise LauncherError("E050", what=f"exit code {proc.returncode}")
        if is_ready(plan):
            return
        time.sleep(0.5)
    raise LauncherError("E050", what=f"no answer after {int(timeout)} s")


def stop_server(proc: subprocess.Popen[bytes], grace: float = 10.0) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


class Engine:
    """Prepares and runs the engine on a thread, next to the backend (RF-74).

    The state file tells the interface what is going on: ``downloading`` while the program and the
    model are fetched and while the model loads, then ``ready`` (or ``error``).
    """

    def __init__(
        self,
        paths: Paths,
        manifest: Manifest,
        plan: Plan,
        state: ModelState,
        ui: UI,
        *,
        offline: bool = False,
    ) -> None:  # noqa: E501
        self.paths, self.manifest, self.plan = paths, manifest, plan
        self.state, self.ui, self.offline = state, ui, offline
        self.server: subprocess.Popen[bytes] | None = None
        self.error: LauncherError | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def name(self) -> str:
        return self.plan.model.name

    def start(self) -> None:
        self.state.write("downloading", self.name)
        self._thread = threading.Thread(target=self._run, name="builtin-engine", daemon=True)
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(5)
        if self.server is not None:
            stop_server(self.server)

    def _run(self) -> None:
        model = self.plan.model
        last = {"pct": -10}

        def progress(done: int, total: int | None) -> None:
            with contextlib.suppress(OSError):
                self.state.write("downloading", self.name, done, total)
            if total:
                pct = done * 100 // total
                if pct - last["pct"] >= 10:
                    last["pct"] = pct
                    self.ui.info(self.ui.t("model.progress", model=self.name, pct=pct))

        try:
            binary = ensure_binary(self.paths, self.manifest, self.offline)
            weights = downloads.download(
                model.url, model_file(self.paths, model), model.sha256,
                offline=self.offline, timeout=60, progress=progress,
            )  # fmt: skip
            if self._stop.is_set():
                return
            with contextlib.suppress(OSError):
                self.state.write("downloading", self.name, 1, 1)  # loading into memory
            log = (self.paths.logs / "llama-server.log").open("ab")
            self.server = start_server(binary, weights, self.plan, log)
            wait_until_ready(self.plan, self.server)
        except LauncherError as err:
            self.error = err
            message, _ = err.render(self.ui.lang)
            with contextlib.suppress(OSError):
                self.state.write("error", self.name, error=message)
            return
        if self._stop.is_set():
            return
        self.state.write("ready", self.name)
        self.ui.info(self.ui.t("model.done", model=self.name))


def installed(paths: Paths, manifest: Manifest, model: BuiltinModel) -> bool:
    """Are the program and the model already on disk (nothing to download)?"""
    try:
        version = manifest.artifact("llamacpp", platform_key()).version
    except KeyError:
        return False
    mark = paths.llamacpp / VERSION_MARK
    return bool(
        find_server(paths.llamacpp)
        and mark.is_file()
        and mark.read_text(encoding="utf-8").strip() == version
        and model_file(paths, model).is_file()
    )
