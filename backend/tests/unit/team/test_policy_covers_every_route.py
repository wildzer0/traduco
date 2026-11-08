"""No endpoint that changes something may be left out of the permission table (ADR-046)."""

from pathlib import Path

from app.config import Settings
from app.core.team import policy
from app.core.team.identity import PERMISSIONS
from app.main import create_app


def test_every_route_that_writes_is_classified_and_nothing_stale_is_listed(tmp_path: Path) -> None:
    app = create_app(Settings(workspaces_dir=tmp_path, frontend_dist=None))
    written = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method.upper() != "GET"
    }
    missing = sorted(written - set(policy.ROUTES))
    assert not missing, f"no permission decided for: {missing}"
    stale = sorted(set(policy.ROUTES) - written)
    assert not stale, f"listed but no such route: {stale}"
    assert set(policy.ROUTES.values()) <= set(PERMISSIONS)
