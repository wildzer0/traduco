"""User-facing output: numbered steps, download progress, localized errors with solutions."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

MESSAGES: dict[str, dict[str, str]] = {
    "step.checks": {"it": "Controlli preliminari", "en": "Preliminary checks"},
    "step.backend": {"it": "Dipendenze del backend", "en": "Backend dependencies"},
    "step.node": {"it": "Node.js portabile", "en": "Portable Node.js"},
    "step.frontend": {"it": "Interfaccia web", "en": "Web interface"},
    "step.start": {"it": "Avvio di Traduco", "en": "Starting Traduco"},
    "done": {"it": "già pronto", "en": "already done"},
    "downloading": {"it": "Download di {name}", "en": "Downloading {name}"},
    "ready": {
        "it": "Traduco è attivo su {url} - premi Ctrl+C per fermarlo.",
        "en": "Traduco is running at {url} - press Ctrl+C to stop.",
    },
    "stopping": {"it": "Arresto in corso...", "en": "Stopping..."},
    "log": {"it": "Log: {path}", "en": "Log: {path}"},
    "reset": {
        "it": "Ripristino di .runtime/ (i progetti non vengono toccati)",
        "en": "Resetting .runtime/ (your projects are not touched)",
    },
    "model_note": {
        "it": "Nota: la scelta del modello e Ollama arrivano in una prossima versione.",
        "en": "Note: model selection and Ollama arrive in a later version.",
    },
    "E001": {
        "it": "Sistema non supportato: {platform}.",
        "en": "Unsupported system: {platform}.",
    },
    "E001.fix": {
        "it": "Usa Windows 10/11, Linux o macOS (x64 o arm64), oppure Docker Compose.",
        "en": "Use Windows 10/11, Linux or macOS (x64 or arm64), or Docker Compose.",
    },
    "E002": {
        "it": "Spazio su disco insufficiente: servono {need} GB, disponibili {have} GB.",
        "en": "Not enough disk space: {need} GB required, {have} GB available.",
    },
    "E002.fix": {
        "it": "Libera spazio nel disco che contiene la cartella del programma e riprova.",
        "en": "Free up space on the disk that holds the program folder and try again.",
    },
    "E003": {"it": "La porta {port} è occupata.", "en": "Port {port} is already in use."},
    "E003.fix": {
        "it": "Scegli un'altra porta con --port <n> oppure chiudi il programma che la usa.",
        "en": "Pick another port with --port <n> or close the program that uses it.",
    },
    "E004": {
        "it": "Nessuna porta libera tra {lo} e {hi}.",
        "en": "No free port between {lo} and {hi}.",
    },
    "E004.fix": {
        "it": "Chiudi qualche programma o indica una porta con --port <n>.",
        "en": "Close some programs or choose a port with --port <n>.",
    },
    "E010": {
        "it": "Download non riuscito: {url} ({reason}).",
        "en": "Download failed: {url} ({reason}).",
    },
    "E010.fix": {
        "it": "Controlla la connessione; dietro un proxy aziendale imposta HTTPS_PROXY. "
        "Il download riprende da dove si era fermato.",
        "en": "Check your connection; behind a corporate proxy set HTTPS_PROXY. "
        "The download resumes where it stopped.",
    },
    "E011": {
        "it": "Verifica SHA-256 fallita per {name}.",
        "en": "SHA-256 verification failed for {name}.",
    },
    "E011.fix": {
        "it": "Il file scaricato è corrotto o manomesso ed è stato eliminato: riprova più tardi.",
        "en": "The downloaded file is corrupt or tampered with and was deleted: try again later.",
    },
    "E012": {
        "it": "Modalità --offline: manca {name}.",
        "en": "--offline mode: {name} is missing.",
    },
    "E012.fix": {
        "it": "Usa il pacchetto offline completo oppure esegui un primo avvio con la rete.",
        "en": "Use the full offline bundle or run a first start with network access.",
    },
    "E020": {
        "it": "Installazione delle dipendenze fallita ({what}).",
        "en": "Dependency installation failed ({what}).",
    },
    "E020.fix": {
        "it": "Controlla la connessione e riprova; i dettagli sono nel log.",
        "en": "Check your connection and try again; details are in the log.",
    },
    "E021": {"it": "Build dell'interfaccia fallita.", "en": "Web interface build failed."},
    "E021.fix": {
        "it": "Riprova con --update; i dettagli sono nel log.",
        "en": "Try again with --update; details are in the log.",
    },
    "E099": {
        "it": "Errore imprevisto: {what}.",
        "en": "Unexpected error: {what}.",
    },
    "E099.fix": {
        "it": "Riprova; se persiste invia il file di log a chi mantiene il progetto.",
        "en": "Try again; if it persists send the log file to the project maintainers.",
    },
    "E030": {"it": "Il backend si è fermato subito.", "en": "The backend stopped immediately."},
    "E030.fix": {
        "it": "Guarda .runtime/logs/backend.log per il motivo.",
        "en": "See .runtime/logs/backend.log for the reason.",
    },
    "E031": {
        "it": "Il backend non risponde dopo {seconds} secondi.",
        "en": "The backend did not respond after {seconds} seconds.",
    },
    "E031.fix": {
        "it": "Guarda .runtime/logs/backend.log; un antivirus o firewall potrebbe bloccarlo.",
        "en": "See .runtime/logs/backend.log; an antivirus or firewall may be blocking it.",
    },
}


def detect_language() -> str:
    """``it`` when the system language is Italian, otherwise ``en``."""
    forced = os.environ.get("TRADUCO_LANG")
    if forced in ("it", "en"):
        return forced
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            return "it" if value.lower().startswith("it") else "en"
    if sys.platform == "win32":
        try:
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
            return "it" if (lang_id & 0x3FF) == 0x10 else "en"
        except (AttributeError, OSError):
            pass
    return "en"


class LauncherError(Exception):
    """A failure with a stable code, a message and a suggested solution."""

    def __init__(self, code: str, **params: object) -> None:
        super().__init__(code)
        self.code = code
        self.params = params

    def render(self, lang: str) -> tuple[str, str]:
        text = MESSAGES[self.code][lang].format(**self.params)
        fix = MESSAGES[f"{self.code}.fix"][lang]
        return f"[{self.code}] {text}", fix


class UI:
    def __init__(self, lang: str | None = None, console: Console | None = None) -> None:
        self.lang = lang or detect_language()
        self.console = console or Console(highlight=False, soft_wrap=True)
        self._total = 0
        self._n = 0

    def t(self, key: str, **params: object) -> str:
        return MESSAGES[key][self.lang].format(**params)

    def plan(self, total: int) -> None:
        self._total, self._n = total, 0

    def step(self, key: str) -> None:
        self._n += 1
        self.console.print(f"[bold][{self._n}/{self._total}][/bold] {self.t(key)}...")

    def info(self, text: str) -> None:
        self.console.print(f"      {text}")

    def error(self, err: LauncherError, log_path: object) -> None:
        message, fix = err.render(self.lang)
        self.console.print(f"\n[bold red]{message}[/bold red]")
        self.console.print(fix)
        self.console.print(self.t("log", path=log_path))

    def progress(self, name: str) -> tuple[Callable[[int, int | None], None], Callable[[], None]]:
        """Return ``(update, close)`` callbacks for a download."""
        label = self.t("downloading", name=name)
        if not self.console.is_terminal:
            last = {"pct": -25}

            def plain(done: int, total: int | None) -> None:
                if total:
                    pct = done * 100 // total
                    if pct - last["pct"] >= 25:
                        last["pct"] = pct
                        self.info(f"{label}: {pct}%")

            return plain, lambda: None
        bar = Progress(
            "      {task.description}", BarColumn(), DownloadColumn(), TransferSpeedColumn(),
            TimeRemainingColumn(), console=self.console, transient=True,
        )  # fmt: skip
        bar.start()
        task = bar.add_task(label, total=None)

        def update(done: int, total: int | None) -> None:
            bar.update(task, completed=done, total=total)

        return update, bar.stop
