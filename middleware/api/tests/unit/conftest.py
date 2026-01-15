"""Unit tests for the FAIRagro middleware API."""

import hashlib
import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography import x509
from fastapi.testclient import TestClient
from pydantic import HttpUrl, SecretStr

from middleware.api.api import Api
from middleware.api.arc_store.gitlab_api import GitlabApi, GitlabApiConfig
from middleware.api.business_logic import (
    BusinessLogic,
)
from middleware.api.config import CeleryConfig, Config


@pytest.fixture(scope="session", autouse=True)
def setup_test_config() -> Generator[None, None, None]:
    """Create a temporary config file for tests and set MIDDLEWARE_API_CONFIG env var."""
    # Create a minimal config file for celery_app to load
    config_content = """
log_level: DEBUG
known_rdis: []
gitlab_api:
  url: http://localhost
  token: test-token
  group: test-group
  branch: main
celery:
  broker_url: amqp://guest:guest@localhost:5672//
  result_backend: redis://localhost:6379/0
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        temp_config_path = f.name

    # Set environment variable before any imports happen
    os.environ["MIDDLEWARE_API_CONFIG"] = temp_config_path

    yield

    # Cleanup
    Path(temp_config_path).unlink(missing_ok=True)


@pytest.fixture
def config(oid: x509.ObjectIdentifier, known_rdis: list[str]) -> Config:
    """Provide a test Config instance with dummy values."""
    return Config(
        log_level="DEBUG",
        known_rdis=known_rdis,
        client_auth_oid=oid,
        gitlab_api=GitlabApiConfig(
            url=HttpUrl("http://localhost:8080"),
            token=SecretStr("test-token"),
            group="test-group",
            branch="main",
        ),
        celery=CeleryConfig(
            broker_url=SecretStr("amqp://guest:guest@localhost:5672//"),
            result_backend=SecretStr("redis://localhost:6379/0"),
        ),
    )


@pytest.fixture
def middleware_api(config: Config) -> Api:
    """Provide the Middleware API instance for tests."""
    return Api(config)


@pytest.fixture
def client(
    middleware_api: Api,
) -> Generator[TestClient, None, None]:  # pylint: disable=redefined-outer-name
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
    store.arc_id = MagicMock(
        side_effect=lambda identifier, rdi: hashlib.sha256(f"{identifier}:{rdi}".encode()).hexdigest()
    )
    store.exists.return_value = False
    store.create_or_update = AsyncMock()
    return BusinessLogic(store)


@pytest.fixture
def gitlab_api() -> GitlabApi:
    """Provide a GitlabApi instance with a mocked Gitlab client."""
    api_config = GitlabApiConfig(url=HttpUrl("http://gitlab"), token=SecretStr("token"), group="1", branch="main")  # nosec
    api = GitlabApi(api_config)
    api._gitlab = MagicMock()  # pylint: disable=protected-access
    return api
