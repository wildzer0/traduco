import sys
from collections.abc import Iterator
from pathlib import Path
from threading import Thread

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fake_llm.server import make_server  # noqa: E402


@pytest.fixture
def base_url() -> Iterator[str]:
    server = make_server("127.0.0.1", 0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()
