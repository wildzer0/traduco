"""Parse and render the YAML front matter of a section, preserving the body byte for byte."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

_OPEN = re.compile(r"\A---[ \t]*\r?\n")
_CLOSE = re.compile(r"^(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.MULTILINE)


class FrontMatterError(ValueError):
    """The front matter is not a valid YAML mapping."""


def _yaml() -> YAML:
    yaml = YAML()  # round-trip: keeps key order, quoting and comments
    yaml.default_flow_style = False
    yaml.width = 10_000
    yaml.allow_unicode = True
    return yaml


@dataclass
class Document:
    """A section split into mutable ``meta`` and the untouched Markdown ``body``."""

    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""


def parse(text: str) -> Document:
    opening = _OPEN.match(text)
    if opening is None:
        return Document({}, text)
    closing = _CLOSE.search(text, opening.end())
    if closing is None:  # no closing fence: a thematic break, not front matter
        return Document({}, text)
    raw = text[opening.end() : closing.start()]
    try:
        data = _yaml().load(raw) if raw.strip() else {}
    except YAMLError as exc:
        raise FrontMatterError(f"invalid front matter: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontMatterError("front matter must be a mapping")
    return Document(data, text[closing.end() :])


def render(doc: Document) -> str:
    if not doc.meta:
        return doc.body
    out = io.StringIO()
    _yaml().dump(doc.meta, out)
    return f"---\n{out.getvalue()}---\n{doc.body}"
