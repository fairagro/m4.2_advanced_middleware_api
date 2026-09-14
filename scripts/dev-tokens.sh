# Personal GH_TOKEN / GITGUARDIAN_API_KEY. Source this file.
# Environment: Linux Dev Container only (requires /commandhistory).
# Empty prompt = skip (remembered). To set later: source ./scripts/set-dev-tokens.sh
# Store: /commandhistory/tokens.env (sole source — process env does not override it).

if [ "${BASH_SOURCE[0]-}" = "${0-}" ]; then
  echo "dev-tokens: source this file (do not execute it directly)" >&2
  echo "dev-tokens: example: source ./scripts/dev-tokens.sh" >&2
  exit 1
fi

_dev_tokens_file() {
  # Test/smoke only: absolute path override (do not use for normal interactive work).
  if [ -n "${DEV_TOKENS_FILE:-}" ]; then
    printf '%s\n' "${DEV_TOKENS_FILE}"
    return 0
  fi
  if [ -d /commandhistory ]; then
    echo /commandhistory/tokens.env
    return 0
  fi
  echo "dev-tokens: /commandhistory missing — personal tokens are supported in the Linux Dev Container only" >&2
  return 1
}

# Decode one stored value. Writes use b64:<base64> only — no legacy parsers.
_dev_tokens_decode_raw() {
  local raw=$1
  local decoded
  if [ "${raw#b64:}" != "${raw}" ]; then
    if decoded="$(printf '%s' "${raw#b64:}" | base64 -d 2>/dev/null)"; then
      printf '%s' "${decoded}"
      return 0
    fi
    echo "dev-tokens: ignoring corrupt b64 token entry" >&2
    return 1
  fi
  if [ -n "${raw}" ]; then
    echo "dev-tokens: ignoring non-b64 token entry (re-run: source ./scripts/set-dev-tokens.sh)" >&2
  fi
  return 1
}

_dev_tokens_get_stored() {
  local var=$1 line raw
  [ -f "${_DEV_TOKENS_FILE}" ] || return 0
  line="$(grep -E "^${var}=" "${_DEV_TOKENS_FILE}" 2>/dev/null | tail -n1)" || true
  [ -n "${line}" ] || return 0
  raw="${line#*=}"
  _dev_tokens_decode_raw "${raw}" || true
}

_DEV_TOKENS_FILE="$(_dev_tokens_file)" || return 1

# If the environment already holds a store-encoded value (e.g. someone ran
# `source /commandhistory/tokens.env`), decode it in place before applying the store.
for _dev_tokens_var in GH_TOKEN GITGUARDIAN_API_KEY; do
  _dev_tokens_cur="${!_dev_tokens_var-}"
  if [ -n "${_dev_tokens_cur}" ] && [ "${_dev_tokens_cur#b64:}" != "${_dev_tokens_cur}" ]; then
    if _dev_tokens_val="$(_dev_tokens_decode_raw "${_dev_tokens_cur}")"; then
      export "${_dev_tokens_var}=${_dev_tokens_val}"
    else
      unset "${_dev_tokens_var}"
    fi
  fi
done
unset _dev_tokens_var _dev_tokens_cur _dev_tokens_val

# Store is the sole source for known keys. Process env never overrides the store:
# missing key → unset; empty skip marker → unset; non-empty → export store value.
if [ -f "${_DEV_TOKENS_FILE}" ]; then
  for _dev_tokens_var in GH_TOKEN GITGUARDIAN_API_KEY; do
    if grep -q "^${_dev_tokens_var}=" "${_DEV_TOKENS_FILE}" 2>/dev/null; then
      _dev_tokens_val="$(_dev_tokens_get_stored "${_dev_tokens_var}")"
      if [ -n "${_dev_tokens_val}" ]; then
        export "${_dev_tokens_var}=${_dev_tokens_val}"
      else
        unset "${_dev_tokens_var}"
      fi
    else
      unset "${_dev_tokens_var}"
    fi
  done
  unset _dev_tokens_var _dev_tokens_val
else
  unset GH_TOKEN GITGUARDIAN_API_KEY
fi

_dev_tokens_write() {
  local var=$1 val=$2 b64 tmp
  (
    set -euo pipefail
    umask 077
    touch "${_DEV_TOKENS_FILE}"
    chmod 600 "${_DEV_TOKENS_FILE}"
    # Bash may not trip `set -e` on a failing command-substitution assignment — check explicitly.
    tmp="$(mktemp "${_DEV_TOKENS_FILE}.XXXXXX")" || exit 1
    # Remove temp (may hold encoded secrets) if we exit before a successful rename.
    trap 'rm -f "${tmp}"' EXIT
    # grep exit 1 = no remaining lines (empty or only this var) — OK; other statuses abort.
    # Capture status before `case` — bash sets $? to 0 when a case arm matches.
    grep -v "^${var}=" "${_DEV_TOKENS_FILE}" >"${tmp}" 2>/dev/null || {
      _grep_st=$?
      case ${_grep_st} in
        1) ;;
        *) exit "${_grep_st}" ;;
      esac
    }
    # GNU coreutils in the Dev Container (no BSD wrap fallback).
    b64="$(printf '%s' "${val}" | base64 -w0)" || exit 1
    printf '%s=b64:%s\n' "${var}" "${b64}" >>"${tmp}"
    # Atomic replace: do not truncate the live store via redirect.
    chmod 600 "${tmp}"
    mv -f "${tmp}" "${_DEV_TOKENS_FILE}"
    trap - EXIT
  )
}

_dev_tokens_ask() {
  local var=$1 hint=$2 val
  if [ -z "${DEV_TOKENS_FORCE:-}" ]; then
    grep -q "^${var}=" "${_DEV_TOKENS_FILE}" 2>/dev/null && return 0
  fi
  { printf '' >/dev/tty; } 2>/dev/null || return 0
  printf '%s — %s (empty skips until set-dev-tokens.sh)\n> ' "${var}" "${hint}" >/dev/tty
  IFS= read -r -s val </dev/tty || true
  printf '\n' >/dev/tty
  if ! _dev_tokens_write "${var}" "${val}"; then
    echo "dev-tokens: failed to persist ${var}; value kept for this shell only (re-run: source ./scripts/set-dev-tokens.sh)" >&2
  fi
  if [ -n "${val}" ]; then
    export "${var}=${val}"
  else
    unset "${var}"
  fi
  return 0
}

_dev_tokens_ask GH_TOKEN "GitHub PAT (issues + PRs)"
_dev_tokens_ask GITGUARDIAN_API_KEY "GitGuardian API key"
unset -f _dev_tokens_file _dev_tokens_write _dev_tokens_ask
unset -f _dev_tokens_decode_raw _dev_tokens_get_stored
unset _DEV_TOKENS_FILE
