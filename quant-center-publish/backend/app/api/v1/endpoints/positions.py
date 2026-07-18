from typing import List

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.position import PositionExitRequest, PositionExitResult, PositionResponse
from app.services.position_exit_actions_service import PositionExitActionsService
from app.services.position_service import PositionService

router = APIRouter()


@router.get("", response_model=List[PositionResponse], status_code=status.HTTP_200_OK)
async def get_positions(current_user: User = Depends(get_current_user)):
    """
    Returns open positions from the canonical orchestrator snapshot.
    """
    return PositionService.get_open_positions()


@router.post(
    "/{trade_key:path}/exit",
    response_model=PositionExitResult,
    status_code=status.HTTP_200_OK,
)
async def request_position_exit(
    trade_key: str,
    body: PositionExitRequest,
    current_user: User = Depends(get_current_user),
) -> PositionExitResult:
    """Submit broker SELL exit for one exact OPEN trade (requires Zerodha CONNECTED)."""
    return PositionExitActionsService.request_exit(trade_key, body.exitReason)


@router.post("/sync", response_model=PositionExitResult, status_code=status.HTTP_200_OK)
async def sync_position_exits(
    force: bool = Query(False, description="Re-check PENDING exit orders at broker"),
    current_user: User = Depends(get_current_user),
) -> PositionExitResult:
    """Reconcile exit fills via production OrderStatusSync."""
    return PositionExitActionsService.sync_exits(force=force)
