"""Fail-closed wrapper around ``openspec instructions … --json``."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from m42_ai.gh import run_cmd

OpenspecRunner = Callable[[list[str], Path | None], Any]


class OpenspecInstructionsError(RuntimeError):
    """Structured failure for agents — do not invent templates."""

    def __init__(self, message: str, *, error_code: str = "openspec_instructions_failed") -> None:
        super().__init__(message)
        self.error_code = error_code

    def as_json(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error_code": self.error_code,
            "error": str(self),
            "agent_action": "stop",
        }


def _status_blocking_error(payload: dict[str, Any]) -> tuple[str, str] | None:
    """Return ``(message, error_code)`` if OpenSpec JSON reports a blocking status error."""
    status = payload.get("status")
    if not isinstance(status, list):
        return None
    messages: list[str] = []
    codes: list[str] = []
    for item in status:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "").lower()
        code = str(item.get("code") or "").strip()
        if severity == "error" or code.endswith("_error") or code == "change_error":
            msg = str(item.get("message") or code or "openspec status error").strip()
            messages.append(msg)
            if code:
                codes.append(code)
    if not messages:
        return None
    # Prefer the first concrete status code; fall back to a generic label when absent.
    error_code = codes[0] if codes else "openspec_status_error"
    return "; ".join(messages), error_code


def fetch_openspec_instructions(
    artifact: str,
    change: str,
    *,
    cwd: Path | None = None,
    runner: OpenspecRunner | None = None,
) -> dict[str, Any]:
    """Run ``openspec instructions <artifact> --change <change> --json``.

    Returns the OpenSpec JSON object (with ``ok: true``) on success.
    Raises :class:`OpenspecInstructionsError` on missing binary, empty/non-JSON
    output, or blocking ``status`` errors — never invents ``template`` /
    ``resolvedOutputPath``.
    """
    art = (artifact or "").strip()
    ch = (change or "").strip()
    if not art:
        raise OpenspecInstructionsError("artifact is required", error_code="invalid_args")
    if not ch:
        raise OpenspecInstructionsError("change is required", error_code="invalid_args")

    root = cwd or Path.cwd()
    openspec_bin = shutil.which("openspec")
    if not openspec_bin:
        raise OpenspecInstructionsError(
            "openspec not found on PATH",
            error_code="openspec_not_found",
        )

    argv = [openspec_bin, "instructions", art, "--change", ch, "--json"]
    proc = runner(argv, root) if runner is not None else run_cmd(argv, cwd=root, check=False)

    stdout = (getattr(proc, "stdout", None) or "") if proc is not None else ""
    stderr = (getattr(proc, "stderr", None) or "") if proc is not None else ""
    returncode = int(getattr(proc, "returncode", 1) if proc is not None else 1)

    text = stdout.strip()
    if not text:
        detail = stderr.strip() or f"openspec exited {returncode} with empty stdout"
        raise OpenspecInstructionsError(detail, error_code="empty_output")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OpenspecInstructionsError(
            f"openspec stdout is not JSON: {exc}",
            error_code="invalid_json",
        ) from exc

    if not isinstance(payload, dict):
        raise OpenspecInstructionsError(
            "openspec JSON root must be an object",
            error_code="invalid_json",
        )

    blocking = _status_blocking_error(payload)
    if blocking:
        message, error_code = blocking
        raise OpenspecInstructionsError(message, error_code=error_code)

    # Non-zero exit without a status error still fail-closed.
    if returncode != 0:
        detail = stderr.strip() or f"openspec exited {returncode}"
        raise OpenspecInstructionsError(detail, error_code="openspec_exit_nonzero")

    out = dict(payload)
    out["ok"] = True
    return out
