"""Unit tests for the ConfigWrapper utility."""

from pathlib import Path
from typing import Any

import pytest

from middleware.shared.config_wrapper import ConfigWrapper, ConfigWrapperDict, ConfigWrapperList, ListType


@pytest.fixture
def sample_dict() -> dict[str, Any]:
    """Sample dictionary for testing."""
    return {
        "foo": "bar",
        "nested": {"key": "value"},
        "list": [{"id": "foo", "key": "value"}],
    }


@pytest.fixture
def sample_list() -> list[Any]:
    """Sample list for testing."""
    return ["a", "b", {"id": "c", "value": 42}]


def test_dict_basic_access(
    sample_dict: dict[str, Any],
) -> None:  # pylint: disable=redefined-outer-name
    """Test basic access in ConfigWrapperDict."""
    cfg = ConfigWrapperDict(sample_dict)
    assert cfg["foo"] == "bar"  # nosec
    nested = cfg["nested"]
    assert isinstance(nested, ConfigWrapper)  # nosec, narrowing for typchecker
    assert nested["key"] == "value"  # nosec


def test_dict_get_method(
    sample_dict: dict[str, Any],
) -> None:  # pylint: disable=redefined-outer-name
    """Test the get method in ConfigWrapperDict."""
    cfg = ConfigWrapperDict(sample_dict)
    assert cfg.get("foo") == "bar"  # nosec
    assert cfg.get("nonexistent", "default") == "default"  # nosec


def test_dict_override_env(
    monkeypatch: Any,
) -> None:  # pylint: disable=redefined-outer-name
    """Test environment variable override in ConfigWrapperDict."""
    monkeypatch.setenv("FOO_BAR", "env_value")
    cfg = ConfigWrapperDict({"bar": "original"}, path="foo")
    assert cfg["bar"] == "env_value"  # nosec


def test_list_override_env(monkeypatch: Any, sample_dict: dict[str, Any]) -> None:  # pylint: disable=redefined-outer-name
    """Test environment variable override in ConfigWrapperList."""
    monkeypatch.setenv("LIST_FOO_BAR", "baz")
    cfg = ConfigWrapper.from_data(sample_dict)
    assert isinstance(cfg, ConfigWrapper)  # nosec
    cfg_list = cfg["list"]
    assert isinstance(cfg_list, ConfigWrapper)  # nosec
    cfg_list_foo = cfg_list[0]
    assert isinstance(cfg_list_foo, ConfigWrapper)  # nosec
    assert "bar" in cfg_list_foo  # nosec
    assert cfg_list_foo["bar"] == "baz"  # nosec


def test_dict_override_secret(
    tmp_path: Path,
) -> None:  # pylint: disable=redefined-outer-name
    """Test secret file override in ConfigWrapperDict."""
    secret_file = tmp_path / "foo_secret"
    secret_file.write_text("secret_value")
    # Patch /run/secrets to tmp_path
    monkeypatch = pytest.MonkeyPatch()
    original_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self: original_exists(tmp_path / self.name))
    original_read_text = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda self, encoding=None: original_read_text(tmp_path / self.name, encoding),
    )
    cfg = ConfigWrapperDict({}, path="foo")
    # pylint: disable=protected-access
    assert cfg._override_key_access("secret") == "secret_value"  # nosec
    monkeypatch.undo()


def test_dict_iteration_and_len(monkeypatch: Any) -> None:
    """Test iteration and length in ConfigWrapperDict."""
    monkeypatch.setenv("FOO_NEWKEY", "val")
    cfg = ConfigWrapperDict({"bar": "baz"}, path="foo")
    keys = set(cfg)
    assert "bar" in keys  # nosec
    assert "newkey" in keys  # nosec
    assert len(cfg) == 2  # nosec
    items = dict(cfg.items())
    assert items["bar"] == "baz"  # nosec
    assert items["newkey"] == "val"  # nosec


def test_list_access_and_items(
    sample_list: ListType,
) -> None:  # pylint: disable=redefined-outer-name
    """Test access and items in ConfigWrapperList."""
    cfg = ConfigWrapperList(sample_list)
    assert cfg[0] == "a"  # nosec
    item_2 = cfg[2]
    assert isinstance(item_2, ConfigWrapper)  # nosec, narrowing for typchecker
    assert item_2["value"] == 42  # nosec
    keys = list(cfg)
    assert keys == [0, 1, 2]  # nosec
    items = dict(cfg.items())
    assert items[0] == "a"  # nosec
    item_2 = cfg[2]
    assert isinstance(item_2, ConfigWrapper)  # nosec, narrowing for typchecker
    assert item_2["value"] == 42  # nosec
    assert len(cfg) == 3  # nosec
