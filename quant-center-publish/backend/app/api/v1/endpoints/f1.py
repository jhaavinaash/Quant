from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.f1 import F1DeployRequest, F1DeployResult, F1RunResult, F1Snapshot
from app.services.f1_service import F1Service

router = APIRouter()


@router.get("", response_model=F1Snapshot, status_code=status.HTTP_200_OK)
async def get_f1_snapshot(current_user: User = Depends(get_current_user)) -> F1Snapshot:
    """Refresh F1 page data from canonical production CSVs (does not run F1)."""
    return F1Service.get_snapshot()


@router.post("/run", response_model=F1RunResult, status_code=status.HTTP_200_OK)
async def run_f1(current_user: User = Depends(get_current_user)) -> F1RunResult:
    """Run production F0/f1_runner.py (same subprocess path as Streamlit Tab 11)."""
    return F1Service.run_f1()


@router.post("/deploy", response_model=F1DeployResult, status_code=status.HTTP_200_OK)
async def deploy_f1_candidate(
    body: F1DeployRequest,
    current_user: User = Depends(get_current_user),
) -> F1DeployResult:
    """Deploy handoff → F0/production/pending_trade.json for Trade Entry."""
    return F1Service.deploy(body.ticker)
