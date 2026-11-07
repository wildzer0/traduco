"""Align the segments of an edited file with the stored ones (docs/02: "Riconciliazione")."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import Segment


@dataclass(frozen=True)
class Match:
    """``old_key`` is the stored segment a new one descends from.

    ``exact`` is true when the source text is unchanged, so the stored translation is reusable.
    """

    old_key: str
    exact: bool


def _family(key: str) -> str:
    return key.split(":", 1)[0]


def reconcile(old: Sequence[tuple[str, str]], new: Sequence[Segment]) -> dict[str, Match | None]:
    """Map every new segment key to its predecessor in ``old`` (``(key, source_hash)`` pairs).

    1. Same hash: exact match, preferring the same key, then the nearest unused one by order.
       A segment keeps its translation even if it moved.
    2. Remaining: the changed ones are paired by position, in document order and only within
       the same kind of segment (a heading never inherits a table cell's translation).
    """
    result: dict[str, Match | None] = {s.key: None for s in new}
    used: set[int] = set()
    matched: dict[int, int] = {}
    by_hash: dict[str, list[int]] = {}
    for i, (_, h) in enumerate(old):
        by_hash.setdefault(h, []).append(i)

    for j, seg in enumerate(new):
        candidates = [i for i in by_hash.get(seg.hash, []) if i not in used]
        if not candidates:
            continue
        same = [i for i in candidates if old[i][0] == seg.key]
        pick = same[0] if same else min(candidates, key=lambda i: abs(i - j))
        used.add(pick)
        matched[j] = pick
        result[seg.key] = Match(old[pick][0], True)

    free_old = [i for i in range(len(old)) if i not in used]
    free_new = [j for j in range(len(new)) if j not in matched]
    pending: dict[str, list[int]] = {}
    for i in free_old:
        pending.setdefault(_family(old[i][0]), []).append(i)
    # Pair unmatched segments of the same kind in document order, keeping relative order:
    # each new segment takes the first unused old one that is not before the previous pairing.
    last = -1
    for j in free_new:
        queue = [i for i in pending.get(_family(new[j].key), []) if i > last]
        if queue:
            pick = queue[0]
            pending[_family(new[j].key)].remove(pick)
            last = pick
            result[new[j].key] = Match(old[pick][0], False)
    return result
