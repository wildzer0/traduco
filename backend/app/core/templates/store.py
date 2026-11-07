"""Templates kept in a project: template/<name>.docx and template/<name>.yaml (RF-50, RF-56)."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.core.templates.analyze import (
    MAX_TEMPLATE_BYTES,
    Analysis,
    analyze,
    check_mapping,
    propose_mapping,
)
from app.core.templates.mapping import (
    Mapping,
    load_mapping,
    mapping_path,
    save_mapping,
    template_path,
)
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_bytes
from app.core.workspace.manifest import load_project, save_project
from app.core.workspace.ordering import slugify

_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,60}$")


@dataclass(frozen=True)
class TemplateInfo:
    name: str
    default: bool
    has_mapping: bool


def check_name(name: str) -> str:
    if not _NAME.match(name):
        raise WorkspaceError("invalid_path", f"invalid template name: {name!r}")
    return name


def list_templates(root: Path) -> list[TemplateInfo]:
    folder = root / "template"
    default = load_project(root).template_predefinito
    if not folder.is_dir():
        return []
    return [
        TemplateInfo(p.stem, p.stem == default, mapping_path(root, p.stem).is_file())
        for p in sorted(folder.glob("*.docx"))
        if _NAME.match(p.stem)
    ]


def _validate_docx(data: bytes) -> None:
    if len(data) > MAX_TEMPLATE_BYTES:
        raise WorkspaceError("too_large", "the template is larger than 50 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise WorkspaceError("invalid_template", "this is not a Word document (.docx)")
            if "word/vbaProject.bin" in names:
                raise WorkspaceError("invalid_template", "templates with macros are not accepted")
            if sum(i.file_size for i in z.infolist()) > 20 * MAX_TEMPLATE_BYTES:
                raise WorkspaceError("too_large", "the template expands to an unreasonable size")
    except zipfile.BadZipFile as exc:
        raise WorkspaceError("invalid_template", "this is not a Word document (.docx)") from exc


def import_template(root: Path, filename: str, data: bytes) -> str:
    """Save an uploaded ``.docx`` and its proposed mapping; returns the template name."""
    if not filename.lower().endswith(".docx"):
        raise WorkspaceError("invalid_template", "only .docx templates are accepted")
    _validate_docx(data)
    name = slugify(filename[: -len(".docx")]) or "template"
    name = name.replace(".", "-")[:60]
    base, n = name, 1
    while template_path(root, name).exists():
        n += 1
        name = f"{base}-{n}"
    check_name(name)
    atomic_write_bytes(template_path(root, name), data)
    try:
        analysis = analyze(template_path(root, name))
    except Exception as exc:  # python-docx / lxml raise many kinds of errors on damaged files
        template_path(root, name).unlink(missing_ok=True)
        raise WorkspaceError("invalid_template", f"the template cannot be read: {exc}") from exc
    save_mapping(root, name, propose_mapping(analysis))
    if load_project(root).template_predefinito is None:
        set_default(root, name)
    return name


def describe(root: Path, name: str) -> tuple[Analysis, Mapping, list[str]]:
    check_name(name)
    path = template_path(root, name)
    if not path.is_file():
        raise WorkspaceError("not_found", f"template not found: {name}")
    analysis = analyze(path)
    mapping = load_mapping(root, name) or propose_mapping(analysis)
    return analysis, mapping, check_mapping(mapping, analysis)


def update_mapping(root: Path, name: str, mapping: Mapping) -> list[str]:
    analysis, _, _ = describe(root, name)
    problems = check_mapping(mapping, analysis)
    save_mapping(root, name, mapping)
    return problems


def set_default(root: Path, name: str) -> None:
    check_name(name)
    if not template_path(root, name).is_file():
        raise WorkspaceError("not_found", f"template not found: {name}")
    project = load_project(root)
    project.template_predefinito = name
    save_project(root, project)


def delete_template(root: Path, name: str) -> None:
    check_name(name)
    template_path(root, name).unlink(missing_ok=True)
    mapping_path(root, name).unlink(missing_ok=True)
    project = load_project(root)
    if project.template_predefinito == name:
        project.template_predefinito = None
        save_project(root, project)
