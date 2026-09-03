# Personal GH_TOKEN / GITGUARDIAN_API_KEY. Source this file.
# Empty prompt = skip (remembered). To set later: ./scripts/set-dev-tokens.sh
# Store: /commandhistory/tokens.env or ~/.config/middleware-api/tokens.env

_dev_tokens_file() {
    if [ -d /commandhistory ]; then
        echo /commandhistory/tokens.env
    else
        mkdir -p "${HOME}/.config/middleware-api"
        echo "${HOME}/.config/middleware-api/tokens.env"
    fi
}

_DEV_TOKENS_FILE="$(_dev_tokens_file)"
# Apply stored tokens without clobbering a caller-set value, and without
# exporting empty "skip" markers (GH_TOKEN='') over a live environment.
if [ -f "${_DEV_TOKENS_FILE}" ]; then
    for _dev_tokens_var in GH_TOKEN GITGUARDIAN_API_KEY; do
        if [ -n "${!_dev_tokens_var-}" ]; then
            continue
        fi
        _dev_tokens_val="$(
            set -a
            # shellcheck disable=SC1090
            source "${_DEV_TOKENS_FILE}"
            set +a
            printf '%s' "${!_dev_tokens_var-}"
        )"
        if [ -n "${_dev_tokens_val}" ]; then
            export "${_dev_tokens_var}=${_dev_tokens_val}"
        fi
    done
    unset _dev_tokens_var _dev_tokens_val
fi

_dev_tokens_write() {
    local var=$1 val=$2
    (
        umask 077
        touch "${_DEV_TOKENS_FILE}"
        chmod 600 "${_DEV_TOKENS_FILE}"
        grep -v "^${var}=" "${_DEV_TOKENS_FILE}" > "${_DEV_TOKENS_FILE}.tmp" 2>/dev/null || true
        printf '%s=%q\n' "${var}" "${val}" >> "${_DEV_TOKENS_FILE}.tmp"
        mv "${_DEV_TOKENS_FILE}.tmp" "${_DEV_TOKENS_FILE}"
    )
}

_dev_tokens_ask() {
    local var=$1 hint=$2 val cur
    cur="${!var-}"
    if [ -z "${DEV_TOKENS_FORCE:-}" ]; then
        [ -n "${cur}" ] && return 0
        grep -q "^${var}=" "${_DEV_TOKENS_FILE}" 2>/dev/null && return 0
    fi
    { printf '' >/dev/tty; } 2>/dev/null || return 0
    printf '%s — %s (empty skips until set-dev-tokens.sh)\n> ' "${var}" "${hint}" >/dev/tty
    IFS= read -r -s val </dev/tty || return 0
    printf '\n' >/dev/tty
    _dev_tokens_write "${var}" "${val}"
    [ -n "${val}" ] && export "${var}=${val}"
}

_dev_tokens_ask GH_TOKEN "GitHub PAT (issues + PRs)"
_dev_tokens_ask GITGUARDIAN_API_KEY "GitGuardian API key"
unset -f _dev_tokens_file _dev_tokens_write _dev_tokens_ask
unset _DEV_TOKENS_FILE
