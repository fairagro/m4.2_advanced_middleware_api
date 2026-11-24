#!/usr/bin/env bash
# Force-prompt for GH_TOKEN and save non-empty values to the store
# (overrides host/process env on later loads). Environment: Linux Dev Container only.
# Source this to export into the current shell: source scripts/set-dev-tokens.sh
# Do not `set -euo pipefail` here — this file is sourced into the caller shell.
#
# Wrap in a function so temps stay local and DEV_TOKENS_FORCE is always restored,
# even if sourcing dev-tokens.sh fails under the caller's `set -e`.
# (A file-level `trap … RETURN` would also fire when the nested `source` returns.)
_set_dev_tokens_main() {
  local prev="${DEV_TOKENS_FORCE-}" had=0 status=0
  [ "${DEV_TOKENS_FORCE+x}" = x ] && had=1

  _set_dev_tokens_cleanup() {
    if [ "${had}" -eq 1 ]; then
      export DEV_TOKENS_FORCE="${prev}"
    else
      unset DEV_TOKENS_FORCE
    fi
    # Shared tty: cancelled read -s can leave echo off (#411).
    stty echo </dev/tty 2>/dev/null || stty echo 2>/dev/null || true
  }

  export DEV_TOKENS_FORCE=1
  # INT during nested source/read must still clear FORCE and restore echo (#411).
  trap '_set_dev_tokens_cleanup; return 130' INT
  # shellcheck source=scripts/dev-tokens.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-tokens.sh" || status=$?
  trap - INT
  _set_dev_tokens_cleanup
  unset -f _set_dev_tokens_cleanup
  return "${status}"
}
_set_dev_tokens_main
unset -f _set_dev_tokens_main
