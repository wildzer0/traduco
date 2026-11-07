"""Export -> client edits -> import: the M5 acceptance scenario."""

import json
import time
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from fastapi.testclient import TestClient

from tests.integration.test_export_api import (  # noqa: F401, F811
    draw_diagrams,
    example,
    llm,
    run_export,
    xapi,
)


def download(c: TestClient, pid: str, status: dict, out: Path) -> Path:  # type: ignore[type-arg]
    r = c.get(f"/api/projects/{pid}/export/{status['id']}/download")
    out.write_bytes(r.content)
    return out


def wait(c: TestClient, pid: str, job: str) -> dict:  # type: ignore[type-arg]
    end = time.monotonic() + 60
    while time.monotonic() < end:
        status = c.get(f"/api/projects/{pid}/import/{job}").json()
        if status["state"] != "running":
            return status  # type: ignore[no-any-return]
        time.sleep(0.2)
    raise AssertionError("the import did not finish")


def tracked_replace(paragraph, new: str) -> None:  # type: ignore[no-untyped-def]
    """Replace the paragraph's text the way Word does with Track Changes on."""
    runs = list(paragraph.runs)
    for run in runs:
        deletion = OxmlElement("w:del")
        deletion.set(qn("w:id"), "901")
        deletion.set(qn("w:author"), "Cliente")
        deletion.set(qn("w:date"), "2026-11-01T10:00:00Z")
        run._r.addprevious(deletion)
        deletion.append(run._r)
        for t in run._r.findall(qn("w:t")):
            t.tag = qn("w:delText")
    insertion = OxmlElement("w:ins")
    insertion.set(qn("w:id"), "902")
    insertion.set(qn("w:author"), "Cliente")
    insertion.set(qn("w:date"), "2026-11-01T10:00:00Z")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = new
    text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    run.append(text)
    insertion.append(run)
    paragraph._p.append(insertion)


def body_paragraphs(doc: Any) -> list[Any]:
    styles = [p.style.style_id if p.style is not None else "" for p in doc.paragraphs]
    started = styles.index("AziendaTitolo1")  # after cover and contents
    return [
        p
        for p in doc.paragraphs[started:]
        if p.style is not None and p.style.style_id in ("AziendaCorpo",) and len(p.text) > 40
    ]


def test_three_edits_give_three_proposals_in_the_right_place(
    xapi: TestClient, tmp_path: Path
) -> None:
    ws = tmp_path / "ws"
    pid = example(xapi)
    draw_diagrams(xapi, pid, ws)
    status = run_export(xapi, pid, scope="project", language="sorgente")
    assert status["state"] == "done", status
    docx = download(xapi, pid, status, tmp_path / "exported.docx")

    doc = Document(str(docx))
    paragraphs = body_paragraphs(doc)
    assert len(paragraphs) >= 3
    first, second, third = paragraphs[0], paragraphs[1], paragraphs[2]
    for p, extra in ((first, " Verificare ogni anno."),):
        p.runs[-1].text += extra  # a direct edit
    second.runs[0].text = second.runs[0].text.replace(second.text[:6], "Modificato", 1)
    tracked_replace(third, "Testo riscritto dal cliente con Word, interamente nuovo.")
    revised = tmp_path / "revised.docx"
    doc.save(str(revised))

    r = xapi.post(f"/api/projects/{pid}/import?filename=revised.docx", content=revised.read_bytes())
    assert r.status_code == 202, r.text
    job = wait(xapi, pid, r.json()["id"])
    assert job["state"] == "done", job
    proposals = job["proposals"]
    assert [p["kind"] for p in proposals] == ["modified"] * 3, proposals
    assert [p["section"] for p in proposals] == [
        "capitoli/01-introduzione/01-scopo.md",
        "capitoli/01-introduzione/01-scopo.md",
        "capitoli/01-introduzione/02-ambito.md",
    ]
    assert any("Verificare ogni anno." in p["new"] for p in proposals)
    assert sum(p["tracked"] for p in proposals) == 1
    assert all(p["section"] and p["applicable"] and not p["stale"] for p in proposals)

    tracked = next(p for p in proposals if p["tracked"])
    done = xapi.post(
        f"/api/projects/{pid}/import/{job['id']}/proposals/{tracked['id']}",
        json={"action": "accept"},
    )
    assert done.status_code == 200, done.text
    text = (ws / pid / "capitoli").rglob("*.md")
    assert any("Testo riscritto dal cliente" in f.read_text() for f in text)
    again = xapi.post(
        f"/api/projects/{pid}/import/{job['id']}/proposals/{tracked['id']}",
        json={"action": "accept"},
    )
    assert again.status_code >= 400


def test_an_unchanged_export_gives_no_proposals(xapi: TestClient, tmp_path: Path) -> None:
    pid = example(xapi)
    draw_diagrams(xapi, pid, tmp_path / "ws")
    status = run_export(xapi, pid, scope="project", language="sorgente")
    docx = download(xapi, pid, status, tmp_path / "e.docx")
    r = xapi.post(f"/api/projects/{pid}/import", content=docx.read_bytes())
    job = wait(xapi, pid, r.json()["id"])
    assert job["state"] == "done" and job["proposals"] == []
    # the identifier inside the document finds its own snapshot: no "latest export" fallback
    assert job["warnings"] == []


def test_a_file_that_is_not_word_fails_cleanly(xapi: TestClient) -> None:
    pid = example(xapi)
    r = xapi.post(f"/api/projects/{pid}/import", content=b"not a zip")
    job = wait(xapi, pid, r.json()["id"])
    assert job["state"] == "failed" and job["error"]["code"]


def test_accepting_a_change_to_the_official_text_keeps_the_clients_wording(
    xapi: TestClient, tmp_path: Path
) -> None:
    ws = tmp_path / "ws"
    pid = example(xapi)
    draw_diagrams(xapi, pid, ws)
    status = run_export(xapi, pid, scope="project", language="ufficiale")
    assert status["state"] == "done", status
    doc = Document(str(download(xapi, pid, status, tmp_path / "e.docx")))
    paragraph = body_paragraphs(doc)[0]
    paragraph.runs[-1].text += " Client addition."
    revised = tmp_path / "r.docx"
    doc.save(str(revised))

    r = xapi.post(f"/api/projects/{pid}/import", content=revised.read_bytes())
    job = wait(xapi, pid, r.json()["id"])
    assert job["state"] == "done", job
    # (the fake model also prefixes the image-only paragraph, which a real one leaves alone)
    found = [p for p in job["proposals"] if "Client addition." in p["new"]]
    assert len(found) == 1, job
    proposal = found[0]
    assert proposal["proposed_source"] and "Client addition." in proposal["new"]

    done = xapi.post(
        f"/api/projects/{pid}/import/{job['id']}/proposals/{proposal['id']}",
        json={"action": "accept", "source": "Testo sorgente rivisto dall'autore."},
    )
    assert done.status_code == 200, done.text
    rel = proposal["section"]
    assert "Testo sorgente rivisto dall'autore." in (ws / pid / rel).read_text()
    store_file = ws / pid / ".traduco" / "segmenti" / "en" / Path(rel).with_suffix(".json")
    stored = [
        s for s in json.loads(store_file.read_text())["segments"] if s.get("origin") == "import"
    ]
    assert stored and stored[0]["locked"] and "Client addition." in stored[0]["target"]
