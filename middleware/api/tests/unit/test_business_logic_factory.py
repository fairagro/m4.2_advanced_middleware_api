"""Unit tests for the BusinessLogicFactory."""

from unittest.mock import patch

from middleware.api.business_logic import BusinessLogic
from middleware.api.business_logic.business_logic_factory import BusinessLogicFactory
from middleware.api.config import Config


def test_factory_creates_api_mode() -> None:
    """Test factory creates API mode BusinessLogic with task sender."""
    config_data = {
        "log_level": "DEBUG",
        "gitlab_api": {
            "url": "https://gitlab.com",
            "group": "test-group",
            "token": "test-token",
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
        patch("middleware.api.business_logic.business_logic_factory.GitlabApi") as mock_gitlab_api,
        patch("middleware.api.business_logic.business_logic_factory.CeleryTaskDispatcher") as mock_dispatcher,
    ):
        bl = BusinessLogicFactory.create(config, mode="api")

        assert isinstance(bl, BusinessLogic)
        # pylint: disable=protected-access
        assert bl._arc_manager._dispatcher == mock_dispatcher.return_value  # noqa: SLF001
        assert bl._doc_store == mock_couch.return_value  # noqa: SLF001
        assert bl._arc_manager._store == mock_gitlab_api.return_value  # noqa: SLF001


def test_factory_creates_worker_mode() -> None:
    """Test factory creates Worker mode BusinessLogic without task sender."""
    config_data = {
        "log_level": "DEBUG",
        "gitlab_api": {
            "url": "https://gitlab.com",
            "group": "test-group",
            "token": "test-token",
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
        patch("middleware.api.business_logic.business_logic_factory.GitlabApi") as mock_gitlab_api,
    ):
        bl = BusinessLogicFactory.create(config, mode="worker")

        assert isinstance(bl, BusinessLogic)
        # pylint: disable=protected-access
        assert bl._arc_manager._dispatcher is None  # noqa: SLF001
        assert bl._doc_store == mock_couch.return_value  # noqa: SLF001
        assert bl._arc_manager._store == mock_gitlab_api.return_value  # noqa: SLF001


def test_factory_git_repo_config() -> None:
    """Test factory correctly initializes GitRepo if configured."""
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
        patch("middleware.api.business_logic.business_logic_factory.GitRepo") as mock_git_repo,
    ):
        bl = BusinessLogicFactory.create(config, mode="worker")

        assert isinstance(bl, BusinessLogic)
        # pylint: disable=protected-access
        assert bl._arc_manager._store == mock_git_repo.return_value  # noqa: SLF001
        assert bl._doc_store == mock_couch.return_value  # noqa: SLF001
