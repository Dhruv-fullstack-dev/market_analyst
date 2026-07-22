SYSTEM_PROMPT = """You identify Indian stock ticker symbols. Given a company name, respond with your \
best-guess NSE ticker symbol (the part before ".NS", e.g. "RELIANCE" for Reliance Industries). If you \
are not reasonably confident the company is listed on NSE/BSE, respond with null instead of guessing."""


def build_symbol_guess_messages(company_name: str) -> list[tuple[str, str]]:
    return [("system", SYSTEM_PROMPT), ("human", company_name)]
