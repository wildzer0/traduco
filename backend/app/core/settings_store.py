"""User settings kept next to the projects (``<workspaces>/.traduco/settings.yaml``).

Environment variables (``TRADUCO_LLM_*``) give the defaults; what the user saves here wins.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_text

KEYS = ("llm_base_url", "llm_model", "llm_api_key")


def _path(workspaces: Path) -> Path:
    return workspaces / ".traduco" / "settings.yaml"


def load(workspaces: Path) -> dict[str, str]:
    path = _path(workspaces)
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (YAMLError, OSError, UnicodeDecodeError):
        return {}  # a damaged settings file falls back to the defaults
    if not isinstance(data, dict):
        return {}
    return {k: str(data[k]) for k in KEYS if isinstance(data.get(k), str)}


def validate_url(url: str) -> str:
    url = url.strip().rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise WorkspaceError("invalid_path", "the address must start with http:// or https://")
    return url


def save(workspaces: Path, values: dict[str, Any]) -> None:
    current: dict[str, Any] = dict(load(workspaces))
    current.update({k: v for k, v in values.items() if k in KEYS and v is not None})
    out = io.StringIO()
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.dump(current, out)
    path = _path(workspaces)
    atomic_write_text(path, out.getvalue())
    path.chmod(0o600)  # may hold an API key
