from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.trade_entry import (
    TradeEntryActionResult,
    TradeEntryAddRequest,
    TradeEntryCloseRequest,
    TradeEntryEditRequest,
    TradeEntrySnapshot,
)
from app.services.trade_entry_service import TradeEntryService

router = APIRouter()


@router.get("", response_model=TradeEntrySnapshot, status_code=status.HTTP_200_OK)
async def get_trade_entry_snapshot(
    current_user: User = Depends(get_current_user),
) -> TradeEntrySnapshot:
    return TradeEntryService.get_snapshot()


@router.delete("/pending-deploy", response_model=TradeEntryActionResult, status_code=status.HTTP_200_OK)
async def discard_pending_deploy(
    current_user: User = Depends(get_current_user),
) -> TradeEntryActionResult:
    return TradeEntryService.discard_pending_deploy()


@router.post("", response_model=TradeEntryActionResult, status_code=status.HTTP_200_OK)
async def add_trade_entry(
    body: TradeEntryAddRequest,
    current_user: User = Depends(get_current_user),
) -> TradeEntryActionResult:
    return TradeEntryService.add_trade(body)


@router.put("/{row_index}", response_model=TradeEntryActionResult, status_code=status.HTTP_200_OK)
async def edit_trade_entry(
    row_index: int,
    body: TradeEntryEditRequest,
    current_user: User = Depends(get_current_user),
) -> TradeEntryActionResult:
    return TradeEntryService.edit_trade(row_index, body)


@router.post("/{row_index}/close", response_model=TradeEntryActionResult, status_code=status.HTTP_200_OK)
async def manual_close_trade_entry(
    row_index: int,
    body: TradeEntryCloseRequest,
    current_user: User = Depends(get_current_user),
) -> TradeEntryActionResult:
    """Manual journal close — not broker-backed. See Positions → Exit for SELL pipeline."""
    return TradeEntryService.close_trade(row_index, body)


@router.delete("/{row_index}", response_model=TradeEntryActionResult, status_code=status.HTTP_200_OK)
async def delete_trade_entry(
    row_index: int,
    current_user: User = Depends(get_current_user),
) -> TradeEntryActionResult:
    return TradeEntryService.delete_trade(row_index)
