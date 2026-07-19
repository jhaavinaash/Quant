"""Read-only Market Briefing endpoint."""

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.market_briefing import MarketBriefingSnapshot
from app.services.market_briefing_service import MarketBriefingService

router = APIRouter()


@router.get("", response_model=MarketBriefingSnapshot, status_code=status.HTTP_200_OK)
def get_market_briefing(
    refresh: bool = Query(default=False),
) -> MarketBriefingSnapshot:
    try:
        return MarketBriefingService.get_snapshot(refresh=refresh)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Market Briefing is unavailable: {exc}",
        ) from exc
