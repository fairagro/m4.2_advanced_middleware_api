"""Unit tests for scaffold write, Docker export, and validate_rocrate."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from middleware.arc_validation.pipeline import (
    DEFAULT_ARC_EXPORT_FORMATS,
    DEFAULT_ARC_EXPORT_IMAGE,
    IMAGE_ENV_VAR,
    ArcExportResult,
    resolve_arc_export_image,
    run_arc_export,
    validate_rocrate,
    write_arc_scaffold,
)


def test_resolve_image_explicit_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(IMAGE_ENV_VAR, "env-image:tag")
    assert resolve_arc_export_image("explicit@sha256:abc") == "explicit@sha256:abc"


def test_resolve_image_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(IMAGE_ENV_VAR, "ghcr.io/example/arc-export@sha256:deadbeef")
    assert resolve_arc_export_image() == "ghcr.io/example/arc-export@sha256:deadbeef"


def test_resolve_image_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(IMAGE_ENV_VAR, raising=False)
    assert resolve_arc_export_image() == DEFAULT_ARC_EXPORT_IMAGE


def test_write_arc_scaffold_success(tmp_path: Path) -> None:
    mock_arc = MagicMock()
    with patch("middleware.arc_validation.pipeline.ARC") as mock_arc_cls:
        mock_arc_cls.from_rocrate_json_string.return_value = mock_arc
        out = write_arc_scaffold('{"@graph":[]}', tmp_path / "arc")
    assert out == tmp_path / "arc"
    mock_arc_cls.from_rocrate_json_string.assert_called_once()
    mock_arc.Write.assert_called_once_with(str(tmp_path / "arc"))


def test_run_arc_export_success_builds_argv(tmp_path: Path) -> None:
    arc_dir = tmp_path / "arc"
    arc_dir.mkdir()
    completed = MagicMock(returncode=0, stdout="ok", stderr="")
    with patch("middleware.arc_validation.pipeline.subprocess.run", return_value=completed) as run:
        result = run_arc_export(arc_dir)
    assert result.ok is True
    assert result.exit_code == 0
    argv = run.call_args.args[0]
    assert argv[0:3] == ["docker", "run", "--rm"]
    assert f"{arc_dir.resolve()}:/arc" in argv
    assert DEFAULT_ARC_EXPORT_IMAGE in argv
    assert argv[argv.index(DEFAULT_ARC_EXPORT_IMAGE) + 1] == "arc-export"
    for fmt in DEFAULT_ARC_EXPORT_FORMATS:
        assert fmt in argv
    assert argv[-2:] == ["-p", "."]


def test_run_arc_export_failure_keeps_logs_and_excerpt(tmp_path: Path) -> None:
    arc_dir = tmp_path / "arc"
    arc_dir.mkdir()
    completed = MagicMock(
        returncode=7,
        stdout="",
        stderr="Internal Error:\nValue cannot be null. (Parameter 'array')\n",
    )
    with patch("middleware.arc_validation.pipeline.subprocess.run", return_value=completed):
        result = run_arc_export(arc_dir)
    assert result.ok is False
    assert result.exit_code == 7
    assert "Value cannot be null" in result.cause_excerpt
    assert "Internal Error" in result.stderr


def test_validate_rocrate_pass() -> None:
    export_result = ArcExportResult(ok=True, exit_code=0, stdout="ok", stderr="", cause_excerpt="")
    with (
        patch("middleware.arc_validation.pipeline.write_arc_scaffold") as write,
        patch(
            "middleware.arc_validation.pipeline.run_arc_export",
            return_value=export_result,
        ) as export,
    ):
        result = validate_rocrate('{"@graph":[]}')
    assert result.ok is True
    write.assert_called_once()
    export.assert_called_once()


def test_validate_rocrate_write_failure_maps_to_result() -> None:
    with patch(
        "middleware.arc_validation.pipeline.write_arc_scaffold",
        side_effect=RuntimeError("bad crate"),
    ):
        result = validate_rocrate("{not-json")
    assert result.ok is False
    assert result.exit_code == 1
    assert "bad crate" in result.cause_excerpt
