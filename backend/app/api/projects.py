from fastapi import APIRouter, Depends

from app.api.deps import Root
from app.config import Settings, get_settings
from app.core.workspace import manifest, registry
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.tree import Node, build_tree
from app.schemas.projects import (
    ProjectCreate,
    ProjectPatch,
    ProjectSummary,
    TreeNode,
    TreeResponse,
)

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(settings: Settings = Depends(get_settings)) -> list[ProjectSummary]:
    return [ProjectSummary(**vars(p)) for p in registry.list_projects(settings.workspaces_path)]


@router.post("/projects", response_model=ProjectSummary, status_code=201)
def create_project(
    body: ProjectCreate, settings: Settings = Depends(get_settings)
) -> ProjectSummary:
    example = None
    if body.esempio:
        example = settings.example_project
        if example is None:
            raise WorkspaceError("not_found", "the example project is not available")
    project_id = registry.create_in_workspaces(
        settings.workspaces_path, body.nome, body.lingua_sorgente, body.lingua_ufficiale, example
    )
    project = manifest.load_project(settings.workspaces_path / project_id)
    return ProjectSummary(
        id=project_id,
        nome=project.nome,
        lingua_sorgente=project.lingua_sorgente,
        lingua_ufficiale=project.lingua_ufficiale,
    )


@router.get("/projects/{project_id}")
def get_project(root: Root) -> dict[str, object]:
    return manifest.load_project(root).model_dump(mode="json", exclude_none=True)


@router.patch("/projects/{project_id}")
def patch_project(root: Root, body: ProjectPatch) -> dict[str, object]:
    current = manifest.load_project(root).model_dump(mode="python", exclude_none=True)
    current.update(body.model_dump(mode="python"))
    manifest.save_project(root, manifest.Project.model_validate(current))
    return manifest.load_project(root).model_dump(mode="json", exclude_none=True)


def _to_schema(node: Node) -> TreeNode:
    return TreeNode(
        kind=node.kind,
        path=node.path,
        name=node.name,
        title=node.title,
        children=[_to_schema(c) for c in node.children],
    )


@router.get("/projects/{project_id}/tree", response_model=TreeResponse)
def get_tree(root: Root) -> TreeResponse:
    return TreeResponse(nodes=[_to_schema(n) for n in build_tree(root)])
