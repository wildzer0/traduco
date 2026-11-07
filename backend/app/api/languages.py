"""The languages of a project and how far each one is translated (RF-21b…d)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import Root
from app.core.segmentation.segmenter import segment
from app.core.translation import store
from app.core.workspace.errors import WorkspaceError
from app.core.workspace.manifest import load_project
from app.core.workspace.sections import read_section
from app.core.workspace.tree import Node, build_tree

router = APIRouter(tags=["languages"])


def _sections(nodes: list[Node]) -> list[Node]:
    out: list[Node] = []
    for node in nodes:
        if node.kind == "section":
            out.append(node)
        out.extend(_sections(node.children))
    return out


@router.get("/projects/{project_id}/languages")
def languages(root: Root) -> list[dict[str, Any]]:
    """Source, official and additional languages with the share of segments translated."""
    project = load_project(root)
    docs = []
    for node in _sections(build_tree(root)):
        try:
            docs.append((node.path, segment(read_section(root, node.path)[0])))
        except WorkspaceError:
            continue
    total = sum(len(doc.segments) for _, doc in docs)
    rows: list[dict[str, Any]] = [
        {
            "code": project.lingua_sorgente,
            "role": "source",
            "percent": 100,
            "translated": total,
            "total": total,
        }
    ]
    for code in project.target_languages:
        done = 0
        for path, doc in docs:
            stored = store.load(root, code, path)
            fresh = {s.key: s for s in stored.segments} if stored else {}
            done += sum(
                1
                for seg in doc.segments
                if (st := fresh.get(seg.key)) is not None
                and st.target
                and st.status != "queued"
                and (st.source_hash == seg.hash or st.locked)
            )
        extra = next((a for a in project.lingue_aggiuntive if a.codice == code), None)
        rows.append(
            {
                "code": code,
                "role": "official" if code == project.lingua_ufficiale else "additional",
                "percent": round(100 * done / total) if total else 100,
                "translated": done,
                "total": total,
                "tono": extra.tono if extra else None,
                "base": extra.base if extra else None,
                "formato_date": extra.formato_date if extra else None,
            }
        )
    return rows
