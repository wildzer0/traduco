#!/usr/bin/env python3
"""Clean-start check used by CI (Linux and Windows): start script -> /api/health -> stop -> restart.

Asserts that the first start serves the frontend, and that the second start takes < 10 s
(docs/04-piano.md, M0 acceptance). A fake Ollama (tools/fake-llm) lets the first start also run the
detection, the model "download" and the capability report (M4b). ``--root`` runs the same check
on an unpacked offline bundle with ``--offline``. Standard library only.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO  # replaced by --root
WINDOWS = sys.platform == "win32"
EXTRA_ARGS: list[str] = []


def free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def start_fake_ollama(port: int) -> subprocess.Popen[bytes]:
    env = {**os.environ, "FAKE_LLM_PORT": str(port)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "fake_llm"], cwd=REPO / "tools" / "fake-llm", env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )  # fmt: skip
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if get(base + "/api/version")[0] == 200:
                return proc
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    proc.kill()
    raise SystemExit("the fake Ollama did not start")


def wait_for_model(base: str, timeout: float) -> dict[str, object]:
    """Poll /api/capabilities until the background download has finished."""
    import json

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        caps = json.loads(get(base + "/api/capabilities")[1])
        if caps["model"]["state"] == "ready":
            return caps  # type: ignore[no-any-return]
        if caps["model"]["state"] == "error":
            raise SystemExit(f"model download failed: {caps['model']}")
        time.sleep(0.3)
    raise SystemExit("the model never became ready")


TINY_NAME = "stories15M-test"
TINY_URL = "https://huggingface.co/ggml-org/stories15M_MOE/resolve/main/stories15M_MOE-Q8_0.gguf"
TINY_SHA = "c7aa6863f9a4b3cdf19716e2c95622dcbd3bd06989324bf1ac8e60486ef8e881"


def use_tiny_model() -> None:
    """Point the built-in engine at a 38 MB test model instead of the 2.8 GB Gemma (CI only)."""
    import re

    path = ROOT / "launcher" / "manifest.toml"
    text = path.read_text(encoding="utf-8")
    block = (
        f'[builtin.models.small]\nname = "{TINY_NAME}"\nurl = "{TINY_URL}"\n'
        f'sha256 = "{TINY_SHA}"\nsize_gb = 1\n'
    )
    text, count = re.subn(r"\[builtin\.models\.small\]\n(?:[^\[]*?\n)*?(?=\[|\Z)", block, text)
    assert count == 1, "builtin.models.small not found in manifest.toml"
    path.write_text(text, encoding="utf-8")


def check_builtin(base: str) -> None:
    """The backend must reach the engine with its key, and the engine must stop with the app."""
    import json

    status = json.loads(get(base + "/api/llm/status")[1])
    assert status["online"] is True and status["model"] == TINY_NAME, status
    print(f"built-in engine answers through the backend: {status}")


def launch(port: int, log: Path) -> subprocess.Popen[bytes]:
    script = ["cmd", "/c", "start.cmd"] if WINDOWS else ["./start.sh"]
    cmd = [*script, "--no-browser", "--port", str(port), *EXTRA_ARGS]
    out = log.open("wb")
    kwargs: dict[str, object] = {
        "cwd": ROOT,
        "stdin": subprocess.DEVNULL,  # start.cmd calls `pause` on errors: never wait for a key
        "stdout": out,
        "stderr": subprocess.STDOUT,
    }
    if WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)  # type: ignore[call-overload]


def get(url: str) -> tuple[int, str]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=3) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def wait_up(base: str, proc: subprocess.Popen[bytes], timeout: float) -> float:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if proc.poll() is not None:
            raise SystemExit(f"launcher exited early with code {proc.returncode}")
        try:
            if get(f"{base}/api/health")[0] == 200:
                return time.monotonic() - start
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.25)
    raise SystemExit(f"backend not healthy after {timeout:.0f}s")


def stop(proc: subprocess.Popen[bytes]) -> None:
    if WINDOWS:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], check=False,
                       capture_output=True)  # fmt: skip
    else:
        os.killpg(proc.pid, signal.SIGINT)  # what Ctrl+C does in a terminal
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def engine_listening() -> bool:
    import socket

    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", 18434)) == 0


def dump_logs(*files: Path) -> None:
    for f in [*files, *sorted((ROOT / ".runtime" / "logs").glob("*.log"))]:
        if f.exists():
            print(f"\n===== {f} =====\n{f.read_text(errors='replace')[-4000:]}")


def main() -> int:
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, help="unpacked offline bundle to start instead of the repository"
    )
    parser.add_argument(
        "--builtin",
        action="store_true",
        help="check the built-in llama.cpp engine (real llama-server, tiny model) instead of Ollama",
    )
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--first-timeout", type=float, default=900)
    parser.add_argument("--second-limit", type=float, default=10)
    args = parser.parse_args()
    if args.root:
        ROOT = args.root.resolve()
        # an offline start downloads nothing: Ollama must already have the model
        EXTRA_ARGS.extend(["--offline", "--model", "gemma4:e4b"])
    base = f"http://127.0.0.1:{args.port}"
    if args.builtin:
        use_tiny_model()
        EXTRA_ARGS.extend(["--llm", "builtin", "--yes"])
    ollama_port = free_port()
    os.environ["TRADUCO_OLLAMA_HOST"] = f"http://127.0.0.1:{ollama_port}"
    fake = None if args.builtin else start_fake_ollama(ollama_port)
    if args.root and fake is not None:
        pull = urllib.request.Request(
            f"http://127.0.0.1:{ollama_port}/api/pull",
            data=b'{"model": "gemma4:e4b"}',
            method="POST",
        )
        urllib.request.urlopen(pull, timeout=10).read()  # noqa: S310 - loopback
    tmp = Path(os.environ.get("RUNNER_TEMP", ROOT / ".runtime"))
    tmp.mkdir(parents=True, exist_ok=True)
    logs = [tmp / "first-start.log", tmp / "second-start.log"]
    try:
        proc = launch(args.port, logs[0])
        first = wait_up(base, proc, args.first_timeout)
        status, html = get(base + "/")
        assert status == 200 and '<div id="root">' in html, "frontend not served"
        print(f"first start healthy after {first:.1f}s")
        caps = wait_for_model(base, 600 if args.builtin else 60)
        assert caps["pandoc"]["available"], "Pandoc was not installed"  # type: ignore[index]
        print(f"model ready, capabilities: {caps}")
        if args.builtin:
            check_builtin(base)
        stop(proc)
        if args.builtin:
            time.sleep(2)
            assert not engine_listening(), "llama-server kept running after the app stopped"
        time.sleep(2)

        proc = launch(args.port, logs[1])
        second = wait_up(base, proc, args.second_limit * 3)
        print(f"second start healthy after {second:.1f}s")
        assert second < args.second_limit, (
            f"second start took {second:.1f}s (limit {args.second_limit}s)"
        )
        stop(proc)
    except BaseException:
        dump_logs(*logs)
        raise
    finally:
        if fake is not None:
            fake.kill()
    print("clean start OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
