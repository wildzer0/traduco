"""Two authors on the same section do not overwrite each other (M7 acceptance)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.integration.test_team_login import SECRET, idp, log_in  # noqa: F401
from tests.support.fake_idp import FakeIdp


@pytest.fixture
def app_clients(tmp_path: Path, idp: FakeIdp) -> Iterator[dict[str, TestClient]]:  # noqa: F811
    idp.users["elena"] = {"sub": "u-elena", "name": "Elena Autrice", "roles": ["author"]}
    settings = Settings(
        workspaces_dir=tmp_path / "ws",
        frontend_dist=None,
        llm_base_url="http://127.0.0.1:9/v1",
        mode="team",
        oidc_issuer=idp.url,
        oidc_client_secret="shh",
        session_secret=SECRET,
    )
    app = create_app(settings)
    clients = {who: TestClient(app) for who in ("carla", "anna", "elena", "bruno")}
    for client in clients.values():
        client.__enter__()
    for who, client in clients.items():
        log_in(client, idp, who)
    yield clients
    for client in clients.values():
        client.__exit__(None, None, None)


def test_the_second_author_cannot_write_while_the_first_is_editing(
    app_clients: dict[str, TestClient],
) -> None:
    carla, anna, elena, bruno = (app_clients[n] for n in ("carla", "anna", "elena", "bruno"))
    pid = carla.post("/api/projects", json={"nome": "Squadra"}).json()["id"]
    chapter = carla.post(f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "Uno"})
    section = carla.post(
        f"/api/projects/{pid}/nodes",
        json={"kind": "section", "title": "Due", "parent": chapter.json()["path"]},
    ).json()["path"]
    url = f"/api/projects/{pid}/files"

    def save(client: TestClient, text: str) -> int:
        file = client.get(url, params={"path": section}).json()
        status: int = client.put(
            url,
            params={"path": section},
            headers={"If-Match": file["hash"]},
            json={"content": text},
        ).status_code
        return status

    # Anna opens the section to edit it and gets the lock; Elena sees who has it
    people = anna.post(f"/api/projects/{pid}/presence", json={"path": section, "edit": True}).json()
    assert [(p["name"], p["editing"]) for p in people["people"]] == [("Anna Autrice", True)]
    seen = elena.post(f"/api/projects/{pid}/presence", json={"path": section, "edit": True}).json()
    assert {p["name"]: p["editing"] for p in seen["people"]} == {
        "Anna Autrice": True,
        "Elena Autrice": False,
    }
    refused = elena.put(
        url,
        params={"path": section},
        headers={"If-Match": "x"},
        json={"content": "Testo di Elena\n"},
    )
    assert refused.status_code == 423
    assert "Anna Autrice" in refused.json()["error"]["message"]
    assert save(anna, "Testo di Anna\n") == 200
    assert anna.get(url, params={"path": section}).json()["content"] == "Testo di Anna\n"

    # a reviewer can look but never takes the lock
    watched = bruno.post(
        f"/api/projects/{pid}/presence", json={"path": section, "edit": True}
    ).json()
    assert [p["editing"] for p in watched["people"] if p["name"] == "Bruno Revisore"] == [False]

    # when Anna leaves the section Elena can write
    anna.post(f"/api/projects/{pid}/presence", json={"path": None})
    assert save(elena, "Testo di Elena\n") == 200


def test_an_approval_needs_the_reviewer_role_and_is_logged_with_its_author(
    app_clients: dict[str, TestClient],
) -> None:
    carla, anna, bruno = (app_clients[n] for n in ("carla", "anna", "bruno"))
    pid = carla.post("/api/projects", json={"nome": "Audit"}).json()["id"]
    chapter = carla.post(f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "Uno"})
    section = carla.post(
        f"/api/projects/{pid}/nodes",
        json={"kind": "section", "title": "Due", "parent": chapter.json()["path"]},
    ).json()["path"]
    url = f"/api/projects/{pid}/files"
    file = carla.get(url, params={"path": section}).json()
    carla.put(
        url,
        params={"path": section},
        headers={"If-Match": file["hash"]},
        json={"content": "Un paragrafo.\n"},
    )
    carla.get(f"/api/projects/{pid}/translation", params={"path": section})
    seg = f"/api/projects/{pid}/segments/p:0"
    edited = anna.put(seg, params={"path": section}, json={"target": "A paragraph."})
    assert edited.status_code == 200, edited.text
    # an author may correct a translation but not approve it
    assert anna.put(seg, params={"path": section}, json={"action": "approve"}).status_code == 403
    assert bruno.put(seg, params={"path": section}, json={"action": "approve"}).status_code == 200

    log = carla.get("/api/audit", params={"project": pid}).json()
    assert [(e["action"], e["name"], e["target"]) for e in log] == [
        ("segment.approve", "Bruno Revisore", f"{section}#p:0")
    ]
    assert anna.get("/api/audit").status_code == 403  # only the administrator reads the log
