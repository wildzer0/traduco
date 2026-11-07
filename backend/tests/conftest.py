from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<html>spa</html>")
    (d / "assets" / "a.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("secret")
    return d


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(frontend_dist=None))) as c:
        yield c


@pytest.fixture
def client_with_dist(dist: Path) -> Iterator[TestClient]:
    with TestClient(create_app(Settings(frontend_dist=dist))) as c:
        yield c


@pytest.fixture
def api(tmp_path: Path) -> Iterator[TestClient]:
    """App with an empty workspaces folder under ``tmp_path`` and the real example available."""
    ws = tmp_path / "workspaces"
    with TestClient(create_app(Settings(workspaces_dir=ws, frontend_dist=None))) as c:
        yield c
