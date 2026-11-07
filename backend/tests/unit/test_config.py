from pathlib import Path

import pytest

from app.config import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.llm_base_url.endswith("/v1")
    assert s.frontend_dist is None


def test_env_override_and_home_expansion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADUCO_WORKSPACES_DIR", "~/docs")
    monkeypatch.setenv("TRADUCO_LLM_MODEL", "x")
    s = Settings(_env_file=None)
    assert s.llm_model == "x"
    assert s.workspaces_path == Path.home() / "docs"
