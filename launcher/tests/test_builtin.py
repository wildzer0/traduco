"""The built-in engine: llama.cpp's llama-server run by the launcher (ADR-041)."""

from __future__ import annotations

import hashlib
import io
import stat
import sys
import tarfile
import textwrap
import time
from pathlib import Path

import pytest

from launcher import builtin, hardware, ollama, steps
from launcher.manifest import Manifest, load_manifest
from launcher.model import ModelState
from launcher.paths import Paths, platform_key
from launcher.ui import UI, LauncherError
from tests.test_steps import REPO, make_ctx

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="the fake server is a script")

FAKE_SERVER = textwrap.dedent(
    """\
    #!{python}
    import sys, time
    from http.server import BaseHTTPRequestHandler, HTTPServer
    args = sys.argv
    port = int(args[args.index("--port") + 1])
    started = time.monotonic()
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            ready = time.monotonic() - started > 0.5   # 503 while "loading", like the real one
            self.send_response(200 if ready else 503)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
    """
)


def archive_with_server() -> bytes:
    buffer = io.BytesIO()
    script = FAKE_SERVER.format(python=sys.executable).encode()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo("llama-test/" + builtin.SERVER)
        info.size = len(script)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(script))
    return buffer.getvalue()


def manifest_for(url: str, archive: bytes, weights: bytes) -> Manifest:
    real = load_manifest(REPO / "launcher" / "manifest.toml")
    data = dict(real.data)
    data["llamacpp"] = {
        "version": "test1",
        "platforms": {platform_key(): {"url": url, "sha256": hashlib.sha256(archive).hexdigest()}},
    }
    data["builtin"] = {
        "models": {
            kind: {
                "name": f"tiny-{kind}",
                "url": "http://127.0.0.1:9/never",
                "sha256": hashlib.sha256(weights).hexdigest(),
                "size_gb": 1,
            }
            for kind in ("small", "default")
        }
    }
    return Manifest(data)


def test_the_real_manifest_pins_the_engine_and_both_models() -> None:
    m = load_manifest(REPO / "launcher" / "manifest.toml")
    for platform in ("linux-x64", "linux-arm64", "darwin-x64", "darwin-arm64", "windows-x64"):
        art = m.artifact("llamacpp", platform)
        assert art.url.startswith("https://github.com/ggml-org/llama.cpp/releases/download/")
        assert len(art.sha256) == 64
    small, default = m.builtin_model("small"), m.builtin_model("default")
    assert small.file.endswith("Q4_0.gguf") and small.url.startswith("https://huggingface.co/")
    assert len(small.sha256) == len(default.sha256) == 64 and small.size_gb < default.size_gb


def test_cpu_gets_the_small_model_and_a_mac_the_default_one() -> None:
    m = load_manifest(REPO / "launcher" / "manifest.toml")
    cpu, why = builtin.choose_model(hardware.Hardware(32.0), m)
    assert (cpu.kind, why) == ("small", "builtin_cpu")
    gpu, _ = builtin.choose_model(hardware.Hardware(32.0, "RTX", 12.0, "nvidia"), m)
    assert gpu.kind == "small"  # the CPU build is used: size the model for the CPU
    mac, why = builtin.choose_model(hardware.Hardware(16.0, "Apple Silicon", 10.4, "apple"), m)
    assert (mac.kind, why) == ("default", "builtin_metal")
    small_mac, _ = builtin.choose_model(hardware.Hardware(8.0, "Apple Silicon", 5.2, "apple"), m)
    assert small_mac.kind == "small"


def test_the_preferred_port_is_used_when_free_and_replaced_when_busy() -> None:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        busy = sock.getsockname()[1]
        other = builtin.free_port(busy)
        assert other != busy and other > 0
    assert builtin.free_port(busy) == busy


@POSIX
def test_the_program_is_downloaded_once_and_checked(server, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    url, behaviour = server
    archive = archive_with_server()
    behaviour.payload = archive
    manifest = manifest_for(url, archive, b"weights")
    paths = Paths(tmp_path)
    paths.ensure()
    first = builtin.ensure_binary(paths, manifest, offline=False)
    assert first.name == builtin.SERVER and first.stat().st_mode & stat.S_IXUSR
    again = builtin.ensure_binary(paths, manifest, offline=False)
    assert again == first and len(behaviour.requests) == 1
    # a new version is fetched again, and what arrives is checked against the pinned hash
    behaviour.payload = b"tampered"
    newer = {
        "version": "t2",
        "platforms": {
            platform_key(): {"url": url + "?v=2", "sha256": hashlib.sha256(b"x").hexdigest()}
        },
    }
    with pytest.raises(LauncherError) as err:
        builtin.ensure_binary(paths, Manifest({**manifest.data, "llamacpp": newer}), offline=False)
    assert err.value.code == "E011"


def test_offline_without_the_program_is_a_clear_error(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    paths.ensure()
    manifest = manifest_for("http://127.0.0.1:9/x", b"a", b"w")
    with pytest.raises(LauncherError) as err:
        builtin.ensure_binary(paths, manifest, offline=True)
    assert err.value.code == "E012"


@POSIX
def test_the_engine_prepares_starts_and_stops_the_server(server, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    url, behaviour = server
    archive, weights = archive_with_server(), b"fake gguf"
    behaviour.payload = archive
    manifest = manifest_for(url, archive, weights)
    paths = Paths(tmp_path)
    paths.ensure()
    model = manifest.builtin_model("small")
    builtin.model_file(paths, model).parent.mkdir(parents=True, exist_ok=True)
    builtin.model_file(paths, model).write_bytes(weights)  # already downloaded
    plan = builtin.Plan(model, builtin.free_port())
    state = ModelState(paths.model_state)
    engine = builtin.Engine(paths, manifest, plan, state, UI("en"))
    engine.start()
    assert state.path.read_text().count('"downloading"') == 1
    engine.join(30)
    assert engine.error is None and '"ready"' in state.path.read_text()
    assert builtin.is_ready(plan)
    engine.stop()
    deadline = time.monotonic() + 5
    while builtin.is_ready(plan) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not builtin.is_ready(plan)


@POSIX
def test_a_server_that_dies_is_reported_with_its_log(tmp_path: Path) -> None:
    script = tmp_path / builtin.SERVER
    script.write_text(f"#!{sys.executable}\nimport sys\nsys.exit(3)\n")
    script.chmod(0o755)
    plan = builtin.Plan(
        load_manifest(REPO / "launcher" / "manifest.toml").builtin_model("small"), 1
    )
    log = (tmp_path / "log").open("ab")
    proc = builtin.start_server(script, tmp_path / "w.gguf", plan, log)
    with pytest.raises(LauncherError) as err:
        builtin.wait_until_ready(plan, proc, timeout=5)
    assert err.value.code == "E050"


# --- the choice inside the launcher's model step -------------------------------------------


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> steps.Context:
    monkeypatch.setenv("TRADUCO_OLLAMA_HOST", "http://127.0.0.1:9")  # no Ollama
    monkeypatch.delenv("TRADUCO_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TRADUCO_LLM_MODEL", raising=False)
    monkeypatch.setattr(ollama, "find_binary", lambda: None)
    monkeypatch.setattr(ollama, "install_command", lambda: None)
    monkeypatch.setattr(hardware, "detect", lambda *a, **k: hardware.Hardware(16.0))
    c = make_ctx(tmp_path, workspace=tmp_path / "ws")
    c.ui.plan(9)
    return c


def test_asking_for_the_builtin_engine_skips_ollama(ctx: steps.Context) -> None:
    llm = steps.setup_llm(ctx, None, False, "builtin")
    assert llm.builtin is not None and llm.model == "gemma-4-E2B-it-Q4_0"
    assert llm.base_url == llm.builtin.openai_url and not llm.external and not llm.pull


def test_without_ollama_the_builtin_engine_is_offered_and_needs_consent(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    monkeypatch.setattr(UI, "confirm", lambda self, key, *a, **k: asked.append(key) or True)
    llm = steps.setup_llm(ctx, None, False)
    assert "builtin.ask" in asked and llm.builtin is not None
    # a "no" is remembered and Traduco still starts
    ctx2 = ctx
    ctx2.state.set("builtin_declined", "0")
    monkeypatch.setattr(UI, "confirm", lambda self, key, *a, **k: key != "builtin.ask")
    again = steps.setup_llm(ctx2, None, False)
    assert again.builtin is None and again.note == "unavailable"
    assert ctx2.state.get("builtin_declined") == "1"


def test_choosing_ollama_never_falls_back_to_the_builtin_engine(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(UI, "confirm", lambda *a, **k: False)
    llm = steps.setup_llm(ctx, None, False, "ollama")
    assert llm.builtin is None and llm.note == "unavailable"


def test_everything_already_on_disk_needs_no_download(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(builtin, "installed", lambda *a: True)
    llm = steps.setup_llm(ctx, None, False, "builtin")
    assert llm.builtin is not None and llm.note == ""


def test_not_enough_room_is_reported_not_fatal(
    ctx: steps.Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    monkeypatch.setattr(
        steps.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(10, 10, 10 * 1024**2)
    )
    llm = steps.setup_llm(ctx, None, False, "builtin")
    assert llm.note == "no_space" and llm.builtin is None
    assert '"error"' in ctx.paths.model_state.read_text()


def test_offline_without_the_files_stops_with_a_clear_message(ctx: steps.Context) -> None:
    ctx.offline = True
    with pytest.raises(LauncherError) as err:
        steps.setup_llm(ctx, None, False, "builtin")
    assert err.value.code == "E012"
