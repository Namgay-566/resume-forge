from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.environment)
