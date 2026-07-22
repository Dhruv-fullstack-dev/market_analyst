"""Router node: classify query intent and resolve tickers to Yahoo Finance symbols."""

from app.agents.schemas import RouterOutput
from app.agents.state import AnalysisState
from app.core.llm import get_llm, get_rate_limiter
from app.core.logging import get_logger
from app.core.timing import log_node_duration
from app.prompts.router import build_router_messages
from app.tools.symbols import resolve_symbol

logger = get_logger(__name__)


@log_node_duration
def router_node(state: AnalysisState) -> dict:
    """Classify intent + extract tickers.

    Skips LLM classification when the caller already forced `intent` + `tickers` (e.g. the
    `/compare` API route) or supplied a `portfolio` directly (the `/portfolio` API route).
    """
    if state.get("intent") and state.get("tickers"):
        logger.info(
            "Intent and tickers already provided (intent=%s, tickers=%s); skipping classification",
            state["intent"],
            state["tickers"],
        )
        return {}

    portfolio = state.get("portfolio")
    if portfolio:
        logger.info("Portfolio supplied with %d holdings; routing as 'portfolio' intent", len(portfolio))
        return {"intent": "portfolio", "tickers": list(portfolio.keys())}

    query = state.get("query", "")
    logger.info("Classifying intent for query: %r", query)

    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(RouterOutput)
        get_rate_limiter().acquire()
        classification: RouterOutput = structured_llm.invoke(build_router_messages(query))
    except Exception as exc:
        logger.exception("Router LLM classification failed")
        return {
            "intent": "single_stock",
            "tickers": [],
            "errors": [f"router: LLM classification failed: {exc}"],
        }

    logger.info("Classified intent=%s companies=%s", classification.intent, classification.companies)

    tickers: list[str] = []
    errors: list[str] = []
    for company in classification.companies:
        symbol = resolve_symbol(company)
        if symbol:
            tickers.append(symbol)
        else:
            errors.append(f"router: could not resolve ticker for '{company}'")

    return {"intent": classification.intent, "tickers": tickers, "errors": errors}
