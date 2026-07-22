"""Sentiment analyst node: assesses recent news tone/events for one ticker via DuckDuckGo search.

Dispatched once per ticker via LangGraph's Send() (see agents/graph.py) for true per-symbol
parallelism, rather than looping over every ticker inside a single node call.
"""

from app.agents.schemas import FindingOutput
from app.agents.state import AnalysisState, AnalystFinding
from app.core.llm import get_llm
from app.core.logging import get_logger
from app.core.timing import log_node_duration
from app.prompts.sentiment import build_sentiment_messages
from app.tools.web_search import search_news

logger = get_logger(__name__)


@log_node_duration
def sentiment_agent_node(state: AnalysisState) -> dict:
    ticker = state["ticker"]
    logger.info("Running sentiment analysis for %s", ticker)
    try:
        company_name = ticker.split(".")[0]
        articles = search_news(f"{company_name} share price news")
        if articles and "error" in articles[0]:
            logger.warning("Skipping sentiment analysis for %s: %s", ticker, articles[0]["error"])
            return {"errors": [f"sentiment_agent: {ticker}: {articles[0]['error']}"]}

        llm = get_llm()
        structured_llm = llm.with_structured_output(FindingOutput)
        result: FindingOutput = structured_llm.invoke(build_sentiment_messages(ticker, articles))

        finding = AnalystFinding(
            ticker=ticker,
            summary=result.summary,
            score=result.score,
            key_points=result.key_points,
            raw_data={"articles": articles},
        )
        logger.debug("Sentiment finding for %s: score=%s", ticker, result.score)
        return {"sentiment_findings": [finding]}
    except Exception as exc:
        logger.exception("Sentiment analysis failed for %s", ticker)
        return {"errors": [f"sentiment_agent: {ticker}: {exc}"]}
