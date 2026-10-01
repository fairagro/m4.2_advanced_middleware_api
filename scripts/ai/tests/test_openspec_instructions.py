"""Tests for openspec-instructions (mocked openspec — no live schema network)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from m42_ai.cli import main
from m42_ai.openspec_instructions import (
    OpenspecInstructionsError,
    fetch_openspec_instructions,
)


def _proc(*, stdout: str = "", stderr: str = "", returncode: int = 0) -> SimpleNamespace:
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def test_fetch_success_passes_through_fields() -> None:
    payload = {
        "resolvedOutputPath": "/tmp/proposal.md",
        "instruction": "write proposal",
        "template": "## Why\n",
    }

    def runner(argv: list[str], cwd: object) -> SimpleNamespace:
        assert argv[1:4] == ["instructions", "proposal", "--change"]
        assert argv[4] == "demo-change"
        assert "--json" in argv
        return _proc(stdout=json.dumps(payload))

    with patch("m42_ai.openspec_instructions.shutil.which", return_value="/usr/bin/openspec"):
        out = fetch_openspec_instructions("proposal", "demo-change", runner=runner)
    assert out["ok"] is True
    assert out["resolvedOutputPath"] == "/tmp/proposal.md"
    assert out["instruction"] == "write proposal"
    assert out["template"] == "## Why\n"


def test_fetch_change_error_status_fails_closed() -> None:
    payload = {
        "status": [
            {
                "severity": "error",
                "code": "change_error",
                "message": "Change 'missing' not found.",
            }
        ]
    }

    def runner(argv: list[str], cwd: object) -> SimpleNamespace:
        return _proc(stdout=json.dumps(payload), returncode=1)

    with (
        patch("m42_ai.openspec_instructions.shutil.which", return_value="/usr/bin/openspec"),
        pytest.raises(OpenspecInstructionsError) as ei,
    ):
        fetch_openspec_instructions("proposal", "missing", runner=runner)
    err = ei.value
    assert err.error_code == "change_error"
    data = err.as_json()
    assert data["ok"] is False
    assert data["agent_action"] == "stop"
    assert "template" not in data
    assert "resolvedOutputPath" not in data


def test_fetch_artifact_error_status_preserves_code() -> None:
    payload = {
        "status": [
            {
                "severity": "error",
                "code": "artifact_error",
                "message": "Artifact blocked.",
            }
        ]
    }

    def runner(argv: list[str], cwd: object) -> SimpleNamespace:
        return _proc(stdout=json.dumps(payload), returncode=1)

    with (
        patch("m42_ai.openspec_instructions.shutil.which", return_value="/usr/bin/openspec"),
        pytest.raises(OpenspecInstructionsError) as ei,
    ):
        fetch_openspec_instructions("proposal", "demo", runner=runner)
    assert ei.value.error_code == "artifact_error"
    assert "Artifact blocked" in str(ei.value)


def test_fetch_nonzero_exit_with_valid_json_fails_closed() -> None:
    """Non-zero openspec exit + valid JSON object + no status error → openspec_exit_nonzero."""
    payload = {
        "resolvedOutputPath": "/tmp/proposal.md",
        "instruction": "write proposal",
        "template": "## Why\n",
    }

    def runner(argv: list[str], cwd: object) -> SimpleNamespace:
        return _proc(stdout=json.dumps(payload), stderr="openspec warn", returncode=1)

    with (
        patch("m42_ai.openspec_instructions.shutil.which", return_value="/usr/bin/openspec"),
        pytest.raises(OpenspecInstructionsError) as ei,
    ):
        fetch_openspec_instructions("proposal", "demo-change", runner=runner)
    assert ei.value.error_code == "openspec_exit_nonzero"
    data = ei.value.as_json()
    assert data["ok"] is False
    assert data["agent_action"] == "stop"
    assert "template" not in data


def test_fetch_empty_stdout_fails_closed() -> None:
    def runner(argv: list[str], cwd: object) -> SimpleNamespace:
        return _proc(stdout="", stderr="boom", returncode=1)

    with (
        patch("m42_ai.openspec_instructions.shutil.which", return_value="/usr/bin/openspec"),
        pytest.raises(OpenspecInstructionsError) as ei,
    ):
        fetch_openspec_instructions("proposal", "x", runner=runner)
    assert ei.value.error_code == "empty_output"
    assert ei.value.as_json()["agent_action"] == "stop"


def test_fetch_non_json_fails_closed() -> None:
    def runner(argv: list[str], cwd: object) -> SimpleNamespace:
        return _proc(stdout="not-json <<<", returncode=0)

    with (
        patch("m42_ai.openspec_instructions.shutil.which", return_value="/usr/bin/openspec"),
        pytest.raises(OpenspecInstructionsError) as ei,
    ):
        fetch_openspec_instructions("proposal", "x", runner=runner)
    assert ei.value.error_code == "invalid_json"


def test_fetch_openspec_missing_on_path() -> None:
    with (
        patch("m42_ai.openspec_instructions.shutil.which", return_value=None),
        pytest.raises(OpenspecInstructionsError) as ei,
    ):
        fetch_openspec_instructions("proposal", "x")
    assert ei.value.error_code == "openspec_not_found"


def test_cli_openspec_instructions_success(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "ok": True,
        "resolvedOutputPath": "/workspace/openspec/changes/demo/proposal.md",
        "instruction": "go",
        "template": "## Why",
    }
    with patch("m42_ai.cli.fetch_openspec_instructions", return_value=payload):
        code = main(["openspec-instructions", "--artifact", "proposal", "--change", "demo"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["resolvedOutputPath"].endswith("proposal.md")
    assert out["ok"] is True


def test_cli_openspec_instructions_error_json(capsys: pytest.CaptureFixture[str]) -> None:
    err = OpenspecInstructionsError("Change missing", error_code="change_error")
    with patch("m42_ai.cli.fetch_openspec_instructions", side_effect=err):
        code = main(["openspec-instructions", "--artifact", "proposal", "--change", "nope"])
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out == {
        "ok": False,
        "error_code": "change_error",
        "error": "Change missing",
        "agent_action": "stop",
    }


def test_cli_openspec_instructions_unexpected_error_still_json(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("m42_ai.cli.fetch_openspec_instructions", side_effect=OSError("boom")):
        code = main(["openspec-instructions", "--artifact", "proposal", "--change", "demo"])
    assert code == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["agent_action"] == "stop"
    assert out["error_code"] == "unexpected_error"
    assert "boom" in out["error"]


def test_cli_missing_required_arg_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as ei:
        main(["openspec-instructions", "--change", "demo"])
    assert ei.value.code == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["agent_action"] == "stop"
    assert out["error_code"] == "invalid_args"
    assert "artifact" in out["error"].lower()


def test_cli_help_lists_openspec_instructions() -> None:
    with pytest.raises(SystemExit) as ei:
        main(["openspec-instructions", "--help"])
    assert ei.value.code == 0
