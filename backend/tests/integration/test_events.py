import contextlib
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from app.api.events import origin_allowed
from app.config import Settings, get_settings
from app.core.workspace.fsio import sha256_bytes


def project_with_section(api: TestClient) -> tuple[str, Path, str]:
    pid = api.post("/api/projects", json={"nome": "Ev"}).json()["id"]
    ch = api.post(f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "A"}).json()[
        "path"
    ]
    sec = api.post(
        f"/api/projects/{pid}/nodes", json={"kind": "section", "title": "S", "parent": ch}
    ).json()["path"]
    settings: Settings = api.app.dependency_overrides[get_settings]()  # type: ignore[attr-defined]
    return pid, settings.workspaces_path / pid, sec


def receive_until(
    ws: WebSocketTestSession,
    predicate: Callable[[dict[str, Any]], bool],
    poke: Callable[[int], None],
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Call ``poke(i)`` every 0.5 s until an event matching ``predicate`` arrives.

    Repeating the change makes the test independent of the watcher start-up time: on WSL and
    network drives watchfiles falls back to polling, which can miss a write made during its
    first scan.
    """
    result: dict[str, Any] = {}

    def reader() -> None:
        with contextlib.suppress(Exception):
            while not result:
                msg = ws.receive_json()
                if predicate(msg):
                    result.update(msg)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    i = 0
    while not result and time.monotonic() < deadline:
        poke(i)
        i += 1
        thread.join(0.5)
    assert result, f"no matching event within {timeout}s"
    return result


def test_external_edit_is_pushed_with_its_hash(api: TestClient) -> None:
    pid, root, sec = project_with_section(api)
    contents: list[str] = []

    def poke(i: int) -> None:
        contents.append(f"modificato da un altro editor {i}\n")
        (root / sec).write_text(contents[-1], encoding="utf-8")

    with api.websocket_connect(f"/api/projects/{pid}/events") as ws:
        assert ws.receive_json() == {"type": "hello", "project": pid}
        event = receive_until(ws, lambda m: m.get("path") == sec, poke)
    assert event["type"] == "file.changed" and event["change"] in ("modified", "added")
    assert event["hash"] in {sha256_bytes(c.encode()) for c in contents}


def test_new_and_deleted_files_are_reported(api: TestClient) -> None:
    pid, root, sec = project_with_section(api)
    extra = root / "capitoli/01-a/09-extra.md"
    extra_rel = "capitoli/01-a/09-extra.md"

    def poke(i: int) -> None:
        if i % 2 == 0:
            extra.write_text("x", encoding="utf-8")
        else:
            extra.unlink(missing_ok=True)

    with api.websocket_connect(f"/api/projects/{pid}/events") as ws:
        ws.receive_json()
        event = receive_until(
            ws, lambda m: m.get("path") == extra_rel and m.get("change") == "deleted", poke
        )
    assert event["hash"] is None


def test_own_atomic_write_temp_files_are_not_reported(api: TestClient) -> None:
    pid, _, sec = project_with_section(api)
    seen: list[str] = []

    def poke(i: int) -> None:
        url = f"/api/projects/{pid}/files"
        h = api.get(url, params={"path": sec}).json()["hash"]
        api.put(url, params={"path": sec}, json={"content": f"v{i}\n"}, headers={"If-Match": h})

    def record(m: dict[str, Any]) -> bool:
        seen.append(m["path"])
        return bool(m["path"] == sec)

    with api.websocket_connect(f"/api/projects/{pid}/events") as ws:
        ws.receive_json()
        done = receive_until(ws, record, poke)
    assert done["path"] == sec and all(".tmp" not in p and "/." not in p for p in seen)


def test_unknown_project_is_rejected(api: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect), api.websocket_connect("/api/projects/nope/events"):
        pass


def test_cross_origin_connection_is_rejected(api: TestClient) -> None:
    pid, _, _ = project_with_section(api)
    with (
        pytest.raises(WebSocketDisconnect),
        api.websocket_connect(
            f"/api/projects/{pid}/events", headers={"Origin": "http://evil.example"}
        ),
    ):
        pass


def test_same_origin_connection_is_accepted(api: TestClient) -> None:
    pid, _, _ = project_with_section(api)
    with api.websocket_connect(
        f"/api/projects/{pid}/events", headers={"Origin": "http://testserver"}
    ) as ws:
        assert json.dumps(ws.receive_json())


def test_origin_rule() -> None:
    assert origin_allowed(None, "localhost:8000")
    assert origin_allowed("http://localhost:8000", "localhost:8000")
    assert not origin_allowed("http://localhost:9999", "localhost:8000")
    assert not origin_allowed("http://evil.example", "localhost:8000")
    assert not origin_allowed("http://localhost:8000", None)
