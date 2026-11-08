"""Attachments through the API: upload, list, download, CSV rows."""

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


def test_upload_list_download_and_table(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"nome": "Allegati"}).json()["id"]
    base = f"/api/projects/{pid}/attachments"
    up = client.post(base, params={"filename": "Dati.csv"}, content=b"a;b\n1;2\n")
    assert up.status_code == 201 and up.json() == {"path": "allegati/dati.csv", "name": "dati.csv"}
    assert [a["name"] for a in client.get(base).json()] == ["dati.csv"]
    assert client.get(f"{base}/dati.csv").content == b"a;b\n1;2\n"
    assert client.get(f"{base}/dati.csv/table").json() == {"rows": [["a", "b"], ["1", "2"]]}
    assert client.post(base, params={"filename": "x.exe"}, content=b"MZ").status_code == 400
    assert client.get(f"{base}/..%2Fprogetto.yaml").status_code in (400, 404)


def test_a_section_keeps_its_earlier_text(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"nome": "Storia"}).json()["id"]
    chapter = client.post(f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "Uno"})
    path = client.post(
        f"/api/projects/{pid}/nodes",
        json={"kind": "section", "title": "Due", "parent": chapter.json()["path"]},
    ).json()["path"]
    url = f"/api/projects/{pid}/files"
    file = client.get(url, params={"path": path}).json()
    first = client.put(
        url, params={"path": path}, headers={"If-Match": file["hash"]}, json={"content": "Primo.\n"}
    ).json()
    client.put(
        url,
        params={"path": path},
        headers={"If-Match": first["hash"]},
        json={"content": "Secondo.\n"},
    )
    versions = client.get(f"/api/projects/{pid}/history", params={"path": path}).json()
    assert len(versions) == 1  # a burst of edits is one version: the text before the burst
    one = client.get(
        f"/api/projects/{pid}/history/{versions[0]['id']}", params={"path": path}
    ).json()
    assert "Primo" not in one["content"] and "Secondo" not in one["content"]
