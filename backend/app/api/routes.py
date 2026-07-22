"""FastAPI routes wrapping the compiled LangGraph analysis graph."""

from fastapi import APIRouter

from app.agents.graph import app as analysis_graph
from app.api.schemas import (
    AnalysisResponse,
    AnalyzeRequest,
    CompareRequest,
    FindingsResponse,
    HealthResponse,
    PortfolioRequest,
    VerdictResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def _build_response(result: dict) -> AnalysisResponse:
    verdict = result.get("verdict")
    return AnalysisResponse(
        intent=result.get("intent", "single_stock"),
        tickers=result.get("tickers", []),
        findings=FindingsResponse(
            fundamental=result.get("fundamental_findings", []),
            technical=result.get("technical_findings", []),
            sentiment=result.get("sentiment_findings", []),
        ),
        verdict=VerdictResponse(**verdict) if verdict else None,
        final_answer=result.get("final_answer", ""),
        errors=result.get("errors", []),
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/analyze", response_model=AnalysisResponse)
def analyze(request: AnalyzeRequest) -> AnalysisResponse:
    logger.info("POST /analyze query=%r", request.query)
    result = analysis_graph.invoke({"query": request.query})
    return _build_response(result)


@router.post("/portfolio", response_model=AnalysisResponse)
def portfolio(request: PortfolioRequest) -> AnalysisResponse:
    holdings = {h.ticker: h.qty for h in request.holdings}
    logger.info("POST /portfolio holdings=%s", holdings)
    result = analysis_graph.invoke({"query": "portfolio review", "portfolio": holdings})
    return _build_response(result)


@router.post("/compare", response_model=AnalysisResponse)
def compare(request: CompareRequest) -> AnalysisResponse:
    logger.info("POST /compare tickers=%s", request.tickers)
    result = analysis_graph.invoke(
        {"query": "compare stocks", "intent": "compare", "tickers": request.tickers}
    )
    return _build_response(result)
