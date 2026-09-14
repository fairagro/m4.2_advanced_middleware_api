"""Regression: stale process GH_TOKEN must not shadow the token store."""

from __future__ import annotations

import base64
import subprocess
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


def test_missing_store_key_unsets_process_gh_token(tmp_path: Path) -> None:
    store = tmp_path / "tokens.env"
    store.write_text(_b64_line("GITGUARDIAN_API_KEY", "gg-only"), encoding="utf-8")
    script = f"""
set -euo pipefail
export DEV_TOKENS_FILE={store!s}
export GH_TOKEN=stale-should-clear
# shellcheck disable=SC1091
source {DEV_TOKENS!s}
test -z "${{GH_TOKEN-}}"
test "${{GITGUARDIAN_API_KEY}}" = "gg-only"
"""
    subprocess.run(["bash", "-c", script], check=True, cwd=REPO_ROOT)
