from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.f1_basket import (
    BasketActionRequest,
    BasketActionResult,
    BasketDeployConfirmation,
    CreateBasketPreviewRequest,
    DeploySelectedRequest,
    F1BasketSnapshot,
)
from app.services.f1_basket_service import F1BasketService

router = APIRouter()


@router.get("/deploy/confirmation/{basket_id}", response_model=BasketDeployConfirmation)
async def get_deploy_confirmation(
    basket_id: str,
    current_user: User = Depends(get_current_user),
) -> BasketDeployConfirmation:
    conf = F1BasketService.get_deploy_confirmation(basket_id)
    if not conf:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Basket not deployable.")
    return conf


@router.post("/deploy", response_model=BasketActionResult, status_code=status.HTTP_200_OK)
async def deploy_f1_basket(
    body: BasketActionRequest,
    current_user: User = Depends(get_current_user),
) -> BasketActionResult:
    return F1BasketService.deploy_basket(body.basketId)


@router.post("/deploy-selected", response_model=BasketActionResult, status_code=status.HTTP_200_OK)
async def deploy_f1_basket_selected(
    body: DeploySelectedRequest,
    current_user: User = Depends(get_current_user),
) -> BasketActionResult:
    selections = [
        {"ticker": s.ticker, "execute": s.execute, "adoptExistingQty": s.adoptExistingQty}
        for s in body.selections
    ]
    return F1BasketService.deploy_selected(body.basketId, selections)


@router.post("/valuation/sync", response_model=BasketActionResult, status_code=status.HTTP_200_OK)
async def sync_f1_basket_valuation(
    body: BasketActionRequest,
    current_user: User = Depends(get_current_user),
) -> BasketActionResult:
    return F1BasketService.sync_valuation(body.basketId)


@router.post("/manual-exit", response_model=BasketActionResult, status_code=status.HTTP_200_OK)
async def manual_exit_f1_basket(
    body: BasketActionRequest,
    current_user: User = Depends(get_current_user),
) -> BasketActionResult:
    return F1BasketService.manual_exit_basket(body.basketId)


@router.post("/retry-failed-exits", response_model=BasketActionResult, status_code=status.HTTP_200_OK)
async def retry_failed_f1_basket_exits(
    body: BasketActionRequest,
    current_user: User = Depends(get_current_user),
) -> BasketActionResult:
    return F1BasketService.retry_failed_exits(body.basketId)


@router.post("/sync", response_model=BasketActionResult, status_code=status.HTTP_200_OK)
async def sync_f1_basket(
    body: BasketActionRequest,
    current_user: User = Depends(get_current_user),
) -> BasketActionResult:
    return F1BasketService.sync_basket(body.basketId)


@router.post("/retry-failed", response_model=BasketActionResult, status_code=status.HTTP_200_OK)
async def retry_failed_f1_basket_orders(
    body: BasketActionRequest,
    current_user: User = Depends(get_current_user),
) -> BasketActionResult:
    return F1BasketService.retry_failed_orders(body.basketId)


@router.get("/eligibility", response_model=F1BasketSnapshot, status_code=status.HTTP_200_OK)
async def get_f1_basket_eligibility(
    current_user: User = Depends(get_current_user),
) -> F1BasketSnapshot:
    return F1BasketService.get_snapshot()


@router.get("/current", response_model=F1BasketSnapshot, status_code=status.HTTP_200_OK)
async def get_f1_basket_current(
    current_user: User = Depends(get_current_user),
) -> F1BasketSnapshot:
    return F1BasketService.get_snapshot()


@router.post("/preview", response_model=F1BasketSnapshot, status_code=status.HTTP_200_OK)
async def create_f1_basket_preview(
    body: CreateBasketPreviewRequest,
    current_user: User = Depends(get_current_user),
) -> F1BasketSnapshot:
    return F1BasketService.create_preview(capital=body.capital)


@router.post("/preview/rebuild", response_model=F1BasketSnapshot, status_code=status.HTTP_200_OK)
async def rebuild_f1_basket_preview(
    body: CreateBasketPreviewRequest,
    current_user: User = Depends(get_current_user),
) -> F1BasketSnapshot:
    return F1BasketService.rebuild_preview(capital=body.capital)
