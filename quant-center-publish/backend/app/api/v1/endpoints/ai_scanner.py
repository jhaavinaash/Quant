from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.ai_scanner import (
    AIScannerActionResult,
    AIScannerSnapshot,
    AddPaperTradeRequest,
    ExitPaperTradeRequest,
)
from app.services.ai_scanner_service import AIScannerService

router = APIRouter()


@router.get("", response_model=AIScannerSnapshot, status_code=status.HTTP_200_OK)
async def get_ai_scanner_snapshot(
    current_user: User = Depends(get_current_user),
) -> AIScannerSnapshot:
    return AIScannerService.get_snapshot()


@router.post("/rescan", response_model=AIScannerSnapshot, status_code=status.HTTP_200_OK)
async def rescan_ai_scanner(
    current_user: User = Depends(get_current_user),
) -> AIScannerSnapshot:
    return AIScannerService.rescan()


@router.post("/paper-trades", response_model=AIScannerActionResult, status_code=status.HTTP_200_OK)
async def add_paper_trade(
    body: AddPaperTradeRequest,
    current_user: User = Depends(get_current_user),
) -> AIScannerActionResult:
    return AIScannerService.add_paper_trade(body)


@router.post(
    "/paper-trades/{ticker}/exit",
    response_model=AIScannerActionResult,
    status_code=status.HTTP_200_OK,
)
async def exit_paper_trade(
    ticker: str,
    body: ExitPaperTradeRequest,
    current_user: User = Depends(get_current_user),
) -> AIScannerActionResult:
    return AIScannerService.exit_paper_trade(ticker, body)
