"""Live broker connectivity via Quant production BrokerManager."""

from app.schemas.broker_connectivity import BrokerConnectivityItem
from app.services.production_broker_service import ProductionBrokerService


class BrokerConnectivityService:
    @staticmethod
    def get_statuses() -> list[BrokerConnectivityItem]:
        return ProductionBrokerService.get_connectivity_statuses()
