from __future__ import annotations

from pathlib import Path

from launcher.hardware import (
    Hardware,
    choose_model,
    detect,
    detect_amd_vram_gb,
    detect_ram_gb,
    parse_nvidia_smi,
)
from launcher.manifest import load_manifest

MANIFEST = load_manifest(Path(__file__).resolve().parents[1] / "manifest.toml")


def tag(hw: Hardware) -> str:
    return choose_model(hw, MANIFEST)[0].tag


def test_table_of_the_architecture_document() -> None:
    assert tag(Hardware(ram_gb=8)) == "gemma4:e2b"  # little RAM, no GPU: reduced quality
    assert tag(Hardware(ram_gb=11.9)) == "gemma4:e2b"
    assert tag(Hardware(ram_gb=12)) == "gemma4:e4b"
    assert tag(Hardware(ram_gb=8, gpu_gb=6, gpu_kind="nvidia")) == "gemma4:e4b"
    assert tag(Hardware(ram_gb=8, gpu_gb=4, gpu_kind="nvidia")) == "gemma4:e2b"
    assert tag(Hardware(ram_gb=64, gpu_gb=24, gpu_kind="nvidia")) == "gemma4:26b-a4b"
    assert tag(Hardware(ram_gb=64, gpu_gb=19.9, gpu_kind="nvidia")) == "gemma4:e4b"


def test_the_reason_is_reported() -> None:
    assert choose_model(Hardware(ram_gb=4), MANIFEST)[1] == "low_memory"
    assert choose_model(Hardware(ram_gb=32), MANIFEST)[1] == "ram_or_gpu"
    assert choose_model(Hardware(ram_gb=32, gpu_gb=24), MANIFEST)[1] == "gpu_large"


def test_nvidia_smi_output_takes_the_largest_gpu() -> None:
    out = "NVIDIA GeForce RTX 5070 Laptop GPU, 8151\nNVIDIA T400, 4096\n"
    name, gb = parse_nvidia_smi(out) or ("", 0)
    assert name == "NVIDIA GeForce RTX 5070 Laptop GPU" and 7.9 < gb < 8.0
    assert parse_nvidia_smi("") is None
    assert parse_nvidia_smi("garbage line") is None


def test_ram_from_proc_meminfo() -> None:
    meminfo = "MemTotal:       16000000 kB\nMemFree:  1 kB\n"
    assert 15.2 < detect_ram_gb(read_meminfo=lambda: meminfo) < 15.3


def test_detect_uses_nvidia_when_present_and_survives_its_absence() -> None:
    def with_gpu(cmd):  # type: ignore[no-untyped-def]
        return "RTX 4090, 24564\n"

    hw = detect(run=with_gpu, ram_gb=32)
    assert (hw.gpu_kind, round(hw.gpu_gb)) == ("nvidia", 24)

    def without_gpu(cmd):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("nvidia-smi")

    assert detect(run=without_gpu, ram_gb=8).gpu_kind in (None, "amd")


def test_amd_vram_from_sysfs(tmp_path: Path) -> None:
    card = tmp_path / "card0" / "device"
    card.mkdir(parents=True)
    (card / "vendor").write_text("0x1002\n")
    (card / "mem_info_vram_total").write_text(str(16 * 1024**3))
    other = tmp_path / "card1" / "device"
    other.mkdir(parents=True)
    (other / "vendor").write_text("0x8086\n")  # Intel: ignored
    assert detect_amd_vram_gb(tmp_path) == ("AMD GPU", 16.0)
    assert detect_amd_vram_gb(tmp_path / "missing") is None
