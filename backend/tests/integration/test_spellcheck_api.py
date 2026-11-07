"""Spelling check through the HTTP API with a stand-in LanguageTool (RF-16)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from tests.unit.spellcheck.test_languagetool import Fake, server  # noqa: F401


@pytest.fixture
def client(tmp_path: Path, server: tuple[str, Fake]) -> Iterator[TestClient]:  # noqa: F811
    from app.main import create_app

    settings = Settings(
        workspaces_dir=tmp_path / "ws",
        frontend_dist=None,
        llm_base_url="http://127.0.0.1:9/v1",
        languagetool_url=server[0],
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_issues_are_found_per_segment_with_their_offsets(client: TestClient) -> None:
    pid = client.post("/api/projects", json={"nome": "T"}).json()["id"]
    chapter = client.post(
        f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "Uno"}
    ).json()
    section = client.post(
        f"/api/projects/{pid}/nodes",
        json={"kind": "section", "title": "Due", "parent": chapter["path"]},
    ).json()["path"]
    file = client.get(f"/api/projects/{pid}/files", params={"path": section}).json()
    client.put(
        f"/api/projects/{pid}/files",
        params={"path": section},
        headers={"If-Match": file["hash"]},
        json={"content": "Tutto bene qui.\n\nDimmi **qual'è** la pompa.\n"},
    )
    assert client.get("/api/capabilities").json()["languagetool"] == {"available": True}
    result = client.post(f"/api/projects/{pid}/spellcheck", json={"path": section}).json()
    [issue] = result["issues"]
    assert issue["word"] == "qual'è" and issue["replacements"] == ["qual è"]
    assert issue["context"][issue["offset"] : issue["offset"] + issue["length"]] == "qual'è"
