"""API tests via FastAPI's TestClient. Per rules.md: the analysis graph is mocked, no real
Gemini/yfinance/DuckDuckGo calls happen."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

FAKE_SINGLE_STOCK_RESULT = {
    "intent": "single_stock",
    "tickers": ["RELIANCE.NS"],
    "fundamental_findings": [
        {
            "ticker": "RELIANCE.NS",
            "summary": "Solid fundamentals",
            "score": 0.5,
            "key_points": ["Strong margins"],
            "raw_data": {"trailingPE": 25.0},
        }
    ],
    "technical_findings": [],
    "sentiment_findings": [],
    "final_answer": "Reliance is doing fine.\n\n_This is not financial advice._",
    "verdict": None,
    "errors": [],
}

FAKE_COMPARE_RESULT = {
    "intent": "compare",
    "tickers": ["TATAMOTORS.NS", "M&M.NS"],
    "fundamental_findings": [],
    "technical_findings": [],
    "sentiment_findings": [],
    "final_answer": "Mahindra edges out Tata Motors.",
    "verdict": {"recommendation": "M&M.NS", "confidence": 0.65},
    "errors": [],
}


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_success(mocker):
    mock_invoke = mocker.patch(
        "app.api.routes.analysis_graph.invoke", return_value=FAKE_SINGLE_STOCK_RESULT
    )

    response = client.post("/analyze", json={"query": "How is Reliance doing?"})

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "single_stock"
    assert body["tickers"] == ["RELIANCE.NS"]
    assert body["findings"]["fundamental"][0]["ticker"] == "RELIANCE.NS"
    assert body["verdict"] is None
    assert "not financial advice" in body["final_answer"]
    mock_invoke.assert_called_once_with({"query": "How is Reliance doing?"})


def test_analyze_rejects_empty_query():
    response = client.post("/analyze", json={"query": ""})

    assert response.status_code == 422


def test_portfolio_success(mocker):
    mock_invoke = mocker.patch(
        "app.api.routes.analysis_graph.invoke",
        return_value={**FAKE_SINGLE_STOCK_RESULT, "intent": "portfolio"},
    )

    response = client.post(
        "/portfolio",
        json={"holdings": [{"ticker": "TATAMOTORS.NS", "qty": 10}, {"ticker": "INFY.NS", "qty": 5}]},
    )

    assert response.status_code == 200
    assert response.json()["intent"] == "portfolio"
    mock_invoke.assert_called_once_with(
        {"query": "portfolio review", "portfolio": {"TATAMOTORS.NS": 10, "INFY.NS": 5}}
    )


def test_portfolio_rejects_empty_holdings():
    response = client.post("/portfolio", json={"holdings": []})

    assert response.status_code == 422


def test_compare_success(mocker):
    mock_invoke = mocker.patch(
        "app.api.routes.analysis_graph.invoke", return_value=FAKE_COMPARE_RESULT
    )

    response = client.post("/compare", json={"tickers": ["TATAMOTORS.NS", "M&M.NS"]})

    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == {"recommendation": "M&M.NS", "confidence": 0.65}
    mock_invoke.assert_called_once_with(
        {"query": "compare stocks", "intent": "compare", "tickers": ["TATAMOTORS.NS", "M&M.NS"]}
    )


def test_compare_requires_at_least_two_tickers():
    response = client.post("/compare", json={"tickers": ["RELIANCE.NS"]})

    assert response.status_code == 422
