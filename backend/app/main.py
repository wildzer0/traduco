"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.types import Scope

from app.api import (
    assets,
    capabilities,
    companion,
    diagrams,
    events,
    files,
    health,
    nodes,
    projects,
    skeleton,
    templates,
    translation,
)
from app.api import comments as comments_api
from app.api import export as export_api
from app.api import importer as importer_api
from app.api import issues as issues_api
from app.api import requirements as requirements_api
from app.api import settings as settings_api
from app.api import snippets as snippets_api
from app.api.deps import STATUS
from app.config import Settings, get_settings
from app.core.export.errors import ExportError
from app.core.export.service import ExportManager
from app.core.importer.service import ImportManager
from app.core.skeleton.model import SkeletonError
from app.core.translation.service import LlmConfig, TranslationService
from app.core.workspace.errors import WorkspaceError
from app.events import EventHub


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "details": {}}}, status_code=status
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        hub = EventHub()
        app.state.hub = hub
        saved = settings_api.effective(settings)
        service = TranslationService(
            LlmConfig(saved["llm_base_url"], saved["llm_model"], saved["llm_api_key"]),
            hub.publish,
        )
        app.state.translation = service
        service.set_gate(lambda: capabilities.model_download()["state"] == "downloading")
        exports = ExportManager(service, publish=hub.publish)
        app.state.exports = exports
        imports = ImportManager(service, publish=hub.publish)
        app.state.imports = imports
        service.start()
        yield
        await exports.close()
        await imports.close()
        await service.close()
        await hub.close()

    app = FastAPI(
        title="Traduco",
        version=settings.version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return _error(f"http_{exc.status_code}", str(exc.detail), exc.status_code)

    @app.exception_handler(WorkspaceError)
    async def workspace_error(_: Request, exc: WorkspaceError) -> JSONResponse:
        return _error(exc.code, exc.message, STATUS.get(exc.code, 400))

    @app.exception_handler(ExportError)
    async def export_error(_: Request, exc: ExportError) -> JSONResponse:
        status = {"not_ready": 409, "not_found": 404, "pandoc_missing": 503, "office_missing": 503}
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
            status_code=status.get(exc.code, 422),
        )

    @app.exception_handler(SkeletonError)
    async def skeleton_error(_: Request, exc: SkeletonError) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_skeleton",
                    "message": str(exc),
                    "details": {"line": exc.line, "reason": exc.reason},
                }
            },
            status_code=422,
        )

    @app.exception_handler(ValidationError)
    async def model_error(_: Request, exc: ValidationError) -> JSONResponse:
        first = exc.errors()[0]
        message = str(first.get("msg", "invalid data")).removeprefix("Value error, ")
        return _error("validation_error", message, 422)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return _error("validation_error", f"{where}: {first.get('msg', 'invalid request')}", 422)

    for router in (
        health.router,
        projects.router,
        nodes.router,
        files.router,
        assets.router,
        diagrams.router,
        companion.router,
        capabilities.router,
        settings_api.router,
        skeleton.router,
        templates.router,
        export_api.router,
        importer_api.router,
        issues_api.router,
        comments_api.router,
        requirements_api.router,
        snippets_api.router,
        translation.router,
        events.router,
    ):
        app.include_router(router, prefix="/api")

    dist = settings.frontend_dist
    if dist is not None and (dist / "index.html").is_file():
        _mount_frontend(app, dist)
    return app


class _HashedAssets(StaticFiles):
    """Files under /assets have the hash of their content in the name: they never change."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def _page(path: Path) -> FileResponse:
    # The page itself must be asked for again every time: after an update it names new asset files,
    # and a stale copy would look for chunks (such as the diagram engine) that no longer exist.
    return FileResponse(path, headers={"Cache-Control": "no-cache"})


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", _HashedAssets(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return _page(candidate)
        return _page(dist / "index.html")


app = create_app()
