"""UI tests for the Streamlit app via Streamlit's AppTest harness.

Per rules.md: `api_client` (and therefore the backend/Gemini/yfinance/DuckDuckGo chain behind it)
is always mocked — these tests never make a real HTTP call.
"""

from streamlit.testing.v1 import AppTest

APP_PATH = "frontend/streamlit_app.py"

FAKE_SINGLE_STOCK_RESULT = {
    "intent": "single_stock",
    "tickers": ["RELIANCE.NS"],
    "findings": {
        "fundamental": [
            {
                "ticker": "RELIANCE.NS",
                "summary": "Solid fundamentals",
                "score": 0.5,
                "key_points": ["Strong margins"],
                "raw_data": {},
            }
        ],
        "technical": [],
        "sentiment": [],
    },
    "verdict": None,
    "final_answer": "Reliance is doing fine overall.",
    "errors": [],
}

FAKE_COMPARE_RESULT = {
    "intent": "compare",
    "tickers": ["M&M.NS", "TATAMOTORS.NS"],
    "findings": {"fundamental": [], "technical": [], "sentiment": []},
    "verdict": {"recommendation": "M&M.NS", "confidence": 0.65},
    "final_answer": "Mahindra edges out Tata Motors.",
    "errors": ["technical_agent: TATAMOTORS.NS: no_price_history"],
}

FAKE_PORTFOLIO_RESULT = {
    "intent": "portfolio",
    "tickers": ["TATAMOTORS.NS"],
    "findings": {"fundamental": [], "technical": [], "sentiment": []},
    "verdict": None,
    "final_answer": "Your portfolio is holding steady.",
    "errors": [],
}


def test_app_loads_without_error():
    at = AppTest.from_file(APP_PATH).run()

    assert not at.exception
    assert at.title[0].value == "📈 Market Analyst"


def test_ask_flow_renders_final_answer_and_findings(mocker):
    mocker.patch("api_client.analyze", return_value=FAKE_SINGLE_STOCK_RESULT)

    at = AppTest.from_file(APP_PATH).run()
    at.text_input(key="ask_query").set_value("How is Reliance doing?")
    at.button(key="analyze_button").click().run()

    assert not at.exception
    markdown_values = [m.value for m in at.markdown]
    assert "Reliance is doing fine overall." in markdown_values
    assert any("RELIANCE.NS" in value for value in markdown_values)


def test_ask_flow_shows_error_on_backend_failure(mocker):
    mocker.patch("api_client.analyze", side_effect=RuntimeError("backend down"))

    at = AppTest.from_file(APP_PATH).run()
    at.text_input(key="ask_query").set_value("How is Reliance doing?")
    at.button(key="analyze_button").click().run()

    assert not at.exception
    assert any("backend down" in e.value for e in at.error)


def test_compare_flow_renders_verdict_and_errors(mocker):
    mock_compare = mocker.patch("api_client.compare", return_value=FAKE_COMPARE_RESULT)

    at = AppTest.from_file(APP_PATH).run()
    at.button(key="compare_button").click().run()

    assert not at.exception
    assert mock_compare.called
    assert any("M&M.NS" in s.value for s in at.success)
    assert any("no_price_history" in w.value for w in at.warning)


def test_compare_same_ticker_warns_without_calling_backend(mocker):
    mock_compare = mocker.patch("api_client.compare")

    at = AppTest.from_file(APP_PATH).run()
    at.selectbox(key="compare_b").set_value(at.selectbox(key="compare_a").value)
    at.button(key="compare_button").click().run()

    assert not at.exception
    mock_compare.assert_not_called()
    assert any("different stocks" in w.value for w in at.warning)


def test_add_holding_and_portfolio_flow(mocker):
    mock_portfolio = mocker.patch("api_client.portfolio", return_value=FAKE_PORTFOLIO_RESULT)

    at = AppTest.from_file(APP_PATH).run()
    at.selectbox(key="holding_ticker").set_value("TATAMOTORS.NS")
    at.number_input(key="holding_qty").set_value(10.0)
    at.button(key="FormSubmitter:add_holding_form-Add holding").click().run()

    assert not at.exception
    assert at.session_state["holdings"] == {"TATAMOTORS.NS": 10.0}

    at.button(key="portfolio_button").click().run()

    assert not at.exception
    mock_portfolio.assert_called_once_with({"TATAMOTORS.NS": 10.0})
    assert any("holding steady" in m.value for m in at.markdown)
