"""Integration test fixtures for API client."""

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient

# Import from the API package
from middleware.api.api import Api
from middleware.api.config import Config as ApiConfig

# Import from the API client package
from middleware.api_client.config import Config


@pytest.fixture
def client_config(test_config_dict: dict) -> Config:
    """Create a Config instance for testing.

    Uses the test_config_dict from the parent conftest.py
    """
    return Config.from_data(test_config_dict)


@pytest.fixture(scope="session")
def api_config(known_rdis: list[str], oid: Any) -> dict[str, Any]:
    """Provide API configuration for integration tests.

    Note: Uses the same known_rdis and oid fixtures from the parent conftest.py
    """
    return {
        "log_level": "DEBUG",
        "known_rdis": known_rdis,
        "client_auth_oid": oid.dotted_string,
        "gitlab_api": {
            "url": "https://fake-gitlab.example.com",
            "group": "test-group",
            "token": "fake-token",
            "branch": "main",
        },
    }


@pytest.fixture
def middleware_api(api_config: dict[str, Any]) -> Api:
    """Provide the Middleware API instance for testing.

    This creates a real API instance that can be used with TestClient.
    """
    config = ApiConfig.from_data(api_config)
    return Api(config)


@pytest.fixture
def api_test_client(middleware_api: Api) -> Generator[TestClient, None, None]:
    """Provide a TestClient for the Middleware API.

    This allows making HTTP requests to the API without a real server.
    """
    with TestClient(middleware_api.app) as client:
        yield client
