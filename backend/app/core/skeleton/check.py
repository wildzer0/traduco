"""Conformity of a project with its skeleton: missing, empty, misplaced and out-of-order nodes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from app.core.skeleton import generate
from app.core.skeleton.model import Skeleton
from app.core.workspace import ops
from app.core.workspace.frontmatter import FrontMatterError, parse
from app.core.workspace.tree import CHAPTER_META, Node, build_tree

Status = Literal["ok", "missing", "empty", "out_of_order", "misplaced"]
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class Found:
    path: str
    kind: str
    node_id: str | None
    parent: str | None  # path of the parent chapter
    empty: bool


@dataclass(frozen=True)
class Item:
    id: str
    title: str
    mandatory: bool
    status: Status
    path: str | None
    guide: str


@dataclass
class Report:
    items: list[Item]
    extra: list[str] = field(default_factory=list)

    @property
    def conform(self) -> bool:
        return all(i.status == "ok" or not i.mandatory for i in self.items)


def _chapter_tag(root: Path, node: Node) -> str | None:
    meta = root / node.path / CHAPTER_META
    try:
        data = YAML(typ="safe").load(meta.read_text(encoding="utf-8")) if meta.is_file() else None
    except (YAMLError, OSError, UnicodeDecodeError):
        return None
    tag = data.get(generate.TAG) if isinstance(data, dict) else None
    return str(tag) if tag else None


def _section_tag(root: Path, node: Node) -> tuple[str | None, bool]:
    try:
        doc = parse((root / node.path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, FrontMatterError):
        return None, False
    tag = doc.meta.get(generate.TAG)
    return (str(tag) if tag else None), not _COMMENT.sub("", doc.body).strip()


def scan(root: Path) -> list[Found]:
    """Every chapter and section in document order with its skeleton tag."""
    found: list[Found] = []

    def visit(nodes: list[Node], parent: str | None) -> None:
        for node in nodes:
            if node.kind == "chapter":
                found.append(Found(node.path, "chapter", _chapter_tag(root, node), parent, False))
                visit(node.children, node.path)
            else:
                tag, empty = _section_tag(root, node)
                found.append(Found(node.path, "section", tag, parent, empty))

    visit(build_tree(root), None)
    return found


def _longest_increasing(values: list[int]) -> set[int]:
    """Indices of one longest strictly increasing subsequence."""
    chains: list[list[int]] = []
    for i, v in enumerate(values):
        prefix: list[int] = []
        for chain in chains:
            if values[chain[-1]] < v and len(chain) > len(prefix):
                prefix = chain
        chains.append([*prefix, i])
    longest: list[int] = []
    for chain in chains:
        if len(chain) > len(longest):
            longest = chain
    return set(longest)


def check(root: Path, skeleton: Skeleton, lang: str) -> Report:
    found = scan(root)
    by_id = {f.node_id: f for f in found if f.node_id}
    path_to_id = {f.path: f.node_id for f in found}
    order = {node.id: i for i, (node, _) in enumerate(skeleton.walk())}

    sequence = [f for f in found if f.node_id in order]
    positions = [order[str(f.node_id)] for f in sequence]
    in_order = {sequence[i].node_id for i in _longest_increasing(positions)}

    items: list[Item] = []
    for node, parent_id in skeleton.walk():
        hit = by_id.get(node.id)
        status: Status
        if hit is None:
            status = "missing"
        elif path_to_id.get(hit.parent or "") != parent_id:
            status = "misplaced"
        elif node.id not in in_order:
            status = "out_of_order"
        elif hit.empty and node.obbligatorio:
            status = "empty"
        else:
            status = "ok"
        items.append(
            Item(
                node.id, node.title(lang), node.obbligatorio, status,
                hit.path if hit else None, node.guida,
            )
        )  # fmt: skip
    extra = [f.path for f in found if f.node_id not in order]
    return Report(items, extra)


def create_missing(
    root: Path, skeleton: Skeleton, lang: str, include_optional: bool = False
) -> list[str]:
    """Create the missing nodes under their parents and put the siblings in skeleton order.

    Returns the paths created. Paths of existing nodes may change (renumbering): check again.
    """
    created: list[str] = []
    paths: dict[str, str] = {f.node_id: f.path for f in scan(root) if f.node_id}
    for node, parent_id in skeleton.walk():
        if node.id in paths or not (node.obbligatorio or include_optional):
            continue
        parent_path = paths.get(parent_id) if parent_id else None
        if parent_id and parent_path is None:
            continue  # its parent was optional and is not being created
        paths[node.id] = generate.create_node(root, node, parent_path, lang)
        created.append(paths[node.id])
    _restore_order(root, skeleton)
    return created


def _restore_order(root: Path, skeleton: Skeleton) -> None:
    order = {node.id: i for i, (node, _) in enumerate(skeleton.walk())}
    parents: dict[str | None, list[Found]] = {}
    for f in scan(root):
        parents.setdefault(f.parent, []).append(f)
    for parent, children in parents.items():
        ranked = sorted(
            range(len(children)),
            key=lambda i: (order.get(children[i].node_id or "", len(order)), i),
        )
        if ranked == list(range(len(children))):
            continue
        names = [children[i].path.rsplit("/", 1)[1] for i in ranked]
        ops.reorder(root, parent, names)
