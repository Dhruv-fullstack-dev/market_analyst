# Market Analyst

A multi-agent system for Indian equities: ask about a single stock, check how your portfolio is doing,
or compare two stocks and get a recommendation. A LangGraph orchestrator fans a query out to
fundamental/technical/sentiment analyst agents in parallel, then a master node synthesizes their
findings into one answer.

See [docs/architecture.md](docs/architecture.md) for the system design and [docs/todo.md](docs/todo.md)
for build-phase progress.

## Features

- **Fundamental analyst** — P/E, growth, margins, debt via `yfinance`
- **Technical analyst** — SMA/EMA/RSI/MACD, 52-week range via `yfinance` + `ta`
- **Sentiment analyst** — recent news tone via DuckDuckGo search
- **Master node** — synthesizes all three into a narrative answer, with a calibrated
  buy/prefer recommendation + confidence for stock-comparison queries
- **FastAPI backend** (`/health`, `/analyze`, `/portfolio`, `/compare`) and a **Streamlit UI** on top of it
- LLM: **Google Gemini** (free tier) via `langchain-google-genai`

## Setup

```bash
cp .env.example .env   # then fill in GOOGLE_API_KEY
make install
```

### Environment variables (`.env`, see `.env.example`)

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key (required for the agents to actually run) |
| `GEMINI_MODEL` | Gemini model name, default `gemini-2.0-flash` |
| `LOG_LEVEL`, `LOG_FILE` | Logging config — every run appends to `dump.log` at the project root |
| `BACKEND_URL` | Where the Streamlit UI finds the FastAPI backend, default `http://localhost:8000` |
| `QUOTE_CACHE_TTL_SECONDS`, `HISTORY_CACHE_TTL_SECONDS`, `FUNDAMENTALS_CACHE_TTL_SECONDS`, `SEARCH_CACHE_TTL_SECONDS` | TTL cache windows for yfinance/DuckDuckGo calls |
| `SEARCH_MAX_RESULTS` | Max news articles fetched per sentiment lookup |

## Running it

```bash
make dev       # FastAPI backend on http://localhost:8000 (see /docs for Swagger UI)
make frontend  # Streamlit UI on http://localhost:8501 (run this in a second terminal)
```

## Common commands

```bash
make test        # run the test suite (everything is mocked — no real Gemini/yfinance/DuckDuckGo calls)
make test-cov     # test suite with coverage report
make lint         # ruff check (backend + frontend)
make format       # ruff format + autofix
make docker-build # build the backend Docker image
make docker-run   # run the backend Docker image (uses .env)
make clean        # remove caches/pycache
```

Logs from every run are written to `dump.log` in the project root (see [docs/rules.md](docs/rules.md)).
