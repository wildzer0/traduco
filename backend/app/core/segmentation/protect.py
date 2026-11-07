"""Protect non-translatable inline elements with placeholders before they reach the model.

Atoms (inline code, URLs, ``{{fields}}``, HTML tags, escapes, "do not translate" terms) become
``⟦n⟧``. Constructs that wrap translatable text (links, images, bold, italic, strike) become a pair
``⟦n⟧text⟦/n⟧`` and the markup is kept aside. After the translation every placeholder must be there
exactly once (ADR-006); restoring an unchanged text gives back the source byte for byte.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

OPEN, CLOSE = "⟦", "⟧"
_MARK = re.compile(r"⟦(/?)(\d+)⟧")
_ESCAPABLE = r"\\`*_{}\[\]()#+\-.!|<>~"


class PlaceholderError(ValueError):
    """The translation lost, duplicated, invented or misordered a placeholder."""


@dataclass(frozen=True)
class Protected:
    text: str
    atoms: dict[int, str]
    pairs: dict[int, tuple[str, str]]

    @property
    def count(self) -> int:
        return len(self.atoms) + len(self.pairs)


class _Builder:
    def __init__(self, terms: Iterable[str]) -> None:
        self.next_id = 1
        self.atoms: dict[int, str] = {}
        self.pairs: dict[int, tuple[str, str]] = {}
        ordered = sorted({t for t in terms if t}, key=len, reverse=True)
        term_re = "|".join(re.escape(t) for t in ordered)
        parts = [
            r"(?P<code>(?P<tick>`+)(?:.+?)(?<!`)(?P=tick)(?!`))",
            rf"(?P<esc>\\[{_ESCAPABLE}])",
            r"(?P<image>!\[(?P<ialt>[^\]]*)\]\((?P<iurl>[^)]*)\))",
            r"(?P<link>\[(?P<ltext>[^\]]*)\]\((?P<lurl>[^)]*)\))",
            r"(?P<refl>\[(?P<rtext>[^\]]+)\]\[(?P<rref>[^\]]*)\])",
            r"(?P<fnref>\[\^[^\]]+\])",
            r"(?P<field>\{\{.*?\}\})",
            r"(?P<html></?[A-Za-z][^>\n]*>)",
            r"(?P<url>https?://[^\s<>\]\)]*[^\s<>\]\).,;:!?'\"])",
            r"(?P<mark>[⟦⟧])",
        ]
        if term_re:
            parts.append(rf"(?P<term>(?<!\w)(?:{term_re})(?!\w))")
        self.pattern = re.compile("|".join(parts), re.DOTALL)

    def atom(self, literal: str) -> str:
        n = self.next_id
        self.next_id += 1
        self.atoms[n] = literal
        return f"{OPEN}{n}{CLOSE}"

    def pair(self, opening: str, inner: str, closing: str) -> str:
        n = self.next_id
        self.next_id += 1
        self.pairs[n] = (opening, closing)
        return f"{OPEN}{n}{CLOSE}{inner}{OPEN}/{n}{CLOSE}"

    def scan(self, text: str) -> str:
        out: list[str] = []
        pos = 0
        for m in self.pattern.finditer(text):
            out.append(text[pos : m.start()])
            pos = m.end()
            kind = m.lastgroup
            if m.group("image") is not None:
                out.append(self.pair("![", self.scan(m.group("ialt")), f"]({m.group('iurl')})"))
            elif m.group("link") is not None:
                out.append(self.pair("[", self.scan(m.group("ltext")), f"]({m.group('lurl')})"))
            elif m.group("refl") is not None:
                out.append(self.pair("[", self.scan(m.group("rtext")), f"][{m.group('rref')}]"))
            else:
                assert kind is not None
                out.append(self.atom(m.group(0)))
        out.append(text[pos:])
        return "".join(out)


_EMPHASIS = (
    re.compile(r"(?P<d>\*\*|__)(?=\S)(?P<body>.+?)(?<=\S)(?P=d)", re.DOTALL),
    re.compile(r"(?P<d>~~)(?=\S)(?P<body>.+?)(?<=\S)(?P=d)", re.DOTALL),
    re.compile(r"(?<![\w*])(?P<d>\*)(?=\S)(?P<body>[^*]+?)(?<=\S)(?P=d)(?!\*)", re.DOTALL),
    re.compile(r"(?<![\w_])(?P<d>_)(?=\S)(?P<body>[^_]+?)(?<=\S)(?P=d)(?![\w_])", re.DOTALL),
)


def _balanced(body: str, pairs: Iterable[int]) -> bool:
    """Does every placeholder pair opened inside ``body`` also close inside it, in order?"""
    known = set(pairs)
    stack: list[int] = []
    for m in _MARK.finditer(body):
        n = int(m.group(2))
        if n not in known:
            continue  # an atom: nothing to close
        if m.group(1) != "/":
            stack.append(n)
        elif stack and stack[-1] == n:
            stack.pop()
        else:
            return False
    return not stack


def protect(source: str, non_translate: Iterable[str] = ()) -> Protected:
    """Replace the elements that must not be translated by placeholders."""
    builder = _Builder(non_translate)
    text = builder.scan(source)

    def wrap(m: re.Match[str]) -> str:
        # an emphasis that would cut across a pair found earlier (``_:*_*``) is left as text
        return (
            builder.pair(m["d"], m["body"], m["d"]) if _balanced(m["body"], builder.pairs) else m[0]
        )

    for rule in _EMPHASIS:
        text = rule.sub(wrap, text)
    return Protected(text, dict(builder.atoms), dict(builder.pairs))


def check(translated: str, protected: Protected) -> None:
    """Raise :class:`PlaceholderError` unless all placeholders are present, once, and nested."""
    seen_atoms: dict[int, int] = {}
    opened: list[int] = []
    closed: set[int] = set()
    opens: set[int] = set()
    for m in _MARK.finditer(translated):
        closing, n = m.group(1) == "/", int(m.group(2))
        if n in protected.atoms and not closing:
            seen_atoms[n] = seen_atoms.get(n, 0) + 1
        elif n in protected.pairs:
            if closing:
                if not opened or opened[-1] != n:
                    raise PlaceholderError(f"placeholder {n} closed out of order")
                opened.pop()
                if n in closed:
                    raise PlaceholderError(f"placeholder {n} closed twice")
                closed.add(n)
            else:
                if n in opens:
                    raise PlaceholderError(f"placeholder {n} opened twice")
                opens.add(n)
                opened.append(n)
        else:
            raise PlaceholderError(f"unknown placeholder {n}")
    for n in protected.atoms:
        if seen_atoms.get(n, 0) != 1:
            raise PlaceholderError(f"placeholder {n} appears {seen_atoms.get(n, 0)} times")
    for n in protected.pairs:
        if n not in opens or n not in closed:
            raise PlaceholderError(f"placeholder {n} is not a complete pair")
    if opened:
        raise PlaceholderError("unbalanced placeholders")


def restore(translated: str, protected: Protected) -> str:
    """Verify and substitute the placeholders with their original markup."""
    check(translated, protected)

    def swap(m: re.Match[str]) -> str:
        closing, n = m.group(1) == "/", int(m.group(2))
        if n in protected.atoms:
            return protected.atoms[n]
        opening, closer = protected.pairs[n]
        return closer if closing else opening

    return _MARK.sub(swap, translated)
