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


@pytest.fixture(scope="session")
def company_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A realistic Italian company template (see tests/support/template_factory.py)."""
    from tests.support.template_factory import build_company_template

    return build_company_template(tmp_path_factory.mktemp("tpl") / "manuale.docx")


@pytest.fixture(scope="session")
def pandoc_bin() -> Path:
    """Pandoc for the export tests. Skipped when missing, except in CI (TRADUCO_REQUIRE_TOOLS=1)."""
    import os

    from app.core.export.errors import ExportError
    from app.core.export.pandoc import find_pandoc

    try:
        return find_pandoc()
    except ExportError:
        if os.environ.get("TRADUCO_REQUIRE_TOOLS"):
            raise
        pytest.skip("Pandoc is not installed (set TRADUCO_PANDOC or use .runtime/pandoc)")


@pytest.fixture(scope="session")
def soffice_bin() -> Path:
    """LibreOffice for the PDF check; skipped when missing, except in CI."""
    import os

    from app.core.export.office import find_soffice

    found = find_soffice()
    if found is None:
        if os.environ.get("TRADUCO_REQUIRE_TOOLS"):
            pytest.fail("LibreOffice is required in CI")
        pytest.skip("LibreOffice is not installed (set TRADUCO_SOFFICE)")
    return found
