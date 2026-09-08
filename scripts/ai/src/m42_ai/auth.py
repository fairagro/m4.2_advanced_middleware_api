"""Auth probe via PATH `gh` (no second credential model)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from m42_ai.gh import GhError, run_gh


def auth_status(*, cwd: Path | None = None, hostname: str = "github.com") -> dict[str, Any]:
    """Return shaped auth status. `ok` is True when an active host entry reports success."""
    try:
        proc = run_gh(["auth", "status", "--json", "hosts"], cwd=cwd, check=False)
    except GhError as exc:
        return {
            "ok": False,
            "hostname": hostname,
            "logged_in": False,
            "login": None,
            "token_source": None,
            "error": str(exc),
        }

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        return {
            "ok": False,
            "hostname": hostname,
            "logged_in": False,
            "login": None,
            "token_source": None,
            "error": detail,
        }

    try:
        raw = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "hostname": hostname,
            "logged_in": False,
            "login": None,
            "token_source": None,
            "error": f"invalid auth JSON: {exc}",
        }

    hosts = raw.get("hosts") or {}
    entries = hosts.get(hostname) or []
    active = next((e for e in entries if e.get("active")), entries[0] if entries else None)
    if not active:
        return {
            "ok": False,
            "hostname": hostname,
            "logged_in": False,
            "login": None,
            "token_source": None,
            "error": f"no auth entry for {hostname}",
        }

    state = str(active.get("state") or "")
    ok = state == "success"
    return {
        "ok": ok,
        "hostname": hostname,
        "logged_in": ok,
        "login": active.get("login"),
        "token_source": active.get("tokenSource"),
        "git_protocol": active.get("gitProtocol"),
        "state": state,
        "error": None if ok else f"auth state={state!r}",
    }
