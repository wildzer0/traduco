from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas.health import Health

router = APIRouter()


@router.get("/health", response_model=Health)
def health(settings: Settings = Depends(get_settings)) -> Health:
    return Health(status="ok", version=settings.version)
