from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from pydantic import HttpUrl
import pytest

from middleware_api.api import Api
from middleware_api.business_logic import (
    ArcResponse,
    ArcStatus,
    CreateOrUpdateArcsResponse,
    BusinessLogicResponse,
    BusinessLogic
)
from middleware_api.arc_store.gitlab_api import GitlabApi, GitlabApiConfig
from ..shared_fixtures import cert # noqa: F401

@pytest.fixture
def middleware_api():
    return Api()

@pytest.fixture
def client(middleware_api):
    """TestClient-Fixture und sicheres Aufräumen der Dependency-Overrides."""
    with TestClient(middleware_api.app) as c:
        yield c
    middleware_api.app.dependency_overrides.clear()

@pytest.fixture
def service() -> BusinessLogic:
    store = MagicMock()
    store.exists.return_value = False
    return BusinessLogic(store)

@pytest.fixture
def mock_service(monkeypatch):
    """Mockt get_service() vollständig, ohne MiddlewareService zu referenzieren."""

    class DummyService:
        async def whoami(self, request, client_cert, accept_type):
            return BusinessLogicResponse(client_id="TestClient", message="ok")

        async def create_or_update_arcs(self, data, client_cert, content_type, accept_type):
            return CreateOrUpdateArcsResponse(
                client_id="TestClient",
                message="ok",
                arcs=[
                    ArcResponse(id="abc123", status=ArcStatus.created, timestamp="2025-01-01T00:00:00Z")
                ]
            )

    monkeypatch.setattr("app.middleware_api.get_service", lambda: DummyService())
    return DummyService()

@pytest.fixture
def api():
    """Erzeugt ein ARCPersistenceGitlabAPI mit gemocktem Gitlab."""
    api_config = GitlabApiConfig(
        url = HttpUrl("http://gitlab"),
        token = "token",
        group = "1",
        branch = "main"
    ) # nosec
    api = GitlabApi(api_config)
    api._gitlab = MagicMock()
    return api