"""Unit tests for CeleryBrokerHealthChecker long-lived AMQP connection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from middleware.api.celery_integration import CeleryBrokerHealthChecker


def _make_checker() -> tuple[CeleryBrokerHealthChecker, MagicMock, MagicMock]:
    """Build a checker with a mocked Celery app and kombu connection."""
    connection = MagicMock()
    celery_app = MagicMock()
    celery_app.connection.return_value = connection
    checker = CeleryBrokerHealthChecker(celery_app)
    return checker, celery_app, connection


def test_is_healthy_reuses_single_connection() -> None:
    """Health checks use one durable connection, not short-lived acquire/release."""
    checker, celery_app, connection = _make_checker()

    assert checker.is_healthy() is True
    assert checker.is_healthy() is True

    celery_app.connection.assert_called_once_with()
    celery_app.connection_or_acquire.assert_not_called()
    assert connection.ensure_connection.call_count == 2
    connection.ensure_connection.assert_called_with(max_retries=1)
    assert connection.heartbeat_check.call_count == 2
    connection.close.assert_not_called()


def test_is_healthy_returns_false_on_ensure_connection_failure() -> None:
    """Broker outages are reported as unhealthy."""
    checker, _celery_app, connection = _make_checker()
    connection.ensure_connection.side_effect = OSError("broker unreachable")

    with patch("middleware.api.celery_integration.logger") as mock_logger:
        assert checker.is_healthy() is False

    mock_logger.error.assert_called_once()
    connection.heartbeat_check.assert_not_called()


def test_is_healthy_returns_false_on_heartbeat_check_failure() -> None:
    """A dead connection detected via heartbeat_check is unhealthy."""
    checker, _celery_app, connection = _make_checker()
    connection.heartbeat_check.side_effect = ConnectionError("heartbeat lost")

    with patch("middleware.api.celery_integration.logger") as mock_logger:
        assert checker.is_healthy() is False

    connection.ensure_connection.assert_called_once_with(max_retries=1)
    mock_logger.error.assert_called_once()


def test_close_closes_durable_connection() -> None:
    """Shutdown performs a clean AMQP close on the durable connection."""
    checker, _celery_app, connection = _make_checker()

    checker.close()

    connection.close.assert_called_once_with()


def test_close_swallows_close_errors() -> None:
    """Close failures during shutdown are logged and do not raise."""
    checker, _celery_app, connection = _make_checker()
    connection.close.side_effect = OSError("already closed")

    with patch("middleware.api.celery_integration.logger") as mock_logger:
        checker.close()

    mock_logger.warning.assert_called_once()
