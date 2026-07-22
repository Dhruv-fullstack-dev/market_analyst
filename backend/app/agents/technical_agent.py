"""Technical analyst node: assesses trend/momentum from price history + indicators for one ticker.

Dispatched once per ticker via LangGraph's Send() (see agents/graph.py) for true per-symbol
parallelism, rather than looping over every ticker inside a single node call.
"""

from app.agents.schemas import FindingOutput
from app.agents.state import AnalysisState, AnalystFinding
from app.core.llm import get_llm, get_rate_limiter
from app.core.logging import get_logger
from app.core.timing import log_node_duration
from app.prompts.technical import build_technical_messages
from app.tools.market_data import get_technical_indicators

logger = get_logger(__name__)


@log_node_duration
def technical_agent_node(state: AnalysisState) -> dict:
    ticker = state["ticker"]
    logger.info("Running technical analysis for %s", ticker)
    try:
        indicators = get_technical_indicators(ticker)
        if "error" in indicators:
            logger.warning("Skipping technical analysis for %s: %s", ticker, indicators["error"])
            return {"errors": [f"technical_agent: {ticker}: {indicators['error']}"]}

        llm = get_llm()
        structured_llm = llm.with_structured_output(FindingOutput)
        get_rate_limiter().acquire()
        result: FindingOutput = structured_llm.invoke(build_technical_messages(ticker, indicators))

        finding = AnalystFinding(
            ticker=ticker,
            summary=result.summary,
            score=result.score,
            key_points=result.key_points,
            raw_data=indicators,
        )
        logger.debug("Technical finding for %s: score=%s", ticker, result.score)
        return {"technical_findings": [finding]}
    except Exception as exc:
        logger.exception("Technical analysis failed for %s", ticker)
        return {"errors": [f"technical_agent: {ticker}: {exc}"]}
