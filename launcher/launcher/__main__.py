"""Entry point: ``python -m launcher [options]`` (normally invoked by start.sh / start.cmd)."""

from __future__ import annotations

import argparse
import signal
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from launcher import steps
from launcher.manifest import load_manifest
from launcher.paths import Paths, default_root
from launcher.proc import Log
from launcher.run import serve
from launcher.state import State
from launcher.ui import UI, LauncherError


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="start", description="Install what is missing and start Traduco."
    )
    parser.add_argument(
        "--update", action="store_true", help="re-sync dependencies and rebuild the frontend"
    )
    parser.add_argument(
        "--model",
        metavar="TAG",
        help="Ollama model to use instead of the one chosen for this computer",
    )
    parser.add_argument(
        "--yes", action="store_true", help="answer yes to questions (install Ollama) without asking"
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="install everything, do not start (offline bundle)",
    )
    parser.add_argument(
        "--port", type=int, metavar="N", help="port to listen on (default: first free from 8000)"
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    parser.add_argument(
        "--offline", action="store_true", help="never download: fail if something is missing"
    )
    parser.add_argument(
        "--reset", action="store_true", help="recreate .runtime/ (projects are not touched)"
    )
    parser.add_argument(
        "--workspace", type=Path, metavar="DIR", help="folder with the projects (default ~/Traduco)"
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace, ui: UI, root: Path) -> int:
    paths = Paths(root)
    paths.ensure()
    log = Log(paths.logs / "launcher.log")
    ctx = steps.Context(
        paths=paths, manifest=load_manifest(root / "launcher" / "manifest.toml"),
        state=State(paths.state_file), ui=ui, log=log, offline=args.offline,
        update=args.update, port=args.port, workspace=args.workspace,
    )  # fmt: skip
    try:
        log.write(f"launcher start, args={sys.argv[1:]}")
        if args.reset:
            ui.info(ui.t("reset"))
            steps.reset_runtime(ctx)
            paths.ensure()
        ui.plan(9)

        ui.step("step.checks")
        port = steps.preflight(ctx)

        ui.step("step.backend")
        if not steps.backend_sync(ctx):
            ui.info(ui.t("done"))

        ui.step("step.pandoc")
        if not steps.ensure_pandoc(ctx):
            ui.info(ui.t("done"))

        ui.step("step.frontend")
        if steps.frontend_needs_build(ctx):
            steps.ensure_node(ctx)
            steps.build_frontend(ctx)
        else:
            ui.info(ui.t("done"))

        if args.prepare_only:
            ui.info(ui.t("prepared"))
            return 0

        ui.step("step.hardware")
        ctx.llm = steps.setup_llm(ctx, args.model, args.yes)  # also runs the Ollama and model steps

        ui.step("step.office")
        office = steps.find_libreoffice()
        ui.info(ui.t("office.found", path=office) if office else ui.t("office.absent"))

        ui.step("step.start")
        return serve(ctx, port, open_browser=not args.no_browser, office=office)
    except LauncherError as err:
        log.write(f"error {err.code} {err.params}")
        ui.error(err, log.path)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # last resort: never show a raw traceback to the user
        log.write(traceback.format_exc())
        ui.error(LauncherError("E099", what=f"{type(exc).__name__}: {exc}"), log.path)
        return 1
    finally:
        log.close()


def _raise_interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main(argv: Sequence[str] | None = None) -> int:
    # Treat SIGTERM (kill, CI) and Ctrl+Break (Windows) like Ctrl+C so the backend is stopped.
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if sig := getattr(signal, name, None):
            signal.signal(sig, _raise_interrupt)
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    return run(parse_args(argv), UI(), default_root())


if __name__ == "__main__":
    sys.exit(main())
