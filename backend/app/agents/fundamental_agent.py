"""Fundamental analyst node: assesses P/E, growth, debt, margins, etc. for one ticker.

Dispatched once per ticker via LangGraph's Send() (see agents/graph.py) for true per-symbol
parallelism, rather than looping over every ticker inside a single node call.
"""

from app.agents.schemas import FindingOutput
from app.agents.state import AnalysisState, AnalystFinding
from app.core.llm import get_llm, get_rate_limiter
from app.core.logging import get_logger
from app.core.timing import log_node_duration
from app.prompts.fundamental import build_fundamental_messages
from app.tools.market_data import get_fundamentals

logger = get_logger(__name__)


@log_node_duration
def fundamental_agent_node(state: AnalysisState) -> dict:
    ticker = state["ticker"]
    logger.info("Running fundamental analysis for %s", ticker)
    try:
        data = get_fundamentals(ticker)
        if "error" in data:
            logger.warning("Skipping fundamental analysis for %s: %s", ticker, data["error"])
            return {"errors": [f"fundamental_agent: {ticker}: {data['error']}"]}

        llm = get_llm()
        structured_llm = llm.with_structured_output(FindingOutput)
        get_rate_limiter().acquire()
        result: FindingOutput = structured_llm.invoke(build_fundamental_messages(ticker, data))

        finding = AnalystFinding(
            ticker=ticker,
            summary=result.summary,
            score=result.score,
            key_points=result.key_points,
            raw_data=data,
        )
        logger.debug("Fundamental finding for %s: score=%s", ticker, result.score)
        return {"fundamental_findings": [finding]}
    except Exception as exc:
        logger.exception("Fundamental analysis failed for %s", ticker)
        return {"errors": [f"fundamental_agent: {ticker}: {exc}"]}
