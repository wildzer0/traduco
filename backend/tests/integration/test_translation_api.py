"""End to end against the fake OpenAI-compatible server (tools/fake-llm)."""

import socket
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "fake-llm"))
from fake_llm.server import make_server  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class FakeLlm:
    def __init__(self, port: int) -> None:
        self.port = port
        self.server: Any = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.server = make_server("127.0.0.1", self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None


@pytest.fixture
def llm() -> Iterator[FakeLlm]:
    fake = FakeLlm(free_port())
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture
def tapi(tmp_path: Path, llm: FakeLlm) -> Iterator[TestClient]:
    settings = Settings(
        workspaces_dir=tmp_path / "ws",
        frontend_dist=None,
        llm_base_url=f"http://127.0.0.1:{llm.port}/v1",
        llm_model="fake-model",
    )
    from app.main import create_app

    with TestClient(create_app(settings)) as c:
        yield c


def setup_section(c: TestClient, text: str) -> tuple[str, str, str]:
    pid = c.post("/api/projects", json={"nome": "T"}).json()["id"]
    ch = c.post(f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "Uno"}).json()
    sec = c.post(
        f"/api/projects/{pid}/nodes",
        json={"kind": "section", "title": "Due", "parent": ch["path"]},
    ).json()["path"]
    got = c.get(f"/api/projects/{pid}/files", params={"path": sec}).json()
    r = c.put(
        f"/api/projects/{pid}/files",
        params={"path": sec},
        headers={"If-Match": got["hash"]},
        json={"content": text},
    )
    assert r.status_code == 200, r.text
    return pid, sec, r.json()["hash"]


def wait_for(cond: Callable[[], bool], timeout: float = 5.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.05)
    raise AssertionError("condition not reached in time")


def view(c: TestClient, pid: str, sec: str) -> dict:  # type: ignore[type-arg]
    return c.get(f"/api/projects/{pid}/translation", params={"path": sec}).json()  # type: ignore[no-any-return]


def test_saving_a_section_translates_it(tapi: TestClient) -> None:
    pid, sec, _ = setup_section(tapi, "# Titolo\n\nPremi `Invio` per **continuare**.\n")
    wait_for(lambda: view(tapi, pid, sec)["pending"] == 0)
    v = view(tapi, pid, sec)
    assert v["markdown"] == "# [EN] Titolo\n\n[EN] Premi `Invio` per **continuare**.\n"
    assert {s["status"] for s in v["segments"]} == {"translated"}


def test_editing_retranslates_only_the_changed_paragraph(tapi: TestClient, tmp_path: Path) -> None:
    pid, sec, h = setup_section(tapi, "Uno.\n\nDue.\n")
    wait_for(lambda: view(tapi, pid, sec)["pending"] == 0)
    seg_file = next((tmp_path / "ws").rglob("*.json"))
    before = seg_file.read_text()
    tapi.put(
        f"/api/projects/{pid}/files",
        params={"path": sec},
        headers={"If-Match": h},
        json={"content": "Uno.\n\nDue modificato.\n"},
    )
    wait_for(lambda: "[EN] Due modificato." in view(tapi, pid, sec)["markdown"])
    v = view(tapi, pid, sec)
    assert v["markdown"] == "[EN] Uno.\n\n[EN] Due modificato.\n"
    assert seg_file.read_text() != before


def test_editor_keeps_working_while_the_model_is_off(tapi: TestClient, llm: FakeLlm) -> None:
    llm.stop()
    pid, sec, h = setup_section(tapi, "Ciao mondo.\n")
    r = tapi.put(
        f"/api/projects/{pid}/files",
        params={"path": sec},
        headers={"If-Match": h},
        json={"content": "Ciao a tutti.\n"},
    )
    assert r.status_code == 200  # saving is not blocked
    v = view(tapi, pid, sec)
    assert v["segments"][0]["status"] == "queued"
    assert tapi.get("/api/llm/status").json()["online"] is False
    llm.start()
    wait_for(lambda: view(tapi, pid, sec)["pending"] == 0, timeout=15)
    assert view(tapi, pid, sec)["markdown"] == "[EN] Ciao a tutti.\n"


def test_llm_status_online(tapi: TestClient) -> None:
    body = tapi.get("/api/llm/status").json()
    assert body["online"] is True and "fake-model" in body["models"]


def test_retranslate_project_queues_unlocked_segments(tapi: TestClient) -> None:
    pid, sec, _ = setup_section(tapi, "Uno.\n\nDue.\n")
    wait_for(lambda: view(tapi, pid, sec)["pending"] == 0)
    r = tapi.post(f"/api/projects/{pid}/retranslate", json={"scope": "project"})
    assert r.status_code == 200 and r.json() == {"sections": 1, "queued": 2}
    wait_for(lambda: view(tapi, pid, sec)["pending"] == 0)


def test_translation_of_unknown_language_is_404(tapi: TestClient) -> None:
    pid, sec, _ = setup_section(tapi, "Uno.\n")
    r = tapi.get(f"/api/projects/{pid}/translation", params={"path": sec, "lang": "de"})
    assert r.status_code == 404
