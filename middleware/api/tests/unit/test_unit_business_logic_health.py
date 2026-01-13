"""Unit tests for the check_health functionality in BusinessLogic."""

from unittest.mock import MagicMock

from middleware.api.arc_store import ArcStore
from middleware.api.business_logic import BusinessLogic


def test_check_health_success() -> None:
    """Test check_health when store returns True."""
    store = MagicMock(spec=ArcStore)
    store.check_health.return_value = True
    logic = BusinessLogic(store)

    assert logic.check_health() is True
    store.check_health.assert_called_once()


def test_check_health_failure() -> None:
    """Test check_health when store returns False."""
    store = MagicMock(spec=ArcStore)
    store.check_health.return_value = False
    logic = BusinessLogic(store)

    assert logic.check_health() is False
    store.check_health.assert_called_once()
