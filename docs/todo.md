# Market Analyst — Phase-Wise TODO

Tracks implementation against [architecture.md](architecture.md). Check items off as they're completed.

---

## Phase 0 — Project Setup
- [x] Init `pyproject.toml` with deps: `langgraph`, `langchain`, `langchain-google-genai`, `yfinance`, `ddgs`, `fastapi`, `uvicorn`, `streamlit`, `pandas`, `ta`, `cachetools`, `httpx`, `pydantic`, `pydantic-settings`, `pytest` (LLM provider: **Gemini**, per rules.md's free-tier note)
- [x] `.env.example` with `GOOGLE_API_KEY`, `GEMINI_MODEL`, `BACKEND_URL`, log level/file, cache TTLs
- [x] `backend/app/core/config.py` — settings loader (pydantic `BaseSettings`)
- [x] `backend/app/core/logging.py` — logging config writing to `dump.log` (rules.md) + stdout
- [x] Repo scaffolding matching the layout in architecture.md (`backend/app/{core,tools}`, `backend/tests/`)
- [x] `README.md` with setup/run instructions
- [x] `.gitignore` (`.venv`, `.env`, `dump.log*`, caches)

---

## Phase 1 — Tool Layer (no agents yet)
- [x] `tools/symbols.py`: curated NIFTY-50 name→ticker dict + `.NS`/`.BO` fallback resolution
- [x] `tools/market_data.py`:
  - [x] `get_quote(ticker)`
  - [x] `get_price_history(ticker, period, interval)`
  - [x] `get_fundamentals(ticker)`
  - [x] `get_technical_indicators(ticker)` (SMA/EMA/RSI/MACD via `ta`)
  - [x] Wrap all with try/except → structured `{"error": ...}` on failure
  - [x] TTL cache (quotes ~1min, fundamentals ~1day) via `cachetools`
- [x] `tools/web_search.py`:
  - [x] `search_news(query, max_results)` via `ddgs`
  - [x] `search_general(query, max_results)`
  - [x] Retry/backoff + per-day cache
- [x] `core/cache.py` — shared TTLCache helper used by both tool modules
- [x] Unit tests: `tests/test_tools.py` (mock yfinance & DDGS responses, no live network calls — 15 tests, 95% coverage on `app/`)

---

## Phase 2 — Agent State & Nodes
- [x] `core/llm.py` — singleton Gemini chat model (`ChatGoogleGenerativeAI`), read from `Settings`
- [x] `agents/schemas.py` — `FindingOutput`/`RouterOutput`/`MasterOutput` pydantic models for `with_structured_output`
- [x] `agents/state.py` — `AnalysisState`, `AnalystFinding` TypedDicts with `operator.add` reducers
- [x] `prompts/` — prompt templates for router, fundamental, technical, sentiment, master
- [x] `agents/router.py` — intent classification (`single_stock`/`portfolio`/`compare`) + ticker extraction/resolution (skips LLM entirely if a `portfolio` dict is already supplied in state)
- [x] `agents/fundamental_agent.py` — calls `get_fundamentals`, LLM produces summary/score/key_points
- [x] `agents/technical_agent.py` — calls `get_technical_indicators`, LLM interprets trend
- [x] `agents/sentiment_agent.py` — calls `search_news`, LLM summarizes tone + notable events
- [x] `agents/master_agent.py`:
  - [x] Single-stock synthesis path
  - [x] Portfolio synthesis path (per-holding + aggregate view)
  - [x] Compare synthesis path (comparison table + verdict + confidence)
  - [x] Always append "not financial advice" disclaimer
- [x] Unit tests: `tests/test_agents.py` — each node tested in isolation, Gemini LLM fully mocked (12 tests, 100% coverage on router/fundamental/master, 89% on technical/sentiment — only the per-ticker loop's unreached branches uncovered)

---

## Phase 3 — LangGraph Wiring
- [x] `agents/graph.py`: build `StateGraph(AnalysisState)`, add router + 3 analyst nodes + master node
- [x] Wire fan-out edges (router → fundamental/technical/sentiment) and fan-in (all three → master)
- [x] Compile graph once (module-level `app = graph.compile()`)
- [x] Smoke test via `tests/test_graph.py::graph_app.invoke()` for all 3 intents (single_stock, portfolio, compare)
- [x] Verify concurrent branches don't clobber shared state (confirmed: `operator.add` reducers merge all 3 analysts' findings correctly)
- [x] Error propagation test: technical tool fails, master still returns a partial answer + `errors` populated (`test_graph_survives_one_analyst_failing`)
- [x] (rules.md #4) `Makefile` — `install`/`dev`/`frontend`/`test`/`test-cov`/`lint`/`format`/`docker-build`/`docker-run`/`clean`, plus `ruff` added as the lint/format tool and a `Dockerfile`/`.dockerignore` for `docker-build`

---

## Phase 4 — FastAPI Backend
- [x] `api/schemas.py` — Pydantic request/response models matching architecture.md §7
- [x] `api/routes.py`:
  - [x] `GET /health`
  - [x] `POST /analyze`
  - [x] `POST /portfolio`
  - [x] `POST /compare`
- [x] `main.py` — FastAPI app init (lifespan startup/shutdown logging), mount routes; graph compiles at import time
- [x] `agents/router.py` — added a bypass so `router_node` skips LLM classification when `intent`+`tickers` are already forced in state (needed so `/compare` doesn't waste a Gemini call re-classifying tickers it was already given)
- [x] `tests/test_api.py` using `TestClient` — 7 tests, `analysis_graph.invoke` mocked (no real Gemini/yfinance/DDG calls)
- [x] Manual test via `curl`/Swagger UI (`/docs`) — verified `/health` (200), all 4 routes registered, `/docs` loads (200), and invalid payloads on `/analyze`/`/compare` correctly 422 *before* reaching the graph. **Did not** exercise valid `/analyze`/`/portfolio`/`/compare` payloads against the real graph — no `.env`/`GOOGLE_API_KEY` is configured yet, and doing so would burn real (limited) Gemini quota per rules.md; revisit once a key is added, if you want a live end-to-end check

---

## Phase 5 — Streamlit Frontend
- [x] `frontend/api_client.py` — thin `httpx` wrapper (`analyze`/`portfolio`/`compare`) so backend calls are unit-testable in isolation from the UI
- [x] `frontend/streamlit_app.py` skeleton — page config, title, query input (used `st.text_input` + button rather than `st.chat_input`, since `chat_input` doesn't play well inside `st.tabs`)
- [x] Chat flow: free-text query → POST `/analyze` → render `final_answer` (markdown)
- [x] Expandable sections per analyst (fundamental/technical/sentiment) showing ticker/score/summary/key_points
- [x] Sidebar: portfolio holdings form (curated NIFTY-50 dropdown + custom-ticker override, qty, add/remove), stored in `st.session_state`
- [x] "How is my portfolio doing?" button → POST `/portfolio` with session holdings
- [x] Compare mode: two-ticker picker (same curated dropdown) → POST `/compare`, render comparison narrative + verdict banner (`st.success`) + any `errors` (`st.warning`)
- [x] Loading states / spinners (`st.spinner`) while each backend call is in flight
- [x] Basic error display (`st.error`) if the backend call raises or returns `errors`
- [x] Tests: `frontend/tests/test_api_client.py` (4 tests, `httpx.post` mocked) + `frontend/tests/test_streamlit_app.py` (6 tests via Streamlit's `AppTest` harness — drives real widget interactions: query→analyze, compare incl. "same ticker" guard, add-holding form→portfolio button, and the error-display path — `api_client` mocked throughout, no real HTTP/Gemini/yfinance/DDG calls)
- [x] `pyproject.toml`: added `frontend/tests` to `testpaths` and `frontend` to `pythonpath` so `import api_client` resolves under pytest; `streamlit_app.py` also inserts its own directory into `sys.path` defensively since `AppTest` (unlike `streamlit run`) doesn't do this automatically
- [x] Manual smoke test: started the real backend (`uvicorn`, :8123) and the real `streamlit run` dev server (:8501) — both booted cleanly, `/health` and the Streamlit page shell both returned 200, `dump.log` shows both processes' startup logging. **Did not** click through `/analyze`/`/portfolio`/`/compare` on the live pair (no browser/screenshot tool is available in this environment, and doing it via raw HTTP would burn real yfinance/DuckDuckGo calls and attempt a real Gemini call for no benefit beyond what the mocked `AppTest` suite already proves) — worth a manual click-through once you have a `GOOGLE_API_KEY` in `.env` and a browser handy

---

## Phase 6 — Hardening & Polish
- [x] `core/retry.py` — shared `retry_with_backoff()` (3 attempts, linear backoff), wired into `market_data.get_quote/get_price_history/get_fundamentals` and `web_search.search_news/search_general` (replacing web_search's own ad-hoc retry loop)
- [x] Expanded `symbols.py` with ~35 well-known non-NIFTY-50 tickers (Zomato, Paytm, Nykaa, IRCTC, DMart, Vedanta, PSU banks, etc.); added an LLM fallback (`_resolve_via_llm` + new `TickerGuessOutput` schema + `prompts/symbol_guess.py`) for multi-word names the curated map and direct-ticker check both miss — the LLM's guess is always re-validated against yfinance before being trusted, never returned blind
- [x] `master_agent.py`: `_calibrate_verdict()` — deterministic post-processing of the LLM's compare verdict using each ticker's average finding score: falls back to the numeric leader if the LLM doesn't commit to a `recommendation`, dampens confidence to ≤0.55 on a near-tie (score gap < 0.05), blends LLM confidence with the score-gap-derived confidence otherwise, and clamps to [0,1]
- [x] `core/timing.py` — `log_node_duration` decorator (latency in ms) applied to all 5 graph nodes (router, fundamental/technical/sentiment analysts, master); cache hit/miss logging already existed from Phase 1 (`core/cache.py`)
- [x] Tests: `test_retry.py` (4), `test_timing.py` (4), plus new cases in `test_tools.py` (retry-recovers-after-transient-failure ×2, LLM-fallback success/no-guess/exception ×3) and `test_agents.py` (`_calibrate_verdict` ×5) — 66 tests total now, 96% coverage, all mocked per rules.md
- [ ] End-to-end manual test of all 3 example queries from architecture.md §9 via the running Streamlit app — **still blocked**: no `GOOGLE_API_KEY` configured in `.env`, and this can't be faked without spending real (limited) Gemini quota; do this yourself once you add a key
- [x] README finalization: features list, env var reference table, `make dev`/`make frontend` run instructions (no longer gated on "once Phase N lands"), `make test`/`lint`/`docker-*` commands

---

## Phase 7 — Stretch (Post-MVP, Optional)
User selected only the `Send()` fan-out item to implement now; the other 4 remain optional/unimplemented (SQLite portfolio persistence, Redis cache, FastAPI auth, Streamlit charting) — revisit if/when needed.

- [x] Per-ticker dynamic fan-out inside analyst nodes using LangGraph `Send()` for true per-symbol parallelism:
  - [x] `agents/state.py` — added a transient `ticker: str` field (only present on the per-Send state a single analyst invocation receives, never on the persistent router/master-level state)
  - [x] `agents/fundamental_agent.py` / `technical_agent.py` / `sentiment_agent.py` — rewritten from "loop over `state['tickers']`, return accumulated lists" to "handle exactly one `state['ticker']`, return a 0-or-1-item list (or an error)" — each is now dispatched once per ticker instead of internally looping
  - [x] `agents/graph.py` — replaced the 3 static `router -> analyst` edges with `add_conditional_edges("router", fan_out_to_analysts)`; `fan_out_to_analysts()` returns one `Send(analyst_node, {**state, "ticker": t})` per (ticker, analyst-type) pair — a portfolio/compare query with N tickers now dispatches N×3 independent parallel branches instead of 3 branches that each loop over N tickers internally
  - [x] Edge case caught during design + fixed: with zero resolvable tickers, no analyst Sends fire at all, so `master` (only reachable via the analysts' static `-> master` edges) would never run and the graph would silently return no `final_answer`. Fixed by having `fan_out_to_analysts` return `[Send("master", state)]` directly when `tickers` is empty — verified via `test_graph_end_to_end_with_no_resolvable_tickers_still_reaches_master`
  - [x] Tests: `test_agents.py`'s fundamental/technical/sentiment node tests updated for the new single-`ticker` signature (18 tests updated); `test_graph.py` gained direct unit tests of `fan_out_to_analysts` itself (dispatch shape + empty-ticker fallback) plus the new empty-ticker end-to-end test — 69 tests total, 96% coverage, `graph.py` at 100%, all mocked per rules.md
  - [x] Manually verified via a standalone script (not committed) that 2 tickers produce exactly 6 distinct analyst log lines (one `Running {type} analysis for {ticker}` per (ticker, analyst) pair) before wiring the pytest coverage above
