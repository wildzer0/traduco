"""Versioned prompt files. ``translate@1`` lives in ``translate_v1.txt``."""

from pathlib import Path

DIR = Path(__file__).parent


def load(name: str, version: int) -> str:
    return (DIR / f"{name}_v{version}.txt").read_text(encoding="utf-8")
