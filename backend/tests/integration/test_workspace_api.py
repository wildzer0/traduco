from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def make_project(api: TestClient, nome: str = "Manuale") -> str:
    r = api.post("/api/projects", json={"nome": nome})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def node(api: TestClient, pid: str, kind: str, title: str, parent: str | None = None) -> str:
    r = api.post(
        f"/api/projects/{pid}/nodes", json={"kind": kind, "title": title, "parent": parent}
    )
    assert r.status_code == 201, r.text
    return str(r.json()["path"])


def ws(api: TestClient) -> Path:
    settings: Settings = api.app.dependency_overrides[get_settings]()  # type: ignore[attr-defined]
    return settings.workspaces_path


# --- projects --------------------------------------------------------------------------------


def test_create_list_and_get_project(api: TestClient) -> None:
    assert api.get("/api/projects").json() == []
    pid = make_project(api)
    assert pid == "manuale"
    assert api.get("/api/projects").json() == [
        {"id": "manuale", "nome": "Manuale", "lingua_sorgente": "it", "lingua_ufficiale": "en"}
    ]
    body = api.get(f"/api/projects/{pid}").json()
    assert body["nome"] == "Manuale" and body["tono"] == "formale"


def test_create_from_example(api: TestClient) -> None:
    r = api.post("/api/projects", json={"esempio": True})
    assert r.status_code == 201 and r.json()["id"] == "progetto-esempio"
    titles = [n["title"] for n in api.get("/api/projects/progetto-esempio/tree").json()["nodes"]]
    assert titles == ["Introduzione", "Installazione"]


def test_patch_project_changes_only_sent_keys_and_validates(api: TestClient) -> None:
    pid = make_project(api)
    r = api.patch(f"/api/projects/{pid}", json={"tono": "neutro", "metadati": {"cliente": "ACME"}})
    assert r.status_code == 200 and r.json()["tono"] == "neutro"
    assert api.get(f"/api/projects/{pid}").json()["lingua_sorgente"] == "it"
    bad = api.patch(f"/api/projects/{pid}", json={"lingua_ufficiale": "it"})
    assert bad.status_code == 422


def test_unknown_project_and_hostile_ids(api: TestClient) -> None:
    assert api.get("/api/projects/nope").status_code == 404
    assert api.get("/api/projects/..%2F..%2Fetc/tree").status_code in (400, 404)
    err = api.get("/api/projects/nope").json()["error"]
    assert err["code"] == "not_found" and "message" in err and err["details"] == {}


def test_create_requires_a_name(api: TestClient) -> None:
    assert api.post("/api/projects", json={}).status_code == 400
    assert api.post("/api/projects", json={"nome": ""}).status_code == 422


# --- acceptance flow: 1 project, 2 chapters, 3 sections ---------------------------------------


def test_structure_on_disk_matches_what_the_ui_does(api: TestClient) -> None:
    pid = make_project(api)
    a = node(api, pid, "chapter", "Introduzione")
    b = node(api, pid, "chapter", "Installazione")
    node(api, pid, "section", "Scopo", a)
    node(api, pid, "section", "Ambito", a)
    node(api, pid, "section", "Requisiti", b)
    root = ws(api) / pid
    on_disk = sorted(
        p.relative_to(root).as_posix() for p in (root / "capitoli").rglob("*") if p.is_file()
    )
    assert on_disk == [
        "capitoli/01-introduzione/01-scopo.md",
        "capitoli/01-introduzione/02-ambito.md",
        "capitoli/01-introduzione/_capitolo.yaml",
        "capitoli/02-installazione/01-requisiti.md",
        "capitoli/02-installazione/_capitolo.yaml",
    ]
    tree = api.get(f"/api/projects/{pid}/tree").json()["nodes"]
    assert [(n["title"], [c["title"] for c in n["children"]]) for n in tree] == [
        ("Introduzione", ["Scopo", "Ambito"]),
        ("Installazione", ["Requisiti"]),
    ]


def test_reorder_rename_move_delete(api: TestClient) -> None:
    pid = make_project(api)
    a = node(api, pid, "chapter", "A")
    b = node(api, pid, "chapter", "B")
    s1 = node(api, pid, "section", "Uno", a)
    node(api, pid, "section", "Due", a)
    url = f"/api/projects/{pid}/nodes"

    r = api.patch(url, json={"parent": a, "order": ["02-due.md", "01-uno.md"]})
    assert r.status_code == 200 and r.json()["renamed"][s1] == f"{a}/02-uno.md"

    r = api.patch(url, json={"path": f"{a}/02-uno.md", "title": "Primo"})
    assert r.json()["path"] == f"{a}/02-primo.md"

    r = api.patch(url, json={"path": f"{a}/02-primo.md", "move": True, "parent": b, "index": 0})
    assert r.json()["path"] == f"{b}/01-primo.md"

    r = api.delete(url, params={"path": b})
    assert r.status_code == 200 and r.json()["trash"].startswith(".traduco/cestino/")
    assert [n["name"] for n in api.get(f"/api/projects/{pid}/tree").json()["nodes"]] == ["01-a"]


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"path": "capitoli/09-x", "title": "T"}, 404, "not_found"),
        ({"path": "../progetto.yaml", "title": "T"}, 400, "invalid_path"),
        ({"order": ["x"], "parent": None}, 422, "invalid_order"),
        ({}, 400, "invalid_path"),
        ({"path": "capitoli/01-a"}, 400, "invalid_path"),
    ],
)
def test_node_errors_use_the_standard_format(
    api: TestClient, body: dict[str, object], status: int, code: str
) -> None:
    pid = make_project(api)
    node(api, pid, "chapter", "A")
    r = api.patch(f"/api/projects/{pid}/nodes", json=body)
    assert (r.status_code, r.json()["error"]["code"]) == (status, code)


def test_delete_outside_chapters_is_refused(api: TestClient) -> None:
    pid = make_project(api)
    r = api.delete(f"/api/projects/{pid}/nodes", params={"path": "progetto.yaml"})
    assert r.status_code == 400 and (ws(api) / pid / "progetto.yaml").exists()


def test_depth_limit_through_the_api(api: TestClient) -> None:
    pid = make_project(api)
    p = node(api, pid, "chapter", "A")
    p = node(api, pid, "chapter", "B", p)
    p = node(api, pid, "chapter", "C", p)
    r = api.post(f"/api/projects/{pid}/nodes", json={"kind": "chapter", "title": "D", "parent": p})
    assert r.status_code == 422 and r.json()["error"]["code"] == "depth_exceeded"


# --- files and conflicts ---------------------------------------------------------------------


def test_read_save_and_etag(api: TestClient) -> None:
    pid = make_project(api)
    sec = node(api, pid, "section", "S", node(api, pid, "chapter", "A"))
    url = f"/api/projects/{pid}/files"
    r = api.get(url, params={"path": sec})
    h0 = r.json()["hash"]
    assert r.headers["etag"] == f'"{h0}"'

    r = api.put(
        url, params={"path": sec}, json={"content": "# Ciao\n"}, headers={"If-Match": f'"{h0}"'}
    )
    assert r.status_code == 200
    h1 = r.json()["hash"]
    assert h1 != h0 and api.get(url, params={"path": sec}).json()["content"] == "# Ciao\n"


def test_save_without_if_match_is_refused(api: TestClient) -> None:
    pid = make_project(api)
    sec = node(api, pid, "section", "S", node(api, pid, "chapter", "A"))
    r = api.put(f"/api/projects/{pid}/files", params={"path": sec}, json={"content": "x"})
    assert r.status_code == 428 and r.json()["error"]["code"] == "precondition_required"


def test_external_edit_causes_409_and_is_not_overwritten(api: TestClient) -> None:
    pid = make_project(api)
    sec = node(api, pid, "section", "S", node(api, pid, "chapter", "A"))
    url = f"/api/projects/{pid}/files"
    h0 = api.get(url, params={"path": sec}).json()["hash"]
    (ws(api) / pid / sec).write_text("scritto da un altro editor\n", encoding="utf-8")
    r = api.put(url, params={"path": sec}, json={"content": "mia"}, headers={"If-Match": h0})
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "conflict" and err["details"]["current_hash"].startswith("sha256:")
    assert (ws(api) / pid / sec).read_text(encoding="utf-8") == "scritto da un altro editor\n"
    # retrying with the hash from the conflict response succeeds
    again = api.put(url, params={"path": sec}, json={"content": "unita"},
                    headers={"If-Match": err["details"]["current_hash"]})  # fmt: skip
    assert again.status_code == 200


def test_files_endpoint_is_limited_to_sections(api: TestClient) -> None:
    pid = make_project(api)
    for bad in ("progetto.yaml", "../x.md", "capitoli"):
        assert api.get(f"/api/projects/{pid}/files", params={"path": bad}).status_code in (400, 404)


# --- assets ----------------------------------------------------------------------------------


def test_upload_and_serve_image(api: TestClient) -> None:
    pid = make_project(api)
    sec = node(api, pid, "section", "S", node(api, pid, "chapter", "A"))
    r = api.post(
        f"/api/projects/{pid}/assets",
        params={"section": sec, "filename": "Schema.PNG"},
        content=PNG,
    )
    assert r.status_code == 201
    assert r.json() == {"path": "capitoli/01-a/img/schema.png", "markdown": "img/schema.png"}
    assert (ws(api) / pid / "capitoli/01-a/img/schema.png").read_bytes() == PNG

    got = api.get(f"/api/projects/{pid}/assets", params={"path": r.json()["path"]})
    assert (
        got.status_code == 200 and got.content == PNG and got.headers["content-type"] == "image/png"
    )
    assert "sandbox" in got.headers["content-security-policy"]


def test_upload_rejects_non_images_and_serving_is_limited_to_img(api: TestClient) -> None:
    pid = make_project(api)
    sec = node(api, pid, "section", "S", node(api, pid, "chapter", "A"))
    r = api.post(
        f"/api/projects/{pid}/assets",
        params={"section": sec, "filename": "x.png"},
        content=b"not an image",
    )
    assert r.status_code == 415
    for bad in (
        "capitoli/01-a/01-s.md",
        "progetto.yaml",
        "capitoli/01-a/img/../01-s.md",
        "capitoli/01-a/img/nope.png",
    ):
        assert api.get(f"/api/projects/{pid}/assets", params={"path": bad}).status_code in (
            400,
            404,
        )
