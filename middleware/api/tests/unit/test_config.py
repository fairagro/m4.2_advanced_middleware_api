"""Unit tests for the API configuration module.

Tests cover:
- RDI identifier validation
- Client authentication OID parsing
- Backend mutual exclusivity (git_repo vs gitlab_api)
- YAML configuration file loading
"""

import textwrap
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from pydantic import ValidationError

from middleware.api.config import Config


def _git_repo(tmp_path: Path, group: str = "g") -> dict[str, str]:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(exist_ok=True)
    return {"url": repo_dir.as_uri(), "group": group, "path": str(repo_dir)}


def test_config_validate_known_rdis_valid(tmp_path: Path) -> None:
    """Test valid known RDIs."""
    # We need a minimal valid config
    config_data = {
        "known_rdis": ["valid-rdi", "rdi.123", "under_score"],
        "git_repo": _git_repo(tmp_path),
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    config = Config.model_validate(config_data)
    assert len(config.known_rdis) == 3  # noqa: PLR2004


def test_config_validate_known_rdis_invalid(tmp_path: Path) -> None:
    """Test invalid known RDIs."""
    config_data = {
        "known_rdis": ["invalid rdi"],  # space not allowed
        "git_repo": _git_repo(tmp_path),
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(ValidationError) as exc:
        Config.model_validate(config_data)
    assert "Invalid RDI identifier" in str(exc.value)


def test_config_parse_client_auth_oid_str(tmp_path: Path) -> None:
    """Test parsing OID from string."""
    oid_str = "1.2.3.4"
    config_data = {
        "client_auth_oid": oid_str,
        "git_repo": _git_repo(tmp_path),
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    config = Config.model_validate(config_data)
    assert isinstance(config.client_auth_oid, x509.ObjectIdentifier)
    assert config.client_auth_oid.dotted_string == oid_str


def test_config_parse_client_auth_oid_obj(tmp_path: Path) -> None:
    """Test parsing OID from ObjectIdentifier."""
    oid = x509.ObjectIdentifier("1.2.3.4")
    config_data = {
        "client_auth_oid": oid,
        "git_repo": _git_repo(tmp_path),
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    config = Config.model_validate(config_data)
    assert config.client_auth_oid == oid


def test_config_parse_client_auth_oid_invalid_type(tmp_path: Path) -> None:
    """Test invalid OID type."""
    config_data = {
        "client_auth_oid": 1234,
        "git_repo": _git_repo(tmp_path),
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(TypeError) as exc:
        Config.model_validate(config_data)
    assert "client_auth_oid must be a string or x509.ObjectIdentifier" in str(exc.value)


def test_config_mutual_exclusivity_none() -> None:
    """Test failure when neither backend is configured."""
    config_data: dict[str, Any] = {
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(ValidationError) as exc:
        Config.model_validate(config_data)
    assert "Either git_repo or gitlab_api must be configured" in str(exc.value)


def test_config_mutual_exclusivity_both(tmp_path: Path) -> None:
    """Test failure when both backends are configured."""
    config_data = {
        "git_repo": _git_repo(tmp_path),
        "gitlab_api": {"url": "https://gitlab.com", "token": "t", "group": "g", "branch": "b"},
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(ValidationError) as exc:
        Config.model_validate(config_data)
    assert "Only one of git_repo or gitlab_api can be configured" in str(exc.value)


def test_config_from_yaml_file_not_found() -> None:
    """Test loading config from non-existent file."""
    with pytest.raises(RuntimeError, match="Config file .* not found"):
        Config.from_yaml_file(Path("/non/existent/path.yaml"))


def test_config_from_yaml_file_success(tmp_path: Path) -> None:
    """Test loading config from a valid file."""
    config_file = tmp_path / "config.yaml"
    config_yaml = textwrap.dedent(
        f"""
        log_level: DEBUG
        git_repo:
          url: {tmp_path.as_uri()}
          group: my-group
          path: {tmp_path}
        couchdb:
          url: http://localhost:5984
        celery:
          broker_url: memory://
          result_backend: cache+memory://
        """
    )
    config_file.write_text(config_yaml)

    config = Config.from_yaml_file(config_file)
    assert config.log_level == "DEBUG"
    assert config.git_repo is not None
    assert config.git_repo.url == tmp_path.as_uri()
