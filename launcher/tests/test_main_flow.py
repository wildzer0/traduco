from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from launcher import __main__ as entry
from launcher import steps
from launcher.ui import UI

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "launcher").mkdir()
    shutil.copy(REPO / "launcher" / "manifest.toml", tmp_path / "launcher" / "manifest.toml")
    return tmp_path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    monkeypatch.setattr(steps, "preflight", lambda ctx: seen.append("checks") or 8123)
    monkeypatch.setattr(steps, "backend_sync", lambda ctx: seen.append("backend") or True)
    monkeypatch.setattr(steps, "ensure_pandoc", lambda ctx: seen.append("pandoc") or True)
    monkeypatch.setattr(steps, "frontend_needs_build", lambda ctx: False)

    def fake_llm(
        ctx: steps.Context, model: str | None, yes: bool, engine: str = "auto"
    ) -> steps.Llm:
        seen.append(f"llm:{model}:{yes}")
        ctx.ui.skip(2)  # the real one numbers the Ollama and model steps itself
        return steps.Llm(model="m")

    monkeypatch.setattr(steps, "setup_llm", fake_llm)
    monkeypatch.setattr(steps, "find_libreoffice", lambda: seen.append("office") or None)
    monkeypatch.setattr(
        entry,
        "serve",
        lambda ctx, port, open_browser, office=None: (
            seen.append(f"serve:{port}:{open_browser}") or 0
        ),
    )
    return seen


def test_new_options_are_accepted() -> None:
    args = entry.parse_args(
        [
            "--model",
            "gemma4:e2b",
            "--yes",
            "--prepare-only",
            "--offline",
            "--no-browser",
            "--port",
            "8123",
        ]
    )
    assert (args.model, args.yes, args.prepare_only, args.offline, args.no_browser, args.port) == (
        "gemma4:e2b",
        True,
        True,
        True,
        True,
        8123,
    )


def test_the_nine_steps_run_in_order(
    root: Path, calls: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    code = entry.run(entry.parse_args(["--model", "x", "--yes", "--no-browser"]), UI("en"), root)
    assert code == 0
    assert calls == ["checks", "backend", "pandoc", "llm:x:True", "office", "serve:8123:False"]
    out = capsys.readouterr().out
    for n in (1, 2, 3, 4, 5, 8, 9):  # 6 and 7 (Ollama, model) are numbered inside setup_llm
        assert f"[{n}/9]" in out, n


def test_prepare_only_installs_but_does_not_start(root: Path, calls: list[str]) -> None:
    assert entry.run(entry.parse_args(["--prepare-only"]), UI("en"), root) == 0
    assert calls == [
        "checks",
        "backend",
        "pandoc",
    ]  # no model, no server: for building an offline bundle


def test_a_launcher_error_is_shown_with_its_code(
    root: Path,
    calls: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from launcher.ui import LauncherError

    def boom(ctx: steps.Context) -> bool:
        raise LauncherError("E010", url="https://x", reason="timeout")

    monkeypatch.setattr(steps, "ensure_pandoc", boom)
    assert entry.run(entry.parse_args([]), UI("en"), root) == 1
    assert "[E010]" in capsys.readouterr().out
