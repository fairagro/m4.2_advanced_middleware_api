"""Shared fixtures for ApiClient unit tests."""

import pytest

from middleware.api_client import Config


@pytest.fixture
def client_config(test_config_dict: dict) -> Config:
    """Create a Config instance for testing."""
    return Config.from_data(test_config_dict)
