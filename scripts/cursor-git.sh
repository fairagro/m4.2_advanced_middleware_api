#!/usr/bin/env bash
# Wrapper for Cursor Source Control: strip the extension's
# GIT_CONFIG_* override of core.hooksPath → /dev/null (or Windows NUL).
#
# Cursor ≥3.15.6 injects that override on every SCM git spawn, which silently
# skips pre-commit / commit-msg / pre-push. Terminal `git` is unaffected.
# Point "git.path" at this script (see .vscode/settings.json) until Cursor fixes it:
# https://forum.cursor.com/t/167719
#
# Only removes null-device hooksPath pins; other injected keys are left alone.

set -euo pipefail

REAL_GIT="${CURSOR_REAL_GIT:-}"
if [[ -z "${REAL_GIT}" ]]; then
  if [[ -x /usr/bin/git ]]; then
    REAL_GIT=/usr/bin/git
  else
    REAL_GIT="$(command -v -p git 2>/dev/null || command -v git)"
  fi
fi

is_null_hooks_path() {
  case "$1" in
    /dev/null | NUL | nul | "\\\\.\\nul" | '//./nul') return 0 ;;
    *) return 1 ;;
  esac
}

count="${GIT_CONFIG_COUNT:-0}"
if [[ "${count}" =~ ^[0-9]+$ ]] && ((count > 0)); then
  new_keys=()
  new_vals=()
  for ((i = 0; i < count; i++)); do
    key_var="GIT_CONFIG_KEY_${i}"
    val_var="GIT_CONFIG_VALUE_${i}"
    key="${!key_var-}"
    val="${!val_var-}"
    if [[ "${key}" == "core.hooksPath" ]] && is_null_hooks_path "${val}"; then
      continue
    fi
    new_keys+=("${key}")
    new_vals+=("${val}")
  done
  for ((i = 0; i < count; i++)); do
    unset "GIT_CONFIG_KEY_${i}" "GIT_CONFIG_VALUE_${i}" || true
  done
  unset GIT_CONFIG_COUNT || true
  export GIT_CONFIG_COUNT="${#new_keys[@]}"
  for i in "${!new_keys[@]}"; do
    export "GIT_CONFIG_KEY_${i}=${new_keys[$i]}"
    export "GIT_CONFIG_VALUE_${i}=${new_vals[$i]}"
  done
fi

exec "${REAL_GIT}" "$@"
