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


# --- M3: control of the translation ----------------------------------------------------------


def settled(c: TestClient, pid: str, sec: str) -> dict:  # type: ignore[type-arg]
    wait_for(lambda: view(c, pid, sec)["pending"] == 0)
    return view(c, pid, sec)


def seg(v: dict, key: str) -> dict:  # type: ignore[type-arg]
    return next(s for s in v["segments"] if s["key"] == key)  # type: ignore[no-any-return]


def put_segment(c: TestClient, pid: str, sec: str, key: str, body: dict) -> dict:  # type: ignore[type-arg]
    r = c.put(f"/api/projects/{pid}/segments/{key}", params={"path": sec}, json=body)
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def test_glossary_violation_ends_in_review_with_the_reason(
    tapi: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_LLM_MODE", "glossary-violation")  # the fake model appends "offer"
    pid, sec, _ = setup_section(tapi, "Invia l'offerta.\n")
    r = tapi.put(
        f"/api/projects/{pid}/glossary",
        json=[
            {
                "sorgente": "offerta",
                "destinazione": {"en": "proposal"},
                "vietati": {"en": ["offer"]},
            }
        ],
    )
    assert r.status_code == 200
    r = tapi.post(f"/api/projects/{pid}/retranslate", json={"scope": "project"})
    v = settled(tapi, pid, sec)
    row = seg(v, "p:0")
    assert row["status"] == "needs_review" and row["reason"].startswith("glossary:")
    assert "offer" in row["target"]  # the best effort stays visible for the author


def test_glossary_api_validates_and_roundtrips(tapi: TestClient) -> None:
    pid = tapi.post("/api/projects", json={"nome": "G"}).json()["id"]
    entries = [{"sorgente": "collaudo", "destinazione": {"en": "acceptance test"}}]
    assert tapi.put(f"/api/projects/{pid}/glossary", json=entries).status_code == 200
    got = tapi.get(f"/api/projects/{pid}/glossary").json()
    assert got[0]["sorgente"] == "collaudo" and got[0]["destinazione"] == {"en": "acceptance test"}
    dup = [*entries, {"sorgente": "Collaudo"}]
    assert tapi.put(f"/api/projects/{pid}/glossary", json=dup).status_code == 409
    assert tapi.put(f"/api/projects/{pid}/glossary", json=[{"sorgente": " "}]).status_code == 422


def test_manual_edit_lock_proposal_flow(tapi: TestClient) -> None:
    pid, sec, h = setup_section(tapi, "Uno.\n")
    settled(tapi, pid, sec)
    row = put_segment(tapi, pid, sec, "p:0", {"target": "My own text."})
    assert (row["status"], row["locked"], row["target"]) == ("translated", True, "My own text.")
    # the source changes: the author's text is kept, the model's text becomes a proposal
    tapi.put(
        f"/api/projects/{pid}/files",
        params={"path": sec},
        headers={"If-Match": h},
        json={"content": "Uno cambiato.\n"},
    )
    wait_for(lambda: seg(view(tapi, pid, sec), "p:0")["pending_target"] is not None)
    row = seg(view(tapi, pid, sec), "p:0")
    assert row["target"] == "My own text." and row["pending_target"] == "[EN] Uno cambiato."
    assert row["status"] == "needs_review"
    row = put_segment(tapi, pid, sec, "p:0", {"action": "accept"})
    assert row["target"] == "[EN] Uno cambiato." and row["pending_target"] is None


def test_manual_correction_survives_project_retranslation(tapi: TestClient) -> None:
    pid, sec, _ = setup_section(tapi, "Uno.\n\nDue.\n")
    settled(tapi, pid, sec)
    put_segment(tapi, pid, sec, "p:0", {"target": "Hand made."})
    assert (
        tapi.post(f"/api/projects/{pid}/retranslate", json={"scope": "project"}).json()["queued"]
        == 1
    )
    v = settled(tapi, pid, sec)
    assert seg(v, "p:0")["target"] == "Hand made."
    assert v["markdown"].startswith("Hand made.")


def test_segment_put_needs_exactly_one_change(tapi: TestClient) -> None:
    pid, sec, _ = setup_section(tapi, "Uno.\n")
    settled(tapi, pid, sec)
    r = tapi.put(f"/api/projects/{pid}/segments/p:0", params={"path": sec}, json={})
    assert r.status_code == 400
    r = tapi.put(f"/api/projects/{pid}/segments/p:9", params={"path": sec}, json={"locked": True})
    assert r.status_code == 404


def test_approve_and_review_listing(tapi: TestClient) -> None:
    pid, sec, _ = setup_section(tapi, "Uno.\n\nDue.\n")
    settled(tapi, pid, sec)
    put_segment(tapi, pid, sec, "p:0", {"action": "approve"})
    data = tapi.get(f"/api/projects/{pid}/review").json()
    assert data["counts"] == {"translated": 2, "approved": 1} or data["counts"]["approved"] == 1
    paths = {r["path"] for r in data["segments"]}
    assert paths == {sec}
    assert data["segments"][0]["section"]


def test_instruction_proposes_without_saving_and_alternatives(tapi: TestClient) -> None:
    pid, sec, _ = setup_section(tapi, "Uno.\n")
    settled(tapi, pid, sec)
    r = tapi.post(
        f"/api/projects/{pid}/segments/p:0/instruct",
        params={"path": sec},
        json={"instruction": "more concise"},
    )
    assert r.status_code == 200 and len(r.json()["proposals"]) == 1
    assert seg(view(tapi, pid, sec), "p:0")["target"] == "[EN] Uno."
    r = tapi.post(
        f"/api/projects/{pid}/segments/p:0/instruct",
        params={"path": sec},
        json={"instruction": "variants", "alternatives": True},
    )
    assert r.status_code == 200 and r.json()["proposals"]


def test_apply_source_updates_the_file(tapi: TestClient, tmp_path: Path) -> None:
    pid, sec, _ = setup_section(tapi, "Uno.\n")
    settled(tapi, pid, sec)
    put_segment(tapi, pid, sec, "p:0", {"target": "One, my way."})
    r = tapi.post(
        f"/api/projects/{pid}/segments/p:0/apply-source",
        params={"path": sec},
        json={"text": "Uno, a modo mio."},
    )
    assert r.status_code == 200
    assert (tmp_path / "ws" / pid / sec).read_text().endswith("Uno, a modo mio.\n")
    v = view(tapi, pid, sec)
    assert seg(v, "p:0")["target"] == "One, my way." and seg(v, "p:0")["status"] == "translated"


def test_section_tone_and_note_are_saved_in_the_front_matter(tapi: TestClient) -> None:
    pid, sec, _ = setup_section(tapi, "Uno.\n")
    settled(tapi, pid, sec)
    r = tapi.patch(
        f"/api/projects/{pid}/sections/meta",
        params={"path": sec},
        json={"tono": "informale", "contesto": "Pubblico di tecnici"},
    )
    assert r.status_code == 200
    v = view(tapi, pid, sec)
    assert v["tone"] == "informale" and v["note"] == "Pubblico di tecnici"
    assert v["project_tone"] == "formale"
    tapi.patch(f"/api/projects/{pid}/sections/meta", params={"path": sec}, json={})
    assert view(tapi, pid, sec)["tone"] is None
