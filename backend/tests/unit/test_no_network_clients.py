"""Rule 1 / ADR-014: no network clients in backend code except the LLM client."""

from pathlib import Path

FORBIDDEN = ("urllib.request", "import requests", "import aiohttp", "import httpx")
ALLOWED = {"app/core/translation/llm_client.py"}


def test_no_network_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    for f in (root / "app").rglob("*.py"):
        rel = f.relative_to(root).as_posix()
        if rel in ALLOWED:
            continue
        text = f.read_text()
        for bad in FORBIDDEN:
            assert bad not in text, f"{rel} uses {bad}"
