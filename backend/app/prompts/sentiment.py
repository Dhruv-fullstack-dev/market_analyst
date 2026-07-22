SYSTEM_PROMPT = """You are a sentiment analyst for Indian equities. Given recent news headlines and \
snippets about a company, assess the overall tone (positive/negative/neutral) and note any notable \
events (earnings, regulatory action, management changes, litigation, etc). Score from -1 (very bearish) \
to +1 (very bullish). Base your assessment only on the articles provided; do not fabricate events."""


def build_sentiment_messages(ticker: str, articles: list[dict]) -> list[tuple[str, str]]:
    if articles:
        joined = "\n".join(f"- {a.get('title')}: {a.get('snippet')}" for a in articles)
    else:
        joined = "No recent news found."
    human = f"Ticker: {ticker}\nRecent news:\n{joined}"
    return [("system", SYSTEM_PROMPT), ("human", human)]
