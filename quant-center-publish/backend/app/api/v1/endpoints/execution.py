from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.execution import (
    ExecutionActionResult,
    ExecutionRejectRequest,
    ExecutionSnapshot,
)
from app.services.execution_actions_service import ExecutionActionsService
from app.services.execution_service import ExecutionService

router = APIRouter()


@router.get("", response_model=ExecutionSnapshot, status_code=status.HTTP_200_OK)
async def get_execution_snapshot(
    current_user: User = Depends(get_current_user),
) -> ExecutionSnapshot:
    return ExecutionService.get_snapshot()


@router.post(
    "/pending/{request_id}/submit",
    response_model=ExecutionActionResult,
    status_code=status.HTTP_200_OK,
)
async def submit_pending_order(
    request_id: str,
    current_user: User = Depends(get_current_user),
) -> ExecutionActionResult:
    return ExecutionActionsService.submit_pending(request_id)


@router.post(
    "/pending/{request_id}/reject",
    response_model=ExecutionActionResult,
    status_code=status.HTTP_200_OK,
)
async def reject_pending_order(
    request_id: str,
    body: ExecutionRejectRequest,
    current_user: User = Depends(get_current_user),
) -> ExecutionActionResult:
    return ExecutionActionsService.reject_pending(request_id, body.reason)


@router.post("/sync", response_model=ExecutionActionResult, status_code=status.HTTP_200_OK)
async def sync_order_status(
    force: bool = Query(False, description="Re-check PENDING and SYNC_FAILED orders"),
    current_user: User = Depends(get_current_user),
) -> ExecutionActionResult:
    return ExecutionActionsService.sync_order_status(force=force)
