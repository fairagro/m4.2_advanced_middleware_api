#!/usr/bin/env bash
# Prompt for GH_TOKEN and GITGUARDIAN_API_KEY and save (overrides a previous skip).
# Environment: Linux Dev Container only (via scripts/dev-tokens.sh).
# Source this to export into the current shell: source scripts/set-dev-tokens.sh
# Do not `set -euo pipefail` here — this file is sourced into the caller shell.
#
# Wrap in a function so temps stay local and DEV_TOKENS_FORCE is always restored,
# even if sourcing dev-tokens.sh fails under the caller's `set -e`.
# (A file-level `trap … RETURN` would also fire when the nested `source` returns.)
_set_dev_tokens_main() {
  local prev="${DEV_TOKENS_FORCE-}" had=0 status=0
  [ "${DEV_TOKENS_FORCE+x}" = x ] && had=1
  export DEV_TOKENS_FORCE=1
  # shellcheck source=scripts/dev-tokens.sh
  source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dev-tokens.sh" || status=$?
  if [ "${had}" -eq 1 ]; then
    export DEV_TOKENS_FORCE="${prev}"
  else
    unset DEV_TOKENS_FORCE
  fi
  return "${status}"
}
_set_dev_tokens_main
unset -f _set_dev_tokens_main
