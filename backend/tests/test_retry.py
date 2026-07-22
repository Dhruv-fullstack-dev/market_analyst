"""Unit tests for the shared retry-with-backoff helper."""

import pytest
from app.core.retry import retry_with_backoff


@pytest.fixture(autouse=True)
def no_sleep(mocker):
    return mocker.patch("app.core.retry.time.sleep", return_value=None)


def test_retry_with_backoff_returns_result_on_first_success(mocker):
    func = mocker.MagicMock(return_value="ok")

    result = retry_with_backoff(func)

    assert result == "ok"
    assert func.call_count == 1


def test_retry_with_backoff_recovers_after_transient_failures(mocker):
    func = mocker.MagicMock(side_effect=[RuntimeError("a"), RuntimeError("b"), "ok"])

    result = retry_with_backoff(func, max_retries=3)

    assert result == "ok"
    assert func.call_count == 3


def test_retry_with_backoff_raises_last_exception_after_exhausting_retries(mocker):
    func = mocker.MagicMock(side_effect=[RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])

    with pytest.raises(RuntimeError, match="c"):
        retry_with_backoff(func, max_retries=3)

    assert func.call_count == 3


def test_retry_with_backoff_sleeps_with_linear_backoff(mocker):
    sleep_mock = mocker.patch("app.core.retry.time.sleep", return_value=None)
    func = mocker.MagicMock(side_effect=[RuntimeError("a"), RuntimeError("b"), "ok"])

    retry_with_backoff(func, max_retries=3, backoff_seconds=2.0)

    sleep_mock.assert_has_calls([mocker.call(2.0), mocker.call(4.0)])
