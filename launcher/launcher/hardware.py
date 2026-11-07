"""Hardware detection and model choice (RF-72, docs/02-architettura.md, hardware table).

Everything that touches the machine goes through small functions that tests replace; the choice
itself (:func:`choose_model`) is a pure function of the numbers.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from launcher.manifest import Manifest, Model

GB = 1024**3
APPLE_GPU_SHARE = 0.65  # on Apple Silicon the GPU can use about two thirds of the unified memory
Runner = Callable[[Sequence[str]], str]


@dataclass(frozen=True)
class Hardware:
    ram_gb: float
    gpu_name: str | None = None
    gpu_gb: float = 0.0
    gpu_kind: str | None = None  # nvidia | amd | apple


def _run(cmd: Sequence[str]) -> str:
    return subprocess.run(list(cmd), capture_output=True, text=True, timeout=15, check=True).stdout


def detect_ram_gb(read_meminfo: Callable[[], str] | None = None, run: Runner = _run) -> float:
    if sys.platform == "win32":
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [  # noqa: RUF012 - ctypes layout
                ("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                ("total", ctypes.c_ulonglong), ("avail", ctypes.c_ulonglong),
                ("page_total", ctypes.c_ulonglong), ("page_avail", ctypes.c_ulonglong),
                ("virt_total", ctypes.c_ulonglong), ("virt_avail", ctypes.c_ulonglong),
                ("ext", ctypes.c_ulonglong),
            ]  # fmt: skip

        status = Status()
        status.length = ctypes.sizeof(Status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))  # type: ignore[attr-defined]
        return status.total / GB
    if sys.platform == "darwin":
        return int(run(["sysctl", "-n", "hw.memsize"]).strip()) / GB
    text = read_meminfo() if read_meminfo else Path("/proc/meminfo").read_text()
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1]) * 1024 / GB
    return 0.0


def parse_nvidia_smi(output: str) -> tuple[str, float] | None:
    """Largest GPU in ``nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits``."""
    best: tuple[str, float] | None = None
    for line in output.strip().splitlines():
        name, _, mib = line.rpartition(",")
        try:
            gb = float(mib.strip()) / 1024
        except ValueError:
            continue
        if best is None or gb > best[1]:
            best = (name.strip() or "NVIDIA GPU", gb)
    return best


def detect_amd_vram_gb(sysfs: Path = Path("/sys/class/drm")) -> tuple[str, float] | None:
    """VRAM of an AMD GPU on Linux (``mem_info_vram_total`` in sysfs)."""
    best: tuple[str, float] | None = None
    for card in sorted(sysfs.glob("card*/device")):
        try:
            if (card / "vendor").read_text().strip().lower() != "0x1002":
                continue
            gb = int((card / "mem_info_vram_total").read_text().strip()) / GB
        except (OSError, ValueError):
            continue
        if best is None or gb > best[1]:
            best = ("AMD GPU", gb)
    return best


def detect(run: Runner = _run, ram_gb: float | None = None) -> Hardware:
    ram = detect_ram_gb(run=run) if ram_gb is None else ram_gb
    if sys.platform == "darwin" and platform.machine().lower() in ("arm64", "aarch64"):
        return Hardware(ram, "Apple Silicon", ram * APPLE_GPU_SHARE, "apple")
    try:
        found = parse_nvidia_smi(
            run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        )
    except (OSError, subprocess.SubprocessError):
        found = None
    if found:
        return Hardware(ram, found[0], found[1], "nvidia")
    if sys.platform.startswith("linux") and (amd := detect_amd_vram_gb()):
        return Hardware(ram, amd[0], amd[1], "amd")
    return Hardware(ram)


def choose_model(hw: Hardware, manifest: Manifest) -> tuple[Model, str]:
    """Pick the model from the table of the architecture document; returns it and the reason."""
    if hw.gpu_gb >= 20:
        return manifest.model("large"), "gpu_large"
    if hw.ram_gb >= 12 or hw.gpu_gb >= 6:
        return manifest.model("default"), "ram_or_gpu"
    return manifest.model("small"), "low_memory"
