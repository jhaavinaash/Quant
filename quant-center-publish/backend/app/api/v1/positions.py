from fastapi import APIRouter, status
from typing import List
from pydantic import BaseModel

# Schema representing the position contract
# This must match the frontend src/types/index.ts: Position interface
class Position(BaseModel):
    id: str
    instrument: str
    quantity: int
    avgPrice: float
    pnl: float

router = APIRouter()

@router.get("/", response_model=List[Position], status_code=status.HTTP_200_OK)
async def get_positions():
    """
    Fetch all active positions for the current user.
    """
    # Implementation Note: 
    # Logic to fetch from database or broker API goes here.
    # Returning empty list until database service is injected.
    return []