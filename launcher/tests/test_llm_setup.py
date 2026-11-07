"""Steps 5-7: hardware, Ollama and the model, against a fake Ollama (RF-72..74)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from launcher import hardware, ollama, steps
from launcher.model import Downloader, ModelState
from launcher.ui import UI, LauncherError
from tests.conftest import FakeOllama
from tests.test_steps import make_ctx

GB = 1024**3


@pytest.fixture
def ctx(tmp_path: Path, fake_ollama: FakeOllama, monkeypatch: pytest.MonkeyPatch) -> steps.Context:
    monkeypatch.setenv("TRADUCO_OLLAMA_HOST", fake_ollama.url)
    monkeypatch.delenv("TRADUCO_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TRADUCO_LLM_MODEL", raising=False)
    monkeypatch.setattr(
        hardware, "detect", lambda *a, **k: hardware.Hardware(16.0, "RTX test", 8.0, "nvidia")
    )
    c = make_ctx(tmp_path, workspace=tmp_path / "ws")
    c.ui.plan(9)
    return c


def test_running_ollama_with_the_model_needs_nothing(
    ctx: steps.Context, fake_ollama: FakeOllama
) -> None:
    fake_ollama.models = ["gemma4:e4b"]
    llm = steps.setup_llm(ctx, None, False)
    assert (llm.model, llm.pull, llm.server, llm.external) == ("gemma4:e4b", False, None, False)
    assert llm.base_url == f"{fake_ollama.url}/v1"


def test_a_missing_model_is_to_be_pulled_in_the_background(
    ctx: steps.Context, fake_ollama: FakeOllama
) -> None:
    llm = steps.setup_llm(ctx, None, False)
    assert llm.pull and llm.model == "gemma4:e4b" and llm.size_gb == 7


def test_model_is_chosen_for_the_hardware_and_can_be_forced(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch, fake_ollama: FakeOllama
) -> None:
    monkeypatch.setattr(hardware, "detect", lambda *a, **k: hardware.Hardware(8.0))
    assert steps.setup_llm(ctx, None, False).model == "gemma4:e2b"
    assert steps.setup_llm(ctx, "qwen3:8b", False).model == "qwen3:8b"  # --model wins


def test_the_model_saved_in_the_app_is_kept(
    ctx: steps.Context, tmp_path: Path, fake_ollama: FakeOllama
) -> None:
    saved = tmp_path / "ws" / ".traduco"
    saved.mkdir(parents=True)
    (saved / "settings.yaml").write_text("llm_model: gemma4:26b-a4b\n")
    assert steps.setup_llm(ctx, None, False).model == "gemma4:26b-a4b"


def test_a_server_the_user_configured_is_left_alone(
    ctx: steps.Context, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Other(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass

        def do_GET(self) -> None:
            body = b'{"data": []}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Other)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/v1"
        monkeypatch.setenv("TRADUCO_LLM_BASE_URL", url)
        monkeypatch.setenv("TRADUCO_LLM_MODEL", "mio-modello")
        llm = steps.setup_llm(ctx, None, False)
        assert llm.external and llm.base_url == url and llm.model == "mio-modello" and not llm.pull
    finally:
        httpd.shutdown()


def test_without_ollama_and_without_consent_the_app_still_starts(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRADUCO_OLLAMA_HOST", "http://127.0.0.1:9")  # nothing there
    monkeypatch.setattr(ollama, "find_binary", lambda: None)
    monkeypatch.setattr(ollama, "install_command", lambda: ["install-ollama"])
    installed: list[object] = []
    monkeypatch.setattr(ollama, "install", lambda cmd: installed.append(cmd))
    llm = steps.setup_llm(ctx, None, False)  # no terminal: the answer is "no"
    assert llm.note == "unavailable" and llm.server is None and not llm.pull
    assert installed == [] and ctx.state.get("ollama_declined") == "1"
    # the second start does not ask again
    asked: list[int] = []
    monkeypatch.setattr(UI, "confirm", lambda *a, **k: asked.append(1) or False)
    steps.setup_llm(ctx, None, False)
    assert asked == []


def test_with_consent_ollama_is_installed_then_started(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch, fake_ollama: FakeOllama
) -> None:
    calls: list[str] = []
    up = {"value": False}
    monkeypatch.setattr(ollama, "is_up", lambda host: up["value"])
    binary = Path("/fake/ollama")
    found: list[Path | None] = [None, binary]
    monkeypatch.setattr(ollama, "find_binary", lambda: found.pop(0) if len(found) > 1 else found[0])
    monkeypatch.setattr(ollama, "install_command", lambda: ["install-ollama"])
    monkeypatch.setattr(ollama, "install", lambda cmd: calls.append("install"))

    class Proc:
        def poll(self) -> None:
            return None

    def start(bin_: Path, host: str, log: object, models_dir: Path | None = None) -> Proc:
        calls.append(f"start:{bin_}")
        up["value"] = True
        return Proc()

    monkeypatch.setattr(ollama, "start_server", start)
    monkeypatch.setattr(ollama, "has_model", lambda host, tag: True)
    llm = steps.setup_llm(ctx, None, assume_yes=True)
    assert calls == ["install", "start:/fake/ollama"] and llm.server is not None


def test_offline_mode_never_installs_and_fails_if_the_model_is_missing(
    ctx: steps.Context, fake_ollama: FakeOllama
) -> None:
    ctx.offline = True
    with pytest.raises(LauncherError) as info:
        steps.setup_llm(ctx, None, False)
    assert info.value.code == "E012" and "gemma4:e4b" in str(info.value.params["name"])


def test_offline_without_ollama_starts_without_a_model(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRADUCO_OLLAMA_HOST", "http://127.0.0.1:9")
    monkeypatch.setattr(ollama, "find_binary", lambda: None)
    ctx.offline = True
    assert steps.setup_llm(ctx, None, True).note == "unavailable"


def test_not_enough_disk_for_the_model_is_reported_not_fatal(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        steps.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(10 * GB, 9 * GB, 1 * GB)
    )
    llm = steps.setup_llm(ctx, None, False)
    assert not llm.pull and llm.note == "no_space"
    state = json.loads(ctx.paths.model_state.read_text())
    assert state["state"] == "error" and "GB" in state["error"]


# --- the background download ---------------------------------------------------------------


def test_the_download_updates_the_state_file_until_ready(
    tmp_path: Path, fake_ollama: FakeOllama
) -> None:
    state = ModelState(tmp_path / "model.json")
    d = Downloader(fake_ollama.url, "gemma4:e4b", 7, state, UI("en"))
    d.start()
    d.join(10)
    data = json.loads((tmp_path / "model.json").read_text())
    assert data["state"] == "ready" and data["model"] == "gemma4:e4b"
    assert ollama.has_model(fake_ollama.url, "gemma4:e4b")


def test_a_failed_download_is_visible_to_the_interface(
    tmp_path: Path, fake_ollama: FakeOllama
) -> None:
    fake_ollama.pull_events = [{"error": "disk full"}]
    state = ModelState(tmp_path / "model.json")
    d = Downloader(fake_ollama.url, "gemma4:e4b", 7, state, UI("en"))
    d.start()
    d.join(10)
    data = json.loads((tmp_path / "model.json").read_text())
    assert data["state"] == "error" and "disk full" in data["error"]
    assert d.error is not None and d.error.code == "E042"
