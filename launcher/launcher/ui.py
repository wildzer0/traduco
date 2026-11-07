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
    "step.pandoc": {"it": "Pandoc portabile", "en": "Portable Pandoc"},
    "step.frontend": {"it": "Interfaccia web", "en": "Web interface"},
    "step.hardware": {"it": "Hardware e modello", "en": "Hardware and model"},
    "step.ollama": {"it": "Ollama", "en": "Ollama"},
    "step.model": {"it": "Modello di traduzione", "en": "Translation model"},
    "step.office": {"it": "LibreOffice (per PDF e ODT)", "en": "LibreOffice (for PDF and ODT)"},
    "step.start": {"it": "Avvio di Traduco", "en": "Starting Traduco"},
    "hardware.found": {
        "it": "{ram} GB di RAM, {gpu}",
        "en": "{ram} GB of RAM, {gpu}",
    },
    "hardware.nogpu": {"it": "nessuna GPU rilevata", "en": "no GPU detected"},
    "hardware.gpu": {"it": "{name} ({gb} GB)", "en": "{name} ({gb} GB)"},
    "model.chosen": {
        "it": "Modello scelto: {model} ({why})",
        "en": "Chosen model: {model} ({why})",
    },
    "model.why.low_memory": {
        "it": "poca memoria: qualità ridotta, puoi cambiarlo con --model",
        "en": "little memory: reduced quality, change it with --model",
    },
    "model.why.ram_or_gpu": {"it": "adatto a questo computer", "en": "suits this computer"},
    "model.why.gpu_large": {
        "it": "GPU potente: modello più grande",
        "en": "powerful GPU: larger model",
    },
    "model.why.requested": {"it": "scelto da te", "en": "chosen by you"},
    "model.why.saved": {"it": "dalle tue impostazioni", "en": "from your settings"},
    "ollama.external": {
        "it": "Uso il server di modelli già configurato: {url}",
        "en": "Using the model server already configured: {url}",
    },
    "ollama.running": {"it": "Ollama è già attivo", "en": "Ollama is already running"},
    "ollama.starting": {"it": "Avvio di Ollama", "en": "Starting Ollama"},
    "ollama.ask": {
        "it": "Ollama (il programma che esegue il modello sul tuo computer) non è installato.\n"
        "      Installarlo adesso? Comando: {command}",
        "en": "Ollama (the program that runs the model on your computer) is not installed.\n"
        "      Install it now? Command: {command}",
    },
    "ollama.prompt": {"it": "Installare Ollama? [s/N] ", "en": "Install Ollama? [y/N] "},
    "ollama.nocommand": {
        "it": "Ollama non è installato e non posso installarlo da solo su questo sistema: "
        "scaricalo da https://ollama.com/download e rilancia, oppure imposta un altro server in Impostazioni.",
        "en": "Ollama is not installed and I cannot install it by myself on this system: "
        "download it from https://ollama.com/download and run again, or set another server in Settings.",
    },
    "ollama.declined": {
        "it": "Ollama non installato: Traduco parte lo stesso. In Impostazioni puoi indicare un altro "
        "server di modelli; per installare Ollama in seguito usa --update.",
        "en": "Ollama not installed: Traduco starts anyway. In Settings you can point to another model "
        "server; to install Ollama later use --update.",
    },
    "ollama.offline": {
        "it": "Modalità --offline: Ollama non è disponibile, il modello non sarà usabile.",
        "en": "--offline mode: Ollama is not available, the model will not be usable.",
    },
    "builtin.ask": {
        "it": "Posso usare il motore integrato di Traduco (llama.cpp) al posto di Ollama: "
        "non serve installare nulla, scarica un programma piccolo e il modello {model} "
        "(circa {gb} GB). Senza scheda grafica è più lento.",
        "en": "I can use Traduco's built-in engine (llama.cpp) instead of Ollama: nothing to "
        "install, it downloads a small program and the model {model} (about {gb} GB). "
        "It is slower without a graphics card.",
    },
    "builtin.prompt": {
        "it": "Usare il motore integrato? [s/N] ",
        "en": "Use the built-in engine? [y/N] ",
    },
    "builtin.declined": {
        "it": "Motore integrato non usato: Traduco parte lo stesso, senza traduzione automatica. "
        "Per ripensarci usa --llm builtin.",
        "en": "Built-in engine not used: Traduco starts anyway, without automatic translation. "
        "To change your mind use --llm builtin.",
    },
    "builtin.chosen_by_you": {
        "it": "Uso il motore integrato (llama.cpp), senza Ollama",
        "en": "Using the built-in engine (llama.cpp), without Ollama",
    },
    "builtin.engine": {"it": "motore integrato", "en": "built-in engine"},
    "builtin.background": {
        "it": "Preparo il motore integrato e il modello {model} in sottofondo: "
        "l'editor funziona già, la traduzione parte appena è pronto.",
        "en": "Preparing the built-in engine and the model {model} in the background: "
        "the editor works already, translation starts as soon as it is ready.",
    },
    "model.why.builtin_cpu": {
        "it": "il più leggero, per girare senza scheda grafica",
        "en": "the lightest, to run without a graphics card",
    },
    "model.why.builtin_metal": {
        "it": "adatto a questo Mac (accelerazione Metal)",
        "en": "suits this Mac (Metal acceleration)",
    },
    "model.have": {
        "it": "Il modello {model} è già scaricato",
        "en": "Model {model} is already downloaded",
    },
    "model.background": {
        "it": "Scarico {model} (circa {gb} GB) in sottofondo: puoi già usare l'editor, "
        "la traduzione parte appena il modello è pronto.",
        "en": "Downloading {model} (about {gb} GB) in the background: you can use the editor now, "
        "translation starts as soon as the model is ready.",
    },
    "model.progress": {"it": "Modello {model}: {pct}%", "en": "Model {model}: {pct}%"},
    "model.done": {"it": "Modello {model} pronto", "en": "Model {model} ready"},
    "model.none": {"it": "Nessun modello da preparare", "en": "No model to prepare"},
    "office.found": {"it": "Trovato: {path}", "en": "Found: {path}"},
    "office.absent": {
        "it": "Non installato: PDF e ODT resteranno disattivati (il DOCX funziona). "
        "Per averli installa LibreOffice da https://www.libreoffice.org/download.",
        "en": "Not installed: PDF and ODT stay disabled (DOCX works). "
        "To get them install LibreOffice from https://www.libreoffice.org/download.",
    },
    "pandoc.have": {
        "it": "Pandoc {version} già installato",
        "en": "Pandoc {version} already installed",
    },
    "done": {"it": "già pronto", "en": "already done"},
    "prepared": {
        "it": "Preparazione completata (--prepare-only): niente viene avviato.",
        "en": "Preparation finished (--prepare-only): nothing is started.",
    },
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
    "E040": {
        "it": "Installazione di Ollama non riuscita ({what}).",
        "en": "Ollama installation failed ({what}).",
    },
    "E040.fix": {
        "it": "Installalo a mano da https://ollama.com/download e rilancia; oppure imposta un "
        "altro server di modelli in Impostazioni.",
        "en": "Install it by hand from https://ollama.com/download and run again; or set another "
        "model server in Settings.",
    },
    "E041": {"it": "Ollama non si avvia.", "en": "Ollama does not start."},
    "E041.fix": {
        "it": "Guarda .runtime/logs/ollama.log; se la porta 11434 è occupata chiudi l'altro programma.",
        "en": "See .runtime/logs/ollama.log; if port 11434 is in use close the other program.",
    },
    "E042": {
        "it": "Download del modello {model} non riuscito ({reason}).",
        "en": "Download of model {model} failed ({reason}).",
    },
    "E042.fix": {
        "it": "Controlla la connessione (proxy: HTTPS_PROXY per Ollama) e rilancia: il download riprende.",
        "en": "Check your connection (proxy: HTTPS_PROXY for Ollama) and run again: the download resumes.",
    },
    "E043": {
        "it": "Spazio insufficiente per il modello {model}: servono circa {need} GB, disponibili {have} GB.",
        "en": "Not enough space for model {model}: about {need} GB needed, {have} GB available.",
    },
    "E043.fix": {
        "it": "Libera spazio oppure scegli un modello più piccolo con --model gemma4:e2b.",
        "en": "Free up space or choose a smaller model with --model gemma4:e2b.",
    },
    "E050": {
        "it": "Il motore integrato non si avvia ({what}).",
        "en": "The built-in engine does not start ({what}).",
    },
    "E050.fix": {
        "it": "Guarda .runtime/logs/llama-server.log; con poca memoria prova a chiudere altri programmi.",
        "en": "See .runtime/logs/llama-server.log; if memory is short try closing other programs.",
    },
    "E051": {
        "it": "Il motore integrato non è disponibile per questo sistema ({platform}).",
        "en": "The built-in engine is not available for this system ({platform}).",
    },
    "E051.fix": {
        "it": "Installa Ollama da https://ollama.com/download oppure imposta un altro server in Impostazioni.",
        "en": "Install Ollama from https://ollama.com/download or set another server in Settings.",
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

    def skip(self, count: int) -> None:
        """Steps that do not apply this time still count, so the numbering stays [n/total]."""
        self._n += count

    def step(self, key: str) -> None:
        self._n += 1
        self.console.print(f"[bold][{self._n}/{self._total}][/bold] {self.t(key)}...")

    def confirm(
        self, question_key: str, prompt_key: str, assume_yes: bool, **params: object
    ) -> bool:
        """Ask a yes/no question. Without a terminal the answer is no, unless ``--yes`` was given."""
        self.info(self.t(question_key, **params))
        if assume_yes:
            return True
        if not sys.stdin or not sys.stdin.isatty():
            return False
        try:
            answer = input("      " + self.t(prompt_key)).strip().lower()
        except EOFError:
            return False
        return answer in ("s", "si", "sì", "y", "yes")

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
