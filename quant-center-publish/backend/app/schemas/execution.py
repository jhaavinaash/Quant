from typing import Optional

from pydantic import BaseModel, Field


class ExecutionCounts(BaseModel):
    pending: int = 0
    approved: int = 0
    submitted: int = 0
    filled: int = 0
    rejectedFailed: int = 0
    queueRejectedBroker: int = 0
    reconciledTotal: int = 0


class ExecutionBrokerState(BaseModel):
    name: str
    status: str


class ExecutionOrderRow(BaseModel):
    id: str
    lifecycle: str
    status: str
    engine: str = ""
    ticker: str = ""
    side: str = ""
    quantity: Optional[int] = None
    broker: str = ""
    brokerOrderId: str = ""
    requestId: str = ""
    timestamp: str = ""
    message: str = ""


class ExecutionSnapshot(BaseModel):
    counts: ExecutionCounts
    brokerState: list[ExecutionBrokerState] = Field(default_factory=list)
    pending: list[ExecutionOrderRow] = Field(default_factory=list)
    approved: list[ExecutionOrderRow] = Field(default_factory=list)
    submitted: list[ExecutionOrderRow] = Field(default_factory=list)
    filled: list[ExecutionOrderRow] = Field(default_factory=list)
    rejectedFailed: list[ExecutionOrderRow] = Field(default_factory=list)


class ExecutionRejectRequest(BaseModel):
    reason: str = "user rejected via Quant-Center"


class ExecutionSyncSummary(BaseModel):
    totalChecked: int = 0
    filled: int = 0
    pending: int = 0
    rejected: int = 0
    failed: int = 0
    exitsChecked: int = 0
    exitsClosed: int = 0
    errors: list[str] = Field(default_factory=list)


class ExecutionActionResult(BaseModel):
    success: bool
    kind: str
    message: str
    outcome: str = ""
    requestId: str = ""
    brokerOrderId: str = ""
    sync: Optional[ExecutionSyncSummary] = None
