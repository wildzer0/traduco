from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectSummary(BaseModel):
    id: str
    nome: str
    lingua_sorgente: str
    lingua_ufficiale: str
    cartella: str | None = None
    percorso: list[str] = []
    autore: str = ""
    emissione: str = ""
    emissione_data: str = ""
    ultima_modifica: str = ""
    sezioni: int = 0
    lingue: list[str] = []


class ProjectCreate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    lingua_sorgente: str = "it"
    lingua_ufficiale: str = "en"
    esempio: bool = False
    # Structure to start from: id of a bundled skeleton, or the text of a scheletro.yaml.
    scheletro: str | None = None
    scheletro_testo: str | None = None


class ProjectPatch(BaseModel):
    """Partial update of ``progetto.yaml``: only the keys sent are changed."""

    model_config = {"extra": "allow"}


class TreeNode(BaseModel):
    kind: Literal["chapter", "section"]
    path: str
    name: str
    title: str
    children: list["TreeNode"] = []


class TreeResponse(BaseModel):
    nodes: list[TreeNode]


class NodeCreate(BaseModel):
    kind: Literal["chapter", "section"]
    title: str = Field(min_length=1, max_length=200)
    parent: str | None = None


class NodePatch(BaseModel):
    """Exactly one operation: rename (``path``+``title``), move (``path``+``parent`` [+``index``]),
    or reorder (``order`` of the children of ``parent``)."""

    path: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    parent: str | None = None
    move: bool = False
    index: int | None = Field(default=None, ge=0)
    order: list[str] | None = None


class NodeResult(BaseModel):
    path: str | None = None
    renamed: dict[str, str] = {}


class DeleteResult(BaseModel):
    trash: str


class FileContent(BaseModel):
    path: str
    content: str
    hash: str


class FilePut(BaseModel):
    content: str


class FileSaved(BaseModel):
    path: str
    hash: str


class AssetSaved(BaseModel):
    path: str  # project-relative
    markdown: str  # reference to put in the section, relative to it (e.g. ``img/a.png``)


Json = dict[str, Any]
