"""The home page's API: folders, projects with their details, copies and the trash."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    from app.main import create_app

    settings = Settings(
        workspaces_dir=tmp_path / "ws", frontend_dist=None, llm_base_url="http://127.0.0.1:9/v1"
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_the_whole_life_of_organising_projects(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"nome": "Manuale pompa"}).json()["id"]
    top = client.post("/api/folders", json={"nome": "Clienti"})
    assert top.status_code == 201, top.text
    sub = client.post("/api/folders", json={"nome": "ACME", "genitore": top.json()["id"]}).json()
    assert (
        client.post("/api/folders", json={"nome": "acme", "genitore": top.json()["id"]}).status_code
        == 409
    )

    assert (
        client.put(f"/api/projects/{pid}/folder", json={"cartella": sub["id"]}).status_code == 200
    )
    home = client.get("/api/workspace").json()
    assert [f["percorso"] for f in home["folders"] if f["id"] == sub["id"]] == [["Clienti", "ACME"]]
    [project] = home["projects"]
    assert project["cartella"] == sub["id"] and project["percorso"] == ["Clienti", "ACME"]
    assert set(project) >= {"autore", "emissione", "ultima_modifica", "sezioni", "lingue"}
    assert client.get("/api/projects").json()[0]["cartella"] == sub["id"]  # the old list has it too

    moved = client.patch(
        f"/api/folders/{sub['id']}", json={"genitore": None, "sposta": True, "nome": "ACME srl"}
    )
    assert moved.json()["genitore"] is None and moved.json()["nome"] == "ACME srl"
    assert (
        client.patch(
            f"/api/folders/{top.json()['id']}", json={"genitore": sub["id"], "sposta": True}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/folders/{sub['id']}", json={"genitore": top.json()["id"], "sposta": True}
        ).status_code
        == 422
    )

    copy = client.post(f"/api/projects/{pid}/duplicate", json={"nome": "Manuale pompa v2"})
    assert copy.status_code == 201 and copy.json()["nome"] == "Manuale pompa v2"
    assert copy.json()["cartella"] == sub["id"]

    gone = client.delete(f"/api/projects/{pid}")
    assert gone.status_code == 200
    assert [p["id"] for p in client.get("/api/workspace").json()["projects"]] == [copy.json()["id"]]
    assert client.get(f"/api/projects/{pid}").status_code == 404
    [entry] = client.get("/api/trash").json()
    assert entry["id"] == pid
    back = client.post(f"/api/trash/{entry['name']}/restore")
    assert (
        back.status_code == 201
        and client.get(f"/api/projects/{back.json()['id']}").status_code == 200
    )

    assert client.delete(f"/api/folders/{sub['id']}").status_code == 204  # the projects stay
    assert len(client.get("/api/workspace").json()["projects"]) == 2


def test_a_name_that_cannot_be_a_trash_entry_is_refused(client: TestClient) -> None:
    assert client.post("/api/trash/..%2Fx/restore").status_code in (400, 404)
    assert client.delete("/api/trash/nonsense").status_code == 400
    assert client.post("/api/projects/missing/duplicate", json={}).status_code == 404
