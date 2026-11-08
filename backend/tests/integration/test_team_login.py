"""Team mode: OIDC login, sessions and the permission of each role (ADR-046)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app.config import Settings
from tests.support.fake_idp import FakeIdp

SECRET = "s" * 48


@pytest.fixture
def idp() -> Iterator[FakeIdp]:
    fake = FakeIdp()
    fake.users = {
        "anna": {
            "sub": "u-anna",
            "name": "Anna Autrice",
            "email": "anna@x.it",
            "roles": ["traduco-author"],
        },
        "bruno": {"sub": "u-bruno", "name": "Bruno Revisore", "roles": ["reviewer"]},
        "carla": {"sub": "u-carla", "name": "Carla Admin", "roles": ["admin"]},
        "dario": {"sub": "u-dario", "name": "Dario", "roles": ["somebody-else"]},
    }
    fake.start()
    yield fake
    fake.stop()


def make_client(tmp_path: Path, idp: FakeIdp, name: str = "ws") -> TestClient:
    from app.main import create_app

    settings = Settings(
        workspaces_dir=tmp_path / name,
        frontend_dist=None,
        llm_base_url="http://127.0.0.1:9/v1",
        mode="team",
        oidc_issuer=idp.url,
        oidc_client_secret="shh",
        session_secret=SECRET,
    )
    return TestClient(create_app(settings))


def log_in(client: TestClient, idp: FakeIdp, who: str, next_url: str = "/") -> Response:
    start = client.get("/api/auth/login", params={"next": next_url}, follow_redirects=False)
    assert start.status_code == 302, start.text
    back = idp.authorize(start.headers["location"], who)
    path = back.split("testserver", 1)[1]
    response: Response = client.get(path, follow_redirects=False)
    return response


@pytest.fixture
def team(tmp_path: Path, idp: FakeIdp) -> Iterator[TestClient]:
    with make_client(tmp_path, idp) as client:
        yield client


def test_nobody_gets_in_without_logging_in(team: TestClient) -> None:
    assert team.get("/api/health").status_code == 200
    assert team.get("/api/me").json() == {"mode": "team", "user": None}
    for path in ("/api/projects", "/api/capabilities", "/api/llm/status"):
        r = team.get(path)
        assert r.status_code == 401 and r.json()["error"]["code"] == "http_401", path
    assert (
        team.put("/api/projects/x/files", params={"path": "a.md"}, json={"content": ""}).status_code
        == 401
    )


def test_login_gives_a_session_with_the_roles_of_the_provider(
    team: TestClient, idp: FakeIdp
) -> None:
    done = log_in(team, idp, "anna", next_url="/p/demo?s=capitoli/a.md")
    assert done.status_code == 302 and done.headers["location"] == "/p/demo?s=capitoli/a.md"
    cookie = done.headers["set-cookie"]
    assert "traduco_session=" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
    me = team.get("/api/me").json()["user"]
    assert me["name"] == "Anna Autrice" and me["roles"] == ["author"]
    assert "edit_source" in me["permissions"] and "approve" not in me["permissions"]
    assert team.get("/api/projects").status_code == 200
    team.post("/api/auth/logout")
    assert team.get("/api/projects").status_code == 401


def test_roles_are_enforced_on_the_routes(tmp_path: Path, idp: FakeIdp) -> None:
    with make_client(tmp_path, idp, "roles") as admin:
        log_in(admin, idp, "carla")
        project = admin.post("/api/projects", json={"nome": "Squadra"})
        assert project.status_code == 201, project.text
        pid = project.json()["id"]
        chapter = admin.post(
            f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "Uno"}
        ).json()
        section = admin.post(
            f"/api/projects/{pid}/nodes",
            json={"kind": "section", "title": "Due", "parent": chapter["path"]},
        ).json()["path"]
        cookies = {
            name: log_in(admin, idp, name).headers.get("set-cookie", "") for name in ("anna",)
        }
        assert cookies

    def as_user(who: str) -> TestClient:
        client = make_client(tmp_path, idp, "roles")
        client.__enter__()
        log_in(client, idp, who)
        return client

    anna, bruno = as_user("anna"), as_user("bruno")
    try:
        body = {"content": "Testo dell'autore.\n"}
        file = anna.get(f"/api/projects/{pid}/files", params={"path": section}).json()
        assert (
            anna.put(
                f"/api/projects/{pid}/files",
                params={"path": section},
                headers={"If-Match": file["hash"]},
                json=body,
            ).status_code
            == 200
        )
        # a reviewer reads and comments but does not write the source or configure the project
        assert bruno.get(f"/api/projects/{pid}/files", params={"path": section}).status_code == 200
        assert (
            bruno.put(f"/api/projects/{pid}/files", params={"path": section}, json=body).status_code
            == 403
        )
        assert bruno.put(f"/api/projects/{pid}/glossary", json=[]).status_code == 403
        # an author does not create projects or touch the model settings; neither does a reviewer
        assert anna.post("/api/projects", json={"nome": "Altro"}).status_code == 403
        assert (
            anna.get("/api/settings").status_code == 403
            and bruno.put("/api/settings", json={}).status_code == 403
        )
        assert bruno.get(f"/api/projects/{pid}/tree").status_code == 200
    finally:
        anna.__exit__(None, None, None)
        bruno.__exit__(None, None, None)


def test_a_user_without_one_of_our_roles_is_turned_away(team: TestClient, idp: FakeIdp) -> None:
    refused = log_in(team, idp, "dario")
    assert refused.status_code == 403 and "no role" in refused.json()["error"]["message"]
    assert team.get("/api/me").json()["user"] is None


def test_roles_may_be_in_the_access_token_only(team: TestClient, idp: FakeIdp) -> None:
    idp.roles_in = "access"
    team.app.state.oidc.settings = team.app.state.oidc.settings.model_copy(  # type: ignore[attr-defined]
        update={"oidc_roles_claim": "realm_access.roles"}
    )
    assert log_in(team, idp, "carla").status_code == 302
    assert team.get("/api/me").json()["user"]["roles"] == ["admin"]


def test_a_forged_or_replayed_login_is_refused(team: TestClient, idp: FakeIdp) -> None:
    # another login's state
    start = team.get("/api/auth/login", follow_redirects=False)
    back = idp.authorize(start.headers["location"], "anna")
    tampered = back.split("testserver", 1)[1].replace("state=", "state=x")
    assert team.get(tampered, follow_redirects=False).status_code == 403
    # a token that belongs to a different login (nonce) or issuer
    idp.break_nonce = True
    assert log_in(team, idp, "anna").status_code == 403
    idp.break_nonce, idp.break_issuer = False, True
    assert log_in(team, idp, "anna").status_code == 403
    idp.break_issuer = False
    # a cookie we did not sign
    team.cookies.set("traduco_session", "e30.e30")
    assert team.get("/api/projects").status_code == 401
    # no cookie at all on the callback
    fresh = team.get(
        "/api/auth/callback", params={"code": "x", "state": "y"}, follow_redirects=False
    )
    assert fresh.status_code == 403


def test_the_page_after_login_is_always_on_this_site(team: TestClient, idp: FakeIdp) -> None:
    for evil in ("https://evil.example/x", "//evil.example", "javascript:alert(1)"):
        assert log_in(team, idp, "anna", next_url=evil).headers["location"] == "/"


def test_team_mode_refuses_to_start_without_a_secret_or_a_provider(
    tmp_path: Path, idp: FakeIdp
) -> None:
    from app.main import create_app

    base = {"workspaces_dir": tmp_path / "w", "frontend_dist": None, "mode": "team"}
    with (
        pytest.raises(RuntimeError, match="SESSION_SECRET"),
        TestClient(
            create_app(Settings(oidc_issuer=idp.url, **base))  # type: ignore[arg-type]
        ),
    ):
        pass
    with (
        pytest.raises(RuntimeError, match="OIDC_ISSUER"),
        TestClient(
            create_app(Settings(session_secret=SECRET, **base))  # type: ignore[arg-type]
        ),
    ):
        pass


def test_desktop_mode_is_unchanged(tmp_path: Path) -> None:
    from app.main import create_app

    settings = Settings(workspaces_dir=tmp_path / "d", frontend_dist=None)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/me").json() == {"mode": "desktop", "user": None}
        assert client.post("/api/projects", json={"nome": "Mio"}).status_code == 201


def test_the_live_channel_needs_a_login_too(tmp_path: Path, idp: FakeIdp) -> None:
    from starlette.websockets import WebSocketDisconnect

    with make_client(tmp_path, idp, "live") as client:
        log_in(client, idp, "carla")
        pid = client.post("/api/projects", json={"nome": "Dal vivo"}).json()["id"]
        with client.websocket_connect(f"/api/projects/{pid}/events") as ws:
            assert ws.receive_json()["type"] == "hello"
    with (
        make_client(tmp_path, idp, "live") as stranger, pytest.raises(WebSocketDisconnect),
        stranger.websocket_connect("/api/projects/dal-vivo/events") as ws,
    ):
        ws.receive_json()  # never reached: the handshake is refused
