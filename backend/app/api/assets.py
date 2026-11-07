import mimetypes
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from app.api.deps import Root
from app.core.workspace.assets import MAX_IMAGE_BYTES, save_image
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.ops import resolve_node
from app.core.workspace.tree import IMAGES_DIR
from app.schemas.projects import AssetSaved

router = APIRouter(tags=["assets"])
IMAGE_TYPES = {".png", ".jpg", ".gif", ".webp", ".svg"}


@router.post("/projects/{project_id}/assets", response_model=AssetSaved, status_code=201)
async def upload_asset(
    root: Root, request: Request, section: str = Query(...), filename: str = Query("")
) -> AssetSaved:
    """Raw image bytes in the body; stored in the ``img/`` folder next to the section."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
        raise WorkspaceError("too_large", "image too large")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_IMAGE_BYTES:
            raise WorkspaceError("too_large", "image too large")
    rel = save_image(root, section, filename, bytes(data))
    return AssetSaved(path=rel, markdown=f"{IMAGES_DIR}/{rel.rsplit('/', 1)[1]}")


@router.get("/projects/{project_id}/assets")
def get_asset(root: Root, path: str = Query(...)) -> FileResponse:
    """Serve an image from a chapter's ``img/`` folder (nothing else)."""
    file = resolve_node_for_image(root, path)
    media = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    return FileResponse(
        file,
        media_type=media,
        headers={
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


def resolve_node_for_image(root: Path, path: str) -> Path:
    parts = path.split("/")
    if len(parts) < 3 or parts[-2] != IMAGES_DIR:
        raise WorkspaceError("invalid_path", "not an image path")
    # ``img`` is excluded from node paths: resolve the chapter, then re-attach the file name
    chapter = resolve_node(root, "/".join(parts[:-2]))
    folder = (chapter / IMAGES_DIR).resolve()
    file = chapter / IMAGES_DIR / parts[-1]
    if (
        not file.is_file()
        or file.suffix.lower() not in IMAGE_TYPES
        or file.resolve().parent != folder
    ):
        raise WorkspaceError("not_found", f"image not found: {path}")
    return file
