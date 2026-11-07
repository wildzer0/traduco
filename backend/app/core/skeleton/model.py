"""``scheletro.yaml``: format, parsing and validation with line numbers in the errors."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from app.core.workspace.tree import MAX_DEPTH

SKELETON_FILE = "scheletro.yaml"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class SkeletonError(ValueError):
    """The skeleton file is not valid; ``line`` is 1-based when it can be located."""

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(f"riga {line}: {message}" if line else message)
        self.reason = message
        self.line = line


class SkeletonNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    titolo: str | dict[str, str]
    obbligatorio: bool = True
    guida: str = ""
    nodi: list[SkeletonNode] = Field(default_factory=list)

    def title(self, lang: str) -> str:
        if isinstance(self.titolo, str):
            return self.titolo
        return self.titolo.get(lang) or next(iter(self.titolo.values()), self.id)


class Skeleton(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str
    versione: str | int | float = 1
    nodi: list[SkeletonNode] = Field(min_length=1)

    def walk(self) -> list[tuple[SkeletonNode, str | None]]:
        """Pre-order list of (node, parent id)."""
        out: list[tuple[SkeletonNode, str | None]] = []

        def visit(nodes: list[SkeletonNode], parent: str | None) -> None:
            for node in nodes:
                out.append((node, parent))
                visit(node.nodi, node.id)

        visit(self.nodi, None)
        return out


def _line_of(data: Any, loc: tuple[Any, ...]) -> int | None:
    """Line (1-based) of the YAML element addressed by a pydantic error location."""
    line: int | None = None
    node = data
    for part in loc:
        lc = getattr(node, "lc", None)
        try:
            if isinstance(part, int):
                line = lc.item(part)[0] + 1 if lc is not None else line
            else:
                line = lc.key(part)[0] + 1 if lc is not None else line
            node = node[part]
        except (KeyError, IndexError, TypeError, AttributeError):
            if lc is not None and line is None:
                line = lc.line + 1
            break
    return line


def _check_tree(nodes: Any, seen: set[str], depth: int) -> None:
    for index, item in enumerate(nodes):
        line = nodes.lc.item(index)[0] + 1
        node_id = str(item["id"])
        if not _ID.match(node_id):
            raise SkeletonError(f"id non valido: {node_id!r} (lettere, cifre, . _ -)", line)
        if node_id in seen:
            raise SkeletonError(f"id duplicato: {node_id!r}", line)
        seen.add(node_id)
        children = item.get("nodi") or []
        if depth == 1 and not children:
            raise SkeletonError(
                f"{node_id!r}: i nodi di primo livello sono capitoli e devono avere sotto-nodi",
                line,
            )
        if children and depth > MAX_DEPTH:
            raise SkeletonError(
                f"{node_id!r}: al massimo {MAX_DEPTH} livelli di capitoli (RF-02)", line
            )
        if children:
            _check_tree(children, seen, depth + 1)


def parse_skeleton(text: str) -> Skeleton:
    """Parse and validate; raises :class:`SkeletonError` with the offending line."""
    yaml = YAML(typ="rt")
    try:
        data = yaml.load(text)
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        reason = str(getattr(exc, "problem", None) or "YAML non valido")
        raise SkeletonError(reason, mark.line + 1 if mark is not None else None) from exc
    if not hasattr(data, "lc") or not hasattr(data, "keys"):
        raise SkeletonError("il file deve essere una mappa con nome e nodi", 1)
    try:
        skeleton = Skeleton.model_validate(_plain(data))
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = tuple(first["loc"])
        where = ".".join(str(p) for p in loc)
        reason = f"{where}: {first['msg']}" if where else str(first["msg"])
        raise SkeletonError(reason, _line_of(data, loc) or 1) from exc
    _check_tree(data["nodi"], set(), 1)
    return skeleton


def _plain(value: Any) -> Any:
    if hasattr(value, "keys"):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value
