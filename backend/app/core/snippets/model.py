"""Project snippets (RF-86): ``snippet.yaml``, macros and persistent counters.

Macros expanded when a snippet is inserted: ``{{contatore:NAME}}`` (next number of a counter,
e.g. ``FOO-REQ-00042``; the count is kept in ``.traduco/contatori.json``), ``{{data}}`` (today, in
the source language's format), ``{{titolo}}`` (title of the open section), ``{{progetto}}``.
Any other ``{{name}}`` is left alone: it may be a template field. Tab-stops use the VS Code
syntax ``${1:placeholder}``, ``$1``, ``$0``; the editor decides how to walk them.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_text

FILE = "snippet.yaml"
COUNTERS = ".traduco/contatori.json"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_MACRO = re.compile(r"\{\{\s*(contatore:[A-Za-z0-9_-]+|data|titolo|progetto)\s*\}\}")
_lock = threading.Lock()


class Counter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prefisso: str = ""
    cifre: int = Field(default=5, ge=1, le=12)
    inizio: int = Field(default=1, ge=0)


class Snippet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alias: str
    testo: str
    descrizione: str = ""


class SnippetFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contatori: dict[str, Counter] = Field(default_factory=dict)
    snippet: list[Snippet] = Field(default_factory=list)


def parse(text: str) -> SnippetFile:
    try:
        data: Any = YAML(typ="safe").load(text) or {}
    except YAMLError as exc:
        raise WorkspaceError("invalid_state", f"{FILE}: {exc}") from exc
    try:
        parsed = SnippetFile.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise WorkspaceError("invalid_state", f"{FILE}: {where}: {first['msg']}") from exc
    seen: set[str] = set()
    for s in parsed.snippet:
        if not _NAME.match(s.alias):
            raise WorkspaceError("invalid_state", f"{FILE}: invalid alias {s.alias!r}")
        if s.alias in seen:
            raise WorkspaceError("invalid_state", f"{FILE}: alias {s.alias!r} appears twice")
        seen.add(s.alias)
        for macro in _MACRO.findall(s.testo):
            name = macro.split(":", 1)[1] if macro.startswith("contatore:") else None
            if name is not None and name not in parsed.contatori:
                raise WorkspaceError(
                    "invalid_state",
                    f"{FILE}: snippet {s.alias!r} uses the unknown counter {name!r}",
                )
    return parsed


def read_raw(root: Path) -> str:
    try:
        return (root / FILE).read_text(encoding="utf-8")
    except OSError:
        return ""


def load(root: Path) -> SnippetFile:
    return parse(read_raw(root))


def save_raw(root: Path, text: str) -> SnippetFile:
    parsed = parse(text)  # nothing invalid reaches the disk
    atomic_write_text(root / FILE, text)
    return parsed


def _counts(root: Path) -> dict[str, int]:
    try:
        data = json.loads((root / COUNTERS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: int(v) for k, v in data.items()} if isinstance(data, dict) else {}


def counters(root: Path) -> list[dict[str, Any]]:
    """Each counter with the identifier it would hand out next."""
    spec = load(root).contatori
    used = _counts(root)
    return [{"name": n, "next": _format(c, used.get(n, c.inizio - 1) + 1)} for n, c in spec.items()]


def _format(counter: Counter, number: int) -> str:
    return f"{counter.prefisso}{number:0{counter.cifre}d}"


def expand(
    root: Path, alias: str, *, title: str, project: str, today: date, language_date: str
) -> str:
    """The snippet's text with macros resolved; every counter used advances exactly once."""
    parsed = load(root)
    snippet = next((s for s in parsed.snippet if s.alias == alias), None)
    if snippet is None:
        raise WorkspaceError("not_found", f"snippet not found: {alias}")
    with _lock:
        used = _counts(root)
        advanced = False

        def replace(match: re.Match[str]) -> str:
            nonlocal advanced
            name = match.group(1)
            if name == "data":
                return language_date
            if name == "titolo":
                return title
            if name == "progetto":
                return project
            key = name.split(":", 1)[1]
            counter = parsed.contatori[key]
            used[key] = used.get(key, counter.inizio - 1) + 1
            advanced = True
            return _format(counter, used[key])

        text = _MACRO.sub(replace, snippet.testo)
        if advanced:
            atomic_write_text(root / COUNTERS, json.dumps(used, indent=2) + "\n")
    return text
