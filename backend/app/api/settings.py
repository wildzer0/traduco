"""``/api/settings``: the model endpoint, saved by the user and applied without a restart."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core import settings_store
from app.core.translation.service import LlmConfig, TranslationService

router = APIRouter(tags=["settings"])


class SettingsPut(BaseModel):
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None


def effective(settings: Settings) -> dict[str, str]:
    saved = settings_store.load(settings.workspaces_path)
    return {
        "llm_base_url": saved.get("llm_base_url", settings.llm_base_url),
        "llm_model": saved.get("llm_model", settings.llm_model),
        "llm_api_key": saved.get("llm_api_key", settings.llm_api_key),
    }


def _public(values: dict[str, str]) -> dict[str, Any]:
    return {
        "llm_base_url": values["llm_base_url"],
        "llm_model": values["llm_model"],
        "has_api_key": bool(values["llm_api_key"]),
    }


@router.get("/settings")
def get_settings_view(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, Any]:
    return _public(effective(settings))


@router.put("/settings")
async def put_settings(
    body: SettingsPut, request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> dict[str, Any]:
    values: dict[str, Any] = body.model_dump()
    if values["llm_base_url"] is not None:
        values["llm_base_url"] = settings_store.validate_url(values["llm_base_url"])
    if values["llm_model"] is not None:
        values["llm_model"] = values["llm_model"].strip()
    settings_store.save(settings.workspaces_path, values)
    now = effective(settings)
    service: TranslationService = request.app.state.translation
    await service.reconfigure(LlmConfig(now["llm_base_url"], now["llm_model"], now["llm_api_key"]))
    return _public(now)
