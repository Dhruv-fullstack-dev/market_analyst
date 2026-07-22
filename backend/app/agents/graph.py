"""LangGraph wiring: router -> per-ticker analyst fan-out (Send) -> master (fan-in).

Each ticker is dispatched to each analyst type as its own parallel branch via LangGraph's
`Send()` API, so a portfolio/compare query with N tickers runs N*3 concurrent analyst
invocations rather than 3 invocations that each internally loop over N tickers.
"""

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents.fundamental_agent import fundamental_agent_node
from app.agents.master_agent import master_agent_node
from app.agents.router import router_node
from app.agents.sentiment_agent import sentiment_agent_node
from app.agents.state import AnalysisState
from app.agents.technical_agent import technical_agent_node
from app.core.logging import get_logger

logger = get_logger(__name__)

_ANALYST_NODES = ("fundamental_analyst", "technical_analyst", "sentiment_analyst")


def fan_out_to_analysts(state: AnalysisState) -> list[Send]:
    """One Send per (ticker, analyst) pair -> true per-symbol parallelism.

    Falls back to sending straight to `master` when there are no tickers (e.g. the router
    couldn't resolve anything): master is normally only reachable via the analyst nodes'
    static edges, and none of them would ever run otherwise.
    """
    tickers = state.get("tickers", [])
    if not tickers:
        logger.warning("No tickers to analyze; routing straight to master")
        return [Send("master", state)]

    return [Send(node, {**state, "ticker": ticker}) for ticker in tickers for node in _ANALYST_NODES]


def build_graph():
    graph = StateGraph(AnalysisState)

    graph.add_node("router", router_node)
    graph.add_node("fundamental_analyst", fundamental_agent_node)
    graph.add_node("technical_analyst", technical_agent_node)
    graph.add_node("sentiment_analyst", sentiment_agent_node)
    graph.add_node("master", master_agent_node)

    graph.add_edge(START, "router")

    # Fan-out: dynamic per-(ticker, analyst) dispatch instead of 3 static edges.
    graph.add_conditional_edges("router", fan_out_to_analysts)

    # Fan-in: master only runs once every dispatched analyst branch has completed; their
    # findings are merged via the `operator.add` reducers on AnalysisState.
    graph.add_edge("fundamental_analyst", "master")
    graph.add_edge("technical_analyst", "master")
    graph.add_edge("sentiment_analyst", "master")

    graph.add_edge("master", END)

    logger.info("Compiling analysis graph")
    return graph.compile()


# Compiled once at import time; reused across requests.
app = build_graph()
