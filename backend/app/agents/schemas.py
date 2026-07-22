"""Pydantic models for structured LLM output (via `with_structured_output`)."""

from typing import Literal

from pydantic import BaseModel, Field


class FindingOutput(BaseModel):
    """What every analyst agent (fundamental/technical/sentiment) must produce for one ticker."""

    summary: str = Field(description="1-3 sentence summary of the analysis")
    score: float = Field(
        description="Bullish/bearish score from -1 (very bearish) to +1 (very bullish)", ge=-1, le=1
    )
    key_points: list[str] = Field(
        default_factory=list, description="3-5 short bullet points backing the summary"
    )


class RouterOutput(BaseModel):
    """Query intent classification + raw company mentions."""

    intent: Literal["single_stock", "portfolio", "compare"]
    companies: list[str] = Field(
        default_factory=list, description="Company names/tickers mentioned in the query, verbatim"
    )


class TickerGuessOutput(BaseModel):
    """Best-guess NSE/BSE ticker for a company name the curated map doesn't cover."""

    ticker: str | None = Field(
        default=None,
        description="Best-guess NSE/BSE ticker symbol (without .NS/.BO suffix) for the company, "
        "or null if you aren't reasonably confident",
    )


class MasterOutput(BaseModel):
    """Final synthesis produced by the master node."""

    final_answer: str = Field(description="Full markdown-formatted narrative answer for the user")
    recommendation: str | None = Field(
        default=None, description="Only for 'compare' intent: which stock to prefer"
    )
    confidence: float | None = Field(
        default=None,
        description="Only for 'compare' intent: confidence (0-1) in the recommendation",
        ge=0,
        le=1,
    )
