"""Word-level comparison of two issues, or of an issue and the draft (RF-82)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.core.workspace import frontmatter

from . import store

_TOKEN = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)


@dataclass
class Side:
    title: str
    text: str


def body_of(text: str) -> str:
    try:
        return frontmatter.parse(text).body
    except frontmatter.FrontMatterError:
        return text


def word_diff(old: str, new: str) -> list[dict[str, str]]:
    """``[{"op": "equal"|"del"|"ins", "text": ...}]``, adjacent pieces of one kind merged."""
    a, b = _TOKEN.findall(old), _TOKEN.findall(new)
    ops: list[dict[str, str]] = []

    def add(op: str, tokens: list[str]) -> None:
        if not tokens:
            return
        text = "".join(tokens)
        if ops and ops[-1]["op"] == op:
            ops[-1]["text"] += text
        else:
            ops.append({"op": op, "text": text})

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            add("equal", a[i1:i2])
        else:
            add("del", a[i1:i2])
            add("ins", b[j1:j2])
    return ops


def _count(ops: list[dict[str, str]], kind: str) -> int:
    return sum(len(re.findall(r"\w+", o["text"])) for o in ops if o["op"] == kind)


def load_side(
    root: Path, rev: str | None, side: str, official_text: Callable[[str, str], str]
) -> dict[str, Side]:
    """Sections of an issue (or of the draft when ``rev`` is None) keyed by path."""
    out: dict[str, Side] = {}
    for entry in store.entries_of(root, rev):
        if entry.kind != "section":
            continue
        if rev is None:
            text = (root / entry.path).read_text(encoding="utf-8")
            if side == "ufficiale":
                text = official_text(entry.path, text)
        else:
            text = store.text_of(root, rev, side, entry.path) or ""
        out[entry.path] = Side(store.title_of(text, entry.title), text)
    return out


def compare(a: dict[str, Side], b: dict[str, Side]) -> dict[str, Any]:
    """Sections that were added, removed or changed from ``a`` to ``b``, with the word diff."""
    # a section renamed on disk (number prefix, file name) is still the same if its title is
    removed = [p for p in a if p not in b]
    added = [p for p in b if p not in a]
    renamed: dict[str, str] = {}
    for old in list(removed):
        for new in list(added):
            if a[old].title == b[new].title:
                renamed[new] = old
                removed.remove(old)
                added.remove(new)
                break
    sections: list[dict[str, Any]] = []
    unchanged = 0
    for path, side in b.items():
        if path in added:
            ops = word_diff("", body_of(side.text))
            sections.append(_row(path, side.title, "added", ops, None))
            continue
        before = a[renamed.get(path, path)]
        ops = word_diff(body_of(before.text), body_of(side.text))
        if all(o["op"] == "equal" for o in ops) and before.title == side.title:
            unchanged += 1
            continue
        sections.append(_row(path, side.title, "modified", ops, renamed.get(path)))
    for path in removed:
        ops = word_diff(body_of(a[path].text), "")
        sections.append(_row(path, a[path].title, "removed", ops, None))
    return {
        "sections": sections,
        "unchanged": unchanged,
        "changes": sum(len([o for o in s["ops"] if o["op"] != "equal"]) for s in sections),
    }


def _row(
    path: str, title: str, status: str, ops: list[dict[str, str]], was: str | None
) -> dict[str, Any]:
    return {
        "path": path,
        "title": title,
        "status": status,
        "was": was,
        "words_added": _count(ops, "ins"),
        "words_removed": _count(ops, "del"),
        "ops": ops,
    }
