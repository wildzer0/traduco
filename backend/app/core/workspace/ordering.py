"""Numeric-prefix ordering (``01-name``) and atomic renumbering of siblings (RF-03)."""

from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path

_PREFIX = re.compile(r"^(\d{2,})-(.+)$")


def split_prefix(name: str) -> tuple[int | None, str]:
    """``'01-scopo.md'`` -> ``(1, 'scopo.md')``; names without a prefix give ``(None, name)``."""
    match = _PREFIX.match(name)
    return (int(match[1]), match[2]) if match else (None, name)


def prefix_of(name: str) -> str:
    """The literal prefix of ``name`` including the dash (``'01-'``), or ``''``."""
    match = _PREFIX.match(name)
    return name[: match.start(2)] if match else ""


def sort_key(name: str) -> tuple[int, int, str]:
    """Prefixed names first, in numeric order; the others after them, alphabetically."""
    number, rest = split_prefix(name)
    if number is None:
        return (1, 0, name.lower())
    return (0, number, rest.lower())


def slugify(title: str) -> str:
    """File-system friendly slug from a title (accents removed, lowercase, dashes)."""
    ascii_text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "senza-titolo"


def format_name(index: int, base: str, width: int = 2) -> str:
    return f"{index:0{width}d}-{base}"


def plan_renumber(ordered: list[str]) -> dict[str, str]:
    """Map ``old name -> new name`` so that ``ordered`` gets prefixes 01, 02, ... in that order.

    Only entries whose name changes are returned. The prefix widens beyond two digits when needed.
    """
    width = max(2, len(str(len(ordered))))
    plan: dict[str, str] = {}
    for position, name in enumerate(ordered, start=1):
        new = format_name(position, split_prefix(name)[1], width)
        if new != name:
            plan[name] = new
    return plan


def apply_renames(parent: Path, mapping: dict[str, str]) -> None:
    """Rename siblings in two phases so swaps never collide; roll back everything on failure."""
    sources = set(mapping)
    for new in mapping.values():
        if new not in sources and (parent / new).exists():
            raise FileExistsError(parent / new)
    token = uuid.uuid4().hex[:8]
    temps = {old: f".traduco-tmp-{token}-{i}" for i, old in enumerate(mapping)}
    done_phase1: list[str] = []
    done_phase2: list[str] = []
    try:
        for old, tmp in temps.items():
            (parent / old).rename(parent / tmp)
            done_phase1.append(old)
        for old, new in mapping.items():
            (parent / temps[old]).rename(parent / new)
            done_phase2.append(old)
    except BaseException:
        for old in reversed(done_phase2):
            (parent / mapping[old]).rename(parent / temps[old])
        for old in reversed(done_phase1):
            (parent / temps[old]).rename(parent / old)
        raise
