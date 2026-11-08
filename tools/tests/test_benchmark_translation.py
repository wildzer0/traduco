import importlib.util
import socket
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "fake-llm"))
from fake_llm.server import make_server  # noqa: E402


def load(name: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), TOOLS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def running(tmp_path: Path) -> Iterator[str]:
    import uvicorn

    from app.config import Settings
    from app.main import create_app

    load("make-big-project").build(tmp_path / "ws" / "prova", 17, seed=1)
    fake = make_server("127.0.0.1", free_port())
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    settings = Settings(
        workspaces_dir=tmp_path / "ws",
        frontend_dist=None,
        llm_base_url=f"http://127.0.0.1:{fake.server_address[1]}/v1",
        llm_model="fake-model",
    )
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(5)
    fake.shutdown()


def test_the_report_tells_speed_outcome_and_the_instruction_check(
    running: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bench = load("benchmark-translation")
    out = tmp_path / "report.md"
    code = bench.main(
        [
            "--url",
            running,
            "--project",
            "prova",
            "--every",
            "0.2",
            "--sample",
            "3",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    text = out.read_text()
    assert "# Translation benchmark" in text and "`fake-model`" in text
    assert "segments/s" in text and "| translated |" in text or "| needs_review |" in text
    assert (
        "Instruction box" in text
        and "legitimate rewrite" in text
        and "request for new content" in text
    )
    assert "Random sample to read" in text and "> " in text


def test_it_stops_politely_when_nothing_answers(capsys: pytest.CaptureFixture[str]) -> None:
    bench = load("benchmark-translation")
    assert bench.main(["--url", f"http://127.0.0.1:{free_port()}", "--project", "x"]) == 1
