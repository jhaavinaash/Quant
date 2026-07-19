"""Read-only API contract for the existing Market Intelligence outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MarketBriefingMetric(BaseModel):
    name: str
    value: str


class MarketBriefingHighlight(BaseModel):
    dimension: str
    state: str
    explanation: str


class MarketBriefingDimension(BaseModel):
    name: str
    state: str
    explanation: str
    metrics: list[MarketBriefingMetric] = Field(default_factory=list)


class MarketBriefingSnapshot(BaseModel):
    scope: str
    approach: str
    confidence: str
    oneLineSummary: str
    reason: str
    keyPositives: list[MarketBriefingHighlight] = Field(default_factory=list)
    keyRisks: list[MarketBriefingHighlight] = Field(default_factory=list)
    dimensions: list[MarketBriefingDimension] = Field(default_factory=list)
    rawMetrics: dict[str, Any] = Field(default_factory=dict)
    dataDate: str
    universeSize: int
    sectorCoverage: int
    lastRefreshTime: str
