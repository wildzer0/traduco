"""Export through the HTTP API with the fake model (M4)."""

import base64
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.workspace.diagrams import diagram_hash
from tests.integration.test_translation_api import FakeLlm, free_port
from tests.support.template_factory import logo_png

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9"><rect width="9" height="9"/></svg>'


@pytest.fixture
def llm() -> Iterator[FakeLlm]:
    fake = FakeLlm(free_port())
    fake.start()
    yield fake
    fake.stop()


@pytest.fixture
def xapi(tmp_path: Path, llm: FakeLlm, pandoc_bin: Path) -> Iterator[TestClient]:
    from app.main import create_app

    settings = Settings(
        workspaces_dir=tmp_path / "ws",
        frontend_dist=None,
        llm_base_url=f"http://127.0.0.1:{llm.port}/v1",
        llm_model="fake-model",
    )
    with TestClient(create_app(settings)) as c:
        yield c


def example(c: TestClient) -> str:
    r = c.post("/api/projects", json={"esempio": True})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def draw_diagrams(c: TestClient, pid: str, ws: Path) -> None:
    """Upload a PNG for every Mermaid block, as the browser does when a section is saved."""
    for md in (ws / pid / "capitoli").rglob("*.md"):
        text = md.read_text()
        if "```mermaid\n" in text:
            code = text.split("```mermaid\n", 1)[1].split("```", 1)[0]
            png = ws / "diagram.png"
            logo_png(png, 120, 60)
            body = {
                "svg": SVG,
                "png_base64": base64.b64encode(png.read_bytes()).decode(),
            }
            r = c.put(f"/api/projects/{pid}/diagrams/{diagram_hash(code)}", json=body)
            assert r.status_code in (200, 201, 204), r.text


def run_export(c: TestClient, pid: str, **body: object) -> dict:  # type: ignore[type-arg]
    r = c.post(f"/api/projects/{pid}/export", json=body)
    assert r.status_code == 202, r.text
    job = r.json()
    end = time.monotonic() + 60
    while time.monotonic() < end:
        status = c.get(f"/api/projects/{pid}/export/{job['id']}").json()
        if status["state"] != "running":
            return status  # type: ignore[no-any-return]
        time.sleep(0.2)
    raise AssertionError("the export did not finish")


def test_exporting_the_example_translates_and_fills_the_template(
    xapi: TestClient, tmp_path: Path
) -> None:
    pid = example(xapi)
    draw_diagrams(xapi, pid, tmp_path / "ws")
    status = run_export(xapi, pid, scope="project", language="ufficiale")
    assert status["state"] == "done", status
    r = xapi.get(f"/api/projects/{pid}/export/{status['id']}/download")
    assert r.status_code == 200 and "wordprocessingml" in r.headers["content-type"]
    out = tmp_path / "out.docx"
    out.write_bytes(r.content)
    doc = Document(str(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "{{" not in text and "}}" not in text
    assert "Manuale impianto di pompaggio" in text  # cover: project name from progetto.yaml
    assert "DOC-2026-014" in text
    assert "[EN] Scopo del documento" in text  # section title, translated by the (fake) model
    assert "[EN] Introduzione" in text  # chapter title too
    assert any(t.style is not None and t.style.style_id == "AziendaTabella" for t in doc.tables)
    with zipfile.ZipFile(out) as z:
        assert any(n.startswith("word/media/") for n in z.namelist())
    # the export leaves a snapshot for the import of revisions (M5) and the file in build/
    assert any((tmp_path / "ws" / pid / ".traduco" / "export").glob("*/combined.md"))
    assert any((tmp_path / "ws" / pid / "build").glob("*.docx"))


def test_a_missing_diagram_stops_the_export_with_a_clear_message(xapi: TestClient) -> None:
    pid = example(xapi)
    status = run_export(xapi, pid, scope="project", language="sorgente")
    assert status["state"] == "failed"
    assert status["error"]["code"] == "diagram_missing"
    assert status["error"]["details"]["diagrams"][0]["section"].endswith("03-collaudo.md")


def test_exporting_one_section_in_the_source_language(xapi: TestClient, tmp_path: Path) -> None:
    pid = example(xapi)
    status = run_export(
        xapi, pid, scope="section", path="capitoli/01-introduzione/01-scopo.md", language="sorgente"
    )
    assert status["state"] == "done", status
    out = tmp_path / "s.docx"
    out.write_bytes(xapi.get(f"/api/projects/{pid}/export/{status['id']}/download").content)
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "Questo documento descrive" in text and "[EN]" not in text
    assert "DOC-2026-014" in text  # the {{codice_documento}} field inside the paragraph


def test_a_chapter_scope_only_contains_that_chapter(xapi: TestClient, tmp_path: Path) -> None:
    pid = example(xapi)
    status = run_export(
        xapi, pid, scope="chapter", path="capitoli/01-introduzione", language="sorgente"
    )
    assert status["state"] == "done"
    out = tmp_path / "c.docx"
    out.write_bytes(xapi.get(f"/api/projects/{pid}/export/{status['id']}/download").content)
    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    assert "Scopo del documento" in text and "Collaudo" not in text


def test_without_a_template_pandoc_defaults_are_used(xapi: TestClient, tmp_path: Path) -> None:
    pid = xapi.post("/api/projects", json={"nome": "Senza template"}).json()["id"]
    ch = xapi.post(f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "Uno"}).json()[
        "path"
    ]
    xapi.post(f"/api/projects/{pid}/nodes", json={"kind": "section", "title": "Due", "parent": ch})
    status = run_export(xapi, pid, scope="project", language="sorgente")
    assert status["state"] == "done", status
    assert any("no template" in w for w in status["warnings"])


def test_bad_requests(xapi: TestClient) -> None:
    pid = example(xapi)
    assert xapi.post(f"/api/projects/{pid}/export", json={"scope": "section"}).status_code == 400
    assert xapi.get(f"/api/projects/{pid}/export/nope").status_code == 404
    status = run_export(
        xapi, pid, scope="section", path="capitoli/99-niente.md", language="sorgente"
    )
    assert status["state"] == "failed" and status["error"]["code"] == "not_found"
    job = xapi.post(
        f"/api/projects/{pid}/export", json={"scope": "project", "language": "sorgente"}
    ).json()
    early = xapi.get(f"/api/projects/{pid}/export/{job['id']}/download")
    assert early.status_code in (200, 409)


def test_a_default_template_that_is_not_in_the_folder_does_not_break_the_export(
    xapi: TestClient, tmp_path: Path
) -> None:
    """Seen in real use: a project made before M4 names 'manuale' but has no such file."""
    pid = example(xapi)
    for f in (tmp_path / "ws" / pid / "template").glob("manuale.*"):
        f.unlink()
    status = run_export(
        xapi, pid, scope="section", path="capitoli/01-introduzione/01-scopo.md", language="sorgente"
    )
    assert status["state"] == "done", status
    assert any('default template "manuale"' in w for w in status["warnings"])
    assert any("no template" in w for w in status["warnings"])


def test_a_template_asked_for_by_name_must_exist(xapi: TestClient) -> None:
    pid = example(xapi)
    status = run_export(
        xapi,
        pid,
        scope="section",
        path="capitoli/01-introduzione/01-scopo.md",
        language="sorgente",
        template="non-esiste",
    )
    assert status["state"] == "failed" and status["error"]["code"] == "template_missing"


def test_the_sample_template_can_be_added_to_any_project(xapi: TestClient, tmp_path: Path) -> None:
    pid = xapi.post("/api/projects", json={"nome": "Vuoto"}).json()["id"]
    r = xapi.post(f"/api/projects/{pid}/templates/example")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "manuale" and body["problems"] == [] and body["has_content"]
    assert (tmp_path / "ws" / pid / "template" / "manuale.docx").is_file()
    assert xapi.get(f"/api/projects/{pid}/templates").json() == [
        {"name": "manuale", "default": True, "has_mapping": True}
    ]
    assert xapi.post(f"/api/projects/{pid}/templates/example").status_code == 409


# --- formats and capabilities (M4b) ----------------------------------------------------------


def test_pdf_and_odt_need_libreoffice_and_say_so(
    xapi: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.export import office

    monkeypatch.setattr(office, "find_soffice", lambda: None)
    pid = example(xapi)
    status = run_export(
        xapi, pid, scope="section", path="capitoli/01-introduzione/01-scopo.md",
        language="sorgente", format="pdf",
    )  # fmt: skip
    assert status["state"] == "failed" and status["error"]["code"] == "office_missing"


def test_pdf_export_end_to_end(xapi: TestClient, soffice_bin: Path, tmp_path: Path) -> None:
    pid = example(xapi)
    for fmt, magic in (("pdf", b"%PDF"), ("odt", b"PK")):
        status = run_export(
            xapi, pid, scope="section", path="capitoli/01-introduzione/01-scopo.md",
            language="sorgente", format=fmt,
        )  # fmt: skip
        assert status["state"] == "done", status
        r = xapi.get(f"/api/projects/{pid}/export/{status['id']}/download")
        assert r.status_code == 200 and r.content.startswith(magic)
        assert status["filename"].endswith(f".{fmt}")


def test_capabilities_report_tools_and_the_model_download(
    xapi: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.export import office

    monkeypatch.setattr(office, "find_soffice", lambda: None)
    body = xapi.get("/api/capabilities").json()
    assert body["pandoc"]["available"] is True and body["libreoffice"]["available"] is False
    assert body["formats"] == ["docx", "html", "epub", "md"] and body["model"] == {"state": "none"}
    monkeypatch.setattr(office, "find_soffice", lambda: Path("/usr/bin/soffice"))
    assert xapi.get("/api/capabilities").json()["formats"] == [
        "docx",
        "html",
        "epub",
        "md",
        "pdf",
        "odt",
    ]
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("TRADUCO_RUNTIME_DIR", str(runtime))
    (runtime / "model.json").write_text(
        '{"state": "downloading", "model": "gemma4:e4b", "completed": 250, "total": 1000}'
    )
    model = xapi.get("/api/capabilities").json()["model"]
    assert model == {
        "state": "downloading",
        "model": "gemma4:e4b",
        "completed": 250,
        "total": 1000,
        "error": "",
    }
    (runtime / "model.json").write_text("{broken")
    assert xapi.get("/api/capabilities").json()["model"] == {"state": "none"}


# --- template wizard (M5) --------------------------------------------------------------------


def test_the_wizard_creates_a_template_that_exports(xapi: TestClient, tmp_path: Path) -> None:
    import base64

    pid = xapi.post("/api/projects", json={"nome": "Con wizard"}).json()["id"]
    ch = xapi.post(f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "Uno"}).json()[
        "path"
    ]
    xapi.post(f"/api/projects/{pid}/nodes", json={"kind": "section", "title": "Due", "parent": ch})
    logo = tmp_path / "logo.png"
    logo_png(logo, 200, 60)
    r = xapi.post(
        f"/api/projects/{pid}/templates/wizard",
        json={
            "nome": "Mio stile",
            "opzioni": {
                "font_body": "Georgia",
                "color": "#2E7D32",
                "cover_fields": ["data", "cliente"],
            },
            "logo_base64": base64.b64encode(logo.read_bytes()).decode(),
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "mio-stile" and body["problems"] == [] and body["has_content"]
    assert body["mapping"]["stili"]["titolo_1"] == "Heading1"
    assert xapi.get(f"/api/projects/{pid}/templates").json()[0]["default"] is True
    # the fields of the cover need values: without them the export says which ones
    first = run_export(xapi, pid, scope="project", language="sorgente")
    assert first["error"]["code"] == "missing_fields"
    assert first["error"]["details"]["fields"] == ["cliente", "codice_documento", "data"]
    xapi.patch(
        f"/api/projects/{pid}",
        json={"metadati": {"codice_documento": "X-1", "cliente": "ACME", "data": "2026-11-07"}},
    )
    status = run_export(xapi, pid, scope="project", language="sorgente")
    assert status["state"] == "done", status["error"]
    assert not any("no template" in w for w in status["warnings"])


def test_wizard_rejects_bad_input(xapi: TestClient) -> None:
    pid = xapi.post("/api/projects", json={"nome": "X"}).json()["id"]
    url = f"/api/projects/{pid}/templates/wizard"
    assert xapi.post(url, json={"opzioni": {"color": "red"}}).status_code == 422
    assert xapi.post(url, json={"logo_base64": "@@@"}).status_code == 415
    assert (
        xapi.post(url, json={"logo_base64": base64.b64encode(b"<svg/>").decode()}).status_code
        == 415
    )
    assert xapi.get("/api/template-wizard/fonts").json()[0] == "Calibri"
