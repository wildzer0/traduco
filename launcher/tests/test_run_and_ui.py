from __future__ import annotations

import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from launcher.run import stop, wait_for_health
from launcher.ui import MESSAGES, UI, LauncherError, detect_language


class Health(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        pass

    def do_GET(self) -> None:
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_wait_for_health_succeeds_and_ignores_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")  # would break a proxied request
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Health)
    Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        wait_for_health(f"http://127.0.0.1:{httpd.server_address[1]}", None, timeout=5)
    finally:
        httpd.shutdown()


def test_wait_for_health_times_out() -> None:
    with pytest.raises(LauncherError) as e:
        wait_for_health("http://127.0.0.1:9", None, timeout=0.5, interval=0.1)
    assert e.value.code == "E031"


def test_wait_for_health_detects_crashed_backend() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "raise SystemExit(3)"])
    proc.wait()
    with pytest.raises(LauncherError) as e:
        wait_for_health("http://127.0.0.1:9", proc, timeout=5)
    assert e.value.code == "E030"


def test_stop_terminates_a_running_process() -> None:
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    stop(proc, grace=5)
    assert proc.poll() is not None


def test_every_error_code_has_both_languages_and_a_solution() -> None:
    codes = {k for k in MESSAGES if k.startswith("E") and not k.endswith(".fix")}
    assert codes
    for code in codes:
        for lang in ("it", "en"):
            assert MESSAGES[code][lang] and MESSAGES[f"{code}.fix"][lang], (code, lang)


def test_messages_are_complete_in_both_languages() -> None:
    for key, text in MESSAGES.items():
        assert set(text) == {"it", "en"}, key


def test_language_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("TRADUCO_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "it_IT.UTF-8")
    assert detect_language() == "it"
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert detect_language() == "en"
    monkeypatch.setenv("TRADUCO_LANG", "it")
    assert detect_language() == "it"


def test_ui_renders_error_with_code_and_solution(capsys: pytest.CaptureFixture[str]) -> None:
    UI("en").error(LauncherError("E002", need="2", have="0.5"), ".runtime/logs/launcher.log")
    out = capsys.readouterr().out
    assert "[E002]" in out and "Free up space" in out and "launcher.log" in out
