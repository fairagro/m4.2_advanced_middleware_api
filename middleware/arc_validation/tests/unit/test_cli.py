"""CLI unit tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from middleware.arc_validation.cli import main
from middleware.arc_validation.pipeline import ArcExportResult


def test_cli_success_exit_zero(tmp_path: Path) -> None:
    crate = tmp_path / "crate.json"
    crate.write_text("{}", encoding="utf-8")
    ok = ArcExportResult(ok=True, exit_code=0, stdout="", stderr="", cause_excerpt="")
    with patch("middleware.arc_validation.cli.validate_rocrate", return_value=ok):
        assert main([str(crate)]) == 0


def test_cli_failure_prints_cause(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    crate = tmp_path / "crate.json"
    crate.write_text("{}", encoding="utf-8")
    failed = ArcExportResult(
        ok=False,
        exit_code=7,
        stdout="",
        stderr="boom",
        cause_excerpt="Value cannot be null",
    )
    with patch("middleware.arc_validation.cli.validate_rocrate", return_value=failed):
        code = main([str(crate)])
    assert code == 7
    assert "Value cannot be null" in capsys.readouterr().err


def test_cli_missing_file() -> None:
    assert main(["/no/such/rocrate.json"]) == 2
