#!/usr/bin/env bash
# Wrapper for Cursor Source Control: strip the extension's
# core.hooksPath → /dev/null (or Windows NUL) override.
#
# Cursor ≥3.15.6 injects that pin on every SCM git spawn (usually via
# GIT_CONFIG_KEY_*/GIT_CONFIG_VALUE_*, sometimes as ``git -c``), which silently
# skips pre-commit / commit-msg / pre-push. Terminal ``git`` is unaffected.
#
# Point **Remote** ``git.path`` (not workspace settings) at this script:
#   /workspaces/m4.2_advanced_middleware_api/scripts/cursor-git.sh
# After a UI commit, check ``/tmp/cursor-git-wrapper.log`` — if empty, Cursor
# is not using this wrapper (set Remote git.path, then Reload Window).
# https://forum.cursor.com/t/167719

set -euo pipefail

LOG_FILE="${CURSOR_GIT_WRAPPER_LOG:-/tmp/cursor-git-wrapper.log}"
WRAPPER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REAL_GIT="${CURSOR_REAL_GIT:-}"
if [[ -z "${REAL_GIT}" ]]; then
  # Prefer a real binary, never this wrapper (avoid recursion if PATH is odd).
  for candidate in /usr/bin/git /usr/local/bin/git; do
    if [[ -x "${candidate}" && "${candidate}" != "${BASH_SOURCE[0]}" ]]; then
      REAL_GIT="${candidate}"
      break
    fi
  done
  if [[ -z "${REAL_GIT}" ]]; then
    REAL_GIT="$(command -v -p git 2>/dev/null || true)"
  fi
fi
if [[ -z "${REAL_GIT}" || ! -x "${REAL_GIT}" ]]; then
  echo "cursor-git.sh: could not find real git binary" >&2
  exit 127
fi

is_null_hooks_path() {
  case "$1" in
    /dev/null | NUL | nul | "\\\\.\\nul" | '//./nul') return 0 ;;
    *) return 1 ;;
  esac
}

# --- Strip GIT_CONFIG_* command-scope pin ------------------------------------
count="${GIT_CONFIG_COUNT:-0}"
stripped_env=0
if [[ "${count}" =~ ^[0-9]+$ ]] && ((count > 0)); then
  new_keys=()
  new_vals=()
  for ((i = 0; i < count; i++)); do
    key_var="GIT_CONFIG_KEY_${i}"
    val_var="GIT_CONFIG_VALUE_${i}"
    key="${!key_var-}"
    val="${!val_var-}"
    if [[ "${key}" == "core.hooksPath" ]] && is_null_hooks_path "${val}"; then
      stripped_env=1
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

# --- Strip ``git -c core.hooksPath=/dev/null`` if present ---------------------
filtered_args=()
stripped_argv=0
args=("$@")
i=0
while ((i < ${#args[@]})); do
  arg="${args[$i]}"
  if [[ "${arg}" == "-c" ]]; then
    next="${args[$((i + 1))]:-}"
    if [[ "${next}" == core.hooksPath=* ]]; then
      val="${next#core.hooksPath=}"
      if is_null_hooks_path "${val}"; then
        stripped_argv=1
        i=$((i + 2))
        continue
      fi
    fi
  elif [[ "${arg}" == -ccore.hooksPath=* ]]; then
    val="${arg#-ccore.hooksPath=}"
    if is_null_hooks_path "${val}"; then
      stripped_argv=1
      i=$((i + 1))
      continue
    fi
  fi
  filtered_args+=("${arg}")
  i=$((i + 1))
done

# Diagnostic: proves the SCM UI invoked this wrapper (not system git).
{
  printf '%s cmd=%q' "$(date -Iseconds)" "${REAL_GIT}"
  printf ' %q' "${filtered_args[@]}"
  printf ' stripped_env=%s stripped_argv=%s GIT_CONFIG_COUNT=%s\n' \
    "${stripped_env}" "${stripped_argv}" "${GIT_CONFIG_COUNT:-0}"
} >>"${LOG_FILE}" 2>/dev/null || true

exec "${REAL_GIT}" "${filtered_args[@]}"
