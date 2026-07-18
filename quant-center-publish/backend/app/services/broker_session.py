from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.broker_session import BrokerSession
from app.schemas.broker_session import BrokerSessionCreate, BrokerSessionUpdate

logger = structlog.get_logger()


class BrokerSessionService:
    """
    Business service layer managing the orchestration and life cycle state 
    of transient broker token connections.
    
    Enforces structural database unique bounds cleanly by automatically 
    inverting older active tokens during a fresh morning handshake.
    """

    @staticmethod
    async def get_by_id(db: AsyncSession, session_id: int, user_id: int) -> BrokerSession | None:
        """Fetch a specific token tracking boundary record verified against the operator workspace."""
        result = await db.execute(
            select(BrokerSession).where(
                BrokerSession.id == session_id,
                BrokerSession.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_credential(db: AsyncSession, broker_credential_id: int, user_id: int) -> BrokerSession | None:
        """Retrieves the single authoritative active session record for a given credential mapping."""
        result = await db.execute(
            select(BrokerSession).where(
                BrokerSession.broker_credential_id == broker_credential_id,
                BrokerSession.user_id == user_id,
                BrokerSession.is_active.is_(True)
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_multi_by_user(db: AsyncSession, user_id: int) -> Sequence[BrokerSession]:
        """Gathers all historical and operational token profiles belonging to an operator."""
        result = await db.execute(
            select(BrokerSession).where(BrokerSession.user_id == user_id)
        )
        return result.scalars().all()

    @staticmethod
    async def create(db: AsyncSession, user_id: int, obj_in: BrokerSessionCreate) -> BrokerSession:
        """
        Registers an active trading session vector.
        
        To fulfill the unique constraint block uq_active_broker_session, this method 
        scans for any pre-existing active session maps linked to the target broker profile 
        and preemptively deactivates them before inserting the new token coordinates.
        """
        # Scan phase: Clear concurrent active records for this identity matrix
        existing_active_stmt = select(BrokerSession).where(
            BrokerSession.broker_credential_id == obj_in.broker_credential_id,
            BrokerSession.is_active.is_(True)
        )
        existing_result = await db.execute(existing_active_stmt)
        stale_session = existing_result.scalar_one_or_none()

        if stale_session:
            await logger.ainfo(
                "Deactivating pre-existing active session channel to avoid token collision",
                broker_credential_id=obj_in.broker_credential_id,
                stale_session_id=stale_session.id
            )
            stale_session.is_active = False
            db.add(stale_session)

        # Ingestion phase: Map and preserve new encrypted authentication channels
        db_obj = BrokerSession(
            user_id=user_id,
            broker_credential_id=obj_in.broker_credential_id,
            encrypted_access_token=obj_in.access_token,  # Assumed pre-sealed or raw layer controlled
            expires_at=obj_in.expires_at,
            is_active=True,
            encrypted_extra_session_data=obj_in.extra_session_data
        )

        try:
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
        except Exception as err:
            await db.rollback()
            await logger.aerror(
                "Failed database transaction during execution session capture loop",
                user_id=user_id,
                broker_credential_id=obj_in.broker_credential_id,
                error=str(err)
            )
            raise

        await logger.ainfo(
            "New operational broker token session established successfully",
            user_id=user_id,
            session_id=db_obj.id,
            broker_credential_id=db_obj.broker_credential_id
        )
        return db_obj

    @staticmethod
    async def deactivate(db: AsyncSession, session_id: int, user_id: int) -> bool:
        """
        Deactivates a specific connection session gracefully by inverting its active flag tracking.
        Preserves complete data lineage records for performance audit trails.
        """
        db_obj = await BrokerSessionService.get_by_id(db, session_id=session_id, user_id=user_id)
        if not db_obj:
            return False

        # Strictly follow uniform 'is_active' deactivation layout pattern
        db_obj.is_active = False

        try:
            db.add(db_obj)
            await db.commit()
        except Exception as err:
            await db.rollback()
            await logger.aerror(
                "Failed database transaction during token channel deactivation execution",
                session_id=session_id,
                error=str(err)
            )
            raise

        await logger.ainfo(
            "Broker transaction session channel deactivated cleanly", 
            session_id=session_id
        )
        return True