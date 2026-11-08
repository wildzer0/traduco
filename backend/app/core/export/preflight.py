"""What is wrong with a document before it is exported: a list, never a stop.

Looks only at the sections in the scope of the export. Everything it finds is something the export
would silently drop or leave behind (a broken link, a missing image, an empty section...).
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.workspace import attachments, frontmatter

_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s#]+)(#[^)\s]*)?\)")
_REMOTE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_FENCE = re.compile(r"^(```|~~~).*?^\1", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Finding:
    code: str  # empty_section | broken_link | link_outside | missing_image | remote_image | ...
    path: str
    detail: str
    severity: str = "warning"  # warning | error

    def public(self) -> dict[str, str]:
        return asdict(self)


def check_section(root: Path, rel: str, text: str, in_scope: set[str]) -> list[Finding]:
    body = _FENCE.sub("", frontmatter.parse(text).body)
    found: list[Finding] = []
    if not body.strip():
        found.append(Finding("empty_section", rel, ""))
    base = posixpath.dirname(rel)
    for url in _IMAGE.findall(body):
        if _REMOTE.match(url):
            found.append(Finding("remote_image", rel, url))
            continue
        if url.startswith(f"{attachments.ATTACHMENTS_DIR}/"):
            source = root / url
        else:
            source = root / posixpath.normpath(posixpath.join(base, url))
        if not source.is_file():
            found.append(Finding("missing_image", rel, url, "error"))
    for url, _anchor in _LINK.findall(body):
        if _REMOTE.match(url) or url.startswith("mailto:"):
            continue
        if url.startswith(f"{attachments.ATTACHMENTS_DIR}/"):
            if not (root / url).is_file():
                found.append(Finding("missing_attachment", rel, url, "error"))
            continue
        target = posixpath.normpath(posixpath.join(base, url))
        if not url.endswith(".md"):
            continue
        if not (root / target).is_file():
            found.append(Finding("broken_link", rel, url, "error"))
        elif target not in in_scope:
            found.append(Finding("link_outside", rel, url))
    return found


def check_review(rows: list[dict[str, Any]], in_scope: set[str]) -> list[Finding]:
    """One finding per section with translations a person still has to look at."""
    counts: dict[str, int] = {}
    for row in rows:
        if row.get("path") in in_scope and row.get("status") == "needs_review":
            counts[str(row["path"])] = counts.get(str(row["path"]), 0) + 1
    return [Finding("needs_review", path, str(n)) for path, n in sorted(counts.items())]
