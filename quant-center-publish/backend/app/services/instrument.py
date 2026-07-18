from typing import List, Tuple
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.instrument import Instrument
from app.schemas.instrument import InstrumentCreate, InstrumentSearchFilter

logger = structlog.get_logger()


class InstrumentService:
    """
    High-performance business logic layer for the global Instrument Master.
    
    Optimized to safely process bulk data streams (e.g., daily exchange contract listings)
    and execute low-latency wildcard queries across global symbols.
    """

    @staticmethod
    async def bulk_upsert(db: AsyncSession, instruments_in: List[InstrumentCreate]) -> int:
        """
        Executes a high-performance bulk upsert pattern against incoming contract feeds.
        Utilizes database-native ON CONFLICT mechanisms to run updates efficiently.
        """
        if not instruments_in:
            return 0

        # Transform Pydantic representations into raw dictionary structures for database compilation
        payloads = [obj.model_dump() for obj in instruments_in]
        
        # Build a robust compilation statement targetting our unique constraint structure
        stmt = pg_insert(Instrument).values(payloads)
        
        update_dict = {
            "symbol": stmt.excluded.symbol,
            "segment": stmt.excluded.segment,  # Ensures structural updates propagate dynamically
            "instrument_token": stmt.excluded.instrument_token,
            "isin": stmt.excluded.isin,
            "asset_type": stmt.excluded.asset_type,
            "expiry": stmt.excluded.expiry,
            "strike": stmt.excluded.strike,
            "option_type": stmt.excluded.option_type,
            "tick_size": stmt.excluded.tick_size,
            "lot_size": stmt.excluded.lot_size,
            "currency": stmt.excluded.currency,
            "is_active": stmt.excluded.is_active,
            "updated_at": func.now()
        }

        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_exchange_trading_symbol",
            set_=update_dict
        )

        try:
            result = await db.execute(upsert_stmt)
            await db.commit()
            record_count = len(payloads)
            await logger.ainfo("Bulk instrument master synchronization complete", processed_count=record_count)
            return record_count
        except Exception as err:
            await db.rollback()
            await logger.aerror("Database bulk transaction failed during instrument ingestion", error=str(err))
            raise

    @staticmethod
    async def search(
        db: AsyncSession, 
        filters: InstrumentSearchFilter, 
        page: int = 1, 
        size: int = 50
    ) -> Tuple[List[Instrument], int]:
        """
        Executes an ordered wildcard search across millions of contracts.
        Returns a structured tuple containing the paginated collection and total matched count.
        """
        # Base querying parameters
        query_stmt = select(Instrument)
        count_stmt = select(func.count()).select_from(Instrument)

        # Dynamic filtering execution block
        filter_conditions = []

        if filters.is_active is not None:
            filter_conditions.append(Instrument.is_active.is_(filters.is_active))
        if filters.exchange:
            filter_conditions.append(Instrument.exchange == filters.exchange.upper().strip())
        if filters.segment:
            filter_conditions.append(Instrument.segment == filters.segment.upper().strip())
        if filters.asset_type:
            filter_conditions.append(Instrument.asset_type == filters.asset_type.upper().strip())
        
        # Wildcard string matching logic
        if filters.q:
            search_term = f"%{filters.q.strip()}%"
            filter_conditions.append(
                or_(
                    Instrument.trading_symbol.ilike(search_term),
                    Instrument.symbol.ilike(search_term)
                )
            )

        if filter_conditions:
            query_stmt = query_stmt.where(*filter_conditions)
            count_stmt = count_stmt.where(*filter_conditions)

        # Dynamic sorting matrix implementation
        sort_attr = getattr(Instrument, filters.sort_by or "trading_symbol", Instrument.trading_symbol)
        if filters.sort_order == "desc":
            query_stmt = query_stmt.order_by(desc(sort_attr))
        else:
            query_stmt = query_stmt.order_by(asc(sort_attr))

        # Paginated bounds extraction
        offset = (page - 1) * size
        query_stmt = query_stmt.offset(offset).limit(size)

        # Execution block
        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar_one() or 0

        query_result = await db.execute(query_stmt)
        items = query_result.scalars().all()

        return list(items), total_count