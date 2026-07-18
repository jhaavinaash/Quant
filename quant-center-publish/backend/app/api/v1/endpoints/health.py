from fastapi import APIRouter, status

from app.schemas.health import SystemHealth
from app.services.health_service import HealthService

router = APIRouter()


@router.get("", response_model=SystemHealth, status_code=status.HTTP_200_OK)
async def get_system_health():
    """
    Returns operational status for core platform subsystems.
    """
    return await HealthService.get_system_health()
