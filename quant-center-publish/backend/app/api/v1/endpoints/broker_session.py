from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.services.broker_session import BrokerSessionService
from app.schemas.broker_session import BrokerSessionCreate, BrokerSessionResponse
from app.core.crypto import SymmetricCrypto

logger = structlog.get_logger()
router = APIRouter()


@router.post("/", response_model=BrokerSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_broker_session(
    session_in: BrokerSessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Registers a new active exchange authorization session vector.
    Applies symmetric cryptographic transformations to raw access keys before service ingestion.
    """
    try:
        session_in.access_token = SymmetricCrypto.encrypt_string(session_in.access_token)
        if session_in.extra_session_data:
            session_in.extra_session_data = SymmetricCrypto.encrypt_json(session_in.extra_session_data)
    except Exception as crypto_err:
        await logger.aerror("Cryptographic processing failure during session token registration", error=str(crypto_err))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to securely seal transient session tokens. Initialization aborted."
        )

    new_session = await BrokerSessionService.create(db, user_id=current_user.id, obj_in=session_in)
    return new_session


@router.get("/current/{broker_credential_id}", response_model=BrokerSessionResponse)
async def get_current_session(
    broker_credential_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches the single authoritative current session record tracking an ongoing exchange link.
    Renamed semantically to match clean consuming API layout standards.
    """
    session = await BrokerSessionService.get_active_by_credential(
        db, 
        broker_credential_id=broker_credential_id, 
        user_id=current_user.id
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current active trading session found for the specified broker configuration profile."
        )
    return session


@router.get("/", response_model=List[BrokerSessionResponse])
async def list_historical_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the complete historical footprint of session connections belonging to the active operator.
    """
    sessions = await BrokerSessionService.get_multi_by_user(db, user_id=current_user.id)
    return sessions


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_broker_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Executes an explicit session channel disconnect pattern.
    Deactivates the token instance state immediately via service layer mutations.
    """
    success = await BrokerSessionService.deactivate(db, session_id=session_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target session profile not found or access privilege validation failed."
        )
    return