"""yfinance-backed market data tools: quotes, price history, fundamentals, technical indicators."""

import pandas as pd
import yfinance as yf

from app.core.cache import cached, make_ttl_cache
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.retry import retry_with_backoff

logger = get_logger(__name__)
settings = get_settings()

_quote_cache = make_ttl_cache(maxsize=256, ttl=settings.quote_cache_ttl_seconds)
_history_cache = make_ttl_cache(maxsize=256, ttl=settings.history_cache_ttl_seconds)
_fundamentals_cache = make_ttl_cache(maxsize=256, ttl=settings.fundamentals_cache_ttl_seconds)

_FUNDAMENTALS_FIELDS = [
    "longName",
    "sector",
    "industry",
    "trailingPE",
    "forwardPE",
    "trailingEps",
    "marketCap",
    "revenueGrowth",
    "earningsGrowth",
    "debtToEquity",
    "returnOnEquity",
    "dividendYield",
    "profitMargins",
]


@cached(_quote_cache)
def get_quote(ticker: str) -> dict:
    """Current price snapshot for a ticker. Returns {"error": ...} on failure."""
    logger.info("Fetching quote for %s", ticker)
    try:
        fast_info = retry_with_backoff(lambda: yf.Ticker(ticker).fast_info, label=f"get_quote({ticker})")
        price = fast_info.get("lastPrice")
        prev_close = fast_info.get("previousClose")
        change_percent = None
        if price is not None and prev_close:
            change_percent = round((price - prev_close) / prev_close * 100, 2)

        result = {
            "ticker": ticker,
            "price": price,
            "previous_close": prev_close,
            "change_percent": change_percent,
            "day_high": fast_info.get("dayHigh"),
            "day_low": fast_info.get("dayLow"),
        }
        logger.debug("Quote for %s: %s", ticker, result)
        return result
    except Exception as exc:
        logger.exception("Failed to fetch quote for %s", ticker)
        return {"error": str(exc), "ticker": ticker}


@cached(_history_cache)
def get_price_history(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """OHLCV price history. Returns an empty DataFrame on failure."""
    logger.info("Fetching price history for %s (period=%s, interval=%s)", ticker, period, interval)
    try:
        df = retry_with_backoff(
            lambda: yf.Ticker(ticker).history(period=period, interval=interval),
            label=f"get_price_history({ticker})",
        )
        if df.empty:
            logger.warning("Empty history returned for %s", ticker)
        return df
    except Exception:
        logger.exception("Failed to fetch price history for %s", ticker)
        return pd.DataFrame()


@cached(_fundamentals_cache)
def get_fundamentals(ticker: str) -> dict:
    """Key fundamental metrics for a ticker. Returns {"error": ...} on failure."""
    logger.info("Fetching fundamentals for %s", ticker)
    try:
        info = retry_with_backoff(lambda: yf.Ticker(ticker).info, label=f"get_fundamentals({ticker})")
        result = {"ticker": ticker, **{field: info.get(field) for field in _FUNDAMENTALS_FIELDS}}
        logger.debug("Fundamentals for %s: %s", ticker, result)
        return result
    except Exception as exc:
        logger.exception("Failed to fetch fundamentals for %s", ticker)
        return {"error": str(exc), "ticker": ticker}


def get_technical_indicators(ticker: str, period: str = "6mo") -> dict:
    """SMA/EMA/RSI/MACD + 52-week range computed from price history."""
    logger.info("Computing technical indicators for %s (period=%s)", ticker, period)
    history = get_price_history(ticker, period=period)
    if history.empty or "Close" not in history:
        logger.warning("No price history available to compute indicators for %s", ticker)
        return {"error": "no_price_history", "ticker": ticker}

    try:
        from ta.momentum import RSIIndicator
        from ta.trend import MACD, EMAIndicator, SMAIndicator

        close = history["Close"]
        result = {
            "ticker": ticker,
            "latest_close": round(float(close.iloc[-1]), 2),
            "sma_20": round(float(SMAIndicator(close, window=20).sma_indicator().iloc[-1]), 2)
            if len(close) >= 20
            else None,
            "sma_50": round(float(SMAIndicator(close, window=50).sma_indicator().iloc[-1]), 2)
            if len(close) >= 50
            else None,
            "ema_20": round(float(EMAIndicator(close, window=20).ema_indicator().iloc[-1]), 2)
            if len(close) >= 20
            else None,
            "rsi_14": round(float(RSIIndicator(close, window=14).rsi().iloc[-1]), 2)
            if len(close) >= 14
            else None,
            "macd": round(float(MACD(close).macd().iloc[-1]), 2) if len(close) >= 26 else None,
            "52_week_high": round(float(close.max()), 2),
            "52_week_low": round(float(close.min()), 2),
        }
        logger.debug("Indicators for %s: %s", ticker, result)
        return result
    except Exception as exc:
        logger.exception("Failed to compute indicators for %s", ticker)
        return {"error": str(exc), "ticker": ticker}
