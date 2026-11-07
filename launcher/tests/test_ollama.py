from __future__ import annotations

import pytest

from launcher import ollama
from launcher.ui import LauncherError
from tests.conftest import FakeOllama


def test_detection_over_http(fake_ollama: FakeOllama) -> None:
    assert ollama.is_up(fake_ollama.url)
    assert not ollama.is_up("http://127.0.0.1:9")
    fake_ollama.models = ["gemma4:e4b", "other:latest"]
    assert ollama.models(fake_ollama.url) == ["gemma4:e4b", "other:latest"]
    assert ollama.has_model(fake_ollama.url, "gemma4:e4b")
    assert ollama.has_model(fake_ollama.url, "other")  # "other" means "other:latest"
    assert not ollama.has_model(fake_ollama.url, "gemma4:e2b")


def test_an_openai_style_endpoint_is_recognised(fake_ollama: FakeOllama) -> None:
    assert ollama.endpoint_answers(f"{fake_ollama.url}/v1")
    assert not ollama.endpoint_answers("http://127.0.0.1:9/v1")


def test_loopback_requests_ignore_the_proxy(
    monkeypatch: pytest.MonkeyPatch, fake_ollama: FakeOllama
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    assert ollama.is_up(fake_ollama.url)


def test_pull_reports_progress_and_the_model_arrives(fake_ollama: FakeOllama) -> None:
    seen: list[tuple[str, int, int | None]] = []
    ollama.pull(fake_ollama.url, "gemma4:e4b", lambda s, d, t: seen.append((s, d, t)))
    assert seen[0] == ("pulling manifest", 0, None)
    assert (("pulling abc", 250, 1000)) in seen and seen[-1][0] == "success"
    assert fake_ollama.pulled == ["gemma4:e4b"] and ollama.has_model(fake_ollama.url, "gemma4:e4b")


def test_pull_error_from_ollama_becomes_a_launcher_error(fake_ollama: FakeOllama) -> None:
    fake_ollama.pull_events = [{"status": "pulling manifest"}, {"error": "model not found"}]
    with pytest.raises(LauncherError) as info:
        ollama.pull(fake_ollama.url, "nope:1", lambda *_: None)
    assert info.value.code == "E042" and "model not found" in str(info.value.params["reason"])


def test_pull_can_be_stopped(fake_ollama: FakeOllama) -> None:
    seen: list[str] = []
    ollama.pull(
        fake_ollama.url, "gemma4:e4b", lambda s, *_: seen.append(s), should_stop=lambda: True
    )
    assert seen == []


def test_pull_from_an_unreachable_server() -> None:
    with pytest.raises(LauncherError) as info:
        ollama.pull("http://127.0.0.1:9", "x", lambda *_: None)
    assert info.value.code == "E042"


def test_server_address_is_what_ollama_host_expects() -> None:
    assert ollama.server_address("http://127.0.0.1:11434/") == "127.0.0.1:11434"


def test_install_command_by_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ollama.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(ollama.sys, "platform", "linux")
    assert ollama.install_command() == ["sh", "-c", "curl -fsSL https://ollama.com/install.sh | sh"]
    monkeypatch.setattr(ollama.sys, "platform", "win32")
    cmd = ollama.install_command() or []
    assert cmd[:3] == ["winget", "install", "--id"] and "Ollama.Ollama" in cmd and "--silent" in cmd
    monkeypatch.setattr(ollama.sys, "platform", "darwin")
    assert (ollama.install_command() or [])[:2] == ["brew", "install"]
    monkeypatch.setattr(ollama.shutil, "which", lambda name: None)
    assert ollama.install_command() is None  # no winget / brew / curl: the user is told what to do


def test_a_failing_installer_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    monkeypatch.setattr(
        ollama.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 3)
    )
    with pytest.raises(LauncherError) as info:
        ollama.install(["fake"])
    assert info.value.code == "E040" and "3" in str(info.value.params["what"])
