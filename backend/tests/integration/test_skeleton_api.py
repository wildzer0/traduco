from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings, get_settings

TEXT = """\
nome: Mini
nodi:
  - id: intro
    titolo: Introduzione
    nodi:
      - id: scopo
        titolo: Scopo
      - id: ambito
        titolo: Ambito
"""


def ws(api: TestClient) -> Path:
    settings: Settings = api.app.dependency_overrides[get_settings]()  # type: ignore[attr-defined]
    return settings.workspaces_path


def test_lists_bundled_skeletons(api: TestClient) -> None:
    ids = [s["id"] for s in api.get("/api/skeletons").json()]
    assert "ecss-e-st-10-06c" in ids


def test_create_project_from_bundled_skeleton(api: TestClient) -> None:
    r = api.post("/api/projects", json={"nome": "Spec", "scheletro": "ecss-e-st-10-06c"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert (ws(api) / pid / "scheletro.yaml").is_file()
    tree = api.get(f"/api/projects/{pid}/tree").json()["nodes"]
    assert [n["title"] for n in tree][:2] == ["Introduzione", "Documenti"]
    assert tree[0]["children"][0]["kind"] == "section"
    check = api.get(f"/api/projects/{pid}/skeleton/check").json()
    assert not check["conform"]
    assert {i["status"] for i in check["items"]} <= {"ok", "empty"}


def test_create_project_from_pasted_text(api: TestClient) -> None:
    r = api.post("/api/projects", json={"nome": "Mini", "scheletro_testo": TEXT})
    pid = r.json()["id"]
    assert (ws(api) / pid / "capitoli/01-introduzione/02-ambito.md").is_file()


def test_invalid_skeleton_is_refused_with_line_and_creates_nothing(api: TestClient) -> None:
    bad = "nome: X\nnodi:\n  - id: a\n    titolo: A\n"
    r = api.post("/api/projects", json={"nome": "Bad", "scheletro_testo": bad})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "invalid_skeleton" and err["details"]["line"] == 3
    assert "riga 3" in err["message"]
    assert api.get("/api/projects").json() == []


def test_unknown_bundled_skeleton_is_404(api: TestClient) -> None:
    assert api.post("/api/projects", json={"nome": "X", "scheletro": "nope"}).status_code == 404
    assert api.post("/api/projects", json={"nome": "X", "scheletro": "../x"}).status_code == 400


def test_check_without_skeleton_is_404(api: TestClient) -> None:
    pid = api.post("/api/projects", json={"nome": "Vuoto"}).json()["id"]
    assert api.get(f"/api/projects/{pid}/skeleton").json() == {"present": False}
    assert api.get(f"/api/projects/{pid}/skeleton/check").status_code == 404


def test_missing_sections_and_create_missing(api: TestClient) -> None:
    pid = api.post("/api/projects", json={"nome": "Mini", "scheletro_testo": TEXT}).json()["id"]
    api.delete(
        f"/api/projects/{pid}/nodes", params={"path": "capitoli/01-introduzione/01-scopo.md"}
    )
    items = {i["id"]: i for i in api.get(f"/api/projects/{pid}/skeleton/check").json()["items"]}
    assert items["scopo"]["status"] == "missing"
    created = api.post(f"/api/projects/{pid}/skeleton/create-missing", json={}).json()["created"]
    assert len(created) == 1
    items = {i["id"]: i for i in api.get(f"/api/projects/{pid}/skeleton/check").json()["items"]}
    assert items["scopo"]["status"] != "missing"


def test_set_skeleton_on_existing_project(api: TestClient) -> None:
    pid = api.post("/api/projects", json={"nome": "Libero"}).json()["id"]
    assert api.put(f"/api/projects/{pid}/skeleton", json={"testo": "nope: 1"}).status_code == 422
    r = api.put(f"/api/projects/{pid}/skeleton", json={"testo": TEXT})
    assert r.status_code == 200
    check = api.get(f"/api/projects/{pid}/skeleton/check").json()
    assert {i["status"] for i in check["items"]} == {"missing"}  # nothing created yet
    api.post(f"/api/projects/{pid}/skeleton/create-missing", json={})
    check = api.get(f"/api/projects/{pid}/skeleton/check").json()
    assert "missing" not in {i["status"] for i in check["items"]}
