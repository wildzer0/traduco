"""``template/<name>.yaml``: how the Markdown elements map to the styles of a company template."""

from __future__ import annotations

import io
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_text

# Roles a style can play, in the order they are shown to the user.
ROLES = (
    "titolo_1", "titolo_2", "titolo_3", "titolo_4", "titolo_5", "titolo_6",
    "corpo", "didascalia", "tabella", "elenco_puntato", "elenco_numerato", "citazione", "codice",
)  # fmt: skip
CONTENT = "{{CONTENUTO}}"


class Mapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contenuto: str = CONTENT
    #: role -> style id (``w:styleId``, which is the same in every language of Word)
    stili: dict[str, str] = Field(default_factory=dict)
    #: kept for the documented format: heading numbers come from the template's own styles
    numerazione_titoli: bool = True
    #: allow fields without a value (left empty) instead of failing the export
    campi_mancanti_ammessi: bool = False


def _yaml() -> YAML:
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    return yaml


def mapping_path(root: Path, name: str) -> Path:
    return root / "template" / f"{name}.yaml"


def template_path(root: Path, name: str) -> Path:
    return root / "template" / f"{name}.docx"


def load_mapping(root: Path, name: str) -> Mapping | None:
    path = mapping_path(root, name)
    if not path.is_file():
        return None
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
        return Mapping.model_validate(data)
    except (YAMLError, ValueError, OSError) as exc:
        raise WorkspaceError("unreadable", f"template/{name}.yaml is not valid: {exc}") from exc


def save_mapping(root: Path, name: str, mapping: Mapping) -> None:
    data = mapping.model_dump()
    data["stili"] = {role: data["stili"][role] for role in ROLES if role in data["stili"]}
    out = io.StringIO()
    _yaml().dump(data, out)
    atomic_write_text(mapping_path(root, name), out.getvalue())
