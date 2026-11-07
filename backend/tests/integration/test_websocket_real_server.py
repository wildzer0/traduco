"""uvicorn only serves WebSockets when a WebSocket library is installed; TestClient hides that.

This test runs a real server so a missing dependency fails here instead of in the user's browser.
"""

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from websockets.sync.client import connect
from websockets.typing import Origin

from app.config import Settings
from app.core.workspace.manifest import create_project
from app.main import create_app


@pytest.fixture
def server(tmp_path: Path) -> Iterator[int]:
    create_project(tmp_path / "ws" / "demo", "Demo", "it", "en")
    app = create_app(Settings(workspaces_dir=tmp_path / "ws", frontend_dist=None))
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not srv.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert srv.started, "server did not start"
    port = srv.servers[0].sockets[0].getsockname()[1]
    yield port
    srv.should_exit = True
    thread.join(timeout=10)


def test_real_server_accepts_the_events_websocket(server: int) -> None:
    with connect(f"ws://127.0.0.1:{server}/api/projects/demo/events", open_timeout=5) as ws:
        assert json.loads(ws.recv(timeout=5)) == {"type": "hello", "project": "demo"}


def test_real_server_rejects_cross_origin_websocket(server: int) -> None:
    from websockets.exceptions import ConnectionClosed, InvalidStatus

    with (
        pytest.raises((ConnectionClosed, InvalidStatus)),
        connect(
            f"ws://127.0.0.1:{server}/api/projects/demo/events",
            origin=Origin("http://evil.example"),
            open_timeout=5,
        ) as ws,
    ):
        ws.recv(timeout=5)
