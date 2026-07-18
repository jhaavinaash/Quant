from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.production_broker import (
    ProductionBrokerConnectAllResult,
    ProductionBrokerConnectResult,
    ProductionBrokerSummary,
)
from app.services.production_broker_service import ProductionBrokerService

router = APIRouter()


@router.get("", response_model=ProductionBrokerSummary, status_code=status.HTTP_200_OK)
async def list_production_brokers(
    current_user: User = Depends(get_current_user),
) -> ProductionBrokerSummary:
    return ProductionBrokerService.get_summary()


@router.post("/{broker_name}/connect", response_model=ProductionBrokerConnectResult, status_code=status.HTTP_200_OK)
async def connect_production_broker(
    broker_name: str,
    current_user: User = Depends(get_current_user),
) -> ProductionBrokerConnectResult:
    return ProductionBrokerService.connect(broker_name)


@router.post("/connect-all", response_model=ProductionBrokerConnectAllResult, status_code=status.HTTP_200_OK)
async def connect_all_production_brokers(
    current_user: User = Depends(get_current_user),
) -> ProductionBrokerConnectAllResult:
    return ProductionBrokerService.connect_all()
