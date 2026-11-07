from __future__ import annotations

import shutil
import socket
import sys
from pathlib import Path

import pytest

from launcher import steps
from launcher.manifest import load_manifest
from launcher.paths import Paths
from launcher.proc import Log
from launcher.state import State, hash_files, hash_tree
from launcher.ui import UI, LauncherError

REPO = Path(__file__).resolve().parents[2]


def make_ctx(tmp_path: Path, **kw: object) -> steps.Context:
    paths = Paths(tmp_path)
    paths.ensure()
    return steps.Context(
        paths=paths, manifest=load_manifest(REPO / "launcher" / "manifest.toml"),
        state=State(paths.state_file), ui=UI("en"), log=Log(paths.logs / "l.log"), **kw,  # type: ignore[arg-type]
    )  # fmt: skip


def test_select_port_skips_busy_ports() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        busy = s.getsockname()[1]
        assert steps.select_port(None, (busy, busy + 20)) != busy


def test_requested_busy_port_is_an_error() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        with pytest.raises(LauncherError) as e:
            steps.select_port(s.getsockname()[1], (8000, 8100))
    assert e.value.code == "E003"


def test_no_free_port_in_range() -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        busy = s.getsockname()[1]
        with pytest.raises(LauncherError) as e:
            steps.select_port(None, (busy, busy))
    assert e.value.code == "E004"


def test_disk_space_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_ctx(tmp_path)
    monkeypatch.setattr(
        steps.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(10, 10, 10 * 1024**2)
    )
    with pytest.raises(LauncherError) as e:
        steps.check_disk(ctx)
    assert e.value.code == "E002"
    message, fix = e.value.render("it")
    assert "GB" in message and fix


def test_state_roundtrip_and_corruption(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    State(path).set("a", "1")
    assert State(path).get("a") == "1"
    path.write_text("{not json")
    assert State(path).get("a") is None


def test_hashes_change_with_content(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.ts").write_text("1")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x").write_text("ignored")
    before = hash_tree(tmp_path)
    (tmp_path / "node_modules" / "x").write_text("still ignored")
    assert hash_tree(tmp_path) == before
    (tmp_path / "src" / "a.ts").write_text("2")
    assert hash_tree(tmp_path) != before
    assert hash_files([tmp_path / "missing"]) == hash_files([])


def test_frontend_build_rules(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "a.ts").write_text("1")
    assert steps.frontend_needs_build(ctx)  # no dist yet
    (tmp_path / "frontend" / "dist").mkdir()
    (tmp_path / "frontend" / "dist" / "index.html").write_text("x")
    ctx.state.set("frontend", steps.frontend_digest(ctx))
    assert not steps.frontend_needs_build(ctx)  # up to date: second start skips the build
    (tmp_path / "frontend" / "src" / "a.ts").write_text("2")
    assert steps.frontend_needs_build(ctx)
    ctx.state.set("frontend", steps.frontend_digest(ctx))
    ctx.update = True
    assert steps.frontend_needs_build(ctx)


def test_release_package_uses_prebuilt_dist(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "dist" / "index.html").write_text("x")
    assert not steps.frontend_needs_build(ctx)


def test_backend_sync_is_skipped_when_inputs_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = make_ctx(tmp_path)
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "uv.lock").write_text("lock")
    calls: list[list[str]] = []

    class Done:
        returncode = 0

    monkeypatch.setattr(steps, "uv_executable", lambda: "uv")
    monkeypatch.setattr(steps, "run_logged", lambda cmd, **_: calls.append(list(cmd)) or Done())
    ctx.paths.backend_python.parent.mkdir(parents=True)
    ctx.paths.backend_python.write_text("")
    assert steps.backend_sync(ctx) is True
    assert "--frozen" in calls[0] and "--no-dev" in calls[0] and "--inexact" in calls[0]
    assert steps.backend_sync(ctx) is False and len(calls) == 1
    (tmp_path / "backend" / "uv.lock").write_text("changed")
    assert steps.backend_sync(ctx) is True


def test_backend_sync_failure_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_ctx(tmp_path)

    class Fail:
        returncode = 1

    monkeypatch.setattr(steps, "uv_executable", lambda: "uv")
    monkeypatch.setattr(steps, "run_logged", lambda *_a, **_k: Fail())
    with pytest.raises(LauncherError) as e:
        steps.backend_sync(ctx)
    assert e.value.code == "E020"


def test_reset_keeps_projects_and_clears_state(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    (ctx.paths.node).mkdir()
    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    ctx.state.set("node", "1")
    projects = tmp_path / "projects"
    projects.mkdir()
    steps.reset_runtime(ctx)
    assert not ctx.paths.node.exists() and not ctx.paths.dist.exists()
    assert not ctx.paths.state_file.exists() and projects.exists()


def test_backend_env_does_not_inherit_the_launcher_venv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/somewhere/launcher-venv")
    ctx = make_ctx(tmp_path)
    env = steps.child_env(ctx)
    assert env["UV_PROJECT_ENVIRONMENT"] == str(tmp_path / "backend" / ".venv")
    assert env["UV_CACHE_DIR"].startswith(str(tmp_path / ".runtime"))


@pytest.mark.skipif(sys.platform == "win32", reason="TIME_WAIT semantics differ on Windows")
def test_port_in_time_wait_counts_as_free() -> None:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    client = socket.create_connection(("127.0.0.1", port))
    server_side, _ = listener.accept()
    server_side.close()  # active close on the server side leaves the port in TIME_WAIT
    client.close()
    listener.close()
    assert steps.is_port_free(port)
