"""Unit tests for GitlabApiConfig validation."""

import pytest
from pydantic import HttpUrl, SecretStr, ValidationError

from middleware.api.arc_store.gitlab_api import GitlabApiConfig


def test_gitlab_api_config_https_valid() -> None:
    """Test valid HTTPS URL."""
    config = GitlabApiConfig(
        url=HttpUrl("https://gitlab.example.com/"),
        group="mygroup",
        token=SecretStr("glpat-token"),
    )
    assert str(config.url) == "https://gitlab.example.com/"


def test_gitlab_api_config_http_valid() -> None:
    """Test valid HTTP URL."""
    config = GitlabApiConfig(
        url=HttpUrl("http://gitlab.example.com/"),
        group="mygroup",
        token=SecretStr("glpat-token"),
    )
    assert str(config.url) == "http://gitlab.example.com/"


def test_gitlab_api_config_file_invalid() -> None:
    """Test invalid file URL (HttpUrl itself usually catches this, but checking strict https validator)."""
    with pytest.raises(ValidationError):
        GitlabApiConfig(
            url=HttpUrl("file:///tmp"),
            group="mygroup",
            token=SecretStr("glpat-token"),
        )
