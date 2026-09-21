"""Regression: store vs host/process env precedence for personal tokens."""

from __future__ import annotations

import base64
import os
import pty
import select
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_TOKENS = REPO_ROOT / "scripts" / "dev-tokens.sh"


def _b64_line(var: str, value: str) -> str:
    encoded = base64.b64encode(value.encode()).decode()
    return f"{var}=b64:{encoded}\n"


def test_stale_env_gh_token_loses_to_store(tmp_path: Path) -> None:
    store = tmp_path / "tokens.env"
    store.write_text(_b64_line("GH_TOKEN", "store-pat-good"), encoding="utf-8")
    script = f"""
set -euo pipefail
export DEV_TOKENS_FILE={store!s}
export GH_TOKEN=stale-agent-bad
# shellcheck disable=SC1091
source {DEV_TOKENS!s}
test "${{GH_TOKEN}}" = "store-pat-good"
"""
    subprocess.run(["bash", "-c", script], check=True, cwd=REPO_ROOT)


def test_missing_store_key_keeps_process_gh_token(tmp_path: Path) -> None:
    store = tmp_path / "tokens.env"
    store.write_text(_b64_line("GITGUARDIAN_API_KEY", "gg-only"), encoding="utf-8")
    script = f"""
set -euo pipefail
export DEV_TOKENS_FILE={store!s}
export GH_TOKEN=host-pat-keep
# shellcheck disable=SC1091
source {DEV_TOKENS!s}
test "${{GH_TOKEN}}" = "host-pat-keep"
test "${{GITGUARDIAN_API_KEY}}" = "gg-only"
"""
    subprocess.run(["bash", "-c", script], check=True, cwd=REPO_ROOT)


def test_absent_store_file_keeps_process_env(tmp_path: Path) -> None:
    store = tmp_path / "missing-tokens.env"
    script = f"""
set -euo pipefail
export DEV_TOKENS_FILE={store!s}
export GH_TOKEN=host-from-remoteenv
export GITGUARDIAN_API_KEY=gg-from-remoteenv
# shellcheck disable=SC1091
source {DEV_TOKENS!s}
test "${{GH_TOKEN}}" = "host-from-remoteenv"
test "${{GITGUARDIAN_API_KEY}}" = "gg-from-remoteenv"
"""
    subprocess.run(["bash", "-c", script], check=True, cwd=REPO_ROOT)


def test_empty_skip_marker_keeps_process_env(tmp_path: Path) -> None:
    """Legacy empty skip markers must not wipe host/process env."""
    store = tmp_path / "tokens.env"
    store.write_text(_b64_line("GH_TOKEN", ""), encoding="utf-8")
    script = f"""
set -euo pipefail
export DEV_TOKENS_FILE={store!s}
export GH_TOKEN=host-pat-keep
# shellcheck disable=SC1091
source {DEV_TOKENS!s}
test "${{GH_TOKEN}}" = "host-pat-keep"
"""
    subprocess.run(["bash", "-c", script], check=True, cwd=REPO_ROOT)


def test_store_after_set_dev_tokens_beats_host(tmp_path: Path) -> None:
    """Simulate set-dev-tokens writing a non-empty store value over host env."""
    store = tmp_path / "tokens.env"
    store.write_text(_b64_line("GH_TOKEN", "store-override"), encoding="utf-8")
    script = f"""
set -euo pipefail
export DEV_TOKENS_FILE={store!s}
export GH_TOKEN=host-should-lose
# shellcheck disable=SC1091
source {DEV_TOKENS!s}
test "${{GH_TOKEN}}" = "store-override"
"""
    subprocess.run(["bash", "-c", script], check=True, cwd=REPO_ROOT)


def test_empty_tty_answer_does_not_write_skip_marker(tmp_path: Path) -> None:
    store = tmp_path / "tokens.env"
    store.write_text("", encoding="utf-8")
    script = f"""
set -euo pipefail
export DEV_TOKENS_FILE={store!s}
export DEV_TOKENS_FORCE=1
unset GH_TOKEN GITGUARDIAN_API_KEY || true
# shellcheck disable=SC1091
source {DEV_TOKENS!s}
# Empty answers must not create skip markers.
if grep -qE '^GH_TOKEN=' {store!s} 2>/dev/null; then
  echo "unexpected GH_TOKEN line in store" >&2
  exit 1
fi
if grep -qE '^GITGUARDIAN_API_KEY=' {store!s} 2>/dev/null; then
  echo "unexpected GITGUARDIAN_API_KEY line in store" >&2
  exit 1
fi
test -z "${{GH_TOKEN-}}"
test -z "${{GITGUARDIAN_API_KEY-}}"
"""
    master, slave = pty.openpty()
    try:
        proc = subprocess.Popen(
            ["bash", "-c", script],
            stdin=slave,
            stdout=slave,
            stderr=subprocess.PIPE,
            cwd=REPO_ROOT,
            text=True,
        )
        os.close(slave)
        slave = -1
        deadline = time.monotonic() + 5.0
        answers_left = 2  # GH_TOKEN + GITGUARDIAN_API_KEY
        while proc.poll() is None and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    _ = os.read(master, 4096)
                except OSError:
                    break
                if answers_left > 0:
                    os.write(master, b"\n")
                    answers_left -= 1
            time.sleep(0.05)
        # Drain any remaining prompts
        while answers_left > 0 and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.2)
            if ready:
                try:
                    _ = os.read(master, 4096)
                except OSError:
                    break
            os.write(master, b"\n")
            answers_left -= 1
        status = proc.wait(timeout=5)
        err = proc.stderr.read() if proc.stderr else ""
        assert status == 0, f"script failed ({status}): {err}"
    finally:
        if slave >= 0:
            os.close(slave)
        os.close(master)
