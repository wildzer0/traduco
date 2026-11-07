#!/usr/bin/env python3
"""Clean-start check used by CI (Linux and Windows): start script -> /api/health -> stop -> restart.

Asserts that the first start serves the frontend, and that the second start takes < 10 s
(docs/04-piano.md, M0 acceptance). Standard library only.
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

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = sys.platform == "win32"


def launch(port: int, log: Path) -> subprocess.Popen[bytes]:
    script = ["cmd", "/c", "start.cmd"] if WINDOWS else ["./start.sh"]
    cmd = [*script, "--no-browser", "--port", str(port)]
    out = log.open("wb")
    kwargs: dict[str, object] = {"cwd": ROOT, "stdout": out, "stderr": subprocess.STDOUT}
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


def dump_logs(*files: Path) -> None:
    for f in [*files, *sorted((ROOT / ".runtime" / "logs").glob("*.log"))]:
        if f.exists():
            print(f"\n===== {f} =====\n{f.read_text(errors='replace')[-4000:]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--first-timeout", type=float, default=900)
    parser.add_argument("--second-limit", type=float, default=10)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    tmp = Path(os.environ.get("RUNNER_TEMP", ROOT / ".runtime"))
    tmp.mkdir(parents=True, exist_ok=True)
    logs = [tmp / "first-start.log", tmp / "second-start.log"]
    try:
        proc = launch(args.port, logs[0])
        first = wait_up(base, proc, args.first_timeout)
        status, html = get(base + "/")
        assert status == 200 and '<div id="root">' in html, "frontend not served"
        print(f"first start healthy after {first:.1f}s")
        stop(proc)
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
    print("clean start OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
