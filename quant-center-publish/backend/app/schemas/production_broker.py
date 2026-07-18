from typing import Optional

from pydantic import BaseModel, Field


class ProductionBrokerCard(BaseModel):
    name: str
    displayName: str
    status: str
    configured: bool = False
    userName: Optional[str] = None
    userId: Optional[str] = None
    email: Optional[str] = None
    availableCash: Optional[float] = None
    error: Optional[str] = None


class ProductionBrokerSummary(BaseModel):
    connectedCount: int
    totalCount: int
    brokers: list[ProductionBrokerCard] = Field(default_factory=list)


class ProductionBrokerConnectResult(BaseModel):
    broker: str
    success: bool
    status: str
    message: str = ""


class ProductionBrokerConnectAllResult(BaseModel):
    results: list[ProductionBrokerConnectResult]
    connectedCount: int
    totalCount: int
