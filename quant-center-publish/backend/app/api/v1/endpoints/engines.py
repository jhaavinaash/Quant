from fastapi import APIRouter
from typing import List
from app.services.engine_service import EngineService
from app.schemas.engine import EngineStatus

router = APIRouter()

@router.get("/status", response_model=List[EngineStatus])
def get_engine_status():
    """
    Returns the current status of all trading engines from the 
    orchestrator-generated engine_status.csv.
    """
    return EngineService.get_engine_statuses()