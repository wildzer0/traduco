"""The language model: choice, state file for the interface, background download (RF-72, RF-74).

The download runs next to the backend, not before it: the browser opens at once, the editor works,
and the interface shows the progress (``.runtime/model.json`` -> ``/api/capabilities``).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from launcher import ollama
from launcher.ui import UI, LauncherError


class ModelState:
    """JSON file: ``state`` is one of unavailable, downloading, ready, error."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(
        self,
        state: str,
        model: str = "",
        completed: int = 0,
        total: int | None = None,
        error: str = "",
    ) -> None:
        payload = {
            "state": state, "model": model, "completed": completed, "total": total,
            "error": error, "updated": int(time.time()),
        }  # fmt: skip
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self.path)


class Downloader:
    """Pulls one model on a thread and keeps the state file up to date."""

    def __init__(self, host: str, tag: str, size_gb: float, state: ModelState, ui: UI) -> None:
        self.host, self.tag, self.size_gb = host, tag, size_gb
        self.state, self.ui = state, ui
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: LauncherError | None = None

    def start(self) -> None:
        self.state.write("downloading", self.tag)
        self.ui.info(self.ui.t("model.background", model=self.tag, gb=f"{self.size_gb:g}"))
        self._thread = threading.Thread(target=self._run, name="model-download", daemon=True)
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(5)

    def _run(self) -> None:
        last = {"pct": -10}

        def progress(_status: str, done: int, total: int | None) -> None:
            self.state.write("downloading", self.tag, done, total)
            if total:
                pct = done * 100 // total
                if pct - last["pct"] >= 10:
                    last["pct"] = pct
                    self.ui.info(self.ui.t("model.progress", model=self.tag, pct=pct))

        try:
            ollama.pull(self.host, self.tag, progress, self._stop.is_set)
        except LauncherError as err:
            self.error = err
            message, _ = err.render(self.ui.lang)
            self.state.write("error", self.tag, error=message)
            return
        if self._stop.is_set():
            return
        self.state.write("ready", self.tag)
        self.ui.info(self.ui.t("model.done", model=self.tag))
