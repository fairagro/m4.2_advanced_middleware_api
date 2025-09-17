"""Unit tests for the FAIRagro middleware API."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import HttpUrl

from middleware_api.api import Api
from middleware_api.arc_store.gitlab_api import GitlabApi, GitlabApiConfig
from middleware_api.business_logic import (
    ArcResponse,
    ArcStatus,
    BusinessLogic,
    BusinessLogicResponse,
    CreateOrUpdateArcsResponse,
)

from ..shared_fixtures import cert  # noqa: F401, pylint: disable=unused-import


@pytest.fixture
def middleware_api():
    """Provide the Middleware API instance for tests."""
    return Api()


@pytest.fixture
def client(middleware_api):  # pylint: disable=redefined-outer-name
    """Provide a TestClient for the Middleware API.

    Also ensure cleanup of dependency overrides.
    """
    with TestClient(middleware_api.app) as c:
        yield c
    middleware_api.app.dependency_overrides.clear()


@pytest.fixture
def service() -> BusinessLogic:
    """Provide a BusinessLogic instance with a mocked ArcStore."""
    store = MagicMock()
    store.exists.return_value = False
    store.create_or_update = AsyncMock()
    return BusinessLogic(store)


@pytest.fixture
def mock_service(monkeypatch):
    """Provide a mocked BusinessLogic service."""

    class DummyService:
        """Dummy service with mocked methods."""

        async def whoami(self, _request, _client_cert, _accept_type):
            """Mock whoami method."""
            return BusinessLogicResponse(client_id="TestClient", message="ok")

        async def create_or_update_arcs(
            self, _data, _client_cert, _content_type, _accept_type
        ):
            """Mock create_or_update_arcs method."""
            return CreateOrUpdateArcsResponse(
                client_id="TestClient",
                message="ok",
                arcs=[
                    ArcResponse(
                        id="abc123",
                        status=ArcStatus.CREATED,
                        timestamp="2025-01-01T00:00:00Z",
                    )
                ],
            )

    monkeypatch.setattr("app.middleware_api.get_service", DummyService)
    return DummyService()


@pytest.fixture
def gitlab_api():
    """Provide a GitlabApi instance with a mocked Gitlab client."""
    api_config = GitlabApiConfig(
        url=HttpUrl("http://gitlab"), token="token", group="1", branch="main"
    )  # nosec
    api = GitlabApi(api_config)
    api._gitlab = MagicMock()  # pylint: disable=protected-access
    return api
