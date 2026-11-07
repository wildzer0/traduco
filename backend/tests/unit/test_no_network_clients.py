"""Rule 1 / ADR-014: no network clients in backend code except the LLM client."""

from pathlib import Path

FORBIDDEN = ("urllib.request", "import requests", "import aiohttp", "import httpx")
# The model client, and the optional LanguageTool client for a server the author runs themselves
# (off by default, never an external address that was not configured; ADR-044).
ALLOWED = {
    "app/core/translation/llm_client.py",
    "app/core/spellcheck/languagetool.py",
}


def test_no_network_imports() -> None:
    root = Path(__file__).resolve().parents[2]
    for f in (root / "app").rglob("*.py"):
        rel = f.relative_to(root).as_posix()
        if rel in ALLOWED:
            continue
        text = f.read_text()
        for bad in FORBIDDEN:
            assert bad not in text, f"{rel} uses {bad}"
