"""Shared LangGraph state for the analysis graph (router -> per-ticker analyst fan-out -> master)."""

import operator
from typing import Annotated, Literal, TypedDict


class AnalystFinding(TypedDict):
    ticker: str
    summary: str
    score: float
    key_points: list[str]
    raw_data: dict


class AnalysisState(TypedDict, total=False):
    query: str
    intent: Literal["single_stock", "portfolio", "compare"]
    tickers: list[str]
    portfolio: dict[str, float] | None

    # Set only on the per-(ticker, analyst) state dict LangGraph's Send() dispatches to each
    # analyst node — never part of the persistent graph-level state the router/master see.
    ticker: str

    # Annotated with operator.add so every parallel analyst branch (one Send per ticker per
    # analyst type) can append its findings without clobbering any other branch's writes.
    fundamental_findings: Annotated[list[AnalystFinding], operator.add]
    technical_findings: Annotated[list[AnalystFinding], operator.add]
    sentiment_findings: Annotated[list[AnalystFinding], operator.add]

    final_answer: str
    verdict: dict | None
    errors: Annotated[list[str], operator.add]
