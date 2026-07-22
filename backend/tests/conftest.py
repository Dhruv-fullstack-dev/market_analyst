"""Shared pytest fixtures for the backend test suite."""

import pytest


@pytest.fixture(autouse=True)
def no_gemini_rate_limit(mocker):
    """The real singleton rate limiter can block/sleep; keep every test instant regardless of
    how many LLM call sites a test exercises."""
    mock_limiter = mocker.MagicMock()
    for module_path in (
        "app.agents.router",
        "app.agents.fundamental_agent",
        "app.agents.technical_agent",
        "app.agents.sentiment_agent",
        "app.agents.master_agent",
        "app.tools.symbols",
    ):
        mocker.patch(f"{module_path}.get_rate_limiter", return_value=mock_limiter)
