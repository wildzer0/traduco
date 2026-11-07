"""WebSocket ``/api/projects/{id}/events`` (docs/02-architettura.md)."""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.registry import project_root
from app.events import EventHub

router = APIRouter(tags=["events"])


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """Browsers do not apply the same-origin policy to WebSockets: check it ourselves.

    Requests without ``Origin`` come from non-browser clients and are allowed.
    """
    if origin is None:
        return True
    return urlparse(origin).netloc == (host or "")


@router.websocket("/projects/{project_id}/events")
async def project_events(websocket: WebSocket, project_id: str) -> None:
    if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host")):
        await websocket.close(code=1008)
        return
    settings = websocket.app.dependency_overrides.get(get_settings, get_settings)()
    try:
        root = project_root(settings.workspaces_path, project_id)
    except WorkspaceError:
        await websocket.close(code=1008)
        return
    hub: EventHub = websocket.app.state.hub
    await websocket.accept()
    queue = hub.subscribe(root)
    await websocket.send_json({"type": "hello", "project": project_id})
    receiver = asyncio.create_task(websocket.receive_text())
    try:
        while True:
            getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter, receiver}, return_when=asyncio.FIRST_COMPLETED)
            if receiver in done:  # client closed (or sent something: ignored)
                getter.cancel()
                receiver.result()
                receiver = asyncio.create_task(websocket.receive_text())
                continue
            await websocket.send_json(getter.result())
    except WebSocketDisconnect:
        pass
    finally:
        receiver.cancel()
        await hub.unsubscribe(root, queue)
