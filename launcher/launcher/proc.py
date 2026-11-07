"""Logging and subprocess helpers shared by the launcher steps."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO


class Log:
    """Append-only text log in ``.runtime/logs`` (RF-76)."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._fh: IO[str] = path.open("a", encoding="utf-8", errors="replace")

    def write(self, text: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self._fh.write(f"{stamp} {text}\n")
        self._fh.flush()

    @property
    def stream(self) -> IO[str]:
        return self._fh

    def close(self) -> None:
        self._fh.close()


def run_logged(
    cmd: Sequence[str], *, cwd: Path, env: Mapping[str, str], log: Log
) -> subprocess.CompletedProcess[None]:
    """Run ``cmd`` sending all output to the log; return the result (non-zero is not an error)."""
    log.write(f"$ {' '.join(cmd)}  (cwd={cwd})")
    proc = subprocess.run(
        list(cmd), cwd=cwd, env=dict(env), stdout=log.stream, stderr=subprocess.STDOUT, check=False
    )
    log.write(f"exit code {proc.returncode}")
    return proc  # type: ignore[return-value]
