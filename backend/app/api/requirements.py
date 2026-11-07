"""Requirement identifiers and cross-references (RF-84)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import Root
from app.core.trace import requirements

router = APIRouter(tags=["requirements"])


@router.get("/projects/{project_id}/requirements")
def list_requirements(root: Root) -> dict[str, Any]:
    return requirements.scan(root)
