from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.trades import TradesSnapshot
from app.services.trades_service import TradesService

router = APIRouter()


@router.get("", response_model=TradesSnapshot, status_code=status.HTTP_200_OK)
async def get_trades_snapshot(
    current_user: User = Depends(get_current_user),
) -> TradesSnapshot:
    return TradesService.get_snapshot()
