from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, get_current_superuser
from app.models.user import User
from app.services.instrument import InstrumentService
from app.schemas.instrument import (
    InstrumentCreate, 
    InstrumentSearchFilter, 
    InstrumentPaginatedResponse
)

router = APIRouter()


@router.post("/bulk-sync", status_code=status.HTTP_200_OK)
async def bulk_synchronize_instruments(
    instruments_in: List[InstrumentCreate],
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_superuser)  # CRITICAL PROTECTION LAYER: Enforces administrative boundaries
):
    """
    Administrative data ingest channel.
    Accepts bulk contract definitions from exchange master dumps or broker files,
    executing a high-performance upsert logic vector to synchronize the core master.
    
    Protected via superuser role gate to isolate infrastructure updates from normal operator actions.
    """
    records_upserted = await InstrumentService.bulk_upsert(db, instruments_in=instruments_in)
    return {"status": "success", "synced_records": records_upserted}


@router.get("/", response_model=InstrumentPaginatedResponse)
async def search_instruments(
    q: str = Query(None, description="Wildcard search text for symbol or trading_symbol matching"),
    exchange: str = Query(None, description="Target execution exchange filter (e.g., NSE, NASDAQ)"),
    segment: str = Query(None, description="Target market tracking segment (e.g., NSE_EQ, NFO_OPT)"),
    asset_type: str = Query(None, description="Asset class identifier (e.g., EQUITY, OPTION)"),
    sort_by: str = Query("trading_symbol", description="Target ordering property"),
    sort_order: str = Query("asc", description="Sorting sequence sequence (asc/desc)"),
    page: int = Query(1, ge=1, description="Target grid data pagination page matrix index"),
    size: int = Query(50, ge=1, le=100, description="Data volume boundary limit per query load"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Safe for any logged-in trader or terminal workspace to call
):
    """
    Exposes high-speed instrument master querying parameters to client UI terminals, 
    order-entry tickets, or downstream algorithmic option scanners.
    """
    search_filter = InstrumentSearchFilter(
        q=q,
        exchange=exchange,
        segment=segment,
        asset_type=asset_type,
        sort_by=sort_by,
        sort_order=sort_order,
        is_active=True
    )
    
    items, total_count = await InstrumentService.search(
        db, 
        filters=search_filter, 
        page=page, 
        size=size
    )
    
    return InstrumentPaginatedResponse(
        items=items,
        total_count=total_count,
        page=page,
        size=size
    )