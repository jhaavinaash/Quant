from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.services.broker import BrokerService
from app.schemas.broker import (
    BrokerCredentialCreate,
    BrokerCredentialUpdate,
    BrokerCredentialResponse
)

logger = structlog.get_logger()
router = APIRouter()

@router.post("/", response_model=BrokerCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_broker_credential(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    broker_in: BrokerCredentialCreate
):
    """
    Registers a new broker connection profile for the authenticated user.
    """
    return await BrokerService.create(db, user_id=current_user.id, obj_in=broker_in)

@router.get("/", response_model=List[BrokerCredentialResponse])
async def read_broker_credentials(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all broker profiles for the authenticated user.
    """
    return await BrokerService.get_multi_by_user(db, user_id=current_user.id)

@router.get("/{credential_id}", response_model=BrokerCredentialResponse)
async def read_broker_credential(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credential_id: int
):
    """
    Retrieve a specific broker profile by ID.
    """
    credential = await BrokerService.get_by_id(db, credential_id=credential_id, user_id=current_user.id)
    if not credential:
        raise HTTPException(status_code=404, detail="Broker credential not found")
    return credential

@router.put("/{credential_id}", response_model=BrokerCredentialResponse)
async def update_broker_credential(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credential_id: int,
    broker_in: BrokerCredentialUpdate
):
    """
    Update an existing broker profile.
    """
    credential = await BrokerService.get_by_id(db, credential_id=credential_id, user_id=current_user.id)
    if not credential:
        raise HTTPException(status_code=404, detail="Broker credential not found")
    
    return await BrokerService.update(db, db_obj=credential, obj_in=broker_in)

@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_broker_credential(
    *,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credential_id: int
):
    """
    Deactivate (soft-delete) a broker profile.
    """
    success = await BrokerService.deactivate(db, credential_id=credential_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Broker credential not found")
    return None