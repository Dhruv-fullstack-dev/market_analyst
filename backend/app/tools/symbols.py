"""Resolve company names / free-text tickers to Yahoo Finance symbols for Indian equities."""

import yfinance as yf

from app.agents.schemas import TickerGuessOutput
from app.core.llm import get_llm
from app.core.logging import get_logger
from app.prompts.symbol_guess import build_symbol_guess_messages

logger = get_logger(__name__)

# Curated NIFTY-50 (and a few common extras) name -> NSE symbol map.
# Lookup keys are lowercase; extend as needed.
NIFTY50_SYMBOLS: dict[str, str] = {
    "reliance": "RELIANCE.NS",
    "reliance industries": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "tata consultancy services": "TCS.NS",
    "infosys": "INFY.NS",
    "infy": "INFY.NS",
    "hdfc bank": "HDFCBANK.NS",
    "icici bank": "ICICIBANK.NS",
    "tata motors": "TATAMOTORS.NS",
    "mahindra": "M&M.NS",
    "mahindra & mahindra": "M&M.NS",
    "mahindra and mahindra": "M&M.NS",
    "m&m": "M&M.NS",
    "hindustan unilever": "HINDUNILVR.NS",
    "hul": "HINDUNILVR.NS",
    "state bank of india": "SBIN.NS",
    "sbi": "SBIN.NS",
    "bharti airtel": "BHARTIARTL.NS",
    "airtel": "BHARTIARTL.NS",
    "kotak mahindra bank": "KOTAKBANK.NS",
    "kotak bank": "KOTAKBANK.NS",
    "larsen & toubro": "LT.NS",
    "larsen and toubro": "LT.NS",
    "l&t": "LT.NS",
    "axis bank": "AXISBANK.NS",
    "itc": "ITC.NS",
    "asian paints": "ASIANPAINT.NS",
    "maruti suzuki": "MARUTI.NS",
    "maruti": "MARUTI.NS",
    "sun pharma": "SUNPHARMA.NS",
    "sun pharmaceutical": "SUNPHARMA.NS",
    "titan": "TITAN.NS",
    "titan company": "TITAN.NS",
    "ultratech cement": "ULTRACEMCO.NS",
    "wipro": "WIPRO.NS",
    "ntpc": "NTPC.NS",
    "power grid": "POWERGRID.NS",
    "power grid corporation": "POWERGRID.NS",
    "nestle india": "NESTLEIND.NS",
    "bajaj finance": "BAJFINANCE.NS",
    "bajaj finserv": "BAJAJFINSV.NS",
    "hcl technologies": "HCLTECH.NS",
    "hcltech": "HCLTECH.NS",
    "adani enterprises": "ADANIENT.NS",
    "adani ports": "ADANIPORTS.NS",
    "coal india": "COALINDIA.NS",
    "grasim industries": "GRASIM.NS",
    "grasim": "GRASIM.NS",
    "tata steel": "TATASTEEL.NS",
    "jsw steel": "JSWSTEEL.NS",
    "indusind bank": "INDUSINDBK.NS",
    "hindalco industries": "HINDALCO.NS",
    "hindalco": "HINDALCO.NS",
    "dr reddy's laboratories": "DRREDDY.NS",
    "dr reddys laboratories": "DRREDDY.NS",
    "dr reddys": "DRREDDY.NS",
    "cipla": "CIPLA.NS",
    "eicher motors": "EICHERMOT.NS",
    "bpcl": "BPCL.NS",
    "bharat petroleum": "BPCL.NS",
    "britannia industries": "BRITANNIA.NS",
    "britannia": "BRITANNIA.NS",
    "divi's laboratories": "DIVISLAB.NS",
    "divis laboratories": "DIVISLAB.NS",
    "shree cement": "SHREECEM.NS",
    "sbi life insurance": "SBILIFE.NS",
    "hdfc life insurance": "HDFCLIFE.NS",
    "apollo hospitals": "APOLLOHOSP.NS",
    "tech mahindra": "TECHM.NS",
    "upl": "UPL.NS",
    "hero motocorp": "HEROMOTOCO.NS",
    "heromotoco": "HEROMOTOCO.NS",
    # Common non-NIFTY-50 additions (rules.md Phase 6: expand beyond NIFTY-50).
    "zomato": "ZOMATO.NS",
    "paytm": "PAYTM.NS",
    "one97 communications": "PAYTM.NS",
    "nykaa": "NYKAA.NS",
    "fsn e-commerce": "NYKAA.NS",
    "irctc": "IRCTC.NS",
    "avenue supermarts": "DMART.NS",
    "dmart": "DMART.NS",
    "vedanta": "VEDL.NS",
    "ambuja cements": "AMBUJACEM.NS",
    "acc": "ACC.NS",
    "bank of baroda": "BANKBARODA.NS",
    "punjab national bank": "PNB.NS",
    "pnb": "PNB.NS",
    "canara bank": "CANBK.NS",
    "vodafone idea": "IDEA.NS",
    "yes bank": "YESBANK.NS",
    "idfc first bank": "IDFCFIRSTB.NS",
    "godrej consumer products": "GODREJCP.NS",
    "dabur india": "DABUR.NS",
    "dabur": "DABUR.NS",
    "marico": "MARICO.NS",
    "pidilite industries": "PIDILITIND.NS",
    "pidilite": "PIDILITIND.NS",
    "havells india": "HAVELLS.NS",
    "havells": "HAVELLS.NS",
    "voltas": "VOLTAS.NS",
    "trent": "TRENT.NS",
    "dlf": "DLF.NS",
    "interglobe aviation": "INDIGO.NS",
    "indigo": "INDIGO.NS",
    "jubilant foodworks": "JUBLFOOD.NS",
    "united spirits": "MCDOWELL-N.NS",
    "colgate-palmolive india": "COLPAL.NS",
    "colgate": "COLPAL.NS",
    "gail india": "GAIL.NS",
    "gail": "GAIL.NS",
    "indian oil corporation": "IOC.NS",
    "ioc": "IOC.NS",
    "ongc": "ONGC.NS",
    "ashok leyland": "ASHOKLEY.NS",
    "bharat electronics": "BEL.NS",
    "lupin": "LUPIN.NS",
    "aurobindo pharma": "AUROPHARMA.NS",
    "biocon": "BIOCON.NS",
    "federal bank": "FEDERALBNK.NS",
    "au small finance bank": "AUBANK.NS",
    "muthoot finance": "MUTHOOTFIN.NS",
    "pb fintech": "POLICYBZR.NS",
    "policybazaar": "POLICYBZR.NS",
}


def resolve_symbol(company_name: str) -> str | None:
    """Resolve a free-text company name or ticker to a Yahoo Finance symbol.

    Order: curated map -> direct ticker validation (.NS then .BO) -> LLM best-guess + validation.
    Returns None if nothing resolves.
    """
    key = company_name.strip().lower()
    if key in NIFTY50_SYMBOLS:
        symbol = NIFTY50_SYMBOLS[key]
        logger.info("Resolved '%s' -> '%s' via curated map", company_name, symbol)
        return symbol

    if _looks_like_ticker(company_name):
        symbol = _validate_with_suffixes(company_name.strip().upper())
        if symbol:
            logger.info("Resolved '%s' -> '%s' via direct ticker validation", company_name, symbol)
            return symbol

    symbol = _resolve_via_llm(company_name)
    if symbol:
        logger.info("Resolved '%s' -> '%s' via LLM guess + validation", company_name, symbol)
        return symbol

    logger.warning("Could not resolve ticker for '%s'", company_name)
    return None


def _resolve_via_llm(company_name: str) -> str | None:
    """Last-resort fallback: ask the LLM for a best-guess ticker, then verify it via yfinance.

    Never trusts the LLM's guess blindly, and never raises — any failure here just means
    resolution falls through to the caller's "could not resolve" path.
    """
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(TickerGuessOutput)
        guess: TickerGuessOutput = structured_llm.invoke(build_symbol_guess_messages(company_name))
    except Exception as exc:
        logger.warning("LLM ticker resolution failed for '%s': %s", company_name, exc)
        return None

    if not guess.ticker:
        return None

    return _validate_with_suffixes(guess.ticker.strip().upper())


def _validate_with_suffixes(base: str) -> str | None:
    for suffix in (".NS", ".BO"):
        candidate = base if base.endswith(suffix) else f"{base}{suffix}"
        if _validate_ticker(candidate):
            return candidate
    return None


def _looks_like_ticker(text: str) -> bool:
    stripped = text.strip().replace("&", "").replace(".", "")
    return bool(stripped) and stripped.isalnum() and " " not in text.strip() and len(stripped) <= 20


def _validate_ticker(symbol: str) -> bool:
    try:
        fast_info = yf.Ticker(symbol).fast_info
        last_price = fast_info.get("lastPrice") if hasattr(fast_info, "get") else None
        return last_price is not None
    except Exception as exc:
        logger.debug("Ticker validation failed for '%s': %s", symbol, exc)
        return False
