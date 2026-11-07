"""Skeletons shipped with the application (``examples/scheletri/*.yaml``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml.error import YAMLError

from app.core.skeleton.model import SkeletonError, parse_skeleton
from app.core.workspace.errors import WorkspaceError

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class BundledSkeleton:
    id: str
    nome: str


def list_bundled(directory: Path) -> list[BundledSkeleton]:
    found: list[BundledSkeleton] = []
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.yaml")):
        try:
            found.append(BundledSkeleton(path.stem, parse_skeleton(path.read_text("utf-8")).nome))
        except (SkeletonError, YAMLError, OSError, UnicodeDecodeError):
            continue  # a broken bundled file must not hide the others
    return found


def bundled_skeleton(directory: Path, skeleton_id: str) -> str:
    """Text of a bundled skeleton; the id can never address anything outside ``directory``."""
    if not _ID.match(skeleton_id):
        raise WorkspaceError("invalid_path", f"invalid skeleton id: {skeleton_id!r}")
    path = directory / f"{skeleton_id}.yaml"
    if not path.is_file():
        raise WorkspaceError("not_found", f"skeleton not found: {skeleton_id}")
    return path.read_text(encoding="utf-8")
