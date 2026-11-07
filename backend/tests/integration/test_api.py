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
