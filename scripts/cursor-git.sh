#!/usr/bin/env bash
# Cursor SCM (≥3.15.6) injects core.hooksPath=/dev/null via GIT_CONFIG_*,
# which skips pre-commit. This wrapper strips that pin, then execs real git.
# Invoked as scripts/bin/git (PATH via .devcontainer remoteEnv).
# https://forum.cursor.com/t/167719

set -euo pipefail

REAL_GIT="${CURSOR_REAL_GIT:-}"
if [[ -z "${REAL_GIT}" ]]; then
  for candidate in /usr/bin/git /usr/local/bin/git; do
    if [[ -x "${candidate}" ]]; then
      REAL_GIT="${candidate}"
      break
    fi
  done
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

filtered_args=()
args=("$@")
i=0
while ((i < ${#args[@]})); do
  arg="${args[$i]}"
  if [[ "${arg}" == "-c" ]]; then
    next="${args[$((i + 1))]:-}"
    if [[ "${next}" == core.hooksPath=* ]] && is_null_hooks_path "${next#core.hooksPath=}"; then
      i=$((i + 2))
      continue
    fi
  elif [[ "${arg}" == -ccore.hooksPath=* ]] && is_null_hooks_path "${arg#-ccore.hooksPath=}"; then
    i=$((i + 1))
    continue
  fi
  filtered_args+=("${arg}")
  i=$((i + 1))
done

exec "${REAL_GIT}" "${filtered_args[@]}"
