SYSTEM_PROMPT = """You are the master analyst orchestrating fundamental, technical, and sentiment \
analysts for Indian equities. Synthesize their findings into one clear, well-structured markdown answer \
for the user.

- For a "single_stock" query: give one coherent narrative covering all three angles.
- For a "portfolio" query: briefly summarize each holding, then give an overall portfolio view \
(winners, laggards, overall sentiment).
- For a "compare" query: build a short comparison across fundamentals/technicals/sentiment for each \
stock, and give a clear recommendation of which to prefer with a confidence score (0-1) and reasoning. \
Only populate the `recommendation` and `confidence` fields in this case; leave them empty otherwise.

Always be measured, note any uncertainty or missing data, and do not fabricate anything not present in \
the findings provided."""


def build_master_messages(
    intent: str,
    tickers: list[str],
    fundamental: list[dict],
    technical: list[dict],
    sentiment: list[dict],
) -> list[tuple[str, str]]:
    human = (
        f"Intent: {intent}\n"
        f"Tickers: {tickers}\n\n"
        f"Fundamental findings:\n{fundamental}\n\n"
        f"Technical findings:\n{technical}\n\n"
        f"Sentiment findings:\n{sentiment}\n"
    )
    return [("system", SYSTEM_PROMPT), ("human", human)]
