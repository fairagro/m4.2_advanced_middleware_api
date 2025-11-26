"""Unit tests for the Config class."""

import tempfile
from pathlib import Path

import pytest
import yaml

from middleware.api_client.config import Config


def test_config_from_yaml_file(test_config_yaml: Path) -> None:
    """Test loading configuration from YAML file."""
    config = Config.from_yaml_file(test_config_yaml)
    
    assert config.log_level == "DEBUG"
    assert config.api_url == "https://test-api.example.com"
    assert config.timeout == 30.0
    assert config.verify_ssl is True


def test_config_from_data(test_config_dict: dict) -> None:
    """Test creating configuration from dictionary."""
    config = Config.from_data(test_config_dict)
    
    assert config.log_level == "DEBUG"
    assert config.api_url == "https://test-api.example.com"
    assert config.client_cert_path == test_config_dict["client_cert_path"]
    assert config.client_key_path == test_config_dict["client_key_path"]


def test_config_get_client_cert_path(test_config_dict: dict) -> None:
    """Test getting client certificate path as Path object."""
    config = Config.from_data(test_config_dict)
    cert_path = config.get_client_cert_path()
    
    assert isinstance(cert_path, Path)
    assert str(cert_path) == test_config_dict["client_cert_path"]


def test_config_get_client_key_path(test_config_dict: dict) -> None:
    """Test getting client key path as Path object."""
    config = Config.from_data(test_config_dict)
    key_path = config.get_client_key_path()
    
    assert isinstance(key_path, Path)
    assert str(key_path) == test_config_dict["client_key_path"]


def test_config_get_ca_cert_path_none(test_config_dict: dict) -> None:
    """Test getting CA cert path when not configured."""
    config = Config.from_data(test_config_dict)
    ca_path = config.get_ca_cert_path()
    
    assert ca_path is None


def test_config_get_ca_cert_path_set(test_config_dict: dict, temp_dir: Path) -> None:
    """Test getting CA cert path when configured."""
    ca_cert_path = temp_dir / "ca-cert.pem"
    ca_cert_path.write_text("fake ca cert")
    
    test_config_dict["ca_cert_path"] = str(ca_cert_path)
    config = Config.from_data(test_config_dict)
    ca_path = config.get_ca_cert_path()
    
    assert ca_path is not None
    assert isinstance(ca_path, Path)
    assert ca_path == ca_cert_path


def test_config_default_values() -> None:
    """Test configuration default values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        cert_path = temp_path / "cert.pem"
        key_path = temp_path / "key.pem"
        cert_path.write_text("fake cert")
        key_path.write_text("fake key")
        
        config = Config.from_data({
            "api_url": "https://api.example.com",
            "client_cert_path": str(cert_path),
            "client_key_path": str(key_path),
        })
        
        assert config.log_level == "INFO"  # Default from ConfigBase
        assert config.timeout == 30.0
        assert config.verify_ssl is True
        assert config.ca_cert_path is None


def test_config_invalid_timeout() -> None:
    """Test configuration with invalid timeout."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        cert_path = temp_path / "cert.pem"
        key_path = temp_path / "key.pem"
        cert_path.write_text("fake cert")
        key_path.write_text("fake key")
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            Config.from_data({
                "api_url": "https://api.example.com",
                "client_cert_path": str(cert_path),
                "client_key_path": str(key_path),
                "timeout": -1.0,  # Invalid: must be > 0
            })


def test_config_missing_required_fields() -> None:
    """Test configuration with missing required fields."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        Config.from_data({
            "api_url": "https://api.example.com",
            # Missing client_cert_path and client_key_path
        })
