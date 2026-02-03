"""Test version CLI parameter."""

from unittest.mock import patch

import pytest

from middleware.api.main import main


def test_version_flag_exits_successfully() -> None:
    """Test that --version flag exits with code 0."""
    with patch("sys.argv", ["middleware-api", "--version"]), patch("builtins.print"):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_version_flag_prints_version() -> None:
    """Test that --version flag prints version information."""
    with patch("sys.argv", ["middleware-api", "--version"]), patch("builtins.print") as mock_print:
        with pytest.raises(SystemExit):
            main()
        # Check that print was called with version info
        assert mock_print.called
        call_args = str(mock_print.call_args)
        assert "middleware-api version" in call_args


def test_short_version_flag() -> None:
    """Test that -v flag works as alias for --version."""
    with patch("sys.argv", ["middleware-api", "-v"]), patch("builtins.print"):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


def test_version_flag_handles_missing_metadata() -> None:
    """Test that --version handles missing metadata gracefully."""
    with (
        patch("sys.argv", ["middleware-api", "--version"]),
        patch("builtins.print") as mock_print,
        patch("importlib.metadata.version", side_effect=Exception("Not found")),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
        # Should print "unknown" when metadata is not available
        call_args = str(mock_print.call_args)
        assert "unknown" in call_args
