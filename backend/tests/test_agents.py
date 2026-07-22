"""Unit tests for agent nodes. Per rules.md: the Gemini LLM is always mocked, never called for real."""

import pytest
from app.agents.fundamental_agent import fundamental_agent_node
from app.agents.master_agent import DISCLAIMER, _calibrate_verdict, master_agent_node
from app.agents.router import router_node
from app.agents.schemas import FindingOutput, MasterOutput, RouterOutput
from app.agents.sentiment_agent import sentiment_agent_node
from app.agents.technical_agent import technical_agent_node


def _mock_structured_llm(mocker, module_path: str, return_value):
    """Patch get_llm() in module_path so with_structured_output(...).invoke(...) returns return_value."""
    mock_structured = mocker.MagicMock()
    mock_structured.invoke.return_value = return_value
    mock_llm = mocker.MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mocker.patch(f"{module_path}.get_llm", return_value=mock_llm)
    return mock_llm


# ---------------------------------------------------------------------------
# router_node
# ---------------------------------------------------------------------------


def test_router_node_uses_supplied_portfolio_without_llm(mocker):
    mock_get_llm = mocker.patch("app.agents.router.get_llm")

    state = {"query": "how is my portfolio doing?", "portfolio": {"TATAMOTORS.NS": 10, "INFY.NS": 5}}
    result = router_node(state)

    assert result["intent"] == "portfolio"
    assert set(result["tickers"]) == {"TATAMOTORS.NS", "INFY.NS"}
    mock_get_llm.assert_not_called()


def test_router_node_classifies_and_resolves_tickers(mocker):
    classification = RouterOutput(intent="compare", companies=["Tata Motors", "Mahindra & Mahindra"])
    _mock_structured_llm(mocker, "app.agents.router", classification)
    mocker.patch(
        "app.agents.router.resolve_symbol",
        side_effect=lambda name: {"Tata Motors": "TATAMOTORS.NS", "Mahindra & Mahindra": "M&M.NS"}[name],
    )

    result = router_node({"query": "Compare Tata Motors & Mahindra, which should I buy?"})

    assert result["intent"] == "compare"
    assert result["tickers"] == ["TATAMOTORS.NS", "M&M.NS"]
    assert result["errors"] == []


def test_router_node_records_unresolved_companies(mocker):
    classification = RouterOutput(intent="single_stock", companies=["Some Unknown Startup"])
    _mock_structured_llm(mocker, "app.agents.router", classification)
    mocker.patch("app.agents.router.resolve_symbol", return_value=None)

    result = router_node({"query": "How is Some Unknown Startup doing?"})

    assert result["tickers"] == []
    assert len(result["errors"]) == 1
    assert "Some Unknown Startup" in result["errors"][0]


def test_router_node_handles_llm_exception(mocker):
    mocker.patch("app.agents.router.get_llm", side_effect=RuntimeError("gemini quota exceeded"))

    result = router_node({"query": "How is Reliance doing?"})

    assert result["intent"] == "single_stock"
    assert result["tickers"] == []
    assert "gemini quota exceeded" in result["errors"][0]


# ---------------------------------------------------------------------------
# fundamental_agent_node
# ---------------------------------------------------------------------------


def test_fundamental_agent_node_success(mocker):
    fake_data = {"ticker": "RELIANCE.NS", "trailingPE": 25.0, "sector": "Energy"}
    mocker.patch("app.agents.fundamental_agent.get_fundamentals", return_value=fake_data)
    _mock_structured_llm(
        mocker,
        "app.agents.fundamental_agent",
        FindingOutput(summary="Solid fundamentals", score=0.6, key_points=["Strong margins"]),
    )

    result = fundamental_agent_node({"ticker": "RELIANCE.NS"})

    assert not result.get("errors")
    finding = result["fundamental_findings"][0]
    assert finding["ticker"] == "RELIANCE.NS"
    assert finding["score"] == 0.6
    assert finding["raw_data"] == fake_data


def test_fundamental_agent_node_skips_ticker_with_data_error(mocker):
    mocker.patch(
        "app.agents.fundamental_agent.get_fundamentals",
        return_value={"error": "rate limited", "ticker": "BAD.NS"},
    )
    mock_get_llm = mocker.patch("app.agents.fundamental_agent.get_llm")

    result = fundamental_agent_node({"ticker": "BAD.NS"})

    assert not result.get("fundamental_findings")
    assert "rate limited" in result["errors"][0]
    mock_get_llm.assert_not_called()


def test_fundamental_agent_node_handles_llm_exception(mocker):
    mocker.patch("app.agents.fundamental_agent.get_fundamentals", return_value={"trailingPE": 10})
    mock_llm = mocker.MagicMock()
    mock_llm.with_structured_output.return_value.invoke.side_effect = RuntimeError("gemini quota exceeded")
    mocker.patch("app.agents.fundamental_agent.get_llm", return_value=mock_llm)

    result = fundamental_agent_node({"ticker": "RELIANCE.NS"})

    assert not result.get("fundamental_findings")
    assert "gemini quota exceeded" in result["errors"][0]


# ---------------------------------------------------------------------------
# technical_agent_node
# ---------------------------------------------------------------------------


def test_technical_agent_node_success(mocker):
    fake_indicators = {"ticker": "TCS.NS", "rsi_14": 55.0, "latest_close": 3800.0}
    mocker.patch("app.agents.technical_agent.get_technical_indicators", return_value=fake_indicators)
    _mock_structured_llm(
        mocker,
        "app.agents.technical_agent",
        FindingOutput(summary="Uptrend intact", score=0.4, key_points=["Price above SMA20"]),
    )

    result = technical_agent_node({"ticker": "TCS.NS"})

    assert not result.get("errors")
    finding = result["technical_findings"][0]
    assert finding["ticker"] == "TCS.NS"
    assert finding["score"] == 0.4
    assert finding["raw_data"] == fake_indicators


def test_technical_agent_node_skips_ticker_with_no_history(mocker):
    mocker.patch(
        "app.agents.technical_agent.get_technical_indicators",
        return_value={"error": "no_price_history", "ticker": "NEWLIST.NS"},
    )
    mock_get_llm = mocker.patch("app.agents.technical_agent.get_llm")

    result = technical_agent_node({"ticker": "NEWLIST.NS"})

    assert not result.get("technical_findings")
    assert "no_price_history" in result["errors"][0]
    mock_get_llm.assert_not_called()


# ---------------------------------------------------------------------------
# sentiment_agent_node
# ---------------------------------------------------------------------------


def test_sentiment_agent_node_success(mocker):
    fake_articles = [{"title": "Reliance beats estimates", "snippet": "Strong quarter", "url": "http://x"}]
    mocker.patch("app.agents.sentiment_agent.search_news", return_value=fake_articles)
    _mock_structured_llm(
        mocker,
        "app.agents.sentiment_agent",
        FindingOutput(summary="Positive sentiment", score=0.5, key_points=["Beat estimates"]),
    )

    result = sentiment_agent_node({"ticker": "RELIANCE.NS"})

    assert not result.get("errors")
    finding = result["sentiment_findings"][0]
    assert finding["ticker"] == "RELIANCE.NS"
    assert finding["raw_data"]["articles"] == fake_articles


def test_sentiment_agent_node_skips_ticker_on_search_error(mocker):
    mocker.patch(
        "app.agents.sentiment_agent.search_news", return_value=[{"error": "duckduckgo unreachable"}]
    )
    mock_get_llm = mocker.patch("app.agents.sentiment_agent.get_llm")

    result = sentiment_agent_node({"ticker": "RELIANCE.NS"})

    assert not result.get("sentiment_findings")
    assert "duckduckgo unreachable" in result["errors"][0]
    mock_get_llm.assert_not_called()


# ---------------------------------------------------------------------------
# master_agent_node
# ---------------------------------------------------------------------------


def test_master_agent_node_single_stock_has_no_verdict(mocker):
    _mock_structured_llm(
        mocker,
        "app.agents.master_agent",
        MasterOutput(final_answer="Reliance looks solid across the board."),
    )

    state = {
        "intent": "single_stock",
        "tickers": ["RELIANCE.NS"],
        "fundamental_findings": [],
        "technical_findings": [],
        "sentiment_findings": [],
    }
    result = master_agent_node(state)

    assert result["verdict"] is None
    assert "Reliance looks solid" in result["final_answer"]
    assert DISCLAIMER in result["final_answer"]


def test_master_agent_node_compare_populates_verdict(mocker):
    _mock_structured_llm(
        mocker,
        "app.agents.master_agent",
        MasterOutput(
            final_answer="Mahindra edges out Tata Motors on fundamentals.",
            recommendation="M&M.NS",
            confidence=0.7,
        ),
    )

    state = {
        "intent": "compare",
        "tickers": ["TATAMOTORS.NS", "M&M.NS"],
        "fundamental_findings": [],
        "technical_findings": [],
        "sentiment_findings": [],
    }
    result = master_agent_node(state)

    assert result["verdict"] == {"recommendation": "M&M.NS", "confidence": 0.7}
    assert DISCLAIMER in result["final_answer"]


def test_master_agent_node_handles_llm_exception(mocker):
    mocker.patch("app.agents.master_agent.get_llm", side_effect=RuntimeError("gemini quota exceeded"))

    state = {
        "intent": "single_stock",
        "tickers": ["RELIANCE.NS"],
        "fundamental_findings": [],
        "technical_findings": [],
        "sentiment_findings": [],
    }
    result = master_agent_node(state)

    assert result["verdict"] is None
    assert DISCLAIMER in result["final_answer"]
    assert "couldn't generate a full analysis" in result["final_answer"]
    assert "gemini quota exceeded" in result["errors"][0]


# ---------------------------------------------------------------------------
# _calibrate_verdict
# ---------------------------------------------------------------------------


def _finding(ticker: str, score: float) -> dict:
    return {"ticker": ticker, "summary": "", "score": score, "key_points": [], "raw_data": {}}


def test_calibrate_verdict_passes_through_when_no_findings():
    verdict = _calibrate_verdict(["A.NS", "B.NS"], [], [], [], "A.NS", 0.8)

    assert verdict == {"recommendation": "A.NS", "confidence": 0.8}


def test_calibrate_verdict_falls_back_to_numeric_leader_when_llm_is_silent():
    fundamental = [_finding("A.NS", 0.6), _finding("B.NS", 0.1)]

    verdict = _calibrate_verdict(["A.NS", "B.NS"], fundamental, [], [], None, None)

    assert verdict["recommendation"] == "A.NS"
    assert verdict["confidence"] == pytest.approx(min(0.5 + (0.6 - 0.1), 0.95), abs=0.01)


def test_calibrate_verdict_dampens_confidence_on_a_near_tie():
    fundamental = [_finding("A.NS", 0.21), _finding("B.NS", 0.20)]

    verdict = _calibrate_verdict(["A.NS", "B.NS"], fundamental, [], [], "A.NS", 0.9)

    assert verdict["recommendation"] == "A.NS"
    assert verdict["confidence"] == 0.55


def test_calibrate_verdict_blends_llm_confidence_with_score_gap_when_not_tied():
    fundamental = [_finding("A.NS", 0.8), _finding("B.NS", 0.1)]

    verdict = _calibrate_verdict(["A.NS", "B.NS"], fundamental, [], [], "A.NS", 0.9)

    score_based = round(min(0.5 + (0.8 - 0.1), 0.95), 2)
    assert verdict["recommendation"] == "A.NS"
    assert verdict["confidence"] == round((0.9 + score_based) / 2, 2)


def test_calibrate_verdict_clamps_confidence_to_valid_range():
    fundamental = [_finding("A.NS", 0.99), _finding("B.NS", -0.99)]

    verdict = _calibrate_verdict(["A.NS", "B.NS"], fundamental, [], [], "A.NS", 0.99)

    assert 0.0 <= verdict["confidence"] <= 1.0
