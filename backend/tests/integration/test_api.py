from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "0.1.0"}


def test_unknown_api_route_uses_error_format(client_with_dist: TestClient) -> None:
    r = client_with_dist.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "http_404"


def test_frontend_served_with_spa_fallback(client_with_dist: TestClient) -> None:
    assert client_with_dist.get("/").text == "<html>spa</html>"
    assert client_with_dist.get("/some/route").text == "<html>spa</html>"
    assert client_with_dist.get("/assets/a.js").text == "console.log(1)"


def test_path_traversal_does_not_leak(client_with_dist: TestClient) -> None:
    r = client_with_dist.get("/..%2Fsecret.txt")
    assert "secret" not in r.text


def test_no_frontend_when_dist_missing(client: TestClient) -> None:
    assert client.get("/").status_code == 404


def test_the_page_is_never_cached_but_hashed_assets_are(client_with_dist: TestClient) -> None:
    """A stale index.html asks for chunks that an update removed (seen as "invalid diagram")."""
    page = client_with_dist.get("/")
    assert page.headers["cache-control"] == "no-cache"
    assert client_with_dist.get("/some/route").headers["cache-control"] == "no-cache"
    asset = client_with_dist.get("/assets/a.js")
    assert asset.status_code == 200
    assert (
        "immutable" in asset.headers["cache-control"]
        and "max-age=31536000" in asset.headers["cache-control"]
    )
