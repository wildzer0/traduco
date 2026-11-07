"""Issues, comparison and the change table (RF-80…82)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import Root
from app.core.emissions import changes as changes_mod
from app.core.emissions import compare as compare_mod
from app.core.emissions import store
from app.core.translation.service import TranslationService
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project, save_project

router = APIRouter(tags=["issues"])
DRAFT = "bozza"


def get_service(request: Request) -> TranslationService:
    service: TranslationService = request.app.state.translation
    return service


Service = Annotated[TranslationService, Depends(get_service)]


class NewIssue(BaseModel):
    rev: str = Field(min_length=1, max_length=20)
    data: date = Field(default_factory=date.today)
    descrizione: str = ""
    nella_tabella: bool = True


@router.get("/projects/{project_id}/issues")
def list_issues(root: Root) -> list[dict[str, Any]]:
    return store.list_issues(root)


@router.post("/projects/{project_id}/issues", status_code=201)
def create_issue(root: Root, service: Service, body: NewIssue) -> dict[str, Any]:
    project = load_project(root)

    def official(path: str, text: str) -> str:
        return str(service.translation(root, project, path, text)["markdown"])

    return store.create(
        root,
        project,
        body.rev,
        body.data,
        body.descrizione,
        official,
        add_to_revisions=body.nella_tabella,
    )


@router.get("/projects/{project_id}/issues/{rev}")
def get_issue(root: Root, rev: str) -> dict[str, Any]:
    return store.meta(root, rev)


@router.delete("/projects/{project_id}/issues/{rev}", status_code=204)
def delete_issue(root: Root, rev: str) -> None:
    store.delete(root, rev)


def _side(
    root: Any, service: TranslationService, which: str, kind: str
) -> dict[str, compare_mod.Side]:
    project = load_project(root)

    def official(path: str, text: str) -> str:
        return str(service.translation(root, project, path, text)["markdown"])

    return compare_mod.load_side(root, None if which == DRAFT else which, kind, official)


@router.get("/projects/{project_id}/compare")
def compare(
    root: Root,
    service: Service,
    a: str,
    b: str = DRAFT,
    lang: Literal["sorgente", "ufficiale"] = "sorgente",
) -> dict[str, Any]:
    """What changed from ``a`` to ``b`` (an issue number, or ``bozza`` for the current text)."""
    result = compare_mod.compare(_side(root, service, a, lang), _side(root, service, b, lang))
    return {"a": a, "b": b, "lang": lang, **result}


class Against(BaseModel):
    against: str | None = None  # default: the previous issue


@router.post("/projects/{project_id}/issues/{rev}/changes")
async def generate_changes(root: Root, service: Service, rev: str, body: Against) -> dict[str, Any]:
    """Compare with the previous issue and let the model summarise each changed section."""
    project = load_project(root)
    store.meta(root, rev)
    against = body.against
    if against is None:
        before = [i["rev"] for i in store.list_issues(root)]
        index = before.index(rev)
        against = before[index - 1] if index > 0 else None
    old = _side(root, service, against, "sorgente") if against else {}
    compared = compare_mod.compare(old, _side(root, service, rev, "sorgente"))
    client = service._client(*service._config_for(project))
    rows = await changes_mod.summarise(client, compared, project.lingua_sorgente)
    return store.save_changes(root, rev, rows)


class ChangeRows(BaseModel):
    changes: list[dict[str, Any]]


@router.put("/projects/{project_id}/issues/{rev}/changes")
def put_changes(root: Root, rev: str, body: ChangeRows) -> dict[str, Any]:
    for row in body.changes:
        if not {"path", "title", "status", "summary"} <= row.keys():
            raise WorkspaceError("invalid_state", "each change needs path, title, status, summary")
    return store.save_changes(root, rev, body.changes)


@router.post("/projects/{project_id}/issues/{rev}/changes/use")
def use_changes(root: Root, rev: str) -> dict[str, Any]:
    """Write the change table into the revision table (``progetto.yaml``) for this issue."""
    project = load_project(root)
    text = changes_mod.describe(store.meta(root, rev).get("changes", []))
    if not text:
        raise WorkspaceError("invalid_state", "there are no changes to write")
    target = next((r for r in project.revisioni if r.rev == rev), None)
    if target is None:
        raise WorkspaceError("not_found", f"revision {rev} is not in the revision table")
    target.descrizione = text
    save_project(root, project)
    return {"rev": rev, "descrizione": text}


class RestoreBody(BaseModel):
    path: str


@router.post("/projects/{project_id}/issues/{rev}/restore")
def restore(root: Root, rev: str, body: RestoreBody) -> dict[str, str]:
    return {"hash": store.restore_section(root, rev, body.path)}
