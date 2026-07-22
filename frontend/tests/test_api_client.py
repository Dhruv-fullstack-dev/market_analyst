"""Unit tests for the Streamlit frontend's HTTP client. Per rules.md: httpx is always mocked."""

from unittest.mock import MagicMock

import api_client


def test_analyze_posts_query_and_returns_json(mocker):
    mock_response = MagicMock()
    mock_response.json.return_value = {"intent": "single_stock", "final_answer": "ok"}
    mock_post = mocker.patch("api_client.httpx.post", return_value=mock_response)

    result = api_client.analyze("How is Reliance doing?")

    assert result == {"intent": "single_stock", "final_answer": "ok"}
    mock_response.raise_for_status.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"query": "How is Reliance doing?"}


def test_portfolio_posts_holdings_as_list(mocker):
    mock_response = MagicMock()
    mock_response.json.return_value = {"intent": "portfolio"}
    mock_post = mocker.patch("api_client.httpx.post", return_value=mock_response)

    result = api_client.portfolio({"TATAMOTORS.NS": 10, "INFY.NS": 5})

    assert result == {"intent": "portfolio"}
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {
        "holdings": [{"ticker": "TATAMOTORS.NS", "qty": 10}, {"ticker": "INFY.NS", "qty": 5}]
    }


def test_compare_posts_tickers(mocker):
    mock_response = MagicMock()
    mock_response.json.return_value = {"intent": "compare"}
    mock_post = mocker.patch("api_client.httpx.post", return_value=mock_response)

    result = api_client.compare(["TATAMOTORS.NS", "M&M.NS"])

    assert result == {"intent": "compare"}
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == {"tickers": ["TATAMOTORS.NS", "M&M.NS"]}


def test_analyze_raises_on_http_error(mocker):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = RuntimeError("500 Internal Server Error")
    mocker.patch("api_client.httpx.post", return_value=mock_response)

    try:
        api_client.analyze("bad query")
        raise AssertionError("expected RuntimeError to propagate")
    except RuntimeError as exc:
        assert "500" in str(exc)
