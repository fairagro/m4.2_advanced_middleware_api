import pytest
from cryptography import x509
from pydantic import ValidationError
from typing import Any
from pathlib import Path

from middleware.api.config import Config
from middleware.api.arc_store.git_repo import GitRepoConfig
from middleware.api.arc_store.gitlab_api import GitlabApiConfig

def test_config_validate_known_rdis_valid() -> None:
    """Test valid known RDIs."""
    # We need a minimal valid config
    config_data = {
        "known_rdis": ["valid-rdi", "rdi.123", "under_score"],
        "git_repo": {"url": "file:///tmp", "group": "g", "path": "/tmp"},
    }
    config = Config.model_validate(config_data)
    assert len(config.known_rdis) == 3

def test_config_validate_known_rdis_invalid() -> None:
    """Test invalid known RDIs."""
    config_data = {
        "known_rdis": ["invalid rdi"], # space not allowed
        "git_repo": {"url": "file:///tmp", "group": "g", "path": "/tmp"},
    }
    with pytest.raises(ValidationError) as exc:
        Config.model_validate(config_data)
    assert "Invalid RDI identifier" in str(exc.value)



def test_config_parse_client_auth_oid_str() -> None:
    """Test parsing OID from string."""
    oid_str = "1.2.3.4"
    config_data = {
        "client_auth_oid": oid_str,
        "git_repo": {"url": "file:///tmp", "group": "g", "path": "/tmp"},
    }
    config = Config.model_validate(config_data)
    assert isinstance(config.client_auth_oid, x509.ObjectIdentifier)
    assert config.client_auth_oid.dotted_string == oid_str

def test_config_parse_client_auth_oid_obj() -> None:
    """Test parsing OID from ObjectIdentifier."""
    oid = x509.ObjectIdentifier("1.2.3.4")
    config_data = {
        "client_auth_oid": oid,
        "git_repo": {"url": "file:///tmp", "group": "g", "path": "/tmp"},
    }
    config = Config.model_validate(config_data)
    assert config.client_auth_oid == oid

def test_config_parse_client_auth_oid_invalid_type() -> None:
    """Test invalid OID type."""
    config_data = {
        "client_auth_oid": 1234,
        "git_repo": {"url": "file:///tmp", "group": "g", "path": "/tmp"},
    }
    with pytest.raises(TypeError) as exc:
        Config.model_validate(config_data)
    assert "client_auth_oid must be a string or x509.ObjectIdentifier" in str(exc.value)

def test_config_mutual_exclusivity_none() -> None:
    """Test failure when neither backend is configured."""
    config_data: dict[str, Any] = {}
    with pytest.raises(ValidationError) as exc:
        Config.model_validate(config_data)
    assert "Either git_repo or gitlab_api must be configured" in str(exc.value)

def test_config_mutual_exclusivity_both() -> None:
    """Test failure when both backends are configured."""
    config_data = {
        "git_repo": {"url": "file:///tmp", "group": "g", "path": "/tmp"},
        "gitlab_api": {"url": "https://gitlab.com", "token": "t", "group": "g", "branch": "b"},
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
    config_file.write_text("""
log_level: DEBUG
git_repo:
  url: file:///tmp
  group: my-group
    """)
    
    config = Config.from_yaml_file(config_file)
    assert config.log_level == "DEBUG"
    assert config.git_repo is not None
    assert config.git_repo.url == "file:///tmp"
