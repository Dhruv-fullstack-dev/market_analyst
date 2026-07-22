"""Unit tests for the Gemini rate limiter (core/rate_limit.py)."""

from app.core.rate_limit import RateLimiter


def test_allows_calls_up_to_max_without_sleeping(mocker):
    mock_sleep = mocker.patch("app.core.rate_limit.time.sleep")
    mocker.patch("app.core.rate_limit.time.monotonic", return_value=0.0)

    limiter = RateLimiter(max_calls=3, period_seconds=60.0)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    mock_sleep.assert_not_called()
    assert len(limiter._calls) == 3


def test_blocks_when_max_calls_reached_within_window(mocker):
    mock_sleep = mocker.patch("app.core.rate_limit.time.sleep")
    mocker.patch("app.core.rate_limit.time.monotonic", return_value=0.0)

    limiter = RateLimiter(max_calls=3, period_seconds=60.0)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()  # 4th call at the same instant must wait for the window to clear

    mock_sleep.assert_called_once()
    waited = mock_sleep.call_args[0][0]
    assert waited == 60.0


def test_does_not_block_once_old_calls_fall_outside_the_window(mocker):
    mock_sleep = mocker.patch("app.core.rate_limit.time.sleep")
    monotonic_mock = mocker.patch("app.core.rate_limit.time.monotonic")

    limiter = RateLimiter(max_calls=2, period_seconds=60.0)

    monotonic_mock.return_value = 0.0
    limiter.acquire()
    limiter.acquire()

    monotonic_mock.return_value = 70.0  # both prior calls have aged out of the 60s window
    limiter.acquire()

    mock_sleep.assert_not_called()
