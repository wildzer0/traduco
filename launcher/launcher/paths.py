"""Filesystem layout. Everything the launcher creates lives under ``.runtime/`` (RF-71)."""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def runtime(self) -> Path:
        return self.root / ".runtime"

    @property
    def downloads(self) -> Path:
        return self.runtime / "downloads"

    @property
    def logs(self) -> Path:
        return self.runtime / "logs"

    @property
    def node(self) -> Path:
        return self.runtime / "node"

    @property
    def state_file(self) -> Path:
        return self.runtime / "state.json"

    @property
    def backend(self) -> Path:
        return self.root / "backend"

    @property
    def frontend(self) -> Path:
        return self.root / "frontend"

    @property
    def dist(self) -> Path:
        return self.frontend / "dist"

    @property
    def backend_python(self) -> Path:
        sub = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
        return self.backend / ".venv" / sub

    @property
    def node_bin(self) -> Path:
        """Directory containing ``node`` and ``corepack`` in the portable Node.js."""
        return self.node if sys.platform == "win32" else self.node / "bin"

    def ensure(self) -> None:
        for d in (self.runtime, self.downloads, self.logs):
            d.mkdir(parents=True, exist_ok=True)


def default_root() -> Path:
    """Repository root: the launcher lives in ``<root>/launcher/launcher``."""
    return Path(__file__).resolve().parents[2]


def platform_key() -> str:
    """Return e.g. ``linux-x64`` or ``windows-arm64``; raises ``KeyError`` if unsupported."""
    os_name = {"linux": "linux", "darwin": "darwin", "win32": "windows"}[sys.platform]
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}[machine]
    return f"{os_name}-{arch}"


def clean_env() -> dict[str, str]:
    """Environment for child processes: UTF-8 everywhere, Python path pollution removed."""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    for var in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(var, None)
    return env
