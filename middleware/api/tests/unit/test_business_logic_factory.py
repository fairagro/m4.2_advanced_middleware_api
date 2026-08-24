"""Unit tests for the BusinessLogicFactory."""

from unittest.mock import MagicMock, patch

import pytest

from middleware.api.business_logic import BusinessLogic
from middleware.api.business_logic.business_logic_factory import BusinessLogicFactory
from middleware.api.config import Config

pytestmark = pytest.mark.filterwarnings("ignore:gitlab_api configuration is deprecated.*:DeprecationWarning")


def test_factory_creates_api_mode() -> None:
    """Test factory creates API mode BusinessLogic with injected adapters."""
    config_data = {
        "log_level": "DEBUG",
        "git_repo": {
            "url": "https://gitlab.com",
            "group": "test-group",
        },
        "couchdb": {
            "url": "http://localhost:5984",
        },
        "celery": {
            "broker_url": "memory://",
            "result_backend": "cache+memory://",
        },
    }
    config = Config.from_data(config_data)
    task_dispatcher = MagicMock()
    broker_health_checker = MagicMock()

    with (
        patch("middleware.api.business_logic.business_logic_factory.CouchDB") as mock_couch,
        patch("middleware.api.business_logic.business_logic_factory.create_arc_store") as mock_create_arc_store,
    ):
        mock_store = MagicMock()
        mock_create_arc_store.return_value = mock_store
        bl = BusinessLogicFactory.create(
            config,
            mode="api",
            task_dispatcher=task_dispatcher,
            broker_health_checker=broker_health_checker,
        )

        assert isinstance(bl, BusinessLogic)
        # pylint: disable=protected-access
        assert bl._arc_manager._dispatcher == task_dispatcher  # noqa: SLF001
        assert bl._broker_health_checker == broker_health_checker  # noqa: SLF001
        assert bl._doc_store == mock_couch.return_value  # noqa: SLF001
        assert bl._arc_manager._store == mock_store  # noqa: SLF001
        mock_create_arc_store.assert_called_once_with(config, mock_couch.return_value)


def test_factory_api_mode_requires_dispatcher() -> None:
    """Test factory fails fast if API mode has no task dispatcher."""
    config_data = {
        "log_level": "DEBUG",
        "git_repo": {
            "url": "https://gitlab.com",
            "group": "test-group",
        },
        "couchdb": {
            "url": "http://localhost:5984",
        },
        "celery": {
            "broker_url": "memory://",
            "result_backend": "cache+memory://",
        },
    }
    config = Config.from_data(config_data)

    with pytest.raises(ValueError, match="task_dispatcher"):
        BusinessLogicFactory.create(config, mode="api")


def test_factory_creates_worker_mode() -> None:
    """Test factory creates Worker mode BusinessLogic without task sender."""
    config_data = {
        "log_level": "DEBUG",
        "git_repo": {
            "url": "https://gitlab.com",
            "group": "test-group",
        },
        "couchdb": {
            "url": "http://localhost:5984",
        },
        "celery": {
            "broker_url": "memory://",
            "result_backend": "cache+memory://",
        },
    }
    config = Config.from_data(config_data)

    with (
        patch("middleware.api.business_logic.business_logic_factory.CouchDB") as mock_couch,
        patch("middleware.api.business_logic.business_logic_factory.create_arc_store") as mock_create_arc_store,
    ):
        mock_store = MagicMock()
        mock_create_arc_store.return_value = mock_store
        bl = BusinessLogicFactory.create(config, mode="worker")

        assert isinstance(bl, BusinessLogic)
        # pylint: disable=protected-access
        assert bl._arc_manager._dispatcher is None  # noqa: SLF001
        assert bl._doc_store == mock_couch.return_value  # noqa: SLF001
        assert bl._arc_manager._store == mock_store  # noqa: SLF001
        mock_create_arc_store.assert_called_once_with(config, mock_couch.return_value)


def test_factory_git_repo_config() -> None:
    """Test factory delegates ArcStore construction to create_arc_store."""
    config_data = {
        "log_level": "DEBUG",
        "git_repo": {
            "url": "https://github.com",
            "group": "test-group",
        },
        "couchdb": {
            "url": "http://localhost:5984",
        },
        "celery": {
            "broker_url": "memory://",
            "result_backend": "cache+memory://",
        },
    }
    config = Config.from_data(config_data)

    with (
        patch("middleware.api.business_logic.business_logic_factory.CouchDB") as mock_couch,
        patch("middleware.api.business_logic.business_logic_factory.create_arc_store") as mock_create_arc_store,
    ):
        mock_store = MagicMock()
        mock_create_arc_store.return_value = mock_store
        bl = BusinessLogicFactory.create(config, mode="worker")

        assert isinstance(bl, BusinessLogic)
        # pylint: disable=protected-access
        assert bl._arc_manager._store == mock_store  # noqa: SLF001
        mock_create_arc_store.assert_called_once_with(config, mock_couch.return_value)
        assert bl._doc_store == mock_couch.return_value  # noqa: SLF001
