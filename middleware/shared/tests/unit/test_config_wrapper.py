"""Unit tests for the ConfigWrapper utility."""

from pathlib import Path
from typing import Any

import pytest

from middleware.shared.config.config_wrapper import ConfigWrapper, ConfigWrapperDict, ConfigWrapperList, ListType


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
    assert len(cfg) == 2  # nosec  # noqa: PLR2004
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
    assert item_2["value"] == 42  # nosec  # noqa: PLR2004
    keys = list(cfg)
    assert keys == [0, 1, 2]  # nosec
    items = dict(cfg.items())
    assert items[0] == "a"  # nosec
    item_2 = cfg[2]
    assert isinstance(item_2, ConfigWrapper)  # nosec, narrowing for typchecker
    assert item_2["value"] == 42  # nosec  # noqa: PLR2004
    assert len(cfg) == 3  # nosec  # noqa: PLR2004


# New tests for primitive type support


def test_parse_primitive_value_bool_true() -> None:
    """Test parsing boolean true value."""
    assert ConfigWrapper._parse_primitive_value("true") is True  # pylint: disable=protected-access  # nosec
    assert ConfigWrapper._parse_primitive_value("True") is True  # pylint: disable=protected-access  # nosec
    assert ConfigWrapper._parse_primitive_value("TRUE") is True  # pylint: disable=protected-access  # nosec


def test_parse_primitive_value_bool_false() -> None:
    """Test parsing boolean false value."""
    assert ConfigWrapper._parse_primitive_value("false") is False  # pylint: disable=protected-access  # nosec
    assert ConfigWrapper._parse_primitive_value("False") is False  # pylint: disable=protected-access  # nosec
    assert ConfigWrapper._parse_primitive_value("FALSE") is False  # pylint: disable=protected-access  # nosec


def test_parse_primitive_value_int() -> None:
    """Test parsing integer values."""
    assert ConfigWrapper._parse_primitive_value("42") == 42  # pylint: disable=protected-access  # nosec  # noqa: PLR2004
    assert ConfigWrapper._parse_primitive_value("-42") == -42  # pylint: disable=protected-access  # nosec  # noqa: PLR2004
    assert ConfigWrapper._parse_primitive_value("0") == 0  # pylint: disable=protected-access  # nosec


def test_parse_primitive_value_float() -> None:
    """Test parsing float values."""
    assert ConfigWrapper._parse_primitive_value("3.14") == 3.14  # pylint: disable=protected-access  # nosec  # noqa: PLR2004
    assert ConfigWrapper._parse_primitive_value("-3.14") == -3.14  # pylint: disable=protected-access  # nosec  # noqa: PLR2004
    assert ConfigWrapper._parse_primitive_value("0.5") == 0.5  # pylint: disable=protected-access  # nosec  # noqa: PLR2004


def test_parse_primitive_value_string() -> None:
    """Test parsing string values that are not primitives."""
    assert ConfigWrapper._parse_primitive_value("hello") == "hello"  # pylint: disable=protected-access  # nosec
    assert ConfigWrapper._parse_primitive_value("3.14.15") == "3.14.15"  # pylint: disable=protected-access  # nosec
    assert ConfigWrapper._parse_primitive_value("notabool") == "notabool"  # pylint: disable=protected-access  # nosec


def test_parse_primitive_value_empty_string() -> None:
    """Test parsing empty string returns None."""
    assert ConfigWrapper._parse_primitive_value("") is None  # pylint: disable=protected-access  # nosec


def test_override_key_access_int_env(monkeypatch: Any) -> None:
    """Test environment variable override with integer value."""
    monkeypatch.setenv("FOO_PORT", "8080")
    cfg = ConfigWrapperDict({"port": 3000}, path="foo")
    result = cfg["port"]
    assert result == 8080  # nosec  # noqa: PLR2004
    assert isinstance(result, int)  # nosec


def test_override_key_access_float_env(monkeypatch: Any) -> None:
    """Test environment variable override with float value."""
    monkeypatch.setenv("FOO_TIMEOUT", "3.5")
    cfg = ConfigWrapperDict({"timeout": 1.0}, path="foo")
    result = cfg["timeout"]
    assert result == 3.5  # nosec  # noqa: PLR2004
    assert isinstance(result, float)  # nosec


def test_override_key_access_bool_env(monkeypatch: Any) -> None:
    """Test environment variable override with boolean value."""
    monkeypatch.setenv("FOO_DEBUG", "true")
    cfg = ConfigWrapperDict({"debug": False}, path="foo")
    result = cfg["debug"]
    assert result is True  # nosec
    assert isinstance(result, bool)  # nosec


def test_override_key_access_bool_false_env(monkeypatch: Any) -> None:
    """Test environment variable override with boolean false value."""
    monkeypatch.setenv("FOO_ENABLED", "false")
    cfg = ConfigWrapperDict({"enabled": True}, path="foo")
    result = cfg["enabled"]
    assert result is False  # nosec
    assert isinstance(result, bool)  # nosec


def test_override_key_access_none_env(monkeypatch: Any) -> None:
    """Test environment variable override with empty string returns default value."""
    monkeypatch.setenv("FOO_EMPTY", "")
    cfg = ConfigWrapperDict({"empty": "default"}, path="foo")
    result = cfg["empty"]
    # Empty string from env variable is parsed to None, so the default value is used
    assert result == "default"  # nosec


def test_parse_primitive_value_for_none_case() -> None:
    """Test that explicitly None values are preserved in YAML config."""
    cfg = ConfigWrapperDict({"nullable": None}, path="foo")
    result = cfg["nullable"]
    assert result is None  # nosec


def test_override_key_access_string_env(monkeypatch: Any) -> None:
    """Test environment variable override with string value."""
    monkeypatch.setenv("FOO_NAME", "John")
    cfg = ConfigWrapperDict({"name": "default"}, path="foo")
    result = cfg["name"]
    assert result == "John"  # nosec
    assert isinstance(result, str)  # nosec


def test_dict_with_primitive_types() -> None:
    """Test ConfigWrapperDict with various primitive types."""
    data: dict[str, Any] = {
        "string": "hello",
        "integer": 42,
        "float": 3.14,
        "bool": True,
    }
    cfg = ConfigWrapperDict(data)
    assert cfg["string"] == "hello"  # nosec
    assert cfg["integer"] == 42  # nosec  # noqa: PLR2004
    assert cfg["float"] == 3.14  # nosec  # noqa: PLR2004
    assert cfg["bool"] is True  # nosec


def test_unwrap_with_primitive_types() -> None:
    """Test unwrapping ConfigWrapper with primitive types."""
    data: dict[str, Any] = {
        "string": "hello",
        "integer": 42,
        "float": 3.14,
        "bool": True,
        "null": None,
    }
    cfg = ConfigWrapper.from_data(data)
    unwrapped = cfg.unwrap()
    assert isinstance(unwrapped, dict)  # nosec
    assert unwrapped["string"] == "hello"  # nosec
    assert unwrapped["integer"] == 42  # nosec  # noqa: PLR2004
    assert unwrapped["float"] == 3.14  # nosec  # noqa: PLR2004
    assert unwrapped["bool"] is True  # nosec
    assert unwrapped["null"] is None  # nosec


def test_nested_dict_with_primitives() -> None:
    """Test nested dictionaries with primitive types."""
    data: dict[str, Any] = {
        "nested": {
            "port": 8080,
            "timeout": 5.5,
            "debug": False,
            "name": "app",
        }
    }
    cfg = ConfigWrapper.from_data(data)  # type: ignore[arg-type]
    nested = cfg["nested"]
    assert isinstance(nested, ConfigWrapper)  # nosec
    assert nested["port"] == 8080  # nosec  # noqa: PLR2004
    assert nested["timeout"] == 5.5  # nosec  # noqa: PLR2004
    assert nested["debug"] is False  # nosec
    assert nested["name"] == "app"  # nosec


def test_list_with_primitive_types() -> None:
    """Test ConfigWrapperList with primitive types."""
    data: ListType = ["string", 42, 3.14, True, None]
    cfg = ConfigWrapperList(data)
    assert cfg[0] == "string"  # nosec
    assert cfg[1] == 42  # nosec  # noqa: PLR2004
    assert cfg[2] == 3.14  # nosec  # noqa: PLR2004
    assert cfg[3] is True  # nosec
    assert cfg[4] is None  # nosec
