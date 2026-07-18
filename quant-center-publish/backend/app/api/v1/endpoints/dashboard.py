from fastapi import APIRouter, status

from app.schemas.dashboard import ControlResult, DashboardSnapshot
from app.schemas.broker_connectivity import BrokerConnectivityItem
from app.services.broker_connectivity_service import BrokerConnectivityService
from app.services.dashboard_controls import DashboardControlsService, get_last_engine_result
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get("", response_model=DashboardSnapshot, status_code=status.HTTP_200_OK)
def get_dashboard() -> DashboardSnapshot:
    return DashboardService.get_snapshot()


@router.get("/control-result", response_model=ControlResult | None, status_code=status.HTTP_200_OK)
def get_control_result() -> ControlResult | None:
    return get_last_engine_result()


@router.get("/broker-status", response_model=list[BrokerConnectivityItem], status_code=status.HTTP_200_OK)
def get_broker_status() -> list[BrokerConnectivityItem]:
    return BrokerConnectivityService.get_statuses()


@router.post("/refresh", response_model=ControlResult, status_code=status.HTTP_200_OK)
def refresh_dashboard() -> ControlResult:
    return DashboardControlsService.refresh_data()


@router.post("/run-engines", response_model=ControlResult, status_code=status.HTTP_200_OK)
def run_engines() -> ControlResult:
    return DashboardControlsService.run_engines()


@router.post("/run-s1", response_model=ControlResult, status_code=status.HTTP_200_OK)
def run_s1() -> ControlResult:
    return DashboardControlsService.run_s1()
