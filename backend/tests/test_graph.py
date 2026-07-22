"""End-to-end tests of the compiled LangGraph (router -> per-ticker analyst fan-out -> master).

Per rules.md: the Gemini LLM and all external tools (yfinance, DuckDuckGo) are always mocked.
"""

from app.agents.graph import app as graph_app
from app.agents.graph import fan_out_to_analysts
from app.agents.schemas import FindingOutput, MasterOutput, RouterOutput

# ---------------------------------------------------------------------------
# fan_out_to_analysts (the Send()-based dispatch itself)
# ---------------------------------------------------------------------------


def test_fan_out_to_analysts_dispatches_one_send_per_ticker_per_analyst():
    state = {"tickers": ["A.NS", "B.NS"], "intent": "portfolio"}

    sends = fan_out_to_analysts(state)

    assert len(sends) == 6  # 2 tickers * 3 analyst types
    dispatched = {(s.node, s.arg["ticker"]) for s in sends}
    assert dispatched == {
        ("fundamental_analyst", "A.NS"),
        ("fundamental_analyst", "B.NS"),
        ("technical_analyst", "A.NS"),
        ("technical_analyst", "B.NS"),
        ("sentiment_analyst", "A.NS"),
        ("sentiment_analyst", "B.NS"),
    }
    # Each Send's arg carries the rest of the state through too, not just the ticker.
    assert all(s.arg["intent"] == "portfolio" for s in sends)


def test_fan_out_to_analysts_falls_back_to_master_when_no_tickers():
    state = {"tickers": [], "intent": "single_stock"}

    sends = fan_out_to_analysts(state)

    assert len(sends) == 1
    assert sends[0].node == "master"
    assert sends[0].arg == state


def _mock_structured_llm(mocker, module_path: str, return_value):
    mock_structured = mocker.MagicMock()
    mock_structured.invoke.return_value = return_value
    mock_llm = mocker.MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mocker.patch(f"{module_path}.get_llm", return_value=mock_llm)


def _mock_all_analyst_tools(mocker, finding: FindingOutput):
    mocker.patch(
        "app.agents.fundamental_agent.get_fundamentals",
        return_value={"ticker": "RELIANCE.NS", "trailingPE": 25.0},
    )
    mocker.patch(
        "app.agents.technical_agent.get_technical_indicators",
        return_value={"ticker": "RELIANCE.NS", "rsi_14": 55.0},
    )
    mocker.patch(
        "app.agents.sentiment_agent.search_news",
        return_value=[{"title": "Reliance news", "snippet": "..."}],
    )
    _mock_structured_llm(mocker, "app.agents.fundamental_agent", finding)
    _mock_structured_llm(mocker, "app.agents.technical_agent", finding)
    _mock_structured_llm(mocker, "app.agents.sentiment_agent", finding)


def test_graph_single_stock_end_to_end(mocker):
    _mock_structured_llm(
        mocker, "app.agents.router", RouterOutput(intent="single_stock", companies=["Reliance"])
    )
    mocker.patch("app.agents.router.resolve_symbol", return_value="RELIANCE.NS")
    _mock_all_analyst_tools(
        mocker, FindingOutput(summary="Looks decent", score=0.3, key_points=["Stable"])
    )
    _mock_structured_llm(
        mocker, "app.agents.master_agent", MasterOutput(final_answer="Reliance is doing fine overall.")
    )

    result = graph_app.invoke({"query": "How is Reliance doing?"})

    assert result["intent"] == "single_stock"
    assert result["tickers"] == ["RELIANCE.NS"]
    assert len(result["fundamental_findings"]) == 1
    assert len(result["technical_findings"]) == 1
    assert len(result["sentiment_findings"]) == 1
    assert "Reliance is doing fine" in result["final_answer"]
    assert result["verdict"] is None


def test_graph_portfolio_end_to_end_skips_router_llm(mocker):
    mock_router_llm = mocker.patch("app.agents.router.get_llm")
    _mock_all_analyst_tools(
        mocker, FindingOutput(summary="Mixed bag", score=0.0, key_points=["Watch closely"])
    )
    _mock_structured_llm(
        mocker,
        "app.agents.master_agent",
        MasterOutput(final_answer="Your portfolio is holding steady."),
    )

    initial_state = {
        "query": "How is my portfolio doing?",
        "portfolio": {"TATAMOTORS.NS": 10, "INFY.NS": 5},
    }
    result = graph_app.invoke(initial_state)

    assert result["intent"] == "portfolio"
    assert set(result["tickers"]) == {"TATAMOTORS.NS", "INFY.NS"}
    mock_router_llm.assert_not_called()
    # Each ticker is dispatched as its own Send() to each analyst type, so 2 tickers -> 2
    # independent fundamental_analyst invocations (not 1 invocation looping over both).
    assert len(result["fundamental_findings"]) == 2
    assert {f["ticker"] for f in result["fundamental_findings"]} == {"TATAMOTORS.NS", "INFY.NS"}
    assert "portfolio is holding steady" in result["final_answer"]


def test_graph_compare_end_to_end_populates_verdict(mocker):
    _mock_structured_llm(
        mocker,
        "app.agents.router",
        RouterOutput(intent="compare", companies=["Tata Motors", "Mahindra & Mahindra"]),
    )
    mocker.patch(
        "app.agents.router.resolve_symbol",
        side_effect=lambda name: {"Tata Motors": "TATAMOTORS.NS", "Mahindra & Mahindra": "M&M.NS"}[name],
    )
    _mock_all_analyst_tools(mocker, FindingOutput(summary="Comparable", score=0.2, key_points=["Similar"]))
    _mock_structured_llm(
        mocker,
        "app.agents.master_agent",
        MasterOutput(
            final_answer="Mahindra edges out Tata Motors.", recommendation="M&M.NS", confidence=0.65
        ),
    )

    result = graph_app.invoke({"query": "Compare Tata Motors & Mahindra, which should I buy?"})

    assert result["intent"] == "compare"
    # Both tickers score identically (0.2) across every analyst, so verdict calibration treats
    # this as a tie and dampens the LLM's stated 0.65 confidence down to 0.55.
    assert result["verdict"] == {"recommendation": "M&M.NS", "confidence": 0.55}
    assert "not financial advice" in result["final_answer"].lower()


def test_graph_survives_one_analyst_failing(mocker):
    """If the technical tool fails for every ticker, master still runs and errors are recorded."""
    _mock_structured_llm(
        mocker, "app.agents.router", RouterOutput(intent="single_stock", companies=["Reliance"])
    )
    mocker.patch("app.agents.router.resolve_symbol", return_value="RELIANCE.NS")

    mocker.patch(
        "app.agents.fundamental_agent.get_fundamentals",
        return_value={"ticker": "RELIANCE.NS", "trailingPE": 25.0},
    )
    mocker.patch(
        "app.agents.technical_agent.get_technical_indicators",
        return_value={"error": "no_price_history", "ticker": "RELIANCE.NS"},
    )
    mocker.patch(
        "app.agents.sentiment_agent.search_news",
        return_value=[{"title": "Reliance news", "snippet": "..."}],
    )
    finding = FindingOutput(summary="Fine", score=0.1, key_points=["OK"])
    _mock_structured_llm(mocker, "app.agents.fundamental_agent", finding)
    _mock_structured_llm(mocker, "app.agents.sentiment_agent", finding)
    _mock_structured_llm(
        mocker,
        "app.agents.master_agent",
        MasterOutput(final_answer="Partial analysis: technical data was unavailable."),
    )

    result = graph_app.invoke({"query": "How is Reliance doing?"})

    assert result["technical_findings"] == []
    assert any("no_price_history" in err for err in result["errors"])
    # Master still produced a final answer despite the missing technical findings.
    assert "Partial analysis" in result["final_answer"]
    assert len(result["fundamental_findings"]) == 1
    assert len(result["sentiment_findings"]) == 1


def test_graph_end_to_end_with_no_resolvable_tickers_still_reaches_master(mocker):
    """If the router can't resolve any ticker, no analyst Sends fire — master must still run."""
    _mock_structured_llm(
        mocker, "app.agents.router", RouterOutput(intent="single_stock", companies=["Nonexistent Corp"])
    )
    mocker.patch("app.agents.router.resolve_symbol", return_value=None)
    _mock_structured_llm(
        mocker,
        "app.agents.master_agent",
        MasterOutput(final_answer="I couldn't find a ticker for that company."),
    )

    result = graph_app.invoke({"query": "How is Nonexistent Corp doing?"})

    assert result["tickers"] == []
    assert result["fundamental_findings"] == []
    assert result["technical_findings"] == []
    assert result["sentiment_findings"] == []
    assert any("Nonexistent Corp" in err for err in result["errors"])
    assert "couldn't find a ticker" in result["final_answer"]
