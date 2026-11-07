from fastapi import APIRouter, Query

from app.api.deps import Root, structure_lock
from app.core.workspace import ops
from app.core.workspace.errors import WorkspaceError
from app.schemas.projects import DeleteResult, NodeCreate, NodePatch, NodeResult

router = APIRouter(tags=["nodes"])


@router.post("/projects/{project_id}/nodes", response_model=NodeResult, status_code=201)
def create_node(root: Root, body: NodeCreate) -> NodeResult:
    with structure_lock(root):
        if body.kind == "chapter":
            return NodeResult(path=ops.create_chapter(root, body.title, body.parent))
        return NodeResult(path=ops.create_section(root, body.parent, body.title))


@router.patch("/projects/{project_id}/nodes", response_model=NodeResult)
def patch_node(root: Root, body: NodePatch) -> NodeResult:
    with structure_lock(root):
        if body.order is not None:
            return NodeResult(renamed=ops.reorder(root, body.parent, body.order))
        if body.path is None:
            raise WorkspaceError("invalid_path", "path is required")
        if body.move:
            moved = ops.move(root, body.path, body.parent, body.index)
            return NodeResult(path=moved.path, renamed=moved.renamed)
        if body.title is not None:
            renamed = ops.rename(root, body.path, body.title)
            return NodeResult(path=renamed.get(body.path, body.path), renamed=renamed)
        raise WorkspaceError("invalid_path", "nothing to do: send title, move or order")


@router.delete("/projects/{project_id}/nodes", response_model=DeleteResult)
def delete_node(root: Root, path: str = Query(...)) -> DeleteResult:
    with structure_lock(root):
        return DeleteResult(trash=ops.delete(root, path))
