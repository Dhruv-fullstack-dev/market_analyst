"""Pydantic request/response models for the FastAPI backend (architecture.md §7)."""

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    query: str = Field(min_length=1)


class Holding(BaseModel):
    ticker: str
    qty: float


class PortfolioRequest(BaseModel):
    holdings: list[Holding] = Field(min_length=1)


class CompareRequest(BaseModel):
    tickers: list[str] = Field(min_length=2)


class AnalystFindingResponse(BaseModel):
    ticker: str
    summary: str
    score: float
    key_points: list[str]
    raw_data: dict


class FindingsResponse(BaseModel):
    fundamental: list[AnalystFindingResponse] = Field(default_factory=list)
    technical: list[AnalystFindingResponse] = Field(default_factory=list)
    sentiment: list[AnalystFindingResponse] = Field(default_factory=list)


class VerdictResponse(BaseModel):
    recommendation: str | None = None
    confidence: float | None = None


class AnalysisResponse(BaseModel):
    intent: str
    tickers: list[str]
    findings: FindingsResponse
    verdict: VerdictResponse | None = None
    final_answer: str
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
