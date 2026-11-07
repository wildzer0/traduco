from fastapi import APIRouter, Header, Query, Response
from fastapi.responses import JSONResponse

from app.api.deps import Root
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.sections import ConflictError, read_section, write_section
from app.schemas.projects import FileContent, FilePut, FileSaved

router = APIRouter(tags=["files"])


@router.get("/projects/{project_id}/files", response_model=FileContent)
def get_file(root: Root, response: Response, path: str = Query(...)) -> FileContent:
    content, digest = read_section(root, path)
    response.headers["ETag"] = f'"{digest}"'
    return FileContent(path=path, content=content, hash=digest)


@router.put("/projects/{project_id}/files", response_model=FileSaved)
def put_file(
    root: Root,
    body: FilePut,
    response: Response,
    path: str = Query(...),
    if_match: str | None = Header(default=None),
) -> FileSaved | JSONResponse:
    if not if_match:
        raise WorkspaceError(
            "precondition_required", "If-Match header with the file hash is required"
        )
    expected = if_match.strip().removeprefix("W/").strip('"')
    try:
        digest = write_section(root, path, body.content, expected)
    except ConflictError as exc:
        return JSONResponse(
            {"error": {"code": "conflict", "message": str(exc),
                       "details": {"current_hash": exc.current_hash}}},
            status_code=409,
        )  # fmt: skip
    response.headers["ETag"] = f'"{digest}"'
    return FileSaved(path=path, hash=digest)
