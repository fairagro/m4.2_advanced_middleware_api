"""Unit tests for the FAIRagro middleware API."""

import hashlib
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography import x509
from fastapi.testclient import TestClient
from pydantic import HttpUrl, SecretStr

from middleware_api.api import Api
from middleware_api.arc_store.gitlab_api import GitlabApi, GitlabApiConfig
from middleware_api.business_logic import (
    BusinessLogic,
)
from middleware_api.config import Config


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
