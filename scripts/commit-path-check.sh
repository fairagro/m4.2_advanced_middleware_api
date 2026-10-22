#!/usr/bin/env bash
# Commit-msg path check: reject feat/fix (and docs-on-archive) when the staged
# index is OpenSpec-planning-only, archive/spec-sync-only, or test-only.
# Fleet gate beside commitlint (#320). Usage:
#   scripts/commit-path-check.sh [--staged-from FILE] <commit-message-file>
# --staged-from: one path per line (tests); default: git diff --cached --name-only

set -euo pipefail

STAGED_FROM=""
MSG_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --staged-from)
      if [[ $# -lt 2 || -z "${2}" ]]; then
        echo "commit-path-check: --staged-from requires a file path" >&2
        exit 2
      fi
      STAGED_FROM="$2"
      shift 2
      ;;
    -h | --help)
      cat <<'EOF'
Usage: commit-path-check.sh [--staged-from FILE] <commit-message-file>

Reject feat/fix when staged paths are only OpenSpec planning, archive+specs
sync, or tests. Reject docs when the commit is an OpenSpec archive (+ optional
spec sync). Soft-pass when there are no staged paths or the type is not gated.
EOF
      exit 0
      ;;
    *)
      MSG_FILE="$1"
      shift
      ;;
  esac
done

if [[ -z "${MSG_FILE}" || ! -f "${MSG_FILE}" ]]; then
  echo "commit-path-check: missing commit message file" >&2
  exit 2
fi

# First non-comment, non-empty line (commitlint subject line)
subject=""
while IFS= read -r line || [[ -n "${line}" ]]; do
  line="${line%$'\r'}"
  [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
  subject="${line}"
  break
done <"${MSG_FILE}"

if [[ -z "${subject}" ]]; then
  exit 0
fi

# Conventional Commits: type(optional-scope)!: subject — extract type only
ctype="$(printf '%s\n' "${subject}" | sed -nE 's/^([a-z]+)(\([^)]*\))?(!)?:.*/\1/p')"
if [[ -z "${ctype}" ]]; then
  # Non-conventional subjects: leave to commitlint
  exit 0
fi

if [[ -n "${STAGED_FROM}" && ! -f "${STAGED_FROM}" ]]; then
  echo "commit-path-check: --staged-from file not found: ${STAGED_FROM}" >&2
  exit 2
fi

mapfile -t staged < <(
  if [[ -n "${STAGED_FROM}" ]]; then
    grep -v '^[[:space:]]*$' "${STAGED_FROM}" || true
  else
    # Include deletions (D): delete-only OpenSpec/test indexes must still hit the type gate.
    # Spec: git diff --cached --name-only (no ACMR-only filter).
    git diff --cached --name-only || true
  fi
)

if [[ "${#staged[@]}" -eq 0 ]]; then
  exit 0
fi

# Renovate / dependency bumps: not gated by this path matrix
if [[ "${ctype}" == "deps" ]]; then
  exit 0
fi

classify() {
  local p="$1"
  if [[ "${p}" == openspec/changes/archive/* || "${p}" == openspec/changes/archive ]]; then
    echo archive
  elif [[ "${p}" == openspec/changes/* ]]; then
    echo planning
  elif [[ "${p}" == openspec/specs/* || "${p}" == openspec/specs ]]; then
    echo specs
  elif [[ "${p}" =~ /(tests|test)/ ]] || [[ "$(basename "${p}")" =~ ^(test_.*|.*_test)\.(py|go)$ ]] ||
    [[ "$(basename "${p}")" =~ \.(test|spec)\.(ts|tsx|js|jsx)$ ]]; then
    echo test
  else
    echo other
  fi
}

has_planning=0
has_archive=0
has_specs=0
has_test=0
has_other=0

for p in "${staged[@]}"; do
  case "$(classify "${p}")" in
    planning) has_planning=1 ;;
    archive) has_archive=1 ;;
    specs) has_specs=1 ;;
    test) has_test=1 ;;
    other) has_other=1 ;;
  esac
done

fail() {
  echo "commit-path-check: $1" >&2
  echo "commit-path-check: subject was: ${subject}" >&2
  echo "commit-path-check: use an appropriate Conventional Commits type for these staged paths (see docs/quality.md)." >&2
  exit 1
}

# docs on archive (+ optional specs) only when the subject indicates archive → chore(openspec)
# Subject gate avoids rejecting routine docs edits under openspec/changes/archive/**
# Match "archive" as a word (not "archived").
if [[ "${ctype}" == "docs" && "${has_archive}" -eq 1 && "${has_planning}" -eq 0 && "${has_test}" -eq 0 &&
  "${has_other}" -eq 0 ]]; then
  subject_lc="$(printf '%s\n' "${subject}" | tr '[:upper:]' '[:lower:]')"
  if printf '%s\n' "${subject_lc}" | grep -Eq '(^|[^a-z])archive([^a-z]|$)'; then
    fail "OpenSpec archive commits must use type 'chore' (optional scope openspec), not 'docs'"
  fi
fi

if [[ "${ctype}" != "feat" && "${ctype}" != "fix" ]]; then
  exit 0
fi

# feat/fix + only OpenSpec planning
if [[ "${has_planning}" -eq 1 && "${has_archive}" -eq 0 && "${has_specs}" -eq 0 && "${has_test}" -eq 0 &&
  "${has_other}" -eq 0 ]]; then
  fail "type '${ctype}' is not allowed when the index is only OpenSpec planning under openspec/changes/ (non-archive)"
fi

# feat/fix + only archive and/or main specs
if [[ "${has_other}" -eq 0 && "${has_test}" -eq 0 && "${has_planning}" -eq 0 &&
  ("${has_archive}" -eq 1 || "${has_specs}" -eq 1) ]]; then
  fail "type '${ctype}' is not allowed for OpenSpec archive / main-spec sync only — use chore(openspec)"
fi

# feat/fix + only tests
if [[ "${has_test}" -eq 1 && "${has_planning}" -eq 0 && "${has_archive}" -eq 0 && "${has_specs}" -eq 0 &&
  "${has_other}" -eq 0 ]]; then
  fail "type '${ctype}' is not allowed when the index is test-only — use 'test' or 'refactor'"
fi

exit 0
