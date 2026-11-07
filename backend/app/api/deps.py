"""Shared dependencies and the mapping from workspace errors to HTTP errors."""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings
from app.core.workspace.registry import project_root

STATUS = {
    "invalid_path": 400,
    "invalid_name": 400,
    "not_found": 404,
    "exists": 409,
    "depth_exceeded": 422,
    "invalid_move": 422,
    "invalid_order": 422,
    "invalid_image": 415,
    "too_large": 413,
    "unreadable": 422,
    "precondition_required": 428,
    "invalid_state": 409,
    "invalid_template": 422,
    "model_refused": 502,
    "off_topic": 422,
}

_locks: defaultdict[str, threading.RLock] = defaultdict(threading.RLock)


@contextmanager
def structure_lock(root: Path) -> Iterator[None]:
    """Serialise structure changes (renumbering) per project."""
    with _locks[str(root)]:
        yield


def get_root(project_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> Path:
    return project_root(settings.workspaces_path, project_id)


Root = Annotated[Path, Depends(get_root)]
