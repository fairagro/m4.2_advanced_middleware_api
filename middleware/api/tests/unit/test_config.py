"""Unit tests for the API configuration module.

Tests cover:
- RDI identifier validation
- Client authentication OID parsing
- Dual-slot ArcStore validation
- YAML configuration file loading
"""

import textwrap
from pathlib import Path
from typing import Any

import pytest
from cryptography import x509
from pydantic import ValidationError

from middleware.api.config import Config


def _git_repo(tmp_path: Path, group: str = "g") -> dict[str, str | dict[str, str]]:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir(exist_ok=True)
    return {
        "url": repo_dir.as_uri(),
        "group": group,
        "path": str(repo_dir),
        "rdi_gitlab_topics": {
            "valid-rdi": "valid-rdi",
            "rdi.123": "rdi.123",
            "under_score": "under_score",
        },
    }


def _arc_store(tmp_path: Path, **git_repo_overrides: object) -> dict[str, object]:
    git_repo = _git_repo(tmp_path)
    git_repo.update(git_repo_overrides)  # type: ignore[arg-type]
    return {"git_repo": git_repo}


def test_config_validate_rdi_gitlab_topics_requires_full_mapping(tmp_path: Path) -> None:
    """Every known RDI must have a GitLab topic mapping when git_repo is configured."""
    config_data = {
        "known_rdis": ["bonares", "edal"],
        "arc_store": {
            "git_repo": {
                **_git_repo(tmp_path),
                "rdi_gitlab_topics": {"edal": "e!DAL"},
            },
        },
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(ValidationError, match="missing from rdi_gitlab_topics"):
        Config.model_validate(config_data)


def test_config_validate_rdi_gitlab_topics_rejects_unknown_keys(tmp_path: Path) -> None:
    """GitLab topic mapping keys must be a subset of known_rdis."""
    config_data = {
        "known_rdis": ["edal"],
        "arc_store": {
            "git_repo": {
                **_git_repo(tmp_path),
                "rdi_gitlab_topics": {"edal": "e!DAL", "bonares": "bonares"},
            },
        },
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(ValidationError, match="not in known_rdis"):
        Config.model_validate(config_data)


def test_config_validate_known_rdis_valid(tmp_path: Path) -> None:
    """Test valid known RDIs."""
    config_data = {
        "known_rdis": ["valid-rdi", "rdi.123", "under_score"],
        "arc_store": _arc_store(tmp_path),
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    config = Config.model_validate(config_data)
    assert len(config.known_rdis) == 3  # noqa: PLR2004


def test_config_validate_known_rdis_invalid(tmp_path: Path) -> None:
    """Test invalid known RDIs."""
    config_data = {
        "known_rdis": ["invalid rdi"],  # space not allowed
        "arc_store": _arc_store(tmp_path),
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
        "arc_store": _arc_store(tmp_path),
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
        "arc_store": _arc_store(tmp_path),
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    config = Config.model_validate(config_data)
    assert config.client_auth_oid == oid


def test_config_parse_client_auth_oid_invalid_type(tmp_path: Path) -> None:
    """Test invalid OID type."""
    config_data = {
        "client_auth_oid": 1234,
        "arc_store": _arc_store(tmp_path),
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(TypeError) as exc:
        Config.model_validate(config_data)
    assert "client_auth_oid must be a string or x509.ObjectIdentifier" in str(exc.value)


def test_config_requires_arc_store() -> None:
    """Test failure when arc_store is missing."""
    config_data: dict[str, Any] = {
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(ValidationError) as exc:
        Config.model_validate(config_data)
    assert "arc_store" in str(exc.value)


def test_config_rejects_legacy_only_top_level_backends(tmp_path: Path) -> None:
    """Top-level store keys alone are not enough; required arc_store is missing."""
    config_data = {
        "git_repo": _git_repo(tmp_path),
        "gitlab_api": {"url": "https://gitlab.com", "token": "t", "group": "g", "branch": "b"},
        "couchdb": {"url": "http://localhost:5984"},
        "celery": {"broker_url": "memory://", "result_backend": "cache+memory://"},
    }
    with pytest.raises(ValidationError, match="arc_store"):
        Config.model_validate(config_data)


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
        arc_store:
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
    assert config.arc_store.git_repo is not None
