"""Project glossary: ``glossario.yaml``, matching in the source and checking of translations.

Rules (RF-40..42): an entry may impose a target term per language, forbid others and mark a term
"do not translate". Comparison is case-insensitive and tolerates simple plural endings.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from app.core.workspace.errors import WorkspaceError
from app.core.workspace.fsio import atomic_write_text

GLOSSARY_FILE = "glossario.yaml"
_PLURAL = r"(?:s|es)?"


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sorgente: str
    destinazione: dict[str, str] = Field(default_factory=dict)
    vietati: dict[str, list[str]] = Field(default_factory=dict)
    non_tradurre: bool = False
    note: str = ""

    @field_validator("sorgente")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("source term must not be empty")
        return value


def _yaml() -> YAML:
    yaml = YAML()
    yaml.allow_unicode = True
    yaml.default_flow_style = False
    yaml.width = 10_000
    return yaml


def load(root: Path) -> list[Entry]:
    path = root / GLOSSARY_FILE
    if not path.is_file():
        return []
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (YAMLError, OSError, UnicodeDecodeError) as exc:
        raise WorkspaceError("unreadable", f"{GLOSSARY_FILE} is not valid YAML") from exc
    if data is None:
        return []
    if not isinstance(data, list):
        raise WorkspaceError("unreadable", f"{GLOSSARY_FILE} must be a list of entries")
    return [Entry.model_validate(item) for item in data]


def save(root: Path, entries: list[Entry]) -> None:
    data = [e.model_dump(exclude_defaults=True) | {"sorgente": e.sorgente} for e in entries]
    # keep "sorgente" first for readable diffs
    ordered = [{"sorgente": d.pop("sorgente"), **d} for d in data]
    out = io.StringIO()
    _yaml().dump(ordered, out)
    atomic_write_text(root / GLOSSARY_FILE, out.getvalue() if ordered else "[]\n")


def _pattern(term: str) -> re.Pattern[str]:
    """Whole-word, case-insensitive; tolerates ``-s``/``-es`` and a changing final vowel
    (Italian ``offerta`` / ``offerte``, ``progetto`` / ``progetti``)."""
    term = term.strip()
    body = re.escape(term)
    if len(term) > 3 and term[-1].lower() in "aeio":
        body = re.escape(term[:-1]) + "[aeio]"
    return re.compile(rf"(?<!\w){body}{_PLURAL}(?!\w)", re.IGNORECASE)


def relevant(entries: list[Entry], source: str) -> list[Entry]:
    """Entries whose source term occurs in ``source``."""
    return [e for e in entries if _pattern(e.sorgente).search(source)]


def do_not_translate(entries: list[Entry]) -> tuple[str, ...]:
    return tuple(e.sorgente for e in entries if e.non_tradurre)


def violations(entries: list[Entry], target: str, lang: str) -> list[str]:
    """Reasons why ``target`` breaks the glossary (empty when it complies).

    ``entries`` must already be limited to those relevant for the source segment.
    """
    problems: list[str] = []
    for e in entries:
        if e.non_tradurre and not _pattern(e.sorgente).search(target):
            problems.append(f'"{e.sorgente}" must be kept unchanged')
        imposed = e.destinazione.get(lang)
        if imposed and not _pattern(imposed).search(target):
            problems.append(f'use "{imposed}" for "{e.sorgente}"')
        problems.extend(
            f'"{bad}" is forbidden (use "{imposed or e.sorgente}")'
            for bad in e.vietati.get(lang, [])
            if _pattern(bad).search(target)
        )
    return problems


def prompt_rules(entries: list[Entry], lang: str) -> str:
    """Glossary lines for the prompt of one segment."""
    lines: list[str] = []
    for e in entries:
        imposed = e.destinazione.get(lang)
        if e.non_tradurre:
            lines.append(f'- Keep "{e.sorgente}" unchanged.')
        elif imposed:
            forbidden = e.vietati.get(lang, [])
            extra = f" Never use: {', '.join(forbidden)}." if forbidden else ""
            lines.append(f'- Translate "{e.sorgente}" as "{imposed}".{extra}')
    return "\n".join(lines)
