"""Issues, comparison, change table and comments through the HTTP API (M5b)."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.test_export_api import example, llm, xapi  # noqa: F401, F811

SECTION = "capitoli/01-introduzione/01-scopo.md"


def read(c: TestClient, pid: str) -> dict:  # type: ignore[type-arg]
    r = c.get(f"/api/projects/{pid}/files", params={"path": SECTION})
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def edit(c: TestClient, pid: str, add: str) -> None:
    file = read(c, pid)
    r = c.put(
        f"/api/projects/{pid}/files",
        params={"path": SECTION},
        json={"content": file["content"] + "\n" + add + "\n"},
        headers={"If-Match": file["hash"]},
    )
    assert r.status_code == 200, r.text


def test_freeze_edit_compare_summarise_restore(xapi: TestClient, tmp_path: Path) -> None:  # noqa: F811
    pid = example(xapi)
    original = read(xapi, pid)["content"]
    made = xapi.post(
        f"/api/projects/{pid}/issues", json={"rev": "01", "descrizione": "Prima emissione"}
    )
    assert made.status_code == 201, made.text
    assert xapi.post(f"/api/projects/{pid}/issues", json={"rev": "01"}).status_code == 409

    edit(xapi, pid, "Il collaudo va ripetuto ogni anno.")
    r = xapi.get(f"/api/projects/{pid}/compare", params={"a": "01"})
    assert r.status_code == 200, r.text
    sections = {s["path"]: s for s in r.json()["sections"]}
    assert list(sections) == [SECTION] and sections[SECTION]["words_added"] >= 6
    assert any(o["op"] == "ins" and "collaudo" in o["text"] for o in sections[SECTION]["ops"])
    assert (
        xapi.get(
            f"/api/projects/{pid}/compare", params={"a": "01", "lang": "ufficiale"}
        ).status_code
        == 200
    )

    second = xapi.post(f"/api/projects/{pid}/issues", json={"rev": "02"})
    assert second.status_code == 201
    rows = xapi.post(f"/api/projects/{pid}/issues/02/changes", json={})
    assert rows.status_code == 200, rows.text
    changes = rows.json()["changes"]
    assert [c["path"] for c in changes] == [SECTION] and changes[0]["summary"]

    edited = [{**changes[0], "summary": "Aggiunto il collaudo annuale"}]
    assert (
        xapi.put(f"/api/projects/{pid}/issues/02/changes", json={"changes": edited}).status_code
        == 200
    )
    used = xapi.post(f"/api/projects/{pid}/issues/02/changes/use")
    assert used.status_code == 200 and "Aggiunto il collaudo annuale" in used.json()["descrizione"]
    project = xapi.get(f"/api/projects/{pid}").json()
    assert [r["rev"] for r in project["revisioni"]][-2:] == ["01", "02"]
    assert "collaudo annuale" in project["revisioni"][-1]["descrizione"]

    back = xapi.post(f"/api/projects/{pid}/issues/01/restore", json={"path": SECTION})
    assert back.status_code == 200, back.text
    assert read(xapi, pid)["content"] == original
    assert [i["rev"] for i in xapi.get(f"/api/projects/{pid}/issues").json()] == ["01", "02"]
    assert xapi.delete(f"/api/projects/{pid}/issues/02").status_code == 204


def test_comments_are_stored_beside_the_document(xapi: TestClient, tmp_path: Path) -> None:  # noqa: F811
    pid = example(xapi)
    tree = xapi.get(f"/api/projects/{pid}/translation", params={"path": SECTION}).json()
    key = tree["segments"][1]["key"]
    made = xapi.post(
        f"/api/projects/{pid}/comments",
        json={"path": SECTION, "key": key, "author": "Anna", "text": "Da verificare"},
    )
    assert made.status_code == 201, made.text
    thread = made.json()["id"]
    listed = xapi.get(f"/api/projects/{pid}/comments", params={"path": SECTION}).json()
    assert listed["counts"] == {"open": 1, "resolved": 0} and not listed["threads"][0]["lost"]
    base = {"path": SECTION}
    assert (
        xapi.post(
            f"/api/projects/{pid}/comments/{thread}/reply", json={**base, "text": "Ok"}
        ).status_code
        == 200
    )
    assert (
        xapi.patch(
            f"/api/projects/{pid}/comments/{thread}", json={**base, "status": "resolved"}
        ).status_code
        == 200
    )
    assert (
        tmp_path
        / "ws"
        / pid
        / ".traduco"
        / "commenti"
        / "capitoli"
        / "01-introduzione"
        / "01-scopo.json"
    ).is_file()
    # the section text itself carries no trace of the comment
    assert "Da verificare" not in read(xapi, pid)["content"]
    assert xapi.delete(f"/api/projects/{pid}/comments/{thread}", params=base).status_code == 204


def test_snippets_expand_through_the_api(xapi: TestClient) -> None:  # noqa: F811
    pid = example(xapi)
    base = f"/api/projects/{pid}/snippets"
    assert xapi.get(base).json()["snippets"] == []
    text = (
        'contatori:\n  REQ: { prefisso: "FOO-REQ-", cifre: 5 }\n'
        "snippet:\n  - alias: req\n    descrizione: Requisito\n"
        '    testo: "{{contatore:REQ}} in {{titolo}}"\n'
    )
    saved = xapi.put(base, json={"text": text})
    assert saved.status_code == 200 and saved.json()["snippets"][0]["alias"] == "req"
    assert xapi.put(base, json={"text": "snippet: ["}).status_code in (400, 409)
    first = xapi.post(f"{base}/req/expand", json={"path": SECTION}).json()["text"]
    second = xapi.post(f"{base}/req/expand", json={"path": SECTION}).json()["text"]
    assert first.startswith("FOO-REQ-00001 in ") and second.startswith("FOO-REQ-00002 in ")
    assert xapi.get(base).json()["counters"][0]["next"] == "FOO-REQ-00003"


def test_web_formats_open_without_a_server(xapi: TestClient, tmp_path: Path) -> None:  # noqa: F811
    import io
    import zipfile

    from tests.integration.test_export_api import draw_diagrams, run_export

    pid = example(xapi)
    draw_diagrams(xapi, pid, tmp_path / "ws")
    html = run_export(xapi, pid, scope="project", language="sorgente", format="html")
    assert html["state"] == "done" and html["filename"].endswith(".html"), html
    page = xapi.get(f"/api/projects/{pid}/export/{html['id']}/download")
    assert page.headers["content-type"].startswith("text/html")
    text = page.text
    assert "<script src" not in text and "<link " not in text  # nothing fetched: file:// works
    assert 'id="q"' in text and 'href="#' in text  # search box and index
    assert "data:image/png;base64," in text  # images are inside the file
    assert "Introduzione" in text

    md = run_export(xapi, pid, scope="project", language="sorgente", format="md")
    assert md["state"] == "done" and md["filename"].endswith(".zip"), md
    archive = zipfile.ZipFile(
        io.BytesIO(xapi.get(f"/api/projects/{pid}/export/{md['id']}/download").content)
    )
    assert "document.md" in archive.namelist() and any(
        n.startswith("img") for n in archive.namelist()
    )

    epub = run_export(xapi, pid, scope="project", language="sorgente", format="epub")
    assert epub["state"] == "done" and epub["filename"].endswith(".epub"), epub
    book = zipfile.ZipFile(
        io.BytesIO(xapi.get(f"/api/projects/{pid}/export/{epub['id']}/download").content)
    )
    assert "mimetype" in book.namelist() and any(n.endswith(".xhtml") for n in book.namelist())
