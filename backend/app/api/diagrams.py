from typing import Literal

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import Root
from app.core.workspace.diagrams import decode_png, read_diagram, save_diagram

router = APIRouter(tags=["diagrams"])


class DiagramUpload(BaseModel):
    svg: str
    png_base64: str


@router.put("/projects/{project_id}/diagrams/{digest}", status_code=204)
def put_diagram(root: Root, digest: str, body: DiagramUpload) -> None:
    save_diagram(root, digest, body.svg, decode_png(body.png_base64))


@router.get("/projects/{project_id}/diagrams/{digest}.{fmt}")
def get_diagram(root: Root, digest: str, fmt: Literal["svg", "png"]) -> FileResponse:
    return FileResponse(
        read_diagram(root, digest, fmt),
        headers={
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )
