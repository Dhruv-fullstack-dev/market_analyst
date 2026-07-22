SYSTEM_PROMPT = """You are a fundamental analyst for Indian equities. Given raw fundamental data for a \
stock (P/E, EPS, market cap, revenue/earnings growth, debt/equity, margins, sector), produce a concise \
assessment of the company's fundamental health. Score from -1 (very bearish) to +1 (very bullish). Base \
your assessment only on the data provided; do not fabricate figures."""


def build_fundamental_messages(ticker: str, data: dict) -> list[tuple[str, str]]:
    human = f"Ticker: {ticker}\nFundamental data:\n{data}"
    return [("system", SYSTEM_PROMPT), ("human", human)]
