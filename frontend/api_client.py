"""Thin HTTP client the Streamlit UI uses to call the FastAPI backend."""

import httpx
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

TIMEOUT = httpx.Timeout(60.0)


def analyze(query: str) -> dict:
    logger.info("Calling POST /analyze query=%r", query)
    response = httpx.post(f"{settings.backend_url}/analyze", json={"query": query}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def portfolio(holdings: dict[str, float]) -> dict:
    logger.info("Calling POST /portfolio holdings=%s", holdings)
    payload = {"holdings": [{"ticker": ticker, "qty": qty} for ticker, qty in holdings.items()]}
    response = httpx.post(f"{settings.backend_url}/portfolio", json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def compare(tickers: list[str]) -> dict:
    logger.info("Calling POST /compare tickers=%s", tickers)
    response = httpx.post(f"{settings.backend_url}/compare", json={"tickers": tickers}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()
