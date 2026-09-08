"""Subprocess helpers for the PATH `gh` / `git` wrappers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


class GhError(RuntimeError):
    """`gh` or `git` exited non-zero."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str, stdout: str = "") -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout
        detail = stderr.strip() or stdout.strip() or "(no output)"
        super().__init__(f"{cmd[0]} failed ({returncode}): {detail}")


def _which(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise GhError([name], 127, f"{name} not found on PATH")
    return path


def run_cmd(
    argv: list[str],
    *,
    input_text: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(
        argv,
        input=input_text,
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise GhError(argv, proc.returncode, proc.stderr or "", proc.stdout or "")
    return proc


def run_gh(
    args: list[str],
    *,
    input_text: str | None = None,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run_cmd([_which("gh"), *args], input_text=input_text, cwd=cwd, check=check)


def run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return run_cmd([_which("git"), *args], cwd=cwd, check=check)


def repo_owner_name(*, cwd: Path | None = None) -> tuple[str, str]:
    proc = run_gh(["repo", "view", "--json", "owner,name", "--jq", "{owner: .owner.login, name: .name}"], cwd=cwd)
    data = json.loads(proc.stdout)
    return str(data["owner"]), str(data["name"])
