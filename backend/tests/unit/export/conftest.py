from pathlib import Path

import pytest

from tests.support.template_factory import logo_png


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project folder with the image the sample sections refer to."""
    (tmp_path / "capitoli/01-intro/img").mkdir(parents=True)
    logo_png(tmp_path / "capitoli/01-intro/img/schema.png", 300, 120, (180, 60, 60))
    return tmp_path
