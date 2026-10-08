#!/usr/bin/env bash
# Emit a ## Changelog section for Final GitHub Releases via git-cliff (R1 surface tags).
# Soft-fail (exit 0 + placeholder markdown): empty cliff output or git-cliff process failure.
# Usage/arg errors still exit non-zero so the caller fails closed on bad invocation.
#
# Usage:
#   scripts/generate-release-changelog.sh --surface docker|helm [--new-tag TAG] [--repo owner/name]
# Env: GIT_CLIFF_CONFIG (default: repo-root cliff.toml), GITHUB_REPOSITORY (for compare link)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

SURFACE=""
NEW_TAG=""
REPO="${GITHUB_REPOSITORY:-}"

usage() {
  echo "Usage: $0 --surface docker|helm [--new-tag TAG] [--repo owner/name]" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --surface)
      SURFACE="${2:-}"
      shift 2
      ;;
    --new-tag)
      NEW_TAG="${2:-}"
      shift 2
      ;;
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "generate-release-changelog: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "${SURFACE}" != "docker" && "${SURFACE}" != "helm" ]]; then
  echo "generate-release-changelog: --surface must be docker or helm" >&2
  exit 1
fi

if [[ "${SURFACE}" == "docker" ]]; then
  TAG_GLOB='*-docker-v*'
  TAG_GREP='^[0-9]+-docker-v[0-9]+\.[0-9]+\.[0-9]+$'
else
  TAG_GLOB='*-chart-v*'
  TAG_GREP='^[0-9]+-chart-v[0-9]+\.[0-9]+\.[0-9]+$'
fi

mapfile -t MATCHING_TAGS < <(git tag --list "${TAG_GLOB}" | grep -E "${TAG_GREP}" | sort -V || true)

RANGE_FROM=""
if [[ ${#MATCHING_TAGS[@]} -gt 0 ]]; then
  LATEST="${MATCHING_TAGS[-1]}"
  if [[ -n "${NEW_TAG}" && "${LATEST}" == "${NEW_TAG}" ]]; then
    if [[ ${#MATCHING_TAGS[@]} -ge 2 ]]; then
      RANGE_FROM="${MATCHING_TAGS[-2]}"
    fi
  else
    RANGE_FROM="${LATEST}"
  fi
fi

emit_placeholder() {
  local reason="$1"
  echo "## Changelog"
  echo ""
  echo "_${reason}_"
  echo ""
}

if ! command -v git-cliff >/dev/null 2>&1; then
  echo "generate-release-changelog: git-cliff not on PATH (install via scripts/install-git-cliff.sh)" >&2
  emit_placeholder "Changelog unavailable (git-cliff not installed)."
  exit 0
fi

CLIFF_CONFIG="${GIT_CLIFF_CONFIG:-${REPO_ROOT}/cliff.toml}"
if [[ ! -f "${CLIFF_CONFIG}" ]]; then
  echo "generate-release-changelog: cliff config not found: ${CLIFF_CONFIG}" >&2
  emit_placeholder "Changelog unavailable (cliff.toml missing)."
  exit 0
fi

RANGE_ARGS=()
if [[ -n "${RANGE_FROM}" ]]; then
  if [[ -n "${NEW_TAG}" ]]; then
    RANGE_ARGS=("${RANGE_FROM}..${NEW_TAG}")
  else
    RANGE_ARGS=("${RANGE_FROM}..HEAD")
  fi
elif [[ -n "${NEW_TAG}" ]]; then
  RANGE_ARGS=("${NEW_TAG}")
fi

CLIFF_ERR="$(mktemp)"
set +e
CHANGELOG_BODY="$(git cliff "${RANGE_ARGS[@]}" --config "${CLIFF_CONFIG}" 2>"${CLIFF_ERR}")"
CLIFF_EC=$?
set -e
if [[ "${CLIFF_EC}" -ne 0 ]]; then
  echo "generate-release-changelog: git-cliff exited ${CLIFF_EC} (surface=${SURFACE}, range=${RANGE_ARGS[*]:-<root>})" >&2
  cat "${CLIFF_ERR}" >&2 || true
  rm -f "${CLIFF_ERR}"
  emit_placeholder "Changelog unavailable (git-cliff failed — see workflow logs)."
  exit 0
fi
rm -f "${CLIFF_ERR}"

# Trim and treat whitespace-only / header-only empties as no entries.
BODY_TRIMMED="$(printf '%s' "${CHANGELOG_BODY}" | sed -e 's/[[:space:]]*$//' | sed -e '/./,$!d')"
if [[ -z "${BODY_TRIMMED}" ]] || ! printf '%s\n' "${BODY_TRIMMED}" | grep -qE '^- '; then
  echo "generate-release-changelog: empty changelog (surface=${SURFACE}, range=${RANGE_ARGS[*]:-<root>})" >&2
  emit_placeholder "No Conventional Commits changelog entries for this release range."
  # Still offer compare link when we have both tags.
  if [[ -n "${RANGE_FROM}" && -n "${NEW_TAG}" && -n "${REPO}" ]]; then
    echo "**Full Changelog:** https://github.com/${REPO}/compare/${RANGE_FROM}...${NEW_TAG}"
    echo ""
  fi
  exit 0
fi

echo "## Changelog"
echo ""
printf '%s\n' "${BODY_TRIMMED}"
echo ""

if [[ -n "${RANGE_FROM}" && -n "${NEW_TAG}" && -n "${REPO}" ]]; then
  echo "**Full Changelog:** https://github.com/${REPO}/compare/${RANGE_FROM}...${NEW_TAG}"
  echo ""
fi
