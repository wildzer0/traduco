"""Review comments on segments (RF-83)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import Root
from app.core.emissions import comments

router = APIRouter(tags=["comments"])


class NewThread(BaseModel):
    path: str
    key: str
    author: str = Field(default="", max_length=80)
    text: str = Field(max_length=4000)


class Reply(BaseModel):
    path: str
    author: str = Field(default="", max_length=80)
    text: str = Field(max_length=4000)


class Status(BaseModel):
    path: str
    status: Literal["open", "resolved"]


@router.get("/projects/{project_id}/comments")
def list_threads(root: Root, path: str) -> dict[str, Any]:
    return {"threads": comments.threads(root, path), "counts": comments.counts(root, path)}


@router.post("/projects/{project_id}/comments", status_code=201)
def add_thread(root: Root, body: NewThread) -> dict[str, Any]:
    return comments.add_thread(root, body.path, body.key, body.author or "?", body.text)


@router.post("/projects/{project_id}/comments/{thread_id}/reply")
def reply(root: Root, thread_id: str, body: Reply) -> dict[str, Any]:
    return comments.reply(root, body.path, thread_id, body.author or "?", body.text)


@router.patch("/projects/{project_id}/comments/{thread_id}")
def set_status(root: Root, thread_id: str, body: Status) -> dict[str, Any]:
    return comments.set_status(root, body.path, thread_id, body.status)


@router.delete("/projects/{project_id}/comments/{thread_id}", status_code=204)
def remove(root: Root, thread_id: str, path: str) -> None:
    comments.remove(root, path, thread_id)
