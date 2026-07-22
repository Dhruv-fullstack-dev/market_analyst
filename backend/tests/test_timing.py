"""Unit tests for the node-duration logging decorator."""

import logging

from app.core.timing import log_node_duration


def test_log_node_duration_returns_wrapped_result():
    @log_node_duration
    def sample_node(state):
        return {"ok": True, "state": state}

    result = sample_node({"tickers": ["RELIANCE.NS"]})

    assert result == {"ok": True, "state": {"tickers": ["RELIANCE.NS"]}}


def test_log_node_duration_logs_completion_with_elapsed_time(caplog):
    caplog.set_level(logging.INFO)

    @log_node_duration
    def sample_node(state):
        return state

    sample_node({})

    assert any("sample_node completed in" in record.message for record in caplog.records)


def test_log_node_duration_logs_even_when_wrapped_function_raises(caplog):
    caplog.set_level(logging.INFO)

    @log_node_duration
    def failing_node(state):
        raise RuntimeError("boom")

    try:
        failing_node({})
        raise AssertionError("expected RuntimeError to propagate")
    except RuntimeError:
        pass

    assert any("failing_node completed in" in record.message for record in caplog.records)


def test_log_node_duration_preserves_function_name():
    @log_node_duration
    def sample_node(state):
        return state

    assert sample_node.__name__ == "sample_node"
