"""Unit tests for the tool layer. Per rules.md: everything is mocked, no live network calls."""

import pandas as pd
import pytest
from app.tools import market_data, symbols, web_search


@pytest.fixture(autouse=True)
def clear_caches():
    """Every tool cache is module-level; reset between tests so mocks don't leak across cases."""
    market_data._quote_cache.clear()
    market_data._history_cache.clear()
    market_data._fundamentals_cache.clear()
    web_search._news_cache.clear()
    web_search._general_cache.clear()
    yield


@pytest.fixture(autouse=True)
def no_retry_sleep(mocker):
    """retry_with_backoff sleeps between attempts; stub it out so error-path tests stay instant."""
    mocker.patch("app.core.retry.time.sleep", return_value=None)


# ---------------------------------------------------------------------------
# market_data.get_quote
# ---------------------------------------------------------------------------


def test_get_quote_success(mocker):
    fake_fast_info = {
        "lastPrice": 2500.0,
        "previousClose": 2450.0,
        "dayHigh": 2510.0,
        "dayLow": 2440.0,
    }
    mock_ticker = mocker.MagicMock()
    mock_ticker.fast_info = fake_fast_info
    mocker.patch("app.tools.market_data.yf.Ticker", return_value=mock_ticker)

    result = market_data.get_quote("RELIANCE.NS")

    assert result["ticker"] == "RELIANCE.NS"
    assert result["price"] == 2500.0
    assert result["change_percent"] == pytest.approx(2.04, rel=1e-2)


def test_get_quote_handles_error(mocker):
    mock_ticker_ctor = mocker.patch(
        "app.tools.market_data.yf.Ticker", side_effect=RuntimeError("boom")
    )

    result = market_data.get_quote("BADTICKER.NS")

    assert "error" in result
    assert result["ticker"] == "BADTICKER.NS"
    assert mock_ticker_ctor.call_count == 3  # exhausted all retries


def test_get_quote_recovers_after_transient_failure(mocker):
    mock_ticker = mocker.MagicMock()
    mock_ticker.fast_info = {"lastPrice": 100.0, "previousClose": 100.0}
    mocker.patch(
        "app.tools.market_data.yf.Ticker", side_effect=[RuntimeError("transient"), mock_ticker]
    )

    result = market_data.get_quote("RECOVER.NS")

    assert result["price"] == 100.0
    assert "error" not in result


def test_get_quote_is_cached(mocker):
    mock_ticker = mocker.MagicMock()
    mock_ticker.fast_info = {"lastPrice": 100.0, "previousClose": 100.0}
    ticker_ctor = mocker.patch("app.tools.market_data.yf.Ticker", return_value=mock_ticker)

    market_data.get_quote("TCS.NS")
    market_data.get_quote("TCS.NS")

    assert ticker_ctor.call_count == 1


# ---------------------------------------------------------------------------
# market_data.get_price_history
# ---------------------------------------------------------------------------


def test_get_price_history_success(mocker):
    df = pd.DataFrame({"Close": [100, 101, 102]})
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = df
    mocker.patch("app.tools.market_data.yf.Ticker", return_value=mock_ticker)

    result = market_data.get_price_history("INFY.NS")

    assert not result.empty
    assert list(result["Close"]) == [100, 101, 102]


def test_get_price_history_handles_error(mocker):
    mocker.patch("app.tools.market_data.yf.Ticker", side_effect=RuntimeError("boom"))

    result = market_data.get_price_history("BAD.NS")

    assert result.empty


# ---------------------------------------------------------------------------
# market_data.get_fundamentals
# ---------------------------------------------------------------------------


def test_get_fundamentals_success(mocker):
    mock_ticker = mocker.MagicMock()
    mock_ticker.info = {"trailingPE": 25.3, "marketCap": 1_000_000, "sector": "Energy"}
    mocker.patch("app.tools.market_data.yf.Ticker", return_value=mock_ticker)

    result = market_data.get_fundamentals("RELIANCE.NS")

    assert result["trailingPE"] == 25.3
    assert result["sector"] == "Energy"


def test_get_fundamentals_handles_error(mocker):
    mocker.patch("app.tools.market_data.yf.Ticker", side_effect=RuntimeError("boom"))

    result = market_data.get_fundamentals("BAD.NS")

    assert "error" in result


# ---------------------------------------------------------------------------
# market_data.get_technical_indicators
# ---------------------------------------------------------------------------


def test_get_technical_indicators_insufficient_history(mocker):
    df = pd.DataFrame({"Close": [100.0, 101.0, 102.0]})
    mocker.patch("app.tools.market_data.get_price_history", return_value=df)

    result = market_data.get_technical_indicators("TCS.NS")

    assert result["sma_20"] is None
    assert result["latest_close"] == 102.0


def test_get_technical_indicators_no_history(mocker):
    mocker.patch("app.tools.market_data.get_price_history", return_value=pd.DataFrame())

    result = market_data.get_technical_indicators("TCS.NS")

    assert "error" in result


# ---------------------------------------------------------------------------
# symbols.resolve_symbol
# ---------------------------------------------------------------------------


def test_resolve_symbol_from_curated_map():
    assert symbols.resolve_symbol("Tata Motors") == "TATAMOTORS.NS"
    assert symbols.resolve_symbol("reliance") == "RELIANCE.NS"
    assert symbols.resolve_symbol("M&M") == "M&M.NS"


def test_resolve_symbol_direct_ticker(mocker):
    mock_ticker = mocker.MagicMock()
    mock_ticker.fast_info = {"lastPrice": 500.0}
    mocker.patch("app.tools.symbols.yf.Ticker", return_value=mock_ticker)

    assert symbols.resolve_symbol("SOMENEWCO") == "SOMENEWCO.NS"


def test_resolve_symbol_unresolvable(mocker):
    mocker.patch("app.tools.symbols.yf.Ticker", side_effect=RuntimeError("not found"))
    mocker.patch("app.tools.symbols._resolve_via_llm", return_value=None)

    assert symbols.resolve_symbol("totally unknown company name") is None


def test_resolve_symbol_llm_fallback_success(mocker):
    from app.agents.schemas import TickerGuessOutput

    mock_structured = mocker.MagicMock()
    mock_structured.invoke.return_value = TickerGuessOutput(ticker="BAJAJHIND")
    mock_llm = mocker.MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mocker.patch("app.tools.symbols.get_llm", return_value=mock_llm)

    mock_ticker = mocker.MagicMock()
    mock_ticker.fast_info = {"lastPrice": 42.0}
    mocker.patch("app.tools.symbols.yf.Ticker", return_value=mock_ticker)

    assert symbols.resolve_symbol("Some Obscure Multi Word Company") == "BAJAJHIND.NS"


def test_resolve_symbol_llm_fallback_no_guess(mocker):
    from app.agents.schemas import TickerGuessOutput

    mock_structured = mocker.MagicMock()
    mock_structured.invoke.return_value = TickerGuessOutput(ticker=None)
    mock_llm = mocker.MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_get_llm = mocker.patch("app.tools.symbols.get_llm", return_value=mock_llm)
    mock_ticker_ctor = mocker.patch("app.tools.symbols.yf.Ticker")

    assert symbols.resolve_symbol("Some Obscure Multi Word Company") is None
    mock_get_llm.assert_called_once()
    mock_ticker_ctor.assert_not_called()


def test_resolve_symbol_llm_fallback_handles_llm_exception(mocker):
    mocker.patch("app.tools.symbols.get_llm", side_effect=RuntimeError("gemini quota exceeded"))

    assert symbols.resolve_symbol("Some Obscure Multi Word Company") is None


# ---------------------------------------------------------------------------
# web_search.search_news / search_general
# ---------------------------------------------------------------------------


def test_search_news_success(mocker):
    fake_results = [
        {"title": "Reliance hits new high", "url": "http://x", "body": "...", "date": "2026-07-20"}
    ]
    mock_ddgs = mocker.MagicMock()
    mock_ddgs.__enter__.return_value = mock_ddgs
    mock_ddgs.news.return_value = fake_results
    mocker.patch("app.tools.web_search.DDGS", return_value=mock_ddgs)

    result = web_search.search_news("Reliance Industries")

    assert result[0]["title"] == "Reliance hits new high"


def test_search_news_handles_error(mocker):
    mock_ddgs = mocker.MagicMock()
    mock_ddgs.__enter__.return_value = mock_ddgs
    mock_ddgs.news.side_effect = RuntimeError("network down")
    mocker.patch("app.tools.web_search.DDGS", return_value=mock_ddgs)

    result = web_search.search_news("Some Company")

    assert "error" in result[0]
    assert mock_ddgs.news.call_count == 3  # exhausted all retries


def test_search_news_recovers_after_transient_failure(mocker):
    mock_ddgs = mocker.MagicMock()
    mock_ddgs.__enter__.return_value = mock_ddgs
    mock_ddgs.news.side_effect = [
        RuntimeError("transient"),
        [{"title": "Recovered", "url": "http://x", "body": "..."}],
    ]
    mocker.patch("app.tools.web_search.DDGS", return_value=mock_ddgs)

    result = web_search.search_news("Some Company")

    assert result[0]["title"] == "Recovered"
    assert mock_ddgs.news.call_count == 2


def test_search_general_success(mocker):
    fake_results = [{"title": "Some article", "href": "http://y", "body": "snippet"}]
    mock_ddgs = mocker.MagicMock()
    mock_ddgs.__enter__.return_value = mock_ddgs
    mock_ddgs.text.return_value = fake_results
    mocker.patch("app.tools.web_search.DDGS", return_value=mock_ddgs)

    result = web_search.search_general("Indian stock market news")

    assert result[0]["title"] == "Some article"
